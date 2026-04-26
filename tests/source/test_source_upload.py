# -*- coding: utf-8 -*-

"""
Integration tests for upload functions: upload_source_zip,
build_and_upload_source_using_pip, build_and_upload_source_using_uv.

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
from aws_lbd_art_builder_core.source.upload import (
    upload_source_zip,
    BuildAndUploadSourceResult,
    build_and_upload_source_using_pip,
    build_and_upload_source_using_uv,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DIR_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
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
    return DIR_PROJECT_ROOT / ".venv" / "bin" / "pip"


@pytest.fixture(scope="module")
def path_bin_uv() -> Path:
    uv = shutil.which("uv")
    assert uv is not None, "uv not found on PATH — install uv to run these tests"
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
# Tests: BuildAndUploadSourceResult
# ---------------------------------------------------------------------------

class TestBuildAndUploadSourceResult:
    def test_fields(self, uv_zip_sha256):
        from s3pathlib import S3Path
        result = BuildAndUploadSourceResult(
            source_sha256=uv_zip_sha256,
            s3path_source_zip=S3Path("my-bucket/lambda/source/0.1.0/abc/source.zip"),
        )
        assert result.source_sha256 == uv_zip_sha256
        assert result.s3path_source_zip.basename == "source.zip"


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.source.upload",
        preview=False,
    )
