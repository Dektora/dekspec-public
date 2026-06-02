# ADR-NNN: [Verb-first, specific title]

## Status

PROPOSED

*Valid statuses:* `TODO` → `DRAFT` → `PROPOSED` → `ACCEPTED` → `LOCKED` | any stage → `DEPRECATED` | `SUPERSEDED` (ADR-specific terminal)

- **TODO** — placeholder; needs review and rewrite against current system state
- **DRAFT** — being written; anything goes
- **PROPOSED** — complete draft ready for review; engineer has not yet accepted
- **ACCEPTED** — engineer approved; downstream work may exist; substantive changes allowed but must cascade
- **LOCKED** — frozen; editorial amendments only; unlock back to PROPOSED for substantive changes
- **DEPRECATED** — terminal; retired from any stage when the artifact is no longer needed
- **SUPERSEDED** — terminal, ADR-specific; the decision has been replaced by a newer ADR

## Supersession

*Supersedes:* [ADR-NNN or "none"]
*Superseded by:* [ADR-NNN or "none"]

## Related Architecture Elements

[The Architecture Element(s) this decision materially shapes. **Linkage is mandatory** — every ADR must link to at least one AE (linkage integrity rule L2). A decision that doesn't shape any AE is either too small to warrant an ADR or describes a slice that itself needs an AE first.]

[The parser recognizes four bullet shapes; pick whichever reads cleanest:
- `AE-NNN: Title — desc`           (plain, unbulleted)
- `- AE-NNN: Title — desc`         (bulleted with colon)
- `- [AE-NNN](path) — desc`        (markdown link form)
- `- **AE-NNN Title** — desc`      (bold-wrapped, no colon)
The `— desc` clause is what the audit shows as the rationale; keep it concise.]

- AE-NNN: [Title] — [which aspect of the AE's description this decision shapes]
- AE-NNN: [Title] — [which aspect this decision shapes]

*Heritage note: This section was added during the DN→AE migration (2026-04-27). Pre-migration ADRs are valid but should backfill this field when next edited.*

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

## Date

[YYYY-MM-DD — the date the decision was made, which may predate when this ADR was written]

## Deciders

[Who made or approved this decision — names, roles, or agents]

## Context and Decision Drivers

[What was true when this decision was made. Past tense — narrative about the situation that motivated the decision, not the decision itself. Keep at the decision/rationale level: no fenced code, no function signatures, no schema tables. See `/write-adr --help` for full drift rules (D1–D9).]

**Decision drivers:**
- [Driver 1 — the force or constraint that shaped the choice]
- [Driver 2]

*Technical story:* [Link to issue, bead, or spec that triggered this — or "none"]

## Decision

[What was decided. One clear statement, then why this option over the alternatives in this system's specific context.]

*Decision-level only. No fenced code blocks beyond 2-line wire-format illustrations where the format IS the decision. No function / method / class signatures. No step-by-step procedures of 3 or more items. No schema / dtype / kwarg tables. No algorithmic math or derivations (state the decision, not the formula). No per-type dispatch enumerations with mechanics. No magic-number configuration values paired with justifying prose (move tunable defaults to the constants-management Working Spec, WS-019). No file paths to implementation (`*.py`, `services/…`, `api_server/…`). No "Key files" section or bullet. Algorithms belong in Working Specs; schemas and wire formats belong in Interface Contracts. See `/write-adr --help` for the full D1–D9 drift rules.*

## Options Considered (if applicable)

*This section is optional. Include when genuine alternatives were evaluated. Omit when documenting a straightforward architectural decision.*

### Option A: [name]

[Description.]

**Pros:** [specific to this system]
**Cons:** [specific to this system]

### Option B: [name]

[Description.]

**Pros:** [specific to this system]
**Cons:** [specific to this system]

## Consequences

**Positive:**
- [Consequence 1]

**Negative:**
- [Consequence 1]

## Validation

**Observable confirmation:**
[Concrete, observable criteria or metrics that verify the decision was correct after implementation. What can be measured, probed, or directly observed.]

**Reconsideration triggers:**
[Conditions or events that would cause this decision to be revisited — e.g., changed assumptions, exceeded thresholds, contradicted measurements, new constraints.]

*Both sub-blocks are required. Historical ADRs using combined-prose form are grandfathered; new ADRs from template revision 2026-04-24 forward use the split structure.*

## Links

- [Related ADRs, specs, probes, or external references]

## Open Issues

[Design-level questions, contradictions, and concerns. Logged during initial drafting, audits, reviews, or cascades from other artifacts. Resolve via `/write-adr --review`.]

*Scope: design-level only. Code-gap observations ("code does X but spec says Y") belong in `dekspec/divergences/DIV-NNN-*.md` or `br`, not here.*

- [ ] [Issue description] — **Source:** [initial draft / audit / review / cascade from \<artifact\>] — **Severity:** [`P0` / `P1` / `P2` / `P3`]

**Severity key:** `P0` = production-incident / cost-runaway reserve. `P1` = critical / blocking — prevents status advancement. `P2` = important / approval-blocking. `P3` = advisory / tracked-only — does not gate progress. Historical aliases (parser accepts indefinitely per ADR-013): `blocking` → `P1`; `non_blocking` → `P3`; `critical` → `P1`; `important` / `warning` → `P2`; `minor` / `info` → `P3`. See `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder + alias map.

## Amendment Log

*Add an entry for every change made after Locked status, or when unlocking back to Proposed.*

**Compressed-format policy (added convergence-v2 iter-7 Δ-SQ-17, 2026-04-22).** Entries SHOULD follow a one-line-per-entry format. Target: `| YYYY-MM-DD | <Type> | <one-sentence what + reference to delta-doc / commit > | <author> |`. Detailed change narrative (rationale, multi-paragraph justifications, cross-artifact impact analysis) belongs in the git commit message — not in the spec body. Historical entries are preserved as-is; the policy applies to **new** entries going forward. An amendment log that grows past ~10 entries per year of spec lifetime is a smell and should be trimmed into a pinned-to-tag release note rather than carried in the spec.

| Date | Type | Change | Author |
|------|------|--------|--------|
| YYYY-MM-DD | Editorial / Unlock / Substantive | <one-sentence summary + delta / commit reference> | [name or agent] |
