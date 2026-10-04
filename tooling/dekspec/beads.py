"""Project bead identity and bounded, non-destructive store operations.

Only issue/governance stores are created. Legacy root stores are never changed.
Operational checks run on disposable copies: some br versions mutate a database
on open even for read verbs. An unreadable/unknown export is never a rebuild source.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

KINDS = {'issue': ('.beads-issues', 'iss'), 'dekspec': ('.beads-dekspec', 'ds')}
TIMEOUT = 5


class BeadsError(ValueError):
    """An actionable identity, operational-health or preservation failure."""


def project_prefix(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch('[a-z0-9]{2,6}', value) is None:
        raise BeadsError('project prefix must be 2–6 lowercase ASCII letters or digits')
    return value


def _yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        doc = yaml.safe_load(path.read_text()) or {}
    except (OSError, yaml.YAMLError) as e:
        raise BeadsError(f'Cannot read {path}: {e}') from e
    if not isinstance(doc, dict):
        raise BeadsError(f'Expected a mapping in {path}')
    return doc


def configured_project(root: Path) -> str | None:
    doc = _yaml(root / '.dekspec/config.yaml')
    tracker = doc.get('issue_tracker')
    if isinstance(tracker, dict) and any(tracker.get(f'{kind}_workspace', directory) != directory for kind, (directory, _) in KINDS.items()):
        raise BeadsError('Nondefault workspace declarations require an explicit migration plan; refusing conventional-store mutation')
    if 'beads' not in doc:
        return None
    beads = doc['beads']
    if isinstance(beads, dict) and set(beads) - {'project_prefix'}:
        raise BeadsError('Unsupported beads configuration keys; refusing to guess workspace identity')
    if not isinstance(beads, dict) or 'project_prefix' not in beads:
        raise BeadsError('beads.project_prefix is missing or malformed')
    return project_prefix(beads['project_prefix'])


def store_prefix(path: Path, default: str, project: str | None = None) -> str:
    doc = _yaml(path / 'config.yaml')
    pin = doc.get('issue_prefix')
    if 'issue_prefix' in doc and (not isinstance(pin, str) or not pin or len(pin) > 64 or pin.lower() != pin or not pin.isprintable()):
        raise BeadsError(f'Invalid issue_prefix in {path / "config.yaml"}')
    expected = f'{project}-{default}' if project else pin or default
    if project and pin and pin != expected:
        raise BeadsError(f'prefix mismatch: {path} pins {pin}, expected {expected}; use beads reprefix')
    for row in read_rows(path / 'issues.jsonl'):
        if not row['id'].startswith(expected + '-'):
            raise BeadsError(f'prefix mismatch: {row["id"]} in {path}; expected {expected}-; pin the actual identity or use beads reprefix')
    return expected


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if any(not isinstance(r, dict) or not isinstance(r.get('id'), str) for r in rows):
            raise ValueError('every row requires an id')
        if len({r['id'] for r in rows}) != len(rows):
            raise ValueError('duplicate IDs')
        return rows
    except (OSError, ValueError) as e:
        raise BeadsError(f'Invalid bead export {path}: {e}') from e


def _run(path: Path, *args: str, timeout: float = TIMEOUT) -> subprocess.CompletedProcess:
    binary = shutil.which('br')
    if not binary:
        raise BeadsError('br unavailable; run dekspec dependencies install br')
    # Ambient overrides must not redirect a supposedly disposable probe into
    # a real workspace. Explicit DB and cwd are always supplied.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('BEADS_', 'BR_', 'BD_'))}
    try:
        result = subprocess.run([binary, '--db', str(path / 'beads.db'), '--no-auto-import',
                                 '--no-auto-flush', *args], cwd=path.parent,
                                env=env, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise BeadsError(f'br operational probe failed within {timeout}s: {e}; preserve DB/WAL and run dekspec resource doc beads-recovery') from e
    if result.returncode:
        raise BeadsError(f'br {args[0]} failed: {(result.stderr or result.stdout)[:500]}; preserve DB/WAL; run dekspec resource doc beads-recovery')
    return result


def _pin(path: Path, prefix: str) -> None:
    config = path / 'config.yaml'
    doc = _yaml(config)
    if doc.get('issue_prefix') == prefix:
        return
    text = config.read_text() if config.exists() else ''
    if 'issue_prefix' in doc:
        raise BeadsError(f'Existing prefix in {config} requires explicit migration')
    config.write_text(text.rstrip('\n') + '\nissue_prefix: ' + json.dumps(prefix) + '\n')


def initialize(root: Path, project: str | None = None) -> None:
    for relative in ['.dekspec', '.dekspec/config.yaml'] + [directory + '/.beads' for directory, _ in KINDS.values()]:
        _safe_relative(root, relative)
    project = project_prefix(project) if project is not None else configured_project(root)
    # Check every existing store before changing either one.
    entries = [(root / directory / '.beads', store_prefix(root / directory / '.beads', kind, project))
               for directory, kind in KINDS.values()]
    for path, _ in entries:
        for source in path.rglob('*') if path.exists() else []:
            _safe_relative(root, str(source.relative_to(root)))
    for path, prefix in entries:
        path.mkdir(parents=True, exist_ok=True)
        _pin(path, prefix)
        if not (path / 'beads.db').exists() and not (path / 'issues.jsonl').exists():
            _run(path, 'init', '--prefix', prefix)
            _run(path, 'sync', '--import-only')
            _run(path, 'sync', '--flush-only')
        # br init can generate a commented default; pin after initialization too.
        _pin(path, prefix)


def probe(path: Path, *, timeout: float = TIMEOUT) -> dict:
    """Return operational status without opening the original database."""
    with tempfile.TemporaryDirectory(prefix='dekspec-beads-probe-') as tmp:
        copy = Path(tmp) / '.beads'
        shutil.copytree(path, copy, symlinks=True)
        if any(p.is_symlink() for p in copy.rglob('*')):
            raise BeadsError(f'Symlink in store {path}; cannot safely probe')
        if not (copy / 'beads.db').exists():
            _run(copy, 'sync', '--import-only', timeout=timeout)
        try:
            status = json.loads(_run(copy, 'sync', '--status', '--json', timeout=timeout).stdout)
        except json.JSONDecodeError as e:
            raise BeadsError(f'Unknown br health response for {path}') from e
        if not isinstance(status, dict) or not isinstance(status.get('dirty_count'), int):
            raise BeadsError(f'Unknown br health schema for {path}; export completeness cannot be established')
        if status.get('workspace_health', 'healthy') != 'healthy' or status.get('coverage_drift', False):
            raise BeadsError(f'Unhealthy bead store {path}: {status}')
        return status


def health(root: Path, *, timeout: float = TIMEOUT) -> list[dict]:
    result = []
    try:
        project = configured_project(root)
    except BeadsError as e:
        return [{'kind': 'config', 'status': 'error', 'detail': str(e)}]
    for name, (directory, kind) in KINDS.items():
        path = root / directory / '.beads'
        if not ((path / 'issues.jsonl').exists() or (path / 'beads.db').exists()):
            continue
        try:
            prefix = store_prefix(path, kind, project)
            status = probe(path, timeout=timeout)
            result.append({'kind': name, 'status': 'healthy', 'prefix': prefix, 'dirty_count': status['dirty_count']})
        except (BeadsError, OSError) as e:
            result.append({'kind': name, 'status': 'error', 'detail': str(e)})
    return result


def _canonical(rows: list[dict]) -> str:
    # Array order is meaningful in issue text, but relations are unordered.
    data = []
    for row in rows:
        row = dict(row)
        for name in ('dependencies', 'comments', 'labels'):
            if name in row:
                row[name] = sorted(row[name], key=lambda x: json.dumps(x, sort_keys=True))
        data.append(row)
    return json.dumps(sorted(data, key=lambda r: r['id']), sort_keys=True)


def _prove_export(path: Path) -> None:
    """Flush a copy, require byte-independent full semantic equivalence."""
    if not (path / 'issues.jsonl').exists():
        raise BeadsError(f'Missing JSONL export for {path}; export completeness unknown')
    if not (path / 'beads.db').exists():
        return
    with tempfile.TemporaryDirectory(prefix='dekspec-beads-export-') as tmp:
        copy = Path(tmp) / '.beads'
        shutil.copytree(path, copy)
        result = json.loads(_run(copy, 'sync', '--status', '--json').stdout)
        if result.get('dirty_count') != 0:
            raise BeadsError(f'Unexported or unknown DB state in {path}; flush and review before migration')
        _run(copy, 'sync', '--flush-only', '--force')
        if _canonical(read_rows(copy / 'issues.jsonl')) != _canonical(read_rows(path / 'issues.jsonl')):
            raise BeadsError(f'DB and JSONL differ in {path}; export completeness unknown, refusing rebuild')


def _pattern(mapping: dict[str, str]) -> re.Pattern:
    # A hyphen is part of slug IDs; a dot belongs to a child ID only when a
    # number follows it. Prose sentence punctuation must still match.
    return re.compile(r'(?<![A-Za-z0-9_-])(?:' + '|'.join(re.escape(x) for x in sorted(mapping, key=len, reverse=True)) + r')(?![A-Za-z0-9_-]|\.[0-9])')


def _links(rows: list[dict], known: set[str]) -> None:
    for row in rows:
        if not isinstance(row.get('dependencies', []), list) or not isinstance(row.get('comments', []), list):
            raise BeadsError(f'Malformed relations in {row["id"]}')
        for dep in row.get('dependencies', []):
            if not isinstance(dep, dict) or not dep.get('depends_on_id'):
                raise BeadsError(f'Malformed dependency in {row["id"]}')
            for key in ('issue_id', 'depends_on_id'):
                if dep.get(key) and dep[key] not in known:
                    raise BeadsError(f'Dangling dependency {dep[key]} in {row["id"]}')
        for comment in row.get('comments', []):
            if not isinstance(comment, dict):
                raise BeadsError(f'Malformed comment in {row["id"]}')
            if comment.get('issue_id', row['id']) not in known:
                raise BeadsError(f'Dangling comment in {row["id"]}')


def _tracked(root: Path) -> list[Path]:
    proc = subprocess.run(['git', 'ls-files', '-z'], cwd=root, capture_output=True, env={k: v for k, v in os.environ.items() if not k.startswith('GIT_')})
    if proc.returncode:
        raise BeadsError('reprefix requires a Git repository to bound reference rewriting')
    return [root / os.fsdecode(p) for p in proc.stdout.split(b'\0') if p]


def _fingerprint(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(str(path.relative_to(root)).encode() + b'\0')
        digest.update(path.read_bytes() if path.is_file() else b'<absent>')
    return digest.hexdigest()


def plan_reprefix(root: Path, target: str) -> tuple[dict, dict[Path, bytes], dict[Path, Path]]:
    """Read-only preview. All construction/rebuilds happen in temporary storage."""
    target = project_prefix(target)
    if (root / '.br_recovery/active.json').exists():
        raise BeadsError('Interrupted migration exists; run dekspec beads recover --at <repo> before planning')
    stores, mapping, all_rows = [], {}, []
    current_project = configured_project(root)
    source_paths = _tracked(root)
    for path in [root / directory for directory, _ in KINDS.values()] + [root / '.dekspec', root / '.br_recovery']:
        _safe_relative(root, str(path.relative_to(root)))
    for directory, kind in KINDS.values():
        path = root / directory / '.beads'
        if not path.exists():
            continue
        if any(p.is_symlink() for p in path.rglob('*')):
            raise BeadsError(f'Symlink in store {path}')
        prefix = store_prefix(path, kind, current_project)
        _prove_export(path)
        rows = read_rows(path / 'issues.jsonl')
        for row in rows:
            old = row['id']
            if old in mapping:
                raise BeadsError(f'Ambiguous ID {old} occurs in multiple stores')
            mapping[old] = target + '-' + kind + old[len(prefix):]
        all_rows.extend(rows)
        stores.append({'path': str(path.relative_to(root)), 'prefix': target + '-' + kind})
        source_paths.extend(p for p in path.rglob('*') if p.is_file() and not p.name.endswith('.lock'))
    if not stores:
        raise BeadsError('No issue/governance stores found; initialize before migration')
    if len(set(mapping.values())) != len(mapping):
        raise BeadsError('Target ID collision')
    _links(all_rows, set(mapping))
    mapping = {old: new for old, new in mapping.items() if old != new}
    pattern = _pattern(mapping) if mapping else None
    path_pattern = re.compile(pattern.pattern.replace('[A-Za-z0-9_-])', '[A-Za-z0-9_])', 1)) if pattern else None
    edits, renames = {}, {}
    for path in sorted(set(source_paths)):
        _safe_relative(root, str(path.relative_to(root)))
        if not path.exists() or path.is_dir():
            continue
        relative = path.relative_to(root)
        # Only the authoritative export/config are edited inside stores.
        in_store = any(path.is_relative_to(root / s['path']) for s in stores)
        if in_store and path.name not in ('issues.jsonl', 'config.yaml'):
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            if pattern and pattern.search(raw.decode('latin1')):
                raise BeadsError(f'Known ID in binary file {relative}; manual migration required')
            continue
        new_text = pattern.sub(lambda m: mapping[m[0]], text) if pattern else text
        new_name = path_pattern.sub(lambda m: mapping[m[0]], str(relative)) if path_pattern else str(relative)
        if new_text != text or new_name != str(relative):
            if any(part in {'execution', 'execution-records', 'runs', 'records'} for part in relative.parts) or re.search(r'"(?:fingerprint|previous_hash|contract_hash|chain_hash)"\s*:', text):
                raise BeadsError(f'Hash-bound evidence in {relative}; preserve records and obtain an explicit migration decision')
            if re.search(r'https?://[^\s<>]*' + '(?:' + '|'.join(re.escape(x) for x in mapping) + ')', text):
                raise BeadsError(f'Ambiguous cross-repository URL in {relative}; resolve ownership before migration')
            edits[path] = new_text.encode()
            if new_name != str(relative):
                dest = root / new_name
                if dest.exists() or dest in renames.values():
                    raise BeadsError(f'Path collision: {new_name}')
                renames[path] = dest
    cfgpath = root / '.dekspec/config.yaml'
    cfg = _yaml(cfgpath) or {'schema_version': '0.1.0', 'methodology_profile': 'full'}
    cfg['beads'] = {**cfg.get('beads', {}), 'project_prefix': target}
    edits[cfgpath] = yaml.safe_dump(cfg, sort_keys=False).encode()
    for s in stores:
        path = root / s['path'] / 'config.yaml'
        cfg = _yaml(path)
        cfg['issue_prefix'] = s['prefix']
        edits[path] = yaml.safe_dump(cfg, sort_keys=False).encode()
    ignore = root / '.gitignore'
    content = ignore.read_text() if ignore.exists() else ''
    if '.br_recovery/' not in content.splitlines():
        edits[ignore] = (content.rstrip('\n') + '\n.br_recovery/\n').encode()
    source_paths.extend(edits)
    receipt = {'target': target, 'ids': mapping, 'stores': stores,
               'files': [str(p.relative_to(root)) for p in sorted(edits)],
               'renames': {str(p.relative_to(root)): str(q.relative_to(root)) for p, q in renames.items()},
               'source_hash': _fingerprint(source_paths, root)}
    receipt['plan_sha256'] = hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()
    return receipt, edits, renames


def _journal(path: Path, payload: dict) -> None:
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as stream:
        json.dump(payload, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def _safe_relative(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise BeadsError('Invalid recovery path')
    rel = Path(relative)
    if any(part in {"..", "."} for part in rel.parts):
        raise BeadsError('Recovery path escapes repository')
    path = root / rel
    for ancestor in [path, *path.parents]:
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise BeadsError(f'Symlink in recovery path: {relative}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise BeadsError('Recovery path escapes repository')
    return path


def _validated_recovery(root: Path, record: dict) -> Path:
    if not isinstance(record, dict) or not isinstance(record.get('files'), dict) or not isinstance(record.get('stores'), list) or not isinstance(record.get('destinations'), list):
        raise BeadsError('Invalid recovery journal schema; preserve current state')
    relative = record.get('backup')
    backup = _safe_relative(root, relative)
    if len(Path(relative).parts) != 2 or Path(relative).parts[0] != '.br_recovery':
        raise BeadsError('Invalid recovery backup path')
    expected_stores = {directory + '/.beads' for directory, _ in KINDS.values()}
    if not set(record['stores']).issubset(expected_stores):
        raise BeadsError('Unknown recovery store path')
    for relative, existed in record['files'].items():
        _safe_relative(root, relative)
        if type(existed) is not bool:
            raise BeadsError('Invalid recovery file existence flag')
    for relative in record['destinations'] + record['stores']:
        _safe_relative(root, relative)
    hashes = record.get('backup_hashes')
    if not isinstance(hashes, dict) or not hashes:
        raise BeadsError('Recovery backup completeness is unknown')
    for relative, digest in hashes.items():
        source = _safe_relative(backup, relative)
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise BeadsError(f'Recovery backup missing or corrupt: {relative}; preserve current state')
    for relative, existed in record['files'].items():
        if existed and 'files/' + relative not in hashes:
            raise BeadsError(f'Recovery backup does not cover {relative}')
    for relative in record['stores']:
        directory = _safe_relative(backup, 'stores/' + relative)
        if not directory.is_dir():
            raise BeadsError(f'Missing recovery store {relative}')
        for path in directory.rglob('*'):
            if path.is_symlink() or (path.is_file() and str(path.relative_to(backup)) not in hashes):
                raise BeadsError(f'Unexpected recovery file {path}')
    return backup


@contextmanager
def _migration_locks(root: Path):
    """Hold br's canonical-path opener barrier across DB replacement (Linux).

    Protocol: beads-rust v0.7.4 src/sync/mod.rs database_opener_lease_path.
    Existing processes hold a shared lease; exclusive acquisition fails fast.
    New br processes cannot open either old or replacement DB while held.
    """
    import sys
    if not sys.platform.startswith('linux'):
        raise BeadsError('Reprefix apply/recovery is qualified on Linux only; no files changed')
    import fcntl
    handles = []
    try:
        for directory, _ in KINDS.values():
            path = root / directory / '.beads'
            if not path.exists():
                continue
            _safe_relative(root, str(path.relative_to(root)))
            db = path / 'beads.db'
            if db.exists() and db.stat().st_nlink > 1:
                raise BeadsError('Hard-linked bead database; cannot establish exclusive migration ownership')
            digest = hashlib.sha256(b'beads-rust-database-openers-v1\0' + os.fsencode(db.resolve())).hexdigest()[:24]
            lease = path / f'.br-db-openers-{digest}.lock'
            # A DB produced by an unqualified old writer cannot be migrated
            # under an invented lock convention. Upgrade/recover deliberately.
            if db.exists() and not lease.exists():
                raise BeadsError('Store lacks the supported br opener lease; use br0.7.4 and establish export parity first')
            names = [lease.with_suffix('.transition.lock'), lease]
            for lock in names:
                _safe_relative(root, str(lock.relative_to(root)))
                descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                handle = os.fdopen(descriptor, 'a')
                handles.append(handle)
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise BeadsError('Bead store is in use; stop the writer and rerun the preview; no originals changed') from error
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def recover(root: Path) -> dict:
    # Validate before creating any lock file: malformed journals must be inert.
    active = root / '.br_recovery/active.json'
    if not active.exists():
        return {'status': 'no interrupted migration'}
    _safe_relative(root, '.br_recovery/active.json')
    _validated_recovery(root, json.loads(active.read_text()))
    with _migration_locks(root):
        return _recover_locked(root)


def _recover_locked(root: Path) -> dict:
    """Restore the saved pre-migration state after a failed/interrupted apply.

    Backups are retained, including original DB sidecars. Never guesses that
    an interrupted rebuild was successful. Operator explicitly requests this.
    """
    active = root / '.br_recovery/active.json'
    if not active.exists():
        return {'status': 'no interrupted migration'}
    _safe_relative(root, '.br_recovery/active.json')
    record = json.loads(active.read_text())
    backup = _validated_recovery(root, record)
    for relative in record['destinations']:
        path = root / relative
        if path.is_file() or path.is_symlink():
            path.unlink()
    for relative, existed in record['files'].items():
        path = root / relative
        if existed:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup / 'files' / relative, path)
        elif path.exists():
            path.unlink()
    for relative in record['stores']:
        path = root / relative
        # Do not unlink/replace the held opener-barrier inodes during rollback.
        path.mkdir(parents=True, exist_ok=True)
        for entry in path.iterdir():
            if entry.name.endswith('.lock'):
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        for source in (backup / 'stores' / relative).rglob('*'):
            destination = path / source.relative_to(backup / 'stores' / relative)
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif not source.name.endswith('.lock'):
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    record['status'] = 'rolled back'
    _journal(backup / 'receipt.json', record)
    active.unlink()
    (root / '.br_recovery/lock').unlink(missing_ok=True)
    return {'status': 'rolled back', 'backup': str(backup)}


def apply_reprefix(root: Path, target: str, expected: str) -> dict:
    with _migration_locks(root):
        return _apply_reprefix_locked(root, target, expected)


def _apply_reprefix_locked(root: Path, target: str, expected: str) -> dict:
    """Build/verify both new stores first, then publish with rollback journal."""
    import uuid

    receipt, edits, renames = plan_reprefix(root, target)
    if receipt['plan_sha256'] != expected:
        raise BeadsError('Preview is stale; rerun beads reprefix and review the new plan_sha256')
    if not receipt['ids'] and all(p.exists() and p.read_bytes() == data for p, data in edits.items()):
        return {**receipt, 'status': 'already qualified'}
    with tempfile.TemporaryDirectory(prefix='dekspec-beads-stage-') as tmp:
        stage = Path(tmp)
        for index, store in enumerate(receipt['stores']):
            staged = stage / str(index) / '.beads'
            staged.mkdir(parents=True)
            original = root / store['path']
            for name in ('issues.jsonl', 'config.yaml'):
                source = original / name
                content = edits.get(source, source.read_bytes() if source.exists() else b'')
                (staged / name).write_bytes(content)
            _run(staged, 'init', '--prefix', store['prefix'])
            # br init may replace a config: restore the tracked pin.
            (staged / 'config.yaml').write_bytes(edits[original / 'config.yaml'])
            _run(staged, 'sync', '--import-only')
            _run(staged, 'sync', '--flush-only')
            status = json.loads(_run(staged, 'sync', '--status', '--json').stdout)
            if status.get('dirty_count') != 0:
                raise BeadsError(f'Rebuilt store {store["path"]} is not clean')
            expected_rows = [json.loads(line) for line in edits.get(original / 'issues.jsonl', (original / 'issues.jsonl').read_bytes()).decode().splitlines() if line.strip()]
            actual_rows = read_rows(staged / 'issues.jsonl')
            if _canonical(expected_rows) != _canonical(actual_rows):
                raise BeadsError(f'Re-import changed bead content in {store["path"]}; refusing publication')
            _links(actual_rows, {r['id'] for r in actual_rows})
            for row in actual_rows:
                _run(staged, 'show', row['id'], '--json')
        # Catch concurrent edits after expensive staging and before publication.
        check, _, _ = plan_reprefix(root, target)
        if check['plan_sha256'] != expected:
            raise BeadsError('Repository changed during staging; no files published; preview again')
        recovery = root / '.br_recovery'
        recovery.mkdir(exist_ok=True)
        try:
            descriptor = os.open(recovery / 'lock', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as e:
            raise BeadsError('Another migration or interrupted preparation holds .br_recovery/lock; inspect it before recovering') from e
        os.close(descriptor)
        backup = recovery / str(uuid.uuid4())
        files = {str(p.relative_to(root)): p.exists() for p in edits}
        record = {'status': 'applying', 'backup': str(backup.relative_to(root)), 'files': files,
                  'stores': [s['path'] for s in receipt['stores']],
                  'destinations': [str(p.relative_to(root)) for p in renames.values()], 'plan': receipt}
        try:
            for relative, existed in files.items():
                if existed:
                    dest = backup / 'files' / relative
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(root / relative, dest)
            for store in receipt['stores']:
                shutil.copytree(root / store['path'], backup / 'stores' / store['path'])
            latest, _, _ = plan_reprefix(root, target)
            if latest['plan_sha256'] != expected:
                raise BeadsError('Repository changed during backup; no originals changed')
            record['backup_hashes'] = {str(p.relative_to(backup)): hashlib.sha256(p.read_bytes()).hexdigest() for p in backup.rglob('*') if p.is_file()}
            _journal(backup / 'receipt.json', record)
            _journal(recovery / 'active.json', record)
            # The active journal is durable before touching originals.
            for path, data in edits.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_name(path.name + '.dekspec-reprefix-tmp')
                temp.write_bytes(data)
                if path.exists():
                    shutil.copymode(path, temp)
                os.replace(temp, path)
            for source, destination in renames.items():
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, destination)
            for index, store in enumerate(receipt['stores']):
                path = root / store['path']
                staged = stage / str(index) / '.beads'
                # Preserve all non-DB store files, old DB/audit history in backup.
                for item in path.iterdir():
                    if item.name.startswith('beads.db'):
                        item.unlink()
                for item in staged.iterdir():
                    if item.is_file() and (item.name.startswith('beads.db') or item.name == 'metadata.json'):
                        shutil.copy2(item, path / item.name)
                # Keep source JSONL representation, pin, and comments exactly.
                with tempfile.TemporaryDirectory(prefix='dekspec-beads-published-') as verify_dir:
                    verified = Path(verify_dir) / '.beads'
                    shutil.copytree(path, verified)
                    status = json.loads(_run(verified, 'sync', '--status', '--json').stdout)
                    if status.get('dirty_count') != 0:
                        raise BeadsError(f'Published store not clean: {store["path"]}')
                    for row in read_rows(verified / 'issues.jsonl'):
                        _run(verified, 'show', row['id'], '--json')
            if receipt['ids']:
                pattern = _pattern(receipt['ids'])
                for path in set(_tracked(root)) | set(renames.values()):
                    if path.exists() and (pattern.search(path.read_bytes().decode('utf-8', errors='replace')) or pattern.search(str(path.relative_to(root)))):
                        raise BeadsError(f'Old ID remains in {path.relative_to(root)}')
            record['status'] = 'complete'
            _journal(backup / 'receipt.json', record)
            (recovery / 'active.json').unlink()
        except BaseException:
            if (recovery / 'active.json').exists():
                _recover_locked(root)
            raise
        finally:
            (recovery / 'lock').unlink(missing_ok=True)
        return {**receipt, 'status': 'complete', 'backup': str(backup)}
