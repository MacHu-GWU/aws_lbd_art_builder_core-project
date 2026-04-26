# -*- coding: utf-8 -*-

"""
Path and S3 layout managers for Lambda source deployment artifacts.

Defines two pure-convention layout classes that encode the directory structure
used by the Lambda source build workflow:

- :class:`SourcePathLayout` — local filesystem paths under
  ``{dir_project_root}/build/lambda/source/``
- :class:`SourceS3Layout` — S3 paths whose root is the ``source/``-scoped
  S3 directory, e.g. ``s3://bucket/path/to/lambda/source/``

Neither class performs I/O; they only compute paths so callers can stay
decoupled from the hard-coded directory names.

Relationship to the higher-level ``s3dir_lambda`` prefix
---------------------------------------------------------
``s3dir_lambda`` is a shared parent used by multiple artifact types (source,
layer, …).  Each type **owns a scoped sub-prefix** so that "delete everything
under this layout's root" is safe and never touches sibling artifacts.
:class:`SourceS3Layout` is constructed directly with the already-scoped
``source/`` directory as ``dir_root``.  Use the convenience factory
:meth:`SourceS3Layout.from_s3dir_lambda` to derive that scoped root
automatically from the shared ``s3dir_lambda`` parent.
"""

import dataclasses
from pathlib import Path

from func_args.api import BaseFrozenModel
from func_args.api import REQ
from ..imports import S3Path


@dataclasses.dataclass(frozen=True)
class SourcePathLayout(BaseFrozenModel):
    """
    Local filesystem path layout for Lambda source build artifacts.

    :param dir_root: Root directory for source artifacts,
        e.g. ``/path/to/git-repo/build/lambda/source``

    Layout::

        {dir_root}/build/        ← pip install target (temporary files)
        {dir_root}/source.zip    ← final deployment package
    """

    dir_root: "Path" = dataclasses.field(default=REQ)

    @property
    def dir_build(self) -> Path:
        """Directory where pip installs the package (temporary files)."""
        return self.dir_root / "build"

    @property
    def path_source_zip(self) -> Path:
        """Final deployment zip archive."""
        return self.dir_root / "source.zip"


@dataclasses.dataclass(frozen=True)
class SourceS3Layout(BaseFrozenModel):
    """
    S3 path layout manager for Lambda source artifacts.

    The root is scoped to the source-specific S3 directory so that operations
    such as "delete everything under root" only affect source artifacts and never
    accidentally touch sibling prefixes (e.g. ``layer/``).

    :param dir_root: Source-specific S3 root directory,
        e.g. ``s3://bucket/path/to/lambda/source/``

    Layout, see :meth:`get_s3path_source_zip`::

        {dir_root}/0.1.1/{source_sha256}/source.zip
        {dir_root}/0.1.2/{source_sha256}/source.zip
        {dir_root}/0.1.3/{source_sha256}/source.zip
        ...
    """

    dir_root: "S3Path" = dataclasses.field(default=REQ)

    @classmethod
    def from_s3dir_lambda(cls, s3dir_lambda: "S3Path") -> "SourceS3Layout":
        """
        Derive a :class:`SourceS3Layout` from the shared Lambda S3 base directory.

        ``s3dir_lambda`` is the higher-level anchor shared by all Lambda artifact
        types (source, layer, …).  This factory pins the root to the ``source/``
        sub-prefix, giving the source layout an isolated namespace.

        :param s3dir_lambda: Base S3 directory for Lambda artifacts,
            e.g. ``s3://bucket/path/to/lambda/``
        :return: :class:`SourceS3Layout` rooted at ``{s3dir_lambda}/source/``
        """
        return cls(dir_root=s3dir_lambda.joinpath("source").to_dir())

    def get_s3path_source_zip(
        self,
        source_version: str,
        source_sha256: str,
    ) -> "S3Path":
        """
        Generate S3 path for a specific version of the Lambda source zip.

        :param source_version: Semantic version string, e.g., ``"0.1.1"``
        :param source_sha256: SHA256 hash of the source build directory

        :return: S3Path pointing to the versioned source.zip file,
            e.g. ``{dir_root}/{source_version}/{source_sha256}/source.zip``

        .. note::
            Including the SHA256 hash in the path ensures that any code change
            produces a new S3 key, which forces CDK / CloudFormation / AWS APIs
            to recognise and deploy the updated Lambda function code.
        """
        return self.dir_root.joinpath(
            source_version,
            source_sha256,
            "source.zip",
        )
