# Lite Mode (`--lite`)

[← back to dispatcher](../SKILL.md)


Skips the `--analyze` and `/write-code-beads` phases for **single-IU, single-component** Intents and hands the Intent itself directly to `/exec-coding-session` as the work unit. `--testpass` is **retained** — the diff-confinement gate is real and worth preserving even for single-IU work; only the bead ceremony is bypassed.

**Source.** INT-088 IU-2, bead `ds-49mc` (parent critique bead `ds-write-intent-lite-single-iu-path-k5cl`). The `--lite` discipline contract is documented inline (OI-C deferred — no ADR governs this bead beyond ADR-013).

> **Inline execution.** This mode runs directly in the parent context — it does not fan out via the Agent tool. The gate check + frontmatter marker are both deterministic Python in `_lib/scripts/artifact_ops.py`; the routing to `/exec-coding-session` is the same skill-invocation surface the explicit-prompt path uses.

## Refusal contract (hard gates)

`--lite` REFUSES with a named-gate error unless **ALL** of the following hold:

- **`components ≤ 1`** — `## Components affected` resolves to ≤ 1 file glob or named component.
- **`ius ≤ 1`** — `## Layer impact analysis` records exactly 1 Implementation Unit (or none, for a freshly-authored Intent whose layer analysis has not been populated).
- **`adrs = []`** — `## Linked ADRs` section is absent, empty, or contains only `(none)` / `n/a` sentinels.
- **`ics = []`** — `## Linked Interface Contracts` section is absent, empty, or contains only `(none)` / `n/a` sentinels.

Any failing gate triggers a refusal message of the form:

```
--lite refused: gate <gate-name> failed (<reason>). Use full /write-intent without --lite for this Intent.
```

The four gate names (in evaluation order) are `components`, `ius`, `adrs`, `ics`. The first failing gate short-circuits — the Intent is never written, the Amendment Log is never appended.

### Step 1: Gate check

Run the deterministic helper. Surface its stderr to the engineer on non-zero exit and **STOP**:

```bash
python plugins/dekspec/skills/_lib/scripts/artifact_ops.py lite-gate <Intent-path>
```

The helper:

1. Parses `## Components affected`, `## Layer impact analysis`, `## Linked ADRs`, and `## Linked Interface Contracts` from the Intent file.
2. Evaluates the four gates in order (`components`, `ius`, `adrs`, `ics`).
3. On the first failing gate, exits non-zero with the refusal message above.
4. On all-pass, exits 0 with a summary line listing the measured values.

### Step 2: Mark `lite: true` in frontmatter

After the gate check passes, mark the Intent so auditors can identify lite-path Intents. The marker lives in the Intent's YAML frontmatter — when no frontmatter block exists, the helper prepends a minimal one:

```bash
python plugins/dekspec/skills/_lib/scripts/artifact_ops.py lite-mark <Intent-path>
```

The helper is idempotent — re-running it on an already-marked Intent leaves the file byte-equivalent.

### Step 3: Skip `--analyze` + `--decompose` + `/write-code-beads`

These phases are intentionally NOT run on the Lite path:

- **`--analyze` skipped** — single-IU is by definition not OVERSIZED; the analyze-time size-cap re-check is moot when caps are 1 by construction.
- **`--decompose` skipped** — no IBs to author and no per-IU branching to perform when there is exactly one IU.
- **`/write-code-beads` skipped** — the Intent file itself is the work unit. The Intent's `## Components affected` + `## Verification` + `## Desired Outcome` blocks supply the equivalent of a bead's Goal + Files + Acceptance Criteria.

### Step 4: Status walk

Walk Status `DRAFT → ACCEPTED → IMPLEMENTING` in one shot (no PROPOSED stop — there is no `--analyze` to fail). Bump `Modified:` and append an Amendment Log row of type `substantive` with note `via /write-intent --lite`:

```bash
python plugins/dekspec/skills/_lib/scripts/artifact_ops.py transition \
  <Intent-path> --from DRAFT --to IMPLEMENTING \
  --note "Lite-path: gates passed; transitioned DRAFT to IMPLEMENTING via /write-intent --lite" \
  --engineer <engineer-or-agent>
```

Surface stderr on non-zero exit and STOP.

### Step 5: Route to `/exec-coding-session`

Hand the Intent itself to the coding session as the work unit. The session resolves its own scope from the Intent's `## Components affected` and `## Desired Outcome`; there is no bead JSON to consume.

```text
Next step: invoke /exec-coding-session with <Intent-path> as the work unit.
```

### Step 6: `--testpass` (retained)

When the coding session reports completion, the engineer runs `/write-intent --testpass <Intent-path>` per [`modes/testpass.md`](testpass.md). The diff-confinement gate + Verification predicate evaluation are unchanged from the full path; the bead-closure pre-condition (`every bead listed in Layer impact analysis is closed`) is trivially satisfied because no beads were emitted.

## What this Mode does NOT do

- **No bead emission.** The bead-tracker queue has no new entry for a `--lite` Intent.
- **No IB authoring.** WS-fan-in checks are not run; no IB-NNN is created.
- **No `--analyze` size-cap report.** The Coverage report and Size assessment sections of the Intent body stay empty / un-populated (they are optional in the lite-intent template — see `templates/lite-intent-template.md`).
- **No Status flip to PROPOSED.** The walk is DRAFT → ACCEPTED → IMPLEMENTING in one step (the `transition` helper accepts that single-flip path).

## Audit signal

The `lite: true` frontmatter marker is the audit signal — fidelity audit rules can filter lite-path Intents in later phases (OI-D, deferred). The optional `scripts/audit-lite-path-intent.sh` script enumerates every Intent file with `lite: true` and reports them for periodic discipline-slope review.

**End of Lite Mode.**
