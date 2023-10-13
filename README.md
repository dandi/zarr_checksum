# zarr_checksum
Algorithms for calculating a zarr checksum against local or cloud storage

# Install
```
pip install zarr-checksum
```

# Usage

## CLI
To calculate the checksum for a local zarr archive
```
zarrsum local <directory>
```

To calculate the checksum for a remote (S3) zarr archive
```
zarrsum remote s3://your_bucket/prefix_to_zarr
```

## Python
To calculate the checksum for a local zarr archive
```python
from zarr_checksum import compute_zarr_checksum
from zarr_checksum.generators import yield_files_local, yield_files_s3

# Local
checksum = compute_zarr_checksum(yield_files_local("local_path"))

# Remote
checksum = compute_zarr_checksum(
    yield_files_s3(
        bucket="your_bucket",
        prefix="prefix_to_zarr",
        # Credentials can also be passed via environment variables
        credentials={
            aws_access_key_id: "youraccesskey",
            aws_secret_access_key: "yoursecretkey",
            region_name: "us-east-1",
        }
    )
)
```

Access checksum information
```python
>>> checksum.digest
'c228464f432c4376f0de6ddaea32650c-37481--38757151179'
>>> checksum.md5
'c228464f432c4376f0de6ddaea32650c'
>>> checksum.count
37481
>>> checksum.size
38757151179
```
