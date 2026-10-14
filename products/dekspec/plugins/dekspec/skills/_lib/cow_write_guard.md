# Write-Time CoW Guard (INT-082 phase 4)

Canonical contract for the copy-on-write guard that runs before a skill edits a
canonical artifact. Cited by the 11 authoring skills; do not restate it in a
skill body.

## Why this file exists

The guard was duplicated inline across 11 skills and three copies had drifted.
`ds-prj-skill-corpus-hardening-ll9k.2` filed that as a **bug**, not a chore:
this is a *guard*, so a drifted copy means the protection behaves differently
depending on which skill you entered through, and nothing detected the
divergence. One of those copies had a real hole — the skill that then owned
both terminology artifacts guarded only `domain-glossary.md`, leaving its
`--log` writes to the corrections log unprotected.

A guard with one text is a guard. Eleven texts are eleven guards.

## The contract

Before any edit to a canonical artifact, consult the guard:

```bash
dekspec library cow-stage <path-to-canonical> [--incubation <slug>] [--at <repo>]
```

If the target path is claimed by a pre-ACCEPTED Intent (DRAFT / PROPOSED) via
that Intent's `Components affected` globs, the verb:

1. Copies the canonical to
   `dekspec/provisional/<incubation-slug>/<KIND>-provisional-<file-slug>.md`.
2. Stamps `replaces: <CANONICAL-ID>` in the frontmatter, so the eventual
   `promote-provisional` run performs a REPLACE — preserving the canonical ID
   — rather than allocating a new one.
3. Returns the new provisional path. Edit that file; the canonical stays frozen.

If the path is **not** claimed by any pre-ACCEPTED Intent, the verb errors
unless you pass an explicit `--incubation <slug>`. That is not a failure: the
canonical-only path is the normal edit flow.

## Skill discipline

Inside a skill body, before any canonical-file `Edit` / `Write` call:

1. Compute the target path you intend to write.
2. Run `dekspec library cow-stage <target-path>` once. Surface the verb's
   stdout to the engineer.
3. **Exit 0** with a provisional path printed → redirect the edit to that path.
4. **Exit 1** (no claim and no `--incubation`) → proceed with the canonical
   edit; it is direct-flow legal.

## The two forms

`ll9k.2` ruled these are two legitimate forms of one contract, not drift. The
difference is only *which path* is computed in step 1.

### kind-dir form

For skills authoring artifacts that live in a per-kind directory under
`dekspec/<kind-dir>/` — the path is derived per invocation from the artifact
being written.

Used by: `write-ae`, `write-intent`, `write-sp`, `write-ic`, `write-ws`,
`write-adr`, `write-ibs`, `write-mission`.

### singleton form

For skills authoring a fixed singleton artifact — the path is a constant, known
before the skill runs, and the skill names it explicitly. A singleton skill that
writes **more than one** file must name every one of them; that omission is the
defect described above.

Used by: `write-constitution` (`dekspec/constitution.md`), `write-sv`
(`dekspec/system-vision.md`), `write-glossary` (`dekspec/domain-glossary.md`),
`write-corrections` (`dekspec/terminology-corrections.md`).

## Recommended skill-side block template

Keep the heading so the contract is discoverable at the point of use, and name
the form plus the path. Nothing else — the contract lives here.

kind-dir:

```markdown
## Write-Time CoW Guard (INT-082 phase 4)

See [`_lib/cow_write_guard.md`](../_lib/cow_write_guard.md) for the canonical contract.

**Form:** kind-dir — canonical artifacts under `dekspec/<kind-dir>/`.
```

singleton:

```markdown
## Write-Time CoW Guard (INT-082 phase 4)

See [`_lib/cow_write_guard.md`](../_lib/cow_write_guard.md) for the canonical contract.

**Form:** singleton — guards `dekspec/constitution.md`.
```

## Audit pairing

`T-COW-CANONICAL-EDITED` (P2, mechanical) fires on every
`git diff --name-only main` entry that is claimed AND lacks a provisional
sibling with `replaces:` set. A skill that skips this guard surfaces as
advisory in the next `dekspec audit linkage` run — it never blocks.

Advisory-but-audited is the deliberate setting: the guard must not stop a
legitimate direct-flow edit, but a bypass must leave a trace.

## Per-skill migration checklist

- [ ] Inline body replaced with the block template above.
- [ ] Form named (`kind-dir` or `singleton`).
- [ ] Singleton skills: **every** guarded path named.
- [ ] Vendored copy updated under `tooling/dekspec/_vendored/skills/` — the
      source and vendored trees drift silently, and PR #136 shipped a rename
      that missed the vendored copy.
- [ ] `scripts/skill_lint.py`, `dekspec audit doctor`, and `pytest -q` clean.

## Reconsideration triggers

- A third form appears (an artifact that is neither kind-dir nor a fixed
  singleton). Document it here; do not fork a skill body.
- `cow-stage`'s exit-code contract changes. Both the contract and the skill
  discipline above are written against exit 0 / exit 1 specifically.
- `T-COW-CANONICAL-EDITED` becomes blocking rather than advisory — the last
  section would then be wrong in a way that matters.
