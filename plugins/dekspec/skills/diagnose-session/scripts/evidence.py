#!/usr/bin/env python3
"""Read-only facts about a target repository; no diagnosis is inferred here."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_lib" / "scripts"))
from evidence_common import emit, git, identity  # noqa: E402


def execution_records(root, full=False):
    """What each DekSpec execution record (IB, Intent, `/implement` run) says
    happened last — read from the JSONL, so no engine is required."""
    out = []
    records = sorted((root / ".dekspec" / "execution").glob("*/record.jsonl"))
    for path in records if full else records[:20]:
        events = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                events.append({"type": "unparseable"})
        types = [e.get("type") for e in events]
        last = events[-1] if events else {}
        opened = sum(t == "attempt.started" for t in types) - sum(t == "attempt.ended" for t in types)
        completed, live = False, {}
        for e in events:
            kind, data = e.get("type"), e.get("data") or {}
            if kind == "completion.recorded":
                completed = True
            elif kind == "completion.reopened":
                completed = False  # a reopened completion no longer counts
            elif kind in ("blocker.raised", "blocker.recorded"):
                live[data.get("key") or data.get("reason") or len(live)] = True
            elif kind == "blocker.cleared":
                live.pop(data.get("key"), None)
            elif kind == "blocker.resolved":
                live.clear()  # an IB's unblock resolves its blockers
        out.append({"id": path.parent.name, "events": len(events), "last": last.get("type"),
                    "last_at": last.get("ts"), "last_actor": last.get("actor"),
                    "open_attempts": max(opened, 0), "live_blockers": len(live), "completed": completed})
    return out


def collect(repo, full=False):
    target = identity(repo)
    root = Path(target["repo"])
    records = execution_records(root, full)
    return {"identity": target,
            "execution_records": records,
            "execution_hint": ("inspect with `dekspec ib status <IB>`, `dekspec implement status <request>`"
                               if records else "no DekSpec execution records"),
            "status": git(root, "status", "--short").stdout.decode().splitlines(),
            "commits": git(root, "log", f"-{100 if full else 10}", "--format=%h %aI %s").stdout.decode().splitlines(),
            "worktrees": git(root, "worktree", "list", "--porcelain").stdout.decode().splitlines(),
            "workspace_candidates": [str(p.relative_to(root)) for p in sorted(root.glob("**/.beads/beads.db")) if ".git" not in p.parts],
            "config_present": (root / ".dekspec/config.yaml").is_file(),
            "session_metadata": "unassessed: no session log supplied",
            "hypotheses": [], "help": "Provide session logs for causal diagnosis; repeated commits alone prove no loop."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", default=".")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    try:
        emit(collect(Path(args.at), args.full), args.full)
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {json.dumps(str(exc))}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
