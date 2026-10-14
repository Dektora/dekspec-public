"""Optional read-only Builder process boundary (IC-020 S0).

Only transport shape is checked here. Spec supplies completion judgment and
Builder supplies its strictly read, recorded integration; Tools owns neither.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

INTERFACE = "structural3-builder-receipt-v1"


class ReceiptUnavailable(Exception):
    """The optional source supplied no usable receipt."""


def _object(value, fields, label):
    if not isinstance(value, dict) or not set(fields).issubset(value):
        raise ReceiptUnavailable(f"malformed {label}: required fields are missing")


def _strings(value):
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _sequence(value):
    return type(value) is int and value >= 0


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate field {key}")
        result[key] = value
    return result


def read_receipt(root: Path, target: str) -> dict:
    """Read one explicit governed target, without acquisition or Python imports."""
    try:
        proc = subprocess.run(
            ["dekbuilder", "implement", "receipt", target, "--at", str(root), "--json"],
            cwd=root, text=True, capture_output=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReceiptUnavailable(f"Builder receipt unavailable: {exc}") from exc
    if proc.returncode:
        detail = ""
        try:
            failure = json.loads(proc.stdout, object_pairs_hook=_unique_object)
            if (isinstance(failure, dict) and failure.get("interface") == INTERFACE
                    and failure.get("available") is False and isinstance(failure.get("error"), dict)
                    and failure["error"].get("code") == "receipt-unavailable"
                    and isinstance(failure["error"].get("detail"), str)):
                detail = ": " + failure["error"]["detail"]
        except ValueError:
            pass
        raise ReceiptUnavailable(f"Builder receipt unavailable (exit {proc.returncode}){detail}")
    try:
        receipt = json.loads(proc.stdout, object_pairs_hook=_unique_object)
    except ValueError as exc:
        raise ReceiptUnavailable(f"malformed Builder receipt: {exc}") from exc
    _object(receipt, ("interface", "available", "outcome", "resolved", "base", "deliveries"),
            "Builder receipt")
    if receipt["interface"] != INTERFACE or receipt["available"] is not True:
        raise ReceiptUnavailable("Builder receipt has an unavailable or incompatible interface")
    if not isinstance(receipt["outcome"], str) or not _strings(receipt["resolved"]):
        raise ReceiptUnavailable("malformed Builder receipt outcome or resolved targets")
    base = receipt["base"]
    _object(base, ("name", "ref", "revision", "problem"), "Builder receipt base")
    if not all(isinstance(base[k], str) and base[k] for k in ("name", "ref")) or not (
            base["revision"] is None or isinstance(base["revision"], str)) or not (
            base["problem"] is None or isinstance(base["problem"], str)):
        raise ReceiptUnavailable("malformed Builder receipt base")
    if not isinstance(receipt["deliveries"], list):
        raise ReceiptUnavailable("malformed Builder receipt deliveries")
    for delivery in receipt["deliveries"]:
        _object(delivery, ("slug", "run", "worktree", "state", "ibs", "outstanding", "last_seq",
                           "last_hash", "integration", "completion_refs", "completion_problem"),
                "Builder delivery")
        if not all(isinstance(delivery[k], str) and delivery[k]
                   for k in ("slug", "run", "worktree", "state")) or not (
                Path(delivery["worktree"]).is_absolute() and _strings(delivery["ibs"])
                and isinstance(delivery["outstanding"], list) and _sequence(delivery["last_seq"])
                and (delivery["last_hash"] is None or isinstance(delivery["last_hash"], str))):
            raise ReceiptUnavailable("malformed Builder delivery identity or record head")
        integration = delivery["integration"]
        if integration is not None:
            _object(integration, ("seq", "hash", "data"), "Builder integration")
            if not (_sequence(integration["seq"]) and isinstance(integration["hash"], str)
                    and integration["hash"] and isinstance(integration["data"], dict)):
                raise ReceiptUnavailable("malformed Builder integration event")
            _object(integration["data"], ("revision", "tree"), "Builder integration data")
            if not all(isinstance(integration["data"][k], str) and integration["data"][k]
                       for k in ("revision", "tree")):
                raise ReceiptUnavailable("malformed Builder integration revision or tree")
        refs = delivery["completion_refs"]
        if refs is not None:
            _object(refs, delivery["ibs"], "Spec completion references")
            for ib in delivery["ibs"]:
                ref = refs[ib]
                _object(ref, ("seq", "hash", "evidence_seq", "verdict_seq"), "Spec completion reference")
                if not (all(_sequence(ref[k]) and ref[k] > 0
                            for k in ("seq", "evidence_seq", "verdict_seq"))
                        and isinstance(ref["hash"], str) and ref["hash"]):
                    raise ReceiptUnavailable("malformed Spec completion reference")
        if delivery["completion_problem"] is not None and not isinstance(
                delivery["completion_problem"], str):
            raise ReceiptUnavailable("malformed Spec completion problem")
    # Hide transport representation from the existing pass reducer. These
    # values retain the actual event data; no local completion judgment runs.
    return {**receipt, "deliveries": [
        {**delivery, "integration": SimpleNamespace(**delivery["integration"])
         if delivery["integration"] is not None else None}
        for delivery in receipt["deliveries"]
    ]}
