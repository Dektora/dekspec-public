"""Hides BR18 path selection, entry hashing, runner sections and git reads; bind(engine, ib, *, head=None) returns ScopedBinding(manifest, runner_inputs, digest), jointly binding the change, acceptance assets and runner inputs.
manifest holds BR18(a,b) entries and runner_inputs holds BR18(c); callers persist the value and use changed_paths(previous, current) for sorted repository paths, with no section suffixes or caller-side comparison.
bind reads working content unless head names a commit; base_move_touches(engine, ib, old, new) reads only ancestor-to-descendant git objects and reports sorted bound paths, including newly added ancestor conftests, even with lean switched off.
Queries write nothing; unchanged content, excluded changes and absent optional runner files yield ordinary unchanged bindings or []; hashes and selection rules never concern callers.
ExecutionError refuses unknown/non-lean briefs, unreadable commits and non-ancestor base moves; LeanNotBuilt remains the compatibility refusal type, never successful emptiness.
Alternatives: exposed select/hash/compare utilities, a stateful binding service, or the fixed portable value plus three questions; the value wins because engine and queue callers need neither policy knowledge nor a service lifecycle.
"""
from contextlib import contextmanager as _contextmanager
from dataclasses import dataclass as _dataclass
from hashlib import sha256 as _sha256
from pathlib import Path as _Path
import posixpath as _posixpath
from tempfile import TemporaryDirectory as _TemporaryDirectory

from dekspec.execution import git_reads
from dekspec.diff_confinement import matches_any_glob as _matches
from dekspec.execution import acceptance as _acceptance
from dekspec.execution import fingerprint as _fingerprint
from dekspec.execution.contract import ContractError as _ContractError, load_contract as _load_contract
from dekspec.execution.engine import ExecutionError as _ExecutionError
from dekspec.execution.record import is_record_file as _is_record_file
from dekspec.execution.scope import ScopeError as _ScopeError, changed_files as _changed_files
from dekspec.execution.settings import load_settings as _load_settings

__all__ = ["LeanNotBuilt", "ScopedBinding", "bind", "changed_paths", "base_move_touches"]


class LeanNotBuilt(_ExecutionError):
    """An unavailable lean query, naming its call, never successful emptiness."""


@_dataclass(frozen=True)
class ScopedBinding:
    """Persistable binding; callers hand it back instead of comparing internals."""
    manifest: dict[str, str]
    runner_inputs: dict[str, str]
    digest: str


_MISSING = _sha256(b"missing\0").hexdigest()


def _git(root, *args):
    """Read git output, refusing failures rather than mistaking them for absence."""
    proc = git_reads.run(root, *args, capture_output=True)
    if proc.returncode == 1 and args[:2] == ("merge-base", "--is-ancestor"):
        raise _ExecutionError(f"base commit {args[2]} is not an ancestor of {args[3]}")
    if proc.returncode:
        raise _ExecutionError(f"git {' '.join(args)}: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def _commit(root, ref):
    """Resolve a commit before any optional-file lookups can report absence."""
    return _git(root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").decode().strip()


def _merge_base(engine, head):
    """Find the change's origin for the requested content, not always HEAD."""
    candidates = [engine.base] if engine.base else ["main", "origin/main", "master", "origin/master"]
    for ref in candidates:
        proc = git_reads.run(engine.repo_root, "merge-base", head, ref, capture_output=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.decode().strip()
    raise _ExecutionError(f"cannot find a merge base with {' / '.join(candidates)}")


def _tree(engine, head):
    """Every entry of ``head``'s tree: path -> (mode, kind, object id)."""
    rows = _git(engine.repo_root, "ls-tree", "-r", "-t", "-z", head).decode("utf-8", "surrogateescape")
    entries = {}
    for row in rows.split("\0"):
        if row:
            metadata, rel = row.split("\t", 1)
            entries[rel] = metadata.split()
    return entries


def _object_reader(engine, head):
    """read(path) over ``head``'s git objects: a file's bytes, None when it is
    absent or a directory. In-tree symlinks resolve from objects, never through
    the host filesystem; one that leaves the tree or never resolves refuses."""
    entries = _tree(engine, head)

    def read(rel):
        if rel not in entries:
            return None
        source, visited = rel, set()
        while True:
            if source in visited or source not in entries:
                raise _ExecutionError(f"cannot read {rel} at {head}: unresolved git symlink")
            visited.add(source)
            mode, kind, oid = entries[source]
            if kind != "blob":
                return None  # a directory is not an optional runner file
            content = _git(engine.repo_root, "cat-file", "blob", oid)
            if mode != "120000":
                return content
            link = content.decode("utf-8", "surrogateescape")
            source = _posixpath.normpath(_posixpath.join(_posixpath.dirname(source), link))
            if _posixpath.isabs(source) or source == ".." or source.startswith("../"):
                raise _ExecutionError(f"cannot read {rel} at {head}: symlink leaves the git tree")

    return read


@_contextmanager
def _snapshot(engine, head):
    """Sparse git-only parser view of the specification and configuration
    files, disposed outside the repository."""
    read = _object_reader(engine, head)
    with _TemporaryDirectory(prefix="dekspec-scoped-") as temporary:
        root = _Path(temporary)
        wanted = {p for p in _tree(engine, head) if p.startswith(engine.spec_root + "/") and p.endswith(".md")}
        wanted.add(".dekspec/config.yaml")
        for rel in sorted(wanted):
            content = read(rel)
            if content is not None:
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        try:
            yield root
        except _ContractError as exc:
            detail = str(exc).replace(str(root), str(engine.repo_root))
            raise _ExecutionError(f"{detail} (at commit {head})") from exc


def _runner_inputs(engine, contract, head):
    """BR18(c): each named runner's bound support files, asked of its adapter,
    and DekSpec's own execution block, in working content or at ``head``."""
    from dekspec.execution.test_runners import adapter_for

    if head is None:
        def read(rel):
            path = engine.repo_root / rel
            return path.read_bytes() if path.is_file() else None
    else:
        read = _object_reader(engine, head)
    inputs = {}
    for runner in dict.fromkeys(c.kind for c in contract.acceptance if c.nodes):
        adapter = adapter_for(runner)
        if adapter is None:
            raise _ExecutionError(f"{contract.ib_id}: DekSpec has no adapter for the test runner {runner}")
        tests = [t for c in contract.acceptance if c.kind == runner for t in c.nodes]
        files = sorted({f for f in map(adapter.file_of, tests) if f is not None})
        inputs.update(adapter.support(files, read).bound)
    config = read(".dekspec/config.yaml")
    block = _acceptance._execution_block(config) if config is not None else None
    if block is not None:
        inputs[".dekspec/config.yaml#execution"] = _sha256(block.encode("utf-8")).hexdigest()
    return dict(sorted(inputs.items()))


def _require_lean(contract):
    """Keep the read-only queries available with the switch off, only for lean briefs."""
    if not contract.is_lean:
        raise _ExecutionError(f"{contract.ib_id} is not lean")


def _change_paths(engine, base, head, excludes):
    """BR18(a): the brief's own diff, including both sides of a rename."""
    return {path for change in _changed_files(engine.repo_root, base, end=head)
            for path in (change.path, change.old_path) if path
            and not (_is_record_file(path) or _fingerprint.is_tracker_record(path)
                     or _matches(path, excludes) or path.startswith(engine.spec_root + "/"))}


def _asset_paths(engine, contract, head):
    """BR18(b): expand directory assets in the same content being bound.

    A base move keeps the brief's own diff fixed, but directory membership
    belongs to each base commit. No HEAD or working-tree listing supplies it.
    """
    files, directories = set(), {"."}
    if head is not None:
        rows = _git(engine.repo_root, "ls-tree", "-r", "-t", "-z", head).decode("utf-8", "surrogateescape")
        for row in rows.split("\0"):
            if row:
                metadata, rel = row.split("\t", 1)
                kind = metadata.split()[1]
                if kind == "tree":
                    directories.add(rel)
                elif kind == "blob" and "__pycache__" not in rel.split("/"):
                    files.add(rel)
    paths = set()
    for asset in contract.acceptance_asset_paths():
        rel = _posixpath.normpath(asset)
        if head is None:
            path = engine.repo_root / rel
            if path.is_dir():
                paths.update(str(p.relative_to(engine.repo_root)) for p in path.rglob("*")
                             if p.is_file() and "__pycache__" not in p.parts)
            else:
                paths.add(rel)
        elif rel in directories:
            paths.update(p for p in files if rel == "." or p.startswith(rel + "/"))
        else:
            paths.add(rel)
    return paths


def _binding(engine, paths, runners, head):
    """Keep absence and runner-only changes in the single evidence digest."""
    entries = _fingerprint.named_entries(engine.repo_root, paths, spec_root=engine.spec_root, head=head)
    manifest = {path: entries.get(path, _MISSING) for path in sorted(paths)}
    # Separate namespaces: a conftest can occur in both groups with different
    # hash rules, and neither entry may overwrite the other in the digest.
    combined = {"manifest:" + p: h for p, h in manifest.items()}
    combined.update({"runner:" + p: h for p, h in runners.items()})
    return ScopedBinding(manifest, runners, _fingerprint.fingerprint_of(combined))


def bind(engine, ib: str, *, head: str | None = None) -> ScopedBinding:
    """Current working content, or committed content when head is given."""
    try:
        if head is None:
            contract = engine.contract(ib)
            _require_lean(contract)
            base = _merge_base(engine, "HEAD")
            paths = _change_paths(engine, base, None, engine.settings.fingerprint_exclude)
        else:
            head = _commit(engine.repo_root, head)
            with _snapshot(engine, head) as root:
                contract = _load_contract(root, ib, spec_root=engine.spec_root)
                _require_lean(contract)
                settings = _load_settings(root, spec_root=engine.spec_root)
                paths = _change_paths(engine, _merge_base(engine, head), head, settings.fingerprint_exclude)
        paths |= _asset_paths(engine, contract, head)
        return _binding(engine, paths, _runner_inputs(engine, contract, head), head)
    except (_ContractError, _ScopeError, _fingerprint.FingerprintError, OSError) as exc:
        raise _ExecutionError(str(exc)) from exc


def changed_paths(previous: ScopedBinding, current: ScopedBinding) -> list[str]:
    """Sorted changed repository paths; unavailable computation refuses."""
    manifest = _fingerprint.manifest_changes(previous.manifest, current.manifest)
    runners = _fingerprint.manifest_changes(previous.runner_inputs, current.runner_inputs)
    # A runner input is a path, or a path, "#" and the part of the file that counts.
    return sorted(set(manifest) | {p.rsplit("#", 1)[0] if "#" in p.rsplit("/", 1)[-1] else p
                                   for p in runners})


def base_move_touches(engine, ib: str, old: str, new: str) -> list[str]:
    """Sorted bound paths moved by an ancestor-to-descendant base change."""
    try:
        old, new = _commit(engine.repo_root, old), _commit(engine.repo_root, new)
        _git(engine.repo_root, "merge-base", "--is-ancestor", old, new)
        head = _commit(engine.repo_root, "HEAD")
        with _snapshot(engine, head) as root:
            contract = _load_contract(root, ib, spec_root=engine.spec_root)
            _require_lean(contract)
            settings = _load_settings(root, spec_root=engine.spec_root)
            paths = _change_paths(engine, _merge_base(engine, head), head, settings.fingerprint_exclude)
        bindings = []
        for revision in (old, new):
            bound_paths = paths | _asset_paths(engine, contract, revision)
            bindings.append(_binding(engine, bound_paths, _runner_inputs(engine, contract, revision), revision))
        return changed_paths(*bindings)
    except (_ContractError, _ScopeError, _fingerprint.FingerprintError, OSError) as exc:
        raise _ExecutionError(str(exc)) from exc
