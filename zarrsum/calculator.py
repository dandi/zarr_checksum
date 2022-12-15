from __future__ import annotations

import hashlib
import os
from abc import ABC
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import boto3
from mypy_boto3_s3.type_defs import ObjectTypeDef
from tqdm import tqdm
from zarr.storage import NestedDirectoryStore

from zarrsum.tree import ZarrChecksumTree

__all__ = [
    "AWSCredentials",
    "ZarrChecksumCalculator",
    "S3ZarrChecksumCalculator",
    "LocalZarrChecksumCalculator",
]


class AWSCredentials(TypedDict):
    key: str
    secret: str
    region: str


class ZarrChecksumCalculator(ABC):
    def compute(self, *args, **kwargs) -> str:
        raise NotImplementedError()


class S3ZarrChecksumCalculator(ZarrChecksumCalculator):
    def _default_credentials(self) -> AWSCredentials:
        return {
            "key": None,
            "secret": None,
            "region": "us-east-1",
        }

    def __init__(self, credentials: AWSCredentials | None = None) -> None:
        self.credentials: AWSCredentials = credentials or self._default_credentials()

    def yield_files(self, bucket: str, prefix: str = "") -> list[ObjectTypeDef]:
        """Get all objects in the zarr."""
        client = boto3.client(
            "s3",
            region_name=self.credentials["region"],
            aws_access_key_id=self.credentials["key"],
            aws_secret_access_key=self.credentials["secret"],
        )

        continuation_token = None
        options = {"Bucket": bucket, "Prefix": prefix}

        # Test that url is fully qualified path by appending slash to prefix and listing objects
        test_resp = client.list_objects_v2(
            Bucket=bucket, Prefix=os.path.join(prefix, "")
        )
        if "Contents" not in test_resp:
            print(f"Warning: No files found under prefix: {prefix}.")
            print(
                "Please check that you have provided the fully qualified path to the zarr root."
            )
            return []

        # Iterate until all files found
        while True:
            if continuation_token is not None:
                options["ContinuationToken"] = continuation_token

            # Fetch
            res = client.list_objects_v2(**options)

            # Fix keys of listing to be relative to zarr root
            mapped = (
                {
                    **obj,
                    "Key": Path(obj["Key"]).relative_to(prefix),
                }
                for obj in res.get("Contents", [])
            )

            # Yield as flat iteratble
            yield from mapped

            # If all files fetched, end
            continuation_token = res.get("NextContinuationToken", None)
            if continuation_token is None:
                break

    def compute(self, s3_url: str) -> str:
        tree = ZarrChecksumTree()

        # Parse url
        parsed = urlparse(s3_url)
        bucket = parsed.netloc
        prefix = parsed.path.lstrip("/")
        if not (parsed.scheme == "s3" and bucket):
            raise Exception(f"Invalid S3 URL: {s3_url}")

        print("Retrieving files...")
        for file in self.yield_files(bucket=bucket, prefix=prefix):
            path = Path(file["Key"])
            tree.add_leaf(
                path=path,
                size=file["Size"],
                digest=file["ETag"].strip('"'),
            )

        # Compute digest
        return tree.process()


class LocalZarrChecksumCalculator(ZarrChecksumCalculator):
    def compute(self, directory: str | Path) -> str:
        root_path = Path(directory)
        if not root_path.exists():
            raise Exception("Path does not exist")

        print("Discovering files...")

        # Initialize tree, iterate over each file in local zarr
        tree = ZarrChecksumTree()
        store = NestedDirectoryStore(root_path)
        for file in tqdm(list(store.keys())):
            path = Path(file)
            absolute_path = root_path / path
            size = absolute_path.stat().st_size

            # Compute md5sum of file
            md5sum = hashlib.md5()
            with open(absolute_path, "rb") as f:
                while chunk := f.read(8192):
                    md5sum.update(chunk)

            # Add file to tree
            tree.add_leaf(
                path=path,
                size=size,
                digest=md5sum.hexdigest(),
            )

        # Compute digest
        return tree.process()
