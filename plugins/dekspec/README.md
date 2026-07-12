# DekSpec Plugin

Claude Code plugin for the [DekSpec](https://github.com/Dektora/dekspec) Spec-Driven Development methodology.

## What this plugin provides

| Surface | Description |
|---|---|
| **Slash commands** | Ergonomic wrappers around the `dekspec` CLI: `/dekspec:doctor`, `/dekspec:compile`, `/dekspec:graph-export`, `/dekspec:migrate`, `/dekspec:validate-artifact`, `/dekspec:man` (overview), `/dekspec:send-issue` (file a classified GitHub issue against `Dektora/dekspec` with operator-confirmed preview). |
| **Authoring agents** | Schema-aware subagents for each artifact type: `ae-author`, `adr-author`, `ic-author`, `ws-author`, `intent-author`, `ib-author`, `mission-author`. Each reads the vendored template, runs a Q&A flow, and produces a conformant artifact. |
| **Hooks** | Background audit/drift detection that fires on file edits and at session end. Surfaces problems inline without requiring manual `dekspec doctor` runs. |

## Architecture: plugin complements the CLI

This plugin **does not replace** the CLI. It assumes the `dekspec` Python CLI is installed (`pipx install "git+https://github.com/Dektora/dekspec-public.git@vX.Y.Z"` from the curated public mirror, ADR-034). Templates and methodology docs are bundled inside the wheel since v0.91.0 and resolved at runtime via `dekspec resource template <name>` / `dekspec resource doc <name>`; consumer-fs copies under `dekspec/templates/` and `dekspec/<doc>.md` override the wheel fallback when present.

The plugin then layers ergonomic surface on top. If the plugin is missing or out of date, the consumer workflow still works via the CLI directly — audits remain reproducible because schemas live with the consumer's artifacts.

See [ADR-002 (proprietary git-URL distribution)](https://github.com/Dektora/dekspec/blob/main/dekspec/adrs/ADR-002-proprietary-git-url-distribution.md) and `docs/architecture.md` for the full distribution rationale.

## Installation

First, install the `dekspec` Python engine (the plugin drives it) from the curated public mirror (ADR-034). `@main` → latest; pin a release with `@vX.Y.Z`:

```bash
pipx install "git+https://github.com/Dektora/dekspec-public.git@main"
```

(pip-from-git pulls transitive deps from PyPI by default — no package index to configure.)

Then, from a consumer repo that already has dekspec vendored:

```bash
# Add the dekspec marketplace
claude plugin marketplace add Dektora/dekspec-public

# Install the plugin
claude plugin install dekspec@dekspec
```

(Or paste the equivalent `/plugin marketplace add Dektora/dekspec-public` and `/plugin install dekspec@dekspec` into an interactive Claude Code session.)

The plugin version is pinned to the dekspec library version — installing the plugin at `v0.40.1` matches the library at `v0.40.1`. To upgrade, run the standard flow **in order** (plugin last): re-acquire the engine (`pipx install dekspec==X.Y.Z`), reconcile vendored content with `dekspec sync`, then `claude plugin update dekspec@dekspec`. The one-command `scripts/install.sh` does all three. (The legacy one-shot `dekspec repo upgrade` acquisition verb was removed once the ADR-032 deprecation window elapsed — ADR-034 killed the in-CLI acquisition model; reconcile via `dekspec sync`.)

## Layout

```
plugins/dekspec/
├── .claude-plugin/plugin.json     # plugin manifest
├── commands/                       # slash commands (CLI wrappers)
├── agents/                         # authoring subagents
├── hooks/                          # hook declarations
├── hooks-handlers/                 # hook executor scripts
└── README.md
```

## Versioning

The plugin version travels with the library version in lockstep. `scripts/bump-version.py` updates both. See `RELEASING.md` in the library root for the full release flow.
