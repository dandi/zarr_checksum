from __future__ import annotations

from dataclasses import dataclass
import heapq
from pathlib import Path

from zarr_checksum.checksum import ZarrChecksum, ZarrChecksumManifest, ZarrDirectoryDigest

__all__ = ["ZarrChecksumNode", "ZarrChecksumTree"]


# Pydantic models aren't used for performance reasons
@dataclass
class ZarrChecksumNode:
    """Represents the aggregation of zarr files at a specific path in the tree."""

    path: Path
    checksums: ZarrChecksumManifest

    def __lt__(self, other):
        return str(self.path) < str(other.path)


class ZarrChecksumTree:
    """A tree that represents the checksummed files in a zarr."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, ZarrChecksumNode]] = []
        self._path_map: dict[Path, ZarrChecksumNode] = {}

    @property
    def empty(self):
        return len(self._heap) == 0

    def _add_path(self, key: Path):
        node = ZarrChecksumNode(path=key, checksums=ZarrChecksumManifest())

        # Add link to node
        self._path_map[key] = node

        # Add node to heap with length (negated to representa max heap)
        length = len(key.parents)
        heapq.heappush(self._heap, (-1 * length, node))

    def _get_path(self, key: Path):
        if key not in self._path_map:
            self._add_path(key)

        return self._path_map[key]

    def add_leaf(self, path: Path, size: int, digest: str):
        """Add a leaf file to the tree."""
        parent_node = self._get_path(path.parent)
        parent_node.checksums.files.append(ZarrChecksum(name=path.name, size=size, digest=digest))

    def add_node(self, path: Path, size: int, digest: str):
        """Add an internal node to the tree."""
        parent_node = self._get_path(path.parent)
        parent_node.checksums.directories.append(
            ZarrChecksum(
                name=path.name,
                size=size,
                digest=digest,
            )
        )

    def pop_deepest(self) -> ZarrChecksumNode:
        """Find the deepest node in the tree, and return it."""
        _, node = heapq.heappop(self._heap)
        del self._path_map[node.path]

        return node

    def process(self) -> ZarrDirectoryDigest:
        """Process the tree, returning the resulting top level digest."""
        # Begin with empty root node, so if no files are present, the empty checksum is returned
        node = ZarrChecksumNode(path=".", checksums=ZarrChecksumManifest())
        while not self.empty:
            # Pop the deepest directory available
            node = self.pop_deepest()

            # If we have reached the root node, then we're done.
            if node.path == Path(".") or node.path == Path("/"):
                break

            # Add the parent of this node to the tree
            directory_digest = node.checksums.generate_digest()
            self.add_node(
                path=node.path,
                size=directory_digest.size,
                digest=directory_digest.digest,
            )

        # Return digest
        return node.checksums.generate_digest()
