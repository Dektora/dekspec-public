"""Folder-local file patterns, frozen legacy readings and proved conversions."""

from .convert import ConversionRun, PatternConversion, PatternEntry, convert, convert_entries
from .dialect import matches, matches_any
from .legacy import LEGACY_READINGS, legacy_matches

__all__ = [
    "LEGACY_READINGS",
    "ConversionRun",
    "PatternConversion",
    "PatternEntry",
    "convert",
    "convert_entries",
    "legacy_matches",
    "matches",
    "matches_any",
]
