#!/usr/bin/env python3
"""Deterministic engine behind `prj-mgr --ingest` and `prj-mgr --adopt`.

The division of labour is the whole design. The MODEL decides what the work
items are -- reading a document, splitting it into independently-grabbable
slices, assigning type/priority/HITL, choosing or inventing a phase, and
judging whether a candidate is genuinely new or already tracked. Everything
else is mechanical and lives here, where it can be tested and where a mistake
is a bug rather than a bad guess:

    context   emit the facts the model needs to decide: boards, their phase
              structure, and the open beads a candidate might duplicate
    review    validate a plan against the real tracker and render the summary
              the human approves. Read-only.
    apply     execute an approved plan. Resumable: every created id is written
              back into the plan file, so a half-failed apply resumes instead
              of duplicating.
    adopt     wire existing beads under a parent. No judgement, no writes
              beyond the edge itself.

Why a plan file at all, when nobody reads it: it makes "propose, then apply"
a thing that exists on disk rather than a promise the model makes to itself,
and it is what lets apply resume. The human sees the rendered summary, never
the JSON.

Quality gate: `br lint` requires a literal `## Acceptance Criteria` heading in
the DESCRIPTION -- the `acceptance_criteria` field does not satisfy it
(verified against br 0.3.2). `review` enforces the heading before anything is
written, so an ingest cannot land beads that fail the repo's own lint.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from beads_workspace import Workspace, pm_workspaces, repo_root, resolve  # noqa: E402

# Reused from the snapshot renderer so board discovery, alias resolution and
# phase detection have exactly ONE implementation. If these two files ever
# disagree about what a phase is, the board and the ingest will disagree too.
from sync_project_snapshot import (  # noqa: E402
    _child_ids,
    _extract_root_id,
    _phase_number,
    _project_alias,
    _run_br_show,
)

PROJECT_ROOT = repo_root(Path.cwd())
PROJECTS_ROOT = PROJECT_ROOT / "docs" / "prj-mgr"
STATE_BUCKETS = ("new", "in-progress", "closed", "archived")
ACTIVE_STATE_BUCKETS = ("new", "in-progress")

VALID_TYPES = {"task", "bug", "feature", "epic", "chore", "issue"}

#: Headings `br lint` demands, BY TYPE -- probed against br 0.3.2, because the
#: template is not the same for every type and an epic that carries
#: "## Acceptance Criteria" still fails lint. `chore` and `issue` have no
#: template requirements at all.
REQUIRED_HEADINGS: dict[str, tuple[str, ...]] = {
    "epic": ("## Success Criteria",),
    "bug": ("## Steps to Reproduce", "## Acceptance Criteria"),
    "task": ("## Acceptance Criteria",),
    "feature": ("## Acceptance Criteria",),
    "chore": (),
    "issue": (),
}
ACCEPTANCE_HEADING = "## Acceptance Criteria"


def required_headings(type_: str) -> tuple[str, ...]:
    return REQUIRED_HEADINGS.get(type_, (ACCEPTANCE_HEADING,))
DESC_HEAD = 400
PLAN_VERSION = 1


# --------------------------------------------------------------------------- #
# br plumbing
# --------------------------------------------------------------------------- #

def _issue_ws() -> Workspace:
    """The workspace new product issues are written to."""
    ws = resolve("issue", PROJECT_ROOT)
    if not ws.exists:
        raise SystemExit(
            "no issue-bead workspace found. Run `bootstrap_beads.py` first, or "
            "`beads_workspace.py` to see what resolved and how."
        )
    return ws


def _br_rc(ws: Workspace, args: list[str]) -> tuple[int, str]:
    """Run `br` and return (exit code, combined output) without raising."""
    proc = subprocess.run(
        ["br", *ws.br_args(), *args],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode, proc.stdout.strip()


def _br(ws: Workspace, args: list[str], *, check: bool = True) -> str:
    proc = subprocess.run(
        ["br", *ws.br_args(), *args],
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if check and proc.returncode != 0:
        raise SystemExit(
            f"br failed (exit {proc.returncode}): br {' '.join(args)}\n{proc.stdout.strip()}"
        )
    return proc.stdout.strip()


def _bead_exists(bead_id: str) -> bool:
    """Does this bead exist, in any project-managed workspace?

    Deliberately NOT `_run_br_show`: that helper runs `br show` with
    check=True, so probing an id that does not exist raises
    CalledProcessError rather than returning an empty mapping. Validation has
    to be able to ask "is this real?" about ids that are, in fact, not real --
    that is the entire point of validating them.
    """
    candidates = [ws for ws in pm_workspaces(PROJECT_ROOT)
                  if bead_id.startswith(f"{ws.prefix}-")] or pm_workspaces(PROJECT_ROOT)
    for ws in candidates:
        code, _ = _br_rc(ws, ["show", bead_id, "--json"])
        if code == 0:
            return True
    return False


def _slug(text: str, cap: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:cap].rstrip("-")


# --------------------------------------------------------------------------- #
# context -- the facts the model decides against
# --------------------------------------------------------------------------- #

def _board_dirs(states: tuple[str, ...] = STATE_BUCKETS) -> list[Path]:
    out: list[Path] = []
    for state in states:
        bucket = PROJECTS_ROOT / state
        if not bucket.is_dir():
            continue
        for path in sorted(bucket.iterdir()):
            if path.is_dir() and not path.is_symlink() and not path.name.startswith("."):
                out.append(path)
    return out


def _board_info(project_dir: Path) -> dict[str, Any] | None:
    try:
        epic_id = _extract_root_id(project_dir)
    except SystemExit:
        return None
    epic = _run_br_show([epic_id]).get(epic_id)
    if epic is None:
        return None
    child_ids = _child_ids(epic)
    children = _run_br_show(child_ids) if child_ids else {}
    phases: list[dict[str, Any]] = []
    for cid in child_ids:
        child = children.get(cid)
        if child is None:
            continue
        number = _phase_number(child)
        if number is None:
            continue
        phases.append(
            {
                "id": child.id,
                "number": number,
                "title": re.sub(r"^Phase\s+\d+\s*:\s*", "", child.title),
                "status": child.status,
                "items": len(_child_ids(child)),
            }
        )
    phases.sort(key=lambda p: p["number"])
    return {
        "project": project_dir.name,
        "state": project_dir.parent.name,
        "alias": _project_alias(project_dir),
        "epic": epic.id,
        "epic_title": epic.title,
        "phases": phases,
    }


def _open_beads() -> list[dict[str, Any]]:
    """Every open bead across the PM workspaces, trimmed for duplicate judging."""
    out: list[dict[str, Any]] = []
    for ws in pm_workspaces(PROJECT_ROOT):
        raw = _br(ws, ["list", "--json"], check=False)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        rows = payload if isinstance(payload, list) else payload.get("issues", [])
        for row in rows:
            if row.get("status") != "open":
                continue
            desc = (row.get("description") or "").strip()
            out.append(
                {
                    "id": row.get("id"),
                    "title": row.get("title", ""),
                    "type": row.get("issue_type", ""),
                    "priority": row.get("priority"),
                    "labels": row.get("labels") or [],
                    "head": desc[:DESC_HEAD],
                }
            )
    return out


def cmd_context(args: argparse.Namespace) -> int:
    boards = [info for d in _board_dirs() if (info := _board_info(d)) is not None]
    if args.into:
        boards = [b for b in boards if args.into in (b["project"], b["alias"])]
        if not boards:
            raise SystemExit(f"unknown board: {args.into}")
    ws = _issue_ws()
    payload = {
        "repo_root": str(PROJECT_ROOT),
        "issue_workspace": {
            "db": str(ws.db),
            "prefix": ws.prefix,
            "source": ws.source,
            "br_args": ws.br_args(),
        },
        "boards": boards,
        "open_beads": _open_beads(),
        "conventions": {
            "phase_title": "Phase <N>: <title> -- any other shape is invisible to the board renderer",
            "acceptance_heading": ACCEPTANCE_HEADING,
            "valid_types": sorted(VALID_TYPES),
            "priority_range": [0, 4],
        },
    }
    print(json.dumps(payload, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# plan model + validation
# --------------------------------------------------------------------------- #

def _load_plan(path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"cannot read plan: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"plan is not valid JSON: {exc}") from exc
    if not isinstance(plan, dict):
        raise SystemExit("plan must be a JSON object")
    return plan


def _save_plan(path: Path, plan: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _normalize_phase_titles(plan: dict[str, Any]) -> None:
    """Force `Phase <N>: <title>`; nothing else is a phase to the renderer."""
    for index, phase in enumerate(plan.get("phases") or [], start=1):
        number = phase.get("number") or index
        phase["number"] = number
        bare = re.sub(r"^Phase\s+\d+\s*:\s*", "", str(phase.get("title", "")).strip())
        phase["title"] = bare
        phase["full_title"] = f"Phase {number}: {bare}"


def validate(plan: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Return (errors, facts). Empty errors means apply may proceed."""
    errors: list[str] = []
    facts: dict[str, Any] = {}

    if plan.get("version") != PLAN_VERSION:
        errors.append(f"plan version must be {PLAN_VERSION}, got {plan.get('version')!r}")

    target = plan.get("target") or {}
    mode = target.get("mode")
    if mode not in {"existing", "new"}:
        errors.append("target.mode must be 'existing' or 'new'")

    board = None
    if mode == "existing":
        selector = target.get("project")
        boards = [info for d in _board_dirs() if (info := _board_info(d)) is not None]
        board = next((b for b in boards if selector in (b["project"], b["alias"])), None)
        if board is None:
            errors.append(f"target.project {selector!r} matches no board")
        else:
            facts["board"] = board
            if target.get("epic") and target["epic"] != board["epic"]:
                errors.append(
                    f"target.epic {target['epic']} != board epic {board['epic']}"
                )
    elif mode == "new":
        if not str(target.get("project_name") or "").strip():
            errors.append("target.project_name is required when mode is 'new'")
        if not (plan.get("phases") or []):
            errors.append("a new board needs at least one phase")

    _normalize_phase_titles(plan)
    phase_keys = {str(p.get("key")) for p in (plan.get("phases") or []) if p.get("key")}
    if len(phase_keys) != len(plan.get("phases") or []):
        errors.append("every phase needs a unique 'key'")

    known_phase_ids = {p["id"] for p in (board or {}).get("phases", [])}
    if board:
        known_phase_ids.add(board["epic"])

    items = plan.get("items") or []
    item_keys: set[str] = set()
    referenced: set[str] = set()
    for index, item in enumerate(items):
        where = f"items[{index}]"
        key = str(item.get("key") or "")
        if not key or key in item_keys:
            errors.append(f"{where}: needs a unique 'key'")
        item_keys.add(key)
        if not str(item.get("title") or "").strip():
            errors.append(f"{where}: title is required")
        if item.get("type") not in VALID_TYPES:
            errors.append(f"{where}: type {item.get('type')!r} not in {sorted(VALID_TYPES)}")
        priority = item.get("priority")
        if not isinstance(priority, int) or not 0 <= priority <= 4:
            errors.append(f"{where}: priority must be an int 0-4, got {priority!r}")
        body = str(item.get("body") or "")
        for heading in required_headings(str(item.get("type"))):
            if heading not in body:
                errors.append(
                    f"{where}: a {item.get('type')} body must contain a literal "
                    f"'{heading}' heading -- br lint rejects it otherwise, so "
                    "ingest refuses to create it"
                )
        parent = str(item.get("parent") or "")
        if not parent:
            errors.append(f"{where}: parent is required (a phase key or an existing bead id)")
        elif parent not in phase_keys and parent not in known_phase_ids:
            referenced.add(parent)

    for parent in sorted(referenced):
        if not _bead_exists(parent):
            errors.append(f"parent {parent} is neither a plan phase key nor an existing bead")

    # blocks/related referents too. Without this a dangling edge passes review
    # and then fails silently during apply, because `br dep add` cannot create
    # an edge to a bead that does not exist.
    dep_refs: set[str] = set()
    for index, item in enumerate(items):
        for dep_type in ("blocks", "related"):
            for raw in item.get(dep_type) or []:
                ref = str(raw)
                if ref not in item_keys:
                    dep_refs.add(ref)
    for ref in sorted(dep_refs):
        if not _bead_exists(ref):
            errors.append(
                f"dependency target {ref} is neither a plan item key nor an existing bead"
            )

    for index, comment in enumerate(plan.get("comments") or []):
        where = f"comments[{index}]"
        bead = str(comment.get("bead") or "")
        if not bead:
            errors.append(f"{where}: 'bead' is required")
        elif not _bead_exists(bead):
            errors.append(f"{where}: bead {bead} does not exist")
        if not str(comment.get("body") or "").strip():
            errors.append(f"{where}: body is required")

    return errors, facts


# --------------------------------------------------------------------------- #
# review -- the only thing the human sees
# --------------------------------------------------------------------------- #

_PRI = {0: "P0", 1: "P1", 2: "P2", 3: "P3", 4: "P4"}


def _hitl(item: dict[str, Any]) -> str:
    labels = item.get("labels") or []
    if "hitl" in labels:
        return "hitl"
    if "afk" in labels:
        return "afk "
    return "----"


def render(plan: dict[str, Any], facts: dict[str, Any]) -> str:
    target = plan.get("target") or {}
    mode = target.get("mode")
    items = plan.get("items") or []
    comments = plan.get("comments") or []
    phases = plan.get("phases") or []
    board = facts.get("board")
    lines: list[str] = []

    source = plan.get("source") or "(inline text)"
    lines.append(f"Source: {source}")
    if mode == "existing" and board:
        lines.append(
            f"Target: {board['project']} ({board['alias']}) "
            f"-- {len(board['phases'])} phases, epic {board['epic']}"
        )
    else:
        lines.append(f"Target: NEW BOARD -- {target.get('project_name')}")
    lines.append("")

    if mode == "new" and phases:
        lines.append("PROPOSED PHASE STRUCTURE")
        for phase in phases:
            count = sum(1 for i in items if i.get("parent") == phase.get("key"))
            noun = "item" if count == 1 else "items"
            lines.append(f"  {phase['full_title']:<52} {count} {noun}")
        lines.append("")

    if items:
        lines.append(f"NEW BEADS ({len(items)})")
        by_parent: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            by_parent.setdefault(str(item.get("parent")), []).append(item)
        phase_label = {str(p.get("key")): p["full_title"] for p in phases}
        if board:
            for phase in board["phases"]:
                phase_label[phase["id"]] = f"Phase {phase['number']}: {phase['title']}"
            phase_label.setdefault(board["epic"], board["epic_title"])
        for parent, group in by_parent.items():
            lines.append(f"  {phase_label.get(parent, parent)}")
            for item in group:
                pri = _PRI.get(item.get("priority"), "P?")
                lines.append(
                    f"    + [{item.get('type','?'):<5} {pri} {_hitl(item)}] {item.get('title','')}"
                )
        lines.append("")

    if comments:
        lines.append(f"ALREADY TRACKED ({len(comments)}) -> append as comments, no new beads")
        for comment in comments:
            reason = str(comment.get("reason") or "").strip()
            lines.append(f"  {comment['bead']}")
            if reason:
                lines.append(f"      <- {reason}")
        lines.append("")

    types: dict[str, int] = {}
    pris: dict[str, int] = {}
    for item in items:
        types[str(item.get("type"))] = types.get(str(item.get("type")), 0) + 1
        pris[_PRI.get(item.get("priority"), "P?")] = pris.get(_PRI.get(item.get("priority"), "P?"), 0) + 1
    if items:
        lines.append(
            "  ".join(
                [
                    "Types: " + ", ".join(f"{n}x{t}" for t, n in sorted(types.items())),
                    "Priorities: " + ", ".join(f"{n}x{p}" for p, n in sorted(pris.items())),
                    f"{sum(1 for i in items if 'hitl' in (i.get('labels') or []))} hitl"
                    f" / {sum(1 for i in items if 'afk' in (i.get('labels') or []))} afk",
                ]
            )
        )
    lines.append(
        f"Totals: {len(items)} new beads, "
        f"{len(phases) if mode == 'new' else 0} new phases, "
        f"{len(comments)} comment{'' if len(comments) == 1 else 's'} on existing beads"
    )
    return "\n".join(lines)


def cmd_review(args: argparse.Namespace) -> int:
    plan = _load_plan(args.plan)
    errors, facts = validate(plan)
    _save_plan(args.plan, plan)  # persist title normalization
    print(render(plan, facts))
    sys.stdout.flush()
    if errors:
        print("\nPLAN REJECTED -- fix these before applying:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.stderr.flush()
        return 1
    print("\nPlan validates. Nothing has been written.")
    return 0


# --------------------------------------------------------------------------- #
# apply
# --------------------------------------------------------------------------- #

README_TEMPLATE = """# {title}

## Project status

- Alias: `{alias}`
- Epic: `{epic}`
- Scope: {scope}
- Last updated: {today}
- Open gates: pending first sync.
- Progress: created by ingest on {today}.

## Active files

- `PROJECT.md` -- generated snapshot, do not hand-edit.
"""


def _create(ws: Workspace, *, title: str, type_: str, priority: int,
            body: str, labels: list[str], slug: str | None = None) -> str:
    """Create one bead and return its id.

    Deliberately does NOT pass `--parent`. `br` responds to it by minting a
    dotted child id (`<parent>.1.2`) and ignoring `--slug`, which bakes the
    parent into the id -- so the id lies the moment an item is re-parented, and
    it reads nothing like the flat slugged ids already on this repo's boards.
    Parentage is wired separately as a `parent-child` edge, which is what the
    board renderer walks anyway.
    """
    # `--description-file` rather than `-d`: bodies are multi-paragraph markdown
    # with fenced code and backticks, which is exactly what breaks on the way
    # through shell quoting.
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".md", prefix="prj-mgr-body-", delete=False, encoding="utf-8"
    )
    with handle:
        handle.write(body)
    tmp = Path(handle.name)
    args = [
        "create", title,
        "-t", type_,
        "-p", str(priority),
        "--description-file", str(tmp),
        "--silent",
    ]
    if slug:
        args += ["--slug", slug]
    if labels:
        args += ["-l", ",".join(labels)]
    try:
        out = _br(ws, args)
    finally:
        tmp.unlink(missing_ok=True)
    bead_id = out.splitlines()[-1].strip() if out else ""
    if not bead_id:
        raise SystemExit(f"br create returned no id for {title!r}")
    return bead_id


def _wire(ws: Workspace, child: str, parent: str, dep_type: str,
          applied: dict[str, str], save, *, quiet: bool = False) -> None:
    edge = f"dep:{child}:{dep_type}:{parent}"
    if edge in applied:
        return
    code, out = _br_rc(ws, ["dep", "add", child, parent, "-t", dep_type])
    if code != 0 and "already" not in out.lower():
        # Never record an edge that was not created. Reporting success for a
        # failed `dep add` is how a dangling reference becomes an invisible
        # hole in the board tree.
        raise SystemExit(
            f"failed to wire {child} -{dep_type}-> {parent} (exit {code}): {out}\n"
            "Nothing else was rolled back; re-run apply to resume."
        )
    applied[edge] = "wired"
    save()
    if not quiet:
        print(f"  dep      {child} -{dep_type}-> {parent}")


def cmd_apply(args: argparse.Namespace) -> int:
    plan = _load_plan(args.plan)
    errors, facts = validate(plan)
    if errors:
        sys.stdout.flush()
        print("refusing to apply an invalid plan:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    ws = _issue_ws()
    target = plan["target"]
    applied: dict[str, str] = plan.setdefault("applied", {})
    created: list[str] = []
    commented: list[str] = []

    def remember(key: str, bead_id: str) -> None:
        applied[key] = bead_id
        _save_plan(args.plan, plan)

    # 1. epic
    if target["mode"] == "new":
        if "__epic__" in applied:
            epic_id = applied["__epic__"]
            print(f"  resume   epic {epic_id}")
        else:
            name = str(target["project_name"]).strip()
            epic_id = _create(
                ws,
                title=name,
                type_="epic",
                priority=int(target.get("priority", 1)),
                body=str(target.get("scope") or name)
                + "\n\n## Success Criteria\n\n- Every phase in this project is closed.\n",
                labels=list(target.get("labels") or ["epic"]),
                slug=_slug(name),
            )
            remember("__epic__", epic_id)
            created.append(epic_id)
            print(f"  created  epic {epic_id}  {name}")
    else:
        epic_id = facts["board"]["epic"]

    # 2. phases
    for phase in plan.get("phases") or []:
        key = f"phase:{phase['key']}"
        if key in applied:
            print(f"  resume   {applied[key]}")
            continue
        phase_id = _create(
            ws,
            title=phase["full_title"],
            type_="task",
            priority=int(phase.get("priority", 1)),
            body=str(phase.get("body") or phase["full_title"])
            + f"\n\n{ACCEPTANCE_HEADING}\n\n- Every child bead in this phase is closed.\n",
            # phases are created as `task`, so ACCEPTANCE_HEADING is correct here
            labels=list(phase.get("labels") or ["phase"]),
            slug=_slug(phase["full_title"]),
        )
        remember(key, phase_id)
        created.append(phase_id)
        print(f"  created  phase {phase_id}  {phase['full_title']}")
        _wire(ws, phase_id, epic_id, "parent-child", applied,
              lambda: _save_plan(args.plan, plan), quiet=True)

    def resolve_parent(ref: str) -> str:
        return applied.get(f"phase:{ref}", ref)

    # 3. items
    for item in plan.get("items") or []:
        key = f"item:{item['key']}"
        if key in applied:
            print(f"  resume   {applied[key]}")
            continue
        bead_id = _create(
            ws,
            title=item["title"],
            type_=item["type"],
            priority=int(item["priority"]),
            body=item["body"],
            labels=list(item.get("labels") or []),
            slug=_slug(item["title"]),
        )
        remember(key, bead_id)
        created.append(bead_id)
        _wire(ws, bead_id, resolve_parent(str(item["parent"])), "parent-child",
              applied, lambda: _save_plan(args.plan, plan), quiet=True)
        print(f"  created  {bead_id}  [{item['type']} {_PRI.get(item['priority'])}] {item['title'][:60]}")

    # 4. edges between plan items and existing beads (second pass: every id exists now)
    for item in plan.get("items") or []:
        bead_id = applied.get(f"item:{item['key']}")
        if not bead_id:
            continue
        for dep_type in ("blocks", "related"):
            for raw in item.get(dep_type) or []:
                ref = applied.get(f"item:{raw}", raw)
                if dep_type == "blocks":
                    # `br dep add A B` records "A depends on B", i.e. B must be
                    # done first. The plan's `blocks: [X]` means "this item
                    # blocks X", so X is the one that depends on this item --
                    # the arguments go the other way round. Getting this
                    # backwards is silent: the edge exists, the graph is
                    # acyclic, and `br ready` simply gates the wrong bead.
                    _wire(ws, ref, bead_id, "blocks", applied,
                          lambda: _save_plan(args.plan, plan))
                else:
                    _wire(ws, bead_id, ref, dep_type, applied,
                          lambda: _save_plan(args.plan, plan))

    # 5. comments on already-tracked beads
    for index, comment in enumerate(plan.get("comments") or []):
        key = f"comment:{index}:{comment['bead']}"
        if key in applied:
            continue
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".md", prefix="prj-mgr-comment-", delete=False, encoding="utf-8"
        )
        with handle:
            handle.write(str(comment["body"]))
        tmp = Path(handle.name)
        try:
            _br(ws, ["comments", "add", comment["bead"], "-f", str(tmp),
                     "--author", str(plan.get("author") or "prj-mgr-ingest")])
        finally:
            tmp.unlink(missing_ok=True)
        remember(key, "commented")
        commented.append(str(comment["bead"]))
        print(f"  comment  {comment['bead']}")

    # 6. scaffold the board directory for a new project
    if target["mode"] == "new":
        slug = target.get("dir") or _slug(str(target["project_name"]))
        board_dir = PROJECTS_ROOT / "new" / slug
        if not (board_dir / "README.md").exists():
            board_dir.mkdir(parents=True, exist_ok=True)
            (board_dir / "README.md").write_text(
                README_TEMPLATE.format(
                    title=target["project_name"],
                    alias=target.get("alias") or _slug(str(target["project_name"]))[:4],
                    epic=epic_id,
                    scope=target.get("scope") or target["project_name"],
                    today=date.today().isoformat(),
                ),
                encoding="utf-8",
            )
            print(f"  board    docs/prj-mgr/new/{slug}/README.md")
        plan["target"]["dir"] = slug
        _save_plan(args.plan, plan)

    # A mis-wired edge can also close a loop. br prints "No dependency cycles
    # detected." on success -- match that exactly rather than guessing at a
    # substring, which is how the first version of this check warned on its own
    # success message.
    code, out = _br_rc(ws, ["dep", "cycles"])
    if code != 0 or "no dependency cycles" not in out.lower():
        print(f"\n  WARNING  `br dep cycles` reported (exit {code}):\n{out}")

    _br(ws, ["sync", "--flush-only"], check=False)
    # Count what THIS run did, not what the plan contains -- on a resume both
    # numbers should read zero, and reporting the plan's totals implies work
    # that did not happen.
    print(
        f"\nApplied. {len(created)} bead{'' if len(created) == 1 else 's'} created, "
        f"{len(commented)} comment{'' if len(commented) == 1 else 's'} appended."
    )
    project = (
        target.get("dir")
        if target["mode"] == "new"
        else facts["board"]["project"]
    )
    print(f"Next: python3 prj_mgr.py {project} --sync")
    return 0


# --------------------------------------------------------------------------- #
# adopt -- wiring only
# --------------------------------------------------------------------------- #

def cmd_adopt(args: argparse.Namespace) -> int:
    ws = _issue_ws()
    parent = args.into
    if not _bead_exists(parent):
        raise SystemExit(f"parent bead {parent} does not exist")
    for bead_id in args.beads:
        if not _bead_exists(bead_id):
            raise SystemExit(f"bead {bead_id} does not exist")
    for bead_id in args.beads:
        _br(ws, ["dep", "add", bead_id, parent, "-t", "parent-child"])
        print(f"  adopted  {bead_id} -> {parent}")
    _br(ws, ["sync", "--flush-only"], check=False)
    return 0


# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest_plan.py",
        description="Deterministic engine behind prj-mgr --ingest / --adopt.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ctx = sub.add_parser("context", help="emit boards, phases and open beads as JSON")
    p_ctx.add_argument("--into", help="restrict to one board (name or alias)")
    p_ctx.set_defaults(func=cmd_context)

    p_rev = sub.add_parser("review", help="validate a plan and render its summary (read-only)")
    p_rev.add_argument("plan", type=Path)
    p_rev.set_defaults(func=cmd_review)

    p_app = sub.add_parser("apply", help="execute an approved plan (resumable)")
    p_app.add_argument("plan", type=Path)
    p_app.set_defaults(func=cmd_apply)

    p_ado = sub.add_parser("adopt", help="wire existing beads under a parent")
    p_ado.add_argument("beads", nargs="+")
    p_ado.add_argument("--into", required=True, help="parent bead id (a phase or the epic)")
    p_ado.set_defaults(func=cmd_adopt)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
