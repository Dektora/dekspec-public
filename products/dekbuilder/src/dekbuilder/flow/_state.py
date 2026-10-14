"""Read-only interpretation of a wave's contracts, deliveries and stage history."""

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from dekspec import builder_compat as _spec

from dekbuilder.implement.config import load_integration
from dekbuilder.implement.driver import DriverError, status as driver_status
from dekbuilder.implement.readiness import assess, authoritative_base
from dekbuilder.implement.targets import resolve

_STAGES = (
    "ready", "started", "tests-authored", "floor-passed", "own-tests-passed",
    "reviewed", "completed", "queued", "checks-registered", "checks-passed", "merged",
)
# BS-046 Data Interfaces. Unknown kinds deliberately keep the ruling-wait default.
_CAUSES = {
    "setup": {
        "base-unavailable", "prerequisite-unavailable", "cannot-start", "setup-failed",
        "push-failed", "integration-blocked", "checks-requirement-unreadable",
        "environment-unavailable", "delivery-copy-unavailable",
    },
    "spec-gap": {
        "not-ready", "contract-conflict", "acceptance-invalid", "interface-not-returned",
        "completion-refused", "outcome-failed",
    },
    "timeout": {
        "dispatch-lost", "attempts-exhausted", "no-progress", "stalled", "no-convergence",
        "review-not-converging", "review-not-recorded", "checks-not-converging",
    },
    "collision": {"scope-expansion", "integration-failed", "landing-gate"},
    "ruling-wait": {"required-checks-failed", "cannot-reopen", "other"},
}
_REPAIR_KINDS = {
    "floor-failed", "review-failed", "guard-refusal", "interface-return",
    "conflict", "base-touched", "candidate-failed",
}


def _git(root, *args):
    """Observe git without optional index refresh writes."""
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
    )


def _queue(root):
    """Ask the storage owner at call time; status never repairs its state."""
    from dekbuilder.implement import landing_queue

    base, _ = authoritative_base(root, load_integration(root))
    return list(landing_queue.LandingQueue(root, base).read())


def _stop(kind, detail):
    cause = next((c for c, kinds in _CAUSES.items() if kind in kinds), "ruling-wait")
    return {"cause": cause, "kind": kind, "detail": detail}


def _last(events, kind):
    return next((e for e in reversed(events) if e.type == kind), None)


def _time(event):
    return event.ts if event else None


def _instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class _Wave:
    """A request snapshot; discovery and record locations stay inside this module."""

    def __init__(self, root, request):
        self.root = Path(root)
        self.settings = load_integration(self.root)
        self.base_name, self.base = authoritative_base(self.root, self.settings)
        self.engine = _spec.Engine(self.root, base=self.base)
        resolution = resolve(self.root, request)
        if not resolution.ok:
            raise DriverError("; ".join(p["detail"] for p in resolution.problems))
        self.contracts = {}
        self.order = {}
        for position, target in enumerate(resolution.targets):
            children = (_spec.intent_children(self.engine, target.id) if target.kind == "intent"
                        else [self.engine.contract(target.id)])
            for contract in children:
                if contract.ib_id not in self.contracts:
                    self.contracts[contract.ib_id] = contract
                    self.order[contract.ib_id] = position
        self.paths = {}
        path = None
        for line in _git(self.root, "worktree", "list", "--porcelain").stdout.splitlines():
            if line.startswith("worktree "):
                path = Path(line[9:])
            elif line.startswith("branch refs/heads/"):
                self.paths[line[18:]] = path
        self.branches = set(_git(
            self.root, "for-each-ref", "--format=%(refname:short)", "refs/heads/implement/",
        ).stdout.splitlines())
        self._briefs = {}

    def brief(self, ident):
        if ident not in self._briefs:
            branch = f"implement/{ident.lower()}"
            path = self.paths.get(branch, self.root)
            self._briefs[ident] = _Brief(self, ident, branch, path)
        return self._briefs[ident]

    def integrated(self, ident):
        try:
            brief = self.brief(ident)
        except _spec.ExecutionError:
            return False  # Missing dependency authority cannot admit a start.
        return (brief.engine.is_complete(ident, base=self.base)
                and brief.engine.integration_state(
                    ident, brief.contract.rel_path, self.base)[0] == "integrated")

    def ready(self, ident):
        contract = self.contracts[ident]
        if not all(self.integrated(dep) for dep in contract.depends_on):
            return False
        return assess(self.root, resolve(self.root, ident).targets).ready

    def candidates(self):
        # Traverse through finished nodes too, but only unfinished request members
        # contribute weight. Sets prevent diamonds (or cycles) counting twice.
        reverse = {}
        pending = list(self.contracts)
        seen = set()
        while pending:
            ident = pending.pop()
            if ident in seen:
                continue
            seen.add(ident)
            try:
                contract = self.brief(ident).contract
            except _spec.ExecutionError:
                continue  # Readiness reports the missing dependency to its caller.
            for dep in contract.depends_on:
                reverse.setdefault(dep, set()).add(ident)
                pending.append(dep)
        unfinished = {ib for ib in self.contracts if not self.integrated(ib)}

        def weight(ident):
            reached, todo = set(), list(reverse.get(ident, ()))
            while todo:
                child = todo.pop()
                if child in reached or child == ident:
                    continue
                reached.add(child)
                todo.extend(reverse.get(child, ()))
            return len(reached & unfinished)

        return sorted(self.contracts, key=lambda ib: (-weight(ib), self.order[ib], ib))


class _Brief:
    """One brief's observable history, shared by capacity and status projection."""

    def __init__(self, wave, ident, branch, path):
        self.wave, self.ident, self.branch, self.path = wave, ident, branch, path
        self.exists = branch in wave.branches
        self.engine = _spec.Engine(path, base=wave.base)
        self.contract = self.engine.contract(ident)
        self.events = self.engine.record(ident).events()
        self.state = _spec.fold(self.events)
        self.run = self.engine.record(f"RUN-{ident}").events() if self.exists else []
        self.blockers = {}
        self.queued = False
        self.latest_dispatch = None
        self.lost = set()
        for event in self.run:
            data = event.data
            if event.type == "blocker.recorded":
                self.blockers[data["key"]] = data
            elif event.type == "blocker.cleared":
                self.blockers.pop(data["key"], None)
            elif event.type in ("queue.joined", "queue.left") and data.get("brief") == ident:
                self.queued = event.type == "queue.joined"
            elif event.type == "dispatch.issued":
                self.latest_dispatch = data["id"]
            elif event.type == "dispatch.lost":
                self.lost.add(data["id"])
        self.merged = _time(_last(self.run, "run.integrated"))

    @property
    def landed(self):
        # The uncommitted run.integrated event may disappear with its worktree.
        # While that worktree exists, its run decides, including a pending push.
        return bool(self.merged) or (
            self.branch not in self.wave.paths and self.wave.integrated(self.ident)
        )

    def stop(self):
        if self.landed:
            return None
        if self.blockers:
            blocker = list(self.blockers.values())[-1]
            return _stop(blocker["kind"], blocker.get("detail", ""))
        blockers = [b for b in self.state.active_blockers if not (
            self.contract.is_lean and b.get("reason") == "acceptance-invalid"
            and b.get("detail", "").startswith("interface:")
        )]
        if blockers:
            blocker = blockers[-1]
            return _stop(blocker["reason"], blocker.get("detail", ""))
        if self.latest_dispatch and self.latest_dispatch in self.lost:
            return _stop("dispatch-lost", f"dispatch {self.latest_dispatch} was lost")
        return None

    @property
    def building(self):
        return self.exists and not self.queued and not self.landed and self.stop() is None

    def _transition(self, status):
        """Committer time of the base change introducing the named status."""
        commits = _git(
            self.wave.root, "log", "--format=%H %cI", "-G",
            r"^\*\*Status:\*\*", self.wave.base, "--", self.contract.rel_path,
        ).stdout.splitlines()
        pattern = re.compile(r"^\+\*\*Status:\*\*\s*`?" + status + r"\b", re.M)
        for line in commits:
            revision, timestamp = line.split(" ", 1)
            patch = _git(self.wave.root, "show", "--format=", "--unified=0", revision,
                         "--", self.contract.rel_path).stdout
            if status == "ACCEPTED" and re.search(
                r"^-\*\*Status:\*\*\s*`?(?:COMPLETE|ACCEPTED)\b", patch, re.M,
            ):
                continue  # A reopening or unchanged status is not acceptance.
            if pattern.search(patch):
                return _instant(timestamp).astimezone(timezone.utc).isoformat()
        return None

    def _ready_time(self):
        accepted = self._transition("ACCEPTED")
        if accepted is None:
            return None
        times = [accepted]
        for dep in self.contract.depends_on:
            if not self.wave.integrated(dep):
                return None
            prior = self.wave.brief(dep)
            merged = (prior._forge_stages().get("merged")
                      if prior.exists and self.wave.settings.method == "github"
                      else prior.merged)
            merged = merged or prior._transition("COMPLETE")
            if merged is None:
                return None
            times.append(merged)
        return max(times, key=_instant)

    def _repairs(self):
        repairs = []
        refused_return = any(b["kind"] == "interface-not-returned"
                             for b in self.blockers.values())
        refused_blocks = {b["seq"] for b in self.state.active_blockers} if refused_return else set()
        for event in self.events:
            data = event.data
            kind = None
            if event.type == "verdict.recorded" and data.get("verdict") == "fail":
                kind = "review-failed"
            elif self.contract.is_lean and event.type == "floor.verdict" and data.get("verdict") == "fail":
                kind = "floor-failed"
            elif (self.contract.is_lean and event.type == "blocker.raised"
                  and data.get("reason") == "acceptance-invalid"
                  and data.get("detail", "").startswith("interface:")):
                if event.seq not in refused_blocks:
                    kind = "interface-return"
            if kind:
                repairs.append({"kind": kind, "at": event.ts})
        for event in self.run:
            kind = event.data.get("reason") if event.type == "queue.left" else None
            if event.type == "dispatch.issued":
                data = event.data
                if data.get("role") == "builder" and data.get("task") == "repair":
                    if any(rule in reason for reason in data.get("reasons", [])
                           for rule in ("test-files-unchanged", "skeleton-interface-kept")):
                        kind = "guard-refusal"
                elif data.get("role") == "resolver":
                    kind = "conflict"
            if kind in _REPAIR_KINDS:
                repair = {"kind": kind, "at": event.ts}
                if repair not in repairs:
                    repairs.append(repair)
        return sorted(repairs, key=lambda r: _instant(r["at"]))

    def _forge_stages(self):
        """Read forge timestamps, never fetch or infer times from local clocks."""
        try:
            proc = subprocess.run(
                ["gh", "pr", "view", self.branch, "--json", "mergedAt,statusCheckRollup"],
                cwd=self.path, capture_output=True, text=True,
            )
        except OSError:
            return {}
        if proc.returncode:
            return {}
        try:
            data = json.loads(proc.stdout)
        except ValueError:
            return {}
        checks = data.get("statusCheckRollup") or []
        starts = [c.get("startedAt") or c.get("createdAt") for c in checks]
        ends = [c.get("completedAt") for c in checks]
        passed = checks and all(
            c.get("conclusion") in ("SUCCESS", "NEUTRAL", "SKIPPED")
            or c.get("state") == "SUCCESS" for c in checks
        )
        return {
            "checks-registered": min(filter(None, starts), key=_instant, default=None),
            "checks-passed": max(filter(None, ends), key=_instant, default=None) if passed else None,
            "merged": data.get("mergedAt"),
        }

    def report(self):
        stages = dict.fromkeys(_STAGES)
        stages["ready"] = self._ready_time()
        stages["started"] = _time(next((e for e in self.events if e.type == "run.started"), None))
        if self.state.completions:
            seq, completion = self.state.completions[-1]
            by_seq = {e.seq: e for e in self.events}
            stages["completed"] = _time(by_seq.get(seq))
            stages["own-tests-passed"] = _time(by_seq.get(completion.get("evidence_seq")))
            stages["reviewed"] = _time(by_seq.get(completion.get("verdict_seq")))
        if self.contract.is_lean:
            history = _spec.lean_state(self.engine, self.ident)
            authored = _last(self.events, "tests.authored")
            stages["tests-authored"] = _time(authored)
            if history.floor_passed:
                stages["floor-passed"] = _time(_last(self.events, "floor.verdict"))
            stages["queued"] = _time(_last(self.run, "queue.joined"))
        stages["merged"] = self.merged
        if self.exists and self.wave.settings.method == "github":
            stages.update(self._forge_stages())
        stop = self.stop()
        try:
            observed = driver_status(self.wave.root, self.ident)
        except OSError as exc:
            observed = {}
            stop = stop or _stop("environment-unavailable", str(exc))
        if stop is None and not self.landed and not stages["merged"]:
            for delivery in observed.get("deliveries", []):
                if delivery.get("blockers"):
                    blocker = delivery["blockers"][-1]
                    stop = _stop(blocker["kind"], blocker.get("detail", ""))
                    break
            if not self.exists and observed.get("not_ready"):
                stop = _stop("not-ready", "; ".join(m["detail"] for m in observed["not_ready"]))
        merges = 0
        if self.exists:
            requested = _last(self.run, "run.requested")
            start = requested.data.get("started_at") if requested else None
            # Keep counting after landing: the moving base eventually contains
            # the branch, but the delivery's original starting commit stays fixed.
            start = start or self.wave.base
            for line in _git(self.path, "rev-list", "--first-parent", "--merges", "--parents",
                             f"{start}..{self.branch}").stdout.splitlines():
                parents = line.split()[2:]
                if any(_git(self.path, "merge-base", "--is-ancestor", p, self.wave.base).returncode == 0
                       for p in parents):
                    merges += 1
        ready, merged = stages["ready"], stages["merged"]
        return {
            "brief": self.ident, "policy": self.contract.authority_policy, "stages": stages,
            "lead_time_seconds": (_instant(merged) - _instant(ready)).total_seconds()
            if ready and merged else None,
            "base_merges": merges,
            "ci_runs": len({e.data["commit"] for e in self.run
                            if e.type.startswith("forge.checks-") and e.data.get("commit")}),
            "repairs": self._repairs(), "stop": stop,
        }


def _status(root, request):
    wave = _Wave(root, request)
    return {"briefs": [wave.brief(ib).report() for ib in wave.contracts], "queue": _queue(root)}
