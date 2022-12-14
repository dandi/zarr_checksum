"""Zarr checksumming code."""

from __future__ import annotations

import hashlib
import heapq
import os
import sys
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

import boto3
from dandischema.digests.zarr import (
    EMPTY_CHECKSUM,
    ZarrChecksum,
    ZarrJSONChecksumSerializer,
)
from mypy_boto3_s3.type_defs import ObjectTypeDef
from zarr.storage import NestedDirectoryStore


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
            print(f"Processing {modification.path}")

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


class ZarrChecksumCalculator(ABC):
    def compute(self, *args, **kwargs) -> str:
        raise NotImplementedError()


def compute_local(directory: str | Path):
    root_path = Path(directory)
    if not root_path.exists():
        raise Exception("Path does not exist")

    queue = ZarrChecksumModificationQueue()
    store = NestedDirectoryStore(root_path)
    for file in store.keys():
        path = root_path / file

        # TODO: Remove print
        print(f"Queueing {path.relative_to(root_path)}...")
        with open(path, "rb") as f:
            file_hash = hashlib.md5()
            while chunk := f.read(8192):
                file_hash.update(chunk)

        # Add file to queue
        md5sum = file_hash.hexdigest()
        queue.queue_file_update(
            key=path.parent.relative_to(root_path),
            checksum=ZarrChecksum(
                name=path.name,
                size=path.stat().st_size,
                digest=md5sum,
            ),
        )

    # Process queue
    return queue.process()


class AWSCredentials(TypedDict):
    key: str
    secret: str


def yield_files(zarr_id: str, credentials: AWSCredentials) -> list[ObjectTypeDef]:
    """Get all objects in the zarr."""
    client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id=credentials["key"],
        aws_secret_access_key=credentials["secret"],
    )

    zarr_root = Path(f"zarr/{zarr_id}")
    common_options = {"Bucket": "dandiarchive", "Prefix": str(zarr_root)}

    continuation_token = None
    while True:
        options = {**common_options}
        if continuation_token is not None:
            options["ContinuationToken"] = continuation_token

        # Fetch
        res = client.list_objects_v2(**options)

        # Yield this batch of files
        # yield from res.get("Contents", [])
        yield from [
            {
                **obj,
                "Key": Path(obj["Key"]).relative_to(zarr_root),
            }
            for obj in res.get("Contents", [])
        ]

        # If all files fetched, end
        if res["IsTruncated"] is False:
            break

        # Get next continuation token
        continuation_token = res["NextContinuationToken"]


def compute_remote(zarr_id: str, credentials: AWSCredentials) -> str:
    queue = ZarrChecksumModificationQueue()
    for file in yield_files(zarr_id, credentials):
        path = Path(file["Key"])
        queue.queue_file_update(
            key=path.parent,
            checksum=ZarrChecksum(
                name=path.name,
                size=file["Size"],
                digest=file["ETag"].strip('"'),
            ),
        )

    return queue.process()


if __name__ == "__main__":
    directory = os.getcwd()
    if len(sys.argv) > 1:
        directory = sys.argv[1]

    # compute_local(path)
    # compute_remote(
    #     sys.argv[1],
    #     credentials={
    #         "key": os.getenv("AWS_ACCESS_KEY_ID", None),
    #         "secret": os.getenv("AWS_SECRET_ACCESS_KEY", None),
    #     },
    # )
