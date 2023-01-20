from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
from typing import Iterable

import boto3
from botocore.client import Config
from tqdm import tqdm
from zarr.storage import NestedDirectoryStore


@dataclass
class ZarrArchiveFile:
    """
    A file path, size, and md5 checksum, ready to be added to a ZarrChecksumTree.

    This class differs from the `ZarrChecksum` class, for the following reasons:
    * Field order does not matter
    * This class is not serialized in any manner
    * The `path` field is relative to the root of the zarr archive, while the `name` field of
    `ZarrChecksum` is just the final component of said path
    """

    path: Path
    size: int
    digest: str


FileGenerator = Iterable[ZarrArchiveFile]


@dataclass
class S3ClientOptions:
    region_name: str = "us-east-1"
    api_version: str | None = None
    use_ssl: bool = True
    verify: bool | None = None
    endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    config: Config | None = None


def yield_files_s3(
    bucket: str, prefix: str = "", client_options: S3ClientOptions | None = None
) -> FileGenerator:
    if client_options is None:
        client_options = S3ClientOptions()

    # Construct client
    client = boto3.client("s3", **asdict(client_options))
    continuation_token = None
    options = {"Bucket": bucket, "Prefix": prefix}

    print("Retrieving files...")

    # Test that url is fully qualified path by appending slash to prefix and listing objects
    test_resp = client.list_objects_v2(Bucket=bucket, Prefix=os.path.join(prefix, ""))
    if "Contents" not in test_resp:
        print(f"Warning: No files found under prefix: {prefix}.")
        print("Please check that you have provided the fully qualified path to the zarr root.")
        yield from []
        return

    # Iterate until all files found
    while True:
        if continuation_token is not None:
            options["ContinuationToken"] = continuation_token

        # Fetch
        res = client.list_objects_v2(**options)

        # Fix keys of listing to be relative to zarr root
        mapped = (
            ZarrArchiveFile(
                path=Path(obj["Key"]).relative_to(prefix),
                size=obj["Size"],
                digest=obj["ETag"].strip('"'),
            )
            for obj in res.get("Contents", [])
        )

        # Yield as flat iteratble
        yield from mapped

        # If all files fetched, end
        continuation_token = res.get("NextContinuationToken", None)
        if continuation_token is None:
            break


def yield_files_local(directory: str | Path) -> FileGenerator:
    root_path = Path(os.path.expandvars(directory)).expanduser()
    if not root_path.exists():
        raise Exception("Path does not exist")

    print("Discovering files...")
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
        digest = md5sum.hexdigest()

        # Yield file
        yield ZarrArchiveFile(path=path, size=size, digest=digest)
