#!/usr/bin/env python3
"""Render the individual beads on a board, grouped by phase.

`--ls` and `--status` both answer at BOARD granularity: which phase is active,
how many beads are open, what is blocking. Neither can show you the items you
would actually pick up, and `br` cannot fill the gap either -- `br list` has no
`--parent` filter, and `br dep tree` walks `blocks` rather than `parent-child`,
so rooting it at an epic returns just the epic. The only thing that knows the
board-to-bead mapping is `sync_project_snapshot._load_tree`, which until now
only ever wrote markdown. This mode prints it.

Read-only.
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import sync_project_snapshot as sps  # noqa: E402  (sys.path insert must precede)

PRIORITY = {0: "P0", 1: "P1", 2: "P2", 3: "P3", 4: "P4"}
STATUS_MARK = {"closed": "x", "in_progress": "~", "blocked": "!"}


def _mark(bead: sps.Bead) -> str:
    return STATUS_MARK.get(bead.status, " ")


def _priority(bead: sps.Bead) -> str:
    return PRIORITY.get(bead.priority, "P?")


def _blocked_by(bead: sps.Bead) -> list[str]:
    """Open `blocks` dependencies -- the beads this one is waiting on."""
    return [
        dep["id"]
        for dep in bead.dependencies
        if dep.get("dependency_type") == "blocks" and dep.get("status") != "closed"
    ]


def _edges(bead: sps.Bead, direction: str) -> list[str]:
    """Ids on the other end of this bead's open `blocks` edges.

    `dependencies` are what this bead waits on; `dependents` are what waits on
    it. Printing the ids rather than a count is the difference between "blocked
    by 4" and knowing which four.
    """
    rows = bead.dependencies if direction == "waits_on" else bead.dependents
    return [
        dep["id"]
        for dep in rows
        if dep.get("dependency_type") == "blocks" and dep.get("status") != "closed"
    ]


def _wrap(text: str, width: int, indent: str) -> list[str]:
    """Indent a bead body, reflowing prose and leaving real structure intact.

    Two things make this fiddlier than `textwrap.wrap`:

    1. Bead bodies are already hard-wrapped near this width, so indenting
       without re-joining paragraphs first pushes every line past the margin and
       dangles its last word onto a continuation.
    2. Structure and prose share a block. `## Consequence` followed immediately
       by a paragraph is one block with no blank line, so deciding "reflow or
       not" per BLOCK leaves that paragraph unwrapped -- which is exactly what
       an earlier version of this function did. The decision has to be per line,
       accumulating prose runs and flushing them at each structural boundary.

    Headings, tables and fenced code are emitted verbatim. Blockquotes and list
    items are reflowed but keep their marker and gain a hanging indent.
    """
    out: list[str] = []
    buffer: list[str] = []
    fenced = False

    def fill(chunk: str, first: str, rest: str) -> list[str]:
        return textwrap.wrap(
            chunk, width=width, initial_indent=first, subsequent_indent=rest,
            break_long_words=False, break_on_hyphens=False,
        ) or [first + chunk]

    def flush() -> None:
        if not buffer:
            return
        out.extend(fill(" ".join(buffer), indent, indent))
        buffer.clear()

    for raw in text.strip().splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            flush()
            fenced = not fenced
            out.append(indent + line)
            continue
        if fenced:
            out.append(indent + line)
            continue

        if not stripped:
            flush()
            if out and out[-1].strip():
                out.append("")
            continue

        if stripped.startswith("#") or stripped.startswith("|"):
            flush()
            out.append(indent + stripped)
            continue

        if stripped.startswith(">"):
            flush()
            body = stripped.lstrip("> ").strip()
            out.extend(fill(body, indent + "> ", indent + "  "))
            continue

        marker = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", stripped)
        if marker:
            flush()
            out.extend(fill(marker.group(2), f"{indent}{marker.group(1)} ",
                            indent + " " * (len(marker.group(1)) + 1)))
            continue

        buffer.append(stripped)

    flush()
    while out and not out[-1].strip():
        out.pop()
    return out


def _sort_key(bead: sps.Bead):
    """Phases in declared order; items closed-last, then by priority, then title.

    Sorting phases by priority would scramble them -- Phase 6 is a P2 and Phase 1
    is a P0, but the whole point of a phase number is that it is the order.
    """
    number = sps._phase_number(bead)
    if number is not None:
        return (0, number, "")
    return (
        1,
        1 if bead.status == "closed" else 0,
        bead.priority if bead.priority is not None else 9,
        bead.title.lower(),
    )


class Renderer:
    def __init__(self, tree: dict[str, sps.Bead], *, only_open: bool, only_ready: bool,
                 phase: int | None, priority_max: int | None, compact: bool,
                 width: int):
        self.tree = tree
        self.only_open = only_open
        self.only_ready = only_ready
        self.phase = phase
        self.priority_max = priority_max
        self.compact = compact
        self.width = width
        self.shown = 0
        self.hidden = 0

    def _keep(self, bead: sps.Bead) -> bool:
        if self.only_open and bead.status == "closed":
            return False
        # NOT `bead.priority or 9`: P0 is priority 0, which is falsy, so that
        # form silently rewrites every P0 as 9 and filters out exactly the beads
        # a --priority-max query exists to find.
        priority = bead.priority if bead.priority is not None else 9
        if self.priority_max is not None and priority > self.priority_max:
            return False
        if self.only_ready and (bead.status != "open" or _blocked_by(bead)):
            return False
        return True

    def _render_bead(self, bead: sps.Bead, depth: int) -> list[str]:
        pad = "  " * depth
        waits_on = _edges(bead, "waits_on")
        if self.compact:
            suffix = f"  (blocked by {len(waits_on)})" if waits_on else ""
            return [f"{pad}[{_mark(bead)}] {_priority(bead)} {bead.title}{suffix}",
                    f"{pad}        {bead.id}"]

        # Expanded: the bead itself, not a line about the bead.
        head = f"{pad}[{_mark(bead)}] {_priority(bead)} {bead.issue_type or 'task'}  "
        out = [""]
        out.extend(
            textwrap.wrap(
                bead.title, width=self.width, initial_indent=head,
                subsequent_indent=" " * len(head),
                break_long_words=False, break_on_hyphens=False,
            )
            or [head + bead.title]
        )
        out.append(f"{pad}    {bead.id}")

        # Labels get their own line when the combined metadata would overflow;
        # a label set on this board can reach six entries.
        tail = f"status: {bead.status}"
        if bead.updated_at:
            tail += f"   updated: {bead.updated_at[:10]}"
        if bead.labels:
            labels = "labels: " + ", ".join(sorted(bead.labels))
            if len(pad) + 4 + len(labels) + 3 + len(tail) <= self.width:
                out.append(f"{pad}    {labels}   {tail}")
            else:
                out.extend(
                    textwrap.wrap(labels, width=self.width,
                                  initial_indent=f"{pad}    ",
                                  subsequent_indent=f"{pad}            ",
                                  break_long_words=False, break_on_hyphens=False)
                )
                out.append(f"{pad}    {tail}")
        else:
            out.append(f"{pad}    {tail}")
        for label, ids in (("waits on", waits_on), ("blocks", _edges(bead, "blocks"))):
            if not ids:
                continue
            head = f"{pad}    {label + ':':<11}"
            cont = " " * len(head)
            line = head
            for index, ref in enumerate(ids):
                piece = ref + ("," if index < len(ids) - 1 else "")
                if len(line) + 1 + len(piece) > self.width and line.strip():
                    out.append(line.rstrip())
                    line = cont + piece
                else:
                    line = f"{line} {piece}" if line.strip() else cont + piece
            out.append(line.rstrip())
        body = (bead.description or "").strip()
        if body:
            out.append("")
            out.extend(_wrap(body, self.width, f"{pad}    "))
        if bead.acceptance_criteria:
            out.append("")
            out.append(f"{pad}    ## Acceptance Criteria")
            out.extend(_wrap(bead.acceptance_criteria, self.width, f"{pad}    "))
        return out

    def walk(self, bead: sps.Bead, depth: int = 0, lines: list[str] | None = None) -> list[str]:
        lines = [] if lines is None else lines
        for child in sorted(
            (self.tree[i] for i in sps._child_ids(bead) if i in self.tree), key=_sort_key
        ):
            is_phase = sps._phase_number(child) is not None
            if self.phase is not None and is_phase and sps._phase_number(child) != self.phase:
                continue

            # A phase is scaffolding: render it when anything under it survives
            # the filters, and never count it as a hidden item.
            subtree = self.walk(child, depth + 1)
            if is_phase:
                if subtree:
                    if not self.compact:
                        lines.append("")
                    lines.append(f"{'  ' * depth}{child.title}")
                    if not self.compact:
                        lines.append(f"{'  ' * depth}{'-' * len(child.title)}")
                    lines.extend(subtree)
                continue

            if not self._keep(child):
                self.hidden += 1
                lines.extend(subtree)
                continue

            self.shown += 1
            lines.extend(self._render_bead(child, depth))
            lines.extend(subtree)
        return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prj-mgr --items",
        description="List the individual beads on a board, grouped by phase.",
    )
    parser.add_argument("project", nargs="?", help="board name or alias; omit for every board")
    parser.add_argument("--open", action="store_true", dest="only_open", help="hide closed beads")
    parser.add_argument("--ready", action="store_true", dest="only_ready",
                        help="only beads that are open and unblocked")
    parser.add_argument("--phase", type=int, help="restrict to one phase number")
    parser.add_argument("--priority-max", type=int, choices=range(5),
                        help="only beads at this priority or more urgent")
    parser.add_argument("--full", action="store_false", dest="compact", help="Show full records.")
    parser.add_argument("--compact", "--brief", action="store_true", dest="compact", default=True,
                        help="one line per bead instead of the full record")
    parser.add_argument("--width", type=int, default=96, help="wrap column (default 96)")
    args = parser.parse_args(argv)

    project_dirs = sps._all_project_dirs(args.project)
    if not project_dirs:
        print("No open projects.")
        return 0

    for index, project_dir in enumerate(project_dirs):
        root_id = sps._extract_root_id(project_dir)
        tree = sps._load_tree(root_id)
        root = tree[root_id]
        renderer = Renderer(
            tree,
            only_open=args.only_open,
            only_ready=args.only_ready,
            phase=args.phase,
            priority_max=args.priority_max,
            compact=args.compact,
            width=args.width,
        )
        lines = renderer.walk(root)
        if index:
            print()
        print(f"{root.title}  ({sps._project_alias(project_dir)})")
        print()
        if lines:
            print("\n".join(f"  {line}" if line.strip() else "" for line in lines))
        else:
            print("  no beads match the filters")
        # Say what was filtered out. A list that silently omits half a board
        # reads as a complete board.
        note = f"\n  {renderer.shown} shown"
        if renderer.hidden:
            note += f", {renderer.hidden} hidden by filters"
        print(note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
