"""ADR-046 migration: relabel terminal `LOCKED` artifacts by nature.

Work items (Intent) → `COMPLETE`; living references / consumed-once specs
(Working Spec, Architecture Element, Implementation Brief) → `ACCEPTED`.
Decision/contract kinds (Constitution, System Vision, ADR, Interface Contract)
keep `LOCKED` and are left untouched. `DEPRECATED`/`SUPERSEDED` off-ramps are
untouched.

Idempotent: an artifact already at its new terminal is skipped. Only the
`## Status` section value is rewritten — never `LOCKED` mentions in prose.
Consumers run this against their own `dekspec/` tree via `dekspec migrate`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# canonical dir (relative to the dekspec/ root) -> new terminal for LOCKED
_DIR_TO_NEW_TERMINAL: dict[str, str] = {
    "intents": "COMPLETE",
    "working-specs": "ACCEPTED",
    "architecture-elements": "ACCEPTED",
    "impl-briefs": "ACCEPTED",
}

# Rewrites only the authored Status value, leaving any `LOCKED` token elsewhere
# in the body alone. Two authored forms: the `## Status` section (Intent/WS/AE)
# and the inline `**Status:** LOCKED` meta-line (IB). Both are matched.
_STATUS_LOCKED = re.compile(r"(^##\s*Status\s*\n\s*\n)LOCKED\b", re.MULTILINE)
_STATUS_LOCKED_INLINE = re.compile(r"(^\*\*Status:\*\*[ \t]*)LOCKED\b", re.MULTILINE)


@dataclass
class MigrationResult:
    migrated: list[str]   # relative paths flipped
    skipped: int          # already at new terminal / not LOCKED


def migrate(dekspec_root: Path) -> MigrationResult:
    """Relabel every LOCKED work-item/spec artifact under ``dekspec_root``."""
    dekspec_root = Path(dekspec_root)
    migrated: list[str] = []
    skipped = 0
    for subdir, new_terminal in _DIR_TO_NEW_TERMINAL.items():
        root = dekspec_root / subdir
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if "provisional" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            new_text, n = _STATUS_LOCKED.subn(r"\1" + new_terminal, text)
            new_text, n2 = _STATUS_LOCKED_INLINE.subn(r"\1" + new_terminal, new_text)
            if n or n2:
                path.write_text(new_text, encoding="utf-8")
                migrated.append(str(path.relative_to(dekspec_root)))
            else:
                skipped += 1
    return MigrationResult(migrated=migrated, skipped=skipped)
