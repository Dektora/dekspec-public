---
name: review-pr
description: Post-implementation review of an IB-aggregate PR diff against the IB it claims to implement. Use when an IB has all beads CLOSED, the IB-branch CI is green, the IB-aggregate PR is open, and the operator wants a non-sycophantic verdict before merge.
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
mode: lite
allowed-tools: Read Grep Glob Bash Agent
argument-hint: [--help] <PR-#>
---

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:review-pr"
one_line: "Post-implementation review of an IB-aggregate PR diff against the IB it claims to implement."
modes:
  - { flag: "", args: "<PR-#>", description: "Review the PR diff against its parent IB; emit MERGE / NO-MERGE / INSUFFICIENT_EVIDENCE verdict." }
  - { flag: "--help", args: "", description: "Show this manifest." }
examples:
  - "/dekspec:review-pr 42"
```

# /dekspec:review-pr <PR-#>

> Post-implementation review of an IB-aggregate Pull Request. Loads `plugins/dekspec/skills/_lib/review-orchestration.md` (INT-105, LOCKED) with the REVIEW_PR lens pack (`plugins/dekspec/skills/review-pr/lenses.md`) and emits a structured GO / NO-GO / INSUFFICIENT_EVIDENCE verdict against the IB the PR claims to implement. Per **ADR-026** (LOCKED 2026-05-29).

This skill is the post-impl half of the two-tier review pipeline (sibling of `/dekspec:review-ib`, INT-106). Both consume the same shared orchestration shell; REVIEW_PR differs in lens pack + input bundle (diff-shaped, not spec-shaped) + output target.

## When this skill fires

REVIEW_PR auto-fires on IB state-entry to `REVIEW_PR` — typically the conjunction of (a) every bead in the IB's decomposition is CLOSED, (b) the IB-branch CI is green, (c) the IB-aggregate PR to main is open. The action-handler framework (INT-108) dispatches this skill on that transition. Operators may invoke it manually with an explicit `<PR-#>` at any time.

The verdict is **RECOMMEND-only at landing**: orchestrator emits + writes sidecar, IB state machine does not auto-advance. Operator triggers the advance to MERGED manually. MIXED / AUTO modes (INT-118) auto-advance once a calibration corpus accumulates (INT-117) and per-lens silver/gold thresholds are operator-committed.

## Pre-flight: is this PR too large to review reliably?

Before fanning out the lenses, check the PR diff size. The review-fix loop (and the lens attack) degrade on a large diff — both the reviewer and the fixing agent lose accuracy past a few hundred changed lines. If the PR is too large to review reliably, **stop and recommend a split** (one reviewable IB-aggregate per concern) rather than running a low-confidence review over thousands of lines. The size signal also sets the `<effort>` for the seeding `/code-review` step in the fail loop (below): `medium` for a small diff, `high`/`max` for a dense one.

## Pairing with the review-fix loop (REVIEW_PR_FAIL)

A NO-GO verdict transitions the IB to `REVIEW_PR_FAIL`, whose handler (`plugins/dekspec/skills/_lib/handlers/review_pr_fail.md`) drives a **review-fix loop**. That loop **seeds** itself by running `/code-review <effort> --comment <PR-#>` first — posting line-anchored findings as inline PR comments — so the fixer has concrete, located feedback alongside this skill's sidecar verdict. It then fixes only real/relevant findings (read the diff first, no unrelated rewrites, a test per fix), lands follow-up commits, and re-fires `/dekspec:review-pr <PR-#>` until the verdict is GO or a human decision is needed. RECOMMEND-only at landing.

## Invocation

```
/dekspec:review-pr <PR-#>
```

`<PR-#>` is the GitHub / GitLab pull-request number. The skill resolves the PR's diff + the IB it claims to implement from the PR body (the IB-aggregate PR convention per ADR-025 requires a `Resolves IB-NNN` header line).

Optional flags:

- `--mode <RECOMMEND|MIXED|AUTO>` — override `.dekspec/config.yaml` `review.mode` for this run.
- `--sidecar-dir <path>` — override sidecar output directory. Default: `dekspec/reviews/`.
- `--lens-pack <path>` — override the REVIEW_PR lens pack.
- `--ib-id <ID>` — bypass PR-body parsing and pin the IB explicitly (rare; lens-dev use).

## Input bundle

| Slot | Source |
|---|---|
| `pr.diff` | Full unified diff of the IB-aggregate PR. |
| `pr.body` | The PR description, for `Resolves IB-NNN` extraction. |
| `pr.files_changed` | List of files touched. |
| `pr.commits` | Per-commit messages + SHAs. |
| `ib.body` | The IB this PR claims to implement. |
| `ib.done_when` | The IB's acceptance criteria, for the done-when-satisfied lens. |
| `ib.files_to_modify` | The IB's declared file globs, for the diff-scope-vs-ib lens. |
| `ib.test_plan` | The IB's test plan, for the test-plan-execution lens. |
| `claude_md` | `CLAUDE.md` content, for the claude-md-compliance lens. |
| `audit_doctor` | Cached `dekspec audit doctor --json --at .` snapshot at the PR's head SHA. |
| `git_history` | Recent `git log` + `git blame` on touched surfaces, for the git-blame-prior-pr lens. |

The orchestration shell pulls these once and caches; each lens sees only its declared slice.

## Output: sidecar review file

Sidecar at `dekspec/reviews/<IB-ID>-review-pr-<UTC-timestamp>.md` (distinct from REVIEW_IB sidecars by the `-pr-` infix). Carries verdict + vetoing lenses + surfaced findings (≥80) + abstaining lenses + audit-doctor snapshot SHA + run timestamp + PR-head SHA.

Structured verdict persisted to the SQLite flywheel (INT-109): `dekspec.review.db.write_verdict(verdict)`.

## Audit-doctor cache reuse

REVIEW_PR leans heavily on `dekspec audit doctor --json --at .` output — the audit-rule-preflight lens consumes it directly, the spec-mode-discipline lens consumes a slice, the doc-changelog-entry lens cross-references it. The orchestration shell runs `dekspec audit doctor --json --at .` exactly once per review session and caches; lenses whose `input_slice` declares `audit_doctor.<path>` consume the cached snapshot rather than re-deriving. A lens that re-walks the source tree to compute what audit-doctor already exposes fails the schema lint at load time.

## Lens pack

The 9 REVIEW_PR lenses live in `plugins/dekspec/skills/review-pr/lenses.md`:

- **Spec ↔ diff fidelity** — done-when-satisfied, diff-scope-vs-ib, test-plan-execution.
- **Source quality** — bug-scan, claude-md-compliance.
- **Operational gates** — audit-rule-preflight, doc-changelog-entry, spec-mode-discipline.
- **Institutional memory** — git-blame-prior-pr.

Each conforms to `plugins/dekspec/skills/_lib/review_lens_registry.md` (4 required fields).

## Verdict semantics

Asymmetric voting per ADR-026: any single lens at the surface threshold (≥80, per `review_confidence_rubric.md`) NO-GO's the verdict regardless of other lenses' scores. No weighted-average override.

- **GO** — every lens <80, no abstentions.
- **NO-GO** — at least one lens at ≥80. Sidecar names vetoing lens(es) + findings.
- **INSUFFICIENT_EVIDENCE** — no lens ≥80 AND at least one lens explicitly abstained.

## Failure modes

- **PR not found / IB unresolvable** — skill aborts before fan-out with a clear error. The PR body must include `Resolves IB-NNN` per ADR-025 convention, OR the operator must pass `--ib-id`.
- **Audit-doctor unavailable** — skill aborts before fan-out (multiple lenses depend on the cache).
- **Lens-pack load failure** — orchestrator raises at load time on schema violation.

## Cross-references

- ADR-026 (load-bearing decision).
- ADR-025 (LOCKED — IB-aggregate PR convention this skill consumes).
- AE-006 (Skills Library — host AE).
- INT-105 (LOCKED — shared orchestration shell).
- INT-106 (sibling — `/dekspec:review-ib`, pre-impl half).
- INT-108 (action-handler framework — dispatches this skill on IB state-entry to `REVIEW_PR`).
- INT-109 (flywheel persistence — SQLite schema this skill writes verdicts into).
- Design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Lens design (per-stage)" REVIEW_PR table.
