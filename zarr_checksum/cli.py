import pathlib

import click

from zarr_checksum.calculator import (
    LocalZarrChecksumCalculator,
    S3ZarrChecksumCalculator,
)


@click.group()
def cli():
    pass


@cli.command()
@click.argument(
    "directory",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, path_type=pathlib.Path
    ),
)
def local(directory: pathlib.Path):
    directory = directory.absolute().resolve()
    checksum = LocalZarrChecksumCalculator().compute(directory)
    click.echo(click.style(text=f"Checksum for {directory} complete:", fg="green"))
    click.echo(f"\n{checksum}")


@cli.command()
@click.argument("url")
def remote(url: str):
    checksum = S3ZarrChecksumCalculator().compute(s3_url=url)
    click.echo(click.style(text=f"Checksum for {url} complete:", fg="green"))
    click.echo(f"\n{checksum}")
