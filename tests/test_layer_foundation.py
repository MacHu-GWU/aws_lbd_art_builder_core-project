# -*- coding: utf-8 -*-

import pytest
import tempfile
from pathlib import Path

from aws_lbd_art_builder_core.constants import LayerBuildToolEnum
from aws_lbd_art_builder_core.layer.foundation import LayerPathLayout

s3pathlib = pytest.importorskip("s3pathlib")

from s3pathlib import S3Path
from aws_lbd_art_builder_core.layer.foundation import LayerS3Layout


@pytest.fixture
def tmp_pyproject_toml(tmp_path):
    p = tmp_path / "pyproject.toml"
    p.write_text("[project]\nname = 'test'\nversion = '0.1.0'\n")
    return p


class TestLayerPathLayout:
    def test_dir_project_root(self, tmp_pyproject_toml):
        layout = LayerPathLayout(path_pyproject_toml=tmp_pyproject_toml)
        assert layout.dir_project_root == tmp_pyproject_toml.parent

    def test_build_paths(self, tmp_pyproject_toml):
        layout = LayerPathLayout(path_pyproject_toml=tmp_pyproject_toml)
        root = tmp_pyproject_toml.parent

        assert layout.dir_build_lambda == root / "build" / "lambda"
        assert layout.dir_build_lambda_layer == root / "build" / "lambda" / "layer"
        assert layout.path_build_lambda_layer_zip == root / "build" / "lambda" / "layer" / "layer.zip"
        assert layout.dir_repo == root / "build" / "lambda" / "layer" / "repo"
        assert layout.dir_artifacts == root / "build" / "lambda" / "layer" / "artifacts"
        assert layout.dir_python == root / "build" / "lambda" / "layer" / "artifacts" / "python"

    def test_manifest_paths(self, tmp_pyproject_toml):
        layout = LayerPathLayout(path_pyproject_toml=tmp_pyproject_toml)
        root = tmp_pyproject_toml.parent

        assert layout.get_path_manifest(LayerBuildToolEnum.pip) == root / "requirements.txt"
        assert layout.get_path_manifest(LayerBuildToolEnum.poetry) == root / "poetry.lock"
        assert layout.get_path_manifest(LayerBuildToolEnum.uv) == root / "uv.lock"

    def test_get_path_manifest_invalid_tool(self, tmp_pyproject_toml):
        layout = LayerPathLayout(path_pyproject_toml=tmp_pyproject_toml)
        with pytest.raises(ValueError):
            layout.get_path_manifest("invalid_tool")

    def test_get_path_in_container(self, tmp_pyproject_toml):
        layout = LayerPathLayout(path_pyproject_toml=tmp_pyproject_toml)
        root = tmp_pyproject_toml.parent

        local_path = root / "build" / "script.py"
        container_path = layout.get_path_in_container(local_path)
        assert container_path == "/var/task/build/script.py"

    def test_credential_and_lock_paths(self, tmp_pyproject_toml):
        layout = LayerPathLayout(path_pyproject_toml=tmp_pyproject_toml)
        root = tmp_pyproject_toml.parent

        assert layout.path_requirements_txt == root / "requirements.txt"
        assert layout.path_poetry_lock == root / "poetry.lock"
        assert layout.path_uv_lock == root / "uv.lock"
        assert layout.path_private_repository_credentials_in_local == (
            root / "build" / "lambda" / "private-repository-credentials.json"
        )


class TestLayerS3Layout:
    def test_s3path_temp_layer_zip(self):
        s3dir_lambda = S3Path("my-bucket/lambda/my-func/")
        layout = LayerS3Layout(s3dir_lambda=s3dir_lambda)

        assert layout.s3path_temp_layer_zip.uri == "s3://my-bucket/lambda/my-func/layer/layer.zip"

    def test_get_s3dir_layer_version(self):
        s3dir_lambda = S3Path("my-bucket/lambda/my-func/")
        layout = LayerS3Layout(s3dir_lambda=s3dir_lambda)

        s3dir = layout.get_s3dir_layer_version(layer_version=1)
        assert s3dir.uri == "s3://my-bucket/lambda/my-func/layer/000001/"

        s3dir = layout.get_s3dir_layer_version(layer_version=42)
        assert s3dir.uri == "s3://my-bucket/lambda/my-func/layer/000042/"

    def test_get_s3path_layer_manifest_files(self):
        s3dir_lambda = S3Path("my-bucket/lambda/my-func/")
        layout = LayerS3Layout(s3dir_lambda=s3dir_lambda)

        assert layout.get_s3path_layer_requirements_txt(1).uri == (
            "s3://my-bucket/lambda/my-func/layer/000001/requirements.txt"
        )
        assert layout.get_s3path_layer_poetry_lock(1).uri == (
            "s3://my-bucket/lambda/my-func/layer/000001/poetry.lock"
        )
        assert layout.get_s3path_layer_uv_lock(1).uri == (
            "s3://my-bucket/lambda/my-func/layer/000001/uv.lock"
        )

    def test_last_manifest_paths(self):
        s3dir_lambda = S3Path("my-bucket/lambda/my-func/")
        layout = LayerS3Layout(s3dir_lambda=s3dir_lambda)

        assert layout.s3path_last_requirements_txt.uri == (
            "s3://my-bucket/lambda/my-func/layer/last-requirements.txt"
        )
        assert layout.s3path_last_poetry_lock.uri == (
            "s3://my-bucket/lambda/my-func/layer/last-poetry.lock"
        )
        assert layout.s3path_last_uv_lock.uri == (
            "s3://my-bucket/lambda/my-func/layer/last-uv.lock"
        )


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.foundation",
        preview=False,
    )
