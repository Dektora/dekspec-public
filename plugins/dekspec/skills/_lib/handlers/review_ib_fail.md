# review_ib_fail handler

> Concrete action handler for the **REVIEW_IB_FAIL** IB lifecycle state. Registers against the INT-108 action-handler framework (`plugins/dekspec/skills/_lib/action-handlers.md`, LOCKED). Per **ADR-026** (LOCKED 2026-05-29). Authored under INT-113.

When an IB transitions to `REVIEW_IB_FAIL` (the REVIEW_IB verdict from `/dekspec:review-ib` came back NO-GO at ≥80 confidence), the action-handler framework dispatches this handler with the failing IB's `HandlerContext`. The handler runs `/write-ibs --revise <IB-ID>` against the IB body, threading the sidecar review's specific findings as revision-notes input. After the revise lands new IB content, the handler signals (RECOMMEND mode) or auto-fires (AUTO mode) `/dekspec:review-ib <IB-ID>` for re-evaluation.

## Registration

```python
from dekspec.action_handlers import register

register("REVIEW_IB_FAIL", "dekspec.action_handlers.handlers.review_ib_fail")
```

Registration is idempotent. The framework refuses any other handler trying to register against `REVIEW_IB_FAIL`.

## Handler entry point

```python
def handle(context: HandlerContext) -> HandlerResult:
    # 1. Read the sidecar review file produced by INT-106's /dekspec:review-ib.
    findings = parse_sidecar(context.sidecar_review_path)

    # 2. Compose revision-notes input from the vetoing lens(es) + their findings.
    revise_notes = format_revise_notes(findings)

    # 3. Invoke /write-ibs --revise on the IB body, threading the notes.
    revise_result = invoke_write_ibs_revise(
        ib_id=context.ib_id,
        ib_path=context.ib_path,
        notes=revise_notes,
    )

    # 4. RECOMMEND mode: stage the revise + signal operator.
    #    AUTO mode: auto-fire /dekspec:review-ib for re-evaluation.
    if context.mode == "AUTO":
        rerun = refire_review_ib(context.ib_id)
        return HandlerResult(
            transition="advance" if rerun.verdict == "GO" else "hold",
            staged_artifacts={"revise_diff": revise_result.diff,
                              "rerun_verdict": rerun.verdict},
            summary="Auto-revised + re-fired REVIEW_IB.",
        )
    return HandlerResult(
        transition="hold",
        staged_artifacts={"revise_diff": revise_result.diff},
        summary="Staged /write-ibs --revise; operator must approve + re-fire REVIEW_IB.",
    )
```

The handler MUST be mode-aware via `context.mode`. A handler that ignores mode and always auto-fires is rejected by the framework at load time.

## Pairing per design substrate

This handler corresponds to row 1 of the action-handler framework's failure-pair table:

| Success state | Failure state | Registered handler |
|---|---|---|
| `REVIEW_IB` | **REVIEW_IB_FAIL** | `/write-ibs --revise` + re-fire REVIEW_IB |

## Cross-references

- ADR-026 (parent decision).
- INT-108 (LOCKED — the framework this handler registers against).
- INT-106 (LOCKED — REVIEW_IB skill that writes the sidecar file this handler consumes).
- INT-118 (three-mode config — supplies `context.mode`).
- Design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Action-handler framework" row 1.
