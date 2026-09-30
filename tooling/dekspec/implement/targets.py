"""Resolve an implementation request to approved targets (ADR-059).

A request is natural language: ``int-041``, ``INT-041 and INT-042``, ``the
authentication feature``. Explicit ids are case-normalized and zero-padded.
Whatever remains after the ids and connective words is a description, which
resolves only when exactly one Intent — or one parentless IB — matches every
significant word of it. Several matches are ambiguous and none is guessed; no
match is reported with the nearest candidates. Resolution never creates an
artifact, and a draft that matches is returned as what it is, so readiness can
say why it cannot be implemented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["Resolution", "Target", "resolve"]

_ID = re.compile(r"(?i)\b(int|ib)[-_ ]?(\d{1,4})\b")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset("""
a an the and or of for to in on with by as at is it this that these those please
implement implementing implementation build deliver ship make do run
feature features intent intents ib ibs work change changes spec specs thing
all way through end fully complete completely
""".split())


@dataclass(frozen=True)
class Target:
    id: str
    kind: str  # "intent" | "ib"
    path: Path
    status: str
    name: str
    provisional: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "path": str(self.path), "status": self.status,
                "name": self.name, "provisional": self.provisional}


@dataclass
class Resolution:
    targets: list[Target] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.targets) and not self.problems

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "targets": [t.as_dict() for t in self.targets], "problems": self.problems}


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


def _matches(want: str, have: set[str]) -> bool:
    return any(w == want or (len(want) >= 4 and w.startswith(want)) or (len(w) >= 4 and want.startswith(w))
               for w in have)


def _status_of(text: str) -> str:
    m = re.search(r"^##\s+Status\s*\n+\s*`?([A-Za-z_]+)", text, re.MULTILINE) or \
        re.search(r"^\*\*Status:\*\*\s*`?([A-Za-z_]+)", text, re.MULTILINE)
    return m.group(1).upper() if m else ""


def _title_of(text: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    title = m.group(1) if m else ""
    return re.sub(r"^(INT|IB)-\d+:\s*|^Implementation Brief:\s*", "", title).strip()


def _candidates(repo_root: Path, spec_root: str) -> list[Target]:
    base = Path(repo_root) / spec_root
    out: list[Target] = []
    for path in sorted((base / "intents").glob("INT-*.md")) if (base / "intents").is_dir() else []:
        text = path.read_text(encoding="utf-8", errors="replace")
        ident = re.match(r"(INT-\d+)", path.name).group(1)
        out.append(Target(ident, "intent", path, _status_of(text), _title_of(text)))
    for path in sorted((base / "provisional").rglob("INT*.md")) if (base / "provisional").is_dir() else []:
        text = path.read_text(encoding="utf-8", errors="replace")
        out.append(Target(f"provisional:{path.parent.name}", "intent", path, _status_of(text) or "DRAFT",
                          _title_of(text), provisional=True))
    for path in sorted((base / "impl-briefs").rglob("IB-*.md")) if (base / "impl-briefs").is_dir() else []:
        text = path.read_text(encoding="utf-8", errors="replace")
        parent = re.search(r"^\*\*Parent:\*\*\s*(\S+)", text, re.MULTILINE)
        if parent and parent.group(1).strip("`").upper().startswith("INT-"):
            continue  # reached through its Intent
        ident = re.match(r"(IB-\d+)", path.name).group(1)
        out.append(Target(ident, "ib", path, _status_of(text), _title_of(text)))
    return out


def _by_id(candidates: list[Target], ident: str) -> list[Target]:
    return [c for c in candidates if c.id == ident]


def resolve(repo_root: Path, request: str, *, spec_root: str = "dekspec") -> Resolution:
    request = re.sub(r"^\s*/?(?:[\w-]+:)?implement\b", "", request.strip(), flags=re.IGNORECASE)
    result = Resolution()
    candidates = _candidates(repo_root, spec_root)
    seen: set[str] = set()

    def add(target: Target) -> None:
        if target.id not in seen:
            seen.add(target.id)
            result.targets.append(target)

    for kind, digits in _ID.findall(request):
        ident = f"{kind.upper()}-{int(digits):03d}"
        found = _by_id(candidates, ident)
        if not found and kind.upper() == "IB":
            # Child IBs are not description candidates but are valid explicit targets.
            base = Path(repo_root) / spec_root / "impl-briefs"
            paths = sorted(base.rglob(f"{ident}-*.md")) if base.is_dir() else []
            found = [Target(ident, "ib", p, _status_of(p.read_text(encoding="utf-8", errors="replace")),
                            _title_of(p.read_text(encoding="utf-8", errors="replace"))) for p in paths]
        if len(found) == 1:
            add(found[0])
        elif not found:
            result.problems.append({"request": f"{kind}-{digits}", "code": "not-found",
                                    "detail": f"no {ident} under {spec_root}/"})
        else:
            result.problems.append({"request": ident, "code": "ambiguous",
                                    "detail": f"{ident} matches {len(found)} files",
                                    "candidates": [str(c.path) for c in found]})

    residue = _words(_ID.sub(" ", request))
    if residue:
        described = " ".join(residue)
        scored = []
        for c in candidates:
            if c.status == "SUPERSEDED":
                continue
            have = set(_words(c.name)) | set(_words(c.path.stem))
            hits = sum(1 for w in residue if _matches(w, have))
            if hits:
                scored.append((hits, c))
        full = [c for hits, c in scored if hits == len(residue)]
        if len(full) == 1:
            add(full[0])
        elif len(full) > 1:
            result.problems.append({"request": described, "code": "ambiguous",
                                    "detail": f"\"{described}\" matches {len(full)} artifacts; name one",
                                    "candidates": [f"{c.id} — {c.name} ({c.status})" for c in full]})
        else:
            near = [f"{c.id} — {c.name} ({c.status})" for _h, c in sorted(scored, key=lambda s: -s[0])[:5]]
            result.problems.append({"request": described, "code": "not-found",
                                    "detail": f"no Intent or standalone IB matches \"{described}\"",
                                    "candidates": near})
    if not result.targets and not result.problems:
        result.problems.append({"request": request, "code": "empty", "detail": "name an Intent, an IB or a feature"})
    return result
