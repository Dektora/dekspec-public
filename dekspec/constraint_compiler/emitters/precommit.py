"""Security Profile mid-layer pre-commit emitter (WS-019 BR1 / BR3 / BR6 / BR7).

Compiles a parsed Security Profile IR into a YAML-shaped string suitable
for inclusion in a consumer's ``.pre-commit-config.yaml``. The emitter:

  - reads ``ir["sast_tools"]`` (typed-record array of ``{name, language,
    ruleset}`` dicts per WS-017's locked schema) and produces a ``repos:``
    list with one entry per declared SAST tool (BR3 per-tool coverage);
  - skips DAST tools — they require a running deployment, not a static
    pre-commit hook, so they belong in the hard-layer CI gate emitter
    instead (BR3 second invariant);
  - is a pure function — no I/O, no global state mutation; the IR dict is
    treated read-only (BR6 byte-stable determinism);
  - raises a typed ``MissingRequiredFieldError`` (subclass of
    ``SecurityProfileEmitterError``) when a required field is missing
    from a tool entry — the message names the JSON-path-style locator
    (``sast_tools[<i>].<field>``) so the operator can fix the SP markdown
    without diffing YAML byte-by-byte (BR7).

Per WS-019 §Domain Constraints "Determinism mechanism", emission goes
through ``yaml.safe_dump(..., sort_keys=False, default_flow_style=False)``
paired with explicit insertion-ordered intermediate dict construction; no
wall-clock, no random, no set-derived iteration. Two consecutive calls on
the same IR return byte-equal strings.

Per WS-019 §Domain Constraints "One-way dependency", this module MUST NOT
import from ``tooling.dekspec.fidelity_audit`` (the audit engine consumes
emitter output, not the other way around — ADR-004).
"""

from __future__ import annotations

from typing import Any

import yaml


class SecurityProfileEmitterError(Exception):
    """Base class for typed errors raised by the Security Profile emitters.

    Subclasses surface specific failure modes (``MissingRequiredFieldError``
    for IR shape violations; ``UnsupportedPlatformError`` for the V1
    github_actions-only platform discriminator in the sibling
    ``ci_gates.py`` module). The IB-032 test suite asserts specific
    subclasses are raised and that messages contain the load-bearing
    locators / supported-value lists.
    """


class MissingRequiredFieldError(SecurityProfileEmitterError):
    """Raised when an emitter encounters an SP IR with a missing required
    field (e.g., ``sast_tools[0].name``, ``sast_tools[0].ruleset``).

    The message format pins a JSON-path-style locator
    (``sast_tools[<i>].<field>``) so the operator can locate the bad row
    in the SP markdown without scanning the emitted YAML. Always raised
    in preference to a bare ``KeyError`` / ``TypeError`` so the operator's
    stack trace surfaces the contract violation, not a Python-level
    accident (WS-019 BR7).
    """


def emit_security_profile_precommit(ir: dict[str, Any]) -> str:
    """Emit a Security Profile IR as a ``.pre-commit-config.yaml`` fragment string.

    Returns a UTF-8 YAML string with a top-level ``repos:`` list, one entry
    per declared SAST tool, in the IR's declared order. ``yaml.safe_load``
    on the result returns a dict containing ``{"repos": [...]}``.

    Raises ``MissingRequiredFieldError`` (a ``SecurityProfileEmitterError``
    subclass) when ``sast_tools`` is absent or any tool row is missing the
    required ``name`` or ``ruleset`` fields. The error message names the
    offending JSON-path locator.
    """
    sast_tools = ir.get("sast_tools")
    if sast_tools is None:
        raise MissingRequiredFieldError(
            "missing required field: sast_tools (the mid-layer pre-commit "
            "emitter requires the SP IR to declare a sast_tools[] array; "
            "an explicit empty list `sast_tools: []` is acceptable and "
            "produces an empty repos: list)"
        )

    repos: list[dict[str, Any]] = []
    for i, tool in enumerate(sast_tools):
        name = _require_field(tool, "name", f"sast_tools[{i}].name")
        ruleset = _require_field(tool, "ruleset", f"sast_tools[{i}].ruleset")
        repos.append({
            "repo": "local",
            "hooks": [
                {
                    "id": name,
                    "name": name,
                    "entry": name,
                    "language": "system",
                    "args": ["--config", ruleset],
                }
            ],
        })

    snippet = {"repos": repos}
    return yaml.safe_dump(
        snippet,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )


def _require_field(tool: Any, field: str, locator: str) -> Any:
    """Return ``tool[field]`` or raise ``MissingRequiredFieldError`` naming the locator.

    Defends against both the "tool is not a dict" case (raises with the
    locator naming the offending row) and the "tool is a dict but the
    field key is absent" case (same locator). Empty-string field values
    are accepted — schema-validation upstream catches those; this helper
    only checks structural presence.
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
