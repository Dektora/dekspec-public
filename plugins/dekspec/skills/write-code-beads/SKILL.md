---
name: write-code-beads
description: Convert an Implementation Brief into beads (atomic work units). Use after an IB has been finalized and approved.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--audit | --rebuild | --help] [path to IB or BEAD-NNN or "all"]
related_skills: [write-ibs, write-tests, exec-coding-session, write-intent]
---

Convert an Implementation Brief into beads.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill decomposes an IB into self-contained bead work units. Prior conversation context can leak assumptions into bead constraints that aren't in the IB.
>
> First message → proceed. Prior history → ask "context may affect bead decomposition quality, recommend /clear, continue? (y/n)" + wait.

## Starter Prompt

```prompt
/dekspec:write-code-beads dekspec/impl-briefs/IB-014-graph-injection-brief.md

This IB was just accepted via /write-ibs --accept. Decompose it into open beads
(one bead = one session = one PR), run the fidelity audit, wire up the blocks
dependencies, and br sync.
```

## Mode Detection

Parse `$ARGUMENTS` for flags. If `--help` is present, skip to **Help Mode**. If `--audit` is present, strip it and skip to **Audit Mode**. If `--rebuild` is present, strip it and skip to **Rebuild Mode**. Otherwise, proceed with **Creation Mode** below.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-code-beads"
one_line:   "Create, audit, or rebuild beads from Implementation Briefs"
modes:
  - { flag: "", args: "<IB-path>", description: "Create beads from an approved IB. Runs fidelity audit automatically before writing beads." }
  - { flag: "--audit", args: "<BEAD-NNN|\"all\">", description: "Re-audit existing beads against their IB. Checks that bead content still matches the IB faithfully. Read-only — reports findings without changes." }
  - { flag: "--rebuild", args: "<IB-path>", description: "Delete all open beads for this IB and re-create them from scratch. Guards against in_progress or closed beads — those require engineer decision." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-code-beads dekspec/impl-briefs/IB-001-component-brief.md"
  - "/write-code-beads --audit BEAD-42"
  - "/write-code-beads --audit all"
  - "/write-code-beads --rebuild dekspec/impl-briefs/IB-001-component-brief.md"
  - "/write-code-beads --help"
extra_sections:
  - heading: "WORKFLOW"
    body:
      - "1. Accept IB:     /write-ibs --accept <IB>"
      - "2. Create beads:  /write-code-beads <IB>"
      - "3. Audit beads:   /write-code-beads --audit <bead-id>  (after IB changes or spot checks)"
      - "4. Rebuild beads: /write-code-beads --rebuild <IB>     (after IB resync or revision)"
      - "5. Code:          /exec-coding-session"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Audit Mode

Re-audit existing beads for fidelity against their IB. Use for spot checks, after IB revisions, or when an IB has been resynced.

### Input

Bead ID(s): the argument after `--audit`. Accepts `BEAD-NNN`, multiple space-separated bead IDs, or `all`.

### Workflow

1. Read the bead(s) from `.beads/beads.jsonl` (via `br show <id> --json`)
2. If any bead is `in_progress` or `closed` — flag as process violation, do not audit, escalate to engineer
3. Read the referenced IB from each bead's `external_ref`. To enumerate which beads belong to an IB (when `--audit` was passed an IB rather than bead IDs), run `scripts/find_beads_for_ib.py <IB>` — it returns JSON `{ib, by_status, total, source}`. Surface stderr on non-zero exit. Audit every bead it lists.

### Audit Checklist

For each bead, verify:

- [ ] **Constraints and Decisions faithful** — bead's `--description` Constraints and Decisions section matches the IB's Constraints & Decisions entries. Not summarized, not paraphrased, not missing entries.
- [ ] **Domain constraints complete** — every constraint field has a value; no "n/a" where the IB specifies a concrete value
- [ ] **Governing ADRs listed** — every ADR referenced in the IB appears in the bead's `--design` Governing ADRs
- [ ] **Evals matched** — if the bead produces model output, eval references exist with `name`, `tests`, `pass_criterion`, and `run`; if deterministic-only, evals may be empty
- [ ] **Acceptance criteria complete** — bead's `--acceptance-criteria` matches the IB's Done When checklist completely, each with verification type
- [ ] **Files correct** — every file in the bead's `--description` Files list exists in the repo and matches what the IB specifies
- [ ] **Interface contracts listed** — if the IB references contracts, the bead's `--design` lists them
- [ ] **Goal is single sentence** — states the observable outcome, not a summary of the IB
- [ ] **Out of Scope populated** — at least one boundary listed in `--design`
- [ ] **Do Not Touch populated** — populated or explicitly states "None — [reason]"
- [ ] **External ref set** — `external_ref` resolves to the IB (bare path for a lone bead; `IB-NNN:<unit-slug>` for each bead of a multi-bead set, so siblings don't collide)

### Output

```
AUDIT RESULTS:
  ✅ BEAD-42: [title] — all checks pass
  ❌ BEAD-43: [title] — 2 failures:
     - Constraints and Decisions: missing entry for [topic]
     - Domain constraints: cuda_device is n/a but IB specifies cuda:0
  ✅ BEAD-44: [title] — all checks pass
```

Report ALL failures across all audited beads before corrections. Engineer batches fixes.

**End of Audit Mode — do not continue to creation workflow.**

## Rebuild Mode

Delete all open beads for an IB and re-create them from scratch. Use after an IB has been resynced or revised.

### Input

IB path: the argument after `--rebuild`.

### Steps

1. Read the IB
2. Run `scripts/ib_status_check.py <IB>` — it returns JSON `{status, path_kind, path}`. Surface stderr on non-zero exit. If `status` is not `ACCEPTED`, STOP: "This IB has not been re-accepted after changes. Run `/write-ibs --accept` first."
3. Run `scripts/find_beads_for_ib.py <IB>` — it returns JSON `{ib, by_status, total, source}` listing every bead whose `external_ref` matches this IB, grouped by status. Surface stderr on non-zero exit.
4. Read `by_status` from the script output:
  - **open** — safe to delete
  - **in_progress** — STOP: "Bead [ID] is in progress. Cannot rebuild while coding is active. Close or unclaim it first, then re-run."
  - **closed** — STOP: "Bead [ID] is closed (work completed). Rebuilding would discard completed work. Create correction beads instead, or confirm you want to discard with: 'yes, delete closed beads'."
5. Present the deletion plan:
  ```
   REBUILD PLAN for [IB path]:
     Delete: [N] open beads ([list IDs])
     Then: re-create beads from current IB content
  
   Proceed? (y/n)
  ```
6. Wait for engineer confirmation.
7. Delete all open beads: `br delete <bead-ids>`
8. Run `br sync`
9. Proceed to Creation Mode workflow (skip the Safety Check — rebuild already validated)

**End of Rebuild Mode.**

## Creation Mode

### Input

IB path: $ARGUMENTS

If no path is provided, list all `.md` files in `dekspec/impl-briefs/` and ask the engineer to select one. (IBs live FLAT in `dekspec/impl-briefs/` — there are no `queued/` / `active/` / `completed/` subdirectories in current repos.)

### Safety Check

Before proceeding:

- Run `scripts/ib_status_check.py <IB path>` — it returns JSON `{status, path_kind, path}`. Surface stderr on non-zero exit. If `status` is not `ACCEPTED` — STOP. Do not proceed. Tell the engineer: "This IB has not been accepted. Run `/write-ibs --accept <path>` before running /write-code-beads."
- If `path_kind` is `active` — warn: "This IB is currently in an active coding session. Continue or abort?"
- If `path_kind` is `completed` — warn: "This IB has already been completed. Creating new beads for it is unusual. Continue or abort?"
- Run `scripts/find_beads_for_ib.py <IB path>` — it returns JSON `{ib, by_status, total, source}`. Surface stderr on non-zero exit. If `by_status.open` is non-empty — warn: "Open beads already exist for this IB. Continuing will create duplicates. Continue or abort?"

Wait for engineer confirmation before proceeding.

### Workflow

1. Read the Planning Agent role from `dekspec/project-context.md` — for role instructions only, not bead content
2. Read the IB from the provided path — the ONLY source of bead content
3. Do NOT read any other document for content: not ADRs, not interface contracts. Everything needed for the beads is in the IB.
4. **Process violation check:** Run `scripts/find_beads_for_ib.py <IB path>`. Surface stderr on non-zero exit. If `by_status` contains any `in_progress` or `closed` bead — STOP. Coding has already started. Do not delete, do not create new beads. Escalate to the engineer.
5. Decompose the IB into beads — one bead = one session = one PR

### Bead Format

The bead is the ONLY document the coding agent reads. It must be fully self-contained. Every field below must be populated from the IB — do not leave placeholders or reference external files as a substitute for content.

Beads are created using `br` CLI commands, NOT by writing raw JSONL. The bead content is distributed across `br`'s native fields using structured markdown so that `br ready`, `br show`, `br list`, etc. all work correctly.

### Field mapping

`**br create` flags:**


| Bead concept | `br` flag        | Format                                  |
| ------------ | ---------------- | --------------------------------------- |
| Title        | `--title`        | `[verb + component + outcome]`          |
| Priority     | `--priority`     | `P0` through `P3`                       |
| Status       | `--status`       | `open`                                  |
| Domain tags  | `--labels`       | Comma-separated: `injection,cuda,graph` |
| IB reference | `--external-ref` | `IB-NNN-[component]-brief.md` (one bead) · `IB-NNN:<unit-slug>` (multi-bead) |
| Type         | `--type`         | `task`                                  |

> **One IB → many beads: disambiguate the `external_ref`.** `br` rejects a
> `--external-ref` value it has already seen, so a literal IB path collides on the
> *second* bead of a multi-bead decomposition (`br create` fails). Give each
> sibling bead a unique ref with the `:<unit-slug>` qualifier — `IB-027:schema`,
> `IB-027:parser`, `IB-027:cli` — never a bare repeated `IB-027-…-brief.md`. The
> qualifier is cosmetic to grouping: `find_beads_for_ib.py` matches on the
> `IB-NNN` token and ignores the `:slice`, so all three still resolve to IB-027.
> A single-bead IB can use the bare path; only multi-bead sets need the suffix.


`**br update` fields (structured markdown):**

`**--description**` — the primary bead content the coding agent uses:

```markdown
## Goal
[one sentence: what the system can do after this bead is complete that it cannot do now]

## Files
- `exact/path/to/file.py`
- `exact/path/to/other.py`

## Constraints and Decisions
- **[topic]:** [what to do — concrete rule, not a reference to a document]
- **[topic]:** [what to do]

## Domain Constraints
- **cuda_device:** cuda:0 | cuda:1-7 | cpu | n/a
- **tensor_dtype_in:** bfloat16 | float32 | n/a
- **tensor_dtype_out:** bfloat16 | float32 | n/a
- **read_path:** shadow | neo4j | n/a
- **write_path:** shadow+buffered | neo4j_direct | n/a
- **precision_threshold:** max error <= X at each bit depth | n/a

## Escalation
Stop and ask the engineer when: (1) any decision requires information not in this bead, (2) a file not listed in Files needs to change, (3) a Done When criterion requires touching something out of scope, (4) the behavior described contradicts what the code currently does in a way not described here. Do NOT assume and proceed. Exception: quality checklists referenced in the IB (e.g., python-quality-checklist.md, security-checklist.md) may be read as operational guidance.
```

#### Optional body lines — failure_class + failure_notes (Phase 1.B / ds-d0as)

When a bead is being created in response to an observed failure (post-mortem context, regression triage, audit follow-up), append two leading-line fields to the description body **above** the structured sections:

```markdown
failure_class: <one of the recommended values>
failure_notes: <free-form prose context>

## Goal
...
```

`failure_class` is an **open-enum** classifier — schema-free; the audit rule `T-BEAD-FAILURE-CLASS-VALID` emits a `P3` advisory for unrecognized values without rejecting. Recommended vocabulary:

| Value                          | When to use                                                                                              |
| ------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `wrong-spec`                   | Spec was complete + reviewed but the implemented behavior reflected what the spec said, not what was needed. |
| `correlated-AI-miss`           | Multiple AI passes converged on the same wrong answer; spec was unclear in a way humans + AI both missed. |
| `production-only-failure`      | Test suite was green; failure only surfaced under production load / state / inputs.                      |
| `flaky-test-masked-bug`        | A flaky test was suppressed or accepted; the real failure was riding the flake.                          |
| `scope-creep-undetected`       | Diff exceeded its Components-affected envelope without TESTFAIL surfacing it (audit-v2 L7b miss).        |
| `dependency-version-conflict`  | Wheel / lockfile / pinned dep produced the failure; root cause is supply-chain, not author code.         |
| `concurrency-race`             | Race condition / ordering bug / lock leak; deterministic reproduction is non-trivial.                    |
| `other`                        | Falls outside the listed values. Use sparingly + populate `failure_notes:` to explain.                   |

`failure_notes` is free-form text — no audit constraint. Use for context the bead body's structured sections don't capture (e.g., what the failure looked like before remediation, which incident timeline it ties to, which monitoring signal first caught it).

**Both lines are convention-only — there is no beads-rust schema change.** The canonical extractor is `tooling/dekspec/fidelity_audit/bead_body.py::parse_bead_failure_class`. Leave both unset for forward-looking work beads (no failure to classify); their presence carries failure-context observability, not a structural requirement.

The two lines compose with the Intent IR `risk_tier` field (also Phase 1.B): `risk_tier` flags blast radius *before* work begins; `failure_class` captures failure mode *after* work resolves a failure.

`**--design**` — guardrails and traceability:

```markdown
## Do Not Touch
- `function_name` — reason
(or: None — [explain why nothing is off-limits])

## Out of Scope
- [what this bead does NOT do — boundary that a reasonable engineer might assume is included]

## Governing ADRs
- ADR-NNN — traceability only, do not read; decisions are in Constraints and Decisions

## Interface Contracts
- dekspec/interface-contracts/IC-NNN-[slug].md — traceability only, do not read; constraints are in Constraints and Decisions
```

`**--acceptance-criteria**` — done-when checklist and evals:

```markdown
## Acceptance Criteria
- [ ] [specific criterion] — verified by [unit test | integration test | manual check | eval]
- [ ] All new tests written for this bead pass — verified by test run
- [ ] All pre-existing tests continue to pass — verified by full suite run
- [ ] **outcome test landed first (red), implementation made it green, no other test files modified to make it pass** — strong-TDD discipline per ADR-029 (LOCKED 2026-05-29); verified by git-blame on the outcome-test file's first commit vs the implementation files' first commits

## Evals
- **eval_name:** [what behavior it validates] — pass: ≥ N% of cases — run: `[command or invocation]`
```

**Dependencies** — added after creation via `br dep add`:

```bash
br dep add <this-bead-id> <dependency-id> --type blocks
```

### Creation sequence

The AI's job is to **author the bead content** (Goal, Files, Constraints and Decisions, etc. — all from the IB). The mechanical `br create` + `br update` + `br dep add` plumbing is handled by `scripts/emit_bead.py`.

For each bead, assemble a JSON bead spec and pass it to the script:

```json
{
  "title": "[verb + component + outcome]",
  "priority": "P1",
  "type": "task",
  "status": "open",
  "labels": ["injection", "cuda"],
  "external_ref": "IB-NNN-[component]-brief.md",   // multi-bead set: use "IB-NNN:<unit-slug>" so siblings don't collide
  "description": "## Goal\n...\n\n## Files\n...\n\n## Constraints and Decisions\n...\n\n## Domain Constraints\n...\n\n## Escalation\n...",
  "design": "## Do Not Touch\n...\n\n## Out of Scope\n...\n\n## Governing ADRs\n...\n\n## Interface Contracts\n...",
  "acceptance_criteria": "## Acceptance Criteria\n...\n\n## Evals\n...",
  "dependencies": [{"id": "BEAD-OTHER", "type": "blocks"}]
}
```

Run `scripts/emit_bead.py --file <spec.json>` (or pipe the JSON on stdin). The script runs `br create`, the three `br update` calls, and any `br dep add` calls, then prints JSON `{bead_id, updates_applied, dependencies_added}`. Surface stderr on non-zero exit. Use `--dry-run` first to inspect the assembled `br` argv plan without mutating the tracker.

### Fidelity Audit (automatic — cannot be skipped)

Runs before any bead is written to the queue:

- [ ] `--description` Constraints and Decisions section is populated from the IB's Constraints & Decisions section — not from Spec Context
- [ ] Constraints and Decisions entries use the canonical format: `**[topic]:** [concrete rule]` — no document references
- [ ] Interface contract constraints are embedded in Constraints and Decisions (not only referenced by path)
- [ ] Goal is a single sentence stating the observable outcome after this bead is complete
- [ ] `--design` Out of Scope lists at least one boundary — not empty
- [ ] `--design` Do Not Touch is populated or explicitly states "None — [reason]"
- [ ] Domain Constraints are complete (no "n/a" where the IB specifies a value)
- [ ] Governing ADRs are listed with "traceability only" label
- [ ] Evals in `--acceptance-criteria` have `name`, `tests`, `pass_criterion`, and `run` — not bare strings
- [ ] Evals are matched (beads with model output have eval entries)
- [ ] Acceptance criteria include verification type for each item
- [ ] Acceptance criteria are complete (match IB's Done When checklist)
- [ ] Files listed in `--description` are correct (exist in repo, match IB)
- [ ] `--external-ref` is set to the IB (bare path for a lone bead; `IB-NNN:<unit-slug>` per bead for a multi-bead set)

Report all failures across all beads before corrections. Engineer batches fixes.

6. After audit passes, create each bead by running `scripts/emit_bead.py` as described in the Creation sequence above. Run `br sync` after all beads are created.

### Re-running After an IB Fix

An IB change is a start-over:

```bash
br delete BEAD-ID BEAD-ID    # delete ALL beads for this IB
br sync
# Fix the IB, then re-run /write-code-beads
```

### Output

Beads created in `br` database and synced to `.beads/beads.jsonl` via `br sync`.

## Common Pitfalls

- Don't pull bead content from prior conversation, ADRs, or interface contracts — author every field from the IB alone; those documents are traceability references, not content sources.
- Don't summarize or paraphrase the IB's Constraints & Decisions into the bead — copy them verbatim into Constraints and Decisions as `**[topic]:** [concrete rule]`; embed IC constraints inline rather than linking the path.
- Don't proceed when `scripts/find_beads_for_ib.py` reports any `in_progress` or `closed` bead — STOP and escalate; coding has started and creating/deleting beads would destroy or duplicate active work.
- Don't run Creation Mode against an IB whose `ib_status_check.py` status is not `ACCEPTED` — route the engineer to `/write-ibs --accept` first.
- Don't write a multi-clause Goal or fold several PRs into one bead — one bead = one session = one PR, and the Goal is a single sentence naming the new observable capability.
- Don't hand-run `br create`/`br update`/`br dep add` — assemble the JSON spec and run `scripts/emit_bead.py` (with `--dry-run` first) so the plumbing stays consistent.

## Verification Checklist

- [ ] Mode was correctly detected from `$ARGUMENTS` (Creation / `--audit` / `--rebuild` / `--help`).
- [ ] `ib_status_check.py` returned `ACCEPTED` (or Rebuild Mode validated it) before any bead was written.
- [ ] `find_beads_for_ib.py` was run and showed no `in_progress`/`closed` beads (otherwise the run was STOPPED and escalated).
- [ ] The full Fidelity Audit checklist ran and every item passed before any bead was emitted.
- [ ] Each bead is single-PR scoped with a one-sentence Goal, and all fields are populated from the IB (no placeholders, no external-file substitutes).
- [ ] Every bead's `--external-ref` resolves to the IB — bare path for a lone bead, `IB-NNN:<unit-slug>` per bead for a multi-bead set (siblings must not share an identical ref or `br create` rejects the duplicate).
- [ ] Beads were created via `scripts/emit_bead.py`, dependencies wired with `br dep add`, and `br sync` was run.