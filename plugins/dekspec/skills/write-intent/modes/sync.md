# Sync Mode (LOCKED — post-merge cleanup)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. The Intent has merged and locked; `--sync` is the structured way to handle the minor non-substantive cleanups that surface only after the diff lands.

### Step 1: Validate

1. File exists; Status is `LOCKED`. Refuse with the expected status if not — substantive changes on a non-LOCKED Intent route through `--amend`; sync is for post-merge tail only.
2. The `## Post-implementation sync` section exists. If absent (older Intent that predates the template revision), add the section with the template-empty shape and continue.

### Step 2: Walk the existing checklist

For each bullet currently under `## Post-implementation sync`:

1. Read the bullet text.
2. Determine whether the item is **complete** (the doc was edited, the test was promoted, the cross-ref now resolves):
   - If the bullet describes a file edit, `git log -1 --since="<lock-date>" -- <file>` is non-empty.
   - If the bullet describes a test-promotion candidate, the test now exists at the promotion target path.
   - If the bullet describes a cross-reference, the referenced artifact exists.
3. If complete, prefix the bullet with `[x] `; otherwise leave as `[ ] `. Add a short one-line completion note where useful (e.g., `— done in commit <sha>`).

### Step 3: Discover new sync items

Walk these signals and propose new bullets if they surface:

- **Test promotion.** For each IB consumed by this Intent, check whether the IB's promotion-candidate tests were referenced anywhere via the IB's promotion-refs note. If candidates exist but the corresponding `tests/promoted/<name>.py` does not, add a bullet.
- **Cross-reference rot.** Grep `dekspec/dekspec-operating-guide.md` and `AGENTS.md` for references to artifacts this Intent renamed / split. Any obsolete reference → a bullet.
- **WS docstring lag.** If any Working Spec listed in `Layer impact analysis` has a `## Example` or `## Test Hooks` section that names a file the Intent renamed, → a bullet.

Each new bullet should be specific and actionable: `[ ] dekspec/working-specs/WS-007.md §Example references services/foo.py — Intent moved it to services/foo_v2.py; update the example.`

### Step 4: Apply edits

`--sync` edits the body of a **LOCKED** Intent via the Edit tool, which the
`pretooluse-locked-guard` hook (ds-k24i) blocks by default. Lift the guard for
the duration of this sync's edits by dropping the staleness-guarded exemption
marker, then remove it in Step 5. Before the first Edit:

```bash
touch dekspec/.dekspec-locked-write-allow   # ds-k24i: authorize sync's LOCKED-body edits
```

For each bullet the engineer wants resolved in this sync session:

1. Run the matching small edit (Edit tool — single-file scope per bullet).
2. Mark the bullet `[x]` with the commit-equivalent description.

Refuse to apply any edit that would touch a file outside the original Intent's `Components affected:` glob set + `dekspec/` content paths. Substantive scope expansion goes through `--amend`, not `--sync`.

### Step 5: Log and exit

1. Update Modified date.
2. Append an Amendment Log entry: `| <date> | Editorial | Sync session: marked N bullets complete, added M new bullets, applied K edits via /write-intent --sync | <engineer-or-agent> |`
3. Save.
4. **Remove the LOCKED-write exemption marker** (the guard re-engages immediately; it is staleness-guarded so a forgotten removal expires on its own):

```bash
rm -f dekspec/.dekspec-locked-write-allow   # ds-k24i: re-engage the LOCKED-write guard
```

5. Surface a closing summary: how many items were marked done, how many were added, how many remain open.

**End of Sync Mode.**
