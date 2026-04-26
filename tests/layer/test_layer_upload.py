# -*- coding: utf-8 -*-

"""
Tests for layer upload module: upload_layer_zip_to_s3.

Uses BaseMockAwsTest so all S3 calls hit moto in-memory.
A fake layer.zip and manifest file are created in setup_class_post_hook.
"""

from aws_lbd_art_builder_core.layer.upload import upload_layer_zip_to_s3

import hashlib
import zipfile
from pathlib import Path

from s3pathlib import S3Path

from aws_lbd_art_builder_core.constants import S3MetadataKeyEnum
from aws_lbd_art_builder_core.layer.foundation import LayerPathLayout
from aws_lbd_art_builder_core.layer.foundation import LayerS3Layout
from aws_lbd_art_builder_core.tests.mock_aws import BaseMockAwsTest


# ---------------------------------------------------------------------------
# Paths — build a fake layer.zip under a temporary project structure
# ---------------------------------------------------------------------------
DIR_TESTS = Path(__file__).parent


def _create_fake_project(base_dir: Path) -> tuple[Path, Path, Path]:
    """
    Create a minimal project structure with a fake layer.zip and manifest.

    Returns (path_pyproject_toml, path_layer_zip, path_manifest).
    """
    pyproject = base_dir / "pyproject.toml"
    pyproject.write_text("[project]\nname = 'fake'")

    manifest = base_dir / "uv.lock"
    manifest.write_text("fake-pkg==1.0.0\n")

    # create layer.zip at the expected location
    layout = LayerPathLayout(path_pyproject_toml=pyproject)
    layout.mkdirs()

    # put a small file in python/ and zip it
    (layout.dir_python / "fake_pkg.py").write_text("x = 1")
    path_layer_zip = layout.path_build_lambda_layer_zip
    with zipfile.ZipFile(path_layer_zip, "w") as zf:
        zf.writestr("python/fake_pkg.py", "x = 1")

    return pyproject, path_layer_zip, manifest


# ---------------------------------------------------------------------------
# Tests: upload_layer_zip_to_s3
# ---------------------------------------------------------------------------
class TestUploadLayerZipToS3(BaseMockAwsTest):
    use_mock = True

    BUCKET = "test-layer-upload-bucket"

    s3dir_lambda: S3Path = None
    path_pyproject_toml: Path = None
    path_manifest: Path = None
    path_layer_zip: Path = None

    @classmethod
    def setup_class_post_hook(cls):
        cls.create_s3_bucket(cls.BUCKET)
        cls.s3dir_lambda = S3Path(f"{cls.BUCKET}/lambda/my-func/")

        # create fake project in a temp dir under tests/layer/build/
        build_dir = DIR_TESTS / "build" / "upload_test"
        build_dir.mkdir(parents=True, exist_ok=True)
        cls.path_pyproject_toml, cls.path_layer_zip, cls.path_manifest = (
            _create_fake_project(build_dir)
        )

    # ------------------------------------------------------------------
    # Object existence
    # ------------------------------------------------------------------
    def test_object_exists_in_s3(self):
        upload_layer_zip_to_s3(
            s3_client=self.s3_client,
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            verbose=False,
        )
        s3_layout = LayerS3Layout(s3dir_lambda=self.s3dir_lambda)
        assert s3_layout.s3path_temp_layer_zip.exists(bsm=self.s3_client)

    # ------------------------------------------------------------------
    # S3 path matches layout
    # ------------------------------------------------------------------
    def test_s3path_matches_layout(self):
        upload_layer_zip_to_s3(
            s3_client=self.s3_client,
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            verbose=False,
        )
        s3_layout = LayerS3Layout(s3dir_lambda=self.s3dir_lambda)
        s3path = s3_layout.s3path_temp_layer_zip
        assert s3path.uri == "s3://test-layer-upload-bucket/lambda/my-func/layer/layer.zip"

    # ------------------------------------------------------------------
    # Content type
    # ------------------------------------------------------------------
    def test_content_type_is_zip(self):
        upload_layer_zip_to_s3(
            s3_client=self.s3_client,
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            verbose=False,
        )
        s3_layout = LayerS3Layout(s3dir_lambda=self.s3dir_lambda)
        s3path = s3_layout.s3path_temp_layer_zip
        head = self.s3_client.head_object(Bucket=s3path.bucket, Key=s3path.key)
        assert head["ContentType"] == "application/zip"

    # ------------------------------------------------------------------
    # Metadata — manifest_md5
    # ------------------------------------------------------------------
    def test_metadata_contains_manifest_md5(self):
        upload_layer_zip_to_s3(
            s3_client=self.s3_client,
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            verbose=False,
        )
        s3_layout = LayerS3Layout(s3dir_lambda=self.s3dir_lambda)
        s3path = s3_layout.s3path_temp_layer_zip
        head = self.s3_client.head_object(Bucket=s3path.bucket, Key=s3path.key)
        metadata = head["Metadata"]
        expected_md5 = hashlib.md5(self.path_manifest.read_bytes()).hexdigest()
        assert metadata[S3MetadataKeyEnum.manifest_md5.value] == expected_md5

    # ------------------------------------------------------------------
    # Verbose mode
    # ------------------------------------------------------------------
    def test_verbose_mode_prints_messages(self):
        messages = []
        upload_layer_zip_to_s3(
            s3_client=self.s3_client,
            path_pyproject_toml=self.path_pyproject_toml,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=self.path_manifest,
            verbose=True,
            printer=messages.append,
        )
        assert any("Uploading" in m for m in messages)
        assert any("upload from" in m for m in messages)


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.upload",
        preview=False,
    )
