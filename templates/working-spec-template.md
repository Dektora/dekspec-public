# Working Spec: [Feature/Component Name]

## Status

DRAFT

*Valid statuses:* `TODO` → `DRAFT` → `PROPOSED` → `ACCEPTED` → `LOCKED` | any stage → `DEPRECATED`

- **TODO** — placeholder; needs review and rewrite against current system state
- **DRAFT** — being written; anything goes
- **PROPOSED** — complete draft ready for review; engineer has not yet accepted
- **ACCEPTED** — engineer approved; downstream work may exist; substantive changes allowed but must cascade
- **LOCKED** — frozen; editorial amendments only; unlock back to PROPOSED for substantive changes
- **DEPRECATED** — terminal; retired from any stage when the artifact is no longer needed (redundant with other specs, or planned work abandoned)

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

## Silent Failure Domain(s)

[Which of the five domains this component lives in. Multiple domains = review whether to split.]

- [ ] Transformer internals (position IDs, injection layer, KV cache)
- [ ] Numerical precision (quantization, tiered compression, serialization round-trips)
- [ ] GPU multi-process isolation (device assignment, process crash recovery)
- [ ] Graph consistency (shadow graph / Neo4j flush, phantom nodes)
- [ ] Timeline coherence (topic segmentation, tier assignment, decay, shadow timeline / PostgreSQL)

## Expertise Audit Record

[Which roles were triggered and which were not. The Critic verifies by checking the trigger rules below against the spec's Interfaces and Domain Constraints — not by evaluating rationales.]

| Role | Triggered | Trigger rule | Rationale |
|------|-----------|-------------|-----------|
| ML / Model Behavior Expert | Yes / No | Required if spec touches injection layer, position IDs, KV cache, or attention mask | [Why or why not] |
| Quantization / Precision Expert | Yes / No | Required if any tensor dtype, bit depth, or precision threshold appears in Interfaces or Domain Constraints | [Why or why not] |
| CUDA Multi-Process Expert | Yes / No | Required if Process Interfaces names more than one device or process boundary | [Why or why not] |
| Graph / Multi-Store Expert | Yes / No | Required if Domain Constraints read/write path references shadow graph, Neo4j, shadow timeline, or PostgreSQL | [Why or why not] |
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

*Structural-reachability guardrail (2026-04-24, per ws-audit proposal §3.5 T-coverage).* Every substantive behavioral claim you write here must also be reachable from a structured section — a numbered Business Rule, a Failure Behavior row, a populated Domain Constraint row (or its Rationale column when the row's Scope and Value are populated), a conditional Contract row (Model / Graph / Timeline / Quantization), a Governing Formula, an Eval Hook, or a Golden I/O example. Claims that exist only in this prose are un-derivable — the IB generator and the test generator cannot consume them, and the behavior will not be enforced downstream. Write the narrative here; encode the contract in the structured sections.

## What This Does NOT Do

[For each active silent failure domain checked above, state at least one exclusion that defines the domain boundary for this spec. Generic exclusions that don't relate to a failure domain are also permitted but do not satisfy this requirement.]

*Structural-reachability guardrail (same as §What This Does).* Exclusions here must be matched by absence of behavior in the structured sections — a negative claim here without a corresponding positive structural absence is an un-verifiable exclusion.

- **[Domain]:** [Exclusion — what this component does not do that a reader might assume it does]

## Interfaces

### Data Interfaces

[What data crosses the component boundary: tensors, embeddings, scores, config values.]

| Interface | Direction | Type / Shape / Dtype | Source or Consumer | Guarantees (dtype, shape, ordering, not-null, device) |
|-----------|-----------|----------------------|--------------------|------------------------------------------------------|
| | in / out | | | |

### Process Interfaces

[Which process, device, or transport is involved. Omit if single-process, in-memory only.]

| Boundary | Transport | Device | Serialization | Failure mode |
|----------|-----------|--------|---------------|-------------|
| | HTTP / in-memory / shared cache | cuda:N / cpu | JSON dict / torch.save / none | |

### Dependencies

| Dependency | Interface | Failure behavior |
|------------|-----------|-----------------|
| | | |

## Domain Constraints

[First-class constraints that prevent silent failures. Carry these verbatim into IBs and beads. For rows touching an active silent failure domain, n/a requires a justification — the Critic will flag unjustified n/a on domain-critical rows.]

| Constraint | Value | Scope | Rationale |
|------------|-------|-------|-----------|
| CUDA device | cuda:N / cpu / n/a — [justification if n/a] | all-IBs / IB-specific | |
| Tensor dtype in | bfloat16 / float32 / n/a — [justification if n/a] | all-IBs / IB-specific | |
| Tensor dtype out | bfloat16 / float32 / n/a — [justification if n/a] | all-IBs / IB-specific | |
| Read path | shadow / persistent / n/a — [justification if n/a] | all-IBs / IB-specific | |
| Write path | shadow+buffered / persistent_direct / n/a — [justification if n/a] | all-IBs / IB-specific | |
| Precision threshold | max error ≤ X / n/a — [justification if n/a] | all-IBs / IB-specific | |
| Position ID format | M-RoPE 3-channel / 1D / n/a — [justification if n/a] | all-IBs / IB-specific | |
| Token budget | N tokens / unbounded | all-IBs / IB-specific | |
| Do not touch | [function/file — reason] | all-IBs / IB-specific | |

**Scope key:** `all-IBs` = must appear in every IB derived from this spec. `IB-specific` = carried only into the IB that touches it.

## Governing Formulas

[Configurable string expressions (per ADR-022) that drive this component's behavior. Omit section if no formulas apply.]

| Formula | Expression | Variables | Units / Scale | Valid range | Validated by |
|---------|-----------|-----------|---------------|-------------|-------------|
| | | | | | caller / this component / config loader |

[If "Validated by" is "this component," a corresponding Business Rule must assert the range check.]

## Business Rules

[Every rule must be testable. Number for reference in IBs and beads. Tag with the silent failure domain it guards (or "general" if none).]

*Testability guardrail (2026-04-24, per ws-audit proposal §3.5 T-coverage).* Every Business Rule must reduce to a testable assertion — a predicate a unit or component test can check. If the behavior you are specifying cannot be reduced to a concrete assertion, it does not belong here: either decompose until each piece is testable, move it to §What This Does / the Source AEs (if it is vision), move it to §Failure Behavior (if it is error-path), or move it to Interfaces (if it is a boundary property). A Business Rule stated as a paragraph of prose is an un-derivable claim — `/write-tests` will not generate a test for it, `/write-ibs` will not carry it into an IB's acceptance criteria, and the pipeline will not enforce it.

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

**Severity key:** `P0` = production-incident / cost-runaway reserve (no artifact-side use today). `P1` = critical / blocking — must resolve before downstream IB authoring. `P2` = important / approval-blocking — IBs can be authored but beads cannot start. `P3` = advisory / tracked-only — does not gate progress.

**Authoring concepts (WS-specific, per WS-015 BR2):** `blocking (pre-IB)` (IBs cannot be authored until resolved → `P1` in IR per ADR-013) and `blocking (pre-code)` (IBs can be authored but beads cannot start → `P2` in IR per ADR-013) are useful IB-vs-bead boundary discussion tools an author may invoke when drafting Open Issues entries; both normalize to their canonical tier at parse time.

**Historical aliases** (parser accepts indefinitely, normalized at parse time per ADR-013): `blocking_pre_ib` → `P1`; `blocking_pre_code` → `P2`; `blocking` → `P1`; `non_blocking` → `P3`; `critical` → `P1`; `important` / `warning` → `P2`; `minor` / `info` → `P3`. Use canonical `P0..P3` in new authoring. See `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder + alias map.

[Zero `P1` open issues must remain when `/write-ibs` is invoked.]

---

*The following contract sections are conditionally mandatory. If any Domain Constraints row touching the contract's domain is populated (non-n/a), the corresponding contract section is required. Delete only when all relevant Domain Constraints rows are n/a with justification.*

*Integration-test scope guardrail (2026-04-24, per ws-audit proposal §12.2).* Each of the four conditional Contracts (Model Behavior, Graph Behavior, Timeline Behavior, Quantization) is the **integration-test scope definition for its domain**. The rows of these sections are read by `/write-tests` (for deterministic paths) and `/write-evals` (for model-output behaviors) to generate integration-level test cases. A missing or under-populated row means the integration suite has no way to exercise that behavior — the Contract is what makes the domain's cross-component interaction verifiable.

## Refactor Targets

*Conditional — include when the WS declares `role: refactoring-ws` in its front-matter. The section permits file-path enumeration of the refactor scope, which is scope-defining content for a refactoring WS (per ws-audit proposal R2 Δ-WS-18 Option (b) resolution, 2026-04-24). Without `role: refactoring-ws` declared, this section is a T9 narrative-file-path violation — do NOT include.*

*Scope guardrail for refactoring-WSes.* A refactoring WS enumerates the concrete refactor surface here (file paths, module boundaries, function-signature changes that define the scope) WITHOUT restating the behavior change in prose. Behavioral invariants live in §Business Rules as usual; this section is a pointer table telling the reader "the refactor touches these files in these ways." Once the refactor lands and the corresponding IB is closed out, this section can be compressed or retired.

| File / module | Scope-defining change | Behavioral invariant (BR #) |
|---------------|-----------------------|-----------------------------|
| | | |

## Model Behavior Contract

*Required when Domain Constraints includes position ID format, injection-related dtype, or attention-related constraints.*

- Injection layer: [which layer(s)]
- Position ID construction: [how M-RoPE channels are built and offset]
- KV cache behavior: [what happens across turns]
- Attention mask: [how injected positions are included]
- Generation trigger: [what the last token/position is before generation]

## Graph Behavior Contract

*Required when Domain Constraints read/write path references shadow graph or Neo4j.*

- Read path: [shadow | neo4j — when each is used]
- Write path: [shadow+buffered | neo4j_direct]
- Flush trigger: [threshold, timer, or explicit]
- Flush failure behavior: [what happens — not "graceful degradation"]
- Phantom detection: [how shadow/persistent divergence is detected]
- Tenant isolation: [how client_id is enforced on every query path]

## Timeline Behavior Contract

*Required when Domain Constraints read/write path references shadow timeline or PostgreSQL, or when spec touches topic segmentation, tier assignment, or decay.*

- Read path: [shadow timeline | PostgreSQL — when each is used]
- Write path: [shadow+buffered | PostgreSQL direct]
- Flush failure behavior: [what happens]
- Topic boundary validation: [how boundary accuracy is verified]
- Decay reference: [capture time | current time | conversation time]
- Pre-quantized copy staleness: [when re-quantization is triggered, or "never"]
- Tenant isolation: [how conversation_id + client_id filtering is enforced]

## Quantization Contract

*Required when Domain Constraints includes tensor dtype or precision threshold with non-n/a values.*

- Input dtype: [bfloat16 | float32]
- Output dtype: [bfloat16 | float32]
- Bit depths: [which levels]
- Max reconstruction error: [per bit depth]
- Round-trip fidelity: [serialize → deserialize acceptable delta]
- Constant tensor handling: [how range < 1e-10 is detected and handled]

## Eval Hooks

*For every behavior involving model output only. Deterministic behaviors get test cases in the IB's Done When checklist, not here.*

- [Eval name: input scenario → expected output range → pass criterion (e.g., ≥ 80% of cases) → what failure means]

## Amendment Log

*Add an entry for every change made after Locked status, or when unlocking back to Proposed.*

**Compressed-format policy (added convergence-v2 iter-7 Δ-SQ-17, 2026-04-22).** Entries SHOULD follow a one-line-per-entry format. Target: `| YYYY-MM-DD | <Type> | <one-sentence what + reference to delta-doc / commit > | <author> |`. Detailed change narrative belongs in the git commit message — not in the spec body. Historical entries are preserved as-is; the policy applies to **new** entries going forward. An amendment log exceeding ~10 entries per year of spec lifetime is a smell; trim older entries into a pinned-to-tag release note rather than carrying them in the spec.

| Date | Type | Change | Author |
|------|------|--------|--------|
| YYYY-MM-DD | Editorial / Unlock / Substantive | <one-sentence summary + delta / commit reference> | [name or agent] |
