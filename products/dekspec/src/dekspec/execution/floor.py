"""`dekspec ib floor` — the acceptance floor report (ADR-062, IB-137).

A read-only report that joins, for each `pytest:` acceptance condition of a
delegated IB, its test nodes with

* whether each node is **new** or **preserves** behavior that predates the IB
  (read from history: the node's test function, decorators included, is
  textually identical at the parent of the commit that first added the IB
  file, renames followed), ignoring Basis declarations and comparing the
  bounded expectation support in IB-183 O-11;
* its **failure kind** — `genuine-red` only for an assertion-class failure of
  the call phase whose own message and captured output carry no usage or
  import signature, raised in test-owned code; every other outcome is
  reported with its kind;
* its **failure line** (`<file>:<line>: <message>`);
* the **expectation basis** it declares (`Basis:` lines, also after a
  write-tests assertion stamp in a comment; inherited ones marked). Code
  never judges a basis's adequacy; the reviewer does.

It states the digest the acceptance baseline would record for the current
assets (the same computation `ib accept` / `ib baseline` use). It never
writes to the repository or the execution record.
"""

from __future__ import annotations

import ast
import configparser
import io
import re
import subprocess
import tokenize
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from dekspec.execution import git_reads
from dekspec.execution import acceptance as acc
from dekspec.execution.contract import ContractError, IBContract, find_ib_path, load_contract, pytest_node_file

__all__ = ["FloorError", "UnknownIB", "GENUINE", "failure_kind", "floor_report", "floor_text",
           "declared_bases", "function_span", "node_path"]

GENUINE = "genuine-red"

#: O-5 signatures, matched in the failure's own message and the node's captured output only.
USAGE_SIGNATURES = ("invalid choice:", "unrecognized arguments:", "the following arguments are required:",
                    "error: argument")
IMPORT_SIGNATURES = ("ModuleNotFoundError", "No module named", "ImportError: cannot import name")
MISSING_SYMBOL_SIGNATURES = ("has no attribute", "NameError")

_UNCOMMITTED_NOTE = ("the IB file is not committed, so every node is classified new — commit the IB to "
                     "distinguish preserved nodes")


class FloorError(RuntimeError):
    """The floor cannot be reported (legacy IB, unreadable contract, no test runner)."""


class UnknownIB(FloorError):
    """No IB file exists for the reference."""


# ------------------------------------------------------------------ failure kinds
def _signature_kind(text: str) -> str | None:
    if any(sig in text for sig in USAGE_SIGNATURES):
        return "usage-exit"
    if any(sig in text for sig in IMPORT_SIGNATURES):
        return "import-error"
    if any(sig in text for sig in MISSING_SYMBOL_SIGNATURES):
        return "missing-symbol"
    return None


def failure_kind(phases: dict[str, str], failures: dict[str, Any], captured: str) -> str:
    """The O-5 kind of one collected node from its per-phase outcomes and failure details."""
    values = set(phases.values())
    if "xfail" in values or "xpass" in values:
        return "xfail"
    if phases.get("setup") == "skipped" or phases.get("call") == "skipped":
        return "skipped"
    if phases.get("setup") == "failed":
        return "setup-error"
    if phases.get("call") == "failed":
        info = failures.get("call") or {}
        signature = _signature_kind(f"{info.get('message', '')}\n{captured}")
        if signature:
            return signature
        if info.get("assertion") and info.get("test_assertion", True):
            return GENUINE
        return f"other-exception:{info.get('type') or 'unknown'}"
    if phases.get("teardown") == "failed":
        return "setup-error"
    if phases.get("call") == "passed":
        return "passed"
    return "not-collected"


# ------------------------------------------------------------------ source: spans and bases
def node_path(node: str) -> tuple[str, list[str]]:
    """`tests/t.py::TestA::test_b[p]` → (`tests/t.py`, ["TestA", "test_b"]).

    A parameter suffix maps to its function and a class-qualified id to its
    method (O-6). The suffix is cut before splitting, so a parameter id that
    itself contains `::` cannot be mistaken for a class."""
    file, _sep, rest = node.partition("::")
    rest = rest.split("[", 1)[0]
    return file, [name for name in rest.split("::") if name]


def _find_def(tree: ast.Module, names: list[str]) -> tuple[ast.AST | None, list[ast.ClassDef]]:
    """The function a node id names, and its enclosing classes (outermost first)."""
    body: list[ast.stmt] = tree.body
    classes: list[ast.ClassDef] = []
    for i, name in enumerate(names):
        last = i == len(names) - 1
        match = None
        for stmt in body:
            if last and isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == name:
                match = stmt
            elif not last and isinstance(stmt, ast.ClassDef) and stmt.name == name:
                match = stmt
        if match is None:
            return None, classes
        if last:
            return match, classes
        classes.append(match)
        body = match.body
    return None, classes


def _span(fn: ast.AST) -> tuple[int, int]:
    start = min([fn.lineno, *(d.lineno for d in getattr(fn, "decorator_list", []))])
    return start, fn.end_lineno or fn.lineno


def function_span(source: str, names: list[str]) -> str | None:
    """The source text of the named function, decorators included (None: absent or unparseable)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    fn, _classes = _find_def(tree, names)
    if fn is None:
        return None
    start, end = _span(fn)
    return "\n".join(source.splitlines()[start - 1:end])


#: IB-143 O-5: a comment whose text, after an optional write-tests assertion stamp
#: (`REQUIRED`, `GIVEN` or `INCIDENTAL`, then `.`, `:` or whitespace and any stamp
#: text), continues with `Basis:` — `# REQUIRED. Basis: …`, `# GIVEN: … Basis: …`.
_STAMPED_BASIS = re.compile(r"(?:REQUIRED|GIVEN|INCIDENTAL)[.:\s].*?\bBasis:(?P<text>.*)", re.S)


def _basis_lines(text: str | None) -> list[str]:
    """Docstring `Basis:` lines (line-start form only), verbatim after the label."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("Basis:"):
            out.append(line[len("Basis:"):].strip())
    return out


def _comment_basis(text: str) -> str | None:
    """The basis a comment declares (its text after `#`), verbatim after the
    label: a comment that starts `Basis:`, or one that continues with `Basis:`
    after an assertion stamp (O-5). None when it declares none."""
    if text.startswith("Basis:"):
        return text[len("Basis:"):].strip()
    stamped = _STAMPED_BASIS.fullmatch(text)
    return stamped["text"].strip() if stamped else None


def _comments(source: str) -> list[tuple[int, str]]:
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                out.append((tok.start[0], tok.string.lstrip("#").strip()))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return out


def declared_bases(source: str, names: list[str]) -> list[dict[str, Any]] | str:
    """O-7: the `Basis:` lines that apply to the named test, verbatim after the label.

    Own: the function's docstring and comments inside its span (decorators
    included). Inherited: enclosing class docstrings, the module docstring and
    module-level comments. A comment counts when it starts `Basis:` or carries
    it after an assertion stamp (IB-143 O-5); a docstring line when it starts
    `Basis:`. ``"unreadable"`` when the file does not parse."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return "unreadable"
    fn, classes = _find_def(tree, names)
    comments = _comments(source)
    bases: list[dict[str, Any]] = []

    def add(text: str, inherited: bool) -> None:
        entry = {"text": text, "inherited": inherited}
        if text.strip() and entry not in bases:
            bases.append(entry)

    if fn is not None:
        start, end = _span(fn)
        for text in _basis_lines(ast.get_docstring(fn, clean=True)):
            add(text, False)
        for line, text in comments:
            declared = _comment_basis(text) if start <= line <= end else None
            if declared is not None:
                add(declared, False)
    for cls in classes:
        for text in _basis_lines(ast.get_docstring(cls, clean=True)):
            add(text, True)
    for text in _basis_lines(ast.get_docstring(tree, clean=True)):
        add(text, True)
    top_spans = [_span(s) for s in tree.body
                 if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    for line, text in comments:
        declared = _comment_basis(text)
        if declared is not None and not any(a <= line <= b for a, b in top_spans):
            add(declared, True)
    return bases


# ------------------------------------------------------------------ history: new or preserved
def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return git_reads.run(str(root), *args, capture_output=True, text=True)


def ib_origin(root: Path, rel_path: str) -> tuple[bool, str | None]:
    """(committed, origin): the parent of the earliest commit that added the IB
    file under any name (renames followed). ``origin`` is None for a root
    commit (the empty tree: nothing predates the IB)."""
    proc = _git(root, "log", "--follow", "--diff-filter=A", "--format=%H", "--", rel_path)
    commits = [c for c in proc.stdout.split() if c] if proc.returncode == 0 else []
    if not commits:
        return False, None
    first = commits[-1]
    parent = _git(root, "rev-parse", "--verify", "-q", f"{first}^")
    return True, (parent.stdout.strip() or None) if parent.returncode == 0 else None


def _source_at(root: Path, rev: str, rel: str, cache: dict[tuple[str, str], str | None]) -> str | None:
    key = (rev, rel)
    if key not in cache:
        shown = _git(root, "show", f"{rev}:{rel}")
        cache[key] = shown.stdout if shown.returncode == 0 else None
    return cache[key]


def _without_basis(source: str, names: list[str]) -> str:
    """Remove declaration text only; retain executable code and all other comments."""
    lines = source.splitlines()
    removals: set[int] = set()
    try:
        tree = ast.parse(source)
        fn, _ = _find_def(tree, names)
        if fn is None:
            return source
        first, last = _span(fn)
        for owner in (fn,):
            doc = ast.get_docstring(owner, clean=False)
            if doc is None or not _basis_lines(doc):
                continue
            statement = owner.body[0]
            kept = [line for line in doc.splitlines() if not line.strip().startswith("Basis:")]
            start, end = statement.lineno - 1, statement.end_lineno
            if lines[start][:statement.col_offset].strip() or lines[end - 1][statement.end_col_offset:].strip():
                # A declaration sharing a physical line with code is not a
                # disposable line: never erase a neighboring assertion.
                continue
            if not any(line.strip() for line in kept):
                removals.update(range(start, end))
            else:
                # In a mixed docstring, keep its original delimiters and all
                # non-Basis text; adding a declaration must not rewrite prose.
                for index in range(start, end):
                    if lines[index].strip().startswith("Basis:"):
                        removals.add(index)
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if (tok.type != tokenize.COMMENT or not first <= tok.start[0] <= last
                    or _comment_basis(tok.string.lstrip("#").strip()) is None):
                continue
            index = tok.start[0] - 1
            prefix = lines[index][:tok.start[1]]
            if prefix.strip():
                lines[index] = prefix.rstrip()
            else:
                removals.add(index)
    except (SyntaxError, ValueError, tokenize.TokenError):
        return source
    return "\n".join(line for i, line in enumerate(lines) if i not in removals)


class _Support:
    """O-11(b): a module binding closure, never a search for same-named methods.

    Only definitions and plain-name assignments can be proved unrelated.
    Everything else remains in the projection even if its names look unused.
    """

    def __init__(self, source: str, names: list[str], fixture_sources: Sequence[str] = (),
                 *, extra_roots: set[str] | None = None):
        self.source = _without_basis(source, names)
        self.tree = ast.parse(self.source)
        self.fn, self.classes = _find_def(self.tree, names)
        self.bindings: dict[str, list[ast.stmt]] = {}
        self.statements: dict[tuple[str, ...], list[str]] = {}
        self.always: list[ast.stmt] = []
        self.fixtures: dict[str, set[str]] = {}
        self.aliases: dict[str, str] = {}
        for stmt in self.tree.body:
            if isinstance(stmt, ast.Import):
                self.aliases.update((a.asname or a.name.split(".")[0], a.name) for a in stmt.names)
            elif isinstance(stmt, ast.ImportFrom):
                self.aliases.update((a.asname or a.name, f"{stmt.module}.{a.name}") for a in stmt.names)
            elif isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                symbol = self._symbol(stmt.value)
                if symbol:
                    self.aliases.update((name, symbol) for name in self._names(stmt))
        # Pytest registers module xunit setup/teardown as autouse fixtures.
        # They are roots for every selected node, including class methods.
        self.roots = {"pytestmark", "pytest_plugins", "setup_module", "setUpModule", "teardown_module",
                      "tearDownModule", "setup_function", "teardown_function"}
        if self.fn is not None and not self.classes:
            self.roots.add(self.fn.name)
        for stmt in self.tree.body:
            keys = self._names(stmt)
            if keys:
                self.statements.setdefault(keys, []).append(self._text(stmt))
                for key in keys:
                    self.bindings.setdefault(key, []).append(stmt)
            else:
                self.always.append(stmt)
            # Pytest invokes hook bindings regardless of definition syntax.
            self.roots.update(key for key in keys if key.startswith("pytest_"))
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self._fixture_roots(stmt)
        # External/configured fixtures can request a module override without
        # the test naming it. Without the complete installed plugin graph, no
        # registered fixture can be proved unrelated by module names alone.
        for bindings in self.fixtures.values():
            self.roots.update(bindings)
        for stmt in self.tree.body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and self._fixture_factory(stmt):
                self.roots.update(self._names(stmt))
        self.reached: set[str] = set()
        self.dynamic = any(isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names)
                           for n in ast.walk(self.tree))
        seeds = [self.fn, *self.classes, *self.always]
        pending = self.roots | (extra_roots or set())
        for seed in seeds:
            if seed is not None:
                pending.update(self._references(seed))
        if self.classes:
            pending.add(self.classes[0].name)
        self._close(pending)
        while fixture_sources:
            reached = set(self.reached)
            for source in fixture_sources:
                # Only reached code in each module may reach back into the
                # test file. Its own fixture/hook roots still participate.
                imported_roots = {a.name for n in ast.walk(self.tree) if isinstance(n, ast.ImportFrom)
                                  for a in n.names if a.asname in self.reached}
                support = _Support(source, [], extra_roots=self.reached | imported_roots)
                self._close(set(support.reached))
                self.dynamic |= support.dynamic
            if self.reached == reached:
                break

    def _close(self, pending: set[str]) -> None:
        """Follow module bindings and fixture edges to a fixed point."""
        while pending:
            name = pending.pop()
            if name in self.reached:
                continue
            self.reached.add(name)
            # Fixture registration adds edges; it never replaces the module
            # binding, and every implementation of a registered name matters.
            pending.update(self.fixtures.get(name, ()))
            for stmt in self.bindings.get(name, []):
                pending.update(self._references(stmt))

    def _fixture_roots(self, stmt: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        """Exclude a decorated binding only when its fixture role is readable.

        Unknown decorators may register autouse or renamed fixtures. Keeping
        them as roots makes uncertainty propagate through the same name closure
        as ordinary fixtures, including declarations added after the origin.
        """
        for decorator in stmt.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            label = self._symbol(call.func if call else decorator)
            if label.startswith("pytest.mark."):
                continue
            if label != "pytest.fixture":
                self.roots.add(stmt.name)
                continue
            exposed = stmt.name
            if call:
                if call.args:
                    self.roots.add(stmt.name)
                for kw in call.keywords:
                    if kw.arg is None:
                        self.roots.add(stmt.name)
                    elif kw.arg == "autouse":
                        if not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
                            self.roots.add(stmt.name)
                    elif kw.arg == "name":
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            exposed = kw.value.value
                        else:
                            self.roots.add(stmt.name)
            self.fixtures.setdefault(exposed, set()).add(stmt.name)

    def _fixture_factory(self, stmt: ast.stmt) -> bool:
        """Follow local factory bindings without executing registration code."""
        pending = [stmt]
        seen: set[str] = set()
        while pending:
            for node in ast.walk(pending.pop()):
                if isinstance(node, (ast.Name, ast.Attribute)) and (
                    self._symbol(node).split(".")[-1] in {"fixture", "yield_fixture"}
                ):
                    return True
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in seen:
                    seen.add(node.id)
                    pending.extend(self.bindings.get(node.id, ()))
        return False

    @staticmethod
    def _names(stmt: ast.stmt) -> tuple[str, ...]:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return (stmt.name,)
        targets = stmt.targets if isinstance(stmt, ast.Assign) else (
            [stmt.target] if isinstance(stmt, ast.AnnAssign) else [])
        if targets and all(isinstance(t, ast.Name) for t in targets):
            return tuple(t.id for t in targets)
        return ()

    def _text(self, stmt: ast.AST) -> str:
        start, end = _span(stmt)
        return "\n".join(self.source.splitlines()[start - 1:end])

    def _symbol(self, node: ast.AST | None) -> str:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return f"{self._symbol(node.value)}.{node.attr}"
        return ""

    def _references(self, stmt: ast.AST) -> set[str]:
        names = set()
        parents = {child: parent for parent in ast.walk(stmt) for child in ast.iter_child_nodes(parent)}
        reflective = {"getattr", "setattr", "hasattr", "delattr"}
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                names.add(node.id)
            if isinstance(node, ast.Attribute):
                # An attribute may address this module (for example through
                # sys.modules[__name__]). Until receiver identity rules it out,
                # retain that module binding; never search other classes by name.
                names.add(node.attr)
            if isinstance(node, (ast.Name, ast.Attribute)):
                symbol = self._symbol(node).removeprefix("builtins.")
                if symbol in {"globals", "locals", "vars", "eval", "exec", "__import__"} or (
                        symbol == "importlib" or symbol.startswith("importlib.")):
                    self.dynamic = True
                if symbol in reflective:
                    call = parents.get(node)
                    if not (isinstance(call, ast.Call) and call.func is node and len(call.args) > 1
                            and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str)):
                        self.dynamic = True
            if isinstance(node, ast.arg):
                # Fixture arguments are module bindings; unresolved local shadowing
                # cannot establish that a same-named binding is unrelated.
                names.add(node.arg)
            if isinstance(node, ast.Call):
                label = self._symbol(node.func).split(".")[-1]
                if label in reflective and len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    if isinstance(node.args[1].value, str):
                        names.add(node.args[1].value)
                if label == "usefixtures":
                    names.update(a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str))
                if label == "getfixturevalue":
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        names.add(node.args[0].value)
                    else:
                        self.dynamic = True
        return names

    def changed(self, old: _Support) -> list[str]:
        changed = []
        for keys in self.statements.keys() | old.statements.keys():
            if self.statements.get(keys) == old.statements.get(keys):
                continue
            if self.dynamic or old.dynamic or set(keys) & (self.reached | old.reached):
                changed.extend(keys)
        def ordered(support):
            result = []
            for stmt in support.tree.body:
                keys = self._names(stmt)
                if not keys or self.dynamic or old.dynamic or set(keys) & (self.reached | old.reached):
                    result.append((keys, support._text(stmt)))
            return result
        current_order, old_order = ordered(self), ordered(old)
        if current_order != old_order:
            # Relative order is part of executing support. Grouping statements
            # by binding alone would miss a constant initialized before/after a mutation.
            # If keyed text is unchanged, name only the top-level change rather
            # than attributing it to every retained binding (including the test).
            if ([self._text(s) for s in self.always] != [old._text(s) for s in old.always]
                    or not changed):
                changed.append("<top-level>")
        return sorted(set(changed))


class _History:
    """One provenance comparison owns source, declared assets and runner inputs."""

    def __init__(self, root: Path, contract: IBContract):
        self.root, self.contract = root, contract
        committed, self.origin = ib_origin(root, contract.rel_path)
        self.notes = [] if committed else [_UNCOMMITTED_NOTE]
        self.sources: dict[tuple[str, str], str | None] = {}
        self.file_changes: dict[str, bool] = {}
        self.support_cache: dict[str, list[str]] = {}
        self.runtime_support: dict[str, set[str]] = {}
        self.changes: dict[str, list[str]] = {}
        self.support_only: set[str] = set()
        self.old_files = ({p for p in _git(root, "ls-tree", "-r", "-z", "--name-only", self.origin).stdout.split("\0") if p}
                          if self.origin else set())
        self.files = {p for p in _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").stdout.split("\0") if p}

    def observe(self, report: dict[str, Any]) -> None:
        known = self.files | self.old_files
        for node, details in report.get("failures", {}).items():
            rel, _ = node_path(node)
            # Runtime discovery can see ignored installed packages inside the
            # checkout; history compares only repository content, as _modules does.
            self.runtime_support.setdefault(rel, set()).update(
                p for p in details.get("support_files", ()) if p in known)
            self.support_cache.pop(rel, None)

    def source(self, rel: str, old: bool = False) -> str | None:
        if old:
            return _source_at(self.root, self.origin, rel, self.sources) if self.origin else None
        key = ("", rel)
        if key not in self.sources:
            path = self.root / rel
            self.sources[key] = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
        return self.sources[key]

    def _different(self, rel: str) -> bool:
        if rel not in self.file_changes:
            old = git_reads.run(self.root, "show", f"{self.origin}:{rel}", capture_output=True)
            path = self.root / rel
            now = path.read_bytes() if path.is_file() else None
            self.file_changes[rel] = now != (old.stdout if old.returncode == 0 else None)
        return self.file_changes[rel]

    def _modules(self, source: str | None, rel: str, *, plugins: bool = False) -> set[str]:
        """Resolve explicit imports/declarations without importing repository code."""
        if source is None:
            return set()
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            return set()
        modules = acc.pytest_evidence._imported_modules(tree) if not plugins else set()
        if plugins:
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and "pytest_plugins" in _Support._names(node):
                    try:
                        value = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        continue
                    values = [value] if isinstance(value, str) else value
                    if isinstance(values, (list, tuple)):
                        modules.update((v, 0) for v in values if isinstance(v, str))
        out: set[str] = set()
        folder = Path(rel).parent
        for module, level in modules:
            if level:
                if level > len(folder.parts):
                    continue
                bases = [folder.parents[level - 2] if level > 1 else folder]
            else:
                bases = list(dict.fromkeys([folder, *folder.parents, Path("src")]))
            for base in bases:
                part = base / module.replace(".", "/")
                candidates = [part.with_suffix(".py"), part / "__init__.py"]
                found = {p.as_posix() for p in candidates if p.as_posix() in self.files | self.old_files}
                if found:
                    out.update(found)
                    break
        if plugins:
            return out
        return {p for p in out if acc.pytest_evidence._is_test_helper(self.root / p, self.root / rel, self.root)}

    def _fixture_files(self, rel: str) -> set[str]:
        """O-11(c)'s fixture modules, at both ends of the history comparison."""
        # Runtime discovery supplies computed plugin declarations and loaded
        # test helpers already admitted by O-11(c), never implementation code.
        paths = set(self.runtime_support.get(rel, ()))
        for old in (False, True):
            for parent in [Path(rel).parent, *Path(rel).parent.parents]:
                conftest = (parent / "conftest.py").as_posix()
                paths.add(conftest)
                paths.update(self._modules(self.source(conftest, old), conftest, plugins=True))
            paths.update(self._modules(self.source(rel, old), rel, plugins=True))
        return paths

    def _support_files(self, rel: str) -> set[str]:
        paths = self._fixture_files(rel)
        for old in (False, True):
            paths.update(self._modules(self.source(rel, old), rel))
        for asset in [*self.contract.declared_assets, *(p for c in self.contract.acceptance for p in (c.test_files or ()))]:
            asset = Path(asset).as_posix()
            directory = self.root / asset
            prefix = "" if asset == "." else asset + "/"
            descendants = {p for p in self.files | self.old_files if p.startswith(prefix)
                           and "__pycache__" not in Path(p).parts}
            if directory.is_dir():
                paths.update(p.relative_to(self.root).as_posix() for p in directory.rglob("*")
                             if p.is_file() and "__pycache__" not in p.parts)
            elif not descendants or directory.is_file():
                paths.add(asset)
            paths.update(descendants)
        return paths

    @staticmethod
    def _runner_section(filename: str, text: str | None):
        if text is None or filename in ("pytest.ini", ".pytest.ini", "pytest.toml"):
            return text
        if filename == "pyproject.toml":
            import tomllib
            try:
                return tomllib.loads(text).get("tool", {}).get("pytest")
            except tomllib.TOMLDecodeError:
                return text
        parser = configparser.ConfigParser(interpolation=None)
        section = "pytest" if filename == "tox.ini" else "tool:pytest"
        try:
            parser.read_string(text)
            return dict(parser.items(section)) if parser.has_section(section) else None
        except configparser.Error:
            return text

    def _support_changes(self, rel: str) -> list[str]:
        """Cache the complete O-11(c) comparison once per test file."""
        if rel in self.support_cache:
            return self.support_cache[rel]
        changed = [p for p in sorted(self._support_files(rel)) if self._different(p)]
        for parent in [Path(rel).parent, *Path(rel).parent.parents]:
            for filename in acc._CONFIG_CANDIDATES:
                path = (parent / filename).as_posix()
                if self._runner_section(filename, self.source(path)) != self._runner_section(filename, self.source(path, True)):
                    changed.append(path)
        import yaml
        def execution(text):
            try:
                data = yaml.safe_load(text or "") or {}
                return data.get("execution") if isinstance(data, dict) else None
            except yaml.YAMLError:
                return text
        config = ".dekspec/config.yaml"
        if execution(self.source(config)) != execution(self.source(config, True)):
            changed.append(config)
        self.support_cache[rel] = sorted(set(changed))
        return self.support_cache[rel]

    def classify(self, node: str) -> str:
        rel, names = node_path(node)
        now, then = self.source(rel), self.source(rel, True)
        if now is None or then is None:
            return "new"
        try:
            fixtures = self._fixture_files(rel)
            present = _Support(now, names, [source for path in sorted(fixtures)
                                           if (source := self.source(path)) is not None])
            past = _Support(then, names, [source for path in sorted(fixtures)
                                         if (source := self.source(path, True)) is not None])
        except (SyntaxError, ValueError):
            return "new"
        text = function_span(present.source, names)
        same_test = text is not None and text == function_span(past.source, names)
        changed = [f"{rel}::{name}" for name in present.changed(past)]
        changed += self._support_changes(rel)
        if same_test and changed:
            self.support_only.add(node)
            self.changes[node] = sorted(set(changed))
        return "preserved" if same_test and not changed else "new"

    def basis(self, node: str) -> list[dict[str, Any]] | str:
        rel, names = node_path(node)
        text = self.source(rel)
        return [] if text is None else declared_bases(text, names)


# ------------------------------------------------------------------ the report
def _contract(root: Path, ref: str, spec_root: str) -> IBContract:
    try:
        find_ib_path(root, ref, spec_root=spec_root)
    except ContractError as exc:
        raise UnknownIB(f"unknown IB {ref}: {exc}") from exc
    try:
        return load_contract(root, ref, spec_root=spec_root)
    except ContractError as exc:
        raise FloorError(str(exc)) from exc


def floor_digest(root: Path, contract: IBContract) -> str:
    """The digest `ib accept` / `ib baseline` would record for the current acceptance assets."""
    digest = acc.baseline_digest(acc.baseline_payload(root, contract))
    assert digest is not None
    return digest


def _collect_error_for(requested: str, report: dict[str, Any]) -> dict[str, Any] | None:
    """The collection error that kept ``requested`` from running: one in its
    own module (or an enclosing package or class), else the run's first — a
    collection error stops the whole pytest session, so a node that did not
    run beside one was not collected because collection failed."""
    file = pytest_node_file(requested).rstrip("/")
    errors = report.get("collect_errors", [])
    for err in errors:
        nodeid = (err.get("nodeid") or "").rstrip("/")
        if nodeid and (nodeid in (file, requested) or requested.startswith(nodeid + "::")
                       or file.startswith(nodeid + "/")):
            return err
    return errors[0] if errors else None


def _collect_failure_line(err: dict[str, Any], report: dict[str, Any]) -> str | None:
    info = (report.get("failures", {}).get(err.get("nodeid", "")) or {}).get("collect")
    if info:
        return info.get("failure_line")
    detail = (err.get("detail") or "").strip()
    return f"{err.get('nodeid')}:0: {detail.splitlines()[-1]}" if detail else None


def floor_report(repo_root: Path, ref: str, *, spec_root: str = "dekspec") -> dict[str, Any]:
    """The acceptance floor report for ``ref`` in the O-8 layout, plus the key
    ``_notes`` (notes for the human report; the CLI removes it from ``--json``)."""
    from dekspec.execution.settings import load_settings, resolve_python

    root = Path(repo_root).resolve()
    contract = _contract(root, ref, spec_root)
    if not contract.is_delegated:
        raise FloorError(f"{contract.ib_id} keeps the legacy authority policy: it has no delegated acceptance "
                         "contract, so there is no acceptance floor to report (adopt it first, ADR-055)")
    settings = load_settings(root, spec_root=spec_root)
    python = resolve_python(root, settings.python)
    history = _History(root, contract)
    notes = history.notes

    def entry(node: str, kind: str, failure_line: str | None) -> dict[str, Any]:
        return {"node": node, "class": history.classify(node), "kind": kind, "failure_line": failure_line,
                "basis": history.basis(node)}

    conditions = []
    for cond in contract.acceptance:
        if cond.kind != "pytest":
            conditions.append({"id": cond.id, "kind": cond.kind, "assessed": False, "nodes": []})
            continue
        run = acc.run_pytest_detail(root, cond, python=python, timeout=settings.command_timeout)
        report = run.get("report")
        if report is None:
            raise FloorError(f"{contract.ib_id} {cond.id}: the acceptance runner produced no report "
                             f"({run.get('detail', run.get('status'))})")
        history.observe(report)
        results, failures, captured = report["results"], report["failures"], report["captured"]
        nodes: list[dict[str, Any]] = []
        for requested in cond.nodes:
            matched = [nid for nid in results if acc._node_matches(requested, nid)]
            dropped = [d for d in report["deselected"] if acc._node_matches(requested, d)]
            for nid in matched:
                if nid in dropped:
                    continue
                kind = failure_kind(results[nid], failures.get(nid, {}), captured.get(nid, ""))
                info = failures.get(nid, {})
                line = None
                if kind not in ("passed", "skipped", "xfail"):
                    phase = next((p for p in ("setup", "call", "teardown") if results[nid].get(p) == "failed"), None)
                    line = (info.get(phase) or {}).get("failure_line") if phase else None
                nodes.append(entry(nid, kind, line))
            for nid in dropped:
                nodes.append(entry(nid, "deselected", None))
            if not matched and not dropped:
                err = _collect_error_for(requested, report)
                if err is not None:
                    nodes.append(entry(requested, "collection-error", _collect_failure_line(err, report)))
                else:
                    nodes.append(entry(requested, "not-collected", None))
        conditions.append({"id": cond.id, "kind": "pytest", "assessed": True, "nodes": nodes})

    command_problems = []
    gated = bool(contract.acceptance_asset_paths())
    if gated:
        for cond in contract.acceptance:
            if cond.kind != "command":
                continue
            if cond.test_files is None:
                command_problems.append(f"{cond.id} [command] test files not declared")
            else:
                command_problems.extend(f"{cond.id} [command] declared test file missing: {p}"
                                        for p in cond.test_files if not (root / p).exists())
    ok = not command_problems and all(_node_ok(n, n["node"] in history.support_only)
                                     for c in conditions for n in c["nodes"])
    return {"ib": contract.ib_id, "digest": floor_digest(root, contract), "ok": ok, "conditions": conditions,
            "_notes": notes, "_support": history.changes, "_command_problems": command_problems}


def _node_ok(node: dict[str, Any], support_only: bool = False) -> bool:
    """O-8: a new node is genuine red with a declared basis; a preserved node passes."""
    if node["class"] == "preserved":
        return node["kind"] == "passed"
    return (node["kind"] == GENUINE or (support_only and node["kind"] == "passed")) and _has_basis(node)


def _has_basis(node: dict[str, Any]) -> bool:
    return isinstance(node["basis"], list) and any(b["text"].strip() for b in node["basis"])


def _node_problem(node: dict[str, Any], support_only: bool = False) -> str | None:
    if node["class"] == "preserved":
        return None if node["kind"] == "passed" else "a preserved node must pass"
    problems = []
    if node["kind"] != GENUINE and not (support_only and node["kind"] == "passed"):
        problems.append("a new node must be genuine red")
    if node["basis"] == "unreadable":
        problems.append("the test file does not parse (basis unreadable)")
    elif not _has_basis(node):
        problems.append("no basis declared")
    return "; ".join(problems) or None


def floor_text(report: dict[str, Any]) -> str:
    """The human floor report."""
    assessed = [c for c in report["conditions"] if c["assessed"]]
    lines = [f"{report['ib']}: acceptance floor {'OK' if report['ok'] else 'NOT OK'}",
             f"  floor digest {report['digest']} (the digest `dekspec ib accept` / `ib baseline` records "
             "for these acceptance assets)"]
    if not assessed:
        status = "" if report["ok"] else "acceptance floor NOT OK; "
        lines[0] = f"{report['ib']}: {status}0 assessed — not red or green test evidence"
    lines += [f"  note: {n}" for n in report.get("_notes", [])]
    lines += [f"  {p}" for p in report.get("_command_problems", [])]
    for cond in report["conditions"]:
        if not cond["assessed"]:
            lines.append(f"  {cond['id']} [{cond['kind']}] not assessed")
            continue
        lines.append(f"  {cond['id']} [pytest] {len(cond['nodes'])} node(s)")
        for node in cond["nodes"]:
            lines.append(f"    {node['node']}  {node['class']}  {node['kind']}")
            if node["basis"] == "unreadable":
                lines.append("      basis: unreadable")
            elif node["basis"]:
                for b in node["basis"]:
                    lines.append(f"      basis{' (inherited)' if b['inherited'] else ''}: {b['text']}")
            else:
                lines.append("      basis: none declared")
            if node["failure_line"]:
                for i, text in enumerate(node["failure_line"].splitlines()):
                    lines.append(("      failure: " if i == 0 else "               ") + text)
            support = report.get("_support", {}).get(node["node"], [])
            if support:
                lines.append("      support changed: " + ", ".join(support))
            problem = _node_problem(node, bool(support))
            if problem:
                lines.append(f"      ! {problem}")
    lines.append(f"  {len(assessed)} assessed ({len(report['conditions'])} condition(s)); "
                 "command and review conditions are not assessed")
    return "\n".join(lines)
