# DekSpec

[![CI](https://github.com/Dektora/dekspec/actions/workflows/ci.yml/badge.svg)](https://github.com/Dektora/dekspec/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Proprietary-lightgrey.svg)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://github.com/Dektora/dekspec/blob/main/.github/workflows/ci.yml)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)](CHANGELOG.md)
[![Spec graph](https://img.shields.io/badge/spec_graph-11_IRs-blue.svg)](#the-eleven-ir-types)
[![Audit rules](https://img.shields.io/badge/audit_rules-~80-blue.svg)](#audit-rule-families)

A five-layer **agentic-(software-)engineering toolkit** for AI-augmented teams — **specification, orchestration, codified rules, human oversight, and observable development**. "Spec" is the layer it's named after, not the whole of it.

- **Specification** — turns the markdown artifacts your team already writes (ADRs, Architecture Elements, Working Specs, Interface Contracts, Implementation Briefs, Intents, Missions, Domain Glossary, System Vision) into a typed, validated **spec graph** that is audited and compiled into check scaffolding and context: Security Profile pre-commit and CI-gate snippets, Interface Contract contract-test stubs and CI jobs for engineers to complete, and advisory AGENTS.md context for agents.
- **Orchestration** — executes accepted Implementation Briefs directly: fresh-context agents in isolated worktrees work from a generated execution context, within bounded attempts, and the work is driven through independent review to merge.
- **Codified rules** — compiles and *audits* your team's decisions and constraints (ADRs, Interface Contracts, the Constitution) at graded severities, instead of trusting prose an agent loads and hopes to follow.
- **Human oversight** — the engineer authorizes each IB's acceptance contract before construction (`dekspec ib accept`); completion requires an independent review verdict from an identity other than the builder; integration is confirmed by the operator, or by the explicit `/implement` request for that request's own delivery (ADR-059). The No Specless Edits guardrail is advisory instruction for the agent, not a runtime gate.
- **Observable development** — completes work only on current evidence (every acceptance condition re-run against the exact content reviewed, recorded in the IB's execution record), and feeds what it learns back into the rules.

DekSpec ships as a Python library and CLI installed from its curated public mirror at a release tag, a Claude Code plugin for its skills, and markdown templates and methodology docs vendored into consumer repos. The current version is **v0.126.0**.

## What's here

| Path | Contents |
|------|----------|
| `tooling/dekspec/` | Python package: Constraint Compiler (parsers + 11 IR schemas + emitters), fidelity audit (~80 audit rules across the L-, T-, and D- families), persistence layer (SQLite-indexed run history), and the `dekspec` CLI. |
| `tooling/dekspec/schemas/` | JSON Schema Draft 2020-12 definitions (YAML) for each artifact type. Shipped as package data; loadable via `importlib.resources`. |
| `tooling/dekspec/roles/` | The six Agent Role Specifications (ADR-061) — one canonical Markdown file per role, shipped as package data and composed into dispatched agents' instructions. Read one with `dekspec resource role <role>`. |
| `plugins/dekspec/skills/` | 25 Claude Code skills — **the spec machine** (ADR-047 core). **Authoring:** `/write-sv`, `/write-constitution`, `/write-ae`, `/write-adr`, `/write-ws`, `/write-ic`, `/write-ibs`, `/write-intent`, `/write-mission`, `/write-glossary`, `/write-corrections`, `/write-sp`, `/write-evals`, `/write-tests`. **Lifecycle + orchestration:** `/spec-intent`, `/implement`, `/orchestrate-coding-session`, `/land-intent`, `/review-ib`, `/review-pr`, `/pr-branch`, `/use-worktrees`, `/write-goal-loop-contract`. **Onboarding:** `/using-dekspec`, `/setup-dekspec`. Ships as the `dekspec` plugin through the Claude Code marketplace at `Dektora/dekspec-public`. |
| `plugins/dekspec/commands/` | Slash-command wrappers + CLI mirrors: `/compile`, `/doctor`, `/graph-export`, `/migrate`, `/validate-artifact`, `/man`, `/send-issue` (CLI verb mirrors); plus Skill-wrapper pairs for `/spec-intent`, `/land-intent`, `/pr-branch`, `/use-worktrees`, `/using-dekspec`, `/setup-dekspec`, `/write-glossary`, `/write-corrections`, `/write-goal-loop-contract`. The user-only skills `/implement` and `/orchestrate-coding-session` (`disable-model-invocation: true`) have no wrapper: each skill is its own slash entry. |
| `plugins/dektools/` | **DekTools** — the optional operator toolkit shipped as a *sibling* plugin (ADR-047): project boards (`/project-board`), code-quality & security review (`/audit-codebase`, `/deepen`, `/security-review`), brownfield onboarding (`/ingest-docs`, `/recover-specs`), handoff (`/handoff`), brainstorming (`/interview-me`), troubleshoot (`/diagnose-session`, `/debug`), explore (`/prototype`, `/spike`), issue-tracker glue (`/project-board`), and the à-la-carte selector (`/setup-dektools`). Installed separately as `dektools@dekspec`; **nothing is on by default**. `tool-catalog.json` is the authoritative roster. See `plugins/dektools/README.md`. |
| `templates/` | Artifact templates (System Vision, Constitution, ADR, AE, WS, IC, IB, Intent, Mission, Domain Glossary, Security Profile, plus a checklists subdirectory). |
| `docs/` | Methodology docs: `dekspec-operating-guide.md`, `dekspec-quick-reference.md`, `architecture-frameworks-reference.md`, plus the framework's own `architecture.md`. |
| `.beads/`, `.beads-dekspec/`, `.beads-issues/` | The project's own `br` trackers (SQLite + JSONL; ADR-052). Governance (`ds-`) and issue (`iss-`) beads are live; the code-bead (`cb-`) workspace is legacy history — construction runs from IBs (ADR-056). |
| `.dekspec/execution/` | IB execution records (`<IB>/record.jsonl`): ownership, plans, attempts, evidence, verdicts, completion. Written by `dekspec ib`; not spec artifacts. |

## The eleven IR types

Each artifact type has a typed schema + lossy markdown parser + cross-artifact resolution. The parser is deliberately permissive — missing fields surface as `parse_warnings` rather than raising. Schema validation catches the genuinely-malformed.

| ID prefix | Artifact | Layer | Purpose |
|-----------|----------|-------|---------|
| `ADR-NNN` | Architecture Decision Record | L1 | Decisions that shape one or more AEs |
| `AE-NNN`  | Architecture Element | L1 | The system's architectural slices (with subtype: System / Subsystem / Container / Component / Pipeline / Data Model / Cross-Cutting Concern / Platform Concern / Interface Surface / Workflow / Process) |
| `WS-NNN`  | Working Spec | L2 | Behavioral contract: business rules + failure behaviors + interface contracts |
| `IC-NNN`  | Interface Contract | L2 | Provider/Consumer API contracts with parties + capabilities + error semantics |
| `IB-NNN`  | Implementation Brief | L3 | The smallest governed work contract, executed directly (no code beads): outcome, obligations by reference, protected surfaces, scope, acceptance conditions, revisable implementation hypothesis, explicit authority policy (ADR-055/056). Parent optional. |
| `INT-NNN` | Intent | (cross-layer) | Optional outcome spanning several IBs — what change is being made and why, with components_affected (diff-confinement globs) + verification predicate (outcome evidence); completes from its IBs via `dekspec intent complete` |
| `MSN-NNN` | Mission | (cross-Intent) | Long-horizon container: outcome, mission verification, out-of-scope contract, flag strategy, rollback plan, kill criteria, Intent queue |
| `DOMAIN-GLOSSARY` | Domain Glossary (singleton) | L0 | Canonical term definitions: term + category + canonical_definition + not_this + code_convention |
| `SYSTEM-VISION` | System Vision (singleton) | L0 | One-paragraph elevator pitch + What this is + Why this exists + What success looks like + What we are NOT building |
| `CONSTITUTION` | Constitution (singleton) | L0 | Non-negotiable operational commitments across eight articles: identity, technology stack, quality standards, architecture principles, development workflow, model configuration, boundaries, amendments |
| `SP-NNN` | Security Profile | L2 | Typed security posture: allowed dataflows, secret stores, authn methods, supply-chain sources, SAST/DAST tools, OWASP coverage; compiles to soft (advisory AGENTS.md context) / mid (pre-commit snippet) / hard (CI-gate snippet) layers |

**Not an IR type: Agent Role Specifications.** DekSpec's six agent roles — specifier, spec reviewer, implementer, code reviewer, verifier, auditor — are library-internal operational contracts in `tooling/dekspec/roles/`, composed into every dispatched agent's instructions (ADR-061). A project never authors, selects or carries one. They replace the retired Context Specifications (`CS-001`…`CS-006`).

## CLI — namespaced commands

```
dekspec --version
dekspec --help
```

The CLI is grouped into namespaces (`dekspec <namespace> <verb>`):

| Namespace | Verbs | What it does |
|-----------|-------|--------------|
| `check` | `validate` · `compile` · `emit` · `aggregate` · `allocate-ids` · `lint-ib` | Single-file parse / compile / validate; emit IR / contract-test / ci-gate / agents-md; aggregate a project-wide AGENTS.md (one fragment per artifact). |
| `audit` | `linkage` · `doctor` · `lock-ready` · `failure-classes` · `relink` | Fidelity audit: run all rule families (`linkage`), composite traffic-light health check (`doctor`), lock-readiness gate, failure-class report, deterministic backlink re-derivation (`relink`). |
| `dev` | `graph` · `ingest` · `recover-specs` | Diagnostics: export the SpecGraph (JSON / DOT / Mermaid), brownfield markdown ingest + classification, code-vs-spec archaeology. |
| `library` | `sync` · `init` · `new-provisional` · `author-target` · `regen-indexes` · `cow-stage` | Consumer-side content ops: scaffold / reconcile the dekspec tree, provisional incubation staging, index regen, copy-on-write write-guard. |
| `exec` | `session` · `runs` · `config` | Session tracking, compile-run history (SQLite-indexed), per-repo `.dekspec/config.yaml`. |
| `migrate` | — | Full upgrade pipeline: verify vendored drift → migrate-ir → migrate-artifacts. |
| `resource` | — | Resolve a wheel-vendored asset (template / methodology doc) to a path or content. |
| `install` | — | Emit the per-host skill / command / hook tree for a harness platform. |
| `slices` | — | Discover structural slices of a Python repo (LLM-free). |
| `ib` | `new` · `lint` · `propose` · `accept` · `baseline` · `amend` · `context` · `start` · `plan` · `task` · `attempt` · `verify` · `review` · `gate` · `complete` · `status` · `block` · `unblock` · `ready` · `import-beads` · `adopt` | Execute an Implementation Brief directly (ADR-055–057): authorize, generate context, run within bounded attempts, verify, record an independent verdict, complete on evidence. |
| `delivery` | `verify` · `check` | Integrated verification and the landing gate at the exact branch head (ADR-058). |
| `intent` | `verify` · `review` · `complete` | Intent outcome evidence and completion from its child IBs. |

(`repo` remains a one-release deprecated alias for `library`.)

Full per-flag reference: [`docs/cli-reference.md`](docs/cli-reference.md) (also vendored into `dekspec/cli-reference.md` for consumers).

## Audit rule families

The audit engine (`dekspec audit linkage`) runs ~80 distinct rules grouped into the L- (linkage integrity), T- (structural completeness), and D- (content-drift routing) families:

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

**T-series (structural completeness):** T11 (AE boundaries with `— why` clauses), T12 (AE views), T14 (Intent verification), T15 (Intent components_affected), T17 (Mission outcome/verification/rollback), T20/T21 (WS business_rules / failure_behavior), T30/T31 (ADR decision / validation), T40/T41 (IB goal / done_when), T-IB-* (IB as an executable contract: explicit authority policy, complete contract, resolvable obligations, `COMPLETE` only with a completion record), plus AE-purpose / AE-responsibilities completeness checks. **Singleton self-consistency** (ds-52p, since v0.40.0): T-GLOSSARY-DUPLICATE, T-GLOSSARY-MISSING-DEFINITION, T-GLOSSARY-DANGLING-ALIAS, T-VISION-MISSING-WHY, T-VISION-INCOMPLETE.

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
dekspec init

# Health check:
dekspec doctor
# → traffic-light summary; exit 0 = clean

# Author your first artifact (in Claude Code):
/write-ae

# Once you have LOCKED + ACCEPTED artifacts, fill AGENTS.md's DekSpec-owned region
# (everything outside `<!-- dekspec:agents-md begin/end -->` stays yours):
dekspec aggregate agents-md
```

See [Installation](#installation) for pinned versions, manual install paths, and the plugin-only / CLI-only splits.

### Shortest path to a merged change

The governed loop for a bounded change — one Implementation Brief, no parent artifact required (ADR-056):

```bash
# 1. Author the IB, in Claude Code (outcome, obligations by reference, scope, acceptance):
/write-ibs "<one-line description of the change>"

# 2. Execute it — the agent works from the generated context in an isolated worktree,
#    investigates, plans, builds, and records evidence:
/orchestrate-coding-session

# 3. Review and land — an independent verdict per IB, evidence-backed completion,
#    the delivery gate, then the operator-confirmed merge:
/review-pr
/land-intent
```

Larger work adds only what it needs: an Intent (`/write-intent`) for an outcome spanning several IBs, a Working Spec, ADR or Interface Contract when the change alters behavior, a decision or a contract. `dekspec ib ready` lists the accepted IBs ready to execute.

See the `using-dekspec` skill for the full catalog and the interactive lifecycle commands.

### Working with an existing dekspec tree

```bash
# Audit:
dekspec audit linkage

# Auto-fix mechanical findings:
dekspec audit linkage --fix --apply

# Validate one artifact (no side effects):
dekspec validate dekspec/architecture-elements/AE-014-formula-engine.md

# Export the full spec graph for downstream tooling:
dekspec graph export --pretty --output graph.json

# Health check before commit:
dekspec doctor
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
3. Reconciles vendored content against the installed engine (`dekspec sync`).
4. Delivers for the chosen `--platform`: `claude` → adds the `Dektora/dekspec-public` Claude Code marketplace + installs the `dekspec@dekspec` plugin; every other host → emits the per-host skill/command/hook tree into the current directory via `dekspec install --platform <host>` (the plugin source is fetched from the mirror at the same ref).

Steps 1–3 are host-agnostic. Re-run to upgrade. For `--platform claude`, plugin-vs-CLI drift is reported by `dekspec doctor` (the `plugin version` section flags ADVISORY when they disagree).

### Requirements

- `git` — see https://git-scm.com/downloads
- `pipx` — see https://pipx.pypa.io/stable/installation/
- `claude` CLI — see https://docs.claude.com/en/docs/claude-code/cli (only for `--platform claude`)
- `curl`, `bash`, `grep`

### Manual install (split surfaces)

CLI only via pipx (isolated venv):
```bash
pipx install "git+https://github.com/Dektora/dekspec-public.git@v0.126.0"
```

CLI only into a project venv:
```bash
pip install "git+https://github.com/Dektora/dekspec-public.git@v0.126.0"
```

Plugin only (in a Claude Code session OR via the `claude` CLI):
```bash
claude plugin marketplace add Dektora/dekspec-public
claude plugin install dekspec@dekspec
```

### DekTools — the optional operator toolkit (second plugin)

DekSpec ships **two** plugins from the one marketplace. `dekspec` is the spec machine and is self-sufficient — it runs the whole `author → audit → execute → verify → review → COMPLETE` flow with nothing else installed. **DekTools** (`dektools`) is the optional sibling holding the helper tools you reach for *around* that machine: project boards, code-quality and security review, brownfield onboarding, handoff, troubleshooting, exploration, and issue-tracker glue (**ADR-047**).

`scripts/install.sh` installs the core plugin only. Add the toolkit deliberately:

```bash
# DekSpec alone — the default, and a complete system
claude plugin marketplace add Dektora/dekspec-public
claude plugin install dekspec@dekspec

# DekSpec + DekTools — add the helpers
claude plugin install dektools@dekspec
```

The marketplace plugin registers **setup only**. Say
`/dektools:setup-dektools enable debugging and handoff`; setup emits the selected
repository-local skills. With zero optional tools, setup remains discoverable.
The wheel contains the same corpus for `dekspec install --platform HOST`.

Selection persists in `.dekspec/config.yaml`. Installation tracks owned hashes,
preserves modified/unowned files and reports repair conflicts. Reload the host
after selection or plugin changes. Old selections migrate without retaining
legacy skill aliases. Project-board and several analysis/exploration tools work
standalone; core-backed capabilities report missing prerequisites explicitly.

See [DekTools installation and tool catalog](plugins/dektools/README.md) for
purposes, requirements, supported scanners and recovery. Core `/implement` owns
autonomous ready-work execution; the optional toolkit does not provide a builder.

### Native Windows (PowerShell / cmd)

The `bash <(curl …)` one-liner does **not** run in native Windows PowerShell/cmd (no `bash`, no process substitution). Use the portable `pipx` sequence — identical to the Linux steps:

```powershell
py -m pipx install --force "git+https://github.com/Dektora/dekspec-public.git@v0.126.0"
dekspec dependencies install br     # user-scoped, no admin — downloads + checksum-verifies the pinned br
dekspec sync                        # reconcile vendored content + .dekspec-version
dekspec install --platform codex    # per-host tree; --platform is on `dekspec install`, NOT on pipx
```

- **`br` (beads-rust) is a required dependency.** `dekspec dependencies install br` acquires the pinned official release for your OS/arch (native Windows included), verifies its SHA-256, and installs it into `%USERPROFILE%\.local\bin` — no Rust/Cargo, WSL, Bash, or admin. `dekspec init` will offer to do this for you (or run `dekspec init --install-deps`). Ensure `%USERPROFILE%\.local\bin` is on PATH.
- **Use `py -m pipx`, not bare `pipx`.** The `py` launcher is already on PATH and runs pipx as a module, so it works even when the pipx shim directory isn't on PATH.
- **Bare `pipx` not found?** That's a host PATH-inheritance issue, not a DekSpec one: `py -m pipx ensurepath` adds pipx's BIN dir to your user PATH, but an **already-running shell/session (including a Codex process) won't inherit it until you restart it** — a live process captures its environment at launch. Restart the terminal, or just keep using `py -m pipx`.
- **`--platform` belongs on `dekspec install`**, never on `pipx install`.
- No `PYTHONUTF8=1` workaround is needed as of v0.121.2 (the CLI reconfigures its console to UTF-8 at startup).

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

`dekspec doctor` (the doctor's `verify-vendored` section) detects drift between the vendored copy and the installed library.

## Versioning

Semver. Major = breaking changes to schemas, parser output shape, or CLI flags. Minor = additive (new IRs, new emitters, new audit rules, new CLI commands). Patch = bug fixes + clarifications.

Pin a specific version in your consuming repo's `pyproject.toml`. Use `dekspec doctor` in CI to detect drift + audit issues + parse failures in one shot.

## Upgrading dekspec in your project

For projects that already have a `dekspec/` tree, vendored content, and a pinned engine version. The install script detects the existing `.dekspec-version` and prints upgrade-aware next-steps; the steps below are what those next-steps expand to.

### Routine upgrade (minor / patch versions)

```bash
# 1. Re-run the install script — picks up the latest tag, reinstalls CLI + plugin at the same version.
bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec-public/main/scripts/install.sh)

# 2. Auto-apply mechanical audit fixes (new bidirectional backlink rules, etc.):
dekspec audit linkage --fix --apply

# 3. Health check:
dekspec doctor

# 4. Regenerate AGENTS.md's DekSpec-owned region. The first time after upgrading
#    past the whole-file generator, the old file is refused as a legacy layout:
#    preview the migration, then migrate (content after its last fragment is kept):
dekspec aggregate agents-md --migrate --dry-run   # only if the plain command asks for it
dekspec aggregate agents-md --migrate             # only if the plain command asks for it
dekspec aggregate agents-md
dekspec aggregate agents-md --check               # verdict: current

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
dekspec doctor

# 7. Regenerate AGENTS.md's DekSpec-owned region (`--migrate` once for a legacy file, as above):
dekspec aggregate agents-md

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

Key principle: **DekSpec artifacts are the source specifications; the compiler lowers them into IR and enforcement artifacts, and the execution engine carries out Implementation Briefs against them and proves completion.** Accepted and locked artifacts compile into:
- `contract_test.py` — pytest stubs against the IC contract; every test starts as `pytest.skip` until an engineer writes the assertion, so it enforces nothing on its own.
- `ci-gate.yml` — GitLab CI job YAML with affected_paths scoping that runs those tests.
- Security Profile pre-commit and CI-gate snippets (`dekspec emit security-profile`) — real checks once the consumer wires them into its config.
- `AGENTS.md` — advisory worker context aggregated from the governing core (Constitution, Security Profile, Vision, Glossary, AE, ADR, IC, WS); agents read it, nothing executes it. Work items are excluded; an agent gets its IB's obligations from `dekspec ib context`.

The gates that are actually executed are the engine's: the IB acceptance baseline, `dekspec ib verify`, evidence-backed `dekspec ib complete`, and `dekspec delivery check` at the landing head.

## Governance

This library's scope and lifecycle are defined in the **DekFactory MVP playbook** (currently in `Dektora/dektora/docs/workspace/dekfactory/dekfactory-mvp-playbook.md`; migrates to `Dektora/dekfactory` once that repo is set up).

## Testing

```bash
pip install -e ".[dev]"
pytest -q
```

CI runs `pytest -q` + `ruff check` on Python 3.11 / 3.12 / 3.13 via GitHub Actions on every push to `main` and every PR. Tests bound to a local `/data/projects/dektora2/` fixture auto-skip in CI via `tests/conftest.py`.

## Status

**v0.126.0** is the current release. The Constraint Compiler PoC (v0.2) has matured into an 11-IR, five-layer agentic-engineering toolkit with ~80 audit rules, a namespaced CLI, a public Python API at `dekspec.api`, an Execution & Evidence Engine (`dekspec ib` / `dekspec delivery` / `dekspec intent`; ADR-055 – ADR-058) that executes Implementation Briefs and completes them only on evidence, and end-to-end test coverage. See [`CHANGELOG.md`](CHANGELOG.md) for the per-version detail.

Open follow-ons:
- GitLab migration — when DekSpec moves to the self-hosted GitLab instance (per DekFactory ADR-003), the release workflow ports to `.gitlab-ci.yml`. Until then the curated public mirror (`Dektora/dekspec-public`, ADR-034) is the canonical install surface: `pipx install "git+https://github.com/Dektora/dekspec-public.git@vX.Y.Z"`. Public PyPI publication was removed 2026-05-12; the Cloudsmith index was retired 2026-06 (ADR-034).
