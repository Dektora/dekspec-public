"""Mission IR migrations.

First real schema-change migration to land in dekspec. Captures the
ds-zuy schema-shape work that splits prose `rollback_plan` and
`kill_criteria` into structured cmd-check predicates (parallel to
`mission_verification`).

Today: one migration, `0.1.0 → 0.2.0`. Forward only.

Companion markdown migration (advisory) lives in
`tooling/dekspec/migrations/mission_markdown.py`.
"""
from __future__ import annotations

from typing import Any

from . import Migration, default_registry

_LEGACY_ROLLBACK_PLACEHOLDER_CMD = "echo SKIP_LEGACY_ROLLBACK"
_LEGACY_KILL_PLACEHOLDER_CMD = "echo SKIP_LEGACY_KILL"


def _v0_1_0_to_v0_2_0(ir: dict[str, Any]) -> dict[str, Any]:
    """Reshape `rollback_plan` (string → {trigger, steps}) and
    `kill_criteria` (list[str] → list[{name, cmd}]).

    Old prose content is preserved so nothing is silently lost:
      - `rollback_plan` prose moves into the new `trigger` field; a
        sentinel `steps[0] = {name: "_legacy_prose", cmd: "echo
        SKIP_LEGACY_ROLLBACK"}` lands in `steps` so the IR validates
        against the v0.2.0 schema AND a runner attempting auto-rollback
        fails loud rather than silently no-oping.
      - `kill_criteria` bullets become one `_legacy_prose_N` entry each,
        with the prose copied into `name` for retrieval and the same
        sentinel cmd.

    The IR is otherwise unchanged. Input dict is not mutated.
    """
    out = dict(ir)

    raw_rollback = ir.get("rollback_plan")
    if isinstance(raw_rollback, str):
        prose = raw_rollback.strip()
        if prose:
            out["rollback_plan"] = {
                "trigger": prose,
                "steps": [{
                    "name": "_legacy_prose",
                    "cmd": _LEGACY_ROLLBACK_PLACEHOLDER_CMD,
                }],
            }
        else:
            out.pop("rollback_plan", None)
    # If rollback_plan is already structured (dict) or absent, leave it.

    raw_kill = ir.get("kill_criteria")
    if isinstance(raw_kill, list) and raw_kill and all(
        isinstance(item, str) for item in raw_kill
    ):
        new_kill: list[dict[str, str]] = []
        for i, prose in enumerate(raw_kill, start=1):
            new_kill.append({
                "name": f"_legacy_prose_{i}: {prose.strip()}"[:200],
                "cmd": _LEGACY_KILL_PLACEHOLDER_CMD,
            })
        out["kill_criteria"] = new_kill
    # If kill_criteria is already structured or absent, leave it.

    out["ir_schema_version"] = "0.2.0"
    return out


default_registry.register(Migration(
    artifact_type="mission",
    from_version="0.1.0",
    to_version="0.2.0",
    migrate=_v0_1_0_to_v0_2_0,
    description=(
        "ds-zuy: rollback_plan (prose) + kill_criteria (string list) → "
        "structured cmd-check predicates parallel to mission_verification."
    ),
))


__all__ = ["_v0_1_0_to_v0_2_0"]
