---
name: write-intent
description: "Use to create or operate on a single Intent (INT-NNN) — a committed outcome that spans several Implementation Briefs, captured as a file with its outcome test. Trigger when the engineer wants to: author/capture a committed direction or planned change as an Intent before starting; decompose an Intent into IBs; amend it to change scope, components, or globs; accept, analyze, review, or audit it; complete it (the `--lock` flag, retained for compatibility, runs `dekspec intent complete` once its IBs are complete — ADR-057), sync post-completion, or supersede it. Phrases like \"author the intent for this\", \"decompose INT-x\", \"amend INT-x to add...\", \"complete INT-x now its IBs are done\", or \"capture this as a committed direction\" all apply — even when stated in plain language without flags. This handles ONE Intent operation or transition. Driving an Intent through specification belongs to spec-intent, and implementing a ready Intent end to end belongs to implement. A bounded change that fits one IB needs no Intent (ADR-056) — use /write-ibs."
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--canonical] [--provisional <slug>] [--help | --teaching | --audit | --review | --analyze | --accept | --approve | --decompose | --lock | --sync | --supersede [--by <INT-NNN|MSN-NNN>] | --amend [--editorial]] [description or path to Intent]
related_skills: [spec-intent, implement, write-ws, write-ibs, write-mission]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

> **When an Intent applies (ADR-056).** An Intent is optional. Use it when an outcome spans several IBs and needs its own outcome test (ADR-029) and components scope. A bounded change is one IB with its own outcome, rationale and acceptance — author it with `/write-ibs` (or `dekspec ib new <slug>`) and skip the Intent.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill writes a contract about a future change. Prior conversation context can degrade quality by anchoring on implementation details before the Intent's scope is set.
>
> First message → proceed. Prior history → ask "context may affect Intent quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-intent The attachment pipeline must reject any upload whose declared MIME type disagrees with its sniffed magic bytes.

Author a new Intent for this. It touches the upload validator and the attachment store; link it to the AE that owns ingest. I want a DRAFT out of this run.
```

## Lifecycle (ADR-057)

`DRAFT` → `PROPOSED` → `ACCEPTED` → `COMPLETE`, plus `SUPERSEDED`. Statuses record decisions only: PROPOSED requests one, ACCEPTED authorizes the outcome, COMPLETE is recorded by `dekspec intent complete` when every child IB (an IB whose `**Parent:**` is this Intent) is COMPLETE and the Intent's Verification has current passing evidence. Progress lives in the child IBs' execution records. OVERSIZED, IMPLEMENTING, TESTPASS and MERGED are retired: an over-cap analysis is a P2 open issue, not a status; `dekspec migrate` maps legacy files.

## Session-Start Reminder (Provisional Awareness)

When entering Creation Mode or Analyze Mode on an Intent that is **pre-ACCEPTED** (DRAFT or PROPOSED status), or when authoring a new Intent, surface this one-line banner before the first substantive action:

> 📝 While this Intent remains pre-ACCEPTED (DRAFT/PROPOSED), every change to canonical artifacts in its `Components affected` scope should be auto-staged to `dekspec/provisional/<incubation-slug>/` via a `replaces:` frontmatter stamp (the CoW spec staging discipline from INT-082). The canonical spec graph is frozen for those paths until you run `--accept`. Use `dekspec library new-provisional <KIND> <slug>` to stage a copy-on-write artifact. The `T-COW-CANONICAL-EDITED` audit rule (P2 mechanical) catches direct-edit bypasses of this guard.

Skip the banner in Lock / Sync / Audit / Review / Help / Teaching modes — those operate on already-settled artifacts and the CoW guard does not apply.

**Roles (ADR-061).** This skill plays DekSpec's Agent Role Specifications; the engineer never selects one. Authoring, revise and resync modes play the **`specifier`** role, audit modes the **`auditor`** role: run `dekspec resource role specifier` or `dekspec resource role auditor` at the start of the mode and follow it (a delegated `*-author` agent loads `specifier` itself). See [`_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) §The role each universal mode plays and [`_lib/agent_roles.md`](../_lib/agent_roles.md).

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Creation Mode**.

Parse `$ARGUMENTS` for the mode flag, then **load the corresponding per-mode body from `modes/<slug>.md`** (Mode Index lazy load — INT-087). Only the chosen mode's body is read into the working context.

- **Help mode** — `--help` flag. Load [`modes/help.md`](modes/help.md).
- **Teaching mode** — `--teaching` flag. Load [`modes/teaching.md`](modes/teaching.md).
- **Analyze mode** — `--analyze` flag, expects a path to an existing Intent in DRAFT. Load [`modes/analyze.md`](modes/analyze.md).
- **Accept mode** — `--accept` flag, expects a path to an existing Intent in PROPOSED. Load [`modes/accept.md`](modes/accept.md).
- **Approve mode** — `--approve` flag, expects a path to an existing Intent file. Load [`modes/approve.md`](modes/approve.md).
- **Decompose mode** — `--decompose` flag, expects a path to an Intent in ACCEPTED. Load [`modes/decompose.md`](modes/decompose.md).
- **Lock mode** — `--lock` flag (retained name; it completes the Intent), expects a path to an Intent in ACCEPTED whose child IBs are COMPLETE. Load [`modes/lock.md`](modes/lock.md).
- **Sync mode** — `--sync` flag, expects a path to an Intent in COMPLETE (post-completion cleanup). Load [`modes/sync.md`](modes/sync.md).
- **Supersede mode** — `--supersede` flag (+ `--by <INT-NNN|MSN-NNN>`), expects a path to a not-yet-complete Intent (DRAFT / PROPOSED / ACCEPTED) absorbed by a named successor artifact (ADR-035). Load [`modes/supersede.md`](modes/supersede.md).
- **Audit mode** — `--audit` flag, expects a path to an Intent in any status but SUPERSEDED. Load [`modes/audit.md`](modes/audit.md).
- **Review mode** — `--review` flag, expects a path to an Intent in DRAFT, PROPOSED, or ACCEPTED. Load [`modes/review.md`](modes/review.md).
- **Amend mode** — `--amend` flag, expects a path to an Intent in DRAFT, PROPOSED, or ACCEPTED. Load [`modes/amend.md`](modes/amend.md).
- **Provisional mode** — `--provisional <slug>` flag (composes with other modes). Load [`modes/provisional.md`](modes/provisional.md) in addition to the chosen mode body.
- **Fan-Out mode** — internal orchestrator dispatch for substantive-work modes (Creation, `--analyze`, `--accept`). Load [`modes/fan-out.md`](modes/fan-out.md) when dispatching a substantive-work mode to a fresh-context subagent.
- **Creation mode** — no flag. Load [`modes/create.md`](modes/create.md). **Defaults to provisional** (ADR-030 hard default): with no opt-out the new Intent lands under `dekspec/provisional/` and no canonical id is allocated. Passing **`--canonical`** opts into canonical-direct authoring (lands in `dekspec/intents/`, allocates an `INT-NNN` id). The routing authority is the `dekspec library author-target --kind INT [--canonical]` verb — create.md calls it rather than hardcoding the directory.

The former `--testpass` mode is retired (ADR-057): the Verification block is executed by `dekspec intent verify`, and per-IB scope confinement by `dekspec ib verify`.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--analyze`, `--accept`
- Inline (parent context): `--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--sync`, `--supersede`, `--amend`, `--decompose`, `--approve`

## Interview Rigor (default-on)

This skill **optionally composes the [`interview-me`](../../../dektools/tools/interview-me/SKILL.md) tool** (INT-167 / D13), which ships in the **DekTools** plugin (ADR-047). It does not re-author the interview prose, and there is no `--grill` flag. When the engineer's input is fuzzy or underspecified and the tool is available, invoke `/interview-me <INT-NNN | description>` so the engineer is interviewed one decision-tree question at a time, with a recommended answer per question, repo-exploration for discoverable answers, glossary + governing ADR/AE citation with conflict-flagging, fuzzy-term sharpening, and scenario-based stress-testing of asserted relationships.

**Degrade gracefully when it is absent.** DekTools may not be installed, or `interview-me` may not be enabled in its à-la-carte selection. Core is self-sufficient by design (ADR-047), so this is a supported configuration, not an error: fall back to asking the engineer the same decisions inline, one at a time, and continue. Never block authoring on a toolkit tool, and never report its absence as a failure.

**Trigger (pinned, INT-167 Open Issues):**

- **Auto-engages** in **Creation** (no-flag) and **`--analyze`** modes when the input is fuzzy/underspecified.
- **Auto-skips** on **`--amend --editorial`** (editorial) and trivial passes — these are not fuzzy-input authoring.
- **Escape:** the `--no-interview` modifier skips the interview on demand even on a fuzzy Creation/analyze pass.

At interview end, read the hand-off log `dekspec/.scratch/interview-me/<artifact-id>.md` and fold its resolved decisions into the Intent being authored. `interview-me` never writes the artifact itself — the host skill (this one) folds the decisions in.

## Mode Index

| Mode | Flag | File | One-liner |
|---|---|---|---|
| Creation | (no flag) | [modes/create.md](modes/create.md) | Author a new Intent from the engineer's description; writes DRAFT. |
| Analyze | `--analyze` | [modes/analyze.md](modes/analyze.md) | Coverage + archaeology + size assessment + drift. DRAFT → PROPOSED; an over-cap result is a P2 open issue and Status stays DRAFT. |
| Accept | `--accept` | [modes/accept.md](modes/accept.md) | Engineer-only gate. PROPOSED → ACCEPTED. Re-runs linkage/shape/drift before promotion. |
| Decompose | `--decompose` | [modes/decompose.md](modes/decompose.md) | Author the child IBs (`**Parent:** INT-NNN`, delegated) via `/write-ibs`. Status stays ACCEPTED. |
| Complete | `--lock` | [modes/lock.md](modes/lock.md) | `dekspec intent verify` + `dekspec intent complete`: ACCEPTED → COMPLETE on child-IB completion and current outcome evidence. |
| Sync | `--sync` | [modes/sync.md](modes/sync.md) | Post-completion cleanup walkthrough — mark checklist items, surface new ones, apply small edits. |
| Supersede | `--supersede` (+ `--by <INT-NNN\|MSN-NNN>`) | [modes/supersede.md](modes/supersede.md) | Not-yet-complete Intent absorbed by a named successor → SUPERSEDED + index Archive move (ADR-035). |
| Audit | `--audit` | [modes/audit.md](modes/audit.md) | Read-only health check — every check the lifecycle modes enforce, mutates nothing. |
| Review | `--review` | [modes/review.md](modes/review.md) | Interactive section-by-section walkthrough; engineer applies/declines edits per section. |
| Amend | `--amend` (+ optional `--editorial`) | [modes/amend.md](modes/amend.md) | Structured substantive change with invariant re-check + Status cascade. With `--editorial`: appends a `Type=editorial` Amendment Log row, refuses on behavioral-field diffs, does NOT cascade Status (INT-088 IU-1). |
| Approve | `--approve` | [modes/approve.md](modes/approve.md) | Record a peer-review approval signature in the Amendment Log (team profile, INT-021). |
| Help | `--help` | [modes/help.md](modes/help.md) | Render the USAGE / MODES / EXAMPLES block and stop. |
| Teaching | `--teaching` | [modes/teaching.md](modes/teaching.md) | Interactive tutorial walking a new author through writing an Intent section-by-section. |
| Provisional | `--provisional <slug>` | [modes/provisional.md](modes/provisional.md) | Redirect authoring into `dekspec/provisional/<slug>/` until the hand-promote workflow runs. |
| Fan-Out (internal) | — | [modes/fan-out.md](modes/fan-out.md) | Orchestrator/subagent dispatch contract for substantive-work modes (Creation, `--analyze`, `--accept`). |

**Dispatcher contract.** After parsing the mode flag in Mode Detection above, read the corresponding `modes/<slug>.md` file with the `Read` tool and follow its body as the active mode contract. The shared scaffolding below (Write-Time CoW Guard, Rules, Output, Closing Step) runs across every substantive-mode invocation regardless of which per-mode body is loaded.

## Teaching Mode

> **Index-stub.** When the engineer passes `--teaching`, the active mode body lives in [`modes/teaching.md`](modes/teaching.md). This stub satisfies the `test_skills_dispatcher.py::test_skill_has_teaching_mode_section` literal-presence check for `## Teaching Mode` in SKILL.md (per ds-int-007 / INT-008). Per-mode lazy-load (INT-087) keeps the per-mode body as the source of truth.

## Approve Mode

> **Index-stub.** When the engineer passes `--approve`, the active mode body lives in [`modes/approve.md`](modes/approve.md). This stub satisfies the `test_skill_approve_modes.py::test_skill_has_approve_mode_section` literal-token presence check for `## Approve Mode`, the `artifact_ops.py approve` helper reference, and the `review-approval` row name in SKILL.md.

`--approve` records a peer-review approval signature on an Intent under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the Intent's `## Amendment Log` table — it does **not** flip Status. Run the shared deterministic helper `python ../_lib/scripts/artifact_ops.py approve <Intent-path> --target-status <STATUS>` (see [`modes/approve.md`](modes/approve.md) for the full contract).

## Help Mode

> **Index-stub.** When the engineer passes `--help`, the active mode body lives in [`modes/help.md`](modes/help.md). The manifest below is duplicated here so that the `T-SKILL-HELP-MODE-PRESENT` audit rule (a mechanical check that reads only `SKILL.md`) sees the canonical YAML keys (`skill_name`, `one_line`, `modes`, `examples`) plus the `_lib/help_mode_template.md` citation.

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-intent"
one_line:   "Author, analyze, accept, decompose into IBs, or complete an Intent"
modes:
  - { flag: "", args: "<description>", description: "Creation mode — see modes/create.md." }
  - { flag: "--analyze", args: "<Intent-path>", description: "Analyze mode — see modes/analyze.md." }
  - { flag: "--accept", args: "<Intent-path>", description: "Accept mode — see modes/accept.md." }
  - { flag: "--decompose", args: "<Intent-path>", description: "Decompose mode — see modes/decompose.md." }
  - { flag: "--lock", args: "<Intent-path>", description: "Complete mode (dekspec intent complete) — see modes/lock.md." }
  - { flag: "--sync", args: "<Intent-path>", description: "Sync mode — see modes/sync.md." }
  - { flag: "--supersede", args: "<Intent-path> --by <INT-NNN|MSN-NNN>", description: "Supersede mode — not-yet-complete Intent absorbed by a named successor → SUPERSEDED (ADR-035). See modes/supersede.md." }
  - { flag: "--audit", args: "<Intent-path>", description: "Audit mode — see modes/audit.md." }
  - { flag: "--review", args: "<Intent-path>", description: "Review mode — see modes/review.md." }
  - { flag: "--amend", args: "<Intent-path>", description: "Amend mode — see modes/amend.md." }
  - { flag: "--amend --editorial", args: "<Intent-path>", description: "Editorial-only amend — append a Type=editorial Amendment Log row; refuses on behavioral-field diffs (Verification / Components affected / Acceptance Criteria / Layer impact analysis); does NOT cascade Status. INT-088 IU-1." }
  - { flag: "--approve", args: "<Intent-path>", description: "Approve mode — see modes/approve.md." }
  - { flag: "--teaching", args: "", description: "Teaching mode — see modes/teaching.md." }
  - { flag: "--provisional", args: "<slug>", description: "Provisional mode — see modes/provisional.md." }
  - { flag: "--help", args: "", description: "Show this help message (load modes/help.md for full per-mode descriptions)." }
examples:
  - "/write-intent --help"
  - "/write-intent --analyze dekspec/intents/INT-005-attachment-mime-coverage.md"
```

At runtime when `--help` is the active flag, load [`modes/help.md`](modes/help.md) for the full descriptions and render per `_lib/help_mode_template.md`.

## Write-Time CoW Guard (INT-082 phase 4)

See [`_lib/cow_write_guard.md`](../_lib/cow_write_guard.md) for the canonical contract.

**Form:** kind-dir — canonical artifacts under `dekspec/<kind-dir>/`.

## Rules

- **Files canonical (Decision D2 / v5 §21).** Intents live as markdown files at `dekspec/intents/INT-NNN-<slug>.md`. External trackers may *seed* and may *mirror* — but the file is canonical. Never write Intent content anywhere except the file.
- **Capture is human-initiated (Decision D3 / v5 §22).** This skill is invoked by an engineer running `/write-intent`. Webhook-driven creation from a tracker is forbidden. The optional `source:` field records provenance only.
- **Serialization (ADR-016).** Per-Mission and advisory. At most one active child Intent per Mission is the intended discipline; across Missions and for Mission-less Intents there is no limit. Creation is never refused on serialization grounds — the gate of record is `dekspec audit linkage`.
- **Type drives shape.** The Intent's `type:` field selects the required block, the default Verification predicate, and the validation rules. Do not silently switch type — if the engineer's intent re-shapes mid-draft, surface and ask.
- **No template placeholders in DRAFT.** Every template section that is required at this stage must be populated with real content. `<reproduction-test-path-from-IB-1>` is the one allowed verbatim placeholder, and only inside the bug-type Verification block; `--decompose` resolves it.
- **D19 / D20 are hard.** Measurable targets and decision rationale do not belong in an Intent. Move them to WS / ADR. The skill refuses to advance state until each finding is resolved.
- **Linked Architecture Elements is mandatory (Decision D12).** Every Intent links to at least one existing AE. If the engineer cannot name one, that signals either the Intent is too small (make it one IB) or there is missing AE work — surface and stop.
- **One home per fact (ADR-056).** The Intent owns the outcome, its outcome test and the components scope. It does not restate ADR, IC or WS content, and it records no execution history: child IBs reference their obligations, and progress, attempts, failures and evidence live in execution records under `.dekspec/execution/`. The retired `## TESTFAIL records` section and bead rows in `Layer impact analysis` are not written for new work.
- **Log corrections.** When this skill corrects a domain misinterpretation in the engineer's input — wrong term, confused concept, contradicted architectural fact — invoke `/write-corrections --log` with the correction details before proceeding. Feeds the glossary promotion pipeline.
- **Components affected bounds the child IBs.** Each child IB's Scope globs should lie inside the Intent's `Components affected:`. Widening scope goes through `--amend` (which re-runs the size assessment), never by quietly authoring an IB outside it. Per-IB scope and protected surfaces are checked by `dekspec ib verify`.
- **Outcome verification shares one scoping altitude with the IB acceptance tests (INT-151).** When authoring an Intent's `outcome_verification` declaration (the single user-observable proof, per ADR-029), apply the same scoping altitude the `/write-tests` **scoping role-pass** applies to acceptance assertions: classify each pinned mechanism **REQUIRED / GIVEN / INCIDENTAL** and keep the outcome assertion as tight as the Intent's intent and no tighter. An `outcome_verification` test that pins an INCIDENTAL mechanism is over-specified — pin the user-observable behavior instead. This keeps the per-Intent `outcome_verification` and the per-IB acceptance conditions speaking one vocabulary, reinforcing `fence-durable` / `fence-golden-path` rather than introducing a second altitude language.
- **Completion is evidence-backed (ADR-057).** `--lock` completes the Intent only through `dekspec intent complete`: every child IB COMPLETE (each through `dekspec ib complete`) and a current passing `dekspec intent verify` run; manual Verification entries additionally need an independent `dekspec intent review` verdict. Never hand-edit Status to COMPLETE — `artifact_ops.py transition` refuses it.
- **`--audit` is strictly read-only.** Audit never mutates the Intent file, never transitions Status, never appends an Amendment Log entry. If a finding requires action, the audit output recommends the remedial mode (`--amend` for substantive, `--review` for editorial); the engineer must explicitly invoke it.
- **`--sync` is non-substantive only.** Sync handles post-completion cleanup against the existing `## Post-implementation sync` checklist plus newly-discovered tail items. It refuses to touch any file outside the original `Components affected:` globs + `dekspec/` content paths. Substantive changes route through `--amend`, never through `--sync`.
- **`--review` cannot promote Status.** Review is editorial — engineer-driven Q&A walkthrough. It never transitions PROPOSED → ACCEPTED (that's `--accept`'s job).
- **`--amend` cascades Status backwards on substantive change.** Amending a PROPOSED or ACCEPTED Intent reverts it to DRAFT (the Coverage Report, Size Assessment and acceptance no longer match); the engineer re-runs `--analyze`. An amendment that pushes the Intent over a cap records the P2 re-split open issue.
- **`--amend` refuses on terminal statuses.** COMPLETE and SUPERSEDED cannot be amended. A `COMPLETE` Intent that needs a *substantive* change spawns a successor Intent and marks the original `SUPERSEDED`. An *editorial* correction to a `COMPLETE` Intent (a stale `Components affected:` glob, a broken cross-reference) is a direct file edit + an Amendment-Log row — a `COMPLETE` Intent is a historical record, not a frozen decision (ADR-046).
- **An over-cap Intent never produces a SUPERSEDED shell** (governing decision: **ADR-028** — "Default oversized handling to PEEL-OFF; reserve SUPERSEDE for LOCKED override / deprecation"). An Intent that has not completed resolves an over-cap finding via one of two non-SUPERSEDE paths: **PEEL-OFF** (default when the Intent has a natural core slice — narrow the parent in place and scaffold the siblings under the same Mission; the parent keeps its identity, slot and history) or **CONVERT-TO-MISSION** (default when the scope is an umbrella over several capability surfaces — extract the substance into a new Mission, scaffold child Intents, delete the draft Intent file, no Archive row). The shared partition-shape decision tree lives in [`_lib/oversized_splitting.md`](../_lib/oversized_splitting.md); `/write-mission` has a `from-oversized: <INT-NNN-path>` Decision Gate entry for the CONVERT branch. SUPERSEDE is reserved for overriding or deprecating a finished (COMPLETE) Intent — ADR-028's LOCKED-override case — and for ADR-035 absorption by a named successor.

## Output

- `dekspec/intents/INT-NNN-<slug>.md` lifecycle transitions:
  - Creation: → DRAFT
  - `--analyze`: DRAFT → PROPOSED (clean); an over-cap result records a P2 "re-split before acceptance" open issue and Status stays DRAFT
  - `--accept`: PROPOSED → ACCEPTED
  - `--decompose`: Status holds at ACCEPTED; child IBs are authored with `**Parent:** INT-NNN`
  - `--lock`: ACCEPTED → COMPLETE, written by `dekspec intent complete`
  - `--sync`: COMPLETE (status hold) + Post-implementation sync checklist edits
  - `--audit`: read-only; no Status mutation
  - `--review`: status hold; editorial edits applied during walkthrough
  - `--amend`: substantive change with Status cascade backwards (PROPOSED → DRAFT, ACCEPTED → DRAFT)
- Updated `dekspec/intent-index.md` per state transition (Active queue ↔ Archive)
- Child IBs produced by `--decompose` (`/write-ibs` does the writing)
- Amendment Log entries on Accept, Decompose, Complete, Sync (editorial), Review (editorial), Amend (substantive). Audit writes nothing.
- Outcome evidence and verdicts in the Intent's execution record (`.dekspec/execution/INT-NNN/`), never in the Intent body
- Mission Intent queue append on `--lock` if `mission:` is set and the Mission file exists
- Post-implementation sync checklist updates on `--sync` (mark `[x]` items + new `[ ]` bullets discovered)
- Audit findings printed to stdout on `--audit`; exit code 0/1 based on CRITICAL findings

## Common Pitfalls

- **Don't author an Intent for a change one IB can carry.** No mandatory chain (ADR-056): an Intent that would decompose into a single IB adds a parent with nothing distinct to say — author the IB directly.
- **Don't bake measurable targets or decision rationale into the Intent — route them to WS / ADR.** D19/D20 are hard refusals.
- **Don't author a new `/write-intent` to make a substantive change to a `COMPLETE` Intent unless you actually mean to supersede it.** Editorial fixes are a direct edit + an Amendment-Log row; genuine behavioral change spawns a successor Intent and marks the original `SUPERSEDED`.
- **Don't treat an over-cap finding as a SUPERSEDE case.** It resolves via PEEL-OFF or CONVERT-TO-MISSION per ADR-028.
- **Don't advance an Intent that names zero existing AEs (D12).** Surface and stop rather than fabricating a link.
- **Don't copy obligations or history into the Intent.** Child IBs reference ADR/IC/WS obligations; test outcomes and progress stay in execution records.
- **Don't edit a canonical artifact claimed by a pre-ACCEPTED Intent directly — stage copy-on-write first.** Run `dekspec library cow-stage <path>` before any canonical `Edit`/`Write`; skipping it trips the `T-COW-CANONICAL-EDITED` advisory.

## Verification Checklist

- [ ] The active mode was detected from `$ARGUMENTS` and the matching `modes/<slug>.md` body was loaded and followed (default: Creation).
- [ ] No template placeholders remain in a DRAFT (the bug-type `<reproduction-test-path-from-IB-1>` is the only allowed verbatim placeholder).
- [ ] The Intent links at least one existing AE (D12), and no D19/D20 finding (measurable target / decision rationale) is left unresolved.
- [ ] Any canonical-file write was preceded by a `dekspec library cow-stage` check, and edits to a claimed path were redirected to the provisional sibling.
- [ ] The Status transition recorded matches the mode's contract (e.g. `--accept` PROPOSED → ACCEPTED; `--decompose` held ACCEPTED; COMPLETE written only by `dekspec intent complete`; `--audit` mutated nothing).
- [ ] The required Amendment Log entry was appended for mutating modes, and `--audit` wrote nothing.
- [ ] Any domain misinterpretation corrected during the run was logged via `/write-corrections --log` before proceeding.
- [ ] `dekspec relink` was run against the repo root as the final action of every substantive mode.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise an Intent — Creation, `--analyze`, `--accept`, `--decompose`, `--lock`, `--sync`, `--review`, `--amend`). After the artifact file is saved and any index update is done, run:

```
dekspec relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it. `dekspec relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
