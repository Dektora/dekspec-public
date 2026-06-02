"""Off-spec detection engine — MSN-009 / INT-051 (detection plane).

Pure classification surface. Given a ``SessionState`` and a list of staged
file paths it resolves the claimed session to its parent Intent, reads that
Intent's ``Components affected`` glob list, and partitions the staged files
into in-scope and off-spec sets by exact glob match (no fuzzy or
adjacent-file tolerance — MSN-009 §Out-of-scope).

Non-goals: no CLI verb (INT-052), no session-state mutation (INT-052), no
git hook (INT-053). The engine never writes a file, never mutates
``SessionState``, never logs — it returns a value and the caller decides
what to do with it. ``classify`` never raises on a normal classification:
malformed input resolves to a ``reason`` enum value, not an exception.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dekspec.session_lifecycle import SessionState

# Reason enum — exactly four values (see INT-051 §Desired Outcome / IB-081).
REASON_ON_SPEC = "on-spec"
REASON_OFF_SPEC = "off-spec"
REASON_NO_CLAIMED_INTENT = "no-claimed-intent"
REASON_UNRESOLVED_INTENT = "unresolved-intent"

# Repo-relative `dekspec/intents/` directory. Module-level so tests can
# monkeypatch it to a scratch tmp dir (IB-082 seam). __file__ is
# tooling/dekspec/vibecoding_guard.py → parent.parent.parent is the repo root.
_INTENTS_DIR = Path(__file__).resolve().parent.parent.parent / "dekspec" / "intents"

# Backtick-quoted bullet inside `## Components affected` — mirrors the
# Constraint Compiler's parser._INT_GLOB_BULLET so classification stays
# byte-consistent with `parse_intent`'s components_affected extraction.
_GLOB_BULLET = re.compile(r"^[-*]\s*`([^`]+)`(?:[ \t]+.*)?$", re.MULTILINE)
_H2_HEADER = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class _IntentResolutionError(Exception):
    """Internal — a claimed Intent could not be resolved or parsed.

    Caught inside ``classify`` and converted to the ``unresolved-intent``
    reason; never propagates out of the public surface.
    """


@dataclass(frozen=True)
class VibecodingResult:
    """Frozen result of an off-spec classification.

    ``off_spec_files`` / ``in_scope_files`` are sorted for deterministic
    output. ``claimed_intent_id`` is the resolved Intent id (e.g.
    ``INT-051``) or ``None`` when no Intent was resolved. ``reason`` is one
    of the four ``REASON_*`` constants.
    """

    off_spec_files: list[str]
    in_scope_files: list[str]
    claimed_intent_id: str | None
    reason: str


def _glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate a path glob to an anchored regex.

    ``**/`` matches zero or more leading path segments; ``**`` matches any
    run of characters including ``/``; ``*`` matches within a single
    segment (no ``/``); ``?`` matches one non-``/`` char. Everything else is
    literal. Exact-match discipline per MSN-009 — no fuzzy tolerance.
    """
    out: list[str] = []
    i, n = 0, len(glob)
    while i < n:
        if glob[i] == "*":
            if glob[i : i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
            elif glob[i : i + 2] == "**":
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _path_matches_glob(path: str, glob: str) -> bool:
    """True iff ``path`` matches ``glob`` exactly (literal or glob match)."""
    path = path.strip()
    glob = glob.strip()
    if not path or not glob:
        return False
    if path == glob:
        return True
    return _glob_to_regex(glob).match(path) is not None


def _read_components_affected(intent_path: Path) -> list[str]:
    """Parse the ``## Components affected`` section of an Intent file.

    Returns the backtick-quoted glob entries. Placeholder ``path/...``
    template entries are dropped (mirrors the Constraint Compiler parser).
    Raises ``_IntentResolutionError`` if the file is missing or unreadable
    — the caller converts that to the ``unresolved-intent`` reason.
    """
    try:
        text = intent_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise _IntentResolutionError(f"cannot read {intent_path}") from exc

    headers = list(_H2_HEADER.finditer(text))
    section = ""
    for idx, match in enumerate(headers):
        if match.group(1).strip().lower() == "components affected":
            start = match.end()
            end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
            section = text[start:end]
            break

    globs: list[str] = []
    for m in _GLOB_BULLET.finditer(section):
        glob = m.group(1).strip()
        if glob and not glob.startswith("path/"):
            globs.append(glob)
    return globs


def _resolve_intent(session: SessionState) -> tuple[str, Path] | None:
    """Resolve a session's binding to its parent Intent.

    Resolution order: (1) ``bound_intent_id`` → locate
    ``dekspec/intents/<id>-*.md`` directly; (2) ``bound_bead_id`` → scan
    every ``INT-*.md`` for the exact bead-id token, succeed only on a
    unique match; (3) no binding → ``None``. A ``None`` return on a present
    binding drives the ``unresolved-intent`` reason; a ``None`` return on no
    binding drives ``no-claimed-intent``.
    """
    intent_id = session.bound_intent_id
    if intent_id:
        matches = sorted(_INTENTS_DIR.glob(f"{intent_id}-*.md"))
        if len(matches) == 1:
            return intent_id, matches[0]
        return None

    bead_id = session.bound_bead_id
    if bead_id:
        token = re.compile(
            r"(?<![A-Za-z0-9_-])" + re.escape(bead_id) + r"(?![A-Za-z0-9_-])"
        )
        hits: list[tuple[str, Path]] = []
        for path in sorted(_INTENTS_DIR.glob("INT-*.md")):
            try:
                body = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if token.search(body):
                resolved_id = path.name.split("-", 2)
                hit_id = "-".join(resolved_id[:2])
                hits.append((hit_id, path))
        if len(hits) == 1:
            return hits[0]
        return None

    return None


def classify(
    session: SessionState | None, staged_files: list[str]
) -> VibecodingResult:
    """Classify ``staged_files`` against the claimed session's Intent scope.

    Returns a ``VibecodingResult`` partitioning the staged files into
    in-scope and off-spec sets. Never raises on a normal classification —
    an unresolvable / unparsable Intent resolves to ``unresolved-intent``,
    an absent or unbound session to ``no-claimed-intent``.
    """
    staged = sorted(f.strip() for f in staged_files if f and f.strip())

    if session is None:
        return VibecodingResult(
            off_spec_files=staged,
            in_scope_files=[],
            claimed_intent_id=None,
            reason=REASON_NO_CLAIMED_INTENT,
        )

    has_binding = bool(session.bound_intent_id or session.bound_bead_id)
    if not has_binding:
        return VibecodingResult(
            off_spec_files=staged,
            in_scope_files=[],
            claimed_intent_id=None,
            reason=REASON_NO_CLAIMED_INTENT,
        )

    try:
        resolved = _resolve_intent(session)
        if resolved is None:
            raise _IntentResolutionError("no unique Intent for session binding")
        intent_id, intent_path = resolved
        globs = _read_components_affected(intent_path)
    except _IntentResolutionError:
        return VibecodingResult(
            off_spec_files=staged,
            in_scope_files=[],
            claimed_intent_id=None,
            reason=REASON_UNRESOLVED_INTENT,
        )

    in_scope: list[str] = []
    off_spec: list[str] = []
    for path in staged:
        if any(_path_matches_glob(path, glob) for glob in globs):
            in_scope.append(path)
        else:
            off_spec.append(path)

    reason = REASON_OFF_SPEC if off_spec else REASON_ON_SPEC
    return VibecodingResult(
        off_spec_files=sorted(off_spec),
        in_scope_files=sorted(in_scope),
        claimed_intent_id=intent_id,
        reason=reason,
    )


__all__ = [
    "VibecodingResult",
    "classify",
    "REASON_ON_SPEC",
    "REASON_OFF_SPEC",
    "REASON_NO_CLAIMED_INTENT",
    "REASON_UNRESOLVED_INTENT",
]
