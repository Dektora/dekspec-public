# REVIEW_PR lens pack

> 9 lenses for `/dekspec:review-pr` (INT-107). Each entry conforms to the schema in `plugins/dekspec/skills/_lib/review_lens_registry.md` (4 required fields). The orchestration shell (INT-105 LOCKED) loads this file and fans out one specialist per lens.
>
> Source design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Lens design (per-stage)" REVIEW_PR table.

All 9 lenses share `severity_rubric: shared` (resolves to `plugins/dekspec/skills/_lib/review_confidence_rubric.md`). Surface threshold 80. Asymmetric voting per ADR-026.

---

## claude-md-compliance

```yaml
- id: claude-md-compliance
  question: |
    Does the diff violate any standing rule pinned in `CLAUDE.md`
    (no specless edits, branch discipline, never-edit-locked-artifacts,
    domain-glossary discipline, cross-repo discipline)?
  input_slice: pr.diff + claude_md
  attack_patterns:
    - diff edits a LOCKED artifact under dekspec/ without an --unlock cycle
    - diff edits source under tooling/dekspec/ with no spec context
    - diff modifies files outside Dektora/dekspec from a library session
    - diff introduces a Title-Case domain term absent from dekspec/domain-glossary.md
    - diff bypasses CLAUDE.md's "never change status to LOCKED without --lock flag" rule
  severity_rubric: shared
```

## done-when-satisfied

```yaml
- id: done-when-satisfied
  question: |
    Does the diff actually satisfy every `done-when` acceptance
    criterion in the IB it claims to implement?
  input_slice: pr.diff + pr.files_changed + ib.done_when
  attack_patterns:
    - done_when criterion N has no corresponding change in the diff
    - diff implements something not declared in done_when (scope creep)
    - done_when criterion is satisfied only by a TODO comment / stub
    - done_when references a test that the diff does not add
  severity_rubric: shared
```

## diff-scope-vs-ib

```yaml
- id: diff-scope-vs-ib
  question: |
    Are all files in `pr.files_changed` within the union of
    `ib.files_to_modify` globs?
  input_slice: pr.files_changed + ib.files_to_modify
  attack_patterns:
    - file in diff is outside every files_to_modify glob
    - file in files_to_modify has no change in the diff (unfinished work)
    - diff touches a generated artifact (.pyc, build/, node_modules/) that should be excluded
    - diff modifies a load-bearing surface (CLAUDE.md, audit profiles) without IB declaring it
  severity_rubric: shared
```

## bug-scan

```yaml
- id: bug-scan
  question: |
    Does the diff introduce a correctness, security, or
    concurrency bug visible from the diff hunks?
  input_slice: pr.diff
  attack_patterns:
    - off-by-one / boundary error in a loop or slice
    - missing null/None / empty-list guard before deref
    - SQL / shell / path injection on un-sanitized input
    - race condition: shared mutable state without synchronization
    - resource leak: file/connection/lock acquired without paired release
    - swallowed exception that masks an underlying failure
  severity_rubric: shared
```

## test-plan-execution

```yaml
- id: test-plan-execution
  question: |
    Did the diff include the test additions the IB's `test_plan`
    promised, and do they exercise the production change?
  input_slice: pr.diff + ib.test_plan + pr.files_changed
  attack_patterns:
    - test_plan entry N has no corresponding test in the diff
    - new test exists but only asserts the change is callable (smoke without coverage)
    - test mocks out the very behavior under test
    - tests added but production code path is untouched (false coverage)
  severity_rubric: shared
```

## audit-rule-preflight

```yaml
- id: audit-rule-preflight
  question: |
    Does `dekspec audit linkage --at .` come back clean (no P0/P1
    findings) at the PR's head SHA?
  input_slice: audit_doctor.linkage_findings
  attack_patterns:
    - P0 finding present on any artifact the diff touches
    - P1 finding present on any artifact the diff touches
    - diff introduces a new artifact that violates L-series linkage (e.g. WS without governing AE)
    - diff edits an artifact in a way that introduces a T-series structural defect
  severity_rubric: shared
```

## doc-changelog-entry

```yaml
- id: doc-changelog-entry
  question: |
    For a user-visible change, does the diff include a CHANGELOG
    entry + appropriate doc updates, or is the change silent?
  input_slice: pr.diff + pr.files_changed
  attack_patterns:
    - new CLI verb / skill / flag with no CHANGELOG entry
    - user-facing behavior change with no doc / README update
    - schema change with no migration note
    - CHANGELOG entry present but vague ("misc improvements") without naming what changed
  severity_rubric: shared
```

## spec-mode-discipline

```yaml
- id: spec-mode-discipline
  question: |
    Does the diff modify source code without a corresponding
    update to its governing spec artifact (Intent / WS / IC / IB),
    violating CLAUDE.md's "No Specless Edits" guardrail?
  input_slice: pr.diff + pr.files_changed + audit_doctor.spec_coverage
  attack_patterns:
    - source file edited but no dekspec/ artifact touched in same PR
    - source file edited and a dekspec/ artifact is touched, but the artifact's claims do not cover the edit
    - new module added with no governing Intent declaring it
    - bug fix lands without an Amendment Log entry on the spec it implements
  severity_rubric: shared
```

## git-blame-prior-pr

```yaml
- id: git-blame-prior-pr
  question: |
    Does git history on the touched surfaces reveal institutional
    context (prior PRs, prior bug fixes, prior revert) the PR
    author appears unaware of and that contradicts the current
    change?
  input_slice: git_history + pr.diff
  attack_patterns:
    - prior commit on the same line block was a revert; this PR re-introduces the reverted change
    - prior PR's commit message warned against the pattern this PR introduces
    - file was recently touched by a different IB the PR does not reference
    - touched function was added by an Intent that the current IB does not link to (orphaned dependency)
  severity_rubric: shared
```

---

## Cross-references

- ADR-026 (parent decision).
- ADR-025 (LOCKED — IB-aggregate PR convention this lens pack reviews against).
- `plugins/dekspec/skills/_lib/review-orchestration.md` (the shell that loads this pack).
- `plugins/dekspec/skills/_lib/review_lens_registry.md` (the schema this pack conforms to).
- `plugins/dekspec/skills/_lib/review_confidence_rubric.md` (the canonical `severity_rubric: shared` target).
