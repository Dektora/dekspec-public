#!/usr/bin/env python3
"""Create a bead in the `br` tracker from a structured JSON bead spec.

`/write-beads` Creation sequence asks the model, in prose, to hand-author a
`br create` invocation followed by three `br update` heredocs (`--description`,
`--design`, `--acceptance-criteria`). That is mechanical: the bead content is
fully decided by the time it is emitted; only the shell plumbing remains.

This module turns the prose into one deterministic emission. It accepts a
bead spec as JSON (on stdin or from `--file`), runs `br create` to obtain a
bead id, then runs the `br update` calls. The `br`-invocation layer is
injectable (`runner=`) so tests exercise the argv assembly without ever
touching a real tracker.

⚠️ This script MUTATES tracker state when run for real. Tests MUST pass an
injected runner — never let a test invoke the default runner.

Bead spec JSON schema (only `title` is required; everything else optional):

    {
      "title": "...",                       -> br create --title
      "priority": "P1",                     -> br create --priority   (default P2)
      "type": "task",                       -> br create --type       (default task)
      "status": "open",                     -> br create --status     (default open)
      "labels": ["injection", "cuda"],      -> br create --labels (comma-joined)
      "external_ref": "IB-019-foo.md",      -> br create --external-ref
      "description": "## Goal\n...",        -> br update --description
      "design": "## Out of Scope\n...",     -> br update --design
      "acceptance_criteria": "## ...",      -> br update --acceptance-criteria
      "dependencies": [                     -> br dep add <id> <dep> --type <t>
        {"id": "bd-7", "type": "blocks"}
      ]
    }

Output (JSON on stdout):

    {"bead_id": "bd-42", "updates_applied": ["description", "design"],
     "dependencies_added": ["bd-7"], "dry_run": false}

Exit codes:
  0 — bead created (or dry-run plan emitted)
  2 — spec JSON malformed or missing required `title`
  3 — a `br` invocation failed (stderr surfaced)

Style mirrors `tooling/dekspec/cli.py`. Stdlib-only — vendored into consumer
repos where the `dekspec` engine is not importable.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

# A runner: given an argv list, return (returncode, stdout, stderr).
# Injectable so tests assemble argv without mutating a real tracker.
Runner = Callable[[list[str]], "tuple[int, str, str]"]

_DEFAULT_PRIORITY = "P2"
_DEFAULT_TYPE = "task"
_DEFAULT_STATUS = "open"

# Spec key -> the `br update` flag that carries it.
_UPDATE_FIELDS = {
    "description": "--description",
    "design": "--design",
    "acceptance_criteria": "--acceptance-criteria",
}


class BeadEmitError(Exception):
    """Raised on a malformed spec or a failed `br` invocation."""


def _default_runner(argv: list[str]) -> tuple[int, str, str]:
    """Run a subprocess with list argv (never shell=True). Returns triple."""
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def _load_spec(file: str | None, stdin_text: str | None) -> dict:
    """Parse the bead spec from a file path or raw stdin text."""
    if file is not None:
        path = Path(file)
        if not path.is_file():
            raise BeadEmitError(f"spec file does not exist: {path}")
        raw = path.read_text(encoding="utf-8")
    else:
        raw = stdin_text or ""
    if not raw.strip():
        raise BeadEmitError("no bead spec provided (empty stdin and no --file)")
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BeadEmitError(f"bead spec is not valid JSON: {exc}") from exc
    if not isinstance(spec, dict):
        raise BeadEmitError("bead spec must be a JSON object")
    if not spec.get("title"):
        raise BeadEmitError("bead spec is missing the required `title` field")
    return spec


def _create_argv(spec: dict) -> list[str]:
    """Assemble the `br create` argv from a bead spec."""
    argv = [
        "br",
        "create",
        "--title",
        str(spec["title"]),
        "--priority",
        str(spec.get("priority") or _DEFAULT_PRIORITY),
        "--type",
        str(spec.get("type") or _DEFAULT_TYPE),
        "--status",
        str(spec.get("status") or _DEFAULT_STATUS),
    ]
    labels = spec.get("labels")
    if labels:
        joined = ",".join(str(label) for label in labels) if isinstance(
            labels, list
        ) else str(labels)
        argv += ["--labels", joined]
    ext_ref = spec.get("external_ref")
    if ext_ref:
        argv += ["--external-ref", str(ext_ref)]
    argv.append("--silent")
    return argv


def _update_argvs(bead_id: str, spec: dict) -> list[tuple[str, list[str]]]:
    """Assemble the `br update` argvs for each populated structured field."""
    out: list[tuple[str, list[str]]] = []
    for key, flag in _UPDATE_FIELDS.items():
        value = spec.get(key)
        if value:
            out.append((key, ["br", "update", bead_id, flag, str(value)]))
    return out


def _dep_argvs(bead_id: str, spec: dict) -> list[tuple[str, list[str]]]:
    """Assemble the `br dep add` argvs for each declared dependency."""
    out: list[tuple[str, list[str]]] = []
    for dep in spec.get("dependencies") or []:
        if isinstance(dep, dict):
            dep_id = dep.get("id")
            dep_type = dep.get("type") or "blocks"
        else:
            dep_id, dep_type = str(dep), "blocks"
        if dep_id:
            out.append(
                (
                    str(dep_id),
                    ["br", "dep", "add", bead_id, str(dep_id),
                     "--type", str(dep_type)],
                )
            )
    return out


def emit_bead(
    spec: dict,
    runner: Runner | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Create a bead from a spec dict; run `br` calls via the runner.

    When `dry_run` is True, no runner is invoked — the assembled argv plan is
    returned instead. Raises BeadEmitError on a failed `br` invocation.
    """
    run = runner or _default_runner
    create_argv = _create_argv(spec)

    if dry_run:
        return {
            "dry_run": True,
            "create_argv": create_argv,
            "update_argvs": [argv for _, argv in _update_argvs("<bead-id>", spec)],
            "dependency_argvs": [
                argv for _, argv in _dep_argvs("<bead-id>", spec)
            ],
        }

    code, out, err = run(create_argv)
    if code != 0:
        raise BeadEmitError(f"`br create` failed (exit {code}): {err.strip()}")
    bead_id = out.strip().splitlines()[-1].strip() if out.strip() else ""
    if not bead_id:
        raise BeadEmitError("`br create` produced no bead id on stdout")

    updates_applied: list[str] = []
    for key, argv in _update_argvs(bead_id, spec):
        code, _, err = run(argv)
        if code != 0:
            raise BeadEmitError(
                f"`br update {key}` failed for {bead_id} "
                f"(exit {code}): {err.strip()}"
            )
        updates_applied.append(key)

    deps_added: list[str] = []
    for dep_id, argv in _dep_argvs(bead_id, spec):
        code, _, err = run(argv)
        if code != 0:
            raise BeadEmitError(
                f"`br dep add {dep_id}` failed for {bead_id} "
                f"(exit {code}): {err.strip()}"
            )
        deps_added.append(dep_id)

    return {
        "bead_id": bead_id,
        "updates_applied": updates_applied,
        "dependencies_added": deps_added,
        "dry_run": False,
    }


def cmd_emit(args: argparse.Namespace) -> int:
    """CLI dispatcher: load a spec and create (or plan) the bead."""
    try:
        stdin_text = None if args.file else sys.stdin.read()
        spec = _load_spec(args.file, stdin_text)
        result = emit_bead(spec, dry_run=args.dry_run)
    except BeadEmitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if "JSON" in str(exc) or "title" in str(exc) or (
            "spec" in str(exc)
        ) else 3
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="emit_bead.py",
        description="Create a bead in `br` from a structured JSON bead spec.",
    )
    parser.add_argument(
        "--file",
        help="path to a JSON bead-spec file (default: read JSON from stdin)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the assembled `br` argv plan without running anything",
    )
    parser.set_defaults(func=cmd_emit)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
