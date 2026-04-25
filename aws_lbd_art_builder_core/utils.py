# -*- coding: utf-8 -*-

import typing as T
import shutil
from pathlib import Path


def ensure_exact_one_true(lst: T.List[bool]):
    """
    Ensure that exactly one element in the list is True.
    """
    if sum(lst) != 1:
        raise ValueError(f"Expected exactly one True, but got {lst}")


def write_bytes(path: Path, content: bytes):
    """
    Write bytes to a file, creating parent directories if they don't exist.
    """
    try:
        path.write_bytes(content)
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def is_match(
    relpath_parts: list[str],
    include: list[str],
    exclude: list[str],
) -> bool:
    """
    Based on the include and exclude pattern, do we ignore this file?

    Explicit exclude > Explicit include > Implicit include

    :param relpath_parts: relative path parts of the file to be checked
        For example, if the file is /a/b/c/d.txt, and the base dir is /a,
        then relpath_parts should be ['b', 'c', 'd.txt']
    :param include: list of glob patterns to include
    :param exclude: list of glob patterns to exclude
    """
    # Use Path to join parts in an OS-compatible way
    # This handles both Unix (/) and Windows (\) path separators
    relpath_obj = Path(*relpath_parts) if relpath_parts else Path(".")

    if len(include) == 0 and len(exclude) == 0:
        return True
    elif len(include) > 0 and len(exclude) > 0:
        match_any_include = any([relpath_obj.match(pattern) for pattern in include])
        match_any_exclude = any([relpath_obj.match(pattern) for pattern in exclude])
        if match_any_exclude:
            return False
        else:
            return match_any_include
    elif len(include) > 0 and len(exclude) == 0:
        return any([relpath_obj.match(pattern) for pattern in include])
    elif len(include) == 0 and len(exclude) > 0:
        return not any([relpath_obj.match(pattern) for pattern in exclude])
    else:  # pragma: no cover
        raise NotImplementedError


def normalize_glob_patterns(patterns: str | list[str] | None) -> list[str]:
    """
    Normalize glob pattern input to a list of strings.

    Handles flexible input types for include/exclude patterns, converting
    single strings to lists and None to empty lists for consistent processing.

    :param patterns: Glob patterns as string, list of strings, or None

    :returns: Normalized list of glob pattern strings

    **Examples**::

        normalize_glob_patterns(None)           # []
        normalize_glob_patterns("*.py")         # ["*.py"]
        normalize_glob_patterns(["*.py", "*.txt"])  # ["*.py", "*.txt"]
    """
    if patterns is None:  # pragma: no cover
        return []
    elif isinstance(patterns, str):  # pragma: no cover
        return [patterns]
    else:  # pragma: no cover
        return patterns


def copy_source_for_lambda_deployment(
    source_dir: str | Path,
    target_dir: str | Path,
    include: str | list[str] | None = None,
    exclude: str | list[str] | None = None,
):
    """
    Selectively copy Python source code for AWS Lambda deployment packaging.

    This function prepares Python library source code for Lambda deployment by
    copying files from a source directory to a target directory with selective
    filtering. It's designed to create clean deployment packages that exclude
    unnecessary files like tests, cache files, and development artifacts.

    **Lambda Deployment Context**:

    Lambda deployment packages must be optimized for size and contain only the
    necessary runtime files. This function helps create such packages by:

    - Filtering source files based on include/exclude patterns
    - Automatically excluding Python cache files (``__pycache__``, ``*.pyc``, ``*.pyo``)
    - Preserving directory structure for proper module imports
    - Creating a clean target directory for packaging

    :param source_dir: Source directory containing Python library code
    :param target_dir: Target directory where filtered files will be copied
    :param include: Glob patterns to include (if None, includes all files)
    :param exclude: Glob patterns to exclude (auto-excludes Python cache files)

    **Examples**::

        # Copy only Python files, excluding tests
        copy_source_for_lambda_deployment(
            source_dir="./my_package",
            target_dir="./build/my_package",
            include=["*.py"],
            exclude=["*test*", "*dev*"]
        )

        # Copy all files except specific patterns
        copy_source_for_lambda_deployment(
            source_dir="./src",
            target_dir="./lambda_build/src",
            exclude=["*.md", "docs/*", "examples/*"]
        )

    .. note::
        The target directory is completely replaced if it exists. Python cache
        files (``__pycache__``, ``*.pyc``, ``*.pyo``) are always excluded regardless of
        the exclude parameter.

    .. seealso::
        :func:`is_match` for the pattern matching logic used in file filtering
    """
    source_path: Path = Path(source_dir).absolute()
    target_path: Path = Path(target_dir).absolute()
    include: list[str] = normalize_glob_patterns(include)
    exclude: list[str] = normalize_glob_patterns(exclude)
    exclude.extend(["__pycache__/*", "*.pyc", "*.pyo"])

    for file_path in source_path.glob("**/*"):
        if file_path.is_file():
            relpath = file_path.relative_to(source_path)
            should_include = is_match(
                relpath_parts=list(relpath.parts),
                include=include,
                exclude=exclude,
            )
            if should_include:
                target_file_path = target_path.joinpath(relpath)
                write_bytes(target_file_path, file_path.read_bytes())


def prompt_to_confirm_before_remove_dir(dir_path: Path) -> bool:  # pragma: no cover
    """
    Prompt user to confirm before removing a directory and its contents.
    """
    answer = input(
        f"Are you sure you want to delete the directory "
        f"'{dir_path}' and all its contents? (Y/N): "
    )
    return answer.strip().upper() == "Y"


def clean_build_directory(
    dir_build: Path,
    folder_alias: str,
    skip_prompt: bool = False,
):  # pragma: no cover
    """
    Prepare the temporary build directory for building artifacts.

    This function ensures that the build directory is clean by removing
    it if it already exists, optionally prompting the user for confirmation. It is
    a common utility used by multiple methods that build Lambda artifacts,
    regardless of the specific build tool or approach.

    :param dir_build: The temporary build directory for Lambda artifacts.
    :param folder_alias: A human-readable alias for the directory, used in
        prompts and error messages.
    :param skip_prompt: If True, skips the confirmation prompt before removing
        an existing directory.
    """
    if dir_build.exists():
        if skip_prompt:
            flag = True
        else:
            flag = prompt_to_confirm_before_remove_dir(dir_build)
        if flag:
            shutil.rmtree(dir_build)
        else:
            raise RuntimeError(f"{folder_alias} {dir_build} already exists!")
