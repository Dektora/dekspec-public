"""Read-only CI classification of protected acceptance tests (IB-234)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dekspec.execution.contract import ContractError, load_contract

_PENDING = {"DRAFT", "PROPOSED", "ACCEPTED"}
_STATUSES = _PENDING | {"COMPLETE", "SUPERSEDED", "DEPRECATED"}


def _covers(entry: dict, node: str) -> bool:
    identifier = entry["id"]
    return (identifier == node
            or entry["kind"] == "file" and identifier == node.split("::", 1)[0]
            or node.startswith(identifier + "[")
            or node.startswith(identifier + "::"))


def _test_module(repo_root: Path, asset: str) -> bool:
    path = Path(asset)
    return (not any(char in asset for char in "*?[]{}")
            and not asset.endswith("/") and not (repo_root / path).is_dir()
            and "fixtures" not in path.parts
            and path.name.startswith("test_") and path.suffix == ".py")


def _collect_entries(repo_root: Path, spec_root: str) -> dict:
    """Resolve contract ownership into root-local entries before classification.

    Only explicit relocation records may repair a missing path. Brief
    attribution records direct ownership, not inherited COMPLETE coverage.
    """
    repo_root = repo_root.resolve()
    roots = ["."] + sorted(
        p.parent.relative_to(repo_root).as_posix()
        for p in (repo_root / "products").glob("*/tests") if p.is_dir()
    )
    moves = {}
    for path in sorted((repo_root / "products").glob("*/relocation.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        for key in ("tests", "test_files"):
            for move in record.get(key, []):
                moves[move["source"]] = move["destination"]

    entries: dict[str | None, dict[str, dict]] = {root: {} for root in roots}
    entries[None] = {}
    for path in sorted((repo_root / spec_root / "impl-briefs").rglob("IB-*.md")):
        try:
            contract = load_contract(repo_root, str(path), spec_root=spec_root)
        except (ContractError, UnicodeError, OSError) as error:
            raise ContractError(f"{path}: {error}") from error
        if not contract.is_delegated:
            continue
        if contract.status not in _STATUSES:
            raise ContractError(f"{path}: unknown status {contract.status!r}")
        nodes = {node for condition in contract.acceptance for node in condition.nodes}
        nodes.update(asset for asset in contract.declared_assets if _test_module(repo_root, asset))
        for node in sorted(nodes):
            filename, separator, suffix = node.partition("::")
            if not (repo_root / filename).exists():
                filename = moves.get(filename, filename)
            file_path = Path(filename)
            if file_path.is_absolute():
                filename = file_path.relative_to(repo_root).as_posix()
            else:
                filename = file_path.as_posix()
            root = next((root for root in roots if filename.startswith(
                "tests/" if root == "." else root + "/tests/")), None)
            relative = filename if root in (None, ".") else filename[len(root) + 1:]
            identifier = relative + separator + suffix
            entry = entries[root].setdefault(identifier, {
                "id": identifier, "kind": "node" if separator else "file", "briefs": set(),
            })
            entry["briefs"].add((contract.ib_id, contract.status))

    return entries


def compute_plan(repo_root: Path, spec_root: str = "dekspec") -> dict:
    """Compute the complete read-only plan, with COMPLETE coverage per root.

    An identically named test in another product protects nothing here.
    All source reading succeeds before any output can be emitted.
    """
    entries = _collect_entries(repo_root, spec_root)

    def serialized(entry: dict) -> dict:
        return {**entry, "briefs": [{"id": ib, "status": status}
                                   for ib, status in sorted(entry["briefs"])]}

    plan = {"format": "dekspec-ci-acceptance-plan", "version": 1, "roots": [],
            "outside": [serialized(e) for _, e in sorted(entries[None].items())]}
    for root, owned in entries.items():
        if root is None:
            continue
        completed = [e for e in owned.values()
                     if any(status == "COMPLETE" for _, status in e["briefs"])]
        item = {"root": root, "required": [], "expected_red": []}
        for identifier, entry in sorted(owned.items()):
            pending = any(status in _PENDING for _, status in entry["briefs"])
            required = any(_covers(e, identifier) for e in completed)
            key = "expected_red" if pending and not required else "required"
            item[key].append(serialized(entry))
        plan["roots"].append(item)
    plan["counts"] = {
        key: sum(len(item[key]) for item in plan["roots"])
        for key in ("required", "expected_red")
    }
    plan["counts"]["outside"] = len(plan["outside"])
    return plan


def render_text(plan: dict) -> str:
    """Report counts and every entry CI may set aside, with its authority."""
    lines = []

    def entry_line(root: str, entry: dict) -> str:
        briefs = ", ".join(f"{b['id']} ({b['status']})" for b in entry["briefs"])
        return f"{root}: {entry['id']} — {briefs}"

    for item in plan["roots"]:
        lines.append(f"{item['root']}: {len(item['required'])} required, "
                     f"{len(item['expected_red'])} expected-red")
        lines.extend(entry_line(item["root"], entry) for entry in item["expected_red"])
    lines.extend(entry_line("outside", entry) for entry in plan["outside"])
    counts = plan["counts"]
    lines.append(f"{counts['expected_red']} expected-red entries, "
                 f"{counts['required']} required, {counts['outside']} outside every test root")
    return "\n".join(lines)


def register(sub: argparse._SubParsersAction) -> None:
    """Register the `ci` command group and its `acceptance-plan` subcommand."""
    ci = sub.add_parser("ci", help="Continuous-integration helpers.")
    ci_sub = ci.add_subparsers(dest="ci_command", metavar="<ci-command>")
    plan = ci_sub.add_parser(
        "acceptance-plan",
        help="Split protected acceptance tests into required and expected-red, per test root.",
    )
    plan.add_argument("--at", help="repository root (default: the current directory)")
    plan.add_argument("--dekspec-root", default="dekspec",
                      help="spec tree relative to the repo (default: dekspec)")
    plan.add_argument("--json", action="store_true", help="machine-readable output")
    plan.set_defaults(func=cmd_acceptance_plan)
    ci.set_defaults(func=lambda _args: (ci.print_help() or 0))


def cmd_acceptance_plan(args: argparse.Namespace) -> int:
    repo_root = Path(args.at or ".")
    if not repo_root.is_dir():
        print(f"error: --at is not a folder: {repo_root}", file=sys.stderr)
        return 2
    try:
        plan = compute_plan(repo_root, args.dekspec_root)
    except (ContractError, UnicodeError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(plan) if args.json else render_text(plan))
    return 0
