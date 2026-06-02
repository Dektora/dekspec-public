---
name: spec-intent
description: Specification phase-executor for an Intent (INT-NNN). Drives an Intent from DRAFT to ready-for-coding by sequencing the existing authoring skills — /write-intent --analyze / --accept / --decompose plus /write-ws, /write-ic, /write-ibs — and the architectural-interview prompts, leaving the Intent at IMPLEMENTING. Stops at the coding boundary; never dispatches a coding session. The specification-side sibling of /exec-coding-session.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] <INT-NNN | path/ID of Intent>
related_skills: [write-intent, write-ws, write-ibs, orchestrate-intent, exec-coding-session]
---

> **Vendored asset paths (INT-097):** Paths below like `dekspec/...` reference the consumer-vendored layout. Pip-only installs resolve via `dekspec resource ...`. See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md).

Specification phase-executor for an Intent. The specification-side counterpart to `/exec-coding-session` (construction) and `/dekspec:land-intent` (review+land): it drives an Intent through its specification lifecycle to the point of being ready for coding, from one launch, by sequencing the existing `write-*` authoring skills unchanged. It is a thin orchestrator — it reimplements none of the authoring logic — and it **stops at the coding boundary** (it never dispatches a coding session itself).

## Starter Prompt

```prompt
/dekspec:spec-intent INT-130

Take INT-130 from DRAFT to ready-for-coding: analyze it, pause for my accept,
then decompose and drive its child specs to ACCEPTED. Stop at IMPLEMENTING —
don't start coding.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Spec Mode**.

- **Help mode** — `--help` flag. See **Help Mode**.
- **Spec mode** — default (an `INT-NNN` / path positional). Proceed to **Spec Mode**.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:spec-intent"
one_line:   "Drive an Intent from DRAFT to ready-for-coding by sequencing the write-* skills."
modes:
  - { flag: "", args: "<INT-NNN>", description: "Spec mode — analyze → accept → decompose → drive child specs; stop at the coding boundary." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:spec-intent INT-130"
  - "/dekspec:spec-intent --help"
```

## Spec Mode

Identify the target Intent `INT-NNN`, then sequence the existing authoring skills (this skill dispatches them; it does not reimplement them):

### Phase 1 — Analyze

Run `/write-intent --analyze <intent>` — top-down coverage + bottom-up archaeology + size assessment. DRAFT → PROPOSED when clean, or surface OVERSIZED (enter the split flow) when a cap is exceeded.

### Phase 2 — Accept (engineer-gated)

Present the analyzed Intent and run `/write-intent --accept <intent>` only on the engineer's approval. This transition stays **engineer-gated** — `spec-intent` never auto-accepts. PROPOSED → ACCEPTED.

### Phase 3 — Decompose & drive child specs

Run `/write-intent --decompose <intent>` to scaffold the downstream artifacts, then drive each scaffolded child spec through its own quality gate to `ACCEPTED`/`LOCKED` by dispatching the matching authoring skill — `/write-ws`, `/write-ic`, `/write-ibs` (and `/write-ae` / `/write-adr` if the decomposition surfaced new architecture). Host the architectural-interview prompts here. Do not proceed with raw DRAFT/PROPOSED child specs in the tree.

### Phase 3b — No-IB review gate (INT-132)

If `--decompose` took the **direct-bead shortcut** (WS-fan-in = 0 IUs → no Implementation Brief), the IB-keyed `REVIEW_IB` pre-implementation review can never fire (there is no IB to enter the `REVIEW_IB` state). To keep the spec materials from reaching coding unreviewed, run the **no-IB review gate** synchronously here, **before** the Intent advances `ACCEPTED → IMPLEMENTING`:

1. Assemble the **`intent_spec_packet`** bundle (Intent body + parent WS acceptance + source-AE bounded contexts + glossary + the direct-bead decomposition) — see [`_lib/review_lens_registry.md`](../_lib/review_lens_registry.md) §Intent-spec-packet input slice.
2. Run it through the shared **orchestration shell** ([`_lib/review-orchestration.md`](../_lib/review-orchestration.md), the INT-105 math-olympiad engine) with the **REVIEW_IB lens pack** (`review-ib/lenses.md`) projected against the Intent-level slice. The scoring engine — context-isolated lens specialists, blind aggregator, single-lens ≥80 veto, calibrated abstention — is reused unchanged; this gate adds no new engine.
3. Act on the verdict (**RECOMMEND-only at landing, ADR-026** — the operator advances):
   - **GO** → proceed to Phase 4; the Intent advances to `IMPLEMENTING`.
   - **NO-GO** → **holds the Intent at ACCEPTED** (does not advance to IMPLEMENTING); record the vetoing lenses + the sidecar verdict and hand back for revision.
   - **INSUFFICIENT_EVIDENCE** → surface + let the operator decide.

IB-bearing Intents skip this gate — their review already fires via `/write-ibs --accept` → `REVIEW_IB` (INT-122) + the INT-108 handler. This gate is the no-IB analogue only.

### Phase 4 — Stop at the coding boundary

When the parent Intent reaches `IMPLEMENTING` with its child specs at `ACCEPTED`/`LOCKED`, the specification phase is complete. **This skill stops at the coding boundary: it does not dispatch a coding session** — `/exec-coding-session <intent>` is the next, separate phase-executor (and `/dekspec:land-intent` the one after). Report the ready-for-coding state and name that next step.

## Common Pitfalls

- Don't auto-accept — `--accept` is the engineer gate; `spec-intent` presents and waits, it never flips PROPOSED → ACCEPTED on its own.
- Don't reimplement authoring logic — sequence `/write-intent` and the `write-*` skills unchanged; a parallel implementation drifts from the canonical authoring surfaces.
- Don't cross the coding boundary — never dispatch `/exec-coding-session` or write implementation code; this skill ends at IMPLEMENTING.
- Don't leave child specs raw — drive every scaffolded WS/IC/IB to ACCEPTED/LOCKED before declaring ready-for-coding.

## Verification Checklist

- [ ] `/write-intent --analyze` ran; the Intent is PROPOSED (or OVERSIZED was handled).
- [ ] `--accept` was run only after explicit engineer approval (engineer gate honored).
- [ ] `--decompose` scaffolded the downstream artifacts; each child spec was driven to ACCEPTED/LOCKED.
- [ ] The parent Intent is at IMPLEMENTING (ready-for-coding).
- [ ] No coding session was dispatched and no implementation code was written — the run stopped at the coding boundary.
- [ ] The next step (`/exec-coding-session <intent>`) was named in the hand-off.

## Closing Step

After the run, `dekspec audit relink` against the repo root to restitch the backlinks the scaffolded child specs introduced.
