# action-handlers

> Action-handler framework registry + dispatch contract for the MSN-017 two-tier review pipeline. Per **ADR-026** (LOCKED 2026-05-29). The three concrete handlers — REVIEW_IB_FAIL (INT-113), TESTFAIL (INT-114), REVIEW_PR_FAIL (INT-115) — register against this framework; the orchestration shell (`review-orchestration.md`, INT-105 LOCKED) dispatches them on IB state-entry to the corresponding FAIL state.

This file is the canonical registry surface. Concrete handlers live under `plugins/dekspec/skills/_lib/handlers/<fail_state>.md` and register against this framework declaratively.

## Failure pairs (the registry's key set)

ADR-026's design substrate names exactly three symmetric failure pairs. Each FAIL state is a first-class IB lifecycle status (INT-102 LOCKED's enum bump) and gets exactly one registered handler:

| Success state | Failure state | Registered handler (per design substrate) |
|---|---|---|
| `REVIEW_IB` | **REVIEW_IB_FAIL** | `/write-ibs --revise` + re-fire REVIEW_IB |
| `TESTPASS` | **TESTFAIL** | `/orchestrate-coding-session --retry` + re-eval |
| `REVIEW_PR` | **REVIEW_PR_FAIL** | seed `/code-review --comment` + `/write-ibs --revise` + new commits (grep-loop fix discipline) + re-fire REVIEW_PR |

The REVIEW_PR_FAIL handler drives a **review-fix loop** that seeds the PR with line-anchored findings via `/code-review <effort> --comment <PR-#>` before fixing — read the diff first, fix only real/relevant findings, a test per fix, summary of resolved items, re-fire until clean. See `handlers/review_pr_fail.md` §Review-fix loop discipline.

The framework's job is to (a) own the registry mapping `{FAIL_state → handler_module_path}`, (b) define the dispatch contract handlers must conform to, (c) provide the trigger seam the IB state machine reaches when an IB transitions to a FAIL state.

## Registry contract

```python
from dekspec.action_handlers import register, dispatch

# Concrete handler registration (called from each handler module on import):
register("REVIEW_IB_FAIL", "dekspec.action_handlers.handlers.review_ib_fail")
register("TESTFAIL",        "dekspec.action_handlers.handlers.testfail")
register("REVIEW_PR_FAIL",  "dekspec.action_handlers.handlers.review_pr_fail")

# Dispatch (called from the IB state machine on state-entry to a FAIL state):
result = dispatch(
    fail_state="REVIEW_IB_FAIL",
    context=HandlerContext(ib=..., sidecar_review_path=..., mode=...),
)
```

`register(state, module_path)` is idempotent — registering the same handler twice is a no-op. Registering a different handler for a state already registered is a hard error (the framework refuses silent overrides).

`dispatch(fail_state, context)` looks up the registered handler, calls it with the context, and returns a `HandlerResult` carrying (a) the transition signal (advance / hold / abort), (b) any new artifacts the handler staged (diff + commit messages for `/write-ibs --revise`, retry-session ID for `/orchestrate-coding-session --retry`), (c) a human-readable summary for the operator's sidecar log.

If no handler is registered for `fail_state`, `dispatch` raises `UnregisteredFailStateError` before the IB state machine commits the transition — better to abort than dispatch a half-broken pipeline.

## Handler input contract

Each handler receives a `HandlerContext` carrying:

| Field | Source | Purpose |
|---|---|---|
| `context.ib_id` | The IB the state machine is operating on | The handler's primary subject. |
| `context.ib_path` | Resolved path to the IB markdown body | For `/write-ibs --revise` invocation. |
| `context.sidecar_review_path` | The sidecar review file the orchestration shell wrote that triggered this FAIL transition | The handler's evidence base — the verdict + findings to act on. |
| `context.audit_doctor_snapshot_sha` | The `dekspec doctor` SHA the review ran against | For correlation with the flywheel + reproducibility. |
| `context.mode` | RECOMMEND / MIXED / AUTO (from `.dekspec/config.yaml` `review.mode` field — INT-118) | Determines whether the handler stages-and-signals (RECOMMEND) or auto-advances (AUTO). |
| `context.coding_session_ref` | Reference to the IB's most recent coding session (for TESTFAIL retry) | Required by `/orchestrate-coding-session --retry`; optional for the other two handlers. |

Handlers are deliberately blind to anything else — they do not see the lens scores, the per-lens findings detail, or the operator's prior decisions. The orchestration shell projects what the handler needs and nothing more.

## Advance contract

Per ADR-026 today is **RECOMMEND-only**: the registered handler stages its action (writes a revise candidate, queues a retry session) and signals the operator via the sidecar log. The IB state machine does not auto-advance; the operator reads the staged change and manually triggers `--testpass` / re-fires REVIEW_IB / etc.

Tomorrow under **AUTO** mode (INT-118 ships the mode plumbing once INT-117's calibration corpus matures): handlers auto-advance when the staged action's preconditions are met (e.g., REVIEW_IB_FAIL handler auto-fires REVIEW_IB once `/write-ibs --revise` lands a new revision and the new revision's preflight passes). Under **MIXED** mode handlers auto-advance per-lens — the operator commits silver thresholds per lens, the handler auto-advances on lenses below silver and escalates on lenses above.

Handlers MUST be mode-aware via `context.mode`. A handler that ignores mode and always auto-advances breaks RECOMMEND-mode operators' expectations and is rejected at framework load time.

## Trigger seam

The framework exposes one entry point — `dispatch(fail_state, context)` — and the IB state machine (in `tooling/dekspec/skills/write-ibs/`) reaches it on every transition where the target state is in `{REVIEW_IB_FAIL, TESTFAIL, REVIEW_PR_FAIL}`. The state machine commits the transition first (the FAIL state is recorded), then dispatches; if dispatch raises, the FAIL state stands and the operator is notified. This ordering matters: a handler crash must not silently lose the FAIL signal.

## Failure modes

- **Unregistered FAIL state** — `UnregisteredFailStateError`. The state machine has tried to dispatch a handler for a state the registry does not know about. Aborts before any IB state change is committed.
- **Duplicate registration with different handler** — `ConflictingHandlerError`. Two modules tried to register different handlers for the same FAIL state. Aborts at framework load.
- **Handler crash** — the FAIL state stands; the sidecar log records the crash + stack; operator notified. No retry loop in the framework itself (the operator decides whether to invoke the handler manually or escalate).

## Cross-references

- ADR-026 (parent decision).
- AE-006 (Skills Library — host AE).
- INT-105 (LOCKED — shared orchestration shell that produces the sidecar review file each handler consumes).
- INT-106, INT-107 (LOCKED — REVIEW_IB / REVIEW_PR skills that write the sidecar files).
- INT-110 (LOCKED — TESTFAIL un-retirement; the TESTFAIL state this framework's handler operates on).
- INT-113 / INT-114 / INT-115 (the three concrete handler Intents that register against this framework).
- INT-118 (three-mode config — supplies `context.mode`).
- Design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Action-handler framework".
