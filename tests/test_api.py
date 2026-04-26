# -*- coding: utf-8 -*-

from aws_lbd_art_builder_core import api


def test():
    _ = api
    _ = api.ZFILL
    _ = api.S3MetadataKeyEnum
    _ = api.LayerBuildToolEnum
    _ = api.T_PRINTER
    _ = api.ensure_exact_one_true
    _ = api.write_bytes
    _ = api.is_match
    _ = api.normalize_glob_patterns
    _ = api.copy_source_for_lambda_deployment
    _ = api.prompt_to_confirm_before_remove_dir
    _ = api.clean_build_directory
    _ = api.source_api
    _ = api.layer_api
    _ = api.temp_cwd
    _ = api.hashes
    _ = api.DateTimeTimer


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.api",
        preview=False,
    )
