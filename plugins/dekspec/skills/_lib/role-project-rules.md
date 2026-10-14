# Your project's rules for generic roles

DekSpec's six built-in roles — `specifier`, `spec-reviewer`, `implementer`, `code-reviewer`, `verifier` and `auditor` — and the seven `*-author` subagents and DekBuilder's `coding-orchestrator` are generic. A project usually needs its own rules in the five areas below.

| Record key | Project rule and where to keep it today |
| --- | --- |
| `roles.project_rules.gates` | Gate and check commands: `.dekspec/config.yaml` keys `execution.integration_command` and `integration.worktree_setup`, a brief's Acceptance, or the Constitution's Quality Standards and Development Workflow articles. |
| `roles.project_rules.write_paths` | Writable paths and protected surfaces: a brief's Scope and Protected Surfaces, or an Intent's Components affected. |
| `roles.project_rules.credentials` | Available credentials: a Security Profile's Secret Stores lists stores; DekSpec has no place yet to specify which role may hold them. |
| `roles.project_rules.review_concerns` | Security and domain review concerns: a Security Profile, the Constitution, ADRs, or a brief's review acceptance conditions. |
| `roles.project_rules.models` | The model each role runs on: no per-role place yet, pending ADR-067's project mapping in wave 3; every role follows the session model until then. |

DekSpec does not yet feed these rules into role dispatches; ADR-077's project role extensions, planned for wave 3, are where that changes.

Under ADR-061 and ADR-077, project rules may only add to a role and never relax it; the library owns the role definitions. Record a repository path (a folder or index for multiple files), or explicitly record that no rule exists:

`dekspec config set roles.project_rules.<kind> <path or "none: <reason>">`

See [Project rules for the built-in roles](../../../../docs/dekspec-operating-guide.md#project-rules-for-the-built-in-roles), available with `dekspec resource doc operating-guide`.
