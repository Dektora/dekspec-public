# DekSpec CLI Reference

Complete per-flag reference for `dekspec`. Mechanically scraped from `argparse` help (run `dekspec <command> --help` for live output).

For tutorial-style examples → [`EXAMPLES.md`](EXAMPLES.md).
For the methodology / how-to-author → [`dekspec-operating-guide.md`](dekspec-operating-guide.md).

## Top-level

```
dekspec [-h] [-V] <command> ...
```

DekSpec — shared library and Constraint Compiler for Dektora projects.

Options:
- `-h, --help` — show top-level help and exit.
- `-V, --version` — print `dekspec X.Y.Z` and exit.

Top-level subcommands documented here:

| Command | One-line summary |
|---------|------------------|
| [`init`](#init) | Scaffold a new dekspec/ tree in the current repo. |
| [`compile`](#compile) | Parse a DekSpec artifact and (optionally) emit an enforcement output. |
| [`validate`](#validate) | Quick parse-only check (no persistence side effect). |
| [`audit`](#audit) | Run fidelity-audit checks (L-series linkage; failure-class trends). |
| [`aggregate`](#aggregate) | Aggregate compiled outputs across the whole spec graph. |
| [`verify-vendored`](#verify-vendored) | Compare consumer's vendored content against library source-of-truth. |
| [`graph`](#graph) | Inspect or export the spec graph (the union of all parsed IRs). |
| [`doctor`](#doctor) | Composite health check: vendoring + audit linkage + parse failures. |
| [`migrate`](#migrate-ir) | Migrate persisted IR JSON files forward through schema migrations. |
| [`runs`](#runs) | Inspect compile-run history persisted under `$XDG_DATA_HOME/dekspec/`. |
| [`ib`](#ib) | Execute an Implementation Brief directly: authorize, run, verify, review, complete (ADR-055 – ADR-057). |
| [`delivery`](#delivery) | Integrated verification and the landing gate for a branch (ADR-058). |
| [`intent`](#intent) | Intent outcome verification and evidence-backed completion (ADR-057). |
| [`session`](#session) | Bind a working session to an IB (or Intent); the commit-time scope guard. |

Universal flags repeated across subcommands:

- `--at PATH` — anchor the repo at PATH (default: cwd).
- `--dekspec-root PATH` — content tree relative to repo root (default: `dekspec`).
- `--json` — emit machine-readable output instead of formatted text.

## The flat surface (ADR-042)

The CLI is a **single-level, hyphenated verb-noun namespace**. Every command is a flat `dekspec <verb>`; the nested `dekspec <group> <sub>` forms (`check`/`audit`/`exec`/`library`/`dev`) are **one-release deprecated aliases** that still work but print a `[DEPRECATED]` notice pointing at the flat successor.

**Public verbs** (shown in `dekspec --help`) — the surface a human or CI uses without the harness:

| Verb | Purpose |
|------|---------|
| `audit` | Composite spec-graph health check. **Fixes to convergence by default**; `--check-only` reports without mutating (the CI-safe path). |
| `lock-ready` | Advance lock-ready ACCEPTED artifacts to LOCKED (a separate **gated** action — never folded into `audit`'s fix default). |
| `sync` | Reconcile the consumer repo to the installed engine version. |
| `init` | Scaffold a new `dekspec/` tree. |
| `regen-indexes` | Regenerate derived index files. |
| `ingest` | Classify inherited markdown into draft artifacts (brownfield adoption). |
| `find-spec-gaps` | Report source files no LOCKED Intent claims; feeds the recover-specs recovery workflow. |
| `migrate` | Full upgrade pipeline (verify-vendored → migrate-ir → migrate-artifacts). |
| `install` | Emit the per-host skill/command/hook tree for a harness platform. |
| `ib` | Execute an Implementation Brief directly — the construction surface (no code beads; ADR-056). |
| `delivery` | Integrated verification + landing gate at the delivery head (ADR-058). |
| `intent` | Intent outcome verification and completion (ADR-057). |

**Internal verbs** (reachable but hidden from top-level help) — skill/hook/pipeline plumbing, not part of the advertised surface: `compile`, `validate`, `doctor`, `relink`, `aggregate`, `emit`, `graph`, `session`, `id` (allocate-ids), `config`, `archeology`, `handoff`, `deepen-record`, `lint-ib`, plus the ADR-043 helpers.

> **CI note.** `dekspec audit` mutates (applies mechanical fixes to convergence) by design. In CI, always use `dekspec audit --check-only`.

## init

```
dekspec init [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--force]
```

Create the conventional `dekspec/` subdirectories, empty index files, and a starter AGENTS.md note. Idempotent — existing files are preserved unless `--force` is passed.

Options:
- `--at AT` — path to the consumer repo (default: cwd).
- `--dekspec-root DEKSPEC_ROOT` — subdirectory to create relative to repo root (default: `dekspec`).
- `--force` — overwrite existing index files / AGENTS.md placeholder.

Exit codes: `0` on success.

## compile

```
dekspec compile [-h] [--emit {ir,contract-test,ci-gate,agents-md}]
                [--output OUTPUT] [--treat-as-locked]
                [--affected-paths PATH1,PATH2,...] [--resolve-aes]
                path
```

Parse a DekSpec artifact (currently: Interface Contracts only for the emit path; the other 8 IR kinds parse + persist but have no executable emitter). Without `--emit`, just parses + persists. With `--emit`, writes the chosen emitter's output to stdout (or to `--output PATH`).

Positional:
- `path` — path to the source artifact (e.g. an IC markdown file).

Options:
- `--emit {ir,contract-test,ci-gate,agents-md}` — what to emit. Default: parse + persist only.
- `--output OUTPUT` — write emitter output to `PATH` instead of stdout.
- `--treat-as-locked` — bypass the LOCKED-status enforcement. PoC scaffold flag.
- `--affected-paths PATH1,PATH2,...` — override `IR.affected_paths`. Supplements / overrides `--resolve-aes`.
- `--resolve-aes` — for ICs only: walk `architecture-elements/`, parse each Provider/Consumer AE referenced via `parties[].ae_id`, and union their `implements_globs` into `IC.affected_paths`.

## validate

```
dekspec validate [-h] [--json] path
```

Parse an artifact and surface parse warnings + schema-validation errors. No run dir is created, no IR is persisted, no events are written. Useful for editor integration / pre-commit hooks.

Positional:
- `path` — markdown file (any of the 9 IR kinds).

Options:
- `--json` — emit warnings as JSON instead of formatted text.

## audit

```
dekspec audit [-h] <audit-command> ...
```

L-series cross-artifact linkage integrity. Other check families (T/D/E) remain in the `/doctor` skill.

### audit linkage

```
dekspec audit linkage [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT]
                      [--json] [--min-severity {P0,P1,P2,P3}]
                      [--fix] [--apply]
```

Walk the spec graph and emit per-rule findings.

Options:
- `--at AT`, `--dekspec-root DEKSPEC_ROOT` — repo anchor + content tree.
- `--json` — emit findings as JSON instead of a formatted table.
- `--min-severity {P0,P1,P2,P3}` — minimum severity to report. Default (unset): every tier (equivalent to `P3`).
- `--fix` — compute mechanical fix proposals (L6 backlink, L7 ADR supersession mirror, L8 Mission↔Intent mirror) and show before/after diffs. Dry-run unless `--apply`.
- `--apply` — used with `--fix`: actually write the proposed changes to disk.

Exit codes: `0` clean, `1` findings present, `2` parse errors.

### audit failure-classes

```
dekspec audit failure-classes [-h] [--at AT] [--window WINDOW]
                              [--by {class,type,risk-tier}]
                              [--format {md,json}] [--detect-reverts]
```

Read-only trend report over classified failed attempts. The source is the IB execution records — every `attempt.ended` event in `.dekspec/execution/*/record.jsonl` that names a `failure_class` (set with `dekspec ib attempt <IB> end --failure-class <class>`). Legacy code beads carrying a `failure-class:<class>` label in `.beads/issues.jsonl` are still read, for history. Rows are cross-referenced to the IB / Intent and, optionally, a revert SHA. Feeds the post-mortem ritual and class-lane decisions; writes nothing.

Options:
- `--at AT` — repo anchor (default: cwd).
- `--window WINDOW` — window in days. Default: `90`.
- `--by {class,type,risk-tier}` — aggregation axis. Default: `class`.
- `--format {md,json}` — report format. Default: `md`.
- `--detect-reverts` — best-effort `git log --grep` revert-SHA lookup (slower).

## aggregate

```
dekspec aggregate [-h] <aggregate-command> ...
```

Walk the SpecGraph and produce a single combined output.

### aggregate agents-md

```
dekspec aggregate agents-md [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT]
                            [--output OUTPUT] [--status STATUS]
                            [--include INCLUDE] [--check] [--migrate]
                            [--dry-run]
```

Generates, or checks, the **DekSpec-owned region** of the instruction file (ADR-063). DekSpec owns exactly the lines from `<!-- dekspec:agents-md begin -->` through `<!-- dekspec:agents-md end -->` (each alone on its line; markers inside fenced code are ignored). Generation replaces only that region with the governing core rendered from the specification graph and preserves everything else — handwritten text, other owners' `<!-- owner:block begin|end -->` blocks, a byte-order mark, CRLF line endings — byte for byte. By default only the **governing core** is projected; work items are left out because an agent receives its IB's binding obligations from `dekspec ib context IB-NNN`, generated from the same canonical sources (ADR-056).

**Ownership.** A missing or empty file is created containing only the region. A file with other content and no region is yours: DekSpec does not adopt it — place the two markers (an empty pair suffices) where the generated content belongs. Generation refuses, leaving the file untouched, on a second region, a nested or unmatched marker, another owner's block inside the region, DekSpec fragment markers outside the region, a specification graph with parse failures, output that would not parse back as exactly the rendered region (a source line that is a marker, or an unbalanced code fence — the source is named), a file that changed while it was being regenerated, and a symbolic link whose target is outside the repository (a link inside the repository is followed; its target is replaced and the link kept). Writes are atomic and keep the file's permission bits.

**Legacy layouts** — the whole-file output of earlier versions of this command, the historical `dekspec init` placeholder and the historical `dekspec install --platform codex` marker — are migrated only with `--migrate`; `--migrate --dry-run` prints the change as a diff and writes nothing. Recognition is by exact content shape, tolerating only CRLF/LF and byte-order-mark differences, never by filename. An old generated file's generated extent runs from its header through its last fragment end marker (`<!-- END dekspec-fragment: <id> -->`); content after that marker is kept, after the region. Inside the extent the file must be exactly what the old generator wrote: no other owner's `<!-- owner:block begin|end -->` line outside fenced code anywhere, and, from the first fragment on, nothing outside the fragments but blank lines, `---` separators and the old generator's fixed section headings and introductions. Anything else there — a fleet block, a handwritten sentence (even directly after a section's introduction), a fenced example or a heading the old generator never wrote, between fragments — means the file is not a recognized legacy layout: plain generation, `--migrate` and `--migrate --dry-run` refuse with exit 1 and the file unchanged, naming the first offending line by number, and `--check` reports it `invalid` (`absent` when the projection is configured). Recovery: move that content after the last fragment end marker, where migration keeps it after the region, or place the region markers by hand around the generated content. An old generated file without any fragment end marker is refused as well (place the markers).

**Destination and migration safety.** The configured/default projection must resolve inside the repository, including absolute or parent-relative paths and links in parent directories. Generation and migration previews refuse an escaping destination with exit 1 and preserve existing files, links and absent targets. A safe internal link remains a link while its target is replaced. An explicit, separate regular-file `--output` may be outside the repository; an output path traversing a link that resolves outside may not. File links, directory links and the resolved target of a configured link share the projection's settings restrictions (conflicting options exit 2).

Migration also refuses handwritten text in the legacy prefix's fixed scaffold and a fragment END without its first BEGIN, naming the offending line and recovery. The historical header, title, summary, optional guidance and first separator must appear in their emitted order before any unframed singleton body is recognized. An inserted Constitution, Vision, Security Profile or Glossary heading cannot confer ownership of text in that fixed prefix. Historical singleton bodies retain their fenced quotations and horizontal rules. Generation, migration and previews refuse to replace a region recording a newer renderer revision (exit 1); upgrade DekSpec before retrying. These refusals never change the destination.

**Determinism and settings.** The output has no timestamps, version stamps or machine paths. The region records its projection settings (source root, status filter, included kinds) and a renderer revision that changes only when rendering changes. The projection's settings are the `agents_md` block of `.dekspec/config.yaml` when declared, else the defaults:

```yaml
agents_md:
  path: AGENTS.md                       # default AGENTS.md
  status: [LOCKED, ACCEPTED]            # default; a list, a comma-separated string, or `all`
  include: [CONSTITUTION, SECURITY_PROFILE, VISION, GLOSSARY, AE, ADR, IC, WS]   # default
  required: true                        # default false
```

Writing the projection file with `--status`/`--include` that differ from its settings exits 2 asking you to declare them. Rendering to another `--output` path, or to `-` (prints the region, writes nothing), is ad hoc and accepts any settings.

**`--check`** recomputes the region read-only from the current sources and the projection's settings (never the file's header) and reports exactly one verdict:

| Verdict | When | Exit |
|---|---|---|
| `current` | the region matches the recomputation | 0 |
| `stale` | any difference — a changed, added or removed source, a status or scope change, a settings change, a hand edit inside the region, a never-generated (empty) region; a **renderer mismatch** (upgrade rather than regenerate with an older tool); or a recognized legacy layout, which needs migration | 1 |
| `absent` | a declared projection whose file is missing, empty or has no region | 1 when `required`, else 0 |
| `inapplicable` | nothing declared, and the file has no DekSpec marker and no legacy layout | 0 |
| `invalid` | malformed DekSpec markers, another owner's block inside the region, fragment markers outside it (including an old generated file holding content its generator never wrote before its last fragment end marker, when the projection is not configured), an old generated file without any fragment end marker, specification parse failures, or invalid configuration | 1 |

The same check is the `agents-md` section of `dekspec doctor` (doctor never regenerates). Only a configuration declaration can make doctor fail on it: with `agents_md` declared, stale and required-absent are warnings (exit 1) and invalid is critical (exit 2); an undeclared repository gets at most an advisory. This repository's CI runs `python -m dekspec.cli aggregate agents-md --check` as an explicit step.

Options:
- `--output OUTPUT` — write here instead of the projection file; `-` prints the region to stdout.
- `--status STATUS` — comma-separated status filter; `all` for every artifact. Default: the projection's settings (`LOCKED,ACCEPTED` unless configured).
- `--include INCLUDE` — comma-separated artifact kinds (any of `CONSTITUTION,SECURITY_PROFILE,VISION,GLOSSARY,AE,ADR,IC,WS,IB,INT,MSN`). Default: the projection's settings — the governing core `CONSTITUTION,SECURITY_PROFILE,VISION,GLOSSARY,AE,ADR,IC,WS` unless configured. Work items (`IB`, `INT`, `MSN`) are excluded unless named explicitly.
- `--check` — the read-only verdict above. Cannot be combined with `--migrate`, `--output`, `--status` or `--include` (exit 2).
- `--migrate` / `--dry-run` — migrate a recognized legacy layout; preview it.

An ADR that later ADRs revised (Amendment Log rows `Revised by ADR-NNN`) is projected with a **Revised by** line naming the in-filter revisers.

Exit codes (generation): `0` written or already current, `1` refused with the file unchanged, `2` usage error.

## verify-vendored

```
dekspec verify-vendored [-h] [--at AT] [--json]
```

Walk the canonical vendoring manifest (skills, templates, methodology docs, CLI reference, EXAMPLES.md) and report drift: modified files, missing files, unknown extras, and version-marker mismatch. Run from the consumer repo root after upgrading the dekspec library to know what to refresh via `install-dekspec.sh`.

Options:
- `--at AT` — consumer repo path (default: cwd).
- `--json` — emit findings as JSON instead of a formatted table.

Exit codes: `0` clean, `1` drift present.

## graph

```
dekspec graph [-h] <graph-command> ...
```

Today: `export` only.

### graph export

```
dekspec graph export [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT]
                     [--output OUTPUT] [--include INCLUDE] [--pretty]
                     [--format {text,json,mermaid,dot}]
```

Walk the spec graph and render it. Default `--format text` is a human-readable CLI summary grouped by artifact kind; `json` dumps every IR as a single document for downstream tooling; `mermaid` / `dot` emit a dependency graph for visualization.

Options:
- `--format {text,json,mermaid,dot}` — output format. Default: `text`. Pass `--format json` explicitly when piping to tooling.
- `--output OUTPUT` — write the rendered output to PATH instead of stdout.
- `--include INCLUDE` — comma-separated kinds (any of `AE,ADR,WS,IC,IB,INT,MSN,GLOSSARY,VISION`). Default: ALL.
- `--pretty` — pretty-print JSON with `indent=2` (`--format json` only). Default: compact (one IR per line).

## doctor

```
dekspec doctor [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--json]
```

Runs `verify-vendored`, `audit linkage`, and parse-failure detection in one pass and rolls up a traffic-light summary. Auto-skips categories that don't apply (e.g. no vendored content → skip `verify-vendored`). Useful for new users, pre-commit hooks, and CI.

Options:
- `--at AT`, `--dekspec-root DEKSPEC_ROOT` — repo anchor + content tree.
- `--json` — emit summary as JSON.

Exit codes: `0` clean, `1` warnings (CI passes), `2` critical (CI fails).

## migrate-ir

```
dekspec migrate-ir [-h] [--to VERSION] [--apply] [--json] path [path ...]
```

Reads one or more IR JSON files (typically from a per-run `<repo-state-dir>/runs/.../irs/<id>.ir.json`), runs them through the migration registry (`dekspec.migrations.default_registry`), and writes the upgraded IR back. Dry-run by default.

Renamed from `dekspec migrate` in v0.50.0 to disambiguate from `dekspec migrate-artifacts` (which handles markdown). The old `dekspec migrate` invocation is no longer accepted — update scripts that called it.

Positional:
- `path` — one or more IR JSON file paths. Shell handles glob expansion (e.g. `dekspec migrate-ir runs/*/irs/*.ir.json`).

Options:
- `--to VERSION` — target `ir_schema_version`. Default: latest registered for the artifact type.
- `--apply` — actually write the migrated IR back to disk. Without this, dry-run only.
- `--json` — emit per-file results as JSON.

## runs

```
dekspec runs [-h] <runs-command> ...
```

Four nested verbs.

### runs ls

```
dekspec runs ls [-h] [-n LIMIT] [--at AT] [--since SINCE] [--until UNTIL]
                [--artifact ARTIFACT] [--exit-code EXIT_CODE] [--milestone]
                [--min-warnings MIN_WARNINGS] [--json]
```

List recent runs.

Options:
- `-n LIMIT`, `--limit LIMIT` — max rows. Default: 20.
- `--at AT` — repo anchor.
- `--since SINCE` / `--until UNTIL` — ISO timestamp window.
- `--artifact ARTIFACT` — only runs that touched this artifact id (e.g. `AE-014`).
- `--exit-code EXIT_CODE` — filter by exit code.
- `--milestone` — only milestone runs.
- `--min-warnings MIN_WARNINGS` — only runs with at least N warnings.
- `--json` — emit as JSON.

### runs show

```
dekspec runs show [-h] [--at AT] [--json] run_id
```

Show one run's manifest + IR list.

Positional:
- `run_id` — full run id, run-dir-name prefix, or the literal `latest`.

Options:
- `--at AT` — repo anchor.
- `--json` — emit as single JSON document (manifest + IR refs + event count).

### runs reindex

```
dekspec runs reindex [-h] [--at AT]
```

Rebuild the SQLite index from on-disk `manifest.json` files. Useful after manual run-dir surgery or a corrupted index.

### runs gc

```
dekspec runs gc [-h] [--at AT] [--keep KEEP] [--dry-run]
```

Garbage-collect old runs while preserving milestone runs.

Options:
- `--keep KEEP` — number of most-recent non-milestone runs to keep. Default: 200.
- `--dry-run` — list candidates without removing them.

## resource (internal)

```
dekspec resource {template,doc,lib,role} NAME [--at AT] [--path-only]
```

Used by skills and agents rather than typed by users (hidden from top-level help). `template`, `doc` and `lib` resolve a wheel-vendored asset; a consumer copy under `dekspec/` overrides it. `role` prints the dispatch-ready role layer of one of the six Agent Role Specifications (ADR-061): `specifier`, `spec-reviewer`, `implementer`, `code-reviewer`, `verifier`, `auditor`, or a retired id `CS-001`…`CS-006`. It always resolves from the installed library; no project file overrides a role and `--at` does not apply. Exit `2` for an unknown role, `1` for a missing or malformed definition (a broken installation). Retired names (`template context-spec`, `lib reviewer_mode`) are refused with what replaces them.

## ib

```
dekspec ib [-h] <ib-command> ...
```

The construction surface. An accepted Implementation Brief is executed directly — there are no code beads (ADR-056). Ownership, the executor's plan and internal tasks, attempts, deviations, blockers, acceptance baselines, evidence, review verdicts and completion all live in the IB's **execution record**: `.dekspec/execution/<IB>/record.jsonl`, an append-only JSON-lines event log in which every event carries the SHA-256 of the previous one, so a hand edit, deleted line or spliced event breaks the chain and is reported (`record-integrity`). The record is committed durable state beside the spec corpus; it is never compiled into IR or projected into `AGENTS.md`. Current state is always folded from the events — there is no separate status to keep in sync.

The IB markdown file carries only decisions: `DRAFT` → `PROPOSED` (`ib propose`) → `ACCEPTED` (`ib accept`) → `COMPLETE` (**only** `ib complete`), plus `SUPERSEDED` / `DEPRECATED` (ADR-057). Each transition the CLI makes also appends an Amendment Log row to the IB.

Every verb except `new` and `ready` takes the IB as its first positional:
- `ib` — IB id (`IB-NNN`) or a path to the IB file.

Common options (every `ib`, `delivery` and `intent` verb):
- `--at AT` — repository root. Default: the git top level of the cwd.
- `--dekspec-root DEKSPEC_ROOT` — spec tree relative to the repo. Default: `dekspec`.
- `--base BASE` (on the verbs that take it) — the delivery's base branch. Default: `$DEKSPEC_BASE`, then `main` / `origin/main` / `master`. An Implementation Run sets `DEKSPEC_BASE` for every worker, so a worker's unqualified commands use the run's base.
- `--actor ACTOR` — identity recorded for this action. Default: `$DEKSPEC_ACTOR`, then `git config user.name`. Identities matter: a builder (the run owner or an attempt actor) can never record the review verdict or authorize an amendment.
- `--json` — machine-readable output.

Exit codes (`ib`, `delivery`, `intent`): `0` ok · `1` refused / gate not satisfied (`REFUSED: …` on stderr) · `2` usage error · `3` blocked (`BLOCKED: …` — a truthful blocked outcome: attempts exhausted, no progress, stalled, prerequisite unavailable, contract conflict).

**Authority policy.** Execution, verification, review and completion apply only to IBs whose header says `**Authority policy:** delegated` (ADR-055). A `legacy` IB — every pre-existing IB, stamped by `dekspec migrate` — keeps its ADR-049 meaning and is refused by these verbs until it is rewritten (`/write-ibs --adopt`) and adopted (`dekspec ib adopt`). `ib context` still renders a legacy IB, with the legacy escalation rules.

### ib new

```
dekspec ib new [-h] [--title TITLE] [--parent PARENT] [--at AT]
               [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
               slug
```

Scaffold a delegated IB from the Implementation Brief template at `dekspec/impl-briefs/IB-NNN-<slug>.md` (next free number; status `DRAFT`; a `Create` Amendment Log row). No parent artifact is required — a bounded change is one IB (ADR-056).

Positional:
- `slug` — filename slug (lower-cased, non-alphanumerics folded to `-`).

Options:
- `--title TITLE` — the IB title. Default: the slug with spaces.
- `--parent PARENT` — optional parent Intent / WS / Mission id (`INT-NNN`, `WS-NNN`, `MSN-NNN`), written to `**Parent:**`.

### ib lint

```
dekspec ib lint [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json] ib
```

Check that the IB is an executable contract: delegated policy, a non-empty Outcome, Scope globs, at least one valid acceptance condition, no parse warnings, and every obligation reference resolving to an approved, in-force source. Exit `1` with the problem list otherwise. (The older structural linter is `dekspec lint-ib <path>`.)

### ib propose

```
dekspec ib propose [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json] ib
```

`DRAFT` → `PROPOSED`: request authorization. Lint-gated — refused while `ib lint` would report a problem.

### ib accept

```
dekspec ib accept [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json] ib
```

`PROPOSED` → `ACCEPTED`: authorize execution and take the **acceptance baseline** — the IB's contract hash (binding + acceptance sections), a hash of every acceptance asset (test files named by the conditions plus declared fixtures; assets not yet written are listed as absent), and a hash of the runner inputs that can change what a test means (test-runner configuration, ancestor `conftest.py` files). Refused unless the IB is `PROPOSED`, its references resolve, and every `Depends on` IB exists. The baseline's digest is the floor digest [`ib floor`](#ib-floor) states for the same assets. For an IB with test conditions or declared assets, write and oracle-review the acceptance tests first, and accept only when a `Floor reviewed: PASS` row names that digest (see [`ib baseline`](#ib-baseline)).

### ib baseline

```
dekspec ib baseline [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                    --reason REASON ib
```

Refresh the acceptance baseline **before execution starts** — for example after writing the acceptance tests red-first (`/write-tests`). Refused once `ib start` has run; after that only `ib amend` changes the baseline.

**Take the baseline only over a reviewed floor (ADR-062).** For an IB with test conditions or declared assets, take or refresh the baseline only when a recorded passing floor review names its digest:
- Run [`ib floor`](#ib-floor) first. Every new node must be genuine red with a declared basis, and every preserved node must pass. The report states the digest this command would record.
- An independent oracle reviewer (`/review-ib`) judges the report and the test sources. The reviewer is never the test author or the builder. On a pass, it records a row in the IB's Amendment Log whose Change text starts `Floor reviewed: PASS` and contains `digest <64 hex>`, naming that digest. A row that records any other outcome (`Floor reviewed: FAIL …`) is not a passing review and does not count.
- Refreshing after the tests change produces a new digest. Repeat the oracle review of the changed tests and record a new row; a row that names an older digest no longer counts.

This command does not check the rule itself. `/implement` readiness enforces it before a run starts: `acceptance-floor-unreviewed` when no passing review row names the current baseline's digest, and `acceptance-tests-missing` when a named node or declared asset is absent from the baseline (see [`implement ready`](#implement-ready)). Protected acceptance tests are therefore never first written by the builder during an `/implement` run.

Options:
- `--reason REASON` — why the baseline is refreshed (required).

### ib amend

```
dekspec ib amend [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                 --reviewer REVIEWER --reason REASON ib
```

Recorded amendment of the acceptance contract after execution started: re-hashes contract, assets and runner inputs, records what changed, and requires the completing review verdict to acknowledge it (ADR-057). The decision is also written to the IB's own Amendment Log with its reason and record sequence, so it stays traceable in the durable spec rather than only in the execution history (ADR-056 §7). The reviewer runs it (`--actor` must equal `--reviewer`); the implementer never approves its own amendment.

Options:
- `--reviewer REVIEWER` — the independent reviewer authorizing the amendment (required; refused if it is a builder identity).
- `--reason REASON` — the reason (required).

### ib context

```
dekspec ib context [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                   [--out OUT] ib
```

Generate the execution context — the dispatch input for the implementing agent: the IB contract, the canonical current text of every referenced obligation with its source path, status and content hash, the precedence order (binding obligations → acceptance conditions → implementation hypothesis → everything else as information), the bounded escalation list (ADR-055), and a manifest hash. It is a derived snapshot, never an editable authority; regenerate it rather than copying from it. Exit `1` if any reference does not resolve (superseded, deprecated, missing or unapproved source).

Options:
- `--json` — emit the packet as JSON instead of markdown.
- `--out OUT` — write to a file instead of stdout.

### ib start

```
dekspec ib start [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                 [--owner OWNER] [--takeover] [--base BASE] ib
```

Start or resume the IB's run: records ownership, binds the generated context's manifest, and runs each `## Environment Prerequisites` probe. Refused unless the IB is `ACCEPTED` with a baseline, not already complete, every `Depends on` IB is `COMPLETE`, and its obligations resolve. A failed required probe raises a `prerequisite-unavailable` blocker (exit `3`).

Options:
- `--owner OWNER` — run owner. Default: the actor.
- `--takeover` — transfer ownership from another agent (recorded).

### ib plan

```
dekspec ib plan [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                --file FILE [--takeover] ib
```

Commit or revise the executor's plan. Investigation comes first: the **first** revision must record findings. Plans carry no authority — closing every task proves nothing; the acceptance evidence does.

Options:
- `--file FILE` — plan YAML path, or `-` for stdin (required).
- `--takeover` — allow rewriting a task another agent has in progress (recorded).

Plan YAML:

```yaml
findings:               # required on the first revision; every key non-empty ("none" is fine)
  inspected: [tooling/dekspec/foo.py, tests/test_foo.py]
  contracts: [ADR-036, IC-012 §Shape]
  reuse: [dekspec.diff_confinement.matches_any_glob]
  uncertainties: [none]
rationale: optional free text
tasks:                  # or, instead of tasks, `direct: true` (one continuous run)
  - id: T-parse         # T-<letters/digits/._->
    title: parse the new field
    covers: [AC-1, AC-2]   # acceptance condition ids this task serves
    depends_on: []
    files: [tooling/dekspec/foo.py]
  - id: T-cli
    covers: [AC-3]
    depends_on: [T-parse]
    files: [tooling/dekspec/cli.py]
```

A plan is either `direct: true` (the IB is carried out in one continuous run and verified at IB level) or a task list — never both. A revision is refused when it: leaves an acceptance condition uncovered (task plans); names an unknown or cyclic dependency; removes a done task or narrows what it covered; reuses a retired task id; rewrites another agent's in-progress task without `--takeover`; or plans a file outside the IB's Scope (a scope expansion needs an IB amendment, not a replan). An in-Scope file the Implementation Hypothesis did not name is allowed and recorded as a deviation.

### ib task

```
dekspec ib task [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                [--note NOTE] [--evidence EVIDENCE] [--takeover]
                ib {claim,done,block,release} task
```

Move an internal task of the current plan. `claim` refuses a task already done, in progress by someone else (without `--takeover`), or waiting on undone dependencies.

Positional:
- `{claim,done,block,release}` — the action.
- `task` — task id from the plan (e.g. `T-parse`).

Options:
- `--note NOTE` — free-text note.
- `--evidence EVIDENCE` — pointer to what shows the task done (informational; completion never relies on it).
- `--takeover` — take over a task another agent holds (recorded).

### ib attempt

```
dekspec ib attempt [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                   [--task TASK] [--outcome {passed,failed,error,abandoned}]
                   [--failure-class FAILURE_CLASS] [--summary SUMMARY]
                   ib {start,heartbeat,end}
```

Counted attempts — the bound on execution (ADR-057). Counts live in the record, so they survive restarts and new sessions.
- `start` — open attempt *n* of the allowed maximum (`execution.max_attempts` plus any `--extra-attempts` granted by `ib unblock`). Refused while the run is blocked or an attempt is still open; starting beyond the limit raises `attempts-exhausted` (exit `3`).
- `heartbeat` — keep the open attempt alive. An attempt with no heartbeat for `execution.stall_minutes` is closed as `stalled`, counted, and blocks the run; the sweep runs on every interaction with the record.
- `end` — close the open attempt with an outcome. Ending can raise `attempts-exhausted` or `no-progress` (the last `execution.no_progress_attempts` attempts satisfied no new condition and returned to already-seen content); exit `3` when it does.

Positional:
- `{start,heartbeat,end}` — the action.

Options:
- `--task TASK` — task the attempt works on (`start`).
- `--outcome {passed,failed,error,abandoned}` — `end` outcome. Default: `failed`.
- `--failure-class FAILURE_CLASS` — classify a failed attempt; read by `dekspec audit failure-classes`.
- `--summary SUMMARY` — note for `heartbeat` / `end`.

### ib verify

```
dekspec ib verify [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                  [--base BASE] [--dry-run] ib
```

Run every acceptance condition and record evidence bound to the current content. Test conditions run through a per-node reporting plugin: a node that is skipped, expected-to-fail, deselected or not collected does **not** pass, and a condition whose file was deleted or renamed fails. Command conditions need exit status `0`. Review conditions are reported as needing a verdict. Also runs the scope and protected-surface check against the base (inside a multi-IB delivery the allowed scope is the union of the co-delivered IBs' scopes and every protected surface applies), checks `**Spec impact:**` specs were actually modified, and checks acceptance integrity (contract, asset and runner-input hashes against the baseline). In-Scope changes the hypothesis and plan did not name are recorded as deviations — no permission needed. A `.dekspec/config.yaml` change confined to the workflow setting (`integration.base`) is bookkeeping; any other DekSpec state (the `execution:` settings above all) or test-runner configuration is always judged as the IB's change. Evidence records the implementation fingerprint (a content hash of the repository excluding execution records, generated indexes and lifecycle bookkeeping), contract hash, baseline digest and context manifest hash; any later change makes it stale. Applies to `ACCEPTED` (and `COMPLETE`) delegated IBs. Exit `0` only when the overall result is `passed`.

**Bytecode.** The same rule holds in every acceptance run (`ib verify`, `ib floor`, `delivery check --rerun`, the `/implement` driver):
- **Reviewed files always run from source, by any path.** Every Python file the implementation fingerprint covers runs from its current source. No bytecode for it is read, in any invalidation mode: not from the repository's `__pycache__`, not from the bytecode cache, and not from pytest's assertion-rewrite cache, even when a file has been planted in one of them. This holds for the file's own path and for every other path that reaches it through the test interpreter's path entries: a symbolic link to it or to a directory holding it (as `flit install --symlink` and setuptools' strict editable mode make), a hard link, or a mount. Before each run those entries are scanned for such paths. Bytecode is neither read nor written at them, nor at the repository's own paths, so a subprocess a test starts cannot read any back. A run does not count when those entries change while it runs, or when it compiled a reviewed file by a path a test made during it (a link in a temporary directory, say). The condition is then run again from source without the cache, and that result is reported.
- **The interpreter's own modules are compiled once.** Bytecode for modules outside the fingerprint (the test interpreter's standard library and site-packages, and a virtual environment the repository ignores) is compiled at most once per interpreter and source version and reused by later runs. It is kept outside every repository, at `$XDG_CACHE_HOME/dekspec/bytecode/` (default `~/.cache/dekspec/bytecode/`; a relative `XDG_CACHE_HOME` is ignored). The location is resolved from the environment at each run.
- **Nothing is written in the repository, and the cache cannot change an outcome.** A run writes no bytecode inside the repository, and the cache is never followed out of itself: a symbolic link found in it is removed, never followed. When the cache is missing, unwritable or corrupt, the run compiles from source and reports the result it would have reported with a working cache. Before every run, whatever its outcome, the cached files it may use are checked: any the interpreter would fail to load is removed, and so is bytecode whose source no longer exists. Deleting the directory is always safe.

Options:
- `--base BASE` — base branch for the scope diff. Default: `$DEKSPEC_BASE`, then `main` / `origin/main`.
- `--dry-run` — run the checks without recording evidence.

### ib floor

```
dekspec ib floor [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--json] ib
```

The **acceptance floor report** (ADR-062). It shows the author and the oracle reviewer the same reproducible facts before the acceptance baseline is taken. For each criterion, it lists the test nodes. For each node, it gives:
- whether the node is new or preserved;
- its failure kind and failure line;
- the expectation basis it declares.

It also states the floor digest.

**Read-only.** It accepts a delegated IB in any status (`DRAFT`, `PROPOSED`, `ACCEPTED`, …) and writes nothing. It records no evidence, creates no execution record and leaves the working tree unchanged. For that reason it takes no `--actor` or `--base`.

**What runs.** Only `pytest:` conditions run, as `ib verify` runs them: the same interpreter, nodes, configuration, per-node reporting plugin and timeout. One difference: the floor's run records every failure message and the captured output in full. It sets pytest's verbosity to 2 (`--verbosity=2`, and `-o verbosity_assertions=2` when the repository's pytest configuration sets that key), because at `ib verify`'s `-q` pytest cuts each repr in an assertion message to 240 characters. It also lifts the plugin's length caps. `ib verify`'s own run, and its pass/fail outcome, are unchanged. `command:` and `review:` conditions are listed as not assessed. An IB with no test conditions reports `0 assessed` and exits `0`.

**New or preserved (read from history, never declared).**
- **Origin.** The IB's first commit is the earliest commit that added its file under any name (`git log --follow --diff-filter=A`; renames and renumbering are followed). The origin is that commit's parent, or the empty tree for a root commit.
- **Preserved.** A node is `preserved` only when its test file existed at the origin and its test function is textually identical there. The comparison covers the function's source span, decorators included. A parameter suffix (`test_x[case]`) maps to its function, and a class-qualified id (`TestA::test_b`) maps to the method.
- **New.** Every other node is `new`. That includes any node in a test file first added at or after the IB's first commit, and a preserved function edited after the origin (fail-safe: restore it, or leave it to the reviewer).
- **Uncommitted IB.** When the IB file is not committed yet, every node is `new`, and the report notes that the IB must be committed to distinguish preserved nodes.
- **What each needs.** A preserved node must pass and needs no basis. A new node must be genuine red and declare a basis.

**Failure kinds.** The kind is decided from the node's per-phase outcomes and the failure details the evidence plugin records.

| Kind | Meaning |
|---|---|
| `genuine-red` | The call phase failed with an assertion-class failure: `AssertionError`, or pytest's own failure outcome such as an expected exception that was not raised. No recognized signature appears in the failure's message or the captured output. This is the only kind that counts as red-first. |
| `usage-exit` | An argparse usage signature appears: `invalid choice:`, `unrecognized arguments:`, `the following arguments are required:` or `error: argument`. This covers an in-process parser exit, and an assertion that fired because a command the test runs rejected its arguments. |
| `import-error` | An import signature appears: `ModuleNotFoundError`, `No module named` or `ImportError: cannot import name`. |
| `missing-symbol` | A missing-symbol signature appears: `has no attribute` or `NameError`. |
| `other-exception:<Type>` | The call phase raised another exception with no recognized signature. `<Type>` is the exception's class name. |
| `setup-error` | A fixture's setup (or teardown) failed. |
| `collection-error` | The node's module could not be collected. A node that did not run beside a collection error elsewhere in its run gets this kind too, because pytest stops the whole session there. |
| `not-collected` | The node was never collected, and no collection error explains it. |
| `skipped` | The node was skipped. |
| `xfail` | The node was expected to fail, or unexpectedly passed under `xfail`. |
| `deselected` | The node was deselected. |
| `passed` | The node passed. |

Signature rules:
- **The signature decides the kind over the exception type.** An in-process `SystemExit` from argparse is `usage-exit`, and an `AttributeError` naming a missing attribute is `missing-symbol`.
- **Signatures are read only for a failed call phase.** They are checked in the order usage, import, missing symbol. A failed setup is `setup-error` whatever its message says.
- **Signatures are matched only in two places:** the failure's own message chain (its message, then its causes and contexts) and the node's captured stdout/stderr. Both are read in full, so a usage error inside a long `CompletedProcess` repr — one that `pytest -q` would cut — is still found.
- **The exception type comes from the exception info.** It is never parsed from the message.
- **The test's source is never scanned.** Pytest's assertion rewriting puts the asserted expression into the message, so an assertion whose own expected literal contains a signature is reported as that kind. This is fail-safe: rephrase the literal.

Every failing node prints its **failure line**, `<file>:<line>: <message>`. The file is relative to the repository root. The line is the last frame in the test's own file, or the raising frame. The message is the exception's own text. A collection error prints the collector's failure line.

**Expectation basis.** The report gives each basis as the text after its `Basis:` label, verbatim, with the comment marker, any stamp and the label removed. These forms declare one:
- a comment that starts with `Basis:` (`# Basis: …`);
- a comment that carries a write-tests assertion stamp and then the label: `REQUIRED`, `GIVEN` or `INCIDENTAL`, followed by `.`, `:` or whitespace and any stamp text, then `Basis:` (`# REQUIRED. Basis: …`, `# REQUIRED: <stamp text> Basis: …`). A stamp without `Basis:` declares none;
- a docstring line that starts with `Basis:`.

Where it looks:
- **Own basis:** the test function's docstring, and comments within its span (decorators included).
- **Inherited basis:** the enclosing class's docstring, the module docstring, and module-level comments. These apply to every test in that scope and are marked `inherited: true`.
- **None:** a node without a basis gets an empty list, shown as `basis: none declared`.
- **Unreadable:** a test file that does not parse reports `unreadable` instead of a list.

Code never judges whether a basis is adequate. The oracle reviewer does.

**Floor digest.** This is the digest `ib accept` or `ib baseline` would record for the current acceptance assets. It is the same computation: SHA-256 over the contract hash, the asset hashes and the runner-input hashes. For unchanged assets it equals the recorded baseline's digest, and it changes once an asset, a runner input or the contract changes. On a passing review the oracle reviewer names it in the `Floor reviewed: PASS` Amendment Log row, and `/implement` readiness compares that row with the baseline (see [`ib baseline`](#ib-baseline)).

**Output.** The human report has:
- `IB-NNN: acceptance floor OK|NOT OK`, then the digest and any note;
- per condition, each node with its class, kind, basis lines, failure line and the reason it does not meet the floor (`! a new node must be genuine red`, `! no basis declared`, `! a preserved node must pass`);
- a closing `N assessed` count.

`--json` prints:

```json
{"ib": "IB-NNN", "digest": "<64 hex>", "ok": false,
 "conditions": [
   {"id": "AC-1", "kind": "pytest", "assessed": true,
    "nodes": [{"node": "tests/test_x.py::test_y", "class": "new", "kind": "genuine-red",
               "failure_line": "tests/test_x.py:12: AssertionError: assert 3 == 4",
               "basis": [{"text": "worked example from ADR-062", "inherited": false}]}]},
   {"id": "AC-9", "kind": "review", "assessed": false, "nodes": []}]}
```

In the JSON:
- `class` is `new` or `preserved`;
- `failure_line` is `null` for a node without a failure;
- an empty `basis` list means none was declared, and the string `"unreadable"` replaces the list when the test file does not parse.

Exit codes:
- `0` — every new node is genuine red with a declared basis and every preserved node passes. Also `0` when nothing is assessed.
- `1` — otherwise. Also `1` for a legacy IB (`REFUSED: … has no delegated acceptance contract` on stderr) and when the runner produces no report.
- `2` — a usage error (argparse's message), or an unknown IB. An unknown IB prints `ERROR: unknown IB <ref>: …` naming it, which is distinct from a usage error.

### ib review

```
dekspec ib review [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                  --reviewer REVIEWER --verdict {pass,fail}
                  [--criteria [CRITERIA ...]] [--acknowledge [ACKNOWLEDGE ...]]
                  [--notes NOTES] [--policy-revision N] ib
```

Record an independent review verdict bound to the current fingerprint, contract hash, baseline, context manifest and the `code-reviewer` Agent Role Specification's policy stamp (ADR-061). Refused when the reviewer is a builder of the IB, when the acting identity (`--actor` / `DEKSPEC_ACTOR`) is not `--reviewer`, when the role definition cannot be loaded, and when the policy revision the review was dispatched under is no longer current. A verdict recorded under an older policy revision stops satisfying the completion gate: the IB needs a fresh review. A later change carries the verdict forward only if it touches none of the reviewed surfaces (scope, protected surfaces, acceptance assets, runner inputs, governing sources); otherwise a fresh review is needed.

Options:
- `--reviewer REVIEWER` — reviewer identity (required).
- `--verdict {pass,fail}` — the verdict (required).
- `--criteria [CRITERIA ...]` — review conditions covered (e.g. `AC-4`). Default: all review conditions.
- `--acknowledge [ACKNOWLEDGE ...]` — attention items acknowledged: amendments, assets first created during execution, runner-input changes (`ib verify` lists them under "needs reviewer acknowledgment").
- `--notes NOTES` — free-text notes.
- `--policy-revision N` — the `code-reviewer` policy revision the review was performed under (shown in the role's header). Omitted, a worker dispatched by `/implement` uses the revision in its `DEKSPEC_ROLE` (`<role>@<revision>`); a worker dispatched in another role is refused.

### ib gate

```
dekspec ib gate [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json] [--base BASE] ib
```

Evaluate the completion gate without writing anything (a stalled attempt is reported, not swept). Exit `0` when `ib complete` would succeed.

### ib complete

```
dekspec ib complete [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json] [--base BASE] ib
```

The only path to `COMPLETE` (ADR-057). Evaluates the gate and, if every check passes, records `completion.recorded` and sets `ACCEPTED` → `COMPLETE`. Gate checks: `delegated-contract`, `authorized`, `record-integrity`, `run-recorded`, `attempt-recorded`, `investigation-recorded` (a plan revision with findings; a `direct: true` plan suffices), `no-active-blocker`, `dependencies-complete`, `obligations-resolve`, `acceptance-integrity` (every baseline change amended and acknowledged), `evidence-present`, `evidence-current`, `acceptance-passed`, `scope-and-protected-surfaces` (including spec impact), and `independent-review` (latest verdict passes, is independent, is current or carried forward, covers every review condition and acknowledges every attention item). Task closure or tracker closure never substitutes. Exit `1` with the failing checks otherwise.

Options:
- `--base BASE` — the delivery's base branch for the scope check (default: `$DEKSPEC_BASE`, then `main`, `origin/main`, `master`). Pass it for a delivery based elsewhere — a stacked pull request or a release branch — or base-branch work merged in after authorization is charged to the IB. `ib status`, `ib gate`, `ib start`, `ib ready` and `intent complete` take the same option, and `delivery check --base` passes it to every IB's gate: one delivery-base context for scope, historical provenance and dependency completion (ADR-057).

### ib status

```
dekspec ib status [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json] [--base BASE] ib
```

Derived execution state: IB status, authority policy, run phase, owner, attempts used / allowed (and the open attempt), blockers, plan revision and tasks, deviation / evidence / verdict counts, record integrity, and — for an accepted delegated IB with a baseline — the completion gate. Always exit `0`.

### ib block

```
dekspec ib block [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                 --reason {attempts-exhausted,no-progress,stalled,prerequisite-unavailable,contract-conflict,scope-expansion,acceptance-invalid,other}
                 [--detail DETAIL] ib
```

Record a blocked outcome on a running IB — for example an ADR-055 escalation (`contract-conflict`, `scope-expansion`, `acceptance-invalid`). Completion and new attempts are refused until `ib unblock`. Exits `3`.

Options:
- `--reason` — one of `attempts-exhausted`, `no-progress`, `stalled`, `prerequisite-unavailable`, `contract-conflict`, `scope-expansion`, `acceptance-invalid`, `other` (required).
- `--detail DETAIL` — what is blocking.

### ib unblock

```
dekspec ib unblock [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                   --decision DECISION [--extra-attempts EXTRA_ATTEMPTS] ib
```

Record the decision that resolves every active blocker. Refused when the run is not blocked.

Options:
- `--decision DECISION` — the decision (required, non-empty).
- `--extra-attempts EXTRA_ATTEMPTS` — attempts added to the allowance. Default: `0`.

### ib ready

```
dekspec ib ready [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
```

The coding pull surface: `ACCEPTED` delegated IBs whose `Depends on` IBs are all `COMPLETE` and that no run has started. Prints `0 IBs ready` when empty. (`br ready` is not the coding pull surface; the `br` workspaces are for issue and governance backlogs.)

### ib import-beads

```
dekspec ib import-beads [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                        [--source SOURCE] ib
```

Legacy migration: import a legacy IB's code beads (those whose `external_ref` names the IB) into its execution record as internal tasks, keeping id, title, status, owner, dependency edges and closure evidence. The beads themselves are untouched; the import is idempotent per bead.

Options:
- `--source SOURCE` — bead JSONL. Default: `.beads/issues.jsonl`.

### ib adopt

```
dekspec ib adopt [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                 --reason REASON ib
```

Switch a rewritten legacy IB to the delegated policy, deliberately (ADR-055). The IB must already declare `**Authority policy:** delegated` after its author classified each legacy constraint (`/write-ibs --adopt`), be an executable contract, and be `PROPOSED` or `ACCEPTED`. Records the adoption (and, for an `ACCEPTED` IB, the adoption baseline) and an Amendment Log row. Adoption migrates legacy work only: it is refused when the IB was never committed under the legacy policy, when a delegated acceptance baseline already exists (change acceptance with `ib amend` instead), when the actor is one of the run's builders, and when the IB was already adopted.

Options:
- `--reason REASON` — why (required).

### A worked sequence

```bash
dekspec ib new retry-backoff --parent INT-042
dekspec ib lint IB-108
dekspec ib propose IB-108
# /dekspec:write-tests writes the acceptance tests red-first, with a surface skeleton
dekspec ib floor IB-108            # new nodes genuine red with a basis; states the floor digest
# /dekspec:review-ib (independent oracle review) records "Floor reviewed: PASS — digest <floor digest> — …"
dekspec ib accept IB-108           # the baseline digest equals the reviewed floor digest
# tests changed before start? repeat the floor review, then:
#   dekspec ib baseline IB-108 --reason "acceptance tests revised; floor re-reviewed"
dekspec ib context IB-108 --out ib-108-context.md
dekspec ib start IB-108
dekspec ib plan IB-108 --file plan.yaml
dekspec ib attempt IB-108 start
dekspec ib attempt IB-108 heartbeat --summary "retry loop in place"
dekspec ib verify IB-108
dekspec ib attempt IB-108 end --outcome passed
dekspec ib review IB-108 --reviewer alice --verdict pass
dekspec ib complete IB-108
dekspec delivery verify
dekspec delivery check
```

Who runs what:
- The specifier writes the IB and its acceptance tests.
- An independent reviewer (never the test author) records the floor review before `ib accept`.
- The builder runs `ib context` through `ib verify` / `attempt end`.
- `ib review` comes from someone other than the builder.
- `delivery check` runs again in CI and immediately before the operator-confirmed merge.

## delivery

```
dekspec delivery [-h] <delivery-command> ...
```

Integrated verification and the landing gate (ADR-058). A delivery is whatever one branch / worktree / pull request carries — a single IB, an Intent's IBs, or a Mission cluster (ADR-048). Acceptance stays per IB; these verbs make sure evidence and verdicts cover the final integrated head. Without `--ib`, the delivered IBs are discovered from the diff against the base: every delegated IB whose file or execution record the branch touches.

Options (both verbs, plus the common `--at`, `--dekspec-root`, `--actor`, `--json`):
- `--ib IB` — IB in the delivery (repeatable). Default: discovered from the diff.
- `--base BASE` — base branch. Default: `main`.

### delivery verify

```
dekspec delivery verify [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                        [--ib IB] [--base BASE]
```

Re-run every included IB's `ib verify` and the repository integration command (the base branch's `execution.integration_command`, if set; a delivery cannot switch it off) against the same head content, and record a delivery evidence event in each IB's record. The event records the base commit it was verified against (`base_commit`) and names each IB evidence event it executed (`executed`: record, sequence and hash). Exit `0` only when every IB and the integration command pass. Any later commit — or a rebase onto a moved base — makes the evidence stale.

### delivery check

```
dekspec delivery check [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                       [--ib IB] [--base BASE] [--rerun]
```

The landing gate. Passes only when:

- every execution record present at the base or in any commit of the delivery — both sides of every merge — is still present, append-only and attached to its IB (`execution-records-present`, `<ID>:record-append-only`, `execution-records-attached`) — records are never deleted, truncated or relabelled, so this runs even when nothing else is delivered;
- a retired IB (DEPRECATED / SUPERSEDED) that ran gets `<ID>:retired` instead of a completion gate. It needs no open attempt, and every remaining change must be accounted for, inside or outside its scope. Accounted-for changes are:
  - lifecycle records and status bookkeeping;
  - changes that predate its run;
  - work an active co-delivered IB owns, inside that IB's Scope and outside its protections.

  The retired IB's protected surfaces still apply. Only an active IB whose Scope names the protected area itself can own a change to one;
- the branch is current with its base (the base is an ancestor of `HEAD`);
- every delivered IB's completion gate passes at the exact head — `--ib` can add IBs but never hide a discovered one (`delivery-coverage`), so a partial selection is never ready to land;
- when the base configures an integration command: with `--rerun`, the command is executed at this head; otherwise a `delivery verify` result for that exact command, covering every IB, is current at this head (`integrated-verification`).

A change that delivers no delegated IB (and touches no execution record) passes trivially. The land skill runs it immediately before the operator-confirmed merge (ADR-026); rewriting commits (e.g. `pr-branch`) changes the head, so run it again.

Options:
- `--rerun` — CI mode: re-execute acceptance and the base's integration command at this head instead of trusting recorded results, evaluate under the base branch's execution settings, and write nothing. From the command line it always re-executes everything, whatever evidence is recorded (ADR-058). Only the `/implement` driver's own landing gate skips what its own passing delivery verification already executed at the identical binding (see `implement next`).

## intent

```
dekspec intent [-h] <intent-command> ...
```

Intent completion from its IBs and its outcome evidence (ADR-057). An Intent's lifecycle is `DRAFT` → `PROPOSED` → `ACCEPTED` → `COMPLETE` (+ `SUPERSEDED`); there is no IMPLEMENTING / TESTPASS / MERGED. Its child IBs are the IBs whose `**Parent:**` names it. Evidence lives in the Intent's own record, `.dekspec/execution/INT-NNN/record.jsonl`.

Positional (all three verbs):
- `intent` — Intent id (`INT-NNN`) or a path to the Intent file.

Common options: `--at`, `--dekspec-root`, `--actor`, `--json` (as for `ib`).

### intent verify

```
dekspec intent verify [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json] intent
```

Run the Intent's `## Verification` commands (the ADR-029 outcome test among them) and record evidence bound to the current fingerprint. Manual entries are reported as needing review. Refused when the Intent declares no Verification entries. Exit `0` only when the overall result is `passed`.

### intent review

```
dekspec intent review [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                      --reviewer REVIEWER --verdict {pass,fail} [--notes NOTES]
                      [--policy-revision N] intent
```

Independent verdict for the Intent's manual verification entries, bound to the current fingerprint and stamped with the `verifier` Agent Role Specification's policy (ADR-061). Refused when the reviewer built one of the Intent's IBs, when the acting identity (`--actor` / `DEKSPEC_ACTOR`) is not `--reviewer`, and when the verifier policy moved since the attestation was dispatched. An attestation under an older policy revision needs to be repeated.

Options:
- `--reviewer REVIEWER` — reviewer identity (required).
- `--verdict {pass,fail}` — the verdict (required).
- `--notes NOTES` — free-text notes.
- `--policy-revision N` — the `verifier` policy revision the attestation was performed under (defaults to `DEKSPEC_ROLE` for a dispatched worker).

### intent complete

```
dekspec intent complete [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT] [--actor ACTOR] [--json]
                        [--check-only] intent
```

`ACCEPTED` → `COMPLETE` when the Intent is authorized, at least one IB names it as parent and every such IB is `COMPLETE`, its outcome evidence is current and passing, and — if any verification entry is manual — a current independent `intent review` verdict passes. Exit `1` with the failing checks otherwise.

Options:
- `--check-only` — evaluate the gate without writing anything.

## implement

```
dekspec implement [-h] <implement-command> ...
```

The core of `/dekspec:implement` (ADR-059) and the supported caller contract for callers such as the `deepen` and `debug` skills, CI and dashboards. This section is the complete verb and payload reference; `docs/implement-caller-contract.md` in the DekSpec repository adds the integration guidance for tool authors. Every verb takes the request as its positional words — `INT-041`, `int-041 and int-042`, `the authentication feature` — plus `--at`, `--dekspec-root`, `--actor` (recorded as the requester; default `$DEKSPEC_ACTOR`, then git `user.name`) and `--json`. Exit codes: `0` ok, `1` not ready or refused, `2` usage, `3` blocked.

### implement resolve

Resolve a request to targets. Explicit ids are case-normalized and zero-padded (`int-41` → `INT-041`). A description resolves only when exactly one Intent, or one parentless IB, matches every significant word. Several matches are reported as `ambiguous`, and none as `not-found` with the nearest candidates. Nothing is ever created. Exit `1` unless the request resolves cleanly.

### implement ready

The READY predicate: the Intent is `ACCEPTED`, with a desired outcome, executable Verification, autonomy `medium`/`high` not capped lower by its Mission's Autonomy ceiling, no unresolved P0–P2 Open Issue, and in-force linked AEs and Mission; child IBs are delegated, `ACCEPTED` (or `COMPLETE`), executable contracts whose obligations resolve, authorized for their current contract, and free of blocking issues or undecided blockers; for a child IB whose run has not started and that has test conditions or declared assets, the acceptance floor is baselined and reviewed (see the two ADR-062 items below); dependencies are `COMPLETE` or selected, with no cycle; and the environment is ready — the targets' specifications are committed, the checkout contains the tip of the integration base and carries nothing beyond it but the targets' specification material (`checkout-ahead-of-base`), the integration method is available, a pytest interpreter exists, and every required prerequisite probe passes. JSON: `ready`, `targets[] {id, kind, status, outcome: ready|not-ready|complete, completion: verified|historical, ibs, missing}`, `order`, `groups` (one delivery each), `base`, `integration`, `missing[] {target, code, detail, fix}`. A `COMPLETE` Intent counts as complete only with provenance. `verified` means an Intent completion record over complete IBs. `historical` means no delegated IBs, every legacy IB historically complete, and the Intent terminal at or before the base. A `COMPLETE` status without either is `intent-complete-unverified`. Completion, dependencies and the environment are judged against the authoritative integration base: the local `integration.base` branch for `merge`, `<integration.remote>/<integration.base>` for `github` (`main` or `master` when unset). It is never substituted. A forge base that has not been fetched is unknown, and a completion that depends on it (a stale one, or one complete only by history) is `no-integration-base`: fetch the base first. Exit `0` when ready, or when every target is already complete.

**The acceptance floor (ADR-062).** Two items apply to a delegated `ACCEPTED` IB whose run has not started, whose baseline matches its current contract, and that has test conditions or declared assets. Both are entry checks: a started run is never stopped by them.
- `acceptance-tests-missing` — the current baseline does not hold one of these:
  - a named node's file, with a recorded hash;
  - a declared asset;
  - for a directory node, every file under it.

  It is also reported when the node's file no longer hashes to its baseline value, or no longer contains the node's function. Fix: write the tests with `/dekspec:write-tests`, have them oracle-reviewed, then `dekspec ib baseline IB-NNN --reason …`.
- `acceptance-floor-unreviewed` — no row in the IB file's Amendment Log table records a passing floor review of the current baseline's digest. A matching row has Change text that starts `Floor reviewed: PASS` and contains `digest <64 hex>`. A row that names an older digest does not count, and neither does a row recording any other outcome, such as `Floor reviewed: FAIL — digest <baseline digest> — …`; the item's detail then says a passing review is required. Fix: run the independent oracle review of the floor (`dekspec ib floor IB-NNN`, `/review-ib`) and, on a pass, record the row `Floor reviewed: PASS — digest <baseline digest> — …`.

An IB with only `command:` and `review:` conditions and no declared assets is unaffected.

### implement next

Take every mechanical step available and print the next action (`--json` for the payload):

- `dispatch` — `{id, role: builder|reviewer|resolver|intent-reviewer, key, actor, worktree, prompt, ib|intent|files}`. Run one fresh-context agent with `prompt` verbatim, then `implement ack`.
- `wait` — `{seconds, reason}`: forge checks are pending.
- `done` — `{result}`: every delivery passed its landing gate at its current content (the run's `landing.verified` record), is integrated (and pushed, with `push: true`), and the integrated content is verified. `result.targets` maps each target to `complete`; each `result.deliveries[]` reports `outcome`, `detail`, `integration {state: merged, detail, revision, tree, pr}` (no `method`), per-IB status and completion, `blockers` and `delivery {slug, targets, branch, worktree, base, run}`. `integration` is observed from git when the payload is built: on the `next` that integrates, its `revision` is the integrated commit, but a repeated `next` re-observes the base and reports its live tip, a later commit once the base has moved. The integrated revision stays available as `integrated.revision` in `implement status`. A head that is in the base without that record is not `done`: the run continues.
- `blocked` — `{result}` with per-target outcomes, `blockers[] {kind, detail}`, `waiting` IBs, and `not_ready[] {target, code, detail, fix}` for requested targets that could form no delivery. Those are marked `not-ready` in `targets`, and the request is not complete. Nothing authorized is left to do. Delivery outcomes include `integrated-unverified` and `push-pending`. Blocker kinds include `push-failed` (retried on the next `next`, never forced), `checks-not-converging`, `required-checks-failed`, `integration-blocked`, `review-not-recorded` (three reviews or Intent attestations in a row returned without a verdict; it clears once an independent verdict is recorded) and `base-unavailable` (the delivery base does not resolve; nothing is dispatched, and it clears once the base resolves). A `not_ready` item with code `no-integration-base` is a completion that fails the current rules while the base is unknown: fetch or correct the base first.
- `not-ready` — `{readiness}` or `{resolution}` with the missing preparation. Nothing was prepared.

Mechanical steps include:
- preparing the delivery worktree (`implement/<targets>` beside the repository; `integration.worktree_setup` runs once);
- starting IB runs, and re-verifying stale evidence;
- `delivery verify` (ADR-059 stage 2) and `intent verify`. Stage 2 does not execute an IB again when its passing evidence was recorded by the driver itself at the identical binding: implementation fingerprint, contract hash, baseline, context manifest and base. Evidence recorded by anyone else, a builder included, is always executed again. Stage 2 runs again whenever the binding changes, after completion too. Its delivery evidence records the base commit and names each IB's evidence, relied on (`relies_on`) or executed (`executed`);
- with `github`, pushing the reviewed head and reading its required checks before any completion. A failing check becomes a builder repair dispatch, with its evidence. A failure on the landing head reopens the unintegrated completions of the downstream IB and the target Intents, then repairs the same way.
- `ib complete`, `intent complete`, and merging a moved base;
- the landing gate (ADR-059 stage 6): `delivery check --rerun`, recorded as `landing.verified` once per binding, that is per content fingerprint and base commit (`base_commit`). It re-executes acceptance and the base's integration command, except where the driver's own passing delivery verification stands at the identical binding. `landing.verified` names the evidence it relied on (`relies_on`) and lists what it executed (`executed`). CI's command-line `delivery check --rerun` always re-executes;
- integration, a retry of an outstanding push, and checkpoint commits. The first run's entry check is `implement ready`; an existing delivery resumes without it. Exit `3` when blocked, `1` when not ready.

Review failures return their findings to a repair builder. Repairs consume the
existing attempt allowance; once it is exhausted, the driver records a changed
strategy and grants more attempts through the existing allowance mechanism.
Construction and review recovery share the limit of two strategy changes per IB
(the initial approach is not a change). Each allowance is consumed before another
change, and each repaired implementation returns through verification and
independent review. Exhaustion with continued FAIL verdicts leaves a stable
`review-not-converging` blocker. Repeating the request preserves consumed attempts,
strategy changes and verdict history.

A historical `review-not-converging` blocker clears only when current passing
evidence and a valid current independent PASS resolve that IB's review. A
`review-not-recorded` blocker clears when an independent verdict is recorded;
FAIL resolves the silence and returns to bounded repair. Neither resolution clears
unrelated blockers or bypasses verification, review, completion or integration
gates.

### implement ack

```
dekspec implement ack <request> --dispatch D-n [--summary TEXT]
```

Record that dispatched worker `D-n` returned and commit its work in the delivery worktree (concluding a merge a resolver finished). Idempotent. A dispatch that is never acknowledged is treated as lost at the next `next` and reissued once.

### implement status

Read-only: per-target resolution and readiness, and per delivery `slug`, `targets`, `branch`, `worktree`, `base`, `run` and `state`, plus — once the delivery has started — `integration`, `outstanding_dispatches`, `blockers` and `ibs` (IB statuses). `state` is decided by the same completion predicate as `next`; it is one of `not-started`, `active`, `blocked`, `integrating`, `push-pending`, `integrated-unverified` or `complete`. `outcome`: `not-ready`, `not-started`, `in-progress`, `blocked` or `complete`.

- `integration {state, detail, revision, tree, pr}` is observed from git (and the forge) on every call: `revision` and `tree` are the base's current tip, which moves on after the delivery lands.
- `integrated {revision, tree, verified_tree, integrated_verified, method}` appears only for a delivery whose run record holds a recorded integration (`run.integrated`), and is absent otherwise. It is the integration as recorded when the delivery landed — the integrated commit and tree, the tree that passed the landing gate, whether the integrated content is the verified content (or passed re-verification), and the method (`merge` or `github`) — and it stays put when the base moves. It lives only in the delivery worktree's run record (`.dekspec/execution/RUN-<targets>/record.jsonl` under `worktree`), which is never committed; if that worktree is removed, `status` omits the delivery (for a target already complete) or reports it `not-started`, in either case without `integrated`.

`status` writes no tracked file, execution record, local branch or worktree; for a forge method, or with `push: true`, it may fetch the base, which updates remote-tracking refs only.

## session

```
dekspec session [-h] <session-command> ...
```

The session-lifecycle gate (MSN-002). Internal verb, used by skills and the installed git hooks.

### session start

```
dekspec session start [-h] [--branch BRANCH] id
```

Open a session bound to an IB or Intent. Binding an **IB** makes the pre-commit `vibecoding-check` enforce that IB's contract at commit time, on the staged content (not the working tree): a staged change to a protected file — or one that edits, removes or renames a protected `path::symbol` — is off-spec even inside an allowed glob, while the rest of a file holding a protected symbol follows Scope, and a staged file outside the IB's Scope is off-spec; the IB file itself, its acceptance assets, `.dekspec/execution/` and the `br` workspaces are always allowed. An Intent binding checks staged files against the Intent's `Components affected`. A legacy code-bead id still resolves to the Intent that lists it.

Positional:
- `id` — `IB-NNN` or `INT-NNN`.

Options:
- `--branch BRANCH` — branch to bind. Default: the current branch (required outside a git repo).

### session end / status / install-hooks / vibecoding-check / report

- `dekspec session end [--reason REASON]` — close the active session.
- `dekspec session status [--machine-readable]` — inspect the active session.
- `dekspec session install-hooks` — install the git hooks that enforce the gate.
- `dekspec session vibecoding-check [--machine-readable] [--files FILES] [--record]` — classify staged files against the bound IB (or Intent); exit `3` on off-spec files.
- `dekspec session report` — summarize off-spec drift recorded during the session.

## Execution settings (`.dekspec/config.yaml` → `execution:`)

Bounds and runner settings read by the `ib`, `delivery` and `intent` verbs. They are adaptable execution **policy** — model- and repository-dependent numbers — not governing obligations, so they live in config rather than in the Constitution. The block is optional; every key has a default, and a missing, non-integer or non-positive integer value falls back to its default (the block is read leniently so a malformed unrelated config key never disables the gate).

```yaml
execution:
  max_attempts: 3
  stall_minutes: 60
  no_progress_attempts: 2
  integration_command: "python -m pytest -q"
  command_timeout: 1800
  python: .venv/bin/python
  fingerprint_exclude: ["docs/generated/**"]
```

| Key | Default | Meaning |
|-----|---------|---------|
| `max_attempts` | `3` | Attempts per IB run before it blocks `attempts-exhausted` (counted across restarts; `ib unblock --extra-attempts` raises it). |
| `stall_minutes` | `60` | An open attempt with no heartbeat for this long is closed as `stalled`, counted, and blocks the run. |
| `no_progress_attempts` | `2` | Consecutive finished attempts with no newly satisfied condition and no new content before the run blocks `no-progress`. |
| `integration_command` | none | Repository-wide integration check run by `dekspec delivery verify`; when set, `delivery check` requires a current passing delivery verification. |
| `command_timeout` | `1800` | Per-command timeout, in seconds, for acceptance commands and test runs (and the integration command). |
| `python` | auto | Interpreter that runs acceptance test nodes. Auto picks the first of the repo `.venv`, `python3`/`python` on PATH, and the interpreter running `dekspec` that can import pytest — a pipx-installed `dekspec` is rarely the project's test environment. The evidence plugin is staged per run, so the interpreter needs pytest but not dekspec. An interpreter that is part of the repository's content (tracked or unignored) is refused; an ignored local `.venv` is fine. |
| `fingerprint_exclude` | none | Extra globs excluded from the implementation fingerprint (execution records, interpreter and tool caches, generated spec indexes and lifecycle bookkeeping are always excluded). |

## Integration settings (`.dekspec/config.yaml` → `integration:`)

How `/implement` integrates a verified delivery (ADR-059). Every key is optional.

```yaml
integration:
  method: merge          # merge | github
  base: main             # default: main, else master
  remote: origin
  push: false            # merge only: also push the base (the remote is then authoritative)
  worktree_setup: "python -m venv .venv && .venv/bin/pip install -e .[dev]"
```

| Key | Default | Meaning |
|-----|---------|---------|
| `method` | `merge` | `merge` fast-forwards the base branch to the verified head; the checkout holding the base is fast-forwarded and must have no local changes. `github` pushes the branch, opens or reuses its pull request, waits for its required checks and merges with `--match-head-commit`, never with an administrator override. |
| `base` | `main` / `master` | Branch to integrate into. |
| `remote` | `origin` | Remote for `push` and `github`. |
| `push` | `false` | `merge` only: push the updated base, never forced. The remote is then authoritative. A delivery in the local base but not the remote is `push-pending`, and completion waits until the remote holds it. |
| `worktree_setup` | none | Shell command run once in each new delivery worktree. |

## Retired: `executions`

The `dekspec executions` verb family (the execution-attempt lifecycle DB written by an external executor under the retired IC-004 executor contract, with per-bead progress events) no longer exists. Attempts, failures, evidence, verdicts and completion are recorded per IB in `.dekspec/execution/<IB>/record.jsonl` through [`dekspec ib`](#ib); failure-class trends come from [`dekspec audit failure-classes`](#audit-failure-classes).

## Universal exit code conventions

- `0` — clean / success.
- `1` — non-fatal findings (audit warnings, vendoring drift, doctor warnings). CI typically still passes.
- `2` — critical findings or parse errors. CI fails.
- `3+` — reserved for unrecoverable invariant violations (rare).

The execution verbs use their own fixed convention: `ib`, `delivery` and `intent` exit `0` ok · `1` refused / gate not satisfied · `2` usage · `3` blocked (see [`ib`](#ib)). `session vibecoding-check` exits `3` on off-spec files.

## See also

- [`EXAMPLES.md`](EXAMPLES.md) — tutorial-style recipes against the Python API.
- [`dekspec-operating-guide.md`](dekspec-operating-guide.md) — methodology + day-to-day workflow.
- [`dekspec-quick-reference.md`](dekspec-quick-reference.md) — skill index + status lifecycle cheatsheet.
- [`architecture.md`](architecture.md) — IR + parser + emitter mental model.

### Helper-skill deterministic helpers

`dekspec archeology scan TARGET --at REPO` emits Python AST evidence, not inferred
requirements. `dekspec handoff` reads continuity evidence; `write --input FILE`
records the documented JSON shape, redaction and repository identity. New records
use external state; legacy records remain readable. `dekspec deepen-record`
maintains multi-pass deepening evidence bound to core (below); it executes no
agents and defines no readiness policy. Each helper provides `--help`. The helper
skills that call them accept ordinary requests without flags.

#### deepen-record

```
dekspec deepen-record [status|start|begin|append|abandon] [--at REPO] [--scope SCOPE]
                      [--input FILE] [--new-run] [--max-passes N]
```

One record per repository and `--scope` (default `whole-repo`), kept in external
state (`$XDG_STATE_HOME/dekspec/<repo key>/deepening/`, else `~/.local/state/…`),
never in the repository. Each pass has a lifecycle bound to core's
`dekspec implement` evidence (IB-139, ADR-059's caller contract): the tool reads
core, and never writes core's records.

Actions:

- `start` — create the record, with `--max-passes N` (default 12, at least 2) as
  the host's safety budget. With a record present it prints it unchanged
  (resume; learning is never discarded). `--new-run` archives the record beside
  it (the new record's `prior_record` names the archive) and starts a fresh one
  that carries the latest integrated revision forward as `prior_integration`; it
  is refused while a pass is pending.
- `begin --input FILE` — record a pass as `pending`. The tool itself reads the
  pass's input revision from the base branch (`integration.base`, else
  `main`/`master`; the remote copy for a forge method, not fetched); callers do
  not supply it. `targets` is empty for a dry reassessment, or exactly one IB or
  Intent for an implementing pass. The tool stores what it read under `begin`:
  `input_revision`, `base`, `latest_integration` (the latest integrated revision
  an earlier pass recorded), the resolved `target`, and `core_runs` (each core
  run that already exists for the target, with its last record sequence).
  Refused: more than one target; a target that does not resolve to exactly one
  IB or Intent, or that core already reports complete (nothing to do); another pass
  pending; a `pass_id` already recorded; a run that has stopped; and an input
  revision that does not contain the latest integrated revision recorded by an
  earlier pass (of this record, else the `prior_integration` an archived run
  carried forward).
- `append --input FILE` — record a pending pass's terminal outcome (needs
  `pass_id` and an `evidence` list). The outcome is judged on the pass as it
  would be stored: the `begin` payload merged with the appended fields. A pass
  claims implementation when it has `targets`, `implementation_status: complete`
  or `completed > 0`.
  - **Complete** (a pass begun with a target, `completed > 0`): recorded only
    when core's `implement status` reports the target `complete` with a recorded
    integration of exactly one delivery, recorded after the pass began (a later
    record sequence than `begin` noted, or a run that did not exist then), read
    from the delivery's run record with its hash chain verified. The integrated
    revision must be a strict descendant of the pass's input revision and not
    already claimed by another pass in the record, and every IB's completion
    record must cite passing verification evidence and a passing independent
    verdict. The pass then stores, under `core`: `outcome`, `target`, `run`,
    `delivery`, `revision`, `tree`, `verified_tree`, `integrated_verified`,
    `method`, the integration event's sequence and hash, and per IB its
    completion reference (`seq`, `hash`, `evidence_seq`, `verdict_seq`). A
    caller `revision` is only compared with core's recorded integrated revision
    — never the base's current tip — and a different one is refused.
  - **Blocker** (`implementation_status` `blocked` or `not-ready`, with no
    completed changes): for a pass begun with a target, core must report the target
    `blocked` or `not-ready`; the caller's assertion alone is refused.
  - **Dry** (a pass begun without targets, claiming nothing): recorded as `dry`
    with its evidence (`dry: true`, `not-needed`, `completed: 0`). A completion
    without targets is refused.

  A pass begun with a target resolves only through core's completion, a
  core-reported blocker or `abandon`: never as `not-needed` or `completed: 0`.
  Refused as well: a pass never begun, `targets` other than the begun ones, and a
  new pass after the run has stopped. The caller's `revision` and `verified`
  (and the tool-owned `state`, `begin`, `core`, `abandon`) are never stored.
  Repeating an append for a resolved pass is idempotent: the same outcome prints
  the record unchanged, a different one is refused.
- `abandon --input FILE` — end a pending pass without a run (`pass_id`,
  `reason`). Refused while core shows an unintegrated run for the pass's target;
  an abandoned pass counts toward neither progress nor convergence. Repeating it
  is idempotent.
- `status` — print the stored record (`{"passes": [], "status": "not-started"}`
  without one). While a pass is pending it adds `pending {pass_id, targets,
  outstanding_dispatches}` with core's outstanding dispatches for the pass's
  target, and `core_outcome` when core was read. When core cannot be read for
  that target it adds `core_error` naming the cause and still exits `0`.

Outcomes (`status`): `continue`; `interrupted` — the latest pass is pending
(`begin` and `start --new-run` are refused until it is resolved);
`convergence` — the last two passes (abandoned ones do not count) are dry
reassessments (`dry: true`, `remaining: 0`, non-empty `evidence`,
`implementation_status: not-needed`), no `unresolved` finding is still carried,
and each began after the latest integration recorded in the record (its
`begin.latest_integration` is that revision); `stalled` — the same candidate is
proposed twice in a row or oscillates (A, B, A), or a candidate an earlier pass
rejected returns without `new_evidence`; `budget` — `--max-passes` passes
recorded (abandoned ones do not count); `blocker` — the latest pass is a
blocker, or a pass counts completed changes without core's evidence. They stay
distinct: an interrupted run is never reported as any other.

Refusals print a JSON `{"error": …}` on stdout and leave the record
byte-for-byte unchanged. They exit `1` for a refusal by rule, and `2` for a
malformed request, a missing record, a `pass_id` already recorded or a
conflicting repeat. When core's status cannot be obtained, or its recorded
integration cannot be read with a valid hash chain (core raises, the run
record's chain is broken, the delivery worktree no longer exists), every action
that needs core — `begin` with a target, a completion or blocker for a targeted
pass, `abandon` of one — is refused with `core evidence unavailable: <cause>`.
