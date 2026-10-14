# Sync Mode (COMPLETE — post-completion cleanup)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. The Intent has completed (ADR-057 — Intents terminate at `COMPLETE`, not `LOCKED`); `--sync` is the structured way to handle the minor non-substantive cleanups that surface only after the work lands.

### Step 1: Validate

1. File exists; Status is `COMPLETE`. Refuse with the expected status if not — substantive changes on a non-`COMPLETE` Intent route through `--amend`; sync is for the post-completion tail only.
2. The `## Post-implementation sync` section exists. If absent (older Intent that predates the template revision), add the section with the template-empty shape and continue.

### Step 2: Walk the existing checklist

For each bullet currently under `## Post-implementation sync`:

1. Read the bullet text.
2. Determine whether the item is **complete** (the doc was edited, the test was promoted, the cross-ref now resolves):
   - If the bullet describes a file edit, `git log -1 --since="<completion-date>" -- <file>` is non-empty.
   - If the bullet describes a test-promotion candidate, the test now exists at the promotion target path.
   - If the bullet describes a cross-reference, the referenced artifact exists.
3. If complete, prefix the bullet with `[x] `; otherwise leave as `[ ] `. Add a short one-line completion note where useful (e.g., `— done in commit <sha>`).

### Step 3: Discover new sync items

Walk these signals and propose new bullets if they surface:

- **Durable specs.** For each child IB, check its `**Spec impact:**` specs were updated (its completion gate enforced this) and that any WS example or AE description the delivery made stale is corrected; a stale one → a bullet.
- **Cross-reference rot.** Grep `dekspec/dekspec-operating-guide.md` and `AGENTS.md` for references to artifacts this Intent renamed / split. Any obsolete reference → a bullet.
- **WS docstring lag.** If any Working Spec listed in `Layer impact analysis` has a `## Example` or `## Test Hooks` section that names a file the Intent renamed, → a bullet.

Each new bullet should be specific and actionable: `[ ] dekspec/working-specs/WS-007.md §Example references services/foo.py — Intent moved it to services/foo_v2.py; update the example.`

### Step 4: Apply edits

`--sync` edits the body of a `COMPLETE` Intent via the Edit tool. A `COMPLETE`
Intent is a historical record, not a frozen artifact, so the
`pretooluse-locked-guard` hook (ds-k24i) — which blocks only `LOCKED` artifacts —
does not fire on it. Edit directly; no exemption marker is needed.

For each bullet the engineer wants resolved in this sync session:

1. Run the matching small edit (Edit tool — single-file scope per bullet).
2. Mark the bullet `[x]` with the commit-equivalent description.

Refuse to apply any edit that would touch a file outside the original Intent's `Components affected:` glob set + `dekspec/` content paths. Substantive scope expansion goes through `--amend`, not `--sync`.

### Step 5: Log and exit

1. Update Modified date.
2. Append an Amendment Log entry: `| <date> | Editorial | Sync session: marked N bullets complete, added M new bullets, applied K edits via /write-intent --sync | <engineer-or-agent> |`
3. Save.
4. Surface a closing summary: how many items were marked done, how many were added, how many remain open.

**End of Sync Mode.**
