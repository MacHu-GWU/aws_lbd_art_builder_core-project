# -*- coding: utf-8 -*-

"""
Lambda layer S3 upload implementation - Step 3 of the layer creation workflow.

This module handles the upload phase of AWS Lambda layer deployment, transferring
the packaged layer zip file to S3 storage where it can be accessed by AWS Lambda
for layer creation and publication.
"""

import typing as T
from pathlib import Path

from ..typehint import T_PRINTER
from ..constants import S3MetadataKeyEnum, LayerBuildToolEnum
from ..imports import S3Path

from .foundation import LayerManifestManager

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client


def upload_layer_zip_to_s3(
    s3_client: "S3Client",
    path_pyproject_toml: Path,
    s3dir_lambda: "S3Path",
    layer_build_tool: LayerBuildToolEnum,
    verbose: bool = True,
    printer: T_PRINTER = print,
):
    """
    Upload Lambda layer zip file to S3 storage for deployment (Public API).

    This function uploads the packaged layer zip file to S3 using an organized
    directory structure that supports versioning and artifact management. The
    uploaded artifact becomes available for Lambda layer creation and can be
    referenced by AWS Lambda service for layer publication.

    :param s3_client: Configured boto3 S3 client with appropriate permissions
    :param path_pyproject_toml: Path to pyproject.toml file (determines project root and zip location)
    :param s3dir_lambda: S3 directory path where Lambda artifacts are stored
    :param layer_build_tool: Build tool used to create dependencies (pip/poetry/uv)
    :param verbose: If True, shows detailed upload progress; if False, runs with minimal output
    :param printer: Function to handle progress messages, defaults to print
    """
    if verbose:
        printer(f"--- Uploading Lambda Layer zip to S3 ...")

    manifest_manager = LayerManifestManager(
        path_pyproject_toml=path_pyproject_toml,
        s3dir_lambda=s3dir_lambda,
        layer_build_tool=layer_build_tool,
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
            # Store manifest MD5 hash in S3 object metadata for consistency validation
            # This enables the publish step to verify that the uploaded layer.zip
            # corresponds to the current local dependency manifest before layer creation
            "Metadata": {
                S3MetadataKeyEnum.manifest_md5.value: manifest_manager.manifest_md5,
            },
        },
        bsm=s3_client,
    )
