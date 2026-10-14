"""Validate the installed Spec S0 boundary before dependent work."""
from __future__ import annotations

import importlib
import inspect
from types import ModuleType

COMPAT_VERSION = "structural3-compat-v1"


class SpecUnavailable(RuntimeError):
    """The explicitly provisioned Spec installation cannot support this Builder."""


_ENGINE_METHODS = (
    "contract", "context", "record", "state", "fingerprint", "is_complete", "current_completion",
    "unintegrated_completion_problem", "integration_state", "start", "verify", "evaluate_completion",
    "complete", "reopen", "block", "unblock",
)
_CALLABLES = (
    "Engine", "IBContract", "ContextPacket", "ExecutionRecord", "Event", "RunState", "GateResult",
    "ExecutionSettings", "AgentRole", "Missing", "TargetReadiness", "Readiness", "DeliveryResult",
    "ReadinessTarget", "AuthorityAssessment", "fold", "dependency_ready", "probe_prerequisites",
    "delivery_verify", "delivery_check", "delivery_failure_reasons", "verify_integration",
    "intent_children", "intent_verify", "intent_evaluate", "intent_complete", "intent_reopen",
    "intent_completion", "load_role", "compose", "verdict_policy_problem", "probe_blocker",
    "hooks_installed", "resolve_base", "completion_receipt", "assess_authority",
    "check_delivery_source", "check_test_interpreter",
)
_EXCEPTIONS = (
    "Blocked", "ExecutionError", "IntegrationUnknown", "RoleDefinitionError", "ScopeError", "ContractError",
    "RecordIntegrityError", "ArtifactEditError", "FingerprintError", "PlanError",
)


def require_spec() -> ModuleType:
    """Inspect actual installed capabilities; never acquire or fall back to private code."""
    try:
        spec = importlib.import_module("dekspec.builder_compat")
    except (ImportError, OSError) as exc:
        raise SpecUnavailable(
            f"Spec is unavailable: {exc}. Provision a local Spec wheel providing {COMPAT_VERSION}; "
            "released Spec 0.128.0 does not supply this boundary."
        ) from exc
    if getattr(spec, "COMPAT_VERSION", None) != COMPAT_VERSION:
        raise SpecUnavailable(f"Incompatible Spec: Builder requires {COMPAT_VERSION}; "
                              f"found {getattr(spec, 'COMPAT_VERSION', None)!r}.")
    missing = [name for name in _CALLABLES if not callable(getattr(spec, name, None))]
    for name in _EXCEPTIONS:
        value = getattr(spec, name, None)
        if not isinstance(value, type) or not issubclass(value, Exception):
            missing.append(name)
    for name in ("CODE_REVIEWER_ROLE", "VERIFIER_ROLE", "EXECUTION_DIRNAME", "RETIRED_STATUSES"):
        if not getattr(spec, name, None):
            missing.append(name)
    engine = getattr(spec, "Engine", None)
    missing += [f"Engine.{name}" for name in _ENGINE_METHODS if not callable(getattr(engine, name, None))]
    record = getattr(spec, "ExecutionRecord", None)
    missing += [f"ExecutionRecord.{name}" for name in ("exists", "events", "verify_chain", "append")
                if not callable(getattr(record, name, None))]
    if missing:
        raise SpecUnavailable("Incompatible Spec S0 surface; missing or invalid: " + ", ".join(missing))
    try:
        inspect.signature(spec.Engine).bind(None, spec_root="dekspec", settings=None, base=None)
        inspect.signature(spec.assess_authority).bind(None, [], spec_root="dekspec", base=None, base_name=None)
        inspect.signature(spec.Engine.start).bind(None, "IB-001", "builder", takeover=False, base=None)
        inspect.signature(spec.Engine.verify).bind(None, "IB-001", "builder", base=None, record=True, kind="ib")
        inspect.signature(spec.Engine.evaluate_completion).bind(None, "IB-001", readonly=True, base=None)
        inspect.signature(spec.ExecutionRecord.events).bind(None, strict=True)
        inspect.signature(spec.ExecutionRecord.append).bind(None, "run.requested", "builder", {})
        inspect.signature(spec.compose).bind(policy="", role=None, procedure="", assignment="")
    except (TypeError, ValueError) as exc:
        raise SpecUnavailable(f"Incompatible Spec S0 signatures: {exc}") from exc
    return spec
