# -*- coding: utf-8 -*-

import pytest

from aws_lbd_art_builder_core.layer.package import move_to_dir_python


class TestMoveToDirectoryPython:
    def test_moves_site_packages_to_python_dir(self, tmp_path):
        site_packages = tmp_path / "site-packages"
        site_packages.mkdir()
        (site_packages / "requests").mkdir()
        (site_packages / "requests" / "__init__.py").write_text("# requests")
        (site_packages / "boto3").mkdir()
        (site_packages / "boto3" / "__init__.py").write_text("# boto3")

        dir_python = tmp_path / "python"

        move_to_dir_python(site_packages, dir_python)

        assert dir_python.exists()
        assert (dir_python / "requests" / "__init__.py").exists()
        assert (dir_python / "boto3" / "__init__.py").exists()
        assert not site_packages.exists()

    def test_overwrites_existing_python_dir(self, tmp_path):
        site_packages = tmp_path / "site-packages"
        site_packages.mkdir()
        (site_packages / "new_pkg").mkdir()
        (site_packages / "new_pkg" / "__init__.py").write_text("# new")

        dir_python = tmp_path / "python"
        dir_python.mkdir()
        (dir_python / "old_pkg").mkdir()
        (dir_python / "old_pkg" / "__init__.py").write_text("# old")

        move_to_dir_python(site_packages, dir_python)

        assert (dir_python / "new_pkg" / "__init__.py").exists()
        assert not (dir_python / "old_pkg").exists()

    def test_no_op_when_src_equals_dst(self, tmp_path):
        dir_python = tmp_path / "python"
        dir_python.mkdir()
        (dir_python / "pkg.py").write_text("# pkg")

        move_to_dir_python(dir_python, dir_python)

        assert (dir_python / "pkg.py").exists()

    def test_raises_when_src_not_found(self, tmp_path):
        missing = tmp_path / "nonexistent"
        dir_python = tmp_path / "python"

        with pytest.raises(FileNotFoundError):
            move_to_dir_python(missing, dir_python)


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.layer.package",
        preview=False,
    )
