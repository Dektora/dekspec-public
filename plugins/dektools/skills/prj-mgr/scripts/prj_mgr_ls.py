#!/usr/bin/env python3
"""Render the active project registry for prj-mgr `--ls`."""

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


def render_registry_table(entries: list[sync_project_snapshot.ProjectRegistryEntry]) -> str:
    headers = ["Alias", "Name", "Current Phase", "Status", "Est. Complete", "Past Week"]
    rows = [
        [
            entry.alias,
            entry.project_name,
            entry.current_phase_title,
            entry.status_label,
            entry.estimate,
            entry.past_week,
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


def main() -> None:
    entries = sync_project_snapshot.load_project_registry_entries()
    if not entries:
        print("No open projects.")
        return
    print(render_registry_table(entries))


if __name__ == "__main__":
    main()
