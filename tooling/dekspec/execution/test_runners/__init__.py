"""Hides each test runner and its tests' language: how it starts, what it prints, how a test is named, found, skipped or marked, why a failure failed, how test and skeleton source read, which files steer it, and how a clean checkout is made able to run it.
Public: Adapter (one subclass per runner; its name is a condition's verify key, as `pytest:`, and its test_files says in words which files hold its tests), register(adapter), adapter_for(name) -> Adapter | None, runners() -> the registered names in registration order (pytest's first), skeleton(path, source) -> Skeleton | None, CannotAnswer, and the values Run (with Run.evidence()), Outcome, Source, Support, Skeleton.
Callers never know which runner or language is behind a condition: they pass test names, a project and a read(path) -> bytes | None function, and get facts: each test's result in DekSpec's one vocabulary and the run's own faults (all the red check judges), the account in the runner's words (only evidence quotes it, never parsed), a test's text, bases and expected-failure mark, the support files closed and bound, a skeleton's names and note, the program, and whether the runner can run here. DekSpec alone, in Run.evidence(), turns facts into the recorded status, words and detail, so "only a pass is a pass" (BR 68 a) is decided once for every runner.
Designed away: an unknown runner is None (the caller refuses, naming it); a brief with no condition naming tests is refused listing runners(), so no caller names a runner it supports; a file that is not the runner's test file is None, and accept refuses naming the condition, the test and the runner and quoting test_files (for pytest "a file ending in .py"), so no caller words a runner's file rule; an unreadable test is an empty Source, which DekSpec judges new (BR 26); a skeleton language no adapter reads is None (unchecked); a run that reported no test has no outcome, recorded indeterminate unless it failed. Kept apart: a fault of the run is never a test's outcome and a test's line is never a fault, so no check merges the two; and a question an adapter cannot answer raises CannotAnswer naming runner and question, and the asking check fails, never passes.
Alternatives: fine-grained facts composed by callers (leaks node syntax and config sections); callers that must already know a runner's name to ask adapter_for (the no-tests refusal would have to write pytest itself, or read the registry's internals); a reason in place of file_of's None, or accept naming the suffix itself (one answer meaning two things, or a runner rule outside the adapter, O-10); one judge per runner owning red/guard/evidence policy, or an adapter-built evidence entry (repeats BR 68 a in every adapter and leaks DekSpec's record format into it); one problems list for user and checks alike (merges run faults with tests' lines, so the red check must parse wording). Fact-reporting adapters behind an open registry won: callers stay runner-blind, a new runner is one subclass, and the account stays the runner's own only because each runner words and orders its report its own way and pytest's evidence detail must stay as it was (O-1).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import singledispatch
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dekspec.execution.engine import ExecutionError

if TYPE_CHECKING:
    from dekspec.execution.settings import ExecutionSettings

__all__ = [
    "Adapter",
    "CannotAnswer",
    "Outcome",
    "Run",
    "Skeleton",
    "Source",
    "Support",
    "adapter_for",
    "register",
    "runners",
    "skeleton",
]

#: read(path) -> the bytes of a repository-relative file, None when it is absent.
Read = Callable[[str], "bytes | None"]

#: Results evidence names as they are; every other result of a test that ran is "failed".
_NOT_FAILED = ("passed", "skipped", "xfail")
#: Evidence fields DekSpec owns: a runner's fact of the same name never replaces one.
_OWN_FIELDS = ("id", "kind", "status", "nodes", "detail", "plugins_in_repo")


class CannotAnswer(ExecutionError):
    """An adapter cannot answer a question. The message names the runner and
    the question (the Adapter method's name); the check that asked fails."""

    def __init__(self, runner: str, question: str) -> None:
        super().__init__(f"test runner {runner} cannot answer {question}")
        self.runner = runner
        self.question = question


@dataclass(frozen=True)
class Outcome:
    """What happened to one test. ``test`` is the runner's own name for a
    test it ran or kept from running, or a named test it found nothing for.
    ``of`` is the named test this outcome answers for when that is not
    ``test`` itself (a case of it), "" otherwise. ``result`` is DekSpec's
    word, the same for every runner: "passed" (ran and passed the first
    time), "genuine-red" (failed on its own assertion), "skipped" (skipped
    or pending, however marked), "xfail" (the runner ran it as an expected
    failure, however marked, whatever it did), a word naming another failure,
    such as "setup-error", "import-error", "timeout",
    "other-exception:<type>" or a pass only on a retry, or, when ``ran`` is
    False, why it did not run (such as "not-found", "deselected" or
    "excluded by configuration"). Callers judge a test by this value alone."""

    test: str
    result: str
    ran: bool = True
    of: str = ""


@dataclass(frozen=True)
class Run:
    """One run of a condition's named tests, as facts.

    ``outcomes``: in the runner's order, one per test the runner ran or kept
    from running for the named tests, and one (ran=False) per named test it
    found nothing for; empty only when the runner reported nothing about the
    tests (it could not start, timed out or left no report).
    ``faults``: what went wrong with the run as a whole and with no single
    test, one phrase each (a broken configuration, a collection error, an
    exit the runner itself calls abnormal, a timeout, no report); never a
    line about one test, which is an outcome. The red check reads outcomes
    and faults only, and fails on any fault, naming it.
    ``account``: the run as the user reads it, in the runner's own order and
    words: empty when the run was clean, and at least one line when there is
    a fault or an outcome that is not a pass. Only evidence reads it, and
    quotes it; no check parses it. ``failed``: the run as a whole failed (it
    timed out, or the runner's own exit contradicts its report).
    ``plugins``: the repository files the run loaded to extend the runner,
    beyond the support files. ``facts``: the runner's own record (for pytest
    its exit code, duration and output tail), kept with the evidence and
    never judged."""

    outcomes: tuple[Outcome, ...] = ()
    faults: tuple[str, ...] = ()
    account: tuple[str, ...] = ()
    failed: bool = False
    plugins: tuple[str, ...] = ()
    facts: Mapping[str, Any] = field(default_factory=dict)

    def evidence(self) -> dict[str, Any]:
        """The condition's evidence entry DekSpec records for this run,
        without its id and kind, made the same way for every runner.

        ``status``: "indeterminate" when there is no outcome and the run did
        not fail; else "failed" when the run failed or a test that ran
        failed (a result other than "passed", "skipped" or "xfail"); else
        "not-run" when there is a fault, an account line or an outcome that
        is not a pass; else "passed". ``nodes`` (only when there is an
        outcome), in outcome order: each test that ran by its word, its
        result when that is "passed", "skipped" or "xfail" and "failed" for
        any other; and each named test none of whose outcomes ran, once, as
        "not-run". A case kept from running is not listed by itself.
        ``detail``: the account joined by "; ", or "<n> node(s) passed" for
        n listed nodes when the account is empty. ``plugins_in_repo`` (only
        when there is an outcome): the plugins, as a list. Then each fact,
        except one named like a field above, which never replaces DekSpec's
        own."""
        entry: dict[str, Any] = {}
        if not self.outcomes:
            entry["status"] = "failed" if self.failed else "indeterminate"
        elif self.failed or any(o.ran and o.result not in _NOT_FAILED for o in self.outcomes):
            entry["status"] = "failed"
        elif (self.faults or self.account
              or any(not o.ran or o.result != "passed" for o in self.outcomes)):
            entry["status"] = "not-run"
        else:
            entry["status"] = "passed"
        nodes: dict[str, str] = {}
        if self.outcomes:
            ran = {o.of or o.test for o in self.outcomes if o.ran}
            for outcome in self.outcomes:
                named = outcome.of or outcome.test
                if outcome.ran:
                    nodes[outcome.test] = outcome.result if outcome.result in _NOT_FAILED else "failed"
                elif named not in ran and named not in nodes:
                    nodes[named] = "not-run"
            entry["nodes"] = nodes
        entry["detail"] = "; ".join(self.account) or f"{len(nodes)} node(s) passed"
        if self.outcomes:
            entry["plugins_in_repo"] = list(self.plugins)
        for name, value in self.facts.items():
            if name not in entry and name not in _OWN_FIELDS:
                entry[name] = value
        return entry


@dataclass(frozen=True)
class Source:
    """One test as written. ``text`` is the test's own source (its markers
    included), equal between two versions exactly when the test is unchanged;
    None when the test is not in the file or the file cannot be read, and
    DekSpec then never judges it unchanged. ``bases`` are the `Basis:`
    declarations that apply to it, verbatim. ``expected_failure``: the test
    carries an expected-failure mark, however written, even one switched off
    or conditional (BR 9)."""

    text: str | None = None
    bases: tuple[str, ...] = ()
    expected_failure: bool = False


@dataclass(frozen=True)
class Support:
    """The files that steer a set of tests. ``closed``: repository paths the
    builder may not change, including ones that would take effect if added.
    ``bound``: entry → content digest bound to the evidence; an entry is a
    path, or a path, "#" and a part name when only part of the file counts."""

    closed: frozenset[str] = frozenset()
    bound: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Skeleton:
    """A skeleton as its language reads it: its public ``names``, its
    interface ``note`` ("" when it has none), and ``problem``, why the source
    could not be read (names and note are then empty)."""

    names: frozenset[str] = frozenset()
    note: str = ""
    problem: str | None = None


class Adapter:
    """DekSpec's support for one test runner. Subclass it, set ``name`` and
    answer the questions below; ``register`` an instance. A question a
    subclass does not answer refuses with CannotAnswer naming the runner and
    the question, except ``skeleton``, whose default is None (unchecked)."""

    #: The runner's name: the verify key of a condition that names its tests.
    name: str = ""

    #: Which files hold this runner's tests, in words a refusal quotes as
    #: they are (for pytest "a file ending in .py"). When ``file_of`` answers
    #: None, accept refuses the condition naming it, the test and the runner,
    #: and quoting these words; "" (the default) quotes nothing, and the
    #: refusal still names the condition, the test and the runner.
    test_files: str = ""

    def file_of(self, test: str) -> str | None:
        """The repository-relative file that holds ``test`` (a test name as a
        brief writes it), or None when that file is not one of this runner's
        test files (accept then refuses the condition, quoting ``test_files``)."""
        raise CannotAnswer(self.name, "file_of")

    def run(self, tests: Sequence[str], *, project: Path, settings: ExecutionSettings,
            timeout: int, checkout: Path | None = None) -> Run:
        """Run the named tests once, stopping after ``timeout`` seconds, and
        report them. ``checkout`` None runs them in the project's working
        tree, as evidence does. A checkout is a directory outside it holding
        one commit's files and nothing else, as the red check uses: the
        adapter first makes it able to run its tests with the project's
        environment. Writes nothing in the project."""
        raise CannotAnswer(self.name, "run")

    def source(self, test: str, read: Read) -> Source:
        """``test`` (the runner's own name for it) as written in the files
        ``read`` returns; an empty Source when it cannot be found or read."""
        raise CannotAnswer(self.name, "source")

    def support(self, paths: Sequence[str], read: Read) -> Support:
        """The support of the tests in, or beside, ``paths`` (repository
        files), reading content through ``read``."""
        raise CannotAnswer(self.name, "support")

    def skeleton(self, path: str, source: bytes) -> Skeleton | None:
        """``source`` of the skeleton at ``path`` read as this runner's
        language; None when this adapter does not read that language."""
        return None

    def program(self, project: Path, settings: ExecutionSettings) -> str:
        """The program that runs this runner's tests in ``project``, as the
        evidence records it (for pytest, the interpreter)."""
        raise CannotAnswer(self.name, "program")

    def ready(self, project: Path, settings: ExecutionSettings) -> str | None:
        """None when this runner can run in ``project``; otherwise why not."""
        raise CannotAnswer(self.name, "ready")


def register(adapter: Adapter) -> None:
    """Put ``adapter`` behind every condition keyed by ``adapter.name``.
    A new name joins the end of the registration order; an adapter of a name
    already registered replaces that one, in its place. pytest's is
    registered first, from the start; a test or a later outcome adds one
    without changing a caller."""
    _registry()[adapter.name] = adapter


def adapter_for(name: str) -> Adapter | None:
    """The adapter registered under ``name``; None when there is none."""
    return _registry().get(name)


def runners() -> tuple[str, ...]:
    """The names of the registered adapters, in registration order: pytest's
    first, then each later name where ``register`` first put it. These are
    the runners DekSpec supports; accept's refusal of a lean brief with no
    condition that names tests lists them. A snapshot: register again, ask
    again."""
    return tuple(_registry())


def skeleton(path: str, source: bytes) -> Skeleton | None:
    """The skeleton as read by the first adapter, in registration order,
    whose ``skeleton`` reads its language (does not answer None); None when
    no adapter reads it, which the skeleton checks report as `unchecked`."""
    for adapter in tuple(_registry().values()):
        read = adapter.skeleton(path, source)
        if read is not None:
            return read
    return None


# The registry, in registration order: a dict keeps a replaced name in its place.
_ADAPTERS: dict[str, Adapter] = {}


def _registry() -> dict[str, Adapter]:
    """The registry, with pytest's adapter first and vitest's after it from
    the first question on."""
    if not _ADAPTERS:
        from dekspec.execution.test_runners._pytest_adapter import PytestAdapter
        from dekspec.execution.test_runners._vitest_adapter import VitestAdapter

        _ADAPTERS[PytestAdapter.name] = PytestAdapter()
        _ADAPTERS[VitestAdapter.name] = VitestAdapter()
    return _ADAPTERS


@singledispatch
def _protected_paths(adapter, paths, read):
    """Internal guard composition: authored files plus runner support.

    A runner can keep its package inputs open without exposing file formats
    to the guard. The default preserves every pre-existing adapter's closure.
    """
    return set(paths) | set(adapter.support(paths, read).closed)
