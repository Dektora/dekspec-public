#!/usr/bin/env python3
"""Repo-local wrapper for the checked-in project-board surfaces.

Argument handling separates FLAGS from POSITIONALS before deciding anything, so
`--status cas` and `cas --status` mean the same thing. The previous version
matched exact argv shapes, which made selector-after-flag an error even though
SKILL.md documented it as the example.

A bare positional runs the classification ladder in `classify()`. The ordering
there is deliberate and the comments explain why; the short version is that a
board name is a tiny closed set this tool controls and advertises, so it wins
over an open-ended path, and an unrecognised short token is REFUSED rather than
guessed at -- silently turning a typo'd board name into a work item is the one
failure this ladder exists to prevent.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PYTHON = sys.executable
LS_SCRIPT = HERE / "prj_mgr_ls.py"
STATUS_SCRIPT = HERE / "prj_mgr_status.py"
SYNC_SCRIPT = HERE / "sync_project_snapshot.py"
BOOTSTRAP_SCRIPT = HERE / "bootstrap_beads.py"
WHERE_SCRIPT = HERE / "beads_workspace.py"
INGEST_SCRIPT = HERE / "ingest_plan.py"
ITEMS_SCRIPT = HERE / "prj_mgr_items.py"

#: Any PM bead id. `cb-` is included ON PURPOSE so a code bead is recognised
#: and refused with an explanation, rather than falling through to the
#: ambiguous branch and being offered up as ingestable text.
BEAD_ID_RE = re.compile(r"^(iss|ds|cb)-[A-Za-z0-9.-]+$")

#: Above this length a single token is prose, not a selector.
TEXT_LEN = 80

HELP_TEXT = """Usage:
  project-board                                  list the project registry
  project-board --ls
  project-board --status [<project>]             one board, or all
  project-board --sync   [<project>]             regenerate snapshots (WRITES)
  project-board --items  [<project>] [--open] [--ready] [--phase N] [--priority-max N]
                                           each bead in full, grouped by phase
                                           add --compact for one line per bead
  project-board --where                          resolved bead workspaces, as JSON
  project-board --bootstrap [--dekspec]          create the br workspaces
                                           default: one, issues only
                                           --dekspec: three (code/issue/dekspec)
  project-board --ingest <file|text> [--into <project> | --new-project [name]]
  project-board --adopt <bead-id>... --into <bead-id>
  project-board --at PATH                 target repository (default cwd)
  project-board --help

  <project> may be the directory name or its alias, before or after the flag.

Bare argument, no flag:
  project-board <project>            -> --status
  project-board <file>               -> --ingest
  project-board <several words...>   -> --ingest as text
  project-board <bead-id>            -> refused, with a pointer to br show / --adopt
  project-board <unknown token>      -> refused, with the known boards listed

Working docs:
  docs/prj-mgr/<state>/<project>
  docs/prj-mgr/<state>/<project>/.scratch     ingest plans (gitignored)
"""


def _run(cmd: list[str]) -> int:
    # Flush first. A child writes straight to the shared fd while this process
    # buffers its own prints whenever stdout is not a tty, so without this the
    # child's output overtakes anything printed above it -- which made the
    # INGEST REQUEST header land *after* the context JSON it introduces.
    sys.stdout.flush()
    sys.stderr.flush()
    return int(subprocess.run(cmd, cwd=_repo_root()).returncode)


def _known_projects() -> list[tuple[str, str]]:
    """(directory name, alias) for every board, or [] if discovery fails."""
    try:
        sys.path.insert(0, str(HERE))
        from sync_project_snapshot import (  # noqa: PLC0415
            STATE_BUCKETS,
            _bucket_project_dirs,
            _project_alias,
        )

        return [(d.name, _project_alias(d)) for d in _bucket_project_dirs(STATE_BUCKETS)]
    except Exception:
        return []


def _is_project(token: str) -> bool:
    return any(token in pair for pair in _known_projects())


def _repo_root() -> Path:
    try:
        sys.path.insert(0, str(HERE))
        from beads_workspace import repo_root  # noqa: PLC0415

        return repo_root(Path.cwd())
    except Exception:
        return Path.cwd()


def resolve_source(token: str) -> Path | None:
    """A source path may be given relative to the cwd OR to the repo root.

    Sub-scripts run with a different cwd than the caller, so a bare
    `docs/foo.md` has to be pinned to an absolute path here or it evaporates on
    hand-off. Trying the repo root as well means the command works from any
    subdirectory, which is how anyone actually types it.
    """
    for candidate in (Path(token), _repo_root() / token):
        if candidate.is_file():
            return candidate.resolve()
    return None


def classify(tokens: list[str]) -> tuple[str, str]:
    """Classify a bare (flagless) argument list into (action, payload).

    Order is load-bearing:

    0. more than one token, or an embedded newline -> prose. A board name never
       contains whitespace, so nothing below could match anyway.
    1. a board name or alias -> status. Checked BEFORE the filesystem because
       it is a small closed set this tool prints at the user, while a path is
       open-ended; and because a bare positional already meant "selector" in
       the old grammar, so this preserves it.
    2. an existing file -> ingest. Real paths carry `/` or `.` and so never
       reach step 1 by accident.
    3. a bead id -> refused. Decomposing an id as prose is nonsense, and
       silently doing it would be worse than an error.
    4. long, or containing whitespace -> prose.
    5. anything else -> refused. A short unknown token is far more likely a
       typo'd board name than a work item worth tracking.
    """
    joined = " ".join(tokens)
    if len(tokens) > 1 or "\n" in joined:
        return "ingest", joined

    token = tokens[0]
    if _is_project(token):
        return "status", token
    resolved = resolve_source(token)
    if resolved is not None:
        return "ingest", str(resolved)
    if BEAD_ID_RE.match(token):
        return "bead", token
    if len(token) > TEXT_LEN or re.search(r"\s", token):
        return "ingest", token
    return "ambiguous", token


class Request:
    """A resolved invocation: one action, plus whatever it needs."""

    def __init__(self, action: str, selector: str | None = None,
                 source: str | None = None, into: str | None = None,
                 new_project: str | None = None, beads: list[str] | None = None,
                 passthrough: list[str] | None = None):
        self.action = action
        self.selector = selector
        self.source = source
        self.into = into
        self.new_project = new_project
        self.beads = beads or []
        self.passthrough = passthrough or []


VALUE_FLAGS = {"--into", "--new-project", "--phase", "--priority-max", "--width"}
BARE_FLAGS = {"--ls", "--status", "--sync", "--where", "--bootstrap", "--help",
              "--independent", "--dekspec",
              "--ingest", "--adopt", "--items", "--open", "--ready", "--compact",
              "--brief", "--full", "-h"}

#: Flags that only mean anything to `--items`, forwarded verbatim.
ITEM_FLAGS = ("--full", "--open", "--ready", "--compact", "--brief", "--phase",
              "--priority-max", "--width")


def parse_args(argv: list[str]) -> Request:
    flags: dict[str, str | None] = {}
    positionals: list[str] = []

    index = 0
    while index < len(argv):
        token = argv[index]
        if token in VALUE_FLAGS:
            value = None
            if index + 1 < len(argv) and not argv[index + 1].startswith("--"):
                value = argv[index + 1]
                index += 1
            flags[token] = value
        elif token in BARE_FLAGS:
            flags[token] = None
        elif token.startswith("--"):
            raise SystemExit(f"unknown flag: {token}\n\n{HELP_TEXT}")
        else:
            positionals.append(token)
        index += 1

    if "--help" in flags or "-h" in flags:
        return Request("help")
    if "--bootstrap" in flags:
        # Default is the one-workspace, issues-only layout. --dekspec selects
        # the three-workspace ADR-052 layout. Passing neither leaves the mode
        # unset, which lets bootstrap_beads.py treat an existing repo as a
        # no-op rather than a conflict.
        mode: list[str] = []
        if "--dekspec" in flags:
            mode = ["--mode", "dekspec"]
        elif "--independent" in flags:
            mode = ["--mode", "independent"]
        return Request("bootstrap", passthrough=mode)
    if "--where" in flags:
        return Request("where")

    if "--items" in flags:
        if len(positionals) > 1:
            raise SystemExit(f"expected at most one project selector, got {positionals}")
        forwarded: list[str] = []
        for flag in ITEM_FLAGS:
            if flag in flags:
                forwarded.append(flag)
                if flags[flag] is not None:
                    forwarded.append(str(flags[flag]))
        return Request("items", selector=positionals[0] if positionals else None,
                       passthrough=forwarded)

    if "--adopt" in flags:
        into = flags.get("--into")
        if not into:
            raise SystemExit("--adopt needs --into <bead-id> naming the parent bead")
        if not positionals:
            raise SystemExit("--adopt needs at least one bead id to adopt")
        return Request("adopt", beads=positionals, into=into)

    if "--ingest" in flags or "--new-project" in flags:
        source = " ".join(positionals) if positionals else None
        if not source:
            raise SystemExit("--ingest needs a file path or some text to ingest")
        # Pin a single-token file source to an absolute path for the same reason
        # the ladder does: sub-scripts run from a different cwd.
        if len(positionals) == 1 and (found := resolve_source(positionals[0])) is not None:
            source = str(found)
        # "" means "new board, name it yourself"; None means the flag is absent.
        # `flags.get(k, "")` cannot express that -- a present-but-valueless flag
        # is stored as None, which read as "absent" and silently downgraded the
        # request to target-mode `detect`.
        if "--new-project" in flags:
            new_project = flags["--new-project"] or ""
        else:
            new_project = None
        return Request("ingest", source=source, into=flags.get("--into"),
                       new_project=new_project)

    if "--status" in flags or "--sync" in flags:
        if "--status" in flags and "--sync" in flags:
            raise SystemExit("--status and --sync are mutually exclusive")
        if len(positionals) > 1:
            raise SystemExit(f"expected at most one project selector, got {positionals}")
        action = "status" if "--status" in flags else "sync"
        return Request(action, selector=positionals[0] if positionals else None)

    if "--ls" in flags:
        return Request("ls")

    if not positionals:
        return Request("ls")

    action, payload = classify(positionals)
    if action == "status":
        return Request("status", selector=payload)
    if action == "ingest":
        return Request("ingest", source=payload)
    if action == "bead":
        raise SystemExit(
            f"{payload} is a bead id, not a project or a document.\n"
            f"  inspect it:            br show {payload}\n"
            f"  put it on a board:     project-board --adopt {payload} --into <phase-bead-id>"
        )
    known = _known_projects()
    listed = ", ".join(sorted({f"{name} ({alias})" for name, alias in known})) or "none"
    raise SystemExit(
        f"'{payload}' is not a board, a file, or long enough to be a work item.\n"
        f"  known boards: {listed}\n"
        f"  to ingest it as a one-line item anyway: project-board --ingest '{payload}'"
    )


def dispatch(request: Request) -> int:
    if request.action == "help":
        print(HELP_TEXT)
        return 0
    if request.action == "ls":
        return _run([PYTHON, str(LS_SCRIPT)])
    if request.action == "bootstrap":
        # `--at` is mandatory here. bootstrap_beads.py defaults to the cwd, and
        # _run sets cwd=_repo_root(), so omitting it created three br workspaces inside
        # the skill's own scripts directory instead of at the repo root.
        cmd = [PYTHON, str(BOOTSTRAP_SCRIPT), "--at", str(_repo_root())]
        return _run(cmd + request.passthrough)
    if request.action == "where":
        return _run([PYTHON, str(WHERE_SCRIPT)])
    if request.action in {"status", "sync"}:
        script = STATUS_SCRIPT if request.action == "status" else SYNC_SCRIPT
        cmd = [PYTHON, str(script)]
        if request.selector:
            cmd.append(request.selector)
        return _run(cmd)
    if request.action == "items":
        cmd = [PYTHON, str(ITEMS_SCRIPT)]
        if request.selector:
            cmd.append(request.selector)
        return _run(cmd + request.passthrough)
    if request.action == "adopt":
        return _run([PYTHON, str(INGEST_SCRIPT), "adopt", *request.beads,
                     "--into", str(request.into)])
    if request.action == "ingest":
        return _ingest_handoff(request)
    raise SystemExit(f"unknown action: {request.action}")


def _ingest_handoff(request: Request) -> int:
    """Emit the ingest brief: the source, the target, and the tracker facts.

    Ingest is the one mode whose hard part -- deciding what the work items ARE --
    is judgement, not computation. This wrapper does not attempt it. It resolves
    the source and target deterministically, prints the facts a decomposition
    has to respect, and hands off; SKILL.md tells the model what to do next.
    Every subsequent step (validate, render, apply) is back in script hands.
    """
    source = str(request.source)
    is_file = Path(source).is_file()  # already absolute when it came via the ladder
    mode = "new" if request.new_project is not None else ("existing" if request.into else "detect")

    print("INGEST REQUEST")
    print(f"  source-kind : {'file' if is_file else 'text'}")
    print(f"  source      : {source if is_file else repr(source[:200])}")
    print(f"  target-mode : {mode}")
    if request.into:
        print(f"  into        : {request.into}")
    if request.new_project:
        print(f"  project-name: {request.new_project}")
    print()
    cmd = [PYTHON, str(INGEST_SCRIPT), "context"]
    if request.into:
        cmd += ["--into", request.into]
    return _run(cmd)


def _main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--at" in argv:
        idx = argv.index("--at")
        if idx + 1 >= len(argv):
            print('error: "--at needs a path"')
            return 2
        os.chdir(Path(argv[idx + 1]).resolve())
        argv = argv[:idx] + argv[idx + 2:]
    request = parse_args(argv)
    return dispatch(request)


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        print(f"error: {json.dumps(str(exc.code).split(chr(10))[0])}")
        return 2
    except OSError as exc:
        print(f"error: {json.dumps(str(exc))}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
