"""One base's durable landing line: LandingQueue(root, base) hides storage, locking, ordering, recovery and duplicate admission across worktrees/sessions; it calls no forge and decides no merge.
join(worktree, brief) admits a currently completed lean delivery once, recording/committing queue.joined before admission, and returns Admission(at_head, head, state, pr, tested_base); repeat admission preserves candidate facts.
candidate(brief, *, head, pr, tested_base) durably binds the tip to that head before push without moving the branch; pr may be None before opening, and tested_base=None means no known tip. It returns Admission; recovery restores only the current head's recorded tip, never another head's.
leave(brief, *, reason) removes it immediately, records queue.left for conflict/base-touched/candidate-failed (landed records no queue.left), and returns remaining ids. read() returns ordered ids as a tuple without writing, even on recovery; callers never know storage, locks or the admitting session.
Missing/damaged/unknown-version storage and repeat join/leave are normal; mutations raise OSError if persistence is impossible, while read falls back to run order; waiting/candidate, head position and departure reasons remain distinct.
Alternatives: entries plus lock/record/rebuild primitives leak recovery; a command/reducer API makes callers learn a protocol; the chosen queue object keeps each question direct, including durable candidate facts in the existing call. No public name or error is added for recovery.
"""
import fcntl as _fcntl
import json as _json
import os as _os
import subprocess as _subprocess
import tempfile as _tempfile
from contextlib import contextmanager as _contextmanager

from dekspec import builder_compat as _spec

from dataclasses import dataclass as _dataclass
from pathlib import Path as _Path


@_dataclass(frozen=True)
class Admission:
    """Landing facts; pr/tested_base are None until known; state is waiting or candidate."""

    at_head: bool
    head: str
    state: str
    pr: dict | None
    tested_base: str | None


class LandingQueue:
    """A base branch shared by every worktree of root; construction writes nothing."""

    def __init__(self, root: _Path, base: str):
        self._root = _Path(root).resolve()
        self._base = base
        common = _git(self._root, "rev-parse", "--git-common-dir")
        self._path = (self._root / common).resolve() / "dekbuilder" / "landing-queue" / (
            base.replace("/", "%2F") + ".json")

    def join(self, worktree: _Path, brief: str) -> Admission:
        """Admit a completed lean brief; repeat calls preserve its position and facts."""
        worktree = _Path(worktree).resolve()
        with self._change() as entries:
            existing = next((e for e in entries if e["brief"] == brief), None)
            if existing is not None:
                record = self._record(existing)
                joined = next((e for e in reversed(record.events())
                               if e.type == "queue.joined" and e.data.get("brief") == brief), None)
                if joined is None:
                    raise OSError(f"admission record disappeared for {brief}")
                head = _commit_join(record.repo_root, record, joined)
                if head != existing["head"]:
                    existing.update(head=head, pr=None, tested_base=None)
                return _admission(entries, existing)
            engine = _spec.Engine(worktree, base=self._base)
            state = engine.state(brief)[2]
            head = _git(worktree, "rev-parse", "HEAD")
            if not engine.contract(brief).is_lean or not state.completions:
                return Admission(False, head, "waiting", None, None)
            branch = _git(worktree, "branch", "--show-current")
            delivery = "RUN-" + branch.removeprefix("implement/").upper()
            record = engine.record(delivery)
            if engine.integration_state(brief, engine.contract(brief).rel_path,
                                        self._base_ref(worktree))[0] == "integrated":
                candidate = next((e.data for e in reversed(record.events())
                                  if e.type == "queue.candidate"
                                  and e.data.get("brief") == brief and e.data.get("head") == head), {})
                return Admission(False, head, "candidate" if candidate else "waiting",
                                 None, candidate.get("tested_base"))
            previous = next((e for e in reversed(record.events())
                             if e.type in ("queue.joined", "queue.left")
                             and e.data.get("brief") == brief), None)
            joined = previous if previous and previous.type == "queue.joined" else record.append(
                "queue.joined", "implement-driver", {
                    "brief": brief, "completion_seq": state.completions[-1][0], "head": head})
            head = _commit_join(worktree, record, joined)
            entry = dict(brief=brief, delivery=delivery, branch=branch,
                         head=head,
                         completion_seq=state.completions[-1][0], joined=joined.ts,
                         state="waiting", pr=None, tested_base=None)
            entries.append(entry)
            return _admission(entries, entry)

    def candidate(self, brief: str, *, head: str, pr: dict | None, tested_base: str | None) -> Admission:
        """Remember an admitted head's facts durably before push without moving HEAD.

        Only an admitted head may be a candidate; None clears the known tip.
        """
        with self._change() as entries:
            entry = next((e for e in entries if e["brief"] == brief), None)
            if entry is None:
                return Admission(False, head, "waiting", None, None)
            if entries[0] is not entry:
                return _admission(entries, entry)
            record = self._record(entry)
            data = {"brief": brief, "head": head, "tested_base": tested_base}
            previous = next((e.data for e in reversed(record.events())
                             if e.type == "queue.candidate" and e.data.get("brief") == brief), None)
            if previous != data:
                record.append("queue.candidate", "implement-driver", data)
            entry.update(head=head, pr=pr, tested_base=tested_base, state="candidate")
            return _admission(entries, entry)

    def leave(self, brief: str, *, reason: str) -> tuple[str, ...]:
        """Remove an admitted brief (or leave an absent brief absent); return the line."""
        with self._change(persist_after=False) as entries:
            entry = next((e for e in entries if e["brief"] == brief), None)
            if entry is not None:
                entries.remove(entry)
                # A failed persist must not leave a departure in the durable record.
                self._write(entries)
                if reason != "landed":
                    self._record(entry).append("queue.left", "implement-driver",
                                               {"brief": brief, "reason": reason})
            return tuple(e["brief"] for e in entries)

    def read(self) -> tuple[str, ...]:
        """Return landing order without writing, including when storage needs recovery."""
        return tuple(e["brief"] for e in self._load())

    @_contextmanager
    def _change(self, *, persist_after=True):
        """Serialize a whole mutation; test persistence before any record or branch write."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.with_suffix(".json.lock").open("a") as lock:
            _fcntl.flock(lock, _fcntl.LOCK_EX)
            try:
                entries = self._load()
                self._write(entries)
                yield entries
                if persist_after:
                    self._write(entries)
            except (_spec.ExecutionError, _spec.RecordIntegrityError) as exc:
                raise OSError(f"cannot persist landing line: {exc}") from exc
            finally:
                _fcntl.flock(lock, _fcntl.LOCK_UN)

    def _write(self, entries):
        """Replace a complete snapshot so readers need neither a lock nor a retry."""
        name = None
        try:
            with _tempfile.NamedTemporaryFile(mode="w", dir=self._path.parent,
                                              prefix=".queue-", delete=False) as stream:
                name = stream.name
                _json.dump({"version": 1, "base": self._base, "entries": entries}, stream)
                stream.flush()
                _os.fsync(stream.fileno())
            _os.replace(name, self._path)
            directory = _os.open(self._path.parent, _os.O_RDONLY)
            try:
                _os.fsync(directory)
            finally:
                _os.close(directory)
        except (TypeError, ValueError) as exc:
            raise OSError(f"cannot persist landing line: {exc}") from exc
        finally:
            if name is not None:
                _Path(name).unlink(missing_ok=True)

    def _load(self):
        """Use the disposable snapshot if intact, otherwise reconstruct without writes."""
        try:
            value = _json.loads(self._path.read_text())
            entries = value["entries"]
            fields = {"brief", "delivery", "branch", "head", "completion_seq",
                      "joined", "state", "pr", "tested_base"}
            if (set(value) == {"version", "base", "entries"}
                    and type(value["version"]) is int and value["version"] == 1
                    and value["base"] == self._base and isinstance(entries, list)
                    and all(isinstance(e, dict) and set(e) == fields
                            and e["state"] in ("waiting", "candidate")
                            and all(isinstance(e[k], str) for k in
                                    ("brief", "delivery", "branch", "head", "joined"))
                            and type(e["completion_seq"]) is int
                            and (e["pr"] is None or isinstance(e["pr"], dict))
                            and (e["tested_base"] is None or isinstance(e["tested_base"], str))
                            for e in entries)
                    and len({e["brief"] for e in entries}) == len(entries)):
                # The snapshot accelerates ordering, but cannot authorize a
                # candidate: only the per-head permanent record supplies its tip.
                paths = dict(self._worktrees())
                for entry in entries:
                    path = paths[entry["branch"]]
                    head = _git(path, "rev-parse", "HEAD")
                    events = _spec.Engine(path).record(entry["delivery"]).events()
                    joined = next((e for e in reversed(events)
                                   if e.type in ("queue.joined", "queue.left")
                                   and e.data.get("brief") == entry["brief"]), None)
                    if joined is None or joined.type != "queue.joined":
                        return self._recover()
                    candidate = next((e.data for e in reversed(events)
                                      if e.type == "queue.candidate" and e.seq > joined.seq
                                      and e.data.get("brief") == entry["brief"]
                                      and e.data.get("head") == head), {})
                    if head != entry["head"]:
                        entry["pr"] = None
                    entry.update(head=head, tested_base=candidate.get("tested_base"))
                return entries
        except (OSError, ValueError, TypeError, KeyError, _spec.RecordIntegrityError):
            pass
        return self._recover()

    def _worktrees(self):
        """Find delivery checkouts without consulting the forge or updating refs."""
        path = None
        for line in _git(self._root, "worktree", "list", "--porcelain").splitlines():
            if line.startswith("worktree "):
                path = _Path(line[9:])
            elif line.startswith("branch refs/heads/implement/") and path is not None:
                yield line.removeprefix("branch refs/heads/"), path

    def _record(self, entry):
        path = next((p for branch, p in self._worktrees() if branch == entry["branch"]), None)
        if path is None:
            raise OSError(f"delivery checkout unavailable: {entry['branch']}")
        return _spec.Engine(path).record(entry["delivery"])

    def _base_ref(self, path):
        # Config is local data; recovery never refreshes the remote.
        from dekbuilder.implement.config import load_integration

        settings = load_integration(path)
        if settings.method == "github":
            ref = f"refs/remotes/{settings.remote}/{self._base}"
            if _git(path, "rev-parse", "--verify", ref, required=False):
                return ref
        return self._base

    def _recover(self):
        """Reconstruct only live joins; candidate bindings are specific to the current head."""
        recovered = {}
        for branch, path in self._worktrees():
            try:
                engine = _spec.Engine(path, base=self._base)
                delivery = "RUN-" + branch.removeprefix("implement/").upper()
                events = engine.record(delivery).events()
                auth = next((e.data for e in events if e.type == "run.requested"), {})
                if auth.get("base") != self._base:
                    continue
                live = {}
                for event in events:
                    if event.type == "queue.joined":
                        live[event.data["brief"]] = event
                    elif event.type == "queue.left":
                        live.pop(event.data["brief"], None)
                for brief, joined in live.items():
                    contract = engine.contract(brief)
                    if not contract.is_lean or not engine.state(brief)[2].completions:
                        continue
                    base = self._base_ref(path)
                    if engine.integration_state(brief, contract.rel_path, base)[0] == "integrated":
                        continue
                    head = _git(path, "rev-parse", "HEAD")
                    candidate = next((e.data for e in reversed(events)
                                      if e.type == "queue.candidate" and e.data.get("brief") == brief
                                      and e.data.get("head") == head and e.seq > joined.seq), None)
                    recovered[brief] = dict(
                        brief=brief, delivery=delivery, branch=branch, head=head,
                        completion_seq=joined.data["completion_seq"], joined=joined.ts,
                        state="candidate" if candidate else "waiting", pr=None,
                        tested_base=candidate["tested_base"] if candidate else None)
            except (OSError, _spec.ExecutionError, _spec.RecordIntegrityError, KeyError):
                continue
        return sorted(recovered.values(), key=lambda e: (e["joined"], e["brief"]))



def _commit_join(worktree, record, joined):
    """Finish an interrupted join's commit without repeating its event."""
    rel = str(record.path.relative_to(worktree))
    committed = _git(worktree, "show", f"HEAD:{rel}", required=False)
    if joined.hash not in committed:
        # Commit only the run record; unrelated caller content stays unstaged.
        _git(worktree, "add", "--", rel)
        _git(worktree, "commit", "-q", "-m", f"implement: queue {joined.data['brief']}", "--", rel)
    return _git(worktree, "rev-parse", "HEAD")


def _admission(entries, entry):
    return Admission(entries[0] is entry, entry["head"], entry["state"],
                     entry["pr"], entry["tested_base"])


def _git(root, *args, required=True):
    result = _subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if required and result.returncode:
        raise OSError((result.stderr or result.stdout).strip())
    return result.stdout.strip() if result.returncode == 0 else ""
