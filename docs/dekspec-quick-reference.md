# DekSpec — Quick Reference

**Read time: 5-10 minutes.** Full guide: `dekspec/dekspec-operating-guide.md`

---

## The Problem This Solves

AI coding agents fill ambiguity with confident, plausible, wrong decisions. By review time the wrong assumption is load-bearing. **The solution: eliminate ambiguity before the agent starts.** Specs are the mechanism. Beads are the persistent task memory.

**The engineer's role:** provide domain knowledge, make decisions, approve work. AI drafts, critiques, and codes.

---

## Four Layers

| Layer | What | Artifacts | Skills |
|---|---|---|---|
| **L1 Design** | Vision, principles, decisions | System Vision, Architecture Elements (AE), ADRs, Domain Glossary | `/write-ae`, `/write-adr`, `/dekspec:archeology` |
| **L2 Specification** | Behavioral contracts | Working Specs (WS), Interface Contracts (IC) | `/write-ws`, `/write-ic` |
| **L3 Implementation** | Decomposed work plans | Implementation Briefs (IB) | `/write-ibs` |
| **L4 Construction** | Atomic coding tasks | Beads, Tests, Evals | `/write-code-beads`, `/write-tests`, `/write-evals`, `/exec-coding-session` |

**Intent (`INT-NNN`) and Mission (`MSN-NNN`) anchor at L1 and span downward through L2-L4.** They link to L1 AEs, spawn L3 IBs, may revise L2 WSs / ICs, and carry L4-surface `verification` / `rollback` / `kill_criteria` commands. The operating guide covers their audit rule classes (L7a / L7b / L8 / L9).

**Hierarchy:** L1 governs L2 governs L3 governs L4. Conflicts resolve upward. Within L1, contradictions are consistency bugs — fix them, don't pick a winner. L1 artifacts are the source of truth (System Vision for scope, Architecture Elements for descriptive slices, ADRs for decisions, Domain Glossary for terminology); L2-L4 derive from L1 plus engineer expertise.

**Practical reading test** (which artifact does this content belong in?):
- *"What is the thing?"* → **AE** · *"Why did we choose this?"* → **ADR**
- *"What must be true?"* → **WS** · *"What is the boundary promise?"* → **IC**
- *"How do we execute the change?"* → **IB**

For the arc42 chapter mapping, C4 diagram lexicon, and skill routing tables, see `architecture-frameworks-reference.md`.

---

## The Pipeline (end to end)

```
1. RESEARCH    /dekspec:archeology --scan <component>   (or ad-hoc design/code research)
2. DESIGN      /write-ae <description>   /write-adr <decision>          → AE, ADRs
3. SPECIFY     /write-ws <description>   /write-ic <boundary> (if needed) → WS, IC
4. PLAN        /write-ibs <spec>                                         → IBs
5. PREPARE     /write-code-beads <IB>   /write-tests   /write-evals (if model output)
6. BUILD       /exec-coding-session   — agents execute beads in parallel worktrees
7. REVIEW      /present --review     — serve draft/proposed artifacts for review
```

---

## Artifact Lifecycle

`TODO` --> `DRAFT` --> `PROPOSED` --> `ACCEPTED` --> `LOCKED` | any stage --> `DEPRECATED` | ADRs also: --> `SUPERSEDED`

`DRAFT`/`PROPOSED` are editable; `ACCEPTED` approved (changes cascade downstream); `LOCKED` frozen (`--unlock` to edit, `--lock` runs a pre-lock audit). `DEPRECATED`/`SUPERSEDED` are terminal — `SUPERSEDED` is ADR-specific. The operating guide carries per-status semantics.

IBs also use directory lifecycle: `queued/` --> `active/` --> `completed/`

---

## Skills

| Skill | Purpose |
|---|---|
| `/dekspec:archeology` | Brownfield spec-gap recovery — scan code, propose retroactive Intents, ratify into LOCKED tree |
| `/write-mission` | Author a near-immutable Mission anchoring a multi-Intent campaign |
| `/write-ae` | Create an L1 Architecture Element describing an architectural slice |
| `/write-adr` | Record architectural decisions |
| `/write-intent` | Author a cross-cutting Intent with a Verification predicate |
| `/write-ws` | Write L2 behavioral specs with expert role passes |
| `/write-ic` | Define cross-component boundary contracts |
| `/write-ibs` | Decompose specs into L3 work packages |
| `/write-code-beads` | Convert IBs into atomic L4 work units |
| `/write-tests` | Write deterministic tests from acceptance criteria |
| `/write-evals` | Write probabilistic evals for model output |
| `/exec-coding-session` | Orchestrate parallel AI coding agents |
| `/doctor` | AE-aware fidelity audit — canonical for new audits |
| `/write-ggc` | Log domain corrections, add glossary terms, audit terminology health |
|  | Record a system-level divergence as a numbered note |
| `/dekspec:brownfield-ingest` | Classify inherited markdown prose into DekSpec artifact slots |
| `/dekspec:dispatch-inbox-listener` | Async-dispatch listener over `.dekspec/inbox/` |
| `/present` *(user-level)* | Serve artifacts in the browser for review/editing |

Every skill supports `--help` for full usage details, modes, and examples.

---

## Common Flags (consistent across skills)

| Flag | What it does |
|---|---|
| `--help` | Show usage, modes, examples |
| `--audit` | Read-only quality check |
| `--revise <notes>` | Incorporate engineer feedback |
| `--lock` | ACCEPTED --> LOCKED (with pre-lock audit) |
| `--unlock` | LOCKED --> PROPOSED (with impact assessment) |
| `--accept` | Audit + PROPOSED → ACCEPTED (Architecture Elements, ADRs, Working Specs, Interface Contracts, IBs). `--approve` is a retained alias on IBs. |
| `--resync` | Refresh against changed spec (IBs) |
| `--dry-run` | Preview without committing (IBs, coding session) |
| `--provisional <slug>` | Write a provisional artifact under `dekspec/provisional/<slug>/` instead of the canonical directory (8 authoring skills: write-mission, write-intent, write-adr, write-ae, write-ic, write-ws, write-ibs, write-sp) |

---

## Key Principles

- **Resolve everything before code.** All ambiguities, conflicts, decisions, and domain questions are resolved in L1-L3. The coding agent only lays down code. Unclear beads = upstream process failure.
- **Beads are self-contained.** The coding agent reads ONLY the bead. `/write-code-beads` distills ADR decisions, IC constraints, and spec context from the IB into the bead's Constraints & Decisions.
- **High cohesion, low coupling.** Each IB has one purpose, one primary failure domain. IBs interact through data interfaces only.
- **Changes cascade downward.** L1 changes cascade: specs resync, IBs `--resync`, beads `--rebuild`, tests rewrite.

---

## Severity

**Severity:** `P0` (highest — reserved) → `P1` (blocking pre-IB) → `P2` (blocking pre-code) → `P3` (advisory / tracked-only) — see [methodology §Severity Vocabulary](dekspec-methodology.md#severity-vocabulary) for the full ladder, legacy alias map, and `dekspec doctor` exit-code semantics.

---

## Lite vs full

DekSpec ships two **methodology profiles** — `lite` and `full` — selected per repo
via `.dekspec/config.yaml` (`methodology_profile`, short alias `profile`). The
profile is the one knob that scales the ceremony to the team.

**Trimmed artifact set under lite.** `dekspec init --profile lite` scaffolds a
minimal tree — System Vision + Constitution, the `adrs/` / `intents/` /
`divergences/` directories, and the ADR + Intent indexes. It does **not**
scaffold `architecture-elements/`, `working-specs/`, `interface-contracts/`,
`missions/`, or `impl-briefs/`. A solo engineer grounds work in the Constitution
plus Intents rather than a deep AE → WS → IC → IB graph. The compact AGENTS.md
emitter follows suit: under `lite`, `dekspec aggregate agents-md` emits a
single-page artifact (a one-page Constitution summary + the in-flight Intent)
instead of the full corpus dump.

**Escalation path — the upgrade is monotonic.** Run
`dekspec config set profile full` to switch an existing repo. The full profile
*surfaces new requirements* (e.g. an Intent must link an Architecture Element)
without flagging existing lite Intents as malformed: the lite Intent body is a
strict subset of the full body — same section headings, same parser — so a lite
Intent still parses as a structurally valid Intent after the switch. The audit
simply reports the newly-applicable rules as additions, not as schema
violations. The upgrade adds requirements; it never invalidates prior work.
*Downgrading (`full → lite`) is not monotonic* — full-profile artifacts (AEs,
WSs, ICs, Missions) have no home in a lite tree.

**Decision rubric — which profile?**

| Choose `lite` when... | Choose `full` when... |
|---|---|
| Solo engineer | Multiple engineers coordinating |
| Single repo | Cross-repo / shared-library work |
| Non-autonomous (you drive each step) | Autonomous-build (agents execute beads) |
| Throwaway / exploratory project | Long-lived production system |

When in doubt start `lite` and escalate — the upgrade is cheap and monotonic.

---

## Provisional Incubation

Exploratory work — refactors, new features, system-level investigations — stages
under `dekspec/provisional/<incubation-slug>/` before landing in the canonical
tree. The mechanics:

- **Scaffold** — `dekspec library new-provisional <kind> <slug>` (or any
  `/dekspec:write-*` skill with `--provisional <incubation-slug>`) writes a
  fresh artifact at `dekspec/provisional/<slug>/<KIND>-provisional-<title-slug>.md`.
  Skill creates a working-tree branch on first artifact (`int/INT-NNN`,
  `mission/MSN-NNN`, `feat/<slug>` for others) unless `--no-branch` is passed.
- **Copy-on-write (CoW) staging** — if a canonical artifact must be modified
  inside an incubation, `dekspec library cow-stage <canonical-path> --incubation
  <slug>` copies it under the incubation folder, stamps `replaces: <KIND-NNN>`
  in the frontmatter, and the engineer edits the copy instead of the canonical.
  CoW is idempotent; re-running it on an already-staged file is a no-op.
- **Promote** — `dekspec repo promote-provisional <slug>` migrates the
  incubation folder into the canonical tree atomically. NEW artifacts get the
  next-free `<KIND>-NNN`; REPLACE artifacts (those carrying `replaces:`)
  preserve the canonical ID and overwrite. Cross-refs inside the bundle are
  rewritten as part of the same atomic.
- **Five skills carve out.** `/write-constitution`, `/write-sv`, `/write-ggc`,
  `/write-evals`, `/write-tests` do **not** accept `--provisional` — the first
  three are singletons; the last two operate on existing beads rather than
  authoring new artifacts.

The advisory audit rule `L-PROVISIONAL-STALE` fires on incubation folders older
than 30 days (mtime-based; engineers `touch` to reset). `T-COW-CANONICAL-EDITED`
fires when a CoW-staged canonical was also edited on the working branch.

The full lifecycle — scaffolding through promotion to the canonical-replace
gate — is in the operating guide §Provisional incubation.

---

## System Integrity

Run `/doctor` periodically or after major changes. It checks skill / template / index / guide alignment, header-metadata freshness, glossary consistency, cross-artifact coherence, sibling-SSoT duplication, extraction-landing, and cascade-scope discipline. See the skill `--help` for `--fix`, `--full`, and the full scope list.

**Provisional + CoW audit rules** (P3 advisory unless noted):
`L-PROVISIONAL-TREE-PRESENT` (incubation folder exists),
`L-PROVISIONAL-STALE` (>30 days old, mtime),
`L-COW-SIBLING-COLLISION` (P2 — two incubations claim the same canonical path),
`T-COW-CANONICAL-EDITED` (P2 — CoW-staged canonical was also edited on the
working branch).

**Skill-frontmatter normalization rules** (P2 mechanical, see
`dekspec-skill-flag-defaults.md`):
`T-SKILL-FRONTMATTER-NORMAL`,
`T-SKILL-HELP-MODE-PRESENT`,
`T-SKILL-ARG-HINT-COMPLETE`.

---

## Where Things Live

```
dekspec/
  dekspec-operating-guide.md            ← master guide
  dekspec-quick-reference.md            ← this document
  project-context.md                    ← role definitions
  domain-glossary.md                     ← canonical terminology
  system-vision.md                       ← top-level system description
  adrs/ADR-NNN-*.md                       ← architectural decisions
  architecture-elements/AE-NNN-*.md       ← architectural slice descriptions
  working-specs/WS-NNN-*.md               ← behavioral specifications
  interface-contracts/IC-NNN-*.md         ← boundary definitions
  impl-briefs/{queued,active,completed}/  ← implementation plans
  missions/MSN-NNN-*.md                   ← multi-Intent campaigns
  provisional/<slug>/                     ← exploratory staging (pre-promotion)
  divergences/NNN-*.md                    ← append-only divergence ledger
  workspace/archaeology/                  ← research notes
  templates/                              ← artifact templates
  skills/                                 ← all DekSpec skills (canonical)
.claude/skills/                           ← discovery shims (symlinks into dekspec/skills/)
.beads/beads.jsonl                        ← bead queue (managed by br)
tests/                                    ← pytest suite
```
