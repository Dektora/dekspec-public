"""pytest plugin: record what actually happened to each test node.

The acceptance runner stages this file as the standalone module
``dekspec_pytest_evidence`` (so it must stay stdlib-only) and loads it with
``-p dekspec_pytest_evidence`` and ``DEKSPEC_EVIDENCE_REPORT=<path>``. It writes the collected node ids,
deselected node ids, collection errors and per-phase outcomes, so the runner
can tell *passed* apart from skipped, expected-failure, deselected or never
collected — a green process exit alone cannot.

It also records *why* a node failed (ADR-062): per failing phase the
exception's type (from the exception info, never parsed from a message),
whether it is assertion-class, the failure's own message chain and the
failure line, plus the node's captured output — so the floor report can
tell a genuine red from a usage, import or setup failure. These fields are
additive; the ones above keep their meaning. They are capped in length unless
``DEKSPEC_EVIDENCE_FULL=1`` (the floor's detail run), which records the message
chain and the captured output in full, so a signature is never cut off
(IB-143 O-2). The failure line, a display field, stays capped.
"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
import json
import os
import sys
from pathlib import Path
from typing import Any

_state: dict[str, Any] = {"collected": [], "deselected": [], "collect_errors": [], "results": {},
                          "failures": {}, "captured": {}}

_MESSAGE_CHARS = 4000
_CAPTURE_CHARS = 20000


def _full() -> bool:
    return os.environ.get("DEKSPEC_EVIDENCE_FULL") == "1"


def pytest_collection_modifyitems(session, config, items):  # noqa: ARG001
    _state["collected"] = [item.nodeid for item in items]


def pytest_deselected(items):
    _state["deselected"].extend(item.nodeid for item in items)


def pytest_collectreport(report):
    if report.failed:
        _state["collect_errors"].append({"nodeid": report.nodeid, "detail": str(report.longrepr)[-800:]})


def _root(config) -> str:
    return str(getattr(config, "rootpath", None) or config.rootdir)


def _rel(path: str, root: str) -> str:
    try:
        rel = os.path.relpath(path, root)
    except ValueError:  # pragma: no cover - another drive on Windows
        return path
    return path if rel.startswith("..") else rel.replace(os.sep, "/")


def _message_chain(value: BaseException, first: str) -> str:
    """The failure's own message, followed by its causes and contexts."""
    parts = [first]
    seen = {id(value)}
    cur = value.__cause__ or value.__context__
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        parts.append(f"{type(cur).__name__}: {cur}")
        cur = cur.__cause__ or cur.__context__
    chain = "\n".join(parts)
    return chain if _full() else chain[:_MESSAGE_CHARS]


def _is_test_helper(path: Path, own_file: Path, root: Path) -> bool:
    """O-11(c)'s location boundary; being repository code alone is insufficient."""
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return path.resolve().parent == own_file.resolve().parent or bool({"test", "tests"} & set(relative.parts[:-1]))


def _imported_modules(tree: ast.AST) -> set[tuple[str, int]]:
    """Read direct imports and literal import calls, including parent packages.

    Shared by history and runtime provenance; this never imports user code.
    Relative levels stay attached until each caller resolves its own context.
    """
    modules: set[tuple[str, int]] = set()
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update((a.name, 0) for a in node.names)
            aliases.update((a.asname or a.name.split(".")[0],
                            a.name if a.asname else a.name.split(".")[0]) for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add((node.module or "", node.level))
            modules.update((".".join(filter(None, (node.module, a.name))), node.level)
                           for a in node.names if a.name != "*")
            if not node.level:
                aliases.update((a.asname or a.name, f"{node.module}.{a.name}") for a in node.names)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = node.func
        suffix = []
        while isinstance(name, ast.Attribute):
            suffix.insert(0, name.attr)
            name = name.value
        if not isinstance(name, ast.Name):
            continue
        symbol = ".".join([aliases.get(name.id, name.id), *suffix])
        if symbol not in {"importlib.import_module", "__import__", "pytest.importorskip"}:
            continue
        literal = node.args[0]
        if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
            module = literal.value
            if module.startswith(".") and symbol == "importlib.import_module":
                package = (node.args[1] if len(node.args) > 1 else
                           next((kw.value for kw in node.keywords if kw.arg == "package"), None))
                if isinstance(package, ast.Constant) and isinstance(package.value, str):
                    try:
                        module = resolve_name(module, package.value)
                    except ImportError:
                        continue
            if module and not module.startswith("."):
                modules.add((module, 0))
    parents = set(modules)
    for module, level in modules:
        parts = module.split(".")
        parents.update((".".join(parts[:i]), level) for i in range(1, len(parts)))
        if level:
            parents.add(("", level))
    return parents


def _test_helpers(own_file: str | None, root: str) -> set[str]:
    """Only modules explicitly imported by this test file qualify as helpers."""
    if not own_file:
        return set()
    try:
        tree = ast.parse(Path(own_file).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return set()
    names = set()
    own_module = next((m for m in list(sys.modules.values())
                       if getattr(m, "__file__", None) == own_file), None)
    package = getattr(own_module, "__package__", "") or ""
    for module, level in _imported_modules(tree):
        prefix = module
        if level:
            parts = package.split(".")
            prefix = ".".join([*parts[:len(parts) - level + 1], *([module] if module else [])])
        # Resolving a relative import also imports its absolute parent packages.
        parts = prefix.split(".")
        names.update(".".join(parts[:i]) for i in range(1, len(parts) + 1))
    paths = set()
    for name in names:
        path = getattr(sys.modules.get(name), "__file__", None)
        if path and _is_test_helper(Path(path), Path(own_file), Path(root)):
            paths.add(os.path.abspath(path))
    return paths


def _failure(excinfo, own_file: str | None, root: str) -> dict[str, Any]:
    """Type, assertion class, message chain and failure line of one exception."""
    etype = excinfo.type
    try:
        first = excinfo.exconly().strip()
    except Exception:  # noqa: BLE001 - a broken __str__ must not lose the record
        first = etype.__name__
    first = first or etype.__name__
    # The failing line: the last frame in the node's own file, else the raising frame.
    frames = []
    tb = excinfo.tb
    while tb is not None:
        frames.append((os.path.abspath(tb.tb_frame.f_code.co_filename), tb.tb_lineno))
        tb = tb.tb_next
    framework = getattr(sys.modules.get("_pytest"), "__file__", None)
    framework_dir = os.path.dirname(os.path.abspath(framework)) + os.sep if framework else None
    raising = next((f for f in reversed(frames) if not framework_dir or not f[0].startswith(framework_dir)), None)
    test_owned = bool(raising and (raising[0] == own_file or raising[0] in _test_helpers(own_file, root)))
    own = [f for f in frames if own_file and f[0] == own_file]
    where = (own or frames or [(own_file or "?", 0)])[-1]
    # pytest's own failure outcome (`pytest.fail`, "DID NOT RAISE"); it reports itself as a builtin.
    is_failed_outcome = etype.__name__ == "Failed" and any(b.__name__ == "OutcomeException" for b in etype.__mro__)
    return {
        "type": etype.__name__,
        "assertion": bool(issubclass(etype, AssertionError) or is_failed_outcome),
        "test_assertion": test_owned,
        "raising_line": f"{_rel(raising[0], root)}:{raising[1]}" if raising else None,
        "message": _message_chain(excinfo.value, first),
        "failure_line": f"{_rel(where[0], root)}:{where[1]}: {first}"[:_MESSAGE_CHARS],
    }


def _own_file(node) -> str | None:
    path = getattr(node, "path", None) or getattr(node, "fspath", None)
    return os.path.abspath(str(path)) if path else None


def pytest_runtest_makereport(item, call):
    # Observes only: returns None so pytest's own report is built as usual.
    if call.excinfo is None or call.excinfo.type.__name__ in ("Skipped", "XFailed"):
        return None
    failures = _state["failures"].setdefault(item.nodeid, {})
    if call.when not in failures:
        failures[call.when] = _failure(call.excinfo, _own_file(item), _root(item.config))
    return None


def pytest_exception_interact(node, call, report):  # noqa: ARG001
    # Collection errors: the collector's exception, with the line that raised it.
    if getattr(report, "when", None) == "collect":
        _state["failures"].setdefault(node.nodeid, {}).setdefault(
            "collect", _failure(call.excinfo, _own_file(node), _root(node.config)))


_RANK = {"passed": 0, "skipped": 1, "xpass": 2, "xfail": 2, "failed": 3}


def pytest_runtest_logreport(report):
    entry = _state["results"].setdefault(report.nodeid, {})
    outcome = report.outcome
    if getattr(report, "wasxfail", None) is not None:
        outcome = "xfail" if report.outcome == "skipped" else "xpass"
    # A phase can report more than once (e.g. unittest subtests); the worst
    # outcome wins, so a later passing report never hides a failure.
    previous = entry.get(report.when)
    if previous is None or _RANK.get(outcome, 3) > _RANK.get(previous, 3):
        entry[report.when] = outcome
    captured = "\n".join(content for title, content in getattr(report, "sections", ())
                         if title.startswith("Captured std"))
    if captured:
        _state["captured"][report.nodeid] = captured if _full() else captured[-_CAPTURE_CHARS:]


def _runtime_support(item, root: str) -> list[str]:
    """Resolve declared plugins and direct test imports through Python's loaded modules.

    This supplements the floor's history resolver for runner-specific import
    paths and computed pytest_plugins declarations; unrelated loaded modules
    never become support merely because they were loaded.
    """
    own = _own_file(item)
    if own is None:
        return []
    paths = _test_helpers(own, root)
    declarations = {own}
    folder = Path(own).parent
    while folder == Path(root) or Path(root) in folder.parents:
        declarations.add(str(folder / "conftest.py"))
        folder = folder.parent
    for module in list(sys.modules.values()):
        file = getattr(module, "__file__", None)
        if not file or os.path.abspath(file) not in declarations:
            continue
        plugins = getattr(module, "pytest_plugins", ())
        if isinstance(plugins, str):
            plugins = [plugins]
        if not isinstance(plugins, (list, tuple)):
            continue
        for name in plugins:
            path = getattr(sys.modules.get(name), "__file__", None) if isinstance(name, str) else None
            if path and Path(root) in Path(path).resolve().parents:
                paths.add(os.path.abspath(path))
    return sorted(_rel(path, root) for path in paths)


def pytest_sessionfinish(session, exitstatus):
    target = os.environ.get("DEKSPEC_EVIDENCE_REPORT")
    if not target:
        return
    _state["exitstatus"] = int(exitstatus)
    # The existing detail transport carries the per-node details map, but not
    # arbitrary report keys. Keep provenance alongside (not inside) phase
    # failures so the runner's outcomes and transport stay unchanged.
    for item in session.items:
        _state["failures"].setdefault(item.nodeid, {})["support_files"] = _runtime_support(item, _root(session.config))
    files = set()
    for plugin in session.config.pluginmanager.get_plugins():
        path = getattr(plugin, "__file__", None)
        if path:
            files.add(os.path.abspath(path))
    _state["plugin_files"] = sorted(files)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(_state, fh)
