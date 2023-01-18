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

To calcuate the checksum for a remote (S3) zarr archive
```
zarrsum remote s3://your_bucket/prefix_to_zarr
```

## Python
To calculate the checksum for a local zarr archive
```python
from zarr_checksum import compute_zarr_checksum
from zarr_checksum.generators import yield_files_local

checksum = compute_zarr_checksum(yield_files_local("local_path"))
```

To calcuate the checksum for a remote (S3) zarr archive
```python
from zarr_checksum import compute_zarr_checksum
from zarr_checksum.generators import yield_files_s3

checksum = compute_zarr_checksum(yield_files_s3(bucket="your_bucket", prefix="prefix_to_zarr"))
```
