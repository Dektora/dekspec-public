#!/usr/bin/env python3
"""Deterministic artifact operations for DekSpec authoring skills.

This script replaces prose instructions in authoring SKILL.md files that ask the
model to perform deterministic work: computing the next artifact id, reading and
guarding Status fields, transitioning an artifact between statuses, updating a
markdown index table, and finding cross-references.

It deliberately does NOT round-trip artifacts through the full IR. Reads use a
lightweight section/inline-field scan (two header conventions exist in the
DekSpec corpus); mutations are surgical line-level regex replacements so the rest
of the file is byte-for-byte preserved.

Runnable:   python artifact_ops.py <subcommand> ...
Importable: from artifact_ops import next_id, read_status, ...
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

# Canonical artifact-directory map. IC lives under dekspec/interface-contracts/
# (the on-disk dir name diverges from the "interface contract" term — confirmed
# against tooling/dekspec/package/build.py and migrations/markdown.py).
KIND_DIRS: dict[str, tuple[str, str]] = {
    "adr": ("adrs", "ADR"),
    "ae": ("architecture-elements", "AE"),
    "ws": ("working-specs", "WS"),
    "ic": ("interface-contracts", "IC"),
    "ib": ("impl-briefs", "IB"),
    "intent": ("intents", "INT"),
    "mission": ("missions", "MSN"),
}

# Canonical core status ladder shared by every artifact kind (parser.py
# _VALID_STATUSES). Kind-specific extra states (DEPRECATED, SUPERSEDED, IB/INT
# lifecycle states, Mission TODO/ACTIVE/...) are accepted as opaque tokens by
# status-guard/transition but only the core ladder is ordered for --expect-min.
STATUS_ORDER: list[str] = ["TODO", "DRAFT", "PROPOSED", "ACCEPTED", "LOCKED"]


def _repo_root(start: Path | None = None) -> Path:
    """Walk upward from `start` (or CWD) until a `dekspec/` directory is found."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "dekspec").is_dir():
            return candidate
    # Fall back to CWD; callers that need dekspec/ will fail with a clear error.
    return cur


# --------------------------------------------------------------------------
# Field reads — tolerate both header conventions in the corpus:
#   section style:  "## Status\n\nACCEPTED"   (ADR/AE/WS/IC/INT)
#   inline style:   "**Status:** ACCEPTED"    (IB/MSN)
# --------------------------------------------------------------------------

_INLINE_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _inline_re(field: str) -> re.Pattern[str]:
    pat = _INLINE_RE_CACHE.get(field)
    if pat is None:
        pat = re.compile(
            rf"^\*\*{re.escape(field)}:\*\*[ \t]*(?P<val>.+?)[ \t]*$",
            re.MULTILINE,
        )
        _INLINE_RE_CACHE[field] = pat
    return pat


def _section_value(text: str, field: str) -> str | None:
    """Return the first non-blank line of a `## <field>` section, if present."""
    sec = re.compile(
        rf"^#+[ \t]+{re.escape(field)}[ \t]*$", re.MULTILINE
    )
    m = sec.search(text)
    if not m:
        return None
    rest = text[m.end():]
    for line in rest.splitlines():
        s = line.strip()
        if s.startswith("#"):
            break
        if s:
            return s
    return None


def _read_field(text: str, field: str) -> str | None:
    """Read `field` (Status / Modified / ...) preferring the `## <field>`
    section heading over any inline `**<field>:**` form.

    Section heading is the canonical structural form for templated artifacts
    (Constitution, AE, ADR, IC, WS, Intent, Mission, SP); inline is only used
    by IB which has no section headings. Preferring the section heading
    prevents stray `**Status:** scaffold-only.` body lines (capability
    descriptors, sub-section markers) from short-circuiting the lookup.
    """
    section = _section_value(text, field)
    if section is not None:
        return section
    m = _inline_re(field).search(text)
    if m:
        return m.group("val").strip()
    return None


def read_status(text: str) -> str:
    """Extract the Status token, stripped of decoration. Raises if absent."""
    raw = _read_field(text, "Status")
    if raw is None:
        raise ValueError("artifact has no Status field")
    token = raw.split()[0].strip("`*_").upper()
    return token


# --------------------------------------------------------------------------
# next-id
# --------------------------------------------------------------------------

def next_id(kind: str, root: Path | None = None) -> str:
    """Scan the artifact directory for `<KIND>-NNN-*.md`; return next padded id."""
    kind = kind.lower()
    if kind not in KIND_DIRS:
        raise ValueError(
            f"unknown kind {kind!r}; expected one of {sorted(KIND_DIRS)}"
        )
    dirname, prefix = KIND_DIRS[kind]
    repo = _repo_root(root)
    art_dir = repo / "dekspec" / dirname
    if not art_dir.is_dir():
        raise FileNotFoundError(f"artifact directory not found: {art_dir}")
    pat = re.compile(rf"^{prefix}-(\d{{3,}})-.*\.md$")
    highest = 0
    width = 3
    for child in art_dir.iterdir():
        m = pat.match(child.name)
        if m:
            num = m.group(1)
            highest = max(highest, int(num))
            width = max(width, len(num))
    return f"{prefix}-{highest + 1:0{width}d}"


# --------------------------------------------------------------------------
# status-guard
# --------------------------------------------------------------------------

def _status_rank(status: str) -> int:
    try:
        return STATUS_ORDER.index(status.upper())
    except ValueError:
        raise ValueError(
            f"status {status!r} is not on the ordered ladder "
            f"({' < '.join(STATUS_ORDER)}); --expect-min cannot rank it"
        ) from None


def status_guard(
    path: Path, expect: str | None, expect_min: str | None
) -> tuple[bool, str]:
    """Return (ok, message). Exactly one of expect/expect_min must be set."""
    text = path.read_text(encoding="utf-8")
    actual = read_status(text)
    if expect is not None:
        if actual == expect.upper():
            return True, f"{path}: Status is {actual} (as expected)"
        return False, (
            f"{path}: Status is {actual}, expected {expect.upper()}"
        )
    if expect_min is not None:
        if _status_rank(actual) >= _status_rank(expect_min):
            return True, (
                f"{path}: Status is {actual} (>= {expect_min.upper()})"
            )
        return False, (
            f"{path}: Status is {actual}, expected at least {expect_min.upper()}"
        )
    raise ValueError("status-guard needs --expect or --expect-min")


# --------------------------------------------------------------------------
# transition — surgical Status flip + Modified bump + Amendment Log row
# --------------------------------------------------------------------------

def _replace_in_section(text: str, field: str, new: str) -> str | None:
    """Replace the first non-blank line under `## <field>` with `new`.
    Returns None if no `## <field>` heading exists."""
    sec = re.compile(rf"(^#+[ \t]+{re.escape(field)}[ \t]*$\n)", re.MULTILINE)
    m = sec.search(text)
    if not m:
        return None
    head = text[: m.end()]
    rest = text[m.end():]
    lines = rest.splitlines(keepends=True)
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("#"):
            break
        if s:
            lines[i] = re.sub(re.escape(s), new, line, count=1)
            return head + "".join(lines)
    return None


def _replace_status(text: str, new: str) -> str:
    """Replace the Status value in place, preferring section heading over
    inline form (mirrors _read_field precedence)."""
    replaced = _replace_in_section(text, "Status", new)
    if replaced is not None:
        return replaced
    inline = _inline_re("Status")
    if inline.search(text):
        return inline.sub(f"**Status:** {new}", text, count=1)
    raise ValueError("could not locate Status field to rewrite")


def _replace_modified(text: str, today: str) -> str:
    """Bump the Modified value if the artifact carries one (IB has none).
    Prefers section heading over inline form. Returns text unchanged when
    no Modified field is present."""
    replaced = _replace_in_section(text, "Modified", today)
    if replaced is not None:
        return replaced
    inline = _inline_re("Modified")
    if inline.search(text):
        return inline.sub(f"**Modified:** {today}", text, count=1)
    return text


_AMEND_HEADER_RE = re.compile(
    r"^\|[ \t]*Date[ \t]*\|.*\|[ \t]*$", re.MULTILINE
)


def _append_amendment_row(
    text: str,
    today: str,
    note: str,
    engineer: str,
    row_type: str = "Substantive",
) -> str:
    """Append one row to the Amendment Log table, if the section exists.

    `row_type` is the value placed in the table's `Type` column. The default
    `"Substantive"` matches the historical behavior used by `transition`; the
    Intent schema accepts `editorial`, `unlock`, and `substantive` (lowercase)
    per `intent.schema.yaml::amendment_log.items.properties.type.enum`. The
    `editorial_amend` codepath passes `"editorial"` here.
    """
    sec = re.compile(r"^#+[ \t]+Amendment Log[ \t]*$", re.MULTILINE)
    sm = sec.search(text)
    if not sm:
        return text  # No Amendment Log — skip silently.
    # Find the header + separator rows after the section heading.
    hm = _AMEND_HEADER_RE.search(text, sm.end())
    if not hm:
        return text
    # Walk past the contiguous block of table rows — the header, the
    # `|---|` separator, and any existing data rows — to the insertion
    # point, the end of the last row. The new row is appended BELOW that,
    # never spliced between the header and the separator.
    idx = hm.end()
    pos = hm.end()
    while pos < len(text):
        # Each iteration examines the next line; skip the leading newline
        # so `pos` lands on the first character of the line.
        if text[pos] == "\n":
            pos += 1
        if pos >= len(text):
            break
        line_end = text.find("\n", pos)
        if line_end == -1:
            line_end = len(text)
        line = text[pos:line_end]
        if not line.lstrip().startswith("|"):
            break
        idx = line_end
        pos = line_end
    row = f"\n| {today} | {row_type} | {note} | {engineer} |"
    return text[:idx] + row + text[idx:]


def transition(
    path: Path,
    from_status: str,
    to_status: str,
    note: str | None,
    engineer: str | None,
    today: str | None = None,
) -> str:
    """Flip Status from->to, bump Modified, append Amendment Log row.

    Returns a human-readable summary. Raises ValueError on a status mismatch.
    """
    today = today or datetime.date.today().isoformat()
    text = path.read_text(encoding="utf-8")
    actual = read_status(text)
    if actual != from_status.upper():
        raise ValueError(
            f"{path}: refusing transition — current Status is {actual}, "
            f"not {from_status.upper()}"
        )
    new_text = _replace_status(text, to_status.upper())
    new_text = _replace_modified(new_text, today)
    amended = False
    if note:
        before = new_text
        resolved_email = engineer or _git_user_email() or "unknown"
        new_text = _append_amendment_row(
            new_text, today, note, resolved_email
        )
        amended = new_text != before
    path.write_text(new_text, encoding="utf-8")
    summary = (
        f"{path}: Status {from_status.upper()} -> {to_status.upper()}, "
        f"Modified -> {today}"
    )
    if note:
        summary += (
            " (Amendment Log row appended)"
            if amended
            else " (no Amendment Log section — row skipped)"
        )
    return summary


# --------------------------------------------------------------------------
# approve — append a review-approval signature row to the Amendment Log
# --------------------------------------------------------------------------

def _git_user_email() -> str | None:
    """Resolve the engineer email from `git config user.email`. Returns None
    when git is unavailable or no email is configured."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    email = result.stdout.strip()
    return email or None


def _append_signature_row(
    text: str, today: str, target_status: str, engineer: str
) -> tuple[str, bool]:
    """Append one `review-approval` signature row to the Amendment Log table.

    Returns (new_text, appended). `appended` is False when the artifact has no
    `## Amendment Log` section — callers surface that as an error since an
    approval with nowhere to record the signature is a no-op.
    """
    sec = re.compile(r"^#+[ \t]+Amendment Log[ \t]*$", re.MULTILINE)
    sm = sec.search(text)
    if not sm:
        return text, False
    hm = _AMEND_HEADER_RE.search(text, sm.end())
    if not hm:
        return text, False
    # Walk past the contiguous block of table rows to the insertion point.
    idx = hm.end()
    pos = idx
    while pos < len(text):
        line_end = text.find("\n", pos)
        if line_end == -1:
            line_end = len(text)
        line = text[pos + 1 if text[pos] == "\n" else pos:line_end]
        if not line.lstrip().startswith("|"):
            break
        idx = line_end
        pos = line_end + 1
    row = (
        f"\n| {today} | review-approval | "
        f"Reviewed and approved for {target_status}. | {engineer} |"
    )
    return text[:idx] + row + text[idx:], True


def approve(
    path: Path,
    target_status: str,
    engineer: str | None,
    today: str | None = None,
) -> str:
    """Append a `review-approval` signature row to the artifact's Amendment Log.

    Resolves the engineer email from `--engineer` or `git config user.email`,
    appends a row of the form
    `| YYYY-MM-DD | review-approval | Reviewed and approved for <STATUS>. | <email> |`
    to the `## Amendment Log` table, and bumps the `Modified` field.

    Returns a human-readable summary. Raises ValueError when the email cannot
    be resolved or the artifact has no Amendment Log section.
    """
    today = today or datetime.date.today().isoformat()
    target_status = target_status.strip().upper()
    resolved_email = engineer or _git_user_email()
    if not resolved_email:
        raise ValueError(
            "could not resolve an engineer email — pass --engineer <email> "
            "or configure `git config user.email`"
        )
    text = path.read_text(encoding="utf-8")
    new_text, appended = _append_signature_row(
        text, today, target_status, resolved_email
    )
    if not appended:
        raise ValueError(
            f"{path}: no `## Amendment Log` section found — cannot record a "
            f"review-approval signature"
        )
    new_text = _replace_modified(new_text, today)
    path.write_text(new_text, encoding="utf-8")
    return (
        f"{path}: appended review-approval signature for {target_status} "
        f"by {resolved_email}, Modified -> {today}"
    )


# --------------------------------------------------------------------------
# editorial-amend — append an `editorial` Amendment Log row without flipping
# Status. Refuses with a named-field error if the diff between the on-disk
# Intent and its git-HEAD baseline touches a behavioral field (Verification,
# Components affected, Acceptance Criteria, or the Implementation Units list
# under `## Layer impact analysis`). See INT-088 IU-1, bead ds-uxpy.
# --------------------------------------------------------------------------

# Section headings that the editorial guard treats as BEHAVIORAL. A diff that
# adds, removes, or otherwise mutates any line inside any of these sections
# routes through full `--amend` (which cascades PROPOSED→DRAFT or
# ACCEPTED→DRAFT). `--editorial` REFUSES with a named-field error.
#
# The IU list lives under `## Layer impact analysis` per the Intent template
# (`templates/intent.md`); the bead body and INT-088 refer to it as the
# "Implementation Units (IU list)". The label below is the bead's wording so
# the refusal-error message names the field the engineer recognizes.
_BEHAVIORAL_SECTIONS: dict[str, str] = {
    # section heading exact text -> human-readable label used in refusal
    "Verification": "Verification block",
    "Components affected": "Components affected",
    "Acceptance Criteria": "Acceptance Criteria",
    "Layer impact analysis": "Implementation Units (IU list)",
}


def _split_sections(text: str) -> dict[str, str]:
    """Return a mapping of section-heading text to that section's body.

    A section is delimited by an `## <heading>` line (markdown level 2). The
    body extends from the line after the heading up to the next `## ` line or
    end-of-file. Sub-sections (`### ...`) stay inside the parent's body, which
    is what we want — a tweak to `### feature` inside `## Type-specific
    required fields` is captured under the parent section's body.

    Both the leading frontmatter and any prose before the first `## ` heading
    are stored under the empty-string key `""`.
    """
    sections: dict[str, str] = {}
    current = ""
    buf: list[str] = []
    heading_re = re.compile(r"^##[ \t]+(?P<title>.+?)[ \t]*$")
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        m = heading_re.match(stripped)
        if m:
            sections[current] = "".join(buf)
            current = m.group("title").strip()
            buf = []
            continue
        buf.append(line)
    sections[current] = "".join(buf)
    return sections


def classify_intent_diff(old_text: str, new_text: str) -> list[str]:
    """Return a list of behavioral-field labels whose section body changed
    between `old_text` and `new_text`.

    Empty list means the diff is editorial-safe (only narrative / metadata
    sections changed, or only whitespace changed inside a behavioral section
    in a way that did not alter that section's body byte-string).

    A non-empty list means full `--amend` (with cascade) is required — pass
    the list to the caller so the refusal error can name the offending
    field(s). The order matches `_BEHAVIORAL_SECTIONS.values()` so the
    user-facing message is stable.
    """
    old_sections = _split_sections(old_text)
    new_sections = _split_sections(new_text)
    touched: list[str] = []
    for heading, label in _BEHAVIORAL_SECTIONS.items():
        old_body = old_sections.get(heading)
        new_body = new_sections.get(heading)
        # Missing-in-one-side is itself a structural mutation of the
        # behavioral surface — treat as touched. A new Intent with no prior
        # Acceptance Criteria section still routes editorial-safe because
        # both sides are None for that heading.
        if old_body is None and new_body is None:
            continue
        if old_body != new_body:
            touched.append(label)
    return touched


# ADR editorial guard (ds-qxpq). For an ADR the editable surface is the
# cross-reference + discoverability prose — the `Decision` section (e.g. adding
# a mantra/principle opening), the `Links` section, and the Related/Linked
# Architecture Elements section. Everything that constitutes the *decision
# itself* is behavioral and must route through `--unlock` + `--lock`: Status,
# the supersession fields, Context, Options Considered, Consequences, and
# Validation. The guard is a DENY-list of those sections (a change inside any
# of them refuses) plus a targeted check on the top-of-file supersession lines
# (which live in the preamble, not under a `## ` heading).
_ADR_BEHAVIORAL_SECTIONS: dict[str, str] = {
    # `## ` heading (exact, or prefix-matched for "Context*") -> refusal label
    "Status": "Status",
    "Context and Decision Drivers": "Context",
    "Context": "Context",
    "Options Considered": "Options Considered",
    "Consequences": "Consequences",
    "Validation": "Validation",
}

_ADR_SUPERSESSION_RE = re.compile(
    r"^\*(?:Supersedes|Superseded by):\*.*$", re.MULTILINE
)


def _supersession_lines(text: str) -> str:
    """Return the ADR's top-of-file supersession lines as a stable string."""
    return "\n".join(_ADR_SUPERSESSION_RE.findall(text))


def classify_adr_diff(old_text: str, new_text: str) -> list[str]:
    """Return behavioral-field labels whose body changed between two ADR texts.

    Empty list == editorial-safe (only Decision / Links / Related AEs / Open
    Issues / preamble-metadata changed). A non-empty list means the change
    alters the decision and must go through `--unlock` + `--lock`.
    """
    old_sections = _split_sections(old_text)
    new_sections = _split_sections(new_text)
    touched: list[str] = []
    seen: set[str] = set()
    for heading, label in _ADR_BEHAVIORAL_SECTIONS.items():
        old_body = old_sections.get(heading)
        new_body = new_sections.get(heading)
        if old_body is None and new_body is None:
            continue
        if old_body != new_body and label not in seen:
            touched.append(label)
            seen.add(label)
    if _supersession_lines(old_text) != _supersession_lines(new_text):
        if "Supersession" not in seen:
            touched.append("Supersession")
    return touched


def _is_adr(path: Path) -> bool:
    """True when `path` is an ADR (under an `adrs/` dir or named `ADR-NNN-*`)."""
    name = path.name
    if name.startswith("ADR-"):
        return True
    return "adrs" in {p.name for p in path.parents}


def _git_head_text(path: Path) -> str | None:
    """Return the git-HEAD baseline contents of `path`, or None when git is
    unavailable, the file is untracked, or any subprocess error occurs.

    The editorial guard falls back to "no baseline" silently when this is
    None — the caller decides what to do (typically: treat as editorial-safe
    since there is no behavioral diff to refuse against; if the engineer
    wants belt-and-suspenders they pass `--baseline <path>` explicitly).
    """
    import subprocess

    repo = _repo_root(path.parent)
    try:
        rel = path.resolve().relative_to(repo.resolve())
    except ValueError:
        return None
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{rel.as_posix()}"],
            capture_output=True,
            text=True,
            cwd=repo,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def editorial_amend(
    path: Path,
    note: str,
    engineer: str | None,
    baseline_text: str | None = None,
    today: str | None = None,
) -> str:
    """Append an `editorial` Amendment Log row to the Intent at `path` and
    bump its Modified field. Does NOT flip Status.

    Refuses (raises ValueError) when the diff between `path`'s on-disk text
    and `baseline_text` (or its git-HEAD baseline when `baseline_text` is
    None) touches any field listed in `_BEHAVIORAL_SECTIONS`. The error
    names every offending field so the engineer can route the change
    through full `--amend` instead.

    Returns a human-readable summary on success.
    """
    today = today or datetime.date.today().isoformat()
    text = path.read_text(encoding="utf-8")
    baseline = baseline_text
    if baseline is None:
        baseline = _git_head_text(path)
    if baseline is None:
        # No baseline available — refuse to silently no-op the guard. The
        # caller can pass `--baseline /dev/null` explicitly to bypass.
        raise ValueError(
            f"{path}: no git-HEAD baseline available for diff classification "
            f"(file may be untracked or git is unavailable). Pass --baseline "
            f"<path-to-prior-version> to classify against an explicit baseline."
        )
    is_adr = _is_adr(path)
    touched = classify_adr_diff(baseline, text) if is_adr else classify_intent_diff(baseline, text)
    if touched:
        # Refusal-message contract — name the FIRST offending field. The
        # remedy differs by kind: an Intent routes through full `--amend`
        # (which cascades PROPOSED→DRAFT); a LOCKED ADR is immutable except via
        # the `--unlock` + `--lock` cycle (ds-qxpq).
        primary = touched[0]
        suffix = ""
        if len(touched) > 1:
            extras = ", ".join(touched[1:])
            suffix = f" (other behavioral fields also touched: {extras})"
        if is_adr:
            raise ValueError(
                f"--amend refused: diff touches decision field "
                f"{primary!r}.{suffix} Editorial amend may only change the "
                f"Decision prose, Links, and Related Architecture Elements. A "
                f"change to the decision itself must go through `--unlock` + "
                f"`--lock`."
            )
        raise ValueError(
            f"--editorial refused: diff touches behavioral field "
            f"{primary!r}.{suffix} Use --amend (without --editorial) for "
            f"behavioral revisions; that walk will cascade PROPOSED→DRAFT "
            f"or ACCEPTED→DRAFT as designed."
        )
    resolved_email = engineer or _git_user_email() or "unknown"
    new_text = _append_amendment_row(
        text, today, note, resolved_email, row_type="editorial"
    )
    if new_text == text:
        raise ValueError(
            f"{path}: no `## Amendment Log` section found — cannot record "
            f"an editorial amendment row"
        )
    new_text = _replace_modified(new_text, today)
    path.write_text(new_text, encoding="utf-8")
    return (
        f"{path}: appended editorial Amendment Log row by {resolved_email}, "
        f"Modified -> {today} (Status unchanged)"
    )


# --------------------------------------------------------------------------
# lite-gate — refusal-contract check + `lite: true` frontmatter marker for
# `/write-intent --lite` (INT-088 IU-2, bead ds-49mc).
#
# Lite Mode REFUSES unless ALL four gates pass:
#   1. Components affected ≤ 1
#   2. Implementation Units ≤ 1
#   3. Linked ADRs = [] (empty / "n/a" / "(none)")
#   4. Linked Interface Contracts = [] (empty / "n/a" / "(none)")
#
# The 4-gate check is mechanical: parse the canonical sections of the Intent
# file. Gate 1 reads `## Components affected`; gate 2 reads the IU list under
# `## Layer impact analysis` (or counts IU footnote bullets); gates 3 and 4
# read `## Linked ADRs` / `## Linked Interface Contracts` sections when
# present, else fall back to scanning `## Layer impact analysis` for ADR-NNN
# / IC-NNN tokens.
#
# Refusal message contract (the bead-body wording is the spec):
#   "--lite refused: gate <gate-name> failed (<reason>). Use full
#    /write-intent without --lite for this Intent."
# --------------------------------------------------------------------------

_LITE_GATES = ("components", "ius", "adrs", "ics")


def _section_lines(text: str, heading: str) -> list[str]:
    """Return the raw body lines under `## <heading>` up to the next `## `."""
    sec = re.compile(rf"^##[ \t]+{re.escape(heading)}[ \t]*$", re.MULTILINE)
    m = sec.search(text)
    if not m:
        return []
    rest = text[m.end():]
    out: list[str] = []
    for line in rest.splitlines():
        if re.match(r"^##[ \t]+\S", line):
            break
        out.append(line)
    return out


def _count_bullet_items(lines: list[str]) -> int:
    """Count Markdown bullet items in `lines`. Ignores narrative paragraphs,
    fenced commentary, italic notes, and `(none)` / `n/a` sentinels."""
    n = 0
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        # Italic note / commentary block (e.g. `*Note: ...*`).
        if s.startswith("*") and s.endswith("*") and not s.startswith("* "):
            continue
        # Bullet markers: `- `, `* `, `+ `, or numbered like `1. `.
        if s.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.\s", s):
            # Ignore explicit emptiness markers.
            body = re.sub(r"^[-*+]\s+|^\d+\.\s+", "", s).strip().lower()
            if body in {"(none)", "none", "n/a", "—", "-"}:
                continue
            n += 1
    return n


def _section_is_empty(lines: list[str]) -> bool:
    """Return True when a section body has no semantic content (only blanks,
    italic commentary, or explicit `(none)` / `n/a` sentinels)."""
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("*") and s.endswith("*") and not s.startswith("* "):
            continue
        if s.lower() in {"(none)", "none", "n/a", "—", "-"}:
            continue
        # Explicit "none" bullets count as empty too.
        body = re.sub(r"^[-*+]\s+|^\d+\.\s+", "", s).strip().lower()
        if body in {"(none)", "none", "n/a", "—", "-"}:
            continue
        return False
    return True


def _count_components_affected(text: str) -> int:
    """Count components in `## Components affected`. Each bullet is one entry."""
    lines = _section_lines(text, "Components affected")
    return _count_bullet_items(lines)


def _count_ius(text: str) -> int:
    """Count Implementation Units. Prefers the IU footnote-bullet block
    (lines beginning with `- IU N`) under `## Layer impact analysis`; falls
    back to the L3/L4 row count when no footnotes are present.

    Returns 0 when the section is absent or contains no IU bullets — a Lite
    Intent with no Layer impact analysis populated still has IU count = 0
    (which is ≤ 1, so the gate passes).
    """
    lines = _section_lines(text, "Layer impact analysis")
    if not lines:
        return 0
    # Look for explicit IU footnote bullets — `- IU 1` / `- IU-1` / `**IU 1**`.
    iu_pat = re.compile(r"^[-*+]\s+(?:\*\*)?IU[-\s]?\d+", re.IGNORECASE)
    iu_count = sum(1 for raw in lines if iu_pat.match(raw.strip()))
    if iu_count:
        return iu_count
    # Fallback: count IB-NNN / bead references in L3/L4 table rows. Cheap
    # heuristic — when a Lite Intent has no layer analysis at all we want 0.
    return 0


def _adr_section_empty(text: str) -> bool:
    """True when `## Linked ADRs` is absent or empty.

    The canonical Intent template does NOT include a `## Linked ADRs` section,
    so absence is the dominant case and means "no ADRs linked." When the
    section IS present (as in INT-088), it must have no ADR-NNN bullets.
    """
    lines = _section_lines(text, "Linked ADRs")
    if not lines:
        return True
    return _section_is_empty(lines)


def _ic_section_empty(text: str) -> bool:
    """True when `## Linked Interface Contracts` is absent or empty."""
    lines = _section_lines(text, "Linked Interface Contracts")
    if not lines:
        return True
    return _section_is_empty(lines)


def lite_gate_check(intent_path: Path) -> tuple[bool, str]:
    """Run the 4-gate refusal-contract check on `intent_path`.

    Returns `(True, summary)` when ALL four gates pass. Returns
    `(False, refusal_message)` naming the FIRST failing gate when any gate
    fails. The refusal-message format follows the bead ds-49mc contract:

        --lite refused: gate <gate-name> failed (<reason>). Use full
        /write-intent without --lite for this Intent.

    The four gate names (in evaluation order) are `components`, `ius`,
    `adrs`, `ics`.
    """
    text = intent_path.read_text(encoding="utf-8")

    # Gate 1 — components ≤ 1
    n_components = _count_components_affected(text)
    if n_components > 1:
        return False, (
            f"--lite refused: gate components failed "
            f"(measured {n_components} components, required ≤ 1). "
            f"Use full /write-intent without --lite for this Intent."
        )

    # Gate 2 — ius ≤ 1
    n_ius = _count_ius(text)
    if n_ius > 1:
        return False, (
            f"--lite refused: gate ius failed "
            f"(measured {n_ius} IUs, required ≤ 1). "
            f"Use full /write-intent without --lite for this Intent."
        )

    # Gate 3 — adrs = []
    if not _adr_section_empty(text):
        return False, (
            "--lite refused: gate adrs failed "
            "(Linked ADRs section has at least one entry, required []). "
            "Use full /write-intent without --lite for this Intent."
        )

    # Gate 4 — ics = []
    if not _ic_section_empty(text):
        return False, (
            "--lite refused: gate ics failed "
            "(Linked Interface Contracts section has at least one entry, "
            "required []). Use full /write-intent without --lite for this "
            "Intent."
        )

    return True, (
        f"{intent_path}: all 4 lite gates pass "
        f"(components={n_components}, ius={n_ius}, adrs=[], ics=[])"
    )


# Frontmatter regex: detects a YAML block at the very top of the file. The
# Intent template stores Status in a `## Status` section rather than YAML
# frontmatter, so most Intents have NO frontmatter at all. `lite_mark`
# handles both cases: when frontmatter exists, insert/replace `lite: true`
# inside; when absent, prepend a minimal `---\nlite: true\n---\n` block.
_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\n(?P<body>.*?)\n---[ \t]*\n",
    re.DOTALL,
)
_LITE_KEY_RE = re.compile(r"^lite:[ \t]*\S.*$", re.MULTILINE)


def lite_mark(intent_path: Path) -> str:
    """Set `lite: true` in the Intent's YAML frontmatter (creating the block
    if absent). Returns a human-readable summary.

    The marker is the audit signal — fidelity audit rules can filter
    lite-path Intents in later phases (OI-D, deferred). The function is
    idempotent: re-running it on an already-marked Intent leaves the file
    unchanged.
    """
    text = intent_path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if m:
        body = m.group("body")
        if _LITE_KEY_RE.search(body):
            # Already set — rewrite to canonical value, idempotent.
            new_body = _LITE_KEY_RE.sub("lite: true", body, count=1)
            if new_body == body:
                return f"{intent_path}: lite: true already set (no change)"
        else:
            # Append `lite: true` to the existing frontmatter block.
            sep = "" if body.endswith("\n") else "\n"
            new_body = body + sep + "lite: true"
        new_text = text[: m.start("body")] + new_body + text[m.end("body"):]
    else:
        # No frontmatter — prepend a minimal block.
        new_text = "---\nlite: true\n---\n" + text

    intent_path.write_text(new_text, encoding="utf-8")
    return f"{intent_path}: lite: true marker set in frontmatter"


# --------------------------------------------------------------------------
# update-index
# --------------------------------------------------------------------------

def update_index(index_path: Path, art_id: str, status: str) -> str:
    """Update (or append) the row for `art_id` in a markdown index table.

    Only the Status cell is rewritten on an existing row — every other column is
    preserved. If no row matches, a minimal row is appended after the last
    table row.
    """
    text = index_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    id_re = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(art_id)}(?![0-9])")
    status_up = status.upper()
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        cells = line.rstrip("\n").split("|")
        # cells[0] is the empty pre-pipe segment; the id is in cells[1].
        # Anchor the match on the ID cell only — substring-matching the whole
        # line would flip the wrong row when the ID literal happens to appear
        # in another row's Title / Notes / description cell
        # (bead ds-update-index-substring-match-wrong-row-bbhe).
        if len(cells) < 2 or not id_re.search(cells[1]):
            continue
        changed = False
        for j in range(1, len(cells)):
            token = cells[j].strip().strip("`*_").upper()
            if token in STATUS_ORDER or token in {
                # `TESTFAIL` retired from the Intent enum 2026-05-25 (E3
                # audit). `TODO` (in STATUS_ORDER) is kept because it remains
                # valid on non-Intent artifacts (AE/WS/IB/MSN).
                "DEPRECATED", "SUPERSEDED", "COMPLETE", "ACTIVE",
                "KILLED", "MERGED", "QUEUED", "COMPLETED",
                "IMPLEMENTING", "TESTPASS", "OVERSIZED",
            }:
                cells[j] = f" {status_up} "
                changed = True
                break
        if not changed:
            raise ValueError(
                f"{index_path}: found row for {art_id} but no Status cell to "
                f"update — check the table shape"
            )
        newline = "\n" if line.endswith("\n") else ""
        lines[i] = "|".join(cells) + newline
        index_path.write_text("".join(lines), encoding="utf-8")
        return f"{index_path}: updated {art_id} row -> Status {status_up}"

    # No existing row — append after the last table row.
    #
    # Derive the row shape from the index's existing header so the new row
    # has the same column count as every other row (ds-8r7m / R3 of
    # INT-091). Previously the appended row was hardcoded to 3 cells
    # (`| <id> | | <STATUS> |`), which malformed any index whose header
    # has 4+ columns (e.g., intent-index.md has 8). Now we:
    #   1. find the first table row (the header line) and the separator
    #      directly below it (`|---|---|...|`),
    #   2. count cells from the header (interior cells between leading and
    #      trailing pipes),
    #   3. construct a row of that exact width with the artifact ID in
    #      cell 0 and the new status in the cell whose header label looks
    #      like `Status` (case-insensitive). If no Status-labelled cell is
    #      found, place the status in cell 1 (legacy 3-column behavior).
    # Refuse-typed if the index has no header row to derive shape from.

    # Derive shape from — and insert into — the DATA table (skipping any
    # leading legend table). The shape-source and insert-target MUST be the
    # same table, else the row gets the wrong width / wrong Status column and
    # lands under the wrong table (ds-update-index-wrong-table-shape-z765).
    table = _find_data_table(lines)
    if table is None:
        raise ValueError(
            f"{index_path}: cannot append row for {art_id} — no markdown "
            "table header row found to derive column shape from. "
            "An index with no `| Column | ... |` + `|---|...|` header "
            "cannot accept a typed append."
        )
    header_idx, _sep_idx, last_row_idx = table

    header_cells = lines[header_idx].rstrip("\n").split("|")
    # cells[0] and cells[-1] are the empty pre/post-pipe segments. Interior
    # cells are header_cells[1:-1]; column count is len(interior).
    interior_headers = header_cells[1:-1]
    n_cols = len(interior_headers)

    # Find the Status column position (0-indexed within interior cells).
    status_col: int | None = None
    for col_idx, cell in enumerate(interior_headers):
        if cell.strip().lower() == "status":
            status_col = col_idx
            break
    if status_col is None:
        # No explicit Status header — fall back to col 1 (the legacy
        # 3-column shape `| id | <empty> | status |`).
        status_col = 1 if n_cols >= 2 else 0

    # Construct row: interior cell 0 = artifact id, status_col = status,
    # all others empty. Guard: never let the status overwrite the id cell —
    # if status_col resolved to 0 (degenerate / single-column table), keep
    # the id and drop the status rather than emit a `| <STATUS> |` row.
    interior = [""] * n_cols
    if n_cols >= 1:
        interior[0] = f" {art_id} "
    if status_col is not None and 0 < status_col < n_cols:
        interior[status_col] = f" {status_up} "
    row = "|" + "|".join(interior) + "|\n"

    # Insert after the data table's last row so the appended row stays grouped
    # with that table (not at the file's last table, which may be a different
    # table such as the Archive block).
    if not lines[last_row_idx].endswith("\n"):
        lines[last_row_idx] += "\n"
    lines.insert(last_row_idx + 1, row)
    index_path.write_text("".join(lines), encoding="utf-8")
    return f"{index_path}: appended new {art_id} row -> Status {status_up}"


def _find_header_and_separator(lines: list[str]) -> tuple[int | None, int | None]:
    """Return (header_idx, sep_idx) for the first markdown table in `lines`.

    Header is the first `|...|` line whose next non-blank line is a
    GFM separator (`|---|---|...|`). Returns (None, None) if no header
    is found.
    """
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        # Look ahead for the separator.
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            continue
        nxt = lines[j].strip()
        if not nxt.startswith("|"):
            continue
        # A separator row's interior cells must each contain only `-` and
        # optional leading/trailing `:` (alignment markers).
        sep_cells = nxt.split("|")[1:-1]
        if not sep_cells:
            continue
        if all(set(c.strip()) <= set("-:") and "-" in c for c in sep_cells):
            return i, j
    return None, None


def _find_data_table(
    lines: list[str],
) -> tuple[int, int, int] | None:
    """Return (header_idx, sep_idx, last_row_idx) for the index's DATA table.

    An index file may open with a legend table (e.g. `| Status | Meaning |`,
    2 columns, first column literally `Status`) before the real data table.
    The append path must derive its row shape from — and insert into — the
    SAME table, the data table, not the legend (ds-update-index-wrong-table-
    shape-z765). The data table is the first whose header has a `Status`
    column at index > 0 (a legend's `Status` is in column 0); legend-shaped
    tables (≤2 cols with a leading `Status`/`Meaning` header) are skipped.
    Falls back to the first table in the file when none qualifies, so a
    legacy 3-column `| id | | status |` index still appends. `last_row_idx`
    is the last contiguous `|`-row of the chosen table's block.
    """
    n = len(lines)
    first_table: tuple[int, int, int] | None = None
    i = 0
    while i < n:
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        j = i + 1
        while j < n and not lines[j].strip():
            j += 1
        sep_cells = lines[j].strip().split("|")[1:-1] if j < n and lines[j].strip().startswith("|") else []
        if not (sep_cells and all(set(c.strip()) <= set("-:") and "-" in c for c in sep_cells)):
            i += 1
            continue
        # `i` is a header row, `j` its separator. Find the block end.
        k = j + 1
        last = j
        while k < n and lines[k].lstrip().startswith("|"):
            last = k
            k += 1
        interior = [c.strip() for c in lines[i].rstrip("\n").split("|")[1:-1]]
        low = [c.lower() for c in interior]
        if first_table is None:
            first_table = (i, j, last)
        status_idx = next((idx for idx, c in enumerate(low) if c == "status"), None)
        is_legend = len(interior) <= 2 and (low[:1] == ["status"] or "meaning" in low)
        if status_idx is not None and status_idx > 0 and not is_legend:
            return (i, j, last)
        i = k
    return first_table


# --------------------------------------------------------------------------
# find-refs
# --------------------------------------------------------------------------

def find_refs(art_id: str, root: Path | None = None) -> list[str]:
    """Return file:line hits referencing `art_id` across the dekspec/ tree."""
    repo = _repo_root(root)
    tree = repo / "dekspec"
    if not tree.is_dir():
        raise FileNotFoundError(f"dekspec/ tree not found at {repo}")
    id_re = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(art_id)}(?![0-9])")
    hits: list[str] = []
    for md in sorted(tree.rglob("*.md")):
        try:
            content = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            if id_re.search(line):
                hits.append(f"{md}:{lineno}:{line.strip()}")
    return hits


# --------------------------------------------------------------------------
# check-retro-lock — the bead-closure gate for /write-intent --lock Path C
# (retroactive post-merge lock; INT-142, bead ds-zyef).
#
# Path C lets a zero-downstream direct-bead Intent whose work already merged to
# main reach LOCKED. This helper enforces the bead-closure portion of that gate
# deterministically: every bead the Intent names in its `## Layer impact
# analysis` must be `closed` in the beads JSONL. It validates each bead-shaped
# token against the beads DB so hyphenated prose ("write-intent") is not gated,
# and requires at least one resolvable closed bead so an Intent with no beads
# cannot rubber-stamp itself into LOCKED via Path C.
# --------------------------------------------------------------------------

# A bead id is lowercase `<prefix>-<suffix>` (e.g. `ds-zyef`); the all-caps
# artifact ids (INT-142, AE-006) never match. Suffix >= 3 chars rules out
# `fan-in`. Candidates are still filtered against the beads DB below, so a
# prose token that merely fits the shape is ignored unless it is a real bead.
_BEAD_TOKEN_RE = re.compile(r"\b[a-z][a-z0-9]*-[a-z0-9]{3,}\b")


def _beads_status_map(beads_file: Path) -> dict[str, str]:
    """Parse a beads JSONL file into `{bead_id: status}` (last record wins)."""
    out: dict[str, str] = {}
    with beads_file.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            bid = rec.get("id")
            if bid:
                out[bid] = (rec.get("status") or "").lower()
    return out


def check_retro_lock(
    intent_path: Path, beads_file: Path | None = None
) -> tuple[bool, str]:
    """Verify every bead in the Intent's Layer impact analysis is closed.

    Returns `(ok, message)`. `ok` is True only when at least one bead from the
    `## Layer impact analysis` resolves to the beads DB and every resolved bead
    has status `closed`. Bead-shaped tokens absent from the DB are ignored.
    """
    text = intent_path.read_text(encoding="utf-8")
    lines = _section_lines(text, "Layer impact analysis")
    if not lines:
        return False, (
            f"{intent_path}: no '## Layer impact analysis' section — cannot "
            f"determine the bead set for a Path C retroactive lock."
        )
    if beads_file is None:
        beads_file = _repo_root(intent_path.parent) / ".beads" / "issues.jsonl"
    if not beads_file.is_file():
        return False, f"{intent_path}: beads file not found at {beads_file}"

    status_map = _beads_status_map(beads_file)
    seen: set[str] = set()
    beads: list[str] = []
    for tok in _BEAD_TOKEN_RE.findall("".join(lines)):
        if tok in status_map and tok not in seen:
            seen.add(tok)
            beads.append(tok)

    if not beads:
        return False, (
            f"{intent_path}: no bead in the Layer impact analysis resolves to a "
            f"record in {beads_file} — a Path C retroactive lock requires at "
            f"least one closed bead as evidence the work landed."
        )

    open_beads = sorted(b for b in beads if status_map.get(b) != "closed")
    if open_beads:
        detail = ", ".join(f"{b}={status_map.get(b)!r}" for b in open_beads)
        return False, (
            f"{intent_path}: Path C retroactive lock refused — "
            f"{len(open_beads)} of {len(beads)} Layer-impact bead(s) not "
            f"closed: {detail}."
        )
    return True, (
        f"{intent_path}: Path C bead-closure gate PASS — all {len(beads)} "
        f"Layer-impact bead(s) closed ({', '.join(sorted(beads))})."
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="artifact_ops.py",
        description="Deterministic artifact operations for DekSpec skills.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")

    p_next = sub.add_parser("next-id", help="print the next artifact id")
    p_next.add_argument("kind", choices=sorted(KIND_DIRS))

    p_guard = sub.add_parser("status-guard", help="assert an artifact's Status")
    p_guard.add_argument("path", type=Path)
    g = p_guard.add_mutually_exclusive_group(required=True)
    g.add_argument("--expect", metavar="STATUS")
    g.add_argument("--expect-min", metavar="STATUS")

    p_tr = sub.add_parser("transition", help="flip an artifact's Status")
    p_tr.add_argument("path", type=Path)
    p_tr.add_argument("--from", dest="from_status", required=True)
    p_tr.add_argument("--to", dest="to_status", required=True)
    p_tr.add_argument("--note", default=None)
    p_tr.add_argument("--engineer", default=None)

    p_app = sub.add_parser(
        "approve",
        help="append a review-approval signature row to the Amendment Log",
    )
    p_app.add_argument("path", type=Path)
    p_app.add_argument("--target-status", dest="target_status", required=True)
    p_app.add_argument("--engineer", default=None)

    p_ed = sub.add_parser(
        "editorial-amend",
        help=(
            "append an `editorial` Amendment Log row to an Intent or ADR "
            "without flipping Status; refuses on behavioral-field diffs "
            "(Intent: INT-088; ADR: ds-qxpq — Decision/Links/Related-AEs only)"
        ),
    )
    p_ed.add_argument("path", type=Path)
    p_ed.add_argument(
        "--note",
        required=True,
        help="one-line summary of the editorial change (becomes the Notes cell)",
    )
    p_ed.add_argument("--engineer", default=None)
    p_ed.add_argument(
        "--baseline",
        default=None,
        type=Path,
        help=(
            "path to a prior version of the Intent to diff against. Defaults "
            "to the git-HEAD baseline. Pass /dev/null to bypass the guard."
        ),
    )

    p_lg = sub.add_parser(
        "lite-gate",
        help=(
            "run the /write-intent --lite 4-gate refusal-contract check on "
            "an Intent file (INT-088 IU-2)"
        ),
    )
    p_lg.add_argument("path", type=Path)

    p_lm = sub.add_parser(
        "lite-mark",
        help=(
            "set `lite: true` in an Intent's YAML frontmatter (creating "
            "the block if absent; idempotent)"
        ),
    )
    p_lm.add_argument("path", type=Path)

    p_idx = sub.add_parser("update-index", help="update a markdown index row")
    p_idx.add_argument("index_path", type=Path)
    p_idx.add_argument("--id", dest="art_id", required=True)
    p_idx.add_argument("--status", required=True)

    p_ref = sub.add_parser("find-refs", help="grep dekspec/ for an id")
    p_ref.add_argument("art_id", metavar="ID")

    p_crl = sub.add_parser(
        "check-retro-lock",
        help=(
            "verify every bead in an Intent's Layer impact analysis is closed "
            "— the bead-closure gate for /write-intent --lock Path C "
            "(retroactive post-merge lock)"
        ),
    )
    p_crl.add_argument("path", type=Path)
    p_crl.add_argument(
        "--beads-file",
        dest="beads_file",
        default=None,
        type=Path,
        help="path to the beads JSONL (default: <repo>/.beads/issues.jsonl)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help(sys.stderr)
        return 2

    try:
        if args.command == "next-id":
            print(next_id(args.kind))
            return 0

        if args.command == "status-guard":
            ok, msg = status_guard(args.path, args.expect, args.expect_min)
            if ok:
                print(msg)
                return 0
            print(msg, file=sys.stderr)
            return 1

        if args.command == "transition":
            print(
                transition(
                    args.path,
                    args.from_status,
                    args.to_status,
                    args.note,
                    args.engineer,
                )
            )
            return 0

        if args.command == "approve":
            print(
                approve(
                    args.path,
                    args.target_status,
                    args.engineer,
                )
            )
            return 0

        if args.command == "editorial-amend":
            baseline_text: str | None = None
            if args.baseline is not None:
                try:
                    baseline_text = args.baseline.read_text(encoding="utf-8")
                except OSError as exc:
                    print(
                        f"artifact_ops: could not read baseline "
                        f"{args.baseline}: {exc}",
                        file=sys.stderr,
                    )
                    return 1
            print(
                editorial_amend(
                    args.path,
                    args.note,
                    args.engineer,
                    baseline_text=baseline_text,
                )
            )
            return 0

        if args.command == "lite-gate":
            ok, msg = lite_gate_check(args.path)
            if ok:
                print(msg)
                return 0
            print(msg, file=sys.stderr)
            return 1

        if args.command == "lite-mark":
            print(lite_mark(args.path))
            return 0

        if args.command == "update-index":
            print(update_index(args.index_path, args.art_id, args.status))
            return 0

        if args.command == "find-refs":
            hits = find_refs(args.art_id)
            for hit in hits:
                print(hit)
            if not hits:
                print(f"no references to {args.art_id} found", file=sys.stderr)
                return 1
            return 0

        if args.command == "check-retro-lock":
            ok, msg = check_retro_lock(args.path, args.beads_file)
            if ok:
                print(msg)
                return 0
            print(msg, file=sys.stderr)
            return 1
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"artifact_ops: {exc}", file=sys.stderr)
        return 1

    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
