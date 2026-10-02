"""Integrate a verified delivery through the configured method (ADR-059).

Integration state is observed, never remembered: whether the delivery is
merged, and whether a pull request exists, is read from git and the forge on
every call, so a repeated or resumed request can neither open a second pull
request nor merge twice.

* ``merge`` — fast-forward the base branch to the verified head. When the base
  is checked out in a worktree, that checkout is fast-forwarded (it must have
  no local changes); otherwise the ref is compare-and-swapped. ``push: true``
  also pushes the base, and then the remote is authoritative: a delivery in
  the local base but not the remote one is ``push-pending``, an obligation
  that survives a restart until a (never forced) push discharges it.
* ``github`` — push the branch, open or reuse its pull request, wait for the
  required checks, and merge with ``--match-head-commit`` (never an
  administrator override). Branch protection that refuses the merge is a
  genuine blocker, not something to route around. A failing required check is
  read from the checks' JSON (``gh`` exits 1), with its evidence, so the
  driver can repair it.
"""

from __future__ import annotations

import json
import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dekspec.implement.config import IntegrationSettings

__all__ = ["Integration", "base_ref", "integrate", "is_ancestor", "observe", "prepare_pr", "push_base",
           "required_checks", "tree_of"]


@dataclass
class Integration:
    state: str  # "merged" | "push-pending" | "pending" | "wait" | "behind" | "blocked" | "failed"
    detail: str = ""
    revision: str | None = None
    tree: str | None = None
    pr: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"state": self.state, "detail": self.detail, "revision": self.revision, "tree": self.tree,
                "pr": self.pr}


def _git(cwd: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=check)


def is_ancestor(cwd: Path, a: str, b: str) -> bool:
    return _git(cwd, "merge-base", "--is-ancestor", a, b).returncode == 0


def tree_of(cwd: Path, rev: str) -> str | None:
    proc = _git(cwd, "rev-parse", f"{rev}^{{tree}}")
    return proc.stdout.strip() if proc.returncode == 0 else None


def base_ref(worktree: Path, base: str, settings: IntegrationSettings, *, fetch: bool = True) -> str:
    """The ref the delivery integrates into: the local base branch, or the
    forge's copy of it for a forge method."""
    if settings.method == "github":
        if fetch:
            _git(worktree, "fetch", "-q", settings.remote, base)
        return f"refs/remotes/{settings.remote}/{base}"
    return f"refs/heads/{base}"


def _holder(worktree: Path, base: str) -> Path | None:
    listing = _git(worktree, "worktree", "list", "--porcelain").stdout
    path = None
    for line in listing.splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):])
        elif line == f"branch refs/heads/{base}" and path is not None:
            return path
    return None


def observe(worktree: Path, base: str, settings: IntegrationSettings, head: str | None = None) -> Integration:
    """Is the delivery's head already in the base? Read-only."""
    head = head or _git(worktree, "rev-parse", "HEAD").stdout.strip()
    ref = base_ref(worktree, base, settings)
    base_rev = _git(worktree, "rev-parse", "-q", "--verify", ref).stdout.strip()
    if not base_rev:
        return Integration("blocked", f"integration base {ref} does not exist")
    if is_ancestor(worktree, head, base_rev):
        if settings.method == "merge" and settings.push:
            # The configured remote is authoritative: merged locally is not integrated
            # until the remote base contains the delivery too.
            _git(worktree, "fetch", "-q", settings.remote, base)
            remote_rev = _git(worktree, "rev-parse", "-q", "--verify",
                              f"refs/remotes/{settings.remote}/{base}").stdout.strip()
            if not remote_rev or not is_ancestor(worktree, head, remote_rev):
                return Integration("push-pending", f"{base} contains the delivery locally, but "
                                                   f"{settings.remote}/{base} does not yet", base_rev,
                                   tree_of(worktree, base_rev))
            return Integration("merged", f"{head[:12]} is in {settings.remote}/{base}", remote_rev,
                               tree_of(worktree, remote_rev))
        return Integration("merged", f"{head[:12]} is in {base}", base_rev, tree_of(worktree, base_rev))
    pr = None
    if settings.method == "github":
        pr = _find_pr(worktree, base, settings)
        if pr and pr.get("state") == "MERGED" and pr.get("headRefOid") == head:
            return Integration("merged", f"pull request #{pr['number']} merged", base_rev,
                               tree_of(worktree, base_rev), pr)
    if not is_ancestor(worktree, base_rev, head):
        return Integration("behind", f"{base} has moved past the delivery", base_rev, pr=pr)
    return Integration("pending", "not merged", base_rev, pr=pr)


def _gh(worktree: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], cwd=str(worktree), capture_output=True, text=True)


def _find_pr(worktree: Path, base: str, settings: IntegrationSettings) -> dict[str, Any] | None:
    branch = _git(worktree, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    proc = _gh(worktree, "pr", "list", "--head", branch, "--base", base, "--state", "all",
               "--json", "number,state,headRefOid,url")
    if proc.returncode != 0:
        return None
    try:
        prs = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return None
    open_or_merged = [p for p in prs if p.get("state") in ("OPEN", "MERGED")]
    return sorted(open_or_merged, key=lambda p: p.get("number", 0))[-1] if open_or_merged else None


def _merge_local(worktree: Path, base: str, settings: IntegrationSettings, head: str) -> Integration:
    ref = f"refs/heads/{base}"
    old = _git(worktree, "rev-parse", ref).stdout.strip()
    if is_ancestor(worktree, head, old):
        if settings.push:
            return push_base(worktree, base, settings)
        return Integration("merged", "already in the base", old, tree_of(worktree, old))
    if not is_ancestor(worktree, old, head):
        return Integration("behind", f"{base} has moved past the delivery", old)
    holder = _holder(worktree, base)
    if holder is not None:
        dirty = _git(holder, "status", "--porcelain", "--untracked-files=no").stdout.strip()
        if dirty:
            return Integration("blocked", f"the checkout of {base} at {holder} has local changes; commit or "
                                          "stash them so it can be fast-forwarded")
        proc = _git(holder, "merge", "--ff-only", "-q", head)
        if proc.returncode != 0:
            return Integration("blocked", f"fast-forwarding {base} at {holder} failed: {proc.stderr.strip()[-300:]}")
    else:
        proc = _git(worktree, "update-ref", ref, head, old)
        if proc.returncode != 0:
            return Integration("behind", f"{base} changed while integrating: {proc.stderr.strip()[-200:]}")
    if settings.push:
        pushed = push_base(worktree, base, settings)
        if pushed.state != "merged":
            return pushed
    return Integration("merged", f"{base} fast-forwarded to {head[:12]}", head, tree_of(worktree, head))


def _push_refusal_detail(base: str, remote: str, output: str) -> str:
    """Budget the wrapper, first remote message and final Git lines separately.

    A single tail slice lets long paths hide the hook's reason and even the
    rejection line. Keep the first nonempty remote message mechanically (a
    banner counts), and give each final Git line its own share of the budget.
    """
    wrapper = (f"merged into {base[:256]} locally, but pushing it to {remote[:256]} "
               "failed (not forced): ")
    truncated = len(base) > 256 or len(remote) > 256
    message = ""
    context: deque[str] = deque(maxlen=3)
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("remote:"):
            diagnostic = line[len("remote:"):].strip()
            if diagnostic:
                if message:
                    truncated = True
                else:
                    message = diagnostic[:512]
                    truncated |= len(diagnostic) > 512
        elif line:
            truncated |= len(context) == context.maxlen
            context.append(line)

    parts = [f"remote: {message}"] if message else []
    marker = "\n[truncated]"
    # Reserve the marker even when unused, and one separator for each Git line.
    remaining = 4096 - len(wrapper) - len("\n".join(parts)) - len(marker) - len(context)
    if context:
        per_line = remaining // len(context)
        for line in context:
            truncated |= len(line) > per_line
            parts.append(line[-per_line:])
    return wrapper + "\n".join(parts) + (marker if truncated else "")


def push_base(worktree: Path, base: str, settings: IntegrationSettings) -> Integration:
    """Push the local base to the configured remote — never forced. Idempotent:
    re-run after an interruption or a rejection until the remote holds it."""
    ref = f"refs/heads/{base}"
    local = _git(worktree, "rev-parse", ref).stdout.strip()
    push = _git(worktree, "push", "-q", settings.remote, f"{ref}:{ref}")
    if push.returncode != 0:
        return Integration("push-pending", _push_refusal_detail(base, settings.remote, push.stderr or push.stdout),
                           local, tree_of(worktree, local))
    return Integration("merged", f"{base} pushed to {settings.remote} at {local[:12]}", local, tree_of(worktree, local))


def required_checks(worktree: Path, pr: dict[str, Any]) -> tuple[str, list[dict[str, Any]], str]:
    """The PR's required checks: ``passed`` | ``pending`` | ``failed`` (with the
    failing checks' evidence) | ``unavailable`` (the forge could not be read).
    `gh pr checks` exits 1 when a check failed and 8 while some are pending, so
    the result is read from its JSON, not from the exit status."""
    proc = _gh(worktree, "pr", "checks", str(pr["number"]), "--required", "--json", "name,bucket,description,link")
    try:
        checks = json.loads(proc.stdout) if proc.stdout.strip() else None
    except json.JSONDecodeError:
        checks = None
    if checks is None:
        text = (proc.stderr or proc.stdout).strip()
        if proc.returncode == 0 or "no required checks" in text.lower() or "no checks reported" in text.lower():
            return "passed", [], "no required checks"
        return "unavailable", [], f"reading the required checks of #{pr['number']} failed: {text[-300:]}"
    failures = [c for c in checks if c.get("bucket") in ("fail", "cancel")]
    if failures:
        return "failed", failures, "required check(s) failed: " + "; ".join(
            f"{c.get('name')}: {c.get('description') or c.get('bucket')} ({c.get('link') or 'no link'})" for c in failures)
    if any(c.get("bucket") == "pending" for c in checks) or proc.returncode == 8:
        return "pending", [], f"required checks of pull request #{pr['number']} are pending"
    return "passed", [], f"{len(checks)} required check(s) passed"


def prepare_pr(worktree: Path, base: str, settings: IntegrationSettings, *, title: str, body: str
               ) -> tuple[Integration, dict[str, Any] | None]:
    """Push the delivery head and open (or reuse) its pull request, without
    merging — so required checks run while the work can still be repaired."""
    branch = _git(worktree, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    push = _git(worktree, "push", "-q", "-u", settings.remote, f"HEAD:refs/heads/{branch}")
    if push.returncode != 0:
        return Integration("blocked", f"pushing {branch} failed: {push.stderr.strip()[-300:]}"), None
    pr = _find_pr(worktree, base, settings)
    # A pull request merged at an earlier head (someone merged a partial branch) is
    # history, not this delivery's pull request.
    if pr is None or (pr.get("state") == "MERGED" and pr.get("headRefOid") != head):
        created = _gh(worktree, "pr", "create", "--base", base, "--head", branch, "--title", title, "--body", body)
        if created.returncode != 0:
            return Integration("blocked", f"opening the pull request failed: {created.stderr.strip()[-300:]}"), None
        pr = _find_pr(worktree, base, settings)
    if pr is None:
        return Integration("blocked", "the pull request was created but cannot be found"), None
    return Integration("pending", f"pull request #{pr['number']}", pr=pr), pr


def _merge_github(worktree: Path, base: str, settings: IntegrationSettings, head: str,
                  title: str, body: str) -> Integration:
    prepared, pr = prepare_pr(worktree, base, settings, title=title, body=body)
    if pr is None:
        return prepared
    if pr.get("state") == "MERGED":
        base_rev = _git(worktree, "rev-parse", base_ref(worktree, base, settings)).stdout.strip()
        return Integration("merged", f"pull request #{pr['number']} merged", base_rev,
                           tree_of(worktree, base_rev), pr)
    if pr.get("headRefOid") and pr["headRefOid"] != head:
        return Integration("wait", f"pull request #{pr['number']} head is {pr['headRefOid'][:12]}, "
                                   f"waiting for {head[:12]}", pr=pr)
    state, failures, detail = required_checks(worktree, pr)
    if state == "unavailable":
        return Integration("blocked", detail, pr=pr)
    if state == "failed":
        return Integration("failed", detail, pr={**pr, "failures": failures})
    if state == "pending":
        return Integration("wait", detail, pr=pr)
    merged = _gh(worktree, "pr", "merge", str(pr["number"]), "--merge", "--match-head-commit", head)
    if merged.returncode != 0:
        return Integration("blocked", f"the forge refused the merge: {(merged.stderr or merged.stdout).strip()[-300:]}",
                           pr=pr)
    base_rev = _git(worktree, "rev-parse", base_ref(worktree, base, settings)).stdout.strip()
    return Integration("merged", f"pull request #{pr['number']} merged", base_rev, tree_of(worktree, base_rev), pr)


def integrate(worktree: Path, base: str, settings: IntegrationSettings, *, title: str, body: str) -> Integration:
    head = _git(worktree, "rev-parse", "HEAD").stdout.strip()
    if settings.method == "github":
        return _merge_github(worktree, base, settings, head, title, body)
    return _merge_local(worktree, base, settings, head)
