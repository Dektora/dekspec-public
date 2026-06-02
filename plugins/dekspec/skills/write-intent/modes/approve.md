# Approve Mode

[← back to dispatcher](../SKILL.md)


`--approve` records a peer-review approval signature on an Intent under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the Intent's `## Amendment Log` table — it does **not** flip Status.

Run the shared deterministic helper:

```
python ../_lib/scripts/artifact_ops.py approve <Intent-path> --target-status <STATUS>
```

`<STATUS>` is the transition the signature authorizes (e.g. `ACCEPTED` or `LOCKED`). The script resolves the reviewer email from `git config user.email` (override with `--engineer <email>`) and appends a row of the form `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`, then bumps `Modified`. The `T-APPROVAL-GATE` audit rule counts these rows under the `team` profile; once enough signatures are present the Intent may walk the gated transition. Under the default `v1` profile the rule is silent. Inline mode — no fan-out.
