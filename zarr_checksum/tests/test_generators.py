import io
import os
import tempfile
from pathlib import Path

import faker
from minio import Minio

from zarr_checksum.generators import (
    S3ClientOptions,
    ZarrArchiveFile,
    yield_files_local,
    yield_files_s3,
)
from zarr_checksum.tests.conftest import MinioSettings


def test_yield_files_s3(minio_client: Minio, minio_settings: MinioSettings) -> None:
    fake = faker.Faker()
    # TODO: Replace with removeprefix once python 3.9+ becomes the minimum version
    files = [fake.file_path().lstrip("/") for _ in range(10)]
    for f in files:
        data = os.urandom(100)
        minio_client.put_object(
            bucket_name=minio_settings.bucket_name,
            object_name=f,
            data=io.BytesIO(data),
            length=len(data),
        )

    s3_files = yield_files_s3(
        bucket=minio_settings.bucket_name,
        client_options=S3ClientOptions(
            endpoint_url=f"http://{minio_settings.endpoint}",
            aws_access_key_id=minio_settings.access_key,
            aws_secret_access_key=minio_settings.secret_key,
            use_ssl=False,
        ),
    )

    s3_file_paths = [str(file.path) for file in s3_files]
    assert len(s3_file_paths) == len(files)
    assert set(s3_file_paths) == set(files)


def test_yield_files_local(tmp_path: Path) -> None:
    # Create file tree like so
    #           . (root)
    #          / \
    #         a  c
    #        /
    #       b
    c = tempfile.mkstemp(dir=tmp_path)[1]

    a = tempfile.mkdtemp(dir=tmp_path)
    b = tempfile.mkstemp(dir=a)[1]

    # Test files yielded
    files = list(yield_files_local(tmp_path))
    assert (
        ZarrArchiveFile(
            path=Path(c).relative_to(tmp_path),
            size=0,
            digest="d41d8cd98f00b204e9800998ecf8427e",
        )
        in files
    )
    assert (
        ZarrArchiveFile(
            path=Path(b).relative_to(tmp_path),
            size=0,
            digest="d41d8cd98f00b204e9800998ecf8427e",
        )
        in files
    )


def test_yield_files_local_no_empty_dirs(tmp_path: Path) -> None:
    """Ensure no empty directories are yielded."""
    # Create a nested file
    filename = tempfile.mkstemp(dir=tempfile.mkdtemp(dir=tmp_path))[1]

    # Create a bunch of empty directories
    tempfile.mkdtemp(dir=tmp_path)
    tempfile.mkdtemp(dir=tmp_path)

    # Create a nest of empty directories
    tempfile.mkdtemp(dir=tempfile.mkdtemp(dir=tempfile.mkdtemp(dir=tmp_path)))

    files = list(yield_files_local(tmp_path))
    assert len(files) == 1
    assert files[0].path == Path(filename).relative_to(tmp_path)
