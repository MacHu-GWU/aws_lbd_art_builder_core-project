# -*- coding: utf-8 -*-

"""
pip-based build step for Lambda source deployment artifacts.

This module contains the single build step that installs the current Python
package into a target directory using ``pip install --no-dependencies
--target``, ready to be zipped into a Lambda deployment package.

Key assumptions
---------------
- The Lambda entry point (``lambda_function.py`` / ``lambda_handler``) lives
  **inside** the installed package, not as a separate file outside it.
- The caller supplies a ``.venv/bin/pip`` built for the target runtime, or
  accepts that the host pip is used.
"""

import subprocess
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
