"""Migration of legacy work into the execution model (ADR-056 / ADR-057).

Two transitions, both explicit and recorded — nothing is reinterpreted silently:

* :func:`import_beads` moves a legacy IB's code beads (``cb-`` workspace)
  into the IB's execution record as internal tasks, keeping each bead's id,
  title, status, owner, dependency edges and closure evidence. The beads
  themselves are left untouched; the import is idempotent per bead.
* :func:`adopt` switches an IB from the legacy to the delegated authority
  policy once its author has rewritten the contract (binding obligations,
  acceptance, hypothesis), takes the adoption baseline, and records the
  change in the IB's Amendment Log.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from dekspec.execution import acceptance as acc
from dekspec.execution.engine import Engine, ExecutionError
from dekspec.execution.history import authority_policy_of, file_versions
from dekspec.execution.state import fold

__all__ = ["adopt", "import_beads"]

_STATUS_MAP = {"closed": "done", "done": "done", "in_progress": "in_progress", "open": "pending",
               "blocked": "blocked", "deferred": "blocked", "tombstone": None}


def _bead_refs_ib(bead: dict[str, Any], ib_id: str, ib_path: str) -> bool:
    ref = str(bead.get("external_ref") or "")
    if not ref:
        return False
    head = ref.split(":", 1)[0] if re.match(r"^IB-\d{3,}:", ref) else ref
    return head == ib_id or head.endswith(Path(ib_path).name) or f"/{ib_id}-" in head or head.startswith(f"{ib_id}-")


def _read_beads(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ExecutionError(f"no bead file at {path}")
    beads = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                beads.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return beads


def import_beads(engine: Engine, ref: str, actor: str, *, source: Path | None = None) -> dict[str, Any]:
    c = engine.contract(ref)
    source = source or engine.repo_root / ".beads" / "issues.jsonl"
    beads = [b for b in _read_beads(source) if _bead_refs_ib(b, c.ib_id, c.rel_path)]
    rec, events, st = engine.state(c.ib_id)
    if st.completions or c.status == "COMPLETE":
        raise ExecutionError(f"{c.ib_id} is complete; there is no in-flight work to import")
    already = {b["id"] for e in events if e.type == "legacy.beads-imported" for b in e.data.get("beads", [])}
    new = [b for b in beads if b.get("id") not in already and _STATUS_MAP.get(b.get("status"), "pending")]
    if not new:
        return {"ib": c.ib_id, "imported": 0, "already": sorted(already)}
    # Only beads that become tasks can be depended on; an edge to anything
    # else (a tombstoned or foreign bead) is dropped and reported.
    ids = {b["id"] for b in new} | {tid[2:] for tid in st.tasks}
    tasks = []
    dropped: list[str] = []
    for b in new:
        deps = []
        for d in b.get("dependencies") or []:
            target = d.get("depends_on_id") if isinstance(d, dict) else d
            if target in ids:
                deps.append(f"T-{target}")
            elif target:
                dropped.append(f"{b['id']} → {target}")
        tasks.append({"id": f"T-{b['id']}", "title": b.get("title", ""), "covers": [],
                      "depends_on": deps, "files": []})
    if not st.started:
        owners = [b.get("assignee") for b in new if b.get("status") == "in_progress" and b.get("assignee")]
        rec.append("run.started", actor, {"owner": owners[0] if owners else actor, "legacy": True,
                                          "contract_hash": c.contract_hash()})
    rec.append("legacy.beads-imported", actor, {
        "source": str(source.relative_to(engine.repo_root)) if source.is_relative_to(engine.repo_root) else str(source),
        "beads": [{"id": b["id"], "status": b.get("status"), "assignee": b.get("assignee"),
                   "close_reason": b.get("close_reason"), "external_ref": b.get("external_ref")} for b in new],
        "dropped_dependencies": dropped})
    prior_tasks = [{k: t.get(k) for k in ("id", "title", "covers", "depends_on", "files")} for t in st.tasks.values()]
    rec.append("plan.committed", actor, {"revision": st.plan_revision + 1, "direct": False, "legacy": True,
                                         "findings": None, "rationale": "imported legacy code beads",
                                         "tasks": prior_tasks + tasks, "hypothesis_deviations": []})
    for b in new:
        status = _STATUS_MAP.get(b.get("status"), "pending")
        data: dict[str, Any] = {"task": f"T-{b['id']}", "status": status}
        if b.get("assignee"):
            data["owner"] = b["assignee"]
        if status == "done":
            data["evidence"] = f"bead {b['id']} closed: {b.get('close_reason') or 'no reason recorded'}"
        rec.append("task.updated", actor, data)
    return {"ib": c.ib_id, "imported": len(new), "tasks": [t["id"] for t in tasks], "dropped_dependencies": dropped}


def adopt(engine: Engine, ref: str, actor: str, *, reason: str) -> dict[str, Any]:
    """Switch a rewritten IB from legacy to delegated authority, deliberately."""
    c = engine.contract(ref)
    if not c.is_delegated:
        raise ExecutionError(
            f"{c.ib_id} still declares the legacy authority policy. Rewrite it first (`/write-ibs --adopt`): "
            "classify each legacy constraint as a binding obligation (reference its home) or an implementation "
            "hypothesis, write the Acceptance block, then set `**Authority policy:** delegated`.")
    problems = c.contract_problems()
    if problems:
        raise ExecutionError("the adopted contract is not executable yet: " + "; ".join(problems))
    if c.status not in ("ACCEPTED", "PROPOSED"):
        raise ExecutionError(f"{c.ib_id} is {c.status}; adoption applies to in-flight (PROPOSED/ACCEPTED) IBs")
    rec, _events, st = engine.state(c.ib_id)
    if any(e.get("type") == "legacy.adopted" for e in st.legacy):
        raise ExecutionError(f"{c.ib_id} was already adopted")
    # Adoption is a one-way migration of legacy work, not a way to re-take a
    # baseline: once a delegated authorization exists, every baseline change
    # is an independent amendment (`dekspec ib amend`, ADR-057).
    if st.baseline is not None:
        raise ExecutionError(
            f"{c.ib_id} already has a delegated acceptance baseline (event #{st.baseline_seq}); "
            "adoption cannot replace it — change the acceptance contract with `dekspec ib amend`")
    if not any(authority_policy_of(text) == "legacy"
               for _commit, _path, text in file_versions(engine.repo_root, c.rel_path)):
        raise ExecutionError(
            f"{c.ib_id} was never committed under the legacy authority policy, so there is nothing to "
            "adopt; authorize a delegated IB with `dekspec ib accept`")
    if actor in st.builder_identities:
        raise ExecutionError(
            f"{actor} works on {c.ib_id}'s run; adoption takes the acceptance baseline, so it must be "
            "recorded by someone independent of the builders")
    payload = acc.baseline_payload(engine.repo_root, c)
    payload.update({"by": actor, "phase": "adoption", "reason": reason,
                    "absent_assets": sorted(k for k, v in payload["assets"].items() if v is None)})
    rec.append("legacy.adopted", actor, {"reason": reason, "contract_hash": c.contract_hash()})
    if c.status == "ACCEPTED":
        rec.append("acceptance.baselined", actor, payload)
    from dekspec.execution.artifact_edit import set_status

    set_status(c.path, {c.status}, c.status, author=actor,
               change=f"Adopted: authority policy legacy → delegated (ADR-055). {reason}")
    return {"ib": c.ib_id, "baseline": acc.baseline_digest(payload) if c.status == "ACCEPTED" else None,
            "run_state": fold(engine.record(c.ib_id).events()).phase()}
