---
name: write-ibs
description: Author Implementation Briefs — the smallest governed work contract, executed directly (ADR-056). Use for a bounded change (outcome + rationale + references are enough, no parent needed), to decompose an Intent or a Working Spec into IBs, to audit, review, revise or accept an IB, or to adopt a legacy IB into the delegated authority policy.
mode: full
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --revise | --resync | --accept | --adopt | --dry-run] [description of the change, Intent / Working Spec path, or IB path] [engineer notes or path to notes file]
related_skills: [write-intent, write-ws, write-ic, write-tests, review-ib, orchestrate-coding-session]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

Author Implementation Briefs. An IB is the smallest governed work contract and is executed directly — there are no code beads (ADR-056). One IB carries a bounded change; an Intent or a Working Spec that spans more than one IB is decomposed into several.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill decides what binds an implementing agent. Prior conversation context can leak unapproved decisions into an IB as if they were obligations.
>
> Inline reasoning only (see mode manifest); substantive fan-out skips this check. First message → proceed. Prior history → ask "context may affect IB quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-ibs Make `dekspec validate` reject an Intent whose Verification cmd is empty.

Bounded change, no parent. The rule belongs to the Intent parser; ADR-013 governs the
severity vocabulary. Include the failure path and the CLI entry point in Acceptance.
```

## The contract you are writing

The template `dekspec/templates/implementation-brief-template.md` is authoritative for the format; follow it section by section. What the sections mean:

- **Three kinds of content (ADR-055).** *Binding obligations* — `## Obligations`, `## Protected Surfaces`, `## Scope`; the implementing agent preserves them. *Acceptance conditions* — the `## Acceptance` YAML block; the agent demonstrates them and never weakens them. *Implementation hypothesis* — `## Implementation Hypothesis`; a starting guess the agent revises after investigating, within Scope, without asking. Classify by meaning, not by where a sentence used to live.
- **One home per fact (ADR-056).** An obligation owned by an ADR, IC, WS, AE, SP or the Constitution is *referenced* (`- **O-1** → ADR-036`, `- **O-2** → IC-012 §Shape`), never copied — no Spec Context, no reconciled restatement. Tag an obligation `(local)` only when this IB is its canonical home. `dekspec ib context IB-NNN` delivers the canonical text, its source revision and hash to the implementing agent; DekSpec's project reference policy decides source eligibility. The default `strict` policy requires approved sources; `evolving` also permits canonical PROPOSED ADRs and AEs with their actual status and policy notice visible. Missing, ambiguous, DRAFT and retired sources still block `propose`, `accept` and `start`. Referencing an evolving source never authorizes an IB by itself.
- **No mandatory chain (ADR-056).** `**Parent:**` (INT-, WS- or MSN-NNN) is optional. A bounded change needs only Outcome, Rationale and references. When the change alters architecture or a contract, name the specs in `**Spec impact:**` — verification fails unless the delivery modifies them.
- **Authority policy.** New IBs say `**Authority policy:** delegated`. An IB without the line, or with `legacy`, keeps the ADR-049 meaning (Files to Modify is an allowlist) until it is adopted (`--adopt`).
- **Lifecycle (ADR-057).** `DRAFT` → `PROPOSED` (`dekspec ib propose`) → `ACCEPTED` (`dekspec ib accept`, which takes the acceptance baseline) → `COMPLETE` (only `dekspec ib complete`), plus `SUPERSEDED` / `DEPRECATED`. Ownership, plans, attempts, deviations, evidence and verdicts live in the execution record (`.dekspec/execution/IB-NNN/`), never in the IB.
- **The authoring order (ADR-062).** Write the IB (`dekspec ib lint`, `dekspec ib propose`) → `/dekspec:write-tests` (mandatory for every `pytest:` condition: a `Basis:` per new assertion, a behavior-free surface skeleton, genuine red on `dekspec ib floor`) → `/dekspec:review-ib` (its `acceptance-oracle` lens records a passing floor review as a `Floor reviewed: PASS — digest …` Amendment Log row) → `dekspec ib accept`, run by the authorizer only while `dekspec ib floor` still reports the digest that row names (the command does not check it; `/implement` readiness does). A pre-start re-baseline after the tests change repeats the review. The builder never writes acceptance tests; `/implement` readiness refuses an IB whose named nodes are missing from its baseline or whose baseline digest no floor review names.

**Roles (ADR-061).** This skill plays DekSpec's Agent Role Specifications; the engineer never selects one. Authoring, revise and resync modes play the **`specifier`** role, audit modes the **`auditor`** role: run `dekspec resource role specifier` or `dekspec resource role auditor` at the start of the mode and follow it (a delegated `*-author` agent loads `specifier` itself). See [`_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) §The role each universal mode plays and [`_lib/agent_roles.md`](../_lib/agent_roles.md).

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode (no flag): content-shape dispatch — an existing IB path → **Audit Mode**; a Working Spec or Intent path, or a description of a change → **Create / Decompose Mode**; otherwise ask the engineer.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Audit mode** — `--audit` flag, or no flag + an existing IB path. Skip to **Audit Mode**. Read-only.
- **Review mode** — `--review` flag. Skip to **Review Mode**.
- **Revise mode** — `--revise` flag. Skip to **Revise Mode**.
- **Resync mode** — `--resync` flag. Skip to **Resync Mode**.
- **Accept mode** — `--accept` flag. Skip to **Accept Mode**.
- **Adopt mode** — `--adopt` flag, expects a legacy IB. Skip to **Adopt Mode**.
- **Dry-run mode** — `--dry-run` flag. Skip to **Dry-Run Mode**.
- **Provisional mode** — `--provisional <slug>` (composes with Create). See **Provisional Mode**.
- **Create / Decompose mode** — no flag + a description, a Working Spec path or an Intent path. Proceed to **Create / Decompose Mode**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): Create / Decompose, `--revise`, `--adopt`
- Inline (parent context): `--help`, `--teaching`, `--audit`, `--review`, `--resync`, `--accept`, `--dry-run`

## Fan-Out Mode

Bundle source paths rather than parent summaries; preserve engineer guidance verbatim. Keep parsed mode/path fields and labeled orchestrator notes separate. Show the manifest and preserve fan-out/ingest provenance per the shared substrate; existing task authorization suffices for dispatch.

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `dekspec:ib-author`
- **substantive_modes**: [Create / Decompose, `--revise`, `--adopt`]
- **inline_modes**: [`--help`, `--teaching`, `--audit`, `--review`, `--resync`, `--accept`, `--dry-run`]
- **mechanical precondition** (orchestrator, before dispatch): when the input is a Working Spec, run the L12 gate below; when it is an Intent, confirm it is `ACCEPTED`.
- **bundle_list** (absolute paths): the IB template; the input (description verbatim, or the WS / Intent path); the domain glossary; the ADR, IC and WS paths the input names (the worker reads what it needs — it references them, it does not copy them); existing IBs sharing the same Parent (for scope overlap and shared-shape homes); engineer notes verbatim; the mode's section of this skill by name.
- **expected_output_path**: `dekspec/impl-briefs/IB-NNN-<slug>.md` per IB (Create), or the input IB path (revise / adopt).
- **validation**: the orchestrator re-runs `dekspec ib lint IB-NNN` and `dekspec validate <path>` per IB (trust-but-verify; see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md)). Surface worker escalations verbatim — an underdefined contract is a finding, not something to paper over.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-ibs"
one_line:   "Author, audit, revise, accept and adopt Implementation Briefs (ADR-055–058)"
modes:
  - { flag: "", args: "<description | WS-path | Intent-path>", description: "Create one IB for a bounded change (no parent needed), or decompose an ACCEPTED Intent / Working Spec into IBs. Writes delegated IBs per the template: obligations referenced, Acceptance YAML, revisable hypothesis. Ends at PROPOSED via `dekspec ib propose` when lint is clean. (Create / Decompose Mode)" }
  - { flag: "--audit", args: "<IB-path | glob>", description: "Read-only contract check: `dekspec ib lint` + authoring checks + cross-IB checks. (Audit Mode)" }
  - { flag: "--review", args: "<IB-path>", description: "Walk open issues with the engineer and run the Spec-Reviewer pass. (Review Mode)" }
  - { flag: "--revise", args: "<IB-path> <notes>", description: "Apply engineer notes; re-authorizes an accepted contract through `ib baseline` or `ib amend`. (Revise Mode)" }
  - { flag: "--resync", args: "<IB-path | glob>", description: "Repair obligation references after an upstream ADR / IC / WS changed (superseded source, renamed section). Never copies text. (Resync Mode)" }
  - { flag: "--accept", args: "<IB-path | glob>", description: "Authorize after a clean audit, written acceptance tests, a passing oracle review (`Floor reviewed:` row) and engineer confirmation: `dekspec ib propose` (if DRAFT) then `dekspec ib accept`, which takes the acceptance baseline. (Accept Mode)" }
  - { flag: "--adopt", args: "<IB-path>", description: "Rewrite a legacy IB into the delegated format, classifying each legacy constraint deliberately, then `dekspec ib adopt`. (Adopt Mode)" }
  - { flag: "--dry-run", args: "<WS-path | Intent-path>", description: "Preview the IB cut — titles, Scope, dependencies, shared-shape homes — without writing. (Dry-Run Mode)" }
  - { flag: "--teaching", args: "", description: "Walk a new author through one IB section by section. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-ibs \"reject Intents whose Verification cmd is empty\""
  - "/write-ibs dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-ibs dekspec/working-specs/WS-001-foo.md"
  - "/write-ibs --audit \"dekspec/impl-briefs/**/*.md\""
  - "/write-ibs --revise IB-012 \"AC-2 must cover the empty-file case\""
  - "/write-ibs --accept IB-012"
  - "/write-ibs --adopt dekspec/impl-briefs/active/IB-040-foo.md"
  - "/write-ibs --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: IB (Implementation Brief)
- **template_path**: `templates/implementation-brief-template.md`
- **methodology_section**: §4 Layer 3 of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/impl-briefs/` (prefer an IB whose header says `**Authority policy:** delegated`)
- **required_sections**: [Outcome, Rationale, Scope, Obligations, Protected Surfaces, Acceptance, Implementation Hypothesis, Environment Prerequisites]

Skill-specific checks to surface as Open Issues: every `dekspec ib lint IB-NNN` problem; any obligation that restates another artifact's text instead of referencing it.

## Create / Decompose Mode

### Inputs and preconditions

- **A description of a bounded change** (no parent). Enough when it yields an Outcome, a Rationale and the references that govern it. Ask for what is missing; do not invent it.
- **An Intent** — must be `ACCEPTED`. Each IB gets `**Parent:** INT-NNN`, and its Scope lies inside the Intent's `Components affected:`. Together the IBs deliver the Intent's Desired Outcome (the Intent's Verification is the cross-IB proof, run by `dekspec intent verify`).
- **A Working Spec** — the IBs reference its sections (`→ WS-NNN §Section`); `**Parent:** WS-NNN` when the WS is the reason the IB exists. **L12 gate:** run `dekspec validate <ws-path> --json`; if the WS is `ACCEPTED` and carries any unresolved `P1` open issue (`blocking_pre_ib` per ADR-013 / LINK-WS-BLOCKING-PRE-IB-CLEAN), refuse and name each issue. A WS at DRAFT/PROPOSED cannot be referenced as binding (it is not approved) — settle it first. No bypass flag.

### Investigate

Read what the change touches before cutting it: the code on the likely paths, the governing ADRs / ICs / WS sections (resolve supersession with `python ../_lib/scripts/resolve_supersession.py <ADR-ID>`), and existing IBs with the same Parent. Investigation is proportionate — a one-file change needs little. Findings feed the hypothesis; a finding that contradicts a binding source is a conflict to raise with the engineer, never to settle silently.

### Cut the IBs

One IB per independently verifiable outcome — something whose acceptance conditions can be demonstrated without another IB's implementation. Split when outcomes are unrelated or fail independently; keep together what one business rule would change together. No fixed sizing: an IB is as large as one coherent, reviewable outcome.

**Shared foundations route, they do not default to extraction (ADR-054, delivery revised by ADR-056).** Cut vertical slices. When several slices need the same type, schema or constant:

1. **Interface Contract** — when the shared surface is a genuine cross-component boundary.
2. **Pin once** *(the default)* — write the shape in exactly one home: an IC section, a WS section, or a `(local)` obligation of one IB. Every consumer references that home (`- **O-n** → IB-NNN §O-1`, `→ WS-NNN §Section`, `→ IC-NNN §Section`); `dekspec ib context` delivers it byte-identical to each consumer by construction. Declare no dependency edge for a pin. The referenced home must be approved before consumers can be proposed (accept the pin-home IB first). `IB-NNN §O-n` resolves a one-line local obligation; a multi-line shape belongs in an IC or WS section.
3. **Foundation IB** — the exception: ≥ 2 real dependents, types only and no logic, reviewable on its own.

Do not absorb a shared type into whichever slice needs it first — that is a hidden sequencing edge; declare `**Depends on:**` if you mean one. Dependencies form a DAG.

**Deep-module pass (Constitution Article 4 / ADR-036).** Where an IB exposes an interface to other IBs, design it for depth: fewer operations, simpler parameters, complexity hidden inside, dependencies injected rather than constructed, operation-specific signatures rather than a generic conduit — so the boundary is mockable and dependents stay testable without this IB.

### Write each IB

Scaffold with `dekspec ib new <slug> --title "<title>"` (add `--parent INT-NNN` or `--parent WS-NNN`); it allocates the next IB id, writes the template with `**Authority policy:** delegated` at DRAFT, and logs the creation. Then fill:

- **Outcome** — the observable state when the IB is complete, not a task list.
- **Rationale** — enough for a reviewer to judge the change without a parent; with a parent, reference it instead of restating it.
- **Scope** — globs where changes are allowed without further permission, each resolving to real paths; plus **Out of scope** for what a reasonable engineer might assume is included.
- **Obligations** — references to the canonical homes, with a short applicability note only when the reference alone does not say how it applies. `(local)` only for obligations this IB owns. List the obligations that actually bind this change, not every ADR in the neighbourhood.
- **Protected Surfaces** — what must not change even inside Scope (`path::symbol` for one Python function or class), each with the reason.
- **Acceptance** — the YAML block. Each condition names exactly one verification: `pytest` nodes, a `command` that exits 0 only when the behavior holds, or a `review` judgment. Cover the **observable** behavior, the **integrated** behavior through the real entry point, and the **failure** behavior (missing, invalid, unavailable input). Conditions must be demonstrable, not "works correctly". Name the test nodes the conditions need even though the tests do not exist yet — `/write-tests` writes them next, before authorization (they are mandatory, never left to the builder); list other fixtures or golden data as protected assets. A `command:` condition's `condition` text is its expectation basis (ADR-062): state what the command checks and why that result shows the behavior; a pass criterion the change itself controls (a string it prints, a count it computes) is not independent. For numerical or data transformations, pin exact input/output examples supplied by the engineer or a reference implementation — never invent them.
- **Implementation Hypothesis** — likely files, approach and reuse, explicitly revisable. Nothing here binds; if something must bind, it is an obligation or a protected surface.
- **Environment Prerequisites** — live services or tools with a probe command; `dekspec ib start` blocks truthfully when a required probe fails.
- **Header** — `**Depends on:**` (IB ids, or none), `**Spec impact:**` (the ADR / IC / WS / AE / SP ids the delivery must update when architecture or contracts change, else none), `**Parent:**`.

When two binding sources contradict each other, or a source contradicts the code in a way the IB cannot settle, stop and put the question to the engineer; record the resolution in the canonical home (ADR / IC / WS), not in the IB.

### Check and save

1. `dekspec ib lint IB-NNN` must pass (contract problems + reference resolution); `dekspec validate <path>` must report no errors.
2. Across the set: no two IBs change the same function without a dependency between them; every shared shape has exactly one home and every consumer references it; the dependency graph is acyclic; with an Intent parent, every Scope lies inside `Components affected:`.
3. For each IB whose lint is clean and whose references resolve to sources eligible under `specification.reference_mode`, request the decision: `dekspec ib propose IB-NNN` (DRAFT → PROPOSED). A PROPOSED ADR or AE can be referenced under the explicit `evolving` project policy without promoting it. Other ineligible sources must be resolved before proposal; IB acceptance remains a separate authorization.
4. Report per IB: id, Outcome, Parent, obligations referenced, acceptance conditions (observable / integration / failure), dependencies, lint result, status. Then name what only the engineer can judge — whether the acceptance conditions capture the right behaviors, the protected surfaces and Out of scope match intent, and any engineer-supplied values are correct — and point at `--accept`.

## Audit Mode

_Plays the **`auditor`** role — run `dekspec resource role auditor` first and follow it: deterministic `dekspec validate` / `dekspec audit` output is primary evidence; report findings, change nothing._

Read-only; writes nothing. For each IB (path or glob):

1. `dekspec ib lint IB-NNN` and `dekspec validate <path>`; report every problem.
2. A `legacy` IB: report "legacy authority policy — adopt with `/write-ibs --adopt`" and the legacy-shape findings only; do not grade it against the delegated contract.
3. Authoring checks: obligations reference their homes and restate nothing (flag any ADR / IC / WS text pasted into the IB); `(local)` used only for IB-owned obligations; each acceptance condition names one verification and the set covers observable, integration and failure behavior; Scope globs resolve and Protected Surfaces exist; the hypothesis contains nothing that must bind; `**Spec impact:**` is named when the change alters architecture or a contract; `**Parent:**` resolves if set.
4. Cross-IB checks over IBs sharing a Parent: shared shapes have one home; no overlapping Scope on the same function without a dependency; the dependency graph is acyclic.
5. For an ACCEPTED IB, `dekspec ib status IB-NNN` shows whether the contract changed since the baseline (a change without `ib baseline` / `ib amend` fails verification).

Report findings by severity with the remedial mode (`--revise`, `--resync`, `--adopt`).

## Review Mode

Walk the IB's unchecked `## Open Issues` with the engineer, one at a time: present the issue, check whether it is still valid against the current IB and its referenced sources, recommend resolve / revise / defer / dismiss, apply the engineer's choice (resolution or dismissal note with today's date). If there are none, say so.

**Spec-reviewer dispatch** — run the shared spec-reviewer dispatch in [`_lib/agent_roles.md`](../_lib/agent_roles.md) §Spec-reviewer dispatch for this IB alongside the open-issue walk: `dekspec resource role spec-reviewer`, one fresh-context sub-agent composed policy → role → procedure → assignment, and its findings presented at their severity (default P2) with the open issues. If it did not run, say so — never present your own review as the spec-reviewer's.

For an adversarial pre-authorization review of the contract and the oracle review of its acceptance tests (ADR-062), `/dekspec:review-ib` is the dedicated skill. If body changes were made, re-run Audit Mode and apply the Revise Mode re-authorization rules.

## Revise Mode

Arguments: the IB path, then notes (inline, or a `.md` / `.txt` path). Classify each note:

- **Hypothesis** — files, approach, sequencing. Edit freely at any status; it is not part of the contract hash.
- **Contract** — Outcome, Scope, Obligations, Protected Surfaces, Acceptance, assets, Depends on, Spec impact.
- **Structural** — split, merge, re-cut, new IB. Exit Revise Mode and route to Create / Decompose; Revise changes one existing IB.
- **Rejection** — the IB rests on a wrong premise. Stop and ask.

Present the classified plan, wait for approval, apply it, log new ambiguity as `## Open Issues` (**Source:** review), then re-run Audit Mode. A contract change needs re-authorization, by status:

- **DRAFT / PROPOSED** — edit; re-run `dekspec ib lint`. A contract or test change moves the floor digest, so the oracle review (`/dekspec:review-ib`) is repeated before `dekspec ib accept`.
- **ACCEPTED, run not started** — after the edit, repeat the oracle review of the changed tests (`/dekspec:review-ib`, a new `Floor reviewed:` row naming the new floor digest), then `dekspec ib baseline IB-NNN --reason "<why>"` refreshes the acceptance baseline (the authorizer's action).
- **ACCEPTED, run started** — only `dekspec ib amend IB-NNN --reviewer <independent reviewer> --reason "<why>"` changes the contract or acceptance assets (ADR-057); the completing review verdict must acknowledge the amendment. Never weaken an acceptance condition to make a run pass.
- **COMPLETE / SUPERSEDED / DEPRECATED** — do not revise; author a new IB.

## Resync Mode

IBs hold references, not copies, so an upstream edit reaches them at the next `dekspec ib context` with no resync (and makes prior evidence stale automatically). This mode repairs references that no longer resolve. For each IB: run `dekspec ib lint IB-NNN`; for each reference problem — a superseded or deprecated source, a missing section, a source disallowed by the project reference policy — propose the repair (repoint to the successor, fix the section name, or wait for approval) and apply it with the engineer's confirmation. A repointed obligation is a contract change: apply the Revise Mode re-authorization rules. Never paste the source text into the IB to make a reference go away.

## Accept Mode

Authorization is the engineer's decision (ADR-057); passing `--accept` after the audit report is that decision.

1. Resolve the target(s); run Audit Mode on each. Refuse any IB with a lint problem, an unresolved `P1` open issue, or an unresolved reference — and, for an IB with `pytest:` conditions or declared assets, any IB whose acceptance tests are not written (`/dekspec:write-tests`) or whose current floor digest (`dekspec ib floor IB-NNN`) no `Floor reviewed:` row in its Amendment Log names (run `/dekspec:review-ib` first; ADR-062).
2. Present the plan (ready / blocked / already ACCEPTED) and wait for an explicit yes.
3. For each ready IB: `dekspec ib propose IB-NNN` if it is still DRAFT, then `dekspec ib accept IB-NNN`. Accept writes ACCEPTED and records the acceptance baseline — the contract hash, the acceptance assets named by the conditions (the reviewed tests, `Basis:` lines included) and the runner inputs. Surface stderr on refusal and skip that IB. Pass `--actor <identity>` (or set `DEKSPEC_ACTOR`) when the engineer is not the git user.
4. Report the next steps: execution picks up from `dekspec ib ready` (or `/dekspec:implement`). Any pre-start change to the acceptance tests repeats the oracle review (a new `Floor reviewed:` row) before `dekspec ib baseline IB-NNN --reason "…"` re-protects them.

## Adopt Mode (legacy IBs)

A legacy IB keeps the ADR-049 meaning until it is adopted deliberately — never by bulk relabeling (ADR-055). Arguments: the legacy IB path.

1. Read the IB, its Governing ADRs, referenced ICs and its WS. Confirm `**Authority policy:** legacy` (or no line).
2. **Classify each `## Constraints & Decisions` entry, one by one**, and record the decision:
   - **Binding obligation** whose canonical home exists → an `O-n` reference to that home (`→ ADR-NNN`, `→ IC-NNN §Section`, `→ WS-NNN §Section`).
   - **Binding obligation** owned by this IB alone → an `O-n (local)` obligation.
   - **Implementation hypothesis** (file choices, sequencing, algorithm preferences not required by a contract) → `## Implementation Hypothesis`.
   - **Obsolete / duplicated** → dropped, with the reason.
   Record the table (legacy entry → disposition) in an `## Adoption` section of the IB; present each classification to the engineer, who confirms or corrects it. An entry you cannot classify is an open question, not a default.
3. Convert `## Files to Modify` into `## Scope` globs (the legitimate change area, not just the guessed files) plus hypothesis entries; `## Do Not Touch` into `## Protected Surfaces`; `## Done When` into the `## Acceptance` YAML (observable, integration and failure conditions, each with one verification). Add Outcome and Rationale.
4. Replace the legacy sections with the new ones and set `**Authority policy:** delegated`. Run `dekspec ib lint IB-NNN` until clean.
5. Record the switch: for a PROPOSED or ACCEPTED IB, `dekspec ib adopt IB-NNN --reason "<summary of the classification>"` (writes the Amendment Log row and, for ACCEPTED, the adoption baseline; run it as the author or authorizer, not as one of the run's builders — it is refused for a builder, for an IB never committed as legacy, and once a delegated baseline exists). A DRAFT IB needs no engine step — add an Amendment Log row and proceed to `dekspec ib propose`.
6. If the IB had legacy code beads, `dekspec ib import-beads IB-NNN` moves them into its execution record as tasks (owner, status, dependencies and closure evidence preserved).

## Dry-Run Mode

For a WS or Intent path: investigate lightly and list the candidate IBs — title, Outcome in one line, likely Scope, dependencies, where each shared shape would live — plus any cut that looks wrong (unrelated outcomes in one IB, one rule split across several, cycles). Write nothing. Offer to proceed with Create / Decompose.

## Provisional Mode

`--provisional <incubation-slug>` authors into `dekspec/provisional/<incubation-slug>/` instead of `dekspec/impl-briefs/`. Scaffold with `dekspec library new-provisional IB <slug> --title "<title>" [--no-branch]` (surface stderr on failure), then fill the skeleton with this skill's Create discipline; the PROVISIONAL banner stays. A provisional IB cannot be proposed or accepted — hand-promote it first (see `docs/dekspec-operating-guide.md` §Provisional Promotion), then `--accept`. Close by reporting the provisional path, the branch if one was created, and the promotion step.

## Write-Time CoW Guard (INT-082 phase 4)

See [`_lib/cow_write_guard.md`](../_lib/cow_write_guard.md) for the canonical contract.

**Form:** kind-dir — canonical artifacts under `dekspec/<kind-dir>/`.

## Rules

- **Log corrections.** When any mode corrects a domain misinterpretation — wrong term usage, confused concepts, contradicted architectural facts — invoke `/write-corrections --log` with the correction details before proceeding. This feeds the glossary promotion pipeline.
- **Reference, never copy.** Obligations point at their canonical home; the generated context carries the text. A copied obligation is a second authority that drifts.
- **The hypothesis never binds.** If a file restriction, algorithm or sequence must hold, state it as an obligation or protected surface with its reason.
- **Acceptance is the contract's teeth.** Every condition is demonstrable by its named verification, and the set covers failure and integration, not only the happy path.
- **Status changes go through the engine.** `dekspec ib propose` / `ib accept` / `ib complete` write IB statuses; never hand-edit them (`artifact_ops.py transition` refuses IB → COMPLETE).
- **Location.** New IBs live in `dekspec/impl-briefs/` (where `dekspec ib new` writes them). A repository that keeps status folders keeps them aligned with the live statuses: `queued/` = DRAFT / PROPOSED, `active/` = ACCEPTED, `completed/` = COMPLETE.

## Common Pitfalls

- Pasting ADR, IC or WS text into an IB "so the agent has it" — reference it; `dekspec ib context` delivers it with its revision.
- Writing the implementation plan as obligations — file lists and sequencing are hypothesis; the agent revises them after investigating.
- Acceptance that only exercises the happy path, or conditions like "works correctly" — add integration and failure conditions with a concrete verification each.
- Authoring an Intent, WS or Mission to justify a bounded change — one IB is enough (ADR-056).
- Pinning a shared shape into every consuming IB — pin it once and reference that home.
- Loosening an acceptance condition mid-run to get green — only `dekspec ib amend` with an independent reviewer changes acceptance after execution starts.
- Inventing golden values for numerical transformations — ask the engineer or use a reference implementation.

## Verification Checklist

- [ ] Every IB is `**Authority policy:** delegated`, passes `dekspec ib lint`, and validates.
- [ ] Obligations are references (or `(local)` for IB-owned ones); nothing is copied from an ADR, IC or WS.
- [ ] Acceptance covers observable, integration and failure behavior; each condition names exactly one verification.
- [ ] Scope, Protected Surfaces and Out of scope are explicit; the hypothesis binds nothing.
- [ ] `**Spec impact:**` names the specs a change to architecture or contracts must update.
- [ ] Shared shapes have one home; dependencies form a DAG; Intent-parented Scopes lie inside `Components affected:`.
- [ ] Statuses were written only by `dekspec ib propose` / `ib accept` (or `ib adopt` for adoption).
- [ ] `dekspec relink` ran as the closing step.

## Closing Step

**Mandatory closing step for every mode that writes or revises an IB** (Create / Decompose, `--revise`, `--resync`, `--accept`, `--adopt`, `--review` with edits). After the files are saved, run:

```
dekspec relink
```

against the repo root. It re-derives the cross-artifact `Linked Artifacts` backlinks from the forward links the artifacts declare. It is the last thing the skill does before reporting back.
