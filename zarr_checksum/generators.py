from __future__ import annotations

import hashlib
import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from botocore.client import Config

import concurrent.futures

from tqdm import tqdm

logger = logging.getLogger(__name__)


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
    import boto3

    if client_options is None:
        client_options = S3ClientOptions()

    # Construct client
    client = boto3.client("s3", **asdict(client_options))

    logger.info("Retrieving files...")

    # Test that url is fully qualified path by appending slash to prefix and listing objects
    test_resp = client.list_objects_v2(Bucket=bucket, Prefix=os.path.join(prefix, ""))
    if "Contents" not in test_resp:
        logger.warning("No files found under prefix: %s.", prefix)
        logger.warning(
            "Please check that you have provided the fully qualified path to the zarr root."
        )
        yield from []
        return

    # Fetch
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        # Fix keys of listing to be relative to zarr root
        mapped = (
            ZarrArchiveFile(
                path=Path(obj["Key"]).relative_to(prefix),
                size=obj["Size"],
                digest=obj["ETag"].strip('"'),
            )
            for obj in page.get("Contents", [])
        )

        # Yield as flat iterable
        yield from mapped


def compute_local_zarr_archive_file(path: Path):
    """
    Return the `ZarrArchiveFile` from a given file path.

    The `path` argument should be relative to the root of the zarr archive.
    """
    if not path.is_file():
        raise Exception("ZarrArchiveFile must be computed from regular file.")  # noqa: TRY002

    # Compute md5sum of file
    md5sum = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5sum.update(chunk)
    digest = md5sum.hexdigest()

    size = path.stat().st_size
    # print("------", path)
    return ZarrArchiveFile(path=path, size=size, digest=digest)


def yield_files_local(directory: str | Path, max_workers: int | None = None) -> FileGenerator:
    root_path = Path(os.path.expandvars(directory)).expanduser()
    if not root_path.exists():
        raise Exception("Path does not exist")  # noqa: TRY002

    logger.info("Discovering files...")
    with ThreadPoolExecutor(max_workers=max_workers) as exc:
        futures: set[Future[ZarrArchiveFile]] = set()
        for parent, _, fnames in os.walk(root_path):
            parent_path = Path(parent)
            for fname in fnames:
                file = parent_path.relative_to(root_path) / fname
                absolute_path = root_path / file
                futures.add(exc.submit(compute_local_zarr_archive_file, path=absolute_path))

        while futures:
            done, futures = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )

            for future in done:
                # print("++++++++++++++++++++++++++++++++++++=+", future.result().path)
                yield future.result()


def yield_files_local_sync(directory: str | Path) -> FileGenerator:
    root_path = Path(os.path.expandvars(directory)).expanduser()
    if not root_path.exists():
        raise Exception("Path does not exist")  # noqa: TRY002

    logger.info("Discovering files...")
    files: list[str] = []
    for parent, _, fnames in os.walk(root_path):
        parent_path = Path(parent)
        files.extend(str(parent_path.relative_to(root_path) / fname) for fname in fnames)

    for file in tqdm(files):
        path = Path(file)
        absolute_path = root_path / path
        yield compute_local_zarr_archive_file(path=absolute_path)
