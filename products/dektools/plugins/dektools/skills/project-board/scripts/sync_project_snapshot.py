#!/usr/bin/env python3
"""Regenerate docs/prj-mgr project snapshots from br.

The prj-mgr skill treats br as source of truth and PROJECT.md as a derivative
fast-path cache. This script keeps that cache executable instead of relying on
manual rollup edits.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from typing import Any


# Repo root, resolved by walking up to the git root rather than counting
# path segments -- this file now lives 5 levels deep in the plugin tree,
# and a hardcoded parents[N] silently breaks if it is ever moved again.
from beads_workspace import pm_workspaces as _pm_workspaces  # noqa: E402
from beads_workspace import repo_root as _repo_root  # noqa: E402

PROJECT_ROOT = _repo_root(Path.cwd())
PROJECTS_ROOT = PROJECT_ROOT / "docs" / "prj-mgr"
STATE_BUCKETS = ("new", "in-progress", "closed", "archived")
ACTIVE_STATE_BUCKETS = ("new", "in-progress")


def _bead_prefix() -> str:
    """Resolve this repo's br issue-id prefix (e.g. ds, df, dk).

    Each repo defines its own prefix via `br config`; `bd` is the br default
    used as the fallback when the prefix cannot be resolved.
    """
    workspaces = _pm_workspaces(PROJECT_ROOT)
    if not workspaces:
        return "bd"
    # Boards may span both PM workspaces; the id regex must match either.
    return "|".join(re.escape(ws.prefix) for ws in workspaces)


BEAD_PREFIX = _bead_prefix()
# Capturing group matching one bead id across every PM workspace prefix.
# `_bead_prefix` already escapes each alternative, so do NOT re-escape here --
# that would turn the alternation into a literal.
BEAD_ID = rf"(?:{BEAD_PREFIX})-[A-Za-z0-9.-]+"
BEAD_ID = rf"({BEAD_ID})"


@dataclass(frozen=True)
class Bead:
    id: str
    title: str
    status: str
    priority: int | None
    issue_type: str
    description: str
    notes: str
    parent: str | None
    dependencies: list[dict[str, Any]]
    dependents: list[dict[str, Any]]
    # Additive fields, defaulted so every existing construction site keeps
    # working. The snapshot renderer does not use them; the per-bead view does.
    labels: list[str] = field(default_factory=list)
    acceptance_criteria: str = ""
    updated_at: str = ""

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "Bead":
        return cls(
            id=raw["id"],
            title=raw.get("title", ""),
            status=raw.get("status", ""),
            priority=raw.get("priority"),
            issue_type=raw.get("issue_type", ""),
            description=raw.get("description", ""),
            notes=raw.get("notes", ""),
            parent=raw.get("parent"),
            dependencies=list(raw.get("dependencies") or []),
            dependents=list(raw.get("dependents") or []),
            labels=list(raw.get("labels") or []),
            acceptance_criteria=raw.get("acceptance_criteria") or "",
            updated_at=raw.get("updated_at") or "",
        )


@dataclass(frozen=True)
class ProjectRegistryEntry:
    project_name: str
    alias: str
    bucket: str
    status_label: str
    current_phase_id: str
    current_phase_title: str
    estimate: str
    past_week: str


@dataclass(frozen=True)
class ProjectStatusEntry:
    project_name: str
    alias: str
    phase_status: str
    progress: str
    blocked_blockers: str
    estimate: str
    dependencies: str
    risks: str
    next_actions: str


def _run_br_show(ids: list[str]) -> dict[str, Bead]:
    """Look ids up across the PM workspaces (issue + dekspec), never code.

    Ids are routed to the workspace whose prefix they carry, so a board may
    mix generic issues and DekSpec work. A `cb-` id is refused outright: code
    beads are not project-managed (ADR-052).
    """
    if not ids:
        return {}
    stray = [i for i in ids if i.startswith("cb-")]
    if stray:
        raise ValueError(
            "prj-mgr will not resolve code beads -- they are the coding agent's "
            f"queue, not project-managed work: {', '.join(sorted(stray))}"
        )
    out: dict[str, Bead] = {}
    for ws in _pm_workspaces(PROJECT_ROOT):
        mine = [i for i in ids if i.startswith(f"{ws.prefix}-")]
        if not mine:
            continue
        proc = subprocess.run(
            ["br", *ws.br_args(), "show", *mine, "--json"],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        for row in json.loads(proc.stdout):
            out[row["id"]] = Bead.from_json(row)
    return out


def _resolve_root_bead_id(seed: str) -> str:
    bead = _run_br_show([seed]).get(seed)
    while bead and bead.parent:
        parent = _run_br_show([bead.parent]).get(bead.parent)
        if not parent:
            break
        bead = parent
    if bead:
        return bead.id
    raise SystemExit(f"cannot resolve root bead from seed {seed}")


def _bucket_project_dirs(states: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for state in states:
        bucket = PROJECTS_ROOT / state
        if not bucket.is_dir():
            continue
        for path in sorted(bucket.iterdir()):
            if not path.is_dir() or path.is_symlink() or path.name.startswith("."):
                continue
            paths.append(path)
    return paths


def _project_dir(selector: str) -> Path:
    matches: list[Path] = []
    for path in _bucket_project_dirs(STATE_BUCKETS):
        if path.name == selector:
            matches.append(path)
            continue
        # Alias lookup MUST go through `_project_alias`, the same function that
        # renders the alias into the status table and the README. Reading the
        # `- Alias:` line directly here meant a board with no such line got an
        # alias it displayed (initials, e.g. `cas`) but could not resolve.
        if _project_alias(path) == selector:
            matches.append(path)
    if len(matches) == 1:
        return matches[0]
    raise SystemExit(f"unknown project selector: {selector}")


def _all_project_dirs(selector: str | None) -> list[Path]:
    if selector:
        return [_project_dir(selector)]
    return [path for path in _bucket_project_dirs(ACTIVE_STATE_BUCKETS) if not _project_is_closed(path)]


def _project_is_closed(project_dir: Path) -> bool:
    project_md = project_dir / "PROJECT.md"
    if not project_md.exists():
        return False
    text = project_md.read_text()
    return bool(re.search(r"\|\s*`?[^|]+`?\s*\|\s*Closed\s*\|", text))


def _extract_root_id(project_dir: Path) -> str:
    readme = project_dir / "README.md"
    if readme.exists():
        text = readme.read_text()
        match = re.search(rf"^- Epic:\s*`{BEAD_ID}`", text, re.MULTILINE)
        if match:
            return _resolve_root_bead_id(match.group(1))

    candidates = [project_dir / "PROJECT.md", project_dir / "README.md"]
    candidate_ids: list[str] = []
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text()
        match = re.search(rf"\|\s*Epic\s*\|\s*`?{BEAD_ID}`?\s*\|", text)
        if match:
            return _resolve_root_bead_id(match.group(1))
        candidate_ids.extend(re.findall(rf"`{BEAD_ID}`", text))
    if candidate_ids:
        seed = sorted(set(candidate_ids), key=lambda value: (value.count("."), len(value), value))[0]
        return _resolve_root_bead_id(seed)
    raise SystemExit(f"cannot determine root bead for {project_dir}")


def _child_ids(bead: Bead) -> list[str]:
    return [
        dep["id"]
        for dep in bead.dependents
        if dep.get("dependency_type") == "parent-child"
    ]


def _load_tree(root_id: str) -> dict[str, Bead]:
    loaded: dict[str, Bead] = {}
    pending = [root_id]
    while pending:
        batch = [item for item in pending if item not in loaded]
        pending = []
        if not batch:
            continue
        loaded.update(_run_br_show(batch))
        for bead_id in batch:
            pending.extend(_child_ids(loaded[bead_id]))
    return loaded


def _natural_key(bead_id: str) -> list[int | str]:
    parts: list[int | str] = []
    for part in re.split(r"(\d+)", bead_id):
        if part.isdigit():
            parts.append(int(part))
        elif part:
            parts.append(part)
    return parts


def _status_counts(beads: list[Bead]) -> tuple[int, int, int, int, int]:
    open_count = sum(1 for b in beads if b.status == "open")
    active_count = sum(1 for b in beads if b.status == "in_progress")
    closed_count = sum(1 for b in beads if b.status == "closed")
    blocked_count = sum(1 for b in beads if b.status == "blocked")
    return open_count, active_count, closed_count, blocked_count, len(beads)


def _phase_number(bead: Bead) -> int | None:
    match = re.search(r"\bPhase\s+(\d+)\b", bead.title)
    return int(match.group(1)) if match else None


def _is_blocker(bead: Bead) -> bool:
    return bead.title.lower().startswith("blocker:") or bead.issue_type == "issue" and "blocker" in bead.title.lower()


def _phase_alias(bead: Bead) -> str:
    title = bead.title
    title = re.sub(r"^Phase\s+\d+\s*:\s*", "", title)
    return title.split(" before ", 1)[0].strip().lower() or bead.title.lower()


def _active_phase(phases: list[Bead]) -> Bead:
    for bead in phases:
        if bead.status in {"in_progress", "open", "blocked"}:
            return bead
    return phases[-1]


def _active_child_for_parent(parent: Bead, tree: dict[str, Bead]) -> Bead | None:
    children = _direct_children(parent, tree)
    for status in ("in_progress", "blocked", "open"):
        for child in children:
            if child.status == status:
                return child
    return None


def _blocking_ids(bead: Bead) -> list[str]:
    return [
        dep["id"]
        for dep in bead.dependencies
        if dep.get("dependency_type") == "blocks" and dep.get("status") != "closed"
    ]


def _title_without_phase(bead: Bead) -> str:
    return re.sub(r"^Phase\s+\d+\s*:\s*", "", bead.title)


def _direct_children(bead: Bead, tree: dict[str, Bead]) -> list[Bead]:
    children = [tree[id_] for id_ in _child_ids(bead) if id_ in tree]
    children.sort(key=lambda child: _natural_key(child.id))
    return children


def _descendant_beads(bead: Bead, tree: dict[str, Bead]) -> list[Bead]:
    descendants: list[Bead] = []
    seen: set[str] = set()

    def visit(node: Bead) -> None:
        for child in _direct_children(node, tree):
            if child.id in seen:
                continue
            seen.add(child.id)
            descendants.append(child)
            visit(child)

    visit(bead)
    return descendants


def _estimate_from_beads(beads: list[Bead]) -> str:
    if not beads:
        return "~0%"
    closed = sum(1 for bead in beads if bead.status == "closed")
    return f"~{round((closed / len(beads)) * 100)}%"


def _all_closed(beads: list[Bead]) -> bool:
    return bool(beads) and all(bead.status == "closed" for bead in beads)


def _classify_project_bucket(root: Bead, tree: dict[str, Bead]) -> str:
    beads = [root, *_descendant_beads(root, tree)]
    if beads and all(bead.status == "closed" for bead in beads):
        return "closed"
    if any(bead.status in {"in_progress", "blocked"} for bead in beads):
        return "in-progress"
    if any(bead.status == "closed" for bead in beads):
        return "in-progress"
    return "new"


def _compat_symlink_path(project_name: str) -> Path:
    return PROJECTS_ROOT / project_name


def _ensure_project_bucket(project_dir: Path, bucket: str) -> Path:
    current_bucket = project_dir.parent.name
    if current_bucket == bucket:
        return project_dir

    destination = PROJECTS_ROOT / bucket / project_dir.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SystemExit(f"cannot move {project_dir} -> {destination}: destination already exists")
    project_dir.rename(destination)

    compat = _compat_symlink_path(project_dir.name)
    if compat.exists() or compat.is_symlink():
        compat.unlink()
    compat.symlink_to(Path(bucket) / project_dir.name)
    return destination


def _project_alias(project_dir: Path) -> str:
    readme = project_dir / "README.md"
    if readme.exists():
        match = re.search(r"^- Alias:\s*`?([^`\n]+)`?", readme.read_text(), re.MULTILINE)
        if match:
            return match.group(1).strip()
    return "".join(part[0] for part in project_dir.name.split("-") if part)[:4]


def _project_past_week(project_dir: Path) -> str:
    latest: datetime | None = None
    for path in project_dir.rglob("*"):
        if path.name.startswith("."):
            continue
        if path.is_file():
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if latest is None or modified > latest:
                latest = modified
    if latest is None:
        return "no recorded change"
    now = datetime.now(timezone.utc)
    if latest >= now - timedelta(days=7):
        return f"updated {latest.date().isoformat()}"
    return f"no recorded change since {latest.date().isoformat()}"


def _status_label_for_project(bucket: str, root: Bead, tree: dict[str, Bead]) -> str:
    if bucket == "archived":
        return "Archived"
    if _all_closed([root, *_descendant_beads(root, tree)]):
        return "Closed"
    if _classify_project_bucket(root, tree) == "in-progress":
        return "In Progress"
    return "Not Started"


def project_registry_entry(project_dir: Path, tree: dict[str, Bead], root_id: str) -> ProjectRegistryEntry:
    root = tree[root_id]
    root_children = [tree[id_] for id_ in _child_ids(root) if id_ in tree]
    root_children.sort(key=lambda bead: _natural_key(bead.id))
    phases = [bead for bead in root_children if _phase_number(bead) is not None]
    current_phase = _active_phase(phases) if phases else root
    return ProjectRegistryEntry(
        project_name=project_dir.name,
        alias=_project_alias(project_dir),
        bucket=project_dir.parent.name,
        status_label=_status_label_for_project(project_dir.parent.name, root, tree),
        current_phase_id=current_phase.id,
        current_phase_title=_title_without_phase(current_phase),
        estimate=_estimate_from_beads(_descendant_beads(root, tree)),
        past_week=_project_past_week(project_dir),
    )


def project_status_entry(project_dir: Path, tree: dict[str, Bead], root_id: str) -> ProjectStatusEntry:
    _, state = _render_project(project_dir, tree, root_id)
    return ProjectStatusEntry(
        project_name=project_dir.name,
        alias=state["alias"],
        phase_status=state["status_phase"],
        progress=state["progress"],
        blocked_blockers=state["blocked_text"],
        estimate=state["estimate"],
        dependencies=state["dependencies"],
        risks=state["risk"],
        next_actions=state["next_action"],
    )


def load_project_registry_entries(selector: str | None = None) -> list[ProjectRegistryEntry]:
    entries: list[ProjectRegistryEntry] = []
    for project_dir in _all_project_dirs(selector):
        root_id = _extract_root_id(project_dir)
        tree = _load_tree(root_id)
        canonical_dir = _ensure_project_bucket(
            project_dir,
            _classify_project_bucket(tree[root_id], tree),
        )
        entries.append(project_registry_entry(canonical_dir, tree, root_id))
    entries.sort(key=lambda entry: (entry.status_label in {"Not Started"}, entry.project_name))
    return entries


def load_project_status_entries(selector: str | None = None) -> list[ProjectStatusEntry]:
    entries: list[ProjectStatusEntry] = []
    for project_dir in _all_project_dirs(selector):
        root_id = _extract_root_id(project_dir)
        tree = _load_tree(root_id)
        canonical_dir = _ensure_project_bucket(
            project_dir,
            _classify_project_bucket(tree[root_id], tree),
        )
        entries.append(project_status_entry(canonical_dir, tree, root_id))
    entries.sort(key=lambda entry: (entry.phase_status == "Closed", entry.project_name))
    return entries


def _readme_focus(project_dir: Path) -> dict[str, str | list[str]]:
    readme = project_dir / "README.md"
    if not readme.exists():
        return {}
    text = readme.read_text()
    focus: dict[str, str | list[str]] = {}
    label_map = (
        ("epic", ("Epic", "Project epic", "Baseline gate epic")),
        ("phase", ("Phase", "Current phase")),
        ("checkpoint", ("Checkpoint",)),
    )
    for key, labels in label_map:
        for label in labels:
            match = re.search(
                rf"^- {re.escape(label)}:\s*`{BEAD_ID}`",
                text,
                re.MULTILINE,
            )
            if match:
                focus[key] = match.group(1)
                break

    ids: list[str] = []
    capture = False
    for line in text.splitlines():
        if line.startswith("- Active work:") or line.startswith("- Follow-on open work:"):
            capture = True
            continue
        if capture and line.startswith("### "):
            capture = False
        if capture:
            ids.extend(re.findall(rf"`{BEAD_ID}`", line))
    if ids:
        focus["work_ids"] = list(dict.fromkeys(ids))
    return focus


def _build_plan_rows(root: Bead, tree: dict[str, Bead]) -> list[list[str]]:
    rows: list[list[str]] = []
    for bead in [root, *_descendant_beads(root, tree)]:
        children = _direct_children(bead, tree)
        done = ", ".join(
            _title_without_phase(child)
            for child in children
            if child.status == "closed"
        ) or "none"
        open_children = sum(1 for child in children if child.status != "closed")
        blocked_children = sum(
            1
            for child in children
            if child.status == "blocked" or _blocking_ids(child)
        )
        dependency_ids = [
            f"`{dep['id']}`"
            for dep in bead.dependencies
            if dep.get("status") != "closed"
            and dep.get("dependency_type") in {"blocks", "parent-child"}
        ]
        dependencies = ", ".join(dependency_ids) or "—"
        next_step = (
            "keep as reference"
            if bead.status == "closed"
            else f"resolve blocker for `{bead.id}`" if bead.status == "blocked"
            else f"continue `{bead.id}`"
        )
        rows.append([
            f"`{bead.id}`",
            bead.issue_type or "task",
            bead.status or "unknown",
            done,
            str(open_children),
            str(blocked_children),
            _title_without_phase(bead),
            dependencies,
            next_step,
        ])
    return rows


def _render_project(project_dir: Path, tree: dict[str, Bead], root_id: str) -> tuple[str, dict[str, Any]]:
    root = tree[root_id]
    focus = _readme_focus(project_dir)
    root_children = [tree[id_] for id_ in _child_ids(root) if id_ in tree]
    root_children.sort(key=lambda bead: _natural_key(bead.id))
    phases = [bead for bead in root_children if _phase_number(bead) is not None]
    blockers = [bead for bead in root_children if _is_blocker(bead)]

    project_closed = _all_closed([root, *_descendant_beads(root, tree)])
    phase_id = focus.get("phase")
    checkpoint_id = focus.get("checkpoint")
    current_phase = root
    if project_closed:
        current_phase = root
    elif isinstance(phase_id, str) and phase_id:
        if phase_id in tree:
            current_phase = tree[phase_id]
        else:
            loaded_phase = _run_br_show([phase_id])
            if phase_id in loaded_phase:
                current_phase = loaded_phase[phase_id]
    else:
        current_phase = _active_phase(phases) if phases else root

    if not project_closed and current_phase.status == "closed" and phases:
        current_phase = _active_phase(phases)

    active = current_phase
    if project_closed:
        active = root
    elif isinstance(checkpoint_id, str) and checkpoint_id:
        if checkpoint_id in tree:
            active = tree[checkpoint_id]
        else:
            loaded_checkpoint = _run_br_show([checkpoint_id])
            if checkpoint_id in loaded_checkpoint:
                active = loaded_checkpoint[checkpoint_id]

    if not project_closed and active.status == "closed":
        fallback_active = _active_child_for_parent(current_phase, tree)
        if fallback_active is not None:
            active = fallback_active

    focused_work_ids = [
        bead_id
        for bead_id in focus.get("work_ids", [])
        if isinstance(bead_id, str) and bead_id in tree
    ]
    active_children = (
        [tree[id_] for id_ in focused_work_ids]
        if focused_work_ids
        else [tree[id_] for id_ in _child_ids(active) if id_ in tree]
    )
    active_children.sort(key=lambda bead: _natural_key(bead.id))

    phase_index = next((index + 1 for index, bead in enumerate(phases) if bead.id == current_phase.id), 1)
    total_phases = len(phases) if phases else 1
    active_blockers = _blocking_ids(active)
    open_bug_blockers = [
        bead.id
        for bead in active_children
        if bead.status != "closed"
        and (bead.status == "blocked" or _is_blocker(bead) or bead.issue_type == "bug")
    ]
    blocker_ids = active_blockers or open_bug_blockers
    blocked_text = "no" if not blocker_ids and active.status != "blocked" else "yes: " + ", ".join(blocker_ids or [active.id])
    phase_descendants = _descendant_beads(current_phase, tree)
    project_descendants = _descendant_beads(root, tree)
    phase_open, phase_active, phase_closed, _phase_blocked, phase_total = _status_counts(phase_descendants)
    progress = f"{phase_open} open / {phase_active} active / {phase_closed} closed / {phase_total} total"
    phase_estimate = _estimate_from_beads(phase_descendants)
    project_estimate = _estimate_from_beads(project_descendants)
    estimate = f"{phase_estimate} phase / {project_estimate} project"
    if project_closed:
        status_phase = "Closed"
    else:
        status_phase = f"Phase {phase_index}/{total_phases}: `{current_phase.id}` - {_title_without_phase(current_phase)}"
    has_open_focused_work = bool(focused_work_ids) and any(
        child.status != "closed" for child in active_children
    )
    next_action = (
        "none"
        if project_closed
        else
        f"continue focused work: `{active_children[0].id}`"
        if has_open_focused_work
        else f"start `{active.id}` child slices"
        if active_children and any(child.status != "closed" for child in active_children)
        else "close project rollup" if all(child.status == "closed" for child in root_children) else f"continue `{active.id}`"
    )
    risk = "exclude source-only/generated clutter" if active.status != "closed" else "none"
    plan_rows = _build_plan_rows(root, tree)
    plan_body = [
        "| " + " | ".join(row) + " |"
        for row in (plan_rows or [["none", "-", "closed", "none", "0", "0", "none", "none", "keep as reference"]])
    ]
    plan_table = "\n".join(
        [
            "| Bead | Type | Status | Done | Open | Blocked | Notes | Dependencies | Next |",
            "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
            *plan_body,
        ]
    )
    blocker_rows = []
    for bead in blockers:
        blocker_dependencies = ", ".join(
            f"`{dep['id']}`"
            for dep in bead.dependencies
            if dep.get("status") != "closed"
        ) or "none"
        blocker_next = "keep as reference" if bead.status == "closed" else f"close `{bead.id}`"
        blocker_rows.append(
            f"| `{bead.id}` | {bead.issue_type} | {bead.status} | {_title_without_phase(bead)} | {blocker_dependencies} | {blocker_next} |"
        )

    open_blockers = [
        f"- `{bead.id}` {bead.title}"
        for bead in blockers
        if bead.status != "closed"
    ]
    if not open_blockers:
        open_blockers = ["- none."]

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    summary = (
        f"{root.description}\n\n"
        f"Generated from br at {generated_at}.\n\n"
        f"Source of truth: `br`. This file is generated by "
        f"the project-board snapshot command. Refresh with `/dekspec:project-board refresh {project_dir.name}`."
    )
    alias = _project_alias(project_dir)
    blocker_rows_text = "\n".join(blocker_rows)
    open_blockers_text = "\n".join(open_blockers)
    key_beads = list({bead.id: bead for bead in [root, current_phase, active, *active_children]}.values())
    key_ids_text = "\n".join(f"- `{bead.id}`" for bead in key_beads)

    rendered = f"""# {root.title} project snapshot

## Project summary

{summary}

## Current phase

| Field | Value |
| --- | --- |
| Epic | `{root.id}` |
| Phase | {("closed" if project_closed else f"`{current_phase.id}` {_title_without_phase(current_phase)}")} |
| Checkpoint | {("closed" if project_closed else f"`{active.id}` {_title_without_phase(active)}")} |
| Blocked | {"yes" if blocked_text != "no" else "no"} |
| Primary blocker | {", ".join(blocker_ids) if blocker_ids else "none"} |

## Status table

| Project / Alias | Phase Status | Progress (Beads) | Blocked / Blockers | Est. Complete | Dependencies | Risks | Next Actions |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| `{project_dir.name} ({alias})` | {status_phase} | {progress} | {blocked_text} | {estimate} | `{root.id}` | {risk} | {next_action} |

## Phase plan

{plan_table}

## Blockers

| Bead | Type | Status | Notes | Dependencies | Next |
| --- | --- | --- | --- | --- | --- |
{blocker_rows_text if blocker_rows_text else '| none | - | - | none | none | keep as reference |'}

## Open blockers

{open_blockers_text}

## Recent activity

- Snapshot regenerated from `br` on {date.today().isoformat()}.
- Active phase: {("closed" if project_closed else f"`{current_phase.id}` {_title_without_phase(current_phase)}")}.
- Active checkpoint: {("closed" if project_closed else f"`{active.id}` {_title_without_phase(active)}")}.
- Open blockers: {"none" if not blocker_ids else ", ".join(blocker_ids)}.

## Key bead IDs

{key_ids_text}
"""
    state = {
        "active": active,
        "root": root,
        "alias": alias,
        "current_phase": current_phase,
        "progress": progress,
        "blocked_text": blocked_text,
        "next_action": next_action,
        "estimate": estimate,
        "status_phase": status_phase,
        "dependencies": f"`{root.id}`",
        "risk": risk,
    }
    return rendered, state


def _scope_line(description: str) -> str:
    """One-line scope for the README status list.

    `- Scope: {description}` inlined the epic's WHOLE description, which for
    every real epic here is multi-paragraph markdown carrying its own `##`
    headings -- so a heading landed inside the bullet list and split it in two.
    The full text is still rendered in PROJECT.md; this is a summary line, so
    take the first paragraph, flatten it, and cap it.
    """
    first = (description or "").strip().split("\n\n", 1)[0]
    flat = " ".join(first.split())
    return (flat[:237] + "...") if len(flat) > 240 else (flat or "not recorded")


def _update_readme(project_dir: Path, state: dict[str, Any]) -> None:
    readme = project_dir / "README.md"
    if not readme.exists():
        return
    text = readme.read_text()
    marker = "\n## Active files\n"
    if marker not in text:
        return
    active: Bead = state["active"]
    root: Bead = state["root"]
    project_closed = active.id == root.id and active.status == "closed"
    bucket = project_dir.parent.name
    if bucket == "archived":
        progress_line = "archived."
        open_gates = "none"
    elif bucket == "closed":
        progress_line = "closed."
        open_gates = "none"
    else:
        progress_line = f'{state["progress"]}. Active phase is {"closed" if project_closed else f"`{active.id}` {_title_without_phase(active)}"}. Blocked: {state["blocked_text"]}.'
        open_gates = state["next_action"]
    status_block = f"""# {root.title}

## Project status

- Alias: `{state["alias"]}`
- Epic: `{root.id}`
- Scope: {_scope_line(root.description)}
- Last updated: {date.today().isoformat()}
- Open gates: {open_gates}.
- Progress: {progress_line}
"""
    rest = text.split(marker, 1)[1]
    readme.write_text(status_block + marker + rest)


def sync_project(project_dir: Path) -> None:
    root_id = _extract_root_id(project_dir)
    tree = _load_tree(root_id)
    project_dir = _ensure_project_bucket(
        project_dir,
        _classify_project_bucket(tree[root_id], tree),
    )
    rendered, state = _render_project(project_dir, tree, root_id)
    (project_dir / "PROJECT.md").write_text(rendered)
    _update_readme(project_dir, state)
    print(f"synced {project_dir.relative_to(PROJECT_ROOT)} from {root_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", nargs="?", help="project folder name or alias; omit to sync all")
    args = parser.parse_args()
    for project_dir in _all_project_dirs(args.project):
        sync_project(project_dir)


if __name__ == "__main__":
    main()
