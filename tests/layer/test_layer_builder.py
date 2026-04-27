# -*- coding: utf-8 -*-

"""
Tests for layer builder module: BaseLambdaLayerContainerBuilder.

Strategy: since this is an abstract base whose real build logic lives in
downstream packages, we test computed properties — image_uri, platform,
container_name, docker_run_args, path_layout.
"""

import pytest

from aws_lbd_art_builder_core.layer.builder import BaseLambdaLayerContainerBuilder


class TestBaseLambdaLayerContainerBuilder:

    def _make_builder(self, tmp_path, is_arm=False, **kwargs):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        defaults = dict(
            path_pyproject_toml=pyproject,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=is_arm,
            verbose=False,
        )
        defaults.update(kwargs)
        return BaseLambdaLayerContainerBuilder(**defaults)

    # --- computed properties ---
    def test_image_tag_x86(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=False)
        assert builder.image_tag == "latest-x86_64"

    def test_image_tag_arm(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=True)
        assert builder.image_tag == "latest-arm64"

    def test_image_uri_x86(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=False)
        assert builder.image_uri == "public.ecr.aws/sam/build-python3.12:latest-x86_64"

    def test_image_uri_arm(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=True)
        assert builder.image_uri == "public.ecr.aws/sam/build-python3.12:latest-arm64"

    def test_platform_x86(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=False)
        assert builder.platform == "linux/amd64"

    def test_platform_arm(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=True)
        assert builder.platform == "linux/arm64"

    def test_container_name_x86(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=False)
        assert builder.container_name == "lambda_layer_builder-python312-amd64"

    def test_container_name_arm(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=True)
        assert builder.container_name == "lambda_layer_builder-python312-arm64"

    def test_docker_run_args_structure(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=False)
        args = builder.docker_run_args
        assert args[0] == "docker"
        assert args[1] == "run"
        assert "--rm" in args
        assert "--name" in args
        assert "--platform" in args
        assert "linux/amd64" in args
        assert "--mount" in args
        assert builder.image_uri in args
        assert "python" in args
        assert "-u" in args

    def test_docker_run_args_mount_binds_project_root(self, tmp_path):
        builder = self._make_builder(tmp_path, is_arm=False)
        args = builder.docker_run_args
        mount_arg = [a for a in args if a.startswith("type=bind")][0]
        assert f"source={tmp_path}" in mount_arg
        assert "target=/var/task" in mount_arg

    def test_path_layout_is_created(self, tmp_path):
        builder = self._make_builder(tmp_path)
        assert builder.path_layout.dir_project_root == tmp_path

    def test_frozen(self, tmp_path):
        builder = self._make_builder(tmp_path)
        with pytest.raises((AttributeError, TypeError)):
            builder.is_arm = True


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.builder",
        preview=False,
    )
