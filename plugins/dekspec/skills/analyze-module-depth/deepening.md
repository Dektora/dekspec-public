# Deepening

How to deepen a cluster of shallow modules safely, given its dependencies.
Assumes [language.md](language.md) vocabulary.

## Dependency categories

1. **In-process** — pure computation, in-memory state, no I/O. Always
   deepenable; merge the modules and test through the new interface directly. No
   adapter.
2. **Local-substitutable** — deps with local test stand-ins (PGLite for
   Postgres, in-memory fs). Deepenable when the stand-in exists; tested with the
   stand-in in the suite. The seam is internal; no port at the external
   interface.
3. **Remote but owned (Ports & Adapters)** — your own services across a network
   boundary. Define a port at the seam; the deep module owns the logic;
   transport is injected as an adapter. Tests use an in-memory adapter; prod
   uses an HTTP / gRPC / queue adapter.
4. **True external (Mock)** — third-party services you don't control. The deep
   module takes the external dep as an injected port; tests provide a mock
   adapter.

## Seam discipline

One adapter = a hypothetical seam; two = a real one — don't introduce a port
unless ≥2 adapters justify it (prod + test). Internal seams vs external seams —
don't expose an internal seam through the interface just because a test uses it.

## Testing strategy: replace, don't layer

Old unit tests on shallow modules become waste once interface tests exist —
delete them. Write new tests at the deepened module's interface (the interface
is the test surface). Assert observable outcomes *through the interface*, not
internal state. Tests should survive internal refactors.

## Concentration-raising methodology (the bounded move-set)

Deepening *concentrates* complexity into a few deep modules. The move-set that
does this is bounded — three moves only — and grounded in APOSD
(`docs/a-philosophy-of-software-design-ai-reference.md`) and
[ADR-039](../../../../dekspec/adrs/ADR-039-classify-module-depth-by-pareto-band-with-floor.md).

### The three moves

(a) **Collapse pass-through layers.** A layer that merely forwards calls to the
next layer adds interface cost and hides nothing (APOSD "Different Layer,
Different Abstraction" / the pass-through-method red flag). Collapse it: fold the
forwarding layer into the layer it forwards to so each layer offers a *different*
abstraction.

(b) **Pull caller-side logic down into the module.** Logic that every caller
must perform to use a module belongs *inside* the module (APOSD "Pull Complexity
Downward"). Moving it down shrinks the interface every caller pays for and
absorbs the complexity once, where it is hidden.

(c) **Merge collaborators — but only on a genuine signal.** Combine two modules
ONLY when one of these holds: they **share important knowledge** (APOSD "If two
pieces of code share important knowledge, consider putting them together"); the
**interface simplifies** by combining (APOSD "If combining code simplifies the
interface, prefer combining"); or the merge **eliminates duplication**. Absent
one of these, leave them apart — merging unrelated code is not deepening.

### The over-consolidation guardrail

A consolidation that pushes a module **past the ADR-039 overexposure cutoff is
REJECTED.** ADR-039 defines **Overexposed** as an *orthogonal axis*: a public
interface so wide that callers must reckon with rarely-used surface just to use
the common one — independent of leverage. A merge that widens the interface past
that cutoff has not deepened the module; it has overexposed it. Reject the merge
and keep the modules apart (or find a narrower seam). Overexposure is reported on
its own axis and never bought back by added depth.

### Concentration is a byproduct, never a target

Per [ADR-039](../../../../dekspec/adrs/ADR-039-classify-module-depth-by-pareto-band-with-floor.md):
complexity concentrated in the deep band is the *goal* of pulling complexity
downward, but the audit's **concentration figure is a health signal, not a
number to chase.** Deepen because the **deletion test** or the **shallow-interface
signal** says a module is shallow — never to make a concentration metric go up.
Correct deepening *raises* concentration as a side effect; raising concentration
is never itself the objective. A module deepened to move a number, rather than
because it was shallow, is over-folding — exactly the smell ADR-039's "sound"
band exists to protect against.
