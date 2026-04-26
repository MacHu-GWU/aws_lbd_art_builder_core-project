# -*- coding: utf-8 -*-

"""
Tests for layer package module: move_to_dir_python, create_layer_zip_file,
default_ignore_package_list.
"""

from aws_lbd_art_builder_core.layer.package import move_to_dir_python
from aws_lbd_art_builder_core.layer.package import create_layer_zip_file
from aws_lbd_art_builder_core.layer.package import default_ignore_package_list

import zipfile

import pytest


# ---------------------------------------------------------------------------
# Tests: move_to_dir_python
# ---------------------------------------------------------------------------
class TestMoveToDirPython:

    def test_move_site_packages_to_dir_python(self, tmp_path):
        site_packages = tmp_path / "repo" / ".venv" / "lib" / "python3.12" / "site-packages"
        site_packages.mkdir(parents=True)
        (site_packages / "my_pkg").mkdir()
        (site_packages / "my_pkg" / "__init__.py").write_text("# pkg")

        dir_python = tmp_path / "artifacts" / "python"
        dir_python.mkdir(parents=True)

        move_to_dir_python(site_packages, dir_python)

        assert not site_packages.exists()
        assert (dir_python / "my_pkg" / "__init__.py").exists()

    def test_dst_already_has_content_gets_replaced(self, tmp_path):
        site_packages = tmp_path / "site-packages"
        site_packages.mkdir()
        (site_packages / "new_pkg.py").write_text("new")

        dir_python = tmp_path / "python"
        dir_python.mkdir()
        (dir_python / "old_pkg.py").write_text("old")

        move_to_dir_python(site_packages, dir_python)

        assert (dir_python / "new_pkg.py").read_text() == "new"
        assert not (dir_python / "old_pkg.py").exists()

    def test_same_src_and_dst_is_noop(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        (dir_python / "pkg.py").write_text("hello")

        move_to_dir_python(dir_python, dir_python)

        assert (dir_python / "pkg.py").read_text() == "hello"

    def test_raises_when_src_not_exists(self, tmp_path):
        src = tmp_path / "nonexistent"
        dst = tmp_path / "python"
        with pytest.raises(FileNotFoundError, match="not found"):
            move_to_dir_python(src, dst)


# ---------------------------------------------------------------------------
# Tests: create_layer_zip_file
# ---------------------------------------------------------------------------
class TestCreateLayerZipFile:

    def _setup_python_dir(self, tmp_path):
        """Create a fake artifacts/python/ directory with some packages."""
        artifacts = tmp_path / "artifacts"
        dir_python = artifacts / "python"
        dir_python.mkdir(parents=True)

        # real package
        (dir_python / "my_pkg").mkdir()
        (dir_python / "my_pkg" / "__init__.py").write_text("# my_pkg")
        (dir_python / "my_pkg" / "core.py").write_text("x = 1")

        # package that should be ignored by default
        (dir_python / "boto3").mkdir()
        (dir_python / "boto3" / "__init__.py").write_text("# boto3")

        (dir_python / "pytest").mkdir()
        (dir_python / "pytest" / "__init__.py").write_text("# pytest")

        path_layer_zip = tmp_path / "layer.zip"
        return dir_python, path_layer_zip

    def test_zip_file_is_created(self, tmp_path):
        dir_python, path_layer_zip = self._setup_python_dir(tmp_path)
        create_layer_zip_file(dir_python, path_layer_zip, verbose=False)
        assert path_layer_zip.exists()

    def test_zip_entries_start_with_python(self, tmp_path):
        dir_python, path_layer_zip = self._setup_python_dir(tmp_path)
        create_layer_zip_file(dir_python, path_layer_zip, verbose=False)
        with zipfile.ZipFile(path_layer_zip) as zf:
            for name in zf.namelist():
                assert name.startswith("python/"), f"entry {name!r} missing python/ prefix"

    def test_ignored_packages_excluded(self, tmp_path):
        dir_python, path_layer_zip = self._setup_python_dir(tmp_path)
        create_layer_zip_file(dir_python, path_layer_zip, verbose=False)
        with zipfile.ZipFile(path_layer_zip) as zf:
            names = zf.namelist()
            assert not any("boto3" in n for n in names)
            assert not any("pytest" in n for n in names)

    def test_real_packages_included(self, tmp_path):
        dir_python, path_layer_zip = self._setup_python_dir(tmp_path)
        create_layer_zip_file(dir_python, path_layer_zip, verbose=False)
        with zipfile.ZipFile(path_layer_zip) as zf:
            names = zf.namelist()
            assert any("my_pkg" in n for n in names)

    def test_custom_ignore_list(self, tmp_path):
        dir_python, path_layer_zip = self._setup_python_dir(tmp_path)
        # ignore my_pkg, but allow boto3
        create_layer_zip_file(
            dir_python,
            path_layer_zip,
            ignore_package_list=["my_pkg"],
            verbose=False,
        )
        with zipfile.ZipFile(path_layer_zip) as zf:
            names = zf.namelist()
            assert not any("my_pkg" in n for n in names)
            assert any("boto3" in n for n in names)

    def test_empty_ignore_list_includes_all(self, tmp_path):
        dir_python, path_layer_zip = self._setup_python_dir(tmp_path)
        create_layer_zip_file(
            dir_python,
            path_layer_zip,
            ignore_package_list=[],
            verbose=False,
        )
        with zipfile.ZipFile(path_layer_zip) as zf:
            names = zf.namelist()
            assert any("boto3" in n for n in names)
            assert any("my_pkg" in n for n in names)

    def test_verbose_mode(self, tmp_path):
        """verbose=True should also work without error."""
        dir_python, path_layer_zip = self._setup_python_dir(tmp_path)
        create_layer_zip_file(dir_python, path_layer_zip, verbose=True)
        assert path_layer_zip.exists()


# ---------------------------------------------------------------------------
# Tests: default_ignore_package_list
# ---------------------------------------------------------------------------
class TestDefaultIgnorePackageList:

    def test_is_list(self):
        assert isinstance(default_ignore_package_list, list)

    def test_contains_aws_runtime_packages(self):
        assert "boto3" in default_ignore_package_list
        assert "botocore" in default_ignore_package_list

    def test_contains_build_tools(self):
        assert "setuptools" in default_ignore_package_list
        assert "pip" in default_ignore_package_list

    def test_contains_test_tools(self):
        assert "pytest" in default_ignore_package_list


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.package",
        preview=False,
    )
