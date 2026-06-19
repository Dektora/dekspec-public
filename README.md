# DekSpec

[![CI](https://github.com/Dektora/dekspec/actions/workflows/ci.yml/badge.svg)](https://github.com/Dektora/dekspec/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey.svg)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://github.com/Dektora/dekspec/blob/main/.github/workflows/ci.yml)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)](CHANGELOG.md)
[![Spec graph](https://img.shields.io/badge/spec_graph-9_IRs-blue.svg)](#the-nine-ir-types)
[![Audit rules](https://img.shields.io/badge/audit_rules-~30-blue.svg)](#audit-rule-families)

A spec-driven-development framework for AI-augmented engineering. Turns the markdown artifacts your team already writes — ADRs, Architecture Elements, Working Specs, Interface Contracts, Implementation Briefs, Intents, Missions, Domain Glossary, System Vision — into a typed, validated **spec graph** that compiles into enforcement artifacts (contract tests, CI gates, AGENTS.md context).

DekSpec is shipped as a Python library + CLI + Claude Code skills + markdown templates, vendored into consumer repos via a single install script. The current version is **v0.120.0**.

## What's here

| Path | Contents |
|------|----------|
| `tooling/dekspec/` | Python package: Constraint Compiler (parsers + 9 IR schemas + emitters), fidelity audit (~30 audit rules), persistence layer (SQLite-indexed run history), and the `dekspec` CLI. |
| `tooling/dekspec/schemas/` | JSON Schema Draft 2020-12 definitions (YAML) for each artifact type. Shipped as package data; loadable via `importlib.resources`. |
| `plugins/dekspec/skills/` | Claude Code skills (authoring + orchestration): `/write-ae`, `/write-adr`, `/write-ws`, `/write-ic`, `/write-ibs`, `/write-intent`, `/write-mission`, `/write-sv`, `/write-ggc`, `/write-sp`, `/write-evals`, `/write-tests`, `/write-code-beads`, `/exec-coding-session`, `/archeology`, `/brownfield-ingest`, `/orchestrate-intent`, `/using-dekspec`. Ship through the Claude Code plugin marketplace at `Dektora/dekspec`. |
| `plugins/dekspec/commands/` | Slash-command wrappers + CLI mirrors: `/doctor`, `/compile`, `/validate-artifact`, `/migrate`, `/upgrade`, `/graph-export` (CLI verb mirrors); plus Skill-wrapper pairs for `/archeology`, `/brownfield-ingest`, `/exec-coding-session`, `/orchestrate-intent`, `/using-dekspec`. |
| `templates/` | Artifact templates (ADR, AE, WS, IC, IB, Intent, Mission, Vision Note, plus a checklists subdirectory). |
| `docs/` | Methodology docs: `dekspec-operating-guide.md`, `dekspec-quick-reference.md`, `architecture-frameworks-reference.md`, plus the framework's own `architecture.md`. |
| `.beads/` | Project's own bead tracker (`br` CLI; SQLite + JSONL). |

## The nine IR types

Each artifact type has a typed schema + lossy markdown parser + cross-artifact resolution. The parser is deliberately permissive — missing fields surface as `parse_warnings` rather than raising. Schema validation catches the genuinely-malformed.

| ID prefix | Artifact | Layer | Purpose |
|-----------|----------|-------|---------|
| `ADR-NNN` | Architecture Decision Record | L1 | Decisions that shape one or more AEs |
| `AE-NNN`  | Architecture Element | L1 | The system's architectural slices (with subtype: System / Subsystem / Container / Component / Pipeline / Data Model / Cross-Cutting Concern / Platform Concern / Interface Surface / Workflow / Process) |
| `WS-NNN`  | Working Spec | L2 | Behavioral contract: business rules + failure behaviors + interface contracts |
| `IC-NNN`  | Interface Contract | L2 | Provider/Consumer API contracts with parties + capabilities + error semantics |
| `IB-NNN`  | Implementation Brief | L3 | Per-task implementation contract: files-to-modify scope + done-when criteria, references its parent WS + source AEs |
| `INT-NNN` | Intent | (cross-layer) | Captured engineer intent — what change is being made and why, with components_affected (diff-confinement globs) + verification predicate (TESTPASS gate) |
| `MSN-NNN` | Mission | (cross-Intent) | Long-horizon container: outcome, mission verification, out-of-scope contract, flag strategy, rollback plan, kill criteria, Intent queue |
| `DOMAIN-GLOSSARY` | Domain Glossary (singleton) | L0 | Canonical term definitions: term + category + canonical_definition + not_this + code_convention |
| `SYSTEM-VISION` | System Vision (singleton) | L0 | One-paragraph elevator pitch + What this is + Why this exists + What success looks like + What we are NOT building |

## CLI — eleven subcommands

```
dekspec --version
dekspec --help
```

| Command | What it does |
|---------|--------------|
| `dekspec init` | Scaffold a new dekspec/ tree (10 subdirs + 6 index files + AGENTS.md placeholder). Idempotent. |
| `dekspec compile <file>` | Parse one artifact + (optionally) emit IR / contract-test / ci-gate / agents-md. Persists to per-run history. |
| `dekspec validate <file>` | Quick parse-only check, no persistence side effect. Useful for editor integrations + pre-commit hooks. |
| `dekspec audit linkage` | Run all audit rule families (L1-L11 + T-series + D-series). `--fix --apply` auto-applies mechanical fixes for L6/L7/L8 mirror gaps. |
| `dekspec aggregate agents-md` | Walk the SpecGraph and emit a project-wide AGENTS.md with one fragment per artifact (default status filter: LOCKED + ACCEPTED). |
| `dekspec graph export` | Dump every IR as a single JSON document for downstream tooling. |
| `dekspec audit doctor` | Composite health check: vendored-content drift + audit linkage + parse failures, rolled up into a traffic-light summary. The vendored-drift section was previously exposed as a standalone CLI verb (retired INT-098). |
| `dekspec migrate-ir` | Migrate persisted IR JSON files forward through registered schema migrations. Walks `$XDG_DATA_HOME/dekspec/<repo>/runs/**/irs/*.ir.json` and rewrites them through the per-IR migration chain. (Renamed from `dekspec migrate` in v0.50.0 — old name no longer accepted.) |
| `dekspec runs ls/show/reindex/gc` | Inspect compile-run history persisted under `$XDG_DATA_HOME/dekspec/` (SQLite-indexed). `gc` garbage-collects old runs while preserving milestone runs. |
| `dekspec executions ls/show/metrics/tag/amend/link` | Query + annotate the execution-attempt lifecycle DB (the flywheel substrate that DekFactory writes to). Produces first-pass success rate, mean time-to-merge, escalation rate. |

Full per-flag reference: [`docs/cli-reference.md`](docs/cli-reference.md) (also vendored into `dekspec/cli-reference.md` for consumers).

## Audit rule families

The audit engine (`dekspec audit linkage`) runs ~30 distinct rules grouped into four families:

**L-series (linkage integrity):**
- L1 — ADR.related_architecture_elements references resolve
- L3 — WS.related_architecture_elements references resolve
- L4 — IC.parties[].ae_id references resolve
- L5 — IB.spec / source_aes / depends_on references resolve
- L6 — Bidirectional backlinks: when X.linked_artifacts mirrors AE-Y, X also appears in AE-Y's consumers
- L7 — ADR supersession integrity (refs resolve, no self-loop, no cycle, mirror) **+** Intent linkage (L7a linked AEs, L7b components_affected globs resolve)
- L8 — Mission ↔ Intent bidirectional + autonomy ceiling
- L9 — Verification cmd checks resolve to executable scripts
- L10 — Glossary coverage advisory (likely jargon Title-Case phrases not in the Glossary)
- L11 — Mission stale-ACTIVE advisory (>90 days since last modified)
- LX-DUP — Duplicate artifact IDs across the dekspec tree
- LX-PARSE — Parse failures surfaced as findings

**T-series (structural completeness):** T11 (AE boundaries with `— why` clauses), T12 (AE views), T14 (Intent verification), T15 (Intent components_affected), T17 (Mission outcome/verification/rollback), T20/T21 (WS business_rules / failure_behavior), T30/T31 (ADR decision / validation), T40/T41 (IB goal / done_when), plus AE-purpose / AE-responsibilities completeness checks. **Singleton self-consistency** (ds-52p, since v0.40.0): T-GLOSSARY-DUPLICATE, T-GLOSSARY-MISSING-DEFINITION, T-GLOSSARY-DANGLING-ALIAS, T-VISION-MISSING-WHY, T-VISION-INCOMPLETE.

**D-series (content-drift routing):** D17 (no measurable targets in AE prose — route to WS), D18 (no decision rationale in AE prose — route to ADR), D19/D20 (same as D17/D18 but for Intent prose). **Symmetric coverage on WS/IC/IB** (ds-52p, since v0.40.0): D-15a (WS rationale → ADR), D-15b (IC rationale → ADR), D-15c (IB rationale → ADR), D-15d (IC numeric → WS).

### Schema validation vs. linkage rules — division of labor (ds-52p, D-14)

The audit engine is intentionally split between two enforcement layers:

- **Schema validation** runs at parse time inside the Constraint Compiler. It catches structural shape errors: required fields missing, enums out of range, additionalProperties violations, type mismatches. Audit rules T10 / T13 / T15 / T16 conceptually live here — they're enforced by `jsonschema` against the IR shape, not by `linkage.py`. If you change a required field's shape, the parser fails to validate and the artifact never reaches the audit.
- **Linkage rules** (everything in `linkage.py`) run against the *graph* — cross-artifact references, content-drift heuristics, glossary coverage, vision completeness, supersession integrity. Linkage rules read parsed IRs but never re-parse markdown.

Practical implication: when adding a new constraint, decide first whether it's schema-shape (add to the schema YAML) or graph-relational (add a rule to `linkage.py`). Don't put graph relationships in schemas (jsonschema can't express them) and don't put shape rules in `linkage.py` (the IR should never reach the engine in an invalid shape).

### Audit-rule families: what does NOT live here (ds-52p, D-42 + D-43)

- **Checklists under `templates/checklists/`** (eval-quality, security) are IB-author-time guidance only. They are not enforced by the audit engine; they are referenced by `/write-ibs` and `/write-evals` as inline elicitation prompts when authoring an IB / eval set. There is no `T-CHECKLIST-*` rule family.
- **L2 numbering is reserved** for a future "ADR → ADR non-supersession reference" rule. No such check exists today (the existing ADR→ADR linkage is supersession via L7). L2 is intentionally absent from the v1 profile so the gap is explicit rather than hidden.

**Mechanical-fix-eligible rules** (`--fix --apply`):
- L6-BACKLINK — append missing IDs to `Related <Kind>:` line
- L7-ADR-SUPER-MIRROR — add back-pointer to ADR's `*Superseded by:*` line
- L8-MSN-INT-MIRROR — set Intent's `## Mission` value
- L8-INT-MSN-MIRROR — append row to Mission's intent_queue table

## Quick start

### As a framework consumer

Single-command install (installs the Python CLI and the Claude Code plugin at the same version):

```bash
# Run from your project root:
bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec-public/main/scripts/install.sh)
```

Then:

```bash
# Scaffold the dekspec/ tree (first-time only):
dekspec library init

# Health check:
dekspec audit doctor
# → traffic-light summary; exit 0 = clean

# Author your first artifact (in Claude Code):
/write-ae

# Once you have LOCKED + ACCEPTED artifacts, build the AGENTS.md:
dekspec check aggregate agents-md
```

See [Installation](#installation) for pinned versions, manual install paths, and the plugin-only / CLI-only splits.

### Smallest path to a merged one-file change

The shortest governed loop for a single-component, single-file change — the `--lite` track (skips `--analyze` and code-bead decomposition, but still LOCKs):

```bash
# 1. Author a lite Intent (single-component, single-IU, no ADRs/ICs), in Claude Code:
/write-intent --lite "<one-line description of the change>"

# 2. Dispatch the coding session — agents implement the bead in an isolated worktree:
/exec-coding-session

# 3. Land it — merge the IB-aggregate PR and LOCK the Intent:
/land-intent
```

See the `using-dekspec` skill for the full catalog and when to step up to the full (non-lite) lifecycle.

### Working with an existing dekspec tree

```bash
# Audit:
dekspec audit linkage

# Auto-fix mechanical findings:
dekspec audit linkage --fix --apply

# Validate one artifact (no side effects):
dekspec check validate dekspec/architecture-elements/AE-014-formula-engine.md

# Export the full spec graph for downstream tooling:
dekspec dev graph export --pretty --output graph.json

# Health check before commit:
dekspec audit doctor
```

## Installation

### Single-command install (recommended)

Installs the Python CLI + vendored content, then delivers DekSpec for one harness platform (default `claude`):

```bash
# latest release, Claude (default)
bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec-public/main/scripts/install.sh)

# latest release, a specific host
bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec-public/main/scripts/install.sh) --platform pi

# pinned version + host
bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec-public/main/scripts/install.sh) v0.117.0 --platform codex
```

`<host>` ∈ `claude` (default) · `codex` · `antigravity` · `cursor` · `copilot` · `pi`.

The script:
1. Resolves the ref (highest release tag on the public mirror, or the explicit tag you pass).
2. Runs `pipx install "git+https://github.com/Dektora/dekspec-public.git@<ref>"` — pip-from-git, pulling transitive deps from PyPI.
3. Reconciles vendored content against the installed engine (`dekspec library sync`).
4. Delivers for the chosen `--platform`: `claude` → adds the `Dektora/dekspec-public` Claude Code marketplace + installs the `dekspec@dekspec` plugin; every other host → emits the per-host skill/command/hook tree into the current directory via `dekspec install --platform <host>` (the plugin source is fetched from the mirror at the same ref).

Steps 1–3 are host-agnostic. Re-run to upgrade. For `--platform claude`, plugin-vs-CLI drift is reported by `dekspec audit doctor` (the `plugin version` section flags ADVISORY when they disagree).

### Requirements

- `git` — see https://git-scm.com/downloads
- `pipx` — see https://pipx.pypa.io/stable/installation/
- `claude` CLI — see https://docs.claude.com/en/docs/claude-code/cli (only for `--platform claude`)
- `curl`, `bash`, `grep`

### Manual install (split surfaces)

CLI only via pipx (isolated venv):
```bash
pipx install "git+https://github.com/Dektora/dekspec-public.git@v0.120.0"
```

CLI only into a project venv:
```bash
pip install "git+https://github.com/Dektora/dekspec-public.git@v0.120.0"
```

Plugin only (in a Claude Code session OR via the `claude` CLI):
```bash
claude plugin marketplace add Dektora/dekspec-public
claude plugin install dekspec@dekspec
```

### Auth note

DekSpec source is proprietary (the source-of-truth repo is private). Consumers install from the curated public mirror `Dektora/dekspec-public` (ADR-034), which carries only the redistributable surface and needs no auth — the engine via pip-from-git, the plugin via the mirror marketplace.

### What gets vendored

- `skills/` → `.claude/skills/` (recursively, deletions mirrored)
- `templates/` → `dekspec/templates/` (recursively, deletions mirrored)
- `docs/dekspec-operating-guide.md` → `dekspec/dekspec-operating-guide.md`
- `docs/dekspec-quick-reference.md` → `dekspec/dekspec-quick-reference.md`
- `docs/architecture-frameworks-reference.md` → `dekspec/architecture-frameworks-reference.md`
- `docs/architecture.md` → `dekspec/architecture.md`
- `docs/cli-reference.md` → `dekspec/cli-reference.md` (per-flag CLI reference)
- `docs/EXAMPLES.md` → `dekspec/EXAMPLES.md` (Python-API cookbook)
- `docs/amendment-log-types.md` → `dekspec/amendment-log-types.md`
- Writes `.dekspec-version` at the repo root.

Your authored artifacts under `dekspec/architecture-elements/`, `dekspec/adrs/`, `dekspec/working-specs/`, etc. are **not** touched by either install or upgrade.

`dekspec audit doctor` (the doctor's `verify-vendored` section) detects drift between the vendored copy and the installed library.

## Versioning

Semver. Major = breaking changes to schemas, parser output shape, or CLI flags. Minor = additive (new IRs, new emitters, new audit rules, new CLI commands). Patch = bug fixes + clarifications.

Pin a specific version in your consuming repo's `pyproject.toml`. Use `dekspec audit doctor` in CI to detect drift + audit issues + parse failures in one shot.

## Upgrading dekspec in your project

For projects that already have a `dekspec/` tree, vendored content, and a pinned engine version. The install script detects the existing `.dekspec-version` and prints upgrade-aware next-steps; the steps below are what those next-steps expand to.

### Routine upgrade (minor / patch versions)

```bash
# 1. Re-run the install script — picks up the latest tag, reinstalls CLI + plugin at the same version.
bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec-public/main/scripts/install.sh)

# 2. Auto-apply mechanical audit fixes (new bidirectional backlink rules, etc.):
dekspec audit linkage --fix --apply

# 3. Health check:
dekspec audit doctor

# 4. Regenerate the project-wide AGENTS.md:
dekspec check aggregate agents-md

# 5. Commit (single PR per consumer):
git add -A && git commit -m "chore(dekspec): bump to vX.Y.Z"
```

### Major version upgrade

Same as routine, plus schema-migration and breaking-change steps:

```bash
# 1. Reinstall CLI + plugin at the new pinned version:
bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec-public/main/scripts/install.sh) vX.Y.Z

# 2. Migrate persisted IR JSON files forward through registered schema migrations:
dekspec migrate-ir

# 3. Auto-apply mechanical audit fixes:
dekspec audit linkage --fix --apply

# 4. Check the audit for critical findings:
dekspec audit linkage

# 5. Revise affected artifacts per the CHANGELOG migration notes for the new major version.
#    (Critical findings on a major bump usually mean a required field was added or renamed.)

# 6. Health check:
dekspec audit doctor

# 7. Regenerate AGENTS.md:
dekspec check aggregate agents-md

# 8. Commit:
git add -A && git commit -m "chore(dekspec): bump to vX.Y.Z"
```

### Alternative: `dekspec upgrade` CLI

If you already have an older dekspec engine installed, the engine ships a built-in upgrade command that atomically bumps the `pyproject.toml` pin AND re-vendors content from the same version:

```bash
dekspec upgrade 0.41.0    # bumps pin + re-vendors in one shot
pip install -e .          # (or your dependency manager equivalent) — reinstall the new engine
/dekspec-migrate          # (in Claude Code, if schemas changed)
```

Use this when you want a single source-controllable change to `pyproject.toml` rather than running the install script. Use the install script when you want the simplest end-to-end refresh.

### What the upgrade does (and does NOT) touch

| Path | Behavior on upgrade |
|---|---|
| `.claude/skills/` | **Replaced** — `rsync --delete`, mirrors the library's `skills/` |
| `dekspec/templates/` | **Replaced** — `rsync --delete`, mirrors the library's `templates/` |
| `dekspec/<methodology>.md` | **Overwritten** — vendored doc files (operating-guide, quick-reference, architecture, cli-reference, EXAMPLES, amendment-log-types) are replaced wholesale |
| `dekspec/architecture-elements/`, `dekspec/adrs/`, `dekspec/working-specs/`, `dekspec/interface-contracts/`, `dekspec/implementation-briefs/`, etc. | **Not touched** — your authored artifacts are safe |
| `.dekspec-version` | **Updated** to the new version |
| `pyproject.toml` | **Not touched by the install script.** Use `dekspec upgrade X.Y.Z` if you want the pin bumped automatically. |

## Persistence

Each `dekspec compile` invocation logs to `$XDG_DATA_HOME/dekspec/<repo-fingerprint>/runs/<timestamp>-<run-id>/`:

- `manifest.json` — run metadata (trigger, command, dekspec version, artifact + emission counts, exit code, duration_ms).
- `events.jsonl` — structured event stream (parsed, emitted, warned, errored).
- `irs/<id>.ir.json` — per-artifact IR captures.

A SQLite index at `<repo-state-dir>/index.db` indexes every run by `run_id`, `timestamp`, `artifact_id`, `kind`, `exit_code`, `milestone`. Query via `dekspec runs ls --since <date> --until <date> --artifact <id> --exit-code <n>`.

Default retention: 200 runs per repo. Milestone runs are preserved. Rebuild the index from on-disk manifests via `dekspec runs reindex`.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the source → IR → compiled outputs → runtime mental model.

For Python-API usage patterns (load + audit + emit + persistence + vendoring via `dekspec.api`), see [`docs/EXAMPLES.md`](docs/EXAMPLES.md).

Key principle: **DekSpec artifacts are the source specifications; consumers compile them into executable intermediate representations and enforcement artifacts.** Locked artifacts compile into:
- `contract_test.py` — pytest stubs against the IC contract.
- `ci-gate.yml` — GitLab CI job YAML with affected_paths scoping.
- `AGENTS.md` — the worker-context constitution (aggregated per-artifact fragments).

## Governance

This library's scope and lifecycle are defined in the **DekFactory MVP playbook** (currently in `Dektora/dektora/docs/workspace/dekfactory/dekfactory-mvp-playbook.md`; migrates to `Dektora/dekfactory` once that repo is set up).

## Testing

```bash
pip install -e ".[dev]"
pytest -q
```

CI runs `pytest -q` + `ruff check` on Python 3.11 / 3.12 / 3.13 via GitHub Actions on every push to `main` and every PR. Tests bound to a local `/data/projects/dektora2/` fixture auto-skip in CI via `tests/conftest.py`.

## Status

**v0.120.0** is the current release. The Constraint Compiler PoC (v0.2) has matured into a 9-IR framework with ~30 audit rules, 11 CLI subcommands, a public Python API at `dekspec.api`, an execution-attempt lifecycle DB (`dekspec.lifecycle`) that DekFactory (or any executor) writes to, and end-to-end test coverage. See [`CHANGELOG.md`](CHANGELOG.md) for the per-version detail.

Open follow-ons:
- Mission rigor calibration after lived MSN execution data (`ds-zuy`).
- Phase 4 orchestration brain design (`ds-j8x`) — explicitly deferred out of Phase 1–3 scope.
- GitLab migration — when DekSpec moves to the self-hosted GitLab instance (per DekFactory ADR-003), the release workflow ports to `.gitlab-ci.yml`. Until then the curated public mirror (`Dektora/dekspec-public`, ADR-034) is the canonical install surface: `pipx install "git+https://github.com/Dektora/dekspec-public.git@vX.Y.Z"`. Public PyPI publication was removed 2026-05-12; the Cloudsmith index was retired 2026-06 (ADR-034).
