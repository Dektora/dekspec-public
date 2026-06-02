# review_pr_fail handler

> Concrete action handler for the **REVIEW_PR_FAIL** IB lifecycle state. Registers against the INT-108 action-handler framework (`plugins/dekspec/skills/_lib/action-handlers.md`, LOCKED). Per **ADR-026** (LOCKED 2026-05-29). Authored under INT-115.

When an IB transitions to `REVIEW_PR_FAIL` (the REVIEW_PR verdict from `/dekspec:review-pr` came back NO-GO on the IB-aggregate PR diff), the action-handler framework dispatches this handler with the failing IB's `HandlerContext`. The handler runs `/write-ibs --revise <IB-ID>` against the IB body (because the IB itself may need adjustment now that the implementation revealed an issue), drives **new commits** onto the IB branch addressing the review findings, then re-fires `/dekspec:review-pr <PR-#>` for re-evaluation.

This handler differs from REVIEW_IB_FAIL: REVIEW_IB_FAIL acts pre-implementation (no diff exists yet — the revise lands new spec content); REVIEW_PR_FAIL acts post-implementation (a diff already exists — the revise + new commits land on top of it).

## Registration

```python
from dekspec.action_handlers import register

register("REVIEW_PR_FAIL", "dekspec.action_handlers.handlers.review_pr_fail")
```

## Handler entry point

```python
def handle(context: HandlerContext) -> HandlerResult:
    # 1. Parse the sidecar review file from INT-107's /dekspec:review-pr.
    findings = parse_sidecar(context.sidecar_review_path)
    revise_notes = format_revise_notes(findings)

    # 2. Invoke /write-ibs --revise to potentially adjust the IB body
    #    (the diff revealed something the IB did not anticipate).
    revise_result = invoke_write_ibs_revise(
        ib_id=context.ib_id,
        ib_path=context.ib_path,
        notes=revise_notes,
    )

    # 3. Drive new commits on the IB branch addressing the findings.
    #    Today RECOMMEND-only: stage the commits + signal operator.
    #    Tomorrow AUTO: dispatch a coding session for the new commits on top.
    if context.mode == "AUTO":
        new_commits = dispatch_followup_commits(
            ib_id=context.ib_id,
            branch=context.ib_branch,
            findings=findings,
        )
        # Re-fire REVIEW_PR after the new commits land.
        rerun = refire_review_pr(context.pr_number)
        return HandlerResult(
            transition="advance" if rerun.verdict == "GO" else "hold",
            staged_artifacts={"revise_diff": revise_result.diff,
                              "new_commits": new_commits,
                              "rerun_verdict": rerun.verdict},
            summary="Auto-revised IB + landed new commits on top + re-fired REVIEW_PR.",
        )
    return HandlerResult(
        transition="hold",
        staged_artifacts={"revise_diff": revise_result.diff,
                          "follow_up_plan": describe_followup_plan(findings)},
        summary=(
            "Staged /write-ibs --revise + drafted follow-up commit plan; "
            "operator drives commits on top of the IB branch then re-fires REVIEW_PR."
        ),
    )
```

The "new commits on top" pattern is what distinguishes this handler from REVIEW_IB_FAIL — the IB branch already carries the implementation; addressing the review means adding to it, not replacing it. The action-handler framework's HandlerContext field `ib_branch` provides the target for the additional commits on top.

## Review-fix loop discipline (grep-loop)

The "new commits on top" step is a **review-fix loop**, not a one-shot patch: review → feed findings back → fix → re-run tests → re-review → repeat until clean or blocked. The full discipline (the six review-fix rules, the PR-size pre-flight, the human guardrails + common pitfalls, and the dekspec REVIEW_PR bindings) is the dekspec-owned vendored workflow at [`_lib/grep_loop_review_workflow.md`](../grep_loop_review_workflow.md) (MIT, adapted from the David Ondrej / Michael Shimeles `grep-loop-review-workflow` notes) — follow it here. In brief, the dekspec bindings are:

- **Seed first** with `/code-review <effort> --comment <PR-#>` (inline PR comments). The REVIEW_PR sidecar (`context.sidecar_review_path`) supplies the lens verdict + the surfaced (≥80) findings; `/code-review --comment` supplies the line-level diff findings — the fixer addresses both. Pick `<effort>` from the `/dekspec:review-pr` PR-size signal (`medium` default, `high`/`max` for a dense diff).
- **Land follow-up commits on `context.ib_branch`** (commits on top, not a replacement), then re-fire `/dekspec:review-pr <PR-#>`.
- **RECOMMEND-only at landing (ADR-026):** the handler stages the plan + commits; the operator drives the commits + re-fire. The same discipline is what an AUTO-mode dispatch would follow once thresholds are committed.

## Pairing per design substrate

This handler corresponds to row 3 of the action-handler framework's failure-pair table:

| Success state | Failure state | Registered handler |
|---|---|---|
| `REVIEW_PR` | **REVIEW_PR_FAIL** | `/write-ibs --revise` + new commits + re-fire REVIEW_PR |

## Cross-references

- ADR-026 (parent decision).
- INT-108 (LOCKED — the framework this handler registers against).
- INT-107 (LOCKED — REVIEW_PR skill that writes the sidecar file this handler consumes).
- INT-118 (three-mode config — supplies `context.mode`).
- Design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Action-handler framework" row 3.
