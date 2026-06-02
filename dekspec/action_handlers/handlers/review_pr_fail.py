"""REVIEW_PR_FAIL handler (INT-115 markdown contract realized in Python).

Per ADR-026 the handler invokes `/write-ibs --revise` + drives NEW
commits on top of the IB branch + re-fires `/dekspec:review-pr`.
Distinct from REVIEW_IB_FAIL: this operates on a post-implementation
surface (the diff already exists; commits land on top).
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

    # Seed the PR with located findings before any fix lands: /code-review
    # --comment posts line-anchored inline comments the fixer acts on, paired
    # with the REVIEW_PR sidecar verdict. Effort comes from the pre-flight
    # PR-size signal (medium default; high/max for a dense diff).
    seed_step = "/code-review <effort> --comment <PR-#>"
    revise_plan = (
        f"/write-ibs --revise {context.ib_id} + new commits on "
        f"{context.ib_branch} (notes-source: {context.sidecar_review_path})"
    )

    if context.mode == "AUTO":
        return HandlerResult(
            transition="advance",
            staged_artifacts={
                "seed_step": seed_step,
                "revise_plan": revise_plan,
                "next_action": "/dekspec:review-pr <PR-#> for re-eval",
            },
            summary=(
                "AUTO: seeded /code-review --comment, revised IB + landed "
                "follow-up commits + re-fired REVIEW_PR."
            ),
        )

    return HandlerResult(
        transition="hold",
        staged_artifacts={
            "seed_step": seed_step,
            "revise_plan": revise_plan,
            "operator_action": (
                f"Run `{seed_step}` to post inline findings on the PR; then "
                f"`{revise_plan}`. Review-fix loop: read the PR diff first; "
                "fix only real, relevant findings (no unrelated rewrites); "
                "add/update a test per bug fix; run the tests; land follow-up "
                "commits on the IB branch; end with a summary of resolved "
                "items; stop when clean or human-blocked; then re-fire "
                "`/dekspec:review-pr <PR-#>`."
            ),
        },
        summary=(
            "RECOMMEND: staged /code-review --comment seed + /write-ibs "
            "--revise + grep-loop fix plan; operator drives commits + re-fire."
        ),
    )
