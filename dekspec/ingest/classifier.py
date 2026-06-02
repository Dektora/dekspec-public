"""Deterministic heuristic classifier for the `dekspec ingest` pipeline.

This module is the foundation of INT-059's brownfield-ingest command (IB-097).
It does three things:

1. **Markdown sectioning** — `section_document` splits a markdown document
   string into ordered `Section` records on ATX-style headings.
2. **The deterministic heuristic classifier** — `classify` sections the
   document and routes each section to a DekSpec IR type via three independent
   rule families (header-match, keyword-match, structural-pattern), combining
   the agreeing signals into a confidence score.
3. **The rule set** — header-match / keyword-match / structural-pattern rules
   expressed as ordered data structures, plus the agreement-based scoring.

There is **no LLM call, no network call, and no nondeterminism** anywhere in
this module. `classify(doc)` is referentially transparent — the same document
string always produces a byte-identical `list[Classification]`. An
LLM-assisted mode is explicitly deferred to a future bead (INT-059 OI-1).

The classifier is a pure function: it operates on an in-memory `str`. File
reading (opening the `<path>` CLI argument) is the CLI layer's job in IB-098;
this module never touches the filesystem.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# --------------------------------------------------------------------------
# IR-type routing vocabulary
# --------------------------------------------------------------------------


class IRKind(Enum):
    """The DekSpec IR types a source section can be classified into.

    This enum is the single source of truth for the routing vocabulary.
    IB-098's draft-artifact emitter switches on these members. `UNCLASSIFIED`
    is the explicit member for a section no rule family confidently matched.
    """

    AE_RESPONSIBILITY = "ae_responsibility"
    ADR_CONTEXT = "adr_context"
    ADR_DECISION = "adr_decision"
    ADR_CONSEQUENCES = "adr_consequences"
    WS_BUSINESS_RULE = "ws_business_rule"
    UNCLASSIFIED = "unclassified"


# Fixed IR-type precedence — breaks ties when two IR kinds tie on vote weight.
# Documented order: header-bearing decision content is the most specific
# signal, then the rest of the ADR slots, then AE responsibility, then WS
# business rules. `UNCLASSIFIED` is never a tie-break winner — it is only
# chosen when no family fires at all.
_IR_PRECEDENCE: tuple[IRKind, ...] = (
    IRKind.ADR_DECISION,
    IRKind.ADR_CONTEXT,
    IRKind.ADR_CONSEQUENCES,
    IRKind.AE_RESPONSIBILITY,
    IRKind.WS_BUSINESS_RULE,
)


# --------------------------------------------------------------------------
# Data types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    """One markdown section of an ingested document.

    A section runs from its ATX heading to the next heading of equal-or-higher
    level. Content before the first heading is a single `Section` with
    `level == 0` and an empty `heading`.
    """

    heading: str
    """The heading text, stripped of `#` markers and surrounding whitespace.

    Empty string for the pre-first-heading preamble section.
    """

    level: int
    """The markdown heading level (1 for `#`, 2 for `##`, ...).

    `0` for the pre-heading preamble section.
    """

    body: str
    """The section body — everything between this heading and the next heading
    of equal-or-higher level, excluding the heading line itself."""

    order: int
    """Zero-based position of the section in source order."""


@dataclass(frozen=True)
class Classification:
    """The classifier's routing decision for one `Section`.

    `signals` is the explainability surface: every rule that fired appends a
    short human-readable string here, so IB-098's report can show a reviewer
    *why* a section was classified the way it was. An `UNCLASSIFIED` section
    carries a single `"no rule matched"` signal.
    """

    section: Section
    ir_kind: IRKind
    confidence: float
    """Float in the closed range `[0.0, 1.0]`."""

    signals: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# Confidence scoring constants
# --------------------------------------------------------------------------
#
# Scoring is agreement-based: a header-match is the strongest single signal,
# keyword and structural matches are supporting signals. The score for the
# chosen IR kind starts from a base for its strongest firing family and adds a
# fixed increment for each additional independent family that agreed, then is
# clamped to [0.0, 1.0]. The numbers below are an implementation choice
# (IB-097 OI-1); they are named constants with a one-line rationale and they
# satisfy the IB's Golden I/O (three agreeing families > one family; an
# unmatched section scores exactly 0.0).

_HEADER_BASE = 0.60
"""Base score when a header-match is the strongest firing family — a literal
heading name is the most reliable single routing signal."""

_KEYWORD_BASE = 0.40
"""Base score when keyword-match (but no header-match) is the strongest family
— body phrasing alone is a moderate signal."""

_STRUCTURE_BASE = 0.35
"""Base score when a structural-pattern match (but no header-match and no
keyword-match) is the strongest family — shape alone is the weakest base."""

_AGREEMENT_INCREMENT = 0.20
"""Added once per *additional* rule family that agreed with the chosen IR kind
beyond the strongest one — independent agreement raises confidence."""


# --------------------------------------------------------------------------
# Markdown sectioning
# --------------------------------------------------------------------------

# ATX headings only (`#`, `##`, ...). Setext-style (`===` underline) headings
# are intentionally NOT parsed at MVP — ATX is the dominant style in the
# brownfield documents this command targets, and ATX detection is exact.
_ATX_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _normalize(document: str) -> str:
    """Normalize line endings: CRLF and lone CR both become LF."""
    return document.replace("\r\n", "\n").replace("\r", "\n")


def section_document(document: str) -> list[Section]:
    """Split a markdown document string into ordered `Section` records.

    Each ATX heading opens a new `Section`; its `body` is every line from the
    heading down to the next ATX heading (of any level), exclusive of the
    heading lines themselves. A nested sub-heading therefore opens its own
    `Section` rather than being folded into its parent's body — this keeps
    sectioning a flat, deterministic split with one `Classification` emitted
    per heading in source order.

    Content before the first ATX heading becomes one `Section` with
    `level == 0` and an empty `heading`. The returned list is in source order.
    This function is deterministic.
    """
    lines = _normalize(document).split("\n")

    # First pass: collect (level, heading_text, body_lines) blocks, with any
    # pre-heading preamble as a level-0 block.
    raw_blocks: list[tuple[int, str, list[str]]] = []
    preamble: list[str] = []
    current: tuple[int, str, list[str]] | None = None
    preamble_flushed = False

    for line in lines:
        match = _ATX_HEADING_RE.match(line)
        if match:
            if current is not None:
                raw_blocks.append(current)
            elif not preamble_flushed:
                # Emit the pre-heading preamble as a level-0 section, but only
                # when it carries non-empty content — a document that opens
                # directly with a heading produces no empty preamble section.
                if "".join(preamble).strip():
                    raw_blocks.append((0, "", preamble))
                preamble_flushed = True
            level = len(match.group(1))
            heading = match.group(2).strip()
            current = (level, heading, [])
        else:
            if current is None:
                preamble.append(line)
            else:
                current[2].append(line)

    if current is not None:
        raw_blocks.append(current)
    elif not raw_blocks:
        # Document with no headings at all — one level-0 preamble section
        # (even if empty, so `classify` always returns at least one row).
        raw_blocks.append((0, "", preamble))

    sections: list[Section] = []
    for order, (level, heading, body_lines) in enumerate(raw_blocks):
        body = "\n".join(body_lines).strip("\n")
        sections.append(
            Section(heading=heading, level=level, body=body, order=order)
        )
    return sections


# --------------------------------------------------------------------------
# Rule family 1 — header-match
# --------------------------------------------------------------------------
#
# Each entry maps a set of known, whitespace-normalized, lower-cased heading
# names to the IR kind that heading routes toward. Ordered tuple — iteration
# order is fixed and deterministic.

_HEADER_RULES: tuple[tuple[frozenset[str], IRKind], ...] = (
    (
        frozenset({"decision", "the decision", "decision drivers", "chosen option"}),
        IRKind.ADR_DECISION,
    ),
    (
        frozenset({"context", "background", "context and problem statement", "problem"}),
        IRKind.ADR_CONTEXT,
    ),
    (
        frozenset(
            {"consequences", "trade-offs", "tradeoffs", "trade offs", "implications"}
        ),
        IRKind.ADR_CONSEQUENCES,
    ),
    (
        frozenset(
            {
                "responsibilities",
                "scope",
                "purpose and scope",
                "purpose",
                "responsibility",
            }
        ),
        IRKind.AE_RESPONSIBILITY,
    ),
    (
        frozenset(
            {
                "business rules",
                "rules",
                "acceptance criteria",
                "requirements",
                "behavioral contracts",
            }
        ),
        IRKind.WS_BUSINESS_RULE,
    ),
)


def _header_signal(section: Section) -> tuple[IRKind, str] | None:
    """Header-match rule family — return (IR kind, signal) if the heading text
    matches a known heading name, else `None`."""
    if not section.heading:
        return None
    key = " ".join(section.heading.lower().split())
    for names, ir_kind in _HEADER_RULES:
        if key in names:
            return ir_kind, f"header-match: '{section.heading}' -> {ir_kind.name}"
    return None


# --------------------------------------------------------------------------
# Rule family 2 — keyword-match
# --------------------------------------------------------------------------
#
# Each entry maps an IR kind to a set of body phrases that vote for it. The
# scan is case-insensitive on the body text. Ordered tuple for determinism.

_KEYWORD_RULES: tuple[tuple[IRKind, tuple[str, ...], str], ...] = (
    (
        IRKind.ADR_DECISION,
        ("we chose", "we decided", "we will", "rather than", "instead of",
         "the alternative", "we selected", "we picked", "decided to"),
        "decision-rationale",
    ),
    (
        IRKind.WS_BUSINESS_RULE,
        ("must ", "must.", "shall ", "is required to", "are required to",
         "required to ", "the system must", "the user must"),
        "obligation",
    ),
    (
        IRKind.AE_RESPONSIBILITY,
        ("is responsible for", "are responsible for", " owns ", " provides ",
         " exposes ", "responsible for", "responsibility of"),
        "responsibility",
    ),
    (
        IRKind.ADR_CONTEXT,
        ("the problem is", "currently", "today,", "background:",
         "the situation is", "historically"),
        "context-framing",
    ),
    (
        IRKind.ADR_CONSEQUENCES,
        ("as a result", "the consequence", "this means", "the trade-off",
         "the tradeoff", "the downside", "the upside", "the cost is"),
        "consequence-framing",
    ),
)


def _keyword_signals(section: Section) -> list[tuple[IRKind, str]]:
    """Keyword-match rule family — return one (IR kind, signal) per IR kind
    whose body-phrase set is hit at least once."""
    body = section.body.lower()
    out: list[tuple[IRKind, str]] = []
    for ir_kind, phrases, label in _KEYWORD_RULES:
        for phrase in phrases:
            if phrase in body:
                out.append(
                    (ir_kind, f"keyword: '{phrase.strip()}' ({label})")
                )
                break
    return out


# --------------------------------------------------------------------------
# Rule family 3 — structural-pattern
# --------------------------------------------------------------------------

_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_OVER_SHAPE_RE = re.compile(
    r"\b(?:chose|choose|chosen|selecting|selected|pick(?:ed)?|decided)\b"
    r"[^.\n]*\bover\b",
    re.IGNORECASE,
)
_OBLIGATION_RE = re.compile(r"\b(?:must|shall|required to)\b", re.IGNORECASE)


def _structural_signals(section: Section) -> list[tuple[IRKind, str]]:
    """Structural-pattern rule family — the section's *shape* votes.

    Two structural votes are recognized at MVP:
      * a list whose items predominantly carry obligation phrasing votes
        `WS_BUSINESS_RULE`;
      * an explicit "X over Y" / "chose ... over ..." prose shape votes
        `ADR_DECISION`.
    """
    out: list[tuple[IRKind, str]] = []
    body = section.body

    # Numbered/bulleted obligation list -> WS_BUSINESS_RULE.
    list_items = [ln for ln in body.split("\n") if _LIST_ITEM_RE.match(ln)]
    if list_items:
        obligation_items = [ln for ln in list_items if _OBLIGATION_RE.search(ln)]
        if obligation_items and len(obligation_items) * 2 >= len(list_items):
            out.append(
                (IRKind.WS_BUSINESS_RULE, "structure: obligation list")
            )

    # "chose X over Y" prose shape -> ADR_DECISION.
    if _OVER_SHAPE_RE.search(body):
        out.append((IRKind.ADR_DECISION, "structure: 'X over Y' decision shape"))

    return out


# --------------------------------------------------------------------------
# Scoring + classification
# --------------------------------------------------------------------------


def _classify_section(section: Section) -> Classification:
    """Run all three rule families against one section and combine the votes.

    The chosen `ir_kind` is the IR type with the highest combined vote weight;
    ties are broken by `_IR_PRECEDENCE`. The confidence score starts from the
    base for the strongest firing family and adds `_AGREEMENT_INCREMENT` per
    additional family that agreed, clamped to `[0.0, 1.0]`. A section with no
    firing family is `UNCLASSIFIED` with `confidence == 0.0`.
    """
    # Collect (IR kind, family-rank, signal). family-rank: header=0 strongest,
    # keyword=1, structure=2 — lower is stronger.
    votes: list[tuple[IRKind, int, str]] = []

    header = _header_signal(section)
    if header is not None:
        votes.append((header[0], 0, header[1]))
    for ir_kind, sig in _keyword_signals(section):
        votes.append((ir_kind, 1, sig))
    for ir_kind, sig in _structural_signals(section):
        votes.append((ir_kind, 2, sig))

    if not votes:
        return Classification(
            section=section,
            ir_kind=IRKind.UNCLASSIFIED,
            confidence=0.0,
            signals=("no rule matched",),
        )

    # Tally per IR kind: which families voted for it.
    families_by_kind: dict[IRKind, set[int]] = {}
    for ir_kind, rank, _sig in votes:
        families_by_kind.setdefault(ir_kind, set()).add(rank)

    # Winner: most families agreeing, ties broken by fixed IR precedence.
    def _rank_key(ir_kind: IRKind) -> tuple[int, int]:
        family_count = len(families_by_kind[ir_kind])
        # _IR_PRECEDENCE is ordered strongest-first; lower index wins ties.
        precedence = (
            _IR_PRECEDENCE.index(ir_kind)
            if ir_kind in _IR_PRECEDENCE
            else len(_IR_PRECEDENCE)
        )
        return (-family_count, precedence)

    winner = min(families_by_kind, key=_rank_key)
    winning_families = families_by_kind[winner]

    # Base score from the strongest (lowest-rank) family that voted for the
    # winner; +increment per additional agreeing family.
    strongest_rank = min(winning_families)
    base = {0: _HEADER_BASE, 1: _KEYWORD_BASE, 2: _STRUCTURE_BASE}[strongest_rank]
    score = base + _AGREEMENT_INCREMENT * (len(winning_families) - 1)
    confidence = max(0.0, min(1.0, score))

    # Signals: every rule that fired, in family order (header, keyword,
    # structure), restricted to those voting for the winner, then the rest.
    winner_signals = [sig for k, _r, sig in votes if k == winner]
    other_signals = [sig for k, _r, sig in votes if k != winner]
    signals = tuple(winner_signals + other_signals)

    return Classification(
        section=section,
        ir_kind=winner,
        confidence=confidence,
        signals=signals,
    )


def classify(document: str) -> list[Classification]:
    """Classify every section of a markdown document into a DekSpec IR type.

    `classify` sections the document on ATX headings and routes each section
    through the three deterministic rule families, returning one
    `Classification` per section in source order. It is a pure function — it
    opens no file, makes no network call, reads no environment variable, and
    calls no model. The same document string always yields a byte-identical
    result.

    Promotion refs: INT-059 §Desired Outcome (deterministic heuristic
    classifier — section-header + keyword + structural-pattern matching →
    IR-type + confidence score, no LLM), INT-059 §Open Issues OI-1.
    """
    return [_classify_section(section) for section in section_document(document)]
