---
purpose: Canonical CLI invocations for DekSpec verbs that skills reference. Skills SHOULD link to this file from their Closing Step prose rather than inline a raw verb. Renames are governed here; drift is caught by `scripts/check-cli-verb-drift.sh` in CI.
audience: Skill authors. The validating side is the CI gate; the discoverability side is here.
last-synced: 2026-05-25b
---

# DekSpec CLI Verbs — Single Source of Truth

This file is the canonical list of DekSpec CLI invocations referenced from skill bodies. When the CLI surface changes (verb renamed, moved under a new group, retired), this file is the first artifact to update. The companion CI gate (`scripts/check-cli-verb-drift.sh`) ensures retired verbs do not leak back into `plugins/dekspec/skills/`.

**ADR-042 flattened the CLI.** The nested group hierarchy (`check / audit / exec / library / dev`) from the v0.50.x sweep is now inverted: the flat `dekspec <verb>` forms are **canonical**, and the nested `dekspec <group> <sub>` forms are **one-release deprecated aliases** that still parse but print a `[DEPRECATED]` banner pointing at the flat successor. Skill bodies — an authored surface — must use the flat form. (This reverses the earlier polarity, where the group-qualified form was canonical.)

The `repo` namespace remains a deprecation alias for `library` (INT-136 / ADR-033); under ADR-042 both collapse to flat verbs (`init`, `sync`, `regen-indexes`). `dekspec repo <verb>` is tolerated for the transition window but should not be authored fresh.

---

## Active verbs

Under ADR-042 the canonical form is the flat `dekspec <verb>`. The **Deprecated alias** column shows the old nested form (still parses, prints `[DEPRECATED]`, must not be authored fresh).

| Verb (canonical, flat) | Purpose | Deprecated alias |
|---|---|---|
| `dekspec validate <path>` | Validate one artifact's schema (single-file). | `dekspec check validate` |
| `dekspec compile <path>` | Parse a DekSpec artifact and (optionally) emit an enforcement output. | `dekspec check compile` |
| `dekspec emit …` | Emitter subcommand for compiled IR (contract-test / ci-gate / agents-md / etc). | `dekspec check emit` |
| `dekspec aggregate …` | Aggregate emitters across multiple artifacts. | `dekspec check aggregate` |
| `dekspec id …` | Allocate / reconcile artifact IDs. | `dekspec check allocate-ids` |
| `dekspec lint-ib <path>` | Lightweight Implementation Brief linter. | `dekspec check lint-ib` |
| `dekspec audit` | Composite spec-graph health check. Fixes to convergence by default; `--check-only` reports (CI-safe). | `dekspec audit doctor` (report-only) |
| `dekspec audit linkage` | Cross-artifact linkage audit. | (no flat form yet — stays nested) |
| `dekspec lock-ready` | Advance lock-ready ACCEPTED artifacts to LOCKED (gated). | `dekspec audit lock-ready` |
| `dekspec relink` | Re-derive backlinks from forward links. Add `--check` for dry-run. | `dekspec audit relink` |
| `dekspec init` | Scaffold the DekSpec artifact directory tree. | `dekspec library init` · `dekspec repo init` |
| `dekspec sync` | Reconcile the consumer repo to the installed engine (reconcile-only). | `dekspec library sync` |
| `dekspec regen-indexes` | Regenerate `*-index.md` files from the artifact tree. | `dekspec library regen-indexes` |
| `dekspec find-spec-gaps` | Report source files no LOCKED Intent claims. | `dekspec dev archeology coverage` |
| `dekspec ingest …` | Brownfield-document ingest classifier. | `dekspec dev ingest` |
| `dekspec graph export …` | Export the DekSpec artifact dependency graph (json / dot / mermaid). | `dekspec dev graph export` |
| `dekspec session …` | Session lifecycle (start / end / status / hooks / report). | `dekspec exec session` |
| `dekspec config …` | Per-repo `.dekspec/config.yaml` get / set. | `dekspec exec config` |
| `dekspec migrate` | Full upgrade pipeline (verify-vendored → migrate-ir → migrate-artifacts). | (canonical top-level — no alias) |
| `dekspec library new-provisional …` | Stamp a new provisional incubation folder. | (no flat form yet — stays nested) |
| `dekspec library cow-stage …` | Copy-on-write staging for artifact-tree edits. | (no flat form yet — stays nested) |
| `dekspec library author-target …` | Resolve where a Creation-mode artifact lands. | (no flat form yet — stays nested) |

---

## Deprecated / retired verbs (do NOT author in skills)

ADR-042 makes the flat verb canonical. The **nested `<group> <sub>` forms** in the Deprecated-alias column above still parse (with a `[DEPRECATED]` banner) but MUST NOT appear in any file under `plugins/dekspec/skills/` — use the flat form. CI (`scripts/check-cli-verb-drift.sh`) fails when a deprecated nested form leaks in. Exceptions: the nested forms with "no flat form yet" (`audit linkage`, `library new-provisional` / `cow-stage` / `author-target`) are still canonical and permitted.

Genuinely retired (removed) verbs:

- `dekspec repo promote-provisional <slug>` — retired 2026-05-25 (F2 audit: zero CLI invocations in history; promotions were hand-promote). Hand-promote workflow is canonical; see `docs/dekspec-operating-guide.md` §Provisional Promotion. The CLI verb still parses but returns a non-zero exit with a pointer to the hand-promote workflow; the underlying promotion helpers (`dekspec.promote.plan_promotion` / `apply_promotion` / `render_plan`) remain importable as a Python API.

The nested aliases survive in `LEGACY_COMMANDS` / the group parsers (in `tooling/dekspec/cli.py`) for consumer-side back-compat only — DekSpec's own authored surfaces (skills, methodology docs, release notes) use the flat verbs.

---

## How skills should reference these

Inline the verb in a fenced code block when the skill's Closing Step prescribes it — that gives copy-paste-ready operator guidance and keeps the surface auditable.

Link to this file (`_lib/cli_verbs.md`) from prose mentions for discoverability. Example: a skill that says "validate the artifact" in passing should follow with a link to this doc rather than inlining a raw verb that might rot.

CI fails if a retired verb (see above) appears anywhere under `plugins/dekspec/skills/`, regardless of whether it's a real invocation, a prose contrast, or a code fence — the gate is intentionally blunt. If a skill genuinely needs to discuss the old verb (e.g. migration prose explaining the rename), put that discussion in `_lib/` (the gate skips the `_lib/` subtree) or in this file (the gate skips this file by name).

The gate lives at `scripts/check-cli-verb-drift.sh` and is wired into CI after the ruff step and before the pytest step.
