# DekTools Plugin

The **optional operator toolkit** for [DekSpec](https://github.com/Dektora/dekspec) — the helper tools you reach for *around* the spec machine, shipped as a sibling Claude Code plugin rather than bolted onto the core one.

The boundary is set by **[ADR-047](https://github.com/Dektora/dekspec/blob/main/dekspec/adrs/ADR-047-core-toolkit-plugin-boundary.md)** and its litmus test: *remove the tool — can you still run the primary greenfield spec→code→COMPLETE flow?* If yes it belongs here; if no it stays in `dekspec`.

## What this plugin provides

| Category | Tools |
|---|---|
| **Project management** | `prj-mgr` — `br`-backed project boards; the issue-side pull surface (ADR-052). |
| **Code-quality & security review** | `audit-codebase`, `analyze-module-depth`, `orchestrate-module-deepening`, `security-review`. |
| **Brownfield onboarding** | `brownfield-ingest`, `archeology`. |
| **Handoff** | `rotation-handoff`. |
| **Brainstorming** | `interview-me`. |
| **Troubleshoot** | `coding-session-forensics`, `debug-testfail`, `diagnose-bug`. |
| **Explore** | `prototype`, `spike`. |
| **Issue-tracker glue** | `write-issue-beads`. |
| **Setup** | `setup-dektools` — the re-runnable à-la-carte selector. |

`tool-catalog.json` at the plugin root is the **authoritative roster**. Each entry carries a `dependency_tier`, and both the dependency guard and the à-la-carte selector read it — so the catalog, not this table, is what the code obeys.

## The dependency guard — per tool, not per plugin

DekTools is DekSpec-native by default, but **nativeness is measured per tool**. `tool-catalog.json` declares one of two tiers for every tool, and the guard keys on it:

| Tier | Meaning | Guard behaviour when `dekspec` is absent |
|---|---|---|
| `dekspec-required` | Imports the engine, reads the IR, or keys off the audit/review model. Meaningless without DekSpec. **The default**, and correct for most of the suite. | **Refuses**, with a remediation message (exit 1). |
| `dekspec-enhanced` | Zero hard coupling; delivers its full primary value standalone and enriches when DekSpec is detected. | **Stays silent** — the tool runs (exit 0). |

**`prj-mgr` is the only tool holding `dekspec-enhanced` today.** It reads the `br` tracker and a `docs/prj-mgr/` board tree, imports nothing the engine owns, and is fully usable in a repo with no DekSpec at all.

ADR-047 explicitly **withdrew** the blanket "DekTools requires DekSpec" rule: applied to a genuinely uncoupled tool it manufactures a dependency that does not exist, and teaches users that the guard's message cannot be trusted. The guard keeps its teeth exactly where a dependency is real.

Mechanics:

- **`scripts/dependency_guard.py <tool-name>`** is the per-tool gate. Exit `0` allowed · `1` guard fired · `2` usage error. An **uncatalogued** tool is treated as `dekspec-required` — ADR-047's declared default, and the safe direction to be wrong in. An unreadable catalog lands every tool on that default rather than silently disarming the guard.
- **The probe is `dekspec` on PATH.** ADR-047 settles this as the portable signal across all six harnesses, since plugin-dependency semantics vary by host and most hosts have no such declaration at all. The guard imports nothing DekSpec owns — it runs precisely when the engine is missing.
- **`hooks/hooks.json` registers a `SessionStart` preflight** (`hooks-handlers/session-start-guard.py`). With the engine absent it names the tools that will refuse, names the ones still fully usable, and prints the install remediation — then **exits 0**. It is loud but never fatal: a nonzero `SessionStart` hook breaks the whole session, which is the wrong trade for an operator who installed DekTools only to read a project board. Set `DEKTOOLS_HOOK_DISABLE=1` to silence it.

The claim behind `dekspec-enhanced` is enforced, not asserted: `tests/test_dektools_dependency_guard.py` audits every such tool's imports, so the tier cannot rot into a lie the next time someone adds an engine import.

## Installation

DekTools installs **alongside** `dekspec`, from the same marketplace:

```bash
claude plugin marketplace add Dektora/dekspec-public
claude plugin install dekspec@dekspec      # the spec machine
claude plugin install dektools@dekspec     # the optional toolkit
```

`dekspec` alone is a complete, self-sufficient system — core has no dependency on the toolkit and runs the full `author → decompose → audit → review → orchestrate → code → COMPLETE` flow standalone. Install `dektools` when you want the helpers.

For the `dekspec-required` majority you also need the engine on PATH:

```bash
pipx install "git+https://github.com/Dektora/dekspec-public.git@main"
```

Installing `dektools` **without** `dekspec` is supported but narrow: `prj-mgr` works, every other tool refuses with the remediation above.

On non-Claude hosts (`codex` · `antigravity` · `cursor` · `copilot` · `pi`) there is no marketplace — `dekspec install --platform <host>` emits the per-host tree, and the à-la-carte selection below decides which DekTools trees it emits.

## À la carte — nothing is on by default

ADR-047 makes DekTools a suite you choose from. Because a plugin installs all-or-nothing at the harness level, DekTools manages selection itself: the catalog above plus a **persisted per-installation enabled-set** stored with the repo's DekSpec config, so the selection travels with the project.

The enabled-set is the `dektools.enabled` key in `.dekspec/config.yaml`:

```bash
dekspec config set dektools.enabled prj-mgr,spike   # comma-separated
dekspec config get dektools.enabled                 # → prj-mgr,spike
dekspec install --platform claude                   # emits exactly that subset
```

- **Empty by default.** An unset key and an empty list mean the same thing, and neither is an error.
- **Unknown names are rejected at write time**, naming the offender and listing the valid tools — validated against `tool-catalog.json`. When the catalog is unresolvable (a pip-installed engine carries no plugin tree) validation is skipped rather than rejecting every name.
- **Disabling is just a shorter list.** Re-run `dekspec install` and the deselected tool's emitted surface is removed.
- **Removal is non-destructive.** Pruning is scoped to the exact paths an emit would have written for that tool: core skills and unrelated files in the host tree are never touched.
- **Every host honors the same selection** — `claude`, `codex`, `antigravity`, `cursor`, `copilot`, `pi`.
- **The emit path is what enforces it today.** `dekspec install --platform <host>` writes only the enabled subset; `claude plugin install dektools@dekspec` installs the plugin whole, because the harness has no partial-install semantics — which is the reason the selection lives here at all.
- **Core self-sufficiency is the load-bearing negative.** With nothing enabled, or with the DekTools tree absent entirely, `dekspec install` produces byte-for-byte the file set it produced before this feature existed.

`setup-dektools` is the interactive, re-runnable front end for that key — it walks the catalog and persists the choice, and can be re-run at any time to add or remove tools. The `dekspec config set` form above is the same contract without the interview.

## Layout

```
plugins/dektools/
├── .claude-plugin/plugin.json   # plugin manifest
├── tool-catalog.json            # authoritative roster + dependency_tier per tool
├── skills/                      # the toolkit skills
├── commands/                    # slash-command wrappers
├── hooks/hooks.json             # SessionStart dependency preflight
├── hooks-handlers/              # the preflight script
├── scripts/dependency_guard.py  # per-tool tier gate
└── README.md
```

## Versioning

DekTools lives in the DekSpec monorepo and releases in **lockstep** with it (ADR-047, Open Issue #2): one release pipeline, no cross-repo sync tax. `scripts/bump-version.py` updates `plugins/dektools/.claude-plugin/plugin.json` alongside the core manifest and the marketplace refs, and `release.yml` asserts that every marketplace entry's `ref` matches `__version__`. See `RELEASING.md` in the library root.
