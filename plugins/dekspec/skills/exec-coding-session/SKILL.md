---
name: exec-coding-session
description: Dispatch unblocked beads to parallel sub-agents in isolated worktrees, then collect results and land the plane.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Bash Agent
argument-hint: [<ib-path-or-id> | --package <sha-or-path> | --confirm-dispatch | --dry-run | --help] [optional engineer guidance]
related_skills: [write-beads, write-tests, orchestrate-intent, review-pr]
---

Orchestrate a parallel coding session across multiple beads.

> **Fresh-context dispatch — structural, not advisory.** Orchestration is exactly the kind of work where stale conversation context is dangerous: it decides which beads to claim, which executor to dispatch them through, and how to reconcile results, and a polluted context window can anchor those decisions on phantom state. This skill therefore does not *ask* the operator to `/clear` before continuing — it delegates its orchestration body into the `dekspec:coding-orchestrator` subagent. Being invoked as a subagent **is** the fresh context: the subagent carries none of this session's prior history, so "dispatch runs in fresh context" becomes a structural guarantee of the dispatch path rather than a prose warning the operator can decline. The `dekspec:coding-orchestrator` subagent carries the full Phase 1-5 dispatch contract authoritatively; this skill resolves the inputs (the claimed bead set + the resolved IC-004 executor — `local` for this skill) and hands them to that subagent. The Phase sections below are the authoritative dispatch logic the subagent adopts.

## Starter Prompt

```prompt
/dekspec:exec-coding-session INT-123

Build the package for INT-123 and dispatch its ready bead set in parallel
worktrees. Auto-dispatch is fine — show me the plan, then land the plane.
```

## Mode Detection

Parse `$ARGUMENTS` for flags. If `--help` is present, skip to **Help Mode**. Otherwise:

- If `--package <sha-or-path>` is present, extract the value into shell var `$PKG_ARG` (the value can be a full SHA hex, a SHA prefix matching exactly one tarball under `.dekspec/packages/`, or an explicit `.tar.gz` path). Strip the `--package <value>` pair from `$ARGUMENTS` before proceeding so engineer guidance prose isn't polluted with the flag.
- Alternatively, if a positional IB path/ID or Intent ID (e.g. `dekspec/impl-briefs/IB-123-*.md` or `IB-123` or `INT-123`) is provided as the first positional argument in `$ARGUMENTS`, extract the value into shell var `$IB_ARG` and strip it from `$ARGUMENTS` before proceeding.
- Strip any other flags (`--confirm-dispatch`, `--dry-run`) and proceed.

If `$IB_ARG` was provided, automatically build the package for the Intent first:
```bash
if [[ "$IB_ARG" == INT-* ]]; then
  PKG_INTENT_ID="$IB_ARG"
else
  PKG_INTENT_ID=$(.venv/bin/python -c "
import sys
from pathlib import Path
from dekspec.cli import _resolve_ib_to_intent
try:
    _, intent_id = _resolve_ib_to_intent(sys.argv[1], Path('.'))
    print(intent_id)
except Exception as e:
    sys.exit(1)
" "$IB_ARG")
  if [ -z "$PKG_INTENT_ID" ]; then
    echo "STOPPED — could not resolve IB/Intent argument $IB_ARG."
    exit 1
  fi
fi

BUILD_OUT=$(dekspec package build "$PKG_INTENT_ID" 2>&1)
if [ $? -ne 0 ]; then
  echo "STOPPED — failed to build package: $BUILD_OUT"
  exit 1
fi
PKG_ARG=$(echo "$BUILD_OUT" | grep -o 'package=[a-f0-9]\{64\}' | cut -d= -f2)
if [ -z "$PKG_ARG" ]; then
  echo "STOPPED — could not extract package ID from: $BUILD_OUT"
  exit 1
fi
```

If `--package` or a resolved `$PKG_ARG` was given, Phase 1's bead-discovery uses the Package manifest (see Phase 1 §Step 1 branches). If absent, Phase 1 runs `br ready` as usual.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/exec-coding-session"
one_line:   "Orchestrate parallel bead execution in isolated worktrees"
modes:
  - { flag: "--confirm-dispatch", args: "", description: "Pause after the dispatch plan and wait for engineer approval before launching sub-agents. Default is auto-dispatch (plan shown for transparency only)." }
  - { flag: "--dry-run", args: "", description: "Run Phase 1 (discover, claim, dependency check) and present the dispatch plan, but do not launch any sub-agents. Use for pre-flight planning." }
  - { flag: "--package", args: "<sha-or-path>", description: "Drive the session from a Package (built by `dekspec package build <intent-id>`) instead of `br ready`. The Package's manifest names the exact `bead_set` + `intent_id` + `ib_path` to run. Use to pin dispatch to a content-addressed bundle (replay; cross-session handoff; CI)." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/exec-coding-session"
  - "/exec-coding-session --confirm-dispatch"
  - "/exec-coding-session --dry-run"
  - "/exec-coding-session \"only dispatch BEAD-42 and BEAD-43\""
  - "/exec-coding-session --confirm-dispatch \"focus on the injection pipeline beads\""
  - "/exec-coding-session --help"
extra_sections:
  - heading: "WORKFLOW"
    body:
      - "Phase 1: Discover & claim unblocked beads, check dependencies"
      - "Phase 2: Dispatch sub-agents in parallel worktrees"
      - "Phase 3: Collect results, merge worktree branches"
      - "Phase 4: Land the plane — close beads, run tests, file follow-ups"
      - "Phase 5: Check for newly unblocked work"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Engineer Guidance

$ARGUMENTS

## Flags

- `--confirm-dispatch` — Pause after presenting the dispatch plan and wait for engineer approval before dispatching sub-agents. Without this flag, the dispatch plan is displayed for transparency and execution proceeds immediately.
- `--dry-run` — Run Phase 1 only. Discover, claim, and verify dependencies, then present the dispatch plan and stop. No sub-agents are launched. Claimed beads are unclaimed before stopping. Use for pre-flight planning and dependency verification.
- `--package <sha-or-path>` — **Package mode (per INT-028 / v0.53.0).** Drive the session from a content-addressed Package built by `dekspec package build <intent-id>` instead of querying `br ready`. The Package's manifest names the exact `bead_set` + `intent_id` + `ib_path` to run. Used for: dispatch replay (same SHA = same inputs); cross-session handoff (a packet dropped in `.dekspec/inbox/` per the future inbox/listener pattern); CI gates pinned to a specific bundle. The session still claims each bead via `br claim` and runs the standard dispatch / Phase 2-5 flow — `--package` only changes Phase 1's bead-discovery source.

## Pre-Flight Checks

Before doing anything else, verify all quality support files exist:

1. Run `br ready --json` to get the candidate bead list.
2. For each bead, run `../_lib/scripts/resolve_bead_context.py <bead-id>` and read `ib_path` from the JSON output (the script resolves the bead's `external_ref`, stripping any `:suffix` qualifier such as `IB-037:phase-2`).
3. Run `scripts/preflight_quality_gates.py <IB> [<IB> ...]` with the resolved IB paths. The script reads each IB, collects every referenced checklist / test / eval file path from the Quality Checklists, Files to Modify, and Acceptance Criteria sections, and verifies each exists on disk. It returns JSON `{missing, present, checked, ok}`.
4. Surface stderr on non-zero exit. The script exits **1** when any referenced quality file is missing (the STOP condition) and **2** when an IB path itself cannot be read. On exit 1 — STOP. Report the `missing` list:

  "⚠️ Quality gate files missing — session cannot proceed safely:
  - [path/to/missing/file.md]
   These files are referenced by the IB and are required for the quality process. Add them before running this session."

Do NOT proceed past this point until the script exits 0 (all referenced quality files exist).

5. Record the current HEAD for use in Phase 4:
  ```bash
   PRE_SESSION_COMMIT=$(git rev-parse HEAD)
  ```

## Session Lifecycle Wiring

Per WS-010 (MSN-002 orchestration plane), this skill opens a `dekspec` session on entry and closes it on exit, so per-attempt execution records (IC-004) acquire a `session_id` parent for cross-attempt audit. The session is opened **after** all Pre-Flight Checks STOP conditions clear (quality-gate files present, agent-mail reachable) — early-exit paths never leave a half-opened session.

### Prelude: open session

After Pre-Flight Checks pass and before Phase 1, detect any outer session and open a new one if needed:

```bash
# Resolve SESSION_BIND_ID per IC-004 prose below: if all claimed beads share one
# parent Intent, use INT-NNN; else use the first claimed bead's id. session_lifecycle.start()
# routes ^INT-\d{3,}$ → bound_intent_id, else → bound_bead_id.

# Detect outer session via the CLI's machine-readable status envelope.
STATUS_JSON=$(dekspec session status --machine-readable 2>/dev/null || echo '{"active":false}')
OUTER_SESSION_PRESENT=0
OUTER_BOUND_TO=""
if echo "$STATUS_JSON" | python -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('active') else 1)"; then
  OUTER_BOUND_TO=$(echo "$STATUS_JSON" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('bound_intent_id') or d.get('bound_bead_id') or '')")
  if [ "$OUTER_BOUND_TO" = "$SESSION_BIND_ID" ]; then
    # Outer session bound to the same target — defer to it.
    OUTER_SESSION_PRESENT=1
  else
    # Outer session bound to a different target — refuse to nest.
    echo "STOPPED — outer session active for $OUTER_BOUND_TO, refusing to nest under $SESSION_BIND_ID. End the outer session first (\`dekspec session end\`)."
    exit 1
  fi
fi
if [ "$OUTER_SESSION_PRESENT" = "0" ]; then
  dekspec session start "$SESSION_BIND_ID" --branch "$(git branch --show-current)"
fi
```

### Epilogue: report off-spec drift, then close session

At **SESSION COMPLETE** (end of Phase 5), first run `dekspec session report` so the operator sees any off-spec (vibecoding) drift recorded during the session (MSN-009) — the report runs against whatever session is active, whether this skill opened it or deferred to an outer one. Then close the session **only if this skill opened it** (skip when an outer session was deferred to):

```bash
# Off-spec drift summary (MSN-009) — surface vibecoding drift to the
# operator before the session closes. Read-only; runs unconditionally.
dekspec session report

if [ "$OUTER_SESSION_PRESENT" = "0" ]; then
  dekspec session end --reason "/exec-coding-session complete"
fi
```

**`--dry-run` exception:** When the skill is invoked with `--dry-run`, the prelude still runs (to honor the outer-session detection contract), but the epilogue runs **before** Phase 1's claimed beads are unclaimed and the skill exits. This keeps `--dry-run` from leaving a half-opened session.

### Failure modes

- **Outer session bound to a different bead/Intent:** the prelude STOPs with the diagnostic above. No beads are claimed; no agents are dispatched.
- **`dekspec session start` raises `SessionAlreadyActiveError`:** indicates a stale session the CLI did not auto-reap. Run `dekspec session reap` and retry the skill; if reap fails, surface to the engineer.
- **Pre-Flight Checks STOP fires before the prelude runs:** no session is opened; the skill exits cleanly. The epilogue does not run.
- **Phase 4 surfaces stopped or conflicted beads:** SESSION COMPLETE still fires at the end of Phase 5; the epilogue closes the session. The bead-level outcomes are recorded via the existing IC-004 lifecycle DB writes.

## Lifecycle DB writes (IC-004 compliance)

This skill is an in-process bead dispatcher (the former IC-004 executor contract has been DEPRECATED in MSN-016; this skill remains as the in-process dispatch surface). Each `/exec-coding-session` invocation MUST write to the execution-attempt lifecycle DB so the flywheel substrate (first-pass rate, time-to-merge, escalation rate) stays accurate. **Granularity: one execution attempt = one Intent's worth of work** (all beads dispatched in this session whose parent IB belongs to the same Intent). Per-bead state lives in events.

If `dekspec executions record-attempt --help` errors (engine not installed), stop and surface to the engineer — per the in-process dispatch contract, the dispatcher fails closed when the lifecycle DB is unavailable.

**Resolve Intent for each claimed bead**: Run `../_lib/scripts/resolve_bead_context.py <bead-id>`; read `intent_id` from the JSON output. The script walks the deterministic chain (bead `external_ref` → IB → IB's `**Spec:**` → parent WS; `intent_id` from the IB's `**Intent:**` field). Beads whose `intent_id` is `null` (loose tasks — the `notes` array explains which hop broke) skip lifecycle writes — note this in the dispatch plan and proceed.

**Phase 1 — after claiming**: for each unique Intent in the dispatch set, record the attempt. Run `scripts/resolve_parent_intent.py <bead-id> --record --agent <model>` for one bead of that Intent — the script computes the next attempt_number (highest existing `attempt_number` from `dekspec executions ls` plus 1), runs `dekspec executions record-attempt`, and returns the `attempt_id` in its JSON output. Surface stderr on non-zero exit:

```bash
scripts/resolve_parent_intent.py <bead-id> --record --agent <model>
# -> {"bead": "...", "intent": "INT-NNN", "attempt_id": "att-...", "next_attempt_number": N}
```

Maintain a mapping `intent_id → attempt_id` for the rest of the session.

**Phase 2-3 — per-bead events**: emit lifecycle events on the bead's parent Intent's attempt_id. Required minimums:

| Trigger | Command |
| --- | --- |
| Sub-agent reports test failures during workflow | `dekspec executions record-event --attempt $ATTEMPT_ID --type first_pass_fail --payload '{"bead_id":"<ID>"}'` |
| Sub-agent reports STOPPED (EXPERTISE GAP / CONFLICT / DEPENDENCY MISSING) | `dekspec executions record-event --attempt $ATTEMPT_ID --type escalation_request --payload '{"bead_id":"<ID>","reason":"<short>"}'` |
| Bead re-dispatched after engineer guidance | `dekspec executions record-event --attempt $ATTEMPT_ID --type retry --payload '{"bead_id":"<ID>"}'` |
| Sub-agent asks the engineer mid-flight | `dekspec executions record-event --attempt $ATTEMPT_ID --type agent_question --payload '{"bead_id":"<ID>","question":"<text>"}'` |

Custom events (executor-internal signals not in the canonical set) use `--type custom --custom-type <label>` — but downstream queries should not depend on custom events; the canonical set is the load-bearing surface.

**Phase 4 — landing the plane**: for each attempt_id, complete it with the aggregate session outcome:

- All beads merged + tests green: `dekspec executions complete --attempt $ATTEMPT_ID --ci-status pass`
- Some beads stopped / conflicts / regressions: `dekspec executions complete --attempt $ATTEMPT_ID --ci-status fail --escalation --notes "<n stopped, m conflict>"`
- A PR was opened + merged in this session (rare): add `--merged --merge-commit <sha>` to the success line.

Idempotency: `record-attempt` is idempotent on `(intent_id, attempt_number)` — re-invoking with the same pair returns the existing attempt_id rather than inserting a duplicate. Safe to retry.

## Phase 1 — Discover & Claim

**Step 1 branches on `--package`:**

- **Without `--package` (default)**: Run `br ready --json` to get all unblocked beads. Proceed to candidate filtering in step 2 against this set.

- **With `--package <sha-or-path>`** (Package mode): The work-set is pre-declared by the Package's manifest — skip `br ready` and read the manifest directly:

  ```bash
  # Resolve SHA → tarball → extract manifest.yaml → parse bead_set + intent_id + ib_path
  PKG_TARBALL=$(.venv/bin/python -c "
  import sys
  from pathlib import Path
  from dekspec.package.inspect import _resolve_package_path
  print(_resolve_package_path('$PKG_ARG', Path('.dekspec/packages')))
  " 2>&1)
  if [ -z "$PKG_TARBALL" ] || [ ! -f "$PKG_TARBALL" ]; then
    echo "STOPPED — --package $PKG_ARG did not resolve to a tarball under .dekspec/packages/."
    exit 1
  fi
  PKG_MANIFEST=$(.venv/bin/python -c "
  import json, yaml, tarfile
  with tarfile.open('$PKG_TARBALL', 'r:gz') as t:
    f = t.extractfile('manifest.yaml')
    print(json.dumps(yaml.safe_load(f.read().decode('utf-8'))))
  ")
  PKG_INTENT_ID=$(echo "$PKG_MANIFEST" | python -c "import sys,json; print(json.load(sys.stdin)['intent_id'])")
  PKG_IB_PATH=$(echo "$PKG_MANIFEST" | python -c "import sys,json; print(json.load(sys.stdin).get('ib_path') or '')")
  PKG_BEAD_SET=$(echo "$PKG_MANIFEST" | python -c "import sys,json; print('\n'.join(json.load(sys.stdin).get('bead_set') or []))")
  echo "Package mode: intent=$PKG_INTENT_ID ib=$PKG_IB_PATH beads=$(echo "$PKG_BEAD_SET" | wc -l)"
  ```

  Treat `$PKG_BEAD_SET` (one bead ID per line) as the candidate list. If the manifest's `bead_set` is empty (e.g., the operator built the Package without a populated bead_set — common for Mission-less Intents that don't have a claimed bead set yet), STOP and tell the engineer:

  > "⚠️ Package $PKG_ARG has empty bead_set — nothing to dispatch. Either rebuild the Package with `dekspec package build <intent-id> --bead-set bd-X,bd-Y,...` (when that flag lands per INT-031), or use `br ready` discovery instead by re-running without `--package`."

  Use `$PKG_IB_PATH` (if non-empty) instead of resolving the IB path per-bead in step 2(b) — every bead in a Package shares one IB by definition. The lifecycle DB writes (IC-004 compliance section) use `$PKG_INTENT_ID` as the bound Intent for the attempt row.

2. For each candidate bead:

  a. `br show <id>` — confirm unclaimed (no assignee, not `in_progress`)
   b. Read the bead's `external_ref` IB to identify target files
   c. Call `file_reservation_paths` (agent-mail MCP) with `exclusive=true` on those files
      - If agent-mail is unavailable or returns an error — STOP. Tell the engineer:
        "⚠️ agent-mail is unavailable — file reservations could not be acquired. Proceeding without locks risks concurrent file collisions. Continue anyway? (y/n)"
      - If engineer says no — stop the session entirely
      - If engineer says yes — skip reservations and proceed to step (e), noting in the dispatch plan that locks were not held
   d. **If conflicts** — skip this bead, move to the next candidate
   e. Claim it: `br update <id> --claim --actor orchestrator`
   f. If the IB is in `queued/`, move it to `active/` and update the bead's `external_ref`
3. Collect all successfully claimed beads into a dispatch list
4. If zero beads claimed, report and stop

Present the dispatch plan:

```
DISPATCH PLAN — [N] beads claimed:
  BEAD-1: [title] → [IB path] → [files]
  BEAD-2: [title] → [IB path] → [files]
  ...
```

If `--confirm-dispatch` is set, wait for engineer approval before proceeding. Otherwise, proceed to Phase 2 immediately.

## Phase 2 — Dispatch Sub-Agents

For each claimed bead, before dispatching, verify dependency merges are present:

- Check the bead's `dependencies` field. For each listed dependency:
  1. Run `git log --oneline --grep "bead <dep-id>"` to check if the dependency's commit is present in the current branch
  2. If found — dependency is merged, proceed
  3. If not found AND the dependency's worktree branch exists in this session — merge it now:
    ```bash
     git merge <dep-worktree-branch> --no-edit
    ```
  
     Re-check with git log. If still not found, stop and surface to the engineer.
  4. If not found AND no worktree branch exists for it — the dependency was never merged. STOP:
  
    "⚠️ bead [ID] depends on [dep-id] whose changes are not present in the current branch and no worktree branch exists to merge. Resolve this before dispatching."

Then dispatch a sub-agent using the Agent tool with `isolation: "worktree"`. Launch all agents in a **single message** so they run in parallel.

Each sub-agent prompt MUST include:

1. **The full bead JSON** (from `br show <id> --json`)
2. **The full IB content** (read and inline it — the sub-agent cannot access `br`)
3. **Eval file contents** if referenced in the IB
4. **Pre-written test file contents** if `tests/bead/test_<bead-slug>.py` exists (check before dispatch)
5. **Checklist contents** if referenced (e.g., `python-quality-checklist.md`, `security-checklist.md`)
6. **The workflow instructions** (copied verbatim from the Sub-Agent Workflow section below)
7. **Local dependency-source paths** if present — for any library/SDK/framework the bead implements against, check for vendored source under `reference/repos/<host>/<org>/<project>` (e.g. `reference/repos/github.com/pallets/flask`) and inline the path list so the sub-agent greps the real implementation instead of guessing APIs. This is **opt-in/best-effort**: if no `reference/repos/` tree exists, pass "None" and dispatch normally — its absence never blocks dispatch.

### Sub-Agent Prompt Template

```
You are implementing bead [ID]: [title]

## Bead
[full bead JSON]

## Implementation Brief
[full IB content]

## Evals
[eval file contents, or "None"]

## Checklists
[checklist contents, or "None"]

## Pre-Written Tests
[test file contents if tests/bead/test_<slug>.py exists, or "None — write tests during implementation"]

## Dependency Source
[reference/repos paths for libraries this bead uses, or "None"]

## Workflow

1. **Interface-first:** Write public interface signatures only — no implementation yet
2. **Source before guessing:** When you implement against a library/SDK/framework, search its real source before writing code — do NOT guess API names or signatures. If a path is listed under Dependency Source, grep it first; otherwise consult the official repo. If the API still can't be resolved from source, surface it as an expertise gap rather than guessing.
3. Implement the interfaces
4. **Tests:**
   - If pre-written tests exist: remove `@pytest.mark.skip` markers and run them — all must pass. Then write additional tests for behaviors discovered during implementation that aren't covered.
   - If no pre-written tests: write tests for all deterministic behavior.
5. Run evals if they exist
6. **Cleanup pass (best-effort, behavior-preserving):** With tests green, scan the files you changed for duplicated mechanics you introduced — repeated API calls, parsing, validation, or business logic. Extract them into a local reusable helper; keep domain policy in the calling route/action/component; keep the diff small. Re-run tests — they MUST still pass. If cleanup would require touching a file outside this bead's IB file list (e.g. a shared service module), do NOT do it — note it as a follow-up in your output. If any cleanup risks a behavior change, skip it and keep the working version.
7. Run `ubs` on all changed files — fix any findings
8. Commit all changes with message: "bead [ID]: [title]"

## Interrupt-Level Stop Patterns

These trigger at ANY point during the workflow. They are not sequential — they interrupt work immediately.

**When the IB doesn't cover something:**
EXPERTISE GAP — Bead: [ID] | Need: [question] | Blocks: [what]
STOPPED — awaiting engineer decision

**When bead/IB constraints conflict with each other or with existing code:**
CONFLICT — [describe the contradiction]. Cannot resolve from bead/IB alone.
STOPPED — awaiting engineer decision

## Rules

- Do NOT read ADRs, interface contracts, or the Working Spec — all decisions were reconciled into the IB
- If something is missing from the IB, surface it as an expertise gap
- Never guess domain constraints — surface and stop
- Never guess a third-party API name or signature — search the library's real source first (Dependency Source paths if listed, else its official repo)
- Stay within the files listed in the IB. Do not touch other files.
- If a function or type your bead depends on (from a dependency bead) is missing from the codebase, do NOT re-implement it. Surface immediately:
  DEPENDENCY MISSING — Bead: [ID] | Missing: [what is absent] | Blocks: [what you cannot do]
  STOPPED — awaiting orchestrator resolution

## Refactoring Checklist (conditional)

Applies only when the bead's domain includes `refactoring` or the IB is marked as a refactoring IB. Skip entirely for feature work or bug fixes.

Before finishing, verify:
- [ ] No behavior change — all existing tests pass without modification
- [ ] No new silent exception handling
- [ ] No new architectural boundary violations
- [ ] All moved functions retain their original signatures
- [ ] Import paths updated everywhere

## Output

When done, report:
STATUS: [COMPLETE | STOPPED]
BEAD: [ID]
FILES_CHANGED: [list]
TESTS: [pass/fail summary]
EVALS: [pass/fail/skipped]
CLEANUP: [extracted N local helpers | none needed | deferred: <cross-file follow-up>]
UBS: [clean/findings]
BLOCKERS: [none, or description]
```

## reference/repos/ convention (source-as-context)

A bead implements better against a library when it can grep the library's **real source** instead of guessing from docs. The convention: drop dependency source under

```
reference/repos/<host>/<org>/<project>
```

e.g. `reference/repos/github.com/pallets/flask`. Phase 2 checks for a matching tree per bead dependency and, when present, inlines the path into the sub-agent prompt's Dependency Source block. The tree is populated manually (clone/copy the dep source) — there is no auto-download. The convention is **opt-in and best-effort**: a session with no `reference/repos/` tree dispatches exactly as before.

## Phase 3 — Collect & Merge

As each sub-agent returns:

1. Parse its status report
2. If STOPPED — surface the blocker to the engineer immediately
3. If COMPLETE — merge the worktree branch into the current branch:
  ```bash
   git merge <worktree-branch> --no-edit
  ```

   If the merge has conflicts:
  - "Resolve automatically" means: conflicts in files not touched by other beads in this session can be resolved by accepting the incoming changes (`git checkout --theirs <file> && git add <file>`). Do NOT auto-resolve conflicts in files touched by multiple beads — surface those to the engineer.
  - If a conflict cannot be safely auto-resolved: run `git merge --abort`, unclaim the bead (`br update <id> --unclaim`), release its file reservations, and surface the conflict to the engineer before proceeding.
  - If ALL beads in the session have unresolvable conflicts: abort all merges, unclaim all beads, release all reservations, and stop. Do not proceed to Phase 4.

Once all agents have returned and merges are attempted, present a summary:

```
SESSION RESULTS — [N] beads dispatched:
  ✅ BEAD-1: [title] — merged
  ✅ BEAD-2: [title] — merged
  ⚠️  BEAD-3: [title] — merge conflict: [description]
  ❌ BEAD-4: [title] — STOPPED: [reason]
```

## Phase 4 — Land the Plane

For each completed and merged bead:

1. Close the bead: `br close <id>`
2. Release file reservations: call `release_file_reservations` (agent-mail MCP) for each held reservation. Skip this step if agent-mail was unavailable and reservations were not acquired.
3. If all beads for an IB are now closed, move the IB from `active/` to `completed/`

For each stopped or conflict bead:

1. Release file reservations
2. Unclaim: `br update <id> --unclaim`
3. File the blocker as a comment or follow-up bead

Finally:

1. Run the full test suite: `python3 -m pytest tests/ -q 2>&1 | tail -20`
  - If all tests pass — done.
  - If collection errors appear (e.g., `ModuleNotFoundError`) — automatically run the same command on a temporary worktree at the pre-session commit to determine if they are pre-existing:
    ```bash
    BASELINE_PATH="/tmp/baseline-check-$(date +%s)"
    git worktree add "$BASELINE_PATH" <pre-session-commit>
    cd "$BASELINE_PATH" && python3 -m pytest tests/ -q 2>&1 | tail -10
    git worktree remove --force "$BASELINE_PATH"
    ```
  - If baseline has the same errors — confirmed pre-existing, report clean.
  - If baseline is clean but HEAD has errors — regression introduced by this session. Stop, investigate, and do not proceed to SESSION COMPLETE until resolved.
2. For any out-of-scope discoveries noted by sub-agents, file follow-up beads:
  ```bash
   br create --title "[description of discovery]" --priority P2 --status open --type task \
     --labels "follow-up" --external-ref "<IB ref>"
  ```

   Add a note explaining what was discovered and why it is out of scope for this session.
3. Run `br sync`
4. Present the merged diff for engineer review:
  ```bash
   git diff <pre-session-commit>..HEAD --stat
  ```

```
LANDED — Session complete.
  Merged: [N] beads into [current branch]
  Stopped: [N] beads (see blockers above)
  Follow-ups filed: [list or "none"]

  Review the merged state with: git log --oneline <pre-session-commit>..HEAD
```

## Phase 5 — Check for Newly Unblocked Work

After landing, run `br ready` again. If new unblocked beads appear (previously blocked by beads just closed), present them to the engineer:

"These beads are now unblocked: [list]. Continue with another dispatch round? (y/n)"

If yes, return to Phase 1.
If no, proceed to SESSION COMPLETE.

**⛔ SESSION COMPLETE.**

## Directive Library

Ready-to-use phrases for the engineer during a session:

```
"Drop BEAD-X from the dispatch list."
"Only dispatch BEAD-X and BEAD-Y."
"That bead is out of scope. Unclaim it."
"Show me the blocker details for BEAD-X."
"Re-dispatch BEAD-X with this guidance: ..."
"Stop all agents. Land the plane now."
```

## Common Pitfalls

- Don't proceed past Pre-Flight when `preflight_quality_gates.py` exits 1 — STOP and report the `missing` list; a referenced checklist/test/eval file that doesn't exist on disk means the session cannot enforce the quality process the IB promises.
- Don't dispatch sub-agents in separate messages — launch every Agent call in a **single message** so they run in parallel worktrees; serial dispatch defeats the entire purpose of this skill.
- Don't let a sub-agent read ADRs, ICs, or the Working Spec — all decisions were reconciled into the IB. Inline the full IB (plus evals, tests, checklists) into the prompt; the sub-agent has no `br` access and must not re-derive contracts.
- Don't auto-resolve merge conflicts in files touched by more than one bead in this session — surface those to the engineer. Only accept-theirs on files no other dispatched bead claims.
- Don't reach SESSION COMPLETE on a pytest collection error without running the pre-session-commit baseline check — confirm the failure is pre-existing, not a regression this session introduced, before declaring clean.
- Don't skip the lifecycle DB writes — every attempt must `record-attempt` (Phase 1) and `complete` (Phase 4); a session that merges beads but leaves the IC-004 attempt row open silently corrupts first-pass-rate and time-to-merge metrics.
- Don't close beads or skip the epilogue when an outer session was deferred to — only close the session this skill opened (`OUTER_SESSION_PRESENT=0`), and always run `dekspec session report` first to surface off-spec drift.

## Verification Checklist

- [ ] Pre-Flight `preflight_quality_gates.py` exited 0 (or the session was stopped) — no missing quality files were dispatched against.
- [ ] `PRE_SESSION_COMMIT` was captured before Phase 1 and used in the Phase 4 baseline/diff steps.
- [ ] Every claimed bead was either merged + closed, or unclaimed with its file reservations released and a blocker recorded — no bead left claimed-but-abandoned.
- [ ] Every dispatched Intent's attempt was completed via `dekspec executions complete` with the correct `--ci-status` (and `--escalation` when any bead stopped/conflicted).
- [ ] All held agent-mail file reservations were released (or the session ran with reservations explicitly skipped and noted in the plan).
- [ ] The full `pytest tests/ -q` run is green, or any failure was confirmed pre-existing against the pre-session-commit baseline.
- [ ] `dekspec session report` ran at the epilogue, and the session this skill opened was closed (skipped only when deferring to an outer session).
- [ ] Phase 5 ran `br ready` again and either dispatched another round or reached the **⛔ SESSION COMPLETE** terminal state.

