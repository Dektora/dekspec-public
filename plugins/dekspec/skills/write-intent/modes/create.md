# Creation Mode

[← back to dispatcher](../SKILL.md)


> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `dekspec:intent-author` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles them into the prompt; the subagent executes them in fresh context; the orchestrator validates the result via `dekspec check validate --kind intent <path>` on return.

### Step 1: Input

Engineer's description: `$ARGUMENTS`

Optional structured cues the engineer may pass inline:

- `type: <feature|bug|nfr|adr-driven|refactor|documentation|environment>` — Intent type
- `mission: MSN-NNN` — parent Mission (Phase 2; absent in Phase 1)
- `source: <url-or-note>` — provenance
- `autonomy: <manual|low|medium|high>` — autonomy override (default by Intent type — see Step 4 Autonomy bullet)

If `type:` is not provided, ask the engineer one direct question and parse the answer against the controlled vocabulary. Do not infer — type drives required fields and the default Verification predicate, so a wrong guess wastes work.

> **Feasibility check (ds-dekspec-spike).** If the engineer's input rests on an
> unvalidated *approach* — an algorithm choice, a third-party integration, or a
> performance/scaling assumption the Intent would bake in — surface:
> "The approach looks unproven — consider `/dekspec:spike <hypothesis>` first to
> validate it, then cite the spike record in this Intent's Motivation." A spike
> de-risks the approach before the Intent commits; it is distinct from
> `/dekspec:prototype` (which explores a design *shape*).

### Step 2: Serialization Advisory

**Per-Mission serialization, advisory enforcement (ADR-016).** Intent
serialization is scoped to the Mission: within one Mission, at most one child
Intent should be in active status at a time — child Intents are dependency-
ordered, so the Mission's Intent queue is also its serialization queue. Across
distinct Missions, and for Mission-less standalone Intents, there is no
serialization limit. Enforcement is advisory — creation is **never refused** on
serialization grounds. The pre-ADR-016 rule (one active Intent across the whole
repo, hard-enforced here) is retired.

Run `scripts/serialization_guard.py` (in this skill's folder) as a courtesy —
it reports any Mission already carrying more than one active Intent:

```
python plugins/dekspec/skills/write-intent/scripts/serialization_guard.py
```

The script always exits 0. If it reports that the new Intent's intended Mission
already has an active Intent, surface that to the engineer as a non-blocking
note and proceed. The gate of record is `dekspec audit linkage`, not this
skill. A missing `dekspec/intents/` directory (first Intent in the repo) is
treated as no-conflict; create the directory in Step 5.

### Step 3: Context Gathering

1. Read the Intent template at `dekspec/templates/intent-template.md` — every section is required at write time except optional ones (Mission, Source, Superseded-By).
2. Read CLAUDE.md sections **§Component → File-Glob Map** and **§Verification Predicate Library** — the canonical sources for Components affected and the type-default Verification predicate.
3. Read `dekspec/architecture-elements-index.md` — Linked Architecture Elements is mandatory (Decision D12), and at least one AE-NNN reference must resolve to an existing AE (audit-v2 L7).
4. Read `dekspec/domain-glossary.md` for canonical terminology.
5. Read `dekspec/dekspec-operating-guide.md` §Intents (when published in Phase 1 P1.9 — until then, fall back to v5 design plan §"Intent" sections in `docs/workspace/dekspec/mission and intent/intent-mission-design-plan-v5-2026-04-26.md`).
6. **Resolve the author target FIRST (ADR-030 hard default).** Run `dekspec library author-target --kind INT` (add `--canonical` iff the engineer passed `--canonical` to this skill). This verb is the single source of truth for the provisional-vs-canonical routing decision — do not hardcode the directory or the allocation choice here. It returns JSON with `target_dir` and `allocate_canonical`:
   - **Default (no `--canonical`):** `target_dir` is under `dekspec/provisional/` and `allocate_canonical` is `false`. **Do NOT allocate a canonical INT-NNN** — the artifact incubates with a `INT-provisional-<slug>` working name (see `dekspec library new-provisional` layout) and the canonical id is allocated later at promotion time.
   - **Opt-out (`--canonical`):** `target_dir` is `dekspec/intents/` and `allocate_canonical` is `true`. Only then, allocate the next INT-NNN deterministically — run `python ../_lib/scripts/artifact_ops.py next-id intent` (surface stderr on non-zero exit). **Reserved numbers:** `INT-000` is the WS-028 retrofit slot (Phase 1 P1.8 only); the script returns max+1 so production numbering starts at `INT-001` once any real Intent exists.

### Step 4: Draft

Fill the Intent template completely. Do **not** leave placeholders in any required field — ask the engineer instead.

- **Title** — verb-first; the title alone tells the reader what lands when this Intent reaches LOCKED.
- **Status** — `DRAFT`.
- **Intent type** — from the engineer's `type:` cue or direct question; controlled vocabulary only.
- **Autonomy** — engineer's `autonomy:` cue, else default by Intent type — `medium` for `bug` / `refactor` / `documentation`, `manual` for `feature` / `nfr` / `adr-driven` / `environment`. Engineers override explicitly when the change is more (or less) trustworthy than the type-default. (Rationale: per INT-094, downstream auto-merge surfaces (e.g. DekFactory INT-063) close the dispatch loop at `medium`+ once CI is green; defaulting `bug`/`refactor`/`documentation` Intents to `manual` silently opts out of a verification path the consumer has already paid to build.)
- **Branch** — `int/INT-NNN-<slug>`.
- **Mission** — engineer's `mission:` cue, else `none`. If a Mission is named, also load `dekspec/missions/MSN-NNN-*.md` (Phase 2; if missing, log a warning — do not hard-fail in Phase 1).
- **Source** — engineer's `source:` cue, else `none`. Provenance only — Linear / Slack / Issue / TODO / conversation reference. Not a parent.
- **Superseded-By** — `none` (only set when Status becomes SUPERSEDED).
- **Created / Modified** — today's date.
- **Linked Architecture Elements** — *mandatory* (Decision D12, audit-v2 L7). Ask the engineer which AE-NNN(s) this Intent shapes; at least one must be present and must resolve to an existing AE file. If the engineer cannot name one, the Intent's scope is too small to warrant an Intent or there is an AE that needs writing first — stop and surface that.
- **Motivation** — 1–3 paragraphs. **Problem-first, user-grounded framing is mandatory (INT-168 / D5).** The first thing the Motivation must establish is the concrete *problem* and the *user or persona* who feels it — not the task to be done and not the solution to be built. A Motivation that names only a task ("rename the dispatcher", "add a `--json` flag") or only a solution ("introduce a cache layer") without first naming who is hurting and how is **incomplete** — do not accept it; push the engineer back to "what breaks for whom, today, without this?" before writing the desired outcome. This bites hardest on `bug` and `refactor` Intents, which slip past with task- or solution-shaped motivations precisely because nothing else in the flow demands the problem-first framing. Stay at the motivation level; **no measurable targets** (move to a Working Spec, audit-v2 D19); **no decision rationale** (move to an ADR, audit-v2 D20).
- **Desired Outcome** — what is observably true after the Intent lands.
- **Non-Goals (optional; expected only when the Intent has *no* parent Mission)** — when `Mission:` is `none`, a standalone Intent has no Mission `Out-of-scope` contract to pin its non-goals against, so author an optional `## Non-Goals` section listing what this Intent will deliberately *not* do (the boundary that stops solo-Intent scope creep). When a parent Mission *is* named, do **not** duplicate non-goals here — the Mission's `Out-of-scope` owns them. A Mission-less Intent lacking this section draws the P3-advisory `T-INT-NON-GOALS-MISSING` finding (INT-168 / D6) — advisory, never a blocker, and silent on already-LOCKED Intents.
- **Type-specific required fields** — populate the block matching the type. For `bug`: ask for the Reproduction — preferably the deterministic PASS/FAIL repro signal `/diagnose` built in PHASE 1; if no repro could be constructed, populate the `### bug — Non-Reproducible Waiver` section instead (the `T-BUG-REPRO-GATE` rule accepts either, and fires a P3 advisory on a ≥ACCEPTED bug Intent carrying neither). For `nfr`: ask for Metric and Target. For `adr-driven`: ask for the driving ADR-NNN. For `refactor`: ask for the Behavior-Equivalence statement **and apply the behavior-split + coverage-first discipline below**. For `documentation`: ask for the Coverage-Gap statement. For `environment`: ask for the Environment-Change description. Delete the type-specific blocks that do not apply.
  - **`refactor` behavior-split + coverage-first discipline (INT-168 / D17).** A single `Behavior-Equivalence:` assertion is not enough — it does not separate work that *preserves* behavior from work that *changes* it, and it does not establish a safety net. When authoring a `refactor` Intent, additionally:
    1. **Split behavior-preserving from behavior-changing.** In the `Behavior-Equivalence:` block, explicitly partition the work into (a) the behavior-*preserving* moves (pure restructuring — extract, rename, relocate, dedup — observably identical inputs→outputs) and (b) any behavior-*changing* moves. If the answer is "this is a pure refactor," the behavior-changing list must be empty and the Intent says so; a non-empty behavior-changing list means the change is not actually a no-op refactor and must be called out (often it belongs in a separate `feature`/`bug` Intent so the refactor stays clean).
    2. **Coverage-first.** Name the *existing* test coverage that pins the current behavior *before* any edit begins. If the surface is under-covered, the first IU establishes the missing characterization tests (red against current behavior is impossible — they pass against today's code) so the refactor has a safety net. Every refactor step must leave the code runnable — no "broken mid-refactor with the tests commented out" intervals.
- **Components affected** — file-glob list. Engineer may name components from the CLAUDE.md component map (resolved to globs) or inline globs directly. Both forms are valid; the skill normalizes to the inline-glob form on save.
- **Verification** — populate from the type default in CLAUDE.md §Verification Predicate Library. Substitute placeholders from type-specific fields:
  - `<reproduction-test-path-from-IB-1>` → fill at `--decompose` time (Part B); leave the placeholder verbatim in the DRAFT.
  - `<Metric>` / `<Target>` → from the nfr block.
  - `<environment-smoke-script>` → from the engineer's environment-change description.
- Leave **Coverage Report**, **Size Assessment**, **Layer impact analysis**, **Open Issues**, **TESTFAIL records**, **Post-implementation sync**, and **Amendment Log** as their template-empty shapes. `--analyze` populates the first three; the rest fill in over the lifecycle.

If `mission:` is set, additionally enforce `Intent.Autonomy ≤ Mission.Autonomy_ceiling`. Phase-1 caveat: if the Mission file does not yet exist, log a warning and proceed — Mission validation hardens at Phase 2 P2.6 when audit-v2 rule L8 lands.

### Step 5: Save and Branch

Use the `target_dir` / `allocate_canonical` decision from Step 3.6 (the `dekspec library author-target` verb is the routing authority — never re-derive the directory by hand).

1. Ensure `target_dir` exists (create it if absent).
2. Save the Intent (Status `DRAFT`):
   - **Default (provisional, `allocate_canonical=false`):** save to `<target_dir>/INT-provisional-<slug>.md` — the canonical graph and `dekspec/intent-index.md` are untouched. (This mirrors `dekspec library new-provisional INT <slug>`; you may run that verb to scaffold the skeleton + branch in one shot.) Skip steps 3–4's canonical-index update; instead create the branch `int/INT-provisional-<slug>` and hand off.
   - **Opt-out (`--canonical`, `allocate_canonical=true`):** save to `dekspec/intents/INT-NNN-<slug>.md` using the INT-NNN allocated in Step 3.6, then continue with steps 3–4 below.
3. **Worktree-collision guard (ds-2tky).** Before creating the branch, run the guard so a second Intent lifecycle in the same checkout cannot flip HEAD against this one:

   ```
   python plugins/dekspec/skills/write-intent/scripts/worktree_guard.py --new-branch int/INT-NNN-<slug>
   ```

   - Exit `2` → HEAD is on another `int/INT-*` branch. **Do NOT `git checkout -b` on the shared tree** — branching one Intent off another's HEAD lets their commits collide and pollutes diff-confinement at `--testpass`. Create an isolated worktree from a clean base (the guard prints the exact `git worktree add … -b int/INT-NNN-<slug> main` command), then run the Intent lifecycle inside that worktree.
   - Exit `0` → safe; proceed. (An advisory may list other in-flight Intent branches — heed it if a coding/spec session for one of them is active in this checkout.)

   Then create the branch: `git checkout -b int/INT-NNN-<slug>` (canonical) or `int/INT-provisional-<slug>` (provisional). The Intent file is in the working tree on the new branch — commit it as the first commit on the branch.
4. (Canonical only) Update `dekspec/intent-index.md` (created at P1.5; until then, log "intent-index.md not yet present — index update will be backfilled when P1.5 lands" and continue). Append a row to the Active queue with INT-NNN, title, type, status, branch, created date, owner.

### Step 6: Hand Off

Tell the engineer: the Intent is in DRAFT. Run `/write-intent --analyze <path>` next to surface coverage / size / type-specific gaps and promote to PROPOSED.

**End of Creation Mode.**
