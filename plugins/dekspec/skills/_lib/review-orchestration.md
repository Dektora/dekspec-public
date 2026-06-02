# review-orchestration

> Shared math-olympiad orchestration shell used by `/dekspec:review-ib` (pre-impl, INT-106) and `/dekspec:review-pr` (post-impl, INT-107). Both skills load this `_lib` to drive a context-isolated, pattern-armed, asymmetric-voting review with calibrated abstention. Per **ADR-026** (LOCKED 2026-05-29).
>
> Source design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Math-olympiad orchestration shape" + §"Lens design (per-stage)" + §"Scoring + threshold action" + §"Audit-doctor reuse".

This file is the canonical contract surface. Each consumer skill (REVIEW_IB, REVIEW_PR) supplies (a) its lens pack via the schema in `review_lens_registry.md`, (b) its per-stage input bundle, (c) its output target (sidecar review file path). The shell handles fan-out, scoring, aggregation, persistence, and verdict emission.

## Load-bearing properties

The seven properties below are not negotiable — REVIEW_IB and REVIEW_PR both depend on them. A consumer skill MUST NOT re-implement aggregation locally with different semantics; it MUST load this shell and supply a lens pack.

1. **Context isolation.** Each lens-specialist runs in a fresh-context system prompt receiving only its targeted input slice (per the lens's `input_slice` selector in `review_lens_registry.md`). Specialists are blind to other specialists' findings and to the parent conversation. The orchestrator does the input projection; lens packs do not bundle whole-repo context.
2. **Solver-cannot-verify-self.** The orchestrator and the lens-specialists are different agents. The orchestrator dispatches; lens-specialists score; a separate aggregator scores them. No specialist ever evaluates its own finding.
3. **Pattern-armed attack.** Lens-specialists ATTACK, not grade. Each lens declares a `attack_patterns` list — specific failure-class checks loaded into the specialist's system prompt. The specialist's job is to FIND a failure matching one of those patterns, not to give a friendly review.
4. **Inter-verifier blindness.** The aggregator runs separately, blind to lens identities at scoring time. It sees `{finding_text, raw_score, abstention_flag}` tuples without lens IDs. This prevents the aggregator from weighting "lens X always exaggerates" into a soft veto.
5. **Asymmetric voting (single-lens veto = NO-GO).** This is the **load-bearing aggregation contract**. Any single lens that reaches the surface threshold (per its `severity_rubric` in `review_lens_registry.md`) vetoes the overall verdict, regardless of other lenses' scores. There is no weighted average that can outvote a confident NO-GO. This is the property that distinguishes math-olympiad orchestration from `code-review`-plugin-style weighted aggregation; it is what makes the system non-sycophantic.
6. **Per-issue confidence scoring (0-100, surface ≥80).** Per the shared `review_confidence_rubric.md`: every finding carries a 0-100 confidence score from the per-lens specialist; only findings ≥80 surface to the operator. Below-threshold findings are dropped from the verdict (they enter the flywheel's per-lens calibration log, but they do not affect the verdict). The 80 threshold is a property of the rubric, not configurable per consumer.
7. **Calibrated abstention (`INSUFFICIENT_EVIDENCE`).** The orchestrator MUST be able to return `INSUFFICIENT_EVIDENCE` as the overall verdict rather than guess. This is reachable when (a) no lens reaches the 80-surface threshold AND (b) at least one lens self-reports insufficient evidence (its `severity_rubric` includes an explicit abstention band). Without this property, the AUTO graduation path (RECOMMEND → MIXED → AUTO) cannot be safe: a system that always emits a confident verdict cannot be auto-merged on a confidence threshold.

## Verdict shape

```yaml
verdict:
  decision: GO | NO-GO | INSUFFICIENT_EVIDENCE
  vetoing_lenses: [lens_id, ...]            # populated on NO-GO
  surfaced_findings:                         # ≥80 only
    - lens_id: ...
      finding: ...
      confidence: 0-100
      severity: false-positive|nitpick|low-impact|important|critical
  abstaining_lenses: [lens_id, ...]          # populated on INSUFFICIENT_EVIDENCE
  audit_doctor_snapshot_sha: <sha>           # for flywheel correlation
  ran_at: <UTC timestamp>
```

## Audit-doctor reuse

The orchestrator runs `dekspec audit doctor --json --at .` **exactly once** per review session and caches the result on disk (in the per-IB session directory). Lens-specialists whose attack patterns overlap existing audit rules (L7b component-glob, L10 glossary, L3/L4 backlinks) consume slices of that cached output rather than re-deriving the audit. This is enforced by the lens-registry schema: a lens that needs audit-doctor data declares `input_slice: audit_doctor.<path>` and the orchestrator projects the slice from the cache. A lens that re-derives an audit rule it could have read from the cache fails the schema lint at lens-pack load time.

## Three-mode operation

The shell supports three operational modes; the consumer config (`.dekspec/config.yaml` `review.mode` field, see INT-118) selects which:

- **RECOMMEND** (default; today). The orchestrator emits the verdict but never auto-advances the IB state machine. The operator reads the sidecar, decides, and triggers the advance manually.
- **MIXED.** Lenses with operator-committed silver thresholds (in `.dekspec/review-thresholds.yaml`, written by INT-117) auto-advance on `verdict ≥ silver`; lenses without commit a silver threshold escalate to the operator regardless.
- **AUTO.** All lenses auto-advance on `verdict ≥ gold` per the same thresholds file. Operator becomes the override switch, not the dispatch button.

Mode plumbing lives in INT-118; this shell exposes the contract.

## Dispatch contract

A consumer skill invokes the shell as:

```python
from dekspec.review.orchestration import run_review

verdict = run_review(
    lens_pack=load_lens_pack("plugins/dekspec/skills/review-ib/lenses.md"),
    input_bundle={"ib_path": ..., "ws_path": ..., "ae_paths": [...], ...},
    sidecar_path="dekspec/reviews/IB-NNN-review-YYYYMMDDTHHMMSS.md",
    mode="RECOMMEND",  # or per .dekspec/config.yaml
)
```

The shell:
1. Loads the audit-doctor snapshot (cached).
2. Projects per-lens input slices.
3. Fans out lens-specialists in parallel, fresh-context.
4. Collects per-lens `{findings, raw_scores, abstention_flag}` tuples.
5. Runs the aggregator (asymmetric voting, blind to lens IDs at scoring time).
6. Emits the verdict + writes the sidecar markdown file.
7. (RECOMMEND mode) returns to caller for operator-driven advance.
8. (MIXED/AUTO mode) auto-advances the IB state machine on verdict ≥ threshold.

## Persistence layer

The verdict + per-lens score tuples are persisted to:

- **Sidecar markdown** at `dekspec/reviews/IB-NNN-review-<UTC>.md` (human-readable; gets committed alongside the IB).
- **SQLite flywheel** at `$XDG_DATA_HOME/dekspec/<repo>/reviews.db` (machine-readable; sample corpus for INT-117's calibration math). The schema row carries `{IB-id, branch-SHA, lens-scores, aggregated-verdict, operator-decision, time-to-decision, eventual-outcome}` — `eventual-outcome` labels (operator-accepted | PR-merged-clean | PR-reverted-in-14d | bead-reopened | audit-doctor-regressed) close the calibration loop.

Persistence is INT-109's surface (peeled by ADR-028 into INT-109 narrow + INT-116 CLI verbs + INT-117 calibration + INT-118 three-mode config); this shell calls into it through a stable contract `dekspec.review.db.write_verdict(verdict)`.

## Failure modes

- **Lens-pack load failure.** If a lens in the pack omits any of the four required schema fields (`question`, `input_slice`, `attack_patterns`, `severity_rubric` — see `review_lens_registry.md`), the shell raises at load time. The consumer skill cannot run a malformed pack.
- **Audit-doctor unavailable.** If `dekspec audit doctor --json --at .` fails, the shell aborts before fan-out. A review without audit-doctor grounding cannot satisfy the lens contracts that depend on it.
- **All lenses abstain.** The aggregator returns `INSUFFICIENT_EVIDENCE` and the sidecar records the unanimous abstention. The operator decides whether to advance manually.

## Relation to other library surfaces

- **ADR-026** (this shell's parent decision).
- **AE-006** (Skills Library — the `_lib/` lives under `plugins/dekspec/skills/_lib/`).
- **AE-003** (Fidelity Audit Engine — audit-doctor cache reuse).
- **INT-106 / INT-107** (the two consumer skills; each ships a lens pack against this shell).
- **INT-108** (action-handler framework — receives FAIL verdicts from this shell and dispatches the registered handler).
- **INT-109 / INT-116 / INT-117 / INT-118** (persistence + CLI + calibration + three-mode config).
- **INT-119 / INT-120** (outcome-test discipline — adds a dedicated TDD lens to the REVIEW_IB lens pack via INT-120).
