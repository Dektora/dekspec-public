# Language

The shared vocabulary every suggestion this skill makes is spoken in. Use these
terms exactly — don't substitute "component," "service," "API," "boundary," or
"wrapper."

**Canonical source.** These eight terms live in `dekspec/domain-glossary.md`
(the *Architecture Vocabulary* section) — that glossary is canonical and should
be the reader's first stop. The definitions are grounded in *A Philosophy of
Software Design* (`docs/a-philosophy-of-software-design-ai-reference.md`); this
file does not re-derive them, it restates them for self-containment and points
back at the glossary + APOSD as the authorities. Do **not** introduce any new
Title-Case architecture term beyond these eight (the L10 audit fires on
undefined domain jargon).

## Terms

- **Module** — anything with an interface and an implementation; scale-agnostic
  (a function, class, package, workflow slice, or tier-spanning slice). The unit
  at which complexity is hidden (APOSD §Modules Should Be Deep). Avoid: unit,
  component, service.
- **Interface** — everything a caller must know to use the module correctly:
  type signature + invariants, ordering, error modes, required config,
  performance, lifecycle. The cognitive cost a caller pays (APOSD §Information
  Hiding). Avoid: API, signature.
- **Implementation** — the code inside a module; the hidden half callers need
  not know. Distinct from Adapter. Where complexity is pulled downward and
  absorbed (APOSD §Pull Complexity Downward).
- **Depth** — leverage at the interface: behaviour exercised per unit of
  interface learned. **Deep** = large behaviour behind a small interface.
  **Shallow** = interface nearly as complex as the implementation (APOSD §Deep
  Modules). Depth is benefit-per-interface-cost, not lines of code or layering.
- **Seam** (Michael Feathers) — a place where behaviour can vary without editing
  in that place; the location at which a module's interface lives, and where an
  alternate implementation can be substituted. Avoid: boundary.
- **Adapter** — a concrete thing that satisfies an interface at a seam. Role,
  not substance — the swappable piece a seam admits.
- **Leverage** — what callers get from depth: one implementation pays back across
  N call sites and M tests. Benefit relative to interface cost, not raw feature
  count (APOSD §Decide What Matters).
- **Locality** — what maintainers get from depth: change, bugs, knowledge, and
  verification concentrate at one place.

## Principles

- Depth is a property of the **interface**, not the implementation — a deep
  module can be internally composed of small mockable parts (internal seams vs
  the one external seam).
- **The deletion test** — imagine deleting the module. If complexity vanishes,
  it was a pass-through. If complexity reappears across N callers, it was
  earning its keep.
- **The interface is the test surface.**
- **One adapter = a hypothetical seam; two = a real one.**

## Relationships

A Module has exactly one Interface. Depth is a property of a Module measured
against its Interface. A Seam is where a Module's Interface lives. An Adapter
sits at a Seam and satisfies the Interface. Depth produces Leverage (for
callers) and Locality (for maintainers).

## Rejected framings

- **Depth as a ratio of implementation-lines to interface-lines** (a naive
  reading of Ousterhout): rewards padding — use depth-as-leverage.
- **"Interface" as the TypeScript `interface` keyword / the set of public
  methods**: too narrow — the interface is everything a caller must know.
- **"Boundary"**: overloaded with the DDD bounded-context sense — say *seam* or
  *interface*.
