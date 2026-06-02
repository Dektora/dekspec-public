---
description: Dispatch a parallel coding session — invokes the /exec-coding-session skill (renamed from /run-coding-session in INT-098). Orchestrates parallel sub-agents in isolated worktrees over an unblocked bead set.
allowed-tools: Skill
argument-hint: [<ib-path-or-id> | --package <sha-or-path> | --confirm-dispatch | --dry-run | --help] [optional engineer guidance]
disable-model-invocation: false
---

Invoke the `exec-coding-session` skill to orchestrate a parallel
coding session.

## Steps

1. Invoke the `exec-coding-session` skill via the Skill tool,
   forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill handles all
   dispatch logic (Phase 1–5: discover/claim, dispatch, collect,
   land-the-plane, newly-unblocked).

## Naming note

Renamed from `/run-coding-session` → `/exec-coding-session` in
INT-098 (v0.92.0+). The old slash command no longer exists; the
skill body is unchanged. The IB-lifecycle wiring below was relocated
here from the retired `run-coding-session.md` (ds-jhbw).

## IB lifecycle transitions (MSN-017 / INT-123)

> Added by **INT-123** (LOCKED 2026-05-30). The exec-coding-session command emits IB lifecycle status transitions after each bead's test run; failure routes through the INT-121 Python action-handler registry.

### Test outcome → IB status

| Bead test result | IB transition | Dispatch |
|---|---|---|
| All beads green (CI + pytest pass) | IMPLEMENTING → **TESTPASS** | (state-machine advance per INT-122) |
| Any bead red (CI or pytest fail) | IMPLEMENTING → **TESTFAIL** | `dekspec.action_handlers.dispatch("TESTFAIL", context)` → INT-114 handler (`/exec-coding-session --retry` + re-eval) |

The TESTFAIL transition is per **ADR-027** (LOCKED — TESTFAIL un-retirement at the IB level). The handler dispatch contract is per **INT-121**'s `dekspec.action_handlers` Python module:

```python
from dekspec.action_handlers import dispatch, HandlerContext

# After test result lands red on bead bead-N of IB-NNN:
result = dispatch(
    "TESTFAIL",
    HandlerContext(
        ib_id=ib_id,
        ib_path=ib_path,
        sidecar_review_path=last_sidecar_path,
        audit_doctor_snapshot_sha=audit_sha,
        mode=resolve_mode(".dekspec/config.yaml"),
        coding_session_ref=current_session_id,
        ib_branch=current_branch,
    ),
)
# result.transition = "hold" (RECOMMEND) | "advance" (AUTO on retry green) | "abort"
```

### Retry loop

After the TESTFAIL handler re-runs the session via `/exec-coding-session --retry`:

- Retry green → **TESTPASS** (handler advances on AUTO; operator approves on RECOMMEND).
- Retry red → loop back to **IMPLEMENTING** with the new failure appended to the TESTFAIL records log; sidecar updated.

The retry loop is bounded by operator decision: the framework does not auto-retry indefinitely. Each TESTFAIL → retry round-trip is one handler dispatch.
