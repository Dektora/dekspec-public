---
purpose: Canonical CLI invocations for DekSpec verbs that skills reference. Skills SHOULD link to this file from their Closing Step prose rather than inline a raw verb. Renames are governed here; drift is caught by `scripts/check-cli-verb-drift.sh` in CI.
audience: Skill authors. The validating side is the CI gate; the discoverability side is here.
last-synced: 2026-05-25b
---

# DekSpec CLI Verbs — Single Source of Truth

This file is the canonical list of DekSpec CLI invocations referenced from skill bodies. When the CLI surface changes (verb renamed, moved under a new group, retired), this file is the first artifact to update. The companion CI gate (`scripts/check-cli-verb-drift.sh`) ensures retired verbs do not leak back into `plugins/dekspec/skills/`.

The CLI grew an explicit group hierarchy (`check / audit / exec / library / dev`) during the v0.50.x sweep. Top-level legacy aliases (e.g. `dekspec validate`, `dekspec relink`, `dekspec migrate`) still parse via `LEGACY_COMMANDS` in `tooling/dekspec/cli.py`, but they print a `[DEPRECATED]` banner and are NOT permitted in skill bodies — skills are an authored surface and should always use the canonical, group-qualified form.

**`repo` → `library` rename (INT-136 / ADR-033).** The former `repo` namespace was renamed to `library` — every former `repo <verb>` is now canonically `dekspec library <verb>` (joining `library sync` from INT-135). `dekspec repo <verb>` is retained for **one transition release** as a deprecation alias: it prints a one-line `[DEPRECATED] 'dekspec repo <verb>' → use 'dekspec library <verb>'` notice on stderr and dispatches to the same handler. Skill bodies should use the canonical `library <verb>` form; the `repo <verb>` alias is tolerated for the transition window but should not be authored fresh.

---

## Active verbs

| Verb | Form | Purpose | Replaces |
|---|---|---|---|
| `dekspec check validate <path>` | `check <path>` | Validate one artifact's schema (single-file). | `dekspec validate <path>` |
| `dekspec check compile <path>` | `check <path>` | Parse a DekSpec artifact and (optionally) emit an enforcement output. | `dekspec compile <path>` |
| `dekspec check emit …` | `check <path>` | Emitter subcommand for compiled IR (contract-test / ci-gate / agents-md / etc). | `dekspec emit …` |
| `dekspec check aggregate …` | `check <path>` | Aggregate emitters across multiple artifacts. | `dekspec aggregate …` |
| `dekspec check allocate-ids …` | `check <path>` | Allocate / reconcile artifact IDs. | `dekspec id …` |
| `dekspec check lint-ib <path>` | `check <path>` | Lightweight Implementation Brief linter. | `dekspec lint-ib …` |
| `dekspec audit linkage` | `audit <graph>` | Cross-artifact linkage audit. | (no legacy form) |
| `dekspec audit relink` | `audit <graph>` | Re-derive backlinks from forward links. Add `--check` for dry-run. | `dekspec relink` |
| `dekspec audit doctor --at .` | `audit <graph>` | Full fidelity audit + drift check over a repo's spec tree. | `dekspec doctor` |
| `dekspec library init` | `library <library-op>` | Scaffold the DekSpec artifact directory tree. | `dekspec repo init` · `dekspec init` |
| `dekspec library sync` | `library <library-op>` | Reconcile the consumer repo to the installed engine (reconcile-only). | `dekspec repo upgrade` (acquisition removed, INT-135 / ADR-032) |
| `dekspec library author-target …` | `library <library-op>` | Resolve where a Creation-mode artifact lands (provisional vs canonical). | `dekspec repo author-target` |
| `dekspec library regen-indexes` | `library <library-op>` | Regenerate `*-index.md` files from the artifact tree. | `dekspec repo regen-indexes` |
| `dekspec library new-provisional …` | `library <library-op>` | Stamp a new provisional incubation folder. | `dekspec repo new-provisional` |
| `dekspec library cow-stage …` | `library <library-op>` | Copy-on-write staging for artifact-tree edits. | `dekspec repo cow-stage` |
| `dekspec exec session …` | `exec <exec-op>` | Session lifecycle (start / end / status / hooks / report). | `dekspec session …` |
| `dekspec exec runs …` | `exec <exec-op>` | List / show / reindex / gc per-run manifests. | `dekspec runs …` |
| `dekspec exec config …` | `exec <exec-op>` | Per-repo `.dekspec/config.yaml` get / set. | `dekspec config …` |
| `dekspec dev archeology …` | `dev <dev-op>` | Brownfield code-archaeology probes (coverage, etc). | `dekspec archeology …` |
| `dekspec dev ingest …` | `dev <dev-op>` | Brownfield-document ingest classifier. | `dekspec ingest …` |
| `dekspec dev graph export …` | `dev <dev-op>` | Export the DekSpec artifact dependency graph (json / dot / mermaid). | `dekspec graph …` |

---

## Retired verbs (do NOT use)

These top-level legacy aliases still parse (with a `[DEPRECATED]` banner) but MUST NOT appear in any file under `plugins/dekspec/skills/`. CI fails when one leaks in.

- `dekspec validate <path>` → use `dekspec check validate <path>` (group-qualified form is the only acceptable surface in skill bodies; rename landed in the v0.50.x verb sweep).
- `dekspec relink` → use `dekspec audit relink` (rename landed in the v0.50.x verb sweep; `--check` flag preserved across the rename).
- `dekspec migrate` (top-level) → use `dekspec repo migrate-ir` (rename + group landed in CHANGELOG ≥ v0.50.0; the `migrate-ir` form is also the canonical name under `repo`).
- `dekspec repo promote-provisional <slug>` — retired 2026-05-25 (F2 audit: zero CLI invocations in history; promotions were hand-promote). Hand-promote workflow is canonical; see `docs/dekspec-operating-guide.md` §Provisional Promotion. The CLI verb still parses but returns a non-zero exit with a pointer to the hand-promote workflow; the underlying promotion helpers (`dekspec.promote.plan_promotion` / `apply_promotion` / `render_plan`) remain importable as a Python API.

The legacy aliases survive in `LEGACY_COMMANDS` (in `tooling/dekspec/cli.py`) for consumer-side back-compat only — DekSpec's own authored surfaces (skills, methodology docs, release notes) are not permitted to fall back to them.

---

## How skills should reference these

Inline the verb in a fenced code block when the skill's Closing Step prescribes it — that gives copy-paste-ready operator guidance and keeps the surface auditable.

Link to this file (`_lib/cli_verbs.md`) from prose mentions for discoverability. Example: a skill that says "validate the artifact" in passing should follow with a link to this doc rather than inlining a raw verb that might rot.

CI fails if a retired verb (see above) appears anywhere under `plugins/dekspec/skills/`, regardless of whether it's a real invocation, a prose contrast, or a code fence — the gate is intentionally blunt. If a skill genuinely needs to discuss the old verb (e.g. migration prose explaining the rename), put that discussion in `_lib/` (the gate skips the `_lib/` subtree) or in this file (the gate skips this file by name).

The gate lives at `scripts/check-cli-verb-drift.sh` and is wired into CI after the ruff step and before the pytest step.
