"""Shared, loss-aware Vision section matching for compiler and authoring gate."""
from __future__ import annotations

import re

REQUIRED_SECTIONS = (
    'What This Is', 'Who This Is For', 'Why This Exists',
    'What Success Looks Like', 'What We Are Not Building',
)


def normalize_heading(heading: str) -> str:
    return ' '.join(heading.split()).casefold()


def vision_sections(text: str) -> dict[str, str]:
    """Extract H2 bodies without interpreting headings inside fenced examples.

    Case and horizontal whitespace are presentation, not identity. Duplicate
    normalized headings are ambiguous; refuse rather than overwrite content.
    """
    sections: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    fence: tuple[str, int] | None = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if marker:
            token = marker[1]
            if fence is None:
                fence = (token[0], len(token))
            elif token[0] == fence[0] and len(token) >= fence[1] and not marker[2].strip():
                fence = None
            if current is not None:
                body.append(line)
            continue
        match = re.match(r'^##[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$', line.rstrip('\r\n')) if fence is None else None
        if match:
            if current is not None:
                sections[current] = ''.join(body).strip()
            current = normalize_heading(match[1])
            if current in sections:
                raise ValueError(f'Duplicate normalized heading: {match[1]!r}')
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        sections[current] = ''.join(body).strip()
    return sections
