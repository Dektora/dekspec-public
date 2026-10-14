# Bead identity, migration and recovery

DekSpec maintains two current bead stores: `.beads-issues/.beads/` for issues and `.beads-dekspec/.beads/` for governance work. A legacy root `.beads/` is historical code-bead data; initialization and project-prefix migration do not create or migrate it.

This guide ships with DekSpec. Read it from any consumer with:

```bash
dekspec resource doc beads-recovery
```

After `dekspec sync`, the consumer copy is `dekspec/beads-recovery.md`. See the [operating guide](dekspec-operating-guide.md#project-bead-identity-and-first-time-setup) for first-time setup.

## Project identity and tracked pins

A project prefix is 2–6 lowercase ASCII letters or digits, with no hyphen, dot or underscore. For project `acme`, issue IDs begin `acme-iss-` and governance IDs begin `acme-ds-`. The existing hash, slug and child suffix remain unchanged: `acme-iss-xwd.21` is a child ID.

The project key lives at `beads.project_prefix` in `.dekspec/config.yaml`. Each store also pins its full `issue_prefix` in its tracked `.beads/config.yaml`: for example, `.beads-issues/.beads/config.yaml` contains `issue_prefix: acme-iss`. Track those config files and `issues.jsonl`; the ignored database alone is not a durable prefix setting.

The board resolver and initialization use this precedence:

1. A valid project setting establishes the expected `<project>-iss` and `<project>-ds` identities. A contradictory store pin is an error, not permission to overwrite it.
2. Without a project setting, use each valid existing tracked store pin. Already-migrated stores such as `usr-iss` and `usr-ds` work even without a DekSpec config.
3. Only when neither setting exists, use the legacy `iss` and `ds` defaults. Stored IDs that disagree with the resolved prefix are a mismatch to repair, not an empty board.

Malformed present settings are errors. The short project-key rule does not restrict a pre-existing full store prefix to six characters. Reading a board creates no stores and changes no IDs.

## Check operational health

```bash
dekspec beads health --at /absolute/path/to/project --json
dekspec doctor --at /absolute/path/to/project
```

The bead health probe runs `br` against disposable store copies. Each `br` invocation has a five-second timeout; a timeout, unreadable database or unknown response is reported as an error. The probe does not open the original database, because some `br` versions modify a database even during read operations. A healthy response can still report a nonzero `dirty_count`; those are edits that must be exported and reviewed before migration.

A timeout proves that the store could not be checked within the bound. It does not establish the cause, and it does not prove that rebuilding is safe.

## Preview and apply a project-prefix migration

Use migration for existing IDs; changing the config key alone does not rename beads or update references. Apply and rollback are qualified on Linux. They use the `br 0.7.4` canonical database-path opener lease to prevent concurrent database access throughout staging, replacement and rollback. An existing database without the supported lease, a hardlinked database, or an active `br` opener causes refusal. Establish compatible tooling and export parity; do not create or delete lease files manually to bypass the guard. Stop tracker writers while applying the migration. First inspect the complete preview:

```bash
dekspec beads reprefix --at /absolute/path/to/project --to acme --json
```

The preview is read-only for the original stores. It lists the exact old-to-new IDs, affected files, filename changes and a `plan_sha256`. It proves database/export agreement using disposable copies before treating JSONL as a rebuild source. Review the complete receipt, including references to other repositories; do not infer ownership from an unqualified ID alone.

Apply the reviewed receipt by supplying its actual hash:

```bash
dekspec beads reprefix --at /absolute/path/to/project --to acme \
  --apply --expect-plan REVIEWED_PLAN_SHA256 --json
```

`REVIEWED_PLAN_SHA256` is a placeholder for the preview's full hash. A changed repository or store makes the preview stale; rerun the preview and inspect the changes before applying. Do not automatically approve a replacement hash.

The migration preserves suffixes, rewrites exact known IDs in JSONL and tracked text, updates dependency/comment endpoints, renames files containing IDs, and pins both the project key and the affected store prefixes. It does not globally replace text such as `iss-`, rewrite Git history, or update a different repository. Untracked consumer text is outside the tracked-reference rewrite boundary. Resolve external references with their owning repository.

Before publishing rebuilt stores, migration verifies semantic export preservation, clean sync and resolvable new IDs. It then checks the installed stores and searches tracked files for old IDs. It refuses ambiguous IDs, collisions, dangling relationships, binary references, unsupported workspace layouts, symlinked paths, ambiguous cross-repository URLs, hash-bound execution evidence, and unexported or unknown database state. Refusal leaves that problem to resolve explicitly; it is not a reason to bypass the checks or rewrite an execution hash chain.

Successful apply returns `status: complete` and a backup path under `.br_recovery/`. The backup retains the original stores, including DB/WAL sidecars, and changed files. The recovery directory is ignored by Git; keep the backup until the migration is verified and accepted. Review and commit the intended JSONL, config, reference and rename changes through the project's normal process.

## Interrupted migration

Ordinary apply failures attempt rollback automatically. After an interruption that leaves `.br_recovery/active.json`, stop writers and use:

```bash
dekspec beads recover --at /absolute/path/to/project --json
```

This restores the saved **pre-migration** files and stores after validating the recovery journal and backup hashes. It does not finish the interrupted migration, and it does not repair an arbitrary old `br` database. Preserve any work written after the interruption separately before rollback; do not let writers continue against a partially migrated store.

Run health checks and obtain a new preview after recovery. A missing or invalid backup/journal requires investigation with the preserved files; never delete the journal to force another apply. A lock without an active journal also needs inspection rather than blind lock removal. With no active journal, `recover` reports `no interrupted migration`.

## A newer br hangs on an older database

A real adoption reported that `br 0.7.4` hung against databases written by an older `br`, while fresh stores worked. Rebuilding from JSONL worked only after checking that the database held nothing unexported. This is evidence of that adoption's workaround, not proof that every hanging database has the same cause.

Use the following recovery sequence:

1. Stop every writer to the affected store. Record the installed `br --version`, the failing command and its output or timeout. Preserve a consistent copy of the **whole** store, including `beads.db`, `beads.db-wal`, `beads.db-shm`, `issues.jsonl`, configuration and metadata, outside tracked project content. Do not copy an actively changing SQLite database and assume it is a coherent backup.
2. Diagnose only disposable copies. If a known compatible `br` version can read the old database, run its status and export commands on a copy with explicit `--db`, `--no-auto-import` and `--no-auto-flush`, under a bounded timeout. Use that compatible binary explicitly; do not silently replace the operator's installed `br`.
3. Establish whether the DB contains edits absent from the tracked export. Compare the complete exported records, including comments, dependencies, labels, status and text, not merely record counts or ID lists. A zero dirty count alone is insufficient. If the DB cannot be read or agreement cannot be established, keep the original and backup intact and obtain compatible tooling or an upstream diagnosis. Do not delete the DB, discard the WAL, or assume JSONL is complete.
4. If a compatible export reveals additional data, preserve and reconcile that data into the authoritative JSONL before rebuilding. Review which changes are intended; never overwrite the newer state with an older checked-in export.
5. Only after export completeness is established, build a fresh store in a separate temporary directory using the intended prefix: `br init --prefix <full-store-prefix>`, restore the tracked `issue_prefix`, and run `br sync --import-only`. Use the disposable workspace's explicit database path for every command. Verify full semantic equality, resolved dependency/comment endpoints, `br sync --status` with zero dirty records, and `br show <id>` for the rebuilt records.
6. With writers still stopped, retain the original whole-store backup and replace the affected live database only with the verified fresh state, keeping JSONL and the tracked prefix aligned. Run `dekspec beads health --at <project>` and `dekspec doctor --at <project>` before resuming writers. If proof fails at any step, preserve the evidence and stop the rebuild.

There is deliberately no “delete the DB and retry” command here: rebuilding an unreadable database without proving export completeness can lose the only copy of recent work. `dekspec beads recover` handles its own journaled reprefix operations; it is not an automatic repair for this older-database failure.
