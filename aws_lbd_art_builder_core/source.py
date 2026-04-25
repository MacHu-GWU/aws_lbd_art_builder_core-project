# -*- coding: utf-8 -*-

"""
This module provides utilities for building, packaging, and uploading AWS Lambda source artifacts.

It handles the complete lifecycle of Lambda source deployment packages:

1. Building source artifacts using pip from setup.py or pyproject.toml
2. Creating compressed zip archives of the built source
3. Uploading artifacts to S3 with proper versioning and metadata

Key Assumptions:

1. **Pip-based packaging**: Uses `pip install` to build source artifacts, ensuring proper
   Python package installation and module discovery within the Lambda runtime environment.
2. **Code folder structure**: Assumes the Lambda entry point (lambda_function.py) is included
   within the installed package structure, not as a separate external file.

S3 Storage Structure::

    s3://bucket/${s3dir_lambda}/source/0.1.1/source.zip
    s3://bucket/${s3dir_lambda}/source/0.1.2/source.zip
    s3://bucket/${s3dir_lambda}/source/0.1.3/source.zip

The pattern in this module is inspired by this
`blog post <https://sanhehu.atlassian.net/wiki/spaces/LEARNAWS/pages/556793859/AWS+Lambda+Python+Package+Deployment+Ultimate+Guide>`_
"""

import typing as T
import glob
import subprocess
import dataclasses
from pathlib import Path
from urllib.parse import urlencode

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # Python < 3.11

from func_args.api import BaseFrozenModel, REQ, OPT
from .imports import S3Path

from .vendor.better_pathlib import temp_cwd
from .vendor.hashes import hashes

from .constants import S3MetadataKeyEnum
from .typehint import T_PRINTER
from .utils import clean_build_directory

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3.client import S3Client


@dataclasses.dataclass
class SourcePathLayout:
    pass


def build_source_artifacts_using_pip(
    path_bin_pip: Path,
    path_setup_py_or_pyproject_toml: Path,
    dir_lambda_source_build: Path,
    skip_prompt: bool = False,
    verbose: bool = True,
    printer: T_PRINTER = print,
):
    """
    Build Lambda source artifacts by installing the current package using pip.

    **Why pip install?** Using pip ensures proper Python package installation with correct
    module paths, entry points, and metadata that Lambda runtime expects. This approach
    guarantees that all package modules are discoverable and importable within the Lambda
    execution environment, unlike simple file copying which may break import resolution.

    This function installs the Python package (defined by setup.py or pyproject.toml)
    into a target directory without dependencies, suitable for Lambda deployment.
    The build directory is cleaned before installation to ensure a fresh build.

    :param path_bin_pip: Path to pip executable, e.g., ``/path/to/.venv/bin/pip``
    :param path_setup_py_or_pyproject_toml: Path to package definition file, e.g., ``/path/to/setup.py`` or ``/path/to/pyproject.toml``
    :param dir_lambda_source_build: Target directory for built artifacts, e.g., ``/path/to/build/lambda/source/build``
    :param verbose: If True, display detailed build output; if False, suppress pip output
    :param skip_prompt: If True, automatically clean existing build directory without user confirmation
    :param printer: Function to handle output messages, defaults to built-in print
    """
    if verbose:
        printer(f"--- Building Lambda source artifacts using pip ...")
        printer(f"{path_bin_pip = !s}")
        printer(f"{path_setup_py_or_pyproject_toml = !s}")
        printer(f"{dir_lambda_source_build = !s}")

    # Clean existing build directory to ensure fresh installation
    clean_build_directory(
        dir_build=dir_lambda_source_build,
        folder_alias="lambda source build folder",
        skip_prompt=skip_prompt,
    )
    # Change to package directory for pip install
    dir_workspace = path_setup_py_or_pyproject_toml.parent
    with temp_cwd(dir_workspace):
        # Build pip install command with target directory
        args = [
            f"{path_bin_pip}",
            "install",
            f"{dir_workspace}",  # Install current package
            "--no-dependencies",  # Skip dependencies for Lambda layer separation
            f"--target={dir_lambda_source_build}",  # Install to build directory
        ]
        # Suppress pip output in quiet mode
        if verbose is False:
            args.append("--disable-pip-version-check")
            args.append("--quiet")
        subprocess.run(args, check=True)


def create_source_zip(
    dir_lambda_source_build: Path,
    path_source_zip: Path,
    verbose: bool = True,
    printer: T_PRINTER = print,
) -> str:
    """
    Create a compressed zip archive from the Lambda source build directory.

    **Important assumption**: This function expects that the Lambda entry point
    (typically `lambda_function.py` with a `lambda_handler` function) is included
    within the installed package structure in the build directory, not as a separate
    external file. The entry point should be part of your Python package as defined
    in setup.py or pyproject.toml.

    This function creates a zip file containing all files from the build directory
    using maximum compression (level 9) and calculates the SHA256 hash of the
    source directory for integrity verification.

    :param dir_lambda_source_build: Directory containing built Lambda source files
    :param path_source_zip: Output path for the created zip file
    :param verbose: If True, display progress information; if False, run quietly
    :param printer: Function to handle output messages, defaults to built-in print
    :return: SHA256 hash of the source build directory
    """
    if verbose:
        printer(f"--- Creating Lambda source zip file ...")
        printer(f"{dir_lambda_source_build = !s}")
        printer(f"{path_source_zip = !s}")

    # Prepare zip command with maximum compression
    args = [
        "zip",
        f"{path_source_zip}",
        "-r",  # Recursive
        "-9",  # Maximum compression
    ]
    # Suppress zip output in quiet mode
    if verbose is False:
        args.append("-q")

    # Change to build directory to include all files in zip root
    with temp_cwd(dir_lambda_source_build):
        args.extend(glob.glob("*"))  # Add all files/directories to zip
        subprocess.run(args, check=True)

    # Calculate SHA256 hash of the source directory for integrity verification
    source_sha256 = hashes.of_paths([dir_lambda_source_build])
    if verbose:
        printer(f"{source_sha256 = }")
    return source_sha256


@dataclasses.dataclass
class SourceS3Layout:
    """
    S3 directory layout manager for Lambda source artifacts.

    This class provides a structured approach to organizing Lambda source artifacts
    in S3 with semantic versioning. Each version gets its own directory containing
    the source.zip file.

    :param s3dir_lambda: Base S3 directory for Lambda artifacts, e.g., ``s3://bucket/path/to/lambda/``

    Generated Layout, see :meth:`get_s3path_source_zip` ::

        ${s3dir_lambda}/source/0.1.1/{source_sha256}/source.zip
        ${s3dir_lambda}/source/0.1.2/{source_sha256}/source.zip
        ${s3dir_lambda}/source/0.1.3/{source_sha256}/source.zip
        ...
    """

    s3dir_lambda: "S3Path" = dataclasses.field()

    def get_s3path_source_zip(
        self,
        source_version: str,
        source_sha256: str,
    ) -> "S3Path":
        """
        Generate S3 path for a specific version of the Lambda source zip.

        :param source_version: Semantic version string, e.g., ``"0.1.1"``
        :param source_sha256: SHA256 hash of the source build directory (not used in path generation)

        :return: S3Path object pointing to the versioned source.zip file, example:
            ${s3dir_lambda}/source/{source_version}/{source_sha256}/source.zip

        .. note::
            The SHA256 hash is essential for proper AWS Lambda deployments. When using CDK,
            CloudFormation, or AWS APIs, if the S3 path remains unchanged between deployments,
            AWS assumes the code hasn't changed and skips the update. Including the source
            SHA256 in the path ensures that any code changes result in a new S3 location,
            forcing AWS to recognize and deploy the updated Lambda function code.
        """
        return self.s3dir_lambda.joinpath(
            "source",
            source_version,
            source_sha256,
            "source.zip",
        )


def upload_source_artifacts(
    s3_client: "S3Client",
    source_version: str,
    source_sha256: str,
    path_source_zip: Path,
    s3dir_lambda: "S3Path",
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
    :param s3dir_lambda: Base S3 directory for Lambda artifacts, e.g., ``s3://bucket/path/to/lambda/``
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
        printer(f"{s3dir_lambda.uri =}")

    # Initialize S3 layout manager and get target path
    source_s3_layout = SourceS3Layout(
        s3dir_lambda=s3dir_lambda,
    )
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
    s3dir_lambda: "S3Path",
    skip_prompt: bool = False,
    verbose: bool = True,
    printer: T_PRINTER = print,
) -> BuildSourceArtifactsResult:
    """
    Build, package, and upload Lambda source artifacts to S3.

    This is a all-in-one function that handles the complete lifecycle of Lambda source.

    :param s3_client: Boto3 S3 client for upload operations
    :param dir_project_root: Root directory of the Python project containing setup.py or pyproject.toml
    :param s3dir_lambda: Base S3 directory for Lambda artifacts, e.g., ``s3://bucket/path/to/lambda/``
    :param skip_prompt: If True, automatically clean existing build directory without user confirmation
    :param verbose: If True, display detailed progress information; if False, run quietly
    :param printer: Function to handle output messages, defaults to built-in print

    :return: :class:`BuildSourceArtifactsResult` containing SHA256 hash and S3 path of the uploaded source.zip

    .. seealso::

        - :func:`build_source_artifacts_using_pip`
        - :func:`create_source_zip`
        - :func:`upload_source_artifacts`
    """
    # step 1: build source artifacts using pip
    path_bin_pip = dir_project_root / ".venv" / "bin" / "pip"
    path_pyproject_toml = dir_project_root / "pyproject.toml"
    dir_lambda_source_build = dir_project_root / "build" / "lambda" / "source" / "build"
    build_source_artifacts_using_pip(
        path_bin_pip=path_bin_pip,
        path_setup_py_or_pyproject_toml=path_pyproject_toml,
        dir_lambda_source_build=dir_lambda_source_build,
        skip_prompt=skip_prompt,
        verbose=verbose,
        printer=printer,
    )

    # step 2: create compressed zip archive of the built source
    path_source_zip = dir_lambda_source_build / "source.zip"
    source_sha256 = create_source_zip(
        dir_lambda_source_build=dir_lambda_source_build,
        path_source_zip=path_source_zip,
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
        path_source_zip=path_source_zip,
        s3dir_lambda=s3dir_lambda,
        verbose=verbose,
        printer=printer,
    )

    return BuildSourceArtifactsResult(
        source_sha256=source_sha256,
        s3path_source_zip=s3path_source_zip,
    )
