from __future__ import annotations

from functools import total_ordering
import hashlib
import re
from typing import List

import pydantic

ZARR_DIGEST_PATTERN = "([0-9a-f]{32})-([0-9]+)--([0-9]+)"


class InvalidZarrChecksum(Exception):
    pass


class ZarrDirectoryDigest(pydantic.BaseModel):
    """The data that can be serialized to / deserialized from a checksum string."""

    md5: str
    count: int
    size: int

    @classmethod
    def parse(cls, checksum: str | None) -> ZarrDirectoryDigest:
        if checksum is None:
            return cls.parse(EMPTY_CHECKSUM)

        match = re.match(ZARR_DIGEST_PATTERN, checksum)
        if match is None:
            raise InvalidZarrChecksum()

        md5, count, size = match.groups()
        return cls(md5=md5, count=count, size=size)

    def __str__(self) -> str:
        return self.digest

    @property
    def digest(self) -> str:
        return f"{self.md5}-{self.count}--{self.size}"


@total_ordering
class ZarrChecksum(pydantic.BaseModel):
    """
    A checksum for a single file/directory in a zarr file.

    Every file and directory in a zarr archive has a name, digest, and size.
    Leaf nodes are created by providing an md5 digest.
    Internal nodes (directories) have a digest field that is a zarr directory digest

    This class is serialized to JSON, and as such, key order should not be modified.
    """

    digest: str
    name: str
    size: int

    # To make this class sortable
    def __lt__(self, other: ZarrChecksum):
        return self.name < other.name


class ZarrChecksumManifest(pydantic.BaseModel):
    """
    A set of file and directory checksums.

    This is the data hashed to calculate the checksum of a directory.
    """

    directories: List[ZarrChecksum] = pydantic.Field(default_factory=list)
    files: List[ZarrChecksum] = pydantic.Field(default_factory=list)

    @property
    def is_empty(self):
        return not (self.files or self.directories)

    def generate_digest(self) -> ZarrDirectoryDigest:
        """Generate an aggregated digest for the provided files/directories."""
        # Ensure sorted first
        self.files.sort()
        self.directories.sort()

        # Aggregate total file count
        count = len(self.files) + sum(
            ZarrDirectoryDigest.parse(checksum.digest).count for checksum in self.directories
        )

        # Aggregate total size
        size = sum(file.size for file in self.files) + sum(
            directory.size for directory in self.directories
        )

        # Seralize json without any spacing
        json = self.json(separators=(",", ":"))

        # Generate digest
        md5 = hashlib.md5(json.encode("utf-8")).hexdigest()

        # Construct and return
        return ZarrDirectoryDigest(md5=md5, count=count, size=size)


# The "null" zarr checksum
EMPTY_CHECKSUM = ZarrChecksumManifest().generate_digest().digest
