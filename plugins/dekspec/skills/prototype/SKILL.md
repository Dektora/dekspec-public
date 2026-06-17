---
name: prototype
description: Cheapest-shape, pre-spec throwaway-exploration loop for DekSpec — feel out a state model or a request/response shape BEFORE committing to an Intent or Working Spec. All throwaway code lands ONLY in the gitignored `dekspec/.scratch/prototypes/<run>/` ephemeral zone (INT-165 / ADR-040) and is never production code; the durable FINDINGS (decision reached, approaches rejected, risks surfaced, suggested next artifact) route into the governed authoring skills (/write-ws, /write-ic, /write-ae) rather than dead-ending. A no-production-leak discipline holds throughout: any production adoption passes through the normal Intent → WS → IB lifecycle. Use when you want to explore a design cheaply and disposably before specifying it, sketch an API shape, or sanity-check a state model first.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] [--shape logic|api] [--at PATH]
related_skills: [write-ws, write-ic, write-ae]
---

Run the governed pre-spec throwaway-exploration loop. The **whole point of this
skill** is to let you explore a design *cheaply and disposably* — before you pay
the cost of specifying it. You build a throwaway artifact in one of two shapes,
learn from it, and capture the **durable findings** that route into a governed
artifact. The throwaway code is disposable; the findings are not.

This skill owns one strict discipline — **no production leak**. Every line of
throwaway code lands ONLY under the gitignored ephemeral zone
`dekspec/.scratch/prototypes/<run>/` (landed by INT-165 / α, ADR-040) and is
never committed. The prototype's *outcome* never gets promoted directly into a
real code path; any production adoption passes through the normal
Intent → Working Spec → Implementation Brief lifecycle. What re-enters the
governed world is the **findings**, handed to `/dekspec:write-ws`,
`/dekspec:write-ic`, or `/dekspec:write-ae` — never the scratch code itself.

## Starter Prompt

```prompt
/dekspec:prototype --shape logic --at .

I want to feel out <design question> before specifying it. Build a throwaway
exploration under dekspec/.scratch/prototypes/<run>/ ONLY — never a tracked
path. Explore, then capture FINDINGS (decision reached, approaches rejected,
risks surfaced, suggested next governed artifact) and route them into
/dekspec:write-ws / /dekspec:write-ic / /dekspec:write-ae. Do not promote any
scratch code into a real code path.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Prototype Mode**.

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Prototype mode** — no flag (default). Optional `--shape logic|api` selects
  the exploration shape (default: `logic`); optional `--at PATH` names the repo
  root (default: current working directory). Run the loop below.

This skill exposes no lifecycle/audit/review flags of its own — it is a pre-spec
exploration loop, not an artifact-lifecycle authoring skill. (It is therefore
exempt from the `_lib/mode_dispatcher.md` universal-mode set, which applies only
to the `write-*` artifact-lifecycle skills.) `--shape` is a sub-argument that
selects the throwaway shape within Prototype mode, not a standalone mode.

## Prototype Mode

### PHASE 1 — pick the shape and scaffold the throwaway zone

1. **Name the design question** in one line — the state model, request/response
   shape, or behavior you want to feel out before specifying it.
2. **Pick a shape** (`--shape`, default `logic`):
   - `logic` — a throwaway terminal app exercising a state model. Wire the
     smallest runnable program that lets you step the states and watch the
     transitions, on the repo's own runtime (detect it from the repo's
     manifest / lockfiles). Never invent a runner.
   - `api` — a request/response shape sketch. Stub the endpoints / message
     payloads as a throwaway sketch you can exercise against sample inputs.
   - *(`UI` switchable-variants is a DEFERRED follow-up — see below.)*
3. **Scaffold the throwaway zone**: create
   `dekspec/.scratch/prototypes/<run>/` (a `<run>` slug for this exploration;
   create the dir if absent) and write **all** throwaway code there and nowhere
   else. This is the gitignored ephemeral zone — it is never committed.

### PHASE 2 — explore disposably

4. **Explore.** Run the throwaway artifact, step the state model or exercise the
   API shape, try the approaches you are weighing against each other. This code
   is disposable working memory; spend it freely and do not harden it.
5. **Throw it away.** When the exploration has answered the question, the
   scratch code has done its job. Do not refactor it toward production; do not
   move it out of `dekspec/.scratch/prototypes/`.

### PHASE 3 — capture findings and route into the governed lifecycle

6. **Capture the findings** — the durable output. Record: the **decision
   reached**, the **approaches rejected** (and why), the **risks surfaced**, and
   the **suggested next governed artifact**. You MAY stage a working draft under
   `dekspec/.scratch/prototypes/<run>/FINDINGS.md` as disposable scratch, but
   durability is achieved by *routing the findings into a governed artifact* —
   never by committing the scratch findings file.
7. **Route the findings** into the governed authoring skills:
   - a behavioral contract → `/dekspec:write-ws` (Working Spec);
   - a cross-component boundary → `/dekspec:write-ic` (Interface Contract);
   - a system/component vision slice → `/dekspec:write-ae` (Architecture Element).
   Domain-term clarifications that surface during exploration route to
   `/dekspec:write-ggc` rather than being defined inline.

**No production leak (the discipline):** any production adoption of a
prototype's outcome must pass through the normal
Intent → Working Spec → Implementation Brief lifecycle (start with
`/dekspec:write-intent`). The prototype output itself is never promoted directly
into a real code path — only the findings re-enter the governed world.

### Deferred: the `UI` (switchable-variants) shape

A third shape — `UI`, rendering switchable variants for side-by-side comparison
— is a **deferred follow-up**, not part of this first cut. Its host-agnostic
rendering surface is a larger question than a pre-spec exploration skill should
carry in v1. When you need UI-variant comparison today, build it as a `logic`
prototype (a throwaway app) under the same scratch zone, or open a follow-up
Intent to add the `UI` shape natively.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:prototype"
one_line:   "Pre-spec throwaway-exploration loop — explore a state model (logic) or request/response shape (api) in disposable dekspec/.scratch/prototypes/ code, then route the durable findings into /write-ws / /write-ic / /write-ae. No production leak."
modes:
  - { flag: "", args: "[--shape logic|api] [--at PATH]", description: "Prototype mode — scaffold a throwaway exploration under dekspec/.scratch/prototypes/<run>/, explore disposably, then capture findings and route them into /write-ws / /write-ic / /write-ae. Shapes: logic (throwaway terminal app over a state model), api (request/response sketch). UI is a deferred follow-up." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:prototype --shape logic --at ."
  - "/dekspec:prototype --shape api"
  - "/dekspec:prototype --help"
storage: "dekspec/.scratch/prototypes/<run>/ (gitignored ephemeral throwaway zone; durable findings route into a governed artifact via /write-ws / /write-ic / /write-ae, never committed as scratch)"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## When to use

- When you want to feel out a state model, sketch an API shape, or compare a
  couple of approaches *cheaply and disposably* — before committing to an Intent
  or Working Spec.
- Before specifying a design whose shape you are unsure of — so the spec rests
  on a throwaway exploration rather than on a blind guess.

## When NOT to use

- To author the governed artifact itself — that is `/dekspec:write-ws`,
  `/dekspec:write-ic`, or `/dekspec:write-ae`; `prototype` *produces the
  findings* those skills consume.
- To reproduce a bug before fixing it — that is `/dekspec:diagnose` (a
  debugging loop, not a pre-spec design exploration).
- To build anything intended to survive — prototype code is throwaway by
  contract and lives only in the gitignored scratch zone.

## Related

- `/dekspec:write-ws` — consumes a behavioral-contract finding into a Working Spec.
- `/dekspec:write-ic` — consumes a cross-component-boundary finding into an Interface Contract.
- `/dekspec:write-ae` — consumes a system/component-vision finding into an Architecture Element.
- `/dekspec:write-intent` — the lifecycle entry point any production adoption of a prototype's outcome must pass through (no direct promotion of scratch code).
- `/dekspec:write-ggc` — domain-term clarifications surfaced during exploration route here.
- AE-006 (Skills Library) — the AE this skill registers under; INT-165 / ADR-040 owns the `dekspec/.scratch/` ephemeral zone this skill's throwaway code is confined to.
