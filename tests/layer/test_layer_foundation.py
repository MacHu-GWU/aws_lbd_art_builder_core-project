# -*- coding: utf-8 -*-

"""
Tests for layer foundation module: Credentials, LayerPathLayout, LayerS3Layout,
BaseLogger, LayerManifestManager.
"""

from aws_lbd_art_builder_core.layer.foundation import Credentials
from aws_lbd_art_builder_core.layer.foundation import LayerPathLayout
from aws_lbd_art_builder_core.layer.foundation import BaseLogger
from aws_lbd_art_builder_core.layer.foundation import LayerManifestManager

import os
import json
import hashlib
from pathlib import Path

import pytest

s3pathlib = pytest.importorskip("s3pathlib")

from s3pathlib import S3Path

from aws_lbd_art_builder_core.layer.foundation import LayerS3Layout


# ---------------------------------------------------------------------------
# Tests: Credentials
# ---------------------------------------------------------------------------
class TestCredentials:
    def setup_method(self):
        self.cred = Credentials(
            index_name="my-private-repo",
            index_url="https://my-private-repo.example.com/simple/",
            username="user1",
            password="pass123",
        )

    def test_frozen(self):
        with pytest.raises(AttributeError):
            self.cred.index_name = "other"

    def test_normalized_index_url_strips_scheme_and_trailing(self):
        assert self.cred.normalized_index_url == "my-private-repo.example.com"

    def test_normalized_index_url_no_scheme(self):
        cred = Credentials(
            index_name="x",
            index_url="my-host.com/simple/",
            username="u",
            password="p",
        )
        assert cred.normalized_index_url == "my-host.com"

    def test_normalized_index_url_trailing_slash_only(self):
        cred = Credentials(
            index_name="x",
            index_url="https://host.com/",
            username="u",
            password="p",
        )
        assert cred.normalized_index_url == "host.com"

    def test_uppercase_index_name(self):
        assert self.cred.uppercase_index_name == "MY_PRIVATE_REPO"

    def test_pip_extra_index_url(self):
        url = self.cred.pip_extra_index_url
        assert url.startswith("https://user1:pass123@")
        assert url.endswith("/simple/")

    def test_additional_pip_install_args_index_url(self):
        args = self.cred.additional_pip_install_args_index_url
        assert args[0] == "--index-url"
        assert args[1] == self.cred.pip_extra_index_url

    def test_additional_pip_install_args_extra_index_url(self):
        args = self.cred.additional_pip_install_args_extra_index_url
        assert args[0] == "--extra-index-url"
        assert args[1] == self.cred.pip_extra_index_url

    def test_dump_and_load(self, tmp_path):
        p = tmp_path / "creds.json"
        self.cred.dump(p)
        loaded = Credentials.load(p)
        assert loaded.index_name == self.cred.index_name
        assert loaded.index_url == self.cred.index_url
        assert loaded.username == self.cred.username
        assert loaded.password == self.cred.password

    def test_dump_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "nested" / "dir" / "creds.json"
        self.cred.dump(p)
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["index_name"] == "my-private-repo"

    def test_poetry_login_sets_env_vars(self):
        key_user, key_pass = self.cred.poetry_login()
        assert key_user == "POETRY_HTTP_BASIC_MY_PRIVATE_REPO_USERNAME"
        assert key_pass == "POETRY_HTTP_BASIC_MY_PRIVATE_REPO_PASSWORD"
        assert os.environ[key_user] == "aws"
        assert os.environ[key_pass] == "pass123"
        # cleanup
        del os.environ[key_user]
        del os.environ[key_pass]

    def test_uv_login_sets_env_vars(self):
        key_user, key_pass = self.cred.uv_login()
        assert key_user == "UV_INDEX_MY_PRIVATE_REPO_USERNAME"
        assert key_pass == "UV_INDEX_MY_PRIVATE_REPO_PASSWORD"
        assert os.environ[key_user] == "aws"
        assert os.environ[key_pass] == "pass123"
        # cleanup
        del os.environ[key_user]
        del os.environ[key_pass]


# ---------------------------------------------------------------------------
# Tests: LayerPathLayout
# ---------------------------------------------------------------------------
class TestLayerPathLayout:
    """
    LayerPathLayout manages local directory conventions for layer builds.
    All paths derive from path_pyproject_toml.
    """

    def setup_method(self):
        self.path_pyproject_toml = Path("/project/pyproject.toml")
        self.layout = LayerPathLayout(path_pyproject_toml=self.path_pyproject_toml)

    def test_dir_project_root(self):
        assert self.layout.dir_project_root == Path("/project")

    def test_dir_venv(self):
        assert self.layout.dir_venv == Path("/project/.venv")

    def test_path_venv_bin_python(self):
        assert self.layout.path_venv_bin_python == Path("/project/.venv/bin/python")

    def test_dir_build_lambda(self):
        assert self.layout.dir_build_lambda == Path("/project/build/lambda")

    def test_dir_build_lambda_layer(self):
        assert self.layout.dir_build_lambda_layer == Path("/project/build/lambda/layer")

    def test_path_build_lambda_layer_zip(self):
        assert self.layout.path_build_lambda_layer_zip == Path(
            "/project/build/lambda/layer/layer.zip"
        )

    def test_dir_repo(self):
        assert self.layout.dir_repo == Path("/project/build/lambda/layer/repo")

    def test_path_tmp_pyproject_toml(self):
        assert self.layout.path_tmp_pyproject_toml == Path(
            "/project/build/lambda/layer/repo/pyproject.toml"
        )

    def test_dir_artifacts(self):
        assert self.layout.dir_artifacts == Path(
            "/project/build/lambda/layer/artifacts"
        )

    def test_dir_python(self):
        assert self.layout.dir_python == Path(
            "/project/build/lambda/layer/artifacts/python"
        )

    def test_path_build_lambda_layer_in_container_script_in_local(self):
        assert self.layout.path_build_lambda_layer_in_container_script_in_local == Path(
            "/project/build/lambda/layer/build_lambda_layer_in_container.py"
        )

    def test_path_build_lambda_layer_in_container_script_in_container(self):
        assert (
            self.layout.path_build_lambda_layer_in_container_script_in_container
            == "/var/task/build_lambda_layer_in_container.py"
        )

    def test_path_private_repository_credentials_in_local(self):
        assert self.layout.path_private_repository_credentials_in_local == Path(
            "/project/build/lambda/layer/private-repository-credentials.json"
        )

    def test_path_private_repository_credentials_in_container(self):
        assert (
            self.layout.path_private_repository_credentials_in_container
            == "/var/task/private-repository-credentials.json"
        )

    def test_get_path_in_container(self):
        local_path = Path("/project/build/lambda/layer/repo/pyproject.toml")
        container_path = self.layout.get_path_in_container(local_path)
        assert container_path == "/var/task/repo/pyproject.toml"

    def test_layer_zip_sits_at_dir_build_lambda_layer(self):
        """layer.zip must be a direct child of dir_build_lambda_layer."""
        assert (
            self.layout.path_build_lambda_layer_zip.parent
            == self.layout.dir_build_lambda_layer
        )

    def test_frozen(self):
        with pytest.raises((AttributeError, TypeError)):
            self.layout.path_pyproject_toml = Path("/other/pyproject.toml")

    def test_venv_python_version(self):
        """Use the real project venv to test venv_python_version."""
        dir_project_root = Path(__file__).parent.parent.parent.resolve()
        layout = LayerPathLayout(
            path_pyproject_toml=dir_project_root / "pyproject.toml",
        )
        major, minor, micro = layout.venv_python_version
        assert major >= 3
        assert minor >= 0
        assert micro >= 0

    def test_dir_build_lambda_layer_repo_venv_site_packages(self):
        """Uses the real project venv to derive the site-packages path."""
        dir_project_root = Path(__file__).parent.parent.parent.resolve()
        layout = LayerPathLayout(
            path_pyproject_toml=dir_project_root / "pyproject.toml",
        )
        site_packages = layout.dir_build_lambda_layer_repo_venv_site_packages
        major, minor, _ = layout.venv_python_version
        assert f"python{major}.{minor}" in str(site_packages)
        assert str(site_packages).endswith("site-packages")
        assert site_packages.is_relative_to(layout.dir_repo)

    def test_clean_removes_build_dir(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        layout = LayerPathLayout(path_pyproject_toml=pyproject)
        layout.mkdirs()
        assert layout.dir_build_lambda_layer.exists()
        layout.clean(skip_prompt=True)
        assert not layout.dir_build_lambda_layer.exists()

    def test_clean_noop_when_dir_not_exists(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        layout = LayerPathLayout(path_pyproject_toml=pyproject)
        # should not raise even if dir doesn't exist
        layout.clean(skip_prompt=True)

    def test_mkdirs(self, tmp_path):
        layout = LayerPathLayout(path_pyproject_toml=tmp_path / "pyproject.toml")
        layout.mkdirs()
        assert layout.dir_repo.exists()
        assert layout.dir_python.exists()

    def test_copy_file(self, tmp_path):
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("hello")
        messages = []
        layout = LayerPathLayout(path_pyproject_toml=tmp_path / "pyproject.toml")
        layout.copy_file(p_src=src, p_dst=dst, printer=messages.append)
        assert dst.read_text() == "hello"
        assert len(messages) == 1

    def test_copy_pyproject_toml(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'")
        layout = LayerPathLayout(path_pyproject_toml=pyproject)
        layout.mkdirs()
        messages = []
        layout.copy_pyproject_toml(printer=messages.append)
        assert layout.path_tmp_pyproject_toml.read_text() == "[project]\nname = 'test'"

    def test_copy_build_script(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        script_src = tmp_path / "my_script.py"
        script_src.write_text("print('hello')")
        layout = LayerPathLayout(path_pyproject_toml=pyproject)
        layout.dir_build_lambda_layer.mkdir(parents=True, exist_ok=True)
        messages = []
        layout.copy_build_script(p_src=script_src, printer=messages.append)
        assert layout.path_build_lambda_layer_in_container_script_in_local.read_text() == "print('hello')"


# ---------------------------------------------------------------------------
# Tests: LayerS3Layout
# ---------------------------------------------------------------------------
class TestLayerS3Layout:
    """
    LayerS3Layout manages S3 paths for Lambda layer artifacts.
    It is generic and does not assume any specific build tool.
    """

    def setup_method(self):
        self.s3dir_lambda = S3Path("my-bucket/lambda/my-func/")
        self.layout = LayerS3Layout(s3dir_lambda=self.s3dir_lambda)

    def test_s3path_temp_layer_zip(self):
        assert (
            self.layout.s3path_temp_layer_zip.uri
            == "s3://my-bucket/lambda/my-func/layer/layer.zip"
        )

    def test_s3path_temp_layer_zip_basename(self):
        assert self.layout.s3path_temp_layer_zip.basename == "layer.zip"

    def test_get_s3dir_layer_version(self):
        s3dir = self.layout.get_s3dir_layer_version(1)
        assert s3dir.uri == "s3://my-bucket/lambda/my-func/layer/000001/"

    def test_get_s3dir_layer_version_zero_padding(self):
        s3dir = self.layout.get_s3dir_layer_version(42)
        assert "000042" in s3dir.uri

    def test_get_s3path_layer_manifest_requirements_txt(self):
        s3path = self.layout.get_s3path_layer_manifest(1, "requirements.txt")
        assert s3path.uri == "s3://my-bucket/lambda/my-func/layer/000001/requirements.txt"

    def test_get_s3path_layer_manifest_uv_lock(self):
        s3path = self.layout.get_s3path_layer_manifest(2, "uv.lock")
        assert s3path.uri == "s3://my-bucket/lambda/my-func/layer/000002/uv.lock"

    def test_get_s3path_layer_manifest_poetry_lock(self):
        s3path = self.layout.get_s3path_layer_manifest(3, "poetry.lock")
        assert s3path.uri == "s3://my-bucket/lambda/my-func/layer/000003/poetry.lock"

    def test_different_versions_produce_different_paths(self):
        p1 = self.layout.get_s3path_layer_manifest(1, "uv.lock")
        p2 = self.layout.get_s3path_layer_manifest(2, "uv.lock")
        assert p1.uri != p2.uri

    def test_different_manifests_produce_different_paths(self):
        p1 = self.layout.get_s3path_layer_manifest(1, "uv.lock")
        p2 = self.layout.get_s3path_layer_manifest(1, "requirements.txt")
        assert p1.uri != p2.uri


# ---------------------------------------------------------------------------
# Tests: BaseLogger
# ---------------------------------------------------------------------------
class TestBaseLogger:
    def test_log_verbose_true(self):
        messages = []
        logger = BaseLogger(verbose=True, printer=messages.append)
        logger.log("hello")
        assert messages == ["hello"]

    def test_log_verbose_false(self):
        messages = []
        logger = BaseLogger(verbose=False, printer=messages.append)
        logger.log("hello")
        assert messages == []

    def test_frozen(self):
        logger = BaseLogger()
        with pytest.raises((AttributeError, TypeError)):
            logger.verbose = False


# ---------------------------------------------------------------------------
# Tests: LayerManifestManager
# ---------------------------------------------------------------------------
class TestLayerManifestManager:
    def setup_method(self):
        self.s3dir_lambda = S3Path("my-bucket/lambda/my-func/")

    def test_path_layout(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        manifest = tmp_path / "uv.lock"
        manifest.write_text("some content")
        mgr = LayerManifestManager(
            path_pyproject_toml=pyproject,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=manifest,
            s3_client=None,
        )
        assert mgr.path_layout.dir_project_root == tmp_path

    def test_s3_layout(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        manifest = tmp_path / "uv.lock"
        manifest.write_text("some content")
        mgr = LayerManifestManager(
            path_pyproject_toml=pyproject,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=manifest,
            s3_client=None,
        )
        assert (
            mgr.s3_layout.s3path_temp_layer_zip.uri
            == "s3://my-bucket/lambda/my-func/layer/layer.zip"
        )

    def test_manifest_md5(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        manifest = tmp_path / "uv.lock"
        content = b"some lock content"
        manifest.write_bytes(content)
        mgr = LayerManifestManager(
            path_pyproject_toml=pyproject,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=manifest,
            s3_client=None,
        )
        expected_md5 = hashlib.md5(content).hexdigest()
        assert mgr.manifest_md5 == expected_md5

    def test_get_versioned_manifest(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        manifest = tmp_path / "uv.lock"
        manifest.write_text("content")
        mgr = LayerManifestManager(
            path_pyproject_toml=pyproject,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=manifest,
            s3_client=None,
        )
        s3path = mgr.get_versioned_manifest(version=5)
        assert s3path.uri == "s3://my-bucket/lambda/my-func/layer/000005/uv.lock"

    def test_get_versioned_manifest_with_requirements_txt(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        manifest = tmp_path / "requirements.txt"
        manifest.write_text("boto3==1.0.0")
        mgr = LayerManifestManager(
            path_pyproject_toml=pyproject,
            s3dir_lambda=self.s3dir_lambda,
            path_manifest=manifest,
            s3_client=None,
        )
        s3path = mgr.get_versioned_manifest(version=1)
        assert s3path.uri == "s3://my-bucket/lambda/my-func/layer/000001/requirements.txt"


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.foundation",
        preview=False,
    )
