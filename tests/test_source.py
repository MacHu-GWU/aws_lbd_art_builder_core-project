# -*- coding: utf-8 -*-

import pytest

s3pathlib = pytest.importorskip("s3pathlib")

from s3pathlib import S3Path
from aws_lbd_art_builder_core.source import SourceS3Layout


def test_source_s3_layout_get_s3path_source_zip():
    s3dir_lambda = S3Path("my-bucket/lambda/my-func/")
    layout = SourceS3Layout(s3dir_lambda=s3dir_lambda)

    s3path = layout.get_s3path_source_zip(
        source_version="0.1.1",
        source_sha256="abc123",
    )

    assert s3path.bucket == "my-bucket"
    assert s3path.key == "lambda/my-func/source/0.1.1/abc123/source.zip"
    assert s3path.uri == "s3://my-bucket/lambda/my-func/source/0.1.1/abc123/source.zip"

    # Different versions/hashes produce different paths
    s3path_v2 = layout.get_s3path_source_zip(
        source_version="0.1.2",
        source_sha256="def456",
    )
    assert s3path_v2.key == "lambda/my-func/source/0.1.2/def456/source.zip"
    assert s3path_v2.key != s3path.key


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.source",
        preview=False,
    )
