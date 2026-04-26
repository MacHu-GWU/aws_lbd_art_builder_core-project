# -*- coding: utf-8 -*-

from aws_lbd_art_builder_core.layer import api


def test():
    _ = api
    _ = api.Credentials
    _ = api.LayerPathLayout
    _ = api.LayerS3Layout
    _ = api.BaseLogger
    _ = api.LayerManifestManager
    _ = api.BaseLambdaLayerLocalBuilder
    _ = api.BaseLambdaLayerContainerBuilder
    _ = api.move_to_dir_python
    _ = api.default_ignore_package_list
    _ = api.create_layer_zip_file
    _ = api.upload_layer_zip_to_s3
    _ = api.LambdaLayerVersionPublisher
    _ = api.LayerDeployment


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.api",
        preview=False,
    )
