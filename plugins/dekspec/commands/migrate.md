---
description: Run `dekspec migrate` — the consolidated upgrade pipeline (verify vendored drift → migrate-ir JSON → migrate-artifacts markdown), then walk the advisory queue interactively with Claude in the loop. Single-surface end-to-end migration.
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(dekspec migrate:*), Bash(dekspec audit:*), Bash(python:*), Bash(rm:*)
argument-hint: [--at PATH] [--from VERSION] [--to VERSION] [--apply] [--dry-run] [--skip-verify] [--json] [--skip-walker | --walker-only] [--skip <n>] [--auto-approve]
disable-model-invocation: false
---

End-to-end DekSpec migration: CLI pipeline + interactive advisory walker in a single invocation.

## Stages

**Stage 1 — CLI pipeline** (`dekspec migrate`):
- vendor-drift verify — drift between vendored content and installed library (internal stage; no standalone CLI verb)
- migrate-ir — persisted IR JSON schema migrations (dry-run unless `--apply`)
- migrate-artifacts — markdown-artifact migrations; mechanical lands directly, semantic items queue to `dekspec/migration-advisory.json`

**Stage 2 — Advisory walker** (this command body): for each queued semantic change, gather context, draft an edit, show diff, prompt apply/edit/skip/quit. Human-in-the-loop on every semantic change. Walker scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/migrate/advisory_io.py`.

## Steps

1. Parse stage-control flags from `$ARGUMENTS`:
   - `--skip-walker` → run only Stage 1, do not invoke the walker.
   - `--walker-only` → skip Stage 1, jump straight to the walker (forward `--skip <n>` / `--auto-approve` / positional path to Stage 2).
   - `--skip <n>` → walker advance, see Stage 2 below.
   - `--auto-approve` → walker non-interactive, see Stage 2 below.
2. **Stage 1** (unless `--walker-only`): run `dekspec migrate <Stage 1 args>` via Bash. Strip walker-specific flags before invoking. Exit non-zero on the first failing stage.
3. **Stage 2** (unless `--skip-walker`): if `dekspec/migration-advisory.json` exists and is non-empty, walk it per the §Walker workflow below. If the file is absent or empty, print "✓ migration complete — no advisory items" and stop.
4. After both stages: suggest `/dekspec:doctor` to confirm the migrated tree audits clean.

## Walker workflow

The walker is a finite-state loop over the advisory queue. Default is interactive; `--auto-approve` runs the full walk without per-item confirmation (reserved for pre-reviewed queues).

### Phase 1 — Load and validate

1. Determine the advisory path: positional argument if supplied, else `<cwd>/dekspec/migration-advisory.json`.
2. Validate with the helper:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/migrate/advisory_io.py" load <path>
   ```
   On any failure, surface the stderr message and stop. On success, the helper prints the header (versions, generated-at, item count).
3. If `advisories` is empty, prompt "Nothing to do. Delete advisory file? (y/n)" — on `y`, `rm` it; either way, stop.

### Phase 2 — Status (if `--status` was passed)

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/migrate/advisory_io.py" status <path>
```

Emits the `IDX / CHANGE_TYPE / ARTIFACT` progress table. Stop after.

### Phase 3 — Interactive walk

For each advisory item (skipping the first `<n>` if `--skip` was given):

**3.1 — Item header**
```
─────────────────────────────────────────────────────────
ITEM <idx>/<total>: <change_type>
File:        <artifact_path>
Versions:    <from> → <to>
Description: <description>
Hint:        <suggested_transform or "(none)">
─────────────────────────────────────────────────────────
```

**3.2 — Gather context.** Read the artifact file. If `context.line_range` is set, focus on that range; otherwise read the whole file. Grep the consumer repo for one-hop references mentioned in the description; no deeper.

**3.3 — Draft the edit.** Use `Edit` for one-line / small-region changes; read-then-`Write` only when the change is structural. Edit must satisfy the description; on ambiguity, prefer the most conservative interpretation that still meets the stated intent.

**3.4 — Diff preview.** Print:
```
Proposed edit to <artifact_path>:

  - old line content
  + new line content
```

**3.5 — Action prompt.**
```
[a]pply / [e]dit / [s]kip / [q]uit →
```

- **[a]pply**: write the edit. One-line confirmation. Next item.
- **[e]dit**: ask "What should the draft change?" Redraft per guidance. Return to 3.4.
- **[s]kip**: leave file untouched. "skipped — file unchanged". Next item.
- **[q]uit**: write a checkpoint (see Phase 4.B), print resume command, stop.

With `--auto-approve`, skip 3.5 and behave as if `[a]` were pressed.

### Phase 4 — End of queue

**A — Completed cleanly:**
1. Print a summary table (applied / edited / skipped counts).
2. `rm <advisory_path>` (one-shot consumption).
3. Print: `→ Run /dekspec:doctor to confirm the migrated tree audits clean.`

**B — User quit mid-walk:**
1. Write a checkpoint via the helper:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/migrate/advisory_io.py" \
       checkpoint <path> --completed <count of items walked>
   ```
   Helper writes `migration-checkpoint.json` next to the advisory with `{"advisory_path", "items_completed", "saved_at"}` and prints the resume line.
2. Relay the resume line to the operator (`/dekspec:migrate --walker-only --skip <items_completed>`).
3. Do not delete the advisory file.

### Phase 5 — Edge cases

- **Artifact file missing** (advisory references a stale path): warn, mark as skipped, continue.
- **File unreadable / parse error during draft**: surface the error, ask [s]kip or [q]uit. Never swallow silently.
- **User rejects every redraft option on the same item (3 attempts)**: suggest [s]kip and continue.
- **`--skip` larger than queue**: print "nothing left to walk" and stop without writing a checkpoint.

## Implementation notes

- The walker is interactive by design. Don't drive it from CI; `--auto-approve` exists for power users who understand the tradeoff.
- Never apply an edit that contradicts the advisory `description`. If the operator's `[e]dit` guidance asks for something inconsistent, push back once before complying.
- After each applied edit, the artifact is the source of truth. Don't re-read the advisory file mid-walk — the in-memory queue is authoritative.
- Keep prompts terse.

## When to use

- After upgrading the installed `dekspec` library to a new version (the `/dekspec:upgrade` flow chains this command automatically — skippable with `--no-migrate`).
- As a standalone check when investigating drift between vendored content and the installed library.
- For CI: `dekspec migrate --apply --skip-walker` forward-migrates persisted IR + markdown mechanically; the walker stays operator-driven.

## Related

- `dekspec migrate` (CLI) — produces the advisory queue this walker consumes.
- `/dekspec:doctor` — run after the walk to audit the migrated tree.
- `/dekspec:upgrade` — full upgrade flow; usually invokes this command as part of the post-upgrade work.
