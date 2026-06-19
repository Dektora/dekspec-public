"""SpecGraph — in-memory graph of all parsed IRs in a repo.

Loaded once at session/audit start; supports cross-artifact queries:
  - graph.aes() / .adrs() / .wses() / .ics()
  - graph.by_id(artifact_id) -> IR
  - graph.consumers_of_ae(ae_id) -> [(artifact_id, kind, where_referenced)]
  - graph.aes_of_adr(adr_id) -> [ae_ids]
  - graph.aes_of_ws(ws_id) -> [ae_ids]
  - graph.aes_of_ic(ic_id) -> [ae_ids]  (from parties[].ae_id)
  - graph.implements_globs_for(artifact_id) -> [globs]
  - graph.parse_failures() -> [(path, error)]

Convention: walks the standard layout under the repo root:
  dekspec/adrs/ADR-*.md
  dekspec/architecture-elements/AE-*.md
  dekspec/working-specs/WS-*.md
  dekspec/interface-contracts/IC-*.md

Parses everything with parse() / parse_ae() / parse_ws() / parse_adr().
Records parse failures so the consumer (audit, AGENTS.md aggregator) can
report them as findings instead of silently dropping artifacts.

Public API: SpecGraph.load(repo_root, dekspec_root='dekspec') -> SpecGraph
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .parser import (
    ADRParseError,
    AEParseError,
    ConstitutionParseError,
    CSParseError,
    GlossaryParseError,
    IBParseError,
    ICParseError,
    IntentParseError,
    MissionParseError,
    SPParseError,
    VisionParseError,
    WSParseError,
    parse,
    parse_adr,
    parse_ae,
    parse_constitution,
    parse_context_spec,
    parse_glossary,
    parse_ib,
    parse_intent,
    parse_mission,
    parse_security_profile,
    parse_vision,
    parse_ws,
)


@dataclass
class ParseFailure:
    path: str
    artifact_kind: str  # 'ic' | 'ae' | 'ws' | 'adr'
    error_type: str
    message: str


# --------------------------------------------------------------------------- #
# Artifact-ID sort key
# --------------------------------------------------------------------------- #

_ID_SPLIT_RE = re.compile(r"^([A-Za-z-]+?)-?(\d+)$")


def artifact_id_sort_key(artifact_id: str) -> tuple[str, int, str]:
    """Natural sort key for a DekSpec artifact ID.

    Splits an ID like ``IB-009`` into its kind prefix and numeric suffix so
    that ``IB-9`` sorts before ``IB-32`` (numeric-suffix-aware), and so that
    IDs of different kinds group deterministically. IDs that do not match the
    ``<PREFIX>-<digits>`` shape fall back to a pure-lexicographic key (the
    prefix carries the whole string, numeric component 0) so the sort is
    still total and deterministic.

    This is the single ID-sort helper for the Constraint Compiler — used by
    :func:`derive_backlinks` and the ``Linked Artifacts`` emitter so every
    rendered ``Related *`` list is byte-stable across runs and processes.
    """
    m = _ID_SPLIT_RE.match(artifact_id.strip())
    if m is None:
        return (artifact_id, 0, artifact_id)
    prefix, digits = m.group(1), m.group(2)
    return (prefix.upper(), int(digits), artifact_id)


def _compose_storage_key(ir: dict[str, Any], kind: str) -> str:
    """Compose the SpecGraph storage key for an IR.

    Most artifacts (ADR/AE/WS/IC/INT/MSN/singletons) have globally unique
    IDs and are keyed by ``ir["id"]`` directly. IBs are the exception: an
    IB-NNN ID is unique only within its parent Working Spec, not globally
    (two WSes can each have an IB-001). Storing IBs by bare ``IB-NNN``
    silently overwrites — the load order determines which IB survives,
    and the other IBs in the corpus are invisible to audits and emitters.

    The fix: scope the storage key by the parent WS, ``<spec_id>:<ib_id>``.
    If the IB's ``spec`` field is missing/malformed (a separate defect,
    surfaced by L5-IB-SPEC-MISSING), fall back to a ``<unknown>:<ib_id>``
    placeholder so the IR still lands in the graph and remains
    discoverable. The placeholder collisions are themselves caught by
    LX-DUP.

    See ``ds-audit-lx-dup-ignores-ib-ws-scope-ae1`` for the rationale.
    """
    if kind != "ib":
        return ir["id"]
    spec = ir.get("spec")
    spec_id: str | None = None
    if isinstance(spec, dict):
        raw = spec.get("id")
        if isinstance(raw, str) and raw:
            spec_id = raw
    return f"{spec_id or '<unknown>'}:{ir['id']}"


@dataclass
class SpecGraph:
    """In-memory graph keyed by artifact id (e.g., 'AE-014').

    IBs are keyed by ``<spec_id>:<ib_id>`` rather than bare ``IB-NNN``
    because IB IDs are unique only within their parent Working Spec.
    Use :py:meth:`ib_by_scope` for unambiguous IB lookups; :py:meth:`by_id`
    accepts bare ``IB-NNN`` for backward compatibility and returns the
    first match found (with no defined order when the corpus contains
    multiple IBs sharing the bare ID — call ``ib_by_scope`` instead).
    """

    irs_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: list[ParseFailure] = field(default_factory=list)
    repo_root: Path | None = None
    dekspec_dir: Path | None = None

    # ----------------------------------------------------------------------- #
    # Loading
    # ----------------------------------------------------------------------- #

    @classmethod
    def load(
        cls,
        repo_root: str | Path,
        dekspec_root: str = "dekspec",
    ) -> SpecGraph:
        """Walk the conventional layout and parse every artifact found.

        Returns a graph populated from disk. Parse failures are captured in
        graph.failures rather than raised — the audit caller surfaces them
        as findings.
        """
        root = Path(repo_root).resolve()
        dekspec_dir = root / dekspec_root
        graph = cls(repo_root=root, dekspec_dir=dekspec_dir)
        if not dekspec_dir.exists():
            return graph

        loaders = [
            (dekspec_dir / "adrs", "ADR-*.md", "adr", parse_adr, ADRParseError, False),
            (dekspec_dir / "architecture-elements", "AE-*.md", "ae", parse_ae, AEParseError, False),
            (dekspec_dir / "working-specs", "WS-*.md", "ws", parse_ws, WSParseError, False),
            (dekspec_dir / "security-profiles", "SP-*.md", "sp", parse_security_profile, SPParseError, False),
            (dekspec_dir / "interface-contracts", "IC-*.md", "ic", parse, ICParseError, False),
            (dekspec_dir / "impl-briefs", "IB-*.md", "ib", parse_ib, IBParseError, True),
            (dekspec_dir / "intents", "INT-*.md", "intent", parse_intent, IntentParseError, True),
            (dekspec_dir / "missions", "MSN-*.md", "mission", parse_mission, MissionParseError, True),
            # ContextSpec (INT-139 / ds-uqnx): role-identity context-window IRs.
            # Canonical filename is role-keyed (role-<role>.md), NOT ID-keyed —
            # the CS-NNN id is sourced from the `## ID` body section.
            (
                dekspec_dir / "context-specs",
                "role-*.md",
                "context_spec",
                parse_context_spec,
                CSParseError,
                False,
            ),
        ]
        from ..draft_ids import is_draft_filename

        for dir_path, glob, kind, parse_fn, parse_err, recursive in loaders:
            if not dir_path.exists():
                continue
            iterator = dir_path.rglob(glob) if recursive else dir_path.glob(glob)
            for artifact_path in sorted(iterator):
                # DRAFT artifacts (`<KIND>-DRAFT-<slug>.md`, INT-020) carry a
                # temporary ID and never enter the canonical audit graph —
                # they are allocated to canonical IDs at commit time via
                # `dekspec id allocate`. Skip them here so they neither
                # parse-fail nor pollute the SpecGraph.
                if is_draft_filename(artifact_path.name):
                    continue
                try:
                    ir = parse_fn(artifact_path)
                    graph.irs_by_id[_compose_storage_key(ir, kind)] = ir
                except parse_err as e:
                    graph.failures.append(
                        ParseFailure(
                            path=str(artifact_path),
                            artifact_kind=kind,
                            error_type=type(e).__name__,
                            message=str(e),
                        )
                    )
                except Exception as e:  # pragma: no cover — catch-all for robustness
                    graph.failures.append(
                        ParseFailure(
                            path=str(artifact_path),
                            artifact_kind=kind,
                            error_type=type(e).__name__,
                            message=str(e),
                        )
                    )

        # Singleton artifacts: domain-glossary.md + system-vision.md +
        # constitution.md (the L0 trio). Each is optional; missing files
        # do not fail the load.
        for filename, kind, parse_fn, parse_err in (
            ("domain-glossary.md", "glossary", parse_glossary, GlossaryParseError),
            ("system-vision.md", "vision", parse_vision, VisionParseError),
            ("constitution.md", "constitution", parse_constitution, ConstitutionParseError),
        ):
            singleton_path = dekspec_dir / filename
            if not singleton_path.exists():
                continue
            try:
                ir = parse_fn(singleton_path)
                graph.irs_by_id[_compose_storage_key(ir, kind)] = ir
            except parse_err as e:
                graph.failures.append(
                    ParseFailure(
                        path=str(singleton_path),
                        artifact_kind=kind,
                        error_type=type(e).__name__,
                        message=str(e),
                    )
                )

        return graph

    # ----------------------------------------------------------------------- #
    # Per-kind iterators
    # ----------------------------------------------------------------------- #

    def all(self) -> Iterator[dict[str, Any]]:
        return iter(self.irs_by_id.values())

    def adrs(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("ADR-"))

    def aes(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("AE-"))

    def wses(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("WS-"))

    def ics(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("IC-"))

    def ibs(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("IB-"))

    def intents(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("INT-"))

    def missions(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("MSN-"))

    def security_profiles(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("SP-"))

    def context_specs(self) -> Iterator[dict[str, Any]]:
        return (ir for ir in self.irs_by_id.values() if ir["id"].startswith("CS-"))

    def glossary(self) -> dict[str, Any] | None:
        return self.irs_by_id.get("DOMAIN-GLOSSARY")

    def vision(self) -> dict[str, Any] | None:
        return self.irs_by_id.get("SYSTEM-VISION")

    def constitution(self) -> dict[str, Any] | None:
        """Return the parsed Constitution IR, or None if the corpus has none.

        Mirrors the glossary() / vision() accessors. Reads the L0 singleton
        loaded from `<dekspec-root>/constitution.md`. Consumers without a
        Constitution remain valid — the absence is not an error.
        """
        return self.irs_by_id.get("CONSTITUTION")

    # ----------------------------------------------------------------------- #
    # Queries
    # ----------------------------------------------------------------------- #

    def by_id(self, artifact_id: str) -> dict[str, Any] | None:
        # Fast path: direct hit (works for globally-unique kinds).
        direct = self.irs_by_id.get(artifact_id)
        if direct is not None:
            return direct
        # Fallback for bare IB-NNN lookups under composite-keyed storage.
        # Ambiguous if multiple IBs share the bare ID across WSes — the
        # first match wins. Use ib_by_scope() for unambiguous lookup.
        if artifact_id.startswith("IB-"):
            suffix = f":{artifact_id}"
            for key, ir in self.irs_by_id.items():
                if key.endswith(suffix):
                    return ir
        return None

    def has(self, artifact_id: str) -> bool:
        if artifact_id in self.irs_by_id:
            return True
        if artifact_id.startswith("IB-"):
            suffix = f":{artifact_id}"
            return any(key.endswith(suffix) for key in self.irs_by_id)
        return False

    def ib_by_scope(self, spec_id: str, ib_id: str) -> dict[str, Any] | None:
        """Unambiguous IB lookup by (parent WS, IB ID).

        Returns the IB IR whose composite storage key is
        ``f"{spec_id}:{ib_id}"``, or None if no such IB exists. Prefer
        this over :py:meth:`by_id` when the calling context already
        knows the parent WS.
        """
        return self.irs_by_id.get(f"{spec_id}:{ib_id}")

    def aes_of_adr(self, adr_id: str) -> list[str]:
        """AE-NNN ids referenced by ADR.related_architecture_elements."""
        adr = self.by_id(adr_id)
        if not adr:
            return []
        return [r["id"] for r in adr.get("related_architecture_elements", [])]

    def aes_of_ws(self, ws_id: str) -> list[str]:
        """AE-NNN ids referenced by WS.related_architecture_elements."""
        ws = self.by_id(ws_id)
        if not ws:
            return []
        return [r["id"] for r in ws.get("related_architecture_elements", [])]

    def aes_of_ic(self, ic_id: str) -> list[str]:
        """AE-NNN ids referenced by an IC. Reads (in priority order):
          1. provider_ae + consumer_aes top-level fields (post-v0.3.1 canonical)
          2. parties[].ae_id (v0.2.x legacy fallback)
        Deduped and order-preserving.
        """
        ic = self.by_id(ic_id)
        if not ic:
            return []
        out: list[str] = []
        if ic.get("provider_ae"):
            out.append(ic["provider_ae"])
        out.extend(ic.get("consumer_aes", []))
        for p in ic.get("parties", []):
            if "ae_id" in p:
                out.append(p["ae_id"])
        return list(dict.fromkeys(out))

    def aes_of_ib(self, ib_id: str) -> list[str]:
        """AE-NNN ids referenced by an IB. Reads (in priority order):
          1. source_aes top-level field (canonical, per template post-v5)
          2. transitive via spec.id -> WS.related_architecture_elements
        Deduped and order-preserving.
        """
        ib = self.by_id(ib_id)
        if not ib:
            return []
        out: list[str] = [r["id"] for r in ib.get("source_aes", []) or []]
        spec = ib.get("spec") or {}
        ws_id = spec.get("id")
        if ws_id:
            out.extend(self.aes_of_ws(ws_id))
        return list(dict.fromkeys(out))

    # ----------------------------------------------------------------------- #
    # Forward-link traversal + backlink derivation (ADR-015)
    # ----------------------------------------------------------------------- #

    @staticmethod
    def _adrs_of(ir: dict[str, Any]) -> list[str]:
        """ADR-NNN ids an artifact forward-links via ``governing_adrs``.

        WS / IC / IB all carry a ``governing_adrs`` list of ``{id: ADR-NNN}``
        objects. Artifacts without the field yield ``[]``.
        """
        out: list[str] = []
        for ref in ir.get("governing_adrs", []) or []:
            ref_id = ref.get("id") if isinstance(ref, dict) else ref
            if isinstance(ref_id, str) and ref_id:
                out.append(ref_id)
        return out

    def forward_links_of(self, artifact_id: str) -> list[str]:
        """All artifact IDs an artifact forward-links to.

        Single authoritative forward-link traversal. Reuses the existing
        ``aes_of_*`` primitives for the AE direction and adds the
        ADR / WS directions, so :func:`derive_backlinks` walks one
        traversal rather than five copies. The result preserves discovery
        order and is deduped; ordering for rendered output is imposed by
        :func:`derive_backlinks` (sorted ascending by ID).

        Forward-link model (ADR-015):
          - ADR    -> AEs            (related_architecture_elements)
          - WS     -> AEs, ADRs      (related_architecture_elements, governing_adrs)
          - IC     -> AEs, ADRs      (provider_ae / consumer_aes / parties, governing_adrs)
          - IB     -> AEs, ADRs, WS  (source_aes, governing_adrs, spec.id)
          - Intent -> AEs            (linked_architecture_elements)
        """
        ir = self.by_id(artifact_id)
        if ir is None:
            return []
        out: list[str] = []
        if artifact_id.startswith("ADR-"):
            out.extend(self.aes_of_adr(artifact_id))
        elif artifact_id.startswith("WS-"):
            out.extend(self.aes_of_ws(artifact_id))
            out.extend(self._adrs_of(ir))
        elif artifact_id.startswith("IC-"):
            out.extend(self.aes_of_ic(artifact_id))
            out.extend(self._adrs_of(ir))
        elif artifact_id.startswith("IB-"):
            out.extend([r["id"] for r in ir.get("source_aes", []) or []])
            out.extend(self._adrs_of(ir))
            spec = ir.get("spec") or {}
            ws_id = spec.get("id")
            if isinstance(ws_id, str) and ws_id:
                out.append(ws_id)
        elif artifact_id.startswith("INT-"):
            out.extend(
                r["id"] for r in ir.get("linked_architecture_elements", []) or []
            )
        return list(dict.fromkeys(out))

    @staticmethod
    def _related_bucket_for(referrer_id: str) -> str | None:
        """Which ``related_*`` bucket a referrer ID lands in, by kind."""
        if referrer_id.startswith("ADR-"):
            return "related_adrs"
        if referrer_id.startswith("WS-"):
            return "related_wss"
        if referrer_id.startswith("IC-"):
            return "related_ics"
        if referrer_id.startswith("IB-"):
            return "related_ibs"
        if referrer_id.startswith("INT-"):
            return "related_intents"
        return None

    def derive_backlinks(
        self,
    ) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
        """Derive every artifact's backlinks from the forward-link index.

        ADR-015: the SpecGraph forward-link index is the single authoritative
        backlink source. This function walks the union of every parsed
        artifact's forward links and inverts the map: for each artifact ID it
        returns the set of artifact IDs that point at it, partitioned by
        referrer kind.

        Returns a ``(backlinks, unresolved_ids)`` tuple:

          - ``backlinks`` — ``{artifact_id: {"related_adrs": [...],
            "related_wss": [...], "related_ics": [...], "related_ibs": [...],
            "related_intents": [...]}}``. Every artifact in the graph appears
            as a key; every artifact gets all five buckets present; each list
            is sorted ascending by artifact ID via :func:`artifact_id_sort_key`.
            Empty buckets are empty lists.
          - ``unresolved_ids`` — sorted list of forward-ref target IDs that do
            not resolve to any parsed artifact (dangling forward refs). The
            ``dekspec relink`` CLI verb (IB-042) consumes this for dangling-ref
            reporting; this function only collects them.

        Pure: does not mutate the graph and does no I/O. The function reads
        only the in-memory ``SpecGraph`` and deliberately ignores any stored
        ``related_*s`` schema field — the derived value is authoritative.
        """
        buckets = ("related_adrs", "related_wss", "related_ics", "related_ibs",
                   "related_intents")
        # Every artifact gets all five buckets, even with zero referrers.
        backlinks: dict[str, dict[str, set[str]]] = {
            ir["id"]: {b: set() for b in buckets}
            for ir in self.irs_by_id.values()
        }
        unresolved: set[str] = set()

        for ir in self.irs_by_id.values():
            referrer_id = ir["id"]
            bucket = self._related_bucket_for(referrer_id)
            for target_id in self.forward_links_of(referrer_id):
                target_entry = backlinks.get(target_id)
                if target_entry is None:
                    # Forward ref to an ID with no parsed artifact -> dangling.
                    if not self.has(target_id):
                        unresolved.add(target_id)
                    continue
                if bucket is not None:
                    target_entry[bucket].add(referrer_id)

        sorted_backlinks: dict[str, dict[str, list[str]]] = {
            artifact_id: {
                b: sorted(entry[b], key=artifact_id_sort_key) for b in buckets
            }
            for artifact_id, entry in backlinks.items()
        }
        return sorted_backlinks, sorted(unresolved, key=artifact_id_sort_key)

    def consumers_of_ae(
        self, ae_id: str
    ) -> list[tuple[str, str, str]]:
        """All artifacts that reference this AE.

        Returns list of (consumer_id, consumer_kind, where_referenced) tuples.
        where_referenced is one of: 'related_architecture_elements' (ADR/WS),
        'parties[].ae_id' (IC). Useful for L6 backlink integrity checks.
        """
        out: list[tuple[str, str, str]] = []
        for adr in self.adrs():
            if ae_id in (r["id"] for r in adr.get("related_architecture_elements", [])):
                out.append((adr["id"], "adr", "related_architecture_elements"))
        for ws in self.wses():
            if ae_id in (r["id"] for r in ws.get("related_architecture_elements", [])):
                out.append((ws["id"], "ws", "related_architecture_elements"))
        for ic in self.ics():
            if ic.get("provider_ae") == ae_id:
                out.append((ic["id"], "ic", "provider_ae"))
            elif ae_id in ic.get("consumer_aes", []):
                out.append((ic["id"], "ic", "consumer_aes"))
            elif ae_id in (p.get("ae_id") for p in ic.get("parties", [])):
                out.append((ic["id"], "ic", "parties[].ae_id"))
        # ds-52p D-17: IBs reference AEs via source_aes; mirror so the AE
        # side exposes its related_ibs back-edges in the graph.
        for ib in self.ibs():
            for ref in ib.get("source_aes", []) or []:
                ref_id = ref["id"] if isinstance(ref, dict) else ref
                if ref_id == ae_id:
                    out.append((ib["id"], "ib", "source_aes"))
                    break
        # ds-u69: Intents reference AEs via linked_architecture_elements;
        # mirror so the AE side exposes its related_intents back-edges in
        # the graph. (Missions are intentionally not mirrored: they have no
        # direct AE link in the Mission schema — they reach AEs only
        # through their child Intents' intent_queue, so a Mission→AE
        # mirror would be a transitive artifact rather than a direct one.)
        for intent in self.intents():
            for ref in intent.get("linked_architecture_elements", []) or []:
                ref_id = ref["id"] if isinstance(ref, dict) else ref
                if ref_id == ae_id:
                    out.append((intent["id"], "intent", "linked_architecture_elements"))
                    break
        return out

    def implements_globs_for(self, artifact_id: str) -> list[str]:
        """Compute the union of implements_globs from referenced AEs.

        For an IC: union over each parties[].ae_id's AE.implements_globs.
        For a WS: union over each related_architecture_elements[].id's AE.implements_globs.
        For an AE: returns its own implements_globs.
        For an ADR: returns [] (ADRs don't drive CI gate scoping per the playbook).
        """
        ir = self.by_id(artifact_id)
        if ir is None:
            return []
        if artifact_id.startswith("AE-"):
            return list(ir.get("implements_globs", []))
        if artifact_id.startswith("ADR-"):
            return []
        if artifact_id.startswith("IC-"):
            ae_ids = self.aes_of_ic(artifact_id)
        elif artifact_id.startswith("WS-"):
            ae_ids = self.aes_of_ws(artifact_id)
        else:
            return []
        out: list[str] = []
        for ae_id in ae_ids:
            ae = self.by_id(ae_id)
            if ae is None:
                continue
            for g in ae.get("implements_globs", []):
                if g not in out:
                    out.append(g)
        return out

    def parse_failures(self) -> list[ParseFailure]:
        return list(self.failures)

    # ----------------------------------------------------------------------- #
    # Summary
    # ----------------------------------------------------------------------- #

    def __repr__(self) -> str:
        n_adr = sum(1 for _ in self.adrs())
        n_ae = sum(1 for _ in self.aes())
        n_ws = sum(1 for _ in self.wses())
        n_ic = sum(1 for _ in self.ics())
        n_fail = len(self.failures)
        return (
            f"<SpecGraph repo_root={self.repo_root} "
            f"adrs={n_adr} aes={n_ae} wses={n_ws} ics={n_ic} failures={n_fail}>"
        )
