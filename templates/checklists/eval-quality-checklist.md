# Eval Quality Checklist

Reference this from Implementation Briefs when the bead involves model output,
scoring functions, retrieval, or injection effectiveness.

---

## Layer-by-Layer — What to Measure

### Retrieval Correctness

- Is the right memory being retrieved for a given context?
- Recall@K — of K retrieved memories, what fraction are relevant?
- MRR (Mean Reciprocal Rank) — where does the first relevant memory appear?
- Embedding drift — cosine similarity between current and insert-time embeddings for same content
- Staleness rate — fraction of retrieved memories from a different model/pooling version

### Injection Effectiveness

- Behavioral probing — construct (with injection / without injection) prompt pairs for known facts. Does the response reflect injected content?
- Ablation eval — run full pipeline with injection disabled. If quality delta is near zero, injection is not contributing.
- Log injection vector magnitude and direction statistics per request
- Track correlation between injection magnitude and response relevance

### Awareness/Hierarchy Scoring

- Scoring calibration — do high-scored memories actually produce better responses?
- Score distribution stability — track mean, variance, percentiles across sessions. Sudden shifts = scoring drift.
- Rank correlation — Spearman correlation between awareness scores and human-labeled relevance
- Hierarchy consistency — parent scores monotonically relate to aggregated child scores

### End-to-End Quality

- Relevance — does the response address the user's actual need? (LLM-as-judge, NOT the same model under evaluation)
- Grounding — claims supported by memory are actually grounded in retrieved content
- Consistency — same question + same memories = consistent answer across sessions
- Hallucination rate — claims not supported by retrieved memories or conversation history

---

## Eval Design Rules

- Always define the null hypothesis before running an experiment
- Use paired evaluation — same queries, same session state, with and without the change
- Define minimum detectable effect size before the experiment, not after
- LLM judge variance is high — run comparisons multiple times, report confidence intervals
- Separate retrieval evals from end-to-end evals — catch regressions at the layer they occur

---

## Regression Patterns to Watch For

- Pooling strategy change silently shifts embedding space
- Scoring function refactor changes score scale without changing rank order (breaks calibration)
- Graph schema migration orphans embeddings without triggering re-embedding
- Context window change alters what memories are in the injection set
- Model version update shifts logit distributions, breaks behavioral probing evals

---

## Red Flags

- No retrieval eval exists — quality assessed only through end-to-end vibe checks
- Injection effectiveness has never been measured with ablation — assumed to work
- Awareness scores are not logged — no way to detect scoring drift
- Response quality assessed only by the same model being evaluated
- A/B experiments run without pre-defined success criteria
- Graph growth has no retrieval quality monitoring — degradation discovered by users, not metrics
