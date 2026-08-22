---
description: View, track, sync, or ingest into br-backed project boards — the issue-side pull surface (ADR-052). Runs standalone with no DekSpec installed.
argument-hint: "[<file|text> | --ls | --status [<project>] | --sync [<project>] | --items [<project>] | --ingest <file|text> [--into <project> | --new-project [name]] | --adopt <bead-id>... --into <bead-id> | --bootstrap | --where | --help]"
allowed-tools: Read Write Bash Grep Glob
---

Invoke the `prj-mgr` skill from the DekTools plugin.

Read [`skills/prj-mgr/SKILL.md`](../skills/prj-mgr/SKILL.md) and follow it as
the active contract, then run the requested mode against `$ARGUMENTS`.

Quick reference — the scripts are self-contained (standard library + `br`):

```bash
python plugins/dektools/skills/prj-mgr/scripts/prj_mgr.py --ls
python plugins/dektools/skills/prj-mgr/scripts/prj_mgr.py --status [<project>]
python plugins/dektools/skills/prj-mgr/scripts/prj_mgr.py --sync [<project>]
python plugins/dektools/skills/prj-mgr/scripts/prj_mgr_items.py <project> [--open] [--ready] [--phase N] [--priority-max N] [--compact]
python plugins/dektools/skills/prj-mgr/scripts/ingest_plan.py context|review|apply|adopt
python plugins/dektools/skills/prj-mgr/scripts/beads_workspace.py      # --where
python plugins/dektools/skills/prj-mgr/scripts/bootstrap_beads.py      # --bootstrap
```

Default mode with no arguments is `--ls`. A bare positional is classified
rather than rejected — a board name means `--status`, a file or several words
means `--ingest`; see the bare-argument ladder in SKILL.md.

**`--sync`, `--ingest apply` and `--adopt` write.** Tell the engineer before
running them and report what changed. Ingest never writes until the engineer
approves the rendered `review` summary.

**This is the issue side.** Bare `br ready` is reserved for the next ready
*code* bead (ADR-052); never use this tool to pick coding work.
