---
name: write-evals
description: Write, audit, review, revise, resync, accept, or dry-run probabilistic behavioral evals for beads / IBs that produce model output. Must run BEFORE the coding session begins. Mode catalog mirrors /write-ibs.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help | --teaching | --audit | --review | --resync | --revise | --accept | --dry-run] [BEAD-NNN or path to IB] [engineer notes or path to notes file]
related_skills: [write-ibs, write-tests, write-beads, write-intent, exec-coding-session]
---

> **Vendored asset paths:** Template + doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>` (wheel-bundled since v0.91.0; consumer-fs override wins when present). See [`_lib/vendored_assets.md`](../_lib/vendored_assets.md) for the full resolution rule.

Write or maintain probabilistic behavioral evals for beads that produce model output. Evals codify the boundary between *deterministic* test assertions (which the coding agent writes during the session) and *probabilistic* model-output checks (which the engineer authors before the session begins, because the coding agent cannot be trusted to grade its own output).

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill defines probabilistic behavioral criteria that validate model output. Prior conversation context can degrade eval quality by biasing threshold selection and scenario design — the model may anchor on whatever range it remembers from the prior turn instead of deriving the range from the bead's acceptance criteria.
>
> First message → proceed. Prior history → ask "context may affect eval quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-evals ds-7f3a

ds-7f3a injects retrieved memory into the prompt and its IB Done-When says
"injection effective on ≥80% of known-fact trials". Author the eval set
(behavioral + adversarial empty-corpus) before the coding session opens.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Creation Mode**.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **Review mode** — `--review` flag. Skip to **Review Mode**.
- **Resync mode** — `--resync` flag. Skip to **Resync Mode**.
- **Dry-run mode** — `--dry-run` flag. Skip to **Dry-Run Mode**.
- **Revise mode** — `--revise` flag. Proceed to **Fan-Out Mode (default authoring path)**.
- **Accept mode** — `--accept` flag. Proceed to **Fan-Out Mode (default authoring path)**.
- **Creation mode** — no flag. Proceed to **Fan-Out Mode (default authoring path)**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--accept`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--review`, `--audit`, `--resync`, `--dry-run`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `general-purpose` (no dedicated `dekspec:evals-author` type today).
- **substantive_modes**: [Creation (default), `--accept`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--review`, `--audit`, `--resync`, `--dry-run`]
- **bundle_list** (Step 1 context):
  1. Template — the eval skeleton from §Eval file template inline in this skill (pass the literal block verbatim; prefer `dekspec/templates/eval-template.md` if a future bead promotes it).
  2. Methodology references — `docs/dekspec-methodology.md` §Test Strategy; `dekspec/templates/checklists/eval-quality-checklist.md` (four-layer canonical guidance — Retrieval / Injection / Awareness / E2E).
  3. CLAUDE.md sections — §Test Strategy / §Eval Policy / §Model Configuration entries from the consuming repo (if present).
  4. Bead context chain (IB / WS / Intent) — run `python ../_lib/scripts/resolve_bead_context.py <bead-id>`; bundle the JSON output. It resolves, deterministically: `ib_path` (the parent IB — supplies Goal, Constraints & Decisions, Done When, §Probe Results) and `ws_path` (the parent Working Spec — owns the acceptance criteria the subagent uses to derive thresholds). If `ws_path` is `null` or the `notes` array flags a broken hop, surface it as a bundle gap. Also bundle the bead row itself from `.beads/issues.jsonl`.
  5. Existing eval files — for `--revise` / `--accept`, eval files referenced in the bead's `evals` field (paths under `tests/evals/{behavioral,regression,adversarial}/`); empty for Creation.
  6. Engineer guidance — `$ARGUMENTS` verbatim, including BEAD-NNN / IB path and inline notes (or `.md`/`.txt` notes file for `--revise`).
  7. Constraints — the rules block at the bottom of this skill (evals authored BEFORE the coding session; coding agent does not write evals; probabilistic-only — deterministic checks belong in `tests/`; one eval per checklist layer; LLM-as-judge uses a different model than the model under evaluation; pass criterion pins trial count + run count + range).
- **expected_output_path**: Creation — `tests/evals/{behavioral,regression,adversarial}/<bead-id>_<scenario-name>.md` (one file per eval); `--revise` / `--accept` — existing eval-file paths (edited in place).
- **validation**: `/write-evals --audit <BEAD-NNN>` (re-invoke this skill's own Audit Mode against the returned eval set; until a typed eval IR + `dekspec check validate eval` land, Audit Mode is the validation surface). Any finding of severity critical or important → surface verbatim. Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — Audit Mode is the equivalent gate here; on a critical/important finding, surface verbatim and stop, do not silently retry. Mode-specific post-checks: Creation — frontmatter populated (Bead, IB, Status=DRAFT) + bead's `evals` field updated; `--revise` — Type=Revise Amendment-Log row per touched eval + Open Issues surfaced; `--accept` — Status flipped DRAFT→ACCEPTED + Type=Accept row + Modified=today.

**End of Fan-Out Mode.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-evals"
one_line:   "Write, audit, review, revise, resync, accept, or dry-run behavioral evals for beads with model output"
modes:
  - { flag: "", args: "<target>", description: "Write evals for a bead or IB. Must run BEFORE the coding session begins. (Creation Mode)" }
  - { flag: "--audit", args: "<BEAD-NNN | \"all\">", description: "Re-check existing evals against their bead / IB for continued validity. Read-only — reports findings without changes. (Audit Mode)" }
  - { flag: "--review", args: "<BEAD-NNN>", description: "Walk through eval open issues interactively; resolve one at a time with the engineer. (Review Mode)" }
  - { flag: "--resync", args: "<BEAD-NNN>", description: "Re-derive evals after the source IB was resynced or acceptance criteria changed. Compares current evals to the updated source and proposes deltas. (Resync Mode)" }
  - { flag: "--revise", args: "<BEAD-NNN> <notes>", description: "Update existing evals after engineer feedback. Notes: inline text or path to a .md / .txt file. (Revise Mode)" }
  - { flag: "--accept", args: "<BEAD-NNN>", description: "Promote evals from DRAFT → ACCEPTED after a clean audit + engineer confirmation. (Accept Mode)" }
  - { flag: "--dry-run", args: "<BEAD-NNN>", description: "Preview eval count, types, and scenarios without drafting full eval files. Useful for bead-scope validation. (Dry-Run Mode)" }
  - { flag: "--teaching", args: "<BEAD-NNN>", description: "Interactive tutorial: walk a new author through authoring evals for the supplied bead section-by-section. Distinct from --review (audits existing) and from no-flag creation (assumes the author already knows evals). (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-evals BEAD-42"
  - "/write-evals dekspec/impl-briefs/IB-001-component-brief.md"
  - "/write-evals --audit BEAD-42"
  - "/write-evals --audit all"
  - "/write-evals --review BEAD-42"
  - "/write-evals --resync BEAD-42"
  - "/write-evals --revise BEAD-42 \"acceptance threshold changed 80%→85%; add empty-input scenario\""
  - "/write-evals --revise BEAD-42 review-notes.md"
  - "/write-evals --accept BEAD-42"
  - "/write-evals --dry-run BEAD-42"
  - "/write-evals --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: Eval set (probabilistic behavioral evals for a bead)
- **template_path**: `templates/eval-template.md`
- **methodology_section**: §Test Strategy of `docs/dekspec-methodology.md`
- **exemplar_paths**: existing eval files in this repo, falling back to `tests/fixtures/` if none exist yet
- **required_sections**: [<H2 names from the eval template>]

Skill-specific structural checks to surface as Open Issues: probabilistic threshold without an acceptance range, scenario without explicit input/output.

## Audit Mode

Re-check existing evals against their bead / IB for continued validity. Read-only.

### Steps

1. Resolve the target — bead ID(s) or `all`.
2. For each bead with evals:
   a. Read the bead from `.beads/issues.jsonl` and the IB referenced by the bead's `ib` field (or by convention from `dekspec/impl-briefs/`).
   b. Read the eval files referenced in the bead's `evals` field (paths under `tests/evals/`).
   c. Read `dekspec/templates/checklists/eval-quality-checklist.md` to ground audit reasoning in the canonical layer-by-layer measurement guidance — Retrieval Correctness, Injection Effectiveness, Awareness/Hierarchy Scoring, End-to-End Quality.
3. Run the per-eval audit checks (mirrors the candidate T-EVAL-* rule family — see *Candidate audit-rule names* below):

   **Per-eval named-field checks (T-EVAL-FIELDS):**
   - [ ] **Input scenario** — present, specific, reproducible (not "some user input")
   - [ ] **Expected output range** — a threshold or distribution, not a single value
   - [ ] **Pass criterion** — explicit (e.g., "passes at ≥ 80% of trials over N runs")
   - [ ] **What failure means** — the engineer can read the failure mode and route the root cause
   - [ ] **Model pin** — concrete model identifier or `n/a` with justification
   - [ ] **Sampling strategy** — temperature, top-p, seed, trial count (or `n/a` with justification)

   **Per-eval coverage checks (T-EVAL-COVERAGE):**
   - [ ] **Layer alignment** — eval targets one of the four checklist layers (retrieval / injection / awareness / E2E) or explicitly justifies "cross-layer"
   - [ ] **Acceptance alignment** — pass criterion matches the bead's acceptance criteria; mismatched thresholds flagged
   - [ ] **Scenario alignment** — every model-output behavior declared in the IB has at least one eval covering it
   - [ ] **Stale-scenario sweep** — every eval still tests a behavior present in the current IB (no orphans after an IB resync)

   **Cross-eval checks (T-EVAL-SET):**
   - [ ] **Adversarial coverage** — at least one adversarial / empty / malformed-input eval if the IB has any failure-mode declarations
   - [ ] **Regression coverage** — at least one eval pinned to a known-good baseline (regression) if the IB touches a load-bearing model path
   - [ ] **Type spread** — behavioral / regression / adversarial categories each have ≥1 eval when applicable

4. Report:

```
EVAL AUDIT:
  ✅ BEAD-42: 3 evals, all valid (1 behavioral, 1 regression, 1 adversarial)
  ❌ BEAD-43: coverage gap — IB lists embedding scoring behavior but no eval covers it
                (per eval-quality-checklist §Awareness/Hierarchy Scoring)
  ⚠️  BEAD-44: threshold mismatch — IB acceptance says ≥85% but eval pass criterion is ≥80%
                (T-EVAL-FIELDS pass-criterion misalignment)
  ⚠️  BEAD-45: stale scenario — eval `embedding_v2.md` tests pooling strategy A but the
                IB was resynced to pooling strategy B (run --resync)
```

Read-only — no changes made. Audit findings of severity **important** or **critical** block any subsequent `--accept` for that bead.

**End of Audit Mode.**

## Review Mode

Walk through open issues in the eval set interactively — present each issue with context and a recommendation, resolve with the engineer one at a time. Open issues are eval-level (not bead-level) — questions about a specific eval's threshold, scenario design, or measurement layer that the engineer flagged during Creation or Revise mode.

Arguments: the bead ID.

### Steps

1. Resolve the bead and load its eval files.
2. Scan each eval file's `## Open Issues` section. Collect all unchecked items (`- [ ]`). If no items exist: "No open issues for BEAD-NNN evals. Nothing to review." **End of Review Mode.**
3. Read the source IB (Goal, Constraints & Decisions, Done When) and `dekspec/templates/checklists/eval-quality-checklist.md` for grounding.
4. Read any governing ADRs referenced by the IB (especially any ADR about scoring methodology, eval policy, or model pinning).
5. Present a summary:

```
REVIEW SESSION: BEAD-NNN
Open issues: [N] ([M] blocking, [K] non-blocking)
Evals: [list of files]
```

6. Walk issues one at a time. For each issue:
   - Show the eval file + the open-issue text + the **Source** + the **Severity**.
   - Surface relevant context: the IB section the issue maps to, the checklist layer, any prior eval that informs the recommendation.
   - Propose a resolution: keep / revise threshold / add scenario / split into a new eval / mark wontfix / escalate.
   - Wait for engineer decision.
   - If the resolution requires edits to the eval file, prepare the edit and ask "Apply? (y/n)" before writing.
7. After the walk, if any blocking issue remains unresolved: report the remaining set. If all blocking issues are resolved: remove resolved checkboxes from the eval files (mark with `- [x]` + a one-line resolution note).
8. Update the bead's eval-set timestamp.

**End of Review Mode.**

## Resync Mode

Re-derive evals after the source IB was resynced (Working Spec changed, acceptance criteria changed, new domain constraints added). The IB Resync produces a delta against the previous IB; this mode produces the corresponding eval delta.

### Steps

1. Read the bead and its eval files.
2. Read the current IB (post-resync state).
3. Read the IB's `## Amendment Log` to identify what changed in the most recent resync.
4. Read `dekspec/templates/checklists/eval-quality-checklist.md` and the bead's acceptance criteria.
5. For each existing eval, classify:
   - **Still valid** — scenario + threshold + measurement layer all still apply.
   - **Threshold update needed** — pass criterion no longer matches the IB's acceptance criteria.
   - **Stale scenario** — eval tests a behavior the IB no longer declares.
   - **Coverage gap created** — the resync added a behavior with no eval coverage.
6. Present the resync delta:

```
EVAL RESYNC for BEAD-NNN (IB resynced YYYY-MM-DD):

Threshold updates:
  - eval_name.md: pass criterion 80% → 85% (per updated IB Done When #3)

New scenarios needed:
  - [behavior] — added in IB §Domain Constraints; no eval covers it
                  (suggested layer: Injection Effectiveness)

Stale scenarios:
  - eval_name.md: tests [behavior] which was removed from IB

Still valid:
  - eval_name.md: scenario + threshold + layer all match current IB

Proceed with these changes? (y/n)
```

7. Wait for engineer approval. Applying:
   - Threshold updates: edit pass-criterion fields in place; record an Amendment-Log row on each updated eval.
   - New scenarios: scaffold the eval shell (input scenario + expected range + pass criterion + failure-meaning fields, all populated from the resync delta); engineer may flag for follow-on revision via `--revise`.
   - Stale scenarios: do NOT delete silently. Move to `tests/evals/archive/<bead-id>/` with a one-line provenance comment so the audit trail survives.
8. Re-run **Audit Mode** post-resync. If audit is clean, the resync is complete; if findings remain, present them and stop.

**End of Resync Mode.**

## Revise Mode

Update existing evals after engineer feedback (not a full resync — a targeted change).

Arguments after the bead ID are the engineer's notes — inline text or a path to a `.md` / `.txt` file.

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `general-purpose` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles them into the prompt; the subagent executes them in fresh context; the orchestrator validates the result via `/write-evals --audit <BEAD-NNN>` on return.

### Steps

1. Read the bead and its eval files.
2. Read the IB at the bead's `ib` reference.
3. Read the engineer's notes (inline or from file).
4. Compare current eval coverage against the IB's acceptance criteria and the engineer's notes — identify:
   - **Threshold changes** — acceptance criteria thresholds that no longer match eval pass criteria.
   - **New scenarios needed** — IB behaviors not covered by existing evals.
   - **Stale scenarios** — evals testing behaviors that were removed or changed in the IB.
   - **Engineer-requested changes** — specific updates from the notes.
5. Present the revision plan:

```
EVAL REVISION PLAN for BEAD-NNN:

Threshold updates:
  - eval_name.md: pass criterion 80% → 85% (IB acceptance changed)

New scenarios:
  - [behavior] — not covered by any existing eval

Stale scenarios:
  - eval_name.md: tests [behavior] which was removed from IB

Engineer requests:
  - [note] → [proposed change]

Proceed? (y/n)
```

6. Wait for engineer approval.
7. Apply approved changes to eval files. Record an Amendment-Log row on each touched eval (one-line: date / Type=Revise / what changed / author).
8. Update the bead's `evals` field if eval names or files changed.
9. If the revision introduces ambiguity or concerns that cannot be fully resolved, log them as new entries in the affected eval files' `## Open Issues` sections (Source: `revise`, Severity: blocking / non_blocking). Inform the engineer: "New open issues were logged. Run `--review` to walk through them."
10. Re-run **Audit Mode** on the revised eval set. If clean, revision is complete; if findings remain, surface them and stop.

### Examples

Inline notes:
```
/write-evals --revise BEAD-42 acceptance threshold changed from 80% to 85%, add scenario for empty input
```

Notes from file:
```
/write-evals --revise BEAD-42 review-notes.md
```

**End of Revise Mode — do not continue to the creation workflow.**

## Accept Mode

Promote eval files from DRAFT → ACCEPTED after a clean audit + engineer confirmation. Mirrors the `/write-ae --accept` ceremony.

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `general-purpose` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles them into the prompt; the subagent executes them in fresh context; the orchestrator validates the result via `/write-evals --audit <BEAD-NNN>` on return.

### Steps

1. Resolve the bead.
2. **Run Audit Mode** first. If any finding is severity **critical** or **important**, refuse:

   ```
   CANNOT ACCEPT — audit found [N] blocking findings:
     [list of findings]
   Resolve via /write-evals --revise or /write-evals --review, then retry.
   ```

3. If audit is clean, present:

   ```
   ACCEPT eval set for BEAD-NNN
     Evals: [list]
     Audit: ✓ clean
     Layer coverage: behavioral=[N], regression=[N], adversarial=[N]
   Confirm? (yes / no)
   ```

4. Wait for explicit "yes". Then for each eval:
   - Set **Status** field in the eval file to ACCEPTED (if the eval-as-IR schema is added in a future bead, this becomes a typed transition; today it's a frontmatter / header field).
   - Update **Modified** to today.
   - Append an Amendment-Log row: `| YYYY-MM-DD | Accept | Audit passed; engineer confirmed; promoted DRAFT → ACCEPTED. | <author> |`.
5. Report:

   ```
   ✅ BEAD-NNN evals: [N] files promoted DRAFT → ACCEPTED.
      Coding session may now begin (the coding agent runs evals; it does not write them).
   ```

**End of Accept Mode.**

## Dry-Run Mode

Preview eval count, types, scenarios, and layer coverage without drafting full eval files. Use for bead-scope validation before committing to the expensive Creation pass.

### Steps

1. Resolve the bead and read its IB.
2. Read `dekspec/templates/checklists/eval-quality-checklist.md`.
3. Walk the IB's model-output behaviors (Goal, Done When, Domain Constraints, and any §Probe Results scratch-pad cited).
4. For each behavior, classify the candidate eval — type (behavioral / regression / adversarial), checklist layer (retrieval / injection / awareness / E2E), expected scenario shape.
5. Lightweight spot-check:
   - [ ] **Single primary measurement layer per eval** — no eval spans two layers without explicit cross-layer justification.
   - [ ] **No coverage gap relative to Done When** — every Done-When item that names probabilistic output has a candidate eval.
   - [ ] **Threshold derivable from IB** — every candidate has a pass criterion derivable from the IB's acceptance prose (otherwise the engineer must supply it during full Creation).
6. Present:

```
DRY RUN — BEAD-NNN

Estimated eval count: [N] (behavioral=[A], regression=[B], adversarial=[C])

Candidate evals:
  - [scenario name] — type=behavioral, layer=injection, pass≥80%
  - [scenario name] — type=regression, layer=retrieval, pass≥Recall@5=0.7
  - [scenario name] — type=adversarial, layer=E2E, pass=no hallucination on empty input

Layer coverage: retrieval=[N], injection=[N], awareness=[N], E2E=[N]

Spot-check:
  [✅/⚠️/❌ per check]

Proceed with full Creation? (yes / no / rescope)
```

7. If "yes," proceed into **Creation Mode**. The dry-run candidates are guidance; Creation re-derives the eval set from scratch with full checklist rigor.
8. If "no" or "rescope," stop.

**End of Dry-Run Mode.**

## Creation Mode

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `general-purpose` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles them into the prompt; the subagent executes them in fresh context; the orchestrator validates the result via `/write-evals --audit <BEAD-NNN>` on return.

### Input

Bead ID or IB path: `$ARGUMENTS`.

If no input is provided, scan `.beads/issues.jsonl` for open beads whose `domain` includes model output (e.g., `injection`, `api` with generation, `retrieval`) and whose `evals` field is empty. List them and ask the engineer to select.

### Safety Check

Before proceeding:
- If the bead is `closed` — warn: "This bead is already closed. Writing evals after completion is unusual. Continue or abort?"
- If eval files already exist for this bead in `tests/evals/` — warn: "Evals already exist. Continuing will overwrite them. Continue or abort?"

Wait for engineer confirmation before proceeding.

### When Required

Decision rule: **does this bead produce model output?** If yes — evals required. If no — only deterministic tests (written by the coding agent during the session).

Concrete triggers:
- The IB's Done-When list contains a probabilistic threshold ("≥80% of trials", "Recall@5 ≥ 0.7", "no hallucination on empty input").
- The IB names a model interaction (LLM call, embedding produce, classifier output) on its load-bearing path.
- The bead's domain label includes `injection`, `retrieval`, `awareness`, `embedding`, or `api-generation`.

If none of these are true and the IB is purely deterministic plumbing (data shape, retry logic, persistence), this skill is not needed; the coding agent's tests cover the surface.

### Workflow

#### Phase 1: Gather sources

1. Read the Eval Agent role from `dekspec/project-context.md` (if present in the consuming repo).
2. Read the bead and the IB it references.
3. Read all ADRs the IB cites under §Governing ADRs (resolve supersession).
4. Read all ICs the IB cites under §Interface Contracts.
5. Read `dekspec/templates/checklists/eval-quality-checklist.md` — the canonical measurement guidance for the four checklist layers (Retrieval, Injection, Awareness, End-to-End).
6. Read the IB's §Probe Results scratch-pad if present — measured baselines feed eval threshold selection.

#### Phase 2: Field-by-field elicitation (per eval)

For each behavior identified in Phase 1, walk the engineer through the per-eval fields. Don't draft the whole file in one shot — elicit each field with grounding, get confirmation, move on.

**Field 1: Scenario name.**
Short slug describing what's being tested. Convention: `<behavior>_<input-condition>` (e.g., `injection_effective_known_facts`, `retrieval_recall_empty_corpus`).

**Field 2: Type.**
One of: `behavioral` (model output vs. known-good baseline), `regression` (pinned baseline, every PR), `adversarial` (empty / malformed / boundary input). Pick by asking the engineer "is this a baseline comparison, a regression guard, or a stress test?"

**Field 3: Measurement layer.**
One of the four checklist layers — Retrieval Correctness, Injection Effectiveness, Awareness/Hierarchy Scoring, End-to-End Quality. Cite the relevant subsection of `eval-quality-checklist.md` inline so the engineer can see the metric the eval should report.

**Field 4: Input scenario.**
Concrete, reproducible input. Reject vague answers ("some user prompt"); push for specific shape ("prompt text + memory stack of 3 items, two relevant"). If the input is large, externalize to a fixture file under `tests/evals/fixtures/<bead-id>/` and reference by path.

**Field 5: Expected output range.**
A threshold or distribution, never a single value. Examples: "Recall@5 ≥ 0.7 across 50 trials", "p95 latency < 200ms", "hallucination rate < 5%". Derive from the IB's acceptance criteria when possible; ask the engineer when not.

**Field 6: Pass criterion.**
Explicit phrasing: "passes if ≥ N% of trials over M runs meet the expected range" or equivalent. Pin trial count + run count — `Recall@5 ≥ 0.7` alone is under-specified without a trial budget.

**Field 7: Model pin.**
Concrete model identifier (e.g., `claude-sonnet-4-6-20251001`) or `n/a` with justification (e.g., "applies to any model satisfying the IC"). The pin must be reproducible.

**Field 8: Sampling strategy.**
Temperature, top-p, seed, trial count. Without these, the eval is not reproducible. Default for behavioral evals: `temperature=0.7, top_p=0.95, seed=42, trials=50`. The engineer can override per eval.

**Field 9: What failure means.**
One or two sentences mapping a failed eval to a likely root cause. Example: "If the retrieval Recall@5 falls below 0.7, the embedding pooling strategy has drifted — re-run the embedding regression suite (`tests/evals/regression/embedding_pooling.md`) to localize." Failure routing is what makes the eval actionable.

**Field 10: Open issues.**
Carry forward any open questions about this eval (Source: `initial draft`, Severity: blocking / non_blocking). These feed `--review` later.

#### Phase 3: Iterate per eval

After drafting all evals, run the **Audit Mode** checks inline (T-EVAL-FIELDS, T-EVAL-COVERAGE, T-EVAL-SET). If any finding is severity **critical** or **important**, fix in place and re-check. Iterate up to 2 rounds — content issues should be mechanical. If round 2 still fails, the underlying problem is structural (likely missing IB content or ambiguous acceptance criteria); escalate to the engineer rather than drafting around it.

#### Phase 4: Save + register

Save eval files to the appropriate `tests/evals/{behavioral,regression,adversarial}/` subdirectory. File naming: `<bead-id>_<scenario-name>.md`.

Update the bead's `evals` field in `.beads/issues.jsonl` to reference the new eval files by path.

Status of the eval set is `DRAFT` after Creation. Promote to `ACCEPTED` via `--accept` after a clean audit + engineer confirmation; the coding session does not begin until evals reach ACCEPTED.

### Rules

- Evals must be written BEFORE the coding session begins. The coding agent runs evals; it does not write them. An eval the coding agent wrote is suspicious by construction (the grader and the candidate are the same model).
- If the coding session has already started without evals for a model-output bead — STOP the session; backfill the evals before resuming.
- Evals verify probabilistic behavior (threshold across N trials), not deterministic behavior (single pass/fail). Deterministic tests belong in `tests/` (not `tests/evals/`).
- The four checklist layers are not exhaustive — if a bead's behavior doesn't fit, document a cross-layer eval and reference both checklist subsections that ground the measurement.
- LLM-as-judge evals must use a different model than the model under evaluation (per `eval-quality-checklist.md` §End-to-End Quality).

### Candidate audit-rule names (forward-looking)

This skill references three candidate audit-rule names that do not yet have implementations in `tooling/dekspec/fidelity_audit/linkage.py`. They are referenced here as planned; when a future bead adds an eval IR + schema, these rules become mechanical:

- **T-EVAL-FIELDS** — each eval's per-eval named fields (scenario / type / layer / input / range / pass / model pin / sampling / failure meaning) are populated.
- **T-EVAL-COVERAGE** — every model-output behavior in the source IB has at least one eval; thresholds align with IB acceptance criteria; no stale scenarios.
- **T-EVAL-SET** — adversarial + regression coverage when applicable; type spread across behavioral / regression / adversarial.

Until the eval IR lands, this skill's Audit Mode runs these checks against the markdown shape, not against an IR.

### Eval file template (skeleton)

```markdown
# Eval: <scenario-name>

**Bead:** BEAD-NNN
**IB:** dekspec/impl-briefs/IB-NNN-*.md
**Status:** DRAFT | ACCEPTED
**Created:** YYYY-MM-DD
**Modified:** YYYY-MM-DD

## Type
behavioral | regression | adversarial

## Measurement Layer
Retrieval Correctness | Injection Effectiveness | Awareness/Hierarchy Scoring | End-to-End Quality
(cross-layer: <subsections cited>)

## Input Scenario
<concrete, reproducible input — externalize to fixtures/ if large>

## Expected Output Range
<threshold or distribution; not a single value>

## Pass Criterion
<explicit: trial count × run count × range>

## Model Pin
<model identifier or n/a with justification>

## Sampling Strategy
temperature=<x>, top_p=<y>, seed=<z>, trials=<N>

## What Failure Means
<root-cause routing — what assumption is wrong if this fails>

## Open Issues

- [ ] <issue> — **Source:** initial draft — **Severity:** non_blocking

## Amendment Log

| Date | Type | Change | Author |
|------|------|--------|--------|
| YYYY-MM-DD | Create | Initial draft. | <author> |
```

### Eval Types

| Type | Location | When |
|------|----------|------|
| Behavioral | `tests/evals/behavioral/` | Model output vs. known-good baselines |
| Regression | `tests/evals/regression/` | Every PR touching model / scoring / retrieval / quant paths |
| Adversarial | `tests/evals/adversarial/` | Empty corpus, malformed input, boundary conditions |

### Output

Eval files in `tests/evals/{behavioral,regression,adversarial}/<bead-id>_<scenario-name>.md`. The bead's `evals` field updated to reference each new file. Eval set status `DRAFT`; promote via `--accept`.

**End of Creation Mode.**

## Cross-references

- `dekspec/templates/checklists/eval-quality-checklist.md` — canonical layer-by-layer measurement guidance. Referenced from Audit, Review, Resync, Dry-Run, and Creation modes.
- `/write-ibs` — the IB authoring skill. The IBs `/write-evals` consumes are produced by `/write-ibs`; the §Probe Results scratch-pad section in particular feeds eval threshold selection.
- `/write-intent` — Intent IRs may carry probabilistic acceptance criteria that flow into the child IB and from there into evals.
- `plugins/dekspec/commands/doctor.md` — once T-EVAL-* rules land, the inlined fidelity body in `/doctor` Stage 2 picks them up automatically via the audit-profile registry.

## Common Pitfalls

- Don't let the coding agent author or "help draft" the eval — author it BEFORE the session opens; an eval the candidate model wrote grades itself (grader == candidate), which is the failure mode this skill exists to prevent.
- Don't write a single expected value ("returns the right answer") — write a threshold or distribution across a pinned trial budget (`Recall@5 ≥ 0.7 over 50 trials`); a probabilistic behavior with no range is not an eval, it's a flaky deterministic test.
- Don't anchor the pass threshold on a number you remember from prior conversation — derive it from the IB's acceptance criteria / §Probe Results baselines, or honor the CONTEXT CHECK and ask to `/clear`.
- Don't ship an eval missing its model pin or sampling strategy (temperature / top_p / seed / trials) — without them the eval is not reproducible and the next run's "regression" is noise.
- Don't put a deterministic check (data shape, retry logic, persistence) under `tests/evals/` — that belongs in `tests/` and is the coding agent's job; evals are probabilistic-only.
- Don't delete a stale scenario silently on resync — move it to `tests/evals/archive/<bead-id>/` with a provenance note so the audit trail survives.
- Don't use the same model for an LLM-as-judge eval as the model under evaluation — pin a different judge model per `eval-quality-checklist.md` §End-to-End Quality.

## Verification Checklist

- [ ] Every authored/touched eval has all per-eval fields populated (scenario / type / layer / input / range / pass criterion / model pin / sampling strategy / failure meaning) — no `<...>` placeholders survive.
- [ ] Every pass criterion pins trial count × run count × range (no bare threshold) and traces to an IB acceptance criterion or `§Probe Results` baseline.
- [ ] Each eval declares exactly one measurement layer (retrieval / injection / awareness / E2E), or explicitly justifies a cross-layer eval citing both checklist subsections.
- [ ] Every model-output behavior in the source IB's Done-When has ≥1 eval covering it; no eval tests a behavior absent from the current IB.
- [ ] Eval files are saved under the correct `tests/evals/{behavioral,regression,adversarial}/` subdir as `<bead-id>_<scenario-name>.md`, and the bead's `evals` field references each by path.
- [ ] Eval-set status is `DRAFT` after Creation/Revise (only `--accept` flips it to `ACCEPTED`), and the touched modes appended their Amendment-Log row (Create / Revise / Accept).
- [ ] Audit Mode was re-run on the final eval set and reports no `critical` / `important` finding (or the residual was surfaced to the engineer, not silently swallowed).

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise an eval suite — Creation, `--accept`, `--revise`, `--resync`). After the artifact file is saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
