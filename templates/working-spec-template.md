# Working Spec: [Feature/Component Name]

## Status

DRAFT

*Valid statuses:* `DRAFT` → `PROPOSED` → `ACCEPTED` | any stage → `DEPRECATED` (ADR-046: a living reference rests at ACCEPTED; it is revised with cascade, never locked)

- **DRAFT** — being written; anything goes
- **PROPOSED** — complete draft ready for review; engineer has not yet accepted
- **ACCEPTED** — engineer approved; downstream work may exist; substantive changes allowed but must cascade
- **DEPRECATED** — terminal; retired from any stage when the artifact is no longer needed (redundant with other specs, or planned work abandoned)

*A Working Spec is the home of behavioral requirements that outlive or span Implementation Briefs (ADR-056). It is optional upstream of an IB — author one only when it adds that. IBs reference its sections as obligations (`- **O-n** → WS-NNN §Business Rules`) and `dekspec ib context` delivers the canonical text; nothing here is copied into an IB.*

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

## Silent Failure Domain(s)

[Which domains this component can fail in *silently* — wrong results without an error. Several domains = review whether to split. The list is neutral and open: replace or extend it with your project's own domains (or override this template in `dekspec/templates/`).]

- [ ] Numerical precision (rounding, serialization round-trips, lossy encodings)
- [ ] Concurrency and process isolation (races, partial failure, crash recovery)
- [ ] Data consistency across stores (write ordering, flush, phantom or orphaned records)
- [ ] Time and ordering (clocks, time zones, sequencing, idempotency)
- [ ] Resource limits (memory, quotas, rate limits, timeouts)

## Expertise Audit Record

[Which roles were triggered and which were not. The Critic verifies by checking the trigger rules below against the spec's Interfaces and Domain Constraints — not by evaluating rationales.]

| Role | Triggered | Trigger rule | Rationale |
|------|-----------|-------------|-----------|
| ML / Model Behavior Expert | Yes / No | Required if the spec's behavior depends on model output or model internals | [Why or why not] |
| Domain specialist | Yes / No | Required when a domain constraint below needs specialist review | [Which specialty, and why or why not] |
| Embedding Space Geometer | Yes / No | Required if Governing Formulas includes similarity, distance, or centroid computation | [Why or why not] |
| Pipeline Sequencing Analyst | Yes / No | Required if Dependencies lists another pipeline stage or spec changes stage ordering | [Why or why not] |

## Related Architecture Elements

[The L1 Architecture Element(s) whose architectural description this spec measures or constrains. **Linkage is mandatory** — every WS must link to at least one AE (per the post-DN→AE migration linkage integrity rule L3). If the spec measures behavior at the boundary of multiple AEs, list each.]

- AE-NNN: [Title] — [which aspect of the AE's description this spec measures or constrains]
- AE-NNN: [Title] — [which aspect this spec measures or constrains]

*Heritage note: This section was previously titled "Source Design Note" and accepted a single DN-NNN value. The DN→AE migration (2026-04-27) renamed and broadened it: AE replaces DN, multiple AEs are permitted, and at least one is required. Specs migrated from the DN era keep their original linkage as AE-NNN (numeric continuity preserved).*

## Governing ADRs

- [ADR-NNN: Title — one-sentence summary of how it constrains this spec]

## Interface Contracts

*(optional; include when this spec describes behavior crossing an IC-governed boundary)*

**Consumed contracts:** IC-NNN (short name), IC-NNN (short name)
**Defined contracts:** IC-NNN (if this spec's boundary becomes an IC)

## What This Does

[1-2 paragraphs: what the component does, its role in the system.]

**Mechanism:** [One mandatory sentence: "This component [verb] [exact artifact] [at/before/after exact boundary] [resulting in exact state change]."]

*Structural-reachability guardrail (2026-04-24, per ws-audit proposal §3.5 T-coverage).* Every substantive behavioral claim you write here must also be reachable from a structured section — a numbered Business Rule, a Failure Behavior row, a populated Domain Constraint row (or its Rationale column when the row's Applies-to and Value are populated), a domain contract section (when your template defines one), a Governing Formula, an Eval Hook, or a Golden I/O example. Claims that exist only in this prose are un-derivable — the IB generator and the test generator cannot consume them, and the behavior will not be enforced downstream. Write the narrative here; encode the contract in the structured sections.

## What This Does NOT Do

[For each active silent failure domain checked above, state at least one exclusion that defines the domain boundary for this spec. Generic exclusions that don't relate to a failure domain are also permitted but do not satisfy this requirement.]

*Structural-reachability guardrail (same as §What This Does).* Exclusions here must be matched by absence of behavior in the structured sections — a negative claim here without a corresponding positive structural absence is an un-verifiable exclusion.

- **[Domain]:** [Exclusion — what this component does not do that a reader might assume it does]

## Interfaces

### Data Interfaces

[What data crosses the component boundary: records, messages, files, scores, config values.]

| Interface | Direction | Type / Shape | Source or Consumer | Guarantees (type, shape, ordering, not-null, units) |
|-----------|-----------|--------------|--------------------|-----------------------------------------------------|
| | in / out | | | |

### Process Interfaces

[Which process, host, device, or transport is involved. Omit if single-process, in-memory only.]

| Boundary | Transport | Placement | Serialization | Failure mode |
|----------|-----------|-----------|---------------|-------------|
| | HTTP / queue / in-memory / shared cache | [host, process or device] | JSON / binary / none | |

### Dependencies

| Dependency | Interface | Failure behavior |
|------------|-----------|-----------------|
| | | |

## Domain Constraints

[First-class constraints that prevent silent failures. IBs reference them (`→ WS-NNN §Domain Constraints`); they are not copied into IBs. For rows touching an active silent failure domain, n/a requires a justification — the Critic will flag unjustified n/a on domain-critical rows.]

<!--
One row per constraint. Neutral examples: hardware/device placement,
numeric precision (max error, rounding mode), data-store or cache path
(which store is read or written, and when), latency budget, resource cap.
-->

| Constraint | Value | Applies to (all IBs / specific IB) | Rationale |
|------------|-------|------------------------------------|-----------|
| [constraint] | [value, or n/a — justification] | all IBs / IB-NNN | [why it matters] |

**Applies-to key:** `all IBs` = binding on every IB that references this spec. A specific IB = binding only on that IB.

A consumer that needs domain-specific rows or sections (fixed constraint rows, domain contract sections, specialist roles) should override this template with its own copy at `dekspec/templates/working-spec-template.md` — the resolver prefers the consumer copy (`tooling/dekspec/vendoring.py::resolve_template`).

## Governing Formulas

[Configurable string expressions (per the consuming project's scoring-formula decision, where it has one) that drive this component's behavior. Omit section if no formulas apply.]

| Formula | Expression | Variables | Units / Scale | Valid range | Validated by |
|---------|-----------|-----------|---------------|-------------|-------------|
| | | | | | caller / this component / config loader |

[If "Validated by" is "this component," a corresponding Business Rule must assert the range check.]

## Business Rules

[Every rule must be testable. Number them so IB obligations and acceptance tests can cite them (`→ WS-NNN §Business Rules`, BR n). Tag with the silent failure domain it guards (or "general" if none).]

*Testability guardrail (2026-04-24, per ws-audit proposal §3.5 T-coverage).* Every Business Rule must reduce to a testable assertion — a predicate a unit or component test can check. If the behavior you are specifying cannot be reduced to a concrete assertion, it does not belong here: either decompose until each piece is testable, move it to §What This Does / the Source AEs (if it is vision), move it to §Failure Behavior (if it is error-path), or move it to Interfaces (if it is a boundary property). A Business Rule stated as a paragraph of prose is an un-derivable claim — `/write-tests` will not generate a test for it, no IB acceptance condition can demonstrate it, and the pipeline will not enforce it.

1. **[Domain]** [Rule — testable assertion]
2. **[Domain]** [Rule — testable assertion]

[Each active silent failure domain must have at least one business rule. The Critic verifies this.]

## Failure Behavior

[Every failure mode must have a stated behavior. "Silent degradation" is not a valid behavior — state what the system does observably. Detection must be an observable, synchronous signal — "log" alone is not sufficient.]

*Observable-detection guardrail (2026-04-24, per ws-audit proposal §12.2).* Detection must be an **observable, synchronous** signal: `raise` (exception type named), `assert` (boolean condition), or `metric + raise` (metric emission paired with an exception). A plain log line is insufficient — it does not fail the test and does not wake any caller. Behavior must state what the system does observably: reject, roll back, retry with bounded semantics, surface an HTTP status, etc. `silent degradation`, `best-effort continuation`, `graceful fallback without signal` are not valid behaviors.

| Failure | Detection | Assertion type | Behavior | Recovery |
|---------|-----------|---------------|----------|----------|
| | [observable signal] | raise / assert / metric + raise | | |

## Open Issues

[Issues, questions, contradictions, and concerns. Logged during initial drafting, expertise audit, reviews, or cascades from other artifacts. Resolve via `/write-ws --review`.]

*Scope guardrail (2026-04-24, per ws-audit proposal §12.2).* Spec-coverage gaps and design-level questions only. Code-gap observations — "code does X but spec says Y at `<file>:<line>`" — belong in `dekspec/divergences/DIV-NNN-*.md` or `br`, **not here**. This section is for decisions the WS itself has not yet resolved.

- [ ] [Issue description] — **Source:** [initial draft / expertise audit / review / cascade from \<artifact\>] — **Severity:** [`P0` / `P1` / `P2` / `P3`]

**Severity key:** `P0` = production-incident / cost-runaway reserve (no artifact-side use today). `P1` = critical / blocking — must resolve before an IB takes this WS as its `Parent`. `P2` = important / approval-blocking — IBs can be authored but execution cannot start. `P3` = advisory / tracked-only — does not gate progress.

**Authoring concepts (WS-specific, per WS-015 BR2):** `blocking (pre-IB)` (IBs cannot be authored until resolved → `P1` in IR per ADR-013) and `blocking (pre-code)` (IBs can be authored but execution cannot start → `P2` in IR per ADR-013) are useful authoring-vs-execution boundary discussion tools an author may invoke when drafting Open Issues entries; both normalize to their canonical tier at parse time.

**Historical aliases** (parser accepts indefinitely, normalized at parse time per ADR-013): `blocking_pre_ib` → `P1`; `blocking_pre_code` → `P2`; `blocking` → `P1`; `non_blocking` → `P3`; `critical` → `P1`; `important` / `warning` → `P2`; `minor` / `info` → `P3`. Use canonical `P0..P3` in new authoring. See `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder + alias map.

[Zero `P1` open issues must remain when an IB takes this WS as its `Parent` (the L12 gate `/write-ibs` enforces). An IB that only references a section of this WS is not gated.]

## Refactor Targets

*Conditional — include when the WS declares `role: refactoring-ws` in its front-matter. The section permits file-path enumeration of the refactor scope, which is scope-defining content for a refactoring WS (per ws-audit proposal R2 Δ-WS-18 Option (b) resolution, 2026-04-24). Without `role: refactoring-ws` declared, this section is a T9 narrative-file-path violation — do NOT include.*

*Scope guardrail for refactoring-WSes.* A refactoring WS enumerates the concrete refactor surface here (file paths, module boundaries, function-signature changes that define the scope) WITHOUT restating the behavior change in prose. Behavioral invariants live in §Business Rules as usual; this section is a pointer table telling the reader "the refactor touches these files in these ways." Once the refactor lands and the corresponding IB is COMPLETE, this section can be compressed or retired.

| File / module | Scope-defining change | Behavioral invariant (BR #) |
|---------------|-----------------------|-----------------------------|
| | | |

## Eval Hooks

*For every behavior involving model output only. Deterministic behaviors get acceptance conditions in the IB's `## Acceptance` block, not here. An eval that gates an IB is one of its acceptance conditions (a `command:` verification with its own threshold).*

- [Eval name: input scenario → expected output range → pass criterion (e.g., ≥ 80% of cases) → what failure means]

## Amendment Log

*Add an entry for every substantive change made after ACCEPTED (a Working Spec never locks; it is revised with cascade — ADR-046).*

**Compressed-format policy (added convergence-v2 iter-7 Δ-SQ-17, 2026-04-22).** Entries SHOULD follow a one-line-per-entry format. Target: `| YYYY-MM-DD | <Type> | <one-sentence what + reference to delta-doc / commit > | <author> |`. Detailed change narrative belongs in the git commit message — not in the spec body. Historical entries are preserved as-is; the policy applies to **new** entries going forward. An amendment log exceeding ~10 entries per year of spec lifetime is a smell; trim older entries into a pinned-to-tag release note rather than carrying them in the spec.

| Date | Type | Change | Author |
|------|------|--------|--------|
| YYYY-MM-DD | Editorial / Substantive | <one-sentence summary + delta / commit reference> | [name or agent] |
