# System Vision: [System Name]

[One-paragraph elevator pitch. What this system does, who it serves, what it changes. 2-4 sentences. This paragraph is the preamble — text between the H1 and the first H2 — and is extracted into `preamble` in the IR.]

## Status

DRAFT

*Valid statuses:* `TODO` → `DRAFT` → `PROPOSED` → `ACCEPTED` → `LOCKED` | any stage → `DEPRECATED`

- **TODO** — placeholder; needs review and rewrite against current system state
- **DRAFT** — being written; anything goes
- **PROPOSED** — complete draft ready for review; engineer has not yet accepted
- **ACCEPTED** — engineer approved; downstream artifacts (AEs / ADRs / WSs) may rely on it; substantive changes allowed but must cascade
- **LOCKED** — frozen; editorial amendments only; unlock back to PROPOSED for substantive changes
- **DEPRECATED** — terminal; retired only when the system itself is retired or superseded

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

## What This Is

[1-2 paragraphs: the concrete shape of the system. What it produces, what it consumes, what the user-observable surface looks like. Reads as "this is a <noun> that <verbs>" — not "this might be" or "this aims to". State the system's current identity, not its aspiration.]

## Who This Is For

[The end users / customers / operators the system serves. Specific roles, not abstract categories. If the system serves both humans and other systems, name both.]

## Why This Exists

[The reason this system was built rather than not built. The problem that justified its existence. Not "why it's useful" — why it exists. If a competing way to solve the same problem was rejected, name the rejected alternative. This section is the load-bearing rationale; a System Vision without a `Why This Exists` body is incomplete by schema and audit convention.]

## Operating Principles

<!--
  Recommended section (not schema-required). One-to-three short
  principles framing HOW this system operates — the design posture
  contributors + AI agents apply at session-load time. The System
  Vision parser ignores this section (it's not part of the IR); the
  principles surface to readers and to the AGENTS.md aggregator, not
  to schema enforcement.

  Each principle is one sentence or one phrase + a brief unpacking.
  The Constitution's §Operating Principle is typically a single mantra
  derived from this section.

  Exemplar (Dektora/dekfactory):
    - **Human in forging, dark on derived.** Forging — creation,
      design, novel architectural choices, spec authoring — requires
      human attention. Derived — mechanical, regenerable outputs (code
      from spec, tests from acceptance, docs from artifacts) — is safe
      for autonomous AI execution. The system's whole shape follows
      from this division.

  See `docs/dekspec-methodology.md` §"Operating Principles" for the
  design heuristic table that maps each principle to its enforcement
  surfaces (skills, audits, hooks).
-->

- **[Principle 1 — short title]** [One-to-two-sentence unpacking. What does this principle mean for daily work? Where does it bite?]
- **[Principle 2 — short title]** [Unpacking.]

## What Success Looks Like

[Concrete observable outcomes. Not metrics — observable states. Each bullet is a sentence the engineer can point at the running system and say "yes" or "no" to without ambiguity.]

- [Observable 1]
- [Observable 2]
- [Observable 3]

## What We Are Not Building

[Explicit exclusions. This section prevents scope creep at the highest level of the system. Each bullet pairs an exclusion with the *why* — without the rationale the exclusion will rot when context fades.]

- [Exclusion 1 — why]
- [Exclusion 2 — why]
- [Exclusion 3 — why]

## Amendment Log

*Add an entry for every change made after LOCKED status, or when unlocking back to PROPOSED. If an amendment note carries a severity tag (e.g., a cascade trigger surfaced via critic-pass), use the canonical `P0` / `P1` / `P2` / `P3` ladder per ADR-013 (historical aliases `blocking` → `P1`, `non_blocking` → `P3`, `critical` → `P1`, `important` / `warning` → `P2`, `minor` / `info` → `P3` remain accepted indefinitely — see `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder and alias map).*

| Date | Type | Change | Author |
|------|------|--------|--------|
| YYYY-MM-DD | Editorial / Unlock / Substantive | [what changed and why] | [name or agent] |
