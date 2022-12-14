from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from pathlib import Path

from dandischema.digests.zarr import (
    EMPTY_CHECKSUM,
    ZarrChecksum,
    ZarrJSONChecksumSerializer,
)

__all__ = ["ZarrChecksumModification", "ZarrChecksumModificationQueue"]


@dataclass
class ZarrChecksumModification:
    """
    A set of changes to apply to a ZarrChecksumListing.

    Additions or modifications are stored in files_to_update and directories_to_update.
    """

    path: Path
    files_to_update: list[ZarrChecksum] = field(default_factory=list)
    directories_to_update: list[ZarrChecksum] = field(default_factory=list)

    def __lt__(self, other):
        return str(self.path) < str(other.path)


class ZarrChecksumModificationQueue:
    """
    A queue of modifications to be applied to a zarr archive.

    It is important to apply modifications starting as deep as possible, because every modification
    changes the checksum of its parent, which bubbles all the way up to the top of the tree hash.
    This class makes managing that queue of modifications much easier.
    """

    def __init__(self) -> None:
        self._heap: list[tuple[int, ZarrChecksumModification]] = []
        self._path_map: dict[Path, ZarrChecksumModification] = {}

    @property
    def empty(self):
        return len(self._heap) == 0

    def _add_path(self, key: Path):
        modification = ZarrChecksumModification(path=key)

        # Add link to modification
        self._path_map[key] = modification

        # Add modification to heap with length (negated to representa max heap)
        length = len(key.parents)
        heapq.heappush(self._heap, (-1 * length, modification))

    def _get_path(self, key: Path):
        if key not in self._path_map:
            self._add_path(key)

        return self._path_map[key]

    def queue_file_update(self, key: Path, checksum: ZarrChecksum):
        self._get_path(key).files_to_update.append(checksum)

    def queue_directory_update(self, key: Path, checksum: ZarrChecksum):
        self._get_path(key).directories_to_update.append(checksum)

    def pop_deepest(self) -> ZarrChecksumModification:
        """Find the deepest path in the queue, and return it and its children to be updated."""
        _, modification = heapq.heappop(self._heap)
        del self._path_map[modification.path]

        return modification

    def process(self):
        """Process the queue, returning the resulting top level digest."""
        while not self.empty:
            # Pop the deepest directory available
            modification = self.pop_deepest()
            # print(f"Processing {modification.path}")

            # Generates a sorted checksum listing for the current path
            checksum_listing = ZarrJSONChecksumSerializer().generate_listing(
                files=modification.files_to_update,
                directories=modification.directories_to_update,
            )
            latest_checksum = checksum_listing

            # If we have reached the root node, then we're done.
            if modification.path == Path(".") or modification.path == Path("/"):
                return latest_checksum.digest

            # The parent needs to incorporate the checksum modification we just made.
            self.queue_directory_update(
                modification.path.parent,
                ZarrChecksum(
                    name=modification.path.name,
                    digest=checksum_listing.digest,
                    size=checksum_listing.size,
                ),
            )

        return EMPTY_CHECKSUM
