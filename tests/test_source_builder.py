# -*- coding: utf-8 -*-

"""
Integration tests for build_source_artifacts_using_uv.

These tests actually invoke uv and install the current project into a
temporary directory under tests/build/lambda/build_source_artifacts_using_uv/.

The directory is left on disk after the test so the developer can inspect the
installed files.  It is cleaned at the start of each run by the function under
test (skip_prompt=True).

uv is resolved via shutil.which("uv"); the test is skipped when uv is not on PATH.
"""

import shutil
from pathlib import Path

import pytest

from aws_lbd_art_builder_core.source.builder import build_source_artifacts_using_uv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# The project root this test lives in
DIR_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
PATH_PYPROJECT_TOML = DIR_PROJECT_ROOT / "pyproject.toml"

# Dedicated temp dir for this test — used as dir_lambda_source_build
DIR_LAMBDA_SOURCE_BUILD = (
    Path(__file__).parent
    / "build"
    / "lambda"
    / "build_source_artifacts_using_uv"
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def path_bin_uv() -> Path:
    """Resolve uv binary; skip the whole module if uv is not on PATH."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not found on PATH — skipping builder tests")
    return Path(uv)


@pytest.fixture(scope="module")
def installed_dir(path_bin_uv) -> Path:
    """
    Run build_source_artifacts_using_uv once for the whole test module and
    return the populated dir_lambda_source_build.
    """
    build_source_artifacts_using_uv(
        path_bin_uv=path_bin_uv,
        path_pyproject_toml=PATH_PYPROJECT_TOML,
        dir_lambda_source_build=DIR_LAMBDA_SOURCE_BUILD,
        skip_prompt=True,
        verbose=True,
    )
    return DIR_LAMBDA_SOURCE_BUILD


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildSourceArtifactsUsingUv:
    def test_target_dir_is_created(self, installed_dir):
        assert installed_dir.exists()
        assert installed_dir.is_dir()

    def test_package_is_installed(self, installed_dir):
        """The main package directory must be present in the target."""
        assert (installed_dir / "aws_lbd_art_builder_core").is_dir()

    def test_package_is_importable_from_target(self, installed_dir):
        """
        Verify that the installed files form a valid Python package by checking
        __init__.py exists (import machinery check without sys.path manipulation).
        """
        init = installed_dir / "aws_lbd_art_builder_core" / "__init__.py"
        assert init.exists()

    def test_tests_subpackage_is_excluded(self, installed_dir):
        """
        [tool.setuptools.packages.find] excludes aws_lbd_art_builder_core.tests
        so the Lambda zip doesn't ship test code.
        """
        assert not (installed_dir / "aws_lbd_art_builder_core" / "tests").exists()

    def test_docs_subpackage_is_excluded(self, installed_dir):
        """
        [tool.setuptools.packages.find] excludes aws_lbd_art_builder_core.docs.
        """
        assert not (installed_dir / "aws_lbd_art_builder_core" / "docs").exists()

    def test_dist_info_is_present(self, installed_dir):
        """pip/uv --target installs a .dist-info directory for the package."""
        dist_infos = list(installed_dir.glob("aws_lbd_art_builder_core-*.dist-info"))
        assert len(dist_infos) == 1, (
            f"Expected exactly one dist-info, found: {dist_infos}"
        )

    def test_no_dependency_packages_installed(self, installed_dir):
        """
        --no-deps must not pull in transitive dependencies (func_args, soft_deps, …).
        Only the project's own package and its dist-info should be present.
        """
        unexpected = [
            "func_args",
            "soft_deps",
            "boto3",
            "s3pathlib",
        ]
        for name in unexpected:
            assert not (installed_dir / name).exists(), (
                f"Dependency '{name}' was installed despite --no-deps"
            )


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.source.builder",
        preview=False,
    )
