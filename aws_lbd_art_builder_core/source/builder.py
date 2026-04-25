# -*- coding: utf-8 -*-

"""
Build-step functions for Lambda source deployment artifacts.

Each function installs the current Python package into a caller-supplied
target directory (``dir_lambda_source_build``) using a different tool:

- :func:`build_source_artifacts_using_pip` — ``pip install --no-dependencies --target``
- :func:`build_source_artifacts_using_uv`  — ``uv pip install --no-deps --target``

Both functions are intentionally thin: they accept a plain :class:`~pathlib.Path`
for the target directory rather than a :class:`~aws_lbd_art_builder_core.source.foundation.SourcePathLayout`
object so that the build logic stays decoupled from any particular path convention.
Callers that use ``SourcePathLayout`` pass ``path_layout.dir_build`` as the argument.

Key assumptions
---------------
- The Lambda entry point lives **inside** the installed package, not as a
  separate file outside it.
- Only ``pyproject.toml``-based projects are supported (``setup.py`` is not).
- The build backend configured in ``[build-system]`` (typically setuptools)
  controls which packages and data files are included; ``packages.find`` /
  ``package-data`` settings in ``pyproject.toml`` are fully respected.
"""

import subprocess
import shutil
from pathlib import Path

from ..vendor.better_pathlib import temp_cwd
from ..typehint import T_PRINTER
from ..utils import clean_build_directory


def build_source_artifacts_using_pip(
    path_bin_pip: Path,
    path_setup_py_or_pyproject_toml: Path,
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

    The build directory is cleaned before installation to guarantee a
    reproducible, artefact-free starting state.

    :param path_bin_pip: pip executable, e.g. ``/path/to/.venv/bin/pip``
    :param path_setup_py_or_pyproject_toml: Package definition file
        (``setup.py`` or ``pyproject.toml``).  Its parent directory is used
        as the pip install source.
    :param dir_lambda_source_build: Target directory for the installed files,
        i.e. :attr:`~aws_lbd_art_builder_core.source.foundation.SourcePathLayout.dir_build`.
    :param skip_prompt: When ``True``, wipe the build directory without asking
        for confirmation.
    :param verbose: When ``True``, print the pip command and its output.
    :param printer: Callable used for log output (default: :func:`print`).
    """
    if verbose:
        printer("--- Building Lambda source artifacts using pip ...")
        printer(f"{path_bin_pip = !s}")
        printer(f"{path_setup_py_or_pyproject_toml = !s}")
        printer(f"{dir_lambda_source_build = !s}")

    clean_build_directory(
        dir_build=dir_lambda_source_build,
        folder_alias="lambda source build folder",
        skip_prompt=skip_prompt,
    )
    dir_workspace = path_setup_py_or_pyproject_toml.parent
    with temp_cwd(dir_workspace):
        args = [
            f"{path_bin_pip}",
            "install",
            f"{dir_workspace}",
            "--no-dependencies",
            f"--target={dir_lambda_source_build}",
        ]
        if verbose is False:
            args.append("--disable-pip-version-check")
            args.append("--quiet")
        subprocess.run(args, check=True)


def build_source_artifacts_using_uv(
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

    Unlike the pip variant, no ``temp_cwd`` is needed because the project
    directory is passed as an explicit path argument to uv.

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
    :raises FileNotFoundError: If *path_bin_uv* does not exist or is not
        executable.
    """
    if verbose:
        printer("--- Building Lambda source artifacts using uv ...")
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
    if verbose is False:
        args.append("--quiet")
    subprocess.run(args, check=True)
