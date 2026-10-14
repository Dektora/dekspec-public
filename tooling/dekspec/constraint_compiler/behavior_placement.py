"""Read an Intent's placement rows and diagnostics without resolving their homes."""
from __future__ import annotations

from dekspec.spec_kinds import BEHAVIOR_SPEC_NAMES as BS

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlacementProblem:
    """One malformed table row: its 1-based file line, a kind code and a message."""

    line: int
    kind: str
    message: str


@dataclass(frozen=True)
class PlacementReading:
    """Everything a caller needs from one Intent's Behavior placement table."""

    present: bool = False
    rows: tuple[dict[str, Any], ...] = ()
    problems: tuple[PlacementProblem, ...] = ()


def _unquote(value: str, quote: str = "`") -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
        return value[1:-1]
    return value


def _home(cell: str) -> dict[str, Any] | None:
    if cell == "none":
        return {"kind": "none"}
    if re.fullmatch(BS.id_pattern, cell):  # dekspec:names-both-forms
        return {"kind": "behavior_spec", "id": cell}
    if cell.startswith("BS (new):"):
        name = _unquote(re.split(r"[,(]", cell[len("BS (new):"):], maxsplit=1)[0], '"')
        return {"kind": "new_behavior_spec", "name": name} if name else None
    match = re.fullmatch(r"(IC-[0-9]{3,}) §([^§]+)", cell)
    if match and match[2].strip():
        return {"kind": "interface_contract_section", "id": match[1],
                "section": match[2].strip()}
    if re.fullmatch(r"AE-[0-9]{3,}", cell):
        return {"kind": "architecture_element", "id": cell}
    match = re.fullmatch(r"local \(brief ([0-9]+)\)", cell)
    if match:
        return {"kind": "local", "brief": int(match[1])}
    match = re.fullmatch(r"local \((IB-[0-9]{3,})\)|(IB-[0-9]{3,})", cell)
    if match:
        return {"kind": "local", "id": match[1] or match[2]}
    return None


def _triggers(cell: str) -> tuple[list[str], str | None]:
    if cell == "none":
        return [], None
    triggers = []
    for item in map(_unquote, cell.split(",")):
        if item == "none":
            return [], '"none" cannot be combined with T1–T4'
        if item not in ("T1", "T2", "T3", "T4"):
            return [], f'unknown trigger "{item}"; use T1, T2, T3, T4 or none'
        if item not in triggers:
            triggers.append(item)
    return triggers, None


def _read_row(raw: str, line: int) -> tuple[dict[str, Any] | None, list[PlacementProblem]]:
    cells = re.split(r"(?<!\\)\|", raw.strip())[1:]
    if cells and not cells[-1]:
        cells.pop()
    cells = [_unquote(cell) for cell in cells]
    if len(cells) != 4:
        return None, [PlacementProblem(
            line, "missing-column",
            f"expected 4 columns (Rule set, Home, Trigger, Reason), found {len(cells)}",
        )]
    if all(cell.startswith("[") and cell.endswith("]") for cell in cells):
        return None, []

    rule_set, home_cell, trigger_cell, reason = cells
    problems = [PlacementProblem(line, "empty-cell", f"empty {label} cell")
                for label, cell in zip(("Rule set", "Home", "Trigger"), cells[:3])
                if not cell]
    if not reason:
        problems.append(PlacementProblem(line, "missing-reason", "missing Reason"))
    home = _home(home_cell) if home_cell else None
    if home_cell and home is None:
        problems.append(PlacementProblem(line, "unknown-home", f'unknown home form "{home_cell}"'))
    triggers, error = _triggers(trigger_cell) if trigger_cell else ([], None)
    if error:
        problems.append(PlacementProblem(line, "unknown-trigger", error))
    if problems:
        return None, problems
    return {"line": line, "rule_set": rule_set, "home": home,
            "triggers": triggers, "reason": reason}, []


def read_placement(text: str) -> PlacementReading:
    """Read the whole Intent text, retaining file lines and every row diagnostic.

    The first two pipe lines are the unchecked header and separator. Placeholders
    and prose are ignored. Home forms are recognized without consulting disk.
    """
    present = False
    table_lines = 0
    rows = []
    problems = []
    for line, raw in enumerate(text.splitlines(), 1):
        if not present:
            if raw.rstrip() == "## Behavior placement":
                present = True
            continue
        if raw.startswith("## "):
            break
        if not raw.lstrip().startswith("|"):
            continue
        table_lines += 1
        if table_lines <= 2:
            continue
        row, defects = _read_row(raw, line)
        if row is not None:
            rows.append(row)
        problems.extend(defects)
    return PlacementReading(present, tuple(rows), tuple(problems))
