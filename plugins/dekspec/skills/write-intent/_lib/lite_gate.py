"""Lite-mode gate for `/write-intent --lite` (INT-088 IU-2, bead ds-49mc).

The actual 4-gate refusal-contract check + the `lite: true` frontmatter
marker live in the shared
`plugins/dekspec/skills/_lib/scripts/artifact_ops.py` module (alongside the
other deterministic artifact ops — `transition`, `approve`, `update-index`,
`status-guard`, `editorial_amend`). This thin re-export module exists to
satisfy the file contract spelled out in bead `ds-49mc` (Files row) and to
give the skill body a stable per-skill import path:

    from _lib.lite_gate import lite_gate_check, lite_mark

The re-export indirection means consumers of `/write-intent` (the only
skill that ships a `--lite` modifier today) can evolve their own gate
logic without touching the shared `artifact_ops.py` API surface. The
shared implementation is the single source of truth; this file is a
stable handle.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Resolve the shared _lib/scripts/ path relative to this file. `__file__` is
# `plugins/dekspec/skills/write-intent/_lib/lite_gate.py`; the shared
# scripts live at `plugins/dekspec/skills/_lib/scripts/`. Three parents up
# (`_lib/` -> `write-intent/` -> `skills/`) lands us on the `skills/` dir.
_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent
_SHARED_SCRIPTS = _SKILLS_DIR / "_lib" / "scripts"
if str(_SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SHARED_SCRIPTS))

# Re-export the load-bearing helpers from the shared module. Engineering
# discipline: do NOT redefine these locally; if behavior needs to change,
# change it in `artifact_ops.py` so `--editorial`, `--lite`, and the
# future `--auto` flags share the same guard surface.
from artifact_ops import (  # noqa: E402  (sys.path mutation precedes import)
    lite_gate_check,
    lite_mark,
)

__all__ = ["lite_gate_check", "lite_mark"]
