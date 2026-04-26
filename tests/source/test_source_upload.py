# -*- coding: utf-8 -*-

"""
Tests for upload functions: upload_source_zip, BuildAndUploadSourceResult.

Uses BaseMockAwsTest so all S3 calls hit moto in-memory rather than real AWS.
The uv build and zip are created once in setup_class_post_hook so the upload
tests run against a real local zip file.

Build output is kept on disk after the run for manual inspection:

    tests/source/build/lambda/source/using_uv/build/   ← uv install target
    tests/source/build/lambda/source/using_uv/source.zip
"""

import shutil
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib

from s3pathlib import S3Path

from aws_lbd_art_builder_core.tests.mock_aws import BaseMockAwsTest
from aws_lbd_art_builder_core.constants import S3MetadataKeyEnum
from aws_lbd_art_builder_core.source.foundation import SourcePathLayout
from aws_lbd_art_builder_core.source.foundation import SourceS3Layout
from aws_lbd_art_builder_core.source.builder import build_source_dir_using_uv
from aws_lbd_art_builder_core.source.builder import create_source_zip
from aws_lbd_art_builder_core.source.upload import upload_source_zip
from aws_lbd_art_builder_core.source.upload import BuildAndUploadSourceResult
from aws_lbd_art_builder_core.source.upload import build_and_upload_source_using_pip
from aws_lbd_art_builder_core.source.upload import build_and_upload_source_using_uv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DIR_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
PATH_PYPROJECT_TOML = DIR_PROJECT_ROOT / "pyproject.toml"
DIR_TESTS = Path(__file__).parent

LAYOUT_UV = SourcePathLayout(
    dir_root=DIR_TESTS / "build" / "lambda" / "source" / "using_uv"
)

# ---------------------------------------------------------------------------
# Tests: upload_source_zip
# ---------------------------------------------------------------------------

class TestUploadSourceZip(BaseMockAwsTest):
    use_mock = True

    BUCKET = "test-lambda-bucket"
    SOURCE_VERSION = "0.1.0"

    s3dir_source: S3Path = None
    source_sha256: str = None

    @classmethod
    def setup_class_post_hook(cls):
        # step 1: build source dir using uv
        path_bin_uv = shutil.which("uv")
        assert path_bin_uv is not None, "uv not found on PATH"
        build_source_dir_using_uv(
            path_bin_uv=Path(path_bin_uv),
            path_pyproject_toml=PATH_PYPROJECT_TOML,
            dir_lambda_source_build=LAYOUT_UV.dir_build,
            skip_prompt=True,
            verbose=True,
        )
        # step 2: create zip and capture sha256
        cls.source_sha256 = create_source_zip(
            dir_lambda_source_build=LAYOUT_UV.dir_build,
            path_source_zip=LAYOUT_UV.path_source_zip,
            verbose=True,
        )
        # step 3: create mock S3 bucket and set up s3dir_source
        cls.create_s3_bucket(cls.BUCKET)
        cls.s3dir_source = S3Path(f"{cls.BUCKET}/lambda/my-func/source/")

    # ------------------------------------------------------------------
    # Return value
    # ------------------------------------------------------------------

    def test_returns_correct_s3path(self):
        s3path = upload_source_zip(
            s3_client=self.s3_client,
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
            path_source_zip=LAYOUT_UV.path_source_zip,
            s3dir_source=self.s3dir_source,
            verbose=False,
        )
        assert s3path.basename == "source.zip"
        expected_key = f"lambda/my-func/source/{self.SOURCE_VERSION}/{self.source_sha256}/source.zip"
        assert s3path.key == expected_key

    # ------------------------------------------------------------------
    # Object existence
    # ------------------------------------------------------------------

    def test_object_exists_in_s3(self):
        s3path = upload_source_zip(
            s3_client=self.s3_client,
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
            path_source_zip=LAYOUT_UV.path_source_zip,
            s3dir_source=self.s3dir_source,
            verbose=False,
        )
        assert s3path.exists(bsm=self.s3_client)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def test_metadata_contains_source_version(self):
        s3path = upload_source_zip(
            s3_client=self.s3_client,
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
            path_source_zip=LAYOUT_UV.path_source_zip,
            s3dir_source=self.s3dir_source,
            verbose=False,
        )
        head = self.s3_client.head_object(Bucket=s3path.bucket, Key=s3path.key)
        metadata = head["Metadata"]
        assert metadata[S3MetadataKeyEnum.source_version] == self.SOURCE_VERSION

    def test_metadata_contains_source_sha256(self):
        s3path = upload_source_zip(
            s3_client=self.s3_client,
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
            path_source_zip=LAYOUT_UV.path_source_zip,
            s3dir_source=self.s3dir_source,
            verbose=False,
        )
        head = self.s3_client.head_object(Bucket=s3path.bucket, Key=s3path.key)
        metadata = head["Metadata"]
        assert metadata[S3MetadataKeyEnum.source_sha256] == self.source_sha256

    def test_custom_metadata_is_merged(self):
        s3path = upload_source_zip(
            s3_client=self.s3_client,
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
            path_source_zip=LAYOUT_UV.path_source_zip,
            s3dir_source=self.s3dir_source,
            metadata={"custom_key": "custom_value"},
            verbose=False,
        )
        head = self.s3_client.head_object(Bucket=s3path.bucket, Key=s3path.key)
        metadata = head["Metadata"]
        assert metadata["custom_key"] == "custom_value"
        # built-in keys must still be present
        assert S3MetadataKeyEnum.source_version in metadata
        assert S3MetadataKeyEnum.source_sha256 in metadata

    # ------------------------------------------------------------------
    # Content type
    # ------------------------------------------------------------------

    def test_content_type_is_zip(self):
        s3path = upload_source_zip(
            s3_client=self.s3_client,
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
            path_source_zip=LAYOUT_UV.path_source_zip,
            s3dir_source=self.s3dir_source,
            verbose=False,
        )
        head = self.s3_client.head_object(Bucket=s3path.bucket, Key=s3path.key)
        assert head["ContentType"] == "application/zip"

    def test_tags_are_set(self):
        s3path = upload_source_zip(
            s3_client=self.s3_client,
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
            path_source_zip=LAYOUT_UV.path_source_zip,
            s3dir_source=self.s3dir_source,
            tags={"env": "test", "team": "infra"},
            verbose=False,
        )
        resp = self.s3_client.get_object_tagging(Bucket=s3path.bucket, Key=s3path.key)
        tag_map = {t["Key"]: t["Value"] for t in resp["TagSet"]}
        assert tag_map["env"] == "test"
        assert tag_map["team"] == "infra"

    # ------------------------------------------------------------------
    # S3 path structure matches SourceS3Layout
    # ------------------------------------------------------------------

    def test_s3path_matches_layout(self):
        """upload_source_zip must place the object exactly where SourceS3Layout says."""
        s3path = upload_source_zip(
            s3_client=self.s3_client,
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
            path_source_zip=LAYOUT_UV.path_source_zip,
            s3dir_source=self.s3dir_source,
            verbose=False,
        )
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        expected = layout.get_s3path_source_zip(
            source_version=self.SOURCE_VERSION,
            source_sha256=self.source_sha256,
        )
        assert s3path.uri == expected.uri


# ---------------------------------------------------------------------------
# Tests: build_and_upload_source_using_pip
# ---------------------------------------------------------------------------

class TestBuildAndUploadSourceUsingPip(BaseMockAwsTest):
    use_mock = True

    BUCKET = "test-lambda-bucket-pip"

    s3dir_source: S3Path = None
    result: BuildAndUploadSourceResult = None

    @classmethod
    def setup_class_post_hook(cls):
        cls.create_s3_bucket(cls.BUCKET)
        cls.s3dir_source = S3Path(f"{cls.BUCKET}/lambda/my-func/source/")
        cls.result = build_and_upload_source_using_pip(
            s3_client=cls.s3_client,
            dir_project_root=DIR_PROJECT_ROOT,
            s3dir_source=cls.s3dir_source,
            skip_prompt=True,
            verbose=False,
        )

    def test_returns_build_and_upload_source_result(self):
        assert isinstance(self.result, BuildAndUploadSourceResult)

    def test_source_sha256_is_64_char_hex(self):
        assert isinstance(self.result.source_sha256, str)
        assert len(self.result.source_sha256) == 64

    def test_s3path_filename_is_source_zip(self):
        assert self.result.s3path_source_zip.basename == "source.zip"

    def test_object_exists_in_s3(self):
        assert self.result.s3path_source_zip.exists(bsm=self.s3_client)

    def test_s3path_contains_version_from_pyproject_toml(self):
        expected_version = tomllib.loads(PATH_PYPROJECT_TOML.read_text())["project"]["version"]
        assert expected_version in self.result.s3path_source_zip.key

    def test_s3path_contains_sha256(self):
        assert self.result.source_sha256 in self.result.s3path_source_zip.key

    def test_s3path_matches_layout(self):
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        expected_version = tomllib.loads(PATH_PYPROJECT_TOML.read_text())["project"]["version"]
        expected = layout.get_s3path_source_zip(
            source_version=expected_version,
            source_sha256=self.result.source_sha256,
        )
        assert self.result.s3path_source_zip.uri == expected.uri


# ---------------------------------------------------------------------------
# Tests: build_and_upload_source_using_uv
# ---------------------------------------------------------------------------

class TestBuildAndUploadSourceUsingUv(BaseMockAwsTest):
    use_mock = True

    BUCKET = "test-lambda-bucket-uv"

    s3dir_source: S3Path = None
    result: BuildAndUploadSourceResult = None

    @classmethod
    def setup_class_post_hook(cls):
        path_bin_uv = shutil.which("uv")
        assert path_bin_uv is not None, "uv not found on PATH"
        cls.create_s3_bucket(cls.BUCKET)
        cls.s3dir_source = S3Path(f"{cls.BUCKET}/lambda/my-func/source/")
        cls.result = build_and_upload_source_using_uv(
            s3_client=cls.s3_client,
            path_bin_uv=Path(path_bin_uv),
            dir_project_root=DIR_PROJECT_ROOT,
            s3dir_source=cls.s3dir_source,
            skip_prompt=True,
            verbose=False,
        )

    def test_returns_build_and_upload_source_result(self):
        assert isinstance(self.result, BuildAndUploadSourceResult)

    def test_source_sha256_is_64_char_hex(self):
        assert isinstance(self.result.source_sha256, str)
        assert len(self.result.source_sha256) == 64

    def test_s3path_filename_is_source_zip(self):
        assert self.result.s3path_source_zip.basename == "source.zip"

    def test_object_exists_in_s3(self):
        assert self.result.s3path_source_zip.exists(bsm=self.s3_client)

    def test_s3path_contains_version_from_pyproject_toml(self):
        expected_version = tomllib.loads(PATH_PYPROJECT_TOML.read_text())["project"]["version"]
        assert expected_version in self.result.s3path_source_zip.key

    def test_s3path_contains_sha256(self):
        assert self.result.source_sha256 in self.result.s3path_source_zip.key

    def test_s3path_matches_layout(self):
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        expected_version = tomllib.loads(PATH_PYPROJECT_TOML.read_text())["project"]["version"]
        expected = layout.get_s3path_source_zip(
            source_version=expected_version,
            source_sha256=self.result.source_sha256,
        )
        assert self.result.s3path_source_zip.uri == expected.uri


# ---------------------------------------------------------------------------
# Tests: BuildAndUploadSourceResult
# ---------------------------------------------------------------------------

class TestBuildAndUploadSourceResult:
    def test_fields(self):
        s3path = S3Path("my-bucket/lambda/source/0.1.0/abc123/source.zip")
        result = BuildAndUploadSourceResult(
            source_sha256="abc123",
            s3path_source_zip=s3path,
        )
        assert result.source_sha256 == "abc123"
        assert result.s3path_source_zip.basename == "source.zip"
        assert result.s3path_source_zip.key == "lambda/source/0.1.0/abc123/source.zip"


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.source.upload",
        preview=False,
    )
