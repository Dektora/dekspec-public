"""Proved conversions and file-atomic batch results; no artifact I/O."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from .languages import ProofLimit, rewrite
from .legacy import validate_reading


@dataclass(frozen=True)
class PatternConversion:
    status: str
    patterns: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class PatternEntry:
    file: str
    line: int
    pattern: str
    reading: str


@dataclass(frozen=True)
class ConversionResult:
    entry: PatternEntry
    status: str
    patterns: tuple[str, ...]
    reason: str | None


@dataclass(frozen=True)
class ConversionRun:
    results: tuple[ConversionResult, ...]
    stopped: tuple[ConversionResult, ...]


@lru_cache(maxsize=2048)
def convert(pattern: str, reading: str) -> PatternConversion:
    """Preserve exactly the old language, or stop with an actionable reason.

    Success is gated by symbolic equivalence over the complete O-9 universe.
    Candidate search is bounded; a stopped result makes no claim of success.
    """
    validate_reading(reading)
    try:
        patterns = rewrite(pattern, reading)
        return PatternConversion("unchanged" if patterns == (pattern,) else "converted", patterns, None)
    except (ProofLimit, RecursionError) as error:
        return PatternConversion("stopped", (), str(error) or "Proof recursion limit exceeded")


def convert_entries(entries: Iterable[PatternEntry]) -> ConversionRun:
    """Convert all entries, withholding every change to a file with a stop."""
    entries = tuple(entries)
    for entry in entries:
        validate_reading(entry.reading)
    conversions = [convert(entry.pattern, entry.reading) for entry in entries]
    stopped_files = {entry.file for entry, result in zip(entries, conversions) if result.status == "stopped"}
    results = []
    for entry, result in zip(entries, conversions):
        if entry.file in stopped_files and result.status != "stopped":
            results.append(ConversionResult(entry, "file-stopped", (entry.pattern,), "Another pattern in this file stopped"))
        else:
            results.append(ConversionResult(entry, result.status, result.patterns, result.reason))
    return ConversionRun(tuple(results), tuple(r for r in results if r.status == "stopped"))
