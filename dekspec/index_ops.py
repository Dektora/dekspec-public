"""Deterministic regeneration of derived index files
(intent-index.md, mission-index.md, etc.).

Source-walks the canonical artifact tree via SpecGraph, normalises
every row to a single canonical column set, and rewrites the table
region of each index file in place. The body text outside the table
(headers, prose, footers) is preserved.

Implements the "deterministic regen" recommendation from
INT-provisional-multi-user-coordination-analysis (the index-file
merge-conflict gap).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constraint_compiler.graph import SpecGraph


@dataclass
class IndexResult:
    path: Path
    changed: bool
    rows_emitted: int


def _format_aes(linked_aes: list[Any] | None) -> str:
    """Render the AEs column. linked_aes is a list of dicts shaped
    `{id: "AE-NNN", description: "..."}` per the IR schema; for the
    index we want the comma-separated AE-NNN ids only."""
    if not linked_aes:
        return ""
    ids: list[str] = []
    for entry in linked_aes:
        if isinstance(entry, dict):
            aid = entry.get("id") or entry.get("ae_id")
            if aid:
                ids.append(str(aid))
        elif isinstance(entry, str):
            ids.append(entry)
    return ", ".join(ids)


def _find_intent_filename(intent_id: str, dekspec_dir: Path) -> str | None:
    """Find the canonical filename for an Intent ID, e.g.
    `intents/INT-079-provisional-folder-scaffold.md`. Returns the path
    relative to dekspec/, or None if not found."""
    target = dekspec_dir / "intents"
    if not target.is_dir():
        return None
    for p in target.glob(f"{intent_id}-*.md"):
        return f"intents/{p.name}"
    return None


def _extract_mission_id(mission_field: Any) -> str:
    """The `mission` IR field is either a string (e.g. 'MSN-014') or
    a dict like {'id': 'MSN-014', 'path': '...'}. Normalize."""
    if isinstance(mission_field, dict):
        return mission_field.get("id") or ""
    if isinstance(mission_field, str):
        return mission_field
    return ""


_INTENT_HEADER = (
    "| Intent | Title | Type | Autonomy | Status | Linked AEs | Created | Modified |"
)
_INTENT_SEP = (
    "|---|---|---|---|---|---|---|---|"
)


def _format_intent_row(ir: dict[str, Any], dekspec_dir: Path) -> str:
    """One markdown table row for an Intent IR."""
    intent_id = ir.get("id", "")
    # The IR field for the H1 title is `name`.
    title = (ir.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
    intent_type = ir.get("intent_type") or ""
    autonomy = ir.get("autonomy") or ""
    status = ir.get("status") or ""
    aes = _format_aes(ir.get("linked_architecture_elements") or [])
    created = ir.get("created") or ""
    modified = ir.get("modified") or ""
    rel = _find_intent_filename(intent_id, dekspec_dir)
    id_cell = f"[{intent_id}]({rel})" if rel else intent_id
    return (
        f"| {id_cell} | {title} | {intent_type} | {autonomy} | {status} "
        f"| {aes} | {created} | {modified} |"
    )


def _split_at_archive_heading(content: str) -> tuple[str, str | None]:
    """Split the file at the `## Archive` heading. Returns
    (pre_archive_content, archive_section_content | None). If no
    Archive heading is present, the second element is None."""
    m = re.search(r"^## Archive\s*$", content, flags=re.MULTILINE)
    if not m:
        return content, None
    return content[: m.start()], content[m.start():]


def _header_prefix(header: str) -> str:
    """Extract the first two columns of a markdown table header so we
    can detect existing tables of the same kind regardless of how many
    columns they carry. E.g. "| Mission | Title | Status | ... |" ->
    "| Mission | Title |"."""
    parts = header.split("|")
    if len(parts) < 3:
        return header
    return f"|{parts[1]}|{parts[2]}|"


def _replace_table_in_section(
    section: str, header: str, separator: str, new_rows: list[str]
) -> str:
    """Replace the first markdown table in `section` (header + sep +
    contiguous `|`-prefixed body rows). If no table exists, append
    one to the section.

    Table detection: the first line starting with the first two
    column-cells of `header` (e.g. "| Mission | Title |") marks the
    start of the table. This allows the same helper to operate on
    indexes of any kind (Intent / Mission / ADR / AE / WS / IC).
    """
    prefix = _header_prefix(header)
    # Backward-compat aliases for intent-index (some older copies use
    # `| ID | Title |` instead of `| Intent | Title |`).
    aliases: list[str] = [prefix]
    if prefix.startswith("| Intent "):
        aliases.append("| ID | Title |")
    lines = section.split("\n")
    out: list[str] = []
    i = 0
    table_replaced = False
    while i < len(lines):
        line = lines[i]
        if not table_replaced and any(line.startswith(a) for a in aliases):
            out.append(header)
            out.append(separator)
            out.extend(new_rows)
            table_replaced = True
            i += 1
            if i < len(lines) and re.match(r"^\|[-: |]+\|", lines[i]):
                i += 1
            while i < len(lines) and lines[i].startswith("|"):
                i += 1
            continue
        out.append(line)
        i += 1
    if not table_replaced:
        out.append("")
        out.append(header)
        out.append(separator)
        out.extend(new_rows)
        out.append("")
    return "\n".join(out)


def _replace_intent_table(content: str, new_rows: list[str]) -> str:
    """Replace the FIRST intent-index.md table body (the Active queue),
    preserving everything from `## Archive` onward."""
    pre_archive, archive = _split_at_archive_heading(content)
    new_pre = _replace_table_in_section(
        pre_archive, _INTENT_HEADER, _INTENT_SEP, new_rows
    )
    return new_pre + (archive or "")


def _replace_archive_table(content: str, new_rows: list[str]) -> str:
    """Replace the Archive section's table body. No-op if `## Archive`
    is not present (and no Archive rows to emit)."""
    pre_archive, archive = _split_at_archive_heading(content)
    if archive is None:
        if not new_rows:
            return content
        # No Archive section yet — append one.
        return (
            pre_archive.rstrip("\n")
            + "\n\n## Archive\n\n"
            + "> Terminal-status Intents (`LOCKED`, `SUPERSEDED`). Moved here from the Active queue above on `--lock` or on supersession.\n\n"
            + _ARCHIVE_HEADER
            + "\n"
            + _ARCHIVE_SEP
            + "\n"
            + "\n".join(new_rows)
            + "\n"
        )
    new_archive = _replace_table_in_section(
        archive, _ARCHIVE_HEADER, _ARCHIVE_SEP, new_rows
    )
    return pre_archive + new_archive


# Statuses that belong in the Active queue (top table). LOCKED +
# SUPERSEDED + DEPRECATED land in the Archive table below.
# `TODO` + `TESTFAIL` were retired from the Intent enum 2026-05-25 (E3 audit).
_ACTIVE_QUEUE_STATUSES = frozenset(
    {"DRAFT", "PROPOSED", "ACCEPTED", "IMPLEMENTING",
     "TESTPASS", "MERGED", "OVERSIZED"}
)
_ARCHIVE_STATUSES = frozenset({"LOCKED", "SUPERSEDED", "DEPRECATED"})


_ARCHIVE_HEADER = (
    "| Intent | Title | Type | Status | Superseded-By | Linked AEs | Modified |"
)
_ARCHIVE_SEP = (
    "|---|---|---|---|---|---|---|"
)


def _format_archive_row(ir: dict[str, Any], dekspec_dir: Path) -> str:
    """One markdown table row for an Intent IR in the Archive shape
    (7 columns: ID, Title, Type, Status, Superseded-By, AEs, Modified)."""
    intent_id = ir.get("id", "")
    title = (ir.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
    intent_type = ir.get("intent_type") or ""
    status = ir.get("status") or ""
    superseded_by = ir.get("superseded_by") or ""
    if isinstance(superseded_by, dict):
        superseded_by = superseded_by.get("id") or ""
    if superseded_by in ("n/a", "none", "None"):
        superseded_by = ""
    aes = _format_aes(ir.get("linked_architecture_elements") or [])
    modified = ir.get("modified") or ""
    rel = _find_intent_filename(intent_id, dekspec_dir)
    id_cell = f"[{intent_id}]({rel})" if rel else intent_id
    return (
        f"| {id_cell} | {title} | {intent_type} | {status} "
        f"| {superseded_by} | {aes} | {modified} |"
    )


def regen_intent_index(
    repo_root: Path,
    dekspec_root: str = "dekspec",
    dry_run: bool = False,
) -> IndexResult:
    """Regenerate intent-index.md from canonical dekspec/intents/.

    intent-index.md is a TWO-TABLE document: an Active queue (top)
    holds non-terminal-status Intents, and an Archive (bottom) holds
    LOCKED / SUPERSEDED / DEPRECATED ones. This MVP regenerates ONLY
    the Active-queue table (the most volatile + merge-conflict-prone
    surface). The Archive table is left untouched; lock-time updates
    continue to flow into it via the artifact-ops `update-index` verb.

    Rows in the Active queue sort by numeric ID ascending so concurrent
    additions from multiple branches converge to identical ordering
    after merge.
    """
    repo_root = repo_root.resolve()
    dekspec_dir = repo_root / dekspec_root
    index_path = dekspec_dir / "intent-index.md"
    if not index_path.exists():
        return IndexResult(path=index_path, changed=False, rows_emitted=0)

    graph = SpecGraph.load(repo_root, dekspec_root=dekspec_root)

    def _id_key(ir: dict[str, Any]) -> tuple[int, str]:
        m = re.match(r"^INT-(\d+)", ir.get("id", "") or "")
        return (int(m.group(1)) if m else 99999, ir.get("id", ""))

    active_intents = sorted(
        (ir for ir in graph.intents()
         if (ir.get("status") or "") in _ACTIVE_QUEUE_STATUSES),
        key=_id_key,
    )
    archive_intents = sorted(
        (ir for ir in graph.intents()
         if (ir.get("status") or "") in _ARCHIVE_STATUSES),
        key=_id_key,
    )

    active_rows = [_format_intent_row(ir, dekspec_dir) for ir in active_intents]
    archive_rows = [_format_archive_row(ir, dekspec_dir) for ir in archive_intents]

    content = index_path.read_text(encoding="utf-8")
    new_content = _replace_intent_table(content, active_rows)
    new_content = _replace_archive_table(new_content, archive_rows)
    if new_content == content:
        return IndexResult(
            path=index_path,
            changed=False,
            rows_emitted=len(active_rows) + len(archive_rows),
        )
    if not dry_run:
        index_path.write_text(new_content, encoding="utf-8")
    return IndexResult(
        path=index_path,
        changed=True,
        rows_emitted=len(active_rows) + len(archive_rows),
    )


# --------------------------------------------------------------------------- #
# Mission index
# --------------------------------------------------------------------------- #

_MSN_ACTIVE_STATUSES = frozenset({"TODO", "ACTIVE", "COMPLETING"})
_MSN_ARCHIVE_STATUSES = frozenset({"COMPLETE", "KILLED", "SUPERSEDED"})

_MSN_HEADER = (
    "| Mission | Title | Status | Owner | Autonomy ceiling | Created | Modified |"
)
_MSN_SEP = "|---|---|---|---|---|---|---|"
_MSN_ARCHIVE_HEADER = (
    "| Mission | Title | Status | Owner | Created | Modified |"
)
_MSN_ARCHIVE_SEP = "|---|---|---|---|---|---|"


def _find_kind_filename(kind: str, artifact_id: str, dekspec_dir: Path) -> str | None:
    """Find canonical filename for any IR kind. Returns path relative
    to dekspec/."""
    dirs = {
        "MSN": "missions",
        "ADR": "adrs",
        "AE": "architecture-elements",
        "WS": "working-specs",
        "IC": "interface-contracts",
    }
    sub = dirs.get(kind)
    if not sub:
        return None
    target = dekspec_dir / sub
    if not target.is_dir():
        return None
    for p in target.glob(f"{artifact_id}-*.md"):
        return f"{sub}/{p.name}"
    return None


def _format_mission_row(ir: dict[str, Any], dekspec_dir: Path) -> str:
    mid = ir.get("id", "")
    title = (ir.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
    status = ir.get("status") or ""
    owner = ir.get("owner") or ""
    autonomy = ir.get("autonomy_ceiling") or ""
    created = ir.get("created") or ""
    modified = ir.get("modified") or ""
    rel = _find_kind_filename("MSN", mid, dekspec_dir)
    id_cell = f"[{mid}]({rel})" if rel else mid
    return f"| {id_cell} | {title} | {status} | {owner} | {autonomy} | {created} | {modified} |"


def _format_mission_archive_row(ir: dict[str, Any], dekspec_dir: Path) -> str:
    mid = ir.get("id", "")
    title = (ir.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
    status = ir.get("status") or ""
    owner = ir.get("owner") or ""
    created = ir.get("created") or ""
    modified = ir.get("modified") or ""
    rel = _find_kind_filename("MSN", mid, dekspec_dir)
    id_cell = f"[{mid}]({rel})" if rel else mid
    return f"| {id_cell} | {title} | {status} | {owner} | {created} | {modified} |"


def _split_at_heading(content: str, heading: str) -> tuple[str, str | None]:
    """Split at `## <heading>`. Generalised version of
    _split_at_archive_heading."""
    m = re.search(rf"^## {re.escape(heading)}\s*$", content, flags=re.MULTILINE)
    if not m:
        return content, None
    return content[: m.start()], content[m.start():]


def _id_key_factory(kind: str):
    pat = re.compile(rf"^{kind}-(\d+)")

    def key(ir: dict[str, Any]) -> tuple[int, str]:
        m = pat.match(ir.get("id", "") or "")
        return (int(m.group(1)) if m else 99999, ir.get("id", ""))

    return key


def regen_mission_index(
    repo_root: Path, dekspec_root: str = "dekspec", dry_run: bool = False
) -> IndexResult:
    """Regenerate mission-index.md (Active + Archive)."""
    repo_root = repo_root.resolve()
    dekspec_dir = repo_root / dekspec_root
    index_path = dekspec_dir / "mission-index.md"
    if not index_path.exists():
        return IndexResult(path=index_path, changed=False, rows_emitted=0)
    graph = SpecGraph.load(repo_root, dekspec_root=dekspec_root)
    key_fn = _id_key_factory("MSN")
    active = sorted(
        (ir for ir in graph.missions()
         if (ir.get("status") or "") in _MSN_ACTIVE_STATUSES),
        key=key_fn,
    )
    archive = sorted(
        (ir for ir in graph.missions()
         if (ir.get("status") or "") in _MSN_ARCHIVE_STATUSES),
        key=key_fn,
    )
    active_rows = [_format_mission_row(ir, dekspec_dir) for ir in active]
    archive_rows = [_format_mission_archive_row(ir, dekspec_dir) for ir in archive]
    content = index_path.read_text(encoding="utf-8")
    pre, arc = _split_at_heading(content, "Archive")
    new_pre = _replace_table_in_section(pre, _MSN_HEADER, _MSN_SEP, active_rows)
    if arc is not None:
        new_arc = _replace_table_in_section(
            arc, _MSN_ARCHIVE_HEADER, _MSN_ARCHIVE_SEP, archive_rows
        )
        new_content = new_pre + new_arc
    elif archive_rows:
        new_content = (
            new_pre.rstrip("\n")
            + "\n\n## Archive\n\n"
            + "> Terminal-status Missions (`COMPLETE`, `KILLED`, `SUPERSEDED`).\n\n"
            + _MSN_ARCHIVE_HEADER + "\n" + _MSN_ARCHIVE_SEP + "\n"
            + "\n".join(archive_rows) + "\n"
        )
    else:
        new_content = new_pre
    if new_content == content:
        return IndexResult(path=index_path, changed=False, rows_emitted=len(active_rows) + len(archive_rows))
    if not dry_run:
        index_path.write_text(new_content, encoding="utf-8")
    return IndexResult(path=index_path, changed=True, rows_emitted=len(active_rows) + len(archive_rows))


# --------------------------------------------------------------------------- #
# Generic single-table regen (ADR, AE, WS, IC)
# --------------------------------------------------------------------------- #


def _regen_single_table_index(
    repo_root: Path,
    dekspec_root: str,
    dry_run: bool,
    index_filename: str,
    kind: str,
    header: str,
    separator: str,
    format_row: Any,
) -> IndexResult:
    repo_root = repo_root.resolve()
    dekspec_dir = repo_root / dekspec_root
    index_path = dekspec_dir / index_filename
    if not index_path.exists():
        return IndexResult(path=index_path, changed=False, rows_emitted=0)
    graph = SpecGraph.load(repo_root, dekspec_root=dekspec_root)
    key_fn = _id_key_factory(kind)
    irs = sorted(
        (ir for ir in graph.irs_by_id.values() if ir.get("id", "").startswith(f"{kind}-")),
        key=key_fn,
    )
    rows = [format_row(ir, dekspec_dir) for ir in irs]
    content = index_path.read_text(encoding="utf-8")
    new_content = _replace_table_in_section(content, header, separator, rows)
    if new_content == content:
        return IndexResult(path=index_path, changed=False, rows_emitted=len(rows))
    if not dry_run:
        index_path.write_text(new_content, encoding="utf-8")
    return IndexResult(path=index_path, changed=True, rows_emitted=len(rows))


# ADR ---------------------------------------------------------------------- #
_ADR_HEADER = "| ADR | Title | Status | Date | Supersedes | Superseded by |"
_ADR_SEP    = "|---|---|---|---|---|---|"


def _format_adr_row(ir: dict[str, Any], dekspec_dir: Path) -> str:
    aid = ir.get("id", "")
    title = (ir.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
    status = ir.get("status") or ""
    date = ir.get("date") or ir.get("modified") or ""
    rel = _find_kind_filename("ADR", aid, dekspec_dir)
    id_cell = f"[{aid}]({rel})" if rel else aid
    # supersedes / superseded_by left empty for MVP — derived from the
    # ADR's text via the supersede flow, not from a single IR field.
    return f"| {id_cell} | {title} | {status} | {date} |  |  |"


def regen_adr_index(repo_root, dekspec_root="dekspec", dry_run=False):
    return _regen_single_table_index(
        repo_root, dekspec_root, dry_run, "adr-index.md", "ADR",
        _ADR_HEADER, _ADR_SEP, _format_adr_row,
    )


# AE ----------------------------------------------------------------------- #
_AE_HEADER = "| AE | Title | Subtype | Classification | Status | Created | Modified |"
_AE_SEP    = "|---|---|---|---|---|---|---|"


def _format_ae_row(ir: dict[str, Any], dekspec_dir: Path) -> str:
    aid = ir.get("id", "")
    title = (ir.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
    subtype = ir.get("subtype") or ""
    classification = ir.get("classification") or ""
    status = ir.get("status") or ""
    created = ir.get("created") or ""
    modified = ir.get("modified") or ""
    rel = _find_kind_filename("AE", aid, dekspec_dir)
    id_cell = f"[{aid}]({rel})" if rel else aid
    return f"| {id_cell} | {title} | {subtype} | {classification} | {status} | {created} | {modified} |"


def regen_ae_index(repo_root, dekspec_root="dekspec", dry_run=False):
    return _regen_single_table_index(
        repo_root, dekspec_root, dry_run, "architecture-elements-index.md", "AE",
        _AE_HEADER, _AE_SEP, _format_ae_row,
    )


# WS ----------------------------------------------------------------------- #
_WS_HEADER = "| WS | Title | Status | Related AEs | Created | Modified |"
_WS_SEP    = "|---|---|---|---|---|---|"


def _format_ws_row(ir: dict[str, Any], dekspec_dir: Path) -> str:
    wid = ir.get("id", "")
    title = (ir.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
    status = ir.get("status") or ""
    aes = _format_aes(ir.get("related_architecture_elements") or [])
    created = ir.get("created") or ""
    modified = ir.get("modified") or ""
    rel = _find_kind_filename("WS", wid, dekspec_dir)
    id_cell = f"[{wid}]({rel})" if rel else wid
    return f"| {id_cell} | {title} | {status} | {aes} | {created} | {modified} |"


def regen_ws_index(repo_root, dekspec_root="dekspec", dry_run=False):
    return _regen_single_table_index(
        repo_root, dekspec_root, dry_run, "working-spec-index.md", "WS",
        _WS_HEADER, _WS_SEP, _format_ws_row,
    )


# IC ----------------------------------------------------------------------- #
_IC_HEADER = "| IC | Name | Status | Version | Provider AE | Created | Modified |"
_IC_SEP    = "|---|---|---|---|---|---|---|"


def _format_ic_row(ir: dict[str, Any], dekspec_dir: Path) -> str:
    iid = ir.get("id", "")
    name = (ir.get("name") or "").replace("|", "\\|").replace("\n", " ").strip()
    status = ir.get("status") or ""
    version = ir.get("version") or ir.get("ir_schema_version") or ""
    provider = ir.get("provider_ae") or ""
    created = ir.get("created") or ""
    modified = ir.get("modified") or ""
    rel = _find_kind_filename("IC", iid, dekspec_dir)
    id_cell = f"[{iid}]({rel})" if rel else iid
    return f"| {id_cell} | {name} | {status} | {version} | {provider} | {created} | {modified} |"


def regen_ic_index(repo_root, dekspec_root="dekspec", dry_run=False):
    return _regen_single_table_index(
        repo_root, dekspec_root, dry_run, "interface-contract-index.md", "IC",
        _IC_HEADER, _IC_SEP, _format_ic_row,
    )


def regen_all(
    repo_root: Path,
    dekspec_root: str = "dekspec",
    dry_run: bool = False,
) -> list[IndexResult]:
    """Regenerate every supported index file."""
    return [
        regen_intent_index(repo_root, dekspec_root=dekspec_root, dry_run=dry_run),
        regen_mission_index(repo_root, dekspec_root=dekspec_root, dry_run=dry_run),
        regen_adr_index(repo_root, dekspec_root=dekspec_root, dry_run=dry_run),
        regen_ae_index(repo_root, dekspec_root=dekspec_root, dry_run=dry_run),
        regen_ws_index(repo_root, dekspec_root=dekspec_root, dry_run=dry_run),
        regen_ic_index(repo_root, dekspec_root=dekspec_root, dry_run=dry_run),
    ]
