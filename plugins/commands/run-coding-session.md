
## IB lifecycle transitions (MSN-017 / INT-123)

> Added by **INT-123** (LOCKED 2026-05-30). The run-coding-session command emits IB lifecycle status transitions after each bead's test run; failure routes through the INT-121 Python action-handler registry.

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
