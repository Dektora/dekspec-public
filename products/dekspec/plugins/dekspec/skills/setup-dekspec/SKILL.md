---
name: setup-dekspec
description: Initial-configuration front-end for DekSpec — interactively walk an engineer through the per-repo `.dekspec/config.yaml` choices (issue tracker, ephemeral-scratch location, triage-label vocabulary, glossary path, methodology profile), persisting each via `dekspec config set` so it round-trips through `dekspec config get`. Writes agent-config pointers for consumer agents and optionally hands off to the quality/guardrail hook install. Called by `using-dekspec`'s onboarding walkthrough for the configuration step.
mode: lite
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: "[--help] [--at PATH]"
related_skills: [using-dekspec, write-glossary, write-ibs]
---

Run the per-repo DekSpec initial-configuration walkthrough: front-end the
existing `.dekspec/config.yaml` (via `dekspec config get` / `dekspec config
set`) so the engineer configures, once, the choices a working DekSpec adoption
needs — which issue tracker the repo uses, where ephemeral skill output lands,
the triage-label vocabulary the issue-tracking flows consume, the
domain-glossary location, and the methodology profile. Each answer persists as
a config key that round-trips through `dekspec config get`.

This skill is the **configuration half** of DekSpec onboarding (INT-174 / ι1).
`using-dekspec` stays narrow (scaffold the artifact tree + toggle the
No-Specless-Edits guardrail + render the catalog) and *calls* `setup-dekspec`
for the configuration step; `setup-dekspec` owns no scaffolding and no hook
surface of its own.

## Starter Prompt

```prompt
/dekspec:setup-dekspec --at .

Walk me through the per-repo DekSpec config one question at a time, recommend a
sensible default per question, and persist each answer with `dekspec config set`
so it round-trips. When a question is genuinely a domain-term decision, route it
to /dekspec:write-glossary rather than inventing a definition inline.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Setup Mode**.

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Setup mode** — no flag (default). Optional `--at PATH` names the repo root (default: current working directory). Run the configuration walkthrough below.

This skill exposes no lifecycle/audit/review flags of its own — it is an
interactive configuration front-end, not an artifact-lifecycle authoring skill.
(It is therefore exempt from the `_lib/mode_dispatcher.md` universal-mode set,
which applies only to the `write-*` artifact-lifecycle skills.)

## Setup Mode

Walk the configuration one question at a time. For each field below: state the
recommended default + a one-line rationale, accept the engineer's answer (or the
default), then persist it with `dekspec config set <key> <value> --at <repo>`
and confirm it reads back via `dekspec config get <key> --at <repo>`. If
`.dekspec/config.yaml` does not exist yet, tell the engineer to run
`/dekspec:using-dekspec --init` (or `dekspec init`) first — `setup-dekspec`
edits an existing config, it does not scaffold one.

1. **Issue tracker** — `issue_tracker` (enum `br | github | gitlab | local`).
   *Recommended:* `br` (the in-repo beads-rust tracker; committed JSONL,
   repo-scoped). Choose `github`/`gitlab` only if the team tracks work on the
   remote forge, `local` for an offline tracker. The tracker holds issue and
   governance work (the `iss-` / `ds-` workspaces); it is **not** the
   construction surface — accepted IBs are executed directly and
   `dekspec ib ready` is the pull surface (ADR-056).
   - **Project prefix (`br` only)** — ask for `beads.project_prefix`.
     Recommend 2–6 lowercase ASCII letters/digits derived from the repository
     name (for example `usurance` → `usr`). No hyphens, dots or underscores.
     Explain that tightly coupled repositories should choose distinct prefixes.
     Inspect existing stores first: if they contain a different identity, run
     `dekspec beads reprefix --to <prefix> --at <repo> --json` for a preview;
     do not change config or rename beads implicitly. Present the preview and
     obtain authorization for `--apply --expect-plan <plan_sha256>`.
     For fresh stores, run `dekspec config set beads.project_prefix <prefix>`
     and confirm with `dekspec config get beads.project_prefix`, then run
     `dekspec beads init --at <repo>`.
     This creates `.beads-issues/.beads` and `.beads-dekspec/.beads`, with tracked
     `issue_prefix: <prefix>-iss` and `<prefix>-ds` pins. Never initialize a root
     code workspace: never run bare `br init` in the repository root. Preserve
     any existing legacy root history.
     No local store initialization is needed for `github`/`gitlab`/`local`.
   - **Before authoring**, run `dekspec sync --at <repo>` to vendor the installed
     templates and methodology content. This reconciles locally without network
     acquisition and reports divergences instead of overwriting authored work.
2. **Ephemeral-scratch location** — `ephemeral_scratch_dir` (path).
   *Recommended:* `dekspec/.scratch/` (the gitignored, disposable hand-off zone
   landed by INT-165). Where interview logs and skill hand-off notes land.
3. **Triage-label vocabulary** — `triage_labels.hitl`, `triage_labels.afk`,
   `triage_labels.buckets`. *Recommended:* `hitl` / `afk` for the
   human-in-the-loop vs away-from-keyboard labels, and a small ordered bucket
   list the team triages into. These are the labels the issue-tracking
   flows consume. For the `buckets` list, write the nested object shape
   directly into `.dekspec/config.yaml` (a YAML list) rather than forcing it
   through a single scalar `config set`.
4. **Glossary path** — `glossary_path` (path). *Recommended:*
   `dekspec/domain-glossary.md` (the term corpus the authoring + interview
   skills cite).
5. **Methodology profile** — `methodology_profile` (alias `profile`; enum
   `full | team`). *Recommended:* `full` — the default lane at full rigor
   (ADR-050), which is what a solo engineer wants and the value to keep
   unless the repo has multiple engineers signing off on transitions.
   `team` adds the INT-021 approval gates on top of it.

### Project rules for the built-in roles

Show the text of [role-project-rules](../_lib/role-project-rules.md) unchanged,
as resolved by `dekspec resource lib role-project-rules --at <repo>` (the
adjacent fragment is available to read too). If the notice cannot be loaded,
report that failure and name `dekspec resource lib role-project-rules`; never
paraphrase or reconstruct it.

Ask where the project keeps each kind below, **one kind at a time**. First run
its `config get`, show any existing value, and keep it unless the engineer gives
a replacement. Accept one repository path, or `none: <reason>` when there is
no home yet. For rules spread across files, record a folder or an index file.
A path need not exist; it must be relative to the repository, with no leading
or trailing whitespace, leading slash, Windows drive prefix, backslash or
`..` segment. Ask for a reason if the answer is `none` or `none:` without a
non-space reason; never record either of those or an empty value. An empty
answer keeps an existing value; without one, ask again.

For each new or changed answer, run its `config set` with the value safely
shell-quoted as one argument, then repeat its `config get` to confirm the exact
value reads back. If the CLI refuses an answer (including exit 2 for an unknown
key or malformed value), show the refusal and ask again. Never edit
`.dekspec/config.yaml` by hand for these keys.

| Kind — explain before asking where it lives | Read existing value and confirm after setting | Record the answer |
| --- | --- | --- |
| `gates` — checks a role must run successfully. | `dekspec config get roles.project_rules.gates --at <repo>` | `dekspec config set roles.project_rules.gates <value> --at <repo>` |
| `write_paths` — allowed write locations and surfaces that must be preserved. | `dekspec config get roles.project_rules.write_paths --at <repo>` | `dekspec config set roles.project_rules.write_paths <value> --at <repo>` |
| `credentials` — available credentials and which roles may use them. | `dekspec config get roles.project_rules.credentials --at <repo>` | `dekspec config set roles.project_rules.credentials <value> --at <repo>` |
| `review_concerns` — security and domain checks for reviewers. | `dekspec config get roles.project_rules.review_concerns --at <repo>` | `dekspec config set roles.project_rules.review_concerns <value> --at <repo>` |
| `models` — where the project documents its rule about models for roles. | `dekspec config get roles.project_rules.models --at <repo>` | `dekspec config set roles.project_rules.models <value> --at <repo>` |

These answers are pointers only: never open, read or validate their target
files. This step writes no role file, agent definition, extension or stub;
it neither recommends nor selects a model and writes no model mapping.
Showing this notice records only the answers above; never create, change or
delete `.dekspec-role-disclosure.json` in this step.

### Agent-config pointers

After the config fields are set, write the consumer-agent pointers so
downstream agents discover the configured choices: the **tracker** (`dekspec
config get issue_tracker`), the **domain glossary** (`dekspec config get
glossary_path`), and the **skill catalog** (`/dekspec:using-dekspec --catalog`).
Surface these as a short pointer block the engineer can drop into the repo's
agent-config (e.g. `AGENTS.md` / `CLAUDE.md`), rather than editing those files
silently.

### Optional next step — quality & guardrail hooks (deferred)

As an **optional, opt-in** final step, offer to install the Python quality gate
+ destructive-git block hooks. That surface is owned by the sibling Intent
`quality-and-guardrail-hooks`, NOT authored here — if the engineer accepts and
that sibling's hook-install flow is available, invoke it; if it is not yet
present, treat this as a no-op skip and note it as a deferred next step.
`setup-dekspec` never writes a hook or a `.pre-commit-config.yaml` fragment
itself.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:setup-dekspec"
one_line:   "Interactive per-repo config front-end — issue tracker, scratch dir, triage labels, glossary, profile (round-trips through dekspec config)"
modes:
  - { flag: "", args: "[--at PATH]", description: "Setup mode — walk the .dekspec/config.yaml choices one question at a time (issue_tracker, ephemeral_scratch_dir, triage_labels, glossary_path, methodology_profile), persisting each via `dekspec config set` so it round-trips, then show the project-rules notice and record where each kind of rule lives, write agent-config pointers and optionally hand off to the quality/guardrail hook install." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:setup-dekspec --at ."
  - "/dekspec:setup-dekspec"
  - "/dekspec:setup-dekspec --help"
storage: ".dekspec/config.yaml (per-repo committed config; written via `dekspec config set`)"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

**End of Help Mode.**

## When to use

- During DekSpec onboarding, after `/dekspec:using-dekspec --init` has scaffolded the artifact tree and written a base `.dekspec/config.yaml` — to configure the per-repo choices a working adoption needs.
- To show the project-rules notice and record or revisit where the project keeps each kind of rule for the built-in roles.
- Any time the engineer wants to revisit the tracker / scratch-dir / triage-label / glossary / profile choices, each of which round-trips through `dekspec config`.

## When NOT to use

- To scaffold the artifact tree or toggle the No-Specless-Edits guardrail — that is `/dekspec:using-dekspec`.
- To author or install the quality/guardrail hooks — that surface is owned by the sibling Intent `quality-and-guardrail-hooks`; `setup-dekspec` only optionally *invokes* it.

## Related

- `/dekspec:using-dekspec` — the onboarding entry point that scaffolds + toggles the guardrail + renders the catalog, and calls this skill for the configuration step.
- `/dekspec:write-glossary` — domain-term clarifications surfaced during setup route here.
- `dekspec config get` / `dekspec config set` — the CLI surface this skill front-ends.
- AE-006 (Skills Library) — the AE this skill registers under; AE-005 (CLI) — the config verb it drives.
