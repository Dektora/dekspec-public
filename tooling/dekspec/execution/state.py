"""Derive current execution state by folding the record's events.

There is no stored status to keep in sync: ownership, the current plan and
tasks, attempt counts, active blockers, the latest baseline, evidence,
verdicts and completion are all recomputed from the append-only log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from dekspec.execution.record import Event

__all__ = ["Attempt", "RunState", "fold", "parse_ts"]


def parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class Attempt:
    number: int
    actor: str
    started: str
    task: str | None = None
    last_seen: str | None = None
    ended: str | None = None
    outcome: str | None = None  # passed | failed | error | stalled | abandoned
    failure_class: str | None = None
    progress: dict[str, Any] = field(default_factory=dict)

    @property
    def open(self) -> bool:
        return self.ended is None


@dataclass
class RunState:
    started: bool = False
    owner: str | None = None
    actors: set[str] = field(default_factory=set)
    #: Everyone who built: every owner the run ever had, plan committers,
    #: task actors and attempt actors. None of them may
    #: review or authorize an amendment of this IB (ADR-057).
    builders: set[str] = field(default_factory=set)
    context: dict[str, Any] | None = None
    baseline: dict[str, Any] | None = None
    baseline_seq: int | None = None
    pre_execution_baseline: dict[str, Any] | None = None
    amendments: list[dict[str, Any]] = field(default_factory=list)
    findings: dict[str, Any] | None = None
    plan_revision: int = 0
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    attempts: list[Attempt] = field(default_factory=list)
    extra_attempts: int = 0
    blockers: list[dict[str, Any]] = field(default_factory=list)
    deviations: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    verdicts: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    #: Current completions: a ``completion.reopened`` event clears them (the
    #: record keeps every completion; ``reopenings`` lists the reopenings).
    completions: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    reopenings: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    legacy: list[dict[str, Any]] = field(default_factory=list)
    prerequisites: dict[str, Any] | None = None

    @property
    def open_attempt(self) -> Attempt | None:
        return next((a for a in reversed(self.attempts) if a.open), None)

    @property
    def attempts_used(self) -> int:
        return len(self.attempts)

    @property
    def active_blockers(self) -> list[dict[str, Any]]:
        return list(self.blockers)

    def latest_evidence(self, kind: str = "ib") -> tuple[int, dict[str, Any]] | None:
        for seq, ev in reversed(self.evidence):
            if ev.get("kind", "ib") == kind:
                return seq, ev
        return None

    @property
    def builder_identities(self) -> set[str]:
        ids = set(self.builders) | {a.actor for a in self.attempts if a.actor != "dekspec"}
        if self.owner:
            ids.add(self.owner)
        return ids

    def phase(self) -> str:
        if self.completions:
            return "complete"
        if self.blockers:
            return "blocked"
        if self.started:
            return "active"
        return "not-started"


def fold(events: list[Event]) -> RunState:
    st = RunState()
    for ev in events:
        d = ev.data
        st.actors.add(ev.actor)
        t = ev.type
        if t in ("run.started", "run.resumed", "run.ownership-transferred", "plan.committed",
                 "task.updated", "attempt.started", "attempt.heartbeat"):
            if ev.actor != "dekspec":
                st.builders.add(ev.actor)
        if t == "run.started":
            st.started = True
            st.owner = d.get("owner") or ev.actor
            st.builders.add(st.owner)
        elif t == "run.ownership-transferred":
            if d.get("from"):
                st.builders.add(d["from"])
            st.owner = d.get("to")
            if st.owner:
                st.builders.add(st.owner)
        elif t == "context.bound":
            st.context = d
        elif t == "prerequisites.checked":
            st.prerequisites = d
        elif t in ("acceptance.baselined", "acceptance.amended"):
            st.baseline = d
            st.baseline_seq = ev.seq
            # The pre-execution baseline anchors scope attribution; a baseline
            # taken after the run started never replaces it.
            if t == "acceptance.baselined" and (st.pre_execution_baseline is None or not st.started):
                st.pre_execution_baseline = d
            if t == "acceptance.amended":
                st.amendments.append({"seq": ev.seq, **d})
        elif t == "plan.committed":
            st.plan_revision = d.get("revision", st.plan_revision + 1)
            if d.get("findings"):
                st.findings = d["findings"]
            previous = st.tasks
            st.tasks = {}
            for task in d.get("tasks", []):
                prior = previous.get(task["id"], {})
                merged = {**task, "status": prior.get("status", "pending"),
                          "owner": prior.get("owner"), "evidence": prior.get("evidence", [])}
                st.tasks[task["id"]] = merged
            # Completed tasks cannot vanish — plan validation refuses that —
            # but a record written by another tool is folded defensively.
            for tid, prior in previous.items():
                if tid not in st.tasks and prior.get("status") == "done":
                    st.tasks[tid] = prior
        elif t == "task.updated":
            task = st.tasks.setdefault(d["task"], {"id": d["task"], "status": "pending"})
            if "status" in d:
                task["status"] = d["status"]
            if "owner" in d:
                task["owner"] = d["owner"]
            if d.get("evidence"):
                task.setdefault("evidence", []).append(d["evidence"])
        elif t == "attempt.started":
            st.attempts.append(Attempt(number=d["attempt"], actor=ev.actor, started=ev.ts,
                                       task=d.get("task"), last_seen=ev.ts))
        elif t == "attempt.heartbeat":
            att = st.open_attempt
            if att and att.number == d.get("attempt", att.number):
                att.last_seen = ev.ts
        elif t == "attempt.ended":
            for att in reversed(st.attempts):
                if att.number == d.get("attempt") and att.open:
                    att.ended = ev.ts
                    att.outcome = d.get("outcome")
                    att.failure_class = d.get("failure_class")
                    att.progress = d.get("progress") or {}
                    break
        elif t == "blocker.raised":
            st.blockers.append({"seq": ev.seq, "raised_by": ev.actor, **d})
        elif t == "blocker.resolved":
            st.blockers = []
            st.extra_attempts += int(d.get("extra_attempts") or 0)
        elif t == "deviation.recorded":
            st.deviations.append({"seq": ev.seq, **d})
        elif t == "evidence.recorded":
            st.evidence.append((ev.seq, d))
        elif t == "verdict.recorded":
            st.verdicts.append((ev.seq, {**d, "reviewer": d.get("reviewer") or ev.actor}))
        elif t == "completion.recorded":
            st.completions.append((ev.seq, d))
        elif t == "completion.reopened":
            st.reopenings.append((ev.seq, d))
            st.completions = []
        elif t.startswith("legacy."):
            st.legacy.append({"type": t, **d})
    return st
