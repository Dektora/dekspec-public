# review_confidence_rubric

> Shared 0-100 per-issue confidence rubric used by every lens specialist in the math-olympiad review (REVIEW_IB — the IB contract before `dekspec ib accept`; REVIEW_PR — the delivery at its head). Per **ADR-026**. Adapted from the `code-review` plugin's per-issue scorer with the 80-threshold filter, extended with an abstention band so `INSUFFICIENT_EVIDENCE` is reachable.

This rubric is the canonical `severity_rubric: shared` target in `review_lens_registry.md`. A lens may override per-band thresholds when its question justifies it, but the band names and the 80 surface threshold MUST NOT be redefined.

## The 0-100 ladder

| Range | Band | Surface? | Meaning |
|---|---|---|---|
| 0-25 | **false-positive** | NO | The pattern looked like the failure class, but on re-reading it does not apply. |
| 26-50 | **nitpick** | NO | Real but operationally irrelevant — formatting, style, would-be-nice. |
| 51-75 | **low-impact** | NO | Real and worth noting, but it won't block the work. |
| 76-90 | **important** | YES (≥80) | Real finding the engineer must see — it could plausibly block downstream work or harm correctness. |
| 91-100 | **critical** | YES | Real finding that **vetoes** the verdict: a single-lens NO-GO under ADR-026's asymmetric voting. |

The **surface threshold is 80**. Surfaced findings decide the verdict: at REVIEW_IB they become Open Issues (`critical` → P1, `important` → P2); at REVIEW_PR they fail the IB's verdict. Findings below 80 do not affect the verdict; a reviewer may list them in the narrative report.

## The abstention band

| Marker | Band | Surfaces? | Meaning |
|---|---|---|---|
| `INSUFFICIENT_EVIDENCE` | **abstention** | as the verdict, not as a finding | The specialist cannot confidently score its question from the slice. If no finding surfaces and at least one lens abstained, the verdict is `INSUFFICIENT_EVIDENCE`, not `GO`. |

Abstention is load-bearing: a reviewer that always emits a confident verdict degenerates to a coin flip on thin substrate. At REVIEW_PR an `INSUFFICIENT_EVIDENCE` records no passing verdict, so completion stays refused rather than guessed. Specialists are told that abstaining is a valid output.

## Per-issue specialist instructions

The orchestration shell injects the following into every lens specialist's prompt:

```prompt
You will be shown a single input slice and asked one specific question
(the lens's `question` field). Score your finding on the 0-100 ladder
defined in plugins/dekspec/skills/_lib/review_confidence_rubric.md:

  0-25   false-positive — the pattern looked like the question's failure
         class but on re-reading it does not apply.
  26-50  nitpick — real finding but not operationally meaningful.
  51-75  low-impact — real finding worth noting but won't block the work.
  76-90  important — real finding the engineer must see.
  91-100 critical — real finding that vetoes the verdict.

If the input slice is too thin to confidently emit any score on the
question, return INSUFFICIENT_EVIDENCE rather than guess. The
aggregator handles abstention; you do not have to.

Surface only your single best finding. One question → one verdict.
```

## Cross-references

- ADR-026 (review shape; revised by ADR-057).
- `review-orchestration.md` (injects this rubric), `review_lens_registry.md` (references it as `severity_rubric: shared`).
