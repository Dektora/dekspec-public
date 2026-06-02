# review_lens_registry

> Schema each per-skill lens pack extends. REVIEW_IB (INT-106 `plugins/dekspec/skills/review-ib/lenses.md`) and REVIEW_PR (INT-107 `plugins/dekspec/skills/review-pr/lenses.md`) both register their lens packs against this schema. The shared `review-orchestration.md` shell loads packs by parsing markdown lens entries against the four required fields below.

## Required fields

Every lens entry MUST declare all four fields. A lens missing any field causes the orchestrator to raise at lens-pack load time — no consumer skill can run a malformed pack. Per ADR-026's load-bearing properties.

| Field | Purpose | Shape |
|---|---|---|
| `question` | The single question this lens asks the IB / PR surface under review. One sentence, falsifiable. Drives the specialist's system prompt. | string |
| `input_slice` | Selector identifying the input projection the orchestrator feeds this lens's specialist. Either a path-glob into the per-stage input bundle (e.g. `ib.body`, `parent_ws.acceptance`, `ae_paths.*.bounded_context`) OR `audit_doctor.<json-path>` to consume a slice of the cached `dekspec audit doctor --json` snapshot. NEVER full-repo context. | string |
| `attack_patterns` | List of specific failure-class checks the specialist loads into its system prompt. The specialist's job is to FIND a failure matching one of these patterns, not to give a friendly review. Pattern-armed attack per ADR-026. | list of strings |
| `severity_rubric` | The 0-100 confidence-band rubric used by the per-issue scorer. Most lenses inherit the shared `review_confidence_rubric.md`; a lens may override per-band thresholds if its question shape justifies it (e.g. an audit-rule preflight lens may have stricter critical-tier semantics). MUST include an explicit abstention band so calibrated `INSUFFICIENT_EVIDENCE` is reachable. | reference or inline yaml |

## Optional fields

| Field | Purpose |
|---|---|
| `surface_threshold` | Override the default 80 surface threshold for this lens. Use sparingly — the default is load-bearing for the rubric calibration corpus. |
| `silver_threshold` / `gold_threshold` | Operator-committed MIXED/AUTO advancement thresholds. Today these are written by the calibration script (INT-117) into `.dekspec/review-thresholds.yaml`; declaring them inline in the lens pack is allowed but the YAML wins on conflict. |
| `requires_audit_doctor` | Boolean. When true, the orchestrator skips this lens if the audit-doctor cache failed to load. Default false. |
| `tdd_discipline_lens` | Boolean. Marks the lens added by INT-120 that checks "did the outcome test land first (red)?" against git-blame. Default false. |

## Lens-pack format

A lens pack is a markdown file (e.g. `plugins/dekspec/skills/review-ib/lenses.md`) containing one entry per lens in a fenced YAML block:

```yaml
- id: scope-creep
  question: |
    Does `IB.files_to_modify` include paths outside the union of
    `Intent.components_affected` globs?
  input_slice: ib.files_to_modify + parent_intent.components_affected
  attack_patterns:
    - file path matches none of the parent Intent's component globs
    - file path is in a sibling Intent's components but no dependency edge exists
    - file is a generated artifact (under .pyc / __pycache__ / etc.) that should not be hand-edited
  severity_rubric: shared
```

A pack may declare 1..N lenses. REVIEW_IB ships 13 lenses; REVIEW_PR ships 9 (per `reference_review_pipeline_design.md` §"Lens design").

## Loader contract

The orchestration shell (`review-orchestration.md`) loads packs through:

```python
from dekspec.review.orchestration import load_lens_pack

pack = load_lens_pack("plugins/dekspec/skills/review-ib/lenses.md")
# pack is a list[Lens]; each Lens has the four required fields populated.
```

The loader:
1. Parses the markdown for fenced YAML blocks tagged as lens entries.
2. Validates each entry against the required-fields schema (raises on miss).
3. Resolves `severity_rubric: shared` references to the canonical `review_confidence_rubric.md`.
4. Returns the pack.

## Anti-patterns the schema rejects

- **Whole-repo input slice.** A lens declaring `input_slice: .` (or any unbounded selector) is rejected at load. Lenses see slices, not the full repo.
- **Open-ended question.** A lens question that does not admit a yes-no specialist verdict is rejected. "Is this PR good?" — rejected. "Does the diff modify any file outside `IB.files_to_modify`?" — accepted.
- **Empty attack_patterns.** A lens that supplies no attack patterns is a "soft review" lens — rejected. Lenses attack, not grade.
- **Severity rubric without abstention band.** A lens whose rubric cannot return abstention breaks the calibrated-abstention contract — rejected.
- **Re-deriving an audit rule from raw source.** A lens that walks the source tree to compute what the audit engine already exposes via `audit_doctor.<path>` — rejected (it must consume the cached snapshot instead).

## Intent-spec-packet input slice (no-IB review — INT-132)

REVIEW_IB normally projects an **IB-keyed** bundle (`ib.body`, `ib.files_to_modify`, …). But the direct-bead decompose shortcut (WS-fan-in = 0 IUs) produces no IB, so an IB-keyed bundle cannot be assembled and the pre-implementation review would never run. For that case the orchestrator projects the **`intent_spec_packet`** bundle instead — the Intent-level analogue of the IB packet — and runs the **same REVIEW_IB lens pack** against it (each lens's `input_slice` selector resolves against the Intent-keyed bundle below; a lens whose slice has no analogue here abstains rather than fires). The scoring engine, asymmetric single-lens veto, blind aggregator, and calibrated abstention are reused unchanged — no second engine.

`intent_spec_packet` bundle keys (the no-IB projection):

| Key | Source |
| --- | --- |
| `intent.body` | the Intent's Motivation + Desired Outcome + Components affected |
| `parent_ws.acceptance` | acceptance criteria of any parent Working Spec (empty for WS-fan-in=0) |
| `source_ae.*.bounded_context` | the Intent's Linked Architecture Elements |
| `glossary` | `dekspec/domain-glossary.md` |
| `bead_decomposition` | the direct-bead set the decompose step emitted (titles + acceptance) |

The bundle is still a **slice projection**, never full-repo context (the anti-patterns above still apply). The consumer is `/dekspec:spec-intent`'s no-IB review gate.

## Cross-references

- ADR-026 (load-bearing decision).
- `review-orchestration.md` (the shell that consumes packs registered against this schema).
- INT-132 (`intent_spec_packet` slice for the no-IB review gate).
- `review_confidence_rubric.md` (the canonical `severity_rubric: shared` target).
- INT-106 / INT-107 (the two consumer skills that ship lens packs).
