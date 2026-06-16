"""L-series linkage integrity checks (Python implementation).

v0.5.0 adds `propose_fixes()` + `apply_fixes()` for mechanical
linkage repairs. Other rule families remain advisory until they
land their own auto-fix logic.

Implements the cross-artifact consistency checks from
`/fidelity-audit` §AE Linkage integrity rules:

  - L1: ADR.related_architecture_elements refs resolve (each AE-NNN exists in the registry).
  - L3: WS.related_architecture_elements refs resolve.
  - L4: IC.parties[].ae_id refs resolve.
  - LX-DUP: Duplicate artifact IDs (e.g., two IC-001 files in the same dir).
  - LX-PARSE: Parse failures from SpecGraph.load() are surfaced as findings.

Each check returns Finding objects with:
  - severity: canonical Severity ('P0' | 'P1' | 'P2' | 'P3') per ADR-013
  - rule: short rule code (e.g., 'L1-ADR-AE-EXISTS')
  - artifact_id: which artifact owns the finding
  - message: human-readable description
  - fix_kind: 'mechanical' | 'semantic'
"""

from __future__ import annotations

import glob as _glob
import importlib.util as _importlib_util
import os as _os
import re
import shutil as _shutil
from dataclasses import dataclass, asdict
from datetime import date as _date
from pathlib import Path
from typing import Any

from ..constraint_compiler.graph import SpecGraph
from ..severity import P0, P1, P2, P3, Severity


# Audit-side legacy → canonical alias map (ADR-013). Distinct from the
# parser-side `ARTIFACT_SEVERITY_ALIAS_MAP` in `dekspec.severity` because
# the legacy audit vocabulary (`critical / important / minor`) does not
# overlap with the legacy artifact vocabulary (`blocking_pre_ib`, etc.).
# The CLI's deprecation-warning translator reuses this map (extending it
# with `"all": P3` at the CLI boundary, where `"all"` is a legacy CLI-flag
# value, not a legacy audit-emission value).
_AUDIT_SEVERITY_ALIAS_MAP: dict[str, Severity] = {
    "critical": P1,
    "important": P2,
    "minor": P3,
}

# Canonical-tier sort key. Lower int → higher priority (P0 first). Used
# by `audit_linkage` for its return-ordering and by the CLI's
# `--min-severity` filter for its threshold comparison. Module-level so
# the CLI can import + reuse it.
severity_order: dict[Severity, int] = {P0: 0, P1: 1, P2: 2, P3: 3}


@dataclass
class Finding:
    severity: Severity  # canonical 'P0' | 'P1' | 'P2' | 'P3' per ADR-013
    rule: str
    artifact_id: str
    message: str
    fix_kind: str = "semantic"  # 'mechanical' | 'semantic'
    file_path: str | None = None

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class Fix:
    """A mechanical, auto-applicable repair for a finding.

    Each Fix describes a single line edit in a single file: replace
    `before` with `after`. apply_fixes() does the writes.
    """

    rule: str  # rule code that produced this fix (e.g., L7-ADR-SUPER-MIRROR)
    artifact_id: str  # the artifact whose source file is being edited
    file_path: str  # absolute path to the source file
    section: str  # which IR field is being repaired (e.g., 'related_wss')
    added_ids: list[str]  # the IDs being inserted
    before: str  # the line as it currently exists
    after: str  # the line as it would be after fix application
    line_number: int  # 1-based line number of the line being edited

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def audit_linkage(
    repo_root: str | Path,
    dekspec_root: str = "dekspec",
    profile: str | None = None,
) -> list[Finding]:
    """Run all L-series linkage checks against a repo's spec graph.

    Loads the graph, runs each check, and returns findings sorted by severity
    (critical first, then important, then minor) and rule code.

    `profile` selects which audit-rule profile to enforce. None (the default)
    resolves to "v1" — the baseline manifest at
    `tooling/dekspec/fidelity_audit/profiles/v1.yaml` enumerating all 50
    rule codes currently emitted by this module. Findings whose `rule` is
    NOT in the profile's rule set are filtered out before return; v2-and-
    beyond profiles can also override rule parameters (consulted by the
    individual check functions where applicable).
    """
    # Resolve the active profile. Lazy import keeps the registry optional
    # for callers that pass an explicit (already-resolved) profile name.
    # `prose_shape` is also imported lazily — it imports `Finding` from this
    # module, so a top-level import would form a circular import.
    from . import prose_shape, spec_review_rules
    from .profiles import load_profile

    active_profile = load_profile(profile or "v1")

    graph = SpecGraph.load(repo_root, dekspec_root=dekspec_root)
    findings: list[Finding] = []

    findings.extend(_lx_parse_failures(graph))
    findings.extend(_lx_duplicate_ids(graph))
    findings.extend(_l1_adr_ae_links(graph))
    findings.extend(_l3_ws_ae_links(graph))
    findings.extend(_l4_ic_ae_links(graph))
    findings.extend(_l5_ib_ws_links(graph))
    findings.extend(_l7_adr_supersession_integrity(graph))
    findings.extend(_t_artifact_completeness(graph))
    findings.extend(_d_artifact_drift(graph))
    findings.extend(_l7_intent_linkage(graph))
    findings.extend(_t_bead_failure_class_valid(graph))
    findings.extend(_l8_mission_intent_bidirectional(graph))
    findings.extend(_l8_mission_intent_serialized(graph))
    findings.extend(
        _l14_intent_backlog_active(
            graph,
            threshold=active_profile.param(
                "L14-INT-BACKLOG-ACTIVE", "threshold", _INT_BACKLOG_ACTIVE_THRESHOLD
            ),
        )
    )
    findings.extend(_l13_intent_lock_coherence(graph))
    findings.extend(_l9_verification_resolves(graph))
    findings.extend(_l10_glossary_coverage(graph))
    findings.extend(
        _l11_mission_stale(
            graph,
            days_threshold=active_profile.param(
                "L11-MSN-STALE", "days_threshold", _MISSION_STALE_DAYS
            ),
        )
    )
    findings.extend(_l12_ws_blocking_pre_ib_clean(graph))
    findings.extend(_d15_prose_drift_wsicib(graph))
    # T-PROSE-* prose-shape heuristic family (INT-065 / IB-109) — advisory.
    findings.extend(prose_shape.prose_shape_rules(graph, active_profile))
    # SPEC-REVIEW reviewer-dispatch family (INT-141 / IB-126) — advisory P2.
    findings.extend(spec_review_rules.spec_review_rules(graph, active_profile))
    findings.extend(_t_glossary_self_consistency(graph))
    findings.extend(_t_vision_completeness(graph))
    findings.extend(_t_constitution_article_present(graph))
    findings.extend(_t_constitution_article_populated(graph))
    findings.extend(_l_constitution_article_1_sv_ref(graph))
    findings.extend(_l_constitution_article_4_adr_refs(graph))
    findings.extend(_l_constitution_article_7_boundary_refs(graph))
    findings.extend(_t_sec_owasp_coverage_gap(graph))
    findings.extend(_t_sec_supply_chain_empty(graph))
    findings.extend(_t_sec_secret_store_enum(graph))
    findings.extend(_t_sec_authn_method_consistency(graph))
    # Supply-chain hygiene advisory (ds-tygt) — sibling to the T-SEC-* family,
    # but consults repo_root, so it is deliberately NOT named T-SEC-*.
    findings.extend(_t_supply_chain_new_dependency(graph))
    findings.extend(_l_no_draft_in_main(graph))
    findings.extend(_l_registry_append_only(graph))
    # T-APPROVAL-GATE (INT-021) is profile-aware: the rule body reads
    # `approval_gates` from the active profile and yields nothing when that
    # block is absent (the default v1 profile). It is registered only in
    # team.yaml, so the profile-filter below also drops it under v1.
    findings.extend(_t_approval_gate(graph, active_profile))
    findings.extend(_l15_index_file_coherence(graph))
    findings.extend(_si01_date_freshness(graph))
    # T-STATUS-* status-maturity coherence family (ADR-020 / INT-070).
    findings.extend(_t_status_inversion(graph))
    findings.extend(_t_status_lag(graph))
    findings.extend(_t_status_lock_ready(graph))
    findings.extend(_t_status_ib_folder(graph))
    # T-SKILL-* — skill catalog hygiene family (Phase B of
    # INT-provisional-skill-flag-normalization).
    findings.extend(_t_skill_frontmatter_normal(graph))
    findings.extend(_t_skill_help_mode_present(graph))
    findings.extend(_t_skill_arg_hint_complete(graph))
    # L-PROVISIONAL-* — provisional incubation visibility
    # (INT-provisional-audit-treatment per MSN-014).
    findings.extend(_l_provisional_tree_present(graph))
    findings.extend(
        _l_provisional_stale(
            graph,
            days_threshold=active_profile.param(
                "L-PROVISIONAL-STALE",
                "days_threshold",
                _PROVISIONAL_STALE_DAYS_DEFAULT,
            ),
        )
    )
    # L-COW-SIBLING-COLLISION — copy-on-write sibling-collision
    # detection (INT-082 MVP slice).
    findings.extend(_l_cow_sibling_collision(graph))
    # T-COW-CANONICAL-EDITED — direct-edit-bypass detection
    # (second audit rule from INT-082).
    findings.extend(_t_cow_canonical_edited(graph))
    # L16-INT-BEADS-BEFORE-ACCEPT — Path A accept-gate bead traceability
    # (INT-105 / ds-xu6g).
    findings.extend(_l16_int_beads_before_accept(graph))
    # T-VERIFICATION-OUTCOME — outcome-test discipline at Intent level
    # (INT-119 / ADR-029). Walks graph.intents() advisory P2.
    findings.extend(_t_verification_outcome(graph))
    # T-CONST-CLASS-LANE-* + L-CONST-CLASS-LANE-INTENT-EXISTS
    # (INT-125 / ds-zhhk).
    findings.extend(_t_const_class_lane_coverage_unique(graph))
    findings.extend(_t_const_class_lane_thresholds_well_formed(graph))
    findings.extend(_l_const_class_lane_intent_exists(graph))
    # INT-128 / ds-provisional-promotion-guardrails — fires P3 advisory
    # on canonical Missions stale TODO without children.
    findings.extend(_t_mission_canonical_without_child(graph))
    # INT-168 (δ / MSN-020) — fires P3 advisory on a non-terminal,
    # Mission-less Intent whose body lacks a `## Non-Goals` section.
    findings.extend(_t_intent_missing_non_goals(graph))
    # INT-169 (ε / MSN-020) — fires P3 advisory on a >=ACCEPTED non-terminal
    # `type: bug` Intent that carries neither a populated Reproduction
    # section nor a Non-Reproducible Waiver section.
    findings.extend(_t_bug_missing_repro_gate(graph))
    # INT-171 (η / MSN-020) — fires P3 advisory on a non-terminal,
    # high-blast-radius IC (>=2 consumers OR >=2 governing ADRs) whose body
    # lacks a populated `## Options Considered / Rejected Rationale` section.
    findings.extend(_t_ic_missing_options(graph))

    # Filter to rules enabled by the active profile. Rules not enumerated
    # in profile.rules are dropped silently (the underlying check still ran;
    # the finding is suppressed). When v2-and-beyond profiles disable a rule
    # this is the seam that honors that.
    findings = [f for f in findings if f.rule in active_profile.rules]

    findings.sort(key=lambda f: (severity_order.get(f.severity, 99), f.rule, f.artifact_id))
    return findings


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #


def _lx_parse_failures(graph: SpecGraph) -> list[Finding]:
    out: list[Finding] = []
    for fail in graph.parse_failures():
        out.append(
            Finding(
                severity=P1,
                rule="LX-PARSE",
                artifact_id=Path(fail.path).name,
                message=f"Parse failed ({fail.error_type}): {fail.message[:200]}",
                fix_kind="semantic",
            )
        )
    return out


# Lightweight regex over an IB markdown file to extract its parent WS ID
# (the `**Spec:** <path-to-WS-NNN-…>.md` line). Used only by LX-DUP so we
# can group IBs by (parent_ws, ib_id) without paying for a full parse.
# Tolerant of: optional path prefix, optional bracket links, slug variability.
_IB_SPEC_PARENT_RE = re.compile(r"^\*\*Spec:\*\*\s.*?(WS-\d{3,})", re.MULTILINE)


def _extract_ib_parent_ws(path: Path) -> str | None:
    """Best-effort extraction of an IB's parent WS ID from its **Spec:** line.

    Returns None if the line is missing/malformed — that's a separate
    defect surfaced by L5-IB-SPEC-MISSING. LX-DUP falls back to grouping
    unknown-parent IBs together so a missing-spec defect doesn't *also*
    hide a real same-parent duplicate.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None
    m = _IB_SPEC_PARENT_RE.search(content)
    return m.group(1) if m else None


def _lx_duplicate_ids(graph: SpecGraph) -> list[Finding]:
    """SpecGraph keys IRs by id, silently overwriting duplicates. To detect
    duplicates we re-walk each dekspec directory and group by parsed id.
    Uses graph.dekspec_dir (set by SpecGraph.load) so this respects the
    --dekspec-root flag.

    IBs are the exception: their IDs are unique only within a parent
    Working Spec (an IB-001 under WS-032 is a different artifact from an
    IB-001 under WS-033). For impl-briefs/ we therefore group by
    (parent_ws_id, ib_id) — extracted via :func:`_extract_ib_parent_ws`
    from each file's `**Spec:**` line. See
    ``ds-audit-lx-dup-ignores-ib-ws-scope-ae1`` for the rationale.
    """
    out: list[Finding] = []
    dekspec_dir = graph.dekspec_dir
    if dekspec_dir is None or not dekspec_dir.exists():
        return out
    # (dirname, prefix, recursive, parent_scoped)
    # parent_scoped=True ⇒ group by (parent_ws, artifact_id) instead of
    # bare artifact_id. Only IBs are parent-scoped today; beads will be
    # the next addition once they live in the artifact tree.
    dirs = [
        ("adrs", "ADR-", False, False),
        ("architecture-elements", "AE-", False, False),
        ("working-specs", "WS-", False, False),
        ("interface-contracts", "IC-", False, False),
        ("impl-briefs", "IB-", True, True),
        ("intents", "INT-", True, False),
        ("missions", "MSN-", True, False),
    ]
    for dirname, prefix, recursive, parent_scoped in dirs:
        d = dekspec_dir / dirname
        if not d.exists():
            continue
        # Keys are either bare artifact_id (global namespaces) or
        # (parent_id, artifact_id) tuples (parent-scoped namespaces).
        seen: dict[Any, list[str]] = {}
        iterator = d.rglob(f"{prefix}*.md") if recursive else d.glob(f"{prefix}*.md")
        for p in iterator:
            stem = p.stem
            parts = stem.split("-", 2)
            if len(parts) < 2:
                continue
            artifact_id = f"{parts[0]}-{parts[1]}"
            try:
                rel = p.relative_to(d)
            except ValueError:
                rel = Path(p.name)
            if parent_scoped:
                parent_id = _extract_ib_parent_ws(p) or "<unknown>"
                key: Any = (parent_id, artifact_id)
            else:
                key = artifact_id
            seen.setdefault(key, []).append(str(rel))
        for key, files in seen.items():
            if len(files) <= 1:
                continue
            if isinstance(key, tuple):
                parent_id, artifact_id = key
                scope_phrase = f"share id {artifact_id} under parent {parent_id}"
            else:
                artifact_id = key
                scope_phrase = f"share id {artifact_id}"
            out.append(
                Finding(
                    severity=P1,
                    rule="LX-DUP",
                    artifact_id=artifact_id,
                    message=(
                        f"Duplicate artifact ID — {len(files)} files in {dirname}/ "
                        f"{scope_phrase}: {', '.join(sorted(files))}. "
                        f"SpecGraph keeps only one (last loaded); audits and emitters see only "
                        f"that one. Renumber or merge."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


def _l1_adr_ae_links(graph: SpecGraph) -> list[Finding]:
    """L1: every ADR must link to at least one AE; each linked AE must exist."""
    out: list[Finding] = []
    for adr in graph.adrs():
        adr_id = adr["id"]
        related = adr.get("related_architecture_elements", [])
        if not related:
            out.append(
                Finding(
                    severity=P3,
                    rule="L1-ADR-AE-MISSING",
                    artifact_id=adr_id,
                    message=(
                        "ADR has no Related Architecture Elements (L1 mandatory). "
                        "Pre-migration ADRs are grandfathered as minor; backfill expected at "
                        "next /write-adr --revise."
                    ),
                    fix_kind="semantic",
                )
            )
            continue
        for ref in related:
            ae_id = ref["id"]
            if not graph.has(ae_id):
                out.append(
                    Finding(
                        severity=P1,
                        rule="L1-ADR-AE-EXISTS",
                        artifact_id=adr_id,
                        message=(
                            f"ADR references AE {ae_id} which does not exist in the registry "
                            f"(checked under architecture-elements/). Either rename the ref to "
                            f"the correct AE, or author AE {ae_id}."
                        ),
                        fix_kind="semantic",
                    )
                )
    return out


def _l3_ws_ae_links(graph: SpecGraph) -> list[Finding]:
    """L3: every WS must link to at least one AE; each linked AE must exist."""
    out: list[Finding] = []
    for ws in graph.wses():
        ws_id = ws["id"]
        if ws.get("status") == "DEPRECATED":
            continue  # don't flag DEPRECATED WSes for missing linkage
        related = ws.get("related_architecture_elements", [])
        if not related:
            out.append(
                Finding(
                    severity=P2,
                    rule="L3-WS-AE-MISSING",
                    artifact_id=ws_id,
                    message=(
                        "WS has no Related Architecture Elements (L3 mandatory at LOCK). "
                        "Backfill expected before next status advance."
                    ),
                    fix_kind="semantic",
                )
            )
            continue
        for ref in related:
            ae_id = ref["id"]
            if not graph.has(ae_id):
                out.append(
                    Finding(
                        severity=P1,
                        rule="L3-WS-AE-EXISTS",
                        artifact_id=ws_id,
                        message=(f"WS references AE {ae_id} which does not exist in the registry."),
                        fix_kind="semantic",
                    )
                )
    return out


def _l4_ic_ae_links(graph: SpecGraph) -> list[Finding]:
    """L4: each IC.parties[].ae_id must resolve to an existing AE."""
    out: list[Finding] = []
    for ic in graph.ics():
        ic_id = ic["id"]
        if ic.get("status") == "DEPRECATED":
            continue
        ae_ids = graph.aes_of_ic(ic_id)
        if not ae_ids:
            out.append(
                Finding(
                    severity=P3,
                    rule="L4-IC-AE-MISSING",
                    artifact_id=ic_id,
                    message=(
                        "IC has no parties[].ae_id populated. Provider/Consumer AE links are "
                        "the source-of-truth for CI gate scoping (via implements_globs). "
                        "Author the ### Provider AE / ### Consumer AEs subsections in §Parties."
                    ),
                    fix_kind="semantic",
                )
            )
            continue
        for ae_id in ae_ids:
            if not graph.has(ae_id):
                out.append(
                    Finding(
                        severity=P1,
                        rule="L4-IC-AE-EXISTS",
                        artifact_id=ic_id,
                        message=(
                            f"IC references AE {ae_id} (parties[].ae_id) which does not exist "
                            f"in the registry."
                        ),
                        fix_kind="semantic",
                    )
                )
    return out


def propose_fixes(
    repo_root: str | Path,
    dekspec_root: str = "dekspec",
) -> list[Fix]:
    """Compute mechanical fixes from the current graph state.

    Two families as of v0.27.0:
      - L7-ADR-SUPER-MIRROR (since v0.27.0): add ADR.superseded_by back-pointer.
      - L8-MSN-INT-MIRROR / L8-INT-MSN-MIRROR (since v0.27.0): add Intent.mission
        back-pointer / append a row to Mission.intent_queue.

    Other rule families produce findings but no auto-fix proposals; the
    engineer applies them by hand. Returns Fix objects ready for `apply_fixes()`.
    """
    graph = SpecGraph.load(repo_root, dekspec_root=dekspec_root)
    out: list[Fix] = []
    out.extend(_propose_l7_supersession_fixes(graph))
    out.extend(_propose_l8_mirror_fixes(graph))
    out.extend(_propose_si01_date_fixes(graph))
    return out


def apply_fixes(fixes: list[Fix], dry_run: bool = True) -> dict[str, Any]:
    """Apply fixes to disk. dry_run=True (default) returns the proposal
    without modifying any file.

    Multiple fixes for the same file are applied in one read-modify-write
    pass, in the order they appear in the input list. If a fix's `before`
    text isn't found in the current file content (e.g., a previous fix
    already changed it, or the file was edited between propose and apply),
    that fix is skipped and reported in the result.

    Returns a summary dict:
      - proposed: total Fix count
      - applied: count of fixes successfully applied (always 0 if dry_run)
      - skipped_not_found: count of fixes whose `before` wasn't in the file
      - files_touched: count of files modified (always 0 if dry_run)
    """
    by_file: dict[str, list[Fix]] = {}
    for fix in fixes:
        by_file.setdefault(fix.file_path, []).append(fix)

    applied = 0
    skipped_not_found = 0
    files_touched = 0

    for path, file_fixes in by_file.items():
        path_obj = Path(path)
        if not path_obj.exists():
            skipped_not_found += len(file_fixes)
            continue
        text = path_obj.read_text(encoding="utf-8")
        original = text
        for fix in file_fixes:
            if fix.before in text:
                text = text.replace(fix.before, fix.after, 1)
                applied += 1
            else:
                skipped_not_found += 1
        if text != original and not dry_run:
            path_obj.write_text(text, encoding="utf-8")
            files_touched += 1

    return {
        "proposed": len(fixes),
        "applied": applied,
        "skipped_not_found": skipped_not_found,
        "files_touched": files_touched,
        "dry_run": dry_run,
    }


def _l5_ib_ws_links(graph: SpecGraph) -> list[Finding]:
    """L5 (IB→WS / IB→AE checks via graph). Reads each IB's `spec` field
    (the canonical L5 source per the IB IR) plus the optional `source_aes`
    field for direct AE linkage; otherwise falls back to transitive
    AE resolution via the parent WS.

      - L5-IB-SPEC-MISSING (important): IB has neither `spec` (no `**Spec:**`
                                        line resolving to a WS) NOR a
                                        resolvable `intent` (no `**Intent:**`
                                        line resolving to an INT). One of the
                                        two parent links is required.
      - L5-IB-WS-EXISTS    (critical):  spec.id not in registry.
      - L5-IB-INTENT-EXISTS (critical): intent.id set but not in registry.
      - L5-IB-AE-MISSING   (minor):     no source_aes AND parent WS has no
                                        related_architecture_elements — the
                                        IB cannot resolve any AE.
      - L5-IB-DEPENDS-EXISTS (critical): each depends_on IB must resolve.
    """
    out: list[Finding] = []
    for ib in graph.ibs():
        ib_id = ib["id"]
        spec = ib.get("spec") or {}
        ws_id = spec.get("id")
        intent = ib.get("intent") or {}
        int_id = intent.get("id")

        # L5-IB-SPEC-MISSING fires only when BOTH parent links are absent or
        # unresolvable. A populated, resolvable intent satisfies the rule
        # (Mission-less single-IB pattern — IB decomposes directly from an
        # Intent with no intervening WS; e.g., IB-038 ← INT-023).
        intent_satisfies = bool(int_id) and graph.has(int_id)

        if not ws_id and not intent_satisfies:
            out.append(
                Finding(
                    severity=P2,
                    rule="L5-IB-SPEC-MISSING",
                    artifact_id=ib_id,
                    message=(
                        "IB has neither a `**Spec:**` line resolving to a WS nor "
                        "an `**Intent:**` line resolving to an existing Intent. "
                        "Add one: `**Spec:** `path/to/WS-NNN-*.md`` (WS-backed "
                        "IB) or ensure the `**Intent:**` line points at an "
                        "existing `INT-NNN` artifact (Intent-only decomposition)."
                    ),
                    fix_kind="semantic",
                )
            )
        elif ws_id and not graph.has(ws_id):
            out.append(
                Finding(
                    severity=P1,
                    rule="L5-IB-WS-EXISTS",
                    artifact_id=ib_id,
                    message=(
                        f"IB references parent {ws_id} which does not exist in "
                        f"the registry. Either fix the path or author {ws_id}."
                    ),
                    fix_kind="semantic",
                )
            )

        if int_id and not graph.has(int_id):
            out.append(
                Finding(
                    severity=P1,
                    rule="L5-IB-INTENT-EXISTS",
                    artifact_id=ib_id,
                    message=(
                        f"IB references parent {int_id} which does not exist in "
                        f"the registry. Either fix the path or author {int_id}."
                    ),
                    fix_kind="semantic",
                )
            )

        for ref_id in ib.get("source_aes", []) or []:
            ae_id = ref_id["id"] if isinstance(ref_id, dict) else ref_id
            if not graph.has(ae_id):
                out.append(
                    Finding(
                        severity=P1,
                        rule="L5-IB-AE-EXISTS",
                        artifact_id=ib_id,
                        message=(
                            f"IB.source_aes references {ae_id} which does not "
                            f"exist in the registry."
                        ),
                        fix_kind="semantic",
                    )
                )

        if not ib.get("source_aes"):
            ws = graph.by_id(ws_id) if ws_id else None
            if ws is not None and not (ws.get("related_architecture_elements") or []):
                out.append(
                    Finding(
                        severity=P3,
                        rule="L5-IB-AE-MISSING",
                        artifact_id=ib_id,
                        message=(
                            f"IB has no `Source AEs:` line and its parent {ws_id} "
                            f"has no Related Architecture Elements. The IB cannot "
                            f"resolve any AE. Add Source AEs to the IB header or "
                            f"backfill {ws_id}'s Related AE section."
                        ),
                        fix_kind="semantic",
                    )
                )

        for dep_id in ib.get("depends_on", []) or []:
            if not graph.has(dep_id):
                out.append(
                    Finding(
                        severity=P1,
                        rule="L5-IB-DEPENDS-EXISTS",
                        artifact_id=ib_id,
                        message=(
                            f"IB.depends_on references {dep_id} which does not "
                            f"exist in the registry."
                        ),
                        fix_kind="semantic",
                    )
                )

    return out


def _l7_adr_supersession_integrity(graph: SpecGraph) -> list[Finding]:
    """L7: ADR.supersession references must resolve, mirror, and not cycle.

    - L7-ADR-SUPER-EXISTS: each ADR ID in supersedes/superseded_by exists.
    - L7-ADR-SUPER-SELF: an ADR cannot supersede itself.
    - L7-ADR-SUPER-MIRROR: if A.supersedes contains B, B.superseded_by contains A.
    - L7-ADR-SUPER-CYCLE: the supersession graph (supersedes edges) is acyclic.
    - L7-ADR-SUPER-STATUS: ADRs with status=SUPERSEDED must populate
      supersession.superseded_by (per schema description).
    """
    out: list[Finding] = []
    adrs = list(graph.adrs())
    super_edges: dict[str, list[str]] = {}  # supersedes edges, for cycle check
    for adr in adrs:
        adr_id = adr["id"]
        sup = adr.get("supersession") or {}
        supersedes = sup.get("supersedes", []) or []
        superseded_by = sup.get("superseded_by", []) or []

        for ref_id in supersedes:
            if ref_id == adr_id:
                out.append(
                    Finding(
                        severity=P1,
                        rule="L7-ADR-SUPER-SELF",
                        artifact_id=adr_id,
                        message=f"ADR supersedes itself ({ref_id}). Remove or correct.",
                        fix_kind="semantic",
                    )
                )
            elif not graph.has(ref_id):
                out.append(
                    Finding(
                        severity=P1,
                        rule="L7-ADR-SUPER-EXISTS",
                        artifact_id=adr_id,
                        message=(
                            f"supersedes references {ref_id} which does not exist in the registry."
                        ),
                        fix_kind="semantic",
                    )
                )
            else:
                target = graph.by_id(ref_id) or {}
                target_sup = target.get("supersession") or {}
                if adr_id not in (target_sup.get("superseded_by", []) or []):
                    out.append(
                        Finding(
                            severity=P2,
                            rule="L7-ADR-SUPER-MIRROR",
                            artifact_id=ref_id,
                            message=(
                                f"{adr_id} supersedes {ref_id} but {ref_id}.superseded_by "
                                f"does not list {adr_id}. Add the back-pointer."
                            ),
                            fix_kind="semantic",
                        )
                    )

        for ref_id in superseded_by:
            if ref_id == adr_id:
                out.append(
                    Finding(
                        severity=P1,
                        rule="L7-ADR-SUPER-SELF",
                        artifact_id=adr_id,
                        message=f"ADR is superseded_by itself ({ref_id}). Remove or correct.",
                        fix_kind="semantic",
                    )
                )
            elif not graph.has(ref_id):
                out.append(
                    Finding(
                        severity=P1,
                        rule="L7-ADR-SUPER-EXISTS",
                        artifact_id=adr_id,
                        message=(
                            f"superseded_by references {ref_id} which does not exist in the registry."
                        ),
                        fix_kind="semantic",
                    )
                )

        if adr.get("status") == "SUPERSEDED" and not superseded_by:
            out.append(
                Finding(
                    severity=P2,
                    rule="L7-ADR-SUPER-STATUS",
                    artifact_id=adr_id,
                    message=(
                        "ADR.status is SUPERSEDED but supersession.superseded_by is empty. "
                        "Per schema, populate superseded_by with the ADR ID(s) that replace this one."
                    ),
                    fix_kind="semantic",
                )
            )

        super_edges[adr_id] = [r for r in supersedes if r != adr_id and graph.has(r)]

    cycles = _find_cycles(super_edges)
    seen_cycles: set[tuple[str, ...]] = set()
    for cycle in cycles:
        key = tuple(sorted(cycle))
        if key in seen_cycles:
            continue
        seen_cycles.add(key)
        out.append(
            Finding(
                severity=P1,
                rule="L7-ADR-SUPER-CYCLE",
                artifact_id=cycle[0],
                message=(
                    f"Supersession cycle detected: {' -> '.join(cycle + (cycle[0],))}. "
                    f"Break the cycle by correcting one of the supersedes references."
                ),
                fix_kind="semantic",
            )
        )
    return out


def _find_cycles(edges: dict[str, list[str]]) -> list[tuple[str, ...]]:
    """Return distinct cycles in a directed graph using DFS."""
    cycles: list[tuple[str, ...]] = []
    visited: set[str] = set()
    stack_index: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in stack_index:
            cycle_start = stack_index[node]
            cycles.append(tuple(stack[cycle_start:]))
            return
        if node in visited:
            return
        stack_index[node] = len(stack)
        stack.append(node)
        for nxt in edges.get(node, []):
            visit(nxt)
        stack.pop()
        del stack_index[node]
        visited.add(node)

    for node in edges:
        if node not in visited:
            visit(node)
    return cycles


# --------------------------------------------------------------------------- #
# T-series — structural-completeness checks (artifact-level)
# --------------------------------------------------------------------------- #
#
# Per the audit-v2 spec (skills/fidelity-audit/SKILL.md), the
# T-series enforces that each artifact's IR contains the structural fields it
# needs to be useful. T10 (subtype enum) is already caught by schema validation;
# the remaining T-checks live here as audit-time content presence checks.

_AE_SUBTYPES_REQUIRING_VIEWS = {
    "system",
    "subsystem",
    "container",
    "pipeline",
    "platform_concern",
}


def _t_artifact_completeness(graph: SpecGraph) -> list[Finding]:
    """T-series structural completeness across AE / WS / ADR / IB.

      AE rules:
        - T11-AE-BOUNDARY (important): boundaries_and_non_goals must contain
          at least one inside item AND one non_goal with a `why` clause.
        - T12-AE-VIEWS (minor): for subtypes that need views (System, Subsystem,
          Container, Pipeline, Platform Concern) the AE should have a Views
          section with content (a diagram or an explicit absence justification).
        - T-AE-BOUNDARIES-MISSING (minor): advisory — the AE carries no
          three-tier `boundaries` block (always_do / ask_first / never_do).
        - T-AE-PURPOSE (minor): purpose_and_scope content present.
        - T-AE-RESPONSIBILITIES (minor): at least one responsibility entry.

      WS rules:
        - T20-WS-BUSINESS-RULES (important): at least one business rule.
        - T21-WS-FAILURE-BEHAVIOR (important): at least one failure-behavior entry.

      ADR rules:
        - T30-ADR-DECISION (critical): §Decision content present.
        - T31-ADR-VALIDATION (minor): §Validation content present (raw_prose
          for grandfathered ADRs is OK).

      IB rules:
        - T40-IB-GOAL (important): §Goal content present.
        - T41-IB-DONE-WHEN (important): at least one Done When criterion.

    DEPRECATED artifacts are skipped for non-critical T-checks.
    """
    out: list[Finding] = []

    for ae in graph.aes():
        ae_id = ae["id"]
        if ae.get("status") == "DEPRECATED":
            continue
        bng = ae.get("boundaries_and_non_goals") or {}
        inside = bng.get("inside") or []
        non_goals = bng.get("non_goals") or []
        non_goals_with_why = [n for n in non_goals if n.get("why")]
        if not inside or not non_goals_with_why:
            out.append(
                Finding(
                    severity=P2,
                    rule="T11-AE-BOUNDARY",
                    artifact_id=ae_id,
                    message=(
                        f"AE.boundaries_and_non_goals incomplete (inside={len(inside)}, "
                        f"non_goals_with_why={len(non_goals_with_why)}). T11 requires ≥1 "
                        f"inside item AND ≥1 non-goal with a `why` clause — author as "
                        f"`- **Name.** prose.` (bold-led, period-split) OR "
                        f"`- text — reason` (em-dash separator). Both forms are parsed."
                    ),
                    fix_kind="semantic",
                )
            )

        subtype = (ae.get("subtype") or "").lower().replace("/", "_").replace(" ", "_")
        views = ae.get("views") or {}
        has_views = bool(views.get("diagrams")) or bool(
            (views.get("absence_justification") or "").strip()
        )
        if subtype in _AE_SUBTYPES_REQUIRING_VIEWS and not has_views:
            out.append(
                Finding(
                    severity=P3,
                    rule="T12-AE-VIEWS",
                    artifact_id=ae_id,
                    message=(
                        f"AE subtype={ae.get('subtype')} should have a `## Views` "
                        f"section with at least one architectural view OR an explicit "
                        f"absence justification (per audit-v2 T12)."
                    ),
                    fix_kind="semantic",
                )
            )

        boundaries = ae.get("boundaries") or {}
        if not any(boundaries.get(k) for k in ("always_do", "ask_first", "never_do")):
            out.append(
                Finding(
                    severity=P3,
                    rule="T-AE-BOUNDARIES-MISSING",
                    artifact_id=ae_id,
                    message=(
                        f"AE {ae_id} carries no three-tier `boundaries` block "
                        f"(always_do / ask_first / never_do). Declaring one is "
                        f"advisory — the block is optional per ADR-014's per-AE "
                        f"boundary surface; this finding does not gate `doctor`."
                    ),
                    fix_kind="semantic",
                )
            )

        if not (ae.get("purpose_and_scope") or "").strip():
            out.append(
                Finding(
                    severity=P3,
                    rule="T-AE-PURPOSE",
                    artifact_id=ae_id,
                    message="AE has no §Purpose and Scope content.",
                    fix_kind="semantic",
                )
            )

        if not (ae.get("responsibilities") or []):
            out.append(
                Finding(
                    severity=P3,
                    rule="T-AE-RESPONSIBILITIES",
                    artifact_id=ae_id,
                    message="AE has no §Responsibilities entries.",
                    fix_kind="semantic",
                )
            )

    for ws in graph.wses():
        ws_id = ws["id"]
        if ws.get("status") == "DEPRECATED":
            continue
        if not (ws.get("business_rules") or []):
            out.append(
                Finding(
                    severity=P2,
                    rule="T20-WS-BUSINESS-RULES",
                    artifact_id=ws_id,
                    message="WS has no §Business Rules entries (T20 requires ≥1).",
                    fix_kind="semantic",
                )
            )
        if not (ws.get("failure_behavior") or []):
            out.append(
                Finding(
                    severity=P2,
                    rule="T21-WS-FAILURE-BEHAVIOR",
                    artifact_id=ws_id,
                    message="WS has no §Failure Behavior entries (T21 requires ≥1).",
                    fix_kind="semantic",
                )
            )

    for adr in graph.adrs():
        adr_id = adr["id"]
        if adr.get("status") in {"DEPRECATED", "SUPERSEDED"}:
            continue
        if not (adr.get("decision") or "").strip():
            out.append(
                Finding(
                    severity=P1,
                    rule="T30-ADR-DECISION",
                    artifact_id=adr_id,
                    message="ADR has no §Decision content. The decision statement is the ADR's reason for existing.",
                    fix_kind="semantic",
                )
            )
        validation = adr.get("validation") or {}
        if not any(
            validation.get(k, "").strip()
            for k in ("observable_confirmation", "reconsideration_triggers", "raw_prose")
        ):
            out.append(
                Finding(
                    severity=P3,
                    rule="T31-ADR-VALIDATION",
                    artifact_id=adr_id,
                    message=(
                        "ADR has no §Validation content (neither the post-2026-04-24 split "
                        "form nor grandfathered raw_prose form)."
                    ),
                    fix_kind="semantic",
                )
            )

    for ib in graph.ibs():
        ib_id = ib["id"]
        if ib.get("status") == "DEPRECATED":
            continue
        if not (ib.get("goal") or "").strip():
            out.append(
                Finding(
                    severity=P2,
                    rule="T40-IB-GOAL",
                    artifact_id=ib_id,
                    message="IB has no §Goal content.",
                    fix_kind="semantic",
                )
            )
        if not (ib.get("done_when") or []):
            out.append(
                Finding(
                    severity=P2,
                    rule="T41-IB-DONE-WHEN",
                    artifact_id=ib_id,
                    message="IB has no §Done When acceptance criteria.",
                    fix_kind="semantic",
                )
            )

    return out


# --------------------------------------------------------------------------- #
# D-series — content-drift checks
# --------------------------------------------------------------------------- #
#
# D17 — no measurable quality targets in AE prose (route to WS).
# D18 — no decision rationale in AE prose (route to linked ADR).
# Both run on AE.purpose_and_scope, AE.responsibilities, AE.key_concepts,
# AE.constraints_and_quality_notes prose. A finding's "snippet" includes
# enough context that the engineer can locate and re-route the content.

# Numeric values with units. The unit set follows audit-v2 D17 + adds tokens/cents.
_D17_NUMERIC_UNIT = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*"
    r"(ms|μs|us|s|min|hours?|days?|weeks?|"
    r"MiB|GiB|TiB|KiB|MB|GB|TB|KB|"
    r"tokens?|req(?:uests?)?/s|qps|rps|"
    r"%|pp|bps|gbps|mbps|kbps)\b",
    re.IGNORECASE,
)

# Rationale-marker phrases. Looser regex; we filter false positives by
# requiring the phrase to appear in a sentence that does NOT also cite an ADR.
_D18_RATIONALE_PHRASES = re.compile(
    r"\b("
    r"we chose|"
    r"the tradeoff(?: is| was)|"
    r"the rationale(?: is| was|:)|"
    r"instead of choosing|"
    r"rather than (using|choosing|adopting)|"
    r"to avoid (the|a|having)|"
    r"the alternative was|"
    r"considered (alternatives?|other options?)|"
    r"deliberately chose"
    r")\b",
    re.IGNORECASE,
)

_WS_REF = re.compile(r"\bWS-\d{3,}\b")
_ADR_REF = re.compile(r"\bADR-\d{3,}\b")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _d_artifact_drift(graph: SpecGraph) -> list[Finding]:
    """D17 + D18 (AE prose) and D19 + D20 (Intent prose) content-drift checks."""
    out: list[Finding] = []

    # AE: D17 + D18
    for ae in graph.aes():
        ae_id = ae["id"]
        if ae.get("status") in {"DEPRECATED", "TODO"}:
            continue
        prose_chunks: list[tuple[str, str]] = []
        if ae.get("purpose_and_scope"):
            prose_chunks.append(("purpose_and_scope", ae["purpose_and_scope"]))
        for r in ae.get("responsibilities", []) or []:
            if isinstance(r, str):
                prose_chunks.append(("responsibilities[]", r))
        if ae.get("key_concepts"):
            prose_chunks.append(("key_concepts", ae["key_concepts"]))
        if ae.get("constraints_and_quality_notes"):
            prose_chunks.append(
                ("constraints_and_quality_notes", ae["constraints_and_quality_notes"])
            )

        for field, text in prose_chunks:
            for sentence in _split_sentences(text):
                num = _D17_NUMERIC_UNIT.search(sentence)
                if num and not _WS_REF.search(sentence):
                    snippet = _truncate(sentence, 180)
                    out.append(
                        Finding(
                            severity=P2,
                            rule="D17-AE-NUMERIC-NO-WS-CITE",
                            artifact_id=ae_id,
                            message=(
                                f"AE.{field} contains a measurable target "
                                f"`{num.group(0)}` outside a WS citation. "
                                f"Per audit-v2 D17, route quantitative SLOs to a WS and cite "
                                f"it here (e.g., 'WS-NNN §Latency targets'). Snippet: {snippet}"
                            ),
                            fix_kind="semantic",
                        )
                    )
                rat = _D18_RATIONALE_PHRASES.search(sentence)
                if rat and not _ADR_REF.search(sentence):
                    snippet = _truncate(sentence, 180)
                    out.append(
                        Finding(
                            severity=P2,
                            rule="D18-AE-RATIONALE-NO-ADR-CITE",
                            artifact_id=ae_id,
                            message=(
                                f"AE.{field} contains decision-rationale prose "
                                f"`{rat.group(0)}` outside an ADR citation. "
                                f"Per audit-v2 D18, route rationale to an ADR and cite "
                                f"it here (e.g., 'ADR-NNN governs this'). Snippet: {snippet}"
                            ),
                            fix_kind="semantic",
                        )
                    )

    # Intent: D19 + D20 (mirror of D17/D18 but on motivation + desired_outcome).
    # NFR type_specific.target is exempt by design.
    for intent in graph.intents():
        int_id = intent["id"]
        if intent.get("status") in {"DEPRECATED", "SUPERSEDED", "TODO"}:
            continue
        prose_chunks_int: list[tuple[str, str]] = []
        if intent.get("motivation"):
            prose_chunks_int.append(("motivation", intent["motivation"]))
        if intent.get("desired_outcome"):
            prose_chunks_int.append(("desired_outcome", intent["desired_outcome"]))

        for field, text in prose_chunks_int:
            for sentence in _split_sentences(text):
                num = _D17_NUMERIC_UNIT.search(sentence)
                if num and not _WS_REF.search(sentence):
                    snippet = _truncate(sentence, 180)
                    out.append(
                        Finding(
                            severity=P2,
                            rule="D19-INT-NUMERIC-NO-WS-CITE",
                            artifact_id=int_id,
                            message=(
                                f"Intent.{field} contains a measurable target "
                                f"`{num.group(0)}` outside a WS citation. "
                                f"Per audit-v2 D19, route quantitative targets to a WS "
                                f"(NFR Intents may put a Target in the type-specific block — "
                                f"that is exempt). Snippet: {snippet}"
                            ),
                            fix_kind="semantic",
                        )
                    )
                rat = _D18_RATIONALE_PHRASES.search(sentence)
                if rat and not _ADR_REF.search(sentence):
                    snippet = _truncate(sentence, 180)
                    out.append(
                        Finding(
                            severity=P2,
                            rule="D20-INT-RATIONALE-NO-ADR-CITE",
                            artifact_id=int_id,
                            message=(
                                f"Intent.{field} contains decision-rationale prose "
                                f"`{rat.group(0)}` outside an ADR citation. "
                                f"Per audit-v2 D20, route rationale to an ADR and cite "
                                f"it here. Snippet: {snippet}"
                            ),
                            fix_kind="semantic",
                        )
                    )

    return out


def _truncate(text: str, max_chars: int) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


# --------------------------------------------------------------------------- #
# L7 — Intent linkage (audit-v2 L7a + L7b)
# --------------------------------------------------------------------------- #


def _expand_braces(pattern: str) -> list[str]:
    """Expand shell-style brace groups `{a,b,c}` into literal alternatives.

    `glob.glob` does not understand brace expansion, so a pattern like
    `src/pkg/{cli,doctor}/**/*.py` would match nothing and emit a false
    L7b-INT-COMPONENTS-RESOLVE finding (ds-l7b). This helper turns one
    pattern into the cartesian product of its brace branches; multiple
    brace groups in one pattern are all expanded. A pattern with no braces
    returns `[pattern]` unchanged. Nested braces are not supported — the
    leftmost innermost-free group is expanded each pass until none remain.
    """
    _brace = re.compile(r"\{([^{}]*)\}")
    results = [pattern]
    while any(_brace.search(candidate) for candidate in results):
        expanded: list[str] = []
        for candidate in results:
            m = _brace.search(candidate)
            if m is None:
                expanded.append(candidate)
                continue
            for alt in m.group(1).split(","):
                expanded.append(candidate[: m.start()] + alt + candidate[m.end() :])
        results = expanded
    return results


# Per ADR-019: an Intent in one of these "build underway" statuses is exempt
# from L7b-INT-COMPONENTS-RESOLVE — an unresolved component glob is the
# expected shadow of authoring specs ahead of the code that lands them.
# `TESTFAIL` retired 2026-05-25 (E3 audit).
_L7B_BUILD_UNDERWAY = {"IMPLEMENTING", "TESTPASS", "MERGED"}

# Phase 1.B / ds-puvi: recommended open-enum vocabulary for Intent.risk_tier.
# Lint-on-boundary (Fowler): the schema accepts any string; the audit rule
# T-INT-RISK-TIER-VALID emits a P3 advisory when the value falls outside this
# set so unrecognized values surface as drift signal without blocking promotion.
_INT_RECOMMENDED_RISK_TIERS = {
    "default",
    "schema-migration",
    "auth",
    "billing",
    "concurrency",
    "data-residency",
    "external-api-surface",
}

# Phase 1.B / ds-27ld: recommended open-enum vocabulary for bead-body
# `failure_class:` lines. Same lint-on-boundary pattern as risk_tier above;
# T-BEAD-FAILURE-CLASS-VALID emits a P3 advisory when a bead's failure_class
# falls outside this set. The bead-body convention is parser-extracted (no
# beads-rust schema change) via fidelity_audit.bead_body.parse_bead_failure_class.
_BEAD_RECOMMENDED_FAILURE_CLASSES = {
    "wrong-spec",
    "correlated-AI-miss",
    "production-only-failure",
    "flaky-test-masked-bug",
    "scope-creep-undetected",
    "dependency-version-conflict",
    "concurrency-race",
    "other",
}


def _l7_intent_linkage(graph: SpecGraph) -> list[Finding]:
    """L7-Intent linkage rules:

      - L7a-INT-AE-MISSING (important): Intent has no linked_architecture_elements.
      - L7a-INT-AE-EXISTS  (critical):  each linked AE-NNN must resolve in the registry.
      - L7b-INT-COMPONENTS-MISSING (important): Intent has no components_affected.
      - L7b-INT-COMPONENTS-RESOLVE (status-conditional): each glob must match ≥1
        path relative to repo_root. **Per ADR-019:** severity tracks the Intent
        lifecycle. DRAFT, PROPOSED, and ACCEPTED Intents emit `P3` (advisory) —
        their declared paths are a forward commitment the Intent itself plans to
        land. IMPLEMENTING and the rest of the build-underway band (TESTPASS,
        MERGED) are exempt — an unresolved glob there is the expected shadow of
        authoring specs ahead of code, not drift. Only LOCKED emits `P2`: a
        LOCKED Intent claims its work is complete, so an unresolved glob is a
        genuine break. DEPRECATED and SUPERSEDED are skipped entirely.
        Skipped when graph.repo_root is None.
      - T14-INT-VERIFICATION (important): no verification cmd checks.

    Note: the L7 prefix here is for Intent-targeted rules (audit-v2 calls them
    L7a/L7b). It does NOT collide with the L7-ADR-SUPER-* family because the
    artifact_id namespace + rule prefix together disambiguate.
    """
    out: list[Finding] = []
    repo_root = graph.repo_root
    for intent in graph.intents():
        int_id = intent["id"]
        if intent.get("status") in {"DEPRECATED", "SUPERSEDED"}:
            continue

        aes = intent.get("linked_architecture_elements", []) or []
        if not aes:
            out.append(
                Finding(
                    severity=P2,
                    rule="L7a-INT-AE-MISSING",
                    artifact_id=int_id,
                    message=(
                        "Intent has no §Linked Architecture Elements entries. "
                        "Per audit-v2 L7a, every Intent must list ≥1 AE-NNN."
                    ),
                    fix_kind="semantic",
                )
            )
        else:
            for ref in aes:
                ae_id = ref["id"] if isinstance(ref, dict) else ref
                if not graph.has(ae_id):
                    out.append(
                        Finding(
                            severity=P1,
                            rule="L7a-INT-AE-EXISTS",
                            artifact_id=int_id,
                            message=(
                                f"Intent references AE {ae_id} which does not exist "
                                f"in the registry."
                            ),
                            fix_kind="semantic",
                        )
                    )

        components = intent.get("components_affected", []) or []
        if not components:
            out.append(
                Finding(
                    severity=P2,
                    rule="L7b-INT-COMPONENTS-MISSING",
                    artifact_id=int_id,
                    message=(
                        "Intent has no §Components affected entries. "
                        "Per audit-v2 T15/L7b, every Intent must list ≥1 file glob."
                    ),
                    fix_kind="semantic",
                )
            )
        elif repo_root is not None:
            # Per ADR-019: L7b severity tracks the Intent lifecycle. The
            # build-underway band (IMPLEMENTING/TESTPASS/MERGED) is
            # exempt — an unresolved glob there is the expected shadow of
            # authoring specs ahead of code. DRAFT/PROPOSED/ACCEPTED emit a
            # `P3` advisory (a forward commitment, surfaced but not gating);
            # only LOCKED — which claims the work is done — keeps `P2`.
            status = (intent.get("status") or "DRAFT").upper()
            if status not in _L7B_BUILD_UNDERWAY:
                severity = P2 if status == "LOCKED" else P3
                for pattern in components:
                    # `glob.glob` understands `*`, `**`, `?`, `[seq]` but NOT
                    # shell brace expansion `{a,b}`. Expand braces ourselves
                    # and union the matches so a brace glob resolves when any
                    # branch matches ≥1 path (ds-l7b).
                    matches: list[str] = []
                    for expansion in _expand_braces(pattern):
                        matches.extend(_glob.glob(str(repo_root / expansion), recursive=True))
                    if not matches:
                        out.append(
                            Finding(
                                severity=severity,
                                rule="L7b-INT-COMPONENTS-RESOLVE",
                                artifact_id=int_id,
                                message=(
                                    f"Intent.components_affected glob `{pattern}` "
                                    f"matched 0 paths under {repo_root}. Per "
                                    f"audit-v2 L7b, each glob must resolve to ≥1 "
                                    f"existing path (severity={severity} at "
                                    f"status={status})."
                                ),
                                fix_kind="semantic",
                            )
                        )

        if not (intent.get("verification") or []):
            out.append(
                Finding(
                    severity=P2,
                    rule="T14-INT-VERIFICATION",
                    artifact_id=int_id,
                    message=(
                        "Intent has no §Verification yaml entries (T14 requires ≥1 "
                        "named cmd check)."
                    ),
                    fix_kind="semantic",
                )
            )

        # T-INT-RISK-TIER-VALID (Phase 1.B / ds-puvi). Warn-only P3 advisory:
        # field is optional + open-enum. Absent → no finding. Value in
        # recommended set → no finding. Unknown value → P3 advisory naming
        # the value + the recommended set so authors catch typos without
        # being blocked on promotion. Per Fowler lint-on-boundary.
        risk_tier = intent.get("risk_tier")
        if risk_tier is not None and risk_tier not in _INT_RECOMMENDED_RISK_TIERS:
            out.append(
                Finding(
                    severity=P3,
                    rule="T-INT-RISK-TIER-VALID",
                    artifact_id=int_id,
                    message=(
                        f"Intent.risk_tier value `{risk_tier}` is outside the "
                        f"recommended open-enum vocabulary. Recommended: "
                        f"{sorted(_INT_RECOMMENDED_RISK_TIERS)}. The field is "
                        f"open-enum — this is an advisory; if the value is "
                        f"intentional, expand the vocabulary in "
                        f"tooling/dekspec/fidelity_audit/linkage.py "
                        f"(_INT_RECOMMENDED_RISK_TIERS)."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# T-BEAD-FAILURE-CLASS-VALID — bead-body failure_class lint (Phase 1.B / ds-27ld)
# --------------------------------------------------------------------------- #


def _t_bead_failure_class_valid(graph: SpecGraph) -> list[Finding]:
    """Walk `.beads/issues.jsonl` and emit a P3 advisory per bead whose
    `failure_class:` body line falls outside the recommended vocabulary.

    Beads are body-only convention — no beads-rust schema change. The
    canonical extractor is `fidelity_audit.bead_body.parse_bead_failure_class`,
    which JSON-walks the JSONL and regex-extracts the line from each bead's
    description.

    Open-enum + lint-on-boundary (Fowler): unknown values surface as P3
    advisories without blocking. Recommended values + absent fields produce
    zero findings.

    Skipped silently when:
      - graph.repo_root is None (in-memory test fixtures)
      - `.beads/issues.jsonl` is absent (consumer repos without bead tracker)
    """
    if graph.repo_root is None:
        return []
    jsonl_path = Path(graph.repo_root) / ".beads" / "issues.jsonl"
    if not jsonl_path.exists():
        return []

    # Lazy import to avoid linking the audit module to bead_body at import
    # time (keeps the dep arrow narrow + lets bead_body grow independently).
    from .bead_body import parse_bead_failure_class

    out: list[Finding] = []
    for record in parse_bead_failure_class(jsonl_path):
        if record.failure_class is None:
            continue
        if record.failure_class in _BEAD_RECOMMENDED_FAILURE_CLASSES:
            continue
        out.append(
            Finding(
                severity=P3,
                rule="T-BEAD-FAILURE-CLASS-VALID",
                artifact_id=record.bead_id,
                message=(
                    f"Bead failure_class `{record.failure_class}` is outside "
                    f"the recommended open-enum vocabulary. Recommended: "
                    f"{sorted(_BEAD_RECOMMENDED_FAILURE_CLASSES)}. The field "
                    f"is open-enum — this is an advisory; if the value is "
                    f"intentional, expand the vocabulary in "
                    f"tooling/dekspec/fidelity_audit/linkage.py "
                    f"(_BEAD_RECOMMENDED_FAILURE_CLASSES)."
                ),
                fix_kind="semantic",
            )
        )
    return out


# --------------------------------------------------------------------------- #
# L8 + T17 — Mission ↔ Intent bidirectional linkage
# --------------------------------------------------------------------------- #

_AUTONOMY_RANK = {"manual": 0, "low": 1, "medium": 2, "high": 3}

# Per ADR-019: an Intent in one of these statuses carries its Mission
# reference for provenance only — it is not a live queue member, so it is
# exempt from L8-INT-MSN-MIRROR (and the matching fix proposer). An OVERSIZED
# design parent decomposes into the child Intents that populate the queue;
# a SUPERSEDED Intent keeps the reference as history.
_L8_MIRROR_EXEMPT = {"OVERSIZED", "SUPERSEDED"}


def _l8_mission_intent_bidirectional(graph: SpecGraph) -> list[Finding]:
    """L8 — Mission ↔ Intent bidirectional linkage:

      - L8-MSN-INT-MIRROR (important): if Mission lists INT-X in intent_queue,
        INT-X.mission must reference this Mission.
      - L8-INT-MSN-MIRROR (important): if Intent.mission references MSN-Y,
        MSN-Y.intent_queue must list this Intent. Per ADR-019, OVERSIZED and
        SUPERSEDED Intents are exempt — they carry a Mission reference for
        provenance, not as a live queue obligation.
      - L8-INT-AUTONOMY-EXCEEDS (critical): Intent.autonomy must NOT exceed
        Mission.autonomy_ceiling (manual < low < medium < high).
      - L8-MSN-INT-EXISTS (critical): each MSN.intent_queue[].id must resolve.

      - T17-MSN-VERIFICATION (important): Mission has no mission_verification.
      - T17-MSN-OUTCOME (important): Mission has no outcome.
      - T17-MSN-ROLLBACK (important): Mission has no rollback_plan
        (v0.2.0: trigger prose + ≥1 named cmd step).

    DEPRECATED + KILLED + COMPLETE Missions are skipped for non-critical T17
    checks.
    """
    out: list[Finding] = []

    intents_by_id = {i["id"]: i for i in graph.intents()}
    missions_by_id = {m["id"]: m for m in graph.missions()}

    # T17 Mission completeness
    for msn in missions_by_id.values():
        msn_id = msn["id"]
        is_terminal = msn.get("status") in {"COMPLETE", "KILLED", "SUPERSEDED"}
        if not is_terminal and not (msn.get("mission_verification") or []):
            out.append(
                Finding(
                    severity=P2,
                    rule="T17-MSN-VERIFICATION",
                    artifact_id=msn_id,
                    message=(
                        "Mission has no §Mission Verification cmd checks "
                        "(audit-v2 T17 requires ≥1)."
                    ),
                    fix_kind="semantic",
                )
            )
        if not is_terminal and not (msn.get("outcome") or "").strip():
            out.append(
                Finding(
                    severity=P2,
                    rule="T17-MSN-OUTCOME",
                    artifact_id=msn_id,
                    message="Mission has no §Outcome paragraph (audit-v2 T17).",
                    fix_kind="semantic",
                )
            )
        if not is_terminal:
            rollback = msn.get("rollback_plan")
            # v0.2.0 (ds-zuy): rollback_plan is now an object with
            # `trigger` (prose) + `steps` (named cmd list). Either piece
            # missing → T17 fires. v0.1.0 string IRs would have been
            # migrated upstream; if we still see a string here, treat it
            # as legacy prose and require the structured shape.
            missing = False
            if rollback is None:
                missing = True
            elif isinstance(rollback, dict):
                if not (rollback.get("trigger") or "").strip() and not (
                    rollback.get("steps") or []
                ):
                    missing = True
            else:  # legacy str — should not happen post-migration
                if not str(rollback).strip():
                    missing = True
            if missing:
                out.append(
                    Finding(
                        severity=P2,
                        rule="T17-MSN-ROLLBACK",
                        artifact_id=msn_id,
                        message=(
                            "Mission has no §Rollback plan (audit-v2 T17). "
                            "Required shape: trigger prose + ≥1 named cmd step."
                        ),
                        fix_kind="semantic",
                    )
                )

    # L8 Mission → Intent
    for msn in missions_by_id.values():
        msn_id = msn["id"]
        for entry in msn.get("intent_queue", []) or []:
            int_id = entry.get("id", "") if isinstance(entry, dict) else entry
            if not int_id or not int_id.startswith("INT-"):
                continue
            intent = intents_by_id.get(int_id)
            if intent is None:
                out.append(
                    Finding(
                        severity=P1,
                        rule="L8-MSN-INT-EXISTS",
                        artifact_id=msn_id,
                        message=(
                            f"Mission.intent_queue references {int_id} which does "
                            f"not exist in the registry."
                        ),
                        fix_kind="semantic",
                    )
                )
                continue
            int_mission = (intent.get("mission") or {}).get("id")
            if int_mission != msn_id:
                out.append(
                    Finding(
                        severity=P2,
                        rule="L8-MSN-INT-MIRROR",
                        artifact_id=int_id,
                        message=(
                            f"Mission {msn_id}.intent_queue lists {int_id} but "
                            f"{int_id}.mission references "
                            f"{int_mission or '(none)'} instead. Add the back-pointer."
                        ),
                        fix_kind="semantic",
                    )
                )

    # L8 Intent → Mission (mirror direction) + autonomy ceiling
    for intent in intents_by_id.values():
        int_id = intent["id"]
        msn_ref = (intent.get("mission") or {}).get("id")
        if not msn_ref:
            continue
        mission = missions_by_id.get(msn_ref)
        if mission is None:
            # Already covered by parse-or-not, but raise as critical so
            # the engineer notices the orphan link.
            out.append(
                Finding(
                    severity=P1,
                    rule="L8-INT-MSN-EXISTS",
                    artifact_id=int_id,
                    message=(
                        f"Intent.mission references {msn_ref} which does not exist in the registry."
                    ),
                    fix_kind="semantic",
                )
            )
            continue
        queue_ids = {
            (e.get("id") if isinstance(e, dict) else e) for e in (mission.get("intent_queue") or [])
        }
        # Per ADR-019: OVERSIZED/SUPERSEDED design-parent Intents are exempt
        # from the mirror — they are not queue members by design.
        int_status = (intent.get("status") or "DRAFT").upper()
        if int_id not in queue_ids and int_status not in _L8_MIRROR_EXEMPT:
            out.append(
                Finding(
                    severity=P2,
                    rule="L8-INT-MSN-MIRROR",
                    artifact_id=msn_ref,
                    message=(
                        f"Intent {int_id}.mission references {msn_ref} but "
                        f"{msn_ref}.intent_queue does not list {int_id}. "
                        f"Add a queue row."
                    ),
                    fix_kind="semantic",
                )
            )
        # Autonomy ceiling
        int_aut = intent.get("autonomy")
        msn_ceiling = mission.get("autonomy_ceiling")
        if (
            int_aut
            and msn_ceiling
            and (_AUTONOMY_RANK.get(int_aut, 99) > _AUTONOMY_RANK.get(msn_ceiling, -1))
        ):
            out.append(
                Finding(
                    severity=P1,
                    rule="L8-INT-AUTONOMY-EXCEEDS",
                    artifact_id=int_id,
                    message=(
                        f"Intent.autonomy={int_aut} exceeds Mission "
                        f"{msn_ref}.autonomy_ceiling={msn_ceiling}. Per audit-v2 "
                        f"L8, no child Intent may exceed its Mission's ceiling."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# Per ADR-016: "active" for the per-Mission serialization finding means an
# Intent in a non-terminal lifecycle status — DRAFT through MERGED. The
# terminal/off-ramp statuses (LOCKED, SUPERSEDED, KILLED) and the design-parent
# status OVERSIZED do NOT count: a LOCKED Intent is done, a SUPERSEDED/KILLED
# Intent is retired, and an OVERSIZED Intent decomposed into the child Intents
# that actually populate the queue. `TODO` + `TESTFAIL` retired 2026-05-25
# (E3 audit) and are no longer in the Intent enum.
_L8_ACTIVE_INTENT_STATUSES = frozenset(
    {
        "DRAFT",
        "PROPOSED",
        "ACCEPTED",
        "IMPLEMENTING",
        "TESTPASS",
        "MERGED",
    }
)


def _l8_mission_intent_serialized(graph: SpecGraph) -> list[Finding]:
    """L8-MSN-INT-SERIALIZED (advisory) — per-Mission Intent serialization.

    Per ADR-016: within a single Mission, the intended discipline is at most
    one child Intent in active status at a time — child Intents are
    dependency-ordered, so the Mission's Intent queue is also its
    serialization queue. This rule fires an advisory (`P3`) finding when one
    Mission carries MORE THAN ONE active Intent.

    "Active" is any non-terminal lifecycle status (`_L8_ACTIVE_INTENT_STATUSES`,
    DRAFT through MERGED). LOCKED / SUPERSEDED / KILLED / OVERSIZED Intents do
    not count toward the limit.

    Per ADR-016, this is advisory and non-gating — DekSpec reserves hard gates
    for the size caps; workflow cadence is surfaced, not walled. Mission-less
    standalone Intents are NEVER serialized (independent workstreams proceed in
    parallel), so the rule only ever inspects Intents with a parent Mission.
    """
    out: list[Finding] = []

    # Bucket each active Intent under its parent Mission. Mission-less Intents
    # carry no `mission` ref and are skipped entirely — they are never
    # serialized under ADR-016's per-Mission scope.
    active_by_mission: dict[str, list[str]] = {}
    for intent in graph.intents():
        status = (intent.get("status") or "DRAFT").upper()
        if status not in _L8_ACTIVE_INTENT_STATUSES:
            continue
        msn_ref = (intent.get("mission") or {}).get("id")
        if not msn_ref:
            continue
        active_by_mission.setdefault(msn_ref, []).append(intent["id"])

    for msn_id, int_ids in active_by_mission.items():
        if len(int_ids) <= 1:
            continue
        listed = ", ".join(sorted(int_ids))
        out.append(
            Finding(
                severity=P3,
                rule="L8-MSN-INT-SERIALIZED",
                artifact_id=msn_id,
                message=(
                    f"Mission carries {len(int_ids)} active Intents ({listed}). "
                    f"Per ADR-016, a Mission's child Intents are dependency-ordered "
                    f"and the intended discipline is at most one active at a time — "
                    f"advisory: run them serially or confirm they are independent."
                ),
                fix_kind="semantic",
            )
        )
    return out


# --------------------------------------------------------------------------- #
# L14-INT-BACKLOG-ACTIVE (advisory) — repo-wide active-Intent backlog health
# --------------------------------------------------------------------------- #

# Per ADR-016 Open Issue 1: the repo-wide count of active Intents is a
# review-bandwidth / linkage-rot signal distinct from L8-MSN-INT-SERIALIZED's
# per-Mission dependency ordering. When too many Intents sit active at once,
# cross-artifact links rot faster than they can be reviewed. The default
# threshold is 10; consumers tune it via the v1-profile parameter
# `L14-INT-BACKLOG-ACTIVE.threshold` (see profiles/v1.yaml) without a code
# change. This module-level constant is the fallback when the parameter is
# unset — the same default the profile manifest declares.
_INT_BACKLOG_ACTIVE_THRESHOLD = 10


def _l14_intent_backlog_active(
    graph: SpecGraph, threshold: int = _INT_BACKLOG_ACTIVE_THRESHOLD
) -> list[Finding]:
    """L14-INT-BACKLOG-ACTIVE (advisory) — repo-wide active-Intent backlog.

    Per ADR-016 Open Issue 1: counts ALL active Intents repo-wide — Mission-
    bound and Mission-less alike — and fires a single advisory (`P3`) finding
    when that count EXCEEDS `threshold`. "Active" reuses
    `_L8_ACTIVE_INTENT_STATUSES` (DRAFT through MERGED); terminal/off-ramp
    statuses (LOCKED / SUPERSEDED / KILLED / OVERSIZED) are excluded.

    This is deliberately distinct from `L8-MSN-INT-SERIALIZED`, which scopes
    Intent serialization per Mission. L14 is about review-bandwidth and
    linkage-rot backlog health for the repo as a whole — a large active
    Intent queue means cross-artifact links rot faster than they can be
    reviewed. It fires AT MOST once (the finding is owned by the whole
    Intent corpus, not by any one Intent).

    `threshold` defaults to 10 (the v1 audit profile value). Future profiles
    may tighten or loosen it via the `L14-INT-BACKLOG-ACTIVE.threshold`
    parameter in their manifest.
    """
    out: list[Finding] = []
    active_ids = [
        intent["id"]
        for intent in graph.intents()
        if (intent.get("status") or "DRAFT").upper() in _L8_ACTIVE_INTENT_STATUSES
    ]
    if len(active_ids) <= threshold:
        return out
    listed = ", ".join(sorted(active_ids))
    out.append(
        Finding(
            severity=P3,
            rule="L14-INT-BACKLOG-ACTIVE",
            artifact_id="intent-index",
            message=(
                f"{len(active_ids)} Intents are in an active lifecycle status "
                f"({listed}); the {threshold}-Intent backlog-health threshold is "
                f"exceeded. Per ADR-016, a large active-Intent queue means "
                f"cross-artifact links rot faster than they can be reviewed — "
                f"advisory: land or supersede in-flight Intents before opening "
                f"more, or raise `L14-INT-BACKLOG-ACTIVE.threshold` in the audit "
                f"profile if this backlog is intentional."
            ),
            fix_kind="semantic",
        )
    )
    return out


# --------------------------------------------------------------------------- #
# L13 — Intent lock coherence (two-path lock gate, ADR-017)
# --------------------------------------------------------------------------- #

_BELOW_ACCEPTED = {"DRAFT", "PROPOSED", "OVERSIZED"}


def _l13_intent_lock_coherence(graph: SpecGraph) -> list[Finding]:
    """L13-INT-LOCK-COHERENCE (important) — a LOCKED Intent must satisfy at
    least one of the two sufficient lock paths defined by ADR-017:

      - Path A — forward flow: the Intent reached LOCKED through the canonical
        ``--testpass`` -> TESTPASS -> MERGED -> LOCKED lifecycle.
      - Path B — downstream-accepted: every downstream WS/IC/IB the Intent
        produced is at status ACCEPTED or LOCKED.

    The rule mirrors ``/write-intent`` Lock Mode (IB-049) so the prompt-time
    gate and this parse-time audit agree — no skill-vs-engine drift.

    It is a deliberate one-sided guard (INT-036 OI-3): it fires ONLY when it
    can positively show Path B is unsatisfied — a LOCKED Intent with >=1
    resolvable downstream artifact below ACCEPTED. Path A leaves no structured
    parse-time evidence in the Intent IR, so the rule stays silent on a LOCKED
    Intent that has no Path-B-blocking downstream artifact; a false negative is
    acceptable here, a false positive would break the ADR-007 CLEAN gate.

    Downstream set: the IB->Intent edge (an IB's ``**Intent:**`` field) is the
    reliably-modelled edge, so the downstream set is the resolvable IB set. No
    direct Intent<->WS / Intent<->IC edge is modelled in the IR (INT-036 OI-2),
    so WS/IC inclusion is out of reach and the set is IBs only. DEPRECATED and
    SUPERSEDED downstream IBs are excluded. Beads (L4) are not part of the gate.
    """
    out: list[Finding] = []

    ibs_by_intent: dict[str, list[dict[str, Any]]] = {}
    for ib in graph.ibs():
        int_ref = (ib.get("intent") or {}).get("id")
        if int_ref:
            ibs_by_intent.setdefault(int_ref, []).append(ib)

    for intent in graph.intents():
        if (intent.get("status") or "").upper() != "LOCKED":
            continue
        int_id = intent["id"]
        downstream = [
            ib
            for ib in ibs_by_intent.get(int_id, [])
            if (ib.get("status") or "").upper() not in {"DEPRECATED", "SUPERSEDED"}
        ]
        if not downstream:
            # No resolvable downstream artifact — bias toward silence.
            continue
        blockers = sorted(
            (ib for ib in downstream if (ib.get("status") or "").upper() in _BELOW_ACCEPTED),
            key=lambda b: b["id"],
        )
        if not blockers:
            # Path B satisfied — every downstream IB is ACCEPTED or LOCKED.
            continue
        blocker_desc = ", ".join(
            f"{ib['id']} is {(ib.get('status') or '').upper()}" for ib in blockers
        )
        out.append(
            Finding(
                severity=P2,
                rule="L13-INT-LOCK-COHERENCE",
                artifact_id=int_id,
                message=(
                    f"Intent is LOCKED but satisfies neither sufficient lock path "
                    f"(ADR-017). Path B (every downstream WS/IC/IB at status "
                    f">= ACCEPTED) is broken: {blocker_desc}. Promote the blocking "
                    f"artifact(s) to ACCEPTED, or — if the Intent locked via the "
                    f"forward-flow Path A — confirm its lifecycle record."
                ),
                fix_kind="semantic",
            )
        )
    return out


# --------------------------------------------------------------------------- #
# L9 — Verification cmd checks resolve to executable scripts
# --------------------------------------------------------------------------- #


def _l9_verification_resolves(graph: SpecGraph) -> list[Finding]:
    """L9-INT-CMD-RESOLVE / L9-MSN-CMD-RESOLVE (minor):

    Per audit-v2 L9, every cmd entry in Intent.verification and
    Mission.mission_verification should resolve to an executable script
    or recognized tool. Resolution rules (in order):

      1. `pytest` (and any flag pattern starting with `pytest`) resolves
         if `pytest` is on PATH.
      2. `scripts/<name>.sh` (or any path starting with `scripts/`) resolves
         if the file exists and is executable, relative to repo_root.
      3. Other commands resolve if `which <first-token>` finds them.

    WARNING-level by design — Intents in DRAFT often cite scripts that
    don't exist yet (audit-v2 docs the script as `dektora-mi-tbd-*` until
    the first --testpass run authors it).

    DEPRECATED + SUPERSEDED + COMPLETE artifacts skipped.
    """
    out: list[Finding] = []
    repo_root = graph.repo_root

    for intent in graph.intents():
        int_id = intent["id"]
        if intent.get("status") in {"DEPRECATED", "SUPERSEDED", "COMPLETE", "TODO"}:
            continue
        for v in intent.get("verification", []) or []:
            cmd = v.get("cmd", "").strip()
            if cmd and not _resolves(cmd, repo_root):
                out.append(
                    Finding(
                        severity=P3,
                        rule="L9-INT-CMD-RESOLVE",
                        artifact_id=int_id,
                        message=(
                            f"Intent.verification[{v.get('name', '?')}].cmd `{cmd}` "
                            f"does not resolve to an executable script or known tool. "
                            f"Per audit-v2 L9, the cmd must run at --testpass."
                        ),
                        fix_kind="semantic",
                    )
                )

    for msn in graph.missions():
        msn_id = msn["id"]
        if msn.get("status") in {"COMPLETE", "KILLED", "SUPERSEDED"}:
            continue
        for v in msn.get("mission_verification", []) or []:
            cmd = v.get("cmd", "").strip()
            if cmd and not _resolves(cmd, repo_root):
                out.append(
                    Finding(
                        severity=P3,
                        rule="L9-MSN-CMD-RESOLVE",
                        artifact_id=msn_id,
                        message=(
                            f"Mission.mission_verification[{v.get('name', '?')}].cmd "
                            f"`{cmd}` does not resolve to an executable script or "
                            f"known tool. Per audit-v2 L9, the cmd must run at "
                            f"--complete to gate the COMPLETING → COMPLETE transition."
                        ),
                        fix_kind="semantic",
                    )
                )

        # Mission IR v0.2.0 (ds-zuy): rollback_plan.steps[].cmd and
        # kill_criteria[].cmd are also predicates that must resolve.
        # `_legacy_prose` sentinels (cmd starts with `echo SKIP_LEGACY_`)
        # are skipped here — they signal "human-attended rollback/kill"
        # rather than an L9 violation. The advisory markdown migration
        # surfaces them through a different channel.
        rollback = msn.get("rollback_plan")
        if isinstance(rollback, dict):
            for step in rollback.get("steps", []) or []:
                cmd = (step.get("cmd") or "").strip()
                if not cmd or cmd.startswith("echo SKIP_LEGACY_"):
                    continue
                if not _resolves(cmd, repo_root):
                    out.append(
                        Finding(
                            severity=P3,
                            rule="L9-MSN-CMD-RESOLVE",
                            artifact_id=msn_id,
                            message=(
                                f"Mission.rollback_plan.steps"
                                f"[{step.get('name', '?')}].cmd `{cmd}` does not "
                                f"resolve to an executable script or known tool. "
                                f"Per audit-v2 L9, the cmd must run when the "
                                f"trigger fires."
                            ),
                            fix_kind="semantic",
                        )
                    )
        for step in msn.get("kill_criteria", []) or []:
            cmd = (step.get("cmd") if isinstance(step, dict) else "").strip()
            if not cmd or cmd.startswith("echo SKIP_LEGACY_"):
                continue
            if not _resolves(cmd, repo_root):
                out.append(
                    Finding(
                        severity=P3,
                        rule="L9-MSN-CMD-RESOLVE",
                        artifact_id=msn_id,
                        message=(
                            f"Mission.kill_criteria[{step.get('name', '?')}].cmd "
                            f"`{cmd}` does not resolve to an executable script or "
                            f"known tool. Per audit-v2 L9, the cmd must run as "
                            f"the kill predicate."
                        ),
                        fix_kind="semantic",
                    )
                )

    return out


def _resolves(cmd: str, repo_root: Path | None) -> bool:
    """Return True if the cmd's first token resolves per the L9 rules."""
    parts = cmd.split()
    if not parts:
        return False
    first = parts[0]
    # Rule 2: scripts/<name>.sh path-form
    if first.startswith("scripts/") or first.startswith("./scripts/"):
        if repo_root is None:
            return False
        path = repo_root / first.lstrip("./")
        return path.exists() and (path.is_dir() or _is_executable_or_text(path))
    # Rule 2 (extended): .venv/bin/<tool> path-form. The venv is a per-developer
    # artifact and may not exist at audit time (e.g., in CI before
    # `pip install -e .`). Accept any first arg under .venv/ as resolving —
    # the audit isn't responsible for venv hygiene.
    if first.startswith(".venv/") or first.startswith("./.venv/"):
        return True
    # Rule 2 (extended): any other path-form binary. `find_spec` only handles
    # module names — passing it `.venv/bin/python` or `/usr/bin/foo` raises
    # ImportError. Do a direct file-existence check instead.
    if "/" in first:
        if first.startswith("/"):
            return Path(first).is_file()
        if repo_root is None:
            return False
        return (repo_root / first.lstrip("./")).is_file()
    # Rule 1 / 3: PATH lookup via shutil.which
    if _shutil.which(first) is not None:
        return True
    # Rule 1 (extended): Python tool installed in the active interpreter.
    # Covers pytest / ruff / dekspec etc. when the venv's bin/ isn't on PATH
    # (e.g., invoking .venv/bin/python directly without venv activation).
    try:
        return _importlib_util.find_spec(first) is not None
    except (ValueError, ModuleNotFoundError, ImportError):
        return False


def _is_executable_or_text(path: Path) -> bool:
    """Conservative check: file exists and is either executable or readable."""
    if not path.exists() or not path.is_file():
        return False
    return _os.access(path, _os.X_OK) or _os.access(path, _os.R_OK)


# --------------------------------------------------------------------------- #
# L10 — Glossary coverage (advisory)
# --------------------------------------------------------------------------- #

# Title-Case multi-word phrase: 2-4 words, each starting with a capital letter.
# Filters out single capitalized words (likely proper nouns), phrases preceded
# by a sentence-ending period (likely sentence starters), AND phrases preceded
# by `§` (per ds-q3t — these are section-header pointers like `§Mission
# Verification` or `MSN-001 §Mission Verification`, not standalone jargon).
_TITLECASE_PHRASE = re.compile(r"(?<![.!?]\s)(?<!§)\b((?:[A-Z][a-z]+\s+){1,3}[A-Z][a-z]+)\b")

# Phrases to never flag — markdown framework, template-defined section names,
# generic prose, and proper nouns that are not domain jargon even though
# they're title-cased.
#
# Per ds-q3t: the L10 heuristic over-flagged template-mandated section names
# (`Mission Verification`, `Business Rules`, etc.), artifact-internal concept
# names (`Constitution Article`), and proper nouns. Treating each one as
# undefined jargon polluted glossaries with redirect entries instead of
# definitions. The four classes below cover the patterns the bead surfaced.
_L10_STOPWORDS = {
    # ----- DekSpec IR kind names ---------------------------------------
    "Working Spec",
    "Working Specs",
    "Implementation Brief",
    "Implementation Briefs",
    "Interface Contract",
    "Interface Contracts",
    "Architecture Decision",
    "Architecture Decisions",
    "Architecture Element",
    "Architecture Elements",
    "Domain Glossary",
    "System Vision",
    "Security Profile",
    "Security Profiles",  # ds-q3t / ADR-011 / INT-007
    # ----- Template-mandated section names (per ds-q3t) ----------------
    "Open Issues",
    "Amendment Log",
    "Linked Artifacts",
    "Related Architecture",
    "Related Artifacts",
    "Options Considered",
    "Decision Drivers",
    "Business Rules",
    "Governing Formulas",
    "Failure Behavior",
    "Failure Behaviors",
    "Acceptance Criteria",
    "Open Questions",
    "Provider AE",
    "Consumer AEs",
    "Domain Constraints",
    "Error Semantics",
    "Consistency Guarantees",
    "Mission Verification",
    "Mission Decomposition",
    "Intent Queue",
    "Autonomy Ceiling",
    "Constitution Article",
    "Constitution Articles",
    "Purpose and Scope",
    "Boundaries and Non-Goals",
    "Relationships and Dependencies",
    "Constraints and Quality Notes",
    # ----- Generic markdown / process vocabulary -----------------------
    "Open Source",
    "Pull Request",
    "Merge Request",
    "Code Review",
    "Code Reviews",
    "Test Plan",
    "Test Plans",
    # ----- Proper nouns (small allowlist; extend as needed) ------------
    "United States",
    "North America",
    "Apple Silicon",
    "Apple Music",
    "GitHub Actions",
    "GitHub Issues",
    "GitHub Workflow",
    "GitLab CI",
    "GitLab Issues",
    "Slack Bot",
    "Slack App",
}


def _l10_glossary_coverage(graph: SpecGraph) -> list[Finding]:
    """L10-GLOSSARY-COVERAGE (minor, advisory): for each artifact, surface
    multi-word Title-Case phrases (likely jargon) that don't appear in the
    Domain Glossary. Rolled up to one finding per artifact listing the top
    5 unknown candidates by frequency. Skipped when no glossary is present.

    Per ds-q3t, the "known" set is extended beyond glossary terms to include
    Title-Case phrases extracted from every loaded artifact's H1 name field.
    This treats artifact titles as definitions-by-link: if `Security Profile`
    appears in INT-007's name ("Add Security Profile artifact..."), it is
    counted as defined-by-INT-007, not undefined jargon. Combined with the
    `§`-preceded filter in `_TITLECASE_PHRASE`, the extended `_L10_STOPWORDS`,
    and the proper-noun allowlist, the rule's false-positive rate against the
    self-spec corpus drops from N flagged phrases to (target) 0.
    """
    glossary = graph.glossary()
    if glossary is None:
        return []
    known = {t["term"].strip().lower() for t in glossary.get("terms", [])}
    # Also accept singular/plural variants (cheap heuristic)
    for t in list(known):
        if t.endswith("s"):
            known.add(t[:-1])
        else:
            known.add(t + "s")

    # Per ds-q3t: extract Title-Case phrases from every loaded artifact's
    # name (H1) and add them to the known set. If a phrase IS the name of
    # a loaded artifact (or part of it), it's a reference to that artifact's
    # definition — not undefined jargon. Covers the "Security Profile in
    # INT-007's own H1" case, the "Tensor Dtype Lifecycle Contract = IC-014"
    # case, and similar cross-artifact title references.
    for ir in graph.all():
        name = ir.get("name") or ""
        if not isinstance(name, str) or not name:
            continue
        for m in _TITLECASE_PHRASE.finditer(name):
            known.add(m.group(1).strip().lower())

    out: list[Finding] = []
    for ir in graph.all():
        artifact_id = ir.get("id", "")
        if not artifact_id or artifact_id in {"DOMAIN-GLOSSARY", "SYSTEM-VISION"}:
            continue
        if ir.get("status") in {"DEPRECATED", "SUPERSEDED", "TODO"}:
            continue
        prose_chunks: list[str] = []
        for key in (
            "purpose_and_scope",
            "key_concepts",
            "constraints_and_quality_notes",
            "motivation",
            "desired_outcome",
            "outcome",
            "decision",
            "goal",
            "what_this_does",
            "what_this_is",
        ):
            v = ir.get(key)
            if isinstance(v, str) and v:
                prose_chunks.append(v)
            elif isinstance(v, dict):
                prose = v.get("prose") or v.get("mechanism") or ""
                if prose:
                    prose_chunks.append(prose)
        for r in ir.get("responsibilities", []) or []:
            if isinstance(r, str):
                prose_chunks.append(r)

        text = " ".join(prose_chunks)
        if not text:
            continue
        unknown_counts: dict[str, int] = {}
        for m in _TITLECASE_PHRASE.finditer(text):
            phrase = m.group(1).strip()
            if phrase in _L10_STOPWORDS:
                continue
            if phrase.lower() in known:
                continue
            unknown_counts[phrase] = unknown_counts.get(phrase, 0) + 1
        # Only flag phrases that recur (cheap signal that it's a real term)
        recurring = sorted(
            ((p, n) for p, n in unknown_counts.items() if n >= 2),
            key=lambda x: (-x[1], x[0]),
        )[:5]
        if recurring:
            sample = ", ".join(f"`{p}`×{n}" for p, n in recurring)
            out.append(
                Finding(
                    severity=P3,
                    rule="L10-GLOSSARY-COVERAGE",
                    artifact_id=artifact_id,
                    message=(
                        f"{artifact_id} uses {len(recurring)} likely-jargon "
                        f"Title-Case phrase(s) not present in the Domain Glossary "
                        f"(top 5 by occurrence): {sample}. Per audit-v2 (advisory), "
                        f"either add a glossary entry or rephrase if the term is "
                        f"not actually domain jargon."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# L11 — Mission progress (stale-active advisory)
# --------------------------------------------------------------------------- #

_MISSION_STALE_DAYS = 90


def _l11_mission_stale(
    graph: SpecGraph, days_threshold: int = _MISSION_STALE_DAYS
) -> list[Finding]:
    """L11-MSN-STALE (minor): a Mission with status=ACTIVE for more than
    `days_threshold` since its last `modified` date is flagged as stale.
    Either the Mission is making progress (and should record activity in
    its Amendment Log + Modified date) or it should advance to
    COMPLETING / KILLED.

    `days_threshold` defaults to 90 (the v1 audit profile value).
    Future profiles may tighten this via the L11-MSN-STALE.days_threshold
    parameter in their manifest.
    """
    out: list[Finding] = []
    today = _date.today()
    for msn in graph.missions():
        if msn.get("status") != "ACTIVE":
            continue
        modified_str = msn.get("modified") or msn.get("created")
        if not modified_str:
            continue
        try:
            modified = _date.fromisoformat(modified_str)
        except (TypeError, ValueError):
            continue
        age_days = (today - modified).days
        if age_days > days_threshold:
            out.append(
                Finding(
                    severity=P3,
                    rule="L11-MSN-STALE",
                    artifact_id=msn["id"],
                    message=(
                        f"Mission has been ACTIVE for {age_days} days since last "
                        f"modification ({modified_str}); the {days_threshold}-day "
                        f"stale threshold is exceeded. Either record progress (and bump "
                        f"`Modified:`) or advance the Mission to COMPLETING / KILLED."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# L12-WS-BLOCKING-PRE-IB-CLEAN (P1): WS gate — `blocking_pre_ib` open_issues
# must be resolved before status walks past PROPOSED.
# --------------------------------------------------------------------------- #

# WS statuses past PROPOSED — beyond this point, P1 (`blocking_pre_ib` /
# `blocking_pre_code` / `blocking` artifact-side aliases per ADR-013) open_issues
# represent the "Clarify Before Plan" failure mode and should not survive.
# `TESTFAIL` retired from the Intent enum 2026-05-25 (E3 audit); it never
# appeared in the WS enum but is removed from this set for consistency.
_L12_GATE_STATUSES = frozenset(
    {
        "ACCEPTED",
        "IMPLEMENTING",
        "TESTPASS",
        "MERGED",
        "LOCKED",
    }
)


def _l12_ws_blocking_pre_ib_clean(graph: SpecGraph) -> list[Finding]:
    """L12-WS-BLOCKING-PRE-IB-CLEAN (P1): a WS at status=ACCEPTED or higher
    must not carry P1 open_issues.

    P1 is the canonical severity for the `blocking_pre_ib` /
    `blocking_pre_code` / `blocking` artifact-side aliases (per ADR-013) —
    these signal unresolved spec-blocking questions that must be settled
    BEFORE downstream work (IB authoring, `/write-code-beads`, coding)
    proceeds. The Working Spec template documents this contract at line
    166: "Zero `blocking (pre-IB)` open issues must remain when
    `/write-ibs` is invoked." This rule realises that documented contract
    as a mechanical audit gate.

    Status semantics:
      - DRAFT / PROPOSED: P1 open_issues are expected (the field exists
        exactly to capture spec-blocking concerns during authoring); the
        rule is silent at these statuses.
      - ACCEPTED / IMPLEMENTING / TESTPASS / MERGED / LOCKED:
        any P1 open_issue is a "Clarify Before Plan" violation; fires P1.

    Pairs with the `/write-ibs` skill precondition (also landed in this
    commit) that refuses to decompose a parent WS carrying unresolved
    P1 open_issues into IBs.

    Tracks `ds-l12-ws-blocking-pre-ib-clean-5tp`.
    """
    out: list[Finding] = []
    for ws in graph.wses():
        status = (ws.get("status") or "").upper()
        if status not in _L12_GATE_STATUSES:
            continue
        open_issues = ws.get("open_issues") or []
        for issue in open_issues:
            if issue.get("severity") != "P1":
                continue
            issue_text = (issue.get("text") or "").strip()
            preview = issue_text[:120] + ("..." if len(issue_text) > 120 else "")
            out.append(
                Finding(
                    severity="P1",
                    rule="L12-WS-BLOCKING-PRE-IB-CLEAN",
                    artifact_id=ws["id"],
                    message=(
                        f"WS status={status} carries a P1 open_issue (canonical for the "
                        f"`blocking_pre_ib` / `blocking_pre_code` / `blocking` aliases per "
                        f'ADR-013): "{preview}". WSes that have walked past PROPOSED must '
                        f'resolve every P1 entry before downstream work — "Clarify Before '
                        f'Plan" gate. Fix: settle the question in the WS body (and demote the '
                        f"open_issue to P2/P3 or check it `[x]`), or unlock the WS back to "
                        f"PROPOSED until the blocker resolves."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# L7-ADR-SUPER-MIRROR fix proposer
# --------------------------------------------------------------------------- #

_SUPERSEDED_BY_LINE_RE = re.compile(
    r"^(\*Superseded by:\*\s*)(.+?)\s*$",
    re.MULTILINE,
)


def _propose_l7_supersession_fixes(graph: SpecGraph) -> list[Fix]:
    """For each ADR-A.supersedes ADR-B mirror gap, emit a Fix that adds
    ADR-A to ADR-B's `*Superseded by:*` line in its §Supersession section.

    Skips when the target ADR's file lacks the `*Superseded by:* ...` line.
    """
    fixes: list[Fix] = []
    # Group missing back-pointers by target ADR so a single edit covers
    # multiple supersedes-by relationships in one pass.
    missing_by_target: dict[str, list[str]] = {}
    target_paths: dict[str, str] = {}
    for adr in graph.adrs():
        adr_id = adr["id"]
        sup = adr.get("supersession") or {}
        for ref_id in sup.get("supersedes", []) or []:
            if ref_id == adr_id or not graph.has(ref_id):
                continue
            target = graph.by_id(ref_id) or {}
            target_back = (target.get("supersession") or {}).get("superseded_by", []) or []
            if adr_id not in target_back:
                missing_by_target.setdefault(ref_id, []).append(adr_id)
                target_paths[ref_id] = (target.get("source") or {}).get("path", "")

    for target_id, missing in missing_by_target.items():
        path_str = target_paths.get(target_id, "")
        if not path_str:
            continue
        path = Path(path_str)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        m = _SUPERSEDED_BY_LINE_RE.search(text)
        if not m:
            continue
        prefix = m.group(1)
        current = m.group(2).strip()
        # Build new value
        is_empty = current.lower() in {"none", "n/a"}
        if is_empty:
            new_value = ", ".join(missing)
        else:
            existing = [t.strip() for t in current.split(",")]
            for new_id in missing:
                if new_id not in existing:
                    existing.append(new_id)
            new_value = ", ".join(existing)
        before_line = f"{prefix}{current}"
        after_line = f"{prefix}{new_value}"
        line_number = text[: m.start()].count("\n") + 1
        fixes.append(
            Fix(
                rule="L7-ADR-SUPER-MIRROR",
                artifact_id=target_id,
                file_path=str(path),
                section="supersession.superseded_by",
                added_ids=missing,
                before=before_line,
                after=after_line,
                line_number=line_number,
            )
        )
    return fixes


# --------------------------------------------------------------------------- #
# L8-MSN-INT-MIRROR / L8-INT-MSN-MIRROR fix proposers
# --------------------------------------------------------------------------- #

_INT_MISSION_SECTION_RE = re.compile(
    r"^(##\s+Mission\s*\n\s*\n)(\[?[^\n]+?\]?)\s*$",
    re.MULTILINE,
)
# Last row of the Intent queue table — used as the anchor for appending.
_MSN_QUEUE_LAST_ROW_RE = re.compile(
    r"(### Intent queue.+?\n\|[^\n]*\|\n\|[\s|:-]+\|\n)((?:\|[^\n]*\|\n)+)",
    re.DOTALL,
)


def _propose_l8_mirror_fixes(graph: SpecGraph) -> list[Fix]:
    """Two complementary fix families:

    L8-MSN-INT-MIRROR (target = Intent file):
      Mission lists INT-X in intent_queue, but INT-X.mission is unset.
      Edit the Intent's §Mission section value from `none` (or template
      placeholder) to the Mission ID.

    L8-INT-MSN-MIRROR (target = Mission file):
      Intent.mission references MSN-Y, but MSN-Y.intent_queue has no row.
      Append a queue row to the Mission's §Intent queue table.
    """
    fixes: list[Fix] = []

    intents_by_id = {i["id"]: i for i in graph.intents()}
    missions_by_id = {m["id"]: m for m in graph.missions()}

    # L8-MSN-INT-MIRROR: edit the Intent file
    for msn in missions_by_id.values():
        msn_id = msn["id"]
        for entry in msn.get("intent_queue", []) or []:
            int_id = entry.get("id", "") if isinstance(entry, dict) else entry
            if not int_id or not int_id.startswith("INT-"):
                continue
            intent = intents_by_id.get(int_id)
            if intent is None:
                continue
            int_mission = (intent.get("mission") or {}).get("id")
            if int_mission == msn_id:
                continue  # already mirrored
            path_str = (intent.get("source") or {}).get("path", "")
            if not path_str:
                continue
            path = Path(path_str)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            m = _INT_MISSION_SECTION_RE.search(text)
            if not m:
                continue
            prefix = m.group(1)
            current = m.group(2).strip()
            # Only fix if the current value is "none" or a template placeholder
            if not (current.lower() == "none" or current.startswith("[")):
                continue
            before_line = f"{prefix}{current}"
            after_line = f"{prefix}{msn_id}"
            line_number = text[: m.start()].count("\n") + 2  # H2 + blank + value line
            fixes.append(
                Fix(
                    rule="L8-MSN-INT-MIRROR",
                    artifact_id=int_id,
                    file_path=str(path),
                    section="mission",
                    added_ids=[msn_id],
                    before=before_line,
                    after=after_line,
                    line_number=line_number,
                )
            )

    # L8-INT-MSN-MIRROR: append a row to the Mission's queue table
    for intent in intents_by_id.values():
        int_id = intent["id"]
        msn_ref = (intent.get("mission") or {}).get("id")
        if not msn_ref:
            continue
        # Per ADR-019: OVERSIZED/SUPERSEDED design parents are exempt from the
        # L8-INT-MSN-MIRROR rule — do not propose a queue row that would
        # contradict the Mission's authored decomposition.
        if (intent.get("status") or "DRAFT").upper() in _L8_MIRROR_EXEMPT:
            continue
        mission = missions_by_id.get(msn_ref)
        if mission is None:
            continue
        queue_ids = {
            (e.get("id") if isinstance(e, dict) else e) for e in (mission.get("intent_queue") or [])
        }
        if int_id in queue_ids:
            continue
        path_str = (mission.get("source") or {}).get("path", "")
        if not path_str:
            continue
        path = Path(path_str)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        m = _MSN_QUEUE_LAST_ROW_RE.search(text)
        if not m:
            continue
        header_block = m.group(1)
        rows_block = m.group(2)
        title = intent.get("name", "").strip() or "(no title)"
        intent_type = intent.get("intent_type", "feature")
        status = intent.get("status", "DRAFT")
        new_row = (
            f"| {int_id} | {title[:60]} | {intent_type} | {status} | added by L8 mirror fix |\n"
        )
        before_block = header_block + rows_block
        after_block = header_block + rows_block + new_row
        line_number = text[: m.start()].count("\n") + 1
        fixes.append(
            Fix(
                rule="L8-INT-MSN-MIRROR",
                artifact_id=msn_ref,
                file_path=str(path),
                section="intent_queue",
                added_ids=[int_id],
                before=before_block,
                after=after_block,
                line_number=line_number,
            )
        )

    return fixes


# --------------------------------------------------------------------------- #
# D-15 — Prose drift on WS / IC / IB (ds-52p)
# --------------------------------------------------------------------------- #
#
# Mirrors D17/D18/D19/D20 (AE + Intent prose) onto Working Specs, Interface
# Contracts, and Implementation Briefs. Heuristics reused unchanged:
# _D17_NUMERIC_UNIT for measurable targets, _D18_RATIONALE_PHRASES for
# decision-rationale prose. Citations are exempted (WS-NNN for numerics,
# ADR-NNN for rationale).


def _d15_prose_drift_wsicib(graph: SpecGraph) -> list[Finding]:
    """D-15a (WS), D-15b (IC), D-15c (IB) — prose decision-rationale → ADR.
    D-15d (IC) — prose numeric targets → WS/NFR."""
    out: list[Finding] = []

    # WS: D-15a — rationale prose without ADR cite. Reads the WS's actual
    # prose surfaces (what_this_does.prose + .mechanism). Pre-ds-rv1 read
    # `goal` + `motivation` which the WS parser never emits, so the rule
    # silently never fired.
    for ws in graph.wses():
        ws_id = ws["id"]
        if ws.get("status") in {"DEPRECATED", "SUPERSEDED", "TODO"}:
            continue
        prose_chunks: list[tuple[str, str]] = []
        wtd = ws.get("what_this_does") or {}
        if wtd.get("prose"):
            prose_chunks.append(("what_this_does.prose", wtd["prose"]))
        if wtd.get("mechanism"):
            prose_chunks.append(("what_this_does.mechanism", wtd["mechanism"]))
        for field, text in prose_chunks:
            if not isinstance(text, str):
                continue
            for sentence in _split_sentences(text):
                rat = _D18_RATIONALE_PHRASES.search(sentence)
                if rat and not _ADR_REF.search(sentence):
                    out.append(
                        Finding(
                            severity=P2,
                            rule="D-15a-WS-RATIONALE-NO-ADR-CITE",
                            artifact_id=ws_id,
                            message=(
                                f"WS.{field} contains decision-rationale prose "
                                f"`{rat.group(0)}` outside an ADR citation. "
                                f"Per audit-v2 D-15a, route rationale to an ADR. "
                                f"Snippet: {_truncate(sentence, 180)}"
                            ),
                            fix_kind="semantic",
                        )
                    )

    # IC: D-15b (rationale) + D-15d (numeric → WS)
    for ic in graph.ics():
        ic_id = ic["id"]
        if ic.get("status") == "DEPRECATED":
            continue
        prose_chunks_ic: list[tuple[str, str]] = []
        if ic.get("purpose"):
            prose_chunks_ic.append(("purpose", ic["purpose"]))
        for conv in ic.get("shared_conventions", []) or []:
            if isinstance(conv, str):
                prose_chunks_ic.append(("shared_conventions[]", conv))
        for field, text in prose_chunks_ic:
            for sentence in _split_sentences(text):
                rat = _D18_RATIONALE_PHRASES.search(sentence)
                if rat and not _ADR_REF.search(sentence):
                    out.append(
                        Finding(
                            severity=P2,
                            rule="D-15b-IC-RATIONALE-NO-ADR-CITE",
                            artifact_id=ic_id,
                            message=(
                                f"IC.{field} contains decision-rationale prose "
                                f"`{rat.group(0)}` outside an ADR citation. "
                                f"Per audit-v2 D-15b, route rationale to an ADR. "
                                f"Snippet: {_truncate(sentence, 180)}"
                            ),
                            fix_kind="semantic",
                        )
                    )
                num = _D17_NUMERIC_UNIT.search(sentence)
                if num and not _WS_REF.search(sentence):
                    out.append(
                        Finding(
                            severity=P2,
                            rule="D-15d-IC-NUMERIC-NO-WS-CITE",
                            artifact_id=ic_id,
                            message=(
                                f"IC.{field} contains a measurable target "
                                f"`{num.group(0)}` outside a WS citation. "
                                f"Per audit-v2 D-15d, quantitative targets belong "
                                f"in a Working Spec / NFR — cite it here. "
                                f"Snippet: {_truncate(sentence, 180)}"
                            ),
                            fix_kind="semantic",
                        )
                    )

    # IB: D-15c — rationale prose without ADR cite
    for ib in graph.ibs():
        ib_id = ib["id"]
        if ib.get("status") in {"DEPRECATED", "COMPLETED", "TODO"}:
            continue
        prose_chunks_ib: list[tuple[str, str]] = []
        if ib.get("goal"):
            prose_chunks_ib.append(("goal", ib["goal"]))
        for cd in ib.get("constraints_and_decisions", []) or []:
            if isinstance(cd, dict) and cd.get("rule"):
                prose_chunks_ib.append(
                    (f"constraints_and_decisions[{cd.get('topic', '?')}]", cd["rule"])
                )
        for field, text in prose_chunks_ib:
            for sentence in _split_sentences(text):
                rat = _D18_RATIONALE_PHRASES.search(sentence)
                if rat and not _ADR_REF.search(sentence):
                    out.append(
                        Finding(
                            severity=P2,
                            rule="D-15c-IB-RATIONALE-NO-ADR-CITE",
                            artifact_id=ib_id,
                            message=(
                                f"IB.{field} contains decision-rationale prose "
                                f"`{rat.group(0)}` outside an ADR citation. "
                                f"Per audit-v2 D-15c, route rationale to an ADR. "
                                f"Snippet: {_truncate(sentence, 180)}"
                            ),
                            fix_kind="semantic",
                        )
                    )

    return out


# --------------------------------------------------------------------------- #
# T-glossary self-consistency (ds-52p, D-16)
# --------------------------------------------------------------------------- #


def _t_glossary_self_consistency(graph: SpecGraph) -> list[Finding]:
    """T-GLOSSARY-DUPLICATE: same canonical term appears twice.
    T-GLOSSARY-MISSING-DEFINITION: term row has empty canonical_definition.
    T-GLOSSARY-DANGLING-ALIAS: an alias names a term not present in the glossary."""
    out: list[Finding] = []
    glossary = graph.glossary()
    if glossary is None:
        return out
    terms = glossary.get("terms", []) or []
    by_term: dict[str, list[str]] = {}
    for entry in terms:
        term = entry.get("term", "").strip()
        if not term:
            continue
        by_term.setdefault(term.lower(), []).append(entry.get("category", "?"))
    for term_lower, cats in by_term.items():
        if len(cats) > 1:
            out.append(
                Finding(
                    severity=P2,
                    rule="T-GLOSSARY-DUPLICATE",
                    artifact_id="DOMAIN-GLOSSARY",
                    message=(
                        f"Glossary term `{term_lower}` appears {len(cats)} times "
                        f"(in categories: {', '.join(cats)}). A term must be "
                        f"defined once; consolidate or rename per audit-v2 D-16."
                    ),
                    fix_kind="semantic",
                )
            )
    for entry in terms:
        term = entry.get("term", "").strip()
        if not term:
            continue
        if not (entry.get("canonical_definition") or "").strip():
            out.append(
                Finding(
                    severity=P2,
                    rule="T-GLOSSARY-MISSING-DEFINITION",
                    artifact_id="DOMAIN-GLOSSARY",
                    message=(
                        f"Glossary term `{term}` has empty canonical_definition. "
                        f"Populate the definition column or remove the row per "
                        f"audit-v2 D-16."
                    ),
                    fix_kind="semantic",
                )
            )

    # T-GLOSSARY-DANGLING-ALIAS: aliases must not duplicate canonical-term
    # names of a *different* term, and the canonical term they belong to
    # must exist in the glossary. The current schema attaches aliases to
    # the row that owns them, so the dangling case is when an alias matches
    # a canonical term of a different row (creates ambiguous lookup).
    canonical_terms = {
        entry.get("term", "").strip().lower() for entry in terms if entry.get("term")
    }
    for entry in terms:
        own_term = entry.get("term", "").strip().lower()
        for alias in entry.get("aliases", []) or []:
            alias_lower = alias.strip().lower()
            if not alias_lower or alias_lower == own_term:
                continue
            if alias_lower in canonical_terms:
                out.append(
                    Finding(
                        severity=P3,
                        rule="T-GLOSSARY-DANGLING-ALIAS",
                        artifact_id="DOMAIN-GLOSSARY",
                        message=(
                            f"Glossary term `{entry.get('term')}` lists alias "
                            f"`{alias}` which is also the canonical term of "
                            f"another row. Aliases must be unique non-canonical "
                            f"strings per audit-v2 D-16."
                        ),
                        fix_kind="semantic",
                    )
                )
    return out


# --------------------------------------------------------------------------- #
# T-vision completeness (ds-52p, D-16)
# --------------------------------------------------------------------------- #


_VISION_REQUIRED_SECTIONS = (
    "what_this_is",
    "who_this_is_for",
    "why_this_exists",
    "what_success_looks_like",
    "what_we_are_not_building",
)


def _t_vision_completeness(graph: SpecGraph) -> list[Finding]:
    """T-VISION-MISSING-WHY: the System Vision's `why_this_exists` body is
    absent or empty — this is the load-bearing rationale section.
    T-VISION-INCOMPLETE: any of the five required H2 sections is empty."""
    out: list[Finding] = []
    vision = graph.vision()
    if vision is None:
        return out

    def _empty(value: Any) -> bool:
        """A vision section is empty when it's None, an empty string, or an
        empty list. Vision schema uses str for two sections and array for two."""
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, list):
            return len(value) == 0
        return False

    if _empty(vision.get("why_this_exists")):
        out.append(
            Finding(
                severity=P2,
                rule="T-VISION-MISSING-WHY",
                artifact_id="SYSTEM-VISION",
                message=(
                    "System Vision has no §Why This Exists body. Per audit-v2 "
                    "D-16, this is the load-bearing rationale section; a vision "
                    "without it is incomplete by schema and convention."
                ),
                fix_kind="semantic",
            )
        )
    missing: list[str] = []
    for section in _VISION_REQUIRED_SECTIONS:
        if _empty(vision.get(section)):
            missing.append(section)
    if missing and not (len(missing) == 1 and missing == ["why_this_exists"]):
        # Avoid double-firing with T-VISION-MISSING-WHY when only `why` is empty.
        out.append(
            Finding(
                severity=P2,
                rule="T-VISION-INCOMPLETE",
                artifact_id="SYSTEM-VISION",
                message=(
                    f"System Vision has {len(missing)} required section(s) empty: "
                    f"{', '.join(missing)}. Per audit-v2 D-16, all five "
                    f"(What This Is / Who This Is For / Why This Exists / "
                    f"What Success Looks Like / What We Are Not Building) "
                    f"must be populated."
                ),
                fix_kind="semantic",
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Constitution T-rules (structural completeness — IB-004 / WS-005 BR1 + BR2)
# --------------------------------------------------------------------------- #
#
# Constitution is the third L0 singleton (after System Vision + Domain
# Glossary). The two rules below enforce its structural shape via
# defense-in-depth: parse_constitution + the closed-shape schema catch
# most violations upstream, but if a hand-injected or fixture IR reaches
# the audit layer with structural defects, these rules surface them as
# findings keyed by Article number.
#
# Boundary: T-rules check structure only — see-also paths, ADR-NNN refs,
# and AE-NNN refs are NOT resolved here. That is L-rule scope (IB-005).

_CONSTITUTION_CANONICAL_ARTICLES: tuple[tuple[str, str], ...] = (
    # (canonical title, canonical kind) at each positional index 0..7
    ("Project Identity", "pointer"),
    ("Technology Stack", "text"),
    ("Quality Standards", "text"),
    ("Architecture Principles", "ref-array"),
    ("Development Workflow", "text"),
    ("Model Configuration", "text"),
    ("Boundaries", "ref-array"),
    ("Amendments", "text"),
)


def _t_constitution_article_present(graph: SpecGraph) -> list[Finding]:
    """T-CONSTITUTION-ARTICLE-PRESENT (critical): the eight canonical
    articles are present in the IR in canonical order with the canonical
    title + kind at each index. Missing / extra / out-of-order / wrong-
    kinded articles each surface as one Finding.

    Returns [] when the corpus has no Constitution (the artifact is
    opt-in; Constitution-absent is not a defect at this rule's layer).
    """
    out: list[Finding] = []
    constitution = graph.constitution()
    if constitution is None:
        return out
    articles = constitution.get("articles", [])

    if len(articles) != 8:
        out.append(
            Finding(
                severity=P1,
                rule="T-CONSTITUTION-ARTICLE-PRESENT",
                artifact_id="CONSTITUTION",
                message=(
                    f"Constitution must have exactly 8 articles in canonical "
                    f"order; found {len(articles)}. Per WS-005 BR1, the "
                    f"canonical titles are: Project Identity, Technology "
                    f"Stack, Quality Standards, Architecture Principles, "
                    f"Development Workflow, Model Configuration, Boundaries, "
                    f"Amendments."
                ),
                fix_kind="semantic",
            )
        )

    for i in range(min(len(articles), 8)):
        article = articles[i]
        canonical_title, canonical_kind = _CONSTITUTION_CANONICAL_ARTICLES[i]
        actual_title = article.get("title")
        actual_kind = article.get("kind")
        if actual_title != canonical_title or actual_kind != canonical_kind:
            out.append(
                Finding(
                    severity=P1,
                    rule="T-CONSTITUTION-ARTICLE-PRESENT",
                    artifact_id="CONSTITUTION",
                    message=(
                        f"Article {i + 1} expected: {canonical_title!r} "
                        f"(kind={canonical_kind!r}); actual: "
                        f"{actual_title!r} (kind={actual_kind!r}). "
                        f"Per WS-005 BR1, both title and kind are pinned "
                        f"positionally."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


def _t_constitution_article_populated(graph: SpecGraph) -> list[Finding]:
    """T-CONSTITUTION-ARTICLE-POPULATED (important): each of the eight
    articles has non-empty content per its kind. Pointer articles need
    non-empty summary + see_also; text articles need non-empty body;
    ref-array articles need at least one ref entry (Article 4: adr_refs;
    Article 7: at least one of adr_refs OR ae_refs, per WS-005 BR2 lenient
    reading — schema does not enforce minItems on either array).

    Returns [] when the corpus has no Constitution.
    """
    out: list[Finding] = []
    constitution = graph.constitution()
    if constitution is None:
        return out
    articles = constitution.get("articles", [])

    for i in range(min(len(articles), 8)):
        article = articles[i]
        kind = article.get("kind")
        article_num = i + 1
        title = article.get("title", "?")
        empty_reason: str | None = None

        if kind == "pointer":
            summary = (article.get("summary") or "").strip()
            see_also = (article.get("see_also") or "").strip()
            if not summary or not see_also:
                missing_parts: list[str] = []
                if not summary:
                    missing_parts.append("summary")
                if not see_also:
                    missing_parts.append("see_also")
                empty_reason = f"empty (kind=pointer): {' and '.join(missing_parts)} missing"
        elif kind == "ref-array":
            adr_refs = article.get("adr_refs") or []
            ae_refs = article.get("ae_refs") or []
            if article_num == 7:
                # Lenient: Article 7 (Boundaries) requires at least ONE
                # of adr_refs or ae_refs to be non-empty per WS-005 BR2.
                if not adr_refs and not ae_refs:
                    empty_reason = "empty (kind=ref-array): both adr_refs and ae_refs are empty"
            else:
                # Article 4 only has adr_refs; require it non-empty.
                if not adr_refs:
                    empty_reason = "empty (kind=ref-array): adr_refs is empty"
        elif kind == "text":
            body = (article.get("body") or "").strip()
            if not body:
                empty_reason = "empty (kind=text): body is whitespace-only or missing"

        if empty_reason is not None:
            out.append(
                Finding(
                    severity=P2,
                    rule="T-CONSTITUTION-ARTICLE-POPULATED",
                    artifact_id="CONSTITUTION",
                    message=f"Article {article_num} ({title}) is {empty_reason}.",
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Constitution L-rules (linkage integrity — IB-005 / WS-005 BR3 + BR4 + BR5)
# --------------------------------------------------------------------------- #
#
# Where the T-rules check structure, the L-rules check cross-reference
# resolution. Each rule reads the parsed Constitution IR + walks the
# SpecGraph's ADR / AE registries (and filesystem for the SV singleton)
# to verify every typed reference resolves. Critical findings on
# dangling refs; opt-in absent-Constitution returns [] per the IB-004
# precedent.
#
# All three rules walk the typed-ref ARRAYS only — they do NOT match
# `ADR-NNN` / `AE-NNN` mentions inside `summary` / `body` prose. That
# guard is enforced by the false-positive test
# (`test_adr_refs_rule_does_not_match_prose_mentions`).


def _l_constitution_article_1_sv_ref(graph: SpecGraph) -> list[Finding]:
    """L-CONSTITUTION-ARTICLE-1-SV-REF (critical): Article 1's
    `see_also` path resolves to an existing markdown file relative to
    the repo root. Kind-validation (is the target actually a SV?) is a
    follow-on enhancement — this rule checks file-existence + .md
    suffix only.
    """
    out: list[Finding] = []
    constitution = graph.constitution()
    if constitution is None:
        return out
    articles = constitution.get("articles", [])
    if len(articles) < 1:
        return out
    see_also = (articles[0].get("see_also") or "").strip()
    if not see_also:
        return out  # T-rule covers empty see_also
    repo_root = graph.repo_root or Path(".")
    resolved = repo_root / see_also
    if not resolved.is_file() or resolved.suffix != ".md":
        out.append(
            Finding(
                severity=P1,
                rule="L-CONSTITUTION-ARTICLE-1-SV-REF",
                artifact_id="CONSTITUTION",
                message=(
                    f"Article 1 see_also {see_also!r} does not resolve to an "
                    f"existing markdown file under repo root ({repo_root}). "
                    f"Either fix the path or author the missing System Vision."
                ),
                fix_kind="semantic",
            )
        )
    return out


def _l_constitution_article_4_adr_refs(graph: SpecGraph) -> list[Finding]:
    """L-CONSTITUTION-ARTICLE-4-ADR-REFS (critical): every entry in
    Article 4's `adr_refs` typed array resolves to a registered ADR.
    Walks the typed array only — prose mentions of `ADR-NNN` inside
    `summary` / `body` are NOT considered.
    """
    out: list[Finding] = []
    constitution = graph.constitution()
    if constitution is None:
        return out
    articles = constitution.get("articles", [])
    if len(articles) < 4:
        return out
    for ref in articles[3].get("adr_refs", []) or []:
        adr_id = ref.get("id")
        if adr_id and not graph.has(adr_id):
            out.append(
                Finding(
                    severity=P1,
                    rule="L-CONSTITUTION-ARTICLE-4-ADR-REFS",
                    artifact_id="CONSTITUTION",
                    message=(
                        f"Article 4 cites {adr_id} which does not exist in "
                        f"dekspec/adrs/. Either rename the ref or author "
                        f"the missing ADR."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


def _l_constitution_article_7_boundary_refs(graph: SpecGraph) -> list[Finding]:
    """L-CONSTITUTION-ARTICLE-7-BOUNDARY-REFS (critical): every entry
    in Article 7's `adr_refs` AND `ae_refs` typed arrays resolves.
    Single rule code, two emit branches per WS-005 BR5 + IB-005 Open
    Issue #1 default. Walks typed arrays only.
    """
    out: list[Finding] = []
    constitution = graph.constitution()
    if constitution is None:
        return out
    articles = constitution.get("articles", [])
    if len(articles) < 7:
        return out
    article_7 = articles[6]
    for ref in article_7.get("adr_refs", []) or []:
        adr_id = ref.get("id")
        if adr_id and not graph.has(adr_id):
            out.append(
                Finding(
                    severity=P1,
                    rule="L-CONSTITUTION-ARTICLE-7-BOUNDARY-REFS",
                    artifact_id="CONSTITUTION",
                    message=(
                        f"Article 7 cites {adr_id} which does not exist in "
                        f"dekspec/adrs/. Either rename the ref or author "
                        f"the missing ADR."
                    ),
                    fix_kind="semantic",
                )
            )
    for ref in article_7.get("ae_refs", []) or []:
        ae_id = ref.get("id")
        if ae_id and not graph.has(ae_id):
            out.append(
                Finding(
                    severity=P1,
                    rule="L-CONSTITUTION-ARTICLE-7-BOUNDARY-REFS",
                    artifact_id="CONSTITUTION",
                    message=(
                        f"Article 7 cites {ae_id} which does not exist in "
                        f"dekspec/architecture-elements/. Either rename the "
                        f"ref or author the missing AE."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# T-SEC-* — Security Profile structural completeness + within-SP cross-field
# consistency (IB-034 / WS-020 BR1-BR4 + BR6 body constraint)
#
# Each rule body uses ONLY `graph.security_profiles()` for graph access per
# ADR-011's §Validation predicate "Observable confirmation". No other
# `graph.<accessor>(` call appears in any of the four functions. Asserted
# by IB-035's static-grep test test_t_sec_rule_bodies_only_call_security_
# profiles_accessor (the BR6 verification surface).
# --------------------------------------------------------------------------- #


def _t_sec_owasp_coverage_gap(graph: SpecGraph) -> list[Finding]:
    """T-SEC-OWASP-COVERAGE-GAP (P1): claims-vs-enforcement consistency
    between owasp_coverage[].mapped_tool and sast_tools[].name ∪
    dast_tools[].name.

    Per SP: build the set of declared tool names. For each owasp_coverage
    entry, if mapped_tool is non-empty AND not in that set, emit one
    Finding. Over-match guard: only the typed `mapped_tool` field is
    inspected — never `mitigation_strategy` prose (which may contain
    incidental tool mentions per WS-020 §Silent Failure Domain(s) row
    "Audit rule false-positive").

    Empty SP corpus → [].
    """
    out: list[Finding] = []
    profiles = list(graph.security_profiles())
    if not profiles:
        return out
    for sp in profiles:
        sp_id = sp.get("id") or "SP-UNKNOWN"
        tools = {t["name"] for t in sp.get("sast_tools", []) or [] if t.get("name")} | {
            t["name"] for t in sp.get("dast_tools", []) or [] if t.get("name")
        }
        for entry in sp.get("owasp_coverage", []) or []:
            mapped_tool = entry.get("mapped_tool", "")
            if not mapped_tool:
                continue
            if mapped_tool not in tools:
                owasp_id = entry.get("owasp_id", "?")
                out.append(
                    Finding(
                        severity=P1,
                        rule="T-SEC-OWASP-COVERAGE-GAP",
                        artifact_id=sp_id,
                        message=(
                            f"Profile claims OWASP {owasp_id} coverage via "
                            f"{mapped_tool!r} but {mapped_tool!r} is not in "
                            f"sast_tools or dast_tools."
                        ),
                        fix_kind="semantic",
                    )
                )
    return out


def _t_sec_supply_chain_empty(graph: SpecGraph) -> list[Finding]:
    """T-SEC-SUPPLY-CHAIN-EMPTY (P3): declared dependency-scan tooling
    paired with empty supply_chain.allowed_sources.

    Per SP: scan sast_tools[] for any entry whose ruleset (case-
    insensitive substring) contains "dependency-scan". If at least one
    such entry exists AND supply_chain.allowed_sources is empty (or
    supply_chain is absent), emit ONE Finding per SP (not per matching
    sast entry — the SP-level claims-coverage gap is the load-bearing
    signal, not the per-tool count). Empty corpus → [].
    """
    out: list[Finding] = []
    profiles = list(graph.security_profiles())
    if not profiles:
        return out
    for sp in profiles:
        sp_id = sp.get("id") or "SP-UNKNOWN"
        first_match_name: str | None = None
        for tool in sp.get("sast_tools", []) or []:
            ruleset = tool.get("ruleset", "") or ""
            if "dependency-scan" in ruleset.lower():
                first_match_name = tool.get("name") or "?"
                break
        if first_match_name is None:
            continue
        allowed_sources = (sp.get("supply_chain") or {}).get("allowed_sources", []) or []
        if not allowed_sources:
            out.append(
                Finding(
                    severity=P3,
                    rule="T-SEC-SUPPLY-CHAIN-EMPTY",
                    artifact_id=sp_id,
                    message=(
                        f"Profile declares dependency-scan tooling "
                        f"({first_match_name!r}) but "
                        f"supply_chain.allowed_sources is empty."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


def _t_sec_secret_store_enum(graph: SpecGraph) -> list[Finding]:
    """T-SEC-SECRET-STORE-ENUM (P0): structural completeness of
    secret_stores[] entries.

    Per SP: for each entry, for each required field in {name, kind,
    scope}, if the field's stripped value is empty (or the key is
    absent), emit one Finding. Empty secret_stores[] (or absent key)
    fires zero — legitimate "no commitment" state per WS-020 BR3.
    Empty SP corpus → [].
    """
    out: list[Finding] = []
    profiles = list(graph.security_profiles())
    if not profiles:
        return out
    for sp in profiles:
        sp_id = sp.get("id") or "SP-UNKNOWN"
        secret_stores = sp.get("secret_stores", []) or []
        for i, entry in enumerate(secret_stores):
            for field in ("name", "kind", "scope"):
                value = entry.get(field, "")
                if not isinstance(value, str) or value.strip() == "":
                    out.append(
                        Finding(
                            severity=P0,
                            rule="T-SEC-SECRET-STORE-ENUM",
                            artifact_id=sp_id,
                            message=(
                                f"secret_stores entry at index {i} is missing "
                                f"required field {field!r}."
                            ),
                            fix_kind="semantic",
                        )
                    )
    return out


def _t_sec_authn_method_consistency(graph: SpecGraph) -> list[Finding]:
    """T-SEC-AUTHN-METHOD-CONSISTENCY (P3): each authn_methods[].scope
    must equal at least one allowed_dataflows[].sink (full case-sensitive
    equality, no suffix/prefix matching).

    Per SP: build the set of declared sinks. For each authn_methods
    entry, if scope is non-empty AND not in that set, emit one Finding.
    The case-sensitive equality requirement is the explicit false-
    positive guard per WS-020 BR4 + §Silent Failure Domain(s) row
    "Audit rule false-positive" — partial matches must NOT clear the
    check. Empty corpus → [].
    """
    out: list[Finding] = []
    profiles = list(graph.security_profiles())
    if not profiles:
        return out
    for sp in profiles:
        sp_id = sp.get("id") or "SP-UNKNOWN"
        sinks = {d["sink"] for d in sp.get("allowed_dataflows", []) or [] if d.get("sink")}
        for entry in sp.get("authn_methods", []) or []:
            scope = entry.get("scope")
            if not scope:
                continue
            if scope not in sinks:
                authn_name = entry.get("name", "?")
                out.append(
                    Finding(
                        severity=P3,
                        rule="T-SEC-AUTHN-METHOD-CONSISTENCY",
                        artifact_id=sp_id,
                        message=(
                            f"authn_methods entry {authn_name!r} declares "
                            f"scope {scope!r} but no allowed_dataflows entry "
                            f"sinks to {scope!r}."
                        ),
                        fix_kind="semantic",
                    )
                )
    return out


# --------------------------------------------------------------------------- #
# T-SUPPLY-CHAIN-NEW-DEPENDENCY (P3) — supply-chain hygiene advisory (ds-tygt).
#
# NOT a member of the SP-IR-pure T-SEC-* family: it consults graph.repo_root,
# which the ADR-011 isolation invariant forbids T-SEC bodies from doing. It is
# a sibling supply-chain advisory in the security-profile audit family, gated on
# the presence of at least one Security Profile so it fires only for repos that
# have declared a security posture.
#
# Encodes the "14-day new-package rule" (do not lean on a dependency pinned to a
# version published < 14 days ago without explicit human approval). Publish
# dates are resolved OFFLINE from a local cache the consumer maintains at
# `.dekspec/package-publish-dates.json` ({"name==version": "YYYY-MM-DD", ...}).
# Absent / malformed cache, or an unparseable date, emits nothing — "metadata
# not resolvable" is a clean state, never a finding. No network call is made
# during the audit; a registry-backed resolver that POPULATES the cache is an
# explicit downstream opt-in, kept out of the deterministic audit path.
# --------------------------------------------------------------------------- #

_NEW_DEPENDENCY_AGE_DAYS = 14
_PACKAGE_PUBLISH_DATES_CACHE = ".dekspec/package-publish-dates.json"


def _audit_today() -> _date:
    """Reference 'today' (UTC) for dependency-age math. Test seam — monkeypatch
    this to pin a deterministic date."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).date()


def _parse_publish_date(value: Any) -> _date | None:
    """Parse a cache value into a calendar date. Accepts 'YYYY-MM-DD' and full
    ISO-8601 datetimes (the first 10 chars are the date). Unparseable → None."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return _date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _t_supply_chain_new_dependency(graph: SpecGraph) -> list[Finding]:
    """T-SUPPLY-CHAIN-NEW-DEPENDENCY (P3): flag dependencies pinned to a version
    published fewer than 14 days ago (offline, cache-resolved).

    Fires only when the repo declares at least one Security Profile. Reads
    `.dekspec/package-publish-dates.json` relative to graph.repo_root; absent or
    malformed cache → []. One advisory Finding per dependency younger than the
    threshold. Future-dated and unparseable entries are skipped (treated as
    unresolvable, never a finding)."""
    import json as _json

    out: list[Finding] = []
    if not list(graph.security_profiles()):
        return out
    root = Path(graph.repo_root) if graph.repo_root else Path(".")
    cache_path = root / _PACKAGE_PUBLISH_DATES_CACHE
    if not cache_path.is_file():
        return out
    try:
        data = _json.loads(cache_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return out
    if not isinstance(data, dict):
        return out
    today = _audit_today()
    for key in sorted(data):
        if not isinstance(key, str) or key.startswith("_"):
            continue
        pub = _parse_publish_date(data[key])
        if pub is None:
            continue
        age_days = (today - pub).days
        if 0 <= age_days < _NEW_DEPENDENCY_AGE_DAYS:
            out.append(
                Finding(
                    severity=P3,
                    rule="T-SUPPLY-CHAIN-NEW-DEPENDENCY",
                    artifact_id=key,
                    message=(
                        f"Dependency {key!r} was published {age_days} day(s) ago "
                        f"(< {_NEW_DEPENDENCY_AGE_DAYS}-day threshold). Confirm explicit "
                        f"human approval before relying on it (supply-chain hygiene); if "
                        f"a breach trends for this package, scan local projects for the "
                        f"pinned version."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# INT-020 — DRAFT-slug temp-ID + append-only registry audit rules
# --------------------------------------------------------------------------- #


def _l_no_draft_in_main(graph: SpecGraph) -> list[Finding]:
    """L-NO-DRAFT-IN-MAIN (P0): no DRAFT-prefixed artifact may reach main.

    DRAFT artifacts (`<KIND>-DRAFT-<slug>.md`, INT-020) carry a temporary ID
    and must be allocated to a canonical `<KIND>-NNN` ID via
    `dekspec id allocate` before commit. The SpecGraph loader skips DRAFT
    files, so they never parse-fail — this rule re-walks the artifact dirs
    and fires once per DRAFT file found, catching engineers who somehow
    committed without running allocate.
    """
    from ..draft_ids import is_draft_filename

    out: list[Finding] = []
    dekspec_dir = graph.dekspec_dir
    if dekspec_dir is None or not dekspec_dir.exists():
        return out
    # (dirname, recursive) — mirror SpecGraph.load's artifact-dir layout.
    dirs = [
        ("adrs", False),
        ("architecture-elements", False),
        ("working-specs", False),
        ("interface-contracts", False),
        ("security-profiles", False),
        ("impl-briefs", True),
        ("intents", True),
        ("missions", True),
    ]
    for dirname, recursive in dirs:
        d = dekspec_dir / dirname
        if not d.exists():
            continue
        iterator = d.rglob("*.md") if recursive else d.glob("*.md")
        for p in sorted(iterator):
            if not is_draft_filename(p.name):
                continue
            try:
                rel = p.relative_to(dekspec_dir.parent)
            except ValueError:
                rel = Path(p.name)
            out.append(
                Finding(
                    severity=P0,
                    rule="L-NO-DRAFT-IN-MAIN",
                    artifact_id=p.name,
                    message=(
                        f"DRAFT artifact {rel} carries a temporary "
                        f"`<KIND>-DRAFT-<slug>` ID. Run `dekspec id allocate` to "
                        f"assign a canonical ID before committing to the main "
                        f"branch."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


def _l_registry_append_only(graph: SpecGraph) -> list[Finding]:
    """L-REGISTRY-APPEND-ONLY (P1): the registry is grow-only.

    Compares the current `dekspec/registry.yaml` against its last committed
    version (`git show HEAD:dekspec/registry.yaml`). Fires if any committed
    entry is missing from, or has changed fields in, the current file.
    Appended (new) entries are fine.

    No findings when: the file is absent (registry is optional), the path is
    not present in HEAD (newly added file), or git is unavailable.
    """
    import subprocess

    out: list[Finding] = []
    repo_root = graph.repo_root
    if repo_root is None:
        return out
    dekspec_dir = graph.dekspec_dir
    if dekspec_dir is None:
        return out
    registry_file = dekspec_dir / "registry.yaml"
    if not registry_file.exists():
        return out  # registry is optional — absent ⇒ no findings

    # The path git uses is relative to the repo root.
    try:
        rel_path = registry_file.resolve().relative_to(Path(repo_root).resolve())
    except ValueError:
        return out
    rel_posix = rel_path.as_posix()

    try:
        committed = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"HEAD:{rel_posix}"],
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return out  # git unavailable — degrade gracefully
    if committed.returncode != 0:
        # Path not in HEAD (newly added) or no HEAD yet — nothing to compare.
        return out

    import yaml as _yaml

    try:
        committed_data = _yaml.safe_load(committed.stdout) or {}
        current_data = _yaml.safe_load(registry_file.read_text(encoding="utf-8")) or {}
    except _yaml.YAMLError:
        return out  # malformed YAML is a separate concern (RegistryError)

    def _by_id(data: dict) -> dict[str, dict]:
        return {
            e["id"]: e for e in (data.get("entries") or []) if isinstance(e, dict) and "id" in e
        }

    committed_entries = _by_id(committed_data)
    current_entries = _by_id(current_data)

    for entry_id, committed_entry in sorted(committed_entries.items()):
        if entry_id not in current_entries:
            out.append(
                Finding(
                    severity=P1,
                    rule="L-REGISTRY-APPEND-ONLY",
                    artifact_id=entry_id,
                    message=(
                        f"Registry entry {entry_id} present in the committed "
                        f"dekspec/registry.yaml has been removed. The registry "
                        f"is append-only — restore the entry."
                    ),
                    fix_kind="semantic",
                )
            )
        elif current_entries[entry_id] != committed_entry:
            out.append(
                Finding(
                    severity=P1,
                    rule="L-REGISTRY-APPEND-ONLY",
                    artifact_id=entry_id,
                    message=(
                        f"Registry entry {entry_id} has been modified vs the "
                        f"committed dekspec/registry.yaml. The registry is "
                        f"append-only — revert the change to {entry_id}."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# INT-021 — approval-gate enforcement (the `team` audit profile)
# --------------------------------------------------------------------------- #

# Artifact-kind label → (dir name, recursive) for the on-disk corpus walk.
# The label matches the `approval_gates.<Kind>` key in `profiles/team.yaml`.
_APPROVAL_GATE_DIRS: list[tuple[str, str, bool]] = [
    ("ADR", "adrs", False),
    ("AE", "architecture-elements", False),
    ("WS", "working-specs", False),
    ("IC", "interface-contracts", False),
    ("SecurityProfile", "security-profiles", False),
    ("Intent", "intents", True),
    ("Mission", "missions", True),
]

# Statuses recognized in Amendment Log transition prose. A "status-transition
# row" is one whose `change` text contains `<FROM> <arrow|to> <TO>` for two of
# these tokens. Order longest-first is irrelevant — all are fixed-width words.
_APPROVAL_GATE_STATUSES = (
    # `TODO` is kept here because it remains a valid status on
    # non-Intent artifacts (AE, WS, IB, Mission); `TESTFAIL` retired
    # 2026-05-25 (E3 audit) and is no longer recognised on any kind.
    "TODO",
    "DRAFT",
    "OVERSIZED",
    "PROPOSED",
    "ACCEPTED",
    "IMPLEMENTING",
    "TESTPASS",
    "MERGED",
    "LOCKED",
    "SUPERSEDED",
    "DEPRECATED",
)

# `<FROM> -> <TO>` / `<FROM> → <TO>` / `<FROM> to <TO>` between two known
# statuses. Used to detect status-transition rows in Amendment Log prose.
_APPROVAL_TRANSITION_RE = re.compile(
    r"\b(" + "|".join(_APPROVAL_GATE_STATUSES) + r")\b"
    r"\s*(?:->|→|to|=>)\s*"
    r"\b(" + "|".join(_APPROVAL_GATE_STATUSES) + r")\b"
)


def _parse_amendment_rows(text: str) -> list[dict[str, str]]:
    """Parse the raw `## Amendment Log` table into ordered row dicts.

    Returns a list of `{date, type, change, author}` dicts in document order.
    Unlike the IR parser's `_extract_amendment_log`, this preserves the `type`
    column VERBATIM (lowercased + stripped) — the IR parser coerces unknown
    types such as `review-approval` to `editorial`, which would make this rule
    unable to count signature rows. Header + separator rows are skipped.
    """
    sec = re.compile(r"^#+[ \t]+Amendment Log[ \t]*$", re.MULTILINE)
    sm = sec.search(text)
    if not sm:
        return []
    body = text[sm.end() :]
    # Stop at the next heading of the same-or-higher level.
    nxt = re.compile(r"^#{1,6}[ \t]+\S", re.MULTILINE)
    nm = nxt.search(body)
    if nm:
        body = body[: nm.start()]
    rows: list[dict[str, str]] = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 4:
            continue
        date, rtype, change, author = cells[0], cells[1], cells[2], cells[3]
        # Skip the header row and the `---|---` separator row.
        if set(date) <= {"-", " ", ":"} and set(rtype) <= {"-", " ", ":"}:
            continue
        if date.lower() == "date" and rtype.lower() == "type":
            continue
        rows.append(
            {
                "date": date,
                "type": rtype.lower(),
                "change": change,
                "author": author,
            }
        )
    return rows


def _classify_transition(change: str) -> tuple[str, str] | None:
    """Return `(from_status, to_status)` if `change` prose names a status
    transition, else None. When the prose chains multiple transitions
    (e.g. `DRAFT → PROPOSED → ACCEPTED`), the first and last tokens win —
    the row's net effect is `first_to_last`."""
    matches = _APPROVAL_TRANSITION_RE.findall(change)
    if not matches:
        return None
    first_from = matches[0][0].upper()
    last_to = matches[-1][1].upper()
    return (first_from, last_to)


def _approval_gate_for_artifact(
    kind: str,
    text: str,
    profile,  # AuditProfile — typed loosely to avoid an import cycle
) -> tuple[str, dict[str, Any], int] | None:
    """Resolve the active approval gate (if any) for one artifact.

    Returns `(transition_label, gate_dict, signature_count)` when the
    artifact's most recent status-transition row matches a gate declared on
    the active profile; None when there is no gated transition to enforce.

    `signature_count` is the number of `review-approval` rows recorded
    BETWEEN the previous status-transition row and the current one
    (exclusive of both) — the deterministic INT-021 counting rule.
    """
    rows = _parse_amendment_rows(text)
    if not rows:
        return None
    # Index every status-transition row.
    transition_idx: list[tuple[int, tuple[str, str]]] = []
    for i, row in enumerate(rows):
        t = _classify_transition(row["change"])
        if t is not None:
            transition_idx.append((i, t))
    if not transition_idx:
        return None
    current_pos, (from_status, to_status) = transition_idx[-1]
    transition_label = f"{from_status}_to_{to_status}"
    gate = profile.gate(kind, transition_label)
    if gate is None:
        return None
    # Count review-approval rows strictly between the previous transition
    # row and the current one (exclusive of both endpoints).
    prev_pos = transition_idx[-2][0] if len(transition_idx) >= 2 else -1
    signature_count = sum(
        1 for j in range(prev_pos + 1, current_pos) if rows[j]["type"] == "review-approval"
    )
    return (transition_label, gate, signature_count)


def _t_approval_gate(graph: SpecGraph, profile) -> list[Finding]:
    """T-APPROVAL-GATE (P0): enforce per-transition reviewer-signature gates.

    Profile-aware. Reads `approval_gates` from the active profile (INT-021).
    When the active profile declares NO `approval_gates` — i.e. the default
    `v1` profile — this rule yields nothing. Under the `team` profile, for
    each artifact whose `## Amendment Log` shows a status-transition row, it
    counts `review-approval` signature rows recorded between the previous
    status-transition row and the current one (exclusive of both); if the
    count is below the gate's `required_reviewers`, it emits a P0 Finding.

    `reviewer_role` is ADVISORY in V1 — the rule counts signatures regardless
    of the signer's role; the declared role is named in the finding for
    documentation only.
    """
    out: list[Finding] = []
    # Profile-aware activation: no `approval_gates` → silent (v1).
    if not getattr(profile, "approval_gates", None):
        return out
    dekspec_dir = graph.dekspec_dir
    if dekspec_dir is None or not dekspec_dir.exists():
        return out
    for kind, dirname, recursive in _APPROVAL_GATE_DIRS:
        if kind not in profile.approval_gates:
            continue
        d = dekspec_dir / dirname
        if not d.exists():
            continue
        iterator = d.rglob("*.md") if recursive else d.glob("*.md")
        for p in sorted(iterator):
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            resolved = _approval_gate_for_artifact(kind, text, profile)
            if resolved is None:
                continue
            transition_label, gate, signature_count = resolved
            required = int(gate.get("required_reviewers", 0))
            if signature_count >= required:
                continue
            reviewer_role = gate.get("reviewer_role", "reviewer")
            missing = required - signature_count
            pretty = transition_label.replace("_to_", " -> ")
            out.append(
                Finding(
                    severity=P0,
                    rule="T-APPROVAL-GATE",
                    artifact_id=p.name,
                    message=(
                        f"{p.name} walked the {pretty} transition with "
                        f"{signature_count} of {required} required "
                        f"`review-approval` signature(s) — {missing} more "
                        f"signature(s) of role `{reviewer_role}` must be "
                        f"recorded in the `## Amendment Log`. Append signatures "
                        f"via the artifact's authoring skill in `--approve` mode."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# L15-INDEX-FILE-COHERENCE (advisory) — artifact-index <-> file coherence
# --------------------------------------------------------------------------- #

# Each entry: (index filename, artifact ID regex, IR iterator attr name).
# The check parses every markdown table in the index, locates the ID column
# and the Status / Version columns by header name, and verifies that every
# artifact IR has a row whose Status (and Version, where the index carries a
# Version column) matches the IR. The IR — i.e. the artifact file itself — is
# canonical; a drifted row is the index's defect.
#
# `intent-index.md` carries two tables (Active queue + Archive) with different
# column shapes; the parser handles every table in the file, so an Intent in
# either table is covered. Indexes without a recognizable Status column are
# skipped (none are today). No index is excluded.
#
# Each ID pattern is bracketed with a left negative lookbehind
# `(?<![A-Za-z0-9-])` and a right negative lookahead `(?!\d)`. The left guard
# prevents matching the canonical `INT-NNN` (or `ADR-NNN`, etc.) inside a
# provisional `P-INT-NNN` cell — without it, a `P-INT-007` row would shadow
# the real `INT-007` row when the rule scans for `INT-007`, surfacing a
# spurious Status drift. The right guard prevents the 3+ digit pattern from
# greedy-consuming a longer numeric suffix (`INT-0070`) when the canonical
# ID is `INT-007`.
_INDEX_COHERENCE_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("adr-index.md", r"(?<![A-Za-z0-9-])ADR-\d{3,}(?!\d)", "adrs"),
    ("architecture-elements-index.md", r"(?<![A-Za-z0-9-])AE-\d{3,}(?!\d)", "aes"),
    ("interface-contract-index.md", r"(?<![A-Za-z0-9-])IC-\d{3,}(?!\d)", "ics"),
    ("intent-index.md", r"(?<![A-Za-z0-9-])INT-\d{3,}(?!\d)", "intents"),
    ("working-spec-index.md", r"(?<![A-Za-z0-9-])WS-\d{3,}(?!\d)", "wses"),
    ("mission-index.md", r"(?<![A-Za-z0-9-])MSN-\d{3,}(?!\d)", "missions"),
)

# Header-cell text (lower-cased, stripped) that identifies the Status and
# Version columns across the four index shapes. The ID column is located
# positionally via the artifact-ID regex match on a data row.
_INDEX_STATUS_HEADERS = frozenset({"status"})
_INDEX_VERSION_HEADERS = frozenset({"version"})

# A markdown table row: leading `|`, cells separated by `|`. The header
# separator row (`|---|---|`) is recognised + skipped by `_is_md_separator`.
_MD_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")

# An unescaped `|` — a pipe NOT preceded by a backslash. Markdown escapes a
# literal pipe inside a cell as `\|`; an index row may legitimately carry one
# (e.g. a `lite \| full` switch label). Splitting on this pattern keeps
# escaped pipes inside their cell rather than spuriously creating a new
# column and shifting every Status/Version lookup rightward.
_MD_UNESCAPED_PIPE_RE = re.compile(r"(?<!\\)\|")


def _split_md_row(line: str) -> list[str] | None:
    """Split one markdown table row into its trimmed cell strings.

    Returns None for non-table lines. Splits only on UNESCAPED `|` so a
    backslash-escaped `\\|` inside a cell stays in that cell. The leading `\\`
    of an escaped pipe is stripped from the trimmed cell text (it is markdown
    syntax, not content). A blank/non-table line between two tables in the
    same file ends the current table; the caller resets header state on it.
    """
    m = _MD_TABLE_ROW_RE.match(line)
    if m is None:
        return None
    return [cell.strip().replace("\\|", "|") for cell in _MD_UNESCAPED_PIPE_RE.split(m.group(1))]


def _is_md_separator(cells: list[str]) -> bool:
    """True if `cells` is a markdown header-separator row (`---`, `:--:`)."""
    return bool(cells) and all(c != "" and set(c) <= set("-:") for c in cells)


def _index_rows(text: str, id_re: re.Pattern[str]) -> dict[str, dict[str, str]]:
    """Parse every markdown table in an index file.

    Returns a map ``{artifact_id: {"status": ..., "version": ...}}``. The
    Status / Version values are taken from the columns whose header cell
    matches `_INDEX_STATUS_HEADERS` / `_INDEX_VERSION_HEADERS`; a column the
    index does not carry is simply absent from the inner dict. The ID is
    extracted by the first `id_re` match in any cell of a data row.

    Handles multiple tables per file (intent-index.md has two): a blank line
    or a non-table line resets the active header state, so the next table's
    own header row re-derives the column positions.
    """
    rows: dict[str, dict[str, str]] = {}
    status_col: int | None = None
    version_col: int | None = None
    have_header = False
    for line in text.splitlines():
        cells = _split_md_row(line)
        if cells is None:
            # Non-table line ends the current table.
            status_col = version_col = None
            have_header = False
            continue
        if _is_md_separator(cells):
            continue
        if not have_header:
            # First table row after a reset is the header row.
            lowered = [c.lower() for c in cells]
            status_col = next(
                (i for i, c in enumerate(lowered) if c in _INDEX_STATUS_HEADERS),
                None,
            )
            version_col = next(
                (i for i, c in enumerate(lowered) if c in _INDEX_VERSION_HEADERS),
                None,
            )
            have_header = True
            continue
        # Data row. Locate the artifact ID by regex over the cells.
        artifact_id: str | None = None
        for cell in cells:
            m = id_re.search(cell)
            if m is not None:
                artifact_id = m.group(0)
                break
        if artifact_id is None:
            continue
        entry: dict[str, str] = {}
        if status_col is not None and status_col < len(cells):
            entry["status"] = cells[status_col].strip()
        if version_col is not None and version_col < len(cells):
            entry["version"] = cells[version_col].strip()
        rows[artifact_id] = entry
    return rows


def _l15_index_file_coherence(graph: SpecGraph) -> list[Finding]:
    """L15-INDEX-FILE-COHERENCE (advisory) — artifact-index <-> file coherence.

    For each artifact index (`adr-index.md`, `architecture-elements-index.md`,
    `interface-contract-index.md`, `intent-index.md`) this rule verifies:

      (a) every artifact file on disk has a row in the index, and
      (b) each row's Status — and Version, where the index carries a Version
          column — matches the artifact file's actual Status / Version.

    The artifact file (its parsed IR) is canonical; a missing or drifted index
    row is the index's defect. One advisory (`P3`) finding is emitted per
    missing or drifted row. The check is index-shape-generic: column positions
    are derived from each table's own header row, so it covers the
    single-table indexes and the two-table `intent-index.md` alike.
    """
    out: list[Finding] = []
    dekspec_dir = graph.dekspec_dir
    if dekspec_dir is None or not dekspec_dir.exists():
        return out
    for filename, id_pattern, iter_attr in _INDEX_COHERENCE_TARGETS:
        index_path = dekspec_dir / filename
        if not index_path.exists():
            continue
        try:
            index_text = index_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        id_re = re.compile(id_pattern)
        rows = _index_rows(index_text, id_re)
        for ir in sorted(graph.__getattribute__(iter_attr)(), key=lambda x: x["id"]):
            artifact_id = ir["id"]
            ir_status = (ir.get("status") or "").strip()
            ir_version = ir.get("version")
            row = rows.get(artifact_id)
            if row is None:
                out.append(
                    Finding(
                        severity=P3,
                        rule="L15-INDEX-FILE-COHERENCE",
                        artifact_id=artifact_id,
                        message=(
                            f"{artifact_id} exists on disk but has no row in "
                            f"`{filename}`. Add a row to the index so it stays a "
                            f"complete live view of its artifact directory."
                        ),
                        fix_kind="semantic",
                    )
                )
                continue
            row_status = row.get("status")
            if row_status is not None and ir_status and row_status != ir_status:
                out.append(
                    Finding(
                        severity=P3,
                        rule="L15-INDEX-FILE-COHERENCE",
                        artifact_id=artifact_id,
                        message=(
                            f"{artifact_id} row in `{filename}` lists Status "
                            f"`{row_status}` but the artifact file's Status is "
                            f"`{ir_status}`. The artifact file is canonical — "
                            f"reconcile the index row to `{ir_status}`."
                        ),
                        fix_kind="semantic",
                    )
                )
            row_version = row.get("version")
            if (
                row_version is not None
                and ir_version is not None
                and str(ir_version).strip()
                and row_version != str(ir_version).strip()
            ):
                out.append(
                    Finding(
                        severity=P3,
                        rule="L15-INDEX-FILE-COHERENCE",
                        artifact_id=artifact_id,
                        message=(
                            f"{artifact_id} row in `{filename}` lists Version "
                            f"`{row_version}` but the artifact file's Version is "
                            f"`{ir_version}`. The artifact file is canonical — "
                            f"reconcile the index row to `{ir_version}`."
                        ),
                        fix_kind="semantic",
                    )
                )
    return out


# --------------------------------------------------------------------------- #
# SI-01-DATE-STALE check and fixer
# --------------------------------------------------------------------------- #

_MODIFIED_SECTION_RE = re.compile(r"(^## Modified\s*?\n\s*?)(\d{4}-\d{2}-\d{2})", re.MULTILINE)


def _si01_date_freshness(graph: SpecGraph) -> list[Finding]:
    """SI-01-DATE-STALE: Verify that an artifact's ## Modified date header
    is not older than the latest date entry in its ## Amendment Log table.
    """
    out: list[Finding] = []
    for art in graph.all():
        art_id = art.get("id")
        modified = art.get("modified")
        amendment_log = art.get("amendment_log", []) or []
        if not art_id or not modified or not amendment_log:
            continue

        log_dates = [
            entry["date"]
            for entry in amendment_log
            if entry.get("date") and re.match(r"^\d{4}-\d{2}-\d{2}$", entry["date"])
        ]
        if not log_dates:
            continue

        latest_log_date = max(log_dates)
        if latest_log_date > modified:
            out.append(
                Finding(
                    severity=P3,
                    rule="SI-01-DATE-STALE",
                    artifact_id=art_id,
                    message=(
                        f"Artifact modified date ({modified}) is older than the "
                        f"latest Amendment Log entry date ({latest_log_date})."
                    ),
                    fix_kind="mechanical",
                )
            )
    return out


def _propose_si01_date_fixes(graph: SpecGraph) -> list[Fix]:
    """For each artifact with a stale ## Modified date, emit a Fix
    advancing the header to match the latest Amendment Log entry date.
    """
    fixes: list[Fix] = []
    for art in graph.all():
        art_id = art.get("id")
        modified = art.get("modified")
        amendment_log = art.get("amendment_log", []) or []
        path_str = (art.get("source") or {}).get("path", "")
        if not art_id or not modified or not amendment_log or not path_str:
            continue

        log_dates = [
            entry["date"]
            for entry in amendment_log
            if entry.get("date") and re.match(r"^\d{4}-\d{2}-\d{2}$", entry["date"])
        ]
        if not log_dates:
            continue

        latest_log_date = max(log_dates)
        if latest_log_date > modified:
            path = Path(path_str)
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            m = _MODIFIED_SECTION_RE.search(text)
            if not m:
                continue

            before_line = m.group(0)
            after_line = f"{m.group(1)}{latest_log_date}"
            line_number = text[: m.start()].count("\n") + 1

            fixes.append(
                Fix(
                    rule="SI-01-DATE-STALE",
                    artifact_id=art_id,
                    file_path=str(path),
                    section="modified",
                    added_ids=[],
                    before=before_line,
                    after=after_line,
                    line_number=line_number,
                )
            )
    return fixes


# --------------------------------------------------------------------------- #
# T-STATUS-* — status-maturity coherence rule family (ADR-020 / INT-070)
# --------------------------------------------------------------------------- #
#
# ADR-020 normalizes every artifact kind's status enum onto one common
# maturity ladder so that dependency edges across kinds are comparable, and
# enforces an `ACCEPTED`-capped invariant on every dependency edge. This
# section implements that model: the band ladder, the two `T-STATUS-*`
# checks, and the bounded `--fix` auto-transition.
#
# Maturity-band ladder (ADR-020 §Decision):
#   band 0  TODO                                  — captured
#   band 1  DRAFT / OVERSIZED                     — drafting
#   band 2  PROPOSED                              — proposed
#   band 3  ACCEPTED / Mission ACTIVE             — accepted / underway
#   band 4  IMPLEMENTING / TESTPASS / MERGED /
#           Mission COMPLETING                    — building
#   band 5  LOCKED / Mission COMPLETE             — locked / done
#
# `DEPRECATED` / `SUPERSEDED` (and Mission `KILLED`) are an off-ramp,
# excluded from every status-coherence check.

# Status token -> maturity band. Mission lifecycle tokens (ACTIVE /
# COMPLETING / COMPLETE) are placed on the same ladder so child-Intent ->
# Mission edges are comparable: ACTIVE (>=1 child LOCKED) sits at band 3,
# the Mission analogue of ACCEPTED; COMPLETING at band 4; COMPLETE at
# band 5.
_MATURITY_BAND: dict[str, int] = {
    # `TODO` band 0 is kept because non-Intent kinds (AE/WS/IB/MSN) still
    # carry it. The Intent enum lost `TODO` + `TESTFAIL` 2026-05-25 (E3
    # audit); `TESTFAIL` no longer appears here because nothing else
    # used it.
    "TODO": 0,
    "DRAFT": 1,
    "OVERSIZED": 1,
    "PROPOSED": 2,
    "ACCEPTED": 3,
    "ACTIVE": 3,  # Mission-only — the Mission analogue of ACCEPTED
    "IMPLEMENTING": 4,
    "TESTPASS": 4,
    "MERGED": 4,
    "COMPLETING": 4,  # Mission-only
    "LOCKED": 5,
    "COMPLETE": 5,  # Mission-only
}

# The off-ramp — excluded from every T-STATUS check on either edge end.
_STATUS_OFFRAMP = frozenset({"DEPRECATED", "SUPERSEDED", "KILLED"})

# The gating threshold: band 3 is `ACCEPTED`. The core invariant
# (ADR-020) — on every edge `consumer -> provider`, if the consumer is at
# band >= ACCEPTED then the provider must be too.
_STATUS_ACCEPTED_BAND = 3


def maturity_band(status: str | None) -> int | None:
    """Map an artifact Status token onto its ADR-020 maturity band.

    Returns the integer band (0..5), or None when the token is unknown or
    on the off-ramp (`DEPRECATED` / `SUPERSEDED` / Mission `KILLED`). A None
    return tells every T-STATUS check to skip that edge end.
    """
    if not status:
        return None
    token = status.strip().strip("`*_").upper()
    if token in _STATUS_OFFRAMP:
        return None
    return _MATURITY_BAND.get(token)


def _t_status_auto_fixable(graph: SpecGraph, artifact_id: str) -> tuple[bool, str]:
    """Whether the lagging artifact can be auto-transitioned to `ACCEPTED`.

    ADR-020's bounded auto-fix only auto-applies a transition that is a
    *clean metadata move with no gated side effect*. An artifact whose
    `ACCEPTED` transition would itself trip a gating audit rule is NOT
    cleanly fixable — its T-STATUS finding is downgraded to flag-only `P3`
    advisory (the engineer must settle the blocker first), and the bounded
    `--fix` sweep skips it. This keeps `dekspec doctor` CLEAN after a sweep:
    the sweep never trades one gating finding for another.

    Returns `(fixable, reason)`. Not auto-fixable when:
      - the artifact is a Mission — Missions have no `ACCEPTED` status; the
        band-3 analogue `ACTIVE` is gated on a child Intent locking.
      - the artifact is a Working Spec carrying an unresolved `P1`
        open_issue — raising it to `ACCEPTED` would trip
        L12-WS-BLOCKING-PRE-IB-CLEAN ("Clarify Before Plan" gate). The WS
        is correctly sub-`ACCEPTED` until the blocker is settled.
    """
    if artifact_id.startswith("MSN-"):
        return False, (
            "provider is a Mission — no `ACCEPTED` status; `ACTIVE` is "
            "reached only when a child Intent locks"
        )
    ir = graph.by_id(artifact_id)
    if ir is None:
        return False, "artifact not in graph"
    if artifact_id.startswith("WS-"):
        for issue in ir.get("open_issues") or []:
            if issue.get("severity") == "P1":
                return False, (
                    "Working Spec carries an unresolved P1 open_issue — "
                    "an `ACCEPTED` transition would trip the "
                    'L12-WS-BLOCKING-PRE-IB-CLEAN "Clarify Before Plan" '
                    "gate; settle the blocker first"
                )
    return True, "clean metadata transition to ACCEPTED"


def _status_dependency_edges(graph: SpecGraph) -> list[tuple[str, str, str]]:
    """Enumerate every spec-graph dependency edge `consumer -> provider`.

    ADR-020 §Decision names six dependency-edge classes; INT-070 §Open
    Issues confirmed the spec graph as built carries exactly these and the
    `T-STATUS-*` family traverses the same edge sources the existing
    L1/L3/L4/L5/L7a/L8 rules use:

      - Intent -> AE        (L7a — linked_architecture_elements)
      - ADR    -> AE        (L1  — related_architecture_elements)
      - WS     -> AE        (L3  — related_architecture_elements)
      - IC     -> AE        (L4  — provider_ae / consumer_aes / parties)
      - WS/IC/IB -> ADR     (governing_adrs forward links)
      - IB     -> WS        (L5  — IB.spec.id)
      - IB     -> Intent    (L5  — IB.intent.id)
      - child-Intent -> Mission (L8 — Intent.mission.id)

    Each tuple is `(consumer_id, provider_id, edge_kind)`. The provider is
    the artifact the consumer forward-links / depends on — the artifact the
    `ACCEPTED`-capped invariant requires to be at least as mature.
    """
    edges: list[tuple[str, str, str]] = []

    # Intent -> AE
    for intent in graph.intents():
        for ref in intent.get("linked_architecture_elements", []) or []:
            ae_id = ref["id"] if isinstance(ref, dict) else ref
            if isinstance(ae_id, str) and ae_id:
                edges.append((intent["id"], ae_id, "Intent->AE"))
        # child-Intent -> Mission
        msn_id = (intent.get("mission") or {}).get("id")
        if isinstance(msn_id, str) and msn_id:
            edges.append((intent["id"], msn_id, "Intent->Mission"))

    # ADR -> AE
    for adr in graph.adrs():
        for ae_id in graph.aes_of_adr(adr["id"]):
            edges.append((adr["id"], ae_id, "ADR->AE"))

    # WS -> AE  +  WS -> ADR
    for ws in graph.wses():
        for ae_id in graph.aes_of_ws(ws["id"]):
            edges.append((ws["id"], ae_id, "WS->AE"))
        for adr_id in SpecGraph._adrs_of(ws):
            edges.append((ws["id"], adr_id, "WS->ADR"))

    # IC -> AE  +  IC -> ADR
    for ic in graph.ics():
        for ae_id in graph.aes_of_ic(ic["id"]):
            edges.append((ic["id"], ae_id, "IC->AE"))
        for adr_id in SpecGraph._adrs_of(ic):
            edges.append((ic["id"], adr_id, "IC->ADR"))

    # IB -> WS  +  IB -> Intent  +  IB -> ADR
    for ib in graph.ibs():
        ws_id = (ib.get("spec") or {}).get("id")
        if isinstance(ws_id, str) and ws_id:
            edges.append((ib["id"], ws_id, "IB->WS"))
        int_id = (ib.get("intent") or {}).get("id")
        if isinstance(int_id, str) and int_id:
            edges.append((ib["id"], int_id, "IB->Intent"))
        for adr_id in SpecGraph._adrs_of(ib):
            edges.append((ib["id"], adr_id, "IB->ADR"))

    return edges


def _t_status_inversion(graph: SpecGraph) -> list[Finding]:
    """T-STATUS-INVERSION — edge-structural status-maturity coherence.

    ADR-020 core invariant: on every dependency edge `consumer -> provider`,
    if `band(consumer) >= ACCEPTED` then `band(provider) >= ACCEPTED`. When
    a settled consumer (band >= 3) depends on an unsettled provider
    (band < 3), the lagging *provider* is the finding's subject — it is the
    artifact that must move.

    Severity (ADR-020 §Decision — gating-vs-advisory two-tier):
      - `P2` (gating, auto-fixable) when the lagging provider can be cleanly
        raised to `ACCEPTED` as a pure metadata move — the bounded `--fix`
        sweep clears it.
      - `P3` (advisory, flag-only) when the provider's `ACCEPTED` transition
        is NOT a clean metadata move — a Mission (no `ACCEPTED` status), or
        a Working Spec carrying an unresolved `P1` open_issue (an `ACCEPTED`
        transition would itself trip L12-WS-BLOCKING-PRE-IB-CLEAN). The
        inversion is surfaced, not gated; the auto-fix never forges it.

    Off-ramp ends (`DEPRECATED` / `SUPERSEDED` / Mission `KILLED`) are
    skipped on either side. One finding per lagging provider, naming the
    out-maturing consumers.
    """
    out: list[Finding] = []

    # provider_id -> (provider_status, [(consumer_id, consumer_status, kind)])
    lagging: dict[str, tuple[str, list[tuple[str, str, str]]]] = {}

    for consumer_id, provider_id, edge_kind in _status_dependency_edges(graph):
        consumer = graph.by_id(consumer_id)
        provider = graph.by_id(provider_id)
        if consumer is None or provider is None:
            # A dangling forward ref — that is L1/L3/L4/L5/L7a's finding,
            # not a status-coherence one.
            continue
        consumer_status = consumer.get("status")
        provider_status = provider.get("status")
        cb = maturity_band(consumer_status)
        pb = maturity_band(provider_status)
        if cb is None or pb is None:
            continue  # off-ramp / unknown on one end — skip the edge
        if cb >= _STATUS_ACCEPTED_BAND and pb < _STATUS_ACCEPTED_BAND:
            entry = lagging.setdefault(provider_id, (provider_status or "", []))
            entry[1].append((consumer_id, consumer_status or "", edge_kind))

    for provider_id in sorted(lagging):
        provider_status, consumers = lagging[provider_id]
        consumers.sort()
        consumer_desc = ", ".join(f"{cid} ({cst})" for cid, cst, _ in consumers)
        # A provider that cannot be cleanly auto-raised to ACCEPTED (a
        # Mission, or a WS with an unresolved P1 blocker) draws a flag-only
        # P3 advisory; everything cleanly fixable is gating P2.
        fixable, reason = _t_status_auto_fixable(graph, provider_id)
        severity = P2 if fixable else P3
        if fixable:
            remedy = (
                "Per the ACCEPTED-capped invariant the provider must be at "
                "least `ACCEPTED`. `dekspec audit linkage --fix` raises it as "
                "a pure metadata transition."
            )
        else:
            remedy = f"Advisory only — not auto-fixable: {reason}. Resolve by hand."
        out.append(
            Finding(
                severity=severity,
                rule="T-STATUS-INVERSION",
                artifact_id=provider_id,
                message=(
                    f"{provider_id} is `{provider_status}` (maturity band below "
                    f"ACCEPTED) but is depended on by settled artifact(s): "
                    f"{consumer_desc}. {remedy}"
                ),
                fix_kind="mechanical" if fixable else "semantic",
            )
        )
    return out


def _closed_bead_statuses() -> frozenset[str]:
    """Statuses that count as a 'closed' decomposition unit for T-STATUS-LAG.

    ADR-020's realized-work signal is 'its beads are all closed'. The
    spec-graph models an artifact's decomposition as its child Implementation
    Briefs (IBs); a `LOCKED` IB is the terminal, demonstrably-done unit. An
    IB at `ACCEPTED` or below is still open work, so it does NOT make the
    parent's decomposition 'complete'.
    """
    return frozenset({"LOCKED"})


def _t_status_lag(graph: SpecGraph) -> list[Finding]:
    """T-STATUS-LAG — realized-work status-maturity coherence.

    ADR-020: an artifact below `ACCEPTED` whose own decomposition is
    *demonstrably complete* has lagged behind its realized work. Two
    realized-work signals are modelled from the spec graph:

      1. Decomposition complete — the artifact has >=1 child Implementation
         Brief and every child IB is `LOCKED` (the terminal done band).
         Off-ramp IBs (`DEPRECATED` / `SUPERSEDED`) are excluded from the
         denominator.
      2. Producing LOCKED Intent — a `LOCKED` Intent forward-links the
         artifact (Intent -> AE), declaring it produced or revised it.

    Engineer ruling (ADR-020 OI-2, resolved 2026-05-22): an artifact with
    NO child IBs AND no producing `LOCKED` Intent is **exempt** — absent any
    realized-work signal the lag check does not fire. (`T-STATUS-INVERSION`
    still reaches such an artifact through its dependency edges.)

    The finding's subject is the lagging artifact itself. Severity `P2`
    (gating, auto-fixable): the correct repair is a transition to
    `ACCEPTED`, a pure metadata move the bounded `--fix` sweep applies.
    Artifacts already at band >= ACCEPTED, and off-ramp artifacts, are
    skipped.
    """
    out: list[Finding] = []
    closed = _closed_bead_statuses()

    # Index: child IBs per parent WS (IB.spec.id) and per parent Intent
    # (IB.intent.id) — the spec-graph decomposition edges.
    ibs_of_ws: dict[str, list[dict[str, Any]]] = {}
    ibs_of_intent: dict[str, list[dict[str, Any]]] = {}
    for ib in graph.ibs():
        ws_id = (ib.get("spec") or {}).get("id")
        if isinstance(ws_id, str) and ws_id:
            ibs_of_ws.setdefault(ws_id, []).append(ib)
        int_id = (ib.get("intent") or {}).get("id")
        if isinstance(int_id, str) and int_id:
            ibs_of_intent.setdefault(int_id, []).append(ib)

    # Index: AEs forward-linked by each LOCKED Intent — the producing-Intent
    # realized-work signal.
    locked_intent_aes: dict[str, list[str]] = {}
    for intent in graph.intents():
        if (intent.get("status") or "").strip().upper() != "LOCKED":
            continue
        for ref in intent.get("linked_architecture_elements", []) or []:
            ae_id = ref["id"] if isinstance(ref, dict) else ref
            if isinstance(ae_id, str) and ae_id:
                locked_intent_aes.setdefault(ae_id, []).append(intent["id"])

    for art in sorted(graph.all(), key=lambda x: x.get("id", "")):
        art_id = art.get("id")
        if not art_id:
            continue
        status = art.get("status")
        band = maturity_band(status)
        if band is None or band >= _STATUS_ACCEPTED_BAND:
            # Off-ramp, unknown, or already settled — nothing to lag.
            continue

        signals: list[str] = []

        # Signal 1 — decomposition complete (all child IBs LOCKED).
        child_ibs = ibs_of_ws.get(art_id, []) + ibs_of_intent.get(art_id, [])
        live_ibs = [
            ib
            for ib in child_ibs
            if (ib.get("status") or "").strip().upper() not in _STATUS_OFFRAMP
        ]
        if live_ibs and all((ib.get("status") or "").strip().upper() in closed for ib in live_ibs):
            ib_ids = ", ".join(sorted(ib["id"] for ib in live_ibs))
            signals.append(f"every child Implementation Brief ({ib_ids}) is LOCKED")

        # Signal 2 — a producing LOCKED Intent.
        producers = locked_intent_aes.get(art_id, [])
        if producers:
            signals.append(
                f"LOCKED Intent(s) {', '.join(sorted(producers))} declare "
                f"this artifact produced/revised"
            )

        if not signals:
            # No realized-work signal — exempt per ADR-020 OI-2.
            continue

        # A lagging artifact that cannot be cleanly auto-raised to ACCEPTED
        # (a WS with an unresolved P1 blocker) draws a flag-only P3 advisory
        # rather than a gating P2 — the same two-tier split as INVERSION.
        fixable, reason = _t_status_auto_fixable(graph, art_id)
        if fixable:
            severity = P2
            remedy = (
                "`dekspec audit linkage --fix` advances it to `ACCEPTED` as a "
                "pure metadata transition."
            )
        else:
            severity = P3
            remedy = f"Advisory only — not auto-fixable: {reason}. Resolve by hand."
        out.append(
            Finding(
                severity=severity,
                rule="T-STATUS-LAG",
                artifact_id=art_id,
                message=(
                    f"{art_id} is `{status}` (maturity band below ACCEPTED) but "
                    f"its decomposition is demonstrably complete — "
                    f"{'; '.join(signals)}. The artifact has lagged behind its "
                    f"realized work; {remedy}"
                ),
                fix_kind="mechanical" if fixable else "semantic",
            )
        )
    return out


# --------------------------------------------------------------------------- #
# T-STATUS-* bounded auto-fix — propose + apply the sub-ACCEPTED transitions
# --------------------------------------------------------------------------- #
#
# ADR-020 §Decision (bounded auto-fix): each T-STATUS finding's correct
# repair is a status transition. The `--fix` apply path auto-applies ONLY
# transitions whose target is at band <= ACCEPTED — pure metadata moves with
# no gated side effects. Transitions into band 4 (build states) or band 5
# (`LOCKED`) are flag-only; the auto-fix never writes them. The transition
# itself reuses the deterministic `artifact_ops.py transition` + update-index
# semantics: rewrite Status, bump Modified, append an Amendment Log row,
# reconcile the artifact's index row.

# The kind-prefix -> index-filename map. A status transition reconciles the
# artifact's row in this index alongside the artifact file itself.
_T_STATUS_INDEX_FILES: dict[str, str] = {
    "ADR-": "adr-index.md",
    "AE-": "architecture-elements-index.md",
    "IC-": "interface-contract-index.md",
    "WS-": "working-spec-index.md",
    "INT-": "intent-index.md",
    "MSN-": "mission-index.md",
}

# T-STATUS auto-fix metadata: every fix produced by `_propose_t_status_fixes`
# carries the proposed status in `Fix.after` and the current status in
# `Fix.before`; `Fix.section` is always "status". The amendment-log note is
# rebuilt at apply time from the rule code.
_T_STATUS_AUTOFIX_RULE = "T-STATUS-AUTOFIX"

# Section-style `## Status\n\nVALUE` and inline `**Status:** VALUE`.
_STATUS_VALUE_INLINE_RE = re.compile(r"^\*\*Status:\*\*[ \t]*(?P<val>\S.*?)[ \t]*$", re.MULTILINE)
_STATUS_SECTION_RE = re.compile(r"(?m)^#+[ \t]+Status[ \t]*$")
_MODIFIED_VALUE_INLINE_RE = re.compile(
    r"^\*\*Modified:\*\*[ \t]*(?P<val>\S.*?)[ \t]*$", re.MULTILINE
)
_MODIFIED_SECTION_HEAD_RE = re.compile(r"(?m)^#+[ \t]+Modified[ \t]*$")
_AMEND_SECTION_RE = re.compile(r"(?m)^#+[ \t]+Amendment Log[ \t]*$")
_AMEND_TABLE_HEADER_RE = re.compile(r"^\|[ \t]*Date[ \t]*\|.*\|[ \t]*$", re.MULTILINE)


def _t_status_correct_target(graph: SpecGraph, artifact_id: str) -> str | None:
    """The correct repair status for a T-STATUS finding on `artifact_id`.

    Every gating T-STATUS finding is repaired by raising the artifact to
    `ACCEPTED` — the `ACCEPTED`-capped invariant never demands more. Returns
    "ACCEPTED" for a cleanly auto-fixable artifact, or None when the artifact
    must not be auto-transitioned: already at band >= ACCEPTED, off-ramp /
    unknown, or not cleanly fixable (`_t_status_auto_fixable` — a Mission, or
    a WS with an unresolved P1 blocker). A None return keeps the finding a
    P3 advisory and out of the `--fix` sweep.
    """
    ir = graph.by_id(artifact_id)
    if ir is None:
        return None
    band = maturity_band(ir.get("status"))
    if band is None or band >= _STATUS_ACCEPTED_BAND:
        return None
    fixable, _ = _t_status_auto_fixable(graph, artifact_id)
    if not fixable:
        return None
    return "ACCEPTED"


def _propose_t_status_fixes(graph: SpecGraph) -> list[Fix]:
    """Compute the bounded T-STATUS auto-transition fixes.

    Runs `T-STATUS-INVERSION` + `T-STATUS-LAG`, and for every gating finding
    whose computed correct status is at band <= ACCEPTED emits one Fix that
    transitions the lagging artifact's Status. Both rules can flag the same
    artifact (e.g. AE-009 draws an INVERSION and a LAG finding); the proposer
    deduplicates — one transition per artifact.

    Transitions into band 4/5 are never proposed: `_t_status_correct_target`
    caps every repair at `ACCEPTED`, and Mission providers (no `ACCEPTED`
    status) return None. Those remain the P3 advisory report only.

    Each Fix carries `section="status"`, `before=<current status>`,
    `after=<proposed status>`; the multi-edit transition (Status + Modified
    + Amendment Log + index row) is performed by `_apply_t_status_fix`.
    """
    findings = _t_status_inversion(graph) + _t_status_lag(graph)
    fixes: list[Fix] = []
    seen: set[str] = set()
    for finding in findings:
        art_id = finding.artifact_id
        if art_id in seen:
            continue
        target = _t_status_correct_target(graph, art_id)
        if target is None:
            continue  # flag-only — Mission, or already settled
        ir = graph.by_id(art_id)
        if ir is None:
            continue
        path_str = (ir.get("source") or {}).get("path", "")
        if not path_str or not Path(path_str).exists():
            continue
        current = (ir.get("status") or "").strip().strip("`*_").upper()
        if not current:
            continue
        seen.add(art_id)
        fixes.append(
            Fix(
                rule=_T_STATUS_AUTOFIX_RULE,
                artifact_id=art_id,
                file_path=path_str,
                section="status",
                added_ids=[],
                before=current,
                after=target,
                line_number=0,
            )
        )
    return fixes


def _rewrite_status_value(text: str, new_status: str) -> str | None:
    """Surgically rewrite the Status value, preserving the header convention.

    Handles inline (`**Status:** VALUE`) and section (`## Status\\n\\nVALUE`)
    styles. Returns the rewritten text, or None when no Status field is found.
    """
    inline = _STATUS_VALUE_INLINE_RE.search(text)
    if inline is not None:
        return text[: inline.start("val")] + new_status + text[inline.end("val") :]
    sec = _STATUS_SECTION_RE.search(text)
    if sec is None:
        return None
    rest = text[sec.end() :]
    offset = sec.end()
    for line in rest.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("#"):
            return None  # ran into the next section with no value line
        if stripped:
            start = offset + (len(line) - len(line.lstrip()))
            end = start + len(stripped)
            return text[:start] + new_status + text[end:]
        offset += len(line)
    return None


def _rewrite_modified_value(text: str, today: str) -> str:
    """Bump the Modified value to `today`. No-op when there is no Modified."""
    inline = _MODIFIED_VALUE_INLINE_RE.search(text)
    if inline is not None:
        return text[: inline.start("val")] + today + text[inline.end("val") :]
    sec = _MODIFIED_SECTION_HEAD_RE.search(text)
    if sec is None:
        return text
    rest = text[sec.end() :]
    offset = sec.end()
    for line in rest.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("#"):
            return text
        if stripped:
            start = offset + (len(line) - len(line.lstrip()))
            end = start + len(stripped)
            return text[:start] + today + text[end:]
        offset += len(line)
    return text


def _append_amendment_row(text: str, today: str, note: str, author: str) -> str:
    """Append one row to the Amendment Log table. No-op when absent."""
    sec = _AMEND_SECTION_RE.search(text)
    if sec is None:
        return text
    header = _AMEND_TABLE_HEADER_RE.search(text, sec.end())
    if header is None:
        return text
    # Walk past the contiguous block of table rows (header, separator, any
    # data rows) to the end of the last row — the new row lands below it.
    idx = header.end()
    pos = header.end()
    while pos < len(text):
        if text[pos] == "\n":
            pos += 1
        if pos >= len(text):
            break
        line_end = text.find("\n", pos)
        if line_end == -1:
            line_end = len(text)
        if not text[pos:line_end].lstrip().startswith("|"):
            break
        idx = line_end
        pos = line_end
    row = f"\n| {today} | Substantive | {note} | {author} |"
    return text[:idx] + row + text[idx:]


def _reconcile_index_row(index_path: Path, artifact_id: str, new_status: str) -> bool:
    """Rewrite `artifact_id`'s Status cell in a markdown index. Returns True
    when a row was found and updated; False when the index has no such row
    (a missing row is L15-INDEX-FILE-COHERENCE's concern, not the fixer's).
    """
    if not index_path.exists():
        return False
    text = index_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    id_re = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(artifact_id)}(?![0-9])")
    new_up = new_status.upper()
    # Recognized status tokens in an index Status cell — kept in sync with
    # artifact_ops.update_index (INT-070 IU-1 added OVERSIZED). `TODO` is
    # retained because it remains a valid status on non-Intent artifacts
    # (AE/WS/IB/MSN); `TESTFAIL` was retired 2026-05-25 (E3 audit) and is
    # no longer recognised on any kind.
    known = {
        "TODO",
        "DRAFT",
        "PROPOSED",
        "ACCEPTED",
        "LOCKED",
        "DEPRECATED",
        "SUPERSEDED",
        "COMPLETE",
        "ACTIVE",
        "KILLED",
        "MERGED",
        "QUEUED",
        "COMPLETED",
        "IMPLEMENTING",
        "TESTPASS",
        "OVERSIZED",
        "COMPLETING",
    }
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|") or not id_re.search(line):
            continue
        cells = line.rstrip("\n").split("|")
        for j in range(1, len(cells)):
            token = cells[j].strip().strip("`*_").upper()
            if token in known:
                cells[j] = f" {new_up} "
                newline = "\n" if line.endswith("\n") else ""
                lines[i] = "|".join(cells) + newline
                index_path.write_text("".join(lines), encoding="utf-8")
                return True
        return False
    return False


def _apply_t_status_fix(
    fix: Fix, graph: SpecGraph, dry_run: bool, today: str | None = None
) -> dict[str, Any]:
    """Apply one T-STATUS auto-transition: Status + Modified + Amendment Log
    on the artifact file, plus the index-row reconcile.

    Returns a per-fix result dict. On `dry_run` no file is written.
    """
    today = today or _date.today().isoformat()
    art_path = Path(fix.file_path)
    result: dict[str, Any] = {
        "artifact_id": fix.artifact_id,
        "from": fix.before,
        "to": fix.after,
        "applied": False,
        "index_reconciled": False,
        "skipped_reason": None,
    }
    if not art_path.exists():
        result["skipped_reason"] = "artifact file not found"
        return result
    text = art_path.read_text(encoding="utf-8")
    rewritten = _rewrite_status_value(text, fix.after)
    if rewritten is None:
        result["skipped_reason"] = "no Status field found"
        return result
    note = (
        f"Status {fix.before} to {fix.after} — auto-transition by "
        f"`dekspec audit linkage --fix` (T-STATUS status-maturity coherence, "
        f"ADR-020)."
    )
    rewritten = _rewrite_modified_value(rewritten, today)
    rewritten = _append_amendment_row(rewritten, today, note, "dekspec-audit-fix")
    result["applied"] = True
    if not dry_run:
        art_path.write_text(rewritten, encoding="utf-8")

    # Reconcile the artifact's index row.
    dekspec_dir = graph.dekspec_dir
    if dekspec_dir is not None:
        for prefix, index_name in _T_STATUS_INDEX_FILES.items():
            if fix.artifact_id.startswith(prefix):
                index_path = dekspec_dir / index_name
                if dry_run:
                    # Dry-run: report whether a reconcilable row exists.
                    result["index_reconciled"] = index_path.exists() and bool(
                        re.search(
                            rf"(?<![A-Za-z0-9-]){re.escape(fix.artifact_id)}(?![0-9])",
                            index_path.read_text(encoding="utf-8"),
                        )
                    )
                else:
                    result["index_reconciled"] = _reconcile_index_row(
                        index_path, fix.artifact_id, fix.after
                    )
                break
    return result


def apply_status_fixes(
    repo_root: str | Path,
    dekspec_root: str = "dekspec",
    dry_run: bool = True,
    today: str | None = None,
) -> dict[str, Any]:
    """Compute and apply the bounded T-STATUS auto-transition sweep.

    Loads the graph, proposes the sub-`ACCEPTED` transitions, and applies
    each (Status + Modified + Amendment Log + index row). `dry_run=True`
    (default) returns the proposal without writing.

    Returns a summary dict: `proposed`, `applied`, `skipped`, `details`
    (per-fix result list), `dry_run`.
    """
    graph = SpecGraph.load(repo_root, dekspec_root=dekspec_root)
    fixes = _propose_t_status_fixes(graph)
    relocations = _propose_ib_relocations(graph)
    details: list[dict[str, Any]] = []
    applied = 0
    skipped = 0
    for fix in fixes:
        res = _apply_t_status_fix(fix, graph, dry_run=dry_run, today=today)
        details.append(res)
        if res["applied"]:
            applied += 1
        else:
            skipped += 1
    for relocation in relocations:
        res = _apply_ib_relocation(graph, relocation, dry_run=dry_run)
        details.append(res)
        if res["applied"]:
            applied += 1
        else:
            skipped += 1
    return {
        "proposed": len(fixes) + len(relocations),
        "applied": applied,
        "skipped": skipped,
        "details": details,
        "dry_run": dry_run,
    }


def is_lock_ready(graph: SpecGraph, artifact_id: str) -> tuple[bool, str]:
    """Check if an ACCEPTED artifact is ready to transition to LOCKED.

    ADR-020 per-kind lock-readiness criteria:
      - IC: all party/consumer AEs are >= ACCEPTED and contract is implemented
        (no active L4 linkage findings) and party/consumer AEs list is non-empty.
      - WS: all realizing Intents are LOCKED and no blocking (P1/P2) open issues.
      - ADR: status is ACCEPTED and no unlock is in flight (since it is ACCEPTED).
      - AE: status is ACCEPTED and all child WSes and ICs are LOCKED.
    """
    ir = graph.by_id(artifact_id)
    if not ir:
        return False, "artifact not found in graph"

    status = ir.get("status")
    band = maturity_band(status)
    if band != 3:  # 3 is ACCEPTED / ACTIVE
        return (
            False,
            f"status is {status} (maturity band {band}), but lock-readiness requires ACCEPTED (band 3)",
        )

    if artifact_id.startswith("IC-"):
        ae_ids = graph.aes_of_ic(artifact_id)
        if not ae_ids:
            return False, "IC has no party/consumer AEs populated"
        for ae_id in ae_ids:
            ae = graph.by_id(ae_id)
            if not ae:
                return False, f"referenced AE {ae_id} does not exist in graph"
            ae_band = maturity_band(ae.get("status"))
            if ae_band is None or ae_band < _STATUS_ACCEPTED_BAND:
                return False, f"referenced AE {ae_id} is below ACCEPTED (band {ae_band})"

        ic_findings = [f for f in _l4_ic_ae_links(graph) if f.artifact_id == artifact_id]
        if ic_findings:
            return (
                False,
                f"IC has active L4 linkage findings: {', '.join(f.rule for f in ic_findings)}",
            )

        return True, "IC has all party/consumer AEs >= ACCEPTED and no active L4 findings"

    elif artifact_id.startswith("WS-"):
        for issue in ir.get("open_issues") or []:
            if issue.get("severity") in ("P1", "P2"):
                return (
                    False,
                    f"WS has unresolved blocking open issue: {issue.get('id')} ({issue.get('severity')})",
                )

        realizing_intents = set()
        for ib in graph.ibs():
            spec_id = (ib.get("spec") or {}).get("id")
            if spec_id == artifact_id:
                intent_id = (ib.get("intent") or {}).get("id")
                if intent_id:
                    realizing_intents.add(intent_id)

        for intent_id in sorted(realizing_intents):
            intent = graph.by_id(intent_id)
            if not intent:
                return False, f"realizing Intent {intent_id} not found in graph"
            intent_band = maturity_band(intent.get("status"))
            if intent_band is None or intent_band < 5:
                return (
                    False,
                    f"realizing Intent {intent_id} is not LOCKED (status is {intent.get('status')})",
                )

        return True, "WS has no blocking open issues and all realizing Intents are LOCKED"

    elif artifact_id.startswith("ADR-"):
        return True, "ADR status is ACCEPTED and no unlock is in flight"

    elif artifact_id.startswith("AE-"):
        child_wss = [ws for ws in graph.wses() if artifact_id in graph.aes_of_ws(ws["id"])]
        child_ics = [ic for ic in graph.ics() if artifact_id in graph.aes_of_ic(ic["id"])]

        for ws in child_wss:
            ws_band = maturity_band(ws.get("status"))
            if ws_band is None or ws_band < 5:
                return (
                    False,
                    f"child Working Spec {ws['id']} is not LOCKED (status is {ws.get('status')})",
                )
        for ic in child_ics:
            ic_band = maturity_band(ic.get("status"))
            if ic_band is None or ic_band < 5:
                return (
                    False,
                    f"child Interface Contract {ic['id']} is not LOCKED (status is {ic.get('status')})",
                )

        return (
            True,
            "AE status is ACCEPTED and all child Working Specs and Interface Contracts are LOCKED",
        )

    else:
        return False, f"lock-readiness check not supported for kind {artifact_id}"


def _t_status_lock_ready(graph: SpecGraph) -> list[Finding]:
    """T-STATUS-LOCK-READY — advisory audit rule checking which ACCEPTED artifacts can be locked.

    Checks all ACCEPTED artifacts (AE, ADR, WS, IC) in the graph and yields P3
    advisory findings for each lock-ready artifact.
    """
    out: list[Finding] = []

    for art in sorted(graph.all(), key=lambda x: x.get("id", "")):
        art_id = art.get("id", "")
        if not art_id:
            continue

        if not (
            art_id.startswith("AE-")
            or art_id.startswith("ADR-")
            or art_id.startswith("WS-")
            or art_id.startswith("IC-")
        ):
            continue

        status = art.get("status")
        if status != "ACCEPTED":
            continue

        ready, reason = is_lock_ready(graph, art_id)
        if ready:
            out.append(
                Finding(
                    severity=P3,
                    rule="T-STATUS-LOCK-READY",
                    artifact_id=art_id,
                    message=(
                        f"{art_id} is `ACCEPTED` and is ready to be locked. Reason: {reason}."
                    ),
                    fix_kind="mechanical",
                )
            )

    return out


def _get_ib_folders_mapping(graph: SpecGraph) -> dict[str, list[int]]:
    """Retrieve the ib_folders mapping from dekspec config, or return the default mapping."""
    from .. import dekspec_config

    if graph.repo_root and dekspec_config.config_exists(graph.repo_root):
        try:
            config = dekspec_config.load_config(graph.repo_root)
            mapping = config.get("ib_folders")
            if mapping and isinstance(mapping, dict):
                return {k: list(v) for k, v in mapping.items() if isinstance(v, (list, tuple))}
        except Exception:
            pass
    return {
        "queued": [0, 1, 2],  # TODO, DRAFT, OVERSIZED, PROPOSED
        "active": [3, 4],  # ACCEPTED, IMPLEMENTING, TESTPASS, MERGED
        "completed": [5],  # LOCKED, COMPLETE
    }


def _t_status_ib_folder(graph: SpecGraph) -> list[Finding]:
    """T-STATUS-IB-FOLDER — IB folder-coherence check (ADR-020).

    Verifies that each Implementation Brief (IB) resides in the filesystem
    folder mapped to its current maturity band.
    """
    out: list[Finding] = []
    dekspec_dir = graph.dekspec_dir
    if not dekspec_dir:
        return out

    mapping = _get_ib_folders_mapping(graph)

    for ib in graph.ibs():
        ib_id = ib.get("id")
        if not ib_id:
            continue
        status = ib.get("status")
        band = maturity_band(status)
        if band is None:
            continue

        art_path_str = (ib.get("source") or {}).get("path", "")
        if not art_path_str:
            continue
        art_path = Path(art_path_str)

        ib_dir = dekspec_dir / "impl-briefs"
        try:
            rel_path = art_path.relative_to(ib_dir)
        except ValueError:
            continue

        if len(rel_path.parts) > 1:
            folder = rel_path.parts[0]
        else:
            folder = ""

        if folder in mapping:
            allowed_bands = mapping[folder]
            if band not in allowed_bands:
                # Find the correct folder(s) for the current band
                correct_folders = [f for f, bands in mapping.items() if band in bands]
                correct_folder = correct_folders[0] if correct_folders else "<unknown>"
                out.append(
                    Finding(
                        severity=P2,
                        rule="T-STATUS-IB-FOLDER",
                        artifact_id=ib_id,
                        message=(
                            f"IB {ib_id} is `{status}` (maturity band {band}) but sits in "
                            f"folder `{folder}`. Allowed bands for `{folder}`: {allowed_bands}. "
                            f"Should be in folder `{correct_folder}`."
                        ),
                        fix_kind="mechanical",
                        file_path=art_path_str,
                    )
                )
    return out


def _get_ib_relocation(
    graph: SpecGraph, ib_id: str, file_path: str | None = None
) -> tuple[Path, Path, str, str] | None:
    ib = None
    if file_path:
        target_path = Path(file_path).resolve()
        for candidate in graph.ibs():
            candidate_path_str = (candidate.get("source") or {}).get("path", "")
            if candidate_path_str and Path(candidate_path_str).resolve() == target_path:
                ib = candidate
                break
    if not ib:
        ib = graph.by_id(ib_id)
    if not ib:
        return None
    art_path_str = (ib.get("source") or {}).get("path", "")
    if not art_path_str:
        return None
    art_path = Path(art_path_str)

    status = ib.get("status")
    band = maturity_band(status)
    if band is None:
        return None

    dekspec_dir = graph.dekspec_dir
    if not dekspec_dir:
        return None

    mapping = _get_ib_folders_mapping(graph)
    correct_folders = [f for f, bands in mapping.items() if band in bands]
    if not correct_folders:
        return None
    correct_folder = correct_folders[0]

    ib_dir = dekspec_dir / "impl-briefs"
    try:
        rel_path = art_path.relative_to(ib_dir)
    except ValueError:
        return None

    if len(rel_path.parts) > 1:
        folder = rel_path.parts[0]
    else:
        folder = ""

    if folder not in mapping:
        return None

    if folder == correct_folder:
        return None

    old_rel = str(rel_path)
    new_rel_path = Path(correct_folder) / art_path.name if correct_folder else Path(art_path.name)
    new_rel = str(new_rel_path)

    dest_path = ib_dir / new_rel_path

    return art_path, dest_path, old_rel, new_rel


def _propose_ib_relocations(graph: SpecGraph) -> list[dict[str, Any]]:
    # Run _t_status_ib_folder to find all mismatched folder findings
    findings = _t_status_ib_folder(graph)
    relocations = []
    seen = set()
    for finding in findings:
        file_path = finding.file_path or finding.artifact_id
        if file_path in seen:
            continue
        seen.add(file_path)
        rel_info = _get_ib_relocation(graph, finding.artifact_id, finding.file_path)
        if rel_info:
            art_path, dest_path, old_rel, new_rel = rel_info
            if art_path != dest_path:
                relocations.append(
                    {
                        "artifact_id": finding.artifact_id,
                        "src_path": art_path,
                        "dest_path": dest_path,
                        "from": old_rel,
                        "to": new_rel,
                    }
                )
    return relocations


def _apply_ib_relocation(
    graph: SpecGraph, relocation: dict[str, Any], dry_run: bool
) -> dict[str, Any]:
    import subprocess

    result = {
        "artifact_id": relocation["artifact_id"],
        "from": relocation["from"],
        "to": relocation["to"],
        "applied": False,
        "index_reconciled": False,
        "skipped_reason": None,
    }
    src_path = relocation["src_path"]
    dest_path = relocation["dest_path"]

    if not src_path.exists():
        result["skipped_reason"] = "source file not found"
        return result

    if not dry_run:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if graph.repo_root:
            try:
                subprocess.run(
                    ["git", "mv", str(src_path), str(dest_path)],
                    cwd=str(graph.repo_root),
                    capture_output=True,
                    text=True,
                    check=True,
                )
                result["applied"] = True
            except subprocess.CalledProcessError as e:
                try:
                    import os

                    os.rename(src_path, dest_path)
                    result["applied"] = True
                except Exception as ex:
                    result["skipped_reason"] = (
                        f"git mv failed: {e.stderr.strip()}; rename fallback failed: {ex}"
                    )
            except Exception as e:
                result["skipped_reason"] = f"subprocess error: {e}"
        else:
            try:
                import os

                os.rename(src_path, dest_path)
                result["applied"] = True
            except Exception as e:
                result["skipped_reason"] = f"rename failed: {e}"
    else:
        # Dry run: just report what would have been applied
        result["applied"] = True

    return result


# --------------------------------------------------------------------------- #
# T-SKILL-* — skill catalog hygiene rules (Phase B of
# INT-provisional-skill-flag-normalization). Canonical defaults table at
# docs/dekspec-skill-flag-defaults.md. All 3 rules are P2 mechanical.
# --------------------------------------------------------------------------- #

# Canonical class defaults per docs/dekspec-skill-flag-defaults.md.
# Mirrored here so the audit rule does not depend on the docs at runtime.
_SKILL_CLASS_DEFAULTS: dict[str, dict[str, str]] = {
    # authoring (shallow / lite)
    "write-adr":          {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-ae":           {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-constitution": {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-ggc":          {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-intent":       {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-sp":           {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-sv":           {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    # authoring (deep / full)
    "write-ws":           {"mode": "full", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-ic":           {"mode": "full", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-ibs":          {"mode": "full", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    "write-mission":      {"mode": "full", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Grep Glob Bash Agent"},
    # dispatch (high-risk; disable-model-invocation: true)
    "exec-coding-session":     {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "true",  "allowed-tools": "Read Bash Agent"},
    "orchestrate-deepening":   {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "true",  "allowed-tools": "Read Bash Agent"},
    "factory-dispatch-intent":  {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "true",  "allowed-tools": "Read Bash Agent"},
    "factory-listen":           {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "true",  "allowed-tools": "Read Bash Agent"},
    # diagnostic (read-mostly CLI-wrap probes; slash-invocation only, no sub-agent spawn)
    "factory":                  {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "true",  "allowed-tools": "Read Bash"},
    # recovery
    "archeology":              {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Grep Glob Bash"},
    "brownfield-ingest":       {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Grep Glob Bash"},
    # architecture (read-mostly source-architecture analysis; spawn Explore/Design-It-Twice sub-agents, propose-only)
    "deepen-codebase-architecture": {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Grep Glob Bash Agent"},
    "audit-codebase": {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Grep Glob Bash Agent"},
    # audit class row retired v0.98.0 (doctor-fidelity inlined into /doctor Stage 2)
    # review (read-only adversarial reviewers; reasoning_effort max, spawn lens sub-agents, no Write/Edit)
    "review-ib":          {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Grep Glob Bash Agent"},
    "review-pr":          {"mode": "lite", "reasoning_effort": "max",  "disable-model-invocation": "false", "allowed-tools": "Read Grep Glob Bash Agent"},
    # utility
    "write-code-beads":        {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "write-issue-beads":       {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "orchestrate-intent": {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "spec-intent":        {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "land-intent":        {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "using-dekspec":      {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "setup-dekspec":      {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "interview-me":       {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "diagnose":           {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "prototype":          {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "write-evals":        {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "write-tests":        {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
    "rotation-handoff":   {"mode": "lite", "reasoning_effort": "high", "disable-model-invocation": "false", "allowed-tools": "Read Write Edit Bash"},
}

# Default model across all skill classes (CLAUDE.md §Agent-model-policy).
_SKILL_MODEL_DEFAULT = "claude-opus-4-7"

# Required canonical frontmatter fields on every SKILL.md.
_SKILL_REQUIRED_FIELDS = (
    "name",
    "description",
    "mode",
    "model",
    "reasoning_effort",
    "disable-model-invocation",
    "allowed-tools",
    "argument-hint",
)


def _read_skill_files(graph: SpecGraph) -> list[Path]:
    """Return the list of canonical SKILL.md paths under
    `plugins/dekspec/skills/<skill>/SKILL.md`. Empty if the directory
    doesn't exist (consumer repo without plugin source).
    """
    skills_dir = graph.repo_root / "plugins" / "dekspec" / "skills"
    if not skills_dir.is_dir():
        return []
    out = []
    for p in sorted(skills_dir.iterdir()):
        if not p.is_dir() or p.name.startswith("_") or p.name.startswith("."):
            continue
        md = p / "SKILL.md"
        if md.is_file():
            out.append(md)
    return out


def _parse_skill_frontmatter(md: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Parse `key: value` lines out of the SKILL.md YAML frontmatter.

    Returns `(values, override_reasons)` where `values[field]` is the
    rightmost value seen for that field and `override_reasons[field]`
    is the `# override-reason: <text>` comment immediately preceding
    that field, if any (and empty otherwise).
    """
    try:
        content = md.read_text(encoding="utf-8")
    except OSError:
        return ({}, {})
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return ({}, {})
    fm = m.group(1)
    values: dict[str, str] = {}
    overrides: dict[str, str] = {}
    last_comment: str | None = None
    for line in fm.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# override-reason:"):
            last_comment = stripped[len("# override-reason:") :].strip()
            continue
        if stripped.startswith("#") or not stripped:
            last_comment = None
            continue
        kv = re.match(r"^([A-Za-z_][A-Za-z_0-9\-]*)\s*:\s*(.*)$", stripped)
        if kv:
            key = kv.group(1)
            val = kv.group(2).strip()
            values[key] = val
            if last_comment is not None:
                overrides[key] = last_comment
            last_comment = None
        else:
            last_comment = None
    return values, overrides


def _t_skill_frontmatter_normal(graph: SpecGraph) -> list[Finding]:
    """T-SKILL-FRONTMATTER-NORMAL (P2 mechanical) — every SKILL.md under
    `plugins/dekspec/skills/<skill>/SKILL.md` carries the canonical
    frontmatter field set with values matching the class default (per
    docs/dekspec-skill-flag-defaults.md) OR an explicit
    `# override-reason: <text>` comment immediately above the
    overridden line.

    Fires P2 when (a) a required field is missing, (b) a value does
    not match the class default and no override-reason comment is
    present, or (c) the skill name is unknown to the canonical
    defaults table.
    """
    findings: list[Finding] = []
    for md in _read_skill_files(graph):
        skill = md.parent.name
        values, overrides = _parse_skill_frontmatter(md)
        rel = str(md.relative_to(graph.repo_root))

        # 1. Every required field must be present.
        for field in _SKILL_REQUIRED_FIELDS:
            if field not in values:
                findings.append(
                    Finding(
                        severity="P2",
                        rule="T-SKILL-FRONTMATTER-NORMAL",
                        artifact_id=f"skill:{skill}",
                        message=(
                            f"SKILL.md frontmatter is missing required field "
                            f"`{field}`. Per docs/dekspec-skill-flag-defaults.md "
                            f"every SKILL.md must declare the canonical field set."
                        ),
                        fix_kind="mechanical",
                        file_path=rel,
                    )
                )

        # 2. Skill must be in the canonical defaults table.
        if skill not in _SKILL_CLASS_DEFAULTS:
            findings.append(
                Finding(
                    severity="P2",
                    rule="T-SKILL-FRONTMATTER-NORMAL",
                    artifact_id=f"skill:{skill}",
                    message=(
                        f"Skill `{skill}` is not registered in the canonical "
                        f"defaults table (docs/dekspec-skill-flag-defaults.md). "
                        f"Add a row to the table and to _SKILL_CLASS_DEFAULTS "
                        f"in tooling/dekspec/fidelity_audit/linkage.py."
                    ),
                    fix_kind="mechanical",
                    file_path=rel,
                )
            )
            continue

        # 3. Values must match the class default OR carry an override-reason.
        defaults = _SKILL_CLASS_DEFAULTS[skill]
        # `model` default is global, not class-keyed.
        expected = dict(defaults)
        expected["model"] = _SKILL_MODEL_DEFAULT

        for field, want in expected.items():
            got = values.get(field)
            if got is None:
                continue  # already flagged above as missing
            if got == want:
                continue
            if field in overrides:
                continue  # explicit override accepted
            findings.append(
                Finding(
                    severity="P2",
                    rule="T-SKILL-FRONTMATTER-NORMAL",
                    artifact_id=f"skill:{skill}",
                    message=(
                        f"`{field}: {got}` does not match the canonical "
                        f"default for class `{skill}` (`{field}: {want}`). "
                        f"Either align to the default or add an inline "
                        f"`# override-reason: <text>` comment immediately "
                        f"above the field. See "
                        f"docs/dekspec-skill-flag-defaults.md."
                    ),
                    fix_kind="mechanical",
                    file_path=rel,
                )
            )
    return findings


def _t_skill_help_mode_present(graph: SpecGraph) -> list[Finding]:
    """T-SKILL-HELP-MODE-PRESENT (P2 mechanical) — every SKILL.md
    declares a `## Help Mode` section that cites
    `_lib/help_mode_template.md` and supplies a YAML manifest with
    the canonical keys (`skill_name`, `one_line`, `modes`,
    `examples`).
    """
    findings: list[Finding] = []
    for md in _read_skill_files(graph):
        skill = md.parent.name
        rel = str(md.relative_to(graph.repo_root))
        try:
            body = md.read_text(encoding="utf-8")
        except OSError:
            continue

        if not re.search(r"^##\s+Help Mode\b", body, re.MULTILINE):
            findings.append(
                Finding(
                    severity="P2",
                    rule="T-SKILL-HELP-MODE-PRESENT",
                    artifact_id=f"skill:{skill}",
                    message=(
                        "SKILL.md is missing a `## Help Mode` section. "
                        "Every skill must render a help page when invoked "
                        "with `--help`. See "
                        "docs/dekspec-skill-flag-defaults.md."
                    ),
                    fix_kind="mechanical",
                    file_path=rel,
                )
            )
            continue

        if "_lib/help_mode_template.md" not in body:
            findings.append(
                Finding(
                    severity="P2",
                    rule="T-SKILL-HELP-MODE-PRESENT",
                    artifact_id=f"skill:{skill}",
                    message=(
                        "`## Help Mode` section does not cite "
                        "`_lib/help_mode_template.md`. The canonical "
                        "rendering contract must be referenced explicitly."
                    ),
                    fix_kind="mechanical",
                    file_path=rel,
                )
            )

        for key in ("skill_name", "one_line", "modes", "examples"):
            if not re.search(rf"^\s*{re.escape(key)}\s*:", body, re.MULTILINE):
                findings.append(
                    Finding(
                        severity="P2",
                        rule="T-SKILL-HELP-MODE-PRESENT",
                        artifact_id=f"skill:{skill}",
                        message=(
                            f"Help Mode YAML manifest is missing required "
                            f"key `{key}`. Required keys per the canonical "
                            f"manifest schema: skill_name, one_line, modes, "
                            f"examples."
                        ),
                        fix_kind="mechanical",
                        file_path=rel,
                    )
                )
    return findings


def _t_skill_arg_hint_complete(graph: SpecGraph) -> list[Finding]:
    """T-SKILL-ARG-HINT-COMPLETE (P2 mechanical) — every SKILL.md has
    an `argument-hint:` frontmatter field whose first bracketed entry
    is `[--help]` (per OI-G of
    INT-provisional-skill-flag-normalization).
    """
    findings: list[Finding] = []
    for md in _read_skill_files(graph):
        skill = md.parent.name
        rel = str(md.relative_to(graph.repo_root))
        values, _overrides = _parse_skill_frontmatter(md)
        hint = values.get("argument-hint")
        if hint is None:
            # T-SKILL-FRONTMATTER-NORMAL already flagged the missing
            # field; don't double-fire.
            continue
        if "--help" not in hint:
            findings.append(
                Finding(
                    severity="P2",
                    rule="T-SKILL-ARG-HINT-COMPLETE",
                    artifact_id=f"skill:{skill}",
                    message=(
                        "`argument-hint:` does not include `--help`. Every "
                        "skill must list `--help` in its argument-hint so "
                        "operators see the help affordance in CLI "
                        "autocomplete. Canonical convention: `[--help]` is "
                        "the first bracketed entry."
                    ),
                    fix_kind="mechanical",
                    file_path=rel,
                )
            )
    return findings


# --------------------------------------------------------------------------- #
# L-PROVISIONAL-* — provisional incubation visibility (audit-treatment).
# Both rules are P3 advisory — non-blocking; surface incubation state.
# Implements INT-provisional-audit-treatment per MSN-014.
# --------------------------------------------------------------------------- #

_PROVISIONAL_STALE_DAYS_DEFAULT = 30


def _l_provisional_tree_present(graph: SpecGraph) -> list[Finding]:
    """L-PROVISIONAL-TREE-PRESENT (P3 advisory) — fires once per
    non-empty incubation folder under `dekspec/provisional/<slug>/`.
    Reports the slug, the artifact count, and the age of the oldest
    file in days (mtime-based, not git-blame, to keep the check cheap).
    """
    findings: list[Finding] = []
    prov = graph.dekspec_dir / "provisional"
    if not prov.is_dir():
        return findings
    import time as _time

    now = _time.time()
    for slug_dir in sorted(prov.iterdir()):
        if not slug_dir.is_dir() or slug_dir.name.startswith(".") or slug_dir.name.startswith("_"):
            continue
        artifacts = [f for f in slug_dir.rglob("*.md") if f.is_file()]
        if not artifacts:
            continue
        oldest_mtime = min(f.stat().st_mtime for f in artifacts)
        age_days = int((now - oldest_mtime) / 86400)
        findings.append(
            Finding(
                severity="P3",
                rule="L-PROVISIONAL-TREE-PRESENT",
                artifact_id=f"provisional:{slug_dir.name}",
                message=(
                    f"Provisional incubation folder `{slug_dir.name}/` has "
                    f"{len(artifacts)} artifact(s); oldest is {age_days}d old. "
                    f"Consider promoting via the hand-promote workflow "
                    f"(see `docs/dekspec-operating-guide.md` §Provisional "
                    f"Promotion) or pruning the folder if the exploration "
                    f"has been abandoned."
                ),
                fix_kind="semantic",
                file_path=str(slug_dir.relative_to(graph.repo_root)),
            )
        )
    return findings


def _l_provisional_stale(
    graph: SpecGraph,
    days_threshold: int = _PROVISIONAL_STALE_DAYS_DEFAULT,
) -> list[Finding]:
    """L-PROVISIONAL-STALE (P3 advisory) — fires once per incubation
    folder whose oldest artifact mtime is older than the configured
    threshold (default 30 days). Reports the slug + age.
    """
    findings: list[Finding] = []
    prov = graph.dekspec_dir / "provisional"
    if not prov.is_dir():
        return findings
    import time as _time

    now = _time.time()
    cutoff = now - days_threshold * 86400
    for slug_dir in sorted(prov.iterdir()):
        if not slug_dir.is_dir() or slug_dir.name.startswith(".") or slug_dir.name.startswith("_"):
            continue
        artifacts = [f for f in slug_dir.rglob("*.md") if f.is_file()]
        if not artifacts:
            continue
        oldest_mtime = min(f.stat().st_mtime for f in artifacts)
        if oldest_mtime >= cutoff:
            continue
        age_days = int((now - oldest_mtime) / 86400)
        findings.append(
            Finding(
                severity="P3",
                rule="L-PROVISIONAL-STALE",
                artifact_id=f"provisional:{slug_dir.name}",
                message=(
                    f"Provisional incubation folder `{slug_dir.name}/` is "
                    f"stale — oldest artifact is {age_days}d old, threshold "
                    f"is {days_threshold}d. Either promote (via the "
                    f"hand-promote workflow — see "
                    f"`docs/dekspec-operating-guide.md` §Provisional "
                    f"Promotion) or prune the folder."
                ),
                fix_kind="semantic",
                file_path=str(slug_dir.relative_to(graph.repo_root)),
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# L-COW-SIBLING-COLLISION — copy-on-write sibling-collision detection.
# Implements the L-COW-SIBLING-COLLISION rule from
# INT-provisional-cow-spec-staging (MVP slice — write-time guard +
# accept gate deferred).
# --------------------------------------------------------------------------- #


def _l_cow_sibling_collision(graph: SpecGraph) -> list[Finding]:
    """L-COW-SIBLING-COLLISION (P2 semantic) — fires when 2+ provisional
    artifacts across different incubation folders declare
    `replaces: <CANONICAL-ID>` for the same canonical artifact.

    Both artifacts CAN coexist while their Intents are pre-ACCEPTED, but
    one engineer's ACCEPTED transition will promote first; the second
    will face a divergent canonical state. Surface the collision early
    so engineers coordinate before the second accept gate.
    """
    findings: list[Finding] = []
    prov = graph.dekspec_dir / "provisional"
    if not prov.is_dir():
        return findings

    # canonical_id -> list of (incubation-slug, provisional-filename)
    claims: dict[str, list[tuple[str, str]]] = {}
    from .. import promote  # lazy to avoid circular at module load

    for slug_dir in sorted(prov.iterdir()):
        if not slug_dir.is_dir() or slug_dir.name.startswith(".") or slug_dir.name.startswith("_"):
            continue
        for md in sorted(slug_dir.rglob("*.md")):
            target = promote.parse_replaces_id(md)
            if target is None:
                continue
            claims.setdefault(target, []).append((slug_dir.name, md.name))

    for canonical_id, claimants in claims.items():
        if len(claimants) < 2:
            continue
        slug_list = ", ".join(f"`{slug}` ({fname})" for slug, fname in claimants)
        findings.append(
            Finding(
                severity="P2",
                rule="L-COW-SIBLING-COLLISION",
                artifact_id=canonical_id,
                message=(
                    f"{len(claimants)} provisional artifacts declare "
                    f"`replaces: {canonical_id}`: {slug_list}. The first "
                    f"incubation to hand-promote wins; the second engineer "
                    f"will face a diverged canonical and must coordinate "
                    f"with the engineer who landed first."
                ),
                fix_kind="semantic",
                file_path="dekspec/provisional/",
            )
        )
    return findings


# --------------------------------------------------------------------------- #
# T-COW-CANONICAL-EDITED — direct-edit-bypass detection.
# Catches the case where a canonical artifact is modified vs origin/main
# while a pre-ACCEPTED Intent claims its path AND no provisional CoW
# sibling exists in dekspec/provisional/. Implements the second audit
# rule from INT-082 (cow-spec-staging). Optional second arg: the git
# command used to enumerate modified-vs-main files (test injection).
# --------------------------------------------------------------------------- #

_COW_PRE_ACCEPTED_STATUSES = frozenset({"DRAFT", "PROPOSED"})


def _resolve_claimed_paths(
    graph: SpecGraph, repo_root: Path
) -> dict[str, list[tuple[str, str]]]:
    """For each pre-ACCEPTED Intent, resolve its Components-affected
    globs against the working tree. Returns
    {canonical-path: [(INT-id, glob), ...]} so a single canonical file
    can be reverse-looked-up to every Intent that claims it.
    """
    import glob as _glob

    claims: dict[str, list[tuple[str, str]]] = {}
    for ir in graph.intents():
        if (ir.get("status") or "") not in _COW_PRE_ACCEPTED_STATUSES:
            continue
        intent_id = ir.get("id", "")
        components = ir.get("components_affected") or []
        for entry in components:
            if isinstance(entry, dict):
                pat = entry.get("glob") or entry.get("path") or ""
            else:
                pat = str(entry)
            if not pat:
                continue
            # Resolve glob against repo root.
            matches = _glob.glob(str(repo_root / pat), recursive=True)
            for m in matches:
                rel = str(Path(m).resolve().relative_to(repo_root.resolve()))
                claims.setdefault(rel, []).append((intent_id, pat))
    return claims


def _collect_provisional_cow_targets(repo_root: Path) -> set[str]:
    """Return the set of canonical IDs that have a provisional
    `replaces: <ID>` sibling under dekspec/provisional/."""
    from .. import promote
    prov = repo_root / "dekspec" / "provisional"
    if not prov.is_dir():
        return set()
    targets: set[str] = set()
    for slug_dir in prov.iterdir():
        if not slug_dir.is_dir() or slug_dir.name.startswith(".") or slug_dir.name.startswith("_"):
            continue
        for md in slug_dir.rglob("*.md"):
            tid = promote.parse_replaces_id(md)
            if tid:
                targets.add(tid)
    return targets


def _git_diff_names(repo_root: Path, ref: str = "main") -> list[str] | None:
    """Run `git diff --name-only <ref>` and return the list of modified
    paths (relative to repo_root). Returns None if git is unavailable
    or the ref doesn't exist (the rule then silently no-ops)."""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", ref],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return [line for line in r.stdout.split("\n") if line.strip()]


def _id_from_canonical_path(path: str) -> str | None:
    """Extract `<KIND>-NNN` from a canonical artifact filename. E.g.
    `dekspec/architecture-elements/AE-007-foo.md` -> `AE-007`."""
    m = re.search(r"/([A-Z]+-\d{3,})-[^/]+\.md$", path)
    return m.group(1) if m else None


def _t_cow_canonical_edited(graph: SpecGraph) -> list[Finding]:
    """T-COW-CANONICAL-EDITED (P2 mechanical) — fires when a canonical
    artifact is modified vs `main` AND a pre-ACCEPTED Intent claims
    its path AND there's no provisional CoW sibling (`replaces:
    <ID>`) under `dekspec/provisional/`. Surfaces the direct-edit
    bypass of the CoW guard.

    Silent when git is unavailable, when `main` doesn't exist, or
    when there are no pre-ACCEPTED Intents. Never blocks LOCK
    transitions because the rule is P2 not P1.
    """
    findings: list[Finding] = []
    diffs = _git_diff_names(graph.repo_root, "main")
    if not diffs:
        return findings
    claims = _resolve_claimed_paths(graph, graph.repo_root)
    if not claims:
        return findings
    cow_targets = _collect_provisional_cow_targets(graph.repo_root)

    seen: set[tuple[str, str]] = set()
    for diff_path in diffs:
        if diff_path not in claims:
            continue
        # If the modified canonical has a provisional CoW sibling
        # declaring `replaces: <ITS-ID>`, the guard was honored.
        canonical_id = _id_from_canonical_path(diff_path)
        if canonical_id and canonical_id in cow_targets:
            continue
        for intent_id, glob_pat in claims[diff_path]:
            key = (intent_id, diff_path)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    severity="P2",
                    rule="T-COW-CANONICAL-EDITED",
                    artifact_id=intent_id,
                    message=(
                        f"Canonical artifact `{diff_path}` is modified vs "
                        f"`main` and is claimed by pre-ACCEPTED Intent "
                        f"{intent_id} (matches glob `{glob_pat}`). Expected "
                        f"a provisional CoW sibling at "
                        f"`dekspec/provisional/<slug>/` with "
                        f"`replaces: {canonical_id or '<KIND-NNN>'}` "
                        f"frontmatter. The CoW guard appears bypassed; "
                        f"either CoW now via `dekspec repo new-provisional` "
                        f"+ `replaces:` stamp, or accept the Intent first "
                        f"if the canonical edit is intentional."
                    ),
                    fix_kind="mechanical",
                    file_path=diff_path,
                )
            )
    return findings


# --------------------------------------------------------------------------- #
# L16-INT-BEADS-BEFORE-ACCEPT (P2): Path A accept-gate — an Intent at status
# >= ACCEPTED with beads_before_accept=true must have at least one bead in the
# tracker.  (INT-105 / ds-xu6g)
# --------------------------------------------------------------------------- #

# Intent statuses at or beyond ACCEPTED — matching the same gate set used by
# L12 and elsewhere. An Intent at these statuses has walked past the accept
# gate, so the bead-traceability invariant applies.
_L16_GATE_STATUSES = frozenset(
    {
        "ACCEPTED",
        "IMPLEMENTING",
        "TESTPASS",
        "MERGED",
        "LOCKED",
    }
)


def _l16_int_beads_before_accept(graph: SpecGraph) -> list[Finding]:
    """L16-INT-BEADS-BEFORE-ACCEPT (P2): an Intent that opts into
    Path A (``beads_before_accept: true``) and has reached ACCEPTED or
    higher must have at least one bead in ``.beads/issues.jsonl`` whose
    ``external_ref`` begins with the Intent's file path.

    Exemptions (silent — no finding emitted):
      - ``beads_before_accept`` is ``false`` (grandfathered / pre-Path-A).
      - ``beads_before_accept`` is absent / ``None`` (not yet stamped).
      - Intent status is below the gate set (DRAFT / PROPOSED / SUPERSEDED).
      - ``graph.repo_root`` is ``None`` (in-memory test fixtures).
      - ``.beads/issues.jsonl`` does not exist (consumer repos without the
        bead tracker).

    Tracks ds-xu6g (IU-2 of INT-105).
    """
    if graph.repo_root is None:
        return []
    jsonl_path = Path(graph.repo_root) / ".beads" / "issues.jsonl"

    # Build a set of Intent file-path prefixes that have at least one bead.
    # A bead's ``external_ref`` looks like
    # ``dekspec/intents/INT-NNN-slug.md:IU-N`` — the prefix before the colon
    # (or the whole string when no colon is present) is the Intent's
    # repo-relative file path.
    bead_intent_paths: set[str] = set()
    if jsonl_path.exists():
        import json as _json
        with open(jsonl_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                ext_ref = rec.get("external_ref") or ""
                if "intents/" in ext_ref:
                    # Normalise: strip IU suffix (``...md:IU-3`` → ``...md``)
                    prefix = ext_ref.split(":")[0] if ":" in ext_ref else ext_ref
                    bead_intent_paths.add(prefix)

    out: list[Finding] = []
    for intent in graph.intents():
        # Only opt-in Intents (beads_before_accept explicitly true).
        if intent.get("beads_before_accept") is not True:
            continue
        status = (intent.get("status") or "").upper()
        if status not in _L16_GATE_STATUSES:
            continue
        # Derive the repo-relative path of this Intent's source file.
        source_path = (intent.get("source") or {}).get("path", "")
        if not source_path:
            continue
        import os as _os_l16
        rel_path = _os_l16.path.relpath(source_path, graph.repo_root)
        if rel_path not in bead_intent_paths:
            out.append(
                Finding(
                    severity="P2",
                    rule="L16-INT-BEADS-BEFORE-ACCEPT",
                    artifact_id=intent["id"],
                    message=(
                        f"Intent {intent['id']} (status={status}) has "
                        f"`beads_before_accept: true` but zero beads in "
                        f"`.beads/issues.jsonl` reference it "
                        f"(expected `external_ref` starting with "
                        f"`{rel_path}`). Path A methodology requires at "
                        f"least one bead to be filed before the Intent "
                        f"walks past ACCEPTED. Fix: file beads via "
                        f"`/write-code-beads`, or set `beads_before_accept: "
                        f"false` if this Intent is grandfathered."
                    ),
                    fix_kind="semantic",
                )
            )
    return out


# ---------------------------------------------------------------------------
# T-VERIFICATION-OUTCOME (INT-119 / ADR-029) — Outcome-test discipline.
# ---------------------------------------------------------------------------
_T_VERIFICATION_OUTCOME_GATE_STATUSES = frozenset(
    {"ACCEPTED", "IMPLEMENTING", "TESTPASS", "MERGED", "LOCKED"}
)


def _t_verification_outcome(graph: SpecGraph) -> list[Finding]:
    """T-VERIFICATION-OUTCOME (P2 advisory) — per ADR-029 every Intent
    at status ≥ ACCEPTED must declare a `outcome_verification` block
    (prose carrying the user-observable behavior proof under strong-TDD
    timing) OR be grandfathered.

    The rule walks `graph.intents()` and fires when:
      (a) Intent status is in the gate set (ACCEPTED..LOCKED), AND
      (b) `outcome_verification` is empty/absent, AND
      (c) `outcome_verification_grandfathered` is not true.

    Lazy-grandfather convention (INT-112 Slice A): pre-existing Intents
    authored before the field landed are stamped with the grandfather
    flag at parse time when the meta-line is absent; new Intents
    (post-INT-112-merge) default to grandfathered: false.

    Severity is P2 (advisory) — see ADR-029 §Consequences for why this
    is not gating (git-blame heuristics have edge cases at rebase /
    squash-merge / file move time).
    """
    out: list[Finding] = []
    for intent in graph.intents():
        status = (intent.get("status") or "").upper()
        if status not in _T_VERIFICATION_OUTCOME_GATE_STATUSES:
            continue
        if intent.get("outcome_verification_grandfathered") is True:
            continue
        outcome = intent.get("outcome_verification")
        if outcome and str(outcome).strip():
            continue
        out.append(
            Finding(
                rule="T-VERIFICATION-OUTCOME",
                artifact_id=intent.get("id", "<unknown>"),
                severity="P2",
                message=(
                    "Intent at status >= ACCEPTED lacks an "
                    "`outcome_verification` declaration and is not "
                    "grandfathered. Per ADR-029, ship a single, simple, "
                    "user-observable outcome test landed under strong-TDD "
                    "timing (red first, implementation makes it green)."
                ),
                fix_kind="semantic",
            )
        )
    return out


# ---------------------------------------------------------------------------
# Constitution §Class Lanes audit rules (INT-125 / ds-zhhk).
# ---------------------------------------------------------------------------
def _t_const_class_lane_coverage_unique(graph) -> list[Finding]:
    """T-CONST-CLASS-LANE-COVERAGE-UNIQUE (P2 advisory) — every
    (intent_type, risk_tier) tuple in the Constitution's class_lanes
    table must resolve to exactly one row. Duplicate tuples fire.
    """
    out: list[Finding] = []
    const = getattr(graph, "constitution", None)
    const_data = const() if callable(const) else const
    rows = (const_data or {}).get("class_lanes") or []
    seen: dict[tuple, int] = {}
    for row in rows:
        key = (row.get("intent_type"), row.get("risk_tier"))
        seen[key] = seen.get(key, 0) + 1
    for key, count in seen.items():
        if count > 1:
            out.append(Finding(
                rule="T-CONST-CLASS-LANE-COVERAGE-UNIQUE",
                artifact_id="CONSTITUTION",
                severity="P2",
                message=(
                    f"Tuple (intent_type={key[0]!r}, risk_tier={key[1]!r}) "
                    f"resolves to {count} rows; expected exactly 1."
                ),
                fix_kind="semantic",
            ))
    return out


def _t_const_class_lane_thresholds_well_formed(graph) -> list[Finding]:
    """T-CONST-CLASS-LANE-THRESHOLDS-WELL-FORMED (P2 advisory) —
    budget caps + attempt limits + promotion/demotion thresholds must
    be non-negative numeric values.
    """
    out: list[Finding] = []
    const = getattr(graph, "constitution", None)
    const_data = const() if callable(const) else const
    rows = (const_data or {}).get("class_lanes") or []
    numeric_fields = (
        "budget_cap_tokens",
        "budget_cap_dollars",
        "max_attempts_per_attempt",
        "max_attempts_per_bead",
        "promotion_threshold_clean_runs",
        "demotion_threshold_reverts",
    )
    for row in rows:
        for field in numeric_fields:
            val = row.get(field)
            if val is None:
                continue
            try:
                if float(val) < 0:
                    out.append(Finding(
                        rule="T-CONST-CLASS-LANE-THRESHOLDS-WELL-FORMED",
                        artifact_id="CONSTITUTION",
                        severity="P2",
                        message=(
                            f"Row (intent_type={row.get('intent_type')!r}, "
                            f"risk_tier={row.get('risk_tier')!r}) carries "
                            f"negative {field}={val!r}; thresholds must be "
                            "non-negative."
                        ),
                        fix_kind="semantic",
                    ))
            except (TypeError, ValueError):
                out.append(Finding(
                    rule="T-CONST-CLASS-LANE-THRESHOLDS-WELL-FORMED",
                    artifact_id="CONSTITUTION",
                    severity="P2",
                    message=(
                        f"Row (intent_type={row.get('intent_type')!r}) "
                        f"carries non-numeric {field}={val!r}."
                    ),
                    fix_kind="semantic",
                ))
    return out


def _l_const_class_lane_intent_exists(graph) -> list[Finding]:
    """L-CONST-CLASS-LANE-INTENT-EXISTS (P3 advisory) — every Intent's
    (type, risk_tier) tuple must match a row in the Constitution's
    class_lanes table. Unmatched tuples fire.
    """
    out: list[Finding] = []
    const = getattr(graph, "constitution", None)
    const_data = const() if callable(const) else const
    rows = (const_data or {}).get("class_lanes") or []
    if not rows:
        return out  # no lanes declared yet — silent
    keys = {(r.get("intent_type"), r.get("risk_tier")) for r in rows}
    for intent in graph.intents():
        tup = (intent.get("type"), intent.get("risk_tier"))
        if tup[1] is None:
            continue  # risk_tier optional; skip when absent
        if tup not in keys:
            out.append(Finding(
                rule="L-CONST-CLASS-LANE-INTENT-EXISTS",
                artifact_id=intent.get("id", "<unknown>"),
                severity="P3",
                message=(
                    f"Intent {intent.get('id')} declares "
                    f"(type={tup[0]!r}, risk_tier={tup[1]!r}) but no "
                    "matching Constitution class_lanes row exists."
                ),
                fix_kind="semantic",
            ))
    return out


# ---------------------------------------------------------------------------
# T-MISSION-CANONICAL-WITHOUT-CHILD (INT-128 / ds-provisional-promotion-guardrails)
# ---------------------------------------------------------------------------
_T_MISSION_CANONICAL_WINDOW_DAYS = 7


def _t_mission_canonical_without_child(graph) -> list[Finding]:
    """T-MISSION-CANONICAL-WITHOUT-CHILD (P3 advisory) — fires when a
    Mission file under canonical `dekspec/missions/` has been at status
    TODO for ≥7 days with zero child Intents declaring it via their
    `Mission:` field. Recommends moving to `dekspec/provisional/<slug>/`
    or killing if the work is YAGNI.

    Per INT-128 / survey at docs/workspace/cc_provisional-promotion-
    guardrails-survey.md, triggered by the MSN-011 eradication cost
    case (2026-05-30).
    """
    from datetime import datetime, timedelta, timezone
    out: list[Finding] = []
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=_T_MISSION_CANONICAL_WINDOW_DAYS
    )
    # Build set of MSN-NNN IDs that have at least one declaring child Intent.
    missions_with_children: set[str] = set()
    for intent in graph.intents():
        mission_ref = intent.get("mission")
        if isinstance(mission_ref, dict):
            mid = mission_ref.get("id")
        elif isinstance(mission_ref, str):
            mid = mission_ref
        else:
            mid = None
        if mid:
            missions_with_children.add(mid)

    for mission in graph.missions():
        # Provisional path → skip silently.
        path = (mission.get("source_path")
                or mission.get("path")
                or "")
        if "dekspec/provisional/" in str(path):
            continue
        # Non-TODO status → skip.
        status = str(mission.get("status") or "").upper()
        if status != "TODO":
            continue
        # Under the 7-day window → skip.
        created_raw = mission.get("created")
        if created_raw:
            try:
                created = datetime.fromisoformat(
                    str(created_raw).replace("Z", "+00:00")
                )
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created >= cutoff:
                    continue
            except ValueError:
                pass  # malformed date → fall through to fire
        # Has a declaring child Intent → skip.
        if mission.get("id") in missions_with_children:
            continue
        out.append(Finding(
            rule="T-MISSION-CANONICAL-WITHOUT-CHILD",
            artifact_id=mission.get("id", "<unknown>"),
            severity="P3",
            message=(
                f"Canonical Mission {mission.get('id')} has been status "
                f"TODO for ≥{_T_MISSION_CANONICAL_WINDOW_DAYS} days with "
                "zero child Intents. Recommend moving to "
                "dekspec/provisional/<slug>/ or killing if YAGNI."
            ),
            fix_kind="semantic",
        ))
    return out


# Statuses at which an Intent's authoring is settled; the Non-Goals
# forward-authoring discipline no longer applies (retroactively flagging
# already-shipped Intents would add advisory noise with no remediation
# value). INT-168 (δ / MSN-020).
_INT_NON_GOALS_TERMINAL_STATUSES = frozenset(
    {"LOCKED", "MERGED", "SUPERSEDED", "DEPRECATED"}
)

# Detects an authored `## Non-Goals` H2 section in an Intent body.
_INT_NON_GOALS_HEADING_RE = re.compile(r"^##\s+Non-Goals\b", re.MULTILINE)


def _t_intent_missing_non_goals(graph) -> list[Finding]:
    """T-INT-NON-GOALS-MISSING (P3 advisory) — fires when a NON-TERMINAL,
    Mission-less Intent's body lacks a `## Non-Goals` section.

    A standalone Intent (no parent Mission) has no Mission `Out-of-scope`
    contract to own its non-goals, so scope creep on a solo Intent goes
    uncaught. The optional `## Non-Goals` template section (INT-168) fills
    that gap; this rule nudges authors toward it.

    Silent when:
      - the Intent declares a parent Mission (``intent.get('mission')``
        truthy — its Out-of-scope owns non-goals, and duplicating them on
        the Intent is explicitly discouraged), or
      - the Intent already carries a populated ``## Non-Goals`` section, or
      - the Intent is at a terminal status (LOCKED / MERGED / SUPERSEDED /
        DEPRECATED) — Non-Goals is a forward-authoring discipline, not a
        retroactive lint on already-shipped work.

    P3-advisory + non-gating per ADR-018: it never blocks a build and stays
    out of the P0/P1/P2 doctor gate. INT-168 (δ / MSN-020), D5/D6.
    """
    out: list[Finding] = []
    for intent in graph.intents():
        # Mission-declaring Intents are exempt — the Mission owns non-goals.
        if intent.get("mission"):
            continue
        status = str(intent.get("status") or "").upper()
        if status in _INT_NON_GOALS_TERMINAL_STATUSES:
            continue
        source_path = (intent.get("source") or {}).get("path", "")
        if not source_path:
            continue
        try:
            body = Path(source_path).read_text(encoding="utf-8")
        except OSError:
            continue
        if _INT_NON_GOALS_HEADING_RE.search(body):
            continue
        out.append(Finding(
            rule="T-INT-NON-GOALS-MISSING",
            artifact_id=intent.get("id", "<unknown>"),
            severity="P3",
            message=(
                f"Mission-less Intent {intent.get('id')} has no `## Non-Goals` "
                "section. A standalone Intent has no parent Mission Out-of-scope "
                "to own its non-goals; add an optional `## Non-Goals` section to "
                "pin what this Intent will not do (or link a parent Mission)."
            ),
            fix_kind="semantic",
        ))
    return out


# Statuses at which a bug Intent's authoring is settled; the repro-gate
# forward-authoring discipline no longer applies (retroactively flagging
# already-shipped bug Intents — both self-spec bug Intents INT-023/INT-089 are
# LOCKED — would add advisory noise with no remediation value). INT-169
# (ε / MSN-020).
_BUG_REPRO_TERMINAL_STATUSES = frozenset(
    {"LOCKED", "MERGED", "SUPERSEDED", "DEPRECATED"}
)

# Statuses below the ACCEPTED gate: the deterministic repro is expected to be
# produced during the accept→decompose ramp, so a pre-ACCEPTED bug Intent is
# not yet obligated to carry one. INT-169 (ε / MSN-020).
_BUG_REPRO_PRE_ACCEPT_STATUSES = frozenset({"DRAFT", "PROPOSED"})

# Detects a populated `### bug — Reproduction` / `### bug — Non-Reproducible
# Waiver` H3 section: the heading (with or without backticks around `bug`)
# followed by at least one non-blank content line before the next H2/H3.
_BUG_REPRO_SECTION_RE = re.compile(
    r"^###\s+`?bug`?\s+—\s+Reproduction\b[^\n]*\n"
    r"(?:[ \t]*\n)*"          # optional blank lines
    r"(?=[ \t]*\S)"          # then a non-blank line …
    r"(?![ \t]*#{2,3}\s)",   # … that is not itself an H2/H3 heading
    re.MULTILINE,
)
_BUG_WAIVER_SECTION_RE = re.compile(
    r"^###\s+`?bug`?\s+—\s+Non-Reproducible\s+Waiver\b[^\n]*\n"
    r"(?:[ \t]*\n)*"
    r"(?=[ \t]*\S)"
    r"(?![ \t]*#{2,3}\s)",
    re.MULTILINE,
)


def _t_bug_missing_repro_gate(graph) -> list[Finding]:
    """T-BUG-REPRO-GATE (P3 advisory) — fires when a NON-TERMINAL,
    ``>= ACCEPTED`` ``type: bug`` Intent carries neither a populated
    ``### bug — Reproduction`` section nor a populated
    ``### bug — Non-Reproducible Waiver`` section.

    A bug fix that lands without a deterministic, agent-runnable repro signal
    (or an explicit waiver explaining why one could not be built) has nothing
    durable to gate the fix or to seed the red-first outcome test. The
    ``diagnose`` skill (INT-169) exists to produce that repro before the bug
    Intent is filled; this rule nudges authors toward one of the two valid
    end-states.

    Silent when:
      - the Intent is not a ``bug`` (``intent_type != 'bug'`` — feature /
        refactor / chore Intents have no Reproduction obligation), or
      - the Intent already carries a populated Reproduction section, or
      - the Intent already carries a populated Non-Reproducible Waiver
        section, or
      - the Intent is at a terminal status (LOCKED / MERGED / SUPERSEDED /
        DEPRECATED) — a forward-authoring discipline, not a retroactive lint
        on already-shipped bug Intents, or
      - the Intent is below the ACCEPTED gate (DRAFT / PROPOSED) — the repro
        is expected during the accept→decompose ramp.

    P3-advisory + non-gating per ADR-018: it never blocks a build and stays
    out of the P0/P1/P2 doctor gate. INT-169 (ε / MSN-020), D9/D11.
    """
    out: list[Finding] = []
    for intent in graph.intents():
        # Only bug Intents carry a Reproduction obligation.
        if str(intent.get("intent_type") or "").lower() != "bug":
            continue
        status = str(intent.get("status") or "").upper()
        # Terminal → settled; pre-ACCEPTED → not yet obligated.
        if status in _BUG_REPRO_TERMINAL_STATUSES:
            continue
        if status in _BUG_REPRO_PRE_ACCEPT_STATUSES:
            continue
        source_path = (intent.get("source") or {}).get("path", "")
        if not source_path:
            continue
        try:
            body = Path(source_path).read_text(encoding="utf-8")
        except OSError:
            continue
        if _BUG_REPRO_SECTION_RE.search(body):
            continue
        if _BUG_WAIVER_SECTION_RE.search(body):
            continue
        out.append(Finding(
            rule="T-BUG-REPRO-GATE",
            artifact_id=intent.get("id", "<unknown>"),
            severity="P3",
            message=(
                f"Bug Intent {intent.get('id')} is at status {status} but "
                "carries neither a populated `### bug — Reproduction` section "
                "nor a `### bug — Non-Reproducible Waiver` section. Run "
                "`/diagnose` to build a deterministic repro before the fix "
                "lands, or record a Non-Reproducible Waiver explaining why one "
                "could not be constructed."
            ),
            fix_kind="semantic",
        ))
    return out


# Statuses at which an IC's authoring is settled; the Options-Considered
# forward-authoring discipline no longer applies (retroactively flagging
# already-shipped LOCKED ICs would add advisory noise with no remediation
# value). INT-171 (η / MSN-020).
_IC_OPTIONS_TERMINAL_STATUSES = frozenset(
    {"LOCKED", "MERGED", "SUPERSEDED", "DEPRECATED"}
)

# High-blast-radius heuristic thresholds (pinned at INT-171 --decompose). An IC
# is high-blast-radius — and so obligated to record the design-twice comparison
# — when it binds at least this many consumer parties OR declares at least this
# many governing ADRs. Both are structured IR fields, so the heuristic is
# deterministic. A future audit profile may dial these via `parameters:`.
_IC_OPTIONS_MIN_CONSUMERS = 2
_IC_OPTIONS_MIN_GOVERNING_ADRS = 2

# Detects a populated `## Options Considered / Rejected Rationale` H2 section:
# the heading followed by at least one non-blank content line that is not
# itself an H2/H3 heading (an empty heading does not count as populated).
_IC_OPTIONS_SECTION_RE = re.compile(
    r"^##\s+Options\s+Considered\s*/\s*Rejected\s+Rationale\b[^\n]*\n"
    r"(?:[ \t]*\n)*"          # optional blank lines
    r"(?=[ \t]*\S)"          # then a non-blank line …
    r"(?![ \t]*#{2,3}\s)",   # … that is not itself an H2/H3 heading
    re.MULTILINE,
)


def _ic_is_high_blast_radius(ic) -> bool:
    """An IC is high-blast-radius when it binds ``>= _IC_OPTIONS_MIN_CONSUMERS``
    consumer parties OR declares ``>= _IC_OPTIONS_MIN_GOVERNING_ADRS`` governing
    ADRs. INT-171 (η / MSN-020) pinned heuristic.
    """
    parties = ic.get("parties") or []
    consumer_count = sum(
        1
        for p in parties
        if str((p or {}).get("role") or "").lower() != "provider"
    )
    governing_adr_count = len(ic.get("governing_adrs") or [])
    return (
        consumer_count >= _IC_OPTIONS_MIN_CONSUMERS
        or governing_adr_count >= _IC_OPTIONS_MIN_GOVERNING_ADRS
    )


def _t_ic_missing_options(graph) -> list[Finding]:
    """T-IC-OPTIONS-MISSING (P3 advisory) — fires when a NON-TERMINAL,
    HIGH-BLAST-RADIUS Interface Contract's body lacks a populated
    ``## Options Considered / Rejected Rationale`` section.

    High-blast-radius boundaries — those many parties bind to, where tests mock
    at the seam (ADR-036) — are the ones whose first design is most expensive to
    lock blindly. The write-ic Phase-2 design-twice pass (INT-171) competes three
    designs and records the comparison in this section; this rule nudges authors
    of high-stakes ICs toward populating it before the contract advances.

    Silent when:
      - the IC already carries a populated Options Considered section, or
      - the IC is low-blast-radius (fewer than ``_IC_OPTIONS_MIN_CONSUMERS``
        consumers AND fewer than ``_IC_OPTIONS_MIN_GOVERNING_ADRS`` governing
        ADRs) — the single deep-module pass is sufficient at that stake, or
      - the IC is at a terminal status (LOCKED / MERGED / SUPERSEDED /
        DEPRECATED) — a forward-authoring discipline, not a retroactive lint on
        already-shipped contracts.

    P3-advisory + non-gating per ADR-018: it never blocks a build and stays out
    of the P0/P1/P2 doctor gate. INT-171 (η / MSN-020), D16.
    """
    out: list[Finding] = []
    for ic in graph.ics():
        status = str(ic.get("status") or "").upper()
        if status in _IC_OPTIONS_TERMINAL_STATUSES:
            continue
        if not _ic_is_high_blast_radius(ic):
            continue
        source_path = (ic.get("source") or {}).get("path", "")
        if not source_path:
            continue
        try:
            body = Path(source_path).read_text(encoding="utf-8")
        except OSError:
            continue
        if _IC_OPTIONS_SECTION_RE.search(body):
            continue
        out.append(Finding(
            rule="T-IC-OPTIONS-MISSING",
            artifact_id=ic.get("id", "<unknown>"),
            severity="P3",
            message=(
                f"High-blast-radius IC {ic.get('id')} (>= "
                f"{_IC_OPTIONS_MIN_CONSUMERS} consumers or >= "
                f"{_IC_OPTIONS_MIN_GOVERNING_ADRS} governing ADRs) has no "
                "populated `## Options Considered / Rejected Rationale` "
                "section. Record the write-ic Phase-2 design-twice comparison "
                "(the competing designs and why the surviving one is deepest) "
                "so the boundary is not locked on its first design."
            ),
            fix_kind="semantic",
        ))
    return out
