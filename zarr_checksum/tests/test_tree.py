from pathlib import Path

from zarr_checksum.checksum import EMPTY_CHECKSUM
from zarr_checksum.tree import ZarrChecksumTree


def test_pop_deepest():
    tree = ZarrChecksumTree()
    tree.add_leaf(Path("a/b"), size=1, digest="asd")
    tree.add_leaf(Path("a/b/c"), size=1, digest="asd")
    node = tree.pop_deepest()

    # Assert popped node is a/b/c, not a/b
    assert str(node.path) == "a/b"
    assert len(node.checksums.files) == 1
    assert len(node.checksums.directories) == 0
    assert node.checksums.files[0].name == "c"


def test_process_empty_tree():
    tree = ZarrChecksumTree()
    assert tree.process().digest == EMPTY_CHECKSUM


def test_process_tree():
    tree = ZarrChecksumTree()
    tree.add_leaf(Path("a/b"), size=1, digest="9dd4e461268c8034f5c8564e155c67a6")
    tree.add_leaf(Path("c"), size=1, digest="415290769594460e2e485922904f345d")
    checksum = tree.process()

    # This zarr checksum was computed against the same file structure using the previous
    # zarr checksum implementation
    # Assert the current implementation produces a matching checksum
    assert checksum.digest == "26054e501f570a8bfa69a2bc75e7c82d-2--2"
