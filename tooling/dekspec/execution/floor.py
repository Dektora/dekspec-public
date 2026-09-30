"""`dekspec ib floor` — the acceptance floor report (ADR-062, IB-137).

A read-only report that joins, for each `pytest:` acceptance condition of a
delegated IB, its test nodes with

* whether each node is **new** or **preserves** behavior that predates the IB
  (read from history: the node's test function, decorators included, is
  textually identical at the parent of the commit that first added the IB
  file, renames followed);
* its **failure kind** — `genuine-red` only for an assertion-class failure of
  the call phase whose own message and captured output carry no usage or
  import signature; every other outcome is reported with its kind;
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
import io
import re
import subprocess
import tokenize
from pathlib import Path
from typing import Any

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
        if info.get("assertion"):
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
        if entry not in bases:
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
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)


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
    committed, origin = ib_origin(root, contract.rel_path)
    notes = [] if committed else [_UNCOMMITTED_NOTE]
    sources: dict[tuple[str, str], str | None] = {}

    def current(rel: str) -> str | None:
        key = ("", rel)
        if key not in sources:
            path = root / rel
            sources[key] = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
        return sources[key]

    def classify(node: str) -> str:
        if origin is None:
            return "new"
        rel, names = node_path(node)
        now, then = current(rel), _source_at(root, origin, rel, sources)
        if now is None or then is None:
            return "new"
        span_now = function_span(now, names)
        return "preserved" if span_now is not None and span_now == function_span(then, names) else "new"

    def basis(node: str) -> list[dict[str, Any]] | str:
        rel, names = node_path(node)
        text = current(rel)
        return [] if text is None else declared_bases(text, names)

    def entry(node: str, kind: str, failure_line: str | None) -> dict[str, Any]:
        return {"node": node, "class": classify(node), "kind": kind, "failure_line": failure_line,
                "basis": basis(node)}

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

    ok = all(_node_ok(n) for c in conditions for n in c["nodes"])
    return {"ib": contract.ib_id, "digest": floor_digest(root, contract), "ok": ok, "conditions": conditions,
            "_notes": notes}


def _node_ok(node: dict[str, Any]) -> bool:
    """O-8: a new node is genuine red with a declared basis; a preserved node passes."""
    if node["class"] == "preserved":
        return node["kind"] == "passed"
    return node["kind"] == GENUINE and isinstance(node["basis"], list) and bool(node["basis"])


def _node_problem(node: dict[str, Any]) -> str | None:
    if node["class"] == "preserved":
        return None if node["kind"] == "passed" else "a preserved node must pass"
    problems = []
    if node["kind"] != GENUINE:
        problems.append("a new node must be genuine red")
    if node["basis"] == "unreadable":
        problems.append("the test file does not parse (basis unreadable)")
    elif not node["basis"]:
        problems.append("no basis declared")
    return "; ".join(problems) or None


def floor_text(report: dict[str, Any]) -> str:
    """The human floor report."""
    assessed = [c for c in report["conditions"] if c["assessed"]]
    lines = [f"{report['ib']}: acceptance floor {'OK' if report['ok'] else 'NOT OK'}",
             f"  floor digest {report['digest']} (the digest `dekspec ib accept` / `ib baseline` records "
             "for these acceptance assets)"]
    lines += [f"  note: {n}" for n in report.get("_notes", [])]
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
            problem = _node_problem(node)
            if problem:
                lines.append(f"      ! {problem}")
    lines.append(f"  {len(assessed)} assessed ({len(report['conditions'])} condition(s)); "
                 "command and review conditions are not assessed")
    return "\n".join(lines)
