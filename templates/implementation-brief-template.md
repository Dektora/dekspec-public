# Implementation Brief: [Component/Feature]

**Spec:** `dekspec/working-specs/WS-NNN-[slug].md`
**Intent:** [`dekspec/intents/INT-NNN-slug.md` or "none" — the parent Intent for this IB. v5 introduced this field for IBs produced by `/write-intent --decompose`; legacy IBs and stand-alone WS-driven IBs may use "none".]
**Source AEs:** [AE-NNN, AE-NNN — the Architecture Elements this IB implements or changes; at least one required per linkage integrity rule L5]
**Depends on:** [IB names or "none"]
**Production gate:** [specific observable or "none"]
**Status:** PROPOSED — do not run /create-beads until Status is ACCEPTED

<!--
SECTIONS BELOW: which ones flow into the IB IR vs which are "author scratch pad"
=================================================================================
Canonical sections (extracted by parser, schema-validated, available to emitters):
  Goal · Out of Scope · Files to Modify · Do Not Touch · Governing ADRs ·
  Done When · Domain Constraints · Constraints & Decisions ·
  Open Issues · Amendment Log

  Note: Domain Constraints + Constraints & Decisions were promoted from
  scratch-pad → canonical in v0.40.0 (ds-ibx). They're now load-bearing
  IR fields: emitters and downstream consumers (e.g., DekFactory)
  read them off `dekspec.api`. See implementation-brief.schema.yaml.

Author scratch pad (rendered for the implementing engineer, NOT in the IR):
  Precedence · Escalation Protocol · Spec Context · Interface Contracts ·
  Probe Results · Quality Checklists · Test Promotion Criteria · Reuse Inventory

  Note: Reuse Inventory is not parsed into the IR, but its presence IS enforced
  by the upstream IB linter on code-bearing briefs (ds-0a7w, Reuse Firewall).

Scratch-pad sections are deliberately not loaded into the IR — they're
prompt-time scaffolding that helps the implementing engineer (or coding
agent) reason about precedence + escalation + checklist conformance. They
do not affect audit findings, contract-test generation, or AGENTS.md output.
If you need a scratch-pad section to drive enforcement, file a bead to
extend the IB schema (per audit divergence D-11's pattern).
-->


## Precedence

This IB was reviewed for conflicts before being written. Any ADR-vs-ADR or ADR-vs-spec conflicts were resolved by the engineer at generation time — they should not appear here.

If you encounter a residual ambiguity (e.g., a checklist pattern that doesn't clearly apply, or an edge case not covered explicitly), use this order to resolve it without stopping:

1. **Constraints & Decisions** (this IB) — the single authoritative implementation source; ADR decisions and spec contracts are already reconciled here
2. **Domain Constraints table** (this IB) — for edge cases involving specific hardware, dtype, or path constraints not explicitly in C&D
3. **Quality Checklists** — default patterns; yield to any explicit constraint above

Do NOT implement from Spec Context — it is traceability only. Do NOT load or re-read ADRs, interface contracts, or probe files.

If the conflict cannot be resolved by this order, or if two entries in Constraints & Decisions contradict each other, stop and ask the engineer. That conflict should have been caught at generation time and was not.

## Goal

[One sentence: what this IB accomplishes when complete — state the final observable system state, not the task.]

## Out of Scope

[Explicit list of what this IB does NOT do. Prevents scope creep. Every boundary that a reasonable engineer might assume is included must appear here if it is not.]

- [What this IB does not do — and why it belongs to a different IB or is out of scope entirely]

## Escalation Protocol

Stop immediately and ask the engineer when:
- Any implementation decision requires information not present in this IB
- A file not listed in Files to Modify needs to change to make this work
- A Done When criterion cannot be satisfied without touching something out of scope
- The behavior implied by Constraints & Decisions contradicts what the code currently does in a way not described here
- An ADR conflict or ambiguity is encountered that the Precedence section does not resolve

Do NOT make a reasonable-sounding assumption and proceed. Stop.

## Spec Context

[Verbatim copy of the Working Spec sections that apply specifically to this IB's scope. Exclude sections that belong to other IBs. Do NOT summarize what is included.]

**CODING AGENT: Do not implement from this section. It is preserved for traceability only. All implementation rules are in Constraints & Decisions below.**

## Files to Modify

| File | Change |
|------|--------|
| `path/to/file.py` | [what changes] |

## Reuse Inventory

Existing capabilities this work MUST reuse — do not reimplement. The Specifier
names each capability the implementer is required to call instead of rebuilding.
This is the upstream (declaration) half of the Reuse Firewall: the durable,
compiled reuse-intent contract that travels with the brief. The live "what code
exists" truth and the active gate live downstream at build time (capability
index + Code Reviewer calibrated gate) — not here, because code is not in DekSpec.

Required on code-bearing IBs (any brief with real entries in Files to Modify).
For a brief that genuinely introduces net-new capability with nothing to reuse,
say so explicitly with a single row: `| none | — | net-new capability |`.

| Capability | Location | Use instead of reimplementing |
|------------|----------|-------------------------------|
| [existing function/module/service to reuse] | `path/or/module.py` | [what the implementer must NOT rebuild] |

## Domain Constraints

| Constraint | Value |
|------------|-------|
| CUDA device | [cuda:0 / cuda:1-7 / cpu / n/a] |
| Tensor dtype in | [bfloat16 / float32 / n/a] |
| Tensor dtype out | [bfloat16 / float32 / n/a] |
| Read path | [shadow / neo4j / n/a] |
| Write path | [shadow+buffered / neo4j_direct / n/a] |
| Precision threshold | [max error specification / n/a] |

## Do Not Touch

| Function/File | Reason |
|---------------|--------|
| | |

## Governing ADRs

[For traceability only. Do NOT read or load these files during implementation — their decisions are already fully incorporated into Constraints & Decisions below.]

| ADR | Title |
|-----|-------|
| ADR-NNN | [title] |

## Constraints & Decisions

Single authoritative source for all implementation rules governing this IB. Reconciled from Spec Context and all governing ADRs — conflicts were resolved by the engineer at generation time. Implement from this section only. Do not derive rules from Spec Context, ADRs, Interface Contracts, or Probe Results directly.

Each entry uses this format:
- **[topic]:** [what to do — concrete, not a reference to a document]

Examples of correct entries:
- **Tensor dtype:** All tensors entering this component must be bfloat16. Upcast to float32 only at the HTTP boundary before JSON serialization.
- **Write path:** All writes go to shadow cache first. Never write directly to Neo4j from this component.
- **Interface contract constraint:** The `/embed` endpoint must return shape `[1, 2048]` float32. Callers must not pass batch size > 1.
- **Probe finding:** Round-trip precision loss through JSON serialization is 1.2e-4 at bfloat16 — within the 1e-3 acceptable threshold. No binary format required.

[Replace this block with actual entries for this IB.]

## Interface Contracts

[Traceability only. Do NOT read these files during implementation — the constraints they impose are already embedded in Constraints & Decisions above.]

- `dekspec/interface-contracts/IC-NNN-[slug].md` or none

## Probe Results

[Traceability only. Do NOT read these files during implementation — the findings that govern this IB are already embedded in Constraints & Decisions above.]

- `dekspec/probes/[name].py` — [one-line summary of the finding that informed this IB]

## Quality Checklists

[Reference checklists the coding agent should review during the session.]

- `dekspec/templates/checklists/python-quality-checklist.md` — if Python code
- `dekspec/templates/checklists/security-checklist.md` — if touching user input, graph writes, or tenant boundaries
- `dekspec/templates/checklists/eval-quality-checklist.md` — if bead produces model output

## Test Promotion Criteria

[List which Working Spec business rules and Interface Contract constraints this IB's tests should reference in their docstrings for promotion candidacy. This enables automated test promotion after bead closure.]

Promotion refs: [WS-NNN Rule N, IC-NNN Constraint N, ...]

## Done When

Each criterion must state what is verified and how. Format: `[criterion] — verified by [unit test | integration test | manual check | eval]`

- [ ] [Specific observable outcome] — verified by [how]
- [ ] [Specific observable outcome] — verified by [how]

**Golden I/O** *(required for numerical/data-transformation IBs — tensor operations, serialization, scoring, data transformation. For non-numerical IBs, use Golden State Transitions or delete this block.)*

| Input | Expected Output | Verified by |
|-------|----------------|-------------|
| [concrete input with exact values] | [concrete output with exact values] | unit test |
| [concrete input with exact values] | [concrete output with exact values] | unit test |

- [ ] All new tests written for this IB pass — verified by unit/integration test run
- [ ] All pre-existing tests continue to pass — verified by full test suite run
- [ ] [Eval criterion: eval name passes at ≥ N% on dataset D] — verified by eval run (if applicable)

## Open Issues

[Issues, questions, contradictions, and concerns. Logged during decomposition, audits, reviews, resyncs, or cascades from other artifacts. Resolve via `/write-ibs --review`.]

- [ ] [Issue description] — **Source:** [initial draft / audit / review / resync / cascade from \<artifact\>] — **Severity:** [`P0` / `P1` / `P2` / `P3`]

**Severity key:** `P0` = production-incident / cost-runaway reserve. `P1` = critical / blocking — prevents engineer approval. `P2` = important / approval-blocking — issues prevent IB acceptance but not authoring. `P3` = advisory / tracked-only — does not gate progress. Historical aliases (parser accepts indefinitely per ADR-013): `blocking` → `P1`; `non_blocking` → `P3`; `critical` → `P1`; `important` / `warning` → `P2`; `minor` / `info` → `P3`. See `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder + alias map.
