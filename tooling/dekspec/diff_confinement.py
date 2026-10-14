"""The shared repository-root file-pattern boundary (ADR-068)."""
from __future__ import annotations

from collections.abc import Iterable

from dekspec.file_patterns import matches_any

__all__ = ["matches_any_glob"]


def matches_any_glob(path: str, globs: Iterable[str]) -> bool:
    """Match folder-local wildcards, recursive globstars and brace groups."""
    return matches_any(path, globs)
