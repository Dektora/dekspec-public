# Implementation Brief: [bounded outcome, in a few words]

**Status:** DRAFT
**Authority policy:** delegated
**Parent:** none
**Depends on:** none
**Spec impact:** none

<!--
An IB is the smallest governed work contract and is executed directly — no
code beads. It separates three kinds of content by meaning (ADR-055):

  Binding obligations   — Obligations, Protected Surfaces, Scope (the boundary).
                          Preserve them; change them only by amending this IB
                          or the canonical source they reference.
  Acceptance conditions — Acceptance. Demonstrate them with evidence; never
                          weaken them unilaterally (ADR-057 amendment process).
  Implementation hypothesis — Implementation Hypothesis. A starting guess the
                          implementing agent revises after investigating the
                          repository, within Scope and without permission.

One authoritative home (ADR-056): an obligation owned by an ADR, IC, WS, SP,
AE or the Constitution is REFERENCED here, never copied. `dekspec ib context`
resolves the reference and delivers the canonical text, with its revision, to
the implementing agent. State an obligation in full only when this IB is its
canonical home (tag it `local`).

`Parent` is optional context (INT-/WS-/MSN-NNN). A bounded change needs no
parent: Outcome + Rationale + references are enough.
-->

## Outcome

[The observable state that is true when this IB is complete. State the result, not the task list.]

## Rationale

[Why this change is wanted — enough for a reviewer to judge it without a parent artifact. One short paragraph. If a parent Intent/WS already carries the rationale, reference it instead.]

## Scope

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
- id: AC-4
  condition: "[property a reviewer must judge, e.g. architectural fidelity to AE-NNN]"
  verify:
    review: "[what the reviewer must establish]"
```

Protected acceptance assets (test files named above are protected automatically; list any other fixtures or golden data):

- none

## Implementation Hypothesis

Revisable. The implementing agent investigates the repository first and may change any of this within Scope; material departures are recorded in the execution record, not here.

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
