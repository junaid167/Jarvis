"""Small, reusable verification helpers for JARVIS 2.0."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def result_says_success(value: Any) -> bool:
    """Conservative check for action results that expose a success field."""
    if isinstance(value, dict):
        if "success" in value:
            return bool(value["success"])
        if "ok" in value:
            return bool(value["ok"])
    return value is not None


def file_exists(path: str | Path) -> bool:
    try:
        return Path(path).expanduser().exists()
    except (OSError, TypeError, ValueError):
        return False


def text_contains(value: Any, expected: str) -> bool:
    return expected.casefold() in str(value).casefold()


def verify_file_created(path: str | Path, result: Any = None) -> bool:
    return file_exists(path) and result_says_success(result)
