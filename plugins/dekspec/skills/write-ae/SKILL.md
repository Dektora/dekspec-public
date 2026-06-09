---
name: write-ae
description: Create an Architecture Element (AE) for a coherent architectural slice — system, subsystem, container, component, pipeline, data model, cross-cutting concern, platform concern, interface surface, or workflow/process. Use when a key component or cross-cutting behavior needs a vision-level Layer-1 document before working specs are written. Replaced the legacy `write-design-note` skill (DN→AE migration 2026-04-27); the legacy alias was removed 2026-05-09.
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --audit | --review | --accept | --approve | --lock | --unlock | --revise] [description or path to architecture element]
related_skills: [write-sv, write-adr, write-ws, write-ic, write-intent]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

> **Skill rename — DN→AE migration 2026-04-27.** This skill was renamed from the legacy `write-design-note` to `write-ae`. The artifact it produces is an **Architecture Element (AE)**, the post-migration replacement for the legacy Design Note (DN). The mandatory new pieces are: (a) **subtype selection** from the C4-aligned enum (System / Subsystem / Container / Component / Pipeline / Data Model / Cross-Cutting Concern / Platform Concern / Interface Surface / Workflow / Process), (b) a **classifier/router** that refuses to write an AE for ADR/WS/IC/IB-shaped input and redirects to the right skill, and (c) three new audit T-checks (**T10 subtype present**, **T11 boundary defined**, **T12 views present or absence justified**) plus drift checks **D17/D18** that replace the retired D6 NFR exemption (see "AE-specific additions" below).
>
> Pre-existing T1–T9 and D1–D16 audit checks are ported from the v1 (DN-era) audit framework; their numeric IDs and severities carry over unchanged. Deep DN→AE language migration throughout the SKILL.md prose was applied 2026-04-27 by bd-mvx0; surface-level references now use AE / Architecture Element vocabulary throughout. The migration banner text "DN-era" remains where it is the correct historical descriptor for the rule set being ported.
>
> For the AE subtype enum, framework reference (arc42 chapter mapping, C4 view types), and routing keyword tables, see `dekspec/architecture-frameworks-reference.md`.

Write, lock, or unlock an Architecture Element.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill requires clear vision-level thinking about a subsystem or concern. Prior conversation context can degrade quality by introducing implementation-level bias.
>
> First message → proceed. Prior history → ask "context may affect AE quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-ae the awareness scoring pipeline and how it feeds context injection

Author a Pipeline-subtype AE for the scoring stage: what it consumes, what it
produces, its boundary against the injection orchestrator, and the ADRs that
govern it. Keep numerics out — route any SLO targets to a WS.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Creation Mode**.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Lock mode** — `--lock` flag. Skip to **Lock Mode**.
- **Unlock mode** — `--unlock` flag. Skip to **Unlock Mode**.
- **Accept mode** — `--accept` flag. Skip to **Accept Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **Review mode** — `--review` flag. Skip to **Review Mode**.
- **Revise mode** — `--revise` flag. Skip to **Revise Mode**.
- **Approve mode** — `--approve` flag. Skip to **Approve Mode**.
- **Creation mode** — no flag. Proceed to **Input**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--accept`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--unlock`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `dekspec:ae-author`
- **substantive_modes**: [Creation (default), `--accept`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--unlock`]
- **bundle_list** (Step 1 context):
  1. Template path — `dekspec/templates/architecture-element-template.md`.
  2. Methodology references — `docs/dekspec-methodology.md` §4 Layer 1 (Architecture Elements); `dekspec/dekspec-operating-guide.md` §AE authoring (if present); `dekspec/architecture-frameworks-reference.md` (C4 + arc42 subtype mapping, routing keyword tables).
  3. System vision — `dekspec/system-vision.md` (required for L1-VISION).
  4. Domain glossary — `dekspec/domain-glossary.md` (required for L1-GLOSSARY).
  5. Related artifacts from the spec graph (paths only — subagent reads what it needs): `dekspec/architecture-elements-index.md` — and for Creation, compute the next AE-NNN id deterministically by running `python ../_lib/scripts/artifact_ops.py next-id ae` (surface stderr on non-zero exit); for Creation, also every existing AE under `dekspec/architecture-elements/` + the ADR index + the WS index; for `--accept` / `--revise`, the target AE path + run `python ../_lib/scripts/bundle_related.py --for <target-AE-path> --include adr,ic,ib --backlinks` to get the artifacts the AE references and the artifacts that reference it (judge which are relevant, bundle those) + any WSes it cites + (for `--revise`) the engineer's notes payload.
  6. Engineer guidance — `$ARGUMENTS` verbatim, including structured cues (subtype hint, classification hint).
  7. Constraints — full T / D / L1 / DS rule set from §Audit Mode (T1–T12, D1–D18, L1-ADR, L1-ADR-STALE, L1-AE, L1-GLOSSARY, L1-VISION, L1-WS-EXISTS, L1-ADR-SCOPE, DS1–DS3) **plus** the §Rules block (Extraction Default-Home Table, writing-time heuristics, anti-patterns, subtype enum, classifier/router rules).
- **expected_output_path**: `dekspec/architecture-elements/AE-NNN-<slug>.md` (Creation) or the input path (`--accept` / `--revise`; subagent edits in place).
- **validation**: `dekspec check validate <output-path>` + mode-specific post-checks (Creation: index row added, Status PROPOSED, D1–D18+L1 Verification clean; `--accept`: PROPOSED→ACCEPTED + index updated + blocking checks all green; `--revise`: full T/D/L1/DS re-run + §Revise Mode Step 6a cascade grep + Open Issues logged + reset to PROPOSED if previously ACCEPTED/LOCKED). Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — on non-zero exit, surface verbatim and stop, do not silently retry.

**End of Fan-Out Mode.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-ae"
one_line:   "Create, audit, review, revise, accept, lock, or unlock Architecture Elements (replaced legacy /write-design-note; legacy removed 2026-05-09)"
modes:
  - { flag: "", args: "<description>", description: "Create a new Architecture Element from the engineer's description. First runs the classifier/router gate (§AE Classifier/Router) — refuses and redirects if the input is ADR/WS/IC/IB-shaped. Then prompts for the mandatory subtype. Runs Step 4a Verification (D1–D14 + T10/T11/T12 + L1) on the draft before Save; refuses to advance to PROPOSED if any check fails without explicit engineer override." }
  - { flag: "--audit", args: "<AE-path>", description: "Read-only quality check: template (T1–T12), drift (D1–D16 + D17/D18), cross-artifact consistency (L1-ADR, L1-ADR-STALE, L1-AE, L1-GLOSSARY, L1-VISION, L1-WS-EXISTS, L1-ADR-SCOPE), downstream impact (DS1–DS3 advisory)." }
  - { flag: "--review", args: "<AE-path>", description: "Walk through open issues interactively. Present each issue with context and a recommendation. Engineer resolves, defers, or dismisses each." }
  - { flag: "--revise", args: "<AE-path> <notes>", description: "Incorporate engineer review notes into the AE. Notes can be inline text or a path to a notes file. Re-runs T+D+L1+DS after applying changes." }
  - { flag: "--accept", args: "<AE-path>", description: "Promote a PROPOSED AE to ACCEPTED (PROPOSED → ACCEPTED). Runs full T+D+L1 final audit; refuses if any T / D / L1-ADR / L1-ADR-STALE / L1-VISION / L1-WS-EXISTS / L1-ADR-SCOPE check fails. L1-GLOSSARY is advisory at Accept (§9 row 1). DS-series is advisory at Accept (§9 row 2)." }
  - { flag: "--lock", args: "<AE-path>", description: "Lock an ACCEPTED AE (ACCEPTED → LOCKED). Runs full pre-lock audit. Rejects if any T / D / L1 check fails, INCLUDING L1-GLOSSARY (blocking at Lock per §9 row 1) AND DS-series (blocking at Lock per §9 row 2)." }
  - { flag: "--unlock", args: "<AE-path>", description: "Unlock a LOCKED AE (LOCKED → PROPOSED). Runs downstream impact assessment. Requires a reason." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing an Architecture Element section-by-section. Distinct from --review (audits existing) and from no-flag creation (assumes the author already knows AEs)." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-ae the awareness scoring pipeline and how it feeds injection"
  - "/write-ae --audit dekspec/architecture-elements/AE-005-mind-map.md"
  - "/write-ae --review dekspec/architecture-elements/AE-005-mind-map.md"
  - "/write-ae --revise AE-005-mind-map.md \"clarify relationship to shadow graph, add exclusion for real-time updates\""
  - "/write-ae --accept dekspec/architecture-elements/AE-005-mind-map.md"
  - "/write-ae --lock dekspec/architecture-elements/AE-005-mind-map.md"
  - "/write-ae --unlock dekspec/architecture-elements/AE-005-mind-map.md"
  - "/write-ae --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: AE (Architecture Element)
- **template_path**: `templates/architecture-element-template.md`
- **methodology_section**: §4 Layer 1 of `docs/dekspec-methodology.md` plus `docs/architecture-frameworks-reference.md` for the subtype enum
- **exemplar_paths**: `dekspec/architecture-elements/AE-001-dekspec.md` (System subtype), `dekspec/architecture-elements/AE-006-skills-library.md` (Cross-Cutting Concern)
- **required_sections**: [Status, Subtype, Classification, Linked Artifacts, Implements, Purpose and Scope, Responsibilities, Boundaries and Non-Goals, Relationships and Dependencies, Views, Constraints and Quality Notes, Open Questions, Amendment Log]

Skill-specific structural checks to surface as Open Issues: T11 (missing inside/non-goal), T12 (missing Views for a subtype that requires them), missing Subtype enum value.

**Skill-unique routing gate:** when prompting for Subtype, route the engineer's input through the AE Classifier/Router below before accepting. The router confirms the engineer's description is AE-shaped (not ADR/WS/IC/IB-shaped) — if the input belongs to a different artifact kind, redirect the engineer to the correct skill rather than continuing the AE ritual.

## AE Classifier/Router

**Run this gate before Creation Mode begins.** Read the engineer's input and decide whether it is genuinely AE-shaped, or whether it should route to a different skill. The classifier uses keyword pattern matching on the input; the routing rules below are the canonical source (see also `dekspec/architecture-frameworks-reference.md` §Routing keyword tables).

### Route to AE when input is dominated by

- Nouns and phrases describing system slices, services, components, responsibilities, boundaries, dependencies, topology, workflows, or interactions.
- Requests to *describe* what a subsystem is or how it fits into the larger system.
- Requests for architectural views or structural descriptions.

→ Proceed with Creation Mode.

### Route to ADR when input is dominated by

- Phrases such as "we chose", "we decided", "instead of", "tradeoff", "because", "consequence", "alternative".
- Comparative reasoning between options.
- Explicit design-choice narratives.

→ Stop and tell the engineer: "This input reads as a *decision* (rationale, alternatives, tradeoffs). It belongs in an ADR, not an AE. Run `/write-adr` instead. If you want, I can pre-frame the description for the ADR — say so."

### Route to WS when input is dominated by

- Phrases such as "must", "shall", "target", "p95", "availability", "throughput", "retention", "auditability", "SLO", "SLA", "latency".
- Acceptance criteria and measurable thresholds.
- Statements that can be validated by tests, monitoring, audits, or benchmarks.

→ Stop and tell the engineer: "This input reads as a *measurable requirement* (numbers, thresholds, acceptance criteria). It belongs in a Working Spec, not an AE. Run `/write-ws` instead."

### Route to IC when input is dominated by

- Endpoints, payloads, request/response semantics, compatibility rules, schema promises, provider/consumer concerns, contract guarantees.

→ Stop and tell the engineer: "This input reads as a *boundary contract* (interface semantics, compatibility). It belongs in an Interface Contract, not an AE. Run `/write-ic` instead."

### Route to IB when input is dominated by

- Rollout plans, migration steps, sequencing, tasks, work packages, implementation approaches, cutover planning.

→ Stop and tell the engineer: "This input reads as an *implementation plan* (tasks, sequencing, rollout). It belongs in an Implementation Brief, not an AE. Run `/write-ibs` instead."

### Mixed input

If the input contains both AE-shaped material and other-shape material, keep the AE-shaped portion in the new AE and explicitly recommend that the engineer extract the other portions into the appropriate sister artifact. Do not silently absorb non-AE material into the AE body.

## AE Subtype Selection (mandatory)

Before drafting begins, prompt the engineer for the AE's primary subtype. **No AE may be authored without a subtype** (Numbered Governance Rule 1; audit T10).

Subtype enum (post-D11, C4-aligned for structural; DekSpec extensions for the rest):

| Subtype | Used for |
|---|---|
| **System** | The highest-level system under discussion (C4 Software System). |
| **Subsystem** | A logical grouping of multiple Containers above the strict C4 hierarchy (DekSpec convenience). |
| **Container** | A deployable / runnable unit — service, web app, data store, runner (C4 Container). |
| **Component** | Code/functionality grouped inside a Container; not independently deployable (C4 Component). |
| **Pipeline** | A sequenced flow of operations; may live inside one Container or span multiple. |
| **Data Model** | A canonical structure (tensor, record schema, knowledge-graph shape) that flows through the system. |
| **Cross-Cutting Concern** | A concern that spans multiple Containers / Components (security, consistency, observability, lifecycle). |
| **Platform Concern** | Operational / deployment topology and runtime environment (C4 Deployment perspective). |
| **Interface Surface** | Boundary between Containers; typically the home of one or more ICs. |
| **Workflow / Process** | A dynamic flow described in scenario / sequence form (C4 Dynamic perspective). |

If the engineer's input clearly maps to one subtype, propose it explicitly and ask for confirmation. If the mapping is ambiguous, list the candidates with a one-line rationale for each and ask the engineer to pick.

## Audit Mode

Read-only quality check on an existing architecture element. Applies the refined T / D / L1 / DS checklist from `dekspec/audits/dn-audit-process-proposal-2026-04-24.md` §3.

**Schema-vs-linkage division of labor (ds-52p, D-14).** The audit splits into two layers: structural shape (T10 subtype, T13/T15/T16 schema-typed fields) is enforced by `jsonschema` validation *at parse time* — invalid IR shapes never reach the audit. Graph-relational rules (T11/T12 content-presence, D17/D18 prose drift, L1/L6 cross-artifact linkage) run in `linkage.py` against the parsed IR set. When this skill reports a T10 failure, that's actually a schema-validation error surfaced at parse time; when it reports a T11/T12/D17/D18 failure, that's a `linkage.py` rule emitting against the IR graph. Both layers are part of the audit's contract; the split affects only where the check lives in code.

### Input

Path to the architecture element.

### Steps

1. Read the architecture element at the provided path.
2. Read the domain glossary (`dekspec/domain-glossary.md`) for L1-GLOSSARY check.
3. Read the system vision (`dekspec/system-vision.md`) for L1-VISION check.
4. For each ADR referenced in the AE body, read the ADR once and cache in-context. For each AE referenced, note it (read only if not already in context). For each WS referenced, verify the file exists at `dekspec/working-specs/WS-NNN-*.md` and is not `TODO` (unless Open Issues explicitly flags it as pending).
5. Run the three-series checklist:

**T-series (T1–T9) — Template / Style.** Each item reports pass/fail and cites the offending line range when failed.

- [ ] **T1** — All template sections are populated — no placeholders, no "TODO" in the body, no empty sections. `Open Questions / Planned Follow-ons` must be present (even if empty or with the sentinel "*None currently contemplated.*"). Optional sections (`Runtime Behavior`, `Data and State`, `Deployment / Operational Shape`) may be omitted if not applicable to the AE's subtype.
- [ ] **T2** — `Status`, `Subtype`, `Classification`, `Created`, `Modified` are all filled with concrete values. `Subtype` is one of `System | Subsystem | Container | Component | Pipeline | Data Model | Cross-Cutting Concern | Platform Concern | Interface Surface | Workflow / Process`. `Classification` is one of `Core | Supporting | Generic`.
- [ ] **T3** — Title is noun-phrase, specific, not verb-first (AEs are about *what*, not *what-was-decided*). *Trigger:* title line starting with verb — regex `^# AE-\d+:\s*(Use|Adopt|Select|Require|Implement|Choose|Replace|Migrate|Pin|Add|Remove|Return|Serve|Route|Inject)\b` indicates ADR-shaped title; move to ADR.
- [ ] **T4** — Document length ≤ 2 pages of rendered markdown (≈ 200–350 lines body excluding amendment log). Flag if body ≥ 350 lines or ≤ 50 lines.
- [ ] **T5** — `Boundaries and Non-Goals` has at least one explicit exclusion under "Outside the boundary (non-goals)" with a *why* clause. Zero exclusions is a hard fail. Ten-plus exclusions with paragraph-length justifications is a soft fail.
- [ ] **T6** — `What Success Looks Like` items are observable states. No bare numeric-latency claims without a AE-034 citation (unless the value defines the architecture, per the D6 exemption).
- [ ] **T7** — `Relationships and Dependencies` uses the four-part structure (`Consumes:` / `Produces:` / `Depends on:` / `Consumed by:`) **or an explicit variant that covers all four directions** (e.g., Below / Governing ADRs / Interface Contracts / Above / Cross-cutting), with all four populated (use "None" explicitly when empty). Optional `**Indirect governing ADRs:**` sub-bullet may appear — indirect ADRs listed under this sub-bullet are exempt from the L1-ADR-SCOPE 2–8 count.
- [ ] **T8** — `Amendment Log` follows the compressed one-line-per-entry format (per Δ-SQ-17, 2026-04-22). Multi-paragraph narrative entries added after 2026-04-22 are a fail; historical entries before that date are grandfathered. **Same discipline applies to the `## Modified` field:** a single ISO-8601 date with no parenthetical narrative, no multi-date stack. Narrative about what changed belongs in AL entries (one line each), not in the Modified field. Multi-line / narrative-prefix Modified fields dated after 2026-04-22 fail T8.
- [ ] **T9** — No `## Key Files` section, no `Key files:` bullet, no raw implementation file paths (`*.py`, `*.ts`, `*.rs`, `services/…`, `api_server/…`, `databases/…`, `src/…`, `model_server/…`). Spec/contract paths in `dekspec/…` are fine. **Meta-reference detection:** path tokens trip regardless of whether they appear backticked, in prose, or in a meta-reference explaining that the paths were moved (e.g. "the `api_server/__init__.py:673` file-path references were migrated" still fails). Reworded paraphrases ("Cortex monolith file-path references") are the correct pattern for talking about moved content.

**AE-specific T-checks (added 2026-04-27 with the DN→AE migration):**

- [ ] **T10 — Subtype present** (Numbered Governance Rule 1). The AE declares one primary `## Subtype` populated from the approved enum: `System`, `Subsystem`, `Container`, `Component`, `Pipeline`, `Data Model`, `Cross-Cutting Concern`, `Platform Concern`, `Interface Surface`, `Workflow / Process`. *Trigger:* missing `## Subtype` section, empty value, or value not in the enum. **Hard fail.**
- [ ] **T11 — Boundary defined** (Numbered Governance Rule 2). The AE has a `## Boundaries and Non-Goals` section with substantive content — at least one explicit "inside the boundary" item AND at least one explicit "outside the boundary (non-goal)" item with a *why* clause. *Trigger:* missing section, empty section, zero non-goals, or non-goals without rationale. **Hard fail.**
- [ ] **T12 — Views present or absence justified** (Numbered Governance Rule 3). For AE subtypes `System`, `Subsystem`, `Container`, `Pipeline`, `Platform Concern`: at least one architectural view (Context / Container / Component / Dynamic / Deployment per `architecture-frameworks-reference.md`) is normally expected in the `## Views` section. If absent, the section must contain an explicit one-paragraph justification of why no view materially clarifies this AE. For `Component`, `Data Model`, `Cross-Cutting Concern`, `Interface Surface`, and `Workflow / Process` subtypes, a view is recommended but not required. *Trigger:* missing `## Views` section, empty section without justification, on a structural-subtype AE.

**D-series (D1–D18) — Drift.** Each item reports *file path, line number, category, one-line extract, recommended destination.*

> **Mechanical trigger pre-pass.** Run `scripts/d_check_triggers.py <ae-path>` first; surface stderr on a non-zero exit (exit 2 = file unreadable). It emits JSON `{rule: [{line, match}], ...}` for the pure-regex D-checks — **D1** (fenced blocks), **D2** (math markers / inline math), **D3** (callable + class names, library-call blacklist, CamelCase / ALL_CAPS regex, HuggingFace model paths), **D6** (number-with-unit near a hedge word), **D13** (mirror-phrase list), **D14** (audit-ruler / canonical-process headers), **D15** (single-authoritative-reference overreach phrases). The script reports *candidate* hits only — you still judge each hit true-vs-false positive (e.g. a CamelCase domain term in the glossary allowlist is a false positive). The remaining D-checks (**D4, D5, D7, D8, D9, D10, D11, D12, D16, D17, D18**) need section scoping or genuine judgment and are evaluated by reading the body directly, as below.

- [ ] **D1** — No fenced code blocks in the body. (Amendment Log table is fine.) *Trigger:* any triple-backtick fenced block other than the amendment-log table.
- [ ] **D2** — No mathematical formulas, derivations, inline math, or invariant narratives. *Trigger:* LaTeX markers, inline `$…$`, prose formulas (`B_k = total_budget × tier_percentage[k]`), invariant narratives ("bfloat16 is a strict subset of float32"; "within each channel, consecutive position IDs should be monotonically increasing").
- [ ] **D3** — No function / method / class / callable names. Concept shortnames are fine. *Trigger:* any backticked name containing `()`, any prose use of `def` / `async def` / `class`, backticked symbol-style names matching a Python / JS / Rust identifier pattern, library-function references. **Library-call blacklist (grep prefixes):** `torch.`, `numpy.`, `asyncio.`, `psycopg2`, `psycopg3`, `pymupdf4llm.`, `tiktoken.`, `transformers.`, `huggingface_hub.`. **HuggingFace-path pattern:** `<Org>/<model>-<variant>-<bits>` (e.g. `SandboxMountain/Qwen3.5-9B-4bit`) — these model-identity strings belong in config / constants manifest / code, never in a AE body. **CamelCase class-name regex:** `\b[A-Z][a-z]+([A-Z][a-z]+){1,}\b` (catches `ImageUrlBlock`, `ModelEntry`, `ToolDefinition`) with glossary-term allowlist. **ALL_CAPS module-constant regex:** `\b[A-Z][A-Z0-9_]{3,}\b` (catches `INFERENCE_LOCK`, `DATABASE_URL`, `COOCCURRENCE_LAYER`) with glossary-term allowlist.
- [ ] **D4** — No step-by-step procedures of 3 or more items. *Trigger:* ordered lists with ≥ 3 items in `Key Concepts` or `What This Is`, any `(1) …; (2) …; (3) …;` prose sequence, any "Phase N" heading with sub-mechanics.
- [ ] **D5** — No per-type / per-mode / per-modality dispatch enumerations with mechanics. *Trigger:* dispatch enumerations where at least one branch lists a specific library, call, or transformation.
- [ ] **D6** — No seed-default configuration values paired with justifying prose, except where the value defines the architecture. *Trigger:* any number with a unit (`s`, `ms`, `MiB`, `GB`, `KB`, `GiB`, `tokens`) paired with 1+ sentence of justification, OR any dimensionless number with rationale. **Hedge-language signal:** numbers preceded or followed by `currently`, `typically`, `roughly`, `~`, `seed default`, `default`, `per ADR-NNN`, `in the near term`, or range language (`tens of`, `hundreds of`, `low thousands`) are high-confidence tunable values — flag these even when the justification is short. The hedge is the tell: architecture-defining values are not hedged. **Exempt: DNs with Category `non-functional requirements`** (§9 row 3).
- [ ] **D7** — No schema / dtype / kwarg tables. Design-level comparison tables (Option A vs Option B, Consumes/Produces summary) are fine. *Trigger:* column headers match the implementation-specificity list (`dtype`, `shape`, `field`, `kwarg`, `return`, `hidden_dim`, `seq_len`, `bit_depth`, `signature`, `endpoint`, `HTTP status`).
- [ ] **D8** — No code-gap punch-lists in `Open Issues` or the body. *Trigger:* Open Issues text references a line number in an implementation file, phrases like "currently in code at …" / "code does X but spec says Y", specific HTTP status mismatches. **Grandfathered: AE-004 and AE-037 pre-2026-04-24 entries (§9 row 5).**
- [ ] **D9** — No process-narrative in `Amendment Log` or body. *Trigger:* entries longer than ~2 lines after 2026-04-22 grandfathering date, any entry containing phrases like "Expertise audit pass", "autonomy L3 @ 0.85", "Pipeline Sequencing Analyst Pass", "skill-led revision pass".
- [ ] **D10** — No stale superseded-approach text kept "for history" in the live body. *Trigger (section-scoped regex):* sentences containing `historical`, `previously`, `prior design`, `superseded`, `formerly`, `legacy` in the **positive-framing sections** `Key Concepts` / `What This Is` / `What Success Looks Like`. These words ARE acceptable inside negative exclusion bullets in `What We Are Not Building` ("Not the prior wave-count solver — continuous ratios…"). Scope the grep to the positive-framing sections only; do not flag hits inside `What We Are Not Building` negative-exclusion bullets.
- [ ] **D11** — No motivational restating of the System Vision. *Trigger:* two consecutive paragraphs where neither names the subsystem's distinguishing technical mechanism.
- [ ] **D12** — No "Expected Operating Range" / capacity table in an L1 vision document. *Trigger:* subsection header matching `Expected Operating Range`, `Capacity`, `Load Profile`, `Scale Assumptions`. **Exempt: DNs with Category `non-functional requirements`** (§9 row 3).

- [ ] **D13 — Mirror-for-reader-convenience anti-pattern** (added 2026-04-24 from DN-convergence lessons). Flag any AE body sentence containing the phrases `mirrored here for reader convenience`, `duplicate of`, `repeated here from`, `for completeness`, `exact values mirrored from`, `mirrored from ADR-`, `mirrored from WS-`, `mirrored from DN-`. These are always a signal that a value's authoritative home is elsewhere and the AE is duplicating rather than citing it. The mirror drifts; the citation stays correct. *Precedent:* AE-009 tier-percentage mirror (19.9 / 32.9 / 23.6 / 14.6 / 9.0 %) labeled "mirrored here for reader convenience — ADR-051 is the authoritative home" — dropped during Phase 3 D6 consolidation.

- [ ] **D14 — Audit-ruler / canonical-process framing** (added 2026-04-24 from DN-convergence lessons). Flag any subsection header matching `Canonical Process`, `Audit Ruler`, `Canonical Procedure`, `Canonical Algorithm`, `Reference Implementation`, `Authoritative Specification`, `Authoritative Procedure`. These framings reliably smuggle procedural L2/L3 content into L1 vision documents — a section that can be used as an audit ruler is a *behavioral contract*, which belongs in a Working Spec. DNs describe why the contract matters; WSs *are* the contract. *Precedent:* AE-031 §Canonical Process (Audit Ruler) — a 9-step block extracted to WS-033 during Phase 4.1.

- [ ] **D15 — Single-authoritative-reference overreach** (added 2026-04-24 from DN-convergence lessons). Flag DN-body phrases claiming contract authority: `single authoritative reference`, `the full contract`, `exhaustive specification`, `the complete definition of`, `the behavioral contract for`, `single source of truth for`, `authoritative specification`, `complete specification`. DNs are authoritative for *vision and principles*; Working Specs are authoritative for *behavior*; Interface Contracts are authoritative for *boundaries*. A DN claiming "authoritative contract" status is almost certainly overstepping. *Precedent:* AE-020 §What This Is opening — "This architecture element is the single authoritative reference for the full dtype contract across all three boundaries" — rewritten during Phase 4.5 with dtype mechanics extracted to IC-014.

- [ ] **D16 — Open Issues classification (spec-coverage-gap vs code-gap)** (added 2026-04-24 from DN-convergence lessons). Each Open Issue is classified by its text shape:
    - **Spec-coverage-gap (acceptable in AE Open Issues):** starts with `WS-NNN is TODO`, `IC-NNN is TODO`, `ADR for <X> is pending`, `<spec> has not been written yet`, `needs a formal spec`. These are design-level questions about spec completeness.
    - **Code-gap (must migrate to divergence ledger or `br`):** contains `code does X but spec says Y`, `currently in code at <path>:<line>`, `violates ADR-NNN at`, `silent fallback at`, `implementation drifts from`, specific HTTP status mismatches. These are code-review observations, not design-level questions.
    - **Severity classification:** spec-coverage gaps are PASS; code-gap items are FAIL (D16 hit). Grandfathered exemptions: pre-2026-04-24 entries (§9 row 5). When a code-gap is flagged, recommend migration to `dekspec/divergences/DIV-NNN-*.md` (oracle-vs-built) or a new `br` issue (spec-vs-code bug).

**AE-specific D-checks (added 2026-04-27 with the DN→AE migration; replace the DN-era D6 NFR exemption per Decision D7):**

- [ ] **D17 — No measurable quality targets in AE** (replaces the DN-era D6 NFR exemption). AEs do not contain measurable quality targets (numeric SLOs, latencies, throughput, capacity, retention, availability) inline. Such content lives in Working Specs, not AEs (per the conversion guide §"Quality / NFR handling" routing rule). The DN-era exemption that allowed AE-034 (`category: non-functional requirements`) to carry inline numeric targets is **retired** under the AE model — measurable targets extract to a WS, and the AE shell describes the architectural framing without numbers. *Trigger:* numeric targets paired with units (`ms`, `s`, `MiB`, `GB`, `tokens`, `req/s`, `%`) appearing in the AE body outside a citation to a WS. **Hard fail.**
- [ ] **D18 — No decision rationale in AE.** AEs do not contain decision-rationale prose ("we chose X because…", "instead of Y", "the tradeoff is…"). Such content lives in linked ADRs. *Trigger:* sentences containing rationale-marker phrases (`we chose`, `we decided`, `instead of`, `tradeoff`, `consequence of choosing`, `alternative`) in `Purpose and Scope`, `Responsibilities`, `Key Concepts`, or `Constraints and Quality Notes`. **Hard fail.** *Allowed:* citing an ADR by number ("ADR-044 governs the merge strategy") is fine; the rationale text itself stays in the ADR.

**L1-series — Cross-Artifact Consistency.**

- [ ] **L1-ADR** — For each ADR referenced by number, read the ADR and verify either (a) full consistency, or (b) explicit acknowledgment of the deviation **in the AE body (`Key Concepts` or `What We Are Not Building`)** — Amendment Log acknowledgment does not satisfy this check (Q5 resolution, §3.3). Silent contradictions are a fail.
- [ ] **L1-ADR-STALE** (Q7 resolution) — For each ADR referenced in the AE body, read the ADR's `Status` field. If the referenced ADR is `SUPERSEDED` or `DEPRECATED`, raise a MINOR flag. When SUPERSEDED, the check also reports the replacement ADR from the `*Superseded by:*` field so the fix is one-step. The skill also runs a subject-phrase heuristic: match cited ADR slug against subject keywords in the same sentence (e.g., "tier-percentage formula" near "ADR-042" → flag candidate mis-citation).
- [ ] **L1-AE** — For each other AE referenced by number, verify the referenced DN exists, is not DEPRECATED, and its claims in the referenced area match.
- [ ] **L1-GLOSSARY** — Every domain term used in the AE body matches the domain glossary. The AE must not redefine a term, use a deprecated alias, or coin a new term without a glossary entry (composite-term auto-promotion per Q4 policy: if a term appears in ≥2 DNs, flag as "promote via `/write-ggc`" rather than as an AE defect). **Deprecated-alias sweep:** grep the AE body against the glossary's deprecated-alias list directly (e.g. `API Server` → `Cortex Service`, `chat model server` → `Cooccurrence Service`, `embedding model server` → `Semantic Embedding Service`). A hit on any deprecated alias is a fail regardless of whether the alias is also in current prose. **Advisory at Accept, blocking at Lock (§9 row 1).**
- [ ] **L1-VISION** — If the DN's scope touches top-level system claims, verify no contradiction with `dekspec/system-vision.md`.
- [ ] **L1-WS-EXISTS** — For each WS referenced by number, verify the file exists and is not `TODO` (unless Open Issues flags it as pending). Section-name mismatches are ADVISORY. **TODO-stub detection:** if the linked WS exists and is not formally `TODO` but its body is under 50 lines (effectively a stub — content hasn't been written), flag as an ADVISORY "linked WS is a stub — the citation may not point to meaningful content." Precedent: WS-025 Injection Pipeline Orchestration was ~30 lines of pointer-only content despite not being TODO status.
- [ ] **L1-ADR-SCOPE** — Scope-discipline check: the AE references between 2 and 8 **direct-body** ADRs. **Direct-body** is defined as: unique ADRs cited anywhere in the AE *minus* the set of ADRs listed under an explicit **Indirect governing ADRs:** sub-bullet of §Relationship to Other Components. Indirect-listed ADRs are fully exempt from the count regardless of where else they appear; the structural check below is what flags dual-citation. Fewer than 2 direct-body ADRs = too narrow. More than 8 direct-body ADRs = too broad — split the AE. **Duplicate-citation count:** report each ADR's citation count separately. Repeated citations (e.g. ADR-005 cited 4×) count once for the scope bound but signal potential consolidation. **Indirect-ADR compliance (structural check):** verify each ADR under **Indirect governing ADRs:** carries a one-line rationale explaining why it is indirect (governing a peer concern rather than this AE's direct scope). An ADR must not appear in both the body and the indirect sub-bullet; dual-citation is a MINOR structural fail — the body citation should be removed, leaving only the indirect listing.

**DS-series (DS1–DS3) — Downstream Impact (advisory at Audit / Accept; blocking at Lock per §9 row 2).**

- [ ] **DS1** — Grep all WSs, ICs, and IBs for references to this AE. If any cite a AE section that no longer exists after a revision, flag as a cascade failure.
- [ ] **DS2** — Grep all downstream artifacts for the DN's distinctive terminology. If a downstream artifact uses the term in a way that contradicts the DN's definition, flag.
- [ ] **DS3** — If the AE has been modified since the last cascade, verify every downstream artifact's last-modified date is ≥ the DN's last-modified date, OR the DN's amendment log states "no downstream changes needed" for that edit.

6. Report using the shape defined in proposal §4:

```
AUDIT: [path]
Status: [current status]

Template/Style (T1–T9):
  Passed: [N/9]
  Failed:
    - T[N] [line range]: [one-line description]

Implementation / Layer drift (D1–D16):
  - [D[N] — line [range]] [one-line extract]
    → Recommend: [concrete destination per the Extraction-Destination Table — see §Rules "Where does the drifted content go?"]
  - [… or: "None found."]

Layer-1 consistency (L1):
  L1-ADR: [pass / specific fail with ADR and deviation]
  L1-ADR-STALE: [pass / list of SUPERSEDED citations + replacements]
  L1-AE: [pass / specific fail]
  L1-GLOSSARY: [pass / specific term violations — note advisory at Accept, blocking at Lock]
  L1-VISION: [pass / specific fail]
  L1-WS-EXISTS: [pass / specific fail]
  L1-ADR-SCOPE: [N direct-body ADRs — within range / too narrow (<2) / too broad (>8)]

Downstream impact (DS1–DS3):
  DS1: [pass / specific cascade failure]
  DS2: [pass / specific terminology drift]
  DS3: [pass / specific stale downstream artifact]

Structural-overlap:
  [If another DN fully absorbs this AE's territory, flag as merge candidate.]

Severity (mechanical classification per proposal §14 Starting action step 6):
  [MAJOR / MODERATE / MINOR / CLEAN]
```

Read-only — no changes made.

**End of Audit Mode.**

## Review Mode

Walk through open issues interactively — present each issue with context and a recommendation, resolve with the engineer one at a time.

Arguments: the architecture element path.

### Steps

1. Read the architecture element at the provided path
2. Parse the `## Open Issues` section. Collect all unchecked items (`- [ ]`).
3. If no unchecked items exist: "No open issues in [path]. Nothing to review." **End of Review Mode.**
4. Read the artifact's What This Is, Key Concepts, and Relationship to Other Components sections for context.
5. Read governing ADRs referenced in the architecture element to check for cross-artifact relevance.
6. Present a summary:
   ```
   REVIEW SESSION: [path]
   Status: [current status]
   Open issues: [N] ([M] blocking, [K] non-blocking)
   
   Starting guided review...
   ```
6.5. **Spec-Reviewer dispatch** (shared `reviewer_mode` path — see [`_lib/reviewer_mode.md`](../_lib/reviewer_mode.md)). This ADDS an adversarial Spec-Reviewer pass alongside the open-issue loop; it does NOT replace it. Perform the shared four-step dispatch:
   a. Load the `spec-reviewer` ContextSpec: `from dekspec.constraint_compiler.parser import parse_context_spec; context_spec = parse_context_spec("dekspec/context-specs/role-spec-reviewer.md")` (`context_spec["role_identity"] == "spec-reviewer"`).
   b. Take the `ReviewerAE` artifact this `--review` mode already holds (the architecture element at the provided path; the caller owns this IO, the dispatcher is IO-free).
   c. Dispatch through the shared surface: `from dekspec.spec_review.reviewer import Reviewer; findings = Reviewer().dispatch(context_spec, artifact)` (`-> list[Finding]`, per IC-016).
   d. Present each returned `Finding` to the engineer at its severity (default `P2` — approval-blocking, not auto-merge) as additional review items alongside the open issues below. Do not reshape the records; they route into the AE-003 surface via the `SPEC-REVIEW` audit-rule family (`dekspec.spec_review.reviewer` → `spec_review_rules`).
7. For each unchecked issue, in order:
   a. Present the issue:
      ```
      ───────────────────────────────────────
      ISSUE [N/total]: [issue description]
      Source: [source]
      Severity: [blocking / non-blocking]
      ───────────────────────────────────────
      ```
   b. Analyze the issue against the current artifact content:
      - Has this issue already been addressed by changes to the artifact since it was logged?
      - Is the issue still valid given the current state of governing ADRs and related artifacts?
      - What would resolving this issue require — a text change to this artifact, a structural change, or an upstream change to another artifact?
   c. Present a recommendation:
      ```
      RECOMMENDATION: [resolve / revise artifact / defer / dismiss]
      
      [Specific explanation — what to change and why, or why to defer/dismiss]
      
      [If resolve or revise: show the proposed text change]
      ```
   d. Wait for the engineer's response.
   e. Based on response:
      - **Resolve** — check off the issue, append resolution: `- [x] [Issue] — **Source:** ... — **Severity:** ... — **Resolved:** [today] [resolution summary]`
      - **Revise** — apply the agreed change to the artifact body, then check off the issue with resolution note
      - **Defer** — leave unchecked, optionally update the issue description with new context
      - **Dismiss** — check off with strikethrough and dismissal note: `- [x] ~~[Issue]~~ — **Source:** ... — **Severity:** ... — **Dismissed:** [today] [reason]`
8. Update **Modified** date.
9. Present summary:
   ```
   REVIEW COMPLETE: [path]
   
   Resolved: [N]
   Dismissed: [N]
   Deferred: [N]
   
   [If blocking issues remain]: ⚠️  [N] blocking issues remain — artifact should not advance status.
   [If no blocking issues remain]: ✅ No blocking issues remain — artifact is clear for status advancement.
   ```

**End of Review Mode.**

## Revise Mode

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `dekspec:ae-author` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles them into the prompt; the subagent executes them in fresh context; the orchestrator validates the result via `dekspec check validate <path>` on return.

Incorporate engineer review notes (annotations, comments, corrections) into a architecture element, then re-run the audit checklist to catch any new drift introduced by the revision.

Arguments after the path are the engineer's notes — inline text or a path to a `.md`/`.txt` file.

### Steps

1. Read the architecture element
2. Read the engineer's notes (inline or from file)
3. Classify each note as:
   - **Content change** — affects What This Is, Key Concepts, or Relationship to Other Components
   - **Scope change** — affects What We Are Not Building or What Success Looks Like
   - **Structural issue** — suggests splitting, merging with another DN, or fundamental rethink
4. Present the revision plan:
   ```
   REVISION PLAN for [path]:

   Content changes:
     - [note] → update [section]: [proposed change]

   Scope changes:
     - [note] → update [section]: [proposed change]

   Structural issues (require engineer decision):
     - [note] → [what needs to happen]

   Proceed with non-structural changes? (y/n)
   ```
5. Apply approved changes. Update **Modified** date.
6. **Re-run the full T / D / L1 / DS checklist from Audit Mode.** Report any new findings.
6a. **Cascade grep (added 2026-04-24 from DN-convergence lessons).** If any revision EXTRACTED content (moved a subsection from this AE to a WS / IC / WS-019 / AE-034 / divergence ledger), grep the corpus for live citations to the moved section and update them in the same commit:

   - **Search scope (include):** `dekspec/working-specs/*.md`, `dekspec/interface-contracts/*.md`, `dekspec/impl-briefs/**/*.md`, `dekspec/architecture-elements/*.md`, `dekspec/divergences/DIV-NNN-*.md`, `dekspec/convergence-loop-v2.md`, `dekspec/convergence-loop.md`, `dekspec/domain-glossary.md`, `dekspec/working-spec-index.md`, `dekspec/interface-contract-index.md`, `dekspec/architecture-elements-index.md`, `.beads/issues.jsonl`.
   - **Search scope (EXCLUDE):** `dekspec/audits/**`, `dekspec/archaeology/**`, `dekspec/research/**`, `dekspec/source-of-truth/**`, `dekspec/todos/**`. These are historical records of past work — cascading changes into them corrupts the audit trail. Audit and archaeology docs are NEVER cascade targets.
   - **Grep patterns:** `AE-NNN §<extracted-subsection-name>`, `AE-NNN's §<extracted-subsection-name>`, AE-NNN prefix plus the exact old subsection heading. For each hit outside the excluded scope, update the pointer to the new home (`WS-NNN §<new-subsection>` / `IC-NNN §<new-subsection>` / appropriate ledger entry). *(Legacy DN-NNN cascades have been folded into the AE-NNN namespace per the DN→AE migration of 2026-04-27; if a stale DN-NNN ref slips through, look it up in `dekspec/dn-to-ae-reference-map-2026-04-27.csv` and rewrite to the corresponding AE-NNN.)*
   - **Report:** list each updated reference in the revision output. If no live citations exist (all hits are in excluded scope), record "no live cross-references required cascade."

7. If the revision introduces ambiguity, contradictions, or concerns that cannot be fully resolved during this revision, log them as new entries in the `## Open Issues` section with **Source:** `review` and appropriate severity. Inform the engineer: "New open issues were logged. Run `--review` to walk through them."
8. If status was ACCEPTED or LOCKED, reset to PROPOSED (revision invalidates prior acceptance).

**End of Revise Mode.**

## Accept Mode (PROPOSED → ACCEPTED)

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `dekspec:ae-author` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles them into the prompt; the subagent executes them in fresh context; the orchestrator validates the result via `dekspec check validate <path>` on return.

Promotes a PROPOSED Architecture Element to ACCEPTED after every quality check passes. Passing the `--accept` flag is itself the deliberate engineer action of approval — no additional confirmation prompt is raised. The skill refuses to accept if any T / D / L1-ADR / L1-ADR-STALE / L1-VISION / L1-WS-EXISTS / L1-ADR-SCOPE check fails; no partial acceptance exists.

### Step 1: Validate

1. Read the architecture element at the provided path
2. Verify current status is PROPOSED. If not, STOP:
   - TODO, DRAFT → "This architecture element is still [status]. It must be revised to PROPOSED before it can be accepted."
   - ACCEPTED → "This architecture element is already ACCEPTED."
   - LOCKED → "This architecture element is LOCKED. Unlock first with `--unlock` if changes are needed."

### Step 2: Final Audit

Run the complete Audit Mode check list. Per §9 resolutions:
- **L1-GLOSSARY is ADVISORY at Accept** (§9 row 1). L1-GLOSSARY findings are reported but do not block.
- **DS-series is ADVISORY at Accept** (§9 row 2). DS findings are reported but do not block.

All other checks (T1–T9, D1–D16, L1-ADR, L1-ADR-STALE, L1-AE, L1-VISION, L1-WS-EXISTS, L1-ADR-SCOPE) must pass.

**Stale-ref sweep (added 2026-04-24 from DN-convergence lessons).** Additionally, for each Open Issue that references a WS, IC, or ADR by ID:

- Read the referenced artifact's current Status.
- If the Open Issue was opened when the referenced artifact was `TODO` / `DRAFT` but the artifact has since advanced to `PROPOSED` / `ACCEPTED` / `LOCKED`, flag as "stale-ref — close or restate."
- Flag at blocking severity at Accept — a AE cannot advance to ACCEPTED with stale cross-references in its Open Issues. The engineer's paths are: (a) close the Open Issue with a resolution pointer to the now-advanced artifact, (b) restate the Open Issue against the current state if a new concern remains, or (c) delete if no longer relevant.

Many pre-convergence DNs carried Open Issues of the form "WS-NNN is TODO" that became stale the moment WS-NNN advanced; this sweep catches those automatically.

### Step 3: Report

```
FINAL AUDIT: [path]

[full T/D/L1/DS report as in Audit Mode]

[If blocking checks all pass]: All blocking checks pass. Promoting PROPOSED → ACCEPTED.
  Advisory findings (L1-GLOSSARY / DS-series): [list or "None."]
[If any blocking failed]: Cannot accept — resolve blocking failures first. No changes made.
```

If any blocking check fails, STOP — do not change status, do not update the index, do not make any other changes.

### Step 4: Accept

Only executed if Step 3 reported zero blocking failures.

1. Flip Status PROPOSED → ACCEPTED and bump Modified — run `python ../_lib/scripts/artifact_ops.py transition <AE-path> --from PROPOSED --to ACCEPTED` (no `--note`: no Amendment Log entry on accept). Surface stderr on non-zero exit and STOP.
2. Update `dekspec/architecture-elements-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/architecture-elements-index.md --id AE-NNN --status ACCEPTED` (surface stderr on non-zero exit).

No Amendment Log entry is written — the log is reserved for changes made after LOCKED status, or when unlocking back to PROPOSED.

**End of Accept Mode.**

## Lock Mode (ACCEPTED → LOCKED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Lock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: architecture element
- **pre_lock_audit_ref**: §Audit Mode of this skill, extended with the AE-specific blocking rules below
- **status_before**: ACCEPTED
- **status_after**: LOCKED
- **artifact_index_path**: `dekspec/architecture-elements-index.md`

AE-specific blocking rules added to the substrate's audit run (per §9 audit resolutions):
- **L1-GLOSSARY is BLOCKING at Lock** (§9 row 1).
- **DS-series is BLOCKING at Lock** (§9 row 2) — an AE may not LOCK while any DS1 or DS2 finding is open (a downstream WS in stale contradiction with the AE must be reconciled first).

## Unlock Mode (LOCKED → PROPOSED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Unlock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: architecture element
- **status_before**: LOCKED
- **status_after**: PROPOSED
- **artifact_index_path**: `dekspec/architecture-elements-index.md`

Downstream impact scan (run during Step 2 alongside the reason gate): grep specs for references to this architecture element; surface the impact list to the engineer before recording the reason. Cascade reminder to surface in Step 4: downstream artifacts may need review, affected IBs may need regeneration, and the AE must be re-locked when the substantive change settles.

## Input

Engineer's description: $ARGUMENTS

## Workflow

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this Creation Mode body to a fresh-context `dekspec:ae-author` subagent per **Fan-Out Mode** above. The steps below — including the §AE Classifier/Router gate and §AE Subtype Selection prompt — are the **subagent's contract**: the orchestrator bundles them into the prompt; the subagent executes them in fresh context; the orchestrator validates the result via `dekspec check validate <path>` on return.

1. Read the Writer role from `dekspec/project-context.md`.
2. Read `dekspec/domain-glossary.md` for canonical domain terminology.
3. Read `dekspec/system-vision.md` for scope reference.
4. Read the template from `dekspec/templates/architecture-element-template.md`.
5. Determine the **Subtype** (mandatory per T10) from the C4-aligned enum: `System | Subsystem | Container | Component | Pipeline | Data Model | Cross-Cutting Concern | Platform Concern | Interface Surface | Workflow / Process`. See §AE Subtype Selection above for the full picker rules.
6. Read `dekspec/architecture-elements-index.md` — determine the next available AE number (highest existing AE-NNN + 1). If an architecture element already exists for this topic, read it and determine if this is an update or a duplicate.
6a. **ADR-scope pre-count (added 2026-04-24 from DN-convergence lessons).** Before drafting, count the ADRs the engineer's description references or implies. If the count is already <2 or >8, raise the scope issue with the engineer now — surfacing scope issues at engineer-review-of-description time lets the author rethink the DN's boundary before sinking time into a full draft that will fail L1-ADR-SCOPE at Step 4a. Suggested resolutions at this pre-check: (a) merge-candidate into an existing DN if too narrow (<2 ADRs and overlapping parent exists); (b) split into two DNs if too broad (>8 ADRs span multiple concerns); (c) use the `**Indirect governing ADRs:**` separator if several ADRs are peer-concerns rather than direct scope (Q1 exemption — reduces the direct-body count toward the 2–8 range).
7. Draft the architecture element using all template sections (see `architecture-element-template.md` for the canonical shape):
   - **Status:** DRAFT
   - **Subtype:** the determined subtype (mandatory per T10)
   - **Classification:** Core / Supporting / Generic
   - **Created:** today's date
   - **Modified:** today's date
   - **Linked Artifacts** — Related ADRs / WSs / ICs / IBs / Owners (use "none" explicitly when empty; mandatory per Numbered Governance Rule 6)
   - **Purpose and Scope** — 1-2 paragraphs: what this architectural slice is, its role in the larger system, why it exists; cite the upstream Mission or Intent it serves where applicable
   - **Responsibilities** — bullet list of architecturally significant load-bearing responsibilities (not exhaustive)
   - **Boundaries and Non-Goals** — explicit "Inside the boundary" + "Outside the boundary (non-goals)" subsections; ≥1 non-goal with a *why* clause required (T11)
   - **Key Concepts** — essential ideas; vision-level only (see Rules block below)
   - **Relationships and Dependencies** — pre-structured four-sub-bullet (Consumes / Produces / Depends on / Consumed by); optional `**Indirect governing ADRs:**` sub-bullet for peripheral ADRs that don't count against the 2–8 direct-body rule
   - **Views** — C4 view(s) that materially clarify the AE; for structural subtypes, at least one view normally expected (T12) — if absent, justify the absence in this section
   - **Runtime Behavior / Data and State / Deployment / Operational Shape** — optional sections; populate when subtype warrants (Pipeline / Workflow / Container / Data Model / Platform Concern)
   - **Constraints and Quality Notes** — non-measurable architectural constraints; measurable quality targets (latency, throughput, SLOs) live in linked WSs, NOT here (D17)
   - **Open Questions / Planned Follow-ons** — design-level questions only; code-gap items route to the divergence ledger or `br`
   - **Amendment Log** — empty on initial creation
8. **Step 4a — Verification (D1–D12 drift + L1 consistency).** Run D1–D12 and L1 consistency checks (L1-ADR, L1-ADR-STALE, L1-AE, L1-GLOSSARY, L1-VISION, L1-WS-EXISTS, L1-ADR-SCOPE) against the draft. If any drift is detected, present the engineer with each finding and three options:

   1. **Rewrite at the vision level** — the content is vision-adjacent, just over-specified. Rewrite to state the principle.
   2. **Move to target artifact** — the content is mechanics. Route to the recommended destination (WS / IC / WS-019 / AE-034 / divergence ledger). The DN retains a cross-reference.
   3. **Keep and justify** — edge case where the mechanic IS the vision (e.g., "five relevance tiers" defining the architecture). Requires explicit engineer confirmation.

   Only after every D1–D12 finding is cleared, and every L1 violation is either fixed or explicitly acknowledged per §3.3 rules, may the AE advance to Step 9 (Save).

9. Present the draft for engineer review.
10. Set **Status** to PROPOSED, update **Modified** to today's date.
11. Save to `dekspec/architecture-elements/AE-NNN-{slug}.md`.
12. Update `dekspec/architecture-elements-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/architecture-elements-index.md --id AE-NNN --status PROPOSED` (surface stderr on non-zero exit). For a brand-new AE the script appends a minimal row; fill in the Title / Subtype / Classification cells the row needs.

## Provisional Mode

`--provisional <incubation-slug>` redirects authoring into the provisional staging area (`dekspec/provisional/<incubation-slug>/`) instead of the canonical `dekspec/architecture-elements/` directory. The canonical Status transition + audit walker pick the work up only after the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)) is run later. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)

Use this mode when:
- The exploration may span many commits before ratification.
- Companion artifacts (ADRs / AEs / ICs that this Architecture Element depends on) will be authored alongside in the same incubation folder.
- The canonical ID should NOT be claimed until the originating Intent reaches ACCEPTED.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding so the remaining args feed normal authoring.
2. If the incubation folder `dekspec/provisional/<slug>/` does not exist OR does not yet contain a `AE-provisional-*.md` file for this work, scaffold via:
   ```
   dekspec library new-provisional AE <slug> --title "<H1 title from remaining $ARGUMENTS>" [--incubation <slug>] [--no-branch]
   ```
   The CLI scaffolds the folder + skeleton + (by default) a git branch named per kind. Surface its stderr on non-zero exit and STOP.
3. Read the scaffolded file at `dekspec/provisional/<slug>/AE-provisional-<title-slug>.md` (the CLI prints the path).
4. **Populate the skeleton with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here (Motivation, Linked AEs, Components affected, Verification, etc.). The PROVISIONAL banner at the top stays.
5. **Reject `--lock`** in combination with `--provisional`. LOCKED state requires linkage-walker visibility that provisional artifacts deliberately lack. The hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion) is the canonical path to LOCKED.
6. **`--analyze` and `--review`** remain available in provisional mode — they operate on the provisional file's content without requiring canonical-graph visibility.
7. Closing step: surface to the engineer the path of the provisional file, the branch (if created), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

### Cross-references

- `INT-079` — provisional folder substrate (parser-ignore, doctor advisory).
- `INT-082` — copy-on-write spec staging (`replaces:` frontmatter, sibling-collision audit).
- `INT-083` — atomic promotion (CLI verb retired 2026-05-25; the hand-promote workflow is canonical — see `_lib/cli_verbs.md`).
- `INT-084` — `dekspec library new-provisional` scaffold + auto-branch.

**End of Provisional Mode.**

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

- **Log corrections.** When any mode (creation, audit, review, revise) corrects a domain misinterpretation — wrong term usage, confused concepts, contradicted architectural facts — invoke `/write-ggc --log` with the correction details before proceeding. This feeds the glossary promotion pipeline.

- **DNs are about vision and principles — never about mechanics, numbers, or names.** A Architecture Element describes *what the subsystem is, what success looks like, what it is not, its key concepts, and how it relates to other components.* It must not contain:
  - Code — no fenced code blocks, no inline code-shaped identifiers with parens, no import paths, no library-function names.
  - Mathematical formulas, derivations, inline math, or algorithm-invariant narratives — refer to the formula by its home.
  - Function / method / class / callable names — concept shortnames only.
  - Step-by-step procedures of 3 or more items — whether numbered, bulleted, "Phase N:" headers, or prose sequences.
  - Per-type dispatch enumerations with mechanics — decision-level categorization only.
  - Configuration defaults with justifying prose — the constants-management WS (WS-019) owns defaults and rationale; the NFR DN (AE-034) owns numeric targets for all other DNs to cite.
  - Schema / dtype / kwarg / interface tables — move to an Interface Contract.
  - Code-gap punch-lists in `Open Issues` — those belong in the divergence ledger or `br`. AE-004 and AE-037 are grandfathered for pre-2026-04-24 entries (§9 row 5).
  - Process narrative in the amendment log or body — audit trails live in git and in the audits directory.
  - Stale superseded-approach prose in the live body — it goes to a one-line Amendment Log summary.
  - Motivational restating of the System Vision — subsystem-specific claims from paragraph one.
  - "Expected Operating Range" / capacity tables — NFR content lives in AE-034 (all other categories are exempt neither from D6 nor from D12).

- **Where does the drifted content go? — Extraction Default-Home Table** (replaces the prose version; added 2026-04-24 from DN-convergence lessons). When Step 4a Verification surfaces drift, use this table to pick the destination. The drafter consults it during authoring; the skill uses it when recommending a target for an Audit Mode D-series finding.

    | Content shape | Default home |
    |---|---|
    | Algorithm / step-by-step procedure | **WS** §Algorithm |
    | Schema / dtype / field / kwarg table | **IC** |
    | HTTP / gRPC / cross-process wire-format definition | **IC** |
    | **In-process Python module** with behavior rules (acquire / release / ref-count etc.) | **WS** — **not IC.** ICs are for cross-process / cross-component boundaries; in-process modules are WS-shaped. Lesson from DN-convergence R2 DECISION 1 (IC-013 → WS-042 re-home). |
    | Tunable configuration default with rationale | **WS-019** §Memory Budgets / §Algorithm Defaults |
    | Numeric capacity / latency / throughput / resource-utilization target | **AE-034** §\<category\> |
    | Code-vs-oracle structural divergence | **`dekspec/divergences/DIV-NNN-*.md`** |
    | Code-bug (built drifts from spec) | **`br`** issue with type `bug` |
    | Implementation file path in prose | never in AE — file a `br` issue (spec-coverage gap) or a `dekspec/divergences/DIV-NNN-*.md` entry (oracle-vs-built) |
    | Historical superseded approach | one-line AL summary; not live body |
    | Motivational scene-setting | delete — `system-vision.md` already does this |

- **Writing-time heuristics** (added 2026-04-24 from DN-convergence lessons). These are internalized rules the drafter applies during authoring; they prevent the drift categories that the D-series catches at audit time.

  - **Reader test.** If a reader needs to read code, a WS, or an IC to understand this paragraph, and the concept is algorithmic / schema-level / wire-format / library-coupled, the content belongs elsewhere. A AE must stand alone as a vision document to someone who has never read the codebase or any Working Spec.

  - **Hedge-word test for numerics.** Before writing a numeric value with a unit, ask: is this value TUNABLE (can an operator change it without changing the architecture)? If yes → cite WS-019 or AE-034 §\<category\>, do not inline. If the value DEFINES the architecture (e.g. "five relevance tiers", "two-phase pipeline", "three services"), inline is correct. Hedging words (`currently`, `~`, `roughly`, `seed default`, `per ADR-NNN`) are the tell: architecture-defining values are not hedged.

  - **Single-authoritative prohibition.** A DN never claims to be "the single authoritative reference" for a contract. WSs are authoritative for *behavior*; ICs are authoritative for *boundaries*; DNs are authoritative for *vision and principles*. If you're tempted to write "this AE is the full / complete / authoritative specification of X", X belongs in a WS or IC, not in this AE.

  - **Mirror prohibition.** Never duplicate a value, table, or formula from another artifact "for reader convenience". A citation is always correct; a mirror is always one amendment away from stale. If the detail is important enough to want the reader to see it, the reader can click through.

  - **Audit-ruler prohibition.** If you need to write a section that serves as an audit ruler — "every IB / WS / code audit must conform to this process" — that content is a behavioral contract. It belongs in a Working Spec. DNs do not author audit rulers; they describe why the contract matters.

  - **One-date Modified rule.** The Modified field is a single ISO-8601 date with no parenthetical narrative, no multi-date stack. Narrative about what changed belongs in Amendment Log entries (one line each per Δ-SQ-17). If you find yourself wanting to explain an edit in the Modified field, write it in AL instead.

  - **Deprecation-pointer format.** When retiring an AE via merge, set Status to DEPRECATED and add a **Deprecation Note** section immediately after Status with this form: "Content merged into AE-NNN §\<subsection\> on YYYY-MM-DD per \<rationale/decision\>. Behavioral spec (WS-NNN) remains unchanged and retains authoritative status. Future design-level edits belong in AE-NNN §\<subsection\>; future behavioral edits belong in WS-NNN."

- **Common authoring anti-patterns to avoid** (named instincts — recognize them in yourself during drafting):

  - **"Completeness instinct."** The drafter tries to make the AE "comprehensive" and detail creeps vision → algorithm → code. *Counter:* a complete DN is concise; a drifting DN is detailed. Target 1–2 pages; anything beyond 350 body lines is a scope error, not a thoroughness virtue.
  - **"Authoritative-reference instinct."** The drafter claims "this is the single source of truth for X" and slides into WS/IC territory. *Counter:* DNs are authoritative for vision; WSs for behavior; ICs for boundaries. If X is a contract, it's not this AE's scope.
  - **"Audit-ruler instinct."** The drafter writes content that other artifacts are supposed to conform to ("every IB / code audit must measure against this process"). *Counter:* audit rulers belong in Working Specs. DNs describe why the ruler matters, not the ruler itself.
  - **"Mirror-for-convenience instinct."** The drafter writes "mirrored here for reader convenience" to duplicate a value whose authoritative home is elsewhere. *Counter:* cite, don't mirror. The mirror always drifts.
  - **"Dev-mode ambition instinct."** The drafter tries to spec an entire feature (DN + WS + IC) in a single document, producing a mega-doc. *Counter:* one DN per subsystem / concern, one WS per behavioral unit, one IC per boundary. If you can't describe the AE without switching into mechanics, you're writing a WS.
  - **"Process-narrative instinct."** The drafter records how a revision was done ("autonomy L3 @ 0.85", "engineer scope-C pre-approval", "Closes iter-6 fidelity-audit finding I-6"). *Counter:* process metadata belongs in git commit messages and audit-trail docs, not the AE body or Amendment Log. AL entries are one-line descriptions of *what* changed; *how* it was done stays outside the artifact.

- **L1-ADR deviation acknowledgment is strict (Q5 resolution, §3.3).** When an AE describes a state that differs from a referenced ADR's current `§Decision`, the acknowledgment must live in the AE body — specifically `Key Concepts` or `What We Are Not Building` — NOT in the Amendment Log. The Amendment Log is an audit trail; a reader who reads only the current body sections must get the right current state.

- **L1-ADR-SCOPE counts direct-body ADRs only (Q1 resolution, §3.3).** The 2–8 ADR scope applies to ADRs cited directly in the AE body text. ADRs listed under an explicit `**Indirect governing ADRs:**` sub-bullet of `§Relationship to Other Components` are exempt from the count. Indirect ADRs must carry a one-line rationale explaining why they are indirect (governing a peer concern rather than this AE's direct scope).

- **SUPERSEDED / DEPRECATED ADR citations flag L1-ADR-STALE (Q7 resolution).** Cite the replacement, not the superseded ancestor. `/write-ae --audit` grep-checks for this across all referenced ADRs.

- Write at the conceptual/architectural level, not code level — no function names, variable names, config keys, or line numbers

- Reference ADRs by number where relevant

- The document should be understandable by someone who has never read the codebase

- 1–2 pages maximum — if you need more, split the spec

- **Scope discipline:** A Architecture Element describes a coherent subsystem or cross-cutting concern. If it covers less than two ADRs worth of territory, it is too narrow — the ADRs are sufficient. If it covers more than eight, it is too broad — split it. The count is over direct-body ADRs only.

- If the architecture element surfaces an undocumented architectural decision, invoke `/write-adr` to create the ADR before completing the architecture element — do not flag it as a stopping point

- The template (`dekspec/templates/architecture-element-template.md`) must be completely filled out. Every section, every placeholder. If information is missing, ask the engineer before proceeding — do not guess or leave blanks.

## Output

- `dekspec/architecture-elements/AE-NNN-{slug}.md` with status PROPOSED (after Step 4a Verification clears all drift and L1 findings)
- Updated `dekspec/architecture-elements-index.md`
- Any ADRs produced during the process

## Amendment Log

| Date | Type | Change |
|------|------|--------|
| 2026-04-24 | Editorial | T7 wording restored to allow "or an explicit variant that covers all four directions" per R1 DECISION 3 of the DN-convergence run — aligns skill with proposal §3.1 (Q1-adjacent). |
| 2026-04-24 | Editorial | L1-ADR-SCOPE interpretation clarified — direct-body count excludes ADRs listed in the Indirect governing ADRs sub-bullet regardless of where else they appear. Dual-citation remains a MINOR structural fail. Aligns skill with Phase 7 engineer interpretation used in AE-016 and AE-022 Amendment Logs; resolves ambiguity surfaced in dekspec/audits/dn-post-convergence-audit-verification-2026-04-24.md R3. | Claude (engineer-directed) |
| 2026-05-19 | Substantive | Fan-out pattern added per bead `ds-di2`. Substantive-work modes (Creation / `--accept` / `--revise`) now delegate to a fresh-context `dekspec:ae-author` subagent via the Agent tool; orchestrator bundles context (template, system vision, glossary, related AE/ADR/WS paths, engineer guidance, constraints), invokes the subagent with a self-contained prompt, then validates the returned artifact with `dekspec check validate <path>`. Modes preserved inline: `--help`, `--teaching`, `--review`, `--audit`, `--lock`, `--unlock` (status walks + engineer-interactive queries). Front-matter `allowed-tools` gained `Bash Agent`. Three substantive-work mode sections carry a "Fan-out delegated" banner pointing back to §Fan-Out Mode. |
| 2026-04-24 | Substantive | Applied DN-convergence lessons. (a) Refined existing check triggers: T3 verb-first title regex; T8 Modified-field discipline; T9 meta-reference detection; D3 library-call blacklist + CamelCase / ALL_CAPS regex + HuggingFace-path pattern; D6 hedge-language signal; D10 scoped-to-positive-sections regex; L1-GLOSSARY deprecated-alias sweep; L1-WS-EXISTS TODO-stub detection; L1-ADR-SCOPE duplicate-citation count + indirect-ADR structural compliance check. (b) Added D13 mirror-for-reader-convenience anti-pattern, D14 audit-ruler / canonical-process framing detection, D15 single-authoritative-reference overreach, D16 Open Issues classification (spec-coverage-gap vs code-gap). (c) Rules block gains an Extraction Default-Home Table (replaces prose "Where does drifted content go?"), writing-time heuristics (reader test, hedge-word test, single-authoritative prohibition, mirror prohibition, audit-ruler prohibition, one-date Modified rule, deprecation-pointer format), and a "Common authoring anti-patterns" subsection (completeness instinct, authoritative-reference instinct, audit-ruler instinct, mirror-for-convenience instinct, dev-mode ambition, process-narrative instinct). (d) Revise Mode gains step 6a cascade grep with explicit include/exclude scope (audits/ and archaeology/ are never cascade targets). (e) Accept Mode gains a stale-ref sweep for Open Issues that reference WS / IC / ADR that have since advanced in status. (f) Workflow Step 6a adds an ADR-scope pre-count so scope issues surface at engineer-review-of-description time rather than at Step 4a Verification. All new D13–D16 checks land at natural blocking severity (no advisory-first); per-finding exceptions use Step 4a "Keep and justify." |

## Approve Mode

`--approve` records a peer-review approval signature on an Architecture Element under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the AE's `## Amendment Log` table — it does **not** flip Status.

Run the shared deterministic helper:

```
python ../_lib/scripts/artifact_ops.py approve <AE-path> --target-status <STATUS>
```

`<STATUS>` is the transition the signature authorizes (e.g. `ACCEPTED` or `LOCKED`). The script resolves the reviewer email from `git config user.email` (override with `--engineer <email>`) and appends a row of the form `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`, then bumps `Modified`. The `T-APPROVAL-GATE` audit rule counts these rows under the `team` profile; once enough signatures are present the AE may walk the gated transition. Under the default `v1` profile the rule is silent. Inline mode — no fan-out.

## Common Pitfalls

- Don't author an AE for decision/requirement/boundary/plan-shaped input — run the §AE Classifier/Router gate first and redirect to `/write-adr`, `/write-ws`, `/write-ic`, or `/write-ibs` when the input is dominated by that shape.
- Don't draft before a Subtype is fixed — prompt §AE Subtype Selection up front; a missing or non-enum `## Subtype` is a hard T10 fail that schema-validation rejects at parse time, not something to backfill later.
- Don't inline numeric quality targets (ms, SLOs, throughput, capacity, retention) — those are a hard D17 fail; extract them to a WS and cite it from the AE shell.
- Don't write decision rationale ("we chose X because…", "instead of Y", "the tradeoff is…") — that is a hard D18 fail; cite the governing ADR by number and leave the rationale in the ADR.
- Don't mirror a value/table/formula "for reader convenience" — D13 fires; cite the authoritative home so the AE can't drift one amendment out of date.
- Don't leave a structural-subtype AE (System/Subsystem/Container/Pipeline/Platform Concern) without a `## Views` section or an explicit one-paragraph absence justification — T12 fires.
- Don't extract a subsection during `--revise` without running the Step 6a cascade grep — stale `AE-NNN §<section>` pointers in WS/IC/IB break DS1 and must be rewritten in the same commit.

## Verification Checklist

- [ ] Classifier/Router gate ran and the input was confirmed AE-shaped (not redirected to ADR/WS/IC/IB).
- [ ] A single `## Subtype` is populated from the C4-aligned enum (T10 green).
- [ ] `## Boundaries and Non-Goals` carries ≥1 inside-boundary item and ≥1 non-goal with a *why* clause (T11 green).
- [ ] `## Views` is present with a real view, or its absence is justified in one paragraph for structural subtypes (T12 green).
- [ ] Step 4a Verification ran: D1–D18 drift clear (no inline numerics per D17, no rationale per D18) and every L1 finding fixed or acknowledged in-body per §3.3.
- [ ] L1-ADR-SCOPE is within 2–8 direct-body ADRs.
- [ ] Status is PROPOSED, `Modified` is today (single ISO-8601 date), and the file saved to `dekspec/architecture-elements/AE-NNN-<slug>.md`.
- [ ] `dekspec/architecture-elements-index.md` row added/updated and `dekspec audit relink` run (Closing Step).

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise an Architecture Element — Creation, `--accept`, `--revise`, `--lock`, `--unlock`). After the artifact file is saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
