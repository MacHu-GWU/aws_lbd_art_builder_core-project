# -*- coding: utf-8 -*-

import os
import pytest
from aws_lbd_art_builder_core.layer.foundation import Credentials


@pytest.fixture
def creds():
    return Credentials(
        index_name="my-private-repo",
        index_url="https://my-domain.codeartifact.us-east-1.amazonaws.com/pypi/my-repo/simple/",
        username="aws",
        password="secret-token",
    )


class TestCredentialsNormalization:
    def test_normalized_index_url_strips_https(self, creds):
        assert creds.normalized_index_url == (
            "my-domain.codeartifact.us-east-1.amazonaws.com/pypi/my-repo"
        )

    def test_normalized_index_url_strips_simple_suffix(self):
        c = Credentials(
            index_name="repo",
            index_url="https://example.com/simple",
            username="u",
            password="p",
        )
        assert c.normalized_index_url == "example.com"

    def test_normalized_index_url_strips_trailing_slash(self):
        c = Credentials(
            index_name="repo",
            index_url="https://example.com/",
            username="u",
            password="p",
        )
        assert c.normalized_index_url == "example.com"

    def test_normalized_index_url_no_https(self):
        c = Credentials(
            index_name="repo",
            index_url="example.com/pypi/repo",
            username="u",
            password="p",
        )
        assert c.normalized_index_url == "example.com/pypi/repo"

    def test_uppercase_index_name_replaces_dash(self, creds):
        assert creds.uppercase_index_name == "MY_PRIVATE_REPO"

    def test_uppercase_index_name_already_underscored(self):
        c = Credentials(
            index_name="my_repo",
            index_url="https://example.com",
            username="u",
            password="p",
        )
        assert c.uppercase_index_name == "MY_REPO"


class TestCredentialsPipArgs:
    def test_pip_extra_index_url(self, creds):
        url = creds.pip_extra_index_url
        assert url.startswith("https://aws:secret-token@")
        assert url.endswith("/simple/")
        assert "my-domain.codeartifact.us-east-1.amazonaws.com" in url

    def test_additional_pip_install_args_index_url(self, creds):
        args = creds.additional_pip_install_args_index_url
        assert args[0] == "--index-url"
        assert args[1] == creds.pip_extra_index_url

    def test_additional_pip_install_args_extra_index_url(self, creds):
        args = creds.additional_pip_install_args_extra_index_url
        assert args[0] == "--extra-index-url"
        assert args[1] == creds.pip_extra_index_url


class TestCredentialsDumpLoad:
    def test_dump_and_load_roundtrip(self, tmp_path, creds):
        path = tmp_path / "creds.json"
        creds.dump(path)
        assert path.exists()
        loaded = Credentials.load(path)
        assert loaded == creds

    def test_dump_creates_parent_dirs(self, tmp_path, creds):
        path = tmp_path / "nested" / "dir" / "creds.json"
        creds.dump(path)
        assert path.exists()


class TestCredentialsLogin:
    def test_poetry_login_sets_env_vars(self, creds):
        key_user, key_pass = creds.poetry_login()
        assert key_user == "POETRY_HTTP_BASIC_MY_PRIVATE_REPO_USERNAME"
        assert key_pass == "POETRY_HTTP_BASIC_MY_PRIVATE_REPO_PASSWORD"
        assert os.environ[key_user] == "aws"
        assert os.environ[key_pass] == "secret-token"

    def test_uv_login_sets_env_vars(self, creds):
        key_user, key_pass = creds.uv_login()
        assert key_user == "UV_INDEX_MY_PRIVATE_REPO_USERNAME"
        assert key_pass == "UV_INDEX_MY_PRIVATE_REPO_PASSWORD"
        assert os.environ[key_user] == "aws"
        assert os.environ[key_pass] == "secret-token"


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.foundation",
        preview=False,
    )
