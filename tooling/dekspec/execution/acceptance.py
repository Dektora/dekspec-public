"""Acceptance baseline, asset protection and evidence production (ADR-057).

* The **baseline** pins the contract hash, every acceptance asset and every
  runner input at authorization. Absent assets are recorded as absent — a
  file first created during execution is a reviewed event, not a free pass.
* **Evidence** re-hashes all of that, runs each condition, and records the
  per-node truth: a condition backed by test nodes is satisfied only when at
  least one matching node ran and every matching node passed. Skipped,
  expected-failure, deselected, uncollected or erroring nodes never count.
"""

from __future__ import annotations

import configparser
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, NamedTuple

from dekspec.execution import pytest_evidence
from dekspec.execution.contract import AcceptanceCondition, IBContract

__all__ = [
    "asset_hashes",
    "baseline_digest",
    "baseline_payload",
    "bytecode_cache_root",
    "run_condition",
    "run_pytest_detail",
    "runner_input_hashes",
]

_TAIL_CHARS = 3000
_PLUGIN_MODULE = "dekspec_pytest_evidence"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str | None:
    return _sha_bytes(path.read_bytes()) if path.is_file() else None


def asset_hashes(repo_root: Path, contract: IBContract) -> dict[str, str | None]:
    """Hash of each acceptance asset; a directory node protects every file under it."""
    root = Path(repo_root)
    out: dict[str, str | None] = {}
    for rel in contract.acceptance_asset_paths():
        path = root / rel
        if path.is_dir():
            for child in sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
                out[str(child.relative_to(root))] = _hash_file(child)
        else:
            out[rel] = _hash_file(path)
    return out


def _ini_section(path: Path, section: str) -> str | None:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(path.read_text(encoding="utf-8"))
    except (configparser.Error, UnicodeDecodeError):
        return path.read_text(encoding="utf-8", errors="replace")
    if not parser.has_section(section):
        return None
    return json.dumps(dict(parser.items(section)), sort_keys=True)


def _pyproject_pytest(path: Path) -> str | None:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
        return path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return path.read_text(encoding="utf-8", errors="replace")
    section = data.get("tool", {}).get("pytest")
    return json.dumps(section, sort_keys=True) if section is not None else None


_CONFIG_CANDIDATES = ("pytest.ini", ".pytest.ini", "pytest.toml", "pyproject.toml", "tox.ini", "setup.cfg")


def _config_text(path: Path) -> str | None:
    """The pytest-relevant part of a config file (None: not a pytest config)."""
    name = path.name
    if name in ("pytest.ini", ".pytest.ini", "pytest.toml"):
        return path.read_text(encoding="utf-8", errors="replace")
    if name == "pyproject.toml":
        return _pyproject_pytest(path)
    if name == "tox.ini":
        return _ini_section(path, "pytest")
    if name == "setup.cfg":
        return _ini_section(path, "tool:pytest")
    return None


def _ancestor_dirs(root: Path, rel: str) -> list[Path]:
    """Directories from the repo root down to ``rel`` (a file or directory)."""
    target = root / rel
    folder = target if target.is_dir() or not target.suffix else target.parent
    out = []
    while True:
        out.append(folder)
        if folder == root or root not in folder.parents:
            break
        folder = folder.parent
    return list(reversed(out))


def root_pytest_config(root: Path) -> Path | None:
    """The configuration pytest would pick at the repository root."""
    for name in _CONFIG_CANDIDATES:
        path = root / name
        if path.is_file() and _config_text(path) is not None:
            return path
    return None


def _execution_settings_text(root: Path) -> str | None:
    cfg = root / ".dekspec" / "config.yaml"
    if not cfg.is_file():
        return None
    import yaml

    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return cfg.read_text(encoding="utf-8", errors="replace")
    block = data.get("execution") if isinstance(data, dict) else None
    return json.dumps(block, sort_keys=True) if block is not None else None


def runner_input_hashes(repo_root: Path, contract: IBContract) -> dict[str, str]:
    """Hash every input that can change what a passing test means.

    Test-runner configuration in every directory from the repository root to
    each acceptance node (only the pytest sections of shared files, so an
    unrelated dependency bump is not flagged), each ``conftest.py`` on those
    paths, and the repository's DekSpec execution settings (which choose the
    interpreter, limits and fingerprint exclusions).
    """
    root = Path(repo_root)
    out: dict[str, str] = {}
    targets = {n.split("::", 1)[0] for c in contract.acceptance for n in c.nodes} or {"."}
    for rel in sorted(targets):
        for folder in _ancestor_dirs(root, rel):
            for name in (*_CONFIG_CANDIDATES, "conftest.py"):
                path = folder / name
                if not path.is_file():
                    continue
                key = str(path.relative_to(root))
                if name == "conftest.py":
                    out[key] = _sha_bytes(path.read_bytes())
                    continue
                text = _config_text(path)
                if text is not None:
                    out[f"{key}#pytest"] = _sha_bytes(text.encode("utf-8"))
    settings = _execution_settings_text(root)
    if settings is not None:
        out[".dekspec/config.yaml#execution"] = _sha_bytes(settings.encode("utf-8"))
    return dict(sorted(out.items()))


def baseline_payload(repo_root: Path, contract: IBContract) -> dict[str, Any]:
    from dekspec.execution.fingerprint import current_commit

    return {
        "commit": current_commit(repo_root),
        "contract_hash": contract.contract_hash(),
        "assets": asset_hashes(repo_root, contract),
        "runner_inputs": runner_input_hashes(repo_root, contract),
    }


def baseline_digest(baseline: dict[str, Any] | None) -> str | None:
    if not baseline:
        return None
    core = {k: baseline.get(k) for k in ("contract_hash", "assets", "runner_inputs")}
    return _sha_bytes(json.dumps(core, sort_keys=True).encode("utf-8"))


def _node_matches(requested: str, actual: str) -> bool:
    requested = requested.rstrip("/")
    if actual == requested:
        return True
    if "::" not in requested:
        # A file (`tests/x.py`) or a directory (`tests/acceptance`).
        return actual.startswith(requested + "::") or actual.startswith(requested + "/")
    return actual.startswith(requested + "[") or actual.startswith(requested + "::")


def _node_outcome(phases: dict[str, str]) -> str:
    values = set(phases.values())
    if "xfail" in values or "xpass" in values:
        return "xfail"
    if "failed" in values:
        return "failed"
    if "skipped" in values:
        return "skipped"
    if phases.get("call") == "passed":
        return "passed"
    return "not-run"


_ENV_DROP_PREFIXES = ("PYTEST_", "PYTHON")
_ENV_KEEP = {"PYTHONIOENCODING", "PYTHONUTF8"}
#: The identity of the worker running the check (ADR-059, ADR-061): evidence must
#: not depend on who runs it, so a check never sees who, in which role, or
#: against which base the command was issued.
_ENV_DROP_EXACT = frozenset({"DEKSPEC_ACTOR", "DEKSPEC_ROLE", "DEKSPEC_BASE"})


def clean_env(**extra: str) -> dict[str, str]:
    """The environment for acceptance runs: nothing from the caller's
    environment may change what runs (`PYTEST_ADDOPTS`, `PYTEST_PLUGINS`,
    `PYTHONPATH`, `PYTHONSTARTUP` … are dropped), and nothing in it may say who
    runs it (the worker identity `DEKSPEC_ACTOR` / `DEKSPEC_ROLE` / `DEKSPEC_BASE`)."""
    env = {k: v for k, v in os.environ.items()
           if (not k.startswith(_ENV_DROP_PREFIXES) or k in _ENV_KEEP) and k not in _ENV_DROP_EXACT}
    env.update(extra)
    return env


def _full_message_options(config: Path) -> list[str]:
    """Options for the floor's detail run only (IB-143 O-2/O-3): record failure
    messages in full. At `-q`, pytest cuts every repr in an assertion message to
    240 characters, which can drop a subprocess's usage or import signature;
    reprs and explanations are unabridged only at assertion verbosity 2.

    ``--verbosity=2`` sets the level outright, over `-q` and any `addopts`, on
    every pytest. An explicit ``verbosity_assertions`` in the repository's own
    pytest configuration (pytest 8+) takes precedence over it, so that key is
    overridden too — only when the configuration names it, because an older
    pytest warns about the unknown key and fails under `--strict-config` or
    `filterwarnings = error`."""
    options = ["--verbosity=2"]
    text = _config_text(config) if config.is_file() else None
    if text and "verbosity_assertions" in text:
        options += ["-o", "verbosity_assertions=2"]
    return options


#: Where acceptance runs keep bytecode for modules outside the implementation
#: fingerprint, below the user's cache directory (IB-145 O-3).
_BYTECODE_CACHE_PARTS = ("dekspec", "bytecode")

_PROBE = """\
import importlib.machinery, importlib.util, json, sys
try:
    import _pytest
    pytest_version = str(_pytest.__version__)
except Exception:
    pytest_version = None
print(json.dumps({"tag": sys.implementation.cache_tag, "magic": importlib.util.MAGIC_NUMBER.hex(),
                  "pytest": pytest_version, "path": sys.path,
                  "suffixes": list(importlib.machinery.SOURCE_SUFFIXES)}))
"""

#: Run by the test interpreter itself (only it can read its own bytecode): of
#: the NUL-separated paths on stdin, print each file whose header claims the
#: interpreter's magic number but whose body is not a loadable code object.
#: CPython loads such a file instead of recompiling, and the import then fails.
_FIND_UNLOADABLE = r"""
import marshal, sys, types
magic = bytes.fromhex(sys.argv[1])
for path in sys.stdin.buffer.read().split(b"\0"):
    if not path:
        continue
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError:
        continue
    if len(data) < 16 or data[:4] != magic:
        continue
    try:
        loadable = isinstance(marshal.loads(data[16:]), types.CodeType)
    except Exception:
        loadable = False
    if not loadable:
        sys.stdout.buffer.write(path + b"\0")
"""


class _Probe(NamedTuple):
    tag: str
    magic: str
    pytest_version: str | None
    path: tuple[str, ...]
    suffixes: tuple[str, ...]


_probes: dict[tuple, _Probe] = {}


def bytecode_cache_root() -> Path | None:
    """The bytecode cache: ``$XDG_CACHE_HOME/dekspec/bytecode/``, or
    ``~/.cache/dekspec/bytecode/`` when ``XDG_CACHE_HOME`` is unset (or not an
    absolute path, per the XDG base-directory rules). Resolved from the
    environment at each call; ``None`` when neither gives an absolute path."""
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    if os.path.isabs(xdg):
        base = xdg
    else:
        home = os.path.expanduser("~")
        if not os.path.isabs(home):
            return None
        base = os.path.join(home, ".cache")
    return Path(base, *_BYTECODE_CACHE_PARTS)


def _within(path: str, folder: str) -> bool:
    """``path`` is ``folder`` or lies below it (plain string paths)."""
    if folder == os.sep:
        return path.startswith(os.sep)
    return path == folder or path.startswith(folder + os.sep)


def _join(base: str, rel: str) -> str:
    return os.path.join(base, rel) if base and rel else base or rel


def _stem(name: str, suffixes: tuple[str, ...]) -> str:
    for suffix in suffixes:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _pyc_stem(name: str) -> str | None:
    """The module a bytecode file's name is for: ``<stem>.<tag>.pyc``,
    ``<stem>.<tag>.opt-<n>.pyc`` or pytest's ``<stem>.<tag>-pytest-<version>.pyc``."""
    base = name[:-4]
    cut = base.find("-pytest-")
    if cut >= 0:
        base = base[:cut]
    else:
        head, dot, last = base.rpartition(".")
        if dot and last.startswith("opt-"):
            base = head
    stem, dot, _tag = base.rpartition(".")
    return stem if dot and stem else None


def _probe_interpreter(python: str) -> _Probe | None:
    """The interpreter's cache tag, bytecode magic number, pytest version,
    ``sys.path`` and source suffixes, as an acceptance run sees them (the same
    clean environment, no repository on the path), writing no bytecode.
    Remembered per interpreter binary, ``HOME`` and ``PATH`` for the life of
    the process; failures are not remembered.

    A stale answer is safe: it can only miss a path entry (whose modules are
    then compiled from source), never admit a repository path, because
    admission and the scan for links are decided at every run."""
    binary = shutil.which(python, path=os.environ.get("PATH")) or python
    try:
        st = os.stat(binary)
        stamp: tuple = (st.st_dev, st.st_ino, st.st_mtime_ns)
    except OSError:
        stamp = ()
    key = (python, stamp, os.environ.get("HOME"), os.environ.get("PATH"))
    if key in _probes:
        return _probes[key]
    try:
        with tempfile.TemporaryDirectory(prefix="dekspec-probe-") as cwd:
            proc = subprocess.run([python, "-c", _PROBE], cwd=cwd, capture_output=True, text=True,
                                  timeout=60, env=clean_env(PYTHONDONTWRITEBYTECODE="1"))
        # The last line: a site hook may print before the probe does.
        data = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 else None
        answer = _Probe(str(data["tag"]), str(data["magic"]),
                        str(data["pytest"]) if data.get("pytest") else None,
                        tuple(str(p) for p in data["path"]),
                        tuple(str(s) for s in data.get("suffixes") or [".py"]))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return None
    _probes[key] = answer
    return answer


def _identities(real: str, rels: Iterable[str]) -> tuple[frozenset[tuple[int, int]], frozenset[tuple[int, int]]]:
    """Each path's identity (``st_dev``, ``st_ino``), and its modification time
    and size as a timestamp ``.pyc`` header records them (seconds and bytes,
    modulo 2**32)."""
    ids, headers = set(), set()
    for rel in rels:
        try:
            st = os.stat(os.path.join(real, rel) if rel else real)
        except OSError:
            continue
        ids.add((st.st_dev, st.st_ino))
        headers.add((int(st.st_mtime) & 0xFFFFFFFF, st.st_size & 0xFFFFFFFF))
    return frozenset(ids), frozenset(headers)


class _Repository(NamedTuple):
    """The repository's reviewed files as one run sees them: what git lists as
    tracked or untracked-but-not-ignored (a superset of the implementation
    fingerprint), every directory holding one, and the identity
    (``st_dev``, ``st_ino``) of each, so that a hard link or a mount reaching
    one from elsewhere is recognised as well as a symbolic link."""

    real: str
    listed: frozenset[str]
    dirs: frozenset[str]
    file_ids: frozenset[tuple[int, int]]
    dir_ids: frozenset[tuple[int, int]]
    headers: frozenset[tuple[int, int]]  # each reviewed file's (mtime, size) as a .pyc header records them

    @classmethod
    def read(cls, root: Path) -> _Repository | None:
        try:
            proc = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                  cwd=str(root), capture_output=True)
        except OSError:
            return None
        if proc.returncode != 0:
            return None
        real = os.path.realpath(root)
        listed = frozenset(os.fsdecode(p) for p in proc.stdout.split(b"\0") if p)
        dirs = {""}
        for rel in listed:
            head = os.path.dirname(rel)
            while head and head not in dirs:
                dirs.add(head)
                head = os.path.dirname(head)
        file_ids, headers = _identities(real, listed)
        return cls(real, listed, frozenset(dirs), file_ids, _identities(real, dirs)[0], headers)

    def reaches(self, real_path: str, ident: tuple[int, int], *, directory: bool) -> bool:
        """Whether a resolved path (with identity ``ident``) is a reviewed file
        or, for a directory, reaches one: it is the repository, an ancestor of
        it, a directory holding a reviewed file, or one of those mounted
        elsewhere."""
        if directory:
            if ident in self.dir_ids or (self.listed and _within(self.real, real_path)):
                return True
            return _within(real_path, self.real) and os.path.relpath(real_path, self.real) in self.dirs
        return ident in self.file_ids or (
            _within(real_path, self.real) and os.path.relpath(real_path, self.real) in self.listed)


class _Inventory(NamedTuple):
    """A directory tree as one scan saw it, never following a link."""

    stamps: tuple[tuple[str, tuple[int, ...]], ...]  # every directory → (dev, ino, mode, mtime, ctime)
    files: dict[tuple[int, int], tuple[str, ...]]  # each source file's identity → its relative paths
    dirs: dict[tuple[int, int], tuple[str, ...]]  # each directory's identity → its relative paths
    links: tuple[str, ...]  # every symbolic link, relative
    mounts: bytes | None
    settled: bool


#: Scans of the interpreters' path entries, reused while no directory in them
#: (and no mount) has changed: a change to a directory's entries — a link, a
#: file or a directory added, removed or replaced — changes its mtime and ctime.
_inventories: dict[str, _Inventory] = {}
#: A directory changed this recently may change again within the same
#: timestamp; its tree is scanned afresh each time until it settles.
_SETTLE_NS = 2_000_000_000
#: An entry with more files and directories than this is not scanned, and not cached.
_INVENTORY_LIMIT = 500_000
#: Directories reached through links while scanning one entry.
_VISIT_LIMIT = 10_000
#: Cached files found loadable in this process: (path, magic) → (dev, ino, size, mtime).
_loadable: dict[tuple[str, str], tuple[int, int, int, int]] = {}

_FILE, _DIR = "file", "dir"


def _mounts() -> bytes | None:
    try:
        with open("/proc/self/mountinfo", "rb") as handle:
            return hashlib.sha256(handle.read()).digest()
    except OSError:
        return None


def _dir_stamp(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_mode, st.st_mtime_ns, st.st_ctime_ns)


def _unchanged(path: str, stamp: tuple[int, ...]) -> bool:
    try:
        return _dir_stamp(os.stat(path, follow_symlinks=False)) == stamp
    except OSError:
        return False


def _inventory(top: str, suffixes: tuple[str, ...], skip: str, mounts: bytes | None) -> _Inventory | None:
    """The tree under ``top`` (a resolved directory): every directory, every
    file with a source suffix, every symbolic link — scanned, or reused from an
    earlier scan in this process when nothing in it has changed since. None
    when ``top`` cannot be read or is too large to scan."""
    known = _inventories.get(top)
    if (known is not None and known.settled and known.mounts == mounts
            and all(_unchanged(path, stamp) for path, stamp in known.stamps)):
        return known
    started = time.time_ns()
    stamps: list[tuple[str, tuple[int, ...]]] = []
    files: dict[tuple[int, int], list[str]] = {}
    dirs: dict[tuple[int, int], list[str]] = {}
    links: list[str] = []
    stack, count = [""], 0
    while stack:
        rel = stack.pop()
        path = os.path.join(top, rel) if rel else top
        try:
            st = os.stat(path, follow_symlinks=False)
        except OSError:
            if not rel:
                return None
            continue
        stamps.append((path, _dir_stamp(st)))
        dirs.setdefault((st.st_dev, st.st_ino), []).append(rel)
        try:
            with os.scandir(path) as it:
                children = list(it)
        except OSError:
            continue  # nothing can be imported from a directory that cannot be listed
        count += len(children)
        if count > _INVENTORY_LIMIT:
            return None
        for child in children:
            name = os.path.join(rel, child.name) if rel else child.name
            try:
                if child.is_symlink():
                    links.append(name)
                elif child.is_dir(follow_symlinks=False):
                    if child.path != skip:
                        stack.append(name)
                elif child.name.endswith(suffixes):
                    cst = child.stat(follow_symlinks=False)
                    files.setdefault((cst.st_dev, cst.st_ino), []).append(name)
            except OSError:
                continue
    settled = all(max(stamp[3], stamp[4]) < started - _SETTLE_NS for _path, stamp in stamps)
    inventory = _Inventory(tuple(stamps), {k: tuple(v) for k, v in files.items()},
                           {k: tuple(v) for k, v in dirs.items()}, tuple(links), mounts, settled)
    _inventories[top] = inventory
    return inventory


def _tree(found: frozenset[tuple[str, str]]) -> dict | str:
    """Hazard paths (relative, each a file or a directory) as a tree of names;
    ``_DIR`` when the entry itself is one."""
    tree: dict = {}
    for rel, kind in sorted(found, key=lambda item: (item[0].count(os.sep), item[0], item[1])):
        if not rel:
            return _DIR
        parts = rel.split(os.sep)
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                break  # below a blocked directory already
        else:
            if kind == _DIR or parts[-1] not in node:
                node[parts[-1]] = kind
    return tree


class _BytecodeCache:
    """The out-of-repository bytecode cache as one acceptance run uses it (IB-145).

    Each run still gets a fresh, empty ``PYTHONPYCACHEPREFIX``; CPython, and
    pytest's assertion rewriter, look bytecode up — and write it — at
    ``<prefix>/<source path>``, the path the module was imported by, never in a
    ``__pycache__``. Into that tree the run puts:

    * **blocks** over the repository's image: a plain file where a directory
      would have to be created, a directory where a bytecode file would go.
      Nothing can be written there, not even by root;
    * **links** from the image of each of the test interpreter's own
      ``sys.path`` entries that holds none of the repository's working
      content (the standard library, site-packages, a virtual environment the
      repository ignores) to that entry's mirror in the cache, so their
      modules are compiled once and read back by later runs, each file
      validated by CPython against its source;
    * **blocks inside those entries** at every path that reaches a reviewed
      file other than its own — a symbolic link to it (or to a directory
      holding one, or to the repository or an ancestor), a hard link or a
      mount sharing its identity — found by scanning the entries before the
      run. Such an entry is laid out as real directories
      down to each blocked path, with every other subdirectory linked.

    Before the run, the mirrors about to be linked are swept (``_sweep``):
    bytecode whose source is gone — nothing waits at a path a test could
    later link to a reviewed file — and files the interpreter could not load
    are removed. After the run the entries are scanned again: if anything in
    them changed while it ran, the run does not count (``unchanged``) and the
    condition is run again from source without the cache. So a run that
    counts reads no bytecode for a reviewed file — from the cache, a
    ``__pycache__`` or pytest's rewrite cache, planted or not — by any path.

    The cache itself is never followed out of: the mirrors are reached from
    its resolved root through real directories only, and a link found inside
    a mirror about to be used is removed.
    """

    def __init__(self, forms: tuple[str, ...], python: str, cache_root: Path, probe: _Probe,
                 repo: _Repository, entries: list[str], inside: list[str]):
        self.forms, self.python, self.cache_root, self.probe = forms, python, cache_root, probe
        self.repo, self.entries, self.inside = repo, entries, inside
        self.hazards: dict[str, frozenset[tuple[str, str]]] = {}
        self.observation: tuple = ()
        self.targets: list[Path] = []
        self.prefix: Path | None = None
        self.used = False
        self.stray = False  # the run compiled a reviewed file by a path a test made (_compiled_reviewed)

    @classmethod
    def open(cls, repo_root: Path, root: Path, python: str) -> _BytecodeCache | None:
        """The cache for a run of ``python`` in ``root``; ``None`` when it cannot
        be used (no location, the location inside the repository, the
        interpreter probe failed, git cannot list the repository, nothing to
        cache) — the run then compiles everything from source and writes
        nothing, as before the cache."""
        location = bytecode_cache_root()
        if location is None:
            return None
        cache_root = Path(os.path.realpath(location))
        forms = tuple(dict.fromkeys([os.path.abspath(repo_root), str(root)]))
        if any(_within(p, f) for p in {str(location), str(cache_root)} for f in forms):
            return None
        # A relative interpreter path names a file under the repository (runs start there).
        exe = python if os.path.isabs(python) or os.sep not in python else str(root / python)
        probe = _probe_interpreter(exe)
        if probe is None:
            return None
        repo = _Repository.read(root)
        if repo is None:
            return None
        entries, inside = cls._admit(forms, probe.path, repo, str(cache_root))
        cache = cls(forms, exe, cache_root, probe, repo, entries, inside)
        mounts = _mounts()
        scans = {entry: cache._scan(entry, mounts) for entry in entries}
        # An entry that cannot be scanned, or is itself a way to reviewed files, is not linked.
        cache.hazards = {e: found for e, (found, _seen) in scans.items() if found is not None}
        cache.entries = [e for e in entries if e in cache.hazards and _tree(cache.hazards[e]) != _DIR]
        cache.inside = [e for e in inside if e in cache.entries]
        cache.observation = (mounts, tuple((e, scans[e]) for e in cache.entries))
        return cache if cache.entries else None

    @staticmethod
    def _admit(forms: tuple[str, ...], path: tuple[str, ...], repo: _Repository,
               cache_root: str) -> tuple[list[str], list[str]]:
        """The ``sys.path`` directories whose bytecode may be cached, and those
        of them inside the repository. An entry is admitted when it is an
        absolute, normalised directory that is neither the repository nor an
        ancestor of it, neither holds nor lies in the cache (by its own path
        and its resolved one) and, when inside the repository, when git lists
        no tracked or untracked-but-not-ignored file under its top-level
        directory there (a superset of the fingerprint). An entry containing a
        refused one is refused too; an entry inside an admitted one needs no
        link of its own. What lies inside an admitted entry is scanned per run
        (``_scan``)."""
        candidates: list[str] = []
        refused: list[str] = []
        inside: dict[str, set[str]] = {}
        for entry in path:
            normal = os.path.normpath(entry) if entry else ""
            if (not os.path.isabs(normal) or normal != (entry.rstrip(os.sep) or os.sep) or normal in candidates
                    or normal in refused or not os.path.isdir(normal)):
                continue
            seen = list(dict.fromkeys([normal, os.path.realpath(normal)]))
            if (any(_within(f, s) for s in seen for f in forms)
                    or any(_within(cache_root, s) or _within(s, cache_root) for s in seen)):
                refused.append(normal)
                continue
            tops = {os.path.relpath(s, f).split(os.sep)[0] for s in seen for f in forms if _within(s, f)}
            if tops:
                inside[normal] = tops
            candidates.append(normal)
        for entry, group in inside.items():
            if any(t in repo.dirs or t in repo.listed for t in group):
                candidates.remove(entry)
                refused.append(entry)
        admitted = [e for e in candidates if not any(_within(r, e) for r in refused)]
        linked: list[str] = []
        for entry in sorted(admitted):
            if not any(_within(entry, kept) for kept in linked):
                linked.append(entry)
        return linked, [e for e in linked if e in inside]

    def _scan(self, entry: str, mounts: bytes | None) -> tuple[frozenset[tuple[str, str]] | None, tuple]:
        """Every path in ``entry`` through which a reviewed file can be imported
        other than by its own path, relative to the entry, each a file or a
        directory: a symbolic link resolving to a reviewed file, or to a
        directory reaching one (the repository, an ancestor, a directory
        holding one); a hard link or a mount sharing a reviewed file's or
        directory's identity; a link back to a directory it lies in, or into
        the cache or above it. Links to other directories are followed. None when the entry cannot be fully
        scanned. Also returns what the scan saw — every directory's stamp and
        every link's resolution, dangling ones included — so a later scan can
        tell whether anything changed."""
        found: set[tuple[str, str]] = set()
        seen: list[tuple] = []
        suffixes, skip = self.probe.suffixes, str(self.cache_root)
        start = os.path.realpath(entry)
        work: list[tuple[str, str, frozenset[str]]] = [(start, "", frozenset([start]))]
        visits = 0
        while work:
            top, base, above = work.pop()
            visits += 1
            inventory = _inventory(top, suffixes, skip, mounts) if visits <= _VISIT_LIMIT else None
            if inventory is None:
                return None, tuple(seen)
            seen.append((top, inventory.stamps))
            for ident, rels in inventory.files.items():
                if ident in self.repo.file_ids:
                    found.update((_join(base, r), _FILE) for r in rels)
            for ident, rels in inventory.dirs.items():
                if ident in self.repo.dir_ids:
                    found.update((_join(base, r), _DIR) for r in rels)
            for rel in inventory.links:
                path, name = os.path.join(top, rel), _join(base, rel)
                real = os.path.realpath(path)
                try:
                    st = os.stat(path)
                except OSError:
                    # Dangling: nothing is imported through it, and bytecode
                    # kept at it has no source (swept); if it starts to resolve
                    # during the run, the scan after the run sees that.
                    seen.append((path, real, None))
                    continue
                ident = (st.st_dev, st.st_ino)
                seen.append((path, real, ident, st.st_mode))
                if stat.S_ISDIR(st.st_mode):
                    # Blocked, not followed: a way back to where the scan came
                    # from, to the cache, or to reviewed files.
                    if (real in above or _within(real, skip) or _within(skip, real)
                            or self.repo.reaches(real, ident, directory=True)):
                        found.add((name, _DIR))
                    else:
                        work.append((real, name, above | {real}))
                elif rel.endswith(suffixes) and self.repo.reaches(real, ident, directory=False):
                    found.add((name, _FILE))
        return frozenset(found), tuple(seen)

    def unchanged(self) -> bool:
        """Whether the run can count: the interpreter's linked path entries are
        still as the scan before the run saw them, and the run compiled no
        reviewed file by a path a test made (``_compiled_reviewed``). When
        something changed while the run used them — a link made or removed, a
        directory's entries rewritten, a mount — the run may have imported
        through a path no scan vetted, so its result does not count: whatever
        it wrote there is removed from the cache (at a path that now reaches a
        reviewed file, or whose source is gone) and False is returned."""
        mounts = _mounts()
        scans = {e: self._scan(e, mounts) for e in self.entries}
        if (mounts, tuple((e, scans[e]) for e in self.entries)) == self.observation and not self.stray:
            return True
        for entry, (found, _seen) in scans.items():
            if found is not None:
                self._purge(entry, found)
        self._sweep(self.targets)
        return False

    def _compiled_reviewed(self) -> bool:
        """Whether the run wrote bytecode for a reviewed file in its own prefix,
        outside the links: only possible by a path the scan did not see, one a
        test made during the run (a link in a temporary directory, say), from
        which another process of the run could have read it back. Known by
        the source's resolved path or identity or — the source gone since — by
        the modification time and size the file's header records. Checked
        before the prefix is discarded."""
        if self.prefix is None:
            return False
        suffixes, stack = self.probe.suffixes, [str(self.prefix)]
        while stack:
            folder = stack.pop()
            try:
                with os.scandir(folder) as it:
                    children = list(it)
            except OSError:
                continue
            for child in children:
                try:
                    if child.is_symlink() or (child.is_dir(follow_symlinks=False) and child.name.endswith(".pyc")):
                        continue  # a link into the cache, or a block
                    if child.is_dir(follow_symlinks=False):
                        stack.append(child.path)
                        continue
                    stem = _pyc_stem(child.name) if child.name.endswith(".pyc") else None
                    if stem is None or child.stat(follow_symlinks=False).st_size < 16:
                        continue  # not bytecode: a block, say
                    source_dir = os.sep + os.path.relpath(folder, self.prefix)
                    sources = [s for s in (os.path.join(source_dir, stem + x) for x in suffixes) if os.path.isfile(s)]
                    for source in sources:
                        st = os.stat(source)
                        if self.repo.reaches(os.path.realpath(source), (st.st_dev, st.st_ino), directory=False):
                            return True
                    if not sources:
                        with open(child.path, "rb") as handle:
                            header = handle.read(16)
                        if (len(header) == 16 and int.from_bytes(header[4:8], "little") == 0
                                and (int.from_bytes(header[8:12], "little"),
                                     int.from_bytes(header[12:16], "little")) in self.repo.headers):
                            return True
                except OSError:
                    continue
        return False

    @staticmethod
    def _mirror(base: Path, source: str) -> Path:
        return base / source.lstrip(os.sep)

    @staticmethod
    def _cache_child(parent: Path, name: str, create: bool = True) -> Path | None:
        """``parent/name`` as a real directory — made when missing and
        ``create`` — or None when it is anything else, a symbolic link above all."""
        path = parent / name
        if create:
            try:
                os.mkdir(path)
            except FileExistsError:
                pass
            except OSError:
                return None
        try:
            return path if stat.S_ISDIR(os.lstat(path).st_mode) else None
        except OSError:
            return None

    def _cache_dir(self, source: str, create: bool = True) -> Path | None:
        """The cache's mirror of ``source``, reached from the resolved cache root
        through real directories only: never a path that follows a link out of
        the cache."""
        path: Path | None = self.cache_root
        for part in Path(source).parts[1:]:
            path = self._cache_child(path, part, create)
            if path is None:
                return None
        return path

    def prepare(self, prefix: Path) -> bool:
        """Lay out the run's fresh ``prefix``: block the repository's image, then
        link the admitted entries, blocking every hazard in them. False when
        the cache cannot be used (the location unwritable or not a directory,
        its files not verifiable) or nothing could be linked; the caller then
        runs from a fresh, empty prefix and writes nothing."""
        try:
            self.cache_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not stat.S_ISDIR(os.lstat(self.cache_root).st_mode):
                return False
        except OSError:
            return False
        plan: list[tuple[Path, Path]] = []
        self.prefix = prefix
        try:
            for form in self.forms:
                within = [os.path.relpath(e, form) for e in self.inside if _within(e, form)]
                self._block(self._mirror(prefix, form), Path(form), within)
            for entry, found in self.hazards.items():
                self._purge(entry, found)
            for entry in self.entries:
                link = self._mirror(prefix, entry)
                link.parent.mkdir(parents=True, exist_ok=True)
                self._image(link, entry, self._cache_dir(entry), _tree(self.hazards[entry]), plan)
        except OSError:
            return False
        self.targets = [target for _link, target in plan]
        if not plan or not self._sweep(self.targets):
            return False
        try:
            for link, target in plan:
                os.symlink(target, link, target_is_directory=True)
        except OSError:
            return False
        return True

    def _block_bytecode(self, folder: Path, stem: str) -> None:
        """A directory at every name bytecode for module ``stem`` would take in
        ``folder`` (CPython's, at each optimisation level, and pytest's
        assertion rewrite): none can be written there, and none read."""
        tag, version = self.probe.tag, self.probe.pytest_version
        for name in (f"{stem}.{tag}.pyc", f"{stem}.{tag}.opt-1.pyc", f"{stem}.{tag}.opt-2.pyc",
                     *([f"{stem}.{tag}-pytest-{version}.pyc"] if version else [])):
            (folder / name).mkdir(exist_ok=True)

    def _block(self, mirror: Path, source: Path, admitted: list[str]) -> None:
        """Make ``mirror`` (the prefix's image of ``source``) unwritable, except
        along the way to the admitted entries below it (relative paths)."""
        mirror.parent.mkdir(parents=True, exist_ok=True)
        if not admitted:
            if not os.path.lexists(mirror):
                mirror.write_bytes(b"")
            return
        mirror.mkdir(exist_ok=True)
        below: dict[str, list[str]] = {}
        for rel in admitted:
            head, _, rest = rel.partition(os.sep)
            below.setdefault(head, []).append(rest)
        try:
            names = os.listdir(source)
        except OSError:
            names = []
        # First a directory at each name bytecode for a module here would take
        # (a plain file there would simply be replaced), then a plain file for
        # every other name, so no directory can be created below this one.
        for stem in {_stem(name, self.probe.suffixes) for name in names if name.endswith(self.probe.suffixes)}:
            self._block_bytecode(mirror, stem)
        for name in names:
            if name not in below and not os.path.lexists(mirror / name):
                (mirror / name).write_bytes(b"")
        for head, rests in below.items():
            if "" not in rests:  # "" — the head itself is an admitted entry, laid out by prepare()
                self._block(mirror / head, source / head, rests)

    def _image(self, link: Path, source: str, target: Path | None, node: dict | str,
               plan: list[tuple[Path, Path]]) -> None:
        """Lay out the prefix's image of ``source`` at ``link``. With no hazard
        in it: one link to its mirror ``target`` in the cache (added to
        ``plan``, made once the cache has been swept). Otherwise a real
        directory in which each hazard is blocked and every other subdirectory
        laid out the same way; files directly in it get no cached bytecode —
        what the run writes for them stays in its own prefix."""
        if node == _DIR:
            link.write_bytes(b"")
            return
        if not node:
            if target is not None:
                plan.append((link, target))
            return
        assert isinstance(node, dict)
        link.mkdir()
        for name, sub in node.items():
            if sub == _DIR:
                (link / name).write_bytes(b"")
            elif sub == _FILE:
                self._block_bytecode(link, _stem(name, self.probe.suffixes))
        try:
            names = os.listdir(source)
        except OSError:
            names = []
        for name in names:
            sub = node.get(name)
            child = os.path.join(source, name)
            if isinstance(sub, str) or (sub is None and not os.path.isdir(child)):
                continue
            below = self._cache_child(target, name) if target is not None else None
            self._image(link / name, child, below, sub or {}, plan)

    def _purge(self, entry: str, found: frozenset[tuple[str, str]]) -> None:
        """Remove from the cache any bytecode kept at a hazard path (written
        before the link existed, or by a run for which it is none), so the
        cache holds none for a reviewed file."""
        for rel, kind in found:
            if kind == _DIR:
                folder = self._cache_dir(_join(entry, rel), create=False)
                if folder is not None:
                    shutil.rmtree(folder, ignore_errors=True)
                continue
            folder = self._cache_dir(_join(entry, os.path.dirname(rel)), create=False)
            if folder is None:
                continue
            prefix = _stem(os.path.basename(rel), self.probe.suffixes) + "."
            try:
                names = os.listdir(folder)
            except OSError:
                continue
            for name in names:
                if name.startswith(prefix) and name.endswith(".pyc"):
                    try:
                        if not stat.S_ISDIR(os.lstat(folder / name).st_mode):
                            os.unlink(folder / name)
                    except OSError:
                        pass

    def _sweep(self, tops: list[Path]) -> bool:
        """Make the mirrors about to be linked safe to use. Removes every
        symbolic link in them (a write through one would leave the cache);
        every bytecode file whose source no longer exists (nothing is kept
        waiting at a path that may later be made to reach a reviewed file);
        and every file of the interpreter's cache tag it would load and fail on
        (a valid header over a damaged body: CPython does not recompile such a
        file). A file found loadable earlier in this process and unchanged
        since is not read again. False when the check could not run."""
        tag, magic, suffixes = self.probe.tag, self.probe.magic, self.probe.suffixes
        marks = (f".{tag}.", f".{tag}-")
        pending: list[tuple[str, tuple[int, int, int, int]]] = []
        for top in tops:
            stack = [str(top)]
            while stack:
                folder = stack.pop()
                try:
                    with os.scandir(folder) as it:
                        children = list(it)
                except OSError:
                    continue
                for child in children:
                    try:
                        if child.is_symlink():
                            os.unlink(child.path)
                        elif child.is_dir(follow_symlinks=False):
                            stack.append(child.path)
                        elif not child.name.endswith(".pyc"):
                            continue
                        elif not self._has_source(folder, child.name, suffixes):
                            os.unlink(child.path)
                        elif any(m in child.name for m in marks):
                            st = child.stat(follow_symlinks=False)
                            stamp = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
                            if _loadable.get((child.path, magic)) != stamp:
                                pending.append((child.path, stamp))
                    except OSError:
                        continue
        if not pending:
            return True
        try:
            proc = subprocess.run([self.python, "-c", _FIND_UNLOADABLE, magic],
                                  input=b"\0".join(os.fsencode(p) for p, _stamp in pending),
                                  cwd=str(self.cache_root), capture_output=True, timeout=300,
                                  env=clean_env(PYTHONDONTWRITEBYTECODE="1"))
        except (OSError, subprocess.SubprocessError):
            return False
        if proc.returncode != 0:
            return False
        unloadable = {os.fsdecode(p) for p in proc.stdout.split(b"\0") if p}
        for path, stamp in pending:
            if path not in unloadable:
                _loadable[(path, magic)] = stamp
                continue
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            except OSError:
                return False
        return True

    def _has_source(self, folder: str, name: str, suffixes: tuple[str, ...]) -> bool:
        """Whether the bytecode file ``name`` in the cache directory ``folder``
        has a source: the cache mirrors each source directory's absolute path."""
        stem = _pyc_stem(name)
        source_dir = os.sep + os.path.relpath(folder, self.cache_root)
        return stem is not None and any(os.path.isfile(os.path.join(source_dir, stem + s)) for s in suffixes)

    def purge_repository(self) -> None:
        """Leave the cache holding no bytecode for the repository's own files
        (a run for another repository, whose interpreter has this one on its
        path, may have put some there), except under an admitted entry."""
        keep = {p for p in (self._cache_dir(e, create=False) for e in self.inside) if p is not None}
        for form in self.forms:
            mirror = self._cache_dir(form, create=False)
            if mirror is not None:
                self._prune(mirror, keep)

    @classmethod
    def _prune(cls, path: Path, keep: set[Path]) -> None:
        """Remove ``path`` — reached from the cache root through real
        directories only — except what lies on the way to ``keep``. Nothing
        is followed: a symbolic link is removed, never what it points to."""
        if path in keep:
            return
        try:
            mode = os.lstat(path).st_mode
        except OSError:
            return
        if not stat.S_ISDIR(mode):
            try:
                os.unlink(path)
            except OSError:
                pass
        elif any(k.is_relative_to(path) for k in keep):
            try:
                names = os.listdir(path)
            except OSError:
                return
            for name in names:
                cls._prune(path / name, keep)
        else:
            shutil.rmtree(path, ignore_errors=True)


def _run_pytest(repo_root: Path, cond: AcceptanceCondition, python: str, timeout: int, *,
                detail: bool = False) -> dict[str, Any]:
    """Run a `pytest:` condition. Bytecode for the interpreter's own modules
    comes from the out-of-repository cache (IB-145); every reviewed file runs
    from its current source. When the interpreter's linked path entries
    changed while the condition ran, it is run again from source without the
    cache, and that is its result."""
    root = Path(repo_root).resolve()
    cache = _BytecodeCache.open(repo_root, root, python)
    result = _run_pytest_once(root, cond, python, timeout, detail=detail, cache=cache)
    if cache is not None:
        if cache.used and not cache.unchanged():
            result = _run_pytest_once(root, cond, python, timeout, detail=detail, cache=None)
        cache.purge_repository()
    return result


def _run_pytest_once(root: Path, cond: AcceptanceCondition, python: str, timeout: int, *,
                     detail: bool, cache: _BytecodeCache | None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="dekspec-evidence-") as tmp:
        report_path = Path(tmp) / "report.json"
        # Pin configuration and rootdir to the repository root: a pytest config
        # nested under the tests (or anywhere else) is never picked up. Bytecode
        # lives under a fresh per-run prefix outside the repository, so a stale
        # or planted `.pyc` cannot stand in for source; only the interpreter's
        # own path entries are linked into it from the cache, every path into
        # the repository blocked (_BytecodeCache).
        config = root_pytest_config(root)
        if config is None:
            config = Path(tmp) / "pytest.ini"
            config.write_text("[pytest]\n", encoding="utf-8")
        # The evidence plugin is stdlib-only and staged as a standalone module,
        # so any interpreter with pytest can load it — the project's test
        # interpreter usually does not have dekspec installed.
        plugin_dir = Path(tmp) / "plugin"
        plugin_dir.mkdir()
        (plugin_dir / f"{_PLUGIN_MODULE}.py").write_bytes(Path(pytest_evidence.__file__).read_bytes())
        extra_env = {"DEKSPEC_EVIDENCE_FULL": "1"} if detail else {}
        prefix = Path(tmp) / "pycache"
        prefix.mkdir()
        if cache is not None:
            cache.used = cache.prepare(prefix)
        if cache is None or not cache.used:
            # No cache: a fresh, empty prefix and no bytecode written, as before
            # it — nothing would outlive the run, and no repository bytecode may
            # be written for a later read.
            prefix = Path(tmp) / "pycache-source"
            prefix.mkdir()
            extra_env["PYTHONDONTWRITEBYTECODE"] = "1"
        env = clean_env(DEKSPEC_EVIDENCE_REPORT=str(report_path), PYTHONPATH=str(plugin_dir),
                        PYTHONPYCACHEPREFIX=str(prefix), **extra_env)
        cmd = [python, "-m", "pytest", *cond.nodes, "-p", _PLUGIN_MODULE,
               "-p", "no:cacheprovider", "-q", "--color=no", "-c", str(config), f"--rootdir={root}"]
        if detail:
            cmd += _full_message_options(config)
        started = time.monotonic()
        try:
            proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True,
                                  env=env, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "failed", "detail": f"timed out after {timeout}s"}
        finally:
            if cache is not None and cache.used:
                cache.stray = cache._compiled_reviewed()
        duration = round(time.monotonic() - started, 2)
        tail = (proc.stdout + proc.stderr)[-_TAIL_CHARS:]
        if not report_path.is_file():
            detail = (f"pytest is not installed for the test interpreter {python} — "
                      "set `execution.python` in .dekspec/config.yaml"
                      if "No module named pytest" in tail
                      else f"pytest under {python} exited {proc.returncode} without an evidence report")
            return {"status": "indeterminate", "exit_code": proc.returncode, "duration": duration,
                    "detail": detail, "tail": tail}
        data = json.loads(report_path.read_text(encoding="utf-8"))
    nodes: dict[str, str] = {}
    problems: list[str] = []
    deselected = data.get("deselected", [])
    for requested in cond.nodes:
        matched = {nid: _node_outcome(ph) for nid, ph in data["results"].items() if _node_matches(requested, nid)}
        dropped = [d for d in deselected if _node_matches(requested, d)]
        if dropped:
            problems.append(f"{requested}: {len(dropped)} case(s) deselected")
        if not matched:
            if not dropped:
                if data.get("collect_errors"):
                    problems.append(f"{requested}: collection error")
                else:
                    problems.append(f"{requested}: not collected (missing, renamed or deleted)")
            nodes[requested] = "not-run"
            continue
        nodes.update(matched)
        for nid, outcome in matched.items():
            if outcome != "passed":
                problems.append(f"{nid}: {outcome}")
    # The process exit status is an independent witness: a report that says
    # "passed" from a run pytest itself calls failed is not evidence.
    if not problems and proc.returncode != 0:
        problems.append(f"pytest exited {proc.returncode} although every requested node reported passed")
    plugins = sorted(
        str(Path(f).resolve().relative_to(root)) for f in data.get("plugin_files", [])
        if Path(f).resolve().is_relative_to(root) and Path(f).name != "conftest.py"
    )
    if any(v == "failed" for v in nodes.values()):
        status = "failed"
    elif problems:
        status = "not-run" if all("pytest exited" not in p for p in problems) else "failed"
    else:
        status = "passed"
    result = {"status": status, "exit_code": proc.returncode, "duration": duration, "nodes": nodes,
              "detail": "; ".join(problems) if problems else f"{len(nodes)} node(s) passed",
              "plugins_in_repo": plugins,
              "collect_errors": data.get("collect_errors", [])[:5], "tail": tail if status != "passed" else ""}
    if detail:
        # What the plugin saw, per node, for the floor report (ADR-062); never part of evidence.
        result["report"] = {k: data.get(k, default) for k, default in (
            ("results", {}), ("deselected", []), ("collect_errors", []), ("failures", {}), ("captured", {}))}
    return result


def run_pytest_detail(repo_root: Path, cond: AcceptanceCondition, *, python: str, timeout: int) -> dict[str, Any]:
    """Run a `pytest:` condition as evidence does — same interpreter, nodes,
    configuration, plugin and timeout — except that failure messages and
    captured output are recorded in full (assertion verbosity 2, no length
    caps in the plugin), and return the plugin's per-node report as well
    (phases, failure details, captured output). Records nothing."""
    return _run_pytest(repo_root, cond, python, cond.timeout or timeout, detail=True)


def _run_command(repo_root: Path, cond: AcceptanceCondition, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        proc = subprocess.run(cond.command or "", shell=True, cwd=str(repo_root), capture_output=True,
                              text=True, timeout=timeout, env=clean_env())
    except subprocess.TimeoutExpired:
        return {"status": "failed", "detail": f"timed out after {timeout}s"}
    output = proc.stdout + proc.stderr
    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "duration": round(time.monotonic() - started, 2),
        "output_sha256": _sha_bytes(output.encode("utf-8")),
        "detail": f"exit {proc.returncode}",
        "tail": output[-_TAIL_CHARS:] if proc.returncode else "",
    }


def run_condition(repo_root: Path, cond: AcceptanceCondition, *, python: str, timeout: int) -> dict[str, Any]:
    if cond.kind == "review":
        result = {"status": "needs-review", "detail": cond.review}
    elif cond.kind == "pytest":
        result = _run_pytest(repo_root, cond, python, cond.timeout or timeout)
    else:
        result = _run_command(repo_root, cond, cond.timeout or timeout)
    return {"id": cond.id, "kind": cond.kind, **result}
