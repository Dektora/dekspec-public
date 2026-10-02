---
name: review-ib
description: Pre-authorization review of an Implementation Brief's contract and acceptance floor via the shared math-olympiad orchestration. Use after /write-tests and before `dekspec ib accept` — evidence for the authorization decision, not a status, and required for an IB with `pytest:` conditions or declared assets, whose acceptance tests it oracle-reviews (ADR-062). Checks that content is classified correctly (binding vs acceptance vs hypothesis), obligations are referenced and resolve, acceptance is observable and complete, each new assertion's expectation basis is independent and the floor genuinely red, scope and protected surfaces cohere, and spec impact and slice routing are declared. Findings go to the IB's Open Issues; a passing floor review is recorded as a `Floor reviewed:` Amendment Log row.
reasoning_effort: max
disable-model-invocation: false
mode: lite
# override-reason: Edit writes surfaced findings into the reviewed IB's Open Issues and a passing floor review into its Amendment Log — the review's only outputs now that REVIEW_IB is not a status (ADR-057, ADR-062)
allowed-tools: Read Grep Glob Bash Agent Edit
argument-hint: [--help] <IB-ID>
---

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:review-ib"
one_line: "Pre-authorization review of an IB contract and its acceptance floor via the math-olympiad orchestration; findings land in the IB's Open Issues, a passing floor review in its Amendment Log."
modes:
  - { flag: "", args: "<IB-ID>", description: "Review the IB contract and oracle-review its acceptance tests before `dekspec ib accept`; emit GO / NO-GO / INSUFFICIENT_EVIDENCE, record surfaced findings as Open Issues and a passing floor review as a `Floor reviewed:` row." }
  - { flag: "--help", args: "", description: "Show this manifest." }
examples:
  - "/dekspec:review-ib IB-067"
```

## Mode Detection

- `--help` → render **Help Mode** and stop.
- an `<IB-ID>` (or IB path) → run the review below.

# /dekspec:review-ib <IB-ID>

> Pre-authorization review of an Implementation Brief's **contract** and its **acceptance floor**. Loads [`_lib/review-orchestration.md`](../_lib/review-orchestration.md) with the REVIEW_IB lens pack ([`lenses.md`](lenses.md)) and emits GO / NO-GO / INSUFFICIENT_EVIDENCE per **ADR-026**. The IB is the executable work contract (ADR-056), so this review asks: is it a contract an agent can execute and a reviewer can later judge — and are its acceptance tests evidence, each expected result resting on a basis independent of the implementation (ADR-062)?

This review plays the **`spec-reviewer`** role ([`_lib/agent_roles.md`](../_lib/agent_roles.md)): the shell loads it once with `dekspec resource role spec-reviewer` and composes it into every lens specialist. Findings inform the authorization decision; the review never accepts the IB. **Independence (ADR-062):** the oracle review is never performed by the test author or a builder — run this review in a context that did not write the acceptance tests (a fresh session), and never let the author's reasoning reach a specialist.

Sibling: `/dekspec:review-pr` reviews the delivered implementation against the same contract after execution.

## When to run

After the IB is written and its acceptance tests exist (`/dekspec:write-tests`, genuinely red on `dekspec ib floor`), and **before `dekspec ib accept`** — the one order is: write the IB (`dekspec ib lint`, `dekspec ib propose`) → `/dekspec:write-tests` → `/dekspec:review-ib` → `dekspec ib accept` (ADR-062). It runs on a PROPOSED IB, or on a DRAFT. For an IB with `pytest:` conditions or declared acceptance assets the review is **mandatory**: its `acceptance-oracle` lens is the oracle review of the floor, and `/implement` readiness refuses the IB until a `Floor reviewed:` row names its baseline digest. For any other IB it is recommended evidence. Either way there is no review status (ADR-057 retired REVIEW_IB / REVIEW_IB_FAIL). A pre-start change to the acceptance tests (or to the contract, which moves the floor digest) repeats the review before `dekspec ib baseline`. A `legacy` IB is reviewed as part of adoption (`/write-ibs --adopt`), against its rewritten delegated form, before `dekspec ib adopt`.

This review never records `dekspec ib review` — that verdict is the post-implementation one the completion gate reads.

## Input bundle

The shell collects these once and projects each lens's `input_slice`:

| Slot | Source |
|---|---|
| `ib.body` | the IB markdown |
| `ib.header` | Status, Authority policy, Parent, Depends on, Spec impact |
| `ib.outcome` / `ib.rationale` | `## Outcome`, `## Rationale` |
| `ib.scope` | `## Scope` globs and `### Out of scope` |
| `ib.obligations` | `## Obligations` references and local obligations |
| `ib.protected_surfaces` | `## Protected Surfaces` |
| `ib.acceptance` | the `## Acceptance` YAML block and declared acceptance assets |
| `ib.hypothesis` | `## Implementation Hypothesis` |
| `ib.environment_prerequisites` | `## Environment Prerequisites` |
| `ib.lint` | `dekspec ib lint <IB> --json` |
| `ib.context` | `dekspec ib context <IB> --json` — each obligation's canonical text, source status and hash, plus unresolved-reference problems |
| `parent.*` | when `Parent` is set: the parent's path; for an Intent, its `Components affected` and `outcome_verification` |
| `sibling_ibs` | IBs sharing this IB's Parent or delivery: scope, protected surfaces, local obligations, `Depends on` |
| `source_ae_paths` | AEs the obligations or parent name |
| `glossary` | `dekspec/domain-glossary.md` |
| `audit_doctor` | cached `dekspec doctor --json --at .` snapshot |
| `acceptance.test_sources` | the full source of every test file the `pytest:` conditions name and of every declared acceptance asset (fixtures, golden data) — the `Basis:` lines are read in place |
| `acceptance.surface_skeleton` | the behavior-free entry points committed with the tests for surfaces that do not exist yet (the write-tests hand-off names them; otherwise the in-Scope modules the tests import or invoke), as source |
| `workspace.acceptance_test_run` | the floor report — `dekspec ib floor <IB>` (and `--json`): per condition and node, new or preserved, failure kind, failure line, declared basis (inherited marked), and the floor digest |
| `workspace.production_tree_absence` | whether the behavior those tests target is still absent (a behavior-free surface skeleton is expected) |

## Lens pack

The 17 lenses in [`lenses.md`](lenses.md):

- **Contract classification and sources (ADR-055, ADR-056)** — content-classification, obligation-references, spec-impact, slice-and-pin-routing.
- **Acceptance (ADR-057, ADR-062)** — acceptance-falsifiability, acceptance-coverage, outcome-tdd-discipline, acceptance-oracle.
- **Boundaries** — scope-and-protected-surfaces, sibling-ib-coherence, dependency-readiness.
- **Design and wording** — interface-depth, constraint-completeness, rollout-risk-plan, ambiguity-audit, glossary-discipline.
- **Environment** — environment-prerequisites.

## Verdict and findings

Asymmetric voting per ADR-026: one lens at ≥80 confidence NO-GO's the verdict.

- **GO** — every lens <80, no abstentions. Recommend `dekspec ib accept`.
- **NO-GO** — a lens vetoed. Do not accept until the contract is fixed and re-reviewed.
- **INSUFFICIENT_EVIDENCE** — no veto, at least one abstention; name what is missing and let the engineer decide.

Write every surfaced finding into the IB's `## Open Issues` as `- [ ] <finding> — **Source:** review-ib <date> (<lens>) — **Severity:** P1|P2` (`critical` → `P1`, `important` → `P2`).

**The floor review (ADR-062).** For an IB with `pytest:` conditions or declared assets, when the verdict is GO and `dekspec ib floor <IB>` reports the floor OK, the shell writes — on behalf of its independent reviewer, as it writes Open Issues, never in the test author's context — one row into the IB's `## Amendment Log`:

`| <date> | Review | Floor reviewed: PASS — digest <64 hex> — <n> new nodes genuine red with a basis, <m> preserved passing (review-ib acceptance-oracle) | <reviewer identity> |`

The digest is the floor digest the report states; `<n>` and `<m>` are its new and preserved node counts. Nothing is written for a failing outcome. The authorizer takes the baseline (`dekspec ib accept`, or `dekspec ib baseline` before the run starts) only while `dekspec ib floor` still reports that digest.

Nothing else is written; no status changes. The verdict is **RECOMMEND-only** (ADR-026): the engineer makes the authorization decision.

A contract fix on an IB that is already ACCEPTED but not started needs `dekspec ib baseline <IB> --reason …`; after `dekspec ib start`, only `dekspec ib amend` changes the contract.

## Failure modes

- **Malformed lens pack** — a lens missing a required field stops the review before fan-out.
- **`dekspec doctor --json --at .` fails** — abort before fan-out; several lenses read the cache.
- **All lenses abstain** — INSUFFICIENT_EVIDENCE; record the abstention in the report.
- **`dekspec ib floor <IB>` fails or the acceptance tests are missing** — the floor cannot be judged: `outcome-tdd-discipline` and `acceptance-oracle` report it (missing acceptance tests are a finding, since they are mandatory before authorization); no floor-review row is written.

## Cross-references

- ADR-026 (review shape), ADR-054 (slice and pin routing, revised by ADR-056), ADR-055 (authority categories), ADR-056 (IB as work contract, one home per fact), ADR-057 (acceptance contract, decision-only lifecycle), ADR-062 (expectation basis, genuine red, the floor review before the baseline).
- ADR-036 + Constitution Article 4 (source of `interface-depth`).
- `/dekspec:review-pr` — the post-implementation sibling.
