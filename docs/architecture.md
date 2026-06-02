# DekSpec Architecture

## Purpose

DekSpec is the shared governance library for Dektora projects. It provides:

- **Templates** for structured artifacts (ADR, Working Spec, Interface Contract, NFR, Architecture Element, Implementation Brief, Intent, Mission, vision note).
- **Skills** for authoring and auditing those artifacts (`/write-adr`, `/write-ws`, etc.).
- **The Constraint Compiler** that mechanically transforms LOCKED artifacts into enforcement representations.
- **The fidelity audit** that verifies the artifact graph is consistent.
- **The methodology** (operating guide, quick reference, architecture-frameworks reference).

Consuming repos (`Dektora/dektora`, `Dektora/dekfactory`, future Dektora projects) depend on DekSpec as a Python package and vendor its markdown content (skills, templates, docs) via `scripts/install-dekspec.sh`.

## Mental model — source → IR → compiled outputs → runtime

A **compilable spec** is a specification written with enough structure that software, agents, or tooling can reliably turn it into downstream artifacts — tests, rules, validation steps, implementation plans. An **intermediate representation (IR)** is the normalized internal form those tools use to reason about, validate, transform, and lower the spec into code or enforcement logic. The compiler analogy is genuine, not metaphorical: the system does not go directly from natural language to code, but through layers — request → normalized artifact set → plan/constraint IR → execution → verification → merge gates — the way a real compiler separates parsing, analysis, optimization, and code generation.

**DekSpec artifacts are the source specifications; consuming systems compile them into executable intermediate representations and enforcement artifacts.**

- **Source** — DekSpec artifacts: Markdown with YAML frontmatter and named-field structure, authored by humans. Templates in `templates/`.
- **IR (intermediate representation)** — the normalized parsed form the Constraint Compiler reasons about. Defined by schemas in `tooling/dekspec/schemas/` (v0.2.0+). Two flavors: the *compile-time IR* is the parsed/normalized artifact set; the *runtime IR* is `IMPLEMENTATION_PLAN.md` (authored by the consuming system's planning agent — e.g., DekFactory's OpenHands wrapper — not by DekSpec itself).
- **Compiled outputs (enforcement artifacts)** — tests, lint rules, fitness functions, AGENTS.md fragments, CI gate definitions. Emitted by the Constraint Compiler and consumed at execution and merge.
- **Runtime** — the consuming system's executor (e.g., DekFactory's OpenHands V1 wrapper), governed by the IR and constrained by the compiled outputs.

### Concrete example

A request like *"add CSV export"* becomes a structured bundle: a Working Spec with acceptance criteria, an Interface Contract for export behavior, an NFR for performance, an ADR about allowed data access. That structured bundle is the *compilable spec*. The Constraint Compiler parses it into the IR — a normalized constraint set the system can reason about; the planning agent reads the IR to produce the runtime IR (`IMPLEMENTATION_PLAN.md`); the executor implements against that plan while the enforcement artifacts (compiled tests, lint rules, CI gates) verify correctness. Humans review intent at the spec layer; machines enforce constraints at the IR and compiled-output layers.

## What lives in this repo

| Directory | Purpose |
|---|---|
| `skills/` | Claude Code skills for authoring/auditing artifacts. Vendored into consumers' `.claude/skills/`. |
| `templates/` | Artifact templates with named fields. Vendored into consumers' `dekspec/templates/`. |
| `docs/` | Methodology guides + this architecture document. Vendored into consumers' `dekspec/`. |
| `tooling/dekspec/constraint_compiler/` | Python implementation of the Compiler. Installed via `pip install dekspec`. |
| `tooling/dekspec/fidelity_audit/` | Python implementation of `/doctor`. Installed via `pip install dekspec`. |
| `tooling/dekspec/schemas/` | IR schemas (JSON Schema in YAML) — the IR specification. Shipped as package data. v0.2.0+. |
| `scripts/install-dekspec.sh` | Sync script run by consumers to vendor markdown content. |

## What does NOT live here

- **Project-specific artifacts.** Each consuming project has its own DekSpec instance under `dekspec/{adrs,working-specs,interface-contracts,…}/`. Dektora's ADRs live in `Dektora/dektora`. DekFactory's ADRs live in `Dektora/dekfactory`. None live here.
- **Project-specific scripts** (e.g., `check-coverage.sh` configured for a specific repo's layout). Stays in the consuming repo.
- **System Visions, Domain Glossaries, Project Contexts.** Each consumer authors its own using the templates here.
- **Phase 4 orchestration brain** — the autonomous executor that takes a PROPOSED Intent and drives the full lifecycle to LOCKED without per-step engineer prompts. **DekSpec stops at the spec authoring + verification surface**; the autonomous executor is `dekfactory`'s responsibility. The `/dekspec:orchestrate-intent --auto` flag (added in v0.85.0 per ADR-021) is the *guided* walker that an engineer can opt into for a clean Intent — it's not the autonomous brain. References to "Phase 4" or "orchestration brain" in skill bodies, Intent templates, and methodology docs all point at this dekfactory-side surface. Tracking bead `ds-j8x` ([FOLLOW.1] Phase 4 orchestration brain design) is retained for dekfactory-side authoring once the integration spec arrives; the boundary itself does not need a bead in this repo.

## Tight vs swappable boundaries

- **Tight:** DekSpec → consumers (Python dependency + vendored markdown). Schemas and skill APIs are part of the contract; breaking changes require a major version bump.
- **Swappable behind the consumer:** the consumer's runtime (e.g., DekFactory's `run_agent(...)` Interface Contract). DekSpec doesn't dictate runtime choices.

## Versioning policy

Semver. See `CHANGELOG.md` for version history and migration notes for breaking changes. The fidelity audit is the safety net that catches incomplete migrations after a bump.

## Anti-patterns DekSpec must enforce in its own design

1. **Don't bake architectural rules into prose.** Skills and templates produce structured artifacts that compile to enforcement; they don't lecture.
2. **Don't ship project-specific content.** Glossary terms, visions, ADRs all stay in consuming repos.
3. **Don't ship one-off prompts in skills.** Skills compose with structured artifacts; they don't replace them.
4. **Don't grow the Constraint Compiler ahead of demand.** Each compiler output lands only when a consumer's enforcement layer is ready to consume it.
5. **Don't mix governance with execution.** DekSpec governs (artifacts, schemas, audit); consumers execute (planning, locking, dispatch, drift detection).

## References

- **DekFactory MVP playbook** — governing document for v0.1.0 scope and sync strategy. Currently at `Dektora/dektora/docs/workspace/dekfactory/dekfactory-mvp-playbook.md`; migrates to `Dektora/dekfactory/docs/workspace/dekfactory/` when that repo is set up.
- **External SDD literature** — see the playbook's Notes section for citations to Thoughtworks, GitHub Spec Kit, Augment Code, Zarar Siddiqi, Maestro, OpenHands V1, and the `agents.md` community standard.
