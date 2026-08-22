---
name: prj-mgr
description: "Use to view, track, or sync br-backed project boards — the issue-side pull surface answering \"what should I pick up next?\". Trigger when the engineer wants to see project status, list the active boards, check a project's phase or completion, or refresh a board snapshot from the tracker. Phrases like \"where are we on X\", \"show the project boards\", \"what's the status of the l5o board\", or \"resync the boards\" all apply. Also handles INGEST: turning a markdown file, a report, or a chunk of pasted text into board-shaped issue beads — \"ingest this file\", \"add these findings to the backlog\", \"turn this roadmap into a project\". A bare file path or several words with no flag is treated as an ingest. This is the ISSUE-side counterpart to `br ready`, which is reserved for the next ready CODE bead (ADR-052). Runs standalone with no DekSpec installed."
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Bash Grep Glob
argument-hint: "[<file|text> | --ls | --status [<project>] | --sync [<project>] | --items [<project>] | --ingest <file|text> [--into <project> | --new-project [name]] | --adopt <bead-id>... --into <bead-id> | --bootstrap | --where | --help]"
related_skills: [write-issue-beads]
---

## What this is

`prj-mgr` renders **project boards** over a `br` tracker. Boards live under
`docs/prj-mgr/<state>/<project>/` and are backed by issue beads.

**It is the issue-side pull surface.** Per **ADR-052**, bare `br ready` is
reserved for the next ready *code* bead — the coding agent's queue. The
corresponding question for issues (*what should a human pick up next?*) is a
project-board question, and this tool answers it.

**It is one consumer, not the owner.** The issue tracker is a shared capability
with a documented resolution path (below); any other tool or agent may use it
without going through `prj-mgr`.

## Dependency tier: `dekspec-enhanced` (ADR-047)

This tool has **zero hard coupling to DekSpec**. It uses only the Python
standard library, shells out to `br`, and reads the board tree. It runs fully
in a repo with no DekSpec engine, no DekSpec plugin, and no marketplace entry —
that is a tested property, not a claim (`test_tool_sources_import_nothing_from_dekspec`).

When DekSpec *is* present it may enrich output (cross-referencing the spec
artifacts behind a board's beads). Enrichment is strictly additive: **no
baseline feature may depend on it**, and the standalone path is first-class,
never a degraded fallback.

## Modes

| Mode | Flag | What it does |
|---|---|---|
| List | `--ls` (default) | Render the active project registry — alias, name, current phase, status, completion, last activity. |
| Status | `--status [<project>]` | Show one board's phase detail, or all boards when no project is named. |
| Sync | `--sync [<project>]` | Regenerate board snapshots from `br`. Writes; run it when the tracker has moved on. |
| Items | `--items [<project>]` | Print each **bead in full** — body, acceptance criteria, labels, edges — grouped by phase. `--compact` for one line per bead. Read-only. |
| Ingest | `--ingest <file\|text>` | Turn a document or a chunk of text into board-shaped beads. Proposes, then writes only on approval. See **Ingest** below. |
| Adopt | `--adopt <ids> --into <id>` | Wire existing beads under a parent. No judgement — the deterministic half of ingest, on its own. |
| Bootstrap | `--bootstrap` | Create the three `br` workspaces in a repo that has none. See below. |
| Where | `--where` | Print the resolved bead workspaces as JSON — the discoverability surface. |
| Help | `--help` | Usage. |

A bare argument with no flag is classified rather than rejected — a board name
means `--status`, a file or several words means `--ingest`. See **Mode
Detection**.

Run via the scripts in [`scripts/`](scripts/):

```bash
python scripts/prj_mgr.py [--ls | --status [<project>] | --sync [<project>]]
python scripts/prj_mgr_items.py <project> [--open] [--ready] [--phase N] [--priority-max N] [--compact]
python scripts/prj_mgr.py --where            # routed
python scripts/prj_mgr.py --bootstrap        # routed
python scripts/ingest_plan.py context|review|apply|adopt   # the ingest engine
```

> **Fixed 2026-08-20.** `--bootstrap` and `--where` were documented here but
> rejected by `prj_mgr.py`, which matched exact argv shapes; so was
> `--status <project>` in the flag-first order this file uses as its own
> example. Flags and positionals are now separated before dispatch, so either
> order works. Separately, `_project_alias` computed initials-based aliases
> that `_project_dir` could not resolve, because one read `_project_alias` and
> the other re-parsed the README. Both now go through `_project_alias`.

## Workspace resolution (ADR-052 §4) — never hardcode a path

Three layers, each usable alone, tried in order. `prj-mgr` gets no privileged
access; any tool follows the same path.

1. **Convention** — `.beads-issues/` (issues) and `.beads-dekspec/` (DekSpec
   work) as siblings of `.beads/` (code beads) at the repo root. Needs nothing
   installed but `br`.
2. **Declaration** — `.dekspec/config.yaml` may name workspace locations under
   `issue_tracker`, for repos that place them elsewhere.
3. **Resolution verb** — `dekspec beads workspaces --json`, when the engine is
   on PATH. Ergonomic, never required.

`--where` prints what resolved and *how* (`convention` / `declaration` /
`verb` / `fallback`), so a misconfigured repo is diagnosable in one command.

**Pre-migration repos still work.** Until a repo is split, all kinds share the
single root workspace; resolution reports `fallback` rather than "no tracker".

## Bootstrap modes

`prj-mgr --bootstrap` provisions the `br` workspaces in one of two layouts.

| | Layout | Use when |
|---|---|---|
| **Independent** *(default)* | `.beads/` `iss-` only | the repo tracks issues and nothing else |
| **DekSpec** `--dekspec` | `.beads/` `cb-` code · `.beads-issues/` `iss-` · `.beads-dekspec/` `ds-` | DekSpec is in play, or a coding agent will run bare `br ready` and must get coding tasks |

Independent mode drops the whole "never run a bare mutating `br` command" discipline —
there is one store, so every `br` command works bare with no `--db`. That is the point.
The trade is that bare `br ready` returns **issues**, so if a coding agent ever runs it
here, it gets issues rather than coding tasks.

**The two are not a subset of one another** — they disagree about what lives at the root.
Switching later is a real migration (export JSONL, re-init the root, import into the
sibling), so conflict handling depends on whether a mode was *asked for*:

- **No flag, root already the other layout** → reports the layout that exists and exits 0.
  Bare `--bootstrap` in an established repo is a no-op, not an error.
- **`--dekspec` or `--independent` given, and it conflicts** → **refuses**, and prints the
  migration steps.

Choose deliberately: if a coding agent will ever run `br ready` in this repo, take DekSpec
mode now even if DekSpec is never installed — the `ds-` workspace costs nothing empty, and
the root stays free for code beads.

## Setting up `br` with no DekSpec and no prj-mgr

Each layout is a convention, so it needs no tooling at all.

Independent — one store, issues only, the default:

```bash
br init --prefix iss && br config set min_hash_length 5
```

DekSpec — three stores:

```bash
br init --prefix cb && br config set min_hash_length 5
mkdir -p .beads-issues  && (cd .beads-issues  && br init --prefix iss && br config set min_hash_length 5)
mkdir -p .beads-dekspec && (cd .beads-dekspec && br init --prefix ds  && br config set min_hash_length 5)
```

`--bootstrap` runs exactly that, idempotently. In DekSpec mode the root workspace holds
**code** beads so bare `br ready` auto-discovers the coding queue with no flag; in
independent mode the root holds the issues themselves, so bare `br ready` is your backlog.

`min_hash_length 5`: at the default of 3, `br`'s random alphanumeric suffix
will occasionally mint IDs containing slurs. Bead IDs land in commit messages,
branch names, and PR titles.

## Bead kinds (ADR-052)

| Prefix | Kind | Workspace | Surface |
|---|---|---|---|
| `cb-` | code beads — executor input | `.beads/` | bare `br ready` |
| `iss-` | the repo's own product tracking | `.beads-issues/` | this tool |
| `ds-` | DekSpec governance work | `.beads-dekspec/` | this tool + DekSpec skills |

Prefixes are disjoint, so **a bead ID is globally unique** — a cross-workspace
reference is just the ID, with no qualifier.

## Scope: two backlogs, never the third

`prj-mgr` manages **both** project-managed backlogs:

- **generic product issues** (`iss-`, `.beads-issues/`)
- **DekSpec governance work** (`ds-`, `.beads-dekspec/`)

A board may mix them; ids are routed to the workspace whose prefix they carry.

**Code beads (`cb-`) are out of scope entirely — not read, not rendered, not
synced.** They are executor input pulled by the coding agent via bare
`br ready`; they are not project-managed work and never appear on a board.
This is structural, not advisory: `pm_workspaces()` returns only the two PM
kinds, `assert_not_code()` refuses a code workspace, and `_run_br_show()`
raises on any `cb-` id rather than resolving it.

## Ingest — turning a document into board-shaped beads

Ingest is the one mode whose hard part is **judgement**: deciding what the work
items are. The wrapper does not attempt it. It resolves the source and target,
prints the facts a decomposition has to respect, and hands off to you. Every
step after that is back in script hands, so a mistake is a rejected plan rather
than a polluted tracker.

Run the steps in order. **Nothing is written until step 8.**

1. **Get the facts.** `prj-mgr --ingest <src> [--into <project> | --new-project [name]]`
   prints an `INGEST REQUEST` header followed by `ingest_plan.py context` JSON:
   every board with its phase ids, every open bead (for duplicate judging), and
   the conventions a plan must satisfy.
2. **Read the source.** A file path arrives already absolute. Text arrives inline.
3. **Decompose into vertical slices** — each independently grabbable, each
   delivering observable value on its own. This is exactly stage 2 of
   `write-issue-beads`; follow it rather than inventing a second policy. Tag
   each slice `hitl` or `afk` (its stage 3) and apply its product gate (stage 5):
   anything product-related *and* substantial should become an Intent, not a bead.
4. **Judge duplicates against `context.open_beads`.** This is the step that
   decides whether ingest improves the backlog or inflates it. A finding that
   restates, confirms, or corrects work already tracked belongs in `comments`,
   not `items`. Err toward commenting: a comment on the right bead is always
   recoverable, a duplicate bead splits the history of one problem in two.
5. **Choose the parent for every item.** For an existing board, a phase id from
   `context`. For a new board, a phase `key` you define. Never leave an item
   parentless — a bead with no `parent-child` edge to the epic is invisible to
   the board renderer no matter how well written it is.
6. **Write the plan** to `docs/prj-mgr/<state>/<project>/.scratch/ingest-<date>.json`
   (or `docs/prj-mgr/.scratch/` when the board does not exist yet). Gitignored.
7. **Review:** `python3 scripts/ingest_plan.py review <plan>`. Read-only. It
   validates against the live tracker and renders the summary. **Show that
   summary to the engineer** — do not paraphrase it and do not show them the
   JSON. For a **new board** ask at most two things: accept or rename the
   project, and accept or restructure the phases. For an **existing board**
   there is usually nothing to ask beyond approval, since the name and phases
   already exist. Fix and re-review until it validates.
8. **Apply:** `python3 scripts/ingest_plan.py apply <plan>`, then
   `python3 scripts/prj_mgr.py <project> --sync`. Apply is resumable: every
   created id is recorded back into the plan, so re-running it after a failure
   continues rather than duplicating.

### The plan file

```json
{
  "version": 1,
  "source": "docs/some-report.md",
  "author": "prj-mgr-ingest",
  "target": {
    "mode": "existing",              // or "new"
    "project": "spec-engine-audit-hardening",  // existing: name or alias
    "project_name": "Instruction-File Projection", // new: becomes the epic title
    "alias": "ifp",                            // new, optional
    "scope": "One paragraph. Becomes the epic body."
  },
  "phases": [                        // new boards only; [] when attaching
    {"key": "p1", "title": "Emit the host instruction files"}
  ],
  "items": [
    {"key": "i1",
     "title": "Emit AGENTS.md from the compiled IR",
     "type": "task",                 // task|bug|feature|epic|chore|issue
     "priority": 0,                  // 0-4
     "labels": ["hitl", "skills"],
     "parent": "p1",                 // a phase key, or an existing bead id
     "blocks": ["i3"],               // "this item blocks i3" -- i3 waits for it
     "related": ["iss-other-bead"],
     "body": "## Problem\n…\n\n## Acceptance Criteria\n- …"}
  ],
  "comments": [
    {"bead": "iss-existing-bead", "reason": "one line for the summary",
     "body": "The full comment text."}
  ]
}
```

`review` rejects a plan rather than letting a bad bead land. It enforces:

| Rule | Why |
|---|---|
| Phase titles normalized to `Phase <N>: <title>` | `sync_project_snapshot._phase_number` matches nothing else, so a differently-titled phase is not a phase |
| Required headings **by type** (below) | `br lint` reads the *description*; the `acceptance_criteria` field does not satisfy it |
| Every `parent`, `blocks`, `related` and `comments[].bead` referent exists | a dangling edge cannot be created, and silently skipping it leaves a hole in the tree |
| Unique `key` per phase and item | keys are how `blocks` and `parent` reference not-yet-created beads |
| `priority` an int 0–4, `type` in the valid set | `br` rejects the rest at create time |

**`blocks` direction.** `blocks: ["X"]` means *this item must be done before X*.
`br dep add A B` records the opposite relation — "A depends on B" — so the engine
swaps the arguments when wiring a `blocks` edge. Getting this backwards is silent:
the edge exists, the graph stays acyclic, and `br ready` just gates the wrong bead.
Check the result with `br dep tree` or by confirming the blocker shows as ready and
the blocked item does not.

### Required headings, by type

Probed against `br` 0.3.2 — the template is **not** the same for every type.

| Type | Description must contain |
|---|---|
| `epic` | `## Success Criteria` |
| `bug` | `## Steps to Reproduce` **and** `## Acceptance Criteria` |
| `task`, `feature` | `## Acceptance Criteria` |
| `chore`, `issue` | nothing required |

An epic carrying `## Acceptance Criteria` still fails lint. Get this right in
the plan; `review` will catch it, but only after a round trip.

### Ids are flat and slugged, never dotted

`ingest_plan.py` creates beads **without** `br create --parent` and wires
parentage as a separate edge. Passing `--parent` makes `br` mint a dotted child
id (`iss-epic-abc.1.2`) and ignore `--slug`, which bakes the parent into the id —
so the id lies the moment an item is re-parented, and it looks nothing like the
flat slugged ids already on this repo's boards.

## Items — the per-bead view

`--ls` and `--status` answer at **board** granularity: which phase is active,
how many beads are open, what is blocking. Neither shows the items you would
pick up, and `br` cannot fill the gap — `br list` has no `--parent` filter, and
`br dep tree` walks `blocks` rather than `parent-child`, so rooting it at an
epic returns just the epic. `--items` walks the same `parent-child` tree the
snapshot renderer uses and prints it.

**The default is the whole bead, not a line about it.** Title, id, type,
priority, labels, status, last-updated, the ids on both ends of every open
`blocks` edge, the full description, and the acceptance criteria. A list of
titles is a summary; `--items` exists to give you the thing itself.

```bash
prj-mgr --items seah                          # every bead, in full
prj-mgr --items seah --ready --priority-max 0 # what can I start right now, in full
prj-mgr --items seah --phase 2 --open         # one phase
prj-mgr --items seah --compact                # one line per bead instead
```

| Filter | Effect |
|---|---|
| `--open` | hide closed beads |
| `--ready` | open **and** unblocked — the "what can I start" query |
| `--phase N` | one phase number |
| `--priority-max N` | that priority or more urgent (`0` = P0 only) |
| `--compact` / `--brief` | one line per bead plus its id, no body |
| `--width N` | wrap column, default 96 |

Marks are `[ ]` open, `[x]` closed, `[~]` in progress, `[!]` blocked. Phases
render only when something beneath them survives the filters, and every run ends
with `N shown, M hidden by filters` — a filtered list that does not say what it
dropped reads as a complete board.

**Size.** Expanded is verbose by design: a 31-bead board runs ~1150 lines
in full, ~70 with `--compact`. Filter rather than reaching for `--compact` when
you want less — `--ready --priority-max 0` is ~170 lines and is usually the
question being asked.

**Bodies are reflowed, not re-indented.** Bead descriptions arrive already
hard-wrapped near the same width, so indenting them without re-joining
paragraphs first pushes every line past the margin and dangles its last word.
`_wrap` re-joins paragraphs before wrapping, and leaves headings, tables, block
quotes and fenced code alone — reflowing those corrupts them.

**A note for anyone extending this.** Priority 0 is falsy. `bead.priority or 9`
rewrites every P0 as 9, so a `--priority-max` query silently drops exactly the
beads it exists to find. Use `x if x is not None else 9`. This shipped once and
was caught by the P0-only case returning nothing.

## Mode Detection

Parse `$ARGUMENTS` for the mode flag and route:

- **List mode** — `--ls`, or no arguments (default). Render the active project registry.
- **Status mode** — `--status [<project>]`. Phase detail for one board or all.
- **Sync mode** — `--sync [<project>]`. Regenerate snapshots from `br`. **Writes.**
- **Items mode** — `--items [<project>]`. The individual beads, grouped by phase. See **Items** below.
- **Bootstrap mode** — `--bootstrap`. Create the three `br` workspaces (ADR-052).
- **Ingest mode** — `--ingest <file|text>`, `--new-project`, or a bare file/text argument. See **Ingest** above.
- **Adopt mode** — `--adopt <bead-id>… --into <bead-id>`. Wire existing beads under a parent.
- **Where mode** — `--where`. Print resolved bead workspaces as JSON, including which resolution layer answered.
- **Help mode** — `--help`. Render the manifest below and stop.

Flags and positionals are separated before dispatch, so `--status seah` and
`seah --status` are the same request.

### The bare-argument ladder

A positional with no flag is classified, in this order. The order is
load-bearing and `prj_mgr.classify()` carries the reasoning:

| # | Test | Action |
|---|---|---|
| 0 | more than one token, or an embedded newline | **ingest** as text |
| 1 | a board directory name or alias | **status** |
| 2 | an existing file (tried against the cwd *and* the repo root) | **ingest** the file |
| 3 | matches `(iss\|ds\|cb)-…` | **refused**, with a pointer to `br show` / `--adopt` |
| 4 | longer than 80 chars, or contains whitespace | **ingest** as text |
| 5 | anything else | **refused**, with the known boards listed |

Rules 3 and 5 refuse rather than guess. A short unrecognised token is far more
likely a mistyped board name than a work item worth tracking, and silently
turning one into a bead is the failure this ladder exists to prevent.

## Help Mode

> When invoked with `--help`, render the manifest below and stop.

See `_lib/help_mode_template.md` for the canonical rendering contract — resolve it across the plugin boundary with `dekspec resource lib help_mode_template --path-only`.

```yaml
skill_name: "/prj-mgr"
one_line:   "View, track, or sync br-backed project boards — the issue-side pull surface"
modes:
  - { flag: "--ls", args: "", description: "List the active project registry: alias, name, current phase, status, completion, last activity. Default mode." }
  - { flag: "--status", args: "[<project>]", description: "Show one board's phase detail, or every board when no project is named." }
  - { flag: "--sync", args: "[<project>]", description: "Regenerate board snapshots from br. WRITES — announce before running and report what changed." }
  - { flag: "--items", args: "[<project>] [--open] [--ready] [--phase N] [--priority-max N] [--compact]", description: "Print each bead IN FULL — body, acceptance criteria, labels, blocks edges — grouped by phase. --compact gives one line per bead. Read-only." }
  - { flag: "--ingest", args: "<file|text> [--into <project> | --new-project [name]]", description: "Turn a document or pasted text into board-shaped beads. Proposes a summary first; WRITES only after approval. Also the meaning of a bare file path or several bare words." }
  - { flag: "--adopt", args: "<bead-id>... --into <bead-id>", description: "Wire existing beads under a parent bead. WRITES one parent-child edge per bead, no judgement." }
  - { flag: "--bootstrap", args: "", description: "Create the three br workspaces (ADR-052) in a repo that has none. Needs only br on PATH." }
  - { flag: "--where", args: "", description: "Print the resolved bead workspaces as JSON, including which resolution layer answered." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/prj-mgr"
  - "/prj-mgr --status seah"
  - "/prj-mgr --items seah --ready --priority-max 0"
  - "/prj-mgr seah"
  - "/prj-mgr docs/some-report.md"
  - "/prj-mgr --ingest docs/roadmap.md --new-project"
  - "/prj-mgr --adopt iss-p41au --into iss-phase-1-stop-the-bleeding-dpnkd"
  - "/prj-mgr --where"
```

## Rules

- **Never touch the code workspace** — read, write, or sync. See above.
- **`--sync`, `--ingest apply` and `--adopt` write.** Say so before running,
  and report what changed.
- **Never hardcode a workspace path** — resolve through the layers above.
- **Report the resolution source** when a board looks empty or wrong; a
  `fallback` result usually means the repo has not been split yet.
- **Ingest proposes before it writes.** Show the engineer the rendered summary
  from `review`, never the plan JSON, and never run `apply` until they approve.
  For a new board that means at most two questions — the name and the phases.
- **Prefer a comment to a duplicate bead.** The backlog is large enough that
  most findings in a new document already have a home. Splitting one problem
  across two beads is worse than a slightly long comment thread.
- **Never author triage policy here.** Decomposition, HITL/AFK tagging and the
  product gate belong to `write-issue-beads`; this skill follows its stages
  rather than restating them. If the two ever disagree, that is a bug.
