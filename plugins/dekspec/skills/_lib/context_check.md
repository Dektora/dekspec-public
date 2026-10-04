# DekSpec Context Check — Canonical Pattern

**Status:** AUTHORITATIVE. **Audience:** authoring skill orchestrators.

Determine the mode before applying this check. The skill's `substantive_modes`
and `inline_modes` manifest is authoritative; do not guess from a mode's name.

## Fresh-context fan-out

For a mode in `substantive_modes`, skip the parent-history check entirely.
Do not ask the engineer to `/clear`, request a history-based go-ahead, or mark
the resulting artifact as produced under known-contaminated context. The worker
reads a fresh bundle governed by [`fan_out.md`](fan_out.md): source paths,
verbatim engineer guidance, separately labeled orchestrator notes and recorded
manifest provenance. Existing lifecycle authorization still applies.

## Inline reasoning

For a mode in `inline_modes` that performs substantive reasoning in the parent
session (review, audit, interactive walkthrough, or a lifecycle decision), retain
the context check. Mechanical help/status queries do not need it.

- First user message with no prior conversation: proceed silently.
- Prior history: explain the artifact-specific risk, recommend `/clear` or a
  new session, and ask: “This session has prior context that may affect
  {artifact-kind} quality. Continue anyway? (y/n)” Wait for the response.
- If the engineer declines, stop that inline operation. If they proceed, record
  the context limitation in that operation's audit output. Do not attach it to
  separately drafted fan-out artifacts.

A prior explicit instruction to continue in the current session already answers
this context question. It does not replace a separately required lifecycle
approval. Preserve per-skill risk explanations; this substrate owns the common
mode-dependent behavior.

## Skill-side preamble

```markdown
> **CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
> {artifact-specific risk explanation}
> Inline reasoning only: first message → proceed; prior history → context check.
> Substantive fan-out modes skip this check and use the manifest hygiene rules.
```
