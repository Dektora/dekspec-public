# DekSpec Fan-Out Mode — Canonical Substrate

**Status:** AUTHORITATIVE (per architectural directive `ds-di2`, 2026-05-19).
**Audience:** DekSpec skill authors. Every authoring or audit skill whose substantive-work modes (creation, accept, revise, decompose, analyze, audit-pass, etc.) route through a fresh-context subagent via the `Agent` tool cites this file in its `## Fan-Out Mode` section and supplies a manifest. The orchestrator/subagent contract below is enforced uniformly across skills.
**Sibling substrates:** `_lib/mode_dispatcher.md` (universal mode catalog + Mode-Detection prose); `_lib/teaching_mode.md` (Teaching Mode contract); `_lib/help_mode_template.md` (Help Mode rendering); `_lib/lock_unlock.md` (lifecycle promotion).

---

## Why this file exists

The `ds-di2` architectural directive (2026-05-19) split every authoring / audit skill into two halves: an **orchestrator** (the SKILL.md body, runs in the parent session) and a **subagent** (a fresh-context worker dispatched via the `Agent` tool). Before this substrate landed, every skill's `## Fan-Out Mode` section embedded the same ~30-50 lines of framing prose verbatim:

- The architectural-directive citation (`ds-di2`, 2026-05-19) and the rule that substantive-work modes delegate.
- The orchestrator/subagent role split (parent never drafts, audits partial content, or writes the artifact file).
- The substantive-vs-inline mode tablature for that skill.
- The four-bullet rationale (context isolation, indirect quality test, parallelism, per-artifact model selection).
- Step 1 ("Bundle context") preamble describing deterministic-order collection.
- Step 2 ("Dispatch via the seam") preamble + the fenced prompt template skeleton.
- Step 3 ("Validate + report") preamble + the do-not-silently-retry rule.
- The terminal "Subagent failure handling" paragraph.

Three concrete consequences of leaving this prose inline in every skill:

1. **Pattern drift across skills.** The "do not silently retry" sentence had three minor wording variants by the time 13 skills had each copied it. The orchestrator/subagent role split was stated differently in `write-adr` vs `write-ws` despite being the same contract.
2. **Authoring new fan-out skills is high-friction.** A new skill author copies ~100 lines of framing from the nearest sibling, then hand-edits every paragraph for the new artifact kind. Mistakes compound (wrong subagent type, missed "End of Fan-Out Mode" terminator, stale "13 skills" count).
3. **No canonical reference for the orchestrator/subagent contract.** When the engineer asked "what is the subagent allowed to assume from the parent session?", the answer was implicit in the copy-paste pattern, not documented anywhere.

This file is the source of truth. Each consuming SKILL.md cites it, supplies a short manifest with only the variable parts (subagent type, substantive vs inline mode lists, bundle-list contents, expected output path, validation command), and lets the substrate carry the rest.

## Orchestrator / subagent contract

Every skill that fans out splits into two layers:

- **Orchestrator (the SKILL.md body, parent session).** Parses `$ARGUMENTS`, runs cheap mechanical preconditions, bundles every input the subagent will need, dispatches the subagent through the harness seam (`run_fanout` / `get_adapter(host).dispatch_subagents`, which on the Claude harness is realized by the `Agent` tool), and validates / reports on whatever the subagent returns. The orchestrator never drafts artifact prose, never runs the artifact's content audit against a partial draft, and never writes the artifact file directly — those are the subagent's job.

- **Subagent (fresh context, dispatched through the seam).** Runs in a context with no parent-session history; anything not in its prompt is invisible to it. Produces the artifact at the bundled output path, runs the bundled validation command, and returns a one-paragraph summary plus any blocking findings. If the bundled context is insufficient to produce a clean artifact, the subagent returns an explicit `INSUFFICIENT_INPUT: <what is missing>` signal rather than guessing.

The fan-out is the **default** path for the modes the skill's manifest names under `substantive_modes`. The modes the manifest names under `inline_modes` (queries, status walks, interactive flows, engineer-facing prose, deferred-by-design modes) run inline in the parent session and never fan out.

## Rationale (the four reasons fan-out is the default)

1. **Context isolation.** The subagent's session has none of the parent's prior conversation history. The artifact is authored from the bundled materials only — no contamination from earlier scratch work, abandoned drafts, or unrelated reasoning that biases the output. This matters especially for load-bearing artifacts (`write-sv`, `write-constitution`) where parent-session contamination is most dangerous.

2. **Indirect quality test of bundled materials.** If the subagent cannot produce a clean artifact from the bundle, that is a real signal that the bundle is incomplete — the orchestrator should expand the bundle (or surface the gap to the engineer) rather than retry the subagent with looser validation. The fan-out exercises the bundle as a test of its own completeness.

3. **Natural parallelism.** N artifacts can be drafted by N parallel subagents (e.g., `write-tests --all` fans out one subagent per bead in the batch; `write-ibs` can decompose a Working Spec into multiple IBs in parallel). The orchestrator collects the per-subagent reports and emits a batch summary.

4. **Per-artifact model / effort selection.** Each subagent dispatch can pick the model tier appropriate to the artifact (e.g., heavy Opus for a load-bearing AE, lighter Sonnet for a mechanical IB). The orchestrator carries no such constraint — it is small and mechanical regardless of the artifact's complexity.

## Canonical three-step skeleton

Every consuming SKILL.md's `## Fan-Out Mode` section follows the same three-step shape. The substrate-side contract for each step is below; the skill-side manifest supplies the variable parts (bundle list, output path, validation command).

### Step 1: Bundle context (orchestrator, parent session)

The orchestrator gathers every input the subagent will need, in deterministic order, before dispatching through the seam. Fan-out fails its purpose if the subagent has to ask back for missing materials.

The skill-side manifest enumerates the bundle items under `bundle_list`. Every entry is either an absolute path the subagent will `Read`, or an inline value (literal text, JSON object, list of paths) the orchestrator pastes into the prompt. The substrate-side rules for bundling:

- **Resolve paths to absolute before dispatch.** Subagents should never have to guess `cwd`.
- **Bundle the template + the methodology references + the related-artifacts paths + the engineer guidance (`$ARGUMENTS` verbatim) + the constraints (as an explicit list the subagent must enforce) + the expected output path + the validation command.** These seven categories cover every fan-out skill; the manifest's `bundle_list` enumerates the per-skill specifics within each category.
- **Run cheap mechanical preconditions inline before dispatch.** Examples: singleton-precheck (refuse if a singleton artifact already exists at a non-DEPRECATED status); L12 status-gate (refuse to dispatch an IB-decomposition against a non-ACCEPTED Working Spec); ID-allocation (compute the next free `<KIND>-NNN` from the index). If a precondition fails, the orchestrator surfaces the failure to the engineer and does not dispatch.
- **If a required bundle item is missing** (e.g., the template file is not vendored, the parent WS is not at ACCEPTED, the engineer guidance is empty in `--revise`), STOP before dispatching and surface the gap. Do not dispatch the subagent against an incomplete bundle.

### Step 2: Dispatch via the seam (orchestrator, parent session)

Dispatch is **host-neutral**: it goes through the harness seam, not directly at any one host's tool. The orchestrator calls `dekspec.harness.run_fanout(tasks, host=<host>, ...)` (equivalently `get_adapter(host).dispatch_subagents(tasks, ...)`), and the resolved adapter realizes the dispatch on whatever host is running — **Claude** realizes it via the `Agent` tool, **Codex** via its multi-agent surface, **Antigravity** via dynamic subagents, **Cursor** via async/nested subagents. The substrate authors describe the dispatch once; the seam guarantees the same result-shape and index-alignment (result[i] ↔ tasks[i]) on every host. On the Claude harness the concrete mechanism below — invoking the `Agent` tool with the three parameters — *is* how the seam realizes a dispatch, so the contract reads identically:

Realize each subagent dispatch (on Claude, via the `Agent` tool) with three required parameters:

- **`subagent_type`** — the value from the skill's manifest. Use the artifact-specific `dekspec:<kind>-author` type if one exists; fall back to `general-purpose` if no dedicated type is registered yet (write-constitution, write-evals, write-sp, write-sv, write-tests currently use `general-purpose`).
- **`description`** — a short label naming the mode + target (e.g., `"author AE-NNN"`, `"accept <path>"`, `"revise <path>"`, `"decompose WS-NNN into IBs"`, `"write tests for BEAD-NNN"`).
- **`prompt`** — a **self-contained** prompt that includes every bundle item from Step 1 plus the mode-specific contract (the body of the matching mode section below — e.g., §Creation Mode steps, §Accept Mode steps, §Revise Mode steps). The subagent must not need any context from the parent session beyond what this prompt contains.

The canonical prompt template (the orchestrator composes the real prompt at runtime by substituting bundled values):

```
You are <subagent_type> dispatched by /<skill_name> in <mode> mode. Run in fresh context.

MODE: <Creation | Accept | Revise | ...> (one of the modes from substantive_modes)

TEMPLATE:     <bundled template path>
METHODOLOGY:  <bundled methodology references>
RELATED ARTIFACTS (paths):
  - <bundled path 1>
  - <bundled path 2>
  - ...

ENGINEER GUIDANCE ($ARGUMENTS):
  <verbatim>

CONSTRAINTS (must hold on output — self-audit before return):
  - <constraint 1 from the skill's Rules block>
  - <constraint 2>
  - ...

EXPECTED OUTPUT PATH:
  <bundled expected_output_path>

VALIDATION COMMAND (the orchestrator will run on your return):
  <bundled validation command>

MODE CONTRACT:
  <full step-by-step body of the matching mode section in the skill body>

Produce the artifact at the expected output path. Return a one-paragraph summary of
what you did, plus any blocking findings. If the bundled context is insufficient to
produce a clean artifact, return:
  INSUFFICIENT_INPUT: <what is missing>
rather than guessing — do NOT invent facts.
```

For batch fan-outs (e.g., `write-tests --all` dispatches one subagent per bead; `write-ibs` may dispatch one subagent per IB in the decomposition): the orchestrator passes the whole task set through the seam (`run_fanout(tasks, parallel=True, ...)`), which dispatches in parallel and returns index-aligned per-subagent results; the orchestrator collects the per-subagent reports and emits a batch summary.

### Step 3: Validate + surface cleanly (orchestrator, parent session)

On subagent return:

1. **Parse / capture the subagent's output.** If the subagent returned `INSUFFICIENT_INPUT:`, surface the named gap to the engineer verbatim and halt — this is the indirect quality signal from Rationale #2. Do NOT silently retry; ask the engineer what additional context to bundle.

2. **Run the bundled validation command** from the manifest (`dekspec validate <output-path>`, `pytest --collect-only <output-path>`, `/write-evals --audit <BEAD-NNN>`, or the skill-specific equivalent). Non-zero exit → surface the validation error verbatim alongside the subagent's own findings; do **not** silently retry with looser validation. The pattern's value is that a subagent that can't produce a clean artifact exposes a gap in the bundled context.

3. **Run mode-specific post-checks.** Confirm the file exists at the expected output path; confirm the status walk happened (PROPOSED for Creation, ACCEPTED for Accept, reset to PROPOSED for Revise on previously-LOCKED artifacts, etc.); confirm Amendment Log entries were appended where required; confirm the index was updated; confirm any cascade reminders are surfaced to the engineer.

4. **Report to the engineer.** Name the file written/edited, the Status transition (if any), the Amendment Log entry (if any), and the next recommended mode.

**Subagent failure handling — the canonical paragraph.** If the subagent returns "could not produce a clean artifact given the bundled context" (or its `INSUFFICIENT_INPUT:` equivalent), surface this explicitly: name what context was bundled (the Step 1 list) and what was reported missing. The fix is to expand the bundle in the orchestrator (or backfill the upstream artifact the subagent needed), **not** to retry blindly with the same bundle. This is the load-bearing application of Rationale #2: the subagent's inability to produce a clean artifact is real information about input quality, not noise to be retried away.

(*Note for cluster 7 — `_lib/validate_and_surface.md` extraction:* the Step 3 contract above is the natural extraction target for the validate-and-surface substrate. If cluster 7 ships, the canonical Step 3 prose moves there, and this file's Step 3 section becomes a short citation back to it. Until cluster 7 lands, the prose stays here and consuming skills cite this file for the full three-step contract.)

**End of Fan-Out Mode** is the terminal marker every consuming SKILL.md emits at the end of its `## Fan-Out Mode` section, on its own line as `**End of Fan-Out Mode.**`. Skills with downstream inline-only sections (e.g., `write-ibs`'s "the inline sections below … are the AUTHORITATIVE SPEC the worker follows") may extend the terminator with additional skill-specific guidance after the period — see write-ibs for the canonical extended form.

## Skill-side manifest (inline this in your SKILL.md)

Each consuming SKILL.md replaces the per-skill `## Fan-Out Mode` body with the canonical citation + manifest block below. The substrate carries the framing; the manifest carries only the variable parts.

```markdown
## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: <e.g., `dekspec:ws-author` or `general-purpose`>
- **substantive_modes**: [<list of mode flags that fan out — e.g., Creation (default), `--accept`, `--revise`>]
- **inline_modes**: [<list of mode flags that stay inline — e.g., `--help`, `--teaching`, `--audit`, `--review`, `--lock`, `--unlock`>]
- **bundle_list** (Step 1 context):
  1. <skill-specific bundle item 1 — e.g., template path>
  2. <skill-specific bundle item 2 — e.g., parent IB path>
  3. <skill-specific bundle item 3 — e.g., related ADRs with supersession applied>
  4. ...
- **expected_output_path**: <e.g., `dekspec/working-specs/WS-NNN-<slug>.md` for Creation; the input path for Accept / Revise>
- **validation**: <e.g., `dekspec validate <path>` + the §Audit Mode checklist; or `pytest --collect-only <path>`; or `/write-evals --audit <BEAD-NNN>`>

**End of Fan-Out Mode.**
```

The manifest deliberately keeps the substantive-modes / inline-modes lists in the SKILL.md (not factored into the substrate) — they are the per-skill load-bearing tablature the dispatcher tests can grep against, and the engineer reading the skill needs to see at a glance which flags trigger fan-out vs which run inline.

## When NOT to use fan-out

Some skills deliberately defer fan-out because their substantive work is interactive multi-turn with the engineer (and the back-and-forth signal is the value the skill provides). The canonical example is `write-ggc`:

- `--log` pauses on partial matches to ask the engineer whether two corrections are the same; Step 5 (Auto-Promote) mutates the glossary based on recurrence-count state the engineer must confirm.
- `--add-term` waits for engineer response on synonym matches before deciding to add a separate entry or update an existing one.

For these skills, the `## Fan-Out Mode` section cites this substrate's "When NOT to use fan-out" rationale and explains the deferral inline. The manifest's `substantive_modes` list is `[]` and `inline_modes` lists every mode. The substrate's three-step skeleton is not applicable; the deferral paragraph is the entire section. **Trigger to revisit:** if a non-interactive batch mode is ever added (e.g., `--log --batch <file>` ingesting pre-disambiguated corrections), fan that mode out at that time per this substrate.

## Per-skill migration checklist

When refactoring an existing fan-out skill to the substrate:

- [ ] Replace the existing `## Fan-Out Mode` body with the manifest block above (citation + 5-bullet manifest + terminator). Preserve any genuinely skill-unique fan-out guidance in a short paragraph after the manifest if it doesn't fit one of the manifest keys.
- [ ] Confirm the manifest's `substantive_modes` list matches the mode flags whose section bodies invoke fan-out, and `inline_modes` lists the rest.
- [ ] Confirm `subagent_type` matches what's actually dispatched (the artifact-specific `dekspec:<kind>-author` if registered, else `general-purpose`).
- [ ] Confirm `bundle_list` enumerates every input the subagent needs without parent-session lookback (template, methodology, related artifacts, engineer guidance, constraints, expected output path, validation command).
- [ ] Confirm the per-mode section bodies (`## Creation Mode`, `## Accept Mode`, `## Revise Mode`, ...) still describe the substantive workflow the subagent runs under the hood — the manifest does NOT replace those sections; it replaces only the meta-framing of `## Fan-Out Mode`.
- [ ] Run `python -m pytest -q` — must be green (and specifically `tests/test_skills_dispatcher.py` if it exists).

## Reconsideration triggers

This substrate's contracts should be revisited if:

- A new artifact kind enters DekSpec whose substantive work cannot be expressed as bundle + dispatch + validate (e.g., a streaming or long-running mode where the orchestrator must remain responsive to subagent intermediate outputs). Add the new dispatch shape to this substrate first, then introduce it in the new kind's skill.
- The "do not silently retry" rule in Step 3 degrades into "retry with looser validation" in practice (sign that the indirect-quality-test rationale isn't holding up). Tighten the prose or introduce a structured `INSUFFICIENT_INPUT` enum.
- Skills end up with substantially more skill-specific divergence than this substrate captures (sign that the substrate is under-fitting). Document the new shared shape here and reduce the divergence.
- Cluster 7 ships `_lib/validate_and_surface.md`. At that point, Step 3 of this file shrinks to a citation back to `_lib/validate_and_surface.md`, and the canonical validate-and-surface prose lives there.

## Links

- `ds-di2` (architectural directive bead, 2026-05-19) — the parent decision this substrate codifies.
- `_lib/mode_dispatcher.md` — the multi-mode dispatcher substrate (sibling).
- `_lib/help_mode_template.md` — the Help Mode rendering substrate (sibling).
- `_lib/teaching_mode.md` — the Teaching Mode contract (sibling).
- `_lib/lock_unlock.md` — the lifecycle promotion substrate (sibling).
- `AE-006 Skills Library` — the AE this substrate lives within.
