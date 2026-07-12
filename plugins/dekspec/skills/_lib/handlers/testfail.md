# testfail handler

> Concrete action handler for the **TESTFAIL** IB lifecycle state. Registers against the INT-108 action-handler framework (`plugins/dekspec/skills/_lib/action-handlers.md`, LOCKED). Per **ADR-026** + **ADR-027** (both LOCKED 2026-05-29). Authored under INT-114.

When an IB transitions to `TESTFAIL` (CI / pytest regressed during IMPLEMENTING), the action-handler framework dispatches this handler with the failing IB's `HandlerContext` + the failing test output. The handler runs `/orchestrate-coding-session --retry <IB-ID>` — re-dispatches the bead set into a fresh coding session with the failure context as input. After the retry session completes (CI green or another TESTFAIL), the handler re-evals: green → transition to TESTPASS; still failing → loop back to IMPLEMENTING with the new failure recorded.

ADR-027 is the LOCKED reversal of the 2026-05-25 E3 retirement of TESTFAIL — that retirement measured an un-engineered world, this handler is the engineered round-trip the retirement note demanded.

## Registration

```python
from dekspec.action_handlers import register

register("TESTFAIL", "dekspec.action_handlers.handlers.testfail")
```

## Handler entry point

```python
def handle(context: HandlerContext) -> HandlerResult:
    # 1. Pull the failing coding-session log from the IB's most recent run.
    session_ref = context.coding_session_ref
    failure_log = read_session_log(session_ref)

    # 2. Re-dispatch the bead set with the failure context as input.
    retry = invoke_exec_coding_session_retry(
        ib_id=context.ib_id,
        prior_session=session_ref,
        failure_context=failure_log,
    )

    # 3. Re-eval the test result after retry completes.
    #    Mode-aware: RECOMMEND stages + signals; AUTO auto-advances on green.
    rerun_verdict = re_eval_tests(retry.session_id)

    if context.mode == "AUTO" and rerun_verdict == "PASS":
        return HandlerResult(
            transition="advance",
            staged_artifacts={"retry_session": retry.session_id,
                              "rerun_verdict": rerun_verdict},
            summary="Auto-advanced TESTFAIL → TESTPASS after retry session passed.",
        )
    if rerun_verdict == "FAIL":
        return HandlerResult(
            transition="hold",
            staged_artifacts={"retry_session": retry.session_id,
                              "rerun_verdict": rerun_verdict,
                              "looped_back_to": "IMPLEMENTING"},
            summary="Retry session still failing; looped back to IMPLEMENTING.",
        )
    # RECOMMEND mode, retry passed but operator must approve.
    return HandlerResult(
        transition="hold",
        staged_artifacts={"retry_session": retry.session_id,
                          "rerun_verdict": rerun_verdict},
        summary="Retry session passed; operator must approve TESTFAIL → TESTPASS.",
    )
```

## Pairing per design substrate

This handler corresponds to row 2 of the action-handler framework's failure-pair table:

| Success state | Failure state | Registered handler |
|---|---|---|
| `TESTPASS` | **TESTFAIL** | `/orchestrate-coding-session --retry` + re-eval |

## Cross-references

- ADR-026 (parent decision for the framework).
- ADR-027 (LOCKED — TESTFAIL un-retirement; this handler is the engineered round-trip).
- INT-108 (LOCKED — the framework this handler registers against).
- INT-110 (LOCKED — TESTFAIL un-retirement impl; this handler is its operational realization).
- INT-118 (three-mode config — supplies `context.mode`).
- Design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Action-handler framework" row 2.
