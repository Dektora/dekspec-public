---
name: spec-intent
description: Specification phase-executor for an Intent (INT-NNN). Drives an Intent from DRAFT to authorized-for-execution by sequencing the existing authoring skills — /write-intent --analyze / --accept / --decompose plus /write-ibs, /write-tests and /review-ib and, only where they add something distinct, /write-ws, /write-ic, /write-ae, /write-adr — and ends with the Intent ACCEPTED and each of its IBs ACCEPTED (`dekspec ib accept`: authorized, acceptance baseline taken over acceptance tests that were written and oracle-reviewed first). Stops at the coding boundary; never starts execution. The specification-side sibling of /orchestrate-coding-session.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] <INT-NNN | path/ID of Intent>
related_skills: [write-intent, write-ws, write-ibs, review-ib, write-tests, implement, orchestrate-coding-session]
---

> **Vendored asset paths (INT-097):** Paths below like `dekspec/...` reference the consumer-vendored layout. Pip-only installs resolve via `dekspec resource ...`. See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md).

Specification phase-executor for an Intent — the specification-side counterpart to `/orchestrate-coding-session` (execution) and `/dekspec:land-intent` (landing). It sequences the existing authoring skills and engine verbs; it reimplements none of them, and it **stops at the coding boundary**.

Use it when an Intent earns its place — an outcome spanning several IBs (ADR-056 §4). A bounded change needs no Intent: author one IB (`dekspec ib new <slug>` or `/write-ibs`) and authorize it directly.

## Starter Prompt

```prompt
/dekspec:spec-intent INT-130

Take INT-130 from DRAFT to authorized-for-execution: analyze it, pause for my
accept, then decompose it into IBs and get each one to ACCEPTED. Stop at the
coding boundary — don't start execution.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Spec Mode**.

- **Help mode** — `--help` flag. See **Help Mode**.
- **Spec mode** — default (an `INT-NNN` / path positional). Proceed to **Spec Mode**.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:spec-intent"
one_line:   "Drive an Intent from DRAFT to ACCEPTED with every child IB ACCEPTED, by sequencing the write-* skills and `dekspec ib` authorization."
modes:
  - { flag: "", args: "<INT-NNN>", description: "Spec mode — analyze → accept → decompose into IBs → per IB: acceptance tests → oracle review → authorize; stop at the coding boundary." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:spec-intent INT-130"
  - "/dekspec:spec-intent --help"
```

## Spec Mode

Identify the target Intent — **canonical or provisional** (ds-jtfn). Resolve `$ARGUMENTS` with the shared resolver, which accepts a canonical `INT-NNN`, a canonical/provisional Intent path, or a provisional incubation slug:

```
python ../_lib/scripts/resolve_intent_target.py "<arg>"
```

It emits `{kind, path, intent_id, status, is_provisional}`. Use the resolved **path** as `<intent>` below. A provisional target is fully supported: `--analyze` works on the provisional content, and `--accept` (Phase 2) runs the INT-082 Provisional Promotion that allocates the canonical `INT-NNN` via `git mv` atomically with PROPOSED → ACCEPTED. On the resolver's exit 1, surface stderr and STOP (for an ambiguous multi-Intent incubation, ask for the explicit file path).

### Phase 1 — Analyze

`/write-intent --analyze <intent>` — coverage, archaeology and size assessment. DRAFT → PROPOSED. A size-cap violation is an analysis finding (a P2 open issue that blocks acceptance, ADR-057), resolved through the split flow in [`_lib/oversized_splitting.md`](../_lib/oversized_splitting.md) (ADR-028 PEEL-OFF default) before accepting.

### Phase 2 — Accept (engineer-gated)

Present the analyzed Intent and run `/write-intent --accept <intent>` only on the engineer's approval. `spec-intent` never auto-accepts. PROPOSED → ACCEPTED.

### Phase 3 — Decompose into IBs; update only the specs the change affects

`/write-intent --decompose <intent>` scaffolds the child IBs (each with `**Parent:** INT-NNN`), cut as vertical slices with shared shapes routed per ADR-054 (as revised by ADR-056: a pin has one home). Complete each IB with `/write-ibs`. Author or revise a WS, IC, AE or ADR only where it adds something distinct — behavior spanning IBs, a real cross-component boundary, an architecture change, a new decision — and let each IB reference it as an obligation rather than copy it (ADR-056 §4–5). Host the architectural-interview prompts here.

### Phase 4 — Authorize each IB

For every child IB, in this order (ADR-062) — acceptance tests are mandatory, written and oracle-reviewed before authorization:

1. `dekspec ib lint <IB>` — clean: executable contract, every obligation reference resolves.
2. `dekspec ib propose <IB>` — DRAFT → PROPOSED.
3. `/dekspec:write-tests <IB>` — **mandatory** for every `pytest:` condition: the named nodes, a `Basis:` for each new assertion, a behavior-free surface skeleton for entry points that do not exist yet, committed together; `dekspec ib floor <IB>` must report every new node genuine red with a basis and every preserved node passing. (`/dekspec:write-evals` for eval `command:` conditions.)
4. `/dekspec:review-ib <IB>` — the independent pre-authorization review, run in a context that did not write the tests: the contract lenses, plus the `acceptance-oracle` lens over the test sources, the skeleton and the floor report. Surfaced findings land in the IB's Open Issues; resolve the P1/P2 ones and repeat steps 3–4. A passing floor review is recorded as a `Floor reviewed: PASS — digest …` Amendment Log row.
5. `dekspec ib accept <IB>` — on the engineer's approval, and only while `dekspec ib floor <IB>` reports the digest the `Floor reviewed:` row names. PROPOSED → ACCEPTED; takes the acceptance baseline, tests included.

A change to the tests or the contract after the review repeats steps 3–4 (a new `Floor reviewed:` row) before the floor is protected — by `dekspec ib accept`, or, once ACCEPTED and before the run starts, by `dekspec ib baseline <IB> --reason "…"` (ADR-057, ADR-062).

Drive any WS or AE you authored to ACCEPTED (they never lock, ADR-046) and any IC or ADR to its terminal status.

### Phase 5 — Check readiness, then stop at the coding boundary

Evaluate the READY predicate — the same one `/implement` checks at entry (ADR-059):

```bash
dekspec implement ready <INT-NNN>
```

- **READY** — report it, with the IB order and the delivery the run would use. The next step is `/dekspec:implement <INT-NNN>`, which carries the work through construction, review, integration and completion without further prompts. The manual alternative is `/orchestrate-coding-session` then `/dekspec:land-intent`.
- **NOT READY** — report each missing item and its fix exactly as returned, for example an IB edited after `accept`, a blocking Open Issue, autonomy `manual`, an unresolved obligation or a missing prerequisite. Resolve the ones that are specification work here with the engineer. Never approve on their behalf.

**This skill stops at the coding boundary: it does not start execution** — no `dekspec ib start`, no dispatch.

## Common Pitfalls

- Don't auto-accept — neither the Intent (`--accept`) nor an IB (`dekspec ib accept`); present and wait for the engineer.
- Don't reimplement authoring logic — sequence `/write-intent`, `/write-ibs` and the other `write-*` skills unchanged.
- Don't cross the coding boundary — never run `dekspec ib start` or write implementation code.
- Don't author empty or duplicative parent artifacts — a WS, IC or ADR exists only when it owns a fact no IB should copy (ADR-056).
- Don't re-baseline after execution starts — then only `dekspec ib amend` with an independent reviewer changes the contract.
- Don't authorize an IB whose acceptance tests are missing, unreviewed, or reviewed at a different floor digest — `/implement` readiness refuses it, and the builder never writes them.

## Verification Checklist

- [ ] `/write-intent --analyze` ran; the Intent is PROPOSED and any size-cap finding was resolved.
- [ ] `--accept` ran only after explicit engineer approval.
- [ ] Every child IB passed `dekspec ib lint` and was proposed; its acceptance tests were then written (`/dekspec:write-tests`, genuine red on `dekspec ib floor`) and oracle-reviewed with `/dekspec:review-ib` (a `Floor reviewed:` row names the floor digest); only then was it accepted with `dekspec ib accept`.
- [ ] Any pre-start change to the tests was re-reviewed (a new row) and re-protected with `dekspec ib baseline` before execution.
- [ ] The Intent is ACCEPTED; no execution was started and no implementation code was written.
- [ ] `dekspec implement ready` was evaluated and its READY / missing-preparation result reported, with `/dekspec:implement <intent>` named as the next step when READY.

## Closing Step

After the run, `dekspec relink` against the repo root to restitch the backlinks the new IBs and specs introduced.
