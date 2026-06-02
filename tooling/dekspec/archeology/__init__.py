"""Archeology — the brownfield spec-gap-detection substrate.

The deterministic Python engine behind the `/dekspec:archeology` skill and
the `dekspec archeology coverage` CLI verb (INT-030 / IB-118). It is the
first *recovery-flow* substrate in the library: where the authoring skills
assume a greenfield drafting context, archeology starts from existing code
and works back toward a ratifiable Intent.

Two helper modules:

- `scan` — an AST walk over a Python file (or directory tree) that
  enumerates the public API (module-level functions, classes, public
  methods), internal state (module-level assignments), and — best-effort —
  external callers (other modules across the repo that import the scanned
  module). The skill's `--scan` / `--cross-ref` modes shell out to it.
- `coverage` — gap detection: `coverage.run(at)` walks a repo, collects the
  §Components-affected glob set from every LOCKED Intent, honors a per-repo
  exclude file (`.dekspec/archeology-exclude`), and reports the files no
  LOCKED Intent claims. The `dekspec archeology coverage` CLI verb is a thin
  adapter over it.

This package writes nothing against the target repo — both helpers are
read-only. `from dekspec.archeology import scan, coverage` resolves to the
two helper modules.
"""
from __future__ import annotations

from . import coverage, scan

__all__ = ["coverage", "scan"]
