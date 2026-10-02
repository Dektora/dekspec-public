"""Scope and protected-surface evaluation for a delivery diff (ADR-055/057).

Precedence, strongest first:

1. **Protected surfaces** — a listed path, glob, or ``path::symbol`` may not be
   modified, renamed away or deleted. Nothing overrides this: not an allowed
   glob, not a lifecycle exemption.
2. **Lifecycle exemptions** — only the execution records, tracker records
   (``br`` workspaces), generated spec indexes, the delivery's own IB files
   and acceptance assets, status-only edits of governed specs, and
   ``.dekspec/config.yaml`` changes confined to workflow sections
   (``integration.base``). (The old diff-confinement
   admit-set exempted all of ``dekspec/**``; a governing-spec edit is now an
   explicit, in-scope change instead.)
3. **Allowed scope** — delegated IBs: ``§Scope`` globs, so a new helper file
   inside an allowed glob needs no permission. Legacy IBs: the exact Files to
   Modify list (their ADR-049-era meaning). Anything else is a scope expansion.

Renames are evaluated on both sides (the old path leaves, the new path
arrives). Symbol-level protection is resolved with the Python AST on both the
base and current text; for non-Python files it degrades *stricter* to
file-level protection and says so.
"""

from __future__ import annotations

import ast
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from dekspec.diff_confinement import matches_any_glob
from dekspec.execution.fingerprint import _is_cache

__all__ = ["Change", "ScopeError", "ScopeReport", "changed_files", "evaluate_scope", "resolve_base"]



class ScopeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Change:
    status: str  # A M D R
    path: str  # current path (new path for renames)
    old_path: str | None = None


@dataclass
class ScopeReport:
    base: str
    changes: list[Change] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    exempt: list[str] = field(default_factory=list)
    unplanned_in_scope: list[str] = field(default_factory=list)
    missing_spec_impact: list[str] = field(default_factory=list)
    pre_run: list[str] = field(default_factory=list)
    bookkeeping: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations and not self.missing_spec_impact

    def as_dict(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "ok": self.ok,
            "changed": [c.path for c in self.changes],
            "violations": self.violations,
            "missing_spec_impact": self.missing_spec_impact,
            "unplanned_in_scope": self.unplanned_in_scope,
            "pre_run": self.pre_run,
            "bookkeeping": self.bookkeeping,
            "notes": self.notes,
        }


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=str(repo_root),
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise ScopeError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def resolve_base(repo_root: Path, base: str | None = None) -> str:
    """Merge-base commit between HEAD and the delivery's base branch."""
    candidates = [base] if base else ["main", "origin/main", "master", "origin/master"]
    for ref in candidates:
        proc = subprocess.run(["git", "merge-base", "HEAD", ref], cwd=str(repo_root),
                              capture_output=True, text=True)
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    raise ScopeError(f"cannot find a merge base with {' / '.join(c for c in candidates if c)}")


def changed_files(repo_root: Path, base_commit: str) -> list[Change]:
    """Work tree (committed + staged + unstaged + untracked) versus the base."""
    out = _git(repo_root, "diff", "--name-status", "-M", "-z", base_commit)
    parts = [p for p in out.split("\0") if p != ""]
    changes: list[Change] = []
    i = 0
    while i < len(parts):
        code = parts[i]
        if code.startswith("R") or code.startswith("C"):
            changes.append(Change("R" if code.startswith("R") else "A", parts[i + 2], parts[i + 1]))
            i += 3
        else:
            changes.append(Change(code[0], parts[i + 1]))
            i += 2
    untracked = _git(repo_root, "ls-files", "--others", "--exclude-standard", "-z")
    known = {c.path for c in changes}
    for path in (p for p in untracked.split("\0") if p):
        # Untracked interpreter/tool caches are produced by running the checks;
        # a tracked change is never filtered, whatever its name.
        if path not in known and not _is_cache(path):
            changes.append(Change("A", path))
    return changes


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _top_level_nodes(body: list[ast.stmt]) -> list[ast.stmt]:
    """Statements at this scope level, looking through compound statements
    (``if`` / ``try`` / ``with`` / ``for`` / ``while`` / ``match``) that do not
    open a new scope."""
    out: list[ast.stmt] = []
    for node in body:
        out.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        nested: list[ast.stmt] = []
        for attr in ("body", "orelse", "finalbody", "handlers", "cases"):
            for child in getattr(node, attr, None) or []:
                if isinstance(child, ast.stmt):
                    nested.append(child)
                elif isinstance(child, (ast.ExceptHandler, ast.match_case)):
                    nested.extend(child.body)
        out.extend(_top_level_nodes(nested))
    return out


def _walk_scope(node: ast.AST):
    """``ast.walk`` that does not descend into nested scopes (a walrus in a
    comprehension still binds the enclosing scope, so comprehensions are walked)."""
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(c for c in ast.iter_child_nodes(n) if not isinstance(c, _SCOPES) or c is node)


def _defines(node: ast.stmt, name: str) -> bool:
    """Does this statement bind or unbind ``name`` at its own scope level —
    a definition, any assignment target, ``del``, an import alias, a ``for`` /
    ``with`` / ``except`` / ``match`` capture or a walrus? Any of them replaces
    what the protected name means, so all of them belong to its segment."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == name
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return any((a.asname or a.name.split(".")[0]) == name for a in node.names)
    if getattr(ast, "TypeAlias", None) and isinstance(node, ast.TypeAlias):  # Python 3.12+
        return isinstance(node.name, ast.Name) and node.name.id == name
    own: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        own = list(node.targets) + [node.value]
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        own = [node.target] + ([node.value] if node.value is not None else [])
    elif isinstance(node, ast.Delete):
        own = list(node.targets)
    elif isinstance(node, (ast.For, ast.AsyncFor)):
        own = [node.target, node.iter]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        own = [i for item in node.items for i in (item.context_expr, item.optional_vars) if i is not None]
    elif isinstance(node, ast.Try) or (hasattr(ast, "TryStar") and isinstance(node, ast.TryStar)):
        if any(h.name == name for h in node.handlers):
            return True
    elif isinstance(node, ast.Match):
        own = [node.subject] + [c.pattern for c in node.cases] + [c.guard for c in node.cases if c.guard]
    elif isinstance(node, (ast.Expr, ast.Return, ast.If, ast.While, ast.Assert, ast.Raise)):
        own = [v for v in ast.iter_child_nodes(node) if isinstance(v, ast.expr)]
    for expr in own:
        for n in _walk_scope(expr):
            if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, (ast.Store, ast.Del)):
                return True
            if isinstance(n, ast.NamedExpr) and n.target.id == name:
                return True
            if isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name == name:
                return True
            if isinstance(n, ast.MatchMapping) and n.rest == name:
                return True
    return False


def _rebinders(tree: ast.Module, name: str) -> list[ast.stmt]:
    """Top-level functions or classes that declare ``global name``: calling
    them rebinds the protected name, so they are part of its segment."""
    return [top for top in tree.body if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and any(isinstance(n, ast.Global) and name in n.names for n in ast.walk(top))]


def _symbol_span(source: str, symbol: str) -> tuple[int, int] | None:
    """Line span of a function, class, or assigned name (dotted for members)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    body: list[ast.stmt] = list(tree.body)
    spans: list[tuple[int, int]] = []
    for depth, part in enumerate(symbol.split(".")):
        matches = [n for n in _top_level_nodes(body) if _defines(n, part)]
        if depth == 0:
            matches += [r for r in _rebinders(tree, part) if r not in matches]
        if not matches:
            return None
        if depth < len(symbol.split(".")) - 1:
            cls = next((m for m in matches if isinstance(m, ast.ClassDef)), None)
            if cls is None:
                return None
            body = list(cls.body)
            continue
        for node in matches:
            start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
            spans.append((start, getattr(node, "end_lineno", node.lineno)))
    return (min(a for a, _ in spans), max(b for _, b in spans)) if spans else None


def _base_text(repo_root: Path, base_commit: str, path: str) -> str | None:
    proc = subprocess.run(["git", "show", f"{base_commit}:{path}"], cwd=str(repo_root),
                          capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def _symbol_segment(source: str | None, symbol: str) -> str | None:
    if source is None:
        return None
    span = _symbol_span(source, symbol)
    if span is None:
        return None
    return "\n".join(source.splitlines()[span[0] - 1:span[1]])


#: Reflective names: however they are reached — a bare name, an attribute
#: (``builtins.globals``), called or not — each can rebind a module-level name
#: (namespace dictionaries, dynamic execution, module lookup, code and
#: function-globals swaps, subclass walking). ``vars`` counts only without an
#: argument; ``__dict__`` only on the module itself.
_REFLECTIVE = frozenset({
    "globals", "locals", "exec", "eval", "__import__", "import_module", "reload", "__builtins__",
    "__globals__", "__code__", "__closure__", "__defaults__", "__kwdefaults__",
    "__subclasses__", "__mro__", "__bases__", "__base__",
    "f_globals", "f_locals", "_getframe", "currentframe", "getmodule",
})
#: Modules whose import brings reflection into reach (``importlib`` itself — its
#: ``metadata`` / ``resources`` submodules do not).
_REFLECTIVE_MODULES = frozenset({"builtins", "importlib", "gc", "ctypes"})


def _reflective_import(n: ast.Import | ast.ImportFrom) -> bool:
    others = _REFLECTIVE_MODULES - {"importlib"}
    if isinstance(n, ast.ImportFrom):
        mod = n.module or ""
        if mod == "importlib":  # the loader functions, not `resources` / `metadata`
            return any(a.name in ("import_module", "reload", "__import__", "*") for a in n.names)
        return mod.split(".")[0] in others
    return any(a.name == "importlib" or a.name.split(".")[0] in others for a in n.names)


def _tail(expr: ast.AST) -> str | None:
    return expr.attr if isinstance(expr, ast.Attribute) else (expr.id if isinstance(expr, ast.Name) else None)


def _rebinding_sites(source: str, symbol: str, module: str) -> Counter | None:
    """Every place in ``source`` that could rebind ``symbol`` in this module
    other than its ordinary binding statements, keyed by the normalised source
    of its enclosing top-level statement — so a site that is added, edited or
    moved changes the result, and one that is untouched does not. Sites:

    * a reflective name (``_REFLECTIVE``), bare or as an attribute, called or
      not; ``vars()`` without arguments; an import of a reflective module;
    * ``sys.modules`` (or ``modules`` imported from ``sys``), a self-import, or
      ``__name__`` handed to a module lookup;
    * ``setattr`` / ``delattr`` / ``__setattr__`` / ``__delattr__`` / a store or
      deletion of the name / ``__dict__`` on the module itself or, for a class
      member, on its class;
    * a ``global`` / ``nonlocal`` declaration of the name, anywhere.

    Everyday code beside the symbol (``re.compile``, ``getLogger(__name__)``,
    ``setattr(self, …)``, ``vars(ns)``, ``obj.__dict__``, a string equal to the
    name) is not a site. ``None`` when unparseable. This is a static guard of
    the module's own namespace, not a sandbox: another module can still
    monkeypatch the symbol (outside per-file protection)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    parts = symbol.split(".")
    leaf, owner = parts[-1], (parts[-2] if len(parts) > 1 else None)
    aliases: set[str] = set()
    owners: set[str] = {owner} if owner else set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            aliases |= {a.asname or a.name.split(".")[0] for a in n.names if a.name.split(".")[-1] == module}
        elif isinstance(n, ast.ImportFrom):
            aliases |= {a.asname or a.name for a in n.names if a.name == module}
        elif owner and isinstance(n, ast.Assign) and isinstance(n.value, ast.Name) and n.value.id == owner:
            owners |= {x.id for x in n.targets if isinstance(x, ast.Name)}  # `_A = Api`

    def module_ref(expr: ast.AST) -> bool:
        for node in ast.walk(expr):
            if isinstance(node, ast.Name) and node.id in aliases:
                return True
            if _tail(node) == "modules" or (isinstance(node, ast.Call) and _tail(node.func) in _REFLECTIVE):
                return True
        return False

    def target(expr: ast.AST) -> bool:
        return module_ref(expr) or (isinstance(expr, ast.Name) and expr.id in owners)

    def keyed(node: ast.AST, key: str):
        """Nodes with the key of their innermost enclosing function (or top-level
        statement): editing an unrelated method of the same class is no change."""
        for child in ast.iter_child_nodes(node):
            inner = ast.unparse(child) if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else key
            yield child, inner
            yield from keyed(child, inner)

    sites: Counter = Counter()
    for top in tree.body:
        top_key = ast.unparse(top)
        for n, key in [(top, top_key), *keyed(top, top_key)]:
            found: list[tuple[str, str]] = []
            if isinstance(n, ast.Name) and n.id in _REFLECTIVE:
                found.append(("reflective", n.id))
            elif isinstance(n, ast.Attribute):
                if n.attr in _REFLECTIVE:
                    found.append(("reflective", n.attr))
                if n.attr == "modules":
                    found.append(("module-lookup", "modules"))
                if n.attr == "__dict__" and target(n.value):
                    found.append(("module-dict", "__dict__"))
                if n.attr == leaf and isinstance(n.ctx, (ast.Store, ast.Del)) and target(n.value):
                    found.append(("attribute-store", leaf))
            elif isinstance(n, ast.Call):
                name = _tail(n.func)
                if name == "vars" and not n.args and not n.keywords:
                    found.append(("reflective", "vars"))
                elif name in ("setattr", "delattr", "__setattr__", "__delattr__") and n.args and target(n.args[0]):
                    found.append(("module-" + name.strip("_"), leaf))
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in n.names]
                mod = n.module if isinstance(n, ast.ImportFrom) else None
                if _reflective_import(n):
                    found.append(("reflective-import", ",".join(names)))
                if any(x.split(".")[-1] == module for x in names) or (mod or "").split(".")[-1] == module:
                    found.append(("import-self", module))
                if mod == "sys" and "modules" in names:
                    found.append(("module-lookup", "modules"))
            elif isinstance(n, (ast.Global, ast.Nonlocal)) and leaf in n.names:
                found.append(("global", leaf))
            for kind, name in found:
                sites[(kind, name, key)] += 1
    return sites


def symbol_protection_violation(old: str | None, new: str | None, surface: str) -> str | None:
    """The one definition of `path::symbol` protection, shared by `dekspec ib
    verify` (base → working tree) and the commit guard (HEAD → staged index).

    ``old`` / ``new`` are the file's text before and after (``None`` = absent).
    Changes outside the symbol are free; editing, deleting or renaming the
    symbol is a violation. A symbol that resolves on neither side, or a
    non-Python file, falls back to whole-file protection rather than
    protecting nothing."""
    path, symbol = surface.split("::", 1)
    if old == new:
        return None
    if new is None:
        return f"{surface}: file deleted or renamed away"
    if not path.endswith(".py"):
        return f"{surface}: protected file modified (symbol-level protection needs Python)"
    module = Path(path).stem
    before_sites = _rebinding_sites(old or "", symbol, module) or Counter()
    after_sites = _rebinding_sites(new, symbol, module)
    if after_sites is None:
        return f"{surface}: file no longer parses; protected at file level"
    added = after_sites - before_sites
    if added:
        kind, name, _statement = sorted(added)[0]
        return (f"{surface}: {kind} `{name}` added or changed outside the symbol — it could rebind it, so the "
                "symbol cannot be proven untouched (file-level)")
    before, after = _symbol_segment(old, symbol), _symbol_segment(new, symbol)
    if before is not None and after is None:
        return f"{surface}: symbol removed or renamed"
    if before is None and after is None:
        return f"{surface}: protected file modified (symbol unresolved)"
    if before != after:
        return f"{surface}: symbol body modified" if before is not None else f"{surface}: symbol introduced"
    return None


def _protected_hits(repo_root: Path, base_commit: str, change: Change, surface: str,
                    notes: list[str]) -> str | None:
    if "::" in surface:
        path, _symbol = surface.split("::", 1)
        touched = {change.path, change.old_path} - {None}
        if path not in touched:
            return None
        if change.status == "D" or (change.status == "R" and change.old_path == path):
            return f"{surface}: file {'deleted' if change.status == 'D' else 'renamed away'}"
        current_path = Path(repo_root) / path
        current = current_path.read_text(encoding="utf-8", errors="replace") if current_path.is_file() else None
        hit = symbol_protection_violation(_base_text(repo_root, base_commit, path), current, surface)
        if hit and "needs Python" in hit:
            notes.append(f"{surface}: symbol-level protection needs Python; treated as file-level")
        elif hit and "unresolved" in hit:
            notes.append(f"{surface}: symbol not found; protected at file level")
        return hit
    for candidate in (change.path, change.old_path):
        if candidate and (candidate == surface or matches_any_glob(candidate, [surface])):
            verb = {"D": "deleted", "R": "renamed", "A": "added"}.get(change.status, "modified")
            return f"{surface}: {candidate} {verb}"
    return None


def _is_lifecycle(path: str, ib_files: set[str], spec_root: str) -> bool:
    """Records the workflow itself writes: execution records, tracker records
    (`br` workspaces), generated spec indexes, and the delivery's own contract
    files. Never implementation."""
    return (
        _is_execution_record_file(path)
        or (path.split("/", 1)[0] in (".beads", ".beads-issues", ".beads-dekspec")
            and path.rsplit(".", 1)[-1] in _TRACKER_SUFFIXES)
        or path in ib_files
        or (path.startswith(spec_root + "/") and path.count("/") == 1 and path.endswith("-index.md"))
    )


#: What a `br` workspace holds: issue logs, its config and database, docs.
_TRACKER_SUFFIXES = {"jsonl", "json", "yaml", "yml", "toml", "md", "db", "gitignore", "lock"}


def _is_execution_record_file(path: str) -> bool:
    from dekspec.execution.record import is_record_file

    return is_record_file(path)


_RUNNER_FILENAMES = {"conftest.py", "pytest.ini", ".pytest.ini", "pytest.toml", "tox.ini", "setup.cfg",
                     "pyproject.toml", "sitecustomize.py", "usercustomize.py"}


def _never_pre_run(path: str) -> bool:
    """Files that can change what verification means are always this IB's
    responsibility, whenever they changed: DekSpec state (including the
    execution settings) and test-runner configuration."""
    return path.startswith(".dekspec/") or path.rsplit("/", 1)[-1] in _RUNNER_FILENAMES


def anchor_in_history(repo_root: Path, commit: str | None) -> bool:
    """Is ``commit`` an existing ancestor of HEAD? An authorization anchor
    rewritten away (a rebase or squash) proves nothing about what predates the
    run, so callers must not grant a pre-run allowance against it."""
    if not commit:
        return False
    exists = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=str(repo_root),
                            capture_output=True).returncode == 0
    return exists and subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=str(repo_root),
                                     capture_output=True).returncode == 0


def _same_as(repo_root: Path, commit: str | None, path: str, spec_root: str = "dekspec") -> bool:
    """True when ``path`` has the same content at ``commit`` and now — for
    governed markdown, ignoring lifecycle bookkeeping (status, Modified,
    Amendment Log), exactly as the fingerprint does. False whenever ``commit``
    is not an ancestor of HEAD in this repository (fail closed)."""
    from dekspec.execution.fingerprint import normalize_governed_markdown

    if not anchor_in_history(repo_root, commit):
        return False
    before = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=str(repo_root), capture_output=True)
    current = Path(repo_root) / path
    if before.returncode != 0:
        return not current.exists()
    if not current.is_file():
        return False
    now = current.read_bytes()
    if now == before.stdout:
        return True
    if path.startswith(spec_root + "/") and path.endswith(".md"):
        return normalize_governed_markdown(before.stdout.decode("utf-8", "replace")) == \
            normalize_governed_markdown(now.decode("utf-8", "replace"))
    return False


#: The `.dekspec/config.yaml` setting that configures the workflow around an IB —
#: which branch its delivery integrates into — not what its verification or
#: integration gates mean. Every other setting (`execution:`, the rest of
#: `integration:` — method, push, the worktree setup command — and any other
#: key) stays judged as the IB's own change.
_CONFIG_PATH = ".dekspec/config.yaml"


def _workflow_view(config: dict) -> dict:
    view = dict(config)
    integration = view.get("integration")
    if isinstance(integration, dict):
        integration = {k: v for k, v in integration.items() if k != "base"}
        if integration:
            view["integration"] = integration
        else:
            view.pop("integration")
    return view


def _workflow_config_only(repo_root: Path, base_commit: str, change: Change) -> bool:
    import yaml

    if change.path != _CONFIG_PATH or change.status not in ("A", "M"):
        return False
    try:
        old = yaml.safe_load(_base_text(repo_root, base_commit, _CONFIG_PATH) or "") or {}
        new = yaml.safe_load((Path(repo_root) / _CONFIG_PATH).read_text(encoding="utf-8")) or {}
    except (yaml.YAMLError, OSError):
        return False
    if not isinstance(old, dict) or not isinstance(new, dict):
        return False
    return _workflow_view(old) == _workflow_view(new)


def predates_run(repo_root: Path, base_commit: str, anchor: str | None, path: str,
                 spec_root: str = "dekspec", *, companions_of: Iterable[str] | None = None) -> bool:
    """Did the delivery change ``path`` *before* the run was authorized?
    Measured from the fork point between the anchor and the base (so merging a
    moved base mid-run changes nothing): the path changed between the fork and
    the anchor, the base did not change it, and it is unchanged since the anchor.
    ``companions_of`` (the run's own specification files) narrows this to that
    specification's companions — every such commit also changed one of those
    files — which is what an autonomous delivery may carry (`/implement`
    readiness). Touching some other specification is not enough. An anchor
    that is itself on the base (authorization landed before the delivery was cut)
    has no such interval, so every change in the delivery — including reverting
    what the base changed after the authorization — is the run's."""
    if not anchor_in_history(repo_root, anchor):
        return False
    fork = subprocess.run(["git", "merge-base", anchor, base_commit], cwd=str(repo_root),
                          capture_output=True, text=True).stdout.strip()
    if not fork:
        return False

    def at(rev: str) -> bytes | None:
        shown = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=str(repo_root), capture_output=True)
        return shown.stdout if shown.returncode == 0 else None

    at_fork = at(fork)
    if at(anchor) == at_fork or at(base_commit) != at_fork:
        return False
    if not _same_as(repo_root, anchor, path, spec_root):
        return False
    if companions_of is None:
        return True
    # Only the run's own specification's companions: every commit that changed the path
    # before the authorization also changed one of that specification's files. Unrelated
    # work — even work landing its own, other specification — is not exempt.
    own = set(companions_of)
    commits = subprocess.run(["git", "log", "--format=%H", f"{fork}..{anchor}", "--", path], cwd=str(repo_root),
                             capture_output=True, text=True).stdout.split()
    for commit in commits:
        touched = set(subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit],
                                     cwd=str(repo_root), capture_output=True, text=True).stdout.split())
        if not touched & own:
            return False
    return bool(commits)


def _bookkeeping_only(repo_root: Path, base_commit: str, change: Change, spec_root: str) -> bool:
    """A governed artifact whose only change is lifecycle bookkeeping (Status,
    Modified, Amendment Log) — e.g. the parent Intent flipping to COMPLETE — or
    a DekSpec configuration change confined to workflow sections."""
    from dekspec.execution.fingerprint import normalize_governed_markdown

    if _workflow_config_only(repo_root, base_commit, change):
        return True
    if change.status != "M" or not (change.path.startswith(spec_root + "/") and change.path.endswith(".md")):
        return False
    before = _base_text(repo_root, base_commit, change.path)
    current = Path(repo_root) / change.path
    if before is None or not current.is_file():
        return False
    return normalize_governed_markdown(before) == normalize_governed_markdown(
        current.read_text(encoding="utf-8", errors="replace"))


def evaluate_scope(
    repo_root: Path,
    contracts: list[Any],
    *,
    base: str | None = None,
    spec_root: str = "dekspec",
    planned_files: Iterable[str] = (),
    since: str | None = None,
) -> ScopeReport:
    """Evaluate the delivery diff against one or more IB contracts.

    For a multi-IB delivery the allowed scope is the union of the IBs'
    scopes, and every IB's protected surfaces apply to the whole delivery:
    a sibling IB's general allowance never unlocks another IB's protected
    surface (ADR-058).

    Attribution: ``since`` is the commit the IB was authorized at. A file
    outside the allowed scope whose content is unchanged since then was
    changed *before* this IB was authorized (e.g. the spec authoring that
    preceded it) and is reported as ``pre_run``, not as this IB's scope
    expansion — except DekSpec state and test-runner configuration, which are
    always judged. Protected surfaces get no such allowance: they are compared
    with the delivery base, whoever changed them.
    """
    repo_root = Path(repo_root)
    base_commit = resolve_base(repo_root, base)
    report = ScopeReport(base=base_commit)
    report.changes = changed_files(repo_root, base_commit)
    if since and not anchor_in_history(repo_root, since):
        report.notes.append(f"authorization anchor {since[:12]} is not in this history (rebased or squashed?): "
                            "no change is attributed to before the run")
        since = None

    # The IB files and their acceptance assets are contract material, not
    # implementation: they are governed by the contract hash and the
    # acceptance baseline (ADR-057), so scope does not judge them.
    ib_files = {c.rel_path for c in contracts} | {a for c in contracts for a in c.acceptance_asset_paths()}
    protected = [(c.ib_id, s) for c in contracts for s in c.protected]
    delegated_globs = [g for c in contracts if c.is_delegated for g in c.scope]
    legacy_files = {f for c in contracts if not c.is_delegated for f in c.scope}
    planned = set(planned_files)
    for c in contracts:
        for h in c.hypothesis:
            planned.update(re.findall(r"`([^`]+)`", h))

    for change in report.changes:
        hits = []
        for ib_id, surface in protected:
            hit = _protected_hits(repo_root, base_commit, change, surface, report.notes)
            if hit:
                hits.append(hit)
                report.violations.append({"kind": "protected-surface", "ib": ib_id,
                                          "path": change.path, "detail": hit})
        if hits:
            continue
        paths = [p for p in (change.path, change.old_path) if p]
        if all(_is_lifecycle(p, ib_files, spec_root) for p in paths):
            report.exempt.append(change.path)
            continue
        if _bookkeeping_only(repo_root, base_commit, change, spec_root):
            report.bookkeeping.append(change.path)
            continue
        for p in paths:
            if matches_any_glob(p, delegated_globs) or p in legacy_files:
                continue
            if (since and not any(_never_pre_run(q) for q in paths)
                    and all(predates_run(repo_root, base_commit, since, q, spec_root) for q in paths)):
                report.pre_run.append(change.path)
                break
            report.violations.append({"kind": "scope-expansion", "path": p,
                                      "detail": f"{p} is outside every allowed scope"})
            break
        else:
            if change.path not in planned and change.status in ("A", "M", "R"):
                report.unplanned_in_scope.append(change.path)

    touched = {c.path for c in report.changes} | {c.old_path for c in report.changes if c.old_path}
    from dekspec.execution.references import artifact_path

    for c in contracts:
        for ref in c.spec_impact:
            path = artifact_path(repo_root, ref, spec_root=spec_root)
            rel = str(path.relative_to(repo_root)) if path else None
            if rel is None or rel not in touched:
                report.missing_spec_impact.append(
                    f"{c.ib_id} declares spec impact on {ref} but the delivery does not modify it"
                )
    return report
