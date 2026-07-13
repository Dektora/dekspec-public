# DekSpec Operating Guide
### Version 1.3.0

---

## Why This Exists

AI coding agents fill ambiguity with confident, plausible, wrong decisions. By review time the wrong assumption is load-bearing. The solution is to eliminate ambiguity before the agent starts. Specs are the mechanism.

Agents also forget everything between sessions. Beads are the solution — persistent, Git-native task memory that travels with the repo.

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
| Author an Implementation Brief from a LOCKED WS | Derived | AI default; human reviews | The WS is the spec. The IB translates spec → file list + sequencing. |
| Author beads from a LOCKED IB | Derived | AI default; human reviews | The IB is the spec. The beads enumerate atomic work units. |
| Implement a bead | Derived | AI default; human reviews diff | The bead is the spec. The diff is verifiable against acceptance + tests. |
| Generate tests from acceptance criteria | Derived | AI default | The criteria are the spec. The tests are deterministic against them. |
| Aggregate AGENTS.md from artifacts | Derived | Fully autonomous | The artifacts are the spec. The aggregator is deterministic. |
| Re-derive backlinks (`dekspec relink`) | Derived | Fully autonomous | The forward links are the spec. The backlinks are pure function. |
| Migrate persisted IR forward (`dekspec migrate`) | Derived | Fully autonomous | The migration is itself a typed transformation. |
| Run linkage + drift audits | Derived | Fully autonomous | The audit rules are the spec. The findings are pure function. |

The table is *not* the methodology — it's a heuristic for daily judgment calls. The methodology lives in the Constitution. The heuristic gives a contributor a quick litmus test when the Constitution's prose is too far away.

A project that adopts a different mantra (e.g., "Spec before code", "One bead at a time", "No specless edits") translates the mantra into a different table. The shape stays the same: name the activity, classify against the mantra, declare the default execution mode, justify with a one-line rationale.

When the mantra changes (rare; treated as a Constitution amendment), the table is re-derived. The cascade through downstream artifacts (AE autonomy fields, Mission autonomy ceilings, audit-rule severity tuning, skill catalog filtering, regenerated AGENTS.md) is documented in `docs/dekspec-methodology.md` §"Operating Principles" → "Cascade".

---

## The Workflow

```
                                    Research
  → /dekspec:archeology --scan       (reverse-engineer existing code before specifying)
                                    ─────────────────────────────────
                                    Framing — the driver (commit the direction first)
  → /write-mission                  (only if the work plausibly spans >1 Intent — L0 container)
  → /write-intent                   the committed direction; `--decompose` fans out L2-L4 below
                                    ─────────────────────────────────
                                    Layer 1 — Design & Architecture (inputs, on demand)
  → /write-ae                       (subtype: System / Subsystem / Container / Component / Pipeline / Data Model / Cross-Cutting Concern / Platform Concern / Interface Surface / Workflow / Process). Architecture Elements (AEs) are authored via /write-ae — the skill and its legacy alias predecessor were retired in the DN→AE migration (2026-05-09).
  → /write-adr                      (if undocumented decisions exist — write before writing specs)
                                    ─────────────────────────────────
                                    Layer 2 — Specification
  → /write-ws             behavior contracts, role passes, ADRs, critic
      → /write-adr                  (triggered by Options Architect — goes back to Layer 1)
      → /write-ic   (triggered for cross-component boundaries)
                                    ─────────────────────────────────
                                    Layer 3 — Implementation
  → /write-ibs    spec → one or more Implementation Briefs
                                    ─────────────────────────────────
                                    Layer 4 — Construction
  → /write-code-beads                   one IB → one or more beads + fidelity audit
  → /write-evals                    (before coding — beads with model output only)
  → /write-tests                    (before coding — TDD stubs from acceptance criteria)
  → /dekspec:review-ib              PRE-impl gate (REVIEW_IB): spec packet + bead decomposition → GO / NO-GO
  → /orchestrate-coding-session             orchestrator dispatches sub-agents in parallel worktrees
  → /dekspec:review-pr              POST-impl gate (REVIEW_PR): PR diff vs IB → MERGE / NO-MERGE
      → NO-MERGE → REVIEW_PR_FAIL    grep-loop: seed /code-review --comment, fix real findings, re-review until GO
  → merge → test → promote → next round
```

Each step is a registered Claude Code skill in `.claude/skills/`. Invoke by name (e.g., `/write-adr`).

### End-to-end flow (step-by-step)

> The L1→L4 diagram above is the **layer-dependency** order. Authoring is **initiated at the Intent (or Mission)** — the committed direction is the spine; AE/ADR are the only genuinely hand-authored design inputs (on demand, often pre-existing), and WS/IC/IB/beads/tests are **derivative** of the Intent's decomposition.

1. **Frame & commit (the driver)** — `/write-mission` if the work plausibly spans >1 Intent; `/write-intent` the committed direction. Every Intent ≥ ACCEPTED ships an `outcome_verification`: one user-observable proof under strong-TDD timing (test red first → impl greens it → no other test files touched; ADR-029).
2. **Architecture inputs (on demand)** — `/write-ae` the architecture slice and `/write-adr` any undocumented decision *only if new*; the Intent links ≥1 Source AE (L5), so these are usually referenced/extended, not authored fresh each time.
3. **Decompose (derivative)** — `/write-intent --decompose` fans the Intent into Working Specs + Implementation Briefs; `/write-ws` carries behavior contracts (role passes + critic), `/write-ibs` produces the IBs, `/write-ic` pins any cross-component boundary surfaced. Code-bearing IBs must declare `## Reuse Inventory` ("use X, don't reimplement"); `dekspec lint-ib` enforces it.
4. **Pre-build (derivative, per IB)** — `/write-code-beads` (one IB → beads + fidelity audit); `/write-evals` (model-output beads); `/write-tests` (TDD stubs from acceptance criteria).
5. **Pre-implementation review** — at `REVIEW_IB` (post-ACCEPTED, pre-IMPLEMENTING): `/dekspec:review-ib <IB-ID>` — an Opus-tier orchestrator skill — fans 13 fresh-context adversarial lenses over the spec packet + bead decomposition (math-olympiad shell), a blind aggregator scores them, any single lens ≥80 confidence vetoes. Verdict **GO / NO-GO / INSUFFICIENT_EVIDENCE**; includes the outcome-tdd lens (git-blame: did the outcome test land red first?). Auto-fires on the `REVIEW_IB` transition (INT-108 handler) or invoked manually. No code yet → no fix-loop.
6. **Implement** — `/orchestrate-coding-session` packages the Intent/IB and fans the ready bead set into parallel isolated worktrees; lands an IB-aggregate PR with green CI.
7. **Post-implementation review** — at `REVIEW_PR` (beads CLOSED, CI green, PR open): `/dekspec:review-pr <PR-#>` reviews the diff against the IB it claims to implement via the same shell. Verdict **MERGE / NO-MERGE / INSUFFICIENT_EVIDENCE**. Oversized diff → split into one reviewable IB-aggregate per concern, don't review.
8. **On NO-MERGE → `REVIEW_PR_FAIL` grep-loop** — seed `/code-review <effort> --comment <PR-#>` (line-anchored inline findings), fix only real/relevant ones (read diff first, no unrelated rewrites, a test per fix), commit, re-fire `/dekspec:review-pr` until GO. **RECOMMEND-only** — the human merges.
9. **Merge → test → promote → next round** — `dekspec doctor` is the dogfood gate (Mission/Intent gates require P0/P1-clean).

Both reviews are **RECOMMEND-only at landing** (they emit the verdict + a `dekspec/reviews/` sidecar but don't auto-advance state) and run the shared non-sycophantic math-olympiad orchestration: context-isolated lens specialists ATTACK rather than grade, a blind aggregator scores, and a single confident veto (≥80) overrides any weighted average.

### Intent-granular phase-executors (MSN-018)

`/dekspec:orchestrate-intent <intent>` is the **top-level conductor**: it owns sequencing + the final lock/propagation and **delegates** each phase to a fresh-context, independently-launchable, Intent-granular phase-executor. The three executors each operate over *all* of an Intent's work and can be run standalone or driven by the conductor:

| Conductor gate | Phase-executor | Does |
| --- | --- | --- |
| Specification | `/dekspec:spec-intent <intent>` | DRAFT → ready-for-coding: sequences `/write-intent --analyze`/`--accept`(engineer-gated)/`--decompose` + the `write-*` authoring skills; stops at the coding boundary |
| Implement | `/orchestrate-coding-session <intent>` | codes **all** the Intent's beads in parallel isolated worktrees |
| Land | `/dekspec:land-intent <intent>` | drives **all** the Intent's IB-aggregate PRs through `review-pr` + the grep-loop to operator-confirmed merge (never auto-merges; ADR-026) |
| Lock | `/write-intent --lock` | the conductor's own ownership — freeze + propagate downstream |

Delegation is structural, not stylistic: the coding executor and the review pipeline depend on context isolation (ADR-026 solver-cannot-verify-self), which an inline conductor body would defeat. `--auto` walks the same delegated sequence without per-step prompts, honoring the ADR-021 safety contract.

**Auxiliary skills** (not part of the L1-L4 main pipeline but ship in the library):

-  — record a system-level divergence (instruction-violation, spec-fidelity, capability-gap) as a numbered `DIV-NNN-*.md` note.
- `/dekspec:archeology` — brownfield spec-gap recovery: scan an orphaned code surface, propose a retroactive Intent skeleton, and ratify it through `/write-intent --accept`. Replaces the retired `/do-code-archaeology` skill (2026-05-24).
- `/dekspec:brownfield-ingest` — classify inherited markdown prose (Confluence exports, inherited PRDs, design wikis) into DekSpec artifact slots via `dekspec ingest`.
- `/write-ggc` — log domain corrections, add glossary terms, audit terminology health.

*The listener side of the async inbox/listener dispatch pattern (originally `/dekspec:dispatch-inbox-listener`, later `/dekspec:factory-listen`) was excised from this library in INT-099 — 2026-05-27 — when the factory surface moved to `Dektora/dekfactory` as an independent plugin. AE-009 still defines the inbox/outbox contract; the listener implementation now lives in the dekfactory plugin.*

**System health:** `/doctor` checks cross-reference consistency across all artifacts, skills, templates, and governance files. Run it after modifying skills, templates, or the operating guide, and periodically to catch drift. The skill is the canonical audit since the DN→AE migration (2026-04-27).

Layer boundaries are phase transitions — crossing from one layer to the next changes what kind of work you are doing. The role system and expertise audit are Layer 2 mechanisms that can trigger Layer 1 artifact creation (e.g., the Options Architect surfaces a decision that needs an ADR).

---

## The Artifacts

The DekSpec process organizes artifacts into four layers. Each layer has a distinct purpose and authority. Work flows downward through the layers; conflicts resolve upward.

```
Layer 1 — Design & Architecture  (the project's source of truth)
  System Vision · Architecture Elements · ADRs · Domain Glossary

Layer 2 — Specification  (behavioral contracts — the "how")
  Working Specs · Interface Contracts

Layer 3 — Implementation  (agent-executable plans)
  Implementation Briefs

Layer 4 — Construction  (code, tests, evals, reviews)
  Beads
```

| Layer | Artifact | What it is | Where |
|-------|----------|-----------|-------|
| 1 | System Vision | Why the system exists, what success looks like, what we're not building. One per system. | `dekspec/system-vision.md` |
| 1 | Architecture Element (AE) | Canonical descriptive artifact for a coherent architectural slice — a system, subsystem, container, component, pipeline, data model, cross-cutting concern, platform concern, interface surface, or workflow/process. Every AE declares a subtype and links to related ADRs, WSs, ICs, IBs. Replaces the legacy Design Note artifact. | `dekspec/architecture-elements/AE-NNN-[slug].md` |
| 1 | ADR | One architectural decision — immutable once accepted. | `dekspec/adrs/ADR-NNN-[slug].md` |
| 1 | Domain Glossary | Canonical definitions for all domain terms — proactive reference read before writing any artifact. | `dekspec/domain-glossary.md` |
| 2 | Working Spec | Behavioral contracts for a feature or subsystem. | `dekspec/working-specs/WS-NNN-[slug].md` |
| 2 | Interface Contract | Cross-component boundary definition — consumed by independently-built components. | `dekspec/interface-contracts/` |
| 3 | Implementation Brief (IB) | Everything a coding agent needs for one session. | `dekspec/impl-briefs/` |
| 4 | Bead | Atomic work unit — one commit-cluster on the IB branch (ADR-025). | `.beads/beads.jsonl` |

**Filename convention (per ADR-012).** L0 singletons — those that are unique per repository (System Vision, Domain Glossary, Guidance and Corrections, the planned Constitution) — use **slug-only filenames** like `system-vision.md`. Layer 1+ artifacts — those authored repeatedly under a counter (AE, ADR, WS, IC, IB, Intent, Mission) — use **`TYPE-NNN-slug.md` filenames** like `AE-001-dekspec.md`. The split reflects cardinality: singletons have no counter dimension, so none appears in the name; L1+ artifacts do, so the counter is load-bearing. Both `dekspec init` and the parser's kind detection honor this rule; the methodology doc §4 has the long-form discussion.

### Authority and Conflict Resolution

Each Layer 1 artifact has authority over a distinct domain:

- **System Vision** — authority over system identity and scope
- **Architecture Elements** — authority over the description of architectural slices (what the slice is, its boundary, its responsibilities, and its relationships)
- **ADRs** — authority over specific architectural decisions
- **Domain Glossary** — authority over terminology, definitions, and naming conventions

These are complementary, not competing. An Architecture Element describes a slice; an ADR records a specific decision that shapes one or more AEs. The System Vision constrains what AEs can describe.

**Within Layer 1:** Contradictions are consistency bugs, not governance disputes. When a Layer 1 artifact contradicts another, the resolution is always to make Layer 1 internally consistent — never to let one artifact silently override another. An ADR can legitimately exist in tension with an AE's description if the ADR records a deliberate tradeoff, but the tension must be acknowledged in the ADR and reflected in the AE. Silent contradictions are never acceptable. When any Layer 1 artifact changes, review all Layer 1 artifacts that reference it for consistency.

**Across layers:** ADRs govern all work in Layers 2–4. A Working Spec that contradicts an ADR must be corrected. An Implementation Brief that contradicts a spec must be corrected. A bead that contradicts an IB must be corrected. Resolution always flows upward to the highest layer where the inconsistency lives.

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

Reactive corrections that surface during spec writing land in `guidance-and-corrections.md` via `/write-ggc --log`. Each recurrence is tracked. At 3 recurrences, the entry is auto-promoted to a glossary row. All authoring skills invoke `/write-ggc --log` when they correct a domain misinterpretation.

### Artifact Lifecycle — Locking

Every artifact type (System Vision, Architecture Element, ADR, Working Spec, Interface Contract) moves through `TODO → DRAFT → PROPOSED → ACCEPTED → LOCKED`. Any artifact may also be set to `DEPRECATED` from any stage. ADRs have an additional ADR-specific terminal state, `SUPERSEDED`.

- **TODO** — placeholder; needs review and rewrite against current system state
- **DRAFT** — being written; anything goes
- **PROPOSED** — complete draft ready for engineer review; not yet accepted
- **ACCEPTED** — engineer approved; downstream work may exist; substantive changes allowed but must cascade to all affected downstream artifacts
- **LOCKED** — frozen; editorial amendments only (typos, grammar, formatting — no meaning change)
- **DEPRECATED** — terminal; retired when the artifact is no longer needed (redundant with other artifacts, or planned work abandoned). Set Status to DEPRECATED and add a Deprecation Note explaining what supersedes it.
- **SUPERSEDED** — terminal, ADR-specific; the decision has been replaced by a newer ADR. Set Status to SUPERSEDED and record the replacement in the Supersession field (*Superseded by:* ADR-NNN).

**Unlocking:** A LOCKED artifact can be unlocked back to PROPOSED when substantive changes are needed. The Amendment Log records the unlock and the reason. Unlocking triggers a full downstream cascade review.

Each artifact carries an Amendment Log to record changes made after locking or when unlocking.

**Post-Wave-3 steady state (2026-04-24, per ws-audit proposal §13 item 11).** After Wave 3 (IB/bead cascade) completes, the WS + IC + IB + bead corpuses are in steady state with respect to the ADR / DN convergence campaigns of 2026-04-23 and 2026-04-24. Drift is prevented going forward by running the refined WS audit checklist (per `dekspec/audits/ws-audit/ws-audit-process-proposal-2026-04-24.md` §3) at every subsequent L2 artifact change (at `--audit`, `--accept`, and `--lock` gates of `/write-ws`). An equivalent IC audit follows per the IC-audit proposal (see `dekspec/audits/ic-audit/ic-audit-process-proposal-<date>.md`).

---

## Intents

Intents (`INT-NNN`) are DekSpec's mechanism for **cross-component change drivers**. An Intent is a single LOCKable, machine-verifiable unit of work that the system commits to landing or explicitly abandoning. Intents sit *orthogonal* to the L1–L4 layer system: they cut horizontally across components, drive changes vertically into each affected component's layer stack, and dissolve at LOCKED into the artifacts they produced (revised AEs, new ADRs, revised WSes, new ICs, IBs, beads, code).

Equivalent framing along the vertical axis: Intent and Mission are **L1-anchored** (their typed graph link is `linked_architecture_elements` — they pin into AEs, not WSs / ICs) and **reach through L2-L4** (they spawn L3 IBs, may revise L2 WSs / ICs, and carry L4-surface `verification` / `rollback` / `kill_criteria` commands the audit's L9 rule resolves to executable scripts). They fit in a layer — L1 — but span it downward to the executable surface. The two framings (horizontal orthogonal-to-layers; vertical L1-anchored-reaching-down) are complementary descriptions of the same artifact shape.

```
              Mission (optional, MSN-NNN)
       ─────────────────────────────────────────
        │   queue of Intents in execution order  │
        │   shared Outcome / flag / rollback     │
       ─────────────────────────────────────────
                          │
                          ▼  (one Intent active at a time)

                Components / Boundaries
          ┌──────────┬──────────┬──────────┐
          │ Comp A   │ Comp B   │ Comp C   │
L1 ADR    │          │  new ADR │          │
   AE     │          │          │  new AE  │
L2 WS     │ revise   │  revise  │  new WS  │
   IC     │       revise IC ◄──►            │
L3 IB     │ IB-001   │  IB-002  │  IB-003  │
L4 Bead   │ beads    │  beads   │  beads   │
          └──────────┴──────────┴──────────┘
                         ▲
                         │
        Intent ════════════════════════════▶
              cuts horizontally across
              components and boundaries
```

An Intent is not a layer; it is a *driver* that an engineer or autonomy brain runs *through* the layered system. Single-component changes are still authored as Intents — they are simply Intents whose `Components affected:` field lists exactly one component.

**Files canonical, branch-scoped during draft.** Every Intent lives at `dekspec/intents/INT-NNN-<slug>.md` and is drafted on its own branch `int/INT-NNN-<slug>` until `--lock`. The branch creates a natural sandbox for the diff; the file is the canonical record at every status transition; the index (`dekspec/intent-index.md`) tracks the active queue and the archive.

### Lifecycle

```
DRAFT → OVERSIZED ──► SUPERSEDED  (terminal off-ramp; size cap exceeded)
  │
  └─────► PROPOSED → ACCEPTED → IMPLEMENTING → TESTPASS → MERGED → LOCKED
                                    └──► `--testpass` failures append to the
                                         TESTFAIL records log and loop back here
```

| Status | Transition trigger | What happens |
|---|---|---|
| `DRAFT` | `/write-intent <description>` | Intent file written; `int/INT-NNN-<slug>` branch created; type-default Autonomy + Verification populated |
| `OVERSIZED` | `--analyze` exceeds any hard cap | Intent cannot promote without splitting or re-scoping; off-ramp to `SUPERSEDED` if abandoned |
| `PROPOSED` | `--analyze` clean | Coverage report + size assessment populated; Verification predicate filled; engineer has not yet accepted |
| `ACCEPTED` | `--accept` (engineer-only) | Ready for `--decompose` |
| `IMPLEMENTING` | `--decompose` | IBs (multi-WS IUs) and direct beads (single-WS IUs) scaffolded; coding sessions run on the int/ branch. On `--testpass` failure (Verification or diff-confinement) a TESTFAIL record is appended and Status stays IMPLEMENTING |
| `TESTPASS` | all Verification checks green; diff confinement clean | Branch is ready to merge to `main` |
| `MERGED` | engineer merges branch to `main` | Manual transition; signals the diff has landed |
| `LOCKED` | `--lock` (run from `main`) | Intent is the executed commitment; appended to Mission Intent queue if `Mission:` is set |
| `SUPERSEDED` | `--supersede` (Phase 2-3 flag) | Replaced by a successor Intent recorded in `Superseded-By` |

*`TODO` and `TESTFAIL` were retired from the Intent enum 2026-05-25 (E3 audit — neither was observed across 99-Intent history; the `TESTFAIL ↔ TESTPASS` round-trip never fired). Files authored against the legacy enum are rejected at `dekspec validate`; transition them to `DRAFT` or `IMPLEMENTING` respectively. The TESTFAIL records section in the Intent template is retained as a captured-failure log on the IMPLEMENTING → TESTPASS path; it no longer corresponds to a Status flip. **Note (ADR-027, LOCKED 2026-05-29):** the retirement above stands at the **Intent** level. The `TESTFAIL` status was re-introduced at the **IB** level by INT-102 (LOCKED) as part of the MSN-017 two-tier review pipeline; ADR-027 formalizes that the empirical basis for retirement (zero round-trip occurrences) no longer applies because the new action-handler framework (INT-108) explicitly engineers the IB-side `IMPLEMENTING ↔ TESTFAIL ↔ IMPLEMENTING → TESTPASS` round-trip.*

**Type-default Autonomy (INT-094).** The `## Autonomy` field of a new Intent is populated by `/write-intent` Creation Mode from a type-dispatched default rather than a flat `manual`: `medium` for `bug` / `refactor` / `documentation` (categories where CI green is sufficient proof of correctness); `manual` for `feature` / `nfr` / `adr-driven` / `environment` (categories that warrant explicit operator sign-off). Engineers override per Intent via the inline `autonomy:` cue. The per-type default exists to honor downstream auto-merge surfaces (e.g. DekFactory INT-063 — auto-merges MRs at `auto-medium`+ once CI is green) without forfeiting that surface for well-bounded code-mod Intents. See `templates/intent-template.md` §Autonomy and `plugins/dekspec/skills/write-intent/modes/create.md` Step 4 for the authoritative wiring.

### Serialization

**Per-Mission serialization, advisory enforcement (ADR-016).** Intent serialization is scoped to the Mission. Within a single Mission, at most one child Intent should be in active status at a time — child Intents are dependency-ordered, so the Mission's Intent queue is also its serialization queue. Active means any non-terminal status: `DRAFT`, `PROPOSED`, `ACCEPTED`, `IMPLEMENTING`, `TESTPASS`, `MERGED`. `OVERSIZED`, `SUPERSEDED`, and `LOCKED` are paused or terminal and are not counted.

Across distinct Missions, and for Mission-less standalone Intents, there is no serialization limit — independent workstreams proceed in parallel. Enforcement is advisory: `/write-intent` Creation Mode never refuses on serialization grounds; the gate of record is a `dekspec audit linkage` finding that surfaces when a Mission carries more than one active Intent. The orchestration brain (Phase 4, deferred) may parallelize across *Missions* (independent feature flags, independent components); it never parallelizes *within* a Mission.

The repo-wide count of active Intents is a separate backlog-health signal, not a serialization rule — a large active-Intent backlog erodes review bandwidth and lets cross-artifact linkage rot (see ADR-015), and may warrant its own advisory finding, but it never blocks creation.

*ADR-016 superseded the original Decision #9 ("one active Intent across the whole repo," hard-enforced at `/write-intent` Creation Mode). That rule was never ratified in an ADR and was, in practice, violated by nearly every Intent — by 2026-05-20 the library self-spec held 19 active Intents against a stated cap of 1.*

### Hard size caps

`--analyze` measures five caps. Any cap exceeded transitions the Intent to `OVERSIZED`. There is **no engineer-side override** — the only path forward from OVERSIZED is splitting the Intent or re-scoping.

| Cap | Limit | Why |
|---|---|---|
| Implementation Units (IBs / direct beads) | ≤ 3 | The Intent stays small enough to review as a single coherent change |
| Components affected | ≤ 3 | Prevents accidental cross-cutting sprawl |
| New L1 artifacts (AEs) | ≤ 1 | New L1 work is its own discipline; one new AE per Intent is the natural unit |
| New + revised L2 artifacts (WSes + ICs) | ≤ 3 | Caps the multi-WS reconciliation surface (Decision #12) |
| Coverage gaps | ≤ 2 | An Intent that surfaces too many gaps is doing two jobs at once |

WS-028 in v3/v4 (5 IBs, 1 component, ~3,817 LOC) is the empirical witness — `--analyze` would mark it `OVERSIZED` immediately. The retrofit at `INT-000` (Phase 1 P1.8) validated this end-to-end: the size-cap mechanism caught WS-028 exactly as designed.

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

### Verification, diff confinement, --testpass, --lock

**Verification** is the machine-checkable predicate that defines `TESTPASS` (Decision #13). Every Intent's Verification block is a list of named cmd checks; `--testpass` runs each, captures exit code and output, and transitions to `TESTPASS` only when every check exits zero. A non-zero exit fast-fails (subsequent checks are not run, since they may depend on invariants the failing one guards) and records the failure in TESTFAIL records.

**Diff confinement** (Decision #14) runs *before* the Verification predicate. `--testpass` Step 2 computes the union of files changed on the int/ branch since it diverged from `main` and confirms every changed file matches at least one glob in the Intent's `Components affected:` (resolving named components via the CLAUDE.md Component → File-Glob Map). An out-of-scope edit appends a TESTFAIL record (Status stays IMPLEMENTING — the TESTFAIL Status flip retired 2026-05-25) even when every Verification check would have passed — the gate that prevents Intents from quietly growing scope.

**`--lock`** runs post-merge from `main`. It refuses unless the Intent is in `MERGED` status and the Verification block is byte-identical to the version `--testpass` last ran against (so the commit history's executed-commitment matches what was verified). On success, it transitions `MERGED → LOCKED`, moves the Intent's row from the Active queue to the Archive in `intent-index.md`, and (when `Mission:` is set) appends a one-line LOCKED row to the Mission's Intent queue.

### Bead execution: EPCV inner loop

Beads exist *before* the accept gate fires — they are authored during the `--analyze` → PROPOSED phase and are part of the spec packet the engineer reviews at `--accept` (ADR-025). The `Explore → Plan → Code → Verify` (EPCV) loop (Decision #19) therefore begins its Plan phase at the PROPOSED → ACCEPTED transition, not after `--decompose`. By the time Status reaches IMPLEMENTING, every bead's scope, constraints, and acceptance criteria are already locked in.

Each bead's execution still runs through the full EPCV loop inside `/orchestrate-coding-session`: Explore (read the bead + target files), Plan (interface-first design), Code (implement + tests), Verify (bead acceptance criteria pass). EPCV is the unit-of-work discipline at the bead level; the Intent's Verification predicate is the unit-of-work discipline at the Intent level. The two compose: each bead's Verify step ensures the bead's acceptance criteria pass before the bead closes; the Intent's `--testpass` ensures the integrated whole passes before the Intent advances.

See `## Coding Session Protocol` below for the full EPCV / bead-runtime detail.

### Recovery playbook

When an Intent encounters a failure that doesn't fit the standard `TESTFAIL → fix → re-testpass` loop — e.g., the Verification predicate's TBD scripts aren't in place, the diff confinement reveals the `Components affected:` list itself is wrong, the size cap is exceeded post-decomposition, or an upstream artifact (AE/ADR/WS) is found inconsistent during implementation — the recovery playbook (Decision #18) defines the four moves: **revise scope**, **escalate to a prerequisite Intent**, **abandon and supersede**, or **route the underlying issue to its proper artifact**. The playbook detail is authored as a follow-on documentation Intent when the first real recovery scenario surfaces; until then, the four-move framing is enough to keep the recovery path bounded.

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

The `/write-intent` skill owns the full Intent lifecycle. Phase 1 flags (all implemented):

- **(no flag)** — Creation Mode. Author a new Intent from the engineer's description; enforce serialization; create the int/ branch; populate Autonomy + Verification from the type defaults.
- **`--analyze`** — Top-down coverage check, bottom-up archaeology (delegates to `/dekspec:archeology --scan` plus the optional 5-phase deeper-investigation mental model in Scan Mode), 5 hard size caps, type-specific field validation, WS-fan-in per IU, drift checks (audit-v2 D19 / D20), Mission Autonomy ceiling validation. Promotes DRAFT → PROPOSED on clean run, DRAFT → OVERSIZED on cap exceedance.
- **`--accept`** — Engineer-only gate; PROPOSED → ACCEPTED.
- **`--decompose`** — Scaffold IBs (multi-WS IUs, via `/write-ibs`) and direct beads (single-WS IUs, via `/write-code-beads`); for `type: bug`, scaffold the failing-test bead as IB-1 via `/write-code-beads --bug-reproduction`. ACCEPTED → IMPLEMENTING.
- **`--testpass`** — Diff confinement + Verification predicate evaluation; IMPLEMENTING → TESTPASS on clean, or Status stays IMPLEMENTING on failure (TESTFAIL record appended to the captured-failure log; the `TESTFAIL` Status flip retired 2026-05-25).
- **`--lock`** — Post-merge from `main`; MERGED → LOCKED; archive in `intent-index.md`; append to Mission Intent queue if applicable.

Phase 2/3 flags deferred: `--sync` (post-implementation catch-up), `--audit` (health check), `--review` (interactive walk-through), `--amend` (mid-flight changes).

The full skill spec lives at `dekspec/skills/write-intent/SKILL.md`.

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
TODO → ACTIVE → COMPLETING → COMPLETE
         │
         └─► KILLED                  (kill criteria triggered or owner abandons)

         any non-terminal → SUPERSEDED  (substantive near-immutable change)
```

| Status | Transition trigger | What happens |
|---|---|---|
| `TODO` | `/write-mission <description>` | Near-immutable section written; no child Intent has reached LOCKED yet |
| `ACTIVE` | `--activate` (gate: ≥ 1 child Intent in LOCKED status, audit-v2 L8) | At least one Intent locked under the Mission; execution underway |
| `COMPLETING` | `--complete` (intermediate state) | Flag (if any) on, all known Intents LOCKED; awaiting Mission Verification |
| `COMPLETE` | `--complete` (Mission Verification predicate evaluates true) | Outcome verified; flag-removal Intent (if any) LOCKED; Mission archived |
| `KILLED` | `--kill` (kill criterion triggered or engineer abandonment) | Rollback executed; archived with reason |
| `SUPERSEDED` | `--supersede` (substantive near-immutable change needed) | Successor Mission created; source archived |

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

- **Intent queue** — ordered list of child Intents. As work proceeds, sketches become drafts, drafts become LOCKED. Order is execution order — at most one Intent in active status at a time across the repo (Decision #9), so the queue is also the serialization queue
- **Discovered prerequisites** — coverage gaps surfaced during child Intent `--analyze` runs that retroactively belong to the Mission as a whole
- **Burndown** — LOCKED / Estimated total / Sketches. Surfaces remaining work; not a hard gate
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

The `--complete` flag runs this predicate as the gate on `COMPLETING → COMPLETE`. Fast-fails on first non-zero exit; reverts Status to `ACTIVE` on failure with the failing check recorded; surfaces for engineer fix.

### Mission ↔ Intent linkage (audit-v2 L8)

When a child Intent's `Mission:` field references a Mission, audit-v2 rule **L8** verifies the linkage is bidirectional:

- The Mission's Intent queue lists the child Intent
- The child Intent's `Mission:` field references this Mission
- The child Intent's `Autonomy:` value ≤ the Mission's `Autonomy_ceiling`

L8 fires at `--accept` (warning) and `--lock` (hard fail). The Mission's Intent queue is appended on the child Intent's `--lock` (one-line append; `/write-mission --review` handles richer queue updates).

### Skill: `/write-mission`

The `/write-mission` skill owns the full Mission lifecycle. Phase 2 flags (all implemented):

- **(no flag)** — Creation Mode. Author a new Mission from the engineer's description; gate-check that work justifies a Mission (refuse single-Intent-shaped requests); draft the near-immutable section in full; save as `TODO`.
- **`--review`** — Revise the live section. Refuses to edit near-immutable fields; surfaces substantive-change attempts as `--supersede` candidates.
- **`--activate`** — `TODO → ACTIVE`. Promotion gate: at least one child Intent in `LOCKED` status.
- **`--complete`** — `ACTIVE → COMPLETING → COMPLETE`. Promotion gates: every child Intent LOCKED, flag (if any) on, flag-removal Intent (if any) LOCKED, Mission Verification predicate evaluates true.
- **`--kill`** — Terminal abandonment. Records kill reason + rollback action; moves to Archive.
- **`--supersede`** — Creates successor Mission; marks source `SUPERSEDED`.

The full skill spec lives at `dekspec/skills/write-mission/SKILL.md`.

### When a Mission is **not** the right answer

Some shapes look like Missions but aren't:

- **Single-component refactor across many files** — that's still one Intent (with `type: refactor`), even if it touches many files. Components affected may include all of them; Mission ceremony is overhead.
- **A multi-stage rollout of one feature with no flag, no shared kill criterion, and no decomposition into independent Intents** — that's one Intent shipped through `--decompose`. The Intent's IBs already provide the multi-stage rigor.
- **A backlog grouping** — Missions are *committed* to land; a backlog grouping is exploratory. Backlogs live in the tracker (Decision D3 / v5 §22) until they're triaged into actual Mission or Intent commitments.

If the work doesn't pass the conditional rule, run `/write-intent` directly. The Mission rigor is too much overhead for work that fits one Intent.

---

## Roles

13 roles across 3 categories. Roles load domain knowledge the model doesn't
reliably have by default. All role definitions and prompts live in
`dekspec/project-context.md`.

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
| Planning Agent | Finalized spec → briefs + beads |
| Coding Agent | Executes beads — fungible, any agent any bead |
| Eval Agent | High-domain-risk beads before coding begins |
| SDET | Before coding — deterministic tests from bead acceptance criteria |

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
- **Eval hooks:** Mandatory for Core beads that produce model output. Required only if explicitly triggered for Supporting/Generic.

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

**Lock when stable.** ADRs progress through `TODO → DRAFT → PROPOSED → ACCEPTED → LOCKED`. Move to `LOCKED` when the decision has proven stable. Once `LOCKED`, only editorial amendments (typos, grammar — no meaning change) are permitted. Unlock back to PROPOSED for substantive changes.

**Past tense in Context.** The Context and Decision Drivers section describes what was true when the decision was made, not what is true now. Decision drivers are listed explicitly, not buried in prose.

**Specific rationale.** The Decision section states why this option was chosen in this system's specific context — not generic praise of a technology.

**Validation is required.** Every ADR states how to confirm the decision was correct after implementation — observable criteria, metrics, or conditions that would trigger reconsideration.

**Links.** Reference related ADRs, specs, or external resources.

Full backlog, format, and index: `dekspec/adr-index.md`

---

## Test Strategy

### Tests vs. Evals

These are different things. Both are required. Neither replaces the other.

```
Tests    → deterministic behavior: given input X, output Y always
           binary pass/fail, fast
           written before and during coding session

Evals    → probabilistic behavior: model output within acceptable range
           threshold: passes at ≥ N% of cases, slower
           written by Eval Agent before session only
```

**Decision rule:** does this bead produce model output? If yes — needs both tests and evals. If no — tests only.

### Test Pyramid

Tests map to DekSpec layers. Each level has a distinct source artifact, lifetime, and location:

| Level | Source Artifact | Location | Lifetime | When Written |
|-------|----------------|----------|----------|-------------|
| Contract assertions | IC/WS constraint tables | `tests/contracts/` | Permanent (regen on spec change) | Auto-generated from constraints |
| Bead tests (TDD) | Bead acceptance criteria | `tests/bead/` | Ephemeral (promote or delete at close) | `/write-tests` before session, extended during session |
| Property-based invariants | WS business rules + formulas | `tests/properties/` | Permanent | Hand-crafted (Hypothesis) |
| Regression tests | Promoted from bead tests | `tests/regression/` | Permanent (with provenance) | Promoted at bead close |
| Integration tests | IB cross-bead data flow + ICs | `tests/integration/` | Permanent | After all IB beads close |
| Behavioral evals | WS eval hooks | `tests/evals/` | Permanent | `/write-evals` before session |

### Promotion Over Regeneration

Bead tests are ephemeral work-order verification. Valuable ones get **promoted** to the permanent regression suite. Tests are never auto-regenerated from spec prose — that produces tautological or vacuous tests.

**Two-gate promotion:**
1. **Gate 1 (automated):** test references a WS business rule or IC constraint ID in its docstring
2. **Gate 2 (engineer):** batch approve/reject in the Phase 4 landing report

At bead close: promote candidates, engineer batch-approves, bead test files deleted at merge to main. No accumulation.

### Golden I/O

For numerical or data-transformation IBs, the engineer writes 2-3 concrete input/output pairs with exact values in the IB's Done When section. This is the single most effective defense against AI self-validation — the coding agent cannot game a test whose expected output was fixed before implementation began.

### Contract Tests

Dtype, device, shape, and value range assertions can be mechanically derived from spec and IC constraint tables and placed permanently in `tests/contracts/`. These regenerate automatically when the source spec changes. Business-rule logic tests require human or coding-agent authorship — the gap between spec language and code is in the test setup, not the assertion.

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

When `/write-ibs --resync` runs, it produces a regression impact list — which regression test files trace back to the changed spec via provenance headers. Contract tests in `tests/contracts/` regenerate automatically. Engineer decides keep/delete/defer for regression tests per file.

---

## Working Spec Structure

Standard sections: what this does, what it does NOT do, interfaces, business rules, failure behavior, open issues.

**Dektora additions** (include only when applicable, delete otherwise):
- **Model behavior contract** — when spec touches injection/model
- **Graph behavior contract** — when spec touches shadow graph/Neo4j
- **Timeline behavior contract** — when spec touches topic segmentation, quantization tier assignment, decay/reactivation, or shadow timeline/PostgreSQL consistency
- **Quantization contract** — when spec touches tensor operations
- **Eval hooks** — for every behavior involving model output only; deterministic behaviors get test cases in the Done When checklist, not eval hooks

**Rules:**
- Every business rule must be testable
- Every failure mode must have a stated behavior
- Open questions are stated explicitly — never buried in vague prose
- 1-2 pages maximum — if you need more, split the spec

---

## Implementation Brief (IB)

One IB = one PR to main. Each bead is a commit-cluster on the IB branch, not a separate PR (ADR-025).

A Working Spec typically produces multiple IBs — one per component or data-flow stage. Each IB covers exactly what can be implemented and verified as an independent unit. The IB distills its portion of the Working Spec into agent-executable form. It copies spec context **verbatim** — not summarized. The coding agent has no access to the spec; everything it needs must be in the IB.

What the IB adds beyond the spec:
- Exact files to modify
- Domain constraints explicit: CUDA device, tensor dtype, read/write path, precision threshold, do-not-touch functions
- ADR decisions as one-sentence implementation rules
- Done when checklist — verifiable, not vague

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

### Changing Artifacts After Downstream Work Exists

Going back is always allowed. Changes cascade downward through the layers.

**Layer-aware cascade:**

```
Layer 1 change (ADR added/revised, Architecture Element amended)
  → Review all Layer 1 artifacts that reference it for consistency
  → Review affected Layer 2 artifacts (Working Specs, Interface Contracts)
  → Regenerate affected Layer 3 artifacts (IBs)
  → Regenerate affected Layer 4 artifacts (beads)

Layer 2 change (spec revised)
  → Review affected IBs — update or delete and regenerate
    via /write-ibs
  → Delete all open beads for affected IBs
    (br delete BEAD-NNN — IB change is a start-over)
  → Re-run /write-code-beads
    (fidelity audit runs automatically — no separate step)
  → Proceed to /orchestrate-coding-session

Layer 3 change (IB revised)
  → Delete all open beads for this IB and recreate
```

The engineer decides when a change is needed — a new ADR, a role pass that reveals a wrong assumption — and cascades the change downward through all affected layers.

Only open beads can be deleted. If any bead is `in_progress` or `closed`, coding has already started — stop and make an explicit decision about whether to continue, revert, or file a correction bead.

**Cascade implementation reference:**

| Trigger | Authoritative skill + mode | Reference |
|---------|---------------------------|-----------|
| Layer 1 change (ADR / Architecture Element revised) | manual (engineer-driven); review propagates through `/write-ws --audit` and `/write-ic --audit` on downstream artifacts | `dekspec-operating-guide.md` §Changing Artifacts After Downstream Work Exists |
| Layer 2 change (Working Spec revised, IBs already exist) | `/write-ibs --resync` | `.claude/skills/write-ibs/SKILL.md` §Resync Mode |
| Layer 3 change (IB revised, beads already exist) | `/write-code-beads --rebuild` | `.claude/skills/write-code-beads/SKILL.md` §Rebuild Mode |
| Interface Contract unlocked | `/write-ic --unlock` then downstream impact check | `.claude/skills/write-ic/SKILL.md` |
| ADR superseded | `/write-adr` (supersession fields) + manual cascade into dependent specs | `.claude/skills/write-adr/SKILL.md` |

### IB Boundaries and Production Gates

The IB boundary is defined by what can be verified as a unit. Beads within an IB are ordered by **technical dependency only** — bead 2 waits for bead 1 because it needs bead 1's code. No production validation inside an IB.

Production gates sit **between IBs**, not within them. When you need production validation before proceeding, that is the signal you have two IBs, not one.

**Common pattern — refactoring before new implementation:**

```
IB-1: Refactor [component]
  Goal: restructure without changing behavior
  Beads: BEAD-1, BEAD-2, BEAD-3
  Production gate: deploy, verify [specific observable] unchanged

IB-2: Implement [new behavior]
  Depends on: IB-1 — production gate
  Beads: BEAD-4, BEAD-5
```

The gate is **engineer discipline**, not tooling. IB-2's beads are created but the engineer does not claim or start any of them until IB-1 is deployed and the observable is verified in production. The observable must be stated specifically in the IB — not "looks good" but a concrete checkable signal. If it can't be stated specifically, the gate criterion belongs in the spec first.

**Two IB dependency types:**

| Type | Meaning | Enforced by |
|------|---------|------------|
| Technical | Next IB's code depends on this IB's code being merged | Bead `depends_on` field |
| Production gate | Next IB depends on IB-1's behavior verified in production | Engineer discipline |

---

## Beads

Beads are Layer 4 — Construction. Crossing from Layer 3 (Implementation Briefs) to Layer 4 is a phase transition: you stop planning and start building. The engineer's role shifts from "verify the plan is correct" to "verify the output matches the plan."

A bead is the atomic work unit for a coding agent. One bead = one session = one commit-cluster on the IB branch; the IB itself is the unit that opens a PR to main (ADR-025).

Beads come from Implementation Briefs via `/write-code-beads`. **The goal is simple: the bead must contain everything a competent coding agent needs to do its job nearly perfectly — without reading any other document, asking any clarifying question, or making any domain assumption.** Domain expertise lives in the bead. The coding agent is fungible because the bead is complete.

### Bead Format

Beads are created via the `br` CLI using `/write-code-beads`. The canonical bead format uses structured markdown across three `br update` fields (`--description`, `--design`, `--acceptance-criteria`). See `.claude/skills/write-code-beads/SKILL.md` for the full field mapping and creation sequence.

**Summary of bead structure:**
- **`--description`**: Goal, Files, Constraints and Decisions, Domain Constraints, Escalation
- **`--design`**: Do Not Touch, Out of Scope, Governing ADRs, Interface Contracts
- **`--acceptance-criteria`**: Acceptance Criteria (with verification type per item), Evals, Test File reference

The bead must contain everything a coding agent needs. The coding agent reads only the bead — not the IB, ADRs, or Working Spec.

### Bead Commands

```bash
bv --robot-insights                    # what to tackle first (bv = bead viewer, a companion to br)
br list --status open --not-blocked    # available beads
br claim BEAD-N                        # claim a bead
br close BEAD-N --pr "#N"             # close with PR
br land-plane                          # end-of-session cleanup
```

### Bead Fidelity Audit

The fidelity audit runs automatically as the final step of `/write-code-beads`
before any bead is written to the queue. It cannot be skipped. All beads
from a run are audited together — failures across all beads are reported
before any corrections are made, so the engineer can batch the fixes.

The audit verifies description verbatim, domain constraints complete,
ADRs listed, evals matched, acceptance complete, files correct, interface
contracts listed.

Bead fidelity auditing is available via `/write-code-beads --audit <BEAD-NNN|"all">`.
See `.claude/skills/write-code-beads/SKILL.md` for the full audit checklist.

**Re-running `/write-code-beads` after an IB fix:**

An IB change is a start-over. Delete all beads for this IB and recreate
from scratch — the new IB may produce a different count, scope, or
dependency structure. Do not attempt to preserve or patch existing beads.

```bash
br delete BEAD-NNN BEAD-NNN    # delete ALL beads for this IB
br sync
# Fix the IB, then re-run /write-code-beads
```

**If any bead is `in_progress` or `closed`:** this is a process violation.
The audit must run before coding begins. Stop immediately, do not delete,
escalate to the engineer.

---

## Session discipline

Every commit and push under DekSpec governance binds to a named bead or Intent via a session-lifecycle gate. The gate has two layers — a **primary gate** enforced by local git hooks and a **secondary gate** enforced by an MCP-layer guard module — plus a documented set of **escape hatches** that emit to an append-only audit log. This section covers the full primary-and-secondary-layer story so adopters get the complete picture in one place.

### Primary gate (local git hooks)

The canonical layer. After `dekspec session install-hooks` runs in a consumer repo, `.git/hooks/pre-commit` and `.git/hooks/pre-push` consult `dekspec session status --machine-readable` and reject the operation with a clear error when no session is active. Every commit and push routed through the local `git` CLI passes through this layer.

To open a session before working:

```bash
dekspec session start <bead-id-or-intent-id>
# … edit, commit, push freely while the session is open …
dekspec session end --reason "feature work complete"
```

`dekspec session status` shows the active session at any time. Sessions expire after a TTL (default 4 hours; overridable via `DEKSPEC_SESSION_TTL_HOURS`); a stale session is reported as stale and can be cleared with `dekspec session reap` before opening a new one.

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

The session gate proves *that* work happens under a named session; it does not prove the work belongs to the claimed Intent's scope. The **off-spec drift guardrail** (MSN-009) closes that gap — it makes "vibecoding" (code changes with no in-flight Intent capturing the work) visible at commit time rather than silent.

**Detection model.** The guardrail resolves the active session to its parent Intent, reads that Intent's `Components affected` glob list, and classifies every staged file as in-scope or off-spec by **exact glob match** — a file matches a glob or it does not. There is no fuzzy or adjacent-file tolerance: that would re-introduce the silent-drift gap the guardrail closes.

**`dekspec session vibecoding-check`.** The CLI verb that runs the classification. It reads the staged file set (`git diff --cached --name-only`, or `--files`), classifies it, and exits `0` when every file is in-scope or `3` on off-spec drift. `--machine-readable` emits a stable JSON envelope; `--record` additionally appends an off-spec record to session state.

**Pre-commit off-spec stage.** The `pre-commit` hook template (`templates/git-hooks/pre-commit.template`) gains an off-spec stage that runs *after* the active-session check passes. It invokes `vibecoding-check` and, by default, **blocks** a commit touching files outside the claimed Intent's `Components affected`. The block names the off-spec files and the two ways forward — expand the claimed Intent's `Components affected`, or proceed as recorded vibecoding. If the `vibecoding-check` verb is unavailable (a consumer on a pre-MSN-009 library version) the stage warns and proceeds — it never hard-blocks on its own malfunction.

**`DEKSPEC_VIBECODING=1`.** Setting this env var downgrades the off-spec **block** to a **warning**: `DEKSPEC_VIBECODING=1 git commit ...` proceeds, but the off-spec commit is recorded into session state either way — exploratory off-spec work stays possible as a deliberate, recorded choice rather than a silent one.

**`dekspec session report`.** The read-only end-of-session summary. It reads the session's recorded off-spec commits and prints a per-commit breakdown plus a *ratify-or-revert* prompt — ratify (file an Intent, or expand the claimed Intent's `Components affected`, so the work is captured) or revert. The `/orchestrate-coding-session` skill runs `dekspec session report` at session close so the operator cannot finish a session without seeing what fell off-spec.

The off-spec guardrail activates only when a consumer has installed the hooks (`dekspec session install-hooks`) at a library version that carries the off-spec stage; the library ships the capability inert until then. The library's own `dekspec/` self-spec is exempt by the same policy described next.

### Library-side self-exemption

The DekSpec library's own `dekspec/` self-spec is governed by **Claude Code session-rules** per the library's `CLAUDE.md` (specifically the "DekSpec Guardrails (library-side)" section), **not** by hook-enforced session gating. The library does not install the hooks against itself; the runtime gate is a capability the library *produces* for consumers, not consumes for its own development. Engineers contributing back to the library should not install the hooks against their library checkout — the session-rules pattern is sufficient discipline for the library's own development loop.

### Consumer adoption steps

1. Install or upgrade DekSpec to a version that ships the session gate (≥ v0.44.0 — exact version pinned at MSN-002 close).
2. Run `dekspec session install-hooks` from your repo's git toplevel. The installer writes `.git/hooks/pre-commit` and `.git/hooks/pre-push` templates that consult the CLI's machine-readable status envelope.
3. Wire `tooling/dekspec/mcp_guard.py::guard_commit` and `::guard_push` into your MCP-server config's pre-flight hook for commit/push tool calls. The exact wiring depends on your MCP runtime; the three-call surface is stable.
4. Document the escape hatches (`git commit --no-verify`, `DEKSPEC_BYPASS_SESSION=1`, `DEKSPEC_MCP_GUARD_MODE=warn`) in your team's onboarding doc so engineers know how to bypass when needed and that bypasses are logged for review.
5. (Optional) Set `DEKSPEC_MCP_GUARD_MODE=warn` in your MCP-server env during the initial rollout window to log-only without blocking; flip to reject (unset, or `=reject`) once the team has internalized the workflow.

The `/orchestrate-coding-session` skill automatically opens and closes a session around its dispatch loop, so engineers running the skill against a bead never need to touch `dekspec session start/end` manually — see `skills/orchestrate-coding-session/SKILL.md` §Session Lifecycle Wiring.

---

## Coding Session Protocol

A coding session is orchestrated by `/orchestrate-coding-session`, which dispatches sub-agents in isolated git worktrees for parallel execution. The engineer monitors from the orchestrator session.

### Phase 1 — Discover & Claim

The orchestrator runs `br ready --json` to find unblocked beads, then for each candidate: verifies it is unclaimed, reserves its target files via `file_reservation_paths` (agent-mail MCP) with `exclusive=true`, and claims it with `br update <id> --claim`. File conflicts cause a bead to be skipped, not blocked. The result is a dispatch plan showing which beads will execute.

### Phase 2 — Dispatch (Parallel Worktrees)

Before dispatch, the orchestrator verifies dependency merges are present — if a bead depends on another bead from the same session, that worktree branch is merged first. Then all independent beads are launched as sub-agents in a **single message**, each with `isolation: "worktree"`.

Each sub-agent receives the full bead JSON, eval files, pre-written test files, and checklists. The sub-agent does NOT read the IB, ADRs, interface contracts, or the Working Spec — all relevant decisions were reconciled into the bead's Constraints and Decisions at generation time by `/write-code-beads`. The bead is the sole authority during construction; the IB is upstream source material that has already been distilled into the bead.

**Sub-agent workflow:**

1. **Interface-first (mandatory):** Write public interface signatures only — no implementation
2. Implement the interfaces
3. **Tests:** If pre-written tests exist, remove `@pytest.mark.skip` markers and run them. Then write additional tests for discovered behaviors. If no pre-written tests, write tests for all deterministic behavior.
4. Run evals if they exist
5. Run `ubs` on all changed files
6. Commit: `bead [ID]: [title]`

**Interrupt-level stop patterns** (trigger at any point):

```
EXPERTISE GAP — Bead: [ID] | Need: [question] | Blocks: [what]
STOPPED — awaiting engineer decision

CONFLICT — [describe the contradiction]. Cannot resolve from bead/IB alone.
STOPPED — awaiting engineer decision

DEPENDENCY MISSING — Bead: [ID] | Missing: [what] | Blocks: [what]
STOPPED — awaiting orchestrator resolution
```

### Phase 3 — Collect & Merge

As each sub-agent returns, the orchestrator merges its worktree branch. Conflicts in files not touched by other beads auto-resolve by accepting incoming changes. Conflicts in shared files are surfaced to the engineer.

### Phase 4 — Land the Plane

1. Close completed beads, release file reservations
2. Move completed IBs from `active/` to `completed/`
3. Unclaim stopped/conflict beads, file follow-up beads for blockers
4. Run the full test suite — compare against the pre-session commit to detect regressions
5. File follow-up beads for out-of-scope discoveries
6. Run `br sync`
7. Present merged diff for engineer review

### Phase 5 — Check for Newly Unblocked Work

Run `br ready` again. If beads that were blocked by just-closed beads are now available, offer another dispatch round. If the engineer declines, SESSION COMPLETE.

### Directive Library

```
"That's not in the spec. Remove it."
"Stop. That file is outside this bead's scope."
"Show me the test for [condition] before continuing."
"You deviated from the IB's Constraints & Decisions. Refactor."
"Which CUDA device does this code run on? State it explicitly."
"Interface signatures don't match the spec. Rewrite them first."
"Evals were not written for this bead. Stop — invoke the Eval Agent first."
"What is the dtype of this tensor? State it explicitly before continuing."
"Does this write go to shadow or Neo4j directly? State it explicitly."
"That dtype promotion is not in the IB. Surface it before continuing."
"Stop. That touches the shadow graph write path. The flush behavior is not in your IB."
"Which topic level does this boundary detect — macro, sub, or micro? State it explicitly."
"What quantization tier does this item land in? Trace the relevance score to the tier threshold."
"Stop. That touches the shadow timeline write path. The flush behavior is not in your IB."
"Does this decay score reflect current time or capture time? State it explicitly."
```

---

## Repository Structure

```
CLAUDE.md                        ← Claude Code: skills map, global rules
AGENTS.md                        ← Tool-agnostic: session protocol, bead commands
.claude/skills/                  ← registered Claude Code skills (invocable via /name)
dekspec/
  adr-index.md                   ← ADR index, escalation rule, backlog
  working-spec-index.md          ← Working Spec index
  interface-contract-index.md    ← Interface Contract index
  architecture-elements-index.md ← Architecture Elements index (replaces design-notes-index.md)
  system-vision.md               ← Layer 1: system vision (singular, top-level)
  domain-glossary.md             ← Layer 1: canonical domain terminology
  guidance-and-corrections.md    ← corrections backlog (promoted to glossary over time)
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
  impl-briefs/                   ← Layer 3: implementation briefs
    queued/                      ← ready to start
    active/                      ← in session
    completed/                   ← archived after merge
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
    archaeology/                 ← (legacy) historical directory for retired /do-code-archaeology skill output; new brownfield work uses /dekspec:archeology which writes no parallel artifact tree
    todos/                       ← quality reports, open-areas assessments
tests/
  unit/                          ← deterministic unit tests (written by coding agent)
  bead/                          ← ephemeral TDD tests (cleaned at merge to main)
  contracts/                     ← auto-generated from spec constraint tables (permanent)
  properties/                    ← hypothesis property-based tests (permanent)
  regression/                    ← promoted from bead tests with provenance (permanent)
  integration/                   ← per-IB cross-bead composition (permanent)
  evals/                         ← probabilistic AI behavioral evals (written by Eval Agent)
    behavioral/                  ← model output vs. known-good baselines
    regression/                  ← run on every PR touching model/graph/quant
    adversarial/                 ← empty moment stack, Q4-only, flush failure
.beads/beads.jsonl               ← bead queue
```

### Library-side layout (`Dektora/dekspec` repo itself)

The diagram above describes a **consumer repo** post-vendoring — what an engineer at Dektora or DekFactory sees after `bash scripts/install-dekspec.sh`. The library's own source tree has a different shape because it *produces* the vendored content rather than receiving it:

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
    migrations/                     ← lazy migration registry (today empty)
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
    install-dekspec.sh              ← the vendoring script consumers invoke
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
  .beads/                           ← upstream bead tracker
```

The **library self-spec under `dekspec/`** is the library's eat-own-cooking gate (ADR-007 + ds-i3g). It is audited on every PR by the `Self-dogfood — dekspec doctor` step in `.github/workflows/ci.yml`; any new audit rule must pass against this corpus before reaching consumers.

---

## Filename Conventions

DekSpec follows two simple rules for filenames inside the `dekspec/` content tree:

1. **Artifact files use the label-NNN format with the LABEL UPPERCASE.** Everything else in the filename is lowercase + hyphenated. Examples: `ADR-022-configurable-scoring-formulas.md`, `AE-014-configurable-formula-engine.md`, `WS-016-scoring-formulas.md`, `IC-007-formula-engine-evaluation.md`, `IB-003-se-embedding-tokens.md`, `MSN-002-attachment-mime-coverage.md`, `MSN-001-se-container-build.md`, `CR-001-cascade-tier-rebalance.md`, `DIV-001-skips-wireups.md`. The artifact-label prefixes are: `ADR`, `AE`, `WS`, `IC`, `IB`, `INT`, `MSN`, `CR`, `DIV`.

2. **All other files inside `dekspec/` are lowercase + hyphenated.** Index files, methodology docs, supporting docs, vendored templates, workspace notes — all lowercase. Examples: `adr-index.md`, `working-spec-index.md`, `architecture-elements-index.md`, `intent-index.md`, `mission-index.md`, `dekspec-operating-guide.md`, `dekspec-quick-reference.md`, `architecture-frameworks-reference.md`, `architecture.md`, `domain-glossary.md`, `system-vision.md`, `project-context.md`, `guidance-and-corrections.md`, `ecosystem-tools.md`, `closeout-audit-v2-2026-05-09.md`, `dn-to-ae-reference-map-2026-04-27.csv`.

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

*DekSpec runs three orthogonal coordination mechanisms over the spec graph. They serve different workflow patterns; do not retire any of them assuming the others cover its case. See INT-086 (multi-user-coordination-analysis) for the full analysis.*

### The three layers

| Layer | Mechanism | Solves | Workflow pattern |
|---|---|---|---|
| Mechanical (intra-MR) | **INT-020** — DRAFT-slug temp IDs + `dekspec id allocate` + append-only `dekspec/registry.yaml` + `L-NO-DRAFT-IN-MAIN` (P0) + `L-REGISTRY-APPEND-ONLY` (P1) | Two engineers each grep the index for next-free `<KIND>-NNN`, both pick the same number, collide at merge time. | "This Intent ships in this MR; defer canonical-ID allocation to commit time." |
| Cross-MR exploratory | **MSN-014** — `dekspec/provisional/<incubation-slug>/` + `<KIND>-provisional-<slug>` ID convention + `dekspec library new-provisional` (scaffold + git branch) + hand-promote workflow (renumber + `git mv` — see §Provisional Promotion) + `replaces:` frontmatter for REPLACE mode + L-PROVISIONAL-* / L-COW-SIBLING-COLLISION / T-COW-CANONICAL-EDITED audit rules | A non-trivial change that may span many commits, may be abandoned, and shouldn't pollute the LOCKED spec graph during exploration. | "Author the family under `dekspec/provisional/<slug>/`; hand-promote when the originating Intent matures toward ACCEPTED." |
| Semantic (cross-engineer) | **MSN-010** (TODO) — divergence detection, contradiction warnings at PROPOSED, system-vision drift advisories, engineer attribution, dependency-cycle detection, coherence health, deconfliction workflow | Two engineers ship Intents that each validate individually but collectively contradict each other or the system vision. | "After this Mission lands, semantic conflicts surface at session-start, at PROPOSED time, at LOCK time, and on a periodic sweep." |

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
- `dekspec aggregate agents-md [--at PATH] [--output PATH]` — rebuilds `AGENTS.md` from LOCKED+ACCEPTED artifacts.

Engineers run these pre-commit or post-merge; CI hook integration is the open piece of MSN-015.

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

- **CLI:** `dekspec library new-provisional <KIND> <slug>` — KIND ∈ {INT, MSN, ADR, AE, IC, WS, IB, SP}. Writes a skeleton at `dekspec/provisional/<slug>/<KIND>-provisional-<slug>.md` with the canonical template body, a `> **PROVISIONAL.**` banner, and a Status of `TODO` (Mission scaffolds use `TODO` per Mission template). On first artifact in the folder the verb creates a working-tree branch — `int/INT-...`, `mission/MSN-...`, or `feat/<slug>` for the others — unless `--no-branch` is passed.
- **Skill:** `/dekspec:write-<kind> --provisional <slug>` — same destination, same banner. Runs the full authoring flow (expertise audits, coverage analysis, etc.) but skips passes that require linkage-walker visibility. `--lock` is rejected in provisional mode; `--review` and `--analyze` are permitted.

Five skills carve out: `/write-constitution`, `/write-sv`, `/write-ggc` (singletons) and `/write-evals`, `/write-tests` (operate on existing beads). They do not accept `--provisional`.

### Step 2 — Copy-on-write (CoW) staging

When the incubation must **modify** an existing canonical artifact (rather than add a new one), stage a copy first:

```bash
dekspec library cow-stage dekspec/architecture-elements/AE-006-skills-library.md \
  --incubation provisional-artifact-incubation
```

The verb copies the canonical file into the incubation folder, stamps `replaces: AE-006` in the frontmatter, and is idempotent — re-running it on an already-staged file is a no-op. Singletons (Constitution, System Vision, Glossary) use a path-as-id form: `replaces: constitution`, `replaces: system-vision`, `replaces: domain-glossary`.

Two audit rules patrol this surface:

- `L-COW-SIBLING-COLLISION` (P2) — two distinct incubations both claim the same canonical path. Resolution: one incubation merges into the other or one is killed before the other promotes.
- `T-COW-CANONICAL-EDITED` (P2) — a CoW-staged canonical was *also* edited on the working branch. Resolution: drop the working-branch edit and re-stage, or drop the CoW copy and accept the working-branch edit as canonical.

### Step 3 — Edit + iterate

Engineers edit provisional artifacts using the same `/write-<kind>` skills that author canonical artifacts. Authoring passes, `--review`, `--analyze`, and `--unlock` (no-op in provisional, prints a warning) all work. `--lock` rejects with a clear error — provisional artifacts cannot be LOCKED. Status transitions inside provisional follow the canonical lifecycle (TODO → DRAFT → PROPOSED → ACCEPTED) but the ACCEPTED transition does **not** trigger promotion automatically — see Step 4.

The advisory rule `L-PROVISIONAL-STALE` (P3) fires on incubation folders whose newest file is older than 30 days (mtime; engineers `touch` to reset). The rule is intentionally lenient — incubations can sit for a quarter — but flags abandoned exploration so the tree doesn't accumulate cruft.

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
6. Validate via `dekspec doctor --at .` and reconcile any new findings; run `dekspec regen-indexes` (or rely on the post-merge hook) to refresh derived index files. The originating Intent's lifecycle then continues from `ACCEPTED` → `IMPLEMENTING` → … → `LOCKED` per the standard flow.

**The accept-gate.** Hand-promote when (and only when) every artifact in the incubation has reached Status `ACCEPTED`. The gate is the explicit acknowledgement that the engineer is converting exploration into commitment: provisional artifacts are abandonable; canonical artifacts carry forward into LOCKED state and become consumer-visible.

> **CLI verb retired 2026-05-25.** The previous `dekspec repo promote-provisional <slug>` CLI verb was retired (per F2 audit; zero invocations in repo history — every promotion was hand-promote). Invoking it now returns a non-zero exit with a pointer to this section. Provisional folders themselves are **not** retired — `dekspec/provisional/`, the `dekspec library new-provisional` scaffold verb, the `dekspec library cow-stage` staging verb, the `replaces:` frontmatter convention, and the `L-PROVISIONAL-*` / `L-COW-*` / `T-COW-*` audit rules all remain canonical. The underlying Python helpers (`dekspec.promote.plan_promotion` / `apply_promotion` / `render_plan`) are also preserved for tooling that needs to drive the renumber programmatically.

---

## *Putting It All Together*

*Here is what using this workflow actually looks like, from the first idea through a coding session running against a live bead queue.*

---

### *The Idea*

*The team wants to replace the JSON tensor serialization between the embedding process and the chat model process with a binary format. The current approach is acknowledged as inefficient and has unquantified precision loss. Nobody has measured either.*

### */write-adr*

*The engineer invokes `/write-adr`. The skill runs the escalation check — tensor serialization format is on the Dektora always-a-full-ADR list, so this goes straight to a full ADR. The Writer drafts ADR-001 from the engineer's description of the decision and the options considered: JSON (current), msgpack, and shared memory. The engineer reviews, corrects the rationale for why shared memory was ruled out (CUDA process isolation makes it unreliable across OS processes), and accepts it. ADR-001 is filed.*

### */write-ws — Writer Draft*

*Now the engineer invokes `/write-ws`. The skill asks for a description of the component. The engineer describes the IPC serialization layer — what it does, what it doesn't do, the interface between the two processes, the error conditions, and the failure behavior if the receiving process is unavailable. The Writer produces a first draft.*

### */write-ws — Expertise Audit and Role Passes*

*The expertise audit runs. This spec touches tensor serialization round-trips, so the Quantization / Precision Expert pass is queued. It also touches process isolation at the IPC boundary, so the CUDA Multi-Process Expert pass is queued. The ML Expert, Graph Expert, Embedding Geometer, and Pipeline Analyst are not triggered — this spec doesn't touch those domains.*

*The Quantization Expert reads the draft and immediately flags something: the spec states the serialization format must preserve tensor values but doesn't specify what precision loss is acceptable or how it will be verified. It also notes that the spec doesn't address the dtype promotion that occurs when bfloat16 is cast to float32 before serialization — a one-way loss that must be acknowledged. The engineer updates the spec with a precision threshold and adds a round-trip fidelity requirement to the eval hooks.*

*The CUDA Multi-Process Expert reads the updated spec and flags that the spec doesn't address what happens if the receiving process is mid-inference when the serialized tensor arrives. The engineer updates the failure behavior section.*

### */write-ws — Options Architect*

*The Options Architect runs — IPC format selection is a genuine architectural alternative domain. It surfaces one additional option the team hadn't considered: a file-based ring buffer. The engineer evaluates it and decides it introduces operational complexity that outweighs the benefit. That reasoning goes into ADR-001 (still in PROPOSED status at this point) as a late addition under Options Considered.*

### */write-ws — Critic*

*The Critic runs on the full spec. It finds two gaps: the spec doesn't state who is responsible for schema versioning if the tensor format changes, and the eval hooks don't specify what "round-trip fidelity" means as a measurable criterion. Both get resolved. The Critic runs a second pass on the changed sections and finds nothing material. The spec is accepted.*

### */write-ibs*

*The engineer invokes `/write-ibs`. The Planning Agent reads the spec and ADR-001, then produces two Implementation Briefs. IB-1 implements the binary serialization library and the core round-trip logic. IB-2 integrates it at each call site — one per service process. IB-1 is foundational; IB-2 depends on it technically. No production gate is needed between them — this is a pure technical dependency, and the round-trip fidelity evals cover the correctness concern. The engineer reviews both IBs, confirms the domain constraints are complete (tensor dtype explicit, CUDA device stated, precision threshold carried from the spec), and approves.*

### */write-code-beads*

*The engineer invokes `/write-code-beads` for each IB. IB-1 produces BEAD-001 and BEAD-002 — one for the serialization core, one for the deserialization and reconstruction logic. IB-2 produces BEAD-003 and BEAD-004 — one per call site integration. BEAD-003 and BEAD-004 both carry `depends_on: ["BEAD-002"]` and can run in parallel once BEAD-002 closes. The fidelity audit runs automatically — all four beads pass. The Eval Agent is not invoked here because IPC serialization round-trip fidelity is deterministic — the coding agent will write those tests during the session.*

### */orchestrate-coding-session*

*The engineer invokes `/orchestrate-coding-session`. The orchestrator runs `br ready --json`, discovers BEAD-001 is the only unblocked bead (BEAD-002 depends on it, and BEAD-003/004 depend on BEAD-002), acquires exclusive file reservations via agent-mail, and claims it. The dispatch plan shows one bead. The orchestrator launches a sub-agent in an isolated worktree.*

*The sub-agent reads the bead — the bead is the sole authority during construction. It does not read the IB, ADRs, interface contracts, or the Working Spec (all decisions from those sources were reconciled into the bead's Constraints and Decisions at generation time). Before writing a single line of implementation, it produces the public interface signatures for the serialization module — function signatures, return types, and error types only. The engineer reviews them against the IB's Constraints & Decisions. One signature is wrong: it accepts any tensor dtype rather than enforcing bfloat16 at the boundary. The agent corrects it before implementation begins.*

*The agent hits one expertise gap during implementation — the IB specifies msgpack but doesn't state which msgpack library to use or how to handle numpy array serialization within it. The agent stops and surfaces the gap rather than choosing. The engineer specifies the library and the numpy handling pattern. The agent continues. BEAD-001 closes with all tests passing, including round-trip fidelity at all five bit depths.*

*The orchestrator merges the worktree branch, closes the bead, and runs `br ready` again. BEAD-002 is now unblocked. Another dispatch round launches it. After BEAD-002 closes, both BEAD-003 and BEAD-004 become unblocked simultaneously. The orchestrator dispatches both as parallel sub-agents in separate worktrees — a single message with two `isolation: "worktree"` launches. Both agents work simultaneously on their respective call site integrations. Both close within the same round.*

*The full binary IPC implementation is done — spec-grounded, test-verified, and traceable back through the IBs, the Working Spec, and ADR-001.*

## Post-mortem ritual (INT-126 / ds-99ko)

> Per **INT-126** (LOCKED 2026-05-30) the `dekspec audit failure-classes` CLI verb surfaces aggregate trends in failure-tagged beads. Coupled with INT-125's Constitution §Class Lanes (LOCKED), the post-mortem ritual is evidence-driven without ceremony.

The ritual is five steps. No new skill — uses existing tools (`br`, `dekspec audit`, `/dekspec:write-constitution`):

1. **Engineer sees revert** — CI flips red after a merge, `git revert` lands, or `dekspec doctor` flags a regression.
2. **Engineer tags the responsible bead** with a `failure-class:<class>` label + notes:
   ```bash
   br update <bead-id> --labels failure-class:flaky-test --notes "MockedTimeService raced under parallel pytest -n auto"
   ```
   The class name is operator-chosen vocabulary (e.g. `flaky-test`, `wrong-mock`, `scope-creep`, `missing-rollback`, `unbounded-retry`). Keep names short and dictionary-able.
3. **Engineer runs the aggregator** to see whether the class is a one-off or a pattern:
   ```bash
   dekspec audit failure-classes --window 90 --by class --format md
   dekspec audit failure-classes --window 90 --by risk-tier --format md   # cross-cut by class-lane risk_tier
   dekspec audit failure-classes --by type --format json | jq             # programmatic consumers
   ```
   The verb is read-only and walks `.beads/issues.jsonl`. Groups beads carrying the `failure-class:*` label, sorts descending by count, and cross-references each bead's `external_ref` so the operator can trace bead → Intent → IB → revert SHA.
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
- `scope-creep` — bead/IB landed changes outside its declared file globs.
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

The B-axis (Behavior rules) and the broader P-axis (Policy rules beyond P-citation) are documented placeholders. Specific rules are authored case-by-case as the rule families mature; today the loop respects whichever rules the audit profile (v1, team, lite) declares.

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
- The Mission is `Convert-from-OVERSIZED` — promoting an existing OVERSIZED Intent into a Mission with N child Intents that already have draft bodies.
- An Intent that decomposes into beads against this Mission already exists and the Mission is missing only because the operator forgot to author it earlier.

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
- The §Provisional Promotion Gate in `/dekspec:write-mission` Activate Mode detects incubation folders and prompts explicit operator confirmation before walking TODO → ACTIVE.
- The hand-promote workflow (renumber + `git mv`) is canonical (the original `dekspec promote-provisional` CLI verb was retired 2026-05-25; see §Provisional Promotion below for the recipe).

### Creation-Mode routing (INT-128 ask→route → ADR-030 hard default)

INT-128 originally added an interactive §1a.0 commitment prompt to `/dekspec:write-mission` Creation Mode ("Will the First Intent's body be authored within this same session? yes → canonical, no → provisional"). **ADR-030 (INT-133) superseded that live prompt with a deterministic hard default** and extended the posture to `/dekspec:write-intent` as well:

> Creation Mode defaults to **provisional**. No prompt is asked. Canonical-direct authoring requires the explicit **`--canonical`** opt-out. Both skills resolve the target via the `dekspec library author-target --kind <K> [--canonical]` verb.

The operator no longer needs to answer a per-run question or know the `--provisional` flag — provisional is simply the default, and `--canonical` is the one token to remember when a same-session canonical landing is intended. INT-128's motivation (the MSN-011 eradication cost, above) is now encoded in the default posture rather than a prompt.

### Audit backstop: T-MISSION-CANONICAL-WITHOUT-CHILD (advisory P3)

The `T-MISSION-CANONICAL-WITHOUT-CHILD` audit rule (INT-128, registered in `v1.yaml`) fires when:

- A Mission file lives under canonical `dekspec/missions/` (not `dekspec/provisional/`).
- Status is `TODO`.
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
