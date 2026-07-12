---
name: write-constitution
description: Write, audit, review, revise, resync, accept, or dry-run the project's Constitution — the L0 singleton that names a project's non-negotiable operational commitments across eight articles (Project Identity, Technology Stack, Quality Standards, Architecture Principles, Development Workflow, Model Configuration, Boundaries, Amendments). Mode catalog mirrors /write-evals.
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --resync | --revise | --accept | --approve | --dry-run] [path to Constitution or target slug] [engineer notes or path to notes file]
related_skills: [write-sv, write-ggc, write-adr, write-ae, write-evals]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

Write or maintain the project's Constitution — the third L0 singleton (after System Vision and Domain Glossary) that captures standing operational commitments worker agents read at session-load time. The Constitution has exactly eight articles in canonical order: Project Identity (typed pointer to System Vision), Technology Stack, Quality Standards, Architecture Principles (typed `adr_refs`), Development Workflow, Model Configuration, Boundaries (typed `adr_refs` + `ae_refs`), Amendments.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill writes or maintains a load-bearing L0 singleton that every agent in the repo reads at session-load time. Prior conversation context can degrade Constitution quality — the model may anchor on prior-session tech-stack assumptions or pre-existing prose instead of deriving content from the project's actual standing commitments.
>
> First message → proceed. Prior history → ask "context may affect Constitution quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-constitution dekspec/constitution.md

Bootstrap our Constitution. Article 1 points at dekspec/system-vision.md; tech stack is Python 3.12 + pytest; cite ADR-002 (git-URL distribution) under Architecture Principles and ADR-004 (audit-vs-compiler separation) + AE-008 (plugin packaging) under Boundaries. Seed Status=DRAFT.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Creation Mode**.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **Review mode** — `--review` flag. Skip to **Review Mode**.
- **Resync mode** — `--resync` flag. Skip to **Resync Mode**.
- **Revise mode** — `--revise` flag. Skip to **Revise Mode**.
- **Accept mode** — `--accept` flag. Skip to **Accept Mode**.
- **Dry-run mode** — `--dry-run` flag. Skip to **Dry-Run Mode**.
- **Lock mode** — `--lock` flag. Skip to **Lock Mode**.
- **Approve mode** — `--approve` flag. Skip to **Approve Mode**.
- **Creation mode** — no flag. Proceed to **Fan-Out Mode (default authoring path)**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--accept`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--dry-run`, `--resync`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `general-purpose` (no dedicated `dekspec:constitution-author` type today; swap when one lands).
- **substantive_modes**: [Creation (default), `--accept`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--dry-run`, `--resync`]
- **bundle_list** (Step 1 context):
  1. Template path — `dekspec/templates/constitution-template.md` (eight Article scaffolds in canonical order: 1 Project Identity, 2 Technology Stack, 3 Quality Standards, 4 Architecture Principles, 5 Development Workflow, 6 Model Configuration, 7 Boundaries, 8 Amendments).
  2. Methodology references — `docs/dekspec-methodology.md` §4 Layer 0; `dekspec/dekspec-operating-guide.md` §Constitution (if present).
  3. System Vision path — `dekspec/system-vision.md` (Article 1 `see_also` target).
  4. Prior Constitution path — `dekspec/constitution.md` if present (mandatory for `--accept` / `--revise`; optional for Creation).
  5. AE registry — `dekspec/architecture-elements-index.md` + full path list of `dekspec/architecture-elements/AE-*.md` (for Article 7 `ae_refs`). When the engineer's guidance names a boundary domain, run `python ../_lib/scripts/bundle_related.py --keywords "<boundary-domain-keywords>" --include ae` to narrow the candidate AE set; the subagent still applies judgment to pick the final `ae_refs`.
  6. ADR registry — `dekspec/adrs-index.md` (if present) + full path list of `dekspec/adrs/ADR-*.md` (for Article 4 + Article 7 `adr_refs`). When a principle/boundary domain is named, run `python ../_lib/scripts/bundle_related.py --keywords "<principle-domain-keywords>" --include adr` to surface candidate ADRs whose linkage sections touch that domain; the subagent applies judgment to pick the final `adr_refs`.
  7. Domain glossary — `dekspec/domain-glossary.md` (no undefined Title-Case jargon).
  8. Engineer guidance — `$ARGUMENTS` verbatim (target path, revise notes if any, structured cues).
  9. Constraints — T-CONSTITUTION (all 8 Articles present, in canonical order, with required structural fields); L-CONSTITUTION (Article 1 `see_also` resolves to system-vision; every `adr_refs` / `ae_refs` resolves to an existing artifact); `Created:` / `Modified:` ISO-8601; Status ∈ `DRAFT | PROPOSED | ACCEPTED`; Article 8 Amendment Log seeded for Creation (Type=Substantive "Initial authoring"), appended for `--revise` (Type=Revise + bump Modified) and `--accept` (Type=Accept + flip Status to ACCEPTED).
- **expected_output_path**: `dekspec/constitution.md` (singleton) or engineer-overridden from `$ARGUMENTS`.
- **validation**: `dekspec validate --kind constitution <output-path>`; fallback `dekspec doctor --at <project-root> 2>&1 | grep -E '^\s*\[(T|L)-CONSTITUTION-'` if the `constitution` subcommand is not yet wired. Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — on non-zero exit, surface verbatim and stop, do not silently retry. Mode-specific post-checks: Creation → 8 Articles present, Article 1 pointer resolves, Amendment Log seeded, Status=DRAFT; Revise → Modified bumped + Type=Revise row + Status unchanged; Accept → Status=ACCEPTED + Type=Accept row + no critical/important findings.

**End of Fan-Out Mode.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-constitution"
one_line:   "Write, audit, review, revise, resync, accept, or dry-run the project's L0 Constitution singleton."
modes:
  - { flag: "", args: "[target]", description: "Write a new Constitution from templates/constitution-template.md at the given target (default: dekspec/constitution.md). (Creation Mode)" }
  - { flag: "--audit", args: "[path]", description: "Run T-CONSTITUTION + L-CONSTITUTION audit rules against the target Constitution (default: dekspec/constitution.md). Read-only — reports findings without changes. (Audit Mode)" }
  - { flag: "--review", args: "[path]", description: "Walk through Open Issues / unresolved amendments interactively; resolve one at a time with the engineer. (Review Mode)" }
  - { flag: "--resync", args: "[path]", description: "Re-derive Article 4 (`adr_refs`) and Article 7 (`adr_refs` + `ae_refs`) after AE / ADR cross-references evolve. Proposes deltas; applies on approval. (Resync Mode)" }
  - { flag: "--revise", args: "[path] <notes>", description: "Update existing Constitution after engineer feedback. Notes: inline text or path to a .md / .txt file. Bumps Modified date and appends an Amendment-Log row. (Revise Mode)" }
  - { flag: "--accept", args: "[path]", description: "Promote DRAFT → ACCEPTED after a clean --audit. Refuses if any critical or important findings remain. (Accept Mode)" }
  - { flag: "--dry-run", args: "[other-flag args]", description: "Preview the action of any other mode without writing. Useful for impact assessment before committing. (Dry-Run Mode)" }
  - { flag: "--teaching", args: "[path]", description: "Interactive tutorial walking a new author through writing the L0 Constitution's eight articles section-by-section. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-constitution"
  - "/write-constitution dekspec/constitution.md"
  - "/write-constitution --audit"
  - "/write-constitution --audit dekspec/constitution.md"
  - "/write-constitution --review"
  - "/write-constitution --resync"
  - "/write-constitution --revise dekspec/constitution.md \"promote to ACCEPTED after AE-001 lands\""
  - "/write-constitution --revise dekspec/constitution.md review-notes.md"
  - "/write-constitution --accept"
  - "/write-constitution --dry-run --resync"
  - "/write-constitution --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: Constitution (L0 singleton)
- **template_path**: `templates/constitution-template.md`
- **methodology_section**: §4 Layer 0 of `docs/dekspec-methodology.md`
- **exemplar_paths**: `dekspec/constitution.md` if present, otherwise `tests/fixtures/`
- **required_sections**: [Article 1 Project Identity, Article 2 Technology Stack, Article 3 Quality Standards, Article 4 Architecture Principles, Article 5 Development Workflow, Article 6 Model Configuration, Article 7 Boundaries, Article 8 Amendments]

Skill-specific structural checks to surface as Open Issues: T-CONSTITUTION (missing required Article), L-CONSTITUTION (broken AE/ADR `see_also` reference).

**Skill-unique field shape:** Article 1 is a typed pointer (`{summary, see_also}` pointing to `dekspec/system-vision.md`), not free prose. The remaining Articles are prose + structured fields. Validate Article 1's pointer shape during step 3 before accepting the engineer's input.

## Audit Mode

**Invocation:** `/write-constitution --audit [path]`

**Purpose.** Run the T-CONSTITUTION + L-CONSTITUTION audit rules against a target Constitution and surface findings in the engineer-facing canonical format. Read-only: reports findings without writing.

**Inputs.**

- Target path (default: `dekspec/constitution.md` at the project root).
- Optional `--profile <name>` to use a non-default audit profile (default: `v1`).

**Outputs.**

- Findings list filtered to `T-CONSTITUTION-*` and `L-CONSTITUTION-*` rule codes.
- Each finding line: `severity rule artifact_id message` (matching `dekspec doctor`'s output shape).
- Summary count by severity (critical / important / minor).

**Delegation.** This mode is engineer-facing sugar over the existing audit CLI. Single rule implementation, two invocation paths (skill + CLI) per WS-005 BR8. Invocation:

```bash
dekspec doctor --at <project-root> 2>&1 | grep -E '^\s*\[(T|L)-CONSTITUTION-'
```

`dekspec audit linkage` has no kind filter, so the Constitution findings are isolated by the grep above, not by a `--kind` flag.

The skill never calls rule functions or parser internals directly — per ADR-004, the audit-vs-compiler separation goes through the CLI surface.

**Behavior on no Constitution.** If the project has no `dekspec/constitution.md`, the underlying CLI emits zero findings (Constitution is opt-in per WS-005 Open Issue #1); the skill reports `"No Constitution found at <path>; nothing to audit."` and exits.

**End of Audit Mode.**

## Review Mode

**Invocation:** `/write-constitution --review [path]`

**Purpose.** Walk the target Constitution's open issues interactively and resolve them one at a time with the engineer. Open issues are tracked in the Constitution's Article 8 Amendment Log as items with non-`done` resolution status, and in any companion `## Open Issues` section if present.

**Inputs.**

- Target path (default: `dekspec/constitution.md`).
- Engineer interaction: present each unresolved item; engineer rules `resolve` / `defer` / `escalate`.

**Outputs.**

- For each resolved item: an updated Amendment-Log row with the resolution.
- For each deferred item: status note in Article 8 explaining why.
- For each escalated item: a new `br` bead filed and referenced in Article 8.

**Workflow.**

1. Parse the target Constitution via the standard parser surface.
2. Extract pending issues from Article 8's Amendment Log + any companion sections.
3. Present each issue with full context: which Article it touches, which WS / Intent / ADR cascades from, any prior partial resolutions.
4. For each, engineer rules `resolve <one-line note>` / `defer <reason>` / `escalate <bead-slug>`.
5. Write back: amend Article 8 with resolution rows; bump `Modified` date.

**Delegation.** Engineer-facing prose work. The skill does not invoke `dekspec doctor` here — review is interactive prose authoring, not rule emission. (Audit-style findings on the *result* of review happen in a follow-up `--audit` pass.)

**End of Review Mode.**

## Resync Mode

**Invocation:** `/write-constitution --resync [path]`

**Purpose.** Re-derive Article 4 (`adr_refs`) and Article 7 (`adr_refs` + `ae_refs`) typed-ref arrays after upstream AE / ADR cross-references evolve. The Constitution cites *load-bearing* references — a curatorial selection, not every ADR / AE in the repo — but when the cited set drifts (an ADR is superseded, an AE is renamed, a new boundary AE lands), Resync proposes deltas.

**Inputs.**

- Target path (default: `dekspec/constitution.md`).
- The current AE / ADR registry on disk (`dekspec/adrs/`, `dekspec/architecture-elements/`).

**Outputs.**

- Delta report: which cited refs no longer resolve; which new ADRs / AEs the engineer may want to cite; which cited refs' titles or status have changed.
- Engineer approves on a per-row basis; applies confirmed deltas.
- Amendment-Log row appended with summary of the resync.

**Workflow.**

1. Run `scripts/validate_linkage.py <constitution-path>` to resolve the existing references. The script parses every `ADR-NNN` token in Articles 4 / 7 and every `AE-NNN` token in Article 7, checks each id against `dekspec/adrs/` and `dekspec/architecture-elements/`, and emits JSON `{adr_refs, ae_refs, broken}`; `broken` lists `{id, kind, article}` per unresolved ref. Exit 1 = at least one broken ref. Surface stderr on a non-zero exit (exit 2 = file unreadable).
2. For each entry in `broken`, judge whether it is a typo, a deleted artifact, or a not-yet-authored ref — and decide the remediation.
3. For each newly-LOCKED ADR with `architectural-principle` labels (or new AE marked as a boundary): propose adding to the typed-ref array.
4. Present a diff; engineer rules `apply` / `skip` per row.
5. Write back: update typed-ref arrays; bump `Modified`; append Amendment-Log row with Type=Resync.

**Delegation.** `scripts/validate_linkage.py` does the deterministic resolve over `dekspec/adrs/` + `dekspec/architecture-elements/` (no new `dekspec list-aes` / `list-adrs` CLI required per WS-005 Open Issue #5). The skill judges what each broken ref means.

**End of Resync Mode.**

## Revise Mode

**Invocation:** `/write-constitution --revise [path] <notes>`

**Purpose.** Apply engineer feedback to the Constitution — substantive content changes, mode-specific updates, prose clarifications. Bumps the `Modified` date and appends an Amendment-Log row.

**Inputs.**

- Target path (default: `dekspec/constitution.md`).
- Notes: inline text or path to a `.md` / `.txt` file.

**Outputs.**

- Constitution markdown updated per the notes.
- `Modified:` field bumped to today's date.
- Amendment-Log row appended with Type=Revise, the one-line change description, and the engineer name.

**Workflow.**

1. Parse target Constitution.
2. Read engineer notes (inline string or file).
3. Identify the affected Article(s); show before/after for engineer approval.
4. Write back the updated Constitution.
5. Run `--audit` automatically on the result; report findings; engineer rules whether to fix-up or accept the new findings.

**Delegation.** The post-revise audit invocation matches the Audit Mode delegation (above): `dekspec doctor --at <root>` filtered to Constitution findings.

**End of Revise Mode.**

## Accept Mode

**Invocation:** `/write-constitution --accept [path]`

**Purpose.** Promote the target Constitution from `DRAFT` (or `PROPOSED`) status to `ACCEPTED`. Refuses if any critical or important audit finding remains.

**Inputs.**

- Target path (default: `dekspec/constitution.md`).

**Outputs.**

- `Status:` field updated to `ACCEPTED`.
- Amendment-Log row appended with Type=Accept.
- Confirmation message + a reminder that LOCKED requires running this skill again with the `--lock` flag (NOT in IB-006's eight-mode catalog — LOCKED transitions live in a separate workflow per the library's guardrails).

**Workflow.**

1. Run `--audit` on the target. If `critical` or `important` findings remain, refuse with the finding list + a "fix these first" recommendation.
2. If clean (or `minor`-only), confirm with the engineer.
3. Flip Status to `ACCEPTED` and bump `Modified:` — read the Constitution's current status, then run `python ../_lib/scripts/artifact_ops.py transition dekspec/constitution.md --from <DRAFT-or-PROPOSED> --to ACCEPTED` (the `--from` is whichever the current status is; surface stderr on non-zero exit and STOP). Do NOT pass `--note` — the Constitution's Amendment Log uses `Type=Accept`, not the script's default `Substantive` row.
4. Hand-append the Amendment-Log row with `Type=Accept` and a one-line summary of what was reviewed at accept time.

**Delegation.** Audit invocation matches Audit Mode (above). The status flip + Modified bump are delegated to `artifact_ops.py transition`; the `Type=Accept` Amendment-Log row is authored in-process.

**End of Accept Mode.**

## Dry-Run Mode

**Invocation:** `/write-constitution --dry-run [other-flag args]`

**Purpose.** Preview the action of any other mode without writing. Useful for impact assessment before a Revise or Resync that would change typed-ref arrays or Article bodies.

**Inputs.**

- Other flag (`--revise`, `--resync`, `--accept`, …) — required.
- The corresponding mode's normal inputs.

**Outputs.**

- The mode's planned changes, presented as a unified diff or per-row delta.
- No file writes.
- Engineer confirmation message: "To apply, re-run without `--dry-run`."

**Workflow.** Run the target mode in a read-only branch — generate the would-be output but route it to stdout instead of disk. For `--audit` (which is already read-only), `--dry-run --audit` is functionally identical; for `--revise` / `--resync` / `--accept`, the dry-run path is meaningful.

**End of Dry-Run Mode.**

## Creation Mode

**Invocation:** `/write-constitution` *(no flag — the default mode)* or `/write-constitution <target-path>`

**Purpose.** Bootstrap a new Constitution at the engineer-specified target path by copying `templates/constitution-template.md` (the IB-001 deliverable) and substituting placeholder tokens. Default target: `dekspec/constitution.md` at the project root.

**Inputs.**

- Target path (optional, default: `dekspec/constitution.md`). If the target already exists, prompt for overwrite confirmation; do not silently clobber.
- Engineer-provided values for placeholder tokens. Standard token set (read the actual template at implementation time to enumerate exactly):
    - `[Project Name]` — the project's display name (e.g., `DekSpec`, `Dektora`).
    - `[YYYY-MM-DD]` — today's date for the `Created:` and `Modified:` fields.
    - Article 1 `see_also` target — usually `dekspec/system-vision.md` at the consumer's repo root.
    - Article 4 placeholder ADR refs (`ADR-NNN` bullets) — the engineer authors the actual citations interactively.
    - Article 7 placeholder ADR + AE refs — same interactive authoring.

**Outputs.**

- New file at the target path, populated with engineer-provided values where placeholders existed.
- Empty Article 8 Amendment Log seeded with one initial-authoring row (Date=today, Type=Substantive, change="Initial authoring", author=engineer name from `git config user.email`).

**Workflow.**

1. Read `templates/constitution-template.md` from the consumer's vendored copy (path: `<repo-root>/dekspec/templates/constitution-template.md` if vendored; otherwise the library's source path for development sessions).
2. Prompt the engineer for each placeholder token; show the placeholder line in context.
3. Substitute tokens; preserve all template comments + structural scaffolding.
4. Write to the target path (after overwrite-confirmation if the file exists).
5. Optionally run `--audit` immediately to confirm the new file parses cleanly + passes T-CONSTITUTION structural checks (it will likely fail L-CONSTITUTION typed-ref checks until the engineer fills in Article 4 / 7 — that's normal; surface as informational, not blocking).

**Delegation.** The Creation mode reads the template via standard `Path.read_text()`; no `dekspec` CLI invocation needed. The optional post-create audit matches Audit Mode (above).

**Match the `/write-ae` Creation-mode substitution pattern.** Read `skills/write-ae/SKILL.md` at implementation time to mirror the prompt shape + substitution flow. Do not invent a new pattern.

**End of Creation Mode.**

## Cross-references

- `skills/write-ae/SKILL.md` — Creation-mode substitution pattern source.
- `skills/write-adr/SKILL.md` — sibling authoring skill (an ADR cited in Articles 4 + 7 is typically authored via this skill).
- `skills/write-evals/SKILL.md` — the v0.40.0 rebuild template that pinned the 8-mode catalog shape.
- `templates/constitution-template.md` — the Creation mode emits a copy of this.
- `tooling/dekspec/fidelity_audit/linkage.py` — the T-CONSTITUTION + L-CONSTITUTION rule functions the Audit mode surfaces via `dekspec doctor`.
- `tooling/dekspec/fidelity_audit/profiles/v1.yaml` — rule-code registration manifest.
- INT-001 / INT-002 / INT-003 / INT-004 — the four Constitution Intents for traceability.

## Approve Mode

`--approve` records a peer-review approval signature on the Constitution under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the Constitution's `## Amendment Log` table — it does **not** flip Status.

Run the shared deterministic helper:

```
python ../_lib/scripts/artifact_ops.py approve <Constitution-path> --target-status <STATUS>
```

`<STATUS>` is the transition the signature authorizes (e.g. `ACCEPTED`). The script resolves the reviewer email from `git config user.email` (override with `--engineer <email>`) and appends a row of the form `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`, then bumps `Modified`. The `T-APPROVAL-GATE` audit rule counts these rows under the `team` profile; the Constitution PROPOSED → ACCEPTED gate requires the most signatures of any artifact kind. Under the default `v1` profile the rule is silent. Inline mode — no fan-out.

## Provisional Mode (Singleton)

`--provisional <incubation-slug>` stages a copy of the Constitution singleton inside `dekspec/provisional/<incubation-slug>/` instead of editing the canonical at `dekspec/constitution.md`. Singletons follow the same CoW discipline as numbered artifacts — the difference is that the `replaces:` field uses the canonical filename rather than a `<KIND>-NNN` ID.

Use this mode when:
- The Constitution change is exploratory and might be abandoned before ratification.
- Multiple Intents in the same incubation folder co-vary with the Constitution change.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding.
2. CoW the singleton via the auto-stage verb:
   ```
   dekspec library cow-stage dekspec/constitution.md --incubation <slug>
   ```
   The verb copies the singleton into `dekspec/provisional/<slug>/<basename>-provisional.md`, stamps `replaces: constitution` in YAML frontmatter, and returns the new path.
3. **Populate the staged copy with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here. The PROVISIONAL banner at the top stays.
4. **Reject `--lock` / `--accept`** in combination with `--provisional`. The singleton's canonical replacement runs as part of the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)), not from this skill body. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)
5. **`--audit` / `--review`** remain available; they operate on the provisional file's content.
6. Closing step: surface the provisional path, the branch (if `dekspec library new-provisional` was used earlier), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

**End of Provisional Mode.**

## Write-Time CoW Guard (INT-082 phase 4)

Before any edit to the Constitution singleton at `dekspec/constitution.md`, consult the CoW guard:

```bash
dekspec library cow-stage dekspec/constitution.md [--incubation <slug>] [--at <repo>]
```

If a pre-ACCEPTED Intent (DRAFT/PROPOSED) claims the singleton's path via Components-affected globs, the verb copies the canonical into the incubation folder + stamps `replaces:`. Edit the staged copy; the canonical stays frozen.

If the singleton is unclaimed, the verb errors unless `--incubation <slug>` is passed explicitly — the canonical-only path is then the normal edit flow.

**Skill discipline.** Inside this skill body, before any canonical `Edit`/`Write` call on `dekspec/constitution.md`:

1. Run `dekspec library cow-stage dekspec/constitution.md` once.
2. On exit 0 (provisional path printed): redirect the edit there.
3. On exit 1 (no claim + no `--incubation`): proceed with the canonical edit (direct-flow legal).

**Audit pairing.** `T-COW-CANONICAL-EDITED` (P2 mechanical) fires on direct-edit bypasses of this guard.

## Common Pitfalls

- Don't author Article 1 as free prose — it is a typed `{summary, see_also}` pointer to `dekspec/system-vision.md`; validate the pointer shape before accepting engineer input.
- Don't cite every ADR / AE in the repo under Articles 4 / 7 — the Constitution carries a *curatorial* set of load-bearing refs; over-citing turns Resync into noise and dilutes the boundary contract.
- Don't flip Status to `ACCEPTED` by hand-editing the field — route the transition through `artifact_ops.py transition` and refuse if any critical/important audit finding remains; bypassing the gate ships an unaudited L0 singleton every agent reads.
- Don't append a prose-only Amendment-Log entry on a `--revise` / `--accept` / `--resync` / class-lane amendment — stamp the correct typed `Type` row (`Revise` / `Accept` / `Resync` / `editorial`) and bump `Modified`; the audit counts these rows.
- Don't direct-`Edit` `dekspec/constitution.md` without first running the CoW guard (`dekspec library cow-stage`) — a pre-ACCEPTED Intent may claim the singleton, and `T-COW-CANONICAL-EDITED` fires on the bypass.
- Don't combine `--provisional` with `--lock` / `--accept` — the singleton's canonical replacement runs in the hand-promote workflow, not from this skill body.
- Don't introduce an undefined Title-Case domain term in any Article — check `dekspec/domain-glossary.md` first; the L10 audit fires on undefined jargon.

## Verification Checklist

- [ ] All eight Articles are present, in canonical order (Project Identity → Technology Stack → Quality Standards → Architecture Principles → Development Workflow → Model Configuration → Boundaries → Amendments).
- [ ] Article 1 `see_also` resolves to `dekspec/system-vision.md`; every Article 4 / 7 `adr_refs` and Article 7 `ae_refs` resolves to an existing on-disk artifact (no broken refs).
- [ ] `Created:` / `Modified:` are valid ISO-8601; `Modified:` was bumped this run for any substantive mode; `Status ∈ {DRAFT, PROPOSED, ACCEPTED}`.
- [ ] Article 8 Amendment Log carries the correct typed row for the mode run (`Substantive` initial-authoring on Creation, `Revise` / `Accept` / `Resync` / `editorial` otherwise) with author resolved from `git config user.email`.
- [ ] Validation ran and exited clean: `dekspec validate --kind constitution <path>` (or the `dekspec doctor` Constitution-filtered fallback); for `--accept`, no critical/important findings remain.
- [ ] Before any canonical edit, the CoW guard (`dekspec library cow-stage dekspec/constitution.md`) was consulted and the edit was routed per its exit code.
- [ ] If `## Class Lanes` was touched, every `(intent_type, risk_tier)` tuple resolves to exactly one row and `effective_model_snapshot` + `effective_corpus_volume` were re-stamped.
- [ ] The mandatory closing step (`dekspec relink`) ran against the repo root after the file was saved.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise the Constitution — Creation, `--accept`, `--revise`, `--resync`). After the artifact file is saved and any index update is done, run:

```
dekspec relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.

## §Class Lanes section (INT-125)

> Added by **INT-125** (LOCKED 2026-05-30) from bead `ds-zhhk`. Promotes the Constitution's lane-routing policy from prose to a structured IR table. Per **AE-004** (IR Schemas) extension.

### Writeable status

The `## Class Lanes` section is writeable through this skill — engineers populate it at Constitution creation and modify it via `--revise` (the routed editorial-amendment mode) for class promotion / demotion. The table is the Constitution IR's `class_lanes` field; the Constraint Compiler extracts it on every parse. (Note: `--amend` is a write-intent-only mode per `_lib/mode_dispatcher.md`; it is **not** a write-constitution mode — use `--revise`.)

### Schema per row

Each row binds `(intent_type, risk_tier)` to a `lane` (enum: `dark` | `canary` | `gated`) plus the budget caps, attempt limits, promotion/demotion thresholds, and the calibration-binding fields `effective_model_snapshot` + `effective_corpus_volume`. See `tooling/dekspec/schemas/constitution.schema.yaml::properties.class_lanes` for the load-bearing schema.

### `--revise` path for class promotion / demotion

When operational evidence (clean-run streak / revert streak) crosses a promotion or demotion threshold, the engineer drives the class transition manually via the routed `--revise` mode:

```
/dekspec:write-constitution --revise <constitution-path> "class-lane promotion: (intent_type, risk_tier) <old-lane> → <new-lane>"
```

The skill walks the engineer through:
1. Identifying the (`intent_type`, `risk_tier`) row to amend.
2. Updating the `lane` field (e.g. `canary` → `gated` on promotion, or `gated` → `canary` on demotion).
3. Re-stamping `effective_model_snapshot` + `effective_corpus_volume` to the current values (the calibration is re-bound to the new operational regime).
4. Appending a row to the typed `amendment_log` IR field via `--revise`'s Amendment-Log step (Nygard MUST-NOT — no prose-only logs): `{date, type: "Revise", change: "class-lane <old>→<new> for (intent_type, risk_tier)", author: "..."}`.

No automation drives the transition. Governance is human work per the dekfactory review synthesis decisions applied at INT-125 authoring.

### Audit rules guarding the section (INT-125 IU-2)

- `T-CONST-CLASS-LANE-COVERAGE-UNIQUE` — every `(intent_type, risk_tier)` tuple resolves to exactly one row.
- `T-CONST-CLASS-LANE-THRESHOLDS-WELL-FORMED` — budget caps + attempts + thresholds are numeric, non-negative.
- `L-CONST-CLASS-LANE-INTENT-EXISTS` — any Intent whose `(type, risk_tier)` tuple does not match a row fires this advisory.

Registered under the `v1` audit profile; consumed by `dekspec audit linkage`.
