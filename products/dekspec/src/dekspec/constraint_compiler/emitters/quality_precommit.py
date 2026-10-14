"""Quality-gate pre-commit emitter (INT-175 / ι2).

Compiles DekSpec's opt-in **Python QUALITY gate** into a
``.pre-commit-config.yaml`` fragment string a consumer can drop into (or
merge into) their repo's pre-commit config. The fragment is built on the
pre-commit framework (NOT Husky / Prettier) and names three hooks:

  - ``ruff``           — the lint/format gate (``ruff check``);
  - ``pytest``         — the test suite gate (``pytest -q``);
  - ``dekspec doctor`` — the DekSpec health/fidelity gate
    (``dekspec doctor --at .``).

Unlike ``precommit.py`` (the Security-Profile-driven SAST emitter), this
emitter is parameterless: the quality gate is a fixed, opinionated hook
set, so ``emit_quality_precommit()`` takes no IR. The sibling static
template ``templates/git-hooks/quality.pre-commit-config.yaml.template``
is the same fragment frozen to disk for the ``setup-dekspec`` installer
(ι1) to drop/merge.

Determinism (mirrors ``precommit.py``'s WS-019 mechanism): emission goes
through ``yaml.safe_dump(..., sort_keys=False, default_flow_style=False)``
over insertion-ordered dicts — no wall-clock, no random, no set-derived
iteration. Two consecutive calls return byte-equal strings.

Idempotency-friendliness (INT-175 Open Issue P3): each hook carries a
stable ``id`` so an upstream append-or-replace-by-id merge never
duplicates. The install-merge itself is ι1's contract, not this module's.

One-way dependency (ADR-004): this module MUST NOT import from
``tooling.dekspec.fidelity_audit`` — the audit engine consumes emitter
output, not the other way around.
"""

from __future__ import annotations

from typing import Any

import yaml

# The fixed, opinionated quality hook set. Insertion order is load-bearing
# for byte-stable determinism. Each entry carries a stable `id` so the
# installer can merge by-id without duplicating (INT-175 P3 open issue).
_QUALITY_HOOKS: tuple[dict[str, Any], ...] = (
    {
        "id": "ruff",
        "name": "ruff",
        "entry": "ruff check",
        "language": "system",
        "pass_filenames": False,
        "always_run": True,
    },
    {
        "id": "pytest",
        "name": "pytest",
        "entry": "pytest -q",
        "language": "system",
        "pass_filenames": False,
        "always_run": True,
    },
    {
        "id": "dekspec-doctor",
        "name": "dekspec doctor",
        "entry": "dekspec doctor --at .",
        "language": "system",
        "pass_filenames": False,
        "always_run": True,
    },
)


def emit_quality_precommit() -> str:
    """Emit the DekSpec quality gate as a ``.pre-commit-config.yaml`` fragment.

    Returns a UTF-8 YAML string with a top-level ``repos:`` list holding a
    single ``local`` repo whose ``hooks`` name ``ruff``, ``pytest``, and
    ``dekspec doctor``. ``yaml.safe_load`` on the result returns a dict
    containing ``{"repos": [{"repo": "local", "hooks": [...]}]}``.

    Parameterless and deterministic: two calls return byte-equal strings.
    """
    snippet = {
        "repos": [
            {
                "repo": "local",
                "hooks": [dict(hook) for hook in _QUALITY_HOOKS],
            }
        ]
    }
    return yaml.safe_dump(
        snippet,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )


__all__ = ["emit_quality_precommit"]
