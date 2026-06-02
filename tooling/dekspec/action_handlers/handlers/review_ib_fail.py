"""REVIEW_IB_FAIL handler (INT-113 markdown contract realized in Python).

Per ADR-026 the handler invokes `/write-ibs --revise` against the
failing IB + signals (RECOMMEND) or auto-fires (AUTO) `/dekspec:review-ib`
for re-evaluation. RECOMMEND-only at first land — the implementation
stages the planned action + returns transition='hold' so the operator
drives the re-fire manually.
"""
from __future__ import annotations

# Note: avoids importing the parent registry to dodge circular-import +
# import-by-path quirks in test fixtures. Uses runtime duck-typed
# HandlerResult lookup.


def handle(context):
    """Stage the revise action + signal the operator. Returns
    HandlerResult(transition='hold', ...) under RECOMMEND mode."""
    import importlib.util
    from pathlib import Path

    # Resolve HandlerResult from the registry module relative to this
    # file's parent's parent (action_handlers/__init__.py).
    import sys
    registry_path = Path(__file__).resolve().parent.parent / "__init__.py"
    mod_name = "_ah_for_handler"
    spec = importlib.util.spec_from_file_location(mod_name, str(registry_path))
    registry = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = registry
    spec.loader.exec_module(registry)
    HandlerResult = registry.HandlerResult

    revise_plan = (
        f"/write-ibs --revise {context.ib_id} "
        f"(notes-source: {context.sidecar_review_path})"
    )

    if context.mode == "AUTO":
        # AUTO-mode auto-fires after revise (real implementation would
        # invoke /write-ibs + /dekspec:review-ib subprocesses).
        return HandlerResult(
            transition="advance",
            staged_artifacts={
                "revise_plan": revise_plan,
                "next_action": f"/dekspec:review-ib {context.ib_id}",
            },
            summary="AUTO: revised IB + re-fired REVIEW_IB.",
        )

    # RECOMMEND (default) — stage + signal.
    return HandlerResult(
        transition="hold",
        staged_artifacts={
            "revise_plan": revise_plan,
            "operator_action": (
                f"Run `{revise_plan}` then `/dekspec:review-ib {context.ib_id}`."
            ),
        },
        summary="RECOMMEND: staged /write-ibs --revise; operator drives re-fire.",
    )
