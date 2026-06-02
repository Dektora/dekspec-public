"""linked_artifacts emitter — derived backlinks -> rendered ``Related *`` lines.

ADR-015: an artifact's ``## Linked Artifacts`` section retains its
``Related ADRs`` / ``Related WSs`` / ``Related ICs`` / ``Related IBs`` /
``Related Intents`` lines as human-readable rendered output — but those lines
are now *emitted* from the SpecGraph-derived backlink mapping rather than
hand-maintained.

:func:`emit_linked_artifacts` is a pure markdown transform: it takes an
artifact's current markdown text plus the derived backlink mapping for that
artifact and returns the markdown with the five ``Related *`` lines replaced
by the derived, sorted values. It is a surgical line-replacement — every other
line in the section and every byte outside the section is preserved exactly.

Properties (ADR-015 §Validation point 4):
  - **Surgical** — only the five ``Related *`` lines change.
  - **Stable empty form** — a kind with zero referrers renders as
    ``Related ICs: none`` (the literal word ``none``).
  - **Idempotent** — feeding the emitter's own output back through it with the
    same derived mapping produces byte-identical output.
  - **Encoding / newline preserving** — UTF-8, LF line endings; the input
    file's exact trailing-newline state is preserved (never added, never
    stripped).

No I/O. The CLI verb (IB-042) reads/writes disk; this emitter only transforms
strings.

Public API:
  emit_linked_artifacts(artifact_markdown, derived_backlinks_for_artifact)
      -> EmitResult
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

EMITTER_VERSION = "0.1.0"

# The five backlink kinds, in canonical render order, paired with the
# bucket key produced by SpecGraph.derive_backlinks().
_BUCKETS: tuple[tuple[str, str], ...] = (
    ("Related ADRs", "related_adrs"),
    ("Related WSs", "related_wss"),
    ("Related ICs", "related_ics"),
    ("Related IBs", "related_ibs"),
    ("Related Intents", "related_intents"),
)
_LABELS: frozenset[str] = frozenset(label for label, _ in _BUCKETS)

# The literal stable form for an empty backlink set (matches the AE template's
# documented "use 'none' explicitly" convention).
_EMPTY_FORM = "none"

# Section heading: the line ``## Linked Artifacts`` (exactly an H2).
_SECTION_HEADING_RE = re.compile(r"^##\s+Linked Artifacts\s*$")
# Any markdown heading line — used to find where the section ends.
_HEADING_RE = re.compile(r"^#{1,6}\s+")
# A rendered ``Related *`` line. The ``head`` group captures everything up to
# and including the first ``:`` after the label — the bullet, optional bold
# markers, the label, and the colon (whether the colon is inside or outside a
# bold span). Re-emitting ``head`` verbatim preserves the artifact's exact
# styling; only the value after the colon is replaced. Tolerates the AE
# template's actual ``- **Related ADRs:** ...`` form (colon inside bold), the
# ``**Related ADRs**: ...`` form (colon outside bold), and the plain unbolded
# ``Related ADRs: ...`` form.
_RELATED_LINE_RE = re.compile(
    r"^(?P<head>\s*(?:[-*]\s+)?\*{0,2}"
    r"(?P<label>Related (?:ADRs|WSs|ICs|IBs|Intents))"
    r"\*{0,2}:\*{0,2})"
    r"(?P<rest>.*)$"
)


@dataclass(frozen=True)
class EmitResult:
    """Outcome of an :func:`emit_linked_artifacts` call.

    ``markdown`` is the transformed text. When the input artifact has no
    ``## Linked Artifacts`` section, ``has_section`` is ``False`` and
    ``markdown`` is the input returned unchanged.
    """

    markdown: str
    has_section: bool
    changed: bool


def _render_id_list(ids: Sequence[str]) -> str:
    """Render a sorted backlink ID list as the value half of a Related line."""
    if not ids:
        return _EMPTY_FORM
    return ", ".join(ids)


def emit_linked_artifacts(
    artifact_markdown: str,
    derived_backlinks_for_artifact: Mapping[str, Sequence[str]],
) -> EmitResult:
    """Replace the ``Related *`` lines in an artifact's ``## Linked Artifacts``.

    Args:
        artifact_markdown: the artifact's full current markdown text.
        derived_backlinks_for_artifact: the derived backlink mapping for *this*
            artifact — ``{"related_adrs": [...], "related_wss": [...],
            "related_ics": [...], "related_ibs": [...], "related_intents":
            [...]}``. Missing keys are treated as an empty list. The lists are
            expected to already be sorted (``SpecGraph.derive_backlinks``
            guarantees this); the emitter renders them in the given order.

    Returns:
        An :class:`EmitResult`. If the artifact has no ``## Linked Artifacts``
        section the result has ``has_section=False`` and the markdown is the
        input returned byte-for-byte unchanged — the emitter never invents a
        section.

    The transform is surgical: only the five ``Related *`` lines inside the
    section change. Every other byte — the heading, prose, sub-headings, any
    ``Owners:`` line, and the entire rest of the file — is preserved exactly,
    including the file's trailing-newline state.
    """
    # Preserve the exact trailing-newline state: splitlines() drops it, so
    # remember whether the input ended with a newline and restore it verbatim.
    ends_with_newline = artifact_markdown.endswith("\n")
    lines = artifact_markdown.splitlines()

    section_start: int | None = None
    for idx, line in enumerate(lines):
        if _SECTION_HEADING_RE.match(line):
            section_start = idx
            break

    if section_start is None:
        # No ## Linked Artifacts section — leave the file untouched.
        return EmitResult(markdown=artifact_markdown, has_section=False,
                          changed=False)

    # Section body runs until the next heading of any level (or EOF).
    section_end = len(lines)
    for idx in range(section_start + 1, len(lines)):
        if _HEADING_RE.match(lines[idx]):
            section_end = idx
            break

    rendered: dict[str, str] = {
        label: _render_id_list(
            list(derived_backlinks_for_artifact.get(bucket_key, []) or [])
        )
        for label, bucket_key in _BUCKETS
    }

    changed = False
    new_lines = list(lines)
    for idx in range(section_start + 1, section_end):
        m = _RELATED_LINE_RE.match(new_lines[idx])
        if m is None:
            continue
        label = m.group("label")
        if label not in _LABELS:
            continue
        # Rebuild the line: re-emit the captured ``head`` (bullet + bold
        # styling + label + colon) verbatim so the template's
        # ``- **Related ADRs:**`` form survives untouched; only the value
        # after the colon is replaced with the derived, sorted IDs.
        replacement = f"{m.group('head')} {rendered[label]}"
        if new_lines[idx] != replacement:
            new_lines[idx] = replacement
            changed = True

    out = "\n".join(new_lines)
    if ends_with_newline:
        out += "\n"
    return EmitResult(markdown=out, has_section=True, changed=changed)
