---
name: review-ib
description: Pre-implementation review of an IB's spec packet + bead decomposition via the shared math-olympiad orchestration. Use when an Implementation Brief enters the REVIEW_IB state (post-ACCEPTED, pre-IMPLEMENTING) and the operator wants a non-sycophantic verdict before code lands.
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
mode: lite
allowed-tools: Read Grep Glob Bash Agent
argument-hint: [--help] <IB-ID>
---

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:review-ib"
one_line: "Pre-implementation review of an IB's spec packet via the math-olympiad orchestration."
modes:
  - { flag: "", args: "<IB-ID>", description: "Review the IB at REVIEW_IB state; emit GO / NO-GO / INSUFFICIENT_EVIDENCE verdict." }
  - { flag: "--help", args: "", description: "Show this manifest." }
examples:
  - "/dekspec:review-ib IB-067"
```

# /dekspec:review-ib <IB-ID>

> Pre-implementation review of an Implementation Brief. Loads `plugins/dekspec/skills/_lib/review-orchestration.md` (INT-105, LOCKED) with the REVIEW_IB lens pack (`plugins/dekspec/skills/review-ib/lenses.md`) and emits a structured GO / NO-GO / INSUFFICIENT_EVIDENCE verdict. Per **ADR-026** (LOCKED 2026-05-29).

This skill is the pre-impl half of the two-tier review pipeline. Its sibling — `/dekspec:review-pr` (INT-107) — is the post-impl half. Both consume the same shared orchestration shell; they differ only in lens pack + input bundle + output target.

## When this skill fires

REVIEW_IB auto-fires on IB state-entry to `REVIEW_IB` — i.e. when `/write-ibs --accept` lands an IB in the `REVIEW_IB` lifecycle state per the IB IR status enum (INT-102, LOCKED). Today the action-handler framework (INT-108) dispatches this skill on that transition. Operators may also invoke it manually with an explicit IB-ID at any IB lifecycle state ≥ ACCEPTED.

The verdict is **RECOMMEND-only at landing**: the orchestrator emits the verdict + writes the sidecar review file, but the IB state machine does not auto-advance. The operator reads the sidecar and triggers the advance manually. MIXED / AUTO modes (INT-118) auto-advance once a calibration corpus accumulates (INT-117) and per-lens silver/gold thresholds are operator-committed in `.dekspec/review-thresholds.yaml`.

## Invocation

```
/dekspec:review-ib <IB-ID>
```

`<IB-ID>` is the canonical Implementation Brief identifier (e.g. `IB-042`). The skill resolves the IB file path from the project's `dekspec/impl-briefs/` tree.

Optional flags:

- `--mode <RECOMMEND|MIXED|AUTO>` — override the per-repo `.dekspec/config.yaml` `review.mode` field for this invocation. Default: whatever the config declares (default `RECOMMEND`).
- `--sidecar-dir <path>` — override the sidecar output directory. Default: `dekspec/reviews/`.
- `--lens-pack <path>` — override the REVIEW_IB lens pack for this invocation (rare; used during lens development).

## Input bundle

The orchestration shell bundles the following inputs and projects per-lens slices via each lens's `input_slice` selector (see `plugins/dekspec/skills/_lib/review_lens_registry.md`). The bundle MUST include:

| Slot | Source |
|---|---|
| `ib.body` | The full Implementation Brief markdown body. |
| `ib.files_to_modify` | The IB's declared file globs. |
| `ib.done_when` | The IB's acceptance criteria. |
| `ib.test_plan` | The IB's test plan list. |
| `parent_ws.path` | Path to the governing Working Spec. |
| `parent_ws.acceptance` | The WS's acceptance criteria, for fidelity-check lenses. |
| `parent_intent.path` | Path to the parent Intent. |
| `parent_intent.components_affected` | The Intent's component globs, for scope-creep lens. |
| `source_ae_paths` | Paths to source Architecture Elements. |
| `glossary` | `dekspec/domain-glossary.md` for glossary-discipline lens. |
| `bead_decomposition` | Bead manifest from `/write-code-beads --audit`. |
| `audit_doctor` | Cached `dekspec audit doctor --json --at .` snapshot. |

The orchestration shell pulls these once and caches; each lens sees only its declared slice.

## Output: sidecar review file

REVIEW_IB writes a human-readable sidecar at `dekspec/reviews/<IB-ID>-review-<UTC-timestamp>.md` mirroring the gsd-eval-review EVAL-REVIEW.md pattern. The sidecar carries:

- The verdict (GO / NO-GO / INSUFFICIENT_EVIDENCE).
- The vetoing lens(es) if NO-GO.
- The surfaced findings (≥80 confidence) grouped by lens.
- The abstaining lenses if INSUFFICIENT_EVIDENCE.
- The audit-doctor snapshot SHA for flywheel correlation.
- The run timestamp.

In parallel the structured verdict is persisted to the SQLite flywheel at `$XDG_DATA_HOME/dekspec/<repo>/reviews.db` (INT-109 ships the schema; this skill calls `dekspec.review.db.write_verdict(verdict)`).

## Lens pack

The 14 REVIEW_IB lenses live in `plugins/dekspec/skills/review-ib/lenses.md`. The pack covers:

- **Spec discipline** — scope-creep, acceptance-falsifiability, test-plan-coverage, source-spec-fidelity, interface-depth, ambiguity-audit, constraint-completeness.
- **Operational discipline** — dependency-readiness, rollout-risk-plan, glossary-discipline.
- **Bead discipline** — bead-coverage, bead-granularity, bead-dependency-graph, bead-to-ib-fidelity.

Each lens conforms to the schema in `plugins/dekspec/skills/_lib/review_lens_registry.md` (4 required fields: `question`, `input_slice`, `attack_patterns`, `severity_rubric`).

## Verdict semantics

The orchestration shell aggregates per-lens findings under ADR-026's asymmetric-voting contract: **any single lens at the surface threshold (≥80 confidence) NO-GO's the verdict regardless of other lenses' scores**. There is no weighted-average path that overrides a confident veto. This is what makes the verdict non-sycophantic.

- **GO** — every lens at <80 confidence on its question, no abstentions.
- **NO-GO** — at least one lens at ≥80 confidence (per the shared `review_confidence_rubric.md` 0-100 ladder; bands `important` 76-90 or `critical` 91-100). Sidecar names the vetoing lens(es) + findings.
- **INSUFFICIENT_EVIDENCE** — no lens reaches ≥80 AND at least one lens explicitly abstained via the rubric's abstention band. The verdict is "we don't know"; operator decides.

## Failure modes

- **Lens-pack load failure** — if any lens in `lenses.md` violates the schema (missing field, empty `attack_patterns`, etc.) the orchestration shell raises at load time before any specialist runs. Fix the lens pack, re-invoke.
- **Audit-doctor unavailable** — if `dekspec audit doctor --json --at .` fails, the skill aborts before fan-out. Several lenses depend on the audit-doctor cache (per `review_lens_registry.md` audit-doctor reuse contract); a review without it cannot satisfy those lens contracts.
- **All lenses abstain** — verdict is INSUFFICIENT_EVIDENCE; sidecar records the unanimous abstention.

## Cross-references

- ADR-026 (load-bearing decision).
- ADR-036 (deep-modules principle — source of the `interface-depth` lens; Constitution Article 4 cites it).
- AE-006 (Skills Library — this skill's host AE).
- INT-105 (LOCKED — the shared orchestration shell this skill consumes).
- INT-107 (sibling — `/dekspec:review-pr`, post-impl half of the two-tier pipeline).
- INT-108 (action-handler framework — dispatches this skill on IB state-entry to `REVIEW_IB`).
- INT-109 (flywheel persistence — the SQLite schema this skill writes verdicts into).
- INT-120 (outcome-test discipline lens — adds a dedicated TDD lens to this pack via Slice C peel-off).
- Design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Lens design (per-stage)" REVIEW_IB table.
