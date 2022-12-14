"""Zarr checksumming code."""

from __future__ import annotations

import hashlib
import os
import sys
from abc import ABC
from pathlib import Path
from typing import TypedDict

import boto3
from dandischema.digests.zarr import ZarrChecksum
from mypy_boto3_s3.type_defs import ObjectTypeDef
from zarr.storage import NestedDirectoryStore

from zarr_checksum.modification import ZarrChecksumModificationQueue


class AWSCredentials(TypedDict):
    key: str
    secret: str


class ZarrChecksumCalculator(ABC):
    def compute(self, *args, **kwargs) -> str:
        raise NotImplementedError()


class S3ZarrChecksumCalculator(ZarrChecksumCalculator):
    def _default_credentials(self) -> AWSCredentials:
        return {
            "key": None,
            "secret": None,
        }

    def __init__(self, credentials: AWSCredentials | None = None) -> None:
        self.credentials: AWSCredentials = credentials or self._default_credentials()

    def yield_files(self, zarr_id: str) -> list[ObjectTypeDef]:
        """Get all objects in the zarr."""
        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id=self.credentials["key"],
            aws_secret_access_key=self.credentials["secret"],
        )

        # Set up zarr root path, to use as prefix and path
        zarr_root = Path("zarr") / zarr_id

        continuation_token = None
        options = {"Bucket": "dandiarchive", "Prefix": str(zarr_root)}
        while True:
            if continuation_token is not None:
                options["ContinuationToken"] = continuation_token

            # Fetch
            res = client.list_objects_v2(**options)

            # Fix keys of listing to be relative to zarr root
            mapped = (
                {
                    **obj,
                    "Key": Path(obj["Key"]).relative_to(zarr_root),
                }
                for obj in res.get("Contents", [])
            )

            # Yield as flat iteratble
            yield from mapped

            # If all files fetched, end
            continuation_token = res.get("NextContinuationToken", None)
            if continuation_token is None:
                break

    def compute(self, zarr_id: str) -> str:
        queue = ZarrChecksumModificationQueue()
        for file in self.yield_files(zarr_id=zarr_id):
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


class LocalZarrChecksumCalculator(ZarrChecksumCalculator):
    def compute(self, directory: str | Path) -> str:
        root_path = Path(directory)
        if not root_path.exists():
            raise Exception("Path does not exist")

        # Initialize queue, iterate over each file in local zarr
        queue = ZarrChecksumModificationQueue()
        store = NestedDirectoryStore(root_path)
        for file in store.keys():
            # Construct full path, relative to root
            path = root_path / file

            # Compute md5sum of file
            md5sum = hashlib.md5()
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    md5sum.update(chunk)

            # Add file to queue
            queue.queue_file_update(
                key=path.parent.relative_to(root_path),
                checksum=ZarrChecksum(
                    name=path.name,
                    size=path.stat().st_size,
                    digest=md5sum.hexdigest(),
                ),
            )

        # Process queue
        return queue.process()


if __name__ == "__main__":
    directory = os.getcwd()
    if len(sys.argv) > 1:
        directory = sys.argv[1]

    # LocalZarrChecksumCalculator().compute(directory)
    S3ZarrChecksumCalculator().compute(directory)
    # compute_remote(
    #     sys.argv[1],
    #     credentials={
    #         "key": os.getenv("AWS_ACCESS_KEY_ID", None),
    #         "secret": os.getenv("AWS_SECRET_ACCESS_KEY", None),
    #     },
    # )
