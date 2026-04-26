# -*- coding: utf-8 -*-

"""
Upload functions for Lambda source deployment artifacts.

Provides three functions that form the upload/publish half of the source
deployment lifecycle:

- :func:`upload_source_zip` — upload a pre-built source zip to S3
- :func:`build_and_upload_source_using_pip` — all-in-one: build dir (pip) → zip → upload
- :func:`build_and_upload_source_using_uv`  — all-in-one: build dir (uv)  → zip → upload

These functions depend on :mod:`.builder` (build step) and
:mod:`.foundation` (path/S3 layout conventions) but are kept in a separate
module so that callers can import only the upload logic without pulling in the
build tooling.
"""

import typing as T
import dataclasses
from pathlib import Path
from urllib.parse import urlencode

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # Python < 3.11

from func_args.api import OPT

from ..imports import S3Path
from ..constants import S3MetadataKeyEnum
from ..typehint import T_PRINTER

from .foundation import SourcePathLayout, SourceS3Layout
from .builder import build_source_dir_using_pip, build_source_dir_using_uv, create_source_zip

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3.client import S3Client


def upload_source_zip(
    s3_client: "S3Client",
    source_version: str,
    source_sha256: str,
    path_source_zip: Path,
    s3dir_source: "S3Path",
    metadata: dict[str, str] | None = OPT,
    tags: dict[str, str] | None = OPT,
    verbose: bool = True,
    printer: T_PRINTER = print,
) -> "S3Path":
    """
    Upload a pre-built Lambda source zip to S3 with versioning and metadata.

    :param s3_client: Boto3 S3 client for upload operations
    :param source_version: Semantic version for the source code, e.g., ``"0.1.1"``
    :param source_sha256: SHA256 hash of the source build directory for integrity verification
    :param path_source_zip: Local path to the source zip file to upload
    :param s3dir_source: S3 directory scoped to source artifacts,
        i.e. :attr:`~aws_lbd_art_builder_core.source.foundation.SourceS3Layout.dir_root`,
        e.g. ``s3://bucket/path/to/lambda/source/``
    :param metadata: Optional custom S3 object metadata to attach
    :param tags: Optional S3 object tags to attach
    :param verbose: If True, display upload progress and URLs; if False, run quietly
    :param printer: Function to handle output messages, defaults to built-in print

    :return: S3Path object pointing to the uploaded source.zip file
    """
    if verbose:  # pragma: no cover
        printer(f"--- Uploading Lambda source zip to S3 ...")
        printer(f"{source_version = }")
        printer(f"{source_sha256 = }")
        printer(f"{path_source_zip = !s}")
        printer(f"{s3dir_source.uri =}")

    source_s3_layout = SourceS3Layout(dir_root=s3dir_source)
    s3path_source_zip = source_s3_layout.get_s3path_source_zip(
        source_version=source_version,
        source_sha256=source_sha256,
    )
    if verbose:  # pragma: no cover
        printer(f"Uploading Lambda source zip to {s3path_source_zip.uri}")
        printer(f"preview at {s3path_source_zip.console_url}")

    extra_args = {"ContentType": "application/zip"}
    metadata_arg = {
        S3MetadataKeyEnum.source_version: source_version,
        S3MetadataKeyEnum.source_sha256: source_sha256,
    }
    if isinstance(metadata, dict):
        metadata_arg.update(metadata)
    extra_args["Metadata"] = metadata_arg

    if isinstance(tags, dict):
        extra_args["Tagging"] = urlencode(tags)

    s3path_source_zip.upload_file(
        path=path_source_zip,
        overwrite=True,
        extra_args=extra_args,
        bsm=s3_client,
    )
    return s3path_source_zip


@dataclasses.dataclass
class BuildAndUploadSourceResult:
    """
    Result of building and uploading Lambda source artifacts.
    """

    source_sha256: str
    s3path_source_zip: "S3Path" = dataclasses.field()


def build_and_upload_source_using_pip(
    s3_client: "S3Client",
    dir_project_root: Path,
    s3dir_source: "S3Path",
    skip_prompt: bool = False,
    verbose: bool = True,
    printer: T_PRINTER = print,
) -> BuildAndUploadSourceResult:
    """
    Build, zip, and upload Lambda source artifacts to S3 using pip.

    All-in-one convenience function. Uses the project's venv pip
    (``{dir_project_root}/.venv/bin/pip``) and reads the version from
    ``pyproject.toml`` automatically.

    :param s3_client: Boto3 S3 client for upload operations
    :param dir_project_root: Root directory of the Python project (contains pyproject.toml)
    :param s3dir_source: S3 directory scoped to source artifacts,
        i.e. :attr:`~aws_lbd_art_builder_core.source.foundation.SourceS3Layout.dir_root`,
        e.g. ``s3://bucket/path/to/lambda/source/``
    :param skip_prompt: If True, clean the build directory without user confirmation
    :param verbose: If True, display detailed progress information
    :param printer: Function to handle output messages, defaults to built-in print

    :return: :class:`BuildAndUploadSourceResult`

    .. seealso::

        - :func:`~aws_lbd_art_builder_core.source.builder.build_source_dir_using_pip`
        - :func:`~aws_lbd_art_builder_core.source.builder.create_source_zip`
        - :func:`upload_source_zip`
    """
    path_bin_pip = dir_project_root / ".venv" / "bin" / "pip"
    path_pyproject_toml = dir_project_root / "pyproject.toml"
    path_layout = SourcePathLayout(
        dir_root=dir_project_root / "build" / "lambda" / "source"
    )

    build_source_dir_using_pip(
        path_bin_pip=path_bin_pip,
        path_pyproject_toml=path_pyproject_toml,
        dir_lambda_source_build=path_layout.dir_build,
        skip_prompt=skip_prompt,
        verbose=verbose,
        printer=printer,
    )
    source_sha256 = create_source_zip(
        dir_lambda_source_build=path_layout.dir_build,
        path_source_zip=path_layout.path_source_zip,
        verbose=verbose,
        printer=printer,
    )
    source_version = tomllib.loads(path_pyproject_toml.read_text())["project"]["version"]
    s3path_source_zip = upload_source_zip(
        s3_client=s3_client,
        source_version=source_version,
        source_sha256=source_sha256,
        path_source_zip=path_layout.path_source_zip,
        s3dir_source=s3dir_source,
        verbose=verbose,
        printer=printer,
    )
    return BuildAndUploadSourceResult(
        source_sha256=source_sha256,
        s3path_source_zip=s3path_source_zip,
    )


def build_and_upload_source_using_uv(
    s3_client: "S3Client",
    path_bin_uv: Path,
    dir_project_root: Path,
    s3dir_source: "S3Path",
    skip_prompt: bool = False,
    verbose: bool = True,
    printer: T_PRINTER = print,
) -> BuildAndUploadSourceResult:
    """
    Build, zip, and upload Lambda source artifacts to S3 using uv.

    All-in-one convenience function. Reads the version from ``pyproject.toml``
    automatically.

    :param s3_client: Boto3 S3 client for upload operations
    :param path_bin_uv: uv executable, e.g. ``Path(shutil.which("uv"))``
    :param dir_project_root: Root directory of the Python project (contains pyproject.toml)
    :param s3dir_source: S3 directory scoped to source artifacts,
        i.e. :attr:`~aws_lbd_art_builder_core.source.foundation.SourceS3Layout.dir_root`,
        e.g. ``s3://bucket/path/to/lambda/source/``
    :param skip_prompt: If True, clean the build directory without user confirmation
    :param verbose: If True, display detailed progress information
    :param printer: Function to handle output messages, defaults to built-in print

    :return: :class:`BuildAndUploadSourceResult`

    .. seealso::

        - :func:`~aws_lbd_art_builder_core.source.builder.build_source_dir_using_uv`
        - :func:`~aws_lbd_art_builder_core.source.builder.create_source_zip`
        - :func:`upload_source_zip`
    """
    path_pyproject_toml = dir_project_root / "pyproject.toml"
    path_layout = SourcePathLayout(
        dir_root=dir_project_root / "build" / "lambda" / "source"
    )

    build_source_dir_using_uv(
        path_bin_uv=path_bin_uv,
        path_pyproject_toml=path_pyproject_toml,
        dir_lambda_source_build=path_layout.dir_build,
        skip_prompt=skip_prompt,
        verbose=verbose,
        printer=printer,
    )
    source_sha256 = create_source_zip(
        dir_lambda_source_build=path_layout.dir_build,
        path_source_zip=path_layout.path_source_zip,
        verbose=verbose,
        printer=printer,
    )
    source_version = tomllib.loads(path_pyproject_toml.read_text())["project"]["version"]
    s3path_source_zip = upload_source_zip(
        s3_client=s3_client,
        source_version=source_version,
        source_sha256=source_sha256,
        path_source_zip=path_layout.path_source_zip,
        s3dir_source=s3dir_source,
        verbose=verbose,
        printer=printer,
    )
    return BuildAndUploadSourceResult(
        source_sha256=source_sha256,
        s3path_source_zip=s3path_source_zip,
    )
