# Shared `--review`-Mode Dispatch Contract — `reviewer_mode`

**Status:** AUTHORITATIVE (per IB-126 / INT-141 / MSN-019 daughter C).
**Audience:** the six DekSpec authoring skills (`write-intent`, `write-ws`, `write-ic`, `write-ae`, `write-adr`, `write-ibs`). Every one of their `--review` modes cites this file and routes its Spec-Reviewer dispatch through the uniform four-step path below.
**Lineage:** the `Reviewer<ArtifactType>` dispatcher surface pinned by IC-016 (daughter B / INT-140). This `reviewer_mode` lib is the consumer-side contract that the six `--review` modes share so the dispatch logic lives in exactly one place.

---

## Why this file exists

Before this substrate landed, each authoring skill's `--review` mode walked the artifact's `## Open Issues` (or, for `write-intent`, the section-by-section walkthrough) with the engineer, but there was no shared, adversarial Spec-Reviewer pass over the artifact-under-review. The six skills all author Layer-1–Layer-4 specification artifacts, so their `--review` function *is* the Spec-Reviewer role (INT-141 §Open Issue (a), CLOSED `spec-reviewer-for-all`): all six load the **same** `spec-reviewer` ContextSpec — this is NOT a per-artifact-kind role mapping.

Centralizing the dispatch here means:

1. **One ContextSpec, one dispatcher call.** All six `--review` modes load `dekspec/context-specs/role-spec-reviewer.md` (`role_identity == "spec-reviewer"`) and call the single `Reviewer().dispatch` surface — no per-skill divergence in the dispatch logic.
2. **Findings route into one audit surface.** The returned `list[Finding]` reuses the LOCKED AE-003 `Finding` dataclass verbatim and is presented at the IC-016 default severity `P2` — no parallel finding record, no per-skill reshaping.
3. **Additive, not a replacement.** Each `--review` mode ADDS this dispatch path and PRESERVES its existing interactive walkthrough / Open-Issues loop. The dispatch is grafted in alongside the walkthrough; it does not restructure it.

This file is the source of truth for *what the shared dispatch does*. Each `--review` mode cites it and grafts the four-step call below.

## The shared four-step dispatch path

Every `--review` mode performs the same four steps. The mode already holds the artifact-under-review (the file it is reviewing); the only IO it performs is loading the role-scoped ContextSpec.

1. **Load the `spec-reviewer` ContextSpec.** Read `dekspec/context-specs/role-spec-reviewer.md` through the LOCKED `parse_context_spec` reader (`from dekspec.constraint_compiler.parser import parse_context_spec`). The result is a `context_spec` dict with `context_spec["role_identity"] == "spec-reviewer"` — the same ContextSpec for ALL six skills (INT-141 §Open Issue (a)). The caller owns this IO.
2. **Load the artifact-under-review.** This is the file the `--review` mode already has in hand (the parsed Intent / WS / IC / AE / ADR / IB the skill is reviewing). The caller owns this IO too — the dispatcher is IO-free (IC-016 §Shared Conventions: `parse_* owns IO; dispatch owns review logic`).
3. **Call the dispatcher.** `Reviewer().dispatch(context_spec, artifact) -> list[Finding]` from `dekspec.spec_review.reviewer`, per IC-016. The call is in-process and synchronous; it routes on `context_spec["role_identity"]` and returns the LOCKED AE-003 `Finding` records (`dekspec.fidelity_audit.linkage.Finding`) — possibly an empty list. `dispatch` performs no file IO and no side-effecting emit.
4. **Route the findings into the AE-003 surface at default P2.** Present each returned `Finding` to the engineer at its severity (default `P2` per IC-016 — approval-blocking, NOT auto-merge) ALONGSIDE the mode's existing walkthrough / Open-Issues items. Routing these findings into the AE-003 audit surface is the consumer's responsibility (the `SPEC-REVIEW` audit-rule family, daughter C / `spec_review.reviewer` → `spec_review_rules`); the dispatcher only returns them.

The escalation conditions the Spec-Reviewer fires on are carried by `role-spec-reviewer.md` §Escalation Triggers (e.g. a spec that claims to derive from an Architecture Element or ADR absent from review scope; scope creep beyond the governing Intent; an adversarial-context-separation violation). Those are the signals the dispatch surfaces as `SPEC-REVIEW` findings.

## Reference dispatch block (inline-and-parameterize in your `--review` mode)

Each `--review` mode grafts the block below at its dispatch seam — for `write-intent` at the validate/exit boundary; for the other five alongside the inline Open-Issues loop. Substitute `<ArtifactType>` / `<artifact-under-review>` for the skill's own artifact (the conceptual `Reviewer<ArtifactType>` specialization IC-016 names — e.g. `ReviewerIntent`, `ReviewerWS`, `ReviewerIC`, `ReviewerAE`, `ReviewerADR`, `ReviewerIB`). The dispatch logic itself does not diverge per skill; only the call-site seam and the artifact do.

```prompt
Spec-Reviewer dispatch (shared `reviewer_mode` path — see
`skills/_lib/reviewer_mode.md`). PRESERVE the existing walkthrough / Open-Issues
loop; ADD this dispatch alongside it:

1. Load the spec-reviewer ContextSpec:
       from dekspec.constraint_compiler.parser import parse_context_spec
       context_spec = parse_context_spec("dekspec/context-specs/role-spec-reviewer.md")
   # context_spec["role_identity"] == "spec-reviewer" for ALL six --review modes.
2. Take the <ArtifactType> artifact this --review mode already holds
   (the <artifact-under-review> you are reviewing). The caller owns this IO;
   the dispatcher is IO-free.
3. Dispatch through the shared Reviewer<ArtifactType> surface:
       from dekspec.spec_review.reviewer import Reviewer
       findings = Reviewer().dispatch(context_spec, artifact)  # -> list[Finding], per IC-016
4. Present each returned Finding to the engineer at its severity (default P2 per
   IC-016 — approval-blocking, not auto-merge), alongside the existing
   walkthrough / open-issue items. Do not reshape the Finding records; route
   them into the AE-003 surface via the SPEC-REVIEW audit-rule family.
```

## Contract invariants

- **One ContextSpec for all six skills.** Every `--review` mode loads `role-spec-reviewer.md` (`role_identity: spec-reviewer`) — not a per-artifact-kind role (INT-141 §Open Issue (a)).
- **IO-free dispatcher.** `Reviewer().dispatch` performs no file IO. The caller (`reviewer_mode`) loads the ContextSpec via `parse_context_spec` and already holds the artifact (IC-016 §Shared Conventions).
- **Finding shape is the LOCKED AE-003 `Finding`, verbatim.** `dekspec.fidelity_audit.linkage.Finding` — no parallel record (IC-016 §Shared Conventions).
- **Default severity `P2`.** All `SPEC-REVIEW` findings emit at `P2` — approval-blocking, no per-rule promotion/demotion (INT-141 §Open Issue (d); IC-016 default emit severity).
- **Additive wiring.** The dispatch is ADDED alongside each skill's existing walkthrough / Open-Issues loop; the loop is preserved.
- **Advisory, not auto-merge.** Findings gate engineer approval; they do NOT trigger auto-merge and do NOT retroactively review the LOCKED corpus (newly-authored / `--unlock`-revised artifacts only).
- **Token contract.** Each of the six `--review` modes references `reviewer_mode` / `spec_review.reviewer` / `Reviewer<ArtifactType>` so the Mission predicate `six-write-skills-invoke-shared-dispatcher` grep matches per skill dir.

## Links

- IC-016 `reviewer-dispatcher-contract` — the LOCKED `Reviewer.dispatch(context_spec, artifact) -> list[Finding]` boundary this lib consumes.
- INT-141 `review-mode-wiring` — the parent Intent (MSN-019 daughter C).
- IB-126 `review-mode-wiring` — the Implementation Brief authoring this lib + the six wirings + the `SPEC-REVIEW` family.
- `dekspec/context-specs/role-spec-reviewer.md` (CS-002) — the `spec-reviewer` ContextSpec all six `--review` modes load.
- AE-003 Fidelity Audit Engine — the `Finding` dataclass + the audit surface the `SPEC-REVIEW` family routes findings into.
- AE-006 Skills Library — the AE this lib + the six `--review` modes live within.
