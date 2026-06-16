# Interface Contract: [Name]

## Status

TODO

*Valid statuses:* `TODO` → `DRAFT` → `PROPOSED` → `ACCEPTED` → `LOCKED` | any stage → `DEPRECATED`

- **TODO** — placeholder; needs review and rewrite against current system state
- **DRAFT** — being written; anything goes
- **PROPOSED** — complete draft ready for review; engineer has not yet accepted
- **ACCEPTED** — engineer approved; downstream work may exist; substantive changes allowed but must cascade
- **LOCKED** — frozen; editorial amendments only; unlock back to PROPOSED for substantive changes
- **DEPRECATED** — terminal; retired from any stage when the artifact is no longer needed

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

## Version

[Semantic version. Bump major on breaking changes, minor on additive changes, patch on editorial.]

## Silent Failure Domain(s)

[Which of the five domains this boundary touches. A contract spanning two domains is a signal to review whether it should be split.]

- [ ] Transformer internals (position IDs, injection layer, KV cache)
- [ ] Numerical precision (quantization, wave compression, serialization round-trips)
- [ ] GPU multi-process isolation (device assignment, process crash recovery)
- [ ] Graph consistency (shadow graph / Neo4j flush, phantom nodes)
- [ ] Timeline coherence (topic segmentation, tier assignment, decay, shadow timeline / PostgreSQL)

## Governing ADRs

- [ADR-NNN: Title — one-sentence summary of how it constrains this contract]

## Purpose

[1-2 paragraphs: what boundary this contract defines, why it exists as a separate contract rather than prose in a Working Spec, and what independence it enables (e.g., either side can be implemented, tested, or replaced independently).]

## Parties

[Who is on each side of this boundary. Name the components, their roles (producer/consumer, reader/writer, caller/callee), and which process/device each runs on.]

- **[Party A]** — [role, process, device, authoritative for what]
- **[Party B]** — [role, process, device, authoritative for what]

[For contracts with multiple consumers (e.g., adapter patterns), list each consumer and what it uses the interface for.]

[**Party-AE linkage is structured-only.** Declare every AE link in the `### Provider AE` / `### Consumer AEs` subsections below. AE-NNN references inside Party body prose are treated as references, not links — they will not show up in the IR's `parties[].ae_id` field and will not satisfy `L4-IC-AE-MISSING` / `L6-BACKLINK`. Keep prose mentions for narrative context; declare the linkage explicitly in the subsections.]

### Provider AE

[The Architecture Element that owns the provider side of this boundary. Single value — every IC has exactly one provider.]

AE-NNN: [Title]

### Consumer AEs

[The Architecture Element(s) that consume this contract. List each — adapter and multi-tenant patterns are common. Use "none" explicitly when the contract is external-facing only and has no DekSpec-tracked consumer.]

- AE-NNN: [Title] — [what this consumer uses the interface for]
- AE-NNN: [Title] — [what this consumer uses the interface for]

*Heritage note: Provider AE / Consumer AEs were added during the DN→AE migration (2026-04-27) to make AE linkage explicit (linkage integrity rule L4). Pre-migration ICs without AE linkage are valid but should backfill these fields when next edited.*

## Relationship Pattern

[Which DDD context-mapping pattern describes this boundary. Choose one primary pattern; note a secondary if applicable. State who adapts when the interface changes.]

**Pattern:** [Open Host Service | Customer-Supplier | Anti-Corruption Layer | Conformist | Shared Kernel | Published Language]

**Change impact:** [When this interface changes, [Party X] adapts because [reason].]

*Available patterns:*
- **Open Host Service** — one side exposes a well-defined protocol for multiple independent consumers. Consumers adapt to the host's protocol.
- **Customer-Supplier** — consumer's needs drive the interface; supplier serves. Supplier adapts to customer needs.
- **Anti-Corruption Layer** — translation boundary protecting each side's internal model from the other. The ACL adapts; neither side changes its internal model.
- **Conformist** — one side accepts the other's model wholesale without ability to influence. The conformist adapts; the other side is external/immutable.
- **Shared Kernel** — both sides share a common model; changes require bilateral coordination.
- **Published Language** — a shared, well-documented format or protocol. Neither side owns it; changes go through format governance.

## Shared Conventions

[Conventions that apply across all operations in this contract: serialization format, content types, dtype handling, error response structure, tenant isolation rules.]

- [Convention 1]
- [Convention 2]

---

## Interface Definition

[The contract itself. Structure this section based on what the interface is:

- **HTTP API:** endpoints with request/response schemas, status codes, headers
- **Consistency contract:** warm/write/flush/read phases with data format and ordering guarantees
- **In-process adapter:** function signatures with input/output contracts, preconditions, postconditions

Use tables for structured data. Be specific about types, shapes, dtypes, and ordering guarantees.]

---

## Domain Constraints

[**Optional — omit the section entirely if not applicable** to this contract or project. This section captures project-specific cross-cutting constraints that apply at the boundary and must be carried into any IB that implements either side — e.g., compute-device pinning, serialization formats, precision thresholds, encoding/coordinate conventions, time/timezone discipline, numeric precision. If your project doesn't have such constraints, delete this section so the IC stays focused on the contract surface.]

| Constraint | Value | Rationale |
|------------|-------|-----------|
| [constraint name] | [value or `n/a` with justification] | [why this value, what breaks at this boundary if it drifts] |

[*Example rows — replace or remove. Originally drawn from a tensor-on-the-wire ML project; substitute your project's cross-cutting constraints.*

- *CUDA device — device or n/a — justification if n/a*
- *Tensor dtype on wire — dtype*
- *Tensor dtype at rest — dtype*
- *Serialization format — JSON dict / torch.save / protobuf / n/a*
- *Precision threshold — max error or n/a*]

## Error Semantics

[Every error condition at this boundary must have a stated behavior. Both parties must agree on what happens. "Silent degradation" is not a valid behavior.]

| Error condition | Producing party | Detection | Behavior | Consumer responsibility |
|-----------------|----------------|-----------|----------|----------------------|
| | [Party A / Party B] | [observable signal] | [raise / reject / retry] | [what the other side must do] |

## Consistency Guarantees

[What consistency properties hold and what does NOT hold. Be explicit about both. Omit this section only for stateless request-response contracts with no shared state.]

**Holds:**
- [Guarantee 1]

**Does NOT hold:**
- [Non-guarantee 1 — why, and what callers must do instead]

## Options Considered / Rejected Rationale

[Record the write-ic Phase-2 **design-twice** comparison for a high-blast-radius boundary — one that binds many parties or governs many ADRs, where the first design is most expensive to lock blindly. Three competing designs are drafted (one each under *minimize-method-count*, *maximize-flexibility*, *optimize-the-common-case*), compared on deep-module criteria (no leaked invariants/ordering, a clear seam, a minimal surface hiding maximal complexity, deep-not-shallow per ADR-036), and the deepest is synthesized. Capture what was compared and why the surviving surface is the deepest, so a reviewer can see the boundary was *competed*, not merely depth-checked once.]

[Omit this section for a trivial / low-blast-radius boundary — the single deep-module pass is sufficient there. The `T-IC-OPTIONS-MISSING` audit rule (P3 advisory) fires only on a high-blast-radius IC that ships without this section populated.]

- **Design A — minimize-method-count:** [the smallest-surface candidate; why kept or rejected]
- **Design B — maximize-flexibility:** [the most-configurable candidate; why kept or rejected]
- **Design C — optimize-the-common-case:** [the candidate tuned for the dominant call path; why kept or rejected]
- **Synthesized result:** [the surviving surface and the deep-module reason it is deepest — what complexity it hides that the rejected designs leaked onto callers]

## Open Issues

[Issues, questions, contradictions, and concerns. Logged during initial drafting, audits, reviews, or cascades from other artifacts. Resolve via `/write-ic --review`.]

- [ ] [Issue description] — **Source:** [initial draft / audit / review / cascade from \<artifact\>] — **Severity:** [`P0` / `P1` / `P2` / `P3`]

**Severity key:** `P0` = production-incident / cost-runaway reserve. `P1` = critical / blocking — prevents status advancement. `P2` = important / approval-blocking. `P3` = advisory / tracked-only — does not gate progress. Historical aliases (parser accepts indefinitely per ADR-013): `blocking` → `P1`; `non_blocking` → `P3`; `critical` → `P1`; `important` / `warning` → `P2`; `minor` / `info` → `P3`. See `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder + alias map.

## Amendment Log

*Add an entry for every change made after Locked status, or when unlocking back to Proposed.*

**Compressed-format policy (added convergence-v2 iter-7 Δ-SQ-17, 2026-04-22).** Entries SHOULD follow a one-line-per-entry format. Target: `| YYYY-MM-DD | <Type> | <one-sentence what + reference to delta-doc / commit > | <author> |`. Detailed change narrative belongs in the git commit message — not in the IC body. Historical entries are preserved as-is; the policy applies to **new** entries going forward.

| Date | Type | Change | Author |
|------|------|--------|--------|
| YYYY-MM-DD | Editorial / Unlock / Substantive | <one-sentence summary + delta / commit reference> | [name or agent] |
