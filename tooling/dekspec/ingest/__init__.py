"""Ingest — the brownfield-document classification substrate for `dekspec ingest`.

The ingest package is the deterministic engine behind the `dekspec ingest`
CLI subcommand (INT-059). It takes an inherited markdown design document
(a Confluence export, an ad-hoc PRD, an onboarding wiki page) and classifies
each of its sections into a draft DekSpec IR type — AE responsibility content,
ADR Context / Decision / Consequences content, WS business-rule content —
so a team adopting DekSpec on a brownfield codebase pays the
manual-classification cost as an incremental review pass rather than as
up-front blank-page authoring.

`classifier.py` provides the deterministic heuristic classifier
(`classify`) plus the `Section`, `Classification`, and `IRKind` types.
There is no LLM call anywhere in the pipeline — the same input always
yields the same output, so the command is fast, reproducible, and
unit-testable like every other DekSpec CLI subcommand.

`report.py` renders the confidence-scored classification report; `runner.py`
provides `run`, the orchestration entry point the `dekspec ingest` CLI
subcommand is a thin adapter over.

Per INT-059 / IB-097 (classifier) + IB-098 (report emitter + `run`).
"""
from __future__ import annotations

from .classifier import Classification, IRKind, Section, classify
from .runner import IngestError, IngestResult, run

__all__ = [
    "Classification",
    "IRKind",
    "IngestError",
    "IngestResult",
    "Section",
    "classify",
    "run",
]
