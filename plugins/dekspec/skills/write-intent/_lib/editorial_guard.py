"""Editorial-amend guard for `/write-intent --amend --editorial` (INT-088 IU-1).

The actual classifier + the surgical Amendment-Log append live in the shared
`plugins/dekspec/skills/_lib/scripts/artifact_ops.py` module (alongside the
other deterministic artifact ops — `transition`, `approve`, `update-index`,
`status-guard`). This thin re-export module exists to satisfy the file
contract spelled out in bead `ds-uxpy` (INT-088 IU-1, Files row) and to give
the skill body a stable per-skill import path:

    from _lib.editorial_guard import classify_intent_diff, editorial_amend

The re-export indirection means consumers of `/write-intent` (the only skill
that ships an `--editorial` modifier today) can evolve their own guard logic
without touching the shared `artifact_ops.py` API surface. The shared
implementation is the single source of truth; this file is a stable handle.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Resolve the shared _lib/scripts/ path relative to this file. `__file__` is
# `plugins/dekspec/skills/write-intent/_lib/editorial_guard.py`; the shared
# scripts live at `plugins/dekspec/skills/_lib/scripts/`. Three parents up
# (`_lib/` -> `write-intent/` -> `skills/`) lands us on the `skills/` dir.
_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent
_SHARED_SCRIPTS = _SKILLS_DIR / "_lib" / "scripts"
if str(_SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SHARED_SCRIPTS))

# Re-export the load-bearing helpers from the shared module. Engineering
# discipline: do NOT redefine these locally; if behavior needs to change,
# change it in `artifact_ops.py` so `approve` / `transition` / the future
# `--lite` and `--auto` flags share the same guard surface.
from artifact_ops import (  # noqa: E402  (sys.path mutation precedes import)
    classify_intent_diff,
    editorial_amend,
)

__all__ = ["classify_intent_diff", "editorial_amend"]
