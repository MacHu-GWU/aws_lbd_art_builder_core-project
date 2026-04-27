# -*- coding: utf-8 -*-

"""
End-to-end Lambda layer workflow — Build → Package → Upload → Publish.

This module provides a single :class:`LayerDeploymentWorkflow` class that orchestrates
the complete 4-step pipeline for creating and deploying an AWS Lambda layer:

1. **Build** — install dependencies via a builder (duck-typed, e.g. uv, pip, poetry)
2. **Package** — create ``layer.zip`` from the build artifacts
3. **Upload** — upload ``layer.zip`` to S3 staging
4. **Publish** — create a versioned Lambda layer in AWS

Usage::

    deployment = LayerDeploymentWorkflow(
        builder=my_builder,        # duck type: needs .run() and .path_layout
        path_manifest=Path("uv.lock"),
        s3dir_lambda=S3Path("s3://bucket/lambda/"),
        layer_name="my_layer",
        s3_client=bsm,
        lambda_client=lambda_client,
    )
    layer_deployment = deployment.run()
"""

import typing as T
import dataclasses
from pathlib import Path

from func_args.api import REQ

from ..imports import S3Path

from .foundation import LayerPathLayout
from .foundation import BaseLogger
from .package import create_layer_zip_file
from .package import default_ignore_package_list
from .upload import upload_layer_zip_to_s3
from .publish import LambdaLayerVersionPublisher
from .publish import LayerDeployment

if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_lambda import LambdaClient


@T.runtime_checkable
class T_BUILDER(T.Protocol):
    """
    Protocol for Lambda layer builders.

    Any builder that has a ``run()`` method and a ``path_layout`` attribute
    satisfies this protocol.
    """

    @property
    def path_layout(self) -> LayerPathLayout: ...

    def run(self) -> None: ...


@dataclasses.dataclass(frozen=True)
class LayerDeploymentWorkflow(BaseLogger): # pragma: no cover
    """
    One-stop orchestrator for the complete Lambda layer lifecycle.

    This class combines the 4 steps — Build, Package, Upload, Publish — into
    a single ``run()`` call. Each step can also be called individually.

    :param builder: A builder object that satisfies :class:`T_BUILDER` protocol
        (i.e. has a ``.run()`` method and a ``.path_layout`` attribute).
        Downstream packages (uv, pip, poetry) each provide their own builder.
    :param path_manifest: Path to the dependency manifest file used for
        change detection (e.g. ``uv.lock``, ``poetry.lock``, ``requirements.txt``).
    :param s3dir_lambda: S3 directory where Lambda artifacts are stored
        (e.g. ``S3Path("s3://my-bucket/projects/my_app/lambda/")``).
    :param layer_name: Name of the Lambda layer to create / update
        (e.g. ``"my_app"``).
    :param s3_client: Boto3 S3 client (or ``BotoSesManager``) for S3 operations.
    :param lambda_client: Boto3 Lambda client for publishing the layer version.
    :param ignore_package_list: Packages to exclude from ``layer.zip``.
        Defaults to :data:`~aws_lbd_art_builder_core.layer.package.default_ignore_package_list`
        (boto3, botocore, setuptools, pip, pytest, etc.).
    :param publish_layer_version_kwargs: Extra keyword arguments passed to
        ``lambda_client.publish_layer_version()``
        (e.g. ``{"CompatibleRuntimes": ["python3.12"], "Description": "..."}``).
    :param verbose: If True, log progress messages. Inherited from
        :class:`~aws_lbd_art_builder_core.layer.foundation.BaseLogger`.
    :param printer: Callable for emitting log messages. Inherited from
        :class:`~aws_lbd_art_builder_core.layer.foundation.BaseLogger`.

    Example::

        import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv
        from boto_session_manager import BotoSesManager
        from s3pathlib import S3Path

        from aws_lbd_art_builder_core.layer.workflow import LayerDeploymentWorkflow

        bsm = BotoSesManager(region_name="us-east-1")

        # 1. Create a builder (downstream package provides this)
        builder = aws_lbd_art_builder_uv.layer_api.UvLambdaLayerLocalBuilder(
            path_pyproject_toml=Path("pyproject.toml"),
            skip_prompt=True,
        )

        # 2. Run the full pipeline in one call
        workflow = LayerDeploymentWorkflow(
            builder=builder,
            path_manifest=Path("uv.lock"),
            s3dir_lambda=S3Path("s3://my-bucket/projects/my_app/lambda/"),
            layer_name="my_app",
            s3_client=bsm,
            lambda_client=bsm.lambda_client,
            publish_layer_version_kwargs={
                "CompatibleRuntimes": ["python3.12"],
                "Description": "my_app dependencies layer",
            },
        )
        result = workflow.run()
        print(result.layer_version_arn)
    """
    # fmt: off
    # Step 1
    builder: T_BUILDER = dataclasses.field(default=REQ)
    # Step 2-4
    path_manifest: Path = dataclasses.field(default=REQ)
    s3dir_lambda: "S3Path" = dataclasses.field(default=REQ)
    layer_name: str = dataclasses.field(default=REQ)
    s3_client: "S3Client" = dataclasses.field(default=REQ)
    lambda_client: "LambdaClient" = dataclasses.field(default=REQ)
    ignore_package_list: T.Optional[list[str]] = dataclasses.field(default=None)
    publish_layer_version_kwargs: T.Optional[dict[str, T.Any]] = dataclasses.field(default=None)
    # fmt: on

    def run(self) -> "LayerDeployment":
        """
        Execute the full Build → Package → Upload → Publish pipeline.

        :return: :class:`~aws_lbd_art_builder_core.layer.publish.LayerDeployment`
            record with layer version details
        """
        self.step_1_build()
        self.step_2_package()
        self.step_3_upload()
        return self.step_4_publish()

    def step_1_build(self):
        """
        Step 1 — Build: install dependencies using the provided builder.
        """
        self.log_header("Step 1: Build Lambda Layer")
        self.builder.run()

    def step_2_package(self):
        """
        Step 2 — Package: create ``layer.zip`` from build artifacts.
        """
        self.log_header("Step 2: Package (create layer.zip)")
        path_layout = self.builder.path_layout
        dir_python = path_layout.dir_python
        path_layer_zip = path_layout.path_build_lambda_layer_zip

        self.log_detail(f"dir_python     = {dir_python}")
        self.log_detail(f"path_layer_zip = {path_layer_zip}")

        if self.ignore_package_list is not None:
            ignore = self.ignore_package_list
        else:
            ignore = list(default_ignore_package_list)

        create_layer_zip_file(
            dir_python=dir_python,
            path_layer_zip=path_layer_zip,
            ignore_package_list=ignore,
            verbose=self.verbose,
        )

    def step_3_upload(self):
        """
        Step 3 — Upload: send ``layer.zip`` to S3 staging location.
        """
        self.log_header("Step 3: Upload layer.zip to S3")
        path_layout = self.builder.path_layout
        upload_layer_zip_to_s3(
            s3_client=self.s3_client,
            path_pyproject_toml=path_layout.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            verbose=self.verbose,
            printer=self.printer,
        )

    def step_4_publish(self) -> "LayerDeployment":
        """
        Step 4 — Publish: create a new Lambda layer version from the uploaded zip.

        :return: :class:`~aws_lbd_art_builder_core.layer.publish.LayerDeployment`
            record with layer version details
        """
        self.log_header("Step 4: Publish Lambda Layer Version")
        path_layout = self.builder.path_layout
        publisher = LambdaLayerVersionPublisher(
            path_pyproject_toml=path_layout.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            s3_client=self.s3_client,
            layer_name=self.layer_name,
            lambda_client=self.lambda_client,
            publish_layer_version_kwargs=self.publish_layer_version_kwargs,
            verbose=self.verbose,
            printer=self.printer,
        )
        return publisher.run()
