# DekSpec Examples

This is the cookbook for using DekSpec's Python API. Each example is self-contained and uses only the public surface at `dekspec.api`. The CLI examples in the README cover the same ground at the shell level; this doc covers the equivalent Python.

For one-line CLI usage, start with [README.md](../README.md). For the framework's mental model, see [architecture.md](architecture.md).

---

## Table of contents

1. [Load and inspect a spec graph](#load-and-inspect-a-spec-graph)
2. [Parse a single artifact directly](#parse-a-single-artifact-directly)
3. [Run the full audit battery](#run-the-full-audit-battery)
4. [Auto-fix mechanical findings](#auto-fix-mechanical-findings)
5. [Generate AGENTS.md programmatically](#generate-agentsmd-programmatically)
6. [Query the SQLite run index](#query-the-sqlite-run-index)
7. [Check vendoring drift](#check-vendoring-drift)
8. [Build a custom CI check](#build-a-custom-ci-check)
9. [Resolve AE implements_globs through an IC](#resolve-ae-implements_globs-through-an-ic)
10. [Export the whole graph as JSON](#export-the-whole-graph-as-json)
11. [Author a schema migration](#author-a-schema-migration)
12. [Apply migrations programmatically](#apply-migrations-programmatically)
13. [Inspect schemas at runtime](#inspect-schemas-at-runtime)
14. [Emit a CI gate from an IC IR](#emit-a-ci-gate-from-an-ic-ir)
15. [Generate a contract-test stub from an IC IR](#generate-a-contract-test-stub-from-an-ic-ir)
16. [Open a compile run and persist IRs directly](#open-a-compile-run-and-persist-irs-directly)
17. [Walk the vendoring manifest](#walk-the-vendoring-manifest)
18. [Wire dekspec into a pre-commit hook](#wire-dekspec-into-a-pre-commit-hook)
19. [Wire dekspec into GitHub Actions CI](#wire-dekspec-into-github-actions-ci)

---

## Load and inspect a spec graph

```python
from dekspec.api import SpecGraph

g = SpecGraph.load("/path/to/repo", dekspec_root="dekspec")

# Iterate by artifact kind
print(f"ADRs:     {sum(1 for _ in g.adrs())}")
print(f"AEs:      {sum(1 for _ in g.aes())}")
print(f"WSes:     {sum(1 for _ in g.wses())}")
print(f"ICs:      {sum(1 for _ in g.ics())}")
print(f"IBs:      {sum(1 for _ in g.ibs())}")
print(f"Intents:  {sum(1 for _ in g.intents())}")
print(f"Missions: {sum(1 for _ in g.missions())}")
print(f"Glossary: {len(g.glossary()['terms']) if g.glossary() else 0} terms")
print(f"Vision:   {g.vision()['name'] if g.vision() else '(none)'}")

# Look up a specific artifact by id
ae = g.by_id("AE-014")
if ae:
    print(ae["name"], ae.get("subtype"), ae.get("status"))

# Cross-artifact queries
print("AEs referenced by ADR-022:", g.aes_of_adr("ADR-022"))
print("AEs referenced by WS-016:", g.aes_of_ws("WS-016"))
print("AEs referenced by IC-007:", g.aes_of_ic("IC-007"))
print("Consumers of AE-014:", g.consumers_of_ae("AE-014"))

# Parse failures (loader is permissive — failures live on the graph,
# not as exceptions)
for failure in g.parse_failures():
    print(f"[{failure.error_type}] {failure.path}: {failure.message}")
```

---

## Parse a single artifact directly

```python
from dekspec.api import parse_ae, AEParseError

try:
    ir = parse_ae("/path/to/dekspec/architecture-elements/AE-001-foo.md")
except AEParseError as e:
    print(f"Parse failed: {e}")
else:
    print(ir["id"], ir["name"])
    print("Status:", ir["status"])
    print("Subtype:", ir.get("subtype"))
    print("Linked ADRs:", ir.get("linked_artifacts", {}).get("related_adrs", []))
    print("Implements globs:", ir.get("implements_globs", []))
    # parse_warnings is the lossy-parser feedback channel
    for w in ir.get("parse_warnings", []):
        print(f"  warning [{w['severity']}] {w['field']}: {w['reason']}")
```

Each of the 9 artifact types has its own parser + error class:

```python
from dekspec.api import (
    parse_adr, parse_ae, parse_ws, parse, parse_ib,
    parse_intent, parse_mission, parse_vision, parse_glossary,
    ADRParseError, AEParseError, WSParseError, ICParseError, IBParseError,
    IntentParseError, MissionParseError, VisionParseError, GlossaryParseError,
)
```

(`parse` is the alias for `parse_ic` — parsing Interface Contracts.)

---

## Run the full audit battery

```python
from dekspec.api import audit_linkage

findings = audit_linkage("/path/to/repo", dekspec_root="dekspec")

# Severity-grouped summary
from collections import Counter
by_severity = Counter(f.severity for f in findings)
by_rule = Counter(f.rule for f in findings)
print(f"Total: {len(findings)}  ({dict(by_severity)})")
print("By rule:", dict(by_rule.most_common(10)))

# Each finding is a Finding dataclass
for f in findings[:5]:
    print(f"[{f.severity}] {f.rule} {f.artifact_id}")
    print(f"  {f.message}")
    print(f"  fix_kind: {f.fix_kind}")  # 'mechanical' | 'semantic'
```

---

## Auto-fix mechanical findings

The audit identifies L6 + L7 + L8 mirror-gap findings as `fix_kind="mechanical"`. The fix proposer + applier handle these.

```python
from dekspec.api import propose_fixes, apply_fixes

# 1. Propose (read-only — no disk writes yet)
fixes = propose_fixes("/path/to/repo", dekspec_root="dekspec")

# Each Fix is a dataclass with before/after line-edit details
for fix in fixes[:3]:
    print(f"[{fix.rule}] {fix.artifact_id}")
    print(f"  {fix.file_path}:{fix.line_number}")
    print(f"  - {fix.before}")
    print(f"  + {fix.after}")

# 2. Apply (dry-run first to confirm)
dry_result = apply_fixes(fixes, dry_run=True)
print(f"Would apply {dry_result['proposed']} fixes "
      f"(skip={dry_result['skipped_not_found']})")

# 3. Actually apply
result = apply_fixes(fixes, dry_run=False)
print(f"Applied {result['applied']} of {result['proposed']} fixes; "
      f"{result['files_touched']} files touched.")
```

`apply_fixes` is idempotent — re-running it after a successful apply is a no-op because `fix.before` no longer matches the (now-corrected) file content.

---

## Generate AGENTS.md programmatically

```python
from dekspec.api import SpecGraph, agents_md

g = SpecGraph.load("/path/to/repo", dekspec_root="dekspec")

# Per-artifact fragments
fragments = []
for ae in sorted(g.aes(), key=lambda x: x["id"]):
    if ae.get("status") in {"LOCKED", "ACCEPTED"}:
        fragments.append(agents_md.emit_ae(ae))

# Or use the dispatcher to route by id prefix automatically
for ir in g.all():
    aid = ir.get("id", "")
    if aid.startswith("AE-") or aid.startswith("ADR-") or aid.startswith("WS-"):
        try:
            fragments.append(agents_md.emit(ir))
        except ValueError:
            pass  # IC doesn't have an agents-md emitter

agents_md_text = "# AGENTS.md\n\n" + "\n".join(fragments)
print(agents_md_text[:500])
```

For the canonical aggregator output (with header comments, section dividers, and the SpecGraph-level summary line), use the CLI: `dekspec aggregate agents-md`.

---

## Query the SQLite run index

```python
from dekspec.api import open_index, query_runs, repo_state_dir
from pathlib import Path

repo_root = Path("/path/to/repo")
state_dir = repo_state_dir(repo_root)

conn = open_index(state_dir)
try:
    # All runs in the last week
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=7)).isoformat()
    recent = query_runs(conn, since=since, limit=20)
    for row in recent:
        print(f"{row['run_dir_name']}  exit={row['exit_code']}  "
              f"warnings={row['warnings']}")

    # All failed runs (non-zero exit code)
    failed = query_runs(conn, exit_code=2)
    print(f"\n{len(failed)} runs failed with exit code 2")

    # All milestone runs
    milestones = query_runs(conn, milestone=True)
    print(f"{len(milestones)} milestone runs preserved")

    # All runs that touched a specific artifact
    ae_014_runs = query_runs(conn, artifact_id="AE-014", limit=10)
    print(f"\nLast 10 runs that touched AE-014:")
    for row in ae_014_runs:
        print(f"  {row['timestamp']}  {row['run_dir_name']}")
finally:
    conn.close()
```

If the index is empty (e.g., after a manual delete), rebuild it from the on-disk manifest JSONs:

```python
from dekspec.api import reindex

result = reindex(state_dir)
print(f"Reindexed {result['runs_indexed']} runs; "
      f"skipped {result['manifests_skipped']} unreadable manifests.")
```

---

## Check vendoring drift

```python
from dekspec.api import compute_drift

drift = compute_drift("/path/to/consumer/repo")
for f in drift:
    print(f"[{f.kind}] {f.consumer_path}")
    print(f"  {f.detail}")
```

Drift kinds:
- `modified` — file exists in both places but sha256 mismatches.
- `missing` — library publishes the file but the consumer doesn't have it.
- `unknown` — consumer has a vendored file the current library doesn't ship.
- `version` — `.dekspec-version` marker absent or doesn't match the installed library.

Exit-code-style helper (`0` = clean, non-zero = drift):

```python
def vendoring_exit_code(repo_root):
    return 0 if not compute_drift(repo_root) else 1
```

---

## Build a custom CI check

Put together: load graph, run audit, fail if any critical findings.

```python
import sys
from dekspec.api import audit_linkage, SpecGraph

REPO = "/path/to/repo"
DEKSPEC = "dekspec"

# Stage 1: graph parses cleanly
g = SpecGraph.load(REPO, dekspec_root=DEKSPEC)
parse_failures = list(g.parse_failures())
if parse_failures:
    for pf in parse_failures:
        print(f"::error::Parse failed in {pf.path}: {pf.message[:200]}")
    sys.exit(2)

# Stage 2: audit linkage critical-clean
findings = audit_linkage(REPO, dekspec_root=DEKSPEC)
critical = [f for f in findings if f.severity == "critical"]
if critical:
    for f in critical:
        print(f"::error::[{f.rule}] {f.artifact_id}: {f.message}")
    sys.exit(1)

print(f"OK — {sum(1 for _ in g.all())} IRs, "
      f"{len(findings)} non-critical findings.")
sys.exit(0)
```

This is the same logic `dekspec doctor` runs (minus the verify-vendored section). Wire it into your CI as a step or pre-commit hook.

---

## Resolve AE implements_globs through an IC

When you compile an IC, you can union the `implements_globs` from each referenced AE into `IC.affected_paths` — that's the data the CI-gate emitter uses to scope GitLab `rules.changes:`.

```python
from dekspec.api import parse, resolve_aes

# Parse the IC
ic_ir = parse("/path/to/dekspec/interface-contracts/IC-007-formula-engine-evaluation.md")
print("IC.affected_paths before resolve:", ic_ir.get("affected_paths", []))

# Resolve — mutates ic_ir in place, returns it for chaining
resolve_aes(ic_ir)
print("IC.affected_paths after resolve:", ic_ir.get("affected_paths", []))
# → ['services/config.py', 'services/track_timeline.py', 'services/score_hierarchy.py']
```

You can also use `SpecGraph.implements_globs_for(artifact_id)` to query the same data without mutating the IR:

```python
from dekspec.api import SpecGraph

g = SpecGraph.load("/path/to/repo", dekspec_root="dekspec")
globs = g.implements_globs_for("IC-007")
print(globs)
```

---

## Export the whole graph as JSON

For downstream tooling that wants the spec graph as data without reimplementing the parsers:

```python
import json
from dekspec.api import SpecGraph, __version__
from datetime import datetime, timezone

g = SpecGraph.load("/path/to/repo", dekspec_root="dekspec")

document = {
    "schema_version": "1.0",
    "library_version": __version__,
    "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "ir_count": sum(1 for _ in g.all()),
    "parse_failures": [
        {"path": pf.path, "error_type": pf.error_type, "message": pf.message}
        for pf in g.parse_failures()
    ],
    "irs": sorted(g.all(), key=lambda x: x.get("id", "")),
}

with open("graph.json", "w") as f:
    json.dump(document, f, indent=2, default=str)
```

For the same output shape from the shell (`--format json`, since the default is the human-readable `text` render):

```bash
dekspec graph export --format json --pretty --output graph.json
```

---

## Author a schema migration

When an artifact's schema evolves, the change is captured as a `Migration` function registered against `dekspec.migrations.default_registry`. The registry composes migrations into chains so an IR at any prior version can be brought forward to the current schema automatically.

Today the registry is empty (every IR is at v0.1.0). The first real migration follows this pattern:

```python
# tooling/dekspec/migrations/mission.py
from . import default_registry, Migration


def _v0_1_0_to_v0_2_0(ir: dict) -> dict:
    """Collapse `out_of_scope` + `kill_criteria` into a single
    `negative_scope` list (calibration finding from MSN-001 — closes ds-zuy)."""
    out = dict(ir)
    merged = list(ir.get("out_of_scope") or []) + list(ir.get("kill_criteria") or [])
    if merged:
        out["negative_scope"] = merged
    out.pop("out_of_scope", None)
    out.pop("kill_criteria", None)
    out["ir_schema_version"] = "0.2.0"
    return out


default_registry.register(Migration(
    artifact_type="mission",
    from_version="0.1.0",
    to_version="0.2.0",
    migrate=_v0_1_0_to_v0_2_0,
    description="Collapse out_of_scope + kill_criteria into negative_scope",
))
```

Each migration is a pure function from one IR shape to the next. The registry composes them: a v0.1.0 IR run through a v0.1.0→v0.2.0→v0.3.0 chain is upgraded transparently.

Apply a migration to a single IR via the public API:

```python
from dekspec.api import migrate_ir

old_ir = {"id": "MSN-001", "ir_schema_version": "0.1.0", ...}
new_ir = migrate_ir(old_ir)  # → upgraded to the latest registered version
```

Apply across many persisted IR JSON files via the CLI:

```bash
# Dry-run: show what would migrate, no writes
dekspec migrate-ir ~/.local/share/dekspec/<fingerprint>/runs/*/irs/*.ir.json

# Actually write the upgrades
dekspec migrate-ir ~/.local/share/dekspec/<fingerprint>/runs/*/irs/*.ir.json --apply

# Stop at an intermediate version (e.g., to debug a multi-step chain)
dekspec migrate-ir path/to/MSN-001.ir.json --to 0.2.0
```

The migration registry validates its own chains at startup — if a step is missing between two registered versions, the CLI refuses to run and surfaces the gap. See [`tooling/dekspec/migrations/__init__.py`](../tooling/dekspec/migrations/__init__.py) module docstring for the full authoring procedure (schema-file update + parser-version bump + test).

## Apply migrations programmatically

`migrate_ir` upgrades a single IR dict; the underlying `default_registry` exposes per-step machinery for batch tooling.

```python
from dekspec.api import (
    Migration,
    MigrationError,
    Registry,
    default_registry,
    migrate_ir,
    target_version_for,
)

# Latest registered target version for each IR type.
print("Latest Mission target:", target_version_for("mission", "0.1.0"))
print("Latest Intent target:", target_version_for("intent", "0.1.0"))

# Upgrade one IR to latest:
old = {"id": "MSN-001", "ir_schema_version": "0.1.0", "name": "Example", ...}
new = migrate_ir(old)  # uses default_registry; target is latest registered
print(new["ir_schema_version"])

# Upgrade to an intermediate version (useful while debugging a chain):
mid = migrate_ir(old, to_version="0.2.0")

# Build your own registry for custom IR shapes:
custom = Registry()
custom.register(Migration(
    artifact_type="my_ir",
    from_version="0.1.0",
    to_version="0.2.0",
    migrate=lambda ir: {**ir, "ir_schema_version": "0.2.0", "new_field": None},
    description="Add `new_field` (always null on upgrade).",
))
chain = custom.chain("my_ir", "0.1.0", "0.2.0")
print(f"{len(chain)} step(s)")

# Catch missing chains at startup rather than mid-batch:
problems = default_registry.validate_chains()
if problems:
    raise MigrationError("\n".join(problems))
```

The registry is linear (one `to_version` per `(artifact_type, from_version)`) and refuses downgrades — `MigrationError` is raised on either a missing intermediate step or a `from_version > to_version` request.

## Inspect schemas at runtime

`dekspec.schemas` loads bundled JSON-Schema YAMLs through `importlib.resources`, so the schemas resolve cleanly whether dekspec was installed from a wheel, a source checkout, or an editable install.

```python
from dekspec.api import (
    LATEST_VERSIONS,
    SCHEMA_FILENAMES,
    SchemaNotFoundError,
    list_schemas,
    load_schema,
)

# Inventory: every (artifact_type, version) currently shipped.
for artifact_type, version in list_schemas():
    print(f"{artifact_type:22}  v{version}")

# Convenience maps for "what's the current schema version?"
print(LATEST_VERSIONS["mission"])    # → "0.1.0"
print(SCHEMA_FILENAMES["intent"])    # → "intent.schema.yaml"

# Load a schema dict (default: latest registered version).
mission_schema = load_schema("mission")
required = mission_schema.get("required", [])
print("Mission required fields:", required)

# Pin a specific version (e.g., to validate an old persisted IR).
try:
    legacy = load_schema("intent", version="0.1.0")
except SchemaNotFoundError as e:
    print(f"Not registered: {e}")

# Schemas are plain JSON-Schema Draft 2020-12 dicts — feed them to jsonschema:
import jsonschema
jsonschema.validate(instance=my_intent_ir, schema=load_schema("intent"))
```

`load_schema` accepts `domain_glossary` / `system_vision` along with the seven prefixed IR kinds. Underscores, not hyphens.

## Emit a CI gate from an IC IR

`ci_gate.emit(ir)` returns a GitLab CI job YAML fragment for one Interface Contract — the CI gate that fires when either the IC markdown or any of the IC's `affected_paths` change.

```python
from pathlib import Path

from dekspec.api import ci_gate, parse, resolve_aes

ic_ir = parse("/path/to/dekspec/interface-contracts/IC-007-formula-engine.md")
resolve_aes(ic_ir)  # populate affected_paths from referenced AEs

yaml_text = ci_gate.emit(ic_ir)
filename = ci_gate.suggested_filename(ic_ir)
# → "ic-007-formula-engine.gitlab-ci.yml"

out = Path(".gitlab/ci/contract-gates") / filename
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(yaml_text, encoding="utf-8")
print(f"Wrote {out}")
```

Behavior:
- The emitted YAML has `rules.changes:` scoped to the IC source path + every `affected_paths` entry, so the job only runs when contract-relevant code changes.
- If `affected_paths` is empty, the emitter writes a clear warning into the YAML header — the gate will still trigger on IC-source edits but won't fire on code-only changes. Run `resolve_aes(ir)` (or `--resolve-aes` on the CLI) first to populate paths from each referenced AE's `implements_globs`.
- `ci_gate.suggested_filename(ir)` gives the conventional filename — use it directly so multiple ICs land at predictable paths.

The emitter is pure: same IR in, same YAML out. Generated files are safe to commit; the YAML header records the source SHA-256 so drift is easy to diff.

## Generate a contract-test stub from an IC IR

`contract_test.emit(ir)` returns a pytest module — one `def test_<operation>(...)` per IC operation, plus structural fixtures and a parse-warning summary. Every assertion is `pytest.skip("CONTRACT_STUB: ...")` initially; the engineer implementing the consumer fills the body in.

```python
from pathlib import Path

from dekspec.api import contract_test, parse

ic_ir = parse("/path/to/dekspec/interface-contracts/IC-007-formula-engine.md")
test_source = contract_test.emit(ic_ir)
filename = contract_test.suggested_filename(ic_ir)
# → "test_ic_007_formula_engine.py"

out = Path("tests/contract") / filename
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(test_source, encoding="utf-8")
print(f"Wrote {out}")
```

What the emitted file contains:
- Module docstring with IC id, name, status, source path + SHA-256, and the parser/emitter versions used.
- One `def test_<op>_holds(...)` per operation in `ic_ir["operations"]`, with a `pytest.skip` body indicating which fields drove the stub.
- A consistency section with `pytest.skip` placeholders for cross-operation invariants and `parse_warnings` (so warnings surface in the test run instead of being silently dropped).
- An operations fixture (`@pytest.fixture` returning the IR's operations list).

The stubs are intentionally unimplemented — `dekspec compile <ic> --emit contract-test` is the regeneration story; engineers should not hand-edit the generated file. Real assertions belong in a sibling module that imports the fixtures from the generated one.

`contract_test.suggested_filename(ir)` returns the conventional `test_<ic_id>_<slug>.py` so downstream emitters (e.g., `ci_gate`) reference the same path.

## Open a compile run and persist IRs directly

The `dekspec compile` CLI persists every invocation under `$XDG_DATA_HOME/dekspec/<repo-fingerprint>/runs/<timestamp>-<run-id>/`. To produce the same artifacts from Python — useful for custom batch compilers or test fixtures — drive the `open_run` context manager directly.

```python
from dekspec.api import open_run, parse_ae, parse, ci_gate

REPO = "/path/to/consumer/repo"

with open_run(REPO, trigger="custom-batch", command="my_tool --batch") as writer:
    # Parse + persist an AE
    ae_ir = parse_ae("/path/to/dekspec/architecture-elements/AE-014-foo.md")
    writer.record_artifact(ae_ir)

    # Parse an IC, emit its CI gate, record both
    ic_ir = parse("/path/to/dekspec/interface-contracts/IC-007.md")
    writer.record_artifact(ic_ir)

    yaml_text = ci_gate.emit(ic_ir)
    out_path = "/tmp/ic-007.gitlab-ci.yml"
    with open(out_path, "w") as f:
        f.write(yaml_text)
    writer.record_emission(
        emitter="ci_gate",
        artifact_id=ic_ir["id"],
        output_path=out_path,
        output_size=len(yaml_text),
    )

    # Custom events (anything you want to surface in events.jsonl)
    writer.event("custom_milestone", note="batch midpoint reached")

# On block exit: manifest.json is flushed, `latest` symlink refreshed,
# old runs pruned (default: keep most recent 200 non-milestone runs).
```

The `Run` dataclass carries the in-memory bookkeeping (`run_id`, `timestamp`, parser/emitter versions, warning counts, exit code, duration). `RunWriter` wraps it with file-writing helpers and is what you actually use inside the `with` block. On exit `open_run` always flushes the manifest — even if the body raises — so partial runs are still inspectable via `dekspec runs show <run_id>`.

For lower-level inspection of the SQLite index (which `dekspec runs ls/show/gc` reads), see [the SQLite run-index section above](#query-the-sqlite-run-index).

## Walk the vendoring manifest

`iter_vendored_pairs` is the canonical source for "which files does the install script copy where?" Use it from custom tooling that needs to mirror or audit vendored content without shelling out to `install-dekspec.sh`.

```python
from pathlib import Path

from dekspec.api import iter_vendored_pairs, library_root

# Inspect the library checkout the installed package lives in.
print("Library root:", library_root())
# → /path/to/dekspec  (the repo root of the library, parent of tooling/)

# Enumerate every (library_src, consumer_dst) pair.
for src, dst in iter_vendored_pairs(repo_root=Path("/path/to/consumer/repo")):
    print(f"{src.relative_to(library_root())}  →  {dst}")
# .claude/skills/<name>/SKILL.md ...
# dekspec/templates/ae-template.md ...
# dekspec/dekspec-operating-guide.md
# dekspec/architecture.md
# dekspec/cli-reference.md  (since v0.38.x)
# dekspec/EXAMPLES.md       (since v0.38.x)
```

`library_root()` resolves to the install-time package layout, so the same code works against an editable checkout (`pip install -e`) and an installed wheel. `iter_vendored_pairs` yields one tuple per vendored file — a custom `install-dekspec` re-implementation is roughly:

```python
import shutil
from pathlib import Path

from dekspec.api import __version__, iter_vendored_pairs

def vendor(consumer_repo: Path) -> None:
    for src, dst in iter_vendored_pairs(repo_root=consumer_repo):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    (consumer_repo / ".dekspec-version").write_text(__version__, encoding="utf-8")
```

`compute_drift` (already covered) is the inverse: walks the same manifest and reports modified / missing / unknown / version findings.

## Wire dekspec into a pre-commit hook

Run `dekspec doctor` (or `dekspec validate` for narrower scope) on every commit. Two ways:

### Option A: the [pre-commit framework](https://pre-commit.com/) (recommended)

`.pre-commit-config.yaml` at the consumer repo root:

```yaml
repos:
  - repo: local
    hooks:
      - id: dekspec-doctor
        name: dekspec doctor
        entry: dekspec doctor --json
        language: system
        pass_filenames: false
        # Only fail the commit on critical findings (exit 2);
        # warnings (exit 1) print but don't block.
        stages: [pre-commit]
        verbose: true

      - id: dekspec-validate-changed-artifacts
        name: dekspec validate (changed artifacts only)
        entry: bash -c 'for f in "$@"; do dekspec validate "$f" || exit $?; done' --
        language: system
        files: ^dekspec/(adrs|architecture-elements|working-specs|interface-contracts|intents|missions|impl-briefs)/.*\.md$
        # Run validate on each changed artifact file only — fast.
```

Then `pre-commit install`. On each commit, the framework runs both hooks against the staging area.

### Option B: a hand-rolled `.git/hooks/pre-commit`

For repos that don't use the pre-commit framework:

```bash
#!/usr/bin/env bash
# .git/hooks/pre-commit — block commit when dekspec doctor reports critical.
set -euo pipefail

# 1. Validate each changed artifact file (fast, file-scoped check).
while IFS= read -r file; do
  if [[ "$file" =~ ^dekspec/(adrs|architecture-elements|working-specs|interface-contracts|intents|missions|impl-briefs)/.*\.md$ ]]; then
    dekspec validate "$file" || exit $?
  fi
done < <(git diff --cached --name-only --diff-filter=ACM)

# 2. Repo-wide doctor (composite drift + audit + parse check).
if ! dekspec doctor; then
  rc=$?
  if [[ $rc -ge 2 ]]; then
    echo "dekspec doctor reported critical findings; commit blocked." >&2
    exit $rc
  fi
  echo "dekspec doctor reported warnings (not blocking)." >&2
fi
```

Make it executable: `chmod +x .git/hooks/pre-commit`.

### Choosing the right scope

| Hook trigger | What to run | Why |
|---|---|---|
| Every commit | `dekspec validate <changed-file>` | Fast, file-scoped, catches malformed YAML / schema-validation errors before they reach main. |
| Every commit (additional) | `dekspec doctor` | Repo-wide. Catches cross-artifact issues (linkage, parse failures) that a single-file validate misses. Exit 1 = warning, exit 2 = critical. |
| Pre-push only | `dekspec audit linkage --severity critical` | Comprehensive but slower. Only enforce critical findings at push time. |

The validate hook is cheap (each invocation parses a single file); the doctor hook is moderate (loads the whole spec graph). For repos with >100 artifacts, consider running doctor on pre-push instead of pre-commit.

---

## Wire dekspec into GitHub Actions CI

Two patterns: a per-PR gate and a scheduled daily audit.

### Per-PR gate

`.github/workflows/dekspec.yml`:

```yaml
name: DekSpec

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  doctor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - name: Install dekspec
        run: pip install git+https://github.com/Dektora/dekspec.git@v0.112.0
      - name: Vendor dekspec skills + templates
        run: bash scripts/install-dekspec.sh
      - name: Run dekspec doctor
        run: dekspec doctor --json | tee dekspec-doctor.json
      - name: Run audit linkage (critical-only)
        run: dekspec audit linkage --severity critical --json | tee dekspec-audit.json
      - name: Upload audit results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: dekspec-results
          path: |
            dekspec-doctor.json
            dekspec-audit.json
```

Exit codes:
- doctor: 0 = clean, 1 = warnings (CI passes), 2 = critical (CI fails).
- audit linkage: 0 = no critical findings, 1 = any critical present.

### Scheduled daily audit

For long-lived repos, schedule a daily `dekspec audit --json` run that posts a summary to a Slack / Teams webhook when findings exceed a threshold. (Example webhook step omitted — the audit JSON envelope makes scripting trivial; see the `summary.critical` / `summary.important` fields.)

---

## See also

- [README.md](../README.md) — quick-start + the canonical install + audit-fix workflow.
- [architecture.md](architecture.md) — source → IR → emitters → runtime mental model.
- [`tooling/dekspec/api.py`](../tooling/dekspec/api.py) — the public API module itself (read the docstring for the canonical list of exports).
- [`tooling/dekspec/schemas/`](../tooling/dekspec/schemas/) — JSON Schema definitions for every IR.
- [CHANGELOG.md](../CHANGELOG.md) — per-version detail.
