"""Python action-handler registry (MSN-017 / INT-121). Materializes the
INT-108 markdown contract (`plugins/dekspec/skills/_lib/action-handlers.md`).

Three failure pairs from ADR-026 each get exactly one registered handler:

    REVIEW_IB  → REVIEW_IB_FAIL  → handlers/review_ib_fail.py
    TESTPASS   → TESTFAIL        → handlers/testfail.py
    REVIEW_PR  → REVIEW_PR_FAIL  → handlers/review_pr_fail.py

The orchestration shell (INT-105 LOCKED) emits FAIL verdicts; the IB
state machine reaches `dispatch(fail_state, context)` on every
transition into one of the three FAIL states.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes — the handler I/O contract per INT-108.
# ---------------------------------------------------------------------------
@dataclass
class HandlerContext:
    """Input bundle handed to a registered handler. Fields mirror the
    INT-108 framework contract."""

    ib_id: str
    ib_path: str
    sidecar_review_path: str
    audit_doctor_snapshot_sha: str
    mode: str  # "RECOMMEND" | "MIXED" | "AUTO"
    coding_session_ref: Optional[str]
    ib_branch: str


@dataclass
class HandlerResult:
    """Return value from a registered handler."""

    transition: str  # "advance" | "hold" | "abort"
    staged_artifacts: dict = field(default_factory=dict)
    summary: str = ""


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------
class ConflictingHandlerError(RuntimeError):
    """Raised when register() is called with a different handler for an
    already-registered FAIL state. The framework refuses silent overrides."""


class UnregisteredFailStateError(RuntimeError):
    """Raised when dispatch() is called for a FAIL state with no
    registered handler. Better to abort than dispatch a half-broken
    pipeline."""


# ---------------------------------------------------------------------------
# Registry — module-level singleton. Tests clear via `_registry.clear()`.
# ---------------------------------------------------------------------------
_registry: dict[str, str] = {}


def register(fail_state: str, handler_path_or_module: str) -> None:
    """Register a handler against a FAIL state.

    `handler_path_or_module` is either an absolute filesystem path to a
    Python module (e.g. `/abs/path/handlers/review_ib_fail.py`) or a
    dotted module path (e.g. `dekspec.action_handlers.handlers.review_ib_fail`).
    Idempotent on identical re-registration; raises
    :class:`ConflictingHandlerError` on a different handler.
    """
    existing = _registry.get(fail_state)
    if existing is None:
        _registry[fail_state] = handler_path_or_module
        return
    if existing == handler_path_or_module:
        return  # idempotent
    raise ConflictingHandlerError(
        f"FAIL state {fail_state!r} already registered to {existing!r}; "
        f"refusing silent override with {handler_path_or_module!r}."
    )


def dispatch(fail_state: str, context: HandlerContext) -> HandlerResult:
    """Look up the registered handler for `fail_state` and call its
    `handle(context)` entry point.

    Raises :class:`UnregisteredFailStateError` if no handler is
    registered. The IB state machine commits the FAIL transition
    BEFORE calling dispatch — a handler crash leaves the FAIL state
    standing for operator intervention.
    """
    handler_ref = _registry.get(fail_state)
    if handler_ref is None:
        raise UnregisteredFailStateError(
            f"No handler registered for FAIL state {fail_state!r}."
        )
    handler_module = _load_handler(handler_ref)
    if not hasattr(handler_module, "handle"):
        raise RuntimeError(
            f"Handler module {handler_ref!r} does not expose handle(context)."
        )
    return handler_module.handle(context)


def _load_handler(ref: str):
    """Load a handler module by filesystem path or dotted module path."""
    path = Path(ref)
    if path.exists() and path.suffix == ".py":
        spec = importlib.util.spec_from_file_location(
            f"_action_handler_{path.stem}", str(path)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    # Dotted module path fallback.
    return importlib.import_module(ref)
