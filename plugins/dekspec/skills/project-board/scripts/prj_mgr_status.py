#!/usr/bin/env python3
"""Render prj-mgr status tables from checked-in project-state helpers."""

from __future__ import annotations

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import sync_project_snapshot  # noqa: E402  (sys.path insert must precede)


def _column_widths(rows: list[list[str]], headers: list[str]) -> list[int]:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    return widths


def render_status_table(entries: list[sync_project_snapshot.ProjectStatusEntry]) -> str:
    headers = [
        "Project / Alias",
        "Phase Status",
        "Progress (Beads)",
        "Blocked / Blockers",
        "Est. Complete",
        "Dependencies",
        "Risks",
        "Next Actions",
    ]
    rows = [
        [
            f"{entry.project_name} ({entry.alias})",
            entry.phase_status,
            entry.progress,
            entry.blocked_blockers,
            entry.estimate,
            entry.dependencies,
            entry.risks,
            entry.next_actions,
        ]
        for entry in entries
    ]
    widths = _column_widths(rows, headers)

    def fmt(row: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |"

    divider = "| " + " | ".join("-" * width for width in widths) + " |"
    body = [fmt(headers), divider]
    body.extend(fmt(row) for row in rows)
    return "\n".join(body)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    selector = args[0] if args else None
    entries = sync_project_snapshot.load_project_status_entries(selector)
    if not entries:
        print("No open projects.")
        return
    print(render_status_table(entries))


if __name__ == "__main__":
    main()
