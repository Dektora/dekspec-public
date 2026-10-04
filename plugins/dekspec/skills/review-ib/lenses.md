# REVIEW_IB lens pack

> 17 lenses for `/dekspec:review-ib` — the pre-execution review of an IB contract and, before authorization, of its acceptance floor (ADR-062). Each entry conforms to the schema in `plugins/dekspec/skills/_lib/review_lens_registry.md` (4 required fields: `question`, `input_slice`, `attack_patterns`, `severity_rubric`). The orchestration shell (`_lib/review-orchestration.md`) loads this file and fans out one specialist per lens.

All 17 lenses share `severity_rubric: shared` (resolves to `plugins/dekspec/skills/_lib/review_confidence_rubric.md`). Surface threshold 80; any single lens at ≥80 vetoes the verdict (ADR-026).

---

## content-classification

```yaml
- id: content-classification
  question: |
    Is every statement in the IB classified by meaning (ADR-055) — binding
    obligations in Obligations / Protected Surfaces / Scope, acceptance in
    the Acceptance block, and revisable guesses in the Implementation
    Hypothesis — so that no guess binds and no real contract is left
    revisable?
  input_slice: ib.body + ib.obligations + ib.protected_surfaces + ib.scope + ib.hypothesis + ib.header
  attack_patterns:
    - a suggested file list, insertion point, sequence or algorithm is written as an obligation or protected surface with no compatibility, security or ownership reason
    - a real contract (interface semantics, compatibility, security, a module other code depends on) sits only in the Implementation Hypothesis where the agent may revise it
    - an obligation restates an acceptance condition, or an acceptance condition hides an implementation choice ("uses library X") that is not a demonstrable outcome
    - Scope is a list of exact files copied from the hypothesis rather than the area the change may legitimately touch
    - the Authority policy header is missing, or says delegated while the body keeps legacy Files to Modify / Constraints & Decisions sections as binding
  severity_rubric: shared
```

## obligation-references

```yaml
- id: obligation-references
  question: |
    Are binding obligations referenced to their one canonical home (ADR,
    IC, WS, SP, AE, Constitution) rather than copied, and does every
    reference resolve to an in-force source eligible under DekSpec's project reference policy in the generated
    execution context?
  input_slice: ib.obligations + ib.context + ib.lint
  attack_patterns:
    - an obligation paraphrases or pastes text owned by an ADR, IC or WS instead of referencing it (a second copy that will drift)
    - "`dekspec ib context` or `dekspec ib lint` reports an unresolved reference, a missing section, or a SUPERSEDED / DEPRECATED source or one disallowed by DekSpec's project reference policy"
    - a section reference names a heading that does not exist in the source
    - a `(local)` obligation states something whose canonical home is an existing ADR or IC
    - a decision the IB depends on has no canonical home at all and is neither local nor referenced (underdefined contract)
  severity_rubric: shared
```

## spec-impact

```yaml
- id: spec-impact
  question: |
    If the outcome changes architecture or a contract, does the IB name
    the governing specifications in `Spec impact` so verification can
    require the delivery to update them (ADR-056 §4)?
  input_slice: ib.header + ib.outcome + ib.scope + ib.obligations + source_ae_paths
  attack_patterns:
    - the change alters a component boundary, responsibility or data flow described by an AE but Spec impact is none
    - the change alters an interface or shape pinned in an IC or WS but Spec impact does not name it
    - Spec impact names an artifact outside the change's reach, or a LOCKED artifact without the unlock/version path the change would need
    - Scope does not include the spec files that Spec impact says must change
  severity_rubric: shared
```

## slice-and-pin-routing

```yaml
- id: slice-and-pin-routing
  question: |
    Is the IB a vertical slice, and is any shape it shares with sibling
    IBs routed by ADR-054's three branches — an Interface Contract for a
    real cross-component boundary, a pin with one home (an IC, a WS, or
    one IB's local obligation referenced as `IB-NNN §O-n`), or a
    bar-clearing foundation IB — rather than copied or absorbed?
  input_slice: ib.outcome + ib.obligations + ib.header + sibling_ibs
  attack_patterns:
    - the IB is a horizontal layer (types, schema or utilities only) that fails the foundation bar (two real dependents, no logic, reviewable alone)
    - two IBs each state the same shared shape locally instead of one home referenced by both
    - a later IB consumes a shape the first IB defines without a Depends on edge (absorbed sequencing, rejected by ADR-054)
    - a shared shape crosses independently built components but is pinned in an IB instead of an Interface Contract
  severity_rubric: shared
```

## acceptance-falsifiability

```yaml
- id: acceptance-falsifiability
  question: |
    Does every acceptance condition state an observable behavior and name
    exactly one verification (test nodes, a command, or an independent
    review judgment), with each mandatory property separately verifiable?
  input_slice: ib.acceptance
  attack_patterns:
    - a condition uses subjective verbs (works correctly, looks good) with no observable outcome
    - one condition bundles several mandatory properties so a partial implementation could pass it
    - a pytest verification names a file or class instead of the nodes that prove the behavior, or a node that cannot fail for the stated reason
    - a command verification exits 0 regardless of the behavior (echo, `|| true`, grep for a string the author controls)
    - a review condition is used where a deterministic check was possible, or states nothing a reviewer can establish
  severity_rubric: shared
```

## acceptance-coverage

```yaml
- id: acceptance-coverage
  question: |
    Taken together, do the acceptance conditions demonstrate the Outcome —
    including integrated behavior through the real entry point and failure
    behavior — rather than only the happy path of internal units?
  input_slice: ib.outcome + ib.acceptance + ib.obligations
  attack_patterns:
    - part of the Outcome has no condition that would fail if it were missing
    - no condition exercises the real entry point (CLI verb, API route, skill invocation) the change is reached through
    - no condition covers the failure behavior (missing, invalid or unavailable input) the change must handle
    - a binding obligation that is observable (an error code, a compatibility promise) is never demonstrated
  severity_rubric: shared
```

## outcome-tdd-discipline

```yaml
- id: outcome-tdd-discipline
  question: |
    Does the floor report prove test-first at this pre-authorization stage
    (ADR-029 as revised by ADR-062) — every named acceptance node exists,
    every new node is genuinely RED (its assertion fired on the intended
    behavior, not an import, collection, missing-symbol, setup or usage
    failure, in-process or from a command it runs), every preserved node
    passes, and the production behavior they target is still ABSENT (at most
    a behavior-free surface skeleton) — and, for a parent Intent, is its
    outcome_verification declared?
  input_slice: ib.acceptance + workspace.acceptance_test_run + workspace.production_tree_absence + parent.outcome_verification
  attack_patterns:
    - a new node's failure kind in the floor report is anything but genuine-red (passed, import-error, missing-symbol, usage-exit, collection-error, setup-error, skipped, xfail, deselected, not-collected)
    - a genuine-red failure line shows the assertion fired only because a command the test runs rejected its arguments or could not import its code
    - a preserved node fails, or a node the IB changed is classified preserved
    - a named acceptance node or declared asset does not exist yet (acceptance tests are mandatory before authorization, never left to the builder)
    - the production behavior the acceptance tests target already exists in the working tree beyond a behavior-free skeleton
    - a parent Intent lacks an outcome_verification declaration
    - elaborate-fixture acceptance test that exercises scaffolding rather than the change (per ADR-029)
  severity_rubric: shared
  tdd_discipline_lens: true
```

Per ADR-029 (revised by ADR-057 — the outcome test is acceptance evidence — and by ADR-062 — red-first is an assertion failure, recorded by the acceptance runner rather than asserted) and DSF-014. Before execution there is no construction history, so this lens proves test-first from WORKSPACE evidence — the floor report of `dekspec ib floor` — not git-blame ordering; `outcome-tdd-history` in the REVIEW_PR pack checks ordering once history and the execution record exist.

## acceptance-oracle

```yaml
- id: acceptance-oracle
  question: |
    Per criterion, is the basis of each new assertion's expected result
    independent of the implementation, and does the assertion represent the
    behavior the condition requires (ADR-062)? Read the acceptance test
    sources, the surface skeleton and the floor report together: a basis
    that is a worked example cited from an approved obligation, an
    independently established fixture, an external reference, or an
    invariant or metamorphic property justified from the contract stands; an
    expectation that is system-derived, copied or blessed does not.
  input_slice: ib.acceptance + ib.obligations + acceptance.test_sources + acceptance.surface_skeleton + workspace.acceptance_test_run
  attack_patterns:
    - a system-derived expectation — the expected value is obtained by calling the system under test, its helpers or its constants (blocking)
    - a copied derivation — the test recomputes the expected value the way the implementation does, so a shared mistake passes (blocking)
    - a blessed observation — a literal recorded from observed output with no recorded source or independent check (blocking)
    - "an author-controlled `command:` criterion — the pass criterion in the condition text is a string the change itself prints or a count it computes (blocking)"
    - a new node with no basis, or only an inherited module or class basis where its own assertions need one
    - a basis that is independent but checks a weaker or different property than the condition states
    - the surface skeleton carries behavior, returns a non-neutral result or raises (NotImplementedError or any other) instead of letting the assertion fire
    - shared fixture plumbing or a test utility shares a mistake with the implementation that would let incorrect behavior pass
  severity_rubric: shared
```

Per ADR-062 §Two checks before the baseline. A finding in the first four patterns is **blocking**: score it at ≥80. Shared fixture plumbing, serialization helpers and test utilities are not defects by themselves; the question is whether a mistake they share with the implementation would let incorrect behavior pass. A property test stands when its property follows from the contract. Preservation nodes (the floor report's `preserved`) need no added basis. The lens may report a weak *requirement* as a finding; it never weakens one to fit an implementation. With no `pytest:` condition and no declared asset, the lens judges the `command:` criteria only.

**Recording a passing floor review (ADR-062).** When the review reaches GO and `dekspec ib floor <IB>` reports the floor OK, the review-ib shell — on behalf of the independent reviewer, never in the test author's context — appends to the IB's `## Amendment Log`:

`| <date> | Review | Floor reviewed: PASS — digest <64 hex> — <n> new nodes genuine red with a basis, <m> preserved passing (review-ib acceptance-oracle) | <reviewer identity> |`

`<64 hex>` is the floor digest the report states, `<n>` and `<m>` its new and preserved node counts. Nothing is written for a failing outcome: surfaced findings go to Open Issues as usual. The authorizer runs `dekspec ib accept` (or a pre-start `dekspec ib baseline`) only when the floor digest still matches the row — the command itself does not check it — and `/implement` readiness refuses an IB whose baseline digest no row names. After tests or contract change before the run starts, the floor is reviewed again and a new row is recorded.

## scope-and-protected-surfaces

```yaml
- id: scope-and-protected-surfaces
  question: |
    Is the allowed Scope coherent with the Outcome (and the parent Intent's
    components, if any), and do the Protected Surfaces name what must not
    change — remembering that a protected surface beats every scope
    allowance?
  input_slice: ib.outcome + ib.scope + ib.protected_surfaces + parent.components_affected
  attack_patterns:
    - a Scope glob reaches well beyond what the Outcome needs, or outside the parent Intent's components
    - the Outcome cannot be achieved without changing a file outside Scope or on a Protected Surface
    - a surface other code depends on (public API, shared schema, migration history) lies inside Scope with no protection or obligation
    - a Protected Surface is also something the Outcome must change (self-contradictory contract)
    - Scope covers generated or vendored output that must not be hand-edited
  severity_rubric: shared
```

## sibling-ib-coherence

```yaml
- id: sibling-ib-coherence
  question: |
    Do sibling IBs (same Parent or same delivery) overlap this IB's Scope
    or protect what it changes, with neither naming the other in
    Depends on — i.e. would executing both produce a conflict the
    dependency graph does not order?
  input_slice: ib.scope + ib.protected_surfaces + ib.header + sibling_ibs
  attack_patterns:
    - a sibling's Scope overlaps this IB's Scope on the same module and neither depends on the other
    - a sibling protects a surface this IB's Outcome must change
    - two siblings rewrite the same surface with independent designs and no shared contract
    - both declare no dependency yet their changes to a shared file are order-sensitive
  severity_rubric: shared
```

`scope-and-protected-surfaces` checks this IB alone; this lens closes the cross-IB gap (ds-review-ib-scope-creep-sibling-ib).

## dependency-readiness

```yaml
- id: dependency-readiness
  question: |
    Do the IBs named in Depends on exist, stay in force, and form an
    acyclic graph, so the engine can release this IB (`dekspec ib ready`)
    once they are COMPLETE?
  input_slice: ib.header + audit_doctor.ib_statuses
  attack_patterns:
    - a Depends on IB does not exist in the spec graph
    - a Depends on IB is SUPERSEDED or DEPRECATED without naming its successor
    - dependency cycle (A depends on B, B depends on A, directly or transitively)
    - a dependency is needed for a shared shape that ADR-054 routes to a pin instead (an unnecessary serialization)
  severity_rubric: shared
```

## interface-depth

```yaml
- id: interface-depth
  question: |
    Is the implementation surface the IB describes (its public boundary —
    function signatures, class APIs, module entry points) DEEP — a small,
    simple surface concentrating a large amount of behavior — or SHALLOW,
    leaking invariants, ordering and error handling onto callers
    (ADR-036 / Constitution Article 4)?
  input_slice: ib.outcome + ib.obligations + ib.hypothesis + source_ae_paths.*.boundaries
  attack_patterns:
    - interface exposes many operations where a few would compose to the same effect
    - operation has a long, branchy parameter list that pushes mode selection onto the caller
    - pass-through operation that adds no behavior over the layer it wraps
    - caller must know internal ordering, invariants or error states to use the surface correctly
    - surface is nearly as complex as the implementation it fronts
  severity_rubric: shared
```

Depth is judgement, not a checkable predicate — surface the smell at ≥80 only when callers are demonstrably forced to absorb internal complexity. A shallow hypothesis is revisable; a shallow interface fixed by an obligation is not.

## constraint-completeness

```yaml
- id: constraint-completeness
  question: |
    Does the IB bind the performance, security, compatibility and
    concurrency constraints the change must respect, or are the
    non-functional obligations absent?
  input_slice: ib.obligations + ib.protected_surfaces + ib.context + source_ae_paths.*.boundaries
  attack_patterns:
    - the change touches a hot path but no obligation bounds its cost
    - the change touches a security-sensitive surface (auth, secrets, untrusted input) with no security obligation or SP reference
    - the change introduces concurrency without naming the consistency model
    - a referenced source pins a constraint the IB's Outcome silently relaxes
  severity_rubric: shared
```

## rollout-risk-plan

```yaml
- id: rollout-risk-plan
  question: |
    Does the IB declare a kill-switch, feature flag or rollback path
    commensurate with the blast radius of the change?
  input_slice: ib.body + ib.scope
  attack_patterns:
    - the change touches a load-bearing surface (auth, data migration, public API) with no rollback path
    - a feature flag is declared with no removal plan
    - the IB asserts "low risk" without justifying it against its Scope
    - a kill-switch is named without who flips it or when
  severity_rubric: shared
```

## ambiguity-audit

```yaml
- id: ambiguity-audit
  question: |
    Does the IB contain vague verbs ("handle", "support", "improve"),
    unresolved pronouns, or unbounded quantifiers that obscure what is
    binding or what must be demonstrated?
  input_slice: ib.outcome + ib.obligations + ib.acceptance
  attack_patterns:
    - vague verb without an object (e.g. "handle errors" with no behavior stated)
    - unresolved "it" / "this" referring to something unnamed
    - quantifier without bound ("some files" — which?)
    - an obligation whose subject cannot be identified
  severity_rubric: shared
```

## glossary-discipline

```yaml
- id: glossary-discipline
  question: |
    Does the IB introduce Title-Case domain terms that are not defined in
    `dekspec/domain-glossary.md`, or use a term against its definition?
  input_slice: ib.body + glossary + audit_doctor.l10_findings
  attack_patterns:
    - Title-Case term in the IB has no glossary entry (L10 hit)
    - the IB redefines an existing glossary term with a different meaning
    - the IB uses a deprecated term flagged in the glossary
    - the IB's casing differs from the term's canonical form
  severity_rubric: shared
```

## environment-prerequisites

```yaml
- id: environment-prerequisites
  question: |
    If an acceptance condition exercises a live service (database, Docker,
    message broker, external API), does the IB declare it in a typed
    `## Environment Prerequisites` row with a RUNNABLE probe command
    (exit 0 = available) and a Required flag, so `dekspec ib start` can
    block truthfully (prerequisite-unavailable) instead of starting work
    that cannot pass?
  input_slice: ib.acceptance + ib.environment_prerequisites
  attack_patterns:
    - an acceptance condition needs a live service but no environment prerequisite declares it
    - a declared probe is prose or a file reference, not a runnable shell command
    - a required live service is declared without a probe
    - a probe references an undefined variable or tool with no setup note
  severity_rubric: shared
```

Per P-INT-185 (DSF-015). The lens checks only that infrastructure dependencies are declared and probeable; `dekspec ib start` runs the probes.

---

## Cross-references

- ADR-026 (review shape), ADR-054 (routing rule), ADR-055 (authority categories), ADR-056 (one home per fact, generated context), ADR-057 (acceptance contract), ADR-062 (expectation basis, genuine red, the floor review).
- ADR-036 + Constitution Article 4 (source of `interface-depth`).
- `_lib/review-orchestration.md` (the shell), `_lib/review_lens_registry.md` (the schema), `_lib/review_confidence_rubric.md` (`severity_rubric: shared`).
