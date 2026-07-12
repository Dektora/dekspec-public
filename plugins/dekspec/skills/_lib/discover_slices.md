> Shared `_lib` prose helper called by `analyze-module-depth`,
> `orchestrate-module-deepening`, and the `audit-codebase --slices` consumers. This is
> not a triggerable skill — it carries no SKILL.md frontmatter and is never
> enumerated by the harness. A parent skill invokes this routine to produce (or
> refresh) the durable, committed architecture-slice manifest the `--scope`
> menus read.

# Discover Slices

Produce the durable `.dekspec/slices.json` manifest: re-run the LLM-free
clustering ENGINE to get RAW structural slices, ENRICH each with a
domain-anchored `name` + `domain_name`, and WRITE the full six-field record the
`--scope` consumers depend on. This routine never re-implements the graph or
clustering engine — it RE-RUNS it and adds the enrichment layer on top.

The mechanism lives in the companion script
`plugins/dekspec/skills/_lib/scripts/enrich_slices.py`. The prose below is the
operator-facing routine; the script is the executable mechanism. Shell it (or
call `enrich_and_write(repo)`) rather than hand-rolling any of these steps.

## Manifest contract (IC-018)

This helper conforms to Interface Contract **IC-018** (slice-discovery
manifest). The manifest at `<repo>/.dekspec/slices.json` is a JSON array of
six-field entries:

- `member_modules` — engine-owned, non-empty list of module paths.
- `globs` — engine-owned, non-empty list of repo-relative glob selectors (this
  is what a `--scope` consumer actually selects on).
- `cohesion_stats` — engine-owned dense-within signal.
- `coupling_stats` — engine-owned sparse-between signal.
- `name` — **helper-owned.** Required, non-null, NON-EMPTY, and UNIQUE across
  the array. This is the label shown in the `--scope` menu. The producer
  de-duplicates / disambiguates before write.
- `domain_name` — **helper-owned.** A non-empty domain noun, or `null` when no
  glossary / `CONTEXT.md` / AE anchor was found. `name` and `domain_name` are
  distinct roles: a null `domain_name` NEVER propagates into `name`.

The engine emits only the first four fields; this helper populates `name` and
`domain_name`.

## Procedure

1. **RUN the engine to get RAW structural slices.** Invoke the `dekspec slices`
   verb (or the public entry point `discover_slices(repo)` the companion calls).
   This RE-RUNS the deterministic, LLM-free graph + clustering engine — it never
   re-implements it. It returns the RAW four-field slices and writes the raw
   array to `.dekspec/slices.json` first.

2. **ENRICH each raw slice with `name` + `domain_name`.** For each raw slice,
   derive a non-empty `name`:
   - On a **dekspec repo**, anchor to domain nouns harvested from
     `CONTEXT.md`, `dekspec/domain-glossary.md`, and the declared AEs under
     `dekspec/`, by matching the slice's `member_modules` / `globs` path nouns
     against those sources. The matched noun phrase becomes `domain_name`; its
     slug becomes `name`.
   - On a **non-dekspec repo** (no `dekspec/` tree), SKIP AE/glossary
     reconciliation and fall back to a STRUCTURAL name derived from the
     dominant top-level package/dir of `member_modules`. In this case
     `domain_name` is `null`.
   - Enforce `name` UNIQUENESS: if two slices derive the same name,
     disambiguate deterministically (append a distinguishing path segment, or a
     `-2` / `-3` suffix) BEFORE write. NEVER emit an empty `name`.

3. **WRITE the durable committed manifest.** Write the FULL six-field array to
   `<repo>/.dekspec/slices.json` (UTF-8, two-space indent, trailing newline —
   mirroring the engine's encoding). Re-running this routine regenerates the
   manifest IN PLACE. The manifest is committed to version control (the
   `.gitignore` carries a scoped `!.dekspec/slices.json` negation so it is
   trackable even though the rest of `.dekspec/` is ignored).

## No partial manifest

If the verb / engine fails, surface the error and write NO partial manifest.
The companion performs enrichment fully in memory and writes the full enriched
array in a single write; on any engine OR enrichment exception it re-raises
without leaving a half-enriched file behind. Do not catch-and-continue — let
the error reach the operator so a broken graph is never silently committed.

## Refresh triggers (options — none hard-coded)

The manifest is a snapshot of the import graph at write time; it goes stale as
the code evolves. A parent skill or operator MAY refresh it via any of:

- **Manual re-run** — re-invoke this routine on demand before a deepening pass.
- **Pre-deepening hook** — refresh as the first step of
  `analyze-module-depth` / `orchestrate-module-deepening`.
- **CI staleness check** — a CI job that regenerates and diffs the manifest,
  flagging drift between committed and freshly-discovered slices.

This helper HARD-CODES none of these — the refresh policy is the consumer's
choice. The routine only knows how to (re)generate the manifest when asked.
