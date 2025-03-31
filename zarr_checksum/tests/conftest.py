import collections
import os
from dataclasses import dataclass
from typing import Generator

import faker
import pytest
from minio import Minio
from minio.deleteobjects import DeleteObject


@dataclass
class MinioSettings:
    bucket_name: str
    endpoint: str
    access_key: str
    secret_key: str


@pytest.fixture
def minio_settings() -> MinioSettings:
    return MinioSettings(
        bucket_name=faker.Faker().first_name().lower(),
        endpoint=os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
    )


@pytest.fixture
def minio_client(minio_settings: MinioSettings) -> Generator[Minio, None, None]:
    minio = Minio(
        endpoint=os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=False,
    )

    def remove_bucket(_bucket: str) -> None:
        res = minio.remove_objects(
            _bucket,
            [
                DeleteObject(x.object_name)
                for x in minio.list_objects(_bucket, recursive=True)
                if x.object_name is not None
            ],
        )

        # Iterator must be consumed for the deletions to occur
        collections.deque(res, maxlen=0)

        minio.remove_bucket(_bucket)

    # Ensure bucket is empty
    bucket = minio_settings.bucket_name
    if minio.bucket_exists(bucket):
        remove_bucket(bucket)

    minio.make_bucket(bucket_name=bucket)

    yield minio

    remove_bucket(bucket)
