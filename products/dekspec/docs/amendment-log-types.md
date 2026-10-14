# amendment_log.type — canonical vocabulary

The five IR schemas that carry an `amendment_log` (ADR, AE, WS, IC, Intent, Mission) use overlapping but not identical enum values for the `type` field. This document is the source-of-truth for the **shared vocabulary** and the **per-IR allowed subset rationale**. Authors should always pick a value from this list; schemas reject anything else.

Audit divergence reference: D-13 (audit 2026-05-11). The current state is "documented per-IR subsetting" rather than "unified enum"; a future minor release may collapse the two families further when usage signal accumulates.

## Two families, one base vocabulary

The base vocabulary partitions into two families:

### Family A — Locked-artifact maintenance lifecycle

For IRs that have a LOCKED state and may need post-lock changes. The flow is `LOCKED → unlock → substantive → lock → ...`, plus orthogonal `editorial` / `fill` / `migration` / `supersession` events. Since ADR-046 only standing decisions and versioned contracts (ADR, IC, Constitution, System Vision, Security Profile) lock; on AE and WS rows the `unlock` / `lock` values survive in the enum for historical entries only.

| value | what it records |
|-------|-----------------|
| `editorial` | Typo / clarity / formatting correction. **Does not change meaning.** No re-lock. No rebuild required for any LOCKED-artifact dependent. |
| `unlock` | Temporarily reopen LOCKED → DRAFT for a substantive edit cycle. |
| `substantive` | Meaning-changing edit while UNLOCKED. Must be followed by `lock`. Triggers downstream rebuild (contract tests, AGENTS.md). |
| `fill` | First-time population of an optional field added in a later schema version. Counts as substantive in spirit but is documented as a one-shot fill, not a free-form edit. |
| `migration` | A schema migration step rewrote this artifact (e.g., a v0.1.0 → v0.2.0 IR upgrade). The body change is mechanical, not authorial. |
| `lock` | Re-locked after a substantive edit cycle. Closes the unlock/substantive/lock triplet. |
| `supersession` | Formal supersession. This artifact has been replaced by another (recorded in the artifact's `superseded_by` field). Adds a record of WHEN supersession was declared. |

### Family B — Mission state-transition lifecycle

Missions have a richer lifecycle than other IRs because they coordinate multi-Intent work over time. The amendment_log records each state transition with a timestamp + change description.

| value | what it records |
|-------|-----------------|
| `activate` | Mission PROPOSED → ACTIVE. The work has been picked up. (Pre-ADR-057 rows read `TODO → ACTIVE`.) |
| `review` | Mission ACTIVE checkpoint review (e.g., the L11 stale-ACTIVE advisory triggered, or scheduled progress review). |
| `complete` | Mission ACTIVE → COMPLETE. Mission Verification predicates resolved inside `--complete` (the `COMPLETING` status was retired by ADR-057). |
| `kill` | Mission ACTIVE → KILLED. Kill criteria fired (or operator manually killed). |
| `supersede` | Mission superseded by another Mission. |
| `editorial` | Same as Family A — typo / formatting correction. The only Family-A value that crosses over. |

## Per-IR allowed subset + rationale

| IR | Allowed enum values | Rationale |
|---|---|---|
| `adr.schema.yaml` | `editorial, unlock, substantive, fill, migration, lock, supersession` | Full Family A. ADRs may be unlocked + substantively edited (e.g., refining a decision after lived experience), and they have formal supersession via the L7 audit rule. |
| `architecture-element.schema.yaml` | `editorial, unlock, substantive, fill, migration, lock` | Family A minus `supersession`. AEs don't formally supersede each other (a deprecated AE is just deleted or marked DEPRECATED in `status`). AEs rest at ACCEPTED and never lock (ADR-046); `unlock` / `lock` remain valid only so historical rows parse. |
| `working-spec.schema.yaml` | `editorial, unlock, substantive, fill, migration, lock` | Same as AE, including the never-lock rule. |
| `interface-contract.schema.yaml` | `editorial, unlock, substantive, fill` | Family A minus `lock` and `supersession`. ICs lock once via the normal status flow; further substantive edits trigger a new IC, not an unlock+lock cycle. (Audit divergence D-13 candidate: do we want to add `lock` for full consistency?) |
| `intent.schema.yaml` | `editorial, unlock, substantive` | Minimal Family A. Intent supersession is recorded via the dedicated `superseded_by` field, not the amendment log. Intents never lock (they end at COMPLETE, ADR-046/057); `unlock` survives for historical rows. Status migrations are recorded as `editorial` rows (see below). |
| `mission.schema.yaml` | `activate, review, complete, kill, supersede, editorial` | Family B, plus the one Family-A crossover (`editorial`). Missions are coordination artifacts; their amendment_log is the source-of-truth for the lifecycle audit timeline. |

## Rows written by the tooling

Some Amendment Log rows are appended by commands rather than by an author. In the markdown they carry the capitalized type shown; in IR they fall under the per-IR values above.

| Written by | Row type | What it records |
|---|---|---|
| `dekspec migrate` (markdown stage) | `Editorial` | A retired status mapped to its successor, with the prior value (ADR-057) — e.g. an IB `TESTFAIL → ACCEPTED`, an Intent `TESTPASS → ACCEPTED`, a Mission `TODO → PROPOSED`; the `**Authority policy:** legacy` stamp on an IB; removal of `Review grandfathered` / `Beads before accept`. |
| `dekspec ib propose` · `dekspec ib accept` · `dekspec ib complete` | `Substantive` | The IB decision transition (DRAFT → PROPOSED → ACCEPTED → COMPLETE). |
| `dekspec ib adopt` | `Substantive` | A legacy IB moved to the delegated authority policy (ADR-055). |
| `dekspec intent complete` | `Substantive` | Intent ACCEPTED → COMPLETE once its child IBs are complete and outcome evidence is current. |

Acceptance-contract amendments after execution starts (`dekspec ib amend`) are **not** Amendment Log rows: they are events in the IB's execution record (`.dekspec/execution/<IB>/record.jsonl`), where the completing review verdict must acknowledge them (ADR-057).

## Naming inconsistency — known issue

`supersession` (Family A, ADR) and `supersede` (Family B, Mission) are different spellings of the same concept. Neither is wrong; both are entrenched in saved artifacts. A future schema migration may unify on one form (likely `supersession`, the noun); until then, authors should match the spelling their IR's schema declares.

## How this gets enforced

The enum lists in each `*.schema.yaml`'s `amendment_log.items.properties.type.enum` are the contract. JSON Schema rejects any value outside the per-IR subset. Audit-time enforcement is implicit — a parsed artifact whose `amendment_log[i].type` is not in the enum fails schema validation, which surfaces as an `LX-PARSE` finding in `dekspec audit linkage`.

## Roadmap

- **Today:** documented per-IR subsetting (this doc).
- **Possible future:** collapse to one enum that's the union of A + B, with per-IR allowed-subset enforced via `audit linkage` rules rather than schema enums. Lets multi-IR tooling (e.g., a future amendment-log dashboard) operate on a single vocabulary.
- **Possible future:** unify `supersession` ↔ `supersede` via schema migration.
