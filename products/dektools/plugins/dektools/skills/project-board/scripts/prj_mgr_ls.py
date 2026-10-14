#!/usr/bin/env python3
"""Render the active project registry for prj-mgr `--ls`."""

from __future__ import annotations

import json
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
    body = [f"projects[{len(entries)}]{{alias,name,phase,status}}:"]
    for entry in entries:
        body.append("  " + ",".join(json.dumps(str(v)) for v in
                                   (entry.alias, entry.project_name, entry.current_phase_title, entry.status_label)))
    body.append('help[1]: "Use a project name for status; --items PROJECT for tasks"')
    return "\n".join(body)


def main() -> None:
    entries = sync_project_snapshot.load_project_registry_entries()
    if not entries:
        print("projects[0]:\nhelp[1]: \"Add findings or a plan to start a board\"")
        return
    print(render_registry_table(entries))


if __name__ == "__main__":
    main()
