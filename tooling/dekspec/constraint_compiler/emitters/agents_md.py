"""agents_md emitter — AE/ADR/WS IR -> AGENTS.md fragment string.

Per the playbook, the AGENTS.md fragment is the *soft* enforcement layer:
prompt-level context the worker reads at session start. Each LOCKED
artifact contributes a fragment; consumers aggregate fragments into
their AGENTS.md (or per-package AGENTS.md fragments if the consumer
prefers per-package scoping).

Fragment shape is tuned per artifact type:
  - AE: architectural-slice context (purpose, responsibilities, boundaries,
        when-working-in globs, related artifacts)
  - ADR: decision context (decision statement, reconsideration triggers,
         what it shapes)
  - WS: behavioral spec context (what it does, business rules, failure
        behaviors, related AE)

Worker context is precious — fragments target ~30-50 lines max. Long
prose is excerpted to first sentence; full content stays in source.

Public API:
  - emit(ir) -> str          dispatches by IR id prefix
  - emit_ae(ir) -> str
  - emit_adr(ir) -> str
  - emit_ws(ir) -> str
  - emit_ib(ir) -> str
  - emit_intent(ir) -> str
  - emit_mission(ir) -> str
  - emit_constitution(ir) -> list[str]   # WS-006 BR1: 8 fragments
  - suggested_filename(ir) -> str

Each fragment is wrapped with HTML comment delimiters:
  <!-- BEGIN dekspec-fragment: <id> -->
  ...
  <!-- END dekspec-fragment: <id> -->

so consumers can aggregate / replace fragments programmatically.
"""

from __future__ import annotations

from typing import Any

from .. import IR_SCHEMA_VERSION, PARSER_VERSION
from . import contract_test as _contract_test  # for _slug helper

EMITTER_VERSION = "0.1.0"

_MAX_PROSE_CHARS = 600  # truncate long prose to keep fragments terse


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def emit(ir: dict[str, Any]) -> str:
    """Dispatch to the per-artifact-kind emitter based on IR id prefix."""
    aid = ir.get("id", "")
    if aid.startswith("AE-"):
        return emit_ae(ir)
    if aid.startswith("ADR-"):
        return emit_adr(ir)
    if aid.startswith("WS-"):
        return emit_ws(ir)
    if aid.startswith("IB-"):
        return emit_ib(ir)
    if aid.startswith("INT-"):
        return emit_intent(ir)
    if aid.startswith("MSN-"):
        return emit_mission(ir)
    raise ValueError(
        f"agents_md emitter doesn't know how to handle artifact id '{aid}'. "
        f"Expected AE-NNN, ADR-NNN, WS-NNN, IB-NNN, INT-NNN, or MSN-NNN."
    )


def suggested_filename(ir: dict[str, Any]) -> str:
    aid = ir["id"].lower()
    name_slug = _contract_test._slug(ir.get("name", ""))
    return f"{aid}-{name_slug}.agents.md"


# --------------------------------------------------------------------------- #
# AE fragment
# --------------------------------------------------------------------------- #


def emit_ae(ir: dict[str, Any]) -> str:
    aid = ir["id"]
    name = ir.get("name", "")
    subtype = ir.get("subtype", "?")
    classification = ir.get("classification", "?")
    purpose = _excerpt(_resolve_prose(ir.get("purpose_and_scope")))
    responsibilities = ir.get("responsibilities", [])
    bng = ir.get("boundaries_and_non_goals", {}) or {}
    non_goals = bng.get("non_goals", [])
    boundaries = ir.get("boundaries", {}) or {}
    globs = ir.get("implements_globs", [])
    linked = ir.get("linked_artifacts", {}) or {}

    parts = [
        _begin_marker(aid),
        _header(ir, kind="Architecture Element"),
        f"## {aid}: {name}",
        "",
        f"**Type:** {subtype} ({classification})",
        "",
        f"**Purpose.** {purpose}" if purpose else "",
    ]

    if responsibilities:
        parts.append("\n**Responsibilities:**")
        for r in responsibilities[:6]:
            parts.append(f"- {_excerpt(r, 200)}")

    if non_goals:
        parts.append("\n**Boundaries (do NOT do):**")
        for ng in non_goals[:5]:
            text = ng.get("text", "")
            why = ng.get("why", "")
            line = f"- {_excerpt(text, 150)}"
            if why:
                line += f" — {_excerpt(why, 150)}"
            parts.append(line)

    if globs:
        parts.append("\n**When working in any of these paths, this AE applies:**")
        for g in globs:
            parts.append(f"- `{g}`")

    # MSN-008 / INT-048: render the AE's three-tier boundary block. Scoped to
    # this AE's fragment, which already appears only when the AE is in scope.
    _tiers = (
        ("always_do", "*Always do:*"),
        ("ask_first", "*Ask first (surface to the engineer before proceeding):*"),
        ("never_do", "*Never do:*"),
    )
    if any(boundaries.get(k) for k, _ in _tiers):
        parts.append("\n**Three-tier boundaries:**")
        for _key, _sub in _tiers:
            _clauses = boundaries.get(_key) or []
            if not _clauses:
                continue
            parts.append(_sub)
            for _c in _clauses:
                parts.append(f"- {_excerpt(_c, 200)}")

    # ds-f2j: plumb AE.views + AE.runtime_behavior into the fragment so the
    # coding agent sees the architectural views the AE relies on.
    views = ir.get("views") or {}
    diagrams = views.get("diagrams") or []
    if diagrams:
        parts.append("\n**Architectural views** (in the AE — load-bearing diagrams):")
        for d in diagrams[:4]:
            kind = d.get("kind", "?")
            desc = _excerpt(d.get("description", ""), 120)
            line = f"- *{kind}*"
            if desc:
                line += f" — {desc}"
            parts.append(line)
    elif views.get("absence_justification"):
        parts.append(f"\n**Views absence:** {_excerpt(views['absence_justification'], 200)}")

    runtime = _resolve_prose(ir.get("runtime_behavior"))
    if runtime:
        parts.append(f"\n**Runtime behavior.** {_excerpt(runtime, 400)}")

    refs = []
    if linked.get("related_adrs"):
        refs.append(f"**ADRs:** {', '.join(linked['related_adrs'])}")
    if linked.get("related_wss"):
        refs.append(f"**WSes:** {', '.join(linked['related_wss'])}")
    if linked.get("related_ics"):
        refs.append(f"**ICs:** {', '.join(linked['related_ics'])}")
    if refs:
        parts.append("\n" + " | ".join(refs))

    parts.append("")
    parts.append(_end_marker(aid))
    return "\n".join(p for p in parts if p is not None) + "\n"


# --------------------------------------------------------------------------- #
# ADR fragment
# --------------------------------------------------------------------------- #


def emit_adr(ir: dict[str, Any]) -> str:
    aid = ir["id"]
    name = ir.get("name", "")
    status = ir.get("status", "?")
    date = ir.get("date") or ir.get("created", "?")
    decision = _excerpt(ir.get("decision", ""), max_chars=_MAX_PROSE_CHARS)

    validation = ir.get("validation", {}) or {}
    triggers = (
        validation.get("reconsideration_triggers")
        or validation.get("raw_prose")
        or ""
    )
    triggers = _excerpt(triggers, 400)

    related_aes = ir.get("related_architecture_elements", [])
    superseded_by = (ir.get("supersession", {}) or {}).get("superseded_by", [])
    # ds-f2j: surface options_considered + consequences — these are the
    # meatiest ADR sections and were previously dropped by the emitter.
    options = ir.get("options_considered") or []
    consequences = ir.get("consequences") or {}

    parts = [
        _begin_marker(aid),
        _header(ir, kind="Architecture Decision Record"),
        f"## {aid}: {name}",
        "",
        f"**Status:** {status}  |  **Decision date:** {date}",
    ]
    if superseded_by:
        parts.append(f"**Superseded by:** {', '.join(superseded_by)} — do not enforce; consult the successor.")
    parts.append("")
    if decision:
        parts.append(f"**Decision.** {decision}")

    if options:
        parts.append("\n**Options considered:**")
        for opt in options[:4]:
            opt_name = opt.get("name", "?")
            parts.append(f"- *{opt_name}*")
        if len(options) > 4:
            parts.append(f"... ({len(options) - 4} more — consult the full ADR)")

    cons_pos = consequences.get("positive") or []
    cons_neg = consequences.get("negative") or []
    if cons_pos or cons_neg:
        parts.append("\n**Consequences:**")
        for c in cons_pos[:3]:
            parts.append(f"- (+) {_excerpt(c, 180)}")
        for c in cons_neg[:3]:
            parts.append(f"- (−) {_excerpt(c, 180)}")
        if len(cons_pos) > 3 or len(cons_neg) > 3:
            parts.append(f"... ({(len(cons_pos) - 3 if len(cons_pos) > 3 else 0) + (len(cons_neg) - 3 if len(cons_neg) > 3 else 0)} more — consult the full ADR)")

    if triggers:
        parts.append(f"\n**Reconsider this decision if:** {triggers}")
    if related_aes:
        ae_ids = [r["id"] for r in related_aes]
        parts.append(f"\n**Shapes:** {', '.join(ae_ids)}")
    parts.append("")
    parts.append(_end_marker(aid))
    return "\n".join(p for p in parts if p is not None) + "\n"


# --------------------------------------------------------------------------- #
# WS fragment
# --------------------------------------------------------------------------- #


def emit_ws(ir: dict[str, Any]) -> str:
    aid = ir["id"]
    name = ir.get("name", "")
    status = ir.get("status", "?")
    related_aes = ir.get("related_architecture_elements", [])

    wtd = ir.get("what_this_does", {}) or {}
    summary = wtd.get("mechanism") or _excerpt(wtd.get("prose", ""), 300)

    rules = ir.get("business_rules", [])
    failures = ir.get("failure_behavior", [])

    parts = [
        _begin_marker(aid),
        _header(ir, kind="Working Spec"),
        f"## {aid}: {name}",
        "",
        f"**Status:** {status}",
    ]
    if related_aes:
        ae_ids = [r["id"] for r in related_aes]
        parts.append(f"**Behavioral spec for:** {', '.join(ae_ids)}")
    parts.append("")
    if summary:
        parts.append(f"**What this does.** {summary}")

    if rules:
        parts.append("\n**Business rules** (testable assertions; honor in any code in scope):")
        for r in rules[:10]:
            num = r.get("number", "?")
            domain = r.get("domain", "")
            rule = _excerpt(r.get("rule", ""), 250)
            parts.append(f"{num}. *{domain}* — {rule}")
        if len(rules) > 10:
            parts.append(f"... ({len(rules) - 10} more — consult the full WS for completeness)")

    if failures:
        parts.append("\n**Failure behaviors** (how the system MUST react):")
        for f in failures[:10]:
            failure = _excerpt(f.get("failure", ""), 100)
            behavior = _excerpt(f.get("behavior", ""), 150)
            parts.append(f"- **{failure}** → {behavior}")
        if len(failures) > 10:
            parts.append(f"... ({len(failures) - 10} more — consult the full WS for completeness)")

    parts.append("")
    parts.append(_end_marker(aid))
    return "\n".join(p for p in parts if p is not None) + "\n"


# --------------------------------------------------------------------------- #
# IB fragment
# --------------------------------------------------------------------------- #


def emit_ib(ir: dict[str, Any]) -> str:
    aid = ir["id"]
    name = ir.get("name", "")
    status = ir.get("status", "?")
    spec = ir.get("spec") or {}
    spec_id = spec.get("id", "?")
    source_aes = ir.get("source_aes", []) or []
    depends_on = ir.get("depends_on", []) or []
    production_gate = ir.get("production_gate", "")
    goal = _excerpt(ir.get("goal", ""), max_chars=_MAX_PROSE_CHARS)
    files = ir.get("files_to_modify", []) or []
    do_not_touch = ir.get("do_not_touch", []) or []
    governing_adrs = ir.get("governing_adrs", []) or []
    done_when = ir.get("done_when", []) or []

    parts = [
        _begin_marker(aid),
        _header(ir, kind="Implementation Brief"),
        f"## {aid}: {name}",
        "",
        f"**Status:** {status}  |  **Parent WS:** {spec_id}",
    ]
    if source_aes:
        ae_ids = [r["id"] for r in source_aes]
        parts.append(f"**Source AEs:** {', '.join(ae_ids)}")
    if depends_on:
        parts.append(f"**Depends on:** {', '.join(depends_on)}")
    if production_gate and production_gate.lower() != "none":
        parts.append(f"**Production gate:** {production_gate}")
    parts.append("")
    if goal:
        parts.append(f"**Goal.** {goal}")

    if files:
        parts.append("\n**Files to modify (this IB's authorized scope):**")
        for f in files[:12]:
            file_path = f.get("file", "")
            change = _excerpt(f.get("change", ""), 120)
            line = f"- `{file_path}`"
            if change:
                line += f" — {change}"
            parts.append(line)
        if len(files) > 12:
            parts.append(f"... ({len(files) - 12} more — consult the full IB)")

    if do_not_touch:
        parts.append("\n**Do NOT touch:**")
        for entry in do_not_touch[:6]:
            parts.append(f"- {_excerpt(entry, 200)}")

    if governing_adrs:
        adr_ids = [r["id"] for r in governing_adrs]
        parts.append(f"\n**Governing ADRs:** {', '.join(adr_ids)}")

    if done_when:
        parts.append("\n**Done when** (acceptance criteria — implementation must satisfy each):")
        for criterion in done_when[:8]:
            parts.append(f"- {_excerpt(criterion, 220)}")
        if len(done_when) > 8:
            parts.append(f"... ({len(done_when) - 8} more — consult the full IB)")

    # ds-f2j + ds-ibx: surface the load-bearing IB sections — these were
    # promoted from author scratch-pad to canonical IR fields in v0.40.0 and
    # are the "implement from here only" rules the coding agent must honor.
    cd = ir.get("constraints_and_decisions") or []
    if cd:
        parts.append("\n**Constraints & decisions** (implement from here only — these reconcile spec context and governing ADRs):")
        for entry in cd[:10]:
            topic = entry.get("topic", "?")
            rule = _excerpt(entry.get("rule", ""), 220)
            parts.append(f"- **{topic}.** {rule}")
        if len(cd) > 10:
            parts.append(f"... ({len(cd) - 10} more — consult the full IB)")

    dc = ir.get("domain_constraints") or []
    if dc:
        parts.append("\n**Domain constraints** (cross-cutting boundary values — carry into every implementation):")
        for row in dc[:8]:
            constraint = row.get("constraint", "?")
            value = row.get("value", "?")
            parts.append(f"- **{constraint}:** `{value}`")

    parts.append("")
    parts.append(_end_marker(aid))
    return "\n".join(p for p in parts if p is not None) + "\n"


# --------------------------------------------------------------------------- #
# Intent fragment
# --------------------------------------------------------------------------- #


def emit_intent(ir: dict[str, Any]) -> str:
    aid = ir["id"]
    name = ir.get("name", "")
    status = ir.get("status", "?")
    intent_type = ir.get("intent_type", "?")
    autonomy = ir.get("autonomy", "?")
    mission = (ir.get("mission") or {}).get("id")
    aes = ir.get("linked_architecture_elements", []) or []
    motivation = _excerpt(ir.get("motivation", ""), max_chars=_MAX_PROSE_CHARS)
    desired = _excerpt(ir.get("desired_outcome", ""), 400)
    components = ir.get("components_affected", []) or []
    verification = ir.get("verification", []) or []
    type_specific = ir.get("type_specific", {}) or {}

    parts = [
        _begin_marker(aid),
        _header(ir, kind="Intent"),
        f"## {aid}: {name}",
        "",
        f"**Status:** {status}  |  **Type:** {intent_type}  |  **Autonomy:** {autonomy}",
    ]
    if mission:
        parts.append(f"**Mission:** {mission}")
    if aes:
        ae_ids = [r["id"] for r in aes]
        parts.append(f"**Shapes:** {', '.join(ae_ids)}")
    parts.append("")
    if motivation:
        parts.append(f"**Motivation.** {motivation}")
    if desired:
        parts.append(f"\n**Desired outcome.** {desired}")

    nfr_target = type_specific.get("target")
    nfr_metric = type_specific.get("metric")
    if nfr_metric and nfr_target:
        parts.append(f"\n**NFR target:** `{nfr_metric}` ≥ `{nfr_target}`")

    if components:
        parts.append("\n**Components affected (this Intent's diff is confined to these globs):**")
        for g in components[:10]:
            parts.append(f"- `{g}`")
        if len(components) > 10:
            parts.append(f"... ({len(components) - 10} more)")

    if verification:
        parts.append("\n**Verification (TESTPASS predicate):**")
        for v in verification[:8]:
            parts.append(f"- `{v.get('name')}`: `{v.get('cmd')}`")
        if len(verification) > 8:
            parts.append(f"... ({len(verification) - 8} more)")

    parts.append("")
    parts.append(_end_marker(aid))
    return "\n".join(p for p in parts if p is not None) + "\n"


# --------------------------------------------------------------------------- #
# Mission fragment
# --------------------------------------------------------------------------- #


def emit_mission(ir: dict[str, Any]) -> str:
    aid = ir["id"]
    name = ir.get("name", "")
    status = ir.get("status", "?")
    autonomy = ir.get("autonomy_ceiling", "?")
    owner = ir.get("owner")
    outcome = _excerpt(ir.get("outcome", ""), max_chars=_MAX_PROSE_CHARS)
    out_of_scope = ir.get("out_of_scope", []) or []
    flag = ir.get("flag_strategy", {}) or {}
    rollback_ir = ir.get("rollback_plan")
    kill = ir.get("kill_criteria", []) or []
    queue = ir.get("intent_queue", []) or []
    verification = ir.get("mission_verification", []) or []

    parts = [
        _begin_marker(aid),
        _header(ir, kind="Mission"),
        f"## {aid}: {name}",
        "",
        f"**Status:** {status}  |  **Autonomy ceiling:** {autonomy}",
    ]
    if owner:
        parts.append(f"**Owner:** {owner}")
    parts.append("")
    if outcome:
        parts.append(f"**Outcome.** {outcome}")

    if verification:
        parts.append("\n**Mission Verification (gates COMPLETING → COMPLETE):**")
        for v in verification[:6]:
            parts.append(f"- `{v.get('name')}`: `{v.get('cmd')}`")

    if out_of_scope:
        parts.append("\n**Out of scope (Mission rejects these even if proposed):**")
        for entry in out_of_scope[:6]:
            parts.append(f"- {_excerpt(entry, 200)}")

    if flag.get("flag_name") and flag.get("flag_name").lower() != "none":
        parts.append(
            f"\n**Flag:** `{flag.get('flag_name')}` "
            f"(default: {flag.get('default_state', '?')}; "
            f"removal: {flag.get('removal_plan', '?')})"
        )

    # rollback_plan: v0.2.0 dict shape {trigger, steps[]}. Pre-0.2.0
    # plain string is rendered as a `trigger`-only excerpt for back-compat
    # — but no v0.1.0 strings should reach here once mission IRs have been
    # migrated to v0.2.0 upstream.
    if isinstance(rollback_ir, dict):
        trig = _excerpt((rollback_ir.get("trigger") or ""), 400)
        steps = rollback_ir.get("steps", []) or []
        if trig:
            parts.append(f"\n**Rollback trigger.** {trig}")
        if steps:
            parts.append("**Rollback steps:**")
            for step in steps[:6]:
                parts.append(
                    f"- `{step.get('name', '?')}`: `{step.get('cmd', '?')}`"
                )
    elif isinstance(rollback_ir, str) and rollback_ir.strip():
        parts.append(f"\n**Rollback.** {_excerpt(rollback_ir, 400)}")

    if kill:
        parts.append("\n**Kill criteria (trigger Mission abandonment):**")
        for entry in kill[:5]:
            if isinstance(entry, dict):
                parts.append(
                    f"- `{entry.get('name', '?')}`: `{entry.get('cmd', '?')}`"
                )
            else:
                parts.append(f"- {_excerpt(str(entry), 200)}")

    if queue:
        parts.append("\n**Intent queue (serialization order; one ACTIVE at a time):**")
        for entry in queue[:10]:
            int_id = entry.get("id", "(sketch)")
            title = entry.get("title", "")
            int_status = entry.get("status", "?")
            line = f"- {int_id}"
            if title:
                line += f" — {_excerpt(title, 80)}"
            line += f"  [{int_status}]"
            parts.append(line)
        if len(queue) > 10:
            parts.append(f"... ({len(queue) - 10} more in queue)")

    parts.append("")
    parts.append(_end_marker(aid))
    return "\n".join(p for p in parts if p is not None) + "\n"


# --------------------------------------------------------------------------- #
# Constitution fragments (WS-006 BR1–6)
# --------------------------------------------------------------------------- #
#
# The Constitution emitter is the singleton-with-multi-fragment case: one IR
# composes 8 article fragments (not the family's usual single-string return).
# Per WS-006 BR1 the fragments emit in canonical article order; per BR2–5
# each article kind has its own shape; per BR6 emission is byte-stable across
# invocations (no datetime.now / set / sorted on adr_refs / ae_refs).

# Canonical title list pinned by WS-004 BR1. Mirrors the parser's
# `_CONSTITUTION_ARTICLES` (title, kind) tuple. Declared here rather than
# imported because the parser's constant is module-private.
#
# TODO: consolidate parser._CONSTITUTION_ARTICLES + this constant into a
# shared `_constitution_canonical.py` module so the schema-pinned title list
# has exactly one source of truth (IB-007 §Open Issues recommendation (c)).
# Drift is currently guarded by `test_emitter_titles_match_parser` in the
# smoke suite, which fails if the two lists diverge.
_CONSTITUTION_ARTICLE_TITLES: tuple[str, ...] = (
    "Project Identity",
    "Technology Stack",
    "Quality Standards",
    "Architecture Principles",
    "Development Workflow",
    "Model Configuration",
    "Boundaries",
    "Amendments",
)


def emit_constitution(ir: dict[str, Any]) -> list[str]:
    """Emit the Constitution IR as 8 ordered AGENTS.md fragments (WS-006 BR1).

    Returns a list of exactly 8 markdown strings, one per article in WS-004
    BR1's pinned canonical order. Each fragment is self-contained: H2 header
    + body. The aggregator joins them with ``\\n\\n`` and frames the block
    with ``---`` horizontal rules per WS-006 BR7.

    Dispatch is by article ``kind``:
      - ``pointer``   → Article 1 (summary + See also). WS-006 BR2.
      - ``ref-array`` → Article 4 (adr_refs bullets) or Article 7 (dual
        adr_refs + ae_refs sub-lists), discriminated by index. WS-006 BR4/5.
      - ``text``      → Articles 2/3/5/6/8 (verbatim opaque markdown body).
        WS-006 BR3.

    Determinism: dict + list iteration is insertion-ordered; no set(),
    sorted(), datetime.now(), or randomness. The parser preserves ref-array
    insertion order per WS-002 BR1.
    """
    articles = ir.get("articles") or []
    fragments: list[str] = []
    for i, article in enumerate(articles):
        n = i + 1
        title = _CONSTITUTION_ARTICLE_TITLES[i]
        kind = article.get("kind")
        if kind == "pointer":
            fragments.append(_emit_pointer_article(article, n, title))
        elif kind == "ref-array":
            if n == 7:
                fragments.append(_emit_boundary_refs_article(article, n, title))
            else:
                fragments.append(_emit_adr_refs_article(article, n, title))
        else:
            fragments.append(_emit_text_article(article, n, title))
    return fragments


def _emit_pointer_article(article: dict[str, Any], n: int, title: str) -> str:
    """Article 1 (typed pointer — WS-006 BR2): H2 + summary verbatim +
    `**See also:**` closing line. Summary is not excerpt-truncated; schema's
    `maxLength: 500` is the cap.
    """
    summary = article.get("summary", "")
    see_also = article.get("see_also", "")
    parts = [
        f"## Article {n}: {title}",
        "",
        summary,
        "",
        f"**See also:** {see_also}",
    ]
    return "\n".join(parts)


def _emit_text_article(article: dict[str, Any], n: int, title: str) -> str:
    """Articles 2/3/5/6/8 (text block — WS-006 BR3): H2 + verbatim opaque
    markdown body. No wrapping, no truncation."""
    body = article.get("body", "")
    parts = [
        f"## Article {n}: {title}",
        "",
        body,
    ]
    return "\n".join(parts)


def _emit_adr_refs_article(article: dict[str, Any], n: int, title: str) -> str:
    """Article 4 (`adr_refs` bulleted list — WS-006 BR4): H2 + one bullet per
    entry in IR insertion order, shape `- **ADR-NNN:** <rationale>`. Empty
    `adr_refs` array → header-only fragment (no bullets, no placeholder).
    """
    parts = [f"## Article {n}: {title}"]
    adr_refs = article.get("adr_refs") or []
    if adr_refs:
        parts.append("")
        for ref in adr_refs:
            parts.append(f"- **{ref['id']}:** {ref['rationale']}")
    return "\n".join(parts)


def _emit_boundary_refs_article(
    article: dict[str, Any], n: int, title: str
) -> str:
    """Article 7 (boundary refs — WS-006 BR5): H2 + two canonical-ordered
    sub-lists ("ADRs" then "AEs"). Each sub-list is a `**Kind:**` heading
    followed by bullets. An empty sub-list omits its heading entirely. Both
    arrays empty → header-only fragment.
    """
    adr_refs = article.get("adr_refs") or []
    ae_refs = article.get("ae_refs") or []
    parts = [f"## Article {n}: {title}"]
    if adr_refs:
        parts.append("")
        parts.append("**ADRs:**")
        parts.append("")
        for ref in adr_refs:
            parts.append(f"- **{ref['id']}:** {ref['rationale']}")
    if ae_refs:
        parts.append("")
        parts.append("**AEs:**")
        parts.append("")
        for ref in ae_refs:
            parts.append(f"- **{ref['id']}:** {ref['aspect']}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Compact aggregate AGENTS.md — the lite-profile render mode (IB-116).
#
# Under the `lite` methodology profile, `dekspec aggregate agents-md` emits a
# single-page AGENTS.md instead of the full corpus dump: a one-page
# Constitution summary plus the in-flight Intent's title + Desired Outcome.
# The target is one screen at a typical terminal width — roughly 50 lines at
# 80 columns.
#
# The `full`-profile render path (the `cmd_aggregate_agents_md` corpus
# assembly) is untouched; the compact mode is a separate branch reached only
# when `get_profile()` returns `lite`. The IR pipeline is unchanged — these
# functions consume already-parsed Constitution + Intent IRs.
# --------------------------------------------------------------------------- #

# Line budget for the compact AGENTS.md — the "one screen at a typical
# terminal width" target. ~50 lines at 80 columns; the exact budget is the
# IB-116 author's call (IB-117's line-count fixture asserts against it).
COMPACT_AGENTS_MD_LINE_BUDGET = 60

# Articles rendered as a one-line distillation in the compact Constitution
# summary. Each article contributes its title plus its single most
# load-bearing commitment (the article summary's / body's first sentence).
# Kept short so each distillation line wraps to at most ~2 rows at 80
# columns — the compact artifact targets one screen.
_COMPACT_CONSTITUTION_PROSE_CHARS = 120

# Desired-outcome excerpt budget for the compact active-Intent summary.
_COMPACT_INTENT_PROSE_CHARS = 400


def emit_compact_aggregate(
    constitution: dict[str, Any] | None,
    active_intent: dict[str, Any] | None,
) -> str:
    """Render the single-page (lite-profile) aggregate AGENTS.md.

    Pure render function: consumes an already-parsed Constitution IR and the
    in-flight Intent IR (either may be ``None``) and returns the compact
    AGENTS.md markdown text. Profile detection is the caller's concern — this
    function does not read ``.dekspec/config.yaml``; see
    :func:`compact_aggregate_for_profile` for the profile-aware entry point.

    The compact artifact is a one-page Constitution summary (article titles +
    the single most load-bearing commitment per article — not the full
    8-article dump) plus the active-Intent summary (the in-flight Intent's
    title + Desired Outcome — not the full Intent body or corpus). The output
    targets one screen at a typical terminal width (~50 lines at 80 columns).

    UTF-8 throughout; LF line endings; the trailing newline mirrors the
    full-profile emitter's convention.
    """
    parts: list[str] = []
    parts.append("<!--")
    parts.append("  AGENTS.md — auto-generated by dekspec aggregate agents-md")
    parts.append("  Methodology profile: lite (compact single-page render)")
    parts.append("")
    parts.append("  DO NOT EDIT THIS FILE BY HAND. Re-run `dekspec aggregate agents-md`")
    parts.append("  to regenerate after spec changes.")
    parts.append("-->")
    parts.append("")
    parts.append("# AGENTS.md")
    parts.append("")
    parts.append(
        "Compact context for AI agents working in this repo (lite profile): "
        "a one-page Constitution summary plus the in-flight Intent. For the "
        "full corpus, switch the profile to `full` and re-aggregate."
    )
    parts.append("")

    parts.append("---")
    parts.append("")
    if constitution:
        parts.append(f"# Constitution: {constitution.get('name', '')}")
        parts.append("")
        for line in _compact_constitution_lines(constitution):
            parts.append(line)
    else:
        parts.append("# Constitution")
        parts.append("")
        parts.append("_No Constitution artifact in scope._")
    parts.append("")

    parts.append("---")
    parts.append("")
    parts.append("# Active Intent")
    parts.append("")
    if active_intent:
        for line in _compact_intent_lines(active_intent):
            parts.append(line)
    else:
        parts.append("_No in-flight Intent — nothing is currently being built._")
    parts.append("")

    output = "\n".join(parts)
    if not output.endswith("\n"):
        output += "\n"
    return output


def compact_aggregate_for_profile(
    repo_root: Any,
    constitution: dict[str, Any] | None,
    active_intent: dict[str, Any] | None,
) -> str | None:
    """Return the compact AGENTS.md when the repo's profile is ``lite``.

    Consults INT-024's ``get_profile()`` (the single load-bearing profile
    read point) for ``repo_root``. Returns the compact single-page render
    when the active profile is ``lite``; returns ``None`` otherwise so the
    caller falls through to the byte-identical full-corpus render path.
    """
    from ...dekspec_config import get_profile

    if get_profile(repo_root) != "lite":
        return None
    return emit_compact_aggregate(constitution, active_intent)


def _compact_constitution_lines(constitution: dict[str, Any]) -> list[str]:
    """One distilled line per Constitution article (title + load-bearing commitment)."""
    articles = constitution.get("articles") or []
    lines: list[str] = []
    for i, article in enumerate(articles):
        title = (
            _CONSTITUTION_ARTICLE_TITLES[i]
            if i < len(_CONSTITUTION_ARTICLE_TITLES)
            else article.get("title", f"Article {i + 1}")
        )
        commitment = _compact_article_commitment(article)
        if commitment:
            lines.append(f"- **{title}.** {commitment}")
        else:
            lines.append(f"- **{title}.**")
    return lines


def _compact_article_commitment(article: dict[str, Any]) -> str:
    """The single most load-bearing commitment of a Constitution article.

    For a ``pointer`` article that is the summary; for a ``text`` article the
    body's first sentence; for a ``ref-array`` article a count of the
    referenced decisions. Excerpted to keep each line on one screen row.
    """
    kind = article.get("kind")
    if kind == "pointer":
        return _excerpt(article.get("summary", ""), _COMPACT_CONSTITUTION_PROSE_CHARS)
    if kind == "ref-array":
        n_adr = len(article.get("adr_refs") or [])
        n_ae = len(article.get("ae_refs") or [])
        bits = []
        if n_adr:
            bits.append(f"{n_adr} ADR(s)")
        if n_ae:
            bits.append(f"{n_ae} AE(s)")
        return ("Governed by " + ", ".join(bits) + ".") if bits else ""
    return _excerpt(article.get("body", ""), _COMPACT_CONSTITUTION_PROSE_CHARS)


def _compact_intent_lines(intent: dict[str, Any]) -> list[str]:
    """The in-flight Intent's title + Desired Outcome — not the full body."""
    aid = intent.get("id", "")
    name = intent.get("name", "")
    status = intent.get("status", "?")
    desired = _excerpt(intent.get("desired_outcome", ""), _COMPACT_INTENT_PROSE_CHARS)
    lines = [
        f"## {aid}: {name}",
        "",
        f"**Status:** {status}",
        "",
    ]
    if desired:
        lines.append(f"**Desired outcome.** {desired}")
    else:
        lines.append("_This Intent declares no Desired Outcome._")
    return lines


# --------------------------------------------------------------------------- #
# Security Profile soft-layer emitter (WS-018 BR1-BR6 / IB-029).
#
# emit_security_profile_soft(ir) returns exactly 7 markdown fragments in
# canonical schema-field order. Sibling IB-030's aggregator composition
# joins them with "\n\n" and frames under per-SP `### SP-NNN — <title>` H3
# subsections (with the H3 -> H4 header rewrite happening in the composer,
# not here — this function returns H3 fragments).
# --------------------------------------------------------------------------- #


# Canonical SP field-group order — single source of truth. Mirrors the
# typed-field declaration order in security-profile.schema.yaml (IB-027);
# WS-018 BR2 pins this as normative. Each entry is
# (ir_field_name, header_text, kind) where kind is "string-array" (six
# entries; for Supply Chain the implementation reads
# ir["supply_chain"]["allowed_sources"]) or "owasp-matrix" (one entry).
_SECURITY_PROFILE_FIELD_GROUPS: tuple[tuple[str, str, str], ...] = (
    ("allowed_dataflows", "Allowed Dataflows", "string-array"),
    ("secret_stores", "Secret Stores", "string-array"),
    ("authn_methods", "Authn Methods", "string-array"),
    ("supply_chain", "Supply Chain", "string-array"),
    ("sast_tools", "SAST Tools", "string-array"),
    ("dast_tools", "DAST Tools", "string-array"),
    ("owasp_coverage", "OWASP Coverage", "owasp-matrix"),
)

_SP_EMPTY_PLACEHOLDER_BULLET = "- _(none declared)_"


def emit_security_profile_soft(ir: dict[str, Any]) -> list[str]:
    """Emit a Security Profile IR as 7 ordered AGENTS.md fragments (WS-018 BR1).

    Returns a list of exactly 7 markdown strings, one per typed-field group
    in WS-018 BR2's canonical order (Allowed Dataflows / Secret Stores /
    Authn Methods / Supply Chain / SAST Tools / DAST Tools / OWASP Coverage).
    Each fragment is self-contained: H3 header + body. Sibling IB-030's
    aggregator joins the seven with ``\\n\\n`` and frames under per-SP H3
    subsections.

    Dispatch is by tuple-entry kind:
      - ``string-array`` → six entries; each renders one ``- <entry>`` bullet
        per array element in IR insertion order (typed records render as
        their dict's ``name`` for the common case but the IR's parser-side
        contract for these arrays is string-of-records — at this milestone
        the lists are plain strings per the synthetic fixtures and the
        IB-028 dogfood SP-001 instance). Supply Chain reads the nested
        ``allowed_sources`` sub-array.
      - ``owasp-matrix`` → one entry; renders one
        ``- **<owasp_id>:** <mitigation_strategy>`` bullet per row in IR
        insertion order.

    Empty-array discipline: a typed-field array with zero entries renders
    a single ``- _(none declared)_`` placeholder bullet under its
    ``### ``-prefixed subsection. The subsection header is ALWAYS emitted;
    the subsection is NEVER omitted (WS-018 BR3).

    Determinism: dict iteration in CPython 3.7+ is insertion-ordered; no
    ``set()``, ``sorted()``, ``datetime.now()``, ``uuid.uuid4()``, or any
    process-state-dependent function is called. Fragments are pure
    functions of the IR (WS-018 BR6).
    """
    fragments: list[str] = []
    for field_name, header, kind in _SECURITY_PROFILE_FIELD_GROUPS:
        if field_name == "supply_chain":
            entries = (ir.get("supply_chain") or {}).get("allowed_sources", []) or []
        else:
            entries = ir.get(field_name, []) or []
        if kind == "string-array":
            fragments.append(_emit_security_profile_string_array(entries, header))
        else:  # "owasp-matrix"
            fragments.append(_emit_security_profile_owasp_matrix(entries, header))
    return fragments


def _emit_security_profile_string_array(entries: list, header: str) -> str:
    """String-array fragment (WS-018 BR4): H3 header + bulleted list.

    Each ``entries`` element renders as ``- {entry}`` verbatim in IR
    insertion order; no truncation, no markdown-escape (parser-side
    contract is that entries do not contain unescaped pipes / backticks).
    Empty array → single ``- _(none declared)_`` placeholder bullet
    (subsection ALWAYS emits per WS-018 BR3).
    """
    parts = [f"### {header}", ""]
    if not entries:
        parts.append(_SP_EMPTY_PLACEHOLDER_BULLET)
    else:
        for entry in entries:
            parts.append(f"- {entry}")
    return "\n".join(parts)


def _emit_security_profile_owasp_matrix(
    entries: list[dict[str, Any]], header: str
) -> str:
    """OWASP matrix fragment (WS-018 BR5): H3 header + bulleted list.

    Each ``entries`` row renders as ``- **{owasp_id}:** {mitigation_strategy}``
    in IR insertion order. Both fields are read via direct dict access (no
    ``.get`` defaults): a malformed row missing either field is a parser
    bug and the ``KeyError`` should bubble up loudly. Empty array → single
    ``- _(none declared)_`` placeholder bullet (subsection ALWAYS emits
    per WS-018 BR3).
    """
    parts = [f"### {header}", ""]
    if not entries:
        parts.append(_SP_EMPTY_PLACEHOLDER_BULLET)
    else:
        for row in entries:
            parts.append(f"- **{row['owasp_id']}:** {row['mitigation_strategy']}")
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _resolve_prose(value: Any) -> str:
    """purpose_and_scope is a string in AE; what_this_does is an object in WS.
    Normalize to a single prose string for excerpting.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("prose", "") or value.get("mechanism", "")
    return ""


def _excerpt(text: str, max_chars: int = _MAX_PROSE_CHARS) -> str:
    """Truncate long prose at the nearest sentence boundary under max_chars.
    Adds an ellipsis when truncation occurs.
    """
    if not text:
        return ""
    text = text.strip().replace("\n\n", " ").replace("\n", " ")
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    # Truncate at last sentence boundary if available
    last_period = cut.rfind(". ")
    if last_period > max_chars * 0.5:
        return cut[: last_period + 1] + " ..."
    return cut.rstrip() + " ..."


def _begin_marker(aid: str) -> str:
    return f"<!-- BEGIN dekspec-fragment: {aid} -->"


def _end_marker(aid: str) -> str:
    return f"<!-- END dekspec-fragment: {aid} -->"


def _header(ir: dict[str, Any], kind: str) -> str:
    src = ir.get("source", {}) or {}
    return (
        f"<!--\n"
        f"  Auto-generated by dekspec.constraint_compiler.emitters.agents_md\n"
        f"  Source {kind}: {src.get('path', '<unknown>')}\n"
        f"  Source SHA-256: {src.get('sha256', '<unknown>')}\n"
        f"  Compiled: {src.get('parsed_at', '<unknown>')}\n"
        f"  Schema: ir_schema_version={IR_SCHEMA_VERSION}, parser={PARSER_VERSION}, emitter={EMITTER_VERSION}\n"
        f"-->"
    )
