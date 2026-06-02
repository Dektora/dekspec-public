"""Per-lens silver/gold threshold proposal from the reviews.db
calibration corpus (MSN-017 / INT-117). Per ADR-026 (LOCKED 2026-05-29).

Inputs (from :mod:`dekspec.review.db`):
- per-row ``{lens, predicted_score, actual_outcome}`` samples.

Outputs:
- ``{lens_id: {silver: float, gold: float}}`` proposal, written by
  :func:`write_thresholds_yaml` to ``.dekspec/review-thresholds.yaml``.

The math is intentionally simple at the first cut: per-lens, find the
lowest score that satisfies a configurable false-positive rate (FPR)
target. ``silver`` = lowest score whose empirical FPR ≤ ``target_fpr``
on the "wrong" outcome labels; ``gold`` = lowest score whose empirical
FPR ≤ ``target_fpr / 2`` (i.e. twice as strict). Real consumers iterate
on this once a corpus exists; for now the contract is the shape, not
the precise math.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import yaml


# Outcomes that count as "the lens was wrong to surface" — calibration FPR target.
WRONG_OUTCOMES = {"operator-accepted", "PR-merged-clean"}


def propose_thresholds(
    samples: Iterable[Mapping[str, object]],
    target_fpr: float = 0.05,
) -> dict[str, dict[str, float]]:
    """Propose per-lens silver/gold thresholds.

    ``samples`` is an iterable of dicts with keys ``lens``,
    ``predicted_score`` (0-100), ``actual_outcome`` (string).
    Returns ``{lens: {silver: float, gold: float}}``. Empty input
    returns ``{}``.
    """
    by_lens: dict[str, list[tuple[float, str]]] = {}
    for s in samples:
        lens = str(s["lens"])
        score = float(s["predicted_score"])
        outcome = str(s["actual_outcome"])
        by_lens.setdefault(lens, []).append((score, outcome))

    out: dict[str, dict[str, float]] = {}
    for lens, rows in by_lens.items():
        out[lens] = {
            "silver": _threshold_for_fpr(rows, target_fpr),
            "gold": _threshold_for_fpr(rows, target_fpr / 2.0),
        }
    return out


def _threshold_for_fpr(rows: list[tuple[float, str]], fpr: float) -> float:
    """Lowest score whose empirical FPR ≤ ``fpr`` on the WRONG_OUTCOMES
    label set among ``rows``. If no score satisfies, return 100.0.
    """
    if not rows:
        return 100.0
    # Sort descending by score; sweep down accumulating wrongs / total.
    sorted_rows = sorted(rows, key=lambda r: r[0], reverse=True)
    total = 0
    wrong = 0
    for score, outcome in sorted_rows:
        total += 1
        if outcome in WRONG_OUTCOMES:
            wrong += 1
        empirical_fpr = wrong / total if total else 0.0
        if empirical_fpr > fpr:
            # Going lower fails the target — the previous boundary is the threshold.
            return float(score) + 1.0  # one above this score
    # All samples satisfy the FPR target — the lowest seen score is acceptable.
    return float(sorted_rows[-1][0])


def write_thresholds_yaml(
    path: Path | str,
    thresholds: Mapping[str, Mapping[str, float]],
) -> None:
    """Write ``thresholds`` to ``path`` as YAML the orchestration shell
    (INT-105) reads on each review run."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(thresholds), sort_keys=True))


def read_thresholds_yaml(path: Path | str) -> dict[str, dict[str, float]]:
    """Read the operator-committed thresholds file. Returns ``{}`` when
    the file is absent."""
    path = Path(path)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}
