---
name: write-sv
description: Author, review, audit, accept, lock, or deprecate the System Vision (`SYSTEM-VISION`, singleton at `dekspec/system-vision.md`). The System Vision is the L0 root document that defines what this system IS, what it is NOT, who it serves, and why it exists. Every Architecture Element, ADR, Working Spec, and Mission ultimately derives from it. Authored once per system; revised by `--unlock` + edit + `--lock` only when the system's identity itself shifts.
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --accept | --lock | --unlock | --deprecate] [description or path]
related_skills: [write-ae, write-adr, write-constitution, write-mission, write-ggc]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

> **Scope of this skill.** The System Vision is the singleton root of the dekspec graph. There is exactly one per system, at `dekspec/system-vision.md` (id: `SYSTEM-VISION`). Subsystem-level descriptions belong in Architecture Elements (`/write-ae`), not in additional Vision documents. If a prior artifact named `Vision Note:` exists, it is a legacy naming — migrate to a System Vision (singleton) or convert to an Architecture Element (subsystem).

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> The System Vision is rigorous up-front and revised rarely. Prior conversation context can anchor on partial framings and degrade the elevator-pitch rigor.
>
> First message → proceed. Prior history → ask "context may affect Vision quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-sv DekFactory is the autonomous coding orchestration platform.

It serves staff engineers running multi-agent build sessions; it exists because
hand-coordinating parallel agents over a shared repo doesn't scale. Success is a
green merge from an unattended overnight run. We are NOT building a chat IDE.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Fan-Out Mode (default authoring path)** — substantive authoring is delegated to a fresh-context subagent (per bead `ds-di2` / INT-032).

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Review mode** — `--review` flag. Walks the existing Vision interactively for editorial revisions. Skip to **Review Mode**.
- **Audit mode** — `--audit` flag. Read-only health check. Skip to **Audit Mode**.
- **Accept mode** — `--accept` flag. Promote PROPOSED → ACCEPTED. Skip to **Accept Mode**.
- **Lock mode** — `--lock` flag. Promote ACCEPTED → LOCKED. Skip to **Lock Mode**.
- **Unlock mode** — `--unlock` flag. Demote LOCKED → PROPOSED for substantive revision. Skip to **Unlock Mode**.
- **Dry-run mode** — `--dry-run` flag. Plan-only path; produce no content.
- **Deprecate mode** — `--deprecate` flag. Mark as DEPRECATED (system retired or superseded). Skip to **Deprecate Mode**.
- **Default authoring (fan-out)** — no flag. Proceed to **Fan-Out Mode (default authoring path)** below.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag)
- Inline (parent context): `--help`, `--teaching`, `--review`, `--audit`, `--accept`, `--lock`, `--unlock`, `--dry-run`, `--deprecate`

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-sv"
one_line:   "Author, review, audit, accept, lock, unlock, or deprecate the System Vision (singleton)"
modes:
  - { flag: "", args: "<description>", description: "Create the System Vision at dekspec/system-vision.md via FAN-OUT: the parent bundles context (template, constitution, glossary, README, key AEs, engineer guidance, constraints) and dispatches a fresh-context subagent (general-purpose) via the Agent tool to author the artifact. The parent then validates + saves. Refuses if a non-DEPRECATED System Vision already exists at that path. Writes all six sections (preamble, What This Is, Who This Is For, Why This Exists, What Success Looks Like, What We Are Not Building). Status: DRAFT." }
  - { flag: "--review", args: "", description: "Walk the existing System Vision interactively. Surfaces each section for editorial revision. Refuses to edit substantively in LOCKED status — use --unlock first." }
  - { flag: "--audit", args: "", description: "Read-only health check. Verifies all six required sections present, schema parses clean, no Vision Note prefix in H1, modified date is current. Mutates nothing." }
  - { flag: "--accept", args: "", description: "Promote PROPOSED → ACCEPTED. Engineer-only gate; downstream artifacts may begin to reference the Vision." }
  - { flag: "--lock", args: "", description: "Promote ACCEPTED → LOCKED. Freezes substantive edits; editorial amendments only." }
  - { flag: "--unlock", args: "", description: "Demote LOCKED → PROPOSED. Required before substantive edits. Appends Amendment Log entry recording the unlock reason." }
  - { flag: "--deprecate", args: "", description: "Mark as DEPRECATED. Used only when the system itself is retired or superseded by another system with its own Vision. Append Amendment Log entry recording the reason." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing the System Vision singleton section-by-section. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-sv DekFactory is the autonomous coding orchestration platform that ..."
  - "/write-sv --review"
  - "/write-sv --audit"
  - "/write-sv --accept"
  - "/write-sv --lock"
  - "/write-sv --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: System Vision (L0 singleton, slug-only filename per ADR-012)
- **template_path**: `templates/system-vision-template.md`
- **methodology_section**: §4 Layer 0 of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/system-vision.md` (the library's own self-spec), falling back to `tests/fixtures/` if the singleton hasn't landed yet
- **required_sections**: [preamble, What This Is, Who This Is For, Why This Exists, What Success Looks Like, What We Are Not Building]

Skill-specific structural checks to surface as Open Issues: T-VISION (missing required section, `Vision Note:` prefix in H1).

**Skill-unique write target:** the System Vision is written to the slug-only path `dekspec/system-vision.md` (not a numbered file) per ADR-012's L0-singleton-as-slug-only convention.

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `general-purpose` (no dedicated `dekspec:vision-author` type today).
- **substantive_modes**: [Creation (default)]
- **inline_modes**: [`--help`, `--teaching`, `--review`, `--audit`, `--accept`, `--lock`, `--unlock`, `--deprecate`]
- **mechanical preconditions** (orchestrator runs inline BEFORE dispatch; refuse on failure):
  1. **Singleton precheck.** Read `dekspec/system-vision.md` if it exists. If status is anything other than `DEPRECATED`, refuse: "A System Vision already exists at dekspec/system-vision.md with status `<STATUS>`. The System Vision is a singleton — only one non-DEPRECATED Vision per system. Use `/write-sv --review` for editorial revisions, `/write-sv --unlock` to substantively change a LOCKED Vision, or `/write-sv --deprecate` to retire it before creating a successor." If status is `DEPRECATED`, ask: "Existing System Vision is DEPRECATED. Replace it (writes a new Vision in DRAFT, archives the DEPRECATED one to `dekspec/archive/system-vision-<date>.md`)? (y/n)" Archive on yes; abort on no.
  2. **Engineer guidance precheck.** If `$ARGUMENTS` has no system name + elevator pitch, ask: "I need the system name and a one-paragraph elevator pitch describing what this system does, who it serves, and what it changes. What system are you describing?" Block until supplied.
- **bundle_list** (Step 1 context — resolve paths only; let the subagent ingest them fresh):
  1. Template (required) — `dekspec/templates/system-vision-template.md` (or `templates/system-vision-template.md` in consumer repos).
  2. Existing constitution (if present) — `dekspec/constitution.md` (grounds non-negotiable commitments the Vision must be coherent with).
  3. Existing domain glossary (if present) — `dekspec/domain-glossary.md` (Title-Case terms the Vision uses consistently).
  4. Repo-wide context (best-effort) — `README.md` at repo root; `dekspec/architecture-elements-index.md` if present.
  5. Key AEs (best-effort) — full path list of AE files under `dekspec/architecture-elements/` so the subagent can read those that ground what the system actually does today.
  6. Engineer guidance — cleaned `$ARGUMENTS` (system name + elevator pitch + any extra direction).
  7. Constraints — singleton path (`dekspec/system-vision.md`); H1 form (`# System Vision: <Name>` — never `# Vision Note: ...`, rejected by parser since v0.38.0+); Status `DRAFT` on creation; `Created` / `Modified` stamped to today (`YYYY-MM-DD`); six load-bearing non-empty sections (preamble, `## What This Is`, `## Who This Is For`, `## Why This Exists`, `## What Success Looks Like`, `## What We Are Not Building`); per-section guidance from §"Draft the six sections" (pasted verbatim into the prompt — it is the authoring contract); Why-This-Exists + Who-This-Is-For load-bearing — return `INSUFFICIENT_INPUT:` rather than guess.
  8. Return-shape contract — subagent returns the **full markdown body as its final message**; no file writes from the subagent; the orchestrator saves to `dekspec/system-vision.md`.
- **expected_output_path**: `dekspec/system-vision.md` (singleton; the only valid path; orchestrator writes the file after structural validation).
- **validation**: cheap parent-side structural pre-save checks — write the returned content to a temp path and run `python ../_lib/scripts/validate_structure.py <temp-path>` (checks H1 starts with `# System Vision:` and not `# Vision Note:`; all required H2 sections present and non-empty; preamble non-empty between H1 and first H2; `Status` is `DRAFT`; `Created`/`Modified` are today; prints failing rule names one per line, exit 1; exit 2 = file unreadable). Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — `validate_structure.py` is this skill's named equivalent gate; on failure, re-dispatch with the failing rule names appended as a fix-up directive, do **not** silently patch in the parent. After save, run `dekspec validate --kind vision dekspec/system-vision.md` (and `dekspec doctor --at .` for the full graph check after Status reaches PROPOSED). Final report names the file written + Status=DRAFT + next recommended mode (`--review` for editorial passes; later `--accept` for PROPOSED→ACCEPTED; later `--lock` to fix dependent AEs/ADRs).

**End of Fan-Out Mode.**

## Review Mode

Walk the existing System Vision interactively for editorial revisions.

### Steps

1. Read `dekspec/system-vision.md`. Refuse if Status is `LOCKED` — surface "System Vision is LOCKED. Substantive edits require `/write-sv --unlock` first."
2. Walk each section in order. For each:
   - Show the current content.
   - Ask: "Keep, edit, or rewrite?" If edit, accept the engineer's revised text. If rewrite, accept new content.
   - Apply the change.
3. After all sections walked, update `Modified` to today's date.
4. Append an Amendment Log entry: `| <today> | Editorial | <one-sentence summary of changes> | <author> |`.
5. Save.

If the engineer asks to change `Why This Exists` substantively, surface: "Changing Why This Exists is a substantive change. If the Vision is LOCKED, you need `--unlock` first. If it is ACCEPTED or PROPOSED, edit freely but expect dependent AEs / ADRs to cascade."

**End of Review Mode.**

## Audit Mode (read-only)

Reads `dekspec/system-vision.md`. Reports findings but mutates nothing.

### Step 1: Parse + schema validation

1. Read the file. Refuse if missing — "No System Vision at dekspec/system-vision.md. Run `/write-sv <description>` to create one."
2. Call `dekspec.constraint_compiler.parse_vision` on the path. Surface any `VisionParseError` as a CRITICAL finding.

### Step 2: Run the check battery

1. **H1 form** — H1 must be `# System Vision: <Name>` or `# <Plain Name>`. If H1 starts with `# Vision Note:`, surface CRITICAL — that form is rejected by the parser as of dekspec v0.38.0+.
2. **Required sections** — all six load-bearing sections present and non-empty: `preamble` (text between H1 and first H2), `What This Is`, `Who This Is For`, `Why This Exists`, `What Success Looks Like`, `What We Are Not Building`. Surface IMPORTANT for any missing.
3. **Status coherence** — Status is one of `TODO | DRAFT | PROPOSED | ACCEPTED | LOCKED | DEPRECATED`. Status `LOCKED` while `Modified` is today's date suggests an edit slipped past the lock — surface as IMPORTANT.
4. **Amendment Log** — if status is `LOCKED` or `ACCEPTED`, an Amendment Log section should exist and have at least one row recording the most recent status transition. Missing is MINOR.
5. **Date stamps** — `Created` and `Modified` are present and `YYYY-MM-DD`. Missing or malformed is IMPORTANT.

### Step 3: Report

Group findings by severity (CRITICAL / IMPORTANT / MINOR), one per line, with the recommended remedial mode.

Exit code `0` if no CRITICAL findings, `1` if any CRITICAL.

**End of Audit Mode.**

## Accept Mode (PROPOSED → ACCEPTED)

1. Read `dekspec/system-vision.md`. Verify Status — run `python ../_lib/scripts/artifact_ops.py status-guard dekspec/system-vision.md --expect PROPOSED`; surface stderr and STOP if it exits non-zero.
2. Confirm with the engineer that the Vision is settled enough for downstream artifacts (AEs / ADRs / WSs) to start referencing it.
3. Flip Status PROPOSED → ACCEPTED, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition dekspec/system-vision.md --from PROPOSED --to ACCEPTED --note "Promoted PROPOSED to ACCEPTED via /write-sv --accept" --engineer <name>` (surface stderr on non-zero exit and STOP).

**End of Accept Mode.**

## Lock Mode (ACCEPTED → LOCKED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Lock for the canonical 4-step contract. The artifact is the singleton at `dekspec/system-vision.md`. Parameters:

- **artifact_kind_singular**: System Vision
- **pre_lock_audit_ref**: §Audit Mode of this skill
- **status_before**: ACCEPTED
- **status_after**: LOCKED
- **artifact_index_path**: none (System Vision is the L0 singleton; no index file)

**L0 singleton — extra-loud warning at Step 2.** Before running the audit, surface to the engineer: "The System Vision is the L0 root. Locking signals that any change here cascades to every dependent Architecture Element, ADR, Working Spec, and Mission. Substantive change after this requires `--unlock` first. Confirm the Vision is unlikely to change before continuing."

## Unlock Mode (LOCKED → PROPOSED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Unlock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: System Vision
- **status_before**: LOCKED
- **status_after**: PROPOSED
- **artifact_index_path**: none

L0 singleton cascade reminder to surface in Step 4: "System Vision unlocked to PROPOSED. Make the substantive edit via `/write-sv --review`, then `--accept` and `--lock` again. Dependent AEs / ADRs may need cascading updates — run `/doctor` after the change settles."

## Deprecate Mode (any → DEPRECATED)

1. Read `dekspec/system-vision.md`. Read its current Status; refuse if it is already `DEPRECATED`.
2. Ask the engineer for the deprecation reason (system retired / superseded by `<successor system>` with its own Vision / merged into another system). Refuse without a reason.
3. Flip Status to `DEPRECATED`, bump Modified, and append the Amendment Log row — run `python ../_lib/scripts/artifact_ops.py transition dekspec/system-vision.md --from <current-status> --to DEPRECATED --note "Deprecated: <engineer's reason>" --engineer <name>` (`--from` is the Vision's current status; the reason is engineer-supplied AI judgment; surface stderr on non-zero exit and STOP).
4. Surface: "System Vision DEPRECATED. The artifact remains at dekspec/system-vision.md for historical record. A new System Vision may now be authored (will prompt to archive this one to dekspec/archive/)."

**End of Deprecate Mode.**

## Provisional Mode (Singleton)

`--provisional <incubation-slug>` stages a copy of the System Vision singleton inside `dekspec/provisional/<incubation-slug>/` instead of editing the canonical at `dekspec/system-vision.md`. Singletons follow the same CoW discipline as numbered artifacts — the difference is that the `replaces:` field uses the canonical filename rather than a `<KIND>-NNN` ID.

Use this mode when:
- The System Vision change is exploratory and might be abandoned before ratification.
- Multiple Intents in the same incubation folder co-vary with the System Vision change.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding.
2. CoW the singleton via the auto-stage verb:
   ```
   dekspec library cow-stage dekspec/system-vision.md --incubation <slug>
   ```
   The verb copies the singleton into `dekspec/provisional/<slug>/<basename>-provisional.md`, stamps `replaces: system-vision` in YAML frontmatter, and returns the new path.
3. **Populate the staged copy with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here. The PROVISIONAL banner at the top stays.
4. **Reject `--lock` / `--accept`** in combination with `--provisional`. The singleton's canonical replacement runs as part of the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)), not from this skill body. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)
5. **`--audit` / `--review`** remain available; they operate on the provisional file's content.
6. Closing step: surface the provisional path, the branch (if `dekspec library new-provisional` was used earlier), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

**End of Provisional Mode.**

## Write-Time CoW Guard (INT-082 phase 4)

Before any edit to the System Vision singleton at `dekspec/system-vision.md`, consult the CoW guard:

```bash
dekspec library cow-stage dekspec/system-vision.md [--incubation <slug>] [--at <repo>]
```

If a pre-ACCEPTED Intent (DRAFT/PROPOSED) claims the singleton's path via Components-affected globs, the verb copies the canonical into the incubation folder + stamps `replaces:`. Edit the staged copy; the canonical stays frozen.

If the singleton is unclaimed, the verb errors unless `--incubation <slug>` is passed explicitly — the canonical-only path is then the normal edit flow.

**Skill discipline.** Inside this skill body, before any canonical `Edit`/`Write` call on `dekspec/system-vision.md`:

1. Run `dekspec library cow-stage dekspec/system-vision.md` once.
2. On exit 0 (provisional path printed): redirect the edit there.
3. On exit 1 (no claim + no `--incubation`): proceed with the canonical edit (direct-flow legal).

**Audit pairing.** `T-COW-CANONICAL-EDITED` (P2 mechanical) fires on direct-edit bypasses of this guard.

## Rules

- **Singleton.** Exactly one non-DEPRECATED System Vision per dekspec tree, always at `dekspec/system-vision.md` with id `SYSTEM-VISION`. Subsystem-level descriptions are Architecture Elements, not additional Vision documents.
- **H1 form.** `# System Vision: <Name>` or `# <Plain Name>`. Never `# Vision Note: ...` — the parser rejects that prefix as a guard against subsystem Vision Notes colliding with the singleton id.
- **All six sections are load-bearing.** Preamble (between H1 and first H2), What This Is, Who This Is For, Why This Exists, What Success Looks Like, What We Are Not Building. The Vision schema and (planned) T-VISION audit rules enforce them.
- **Why This Exists is the load-bearing rationale.** A Vision without a Why-This-Exists body is structurally incomplete. Creation Mode refuses to proceed without it.
- **LOCKED is the steady state.** Once a system's Vision is settled, it lives in LOCKED. Substantive change is an `--unlock` → edit → `--lock` cycle, not a routine edit.
- **Editorial vs substantive.** Editorial = typo, clarification, link fix, formatting. Substantive = changing what the system IS, who it's FOR, why it EXISTS, what it considers success, or what it explicitly is NOT. Substantive edits in LOCKED status require `--unlock` first.
- **Log corrections.** When this skill corrects a domain misinterpretation in the engineer's input, invoke `/write-ggc --log` with the correction details before proceeding.

## Output

- `dekspec/system-vision.md` lifecycle transitions:
  - Creation: → DRAFT (engineer drives DRAFT → PROPOSED manually as the draft settles)
  - `--review`: editorial revisions (no status change)
  - `--accept`: PROPOSED → ACCEPTED
  - `--lock`: ACCEPTED → LOCKED
  - `--unlock`: LOCKED → PROPOSED
  - `--deprecate`: any → DEPRECATED
- Amendment Log entries on every mode except `--review` editorial passes that touch only typos.
- No index file update (the System Vision is a singleton; no index needed).

## Common Pitfalls

- Don't author a second Vision for a subsystem — write an Architecture Element via `/write-ae` instead; the System Vision is a per-system singleton at `dekspec/system-vision.md`.
- Don't emit `# Vision Note: ...` as the H1 — use `# System Vision: <Name>` (or `# <Plain Name>`); the parser has rejected the `Vision Note:` prefix since v0.38.0+.
- Don't leave `Why This Exists` (or `Who This Is For`) thin or inferred — return `INSUFFICIENT_INPUT:` and ask the engineer; these are the load-bearing rationale, and guessing them poisons every downstream AE/ADR.
- Don't patch a failed subagent draft inline in the parent — re-dispatch with the failing `validate_structure.py` rule names appended; silent parent-side fixes defeat the fan-out contract.
- Don't make a substantive edit (what the system IS / FOR / WHY / success / NOT) while the Vision is LOCKED — run `/write-sv --unlock` first; editorial-only changes (typo, link, formatting) are the sole exception.
- Don't skip `dekspec relink` after a write/revise mode — the cross-artifact backlinks go stale; it is the mandatory last action, not a deferred reminder.

## Verification Checklist

- [ ] Exactly one non-DEPRECATED System Vision exists at `dekspec/system-vision.md` (id `SYSTEM-VISION`); no duplicate or subsystem Vision was created.
- [ ] H1 is `# System Vision: <Name>` or `# <Plain Name>` — not `# Vision Note: ...`.
- [ ] All six sections are present and non-empty: preamble, What This Is, Who This Is For, Why This Exists, What Success Looks Like, What We Are Not Building.
- [ ] `Status`, `Created`, and `Modified` are stamped; `Created`/`Modified` use `YYYY-MM-DD` and reflect the transition just made.
- [ ] An Amendment Log row was appended for every mode except a typo-only `--review` pass.
- [ ] `dekspec validate --kind vision dekspec/system-vision.md` parses clean (and `dekspec doctor --at .` once Status ≥ PROPOSED).
- [ ] `dekspec relink` was run against the repo root after saving (the mandatory closing step).

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise the System Vision — Creation, `--accept`, `--review`, `--lock`, `--unlock`, `--deprecate`). After the artifact file is saved, run:

```
dekspec relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
