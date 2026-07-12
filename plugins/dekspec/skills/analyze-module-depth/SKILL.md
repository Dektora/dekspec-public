---
name: analyze-module-depth
description: Surface deepening opportunities in a codebase — refactors that turn shallow modules into deep ones, grounded in the domain language in `dekspec/domain-glossary.md` and the decisions in `dekspec/adrs/`. Use when the engineer wants to improve architecture, find refactoring opportunities, consolidate tightly-coupled modules, or make a codebase more testable and AI-navigable.
mode: lite
# override-reason: latest Opus tier per CLAUDE.md model policy; suite default (claude-opus-4-7) predates 4-8
model: claude-opus-4-8
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Grep Glob Bash Agent
argument-hint: [--help] [--teaching] [--scope PATH]
---

Surface architectural friction and propose **deepening opportunities** —
refactors that turn shallow modules into deep ones. The aim is testability and
AI-navigability.

This skill **surfaces → reports → interviews**. It opens no `br` beads, implements
nothing, and lands nothing — that is the sibling `orchestrate-module-deepening` skill,
which is out of scope here. See **Boundary** below.

The architecture vocabulary it speaks — Module, Interface, Implementation,
Depth, Seam, Adapter, Leverage, Locality — is canonical in
`dekspec/domain-glossary.md` (the *Architecture Vocabulary* section) and grounded
in *A Philosophy of Software Design*
(`../../../../docs/a-philosophy-of-software-design-ai-reference.md`).
[language.md](language.md) restates it for self-containment but the glossary is
the authority. Don't re-derive the definitions or invent new architecture terms.

This skill is _informed_ by the project's domain model: the domain glossary
gives names to good seams, and the ADRs under `dekspec/adrs/` record decisions
the skill should not re-litigate.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill surfaces deepening opportunities from a codebase. Prior
> conversation context can bias the walk by anchoring on a mental model the
> code itself does not support.
>
> First message → proceed. Prior history → ask "context may bias the deepening
> walk, recommend /clear, continue? (y/n)" + wait.

## Glossary

Use these terms exactly in every suggestion — don't drift into "component,"
"service," "API," or "boundary." Full definitions in [language.md](language.md);
canonical in `dekspec/domain-glossary.md`.

- **Module** — anything with an interface and an implementation (function, class,
  package, slice).
- **Interface** — everything a caller must know to use the module: types,
  invariants, error modes, ordering, config. Not just the type signature.
- **Implementation** — the code inside.
- **Depth** — leverage at the interface: a lot of behaviour behind a small
  interface. **Deep** = high leverage. **Shallow** = interface nearly as complex
  as the implementation.
- **Seam** — where an interface lives; a place behaviour can be altered without
  editing in place. (Use this, not "boundary.")
- **Adapter** — a concrete thing satisfying an interface at a seam.
- **Leverage** — what callers get from depth.
- **Locality** — what maintainers get from depth: change, bugs, knowledge
  concentrated in one place.

Key principles (full list in [language.md](language.md)):

- **Deletion test** — imagine deleting the module. If complexity vanishes, it
  was a pass-through. If complexity reappears across N callers, it was earning
  its keep.
- **The interface is the test surface.**
- **One adapter = a hypothetical seam. Two adapters = a real seam.**

## The `--scope` argument

The skill takes ONE optional slice argument, `--scope <path-or-module>`. It
collapses the inherited free-form axis + focus pair into this single input.

- **Absent** (no scope given) ⇒ the default: an unsteered, **exhaustive
  whole-repo** Explore walk. This is the no-scope default-walk behavior.
- **Present** ⇒ the scope value **confines / filters WHERE** the Explore walk
  looks — it restricts the walk to that path / subsystem / module slice.

Critically, `--scope` changes only *where* the walk looks. It does **not** change
the objective deepening criteria: the **deletion test** and the
**shallow-interface signal** are applied identically and remain **unchanged**
regardless of scope. A narrow scope finds fewer candidates; it does not lower
the bar for what counts as a deepening.

## Mode Detection

Parse `$ARGUMENTS` for flags.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Scoped walk** — `--scope <path-or-module>` flag. Proceed to **Workflow
  Mode**, confining the Explore walk in step 1 to the given slice. The objective
  deepening criteria are unchanged by scope.
- **Default (whole-repo) mode** — no flag. Proceed to **Workflow Mode** with an
  unsteered, exhaustive whole-repo Explore walk.

The mode catalog is deliberately minimal. This skill has no artifact lifecycle
of its own (it promotes nothing), so it carries none of the lifecycle modes
(`--accept`, `--lock`, `--decompose`, …) the `/dekspec:write-*` skills expose.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the
canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:analyze-module-depth"
one_line:   "Surface deepening opportunities — shallow modules made deep — and interview the chosen one"
modes:
  - { flag: "", args: "", description: "Default mode: an unsteered, exhaustive whole-repo Explore walk, then an HTML report, then an interview loop on the chosen candidate." }
  - { flag: "--scope", args: "<path-or-module>", description: "Confine the Explore walk to one path / subsystem / module slice. Filters WHERE the walk looks; the objective deepening criteria (deletion test, shallow-interface signal) are unchanged." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial — the surface → report → interview workflow explained step-by-step for an engineer new to deepening." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:analyze-module-depth"
  - "/dekspec:analyze-module-depth --scope tooling/dekspec/fidelity_audit"
  - "/dekspec:analyze-module-depth --teaching"
  - "/dekspec:analyze-module-depth --help"
extra_sections:
  - heading: "BOUNDARY"
    body:
      - "This skill surfaces, reports (a self-contained HTML file), and interviews."
      - "It opens no br beads, implements nothing, and lands nothing — that is"
      - "the sibling orchestrate-module-deepening skill. Every change is an explicit"
      - "engineer action downstream of this skill's report."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

Teaching Mode walks an engineer new to deepening through the same workflow as
the default mode, but slowly and with explanation at each step. It is **not** a
fast one-shot — it is the workflow with teaching scaffolding.

Run the three **Workflow Mode** steps below, and before each step pause to
explain:

1. **Before step 1 (Explore)** — explain what a *deep* vs *shallow* module is
   (see [language.md](language.md)), and the **deletion test** that decides it.
   Explain that the default walk is an exhaustive whole-repo sweep, and that
   `--scope` only narrows *where* it looks, never the bar for what counts.
2. **Before step 2 (Report)** — explain why candidates are surfaced as a
   self-contained HTML report before any interface is proposed: the engineer
   chooses the direction; the skill does not pre-commit.
3. **Before step 3 (Interview)** — explain the Design-It-Twice interview loop and
   that the skill stops at the design boundary — it opens no beads and lands
   nothing.

After the walk-through, confirm the engineer can run the default mode unaided,
and stop.

## Workflow Mode

The default mode. Surface, report, interview — and stop.

### 1. Explore

Read the project's domain glossary (`dekspec/domain-glossary.md`) and any ADRs
under `dekspec/adrs/` in the area you're touching first.

Then use the Agent tool with `subagent_type=Explore` to walk the codebase.

- **No `--scope`** ⇒ an unsteered, **exhaustive whole-repo** walk. Don't follow
  rigid heuristics — explore organically.
- **`--scope <slice>`** ⇒ confine the walk to that path / subsystem / module.

Either way, note friction: where understanding one concept requires bouncing
between many small modules; where modules are shallow; where pure functions were
extracted just for testability but real bugs hide in how they're called (no
locality); where tightly-coupled modules leak across seams; which parts are
untested or hard to test through their current interface. Apply the **deletion
test** to anything you suspect is shallow. These objective criteria — the
deletion test and the shallow-interface signal — are **unchanged** by scope.

### 2. Present candidates as an HTML report

Write a self-contained HTML file to the OS temp dir (resolve `$TMPDIR`, fall
back to `/tmp` or `%TEMP%`): `<tmpdir>/architecture-review-<timestamp>.html`.
Open it (`xdg-open` / `open` / `start`) and tell the engineer the absolute path.

Use the domain vocabulary from `dekspec/domain-glossary.md` for the domain and
[language.md](language.md) vocabulary for the architecture. If a candidate
contradicts an existing ADR under `dekspec/adrs/`, surface it only when the
friction is real enough to warrant revisiting the ADR, and mark it clearly —
don't list every theoretical refactor an ADR forbids.

See [html_report.md](html_report.md) for the full HTML scaffold. Do NOT propose
interfaces yet. After the file is written, ask the engineer: "Which of these
would you like to explore?"

### 3. Interview loop

Once the engineer picks a candidate, drop into an interview conversation. Walk the
design tree — constraints, dependencies (categorise them per
[deepening.md](deepening.md)), the shape of the deepened module, what sits behind
the seam, what tests survive. The bounded three-move set and the over-consolidation
guardrail in [deepening.md](deepening.md) govern what a legal deepening move is.

Side effects inline, as decisions crystallise — re-grounded on the dekspec
surface:

- Naming a deepened module after a concept not in `dekspec/domain-glossary.md`?
  Add the term to `dekspec/domain-glossary.md` (the canonical domain glossary).
- Sharpening a fuzzy term? Update `dekspec/domain-glossary.md` right there.
- The engineer rejects a candidate with a load-bearing reason that a future
  explorer would actually need? Offer an ADR under `dekspec/adrs/`: "Want me to
  record this as an ADR so future deepening walks don't re-suggest it?"
- Want to explore alternative interfaces? See [interface_design.md](interface_design.md).
- A chosen deep module that should become a package? Folderize it per
  [`../_lib/folderize_deep_module.md`](../_lib/folderize_deep_module.md).

The skill stops here — at the design boundary. It opens no beads and lands
nothing.

## Boundary — this skill surfaces, reports, and interviews; it lands nothing

This skill produces conversational guidance plus one self-contained HTML report.
It does **not**:

- open any `br` bead,
- implement, edit, or land any code,
- edit anything under `dekspec/` except the inline domain-glossary / ADR
  side-effects above, which are explicit engineer-confirmed authoring steps,
- set or change any artifact's status.

Driving a chosen deepening to landed code is the sibling `orchestrate-module-deepening`
skill's job, not this one's.
