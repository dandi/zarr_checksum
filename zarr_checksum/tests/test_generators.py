from pathlib import Path
import tempfile

from zarr_checksum.generators import ZarrArchiveFile, yield_files_local


def test_yield_files_local(tmp_path):
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


def test_yield_files_local_no_empty_dirs(tmp_path):
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


# TODO: Add tests for yield_files_s3
