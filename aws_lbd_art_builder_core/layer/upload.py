# -*- coding: utf-8 -*-

"""
Lambda layer S3 upload — Step 3 of the layer workflow.

Uploads the packaged ``layer.zip`` to a staging location in S3 where the
publish step can pick it up to create a Lambda layer version.

**Why store manifest_md5 in S3 metadata?**

The publish step needs to verify that the ``layer.zip`` sitting in S3 was
actually built from the *current* dependency manifest on disk. Without this
check, a stale zip from a previous build could be published by accident.
By embedding the manifest MD5 at upload time and comparing it at publish
time, we get a cheap consistency gate.
"""

import typing as T
from pathlib import Path

from ..typehint import T_PRINTER
from ..constants import S3MetadataKeyEnum
from ..imports import S3Path

from .foundation import LayerManifestManager

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


def upload_layer_zip_to_s3(
    s3_client: "S3Client",
    path_pyproject_toml: Path,
    s3dir_lambda: "S3Path",
    path_manifest: Path,
    verbose: bool = True,
    printer: T_PRINTER = print,
):
    """
    Upload Lambda layer zip file to S3 staging location.

    :param s3_client: Configured boto3 S3 client
    :param path_pyproject_toml: Path to pyproject.toml (determines project root and zip location)
    :param s3dir_lambda: S3 directory path where Lambda artifacts are stored
    :param path_manifest: Path to the dependency manifest file (e.g. requirements.txt, uv.lock)
    :param verbose: If True, shows detailed upload progress
    :param printer: Function to handle progress messages
    """
    if verbose:
        printer("--- Uploading Lambda Layer zip to S3 ...")

    manifest_manager = LayerManifestManager(
        path_pyproject_toml=path_pyproject_toml,
        s3dir_lambda=s3dir_lambda,
        path_manifest=path_manifest,
        s3_client=s3_client,
        printer=printer,
    )
    path_layer_zip = manifest_manager.path_layout.path_build_lambda_layer_zip
    s3path = manifest_manager.s3_layout.s3path_temp_layer_zip
    printer(f"upload from {path_layer_zip} to {s3path.uri}")
    printer(f"preview at {s3path.console_url}")
    s3path.upload_file(
        path=path_layer_zip,
        overwrite=True,
        extra_args={
            "ContentType": "application/zip",
            "Metadata": {
                S3MetadataKeyEnum.manifest_md5.value: manifest_manager.manifest_md5,
            },
        },
        bsm=s3_client,
    )
