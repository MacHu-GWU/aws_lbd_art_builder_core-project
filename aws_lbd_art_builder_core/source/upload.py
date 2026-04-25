# -*- coding: utf-8 -*-

"""
Upload functions for Lambda source deployment artifacts.

Provides two functions that form the upload/publish half of the source
deployment lifecycle:

- :func:`upload_source_artifacts` — upload a pre-built source zip to S3
- :func:`build_package_upload_source_artifacts` — all-in-one: build → zip → upload

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

from .foundation import SourcePathLayout
from .foundation import SourceS3Layout
from .builder import build_source_artifacts_using_pip
from .builder import build_source_artifacts_using_uv
from .builder import create_source_zip


if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3.client import S3Client


def upload_source_artifacts(
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
    Upload Lambda source artifact zip file to S3 with versioning and metadata.

    This function uploads the built source zip to S3 following the structured layout,
    automatically adding SHA256 hash metadata for integrity verification and
    supporting custom metadata and tags.

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
    if verbose:
        printer(f"--- Uploading Lambda source artifacts to S3 ...")
        printer(f"{source_version = }")
        printer(f"{source_sha256 = }")
        printer(f"{path_source_zip = !s}")
        printer(f"{s3dir_source.uri =}")

    # Initialize S3 layout manager and get target path
    source_s3_layout = SourceS3Layout(dir_root=s3dir_source)
    s3path_source_zip = source_s3_layout.get_s3path_source_zip(
        source_version=source_version,
        source_sha256=source_sha256,
    )
    if verbose:
        uri = s3path_source_zip.uri
        printer(f"Uploading Lambda source artifact to {uri}")
        url = s3path_source_zip.console_url
        printer(f"preview at {url}")

    # Configure S3 upload parameters
    extra_args = {"ContentType": "application/zip"}

    # Add SHA256 hash to metadata for integrity verification
    metadata_arg = {
        S3MetadataKeyEnum.source_version: source_version,
        S3MetadataKeyEnum.source_sha256: source_sha256,
    }
    # Merge with any custom metadata provided
    if isinstance(metadata, dict):
        metadata_arg.update(metadata)
    extra_args["Metadata"] = metadata_arg

    # Add tags if provided
    if isinstance(tags, dict):
        extra_args["Tagging"] = urlencode(tags)
    # Upload zip file to S3 with metadata and tags
    s3path_source_zip.upload_file(
        path=path_source_zip,
        overwrite=True,  # Allow overwriting existing versions
        extra_args=extra_args,
        bsm=s3_client,
    )
    return s3path_source_zip


@dataclasses.dataclass
class BuildSourceArtifactsResult:
    """
    Result of building and uploading Lambda source artifacts.
    """

    source_sha256: str
    s3path_source_zip: "S3Path" = dataclasses.field()


def build_package_upload_source_artifacts(
    s3_client: "S3Client",
    dir_project_root: Path,
    s3dir_source: "S3Path",
    skip_prompt: bool = False,
    verbose: bool = True,
    printer: T_PRINTER = print,
) -> BuildSourceArtifactsResult:
    """
    Build, package, and upload Lambda source artifacts to S3.

    This is a all-in-one function that handles the complete lifecycle of Lambda source.

    :param s3_client: Boto3 S3 client for upload operations
    :param dir_project_root: Root directory of the Python project containing setup.py or pyproject.toml
    :param s3dir_source: S3 directory scoped to source artifacts,
        i.e. :attr:`~aws_lbd_art_builder_core.source.foundation.SourceS3Layout.dir_root`,
        e.g. ``s3://bucket/path/to/lambda/source/``
    :param skip_prompt: If True, automatically clean existing build directory without user confirmation
    :param verbose: If True, display detailed progress information; if False, run quietly
    :param printer: Function to handle output messages, defaults to built-in print

    :return: :class:`BuildSourceArtifactsResult` containing SHA256 hash and S3 path of the uploaded source.zip

    .. seealso::

        - :func:`~aws_lbd_art_builder_core.source.builder.build_source_artifacts_using_pip`
        - :func:`~aws_lbd_art_builder_core.source.builder.create_source_zip`
        - :func:`upload_source_artifacts`
    """
    # step 1: build source artifacts using pip
    path_bin_pip = dir_project_root / ".venv" / "bin" / "pip"
    path_pyproject_toml = dir_project_root / "pyproject.toml"
    path_layout = SourcePathLayout(
        dir_root=dir_project_root / "build" / "lambda" / "source"
    )
    build_source_artifacts_using_pip(
        path_bin_pip=path_bin_pip,
        path_setup_py_or_pyproject_toml=path_pyproject_toml,
        dir_lambda_source_build=path_layout.dir_build,
        skip_prompt=skip_prompt,
        verbose=verbose,
        printer=printer,
    )

    # step 2: create compressed zip archive of the built source
    source_sha256 = create_source_zip(
        dir_lambda_source_build=path_layout.dir_build,
        path_source_zip=path_layout.path_source_zip,
        verbose=verbose,
        printer=printer,
    )

    # step 3: upload the zip file to S3 with versioning
    pyproject_toml_data = tomllib.loads(path_pyproject_toml.read_text())
    source_version = pyproject_toml_data["project"]["version"]
    s3path_source_zip = upload_source_artifacts(
        s3_client=s3_client,
        source_version=source_version,
        source_sha256=source_sha256,
        path_source_zip=path_layout.path_source_zip,
        s3dir_source=s3dir_source,
        verbose=verbose,
        printer=printer,
    )

    return BuildSourceArtifactsResult(
        source_sha256=source_sha256,
        s3path_source_zip=s3path_source_zip,
    )
