# Architecture Principles

This file is self-contained. Do not depend on external architecture skill files
or book/source files when using the `audit-codebase` skill. The vocabulary and
rubric below are condensed from *A Philosophy of Software Design*
(`../../../../../docs/a-philosophy-of-software-design-ai-reference.md`), which is
the canonical authority — this file restates it for self-containment.

## Vocabulary

Use these terms consistently:

- **Module** - anything with an interface and an implementation: function,
  class, package, workflow slice, or tier-spanning slice.
- **Interface** - everything callers must know to use a module correctly:
  names, types, invariants, ordering, errors, configuration, performance, and
  lifecycle expectations.
- **Implementation** - code inside the module.
- **Depth** - leverage at the interface. A module is **deep** when a small
  interface hides substantial behavior or policy.
- **Shallow** - interface is nearly as complex as the implementation.
- **Seam** - a place where behavior can vary without editing that place.
- **Adapter** - concrete implementation satisfying an interface at a seam.
- **Leverage** - capability callers get per unit of interface they must learn.
- **Locality** - change, bugs, and verification concentrated in one module.

Avoid these substitutions when using the architecture vocabulary:

- use **module**, not component/unit/service
- use **interface**, not API/signature when the whole contract is meant
- use **seam**, not boundary

## Deep Modules

A module is deep when callers learn little and get a lot:

- small public interface
- large or subtle implementation hidden behind it
- clear ownership of policy, invariants, ordering, or error behavior
- tests can lock behavior through the public interface
- deleting it would scatter complexity across callers

Shallow-module signals:

- pass-through functions or classes
- interface nearly duplicates implementation
- callers must orchestrate internal phases manually
- tests patch private helpers because no public behavior seam exists
- concepts are split across many tiny files and must be understood together

## Deletion Test

Imagine deleting the module:

- If complexity vanishes, the module was probably pass-through.
- If complexity reappears across multiple callers, the module was earning its
  keep.
- If deletion would force callers to learn ordering, config, persistence,
  tensor, transport, or error rules, the module likely has depth.

## Information Hiding

Good modules hide design decisions. Look for hidden or leaked information:

- hidden data-shape invariants
- hidden ordering rules
- hidden persistence grammar
- hidden transport/retry/error policy
- hidden cache/write-buffer semantics
- hidden model/device/dtype rules

Information leakage occurs when the same design decision appears in multiple
modules or when callers must know internals to use a module correctly.

## Pull Complexity Downward

Prefer modules that absorb complexity so callers do less work. A caller should
not repeatedly provide flags, preconditions, or sequencing instructions that the
module can infer or own.

Audit questions:

- Are callers passing many pass-through variables?
- Are callers responsible for ordering calls correctly?
- Is specialized case handling pushed into every caller?
- Would a slightly more general module interface remove special cases?

## Different Layer, Different Abstraction

Adjacent layers should not repeat the same abstraction. Pass-through layers are
usually shallow unless they change abstraction, enforce policy, or isolate a
real seam.

Audit questions:

- Does this layer add a new abstraction?
- Does it hide policy or just rename calls?
- Would removing it make callers simpler?

## Better Together Or Better Apart

Bring code together when:

- pieces share information
- combining them simplifies the interface
- separation creates duplication
- callers must understand both pieces together

Keep code apart when:

- one part is general-purpose and another is special-purpose
- there is a real seam with real adapters
- separate lifecycle or dependency constraints justify the split

## Errors As Complexity

Errors add interface complexity. Prefer modules that define errors out of
existence, aggregate low-level failures, or expose a small error vocabulary.

Audit questions:

- Do callers handle many low-level exceptions?
- Is error translation repeated?
- Can a module make an invalid state unrepresentable?

## Comments And Design Intent

Useful comments explain non-obvious design intent, invariants, or cross-module
decisions. Comments that merely restate code are noise.

Audit questions:

- Are interface invariants documented?
- Are surprising constraints explained near the module interface?
- Are cross-module decisions captured in docs/ADRs instead of scattered comments?

## Deepening Dependencies

Classify dependencies before recommending a deepening:

- **In-process** - pure computation or in-memory state. Merge/deepen directly.
- **Local-substitutable** - dependency has a local test stand-in. Test with that
  stand-in behind the module interface.
- **Remote but owned** - define a port at the seam; production adapter uses
  HTTP/gRPC/queue; tests use in-memory adapter.
- **True external** - inject a port and test with a mock/fake adapter.

Seam discipline:

- one adapter usually means a hypothetical seam
- two adapters usually justify a real seam
- internal seams may exist for implementation tests, but do not expose them as
  public interface just to make tests convenient

Testing rule:

- the interface is the test surface
- tests should assert observable behavior, not internal state
- tests should survive internal refactors

## Audit Rule Families

Use stable finding codes so audits can be compared over time. Start with the
family prefix, then a short uppercase slug.

### DM - Deep Module

Use for module-depth classification and deep-module problems.

Examples:

- `DM-DEEP-MODULE` - informational classification; module is deep by rubric.
- `DM-SHALLOW-INTERFACE` - interface is nearly as complex as implementation.
- `DM-DELETION-SCATTERS-COMPLEXITY` - deletion test indicates depth.

### SH - Shallow Module

Use for pass-through modules, classitis, or thin wrappers that do not hide
meaningful behavior.

Examples:

- `SH-PASS-THROUGH-MODULE`
- `SH-HELPER-SPRAWL`
- `SH-CLASSITIS`

### IH - Information Hiding

Use when design decisions are hidden well or leak across modules.

Examples:

- `IH-LEAKED-INVARIANT`
- `IH-DUPLICATED-POLICY`
- `IH-HIDDEN-DECISION`

### PT - Pass-Through Layer

Use when adjacent layers repeat the same abstraction.

Examples:

- `PT-SAME-ABSTRACTION-LAYER`
- `PT-PASS-THROUGH-VARIABLES`

### PCD - Pull Complexity Downward

Use when callers carry complexity the module should absorb.

Examples:

- `PCD-CALLER-OWNS-SEQUENCING`
- `PCD-CALLER-OWNS-CONFIG-POLICY`
- `PCD-SPECIAL-CASE-SPREAD`

### BTA - Better Together / Better Apart

Use for cohesion and separation findings.

Examples:

- `BTA-SHARED-INFORMATION-SPLIT`
- `BTA-GENERAL-SPECIAL-MIXED`
- `BTA-REAL-SEAM-JUSTIFIES-SPLIT`

### ERR - Error Complexity

Use when errors enlarge the interface or when a module successfully aggregates
error behavior.

Examples:

- `ERR-LOW-LEVEL-ERROR-LEAK`
- `ERR-REPEATED-ERROR-TRANSLATION`
- `ERR-INVALID-STATE-REPRESENTABLE`

### DOC - Comments And Design Intent

Use for missing or noisy design documentation.

Examples:

- `DOC-MISSING-INTERFACE-INVARIANT`
- `DOC-OBVIOUS-COMMENT`
- `DOC-CROSS-MODULE-DECISION-SCATTERED`

### TEST - Test Surface

Use when tests do or do not lock behavior through the module interface.

Examples:

- `TEST-MISSING-INTERFACE-COVERAGE`
- `TEST-PRIVATE-HELPER-COUPLING`
- `TEST-BEHAVIOR-LOCKED-AT-SEAM`

### FOLD - Folderization Fit

Use for Python package/folderization judgments.

Examples:

- `FOLD-SHOULD-FOLDERIZE`
- `FOLD-SINGLE-FILE-OK`
- `FOLD-FOLDERIZED-BUT-SHALLOW`
- `FOLD-PUBLIC-INIT-LEAKS-INTERNALS`
