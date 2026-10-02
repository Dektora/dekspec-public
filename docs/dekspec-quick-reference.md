# DekSpec — Quick Reference

**Read time: 5-10 minutes.** Full guide: `dekspec/dekspec-operating-guide.md`

---

## The Problem This Solves

AI coding agents fill ambiguity with confident, plausible, wrong decisions. By review time the wrong assumption is load-bearing. **The solution: settle what must be true — obligations, boundaries, acceptance — before the agent starts, let the agent own how, and accept the work only on evidence.** Specs are the mechanism. Each Implementation Brief's execution record is the persistent memory of the work.

**The engineer's role:** provide domain knowledge, make decisions, approve work. AI drafts, critiques, and codes.

---

## Four Layers

| Layer | What | Artifacts | Skills |
|---|---|---|---|
| **L1 Design** | Vision, principles, decisions | System Vision, Architecture Elements (AE), ADRs, Domain Glossary | `/write-ae`, `/write-adr`, `/recover-specs` |
| **L2 Specification** | Behavioral contracts | Working Specs (WS), Interface Contracts (IC) | `/write-ws`, `/write-ic` |
| **L3 Implementation** | Executable work contracts | Implementation Briefs (IB) | `/write-ibs` |
| **L4 Construction** | Code, evidence, completion | Code, acceptance tests, evals, IB execution records | `/write-tests`, `/write-evals`, `/orchestrate-coding-session`, `/review-pr`, `/land-intent` |

**Intent (`INT-NNN`) and Mission (`MSN-NNN`) anchor at L1 and span downward through L2-L4.** They link to L1 AEs, parent L3 IBs, may revise L2 WSs / ICs, and carry L4-surface `verification` / `rollback` / `kill_criteria` commands. The operating guide covers their audit rule classes (L7a / L7b / L8 / L9). Both are optional: a bounded change is one IB with no parent (ADR-056); reach for an Intent when an outcome spans several IBs, a Mission for a programme with kill criteria.

**Hierarchy:** L1 governs L2 governs L3 governs L4. Conflicts resolve upward. Within L1, contradictions are consistency bugs — fix them, don't pick a winner. L1 artifacts are the source of truth (System Vision for scope, Architecture Elements for descriptive slices, ADRs for decisions, Domain Glossary for terminology); L2-L4 derive from L1 plus engineer expertise. Every fact has one home: an IB *references* the ADR / IC / WS that owns an obligation instead of copying it (ADR-056).

**Practical reading test** (which artifact does this content belong in?):
- *"What is the thing?"* → **AE** · *"Why did we choose this?"* → **ADR**
- *"What must be true?"* → **WS** · *"What is the boundary promise?"* → **IC**
- *"How do we execute the change?"* → **IB**

For the arc42 chapter mapping, C4 diagram lexicon, and skill routing tables, see `architecture-frameworks-reference.md`.

---

## The Pipeline (end to end)

```
1. RESEARCH    /recover-specs <component>       (or ad-hoc design/code research)
2. DESIGN      /write-ae, /write-adr            → AE, ADRs   (only when the change alters them)
3. SPECIFY     /write-ws, /write-ic             → WS, IC     (only for behavior / contracts spanning IBs)
4. PLAN        /write-ibs                       → one IB per bounded change (with or without a WS)
5. PREPARE     /write-tests, /write-evals       → acceptance assets: a basis per assertion, genuine red on `ib floor`
               /review-ib                       → contract review + oracle review; pass = `Floor reviewed:` row
               dekspec ib accept                → the baseline protects exactly the reviewed floor
6. BUILD       /orchestrate-coding-session      → start, investigate, plan, attempts, verify
7. REVIEW      /review-pr                       → an independent verdict per IB
8. LAND        /land-intent                     → complete each IB, check the delivery, operator merges

   6–8 in one request, once the work is READY:
   /implement <INT | IB | feature>      → construct, review, repair, integrate, verify, complete (ADR-059)
```

Steps 1–3 are used when they add something. Step 5 is not optional for an IB with `pytest:` conditions or declared assets (ADR-062): one order everywhere — write the IB (`dekspec ib lint`, `dekspec ib propose`) → `/write-tests` → `/review-ib` → `dekspec ib accept`; a pre-start change to the tests repeats the oracle review before `dekspec ib baseline`. The builder never writes an acceptance test, and `/implement` readiness refuses an IB whose named nodes are missing from its baseline or whose baseline digest no `Floor reviewed:` row names. The engine verbs underneath (the skills call them; `dekspec ib <verb> --help` for flags):

```
dekspec ib new <slug>
dekspec ib propose IB-NNN
dekspec ib floor IB-NNN
dekspec ib accept IB-NNN
dekspec ib context IB-NNN
dekspec ib start IB-NNN
dekspec ib plan IB-NNN --file plan.yaml
dekspec ib verify IB-NNN
dekspec ib review IB-NNN --reviewer <reviewer> --verdict pass
dekspec ib complete IB-NNN
dekspec delivery check
```

`dekspec ib ready` lists accepted IBs whose dependencies are complete and that no run owns — the coding pull surface (`br` stays the issue and governance tracker; there are no code beads).

---

## Artifact Lifecycle

Statuses record decisions, not activity (ADR-057):

| Kind | Lifecycle |
|---|---|
| Constitution, System Vision, ADR, IC, SP | `DRAFT` → `PROPOSED` → `ACCEPTED` → `LOCKED` (unlock to version) · `DEPRECATED` / `SUPERSEDED` |
| Architecture Element, Working Spec | `DRAFT` → `PROPOSED` → `ACCEPTED` · `DEPRECATED` — never lock |
| Implementation Brief | `DRAFT` → `PROPOSED` → `ACCEPTED` → `COMPLETE` · `SUPERSEDED` / `DEPRECATED` — `COMPLETE` only via `dekspec ib complete` |
| Intent | `DRAFT` → `PROPOSED` → `ACCEPTED` → `COMPLETE` · `SUPERSEDED` — completes via `dekspec intent verify` + `dekspec intent complete` |
| Mission | `PROPOSED` → `ACTIVE` → `COMPLETE` · `KILLED` / `SUPERSEDED` |

Progress, attempts, failures, reviews and blockers live in the IB's execution record (`dekspec ib status`), not in a status. `TODO`, the IB review/test states, Intent `OVERSIZED` / `IMPLEMENTING` / `TESTPASS` / `MERGED` and Mission `COMPLETING` are retired; `dekspec migrate` maps them.

---

## Skills

| Skill | Purpose |
|---|---|
| `/recover-specs` | Brownfield spec-gap recovery — scan code, propose retroactive Intents or IBs (composed by `/write-intent --analyze`) |
| `/write-mission` | Author a near-immutable Mission anchoring a multi-Intent campaign |
| `/write-ae` | Create an L1 Architecture Element describing an architectural slice |
| `/write-adr` | Record architectural decisions |
| `/write-intent` | Author a cross-cutting Intent with a Verification predicate |
| `/write-ws` | Write L2 behavioral specs with expert role passes |
| `/write-ic` | Define cross-component boundary contracts |
| `/write-ibs` | Author IBs — from a WS, or directly for a bounded change; `--adopt` a legacy IB |
| `/write-tests` | Write acceptance tests named by an IB's conditions — a basis per new assertion, genuine red on `dekspec ib floor` — before authorization (mandatory) |
| `/review-ib` | Pre-authorization review of an IB contract and oracle review of its acceptance tests and floor report; a pass is a `Floor reviewed:` row |
| `/write-evals` | Write probabilistic evals for model output |
| `/implement` | Implement ready work end to end — no prompts, no flags; READY = `dekspec implement ready` (ADR-059) |
| `/orchestrate-coding-session` | Execute accepted IBs through the `dekspec ib` engine (parallel worktrees for independent IBs) |
| `/review-pr` | Independent post-implementation review; records a verdict per IB, judging the basis of amended or added acceptance assets before acknowledging them |
| `/land-intent` | Complete each IB, run the delivery gate, operator-confirmed merge |
| `/doctor` | AE-aware fidelity audit — canonical for new audits |
| `/write-glossary` | Extract term candidates and add terms to the domain glossary |
| `/write-corrections` | Log domain corrections, track recurrences, promote at threshold |
| `/ingest-docs` | Classify inherited markdown prose into DekSpec artifact slots (helper tool) |

Core skills support `--help`. The helper tools take natural-language requests; the ten user-only ones (`project-board`, `audit-codebase`, `deepen`, `security-review`, `ingest-docs`, `handoff`, `diagnose-session`, `debug`, `prototype`, `spike`) are started by the operator: `/dekspec:<tool>` on Claude Code, or the host-native skill invocation on other hosts, and the authoring skills compose `interview-me` and `recover-specs`. Ask a tool what it does for examples and recovery options.

---

## Common Flags (consistent across skills)

| Flag | What it does |
|---|---|
| `--help` | Show usage, modes, examples |
| `--audit` | Read-only quality check |
| `--revise <notes>` | Incorporate engineer feedback |
| `--lock` | ACCEPTED --> LOCKED (with pre-lock audit) — Constitution, System Vision, ADR, IC, SP only |
| `--unlock` | LOCKED --> PROPOSED (with impact assessment) — same kinds |
| `--accept` | Audit + PROPOSED → ACCEPTED (Architecture Elements, ADRs, Working Specs, Interface Contracts, Intents). An IB is accepted with `dekspec ib accept`, which also takes its acceptance baseline. |
| `--dry-run` | Preview without committing (IBs, coding session) |
| `--provisional <slug>` | Write a provisional artifact under `dekspec/provisional/<slug>/` instead of the canonical directory (8 authoring skills: write-mission, write-intent, write-adr, write-ae, write-ic, write-ws, write-ibs, write-sp) |

---

## Key Principles

- **Bind the what, delegate the how.** An IB binds its obligations, protected surfaces, scope and acceptance conditions; its implementation hypothesis is a revisable starting guess. The agent may read anything, investigates before planning, and escalates only for a decision it is not authorized to make — changing an obligation, leaving scope, weakening acceptance, an unresolved contradiction, a missing prerequisite (ADR-055). An underdefined contract is an escalation and an upstream defect.
- **One home per fact.** An IB references the ADR / IC / WS that owns an obligation; `dekspec ib context` delivers the canonical text with its revision. Nothing is copied into a task or prompt (ADR-056).
- **Complete on evidence.** `dekspec ib complete` requires fresh passing evidence for every acceptance condition, an independent reviewer's verdict, and passing scope and integrity checks. Task closure proves nothing (ADR-057).
- **High cohesion, low coupling.** Each IB has one purpose, one primary failure domain. IBs interact through data interfaces only.
- **Changes cascade downward.** L1 changes cascade: specs revise, the next generated context picks up the new text, and evidence bound to the old sources goes stale. Acceptance changes after execution starts go through `dekspec ib amend`.

---

## Severity

**Severity:** `P0` (highest — reserved) → `P1` (blocking pre-IB) → `P2` (blocking pre-code) → `P3` (advisory / tracked-only) — see [methodology §Severity Vocabulary](dekspec-methodology.md#severity-vocabulary) for the full ladder, legacy alias map, and `dekspec doctor` exit-code semantics.

---

## One lane, at full rigor

DekSpec is **one system, at full rigor** (ADR-050). There is no trimmed lane and
no "which ceremony level?" decision to make: `dekspec init` scaffolds the whole
tree, every audit rule in the baseline rule set applies, and the behaviour you
get by doing nothing is the behaviour the library is designed around.

**The default lane has no name.** Only a *deviation* needs one, because only a
deviation must be asked for. There is no `--profile` flag on `init` and no lane
name in `.dekspec/config.yaml` to choose. The `methodology_profile: full` value
is the default's legacy spelling, retained so existing configs keep working;
`v1` names the *rule-set version*, not a lane. In prose the default lane is
described as serving a **solo engineer** — one person directing agents — but
that word is an audience description, never an identifier.

**`team` is the sole named opt-in, and it is a future lane.** Setting
`methodology_profile: team` resolves the `team` audit profile, which inherits
the baseline rule set and *adds* the INT-021 approval gates (reviewer signatures
enforced on artifact status transitions). It is additive by construction — it
never subtracts a rule. The full definition of team-oriented agentic
engineering is deliberately open and will be settled by a later Mission; see
ADR-051 for the shape it is expected to take.

**Why there is no lite lane.** A trimmed lane is a small step up from
vibecoding: it optimises for prototyping, which is the opposite of what this
library exists to promote. The "ceremony is too heavy" concern that motivated
the old `lite` profile is real, but it is a **usability** problem — simpler
commands, fewer flags, better guidance — not a rigor problem. For genuine
exploration, use the governed pre-spec surfaces `/prototype` and `/spike`, whose
output is *knowledge* rather than production code under relaxed governance.

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
- **Promote** — hand-promote the incubation folder into the canonical tree via
  the `dekspec.promote` helpers (`plan_promotion` → `apply_promotion`); see
  `docs/dekspec-operating-guide.md` §Provisional Promotion. NEW artifacts get
  the next-free `<KIND>-NNN`; REPLACE artifacts (those carrying `replaces:`)
  preserve the canonical ID and overwrite. Cross-refs inside the bundle are
  rewritten as part of the same atomic step. (The former `dekspec repo
  promote-provisional` CLI verb was retired 2026-05-25 and removed in ds-ib9o.)
- **Six skills carve out.** `/write-constitution`, `/write-sv`, `/write-glossary`,
  `/write-corrections`, `/write-evals`, `/write-tests` do **not** accept
  `--provisional` — the first four are singletons; the last two write
  acceptance assets for an existing IB rather than authoring new artifacts.

The advisory audit rule `LINK-PROVISIONAL-STALE` fires on incubation folders older
than 30 days (mtime-based; engineers `touch` to reset). `T-COW-CANONICAL-EDITED`
fires when a CoW-staged canonical was also edited on the working branch.

The full lifecycle — scaffolding through promotion to the canonical-replace
gate — is in the operating guide §Provisional incubation.

---

## System Integrity

Run `/doctor` periodically or after major changes. It checks skill / template / index / guide alignment, header-metadata freshness, glossary consistency, cross-artifact coherence, sibling-SSoT duplication, extraction-landing, and cascade-scope discipline. See the skill `--help` for `--fix`, `--full`, and the full scope list.

**AGENTS.md freshness.** `dekspec aggregate agents-md` rewrites only the DekSpec-owned region (`<!-- dekspec:agents-md begin -->` … `<!-- dekspec:agents-md end -->`) and keeps everything else; a legacy whole-file AGENTS.md needs `--migrate` once (`--migrate --dry-run` previews). `dekspec aggregate agents-md --check` is read-only and prints one verdict — `current` (0), `stale` (1), `absent` (1 if required), `inapplicable` (0), `invalid` (1). Declare the projection in `.dekspec/config.yaml` (`agents_md: {path, status, include, required}`) and `dekspec doctor` fails when it goes stale (ADR-063).

**Provisional + CoW audit rules** (P3 advisory unless noted):
`LINK-PROVISIONAL-TREE-PRESENT` (incubation folder exists),
`LINK-PROVISIONAL-STALE` (>30 days old, mtime),
`LINK-COW-SIBLING-COLLISION` (P2 — two incubations claim the same canonical path),
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
  impl-briefs/IB-NNN-*.md                 ← executable work contracts
  intents/INT-NNN-*.md                    ← multi-IB outcomes (optional)
  missions/MSN-NNN-*.md                   ← multi-Intent campaigns (optional)
  provisional/<slug>/                     ← exploratory staging (pre-promotion)
  divergences/NNN-*.md                    ← append-only divergence ledger
  workspace/archaeology/                  ← research notes
  templates/                              ← artifact templates
  skills/                                 ← all DekSpec skills (canonical)
.claude/skills/                           ← discovery shims (symlinks into dekspec/skills/)
.dekspec/execution/IB-NNN/record.jsonl    ← IB execution records (written by `dekspec ib`)
.beads*/                                  ← br issue + governance trackers (no code beads)
tests/                                    ← pytest suite
```
