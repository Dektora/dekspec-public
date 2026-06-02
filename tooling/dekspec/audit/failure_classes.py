"""`dekspec audit failure-classes` aggregator (INT-126 / ds-99ko).

Read-only walk over the bead corpus (`.beads/issues.jsonl`), grouping
beads carrying a `failure-class:<class>` label and producing a markdown
or JSON report. Cross-references each bead's `external_ref` so the
post-mortem ritual (engineer → class label → aggregator → §Class Lanes
amendment per INT-125) can trace bead → Intent → IB → revert SHA.

No system-writes; surfaces trend evidence so the engineer can drive
class-lane decisions per INT-125's `--amend --editorial` path.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


_FAILURE_CLASS_PREFIX = "failure-class:"


@dataclass
class BeadRow:
    """Per-bead row surfaced in the report."""

    id: str
    failure_class: str | None
    bead_type: str | None
    updated_at: str | None
    external_ref: str | None
    revert_sha: str | None = None


@dataclass
class Group:
    """Aggregated group — `by` axis value + the beads in it."""

    key: str
    count: int
    beads: list[BeadRow] = field(default_factory=list)


@dataclass
class Aggregate:
    """The aggregator's return shape — what `format_report` formats."""

    by: str
    window_days: int
    total_beads: int
    groups: list[Group]


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------
def aggregate(
    repo_root: Path | str,
    by: str = "class",
    window_days: int = 90,
    detect_reverts: bool = False,
) -> Aggregate:
    """Walk `<repo_root>/.beads/issues.jsonl` and aggregate per
    `by ∈ {class, type, risk-tier}` within the `window_days` window
    (default 90).

    `detect_reverts` is opt-in because it shells out to `git log` and
    can be slow; the CLI verb passes it through. Tests run with the
    default `False` and assert revert detection through the `revert_sha`
    field stays `None`.
    """
    repo_root = Path(repo_root)
    rows = list(_load_beads(repo_root, window_days))
    if by == "class":
        groups = _group_by(rows, key=lambda r: r.failure_class)
    elif by == "type":
        groups = _group_by(rows, key=lambda r: r.bead_type)
    elif by == "risk-tier":
        groups = _group_by(rows, key=lambda r: _risk_tier_for(repo_root, r))
    else:
        raise ValueError(f"Unknown --by axis: {by!r}.")
    if detect_reverts:
        _attach_revert_shas(repo_root, rows)
    return Aggregate(
        by=by,
        window_days=window_days,
        total_beads=len(rows),
        groups=groups,
    )


def format_report(agg: Aggregate, fmt: str = "md") -> str:
    """Render the aggregate to markdown (default) or JSON."""
    if fmt == "json":
        return json.dumps({
            "by": agg.by,
            "window_days": agg.window_days,
            "total_beads": agg.total_beads,
            "groups": [
                {
                    "key": g.key,
                    "count": g.count,
                    "beads": [
                        {
                            "id": b.id,
                            "external_ref": b.external_ref,
                            "type": b.bead_type,
                            "updated_at": b.updated_at,
                            "revert_sha": b.revert_sha,
                        }
                        for b in g.beads
                    ],
                }
                for g in agg.groups
            ],
        }, indent=2)
    if fmt != "md":
        raise ValueError(f"Unknown --format: {fmt!r}.")
    out: list[str] = []
    out.append("# Failure-class aggregator")
    out.append("")
    out.append(
        f"By **{agg.by}** over the last {agg.window_days} days · "
        f"{agg.total_beads} bead(s) scanned · "
        f"{len(agg.groups)} group(s)."
    )
    out.append("")
    if not agg.groups:
        out.append("_No beads in window carry a `failure-class:*` label._")
        return "\n".join(out)
    for g in agg.groups:
        out.append(f"## {g.key} ({g.count} bead{'s' if g.count != 1 else ''})")
        out.append("")
        out.append("| Bead | Type | External Ref | Revert SHA |")
        out.append("|---|---|---|---|")
        for b in g.beads:
            out.append(
                f"| `{b.id}` | {b.bead_type or '-'} | "
                f"{b.external_ref or '-'} | {b.revert_sha or '-'} |"
            )
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _load_beads(repo_root: Path, window_days: int) -> Iterable[BeadRow]:
    """Yield BeadRow per bead in `.beads/issues.jsonl` within the
    update window."""
    path = repo_root / ".beads" / "issues.jsonl"
    if not path.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            updated_raw = rec.get("updated_at") or rec.get("updated")
            if not _within_window(updated_raw, cutoff):
                continue
            failure_class = _extract_failure_class(rec.get("labels") or [])
            if failure_class is None:
                continue  # only beads with the label surface
            yield BeadRow(
                id=str(rec.get("id") or "<unknown>"),
                failure_class=failure_class,
                bead_type=rec.get("type"),
                updated_at=updated_raw,
                external_ref=rec.get("external_ref"),
            )


def _within_window(ts: str | None, cutoff: datetime) -> bool:
    if not ts:
        return True  # tolerate missing timestamps
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed >= cutoff
    except ValueError:
        return True


def _extract_failure_class(labels: list[Any]) -> str | None:
    for lbl in labels:
        s = str(lbl)
        if s.startswith(_FAILURE_CLASS_PREFIX):
            return s[len(_FAILURE_CLASS_PREFIX):]
    return None


def _group_by(rows: list[BeadRow], key) -> list[Group]:
    bucket: dict[str, list[BeadRow]] = {}
    for r in rows:
        k = key(r) or "<unknown>"
        bucket.setdefault(k, []).append(r)
    groups = [Group(key=k, count=len(v), beads=v) for k, v in bucket.items()]
    groups.sort(key=lambda g: (-g.count, g.key))
    return groups


def _risk_tier_for(repo_root: Path, row: BeadRow) -> str | None:
    """Resolve the risk_tier for a bead via its external_ref → Intent →
    Constitution §Class Lanes lookup (INT-125 substrate).

    Best-effort: returns None when the chain can't be traversed; the
    caller groups Nones under `<unknown>`.
    """
    if not row.external_ref:
        return None
    # external_ref looks like `dekspec/intents/INT-NNN-slug.md[:IU-N]`.
    head = row.external_ref.split(":")[0]
    intent_path = repo_root / head
    if not intent_path.exists():
        return None
    body = intent_path.read_text(errors="ignore")
    match = re.search(r"^\s*Risk Tier\s*:\s*(.+)$", body, re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Alternative shape: `## Risk Tier\n\n<value>`
    match = re.search(r"^##\s+Risk Tier\s*\n+(\S[^\n]*)", body, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def _attach_revert_shas(repo_root: Path, rows: list[BeadRow]) -> None:
    """Best-effort `git log --grep=<bead-id>` to look up revert SHAs.

    Read-only; populates `row.revert_sha` in place when a match exists.
    """
    for r in rows:
        try:
            proc = subprocess.run(
                ["git", "log", "--grep", r.id, "--grep", "Revert", "--all",
                 "--pretty=%H", "-1"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            sha = (proc.stdout or "").strip().split("\n")[0]
            if sha and len(sha) >= 8:
                r.revert_sha = sha[:12]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
