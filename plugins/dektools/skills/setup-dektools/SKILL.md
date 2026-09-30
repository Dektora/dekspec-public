---
name: setup-dektools
description: Choose optional tools, inspect selection, or repair their installation.
mode: lite
interaction: natural-language
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: "[request or target]"
---

Show current selection and available tools by default. Infer enable, disable,
replace, or repair from the request; “enable debugging and handoff” authorizes
that change without a questionnaire. Map the description to catalog names.

Run `python3 scripts/selector.py` from this skill directory with `--at` pointing
to the user's repository. The helper uses the installed `dekspec` CLI, not an
import from the ambient Python interpreter. Read `../../tool-catalog.json` for
purposes and dependency tiers. The default output distinguishes desired config
from each host's installed state. `status --full` includes tool descriptions.

For an explicit request, call `enable NAME...`, `disable NAME...`, or `set NAME...`
with `--at REPO --platform HOST`. `set` with no names disables all optional tools.
For repair, use `apply --at REPO --platform HOST`. Infer the host from the current
session or existing manifest; ask only if there are multiple plausible targets.
The user never needs to remember these helper flags.

Setup is always discoverable. The marketplace plugin registers only setup;
optional skills reside in its non-discovered `tools/` corpus. Selection emits
only the selected tools as repository-local skills, normally invoked as
`/handoff`, `/debug`, etc.; where the marketplace delivers core and setup, it
never re-emits them. Plugin
setup is `/dektools:setup-dektools` on namespaced hosts. Report the host's actual
name and reload requirement; existing sessions can retain stale registrations.

Recovery: missing engine → install the matching DekSpec engine release; missing
repo config → use core setup/init; failed config read → report its actual error;
failed emit → desired state may be saved but is NOT installed, then retry apply.
Conflicting modified/unowned files are preserved: show exact paths and review or
move them aside before retry. Do not delete a user's files to make selection pass.
An old cached whole-toolkit plugin requires upgrade and host reload. Never edit
plugin caches. With zero selected tools, setup still explains every capability.

Examples: “show what's available”; “enable project boards”; “remove security
review”; “repair this installation”. Recommend only tools relevant to the repo.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
