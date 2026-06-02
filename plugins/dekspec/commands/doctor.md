---
description: Full DekSpec health check — schema validate + linkage + drift via `dekspec audit doctor`, then the AE-aware T/D/L fidelity audit (inlined here, v0.98.0+). Gold-standard pre-merge gate. Subsumes the previous /doctor-fidelity surface.
allowed-tools: Bash(dekspec audit doctor:*), Bash(dekspec audit:*), Bash(python:*), Bash(git:*), Read, Grep, Glob, Edit, Write, Skill, Agent
argument-hint: [--at PATH] [--dekspec-root DIR] [--json] [--profile PROFILE] [--skip-fidelity] [--fidelity-only] [--fix | --full | --library-self-audit] [scope]
disable-model-invocation: false
---

Run the DekSpec health check in two stages.

**Stage 1 — CLI doctor** (`dekspec audit doctor`): schema validate + linkage + drift. Bash subprocess, fast, deterministic.

**Stage 2 — Fidelity audit** (inlined body below): AE-aware T/D/L family (T10/T11/T12 subtype/boundary/views, D17/D18 AE no-target + no-rationale, L1-ADR-AE through L9 linkage integrity, Phase 2A–2L cross-reference checks).

Both stages run by default. Use `--skip-fidelity` for Stage 1 only, `--fidelity-only` for Stage 2 only. The previous `/doctor-fidelity` slash command was retired in v0.98.0; its body lives here.

## Mode flags

- `--fix` — Stage 2 proposes fixes after the audit pass; engineer approves each before apply.
- `--full` — Stage 2 deep-dive Phase 2F: invokes each artifact-skill's Audit Mode on every matched artifact (slower, authoritative). Default is sampling (3–5 per type).
- `--library-self-audit` — Stage 2 applies library-side path overrides; use when auditing `Dektora/dekspec` itself. Composes with `--fix` and `--full`.
- `--skip-fidelity` — run only Stage 1.
- `--fidelity-only` — skip Stage 1, run only Stage 2 (forwards `--fix`, `--full`, `--library-self-audit`, scope).

Optional scope filter after the flag narrows Stage 2 to one category: `skills`, `templates`, `indexes`, `guide`, `artifacts`, `artifacts-deep`, `coherence`, `duplication`, `landing`, `cascade-discipline`. No filter = full audit.

## Steps

1. Resolve target directory: honour `--at <path>` in `$ARGUMENTS`; default to cwd.
2. Parse stage-control flags from `$ARGUMENTS`:
   - `--skip-fidelity` → run only Stage 1.
   - `--fidelity-only` → skip Stage 1; jump to Stage 2.
3. **Stage 1** (unless `--fidelity-only`): run `dekspec audit doctor <Stage 1 args>` via Bash. Strip stage-control + fidelity-only flags from the args before invoking. Exit code `0` → print `✓ Stage 1 (doctor): CLEAN` then summarise artifact counts from the output. Non-zero → print `✗ Stage 1 (doctor): findings detected`, surface the findings block verbatim. **Stop here unless `--fidelity-only` was passed** — Stage 1 findings usually block Stage 2's meaning.
4. **Stage 2** (unless `--skip-fidelity`): execute the inlined Fidelity Audit body below using the remaining `$ARGUMENTS` (`--fix` / `--full` / `--library-self-audit` / scope). Render the Phase 3 report directly.
5. **Final summary:** report combined status across both stages. If either stage surfaced findings, exit non-zero so CI gates fail.

If the CLI is not on PATH, tell the user to run `pip install git+https://github.com/Dektora/dekspec.git@vX.Y.Z` and stop.

Do not paraphrase findings — pass them through verbatim.

---

# Stage 2 — Fidelity Audit (inlined)

> **Vendored asset paths (INT-097):** Paths below like `dekspec/templates/X-template.md` and `dekspec/dekspec-<doc>.md` reference the consumer-vendored layout. If your install is pip-only (no `scripts/install-dekspec.sh` run), resolve any reference via `dekspec resource template X` or `dekspec resource doc <name>` (consumer-fs override wins when present).

> **AE-aware v2 — DN→AE migration 2026-04-27 (Decision D7).** The rule set below was migrated from the v1 `run-dekspec-fidelity-audit` skill (FROZEN at `dekspec/skills/fidelity-audit/`) with DN→AE language migration applied. Numeric IDs preserved (DN-NNN → AE-NNN). New AE-specific T10–T12 / D17–D18; new linkage rules L1-ADR-AE / L3 / L4 / L5 / L6 / L7a / L7b / L8 / L9. Audit reports filed against v1 retain their original DN terminology and remain reproducible against the frozen skill.

## AE-specific T-checks

These run in addition to T1–T9 (DN-era checks; structurally still valid for AE artifacts).

- [ ] **T10 — Subtype present** (Numbered Governance Rule 1). Every AE declares one primary `## Subtype` from the approved enum: `System`, `Subsystem`, `Container`, `Component`, `Pipeline`, `Data Model`, `Cross-Cutting Concern`, `Platform Concern`, `Interface Surface`, `Workflow / Process`. Missing or off-enum value = **HARD FAIL**.
- [ ] **T11 — Boundary defined** (Numbered Governance Rule 2). Every AE has a `## Boundaries and Non-Goals` section with at least one explicit "inside" item AND one explicit non-goal with a *why* clause. Missing section, empty section, or zero non-goals = **HARD FAIL**.
- [ ] **T12 — Views present or absence justified** (Numbered Governance Rule 3). For AE subtypes `System`, `Subsystem`, `Container`, `Pipeline`, `Platform Concern`: at least one architectural view (Context / Container / Component / Dynamic / Deployment per `architecture-frameworks-reference.md`) is expected. If absent, the `## Views` section must contain an explicit one-paragraph justification. For other subtypes, a view is recommended but not required (advisory).

## AE-specific D-checks

These run in addition to D1–D16. **The DN-era D6 NFR exemption is retired** — D17 supersedes it.

- [ ] **D17 — No measurable quality targets in AE.** AE bodies do not contain inline numeric SLOs, latencies, throughput, capacity, retention, availability targets. Routing rule: such content lives in WS, not AE. Trigger: numeric values with units (`ms`, `s`, `MiB`, `GB`, `tokens`, `req/s`, `%`) outside a citation to a WS. **HARD FAIL.** Allowed: citing the WS that holds the number ("WS-039 §Latency targets").
- [ ] **D18 — No decision rationale in AE.** AE bodies do not contain rationale prose ("we chose X because…", "instead of Y", "the tradeoff is…"). Such content lives in linked ADRs. Trigger: rationale-marker phrases in `Purpose and Scope`, `Responsibilities`, `Key Concepts`, or `Constraints and Quality Notes`. **HARD FAIL.** Allowed: citing the ADR by number ("ADR-044 governs this").

## AE Linkage integrity rules

> **Mechanically enforced by the CLI.** The full L1-ADR-AE to L9 rule set (path-existence, backlink integrity, supersession chains, components-affected resolution, verification-cmd resolution) is implemented in `tooling/dekspec/fidelity_audit/linkage.py` and exposed via `dekspec audit linkage`. Do **not** re-derive these checks by hand. Run, capturing the typed JSON findings and automatically caching proposed fixes:
>
> ```bash
> dekspec audit linkage --json --write-fixes scratch/fixes-cache.json
> ```
>
> Roll the emitted findings into the audit report under their `rule` tag (`L3-WS-AE-EXISTS`, `L6-BACKLINK`, `L7b-INT-COMPONENTS-RESOLVE`, `L9-INT-CMD-RESOLVE`, …). The prose definitions below remain the authoritative human-readable spec of each rule; the CLI is the execution surface. In `--library-self-audit` mode, run with `--at .` against the library repo root.

- [ ] **L1-ADR-AE — ADR → AE linkage.** Every ADR's `## Related Architecture Elements` section lists at least one AE-NNN, AND each listed AE exists in `dekspec/architecture-elements/`. Missing section, empty list, or broken AE reference = **HARD FAIL** (advisory at Audit; blocking at Lock for the ADR).
- [ ] **L3 — WS → AE linkage.** Every WS's `## Related Architecture Elements` section lists at least one AE-NNN, AND each listed AE exists. Missing or broken = **HARD FAIL** at Lock.
- [ ] **L4 — IC → AE linkage.** Every IC's `## Provider AE` is populated and points to an existing AE. `## Consumer AEs` lists at least one consumer AE-NNN OR the explicit value `none — external-facing only` with rationale. Broken provider/consumer AE references = **HARD FAIL** at Lock.
- [ ] **L5 — IB → AE linkage.** Every IB's `Source AEs:` header field is populated with at least one AE-NNN, AND each listed AE exists. Missing, empty, or broken = **HARD FAIL** at Accept.
- [ ] **L6 — Backlink integrity** (warning-level). For each ADR listed in an AE's Linked Artifacts, verify the ADR's `Related Architecture Elements` section names that AE. For each WS listed in an AE's Linked Artifacts, verify the WS's `Related Architecture Elements` section names that AE. (Backlinks update lags during cascade; a missing backlink is a WARNING, not a failure — surface and recommend backfill.)

## Backfill discipline

Pre-migration ADR/WS/IC/IB artifacts (107 across the corpus per the Phase 0 baseline snapshot) are exempt from L1-ADR-AE to L5 hard-fail at Audit time. The backfill rule: **mandatory at next edit**. When `/write-adr --revise`, `/write-ws --revise`, `/write-ic --revise`, or `/write-ibs --revise` runs against a pre-migration artifact, the AE linkage section MUST be populated as part of the revision; advancement to ACCEPTED or LOCKED is blocked until populated. New artifacts from 2026-04-27 forward must populate at write time (HARD FAIL at PROPOSED if missing).

## Intent + Mission T-checks

These run on Intent (`dekspec/intents/INT-NNN-*.md`) and Mission (`dekspec/missions/MSN-NNN-*.md`) artifacts only. They are additive to T1–T12; existing T-checks remain in force on AE / ADR / WS / IC / IB artifacts.

- [ ] **T13 — Intent type from controlled vocabulary.** Every Intent has an `## Intent type` section populated with exactly one value from the enum: `feature`, `bug`, `nfr`, `adr-driven`, `refactor`, `documentation`, `environment`. Missing section, empty section, or off-enum value = **HARD FAIL** at PROPOSED.
- [ ] **T14 — Intent Verification block populated.** Every Intent has a `## Verification` section containing a yaml block with at least one named cmd check (each entry has `name:` and `cmd:`). Missing section, empty yaml block, or zero cmd checks = **HARD FAIL** at PROPOSED. Per-Intent overrides of the type-default Verification predicate are allowed but must be logged in the Intent body.
- [ ] **T15 — Intent Components affected populated as file-glob list.** Every Intent has a `## Components affected` section with at least one entry. Each entry is either a named component from CLAUDE.md §Component → File-Glob Map OR a directly-inlined file glob. Missing section, empty list = **HARD FAIL** at PROPOSED.
- [ ] **T16 — Intent Autonomy from controlled vocabulary.** Every Intent has an `## Autonomy` section populated with exactly one value from the enum: `manual`, `low`, `medium`, `high`. Missing section, empty section, or off-enum value = **HARD FAIL** at PROPOSED.
- [ ] **T17 — Mission near-immutable section populated.** Every Mission has all 8 near-immutable fields populated: `Outcome`, `Mission Verification`, `Out-of-scope`, `Flag strategy`, `Rollback plan`, `Kill criteria`, `Autonomy ceiling`, `First Intent`. Missing field or empty placeholder text (e.g., the literal string `[Outcome]`) = **HARD FAIL** at TODO → ACTIVE transition (refuses `/write-mission --activate`). The `Flag strategy.Flag name` may be `none` provided a one-line rationale is documented. **Mission IR v0.2.0:** `Rollback plan` requires both a `Trigger:` prose paragraph AND a `steps:` fenced yaml list of `{name, cmd}` entries; `Kill criteria` requires a fenced yaml list of `{name, cmd}` entries parallel to Mission Verification. Audit-v2 L9 resolves every `cmd` in those lists; `_legacy_prose` / `_legacy_prose_N` sentinel entries with `echo SKIP_LEGACY_*` cmds are skipped by L9 (they signal human-attended steps).

## Intent + Mission D-checks

These run on Intent prose only.

- [ ] **D19 — No measurable targets in Intent prose.** Intent bodies do not contain inline numeric SLOs, latencies, throughput, capacity, retention, availability targets, or coverage thresholds in `Motivation`, `Desired Outcome`, or prose around the type-specific block. Routing rule: such content lives in WS, not Intent. Trigger: numeric values with units (`ms`, `s`, `MiB`, `GB`, `tokens`, `req/s`, `%`, `pp`) outside a citation to a WS. **HARD FAIL** at PROPOSED. Allowed: citing the WS that holds the number ("WS-NNN BR M defines the Target as ≤ 250 ms"). The Intent's `nfr`-type-specific block (`Metric:` + `Target:`) is **not** subject to D19 — type-specific blocks are exempt by design.
- [ ] **D20 — No decision rationale in Intent prose.** Intent bodies do not contain rationale prose ("we chose X because…", "instead of Y", "the tradeoff is…") in `Motivation`, `Desired Outcome`, or prose around the type-specific block. Routing rule: such content lives in linked ADRs. Trigger: rationale-marker phrases. **HARD FAIL** at PROPOSED. Allowed: citing the ADR by number ("ADR-048 governs this; INT-001 implements its consequences").

## Intent + Mission Linkage rules

- [ ] **L7 — Intent linkage.** Two sub-rules, both required:
   - **L7a (Linked Architecture Elements).** Every Intent's `## Linked Architecture Elements` section lists at least one `AE-NNN` reference, AND each referenced AE exists in `dekspec/architecture-elements/`. Missing section, empty list, or broken AE reference = **HARD FAIL** at PROPOSED.
   - **L7b (Components affected resolves).** Every entry in an Intent's `## Components affected` section resolves to at least one path that exists in the repo. Named components (resolved via CLAUDE.md §Component → File-Glob Map) and directly-inlined globs are both checked. Broken glob with zero matching paths = **HARD FAIL** at ACCEPT.
- [ ] **L8 — Mission ↔ Intent bidirectional linkage.** When a child Intent's `## Mission` section references a Mission, the linkage MUST be bidirectional:
   - The Mission's Intent queue (live section) lists the child Intent.
   - The child Intent's `Mission:` field references this Mission file.
   - The child Intent's Autonomy value ≤ the Mission's Autonomy ceiling (string comparison via the `manual` < `low` < `medium` < `high` ordering).
   Missing backlink in either direction, or Autonomy violation = **HARD FAIL** at the child Intent's `--lock` and at the Mission's `--activate`. Warning-level at the child Intent's `--accept`.
- [ ] **L9 — Verification cmd checks resolve to executable scripts.** Every cmd entry in an Intent's `## Verification` yaml block, and in a Mission's `## Mission Verification` yaml block, resolves to an executable script or recognized tool. Resolution rules: (a) `pytest` (and any flag pattern) resolves if `pytest` is on PATH; (b) `scripts/<name>.sh` resolves if the file exists and is executable; (c) other commands resolve if invocable as `which <first-token>`. Unresolved cmd = **WARNING** at ACCEPT (with the cmd named); **HARD FAIL** at `--testpass` (the predicate must run).

## Decision drift checks (corpus-level sweep)

> **Mechanically enforced by the CLI.** D19 and D20 above are implemented as `D19-INT-NUMERIC-NO-WS-CITE` and `D20-INT-RATIONALE-NO-ADR-CITE` in `tooling/dekspec/fidelity_audit/linkage.py` and run as part of `dekspec audit linkage --json`. Surface the CLI findings as ADVISORY.

- [ ] **D19-CORPUS.** Across all Intents in `dekspec/intents/` (Active queue + Archive), surface any Intent body that contains inline numeric targets (per D19 trigger pattern) that haven't been moved to a WS. Surface as ADVISORY.
- [ ] **D20-CORPUS.** Across all Intents, surface any Intent body that contains rationale prose (per D20 trigger pattern). ADVISORY.

---

## Library self-audit mode

When the engineer passed `--library-self-audit`, apply the path overrides below so the audit walks the library's source-side layout (`Dektora/dekspec`) instead of the consumer-side vendored layout.

| Consumer-side path (default) | Library-side path (`--library-self-audit`) |
|---|---|
| `.claude/skills/<name>/SKILL.md` | `skills/<name>/SKILL.md` |
| `dekspec/templates/*.md` | `templates/*.md` |
| `dekspec/templates/checklists/*.md` | `templates/checklists/*.md` |
| `dekspec/dekspec-operating-guide.md` | `docs/dekspec-operating-guide.md` |
| `dekspec/dekspec-quick-reference.md` | `docs/dekspec-quick-reference.md` |
| `dekspec/project-context.md` | (not present in library; skip) |

Application scope: the overrides apply to **Phase 1 Steps 1, 2, 5** (inventory globs and governance-file reads) and to **Phase 2A / 2D / 2D+** (skill-to-document and operating-guide-and-quick-reference alignment). When a Phase 2A check greps a skill body for a `dekspec/templates/...` path reference and then validates that path exists, library mode translates the matched path from `dekspec/templates/` to `templates/` before the existence check.

The translation is deterministic — do not apply the table by hand. Run the helper, which owns the override table:

```bash
# Translate one or more consumer-side paths to their library-side form:
python "$CLAUDE_PLUGIN_ROOT/scripts/doctor/apply_path_overrides.py" \
  translate dekspec/templates/AE.md .claude/skills/write-ae/SKILL.md

# Print the full override table as JSON:
python "$CLAUDE_PLUGIN_ROOT/scripts/doctor/apply_path_overrides.py" table
```

`translate` emits one JSON object per input path (`{input, library_path, rule, skip}`); a `skip: true` result means the path has no library-side equivalent (e.g. `dekspec/project-context.md`) and the check is omitted. A path that matches no rule passes through unchanged.

Out of scope of the overrides:
- The `dekspec/` self-spec audit (the eat-own-cooking gate from ADR-007). The library has its own `dekspec/` tree by design; all linkage rules run unchanged.
- Phase 2I / 2J / 2K / 2L (coherence / fitness functions / extraction landing / cascade discipline) — all operate over `dekspec/` content.
- Phase 2C (index alignment) — indexes live in `dekspec/` in both layouts.
- Phase 2E (cross-skill consistency) — skills are walked from the inventory in Phase 1, which already carries the override.

When this flag is absent, the audit behaves on consumer-side paths only.

---

## Audit Mode

### Phase 1: Inventory

Collect the current state of all DekSpec assets:

1. **Skills inventory.** Glob `.claude/skills/*/SKILL.md` (or `skills/*/SKILL.md` in `--library-self-audit` mode). For each skill, extract:
   - Name (from frontmatter `name` field)
   - Model (from frontmatter `model` field)
   - Flags (from frontmatter `argument-hint` field)
   - Allowed tools (from frontmatter `allowed-tools` field)
   - Whether the skill defines an `--audit` mode (Phase 2F depends on this)

2. **Template inventory.** Glob `dekspec/templates/*.md` and `dekspec/templates/checklists/*.md` (or `templates/*.md` and `templates/checklists/*.md` in `--library-self-audit` mode). For each, extract:
   - Template name
   - Sections/headers
   - Status field default value

3. **Index inventory.** Read:
   - `dekspec/adr-index.md`
   - `dekspec/working-spec-index.md`
   - `dekspec/architecture-elements-index.md`
   - `dekspec/interface-contract-index.md`

   Extract all artifact references (IDs, paths, statuses).

4. **Artifact inventory.** Glob all artifacts:
   - `dekspec/adrs/ADR-*.md`
   - `dekspec/architecture-elements/AE-*.md` and `dekspec/architecture-elements/*/*.md`
   - `dekspec/working-specs/WS-*.md`
   - `dekspec/interface-contracts/IC-*.md`
   - `dekspec/impl-briefs/{queued,active,completed}/*.md`

   For each, extract: ID, title, status, created date, modified date.

5. **Governance files.** Read:
   - `dekspec/dekspec-operating-guide.md` (in `--library-self-audit` mode: `docs/dekspec-operating-guide.md`)
   - `dekspec/dekspec-quick-reference.md` (in `--library-self-audit` mode: `docs/dekspec-quick-reference.md`)
   - `dekspec/project-context.md` (in `--library-self-audit` mode: not present; skip)
   - `CLAUDE.md`
   - `AGENTS.md`
   - `dekspec/domain-glossary.md` (if exists)
   - `dekspec/guidance-and-corrections.md` (if exists)
   - `dekspec/audits/spec-fitness-functions.md` (if exists — registry consumed by Phase 2J)

6. **Convergence evidence.** `git log --oneline -n 30 dekspec/` — note any commits matching `convergence`, `Phase 4`, `extract`, `→ WS-`, `→ IC-` in the last 14 days. Phase 2K runs when such evidence is present.

### Phase 2: Cross-Reference Checks

Run ALL of the following checks. Skip checks outside the scope filter if one is set.

#### 2A. Skill-to-Document Alignment

For each skill:

- [ ] **Skill references valid template paths.** Grep each skill for `dekspec/templates/` paths. Verify each path exists on disk. (In `--library-self-audit` mode, translate `dekspec/templates/` → `templates/` before the existence check.)
- [ ] **Skill references valid checklist paths.** Grep for `checklists/` references. Verify each exists.
- [ ] **Skill name matches directory name.** Frontmatter `name` must match the directory name under `.claude/skills/` (or `skills/` in `--library-self-audit` mode).
- [ ] **Skills listed in AGENTS.md match actual skill directories.** Every skill in AGENTS.md must have a corresponding `.claude/skills/<name>/SKILL.md` (or `skills/<name>/SKILL.md` in `--library-self-audit` mode). Every skill directory must be listed in AGENTS.md.
- [ ] **Skill flags in AGENTS.md match frontmatter argument-hint.** Compare the flags listed in AGENTS.md's table with the flags in the skill's `argument-hint`.
- [ ] **Model policy compliance.** Compare each skill's `model` field against CLAUDE.md's Agent Model Policy. Flag any mismatch.
- [ ] **No phantom skill references.** Grep the operating guide, CLAUDE.md, AGENTS.md, and all templates for `/skill-name` patterns. Verify each referenced skill exists.

#### 2B. Template-to-Artifact Alignment

For each template:

- [ ] **Template sections match actual artifacts.** For each artifact type, read 2-3 actual artifacts and compare their section headers against the template. Flag sections present in artifacts but not in the template (custom additions) or in the template but not in artifacts (missing sections).
- [ ] **Status lifecycle consistent.** Verify all artifacts use the same status values: DRAFT → PROPOSED → ACCEPTED → LOCKED. Flag any artifact with a status not in this set.
- [ ] **Date integrity.** For each artifact, verify Modified >= Created. Flag violations.

#### 2C. Index-to-Artifact Alignment

For each index file:

- [ ] **Every indexed artifact exists on disk.** For each row in the index table, verify the linked file path exists.
- [ ] **Every artifact on disk is indexed.** For each artifact file found by glob, verify it has a corresponding row in the index.
- [ ] **Index status matches artifact status.** Read each artifact's Status field and compare with the index table's Status column.
- [ ] **Index dates match artifact dates.** Compare Created and Modified dates between index and artifact.
- [ ] **Index ID format is consistent.** Verify all IDs follow the NNN zero-padded convention.
- [ ] **Git-aware index update verification (SI-A1).** For each commit that modified an artifact's `## Modified` field, verify the same commit also modified the artifact's canonical-index row — **ONLY IF** the index row's Modified date is OLDER than the artifact's new Modified date. Flag only stale-index cases. This check is only meaningful when running the audit post-commit in a clean working tree. In `--fix` mode, the audit may propose the missing index-row update as a fix commit.

#### 2D. Operating Guide Alignment

The operating guide is the master document of the DekSpec system. Highest-drift-risk file — long, narrative, first to desync when skills change.

**Large-doc discipline (SI-FA-2).** For any audited document exceeding **1500 lines** (the operating guide and the domain glossary always qualify), Phase 2D MUST walk the full file rather than spot-checking. If the auditor's working context cannot hold the file, dispatch a narrow-scope sub-agent with a template-reference checklist and pull only the sub-agent's findings back. Spot-check-only is explicitly disallowed for `dekspec/dekspec-operating-guide.md` and `dekspec/domain-glossary.md`. (In `--library-self-audit` mode, the operating guide path is `docs/dekspec-operating-guide.md`; the glossary path is unchanged at `dekspec/domain-glossary.md`.)

**Structure and references:**
- [ ] **Repository structure diagram matches reality.** Parse the operating guide's directory tree and verify each listed path exists. Flag phantom paths and paths that exist but aren't listed.
- [ ] **Skill names in operating guide match actual skill names.** Grep for `/skill-name` references. Verify each matches an actual skill directory.
- [ ] **No stale tool/command references.** Grep for `br`, `bv`, `cm`, `ubs`, `dcg` commands. Verify each is defined somewhere (AGENTS.md, CLAUDE.md, or operating guide).
- [ ] **Role definitions in project-context.md align with operating guide references.**

**Format and schema alignment:**
- [ ] **Bead format matches write-beads skill.** Compare the operating guide's bead description/format with the canonical format in `/write-beads`. Flag any divergence.
- [ ] **IB format matches write-ibs skill.** Compare the operating guide's IB description with the IB Content Rules in the skill.
- [ ] **Template references are current.** For each template path mentioned in the operating guide, verify the template exists and its sections match what the guide describes.

**Workflow and process alignment:**
- [ ] **Workflow steps match skill capabilities.** For each workflow step described, verify the corresponding skill has the described mode/flag.
- [ ] **Walkthrough traces match current skill phases.** Read each walkthrough end-to-end. Flag any action that contradicts the skill's rules.
- [ ] **Layer hierarchy rules are consistent** across guide, CLAUDE.md, AGENTS.md. Flag contradictions.
- [ ] **Status lifecycle rules are consistent** between guide and skill `--lock`/`--unlock` behavior.
- [ ] **Cascade rules are consistent** between guide and skill cascade behavior (`--resync`, `--rebuild`, downstream impact checks).

**Content freshness:**
- [ ] **No references to deleted skills or artifacts.** Grep the full operating guide. Verify each still exists.
- [ ] **Example commands are current.** For each code block or inline command, verify the syntax matches the current tool's interface.
- [ ] **Terminology matches domain glossary.** Grep for key domain terms and verify they match the glossary's canonical definitions.

#### 2D+. Quick Reference Alignment

The quick reference (`dekspec/dekspec-quick-reference.md`; in `--library-self-audit` mode: `docs/dekspec-quick-reference.md`) is a 5-10 minute onboarding document. It must stay short, clear, and accurate.

- [ ] **Skills table is complete.** Every skill in `.claude/skills/` (or `skills/` in `--library-self-audit` mode) appears in the quick reference's Skills table. No phantom skills listed.
- [ ] **Skills table flags match.** The Common Flags table lists only flags that actually exist across skills.
- [ ] **Pipeline steps match current skill capabilities.**
- [ ] **Layer hierarchy and source-of-truth statements match operating guide and CLAUDE.md.**
- [ ] **Key Principles are accurate.** Each principle stated is still true and consistent with the operating guide.
- [ ] **"Where Things Live" paths exist.** Every path in the directory listing exists on disk.
- [ ] **No bloat.** The quick reference should not exceed ~150 lines.

#### 2E. Cross-Skill Consistency

- [ ] **Shared concepts use consistent terminology.** Check that all skills use the same names for:
  - Fidelity Audit (not "quality audit" or "completeness check")
  - Conflict Detection (not "conflict check" or "contradiction scan")
  - Decomposition Checklist (not "decomposition check" or "split analysis")
  - IB Status field format: `**Status:** PROPOSED` vs `**Status:** ACCEPTED` (legacy `Engineer review` checkbox retired)
  - Escalation Protocol wording
- [ ] **Context check wording is consistent.** Compare the context check block across all skills that have one.
- [ ] **Coupling/cohesion checks are only in skills that need them.**
- [ ] **All skills with `--audit` mode follow the same reporting format.**
- [ ] **All skills with `--revise` mode follow the same revision plan format.**
- [ ] **Artifact skills with `--lock`/`--unlock` follow the standard state transition rules.** For `write-ws`, `write-ic`, `write-ae`, `write-adr`, `write-sp`, `write-system-vision`: Lock is ACCEPTED → LOCKED, Unlock is LOCKED → PROPOSED. **Known exceptions — not drift:** `write-intent` has a richer lifecycle (`IMPLEMENTING → TESTPASS → MERGED → LOCKED`); its `--lock` is **MERGED → LOCKED** by design. `write-mission` has no `--lock`/`--unlock` — its lifecycle runs through `--activate` / `--complete` / `--kill` / `--supersede`.

#### 2F. Artifact Body Checks — Delegation Protocol

**Ownership model (delegation, not mirror).** Per-artifact body checks — structural completeness, drift patterns (D-series), layer-consistency (L1 / L2), testability, domain constraints, extraction landing — are **owned by the artifact's own skill**. This phase **invokes the artifact-skill's Audit Mode** and rolls up findings with the skill's tag preserved.

**Default sampling behavior** (no `--full` flag): spot-check 3–5 artifacts per type. Record in the Summary that sampling was used.

**Full sweep** (`--full` or scope `artifacts-deep`): for every artifact glob-matched in Phase 1, invoke the artifact-skill's Audit Mode and inherit its checks:

| Artifact | Invocation | Inherited check families |
|---|---|---|
| **ADRs** | `/write-adr --audit <path>` | D1–D9 drift (fenced-code, impl-paths, signatures, numbered-procedures, schema-tables, magic-number-rationale, per-type-dispatch, algorithm-math, key-files-section) + L1-AE / L1-GLOSSARY / L1-VISION consistency |
| **Architecture Elements** | `/write-ae --audit <path>` | T1–T9 (sections, header, title, body-length, exclusions, silent-domain-coherence, expertise-record, modified-discipline, meta-reference) + D1–D16 (includes D13 mirror anti-pattern, D14 audit-ruler framing, D15 SSoT overreach, D16 Open-Issues spec-vs-code classification) + L1-ADR-SCOPE + L1-ADR-STALE + L1-ADR body-not-AL + L1-GLOSSARY + L1-WS-EXISTS + DS1–DS3 |
| **Working Specs** | `/write-ws --audit <path>` | T1–T9 + D1–D5 + L1-ADR-AE series + E1–E4 extraction-landing + T-coverage behavioral-reachability + DS1–DS3 + BR-testability + Failure-detection-observable + Domain-constraint-populated + Contract-section-integration-test-scope |
| **Interface Contracts** | `/write-ic --audit <path>` | Contract completeness, error-semantics coverage, consistency-guarantees-bounded, downstream-consumer-citation |
| **Implementation Briefs** | `/write-ibs --audit <path>` | Golden I/O presence, Test Promotion Criteria, Escalation Protocol verbatim, Decomposition Checklist, coupling/cohesion |

**Roll-up format.** Each finding returned enters the audit's Phase 3 table with:

- **Source tag prefix:** `[<SKILL>:<CHECK-ID>]` — e.g., `[DN:D15]`, `[WS:E3]`, `[ADR:D6]`, `[IB:golden-io-missing]`.
- **Severity mapping:** skill's CRITICAL → audit CRITICAL; skill's IMPORTANT or MAJOR → audit IMPORTANT; skill's MINOR or MODERATE → audit MINOR.
- **`fix_kind` tag:** inherit from the artifact skill if provided; else derive per the fix_kind rules in Phase 3.

**Fallback for missing Audit Mode.** When an artifact skill lacks an `--audit` mode, fall back to sampling with the skill's template sections as the check list, and emit one IMPORTANT finding tagged `[fidelity:2F-missing-audit-mode]`.

**What Phase 2F does NOT duplicate.** No copy of D-series / T-series / L-series / E-series check text lives here. If a check is missing in an artifact skill's Audit Mode, the fix is to add it there.

#### 2G. Header Metadata Freshness

Artifact headers `## Modified` and `## Amendment Log` must co-advance. For each artifact with an Amendment Log section:

- [ ] **SI-01 — Modified date >= latest Amendment Log entry date.** Parse the `## Modified` field's date and the date of the most recent row in the Amendment Log. Flag if Modified is older than the latest entry. Fix kind: **mechanical**.
- [ ] **SI-02 — Modified annotation freshness.** The parenthetical annotation after the Modified date should describe the most recent meaningful revision. Heuristic: minor editorial entries may not displace a substantive annotation, but substantive revisions should update both. Severity: IMPORTANT. Fix kind: **semantic**.
- [ ] **SI-A1 — Cross-file cascade completeness.** For each artifact with an Amendment Log, scan every recent entry (last 14 days) for citations of other artifacts. For each cited artifact, verify its Modified date ≥ the Amendment Log entry's date. Severity: IMPORTANT. Fix kind: **mechanical**.

#### 2H. Glossary Consistency

- [ ] **2H.1 Sample-drift check (SI-FA-3).** Sample N=10 glossary terms uniformly at random. For each: grep the corpus for usages and flag any usage where the surrounding sentence redefines or contradicts. Findings are recorded as GGC candidates (via `/write-ggc`), not hard-stop failures. Fix kind: **semantic**.
- [ ] **2H.2 Deprecated-alias sweep** (mechanical, hard-fail). Parse `dekspec/domain-glossary.md` for the deprecated-aliases list. Grep the corpus for each deprecated alias. Any occurrence outside an Amendment Log historical note = IMPORTANT. Fix kind: **mechanical**.
- [ ] **2H.3 Composite-term auto-promotion.** A multi-word phrase consistently capitalized or backticked appearing in ≥2 artifacts but absent from glossary → file a `/write-ggc` candidate.

#### 2I. Cross-Artifact Coherence

- [ ] **2I.1 Governing-ADR ↔ WS coherence (SI-FA-1).** For every WS citing an ADR as "governing", diff the WS's normative claims against the ADR's for the same concepts. Disagreement = `[fidelity:2I-gov-adr-ws-conflict]`. Severity: CRITICAL. Fix kind: **semantic**.
- [ ] **2I.2 ADR ↔ IC API-pinning coherence.** An ADR whose Decision pins an external API / boundary / library version MUST have a corresponding IC. Orphan pins emit `[fidelity:2I-adr-orphan-pin]`. Severity: IMPORTANT. Fix kind: **semantic**.
- [ ] **2I.3 WS ↔ IC boundary clarity.** A WS describing behavior crossing an IC-governed boundary must reference the IC by ID and not duplicate the interface spec in prose. Verify citation; if WS duplicates IC interface spec verbatim, emit `[fidelity:2I-ws-ic-duplicated-boundary]`. Severity: IMPORTANT. Fix kind: **semantic**.
- [ ] **2I.4 AE → WS/IC vision-extraction completeness.** For each AE with recent extraction evidence (Amendment Log entries matching `extract`, `→ WS-`, `→ IC-`, `Phase 4.x` within the last 14 days): verify the AE body retains only vision + pointer. Residual content = `[fidelity:2I-dn-extraction-residual]`. Severity: IMPORTANT. Fix kind: **semantic**.
- [ ] **2I.5 ADR supersession cascade closure.** For each ADR with Status `SUPERSEDED` or `DEPRECATED`: grep the corpus for citations. Any WS/AE/IC/IB citing the old ADR without a replacement note or superseding-ADR citation in the same paragraph = `[fidelity:2I-adr-supersession-stale-citation]`. Severity: IMPORTANT. Fix kind: **semantic**.

#### 2J. Sibling-SSoT Duplication Scan (Fitness Functions)

Mechanical scans consuming `dekspec/audits/spec-fitness-functions.md` as the check registry. Each invariant defines a canonical home, a grep pattern, scopes, and an expected-count or citation-presence rule. Findings emitted as `[fitness:F-NN]`.

**Execution protocol.** For each invariant:

1. Apply the invariant's grep pattern across the scopes it declares.
2. For **bounded count** invariants, compare hits against expected count. Miscount = IMPORTANT.
3. For **unbounded with citation** invariants, verify every occurrence has the canonical-home citation within the configured distance (default 5 lines). Missing citation = IMPORTANT.
4. For **forbidden pattern** invariants, any non-Amendment-Log hit = CRITICAL.

**Invariant schema fields** (read from `spec-fitness-functions.md`): `id`, `fact`, `canonical_home`, `pattern`, `scopes`, one of (`expected_count` | `unbounded_with_citation` | `forbidden`), `severity`, optional `citation_distance_lines`.

**Extensibility.** New invariants added to `spec-fitness-functions.md` under the same schema auto-register on next run.

#### 2K. Extraction Landing Verification (post-convergence, E-series)

Runs when convergence evidence is present (Phase 1 Step 6 detects commits matching `convergence` / `Phase 4` / `extract` in the last 14 days; OR when L1/L2 Amendment Log entries cite extractions). For each (source, destination) pair:

- [ ] **2K.1 E1 landing-present.** Extract N=2 distinctive tokens from the source's pre-extraction snapshot (via `git show <pre-extraction-commit>:<source>`). Grep destination for those tokens. Missing = `[fidelity:2K-e1-landing-missing]`. Severity: CRITICAL.
- [ ] **2K.2 E2 landing-complete.** Diff the pre-extraction source snapshot against the destination. Flag any invariant, formula, edge case, failure mode, or numeric constant present in source but absent in destination. Partial landing = `[fidelity:2K-e2-landing-partial]`. Severity: CRITICAL. Fix kind: **semantic**.
- [ ] **2K.3 E3 structural-landing.** The extracted content must live in a structured section that downstream tests/IBs can consume — Business Rule row, Failure Behavior row, Domain Constraint row, Contract row, Governing Formula block, Eval Hook, Golden I/O. Prose-only landing = `[fidelity:2K-e3-prose-only-landing]`. Severity: CRITICAL (downstream-unreachable).
- [ ] **2K.4 E4 source-trimmed + backref-valid.** Source ADR/AE after extraction must retain only decision/vision + citation. Parallel copy remaining = `[fidelity:2K-e4-source-not-trimmed]`. Severity: IMPORTANT. Separately: grep downstream consumers for citations still pointing at the emptied source location; any = `[fidelity:2K-e4-downstream-stale-backref]`. Severity: IMPORTANT.

#### 2L. Cascade Scope Discipline

- [ ] **2L.1 Cascade exclusion zones.** `dekspec/audits/**`, `dekspec/archaeology/**`, and `.beads/**` are NEVER cascade targets. Scan Amendment Log entries across all L1/L2 artifacts for phrases indicating cascade into these zones. Any hit emits `[fidelity:2L-cascade-scope-violation]`. Severity: IMPORTANT.
- [ ] **2L.2 Open-Issues spec-vs-code classification (D16).** For each ADR / AE / WS / IC with an Open Issues section, classify every entry:
  - **spec-coverage-gap** (acceptable) — "WS-NNN is TODO", "ADR for X pending", "glossary needs term Y", "IC boundary not yet specified".
  - **code-gap** (forbidden in L1/L2) — "code does X but spec says Y", "currently in code at `<path>:<line>`", observed-vs-specified behavior divergence.

  Code-gaps in L1/L2 artifacts must migrate to `dekspec/divergences/DIV-NNN-*.md` or to `br` issues. Violations emit `[fidelity:2L-open-issue-code-gap]`. Severity: IMPORTANT. Grandfathered entries (pre-2026-04-24): AE-004, AE-037.

### Phase 3: Report

Present findings in severity-grouped tables with source-tag-prefixed IDs and a `Fix` column carrying the `fix_kind` tag. ALWAYS produce all three tables (show "None found" for empty tables).

**Finding ID format.** `<severity-letter><N> [<source-tag>]` — e.g., `C1 [DN:D15]`, `I3 [WS:E3]`, `I7 [fidelity:2I.2]`, `M4 [fitness:F-05]`.

**`fix_kind` values:**

- **mechanical** — deterministic transform over file content. Examples: grep-replace after rename; stale `## Modified` date → advance to `max(existing, latest-Amendment-Log-date)`; missing index row → auto-append from artifact metadata; deprecated-alias replacement.
- **semantic** — requires human judgment. Examples: glossary redefinition; supersession cascade touching Decision text; spec drift where the "right" answer depends on architectural intent; contradictions where either side could be authoritative; E3 prose-only-landing.

```
DEKSPEC FIDELITY AUDIT — [date]
Scope: [full / filtered scope]
Mode: [sampling | --full]
Files scanned: [N]
Artifact skills invoked (Phase 2F): [list of skills that ran --audit]

## CRITICAL — would cause agents to produce wrong output

| # | Issue | Files | Impact | Fix |
|---|---|---|---|---|
| C1 [DN:D15] | [description] | [file1], [file2] | [what goes wrong] | [fix_kind] — [proposed fix text] |

(None found)

## IMPORTANT — creates friction, inconsistency, or maintenance burden

| # | Issue | Files | Impact | Fix |
|---|---|---|---|---|
| I1 [fidelity:2I.2] | [description] | [file1], [file2] | [what goes wrong] | [fix_kind] — [proposed fix text] |

(None found)

## MINOR — cosmetic, naming, or nice-to-have

| # | Issue | Files | Impact | Fix |
|---|---|---|---|---|
| M1 [fitness:F-05] | [description] | [file1], [file2] | [what goes wrong] | [fix_kind] — [proposed fix text] |

(None found)

## Summary

Critical: [N] | Important: [N] | Minor: [N]
Mechanical fixes: [M] | Semantic fixes: [S]
Coverage: [sampling note if applicable — "Phase 2F sampled 3–5 per type; --full required for authoritative per-artifact coverage"]
[One-sentence overall assessment]
```

### Phase 4: Fix (only in `--fix` mode)

> [!TIP]
> **High-Efficiency Caching (`--write-fixes` / `--read-fixes`)**
> To prevent running expensive `SpecGraph.load` and sweep rule checks twice during review and fix phases:
> 1. In Phase 3 (Review), run the audit and write mechanical fix proposals to a cache file:
>    ```bash
>    dekspec audit linkage --write-fixes scratch/fixes-cache.json
>    ```
> 2. In Phase 4 (Fix), apply the cached fixes instantly by reading the file and passing `--apply`:
>    ```bash
>    dekspec audit linkage --read-fixes scratch/fixes-cache.json --apply
>    ```

> [!IMPORTANT]
> **Orchestration Rule (Zero-Redundant Scan)**:
> When the review step has already run in Phase 3 and generated `scratch/fixes-cache.json`, you **MUST NOT** kick off a fresh compile or full scan. Directly load the cached fixes and run the apply command.

If `--fix` flag is set, after presenting the report:

1. Group fixes by severity (critical first, then important, then minor).
2. For findings delegated from an artifact skill (source tag `[<SKILL>:<CHECK-ID>]` where `<SKILL>` is not `fidelity` / `fitness`), route the fix through that skill's Fix / Revise mode rather than editing directly. Example: a `[DN:D15]` SSoT-overreach fix runs via `/write-ae --revise <path>` on the affected AE.
3. For findings owned here (source tags `[fidelity:*]` and `[fitness:*]`), propose the fix inline and apply it.
4. For each fix, present:
   ```
   FIX [C1 DN:D15]: [short description]
   Owning skill: /write-ae
   Files to modify: [list]
   Change: [what will be changed]
   Route: [direct | delegated to /write-ae --revise]

   Apply? (yes / no / skip)
   ```
5. Wait for engineer approval on each fix before applying.
6. For fixes that require a judgment call, present options instead of a single fix.
7. After all fixes are applied (or skipped), re-run the relevant checks. Report:
   ```
   FIX RESULTS:
     ✅ C1 [DN:D15]: fixed — [description]
     ✅ I2 [fidelity:2I.2]: fixed — [description]
     ⏭️  I3 [WS:E3]: skipped by engineer
     ❌ M1 [fitness:F-05]: fix applied but check still fails — [description]

   Remaining issues: [N]
   ```

## SCOPE FILTERS

| Filter | Limits Stage 2 to |
|---|---|
| `skills` | Skill files only (`.claude/skills/`) |
| `templates` | Templates and checklists (`dekspec/templates/`) |
| `indexes` | Index files (adr-index, working-spec-index, etc.) |
| `guide` | Operating guide, CLAUDE.md, AGENTS.md |
| `artifacts` | Phase 2F sampling (3–5 per type) |
| `artifacts-deep` | Phase 2F per-artifact Audit Mode (== `--full artifacts`) |
| `coherence` | Phase 2I cross-artifact coherence only |
| `duplication` | Phase 2J sibling-SSoT / fitness-function scan only |
| `landing` | Phase 2K extraction-landing verification only |
| `cascade-discipline` | Phase 2L cascade scope and Open-Issues classification only |
| (none) | Full audit — all categories |

## WHEN TO RUN

- After modifying skills, templates, or the operating guide
- After adding or removing a skill
- After changing artifact status lifecycle or naming conventions
- After a convergence run (especially `--full` + `landing` scope)
- Before a major spec-writing or IB-generation session
- Periodically (monthly) to catch drift

## Rules

- **Read-only by default.** Without `--fix`, Stage 2 NEVER modifies any file.
- **Delegation, not duplication.** Per-artifact body checks live in the artifact's skill. If a check is missing in an artifact skill's Audit Mode, fix it there and re-run.
- **No false positives.** Verify every finding by reading the actual files before reporting.
- **Cite specific lines.** Every finding must reference specific file paths and line numbers.
- **Don't flag intentional divergence.** Only flag differences that indicate drift or error.
- **Prioritize correctly.** CRITICAL = an agent would follow wrong instructions. IMPORTANT = friction or maintenance burden. MINOR = cosmetic or edge case. When in doubt, downgrade.
- **Be efficient.** Use Grep for cross-reference checks rather than reading every file end-to-end.
- **Include the positive.** If a category has zero issues, say so explicitly.
- **Sampling is disclosed.** When Phase 2F runs in sampling mode (default), the Summary must say so and must note that `--full` is needed for authoritative coverage.
- **Grandfathering is logged, not hidden.** Grandfathered exceptions listed at the end of Phase 3 under a "Grandfathered" subsection.

## Provenance

- **SI-01, SI-02** (Phase 2G): header-metadata freshness, added 2026-04-19; engineer-verified 2026-04-20 at SE convergence iter-4.
- **SI-A1** (Phase 2C): git-aware index update verification, added 2026-04-20 (SI-A2); refined 2026-04-20 (SI-A8).
- **SI-FA-1** (Phase 2I.1): governing-ADR ↔ WS coherence, added convergence-v2 iter-2 (2026-04-21).
- **SI-FA-2** (Phase 2D large-doc discipline): added convergence-v2 iter-2 (2026-04-21).
- **SI-FA-3** (Phase 2H.1): glossary sample-drift, added convergence-v2 iter-2 (2026-04-21).
- **Phase 2F delegation protocol** (2026-04-24 refactor): replaced prior 5-bullet artifact-content spot-check with delegation to the artifact-skill's Audit Mode.
- **Phase 2I cross-artifact coherence** (2026-04-24 refactor): 2I.1 SI-FA-1 promoted; 2I.2–2I.5 extracted from the ADR convergence audit's cross-artifact findings.
- **Phase 2J sibling-SSoT duplication scan** (2026-04-24 refactor): consumes `dekspec/audits/spec-fitness-functions.md` as the invariant registry.
- **Phase 2K extraction-landing verification** (2026-04-24 refactor): mirrors the E1–E4 rubric baked into `/write-ws` Audit Mode.
- **Phase 2L cascade-scope discipline** (2026-04-24 refactor): 2L.1 cascade exclusion zones from `/write-ae` Revise Mode step 6a; 2L.2 Open-Issues spec-vs-code classification from AE audit D16.
- **`--library-self-audit` mode** (2026-05-15, ds-a4h).
- **Inlined into `/doctor`** (2026-05-28, v0.98.0): the standalone `doctor-fidelity` skill was retired; its body now lives here as Stage 2 of the unified `/doctor` command. The Stage 1 + Stage 2 split is preserved, but the operator surface is one. `apply_path_overrides.py` moved from `plugins/dekspec/skills/doctor-fidelity/scripts/` to `plugins/dekspec/scripts/doctor/`.
