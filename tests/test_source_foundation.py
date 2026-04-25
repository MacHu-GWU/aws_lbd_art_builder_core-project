# -*- coding: utf-8 -*-

from pathlib import Path

import pytest

from aws_lbd_art_builder_core.source.foundation import SourcePathLayout
from aws_lbd_art_builder_core.source.foundation import SourceS3Layout

s3pathlib = pytest.importorskip("s3pathlib")

from s3pathlib import S3Path


class TestSourcePathLayout:
    """
    SourcePathLayout wraps the local build directory for Lambda source artifacts.

    dir_root = {dir_project_root}/build/lambda/source

    Everything under dir_root is owned by this layout and can be freely deleted
    before a fresh build.
    """

    def setup_method(self):
        self.dir_root = Path("/project/build/lambda/source")
        self.layout = SourcePathLayout(dir_root=self.dir_root)

    def test_dir_build(self):
        assert self.layout.dir_build == Path("/project/build/lambda/source/build")

    def test_path_source_zip(self):
        assert self.layout.path_source_zip == Path("/project/build/lambda/source/source.zip")

    def test_source_zip_sits_at_dir_root_not_inside_build(self):
        # source.zip must be a direct child of dir_root, not nested inside dir_build.
        # Having it inside dir_build would cause the zip command to capture itself.
        assert self.layout.path_source_zip.parent == self.dir_root
        assert self.layout.dir_build.parent == self.dir_root

    def test_frozen(self):
        with pytest.raises((AttributeError, TypeError)):
            self.layout.dir_root = Path("/other")


class TestSourceS3Layout:
    """
    SourceS3Layout manages S3 paths for Lambda source artifacts.

    dir_root = s3dir_lambda/source/

    Scoping to the source/ sub-prefix means "delete everything under dir_root"
    only ever touches source artifacts and never accidentally hits sibling
    prefixes such as layer/.

    s3dir_lambda is the higher-level anchor shared by all Lambda artifact types.
    Use from_s3dir_lambda() to derive the correctly scoped root from it.
    """

    def setup_method(self):
        self.s3dir_lambda = S3Path("my-bucket/lambda/my-func/")
        self.s3dir_source = S3Path("my-bucket/lambda/my-func/source/")

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_construct_directly(self):
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        assert layout.dir_root.uri == "s3://my-bucket/lambda/my-func/source/"

    def test_construct_from_s3dir_lambda(self):
        layout = SourceS3Layout.from_s3dir_lambda(self.s3dir_lambda)
        assert layout.dir_root.uri == "s3://my-bucket/lambda/my-func/source/"

    def test_both_construction_paths_are_equivalent(self):
        direct = SourceS3Layout(dir_root=self.s3dir_source)
        via_factory = SourceS3Layout.from_s3dir_lambda(self.s3dir_lambda)
        assert direct.dir_root.uri == via_factory.dir_root.uri

    def test_frozen(self):
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        with pytest.raises((AttributeError, TypeError)):
            layout.dir_root = self.s3dir_lambda

    # ------------------------------------------------------------------
    # get_s3path_source_zip
    # ------------------------------------------------------------------

    def test_path_structure(self):
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        s3path = layout.get_s3path_source_zip(
            source_version="0.1.1",
            source_sha256="abc123",
        )
        assert s3path.bucket == "my-bucket"
        assert s3path.key == "lambda/my-func/source/0.1.1/abc123/source.zip"
        assert s3path.uri == "s3://my-bucket/lambda/my-func/source/0.1.1/abc123/source.zip"

    def test_filename_is_source_zip(self):
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        s3path = layout.get_s3path_source_zip("0.1.1", "abc123")
        assert s3path.basename == "source.zip"

    def test_different_versions_produce_different_paths(self):
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        p1 = layout.get_s3path_source_zip("0.1.1", "abc123")
        p2 = layout.get_s3path_source_zip("0.1.2", "def456")
        assert p1.key != p2.key

    def test_same_version_different_sha256_produces_different_paths(self):
        """SHA256 in the S3 key forces CDK/CloudFormation to detect code changes."""
        layout = SourceS3Layout(dir_root=self.s3dir_source)
        p1 = layout.get_s3path_source_zip("0.1.1", "sha_before")
        p2 = layout.get_s3path_source_zip("0.1.1", "sha_after")
        assert p1.key != p2.key

    # ------------------------------------------------------------------
    # Namespace isolation
    # ------------------------------------------------------------------

    def test_dir_root_is_scoped_under_source_prefix(self):
        """
        The layout root must sit inside source/, not at the s3dir_lambda level.
        This guarantees delete operations on dir_root cannot reach layer/ or
        any other sibling prefix.
        """
        layout = SourceS3Layout.from_s3dir_lambda(self.s3dir_lambda)
        # dir_root key starts with the lambda prefix + source/
        assert layout.dir_root.key.startswith("lambda/my-func/source")

    def test_dir_root_is_not_equal_to_s3dir_lambda(self):
        layout = SourceS3Layout.from_s3dir_lambda(self.s3dir_lambda)
        assert layout.dir_root.uri != self.s3dir_lambda.uri


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.source.foundation",
        preview=False,
    )
