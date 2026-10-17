"""pytest behind the adapter: the one place a lean check meets pytest (IB-292 O-10).

It reuses the runner DekSpec already had (``acceptance``: the evidence plugin,
the configuration pin and the bytecode cache) and the readings the floor
report already makes (``floor``: failure kinds, a test's span and bases), and
turns what they see into facts. For pytest every answer is the one DekSpec gave
before (BS-045 BR 68): the words of each evidence entry, the red check's
details, the closed and bound files, the interpreter.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path, PurePosixPath

from dekspec.execution import acceptance as acc
from dekspec.execution.contract import AcceptanceCondition
from dekspec.execution.floor import declared_bases, failure_kind, function_span, node_path
from dekspec.execution.settings import _has_pytest, resolve_python
from dekspec.execution.test_runners import Adapter, Outcome, Run, Skeleton, Source, Support


class PytestAdapter(Adapter):
    """pytest: tests are `<file>.py::<name>` node ids."""

    name = "pytest"
    test_files = "a file ending in .py"

    def file_of(self, test):
        file = test.split("::", 1)[0]
        return file if file.endswith(".py") else None

    def run(self, tests, *, project, settings, timeout, checkout=None):
        # The interpreter a caller gives runs as given, as before this adapter
        # (evidence records the command line); only an unset one is resolved.
        python = settings.python or resolve_python(project, None)
        root = Path(project)
        if checkout is not None:
            # The checkout is elsewhere: a repository-relative interpreter stays the project's.
            if not Path(python).is_absolute() and "/" in python:
                python = str(Path(project) / python)
            root = Path(checkout)
        condition = AcceptanceCondition("", "", self.name, nodes=tuple(tests))
        try:
            raw = acc._run_pytest(root, condition, python, timeout, detail=checkout is not None)
        except OSError as exc:
            if checkout is None:
                raise
            fault = f"interpreter {python}: {exc}"
            return Run(faults=(fault,), account=(fault,))
        if "report" not in raw:
            facts = {k: raw[k] for k in ("exit_code", "duration", "tail") if k in raw}
            return Run(faults=(raw["detail"],), account=(raw["detail"],),
                       failed=raw.get("status") == "failed", facts=facts)
        return _facts(tests, raw, root.resolve())

    def source(self, test, read):
        file, names = node_path(test)
        content = read(file)
        if content is None:
            return Source()
        text = content.decode("utf-8", "replace")
        span = function_span(text, names)
        if span is None:
            return Source()
        bases = declared_bases(text, names)
        return Source(span, tuple(b["text"] for b in bases) if isinstance(bases, list) else (),
                      _marked_xfail(text, names))

    def support(self, paths, read):
        closed, bound = set(), {}
        folders = {str(folder) for path in paths for folder in PurePosixPath(path).parents}
        for folder in sorted(folders):
            conftest = _join(folder, "conftest.py")
            closed.add(conftest)
            content = read(conftest)
            if content is not None:
                bound[conftest] = hashlib.sha256(content).hexdigest()
            for name in acc._CONFIG_CANDIDATES:
                content = read(_join(folder, name))
                text = acc._config_section(name, content) if content is not None else None
                if text is not None:
                    bound[_join(folder, name) + "#pytest"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return Support(frozenset(closed), dict(sorted(bound.items())))

    def skeleton(self, path, source):
        if not path.endswith(".py"):
            return None
        try:
            tree = ast.parse(source)
            return Skeleton(frozenset(_names(tree)), ast.get_docstring(tree) or "")
        except (SyntaxError, ValueError, TypeError) as exc:
            return Skeleton(problem=str(exc))

    def program(self, project, settings):
        return resolve_python(project, settings.python)

    def ready(self, project, settings):
        python = resolve_python(project, settings.python)
        if _has_pytest(python, Path(project)):
            return None
        return (f"pytest is not installed for the test interpreter {python} — "
                "set `execution.python` in .dekspec/config.yaml")


def _join(folder: str, name: str) -> str:
    return name if folder == "." else f"{folder}/{name}"


def _facts(tests, raw, root: Path) -> Run:
    """The plugin's report as facts, worded as pytest's evidence always was."""
    report, code = raw["report"], raw["exit_code"]
    results, failures, captured = report["results"], report["failures"], report["captured"]
    outcomes: list[Outcome] = []
    account: list[str] = []
    for requested in tests:
        matched = [nid for nid in results if acc._node_matches(requested, nid)]
        dropped = [d for d in report["deselected"] if acc._node_matches(requested, d)]
        if dropped:
            account.append(f"{requested}: {len(dropped)} case(s) deselected")
        outcomes.extend(Outcome(d, "deselected", ran=False, of=_case_of(requested, d)) for d in dropped)
        if not matched:
            if not dropped:
                if report["collect_errors"]:
                    account.append(f"{requested}: collection error")
                    outcomes.append(Outcome(requested, "collection-error (import/collection)", ran=False))
                else:
                    account.append(f"{requested}: not collected (missing, renamed or deleted)")
                    outcomes.append(Outcome(requested, "not-collected", ran=False))
            continue
        for nid in matched:
            phases = results[nid]
            seen = acc._node_outcome(phases)
            if seen != "passed":
                account.append(f"{nid}: {seen}")
            if seen == "not-run":
                outcomes.append(Outcome(nid, "not-collected", ran=False, of=_case_of(requested, nid)))
                continue
            result = seen
            if seen == "failed":
                result = failure_kind(phases, failures.get(nid, {}), captured.get(nid, ""))
                if result in ("passed", "skipped", "xfail", "not-collected"):
                    result = "setup-error"  # a later phase failed
            outcomes.append(Outcome(nid, result, of=_case_of(requested, nid)))
    # The process exit status is an independent witness: a report that says
    # "passed" from a run pytest itself calls failed is not evidence.
    failed = not account and code != 0
    if failed:
        account.append(f"pytest exited {code} although every requested node reported passed")
    faults = []
    if report["collect_errors"]:
        faults.append("collection-error (import/collection)")
    if code not in (0, 1):
        faults.append(f"pytest exit {code}")
    plugins = sorted(
        str(Path(f).resolve().relative_to(root)) for f in report["plugin_files"]
        if Path(f).resolve().is_relative_to(root) and Path(f).name != "conftest.py")
    facts = {"exit_code": code, "duration": raw["duration"], "collect_errors": report["collect_errors"][:5],
             "tail": raw["tail"] if account else ""}
    return Run(tuple(outcomes), faults=tuple(faults), account=tuple(account), failed=failed,
               plugins=tuple(plugins), facts=facts)


def _case_of(requested: str, nid: str) -> str:
    return "" if nid == requested else requested


def _names(tree: ast.Module) -> set[str]:
    """A module's public names: its `__all__` when literal, else its public
    top-level definitions and assignments, plus the public members of each
    public class as `Class.member`."""

    def declared(body):
        names = set()
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        return {n for n in names if not n.startswith("_")}

    names = declared(tree.body)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                try:
                    exports = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(exports, (list, tuple)) and all(isinstance(n, str) for n in exports):
                    names = set(exports)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in names:
            names |= {node.name + "." + n for n in declared(node.body)}
    return names


def _marked_xfail(source: str, names: list[str]) -> bool:
    """A disabled xfail marker is still forbidden on an acceptance node."""
    try:
        body = ast.parse(source).body
    except (SyntaxError, ValueError):
        return False
    markers = []
    for name in [*names, None]:
        for node in body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets):
                    markers.append(node.value)
        selected = next((n for n in body if isinstance(
            n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name), None)
        if selected is None:
            break
        markers.extend(selected.decorator_list)
        body = selected.body if isinstance(selected, ast.ClassDef) else []
    return any(isinstance(n, ast.Attribute) and n.attr == "xfail"
               for marker in markers if marker is not None for n in ast.walk(marker))
