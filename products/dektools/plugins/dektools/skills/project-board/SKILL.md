---
name: project-board
description: Inspect and groom br-backed project boards; turn findings into actionable issues.
mode: lite
interaction: natural-language
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Write Bash Grep Glob
argument-hint: "[request or target]"
---

Use this for general issue intake, board status, dependency grooming, and derived
snapshots. It works without DekSpec. `br` is authoritative; PROJECT.md is generated.

Run `python3 scripts/prj_mgr.py --at REPO` from this skill's directory to list
boards. A project name shows its status; `--items PROJECT` shows compact tasks;
`--items PROJECT --full` expands bodies; `--where` shows resolved workspaces.
Use `--sync PROJECT` after tracker changes to regenerate snapshots. Resolve the
repo from the user's working directory or explicit target, never the plugin path.

Workspace identity comes from project configuration and tracked store pins, not from a fixed prefix. With `beads.project_prefix`, expect `<project>-iss` and `<project>-ds` and report any contradictory pin. Without that setting, use each existing store's tracked `.beads/config.yaml` `issue_prefix`; already-qualified stores work without installing DekSpec. Fall back to `iss`/`ds` only when neither setting exists. Malformed settings or stored-ID mismatches are errors, not empty boards. Use the resolved identities for routing, filtering and snapshots as well as `--where` output.

Reads do not initialize or migrate stores. When setup is explicitly requested, create only issue and governance stores (`.beads-issues/.beads/` and `.beads-dekspec/.beads/`) and pin their prefixes; do not create a root code-bead store. Preserve any legacy root workspace for history. Prefix migration is a separate, explicitly requested maintenance operation. Projects that also use the optional DekSpec library can consult its bead migration and recovery guide (`dekspec/beads-recovery.md` in a synced consumer, `docs/beads-recovery.md` in the library source) for the reviewed-preview and recovery procedure. The board does not invoke library migration or recovery commands and requires no engine installation. A hung or unreadable database requires preserving DB/WAL and proving export completeness before any rebuild; surface the operational failure without attempting an implicit repair.

For “add these findings”, first read current issues and search for duplicates.
Group findings by user outcome; preserve reproduction/evidence, acceptance checks,
priority and dependencies. Merge duplicates or append evidence before creating
new issues. Keep general issues distinct from governance and execution contracts;
never require code beads for implementation. The standalone path needs only br.

For a plan file or prose, `--ingest SOURCE --into PROJECT` gathers context. Follow
`scripts/ingest_plan.py --help` for its validate/review/apply sequence; validate
the prepared plan before apply and reuse its recorded IDs when resuming. An
explicit intake request authorizes routine record creation. Surface unresolved
scope/ownership decisions without forcing a row-by-row approval interview.
Use `--adopt ID... --into PARENT` to reparent existing work without duplicating it.

Report counts, blockers, next actionable tasks and resulting IDs. If br/workspaces
are missing, report that prerequisite; use bootstrap only when setup is requested.
If a source or project is ambiguous, show known projects and ask one scoped question.
Examples: “show parser work”; “add these audit findings”; “refresh the board”.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
