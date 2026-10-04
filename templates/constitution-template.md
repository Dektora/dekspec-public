# Constitution: [Project Name]

[One-paragraph preamble. What this Constitution covers, when it applies, and how it relates to the System Vision. 2-4 sentences. Extracted into `preamble` in the IR.]

## Status

DRAFT

*Valid statuses:* `DRAFT` → `PROPOSED` → `ACCEPTED` → `LOCKED` | any stage → `DEPRECATED`

- **DRAFT** — being written; anything goes
- **PROPOSED** — complete draft ready for review; engineer has not yet accepted
- **ACCEPTED** — engineer approved; AGENTS.md emission can rely on it
- **LOCKED** — frozen; editorial amendments only; unlock back to PROPOSED for substantive changes
- **DEPRECATED** — terminal; retired only when the project itself is retired or superseded

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

## Operating Principle

<!--
  Recommended section (not schema-required). A short, memorable mantra
  expressing the project's operating posture — one sentence or one
  phrase that orients every contributor + AI agent at session-load
  time. Sits ABOVE the 8 canonical Articles so its framing scopes the
  articles that follow. The Constitution parser ignores this section
  (it's not part of the IR); the mantra surfaces to readers and to the
  AGENTS.md aggregator, not to schema enforcement.

  Exemplar (Dektora/dekfactory): "Human in forging, dark on derived."
    - "Forging" = creation, design, novel architectural choices, spec
      authoring → requires human attention.
    - "Derived" = mechanical, regenerable outputs (code from spec,
      tests from acceptance criteria, docs from artifacts) → safe for
      autonomous AI execution.
  The mantra compresses the project's design heuristic into a sentence
  contributors can recite. See `docs/dekspec-methodology.md`
  §"Operating Principles" for the full design heuristic table.
-->

> **[Replace with the project's operating mantra — one sentence or one phrase that orients every contributor + AI agent at session-load time.]**

<!--
  ============================================================
  ARTICLES — exactly 8 in canonical order. Each `## Article N:`
  heading is positional; the schema's `articles[N-1]` is locked
  to the exact title shown. Do not rename, reorder, or add.
  ============================================================
-->

## Article 1: Project Identity

<!--
  kind: pointer
  Article 1 is a typed pointer back to the System Vision singleton.
  Fill the labelled placeholders below. `summary` is capped at 500
  characters (schema-enforced). `see_also` must be a relative path
  to a markdown file (typically `dekspec/system-vision.md`); the
  audit layer L-CONSTITUTION-ARTICLE-1-SV-REF verifies the path
  resolves to an existing System Vision.
-->

**Summary:** [One paragraph distilling the System Vision's "What This Is". Cap at ~500 characters. Don't restate — the see_also pointer carries the indirection.]

**See Also:** [dekspec/system-vision.md]

## Article 2: Technology Stack

<!--
  kind: text
  Free-form prose listing the pinned tech-stack commitments: language
  version, framework versions, distribution mechanism, testing
  toolchain, package layout. Worker agents read this at session-load
  time to ground language/library choices.
-->

[Replace with the project's standing technology choices. List the language + version, frameworks, distribution mechanism (e.g., proprietary git URL per ADR-NNN), tracker, and toolchain. Be specific — version pins, not aspirational ranges.]

## Article 3: Quality Standards

<!--
  kind: text
  Free-form prose listing the quality gates that must hold for any
  change: test suite expectations, lint expectations, audit
  cleanliness, version-triad invariants, coverage thresholds.
-->

[Replace with the project's standing quality gates. State each as a binary observable: tests pass / lint clean / doctor returns CLEAN / version triad enforced / coverage at-or-above N%. Severity of any audit finding cited as a gate is named on the canonical `P0` / `P1` / `P2` / `P3` ladder per ADR-013 (e.g., "zero `P0` / `P1` findings on `dekspec doctor`"); historical aliases (`blocking` → `P1`, `non_blocking` → `P3`, `critical` → `P1`, `important` / `warning` → `P2`, `minor` / `info` → `P3`) remain accepted indefinitely — see `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder and alias map.]

## Article 4: Architecture Principles

<!--
  State the project's standing architecture principles in their own right.
  Existing ADR references are optional elaboration, not a prerequisite to
  authoring or accepting this L0 Constitution. Do not invent ADRs.
  Optional reference format: - ADR-001 — One-line rationale.
  The IR retains authored markdown plus typed adr_refs for linkage audits.
-->

[State the principles every implementation must preserve. Use concrete prose or bullets; a new project needs no ADR to state these commitments.]

## Article 5: Development Workflow

<!--
  kind: text
  Free-form prose describing the standing workflow contract:
  branching model, commit / PR conventions, release runbook
  pointer, tracker discipline, cross-repo coordination rules.
-->

[Replace with the project's standing workflow rules. Cover: branching model, commit conventions, release runbook reference, tracker discipline (e.g., `dekspec ib ready` for accepted implementation work, in-repo JSONL), cross-repo coordination if applicable.]

## Article 6: Model Configuration

<!--
  kind: text
  State how authoring, implementation and review inherit the engineer's
  selected host model. Independent review uses separate identity/context.
  Do not hard-code a model or substitute capability tiers.
-->

[State the project's model policy. DekSpec work inherits the engineer-selected host model; separate review identity/context is required without selecting a different model. Surface an unavailable selected model instead of silently substituting.]

## Article 7: Boundaries

<!--
  State standing boundaries and prohibited behavior directly. References to
  existing ADRs/AEs are optional; when present each must resolve.
  Optional reference formats:
    - ADR-001 — What this decision forbids or fences off.
    - AE-001 — The architecture element's boundary aspect.
  The IR retains authored markdown plus typed adr_refs and ae_refs.
-->

[State what the project must never do or become. No ADR or AE is required before this Constitution can be accepted.]

## Article 8: Amendments

<!--
  kind: text
  Standing log of Constitution amendments. Each row records a
  date, change type (Editorial / Substantive / CLAUDE.md-migration /
  …), one-sentence summary + commit reference, and author.
-->

| Date       | Type        | Change                                              | Author |
|------------|-------------|-----------------------------------------------------|--------|
| YYYY-MM-DD | Substantive | [initial authoring — what content was migrated in] | [name] |


## Class Lanes

<!--
  kind: typed-table
  parser: constitution.class_lanes
  Per INT-125 / ds-zhhk: structured policy table binding
  (intent_type, risk_tier) → lane + budget caps + thresholds.
  Rows include effective_model_snapshot + effective_corpus_volume so
  calibration drift across model/corpus boundaries is audit-detectable
  (Fowler R3 + Wu R2 model-drift gap). The Constraint Compiler extracts
  this section into the Constitution IR's `class_lanes` array. Update
  via `/dekspec:write-constitution --revise` for class
  promotion/demotion (engineer-driven; not automated). Record lane-policy changes as substantive amendments, with promotion gated → canary → dark and demotion in the reverse direction.

  Columns (in order):
    intent_type | risk_tier | lane | budget_cap_tokens | budget_cap_dollars |
    max_attempts_per_attempt | max_attempts_per_bead |
    promotion_threshold_clean_runs | demotion_threshold_reverts |
    effective_model_snapshot | effective_corpus_volume

  `max_attempts_per_attempt` and `max_attempts_per_bead` are legacy
  tolerance columns: still validated, consumed by nothing (there are no
  code beads — ADR-056). Execution bounds are policy, not obligation, and
  live in `.dekspec/config.yaml` under `execution:` (max_attempts,
  stall_minutes, no_progress_attempts, integration_command), enforced by
  the IB execution record (ADR-057).
-->

| intent_type | risk_tier | lane | budget_cap_tokens | budget_cap_dollars | max_attempts_per_attempt | max_attempts_per_bead | promotion_threshold_clean_runs | demotion_threshold_reverts | effective_model_snapshot | effective_corpus_volume |
|---|---|---|---|---|---|---|---|---|---|---|
| feature | default | gated | 50000 | 0.50 | 3 | 5 | 10 | 2 | [selected host model snapshot] | small-N<100 |
| feature | auth | gated | 200000 | 5.00 | 3 | 5 | 25 | 1 | [selected host model snapshot] | small-N<100 |
