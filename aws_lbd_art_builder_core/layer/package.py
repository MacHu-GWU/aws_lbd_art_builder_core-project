# -*- coding: utf-8 -*-

"""
Lambda layer packaging — Step 2 of the layer workflow.

This module provides two tool-agnostic functions that every downstream builder
needs after dependencies have been installed:

1. :func:`move_to_dir_python` — relocate installed packages into the
   ``python/`` directory that AWS Lambda requires for layers.
2. :func:`create_layer_zip_file` — compress that directory into a deployable
   ``layer.zip``.

**Why a separate ``python/`` directory?**

AWS Lambda layers are extracted into ``/opt``. For Python packages to be
importable, they must live under ``/opt/python`` so that Python's default
``sys.path`` picks them up. The zip must therefore contain ``python/`` as its
top-level entry — not a bare set of packages and not an absolute path.

**Why ``temp_cwd`` before zipping?**

The ``zip`` command records paths relative to the current working directory.
By ``cd``-ing into the artifacts directory first, the resulting zip entries
start with ``python/…`` instead of the full host filesystem path.
"""

import glob
import shutil
import subprocess
from pathlib import Path

from ..vendor.better_pathlib import temp_cwd


def move_to_dir_python(
    dir_site_packages: Path,
    dir_python: Path,
):
    """
    Relocate installed packages into the Lambda layer's ``python/`` directory.

    **Why this is needed:** Different build tools place packages in different
    locations (e.g. ``.venv/lib/python3.x/site-packages/``). Lambda layers
    require all packages under a single ``python/`` directory so they appear
    on ``sys.path`` at runtime. This function bridges that gap by moving
    (not copying) the site-packages tree into the target.

    :param dir_site_packages: Path to the source site-packages directory
    :param dir_python: Path to the target ``python/`` directory
    :raises FileNotFoundError: If the source site-packages directory doesn't exist
    """
    if dir_site_packages.exists():
        if dir_site_packages != dir_python:
            if dir_python.exists():
                shutil.rmtree(dir_python)
            shutil.move(dir_site_packages, dir_python)
        # otherwise, dir_site_packages is the same as dir_python, do nothing
    else:
        raise FileNotFoundError(f"dir_site_packages {dir_site_packages} not found")


default_ignore_package_list = [
    "boto3",
    "botocore",
    "s3transfer",
    "urllib3",
    "setuptools",
    "pip",
    "wheel",
    "twine",
    "_pytest",
    "pytest",
]
"""
Default packages to exclude from Lambda layer zip files.

- **AWS Runtime Provided**: boto3, botocore, s3transfer, urllib3 are
  pre-installed in Lambda — bundling them wastes space and can cause
  version conflicts with the runtime.
- **Build Tools**: setuptools, pip, wheel, twine are not needed at runtime.
- **Development Tools**: pytest, _pytest are testing frameworks not needed
  in production.
"""


def create_layer_zip_file(
    dir_python: Path,
    path_layer_zip: Path,
    ignore_package_list: list[str] | None = None,
    verbose: bool = True,
):
    """
    Create optimized zip file for AWS Lambda layer deployment.

    Compresses the ``python/`` directory into a zip file with maximum
    compression (``-9``) and selective package exclusions.

    :param dir_python: Path to the ``python/`` directory containing layer packages
    :param path_layer_zip: Output path for the layer zip file
    :param ignore_package_list: Packages to exclude from the zip.
        If None, uses :data:`default_ignore_package_list`.
    :param verbose: If True, shows detailed zip creation progress
    """
    if ignore_package_list is None:
        ignore_package_list = list(default_ignore_package_list)

    args = [
        "zip",
        f"{path_layer_zip}",
        "-r",
        "-9",
    ]
    if verbose is False:
        args.append("-q")

    # cd into artifacts dir so zip entries start with "python/…"
    with temp_cwd(dir_python.parent):
        args.extend(glob.glob("*"))

        if ignore_package_list:
            args.append("-x")
            for package in ignore_package_list:
                args.append(f"python/{package}*")
        subprocess.run(args, check=True)
