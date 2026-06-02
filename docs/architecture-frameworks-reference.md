# Architecture Frameworks Reference (arc42 + C4)

> **Permanent reference for the arc42 / C4 framework concepts that DekSpec borrows from.**
> Extracted from the DN→AE conversion guide (`docs/workspace/dekspec/dn-to-ae-conversion-guide-2026-04-27.md` §arc42 lexicon + §C4 lexicon + §combined interpretation) to survive the conversion guide's working-document lifecycle.
>
> **Read this when:** authoring a new Architecture Element (AE) and the subtype is non-obvious; deciding whether content belongs in an AE vs. ADR vs. WS vs. IC vs. IB; choosing a C4 view type for a diagram inside an AE.
>
> **Source frameworks:**
> - **arc42** — `https://arc42.org` — a documentation-structure standard separating goals, decisions, and quality requirements.
> - **C4 model** — `https://c4model.com` — a hierarchy of architecture views (Context, Container, Component, Code) plus supporting diagrams (Dynamic, Deployment).

## Synthesis statement

DekSpec's relationship to these two frameworks is layered:

- **arc42** provides the *drawer logic* for what kind of architecture information is being expressed (goals, constraints, structure, runtime, deployment, decisions, quality). DekSpec's writing skills internalize this so authors don't need to know arc42 directly.
- **C4** provides the *view vocabulary* for diagrams placed *inside* AEs (Context, Container, Component, Dynamic, Deployment).
- **DekSpec's AE subtype enum** is the *artifact taxonomy* — it borrows naming from C4's structural hierarchy (System / Container / Component) but adds breadth-categories that neither framework formalizes (Pipeline, Data Model, Cross-Cutting Concern, Platform Concern, Interface Surface, Workflow / Process). Subsystem is retained as a DekSpec convenience for *logical groupings of multiple Containers* above the strict C4 hierarchy.

Neither framework is normative for DekSpec on its own. DekSpec routes the framework concepts through its own enum and its own skills.

## Compact mapping (arc42 ↔ C4 ↔ DekSpec)

| DekSpec artifact | Role | arc42 fit | C4 fit |
|---|---|---|---|
| **AE** | Describe a slice | Building blocks (5), runtime (6), context (3), deployment (7), cross-cutting concepts (8) | Subtypes System / Subsystem / Container / Component align with C4; views Context / Container / Component / Dynamic / Deployment placed inside AE |
| **ADR** | Decision record | Architecture decisions (9) | None |
| **WS** | Measurable constraints | Quality requirements (10), constraints (2) | None |
| **IC** | Interface promise | Interface / interaction edges | Context / Component flows |
| **IB** | Implementation plan | Downstream from architecture description | None |

(Numbers in parentheses refer to arc42 chapter numbers; see lexicon below.)

---

## arc42 lexicon — chapter-by-chapter mapping into DekSpec

arc42 defines a standard documentation structure with 10 chapters. DekSpec's writing skills internalize these as conceptual drawers used to classify incoming content into the correct artifact family.

### 1. Introduction and Goals

**arc42 purpose:** capture business goals, functional expectations, quality goals, stakeholders.

**DekSpec routing:**
- Top-level system identity → **System Vision** (singular)
- Top-3-to-5 quality *goals* (named, not measured) → AE context section or System Vision
- Detailed measurable quality *requirements* → **WS**

### 2. Constraints

**arc42 purpose:** restrictions limiting design freedom (technology, regulatory, organizational, environmental).

**DekSpec routing:**
- Measurable / enforceable constraints → **WS**
- Explanatory mention of constraints → AE prose or ADR (where the constraint shaped a decision)
- Reasoning about why a constraint forced a particular choice → **ADR**

### 3. Context and Scope

**arc42 purpose:** describe external interfaces, neighboring systems, users, the boundary between system and environment.

**DekSpec routing:**
- Boundary, context, relationships → **AE** sections (Boundaries and Non-Goals; Relationships and Dependencies)
- Often visualized with **C4 Context view**
- Detailed external promises → **IC**

### 4. Solution Strategy

**arc42 purpose:** key strategic design approaches that respond to goals, context, and constraints.

**DekSpec routing:**
- High-level strategy summary → **AE** (in Purpose / Constraints sections) or System Vision
- Significant strategy choices and tradeoffs → **ADR**
- Should not silently absorb detailed quality requirements (those go to WS) or plans (those go to IB)

### 5. Building Block View

**arc42 purpose:** static decomposition of the system into major parts and their relationships.

**DekSpec routing:**
- Strongest influence on **AE subtype** assignment. Subtypes that draw from this drawer: System, Subsystem, Container, Component, Pipeline, Data Model.
- Often visualized with **C4 Container** and **C4 Component** views.

### 6. Runtime View

**arc42 purpose:** architecturally relevant runtime behavior and interactions through selected scenarios.

**DekSpec routing:**
- AE Runtime Behavior section
- Often visualized with **C4 Dynamic view**
- Test for inclusion: *architectural relevance*, not exhaustive scenario coverage. Pick a few representative flows (ingestion, retrieval, failure handling, startup, cutover).

### 7. Deployment View

**arc42 purpose:** how software is mapped onto infrastructure and execution environments.

**DekSpec routing:**
- AE Deployment / Operational Shape section
- AEs of subtype **Platform Concern** typically center this content
- Often visualized with **C4 Deployment view**

### 8. Crosscutting Concepts

**arc42 purpose:** concerns that apply across multiple building blocks (security, observability, error handling, consistency, caching, configuration, tenancy).

**DekSpec routing:**
- AEs of subtype **Cross-Cutting Concern** or **Platform Concern**
- Measurable requirements related to these concepts still go to **WS**
- Major adoption / tradeoff choices for the concept → **ADR**

### 9. Architectural Decisions

**arc42 purpose:** important architecture decisions, visible and traceable.

**DekSpec routing:**
- Maps directly to **ADR**
- AEs may summarize *local implications* of a decision but the decision record itself is an ADR
- If incoming text is dominated by rationale / alternatives / consequences, route away from AE into ADR

### 10. Quality Requirements

**arc42 purpose:** quality trees, quality scenarios, detailed quality expectations.

**DekSpec routing:**
- Maps directly to **WS** (especially quality-flavored Working Specs)
- Top-level quality *goals* may be reflected in the System Vision or AE context, but detailed *measurable* quality requirements go to WS
- If incoming text is dominated by measurable quality language (SLOs, latencies, throughput, retention, auditability), route away from AE into WS

### Summary of arc42 routing in DekSpec

- **System Vision / AE context** absorbs much of arc42 chapter 1.
- **WS** absorbs much of arc42 chapter 2 (when constraints are enforceable) and chapter 10 (quality requirements).
- **AE** absorbs much of arc42 chapters 3, 5, 6, 7, and 8 in an AE-shaped local form.
- **ADR** absorbs chapter 9.
- **IC** refines boundary promises surfaced in context / decomposition views.
- **IB** is execution-facing, sitting downstream of arc42 rather than mapping to a specific arc42 chapter.

---

## C4 lexicon — abstractions and diagram types

The C4 model defines a hierarchical set of architectural abstractions plus a set of diagram view types. C4 is **notation-independent** and **tooling-independent**.

In DekSpec, C4 is **the diagram vocabulary used inside AEs** — not the artifact taxonomy itself.

### C4 abstraction levels

#### Software System

The highest-level abstraction. The system under discussion as a whole.

**DekSpec mapping:** AE with subtype **System**. Often appears in Context views and system-landscape discussions.

#### Container

An application or data store that executes code or stores data. Web app, API service, database, message broker, serverless function boundary. Has its own runtime, deployment, possibly its own internal architecture.

**DekSpec mapping:** AE with subtype **Container**. This is the canonical AE subtype for a single deployable unit. Subsystem AEs may aggregate multiple Containers as a logical grouping.

#### Component

A grouping of related functionality inside a Container, separately understandable at the code-structure level without dropping to class-by-class detail.

**DekSpec mapping:** AE with subtype **Component**. Components do not deploy independently — their Container does.

#### Code

Classes, modules, implementation-level structures. The lowest C4 abstraction.

**DekSpec mapping:** Generally not modeled at the AE level. Code-level structure belongs in implementation, not architecture description, unless a repository explicitly wants code-level architecture views.

### C4 diagram (view) types

#### Context diagram

Shows the system in its environment — users, neighboring systems, major external relationships.

**Use in AEs:** AE Boundaries / Context sections, especially for AEs of subtype **System**, **Subsystem**, **Interface Surface**, or cross-boundary concerns. Don't overload with low-level internals.

#### Container diagram

Shows the major deployable / runnable parts of a system and how they interact.

**Use in AEs:** AE Decomposition at service / application / store level. Useful for AEs describing systems, subsystems, platforms, or cross-Container pipelines.

#### Component diagram

Shows the main internal components within a Container and their relationships.

**Use in AEs:** When an AE needs more internal structural clarity than a Container diagram can provide. Use selectively, not by default.

#### Dynamic diagram

Shows architecturally significant runtime interactions for a specific scenario.

**Use in AEs:** AE Runtime Behavior section. Pick architecturally significant flows (ingestion, retrieval, failure handling, startup, cutover). A few representative scenarios are better than exhaustive flow coverage.

#### Deployment diagram

Shows how Software-System / Container instances are deployed onto infrastructure within a given environment.

**Use in AEs:** AE Deployment / Operational Shape section. Identify the environment (production / staging / dev) or explicitly mark as environment-agnostic.

### Optional / supporting C4 views

C4 acknowledges supporting views such as the System Landscape view (multiple Software Systems together). Useful at repo / portfolio level; secondary to Context / Container / Component / Dynamic / Deployment for AE work.

### C4 usage rules in DekSpec

- Use C4 diagrams only when they materially clarify an AE.
- Prefer multiple simple diagrams over one overloaded diagram.
- Align diagram labels with AE / ADR / WS / IC terminology so the spec graph is traceable.
- Dynamic diagrams illustrate architecturally relevant flows — not exhaustive business workflows.
- Deployment diagrams reflect a specific environment or clearly identify if environment-agnostic.
- Context diagrams emphasize boundaries and external relationships, not internals.

### Diagram syntax policy

C4 is notation-independent. DekSpec recommends:

- **Mermaid** for inline lightweight authoring (the default).
- **Structurizr DSL** when the architecture model becomes large enough that consistency, reuse, and generated views materially matter.

---

## Practical reading test (which artifact does this content belong in?)

A one-glance routing rule used by humans and embedded in writing skills:

| Question | Answer |
|---|---|
| *What is the thing?* | **AE** (description of an architectural slice) |
| *Why did we choose this?* | **ADR** (decision rationale) |
| *What must be true?* | **WS** (measurable requirement) |
| *What is the boundary promise?* | **IC** (cross-component contract) |
| *How do we execute the change?* | **IB** (implementation plan) |

## Routing keyword tables (used by the writing skills' classifier)

When the engineer offers content that mixes concerns, the writing skills route material to the right artifact family by matching keyword patterns. These tables are reproduced below for reference; the canonical home for the routing logic is the relevant skill's `SKILL.md`.

### Route to AE when content is dominated by

- Nouns and phrases describing system slices, services, components, responsibilities, boundaries, dependencies, topology, workflows, or interactions.
- Requests to *describe* what a subsystem is or how it fits into the larger system.
- Requests for architectural views or structural descriptions.

### Route to ADR when content is dominated by

- Phrases such as "we chose", "we decided", "instead of", "tradeoff", "because", "consequence", "alternative".
- Comparative reasoning between options.
- Explicit design-choice narratives.

### Route to WS when content is dominated by

- Phrases such as "must", "shall", "target", "p95", "availability", "throughput", "retention", "auditability", "SLO", "SLA", "latency".
- Acceptance criteria and measurable thresholds.
- Statements that can be validated by tests, monitoring, audits, or benchmarks.

### Route to IC when content is dominated by

- Endpoints, payloads, request/response semantics, compatibility rules, schema promises, provider/consumer concerns, contract guarantees.

### Route to IB when content is dominated by

- Rollout plans, migration steps, sequencing, tasks, work packages, implementation approaches, cutover planning.

---

## Cross-references

- AE subtype enum + brief definitions: `dekspec-operating-guide.md` §Architecture Elements
- AE / DN glossary entries: `domain-glossary.md` §DekSpec Artifacts (Layer 1)
- AE skill (creates AEs, classifies and routes content): `.claude/skills/write-ae/SKILL.md` (Phase 3 work)
- ADR / WS / IC / IB skills: respective `SKILL.md` files
- Source frameworks:
  - arc42: `https://arc42.org` — full template, detailed chapter explanations, multi-language editions.
  - C4 model: `https://c4model.com` — abstraction definitions, view-type reference, notation guidance.

## Lifecycle

This document is a **permanent reference**. It does not move into `_archive/` at migration close-out. Updates flow from:

1. Changes to the AE subtype enum (require Architecture Element design owner approval).
2. Changes to the DekSpec routing rules (require coordination with the writing skills).
3. Updates to upstream arc42 / C4 specifications (the document describes DekSpec's *interpretation*, not the upstream specs themselves; upstream changes are reflected only when DekSpec adopts them).
