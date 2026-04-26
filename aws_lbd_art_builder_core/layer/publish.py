# -*- coding: utf-8 -*-

"""
Lambda layer publication — Step 4 of the layer workflow.

Takes the uploaded ``layer.zip`` from S3 and creates a versioned Lambda layer
resource via the AWS API.

**Why smart publishing?**

Creating a Lambda layer version is a non-reversible, append-only operation
(versions can be deleted but not overwritten). Publishing identical
dependencies as a new version wastes version numbers and forces downstream
stacks to update for no reason. This module compares the local dependency
manifest against the previously stored one and skips the publish when nothing
has changed.
"""

import typing as T
import dataclasses
from functools import cached_property

from func_args.api import BaseFrozenModel
from func_args.api import REQ

from ..constants import S3MetadataKeyEnum
from ..imports import S3Path
from ..imports import simple_aws_lambda

from .foundation import LayerManifestManager


if T.TYPE_CHECKING:  # pragma: no cover
    from mypy_boto3_lambda import LambdaClient


@dataclasses.dataclass(frozen=True)
class LambdaLayerVersionPublisher(LayerManifestManager):
    """
    Command class for intelligent Lambda layer version publishing.

    Inherits :class:`~aws_lbd_art_builder_core.layer.foundation.LayerManifestManager`
    for manifest handling and adds layer publication logic.

    **Why Command Pattern here?**

    Publishing involves multiple AWS API calls with shared state (layer name,
    clients, manifest path, S3 layout). Keeping these as fields on a frozen
    dataclass makes the publisher easy to construct, inspect, and test —
    same rationale as the builder classes.
    """

    # fmt: off
    layer_name: str = dataclasses.field(default=REQ)
    lambda_client: "LambdaClient" = dataclasses.field(default=REQ)
    publish_layer_version_kwargs: dict[str, T.Any] | None = dataclasses.field(default=None)
    # fmt: on

    def run(self) -> "LayerDeployment":
        """
        Execute the complete layer publication workflow.
        """
        self.log("--- Start publish Lambda layer workflow")
        self.step_1_preflight_check()
        layer_deployment = self.step_2_publish_layer_version()
        return layer_deployment

    def step_1_preflight_check(self):
        """
        Perform read-only validation of build environment and project configuration.
        """
        self.log("--- Step 1 - Flight Check")
        self.step_1_1_ensure_layer_zip_exists()
        self.step_1_2_ensure_layer_zip_is_consistent()
        self.step_1_3_ensure_dependencies_have_changed()

    def step_2_publish_layer_version(self) -> "LayerDeployment":
        """
        Execute the layer publication workflow, creating a new Lambda layer version.
        """
        self.log("--- Step 2 - Publish Lambda Layer Version")
        layer_version, layer_version_arn = self.step_2_1_run_publish_layer_version_api()
        s3path_manifest = self.step_2_2_upload_dependency_manifest(
            version=layer_version
        )
        layer_deployment = LayerDeployment(
            layer_name=self.layer_name,
            layer_version=layer_version,
            layer_version_arn=layer_version_arn,
            s3path_manifest=s3path_manifest,
        )
        return layer_deployment

    # --- step_1_preflight_check sub-steps
    def step_1_1_ensure_layer_zip_exists(self):
        """
        Verify that the layer.zip file was successfully uploaded to S3.
        """
        s3path = self.s3_layout.s3path_temp_layer_zip
        self.log(f"--- Step 1.1 - Verify layer.zip exists in S3 at {s3path.uri}...")
        if self.is_layer_zip_exists() is False:
            s3path = self.s3_layout.s3path_temp_layer_zip
            raise FileNotFoundError(
                f"Layer zip file {s3path.uri} does not exist! "
                f"Please run the upload step first to create the layer.zip in S3."
            )
        else:
            self.log("Layer zip file found in S3.")

    def is_layer_zip_exists(self) -> bool:
        """
        Check if the layer zip file exists in S3 temporary storage.

        :return: True if layer.zip exists in S3, False otherwise
        """
        s3path = self.s3_layout.s3path_temp_layer_zip
        return s3path.exists(bsm=self.s3_client)

    def step_1_2_ensure_layer_zip_is_consistent(self):
        """
        Validate that the uploaded layer.zip matches the current local manifest.
        """
        self.log("--- Step 1.2 - Validate layer.zip consistency with manifest")
        if self.is_layer_zip_consistent() is False:
            path = self.path_manifest
            s3path = self.s3_layout.s3path_temp_layer_zip
            raise ValueError(
                f"Layer zip file {s3path.uri} is inconsistent with current manifest {path}! "
                f"The uploaded layer.zip corresponds to a different dependency state. "
                f"Please re-run the upload step to sync the layer.zip with current dependencies."
            )
        else:
            self.log("Layer zip file is consistent with current manifest.")

    def is_layer_zip_consistent(self) -> bool:
        """
        Compare the manifest MD5 stored in S3 metadata with the local manifest.

        :return: True if uploaded layer.zip matches current manifest, False otherwise
        """
        s3path = self.s3_layout.s3path_temp_layer_zip
        s3path.head_object(bsm=self.s3_client)
        manifest_md5 = s3path.metadata.get(
            S3MetadataKeyEnum.manifest_md5.value, "__invalid__"
        )
        return manifest_md5 == self.manifest_md5

    def step_1_3_ensure_dependencies_have_changed(self):
        """
        Check if dependencies have changed since the last publication.

        This is the core intelligence that prevents unnecessary layer version
        creation — skips publishing when the manifest is identical to the
        previously published one.
        """
        self.log(
            "--- Step 1.3 - Check if dependencies have changed since last publication"
        )
        has_changed = self.has_dependency_manifest_changed()
        if not has_changed:
            raise ValueError("Dependencies unchanged since last publication - skipping")
        else:
            self.log("Dependencies have changed - proceeding with publishing.")

    def has_dependency_manifest_changed(self) -> bool:
        """
        Detect if the local dependency manifest has changed from the last published layer.

        :return: True if local manifest differs from latest published version,
                False if they are identical (no changes detected)
        """
        latest_layer_version = self.latest_layer_version
        if latest_layer_version is None:
            return True  # No previous version exists, treat as changed

        path_manifest = self.path_manifest
        s3path_manifest = self.get_versioned_manifest(
            version=latest_layer_version.version
        )
        if s3path_manifest.exists(bsm=self.s3_client) is False:
            return True

        local_manifest_content = path_manifest.read_text()
        stored_manifest_content = s3path_manifest.read_text(bsm=self.s3_client)

        return local_manifest_content != stored_manifest_content

    @cached_property
    def latest_layer_version(self) -> T.Union["simple_aws_lambda.LayerVersion", None]:
        return simple_aws_lambda.get_latest_layer_version(
            lambda_client=self.lambda_client,
            layer_name=self.layer_name,
        )

    # --- step_2_publish_layer_version sub-steps
    def step_2_1_run_publish_layer_version_api(self) -> tuple[int, str]:
        """
        Publish a new Lambda layer version using the zip file stored in S3.

        :return: Tuple of (layer_version_number, layer_version_arn)
        """
        self.log("--- Step 2.1 - Publish new Lambda layer version via API")
        if self.publish_layer_version_kwargs is None:
            publish_layer_version_kwargs = {}
        else:
            publish_layer_version_kwargs = self.publish_layer_version_kwargs
        s3path = self.s3_layout.s3path_temp_layer_zip
        response = self.lambda_client.publish_layer_version(
            LayerName=self.layer_name,
            Content={
                "S3Bucket": s3path.bucket,
                "S3Key": s3path.key,
            },
            **publish_layer_version_kwargs,
        )
        layer_version_arn = response["LayerVersionArn"]
        layer_version = int(layer_version_arn.split(":")[-1])
        self.log(f"Successfully published layer version: {layer_version}")
        self.log(f"Layer version ARN: {layer_version_arn}")
        return layer_version, layer_version_arn

    def step_2_2_upload_dependency_manifest(
        self,
        version: int,
    ) -> "S3Path":
        """
        Upload the dependency manifest file to S3 for the specified layer version.

        :param version: The layer version number to associate the manifest with
        :return: S3Path where the manifest was stored
        """
        self.log("--- Step 2.2 - Upload dependency manifest to S3")
        path = self.path_manifest
        s3path_manifest = self.get_versioned_manifest(version=version)
        s3path_manifest.write_bytes(
            path.read_bytes(),
            content_type="text/plain",
            bsm=self.s3_client,
        )
        if self.verbose:
            self.log(f"Manifest stored at: {s3path_manifest.uri}")
            self.log(f"Console URL: {s3path_manifest.console_url}")
        return s3path_manifest


@dataclasses.dataclass(frozen=True)
class LayerDeployment(BaseFrozenModel):
    """
    Immutable record of a completed layer deployment.
    """

    layer_name: str = dataclasses.field(default=REQ)
    layer_version: int = dataclasses.field(default=REQ)
    layer_version_arn: str = dataclasses.field(default=REQ)
    s3path_manifest: "S3Path" = dataclasses.field(default=REQ)
