# Constitution: [Project Name]

[One-paragraph preamble. What this Constitution covers, when it applies, and how it relates to the System Vision. 2-4 sentences. Extracted into `preamble` in the IR.]

<!--
LITE CONSTITUTION TEMPLATE — compact sibling of templates/constitution-template.md
====================================================================================
This is the lite-profile Constitution template. It keeps all 8 articles in canonical
order — the article structure and headings are identical to the full template, so the
same parser accepts both.

The one lite-profile difference is in Article 4 (Architecture Principles) and
Article 7 (Boundaries): a lite repo typically has no ADRs / AEs yet, so those
articles' typed `adr_refs` / `ae_refs` cross-references render as free-text bullets
instead. Once ADRs / AEs land in the corpus, promote the free-text bullets to typed
`- ADR-NNN — ...` / `- AE-NNN — ...` references — that is the lite → full round-trip
for the Constitution.
-->

## Status

DRAFT

*Valid statuses:* `TODO` → `DRAFT` → `PROPOSED` → `ACCEPTED` → `LOCKED` | any stage → `DEPRECATED`

- **TODO** — placeholder; needs review and rewrite against current project state
- **DRAFT** — being written; anything goes
- **PROPOSED** — complete draft ready for review; engineer has not yet accepted
- **ACCEPTED** — engineer approved; AGENTS.md emission can rely on it
- **LOCKED** — frozen; editorial amendments only; unlock back to PROPOSED for substantive changes
- **DEPRECATED** — terminal; retired only when the project itself is retired or superseded

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

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

[Replace with the project's standing technology choices. List the language + version, frameworks, distribution mechanism, tracker, and toolchain. Be specific — version pins, not aspirational ranges.]

## Article 3: Quality Standards

<!--
  kind: text
  Free-form prose listing the quality gates that must hold for any
  change: test suite expectations, lint expectations, audit
  cleanliness, version-triad invariants, coverage thresholds.
-->

[Replace with the project's standing quality gates. State each as a binary observable: tests pass / lint clean / doctor returns CLEAN / coverage at-or-above N%. Severity of any audit finding cited as a gate is named on the canonical `P0` / `P1` / `P2` / `P3` ladder per ADR-013 (e.g., "zero `P0` / `P1` findings on `dekspec doctor`"); historical aliases (`blocking` → `P1`, `non_blocking` → `P3`, `critical` → `P1`, `important` / `warning` → `P2`, `minor` / `info` → `P3`) remain accepted indefinitely — see `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder and alias map.]

## Article 4: Architecture Principles

<!--
  kind: ref-array
  Article 4 cites the project's load-bearing architecture commitments.
  LITE PROFILE: a lite repo typically has no ADRs yet, so list the
  standing architecture principles as free-text bullets — one
  principle per bullet, in standing terms. Once ADRs land in
  `dekspec/adrs/`, promote each bullet to a typed
  `- ADR-NNN — [one-line rationale]` reference; the audit layer
  L-CONSTITUTION-ARTICLE-4-ADR-REFS then verifies each ADR-NNN exists.
-->

- [Standing architecture principle stated in plain terms — e.g., "All cross-component boundaries go through an explicit interface, never a shared mutable module."]
- [Standing architecture principle — promote to `- ADR-NNN — [rationale]` once the decision is recorded as an ADR.]

## Article 5: Development Workflow

<!--
  kind: text
  Free-form prose describing the standing workflow contract:
  branching model, commit / PR conventions, release runbook
  pointer, tracker discipline, cross-repo coordination rules.
-->

[Replace with the project's standing workflow rules. Cover: branching model, commit conventions, release runbook reference, tracker discipline (e.g., `br ready` for queue, in-repo JSONL), cross-repo coordination if applicable.]

## Article 6: Model Configuration

<!--
  kind: text
  Free-form prose pinning model-tier choices for AI agent work:
  which capability tier is the default, what tasks may run on a
  lower tier, what work is forbidden on a lower tier.
-->

[Replace with the project's standing model-tier policy. Example: "Sessions default to the highest-capability model available (Claude Opus tier). Lower-capability models may be used for mechanical tasks (tests, lint), never for authoring under specific protected paths."]

## Article 7: Boundaries

<!--
  kind: ref-array
  Article 7 names the project's non-goal boundaries.
  LITE PROFILE: a lite repo typically has no ADRs / AEs yet, so list
  the standing boundaries as free-text bullets — one non-goal per
  bullet. Once ADRs / AEs land, promote each bullet to a typed
  `- ADR-NNN — ...` / `- AE-NNN — ...` reference; the audit layer
  L-CONSTITUTION-ARTICLE-7-BOUNDARY-REFS then verifies each
  ADR-NNN / AE-NNN exists.
-->

- [Standing boundary stated in plain terms — what the project deliberately does NOT do. Promote to `- ADR-NNN — [rationale]` (a decision framed as a boundary) or `- AE-NNN — [aspect]` (an Architecture Element's named non-goal) once recorded.]
- [Standing boundary — another non-goal the project commits to.]

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
