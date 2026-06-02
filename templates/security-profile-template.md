# Security Profile: <engineer-fills-here — short title>

> **Purpose.** Capture a project's typed security posture — allowed
> dataflows, secret stores, authn methods, supply-chain allowed sources,
> SAST/DAST tools, and OWASP coverage — as a Security Profile (SP), the
> 10th DekSpec IR kind per ADR-011 Option B. One repo may declare a
> singleton SP-001 covering the whole codebase (`bounded_context` absent),
> or multiple per-`bounded_context` SPs (e.g., `api-gateway`, `worker`).
>
> **Canonical ID regex.** `^SP-\d{3,}$` — filename is
> `dekspec/security-profiles/SP-NNN-<slug>.md`. Three or more digits;
> `SP-001` is the lowest reserved value.
>
> **Schema.** `tooling/dekspec/schemas/security-profile.schema.yaml`
> (`additionalProperties: false` at every nesting level).
>
> **Canonical authoring path.** `/dekspec:write-sp` —
> eight-mode skill (create, analyze, accept, lock, unlock, amend,
> supersede, review). The `--create` mode of that skill scaffolds this
> file with sections populated against the schema; `--accept` walks
> PROPOSED → ACCEPTED; `--lock` walks ACCEPTED → LOCKED.
>
> **Placeholder discipline.** Every `<engineer-fills-here>` marker is
> deliberately invalid: a thoughtless `cp` of this template produces
> markdown that fails `parse_security_profile` schema validation loudly,
> so an unfilled section can't slip past `dekspec validate`. Replace
> every marker before committing; remove or expand any row whose
> placeholder text shouldn't ship.

## ID

SP-NNN — replace NNN with the next free 3+ digit number (lowest currently in
use is SP-001; consult `dekspec/security-profiles/` before claiming).

## Title

<engineer-fills-here — a one-line human title for this SP>

## Status

<pick-one: PROPOSED | ACCEPTED | LOCKED | SUPERSEDED>

Initial committed state is PROPOSED. Walk forward via the
`/dekspec:write-sp --accept` / `--lock` skill modes — do not
hand-edit the status line past LOCKED without the `--unlock` flag.

## Bounded Context

OPTIONAL. The singleton case is this section being EMPTY (or removed
entirely): the SP covers the whole repo. SP-001 is authored in this
shape.

The multi-context case is this section containing a single non-empty
string identifying a sub-context (e.g., `api-gateway`, `worker-pool`,
`background-jobs`). When present, downstream audit rules iterate
per-context.

## Allowed Dataflows

| Name | Source | Sink | Classification |
|------|--------|------|----------------|
| <engineer-fills-here — flow name> | <engineer-fills-here — source system> | <engineer-fills-here — sink system> | <engineer-fills-here — sensitivity class> |

Empty array is valid (the engineer asserts "no allowed dataflows at this
layer"); delete the placeholder row but keep the header + separator if
the value should be `[]`.

## Secret Stores

| Name | Kind | Scope |
|------|------|-------|
| <engineer-fills-here — store name> | <engineer-fills-here — kind> | <engineer-fills-here — scope> |

Empty array is valid; delete the placeholder row but keep the table
header if the value should be `[]`.

## Authn Methods

| Name | Kind | Scope |
|------|------|-------|
| <engineer-fills-here — method name> | <engineer-fills-here — kind> | <engineer-fills-here — scope> |

Empty array is valid; delete the placeholder row but keep the header if
the value should be `[]`.

## Supply Chain

The `supply_chain` object is REQUIRED. Its single sub-field
`allowed_sources` is an array of strings; the array may be empty
(explicit "we declare no allowed sources" assertion). Authored here as a
bullet list:

- <engineer-fills-here — first allowed source, e.g. `pypi.org`>
- <engineer-fills-here — additional allowed sources, one per bullet>

**Supply-chain hygiene (advisory, ds-tygt).** Two operating rules pair with
this profile; both are operator discipline, not schema fields:

1. **14-day new-package rule.** Do not lean on a dependency pinned to a version
   published fewer than 14 days ago without explicit human approval — fresh
   releases are the prime window for typosquat / account-takeover supply-chain
   attacks. The `T-SUPPLY-CHAIN-NEW-DEPENDENCY` audit advisory (P3) surfaces
   this when publish-date metadata is resolvable. It reads an OFFLINE cache the
   repo maintains at `.dekspec/package-publish-dates.json` — a JSON map of
   `"name==version"` → `"YYYY-MM-DD"` (publish date). No cache or no entry → no
   finding (the audit never reaches out to a registry; populating the cache from
   a registry is an explicit downstream opt-in).
2. **Breach-scan reflex.** When a breach trends for a package, scan local
   projects for that package/version (e.g. `grep -rn "<pkg>" **/requirements*.txt
   **/pyproject.toml` or your lockfiles) and pin away from the affected version
   before resuming work.

## SAST Tools

| Name | Language | Ruleset |
|------|----------|---------|
| <engineer-fills-here — tool name> | <engineer-fills-here — language> | <engineer-fills-here — ruleset name> |

Empty array is valid; delete the placeholder row but keep the header if
the value should be `[]`.

## DAST Tools

| Name | Target | Schedule |
|------|--------|----------|
| <engineer-fills-here — tool name> | <engineer-fills-here — target> | <engineer-fills-here — schedule cadence> |

Empty array is valid; delete the placeholder row but keep the header if
the value should be `[]`.

## OWASP Coverage

| OWASP ID | Mitigation Strategy | Mapped Tool |
|----------|---------------------|-------------|
| <engineer-fills-here — OWASP top-10 ID, e.g. `A03`> | <engineer-fills-here — short mitigation description> | <engineer-fills-here — mapped tool from SAST/DAST tables above> |

Row-per-OWASP-ID matrix. Empty array is valid (engineer asserts no
coverage today; sibling WS-020's T-SEC-OWASP-COVERAGE audit rule will
surface this as an advisory finding — the correct surface for the
conversation about populating it). Delete the placeholder row but keep
the header if the value should be `[]`.

## IR Schema Version

0.1.0

Pinned to `0.1.0` for v1. The schema enforces this via `const`; a future
v0.2.0 schema bump will land its own migration via a NEW IB (per the SP
data-plane immutability guarantee from IB-027).
