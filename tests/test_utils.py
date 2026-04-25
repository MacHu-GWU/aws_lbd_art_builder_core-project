# -*- coding: utf-8 -*-

import tempfile
from pathlib import Path

from aws_lbd_art_builder_core.utils import (
    ensure_exact_one_true,
    is_match,
    copy_source_for_lambda_deployment,
)


def test_ensure_exact_one_true():
    # Test with exactly one True
    ensure_exact_one_true([True, False, False])
    ensure_exact_one_true([False, True])

    # Test with no True values
    try:
        ensure_exact_one_true([False, False, False])
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    # Test with multiple True values
    try:
        ensure_exact_one_true([True, True, False])
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

    # Test with all True values
    try:
        ensure_exact_one_true([True, True, True])
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_is_match():
    # Case 1: Empty include, empty exclude (matches everything)
    assert is_match(["file.txt"], [], []) is True
    assert is_match(["folder", "file.py"], [], []) is True

    # Case 2: Empty include, with exclude (matches everything except excluded)
    assert is_match(["file.txt"], [], ["*.txt"]) is False
    assert is_match(["file.py"], [], ["*.txt"]) is True
    assert is_match(["folder", "file.txt"], [], ["*.txt"]) is False
    assert is_match(["folder", "file.py"], [], ["*.txt"]) is True

    assert is_match(["__pycache__", "script.py"], [], ["__pycache__/*"]) is False
    assert (
        is_match(["folder", "__pycache__", "script.py"], [], ["__pycache__/*"]) is False
    )

    # Case 3: With include, empty exclude (matches only included)
    assert is_match(["file.txt"], ["*.py"], []) is False
    assert is_match(["file.py"], ["*.py"], []) is True
    assert is_match(["folder", "file.py"], ["*.py"], []) is True
    assert is_match(["folder", "file.txt"], ["*.py"], []) is False

    # Case 4: With include, with exclude (exclude takes precedence)
    assert is_match(["file.py"], ["*.py"], ["test_*.py"]) is True
    assert is_match(["test_file.py"], ["*.py"], ["test_*.py"]) is False
    assert is_match(["module.py"], ["*.py"], ["test_*.py"]) is True

    # Case 5: With include, with overlapping exclude (exclude takes precedence)
    assert (
        is_match(["file.py"], ["*.py", "**/*.py"], ["folder/*.py"]) is True
    )
    assert (
        is_match(["folder", "file.py"], ["*.py", "**/*.py"], ["folder/*.py"]) is False
    )
    assert is_match(["other", "file.py"], ["*.py", "**/*.py"], ["folder/*.py"]) is True
    assert (
        is_match(["deep", "folder", "file.py"], ["*.py", "**/*.py"], ["folder/*.py"])
        is False
    )

    # Case 6: Multiple includes, multiple excludes
    assert (
        is_match(
            ["file.py"],
            ["*.py", "**/*.py", "*.md", "**/*.md"],
            ["test_*.py", "**/test_*.py", "temp/*", "**/temp/*"],
        )
        is True
    )
    assert (
        is_match(
            ["docs", "file.md"],
            ["*.py", "**/*.py", "*.md", "**/*.md"],
            ["test_*.py", "**/test_*.py", "temp/*", "**/temp/*"],
        )
        is True
    )
    assert (
        is_match(
            ["test_file.py"],
            ["*.py", "**/*.py", "*.md", "**/*.md"],
            ["test_*.py", "**/test_*.py", "temp/*", "**/temp/*"],
        )
        is False
    )
    assert (
        is_match(
            ["temp", "file.py"],
            ["*.py", "**/*.py", "*.md", "**/*.md"],
            ["temp/*", "**/temp/*"],
        )
        is False
    )
    assert (
        is_match(
            ["folder", "temp", "file.md"],
            ["*.py", "**/*.py", "*.md", "**/*.md"],
            ["temp/*", "**/temp/*"],
        )
        is False
    )

    # Case 7: Edge cases - single path parts
    assert is_match(["README.md"], ["*.md"], []) is True
    assert is_match(["setup.py"], ["*.py"], ["*test*"]) is True
    assert is_match(["test.py"], ["*.py"], ["*test*"]) is False

    # Case 8: Complex nested patterns
    assert is_match(["src", "main.py"], ["src/*.py"], []) is True
    assert is_match(["src", "test", "main.py"], ["src/*.py"], []) is False
    assert is_match(["src", "test", "main.py"], ["src/**/*.py"], []) is True

    # Case 9: Both include and exclude match, exclude should win
    assert is_match(["test_main.py"], ["*.py"], ["test_*"]) is False
    assert is_match(["main_test.py"], ["*.py"], ["test_*"]) is True

    # Case 10: Edge case - empty path parts (should handle gracefully)
    assert is_match([], [], []) is True
    assert is_match([], ["*.py"], []) is False  # Empty path (.) won't match *.py
    assert (
        is_match([], [], ["*"]) is True
    )  # Empty path (.) doesn't match "*" pattern, so not excluded

    # Case 11: Cross-platform compatibility - should work regardless of OS path separator
    assert is_match(["src", "main.py"], ["src/*.py"], []) is True
    assert is_match(["src", "tests", "test.py"], ["src/**/*.py"], []) is True


def test_copy_source_for_lambda_deployment():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        source_dir = temp_path / "source"
        target_dir = temp_path / "target"

        # Create source structure
        source_dir.mkdir()
        (source_dir / "main.py").write_text("print('hello')")
        (source_dir / "config.txt").write_text("config data")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "module.py").write_text("def func(): pass")
        (source_dir / "__pycache__").mkdir()
        (source_dir / "__pycache__" / "cache.pyc").write_text("cache")

        # Build with include/exclude patterns
        copy_source_for_lambda_deployment(
            source_dir=source_dir,
            target_dir=target_dir,
            include=["*.py"],
            exclude=["*test*"],
        )

        # Verify results - should copy .py files but exclude __pycache__
        assert (target_dir / "main.py").exists()
        assert (target_dir / "subdir" / "module.py").exists()
        assert not (target_dir / "config.txt").exists()  # not included
        assert not (target_dir / "__pycache__").exists()  # auto-excluded

        # Verify file contents
        assert (target_dir / "main.py").read_text() == "print('hello')"
        assert (target_dir / "subdir" / "module.py").read_text() == "def func(): pass"


if __name__ == "__main__":
    from aws_lbd_art_builder_core.tests import run_cov_test

    run_cov_test(
        __file__,
        "aws_lbd_art_builder_core.utils",
        preview=False,
    )
