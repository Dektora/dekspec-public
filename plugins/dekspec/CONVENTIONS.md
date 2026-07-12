# DekSpec Plugin — Surface Classification Conventions

**Status:** AUTHORITATIVE.
**Audience:** Plugin contributors. Read this before adding, renaming, or removing a slash command or skill.
**Origin:** Codified after the 2026-05-27 plugin-cleanup sprint (B1–B12). Captures the conventions that emerged from INT-095, INT-096, INT-098 + the cleanup sprint.

---

## What lives where

```
plugins/dekspec/
├── commands/             # slash commands — typeable invocation surfaces
├── skills/               # skills — capability + expertise surfaces
├── agents/               # subagent definitions (separate surface, not in scope here)
├── hooks/                # hook declarations
├── hooks-handlers/       # hook executor scripts
├── scripts/              # shared helper scripts (not skill-scoped)
└── CONVENTIONS.md        # this file
```

---

## Two-surface model

Every operator-facing capability ships as one of three patterns:

### Pattern A — CLI-wrapper command (Bash-only)

A thin slash command that wraps a `dekspec` CLI verb. No skill exists for these.

- **Use when**: the capability is a CLI verb the operator wants to type as a slash command (`/dekspec:doctor`, `/dekspec:compile`, `/dekspec:validate-artifact`). The CLI does the work; the command is the ergonomic shortcut.
- **Frontmatter**: `allowed-tools: Bash(dekspec <verb>:*)`; body is 1–5 steps that pass `$ARGUMENTS` through.
- **Cost**: 1 file (`commands/<name>.md`).

**Pattern-A members today:**
| Command | Wraps |
|---|---|
| `/compile` | `dekspec compile` |
| `/doctor` | `dekspec doctor` + inlined fidelity-audit body (hybrid; see Pattern C exception) |
| `/graph-export` | `dekspec graph export` |
| `/man` | Renders `docs/dekspec-overview.md` (no CLI verb; doc-render pattern) |
| `/migrate` | `dekspec migrate` + inlined advisory walker (hybrid; see Pattern C exception) |
| `/validate-artifact` | `dekspec validate` |

**Retired commands** (functionality folded into the table above):
- `/basic-audit` (linkage-only audit) — folded into `/doctor` Stage 1, which runs `dekspec doctor` (schema validate + linkage + drift in one pass). Retired v0.98.0.
- `/doctor-fidelity` (T/D/L fidelity body) — inlined into `/doctor` Stage 2. Retired v0.98.0.
- `/validate` — renamed to `/validate-artifact` for clarity vs the broader `/doctor` graph audit. Renamed v0.98.0.
- `/upgrade` — removed once the ADR-032 deprecation window elapsed (ADR-034 killed the in-CLI acquisition model). Acquire out-of-band (`pipx`/pip-from-git + `claude plugin update`) and reconcile via `dekspec sync`.
- `/run-coding-session` — renamed to `/orchestrate-coding-session` in INT-098; the stray `run-coding-session.md` file (which had no command frontmatter and only carried INT-123's IB-lifecycle wiring docs) was deleted and its wiring relocated into `orchestrate-coding-session.md`. Retired ds-jhbw.

### Pattern B — Skill-only authoring

Heavy, stateful expertise for authoring an artifact (an AE, ADR, IC, WS, IB, Intent, Mission, SP, SV, Constitution, GGC entry, eval suite, test suite, bead set). No slash command wrapper. The model invokes the skill by description-match when the operator describes intent in natural language (`"write an ADR for X"` → `write-adr` skill).

- **Use when**: the capability is multi-mode authoring with field-by-field elicitation, role passes, audits, and promotion ceremonies — too much body for a command file, and operators tend to invoke by intent rather than slash.
- **Frontmatter**: `name`, `description`, `mode: lite|full`, `model`, `reasoning_effort: max|high`, `disable-model-invocation`, `allowed-tools` (typically `Read Write Edit Grep Glob Bash Agent`). See [`docs/dekspec-skill-flag-defaults.md`](../../docs/dekspec-skill-flag-defaults.md) for class defaults.
- **Cost**: 1 skill dir (`skills/<name>/SKILL.md`).

**Pattern-B members today:**
- Authoring (lite): `write-adr`, `write-ae`, `write-constitution`, `write-evals`, `write-ggc`, `write-intent`, `write-sp`, `write-sv`, `write-tests`
- Authoring (deep, mode=full): `write-ibs`, `write-ic`, `write-mission`, `write-ws`
- Utility authoring: `write-code-beads`

### Pattern C — Command + skill pair (typeable + heavy logic)

Heavy logic lives in a skill; a thin command wraps it for typeable invocation. The command's `allowed-tools` is `Skill`; its body is a 2-step stub that forwards `$ARGUMENTS` to the skill via the Skill tool.

- **Use when**: the skill has enough body to warrant skill-only ergonomics, AND operators routinely want a typeable handle (onboarding, dispatch, recovery, lifecycle walkers).
- **Cost**: 2 files (`commands/<name>.md` + `skills/<name>/SKILL.md`).

**Pattern-C members today:**
| Command | Skill | Purpose |
|---|---|---|
| `/archeology` | `archeology` | brownfield spec-gap recovery |
| `/brownfield-ingest` | `brownfield-ingest` | classify inherited markdown into artifact slots |
| `/orchestrate-coding-session` | `orchestrate-coding-session` | dispatch parallel coding session over a bead set |
| `/orchestrate-intent` | `orchestrate-intent` | guided Intent lifecycle walker |
| `/using-dekspec` | `using-dekspec` | onboarding entry point (init + spec-mode + catalog) |

### Pattern C exceptions — hybrid commands

Two slash commands run a CLI verb AND invoke a skill body, combining Patterns A and C:

- **`/doctor`** — Stage 1 runs `dekspec doctor` (Bash; schema validate + linkage + drift); Stage 2 executes the inlined AE-aware T/D/L fidelity audit body. Single full-audit surface; subsumed the legacy `/fidelity-audit` command in B11, the `/doctor-fidelity` skill in v0.98.0, and `/basic-audit` (linkage-only) in v0.98.0.
- **`/migrate`** — Stage 1 runs `dekspec migrate` (Bash); Stage 2 walks the advisory queue interactively (inlined walker body using `${CLAUDE_PLUGIN_ROOT}/scripts/migrate/advisory_io.py` helpers). Single migration surface; subsumed the legacy `/migrate-artifact-format` skill in B2.

When a capability needs both CLI execution AND in-loop Claude reasoning, expand the command body to dispatch both — don't fan out across separately-invocable surfaces.

---

## Skill-only authoring rationale

The dozen `write-*` skills (Pattern B) are deliberately not wrapped in slash commands. The convention emerged from observing:

- Operators don't type `/write-ae` — they say "write an AE for X" and the harness picks the skill.
- Each `write-*` skill has 5–10 modes (`--audit`, `--review`, `--accept`, `--lock`, `--unlock`, `--revise`, `--teaching`, `--resync`, `--dry-run`, `--amend`, `--analyze`). Typing the right flag is harder than describing intent.
- A command wrapper adds a maintenance surface (2 files instead of 1) without ergonomic gain.

`write-code-beads` historically had a command wrapper from the INT-098 rename alias (`/create-beads` → `/write-code-beads`). The wrapper was dropped in B1 (2026-05-27) to restore the convention. The skill remains discoverable; bare `/write-code-beads` (or `"create beads from IB-NNN"`) still resolves to it.

---

## When adding a new capability

Decision tree:

1. **Does the CLI already do it?** → Pattern A. One command file.
2. **Is it artifact authoring (one of the `write-*` family)?** → Pattern B. One skill dir.
3. **Is it operator-driven orchestration, recovery, or onboarding that benefits from a typeable handle?** → Pattern C. Command + skill pair.
4. **Does it need both CLI execution AND in-loop reasoning?** → Pattern C exception (hybrid). One command file with `allowed-tools` widened, body runs Bash + invokes Skill (or inlines the reasoning body).

Avoid: skill-only orchestration (no typeable handle) — operators don't discover it. Avoid: command-only orchestration that duplicates a skill body (drift risk; ergonomics asymmetric). Avoid: skill that exists solely to be invoked by a command (just inline into the command body unless it's >100 lines OR shared by ≥2 commands).

---

## Cross-references

- [`docs/dekspec-skill-flag-defaults.md`](../../docs/dekspec-skill-flag-defaults.md) — canonical frontmatter defaults per skill class (authoring / dispatch / recovery / audit / utility).
- [`plugins/dekspec/skills/_lib/help_mode_template.md`](skills/_lib/help_mode_template.md) — canonical Help Mode rendering contract.
- [`dekspec/architecture-elements/AE-006-skills-library.md`](../../dekspec/architecture-elements/AE-006-skills-library.md) — system-level architectural spec for the Skills Library.
