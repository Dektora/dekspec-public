---
name: setup-dektools
description: "Re-runnable à-la-carte selector for the DekTools suite (ADR-047) — show the tool catalog with each tool's dependency tier, let the engineer add or remove individual tools, persist the choice as the repo's `dektools.enabled` set, then re-emit the host tree so exactly the enabled tools register. Nothing is on by default, the selection travels with the repo, and removal is non-destructive: it disables a tool's surface and deletes no user data. Re-run it any time to widen or narrow the active tool set. The toolkit analogue of core's `setup-dekspec`."
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: "[--help] [--status] [--apply] [--at PATH] [--platform HOST]"
related_skills: [setup-dekspec, using-dekspec, prj-mgr]
---

> **Preflight (ADR-047).** This is a `dekspec-required` tool. From this skill's own directory run `python ../../scripts/dependency_guard.py setup-dektools` before anything else — it exits non-zero with install instructions when the DekSpec engine is absent. (The path is relative to this file so it resolves identically in the monorepo, a packaged plugin install, and an emitted per-host tree.) If it fires, stop and surface its message; do not proceed.

> **Shared `_lib` lives in the DekSpec core plugin** (ADR-047). Resolve it with `dekspec resource lib <name> --path-only`, then read that path — a relative `../_lib/` link does not cross the plugin boundary.

Run the **DekTools à-la-carte selector**: choose which tools in the toolkit are
active in this repo, and make the host tree match.

A plugin installs all-or-nothing at the harness level, so DekTools manages
selection itself (ADR-047). Two pieces already exist in core and this skill is
their front-end — it invents no state of its own:

- **The catalog** — `plugins/dektools/tool-catalog.json`, the list of known
  tools and each one's `dependency_tier`.
- **The enabled-set** — `dektools.enabled` in the repo's
  `.dekspec/config.yaml`. It is the single gate: `dekspec install` emits
  exactly the enabled subset and prunes every catalogued tool that is not in
  it, on every host.

Three properties hold at all times, and they are ADR-047's, not this skill's:

1. **Nothing is on by default.** An unset key and an empty list mean the same
   thing. A fresh repo has zero DekTools tools active.
2. **Re-running adds *and* removes.** The selector is not a one-shot installer;
   it is the standing surface for changing the active set.
3. **Removal is non-destructive.** Disabling a tool removes that tool's
   emitted skill directory and command file and nothing else. Boards, spike
   records, scratch logs, notes, and every core skill survive untouched.

## Starter Prompt

```prompt
/dektools:setup-dektools --at .

Show me the DekTools catalog with each tool's dependency tier and what is
enabled today, recommend a starting set for this repo, then enable exactly what
I pick and re-emit the Claude host tree so the selection takes effect.
```

## Mode Detection

See `_lib/mode_detection_template.md` (resolve: `dekspec resource lib mode_detection_template`). Default mode: **Select mode**.

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Status mode** — `--status` flag. Read-only: render the catalog and the
  current selection, change nothing, persist nothing, emit nothing.
- **Apply mode** — `--apply` flag. Re-emit the host tree from the *already
  persisted* selection without changing it. Use after a `git pull` brings a
  teammate's selection in, or when a host tree has drifted.
- **Select mode** — no flag (default). Run the walkthrough below.

`--at PATH` names the repo root (default: cwd) and `--platform HOST` names the
harness to emit for (`claude`, `codex`, `antigravity`, `cursor`, `copilot`,
`pi`; default `claude`). Both are arguments to every mode, not modes.

## Select Mode

The whole selector is one script — `scripts/selector.py`, shipped beside this
file. It reads the catalog, computes the add/remove diff, persists through
`dekspec config set`, and re-runs `dekspec install`. Drive it; do not edit
`.dekspec/config.yaml` by hand, and never hand-copy a skill directory into a
host tree.

### 1. Show where the repo stands

```bash
python scripts/selector.py status --at <repo>
```

It prints what is enabled, then a numbered **still remaining** list of the rest
of the catalog (capped at 8; `--full` for all), so the à-la-carte progress is
visible at every step. Each row carries the tool's `dependency_tier`.

If it reports no `.dekspec/config.yaml`, stop and route the engineer to
`/dekspec:using-dekspec --init` (or `dekspec init`) first — the selection is
persisted in the repo's DekSpec config so it travels with the project, and
there is nowhere to write it until that file exists.

### 2. Talk through the choice

Present the remaining tools and recommend a set, grounded in what the repo
actually does rather than in the catalog's length. Useful framings:

- A repo that tracks work in `br` wants `prj-mgr`.
- A brownfield adoption wants `brownfield-ingest` and `archeology`; a
  greenfield one wants neither.
- A repo doing architecture work wants `audit-codebase` and
  `analyze-module-depth`.
- Sessions that rotate or compact often want `rotation-handoff`.

**Say the tier out loud, because it changes what a tool needs.** Every tool is
`dekspec-required` — it reads the DekSpec IR or the audit/review model, and the
dependency guard refuses to run it when the engine is absent — *except*
`prj-mgr`, which holds the `dekspec-enhanced` tier: zero coupling, fully usable
with no DekSpec engine installed at all, and enriched rather than enabled when
DekSpec is present. The guard stays silent for it by design.

Two cautions worth raising when they come up:

- Enabling everything is the default this ADR exists to prevent. A tool the
  engineer cannot name a use for should stay off; re-running later costs one
  command.
- Disabling `setup-dektools` itself removes the selector's own emitted surface
  from the host tree. The skill still runs from the plugin, but confirm the
  engineer means it.

### 3. Persist and emit — one command

```bash
python scripts/selector.py enable  <tool>... --at <repo> --platform <host>
python scripts/selector.py disable <tool>... --at <repo> --platform <host>
python scripts/selector.py set     <tool>... --at <repo> --platform <host>
```

- `enable` adds to the current set; `disable` removes from it; `set` replaces
  it outright, and `set` with no names clears it.
- Each writes `dektools.enabled` via `dekspec config set`, then — when
  `--platform` is given — runs `dekspec install` so the host tree matches
  immediately. Without `--platform` nothing is emitted and the printed
  next-step names the install command; run it before telling the engineer the
  change is live.
- An uncatalogued name is a usage error (exit 2) and **nothing is written** —
  the selector never reports success for a tool it did not enable.
- Re-running with an already-enabled tool is a clean no-op, not a duplicate.

Report the `added` / `removed` diff the script prints, and confirm the outcome
against the host tree rather than against the config alone — the emitted
`skills/<tool>/` directory appearing or disappearing is the observable proof
that the selection took effect.

### 4. Multi-host repos

The enabled-set is one per repo, shared by every harness. A repo that emits for
more than one host re-applies the same selection per host:

```bash
python scripts/selector.py apply --at <repo> --platform codex
```

## Help Mode

See `_lib/help_mode_template.md` (resolve: `dekspec resource lib help_mode_template`). Manifest for this skill:

```yaml
skill_name: "/dektools:setup-dektools"
one_line:   "À-la-carte DekTools selector — catalog + tiers, add/remove tools, persist to dektools.enabled, re-emit the host tree"
modes:
  - { flag: "", args: "[--at PATH] [--platform HOST]", description: "Select mode — show the catalog with dependency tiers and the current selection, walk the engineer through what to add or remove, persist it via `dekspec config set dektools.enabled`, and re-emit the host tree so exactly the enabled tools register." }
  - { flag: "--status", args: "[--at PATH]", description: "Read-only — render the catalog, the enabled-set, and the numbered still-remaining list. Persists nothing, emits nothing." }
  - { flag: "--apply", args: "[--at PATH] [--platform HOST]", description: "Re-emit the host tree from the already-persisted selection without changing it (after a pull, or when a host tree has drifted)." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dektools:setup-dektools --at ."
  - "/dektools:setup-dektools --status"
  - "/dektools:setup-dektools --apply --platform codex"
  - "/dektools:setup-dektools --help"
storage: ".dekspec/config.yaml key `dektools.enabled` (per-repo, committed, written via `dekspec config set`); the emitted host tree under the harness root."
```

At runtime, render the manifest per the help-mode template and stop.

**End of Help Mode.**

## When to use

- Right after installing DekTools in a repo — nothing is active until a
  selection is made.
- Any time the active tool set should widen (a new phase of work needs
  `archeology`) or narrow (a tool the team never reaches for).
- After a pull that brings a teammate's selection in, to re-emit the host tree
  (`--apply`).

## When NOT to use

- **To configure DekSpec itself** — tracker, scratch dir, triage labels,
  glossary, methodology profile. That is `/dekspec:setup-dekspec`.
- **To scaffold the artifact tree or initialize the repo.** This skill edits an
  existing config; `/dekspec:using-dekspec` does the init.
- **To delete a tool's data.** Disabling removes a tool's emitted surface, and
  that is all it will ever do. Boards, spike records, and scratch logs are the
  engineer's to remove deliberately.
- **To change what a tool's dependency tier is.** The tier is a claim about the
  code, granted on evidence and revoked when coupling lands (ADR-047); it is a
  catalog + test question, not a selector setting.

## Governing artifacts

- **ADR-047** — core/toolkit plugin boundary. Names the à-la-carte selector a
  required deliverable, fixes "nothing on by default" and non-destructive
  removal, and defines the two dependency tiers.
- `plugins/dektools/tool-catalog.json` — the catalog this selector reads.
- `plugins/dektools/scripts/dependency_guard.py` — the per-tool, tier-keyed
  guard the preflight runs.
