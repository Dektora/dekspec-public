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

Top-level subcommands (eleven):

| Command | One-line summary |
|---------|------------------|
| [`init`](#init) | Scaffold a new dekspec/ tree in the current repo. |
| [`compile`](#compile) | Parse a DekSpec artifact and (optionally) emit an enforcement output. |
| [`validate`](#validate) | Quick parse-only check (no persistence side effect). |
| [`audit`](#audit) | Run fidelity-audit checks (L-series linkage today). |
| [`aggregate`](#aggregate) | Aggregate compiled outputs across the whole spec graph. |
| [`verify-vendored`](#verify-vendored) | Compare consumer's vendored content against library source-of-truth. |
| [`graph`](#graph) | Inspect or export the spec graph (the union of all parsed IRs). |
| [`doctor`](#doctor) | Composite health check: vendoring + audit linkage + parse failures. |
| [`migrate`](#migrate) | Migrate persisted IR JSON files forward through schema migrations. |
| [`runs`](#runs) | Inspect compile-run history persisted under `$XDG_DATA_HOME/dekspec/`. |
| [`executions`](#executions) | Query + annotate the execution-attempt lifecycle DB (flywheel substrate). |

Universal flags repeated across subcommands:

- `--at PATH` — anchor the repo at PATH (default: cwd).
- `--dekspec-root PATH` — content tree relative to repo root (default: `dekspec`).
- `--json` — emit machine-readable output instead of formatted text.

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
                      [--json]
                      [--severity {critical,important,minor,all}]
                      [--fix] [--apply]
```

Walk the spec graph and emit per-rule findings.

Options:
- `--at AT`, `--dekspec-root DEKSPEC_ROOT` — repo anchor + content tree.
- `--json` — emit findings as JSON instead of a formatted table.
- `--severity {critical,important,minor,all}` — minimum severity to report. Default: `all`.
- `--fix` — compute mechanical fix proposals (L6 backlink, L7 ADR supersession mirror, L8 Mission↔Intent mirror) and show before/after diffs. Dry-run unless `--apply`.
- `--apply` — used with `--fix`: actually write the proposed changes to disk.

Exit codes: `0` clean, `1` findings present, `2` parse errors.

## aggregate

```
dekspec aggregate [-h] <aggregate-command> ...
```

Walk the SpecGraph and produce a single combined output.

### aggregate agents-md

```
dekspec aggregate agents-md [-h] [--at AT] [--dekspec-root DEKSPEC_ROOT]
                            [--output OUTPUT] [--status STATUS]
                            [--include INCLUDE]
```

Aggregates per-artifact `agents-md` fragments (AE, ADR, WS, IB, Intent, Mission, Glossary, Vision) into a single project-wide `AGENTS.md`.

Options:
- `--output OUTPUT` — default `<repo_root>/AGENTS.md`. Use `-` for stdout.
- `--status STATUS` — comma-separated status filter. Default: `LOCKED,ACCEPTED`. Pass `all` for every artifact.
- `--include INCLUDE` — comma-separated artifact kinds (any of `VISION,GLOSSARY,AE,ADR,WS,IB,INT,MSN`). Default: all kinds.

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

## executions

```
dekspec executions [-h] <executions-command> ...
```

Inspect or annotate the execution-attempt records that DekFactory (or any executor) writes when it runs against compiled IRs. The lifecycle DB is the flywheel substrate — first-pass success rate, pattern promotion eligibility, and constraint evolution signal all read from here. Six nested verbs.

### executions ls

```
dekspec executions ls [-h] [--intent INTENT] [--mission MISSION]
                      [--agent AGENT] [--since SINCE] [--until UNTIL]
                      [--first-pass-only] [--merged-only] [-n LIMIT]
                      [--at AT] [--json]
```

List execution attempts.

Options:
- `--intent INTENT` — filter to one Intent (e.g. `INT-042`).
- `--mission MISSION` — filter to one Mission (e.g. `MSN-007`).
- `--agent AGENT` — filter to one agent model.
- `--since SINCE` / `--until UNTIL` — ISO timestamp bounds on `started_at`.
- `--first-pass-only` — only attempts that were first-pass AND merged.
- `--merged-only` — only attempts that merged.
- `-n, --limit LIMIT` — default 100.
- `--at AT` — repo anchor.
- `--json` — emit as JSON.

### executions show

```
dekspec executions show [-h] [--events] [--at AT] [--json] attempt_id
```

Show one attempt + (optionally) its event log.

Positional:
- `attempt_id` — numeric attempt id.

Options:
- `--events` — include the event log.
- `--at AT` — repo anchor.
- `--json` — emit as JSON.

### executions metrics

```
dekspec executions metrics [-h] [--since SINCE] [--until UNTIL]
                           [--by-agent-model] [--at AT] [--json]
```

Aggregate flywheel-health metrics (first-pass rate, mean TTM, escalation rate).

Options:
- `--since SINCE` / `--until UNTIL` — ISO timestamp bounds.
- `--by-agent-model` — also break results down per agent model.
- `--at AT` — repo anchor.
- `--json` — emit as JSON.

### executions tag

```
dekspec executions tag [-h] [--at AT] attempt_id kv
```

Set a tag (key=value) on an attempt.

Positional:
- `attempt_id`
- `kv` — `key=value` (e.g. `flywheel-pattern=crud-endpoint`).

### executions amend

```
dekspec executions amend [-h] [--at AT] attempt_id note
```

Append a free-form note to an attempt.

Positional:
- `attempt_id`
- `note` — free-form text.

### executions link

```
dekspec executions link [-h] --pr PR [--at AT] attempt_id
```

Tag an attempt with a PR URL (shorthand for `tag pr_url=<url>`).

Positional:
- `attempt_id`

Options:
- `--pr PR` — PR URL (required).

### executions record-attempt

```
dekspec executions record-attempt [-h] --intent INTENT --agent AGENT --attempt N
                                  [--mission MISSION] [--compile-run COMPILE_RUN]
                                  [--audit-profile PROFILE] [--at AT] [--json]
```

Insert a new `execution_attempts` row. Idempotent on `(intent_id, attempt_number)`. **Required by any executor that implements IC-004-executor-contract.**

Options:
- `--intent` — Intent id (e.g., `INT-042`). Required.
- `--agent` — Agent model identifier (e.g., `claude-opus-4-7`). Required.
- `--attempt N` — 1-based attempt number. Idempotent against re-record. Required.
- `--mission` — Optional parent Mission id.
- `--compile-run` — Optional compile-run id linking the attempt to the compiled artifacts it was run against.
- `--audit-profile` — Audit profile in force (default: `v1`).
- `--json` — Emit `{"attempt_id": N}` for downstream parsing.

### executions record-event

```
dekspec executions record-event [-h] --attempt N --type EVENT_TYPE
                                [--payload JSON] [--custom-type LABEL]
                                [--agent AGENT] [--at AT]
```

Append a structured event to an in-flight attempt. Per IC-004, executors emit per-bead progress + interrupt events through this channel.

Options:
- `--attempt N` — Attempt id from `record-attempt`. Required.
- `--type` — Canonical event type or `custom`. Required. Canonical set: `agent_question`, `first_pass_fail`, `ci_failure`, `constraint_violation`, `escalation_request`, `retry`, `kill_triggered`.
- `--payload JSON` — Event payload as a JSON object string. Default `{}`. By convention, per-bead events carry `bead_id` in the payload.
- `--custom-type LABEL` — Free-form label, required when `--type=custom`.
- `--agent AGENT` — Override the agent model recorded on this event (defaults to the attempt's agent_model).

### executions complete

```
dekspec executions complete [-h] --attempt N --ci-status {pass,fail,skipped,error}
                            [--violations COUNT] [--escalation]
                            [--merged] [--merge-commit SHA]
                            [--notes TEXT] [--at AT]
```

Finalize an in-flight attempt with its terminal outcome. Auto-recomputes `merge_outcomes` for the Intent when `--merged` is set.

Options:
- `--attempt N` — Attempt id. Required.
- `--ci-status` — Terminal CI status. Required. One of `pass`, `fail`, `skipped`, `error`.
- `--violations COUNT` — `constraint_violations_count` (default: 0).
- `--escalation` — Mark `escalation_required=True`. By IC-004, this is set when the executor refuses dispatch due to autonomy ceiling or otherwise hands the decision back to the engineer.
- `--merged` — Mark `merged=True`. Requires `--merge-commit`.
- `--merge-commit SHA` — Merge commit SHA. Required with `--merged`.
- `--notes TEXT` — Free-form notes appended to the attempt's `notes` column.

## Universal exit code conventions

- `0` — clean / success.
- `1` — non-fatal findings (audit warnings, vendoring drift, doctor warnings). CI typically still passes.
- `2` — critical findings or parse errors. CI fails.
- `3+` — reserved for unrecoverable invariant violations (rare).

## See also

- [`EXAMPLES.md`](EXAMPLES.md) — tutorial-style recipes against the Python API.
- [`dekspec-operating-guide.md`](dekspec-operating-guide.md) — methodology + day-to-day workflow.
- [`dekspec-quick-reference.md`](dekspec-quick-reference.md) — skill index + status lifecycle cheatsheet.
- [`architecture.md`](architecture.md) — IR + parser + emitter mental model.
