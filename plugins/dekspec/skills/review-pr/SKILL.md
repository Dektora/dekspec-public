---
name: review-pr
description: Post-implementation review of a delivery (one branch / worktree / pull request, per ADR-058) at its head. For every IB the delivery carries, judges the diff against that IB's contract, generated context, evidence, deviations and attention items, then records one verdict per IB with `dekspec ib review`. Use after `dekspec delivery verify` and before `dekspec ib complete`; the reviewer must not be a builder of the IB.
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
mode: lite
allowed-tools: Read Grep Glob Bash Agent
argument-hint: [--help] <PR-# | branch> [--ib IB-NNN ...] [--base <branch>]
---

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:review-pr"
one_line: "Review a delivery at its head against every IB it carries; record one verdict per IB with `dekspec ib review`."
modes:
  - { flag: "", args: "<PR-# | branch> [--ib IB-NNN ...] [--base <branch>]", description: "Review the delivery head; emit GO / NO-GO / INSUFFICIENT_EVIDENCE per IB and record pass/fail verdicts." }
  - { flag: "--help", args: "", description: "Show this manifest." }
examples:
  - "/dekspec:review-pr 42"
  - "/dekspec:review-pr int/INT-129-land-intent --ib IB-140 --ib IB-141"
```

## Mode Detection

- `--help` → render **Help Mode** and stop.
- a PR number or branch → run the review below. `--ib` pins the IBs (repeatable); `--base` names the base branch (default `main`).

# /dekspec:review-pr <PR-# | branch>

> Post-implementation review of a **delivery at its head** (ADR-058). Loads [`_lib/review-orchestration.md`](../_lib/review-orchestration.md) with the REVIEW_PR lens pack ([`lenses.md`](lenses.md)) and reaches GO / NO-GO / INSUFFICIENT_EVIDENCE for each IB per **ADR-026**. The verdict is recorded as an event in the IB's execution record, bound to the reviewed content (ADR-057) — that event, not a report, is what `dekspec ib complete` and `dekspec delivery check` read.

Sibling: `/dekspec:review-ib` reviews the contract before `dekspec ib accept`.

## When to run

At the delivery head, after `dekspec delivery verify` has recorded evidence there, and before `dekspec ib complete`. `/dekspec:land-intent` invokes it; it can also run on its own. Re-run it after any commit that touches a reviewed surface — a verdict carries forward only across changes outside every surface it reviewed (scope, protected surfaces, acceptance assets, runner inputs, governing sources).

**Independence.** This review plays the **`code-reviewer`** role ([`_lib/agent_roles.md`](../_lib/agent_roles.md)): the shell loads it once with `dekspec resource role code-reviewer` and composes it into every lens specialist. Record verdicts under an identity that is not a builder of the IB — not its run owner and not an attempt actor (`dekspec ib status <IB>` shows them). The engine refuses a builder's verdict. Specialists get the recorded facts and the code, never the builder's conversation or self-assessment.

## Pre-flight

1. **Resolve the delivery.** Check out the head. Take the IBs from `--ib`, or from the delivery verification that preceded this review (`dekspec delivery verify` discovers them from the IB files and execution records the branch diff touches).
2. **Too large to review?** If the diff is too large to review reliably, stop and recommend splitting the delivery (ADR-058 reconsideration trigger) rather than running a low-confidence review.
3. **Evidence current?** For each IB, the completion gate in `dekspec ib status <IB>` must show `evidence-current` and `acceptance-passed` at this head. If not, stop: the delivery is not ready for review (fix, then `dekspec delivery verify`).

## Input bundle (per IB)

| Slot | Source |
|---|---|
| `delivery.diff` / `delivery.files_changed` / `delivery.commits` | `git diff` / `git log` base..head |
| `delivery.ibs` | every IB in the delivery, with scope, protected surfaces and obligations |
| `delivery.integration` | the integration-command result from `dekspec delivery verify --json` |
| `ib.body` | the IB contract |
| `ib.context` | `dekspec ib context <IB> --json` — obligations' canonical text, status, hash; precedence |
| `evidence` | `dekspec ib verify <IB> --dry-run --json` — per-condition results, scope check, integrity problems, `attention` items |
| `status` | `dekspec ib status <IB> --json` — owner, attempts, blockers, completion gate |
| `record` | `.dekspec/execution/<IB>/record.jsonl` (read-only) — deviations, amendments, baselines, plan findings |
| `acceptance.test_sources` | the source of every acceptance asset, with each amended or added one (the `attention` items) and its diff since the baseline — `Basis:` lines included |
| `claude_md` | `CLAUDE.md` |
| `audit_doctor` | cached `dekspec doctor --json --at .` at the head |
| `git_history` | `git log` / `git blame` on touched surfaces |

Run the IB-scoped lenses once per IB. Delivery-wide lenses (bug-scan, claude-md-compliance, audit-rule-preflight, doc-changelog-entry, git-blame-prior-pr, cross-ib-integration) run once; attach each finding to the IB whose Scope contains the file, or to every IB when it concerns their interaction.

## Lens pack

The 13 lenses in [`lenses.md`](lenses.md):

- **Contract fidelity** — acceptance-satisfied, obligation-fidelity, scope-and-protected-surfaces, spec-impact, cross-ib-integration.
- **Evidence integrity** — acceptance-integrity, deviation-review, outcome-tdd-history.
- **Source quality** — bug-scan, claude-md-compliance.
- **Operational gates** — audit-rule-preflight, doc-changelog-entry.
- **Institutional memory** — git-blame-prior-pr.

## Recording the verdict

Asymmetric voting per ADR-026: any lens at ≥80 for an IB makes that IB NO-GO. Then, per IB:

- **GO** → `dekspec ib review <IB> --reviewer <you> --actor <you> --verdict pass --policy-revision <N> --acknowledge <item> … --notes "<summary>"`. Acknowledge each `attention` item from the evidence (amendments, acceptance assets first created during execution, runner-input changes) only after judging it sound — for an amended or added acceptance asset that includes the oracle judgment of `acceptance-integrity`: the expectation basis of each new or changed assertion is independent of the implementation and represents the required behavior (ADR-062). A system-derived, copied or blessed expectation is a veto, not an acknowledgment. An unacknowledged item keeps completion refused.
- **NO-GO** → `dekspec ib review <IB> --reviewer <you> --actor <you> --verdict fail --policy-revision <N> --notes "<vetoing lenses and findings>"`.

`<N>` is the policy revision in the header of the loaded `code-reviewer` role (`policy revision <N>`). If the role changed during the review, `dekspec ib review` refuses the verdict: review again under the current definition.
- **INSUFFICIENT_EVIDENCE** → record nothing; completion stays refused. Name what is missing and hand back. Record `fail` instead when the gap is itself a defect of the delivery (for example an acceptance condition that cannot be judged).

`--criteria` defaults to every `review:` acceptance condition; a pass covers them all, so judge each one. A FAIL on one IB holds the whole delivery (ADR-058). The fix loop is [`_lib/grep_loop_review_workflow.md`](../_lib/grep_loop_review_workflow.md): fix → re-verify → re-review, bounded by the engine's attempt limits.

A narrative report (vetoing lenses, surfaced findings, abstentions, head commit) may be posted to the PR or written under the gitignored scratch zone; it is commentary. The verdict is the event.

**RECOMMEND-only (ADR-026).** Recording a verdict never completes an IB or merges anything.

## Failure modes

- **IBs unresolvable** — no `--ib` and the delivery diff names no delegated IB: stop and ask. A `legacy` IB cannot take a verdict until adopted (ADR-055).
- **`dekspec doctor --json --at .` fails** — abort before fan-out.
- **Malformed lens pack** — stops the review before fan-out.

## Cross-references

- ADR-026 (review shape; operator-confirmed merge), ADR-055 (authority and escalation), ADR-057 (evidence, verdict binding and carry-forward), ADR-058 (delivery head review), ADR-062 (oracle judgment of amended or added acceptance assets).
- `/dekspec:land-intent` — sequences delivery verify → this review → `dekspec ib complete` → `dekspec delivery check` → operator-confirmed merge.
