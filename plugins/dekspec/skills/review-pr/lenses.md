# REVIEW_PR lens pack

> 13 lenses for `/dekspec:review-pr` — the post-implementation review of a delivery at its head, judged per IB (ADR-058). Each entry conforms to the schema in `plugins/dekspec/skills/_lib/review_lens_registry.md` (4 required fields). The orchestration shell (`_lib/review-orchestration.md`) loads this file and fans out one specialist per lens.

All 13 lenses share `severity_rubric: shared` (resolves to `plugins/dekspec/skills/_lib/review_confidence_rubric.md`). Surface threshold 80. Asymmetric voting per ADR-026.

---

## acceptance-satisfied

```yaml
- id: acceptance-satisfied
  question: |
    Beyond passing their named checks, does the diff actually achieve the
    observable behavior each acceptance condition states — and does every
    `review:` condition hold?
  input_slice: delivery.diff + ib.body + evidence.results
  attack_patterns:
    - a condition's check passes against a stub, a hard-coded value or a special case for the test input
    - the named test asserts something weaker than the condition states
    - a review condition's property is not established by the diff
    - the Outcome is only partly delivered although every check is green
  severity_rubric: shared
```

## obligation-fidelity

```yaml
- id: obligation-fidelity
  question: |
    Does the diff honor every binding obligation as its canonical text in
    the generated execution context states it (ADR-055) — architecture,
    interface semantics, security, compatibility, resource bounds?
  input_slice: delivery.diff + ib.context
  attack_patterns:
    - the diff contradicts a referenced ADR, IC or WS section
    - an interface pinned by an IC changes shape, error semantics or ordering
    - a compatibility or security obligation is weakened by a new code path
    - the implementation re-decides something an obligation settles, citing its own judgment
  severity_rubric: shared
```

## scope-and-protected-surfaces

```yaml
- id: scope-and-protected-surfaces
  question: |
    Does every changed file fall inside the delivery's allowed Scope with
    no Protected Surface modified, renamed or deleted — and does the
    engine's scope check agree?
  input_slice: delivery.files_changed + ib.body + evidence.scope
  attack_patterns:
    - a changed file lies outside every co-delivered IB's Scope
    - a protected path or `path::symbol` is modified, renamed or deleted
    - the scope check reports a violation or an indeterminate result
    - generated or vendored output is hand-edited
  severity_rubric: shared
```

## spec-impact

```yaml
- id: spec-impact
  question: |
    Does the delivery update every specification its IBs name in `Spec
    impact`, and does it change architecture or a contract that no `Spec
    impact` declares (ADR-056 §4)?
  input_slice: delivery.diff + delivery.files_changed + ib.body + audit_doctor.spec_coverage
  attack_patterns:
    - a Spec impact artifact is not modified by the delivery
    - the diff changes a component boundary or interface described by an AE or IC with Spec impact none
    - source changes fall under no IB in the delivery (ungoverned change)
    - a spec update contradicts the code it describes
  severity_rubric: shared
```

## cross-ib-integration

```yaml
- id: cross-ib-integration
  question: |
    In a multi-IB delivery, does one IB's change break, bypass or
    contradict another IB's obligations or acceptance, and does every
    shared shape follow its single pinned home?
  input_slice: delivery.diff + delivery.ibs + delivery.integration
  attack_patterns:
    - two IBs define the same shared shape differently, or one bypasses the pinned home
    - an IB changes a surface another co-delivered IB protects
    - the integration command failed or does not exercise the interaction between the IBs
    - defensive aliasing or shims make integration pass over incompatible definitions (ADR-054 qualification b)
  severity_rubric: shared
```

## acceptance-integrity

```yaml
- id: acceptance-integrity
  question: |
    Was the meaning of acceptance preserved — no condition weakened,
    skipped, deselected or reinterpreted — and is every attention item
    (amendment, acceptance asset first created during execution, runner-
    input change) justified before it is acknowledged? For each amended or
    added acceptance asset, is the expectation basis of every new or changed
    assertion independent of the implementation — a cited worked example,
    an independently established fixture, an external reference or a
    property justified from the contract — and does it represent the
    required behavior (ADR-062)?
  input_slice: ib.body + evidence.attention + evidence.integrity_problems + record.amendments + acceptance.test_sources + delivery.diff
  attack_patterns:
    - an amendment weakens a condition without a reason an independent reviewer would accept
    - an acceptance asset created during execution tests less than the condition states
    - an amended or added acceptance assertion takes its expected value from the system under test, its helpers or its constants (a system-derived expectation) — blocking
    - an amended or added acceptance assertion repeats the implementation's derivation (a copied derivation) or blesses observed output with no recorded source (a blessed observation) — blocking
    - an amended or added acceptance assertion has no `Basis:` line, or an amendment changed a `Basis:` line without a reason
    - an amended `command:` condition's pass criterion is something the change itself controls (a string it prints, a count it computes) — blocking
    - a runner-input change (pytest configuration, conftest) alters what an acceptance test means
    - a test mocks out the very behavior it claims to verify
    - skip, xfail, deselect or collection tricks around an acceptance node
  severity_rubric: shared
```

An attention item is acknowledged (`dekspec ib review … --acknowledge`) only after this judgment: a system-derived expectation, a copied derivation or a blessed observation in an amended or added asset, or an amended `command:` criterion the change itself controls, is a finding at ≥80, so the verdict is FAIL. Unchanged acceptance assets were oracle-reviewed before the baseline (the IB's `Floor reviewed:` row, ADR-062); this lens judges what changed after it.

## deviation-review

```yaml
- id: deviation-review
  question: |
    Are the recorded deviations — unplanned in-scope files, departures from
    the implementation hypothesis — ordinary engineering judgment, or do
    any quietly cross a line that required escalation (ADR-055): a binding
    obligation, a protected surface, an acceptance condition, or product
    scope?
  input_slice: record.deviations + record.plan_findings + delivery.diff + ib.body
  attack_patterns:
    - a deviation changes behavior an obligation binds while being recorded as a mere file departure
    - the implementation expands product scope beyond the Outcome
    - an unresolved contradiction between obligations was settled silently instead of escalated
    - plan findings name a material uncertainty the diff never resolves
  severity_rubric: shared
```

## outcome-tdd-history

```yaml
- id: outcome-tdd-history
  question: |
    Were the acceptance tests red-first (ADR-029, as revised by ADR-057)?
    When commit history exists, did each acceptance test file's first
    commit land BEFORE the implementation files' first commits? For squash
    or no-intermediate-commit workflows, is there equivalent evidence — the
    test assets hashed in the pre-execution acceptance baseline of the
    execution record?
  input_slice: ib.body + git_history.first_commit_per_file + record.baselines
  attack_patterns:
    - history exists and an acceptance test file's first commit is AFTER the implementation file's first commit
    - an acceptance test first appears in the same commit as the implementation with no pre-execution baseline covering it
    - a squash workflow is claimed but the baseline shows the acceptance assets absent before the run started
    - other test files modified to make the acceptance tests pass (collateral edits)
  severity_rubric: shared
  tdd_discipline_lens: true
```

The commit-ordering half of the strong-TDD gate (DSF-014); `outcome-tdd-discipline` in the REVIEW_IB pack proves test-first from workspace evidence before history exists. An asset first created during execution is also an attention item the verdict must acknowledge.

## bug-scan

```yaml
- id: bug-scan
  question: |
    Does the diff introduce a correctness, security or concurrency bug
    visible from the diff hunks?
  input_slice: delivery.diff
  attack_patterns:
    - off-by-one / boundary error in a loop or slice
    - missing None / empty guard before dereference
    - SQL / shell / path injection on unsanitized input
    - race condition on shared mutable state
    - resource leak (file, connection, lock) without paired release
    - swallowed exception that masks an underlying failure
  severity_rubric: shared
```

## claude-md-compliance

```yaml
- id: claude-md-compliance
  question: |
    Does the diff violate a standing rule pinned in `CLAUDE.md` (no
    specless edits, branch discipline, never-edit-locked-artifacts,
    glossary discipline, cross-repo discipline)?
  input_slice: delivery.diff + claude_md
  attack_patterns:
    - diff edits a LOCKED artifact (ADR, IC, SP, SV, Constitution) without its unlock cycle
    - diff edits source that no IB in the delivery governs
    - diff modifies files outside this repository from a library session
    - diff introduces a Title-Case domain term absent from dekspec/domain-glossary.md
    - diff hand-edits a status the engine owns (an IB COMPLETE not written by `dekspec ib complete`)
  severity_rubric: shared
```

## audit-rule-preflight

```yaml
- id: audit-rule-preflight
  question: |
    Does the cached audit come back without P0/P1 findings on the
    artifacts the delivery touches, at the head?
  input_slice: audit_doctor.linkage_findings
  attack_patterns:
    - P0 finding on any artifact the diff touches
    - P1 finding on any artifact the diff touches
    - the diff adds an artifact that violates L-series linkage
    - the diff introduces a T-series structural defect
  severity_rubric: shared
```

## doc-changelog-entry

```yaml
- id: doc-changelog-entry
  question: |
    For a user-visible change, does the delivery include a CHANGELOG entry
    and the doc updates it needs, or is the change silent?
  input_slice: delivery.diff + delivery.files_changed
  attack_patterns:
    - new CLI verb, skill or flag with no CHANGELOG entry
    - user-facing behavior change with no doc / README update
    - schema change with no migration note
    - CHANGELOG entry too vague to say what changed
  severity_rubric: shared
```

## git-blame-prior-pr

```yaml
- id: git-blame-prior-pr
  question: |
    Does history on the touched surfaces reveal context (prior fixes,
    reverts, warnings) the delivery appears unaware of and contradicts?
  input_slice: git_history + delivery.diff
  attack_patterns:
    - the delivery re-introduces a change a prior commit reverted
    - a prior commit message warned against the pattern this delivery introduces
    - the file was recently changed by another IB this delivery does not reference
    - the touched code serves an obligation of an IB the delivery does not account for
  severity_rubric: shared
```

---

## Cross-references

- ADR-026 (review shape), ADR-054 (shared shapes), ADR-055 (authority and escalation), ADR-056 (spec impact, one home per fact), ADR-057 (evidence, attention items, verdict binding), ADR-058 (delivery head review), ADR-062 (the expectation basis judged before an amended or added acceptance asset is acknowledged).
- `_lib/review-orchestration.md` (the shell), `_lib/review_lens_registry.md` (the schema), `_lib/review_confidence_rubric.md` (`severity_rubric: shared`).
