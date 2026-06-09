"""Interface Contract markdown -> IR parser.

Lossy by design. Fields the parser cannot extract from free-form prose populate
IR.parse_warnings rather than failing validation. Schema validation runs after
extraction; ICParseError is raised only if the resulting IR is structurally
invalid.

Public API: parse(path) -> dict
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .. import __version__ as DEKSPEC_VERSION
from ..severity import (
    ARTIFACT_SEVERITY_ALIAS_MAP as _SHARED_SEVERITY_ALIAS_MAP,
    CANONICAL_VALUES as _SEVERITY_CANONICAL_VALUES,
    is_canonical as _severity_is_canonical,
)

IR_SCHEMA_VERSION = "0.1.0"
PARSER_VERSION = DEKSPEC_VERSION

# Per-artifact IR schema versions for the five artifact types whose
# `open_issues[*].severity` enum tightens from legacy `{blocking,
# blocking_pre_ib, blocking_pre_code, non_blocking}` strings to canonical
# `{P0, P1, P2, P3}` (ADR-013 / IB-023 / WS-013). Bumped 0.1.0 → 0.2.0
# alongside the parser-side alias normalization landing in
# `_normalize_severity_alias`; the matching migration that re-keys
# persisted IR JSON lives in
# `tooling/dekspec/migrations/severity_unification.py`. Tracked
# separately from the global IR_SCHEMA_VERSION so the eight other
# artifact types (AE, glossary, vision, constitution) can stay pinned at
# 0.1.0 until their own schemas evolve.
_IC_IR_SCHEMA_VERSION = "0.2.0"
_WS_IR_SCHEMA_VERSION = "0.2.0"
_ADR_IR_SCHEMA_VERSION = "0.2.0"
_IB_IR_SCHEMA_VERSION = "0.3.0"
_INTENT_IR_SCHEMA_VERSION = "0.3.0"  # INT-104 IU-1 (ds-xoah)

# AE IR schema version. Bumped 0.1.0 → 0.2.0 at IB-044 (INT-034 / ADR-015):
# the stored `related_*s` backlink projections under `linked_artifacts` are
# retired — backlinks are derived from forward links and emitted by
# `dekspec relink`, not schema-validated input. Tracked separately from the
# global IR_SCHEMA_VERSION so glossary / vision / constitution stay at 0.1.0.
# The matching persisted-IR migration lands in IB-045.
_AE_IR_SCHEMA_VERSION = "0.2.0"


class ParseError(Exception):
    """Raised for cross-artifact structural failures shared by the five
    `open_issues`-carrying artifact types (IC, WS, ADR, IB, Intent).

    Today: raised by `_normalize_severity_alias` when an open-issues
    bullet carries a severity token that is neither canonical
    (`P0..P3`) nor any of the artifact-side legacy aliases registered
    in `dekspec.severity.ARTIFACT_SEVERITY_ALIAS_MAP`. Per-artifact
    `ICParseError` / `WSParseError` / `ADRParseError` / `IBParseError`
    / `IntentParseError` remain in place for artifact-specific
    structural failures (filename mismatch, schema validation, etc.);
    `ParseError` is the cross-artifact fallback for shared helpers.
    """


class DraftArtifactError(Exception):
    """Raised when a DRAFT-IDed artifact (`<KIND>-DRAFT-<slug>.md`) is parsed
    directly (INT-020).

    DRAFT artifacts carry a temporary `<KIND>-DRAFT-<slug>` ID that does not
    satisfy the IR schema's `^<KIND>-\\d{3,}$` `id` pattern. The corpus loader
    skips DRAFT files so they never enter the canonical audit graph; a direct
    `parse_*` call on one raises this clear typed error instead of the cryptic
    "filename does not match" `*ParseError`. Allocate canonical IDs first via
    `dekspec id allocate`.
    """


def _draft_id_or_none(filename: str) -> str | None:
    """Return the `<KIND>-DRAFT-<slug>` ID if `filename` is a DRAFT filename,
    else None. Single seam the per-kind `_extract_*_id` helpers consult before
    raising their canonical-filename-mismatch error."""
    from ..draft_ids import is_draft_filename, parse_draft_filename

    if not is_draft_filename(filename):
        return None
    kind, slug = parse_draft_filename(filename)
    return f"{kind}-DRAFT-{slug}"


# Parser-side legacy → canonical severity alias map. Imported from
# `dekspec.severity` (the leaf module that both this parser and the
# IB-024 audit engine share) and re-exposed under a parser-private
# name so the funnel helper `_normalize_severity_alias` can stay
# self-contained. A change to any row of this map requires an ADR-013
# amendment first — the per-alias unit tests under
# `tests/test_severity_normalization.py` lock the mapping.
_ARTIFACT_SEVERITY_ALIAS_MAP: dict[str, str] = dict(_SHARED_SEVERITY_ALIAS_MAP)


_TRAILING_PARENTHETICAL = re.compile(r"\s*\([^)]*\)\s*$")


def _normalize_severity_alias(raw: str) -> str:
    r"""Normalize an open-issues severity token to the canonical
    `P0|P1|P2|P3` ladder (ADR-013).

    Resolution order:
      1. Lowercase + strip the input.
      2. If the case-normalized input matches a canonical value (after
         re-uppercasing), return the canonical form unchanged.
      3. If the lowercased input is in
         `_ARTIFACT_SEVERITY_ALIAS_MAP`, return the mapped canonical
         (this is the exact-match path; covers both the four canonical
         legacy keys and the load-bearing variant spellings
         `blocking (pre-ib)` / `blocking (pre-code)`).
      4. Annotation-stripped retry: if the lowercased input has a
         trailing parenthetical descriptor (e.g., `non-blocking
         (resolved at merge time)`) OR an unbalanced open-paren
         (the upstream regex stopped capturing mid-parenthetical
         because the descriptor contained an em-dash or backtick),
         drop the descriptor and retry the alias-map lookup. This
         preserves the load-bearing variant spellings (which hit step
         3 first) while accepting the historical authoring convention
         of annotating an alias with an inline parenthetical
         rationale. Also retry against the leading bare-canonical
         token (e.g., `P3 (non-blocking; authoring detail)` →
         `P3`).
      5. Otherwise raise `ParseError` whose message includes the
         offending input verbatim (pre-strip, for engineer signal),
         the four canonical valid values, and the literal pointer
         "see ADR-013 for the legacy alias map".

    Audit-side aliases (`critical / important / minor`) are NOT
    handled here — they are owned by IB-024 in
    `dekspec.fidelity_audit`. Passing one to this helper raises.

    Backticks are stripped from both ends — the template's `**Severity:** \`P3\``
    convention (markdown code-formatting on the literal) would otherwise trip
    on whitespace where the regex captures around the backticks. Backticks
    are not part of the severity vocabulary; strip and normalize.
    """
    stripped = raw.strip().strip("`").strip()
    folded = stripped.lower()
    if folded:
        upper = folded.upper()
        if _severity_is_canonical(upper):
            return upper
        mapped = _ARTIFACT_SEVERITY_ALIAS_MAP.get(folded)
        if mapped is not None:
            return mapped
        # Annotation-stripped retry — handles the historical authoring
        # convention of decorating a legacy alias with an inline
        # parenthetical rationale (e.g. `non-blocking (resolved at
        # merge time)`). The load-bearing variant spellings
        # `blocking (pre-ib)` and `blocking (pre-code)` are in the
        # alias map and already matched at the previous step, so
        # stripping the parenthetical here does NOT collide with
        # ADR-013's per-row mapping.
        annotated = _TRAILING_PARENTHETICAL.sub("", folded).strip()
        if annotated and annotated != folded:
            mapped = _ARTIFACT_SEVERITY_ALIAS_MAP.get(annotated)
            if mapped is not None:
                return mapped
            up = annotated.upper()
            if _severity_is_canonical(up):
                return up
        # Unbalanced-paren retry — the upstream regex may have stopped
        # mid-parenthetical (e.g. when the descriptor contains an
        # em-dash or backtick that falls outside the regex's char
        # class). Truncate at the first `(`.
        if "(" in folded:
            head = folded.split("(", 1)[0].rstrip()
            if head and head != folded:
                mapped = _ARTIFACT_SEVERITY_ALIAS_MAP.get(head)
                if mapped is not None:
                    return mapped
                up = head.upper()
                if _severity_is_canonical(up):
                    return up
    valid = ", ".join(repr(v) for v in _SEVERITY_CANONICAL_VALUES)
    raise ParseError(
        f"Unknown severity {raw!r}: expected one of {valid} "
        f"(see ADR-013 for the legacy alias map)."
    )

_IC_FILENAME = re.compile(r"^(IC-\d{3,})-.+\.md$")
_H1_TITLE = re.compile(r"^#\s+Interface Contract:\s*(.+?)\s*$", re.MULTILINE)
_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_SEMVER = re.compile(r"\b(\d+\.\d+\.\d+)\b")
_DOMAIN_LINE = re.compile(r"^-\s*\[(x| )\]\s*(.+?)$", re.MULTILINE | re.IGNORECASE)
_ADR_LINE = re.compile(
    r"^[-*]\s*\[?ADR-(\d{3,})\]?\s*[:\-—]\s*"
    r"(?P<title>[^—\n]+?)"
    r"(?:\s+—\s+(?P<summary>.+?))?\s*$",
    re.MULTILINE,
)
_BULLET = re.compile(r"^[-*]\s+(.+?)$", re.MULTILINE)
_PARTY_BULLET = re.compile(
    r"^[-*]\s*\*\*(?P<name>.+?)\*\*\s*"
    r"(?:\((?P<hint>[^)]+)\))?\s*"
    r"[—\-:]\s*(?P<desc>.+?)$",
    re.MULTILINE,
)
_PATTERN_LINE = re.compile(r"^\*\*Pattern:\*\*\s*(.+?)\s*$", re.MULTILINE)
_CHANGE_IMPACT = re.compile(
    r"^\*\*Change impact:\*\*\s*(.+?)$", re.MULTILINE | re.DOTALL
)
_AE_ID = re.compile(r"\b(AE-\d{3,})\b")
_SIGNATURE = re.compile(
    r"`([a-zA-Z_][\w]*)\s*\(([^`]*?)\)\s*->\s*([^`]+?)`"
)
_OPEN_ISSUE_BULLET = re.compile(
    r"^[-*]\s*\[[ x]\]\s*(.+?)$",
    re.MULTILINE | re.IGNORECASE,
)
# Same shape as _OPEN_ISSUE_BULLET but with named state + text groups so
# the IC/IB/ADR/Intent extractor can filter resolved `[x]` rows (IB-023
# aligned the two extractors on the same skip-resolved predicate; see
# `_extract_open_issues` for the rationale).
_OPEN_ISSUE_BULLET_WITH_STATE = re.compile(
    r"^[-*]\s*\[(?P<state>[ x])\]\s*(?P<text>.+?)$",
    re.MULTILINE | re.IGNORECASE,
)

_DOMAIN_SLUGS = {
    "transformer internals": "transformer_internals",
    "numerical precision": "numerical_precision",
    "gpu multi-process isolation": "gpu_multi_process_isolation",
    "graph consistency": "graph_consistency",
    "timeline coherence": "timeline_coherence",
}

_PATTERN_SLUGS = {
    "open host service": "open_host_service",
    "customer-supplier": "customer_supplier",
    "customer supplier": "customer_supplier",
    "anti-corruption layer": "anti_corruption_layer",
    "anti corruption layer": "anti_corruption_layer",
    "conformist": "conformist",
    "shared kernel": "shared_kernel",
    "published language": "published_language",
}

_PROVIDER_KEYWORDS = ("provider", "supplier", "host", "callee", "writer", "server")
_CONSUMER_KEYWORDS = ("consumer", "caller", "client", "reader", "subscriber")

_VALID_STATUSES = {"TODO", "DRAFT", "PROPOSED", "ACCEPTED", "LOCKED", "DEPRECATED"}


@dataclass
class _Warn:
    field: str
    reason: str
    severity: str = "warning"

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason, "severity": self.severity}


@dataclass
class _ParseContext:
    src: Path
    text: str
    sections: dict[str, str]
    warnings: list[_Warn] = field(default_factory=list)


class ICParseError(Exception):
    """Raised when an IC's parsed IR fails schema validation."""


def parse(path: str | Path) -> dict[str, Any]:
    """Parse an Interface Contract markdown file into a validated IR dict.

    Schema-required fields that cannot be extracted raise ICParseError.
    Optional fields that cannot be extracted populate parse_warnings.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    ctx = _ParseContext(src=src, text=text, sections=_split_sections(text))

    ir: dict[str, Any] = {
        # IC IR bumped 0.1.0 → 0.2.0 at IB-023 (severity vocabulary
        # unification — see ADR-013); `open_issues[*].severity` is
        # now canonical `P0..P3` rather than legacy `{blocking,
        # non_blocking}`.
        "ir_schema_version": _IC_IR_SCHEMA_VERSION,
        "id": _extract_id(src.name, ctx),
        "name": _extract_name(text, ctx),
        "status": _extract_status(ctx),
        "version": _extract_version(ctx),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "interface_definition": _extract_interface_definition(ctx),
    }

    _maybe_set(ir, "created", _extract_first_date(ctx.sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(ctx.sections.get("Modified", "")))

    domains = _extract_domains(ctx.sections.get("Silent Failure Domain(s)", ""))
    if domains:
        ir["silent_failure_domains"] = domains

    adrs = _extract_governing_adrs(ctx.sections.get("Governing ADRs", ""))
    if adrs:
        ir["governing_adrs"] = adrs

    purpose = ctx.sections.get("Purpose", "").strip()
    if purpose:
        ir["purpose"] = purpose

    parties_body = ctx.sections.get("Parties", "")
    parties = _extract_parties(parties_body, ctx)
    if parties:
        ir["parties"] = parties

    # New in v0.3.1: extract ### Provider AE / ### Consumer AEs H3 subsections
    # nested inside §Parties. These are the canonical source per the post-DN→AE
    # migration IC template (vendored 2026-04-27); parties[].ae_id remains as a
    # legacy / redundant inline-text fallback.
    provider_ae, consumer_aes = _extract_party_ae_subsections(parties_body)
    if provider_ae:
        ir["provider_ae"] = provider_ae
    if consumer_aes:
        ir["consumer_aes"] = consumer_aes

    rel = _extract_relationship(ctx.sections.get("Relationship Pattern", ""), ctx)
    if rel:
        ir["relationship_pattern"] = rel

    conventions = _extract_bullets(ctx.sections.get("Shared Conventions", ""))
    if conventions:
        ir["shared_conventions"] = conventions

    constraints = _extract_table(
        ctx.sections.get("Domain Constraints", ""),
        ["constraint", "value", "rationale"],
    )
    if constraints:
        ir["domain_constraints"] = constraints

    errors = _extract_table(
        ctx.sections.get("Error Semantics", ""),
        ["condition", "producing_party", "detection", "behavior", "consumer_responsibility"],
    )
    if errors:
        ir["error_semantics"] = errors
        for i, row in enumerate(errors):
            if "behavior" not in row:
                ctx.warnings.append(
                    _Warn(
                        field=f"/error_semantics/{i}/behavior",
                        reason=f"Row '{row.get('condition', '?')[:60]}' has no behavior cell; contract_test emitter will skip it.",
                        severity="warning",
                    )
                )

    cg = _extract_consistency(ctx.sections.get("Consistency Guarantees", ""))
    if cg:
        ir["consistency_guarantees"] = cg

    issues = _extract_open_issues(ctx.sections.get("Open Issues", ""))
    if issues is not None:
        ir["open_issues"] = issues

    amendments = _extract_amendment_log(ctx.sections.get("Amendment Log", ""))
    if amendments:
        ir["amendment_log"] = amendments

    if ctx.warnings:
        ir["parse_warnings"] = [w.to_dict() for w in ctx.warnings]

    _validate(ir)
    return ir


# --------------------------------------------------------------------------- #
# Section splitter
# --------------------------------------------------------------------------- #


def _split_sections(text: str) -> dict[str, str]:
    """Split markdown text into a {h2_name: body} dict.

    H1 and H3+ are skipped at the top level; H3s remain inside their parent
    H2 body. The horizontal-rule separator (---) used in the IC template is
    also kept inside whichever section it appears in.
    """
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        h2_match = re.match(r"^##\s+(.+?)\s*$", line)
        if h2_match:
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip("\n")
            current_name = h2_match.group(1).strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip("\n")

    return sections


# --------------------------------------------------------------------------- #
# Field extractors
# --------------------------------------------------------------------------- #


def _extract_id(filename: str, ctx: _ParseContext) -> str:
    m = _IC_FILENAME.match(filename)
    if not m:
        if _draft_id_or_none(filename) is not None:
            raise DraftArtifactError(
                f"{filename} is a DRAFT artifact (IC-DRAFT-<slug>); allocate a "
                f"canonical ID with `dekspec id allocate` before parsing."
            )
        raise ICParseError(
            f"Filename does not match IC-NNN-*.md pattern: {filename}"
        )
    return m.group(1)


def _extract_name(text: str, ctx: _ParseContext) -> str:
    m = _H1_TITLE.search(text)
    if not m:
        raise ICParseError("Missing or malformed H1 — expected '# Interface Contract: <Name>'")
    return m.group(1).strip()


def _extract_status(ctx: _ParseContext) -> str:
    body = ctx.sections.get("Status", "")
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s in _VALID_STATUSES:
            return s
        # Strip common decorations
        token = s.split()[0].strip("`*_").upper()
        if token in _VALID_STATUSES:
            return token
    raise ICParseError(
        "Could not extract a valid Status (TODO|DRAFT|PROPOSED|ACCEPTED|LOCKED|DEPRECATED)"
    )


def _extract_version(ctx: _ParseContext) -> str:
    body = ctx.sections.get("Version", "")
    m = _SEMVER.search(body)
    if not m:
        raise ICParseError("Could not extract a semver Version (X.Y.Z)")
    return m.group(1)


def _extract_first_date(body: str) -> str | None:
    """Most-recent date wins. The Modified section may have multiple."""
    if not body:
        return None
    dates = sorted(set(_DATE.findall(body)), reverse=True)
    return dates[0] if dates else None


def _extract_domains(body: str) -> list[str]:
    out: list[str] = []
    for marker, label in _DOMAIN_LINE.findall(body):
        if marker.lower() != "x":
            continue
        # Strip trailing parens with details: "Numerical precision (...)"
        clean = re.split(r"\s*\(", label, maxsplit=1)[0].strip().lower()
        slug = _DOMAIN_SLUGS.get(clean)
        if slug and slug not in out:
            out.append(slug)
    return out


def _extract_governing_adrs(body: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in _ADR_LINE.finditer(body):
        entry: dict[str, str] = {"id": f"ADR-{m.group(1)}"}
        title = (m.group("title") or "").strip()
        summary = (m.group("summary") or "").strip()
        if title:
            entry["title"] = title
        if summary:
            entry["summary"] = summary
        out.append(entry)
    return out


def _extract_parties(body: str, ctx: _ParseContext) -> list[dict[str, Any]]:
    """Extract named parties from bullet lines like:
        - **Formula Engine** (provider) — evaluates ...
        - **Formula Consumers** (callers) — awareness scoring, placement, ...
    Role inferred from parenthesized hint, then from keyword scan of the description.

    Party-AE linkage is structured-only and lives in the
    `### Provider AE` / `### Consumer AEs` H3 subsections of §Parties
    (see _extract_party_ae_subsections). AE-NNN mentions in Party description
    prose are intentionally NOT lifted into parties[].ae_id — that conflicts
    with the structured-subsection schema and caused backlink-audit
    false-positives (ds-59l). Prose mentions are reference-style, not linkage.
    """
    out: list[dict[str, Any]] = []
    for m in _PARTY_BULLET.finditer(body):
        name = m.group("name").strip()
        hint = (m.group("hint") or "").strip()
        desc = m.group("desc").strip()
        role = _infer_role(hint, desc)
        entry: dict[str, Any] = {"role": role, "name": name, "description": desc}
        out.append(entry)

    if len(out) < 2:
        ctx.warnings.append(
            _Warn(
                field="/parties",
                reason=f"Extracted {len(out)} parties; schema requires at least 2 if present. Field omitted from IR.",
            )
        )
        return []
    return out


def _extract_party_ae_subsections(body: str) -> tuple[str | None, list[str]]:
    """Extract AE-NNN refs from ### Provider AE / ### Consumer AEs H3 subsections
    nested inside §Parties.

    Returns (provider_ae | None, consumer_aes_list). Each may be None / empty
    if the subsection doesn't exist or has no extractable AE-NNN.
    """
    if not body.strip():
        return None, []
    provider_ae: str | None = None
    consumer_aes: list[str] = []
    for header, block in _split_h3(body):
        h = header.strip().lower()
        if h == "provider ae":
            ids = _AE_ID.findall(block)
            if ids:
                provider_ae = ids[0]
        elif h in {"consumer aes", "consumer ae"}:
            for ae in _AE_ID.findall(block):
                if ae not in consumer_aes:
                    consumer_aes.append(ae)
    return provider_ae, consumer_aes


def _infer_role(hint: str, description: str) -> str:
    haystack = f"{hint} {description}".lower()
    for kw in _PROVIDER_KEYWORDS:
        if kw in haystack:
            return "provider"
    for kw in _CONSUMER_KEYWORDS:
        if kw in haystack:
            return "consumer"
    return "provider"


def _extract_relationship(body: str, ctx: _ParseContext) -> dict[str, Any] | None:
    if not body.strip():
        return None
    pat_match = _PATTERN_LINE.search(body)
    if not pat_match:
        ctx.warnings.append(
            _Warn(
                field="/relationship_pattern",
                reason="No '**Pattern:** <name>' line found.",
            )
        )
        return None
    raw = pat_match.group(1).strip().strip("*_`").lower()
    # Strip trailing notes after a separator
    raw = re.split(r"\s+\(", raw, maxsplit=1)[0].strip()
    slug = _PATTERN_SLUGS.get(raw)
    if not slug:
        ctx.warnings.append(
            _Warn(
                field="/relationship_pattern/pattern",
                reason=f"Pattern '{raw}' did not match known DDD patterns.",
            )
        )
        return None
    rel: dict[str, Any] = {"pattern": slug}
    impact_match = _CHANGE_IMPACT.search(body)
    if impact_match:
        # Trim at next blank line / next bold marker
        impact = impact_match.group(1).strip()
        impact = re.split(r"\n\n|\n\*\*", impact, maxsplit=1)[0].strip()
        if impact:
            rel["change_impact"] = impact
    return rel


def _extract_bullets(body: str) -> list[str]:
    return [b.strip() for b in _BULLET.findall(body) if b.strip()]


def _extract_table(body: str, columns: list[str]) -> list[dict[str, str]]:
    """Parse a markdown table; map cells to provided column keys by position.

    Skips header row, separator row, and any row that doesn't have at least
    as many cells as `columns` requires (truncates extra cells, pads short
    rows with empty strings — but rejects rows with no leading pipe).
    """
    rows: list[dict[str, str]] = []
    in_table = False
    seen_header = False

    for line in body.splitlines():
        s = line.rstrip()
        if not s.startswith("|"):
            if in_table:
                # Table block ended; reset for any subsequent table
                in_table = False
                seen_header = False
            continue
        in_table = True
        cells = [c.strip() for c in s.strip("|").split("|")]
        # Separator row: all cells are dashes / colons
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            seen_header = True
            continue
        if not seen_header:
            # Header row
            continue
        if not any(cells):
            continue
        # Pad/truncate cells to match columns
        while len(cells) < len(columns):
            cells.append("")
        cells = cells[: len(columns)]
        row = {col: cell for col, cell in zip(columns, cells) if cell}
        if row:
            rows.append(row)
    return rows


def _extract_consistency(body: str) -> dict[str, list[str]] | None:
    if not body.strip():
        return None
    cg: dict[str, list[str]] = {}
    holds_match = re.search(
        r"\*\*Holds:\*\*\s*\n(.+?)(?=\n\*\*|$)", body, re.DOTALL
    )
    if holds_match:
        cg["holds"] = _extract_bullets(holds_match.group(1))
    not_match = re.search(
        r"\*\*Does NOT hold:\*\*\s*\n(.+?)(?=\n\*\*|\Z)", body, re.DOTALL
    )
    if not_match:
        cg["does_not_hold"] = _extract_bullets(not_match.group(1))
    return cg or None


def _extract_open_issues(body: str) -> list[dict[str, str]] | None:
    """Returns [] if explicitly 'None.', list of parsed issues otherwise, or
    None if section is absent/empty.

    Severity tokens are normalized to canonical `P0..P3` via
    `_normalize_severity_alias` (IB-023 / ADR-013). Unknown severity
    strings raise `ParseError`; an absent `**Severity:**` token
    defaults to `non_blocking` (which the alias map maps to `P3`).
    The historical substring-heuristic fold (any string containing
    `block` but not `non` → `blocking`) is removed — the literal alias
    `"blocking"` continues to map to `P1` via the alias-map row.

    Resolved `[x]` rows are skipped (matching the long-standing
    behaviour of `_extract_open_issues_ws`). Open `[ ]` rows are
    included. Pre-IB-023 the IC/IB/ADR/Intent extractor returned
    both states, which the lenient substring-fold severity helper
    silently absorbed; with the strict alias map landing in IB-023,
    keeping resolved rows surfaces historical authoring quirks
    (e.g., `**Severity:** was blocking`) as ParseError and breaks
    audit linkage. Skipping `[x]` rows aligns the two extractors on
    the same predicate while still capturing every open concern.
    """
    text = body.strip()
    if not text:
        return None
    if text.lower().startswith("none"):
        return []
    out: list[dict[str, str]] = []
    for raw in _OPEN_ISSUE_BULLET_WITH_STATE.finditer(body):
        if raw.group("state").lower() == "x":
            continue
        raw_text = raw.group("text").strip()
        # Bind back to the original local name to keep the rest of
        # the extractor body identical to its pre-IB-023 shape.
        raw = raw_text
        # Heuristic split: "issue text — **Source:** ... — **Severity:** ..."
        # Char class widened from `[a-z\-_]+` to `[a-z0-9\-_]+` so the
        # canonical `P0..P3` tokens capture cleanly. Parentheticals
        # and spaces are NOT in the class — matching the historical
        # capture semantics for IC / IB / ADR / Intent (which never
        # historically accepted the `blocking (pre-code)` variant
        # spelling — that lives on the WS surface only). The WS-side
        # extractor `_extract_open_issues_ws` keeps the wider class.
        sev_match = re.search(r"\*\*Severity:\*\*\s*([a-z0-9\-_]+)", raw, re.IGNORECASE)
        src_match = re.search(r"\*\*Source:\*\*\s*([^—\n]+)", raw, re.IGNORECASE)
        text_only = re.split(r"\s+[—-]\s+\*\*Source:", raw, maxsplit=1)[0].strip()
        sev_raw = sev_match.group(1) if sev_match else "non_blocking"
        sev_norm = _normalize_severity_alias(sev_raw)
        entry: dict[str, str] = {"text": text_only, "severity": sev_norm}
        if src_match:
            entry["source"] = src_match.group(1).strip()
        out.append(entry)
    return out


_AMENDMENT_TYPES = {"editorial", "unlock", "substantive", "fill"}


def _extract_amendment_log(body: str) -> list[dict[str, str]]:
    rows = _extract_table(body, ["date", "type", "change", "author"])
    cleaned: list[dict[str, str]] = []
    for r in rows:
        if "date" not in r or "change" not in r:
            continue
        t = r.get("type", "").strip().lower()
        if t not in _AMENDMENT_TYPES:
            # Default to 'editorial' if unknown — schema enforces enum, but
            # historic logs may use freeform; degrade gracefully.
            t = "editorial"
        r["type"] = t
        cleaned.append(r)
    return cleaned


# --------------------------------------------------------------------------- #
# Interface Definition (polymorphic)
# --------------------------------------------------------------------------- #


def _extract_interface_definition(ctx: _ParseContext) -> dict[str, Any]:
    body = ctx.sections.get("Interface Definition", "")
    kind = _detect_kind(body)
    operations = _extract_operations(body, ctx)
    if not operations and body.strip() and not body.strip().lower().startswith("*todo"):
        ctx.warnings.append(
            _Warn(
                field="/interface_definition/operations",
                reason="No operation signatures detected in Interface Definition; raw_markdown preserved as fallback.",
            )
        )
    return {
        "kind": kind,
        "operations": operations,
        "raw_markdown": body,
    }


def _detect_kind(body: str) -> str:
    if not body.strip():
        return "other"
    lower = body.lower()
    http_signals = ("get /", "post /", "put /", "delete /", "patch /", "endpoint", "http", "status code")
    consistency_signals = ("warm phase", "write phase", "flush phase", "read phase", "ordering guarantee", "consistency")
    if any(sig in lower for sig in http_signals):
        return "http_api"
    if _SIGNATURE.search(body):
        return "in_process_adapter"
    if any(sig in lower for sig in consistency_signals):
        return "consistency_contract"
    return "other"


def _extract_operations(body: str, ctx: _ParseContext) -> list[dict[str, Any]]:
    """Detect H3 subsections that introduce a function-style signature.

    Looks for backtick-wrapped `name(args) -> ret` patterns near H3 boundaries.
    Inputs/Outputs tables that follow are attached to the operation. Section-
    level Preconditions (an ### Preconditions H3 not inside an op block) are
    attached to the single operation when exactly one is present.
    """
    operations: list[dict[str, Any]] = []
    section_preconditions = _extract_section_preconditions(body)
    blocks = _split_h3(body)
    for header, block in blocks:
        sig_match = _SIGNATURE.search(header) or _SIGNATURE.search(block)
        if not sig_match:
            continue
        name = sig_match.group(1)
        full_sig = sig_match.group(0).strip("`").strip()
        op: dict[str, Any] = {"name": name, "signature": full_sig}
        inputs = _extract_input_table(block)
        if inputs:
            op["inputs"] = [_clean_param_row(r) for r in inputs]
        outputs = _extract_output_table(block)
        if outputs:
            op["outputs"] = [_clean_param_row(r) for r in outputs]
        # Block-local preconditions (rare); fallback to section-level next.
        block_preconds = _extract_preconditions(block)
        if block_preconds:
            op["preconditions"] = block_preconds
        operations.append(op)

    # Section-level preconditions attach to the single operation if unambiguous.
    if section_preconditions and len(operations) == 1 and "preconditions" not in operations[0]:
        operations[0]["preconditions"] = section_preconditions
    elif section_preconditions and len(operations) > 1:
        ctx.warnings.append(
            _Warn(
                field="/interface_definition/operations/*/preconditions",
                reason="Section-level Preconditions found but multiple operations exist; cannot disambiguate which to attach to.",
            )
        )

    return operations


def _clean_param_row(row: dict[str, str]) -> dict[str, str]:
    """Strip backticks from name/type cells in input/output rows."""
    cleaned: dict[str, str] = {}
    for k, v in row.items():
        if k in {"name", "type"}:
            cleaned[k] = v.strip("`").strip()
        else:
            cleaned[k] = v
    return cleaned


def _extract_section_preconditions(body: str) -> list[str]:
    """Find a top-level '### Preconditions' inside the section body."""
    blocks = _split_h3(body)
    for header, block in blocks:
        if header.strip().lower() == "preconditions":
            return _extract_numbered_list(block)
    return []


def _extract_numbered_list(text: str) -> list[str]:
    out: list[str] = []
    for raw in re.findall(r"^\s*\d+\.\s*(.+?)$", text, re.MULTILINE):
        cleaned = re.sub(r"^\*\*([^*]+)\*\*\s*", r"\1 ", raw).strip()
        out.append(cleaned)
    return out


def _split_h3(body: str) -> list[tuple[str, str]]:
    """Split a body into [(h3_header_text, block_text), ...] pairs.

    The block before the first H3 is returned with header == "".
    """
    blocks: list[tuple[str, str]] = []
    current_header = ""
    current_lines: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            blocks.append((current_header, "\n".join(current_lines)))
            current_header = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    blocks.append((current_header, "\n".join(current_lines)))
    return blocks


def _extract_input_table(block: str) -> list[dict[str, str]]:
    # Look for an "**Input:**" marker followed by a table.
    m = re.search(r"\*\*Input:?\*\*\s*\n(.+?)(?=\n\*\*|\Z)", block, re.DOTALL)
    if not m:
        return []
    return _extract_table(m.group(1), ["name", "type", "description"])


def _extract_output_table(block: str) -> list[dict[str, str]]:
    m = re.search(r"\*\*Output:?\*\*\s*\n(.+?)(?=\n\*\*|\Z)", block, re.DOTALL)
    if not m:
        return []
    return _extract_table(m.group(1), ["name", "type", "description"])


def _extract_preconditions(block: str) -> list[str]:
    """Block-local preconditions: nested **Preconditions** marker inside an operation block."""
    m = re.search(
        r"\*\*Preconditions:?\*\*\s*\n(.+?)(?=\n\*\*|\Z)",
        block,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return []
    return _extract_numbered_list(m.group(1))


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #


def _load_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("interface_contract")


def _validate(ir: dict[str, Any]) -> None:
    schema = _load_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise ICParseError(
            "Parsed IR failed schema validation:\n" + "\n".join(msgs)
        )


# --------------------------------------------------------------------------- #
# Misc helpers
# --------------------------------------------------------------------------- #


def _maybe_set(d: dict[str, Any], key: str, value: Any) -> None:
    if value is not None and value != "" and value != []:
        d[key] = value


# =========================================================================== #
# Architecture Element parser (v0.2)
# =========================================================================== #

_AE_FILENAME = re.compile(r"^(AE-\d{3,})-.+\.md$")
_AE_H1_TITLE = re.compile(r"^#\s+(?:AE-\d{3,}|Architecture Element):\s*(.+?)\s*$", re.MULTILINE)
_FORMER_DN = re.compile(r"\b(DN-\d{3,})\b")

_AE_VALID_STATUSES = {"TODO", "DRAFT", "PROPOSED", "ACCEPTED", "LOCKED", "DEPRECATED"}
_AE_VALID_CLASSIFICATIONS = {"Core", "Supporting", "Generic"}

_AE_SUBTYPE_SLUGS = {
    "system": "system",
    "subsystem": "subsystem",
    "container": "container",
    "component": "component",
    "pipeline": "pipeline",
    "data model": "data_model",
    "cross-cutting concern": "cross_cutting_concern",
    "cross cutting concern": "cross_cutting_concern",
    "platform concern": "platform_concern",
    "interface surface": "interface_surface",
    "workflow / process": "workflow_process",
    "workflow/process": "workflow_process",
    "workflow process": "workflow_process",
}

_LINKED_ARTIFACT_BULLET = re.compile(
    r"^[-*]\s*\*\*Related\s+(?P<kind>ADRs?|WSs?|ICs?|IBs?|AEs?|INTs?|Intents?|Owners?):\*\*\s*(?P<value>.+?)$",
    re.MULTILINE | re.IGNORECASE,
)
_NON_GOAL_BULLET = re.compile(
    r"^[-*]\s*\*\*(?P<text>[^*]+?)\.?\*\*\s*(?P<why>.+?)$",
    re.MULTILINE,
)
# Em-dash separator form: `- Not X — reason` (per the AE template + the T11
# audit message). The text + why are split on the first ` — ` occurrence.
# Authored 2026-05-17 (ds-pto) — previously the parser only matched the
# `**name.** prose` form, so the template's em-dash form silently dropped
# the `why` field and every template-following AE failed T11.
_NON_GOAL_BULLET_DASH = re.compile(
    r"^[-*]\s+(?!\*\*)(?P<text>[^—\n]+?)\s+—\s+(?P<why>.+?)$",
    re.MULTILINE,
)
_AMENDMENT_TYPES_AE = {"editorial", "unlock", "substantive", "fill", "migration", "lock"}


class AEParseError(Exception):
    """Raised when an AE's parsed IR fails schema validation."""


def parse_ae(path: str | Path) -> dict[str, Any]:
    """Parse an Architecture Element markdown file into a validated IR dict.

    Mirrors parse() (the IC parser) — lossy by design, missing fields populate
    parse_warnings, schema validation runs after extraction.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    ctx = _ParseContext(src=src, text=text, sections=_split_sections(text))

    ir: dict[str, Any] = {
        "ir_schema_version": _AE_IR_SCHEMA_VERSION,
        "id": _extract_ae_id(src.name),
        "name": _extract_ae_name(text),
        "status": _extract_ae_status(ctx),
        "subtype": _extract_ae_subtype(ctx),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    classification = _extract_ae_classification(ctx)
    if classification:
        ir["classification"] = classification

    _maybe_set(ir, "created", _extract_first_date(ctx.sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(ctx.sections.get("Modified", "")))

    former = _extract_former_dn(ctx.sections.get("Former DN", ""))
    if former:
        ir["former_dn"] = former

    linked = _extract_linked_artifacts(ctx.sections.get("Linked Artifacts", ""))
    if linked:
        ir["linked_artifacts"] = linked

    implements = _extract_implements(ctx.sections.get("Implements", ""))
    if implements:
        ir["implements_globs"] = implements

    purpose = ctx.sections.get("Purpose and Scope", "").strip()
    if purpose:
        ir["purpose_and_scope"] = purpose

    responsibilities = _extract_bullets(ctx.sections.get("Responsibilities", ""))
    if responsibilities:
        ir["responsibilities"] = [_strip_bold_lead(r) for r in responsibilities]

    bng = _extract_boundaries(ctx.sections.get("Boundaries and Non-Goals", ""))
    if bng:
        ir["boundaries_and_non_goals"] = bng

    boundaries = _extract_three_tier_boundaries(
        ctx.sections.get("Three-tier Boundaries", "")
    )
    if boundaries:
        ir["boundaries"] = boundaries

    rels = _extract_relationships(ctx.sections.get("Relationships and Dependencies", ""))
    if rels:
        ir["relationships_and_dependencies"] = rels

    views = _extract_views(ctx.sections.get("Views", ""))
    if views:
        ir["views"] = views

    for section, key in [
        ("Runtime Behavior", "runtime_behavior"),
        ("Data and State", "data_and_state"),
        ("Deployment / Operational Shape", "deployment_operational_shape"),
        ("Constraints and Quality Notes", "constraints_and_quality_notes"),
    ]:
        body = ctx.sections.get(section, "").strip()
        if body:
            ir[key] = body

    open_qs = _extract_ae_open_questions(ctx.sections.get("Open Questions / Planned Follow-ons", ""))
    if open_qs:
        ir["open_questions"] = open_qs

    amendments = _extract_ae_amendment_log(ctx.sections.get("Amendment Log", ""))
    if amendments:
        ir["amendment_log"] = amendments

    # Legacy DN-era sections (preserved for migrated AEs)
    wsll = _extract_bullets(ctx.sections.get("What Success Looks Like", ""))
    if wsll:
        ir["what_success_looks_like"] = wsll
    key_concepts = ctx.sections.get("Key Concepts", "").strip()
    if key_concepts:
        ir["key_concepts"] = key_concepts

    if ctx.warnings:
        ir["parse_warnings"] = [w.to_dict() for w in ctx.warnings]

    _validate_ae(ir)
    return ir


# --------------------------------------------------------------------------- #
# AE field extractors
# --------------------------------------------------------------------------- #


def _extract_ae_id(filename: str) -> str:
    m = _AE_FILENAME.match(filename)
    if not m:
        if _draft_id_or_none(filename) is not None:
            raise DraftArtifactError(
                f"{filename} is a DRAFT artifact (AE-DRAFT-<slug>); allocate a "
                f"canonical ID with `dekspec id allocate` before parsing."
            )
        raise AEParseError(f"Filename does not match AE-NNN-*.md pattern: {filename}")
    return m.group(1)


def _extract_ae_name(text: str) -> str:
    m = _AE_H1_TITLE.search(text)
    if not m:
        raise AEParseError("Missing or malformed H1 — expected '# AE-NNN: <Name>'")
    return m.group(1).strip()


def _extract_ae_status(ctx: _ParseContext) -> str:
    body = ctx.sections.get("Status", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        token = s.split()[0].strip("`*_").upper()
        if token in _AE_VALID_STATUSES:
            return token
    raise AEParseError(
        "Could not extract a valid Status (TODO|DRAFT|PROPOSED|ACCEPTED|LOCKED|DEPRECATED)"
    )


def _extract_ae_subtype(ctx: _ParseContext) -> str:
    body = ctx.sections.get("Subtype", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*") or s.startswith("["):
            continue
        slug = _AE_SUBTYPE_SLUGS.get(s.lower())
        if slug:
            return slug
        ctx.warnings.append(
            _Warn(
                field="/subtype",
                reason=f"Subtype value '{s}' not in C4 enum; falling back to 'component'.",
            )
        )
        return "component"
    raise AEParseError("Could not extract Subtype value")


def _extract_ae_classification(ctx: _ParseContext) -> str | None:
    body = ctx.sections.get("Classification", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*") or s.startswith("["):
            continue
        token = s.split()[0].strip("`*_")
        if token in _AE_VALID_CLASSIFICATIONS:
            return token
    return None


def _extract_former_dn(body: str) -> str | None:
    if not body.strip():
        return None
    m = _FORMER_DN.search(body)
    return m.group(1) if m else None


def _extract_linked_artifacts(body: str) -> dict[str, list[str]]:
    """Project the §Linked Artifacts section into the IR.

    IB-044 (INT-034 / ADR-015): the stored `related_*s` backlink projections
    (`related_adrs` / `related_wss` / `related_ics` / `related_ibs` /
    `related_aes` / `related_intents`) are retired. Backlinks are derived
    from the union of forward links and rendered by `dekspec relink` — they
    are no longer schema-validated input. The `Related *` lines remain in
    artifact markdown as `dekspec relink` output; this parser simply does
    NOT project them into the IR (no warning, no failure — they are
    legitimate tool-emitted display lines). Only `owners` — author-maintained
    ownership metadata, not a backlink — is still projected.
    """
    out: dict[str, list[str]] = {}
    # Map kind labels (singular OR plural form) to canonical singular keys.
    # rstrip("S") was wrong because "WS" → "W" (strips ALL trailing S).
    # Only OWNER is retained; the `related_*s` backlink kinds were retired
    # at IB-044. Non-OWNER `Related *` lines are ignored, not projected.
    kind_normalize = {
        "OWNER": "OWNER", "OWNERS": "OWNER",
    }
    for m in _LINKED_ARTIFACT_BULLET.finditer(body):
        kind_raw = kind_normalize.get(m.group("kind").upper())
        if kind_raw is None:
            # `Related ADRs/WSs/ICs/IBs/AEs/Intents` lines are now
            # `dekspec relink` output — legitimate markdown, simply not
            # projected into the IR. Skip without warning or failure.
            continue
        value = m.group("value").strip()
        if kind_raw == "OWNER":
            owners = [v.strip() for v in re.split(r"[,;]", value) if v.strip() and v.strip().lower() != "none"]
            if owners:
                out.setdefault("owners", []).extend(owners)
            continue
    # Dedupe + preserve order
    return {k: list(dict.fromkeys(v)) for k, v in out.items()}


def _extract_implements(body: str) -> list[str]:
    """Parse the new ## Implements section's path globs."""
    if not body.strip():
        return []
    paths: list[str] = []
    for raw in _BULLET.findall(body):
        cleaned = raw.strip().strip("`")
        if not cleaned or cleaned.lower() in {"none", "n/a"}:
            continue
        paths.append(cleaned)
    return paths


def _extract_boundaries(body: str) -> dict[str, Any] | None:
    if not body.strip():
        return None
    out: dict[str, Any] = {}
    inside_match = re.search(
        r"\*\*Inside the boundary:\*\*\s*\n(.+?)(?=\n\*\*|\Z)", body, re.DOTALL
    )
    if inside_match:
        inside = [_strip_bold_lead(b) for b in _extract_bullets(inside_match.group(1))]
        if inside:
            out["inside"] = inside
    non_goals_match = re.search(
        r"\*\*Outside the boundary[^*]*\*\*\s*\n(.+?)(?=\n##|\Z)", body, re.DOTALL
    )
    if non_goals_match:
        section = non_goals_match.group(1)
        non_goals: list[dict[str, str]] = []
        # First pass: bold-led form `- **Name.** prose.` (canonical for many
        # AEs in the corpus + the only form supported pre-ds-pto).
        bold_spans: list[tuple[int, int]] = []
        for m in _NON_GOAL_BULLET.finditer(section):
            entry: dict[str, str] = {"text": m.group("text").strip()}
            why = m.group("why").strip()
            if why:
                entry["why"] = why
            non_goals.append(entry)
            bold_spans.append(m.span())
        # Second pass: em-dash separator form `- Not X — reason` (per the AE
        # template + the T11 audit message — ds-pto 2026-05-17). Skip
        # bullets already captured by the bold pass to avoid double-counting
        # if a line somehow matches both shapes.
        for m in _NON_GOAL_BULLET_DASH.finditer(section):
            if any(start <= m.start() < end for start, end in bold_spans):
                continue
            entry = {"text": m.group("text").strip()}
            why = m.group("why").strip()
            if why:
                entry["why"] = why
            non_goals.append(entry)
        # Fallback for non-goals authored as plain bullets matching neither
        # bold-led nor em-dash form.
        if not non_goals:
            for raw in _extract_bullets(section):
                non_goals.append({"text": raw})
        if non_goals:
            out["non_goals"] = non_goals
    return out or None


def _extract_three_tier_boundaries(body: str) -> dict[str, Any] | None:
    """Extract the `## Three-tier Boundaries` section into a typed block.

    Parses three labelled bullet sub-lists — `**Always do:**`,
    `**Ask first:**`, `**Never do:**` — into the `always_do` / `ask_first`
    / `never_do` clause lists (ADR-014 / MSN-008). Returns None when the
    section is empty or every tier is empty — the field is optional.
    """
    if not body.strip():
        return None
    out: dict[str, Any] = {}
    for label, key in (
        ("Always do", "always_do"),
        ("Ask first", "ask_first"),
        ("Never do", "never_do"),
    ):
        m = re.search(
            rf"\*\*{label}:\*\*\s*\n(.+?)(?=\n\*\*|\Z)", body, re.DOTALL
        )
        if m:
            clauses = [_strip_bold_lead(b) for b in _extract_bullets(m.group(1))]
            if clauses:
                out[key] = clauses
    return out or None


def _extract_relationships(body: str) -> dict[str, Any] | None:
    if not body.strip():
        return None
    out: dict[str, Any] = {}
    for label, key in [
        ("Consumes", "consumes"),
        ("Produces", "produces"),
        ("Depends on", "depends_on"),
        ("Consumed by", "consumed_by"),
    ]:
        m = re.search(
            rf"\*\*{re.escape(label)}:\*\*\s*(.+?)(?=\n\*\*|\Z)",
            body,
            re.DOTALL,
        )
        if not m:
            continue
        prose = m.group(1).strip()
        # Each direction is typically a paragraph or bullet list. Capture verbatim
        # as a single-element list for now; structured parsing is a v0.3 polish.
        if prose and prose.lower() not in {"none", "n/a"}:
            out[key] = [prose]
    indirect_match = re.search(
        r"\*\*Indirect governing ADRs:\*\*\s*\n(.+?)(?=\n##|\Z)", body, re.DOTALL
    )
    if indirect_match:
        indirect: list[dict[str, str]] = []
        for raw in _extract_bullets(indirect_match.group(1)):
            adr_match = re.match(r"(ADR-\d{3,})\s*[—\-:]\s*(.+)", raw)
            if adr_match:
                indirect.append({"id": adr_match.group(1), "rationale": adr_match.group(2).strip()})
        if indirect:
            out["indirect_governing_adrs"] = indirect
    return out or None


_VIEW_KIND_PATTERN = re.compile(
    r"^\s*(context|container|component|dynamic|deployment)\b"
    r"\s*(?:view|diagram)?\s*(?:[—\-:]\s*(.+))?$",
    re.IGNORECASE,
)
_FENCED_BLOCK_PATTERN = re.compile(
    r"```([A-Za-z0-9_+\-]*)\n(.*?)```", re.DOTALL
)
# A bold inline view-kind lead-in on its own line, e.g. ``**Deployment view.**``
# or ``**Deployment view —**``. The bold text matches the same view-kind
# vocabulary as the H3 path; a trailing description after — / - / : is captured.
_VIEW_BOLD_LEAD_PATTERN = re.compile(
    r"(?m)^\s*\*\*\s*(context|container|component|dynamic|deployment)\b"
    r"\s*(?:view|diagram)?\s*\.?\s*(?:[—\-:]\s*([^*]+?))?\s*\*\*\s*$",
    re.IGNORECASE,
)


def _extract_views(body: str) -> dict[str, Any] | None:
    if not body.strip():
        return None
    out: dict[str, Any] = {}

    # Absence justification: italic-wrapped paragraph saying no view authored
    if re.search(r"\*[^*]*no\s+(?:architectural\s+)?view\s+(?:diagram\s+)?(?:is|authored)[^*]*\*", body, re.IGNORECASE | re.DOTALL):
        m = re.search(r"\*([^*]+)\*", body, re.DOTALL)
        if m:
            out["absence_justification"] = m.group(1).strip()

    # H3 view-kind headings + fenced source blocks
    diagrams: list[dict[str, str]] = []
    # Track which fenced blocks an H3 segment has already claimed, so the
    # bold-lead-in pass below does not register the same diagram twice.
    h3_consumed_spans: list[tuple[int, int]] = []
    segments = re.split(r"(?m)^###\s+", body)
    for seg in segments[1:]:  # segments[0] is the prelude before the first H3
        title_line, _, seg_body = seg.partition("\n")
        kind_match = _VIEW_KIND_PATTERN.match(title_line.strip())
        if not kind_match:
            continue
        entry: dict[str, str] = {"kind": kind_match.group(1).lower()}
        title_remainder = (kind_match.group(2) or "").strip()
        if title_remainder:
            entry["description"] = title_remainder
        fence_match = _FENCED_BLOCK_PATTERN.search(seg_body)
        if fence_match:
            inline = fence_match.group(2).strip()
            if inline:
                entry["inline"] = inline
            seg_start = body.find(seg_body)
            if seg_start != -1:
                h3_consumed_spans.append(
                    (seg_start + fence_match.start(), seg_start + fence_match.end())
                )
        diagrams.append(entry)

    # Bold inline view-kind lead-in (e.g. ``**Deployment view.**``) followed by a
    # fenced source block. This is an *additional* path: the H3 form above stays
    # authoritative, and a fence already claimed by an H3 segment is skipped.
    for lead in _VIEW_BOLD_LEAD_PATTERN.finditer(body):
        fence_match = _FENCED_BLOCK_PATTERN.search(body, lead.end())
        if not fence_match:
            continue
        if any(s <= fence_match.start() < e for s, e in h3_consumed_spans):
            continue
        entry = {"kind": lead.group(1).lower()}
        lead_remainder = (lead.group(2) or "").strip()
        if lead_remainder:
            entry["description"] = lead_remainder
        inline = fence_match.group(2).strip()
        if inline:
            entry["inline"] = inline
        diagrams.append(entry)

    if diagrams:
        out["diagrams"] = diagrams

    return out or None


def _extract_ae_open_questions(body: str) -> list[dict[str, str]]:
    if not body.strip():
        return []
    out: list[dict[str, str]] = []
    for raw in _OPEN_ISSUE_BULLET.findall(body):
        raw = raw.strip()
        sev_match = re.search(r"\*\*Severity:\*\*\s*([a-z\-_]+)", raw, re.IGNORECASE)
        src_match = re.search(r"\*\*Source:\*\*\s*([^—\n]+)", raw, re.IGNORECASE)
        text_only = re.split(r"\s+[—-]\s+\*\*Source:", raw, maxsplit=1)[0].strip()
        sev = (sev_match.group(1).strip().lower() if sev_match else "non_blocking")
        sev_norm = "blocking" if "block" in sev and "non" not in sev else "non_blocking"
        entry: dict[str, str] = {"text": text_only, "severity": sev_norm}
        if src_match:
            entry["source"] = src_match.group(1).strip()
        out.append(entry)
    return out


def _extract_ae_amendment_log(body: str) -> list[dict[str, str]]:
    rows = _extract_table(body, ["date", "type", "change", "author"])
    cleaned: list[dict[str, str]] = []
    for r in rows:
        if "date" not in r or "change" not in r:
            continue
        t = r.get("type", "").strip().lower()
        if t not in _AMENDMENT_TYPES_AE:
            t = "editorial"
        r["type"] = t
        cleaned.append(r)
    return cleaned


def _strip_bold_lead(text: str) -> str:
    """Strip leading **bold lead-in.** from a bullet text."""
    return re.sub(r"^\*\*([^*]+)\*\*\s*", r"\1 ", text).strip()


# --------------------------------------------------------------------------- #
# AE schema validation
# --------------------------------------------------------------------------- #


def _load_ae_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("architecture_element")


def _validate_ae(ir: dict[str, Any]) -> None:
    schema = _load_ae_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise AEParseError("Parsed AE IR failed schema validation:\n" + "\n".join(msgs))


# =========================================================================== #
# Cross-artifact resolution — IC -> AE -> implements_globs -> affected_paths
# =========================================================================== #


def resolve_aes(
    ir: dict[str, Any],
    ae_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Populate IC/WS IR's affected_paths from referenced AEs' implements_globs.

    Source of AE references depends on the IR shape:
      - IC IR: ic_ir.parties[].ae_id (typically Provider AE / Consumer AEs)
      - WS IR: ws_ir.related_architecture_elements[].id

    For each AE-NNN id, parse the corresponding AE-NNN-*.md from ae_dir (or
    the conventional sibling location) and union its implements_globs into
    ir.affected_paths.

    If ae_dir is None, infer it: the source typically lives at
    .../dekspec/{interface-contracts,working-specs}/<id>-*.md, and AEs at
    .../dekspec/architecture-elements/AE-NNN-*.md. Falls back gracefully
    (no-op + parse_warning) when the AE dir or specific AE files don't exist.

    Returns the IR (mutated in place + returned for convenience).
    """
    referenced_ae_ids: list[str] = []
    # IC top-level fields (canonical source post-v0.3.1)
    if ir.get("provider_ae"):
        referenced_ae_ids.append(ir["provider_ae"])
    referenced_ae_ids.extend(ir.get("consumer_aes", []))
    # IC legacy: parties[].ae_id (inline-in-description matches)
    for p in ir.get("parties", []):
        if "ae_id" in p:
            referenced_ae_ids.append(p["ae_id"])
    # WS source: related_architecture_elements[].id
    for r in ir.get("related_architecture_elements", []):
        if "id" in r:
            referenced_ae_ids.append(r["id"])
    # Dedupe preserving order
    referenced_ae_ids = list(dict.fromkeys(referenced_ae_ids))

    if not referenced_ae_ids:
        return ir
    # Rename for clarity in the rest of the function (was party_ae_ids in v0.2.1)
    ic_ir = ir
    party_ae_ids = referenced_ae_ids

    if ae_dir is None:
        ae_dir = _infer_ae_dir(ic_ir)
    ae_dir_path = Path(ae_dir) if ae_dir else None

    if ae_dir_path is None or not ae_dir_path.exists():
        ic_ir.setdefault("parse_warnings", []).append({
            "field": "/affected_paths",
            "reason": (
                f"AE registry directory not found (looked at {ae_dir_path}); "
                f"affected_paths not auto-derived. Use --affected-paths or "
                f"create architecture-elements/ alongside the IC."
            ),
            "severity": "info",
        })
        return ic_ir

    derived_paths: list[str] = list(ic_ir.get("affected_paths", []))
    for ae_id in party_ae_ids:
        matches = sorted(ae_dir_path.glob(f"{ae_id}-*.md"))
        if not matches:
            ic_ir.setdefault("parse_warnings", []).append({
                "field": f"/affected_paths (resolution of {ae_id})",
                "reason": f"AE file {ae_id}-*.md not found under {ae_dir_path}.",
                "severity": "warning",
            })
            continue
        try:
            ae_ir = parse_ae(matches[0])
        except AEParseError as e:
            ic_ir.setdefault("parse_warnings", []).append({
                "field": f"/affected_paths (resolution of {ae_id})",
                "reason": f"AE parse failed: {e}",
                "severity": "warning",
            })
            continue
        ae_globs = ae_ir.get("implements_globs", [])
        added = [g for g in ae_globs if g not in derived_paths]
        derived_paths.extend(added)
        if not ae_globs:
            ic_ir.setdefault("parse_warnings", []).append({
                "field": f"/affected_paths (resolution of {ae_id})",
                "reason": (
                    f"AE {ae_id} has no implements_globs; CI gate cannot scope "
                    f"from this AE. Author the ## Implements section in "
                    f"{matches[0].name}."
                ),
                "severity": "warning",
            })

    if derived_paths:
        ic_ir["affected_paths"] = derived_paths
    return ic_ir


def _infer_ae_dir(ic_or_ws_ir: dict[str, Any]) -> Path | None:
    """Infer the architecture-elements/ dir from an IC or WS source path.

    Convention: IC at .../interface-contracts/IC-NNN-*.md or WS at
    .../working-specs/WS-NNN-*.md → AEs at .../architecture-elements/.
    Returns None if the convention doesn't apply.
    """
    src = ic_or_ws_ir.get("source", {}).get("path")
    if not src:
        return None
    src_path = Path(src)
    parent = src_path.parent
    if parent.name not in {"interface-contracts", "working-specs"}:
        return None
    return parent.parent / "architecture-elements"


# =========================================================================== #
# Working Spec parser (v0.3-dev)
# =========================================================================== #

_WS_FILENAME = re.compile(r"^(WS-\d{3,})-.+\.md$")
_WS_H1_TITLE = re.compile(r"^#\s+Working Spec:\s*(.+?)\s*$", re.MULTILINE)
_WS_VALID_STATUSES = _AE_VALID_STATUSES  # same enum
_MECHANISM_LINE = re.compile(r"\*\*Mechanism:\*\*\s*(.+?)(?=\n\n|\Z)", re.DOTALL)
_AE_REF_BULLET = re.compile(
    r"^(?:[-*]\s*)?"
    r"(?:\[)?(?:\*\*)?"
    r"(AE-\d{3,})"
    r"(?:[ \t]+(?P<title>[^*\n\]]+?))?"
    r"(?:\*\*)?"
    r"(?:\]\([^)]*\))?"
    r"\s*(?P<sep>[:\-—])\s*(?P<rest>.+?)\s*$",
    re.MULTILINE,
)
_IC_REF_BULLET = re.compile(
    r"^(?:[-*]\s*)?(?:\*\*)?(IC-\d{3,})(?:\*\*)?\s*[:\-—]\s*(?P<rest>.+?)$",
    re.MULTILINE,
)
_OPEN_ISSUE_TASK = re.compile(
    r"^[-*]\s*\[(?P<state>[ x])\]\s*(?P<text>.+?)$",
    re.MULTILINE | re.IGNORECASE,
)
_BUSINESS_RULE_LINE = re.compile(
    r"^\s*(?P<num>\d+)\.\s*(?:\*\*(?P<domain>[^*]+?)\*\*\s*)?(?P<rule>.+?)$",
    re.MULTILINE,
)
_DOMAIN_EXCLUSION = re.compile(
    r"^[-*]\s*\*\*(?P<domain>[^*:]+?):\*\*\s*(?P<text>.+?)$",
    re.MULTILINE,
)


class WSParseError(Exception):
    """Raised when a WS's parsed IR fails schema validation."""


def parse_ws(path: str | Path) -> dict[str, Any]:
    """Parse a Working Spec markdown file into a validated IR dict.

    Mirrors parse() (IC) and parse_ae() — lossy by design, missing fields
    populate parse_warnings, schema validation runs after extraction.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    ctx = _ParseContext(src=src, text=text, sections=_split_sections(text))

    ir: dict[str, Any] = {
        # WS IR bumped 0.1.0 → 0.2.0 at IB-023 (severity vocabulary
        # unification — see ADR-013); `open_issues[*].severity` is
        # now canonical `P0..P3` rather than legacy
        # `{blocking_pre_ib, blocking_pre_code, non_blocking}`.
        "ir_schema_version": _WS_IR_SCHEMA_VERSION,
        "id": _extract_ws_id(src.name),
        "name": _extract_ws_name(text),
        "status": _extract_ws_status(ctx),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    _maybe_set(ir, "created", _extract_first_date(ctx.sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(ctx.sections.get("Modified", "")))

    # Reuse IC's silent-failure-domain extractor (same checkbox shape)
    domains = _extract_domains(ctx.sections.get("Silent Failure Domain(s)", ""))
    if domains:
        ir["silent_failure_domains"] = domains

    expertise = _extract_expertise_audit(ctx.sections.get("Expertise Audit Record", ""))
    if expertise:
        ir["expertise_audit"] = expertise

    related_aes = _extract_related_aes_ws(ctx.sections.get("Related Architecture Elements", ""))
    if related_aes:
        ir["related_architecture_elements"] = related_aes

    # Reuse IC's governing-ADR extractor
    adrs = _extract_governing_adrs(ctx.sections.get("Governing ADRs", ""))
    if adrs:
        ir["governing_adrs"] = adrs

    ics = _extract_ws_interface_contracts(ctx.sections.get("Interface Contracts", ""))
    if ics:
        ir["interface_contracts"] = ics

    wtd = _extract_what_this_does(ctx.sections.get("What This Does", ""))
    if wtd:
        ir["what_this_does"] = wtd

    wtdnd = _extract_what_this_does_not_do(ctx.sections.get("What This Does NOT Do", ""))
    if wtdnd:
        ir["what_this_does_not_do"] = wtdnd

    interfaces = _extract_ws_interfaces(ctx.sections.get("Interfaces", ""))
    if interfaces:
        ir["interfaces"] = interfaces

    constraints = _extract_table(
        ctx.sections.get("Domain Constraints", ""),
        ["constraint", "value", "scope", "rationale"],
    )
    if constraints:
        ir["domain_constraints"] = constraints

    formulas = _extract_table(
        ctx.sections.get("Governing Formulas", ""),
        ["formula", "expression", "variables", "units_or_scale", "valid_range", "validated_by"],
    )
    if formulas:
        ir["governing_formulas"] = formulas

    rules = _extract_business_rules(ctx.sections.get("Business Rules", ""))
    if rules:
        ir["business_rules"] = rules

    failures = _extract_table(
        ctx.sections.get("Failure Behavior", ""),
        ["failure", "detection", "assertion_type", "behavior", "recovery"],
    )
    if failures:
        ir["failure_behavior"] = failures

    issues = _extract_open_issues_ws(ctx.sections.get("Open Issues", ""))
    if issues is not None:
        ir["open_issues"] = issues

    contracts = _extract_ws_contracts(ctx.sections)
    if contracts:
        ir["contracts"] = contracts

    refactor_targets = _extract_table(
        ctx.sections.get("Refactor Targets", ""),
        ["file_or_module", "scope_defining_change", "behavioral_invariant_br"],
    )
    if refactor_targets:
        ir["refactor_targets"] = refactor_targets
        ir["role"] = "refactoring-ws"

    eval_hooks = _extract_bullets(ctx.sections.get("Eval Hooks", ""))
    if eval_hooks:
        ir["eval_hooks"] = eval_hooks

    amendments = _extract_ae_amendment_log(ctx.sections.get("Amendment Log", ""))
    if amendments:
        ir["amendment_log"] = amendments

    if ctx.warnings:
        ir["parse_warnings"] = [w.to_dict() for w in ctx.warnings]

    _validate_ws(ir)
    return ir


# --------------------------------------------------------------------------- #
# WS field extractors
# --------------------------------------------------------------------------- #


def _extract_ws_id(filename: str) -> str:
    m = _WS_FILENAME.match(filename)
    if not m:
        if _draft_id_or_none(filename) is not None:
            raise DraftArtifactError(
                f"{filename} is a DRAFT artifact (WS-DRAFT-<slug>); allocate a "
                f"canonical ID with `dekspec id allocate` before parsing."
            )
        raise WSParseError(f"Filename does not match WS-NNN-*.md pattern: {filename}")
    return m.group(1)


def _extract_ws_name(text: str) -> str:
    m = _WS_H1_TITLE.search(text)
    if not m:
        raise WSParseError("Missing or malformed H1 — expected '# Working Spec: <Name>'")
    return m.group(1).strip()


def _extract_ws_status(ctx: _ParseContext) -> str:
    body = ctx.sections.get("Status", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        token = s.split()[0].strip("`*_").upper()
        if token in _WS_VALID_STATUSES:
            return token
    raise WSParseError(
        "Could not extract a valid Status (TODO|DRAFT|PROPOSED|ACCEPTED|LOCKED|DEPRECATED)"
    )


def _extract_expertise_audit(body: str) -> list[dict[str, str]]:
    rows = _extract_table(body, ["role", "triggered", "trigger_rule", "rationale"])
    # Normalize the triggered column to lowercase enum values
    for row in rows:
        if "triggered" in row:
            t = row["triggered"].strip().lower()
            if t in {"yes", "no"}:
                row["triggered"] = t
            elif "n/a" in t or "n.a" in t or t == "":
                row["triggered"] = "n/a"
            else:
                row["triggered"] = "n/a"
    return rows


def _extract_related_aes_ws(body: str) -> list[dict[str, str]]:
    """Extract AE references from a Related Architecture Elements section.

    Handles four line formats:
      - 'AE-NNN: Title — desc'                (plain, unbulleted)
      - '- AE-NNN: Title — desc'              (bulleted with colon)
      - '- [AE-NNN](path) — desc'             (markdown link form)
      - '- **AE-NNN Title** — desc'           (bold-wrapped, no colon — ds-og8)
    """
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in _AE_REF_BULLET.finditer(body):
        ae_id = m.group(1)
        if ae_id in seen:
            continue
        seen.add(ae_id)
        rest = (m.group("rest") or "").strip()
        # If rest contains ' — ', split into title + description; else single field.
        if " — " in rest:
            _, _, description = rest.partition(" — ")
            description = description.strip()
        else:
            description = rest
        entry: dict[str, str] = {"id": ae_id}
        if description:
            entry["description"] = description
        out.append(entry)
    return out


def _extract_ws_interface_contracts(body: str) -> dict[str, list[dict[str, str]]]:
    """Parse §Interface Contracts. Two possible shapes:
      - **Consumed contracts:** IC-001, IC-002 / **Defined contracts:** IC-003
      - simple bullets: - IC-007: short name — description
    Best-effort: extract both forms.
    """
    out: dict[str, list[dict[str, str]]] = {}
    consumed_match = re.search(
        r"\*\*Consumed contracts?:\*\*\s*(.+?)(?=\n\*\*|\Z)", body, re.DOTALL
    )
    defined_match = re.search(
        r"\*\*Defined contracts?:\*\*\s*(.+?)(?=\n\*\*|\Z)", body, re.DOTALL
    )
    if consumed_match:
        out["consumed"] = _parse_ic_refs(consumed_match.group(1))
    if defined_match:
        out["defined"] = _parse_ic_refs(defined_match.group(1))
    if not out:
        # Fallback: simple bullets like "- IC-007: short name — description"
        bullets: list[dict[str, str]] = []
        for m in _IC_REF_BULLET.finditer(body):
            bullets.append({"id": m.group(1), "short_name": m.group("rest").strip()})
        if bullets:
            out["consumed"] = bullets
    return out


def _parse_ic_refs(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in re.finditer(r"\b(IC-\d{3,})(?:\s*\(([^)]+)\))?", text):
        entry: dict[str, str] = {"id": m.group(1)}
        if m.group(2):
            entry["short_name"] = m.group(2).strip()
        out.append(entry)
    return out


def _extract_what_this_does(body: str) -> dict[str, str] | None:
    if not body.strip():
        return None
    out: dict[str, str] = {"prose": body.strip()}
    mech = _MECHANISM_LINE.search(body)
    if mech:
        out["mechanism"] = mech.group(1).strip()
    return out


def _extract_what_this_does_not_do(body: str) -> dict[str, Any] | None:
    if not body.strip():
        return None
    out: dict[str, Any] = {"prose": body.strip()}
    exclusions: list[dict[str, str]] = []
    for m in _DOMAIN_EXCLUSION.finditer(body):
        exclusions.append({"domain": m.group("domain").strip(), "text": m.group("text").strip()})
    if exclusions:
        out["exclusions"] = exclusions
    return out


def _extract_ws_interfaces(body: str) -> dict[str, Any] | None:
    if not body.strip():
        return None
    out: dict[str, Any] = {}
    blocks = _split_h3(body)
    for header, block in blocks:
        h = header.strip().lower()
        if h == "data interfaces":
            rows = _extract_table(
                block,
                ["interface", "direction", "type_shape_dtype", "source_or_consumer", "guarantees"],
            )
            if rows:
                out["data_interfaces"] = rows
        elif h == "process interfaces":
            rows = _extract_table(
                block,
                ["boundary", "transport", "device", "serialization", "failure_mode"],
            )
            if rows:
                out["process_interfaces"] = rows
        elif h == "dependencies":
            rows = _extract_table(block, ["dependency", "interface", "failure_behavior"])
            if rows:
                out["dependencies"] = rows
    return out or None


def _extract_business_rules(body: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _BUSINESS_RULE_LINE.finditer(body):
        num = int(m.group("num"))
        domain = (m.group("domain") or "general").strip()
        rule = m.group("rule").strip()
        # Skip lines that are just structural commentary (italics-only blocks)
        if not rule or rule.startswith("*") and rule.endswith("*"):
            continue
        out.append({"number": num, "domain": domain, "rule": rule})
    return out


def _extract_open_issues_ws(body: str) -> list[dict[str, str]] | None:
    """WS-flavoured open-issues extractor (uses `- [ ]` task syntax).

    Severity tokens are normalized to canonical `P0..P3` via
    `_normalize_severity_alias` (IB-023 / ADR-013). Unknown severity
    strings raise `ParseError`; an absent `**Severity:**` / `**Gate:**`
    token defaults to `non-blocking` (which the alias map maps to
    `P3`).
    """
    text = body.strip()
    if not text:
        return None
    if text.lower().startswith("none"):
        return []
    out: list[dict[str, str]] = []
    for m in _OPEN_ISSUE_TASK.finditer(body):
        # [x] = resolved/done, skip. [ ] = open, include.
        if m.group("state").lower() == "x":
            continue
        raw = m.group("text").strip()
        # Accept optional surrounding backticks on the severity token —
        # the WS template seeds Open Issues rows as
        # `**Severity:** \`P3\`` (markdown code-formatting on the
        # canonical literal). Without explicit backtick handling the
        # greedy `\s*` + char-class would backtrack to capture the
        # single space between `**` and the opening backtick, then
        # stop at the backtick — yielding `sev_raw=' '` which the
        # normalizer rejects (bead
        # `ds-ws-open-issues-severity-backtick-parse-w0ut`). The
        # `?:[ \t]*` after the opening backtick tolerates pathological
        # `**Severity:** \` P3 \`` spacing as well. Backticks are then
        # stripped inside `_normalize_severity_alias`.
        sev_match = re.search(
            r"\*\*(?:Severity|Gate):\*\*[ \t]*`?[ \t]*"
            r"([a-z0-9\-_ \(\)]+?)"
            r"[ \t]*`?(?:\s+[—\-]|\s*$)",
            raw,
            re.IGNORECASE,
        )
        src_match = re.search(r"\*\*Source:\*\*\s*([^—\n]+)", raw, re.IGNORECASE)
        text_only = re.split(
            r"\s+[—-]\s+\*\*(?:Source|Severity|Gate|Owner|Blocks):", raw, maxsplit=1
        )[0].strip()
        sev_raw = sev_match.group(1) if sev_match else "non-blocking"
        sev_norm = _normalize_severity_alias(sev_raw)
        entry: dict[str, str] = {"text": text_only, "severity": sev_norm}
        if src_match:
            entry["source"] = src_match.group(1).strip()
        out.append(entry)
    return out


def _normalize_ws_severity(raw: str) -> str:
    """DEPRECATED — delegates to `_normalize_severity_alias`; remove
    after v0.3.0 (per WS-013 §Open Issues row 1's one-minor-release
    retention window).

    Behavior matches `_normalize_severity_alias` exactly: emits
    canonical `P0..P3`, raises `ParseError` on unknown inputs. The
    historical silent-fold-to-`non_blocking` return and the
    substring-heuristic for `pre-ib` / `pre-code` keywords are gone —
    every recognized legacy alias flows through the shared
    `ARTIFACT_SEVERITY_ALIAS_MAP` in `dekspec.severity` (which already
    covers the `pre-ib` / `pre-code` variant spellings).
    """
    return _normalize_severity_alias(raw)


def _extract_ws_contracts(sections: dict[str, str]) -> dict[str, Any] | None:
    out: dict[str, Any] = {}
    section_to_key = {
        "Model Behavior Contract": ("model_behavior", _MODEL_BEHAVIOR_FIELDS),
        "Graph Behavior Contract": ("graph_behavior", _GRAPH_BEHAVIOR_FIELDS),
        "Timeline Behavior Contract": ("timeline_behavior", _TIMELINE_BEHAVIOR_FIELDS),
        "Quantization Contract": ("quantization", _QUANTIZATION_FIELDS),
    }
    for section, (key, field_map) in section_to_key.items():
        body = sections.get(section, "").strip()
        if not body:
            continue
        contract: dict[str, str] = {"raw_markdown": body}
        for label, ir_field in field_map:
            m = re.search(
                rf"^[-*]\s*{re.escape(label)}\s*[:\-—]\s*(.+?)(?=\n[-*]|\Z)",
                body,
                re.MULTILINE | re.DOTALL,
            )
            if m:
                contract[ir_field] = m.group(1).strip().rstrip(",.")
        out[key] = contract
    return out or None


_MODEL_BEHAVIOR_FIELDS = [
    ("Injection layer", "injection_layer"),
    ("Position ID construction", "position_id_construction"),
    ("KV cache behavior", "kv_cache_behavior"),
    ("Attention mask", "attention_mask"),
    ("Generation trigger", "generation_trigger"),
]
_GRAPH_BEHAVIOR_FIELDS = [
    ("Read path", "read_path"),
    ("Write path", "write_path"),
    ("Flush trigger", "flush_trigger"),
    ("Flush failure behavior", "flush_failure_behavior"),
    ("Phantom detection", "phantom_detection"),
    ("Tenant isolation", "tenant_isolation"),
]
_TIMELINE_BEHAVIOR_FIELDS = [
    ("Read path", "read_path"),
    ("Write path", "write_path"),
    ("Flush failure behavior", "flush_failure_behavior"),
    ("Topic boundary validation", "topic_boundary_validation"),
    ("Decay reference", "decay_reference"),
    ("Pre-quantized copy staleness", "pre_quantized_copy_staleness"),
    ("Tenant isolation", "tenant_isolation"),
]
_QUANTIZATION_FIELDS = [
    ("Input dtype", "input_dtype"),
    ("Output dtype", "output_dtype"),
    ("Bit depths", "bit_depths"),
    ("Max reconstruction error", "max_reconstruction_error"),
    ("Round-trip fidelity", "round_trip_fidelity"),
    ("Constant tensor handling", "constant_tensor_handling"),
]


# --------------------------------------------------------------------------- #
# WS schema validation
# --------------------------------------------------------------------------- #


def _load_ws_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("working_spec")


def _validate_ws(ir: dict[str, Any]) -> None:
    schema = _load_ws_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise WSParseError("Parsed WS IR failed schema validation:\n" + "\n".join(msgs))


# =========================================================================== #
# ADR parser (v0.3-dev)
# =========================================================================== #

_ADR_FILENAME = re.compile(r"^(ADR-\d{3,})-.+\.md$")
_ADR_H1_TITLE = re.compile(r"^#\s+ADR-\d{3,}:\s*(.+?)\s*$", re.MULTILINE)
_ADR_VALID_STATUSES = {
    "TODO", "DRAFT", "PROPOSED", "ACCEPTED", "LOCKED", "DEPRECATED", "SUPERSEDED",
}
_SUPERSEDES_LINE = re.compile(r"\*Supersedes:\*\s*(.+?)(?=\n|$)", re.MULTILINE)
_SUPERSEDED_BY_LINE = re.compile(r"\*Superseded by:\*\s*(.+?)(?=\n|$)", re.MULTILINE)
_ADR_ID_REF = re.compile(r"\b(ADR-\d{3,})\b")
_DECISION_DRIVERS_BLOCK = re.compile(
    r"\*\*Decision drivers:\*\*\s*\n(.+?)(?=\n\*|\n##|\Z)", re.DOTALL
)
_TECHNICAL_STORY_LINE = re.compile(r"\*Technical story:\*\s*(.+?)(?=\n|$)", re.MULTILINE)
_OPTION_H3 = re.compile(r"^###\s+(?:Option\s+\w+:\s*)?(.+?)\s*$", re.MULTILINE)
_OBSERVABLE_CONFIRMATION = re.compile(
    r"\*\*Observable confirmation:\*\*\s*\n(.+?)(?=\n\*\*|\n##|\Z)", re.DOTALL
)
_RECONSIDERATION_TRIGGERS = re.compile(
    r"\*\*Reconsideration triggers:\*\*\s*\n(.+?)(?=\n\*\*|\n##|\Z)", re.DOTALL
)
# M1 — extract reconsideration triggers from grandfathered prose form.
# Matches sentences (or clauses) that start with a reconsideration-marker phrase.
_RECONSIDER_PROSE = re.compile(
    r"((?:revisit|reconsider)\s+"
    r"(?:this\s+)?(?:decision\s+)?"
    r"(?:should\s+be\s+)?"
    r"(?:if|when|on|once|after)\s+"
    r"[^.!?]+[.!?])",
    re.IGNORECASE,
)
_POSITIVE_BLOCK = re.compile(r"\*\*Positive:\*\*\s*\n(.+?)(?=\n\*\*|\n##|\Z)", re.DOTALL)
_NEGATIVE_BLOCK = re.compile(r"\*\*Negative:\*\*\s*\n(.+?)(?=\n\*\*|\n##|\Z)", re.DOTALL)
_PROS_LINE = re.compile(r"\*\*Pros:\*\*\s*(.+?)(?=\n|$)", re.MULTILINE)
_CONS_LINE = re.compile(r"\*\*Cons:\*\*\s*(.+?)(?=\n|$)", re.MULTILINE)


class ADRParseError(Exception):
    """Raised when an ADR's parsed IR fails schema validation."""


def parse_adr(path: str | Path) -> dict[str, Any]:
    """Parse an Architecture Decision Record markdown file into a validated IR.

    Mirrors the IC / AE / WS parsers — lossy by design, missing fields populate
    parse_warnings, schema validation runs after extraction.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    ctx = _ParseContext(src=src, text=text, sections=_split_sections(text))

    ir: dict[str, Any] = {
        # ADR IR bumped 0.1.0 → 0.2.0 at IB-023 (severity vocabulary
        # unification — see ADR-013); `open_issues[*].severity` is
        # now canonical `P0..P3` rather than legacy
        # `{blocking, non_blocking}`.
        "ir_schema_version": _ADR_IR_SCHEMA_VERSION,
        "id": _extract_adr_id(src.name),
        "name": _extract_adr_name(text),
        "status": _extract_adr_status(ctx),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    supersession = _extract_supersession(ctx.sections.get("Supersession", ""))
    if supersession:
        ir["supersession"] = supersession

    related_aes = _extract_related_aes_ws(ctx.sections.get("Related Architecture Elements", ""))
    if related_aes:
        ir["related_architecture_elements"] = related_aes

    _maybe_set(ir, "created", _extract_first_date(ctx.sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(ctx.sections.get("Modified", "")))
    _maybe_set(ir, "date", _extract_first_date(ctx.sections.get("Date", "")))

    deciders = ctx.sections.get("Deciders", "").strip()
    if deciders:
        ir["deciders"] = deciders

    cdd = _extract_context_and_decision_drivers(
        ctx.sections.get("Context and Decision Drivers", "")
    )
    if cdd:
        ir["context_and_decision_drivers"] = cdd

    decision = ctx.sections.get("Decision", "").strip()
    if decision:
        ir["decision"] = decision

    options = _extract_options_considered(ctx.sections.get("Options Considered", ""))
    if options:
        ir["options_considered"] = options

    consequences = _extract_consequences(ctx.sections.get("Consequences", ""))
    if consequences:
        ir["consequences"] = consequences

    validation = _extract_validation(ctx.sections.get("Validation", ""))
    if validation:
        ir["validation"] = validation

    links = _extract_bullets(ctx.sections.get("Links", ""))
    if links:
        ir["links"] = links

    issues = _extract_open_issues(ctx.sections.get("Open Issues", ""))
    if issues is not None:
        ir["open_issues"] = issues

    amendments = _extract_adr_amendment_log(ctx.sections.get("Amendment Log", ""))
    if amendments:
        ir["amendment_log"] = amendments

    if ctx.warnings:
        ir["parse_warnings"] = [w.to_dict() for w in ctx.warnings]

    _validate_adr(ir)
    return ir


# --------------------------------------------------------------------------- #
# ADR field extractors
# --------------------------------------------------------------------------- #


def _extract_adr_id(filename: str) -> str:
    m = _ADR_FILENAME.match(filename)
    if not m:
        if _draft_id_or_none(filename) is not None:
            raise DraftArtifactError(
                f"{filename} is a DRAFT artifact (ADR-DRAFT-<slug>); allocate a "
                f"canonical ID with `dekspec id allocate` before parsing."
            )
        raise ADRParseError(f"Filename does not match ADR-NNN-*.md pattern: {filename}")
    return m.group(1)


def _extract_adr_name(text: str) -> str:
    m = _ADR_H1_TITLE.search(text)
    if not m:
        raise ADRParseError("Missing or malformed H1 — expected '# ADR-NNN: <Verb-first title>'")
    return m.group(1).strip()


def _extract_adr_status(ctx: _ParseContext) -> str:
    body = ctx.sections.get("Status", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        token = s.split()[0].strip("`*_").upper()
        if token in _ADR_VALID_STATUSES:
            return token
    raise ADRParseError(
        "Could not extract a valid Status (TODO|DRAFT|PROPOSED|ACCEPTED|LOCKED|DEPRECATED|SUPERSEDED)"
    )


def _extract_supersession(body: str) -> dict[str, list[str]] | None:
    if not body.strip():
        return None
    out: dict[str, list[str]] = {}
    sup = _SUPERSEDES_LINE.search(body)
    if sup:
        ids = _ADR_ID_REF.findall(sup.group(1))
        if ids:
            out["supersedes"] = list(dict.fromkeys(ids))
    sup_by = _SUPERSEDED_BY_LINE.search(body)
    if sup_by:
        ids = _ADR_ID_REF.findall(sup_by.group(1))
        if ids:
            out["superseded_by"] = list(dict.fromkeys(ids))
    return out or None


def _extract_context_and_decision_drivers(body: str) -> dict[str, Any] | None:
    if not body.strip():
        return None
    out: dict[str, Any] = {}
    # Capture context prose (everything before **Decision drivers:**)
    drivers_match = _DECISION_DRIVERS_BLOCK.search(body)
    if drivers_match:
        context_prose = body[: drivers_match.start()].strip()
        if context_prose:
            out["context_prose"] = context_prose
        drivers = _extract_bullets(drivers_match.group(1))
        if drivers:
            out["decision_drivers"] = drivers
    else:
        # No Decision drivers block — entire body is context prose.
        out["context_prose"] = body.strip()
    tech = _TECHNICAL_STORY_LINE.search(body)
    if tech:
        out["technical_story"] = tech.group(1).strip()
    return out or None


def _extract_options_considered(body: str) -> list[dict[str, Any]]:
    if not body.strip():
        return []
    out: list[dict[str, Any]] = []
    blocks = _split_h3(body)
    for header, block in blocks:
        if not header.strip():
            continue  # skip preamble before first H3
        # Strip "Option X: " prefix from name
        name = re.sub(r"^Option\s+\w+:\s*", "", header).strip()
        # Strip trailing markers like "(chosen)"
        entry: dict[str, Any] = {"name": name}
        # Description = prose before first **Pros:** or **Cons:** marker
        pros_match = _PROS_LINE.search(block)
        cons_match = _CONS_LINE.search(block)
        first_marker = min(
            (m.start() for m in [pros_match, cons_match] if m),
            default=len(block),
        )
        desc = block[:first_marker].strip()
        if desc:
            entry["description"] = desc
        if pros_match:
            entry["pros"] = [pros_match.group(1).strip()]
        if cons_match:
            entry["cons"] = [cons_match.group(1).strip()]
        out.append(entry)
    return out


def _extract_consequences(body: str) -> dict[str, list[str]] | None:
    if not body.strip():
        return None
    out: dict[str, list[str]] = {}
    pos_match = _POSITIVE_BLOCK.search(body)
    if pos_match:
        bullets = _extract_bullets(pos_match.group(1))
        if bullets:
            out["positive"] = bullets
    neg_match = _NEGATIVE_BLOCK.search(body)
    if neg_match:
        bullets = _extract_bullets(neg_match.group(1))
        if bullets:
            out["negative"] = bullets
    return out or None


def _extract_validation(body: str) -> dict[str, str] | None:
    if not body.strip():
        return None
    out: dict[str, str] = {}
    obs_match = _OBSERVABLE_CONFIRMATION.search(body)
    rec_match = _RECONSIDERATION_TRIGGERS.search(body)
    if obs_match:
        out["observable_confirmation"] = obs_match.group(1).strip()
    if rec_match:
        out["reconsideration_triggers"] = rec_match.group(1).strip()
    if not out:
        # Grandfathered prose form (pre-2026-04-24 ADRs).
        prose = body.strip()
        out["raw_prose"] = prose
        # M1: try to extract reconsideration triggers from the prose form too,
        # so the agents-md emitter can show "Reconsider this decision if ..."
        # for grandfathered ADRs without forcing the engineer to migrate.
        rec_prose_matches = _RECONSIDER_PROSE.findall(prose)
        if rec_prose_matches:
            out["reconsideration_triggers"] = " ".join(
                m.strip() for m in rec_prose_matches
            )
    return out


_ADR_AMENDMENT_TYPES = {
    "editorial", "unlock", "substantive", "fill", "migration", "lock", "supersession",
}


def _extract_adr_amendment_log(body: str) -> list[dict[str, str]]:
    rows = _extract_table(body, ["date", "type", "change", "author"])
    cleaned: list[dict[str, str]] = []
    for r in rows:
        if "date" not in r or "change" not in r:
            continue
        t = r.get("type", "").strip().lower()
        if t not in _ADR_AMENDMENT_TYPES:
            t = "editorial"
        r["type"] = t
        cleaned.append(r)
    return cleaned


# --------------------------------------------------------------------------- #
# ADR schema validation
# --------------------------------------------------------------------------- #


def _load_adr_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("adr")


def _validate_adr(ir: dict[str, Any]) -> None:
    schema = _load_adr_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise ADRParseError("Parsed ADR IR failed schema validation:\n" + "\n".join(msgs))


# --------------------------------------------------------------------------- #
# IB IR (Implementation Brief) parser
# --------------------------------------------------------------------------- #

_IB_FILENAME = re.compile(r"^(IB-\d{3,})-.+\.md$")
_IB_VALID_STATUSES = {
    "TODO", "DRAFT", "PROPOSED", "ACCEPTED", "LOCKED",
    "QUEUED", "ACTIVE", "COMPLETED",
    # MSN-017 two-tier review pipeline (INT-102 IU-1, ds-2zoj):
    "REVIEW_IB", "REVIEW_IB_FAIL", "REVIEW_PR", "REVIEW_PR_FAIL", "TESTFAIL",
}
_IB_H1_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_IB_META_LINE = re.compile(r"^\*\*([^*]+?):\*\*\s*(.+?)\s*$", re.MULTILINE)
_IB_AE_ID_REF = re.compile(r"\b(AE-\d{3,})\b")
_IB_IB_ID_REF = re.compile(r"\b(IB-\d{3,})\b")
_IB_INT_ID_REF = re.compile(r"\b(INT-\d{3,})\b")
_WS_ID_FROM_PATH_IB = re.compile(r"\b(WS-\d{3,})\b")


class IBParseError(Exception):
    """Raised when an IB's parsed IR fails schema validation."""


def parse_ib(path: str | Path) -> dict[str, Any]:
    """Parse an Implementation Brief markdown file into a validated IR dict.

    Mirrors parse_ic / parse_ae / parse_ws / parse_adr — lossy by design.
    Missing fields populate parse_warnings; schema validation runs after
    extraction.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    ctx = _ParseContext(src=src, text=text, sections=_split_sections(text))
    meta = _extract_ib_metadata(text)

    ir: dict[str, Any] = {
        # IB IR bumped 0.1.0 → 0.2.0 at IB-023 (severity vocabulary
        # unification — see ADR-013); `open_issues[*].severity` is
        # now canonical `P0..P3` rather than legacy
        # `{blocking, non_blocking}`.
        "ir_schema_version": _IB_IR_SCHEMA_VERSION,
        "id": _extract_ib_id(src.name),
        "name": _extract_ib_name(text),
        "status": _extract_ib_status(meta, ctx),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    spec = _extract_ib_spec(meta)
    if spec:
        ir["spec"] = spec
    else:
        ctx.warnings.append(_Warn(
            field="/spec",
            reason="No `**Spec:** path/to/WS-NNN-*.md` line at top of file",
            severity="warning",
        ))

    intent = _extract_ib_intent(meta)
    if intent:
        ir["intent"] = intent

    source_aes = _extract_ib_source_aes(meta)
    if source_aes:
        ir["source_aes"] = source_aes

    depends_on = _extract_ib_depends_on(meta)
    if depends_on:
        ir["depends_on"] = depends_on

    prod_gate = (meta.get("Production gate") or "").strip()
    if prod_gate:
        ir["production_gate"] = prod_gate

    # INT-102 IU-1 (ds-2zoj): MSN-017 two-tier review pipeline.
    # `**Review grandfathered:** true|false` meta-line is optional;
    # absent → false. Anything other than a recognized truthy token
    # also resolves to false (the strict default), so a malformed
    # value silently degrades rather than failing the parse.
    rg_raw = (meta.get("Review grandfathered") or "").strip().lower()
    ir["review_grandfathered"] = rg_raw in {"true", "yes", "1"}

    goal = ctx.sections.get("Goal", "").strip()
    if goal:
        ir["goal"] = goal

    out_of_scope = _extract_bullets(ctx.sections.get("Out of Scope", ""))
    if out_of_scope:
        ir["out_of_scope"] = out_of_scope

    governing_adrs = _extract_governing_adrs(ctx.sections.get("Governing ADRs", ""))
    if governing_adrs:
        ir["governing_adrs"] = governing_adrs

    files_to_modify = _extract_table(
        ctx.sections.get("Files to Modify", ""), ["file", "change"]
    )
    if files_to_modify:
        ir["files_to_modify"] = files_to_modify

    do_not_touch = _extract_bullets(ctx.sections.get("Do Not Touch", ""))
    if do_not_touch:
        ir["do_not_touch"] = do_not_touch

    done_when = _extract_bullets(ctx.sections.get("Done When", ""))
    if done_when:
        ir["done_when"] = done_when

    # ds-ibx: §Constraints & Decisions + §Domain Constraints lifted to canonical IR fields.
    cd_body = ctx.sections.get("Constraints & Decisions", "")
    cd = _extract_constraints_and_decisions(cd_body)
    if cd:
        ir["constraints_and_decisions"] = cd
    elif cd_body.strip() and _is_placeholder_constraints(cd_body):
        ctx.warnings.append(_Warn(
            field="/constraints_and_decisions",
            reason=(
                "§Constraints & Decisions section is present but contains only "
                "placeholder template text (no `- **topic:** rule` bullets). "
                "Author actual entries to populate the IR field."
            ),
            severity="warning",
        ))

    dc = _extract_ib_domain_constraints(ctx.sections.get("Domain Constraints", ""))
    if dc:
        ir["domain_constraints"] = dc

    issues = _extract_open_issues(ctx.sections.get("Open Issues", ""))
    if issues:
        ir["open_issues"] = issues

    if ctx.warnings:
        ir["parse_warnings"] = [w.to_dict() for w in ctx.warnings]

    _validate_ib(ir)
    return ir


def _extract_ib_id(filename: str) -> str:
    m = _IB_FILENAME.match(filename)
    if not m:
        if _draft_id_or_none(filename) is not None:
            raise DraftArtifactError(
                f"{filename} is a DRAFT artifact (IB-DRAFT-<slug>); allocate a "
                f"canonical ID with `dekspec id allocate` before parsing."
            )
        raise IBParseError(f"Filename does not match IB-NNN-*.md pattern: {filename}")
    return m.group(1)


def _extract_ib_name(text: str) -> str:
    m = _IB_H1_TITLE.search(text)
    if not m:
        raise IBParseError("Missing or malformed H1 — expected '# Implementation Brief: ...'")
    return m.group(1).strip()


def _extract_ib_metadata(text: str) -> dict[str, str]:
    """The IB header has 4-6 `**Key:** value` lines between the H1 and the
    first `## Section`. Returns key->value mapping for those lines.
    """
    out: dict[str, str] = {}
    h1_end = text.find("\n", text.find("# "))
    section_start = text.find("\n## ", h1_end if h1_end != -1 else 0)
    header = text[h1_end:section_start] if section_start != -1 else text[h1_end:]
    for m in _IB_META_LINE.finditer(header):
        key = m.group(1).strip()
        value = m.group(2).strip().strip("`")
        out[key] = value
    return out


def _extract_ib_status(meta: dict[str, str], ctx: _ParseContext) -> str:
    raw = (meta.get("Status") or "").strip()
    if raw:
        # Strip parenthetical / em-dash trailing notes
        token = raw.split()[0].strip("`*_").upper()
        if token in _IB_VALID_STATUSES:
            return token
    raise IBParseError(
        "Could not extract a valid Status from `**Status:** ...` "
        "(TODO|DRAFT|PROPOSED|ACCEPTED|LOCKED|QUEUED|ACTIVE|COMPLETED|"
        "REVIEW_IB|REVIEW_IB_FAIL|REVIEW_PR|REVIEW_PR_FAIL|TESTFAIL)"
    )


def _extract_ib_spec(meta: dict[str, str]) -> dict[str, str] | None:
    raw = (meta.get("Spec") or "").strip()
    if not raw or raw.lower() == "none":
        return None
    m = _WS_ID_FROM_PATH_IB.search(raw)
    if not m:
        return None
    out = {"id": m.group(1)}
    if raw != m.group(1):
        out["path"] = raw
    return out


def _extract_ib_intent(meta: dict[str, str]) -> dict[str, str] | None:
    raw = (meta.get("Intent") or "").strip()
    if not raw or raw.lower() == "none":
        return None
    m = _IB_INT_ID_REF.search(raw)
    if not m:
        return None
    out = {"id": m.group(1)}
    if raw != m.group(1):
        out["path"] = raw
    return out


def _extract_ib_source_aes(meta: dict[str, str]) -> list[dict[str, str]]:
    raw = (meta.get("Source AEs") or "").strip()
    if not raw or raw.lower() == "none":
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in _IB_AE_ID_REF.finditer(raw):
        ae_id = m.group(1)
        if ae_id in seen:
            continue
        seen.add(ae_id)
        out.append({"id": ae_id})
    return out


def _extract_ib_depends_on(meta: dict[str, str]) -> list[str]:
    raw = (meta.get("Depends on") or "").strip()
    if not raw or raw.lower() == "none":
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in _IB_IB_ID_REF.finditer(raw):
        ib_id = m.group(1)
        if ib_id in seen:
            continue
        seen.add(ib_id)
        out.append(ib_id)
    return out


_IB_CD_BULLET = re.compile(
    r"^[-*]\s+\*\*(?P<topic>[^*\n]+?):\*\*\s*(?P<rule>.+?)\s*$",
    re.MULTILINE,
)


def _extract_constraints_and_decisions(body: str) -> list[dict[str, str]]:
    """ds-ibx: extract `- **topic:** rule` bullets into structured entries.

    Placeholder bullets whose topic is bracket-wrapped (`[topic]`) are
    skipped so an unedited template doesn't populate the IR. The check
    runs at the topic level — rule prose may still legitimately contain
    brackets (e.g., shape annotations like `[1, 2048]`).
    """
    out: list[dict[str, str]] = []
    for m in _IB_CD_BULLET.finditer(body):
        topic = m.group("topic").strip()
        rule = m.group("rule").strip()
        if not topic or not rule:
            continue
        # Skip template placeholders (e.g., `**[topic]:** [what to do ...]`).
        if topic.startswith("[") and topic.endswith("]"):
            continue
        out.append({"topic": topic, "rule": rule})
    return out


def _is_placeholder_constraints(body: str) -> bool:
    """ds-ibx: heuristic — `body` is template-placeholder-only when the
    extractor produced no real entries AND the body either carries the
    template's "[Replace this block...]" marker or only has bracket-topic
    bullets (`- **[topic]:** ...`). Avoids false-positive warnings on
    absent sections AND false-negative silence on unedited templates."""
    return "Replace this block" in body or "[topic]" in body


_IB_DC_PLACEHOLDER_VALUE = re.compile(r"^\s*\[.*\]\s*$")


def _extract_ib_domain_constraints(body: str) -> list[dict[str, str]]:
    """ds-ibx: extract the §Domain Constraints `| constraint | value |` table.

    Rows whose value is the bare "n/a" sentinel or a bracket-only template
    placeholder are dropped — the IR should only carry binding constraints.
    """
    rows = _extract_table(body, ["constraint", "value"])
    out: list[dict[str, str]] = []
    for r in rows:
        constraint = (r.get("constraint") or "").strip()
        value = (r.get("value") or "").strip()
        if not constraint or not value:
            continue
        if value.lower() == "n/a":
            continue
        if _IB_DC_PLACEHOLDER_VALUE.match(value):
            continue
        out.append({"constraint": constraint, "value": value})
    return out


def _load_ib_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("implementation_brief")


def _validate_ib(ir: dict[str, Any]) -> None:
    schema = _load_ib_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise IBParseError("Parsed IB IR failed schema validation:\n" + "\n".join(msgs))


# --------------------------------------------------------------------------- #
# Intent IR (INT-NNN) parser
# --------------------------------------------------------------------------- #

_INT_FILENAME = re.compile(r"^(INT-\d{3,})-.+\.md$")
_INT_VALID_STATUSES = {
    # `TODO` + `TESTFAIL` retired 2026-05-25 (E3 audit: 0 in-degree,
    # 0 out-degree, 0 as-initial across the 99-Intent history). Files
    # authored against the legacy enum are rejected at schema validation;
    # transition them to DRAFT or IMPLEMENTING respectively before parse.
    "DRAFT", "OVERSIZED", "PROPOSED", "ACCEPTED", "IMPLEMENTING",
    "TESTPASS", "MERGED", "LOCKED", "SUPERSEDED",
}
# Retired Intent statuses — extraction matches these so the parser can
# emit a targeted error message instead of "could not extract a valid
# status." Pre-retirement files surface a clear migration path.
_INT_RETIRED_STATUSES = {"TODO", "TESTFAIL"}
_INT_VALID_TYPES = {
    "feature", "bug", "nfr", "adr-driven", "refactor", "documentation", "environment",
}
_INT_VALID_AUTONOMY = {"manual", "low", "medium", "high"}
_INT_H1_TITLE = re.compile(r"^#\s+INT-\d{3,}:\s*(.+?)\s*$", re.MULTILINE)
_INT_AE_REF = re.compile(r"^[-*]\s*(?:\*\*)?(AE-\d{3,})(?:\*\*)?\s*[:\-—]\s*(?P<rest>.+?)$", re.MULTILINE)
_INT_GLOB_BULLET = re.compile(r"^[-*]\s*`([^`]+)`(?:[ \t]+.*)?$", re.MULTILINE)
_INT_FENCED_YAML = re.compile(r"```(?:yaml)?\s*\n(.*?)\n```", re.DOTALL)
_INT_VERIF_ENTRY = re.compile(r"-\s+name:\s*(.+?)\n\s+cmd:\s*(.+?)(?=\n\s*-|\n*$)", re.DOTALL)


class IntentParseError(Exception):
    """Raised when an Intent's parsed IR fails schema validation."""


def parse_intent(path: str | Path) -> dict[str, Any]:
    """Parse an Intent markdown file into a validated IR.

    Lossy by design — missing fields surface as parse_warnings; schema
    validation runs after extraction.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    ctx = _ParseContext(src=src, text=text, sections=_split_sections(text))

    ir: dict[str, Any] = {
        # Intent IR bumped 0.1.0 → 0.2.0 at IB-023 (severity vocabulary
        # unification — see ADR-013); `open_issues[*].severity` is
        # now canonical `P0..P3` rather than legacy
        # `{blocking, non_blocking}`.
        "ir_schema_version": _INTENT_IR_SCHEMA_VERSION,
        "id": _extract_intent_id(src.name),
        "name": _extract_intent_name(text),
        "status": _extract_intent_status(ctx),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    intent_type = _extract_intent_type(ctx)
    if intent_type:
        ir["intent_type"] = intent_type

    autonomy = _extract_intent_autonomy(ctx)
    if autonomy:
        ir["autonomy"] = autonomy

    risk_tier = _extract_intent_risk_tier(ctx)
    if risk_tier:
        ir["risk_tier"] = risk_tier

    beads_before_accept = _extract_intent_beads_before_accept(ctx)
    if beads_before_accept is not None:
        ir["beads_before_accept"] = beads_before_accept

    branch = ctx.sections.get("Branch", "").strip().strip("`").strip()
    if branch:
        ir["branch"] = branch

    mission = _extract_intent_mission(ctx.sections.get("Mission", ""))
    if mission:
        ir["mission"] = mission

    src_prov = ctx.sections.get("Source", "").strip()
    if src_prov and src_prov.lower() != "none":
        ir["source_provenance"] = src_prov

    superseded_by = ctx.sections.get("Superseded-By", "").strip()
    m = re.search(r"\bINT-\d{3,}\b", superseded_by)
    if m:
        ir["superseded_by"] = m.group(0)

    _maybe_set(ir, "created", _extract_first_date(ctx.sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(ctx.sections.get("Modified", "")))

    aes = _extract_intent_aes(ctx.sections.get("Linked Architecture Elements", ""))
    if aes:
        ir["linked_architecture_elements"] = aes

    motivation = ctx.sections.get("Motivation", "").strip()
    if motivation:
        ir["motivation"] = motivation

    desired = ctx.sections.get("Desired Outcome", "").strip()
    if desired:
        ir["desired_outcome"] = desired

    type_specific = _extract_intent_type_specific(ctx)
    if type_specific:
        ir["type_specific"] = type_specific

    components = _extract_intent_components_affected(
        ctx.sections.get("Components affected", "")
    )
    if components:
        ir["components_affected"] = components

    verification = _extract_intent_verification(ctx.sections.get("Verification", ""))
    if verification:
        ir["verification"] = verification

    issues = _extract_open_issues(ctx.sections.get("Open Issues", ""))
    if issues:
        ir["open_issues"] = issues

    amendments = _extract_intent_amendment_log(ctx.sections.get("Amendment Log", ""))
    if amendments:
        ir["amendment_log"] = amendments

    # INT-112 Slice A / ADR-029 — Outcome Verification section + auto-grandfather.
    # Surface `outcome_verification` from the `## Outcome Verification` H2 body
    # when present + non-empty. Auto-stamp `outcome_verification_grandfathered:
    # true` for Intents created strictly before the INT-112 Slice A cutover
    # date (2026-05-30) when no outcome_verification was captured — matches
    # the schema-comment contract: "Parser defaults absent meta-line to true
    # for pre-existing Intents, false for new ones (post-INT-112-merge)."
    # Without this stamping, T-VERIFICATION-OUTCOME fires unconditionally on
    # every legacy Intent.
    # Strip the template's instructional italic block (lines that are pure
    # `*...*` and start with `*Per ADR-029`) so an untouched template
    # section reads as empty for grandfather purposes.
    _outcome_raw = ctx.sections.get("Outcome Verification", "")
    _outcome_body = "\n".join(
        line for line in _outcome_raw.splitlines()
        if not line.strip().startswith("*Per ADR-029")
    ).strip()
    if _outcome_body:
        ir["outcome_verification"] = _outcome_body
        ir["outcome_verification_grandfathered"] = False
    else:
        _OUTCOME_CUTOVER_DATE = "2026-05-30"
        _created_str = ir.get("created", "") or ""
        # `created` may be a datetime, date, or str depending on the
        # _extract_first_date contract; normalize to ISO-date string.
        _created_iso = getattr(_created_str, "isoformat", lambda: str(_created_str))()
        if not _created_iso or _created_iso <= _OUTCOME_CUTOVER_DATE:
            ir["outcome_verification_grandfathered"] = True
        else:
            ir["outcome_verification_grandfathered"] = False

    if ctx.warnings:
        ir["parse_warnings"] = [w.to_dict() for w in ctx.warnings]

    _validate_intent(ir)
    return ir


def _extract_intent_id(filename: str) -> str:
    m = _INT_FILENAME.match(filename)
    if not m:
        if _draft_id_or_none(filename) is not None:
            raise DraftArtifactError(
                f"{filename} is a DRAFT artifact (INT-DRAFT-<slug>); allocate a "
                f"canonical ID with `dekspec id allocate` before parsing."
            )
        raise IntentParseError(f"Filename does not match INT-NNN-*.md pattern: {filename}")
    return m.group(1)


def _extract_intent_name(text: str) -> str:
    m = _INT_H1_TITLE.search(text)
    if not m:
        raise IntentParseError("Missing or malformed H1 — expected '# INT-NNN: <title>'")
    return m.group(1).strip()


def _extract_intent_status(ctx: _ParseContext) -> str:
    body = ctx.sections.get("Status", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        token = s.split()[0].strip("`*_").upper()
        if token in _INT_VALID_STATUSES:
            return token
        if token in _INT_RETIRED_STATUSES:
            replacement = "DRAFT" if token == "TODO" else "IMPLEMENTING"
            raise IntentParseError(
                f"Intent Status `{token}` was retired 2026-05-25 (E3 audit — "
                f"0 in/out-degree across 99-Intent history). Transition this "
                f"Intent to `{replacement}` (the closest live status on the "
                f"new lifecycle: DRAFT -> PROPOSED -> ACCEPTED -> IMPLEMENTING "
                f"-> TESTPASS -> MERGED -> LOCKED). See CHANGELOG entry for "
                f"the retirement migration note."
            )
    raise IntentParseError("Could not extract a valid Intent Status.")


def _extract_intent_type(ctx: _ParseContext) -> str | None:
    body = ctx.sections.get("Intent type", "")
    for line in body.splitlines():
        s = line.strip().lower()
        if not s or s.startswith("*") or s.startswith("[") or s.startswith("pick"):
            continue
        token = s.split()[0].strip("`*_-")
        if token in _INT_VALID_TYPES:
            return token
    return None


def _extract_intent_autonomy(ctx: _ParseContext) -> str | None:
    body = ctx.sections.get("Autonomy", "")
    for line in body.splitlines():
        s = line.strip().lower()
        if not s or s.startswith("*") or s.startswith("[") or s.startswith("required"):
            continue
        token = s.split()[0].strip("`*_-")
        if token in _INT_VALID_AUTONOMY:
            return token
    return None


def _extract_intent_risk_tier(ctx: _ParseContext) -> str | None:
    """Extract the open-enum `risk_tier` value from the ## Risk Tier section.

    Open-enum (ds-d0as / Phase 1.B): no schema-side enum, no value rejection.
    Returns the first non-meta-prefixed single token; the audit rule
    T-INT-RISK-TIER-VALID surfaces P3 advisories for unrecognized values.
    Absent section / placeholder-only body → None.
    """
    body = ctx.sections.get("Risk Tier", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*") or s.startswith("[") or s.lower().startswith(("optional", "recommended")):
            continue
        token = s.split()[0].strip("`*_-")
        if token:
            return token
    return None


def _extract_intent_beads_before_accept(ctx: _ParseContext) -> bool | None:
    """Extract the optional `beads_before_accept` boolean from the Intent body.

    Looks for a `**Beads before accept:**` meta-line anywhere in the full
    document text.  Returns True/False when found, None when absent.  Absent
    → the schema default (true) applies at validation time.
    (INT-104 IU-1 / ds-xoah)
    """
    for line in ctx.text.splitlines():
        s = line.strip()
        low = s.lower()
        if low.startswith("**beads before accept:**"):
            val = s.split(":", 1)[1].strip().strip("*").strip().lower()
            if val in ("false", "no"):
                return False
            if val in ("true", "yes", ""):
                return True
            return True  # unrecognized → default true
    return None


def _extract_intent_mission(body: str) -> dict[str, str] | None:
    raw = body.strip()
    if not raw or raw.lower().startswith("none") or raw.startswith("["):
        return None
    m = re.search(r"\bMSN-\d{3,}\b", raw)
    if not m:
        return None
    out = {"id": m.group(0)}
    if raw != m.group(0):
        out["path"] = raw
    return out


def _extract_intent_aes(body: str) -> list[dict[str, str]]:
    if not body.strip():
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in _INT_AE_REF.finditer(body):
        ae_id = m.group(1)
        if ae_id in seen:
            continue
        seen.add(ae_id)
        rest = (m.group("rest") or "").strip()
        entry: dict[str, str] = {"id": ae_id}
        if rest:
            if " — " in rest:
                _, _, desc = rest.partition(" — ")
                entry["description"] = desc.strip()
            else:
                entry["description"] = rest
        out.append(entry)
    return out


def _extract_intent_components_affected(body: str) -> list[str]:
    out: list[str] = []
    for m in _INT_GLOB_BULLET.finditer(body):
        glob = m.group(1).strip()
        if glob and not glob.startswith("path/"):
            out.append(glob)
    return out


def _extract_intent_verification(body: str) -> list[dict[str, str]]:
    if not body.strip():
        return []
    yaml_match = _INT_FENCED_YAML.search(body)
    if not yaml_match:
        return []
    yaml_body = yaml_match.group(1)
    out: list[dict[str, str]] = []
    for m in _INT_VERIF_ENTRY.finditer(yaml_body):
        name = m.group(1).strip().strip("`'\"")
        cmd = m.group(2).strip().strip("`'\"")
        if name and cmd:
            out.append({"name": name, "cmd": cmd})
    return out


def _extract_intent_type_specific(ctx: _ParseContext) -> dict[str, str]:
    """Pull type-specific subsections under §Type-specific required fields.
    Each appears as `### <type> — <field>` H3."""
    out: dict[str, str] = {}
    body = ctx.sections.get("Type-specific required fields", "")
    if not body:
        return out
    # bug — Reproduction
    m = re.search(r"^###\s+`?bug`?\s*[—-]\s*Reproduction\s*$\n(.+?)(?=^###|\Z)", body, re.MULTILINE | re.DOTALL)
    if m:
        out["reproduction"] = m.group(1).strip()
    # nfr — Metric / Target
    metric_m = re.search(r"\*\*Metric:\*\*\s*(.+?)(?=\n|$)", body)
    target_m = re.search(r"\*\*Target:\*\*\s*(.+?)(?=\n|$)", body)
    if metric_m:
        out["metric"] = metric_m.group(1).strip()
    if target_m:
        out["target"] = target_m.group(1).strip()
    # adr-driven — ADR
    adr_m = re.search(r"\*\*ADR:\*\*\s*(ADR-\d{3,})\b", body)
    if adr_m:
        out["adr"] = adr_m.group(1)
    # refactor — Behavior-Equivalence
    be_m = re.search(r"\*\*Behavior-Equivalence:\*\*\s*(.+?)(?=\n\n|\n###|\Z)", body, re.DOTALL)
    if be_m:
        out["behavior_equivalence"] = be_m.group(1).strip()
    # documentation — Coverage-Gap
    cg_m = re.search(r"\*\*Coverage-Gap:\*\*\s*(.+?)(?=\n\n|\n###|\Z)", body, re.DOTALL)
    if cg_m:
        out["coverage_gap"] = cg_m.group(1).strip()
    # environment — Environment-Change
    ec_m = re.search(r"\*\*Environment-Change:\*\*\s*(.+?)(?=\n\n|\n###|\Z)", body, re.DOTALL)
    if ec_m:
        out["environment_change"] = ec_m.group(1).strip()
    return out


def _extract_intent_amendment_log(body: str) -> list[dict[str, str]]:
    rows = _extract_table(body, ["date", "type", "change", "author"])
    out: list[dict[str, str]] = []
    for r in rows:
        if "date" not in r or "change" not in r:
            continue
        t = r.get("type", "").strip().lower()
        if t not in {"editorial", "unlock", "substantive"}:
            t = "editorial"
        r["type"] = t
        out.append(r)
    return out


def _load_intent_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("intent")


def _validate_intent(ir: dict[str, Any]) -> None:
    schema = _load_intent_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise IntentParseError(
            "Parsed Intent IR failed schema validation:\n" + "\n".join(msgs)
        )


# --------------------------------------------------------------------------- #
# Mission IR (MSN-NNN) parser
# --------------------------------------------------------------------------- #

# Mission IR schema version. Bumped 0.1.0 → 0.2.0 at ds-zuy when
# rollback_plan + kill_criteria moved from prose to structured cmd-check
# predicates. Tracked separately from the global IR_SCHEMA_VERSION so
# other artifact types can stay pinned to 0.1.0.
_MISSION_IR_SCHEMA_VERSION = "0.2.0"

_MSN_FILENAME = re.compile(r"^(MSN-\d{3,})-.+\.md$")
_MSN_VALID_STATUSES = {"TODO", "ACTIVE", "COMPLETING", "COMPLETE", "KILLED", "SUPERSEDED"}
_MSN_VALID_AUTONOMY = {"manual", "low", "medium", "high"}
_MSN_H1_TITLE = re.compile(r"^#\s+Mission\s+MSN-\d{3,}:\s*(.+?)\s*$", re.MULTILINE)
_MSN_BOLD_META = re.compile(r"^\*\*([^*]+?):\*\*\s*(.+?)\s*$", re.MULTILINE)


class MissionParseError(Exception):
    """Raised when a Mission's parsed IR fails schema validation."""


def parse_mission(path: str | Path) -> dict[str, Any]:
    """Parse a Mission markdown file into a validated IR.

    The Mission template puts substantive content under H3 inside two H2
    wrappers (Near-immutable / Live). Combine all H3 subsections into one
    name->body map; fall back to H2 for the Amendment Log which lives
    outside the wrappers.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    h2 = _split_sections(text)
    h3: dict[str, str] = {}
    for h2_body in h2.values():
        h3.update(_split_h3_sections(h2_body))
    if "Amendment Log" in h2:
        h3.setdefault("Amendment Log", h2["Amendment Log"])
    meta = _extract_msn_top_metadata(text)

    ctx = _ParseContext(src=src, text=text, sections=h3)
    ir: dict[str, Any] = {
        # Mission IR bumped 0.1.0 → 0.2.0 at ds-zuy: rollback_plan +
        # kill_criteria reshape from prose to named cmd-check predicates
        # (parallel to mission_verification). Other artifact types remain
        # at the global IR_SCHEMA_VERSION default.
        "ir_schema_version": _MISSION_IR_SCHEMA_VERSION,
        "id": _extract_msn_id(src.name),
        "name": _extract_msn_name(text),
        "status": _extract_msn_status(meta),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    if meta.get("Owner"):
        ir["owner"] = meta["Owner"]
    if meta.get("Created"):
        d = _extract_first_date(meta["Created"])
        if d:
            ir["created"] = d
    if meta.get("Modified"):
        d = _extract_first_date(meta["Modified"])
        if d:
            ir["modified"] = d

    autonomy = (meta.get("Autonomy ceiling") or "").strip().lower()
    autonomy_token = autonomy.split()[0].strip("`*_-") if autonomy else ""
    if autonomy_token in _MSN_VALID_AUTONOMY:
        ir["autonomy_ceiling"] = autonomy_token

    outcome = h3.get("Outcome", "").strip()
    if outcome:
        ir["outcome"] = outcome

    verification = _extract_intent_verification_msn(h3.get("Mission Verification", ""))
    if verification:
        ir["mission_verification"] = verification

    out_of_scope = _extract_bullets(h3.get("Out-of-scope", ""))
    if out_of_scope:
        ir["out_of_scope"] = out_of_scope

    flag = _extract_msn_flag_strategy(h3.get("Flag strategy", ""))
    if flag:
        ir["flag_strategy"] = flag

    rollback = _extract_msn_rollback_plan(h3.get("Rollback plan", ""))
    if rollback:
        ir["rollback_plan"] = rollback

    kill = _extract_msn_kill_criteria(h3.get("Kill criteria", ""))
    if kill:
        ir["kill_criteria"] = kill

    first = h3.get("First Intent", "").strip()
    if first:
        m = re.search(r"\bINT-(?:\d{3,}|\?{3,})\b", first)
        if m:
            ir["first_intent"] = m.group(0)

    queue = _extract_msn_intent_queue(h3.get("Intent queue", ""))
    if queue:
        ir["intent_queue"] = queue

    prereqs = _extract_msn_prerequisites(h3.get("Discovered prerequisites", ""))
    if prereqs:
        ir["discovered_prerequisites"] = prereqs

    notes = h3.get("Notes", "").strip()
    if notes and not notes.startswith("[Working notes"):
        ir["notes"] = notes

    amendments = _extract_msn_amendment_log(h3.get("Amendment Log", ""))
    if amendments:
        ir["amendment_log"] = amendments

    if ctx.warnings:
        ir["parse_warnings"] = [w.to_dict() for w in ctx.warnings]

    _validate_mission(ir)
    return ir


def _split_h3_sections(body: str) -> dict[str, str]:
    """Split a markdown body into H3-keyed sections (mirror of _split_sections
    but for `### ` headings)."""
    out: dict[str, str] = {}
    pattern = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(body))
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out[name] = body[start:end].strip("\n")
    return out


def _extract_intent_verification_msn(body: str) -> list[dict[str, str]]:
    """Same as _extract_intent_verification but tolerates the Mission's
    verification yaml that doesn't have an outer `verification:` key
    (it's a bare list)."""
    if not body.strip():
        return []
    yaml_match = _INT_FENCED_YAML.search(body)
    if not yaml_match:
        return []
    yaml_body = yaml_match.group(1)
    out: list[dict[str, str]] = []
    for m in _INT_VERIF_ENTRY.finditer(yaml_body):
        name = m.group(1).strip().strip("`'\"")
        cmd = m.group(2).strip().strip("`'\"")
        if name and cmd:
            out.append({"name": name, "cmd": cmd})
    return out


def _extract_msn_id(filename: str) -> str:
    m = _MSN_FILENAME.match(filename)
    if not m:
        if _draft_id_or_none(filename) is not None:
            raise DraftArtifactError(
                f"{filename} is a DRAFT artifact (MSN-DRAFT-<slug>); allocate a "
                f"canonical ID with `dekspec id allocate` before parsing."
            )
        raise MissionParseError(f"Filename does not match MSN-NNN-*.md pattern: {filename}")
    return m.group(1)


def _extract_msn_name(text: str) -> str:
    m = _MSN_H1_TITLE.search(text)
    if not m:
        raise MissionParseError(
            "Missing or malformed H1 — expected '# Mission MSN-NNN: <title>'"
        )
    return m.group(1).strip()


def _extract_msn_top_metadata(text: str) -> dict[str, str]:
    """The Mission template uses `**Key:** value` lines between the H1 and
    the first `---` divider. Returns key->value mapping."""
    h1_end = text.find("\n", text.find("# "))
    end = text.find("\n---", h1_end if h1_end != -1 else 0)
    header = text[h1_end:end] if end != -1 else text[h1_end:]
    out: dict[str, str] = {}
    for m in _MSN_BOLD_META.finditer(header):
        out[m.group(1).strip()] = m.group(2).strip().strip("`")
    return out


def _extract_msn_status(meta: dict[str, str]) -> str:
    raw = (meta.get("Status") or "").strip()
    if raw:
        token = raw.split()[0].strip("`*_-").upper()
        if token in _MSN_VALID_STATUSES:
            return token
    raise MissionParseError(
        "Could not extract a valid Mission Status from `**Status:** ...` "
        "(TODO|ACTIVE|COMPLETING|COMPLETE|KILLED|SUPERSEDED)"
    )


def _extract_msn_rollback_plan(body: str) -> dict[str, Any] | None:
    """Extract the Mission §Rollback plan into the v0.2.0 structured shape.

    Two forms are accepted:

    - **v0.2.0 (structured).** A `**Trigger:**` line followed by a fenced
      yaml block of `- name: ... cmd: ...` entries (parallel to
      `mission_verification`). Returns `{trigger, steps}`.
    - **v0.1.0 (legacy prose).** Free-form paragraph. Returned as
      `{trigger: <prose>, steps: [{name: "_legacy_prose", cmd: "echo
      SKIP_LEGACY_ROLLBACK"}]}` so the IR validates against the v0.2.0
      schema while making the legacy shape grep-able for follow-on
      migration. Downstream consumers that try to execute the cmd fail
      loud, not silent.

    Returns None when the section is empty or matches the template
    placeholder text.
    """
    text = body.strip()
    if not text or text.startswith("[Exact mechanism") or text.startswith("["):
        return None

    yaml_match = _INT_FENCED_YAML.search(text)
    steps: list[dict[str, str]] = []
    if yaml_match:
        yaml_body = yaml_match.group(1)
        for m in _INT_VERIF_ENTRY.finditer(yaml_body):
            name = m.group(1).strip().strip("`'\"")
            cmd = m.group(2).strip().strip("`'\"")
            if name and cmd:
                steps.append({"name": name, "cmd": cmd})

    trigger_match = re.search(
        r"\*\*Trigger:\*\*\s*(.+?)(?=\n\n|\n```|\Z)",
        text, re.DOTALL,
    )
    if steps:
        trigger = trigger_match.group(1).strip() if trigger_match else ""
        return {"trigger": trigger, "steps": steps}

    # Legacy prose fallback — wrap into the v0.2.0 shape with a loud
    # placeholder cmd that signals "executor must be human-attended."
    prose = re.sub(r"\s+", " ", text).strip()
    return {
        "trigger": prose,
        "steps": [{
            "name": "_legacy_prose",
            "cmd": "echo SKIP_LEGACY_ROLLBACK",
        }],
    }


def _extract_msn_kill_criteria(body: str) -> list[dict[str, str]]:
    """Extract Mission §Kill criteria into the v0.2.0 structured shape.

    Two forms are accepted:

    - **v0.2.0 (structured).** A fenced yaml block of `- name: ... cmd:
      ...` entries (parallel to `mission_verification`). Returns a list
      of `{name, cmd}` dicts.
    - **v0.1.0 (legacy prose bullets).** Returned as a sibling list of
      `{name: "_legacy_prose_N", cmd: "echo SKIP_LEGACY_KILL"}` entries,
      one per bullet, preserving the prose in `name` so it survives
      round-trip for follow-on migration.

    Returns an empty list when the section is empty.
    """
    if not body.strip():
        return []

    yaml_match = _INT_FENCED_YAML.search(body)
    if yaml_match:
        out: list[dict[str, str]] = []
        yaml_body = yaml_match.group(1)
        for m in _INT_VERIF_ENTRY.finditer(yaml_body):
            name = m.group(1).strip().strip("`'\"")
            cmd = m.group(2).strip().strip("`'\"")
            if name and cmd:
                out.append({"name": name, "cmd": cmd})
        if out:
            return out

    # Legacy prose-bullet fallback.
    bullets = _extract_bullets(body)
    return [
        {
            "name": f"_legacy_prose_{i + 1}: {b}"[:200],
            "cmd": "echo SKIP_LEGACY_KILL",
        }
        for i, b in enumerate(bullets)
    ]


def _extract_msn_flag_strategy(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    fields = {
        "Flag name": "flag_name",
        "Default state during Mission": "default_state",
        "Who flips it on": "who_flips_it_on",
        "Removal plan": "removal_plan",
    }
    for label, key in fields.items():
        m = re.search(
            rf"\*\*{re.escape(label)}:\*\*\s*(.+?)(?=\n[-*]\s*\*\*|\n\n|\Z)",
            body, re.DOTALL,
        )
        if m:
            value = m.group(1).strip().strip("`")
            if value:
                out[key] = value
    return out


def _extract_msn_intent_queue(body: str) -> list[dict[str, str]]:
    rows = _extract_table(body, ["int", "title", "type", "status", "notes"])
    out: list[dict[str, str]] = []
    for r in rows:
        if "int" not in r:
            continue
        entry = {"id": r["int"]}
        for k_in, k_out in [("title", "title"), ("type", "type"),
                             ("status", "status"), ("notes", "notes")]:
            if r.get(k_in):
                entry[k_out] = r[k_in]
        out.append(entry)
    return out


def _extract_msn_prerequisites(body: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith(("- ", "* ")):
            continue
        text = s[2:].strip()
        if not text or text.startswith("["):
            continue
        entry: dict[str, str] = {"text": text}
        src_m = re.search(r"\*\*Source:\*\*\s*([^*\n]+?)(?:\s*—|$)", text)
        if src_m:
            entry["source"] = src_m.group(1).strip()
        res_m = re.search(r"\*\*Resolution:\*\*\s*([^*\n]+?)$", text)
        if res_m:
            entry["resolution"] = res_m.group(1).strip()
        out.append(entry)
    return out


_MSN_AMENDMENT_TYPES = {"activate", "review", "complete", "kill", "supersede", "editorial"}


def _extract_msn_amendment_log(body: str) -> list[dict[str, str]]:
    rows = _extract_table(body, ["date", "type", "change", "author"])
    out: list[dict[str, str]] = []
    for r in rows:
        if "date" not in r or "change" not in r:
            continue
        t = r.get("type", "").strip().lower()
        if t not in _MSN_AMENDMENT_TYPES:
            t = "editorial"
        r["type"] = t
        out.append(r)
    return out


def _load_mission_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("mission")


def _validate_mission(ir: dict[str, Any]) -> None:
    schema = _load_mission_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise MissionParseError(
            "Parsed Mission IR failed schema validation:\n" + "\n".join(msgs)
        )


# --------------------------------------------------------------------------- #
# Domain Glossary IR (singleton at <dekspec-root>/domain-glossary.md)
# --------------------------------------------------------------------------- #


class GlossaryParseError(Exception):
    """Raised when the Domain Glossary fails schema validation."""


def parse_glossary(path: str | Path) -> dict[str, Any]:
    """Parse the singleton domain-glossary.md into a validated IR.

    Walks H2 sections (each is a category) for markdown tables of
    (Term | Canonical Definition | NOT this | Code convention).
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    sections = _split_sections(text)

    ir: dict[str, Any] = {
        "ir_schema_version": IR_SCHEMA_VERSION,
        "id": "DOMAIN-GLOSSARY",
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "terms": [],
    }
    warnings: list[dict[str, str]] = []

    _maybe_set(ir, "created", _extract_first_date(sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(sections.get("Modified", "")))
    purpose = sections.get("Purpose", "").strip()
    if purpose:
        ir["purpose"] = purpose

    skip_categories = {"Created", "Modified", "Purpose", "Amendment Log",
                       "Status", "Source"}
    categories_seen = 0
    for category, body in sections.items():
        if category in skip_categories:
            continue
        categories_seen += 1
        rows = _extract_table(
            body,
            ["term", "canonical_definition", "not_this", "code_convention", "aliases"],
        )
        for row in rows:
            term = (row.get("term") or "").strip().strip("`*_")
            if not term or term.lower() in {"term", "---"}:
                if row.get("canonical_definition", "").strip():
                    warnings.append({
                        "field": f"terms[{category}]",
                        "reason": (
                            "Skipped a row with a definition but no term value — "
                            "check that the first column is non-empty."
                        ),
                        "severity": "warning",
                    })
                continue
            entry: dict[str, Any] = {"term": term, "category": category}
            for k in ("canonical_definition", "not_this", "code_convention"):
                v = (row.get(k) or "").strip()
                if v:
                    entry[k] = v
            aliases_raw = (row.get("aliases") or "").strip()
            if aliases_raw:
                aliases = [
                    a.strip().strip("`*_")
                    for a in aliases_raw.split(",")
                    if a.strip()
                ]
                if aliases:
                    entry["aliases"] = aliases
            if "canonical_definition" not in entry:
                warnings.append({
                    "field": f"terms[{term}].canonical_definition",
                    "reason": (
                        "Term has no canonical_definition — schema will reject "
                        "as required field unless the table is corrected."
                    ),
                    "severity": "warning",
                })
            ir["terms"].append(entry)

    if not ir["terms"]:
        # Fallback: look for a markdown table directly under the H1 (no H2
        # categories used). Common shape for small projects that don't need
        # category groupings — see ds-47c / DIV-011.
        prelude_lines: list[str] = []
        for line in text.splitlines():
            if re.match(r"^##\s+", line):
                break
            prelude_lines.append(line)
        prelude = "\n".join(prelude_lines)
        prelude_rows = _extract_table(
            prelude,
            ["term", "canonical_definition", "not_this", "code_convention", "aliases"],
        )
        if prelude_rows:
            fallback_category = "Terms"
            for row in prelude_rows:
                term = (row.get("term") or "").strip().strip("`*_")
                if not term or term.lower() in {"term", "---"}:
                    if row.get("canonical_definition", "").strip():
                        warnings.append({
                            "field": f"terms[{fallback_category}]",
                            "reason": (
                                "Skipped a row with a definition but no term value — "
                                "check that the first column is non-empty."
                            ),
                            "severity": "warning",
                        })
                    continue
                entry: dict[str, Any] = {"term": term, "category": fallback_category}
                for k in ("canonical_definition", "not_this", "code_convention"):
                    v = (row.get(k) or "").strip()
                    if v:
                        entry[k] = v
                aliases_raw = (row.get("aliases") or "").strip()
                if aliases_raw:
                    aliases = [
                        a.strip().strip("`*_")
                        for a in aliases_raw.split(",")
                        if a.strip()
                    ]
                    if aliases:
                        entry["aliases"] = aliases
                ir["terms"].append(entry)

    if not ir["terms"]:
        warnings.append({
            "field": "terms",
            "reason": (
                "Glossary parses but has zero terms — either every category "
                "table is empty, or no H2 categories were found."
                if categories_seen
                else "No H2 category sections found and no top-level term table "
                     "was found under the H1 — glossary structure requires either "
                     "at least one H2 with a markdown table, or a top-level table "
                     "directly under the H1."
            ),
            "severity": "warning",
        })

    if warnings:
        ir["parse_warnings"] = warnings
    _validate_glossary(ir)
    return ir


def _load_glossary_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("domain_glossary")


def _validate_glossary(ir: dict[str, Any]) -> None:
    schema = _load_glossary_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise GlossaryParseError(
            "Parsed Domain Glossary IR failed schema validation:\n" + "\n".join(msgs)
        )


# --------------------------------------------------------------------------- #
# System Vision IR (singleton at <dekspec-root>/system-vision.md)
# --------------------------------------------------------------------------- #

_VISION_H1 = re.compile(r"^#\s+(?:System\s+Vision:\s*)?(.+?)\s*$", re.MULTILINE)
_VISION_NOTE_H1 = re.compile(r"^#\s+Vision\s+Note:\s*", re.MULTILINE)


class VisionParseError(Exception):
    """Raised when the System Vision fails schema validation."""


def parse_vision(path: str | Path) -> dict[str, Any]:
    """Parse the singleton system-vision.md into a validated IR."""
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    sections = _split_sections(text)

    ir: dict[str, Any] = {
        "ir_schema_version": IR_SCHEMA_VERSION,
        "id": "SYSTEM-VISION",
        "name": _extract_vision_name(text),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
    warnings: list[dict[str, str]] = []

    status_body = sections.get("Status", "")
    for line in status_body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        token = s.split()[0].strip("`*_-").upper()
        if token in {"TODO", "DRAFT", "PROPOSED", "ACCEPTED", "LOCKED", "DEPRECATED"}:
            ir["status"] = token
            break

    _maybe_set(ir, "created", _extract_first_date(sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(sections.get("Modified", "")))

    # Preamble: text between H1 and first H2.
    h1_end = text.find("\n", text.find("# "))
    first_h2 = text.find("\n## ", h1_end if h1_end != -1 else 0)
    if first_h2 != -1:
        preamble = text[h1_end:first_h2].strip()
        if preamble:
            ir["preamble"] = preamble
        else:
            warnings.append({
                "field": "preamble",
                "reason": (
                    "No preamble text between the H1 and the first H2 — the "
                    "convention is a one-paragraph elevator pitch before "
                    "'## What This Is'."
                ),
                "severity": "info",
            })
    else:
        warnings.append({
            "field": "preamble",
            "reason": (
                "Document has no H2 sections — System Vision requires the "
                "five sections: What This Is, Who This Is For, Why This "
                "Exists, What Success Looks Like, What We Are Not Building."
            ),
            "severity": "warning",
        })

    section_field_map = {
        "What This Is": "what_this_is",
        "Who This Is For": "who_this_is_for",
        "Why This Exists": "why_this_exists",
    }
    for section, key in section_field_map.items():
        body = sections.get(section, "").strip()
        if body:
            ir[key] = body
        elif section in sections:
            # Header is present but body is empty — surface this as a warning
            # (schema validation will catch genuinely-missing required sections).
            warnings.append({
                "field": key,
                "reason": (
                    f"Section '## {section}' present but empty — schema will "
                    f"reject the IR as missing required field {key!r}."
                ),
                "severity": "warning",
            })

    success = _extract_bullets(sections.get("What Success Looks Like", ""))
    if success:
        ir["what_success_looks_like"] = success
    elif "What Success Looks Like" in sections:
        warnings.append({
            "field": "what_success_looks_like",
            "reason": (
                "Section '## What Success Looks Like' present but contains no "
                "bulleted items — use markdown '- ' bullets to enumerate the "
                "success criteria."
            ),
            "severity": "warning",
        })

    not_building = _extract_bullets(sections.get("What We Are Not Building", ""))
    if not_building:
        ir["what_we_are_not_building"] = not_building
    elif "What We Are Not Building" in sections:
        warnings.append({
            "field": "what_we_are_not_building",
            "reason": (
                "Section '## What We Are Not Building' present but contains no "
                "bulleted items — list the explicit out-of-scope items as "
                "'- ' bullets."
            ),
            "severity": "warning",
        })

    if warnings:
        ir["parse_warnings"] = warnings
    _validate_vision(ir)
    return ir


def _extract_vision_name(text: str) -> str:
    if _VISION_NOTE_H1.search(text):
        raise VisionParseError(
            "H1 uses 'Vision Note:' prefix — System Vision is a singleton with "
            "id SYSTEM-VISION. Use '# System Vision: <Name>' or a plain '# <Name>' "
            "H1. Subsystem-level Vision Notes are not a supported IR."
        )
    m = _VISION_H1.search(text)
    if not m:
        raise VisionParseError("Missing or malformed H1 in system-vision.md")
    return m.group(1).strip()


def _load_vision_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("system_vision")


def _validate_vision(ir: dict[str, Any]) -> None:
    schema = _load_vision_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: e.absolute_path)
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise VisionParseError(
            "Parsed System Vision IR failed schema validation:\n" + "\n".join(msgs)
        )


# --------------------------------------------------------------------------- #
# Constitution IR (singleton at <dekspec-root>/constitution.md)
# --------------------------------------------------------------------------- #
#
# Constitution is the third L0 singleton (after System Vision + Domain
# Glossary). The 8 articles are positional + their kinds are fixed by
# schema; the parser walks H2 sections matching '## Article N: <Title>'
# in canonical order and dispatches per-article-kind handlers. The
# round-trip emitter (`emit_constitution_markdown`) is the inverse and
# is what makes WS-004 BR6 byte-stability verifiable.

_CONSTITUTION_H1 = re.compile(r"^#\s+Constitution:\s*(.+?)\s*$", re.MULTILINE)
_ARTICLE_HEADING = re.compile(r"^##\s+Article\s+(\d+):\s+(.+?)\s*$", re.MULTILINE)
# Labelled-paragraph regexes: use [ \t]+ instead of \s* so `\s` doesn't
# eat the newline and greedily match the next labelled line's value.
# `(.+)` (not `.+?`) captures the full rest of the line; `$` is per-line
# under re.MULTILINE.
_POINTER_SUMMARY = re.compile(r"^\*\*Summary:\*\*[ \t]+(.+)$", re.MULTILINE)
_POINTER_SEE_ALSO = re.compile(r"^\*\*See\s+Also:\*\*[ \t]+(.+)$", re.MULTILINE)
# `_REF_BULLET` matches the strict canonical shape (ADR-NNN / AE-NNN).
# `_REF_BULLET_ANY` is a wider net that catches any `- token — text`
# bullet, used to detect malformed IDs that should reject the parse.
_REF_BULLET = re.compile(
    r"^-\s+(ADR-\d{3,}|AE-\d{3,})\s+—\s+(.+?)\s*$", re.MULTILINE
)
_REF_BULLET_ANY = re.compile(r"^-\s+(\S+)\s+—", re.MULTILINE)

# (index 0-based, title, kind). Pinned by schema's prefixItems and
# enforced positionally by the parser.
_CONSTITUTION_ARTICLES: tuple[tuple[str, str], ...] = (
    ("Project Identity", "pointer"),
    ("Technology Stack", "text"),
    ("Quality Standards", "text"),
    ("Architecture Principles", "ref-array"),
    ("Development Workflow", "text"),
    ("Model Configuration", "text"),
    ("Boundaries", "ref-array"),
    ("Amendments", "text"),
)


class ConstitutionParseError(Exception):
    """Raised when constitution.md fails parsing or schema validation."""


def parse_constitution(path: str | Path) -> dict[str, Any]:
    """Parse the singleton constitution.md into a validated IR.

    Walks H2 sections matching `^## Article N: <Title>$` in canonical
    order; dispatches per-kind handlers (pointer / ref-array / text);
    validates the assembled dict against `constitution.schema.yaml`.
    Mirrors parse_glossary / parse_vision shape per ADR-003.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")

    article_blocks = _extract_article_blocks(text)
    if len(article_blocks) != 8:
        raise ConstitutionParseError(
            f"Expected exactly 8 articles, found {len(article_blocks)}. "
            f"Constitution articles must use the heading shape "
            f"'## Article N: <Title>' in canonical order."
        )

    articles: list[dict[str, Any]] = []
    for i, (idx, title, body) in enumerate(article_blocks):
        expected_idx = i + 1
        expected_title, expected_kind = _CONSTITUTION_ARTICLES[i]
        if idx != expected_idx:
            raise ConstitutionParseError(
                f"Article at position {i + 1} has heading "
                f"'Article {idx}: ...', expected "
                f"'Article {expected_idx}: {expected_title}'."
            )
        if title != expected_title:
            raise ConstitutionParseError(
                f"Article {idx} has title {title!r}, expected "
                f"{expected_title!r}. The eight article titles are "
                f"pinned by schema and must appear verbatim."
            )
        if expected_kind == "pointer":
            articles.append(_parse_pointer_article(body, expected_title))
        elif expected_kind == "ref-array":
            articles.append(_parse_ref_array_article(body, expected_title, idx))
        else:
            articles.append(_parse_text_article(body, expected_title))

    name_match = _CONSTITUTION_H1.search(text)
    if not name_match:
        raise ConstitutionParseError(
            "Missing or malformed H1 in constitution.md — expected "
            "'# Constitution: <name>'."
        )
    name = name_match.group(1).strip()

    sections = _split_sections(text)
    ir: dict[str, Any] = {
        "ir_schema_version": IR_SCHEMA_VERSION,
        "id": "CONSTITUTION",
        "name": name,
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "articles": articles,
    }

    status_body = sections.get("Status", "")
    for line in status_body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        token = s.split()[0].strip("`*_-").upper()
        if token in {"TODO", "DRAFT", "PROPOSED", "ACCEPTED", "LOCKED", "DEPRECATED"}:
            ir["status"] = token
            break

    _maybe_set(ir, "created", _extract_first_date(sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(sections.get("Modified", "")))

    # Preamble: text between H1 and first H2.
    h1_end = text.find("\n", text.find("# "))
    first_h2 = text.find("\n## ", h1_end if h1_end != -1 else 0)
    if first_h2 != -1:
        preamble = text[h1_end:first_h2].strip()
        if preamble:
            ir["preamble"] = preamble

    _validate_constitution(ir)
    return ir


def _extract_article_blocks(text: str) -> list[tuple[int, str, str]]:
    """Return [(article_number, title, body), ...] in document order.

    Walks the text top-to-bottom collecting only `## Article N: <Title>`
    H2s; other H2s (e.g., Status, Created) are not articles. Each
    article's body runs from the line after its heading to the line
    before the next H2 (article or non-article) or end of text.
    """
    blocks: list[tuple[int, str, str]] = []
    headings: list[tuple[int, int, str]] = []  # (start_offset, number, title)

    # First pass: find all article headings + their offsets.
    for m in _ARTICLE_HEADING.finditer(text):
        headings.append((m.start(), int(m.group(1)), m.group(2)))

    # For each article, body runs from end-of-its-heading-line to the
    # start of the NEXT H2 (article or otherwise) or end-of-text.
    h2_starts = [m.start() for m in re.finditer(r"^##\s+", text, re.MULTILINE)]
    for start, num, title in headings:
        heading_line_end = text.find("\n", start)
        if heading_line_end == -1:
            body_start = len(text)
        else:
            body_start = heading_line_end + 1
        next_h2 = min(
            (s for s in h2_starts if s > start), default=len(text)
        )
        body = text[body_start:next_h2].rstrip("\n")
        blocks.append((num, title, body))
    return blocks


def _parse_pointer_article(body: str, title: str) -> dict[str, Any]:
    """Article 1 (pointer): extract **Summary:** and **See Also:**.

    Both labelled paragraphs must be present on their own line with at
    least one non-newline whitespace separator before the value. An
    empty value (label followed by EOL with no content) fails to match
    and raises ConstitutionParseError.
    """
    summary_match = _POINTER_SUMMARY.search(body)
    see_also_match = _POINTER_SEE_ALSO.search(body)
    if summary_match is None:
        raise ConstitutionParseError(
            f"Article 1 ({title!r}) is missing the **Summary:** labelled "
            f"paragraph (or its value is empty); pointer-kind articles "
            f"require both **Summary:** <text> and **See Also:** <path>."
        )
    if see_also_match is None:
        raise ConstitutionParseError(
            f"Article 1 ({title!r}) is missing the **See Also:** labelled "
            f"paragraph (or its value is empty); pointer-kind articles "
            f"require both **Summary:** <text> and **See Also:** <path>."
        )
    return {
        "kind": "pointer",
        "title": title,
        "summary": summary_match.group(1).strip(),
        "see_also": see_also_match.group(1).strip(),
    }


def _parse_ref_array_article(
    body: str, title: str, article_number: int
) -> dict[str, Any]:
    """Articles 4 (Architecture Principles) + 7 (Boundaries): extract
    typed ref bullets. Article 4 has only adr_refs; Article 7 has both
    adr_refs + ae_refs (parsed by ID prefix). Canonical bullet shape:
    `- (ADR|AE)-NNN — <text>`.

    Bullets that look like `- IDENTIFIER — text` but whose IDENTIFIER
    fails the strict ID pattern (ADR/AE-NNN) raise
    ConstitutionParseError — silently skipping them would let
    malformed-ID typos slide and produce empty ref arrays that pass
    schema validation.
    """
    # First pass: catch malformed bullets (bullet shape matches but the
    # token isn't a valid ADR/AE-NNN). This is a structural defect, not
    # a content/lint warning.
    for m in _REF_BULLET_ANY.finditer(body):
        token = m.group(1)
        if not (
            re.fullmatch(r"ADR-\d{3,}", token)
            or re.fullmatch(r"AE-\d{3,}", token)
        ):
            raise ConstitutionParseError(
                f"Article {article_number} ({title!r}) contains a bullet "
                f"with malformed ref ID {token!r}; expected pattern "
                f"^ADR-\\d{{3,}}$ or ^AE-\\d{{3,}}$ for the typed refs."
            )

    adr_refs: list[dict[str, str]] = []
    ae_refs: list[dict[str, str]] = []
    for m in _REF_BULLET.finditer(body):
        ref_id = m.group(1)
        text_val = m.group(2).strip()
        if ref_id.startswith("ADR-"):
            adr_refs.append({"id": ref_id, "rationale": text_val})
        elif ref_id.startswith("AE-"):
            ae_refs.append({"id": ref_id, "aspect": text_val})
    out: dict[str, Any] = {
        "kind": "ref-array",
        "title": title,
        "adr_refs": adr_refs,
    }
    if article_number == 7:
        out["ae_refs"] = ae_refs
    return out


def _parse_text_article(body: str, title: str) -> dict[str, Any]:
    """Articles 2/3/5/6/8: opaque markdown body, leading/trailing
    whitespace trimmed."""
    return {
        "kind": "text",
        "title": title,
        "body": body.strip(),
    }


def emit_constitution_markdown(ir: dict[str, Any]) -> str:
    """Round-trip emitter — inverse of `parse_constitution`.

    Produces a markdown document that, when read and re-parsed, yields
    an IR semantically equivalent to the input. For fixtures authored
    in this emitter's canonical style, `emit(parse(p)) == read(p)` is
    byte-equal (WS-004 BR6).

    The emitter's output style is the canonical reference — fixtures
    and the library's own constitution.md should be authored to match
    this output exactly.
    """
    name = ir.get("name", "Untitled")
    parts: list[str] = [f"# Constitution: {name}\n"]

    preamble = ir.get("preamble")
    if preamble:
        parts.append(f"\n{preamble}\n")

    status = ir.get("status")
    if status:
        parts.append(f"\n## Status\n\n{status}\n")
    created = ir.get("created")
    if created:
        parts.append(f"\n## Created\n\n{created}\n")
    modified = ir.get("modified")
    if modified:
        parts.append(f"\n## Modified\n\n{modified}\n")

    for i, article in enumerate(ir.get("articles", [])):
        idx = i + 1
        title = article["title"]
        parts.append(f"\n## Article {idx}: {title}\n\n")
        kind = article["kind"]
        if kind == "pointer":
            parts.append(f"**Summary:** {article['summary']}\n\n")
            parts.append(f"**See Also:** {article['see_also']}\n")
        elif kind == "ref-array":
            adr_refs = article.get("adr_refs", [])
            ae_refs = article.get("ae_refs", [])
            if idx == 7:
                # Article 7 renders the two arrays under labelled
                # sub-headings to keep them visually distinct.
                parts.append("**Boundary ADRs:**\n\n")
                for ref in adr_refs:
                    parts.append(f"- {ref['id']} — {ref['rationale']}\n")
                parts.append("\n**Boundary AEs:**\n\n")
                for ref in ae_refs:
                    parts.append(f"- {ref['id']} — {ref['aspect']}\n")
            else:
                for ref in adr_refs:
                    parts.append(f"- {ref['id']} — {ref['rationale']}\n")
        else:  # text
            parts.append(f"{article['body']}\n")

    return "".join(parts)


def _load_constitution_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("constitution")


def _validate_constitution(ir: dict[str, Any]) -> None:
    schema = _load_constitution_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise ConstitutionParseError(
            "Parsed Constitution IR failed schema validation:\n" + "\n".join(msgs)
        )


# =========================================================================== #
# Security Profile parser (10th IR kind — ADR-011 Option B)
#
# Multi-instance L2 artifact at <dekspec-root>/security-profiles/SP-NNN-*.md.
# Parser is purely additive: it does NOT modify or share scaffolding with any
# existing parse_* function, and it carries ZERO references to the WS-symbol
# set per ADR-011 Option B § Validation predicate. Asserted by
# tests/test_security_profile_parser.py::test_adr_011_conformance_zero_ws_coupling.
# =========================================================================== #

_SP_FILENAME = re.compile(r"^(SP-\d{3,})-.+\.md$")
_SP_H1_TITLE = re.compile(
    r"^#\s+(?:Security Profile:\s*)?(.+?)\s*$", re.MULTILINE
)
_SP_IR_SCHEMA_VERSION = "0.1.0"
_SP_VALID_STATUSES = {"PROPOSED", "ACCEPTED", "LOCKED", "SUPERSEDED"}


class SPParseError(Exception):
    """Raised when a Security Profile markdown fails parsing or schema validation."""


def parse_security_profile(path: str | Path) -> dict[str, Any]:
    """Parse a Security Profile markdown file into a validated IR.

    Walks H2 sections of the markdown; extracts the twelve documented fields
    (id from filename; title from H1; status / bounded_context / six typed-
    record arrays / supply_chain.allowed_sources from per-field H2 sections);
    attaches provenance; validates the assembled dict against
    `security-profile.schema.yaml`.

    Raises SPParseError on schema-validation failure (wraps the underlying
    jsonschema.ValidationError messages); re-raises OSError /
    UnicodeDecodeError from the file read unchanged.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    sections = _split_sections(text)

    ir: dict[str, Any] = {
        "ir_schema_version": _SP_IR_SCHEMA_VERSION,
        "id": _extract_sp_id(src.name),
        "title": _extract_sp_title(text),
        "status": _extract_sp_status(sections),
        "allowed_dataflows": _extract_sp_allowed_dataflows(
            sections.get("Allowed Dataflows", "")
        ),
        "secret_stores": _extract_sp_secret_stores(
            sections.get("Secret Stores", "")
        ),
        "authn_methods": _extract_sp_authn_methods(
            sections.get("Authn Methods", "")
        ),
        "supply_chain": _extract_sp_supply_chain(
            sections.get("Supply Chain", "")
        ),
        "sast_tools": _extract_sp_sast_tools(
            sections.get("SAST Tools", "")
        ),
        "dast_tools": _extract_sp_dast_tools(
            sections.get("DAST Tools", "")
        ),
        "owasp_coverage": _extract_sp_owasp_coverage(
            sections.get("OWASP Coverage", "")
        ),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    bounded_context = _extract_sp_bounded_context(sections)
    if bounded_context is not None:
        ir["bounded_context"] = bounded_context

    _maybe_set(ir, "created", _extract_first_date(sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(sections.get("Modified", "")))

    _validate_security_profile(ir)
    return ir


def _extract_sp_id(filename: str) -> str:
    m = _SP_FILENAME.match(filename)
    if not m:
        if _draft_id_or_none(filename) is not None:
            raise DraftArtifactError(
                f"{filename} is a DRAFT artifact (SP-DRAFT-<slug>); allocate a "
                f"canonical ID with `dekspec id allocate` before parsing."
            )
        raise SPParseError(
            f"Filename does not match SP-NNN-*.md pattern: {filename}"
        )
    return m.group(1)


def _extract_sp_title(text: str) -> str:
    m = _SP_H1_TITLE.search(text)
    if not m:
        raise SPParseError(
            "Missing or malformed H1 — expected '# Security Profile: <title>' "
            "or '# <title>'."
        )
    return m.group(1).strip()


def _extract_sp_status(sections: dict[str, str]) -> str:
    body = sections.get("Status", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        # First non-decoration token — passed through verbatim (no .upper()
        # casefold) so the schema enum can reject mixed-case typos like
        # `proposed` cleanly.
        token = s.split()[0].strip("`*_-")
        if token:
            return token
    raise SPParseError(
        "Could not extract a Status value — expected '## Status' section "
        "with a token from {PROPOSED, ACCEPTED, LOCKED, SUPERSEDED}."
    )


def _extract_sp_bounded_context(sections: dict[str, str]) -> str | None:
    body = sections.get("Bounded Context", "")
    if not body.strip():
        return None
    # Treat the first non-empty non-decoration line as the value. Empty body
    # → return None (absent = singleton case); non-empty → return as-is so a
    # whitespace-only value can still be schema-rejected via minLength.
    for line in body.splitlines():
        s = line.strip()
        if s and not s.startswith("*"):
            return s
    return None


def _extract_sp_allowed_dataflows(body: str) -> list[dict[str, str]]:
    return _extract_table(body, ["name", "source", "sink", "classification"])


def _extract_sp_secret_stores(body: str) -> list[dict[str, str]]:
    return _extract_table(body, ["name", "kind", "scope"])


def _extract_sp_authn_methods(body: str) -> list[dict[str, str]]:
    return _extract_table(body, ["name", "kind", "scope"])


def _extract_sp_supply_chain(body: str) -> dict[str, Any]:
    # The supply_chain object is REQUIRED at schema level even when the
    # section is absent or empty — return the canonical empty shape so
    # downstream validators surface the missing-section condition through a
    # consistent IR rather than an exception spike here.
    return {"allowed_sources": _extract_bullets(body)}


def _extract_sp_sast_tools(body: str) -> list[dict[str, str]]:
    return _extract_table(body, ["name", "language", "ruleset"])


def _extract_sp_dast_tools(body: str) -> list[dict[str, str]]:
    return _extract_table(body, ["name", "target", "schedule"])


def _extract_sp_owasp_coverage(body: str) -> list[dict[str, str]]:
    return _extract_table(
        body, ["owasp_id", "mitigation_strategy", "mapped_tool"]
    )


def _load_security_profile_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("security_profile")


def _validate_security_profile(ir: dict[str, Any]) -> None:
    schema = _load_security_profile_schema()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise SPParseError(
            "Parsed Security Profile IR failed schema validation:\n"
            + "\n".join(msgs)
        )


# --------------------------------------------------------------------------- #
# ContextSpec IR (IB-124 / INT-139, MSN-019 daughter A)
#
# The 11th DekSpec IR kind — generalizes the dekfactory Phase 0 prototype
# reviewer_context_spec.schema.json into a first-class, parser-validated,
# ID-addressable IR. Additive per ADR-011 Option B: zero edits to any existing
# parse_* function or shared helper; no references to WS or Security-Profile
# internals. The one shape divergence from parse_security_profile: `id` is
# sourced from the `## ID` body section (the canonical filename is role-keyed,
# `role-<role>.md`, not ID-keyed), not from the filename.
# --------------------------------------------------------------------------- #

_CS_IR_SCHEMA_VERSION = "0.1.0"
_CS_ID_RE = re.compile(r"\bCS-\d{3,}\b")
_CS_H1_TITLE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


class CSParseError(Exception):
    """Raised when a ContextSpec markdown fails parsing or schema validation."""


def parse_context_spec(path: str | Path) -> dict[str, Any]:
    """Parse a ContextSpec markdown file into a validated IR.

    Walks H2 sections of the markdown; extracts id from the `## ID` body
    section (NOT the filename — the canonical filename is role-keyed,
    `role-<role>.md`); title from H1; status / role_identity from per-field H2
    sections; the four input-scoping fields (artifact_path_scope,
    schema_fragment_scope, glossary_subset_scope, escalation_triggers) via
    per-field `_extract_cs_*` helpers; attaches provenance; validates the
    assembled dict against `context-spec.schema.yaml`.

    Raises CSParseError on schema-validation failure (wraps the underlying
    jsonschema.ValidationError messages); re-raises OSError /
    UnicodeDecodeError from the file read unchanged.
    """
    src = Path(path).resolve()
    text = src.read_text(encoding="utf-8")
    sections = _split_sections(text)

    ir: dict[str, Any] = {
        "ir_schema_version": _CS_IR_SCHEMA_VERSION,
        "id": _extract_cs_id(sections),
        "title": _extract_cs_title(text),
        "status": _extract_cs_status(sections),
        "role_identity": _extract_cs_role_identity(sections),
        "artifact_path_scope": _extract_cs_scope(
            sections.get("Artifact Path Scope", "")
        ),
        "schema_fragment_scope": _extract_cs_scope(
            sections.get("Schema Fragment Scope", "")
        ),
        "glossary_subset_scope": _extract_cs_scope(
            sections.get("Glossary Subset Scope", "")
        ),
        "escalation_triggers": _extract_cs_escalation_triggers(
            sections.get("Escalation Triggers", "")
        ),
        "source": {
            "path": str(src),
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "parser_version": PARSER_VERSION,
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }

    _maybe_set(ir, "created", _extract_first_date(sections.get("Created", "")))
    _maybe_set(ir, "modified", _extract_first_date(sections.get("Modified", "")))

    _validate_context_spec(ir)
    return ir


def _extract_cs_id(sections: dict[str, str]) -> str:
    body = sections.get("ID", "")
    m = _CS_ID_RE.search(body)
    if not m:
        raise CSParseError(
            "Could not extract a ContextSpec id — expected a '## ID' section "
            "with a token matching CS-NNN (id lives in the body, not the "
            "role-keyed filename)."
        )
    return m.group(0)


def _extract_cs_title(text: str) -> str:
    m = _CS_H1_TITLE.search(text)
    if not m:
        raise CSParseError(
            "Missing or malformed H1 — expected '# <title>'."
        )
    return m.group(1).strip()


def _extract_cs_status(sections: dict[str, str]) -> str:
    body = sections.get("Status", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        # First non-decoration token — passed through verbatim (no casefold)
        # so the schema enum rejects mixed-case typos like `proposed` cleanly.
        token = s.split()[0].strip("`*_-")
        if token:
            return token
    raise CSParseError(
        "Could not extract a Status value — expected '## Status' section with "
        "a token from {PROPOSED, ACCEPTED, LOCKED, SUPERSEDED}."
    )


def _extract_cs_role_identity(sections: dict[str, str]) -> str:
    body = sections.get("Role Identity", "")
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        token = s.split()[0].strip("`*_-")
        if token:
            return token
    raise CSParseError(
        "Could not extract a Role Identity value — expected '## Role Identity' "
        "section with one of {specifier, spec-reviewer, implementer, "
        "code-reviewer, verifier, auditor}."
    )


def _extract_cs_scope(body: str) -> list[str]:
    """Extract a bullet-list input-scoping field (strips surrounding backticks
    from each item; empty list when the section is absent or empty)."""
    return [item.strip("`").strip() for item in _extract_bullets(body) if item.strip()]


def _extract_cs_escalation_triggers(body: str) -> list[dict[str, str]]:
    """Parse the `## Escalation Triggers` bullets into closed (condition,
    action) rows. Each bullet is `condition: <c> | action: <a>`."""
    rows: list[dict[str, str]] = []
    for bullet in _extract_bullets(body):
        parts = [p.strip() for p in bullet.split("|")]
        fields: dict[str, str] = {}
        for part in parts:
            if ":" not in part:
                continue
            key, _, value = part.partition(":")
            key = key.strip().lower()
            if key in ("condition", "action"):
                fields[key] = value.strip()
        if "condition" in fields and "action" in fields:
            rows.append({"condition": fields["condition"], "action": fields["action"]})
    return rows


def _validate_context_spec(ir: dict[str, Any]) -> None:
    from ..schemas import load_schema as _load

    schema = _load("context_spec")
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(ir), key=lambda e: list(e.absolute_path))
    if errors:
        msgs = []
        for e in errors:
            ptr = "/" + "/".join(str(p) for p in e.absolute_path)
            msgs.append(f"  {ptr}: {e.message}")
        raise CSParseError(
            "Parsed ContextSpec IR failed schema validation:\n" + "\n".join(msgs)
        )
