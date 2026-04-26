# -*- coding: utf-8 -*-

"""
Integration tests for builder functions: build_source_dir_using_pip,
build_source_dir_using_uv, and create_source_zip.

Each build tool gets its own SourcePathLayout so the outputs are isolated:

    tests/build/lambda/source/using_pip/build/   ← pip install target
    tests/build/lambda/source/using_pip/source.zip
    tests/build/lambda/source/using_uv/build/    ← uv install target
    tests/build/lambda/source/using_uv/source.zip

Directories are left on disk after the test run so the developer can inspect
them.  They are cleaned at the start of each run (skip_prompt=True).
"""

import shutil
import zipfile
from pathlib import Path

import pytest

from aws_lbd_art_builder_core.source.foundation import SourcePathLayout
from aws_lbd_art_builder_core.source.builder import (
    build_source_dir_using_pip,
    build_source_dir_using_uv,
    create_source_zip,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DIR_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
PATH_PYPROJECT_TOML = DIR_PROJECT_ROOT / "pyproject.toml"

DIR_TESTS = Path(__file__).parent

LAYOUT_PIP = SourcePathLayout(
    dir_root=DIR_TESTS / "build" / "lambda" / "source" / "using_pip"
)
LAYOUT_UV = SourcePathLayout(
    dir_root=DIR_TESTS / "build" / "lambda" / "source" / "using_uv"
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def path_bin_pip() -> Path:
    # builder.py converts Path to str via f"{path_bin_pip}" before subprocess.run,
    # so the Windows PathLike warning from the IDE is a false positive.
    return DIR_PROJECT_ROOT / ".venv" / "bin" / "pip"


@pytest.fixture(scope="module")
def path_bin_uv() -> Path:
    uv = shutil.which("uv")
    assert uv is not None, "uv not found on PATH — install uv to run these tests"
    # Same note as above re: PathLike.
    return Path(uv)


@pytest.fixture(scope="module")
def pip_build_dir(path_bin_pip) -> Path:
    """Run pip build once for the whole module; return dir_build."""
    build_source_dir_using_pip(
        path_bin_pip=path_bin_pip,
        path_pyproject_toml=PATH_PYPROJECT_TOML,
        dir_lambda_source_build=LAYOUT_PIP.dir_build,
        skip_prompt=True,
        verbose=True,
    )
    return LAYOUT_PIP.dir_build


@pytest.fixture(scope="module")
def uv_build_dir(path_bin_uv) -> Path:
    """Run uv build once for the whole module; return dir_build."""
    build_source_dir_using_uv(
        path_bin_uv=path_bin_uv,
        path_pyproject_toml=PATH_PYPROJECT_TOML,
        dir_lambda_source_build=LAYOUT_UV.dir_build,
        skip_prompt=True,
        verbose=True,
    )
    return LAYOUT_UV.dir_build


@pytest.fixture(scope="module")
def uv_zip_sha256(uv_build_dir) -> str:
    """Run create_source_zip on the uv build; return the sha256."""
    return create_source_zip(
        dir_lambda_source_build=LAYOUT_UV.dir_build,
        path_source_zip=LAYOUT_UV.path_source_zip,
        verbose=True,
    )


# ---------------------------------------------------------------------------
# Shared assertions (used by both pip and uv test classes)
# ---------------------------------------------------------------------------

def _assert_build_dir(build_dir: Path):
    assert build_dir.exists() and build_dir.is_dir()
    assert (build_dir / "aws_lbd_art_builder_core").is_dir()
    assert (build_dir / "aws_lbd_art_builder_core" / "__init__.py").exists()
    # setuptools exclude rules respected
    assert not (build_dir / "aws_lbd_art_builder_core" / "tests").exists()
    assert not (build_dir / "aws_lbd_art_builder_core" / "docs").exists()
    # dist-info present, exactly one
    dist_infos = list(build_dir.glob("aws_lbd_art_builder_core-*.dist-info"))
    assert len(dist_infos) == 1, f"Expected 1 dist-info, got: {dist_infos}"
    # no transitive deps leaked
    for dep in ("func_args", "soft_deps", "boto3", "s3pathlib"):
        assert not (build_dir / dep).exists(), f"Dep '{dep}' leaked despite --no-deps"


# ---------------------------------------------------------------------------
# Tests: build_source_dir_using_pip
# ---------------------------------------------------------------------------

class TestBuildSourceDirUsingPip:
    def test_build_dir_structure(self, pip_build_dir):
        _assert_build_dir(pip_build_dir)

    def test_source_zip_not_inside_build_dir(self, pip_build_dir):
        # source.zip must be a sibling of dir_build, not nested inside it.
        assert not (pip_build_dir / "source.zip").exists()


# ---------------------------------------------------------------------------
# Tests: build_source_dir_using_uv
# ---------------------------------------------------------------------------

class TestBuildSourceDirUsingUv:
    def test_build_dir_structure(self, uv_build_dir):
        _assert_build_dir(uv_build_dir)

    def test_source_zip_not_inside_build_dir(self, uv_build_dir):
        assert not (uv_build_dir / "source.zip").exists()


# ---------------------------------------------------------------------------
# Tests: create_source_zip  (uses the uv build as input)
# ---------------------------------------------------------------------------

class TestCreateSourceZip:
    def test_zip_file_is_created(self, uv_zip_sha256):
        assert LAYOUT_UV.path_source_zip.exists()

    def test_returns_non_empty_hash(self, uv_zip_sha256):
        # hashes.of_paths() uses SHA256 by default → 64-char hex digest
        assert isinstance(uv_zip_sha256, str)
        assert len(uv_zip_sha256) == 64

    def test_zip_entries_are_at_root(self, uv_zip_sha256):
        """
        Zip entries must not carry absolute paths or a build/ prefix.
        The Lambda runtime expects to find package dirs at the archive root.
        """
        with zipfile.ZipFile(LAYOUT_UV.path_source_zip) as zf:
            names = zf.namelist()
        assert len(names) > 0
        for name in names:
            assert not name.startswith("/"), f"Absolute path in zip: {name}"

    def test_zip_contains_package(self, uv_zip_sha256):
        with zipfile.ZipFile(LAYOUT_UV.path_source_zip) as zf:
            names = zf.namelist()
        assert any(n.startswith("aws_lbd_art_builder_core/") for n in names)

    def test_zip_does_not_contain_source_zip_itself(self, uv_zip_sha256):
        """
        source.zip must not archive itself — only possible if path_source_zip
        is correctly placed outside dir_build.
        """
        with zipfile.ZipFile(LAYOUT_UV.path_source_zip) as zf:
            names = zf.namelist()
        assert "source.zip" not in names

    def test_same_content_same_sha256(self, uv_build_dir, uv_zip_sha256):
        """SHA256 is deterministic for the same build directory content."""
        sha2 = create_source_zip(
            dir_lambda_source_build=LAYOUT_UV.dir_build,
            path_source_zip=LAYOUT_UV.path_source_zip,
            verbose=False,
        )
        assert sha2 == uv_zip_sha256


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.source.builder",
        preview=False,
    )
