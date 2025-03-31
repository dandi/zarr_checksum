from __future__ import annotations

from typing import TYPE_CHECKING

from zarr_checksum.tree import ZarrChecksumTree

if TYPE_CHECKING:
    from zarr_checksum.checksum import ZarrDirectoryDigest
    from zarr_checksum.generators import FileGenerator

__all__ = [
    "compute_zarr_checksum",
]


def compute_zarr_checksum(generator: FileGenerator) -> ZarrDirectoryDigest:
    tree = ZarrChecksumTree()
    for file in generator:
        tree.add_leaf(
            path=file.path,
            size=file.size,
            digest=file.digest,
        )

    # Compute digest
    return tree.process()
