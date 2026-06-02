---
name: write-intent
description: Author, analyze, accept, decompose, testpass, lock, unlock, sync, audit, review, or amend an Intent (INT-NNN) — a single LOCKable, machine-verifiable unit of cross-component work. Use when the engineer has a committed direction the system intends to land. Phase 1 (Parts A + B) + Phase 3 flags (--sync / --audit / --review / --amend) all implemented.
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--canonical] [--provisional <slug>] [--help | --teaching | --audit | --review | --analyze | --accept | --approve | --decompose | --testpass | --lock | --unlock | --sync | --amend [--editorial] | --lite] [description or path to Intent]
related_skills: [orchestrate-intent, write-ws, write-ibs, write-beads, write-mission]
---

> **Vendored asset paths (INT-097):** Paths below like `dekspec/templates/X-template.md` and `dekspec/dekspec-<doc>.md` reference the consumer-vendored layout. If your install is pip-only (no `scripts/install-dekspec.sh` run), resolve any reference via `dekspec resource template X` or `dekspec resource doc <name>` (consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

> **Scope of this skill (Phase 1 + Phase 3 complete).** Phase 1: **(no flag)**, **`--analyze`**, **`--accept`** (Part A — v5 Prompt 4), and **`--decompose`**, **`--testpass`**, **`--lock`** (Part B — v5 Prompt 6). Phase 3: **`--sync`**, **`--audit`**, **`--review`**, **`--amend`** (P3.1–P3.4), plus **`--unlock`** — the `LOCKED → PROPOSED` editorial-correction precursor to `--lock`, pairing with it per the CLAUDE.md guardrail. All eleven flags are now implemented; Phase 4 (the autonomous orchestration brain) is **out of scope for this repo** — it lives in `dekfactory`. See `docs/architecture.md` §What does NOT live here.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill writes a contract about a future change. Prior conversation context can degrade quality by anchoring on implementation details before the Intent's scope is set.
>
> First message → proceed. Prior history → ask "context may affect Intent quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-intent The attachment pipeline must reject any upload whose declared MIME type disagrees with its sniffed magic bytes.

Author a new Intent for this. It touches the upload validator and the attachment store; link it to the AE that owns ingest. I want a DRAFT + branch out of this run.
```

## Session-Start Reminder (Provisional Awareness)

When entering Creation Mode or Analyze Mode on an Intent that is **pre-ACCEPTED** (DRAFT or PROPOSED status), or when authoring a new Intent, surface this one-line banner before the first substantive action:

> 📝 While this Intent remains pre-ACCEPTED (DRAFT/PROPOSED), every change to canonical artifacts in its `Components affected` scope should be auto-staged to `dekspec/provisional/<incubation-slug>/` via a `replaces:` frontmatter stamp (the CoW spec staging discipline from INT-082). The canonical spec graph is frozen for those paths until you run `--accept`. Use `dekspec library new-provisional <KIND> <slug>` to stage a copy-on-write artifact. The `T-COW-CANONICAL-EDITED` audit rule (P2 mechanical) catches direct-edit bypasses of this guard.

Skip the banner in Lock / Unlock / Sync / Audit / Review / Help / Teaching modes — those operate on already-locked artifacts and the CoW guard does not apply.

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Creation Mode**.

Parse `$ARGUMENTS` for the mode flag, then **load the corresponding per-mode body from `modes/<slug>.md`** (Mode Index lazy load — INT-087). Only the chosen mode's body is read into the working context; the other 15 mode files stay on disk.

- **Help mode** — `--help` flag. Load [`modes/help.md`](modes/help.md).
- **Teaching mode** — `--teaching` flag. Load [`modes/teaching.md`](modes/teaching.md).
- **Analyze mode** — `--analyze` flag, expects a path to an existing Intent file. Load [`modes/analyze.md`](modes/analyze.md).
- **Accept mode** — `--accept` flag, expects a path to an existing Intent file in PROPOSED. Load [`modes/accept.md`](modes/accept.md).
- **Approve mode** — `--approve` flag, expects a path to an existing Intent file. Load [`modes/approve.md`](modes/approve.md).
- **Decompose mode** — `--decompose` flag, expects a path to an Intent in ACCEPTED. Load [`modes/decompose.md`](modes/decompose.md).
- **Testpass mode** — `--testpass` flag, expects a path to an Intent in IMPLEMENTING. Load [`modes/testpass.md`](modes/testpass.md).
- **Lock mode** — `--lock` flag, expects a path to an Intent eligible for locking via either sufficient path (ADR-017). Load [`modes/lock.md`](modes/lock.md).
- **Unlock mode** — `--unlock` flag, expects a path to an Intent in LOCKED. Load [`modes/unlock.md`](modes/unlock.md).
- **Sync mode** — `--sync` flag, expects a path to an Intent in LOCKED. Load [`modes/sync.md`](modes/sync.md).
- **Audit mode** — `--audit` flag, expects a path to an Intent in any non-terminal status. Load [`modes/audit.md`](modes/audit.md).
- **Review mode** — `--review` flag, expects a path to an Intent in DRAFT, PROPOSED, or ACCEPTED. Load [`modes/review.md`](modes/review.md).
- **Amend mode** — `--amend` flag, expects a path to an Intent in any non-terminal status. Load [`modes/amend.md`](modes/amend.md).
- **Provisional mode** — `--provisional <slug>` flag (composes with other modes). Load [`modes/provisional.md`](modes/provisional.md) in addition to the chosen mode body.
- **Lite mode** — `--lite` flag, expects a path to an Intent in DRAFT (single-component, single-IU, no ADRs, no ICs). Load [`modes/lite.md`](modes/lite.md).
- **Fan-Out mode** — internal orchestrator dispatch for substantive-work modes (Creation, `--analyze`, `--accept`). Load [`modes/fan-out.md`](modes/fan-out.md) when dispatching a substantive-work mode to a fresh-context subagent.
- **Creation mode** — no flag. Load [`modes/create.md`](modes/create.md). **Defaults to provisional** (ADR-030 hard default): with no opt-out the new Intent lands under `dekspec/provisional/` and no canonical id is allocated. Passing **`--canonical`** opts into canonical-direct authoring (lands in `dekspec/intents/`, allocates an `INT-NNN` id). The routing authority is the `dekspec library author-target --kind INT [--canonical]` verb — create.md calls it rather than hardcoding the directory.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--analyze`, `--accept`
- Inline (parent context): `--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--unlock`, `--sync`, `--testpass`, `--amend`, `--decompose`, `--approve`, `--lite`

## Mode Index

| Mode | Flag | File | One-liner |
|---|---|---|---|
| Creation | (no flag) | [modes/create.md](modes/create.md) | Author a new Intent (INT-NNN) from the engineer's description; writes DRAFT + branch. |
| Analyze | `--analyze` | [modes/analyze.md](modes/analyze.md) | Top-down coverage + bottom-up archaeology + size assessment + drift. DRAFT → PROPOSED (or OVERSIZED). |
| Accept | `--accept` | [modes/accept.md](modes/accept.md) | Engineer-only gate. PROPOSED → ACCEPTED. Re-runs linkage/shape/drift before promotion. |
| Decompose | `--decompose` | [modes/decompose.md](modes/decompose.md) | Branch by IB-need (Decision #12); scaffolds IBs / beads. ACCEPTED → IMPLEMENTING. |
| Testpass | `--testpass` | [modes/testpass.md](modes/testpass.md) | Diff-confinement + Verification predicate eval. IMPLEMENTING → TESTPASS (or TESTFAIL records). |
| Lock | `--lock` | [modes/lock.md](modes/lock.md) | Promote to LOCKED via ADR-017 Path A (MERGED) or Path B (downstream WS/IC/IBs ≥ ACCEPTED). |
| Unlock | `--unlock` | [modes/unlock.md](modes/unlock.md) | Reason-gated LOCKED → PROPOSED for editorial corrections (precursor to a re-`--lock`). |
| Sync | `--sync` | [modes/sync.md](modes/sync.md) | Post-merge cleanup walkthrough — mark checklist items, surface new ones, apply small edits. |
| Audit | `--audit` | [modes/audit.md](modes/audit.md) | Read-only health check — every check the lifecycle modes enforce, mutates nothing. |
| Review | `--review` | [modes/review.md](modes/review.md) | Interactive section-by-section walkthrough; engineer applies/declines edits per section. |
| Amend | `--amend` (+ optional `--editorial`) | [modes/amend.md](modes/amend.md) | Structured mid-flight substantive change with invariant re-check + Status cascade. With `--editorial`: appends a `Type=editorial` Amendment Log row, refuses on behavioral-field diffs, does NOT cascade Status (INT-088 IU-1). |
| Approve | `--approve` | [modes/approve.md](modes/approve.md) | Record a peer-review approval signature in the Amendment Log (team profile, INT-021). |
| Help | `--help` | [modes/help.md](modes/help.md) | Render the USAGE / MODES / EXAMPLES block and stop. |
| Teaching | `--teaching` | [modes/teaching.md](modes/teaching.md) | Interactive tutorial walking a new author through writing an Intent section-by-section. |
| Provisional | `--provisional <slug>` | [modes/provisional.md](modes/provisional.md) | Redirect authoring into `dekspec/provisional/<slug>/` until `promote-provisional` runs. |
| Lite | `--lite` | [modes/lite.md](modes/lite.md) | Single-IU single-component bypass — skips `--analyze` + `/write-beads`, sets `lite: true` frontmatter, retains `--testpass`. Hard-refuses on `components > 1` / `ius > 1` / `adrs ≠ []` / `ics ≠ []`. INT-088 IU-2. |
| Fan-Out (internal) | — | [modes/fan-out.md](modes/fan-out.md) | Orchestrator/subagent dispatch contract for substantive-work modes (Creation, `--analyze`, `--accept`). |

**Dispatcher contract.** After parsing the mode flag in Mode Detection above, read the corresponding `modes/<slug>.md` file with the `Read` tool and follow its body as the active mode contract. The shared scaffolding below (Write-Time CoW Guard, Rules, Output, Closing Step) runs across every substantive-mode invocation regardless of which per-mode body is loaded.

## Teaching Mode

> **Index-stub.** When the engineer passes `--teaching`, the active mode body lives in [`modes/teaching.md`](modes/teaching.md). This stub satisfies the `test_skills_dispatcher.py::test_skill_has_teaching_mode_section` literal-presence check for `## Teaching Mode` in SKILL.md (per ds-int-007 / INT-008). Per-mode lazy-load (INT-087) keeps the per-mode body as the source of truth.

## Approve Mode

> **Index-stub.** When the engineer passes `--approve`, the active mode body lives in [`modes/approve.md`](modes/approve.md). This stub satisfies the `test_skill_approve_modes.py::test_skill_has_approve_mode_section` literal-token presence check for `## Approve Mode`, the `artifact_ops.py approve` helper reference, and the `review-approval` row name in SKILL.md.

`--approve` records a peer-review approval signature on an Intent under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the Intent's `## Amendment Log` table — it does **not** flip Status. Run the shared deterministic helper `python ../_lib/scripts/artifact_ops.py approve <Intent-path> --target-status <STATUS>` (see [`modes/approve.md`](modes/approve.md) for the full contract).

## Help Mode

> **Index-stub.** When the engineer passes `--help`, the active mode body lives in [`modes/help.md`](modes/help.md). The manifest below is duplicated here so that the `T-SKILL-HELP-MODE-PRESENT` audit rule (a mechanical check that reads only `SKILL.md`) sees the canonical YAML keys (`skill_name`, `one_line`, `modes`, `examples`) plus the `_lib/help_mode_template.md` citation. Per-mode lazy-load (INT-087) keeps the per-mode body as the source of truth; this stub satisfies the audit rule's literal-token requirement.

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-intent"
one_line:   "Author, analyze, accept, decompose, testpass, or lock an Intent (Phase 1 complete)"
modes:
  - { flag: "", args: "<description>", description: "Creation mode — see modes/create.md." }
  - { flag: "--analyze", args: "<Intent-path>", description: "Analyze mode — see modes/analyze.md." }
  - { flag: "--accept", args: "<Intent-path>", description: "Accept mode — see modes/accept.md." }
  - { flag: "--decompose", args: "<Intent-path>", description: "Decompose mode — see modes/decompose.md." }
  - { flag: "--testpass", args: "<Intent-path>", description: "Testpass mode — see modes/testpass.md." }
  - { flag: "--lock", args: "<Intent-path>", description: "Lock mode — see modes/lock.md." }
  - { flag: "--unlock", args: "<Intent-path>", description: "Unlock mode — see modes/unlock.md." }
  - { flag: "--sync", args: "<Intent-path>", description: "Sync mode — see modes/sync.md." }
  - { flag: "--audit", args: "<Intent-path>", description: "Audit mode — see modes/audit.md." }
  - { flag: "--review", args: "<Intent-path>", description: "Review mode — see modes/review.md." }
  - { flag: "--amend", args: "<Intent-path>", description: "Amend mode — see modes/amend.md." }
  - { flag: "--amend --editorial", args: "<Intent-path>", description: "Editorial-only amend — append a Type=editorial Amendment Log row; refuses on behavioral-field diffs (Verification / Components affected / Acceptance Criteria / IU list); does NOT cascade Status. INT-088 IU-1." }
  - { flag: "--approve", args: "<Intent-path>", description: "Approve mode — see modes/approve.md." }
  - { flag: "--teaching", args: "", description: "Teaching mode — see modes/teaching.md." }
  - { flag: "--provisional", args: "<slug>", description: "Provisional mode — see modes/provisional.md." }
  - { flag: "--lite", args: "<Intent-path>", description: "Lite mode — single-IU single-component bypass of --analyze + /write-beads; sets `lite: true` frontmatter; retains --testpass. Hard-refuses on components > 1 / ius > 1 / adrs ≠ [] / ics ≠ []. INT-088 IU-2. See modes/lite.md." }
  - { flag: "--help", args: "", description: "Show this help message (load modes/help.md for full per-mode descriptions)." }
examples:
  - "/write-intent --help"
  - "/write-intent --analyze dekspec/intents/INT-005-attachment-mime-coverage.md"
```

At runtime when `--help` is the active flag, load [`modes/help.md`](modes/help.md) for the full descriptions and render per `_lib/help_mode_template.md`.

## Write-Time CoW Guard (INT-082 phase 4)

Before any edit to a canonical artifact (anything under `dekspec/<kind-dir>/`), consult the CoW guard:

```bash
dekspec library cow-stage <path-to-canonical> [--incubation <slug>] [--at <repo>]
```

If the target path is claimed by a pre-ACCEPTED Intent (DRAFT/PROPOSED) via that Intent's `Components affected` globs, the verb:

1. Copies the canonical to `dekspec/provisional/<incubation-slug>/<KIND>-provisional-<file-slug>.md`.
2. Stamps `replaces: <CANONICAL-ID>` in the frontmatter so the eventual `promote-provisional` run does a REPLACE (preserving the canonical ID) instead of allocating a new one.
3. Returns the new provisional path. Edit that file instead; the canonical stays frozen.

If the path is not claimed by any pre-ACCEPTED Intent, the verb errors unless you pass an explicit `--incubation <slug>` (the canonical-only path is the normal edit flow).

**Skill discipline.** Inside this skill body, before any canonical-file `Edit`/`Write` call:

1. Compute the target path you intend to write.
2. Run `dekspec library cow-stage <target-path>` once. Surface the verb's stdout to the engineer.
3. If the verb exits 0 with a new provisional path printed, redirect the edit to that path.
4. If the verb exits 1 (no claim + no `--incubation`), proceed with the canonical edit as normal — the canonical is unclaimed and the edit is direct-flow legal.

**Audit pairing.** The `T-COW-CANONICAL-EDITED` rule (P2 mechanical) fires on every `git diff --name-only main` entry that is claimed AND lacks a provisional sibling with `replaces:` set — so a skill that skips this guard surfaces as advisory in the next `dekspec audit linkage` run, but never blocks.


## Rules

- **Files canonical (Decision D2 / v5 §21).** Intents live as markdown files at `dekspec/intents/INT-NNN-<slug>.md`. External trackers (Linear, Jira, GitHub Issues, Slack) may *seed* and may, at Phase 3+, *mirror* — but the file is canonical. Never write Intent content to anywhere except the file.
- **Capture is human-initiated (Decision D3 / v5 §22).** This skill is invoked by an engineer running `/write-intent`. Webhook-driven creation from a tracker is forbidden. The optional `source:` field records provenance only.
- **Serialization (ADR-016).** Per-Mission and advisory. At most one active child Intent per Mission is the intended discipline; across Missions and for Mission-less Intents there is no limit. Creation is never refused on serialization grounds — the Creation-mode check is an advisory note, and the gate of record is `dekspec audit linkage`.
- **Type drives shape.** The Intent's `type:` field selects the required block, the default Verification predicate, and the validation rules. Do not silently switch type — if the engineer's intent re-shapes mid-draft, surface and ask.
- **No template placeholders in DRAFT.** Every template section that is required at this stage must be populated with real content. `<reproduction-test-path-from-IB-1>` is the one allowed verbatim placeholder, and only inside the bug-type Verification block; `--decompose` (Part B) resolves it.
- **D19 / D20 are hard.** Measurable targets and decision rationale do not belong in an Intent. Move them to WS / ADR. The skill refuses to advance state until each finding is resolved.
- **Linked Architecture Elements is mandatory (Decision D12).** Every Intent links to at least one existing AE. If the engineer cannot name one, that signals either the Intent is too small or there is missing AE work — surface and stop.
- **Log corrections.** When this skill corrects a domain misinterpretation in the engineer's input — wrong term, confused concept, contradicted architectural fact — invoke `/write-ggc --log` with the correction details before proceeding. Feeds the glossary promotion pipeline.
- **Diff confinement is hard.** `--testpass` Step 2 is the gate that prevents Intents from quietly growing scope. An out-of-scope edit appends a TESTFAIL record (Status stays IMPLEMENTING — the TESTFAIL Status flip retired 2026-05-25) even when every Verification check passes. The remedy is either reverting the out-of-scope edit or re-running `--analyze` with an updated `Components affected:` (which re-validates the size cap). Never silently extend the glob list inside `--testpass`.
- **Verification fast-fails on first failure.** `--testpass` Step 3 stops at the first non-zero check. Subsequent checks are not run because they may depend on invariants the failing check guards. The engineer fixes, then re-runs.
- **`--lock` has two sufficient paths (ADR-017).** Run from `main` only. Path A — forward flow: Status `MERGED` and the Verification block byte-identical to the version `--testpass` ran against. Path B — every downstream WS/IC/IB the Intent produced is at status `>= ACCEPTED`; no `MERGED`, no `--testpass` record, no branch diff required (the path for Intents whose work shipped outside the Intent lifecycle). Either path is sufficient; if neither holds, refuse and name what each still needs.
- **`--unlock` is editorial-only and reason-gated.** `--unlock` walks `LOCKED → PROPOSED` so an editorial correction (stale glob, broken cross-ref, renamed-file path) can land; it refuses any status other than `LOCKED`, demands a full-sentence reason recorded verbatim in the Amendment Log, and never paraphrases that reason. It is the precursor to a re-`--lock` (Path B). Substantive change to a LOCKED Intent is **not** an `--unlock` case — see the `--amend` terminal-status rule below.
- **`--audit` is strictly read-only.** Audit never mutates the Intent file, never transitions Status, never appends an Amendment Log entry. If a finding requires action, the audit output recommends the remedial mode (`--amend` for substantive, `--review` for editorial); the engineer must explicitly invoke it.
- **`--sync` is non-substantive only.** Sync handles post-merge cleanup against the existing `## Post-implementation sync` checklist plus newly-discovered tail items. It refuses to touch any file outside the original `Components affected:` globs + `dekspec/` content paths. Substantive changes route through `--amend`, never through `--sync`.
- **`--review` cannot promote Status.** Review is editorial — engineer-driven Q&A walkthrough. It applies edits the engineer accepts and may end in DRAFT or hold whatever incoming Status the Intent already had, but it never transitions PROPOSED → ACCEPTED (that's `--accept`'s job).
- **`--amend` cascades Status backwards on substantive change.** Amending a PROPOSED Intent reverts it to DRAFT (Coverage Report + Size Assessment no longer match); amending an ACCEPTED Intent reverts it to DRAFT (the acceptance is no longer current). The engineer re-runs `--analyze` to re-validate. IMPLEMENTING amendments hold Status if `Components affected:` still covers the diff; OVERSIZED amendments are the typical remedy path.
- **`--amend` refuses on terminal statuses.** TESTPASS, MERGED, LOCKED, SUPERSEDED cannot be amended. Locked Intents that need a *substantive* change spawn a successor Intent (a new `/write-intent` invocation) and mark the original `SUPERSEDED`. An *editorial* correction to a LOCKED Intent (a stale `Components affected:` glob, a broken cross-reference) instead goes through `--unlock` → edit → `--lock` — a successor Intent would be disproportionate for a path-string fix.
- **OVERSIZED never produces a SUPERSEDED shell** (governing decision: **ADR-028**, LOCKED 2026-05-29 — "Default OVERSIZED handling to PEEL-OFF; reserve SUPERSEDE for LOCKED override / deprecation"). `SUPERSEDED` means *this artifact was overridden or deprecated* and is reserved for LOCKED Intents that shipped. Provisional state (DRAFT / OVERSIZED — never shipped) resolves via one of two non-SUPERSEDE paths: **PEEL-OFF** (default when the Intent has a natural core slice — narrow parent in place + scaffold N-1 siblings under the same Mission, parent keeps its identity / slot / history) or **CONVERT-TO-MISSION** (default when the Intent's scope is an umbrella over N capability surfaces — extract substance into a new Mission's near-immutable section, scaffold child Intents, **delete the OVERSIZED Intent file**, no Archive row). The shared partition-shape decision tree lives in [`_lib/oversized_splitting.md`](../_lib/oversized_splitting.md); both `/write-intent --analyze` and `/dekspec:orchestrate-intent` enter it on cap-violation, and `/write-mission` has a `from-oversized: <INT-NNN-path>` Decision Gate entry for the CONVERT branch. SUPERSEDE+N is **not** a default and is rarely correct — it only applies to genuine LOCKED overrides per ADR-028.

## Output

- `dekspec/intents/INT-NNN-<slug>.md` lifecycle transitions:
  - Creation: → DRAFT
  - `--analyze`: DRAFT → PROPOSED (clean) or DRAFT → OVERSIZED (cap exceeded)
  - `--accept`: PROPOSED → ACCEPTED
  - `--decompose`: ACCEPTED → IMPLEMENTING (or back to OVERSIZED if post-decomposition caps exceeded)
  - `--testpass`: IMPLEMENTING → TESTPASS (clean) or Status stays IMPLEMENTING (any failure appends a TESTFAIL record and the engineer's fix-then-rerun loop is captured there; the `TESTFAIL` Status flip retired 2026-05-25)
  - `--lock`: MERGED → LOCKED (Path A) or any non-terminal status → LOCKED (Path B, ADR-017)
  - `--unlock`: LOCKED → PROPOSED (reason-gated editorial-correction precursor to a re-`--lock`)
  - `--sync`: LOCKED (status hold) + Post-implementation sync checklist edits
  - `--audit`: read-only; no Status mutation
  - `--review`: status hold; editorial edits applied during walkthrough
  - `--amend`: substantive change with potential Status cascade backwards (PROPOSED → DRAFT, ACCEPTED → DRAFT, or any → OVERSIZED if a cap fails)
- Branch `int/INT-NNN-<slug>` (Creation only)
- Updated `dekspec/intent-index.md` per state transition (Active queue ↔ Archive)
- IB / bead artifacts produced by `--decompose` (sister skills do the actual writing)
- Amendment Log entries on Accept, Decompose, Testpass, Lock, Unlock (reason verbatim), Sync (editorial), Review (editorial), Amend (substantive). Audit writes nothing.
- Verification block per-check results recorded inside the Intent body on `--testpass`
- TESTFAIL records appended on every `--testpass` failure (record per-fail, not overwrite). Status stays IMPLEMENTING — the `TESTFAIL` Status flip retired 2026-05-25.
- Mission Intent queue append on `--lock` if `mission:` is set and the Mission file exists
- Post-implementation sync checklist updates on `--sync` (mark `[x]` items + new `[ ]` bullets discovered)
- Audit findings printed to stdout on `--audit`; exit code 0/1 based on CRITICAL findings

## Common Pitfalls

- **Don't bake measurable targets or decision rationale into the Intent — route them to WS / ADR.** D19/D20 are hard refusals; an Intent that names a latency budget or argues *why* an approach was chosen will not advance state until the finding is resolved upstream.
- **Don't author a new `/write-intent` to make a substantive change to a LOCKED Intent unless you actually mean to supersede it — and don't reach for `--unlock` for substantive change either.** Editorial fixes (stale glob, broken cross-ref, renamed path) go `--unlock` → edit → `--lock`; genuine behavioral change spawns a successor Intent and marks the original `SUPERSEDED`.
- **Don't silently widen `Components affected:` inside `--testpass` to absorb an out-of-scope edit — revert the edit or re-run `--analyze`.** Diff confinement is the gate that stops scope creep; extending the glob list bypasses the size-cap re-validation and appends a TESTFAIL record anyway.
- **Don't treat OVERSIZED as a SUPERSEDE case.** Provisional state (DRAFT / OVERSIZED, never shipped) resolves via PEEL-OFF or CONVERT-TO-MISSION per ADR-028; `SUPERSEDED` is reserved for LOCKED Intents that shipped and were overridden.
- **Don't advance an Intent that names zero existing AEs (D12).** No linked Architecture Element signals the Intent is too small or that AE work is missing — surface and stop rather than fabricating a link.
- **Don't edit a canonical artifact claimed by a pre-ACCEPTED Intent directly — stage copy-on-write first.** Run `dekspec library cow-stage <path>` before any canonical `Edit`/`Write`; skipping it trips the `T-COW-CANONICAL-EDITED` advisory.

## Verification Checklist

- [ ] The active mode was detected from `$ARGUMENTS` and the matching `modes/<slug>.md` body was loaded and followed (default: Creation).
- [ ] No template placeholders remain in a DRAFT (the bug-type `<reproduction-test-path-from-IB-1>` is the only allowed verbatim placeholder).
- [ ] The Intent links at least one existing AE (D12), and no D19/D20 finding (measurable target / decision rationale) is left unresolved.
- [ ] Any canonical-file write was preceded by a `dekspec library cow-stage` check, and edits to a claimed path were redirected to the provisional sibling.
- [ ] The Status transition recorded matches the mode's contract (e.g. `--accept` PROPOSED → ACCEPTED; `--audit` mutated nothing; `--review` did not promote Status).
- [ ] The required Amendment Log entry was appended for mutating modes (with `--unlock`'s reason recorded verbatim), and `--audit` wrote nothing.
- [ ] Any domain misinterpretation corrected during the run was logged via `/write-ggc --log` before proceeding.
- [ ] `dekspec audit relink` was run against the repo root as the final action of every substantive mode.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise an Intent — Creation, `--analyze`, `--accept`, `--decompose`, `--testpass`, `--lock`, `--unlock`, `--sync`, `--review`, `--amend`). After the artifact file is saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
