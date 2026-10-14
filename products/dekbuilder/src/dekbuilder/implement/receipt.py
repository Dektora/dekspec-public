"""Strict, read-only S0 observations for optional governed Tools callers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dekspec.builder_compat import Engine, completion_receipt
from dekbuilder.implement import driver, integration
from dekbuilder.implement.config import load_integration
from dekbuilder.implement.readiness import authoritative_base

INTERFACE = "structural3-builder-receipt-v1"


def receipt(root: Path, request: str) -> dict[str, Any]:
    """Aggregate actual strict records and Spec judgments without invoking admission probes."""
    root = Path(root).resolve()
    resolution, readiness, deliveries, settings = driver._plan(root, request, strict=True)
    if not resolution.ok or readiness is None:
        raise driver.DriverError("unresolved receipt target: " + "; ".join(p["detail"] for p in resolution.problems))
    # Readiness can omit a blocked target's delivery. Preserve the original Tools
    # missing-worktree refusal independently of the selected readiness groups.
    for target in resolution.targets:
        branch = f"implement/{target.id.lower()}"
        if driver._git(root, "rev-parse", "-q", "--verify", f"refs/heads/{branch}").returncode != 0:
            continue
        holder = driver._branch_path(root, branch)
        if holder is None or not holder.exists():
            raise driver.DriverError(f"delivery worktree unavailable: {branch} ({holder or 'none'}); "
                                     "its recorded integration cannot be read")
    name, ref = authoritative_base(root, load_integration(root))
    base = driver._git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    out = {"interface": INTERFACE, "available": True, "outcome": None,
           "resolved": [t.id for t in resolution.targets],
           "base": {"name": name, "ref": ref, "revision": base.stdout.strip() if base.returncode == 0 else None,
                    "problem": None if base.returncode == 0 else f"authoritative base {ref} cannot resolve"},
           "deliveries": []}
    status_entries = []
    for delivery in deliveries:
        entry = {"slug": delivery.slug, "run": delivery.run_id, "worktree": str(delivery.path.resolve()),
                 "state": "not-started", "ibs": [], "outstanding": [], "last_seq": 0, "last_hash": None,
                 "integration": None, "reported": None, "completion_refs": None,
                 "completion_problem": "the delivery has not started"}
        if delivery.exists:
            if not delivery.path.is_dir():
                raise driver.DriverError(f"delivery worktree unavailable: {delivery.path}")
            engine = Engine(delivery.path, base=integration.base_ref(delivery.path, delivery.base, settings, fetch=False))
            record = engine.record(delivery.run_id)
            if not record.exists():
                raise driver.DriverError(f"run record unavailable: {delivery.run_id}")
            events = record.events(strict=True)
            view = driver._view(engine, delivery.run_id, strict=True)
            observed = integration.observe(delivery.path, delivery.base, settings, fetch=False)
            entry["state"] = driver._delivery_state(engine, view, delivery, settings, observed)
            entry["ibs"] = list(view.auth.get("ibs", []))
            entry["outstanding"] = view.outstanding
            if events:
                entry["last_seq"], entry["last_hash"] = events[-1].seq, events[-1].hash
            integrated = next((e for e in reversed(events) if e.type == "run.integrated"), None)
            if integrated is not None:
                entry["integration"] = {"seq": integrated.seq, "hash": integrated.hash, "data": integrated.data}
                entry["reported"] = driver._recorded_integration(view)
            refs = {}
            missing = []
            for ib in entry["ibs"]:
                ref_receipt = completion_receipt(engine, ib)
                if ref_receipt is None:
                    missing.append(ib)
                else:
                    refs[ib] = ref_receipt
            if missing or not entry["ibs"]:
                entry["completion_problem"] = "no current completion receipt for " + (", ".join(missing) or "any IB")
            else:
                entry["completion_refs"], entry["completion_problem"] = refs, None
        out["deliveries"].append(entry)
        status_entries.append({"targets": delivery.targets, "state": entry["state"]})
    out["outcome"] = driver._status_summary(readiness, deliveries, status_entries)["outcome"]
    return out
