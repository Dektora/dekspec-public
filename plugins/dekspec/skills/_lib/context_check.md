# DekSpec Context-Check Preamble — Canonical Pattern

**Status:** AUTHORITATIVE.
**Audience:** DekSpec skill authors. Every skill whose output quality is sensitive to prior-conversation contamination cites this file and inlines the canonical 3-line context-check block below.
**Sibling substrate:** `_lib/mode_dispatcher.md` (canonical mode dispatch). The two substrates compose — a skill MAY use both, and they appear in this order: front-matter, citations, **context-check preamble**, **mode-dispatcher citation**, mode-detection prose, mode sections.

---

## Why this file exists

Before this substrate landed, fourteen DekSpec authoring/archaeology skills each carried their own seven-line `> **⛔ CONTEXT CHECK**` blockquote. The skill-specific *risk paragraph* (one or two sentences naming *why this particular artifact degrades under prior context*) varied meaningfully across skills — Security Profile's "before `bounded_context` settles" is genuinely different from ADR's "introducing bias and competing patterns." But the surrounding scaffolding — the emoji header, the "first message → proceed" line, and the "prior history → ask y/n + wait" line — was duplicated near-verbatim fourteen times. Three concrete consequences:

1. **Wording drift.** Minor phrasings ("Recommend `/clear` or a new session" vs. "Recommend `/clear`") drifted across skills and across releases, with no canonical source to reconcile against.
2. **Onboarding cost for new skills.** A new authoring skill had to re-derive (or copy-and-tweak) seven lines of preamble before the load-bearing one-sentence risk paragraph.
3. **No single place to evolve the contract.** When the y/n question phrasing needed to change (e.g., switching from "Continue anyway?" to "Continue? (y/n)"), the change had to be made in fourteen places — and inevitably wasn't.

This file is the source of truth for the *scaffolding*. The per-skill *risk paragraph* stays per-skill because it is load-bearing.

## The first-vs-prior behavior contract

Every skill that cites this substrate MUST honor the same two-branch behavior, regardless of how it phrases the per-skill risk paragraph:

| Session state at skill invocation | Required behavior |
|---|---|
| **First user message in the session** (no prior turns, clean context) | Proceed silently. Do not ask. Do not delay. |
| **Prior conversation history exists** (any prior user or assistant turn) | Surface a one-line warning naming the artifact kind, recommend `/clear`, ask `(y/n)`, and **wait for the engineer's response** before proceeding. |

The "first vs. prior" decision is made by the model from the visible transcript; there is no machine signal to consult. Be lenient: if there is *any* prior content beyond the system prompt and the current user message, treat it as "prior history exists."

The y/n trailer wording follows this template, with `{artifact-kind}` substituted per skill (e.g., `Constitution`, `Intent`, `bead decomposition`, `eval`, `SP`, `test derivation`):

> "This session has prior context that may affect **{artifact-kind} quality**. Recommend `/clear` or a new session. Continue anyway? (y/n)"

The skill must **wait for the engineer's response** before proceeding. If the engineer answers `n`, stop. If `y`, proceed but note in any subsequent audit / open-issues output that the artifact was produced under known-contaminated context.

## Recommended skill-side block template

Inline this in each SKILL.md immediately under the one-line description, replacing the legacy seven-line preamble:

```markdown
> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> {degradation_reason}
>
> First message → proceed. Prior history → ask "context may affect {artifact-kind} quality, recommend /clear, continue? (y/n)" + wait.
```

Where:

- `{degradation_reason}` — a one- to two-sentence skill-specific paragraph naming *why this artifact is sensitive to prior-context contamination*. This is the **load-bearing** part. Examples:
  - ADR: "This skill requires precise architectural reasoning. Prior conversation context can degrade quality by introducing bias and competing patterns."
  - Security Profile: "A Security Profile is a load-bearing declaration of what the project permits at the security layer. Prior conversation context can degrade rigor by anchoring on partial sketches before the engineer has settled the `bounded_context` or the `allowed_dataflows` shape."
  - Create-beads: "This skill decomposes an IB into self-contained bead work units. Prior conversation context can leak assumptions into bead constraints that aren't in the IB."
- `{artifact-kind}` — the noun phrase that names what the skill produces (`ADR`, `Constitution`, `Intent`, `bead decomposition`, `eval`, `SP`, `test derivation`, etc.). Used inside the y/n trailer.

Three lines of canonical preamble + one skill-specific paragraph replaces seven lines of duplicated scaffolding.

## Per-skill migration checklist

When refactoring an existing skill to this substrate, or adding a new skill that needs context-check semantics:

- [ ] Replace the legacy `> **⛔ CONTEXT CHECK**` block (typically lines 12–18) with the recommended template above.
- [ ] Preserve the existing skill-specific risk paragraph **verbatim or lightly trimmed to one or two sentences** — do not homogenize across skills. The per-skill framing is the load-bearing part.
- [ ] Substitute the correct `{artifact-kind}` noun in the y/n trailer (match what the skill emits — e.g., the skill that writes Constitutions uses `Constitution`; the skill that decomposes IBs into beads uses `bead decomposition`).
- [ ] Keep the substrate citation link relative-and-correct: `[\`_lib/context_check.md\`](../_lib/context_check.md)`.
- [ ] Leave the `**Mode dispatcher pattern:** see ...` citation immediately below (if present) untouched — the two substrates compose.

## Reconsideration triggers

This substrate's contract should be revisited if:

- A skill emerges whose context-sensitivity is fundamentally different (e.g., needs a three-way branch instead of first-vs-prior). Document the new shape here before forking the contract.
- The y/n trailer wording proves consistently mis-parsed by engineers (sign that "continue anyway?" reads as encouragement instead of a guard). Reword here once; the change propagates by re-running the migration.
- The substrate cite line itself becomes prose-noise in practice (sign that the substrate is over-fitting). Consider collapsing back to inline preambles only if duplication cost is genuinely lower than indirection cost.
