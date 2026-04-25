# -*- coding: utf-8 -*-

from aws_lbd_art_builder_core import api


def test():
    _ = api
    _ = api.ZFILL
    _ = api.S3MetadataKeyEnum
    _ = api.LayerBuildToolEnum
    _ = api.write_bytes
    _ = api.is_match
    _ = api.copy_source_for_lambda_deployment
    _ = api.prompt_to_confirm_before_remove_dir
    _ = api.clean_build_directory
    _ = api.SourcePathLayout
    _ = api.SourceS3Layout
    _ = api.BuildSourceArtifactsResult
    _ = api.build_source_artifacts_using_pip
    _ = api.create_source_zip
    _ = api.upload_source_artifacts
    _ = api.build_package_upload_source_artifacts
    _ = api.Credentials
    _ = api.LayerPathLayout
    _ = api.LayerS3Layout
    _ = api.LayerManifestManager
    _ = api.BasedLambdaLayerLocalBuilder
    _ = api.BasedLambdaLayerContainerBuilder
    _ = api.move_to_dir_python
    _ = api.create_layer_zip_file
    _ = api.LambdaLayerZipper
    _ = api.upload_layer_zip_to_s3
    _ = api.LambdaLayerVersionPublisher
    _ = api.LayerDeployment
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
