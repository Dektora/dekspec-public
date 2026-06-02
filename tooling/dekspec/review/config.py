"""Three-mode review config (MSN-017 / INT-118). Per ADR-026 (LOCKED).

Resolves the active review mode from ``.dekspec/config.yaml``'s
``review.mode`` field, falling back to ``DEFAULT_MODE = "RECOMMEND"``
when the field is absent. If mode is MIXED or AUTO but the operator
has not committed ``.dekspec/review-thresholds.yaml`` (INT-117 writes
it), the resolver reverts to RECOMMEND with a P2 advisory so the
pipeline never auto-advances without an explicit calibration corpus.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


VALID_MODES = ("RECOMMEND", "MIXED", "AUTO")
DEFAULT_MODE = "RECOMMEND"
MIN_SAMPLES_PER_LENS = 50  # consumed by the audit-rule emitter advisory


class InvalidModeError(ValueError):
    """Raised when a config declares a mode outside :data:`VALID_MODES`."""


def assert_valid_mode(mode: str) -> None:
    if mode not in VALID_MODES:
        raise InvalidModeError(
            f"Unknown review.mode {mode!r}; expected one of {VALID_MODES}."
        )


def resolve_mode(
    config_path: Path | str,
    thresholds_path: Optional[Path | str] = None,
) -> str:
    """Resolve the active review mode.

    Reads ``review.mode`` from ``config_path`` (an absent file
    silently yields :data:`DEFAULT_MODE`). If the declared mode is
    MIXED or AUTO but ``thresholds_path`` (default
    ``.dekspec/review-thresholds.yaml`` adjacent to the config) is
    missing, falls back to :data:`DEFAULT_MODE`.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        return DEFAULT_MODE

    data = yaml.safe_load(config_path.read_text()) or {}
    declared = (data.get("review") or {}).get("mode", DEFAULT_MODE)
    assert_valid_mode(declared)

    if declared in {"MIXED", "AUTO"}:
        tpath = Path(thresholds_path) if thresholds_path is not None else (
            config_path.parent / "review-thresholds.yaml"
        )
        if not tpath.exists():
            return DEFAULT_MODE
    return declared
