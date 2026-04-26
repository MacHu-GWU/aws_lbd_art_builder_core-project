# -*- coding: utf-8 -*-

"""
Tests for layer publish module: LambdaLayerVersionPublisher, LayerDeployment.

Uses BaseMockAwsTest (moto) for S3 + Lambda mock services.
We upload a fake layer.zip via upload_layer_zip_to_s3, then exercise the
publisher's preflight checks and publish workflow.
"""

from aws_lbd_art_builder_core.layer.publish import LambdaLayerVersionPublisher
from aws_lbd_art_builder_core.layer.publish import LayerDeployment

import hashlib
import zipfile
from pathlib import Path

import pytest
from s3pathlib import S3Path

from aws_lbd_art_builder_core.constants import S3MetadataKeyEnum
from aws_lbd_art_builder_core.layer.foundation import LayerPathLayout
from aws_lbd_art_builder_core.layer.foundation import LayerS3Layout
from aws_lbd_art_builder_core.layer.upload import upload_layer_zip_to_s3
from aws_lbd_art_builder_core.tests.mock_aws import BaseMockAwsTest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
DIR_TESTS = Path(__file__).parent


def _create_fake_project(base_dir: Path) -> tuple[Path, Path]:
    """
    Create a minimal project with a fake layer.zip and manifest.

    Returns (path_pyproject_toml, path_manifest).
    """
    pyproject = base_dir / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'fake'")

    manifest = base_dir / "uv.lock"
    manifest.write_text("fake-pkg==1.0.0\n")

    layout = LayerPathLayout(path_pyproject_toml=pyproject)
    layout.mkdirs()

    path_layer_zip = layout.path_build_lambda_layer_zip
    with zipfile.ZipFile(path_layer_zip, "w") as zf:
        zf.writestr("python/fake_pkg.py", "x = 1")

    return pyproject, manifest


# ---------------------------------------------------------------------------
# Tests: LambdaLayerVersionPublisher — preflight checks
# ---------------------------------------------------------------------------
class TestPublisherPreflightChecks(BaseMockAwsTest):
    use_mock = True

    BUCKET = "test-publish-bucket"
    LAYER_NAME = "test-layer"

    @classmethod
    def setup_class_post_hook(cls):
        cls.create_s3_bucket(cls.BUCKET)
        cls.s3dir_lambda = S3Path(f"{cls.BUCKET}/lambda/my-func/")
        cls.lambda_client = cls.boto_ses.client("lambda")

        build_dir = DIR_TESTS / "build" / "publish_test"
        build_dir.mkdir(parents=True, exist_ok=True)
        cls.path_pyproject_toml, cls.path_manifest = _create_fake_project(build_dir)

    def _make_publisher(self, **kwargs):
        defaults = dict(
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            s3_client=self.s3_client,
            layer_name=self.LAYER_NAME,
            lambda_client=self.lambda_client,
            verbose=False,
        )
        defaults.update(kwargs)
        return LambdaLayerVersionPublisher(**defaults)

    def _upload_layer(self):
        upload_layer_zip_to_s3(
            s3_client=self.s3_client,
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            verbose=False,
        )

    # --- is_layer_zip_exists ---
    def test_is_layer_zip_exists_false_when_not_uploaded(self):
        # make sure there's no zip in S3
        s3_layout = LayerS3Layout(s3dir_lambda=self.s3dir_lambda)
        s3path = s3_layout.s3path_temp_layer_zip
        if s3path.exists(bsm=self.s3_client):
            s3path.delete(bsm=self.s3_client)

        publisher = self._make_publisher()
        assert publisher.is_layer_zip_exists() is False

    def test_is_layer_zip_exists_true_after_upload(self):
        self._upload_layer()
        publisher = self._make_publisher()
        assert publisher.is_layer_zip_exists() is True

    def test_step_1_1_raises_when_zip_not_exists(self):
        s3_layout = LayerS3Layout(s3dir_lambda=self.s3dir_lambda)
        s3path = s3_layout.s3path_temp_layer_zip
        if s3path.exists(bsm=self.s3_client):
            s3path.delete(bsm=self.s3_client)

        publisher = self._make_publisher()
        with pytest.raises(FileNotFoundError, match="does not exist"):
            publisher.step_1_1_ensure_layer_zip_exists()

    def test_step_1_1_passes_when_zip_exists(self):
        self._upload_layer()
        publisher = self._make_publisher()
        publisher.step_1_1_ensure_layer_zip_exists()  # should not raise

    # --- is_layer_zip_consistent ---
    def test_is_layer_zip_consistent_true(self):
        self._upload_layer()
        publisher = self._make_publisher()
        assert publisher.is_layer_zip_consistent() is True

    def test_is_layer_zip_consistent_false_when_manifest_changed(self):
        self._upload_layer()
        # change the local manifest after upload
        self.path_manifest.write_text("changed-pkg==2.0.0\n")
        publisher = self._make_publisher()
        assert publisher.is_layer_zip_consistent() is False
        # restore
        self.path_manifest.write_text("fake-pkg==1.0.0\n")

    def test_step_1_2_raises_when_inconsistent(self):
        self._upload_layer()
        self.path_manifest.write_text("changed-pkg==2.0.0\n")
        publisher = self._make_publisher()
        with pytest.raises(ValueError, match="inconsistent"):
            publisher.step_1_2_ensure_layer_zip_is_consistent()
        self.path_manifest.write_text("fake-pkg==1.0.0\n")

    def test_step_1_2_passes_when_consistent(self):
        self._upload_layer()
        publisher = self._make_publisher()
        publisher.step_1_2_ensure_layer_zip_is_consistent()  # should not raise

    # --- has_dependency_manifest_changed ---
    def test_has_dependency_manifest_changed_true_when_no_previous_version(self):
        self._upload_layer()
        publisher = self._make_publisher()
        # no layer has been published yet
        assert publisher.has_dependency_manifest_changed() is True

    def test_step_1_3_raises_when_unchanged(self):
        """
        After a full publish, the manifest is stored in S3.
        If we try to publish again without changing the manifest, step_1_3 should raise.
        """
        self._upload_layer()
        publisher = self._make_publisher()
        # do a full publish first
        publisher.run()

        # now re-upload and try again with same manifest
        self._upload_layer()
        publisher2 = self._make_publisher()
        with pytest.raises(ValueError, match="unchanged"):
            publisher2.step_1_3_ensure_dependencies_have_changed()


# ---------------------------------------------------------------------------
# Tests: LambdaLayerVersionPublisher — full publish workflow
# ---------------------------------------------------------------------------
class TestPublisherFullWorkflow(BaseMockAwsTest):
    use_mock = True

    BUCKET = "test-publish-workflow-bucket"
    LAYER_NAME = "test-layer-workflow"

    @classmethod
    def setup_class_post_hook(cls):
        cls.create_s3_bucket(cls.BUCKET)
        cls.s3dir_lambda = S3Path(f"{cls.BUCKET}/lambda/my-func/")
        cls.lambda_client = cls.boto_ses.client("lambda")

        build_dir = DIR_TESTS / "build" / "publish_workflow_test"
        build_dir.mkdir(parents=True, exist_ok=True)
        cls.path_pyproject_toml, cls.path_manifest = _create_fake_project(build_dir)

        # upload layer.zip
        upload_layer_zip_to_s3(
            s3_client=cls.s3_client,
            path_pyproject_toml=cls.path_pyproject_toml,
            s3dir_lambda=cls.s3dir_lambda,
            path_manifest=cls.path_manifest,
            verbose=False,
        )

        # run full publish
        cls.publisher = LambdaLayerVersionPublisher(
            path_pyproject_toml=cls.path_pyproject_toml,
            s3dir_lambda=cls.s3dir_lambda,
            path_manifest=cls.path_manifest,
            s3_client=cls.s3_client,
            layer_name=cls.LAYER_NAME,
            lambda_client=cls.lambda_client,
            verbose=True,
            printer=lambda msg: None,  # suppress output
        )
        cls.result = cls.publisher.run()

    def test_returns_layer_deployment(self):
        assert isinstance(self.result, LayerDeployment)

    def test_layer_name_matches(self):
        assert self.result.layer_name == self.LAYER_NAME

    def test_layer_version_is_positive_int(self):
        assert isinstance(self.result.layer_version, int)
        assert self.result.layer_version >= 1

    def test_layer_version_arn_contains_layer_name(self):
        assert self.LAYER_NAME in self.result.layer_version_arn

    def test_manifest_stored_in_s3(self):
        assert self.result.s3path_manifest.exists(bsm=self.s3_client)

    def test_manifest_content_matches_local(self):
        stored = self.result.s3path_manifest.read_text(bsm=self.s3_client)
        local = self.path_manifest.read_text()
        assert stored == local

    def test_manifest_s3path_contains_version(self):
        version_str = str(self.result.layer_version).zfill(6)
        assert version_str in self.result.s3path_manifest.key

    def test_publish_with_custom_kwargs(self):
        """publish_layer_version_kwargs are forwarded to the API."""
        # change manifest so we can publish again
        self.path_manifest.write_text("new-pkg==3.0.0\n")
        upload_layer_zip_to_s3(
            s3_client=self.s3_client,
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            verbose=False,
        )
        publisher = LambdaLayerVersionPublisher(
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            s3_client=self.s3_client,
            layer_name=self.LAYER_NAME,
            lambda_client=self.lambda_client,
            publish_layer_version_kwargs={
                "Description": "test description",
            },
            verbose=False,
        )
        result = publisher.run()
        assert result.layer_version >= 2
        # restore
        self.path_manifest.write_text("fake-pkg==1.0.0\n")


# ---------------------------------------------------------------------------
# Tests: LayerDeployment
# ---------------------------------------------------------------------------
class TestLayerDeployment:

    def test_fields(self):
        s3path = S3Path("my-bucket/lambda/layer/000001/uv.lock")
        deployment = LayerDeployment(
            layer_name="my-layer",
            layer_version=1,
            layer_version_arn="arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1",
            s3path_manifest=s3path,
        )
        assert deployment.layer_name == "my-layer"
        assert deployment.layer_version == 1
        assert "my-layer" in deployment.layer_version_arn
        assert deployment.s3path_manifest.basename == "uv.lock"

    def test_frozen(self):
        s3path = S3Path("my-bucket/lambda/layer/000001/uv.lock")
        deployment = LayerDeployment(
            layer_name="my-layer",
            layer_version=1,
            layer_version_arn="arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1",
            s3path_manifest=s3path,
        )
        with pytest.raises((AttributeError, TypeError)):
            deployment.layer_name = "other"


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.publish",
        preview=False,
    )
