"""File ended-loop findings through br, publishing one complete issue export.

All command effects stay in a disposable store until every finding has an id.
A failed filing leaves the project's export unchanged and raises ExecutionError.
The ordinary br import reconciles its local database with the published export.
"""
from __future__ import annotations

import fcntl as _fcntl
import json as _json
import os as _os
import shutil as _shutil
import tempfile as _tempfile
from pathlib import Path as _Path

from dekspec import beads as _beads
from dekspec.execution.engine import ExecutionError as _ExecutionError
from dekspec.execution.lean_records import _history


def _file_follow_ups(engine, ib):
    events = engine.record(ib).events()
    history = _history(events)
    findings = [dict(loop=name, level=f.level, text=f.text)
                for name, loop in (("floor", history.floor_loop), ("code", history.code_loop))
                if loop.disposition == "ended" for f in loop.findings]
    if not findings:
        return []
    # Reconstruct loop identity at each earlier completion, including records
    # written before this repair. IDs come only from the execution record;
    # identical finding text in a new loop must still produce a new issue.
    filed = {}
    for index, event in enumerate(events):
        if event.type != "completion.recorded" or not event.data.get("known_issues"):
            continue
        earlier = _history(events[:index])
        for finding in event.data["known_issues"]:
            name = finding["loop"]
            start = getattr(earlier, f"_{name}_loop_start")
            filed[(name, start, finding["level"], finding["text"])] = finding["follow_up"]
    pending = []
    for finding in findings:
        name = finding["loop"]
        key = (name, getattr(history, f"_{name}_loop_start"), finding["level"], finding["text"])
        if key in filed:
            finding["follow_up"] = filed[key]
        else:
            pending.append(finding)
    if not pending:
        return findings
    root = engine.repo_root
    try:
        store = _beads._safe_relative(root, ".beads-issues/.beads")
        if not store.is_dir():
            raise _beads.BeadsError("project issue workspace .beads-issues is missing")
        prefix = _beads.store_prefix(store, "iss", _beads.configured_project(root))
        for source in store.rglob("*"):
            _beads._safe_relative(root, str(source.relative_to(root)))
        lock = _beads._safe_relative(root, ".beads-issues/.beads/.follow-ups.lock")
        with lock.open("a") as handle, _tempfile.TemporaryDirectory(prefix="dekspec-follow-ups-") as tmp:
            _fcntl.flock(handle, _fcntl.LOCK_EX)
            export = store / "issues.jsonl"
            before = export.read_bytes() if export.exists() else None
            staged = _Path(tmp) / ".beads"
            _shutil.copytree(store, staged)
            for finding in pending:
                title = f"{ib} {finding['loop']} review: {finding['text']}"
                # JSONL mode is br's supported import/export boundary, also used
                # when a checkout has no local database. Never hand-write issues.
                result = _beads._run(staged, "create", "--title", title[:200], "--type", "bug",
                                     "--priority", finding["level"], "--description", title,
                                     "--json", "--no-db")
                row = _json.loads(result.stdout)
                ident = row.get("id") if isinstance(row, dict) else None
                if not isinstance(ident, str) or not ident.startswith(prefix + "-"):
                    raise _beads.BeadsError("issue command did not return an id in the project issue workspace")
                finding["follow_up"] = ident
            exported = {row["id"] for row in _beads.read_rows(staged / "issues.jsonl")}
            if any(f["follow_up"] not in exported for f in pending):
                raise _beads.BeadsError("issue command did not export every follow-up")
            if _beads.probe(store).get("dirty_count") != 0:
                raise _beads.BeadsError("issue workspace has unexported changes; flush it before completion")
            if (export.read_bytes() if export.exists() else None) != before:
                raise _beads.BeadsError("issue export changed during filing; retry completion")
            # Same-filesystem replacement publishes all findings at once. A
            # failed create/probe/replace never exposes a partially filed batch.
            temp = None
            try:
                with _tempfile.NamedTemporaryFile(dir=store, prefix=".follow-up-", delete=False) as stream:
                    temp = _Path(stream.name)
                    stream.write((staged / "issues.jsonl").read_bytes())
                _os.replace(temp, export)
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)
    except (_beads.BeadsError, OSError, ValueError) as exc:
        raise _ExecutionError(f"issue filing failed: {exc}") from exc
    return findings
