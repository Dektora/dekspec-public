---
name: using-dekspec
description: Onboarding entry point for DekSpec — scaffold the artifact tree, toggle the No Specless Edits guardrail, and discover the skill catalog from a single skill. Merges the legacy `spec-mode`, `dekspec-skills`, and `dekspec-init` surfaces (INT-096).
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--init [--at PATH] [--force] [--methodology lite|team|full] [--profile lite|full]] [--spec-mode --on|--off|--status] [--catalog] [--help]
---

A single onboarding skill that walks an engineer through getting DekSpec live in a repo: scaffold the artifact tree, decide whether to enable the "No Specless Edits" guardrail, and discover the full skill catalog.

> **Replaces three legacy surfaces (INT-096):** `/dekspec:spec-mode`, `/dekspec:skills`, and `/dekspec:init` are merged into this single entry point. Existing functionality is preserved verbatim via the `--init`, `--spec-mode`, and `--catalog` modes below.

## Mode Detection

Default mode: **Walkthrough Mode** (no flag — guided tour of all three sub-surfaces).

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Init mode** — `--init` flag. Skip to **Init Mode**.
- **Spec-mode mode** — `--spec-mode` flag (paired with `--on`, `--off`, or `--status`). Skip to **Spec-Mode Mode**.
- **Catalog mode** — `--catalog` flag. Skip to **Catalog Mode**.
- **Walkthrough mode** — no flag. Proceed to **Walkthrough Mode**.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Render the manifest below and stop.

```yaml
skill_name: "/dekspec:using-dekspec"
one_line:   "Onboarding entry point — init + spec-mode + catalog merged into one skill (INT-096)"
modes:
  - { flag: "",             args: "",                       description: "Walkthrough: scaffold + guardrail decision + catalog summary, in that order. (Default)" }
  - { flag: "--init",       args: "[--at PATH] [--force]",  description: "Run `dekspec library init` — scaffold the artifact tree (adrs/, architecture-elements/, working-specs/, ...). Forwards remaining args to the CLI verb." }
  - { flag: "--spec-mode",  args: "--on|--off|--status",    description: "Enable, disable, or check the 'No Specless Edits' guardrail in CLAUDE.md. (Status is the default if no on/off/status given.)" }
  - { flag: "--catalog",    args: "",                       description: "Print the full DekSpec skill catalog grouped by category, with one-line purpose + how to trigger for each skill." }
  - { flag: "--help",       args: "",                       description: "Show this help message." }
examples:
  - "/dekspec:using-dekspec                       # default — guided walkthrough"
  - "/dekspec:using-dekspec --init --at ."
  - "/dekspec:using-dekspec --spec-mode --on"
  - "/dekspec:using-dekspec --catalog"
```

## Walkthrough Mode

Guided tour for an engineer adopting DekSpec in a fresh repo. Touches all three sub-surfaces in the order an operator usually needs them:

0. **Engine check.** Run `command -v dekspec`. If the `dekspec` CLI is not on PATH, the plugin's surfaces have no engine to drive — surface the pip-from-git install line and continue:
   ```bash
   pipx install "git+https://github.com/Dektora/dekspec-public.git@main"
   ```
   (`@main` → latest; pin a release with `@vX.Y.Z`. Engine is acquired from the curated public mirror, ADR-034). Re-run this walkthrough once the CLI resolves.
1. **Scaffold check.** Run `ls dekspec/ 2>/dev/null`. If the tree exists, report "DekSpec artifact tree present — skipping scaffold." Else, ask: "Run `dekspec library init` here? [Y/n]" and, on yes, run Init Mode against the cwd. On no, surface the manual command and continue.
2. **Spec-mode decision.** Run the Status sub-flow from Spec-Mode Mode. If `NOT INSTALLED` or `DISABLED`, ask: "Enable the 'No Specless Edits' guardrail in CLAUDE.md? [Y/n] (recommended for repos with active spec work)". On yes, run the On sub-flow. On no, leave as-is and continue.
3. **Catalog summary.** Render the **Quick reference** subset from Catalog Mode (categories + the single most-used skill per category, not the full table). End with one-liner: "Run `/dekspec:using-dekspec --catalog` for the full table; ask in natural language to trigger any skill."

Close with a one-line "Next step" recommendation matched to the engineer's state: if the scaffold was fresh, recommend `/write-ae` for the first Architecture Element; if spec-mode was just enabled, remind that future code-changing requests will be gated on a spec artifact existing.

**End of Walkthrough Mode.**

## Init Mode

Scaffold the DekSpec artifact directory layout in the current directory (or `--at <path>`). Wraps the `dekspec library init` CLI verb.

1. Confirm the user wants to scaffold in the current directory (run `pwd` and show the path). If `--at <path>` is supplied, use that path.
2. Run `dekspec library init $ARGUMENTS` via Bash (forwarding all flags after `--init` to the CLI verb — `--at`, `--dekspec-root`, `--force`, `--executor`, `--endpoint`, `--methodology`, `--profile`).
3. Report which subdirs were created and which already existed.
4. Hint that the natural next step is `/write-ae` (for the first Architecture Element), after which `/dekspec:doctor` will surface a baseline of findings to triage.

**End of Init Mode.**

## Spec-Mode Mode

Enable, disable, or check the "No Specless Edits" guardrail in the repo-root `CLAUDE.md`. Behavior preserved verbatim from the legacy `spec-mode` skill (INT-091 / INT-096).

### Status sub-flow (default when no `--on` / `--off` given)

1. Read `CLAUDE.md` in the repo root. If it does not exist, report status as `NOT INSTALLED` and stop.
2. Scan for the **No Specless Edits** pattern:
   - Present + uncommented → report **ENABLED**.
   - Present + enclosed in `<!-- ... -->` → report **DISABLED**.
   - Not found → report **NOT INSTALLED**.
3. Display the status in a clean, high-visibility format:
   ```
   Spec Mode Status: ENABLED
   ```

### On sub-flow (`--on`)

1. Read `CLAUDE.md` in the repo root. If absent, create it with a default structure.
2. Locate the `## Guardrails` or `## Rules` section. If neither exists, append a new `## Guardrails` section at the end (or after the project description).
3. Check the **No Specless Edits** spec-mode line:
   - Present + active → no-op.
   - Commented out (`<!-- ... -->`) → uncomment to activate.
   - Missing → insert under the `## Guardrails` / `## Rules` heading.

   The exact text of the active spec mode MUST be:
   ```markdown
    - **No Specless Edits**: You have wide latitude to determine when a user request suggests, implies, or directly asks for new capabilities, features, refactoring, codebase modifications, or updates to code/spec artifacts. In any such case, before proceeding with the request, you must immediately halt, make the engineer aware, and inquire whether a corresponding specification artifact (such as an Intent, Mission, ADR, or active Implementation Brief under `dekspec/`) should be created or updated. To assist the engineer, you must provide 1 to 3 context-aware suggestions (formatted as clear choices) of what specific actions or new/modified artifacts would be appropriate for the task. Prompt the user clearly with your inquiry and suggestions. Do not make source code edits until this specification context is established or explicitly deferred by the engineer.
   ```
4. Write the modified content back to `CLAUDE.md`.
5. Display a clean success message indicating spec mode is now **ENABLED**.
6. **Provisional-first reminder.** After the success message, ALWAYS emit the following authoring-discipline reminder block verbatim. This is the R1 augmentation from INT-091 — spec-mode catches code edits without a spec, but does NOT catch a spec being authored in the wrong place. The reminder closes that gap so engineers don't author new Intents/Missions directly in the canonical `dekspec/intents/` or `dekspec/missions/` tree (which collides on canonical ID allocation when multiple authors draft concurrently) and instead use the provisional → hand-promote workflow:

   ```
   --- Authoring discipline reminder ---
   NEW Intents (INT-NNN) and NEW Missions (MSN-NNN) ALWAYS start under
   `dekspec/provisional/<slug>/` via `dekspec library cow-stage <slug>` (or by
   hand-creating the directory + `INT-provisional-<slug>.md` skeleton).
   Canonical IDs (INT-NNN / MSN-NNN) are allocated only at hand-promote time,
   not at draft time. Walk DRAFT -> analyze -> PROPOSED -> ACCEPTED in
   provisional; promote via:
       dekspec.promote.plan_promotion(incubation_dir, dekspec_dir)
       dekspec.promote.apply_promotion(steps, incubation_dir, repo_root)
   when the family is ACCEPTED. This rule prevents canonical-ID collisions
   when multiple authors draft concurrently and keeps the canonical tree
   free of half-baked drafts.
   ```

   Emit the reminder unconditionally on every `--on` invocation. If the engineer's next user request authors a NEW Intent/Mission (heuristic: the request mentions "draft an Intent / draft a Mission / new INT-NNN / new MSN-NNN / author an Intent / author a Mission" and there is no current provisional dir matching the topic), additionally call the rule out inline in the assistant's response and recommend the provisional path explicitly rather than silently complying with a canonical-tree create.

### Off sub-flow (`--off`)

1. Read `CLAUDE.md` in the repo root. If absent, there is nothing to disable — report and stop.
2. Locate the **No Specless Edits** spec-mode line under the `## Guardrails` or `## Rules` section.
3. Check its current state:
   - Already commented out or missing → no-op.
   - Present + active → enclose in HTML comment tags so it is not parsed as an active rule:
     ```markdown
      <!-- - **No Specless Edits**: You have wide latitude to determine when a user request suggests, implies, or directly asks for new capabilities, features, refactoring, codebase modifications, or updates to code/spec artifacts. In any such case, before proceeding with the request, you must immediately halt, make the engineer aware, and inquire whether a corresponding specification artifact (such as an Intent, Mission, ADR, or active Implementation Brief under `dekspec/`) should be created or updated. To assist the engineer, you must provide 1 to 3 context-aware suggestions (formatted as clear choices) of what specific actions or new/modified artifacts would be appropriate for the task. Prompt the user clearly with your inquiry and suggestions. Do not make source code edits until this specification context is established or explicitly deferred by the engineer. -->
     ```
4. Write the modified content back to `CLAUDE.md`.
5. Display a clean confirmation message indicating spec mode is now **DISABLED**.

**End of Spec-Mode Mode.**

## Catalog Mode

Render the full DekSpec skill catalog. Behavior preserved verbatim from the legacy `skills` command (INT-096).

1. Print a beautifully formatted, premium markdown table of all available DekSpec skills grouped by category.
2. For each skill, include the purpose and how to trigger it in conversation.
3. Suggest typing `/dekspec:run-session` to launch an interactive spec-authoring shell.

---

# DekSpec Skills Catalog 🧭

Welcome to the DekSpec Spec-Driven Development skills catalog. Since authoring skills are designed to be run through interactive AI reasoning, they are not registered as raw shell commands. Instead, you can trigger them simply by asking me in natural language!

Use the table below as a quick reference sheet:

### 1. Spec Authoring Skills (L1 & L2 Artifacts)
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`write-sv`** | System Vision (L0 Singleton) | *"Let's write/edit the System Vision"* |
| **`write-ae`** | Architecture Element (AE) | *"Create a new Architecture Element for [component]"* |
| **`write-adr`** | Architectural Decision Record (ADR) | *"Let's author an ADR choosing X over Y"* |
| **`write-ic`** | Interface Contract | *"Create an Interface Contract for [boundary]"* |
| **`write-ws`** | Working Spec | *"Write a Working Spec for [subsystem]"* |
| **`write-ibs`** | Implementation Briefs (IB) | *"Decompose [Working Spec] into IBs"* |
| **`write-intent`** | Intent (INT-NNN) | *"Let's draft a new Intent for [feature]"* |
| **`write-mission`** | Mission (MSN-NNN) | *"Create a long-horizon Mission for [goal]"* |
| **`write-constitution`**| Project Constitution | *"Review or amend the Constitution"* |

### 2. Verification & Quality Skills
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`/doctor`** | Full health check — schema + linkage + drift + T/D/L fidelity (Stage 1 CLI doctor, Stage 2 inlined fidelity body) | *"Run /doctor"* or *"Audit our specs"* |
| **`/validate-artifact`** | Single-artifact schema validation (narrower than `/doctor`) | *"Validate dekspec/intents/INT-105-foo.md"* |
| **`write-tests`** | Pre-generate test cases from beads | *"Generate test cases for [beads]"* |
| **`write-evals`** | Setup probabilistic behavior evals | *"Write evals for [IB/beads]"* |

### 3. Developer Aids & Utilities
| Skill | Purpose | How to Trigger / Ask |
|---|---|---|
| **`archeology`** | Brownfield spec-gap recovery — code → ratifiable Intent | *"Recover the spec gaps in this repo"* |
| **`brownfield-ingest`** | Classify inherited markdown prose into DekSpec artifact slots | *"Ingest legacy document [path]"* |
| **`dispatch-inbox-listener`** | Async-dispatch listener for `.dekspec/inbox/` Packages | *"Start the dispatch listener"* |
| **`using-dekspec`** | This skill — onboarding + spec-mode + catalog | *"Get me started with DekSpec"* |

---

### Pro-Tip 💡
To boot up a dedicated, interactive spec-authoring workspace where we guide you through the process, just run the orchestration slash command:
```bash
/dekspec:run-session
```

**End of Catalog Mode.**
