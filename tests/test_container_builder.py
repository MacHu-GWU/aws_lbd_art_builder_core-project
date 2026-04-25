# -*- coding: utf-8 -*-

import pytest
from pathlib import Path

from aws_lbd_art_builder_core.layer.builder import BasedLambdaLayerContainerBuilder
from aws_lbd_art_builder_core.constants import LayerBuildToolEnum


@pytest.fixture
def builder_x86(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname='test'\nversion='0.1.0'\n")
    script = tmp_path / "build_script.py"
    script.write_text("# build script")
    return BasedLambdaLayerContainerBuilder(
        path_pyproject_toml=pyproject,
        py_ver_major=3,
        py_ver_minor=12,
        is_arm=False,
        path_script=script,
    )


@pytest.fixture
def builder_arm(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\nname='test'\nversion='0.1.0'\n")
    script = tmp_path / "build_script.py"
    script.write_text("# build script")
    return BasedLambdaLayerContainerBuilder(
        path_pyproject_toml=pyproject,
        py_ver_major=3,
        py_ver_minor=12,
        is_arm=True,
        path_script=script,
    )


class TestContainerBuilderProperties:
    def test_image_tag_x86(self, builder_x86):
        assert builder_x86.image_tag == "latest-x86_64"

    def test_image_tag_arm(self, builder_arm):
        assert builder_arm.image_tag == "latest-arm64"

    def test_image_uri_x86(self, builder_x86):
        assert builder_x86.image_uri == (
            "public.ecr.aws/sam/build-python3.12:latest-x86_64"
        )

    def test_image_uri_arm(self, builder_arm):
        assert builder_arm.image_uri == (
            "public.ecr.aws/sam/build-python3.12:latest-arm64"
        )

    def test_platform_x86(self, builder_x86):
        assert builder_x86.platform == "linux/amd64"

    def test_platform_arm(self, builder_arm):
        assert builder_arm.platform == "linux/arm64"

    def test_container_name_x86(self, builder_x86):
        assert builder_x86.container_name == "lambda_layer_builder-python312-amd64"

    def test_container_name_arm(self, builder_arm):
        assert builder_arm.container_name == "lambda_layer_builder-python312-arm64"

    def test_docker_run_args_structure(self, builder_x86):
        args = builder_x86.docker_run_args
        assert args[0] == "docker"
        assert args[1] == "run"
        assert "--rm" in args
        assert "--platform" in args
        assert "linux/amd64" in args
        assert builder_x86.image_uri in args
        assert "python" in args
        assert "-u" in args

    def test_docker_run_args_mount_uses_project_root(self, builder_x86):
        args = builder_x86.docker_run_args
        mount_idx = args.index("--mount") + 1
        mount_val = args[mount_idx]
        assert "type=bind" in mount_val
        assert "/var/task" in mount_val
        assert str(builder_x86.path_layout.dir_project_root) in mount_val


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.builder",
        preview=False,
    )
