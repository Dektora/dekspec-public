# REVIEW_IB lens pack

> 16 lenses for `/dekspec:review-ib` (INT-106). Each entry conforms to the schema in `plugins/dekspec/skills/_lib/review_lens_registry.md` (4 required fields: `question`, `input_slice`, `attack_patterns`, `severity_rubric`). The orchestration shell (INT-105 LOCKED) loads this file and fans out one specialist per lens.
>
> Source design substrate: `~/.claude/projects/-home-dfxop-projects-dekspec/memory/reference_review_pipeline_design.md` §"Lens design (per-stage)" REVIEW_IB table.

All 16 lenses share `severity_rubric: shared` (resolves to `plugins/dekspec/skills/_lib/review_confidence_rubric.md`). The orchestrator surface threshold is 80; any single lens at ≥80 confidence vetoes the verdict per ADR-026's asymmetric-voting contract.

---

## scope-creep

```yaml
- id: scope-creep
  question: |
    Does `IB.files_to_modify` include paths outside the union of the
    parent Intent's `components_affected` globs?
  input_slice: ib.files_to_modify + parent_intent.components_affected
  attack_patterns:
    - file path matches none of the parent Intent's component globs
    - file path is in a sibling Intent's components with no dependency edge
    - file is a generated artifact (.pyc / __pycache__ / build/) that should not be hand-edited
    - file is outside the project root entirely
  severity_rubric: shared
```

## sibling-ib-coherence

```yaml
- id: sibling-ib-coherence
  question: |
    Do any OTHER in-flight IBs under the same parent Intent modify a
    file this IB also modifies, while neither IB names the other in
    `depends_on` — i.e. would landing both produce a write-write
    conflict the dependency graph does not order?
  input_slice: ib.files_to_modify + ib.depends_on + sibling_ibs.*.files_to_modify + sibling_ibs.*.depends_on
  attack_patterns:
    - a sibling IB under the same parent modifies a file in this IB's file set, and neither IB names the other in depends_on
    - two sibling IBs rewrite the same module / surface with contradictory or independent designs (no shared contract, no ordering edge)
    - both sibling IBs declare depends_on: [] yet their edits to a shared file are order-sensitive
    - per-IB file partitioning looks clean, but the union of sibling edits collides on the same region of a shared file
  severity_rubric: shared
```

The `scope-creep` lens checks this IB against the *parent Intent's* component
globs; it is blind to *sibling IBs*. This lens closes that cross-IB coherence
gap (ds-review-ib-scope-creep-sibling-ib — surfaced by the review-ib live eval):
two siblings that each look in-scope can still collide when their file sets
overlap with no ordering edge between them.

## acceptance-falsifiability

```yaml
- id: acceptance-falsifiability
  question: |
    Is every `done-when` acceptance criterion machine-checkable (a
    shell command or a test assertion) rather than a prose judgment?
  input_slice: ib.done_when
  attack_patterns:
    - criterion uses subjective verbs (looks good, seems right, works correctly)
    - criterion has no concrete cmd or test reference
    - criterion is a tautology (X is Y because X is Y)
    - criterion depends on undefined external state
  severity_rubric: shared
```

## test-plan-coverage

```yaml
- id: test-plan-coverage
  question: |
    Is every acceptance criterion in `done-when` mapped to at least
    one test in `ib.test_plan`?
  input_slice: ib.done_when + ib.test_plan
  attack_patterns:
    - acceptance criterion N has no corresponding test entry
    - test_plan covers criteria but mentions nothing in done_when (drift)
    - test_plan is empty while done_when is non-empty
    - test_plan punts coverage to "existing tests" without naming them
  severity_rubric: shared
```

## dependency-readiness

```yaml
- id: dependency-readiness
  question: |
    Are the IBs this IB names in `depends_on` all at status
    `MERGED` or `LOCKED`?
  input_slice: ib.depends_on + audit_doctor.ib_statuses
  attack_patterns:
    - depends_on IB is at status DRAFT / PROPOSED / ACCEPTED / IMPLEMENTING
    - depends_on IB does not exist in the spec graph
    - depends_on points to a SUPERSEDED IB without naming the successor
    - dependency cycle: A depends_on B, B depends_on A
  severity_rubric: shared
```

## source-spec-fidelity

```yaml
- id: source-spec-fidelity
  question: |
    Are the IB's claims grounded in `source_aes` and the parent WS,
    or does the IB introduce architectural decisions not present in
    the upstream spec?
  input_slice: ib.body + parent_ws.acceptance + source_ae_paths.*.boundaries
  attack_patterns:
    - IB introduces an interface contract not declared by source_aes
    - IB asserts an invariant not present in parent_ws
    - IB cites an AE that does not exist
    - IB silently shifts a boundary the source AE pins
  severity_rubric: shared
```

## interface-depth

```yaml
- id: interface-depth
  question: |
    Is the implementation surface the IB describes (the public
    boundary its beads build out — function signatures, class APIs,
    module entry points) DEEP — a small, simple surface concentrating
    a large amount of implementation behavior — or SHALLOW: a surface
    nearly as complex as the implementation it fronts, leaking
    invariants, ordering, and error-handling onto callers (ADR-036 /
    Constitution Article 4)?
  input_slice: ib.body + parent_ws.acceptance + source_ae_paths.*.boundaries
  attack_patterns:
    - interface exposes many operations/methods where a few would compose to the same effect
    - operation has a long, branchy parameter list that pushes mode-selection onto the caller
    - pass-through / thin operation that adds no behavior over the layer it wraps
    - caller is forced to know internal ordering, invariants, or error states to use the surface correctly
    - surface is nearly as complex as the implementation it fronts (shallow-module smell)
  severity_rubric: shared
```

Per **ADR-036** (deep-modules design principle) + **Constitution Article 4**. A shallow interface is a smell: recommend deepening (hide more behind a smaller surface) or combining operations before the IB advances. Depth here is judgement, not a checkable predicate — surface the smell at ≥80 only when callers are demonstrably forced to absorb internal complexity.

## rollout-risk-plan

```yaml
- id: rollout-risk-plan
  question: |
    Does the IB declare a kill-switch, feature flag, or rollback
    plan commensurate with the blast radius of the change?
  input_slice: ib.body + ib.files_to_modify
  attack_patterns:
    - IB touches a load-bearing surface (auth, db migration, public API) with no rollback plan
    - IB declares a feature flag but no removal plan
    - IB asserts "low risk" without justifying against the file set
    - IB names a kill-switch but does not pin who flips it / when
  severity_rubric: shared
```

## ambiguity-audit

```yaml
- id: ambiguity-audit
  question: |
    Does the IB body contain vague verbs ("handle", "support",
    "improve"), unresolved pronouns ("it", "this"), or quantifier
    drift ("some", "various", "a few") that obscure the contract?
  input_slice: ib.body
  attack_patterns:
    - vague verb without an object (e.g., "handle errors" with no specifics)
    - unresolved "it"/"this" referring to something unnamed
    - quantifier without bound ("some files" — which? how many?)
    - sentence whose subject cannot be identified
  severity_rubric: shared
```

## constraint-completeness

```yaml
- id: constraint-completeness
  question: |
    Does the IB capture the performance, security, and concurrency
    constraints the change must respect, or are non-functional
    requirements absent?
  input_slice: ib.body + parent_ws.acceptance + source_ae_paths.*.boundaries
  attack_patterns:
    - IB touches a hot path but declares no perf budget
    - IB modifies a security-sensitive surface (auth, secrets) with no security note
    - IB introduces concurrency without naming the consistency model
    - parent_ws pins a constraint the IB body silently relaxes
  severity_rubric: shared
```

## glossary-discipline

```yaml
- id: glossary-discipline
  question: |
    Does the IB introduce any Title-Case domain terms that are not
    defined in `dekspec/domain-glossary.md`?
  input_slice: ib.body + glossary + audit_doctor.l10_findings
  attack_patterns:
    - Title-Case term in IB body has no glossary entry (L10 hit)
    - IB redefines an existing glossary term with a different meaning (drift)
    - IB uses a deprecated term flagged in the glossary
    - IB uses a term whose canonical form differs from the IB's casing
  severity_rubric: shared
```

## bead-coverage

```yaml
- id: bead-coverage
  question: |
    Is every IB acceptance criterion (`done-when`) covered by at
    least one bead in the bead decomposition?
  input_slice: ib.done_when + bead_decomposition
  attack_patterns:
    - acceptance criterion N has no bead claiming to satisfy it
    - bead claims to satisfy a criterion that does not exist in done_when
    - bead acceptance is broader than any single done_when entry (vague mapping)
    - bead set, taken as a union, leaves a gap against done_when
  severity_rubric: shared
```

## bead-granularity

```yaml
- id: bead-granularity
  question: |
    Are the beads sized appropriately — neither so large they would
    obscure failure modes nor so small they decompose past
    coherence?
  input_slice: bead_decomposition + ib.body
  attack_patterns:
    - single bead claims to ship the entire IB (too large)
    - bead would require >2 hours of focused work (too large)
    - bead is a single-line edit (too small unless coordinating)
    - beads carve along incidental rather than architectural seams
  severity_rubric: shared
```

## bead-dependency-graph

```yaml
- id: bead-dependency-graph
  question: |
    Does the bead `depends_on` graph form a DAG with no cycles,
    and is the topological order respected by the proposed
    execution sequence?
  input_slice: bead_decomposition
  attack_patterns:
    - cycle: bead A depends_on B which depends_on A (transitively)
    - bead depends on a non-existent bead ID
    - execution order in the IB contradicts the depends_on DAG
    - bead depends on a closed bead from a prior IB without naming the carryover
  severity_rubric: shared
```

## outcome-tdd-discipline

```yaml
- id: outcome-tdd-discipline
  question: |
    Does the parent Intent declare an `outcome_verification` block,
    and does git-blame show the outcome-test file's first commit
    landed BEFORE the implementation files' first commits (strong-TDD
    timing) per ADR-029?
  input_slice: parent_intent.outcome_verification + git_history.first_commit_per_file
  attack_patterns:
    - parent Intent lacks an outcome_verification declaration
    - outcome-test file's first commit is AFTER the implementation file's first commit
    - outcome-test file modified together with the implementation in the same commit (not red-first)
    - elaborate-fixture outcome test that exercises scaffolding rather than the change (per ADR-029)
    - other test files modified to make the outcome test pass (collateral edits)
  severity_rubric: shared
  tdd_discipline_lens: true
```

Per **INT-120** (Slice C peel-off of INT-112 per ADR-028). This lens fires the strong-TDD check ADR-029 commits the system to; the rule body (`T-VERIFICATION-OUTCOME`) is the audit-time mirror surfaced by INT-119.

## bead-to-ib-fidelity

```yaml
- id: bead-to-ib-fidelity
  question: |
    Does the bead set faithfully implement the IB's contract per
    `/write-code-beads --audit`, or does it carry drift?
  input_slice: audit_doctor.write_beads_audit_findings + bead_decomposition
  attack_patterns:
    - /write-code-beads --audit reports drift between IB body and bead claims
    - bead acceptance contradicts IB acceptance
    - bead introduces a surface IB does not declare
    - bead silently omits an IB-declared deliverable
  severity_rubric: shared
```

---

## Cross-references

- ADR-026 (parent decision).
- ADR-036 + Constitution Article 4 (deep-modules principle — source of the `interface-depth` lens).
- `plugins/dekspec/skills/_lib/review-orchestration.md` (the shell that loads this pack).
- `plugins/dekspec/skills/_lib/review_lens_registry.md` (the schema this pack conforms to).
- `plugins/dekspec/skills/_lib/review_confidence_rubric.md` (the canonical `severity_rubric: shared` target).
- INT-120 (Slice C of INT-112 peel-off — will add a 14th lens to this pack: outcome-test + strong-TDD discipline).
