# DekSpec Operating Guide
### Version 2.0.0

---

## Why This Exists

AI coding agents fill ambiguity with confident, plausible, wrong decisions. By review time the wrong assumption is load-bearing. The solution is to eliminate ambiguity before the agent starts. Specs are the mechanism.

Agents also forget everything between sessions. Execution records are the solution — each Implementation Brief's run (ownership, plan, attempts, evidence, review verdicts) is an append-only, Git-native log that travels with the repo (`.dekspec/execution/<IB>/record.jsonl`, ADR-056).

**The engineer's role:** provide domain knowledge, make decisions, approve work. AI drafts, critiques, and codes.

**What makes this different from standard spec-driven development:** most spec-driven practice assumes the engineer already has the domain knowledge to write a correct spec. For a sophisticated AI product — open-weight LLMs, embedding injection, graph databases, agentic design — that assumption does not hold. This methodology explicitly fills the gap with domain expert roles that expand the team's expertise before spec creation begins. The spec creation process, the 13 roles, and the expertise audit all exist for this reason.

---

## The System

Dektora injects quantized embedding tensors from a graph knowledge base into an open-weight vision-language model's hidden-state space, bypassing tokenization. Two model processes (chat and embedding) run in parallel across separate GPU devices and communicate via HTTP. An in-memory shadow graph serves as the hot-path read layer with buffered writes to the persistent graph database. An in-memory shadow timeline mirrors the conversation timeline store with the same caching pattern.

**Silent failure zones** — these don't crash, they produce plausible wrong outputs:
- Transformer internals (position ID construction, injection layer, KV cache)
- Numerical precision (quantization, wave compression, tensor serialization round-trips)
- GPU multi-process isolation (device assignment, process crash recovery)
- Graph consistency (shadow graph / Neo4j flush failures, phantom nodes)
- Timeline coherence (topic segmentation, quantization tier assignment, decay/reactivation scoring, shadow timeline / PostgreSQL flush failures)

The spec creation process catches these before a coding agent sees the work.

---

## Operating Principles — the design heuristic

Every DekSpec consumer carries an **Operating Principle** in its Constitution + System Vision (recommended, not schema-required — see `docs/dekspec-methodology.md` §"Operating Principles"). The principle is a short mantra that compresses the project's design posture into a sentence contributors can recite at session-load time.

The most common shape is a **forging-vs-derived** division. The exemplar mantra (Dektora/dekfactory, 2026-05-28): **"Human in forging, dark on derived."**

Use this design heuristic table to decide which side of the mantra a given activity falls on:

| Activity | Forging or derived? | Default execution | Why |
|---|---|---|---|
| Author a System Vision | Forging | Human in chair | Taste call. The vision IS the project's identity. |
| Author an ADR | Forging | Human in chair | Architectural decision; the rationale must survive context loss. |
| Author a Working Spec | Forging | Human + AI assist | Capturing intent; the human's mental model is the source of truth. |
| Author an Intent | Forging | Human + AI assist | Cross-component commitment; the engineer commits to outcome + verification. |
| Author an Implementation Brief | Derived from a WS or Intent; forging for a direct bounded change | AI default; human authorizes (`dekspec ib accept`) | The IB is the work contract: outcome, obligations by reference, scope, acceptance. Authorization is the human decision. |
| Execute an accepted IB | Derived | AI default; an independent reviewer judges the result | Obligations and acceptance bind; how to meet them is delegated (ADR-055). Completion needs current evidence (ADR-057). |
| Write acceptance tests from acceptance conditions | Derived | AI default; an independent oracle review before the baseline | The conditions are the spec. The tests are deterministic against them, each expectation carries an independent basis the oracle reviewer judges, and they are protected once accepted (ADR-062). |
| Aggregate AGENTS.md from artifacts | Derived | Fully autonomous | The artifacts are the spec. The aggregator is deterministic. |
| Re-derive backlinks (`dekspec relink`) | Derived | Fully autonomous | The forward links are the spec. The backlinks are pure function. |
| Migrate persisted IR forward (`dekspec migrate`) | Derived | Fully autonomous | The migration is itself a typed transformation. |
| Run linkage + drift audits | Derived | Fully autonomous | The audit rules are the spec. The findings are pure function. |

The table is *not* the methodology — it's a heuristic for daily judgment calls. The methodology lives in the Constitution. The heuristic gives a contributor a quick litmus test when the Constitution's prose is too far away.

A project that adopts a different mantra (e.g., "Spec before code", "One contract, one run", "No specless edits") translates the mantra into a different table. The shape stays the same: name the activity, classify against the mantra, declare the default execution mode, justify with a one-line rationale.

When the mantra changes (rare; treated as a Constitution amendment), the table is re-derived. The cascade through downstream artifacts (AE autonomy fields, Mission autonomy ceilings, audit-rule severity tuning, skill catalog filtering, regenerated AGENTS.md) is documented in `docs/dekspec-methodology.md` §"Operating Principles" → "Cascade".

---

## The Workflow

```
                                    Research (helper skill)
  → /recover-specs                  reverse-engineer existing code before specifying
                                    ─────────────────────────────────
                                    Framing (optional — only when it adds something, ADR-056)
  → /write-mission                  a programme with a shared outcome, flag, rollback or kill criteria across several Intents
  → /write-intent                   an outcome spanning several IBs, with its own outcome test (ADR-029)
                                    ─────────────────────────────────
                                    Layer 1 — Design & Architecture (on demand)
  → /write-ae                       an architecture slice (subtype: System / Subsystem / Container / Component / Pipeline / Data Model / Cross-Cutting Concern / Platform Concern / Interface Surface / Workflow / Process)
  → /write-adr                      an undocumented or changed decision
                                    ─────────────────────────────────
                                    Layer 2 — Specification (on demand)
  → /write-ws                       behavior that spans or outlives IBs (role passes, critic)
      → /write-adr                  (triggered by the Options Architect — back to Layer 1)
      → /write-ic                   (triggered for a cross-component boundary)
                                    ─────────────────────────────────
                                    Layer 3 — The work contract (always)
  → /write-ibs  or  ib new          one Implementation Brief per bounded change — from a WS, an Intent, or nothing
  → ib lint → ib propose            an executable contract; request authorization
  → /write-tests · /write-evals     (mandatory, before authorization) acceptance tests the conditions name — a basis per
                                    assertion, a surface skeleton, genuine red on `ib floor` — and eval commands
  → /dekspec:review-ib              independent review of the contract and oracle review of the tests and floor report;
                                    a passing floor review is a `Floor reviewed:` Amendment Log row naming the digest
  → ib accept                       authorize execution; the acceptance baseline protects the reviewed floor
                                    ─────────────────────────────────
                                    Layer 4 — Construction and completion
  → /orchestrate-coding-session     executes ready IBs in isolated worktrees: start → investigate → plan → attempts → verify
  → /dekspec:review-pr              independent review of the delivery → one recorded verdict per IB
  → ib complete                     per IB, only on current evidence and a current independent verdict
  → /dekspec:land-intent            delivery check at the exact head → operator-confirmed merge
```

Each `/name` step is a skill shipped by the `dekspec` plugin; each `ib …` / `delivery …` step is a `dekspec` CLI verb. The diagram shows layer order, **not a mandatory chain**.

### End-to-end flow (step-by-step)

> **A bounded change is one IB** (ADR-056). Intents, Missions, Working Specs, Interface Contracts, AEs and ADRs are authored only when they hold something the IB cannot: an outcome spanning several IBs, a programme with kill criteria, behavior that spans briefs, a cross-component contract, an architecture description, a decision. No parent artifact is ever written just to satisfy a workflow.

1. **Decide what the change needs.** A bounded change starts at step 3. A committed outcome that will take several IBs gets `/write-intent` — every Intent ≥ ACCEPTED ships an `outcome_verification` under strong-TDD timing (ADR-029). Work that plausibly spans several Intents, or needs a flag, rollback plan or kill criteria, gets `/write-mission`.
2. **Update the durable specs the change actually affects** — `/write-adr` for a decision, `/write-ae` for architecture, `/write-ws` for behavior that spans IBs, `/write-ic` for a boundary. An IB whose change alters architecture or a contract names those artifacts under `**Spec impact:**`; its verification fails unless the delivery modifies them.
3. **Write the IB** — Outcome, Rationale, Scope, Obligations *by reference*, Protected Surfaces, Acceptance, and a revisable Implementation Hypothesis (§Implementation Brief). `dekspec ib new <slug>` scaffolds a delegated IB with no parent; `/write-ibs` authors IBs from a WS, from an Intent (`/write-intent --decompose`), or from a plain description. `dekspec ib lint IB-NNN` confirms it is an executable contract whose references resolve.
4. **Acceptance tests, then the oracle review — mandatory before authorization (ADR-062).** `dekspec ib propose IB-NNN` (lint-gated) requests authorization. `/write-tests` writes the acceptance tests the conditions name — behavior-first (ADR-036), each new assertion with a `Basis:` line saying where its expected result comes from, and a behavior-free surface skeleton for any entry point that does not exist yet — and `dekspec ib floor IB-NNN` must show every new node genuinely red with a basis and every preserved node passing; `/write-evals` writes eval commands for model-output behavior. Then `/dekspec:review-ib IB-NNN`, in a context that did not write the tests, reviews the contract and, through its `acceptance-oracle` lens, the test sources, the skeleton and the floor report; a passing floor review is recorded as a `Floor reviewed: PASS — digest …` row in the IB's Amendment Log (§Protected acceptance, no regeneration).
5. **Authorize** — `dekspec ib accept IB-NNN` (the engineer's decision; takes the acceptance baseline) — only while `dekspec ib floor IB-NNN` still reports the digest the `Floor reviewed:` row names. A pre-start change to the tests repeats the oracle review (a new row) before `dekspec ib baseline IB-NNN --reason "…"` re-protects them.
6. **Execute** — `/dekspec:implement IB-NNN` (or `INT-NNN`) runs steps 6–8 autonomously once the work is READY (§Implementing ready work). Manually, `/orchestrate-coding-session` (or any agent, or a human) runs §Executing an Implementation Brief: `dekspec ib start`, investigation, a committed plan, counted attempts, `dekspec ib verify`.
7. **Review** — `/dekspec:review-pr` reviews the delivery diff against every included IB; the reviewer, never the builder, records `dekspec ib review IB-NNN --reviewer NAME --verdict pass` (or `--verdict fail`). On `fail`: fix, re-verify, re-review.
8. **Complete and land** — `dekspec ib complete IB-NNN` per IB; `dekspec delivery verify` and `dekspec delivery check` at the exact head; the operator merges (`/dekspec:land-intent`, ADR-026, ADR-058) — or `/dekspec:implement` integrates, when it was the engineer's request (ADR-059). An Intent completes with `dekspec intent verify` + `dekspec intent complete`; a Mission with `/write-mission --complete`.
9. **Throughout** — `dekspec doctor` is the dogfood gate (Mission/Intent gates require P0/P1-clean).

Reviews run the shared non-sycophantic orchestration: context-isolated lens specialists attack rather than grade, a blind aggregator scores, and a single confident veto (≥80) overrides any weighted average. A verdict counts only when it is recorded with `dekspec ib review`, bound to the content it reviewed (ADR-057); nothing merges without the operator (ADR-026) — whose explicit `/implement` request is that confirmation for the requested work (ADR-059).

### Implementing ready work (`/implement`, ADR-059)

`/dekspec:implement <request>` takes ready work all the way through without asking the engineer to drive: `/dekspec:implement INT-041`, `/dekspec:implement int-041 and int-042`, `/dekspec:implement the authentication feature`. There are no mode flags. The explicit request is the authorization: it covers construction, tests, independent review, repair within scope and integration of that work, and nothing else — no specification approval, no weakening of acceptance, no branch-protection bypass, no deployment.

**READY is a predicate, not a status.** `dekspec implement ready <request>` holds when the Intent is `ACCEPTED` with a desired outcome, executable Verification and autonomy `medium` or `high`, no unresolved P0–P2 Open Issue and in-force linked specs; its IBs are delegated, authorized *for their current contract* (baseline hash = contract hash) and their obligations resolve; an IB with test conditions or declared assets holds its named acceptance nodes and declared assets in its baseline, and a `Floor reviewed:` row in its Amendment Log names the baseline digest (ADR-062 — the builder never first creates an acceptance test); every dependency is complete or selected; and the environment can execute (committed specs, the integration base, the integration method, a pytest interpreter, the IBs' prerequisite probes). Otherwise it names each missing preparation and its fix. `/dekspec:spec-intent` ends by evaluating the same predicate. A complete target is a verification result, not work.

**The driver.** `dekspec implement next` decides every step from durable state — the IB, Intent and run records, git and the forge — and takes the mechanical ones itself; the skill only dispatches the workers it asks for (builder, independent reviewer, conflict resolver, intent reviewer) and acknowledges them:

| Stage | What happens |
| --- | --- |
| Prepare | a delivery worktree and branch `implement/<targets>` per dependency-connected group of targets, and a run record holding the authorization |
| Construct | IB runs start in dependency order; builders investigate, plan, work in counted attempts and record evidence; failures come back as repair dispatches |
| Verify | `dekspec delivery verify` (every IB plus the base's integration command) and each Intent's outcome verification at the same content. An IB whose passing evidence the driver itself recorded at the identical binding (content, contract, baseline, context manifest and base) is not executed again; a builder's evidence always is |
| Review | an independent reviewer per IB records `dekspec ib review`; a failed verdict goes back to the builder with its findings |
| Complete | `dekspec ib complete` per IB, then `dekspec intent complete` |
| Land | `dekspec delivery check --rerun` at the content and base, recorded as `landing.verified`: it re-executes acceptance and the integration command except where the driver's own passing delivery verification stands at the identical binding, and names the evidence it relied on. Then integration (`integration.method`: `merge` or `github`), and confirmation that the integrated content is the verified content |

**Agent roles.** Every worker's instructions are composed from one of DekSpec's six Agent Role Specifications (ADR-061) — builders and resolvers `implementer`, reviewers `code-reviewer`, Intent attestation `verifier` — as governing policy, role, procedure and assignment. The run record names the role and its policy revision for every dispatch, reviewers get the recorded facts rather than the builder's account, and a verdict made under an older review-policy revision is reviewed again. The roles ship inside DekSpec; there is nothing to author, select or configure.

A moved base is merged in (conflicts go to a resolver) and everything re-verifies; reviews carry forward only across unreviewed surfaces. Repeated failure without progress gets two recorded strategy changes, then a genuine blocker; independent deliveries continue. Records make the run restartable: after a compaction the skill simply asks `next` again, and repeating the request after the session ended resumes it — a lost worker is reissued, and nothing merges twice.

**Manual path.** The same phases remain available one at a time: `/orchestrate-coding-session` (construction), `/dekspec:review-pr` (review) and `/dekspec:land-intent` (landing with an operator-confirmed merge, ADR-026). `/orchestrate-intent` was retired by ADR-059 (which supersedes ADR-021).

**Auxiliary skills** (outside the main pipeline):

- `/recover-specs` — brownfield spec-gap recovery: scan an orphaned code surface, propose a retroactive Intent skeleton, and ratify it through `/write-intent --accept`. `/write-intent --analyze` composes it for bottom-up archaeology.
- `/ingest-docs` — classify inherited markdown prose (Confluence exports, inherited PRDs, design wikis) into DekSpec artifact slots via `dekspec ingest`. A helper tool the operator starts as a slash command.
- `/write-glossary` — extract term candidates and add terms to the domain glossary.
- `/write-corrections` — log domain corrections, track recurrences, promote at threshold.

*The listener side of the async inbox/listener dispatch pattern (originally `/dekspec:dispatch-inbox-listener`, later `/dekspec:factory-listen`) was excised from this library in INT-099 — 2026-05-27 — when the factory surface moved to `Dektora/dekfactory` as an independent plugin. AE-009 still defines the inbox/outbox contract; the listener implementation now lives in the dekfactory plugin.*

**System health:** `/doctor` checks cross-reference consistency across all artifacts, skills, templates, and governance files. Run it after modifying skills, templates, or the operating guide, and periodically to catch drift.

Layer boundaries are phase transitions — crossing from one layer to the next changes what kind of work you are doing. The role system and expertise audit are Layer 2 mechanisms that can trigger Layer 1 artifact creation (e.g., the Options Architect surfaces a decision that needs an ADR).

---

## The Artifacts

The DekSpec process organizes artifacts into four layers. Each layer has a distinct purpose and authority. Work flows downward through the layers; conflicts resolve upward.

```
Layer 1 — Design & Architecture  (the project's source of truth)
  System Vision · Architecture Elements · ADRs · Domain Glossary

Layer 2 — Specification  (behavioral contracts — the "how")
  Working Specs · Interface Contracts

Layer 3 — Implementation  (the executable work contract)
  Implementation Briefs

Layer 4 — Construction  (code, tests, evidence — produced, not authored)
  Execution records
```

| Layer | Artifact | What it is | Where |
|-------|----------|-----------|-------|
| 1 | System Vision | Why the system exists, what success looks like, what we're not building. One per system. | `dekspec/system-vision.md` |
| 1 | Architecture Element (AE) | Canonical descriptive artifact for a coherent architectural slice — a system, subsystem, container, component, pipeline, data model, cross-cutting concern, platform concern, interface surface, or workflow/process. Every AE declares a subtype and links to related ADRs, WSs, ICs, IBs. Replaces the legacy Design Note artifact. | `dekspec/architecture-elements/AE-NNN-[slug].md` |
| 1 | ADR | One architectural decision — immutable once locked; changed by supersession. | `dekspec/adrs/ADR-NNN-[slug].md` |
| 1 | Domain Glossary | Canonical definitions for all domain terms — proactive reference read before writing any artifact. | `dekspec/domain-glossary.md` |
| 2 | Working Spec | Behavioral requirements that span or outlive IBs. Optional upstream of an IB. | `dekspec/working-specs/WS-NNN-[slug].md` |
| 2 | Interface Contract | Cross-component boundary definition — consumed by independently-built components. | `dekspec/interface-contracts/` |
| 3 | Implementation Brief (IB) | The smallest governed work contract — outcome, binding obligations (by reference), scope, protected surfaces, acceptance conditions, and a revisable implementation hypothesis. Executed directly (ADR-056). | `dekspec/impl-briefs/` |
| 4 | Execution record | Append-only, hash-chained log of one IB's run: ownership, plan and tasks, attempts, deviations, blockers, acceptance baselines, evidence, review verdicts, completion. Not a spec artifact — never compiled into IR, projected into `AGENTS.md`, or copied into specs. | `.dekspec/execution/<IB>/record.jsonl` |

There are no code beads. Construction was once decomposed into `br` code beads authored from each IB; ADR-056 retired that tier. An executor may split an IB into internal tasks after investigating, but tasks live in the execution record and carry no authority. The legacy `cb-` workspace stays readable for history, and `dekspec ib import-beads IB-NNN` moves a legacy IB's beads into its execution record. Issue beads (`iss-`) and governance beads (`ds-`) are unaffected — backlog tracking stays in `br`.

**Filename convention (per ADR-012).** L0 singletons — those that are unique per repository (System Vision, Domain Glossary, Terminology Corrections, the Constitution) — use **slug-only filenames** like `system-vision.md`. Layer 1+ artifacts — those authored repeatedly under a counter (AE, ADR, WS, IC, IB, Intent, Mission) — use **`TYPE-NNN-slug.md` filenames** like `AE-001-dekspec.md`. The split reflects cardinality: singletons have no counter dimension, so none appears in the name; L1+ artifacts do, so the counter is load-bearing. Both `dekspec init` and the parser's kind detection honor this rule; the methodology doc §4 has the long-form discussion.

### Authority and Conflict Resolution

Each Layer 1 artifact has authority over a distinct domain:

- **System Vision** — authority over system identity and scope
- **Architecture Elements** — authority over the description of architectural slices (what the slice is, its boundary, its responsibilities, and its relationships)
- **ADRs** — authority over specific architectural decisions
- **Domain Glossary** — authority over terminology, definitions, and naming conventions

These are complementary, not competing. An Architecture Element describes a slice; an ADR records a specific decision that shapes one or more AEs. The System Vision constrains what AEs can describe.

**Within Layer 1:** Contradictions are consistency bugs, not governance disputes. When a Layer 1 artifact contradicts another, the resolution is always to make Layer 1 internally consistent — never to let one artifact silently override another. An ADR can legitimately exist in tension with an AE's description if the ADR records a deliberate tradeoff, but the tension must be acknowledged in the ADR and reflected in the AE. Silent contradictions are never acceptable. When any Layer 1 artifact changes, review all Layer 1 artifacts that reference it for consistency.

**Across layers:** ADRs govern all work in Layers 2–4. A Working Spec that contradicts an ADR must be corrected. An IB whose obligations contradict each other, or contradict the existing system, is escalated rather than silently resolved by the implementing agent. Resolution always flows upward to the highest layer where the inconsistency lives.

**Inside a work contract — three kinds of authority (ADR-055).** An IB's content is classified by meaning, not by heading:

| Category | Where it lives in the IB | The implementing agent… |
|---|---|---|
| **Binding obligation** | Obligations (by reference), Protected Surfaces, Scope | preserves it. Changing it takes a decision: amend the IB, or change the canonical artifact the obligation lives in (ADR supersession, IC unlock-to-version, WS/AE revision with cascade). |
| **Acceptance condition** | the `## Acceptance` block (`AC-n`) | demonstrates it with evidence, and never weakens, skips, deletes or reinterprets it to claim success. An invalid condition is corrected only by recorded amendment (ADR-057). |
| **Implementation hypothesis** | Implementation Hypothesis | investigates first and revises it within Scope without asking; material departures are recorded as deviations in the execution record, automatically. |

**Context is retrievable; authority is bound.** The implementing agent may read anything — code, ADRs, ICs, WSs, historical Intents, drafts. Reading a rationale is not authority to overturn it: only approved obligations bind. Draft, superseded and historical material informs but never binds, and a binding reference to a superseded, deprecated, missing or unapproved source is an error that blocks `dekspec ib propose`, `accept` and `start` rather than a silent fallback.

**Escalate only when you must.** The agent stops and escalates when it would have to change a binding obligation or protected surface; change something outside Scope; weaken, reinterpret or replace an acceptance condition; resolve a contradiction the contract does not settle; or proceed without a required prerequisite or authority. An **underdefined contract** — the outcome or an obligation cannot be determined from the approved sources — is an escalation and a visible contract defect. An implementation detail the agent can discover by investigation is not. More implementation freedom never authorizes more product scope.

**One home per fact (ADR-056).** A decision lives in its ADR, an interface contract in its IC, a cross-brief behavioral requirement in its WS, an architecture description in its AE, a project-wide commitment in the Constitution, and an IB-specific acceptance condition in the IB. An IB *references* an obligation — `- **O-1** → ADR-036`, `- **O-2** → IC-012 §Shape` — and states one in full only when the IB is its canonical home (`- **O-3** (local): …`). A shared shape pinned under ADR-054 branch 2 is written once — in an IC, in a WS, or as one IB's local obligation that others reference as `IB-NNN §O-n` — never copied into every consumer.

**Context is generated, never maintained.** `dekspec ib context IB-NNN` resolves every reference to the source's current text with its path, status and content hash, states the precedence (binding obligations → acceptance conditions → implementation hypothesis → everything else as information), and lists informational pointers. It is a derived snapshot, bound to the run at `dekspec ib start`; changing a source changes the next generation and makes evidence bound to the old manifest stale (ADR-057). Dispatch prompts are built from it — nobody pastes ADR, IC or WS text into an IB, a prompt or a task. The project-wide `AGENTS.md` (`dekspec aggregate agents-md`) likewise projects only the governing core — Constitution, Security Profile, System Vision, glossary, AEs, ADRs, ICs, WSs; work items (IBs, Intents, Missions) are excluded by default and reach an agent through `ib context`.

### Architecture Elements

The System Vision is a singular, top-level document describing the entire system — why it exists, who it serves, and what it is not. It is authored via `/write-sv` from the `dekspec/templates/system-vision-template.md` template (singleton at `dekspec/system-vision.md`, id `SYSTEM-VISION`). Subsystem-level descriptions live in Architecture Elements, not in additional Vision documents. Architecture Elements (AEs) describe coherent architectural slices — the canonical descriptive artifact for a system, subsystem, container, component, pipeline, data model, cross-cutting concern, platform concern, interface surface, or workflow/process. AEs use a global `AE-NNN` numbering scheme and live in a flat directory at `dekspec/architecture-elements/`. Each AE declares one primary **subtype** in its metadata, drawn from the enum:

- **System** — the highest-level system under discussion (C4 Software System)
- **Subsystem** — a *logical grouping* of multiple Containers above the C4 hierarchy
- **Container** — a deployable / runnable unit (service, app, store) — C4 Container
- **Component** — code/functionality inside a Container — C4 Component
- **Pipeline** — sequenced flow of operations
- **Data Model** — canonical data/state structure
- **Cross-Cutting Concern** — concerns spanning multiple Containers
- **Platform Concern** — operational/deployment topology (C4 Deployment perspective)
- **Interface Surface** — boundary between Containers (where ICs live)
- **Workflow / Process** — dynamic flow (C4 Dynamic perspective)

AEs use `dekspec/templates/architecture-element-template.md`.

**Framework reference:** the AE subtype enum borrows naming from C4 (System / Container / Component) and breadth-categories from arc42 (Building Blocks, Crosscutting Concepts, Quality, etc.). For the full arc42 chapter mapping, C4 diagram lexicon, routing keyword tables, and the synthesis used by the writing skills' classifier, see `dekspec/architecture-frameworks-reference.md`.

**Heritage note:** AE replaces the legacy *Design Note* (DN) artifact (DN→AE migration 2026-04-27). Migrated artifacts retain their numeric IDs and carry a `former_dn:` metadata field for traceability. Historical references to "DN" remain in `audits/` reports as factual records of the corpus state at audit time.

**Scope discipline:** An AE describes a coherent architectural slice. An AE should link to at least one ADR — if it does not, it is too narrow in scope to be an AE. If it covers more than eight ADRs worth of territory, it is too broad — split it (or, if the breadth is genuine, declare subtype `Subsystem` and decompose into linked Container AEs).

### Domain Glossary

The Domain Glossary (`dekspec/domain-glossary.md`) is a singular Layer 1 artifact that defines canonical terminology for the entire system. It is a proactive reference — terms are defined here before use, not corrected after mistakes. Every agent writing or reviewing a Layer 1, 2, or 3 artifact must read the glossary before starting.

The glossary defines: canonical term definitions, common confusions to avoid ("NOT this"), and code naming conventions. It is organized by domain category (Embedding & Tensor, Quantization & Compression, Architecture & Pipeline, Graph & Storage, Scoring & Geometry, Position & Injection, Timeline & Topics).

Reactive corrections that surface during spec writing land in `terminology-corrections.md` via `/write-corrections --log`. Each recurrence is tracked. At 3 recurrences, the entry is auto-promoted to a glossary row (composed by `/write-glossary`). All authoring skills invoke `/write-corrections --log` when they correct a domain misinterpretation.

### Artifact Lifecycle

A governed status records a **decision** — a request for approval, an authorization, a completion, a retirement. Activity (being built, being tested, being reviewed, being merged) is not a status; it lives in the execution record (ADR-057, ADR-046).

| Kind | Lifecycle | Retirement |
|---|---|---|
| System Vision, Constitution, Interface Contract | `DRAFT → PROPOSED → ACCEPTED → LOCKED` | `DEPRECATED` |
| ADR | `DRAFT → PROPOSED → ACCEPTED → LOCKED` | `DEPRECATED`, `SUPERSEDED` |
| Security Profile | `PROPOSED → ACCEPTED → LOCKED` | `SUPERSEDED` |
| Architecture Element, Working Spec | `DRAFT → PROPOSED → ACCEPTED` — living references that never lock (ADR-046) | `DEPRECATED` |
| Implementation Brief | `DRAFT → PROPOSED → ACCEPTED → COMPLETE` — `COMPLETE` only via `dekspec ib complete` | `SUPERSEDED`, `DEPRECATED` |
| Intent | `DRAFT → PROPOSED → ACCEPTED → COMPLETE` — `COMPLETE` only via `dekspec intent complete` | `SUPERSEDED` |
| Mission | `PROPOSED → ACTIVE → COMPLETE` | `KILLED`, `SUPERSEDED` |

- **DRAFT** — being written; anything goes
- **PROPOSED** — complete and submitted for a decision; not yet accepted
- **ACCEPTED** — approved. For an AE or WS, the living reference; substantive changes are allowed but must cascade to affected downstream artifacts. For an IB, **authorized for execution** — acceptance takes the acceptance baseline.
- **LOCKED** — frozen; editorial amendments only (typos, grammar, formatting — no meaning change)
- **COMPLETE** — evidence-backed completion of a work item, recorded by the completion gate; a historical record thereafter
- **DEPRECATED** — retired without a successor. Add a Deprecation Note explaining why.
- **SUPERSEDED** — replaced; record the successor in the Supersession field (*Superseded by:* …).

**Retired statuses.** `TODO` (everywhere — it duplicated DRAFT); IB `QUEUED`, `ACTIVE`, `COMPLETED`, `REVIEW_IB`, `REVIEW_IB_FAIL`, `REVIEW_PR`, `REVIEW_PR_FAIL`, `TESTFAIL`; Intent `OVERSIZED`, `IMPLEMENTING`, `TESTPASS`, `MERGED`; Mission `COMPLETING`. The parser refuses them with a pointer to `dekspec migrate`, which maps each one explicitly and records the prior status in the artifact's own Amendment Log. A legacy IB migrated from `COMPLETED` is *historically complete* (ADR-057): its completion predates the delivery in the committed history, so it satisfies dependencies and Intent completion without new evidence; a `COMPLETE` written on a delivery branch never does. See `docs/artifact-and-transition-inventory.md` for where each retired state's information went.

**Unlocking:** A LOCKED artifact can be unlocked back to PROPOSED when substantive changes are needed. The Amendment Log records the unlock and the reason. Unlocking triggers a full downstream cascade review.

Each artifact carries an Amendment Log to record changes made after locking, when unlocking, and on every lifecycle decision the tooling writes.

---

## Intents

Intents (`INT-NNN`) are DekSpec's mechanism for **cross-component outcomes that span several IBs**. An Intent is a machine-verifiable commitment the system lands or explicitly abandons: it names the outcome, its outcome test (ADR-029), and the components it may touch. Intents sit *orthogonal* to the L1–L4 layer system: they cut horizontally across components, drive changes vertically into each affected component's layer stack, and dissolve at `COMPLETE` into the artifacts and code they produced (revised AEs, new ADRs, revised WSes, new ICs, completed IBs with their execution records).

**Optional (ADR-056).** A bounded change needs no Intent — it is one IB. Author an Intent when an outcome spans several IBs and deserves its own verification, or when a Mission sequences it.

Equivalent framing along the vertical axis: Intent and Mission are **L1-anchored** (their typed graph link is `linked_architecture_elements` — they pin into AEs, not WSs / ICs) and **reach through L2-L4** (they spawn L3 IBs, may revise L2 WSs / ICs, and carry L4-surface `verification` / `rollback` / `kill_criteria` commands the audit's L9 rule resolves to executable scripts). They fit in a layer — L1 — but span it downward to the executable surface. The two framings (horizontal orthogonal-to-layers; vertical L1-anchored-reaching-down) are complementary descriptions of the same artifact shape.

```
              Mission (optional, MSN-NNN)
       ─────────────────────────────────────────
        │   queue of Intents in execution order  │
        │   shared Outcome / flag / rollback     │
       ─────────────────────────────────────────
                          │
                          ▼  (one Intent active at a time within a Mission)

                Components / Boundaries
          ┌──────────┬──────────┬──────────┐
          │ Comp A   │ Comp B   │ Comp C   │
L1 ADR    │          │  new ADR │          │
   AE     │          │          │  new AE  │
L2 WS     │ revise   │  revise  │  new WS  │
   IC     │       revise IC ◄──►            │
L3 IB     │ IB-001   │  IB-002  │  IB-003  │
L4 Run    │ record   │  record  │  record  │
          └──────────┴──────────┴──────────┘
                         ▲
                         │
        Intent ════════════════════════════▶
              cuts horizontally across
              components and boundaries
```

An Intent is not a layer; it is a *driver* that an engineer or autonomy brain runs *through* the layered system. Its IBs point back at it (`**Parent:** INT-NNN`); nothing else ties them together.

**Files canonical, delivered from one worktree.** Every Intent lives at `dekspec/intents/INT-NNN-<slug>.md` (provisional under `dekspec/provisional/<slug>/` until promoted, ADR-030). Its work is delivered from one worktree and branch per ADR-048 (`/dekspec:use-worktrees`); the file is the canonical record at every status transition; the index (`dekspec/intent-index.md`) tracks the active queue and the archive.

### Lifecycle

```
DRAFT → PROPOSED → ACCEPTED → COMPLETE
  any non-terminal ──────────► SUPERSEDED
```

| Status | Transition trigger | What happens |
|---|---|---|
| `DRAFT` | `/write-intent <description>` | Intent file written (provisional by default, ADR-030); default Autonomy (`medium`) + type-default Verification populated. An analysis that exceeds a size cap leaves the Intent here with a P2 open issue — *re-split before acceptance* |
| `PROPOSED` | `--analyze` clean | Coverage report + size assessment populated; Verification predicate filled; engineer has not yet accepted |
| `ACCEPTED` | `--accept` (engineer-only) | Direction authorized. `--decompose` writes the child IBs (`**Parent:** INT-NNN`); the status does not change while they execute |
| `COMPLETE` | `dekspec intent complete INT-NNN` | Every child IB `COMPLETE` and the outcome evidence current and passing (§Verification and completion). A historical record thereafter, editable with no unlock cycle |
| `SUPERSEDED` | `--supersede` | Replaced by a successor Intent recorded in `Superseded-By` |

*`TODO`, `OVERSIZED`, `IMPLEMENTING`, `TESTPASS` and `MERGED` were retired by ADR-057: they mirrored activity, which now lives in the IBs' execution records and in git. `dekspec migrate` maps each and records the prior status in the Amendment Log. `TESTFAIL` was retired at the Intent level in 2026-05, reintroduced for IBs by ADR-027, and retired again when ADR-057 superseded ADR-027 — a failing verification is evidence, not a status. The Intent's `## TESTFAIL records` log and the bead tracking in `Layer impact analysis` are likewise retired for new work.*

**Default Autonomy: `medium` (ADR-059).** `/write-intent` Creation Mode gives every new Intent `medium`, whatever its type: feature, NFR, ADR-driven and environment work included. Acceptance is the approval. After it, and once `dekspec implement ready` holds, `/implement` builds, tests, independently reviews, repairs and integrates the accepted work without routine prompts. The readiness and acceptance gates stay; the per-step approvals go. `manual` and `low` remain available as explicit restrictions. The engineer names the human decision they reserve, and the cap is the Mission's Autonomy ceiling. Existing Intents keep the value they recorded, and `dekspec implement ready` reports a restriction as `intent-autonomy` (or `mission-autonomy-ceiling`) rather than overriding it. This replaces INT-094's per-type default, which set `manual` for `feature` / `nfr` / `adr-driven` / `environment`. See `templates/intent-template.md` §Autonomy and `plugins/dekspec/skills/write-intent/modes/create.md` Step 4.

### Serialization

**Per-Mission serialization, advisory enforcement (ADR-016).** Intent serialization is scoped to the Mission. Within a single Mission, at most one child Intent should be in active status at a time — child Intents are dependency-ordered, so the Mission's Intent queue is also its serialization queue. Active means any non-terminal status: `DRAFT`, `PROPOSED`, `ACCEPTED`. `COMPLETE` and `SUPERSEDED` are terminal and are not counted.

Across distinct Missions, and for Mission-less standalone Intents, there is no serialization limit — independent workstreams proceed in parallel. Enforcement is advisory: `/write-intent` Creation Mode never refuses on serialization grounds; the gate of record is a `dekspec audit linkage` finding that surfaces when a Mission carries more than one active Intent. The orchestration brain (Phase 4, deferred) may parallelize across *Missions* (independent feature flags, independent components); it never parallelizes *within* a Mission.

The repo-wide count of active Intents is a separate backlog-health signal, not a serialization rule — a large active-Intent backlog erodes review bandwidth and lets cross-artifact linkage rot (see ADR-015), and may warrant its own advisory finding, but it never blocks creation.

*ADR-016 superseded the original Decision #9 ("one active Intent across the whole repo," hard-enforced at `/write-intent` Creation Mode). That rule was never ratified in an ADR and was, in practice, violated by nearly every Intent — by 2026-05-20 the library self-spec held 19 active Intents against a stated cap of 1.*

### Hard size caps

`--analyze` measures five caps. Exceeding any cap is an **analysis finding, not a status**: `--analyze` records a P2 open issue ("re-split before acceptance") and the Intent stays `DRAFT` (ADR-057). There is **no engineer-side override** — the only path forward is splitting the Intent (peel off siblings, or convert it into a Mission) or re-scoping.

| Cap | Limit | Why |
|---|---|---|
| Implementation Briefs | ≤ 3 | The Intent stays small enough to review as a single coherent change |
| Components affected | ≤ 3 | Prevents accidental cross-cutting sprawl |
| New L1 artifacts (AEs) | ≤ 1 | New L1 work is its own discipline; one new AE per Intent is the natural unit |
| New + revised L2 artifacts (WSes + ICs) | ≤ 3 | Caps the multi-WS reconciliation surface (Decision #12) |
| Coverage gaps | ≤ 2 | An Intent that surfaces too many gaps is doing two jobs at once |

WS-028 in v3/v4 (5 IBs, 1 component, ~3,817 LOC) is the empirical witness — `--analyze` flags it over cap immediately. The retrofit at `INT-000` (Phase 1 P1.8) validated this end-to-end: the size-cap mechanism caught WS-028 exactly as designed.

### Type-specific required fields

The `Intent type:` field selects required content. `--analyze` refuses to advance to PROPOSED if the type-specific block is empty.

| Type | Required block | Default Verification predicate |
|---|---|---|
| `feature` | (none extra; Desired Outcome describes the new behavior) | full-suite-green + integration-suite-green + no-coverage-drop |
| `bug` | `Reproduction:` (verbatim failing command, log, or steps) | bug-reproduction-fixed + full-suite-green + no-coverage-drop |
| `nfr` | `Metric:` + `Target:` | metric-meets-target + full-suite-green |
| `adr-driven` | `ADR:` (driving ADR-NNN) | full-suite-green + no-coverage-drop + ADR consequence checks |
| `refactor` | `Behavior-Equivalence:` (assertion that observable behavior is unchanged) | full-suite-green + test-files-unchanged + no-coverage-drop |
| `documentation` | `Coverage-Gap:` | docs-lint-clean + cross-references-resolve |
| `environment` | `Environment-Change:` | smoke-check-passes + full-suite-green |

The default predicates live in `CLAUDE.md` §Verification Predicate Library so agents can read them at runtime without parsing this guide.

### Verification and completion

**Verification** is the Intent's machine-checkable outcome predicate (Decision #13): a list of named `cmd` checks, the ADR-029 outcome test among them. `dekspec intent verify INT-NNN` runs every check against the current content and records the result as evidence in the Intent's own execution record (`.dekspec/execution/INT-NNN/`). A `manual` entry becomes a review item that needs an independent verdict — `dekspec intent review INT-NNN --reviewer NAME --actor NAME --verdict pass` (or `fail`) — from someone who built none of the Intent's IBs, working in the `verifier` role (ADR-061).

**Completion.** `dekspec intent complete INT-NNN` writes `COMPLETE` only when the Intent is `ACCEPTED`, every IB whose `**Parent:**` is the Intent is `COMPLETE`, and the latest outcome evidence passes and matches the current content (with a current independent verdict for manual entries). `--check-only` evaluates the gate without writing. Evidence binds to content, not to a branch: any later content change makes it stale, and `dekspec intent verify` must run again.

**Diff confinement lives at the IB.** Every IB's `dekspec ib verify` checks each changed file against that IB's Scope and Protected Surfaces, and `dekspec delivery check` re-checks the whole delivery at its head. The Intent's `Components affected:` still bounds the size analysis and the commit-time check of an Intent-bound session (§Session discipline).

### Executing an Intent's IBs

An Intent's work is executed IB by IB (§Executing an Implementation Brief), usually delivered together from one worktree (ADR-058). Investigation precedes each committed plan (ADR-056 §3) — the successor of the old Explore → Plan → Code → Verify loop. Each IB's acceptance evidence is the unit-of-work discipline for that IB; the Intent's Verification is the discipline for the integrated outcome. The two compose: an IB completes only on its own current evidence, and the Intent completes only when all its IBs have and the outcome is proven.

### Recovery playbook

When an Intent hits a failure that doesn't fit the ordinary verify → fix → re-verify loop — e.g., the Verification predicate's scripts aren't in place, a child IB is blocked on a contract conflict or a scope expansion, the size cap is exceeded after decomposition, or an upstream artifact (AE/ADR/WS) is found inconsistent during implementation — the recovery playbook (Decision #18) defines the four moves: **revise scope**, **escalate to a prerequisite Intent**, **abandon and supersede**, or **route the underlying issue to its proper artifact**. A blocked IB records which of these the operator chose in its `dekspec ib unblock --decision "…"`.

### Persistence model

**Files canonical, version-controlled (Decision D2 / v5 §21).** Intents and Missions are markdown files in this repo, version-controlled with the code they govern. They are not primarily stored in any external system. External trackers (Linear, Jira, GitHub Issues, Notion, Slack) may *seed* the Mission/Intent process and may, at Phase 3+, *mirror* a small set of frontmatter fields read-only for board visibility — but the file in the repo is the source of truth at every status transition. The principle, in one line: anything an LLM (or a thoughtful human) iterates on heavily belongs in version control, not a database.

This rules out three failure modes that have no good resolution: round-trip latency between the agent and the tracker; merge conflicts between human-edited tracker descriptions and agent-revised file content; schema drift when the Verification predicate format changes (files migrate via `sed`; tracker schemas are global and effectively unmigrateable).

**No custom UI.** DekSpec does not build a custom Mission/Intent management UI. If a board view is wanted, it comes from a thin one-way mirror to an existing tool (deferred to Phase 3+) — never from a bespoke tool.

### Capture and triage

**DekSpec is initiated by a human running `/write-intent` or `/write-mission` (Decision D3 / v5 §22).** Capture (an idea worth pursuing), triage (the human deciding it warrants an Intent or Mission), and authoring (running the skill) are three distinct activities; only capture belongs in a tracker. Webhook-driven creation from a tracker is forbidden — it would smuggle the tracker back into the source-of-truth role through the back door.

The optional `source:` field on each Intent records provenance — the captured URL, ticket, message, or note that motivated the work. Provenance is not parentage: there is no enforced 1:1 relationship between a captured item and an Intent. One Linear issue might split into a 4-Intent Mission; three Linear issues might collapse into one Intent; many Intents have no captured source at all.

### Linkage to the AE corpus

Every Intent has a mandatory `Linked Architecture Elements:` section listing at least one existing AE-NNN reference (Decision D12). This is **distinct** from `Components affected:`:

- **Linked Architecture Elements** describes spec-graph linkage — which architectural slices the Intent revises. Audit-v2 rule **L7** verifies every entry resolves to an existing AE file.
- **Components affected** describes blast radius — which file paths the diff is confined to. Audit-v2 rule **L7** also verifies these globs resolve to existing paths in the repo.

Both fields are required, single-purpose, and neither subsumes the other. An Intent that doesn't shape any AE is either too small to warrant an Intent or describes a slice that itself needs an AE first — surface and stop.

### Skill: `/write-intent`

The `/write-intent` skill owns the authoring side of the Intent lifecycle:

- **(no flag)** — Creation Mode. Author a new Intent from the engineer's description (provisional by default, ADR-030); populate Autonomy `medium` (ADR-059) and the type-default Verification.
- **`--analyze`** — Top-down coverage check, bottom-up archaeology (delegates to `/recover-specs`), 5 hard size caps, type-specific field validation, WS-fan-in per IB, drift checks (audit-v2 D19 / D20), Mission Autonomy ceiling validation. Promotes DRAFT → PROPOSED on a clean run; an over-cap result records a P2 open issue and the Intent stays DRAFT.
- **`--accept`** — Engineer-only gate; PROPOSED → ACCEPTED.
- **`--decompose`** — Writes the Intent's IBs via `/write-ibs` (each with `**Parent:** INT-NNN`); for `type: bug`, the first IB's acceptance names the failing reproduction test. Status stays ACCEPTED. No beads are produced.
- **Completion** — never a hand edit: `dekspec intent verify` records the outcome evidence and `dekspec intent complete` writes `COMPLETE`.
- **`--sync`**, **`--audit`**, **`--review`**, **`--amend`**, **`--supersede`** — post-merge catch-up, health check, interactive walk-through, mid-flight scope changes, and replacement.

The full skill spec lives at `plugins/dekspec/skills/write-intent/SKILL.md`.

---

## Missions

**Missions (`MSN-NNN`) are the long-horizon container above Intents.** A Mission holds an ordered queue of child Intents that share an outcome, a feature flag, a release boundary, or a kill criterion. Missions sit *above* Intents but are not a layer of the spec graph — they sequence and contextualize Intents without producing code themselves. The cross-section diagram from §Intents shows the Mission as the optional cap above the horizontal Intent driver.

**Conditional creation rule (Decision #20).** A Mission is created when **any** of:

- Work plausibly decomposes into more than one Intent at first sketch (≥ 2 Intents)
- A feature flag will guard partial state during rollout
- Multiple Intents need to share an outcome, an out-of-scope contract, or a kill criterion
- Work spans more than ~1 week of execution

**Single-Intent work skips the Mission layer entirely** — small bug fixes, single features, isolated NFR passes do not need the Mission ceremony. The `/write-mission` skill enforces this gate at Creation Mode and refuses single-Intent-shaped requests. Lazy Mission creation is treated as Mission-debt.

### Lifecycle

```
PROPOSED → ACTIVE → COMPLETE
             │
             └─► KILLED                  (kill criteria triggered or owner abandons)

any non-terminal → SUPERSEDED            (substantive near-immutable change)
```

| Status | Transition trigger | What happens |
|---|---|---|
| `PROPOSED` | `/write-mission <description>` | Near-immutable section written; awaiting the engineer's authorization |
| `ACTIVE` | `--activate` (engineer-only; near-immutable section complete (T17) and the First Intent named) | Programme authorized; child Intents proceed |
| `COMPLETE` | `--complete` (every queued Intent `COMPLETE`, flag on and flag-removal Intent `COMPLETE` if any, Mission Verification passes) | Outcome verified; Mission archived. A failing predicate leaves the Mission `ACTIVE` |
| `KILLED` | `--kill` (kill criterion triggered or engineer abandonment) | Rollback executed; archived with reason |
| `SUPERSEDED` | `--supersede` (substantive near-immutable change needed) | Successor Mission created; source archived |

*ADR-057 renamed `TODO` to `PROPOSED` and retired `COMPLETING` (verification now runs inside `--complete`); `dekspec migrate` maps both.*

### Mission rigor: two-section structure

A Mission is rigorous *up front* on a small, durable set of fields and *continuously revised* on everything else. The two-section structure is the rigor: the contract is committed before any child Intent lands, and the runtime state is captured as it evolves.

**Near-immutable section** (8 fields, written before any child Intent leaves DRAFT):

| Field | Why it's near-immutable |
|---|---|
| **Outcome** | The user-observable change. If this changes, the Mission is wrong-shaped — supersede it, don't edit it |
| **Mission Verification** | Machine-checkable, user-observable predicate. Stronger than per-Intent Verification — a behavioral assertion across the integrated system |
| **Out-of-scope** | Explicit non-goals. Drift detection lives here — when a child Intent's Components affected reaches into out-of-scope territory, surface and refuse |
| **Flag strategy** | Flag name, default state, who flips it on, removal Intent. `none` allowed with rationale for non-flag-gated Missions |
| **Rollback plan** | Concrete steps to undo a partially-shipped Mission. Executable without the original author |
| **Kill criteria** | Observable conditions that trigger `KILLED`. Each criterion is measurable, not subjective |
| **Autonomy ceiling** | Maximum Autonomy any child Intent may have. No Intent may exceed this (audit-v2 L8) |
| **First Intent** | The first Intent the Mission creates. Concrete enough to start; no commitment to subsequent Intents at this stage |

Substantive changes to near-immutable fields require `/write-mission --supersede`, which creates a successor Mission and marks the source `SUPERSEDED`. Routine `--review` revisions edit only the live section.

**Live section** (revised continuously via `/write-mission --review`):

- **Intent queue** — ordered list of child Intents. As work proceeds, sketches become drafts, drafts become `COMPLETE`. Order is execution order — at most one Intent in active status at a time within the Mission (ADR-016), so the queue is also the serialization queue
- **Discovered prerequisites** — coverage gaps surfaced during child Intent `--analyze` runs that retroactively belong to the Mission as a whole
- **Burndown** — COMPLETE / Estimated total / Sketches. Surfaces remaining work; not a hard gate
- **Flag transitions** — every flag flip recorded with date, action, observed effect
- **Notes** — working notes, calibration findings (the place where rigor-recalibration insights for FOLLOW.2 land)

### Mission Verification

Mission Verification is **stronger than per-Intent Verification** (Decision #20). Per-Intent Verification proves "this change works" — typically `pytest -q` plus type-specific checks. Mission Verification proves "the integrated system delivers the outcome" — typically a behavioral assertion or an integration-level evaluation that spans multiple components and could not be expressed as a per-component test.

The shape mirrors per-Intent Verification (yaml cmd-check list), but the checks are at a higher level of integration:

```yaml
- name: <user-observable-check-1>
  cmd: <command that exits 0 only when the Mission outcome is true>
- name: <integration-or-behavioral-check-2>
  cmd: <command>
```

The `--complete` flag runs this predicate as the gate on `ACTIVE → COMPLETE`. Fast-fails on first non-zero exit; on failure the Mission stays `ACTIVE` with the failing check recorded and surfaced for engineer fix.

### Mission ↔ Intent linkage (audit-v2 L8)

When a child Intent's `Mission:` field references a Mission, audit-v2 rule **L8** verifies the linkage is bidirectional:

- The Mission's Intent queue lists the child Intent
- The child Intent's `Mission:` field references this Mission
- The child Intent's `Autonomy:` value ≤ the Mission's `Autonomy_ceiling`

L8 runs in `dekspec audit linkage` and `dekspec doctor`, and `/write-mission --audit`, `--activate` and `--complete` re-check it. Keep the Mission's Intent queue current with `/write-mission --review` as child Intents complete.

### Skill: `/write-mission`

The `/write-mission` skill owns the full Mission lifecycle. Phase 2 flags (all implemented):

- **(no flag)** — Creation Mode. Author a new Mission from the engineer's description; gate-check that work justifies a Mission (refuse single-Intent-shaped requests); draft the near-immutable section in full; save as `PROPOSED`.
- **`--review`** — Revise the live section. Refuses to edit near-immutable fields; surfaces substantive-change attempts as `--supersede` candidates.
- **`--activate`** — `PROPOSED → ACTIVE`. The engineer authorizes the programme; refuses unless the near-immutable section is complete (T17) and the First Intent is named.
- **`--complete`** — `ACTIVE → COMPLETE`. Promotion gates: every child Intent `COMPLETE`, flag (if any) on, flag-removal Intent (if any) `COMPLETE`, Mission Verification predicate evaluates true.
- **`--kill`** — Terminal abandonment. Records kill reason + rollback action; moves to Archive.
- **`--supersede`** — Creates successor Mission; marks source `SUPERSEDED`.

The full skill spec lives at `plugins/dekspec/skills/write-mission/SKILL.md`.

### When a Mission is **not** the right answer

Some shapes look like Missions but aren't:

- **Single-component refactor across many files** — that's still one Intent (with `type: refactor`), even if it touches many files. Components affected may include all of them; Mission ceremony is overhead.
- **A multi-stage rollout of one feature with no flag, no shared kill criterion, and no decomposition into independent Intents** — that's one Intent shipped through `--decompose`. The Intent's IBs already provide the multi-stage rigor.
- **A backlog grouping** — Missions are *committed* to land; a backlog grouping is exploratory. Backlogs live in the tracker (Decision D3 / v5 §22) until they're triaged into actual Mission or Intent commitments.

If the work doesn't pass the conditional rule, run `/write-intent` directly — or, for a bounded change, write one IB. The Mission rigor is too much overhead for work that fits one Intent.

---

## Roles

13 roles across 3 categories. Roles load domain knowledge the model doesn't
reliably have by default. All role definitions and prompts live in
`dekspec/project-context.md`.

These are *expertise* roles a project maintains for its own specification
work. They are distinct from DekSpec's six **Agent Role Specifications**
(specifier, spec reviewer, implementer, code reviewer, verifier, auditor —
ADR-061), which ship inside the library, govern how dispatched agents work,
and are never authored or selected by a project.

### Knowledge Expansion — Technology *(Dektora-specific)*

| Role | Triggers when spec touches |
|------|--------------------------|
| ML / Model Behavior Expert | Hidden-state injection, M-RoPE position IDs, KV cache |
| Quantization / Precision Expert | Quantization, tensor precision, serialization round-trips |
| CUDA Multi-Process Expert | Process isolation, CUDA device assignment, GPU memory |
| Graph / Multi-Store Expert | Mind map, shadow graph, multi-store write ordering, timeline, shadow timeline, topic segmentation, decay/reactivation scoring, quantization tier assignment |

### Knowledge Expansion — System Reasoning *(Dektora-specific)*

| Role | Triggers when spec touches |
|------|--------------------------|
| Embedding Space Geometer | Scoring, comparing, or compressing embeddings |
| Pipeline Sequencing Analyst | Reordering, parallelizing, or adding pipeline stages |

### Universal Roles

| Role | When |
|------|------|
| Writer | Every artifact — drafts from engineer's description |
| Options Architect | Genuine architectural alternatives exist (conditional) |
| Critic | Every spec — after all other passes (always) |
| Planning Agent | Finalized spec, Intent or change request → Implementation Briefs |
| Coding Agent | Executes an accepted IB — investigates, plans, implements within its obligations; fungible, any agent any IB |
| Eval Agent | Eval conditions for IBs whose outcome involves model output, before execution |
| SDET | Before authorization — acceptance tests for the IB's acceptance conditions, a basis per new assertion, genuine red on `dekspec ib floor` (ADR-062) |
| Reviewer | Independent verdict on each IB's delivery — never the builder (ADR-057) |

**No role needed for:** Python patterns, REST API design, PostgreSQL, FastAPI/Flask, React, pytest, shell scripting. Claude already knows these — use a good brief instead.

---

## The Spec Creation Process

```
Writer drafts spec from engineer's description
  ↓
Engineer reviews scope and intent
  ↓
Expertise Audit — which roles apply?
  ↓
Knowledge Expert passes — serialize, engineer edits after each:
  ML Expert → Quantization Expert → CUDA Expert → Graph Expert
  → Embedding Geometer → Pipeline Analyst (only triggered roles)
  ↓
Options Architect (if genuine architectural alternatives exist)
  ↓
Engineer decides → write ADRs for each decision
  ↓
Critic pass 1 — full spec
  ↓
Engineer resolves findings
  ↓
Non-trivial changes? → Critic pass 2 on changed sections only
  ↓
Final spec
```

**Why serialize (not parallel):** Each role reads what the previous one added. Conflicts surface during production, not after.

**Critic stop condition:** Would this finding cause a coding agent to make a wrong implementation decision? If no — ship the spec. Never run a third pass; split the spec instead.

**Critic also verifies the audit:** The Critic's pass 1 prompt includes a check for missed expertise audit triggers — if the spec touches a domain but shows no evidence of that role's pass, the Critic flags it. This catches the case where the engineer missed a trigger during the self-administered audit.

---

## Expertise Audit

Run before every Working Spec.

```
Spec touches injection, position IDs, KV cache?          → ML Expert
Spec touches quantization, precision, serialization?     → Quantization Expert
Spec touches CUDA device or process isolation?           → CUDA Expert
Spec touches mind map, shadow graph, multi-store?        → Graph Expert
Spec touches timeline, topic segmentation, decay,
  shadow timeline, or quantization tier assignment?      → Graph Expert (timeline scope)
Spec touches embedding scoring or compression?           → Embedding Geometer
Spec touches pipeline stage ordering?                    → Pipeline Analyst
Spec depends on an undocumented decision?                → write ADR first
```

ADRs can be written at three points: before spec creation (known undocumented decisions), during spec creation when the audit flags one, and inside `/write-ws` when the Options Architect surfaces an architectural choice. All three are valid — the trigger determines the timing.

---

## Subdomain Classification

Every Architecture Element declares a subdomain classification that calibrates specification intensity. This follows Domain-Driven Design's strategic design principle: invest maximum rigor where the system's competitive advantage lives, and move faster on commodity components. The classification cascades from Architecture Element to all Working Specs within that subsystem.

### Classification Levels

| Level | Definition | Specification Intensity |
|-------|-----------|------------------------|
| **Core** | Novel capability that constitutes Dektora's competitive advantage. Failure here produces plausible-but-wrong results with no error signal. | Full expertise audit with rationale for every role (triggered or not). All conditional contract sections evaluated. Eval hooks mandatory for model output. Options Architect always consulted. |
| **Supporting** | Domain-specific infrastructure necessary for the core to function. Important but not the core innovation itself. | Expertise audit runs only triggered roles — non-triggered roles omitted from the audit record (no "why not" rationale needed). Conditional contract sections only if domain constraints trigger them. |
| **Generic** | Commodity patterns well-understood by the model (REST APIs, config loading, CRUD, process management). | Simplified audit: only roles that fire. Critic pass focuses on interface correctness and ADR compliance, not domain depth. Lighter business rules expected. |

Each Architecture Element declares its classification. See `dekspec/architecture-elements-index.md` for the current classification of every subsystem.

### How Classification Affects the Workflow

- **Expertise audit:** Core subsystems require rationale for every role (triggered or not). Supporting and Generic subsystems document only triggered roles.
- **Options Architect:** Always consulted for Core. Only consulted for Supporting/Generic if genuine alternatives surface during expert passes.
- **Conditional contract sections:** Core evaluates all five domains. Supporting/Generic evaluate only triggered domains.
- **Business rules:** Core specs are expected to have rules for every active silent failure domain. Supporting specs have rules for triggered domains. Generic specs focus on interface correctness.
- **Eval hooks:** Mandatory for Core IBs whose outcome involves model output. Required only if explicitly triggered for Supporting/Generic.

Classification is forward-looking — existing PROPOSED specs are not retroactively modified. When a spec is unlocked for revision, the classification's intensity rules apply.

---

## ADRs

An ADR is a permanent written record of a single architectural decision — what was decided, why that option was chosen over the alternatives, and what consequences the decision carries. Code shows what was built, not why. An ADR makes the reasoning permanent and findable.

**What it is not:** not a design document, not a requirements document, not a meeting note.

### How it is used

**Ends recurring debates.** Write the ADR once, link it when the same question surfaces again. The debate ends.

**Prevents well-intentioned reversals.** A future engineer or coding agent won't undo a deliberate decision if the reasoning is recorded. Without the ADR, "fixing" the code back to the wrong approach looks reasonable.

**Governs all downstream work (Layers 2–4).** A Working Spec that contradicts an ADR must be corrected. An Implementation Brief that contradicts an ADR must be corrected. Code that contradicts an ADR must be corrected. Within Layer 1, ADRs are constrained by Architecture Element principles and System Vision scope — an ADR that deviates from an Architecture Element's stated principle must acknowledge the deviation explicitly.

**Captures inferred decisions.** Several major Dektora decisions are baked into the code without being written down. ADRs formalize these before they become invisible load-bearing assumptions.

All architectural decisions use one mechanism: ADRs. There is no lightweight alternative. One artifact, one location, one format.

### Rules

**One decision per ADR.** Never combine two decisions, even if made together.

**Verb-first, specific title.** The title alone must tell you what was decided. "Use in-memory shadow graph as authoritative hot-path read layer" not "Graph caching strategy."

**Options Considered is optional.** Include when genuine alternatives were evaluated. Omit when documenting a straightforward architectural decision.

**Lock when stable.** ADRs progress through `DRAFT → PROPOSED → ACCEPTED → LOCKED`. Move to `LOCKED` when the decision has proven stable. Once `LOCKED`, only editorial amendments (typos, grammar — no meaning change) are permitted. Unlock back to PROPOSED for substantive changes.

**Past tense in Context.** The Context and Decision Drivers section describes what was true when the decision was made, not what is true now. Decision drivers are listed explicitly, not buried in prose.

**Specific rationale.** The Decision section states why this option was chosen in this system's specific context — not generic praise of a technology.

**Validation is required.** Every ADR states how to confirm the decision was correct after implementation — observable criteria, metrics, or conditions that would trigger reconsideration.

**Links.** Reference related ADRs, specs, or external resources.

Full backlog, format, and index: `dekspec/adr-index.md`

---

## Test Strategy

### Tests vs. Evals

These are different things. Both are required where they apply. Neither replaces the other.

```
Tests    → deterministic behavior: given input X, output Y always
           binary pass/fail, fast
           acceptance tests written and oracle-reviewed before authorization; development tests any time

Evals    → probabilistic behavior: model output within acceptable range
           threshold: passes at ≥ N% of cases, slower
           written by the Eval Agent before execution; an IB acceptance condition
           (`command:` with its own threshold), protected by the acceptance baseline
```

**Decision rule:** does this IB's outcome involve model output? If yes — it needs both test and eval conditions. If no — tests only.

### Test Pyramid

Tests map to DekSpec layers. Each level has a distinct source artifact, lifetime, and location:

| Level | Source Artifact | Location | Lifetime | When Written |
|-------|----------------|----------|----------|-------------|
| Contract assertions | IC/WS constraint tables | `tests/contracts/` | Permanent (regen on spec change) | Auto-generated from constraints |
| Acceptance tests | IB acceptance conditions (`AC-n` `pytest:` nodes) | where the condition names them | Permanent; protected by the acceptance baseline once the IB is accepted | `/write-tests` before authorization, then oracle-reviewed by `/dekspec:review-ib` (ADR-062) — never by the builder; an asset added after the baseline only through `dekspec ib amend`, oracle-judged by the completing reviewer |
| Development tests | the builder's own discoveries | anywhere in Scope | kept or removed at the builder's judgment; freely editable | during execution |
| Property-based invariants | WS business rules + formulas | `tests/properties/` | Permanent | Hand-crafted (Hypothesis) |
| Regression tests | a fixed defect's reproduction | `tests/regression/` | Permanent (with provenance) | as the acceptance of the bug IB that fixes it |
| Integration tests | cross-IB data flow + ICs | `tests/integration/` | Permanent; run by the `integration_command` of `dekspec delivery verify` | with the IB that introduces the flow |
| Behavioral evals | WS eval hooks | `tests/evals/` | Permanent | `/write-evals` before execution |

### Protected acceptance, no regeneration

Tests are never auto-regenerated from spec prose — that produces tautological or vacuous tests. Acceptance tests are written deliberately (by `/write-tests` or an SDET — never the builder) and named by the IB's conditions.

**Every expectation carries an independent basis (ADR-062).** Protection makes an acceptance test tamper-evident; it does not make it right. A new or changed acceptance assertion therefore records, beside it (or once in the test's docstring when one basis covers all of its assertions), a `Basis:` line saying where its expected result comes from: a worked example cited from an approved obligation, an independently established fixture (and how it was established), an external reference, or an invariant or metamorphic property justified from the contract. A basis on a class or module is reported as inherited. An expected value obtained from the system under test or its helpers and constants, a repetition of the implementation's derivation, or a blessed observation is not independent. A `command:` condition's basis is its condition text: what the command checks and why that result shows the behavior — never a criterion the change controls. Nodes whose test existed unchanged before the IB was first committed are preservation nodes: they must pass and need no added basis.

**Red on the behavior, recorded.** A test for an entry point that does not exist yet ships with a behavior-free surface skeleton — the contracted entry point returning a neutral result, never raising — so its assertion fires on the missing behavior. `dekspec ib floor IB-NNN` runs the acceptance runner and reports, per condition and node, new or preserved, the failure kind (`genuine-red` only for an assertion failure with no usage or import signature, in-process or from a command the test runs), the failure line, the declared basis, and the floor digest the baseline would record. It changes nothing.

**The oracle review before the baseline.** An independent reviewer — `/dekspec:review-ib`'s `acceptance-oracle` lens, a fresh-context `spec-reviewer`, never the test author or a builder — reads the test sources, the skeleton and the floor report and judges, per criterion, whether each basis is independent and represents the required behavior; a system-derived, copied or blessed expectation is blocking. A passing review is recorded in the IB's own Amendment Log as `| <date> | Review | Floor reviewed: PASS — digest <64 hex> — <n> new nodes genuine red with a basis, <m> preserved passing (review-ib acceptance-oracle) | <reviewer identity> |`, and the authorizer takes the baseline only when its digest matches. `/implement` readiness refuses an IB whose named nodes or declared assets are missing from its baseline, or whose baseline digest no such row names. The order is one and the same everywhere: write the IB (`dekspec ib lint`, `dekspec ib propose`) → `/write-tests` → `/dekspec:review-ib` → `dekspec ib accept`. This establishes a workflow and reproducible evidence, not the correctness of every assertion.

Once an IB is accepted, its acceptance tests are protected (ADR-057): the baseline pins the contract, every acceptance asset (`Basis:` lines included) and the runner inputs. Before a run starts, the authorizer may refresh it (`dekspec ib baseline IB-NNN --reason "…"`) — after the oracle review of any changed tests has recorded a new `Floor reviewed:` row. After the run starts, the builder may not edit, skip, deselect, delete or first create them to claim success — a genuinely invalid condition, or a missing test, is corrected only by `dekspec ib amend IB-NNN --reviewer NAME --reason "…"`, and the completing reviewer oracle-judges every amended or added asset's basis before acknowledging it. Development tests outside the acceptance assets stay freely editable. A useful development test becomes permanent by being named in a later IB's acceptance or kept under `tests/regression/` with a provenance docstring naming the WS rule or IC constraint it guards.

### Golden I/O

For numerical or data-transformation IBs, the engineer writes 2-3 concrete input/output pairs with exact values as acceptance conditions of the IB. This is the single most effective defense against AI self-validation — the implementing agent cannot game a test whose expected output was fixed, and protected, before implementation began.

### Contract Tests

Dtype, device, shape, and value range assertions can be derived from spec and IC constraint tables and placed permanently in `tests/contracts/`. Nothing regenerates them automatically: `dekspec compile <IC> --emit contract-test` produces a scaffold whose every test starts as a `pytest.skip("CONTRACT_STUB: …")` stub, and `--emit ci-gate` a CI job that runs them; an engineer writes the assertions and re-emits (and reconciles) when the IC changes. Until then the contract is checked by nothing. Business-rule logic tests require human or coding-agent authorship — the gap between spec language and code is in the test setup, not the assertion.

### Property-Based Tests

Targeted `tests/properties/` directory for invariants most resistant to AI gaming:
- Serialization/deserialization round-trips
- Quantization bit-budget invariants
- Wave compression properties (constant output size)
- Idempotency properties

These use Hypothesis to generate inputs the coding agent never saw.

### Tests That Resist AI Gaming

- **Round-trip tests:** `serialize(deserialize(x)) == x`
- **Property assertions on output:** "Output tensor has same shape as input"
- **Cross-function consistency:** "Output of A, fed into B, produces valid result"
- **Numerical bounds:** "Quantized tensor has at most 2^N unique values"
- **Golden I/O from specs:** Expected output fixed before implementation

### Tests That Are Easy to Game (Avoid)

- Mock-based interaction tests ("function was called N times")
- Return-type-only assertions
- "No exception raised" tests
- Tests that compute expected values using the same logic as the implementation

### Spec-Change Cascade

A spec change never requires editing copies inside IBs — IBs reference obligations, and `dekspec ib context` regenerates from the changed source. `/write-ibs --resync` repairs references that no longer resolve (a moved section, a superseded ADR). Contract tests in `tests/contracts/` do not regenerate: re-emit the scaffold (`dekspec compile <IC> --emit contract-test`) and reconcile the hand-written assertions (§Contract Tests). Evidence and verdicts bound to the old context manifest go stale (ADR-057), so affected IBs re-verify, and are re-reviewed, before they complete.

---

## Working Spec Structure

Standard sections: what this does, what it does NOT do, interfaces, business rules, failure behavior, open issues.

**Dektora additions** (include only when applicable, delete otherwise):
- **Model behavior contract** — when spec touches injection/model
- **Graph behavior contract** — when spec touches shadow graph/Neo4j
- **Timeline behavior contract** — when spec touches topic segmentation, quantization tier assignment, decay/reactivation, or shadow timeline/PostgreSQL consistency
- **Quantization contract** — when spec touches tensor operations
- **Eval hooks** — for every behavior involving model output only; deterministic behaviors become acceptance conditions of the IBs that implement them, not eval hooks

**Rules:**
- Every business rule must be testable
- Every failure mode must have a stated behavior
- Open questions are stated explicitly — never buried in vague prose
- 1-2 pages maximum — if you need more, split the spec

---

## Implementation Brief (IB)

The IB is the smallest governed work contract, and an accepted IB is executed directly — there is no second tier of authored work items (ADR-056). One IB is one bounded change with its own acceptance; it may be delivered alone or with sibling IBs from one worktree and pull request (ADR-058). A Working Spec may produce several IBs (one per component or data-flow stage), an Intent's `--decompose` writes its IBs, and a bounded change with no parent starts from `dekspec ib new <slug> [--title "…"] [--parent INT-NNN|WS-NNN|MSN-NNN]` or `/write-ibs` with a plain description.

The format is `templates/implementation-brief-template.md`:

| Section | Authority (ADR-055) | Holds |
|---|---|---|
| Header: `**Status:**`, `**Authority policy:**`, `**Parent:**`, `**Depends on:**`, `**Spec impact:**` | — | lifecycle; `delegated` or `legacy`; optional parent (context only); IBs that must be `COMPLETE` first; the AEs/ADRs/ICs/WSs this delivery must modify |
| Outcome, Rationale | — | the observable end state, and why — enough for a reviewer to judge the IB without a parent artifact |
| Scope (+ Out of scope) | binding | globs where change is allowed without further permission |
| Obligations | binding | references `- **O-n** → ADR-/IC-/WS-/SP-/AE-NNN [§Section]`, or `(local)` obligations whose canonical home is this IB |
| Protected Surfaces | binding | files, or `path::symbol` for one Python function or class, that may not change even inside Scope |
| Acceptance | acceptance | a YAML list of `AC-n`, each with a `condition` and exactly one `verify`: `pytest: [nodes]`, `command: "…"`, or `review: "…"`; plus any extra protected acceptance assets (fixtures, golden data) |
| Implementation Hypothesis | hypothesis | likely files, approach, reuse — revisable after investigation |
| Environment Prerequisites | precondition | probe commands `dekspec ib start` runs; a failed required probe blocks the run truthfully |
| Open Issues, Amendment Log | — | as for every artifact |

Rules of the format:

- **Reference, don't copy.** An obligation owned by an ADR, IC, WS, SP, AE or the Constitution is referenced, never restated; `dekspec ib context` delivers its canonical text (§Authority and Conflict Resolution). The old practice of copying spec context verbatim into the IB, and from the IB into beads, is retired.
- **Acceptance covers observable behavior, integration through the real entry point, and failure behavior** — not only the happy path. Each condition names exactly one verification. An eval is an acceptance condition too: a `command:` that exits non-zero below its own threshold.
- **Spec impact is checked.** When a change alters architecture or a contract, name the governing artifacts under `**Spec impact:**`; `dekspec ib verify` fails unless the delivery modifies them.
- **Executable before authorization.** `dekspec ib lint IB-NNN` checks the contract is complete and every reference resolves to an approved, in-force source; `dekspec ib propose` is lint-gated.

**Lifecycle.** `DRAFT → PROPOSED` (`dekspec ib propose`) `→ ACCEPTED` (`dekspec ib accept` — the authorization to execute, which takes the acceptance baseline) `→ COMPLETE` (only `dekspec ib complete`; the `T-IB-COMPLETE-WITHOUT-EVIDENCE` audit rule (P1) catches a hand edit), plus `SUPERSEDED` and `DEPRECATED`. Before acceptance `/dekspec:review-ib` reviews the contract and — mandatory for an IB with `pytest:` conditions or declared assets — oracle-reviews its acceptance tests and floor report; its findings stay Open Issues, and a passing floor review is a `Floor reviewed:` Amendment Log row (ADR-062). Progress is never a status — `dekspec ib status IB-NNN` derives it from the execution record.

**IB location.** IBs live under `dekspec/impl-briefs/` (`dekspec ib new` writes there directly). A repo may keep the `queued/` / `active/` / `completed/` folders; the `T-STATUS-IB-FOLDER` audit rule checks each IB sits in the folder mapped to its status band.

### Authority policy and legacy IBs

Every IB declares `**Authority policy:** delegated` or `legacy`. `delegated` applies the three categories of ADR-055. `legacy` keeps the ADR-049-era meaning exactly: Files to Modify is an allowlist, Constraints & Decisions and Do Not Touch are binding, and any unlisted file requires escalation. An IB with no marker is legacy; `dekspec migrate` stamps the marker on every pre-existing IB so the policy is explicit and reviewable.

A legacy IB cannot complete through `dekspec ib complete`. To bring one in-flight IB (PROPOSED or ACCEPTED) under the new model, **adopt** it deliberately, never by bulk relabeling:

1. Rewrite it to the new format with `/write-ibs --adopt IB-NNN` — classify each legacy constraint as a binding obligation (and reference its canonical home) or as implementation hypothesis, write the Acceptance block, and set `**Authority policy:** delegated`.
2. Record the switch: `dekspec ib adopt IB-NNN --reason "…"` refuses until the rewritten contract is executable, then writes the Amendment Log row and, for an ACCEPTED IB, the adoption baseline. It migrates legacy work only: someone independent of the run's builders records it, the IB must have been committed under the legacy policy, and it is refused once a delegated baseline exists — acceptance changes after that are `dekspec ib amend`.
3. If the IB had legacy code beads, `dekspec ib import-beads IB-NNN [--source .beads/issues.jsonl]` moves them into its execution record as tasks, keeping owner, status, dependencies and closure evidence.

### IB Count and Spec Size

| IB count | Assessment |
|----------|-----------|
| 1-3 | Normal — focused feature or component |
| 4-6 | Acceptable — complex subsystem with multiple interacting components |
| 7-10 | Warning — review whether this is actually two subsystems in one spec |
| 10+ | Too large — split the spec |

The real signal isn't the count. Split the spec if:
- A new engineer can't understand the full scope in under 30 minutes
- You can't describe the IB dependency graph from memory
- The spec spans two silent failure domains (injection, quantization, graph, timeline, CUDA) — those domain boundaries are almost always the right spec boundaries

There is no universal size limit on an IB itself — no hour, context-window or one-file-per-unit rule (ADR-056). An IB is the right size when its acceptance can be judged as one unit.

### Changing Artifacts After Downstream Work Exists

Going back is always allowed. Changes cascade downward through the layers — and because IBs reference their obligations instead of copying them, most of the cascade is regeneration, not hand reconciliation.

```
Layer 1 change (ADR added/revised/superseded, Architecture Element amended)
  → Review all Layer 1 artifacts that reference it for consistency
  → Review affected Layer 2 artifacts (Working Specs, Interface Contracts)
  → IBs that reference it get the new text at the next `dekspec ib context`;
    a binding reference to a SUPERSEDED ADR blocks propose/accept/start until
    the IB is re-pointed at the successor (an IB amendment)
  → Evidence and verdicts bound to the old context manifest are stale:
    re-verify and re-review before completion

Layer 2 change (Working Spec or Interface Contract revised)
  → /write-ibs --resync — update or retire affected IBs
  → Same staleness rule for evidence already recorded

Layer 3 change (IB revised)
  → DRAFT / PROPOSED: edit freely
  → ACCEPTED, run not started: edit, repeat the oracle review of the changed tests
    (`/dekspec:review-ib`, a new `Floor reviewed:` row), then
    `dekspec ib baseline IB-NNN --reason "…"` re-pins the contract and acceptance assets
  → Run started: a change to a binding or acceptance section is an amendment —
    `dekspec ib amend IB-NNN --reviewer NAME --reason "…"` (an independent reviewer;
    the completing verdict must acknowledge it). A change to the Implementation
    Hypothesis needs nothing: revise the plan (`dekspec ib plan`).
```

The engineer decides when a change is needed — a new ADR, a role pass that reveals a wrong assumption — and cascades it through all affected layers.

Work already done is never silently discarded: a plan revision cannot drop a completed task or its evidence, and a `COMPLETE` IB changes only through a successor IB (`SUPERSEDED`).

**Cascade implementation reference:**

| Trigger | Authoritative skill or verb | Reference |
|---------|---------------------------|-----------|
| Layer 1 change (ADR / Architecture Element revised) | manual (engineer-driven); review propagates through `/write-ws --audit` and `/write-ic --audit` on downstream artifacts | §Changing Artifacts After Downstream Work Exists |
| Layer 2 change (Working Spec revised, IBs already exist) | `/write-ibs --resync` | `plugins/dekspec/skills/write-ibs/SKILL.md` §Resync Mode |
| Layer 3 change (IB contract revised after acceptance) | `dekspec ib baseline` (before the run starts) / `dekspec ib amend` (after) | ADR-057 §The acceptance contract |
| Interface Contract unlocked | `/write-ic --unlock` then downstream impact check | `plugins/dekspec/skills/write-ic/SKILL.md` |
| ADR superseded | `/write-adr` (supersession fields) + re-point binding references in dependent IBs | `plugins/dekspec/skills/write-adr/SKILL.md` |

### IB Boundaries and Production Gates

The IB boundary is what can be accepted as a unit. Inside an IB, the executor may split the work into internal tasks for its own reasons — ownership, dependencies, verification, recovery — or do it in one continuous run; tasks are execution records, carry no authority, and never replace the IB's acceptance (ADR-056 §2). No production validation inside an IB.

Production gates sit **between IBs**, not within them. When you need production validation before proceeding, that is the signal you have two IBs, not one.

**Common pattern — refactoring before new implementation:**

```
IB-1: Refactor [component]
  Outcome: restructured; observable behavior unchanged
  Acceptance: the existing suite passes; AC-2 (review): no public signature changed
  Production gate: deploy, verify [specific observable] unchanged

IB-2: Implement [new behavior]
  Depends on: IB-1
  Environment Prerequisites: a probe for IB-1's observable in production (when one can be scripted)
```

`dekspec ib start` refuses IB-2, and `dekspec ib ready` omits it, until IB-1 is `COMPLETE`. The production observable itself is **engineer discipline** unless it can be probed — then it belongs in IB-2's Environment Prerequisites, where a failed required probe blocks the run truthfully. Either way the observable must be stated specifically in the IB — not "looks good" but a concrete checkable signal. If it can't be stated specifically, the gate criterion belongs in the spec first.

**Two IB dependency types:**

| Type | Meaning | Enforced by |
|------|---------|------------|
| Technical | Next IB's code depends on this IB's code | `**Depends on:**` — `ib ready` / `ib start` wait for `COMPLETE` |
| Production gate | Next IB depends on IB-1's behavior verified in production | Engineer discipline, or a required Environment Prerequisite probe |

---

## Executing an Implementation Brief

Crossing from Layer 3 to Layer 4 is a phase transition: the contract is authorized, and the work is now to satisfy it with evidence. The engineer's role shifts from "is the contract right?" to "does the evidence show it is met?"

The engine is the `dekspec ib` verb family (AE-011). Every step appends to the IB's **execution record**, `.dekspec/execution/<IB>/record.jsonl` — an append-only, hash-chained event log of ownership, investigation, plan and task revisions, attempts, deviations, blockers, acceptance baselines, evidence, review verdicts and completion. It is committed durable state for audit and recovery, never a spec artifact: nothing in it is compiled into IR, projected into `AGENTS.md`, or copied back into specs (ADR-056). A hand edit breaks the hash chain and fails the completion gate. `/orchestrate-coding-session` drives these steps for the ready set; any agent, or a human, can run them directly.

All `ib` verbs take `--at`, `--dekspec-root`, `--actor` (default `$DEKSPEC_ACTOR`, then `git config user.name`) and `--json`. Exit codes: `0` ok · `1` refused or not satisfied · `2` usage · `3` blocked. Full flag reference: `docs/cli-reference.md` §ib.

### 1. Pick up and start

- `dekspec ib ready` lists accepted, delegated IBs whose dependencies are `COMPLETE` and that no run owns — the pull surface for construction (`br ready` no longer is).
- `dekspec ib context IB-NNN [--out FILE]` generates the execution context: the contract, each obligation's canonical text with its source path, status and hash, the precedence order, and informational pointers. Dispatch prompts are built from it.
- `dekspec ib start IB-NNN [--owner NAME] [--takeover]` opens (or resumes) the run: it refuses when a dependency is incomplete or an obligation does not resolve, runs every Environment Prerequisite probe (a failed required probe blocks the run as `prerequisite-unavailable`, exit 3), records ownership, and binds the context manifest. Another owner's run is transferred only with `--takeover`, which is recorded.
- `dekspec session start IB-NNN` binds the git session to the IB so a commit outside its Scope, or touching a Protected Surface, is blocked at commit time (§Session discipline).

### 2. Investigate, then commit a plan

Investigation precedes the committed plan (ADR-056 §3), in proportion to the task: the code involved, the contracts that apply, what can be reused, what is uncertain. The first plan must record those findings. Then either run the IB directly or split it into tasks:

```yaml
findings:
  inspected: [tooling/foo/parser.py, tests/test_parser.py]
  contracts: [ADR-036 behavior-first tests, IC-012 §Shape]
  reuse: [dekspec.diff_confinement.matches_any_glob]
  uncertainties: [none]
rationale: parser first; the CLI change is mechanical once it lands
tasks:                      # or `direct: true` for one continuous run
  - id: T-parse
    title: parse the new header
    covers: [AC-1, AC-2]
    files: [tooling/foo/parser.py]
  - id: T-cli
    title: expose it on the CLI
    covers: [AC-3]
    depends_on: [T-parse]
    files: [tooling/foo/cli.py]
```

`dekspec ib plan IB-NNN --file plan.yaml` (or `--file -` for stdin) commits it. Plans are revisable at any time, but the engine refuses a revision that leaves an acceptance condition uncovered, creates a dependency cycle, drops or narrows a completed task, reuses a retired task id, rewrites a task another agent has in progress (without `--takeover`), or plans a file outside Scope — that is a scope expansion and needs an IB amendment, not a plan revision. A planned file inside Scope but absent from the Implementation Hypothesis is recorded as a deviation: allowed, and visible to the reviewer.

Tasks move with `dekspec ib task IB-NNN claim T-x` — the actions are `claim`, `done`, `block` and `release`, each taking optional `--evidence` and `--note`. Closing every task proves nothing on its own — only the IB's acceptance evidence does (ADR-057). No universal sizing applies: no hour budget, no one-file-per-task rule, no mandatory test file per task.

### 3. Attempts: bounded and truthful

Each implementation try is a counted attempt:

```bash
dekspec ib attempt IB-NNN start [--task T-x]
dekspec ib attempt IB-NNN heartbeat --summary "…"
dekspec ib attempt IB-NNN end --outcome failed --failure-class flaky-test --summary "…"
```

`--outcome` is `passed`, `failed`, `error` or `abandoned`. The limits come from the `execution:` block of `.dekspec/config.yaml` — by default 3 attempts, a 60-minute stall timeout and a 2-attempt no-progress window (`docs/cli-reference.md` §execution). Counts live in the record, so they survive restarts and new sessions. The run **blocks** (exit 3) when attempts are exhausted, when an attempt goes without a heartbeat past the stall timeout (it is closed and counted), or when consecutive attempts satisfy no new condition and change no content.

**Escalate only for decisions the agent may not make** (ADR-055) — record them as blockers instead of guessing:

```bash
dekspec ib block IB-NNN --reason contract-conflict --detail "O-2 and IC-012 §Errors disagree on retry semantics"
```

`--reason` is one of `attempts-exhausted`, `no-progress`, `stalled`, `prerequisite-unavailable`, `contract-conflict`, `scope-expansion`, `acceptance-invalid`, `other`. Use them for: changing a binding obligation or protected surface; changing outside Scope; weakening or replacing an acceptance condition; a contradiction the contract does not settle; a missing prerequisite or authority; an underdefined contract. An extra helper file inside Scope, a better sequence or a corrected file guess is engineering judgment, not an escalation. A blocked run refuses completion until an operator records the decision: `dekspec ib unblock IB-NNN --decision "…" [--extra-attempts N]`.

### 4. Verify

`dekspec ib verify IB-NNN [--base BRANCH] [--dry-run]` runs every acceptance condition against the current content and checks the rest of the contract:

- **Test conditions** run through a per-node reporting plugin: a skipped, expected-to-fail, deselected or uncollected node does not satisfy its condition, and a deleted or renamed test file fails it. **Command conditions** need exit status 0. **Review conditions** are marked for the independent reviewer.
- **Bytecode** — every Python file the implementation fingerprint covers runs from its current source. No bytecode for it is read, in any invalidation mode, from the repository's `__pycache__`, the bytecode cache or pytest's assertion-rewrite cache, even when a file has been planted there. That holds for its own path and for any path reaching it through the test interpreter's path entries: a symbolic link (`flit install --symlink`, setuptools' strict editable mode), a hard link or a mount. The entries are scanned for such paths before each run, and no bytecode is read or written at them. If they change while a condition runs, or the run compiled a reviewed file by a path a test made, the condition is run again from source without the cache. The test interpreter's own modules (standard library, site-packages, a virtual environment the repository ignores) are compiled at most once per interpreter and source version. They are reused from `$XDG_CACHE_HOME/dekspec/bytecode/` (default `~/.cache/dekspec/bytecode/`), outside every repository and resolved from the environment at each run. A run writes no bytecode inside the repository. A missing, unwritable or corrupt cache never changes an outcome: files the interpreter could not load are removed before every run, and without a usable cache the run compiles from source.
- **Scope and Protected Surfaces** — every changed file (against `--base`, default `main`) inside Scope, none on a Protected Surface; declared **Spec impact** present in the delivery.
- **Acceptance integrity** — the contract, acceptance assets and runner inputs (test configuration, ancestor `conftest.py`) match the baseline, or the change was amended.
- **Obligations** still resolve to approved, in-force sources.

The result is recorded as evidence bound to the content fingerprint, the contract hash, the baseline and the context manifest. Any later change to code, tests, configuration, the contract or a governing source makes it stale — verify again. `--dry-run` records nothing.

### 5. Review

The reviewer — an identity other than the run owner and every attempt actor — examines the delivery against the IB (`/dekspec:review-pr`) and records the verdict:

```bash
dekspec ib review IB-NNN --reviewer NAME --verdict pass --acknowledge "…" --notes "…"
```

`--criteria AC-…` narrows which review conditions the verdict covers (default: all of them). The verdict is bound to the reviewed content. It carries forward across later commits only when they touch none of the reviewed surfaces — Scope, protected surfaces, acceptance assets, runner inputs, governing sources — and the completion record lists every change carried across. An amendment, an acceptance asset first created during execution, or a runner-input change appears in `ib verify` as needing acknowledgment; the completing verdict must `--acknowledge` each one, and only after judging it — for an amended or added acceptance asset, the independent basis of each new or changed expectation (ADR-062). The implementer never approves its own work or its own amendment (ADR-057).

### 6. Complete

`dekspec ib gate IB-NNN` evaluates the completion gate read-only; `dekspec ib complete IB-NNN` writes `COMPLETE` — the only path to it — when every check passes: a delegated, executable, `ACCEPTED` contract; an intact record; no stalled attempt and no active blocker; dependencies complete; obligations resolving; acceptance integrity; current, passing evidence for every condition; scope and protected surfaces confined; and a current independent passing verdict. Task closure, a closed tracker item or an unrelated green run never substitutes.

`dekspec ib status IB-NNN` shows the derived state at any time — status, authority policy, run phase, owner, attempts used/allowed, blockers, tasks and the gate — so nobody mirrors progress by hand. Like every run-touching verb it applies stall detection, so it can close a stalled attempt; `dekspec ib gate` is the strictly read-only view.

### 7. Deliver and land (ADR-058)

One pull request = one worktree = one delivery unit, scoped per ADR-048: a single IB, an Intent's IBs, or a Mission cluster. Acceptance stays per IB; verification and review cover the integrated head. Before merge:

1. `dekspec delivery verify [--ib IB-NNN …] [--base main]` re-runs every included IB's acceptance and the configured `integration_command` against the same final content (the IBs default to those discovered from the diff).
2. A current verdict per IB at that head, then `dekspec ib complete` per IB.
3. `dekspec delivery check [--base …]` passes only when every execution record the base or the delivery's history carried is still present and append-only, the branch is current with its base, and every delivered IB is satisfied at the exact head (`--ib` can add IBs, never hide one). `/dekspec:land-intent` runs it immediately before the operator-confirmed merge (ADR-026 — nothing merges automatically); CI runs `dekspec delivery check --rerun`, which re-executes acceptance and the base's integration command instead of trusting recorded results, and writes nothing. `/dekspec:implement` runs the same check as its landing gate but does not repeat what its own passing delivery verification already executed at the identical binding (ADR-059 stage 6); CI's run always re-executes.

Any later commit — to any IB, or a rebase onto a moved base — makes deterministic evidence stale until re-run. Rewriting commits after review (for example `/dekspec:pr-branch` stripping spec-only commits) changes the head, so the check must pass again on the rewritten head.

### Directive Library

```
"That's not in the IB's outcome. Remove it."
"That file is outside the IB's Scope. Amend the IB or drop the change."
"That touches a Protected Surface. Stop and raise a blocker."
"Show me the acceptance evidence for [AC-n] before continuing."
"You edited an acceptance test. Revert it, or raise acceptance-invalid."
"Which CUDA device does this code run on? State it explicitly."
"Interface signatures don't match the IC. Rewrite them first."
"This IB's outcome involves model output and has no eval condition. Stop — invoke the Eval Agent first."
"What is the dtype of this tensor? State it explicitly before continuing."
"Does this write go to shadow or Neo4j directly? State it explicitly."
"That dtype promotion is not in the IB's obligations. Surface it before continuing."
"Stop. That touches the shadow graph write path. The flush behavior is not in your IB's obligations."
"Which topic level does this boundary detect — macro, sub, or micro? State it explicitly."
"What quantization tier does this item land in? Trace the relevance score to the tier threshold."
"Stop. That touches the shadow timeline write path. The flush behavior is not in your IB's obligations."
"Does this decay score reflect current time or capture time? State it explicitly."
```

---

## Session discipline

Every commit and push under DekSpec governance binds to a named IB or Intent via a session-lifecycle gate. The gate has two layers — a **primary gate** enforced by local git hooks and a **secondary gate** enforced by an MCP-layer guard module — plus a documented set of **escape hatches** that emit to an append-only audit log. This section covers the full primary-and-secondary-layer story so adopters get the complete picture in one place.

### Primary gate (local git hooks)

The canonical layer. After `dekspec session install-hooks` runs in a consumer repo, `.git/hooks/pre-commit` and `.git/hooks/pre-push` consult `dekspec session status --machine-readable` and reject the operation with a clear error when no session is active. Every commit and push routed through the local `git` CLI passes through this layer.

To open a session before working:

```bash
dekspec session start <IB-id-or-intent-id>
# … edit, commit, push freely while the session is open …
dekspec session end --reason "feature work complete"
```

`dekspec session status` shows the active session at any time. Sessions expire after a TTL (default 4 hours; overridable via `DEKSPEC_SESSION_TTL_HOURS`); a stale session is reported as stale and is replaced by the next `dekspec session start` (or closed with `dekspec session end`). A legacy code-bead id still resolves to the Intent that lists it.

### Secondary gate (MCP guard)

The primary gate catches every `git`-routed commit/push, but commits routed via the GitHub MCP server's REST API never touch local hooks. The secondary gate closes that hole. `tooling/dekspec/mcp_guard.py` exports a three-call surface consumable by an MCP runtime's pre-flight hook for commit/push tool calls:

```python
from dekspec.mcp_guard import is_session_active, guard_commit, guard_push, GuardResult

# Wired into the MCP runtime's commit-tool pre-flight:
result: GuardResult = guard_commit(operator, files, message)
if not result.allow:
    raise RuntimeError(result.reason)  # surfaces the diagnostic to the MCP caller
```

The guard subprocess-invokes `dekspec session status --machine-readable` for its information source — it never reads the session-state file directly, so the contract sits cleanly atop the CLI envelope. Fail-closed by default: reject when no active session, when status parsing fails, when the CLI is absent, or when the session is stale. The guard also honors a consumer-opt-in warn-only mode via `DEKSPEC_MCP_GUARD_MODE=warn` (allow + log; useful during initial rollout).

### Escape hatches

Three documented bypass paths, all of which emit a row to the append-only bypass log at `XDG_STATE_HOME/dekspec/<repo-hash>/bypass.log` so reviewers can audit after the fact:

- `git commit --no-verify` — skips the pre-commit hook (standard `git` flag). Logged.
- `DEKSPEC_BYPASS_SESSION=1 git commit ...` — env-var bypass honored by both the primary hook and the secondary MCP guard. Logged.
- `DEKSPEC_MCP_GUARD_MODE=warn` — downgrades MCP guard reject to allow-with-log (does not affect the primary git-hook gate). Logged on each downgrade.

The bypass log is append-only NDJSON; one row per bypass; each row carries `ts`, `session_id` (null if bypass fires without an active session), `operator`, `files`, `reason`. A sample row:

```json
{"ts": "2026-05-17T14:23:11Z", "session_id": null, "operator": "alice@example.com", "files": ["src/foo.py"], "reason": "DEKSPEC_BYPASS_SESSION=1 set on MCP-routed commit"}
```

### Off-spec drift guardrail

The session gate proves *that* work happens under a named session; it does not prove the work belongs to the claimed IB's or Intent's scope. The **off-spec drift guardrail** (MSN-009) closes that gap — it makes "vibecoding" (code changes with no in-flight Intent capturing the work) visible at commit time rather than silent.

**Detection model.** The guardrail classifies every staged file as in-scope or off-spec by **exact glob match** — a file matches a glob or it does not — against the claimed scope:

- **IB-bound session** (`dekspec session start IB-NNN`, ADR-056): the IB's Scope (a legacy IB: its Files to Modify), plus the IB file itself, its acceptance assets and its execution record. A file on a Protected Surface is off-spec even inside Scope — protected wins over every allowance (ADR-055). This is the same precedence `dekspec ib verify` applies, enforced at commit time.
- **Intent-bound session**: the Intent's `Components affected` glob list.

 There is no fuzzy or adjacent-file tolerance: that would re-introduce the silent-drift gap the guardrail closes.

**`dekspec session vibecoding-check`.** The CLI verb that runs the classification. It reads the staged file set (`git diff --cached --name-only`, or `--files`), classifies it, and exits `0` when every file is in-scope or `3` on off-spec drift. `--machine-readable` emits a stable JSON envelope; `--record` additionally appends an off-spec record to session state.

**Pre-commit off-spec stage.** The `pre-commit` hook template (`templates/git-hooks/pre-commit.template`) gains an off-spec stage that runs *after* the active-session check passes. It invokes `vibecoding-check` and, by default, **blocks** a commit touching files outside the claimed scope. The block names the off-spec files and the ways forward — widen the claimed scope through its own decision process (amend the IB, or expand the Intent's `Components affected`), or proceed as recorded vibecoding. If the `vibecoding-check` verb is unavailable (a consumer on a pre-MSN-009 library version) the stage warns and proceeds — it never hard-blocks on its own malfunction.

**`DEKSPEC_VIBECODING=1`.** Setting this env var downgrades the off-spec **block** to a **warning**: `DEKSPEC_VIBECODING=1 git commit ...` proceeds, but the off-spec commit is recorded into session state either way — exploratory off-spec work stays possible as a deliberate, recorded choice rather than a silent one.

**`dekspec session report`.** The read-only end-of-session summary. It reads the session's recorded off-spec commits and prints a per-commit breakdown plus a *ratify-or-revert* prompt — ratify (capture the work in an IB, or widen the claimed scope) or revert. The `/orchestrate-coding-session` skill runs `dekspec session report` at session close so the operator cannot finish a session without seeing what fell off-spec.

The off-spec guardrail activates only when a consumer has installed the hooks (`dekspec session install-hooks`) at a library version that carries the off-spec stage; the library ships the capability inert until then. The library's own `dekspec/` self-spec is exempt by the same policy described next.

### Library-side self-exemption

The DekSpec library's own `dekspec/` self-spec is governed by **Claude Code session-rules** per the library's `CLAUDE.md` (specifically the "DekSpec Guardrails (library-side)" section), **not** by hook-enforced session gating. The library does not install the hooks against itself; the runtime gate is a capability the library *produces* for consumers, not consumes for its own development. Engineers contributing back to the library should not install the hooks against their library checkout — the session-rules pattern is sufficient discipline for the library's own development loop.

### Consumer adoption steps

1. Install or upgrade DekSpec to a version that ships the session gate (≥ v0.44.0 — exact version pinned at MSN-002 close).
2. Run `dekspec session install-hooks` from your repo's git toplevel. The installer writes `.git/hooks/pre-commit` and `.git/hooks/pre-push` templates that consult the CLI's machine-readable status envelope.
3. Wire `tooling/dekspec/mcp_guard.py::guard_commit` and `::guard_push` into your MCP-server config's pre-flight hook for commit/push tool calls. The exact wiring depends on your MCP runtime; the three-call surface is stable.
4. Document the escape hatches (`git commit --no-verify`, `DEKSPEC_BYPASS_SESSION=1`, `DEKSPEC_MCP_GUARD_MODE=warn`) in your team's onboarding doc so engineers know how to bypass when needed and that bypasses are logged for review.
5. (Optional) Set `DEKSPEC_MCP_GUARD_MODE=warn` in your MCP-server env during the initial rollout window to log-only without blocking; flip to reject (unset, or `=reject`) once the team has internalized the workflow.

The `/orchestrate-coding-session` skill automatically opens and closes a session around its dispatch loop, so engineers running the skill against an IB never need to run `dekspec session start` or `dekspec session end` themselves — see `plugins/dekspec/skills/orchestrate-coding-session/SKILL.md`.

---

## Repository Structure

```
CLAUDE.md                        ← Claude Code: skills map, global rules
AGENTS.md                        ← Tool-agnostic: generated governing context (`dekspec aggregate agents-md`)
.claude/skills/                  ← registered Claude Code skills (invocable via /name)
.dekspec/
  config.yaml                    ← per-repo config, incl. the `execution:` policy block
  execution/<IB>/record.jsonl    ← one execution record per IB / Intent run (committed; not a spec artifact)
dekspec/
  adr-index.md                   ← ADR index, escalation rule, backlog
  working-spec-index.md          ← Working Spec index
  interface-contract-index.md    ← Interface Contract index
  architecture-elements-index.md ← Architecture Elements index (replaces design-notes-index.md)
  system-vision.md               ← Layer 1: system vision (singular, top-level)
  domain-glossary.md             ← Layer 1: canonical domain terminology
  terminology-corrections.md     ← corrections backlog (promoted to glossary over time)
  dekspec-operating-guide.md      ← this document
  dekspec-quick-reference.md     ← 5-10 minute onboarding summary
  project-context.md             ← all 13 role definitions and prompts
  adrs/
    ADR-NNN-[slug].md            ← Layer 1: one decision per ADR
  architecture-elements/         ← Layer 1: canonical descriptions of architectural slices (flat directory)
    AE-NNN-[slug].md             ← each AE declares subtype in metadata: System | Subsystem | Container | Component | Pipeline | Data Model | Cross-Cutting Concern | Platform Concern | Interface Surface | Workflow / Process
  working-specs/
    WS-NNN-[slug].md             ← Layer 2: working specs (numbered sequentially)
  interface-contracts/
    IC-NNN-[slug].md             ← Layer 2: formal interface contracts
  impl-briefs/                   ← Layer 3: implementation briefs (optionally in status-band folders)
    queued/                      ← DRAFT / PROPOSED
    active/                      ← ACCEPTED
    completed/                   ← COMPLETE (and legacy IBs done under the old model)
  templates/                     ← spec and checklist templates
  audits/                        ← campaign-bucketed audit records (reference, not governed artifacts)
    convergence-v1/                ← per-service convergence iterations (se, co, cx)
    convergence-v2/                ← unified Dektora convergence iterations
    dn-audit/                      ← DN audit campaign
    adr-audit/                     ← ADR audit campaign
    ws-audit/                      ← WS audit campaign
    ic-audit/                      ← IC audit campaign
    (misc)                         ← baseline-decisions, rollups, spec-fitness-functions, ws-audit-process-proposal — files that don't belong to a campaign bucket
  workspace/                     ← non-artifact companion material for the DekSpec process
    convergence/
      convergence-loop.md                         ← v1 convergence-loop orchestration runbook (not a governed artifact)
      convergence-loop-v2.md                      ← v2 convergence-loop orchestration runbook (not a governed artifact)
      convergence-bootstrap-prompt.md             ← v1 convergence bootstrap prompt
      convergence-v2-bootstrap-prompt.md          ← v2 convergence bootstrap prompt
      convergence-v2.config.md                    ← v2 convergence configuration
      (divergences relocated to `dekspec/divergences/DIV-NNN-*.md` as of 2026-05-11; see migration notes)
    prompts/
      deep-spec-audit-prompt.md                     ← deep spec-audit prompt scaffolding
      service-buildability-rollup-prompt.md         ← per-service DekSpec-coverage rollup
      service-buildability-closeout-plan-prompt.md  ← phased closeout plan from the rollup
    ops/
      dektora-production-plan-lambda.md             ← production deployment plan (Lambda Cloud)
      dektora-dev-experimentation-runpod.md         ← dev/experimentation plan (RunPod)
    archive/                     ← retired artifacts and shelved plans (kept for reference; not governed)
      divergence-ledgers-v1/
        divergence-ledger-{cooccurrence,cortex,semantic-embedding}.md ← ARCHIVED v1 per-service divergence ledgers (banner-flagged; archived 2026-04-24)
      source-of-truth/           ← retired inventor-composed source-of-truth docs + pre-DekSpec legacy archive
      (the source-of-truth/ and divergence-ledgers-v1/ subdirs above are the current archived content)
    research/                    ← methodology, tech research, benchmarks, DekSpec meta-analyses (not governed)
    explorations/                ← pre-artifact live work: proposals, handoff briefs, exploratory concepts awaiting promotion to DN/WS/skill
    archaeology/                 ← (legacy) historical directory for retired /do-code-archaeology skill output; new brownfield work uses /recover-specs which writes no parallel artifact tree
    todos/                       ← quality reports, open-areas assessments
tests/
  unit/                          ← deterministic unit tests (written by coding agent)
  contracts/                     ← auto-generated from spec constraint tables (permanent)
  properties/                    ← hypothesis property-based tests (permanent)
  regression/                    ← defect reproductions with provenance (permanent)
  integration/                   ← cross-IB composition; run by the delivery integration command (permanent)
  evals/                         ← probabilistic AI behavioral evals (written by Eval Agent)
    behavioral/                  ← model output vs. known-good baselines
    regression/                  ← run on every PR touching model/graph/quant
    adversarial/                 ← empty moment stack, Q4-only, flush failure
.beads/                          ← `br` issue tracker (legacy `cb-` code beads readable for history)
```

### Library-side layout (`Dektora/dekspec` repo itself)

The diagram above describes a **consumer repo** post-vendoring — what an engineer at Dektora or DekFactory sees after `bash scripts/install.sh` (engine install, then `dekspec sync`). The library's own source tree has a different shape because it *produces* the vendored content rather than receiving it:

```
Dektora/dekspec/                    ← this repo
  AGENTS.md                         ← library-side session protocol (small; points at methodology)
  CLAUDE.md                         ← library-side session rules + model policy
  README.md                         ← library landing page
  CHANGELOG.md                      ← release history (consumer-facing)
  RELEASING.md                      ← release runbook
  pyproject.toml                    ← Python package metadata + entry points
  tooling/dekspec/                  ← Python implementation
    constraint_compiler/            ← parsers + emitters
    fidelity_audit/                 ← audit engine + profile registry
    schemas/                        ← JSON Schema (YAML) per IR type
    migrations/                     ← IR + markdown migrations (`dekspec migrate`)
    execution/                      ← IB execution & evidence engine (`dekspec ib|delivery|intent`, AE-011)
    cli.py                          ← `dekspec` command entry point
    api.py                          ← public typed surface
  skills/                           ← Claude Code skills (vendored → consumer's .claude/skills/)
    write-*/SKILL.md
    fidelity-audit/SKILL.md
  templates/                        ← artifact templates (vendored → consumer's dekspec/templates/)
    {adr,architecture-element,working-spec,…}-template.md
    checklists/{eval-quality,security,python-quality}-checklist.md
  docs/                             ← methodology (vendored selectively → consumer's dekspec/)
    dekspec-operating-guide.md      ← this document
    dekspec-quick-reference.md
    architecture.md
    architecture-frameworks-reference.md
    dekspec-methodology.md
    cli-reference.md
    EXAMPLES.md
    amendment-log-types.md
    releases/                       ← per-release consumer-notification docs
  scripts/
    install.sh                      ← the installer consumers invoke (engine + dekspec sync + per-host delivery)
    bump-version.py                 ← release-side version-mirror sync
  tests/                            ← pytest suite (400+ tests; library behavior)
  dekspec/                          ← the LIBRARY'S OWN self-spec (audited on every PR)
    system-vision.md
    domain-glossary.md
    adr-index.md / architecture-elements-index.md / interface-contract-index.md
    adrs/ADR-NNN-*.md               ← 10 ADRs documenting library decisions
    architecture-elements/AE-NNN-*.md   ← 8 AEs covering subsystems
    interface-contracts/IC-NNN-*.md       ← 3 ICs (emitter contracts)
  .github/workflows/                ← ci.yml + release.yml (version-triad enforcement)
  .beads/ .beads-dekspec/ .beads-issues/  ← `br` workspaces (code-bead workspace legacy-only, ADR-052/056)
```

The **library self-spec under `dekspec/`** is the library's eat-own-cooking gate (ADR-007 + ds-i3g). It is audited on every PR by the `Self-dogfood — dekspec doctor` step in `.github/workflows/ci.yml`; any new audit rule must pass against this corpus before reaching consumers.

---

## Filename Conventions

DekSpec follows two simple rules for filenames inside the `dekspec/` content tree:

1. **Artifact files use the label-NNN format with the LABEL UPPERCASE.** Everything else in the filename is lowercase + hyphenated. Examples (from a consumer's tree — the numbers are that consumer's, not this library's): `ADR-022-configurable-scoring-formulas.md`, `AE-014-configurable-formula-engine.md`, `WS-016-scoring-formulas.md`, `IC-007-formula-engine-evaluation.md`, `IB-003-se-embedding-tokens.md`, `MSN-002-attachment-mime-coverage.md`, `MSN-001-se-container-build.md`, `CR-001-cascade-tier-rebalance.md`, `DIV-001-skips-wireups.md`. The artifact-label prefixes are: `ADR`, `AE`, `WS`, `IC`, `IB`, `INT`, `MSN`, `CR`, `DIV`.

2. **All other files inside `dekspec/` are lowercase + hyphenated.** Index files, methodology docs, supporting docs, vendored templates, workspace notes — all lowercase. Examples: `adr-index.md`, `working-spec-index.md`, `architecture-elements-index.md`, `intent-index.md`, `mission-index.md`, `dekspec-operating-guide.md`, `dekspec-quick-reference.md`, `architecture-frameworks-reference.md`, `architecture.md`, `domain-glossary.md`, `system-vision.md`, `project-context.md`, `terminology-corrections.md`, `ecosystem-tools.md`, `closeout-audit-v2-2026-05-09.md`, `dn-to-ae-reference-map-2026-04-27.csv`.

### Allowed UPPERCASE exceptions (outside `dekspec/`)

These nine files stay UPPERCASE because tooling or universal conventions require it:

| File | Where | Why UPPERCASE |
|---|---|---|
| `README.md` | Repo root | Universal convention; every Git host displays it as the project's front page |
| `CHANGELOG.md` | Repo root | Keep-a-Changelog convention; every release-tooling pipeline expects it |
| `LICENSE` / `LICENSE.md` | Repo root | GitHub's license-detection bot requires capitalization to display the license badge |
| `CONTRIBUTING.md` | Repo root | GitHub community-standards bot detects this for the contributor sidebar |
| `CODE_OF_CONDUCT.md` | Repo root | GitHub community-standards bot — uses the SCREAMING_SNAKE_CASE form |
| `SECURITY.md` | Repo root | GitHub Security tab detection |
| `SKILL.md` | Every `.claude/skills/<name>/` dir | Claude Code skill loader hardcodes the filename for slash-command discovery |
| `AGENTS.md` | Consumer repo root | Claude Code worker context loaded at session start; AI-coding-agent-ecosystem convention |
| `CLAUDE.md` | Consumer repo root + `~/.claude/` | Claude Code persistent memory (per-project + per-user) |

**Within `dekspec/` content, NO file should be UPPERCASE** — the rule is unconditional. The label prefix (`ADR-`, `AE-`, etc.) is the only uppercase, and it's part of the artifact ID, not a casing decision about the filename.

### Why this matters

Consistency makes the corpus greppable, glob-able, and case-insensitive-filesystem-safe. The label-uppercase convention also means a single grep like `^[A-Z]+-\d+-` finds every artifact across all dirs, with no false positives from sibling files.

---

## Interface Contracts

Interface Contracts are Layer 2 specification artifacts alongside Working Specs. Both are behavioral contracts — Working Specs define component behavior, Interface Contracts define cross-component boundaries. Interface Contracts are typically produced during `/write-ws` (Phase 5 invokes `/write-ic` when a boundary warrants a formal contract). The `/write-ic` skill can also be invoked standalone when a boundary is identified outside the spec-writing flow.

**Write a formal contract when:**
- The interface is consumed by a different component built independently
- The interface is external-facing
- Error semantics are complex enough that prose is ambiguous

**Prose in the Working Spec is sufficient when:**
- Same team builds both sides
- Same session or closely coordinated work

All interface contracts live in `dekspec/interface-contracts/`.

**Relationship Pattern:** Every contract declares a DDD context-mapping pattern that identifies who adapts when the interface changes. Available patterns: Open Host Service, Customer-Supplier, Anti-Corruption Layer, Conformist, Shared Kernel, Published Language. This makes change-impact analysis mechanical rather than case-by-case.

---

*Role definitions and prompts: `dekspec/project-context.md`*
*Skill workflows: `.claude/skills/[name]/SKILL.md`*
*Spec templates: `dekspec/templates/`*
*Pending ADRs: `dekspec/adr-index.md`*

---

## Multi-User Coordination

*DekSpec runs two orthogonal coordination mechanisms over the spec graph; a third, semantic layer was proposed and not built. They serve different workflow patterns; do not retire either assuming the other covers its case. See INT-086 (multi-user-coordination-analysis) for the full analysis.*

### The three layers

| Layer | Mechanism | Solves | Workflow pattern |
|---|---|---|---|
| Mechanical (intra-MR) | **INT-020** — DRAFT-slug temp IDs + `dekspec id allocate` + append-only `dekspec/registry.yaml` + `LINK-NO-DRAFT-IN-MAIN` (P0) + `LINK-REGISTRY-APPEND-ONLY` (P1) | Two engineers each grep the index for next-free `<KIND>-NNN`, both pick the same number, collide at merge time. | "This Intent ships in this MR; defer canonical-ID allocation to commit time." |
| Cross-MR exploratory | **MSN-014** — `dekspec/provisional/<incubation-slug>/` + `<KIND>-provisional-<slug>` ID convention + `dekspec library new-provisional` (scaffold + git branch) + hand-promote workflow (renumber + `git mv` — see §Provisional Promotion) + `replaces:` frontmatter for REPLACE mode + L-PROVISIONAL-* / LINK-COW-SIBLING-COLLISION / T-COW-CANONICAL-EDITED audit rules | A non-trivial change that may span many commits, may be abandoned, and shouldn't pollute the LOCKED spec graph during exploration. | "Author the family under `dekspec/provisional/<slug>/`; hand-promote when the originating Intent matures toward ACCEPTED." |
| Semantic (cross-engineer) — *not built* | Proposed as **MSN-010** (killed 2026-05-30 as stale; its provisional successor was aborted 2026-09-28 — team coordination is settled by ADR-051 as an additive profile plus the host orchestrator) — divergence detection, contradiction warnings at PROPOSED, system-vision drift advisories, engineer attribution, dependency-cycle detection, coherence health, deconfliction workflow | Two engineers ship Intents that each validate individually but collectively contradict each other or the system vision. | "After this Mission lands, semantic conflicts surface at session-start, at PROPOSED time, at LOCK time, and on a periodic sweep." |

### When to pick which

| Pattern | INT-020 (DRAFT-slug) | MSN-014 (provisional folder) |
|---|---|---|
| Small Intent (single file, one MR) | ✓ canonical dir with DRAFT-slug; allocate at commit | ✗ too much ceremony |
| Multi-artifact family across many commits | ✗ canonical pollution during exploration | ✓ everything stays in `dekspec/provisional/<slug>/` |
| Need git branch per exploration | (manual) | ✓ `dekspec library new-provisional` auto-creates branch |
| Need audit cleanliness during exploration | ✗ DRAFT artifacts visible to canonical audit | ✓ provisional tree invisible to canonical audit walker |
| Need REPLACE mode (overwrite LOCKED canonicals) | n/a | ✓ `replaces:` frontmatter + hand-promote REPLACE step |

The two compose: a promoted provisional family CAN run through `dekspec id allocate` for its final canonical IDs if the team's `methodology_profile: team` runs both.

### Derived-output regeneration (MSN-015)

Index files (`intent-index.md`, `mission-index.md`, `adr-index.md`, `architecture-elements-index.md`, `working-spec-index.md`, `interface-contract-index.md`) and `AGENTS.md` are **derived** outputs — regenerate them from canonical artifact state rather than hand-editing. Two engineers adding rows on parallel branches produce no merge conflict after both run regen pre-commit, because rows sort by numeric ID ascending.

Tools:

- `dekspec regen-indexes [--check] [--at PATH]` — rebuilds all 6 derived indexes deterministically from the canonical artifact tree.
- `dekspec aggregate agents-md [--at PATH] [--output PATH]` — regenerates only the DekSpec-owned region of `AGENTS.md` (between `<!-- dekspec:agents-md begin -->` and `<!-- dekspec:agents-md end -->`; everything outside it is preserved byte for byte) from LOCKED+ACCEPTED artifacts of the governing core (Constitution, Security Profile, System Vision, glossary, AE, ADR, IC, WS); work items (IB, Intent, Mission) are excluded by default (ADR-056). A legacy whole-file AGENTS.md is migrated only with `--migrate` (preview with `--migrate --dry-run`). Settings come from `.dekspec/config.yaml` `agents_md` (`path`, `status`, `include`, `required`) when declared (ADR-063).
- `dekspec aggregate agents-md --check` — read-only freshness verdict: `current` 0, `stale` 1, `absent` 1 when required (else 0), `inapplicable` 0, `invalid` 1. It is also the `agents-md` section of `dekspec doctor` (a declared projection that is stale fails doctor) and an explicit CI step in this repository.

Engineers regenerate pre-commit or post-merge; the post-merge hook reports a stale projection using the check. Regeneration is always an explicit act — checking never writes. CI runs `dekspec relink --check`, the `agents-md --check` step above and `dekspec doctor`, whose index-coherence rule reports an artifact missing from its index; there is no dedicated `regen-indexes --check` CI step. (MSN-015 is COMPLETE; an earlier note calling CI integration its open piece is historical.)

### Remaining gaps (deferred)

1. **Concurrent unlock-edit-relock on LOCKED artifacts** — 2nd engineer to unlock sees stale view, re-applies changes the 1st engineer already made (see DIV-017). Deferred; wait for an actual incident.
2. **Plugin/skill catalog auto-gen** — `skills.md` lists every skill manually. Future Intent.
3. **Migration concurrency** — only one engineer per release should run `dekspec migrate-artifacts`. No mechanism currently enforces this. Schema bumps are infrequent; cost-of-cure is low.

---

## Provisional incubation

*The MSN-014 surface — what the cross-MR exploratory layer (above) actually feels like end-to-end.* This section is the operator's walkthrough for the four-step lifecycle: scaffold → CoW → edit → hand-promote.

> **Provisional ID scheme (ADR-043).** Every kind incubates under one form: `P-<KIND>-<NNN>-<slug>.md` with an in-file id `P-<KIND>-<NNN>`. The number is a *non-binding hint* (the next-free canonical number at authoring time); hand-promotion re-derives the real next-free number, which may differ. The `P-` prefix self-excludes a provisional file from the canonical `<KIND>-NNN` scan, so it is never miscounted (retiring the old `≥900` placeholder). A `P-` artifact parses, `dekspec validate`s, and promotes like any other, but **stays out of the canonical spec graph** — it is never loaded by the linkage walker, never referenced by a canonical artifact, and never listed in an index, so a provisional folder is **freely abortable** (delete it with zero cascade). The `T-PROVISIONAL-NOT-LOCKED` rule (P2) guards the one hard invariant: a provisional artifact must be *promoted*, never frozen at a terminal `LOCKED`/`COMPLETE` status. The legacy numberless `<KIND>-provisional-<slug>` form is still recognized by the promotion walker during the transition.

### Step 1 — Scaffold

Two equivalent entry points:

- **CLI:** `dekspec library new-provisional <KIND> <slug>` — KIND ∈ {INT, MSN, ADR, AE, IC, WS, IB, SP}. Writes a skeleton at `dekspec/provisional/<slug>/<KIND>-provisional-<slug>.md` with the canonical template body, a `> **PROVISIONAL.**` banner, and the template's initial Status (`DRAFT`; `PROPOSED` for a Mission). On first artifact in the folder the verb creates a working-tree branch — `int/INT-...`, `mission/MSN-...`, or `feat/<slug>` for the others — unless `--no-branch` is passed.
- **Skill:** `/dekspec:write-<kind> --provisional <slug>` — same destination, same banner. Runs the full authoring flow (expertise audits, coverage analysis, etc.) but skips passes that require linkage-walker visibility. `--lock` is rejected in provisional mode; `--review` and `--analyze` are permitted.

Six skills carve out: `/write-constitution`, `/write-sv`, `/write-glossary`, `/write-corrections` (singletons) and `/write-evals`, `/write-tests` (operate on existing IBs). They do not accept `--provisional`.

### Step 2 — Copy-on-write (CoW) staging

When the incubation must **modify** an existing canonical artifact (rather than add a new one), stage a copy first:

```bash
dekspec library cow-stage dekspec/architecture-elements/AE-006-skills-library.md \
  --incubation provisional-artifact-incubation
```

The verb copies the canonical file into the incubation folder, stamps `replaces: AE-006` in the frontmatter, and is idempotent — re-running it on an already-staged file is a no-op. Singletons (Constitution, System Vision, Glossary) use a path-as-id form: `replaces: constitution`, `replaces: system-vision`, `replaces: domain-glossary`.

Two audit rules patrol this surface:

- `LINK-COW-SIBLING-COLLISION` (P2) — two distinct incubations both claim the same canonical path. Resolution: one incubation merges into the other or one is killed before the other promotes.
- `T-COW-CANONICAL-EDITED` (P2) — a CoW-staged canonical was *also* edited on the working branch. Resolution: drop the working-branch edit and re-stage, or drop the CoW copy and accept the working-branch edit as canonical.

### Step 3 — Edit + iterate

Engineers edit provisional artifacts using the same `/write-<kind>` skills that author canonical artifacts. Authoring passes, `--review`, `--analyze`, and `--unlock` (no-op in provisional, prints a warning) all work. `--lock` rejects with a clear error — provisional artifacts cannot be LOCKED. Status transitions inside provisional follow the canonical lifecycle (DRAFT → PROPOSED → ACCEPTED) but the ACCEPTED transition does **not** trigger promotion automatically — see Step 4.

The advisory rule `LINK-PROVISIONAL-STALE` (P3) fires on incubation folders whose newest file is older than 30 days (mtime; engineers `touch` to reset). The rule is intentionally lenient — incubations can sit for a quarter — but flags abandoned exploration so the tree doesn't accumulate cruft.

### Step 4 — Provisional Promotion (hand-promote workflow)

Provisional artifacts live under `dekspec/provisional/<incubation-slug>/`. When an incubation slug is ready to promote into canonical paths, perform the hand-promote workflow:

1. Decide the canonical ID for each artifact in the incubation folder. NEW artifacts get the next-free `<KIND>-NNN` (consult the relevant index — `intent-index.md`, `mission-index.md`, etc.); REPLACE artifacts (those whose frontmatter declares `replaces: <KIND-NNN>`) inherit the canonical's ID.
2. Move each artifact to its canonical path — e.g. `dekspec/provisional/foo/INT-provisional-bar.md` → `dekspec/intents/INT-NNN-bar.md`. Use `git mv` so history follows. IBs land in `dekspec/impl-briefs/queued/` (the IB lifecycle picks up from there). For REPLACE mode the canonical file is overwritten.
3. Rewrite content in-bundle:
   - Provisional IDs in cross-references (`INT-provisional-bar` → `INT-NNN`) — both within the moved files and in any other artifact (`MSN-NNN` Intent queue, etc.) that pointed at the provisional form.
   - The artifact's H1 — Mission files use `# Mission MSN-NNN: <title>`; the other kinds use a bare `# <KIND>-NNN: <title>`.
   - The artifact's `**<Kind> ID:**` frontmatter field.
4. Update the parent Mission's §Intent queue if applicable.
5. Delete the now-empty incubation folder (or leave residue files like `NOTES.md` and prune the folder later).
6. Validate via `dekspec doctor --at .` and reconcile any new findings; run `dekspec regen-indexes` (or rely on the post-merge hook) to refresh derived index files. The originating Intent's lifecycle then continues from `ACCEPTED` → `COMPLETE` per the standard flow.

**The accept-gate.** Hand-promote when (and only when) every artifact in the incubation has reached Status `ACCEPTED`. The gate is the explicit acknowledgement that the engineer is converting exploration into commitment: provisional artifacts are abandonable; canonical artifacts carry forward into the spec graph and become consumer-visible.

> **CLI verb retired 2026-05-25, removed ds-ib9o.** The previous `dekspec repo promote-provisional <slug>` CLI verb was retired (per F2 audit; zero invocations in repo history — every promotion was hand-promote), and its stub plus the whole `dekspec repo` alias namespace were removed in ds-ib9o. Invoking `dekspec repo …` now fails as an invalid command; promote via the Python helpers below. Provisional folders themselves are **not** retired — `dekspec/provisional/`, the `dekspec library new-provisional` scaffold verb, the `dekspec library cow-stage` staging verb, the `replaces:` frontmatter convention, and the `L-PROVISIONAL-*` / `L-COW-*` / `T-COW-*` audit rules all remain canonical. The underlying Python helpers (`dekspec.promote.plan_promotion` / `apply_promotion` / `render_plan`) are also preserved for tooling that needs to drive the renumber programmatically.

---

## *Putting It All Together*

*Here is what using this workflow actually looks like, from the first idea through two executed, reviewed and landed Implementation Briefs.*

---

### *The Idea*

*The team wants to replace the JSON tensor serialization between the embedding process and the chat model process with a binary format. The current approach is acknowledged as inefficient and has unquantified precision loss. Nobody has measured either.*

### */write-adr*

*The engineer invokes `/write-adr`. The skill runs the escalation check — tensor serialization format is on the Dektora always-a-full-ADR list, so this goes straight to a full ADR. The Writer drafts ADR-001 from the engineer's description of the decision and the options considered: JSON (current), msgpack, and shared memory. The engineer reviews, corrects the rationale for why shared memory was ruled out (CUDA process isolation makes it unreliable across OS processes), and accepts it. ADR-001 is filed.*

### */write-ws — Writer Draft*

*The behavior will be implemented in more than one brief and must hold across both processes, so it earns a Working Spec. The engineer invokes `/write-ws` and describes the IPC serialization layer — what it does, what it doesn't do, the interface between the two processes, the error conditions, and the failure behavior if the receiving process is unavailable. The Writer produces a first draft.*

### */write-ws — Expertise Audit and Role Passes*

*The expertise audit runs. This spec touches tensor serialization round-trips, so the Quantization / Precision Expert pass is queued. It also touches process isolation at the IPC boundary, so the CUDA Multi-Process Expert pass is queued. The ML Expert, Graph Expert, Embedding Geometer, and Pipeline Analyst are not triggered — this spec doesn't touch those domains.*

*The Quantization Expert reads the draft and immediately flags something: the spec states the serialization format must preserve tensor values but doesn't specify what precision loss is acceptable or how it will be verified. It also notes that the spec doesn't address the dtype promotion that occurs when bfloat16 is cast to float32 before serialization — a one-way loss that must be acknowledged. The engineer updates the spec with a precision threshold and adds a round-trip fidelity requirement to the eval hooks.*

*The CUDA Multi-Process Expert reads the updated spec and flags that the spec doesn't address what happens if the receiving process is mid-inference when the serialized tensor arrives. The engineer updates the failure behavior section.*

### */write-ws — Options Architect*

*The Options Architect runs — IPC format selection is a genuine architectural alternative domain. It surfaces one additional option the team hadn't considered: a file-based ring buffer. The engineer evaluates it and decides it introduces operational complexity that outweighs the benefit. That reasoning goes into ADR-001 (still in PROPOSED status at this point) as a late addition under Options Considered.*

### */write-ws — Critic*

*The Critic runs on the full spec. It finds two gaps: the spec doesn't state who is responsible for schema versioning if the tensor format changes, and the eval hooks don't specify what "round-trip fidelity" means as a measurable criterion. Both get resolved. The Critic runs a second pass on the changed sections and finds nothing material. The spec is accepted.*

### */write-ibs*

*The engineer invokes `/write-ibs`. The Planning Agent reads the spec and ADR-001 and produces two Implementation Briefs. IB-1 implements the binary serialization library and the core round-trip logic; IB-2 integrates it at each call site, one per service process, and declares `**Depends on:** IB-1`. Neither copies the spec: IB-1's Obligations read `- **O-1** → ADR-001` and `- **O-2** → WS-001 §Precision` (the bfloat16 threshold), and it protects the existing JSON reader as a Protected Surface until IB-2 retires it. IB-1's Acceptance names the round-trip test at all five bit depths, a failure test for an unavailable receiver, and a golden-I/O pair the engineer fixes by hand. The Eval Agent is not invoked — round-trip fidelity here is deterministic.*

*The engineer runs `dekspec ib lint` on both and proposes them (`dekspec ib propose`). `/write-tests` writes IB-1's acceptance tests before any code exists: each assertion carries a `Basis:` — the golden-I/O pair cites the engineer's hand-fixed values, the round-trip test a property justified from WS-001 §Precision — a behavior-free serializer skeleton makes the assertions fire, and `dekspec ib floor IB-001` shows every node genuinely red. `/dekspec:review-ib`, in a fresh context, reviews the contracts — domain constraints reachable through the references, acceptance covering integration and failure, not only the happy path — and oracle-reviews IB-1's tests against the floor report, recording `Floor reviewed: PASS — digest …` in its Amendment Log. The engineer then authorizes with `dekspec ib accept`, which protects exactly the reviewed floor.*

### */orchestrate-coding-session*

*The engineer invokes `/orchestrate-coding-session`. `dekspec ib ready` returns only IB-1 — IB-2 waits for IB-1 to complete. The orchestrator starts the run (`dekspec ib start IB-001`), generates the execution context with `dekspec ib context`, and dispatches a sub-agent in an isolated worktree with a prompt built from that context: ADR-001's decision and WS-001's precision section arrive as canonical text with their hashes, not as copies someone maintained.*

*The sub-agent investigates before it plans. It finds an existing numpy buffer helper worth reusing and notices the IB's hypothesis put the codec in one file where the module already has a `codecs/` package. It commits a direct plan with those findings; the new file inside Scope is recorded as a deviation, no permission needed. It writes the public interface signatures first and the engineer reviews them against ADR-001: one accepts any tensor dtype rather than enforcing bfloat16 at the boundary. The agent corrects it before implementation.*

*The first attempt fails a round-trip test at 2-bit depth; the agent ends it as failed and starts a second. Then it hits a real gap: ADR-001 chooses msgpack, but neither the ADR nor the WS says how numpy arrays are packed, and two plausible encodings give different byte layouts on the wire — an underdefined contract, not an implementation detail. The agent records `dekspec ib block IB-001 --reason contract-conflict` instead of choosing. The engineer settles the encoding in WS-001 §Encoding, adds it to IB-1's Obligations with `dekspec ib amend`, and unblocks the run. The next attempt passes; `dekspec ib verify IB-001` records passing evidence for every condition.*

### */dekspec:review-pr and landing*

*IB-2 becomes ready and runs the same way. Both IBs ship from one worktree as one pull request. A reviewer who built neither IB runs `/dekspec:review-pr`, reviews the delivery against both, and records one verdict per IB with `dekspec ib review`, acknowledging IB-1's amendment. `dekspec delivery verify` re-runs both IBs' acceptance and the integration suite at the head; `dekspec ib complete` records each completion; `dekspec delivery check` passes at the exact head, and the operator merges.*

*The full binary IPC implementation is done — spec-grounded, evidence-verified, independently reviewed, and traceable back through the IBs' execution records, the Working Spec, and ADR-001.*

## Post-mortem ritual (INT-126 / ds-99ko)

> Per **INT-126** (LOCKED 2026-05-30) the `dekspec audit failure-classes` CLI verb surfaces aggregate trends in classified failures — today, failed attempts in the IB execution records (ADR-056). Coupled with INT-125's Constitution §Class Lanes (LOCKED), the post-mortem ritual is evidence-driven without ceremony.

The ritual is five steps. No new skill — uses existing tools (`dekspec ib`, `dekspec audit`, `/dekspec:write-constitution`):

1. **Engineer sees revert** — CI flips red after a merge, `git revert` lands, or `dekspec doctor` flags a regression.
2. **The failure is classified where it happened** — on the attempt, in the IB's execution record. The executor classifies a failed attempt when it ends it; the engineer may classify one found later the same way:
   ```bash
   dekspec ib attempt IB-NNN end --outcome failed --failure-class flaky-test --summary "MockedTimeService raced under parallel pytest -n auto"
   ```
   The class name is operator-chosen vocabulary (e.g. `flaky-test`, `wrong-mock`, `scope-creep`, `missing-rollback`, `unbounded-retry`). Keep names short and dictionary-able.
3. **Engineer runs the aggregator** to see whether the class is a one-off or a pattern:
   ```bash
   dekspec audit failure-classes --window 90 --by class --format md
   dekspec audit failure-classes --window 90 --by risk-tier --format md
   dekspec audit failure-classes --by type --format json | jq
   ```
   The verb is read-only. It reads every classified `attempt.ended` event in `.dekspec/execution/*/record.jsonl` (plus legacy code beads carrying a `failure-class:*` label, for history), sorts classes descending by count, and cross-references each to its IB and Intent — and, with `--detect-reverts`, a revert SHA.
4. **Engineer decides on class-lane adjustment.** A class that fires repeatedly on `(intent_type=feature, risk_tier=high)` is signal to demote that lane from `canary` to `gated`. A class that doesn't fire on `(intent_type=feature, risk_tier=low)` over a full window is signal to promote that lane from `dark` to `canary`.
5. **Engineer applies the §Class Lanes amendment** via `/dekspec:write-constitution --amend --editorial`:
   - Re-stamps the affected row's `lane` field.
   - Re-stamps `effective_model_snapshot` + `effective_corpus_volume` to the current values (calibration re-binds to the new regime per ADR-029 model-drift discipline).
   - Appends a typed `amendment_log` row recording the change + the failure-class evidence that motivated it.

Governance stays human work. The aggregator surfaces trends; the engineer decides. No automation closes the loop end-to-end — explicitly out of scope per the dekfactory review synthesis §1.D decisions.

### Class-name conventions (informal)

Lowercase kebab-case. Short (≤30 chars). Self-describing without context. Examples in use:
- `flaky-test` — non-deterministic test pass/fail.
- `wrong-mock` — test stubs the wrong thing; production code path untouched.
- `scope-creep` — an IB's delivery changed files outside its Scope.
- `missing-rollback` — change to load-bearing surface shipped without rollback plan.
- `unbounded-retry` — handler retries without backoff or cap.
- `silent-downgrade` — version regression that doesn't fail loudly (the bug this ritual was first tested on — ds-upgrade-plugin-marketplace-lags).

## Audit-loop discipline (INT-127 / ds-bqhf)

> Per **INT-127** (LOCKED 2026-05-30) the existing `dekspec doctor` verb gains a `--loop` flag that runs the rule family until it converges (or escapes). No new verb is introduced; no `dekspec audit` refactor lands. Strict additive flag set.

### Invocation

```bash
dekspec doctor --loop [--pass-cap N] [--scope artifact|corpus] [--axis T,L]
```

- `--loop` — run the mechanical-fixed-point loop (default off).
- `--pass-cap N` — max passes (default 5; placeholder per cross-plan SOFT dep on DekFactory Phase 0 archeology).
- `--scope artifact|corpus` — narrow loop to one artifact or the whole tree (default `corpus`).
- `--axis T,L` — comma-separated rule-family axes considered (T=structural, L=linkage, P-citation=cross-doc citations). Default: all axes. B-axis and P-axis (non-citation) are documented placeholders authored case-by-case.

### Mechanical-fixed-point loop semantics (algorithmic illustration)

```text
state ← initial corpus
for pass in 1..pass_cap:
    findings_n ← apply(rules, state)
    log.append(findings_n)
    if findings_n is empty:
        terminate(quiescence)
    if pass >= 2:
        if any identity in findings_n disappeared earlier and reappears now:
            terminate(oscillation)
        if findings_n_identities == findings_{n-1}_identities:
            terminate(semantic-only)
terminate(pass-cap)
```

The pseudocode is illustration only. The actual contract is the property below.

### Property-based convergence spec

> ∀ corpus C, rule set R, finite pass-cap N:
> `run_loop(R, N)` terminates in ≤ N passes with `termination ∈ {quiescence, semantic-only, oscillation, pass-cap}`.

Termination conditions are mutually exclusive at the boundary case. `quiescence` advances the workflow; the other three escape with a warning and require operator inspection.

Oscillation detection is **by semantic identity** `(rule, artifact, field)` — per **Nygard R1**, line numbers shift across passes, so finding-hash-based detection is unreliable. The driver tracks identity, not text.

### Cadence-by-trigger matrix (guidance for consumer repos)

| Trigger | Recommended cadence | Default flags |
|---|---|---|
| Pre-commit hook | per commit | `--loop --pass-cap 3 --axis T,L` (fast; catches structural drift early) |
| CI gate | per push | `--loop --pass-cap 5` (full axes) |
| Nightly sweep | once per day | `--loop --pass-cap 5 --scope corpus` |
| Pre-release | before tag | `--loop --pass-cap 10` (deeper convergence acceptable) |
| Post-incident | after a revert | `--loop --pass-cap 5 --scope corpus --axis T,L,P-citation` |
| Engineer-initiated | on demand | any flag combination |

The matrix is guidance, not enforcement. Consumer repos may calibrate per their failure-class signal (see §Post-mortem ritual + INT-126's `dekspec audit failure-classes` aggregator).

### B-axis + P-axis placeholders

The B-axis (Behavior rules) and the broader P-axis (Policy rules beyond P-citation) are documented placeholders. Specific rules are authored case-by-case as the rule families mature; today the loop respects whichever rules the audit profile (v1, team) declares.

## Recurring Rituals

Operator rituals that recur on a calendar or event cadence rather than belonging to any Mission. Each is engineer-driven; none is automated — governance response to evidence is human work.

### Class-lane evolution ritual

> Origin: Dark Execution Phase 2.J (CUT from the phase list as "not a phase, a recurring ritual"). Consumes the Constitution §Class Lanes table, the failure-class aggregator (§Post-mortem ritual), and the consumer repo's per-class run metrics (e.g. a dashboard's `per_class_revert_rate` family).

**Cadence:** every 30 days once an operator-UX/metrics surface ships in the consumer repo, the engineer reviews aggregate per-class metrics and promotes or demotes classes in Constitution §Class Lanes.

**Promotion criteria** (a class moves one lane toward `dark` only when ALL hold — combined signal, clean-runs alone are insufficient):

- ≥ 15 clean runs over the trailing 30 days
- Zero reverts in the window
- Code Reviewer + Verifier collectively caught ≥ 95% of the issues human reviewers (still gating gated classes) flagged
- Near-miss rate below the repo's threshold (a clean merge that needed a late catch is a near-miss, not a clean signal)
- Inter-reviewer agreement rate above the repo's target

**Demotion criteria** (any one suffices):

- Failure-taxonomy trend warrants demotion (`dekspec audit failure-classes` shows a worsening class pattern)
- 1 revert in a `dark`-lane class triggers immediate review of that class's lane assignment

**Path:** engineer-driven `/dekspec:write-constitution --amend --editorial` on §Class Lanes — a single markdown edit plus an Amendment Log row. **No automation:** no agent proposes, applies, or schedules lane amendments; the ritual is an operator reading evidence and making a governance call.

## Provisional vs. Canonical (INT-128 → ADR-030 / INT-133)

> Per **INT-128** (LOCKED 2026-05-30) and **ADR-030 / INT-133** (2026-06-01). INT-128 first made the asymmetric cost of canonical vs. provisional authoring explicit (MSN-011 case) and added a soft ask→route prompt to `/dekspec:write-mission`. **ADR-030 (INT-133) then made provisional the hard default for BOTH `/dekspec:write-intent` and `/dekspec:write-mission` Creation modes** — canonical-direct authoring now requires an explicit `--canonical` opt-out. Read this before invoking either Creation skill.

### Decision rule

> **If you cannot name the First Intent's body NOW, leave it provisional (the default). Reach for `--canonical` only when you can.**

That is the single load-bearing decision criterion. Under ADR-030 the safe posture is automatic — you opt *out* to canonical, you don't opt *in* to provisional. Everything below is supporting evidence and tooling that backstops it.

### Why the default matters

As of **ADR-030 (INT-133)**, `/dekspec:write-intent <desc>` and `/dekspec:write-mission <desc>` Creation modes land the artifact under `dekspec/provisional/<slug>/` **by default** — no canonical id is allocated and the canonical graph is untouched. Canonical-direct authoring (landing in `dekspec/intents/` or `dekspec/missions/` and allocating the id) requires the explicit `--canonical` opt-out. The provisional-vs-canonical routing is decided by the `dekspec library author-target --kind <K> [--canonical]` verb that both skills call — a single deterministic source of truth, not duplicated skill prose. (Before ADR-030 the default was the reverse — canonical, with `--provisional <slug>` as the opt-in — which is the posture the MSN-011 case below was paid under.)

Canonical artifacts enter the spec graph immediately:

- They are walked by `dekspec audit linkage`, `dekspec doctor`, the constraint compiler, the AGENTS.md soft-layer emitter, and the IR JSON used by the dispatch surface.
- They are linked from sibling artifacts via the typed `Linked Artifacts` derivation (ADR-015).
- They appear in `dekspec/mission-index.md` and the various index files for downstream consumers to discover.
- They participate in the status-maturity coherence model (ADR-020 / MSN-012).

A canonical Mission that never activates ends up cross-referenced by other LOCKED artifacts within days. Eradicating it later requires unlocking each citing artifact, scrubbing the reference, and relocking — an asymmetric cost.

### The MSN-011 case (empirical cost data)

MSN-011 (Builder Integration Protocol umbrella) was authored canonical 2026-05-21 with the intent that its 9-sub-IC fan-out Mission would activate soon. It never activated. By 2026-05-30 it had accumulated 11 canonical cross-references (in 5 LOCKED Intents/ICs + 3 ACCEPTED AEs + 2 Missions + the index). YAGNI surfaced and the Mission was eradicated.

**Eradication cost (canonical):**

- 12 commits across 6 days.
- ~30 minutes of focused engineer attention.
- 5 LOCKED-artifact `transition LOCKED → PROPOSED → ACCEPTED → LOCKED` cycles (one per touched LOCKED artifact, each cycle leaves 3 Amendment Log rows documenting the unlock/edit/relock).
- Hand-edit of ~10 narrative paragraphs in INT-028 + IC-005 to rewrite "MSN-011-as-author" history into "umbrella-effort-future-Mission" framing.
- Sed-batch scrubs across INT-030 / INT-059 / INT-098 / AE-001/005/006 / MSN-010 / MSN-012.

**Hypothetical eradication cost (had it been provisional):**

```bash
rm -rf dekspec/provisional/builder-integration-protocol/
git commit -am "eradicate: provisional builder-integration-protocol incubation (YAGNI)"
```

Single command. Zero canonical churn. Zero audit-trail pollution. The 30-minute / 12-commit / 5-unlock-cycle cost was paid because of one missing `--provisional` flag at authoring time.

### When to choose canonical vs. provisional

**Canonical** is correct when ANY of:

- The First Intent's body is ready to author within the same session. The Mission file is being created as scaffolding for an Intent the engineer is about to write.
- The Mission converts an over-cap Intent (the size analysis recorded a *re-split before acceptance* finding) into a Mission with N child Intents that already have draft bodies.
- An Intent that decomposes into IBs against this Mission already exists and the Mission is missing only because the operator forgot to author it earlier.

**Provisional** is correct when ANY of:

- The First Intent's body is not ready to author NOW (the typical case for a synthesis-driven Mission proposal).
- The Mission is speculative — exploring whether a decomposition is even the right shape.
- The Mission's outcome depends on external work (a Phase 2 in another repo, a calibration corpus that doesn't exist yet, a builder integration that hasn't been requested).
- ANY of the above plus an LLM is authoring the Mission file (LLM authoring is the default-exploring case).

### Substrate (already shipped)

MSN-014 (LOCKED 2026-05-24) shipped the provisional substrate. It is fully operational:

- `dekspec/provisional/<slug>/` folders carry the incubating artifact family.
- Provisional artifacts use `<KIND>-provisional-<kebab-slug>` IDs.
- The constraint compiler, audit linkage, emitter pipeline, and IR JSON are all invisible to `dekspec/provisional/`.
- The `/dekspec:write-mission --provisional <slug>` flag routes authoring there.
- The §Provisional Promotion Gate in `/dekspec:write-mission` Activate Mode detects incubation folders and prompts explicit operator confirmation before walking PROPOSED → ACTIVE.
- The hand-promote workflow (renumber + `git mv`) is canonical (the original `dekspec promote-provisional` CLI verb was retired 2026-05-25; see §Provisional Promotion below for the recipe).

### Creation-Mode routing (INT-128 ask→route → ADR-030 hard default)

INT-128 originally added an interactive §1a.0 commitment prompt to `/dekspec:write-mission` Creation Mode ("Will the First Intent's body be authored within this same session? yes → canonical, no → provisional"). **ADR-030 (INT-133) superseded that live prompt with a deterministic hard default** and extended the posture to `/dekspec:write-intent` as well:

> Creation Mode defaults to **provisional**. No prompt is asked. Canonical-direct authoring requires the explicit **`--canonical`** opt-out. Both skills resolve the target via the `dekspec library author-target --kind <K> [--canonical]` verb.

The operator no longer needs to answer a per-run question or know the `--provisional` flag — provisional is simply the default, and `--canonical` is the one token to remember when a same-session canonical landing is intended. INT-128's motivation (the MSN-011 eradication cost, above) is now encoded in the default posture rather than a prompt.

### Audit backstop: T-MISSION-CANONICAL-WITHOUT-CHILD (advisory P3)

The `T-MISSION-CANONICAL-WITHOUT-CHILD` audit rule (INT-128, registered in `v1.yaml`) fires when:

- A Mission file lives under canonical `dekspec/missions/` (not `dekspec/provisional/`).
- Status is `PROPOSED` (`TODO` before ADR-057).
- `Created` is ≥7 days ago.
- No Intent file declares this Mission via its `Mission:` field.

Severity P3 (advisory; non-gating per ADR-018). Surfaces in `dekspec doctor` output with the recommendation to either demote to `dekspec/provisional/` or kill.

The rule is the **catch-of-last-resort** when the commitment prompt is bypassed or the original First-Intent commitment slips. It does NOT prevent the canonical authoring — it surfaces the drift cheaply 7+ days later.

### Decision tree summary

```
Authoring a Mission:
├─ Is the First Intent's body ready to author NOW?
│  ├─ YES → /dekspec:write-mission <desc>          → canonical
│  └─ NO  → /dekspec:write-mission --provisional <slug> <desc> → provisional
│
└─ Already authored canonical, now noticed it should have been provisional?
   ├─ Still under 7 days, never cross-referenced? → git mv to provisional/, update index
   ├─ Heavily cross-referenced + LOCKED siblings? → kill in place (KILLED status,
   │  Mission file stays, references remain), OR pay the eradication cost
   │  (see MSN-011 case above for what that costs)
   └─ T-MISSION-CANONICAL-WITHOUT-CHILD will surface it at 7-day mark
      regardless — the audit rule is the backstop.
```

### Cross-references

- ADR-015 (derived backlinks) — the substrate that makes provisional folders cheap to walk away from.
- MSN-014 (provisional incubation) — the originating Mission that shipped the provisional/ folder convention.
- MSN-011 (eradicated 2026-05-30) — the case study; see `docs/workspace/cc_provisional-promotion-guardrails-survey.md` for the full survey.
- ADR-018 (P0/P1-clean gate) — explains why the new audit rule is P3 advisory (Mission completion gates on P0/P1-clean, so P3 never blocks).
