# Implementation Brief: [bounded outcome, in a few words]

<!-- Before writing content, read `dekspec resource purpose implementation-brief` for the canonical purpose and routing items. -->

**Status:** DRAFT
**Authority policy:** delegated
**Parent:** none
**Depends on:** none
**Spec impact:** none

<!--
Read `dekspec resource purpose implementation-brief` for the contract purpose.
Execute directly, without code beads; preserve the following authority
semantics when authoring its sections (ADR-055):

  Binding obligations   — Obligations, Protected Surfaces, Scope (the boundary).
                          Preserve them; change them only by amending this IB
                          or the canonical source they reference.
  Acceptance conditions — Acceptance. Demonstrate them with evidence; never
                          weaken them unilaterally (ADR-057 amendment process).
  Implementation hypothesis — Implementation Hypothesis. A starting guess the
                          implementing agent revises after investigating the
                          repository, within Scope and without permission.

Apply implementation-brief.holds.obligations from the purpose entry (ADR-056).
`dekspec ib context` resolves each reference and delivers canonical text with
its revision to the implementing agent; tag a locally owned obligation `local`.

`Parent` is optional context (INT-/WS-/MSN-NNN). A bounded change needs no
parent: Outcome + Rationale + references are enough.
-->

## Outcome

[The observable state that is true when this IB is complete. State the result, not the task list.]

## Rationale

[Why this change is wanted — enough for a reviewer to judge it without a parent artifact. One short paragraph. If a parent Intent/WS already carries the rationale, reference it instead.]

## Scope

Patterns are anchored at the repository root. `*`, `?` and `[...]` stay within one folder and never match `/`; `**` matches any depth, including none. A trailing `/` names a folder and covers everything inside it. Unlike `.gitignore`, all patterns are root-anchored, there is no negation (a leading `!` is literal), and brace groups such as `{a,b}` expand. Use `docs/*.md` for Markdown files directly in `docs`, `docs/**/*.md` for any depth, and `**/build/` for build folders at any depth.

Changes are allowed anywhere inside these globs without further permission. A change outside them is a scope expansion and needs an amendment to this IB.

- `path/or/glob/**` — [what may change here]

### Out of scope

- [Non-goal — something a reasonable engineer might assume is included but is not]

## Obligations

Binding. Reference the canonical home; add a short applicability note only when the reference alone does not say how it applies here.

- **O-1** → ADR-NNN — [optional: how it applies to this change]
- **O-2** → IC-NNN §[Section heading]
- **O-3** (local): [an obligation whose canonical home is this IB]

## Protected Surfaces

Binding, and stronger than Scope: nothing listed here may be modified, renamed or deleted by this IB, even inside an allowed glob. Use `path::symbol` to protect one Python function or class.

Protection refuses every change except ADR-073 lifecycle bookkeeping: on the delivery's own existing brief files and their parent Intent files, only the status value under an engine transition (DRAFT → PROPOSED, PROPOSED → ACCEPTED, ACCEPTED → COMPLETE, COMPLETE → ACCEPTED) and rows appended to the Amendment Log; execution-record writes are exempt only for added or modified record files. Modified dates, edited/deleted/reordered existing rows, other sections or artifacts, mixed edits, and artifact additions, deletions or renames (including archive moves) stay refused. The check judges content, not authorship; hand-written bookkeeping grants no completion authority.

| Surface | Reason |
|---------|--------|
| `path/to/file.py::symbol` | [what depends on it staying unchanged] |

## Acceptance

Acceptance conditions: what must be demonstrated, and the evidence that demonstrates it. Every condition is checked by `dekspec ib verify` against the delivered revision; `review` conditions are judged by an independent reviewer (`dekspec ib review`). Include integration and failure behavior, not only the happy path.

```yaml
- id: AC-1
  condition: "[observable behavior]"
  verify:
    pytest: ["tests/test_[area].py::test_[behavior]"]
- id: AC-2
  condition: "[failure behavior: what happens when X is missing or invalid]"
  verify:
    pytest: ["tests/test_[area].py::test_[failure]"]
- id: AC-3
  condition: "[integrated behavior through the real entry point]"
  verify:
    command: "[shell command that exits 0 only when the behavior holds]"
    test_files: ["tests/test_entry_point.py"]
- id: AC-4
  condition: "[property a reviewer must judge, e.g. architectural fidelity to AE-NNN]"
  verify:
    review: "[what the reviewer must establish]"
```

`test_files` belongs beside `command` and lists repository-relative files or folders,
without `*`, `?` or `[`. Use `[]` to declare that a command runs or reads no test
files. These paths are acceptance assets and part of the contract hash and baseline;
DekSpec never discovers them from command text. `ib lint` rejects malformed lists
and declarations on pytest/review conditions. Where a brief has pytest conditions
or declared assets, `ib floor` refuses commands with undeclared or missing test
files. Command-only declared assets also require a reviewed floor for readiness.

The floor reports `support changed:` for a test made new by changed expectation
support. Such a test needs a non-empty Basis but no red if it passes on the base.
A report with `0 assessed` says `not red or green test evidence`; it does not say
`acceptance floor OK`.

Protected acceptance assets (test files named above are protected automatically; list any other fixtures or golden data):

- none

## Implementation Hypothesis

Revisable. The implementing agent investigates the repository first and may change any of this within Scope; material departures are recorded in the execution record, not here. <!-- purpose: implementation-brief.not.execution-history -->

- Likely files: `path/to/file.py` — [expected change]
- Approach: [suggested approach, if useful]
- Reuse: [existing capability worth reusing, if known]

## Environment Prerequisites

Live services or tools the work needs. `dekspec ib start` runs each probe; a failed required probe blocks the run truthfully (`prerequisite-unavailable`) rather than letting work start.

| Prerequisite | Probe command | Required |
|--------------|---------------|----------|

## Open Issues

- [ ] [Issue] — **Source:** [initial draft / review / cascade] — **Severity:** [`P0`–`P3`]

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
