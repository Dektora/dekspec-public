# INT-NNN: [Verb-first title]

<!--
LITE INTENT TEMPLATE — compact sibling of templates/intent-template.md
====================================================================================
This is the lite-profile Intent template. Its section set is a STRICT SUBSET of the
full Intent template's canonical sections — same headings, so the same parser accepts
both. It carries only the load-bearing canonical sections:
  Status · Intent type · Autonomy · Branch · Mission · Source · Superseded-By ·
  Created · Modified · Linked Architecture Elements · Motivation ·
  Desired Outcome · Type-specific required fields · Components affected ·
  Verification · Open Issues · Amendment Log

It deliberately OMITS the five scratch-pad sections of the full template:
  Coverage report · Size assessment · Layer impact analysis ·
  TESTFAIL records · Post-implementation sync

Those sections are auto-derived / lifecycle-mode scaffolding (--analyze surfaces
coverage + size; --testpass appends to TESTFAIL records on failure but Status
stays IMPLEMENTING — the TESTFAIL Status flip retired 2026-05-25; --sync walks
Post-implementation sync at MERGED). They are not load-bearing for a compact
solo Intent and do not affect audit findings, contract-test generation, or
AGENTS.md output.

lite → full round-trip: upgrading a lite Intent to the full template means
populating the five omitted sections explicitly — no existing section is removed or
renamed. The lite body is a strict subset of the full body, so the upgrade is
monotonic and loses no data.
-->

## Status

DRAFT

*Valid statuses:* `DRAFT` → `OVERSIZED` → `SUPERSEDED` (terminal off-ramp) | `DRAFT` → `PROPOSED` → `ACCEPTED` → `IMPLEMENTING` → `TESTPASS` → `MERGED` → `LOCKED`

- **DRAFT** — being written; type, motivation, and rough scope present; coverage / size / verification not yet populated
- **OVERSIZED** — `--analyze` measured at least one hard cap exceeded (≤3 IUs / ≤3 components / ≤1 new L1 / ≤3 new+revised L2 / ≤2 coverage gaps). Cannot promote to PROPOSED without splitting or re-scoping
- **PROPOSED** — `--analyze` clean; coverage report complete; Verification predicate populated; size within caps; engineer has not yet accepted
- **ACCEPTED** — engineer approved; ready for `--decompose`
- **IMPLEMENTING** — beads (or IB → beads) in flight; coding sessions running on `int/INT-NNN-slug`. On `--testpass` failure (Verification or diff-confinement) a failure record is appended but Status remains IMPLEMENTING — fix and re-run
- **TESTPASS** — all Verification checks green; diff confinement clean
- **MERGED** — branch merged to main
- **LOCKED** — `--lock` ran post-merge; Intent is the executed commitment; appended to Mission Intent queue if a Mission was specified
- **SUPERSEDED** — terminal; replaced by a successor Intent (recorded in `Superseded-By`)

*Note: `TODO` and `TESTFAIL` were retired 2026-05-25 (E3 audit — neither appeared in 99-Intent history).*

## Intent type

[ feature | bug | nfr | adr-driven | refactor | documentation | environment ]

*Pick exactly one.* Required, controlled vocabulary. The type drives required fields and the default Verification predicate (see CLAUDE.md §Verification predicate library).

## Autonomy

[ manual | low | medium | high ]

*Required.* What level of autonomy is permitted on this Intent. If the Intent's `Mission:` is populated, this value MUST NOT exceed the Mission's `Autonomy ceiling:`.

- `manual` — every step gated by engineer approval
- `low` — engineer approves at PROPOSED → ACCEPTED, then again at TESTPASS → MERGED
- `medium` — engineer approves at PROPOSED → ACCEPTED only; rest runs autonomously
- `high` — full autonomous execution from PROPOSED through LOCKED (requires `dekfactory` orchestration brain; out of scope for this repo per `docs/architecture.md` §What does NOT live here)

## Branch

`int/INT-NNN-slug`

## Mission

[ MSN-NNN or "none" ]

*Optional.* Populated only when this Intent belongs to a Mission. When set, the parent Mission's Intent queue MUST list this Intent and the Intent's Autonomy MUST NOT exceed the Mission's Autonomy ceiling (audit-v2 L8).

## Source

[ provenance URL, capture-tool reference, or freeform note — or "none" ]

*Optional.* Where the idea originated (Linear issue, Slack thread, incident postmortem, code TODO, conversation, ADR cross-reference). Provenance only — not a parent. There is no enforced 1:1 relationship between a captured source and an Intent.

## Superseded-By

[ INT-NNN — only present if Status is SUPERSEDED ]

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

## Linked Architecture Elements

[The Architecture Element(s) this Intent materially shapes or revises. **Linkage is mandatory** — every Intent must list at least one existing AE-NNN reference (audit-v2 L7). An Intent that doesn't shape any AE is either too small to warrant an Intent or describes a slice that itself needs an AE first.]

- AE-NNN: [Title] — [which aspect of the AE this Intent materially affects]

*Distinct from Components affected.* AE references describe spec-graph linkage (which architectural slices this Intent revises). Components affected (below) describes blast radius as file globs (which paths the diff is confined to). Both are required, single-purpose, and neither subsumes the other.

## Motivation

[Why this change is needed. 1-3 paragraphs. The user-observable problem, the underlying gap, the cost of not changing.]

*Stay at the motivation level.* Decision rationale (why option A over option B) belongs in an ADR, not here (audit-v2 D20). Measurable targets (latency, throughput, capacity, coverage thresholds) belong in a Working Spec, not here (audit-v2 D19).

## Desired Outcome

[What is true after the Intent lands. State as observable system behavior, not as task completion. One paragraph.]

## Type-specific required fields

*Populate only the block matching this Intent's `Intent type`. Delete the others when the Intent moves out of DRAFT.*

### `feature` — Desired Outcome

(No additional required field beyond the Desired Outcome above. The Desired Outcome must describe the new behavior in user-observable terms.)

### `bug` — Reproduction

[Verbatim failing command, log excerpt, or step-by-step repro. Required for `type: bug`. The first bead produced at `--decompose` is the failing test that proves this Reproduction — and it is the Intent's ADR-029 Outcome Verification test (red-first); the Verification predicate's `bug-reproduction-fixed` check runs that test.]

### `nfr` — Metric and Target

**Metric:** [the numerical measurement, e.g. `cooccurrence/generate p95 latency`]
**Target:** [the threshold the metric must meet or exceed, e.g. `≤ 250 ms`]

(Required for `type: nfr`. The Verification predicate's `metric-meets-target` check runs `scripts/measure-nfr.sh` against these values.)

### `adr-driven` — ADR

**ADR:** [ADR-NNN — the driving ADR whose consequences this Intent realizes]

(Required for `type: adr-driven`. `--analyze` adds ADR-specific consequence checks to the Verification predicate based on the ADR's Consequences section.)

### `refactor` — Behavior-Equivalence

**Behavior-Equivalence:** [explicit assertion that observable behavior is unchanged — e.g., "extract embedding-pipeline orchestration into a service class; no public API changes; no test file modifications"]

(Required for `type: refactor`. The Verification predicate's `test-files-unchanged` check enforces zero modifications to test files; the Behavior-Equivalence statement documents what externally observable invariant this proves.)

### `documentation` — Coverage-Gap

**Coverage-Gap:** [the documentation gap this Intent closes — which artifacts are missing, stale, or contradictory; what the resulting set of artifacts will cover]

(Required for `type: documentation`. The Verification predicate's `docs-lint-clean` and `cross-references-resolve` checks enforce structural correctness of the resulting artifacts.)

### `environment` — Environment-Change

**Environment-Change:** [the runtime / deployment / dependency change being made — exactly what changes in the target environment, on what host(s), under what supervision model]

(Required for `type: environment`. The Verification predicate's `smoke-check-passes` check runs an environment-specific smoke script named here.)

## Components affected

[File-glob list of paths this Intent's diff is confined to. Required (audit-v2 T15). Drives diff-confinement at `--testpass` (Decision #14); any edit landing outside this list logs a TESTFAIL record (Status stays IMPLEMENTING — the TESTFAIL Status flip retired 2026-05-25) even if all other Verification checks pass. Each glob must resolve to existing paths in the repo (audit-v2 L7).]

- `path/glob/**/*.py`

*Distinct from Linked Architecture Elements.* Components describe blast radius (where the diff lands); AEs describe spec-graph shape (which architectural slices this Intent revises). Both are required.

## Verification

*The TESTPASS predicate. List of named cmd checks that define "this Intent is done." Required (audit-v2 T14): at least one named cmd check must be present. `--analyze` populates from the type-default predicate (CLAUDE.md §Verification predicate library); engineers may override per Intent — overrides are logged. Every cmd check must resolve to an executable script or recognized tool (audit-v2 L9).*

```yaml
# Verification predicate for this Intent.
# Each entry: { name: <human-readable check>, cmd: <executable command> }
# All checks must pass for `--testpass` to succeed.
verification:
  - name: full-suite-green
    cmd: pytest -q
  # Add type-specific checks here. See CLAUDE.md §Verification predicate library
  # for the canonical defaults per Intent type.
```

## Open Issues

*Coverage gaps and ambiguities surfaced during drafting, `--analyze`, or review. Resolve via `/write-intent --review` (Phase 2 flag). `P1` issues prevent promotion to PROPOSED and ACCEPTED. `P2`/`P3` issues are tracked but do not gate promotion.*

- [ ] [Issue description] — **Source:** [initial draft / analyze / review / cascade from artifact] — **Severity:** [`P0` / `P1` / `P2` / `P3`]

**Severity key:** `P0` = production-incident / cost-runaway reserve. `P1` = critical / blocking — prevents promotion. `P2` = important / approval-blocking. `P3` = advisory / tracked-only — does not gate progress. Historical aliases (parser accepts indefinitely per ADR-013): `blocking` → `P1`; `non_blocking` → `P3`; `critical` → `P1`; `important` / `warning` → `P2`; `minor` / `info` → `P3`. See `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder + alias map.

*Scope: design-level only.* Code-gap observations belong in `dekspec/divergences/` or `br`, not here.

## Amendment Log

*Add an entry for every change made after LOCKED status, or when unlocking back to PROPOSED.*

**Compressed-format policy.** Entries SHOULD follow a one-line-per-entry format. Target: `| YYYY-MM-DD | <Type> | <one-sentence what + reference to delta-doc / commit> | <author> |`. Detailed change narrative belongs in the git commit message — not in the Intent body.


| Date       | Type                             | Change                                            | Author          |
| ---------- | -------------------------------- | ------------------------------------------------- | --------------- |
| YYYY-MM-DD | Editorial / Unlock / Substantive | <one-sentence summary + delta / commit reference> | [name or agent] |
