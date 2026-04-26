# -*- coding: utf-8 -*-

"""
Tests for layer builder module: BaseLambdaLayerLocalBuilder,
BaseLambdaLayerContainerBuilder.

Strategy: since these are abstract bases whose real build logic lives in
downstream packages, we test:

1. Orchestration order — ``run()`` calls steps 1→2→3→4 in sequence.
2. Computed properties — image_uri, platform, container_name, docker_run_args.
3. Side effects of steps that *do* run in the base — setup_build_dir,
   copy_build_script, setup_private_repository_credential.
4. We do NOT invoke ``step_3_1_docker_run`` (subprocess.run docker) in tests.
"""

from aws_lbd_art_builder_core.layer.builder import BaseLambdaLayerLocalBuilder
from aws_lbd_art_builder_core.layer.builder import BaseLambdaLayerContainerBuilder

import json
from unittest.mock import patch

import pytest

from aws_lbd_art_builder_core.layer.foundation import Credentials


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class FakeLocalBuilder(BaseLambdaLayerLocalBuilder):
    """Records which steps were called, in order."""

    def __init_post_init__(self):
        object.__setattr__(self, "_call_log", [])

    def step_1_preflight_check(self):
        self._call_log.append("step_1")
        super().step_1_preflight_check()

    def step_2_prepare_environment(self):
        self._call_log.append("step_2")
        super().step_2_prepare_environment()

    def step_3_execute_build(self):
        self._call_log.append("step_3")
        super().step_3_execute_build()

    def step_4_finalize_artifacts(self):
        self._call_log.append("step_4")
        super().step_4_finalize_artifacts()


class FakeContainerBuilder(BaseLambdaLayerContainerBuilder):
    """Records which steps were called, in order."""

    def __init_post_init__(self):
        object.__setattr__(self, "_call_log", [])

    def step_1_preflight_check(self):
        self._call_log.append("step_1")
        super().step_1_preflight_check()

    def step_2_prepare_environment(self):
        self._call_log.append("step_2")
        super().step_2_prepare_environment()

    def step_3_execute_build(self):
        self._call_log.append("step_3")
        # do NOT call super — that would try to run docker

    def step_4_finalize_artifacts(self):
        self._call_log.append("step_4")
        super().step_4_finalize_artifacts()


# ---------------------------------------------------------------------------
# Tests: BaseLambdaLayerLocalBuilder
# ---------------------------------------------------------------------------
class TestBaseLambdaLayerLocalBuilder:

    def test_run_executes_steps_in_order(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        builder = FakeLocalBuilder(
            path_pyproject_toml=pyproject,
            skip_prompt=True,
            verbose=False,
        )
        object.__setattr__(builder, "_call_log", [])
        builder.run()
        assert builder._call_log == ["step_1", "step_2", "step_3", "step_4"]

    def test_path_layout_is_created(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        builder = BaseLambdaLayerLocalBuilder(
            path_pyproject_toml=pyproject,
            verbose=False,
        )
        assert builder.path_layout.dir_project_root == tmp_path

    def test_step_1_1_print_info(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        messages = []
        builder = BaseLambdaLayerLocalBuilder(
            path_pyproject_toml=pyproject,
            verbose=True,
            printer=messages.append,
        )
        builder.step_1_1_print_info()
        text = "\n".join(messages)
        assert "path_pyproject_toml" in text
        assert "dir_build_lambda_layer" in text

    def test_step_2_1_setup_build_dir_creates_dirs(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        builder = BaseLambdaLayerLocalBuilder(
            path_pyproject_toml=pyproject,
            skip_prompt=True,
            verbose=False,
        )
        builder.step_2_1_setup_build_dir()
        assert builder.path_layout.dir_repo.exists()
        assert builder.path_layout.dir_python.exists()

    def test_step_2_1_setup_build_dir_cleans_existing(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        builder = BaseLambdaLayerLocalBuilder(
            path_pyproject_toml=pyproject,
            skip_prompt=True,
            verbose=False,
        )
        # create a stale file
        builder.path_layout.dir_build_lambda_layer.mkdir(parents=True)
        stale = builder.path_layout.dir_build_lambda_layer / "stale.txt"
        stale.write_text("old")
        # run setup — should clean and recreate
        builder.step_2_1_setup_build_dir()
        assert not stale.exists()
        assert builder.path_layout.dir_repo.exists()

    def test_credentials_default_none(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        builder = BaseLambdaLayerLocalBuilder(
            path_pyproject_toml=pyproject,
            verbose=False,
        )
        assert builder.credentials is None

    def test_frozen(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        builder = BaseLambdaLayerLocalBuilder(
            path_pyproject_toml=pyproject,
            verbose=False,
        )
        with pytest.raises((AttributeError, TypeError)):
            builder.skip_prompt = True


# ---------------------------------------------------------------------------
# Tests: BaseLambdaLayerContainerBuilder
# ---------------------------------------------------------------------------
class TestBaseLambdaLayerContainerBuilder:

    def _make_builder(self, tmp_path, is_arm=False, **kwargs):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        script = tmp_path / "build_script.py"
        script.write_text("print('build')")
        defaults = dict(
            path_pyproject_toml=pyproject,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=is_arm,
            path_script=script,
            verbose=False,
        )
        defaults.update(kwargs)
        return BaseLambdaLayerContainerBuilder(**defaults)

    def test_run_executes_steps_in_order(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        script = tmp_path / "build_script.py"
        script.write_text("print('build')")
        builder = FakeContainerBuilder(
            path_pyproject_toml=pyproject,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=False,
            path_script=script,
            verbose=False,
        )
        object.__setattr__(builder, "_call_log", [])
        builder.run()
        assert builder._call_log == ["step_1", "step_2", "step_3", "step_4"]

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

    # --- step_2 sub-steps ---
    def test_step_2_1_copy_build_script(self, tmp_path):
        builder = self._make_builder(tmp_path)
        builder.step_2_1_copy_build_script()
        dst = builder.path_layout.path_build_lambda_layer_in_container_script_in_local
        assert dst.exists()
        assert dst.read_text() == "print('build')"

    def test_step_2_2_setup_credential_with_none(self, tmp_path):
        builder = self._make_builder(tmp_path, credentials=None)
        messages = []
        builder_with_log = BaseLambdaLayerContainerBuilder(
            path_pyproject_toml=builder.path_pyproject_toml,
            py_ver_major=3,
            py_ver_minor=12,
            is_arm=False,
            path_script=builder.path_script,
            credentials=None,
            verbose=True,
            printer=messages.append,
        )
        builder_with_log.step_2_2_setup_private_repository_credential()
        assert any("skip" in m.lower() for m in messages)

    def test_step_2_2_setup_credential_with_credentials(self, tmp_path):
        cred = Credentials(
            index_name="my-repo",
            index_url="https://example.com/simple/",
            username="user",
            password="pass",
        )
        builder = self._make_builder(tmp_path, credentials=cred)
        builder.step_2_2_setup_private_repository_credential()
        cred_path = builder.path_layout.path_private_repository_credentials_in_local
        assert cred_path.exists()
        data = json.loads(cred_path.read_text())
        assert data["index_name"] == "my-repo"
        assert data["username"] == "user"

    def test_step_3_execute_build_calls_docker_run(self, tmp_path):
        builder = self._make_builder(tmp_path)
        with patch("subprocess.run") as mock_run:
            builder.step_3_execute_build()
            mock_run.assert_called_once_with(builder.docker_run_args, check=True)

    def test_step_3_1_docker_run_calls_subprocess(self, tmp_path):
        builder = self._make_builder(tmp_path)
        with patch("subprocess.run") as mock_run:
            builder.step_3_1_docker_run()
            mock_run.assert_called_once_with(builder.docker_run_args, check=True)

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
