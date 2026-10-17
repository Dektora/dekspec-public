"""vitest behind IB-292's Adapter: hides how vitest is started and with which configuration, its report, how a test's name is matched, how it marks skipped, pending, expected-failure and retried tests, which files configure and set it up, and what keeps a run clean (no caller environment that makes it load other code, no cached transform, no runner the delivery could rewrite).
Public: VitestAdapter, registered with pytest's from the start and after it (runners() begins pytest, vitest), so a condition names tests as `vitest: [...]`; a test is `<file> > <group> > ... > <name>` (the groups around it, then its own name, as `vitest list` prints it) and a file alone names every test in it. The configuration is the repository-relative file the project states as `execution.vitest_config` in .dekspec/config.yaml (ExecutionSettings.vitest_config), else vitest's default lookup from the project root, never the test file's folder.
Callers never know vitest's command line, report, configuration format or marks, or that the tests are TypeScript: file_of judges a file by its name alone (a JavaScript or TypeScript source file), never running vitest; run reports each named test, by that name, as "passed" only when it ran and passed the first time, "skipped" when skipped or pending, "xfail" under any expected-failure mark, "failed" when it ran and failed, a word that is not a pass for a pass only on a retry, and as not run (ran False) when filtered out by name, excluded by the configuration, not found or sharing its full name with another test of its file; support closes and binds every file that can change which named tests run or what they report (the configuration in effect, its setup and other loaded files, each configuration file that would take effect if added, and any file it cannot rule out), never package.json or a lockfile; program names node and vitest; ready says why vitest cannot run here.
Designed away: vitest's exit code and its own "passed" never make a pass; a runner that cannot run here (no Node, vitest's packages not installed, a node or vitest that is repository content) gives a run with no outcome and one fault naming vitest and the reason, so evidence is indeterminate, never passed or failed; a named test vitest did not run is an outcome, never an error. Source reads test identity and bases; run with a checkout prepares its dependencies and classifies assertion provenance. Uncertain answers refuse.
Alternatives: a `configuration` parameter on Adapter.run and Adapter.support (every caller would carry vitest's configuration); a NotBuilt error type in test_runners (callers would need a second handler, where CannotAnswer already fails the check that asked); a per-runner settings map or a runner-neutral `test_config` for the statement (more structure for one value, or ambiguous when a brief names two runners). IB-292's Adapter unchanged, with one flat `execution.vitest_config` like `execution.python`, won: no caller changes, and support reads the statement through ``read`` at the revision it is asked about.

IB-294 interface design (before tests): keep VitestAdapter.run/source/support; no new public names. The built extension hides failure provenance, TypeScript source identity/bases and clean-checkout preparation. Run keeps preparation faults separate from outcomes, Source.text=None means new while unambiguous attached bases survive, and support retains conservative closure; IB-296 supplies skeleton reading.
Callers never know TypeScript syntax, vitest errors or dependency locations. execution.vitest_install optionally supplies a checkout install command; otherwise the committed lockfile selects the frozen install. No working-tree dependency is borrowed. Missing Node/runner/transform dependencies and unreadable configuration remain named refusals, never test results.
Alternatives: expose parser/classifier/installer steps (leaks ordering and syntax), or add a vitest gate (duplicates policy). Existing fact-reporting Adapter wins: no new caller protocol. The IB-294 implementation below supplies these answers.

IB-296 design: skeleton(path, source) hides exports, class visibility, comments and parsing.
Its existing Skeleton answer holds import-facing names, note and problem; None means unsupported language only.
Callers need no syntax tree, parser lifecycle or export-form switch; source is never executed.
Empty names/no note are normal values; invalid source and unlisted star re-exports remain problems, never unchecked successes.
Alternatives: separate queries or a parser session leak assembly or lifecycle; the existing single question keeps callers simplest.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path

from dekspec.execution.engine import ExecutionError
from dekspec.execution.test_runners import Adapter, CannotAnswer, Outcome, Run, Source, Support, _protected_paths
from dekspec.execution.test_runners import Skeleton as _Skeleton

#: The extensions of a JavaScript or TypeScript source file (vitest's own test files).
_SOURCES = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")
#: vitest 4's default configuration files, in the order it looks for them in the root.
_CONFIGS = tuple(name + ext for name in ("vitest.config", "vite.config")
                 for ext in (".ts", ".mts", ".cts", ".js", ".mjs", ".cjs"))
#: Files read beside the tests whatever the configuration says: the TypeScript
#: options vite transforms each file under (per folder, as conftest.py is for
#: pytest), and the environment files vite loads in vitest's `test` mode.
_FOLDER_FILES = ("tsconfig.json",)
_ROOT_FILES = (".env", ".env.local", ".env.test", ".env.test.local")
#: Caller environment that would make node or vitest load other code.
_ENV_DROP_PREFIXES = ("NODE_", "VITE")
#: How a module path without its extension is completed.
_COMPLETIONS = ("", *_SOURCES, ".json", *(f"/index{ext}" for ext in _SOURCES))
_COMPILED = ((".js", ".ts"), (".mjs", ".mts"), (".cjs", ".cts"), (".jsx", ".tsx"))
_TAIL_CHARS = 4000
#: The options whose values are files vitest loads (`projects` names
#: configuration files, folders whose configuration files it loads, or
#: inline project configurations).
_LOADING_KEYS = frozenset(("setupFiles", "globalSetup", "snapshotSerializers", "customProviderModule", "projects"))
#: The options whose value may name a module vitest loads, or a built-in or
#: installed one by name: a value naming a repository source file is followed.
_NAMING_KEYS = frozenset(("runner", "environment", "pool", "diff", "snapshotEnvironment", "reporters"))
#: The keys an inline project may not set: they move what its paths mean.
_MOVING_KEYS = frozenset(("root", "dir"))
#: The package list (a manifest or a lockfile): never a support file, even
#: when a loaded module names it; a change to it is bound through the diff.
_PACKAGE_LISTS = frozenset(("package.json", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml",
                            "yarn.lock", "bun.lock", "bun.lockb"))
#: vitest's own loaders, called as `vi.importActual(...)` / `vi.importMock(...)`,
#: and its mocks, `vi.mock(...)` / `vi.doMock(...)`, which load a module or its
#: __mocks__ file in its place.
_VI_LOADERS = frozenset(("importActual", "importMock"))
_VI_MOCKS = frozenset(("mock", "doMock"))
#: Names that can load code, vitest's mocks and vi itself: reached through a
#: quoted member (`x["doMock"]`) they are refused.
_LOADER_WORDS = frozenset(("require", "import", "createRequire", "importActual", "importMock", "eval",
                           *_VI_MOCKS, "vi"))
#: The import.meta properties that load nothing.
_META = frozenset(("url", "dirname", "filename", "env", "resolve", "main", "hot", "vitest"))
#: Node modules that run code they are given; and the module system's own,
#: of which only these names load nothing.
_EVALUATING = frozenset(("vm", "node:vm"))
_MODULE_API = frozenset(("module", "node:module"))
_MODULE_SAFE = frozenset(("createRequire", "isBuiltin", "builtinModules"))
#: Characters that make a module name a pattern or a computed path, not a file
#: (a `projects` entry is also a pattern when it holds any of "()!").
_NOT_PLAIN = "*?{}[]$<>|"
#: The longest quoted text read as a path.
_LONGEST_PATH = 300
#: The tokenizer's pieces: a name, a number, white space.
_NAME = re.compile(r"[A-Za-z_$\u0080-￿][\w$\u0080-￿]*")
_NUMBER = re.compile(r"\d[\w.]*")
_SPACE = re.compile(r"\s+")
#: Words after which a "/" starts a regular expression, not a division.
_BEFORE_REGEX = frozenset(
    "return typeof case do else in of new delete void throw instanceof yield await".split())
#: A name npm can publish (an alias such as "@/x" or "~/x" is not one).
_PACKAGE_NAME = re.compile(r"^(?:@[a-z0-9-][a-z0-9-._]*/)?[a-z0-9-][a-z0-9-._]*$", re.IGNORECASE)
#: Node's own modules, importable without the "node:" prefix.
_BUILTINS = frozenset(
    "assert async_hooks buffer child_process cluster console constants crypto dgram diagnostics_channel dns "
    "domain events fs http http2 https inspector module net os path perf_hooks process punycode querystring "
    "readline repl stream string_decoder sys timers tls trace_events tty url util v8 vm wasi worker_threads "
    "zlib".split())


class VitestAdapter(Adapter):
    """vitest: a test is `<file> > <groups...> > <name>`, or a file alone."""

    name = "vitest"
    test_files = "a JavaScript or TypeScript source file (.js, .jsx, .mjs, .cjs, .ts, .tsx, .mts or .cts)"

    def skeleton(self, path, source):
        """Hide export forms, class visibility, leading comments and parsing.
        Public skeleton(path, source) returns Skeleton(names, note, problem),
        or None only for an unsupported language; callers need no syntax rules.
        Empty exports/no note are values; unreadable source and unlisted star
        re-exports are problems, never empty successes. Source is never executed.
        Alternatives: separate queries or a parser session; one answer hides both.
        """
        if not path.endswith(_SOURCES):
            return None
        try:
            text = source.decode("utf-8-sig")
            reader = _SkeletonReader(text)
            return _Skeleton(frozenset(reader._names()), reader._note())
        except (UnicodeError, ValueError, RecursionError) as exc:
            return _Skeleton(problem=f"cannot read {path}: {exc}")

    def file_of(self, test):
        """The text before the first " > " (all of ``test`` when there is
        none) when its name ends in a JavaScript or TypeScript extension;
        None for a directory or any other file. Never runs vitest: whether
        the configuration includes the file is found when the test runs."""
        file = test.split(" > ", 1)[0]
        name = file.rsplit("/", 1)[-1]
        return file if name.endswith(_SOURCES) and name not in _SOURCES else None

    def run(self, tests, *, project, settings, timeout, checkout=None):
        """Run exactly the named tests once, in the project's working tree,
        under the stated or default configuration, and report them as the
        module note says; a file alone gives one outcome per test in it,
        whose ``of`` is the file. Nothing from the caller's environment
        that would make vitest load other code reaches it, and no cached
        transform stands in for source. A checkout installs its own declared
        dependencies first; preparation faults report no test outcomes."""
        if checkout is not None:
            project = Path(checkout).resolve()
            fault = _prepare(project, settings.vitest_install, timeout)
            if fault:
                return Run(faults=(fault,), account=(fault,))
        project = Path(project).resolve()
        found = _find(project, judge=checkout is None)
        if checkout is not None and isinstance(found, _Found) and (
                not found.package.resolve().is_relative_to(project) or not found.entry.is_relative_to(project)):
            found = _Fault("checkout dependencies resolve outside the checkout; borrowed packages are refused")
        config = _configuration(project, settings.vitest_config)
        for fault in (found, config):
            if isinstance(fault, _Fault):
                fault = f"vitest cannot run here: {fault.reason}"
                return Run(faults=(fault,), account=(fault,))
        named = _named(tests)
        with tempfile.TemporaryDirectory(prefix="dekspec-vitest-") as temp:
            scratch = Path(temp)
            (scratch / "driver.mjs").write_text(_DRIVER, encoding="utf-8")
            (scratch / "input.json").write_text(json.dumps({
                "root": str(project), "entry": str(found.entry), "config": config,
                "cache": str(scratch / "cache"), "output": str(scratch / "report.json"),
                "names": {file: (None if parts is None else [list(p) for p in parts])
                          for file, parts in named.items()},
            }), encoding="utf-8")
            started = time.monotonic()
            try:
                exit_code, output, timed_out = _execute(
                    [found.node, str(scratch / "driver.mjs"), str(scratch / "input.json")], project, timeout)
            except OSError as exc:
                fault = f"vitest cannot start: {exc}"
                return Run(faults=(fault,), account=(fault,))
            duration = round(time.monotonic() - started, 2)
            report_path = scratch / "report.json"
            try:
                report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
                if report is not None and not isinstance(report, dict):
                    raise ValueError("report is not an object")
            except (OSError, ValueError) as exc:
                fault = f"vitest report unreadable: {exc}"
                return Run(faults=(fault,), account=(fault,))
        tail = output[-_TAIL_CHARS:]
        if timed_out:
            fault = f"vitest timed out after {timeout}s"
            return Run(faults=(fault,), account=(fault,), failed=True,
                       facts={"duration": duration, "tail": tail})
        if report is None:
            fault = f"vitest under {found.node} exited {exit_code} without a report"
            return Run(faults=(fault,), account=(fault,), facts={"exit_code": exit_code, "tail": tail})
        return _facts(project, named, report, exit_code, duration, tail)

    def source(self, test, read):
        """Read one test without project packages; ambiguous identity is new.

        Only comments inside or immediately above its declaration supply bases.
        Unknown syntax never proves sameness.
        """
        file = self.file_of(test)
        content = _optional(read, file) if file else None
        if content is None:
            return Source()
        return _source(test, content.decode("utf-8", "replace"))

    def support(self, paths, read):
        """The files that steer the tests in ``paths``, read through
        ``read`` at its revision, including the project's statement in
        .dekspec/config.yaml: ``closed`` lists them, present or not;
        ``bound`` maps each present one to its content digest."""
        closed: set[str] = set()
        bound: dict[str, str] = {}

        def take(path: str, content: bytes | None) -> None:
            closed.add(path)
            if content is not None:
                bound[path] = hashlib.sha256(content).hexdigest()

        stated = _stated(read)
        effective = stated
        if stated is not None:
            take(stated, read(stated))
        else:
            for name in _CONFIGS:  # each would take effect if added before the one in effect
                content = read(name)
                take(name, content)
                if content is not None and effective is None:
                    effective = name
        for name in _ROOT_FILES:
            take(name, _optional(read, name))
        starts: dict[str, bytes] = {}
        for folder in sorted({f for path in paths for f in _folders(path)}):
            for name in _FOLDER_FILES:
                file = name if folder == "." else f"{folder}/{name}"
                content = _optional(read, file)
                take(file, content)
                if content is not None:
                    starts[file] = content
        if effective is not None and effective in bound:
            starts[effective] = read(effective)
        for path, content in _loaded(starts, read):
            take(path, content)
        return Support(frozenset(closed), dict(sorted(bound.items())))

    def program(self, project, settings):
        """The node and the vitest that run the tests, by path and version."""
        found = _find(Path(project).resolve(), judge=False)
        if isinstance(found, _Fault):
            return f"node and vitest unavailable: {found.reason}"
        return f"node {found.node} ({found.node_version}); vitest {found.package} ({found.version})"

    def ready(self, project, settings):
        """None when vitest can run in ``project``; else why not, naming
        what is missing (Node, or vitest's packages) or refused."""
        found = _find(Path(project).resolve())
        return found.reason if isinstance(found, _Fault) else None


@_protected_paths.register(VitestAdapter)
def _vitest_protected(adapter, paths, read):
    """The package list stays open even when the test author changed it."""
    return {p for p in paths if posixpath.basename(p) not in _PACKAGE_LISTS} | set(adapter.support(paths, read).closed)


def _prepare(project: Path, statement: str | None, timeout: int) -> str | None:
    """Install only this checkout's dependencies; a problem is never a test result."""
    if shutil.which("node") is None:
        return "vitest checkout preparation: Node is missing (no node on PATH)"
    if statement:
        command = ["/bin/sh", "-c", statement]
    else:
        choices = [("npm", ("package-lock.json", "npm-shrinkwrap.json"), ["npm", "ci"]),
                   ("pnpm", ("pnpm-lock.yaml",), ["pnpm", "install", "--frozen-lockfile"]),
                   ("yarn", ("yarn.lock",), ["yarn", "install", "--frozen-lockfile"])]
        found = [(manager, cmd) for manager, locks, cmd in choices
                 if any((project / lock).is_file() for lock in locks)]
        if len(found) != 1:
            return ("vitest checkout preparation: cannot choose a package manager from the committed lockfile; "
                    "state execution.vitest_install (required for other managers or conflicting lockfiles)")
        manager, command = found[0]
        declared = _json((project / "package.json").read_bytes() if (project / "package.json").is_file() else None)
        named = str(declared.get("packageManager", "")).split("@", 1)[0]
        if named and named != manager:
            return f"vitest checkout preparation: package manager {named} needs execution.vitest_install"
        if shutil.which(manager) is None:
            return f"vitest checkout preparation: package manager {manager} is missing on PATH"
    try:
        code, output, timed_out = _execute(command, project, timeout)
    except OSError as exc:
        return f"vitest checkout preparation: dependency installation cannot start: {exc}"
    if timed_out or code:
        reason = f"timeout after {timeout}s" if timed_out else f"exit {code}"
        return f"vitest checkout preparation: dependency installation failed ({reason}): {output[-1500:].strip()}"
    return None


@dataclass(frozen=True)
class _TestSource:
    """A lexical test declaration, its enclosing names and callback extent.

    Unknown/computed identities carry None; their comments may still be attached
    unambiguously. Offsets also let reported stack locations prove provenance.
    """

    names: tuple[str, ...] | None
    start: int
    end: int
    body_start: int
    body_end: int
    marked: bool


def _declarations(text: str) -> tuple[tuple[_Token, ...], list[_TestSource]]:
    """Read the common direct it/test/describe syntax with the bundled lexer.

    This is deliberately not a TypeScript evaluator. Calls hidden in functions,
    computed groups and parameterized declarations cannot prove static identity.
    """
    tokens = _tokens(text)
    declarations = []

    def walk(lo, hi, groups=(), direct=True, inherited_mark=False):
        at = lo
        while at < hi:
            token = tokens[at]
            if token.kind == "name" and token.text in ("it", "test", "describe", "suite") and not _is(tokens, at - 1, "."):
                start, opening = at, at + 1
                marks = []
                while _is(tokens, opening, ".") and opening + 1 < hi:
                    marks.append(tokens[opening + 1].text)
                    opening += 2
                if not _is(tokens, opening, "("):
                    at += 1
                    continue
                end = _closing(tokens, opening)
                # each()/for() and conditional modifiers have a second call.
                while _is(tokens, end + 1, "("):
                    opening, end = end + 1, _closing(tokens, end + 1)
                    marks.append("computed")
                if end >= hi or not _is(tokens, end, ")"):
                    raise ValueError("unclosed test declaration")
                first = tokens[opening + 1] if opening + 1 < end else None
                name = (first.text if first and first.kind == "string" and "\\" not in first.text
                        and _is(tokens, opening + 2, ",", ")") else None)
                names = (*groups, name) if direct and groups is not None and name is not None and not any(
                    m in marks for m in ("each", "for", "computed")) else None
                # Find the direct callback body, stepping over options and args.
                body, body_end = end, end
                cursor = opening + 1
                while cursor < end:
                    if _is(tokens, cursor, "=") and _is(tokens, cursor + 1, ">"):
                        body = cursor + 2
                        body_end = _closing(tokens, body) if _is(tokens, body, "{") else end
                        break
                    if _is(tokens, cursor, "function"):
                        body = cursor + 1
                        while body < end and not _is(tokens, body, "{"):
                            body += 1
                        body_end = _closing(tokens, body) if body < end else end
                        break
                    if _is(tokens, cursor, "{", "[", "("):
                        cursor = _closing(tokens, cursor)
                    cursor += 1
                marked = inherited_mark or "fails" in marks or any(
                    tokens[i].text == "fails" and _is(tokens, i + 1, ":")
                    for i in range(opening + 1, body))
                if token.text in ("describe", "suite"):
                    if body < end:
                        walk(body + 1, body_end, names, direct, marked)
                else:
                    declarations.append(_TestSource(names, tokens[start].start, tokens[end].end,
                                                    tokens[body].start, tokens[body_end].end, marked))
                at = end + 1
                continue
            if _is(tokens, at, "{"):
                end = _closing(tokens, at)
                walk(at + 1, end, groups, False, inherited_mark)
                at = end + 1
            else:
                at += 1
    walk(0, len(tokens))
    return tokens, declarations


def _bases(text: str, tokens, declaration: _TestSource) -> tuple[str, ...]:
    """Basis lines only in actual comments inside or directly above this test."""
    previous = max((t.end for t in tokens if t.end <= declaration.start), default=0)
    gaps = []
    inside = [t for t in tokens if declaration.start <= t.start < declaration.end]
    end = previous
    for token in inside:
        gaps.append(text[end:token.start])
        end = token.end
    bases = []
    for gap in gaps:
        for comment in re.findall(r"//[^\n]*|/\*[\s\S]*?\*/", gap):
            for line in comment.splitlines():
                line = re.sub(r"^\s*(?://|/\*+|\*)?\s*", "", line).removesuffix("*/").strip()
                if line.startswith("Basis:") and line[6:].strip():
                    bases.append(line)
    return tuple(bases)


def _source(test: str, text: str) -> Source:
    """A unique literal declaration proves sameness; uncertainty means new."""
    try:
        tokens, declarations = _declarations(text)
    except ValueError:
        return Source()
    wanted = tuple(test.split(" > ")[1:])
    matches = [d for d in declarations if d.names == wanted]
    unknown = [d for d in declarations if d.names is None]
    if len(matches) == 1 and not unknown:
        declaration = matches[0]
        return Source(text[declaration.start:declaration.end], _bases(text, tokens, declaration), declaration.marked)
    # One unknown declaration can supply its own basis, but can never be preserved.
    if not matches and len(unknown) == 1:
        declaration = unknown[0]
        return Source(None, _bases(text, tokens, declaration), declaration.marked)
    return Source(expected_failure=any(d.marked for d in matches + unknown))


def _error_kind(error: dict) -> str:
    """Non-assertion error category from the runner's type/message, never exit status."""
    name, message = str(error.get("name", "Error")), str(error.get("message", ""))
    if name == "AssertionError":
        # Assertion messages include user text and compared values. Only source
        # provenance can distinguish an own assertion from production or setup.
        return "other-exception:" + name
    if re.search(r"timed?\s*out|timeout", message, re.I):
        return "timeout"
    if name == "ReferenceError" or re.search(r"not a function|does not provide an export|is not defined", message):
        return "missing name:" + name
    if re.search(r"transform|parse error|syntax error|expected.*(?:token|identifier)", message, re.I) or name == "SyntaxError":
        return "transform-error:" + name
    if re.search(r"cannot find|cannot resolve|failed to (?:load|resolve)|module not found|ERR_MODULE_NOT_FOUND", message, re.I):
        return "import-error:" + name
    return "other-exception:" + name


def _module_error(project: Path, error: dict, report: dict) -> str:
    """Collection failures retain setup provenance from resolved runner config."""
    stack = str(error.get("stack", ""))
    locations = [str(frame.get("file", "")) for frame in error.get("stacks", [])]
    if any(str(project / path) in stack or str(project / path) in locations
           for path in report.get("setup", [])):
        return "setup-error:" + str(error.get("name", "Error"))
    return _error_kind(error)


def _failure(project: Path, test: str, errors: list[dict]) -> str:
    """An assertion is genuine only when its first project frame is in this test's body.

    Library/internal frames are ignored, but the first application frame is never
    skipped: production assertions and hooks must not become test assertions.
    Every reported error must independently qualify; absent provenance refuses.
    """
    file = test.split(" > ", 1)[0]
    try:
        text = (project / file).read_text(encoding="utf-8")
        _, declarations = _declarations(text)
    except (OSError, ValueError):
        return "unclassified failure: test source unreadable"
    wanted = tuple(test.split(" > ")[1:])
    spans = [d for d in declarations if d.names == wanted]
    if not spans:
        spans = [d for d in declarations if d.names is None]
    if not errors:
        return "unclassified failure: no reported errors"
    for error in errors:
        kind = _error_kind(error)
        if not kind.startswith("other-exception:"):
            return kind
        frames = error.get("stacks") or []
        if not frames:
            frames = [{"file": m[0].removeprefix("file://"), "line": int(m[1]), "column": int(m[2])}
                      for m in re.findall(r"(?:\(|\s)((?:file://)?/[^\n()]+?):(\d+):(\d+)\)?", error.get("stack", ""))]
        frame = None
        for candidate in frames:
            raw = str(candidate.get("file", "")).removeprefix("file://")
            if not raw or raw.startswith("node:"):
                continue
            path = Path(raw)
            if not path.is_absolute():
                path = project / path
            normalized = path.as_posix()
            # Assertion/runner plumbing is not the code under test. Other
            # dependencies are: never skip their frames to reach the test.
            if any(part in normalized for part in (
                    "/node_modules/chai/", "/node_modules/@vitest/", "/node_modules/vitest/",
                    "/node_modules/assertion-error/")):
                continue
            rel = path.relative_to(project).as_posix() if path.is_relative_to(project) else normalized
            frame = (rel, candidate.get("line"), candidate.get("column", 1))
            break
        if frame is None:
            return "unclassified AssertionError: no source provenance" if error.get("name") == "AssertionError" else kind
        if frame[0] != file:
            return "production assertion:AssertionError (code under test or setup)" if error.get("name") == "AssertionError" else kind
        lines = text.splitlines(keepends=True)
        line, column = frame[1:]
        if not isinstance(line, int) or not 1 <= line <= len(lines):
            return "unclassified failure: invalid source location"
        offset = sum(map(len, lines[:line - 1])) + max(0, int(column or 1) - 1)
        if len(spans) != 1 or not spans[0].body_start <= offset < spans[0].body_end:
            return "setup or helper failure outside the test body:" + str(error.get("name", "Error"))
        if error.get("name") != "AssertionError":
            return kind
    return "genuine-red"


@dataclass(frozen=True)
class _Fault:
    """Why vitest cannot run here, as one phrase."""

    reason: str


@dataclass(frozen=True)
class _Found:
    """The node and the vitest package that run a project's tests; ``entry``
    is vitest's node API module."""

    node: str
    node_version: str
    package: Path
    version: str
    entry: Path



def _find(project: Path, *, judge: bool = True) -> _Found | _Fault:
    """The node on PATH and the vitest installed in the project, or why
    vitest cannot run; with ``judge``, a node or vitest the delivery could
    rewrite (repository content) is refused."""
    node = shutil.which("node")
    if node is None:
        return _Fault("Node is not installed here (no node on PATH)")
    try:
        version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=60,
                                 env=_environment()).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return _Fault(f"Node at {node} cannot start: {exc}")
    package = project / "node_modules" / "vitest"
    manifest = package / "package.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        entry = data["exports"]["./node"]
        entry = entry if isinstance(entry, str) else entry.get("import") or entry["default"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return _Fault(f"vitest's packages are not installed in {project} (no usable node_modules/vitest); "
                      "install them with the project's package manager, for example npm ci")
    if judge:
        for program in (Path(node).resolve(), package.resolve()):
            problem = _content(project, program)
            if problem:
                return _Fault(problem)
    return _Found(node, version or "unknown version", package, str(data.get("version", "unknown version")),
                  (package / entry).resolve())


def _content(project: Path, program: Path) -> str | None:
    """Why ``program`` (node, or the vitest package) is repository content:
    tracked, or not ignored, so the delivery could rewrite it."""
    if not program.is_relative_to(project):
        return None
    rel = program.relative_to(project).as_posix()
    parts = rel.split("/")
    # The whole package folder a delivery could fill, not only the one program.
    folder = "/".join(parts[: parts.index("node_modules") + 1]) if "node_modules" in parts else rel
    tracked = subprocess.run(["git", "ls-files", "-z", "--", folder], cwd=project, capture_output=True)
    ignored = subprocess.run(["git", "check-ignore", "-q", rel], cwd=project, capture_output=True)
    if tracked.returncode or ignored.returncode not in (0, 1):
        return f"cannot tell whether {rel} is part of the repository's content (git fails here)"
    if tracked.stdout or ignored.returncode != 0:
        return (f"{rel} is part of the repository's content ({folder} has tracked or unignored files); "
                "evidence must come from a node and vitest the delivery cannot rewrite")
    return None


def _configuration(project: Path, statement: str | None) -> str | bool | _Fault:
    """The configuration file the run uses: the stated one, else the first
    default file in the project root; False when there is none (vitest would
    otherwise look above the repository)."""
    if statement:
        rel = _repository_path(statement)
        if rel is None:
            return _Fault(f"the stated configuration file {statement} is not a repository path")
        path = project / rel
        if not path.is_file():
            return _Fault(f"the stated configuration file {rel} does not exist")
        return str(path)
    for name in _CONFIGS:
        if (project / name).is_file():
            return str(project / name)
    return False


def _named(tests) -> dict[str, list[tuple[str, ...]] | None]:
    """Each named file with the name parts of its named tests, or None when
    the file alone is named (every test in it)."""
    named: dict[str, list[tuple[str, ...]] | None] = {}
    for test in tests:
        file, *parts = test.split(" > ")
        if not parts:
            named[file] = None
        elif named.get(file, []) is not None:
            named.setdefault(file, [])
            if tuple(parts) not in named[file]:
                named[file].append(tuple(parts))
    return named


def _environment() -> dict[str, str]:
    from dekspec.execution.acceptance import clean_env

    return {k: v for k, v in clean_env().items() if not k.startswith(_ENV_DROP_PREFIXES)}


def _execute(command: list[str], cwd: Path, timeout: int) -> tuple[int | None, str, bool]:
    """Run ``command`` in its own process group; on timeout the whole group
    (vitest's workers too) is killed."""
    with subprocess.Popen(command, cwd=str(cwd), env=_environment(), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
            return process.returncode, output or "", False
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                pass
            output, _ = process.communicate()
            return process.returncode, output or "", True


def _facts(project: Path, named, report, exit_code, duration, tail) -> Run:
    """The driver's report as facts: one outcome per named test, in the order
    named, and the run's own faults."""
    modules = {m["file"]: m for m in report.get("modules", [])}
    included = set(report.get("specs", []))
    faults = [f"vitest configuration/startup {_module_error(project, e, report)}: {_first_line(e.get('message', ''))}"
              for e in report.get("errors", [])]
    if faults and not included and not modules:
        # vitest did not start (its configuration failed to load, for one): nothing about any test.
        return Run(faults=tuple(faults), account=tuple(faults),
                   facts={"exit_code": exit_code, "duration": duration, "tail": tail})
    outcomes: list[Outcome] = []
    for file, parts in named.items():
        module = modules.get(file)
        if module is None:
            why = ("not reported" if file in included
                   else "excluded by configuration" if (project / file).is_file() else "not-found")
            outcomes.extend(Outcome(_test(file, p), why, ran=False) for p in (parts or [()]))
            continue
        module_problem = None
        if module.get("errors"):
            error = module["errors"][0]
            module_problem = _module_error(project, error, report)
            faults.append(f"{file}: {module_problem}: {_first_line(error.get('message', ''))}")
        tests = module.get("tests", [])
        counts: dict[str, int] = {}
        for test in tests:
            counts[test["name"]] = counts.get(test["name"], 0) + 1
        if parts is None:
            if not tests:
                outcomes.append(Outcome(file, module_problem or "no tests", ran=False))
            for test in tests:
                outcomes.append(_outcome(project, f"{file} > {test['name']}", test, counts, of=file))
            continue
        for wanted in parts:
            name = " > ".join(wanted)
            matches = [t for t in tests if t["name"] == name]
            if not matches:
                outcomes.append(Outcome(_test(file, wanted),
                                        (module_problem or "not-found") if not tests else "not-found",
                                        ran=False))
                continue
            outcomes.append(_outcome(project, _test(file, wanted), matches[0], counts))
    account = [f"{o.test}: {o.result}" for o in outcomes if o.result != "passed"] + faults
    facts = {"exit_code": exit_code, "duration": duration, "tail": tail if account else ""}
    return Run(tuple(outcomes), faults=tuple(faults), account=tuple(account), facts=facts)


def _outcome(project: Path, test: str, seen: dict, counts: dict[str, int], of: str = "") -> Outcome:
    """What happened to one test vitest collected, in DekSpec's words."""
    if counts.get(seen["name"], 0) > 1:
        return Outcome(test, "shares its full name with another test of its file", ran=False, of=of)
    if seen.get("filtered"):
        return Outcome(test, "filtered out by name", ran=False, of=of)
    state = seen.get("state")
    if state == "skipped" or seen.get("mode") in ("skip", "todo"):
        if seen.get("around") and seen.get("mode") == "run":
            return Outcome(test, "setup-error", of=of)
        return Outcome(test, "skipped", of=of)
    if seen.get("fails"):
        return Outcome(test, "xfail", of=of)
    if state == "passed":
        return Outcome(test, "passed" if not seen.get("retries") else "passed only on a retry", of=of)
    if state == "failed":
        return Outcome(test, "setup-error" if seen.get("around") or seen.get("setupFailed") else
                       _failure(project, test, seen.get("errors", [])), of=of)
    return Outcome(test, "did not finish", of=of)


def _test(file: str, parts: tuple[str, ...]) -> str:
    return " > ".join((file, *parts))


def _first_line(text: str) -> str:
    return (str(text).strip().splitlines() or [""])[0][:300]


def _repository_path(path: str) -> str | None:
    """``path`` as a normalized repository-relative path; None when it is
    absolute or leaves the repository."""
    if not isinstance(path, str) or not path.strip() or posixpath.isabs(path.strip()):
        return None
    rel = posixpath.normpath(path.strip().replace("\\", "/"))
    return None if rel in (".", "..") or rel.startswith("../") else rel


def _stated(read) -> str | None:
    """The configuration file the project states, read through ``read``."""
    from dekspec.execution.settings import _from_text

    content = read(".dekspec/config.yaml")
    if content is None:
        return None
    statement = _from_text(content.decode("utf-8", "replace"), "dekspec").vitest_config
    return _repository_path(statement) if statement else None


def _optional(read, path: str) -> bytes | None:
    """A file that may be absent or a folder at the revision ``read`` reads."""
    try:
        return read(path)
    except (ExecutionError, OSError):
        return None


def _folders(path: str) -> list[str]:
    """Every folder from the root (".") down to the one holding ``path``."""
    parts = posixpath.dirname(path).split("/") if posixpath.dirname(path) else []
    return ["."] + ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]


def _loaded(starts: dict[str, bytes], read) -> list[tuple[str, bytes | None]]:
    """Every repository file the configuration and the TypeScript options in
    ``starts`` load, transitively, with its content (None for a file that is
    absent but would take effect if added). A module is read as tokens
    (strings, template substitutions as code, comments and regular
    expressions told apart); a quote left open on its line means it was not
    read right, so CannotAnswer.
    Listing and following are kept apart. A file is followed (read in turn
    for what it names) once, whenever anything loads it, whatever listed it
    first: a module a followed module loads (see _loads), a file a setup
    option names (setupFiles, globalSetup, snapshotSerializers,
    coverage.customProviderModule; read beside its module and from the
    repository root, where vitest's root puts it), a repository file the
    runner, environment, pool, diff, snapshotEnvironment or reporters option
    names, each configuration `projects` names (a folder by each default
    configuration file and environment file in it, present or not; an inline
    project object is read in place, as part of its module), the package of
    the repository's own workspaces a load names, the __mocks__ file vitest
    would use for a module vi.mock names, and each file a tsconfig extends
    (as a tsconfig). Listed and not followed (the owner's rule of 15 Oct: a
    quoted path is listed, not followed): every other file a quoted path in
    a followed module names, such as a spawn argument or an alias target,
    except inside the `coverage` option, which chooses only what coverage
    reports. A load that names no present file lists every file that would
    answer it if added. Packages installed under node_modules and the
    package list (package.json and the lockfile, wherever a module names
    them) are not support files. Where the read cannot tell what is loaded,
    CannotAnswer naming support: what _loads and _keyed refuse, a pattern
    where a module or project is named, and a bare name no installed package
    or workspace answers."""
    seen: dict[str, bytes | None] = dict(starts)
    followed = set(starts)
    queue = [(path, _is_tsconfig(path)) for path in starts]

    def add(path: str, content: bytes | None, follow: bool = False, tsconfig: bool = False) -> None:
        seen.setdefault(path, content)
        if (follow and content is not None and path not in followed
                and (tsconfig or path.endswith(_SOURCES))):
            followed.add(path)
            queue.append((path, tsconfig))

    while queue:
        module, tsconfig = queue.pop(0)
        try:
            tokens = _tokens(seen[module].decode("utf-8", "replace"))
        except ValueError as exc:
            raise _cannot_tell(f"{module} cannot be read as code: {exc}") from None
        if tsconfig:
            for path, content, follow in _extended(module, tokens, read):
                add(path, content, follow, tsconfig=True)
            continue
        loading, mocked = _loads(module, tokens)
        naming: set[str] = set()
        for key, value in _keyed(module, tokens):
            if key == "projects":
                for path, content, follow in _projects(module, value, read):
                    add(path, content, follow, tsconfig=_is_tsconfig(path))
                continue
            named = naming if key in _NAMING_KEYS else loading
            named.add(value)
            if value.startswith(".") and posixpath.dirname(module):
                named.add("/" + value)  # the same path from vitest's root, the repository's
        for literal in sorted(_quoted_paths(tokens) | loading | naming):
            loads = literal in loading
            if loads and any(c in literal for c in _NOT_PLAIN) and ":" not in literal:
                raise _cannot_tell(f"{module} loads {literal}, a pattern or a computed path")
            path, content = _resolve(module, literal, read)
            if path is None and loads and not literal.startswith((".", "/")):
                path, content = _workspace_module(module, literal, read)
            if literal in mocked:
                for mock in _mocks(literal, path):
                    add(mock, _optional(read, mock), follow=True)
            if path is None:
                if loads and literal.startswith((".", "/")):
                    for absent in _candidates(module, literal):
                        add(absent, None)  # each would answer the load if added
                continue
            add(path, content, follow=loads or literal in naming, tsconfig=_is_tsconfig(path))
    return sorted((path, content) for path, content in seen.items()
                  if path not in starts and posixpath.basename(path) not in _PACKAGE_LISTS)


def _mocks(literal: str, path: str | None) -> list[str]:
    """The files vitest would load in place of the module ``literal`` (which
    vi.mock names; ``path`` is the repository file it resolves to, if any)
    when no factory is given: the file of the same name in a __mocks__
    folder beside ``path``, and for a package or Node module the file or
    folder of its name, with any extension, in the root's __mocks__ folder
    (@vitest/mocker's findMockRedirect)."""
    out = []
    if path is not None:
        out.append(posixpath.join(posixpath.dirname(path), "__mocks__", posixpath.basename(path)))
    if not literal.startswith((".", "/")):
        for name in dict.fromkeys((literal, literal.removeprefix("node:"))):
            rel = _repository_path(f"__mocks__/{name}")
            if rel is not None:
                out.extend(rel + suffix for suffix in _COMPLETIONS)
    return out


@dataclass(frozen=True)
class _Token:
    """One token of a JavaScript or TypeScript module, or of a tsconfig.
    ``kind`` is "string" (a quoted string, or a template with no
    substitution; ``text`` is its content), "template" (a template with
    substitutions; ``inner`` holds each substitution's tokens, which are
    code), "regex", "name" (an identifier or a keyword), "number" or
    "punct" (``text`` is one character). ``start``/``end`` delimit the
    original source, preserving comments and whitespace for test identity."""

    kind: str
    text: str
    inner: tuple[tuple[_Token, ...], ...] = ()
    start: int = 0
    end: int = 0


def _tokens(text: str) -> tuple[_Token, ...]:
    """``text`` as tokens; comments and white space are dropped. ValueError
    when a quoted string is not closed on its line (the text was misread,
    or is not code)."""
    return _scan(text, 0, nested=False)[0]


def _scan(text: str, at: int, *, nested: bool) -> tuple[tuple[_Token, ...], int]:
    """The tokens from ``at``, and where they end: the end of ``text``, or,
    when ``nested`` (a template substitution), just after the "}" that
    closes it."""
    out: list[_Token] = []
    depth, size = 0, len(text)
    while at < size:
        start, count = at, len(out)
        char = text[at]
        if char.isspace():
            at = _SPACE.match(text, at).end()
        elif text.startswith("//", at):
            end = text.find("\n", at)
            at = size if end < 0 else end
        elif text.startswith("/*", at):
            end = text.find("*/", at + 2)
            at = size if end < 0 else end + 2
        elif char in "\"'":
            end = at + 1
            while end < size and text[end] not in (char, "\n"):
                end += 2 if text[end] == "\\" else 1
            if end >= size or text[end] != char:
                raise ValueError(f"the quote opened on line {text.count(chr(10), 0, at) + 1} is not closed on it")
            out.append(_Token("string", text[at + 1:end]))
            at = end + 1
        elif char == "`":
            end, substitutions = at + 1, []
            while end < size and text[end] != "`":
                if text[end] == "\\":
                    end += 2
                elif text.startswith("${", end):
                    inner, end = _scan(text, end + 2, nested=True)
                    substitutions.append(inner)
                else:
                    end += 1
            out.append(_Token("template", "", tuple(substitutions)) if substitutions
                       else _Token("string", text[at + 1:min(end, size)]))
            at = end + 1
        elif char == "/" and _regex_may_start(out) and (end := _regex_end(text, at)) is not None:
            out.append(_Token("regex", text[at:end]))
            at = end
        elif (name := _NAME.match(text, at)) is not None:
            out.append(_Token("name", name.group()))
            at = name.end()
        elif (number := _NUMBER.match(text, at)) is not None:
            out.append(_Token("number", number.group()))
            at = number.end()
        else:
            if nested and char == "}":
                if depth == 0:
                    return tuple(out), at + 1
                depth -= 1
            elif nested and char == "{":
                depth += 1
            out.append(_Token("punct", char))
            at += 1
        if len(out) > count:
            out[-1] = replace(out[-1], start=start, end=at)
    return tuple(out), at


class _SkeletonReader:
    """Read a module's declared import surface, without evaluating its code.

    Brackets delimit opaque bodies and expressions. Only declaration headers,
    bindings, export lists and class members contribute names. Unknown export
    shapes fail closed; local class aliases are resolved after all declarations
    so export order does not matter. This is not a TypeScript type checker.
    """

    def __init__(self, text):
        self.text = text
        self.tokens = _tokens(text)
        self.pairs = {}
        self.locals = {}
        self.imports = set()
        self.exports = []
        self.direct = set()
        self.commonjs = set()
        self.commonjs_object = False
        self._validate(self.tokens)

    def _validate(self, tokens):
        stack = []
        previous = 0 if tokens is self.tokens or not tokens else tokens[0].start
        for index, token in enumerate(tokens):
            # The shared tokenizer deliberately tolerates incomplete comments
            # and templates for dependency discovery. A skeleton cannot.
            self._trivia(previous, token.start)
            if token.end > len(self.text) or token.kind == 'template' and not self.text[
                    token.start:token.end].endswith('`'):
                raise ValueError('unclosed template literal')
            previous = token.end
            if token.kind == 'punct':
                if token.text in '({[':
                    stack.append(index)
                elif token.text in ')}]':
                    if not stack or tokens[stack[-1]].text != dict(zip(')}]', '({['))[token.text]:
                        raise ValueError(f'unmatched {token.text}')
                    opened = stack.pop()
                    if tokens is self.tokens:
                        self.pairs[opened] = index
                elif token.text in ('\\', '\x00'):
                    raise ValueError('invalid source character or escaped identifier')
            for inner in token.inner:
                self._validate(inner)
        if stack:
            raise ValueError(f'unclosed {tokens[stack[-1]].text}')
        if tokens is self.tokens:
            self._trivia(previous, len(self.text))

    def _trivia(self, start, end):
        # Token offsets distinguish actual comments from comment-like strings.
        gap = self.text[start:end]
        i = 0
        while i < len(gap):
            if gap[i].isspace():
                i += 1
            elif gap.startswith('//', i):
                newline = gap.find('\n', i)
                i = len(gap) if newline < 0 else newline + 1
            elif gap.startswith('/*', i):
                close = gap.find('*/', i + 2)
                if close < 0:
                    raise ValueError('unclosed comment')
                i = close + 2
            else:
                raise ValueError('cannot read source between tokens')

    def _note(self):
        text = self.text.lstrip()
        if not text.startswith('/*'):
            return ''
        end = text.find('*/', 2)
        if end < 0:
            raise ValueError('unclosed interface comment')
        return '\n'.join(re.sub(r'^\s*\* ?', '', line).rstrip()
                         for line in text[2:end].splitlines()).strip()

    def _at(self, i, *words):
        return _is(self.tokens, i, *words)

    def _name(self, i, *, quoted=False):
        if i >= len(self.tokens) or self.tokens[i].kind not in (
                ('name', 'string', 'number') if quoted else ('name',)):
            raise ValueError('expected a declared name')
        value = self.tokens[i].text
        if '\\' in value:
            raise ValueError('cannot decide an escaped public name')
        return value

    def _jump(self, i):
        return self.pairs.get(i, i) + 1

    def _linebreak(self, i):
        return 0 < i < len(self.tokens) and any(
            c in self.text[self.tokens[i - 1].end:self.tokens[i].start] for c in '\r\n\u2028\u2029')

    def _end(self, i, stops=(';',), *, newline=False, types=False, limit=None):
        """Find a production's end before applying automatic semicolon insertion.

        TypeScript's canParseSemicolon does not decide how far a production
        extends. Types and expressions have different continuation grammars;
        in particular a member-looking token is not evidence for ASI.
        Delimited lists/heritage (newline=False) are scanned to their delimiter.
        """
        limit = len(self.tokens) if limit is None else limit
        if newline and types:
            return self._type_end(i)
        if newline:
            # Statements outside declarations do not contribute names, but
            # their blocks must remain opaque to the module reader.
            if self._at(i, 'if', 'for', 'while', 'switch', 'with') and self._at(i + 1, '('):
                end = self._jump(i + 1)
                if self._at(end, '{'):
                    return self._jump(end)
                raise ValueError('cannot decide an unbraced control statement')
            if i == 0 and self.text.startswith('#!'):
                i += 2
                while i < limit and not self._linebreak(i):
                    i += 1
                return i
            if self._at(i, 'throw'):
                if self._linebreak(i + 1):
                    raise ValueError('line break after throw')
                i += 1
            end = self._expression_end(i)
            if end < limit and not (self._at(end, *stops) or self._linebreak(end)):
                raise ValueError('expression is not followed by a semicolon or line break')
            return end
        while i < limit and not self._at(i, *stops):
            if self._at(i, '<') and types:
                i = self._type_arguments_end(i)
            else:
                i = self._jump(i)
        return i

    def _operator(self, i):
        """Reassemble punctuation without joining across whitespace/comments."""
        if i >= len(self.tokens):
            return '', i
        token = self.tokens[i]
        if token.kind != 'punct':
            return token.text if token.kind == 'name' else '', i + 1
        for op in ('>>>=', '**=', '===', '!==', '>>>', '<<=', '>>=', '&&=', '||=', '??=',
                   '=>', '?.', '++', '--', '**', '==', '!=', '<=', '>=', '<<', '>>',
                   '&&', '||', '??', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^='):
            if self.text.startswith(op, token.start):
                end = i + len(op)
                if end <= len(self.tokens) and self.tokens[end - 1].end == token.start + len(op):
                    return op, end
        return token.text, i + 1

    def _arrow_head_end(self, i):
        if self._at(i, 'async') and not self._linebreak(i + 1):
            i += 1
        if self._at(i, '<'):
            i = self._type_arguments_end(i)
        if self._at(i, '('):
            i = self._jump(i)
            if self._at(i, ':'):
                i = self._type_end(i + 1)
        elif i < len(self.tokens) and self.tokens[i].kind == 'name':
            i += 1
        else:
            return None
        op, end = self._operator(i)
        if op == '=>':
            return end
        return None

    def _expression_end(self, i, minimum=1):
        """Consume an assignment expression using TS's operator precedence.

        ASI is considered by the caller only after this production returns.
        Arrow bodies and as/satisfies types finish their own productions: unlike
        primary expressions they cannot acquire a call/index/tag suffix here.
        This distinction matters for a following computed class member.
        """
        assignable = self._operator(i)[0] not in (
            '+', '-', '!', '~', '++', '--', 'typeof', 'void', 'delete', 'await')
        if minimum <= 1:
            arrow = self._arrow_head_end(i)
            if arrow is not None:
                return self._jump(arrow) if self._at(arrow, '{') else self._expression_end(arrow)
        i = self._expression_operand_end(i)
        precedence = {
            '=': 1, '+=': 1, '-=': 1, '*=': 1, '/=': 1, '%=': 1, '**=': 1,
            '<<=': 1, '>>=': 1, '>>>=': 1, '&=': 1, '|=': 1, '^=': 1,
            '&&=': 1, '||=': 1, '??=': 1,
            '??': 3, '||': 3, '&&': 4, '|': 5, '^': 6, '&': 7,
            '==': 8, '!=': 8, '===': 8, '!==': 8,
            '<': 9, '>': 9, '<=': 9, '>=': 9, 'in': 9, 'instanceof': 9,
            'as': 9, 'satisfies': 9, '<<': 10, '>>': 10, '>>>': 10,
            '+': 11, '-': 11, '*': 12, '/': 12, '%': 12, '**': 13,
        }
        while True:
            op, after = self._operator(i)
            if op == '?' and minimum <= 2:
                i = self._expression_end(after)
                if not self._at(i, ':'):
                    raise ValueError('conditional expression has no false branch')
                return self._expression_end(i + 1)
            level = precedence.get(op, 0)
            if level < minimum:
                return i
            if level == 1 and not assignable:
                raise ValueError('expression cannot be an assignment target')
            if op in ('as', 'satisfies'):
                if self._linebreak(i):
                    return i
                i = self._type_end(after)
            else:
                i = self._expression_end(after, level if level == 1 or op == '**' else level + 1)
                assignable = False

    def _expression_operand_end(self, i):
        op, after = self._operator(i)
        if op in ('+', '-', '!', '~', '++', '--', 'typeof', 'void', 'delete', 'await', 'yield', 'new'):
            return self._expression_operand_end(after)
        if self._at(i, 'class'):
            _, _, i = self._class(i)
        elif self._at(i, 'function') or self._at(i, 'async') and self._at(i + 1, 'function'):
            i += 2 if self._at(i, 'async') else 1
            if self._at(i, '*'):
                i += 1
            if i < len(self.tokens) and self.tokens[i].kind == 'name':
                i += 1
            if self._at(i, '<'):
                i = self._type_arguments_end(i)
            if not self._at(i, '('):
                raise ValueError('function expression has no parameters')
            i = self._function_tail(self._jump(i))
        elif self._at(i, '<'):
            i = self._jsx_end(i)
        elif i in self.pairs:
            if self._at(i, '(') and self.pairs[i] == i + 1:
                raise ValueError('empty expression')
            i = self._jump(i)
        elif (i < len(self.tokens) and self.tokens[i].kind != 'punct'
              and not self._at(i, 'in', 'instanceof', 'export', 'const', 'let', 'var')):
            i += 1
        else:
            raise ValueError('expected an expression operand')
        while i < len(self.tokens):
            op, after = self._operator(i)
            if op == '?.':
                i = after
                if self._at(i, '<'):
                    i = self._type_arguments_end(i)
                if self._at(i, '(', '['):
                    i = self._jump(i)
                else:
                    self._name(i)
                    i += 1
            elif op == '.':
                if self._at(after, '#'):
                    after += 1
                self._name(after)
                i = after + 1
            elif self._at(i, '(', '['):
                i = self._jump(i)
            elif self.text[self.tokens[i].start:self.tokens[i].start + 1] == '`':
                i += 1
            elif op == '!' and not self._linebreak(i):
                i = after
            elif op in ('++', '--') and not self._linebreak(i):
                return after
            elif op == '<' and self._generic_call(i):
                i = self._type_arguments_end(i)
            else:
                break
        return i

    def _jsx_end(self, i):
        """Skip a balanced JSX element; ambiguous angle syntax fails closed."""
        stack = []
        while i < len(self.tokens):
            if not self._at(i, '<'):
                i = self._jump(i)
                continue
            closing = self._at(i + 1, '/')
            i += 2 if closing else 1
            name = []
            while (i < len(self.tokens)
                   and (self.tokens[i].kind == 'name' or self._at(i, '.', ':', '-'))
                   and (not name or self.tokens[i - 1].end == self.tokens[i].start)):
                name.append(self.tokens[i].text)
                i += 1
            while i < len(self.tokens) and not self._at(i, '>'):
                i = self._jump(i)
            if i == len(self.tokens):
                break
            empty = self._at(i - 1, '/')
            i += 1
            if closing:
                if not stack or stack.pop() != name:
                    raise ValueError('cannot decide JSX or angle-bracket expression')
            elif not empty:
                stack.append(name)
            if not stack:
                return i
        raise ValueError('cannot decide JSX or angle-bracket expression')

    def _type_arguments_end(self, i):
        depth = 0
        while i < len(self.tokens):
            if self._at(i, '<'):
                depth += 1
            elif self._at(i, '>') and not self._at(i - 1, '='):
                depth -= 1
                if depth == 0:
                    return i + 1
            i = self._jump(i)
        raise ValueError('unclosed type arguments')

    def _type_end(self, i, *, conditional=True):
        """Read a type's extent, following TS 5.9's type productions.

        Balanced type literals/tuples/parameters are opaque. Outside them only
        union/intersection, qualified names and a function type's arrow cross
        line breaks. Postfix brackets, type arguments, predicates and extends
        obey their own restricted productions, not an expression keyword list.
        """
        if self._at(i, '|', '&'):
            i += 1
        i = self._type_operand_end(i)
        while self._at(i, '|', '&'):
            i = self._type_operand_end(i + 1)
        if conditional and self._at(i, 'extends') and not self._linebreak(i):
            i = self._type_end(i + 1, conditional=False)
            if not self._at(i, '?'):
                raise ValueError('conditional type has no question mark')
            i = self._type_end(i + 1)
            if not self._at(i, ':'):
                raise ValueError('conditional type has no false branch')
            i = self._type_end(i + 1)
        return i

    def _type_operand_end(self, i):
        if self._at(i, 'keyof', 'readonly', 'unique'):
            return self._type_operand_end(i + 1)
        if self._at(i, 'asserts') and not self._linebreak(i + 1):
            self._name(i + 1)
            i += 2
            return self._type_end(i + 1) if self._at(i, 'is') else i
        if self._at(i, 'infer'):
            self._name(i + 1)
            return i + 2
        if self._at(i, 'abstract') and self._at(i + 1, 'new'):
            i += 1
        constructor = self._at(i, 'new')
        if constructor:
            i += 1
        generic = self._at(i, '<')
        if generic:
            i = self._type_arguments_end(i)
        parens = self._at(i, '(')
        empty = parens and self.pairs[i] == i + 1
        if i in self.pairs:
            i = self._jump(i)
        else:
            if self._at(i, 'typeof'):
                i += 1
            if self._at(i, '-'):
                i += 1
                if i >= len(self.tokens) or self.tokens[i].kind != 'number':
                    raise ValueError('expected a numeric literal type')
            if i >= len(self.tokens) or self.tokens[i].kind not in ('name', 'string', 'number', 'template'):
                raise ValueError('expected a type')
            imported = self._at(i, 'import')
            i += 1
            if imported and self._at(i, '('):
                i = self._jump(i)
            while self._at(i, '.'):
                self._name(i + 1)
                i += 2
            if self._at(i, '<') and not self._linebreak(i):
                i = self._type_arguments_end(i)
            if self._at(i, 'is') and not self._linebreak(i):
                return self._type_end(i + 1)
        if parens and self._at(i, '=') and self._at(i + 1, '>'):
            return self._type_end(i + 2)
        if constructor or generic or empty:
            raise ValueError('function type has no arrow')
        while self._at(i, '[', '!') and not self._linebreak(i):
            i = self._jump(i)
        return i

    def _generic_call(self, i):
        end = _after_type_arguments(self.tokens, i)
        if not self._at(end - 1, '>') or self._at(end, '<', '>', '+', '-'):
            return False
        if end == len(self.tokens) or self._linebreak(end):
            return True
        token = self.tokens[end]
        return (self._at(end, '(', '.', ';', ',', ')', ']', '}', '=', '&', '|', '?', ':')
                or self.text[token.start:token.start + 1] == '`')

    def _parts(self, start, end):
        while start < end:
            stop = self._end(start, (',',), types=True, limit=end)
            yield start, stop
            start = stop + 1

    def _binding(self, i):
        if self._at(i, '{', '['):
            object_pattern = self._at(i, '{')
            end, names = self.pairs[i], set()
            for start, stop in self._parts(i + 1, end):
                if start == stop:
                    continue
                if self._at(start, '.'):
                    if not all(self._at(start + n, '.') for n in range(3)):
                        raise ValueError('invalid rest binding')
                    start += 3
                elif object_pattern:
                    if self._at(start, '['):
                        start = self.pairs[start] + 1
                        if not self._at(start, ':'):
                            raise ValueError('invalid computed binding')
                        start += 1
                    elif self._at(start + 1, ':'):
                        self._name(start, quoted=True)
                        start += 2
                found, after = self._binding(start)
                if after < stop and not self._at(after, '='):
                    raise ValueError('invalid destructured binding')
                names.update(found)
            return names, end + 1
        return {self._name(i)}, i + 1

    def _class(self, i):
        """Return local class name, public members and the end of its body."""
        i += 1
        local = None
        if i < len(self.tokens) and self.tokens[i].kind == 'name' and not self._at(i, 'extends', 'implements'):
            local, i = self._name(i), i + 1
        i = self._end(i, ('{', ';'), types=True)
        if not self._at(i, '{'):
            raise ValueError('class has no body')
        end, members = self.pairs[i], set()
        i += 1
        modifiers = ('public', 'private', 'protected', 'static', 'abstract', 'declare', 'readonly', 'override', 'accessor')
        while i < end:
            if self._at(i, ';'):
                i += 1
                continue
            if self._at(i, 'static') and self._at(i + 1, '{'):
                i = self._jump(i + 1)
                continue
            hidden = False
            static = False
            while (self._at(i, *modifiers)
                   and not (static and self._at(i, 'static'))
                   and (self._at(i, 'static') or not self._linebreak(i + 1))
                   and not self._at(i + 1, '(', '<', '=', ':', '?', '!', ';', '}')):
                hidden |= self._at(i, 'private', 'protected')
                static |= self._at(i, 'static')
                i += 1
            if self._at(i, '#'):
                hidden, i = True, i + 1
            accessor = False
            if (self._at(i, 'get', 'set', 'async')
                    and (not self._at(i, 'async') or not self._linebreak(i + 1))
                    and not self._at(i + 1, '(', '<', '=', ':', '?', '!', ';', '}')):
                accessor = self._at(i, 'get', 'set')
                i += 1
            if self._at(i, '*'):
                i += 1
            computed = self._at(i, '[')
            if computed:
                close = self.pairs[i]
                if close != i + 2 or self.tokens[i + 1].kind not in ('string', 'number'):
                    raise ValueError('cannot decide computed class member or index signature')
                name, i = self._name(i + 1, quoted=True), close + 1
            else:
                name, i = self._name(i, quoted=True), i + 1
            constructor = name == 'constructor' and not accessor and not computed
            if constructor and not self._at(i, '(', '<'):
                raise ValueError('constructor has no parameter list')
            if not constructor and not hidden:
                members.add(name)
            if self._at(i, '?', '!'):
                i += 1
            if self._at(i, '<'):
                i = _after_type_arguments(self.tokens, i)
            if self._at(i, '('):
                close = self.pairs[i]
                if constructor:
                    for start, stop in self._parts(i + 1, close):
                        visibility = []
                        while self._at(start, 'public', 'private', 'protected', 'readonly', 'override'):
                            visibility.append(self.tokens[start].text)
                            start += 1
                        if visibility and not {'private', 'protected'}.intersection(visibility):
                            members.add(self._name(start))
                i = self._function_tail(close + 1)
            else:
                if self._at(i, ':'):
                    i = self._end(i + 1, ('=', ';', '}'), newline=True, types=True)
                if self._at(i, '='):
                    start = i + 1
                    i = self._end(start, (';', '}'), newline=True)
                    if start == i:
                        raise ValueError('missing class field initializer')
                if not (self._at(i, ';', '}') or i < end and self._linebreak(i)):
                    raise ValueError(f'cannot read class member {name}')
            if self._at(i, ';'):
                i += 1
        return local, members, end + 1

    def _function_tail(self, i):
        if self._at(i, ':'):
            start = i + 1
            i = self._end(start, ('{', ';', '}'), newline=True, types=True)
        if self._at(i, '{'):
            return self._jump(i)
        if i == len(self.tokens) or self._at(i, ';', '}') or self._linebreak(i):
            return i  # overload or ambient declaration
        raise ValueError('cannot read function body or return type')

    def _declaration(self, i, exported, default=False):
        ambient = False
        while self._at(i, 'declare', 'abstract', 'async'):
            ambient |= self._at(i, 'declare')
            i += 1
        kind = self.tokens[i].text if i < len(self.tokens) else ''
        if kind == 'class':
            local, members, end = self._class(i)
            if local:
                self.locals[local] = members
            elif not default:
                raise ValueError('class declaration has no name')
            if exported:
                public = 'default' if default else local
                self.direct.add(public)
                self.direct.update(f'{public}.{member}' for member in members)
            return end
        if kind == 'function':
            i += 1
            if self._at(i, '*'):
                i += 1
            local = None
            if not self._at(i, '('):
                local, i = self._name(i), i + 1
            if local:
                self.locals[local] = set()
            elif not default:
                raise ValueError('function declaration has no name')
            if exported:
                self.direct.add('default' if default else local)
            if self._at(i, '<'):
                i = _after_type_arguments(self.tokens, i)
            if not self._at(i, '('):
                raise ValueError('function has no parameter list')
            return self._function_tail(self.pairs[i] + 1)
        if kind in ('const', 'let', 'var') and not self._at(i + 1, 'enum'):
            i += 1
            while True:
                pattern = self._at(i, '{', '[')
                names, i = self._binding(i)
                if self._at(i, ':'):
                    i = self._end(i + 1, ('=', ',', ';'), newline=True, types=True)
                value = set()
                if self._at(i, '='):
                    start = i + 1
                    i = self._end(start, (',', ';'), newline=True)
                    if i == start:
                        raise ValueError('missing variable initializer')
                    value = set() if pattern else self._value(start, i)
                elif kind == 'const' and not ambient:
                    raise ValueError('const declaration has no initializer')
                for name in names:
                    self.locals[name] = value
                    if exported:
                        self.exports.append((name, name))
                if not self._at(i, ','):
                    return i
                i += 1
        if kind == 'const' and self._at(i + 1, 'enum'):
            i += 1
            kind = 'enum'
        if kind in ('type', 'interface', 'enum', 'namespace', 'module'):
            name = self._name(i + 1)
            self.locals.setdefault(name, set())
            if exported:
                self.direct.add(name)
            i += 2
            if kind == 'type':
                i = self._end(i, ('=', ';'), types=True)
                if not self._at(i, '='):
                    raise ValueError('type alias has no definition')
                start = i + 1
                i = self._end(start, newline=True, types=True)
                if start == i:
                    raise ValueError('empty type alias')
                return i
            i = self._end(i, ('{', ';'), types=True)
            if not self._at(i, '{'):
                raise ValueError(f'{kind} has no body')
            return self._jump(i)
        if exported:
            raise ValueError(f'cannot decide export declaration {kind!r}')
        return None

    def _value(self, start, end):
        """Class members, a local alias, or no declared class in an expression."""
        while self._at(start, '(') and self.pairs[start] == end - 1:
            start, end = start + 1, end - 1
        if self._at(start, 'class'):
            _, members, after = self._class(start)
            if after != end:
                raise ValueError('cannot decide class-valued expression')
            return members
        if self._at(start, 'function') or self._at(start, 'async') and self._at(start + 1, 'function'):
            return set()  # function bodies never contribute declared names
        arrow = start + 1 if self._at(start, 'async') else start
        if self._at(arrow, '<'):
            arrow = _after_type_arguments(self.tokens, arrow)
        if self._at(arrow, '('):
            arrow = self.pairs[arrow] + 1
        elif arrow < end and self.tokens[arrow].kind == 'name':
            arrow += 1
        if self._at(arrow, ':'):
            arrow = self._end(arrow + 1, ('=',), types=True)
        if self._at(arrow, '=') and self._at(arrow + 1, '>'):
            return set()  # an arrow's body never contributes declared names
        if self._at(start, '{') and self.pairs[start] == end - 1:
            return set()  # an exported object is not an exported class
        if self._at(start, 'exports', 'module', 'eval'):
            raise ValueError('cannot decide an indirect CommonJS export or evaluation')
        if end == start + 1 and self.tokens[start].kind == 'name':
            return self.tokens[start].text
        # A nested class or export mutation in an expression needs evaluation
        # to identify its public surface. Do not return a partial name set.
        for token in self.tokens[start:end]:
            if token.kind == 'name' and token.text in ('class', 'export', 'exports', 'eval'):
                raise ValueError(f'cannot decide indirect {token.text} in expression')
        return set()

    def _expose(self, name, start, end):
        self.direct.add(name)
        value = self._value(start, end)
        if isinstance(value, str):
            self.exports.append((value, name))
        else:
            self.direct.update(f'{name}.{member}' for member in value)

    def _export(self, i):
        i += 1
        if self._at(i, 'default'):
            i += 1
            if self._at(i, 'class', 'function', 'abstract') or (
                    self._at(i, 'async') and self._at(i + 1, 'function')):
                return self._declaration(i, True, True)
            end = self._end(i, newline=True)
            if end == i:
                raise ValueError('missing default export')
            self._expose('default', i, end)
            return end
        if self._at(i, 'type') and self._at(i + 1, '{', '*'):
            i += 1
        if self._at(i, '*'):
            if not self._at(i + 1, 'as'):
                raise ValueError('unlisted star re-export cannot be compared')
            self.direct.add(self._name(i + 2, quoted=True))
            i += 3
            if not self._at(i, 'from'):
                raise ValueError('namespace re-export has no source')
        elif self._at(i, '{'):
            end, aliases = self.pairs[i], []
            for start, stop in self._parts(i + 1, end):
                if self._at(start, 'type') and stop > start + 1 and not self._at(start + 1, 'as'):
                    start += 1
                local = self._name(start, quoted=True)
                if start + 1 == stop:
                    public = local
                elif self._at(start + 1, 'as') and start + 3 == stop:
                    public = self._name(start + 2, quoted=True)
                else:
                    raise ValueError('cannot read export list')
                aliases.append((local, public))
            i = end + 1
            if not self._at(i, 'from'):
                self.exports.extend(aliases)
                return i
            self.direct.update(public for _, public in aliases)
        else:
            return self._declaration(i, True)
        if i + 1 >= len(self.tokens) or self.tokens[i + 1].kind != 'string':
            raise ValueError('re-export has no literal module name')
        i += 2
        if self._at(i, 'with', 'assert'):
            if not self._at(i + 1, '{'):
                raise ValueError('invalid import attributes')
            i = self._jump(i + 1)
        return i

    def _commonjs(self, i):
        start = i
        if self._at(i, 'module') and self._at(i + 1, '.') and self._at(i + 2, 'exports'):
            i += 3
        elif self._at(i, 'exports'):
            i += 1
        else:
            return None
        if self._at(i, '.'):
            name, i = self._name(i + 1), i + 2
        elif self._at(i, '[') and self.pairs[i] == i + 2 and self.tokens[i + 1].kind == 'string':
            name, i = self._name(i + 1, quoted=True), i + 3
        elif self._at(i, '=') and self.tokens[start].text == 'module':
            name = None
        else:
            raise ValueError('cannot decide computed CommonJS exports')
        if not self._at(i, '=') or self._at(i + 1, '=', '>'):
            raise ValueError('cannot decide CommonJS export assignment')
        value = i + 1
        end = self._end(value, newline=True)
        if value == end:
            raise ValueError('missing CommonJS export value')
        if name is not None:
            if name in self.commonjs:
                raise ValueError(f'cannot decide repeated CommonJS export {name}')
            self.commonjs.add(name)
            self._expose(name, value, end)
        elif self._at(value, '{') and self.pairs[value] + 1 == end:
            if self.commonjs or self.commonjs_object:
                raise ValueError('cannot decide replacement of CommonJS exports')
            self.commonjs_object = True
            for a, b in self._parts(value + 1, end - 1):
                public = self._name(a, quoted=True)
                if public in self.commonjs:
                    raise ValueError(f'cannot decide repeated CommonJS export {public}')
                self.commonjs.add(public)
                self.direct.add(public)
                if a + 1 == b:
                    self.exports.append((public, public))
                elif self._at(a + 1, ':'):
                    if a + 2 == b:
                        raise ValueError('missing CommonJS property value')
                    self._expose(public, a + 2, b)
                elif not self._at(a + 1, '('):
                    raise ValueError('cannot decide CommonJS object exports')
        else:
            raise ValueError('cannot enumerate module.exports without a literal export object')
        return end

    def _members(self, local, seen):
        if local in seen:
            raise ValueError(f'cyclic class alias {local}')
        if local in self.imports or local in ('true', 'false', 'null', 'undefined'):
            return set()
        if local not in self.locals:
            raise ValueError(f'cannot resolve exported local name {local}')
        value = self.locals[local]
        return self._members(value, seen | {local}) if isinstance(value, str) else value

    def _import(self, i):
        """Listed imports may be re-exported without following another file."""
        i += 1
        if i == len(self.tokens):
            raise ValueError('incomplete import')
        if self.tokens[i].kind == 'string':
            return i + 1
        if self._at(i, 'type') and not self._at(i + 1, ',', 'from', '='):
            i += 1
        if not self._at(i, '{', '*'):
            self.imports.add(self._name(i))
            i += 1
            if self._at(i, '='):
                raise ValueError('cannot decide import assignment')
            if self._at(i, ','):
                i += 1
        if self._at(i, '*'):
            if not self._at(i + 1, 'as'):
                raise ValueError('invalid namespace import')
            self.imports.add(self._name(i + 2))
            i += 3
        elif self._at(i, '{'):
            end = self.pairs[i]
            for start, stop in self._parts(i + 1, end):
                if self._at(start, 'type') and stop > start + 1 and not self._at(start + 1, 'as'):
                    start += 1
                self._name(start, quoted=True)
                if start + 1 == stop:
                    self.imports.add(self._name(start))
                elif self._at(start + 1, 'as') and start + 3 == stop:
                    self.imports.add(self._name(start + 2))
                else:
                    raise ValueError('invalid import list')
            i = end + 1
        if not self._at(i, 'from') or i + 1 >= len(self.tokens) or self.tokens[i + 1].kind != 'string':
            raise ValueError('import has no literal module name')
        i += 2
        if self._at(i, 'with', 'assert'):
            if not self._at(i + 1, '{'):
                raise ValueError('invalid import attributes')
            i = self._jump(i + 1)
        return i

    def _names(self):
        i = 0
        while i < len(self.tokens):
            if self._at(i, '@'):
                raise ValueError('cannot decide a decorated declaration')
            if self._at(i, ';'):
                i += 1
            elif self._at(i, 'export'):
                i = self._export(i)
            elif self._at(i, 'import') and not self._at(i + 1, '(', '.'):
                i = self._import(i)
            elif (end := self._commonjs(i)) is not None or (end := self._declaration(i, False)) is not None:
                i = end
            else:
                end = self._end(i, newline=True)
                # Export mutation hidden in an expression/control-flow block
                # cannot be enumerated safely, even if its brackets balance.
                for token in self.tokens[i:end]:
                    if token.kind == 'name' and token.text in ('export', 'exports', 'eval'):
                        raise ValueError(f'cannot decide indirect {token.text}')
                if end == i:
                    raise ValueError('invalid module statement')
                i = end
        for local, public in self.exports:
            self.direct.add(public)
            self.direct.update(f'{public}.{member}' for member in self._members(local, set()))
        return self.direct


def _regex_may_start(before: list[_Token]) -> bool:
    """Whether a "/" after ``before`` starts a regular expression."""
    if not before:
        return True
    last = before[-1]
    if last.kind == "name":
        return last.text in _BEFORE_REGEX
    return last.kind == "punct" and last.text not in ")]<"  # after "}" (a block's end) it does


def _regex_end(text: str, at: int) -> int | None:
    """Just after the regular expression starting at ``at`` and its flags;
    None when the line holds no end (the "/" is a division)."""
    end, in_class = at + 1, False
    while end < len(text) and text[end] != "\n":
        char = text[end]
        if char == "\\":
            end += 2
            continue
        if char == "/" and not in_class:
            return _NAME.match(text, end + 1).end() if _NAME.match(text, end + 1) else end + 1
        in_class = (in_class or char == "[") and char != "]"
        end += 1
    return None


def _streams(tokens: tuple[_Token, ...]):
    """``tokens`` and, recursively, each template substitution in them: each
    a run of code read on its own."""
    yield tokens
    for token in tokens:
        for inner in token.inner:
            yield from _streams(inner)


def _is(tokens: tuple[_Token, ...], at: int, *texts: str) -> bool:
    """Whether the token at ``at`` is punctuation or a name in ``texts``."""
    return 0 <= at < len(tokens) and tokens[at].kind in ("punct", "name") and tokens[at].text in texts


def _quoted_member(tokens: tuple[_Token, ...], at: int) -> bool:
    """Whether the string at ``at`` names a member (`x["name"]`), not an
    array item (`["name"]`, `return ["name"]`)."""
    before = tokens[at - 2] if at >= 2 else None
    return _is(tokens, at - 1, "[") and before is not None and (
        (before.kind == "name" and before.text not in _BEFORE_REGEX) or _is(tokens, at - 2, ")", "]"))


def _key(tokens: tuple[_Token, ...], at: int) -> str | None:
    """The property name at ``at`` when it stands where an object's key does
    (after "{" or ",", as a name or a string), else None."""
    token = tokens[at]
    return token.text if token.kind in ("name", "string") and _is(tokens, at - 1, "{", ",") else None


def _closing(tokens: tuple[_Token, ...], at: int) -> int:
    """The index of the bracket that closes the one at ``at`` (the last
    index when none does)."""
    pairs = {"{": "}", "[": "]", "(": ")"}
    depth = 0
    for index in range(at, len(tokens)):
        if _is(tokens, index, *pairs):
            depth += 1
        elif _is(tokens, index, *pairs.values()):
            depth -= 1
            if depth == 0:
                return index
    return len(tokens) - 1


def _loads(module: str, tokens: tuple[_Token, ...]) -> tuple[set[str], set[str]]:
    """The module names ``module`` loads, and those of them vi.mock or
    vi.doMock names. Read as an allow-list, wherever a use stands (inside a
    template substitution too): a name that can load code may appear only in
    one of these shapes, and any other use of it is CannotAnswer.
    - `import ... from "x"`, `export ... from "x"`, `import "x"`; `import`
      starting a declaration; `import.meta.` url, dirname, filename, env,
      resolve, main, hot or vitest.
    - A call whose whole argument is one quoted name: `import("x")`,
      `require("x")`, `<object>.require("x")`, `req("x")` for a require
      function createRequire makes, and, after any TypeScript type
      arguments, `vi.importActual("x")`, `vi.importMock("x")`, `vi.mock("x", ...)`,
      `vi.doMock("x", ...)`; vi.mock and vi.doMock may name the module by
      `import("x")` instead, and either way it is loaded and mocked.
    - vi is `vi`, any member named vi (`vitest.vi`), or a name vi is
      imported under (`import { vi as v }`); it may stand only as the object
      of a member access (`v.mock`), or in a braces list under its own name
      (`{ vi }`) or renamed there by `as`.
    - `require.resolve` and `req.resolve`; a require function's own
      declaration; the definition of a function of that name; an object key.
    - createRequire imported or destructured under its own name, or called
      as the whole value of a `const`, `let` or `var` of one name, typed or
      not, which makes that name a require function.
    So a computed name, an alias or a reference that is not called refuses
    (`const { doMock } = vi`, `v.doMock(name)`, `vi["mock"](...)`), as do
    import.meta.glob, a direct `eval(...)` call, `Function(...)` and
    `new Function`, a loader reached by a quoted member (`x["require"]`),
    loading node:vm, and loading node:module for anything but createRequire,
    isBuiltin and builtinModules by import or a require call. This reads
    ordinary code; it is not a sandbox. Code written to evade it (eval or
    Function reached through another object or a comma expression,
    process.getBuiltinModule) is not refused."""
    made = _made_requires(module, tokens)
    requires = {"require", *made}
    loads: set[str] = set()
    mocked: set[str] = set()

    def call(stream: tuple[_Token, ...], at: int, start: int, callee: str, *, mock: bool = False) -> None:
        if not _is(stream, at, "("):
            raise _cannot_tell(f"{module} uses {callee} other than to call it")
        argument = stream[at + 1] if at + 1 < len(stream) else None
        if argument is not None and argument.kind == "string" and _is(stream, at + 2, ",", ")"):
            loads.add(argument.text)
            if mock:
                mocked.add(argument.text)
            _module_api(module, stream, start, argument.text, declaration=False)
        elif (mock and _is(stream, at + 1, "import") and _is(stream, at + 2, "(") and at + 3 < len(stream)
              and stream[at + 3].kind == "string" and _is(stream, at + 4, ")") and _is(stream, at + 5, ",", ")")):
            loads.add(stream[at + 3].text)  # vi.mock(import("x")) mocks x as vi.mock("x") does
            mocked.add(stream[at + 3].text)
            _module_api(module, stream, start, stream[at + 3].text, declaration=False)
        else:
            raise _cannot_tell(f"{module} loads files through {callee}() of a computed name")

    vis = _vi_names(tokens)
    for stream in _streams(tokens):
        for at, token in enumerate(stream):
            word, after = token.text, at + 1
            if token.kind == "string":
                if word in _LOADER_WORDS and _quoted_member(stream, at):
                    raise _cannot_tell(f"{module} reaches {word} through a computed member")
                continue
            if token.kind != "name":
                continue
            if word in vis and not _vi_kept(stream, at, alias=word != "vi"):
                raise _cannot_tell(f"{module} uses {'vi' if word == 'vi' else f'{word} (vi)'} other than as the "
                                  "object of a member access")
            if _is(stream, at - 1, "."):  # a member of another object
                owner = stream[at - 2].text if at >= 2 else ""
                if word in _VI_LOADERS or (word in _VI_MOCKS and owner in vis):
                    call(stream, _after_type_arguments(stream, after), at - 2, f"{owner}.{word}",
                         mock=word in _VI_MOCKS)
                elif word == "require" and _is(stream, after, "("):
                    call(stream, after, at - 2, f"{owner}.require")
                continue
            if word == "from":
                if after < len(stream) and stream[after].kind == "string":
                    loads.add(stream[after].text)
                    _module_api(module, stream, at, stream[after].text, declaration=True)
                continue
            if word != "createRequire" and _is(stream, after, ":") and _key(stream, at) is not None:
                continue  # an object key
            if word in requires:
                if (_is(stream, at - 1, "function") or (_is(stream, at - 1, "*") and _is(stream, at - 2, "function"))
                        or (_is(stream, after, "(") and _is(stream, _closing(stream, after) + 1, "{"))):
                    continue  # a function of that name is defined here, not called
                if word in made and _is(stream, at - 1, "const", "let", "var"):
                    continue  # the require function's own declaration
                if not (_is(stream, after, ".") and _is(stream, after + 1, "resolve")):
                    call(stream, after, at, word)
            elif word == "import":
                if after < len(stream) and stream[after].kind == "string":
                    loads.add(stream[after].text)  # import "x"
                elif _is(stream, after, "("):
                    call(stream, after, at, "import")
                elif _is(stream, after, "."):
                    if _is(stream, after + 1, "meta") and _is(stream, after + 2, ".") and _is(stream, after + 3, *_META):
                        continue
                    if _is(stream, after + 3, "glob", "globEager"):
                        raise _cannot_tell(f"{module} loads files through import.meta.glob")
                    raise _cannot_tell(f"{module} uses import.meta other than for {', '.join(sorted(_META))}")
                elif not (after < len(stream) and (stream[after].kind == "name" or _is(stream, after, "{", "*"))):
                    raise _cannot_tell(f"{module} uses import other than to load one quoted name")
            elif (word == "eval" and _is(stream, after, "(")) or (
                    word == "Function" and (_is(stream, after, "(") or _is(stream, at - 1, "new"))):
                raise _cannot_tell(f"{module} runs code it builds ({word})")
    return loads, mocked


def _vi_names(tokens: tuple[_Token, ...]) -> set[str]:
    """"vi" and every name a braces list renames it to (`{ vi as v }`)."""
    names = {"vi"}
    for stream in _streams(tokens):
        for at, token in enumerate(stream):
            if (token.kind == "name" and token.text == "vi" and _braces_item(stream, at)
                    and _is(stream, at + 1, "as") and at + 2 < len(stream) and stream[at + 2].kind == "name"):
                names.add(stream[at + 2].text)
    return names


def _braces_item(tokens: tuple[_Token, ...], at: int) -> bool:
    """Whether the name at ``at`` is an item of a braces list (`{ a, vi }`,
    `{ vi as v }`): right after "{" or ",", with nothing but names, ","
    and ":" back to the "{"."""
    if not _is(tokens, at - 1, "{", ","):
        return False
    index = at - 1
    while index >= 0 and not _is(tokens, index, "{"):
        if not (tokens[index].kind == "name" or _is(tokens, index, ",", ":")):
            return False
        index -= 1
    return index >= 0


def _vi_kept(tokens: tuple[_Token, ...], at: int, *, alias: bool) -> bool:
    """Whether the vi name at ``at`` stands where vi is still seen: as the
    object of a member access (`vi.mock`), or as a braces item under its
    own name or renamed by `as` (`{ vi }`, `{ vi as v }`). A name vi is
    imported under (``alias``) also stands for itself, not vi, as a member
    of another object, an object key, or the name `as` gives."""
    if _is(tokens, at + 1, ".") and at + 2 < len(tokens) and tokens[at + 2].kind == "name":
        return True
    if _braces_item(tokens, at) and (_is(tokens, at + 1, "}", ",") or (
            _is(tokens, at + 1, "as") and _is(tokens, at + 3, "}", ","))):
        return True
    return alias and (_is(tokens, at - 1, ".", "as") or (_is(tokens, at + 1, ":") and _key(tokens, at) is not None))


def _made_requires(module: str, tokens: tuple[_Token, ...]) -> set[str]:
    """The names ``module`` binds to a require function createRequire makes
    (`const req = createRequire(...)`, optionally typed). CannotAnswer for
    any other use of createRequire than that or importing or destructuring
    it under its own name."""
    made: set[str] = set()
    for stream in _streams(tokens):
        for at, token in enumerate(stream):
            if token.kind != "name" or token.text != "createRequire":
                continue
            if _is(stream, at - 1, "{", ",") and _is(stream, at + 1, "}", ","):
                continue  # imported or destructured under its own name
            start = at - 2 if _is(stream, at - 1, ".") else at
            name = _bound_name(stream, start - 1) if _is(stream, at + 1, "(") else None
            if name is None:
                raise _cannot_tell(f"{module} uses createRequire other than to bind the require function it "
                                   "makes to one declared name")
            made.add(name)
    return made


def _bound_name(tokens: tuple[_Token, ...], at: int) -> str | None:
    """The name a `const`, `let` or `var` declares when the token at ``at``
    is its "=", with or without a type annotation (`const req: NodeRequire
    =`); None for anything else (an assignment, a comparison, a second
    declarator, a destructuring pattern)."""
    if not _is(tokens, at, "=") or _is(tokens, at - 1, *"=!<>+-*/%&|^?"):
        return None
    index = at - 1
    while index >= 1 and not _is(tokens, index - 1, "const", "let", "var"):
        if _is(tokens, index, ";") or (_is(tokens, index, "=") and not _is(tokens, index + 1, ">")):
            return None  # another statement or declarator stands between
        index -= 1
    if index < 1 or tokens[index].kind != "name" or not (index == at - 1 or _is(tokens, index + 1, ":")):
        return None
    return tokens[index].text


def _module_api(module: str, tokens: tuple[_Token, ...], at: int, name: str, *, declaration: bool) -> None:
    """CannotAnswer when ``module`` loads ``name`` and that lets it run or
    redirect code the read cannot see: node:vm at all, node:module for
    anything but createRequire, isBuiltin and builtinModules. ``at`` is the
    `from` of a declaration, or the first token of a load call, whose value
    must then be destructured (`const { createRequire } = [await] ...`)."""
    if name in _EVALUATING:
        raise _cannot_tell(f"{module} loads {name}, which runs code it is given")
    if name not in _MODULE_API:
        return
    index = at - 1
    if not declaration:
        index -= _is(tokens, index, "await")
        if not _is(tokens, index, "="):
            index = -1
        index -= 1
    allowed = _is(tokens, index, "}")
    index -= 1
    while allowed and not _is(tokens, index, "{"):
        allowed = index >= 0 and _is(tokens, index, ",", "type", *_MODULE_SAFE)
        index -= 1
    index -= 1
    if declaration and _is(tokens, index, "type"):
        index -= 1
    if not (allowed and _is(tokens, index, *(("import", "export") if declaration else ("const", "let", "var")))):
        raise _cannot_tell(f"{module} loads {name} for more than {', '.join(sorted(_MODULE_SAFE))}")


def _after_type_arguments(tokens: tuple[_Token, ...], at: int) -> int:
    """Just after the TypeScript type arguments (`<...>`) at ``at``; ``at``
    itself when there are none."""
    if not _is(tokens, at, "<"):
        return at
    depth = 0
    for index in range(at, len(tokens)):  # a ">" after "=" is an arrow's, not a bracket
        depth += _is(tokens, index, "<") - (_is(tokens, index, ">") and not _is(tokens, index - 1, "="))
        if depth == 0:
            return index + 1
    return len(tokens)


def _quoted_paths(tokens: tuple[_Token, ...]) -> set[str]:
    """Every quoted text in ``tokens`` that could name a file, except those
    inside the `coverage` option's value, which chooses only the files the
    coverage report covers."""
    skipped: set[int] = set()
    for at in range(len(tokens)):
        if _key(tokens, at) == "coverage" and _is(tokens, at + 1, ":") and _is(tokens, at + 2, "{"):
            skipped.update(range(at + 2, _closing(tokens, at + 2) + 1))
    out = {t.text for at, t in enumerate(tokens) if t.kind == "string" and at not in skipped}
    for token in tokens:
        for inner in token.inner:
            out |= _quoted_paths(inner)
    return {text for text in out if text.strip() and "\n" not in text and len(text) <= _LONGEST_PATH}


def _projects(module: str, entry: str, read) -> list[tuple[str, bytes | None, bool]]:
    """The files a `projects` entry in ``module`` makes vitest load, as
    (path, content, follow): the configuration file it names, or each
    default configuration file and environment file of the folder it names,
    present or not (the first present configuration is the project's).
    vitest reads the entry from its root, the repository root here; the
    folder beside ``module`` is listed too. CannotAnswer for a pattern."""
    entry = entry.replace("<rootDir>", ".")
    if any(c in entry for c in _NOT_PLAIN + "()!"):
        raise _cannot_tell(f"{module} names projects by the pattern {entry}")
    out = []
    for base in dict.fromkeys(("", posixpath.dirname(module))):
        rel = _repository_path(posixpath.join(base, entry))
        if rel is None:
            raise _cannot_tell(f"{module} names the project {entry}, outside the repository")
        content = _optional(read, rel)
        if content is not None or rel.endswith(_SOURCES):  # a configuration file, present or not
            out.append((rel, content, True))
            continue
        for name in _CONFIGS + _ROOT_FILES:
            file = name if rel == "." else f"{rel}/{name}"
            found = _optional(read, file)
            out.append((file, found, name in _CONFIGS))
    return out


def _resolve(module: str, literal: str, read) -> tuple[str | None, bytes | None]:
    """The repository file a quoted ``literal`` in ``module`` names, and its content."""
    for path in _candidates(module, literal):
        found = _optional(read, path)
        if found is not None:
            return path, found
    return None, None


def _candidates(module: str, literal: str) -> list[str]:
    """The repository files a quoted ``literal`` in ``module`` could name."""
    if any(c in literal for c in _NOT_PLAIN + "\n") or ":" in literal or not literal.strip():
        return []
    # "./x" is beside the module, "/x" at the root (as Vite reads it), "x" either.
    here = posixpath.dirname(module)
    bases = [""] if literal.startswith("/") else [here] if literal.startswith(".") else [here, ""]
    out = []
    for base in bases:
        rel = _repository_path(posixpath.join(base, literal.lstrip("/")))
        if rel is None or "node_modules" in rel.split("/"):
            continue
        out.extend(rel + suffix for suffix in _COMPLETIONS)
        # TypeScript sources are imported by the name of the JavaScript they become.
        out.extend(rel[: -len(js)] + ts for js, ts in _COMPILED if rel.endswith(js))
    return list(dict.fromkeys(out))


def _cannot_tell(why: str) -> CannotAnswer:
    error = CannotAnswer("vitest", "support")
    error.args = (f"{error.args[0]}: cannot tell what the tests load: {why}",)
    return error


def _is_tsconfig(path: str) -> bool:
    name = posixpath.basename(path)
    return name.startswith("tsconfig") and name.endswith(".json")


def _keyed(module: str, tokens: tuple[_Token, ...]) -> list[tuple[str, str]]:
    """Each (option, value) of the options that make vitest load a file
    (setupFiles, globalSetup, snapshotSerializers,
    coverage.customProviderModule, projects) in ``tokens``, wherever the
    option stands as an object key (in an inline project too). CannotAnswer
    when a value is not a plain string or a list of them (for `projects`, a
    list item may also be an inline project object, read in place by
    _inline_project), and when code reaches such an option other than as an
    object key: as a member (`config.test.setupFiles`, read, assigned or
    changed) or by a quoted member (`config.test["setupFiles"]`). Also each
    quoted text in the value of an option that may name a module
    (runner, environment, pool, diff, snapshotEnvironment, reporters), which
    is never refused: its value may be a built-in or installed name."""
    values: list[tuple[str, str]] = []
    for at, token in enumerate(tokens):
        key = token.text
        if token.kind not in ("name", "string") or key not in _LOADING_KEYS | _NAMING_KEYS:
            continue
        naming = key in _NAMING_KEYS
        if not naming and (_is(tokens, at - 1, ".") or (token.kind == "string" and _quoted_member(tokens, at))):
            raise _cannot_tell(f"{module} reaches {key} in code")
        if _key(tokens, at) is None:
            continue
        if _is(tokens, at + 1, ",", "}") and not naming:  # shorthand ({ setupFiles }): a value built elsewhere
            raise _cannot_tell(f"{module} sets {key} from a variable")
        if not _is(tokens, at + 1, ":"):
            continue
        start = at + 2
        if naming:
            end = _closing(tokens, start) if _is(tokens, start, "[") else start
            values.extend((key, t.text) for t in tokens[start:end + 1] if t.kind == "string")
            continue
        if start < len(tokens) and tokens[start].kind == "string":
            items, end = [start], start
        elif _is(tokens, start, "["):
            end = _closing(tokens, start)
            items, index = [], start + 1
            while index < end:
                item = tokens[index]
                if item.kind == "string":
                    items.append(index)
                    index += 1
                elif key == "projects" and _is(tokens, index, "{"):
                    close = _closing(tokens, index)
                    _inline_project(module, tokens[index:close + 1])
                    index = close + 1
                else:
                    raise _cannot_tell(f"{module} sets {key} to a list holding something other than "
                                       f"{'plain strings and inline projects' if key == 'projects' else 'plain strings'}")
                if not _is(tokens, index, ",", "]"):
                    raise _cannot_tell(f"{module} sets {key} to a list holding a computed item")
                index += _is(tokens, index, ",")
        else:
            raise _cannot_tell(f"{module} sets {key} to something other than a plain string or a list")
        if end + 1 < len(tokens) and not _is(tokens, end + 1, ",", "}", "]"):
            raise _cannot_tell(f"{module} sets {key} to a computed value")
        values.extend((key, tokens[index].text) for index in items)
    return values


def _inline_project(module: str, tokens: tuple[_Token, ...]) -> None:
    """Refuse an inline project object (``tokens``, its braces included)
    whose paths do not mean what they mean in ``module``: one that sets
    root or dir, or extends anything but true or false. Its setup options
    are read with the rest of ``module``."""
    for at in range(len(tokens)):
        key = _key(tokens, at)
        if key in _MOVING_KEYS and _is(tokens, at + 1, ":", ",", "}"):
            raise _cannot_tell(f"{module} has an inline project that sets {key}")
        if key == "extends" and _is(tokens, at + 1, ":", ",", "}") and not (
                _is(tokens, at + 1, ":") and _is(tokens, at + 2, "true", "false")):
            raise _cannot_tell(f"{module} has an inline project that extends another configuration")


def _extended(module: str, tokens: tuple[_Token, ...], read) -> list[tuple[str, bytes | None, bool]]:
    """Each file the tsconfig ``module`` extends: (path, content, follow)."""
    out = []
    values: list[str] = []
    for at, token in enumerate(tokens):
        if token.kind == "string" and token.text == "extends" and _is(tokens, at + 1, ":"):
            value = tokens[at + 2:_closing(tokens, at + 2) + 1] if _is(tokens, at + 2, "[") else tokens[at + 2:at + 3]
            values += [t.text for t in value if t.kind == "string"]
            break
    for value in values:
        if value.startswith((".", "/")):
            rel = _repository_path(posixpath.join(posixpath.dirname(module), value.lstrip("/"))
                                   if value.startswith(".") else value)
            if rel is None:
                raise _cannot_tell(f"{module} extends {value}, outside the repository")
            names = [rel] if rel.endswith(".json") else [rel, rel + ".json"]
            found = next(((n, c) for n in names if (c := _optional(read, n)) is not None), None)
            out.append((*found, True) if found else (names[-1], None, False))
            continue
        name, rest = _split(value)
        folder = _workspace(name, read)
        if folder is not None:
            rel = f"{folder}/{rest or 'tsconfig.json'}"
            rel = rel if rel.endswith(".json") or _optional(read, rel) is not None else rel + ".json"
            content = _optional(read, rel)
            out.append((rel, content, content is not None))
        elif not _installed(name, read) and (not _PACKAGE_NAME.match(name) or _has_workspaces(read)):
            raise _cannot_tell(f"{module} extends {value}, which no installed package or workspace answers")
    return out


def _workspace_module(module: str, specifier: str, read) -> tuple[str | None, bytes | None]:
    """The repository module a bare ``specifier`` imported or loaded by
    ``module`` is, when a workspace package of the repository answers it;
    (None, None) for Node's own modules and installed packages."""
    name, rest = _split(specifier)
    if name in _BUILTINS or ":" in specifier:  # node:fs, or a module a plugin supplies (virtual:x)
        return None, None
    folder = _workspace(name, read)
    if folder is None:
        if _installed(name, read) or (_PACKAGE_NAME.match(name) and not _has_workspaces(read)):
            return None, None
        raise _cannot_tell(f"{module} loads {specifier}, which no installed package or workspace answers")
    manifest = _json(_optional(read, f"{folder}/package.json"))
    for entry in ([rest] if rest else [*_entries(manifest), "index"]):
        path, content = _resolve(f"{folder}/package.json", entry if entry.startswith("./") else "./" + entry, read)
        if path is not None:
            return path, content
    raise _cannot_tell(f"{module} loads {specifier}, the repository's package at {folder}, "
                       "whose entry is not in the repository")


def _split(specifier: str) -> tuple[str, str]:
    """A bare specifier's package name and the path inside the package."""
    parts = specifier.split("/")
    size = 2 if specifier.startswith("@") else 1
    return "/".join(parts[:size]), "/".join(parts[size:])


def _json(content: bytes | None) -> dict:
    try:
        data = json.loads(content.decode("utf-8")) if content is not None else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _locked(name: str, read) -> dict | None:
    """npm's lockfile entry for the package ``name``, if any."""
    for lockfile in ("package-lock.json", "npm-shrinkwrap.json"):
        entry = (_json(_optional(read, lockfile)).get("packages") or {}).get(f"node_modules/{name}")
        if isinstance(entry, dict):
            return entry
    return None


def _declared(name: str, read) -> str | None:
    """The version the root package.json gives the dependency ``name``."""
    manifest = _json(_optional(read, "package.json"))
    for field in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        version = (manifest.get(field) or {}).get(name) if isinstance(manifest.get(field), dict) else None
        if isinstance(version, str):
            return version
    return None


def _workspace_patterns(read) -> list[str]:
    workspaces = _json(_optional(read, "package.json")).get("workspaces")
    patterns = workspaces.get("packages") if isinstance(workspaces, dict) else workspaces
    patterns = list(patterns) if isinstance(patterns, list) else []
    pnpm = _optional(read, "pnpm-workspace.yaml")
    if pnpm is not None:
        patterns += re.findall(r"""(?m)^\s*-\s*["']?([^"'\s#]+)""", pnpm.decode("utf-8", "replace"))
    return [p for p in patterns if isinstance(p, str)]


def _has_workspaces(read) -> bool:
    return bool(_workspace_patterns(read))


def _workspace(name: str, read) -> str | None:
    """The repository folder of the package ``name`` when the package manager
    links it from the repository (a workspace, or a file: or link:
    dependency), else None."""
    entry = _locked(name, read)
    if entry is not None and entry.get("link"):
        return _repository_path(str(entry.get("resolved", "")))
    version = _declared(name, read) or ""
    if version.startswith(("file:", "link:")):
        return _repository_path(version.split(":", 1)[1])
    for pattern in _workspace_patterns(read):
        pattern = pattern.strip().rstrip("/")
        if pattern.endswith("/*") and not any(c in pattern[:-2] for c in "*?{}[]!"):
            folders = [f"{pattern[:-2]}/{name.rsplit('/', 1)[-1]}"]
        else:
            folders = [] if any(c in pattern for c in "*?{}[]!") else [pattern]
        for folder in folders:
            if _json(_optional(read, f"{folder}/package.json")).get("name") == name:
                return _repository_path(folder)
    return None


def _installed(name: str, read) -> bool:
    """Whether ``name`` is a package the package manager installs from
    outside the repository."""
    entry = _locked(name, read)
    if entry is not None:
        return not entry.get("link")
    version = _declared(name, read)
    if version is not None:
        return not version.startswith(("file:", "link:", "workspace:"))
    for lockfile in ("pnpm-lock.yaml", "yarn.lock", "bun.lock"):
        content = _optional(read, lockfile)
        if content is not None and re.search(rf"""(?m)(?:^|[\s'"/]){re.escape(name)}@(?!workspace:|link:|file:)""",
                                             content.decode("utf-8", "replace")):
            return True
    return False


def _entries(manifest: dict) -> list[str]:
    """A package's entry modules, in the order its manifest gives them."""
    exports = manifest.get("exports")
    if isinstance(exports, dict) and "." in exports:
        exports = exports["."]
    out = []

    def strings(value) -> None:
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, dict):
            for key in ("source", "import", "module", "development", "node", "default", "require"):
                if key in value:
                    strings(value[key])
    strings(exports)
    out += [manifest[f] for f in ("module", "main") if isinstance(manifest.get(f), str)]
    return list(dict.fromkeys(out))


#: The program node runs: vitest's own node API, loaded from the project's
#: installation, runs the named tests under the configuration DekSpec chose
#: and writes, per named file, what vitest collected and how each test ended.
#: The run caches nothing (no results cache, no module cache, Vite's cache in
#: a temporary folder) and names exactly the named tests: each file's own
#: name filter is kept and narrowed to those tests.
_DRIVER = r"""
import { readFileSync, writeFileSync } from "node:fs";
import { relative, sep } from "node:path";
import { pathToFileURL } from "node:url";

const input = JSON.parse(readFileSync(process.argv[2], "utf8"));
const out = { modules: [], errors: [], specs: [], setup: [] };
const errorData = (e) => ({ name: String(e?.name || "Error"), message: String(e?.message || e),
  stack: String(e?.stack || ""), stacks: e?.stacks || [] });
const rel = (file) => relative(input.root, file).split(sep).join("/");
const spaced = (task) => (task.suite ? spaced(task.suite) + " " : "") + task.name;
const plain = (p) => (p == null || p === "" ? null : p instanceof RegExp
  ? new RegExp(p.source, p.flags.replace(/[gy]/g, "")) : new RegExp(String(p)));
const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
let vitest;
try {
  const { createVitest } = await import(pathToFileURL(input.entry).href);
  vitest = await createVitest("test", {
    root: input.root, config: input.config, run: true, watch: false, reporters: [{}],
    cache: false, passWithNoTests: true,
    experimental: { fsModuleCache: false, fsModuleCachePath: input.cache + "/modules" },
  }, { cacheDir: input.cache + "/vite" });
  const files = Object.keys(input.names);
  const found = files.length ? await vitest.globTestSpecifications(files.map((f) => input.root + "/" + f)) : [];
  const filters = new Map();
  const specs = [];
  for (const spec of found) {
    const file = rel(spec.moduleId);
    if (!files.includes(file) || filters.has(spec.moduleId)) continue;
    out.specs.push(file);
    out.setup.push(...(spec.project.config.setupFiles || []).map(rel));
    const global = spec.project.config.globalSetup || [];
    out.setup.push(...(Array.isArray(global) ? global : [global]).map(rel));
    const configured = plain(spec.project.config.testNamePattern);
    filters.set(spec.moduleId, configured);
    const names = input.names[file];
    if (names === null) { specs.push(spec); continue; }
    const mine = "(?:" + names.map((parts) => escape(parts.join(" "))).join("|") + ")$";
    const pattern = configured
      ? new RegExp(`^(?=${mine})(?=[\\s\\S]*?(?:${configured.source}))`, configured.flags)
      : new RegExp("^" + mine);
    specs.push(spec.project.createSpecification(spec.moduleId, { testNamePattern: pattern }, spec.pool));
  }
  const result = await vitest.runTestSpecifications(specs);
  for (const error of result.unhandledErrors || []) out.errors.push(errorData(error));
  for (const module of result.testModules) {
    const configured = filters.get(module.moduleId);
    const entry = { file: rel(module.moduleId), errors: module.errors().map(errorData), tests: [] };
    for (const test of module.children.allTests()) {
      const ended = test.result();
      const diagnostic = test.diagnostic();
      const around = [];
      for (let parent = test.parent; parent; parent = parent.type === "module" ? null : parent.parent) {
        around.push(...(parent.errors ? parent.errors() : []).map(errorData));
      }
      entry.tests.push({
        name: test.fullName, mode: test.options.mode, fails: !!test.options.fails, state: ended.state,
        retries: diagnostic ? diagnostic.retryCount : 0, around,
        setupFailed: Object.values(test.task.result?.hooks || {}).includes("fail"), errors: (ended.errors || []).map(errorData),
        filtered: !!configured && !configured.test(spaced(test.task)),
      });
    }
    out.modules.push(entry);
  }
} catch (error) {
  out.errors.push(errorData(error));
}
writeFileSync(input.output, JSON.stringify(out));
if (vitest) await vitest.close().catch(() => {});
process.exit(0);
"""
