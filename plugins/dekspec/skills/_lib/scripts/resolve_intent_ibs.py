#!/usr/bin/env python3
"""Resolve child Implementation Briefs for one or more Intents.

This script parses a list of Intent IDs, loads the SpecGraph, matches each
Intent to its child Implementation Briefs (IBs), and extracts their status
and absolute/relative paths.

It prints a JSON block to stdout containing the resolved mappings, statuses,
and any validation errors or warnings.

Usage:
    python resolve_intent_ibs.py <INTENT-ID> [<INTENT-ID> ...] [--at REPO-ROOT]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dekspec.constraint_compiler.graph import SpecGraph


def _find_repo_root(start: Path | None = None) -> Path:
    """Walk upward from start (or CWD) until a `dekspec` directory is found."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "dekspec").is_dir():
            return candidate
    return cur


def resolve_intent_ibs(
    intent_ids: list[str], repo_root: Path
) -> dict[str, Any]:
    """Load the SpecGraph and find all child IBs for each target Intent ID.

    Returns a structured dictionary mapping each target intent to its
    details and child IBs.
    """
    graph = SpecGraph.load(repo_root)

    # Pre-index intents in SpecGraph
    existing_intents = {
        intent["id"].upper(): intent for intent in graph.intents()
    }

    # Group IBs by their parent Intent ID
    ibs_by_intent: dict[str, list[dict[str, Any]]] = {}
    for ib in graph.ibs():
        intent_block = ib.get("intent")
        if not isinstance(intent_block, dict):
            continue
        par_id = intent_block.get("id")
        if not par_id or not isinstance(par_id, str):
            continue
        par_id_upper = par_id.strip().upper()
        ibs_by_intent.setdefault(par_id_upper, []).append(ib)

    resolved: dict[str, Any] = {}
    all_locked = True
    any_found = False

    for raw_id in intent_ids:
        intent_id = raw_id.strip().upper()
        intent_ir = existing_intents.get(intent_id)

        intent_entry: dict[str, Any] = {
            "exists": intent_ir is not None,
            "status": intent_ir["status"] if intent_ir else None,
            "path": intent_ir["source"]["path"] if intent_ir else None,
            "ibs": [],
            "warnings": [],
        }

        if not intent_entry["exists"]:
            intent_entry["warnings"].append(f"Intent {intent_id} not found in the spec graph")
        else:
            any_found = True

        child_ibs = ibs_by_intent.get(intent_id, [])
        for ib in sorted(child_ibs, key=lambda x: x["id"]):
            ib_id = ib["id"]
            ib_status = ib["status"].upper()
            ib_path = Path(ib["source"]["path"])
            
            try:
                rel_path = str(ib_path.relative_to(repo_root))
            except ValueError:
                rel_path = str(ib_path)

            is_locked = ib_status == "LOCKED"
            if not is_locked:
                all_locked = False

            intent_entry["ibs"].append({
                "id": ib_id,
                "status": ib_status,
                "path": str(ib_path),
                "relative_path": rel_path,
                "is_locked": is_locked,
            })

        if intent_entry["exists"] and not intent_entry["ibs"]:
            intent_entry["warnings"].append(f"Intent {intent_id} has no child Implementation Briefs")

        resolved[intent_id] = intent_entry

    any_ibs = any(len(intent_entry["ibs"]) > 0 for intent_entry in resolved.values())

    return {
        "success": any_found and all_locked and any_ibs,
        "all_locked": all_locked,
        "any_found": any_found,
        "resolved": resolved,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "intent_ids",
        nargs="+",
        help="One or more Intent IDs (e.g. INT-001 INT-002)",
    )
    parser.add_argument(
        "--at",
        default=None,
        help="Path to repository root (defaults to auto-discovered root)",
    )

    args = parser.parse_args(argv)
    
    start_path = Path(args.at) if args.at else None
    repo_root = _find_repo_root(start_path)

    try:
        res = resolve_intent_ibs(args.intent_ids, repo_root)
        print(json.dumps(res, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e), "success": False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
