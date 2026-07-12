# DekSpec Validate-and-Surface — Canonical Substrate

**Status:** AUTHORITATIVE (per ds-di2 architectural directive 2026-05-19).
**Audience:** DekSpec skill authors. Every fan-out skill that ends in a `dekspec validate` gate cites this file from its Step 3 prose. Skills that run inline validation (no fan-out) may also cite it to inherit the same non-retry contract.
**Lineage:** Pattern derived from the original `ds-di2` Open-Issue rationale #2 — "if a subagent cannot produce a clean artifact given the bundled context, that is an explicit signal that the input materials were insufficient." Lifted out of the per-skill Step 3 prose into a single substrate during the Dim 3 skills-audit refactor (cluster 7).

---

## Why this file exists

Before this substrate landed, every fan-out skill repeated the same three-sentence validate-and-surface paragraph in its `## Fan-Out Mode` § Step 3. Three concrete consequences:

1. **Phrasing drift.** Some skills said "do not silently retry," others "do not retry blindly," others "do not patch the artifact in the parent context." All meant the same thing — but a reader scanning two skills side-by-side could not tell whether the difference was load-bearing or accidental.
2. **Rationale was buried.** The *why* (a failed subagent return is a signal about input quality, not a transient error to be papered over) lived in the Open-Issue prose for `ds-di2` and in some skills' "Subagent failure handling" tail paragraphs — but not consistently in Step 3 where the validate call actually fires.
3. **Skills outside the fan-out family (e.g., inline-validation skills, audit gates inside `--accept`) had no canonical contract to point at.** They reinvented the wording each time.

This file is the source of truth for that contract. Each fan-out skill's Step 3 cites it; the citation block below is what skill authors paste in.

---

## The validate-and-surface contract

When a substantive-work mode (fan-out or inline) produces or mutates a DekSpec artifact, the orchestrator MUST:

### 1. Run `dekspec validate <path>` from the parent session

- **Always** — even when the subagent self-reports a clean validate. The subagent's claim is suggestive; the parent's independent `dekspec validate` call is authoritative. (Trust-but-verify: a confused subagent can return `validation: clean` from inside its own buggy run.)
- Use the typed form when known: `dekspec validate --kind <ir_kind> <path>` (e.g., `--kind intent`, `--kind security-profile`). Untyped `dekspec validate <path>` falls through to the dispatcher, which is fine but slower and less specific on errors.
- Validation is a **post-write** check. The subagent has already written the file via its own `Write` tool by the time the parent runs validate.

### 2. On non-zero exit: surface verbatim, do not retry

If `dekspec validate` returns non-zero (or the artifact fails an equivalent post-write gate — see *Equivalent gates* below):

- Surface the validator's exact stderr/stdout to the engineer. Do not paraphrase, do not summarize, do not truncate.
- Surface the subagent's own findings alongside (the subagent's one-paragraph return + any blocking findings it reported).
- **Stop.** Do not silently re-dispatch the subagent with the same bundle. Do not patch the artifact in the parent context to make it validate. Do not loosen the validator to make it pass.
- The fix is to **expand the bundle in the orchestrator** (or fix the upstream artifact the bundle was derived from), then re-dispatch. The engineer makes that call, not the skill.

### 3. The rationale (why this contract)

A subagent fails to produce a clean artifact for one of three reasons:

1. **The bundled context was missing material the subagent needed.** (Most common — e.g., a referenced AE wasn't included, a glossary term wasn't defined, a parent ADR was stale.)
2. **The upstream artifact the bundle was derived from has a real gap.** (E.g., a WS with acceptance criteria too vague to derive evals from; a bead's Files section ambiguous enough that the test author can't write deterministic assertions.)
3. **The subagent itself misread the template / requirements.** (Rare with a fresh-context subagent + a well-bundled prompt — but possible.)

In cases 1 and 2, **retrying with the same bundle will fail again** — the gap is in the input, not the run. Surfacing the gap to the engineer is the load-bearing behavior: it converts a silent failure into a signal about input material quality. The skill's value comes from *exposing* the gap, not from papering over it.

In case 3, the engineer's next-step decision (re-dispatch with a sharper prompt, or unblock by hand) is also better than a silent retry — because case 3 is indistinguishable from case 1 from inside the skill, and the engineer is the only party with full context.

This is the architectural directive `ds-di2` OI-2 in one sentence: **a subagent that can't produce a clean artifact exposes a gap in the bundled context; the fix is to expand the bundle, not to retry blindly.**

---

## Equivalent gates

Some artifact kinds have a post-write check that is the *de facto* equivalent of `dekspec validate`. These get the same surface-verbatim-don't-retry contract:

| Artifact kind | Equivalent gate | Skill |
|---|---|---|
| Test files | `pytest --collect-only <path>` | `write-tests` |
| All artifacts | `dekspec doctor --at .` (full fidelity audit; heavier than validate) | any skill that runs doctor as part of Step 3 |
| Audit findings JSON (audit subagent) | JSON parse + per-finding schema check | `/doctor` Stage 2 (inlined fidelity body) |
| Structural pre-save (System Vision) | parent-side H1/H2 shape check before saving | `write-sv` |

When the equivalent gate fires non-zero / fails parse / fails shape: same contract — surface verbatim, stop, do not silently retry.

---

## Recommended skill-side citation block

Paste this into your skill's `## Fan-Out Mode` § Step 3 (the validate step), parameterized for your artifact kind. It replaces the previous standalone validate-and-surface paragraph.

```
Validation contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md).
After the subagent returns, run `dekspec validate --kind <KIND> <output-path>`; on
non-zero exit, surface verbatim and stop — do not silently retry. <KIND>-specific
audit gate: this skill's §Audit Mode checklist (see below). <Any genuinely skill-
unique post-write checks listed here as additional items, NOT as replacements for
the validate gate>.
```

Where:

- `<KIND>` is the IR kind (`adr`, `architecture-element`, `working-spec`, `intent`, `mission`, `interface-contract`, `system-vision`, `security-profile`, `constitution`) — or omit `--kind` if your skill targets multiple kinds and the dispatcher will infer.
- The "skill-unique post-write checks" slot is for things like `pytest --collect-only` (write-tests), `dekspec doctor --at .` (write-ic), index-row insertion (write-mission), Amendment Log entry verification (write-sp, write-constitution). These are **additional** gates layered on top of the validate gate — they do not replace it.

The mode-specific post-checks list (Creation/Accept/Revise/etc. specifics) stays inline in Step 3 — only the standalone validate-and-surface paragraph is replaced by the citation.

---

## Per-skill migration checklist

When refactoring an existing fan-out skill to the substrate:

- [ ] Locate the validate paragraph in `## Fan-Out Mode` § Step 3. It typically begins with "Run `dekspec validate <output-path>`. Non-zero exit → surface the validation error verbatim..." and ends with "...gap in the bundled context."
- [ ] Replace that paragraph with the citation block above, parameterized for this skill's artifact kind.
- [ ] Preserve any skill-unique post-write gates as additional items (do NOT delete `pytest --collect-only`, `dekspec doctor --at .`, structural pre-save checks, JSON parse, etc.).
- [ ] Preserve the mode-specific post-checks list (Creation/Accept/Revise/etc.) — those are skill-specific contracts, not substrate.
- [ ] Preserve any "Subagent failure handling" tail paragraph — it is the case-1/case-2 elaboration that names the specific bundle items this skill ships (Step 1 list reference). The substrate covers the *contract*; the tail names the *bundle*.
- [ ] Run the test suite — must be green.

## Reconsideration triggers

This substrate's contract should be revisited if:

- A fan-out skill needs to **silently retry on non-zero validate** for a documented reason (e.g., a known transient validator bug). Add the exception to the contract here first, then introduce it in the skill — don't let exceptions accumulate skill-side.
- A new IR kind enters DekSpec (per ADR-011) with a post-write gate that doesn't fit `dekspec validate` (e.g., a generated-code artifact whose gate is `cargo check`). Add the gate to the *Equivalent gates* table above.
- The "fix is to expand the bundle, not retry" rationale stops matching observed failure patterns in practice (e.g., if engineers start seeing genuinely transient subagent failures that *do* benefit from a single retry). Document the new shape here and update the contract.

## Links

- `ds-di2` (the original architectural directive that introduced the fan-out + validate-and-surface contract; OI-2 carries the rationale).
- `_lib/mode_dispatcher.md` (sibling substrate — canonical multi-mode dispatcher pattern).
- `_lib/fan_out.md` (sibling substrate, cluster 6 of the Dim 3 refactor — canonical fan-out pattern. Its Step 3 § C ("handoff back to parent") cites this file for the validate gate.) — *Note: `fan_out.md` lands on `main` via the cluster 6 PR; the substrate-to-substrate cite is a one-line follow-up once both PRs merge.*
- AE-006 Skills Library (the AE this substrate lives within).
