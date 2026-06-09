# Context Spec: <engineer-fills-here — short title>

> **Purpose.** Capture a single agent role's typed *input-scoping
> contract* — the artifact paths, schema fragments, and glossary terms
> that role's context window is scoped to, plus the conditions under
> which it escalates rather than decides — as a Context Spec (CS), the
> 11th DekSpec IR kind per ADR-011 Option B. One canonical instance ships
> per role identity (six in total), generalizing the dekfactory Phase 0
> `additionalProperties: false` adversarial-separation invariant into a
> first-class, parser-validated, ID-addressable IR.
>
> **Canonical ID regex.** `^CS-\d{3,}$` — three or more digits; `CS-001`
> is the lowest reserved value. The ID lives in the `## ID` section BODY,
> NOT the filename: the canonical filename is role-keyed
> (`dekspec/context-specs/role-<role>.md`), not ID-keyed.
>
> **Schema.** `tooling/dekspec/schemas/context-spec.schema.yaml`
> (`additionalProperties: false` at every nesting level — the schema-level
> enforcement of the input-scoping invariant).
>
> **Canonical authoring path.** `dekspec/context-specs/role-<role>.md`
> (flat layout — no per-role subdir). Resolve this template via
> `dekspec resource template context-spec-template`.
>
> **Placeholder discipline.** Every `<engineer-fills-here>` marker is
> deliberately schema-invalid: a thoughtless `cp` of this template
> produces markdown that fails `parse_context_spec` schema validation
> loudly, so an unfilled section can't slip past `dekspec validate`.
> Replace every marker before committing.

<!--
SECTIONS BELOW: which ones flow into the ContextSpec IR vs which are "author scratch pad"
========================================================================================
Canonical sections (extracted by parse_context_spec, schema-validated):
  ID · Title · Status · Role Identity · IR Schema Version ·
  Artifact Path Scope · Schema Fragment Scope · Glossary Subset Scope ·
  Escalation Triggers

Author scratch pad (guidance for the authoring engineer, NOT loaded into
the IR — every paragraph below a canonical section that sits inside an
HTML comment is scratch-pad prose the parser ignores):
  the per-section "how to fill this" prose wrapped in HTML comments.

Canonical content stays OUTSIDE HTML comments; author guidance / scratch-pad
prose stays INSIDE HTML comments. This is the AE-007
canonical-vs-author-scratch-pad convention.
-->

## ID

CS-NNN

<!--
Replace NNN with the next free 3+ digit number (lowest reserved is CS-001;
consult `dekspec/context-specs/` before claiming). The ID is sourced from
THIS section body by the parser — the role-keyed filename carries no ID.
The literal `CS-NNN` above is deliberately schema-invalid (`^CS-\d{3,}$`
requires digits) so an unfilled template fails `parse_context_spec` loudly.
-->

## Title

<engineer-fills-here — a one-line human title for this ContextSpec>

<!--
A one-line human-readable title for this role's input-scoping contract,
e.g. "Code-Reviewer input scope" or "Specifier input scope".
-->

## Status

<pick-one: PROPOSED | ACCEPTED | LOCKED | SUPERSEDED>

<!--
Initial committed state is PROPOSED. Four-value enum (no DRAFT — mirrors
the SP precedent). Walk forward via the artifact's skill modes; do not
hand-edit past LOCKED without an --unlock flag.
-->

## Role Identity

<pick-one: specifier | spec-reviewer | implementer | code-reviewer | verifier | auditor>

<!--
Exactly one of the six canonical role identities — this enum is the closure
of valid role identities, and the six canonical instances form a bijection
onto these values. A seventh role is a future additive Intent, not an
inline widening.
-->

## Artifact Path Scope

- <engineer-fills-here — first artifact path/glob this role's context window is scoped to>

<!--
The artifact paths / globs this role's context window is scoped to — one
non-empty string per bullet. This is the role's "what files may I see"
contract (e.g. the IB + bead JSON + diff surface for code-reviewer; the
Intent/WS artifact paths for specifier). An empty array is valid only if
the role genuinely scopes to no artifact paths; otherwise list each path.
-->

## Schema Fragment Scope

- <engineer-fills-here — first schema fragment/kind this role sees>

<!--
The schema fragments / IR kinds this role sees — one non-empty string per
bullet (e.g. `intent` + `working_spec` for specifier; `implementation_brief`
for implementer). An empty array is valid only as a deliberate "this role
reads no schema fragments" assertion.
-->

## Glossary Subset Scope

- <engineer-fills-here — first domain-glossary term scoped in for this role>

<!--
The domain-glossary terms scoped into this role's context window — one
non-empty string per bullet. Scope in only the terms the role needs, not
the whole glossary; the subset IS the adversarial-separation discipline.
An empty array is valid only as a deliberate assertion.
-->

## Escalation Triggers

| Condition | Action |
|-----------|--------|
| <engineer-fills-here — condition under which this role escalates rather than decides> | <engineer-fills-here — the escalation action to take> |

<!--
The conditions under which this role escalates rather than decides — one
row per trigger. Both `condition` and `action` are REQUIRED non-empty
strings on every row (nested `additionalProperties: false` — no extra
sub-fields). E.g. for code-reviewer: condition "diff touches a file outside
the bead's declared scope" → action "halt and surface to the operator".
An empty array (delete the placeholder row, keep the header) is valid only
as a deliberate "this role never escalates" assertion.
-->

## IR Schema Version

0.1.0

<!--
Pinned to `0.1.0`. The schema enforces this via `const: "0.1.0"`; a future
v0.2.0 schema bump lands its own migration via a new IB. Do not change this
line.
-->
