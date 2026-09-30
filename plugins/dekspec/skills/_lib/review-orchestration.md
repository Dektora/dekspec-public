# review-orchestration

> Shared math-olympiad orchestration shell used by `/dekspec:review-ib` (pre-execution review of an IB contract) and `/dekspec:review-pr` (post-implementation review of a delivery at its head). Both drive a context-isolated, pattern-armed, asymmetric-voting review with calibrated abstention. Per **ADR-026**, as revised by ADR-057 (verdicts live in the IB execution record, bound to the reviewed content).

Each consumer skill supplies (a) its lens pack (schema: `review_lens_registry.md`), (b) its input bundle, (c) its **Agent Role Specification** — `spec-reviewer` for REVIEW_IB, `code-reviewer` for REVIEW_PR ([`agent_roles.md`](agent_roles.md)) — and (d) what it does with the verdict. The shell covers fan-out, scoring and aggregation. A lens specializes the consumer's role; it never replaces it.

## Load-bearing properties

These are not negotiable — a consumer MUST NOT re-implement aggregation with different semantics.

1. **Context isolation.** Each lens specialist runs in a fresh context receiving the governing policy, the consumer's role layer, its lens and only its lens's `input_slice` (composed per `agent_roles.md`). Specialists are blind to each other and to the parent conversation, and never receive an author's or builder's reasoning.
2. **Solver-cannot-verify-self.** The orchestrator dispatches; specialists score; a separate aggregator decides. No specialist judges its own finding, and at REVIEW_PR the reviewer is never a builder of the IB (the engine enforces this on `dekspec ib review`).
3. **Pattern-armed attack.** Specialists hunt the lens's `attack_patterns`; they do not grade.
4. **Inter-verifier blindness.** The aggregator sees `{finding, score, abstention}` tuples without lens identities.
5. **Asymmetric voting (single-lens veto = NO-GO).** Any single lens at the surface threshold vetoes the verdict regardless of the others. No weighted average outvotes a confident NO-GO.
6. **Per-issue confidence scoring (0-100, surface ≥80).** Per `review_confidence_rubric.md`. Below-threshold findings do not affect the verdict.
7. **Calibrated abstention (`INSUFFICIENT_EVIDENCE`).** Reachable when no lens reaches 80 and at least one lens abstains. A reviewer that always emits a confident verdict turns thin substrate into a coin flip; abstaining keeps a decision open rather than guessed.

## Verdict shape

```yaml
verdict:
  decision: GO | NO-GO | INSUFFICIENT_EVIDENCE
  vetoing_lenses: [lens_id, ...]      # on NO-GO
  surfaced_findings:                   # ≥80 only
    - lens_id: ...
      finding: ...
      confidence: 0-100
      severity: important | critical
  abstaining_lenses: [lens_id, ...]    # on INSUFFICIENT_EVIDENCE
  subject: IB-NNN                      # one verdict per IB
  head: <commit>                       # REVIEW_PR: the reviewed delivery head
```

## Procedure

1. Run `dekspec doctor --json --at .` **once** and cache it; lenses that need audit data declare `input_slice: audit_doctor.<path>`.
2. Load the consumer's role **once**: `dekspec resource role <spec-reviewer|code-reviewer>`. A non-zero exit aborts before fan-out — a review without its role definition does not run.
3. Build the input bundle (the consumer skill's table) and project each lens's slice.
4. Fan out one fresh-context specialist per lens, in parallel (Agent tool), each composed policy → role (verbatim) → lens procedure → slice. The lens procedure tells the specialist it **scores only**: it returns findings or an abstention and never runs `dekspec ib review` — the consumer skill records the one verdict after aggregation.
5. Collect `{findings, scores, abstention}` per lens. A lens that returned nothing abstains; it never counts as a clean pass.
6. Aggregate blind, applying the asymmetric veto and abstention rules.
7. Hand the verdict to the consumer skill.

## Where the verdict goes

| Stage | GO | NO-GO | INSUFFICIENT_EVIDENCE |
|---|---|---|---|
| REVIEW_IB (contract and acceptance floor, pre-`dekspec ib accept`) | recommend `dekspec ib accept`; when the IB has `pytest:` conditions or declared assets and `dekspec ib floor` reports the floor OK, write the `Floor reviewed: PASS — digest …` row into its `## Amendment Log` (ADR-062) | surfaced findings → the IB's `## Open Issues` (P1/P2); no floor-review row; do not accept | name the gap; no floor-review row; engineer decides |
| REVIEW_PR (delivery head, per IB) | `dekspec ib review <IB> --verdict pass --policy-revision <N> [--acknowledge …]` | `dekspec ib review <IB> --verdict fail --policy-revision <N> --notes …` | record nothing; completion stays refused |

GO maps to `pass` and NO-GO to `fail`. The recorded `verdict.recorded` event — bound to the content fingerprint, contract hash, acceptance baseline, source manifest and the `code-reviewer` policy revision `<N>` loaded in step 2 (ADR-061) — is the only verdict the completion gate reads (ADR-057). There are no review statuses, no review sidecar files and no separate review database; a narrative report is optional commentary.

**RECOMMEND-only (ADR-026).** A verdict never changes a status by itself and never merges. Authorization (`dekspec ib accept`), completion (`dekspec ib complete`) and merge stay separate, deliberate steps.

## Failure modes

- **Malformed lens pack.** A lens missing a required field stops the review before fan-out.
- **Audit-doctor unavailable.** If `dekspec doctor --json --at .` fails, abort before fan-out.
- **All lenses abstain.** The verdict is `INSUFFICIENT_EVIDENCE`.

## Relation to other surfaces

- **ADR-026** (this shell's decision; revised by ADR-057), **ADR-058** (review at the delivery head, one verdict per IB), **ADR-061** (the reviewer roles; `agent_roles.md`), **ADR-062** (the oracle review of the acceptance floor before the baseline, and of amended or added acceptance assets before acknowledgment).
- **AE-006** (Skills Library), **AE-003** (audit-doctor reuse), **AE-011** (Execution & Evidence Engine — owns verdict recording).
- `review_lens_registry.md`, `review_confidence_rubric.md`, `grep_loop_review_workflow.md` (the fix loop after a FAIL).
