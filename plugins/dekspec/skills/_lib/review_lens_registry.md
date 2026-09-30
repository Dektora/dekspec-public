# review_lens_registry

> Schema each per-skill lens pack extends. REVIEW_IB (`plugins/dekspec/skills/review-ib/lenses.md`, the pre-execution contract review) and REVIEW_PR (`plugins/dekspec/skills/review-pr/lenses.md`, the post-implementation delivery review) both register against it. The shared `review-orchestration.md` shell reads packs against the four required fields below.

## Required fields

Every lens entry MUST declare all four fields. A lens missing any field stops the review before fan-out — no skill runs a malformed pack (ADR-026).

| Field | Purpose | Shape |
|---|---|---|
| `question` | The single question this lens asks of the IB contract or the delivery. One question, falsifiable. Drives the specialist's prompt. | string |
| `input_slice` | Selector for the projection the specialist receives: a path into the per-stage input bundle (e.g. `ib.acceptance`, `ib.context`, `delivery.diff`, `record.deviations`) OR `audit_doctor.<json-path>` to consume a slice of the cached `dekspec doctor --json` snapshot. NEVER full-repo context. | string |
| `attack_patterns` | Specific failure classes the specialist hunts for. Its job is to FIND a failure matching one of them, not to grade (ADR-026 pattern-armed attack). | list of strings |
| `severity_rubric` | The 0-100 confidence rubric the specialist scores on. Normally `shared` (→ `review_confidence_rubric.md`); a lens may override band thresholds if its question justifies it. MUST keep an abstention band so `INSUFFICIENT_EVIDENCE` is reachable. | reference or inline yaml |

## Optional fields

| Field | Purpose |
|---|---|
| `surface_threshold` | Override the default 80 surface threshold for this lens. Use sparingly. |
| `requires_audit_doctor` | When true, the lens abstains if the audit-doctor cache failed to load. Default false. |
| `tdd_discipline_lens` | Marks a strong-TDD timing lens (`outcome-tdd-discipline` at REVIEW_IB, `outcome-tdd-history` at REVIEW_PR). Default false. |

## Lens-pack format

A lens pack is a markdown file with one fenced YAML block per lens:

```yaml
- id: scope-and-protected-surfaces
  question: |
    Is the allowed Scope coherent with the Outcome, and do the Protected
    Surfaces name what must not change?
  input_slice: ib.outcome + ib.scope + ib.protected_surfaces
  attack_patterns:
    - the Outcome cannot be achieved without changing a file outside Scope
    - a surface other code depends on lies inside Scope with no protection
  severity_rubric: shared
```

A pack may declare 1..N lenses. REVIEW_IB ships 16; REVIEW_PR ships 13.

## Loading

There is no Python loader. The consuming skill reads the pack itself before fan-out:

1. Collect every fenced YAML block whose entries carry an `id`.
2. Check each entry for the four required fields; stop the review on any miss.
3. Resolve `severity_rubric: shared` to `review_confidence_rubric.md`.
4. Hand each lens, with only its projected slice, to a fresh-context specialist composed with the consumer skill's Agent Role Specification (`agent_roles.md`) — a lens specializes that role.

## Anti-patterns the schema rejects

- **Whole-repo input slice.** `input_slice: .` or any unbounded selector. Lenses see slices.
- **Open-ended question.** "Is this delivery good?" — rejected. "Does any changed file fall outside the delivery's Scope?" — accepted.
- **Empty `attack_patterns`.** A lens that attacks nothing is a grading lens — rejected.
- **Rubric without abstention.** Breaks calibrated abstention — rejected.
- **Re-deriving what the engine or audit already computes.** A lens that re-walks the tree for audit findings, re-runs acceptance checks, or recomputes scope must read `audit_doctor.<path>` or the `evidence` slot instead.

## Retired

The `intent_spec_packet` slice (the no-IB review path for direct-bead decompositions, INT-132) is retired with code beads (ADR-056): every executed change is an IB, so every change is reviewed as an IB contract.

## Cross-references

- ADR-026 (review shape), ADR-056 (IB as the executable work contract), ADR-057 (evidence and verdicts in the execution record).
- `review-orchestration.md` (the shell), `review_confidence_rubric.md` (`severity_rubric: shared`).
- `review-ib/lenses.md`, `review-pr/lenses.md` (the two packs).
