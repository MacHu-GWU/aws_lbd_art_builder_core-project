# -*- coding: utf-8 -*-

"""
Build-step functions for Lambda source deployment artifacts.

Each function installs the current Python package into a caller-supplied
target directory (``dir_lambda_source_build``) using a different tool:

- :func:`build_source_dir_using_pip` — ``pip install --no-dependencies --target``
- :func:`build_source_dir_using_uv`  — ``uv pip install --no-deps --target``
- :func:`create_source_zip`          — zip the build dir and return its SHA256

All three functions are intentionally thin: they accept plain :class:`~pathlib.Path`
arguments rather than a :class:`~aws_lbd_art_builder_core.source.foundation.SourcePathLayout`
object so that the build logic stays decoupled from any particular path convention.
Callers that use ``SourcePathLayout`` pass ``path_layout.dir_build`` /
``path_layout.path_source_zip`` as arguments.

Key assumptions
---------------
- The Lambda entry point lives **inside** the installed package, not as a
  separate file outside it.
- Only ``pyproject.toml``-based projects are supported (``setup.py`` is not).
- The build backend configured in ``[build-system]`` (typically setuptools)
  controls which packages and data files are included; ``packages.find`` /
  ``package-data`` settings in ``pyproject.toml`` are fully respected.
- ``zip`` (the system binary) must be available on ``PATH`` for
  :func:`create_source_zip`.
"""

import glob
import subprocess
from pathlib import Path

from ..vendor.better_pathlib import temp_cwd
from ..vendor.hashes import hashes
from ..typehint import T_PRINTER
from ..utils import clean_build_directory


def build_source_dir_using_pip(
    path_bin_pip: Path,
    path_pyproject_toml: Path,
    dir_lambda_source_build: Path,
    skip_prompt: bool = False,
    verbose: bool = True,
    printer: T_PRINTER = print,
):
    """
    Install the current Python package into a target directory using pip.

    **Why pip install instead of copying files?**  pip resolves package
    metadata, entry points, and import paths exactly as the Lambda runtime
    expects.  Plain file copying can silently break relative imports or miss
    ``*.dist-info`` records that some libraries rely on at runtime.

    ``temp_cwd`` is intentionally **not** used here: ``path_pyproject_toml``
    is always an absolute path so pip does not need a specific working
    directory to locate the project.

    The build directory is cleaned before installation to guarantee a
    reproducible, artefact-free starting state.

    :param path_bin_pip: pip executable, e.g. ``/path/to/.venv/bin/pip``
    :param path_pyproject_toml: ``pyproject.toml`` of the project to install.
        Its parent directory is passed to ``pip install`` as the source.
    :param dir_lambda_source_build: Target directory for the installed files,
        i.e. :attr:`~aws_lbd_art_builder_core.source.foundation.SourcePathLayout.dir_build`.
    :param skip_prompt: When ``True``, wipe the build directory without asking
        for confirmation.
    :param verbose: When ``True``, print the pip command and its output.
    :param printer: Callable used for log output (default: :func:`print`).
    """
    if verbose:  # pragma: no cover
        printer("--- Building Lambda source dir using pip ...")
        printer(f"{path_bin_pip = !s}")
        printer(f"{path_pyproject_toml = !s}")
        printer(f"{dir_lambda_source_build = !s}")

    clean_build_directory(
        dir_build=dir_lambda_source_build,
        folder_alias="lambda source build folder",
        skip_prompt=skip_prompt,
    )
    dir_workspace = path_pyproject_toml.parent
    args = [
        f"{path_bin_pip}",
        "install",
        f"{dir_workspace}",
        "--no-dependencies",
        f"--target={dir_lambda_source_build}",
    ]
    if verbose is False:  # pragma: no cover
        args.append("--disable-pip-version-check")
        args.append("--quiet")
    subprocess.run(args, check=True)


def build_source_dir_using_uv(
    path_bin_uv: Path,
    path_pyproject_toml: Path,
    dir_lambda_source_build: Path,
    skip_prompt: bool = False,
    verbose: bool = True,
    printer: T_PRINTER = print,
):
    """
    Install the current Python package into a target directory using uv.

    ``uv pip install`` has its own wheel installer and does **not** require pip
    to be present in the virtual environment.  It is otherwise equivalent to
    ``pip install --no-deps --target`` but noticeably faster.

    ``temp_cwd`` is intentionally **not** used: the project directory is
    passed as an explicit absolute path argument to uv, so the working
    directory is irrelevant.

    ``setup.py``-only projects are **not** supported; the project must have a
    ``pyproject.toml`` with a ``[build-system]`` table.

    The build directory is cleaned before installation to guarantee a
    reproducible, artefact-free starting state.

    :param path_bin_uv: uv executable, e.g. ``/path/to/.venv/bin/uv`` or the
        system-wide uv resolved via :func:`shutil.which`.
    :param path_pyproject_toml: ``pyproject.toml`` of the project to install.
        Its parent directory is passed to ``uv pip install`` as the source.
    :param dir_lambda_source_build: Target directory for the installed files,
        i.e. :attr:`~aws_lbd_art_builder_core.source.foundation.SourcePathLayout.dir_build`.
    :param skip_prompt: When ``True``, wipe the build directory without asking
        for confirmation.
    :param verbose: When ``True``, print the uv command and its output.
    :param printer: Callable used for log output (default: :func:`print`).
    """
    if verbose: # pragma: no cover
        printer("--- Building Lambda source dir using uv ...")
        printer(f"{path_bin_uv = !s}")
        printer(f"{path_pyproject_toml = !s}")
        printer(f"{dir_lambda_source_build = !s}")

    clean_build_directory(
        dir_build=dir_lambda_source_build,
        folder_alias="lambda source build folder",
        skip_prompt=skip_prompt,
    )
    args = [
        f"{path_bin_uv}",
        "pip",
        "install",
        f"{path_pyproject_toml.parent}",
        "--no-deps",
        f"--target={dir_lambda_source_build}",
    ]
    if verbose is False:  # pragma: no cover
        args.append("--quiet")
    subprocess.run(args, check=True)


def create_source_zip(
    dir_lambda_source_build: Path,
    path_source_zip: Path,
    verbose: bool = True,
    printer: T_PRINTER = print,
) -> str:
    """
    Zip the Lambda source build directory and return its SHA256 hash.

    The zip is created with maximum compression (``-9``) and its root entries
    are the direct children of *dir_lambda_source_build*, so that the Lambda
    runtime can import them without any extra path prefix.

    ``path_source_zip`` **must not** be inside *dir_lambda_source_build*.
    Place it at :attr:`~aws_lbd_art_builder_core.source.foundation.SourcePathLayout.path_source_zip`
    (a sibling of the build directory) to avoid the zip accidentally
    archiving itself mid-creation.

    ``temp_cwd`` **is** required here: :func:`glob.glob` is CWD-relative and
    the ``zip`` command must run from inside *dir_lambda_source_build* so that
    archive entries carry relative (not absolute) paths.

    The SHA256 is computed over the *build directory* (not the zip file) so
    that the hash is stable regardless of zip metadata or timestamps.

    :param dir_lambda_source_build: Directory containing the installed package
        files, i.e. :attr:`~aws_lbd_art_builder_core.source.foundation.SourcePathLayout.dir_build`.
    :param path_source_zip: Output path for the zip archive, i.e.
        :attr:`~aws_lbd_art_builder_core.source.foundation.SourcePathLayout.path_source_zip`.
    :param verbose: When ``True``, print progress and the computed hash.
    :param printer: Callable used for log output (default: :func:`print`).
    :return: SHA256 hex digest of the source build directory.
    """
    if verbose:  # pragma: no cover
        printer("--- Creating Lambda source zip file ...")
        printer(f"{dir_lambda_source_build = !s}")
        printer(f"{path_source_zip = !s}")

    args = [
        "zip",
        f"{path_source_zip}",
        "-r",
        "-9",
    ]
    if verbose is False:  # pragma: no cover
        args.append("-q")

    # temp_cwd is required: glob("*") is CWD-relative and zip entries must be
    # relative paths so the Lambda runtime can find them at the root of the archive.
    with temp_cwd(dir_lambda_source_build):
        args.extend(glob.glob("*"))
        subprocess.run(args, check=True)

    source_sha256 = hashes.of_paths([dir_lambda_source_build])
    if verbose:  # pragma: no cover
        printer(f"{source_sha256 = }")
    return source_sha256
