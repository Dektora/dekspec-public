"""TESTFAIL handler (INT-114 markdown contract realized in Python).

Per ADR-026 + ADR-027 the handler invokes `/exec-coding-session
--retry` with the failing coding session's context + re-evals.
RECOMMEND mode stages + signals; AUTO advances on retry pass.
"""
from __future__ import annotations


def handle(context):
    import importlib.util
    from pathlib import Path

    import sys
    registry_path = Path(__file__).resolve().parent.parent / "__init__.py"
    mod_name = "_ah_for_handler"
    spec = importlib.util.spec_from_file_location(mod_name, str(registry_path))
    registry = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = registry
    spec.loader.exec_module(registry)
    HandlerResult = registry.HandlerResult

    retry_plan = (
        f"/exec-coding-session --retry {context.ib_id} "
        f"(prior-session: {context.coding_session_ref or '<unknown>'})"
    )

    if context.mode == "AUTO":
        return HandlerResult(
            transition="advance",
            staged_artifacts={
                "retry_plan": retry_plan,
                "next_action": "re-eval test result; advance on green",
            },
            summary="AUTO: dispatched retry session; advance on green re-eval.",
        )

    return HandlerResult(
        transition="hold",
        staged_artifacts={
            "retry_plan": retry_plan,
            "operator_action": (
                f"Run `{retry_plan}`; on green, mark TESTPASS; on red, "
                "loop back to IMPLEMENTING with new failure recorded."
            ),
        },
        summary=(
            "RECOMMEND: staged /exec-coding-session --retry; "
            "operator drives re-eval."
        ),
    )
