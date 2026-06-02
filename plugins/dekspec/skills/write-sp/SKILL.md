---
name: write-sp
description: Create, analyze, accept, lock, unlock, revise, supersede, or review a Security Profile (SP-NNN) — the 10th DekSpec IR kind (ADR-011 Option B). A Security Profile captures a project's typed security posture (allowed dataflows, secret stores, authn methods, supply-chain allowed sources, SAST/DAST tools, OWASP coverage). One repo declares a singleton SP-001 (bounded_context absent) or multiple per-bounded-context SPs (e.g., api-gateway, worker).
mode: lite
model: claude-opus-4-7
reasoning_effort: max
disable-model-invocation: false
allowed-tools: Read Write Edit Grep Glob Bash Agent
argument-hint: [--provisional <slug>] [--help | --teaching | --create | --analyze | --accept | --approve | --lock | --unlock | --revise | --supersede | --review] [description or path to SP]
related_skills: [write-sv, write-ae, write-constitution, write-adr, write-ws]
---

> **Scope of this skill.** A Security Profile (`SP-NNN`) is the data plane
> for MSN-003's three-layer compilation (soft / mid / hard) of security
> commitments. The schema is pinned at `tooling/dekspec/schemas/security-profile.schema.yaml`
> with `additionalProperties: false` at every nesting level; the parser
> entry point `parse_security_profile(path)` lives in
> `tooling/dekspec/constraint_compiler/parser.py`. Downstream consumers
> (WS-018 AGENTS.md soft-layer emitter, WS-019 mid+hard pre-commit / CI
> gate emitters, WS-020 T-SEC-* audit family) compose against SPs via
> `SpecGraph.security_profiles()`. This skill is the canonical authoring
> path; hand-edits past `--lock` are governed by `--unlock`.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> A Security Profile is a load-bearing declaration of what the project permits at the security layer. Prior conversation context can degrade rigor by anchoring on partial sketches before the engineer has settled the `bounded_context` or the `allowed_dataflows` shape.
>
> First message → proceed. Prior history → ask "context may affect SP quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode.

**Canonical 8-mode catalog (INT-012 § Desired Outcome).** This skill exposes
exactly eight named modes in canonical order: **create, analyze, accept,
lock, unlock, revise, supersede, review**. Drift on names or order breaks
consumer muscle memory built from sibling 8-mode skills (`/dekspec:write-mission`,
`/dekspec:write-intent`, `/dekspec:write-constitution`). The `--help` and
`--teaching` flags are universal infrastructure and do not count toward
the eight.

## Starter Prompt

```prompt
/dekspec:write-sp capture the api-gateway bounded context

Allowed dataflows: browser → api-gateway (TLS), api-gateway → worker (mTLS).
Secret store is Vault; authn is OIDC. SAST is CodeQL, no DAST yet.
SP-001 singleton already exists, so this one declares bounded_context: api-gateway.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Create Mode** (`--create` is the no-flag default per sibling-skill convention).

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Create mode** — `--create` flag (or no flag). Proceed to **Fan-Out Mode (default authoring path)**.
- **Analyze mode** — `--analyze` flag, expects a path to an existing SP. Skip to **Analyze Mode**.
- **Accept mode** — `--accept` flag, expects a path to an existing SP in `PROPOSED` status. Proceed to **Fan-Out Mode (default authoring path)**.
- **Lock mode** — `--lock` flag, expects a path to an existing SP in `ACCEPTED` status. Skip to **Lock Mode**.
- **Unlock mode** — `--unlock` flag, expects a path to an existing SP in `LOCKED` status. Skip to **Unlock Mode**.
- **Revise mode** — `--revise` flag, expects a path to an existing SP in any non-terminal status + a notes string or file. Proceed to **Fan-Out Mode (default authoring path)**.
- **Supersede mode** — `--supersede` flag, expects a path to an existing SP. Skip to **Supersede Mode**.
- **Review mode** — `--review` flag, expects a path to an existing SP. Skip to **Review Mode**.
- **Approve mode** — `--approve` flag, expects a path to an existing SP. Skip to **Approve Mode**. (Universal infrastructure per INT-021 — does not count toward the canonical eight, like `--help` / `--teaching`.)

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag) / `--create`, `--accept`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--analyze`, `--review`, `--lock`, `--unlock`, `--supersede`, `--dry-run`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `general-purpose` (no dedicated `dekspec:sp-author` type today).
- **substantive_modes**: [Create (default), `--accept`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--analyze`, `--review`, `--lock`, `--unlock`, `--supersede`, `--dry-run`]
- **bundle_list** (Step 1 context):
  1. Template path — `templates/security-profile-template.md`.
  2. Schema path — `tooling/dekspec/schemas/security-profile.schema.yaml` (closed-shape JSON Schema, `additionalProperties: false` at every nesting level).
  3. Methodology references — `docs/dekspec-methodology.md` §Security Profile (if present); `docs/dekspec-operating-guide.md` §Security Profiles (if present).
  4. CLAUDE.md sections — project Guardrails section; "Domain terminology" / "Constraints flow from artifacts" notes.
  5. Parent Architecture Element — if `$ARGUMENTS` names a `bounded_context` (e.g., `api-gateway`, `worker`), the matching AE under `dekspec/architecture-elements/`. For singleton SPs (`bounded_context` absent, typically SP-001), pass the root AE (`AE-001-dekspec.md` or project equivalent) for dataflow coverage validation. If no AE applies, pass the empty list and document the absence.
  6. Related artifacts from the spec graph (paths only): every existing SP under `dekspec/security-profiles/` (singleton-vs-multi-context consistency + OWASP coverage matrix alignment); `dekspec/constitution.md` Article 5 (Development Workflow — SAST/DAST/secret-store/supply-chain commitments to compile into typed-record arrays); `dekspec/domain-glossary.md` (L10 advisory).
  7. Engineer guidance — `$ARGUMENTS` verbatim, including structured cues (`bounded_context:`, `singleton`, notes path for `--revise`).
  8. Constraints — schema closed-shape; loud-placeholder discipline (every `<engineer-fills-here>` replaced or the row deleted before `dekspec validate` passes); singleton-vs-multi-context gate (if SP-001 singleton exists, new SP MUST declare `bounded_context`); honest-empty typed-record arrays allowed (keep H2 + table header); `ir_schema_version: 0.1.0`; status walk legality (Create→PROPOSED; Accept: PROPOSED→ACCEPTED; Revise: any non-terminal, append Amendment Log entry).
- **expected_output_path**: `dekspec/security-profiles/SP-NNN-<slug>.md` (Create — next free SP-NNN) or the input path (Accept / Revise — subagent edits in place).
- **validation**: `dekspec check validate <output-path>`. Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — on non-zero exit, surface verbatim and stop, do not silently retry. Mode-specific post-checks: Create — SP file exists with `status: PROPOSED`, `ir_schema_version: 0.1.0`, index row added (if maintained); Accept — Status flipped PROPOSED→ACCEPTED + `lifecycle` Amendment Log entry; Revise — `substantive` or `editorial` Amendment Log entry summarizing changes.

**End of Fan-Out Mode.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:write-sp"
one_line:   "Author, analyze, accept, lock, unlock, revise, supersede, or review a Security Profile."
modes:
  - { flag: "--create", args: "<description>", description: "Author a new Security Profile from the engineer's description. Copies the canonical template, populates fields, writes to dekspec/security-profiles/ SP-NNN-<slug>.md at PROPOSED status." }
  - { flag: "--analyze", args: "<SP-path>", description: "Read-only health check. Validates against the schema; surfaces empty typed-record arrays for engineer awareness (sibling WS-020's T-SEC-* rules audit them separately). Mutates nothing." }
  - { flag: "--accept", args: "<SP-path>", description: "Promote PROPOSED → ACCEPTED after a clean --analyze + engineer confirmation." }
  - { flag: "--lock", args: "<SP-path>", description: "Promote ACCEPTED → LOCKED. Spec is immutable after this — any further shape change requires --unlock first." }
  - { flag: "--unlock", args: "<SP-path>", description: "Walk LOCKED → ACCEPTED for an emergency rollback. Requires a written reason + an Amendment Log entry." }
  - { flag: "--revise", args: "<SP-path> <notes>", description: "Structured mid-flight change with an Amendment Log entry. Notes accept either an inline string or a path to a notes file." }
  - { flag: "--supersede", args: "<SP-path>", description: "Create a successor SP that supersedes the given one. Marks the old SP as SUPERSEDED." }
  - { flag: "--review", args: "<SP-path>", description: "Walk an existing SP interactively — present each field with context and surface gaps with the engineer one at a time." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing an SP section- by-section. Distinct from --review." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:write-sp capture the api-gateway bounded context"
  - "/dekspec:write-sp --analyze dekspec/security-profiles/SP-001-dekspec-library.md"
  - "/dekspec:write-sp --accept dekspec/security-profiles/SP-002-api-gateway.md"
  - "/dekspec:write-sp --lock dekspec/security-profiles/SP-002-api-gateway.md"
  - "/dekspec:write-sp --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: Security Profile (SP-NNN)
- **template_path**: `templates/security-profile-template.md`
- **methodology_section**: §Security Profile of `docs/dekspec-methodology.md` (per ADR-011 Option B)
- **exemplar_paths**: existing `dekspec/security-profiles/SP-*.md` if present, otherwise `tests/fixtures/`
- **required_sections**: [ID, Title, Status, Bounded Context, Allowed Dataflows, Secret Stores, Authn Methods, Supply Chain, SAST Tools, DAST Tools, OWASP Coverage, IR Schema Version]

**Skill-unique prompts and discipline:**

- For **Bounded Context**, walk the engineer through the singleton-vs-multi-context decision before accepting input — a repo declares either a singleton SP-001 (bounded_context absent) or multiple per-bounded-context SPs.
- For each typed-record array section (Allowed Dataflows, Secret Stores, etc.), explain the canonical record shape before prompting.
- **Loud-placeholder discipline:** the template seeds every typed-record array with a `<engineer-fills-here>` placeholder row. Surface this discipline during the ritual — every placeholder must be replaced with real content or the row deleted before `dekspec validate` passes. On exit, flag any remaining placeholder rows as deferred sections that MUST be removed before `--accept`.
- The SP is written to disk at PROPOSED status (not DRAFT); the engineer audits with `--analyze` (the skill's substitute for `--audit`) before `--accept`.
- **Supply-chain hygiene (ds-tygt):** when walking **Supply Chain**, surface the two operating rules that pair with the profile (they are operator discipline, not schema fields): (1) the **14-day new-package rule** — never lean on a dependency pinned to a version published < 14 days ago without explicit human approval; the `T-SUPPLY-CHAIN-NEW-DEPENDENCY` audit advisory (P3) flags this from an offline `.dekspec/package-publish-dates.json` cache when present; (2) the **breach-scan reflex** — when a breach trends for a package, scan local projects for that package/version and pin away before resuming. Both are documented in the template's Supply Chain section.

## Create Mode

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this
> mode's body to a fresh-context `general-purpose` subagent per
> **Fan-Out Mode** above. The steps below are the **subagent's
> contract** — the orchestrator bundles them into the prompt; the
> subagent executes them in fresh context; the orchestrator validates
> the result via `dekspec check validate <path>` on return and confirms the
> SP was written at PROPOSED with `ir_schema_version: 0.1.0`.

Author a new Security Profile from the engineer's description.

### Step 1: Input

Take the engineer's free-text description. Determine:
- Whether this is a singleton SP (covers the whole repo →
  `bounded_context` absent → SP-001 if the corpus has none yet) or a
  per-context SP (covers a sub-context like `api-gateway` →
  `bounded_context` populated → next free SP-NNN).
- Whether the engineer has any current commitments to populate the
  typed-record arrays, OR whether the SP should ship with honest-empty
  arrays.

### Step 2: Decision Gate — singleton vs multi-context

Run `scripts/singleton_gate.py` (in this skill's folder) — it scans
`dekspec/security-profiles/` and reports `requires_bounded_context`. Surface
stderr on a non-zero exit. If `requires_bounded_context` is `true` (a singleton
SP-001 already exists), the new SP MUST declare a `bounded_context` — refuse to
proceed until the engineer names one. If `false` and the corpus has no SP at
all, the engineer chooses: singleton (no `bounded_context`) or first-of-many
(with `bounded_context`). If `false` because the corpus is already
multi-context, follow the established `bounded_context` convention.

### Step 3: Context Gathering

Run `scripts/compile_article5.py` (in this skill's folder) — it parses
`dekspec/constitution.md` Article 5 (Development Workflow) for any
SAST/DAST/secret-store/supply-chain commitments and emits SP-shaped
typed-record stubs. Surface stderr on a non-zero exit. The script degrades
cleanly: no constitution, or no Article 5, or an Article 5 with no security
tooling, each yields an empty result + an explanatory `note` (those SP arrays
ship honest-empty). Each emitted stub carries `<engineer-fills-here>` — the AI
pins the exact tool name, scope, and OWASP mapping from the engineer's input.
Read existing SPs (if any) for cross-context consistency on the OWASP coverage
matrix.

### Step 4: Draft the SP

Copy `templates/security-profile-template.md` to
`dekspec/security-profiles/SP-NNN-<slug>.md`. Replace every
`<engineer-fills-here>` marker with the engineer's value, OR delete the
placeholder row entirely if the typed-record array should ship empty
(keep the H2 + table header so the section still documents what could
populate it). Set `status: PROPOSED`. Set `ir_schema_version: 0.1.0`.

### Step 5: Validate and Save

Run `dekspec check validate dekspec/security-profiles/SP-NNN-<slug>.md`. If
validation fails, surface the schema error to the engineer and loop on
Step 4. If validation passes, commit the SP at PROPOSED. Add a row to
the SP index (if one exists; otherwise the index lives implicitly in
the directory listing).

## Analyze Mode

Read-only health check. Runs the same schema-validation predicate that
`--accept` would run, but mutates nothing.

### Steps

1. Read the SP. Run `parse_security_profile(path)`; surface any
   schema-validation error verbatim.
2. Walk the typed-record arrays. Surface empty arrays as
   informational (`allowed_dataflows: [] — engineer asserts no
   allowed dataflows; sibling WS-020 T-SEC-ALLOWED-DATAFLOWS-COMPLETE
   may flag this`).
3. Check `bounded_context` cardinality consistency with sibling SPs in
   the corpus.
4. Report findings. Recommend next mode (`--accept` if clean,
   `--revise` if findings).

## Accept Mode (PROPOSED → ACCEPTED)

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this
> mode's body to a fresh-context `general-purpose` subagent per
> **Fan-Out Mode** above. The steps below are the **subagent's
> contract**; on return, the orchestrator runs `dekspec check validate <path>`
> and confirms Status flipped PROPOSED → ACCEPTED with the Amendment
> Log entry appended.

Promote a Security Profile from PROPOSED → ACCEPTED after a clean
`--analyze` + engineer confirmation.

### Steps

1. Run `--analyze` first. If any schema-validation error surfaces,
   refuse to accept until the error is resolved (via `--revise`).
2. Walk the SP's typed-record arrays one more time with the engineer;
   confirm the honest-empty vs populated calls.
3. Flip the SP's Status PROPOSED → ACCEPTED and bump Modified — run
   `python ../_lib/scripts/artifact_ops.py transition <SP-path> --from PROPOSED --to ACCEPTED`
   (surface stderr on non-zero exit and STOP). Then hand-add an Amendment
   Log entry with the date, type `lifecycle`, and a one-line summary of
   what the engineer reviewed at accept time — the SP uses lowercase
   lifecycle types, so do not delegate the row to the script's default
   `Substantive` type.
4. Re-run `dekspec check validate <path>` to confirm the walk didn't break
   schema validation.

## Lock Mode (ACCEPTED → LOCKED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Lock for the canonical 4-step contract. Parameters:

- **artifact_kind_singular**: Security Profile
- **pre_lock_audit_ref**: §Analyze Mode of this skill (re-run `--analyze` as the pre-lock audit; surface any new schema-validation error — should be none if the SP was clean at `--accept`)
- **status_before**: ACCEPTED
- **status_after**: LOCKED
- **artifact_index_path**: none (SPs are tracked under `dekspec/security-profiles/` without a separate status index file)

SP-specific Step 3 phrasing for the confirmation prompt: "Locking SP-NNN. After this, the spec is immutable. Continue? (y/n)". The substrate's Amendment Log entry uses type `lock` with a one-line lock reason (typically "implementation merged + audited clean").

## Unlock Mode (LOCKED → ACCEPTED)

See [`_lib/lock_unlock.md`](../_lib/lock_unlock.md) §Unlock for the canonical 4-step contract. **Variance:** SPs unlock to `ACCEPTED`, not to `PROPOSED` — an unlocked SP is one edit away from re-lock, not back at the proposal stage. Parameters:

- **artifact_kind_singular**: Security Profile
- **status_before**: LOCKED
- **status_after**: ACCEPTED *(non-canonical — see variance note above)*
- **artifact_index_path**: none

SP-specific closing reminder (in Step 4): recommend the engineer follow up with `--revise` to apply the change that motivated the unlock, then `--lock` again when done. Amendment Log entry uses type `unlock` with the engineer's reason verbatim.

## Revise Mode

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this
> mode's body to a fresh-context `general-purpose` subagent per
> **Fan-Out Mode** above. The steps below are the **subagent's
> contract**; on return, the orchestrator runs `dekspec check validate <path>`
> and confirms the Amendment Log entry was appended summarizing the
> changes.

Structured mid-flight change with an Amendment Log entry. Used when the
engineer has review notes — from an `--analyze` session, an external
review, or their own analysis — that need to be worked into an SP.

### Steps

1. Read the SP. Confirm status is non-terminal (not SUPERSEDED).
2. Read the engineer's notes (inline string or path to notes file).
3. Apply the changes section by section. For each non-trivial edit,
   confirm with the engineer before writing.
4. Add an Amendment Log entry summarizing the changes (date, type
   `substantive` or `editorial`, the change one-line).
5. Re-run `dekspec validate`. If the revise triggered a schema-
   validation error, surface and loop.

## Supersede Mode

Create a successor Security Profile that supersedes the given one. The
successor inherits the bounded_context (if any) but carries its own
typed-record arrays + Amendment Log.

### Steps

1. Read the source SP. Confirm status is non-terminal.
2. Allocate the next free SP-NNN.
3. Copy the source SP's `bounded_context` (if any) and `title` (with
   a "(successor to SP-NNN)" suffix recommendation). Reset the typed-
   record arrays per engineer guidance.
4. Write the successor at `dekspec/security-profiles/SP-NNN-<slug>.md`
   at PROPOSED status.
5. Mark the source SP's status as `SUPERSEDED` with an Amendment Log
   entry citing the successor's ID.
6. Re-run `dekspec validate` against both files.

## Review Mode

Walk an existing SP interactively — present each section with context
and surface gaps with the engineer one at a time. Read-only with respect
to the SP file itself; produces a list of recommended `--revise` actions
for the engineer to apply.

### Steps

1. Read the SP.
2. For each H2 section, surface the current value alongside the
   sibling-SP values (if any) and the schema's required shape.
3. Ask the engineer: "Is this section complete? (y/n/skip)". Record
   responses in a structured review-notes file.
4. On exit, recommend `--revise <SP-path> <review-notes-path>` if any
   sections were marked incomplete.

## Cross-references

- **Schema:** `tooling/dekspec/schemas/security-profile.schema.yaml`
- **Parser:** `tooling/dekspec/constraint_compiler/parser.py::parse_security_profile`
- **SpecGraph accessor:** `tooling/dekspec/constraint_compiler/graph.py::SpecGraph.security_profiles`
- **Template:** `templates/security-profile-template.md`
- **Library dogfood:** `dekspec/security-profiles/SP-001-dekspec-library.md`
- **Source contracts:** INT-012, WS-017
- **Source ADRs:** ADR-011 (Option B — new IR kind), ADR-007 (eat-own-cooking),
  ADR-006 (schema closure)

## Approve Mode

`--approve` records a peer-review approval signature on a Security Profile under the multi-engineer `team` audit profile (INT-021). It appends one `review-approval` row to the SP's `## Amendment Log` table — it does **not** flip Status.

Run the shared deterministic helper:

```
python ../_lib/scripts/artifact_ops.py approve <SP-path> --target-status <STATUS>
```

`<STATUS>` is the transition the signature authorizes (e.g. `ACCEPTED` or `LOCKED`). The script resolves the reviewer email from `git config user.email` (override with `--engineer <email>`) and appends a row of the form `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`, then bumps `Modified`. The `T-APPROVAL-GATE` audit rule counts these rows under the `team` profile; once enough signatures are present the SP may walk the gated transition. Under the default `v1` profile the rule is silent. Inline mode — no fan-out.

## Provisional Mode

`--provisional <incubation-slug>` redirects authoring into the provisional staging area (`dekspec/provisional/<incubation-slug>/`) instead of the canonical `dekspec/security-profiles/` directory. The canonical Status transition + audit walker pick the work up only after the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)) is run later. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)

Use this mode when:
- The exploration may span many commits before ratification.
- Companion artifacts (ADRs / AEs / ICs that this Security Profile depends on) will be authored alongside in the same incubation folder.
- The canonical ID should NOT be claimed until the originating Intent reaches ACCEPTED.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding so the remaining args feed normal authoring.
2. If the incubation folder `dekspec/provisional/<slug>/` does not exist OR does not yet contain a `SP-provisional-*.md` file for this work, scaffold via:
   ```
   dekspec library new-provisional SP <slug> --title "<H1 title from remaining $ARGUMENTS>" [--incubation <slug>] [--no-branch]
   ```
   The CLI scaffolds the folder + skeleton + (by default) a git branch named per kind. Surface its stderr on non-zero exit and STOP.
3. Read the scaffolded file at `dekspec/provisional/<slug>/SP-provisional-<title-slug>.md` (the CLI prints the path).
4. **Populate the skeleton with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here (Motivation, Linked AEs, Components affected, Verification, etc.). The PROVISIONAL banner at the top stays.
5. **Reject `--lock`** in combination with `--provisional`. LOCKED state requires linkage-walker visibility that provisional artifacts deliberately lack. The hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion) is the canonical path to LOCKED.
6. **`--analyze` and `--review`** remain available in provisional mode — they operate on the provisional file's content without requiring canonical-graph visibility.
7. Closing step: surface to the engineer the path of the provisional file, the branch (if created), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

### Cross-references

- `INT-079` — provisional folder substrate (parser-ignore, doctor advisory).
- `INT-082` — copy-on-write spec staging (`replaces:` frontmatter, sibling-collision audit).
- `INT-083` — atomic promotion (CLI verb retired 2026-05-25; the hand-promote workflow is canonical — see `_lib/cli_verbs.md`).
- `INT-084` — `dekspec library new-provisional` scaffold + auto-branch.

**End of Provisional Mode.**

## Write-Time CoW Guard (INT-082 phase 4)

Before any edit to a canonical artifact (anything under `dekspec/<kind-dir>/`), consult the CoW guard:

```bash
dekspec library cow-stage <path-to-canonical> [--incubation <slug>] [--at <repo>]
```

If the target path is claimed by a pre-ACCEPTED Intent (DRAFT/PROPOSED) via that Intent's `Components affected` globs, the verb:

1. Copies the canonical to `dekspec/provisional/<incubation-slug>/<KIND>-provisional-<file-slug>.md`.
2. Stamps `replaces: <CANONICAL-ID>` in the frontmatter so the eventual `promote-provisional` run does a REPLACE (preserving the canonical ID) instead of allocating a new one.
3. Returns the new provisional path. Edit that file instead; the canonical stays frozen.

If the path is not claimed by any pre-ACCEPTED Intent, the verb errors unless you pass an explicit `--incubation <slug>` (the canonical-only path is the normal edit flow).

**Skill discipline.** Inside this skill body, before any canonical-file `Edit`/`Write` call:

1. Compute the target path you intend to write.
2. Run `dekspec library cow-stage <target-path>` once. Surface the verb's stdout to the engineer.
3. If the verb exits 0 with a new provisional path printed, redirect the edit to that path.
4. If the verb exits 1 (no claim + no `--incubation`), proceed with the canonical edit as normal — the canonical is unclaimed and the edit is direct-flow legal.

**Audit pairing.** The `T-COW-CANONICAL-EDITED` rule (P2 mechanical) fires on every `git diff --name-only main` entry that is claimed AND lacks a provisional sibling with `replaces:` set — so a skill that skips this guard surfaces as advisory in the next `dekspec audit linkage` run, but never blocks.


## Common Pitfalls

- Don't author a second SP without a `bounded_context` when SP-001 singleton already exists — run `scripts/singleton_gate.py` first and refuse until the engineer names a context; two `bounded_context`-absent SPs is an unresolvable cardinality conflict.
- Don't leave `<engineer-fills-here>` placeholder rows in the file — either replace them with real typed records or delete the row entirely (keeping the H2 + table header), because `dekspec check validate` fails on a live placeholder.
- Don't delete a whole typed-record section to represent "no commitments" — ship the array honest-empty (keep H2 + header) so the section still documents what could populate it; an absent section is not the same as an asserted-empty one.
- Don't unlock an SP to `PROPOSED` — SPs are the documented variance and unlock to `ACCEPTED` (one edit away from re-lock); routing through `lock_unlock.md`'s default would corrupt the status walk.
- Don't combine `--lock` with `--provisional` — provisional artifacts lack the linkage-walker visibility LOCKED requires; route to LOCKED only through the hand-promote workflow.
- Don't let the transition script stamp a `Substantive`/default Amendment Log type on a lifecycle move — SPs use lowercase lifecycle types (`lifecycle`, `lock`, `unlock`); hand-add the row with the correct lowercase type.

## Verification Checklist

- [ ] Singleton-vs-multi-context gate ran (`scripts/singleton_gate.py`) and the SP's `bounded_context` presence matches its verdict.
- [ ] `dekspec check validate <SP-path>` exits 0 — no live `<engineer-fills-here>` placeholder rows remain.
- [ ] Every typed-record array is either populated or honest-empty (H2 + table header retained, no whole section deleted).
- [ ] `status` and `ir_schema_version: 0.1.0` reflect the mode run (Create → PROPOSED; Accept → ACCEPTED; Lock → LOCKED; Unlock → ACCEPTED; Supersede → source SUPERSEDED + successor PROPOSED).
- [ ] An Amendment Log entry was appended for every status-changing mode, using the correct lowercase lifecycle type (`lifecycle` / `lock` / `unlock` / `substantive` / `editorial`).
- [ ] `--lock` was NOT used in combination with `--provisional`.
- [ ] `dekspec audit relink` ran against the repo root after any substantive write.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise a Security Profile — Creation, `--accept`, `--revise`, `--lock`, `--unlock`, `--supersede`). After the artifact file is saved and any index update is done, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
