# -*- coding: utf-8 -*-

from aws_lbd_art_builder_core.source import api


def test():
    _ = api
    _ = api.SourcePathLayout
    _ = api.SourceS3Layout
    _ = api.build_source_dir_using_pip
    _ = api.build_source_dir_using_uv
    _ = api.create_source_zip
    _ = api.upload_source_zip
    _ = api.BuildAndUploadSourceResult
    _ = api.build_and_upload_source_using_pip
    _ = api.build_and_upload_source_using_uv


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.source.api",
        preview=False,
    )
