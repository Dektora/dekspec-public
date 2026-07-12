# INT-NNN: [Verb-first title]

<!--
SECTIONS BELOW: which ones flow into the Intent IR vs which are "author scratch pad"
====================================================================================
Canonical sections (extracted by parser, schema-validated, available to emitters):
  Status · Intent type · Autonomy · Branch · Mission · Source · Superseded-By ·
  Created · Modified · Linked Architecture Elements · Motivation ·
  Desired Outcome · Type-specific required fields · Components affected ·
  Verification · Open Issues · Amendment Log

Author scratch pad (rendered for /write-intent's --analyze / --decompose
walkthroughs, NOT loaded into the IR):
  Coverage report · Size assessment · Layer impact analysis ·
  TESTFAIL records · Post-implementation sync

Scratch-pad sections support the Intent lifecycle modes (--analyze surfaces
coverage + size; --testpass appends to TESTFAIL records on failure but
Status stays IMPLEMENTING — the TESTFAIL Status flip retired 2026-05-25;
--sync walks Post-implementation sync at MERGED). They are prompt-time
scaffolding for the implementing engineer and do not affect audit findings,
contract-test generation, or AGENTS.md output. If you need a scratch-pad
section to drive enforcement, file a bead to extend the Intent schema
(audit divergence D-11).
-->

## Status

DRAFT

*Valid statuses:* `DRAFT` → `OVERSIZED` → `SUPERSEDED` (terminal off-ramp) | `DRAFT` → `PROPOSED` → `ACCEPTED` → `IMPLEMENTING` → `TESTPASS` → `MERGED` → `LOCKED`

- **DRAFT** — being written; type, motivation, and rough scope present; coverage / size / verification not yet populated
- **OVERSIZED** — `--analyze` measured at least one hard cap exceeded (≤3 IUs / ≤3 components / ≤1 new L1 / ≤3 new+revised L2 / ≤2 coverage gaps). Cannot promote to PROPOSED without splitting or re-scoping
- **PROPOSED** — `--analyze` clean; coverage report complete; Verification predicate populated; size within caps; engineer has not yet accepted
- **ACCEPTED** — engineer approved; ready for `--decompose`
- **IMPLEMENTING** — beads (or IB → beads) in flight; coding sessions running on `int/INT-NNN-slug`. On `--testpass` failure (any Verification check exits non-zero, or diff-confinement finds out-of-scope edits) the failure is recorded in TESTFAIL records but Status remains IMPLEMENTING — fix and re-run
- **TESTPASS** — all Verification checks green; diff confinement clean
- **MERGED** — branch merged to main
- **LOCKED** — `--lock` ran post-merge; Intent is the executed commitment; appended to Mission Intent queue if a Mission was specified
- **SUPERSEDED** — terminal; replaced by a successor Intent (recorded in `Superseded-By`)

*Note: `TODO` and `TESTFAIL` were retired 2026-05-25 (E3 audit — neither appeared in 99-Intent history; the `TESTFAIL ↔ TESTPASS` round-trip never fired). The TESTFAIL records section below is retained as a captured-failure log on the IMPLEMENTING → TESTPASS path; it no longer corresponds to a Status flip.*

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

**Recommended default by Intent type (INT-094).** `medium` for `bug` / `refactor` / `documentation` (categories where CI green is sufficient proof of correctness); `manual` for `feature` / `nfr` / `adr-driven` / `environment` (categories warranting explicit operator sign-off — UX judgment, NFR targets, architectural ratification, blast radius beyond the test surface). Engineers override per Intent. The per-type default exists to honor downstream auto-merge surfaces (e.g. DekFactory INT-063, which auto-merges MRs at `auto-medium`+ once CI is green) without forfeiting that surface for well-bounded code-mod Intents.

## Risk Tier

[ default | schema-migration | auth | billing | concurrency | data-residency | external-api-surface | <custom> ]

*Optional.* Blast-radius classifier for the Intent. **Open enum + lint-on-boundary** (Phase 1.B): the schema accepts any string; the audit rule `T-INT-RISK-TIER-VALID` emits a `P3` advisory when the value falls outside the recommended vocabulary so typos surface as drift signal without blocking promotion. Absent = no audit signal (the field is forward-looking observability, not a gate).

- `default` — no special risk class (most Intents)
- `schema-migration` — touches typed-IR or persisted-data schemas; forward-migration story required
- `auth` — touches authn / authz / session / token handling
- `billing` — touches metering / invoicing / payment / quota enforcement
- `concurrency` — touches lock ordering / queue semantics / parallelism guarantees
- `data-residency` — touches storage location / cross-region replication / regulatory zoning
- `external-api-surface` — changes the contract of a publicly-consumed API (Intent should also link an IC)

Custom values are tolerated (Fowler lint-on-boundary). The advisory surfaces them so the vocabulary can grow deliberately — when a custom value appears repeatedly across Intents, promote it into `_INT_RECOMMENDED_RISK_TIERS` in `tooling/dekspec/fidelity_audit/linkage.py`.

The risk tier is **complementary** to Autonomy and Intent type: type classifies *what kind of change* (feature / bug / refactor / …); Autonomy classifies *how much human gating* (manual / low / medium / high); risk_tier classifies *blast radius* (which subsystem boundary the change is on). All three feed downstream observability + execution-routing decisions.

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
- AE-NNN: [Title] — [which aspect this Intent materially affects]

*Distinct from Components affected.* AE references describe spec-graph linkage (which architectural slices this Intent revises). Components affected (below) describes blast radius as file globs (which paths the diff is confined to). Both are required, single-purpose, and neither subsumes the other.

## Motivation

[Why this change is needed. 1-3 paragraphs. **Problem-first, user-grounded:** open by naming the concrete *problem* and the *user or persona* who feels it — what breaks for whom, today, without this — before any task or solution. A motivation that names only the task to do or the solution to build, without first establishing the problem and who hurts, is incomplete (INT-168 / D5). Then state the underlying gap and the cost of not changing.]

*Stay at the motivation level.* Decision rationale (why option A over option B) belongs in an ADR, not here (audit-v2 D20). Measurable targets (latency, throughput, capacity, coverage thresholds) belong in a Working Spec, not here (audit-v2 D19).

## Desired Outcome

[What is true after the Intent lands. State as observable system behavior, not as task completion. One paragraph.]

## Non-Goals

*Optional — expected only when this Intent has **no** parent Mission (i.e. `Mission:` is `none`).* List what this Intent will deliberately **not** do: the boundary that stops scope creep on a standalone Intent. When a parent Mission **is** named, delete this section — the Mission's `Out-of-scope` contract owns non-goals and duplicating them here is discouraged. A Mission-less Intent that omits this section draws the P3-advisory `T-INT-NON-GOALS-MISSING` audit finding (INT-168 / D6) — advisory only, never a blocker, and silent on already-LOCKED Intents.

- [What this Intent will not do / not touch — and, where useful, where that work lives instead.]

## Type-specific required fields

*Populate only the block matching this Intent's `Intent type`. Delete the others when the Intent moves out of DRAFT.*

### `feature` — Desired Outcome

(No additional required field beyond the Desired Outcome above. The Desired Outcome must describe the new behavior in user-observable terms.)

### `bug` — Reproduction

[A deterministic, agent-runnable PASS/FAIL repro signal — ideally the one `/diagnose-bug` built in PHASE 1 (a single shell command whose exit code *is* the signal). Required for `type: bug` *unless* a `### bug — Non-Reproducible Waiver` is supplied instead. The first bead produced at `--decompose` is the failing test that proves this Reproduction — and it is the Intent's ADR-029 Outcome Verification test (red-first); the Verification predicate's `bug-reproduction-fixed` check runs that test. The `T-BUG-REPRO-GATE` audit rule fires a P3 advisory on a `≥ACCEPTED` bug Intent that has neither this section nor the waiver below.]

### `bug` — Non-Reproducible Waiver

[Supply *this section instead of* Reproduction only when `/diagnose-bug` could not construct a deterministic repro (e.g. a Heisenbug, an environment-bound failure on a since-deleted runner, a data-dependent crash with no reproducible input). State plainly *why* no repro could be built and what evidence the fix rests on instead. A populated waiver satisfies the `T-BUG-REPRO-GATE` audit rule exactly as a populated Reproduction does — it is the explicit escape hatch, not a silent omission.]

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
- `dekspec/working-specs/WS-NNN-*.md`

*Distinct from Linked Architecture Elements.* Components describe blast radius (where the diff lands); AEs describe spec-graph shape (which architectural slices this Intent revises). Both are required.

## Coverage report

*Populated by `--analyze`. Lists completeness gaps surfaced when comparing the Desired Outcome against the current corpus. Each gap is logged as a `P1` Open Issue (canonical severity per ADR-013 — see §Open Issues for the full severity key) unless explicitly resolved as part of this Intent or as a prerequisite Intent.*


| Gap                                                                                      | Source                          | Resolution                                                                                | Status                     |
| ---------------------------------------------------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------- | -------------------------- |
| [missing prerequisite, missing script, missing test coverage on touched component, etc.] | [analyze step that surfaced it] | [resolve in this Intent / split out as prerequisite Intent / mark TBD with tracking bead] | [open / closed / deferred] |


## Size assessment

*Populated by `--analyze`. Each hard cap from Decision #5 with measured value and verdict. Any cap exceeded transitions the Intent to OVERSIZED — promotion to PROPOSED is blocked until the Intent is split or re-scoped. No engineer-side override.*


| Cap                                       | Limit | Measured | Verdict            |
| ----------------------------------------- | ----- | -------- | ------------------ |
| Implementation Units (IBs / direct beads) | ≤ 3   | [N]      | [PASS / OVERSIZED] |
| Components affected                       | ≤ 3   | [N]      | [PASS / OVERSIZED] |
| New L1 artifacts (AEs)                    | ≤ 1   | [N]      | [PASS / OVERSIZED] |
| New + revised L2 artifacts (WSes + ICs)   | ≤ 3   | [N]      | [PASS / OVERSIZED] |
| Coverage gaps                             | ≤ 2   | [N]      | [PASS / OVERSIZED] |


## Layer impact analysis

*Populated by `--analyze`. What changes at each layer of the spec graph. Empty rows allowed; explicit "none" preferred over omission.*


| Layer                         | Artifact                                                   | Action                |
| ----------------------------- | ---------------------------------------------------------- | --------------------- |
| L1 (Architecture & Decisions) | [AE-NNN, ADR-NNN, Domain Glossary, Guidance & Corrections] | [revise / new / none] |
| L2 (Specification)            | [WS-NNN, IC-NNN]                                           | [revise / new / none] |
| L3 (Implementation)           | [IB-NNN]                                                   | [new / none]          |
| L4 (Construction)             | [beads]                                                    | [new / none]          |


## Verification

*The TESTPASS predicate. List of named cmd checks that define "this Intent is done." Required (audit-v2 T14): at least one named cmd check must be present. `--analyze` populates from the type-default predicate (CLAUDE.md §Verification predicate library); engineers may override per Intent — overrides are logged. Every cmd check must resolve to an executable script or recognized tool (audit-v2 L9).*

```yaml
# Verification predicate for this Intent.
# Each entry: { name: <human-readable check>, cmd: <executable command> }
# All checks must pass for `--testpass` to succeed.
# Optional per check: `manual: true` + `manual_rationale: <why>` — the cmd is
# NOT executed by --testpass; a MANUAL-TESTPASS row is recorded instead. Use
# only for predicates needing infrastructure the local box lacks (ds-cjqi).
verification:
  - name: full-suite-green
    cmd: pytest -q
  - name: no-coverage-drop
    cmd: scripts/check-coverage.sh --baseline main
  # Add type-specific checks here. See CLAUDE.md §Verification predicate library
  # for the canonical defaults per Intent type.
```

## Outcome Verification

*Per ADR-029 (LOCKED 2026-05-29): every Intent ≥ ACCEPTED ships a single, simple, user-observable outcome test landed under strong-TDD timing (test red first → implementation makes it green → no other test files modified to make it pass). State the question, the input, and the expected assertion in one paragraph. Audited by `T-VERIFICATION-OUTCOME` (P2 advisory, INT-119) and consumed as a REVIEW_IB lens input (INT-120). Pre-existing Intents authored before INT-112 Slice A landed (2026-05-30) are auto-grandfathered (`outcome_verification_grandfathered: true`). Leave this section's body blank only if the Intent is genuinely grandfathered.*

<!-- Example shape:
"On input X, the algorithm produces placement Y. Tested by `tests/test_outcome_<slug>.py::test_<assertion>`; landed first in commit <SHA-red>, made green by commit <SHA-green>."
-->

## Open Issues

*Coverage gaps and ambiguities surfaced during drafting, `--analyze`, or review. Resolve via `/write-intent --review` (Phase 2 flag). `P1` issues prevent promotion to PROPOSED and ACCEPTED. `P2`/`P3` issues are tracked but do not gate promotion.*

- [ ] [Issue description] — **Source:** [initial draft / analyze / review / cascade from artifact] — **Severity:** [`P0` / `P1` / `P2` / `P3`]

**Severity key:** `P0` = production-incident / cost-runaway reserve. `P1` = critical / blocking — prevents promotion. `P2` = important / approval-blocking. `P3` = advisory / tracked-only — does not gate progress. Historical aliases (parser accepts indefinitely per ADR-013): `blocking` → `P1`; `non_blocking` → `P3`; `critical` → `P1`; `important` / `warning` → `P2`; `minor` / `info` → `P3`. See `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder + alias map.

*Scope: design-level only.* Code-gap observations belong in `dekspec/divergences/` or `br`, not here.

## TESTFAIL records

*Captured-failure log on the IMPLEMENTING → TESTPASS path. Populated by `--testpass` when any Verification check fails or diff-confinement detects out-of-scope edits. Each failure is recorded with what failed, when, and how it was resolved. Status stays IMPLEMENTING through the fail/fix loop (the TESTFAIL Status flip retired 2026-05-25 — E3 audit); subsequent `--testpass` runs append new records here rather than overwriting prior ones.*


| Date       | Failed check                       | Detail                                                                              | Resolution                                                      |
| ---------- | ---------------------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| YYYY-MM-DD | [check name or "diff-confinement"] | [what was wrong — failing test name / unexpected file edited / metric below target] | [what fixed it — bead ID / commit reference / scope correction] |


## Post-implementation sync

*Checklist of minor catch-up items surfaced post-merge. Run via `/write-intent --sync` (Phase 3 flag). Limited to non-substantive cleanups; substantive changes require `--amend`.*

- [ ] [WS docstring or example needs updating to reflect landed behavior]
- [ ] [Operating-guide cross-reference points at obsolete artifact]
- [ ] [Test-promotion candidates from this Intent's IBs]

## Amendment Log

*Add an entry for every change made after LOCKED status, or when unlocking back to PROPOSED.*

**Compressed-format policy.** Entries SHOULD follow a one-line-per-entry format. Target: `| YYYY-MM-DD | <Type> | <one-sentence what + reference to delta-doc / commit> | <author> |`. Detailed change narrative belongs in the git commit message — not in the Intent body.


| Date       | Type                             | Change                                            | Author          |
| ---------- | -------------------------------- | ------------------------------------------------- | --------------- |
| YYYY-MM-DD | Editorial / Unlock / Substantive | <one-sentence summary + delta / commit reference> | [name or agent] |


