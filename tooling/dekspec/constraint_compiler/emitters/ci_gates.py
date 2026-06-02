"""Security Profile hard-layer CI-gate emitter (WS-019 BR2 / BR4 / BR5 / BR6 / BR7).

Compiles a parsed Security Profile IR into a YAML-shaped string suitable
for inclusion in a consumer's ``.github/workflows/security.yml``. The
emitter:

  - reads ``ir["sast_tools"]`` AND ``ir["dast_tools"]`` (typed-record
    arrays per WS-017's locked schema) and produces a ``jobs:`` map with
    one entry per declared SAST + DAST tool (BR4 per-tool coverage);
  - SAST jobs emit first (in IR order), DAST jobs second (in IR order) —
    this order is locked for determinism (BR6);
  - accepts ``platform="github_actions"`` ONLY in V1; any other value
    raises a typed ``UnsupportedPlatformError`` whose message names both
    the offending value and the V1 supported list (BR5);
  - is a pure function — no I/O, no IR mutation; ``yaml.safe_dump`` with
    ``sort_keys=False, default_flow_style=False`` for byte-stable output
    (BR6);
  - raises a typed ``MissingRequiredFieldError`` (imported from the
    sibling ``precommit.py`` module) when any required field is missing,
    naming the JSON-path locator (BR7).

Per WS-019 §Domain Constraints "One-way dependency", this module MUST NOT
import from ``tooling.dekspec.fidelity_audit`` (ADR-004).
"""

from __future__ import annotations

from typing import Any

import yaml

from .precommit import MissingRequiredFieldError, SecurityProfileEmitterError


# V1 supported platforms — exactly one entry. V2 (GitLab CI / Bitbucket
# Pipelines) extends this set behind a follow-on Intent (MSN-003 §Notes
# OI-2) and ships with its own per-platform emission shape — for now any
# other value raises UnsupportedPlatformError.
_SUPPORTED_PLATFORMS: tuple[str, ...] = ("github_actions",)


class UnsupportedPlatformError(SecurityProfileEmitterError):
    """Raised when the hard-layer emitter is called with a ``platform``
    value not in the V1 supported list.

    The message contains the offending value verbatim AND the literal
    string ``github_actions`` (the V1 supported list's sole entry) so the
    operator sees both what they passed and what they should have passed.
    The check happens BEFORE any IR-shape inspection so a bad platform
    short-circuits with a clear error rather than surfacing as an
    unrelated missing-field failure later.
    """


def emit_security_profile_ci_gates(
    ir: dict[str, Any], platform: str = "github_actions"
) -> str:
    """Emit a Security Profile IR as a ``.github/workflows/security.yml`` fragment string.

    Returns a UTF-8 YAML string with top-level keys ``name:``, ``on:``,
    and ``jobs:`` (the ``jobs:`` value is a mapping, one entry per
    declared SAST + DAST tool). ``yaml.safe_load`` on the result returns
    a dict containing those three top-level keys.

    The default ``platform="github_actions"`` is the only V1 supported
    value; passing any other value raises ``UnsupportedPlatformError``.

    Raises ``MissingRequiredFieldError`` when any tool entry is missing
    its required ``name`` field. The error message names the offending
    locator (e.g., ``sast_tools[0].name`` or ``dast_tools[1].name``).
    """
    if platform not in _SUPPORTED_PLATFORMS:
        raise UnsupportedPlatformError(
            f"unsupported platform {platform!r}: V1 supports only "
            f"{list(_SUPPORTED_PLATFORMS)} (e.g., platform='github_actions'). "
            f"GitLab CI / Bitbucket Pipelines support is tracked under a "
            f"follow-on Intent (MSN-003 §Notes OI-2)."
        )

    sast_tools = ir.get("sast_tools")
    if sast_tools is None:
        raise MissingRequiredFieldError(
            "missing required field: sast_tools (the hard-layer CI-gate "
            "emitter requires the SP IR to declare a sast_tools[] array; "
            "an explicit empty list `sast_tools: []` is acceptable)"
        )
    dast_tools = ir.get("dast_tools")
    if dast_tools is None:
        raise MissingRequiredFieldError(
            "missing required field: dast_tools (the hard-layer CI-gate "
            "emitter requires the SP IR to declare a dast_tools[] array; "
            "an explicit empty list `dast_tools: []` is acceptable)"
        )

    jobs: dict[str, dict[str, Any]] = {}
    for i, tool in enumerate(sast_tools):
        name = _require_field(tool, "name", f"sast_tools[{i}].name")
        jobs[name] = _build_job(name)
    for i, tool in enumerate(dast_tools):
        name = _require_field(tool, "name", f"dast_tools[{i}].name")
        # Disambiguate if a DAST tool collides with a SAST tool name —
        # this should not happen in practice (engineer judgment in SP
        # authoring catches it), but defensively suffix `-dast` so both
        # land cleanly in the jobs: map rather than the SAST entry
        # being silently overwritten.
        job_key = name if name not in jobs else f"{name}-dast"
        jobs[job_key] = _build_job(name)

    snippet = {
        "name": "Security",
        "on": {
            "push": {"branches": ["main"]},
            "pull_request": {"branches": ["main"]},
        },
        "jobs": jobs,
    }
    return yaml.safe_dump(
        snippet,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )


def _build_job(tool_name: str) -> dict[str, Any]:
    """Build a single GitHub Actions job spec invoking ``tool_name``."""
    return {
        "runs-on": "ubuntu-latest",
        "steps": [
            {"uses": "actions/checkout@v4"},
            {"name": f"Run {tool_name}", "run": tool_name},
        ],
    }


def _require_field(tool: Any, field: str, locator: str) -> Any:
    """Return ``tool[field]`` or raise ``MissingRequiredFieldError`` naming the locator.

    Mirrors the helper in ``precommit.py`` (kept local rather than
    re-exported to avoid a private-helper import path; the function is
    tiny and the duplication is intentional).
    """
    if not isinstance(tool, dict):
        raise MissingRequiredFieldError(
            f"missing required field: {locator} "
            f"(row is not a dict: {type(tool).__name__})"
        )
    if field not in tool:
        raise MissingRequiredFieldError(
            f"missing required field: {locator}"
        )
    return tool[field]
