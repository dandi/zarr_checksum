import pathlib
from urllib.parse import urlparse

import click

from zarr_checksum import compute_zarr_checksum
from zarr_checksum.generators import yield_files_local, yield_files_s3


@click.group()
def cli():
    pass


@cli.command()
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=pathlib.Path),
)
def local(directory: pathlib.Path):
    checksum = compute_zarr_checksum(yield_files_local(directory))
    click.echo(click.style(text=f"Checksum for {directory} complete:", fg="green"))
    click.echo(f"\n{checksum}")


@cli.command()
@click.argument("url")
def remote(url: str):
    # Parse url
    parsed = urlparse(url)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    if not (parsed.scheme == "s3" and bucket):
        raise click.ClickException(f"Invalid S3 URL: {url}")

    checksum = compute_zarr_checksum(yield_files_s3(bucket=bucket, prefix=prefix))
    click.echo(click.style(text=f"Checksum for {url} complete:", fg="green"))
    click.echo(f"\n{checksum}")
