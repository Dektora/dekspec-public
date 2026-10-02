# DekSpec Architecture

## Purpose

DekSpec is the shared governance library for Dektora projects. It provides:

- **Templates** for structured artifacts (ADR, Working Spec, Interface Contract, NFR, Architecture Element, Implementation Brief, Intent, Mission, vision note).
- **Skills** for authoring and auditing those artifacts (`/write-adr`, `/write-ws`, etc.).
- **The Constraint Compiler** that mechanically transforms ACCEPTED and LOCKED artifacts into downstream representations: agent context (advisory), test and CI scaffolds, and pre-commit/CI snippets that enforce only where a repository installs them.
- **The fidelity audit** that verifies the artifact graph is consistent.
- **The Execution & Evidence Engine** (`dekspec ib`, `dekspec delivery`, `dekspec intent`) that executes an accepted Implementation Brief directly, keeps its execution record, and records completion only on current evidence (ADR-056 – ADR-058, AE-011).
- **The methodology** (operating guide, quick reference, architecture-frameworks reference).

Consuming repos (`Dektora/dektora`, `Dektora/dekfactory`, future Dektora projects) depend on DekSpec as a Python package. `scripts/install.sh` installs the engine, then `dekspec sync` vendors its templates and methodology docs from the installed wheel; skills, commands, agents and hooks are never vendored — they reach Claude Code through the `dekspec` plugin marketplace (AE-006, AE-008) and other hosts through `dekspec install --platform` (ADR-045).

## Mental model — source → IR → compiled outputs → runtime

A **compilable spec** is a specification written with enough structure that software, agents, or tooling can reliably turn it into downstream artifacts — tests, rules, validation steps, implementation plans. An **intermediate representation (IR)** is the normalized internal form those tools use to reason about, validate, transform, and lower the spec into code or enforcement logic. The compiler analogy is genuine, not metaphorical: the system does not go directly from natural language to code, but through layers — request → normalized artifact set → plan/constraint IR → execution → verification → merge gates — the way a real compiler separates parsing, analysis, optimization, and code generation.

**DekSpec artifacts are the source specifications; the Constraint Compiler lowers them into IR and enforcement artifacts, and the execution engine carries out Implementation Briefs against them and proves completion.**

- **Source** — DekSpec artifacts: Markdown with YAML frontmatter and named-field structure, authored by humans. Templates in `templates/`.
- **IR (intermediate representation)** — the normalized parsed form the Constraint Compiler reasons about. Defined by schemas in `tooling/dekspec/schemas/` (v0.2.0+). An executor's construction plan is deliberately not IR: it is a revisable entry in the IB's execution record (`dekspec ib plan`), never a spec artifact (ADR-056).
- **Compiled outputs** — Interface Contract contract-test stubs (skipped until an engineer writes the assertions) and CI-gate jobs, Security Profile pre-commit and CI-gate snippets (enforcing once the consumer installs them), and AGENTS.md fragments (advisory context for agents, not a runtime check). Emitted by the Constraint Compiler. No lint rules or fitness functions are emitted today.
- **Execution** — an accepted IB is executed directly (ADR-056). `dekspec ib context` generates the agent's execution context from the canonical sources (binding obligations with source status and content hash, in explicit precedence — ADR-055); the agent, running in the harness, investigates, commits a plan and builds within bounded attempts; `dekspec ib verify`, an independent `dekspec ib review` verdict and `dekspec ib complete` record evidence-backed completion in `.dekspec/execution/<IB>/record.jsonl` (ADR-057). `dekspec delivery check` gates the merge at the exact branch head (ADR-058).

### Concrete example

A request like *"add CSV export"* becomes a structured bundle: a Working Spec with acceptance criteria, an Interface Contract for export behavior, an NFR for performance, an ADR about allowed data access. That structured bundle is the *compilable spec*. The Constraint Compiler parses it into the IR — a normalized constraint set the system can reason about. The change itself is carried by one Implementation Brief that references those artifacts as obligations and states its acceptance conditions; the agent receives the generated execution context, investigates, plans and implements, and the engine runs the acceptance conditions and enforces the completion and landing gates, while compiled scaffolding (contract tests and CI gates, once engineers complete them) checks the boundaries. Humans review intent at the spec layer and judge the result through an independent verdict; machines enforce constraints and bind evidence to the exact content reviewed.

## What lives in this repo

| Directory | Purpose |
|---|---|
| `plugins/dekspec/` | The Claude Code plugin — skills, commands, agents and hooks for authoring, auditing and execution, and the helper tools (project boards, code-quality and security review, brownfield onboarding, handoff, troubleshooting, exploration) as `/dekspec:<tool>` skills. Installed via the plugin marketplace; never vendored (AE-006). |
| `templates/` | Artifact templates with named fields. Bundled in the wheel; vendored into consumers' `dekspec/templates/` by `dekspec sync`. |
| `docs/` | Methodology guides + this architecture document. A selected set is bundled in the wheel and vendored into consumers' `dekspec/` by `dekspec sync`. |
| `tooling/dekspec/constraint_compiler/` | Python implementation of the Compiler. Installed via `pip install dekspec`. |
| `tooling/dekspec/fidelity_audit/` | Python implementation of `/doctor`. Installed via `pip install dekspec`. |
| `tooling/dekspec/execution/` | The Execution & Evidence Engine behind `dekspec ib`, `dekspec delivery` and `dekspec intent` (AE-011). |
| `tooling/dekspec/schemas/` | IR schemas (JSON Schema in YAML) — the IR specification. Shipped as package data. v0.2.0+. |
| `scripts/install.sh` | Consumer installer: the engine from the curated public mirror (ADR-034), then `dekspec sync`, then per-host delivery. |

## What does NOT live here

- **Project-specific artifacts.** Each consuming project has its own DekSpec instance under `dekspec/{adrs,working-specs,interface-contracts,…}/`. Dektora's ADRs live in `Dektora/dektora`. DekFactory's ADRs live in `Dektora/dekfactory`. None live here.
- **Project-specific scripts** (e.g., `check-coverage.sh` configured for a specific repo's layout). Stays in the consuming repo.
- **System Visions, Domain Glossaries, Project Contexts.** Each consumer authors its own using the templates here.
- **An external executor or long-running factory.** DekSpec owns governed, in-process execution (ADR-024, ADR-041) — the `dekspec ib` engine and the skills that drive it inside a harness — but not the agent runtime, sandbox, or an autonomous service that walks work without an engineer. `/dekspec:implement` (ADR-059) drives ready work to integrated completion inside the engineer's own harness session, on the engineer's explicit request; the deterministic decisions are core code (`dekspec implement next`), the agents are the harness's sub-agents, and it never skips acceptance evidence (ADR-057). References to "Phase 4" or "orchestration brain" in older skill bodies and docs point at that out-of-repo surface (historical tracking bead `ds-j8x`, closed).

## Tight vs swappable boundaries

- **Tight:** DekSpec → consumers (Python dependency + vendored templates and docs + the plugin). Schemas and skill APIs are part of the contract; breaking changes require a major version bump.
- **Swappable behind the engine:** the agent runtime and harness (model, sandbox, session management). The integration surface is the `dekspec ib` / `dekspec delivery` CLI verbs and the execution record; DekSpec doesn't dictate runtime choices.

## Versioning policy

Semver. See `CHANGELOG.md` for version history and migration notes for breaking changes. The fidelity audit is the safety net that catches incomplete migrations after a bump.

## Anti-patterns DekSpec must enforce in its own design

1. **Don't bake architectural rules into prose.** Skills and templates produce structured artifacts that are parsed and audited (and, for ICs and SPs, lowered to check scaffolding and snippets); they don't lecture.
2. **Don't ship project-specific content.** Glossary terms, visions, ADRs all stay in consuming repos.
3. **Don't ship one-off prompts in skills.** Skills compose with structured artifacts; they don't replace them.
4. **Don't grow the Constraint Compiler ahead of demand.** Each compiler output lands only when a consumer's enforcement layer is ready to consume it.
5. **Don't let activity masquerade as a decision, or a copy as a source.** Progress, attempts, reviews and failures live in the IB's execution record, never in a status (ADR-057); obligations are referenced from their one home and delivered by generation, never copied (ADR-056); DekSpec ships no external executor (ADR-024).

## References

- **DekFactory MVP playbook** — governing document for v0.1.0 scope and sync strategy. Currently at `Dektora/dektora/docs/workspace/dekfactory/dekfactory-mvp-playbook.md`; migrates to `Dektora/dekfactory/docs/workspace/dekfactory/` when that repo is set up.
- **External SDD literature** — see the playbook's Notes section for citations to Thoughtworks, GitHub Spec Kit, Augment Code, Zarar Siddiqi, Maestro, OpenHands V1, and the `agents.md` community standard.
