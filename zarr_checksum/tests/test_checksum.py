import pytest

from zarr_checksum.checksum import (
    InvalidZarrChecksum,
    ZarrChecksum,
    ZarrChecksumManifest,
    ZarrDirectoryDigest,
)


def test_generate_digest():
    manifest = ZarrChecksumManifest(
        directories=[
            ZarrChecksum(digest="a7e86136543b019d72468ceebf71fb8e-1--1", name="a/b", size=1)
        ],
        files=[ZarrChecksum(digest="92eb5ffee6ae2fec3ad71c777531578f-1--1", name="b", size=1)],
    )
    assert manifest.generate_digest().digest == "2ed39fd5ae56fd4177c4eb503d163528-2--2"


def test_zarr_checksum_sort_order():
    # The a < b in the name should take precedence over z > y in the md5
    a = ZarrChecksum(name="a", digest="z", size=3)
    b = ZarrChecksum(name="b", digest="y", size=4)
    assert sorted([b, a]) == [a, b]


def test_parse_zarr_directory_digest():
    # Parse valid
    ZarrDirectoryDigest.parse("c228464f432c4376f0de6ddaea32650c-37481--38757151179")
    ZarrDirectoryDigest.parse(None)

    # Ensure exception is raised
    with pytest.raises(InvalidZarrChecksum):
        ZarrDirectoryDigest.parse("asd")
    with pytest.raises(InvalidZarrChecksum):
        ZarrDirectoryDigest.parse("asd-0--0")
