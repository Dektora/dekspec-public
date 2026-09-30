"""AGENTS.md projection — the DekSpec-owned region of an instruction file (ADR-063).

DekSpec owns exactly one delimited region of the instruction file::

    <!-- dekspec:agents-md begin -->
    ...generated governing core...
    <!-- dekspec:agents-md end -->

Everything outside the region belongs to someone else and is preserved byte for
byte. This module owns the whole mechanism so that `dekspec aggregate agents-md`,
its `--check`, and the `dekspec doctor` section run one implementation:

- ownership parsing — line-anchored markers, fenced code ignored (IB-138 O-5);
- legacy recognition — the earlier generator's whole-file output, the historical
  `dekspec init` placeholders and the historical Codex marker (O-7), a generated
  layout only when its extent is exactly generator output (IB-142 O-2);
- rendering — deterministic, recording its settings and `RENDERER_REVISION`
  (O-12), refusing a partial graph and output that would not parse back;
- the verdict — current / stale / absent / inapplicable / invalid (O-6);
- the safe writer — atomic replace, permission bits kept, a re-read guard
  against concurrent writers, symbolic links followed only inside the
  repository (O-10).

The concurrency guard re-reads the file immediately before the atomic rename; a
writer that lands in the residual window between that re-read and the rename is
not detected.
"""
from __future__ import annotations

import difflib
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

import yaml

from .constraint_compiler.emitters import agents_md

#: Changes only in a commit that changes rendered output, never with the library
#: version (O-12). The digest of the fixed corpus rendered by this revision is
#: pinned in `tests/fixtures/agents-md-renderer-pin.json`.
RENDERER_REVISION: int = 1

BEGIN_MARKER = "<!-- dekspec:agents-md begin -->"
END_MARKER = "<!-- dekspec:agents-md end -->"

DEFAULT_PATH = "AGENTS.md"
DEFAULT_STATUS: tuple[str, ...] = ("ACCEPTED", "LOCKED")
# The governing core (ADR-056): work items reach agents through `dekspec ib context`.
DEFAULT_INCLUDE: tuple[str, ...] = (
    "CONSTITUTION", "SECURITY_PROFILE", "VISION", "GLOSSARY", "AE", "ADR", "IC", "WS",
)
VALID_KINDS = frozenset({
    "AE", "ADR", "IC", "WS", "IB", "INT", "MSN",
    "VISION", "GLOSSARY", "CONSTITUTION", "SECURITY_PROFILE",
})

_BOM = "﻿"
_OWNER_MARKER = re.compile(r"^<!--\s*([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+)\s+(begin|end)\s*-->$")
_FRAGMENT_MARKER = re.compile(r"^<!--\s*(BEGIN|END) dekspec-fragment:\s*(\S+)\s*-->$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_RECORDED_REVISION = re.compile(r"^\s*Renderer revision:\s*(\d+)\s*$")
_RECORDED_SETTINGS = re.compile(r"^\s*Projection settings:\s*(.*?)\s*$")
_REVISED_BY = re.compile(r"^\s*Revised by\s+((?:ADR-\d+)(?:\s*(?:,|and|&)\s*ADR-\d+)*)")

_MIGRATE_HINT = (
    "Preview the migration with `dekspec aggregate agents-md --migrate --dry-run`, "
    "then run `dekspec aggregate agents-md --migrate`."
)
_PLACE_MARKERS = (
    f"place the markers `{BEGIN_MARKER}` and `{END_MARKER}` (an empty pair suffices), "
    "each alone on its line, where the generated content belongs"
)


class ProjectionRefused(Exception):
    """Generation refused; the file is left untouched (exit 1)."""


class ProjectionUsageError(Exception):
    """A usage error (exit 2)."""


# --------------------------------------------------------------------------- #
# Settings and declaration (O-8)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Settings:
    dekspec_root: str = "dekspec"
    status: tuple[str, ...] | None = DEFAULT_STATUS  # None = every status
    include: tuple[str, ...] = DEFAULT_INCLUDE

    def normalized(self) -> Settings:
        root = self.dekspec_root.replace("\\", "/").rstrip("/") or "."
        status = None if self.status is None else tuple(sorted({s.upper() for s in self.status}))
        return Settings(root, status, tuple(sorted({k.upper() for k in self.include})))

    def describe(self) -> str:
        s = self.normalized()
        status = "all" if s.status is None else ",".join(s.status)
        return f"source={s.dekspec_root}/; status={status}; include={','.join(s.include)}"


def parse_status(value: Any) -> tuple[str, ...] | None:
    items = _as_items(value, "status")
    if len(items) == 1 and items[0].lower() == "all":
        return None
    return tuple(i.upper() for i in items)


def parse_include(value: Any) -> tuple[str, ...]:
    items = tuple(i.upper() for i in _as_items(value, "include"))
    bad = sorted(set(items) - VALID_KINDS)
    if bad:
        raise ProjectionUsageError(
            f"include contains unknown kinds: {bad}. Valid: {sorted(VALID_KINDS)}."
        )
    return items


def _as_items(value: Any, name: str) -> list[str]:
    if isinstance(value, str):
        items = [v.strip() for v in value.split(",") if v.strip()]
    elif isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        items = [v.strip() for v in value if v.strip()]
    else:
        raise ProjectionUsageError(f"{name} must be a list of strings or a comma-separated string")
    if not items:
        raise ProjectionUsageError(f"{name} is empty")
    return items


@dataclass(frozen=True)
class Declaration:
    configured: bool
    path: str
    settings: Settings
    required: bool
    error: str | None = None


def resolve_declaration(repo_root: Path, dekspec_root: str = "dekspec") -> Declaration:
    """The projection's declaration and settings: the configuration's `agents_md`
    block when present, else the defaults (O-8). Never the file's header."""
    from . import dekspec_config

    defaults = Declaration(False, DEFAULT_PATH, Settings(dekspec_root).normalized(), False)
    cfg_path = dekspec_config.config_path(repo_root)
    if not cfg_path.is_file():
        return defaults
    try:
        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as err:
        # Unreadable configuration: whether it declares a projection is unknown.
        return Declaration(True, DEFAULT_PATH, defaults.settings, False,
                           f"cannot read {cfg_path}: {err}")
    if not isinstance(raw, dict) or "agents_md" not in raw:
        return defaults
    block = raw["agents_md"]
    try:
        dekspec_config.load_config(repo_root)
    except dekspec_config.DekspecConfigError as err:
        return Declaration(True, DEFAULT_PATH, defaults.settings, False, str(err))
    block = block or {}
    try:
        status = parse_status(block["status"]) if "status" in block else DEFAULT_STATUS
        include = parse_include(block["include"]) if "include" in block else DEFAULT_INCLUDE
    except ProjectionUsageError as err:
        return Declaration(True, DEFAULT_PATH, defaults.settings, False,
                           f"invalid agents_md block in {cfg_path}: {err}")
    return Declaration(
        True,
        str(block.get("path") or DEFAULT_PATH),
        Settings(dekspec_root, status, include).normalized(),
        bool(block.get("required", False)),
    )


# --------------------------------------------------------------------------- #
# Ownership parsing (O-5, O-7)
# --------------------------------------------------------------------------- #


def _split_lines(text: str) -> list[str]:
    """Lines with their terminators; only LF (and CRLF) end a line."""
    lines = text.split("\n")
    out = [ln + "\n" for ln in lines[:-1]]
    if lines[-1]:
        out.append(lines[-1])
    return out


@dataclass
class Ownership:
    bom: bool
    body: str  # the text after an optional byte-order mark
    lines: list[str]
    region: tuple[int, int] | None = None  # line indices of the begin and end markers
    problems: list[str] = field(default_factory=list)
    stray_fragments: list[str] = field(default_factory=list)  # fragment ids outside any region
    dekspec_marker_lines: int = 0
    # Another owner's `<!-- <owner>:<block> begin|end -->` lines outside fenced code: (index, text).
    foreign_markers: list[tuple[int, str]] = field(default_factory=list)

    @property
    def region_text(self) -> str:
        assert self.region is not None
        b, e = self.region
        return "".join(self.lines[b:e + 1])

    def region_offsets(self) -> tuple[int, int]:
        assert self.region is not None
        b, e = self.region
        start = sum(len(ln) for ln in self.lines[:b])
        return start, start + sum(len(ln) for ln in self.lines[b:e + 1])


def parse_ownership(text: str) -> Ownership:
    bom = text.startswith(_BOM)
    body = text[1:] if bom else text
    lines = _split_lines(body)
    own = Ownership(bom=bom, body=body, lines=lines)

    begins: list[int] = []
    ends: list[int] = []
    foreign: list[tuple[int, str]] = []
    fragments: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None
    for i, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        m = _FENCE.match(line)
        if fence is None and m:
            fence = (m.group(1)[0], len(m.group(1)))
            continue
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and not m.group(2).strip():
                fence = None
            continue
        bare = line.strip()
        if bare == BEGIN_MARKER:
            begins.append(i)
        elif bare == END_MARKER:
            ends.append(i)
        elif _OWNER_MARKER.match(bare):
            foreign.append((i, bare))
        else:
            fm = _FRAGMENT_MARKER.match(bare)
            if fm:
                fragments.append((i, fm.group(2)))
    own.dekspec_marker_lines = len(begins) + len(ends)
    own.foreign_markers = foreign

    if begins or ends:
        if len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
            own.region = (begins[0], ends[0])
        else:
            own.problems.append(_describe_malformed(begins, ends))

    if own.region is not None:
        b, e = own.region
        inside = [(i, text_) for i, text_ in foreign if b < i < e]
        if inside:
            listing = ", ".join(f"line {i + 1} `{t}`" for i, t in inside)
            own.problems.append(
                f"another owner's block is inside the DekSpec region ({listing}). Recovery: move that "
                "block outside the region; content that claims another owner is never replaced."
            )
        stray = [(i, fid) for i, fid in fragments if not b < i < e]
    else:
        stray = fragments
    own.stray_fragments = sorted({fid for _, fid in stray})
    if stray and (own.region is not None or own.problems):
        own.problems.append(_describe_stray(stray))
    return own


def _describe_malformed(begins: list[int], ends: list[int]) -> str:
    where = ", ".join(
        [f"begin marker at line {i + 1}" for i in begins] + [f"end marker at line {i + 1}" for i in ends]
    )
    if len(begins) > 1 and len(ends) > 1:
        what = "more than one DekSpec region"
    elif len(begins) > 1:
        what = "a nested or repeated begin marker"
    elif len(ends) > 1:
        what = "a repeated end marker"
    elif not ends:
        what = "a begin marker without a matching end marker"
    elif not begins:
        what = "an end marker without a matching begin marker"
    else:
        what = "an end marker before its begin marker"
    return (
        f"malformed DekSpec region markers: {what} ({where}). Recovery: leave exactly one "
        f"`{BEGIN_MARKER}` line followed by one `{END_MARKER}` line and delete the others."
    )


def _describe_stray(stray: list[tuple[int, str]]) -> str:
    ids = sorted({fid for _, fid in stray})
    lines = ", ".join(str(i + 1) for i, _ in stray)
    return (
        f"DekSpec fragment markers outside the DekSpec region ({', '.join(ids)}; lines {lines}). "
        "Recovery: wrap them in the region or delete them; they are regenerated from the sources."
    )


# --------------------------------------------------------------------------- #
# Legacy layouts (O-7) — frozen texts; matching tolerates CRLF/LF and a BOM only
# --------------------------------------------------------------------------- #

_LEGACY_INIT_B2EE25A3 = """\
<!--
  AGENTS.md — placeholder authored by `dekspec init`.
  Re-generate this file with `dekspec aggregate agents-md` once your
  spec graph contains LOCKED or ACCEPTED artifacts.
-->

# AGENTS.md

This file is the compiled context surface for AI agents working in this repo.
It will be regenerated by `dekspec aggregate agents-md` after artifacts land.

Until then, read `dekspec/dekspec-operating-guide.md` for the methodology.
"""

_LEGACY_INIT_1F0A978D = """\
<!--
  AGENTS.md — placeholder authored by `dekspec init`.
  Re-generate this file with `dekspec aggregate agents-md` once your
  spec graph contains LOCKED or ACCEPTED artifacts.
-->

# AGENTS.md

This file is the compiled context surface for AI agents working in this repo.
It will be regenerated by `dekspec aggregate agents-md` after artifacts land.

Until then, read the methodology via `dekspec resource doc operating-guide`
(resolves from the wheel; falls back to `dekspec/dekspec-operating-guide.md`
if your repo has vendored a customized copy).
"""

_LEGACY_CODEX_74A7380D = (
    "# DekSpec (Codex)\n\n"
    "DekSpec skill suite installed under `.codex/`. "
    "Skills live in `.codex/skills/`, commands in `.codex/commands/`.\n"
)

_LEGACY_EXACT = {
    "the historical `dekspec init` placeholder (b2ee25a3)": _LEGACY_INIT_B2EE25A3,
    "the historical `dekspec init` placeholder (1f0a978d)": _LEGACY_INIT_1F0A978D,
    "the historical `dekspec install --platform codex` marker (74a7380d)": _LEGACY_CODEX_74A7380D,
}

_LEGACY_GENERATOR_HEAD = ("<!--", "  AGENTS.md — auto-generated by dekspec aggregate agents-md")

# Every line the earlier generator wrote between its fragments (IB-142 O-2 (b)): blank lines, `---`
# separators, and the fixed heading and one-line introduction of each fragment-bearing section. Taken
# from `cmd_aggregate_agents_md` in `tooling/dekspec/cli.py` at 3db7bc9f and each earlier version back
# to cf913f07 (the texts never changed) and matching every generated AGENTS.md in this repository's
# history. The Constitution, Security Profile, Vision and Glossary sections always precede the first
# fragment and carry no fragment markers, so their lines are not here.
_LEGACY_BETWEEN_FRAGMENTS = frozenset({
    "",
    "---",
    "# Architecture Elements",
    "Architectural slices that scope where each rule applies. When working in any path matched by an "
    "AE's `When working in` globs, treat its purpose, responsibilities, and boundaries as binding.",
    "# Architecture Decision Records",
    "Decisions that shape one or more AEs. Honor each ACCEPTED/LOCKED decision unless its "
    "`Reconsider this decision if` triggers fire — in which case stop and surface to the human.",
    "# Interface Contracts",
    "Binding cross-component contracts. Preserve them; a change goes through an unlock-to-version of "
    "the contract, never an implementation shortcut.",
    "# Working Specs",
    "Behavioral contracts. Business rules and failure behaviors are testable assertions; treat them as "
    "required when implementing or modifying code in scope.",
    "# Implementation Briefs",
    "Per-task implementation contracts. Each IB authorizes a specific scope of files-to-modify, lists "
    "Done When acceptance criteria, and points back at its parent Working Spec + Source AEs. When "
    "executing an IB, the listed scope is the only scope you are authorized to change.",
    "# Missions",
    "Cross-Intent coordination artifacts. Each Mission binds a set of Intents to a single "
    "user-observable outcome with explicit out-of-scope, flag strategy, kill criteria, and a Mission "
    "Verification predicate that gates COMPLETING → COMPLETE.",
    "# Intents",
    "Captured engineer intent — what change is being made and why. Each Intent declares its "
    "components_affected (diff confinement) and a Verification predicate (the TESTPASS gate). "
    "Intents under a Mission inherit the Mission's autonomy ceiling.",
})


@dataclass(frozen=True)
class Legacy:
    name: str
    end: int | None  # characters of `body` the legacy layout covers; None = no fragment end marker


@dataclass(frozen=True)
class LegacyMismatch:
    """A file that starts like the earlier generator's output but whose generated extent holds
    content that generator never wrote (IB-142 O-2): unrecognized content, never migrated."""
    line: int  # 1-based number of the first offending line
    text: str  # that line, without its terminator
    what: str  # what the line is, for the refusal
    extent_end: int  # 1-based number of the extent's last `END dekspec-fragment` line


def recognize_legacy(own: Ownership) -> Legacy | LegacyMismatch | None:
    """A recognized legacy layout in a file without DekSpec region markers; a `LegacyMismatch`
    when the file has the earlier generator's header but is not exactly that generator's output
    within its extent; otherwise None."""
    if own.dekspec_marker_lines:
        return None
    normalized = own.body.replace("\r\n", "\n")
    for name, text in _LEGACY_EXACT.items():
        if normalized == text:
            return Legacy(name, len(own.body))
    lines = own.lines
    if len(lines) < 3 or tuple(ln.rstrip("\r\n") for ln in lines[:2]) != _LEGACY_GENERATOR_HEAD:
        return None
    source_line = False
    for ln in lines[2:]:
        bare = ln.rstrip("\r\n")
        if bare == "-->":
            break
        if bare.startswith("  Source spec graph: "):
            source_line = True
    if not source_line:
        return None
    last_end = None
    for i, ln in enumerate(lines):
        m = _FRAGMENT_MARKER.match(ln.rstrip("\r\n").strip())
        if m and m.group(1) == "END":
            last_end = i
    name = "the earlier generator's whole-file output"
    if last_end is None:
        return Legacy(name, None)
    mismatch = _legacy_extent_mismatch(own, last_end)
    if mismatch is not None:
        return mismatch
    return Legacy(name, sum(len(ln) for ln in lines[:last_end + 1]))


def _legacy_extent_mismatch(own: Ownership, last_end: int) -> LegacyMismatch | None:
    """The first line of the legacy extent (lines 0..`last_end`) that the earlier generator did not
    write (IB-142 O-2): (a) another owner's marker outside fenced code anywhere in the extent, or
    (b) from the first fragment begin marker on, a line outside every `BEGIN`…`END dekspec-fragment`
    pair that is not one of the generator's fixed between-fragment lines."""
    found: list[tuple[int, str]] = []
    foreign = [(i, text) for i, text in own.foreign_markers if i <= last_end]
    if foreign:
        found.append((foreign[0][0], "another owner's block marker"))
    lines = own.lines
    first_begin = next(
        (i for i, ln in enumerate(lines[:last_end + 1])
         if (m := _FRAGMENT_MARKER.match(ln.rstrip("\r\n").strip())) and m.group(1) == "BEGIN"),
        None,
    )
    if first_begin is not None:
        current: tuple[int, str] | None = None  # (index, id) of the open fragment's begin marker
        for i in range(first_begin, last_end + 1):
            bare = lines[i].rstrip("\r\n")
            m = _FRAGMENT_MARKER.match(bare.strip())
            if current is not None:
                if m and m.group(1) == "END" and m.group(2) == current[1]:
                    current = None
                continue
            if m and m.group(1) == "BEGIN":
                current = (i, m.group(2))
            elif bare not in _LEGACY_BETWEEN_FRAGMENTS:
                found.append((i, "text the earlier generator never wrote between its fragments"))
                break
        if current is not None:
            # A begin marker never closed inside the extent is not part of a fragment pair.
            found.append((current[0], "a fragment begin marker without its end marker"))
    if not found:
        return None
    index, what = min(found)
    return LegacyMismatch(index + 1, lines[index].rstrip("\r\n"), what, last_end + 1)


def _describe_mismatch(m: LegacyMismatch, fragment_ids: list[str]) -> str:
    shown = m.text if len(m.text) <= 80 else m.text[:77] + "..."
    ids = f" ({', '.join(fragment_ids)})" if fragment_ids else ""
    return (
        f"the file starts like the earlier generator's output, but line {m.line} (`{shown}`) is {m.what}, "
        f"within the generated extent (its header through its last `END dekspec-fragment` line, line "
        f"{m.extent_end}). It is therefore not a recognized legacy layout and is not migrated: its DekSpec "
        f"fragment markers{ids} are outside any region. Recovery: move that content after the last fragment "
        f"end marker, where migration keeps it after the region, or place the region markers "
        f"`{BEGIN_MARKER}` and `{END_MARKER}` by hand around the generated content."
    )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


@dataclass
class Rendered:
    region: str  # LF line endings, begin line through end line with its newline
    parts: list[tuple[str, str]]  # (source label, text) — for naming a self-check failure
    counts: dict[str, int]


def _load_graph(repo_root: Path, settings: Settings):
    from .constraint_compiler.graph import SpecGraph

    graph = SpecGraph.load(repo_root, dekspec_root=settings.dekspec_root)
    failures = list(graph.parse_failures())
    if failures:
        listing = "; ".join(f"{_relpath(f.path, repo_root)} ({f.error_type}: {_first_line(f.message)})"
                            for f in failures[:10])
        more = f" and {len(failures) - 10} more" if len(failures) > 10 else ""
        raise ProjectionRefused(
            f"the specification graph has {len(failures)} parse failure(s): {listing}{more}. "
            "Refusing to render a partial projection; fix the sources (`dekspec audit linkage` "
            "lists them) and run the command again."
        )
    return graph


def _first_line(text: str) -> str:
    return (text or "").strip().splitlines()[0][:160] if (text or "").strip() else ""


def _relpath(path: str | Path, repo_root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def revisers_of(adr: dict[str, Any], in_force: set[str]) -> list[str]:
    """The ADRs named at the start of the ADR's Amendment Log rows' Change text
    (`Revised by ADR-NNN`), excluding itself, that pass the status filter (O-11)."""
    found: set[str] = set()
    for row in adr.get("amendment_log") or []:
        m = _REVISED_BY.match(str(row.get("change", "")))
        if m:
            found.update(re.findall(r"ADR-\d+", m.group(1)))
    found.discard(adr["id"])
    return sorted(found & in_force)


def _with_revisers(fragment: str, revisers: list[str]) -> str:
    if not revisers:
        return fragment
    lines = fragment.split("\n")
    at = next((i for i, ln in enumerate(lines) if ln.startswith("**Status:**")), 1)
    note = (f"**Revised by:** {', '.join(revisers)} — this decision is in force as revised; "
            "read it together with its revisers.")
    return "\n".join(lines[:at + 1] + [note] + lines[at + 1:])


def render(repo_root: Path, settings: Settings) -> Rendered:
    """Render the owned region from the specification graph (deterministic)."""
    settings = settings.normalized()
    repo_root = repo_root.resolve()
    graph = _load_graph(repo_root, settings)
    status_filter = None if settings.status is None else set(settings.status)
    include = set(settings.include)

    def passes(ir: dict[str, Any]) -> bool:
        return status_filter is None or str(ir.get("status", "")).upper() in status_filter

    def select(kind: str, items) -> list[dict[str, Any]]:
        if kind not in include:
            return []
        return [_rel(x, repo_root) for x in sorted((i for i in items if passes(i)), key=lambda x: x["id"])]

    aes = select("AE", graph.aes())
    adrs = select("ADR", graph.adrs())
    ics = select("IC", graph.ics())
    wses = select("WS", graph.wses())
    ibs = select("IB", graph.ibs())
    intents = select("INT", graph.intents())
    missions = select("MSN", graph.missions())
    vision = graph.vision() if "VISION" in include else None
    glossary = graph.glossary() if "GLOSSARY" in include else None
    constitution = graph.constitution() if "CONSTITUTION" in include else None
    security_profiles = select("SECURITY_PROFILE", graph.security_profiles())
    in_force_adrs = {a["id"] for a in graph.adrs() if passes(a)}

    def src(ir: dict[str, Any] | None, fallback: str) -> str:
        path = ((ir or {}).get("source") or {}).get("path")
        return _relpath(path, repo_root) if path else fallback

    parts: list[tuple[str, str]] = []

    def add(label: str, *lines: str) -> None:
        parts.append((label, "\n".join(lines)))

    add("header",
        "<!--",
        "  DekSpec-owned region, generated by `dekspec aggregate agents-md` from the",
        "  specification sources. Change the sources, not this region; everything",
        "  outside the begin and end markers belongs to others and is kept as is.",
        f"  Renderer revision: {RENDERER_REVISION}",
        f"  Projection settings: {settings.describe()}",
        "  Per-artifact fragments are framed by BEGIN and END dekspec-fragment comments.",
        "-->",
        "",
        "# AGENTS.md",
        "",
        (
            f"Compiled context for AI agents working in this repo. "
            f"{len(aes)} architecture element(s), {len(adrs)} decision record(s), "
            f"{len(ics)} interface contract(s), "
            f"{len(wses)} working spec(s), {len(ibs)} implementation brief(s), "
            f"{len(intents)} intent(s), {len(missions)} mission(s)."
            + (f" Glossary: {len(glossary['terms'])} terms." if glossary else "")
            + (f" Vision: {vision['name']}." if vision else "")
            + (f" Constitution: {len(constitution['articles'])} article(s)." if constitution else "")
            + (f" Security profiles: {len(security_profiles)}." if security_profiles else "")
        ),
        "")
    if not ({"IB", "INT", "MSN"} & include):
        add("header",
            "**How to use this file (ADR-055 / ADR-056).** This is the governing core: "
            "commitments, architecture, decisions, contracts and behavioral requirements "
            "currently in force. It deliberately omits work items (Missions, Intents, "
            "Implementation Briefs) and their execution history. When you work on an IB, "
            "run `dekspec ib context IB-NNN` — it delivers that IB's binding obligations "
            "from their canonical files, with revisions, acceptance conditions and the "
            "precedence to apply. Anything else in the repository (history, drafts, "
            "superseded decisions) may be read for information but does not bind.",
            "")

    # WS-006 BR7: the Constitution comes first after the header.
    if constitution:
        add(f"{src(constitution, 'constitution')} (Constitution)",
            "---", "", f"# Constitution: {constitution['name']}", "",
            "\n\n".join(agents_md.emit_constitution(constitution)), "")

    # WS-018: Security Profile fragments composed exactly as the emitter returns them.
    if security_profiles:
        add("Security Profile", "---", "", "## Security Profile", "")
        for sp in security_profiles:
            sp_for_emit = {
                **sp,
                "allowed_dataflows": [r["name"] for r in sp.get("allowed_dataflows", [])],
                "secret_stores": [r["name"] for r in sp.get("secret_stores", [])],
                "authn_methods": [r["name"] for r in sp.get("authn_methods", [])],
                "sast_tools": [r["name"] for r in sp.get("sast_tools", [])],
                "dast_tools": [r["name"] for r in sp.get("dast_tools", [])],
            }
            fragments = [f.replace("### ", "#### ", 1) for f in agents_md.emit_security_profile_soft(sp_for_emit)]
            add(f"{src(sp, sp['id'])} ({sp['id']})",
                f"### {sp['id']} — {sp['title']}", "", "\n\n".join(fragments), "")
        add("Security Profile", "---", "")

    if vision:
        lines = ["---", "", f"# System Vision: {vision['name']}", ""]
        if vision.get("preamble"):
            lines += [vision["preamble"], ""]
        if vision.get("what_this_is"):
            lines += ["## What this is", "", vision["what_this_is"], ""]
        if vision.get("what_we_are_not_building"):
            lines += ["## Out of scope (Vision-level)", ""]
            lines += [f"- {entry}" for entry in vision["what_we_are_not_building"]]
            lines += [""]
        add(f"{src(vision, 'system-vision.md')} (System Vision)", *lines)

    if glossary:
        terms = glossary["terms"]
        lines = [
            "---", "", "# Domain Glossary", "",
            f"Canonical definitions for {len(terms)} domain term(s) "
            f"across {len({t['category'] for t in terms})} categor(y/ies). "
            f"Read this before introducing or interpreting any domain term.",
            "",
        ]
        by_cat: dict[str, list[dict[str, Any]]] = {}
        for t in terms:
            by_cat.setdefault(t["category"], []).append(t)
        for cat in sorted(by_cat):
            lines += [f"## {cat}", ""]
            for t in by_cat[cat]:
                defn = t.get("canonical_definition", "")
                lines.append(f"- **{t['term']}** — {defn}" if defn else f"- **{t['term']}**")
            lines.append("")
        add(f"{src(glossary, 'domain-glossary.md')} (Domain Glossary)", *lines)

    def section(title: str, intro: str, items: list[dict[str, Any]], emit) -> None:
        if not items:
            return
        add(title, "---", "", f"# {title}", "", intro, "")
        for ir in items:
            add(f"{src(ir, ir['id'])} ({ir['id']})", emit(ir).rstrip("\n") + "\n")

    section("Architecture Elements",
            "Architectural slices that scope where each rule applies. "
            "When working in any path matched by an AE's `When working in` globs, "
            "treat its purpose, responsibilities, and boundaries as binding.",
            aes, agents_md.emit_ae)
    section("Architecture Decision Records",
            "Decisions that shape one or more AEs. Honor each ACCEPTED/LOCKED "
            "decision unless its `Reconsider this decision if` triggers fire — "
            "in which case stop and surface to the human.",
            adrs, lambda adr: _with_revisers(agents_md.emit_adr(adr), revisers_of(adr, in_force_adrs)))
    section("Interface Contracts",
            "Binding cross-component contracts. Preserve them; a change goes through "
            "an unlock-to-version of the contract, never an implementation shortcut.",
            ics, agents_md.emit_ic)
    section("Working Specs",
            "Behavioral contracts. Business rules and failure behaviors are "
            "testable assertions; treat them as required when implementing or "
            "modifying code in scope.",
            wses, agents_md.emit_ws)
    section("Implementation Briefs",
            "Per-task implementation contracts. Each IB authorizes a specific "
            "scope of files-to-modify, lists Done When acceptance criteria, "
            "and points back at its parent Working Spec + Source AEs. When "
            "executing an IB, the listed scope is the only scope you are "
            "authorized to change.",
            ibs, agents_md.emit_ib)
    section("Missions",
            "Cross-Intent coordination artifacts. Each Mission binds a set of "
            "Intents to a single user-observable outcome with explicit "
            "out-of-scope, flag strategy, kill criteria, and a Mission Verification "
            "predicate that gates COMPLETING → COMPLETE.",
            missions, agents_md.emit_mission)
    section("Intents",
            "Captured engineer intent — what change is being made and why. "
            "Each Intent declares its components_affected (diff confinement) "
            "and a Verification predicate (outcome evidence from `dekspec intent verify`). Intents under "
            "a Mission inherit the Mission's autonomy ceiling.",
            intents, agents_md.emit_intent)

    body = "\n".join(text for _, text in parts).replace("\r\n", "\n")
    body = body.rstrip("\n") + "\n"
    region = f"{BEGIN_MARKER}\n{body}{END_MARKER}\n"
    counts = {"AE": len(aes), "ADR": len(adrs), "IC": len(ics), "WS": len(wses)}
    return Rendered(region, parts, counts)


def _rel(ir: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Repository-relative POSIX provenance, so no machine path is embedded."""
    src = dict(ir.get("source") or {})
    if src.get("path"):
        src["path"] = _relpath(src["path"], repo_root)
    return {**ir, "source": src}


def _self_check(new_text: str, region: str, rendered: Rendered) -> None:
    """Refuse output that would not parse back as exactly the region it rendered."""
    own = parse_ownership(new_text)
    ok = (own.region is not None and not own.problems
          and own.region_text.replace("\r\n", "\n").rstrip("\n") == region.replace("\r\n", "\n").rstrip("\n"))
    if ok:
        return
    culprits = [label for label, text in rendered.parts if _part_breaks_region(text)]
    named = ", ".join(culprits) if culprits else "the rendered content"
    raise ProjectionRefused(
        f"the rendered region would not parse back as exactly one DekSpec region; the cause is in "
        f"{named} (a line that is an ownership or fragment marker, or an unbalanced code fence). "
        "Fix that source and run the command again."
    )


def _part_breaks_region(text: str) -> bool:
    fence: tuple[str, int] | None = None
    for line in text.split("\n"):
        m = _FENCE.match(line)
        if fence is None and m:
            fence = (m.group(1)[0], len(m.group(1)))
            continue
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and not m.group(2).strip():
                fence = None
            continue
        bare = line.strip()
        if bare in (BEGIN_MARKER, END_MARKER) or _OWNER_MARKER.match(bare):
            return True
    return fence is not None


# --------------------------------------------------------------------------- #
# The verdict (O-6)
# --------------------------------------------------------------------------- #


@dataclass
class Verdict:
    verdict: str  # current | stale | absent | inapplicable | invalid
    declared: str  # "configured" | "region" | "none"
    message: str
    required: bool = False

    @property
    def exit_code(self) -> int:
        if self.verdict in ("current", "inapplicable"):
            return 0
        if self.verdict == "absent" and not self.required:
            return 0
        return 1

    @property
    def doctor_status(self) -> str:
        if self.verdict == "inapplicable":
            return "skipped"
        if self.verdict == "current":
            return "clean"
        if self.declared != "configured":
            return "advisory"
        if self.verdict == "invalid":
            return "critical"
        if self.verdict == "absent" and not self.required:
            return "advisory"
        return "warning"


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except IsADirectoryError as err:
        raise ProjectionRefused(f"{path} is a directory, not an instruction file") from err


def _decode(data: bytes, path: Path) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as err:
        raise ProjectionRefused(f"{path} is not UTF-8 text ({err})") from err


def check(repo_root: Path, dekspec_root: str = "dekspec") -> Verdict:
    """Recompute the owned region read-only and return exactly one verdict.
    Never writes, never touches a modification time, never repairs anything."""
    repo_root = repo_root.resolve()
    decl = resolve_declaration(repo_root, dekspec_root)
    declared = "configured" if decl.configured else "none"
    rel = decl.path
    if decl.error:
        return Verdict("invalid", declared, f"invalid configuration: {decl.error}", decl.required)
    target = repo_root / decl.path
    try:
        data = _read(target)
        text = _decode(data, target) if data is not None else None
    except ProjectionRefused as err:
        return Verdict("invalid", declared, str(err), decl.required)

    def missing(why: str) -> Verdict:
        if decl.configured:
            need = "required" if decl.required else "declared but not required"
            fix = (" Create it with `dekspec aggregate agents-md` (a missing or empty file is created "
                   f"containing only the region); for a file with other content, {_PLACE_MARKERS} first."
                   if decl.required else "")
            return Verdict("absent", "configured", f"{rel} {why}; the projection is {need}.{fix}",
                           decl.required)
        return Verdict("inapplicable", "none",
                       f"no projection is declared and {rel} {why}; nothing to check.")

    if not text:
        return missing("does not exist" if text is None else "is empty")
    own = parse_ownership(text)
    if own.region is None and not own.problems:
        legacy = recognize_legacy(own)
        if isinstance(legacy, LegacyMismatch):
            # IB-142 O-2: unrecognized content with DekSpec fragment markers outside any region —
            # invalid when undeclared, absent (no region) when configured (IB-138 O-6).
            why = _describe_mismatch(legacy, own.stray_fragments)
            if not decl.configured:
                return Verdict("invalid", declared, f"{rel}: {why}", decl.required)
            need = "required" if decl.required else "declared but not required"
            return Verdict("absent", "configured",
                           f"{rel} has no DekSpec-owned region; the projection is {need}. "
                           f"{why[0].upper()}{why[1:]}", decl.required)
        if legacy is not None and legacy.end is None:
            return Verdict("invalid", declared,
                           f"{rel} is the earlier generator's output but has no fragment end marker, so its "
                           f"generated extent cannot be determined. Recovery: {_PLACE_MARKERS}.", decl.required)
        if legacy is not None:
            return Verdict("stale", declared,
                           f"{rel} is a recognized legacy layout ({legacy.name}) and needs migration. "
                           + _MIGRATE_HINT, decl.required)
        # O-6: for a configured projection a file without a region is absent, whatever else it holds.
        if own.stray_fragments and not decl.configured:
            return Verdict("invalid", declared, _describe_stray_ids(own.stray_fragments), decl.required)
        return missing("has no DekSpec-owned region")
    if own.region is not None and not decl.configured:
        declared = "region"
    if own.problems:
        return Verdict("invalid", declared, f"{rel}: " + " ".join(own.problems), decl.required)

    recorded = own.region_text.replace("\r\n", "\n")
    rec_revision, rec_settings = _recorded(recorded)
    if rec_revision is not None and rec_revision != RENDERER_REVISION:
        if rec_revision > RENDERER_REVISION:
            advice = ("It was written by a newer DekSpec; this older tool must not overwrite it. "
                      "Upgrade dekspec, then check again.")
        else:
            advice = "It was written by an older DekSpec; refresh it with `dekspec aggregate agents-md`."
        return Verdict("stale", declared,
                       f"{rel}: renderer mismatch — the region records renderer revision {rec_revision}, "
                       f"this tool renders revision {RENDERER_REVISION}. {advice}", decl.required)
    try:
        rendered = render(repo_root, decl.settings)
    except ProjectionRefused as err:
        return Verdict("invalid", declared, f"{rel}: {err}", decl.required)
    expected = rendered.region
    if recorded.rstrip("\n") == expected.rstrip("\n"):
        what = "the configured" if decl.configured else "the default"
        return Verdict("current", declared,
                       f"{rel} matches its specification sources under {what} settings "
                       f"({decl.settings.describe()}).", decl.required)
    reasons: list[str] = []
    if rec_revision is None:
        reasons.append("the region has never been generated")
    elif rec_settings is not None and rec_settings != decl.settings.describe():
        reasons.append(f"settings differ: the region records `{rec_settings}`, the "
                       f"{'configuration' if decl.configured else 'defaults'} resolve to "
                       f"`{decl.settings.describe()}`")
    if rec_revision is not None:
        reasons.extend(_differences(recorded, expected))
    return Verdict("stale", declared,
                   f"{rel} differs from its specification sources: {'; '.join(reasons) or 'content differs'}. "
                   "Regenerate it with `dekspec aggregate agents-md` and commit the result.", decl.required)


def _describe_stray_ids(ids: list[str]) -> str:
    return (f"DekSpec fragment markers outside any DekSpec region ({', '.join(ids)}). Recovery: wrap "
            "them in the region or delete them; they are regenerated from the sources.")


def _recorded(region: str) -> tuple[int | None, str | None]:
    revision = settings = None
    for line in region.split("\n")[:12]:
        m = _RECORDED_REVISION.match(line)
        if m and revision is None:
            revision = int(m.group(1))
        m = _RECORDED_SETTINGS.match(line)
        if m and settings is None:
            settings = m.group(1)
    return revision, settings


def _fragments(region: str) -> tuple[dict[str, str], str]:
    """Per-artifact fragment texts and the remaining (non-fragment) text."""
    frags: dict[str, list[str]] = {}
    rest: list[str] = []
    current: str | None = None
    for line in region.split("\n"):
        m = _FRAGMENT_MARKER.match(line.strip())
        if m and m.group(1) == "BEGIN":
            current = m.group(2)
            frags[current] = [line]
            continue
        if current is not None:
            frags[current].append(line)
            if m and m.group(1) == "END" and m.group(2) == current:
                current = None
            continue
        rest.append(line)
    return {k: "\n".join(v) for k, v in frags.items()}, "\n".join(rest)


def _differences(recorded: str, expected: str) -> list[str]:
    old, old_rest = _fragments(recorded)
    new, new_rest = _fragments(expected)
    changed = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    added = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    out = []
    if changed:
        out.append(f"changed {', '.join(changed)}")
    if added:
        out.append(f"added {', '.join(added)}")
    if removed:
        out.append(f"removed {', '.join(removed)}")
    if old_rest != new_rest:
        out.append("other content differs (" + _sections_differing(old_rest, new_rest) + ")")
    return out


def _sections_differing(old: str, new: str) -> str:
    def heading_at(lines: list[str], idx: int) -> str:
        for ln in reversed(lines[: idx + 1]):
            if ln.startswith("#"):
                return ln.lstrip("#").strip()
        return "region header"

    a, b = old.split("\n"), new.split("\n")
    names: list[str] = []
    for tag, i1, _i2, j1, _j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        name = heading_at(b, j1) if j1 < len(b) else heading_at(a, i1)
        if name not in names:
            names.append(name)
    shown = names[:5]
    return "in " + ", ".join(shown) + (f" and {len(names) - 5} more" if len(names) > 5 else "")


# --------------------------------------------------------------------------- #
# Generation and the safe writer (O-9, O-10)
# --------------------------------------------------------------------------- #


def _before_replace(path: object) -> None:
    """Test seam of the safe writer (O-10): called after rendering, immediately
    before the guarding re-read that precedes the atomic replace."""
    return None


def _uses_crlf(data: str) -> bool:
    return "\n" in data and data.count("\r\n") == data.count("\n")


def compose(existing: str | None, rendered: Rendered, *, migrate: bool) -> tuple[str, str]:
    """The new file text and a one-line description of the change. Raises
    `ProjectionRefused` for ownership problems and unmigrated legacy layouts."""
    region = rendered.region
    if not existing:
        return region, "created containing only the DekSpec region"
    own = parse_ownership(existing)
    if own.problems:
        raise ProjectionRefused(" ".join(own.problems))
    bom = _BOM if own.bom else ""
    if _uses_crlf(own.body):
        region = region.replace("\n", "\r\n")
    if own.region is not None:
        start, end = own.region_offsets()
        old_region = own.body[start:end]
        if not old_region.endswith("\n"):
            region = region.rstrip("\r\n")
        return bom + own.body[:start] + region + own.body[end:], "regenerated the DekSpec region"
    legacy = recognize_legacy(own)
    if isinstance(legacy, LegacyMismatch):
        raise ProjectionRefused(_describe_mismatch(legacy, own.stray_fragments))
    if legacy is not None and legacy.end is None:
        raise ProjectionRefused(
            "the file is the earlier generator's output but has no fragment end marker, so its generated "
            f"extent cannot be determined. Recovery: {_PLACE_MARKERS}; content outside them is kept."
        )
    if legacy is not None:
        if not migrate:
            raise ProjectionRefused(
                f"the file is a recognized legacy layout ({legacy.name}); it is migrated only on request. "
                + _MIGRATE_HINT
            )
        return bom + region + own.body[legacy.end:], f"migrated {legacy.name} to the owned-region format"
    if own.stray_fragments:
        raise ProjectionRefused(_describe_stray_ids(own.stray_fragments))
    raise ProjectionRefused(
        "the file has no DekSpec-owned region and is not a recognized legacy layout, so it is treated as "
        f"your content and not adopted. Recovery: {_PLACE_MARKERS}."
    )


def _resolve_target(path: Path, repo_root: Path) -> Path:
    """The file to write: a symbolic link is followed only to a target inside the repository."""
    if not path.is_symlink():
        return path
    real = Path(os.path.realpath(path))
    root = Path(os.path.realpath(repo_root))
    if real != root and root not in real.parents:
        raise ProjectionRefused(
            f"{path} is a symbolic link to {real}, outside the repository; refusing to write through it. "
            "Recovery: point the link inside the repository or replace it with a regular file."
        )
    return real


def safe_write(path: Path, original: bytes | None, new: bytes) -> None:
    """Atomic replace keeping permission bits; refuse if the file changed since it was read."""
    _before_replace(path)
    try:
        now = path.read_bytes()
    except FileNotFoundError:
        now = None
    except OSError as err:
        raise ProjectionRefused(f"cannot re-read {path} before writing: {err}") from err
    if now != original:
        raise ProjectionRefused(
            f"{path} changed since it was read (a concurrent writer?); nothing was written. "
            "Run the command again."
        )
    try:
        mode = path.stat().st_mode & 0o7777 if original is not None else None
    except OSError:
        mode = None
    if mode is None:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    tmp = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "wb") as fh:
            fh.write(new)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
        tmp = None
    except OSError as err:
        raise ProjectionRefused(f"write failed for {path}: {err}; the previous file is intact") from err
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def generate(
    repo_root: Path,
    target: Path,
    settings: Settings,
    *,
    migrate: bool = False,
    dry_run: bool = False,
    out: TextIO = sys.stdout,
) -> str:
    """Render and write the owned region of `target`. Returns a summary line.
    Raises `ProjectionRefused` (file untouched) on any refusal."""
    repo_root = repo_root.resolve()
    real = _resolve_target(target, repo_root)
    original = _read(real)
    existing = _decode(original, real) if original is not None else None
    if existing:
        # Ownership refusals come before any rendering work.
        own = parse_ownership(existing)
        if own.problems:
            raise ProjectionRefused(f"{target}: " + " ".join(own.problems))
    rendered = render(repo_root, settings)
    try:
        new_text, what = compose(existing, rendered, migrate=migrate)
    except ProjectionRefused as err:
        raise ProjectionRefused(f"{target}: {err}") from err
    _self_check(new_text, rendered.region, rendered)
    if dry_run:
        diff = difflib.unified_diff(
            (existing or "").replace("\r\n", "\n").splitlines(keepends=True),
            new_text.replace("\r\n", "\n").splitlines(keepends=True),
            fromfile=f"{target} (now)", tofile=f"{target} (after --migrate)",
        )
        out.write("".join(diff))
        return f"dry run: would have {what} in {target}; nothing was written"
    new = new_text.encode("utf-8")
    if original == new:
        return f"{target} is already current; nothing was written"
    safe_write(real, original, new)
    return f"{what} in {target} ({len(new)} bytes; renderer revision {RENDERER_REVISION})"
