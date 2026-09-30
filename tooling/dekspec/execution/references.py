"""Resolve an IB's obligation references to their canonical text (ADR-056 §5).

An IB never restates an obligation owned by another artifact; it names the
artifact (and optionally a section). This module fetches the current text
from that one home, reports its status and a content hash, and refuses to
treat anything but an approved, in-force source as binding:

* missing artifact or section                → error
* SUPERSEDED / DEPRECATED / KILLED source    → error naming the successor
* DRAFT / PROPOSED / TODO source             → error (not yet approved)

The hash covers the extracted text only, so an edit elsewhere in the same
artifact does not stale the evidence of an IB that never referenced it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "APPROVED_STATUSES",
    "ResolvedObligation",
    "artifact_path",
    "artifact_status",
    "extract_section",
    "resolve_obligations",
]

APPROVED_STATUSES = frozenset({"ACCEPTED", "LOCKED", "COMPLETE", "ACTIVE"})
RETIRED_STATUSES = frozenset({"SUPERSEDED", "DEPRECATED", "KILLED"})

_KIND_DIRS: dict[str, tuple[str, bool]] = {
    "ADR": ("adrs", False),
    "IC": ("interface-contracts", False),
    "WS": ("working-specs", False),
    "AE": ("architecture-elements", False),
    "SP": ("security-profiles", False),
    "INT": ("intents", False),
    "MSN": ("missions", False),
    "IB": ("impl-briefs", True),
}
_SINGLETONS = {"CONSTITUTION": "constitution.md", "SYSTEM-VISION": "system-vision.md"}
# Default section when a reference names no `§Section`: an ADR binds through
# its Decision; the other kinds bind through their whole body.
_DEFAULT_SECTION = {"ADR": "Decision"}
_NON_BINDING_SECTIONS = {"status", "created", "modified", "date", "amendment log", "open issues",
                         "open questions / planned follow-ons", "supersession"}
_HEADING = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
_STATUS_H2 = re.compile(r"^##\s+Status\s*\n+\s*([A-Za-z_]+)", re.MULTILINE)
_STATUS_META = re.compile(r"^\*\*Status:\*\*\s*`?([A-Za-z_]+)", re.MULTILINE)
_SUPERSEDED_BY = re.compile(r"(?:\*Superseded by:\*|##\s*Superseded-By\s*\n+)\s*([A-Z]+-\d{3,}|none)", re.IGNORECASE)
_LOCAL_OBLIGATION = re.compile(r"^[-*]\s+\*\*(O-\d+)\*\*\s*\(local\):\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ResolvedObligation:
    id: str
    ref: str
    section: str | None
    note: str | None
    path: str | None
    status: str | None
    text: str
    sha256: str
    problem: str | None = None

    @property
    def ok(self) -> bool:
        return self.problem is None

    def manifest_entry(self) -> dict[str, Any]:
        return {"obligation": self.id, "ref": self.ref, "section": self.section,
                "path": self.path, "status": self.status, "sha256": self.sha256}


class AmbiguousReference(RuntimeError):
    """An obligation reference names an id several files carry."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def artifact_path(repo_root: Path, ref: str, *, spec_root: str = "dekspec") -> Path | None:
    base = Path(repo_root) / spec_root
    if ref in _SINGLETONS:
        p = base / _SINGLETONS[ref]
        return p if p.is_file() else None
    kind = ref.split("-", 1)[0]
    if kind not in _KIND_DIRS:
        return None
    sub, recursive = _KIND_DIRS[kind]
    folder = base / sub
    if not folder.is_dir():
        return None
    pattern = f"{ref}-*.md"
    found = sorted(folder.rglob(pattern) if recursive else folder.glob(pattern))
    if not found and kind == "SP":
        found = sorted(folder.glob(f"{ref}*.md"))
    if len(found) > 1:
        raise AmbiguousReference(f"{ref} matches {len(found)} files: " + ", ".join(
            str(f.relative_to(base)) for f in found))
    return found[0] if found else None


def artifact_status(text: str) -> str | None:
    m = _STATUS_H2.search(text) or _STATUS_META.search(text)
    return m.group(1).upper() if m else None


def _successor(text: str) -> str | None:
    m = _SUPERSEDED_BY.search(text)
    if m and m.group(1).lower() != "none":
        return m.group(1)
    return None


def extract_section(text: str, section: str | None) -> str | None:
    """Return the heading+body of the first H2–H4 whose title equals or
    starts with ``section`` (case-insensitive). ``None`` → the whole body
    minus lifecycle bookkeeping sections."""
    lines = text.splitlines()
    if section is None:
        out: list[str] = []
        skip_level = 0
        for line in lines:
            h = _HEADING.match(line)
            if h:
                level = len(h.group(1))
                if skip_level and level > skip_level:
                    continue
                skip_level = level if h.group(2).strip().lower() in _NON_BINDING_SECTIONS else 0
                if skip_level:
                    continue
            elif skip_level:
                continue
            out.append(line)
        return "\n".join(out).strip()
    want = section.strip().lower()
    for i, line in enumerate(lines):
        h = _HEADING.match(line)
        if not h:
            continue
        title = h.group(2).strip().lower()
        if title == want or title.startswith(want):
            level = len(h.group(1))
            body = [line]
            for nxt in lines[i + 1:]:
                hn = _HEADING.match(nxt)
                if hn and len(hn.group(1)) <= level:
                    break
                body.append(nxt)
            return "\n".join(body).strip()
    return None


def _resolve_one(repo_root: Path, ib_path: Path, ob: dict[str, Any], spec_root: str) -> ResolvedObligation:
    repo_root = Path(repo_root)
    if ob.get("local"):
        text = ob.get("text", "")
        rel = str(ib_path.relative_to(repo_root)) if ib_path.is_relative_to(repo_root) else str(ib_path)
        return ResolvedObligation(ob["id"], "local", None, None, rel, None, text, _sha(text))
    ref = ob["ref"]
    section = ob.get("section")
    note = ob.get("note")
    try:
        path = artifact_path(repo_root, ref, spec_root=spec_root)
    except AmbiguousReference as exc:
        return ResolvedObligation(ob["id"], ref, section, note, None, None, "", _sha(""), problem=str(exc))
    if path is None:
        return ResolvedObligation(ob["id"], ref, section, note, None, None, "", _sha(""),
                                  problem=f"{ref} does not exist under {spec_root}/")
    rel = str(path.relative_to(repo_root))
    text = path.read_text(encoding="utf-8")
    status = artifact_status(text)
    if status in RETIRED_STATUSES:
        succ = _successor(text)
        hint = f"; reference its successor {succ}" if succ else ""
        return ResolvedObligation(ob["id"], ref, section, note, rel, status, "", _sha(""),
                                  problem=f"{ref} is {status}{hint}")
    if status not in APPROVED_STATUSES:
        return ResolvedObligation(ob["id"], ref, section, note, rel, status, "", _sha(""),
                                  problem=f"{ref} is {status or 'without a status'} — not approved, so it cannot bind")
    kind = ref.split("-", 1)[0]
    if kind == "IB" and section and re.fullmatch(r"O-\d+", section.strip()):
        match = {m.group(1): m.group(2) for m in _LOCAL_OBLIGATION.finditer(text)}.get(section.strip())
        if match is None:
            return ResolvedObligation(ob["id"], ref, section, note, rel, status, "", _sha(""),
                                      problem=f"{ref} has no local obligation {section.strip()}")
        return ResolvedObligation(ob["id"], ref, section, note, rel, status, match, _sha(match))
    wanted = section or _DEFAULT_SECTION.get(kind)
    body = extract_section(text, wanted)
    if body is None:
        return ResolvedObligation(ob["id"], ref, section, note, rel, status, "", _sha(""),
                                  problem=f"{ref} has no section matching §{wanted}")
    return ResolvedObligation(ob["id"], ref, section, note, rel, status, body, _sha(body))


def resolve_obligations(repo_root: Path, contract: Any, *, spec_root: str = "dekspec") -> list[ResolvedObligation]:
    return [_resolve_one(repo_root, contract.path, ob, spec_root) for ob in contract.obligations]
