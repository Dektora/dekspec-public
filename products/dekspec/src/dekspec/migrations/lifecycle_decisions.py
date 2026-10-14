"""IR-JSON migrations for the decision-only lifecycle (ADR-055–057).

Carries persisted compile output forward to the schemas that retired activity
statuses and bead fields. The mapping is the same one the markdown migration
(:mod:`dekspec.migrations.disciplined_delegation`) applies to source files,
so a persisted IR and its re-parsed source agree after both run.

Also closes a pre-existing gap in the chain: IB and Intent went 0.2.0 → 0.3.0
(INT-102 / INT-104) with purely additive changes and no registered step, so
persisted 0.2.0 IR could not reach the latest version.
"""

from __future__ import annotations

import copy
from typing import Any

from . import Migration, default_registry
from .disciplined_delegation import _DEFAULT_MAP, _STATUS_MAPS

__all__: list[str] = []


def _map_status(ir: dict[str, Any], kind: str, to_version: str) -> dict[str, Any]:
    out = copy.deepcopy(ir)
    mapping = _STATUS_MAPS.get(kind, _DEFAULT_MAP)
    status = out.get("status")
    if status in mapping:
        out["status"] = mapping[status]
    out["ir_schema_version"] = to_version
    return out


def _identity(to_version: str):
    def migrate(ir: dict[str, Any]) -> dict[str, Any]:
        out = copy.deepcopy(ir)
        out["ir_schema_version"] = to_version
        return out
    return migrate


def _ib_0_3_to_0_4(ir: dict[str, Any]) -> dict[str, Any]:
    out = _map_status(ir, "implementation_brief", "0.4.0")
    out.pop("review_grandfathered", None)
    # Every IB persisted before ADR-055 was authored under ADR-049.
    out.setdefault("authority_policy", "legacy")
    return out


def _intent_0_3_to_0_4(ir: dict[str, Any]) -> dict[str, Any]:
    out = _map_status(ir, "intent", "0.4.0")
    out.pop("beads_before_accept", None)
    return out


_STEPS: tuple[tuple[str, str, str, Any, str], ...] = (
    ("implementation_brief", "0.2.0", "0.3.0", _identity("0.3.0"), "INT-102 additive review fields (chain gap)"),
    ("implementation_brief", "0.3.0", "0.4.0", _ib_0_3_to_0_4, "ADR-055/057: decision-only status, authority policy"),
    ("intent", "0.2.0", "0.3.0", _identity("0.3.0"), "INT-104 additive field (chain gap)"),
    ("intent", "0.3.0", "0.4.0", _intent_0_3_to_0_4, "ADR-056/057: decision-only status, beads retired"),
    ("mission", "0.2.0", "0.3.0", lambda ir: _map_status(ir, "mission", "0.3.0"), "ADR-057: TODO→PROPOSED, COMPLETING retired"),
    ("adr", "0.2.0", "0.3.0", lambda ir: _map_status(ir, "adr", "0.3.0"), "ADR-057: TODO retired"),
    ("architecture_element", "0.2.0", "0.3.0", lambda ir: _map_status(ir, "architecture_element", "0.3.0"), "ADR-057: TODO retired"),
    ("working_spec", "0.2.0", "0.3.0", lambda ir: _map_status(ir, "working_spec", "0.3.0"), "ADR-057: TODO retired"),
    ("interface_contract", "0.2.0", "0.3.0", lambda ir: _map_status(ir, "interface_contract", "0.3.0"), "ADR-057: TODO retired"),
    ("system_vision", "0.1.0", "0.2.0", lambda ir: _map_status(ir, "system_vision", "0.2.0"), "ADR-057: TODO retired"),
    ("constitution", "0.1.0", "0.2.0", lambda ir: _map_status(ir, "constitution", "0.2.0"), "ADR-057: TODO retired"),
)

for _kind, _from, _to, _fn, _desc in _STEPS:
    default_registry.register(Migration(artifact_type=_kind, from_version=_from, to_version=_to,
                                        migrate=_fn, description=_desc))
