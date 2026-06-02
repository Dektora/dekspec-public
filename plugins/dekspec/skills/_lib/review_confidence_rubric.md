# review_confidence_rubric

> Shared 0-100 per-issue confidence rubric used by every lens specialist in the math-olympiad review pipeline (REVIEW_IB, INT-106; REVIEW_PR, INT-107). Per **ADR-026** (LOCKED 2026-05-29). Adapted from the `code-review` plugin's per-issue Haiku scorer with the 80-threshold filter; extended with a calibrated-abstention band so `INSUFFICIENT_EVIDENCE` is reachable per ADR-026.

This rubric is the canonical `severity_rubric: shared` target in `review_lens_registry.md`. Lens packs may override per-band thresholds if a lens question's shape justifies it, but the band names and the 80 surface threshold are load-bearing — they MUST NOT be redefined.

## The 0-100 ladder

| Range | Band | Surface? | Meaning |
|---|---|---|---|
| 0-25 | **false-positive** | NO | Specialist saw the pattern but reading the surface again it does not apply. Drops from the verdict; logged to the flywheel as a calibration sample. |
| 26-50 | **nitpick** | NO | Real finding but operationally irrelevant — formatting, stylistic preference, would-be-nice. Drops from the verdict; logged. |
| 51-75 | **low-impact** | NO | Real finding worth noting but not load-bearing — it won't break shipping. Drops from the verdict; logged. |
| 76-90 | **important** | YES | Real finding the operator must see — it could plausibly block downstream work or harm correctness. **Surfaces.** |
| 91-100 | **critical** | YES | Real finding that **vetoes** the verdict. The lens registers a single-lens NO-GO per ADR-026's asymmetric-voting contract regardless of other lenses' scores. **Surfaces.** |

The **surface threshold is 80** (i.e., bands `important` 76-90 and `critical` 91-100 both surface; the conservative "76-79" sub-band in `important` only surfaces in MIXED/AUTO modes once the operator has committed a per-lens silver threshold below 80). The flywheel (INT-117 calibration math) eventually proposes per-lens silver/gold thresholds that may differ from 80, but until those land in `.dekspec/review-thresholds.yaml` the global 80 is authoritative.

## The abstention band

| Marker | Band | Surfaces? | Meaning |
|---|---|---|---|
| `INSUFFICIENT_EVIDENCE` | **abstention** | YES (as `INSUFFICIENT_EVIDENCE` verdict, not as a finding) | The specialist read the input slice and cannot confidently emit any score on this lens. The aggregator counts the abstention; if the overall verdict has no `surface` findings AND at least one lens abstained, the verdict is `INSUFFICIENT_EVIDENCE` (not `GO`). |

The abstention band is **load-bearing** for the AUTO graduation path: a system that always emits a confident verdict cannot safely auto-merge on a confidence threshold (it would degenerate to a coin flip on edge cases). Specialists are explicitly instructed via the system prompt that abstaining is a valid output.

## Per-issue specialist instructions

The orchestration shell injects the following into every lens-specialist's system prompt:

```
You will be shown a single input slice and asked one specific question
(the lens's `question` field). Score your finding on the 0-100 ladder
defined in dekspec/plugins/dekspec/skills/_lib/review_confidence_rubric.md:

  0-25   false-positive — the pattern looked like the question's failure
         class but on re-reading it does not apply.
  26-50  nitpick — real finding but not operationally meaningful.
  51-75  low-impact — real finding worth noting but won't block shipping.
  76-90  important — real finding the operator must see.
  91-100 critical — real finding that vetoes the verdict.

If the input slice is too thin to confidently emit any score on the
question, return INSUFFICIENT_EVIDENCE rather than guess. The
aggregator handles abstention; you do not have to.

Surface only your single best finding. The orchestrator does not want
your top-10 list. One question → one verdict.
```

## Cross-references

- ADR-026 (load-bearing decision).
- `review-orchestration.md` (the shell that injects this rubric into specialist prompts).
- `review_lens_registry.md` (the schema that references this as `severity_rubric: shared`).
- INT-117 (calibration math that proposes per-lens silver/gold thresholds that may move below 80 once a corpus accumulates).
