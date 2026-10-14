"""Advance existing work outside the lock; serialize only admission of new work."""

import fcntl
from pathlib import Path

from dekbuilder.implement.config import load_integration
from dekbuilder.implement.driver import DriverError, next_step
from dekbuilder.implement.readiness import authoritative_base

from ._state import _Wave, _git, _queue


def _fast_forward(root):
    settings = load_integration(root)
    name, _ = authoritative_base(root, settings)
    if _git(root, "status", "--porcelain").stdout.strip():
        return
    if _git(root, "remote", "get-url", settings.remote).returncode:
        return
    fetched = _git(root, "fetch", "-q", settings.remote, name)
    if fetched.returncode:
        return  # The driver's admission reports unavailable bases.
    remote = f"refs/remotes/{settings.remote}/{name}"
    if (_git(root, "rev-parse", "HEAD").stdout != _git(root, "rev-parse", remote).stdout
            and _git(root, "merge-base", "--is-ancestor", "HEAD", remote).returncode == 0):
        result = _git(root, "merge", "--ff-only", remote)
        if result.returncode:
            raise DriverError(result.stderr.strip())


def _next_round(root, request, *, actor):
    root = Path(root)
    _fast_forward(root)
    wave = _Wave(root, request)
    actions, started = [], []
    for ident in wave.contracts:
        brief = wave.brief(ident)
        if brief.exists and not brief.landed:
            actions.append({**next_step(root, ident, actor=actor), "ack_request": ident})
    common = _git(root, "rev-parse", "--git-common-dir")
    if common.returncode:
        raise DriverError("wave next requires a git repository")
    lock = (root / common.stdout.strip()).resolve() / "dekbuilder/start.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        # Counting and admission share one cross-process lock and fresh state.
        wave = _Wave(root, request)
        limit = wave.settings.parallel_briefs
        building = sum(wave.brief(ib).building for ib in wave.contracts)
        for ident in wave.candidates():
            if building >= limit:
                break
            if wave.brief(ident).exists or not wave.ready(ident):
                continue
            actions.append({**next_step(root, ident, actor=actor), "ack_request": ident})
            updated = _Wave(root, request).brief(ident)
            if updated.exists:
                started.append(ident)
                building += int(updated.building)
        fcntl.flock(stream, fcntl.LOCK_UN)
    return {"actions": actions, "started": started, "building": building,
            "limit": limit, "queue": _queue(root)}
