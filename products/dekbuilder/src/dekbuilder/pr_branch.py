"""Build a review branch while hiding git replay and artifact classification."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
from typing import Any

from dekspec.api import BEHAVIOR_SPEC_NAMES

__all__ = ["PrBranchRefused", "PrBranchReport", "build_pr_branch", "leaked_paths", "register"]


class PrBranchRefused(Exception):
    """A branch could not be built safely; ``reason`` explains why."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class PrBranchReport:
    """Commit/file counts, filtering decisions and verification from one run."""

    branch: str = ""
    target: str = ""
    pr_branch: str = ""
    original_commits: int = 0
    original_files: int = 0
    pr_commits: int = 0
    pr_files: int = 0
    excluded: list[dict[str, Any]] = field(default_factory=list)
    stripped: list[dict[str, Any]] = field(default_factory=list)
    leaked: list[str] = field(default_factory=list)
    next_step: str = ""


def _git(repo: Path | str, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    # Hooks can run arbitrary commands (including pushes); do not invoke them.
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_LITERAL_PATHSPECS="1")
    try:
        result = subprocess.run(
            ["git", "-c", f"core.hooksPath={os.devnull}", "-c", "commit.gpgSign=false", *args],
            cwd=repo, env=env, capture_output=True,
        )
    except OSError as error:
        raise PrBranchRefused(str(error)) from error
    # Decode without universal-newline conversion: carriage returns are valid
    # filename bytes in git's NUL-delimited output.
    result.stdout = result.stdout.decode("utf-8", errors="surrogateescape")
    result.stderr = result.stderr.decode("utf-8", errors="surrogateescape")
    if check and result.returncode:
        raise PrBranchRefused(f"git {args[0]}: {result.stderr.strip() or result.stdout.strip()}")
    return result


def _resolve(repo: Path | str, ref: str) -> str:
    # Git 2.23 predates --end-of-options. Reject option-shaped input before
    # passing the single revision to --verify.
    if ref.startswith("-"):
        raise PrBranchRefused(f"Target {ref!r} does not resolve to a commit")
    result = _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    if result.returncode:
        raise PrBranchRefused(f"Target {ref!r} does not resolve to a commit")
    return result.stdout.strip()


def _changes(repo: Path | str, *args: str) -> list[tuple[str, str]]:
    fields = _git(repo, *args, "--no-renames", "--name-status", "-z", "--").stdout.split("\0")
    return list(zip(fields[0:-1:2], fields[1:-1:2]))


def _commits(repo: Path | str, target: str, ref: str) -> list[str]:
    return _git(repo, "rev-list", "--reverse", f"{target}..{ref}", "--").stdout.split()


def _delivered(repo: Path | str, commits: list[str]) -> set[str]:
    # Read every commit, even if a later commit undoes a record change.
    return {
        match[1] for sha in commits
        for _, path in _changes(repo, "show", "--no-show-signature", "--format=", sha)
        if (match := re.match(r"^\.dekspec/execution/(IB-\d+)/", path))
    }


def _artifact_number(path: str, folders: tuple[str, ...], prefixes: tuple[str, ...]) -> str | None:
    p = PurePosixPath(path)
    if str(p.parent) not in {f"dekspec/{folder}" for folder in folders}:
        return None
    match = re.fullmatch(r"(?:" + "|".join(map(re.escape, prefixes)) + r")-(\d+)-.+\.md", p.name)
    return match[1] if match else None


def _transient(changes: list[tuple[str, str]], delivered: set[str]) -> list[str]:
    names = BEHAVIOR_SPEC_NAMES
    moved = {
        number for kind, path in changes if kind == "D"
        if (number := _artifact_number(path, names.old_folders, names.old_id_prefixes))
    }
    folders = ("intents", "impl-briefs", "interface-contracts", "architecture-elements",
               names.folder, *names.old_folders)
    indexes = {f"dekspec/{name}" for name in
               ("intent-index.md", "ib-index.md", "mission-index.md", names.index_file, *names.old_index_files)}
    transient = []
    for kind, path in changes:
        parts = PurePosixPath(path).parts
        ib = re.match(r"^dekspec/impl-briefs/(IB-\d+)(?=[-.]|$)", path)
        if path.startswith(".dekspec/execution/") or (ib and ib[1] in delivered):
            continue
        ledger = (path.startswith("docs/workspace/") and "pm" in parts[2:-1]
                  and parts[-1] in {"STATE.md", "LEDGER.md"})
        move = (kind == "A" and _artifact_number(path, (names.folder,), (names.id_prefix,)) in moved)
        if (path in indexes or path.startswith("pm/") or ledger or move
                or (kind != "A" and any(path.startswith(f"dekspec/{folder}/") for folder in folders))):
            transient.append(path)
    return transient


def leaked_paths(repo: Path | str, target: str, pr_branch: str) -> list[str]:
    """Return sorted transient paths in the diff, preserving new and delivered artifacts."""
    base, tip = _resolve(repo, target), _resolve(repo, pr_branch)
    return sorted(_transient(_changes(repo, "diff", base, tip), _delivered(repo, _commits(repo, base, tip))))


def _restore(repo: Path | str, source: str, paths: list[str]) -> None:
    # An added move half can be absent from both trees before replay. Git
    # restore refuses unmatched pathspecs, so only pass paths in either tree.
    indexed = set(_git(repo, "ls-files", "-z").stdout.split("\0"))
    present = set(_git(repo, "ls-tree", "-r", "--name-only", "-z", source).stdout.split("\0"))
    selected = [path for path in paths if path in indexed or path in present]
    if selected:
        _git(repo, "restore", f"--source={source}", "--staged", "--worktree", "--", *selected)


def _replay(repo: Path | str, sha: str, transient: list[str]) -> None:
    if transient:
        # --no-commit applies against the starting index. Match excluded paths
        # to the input parent so previously skipped edits cannot create a
        # spurious conflict, then restore those paths to the PR's prior HEAD.
        _restore(repo, f"{sha}^", transient)
        pick = _git(repo, "cherry-pick", "--no-commit", sha, check=False)
    else:
        pick = _git(repo, "cherry-pick", "--allow-empty", "--keep-redundant-commits", sha, check=False)
    if pick.returncode:
        raise PrBranchRefused(f"Cherry-pick failed for {sha}: {pick.stderr.strip() or pick.stdout.strip()}")
    if transient:
        _restore(repo, "HEAD", transient)
        _git(repo, "commit", "--allow-empty", "--no-verify", "-C", sha)


def build_pr_branch(repo: Path | str, target: str = "main") -> PrBranchReport:
    """Build a filtered sibling branch and restore the original checkout on completion."""
    repo = _git(repo, "rev-parse", "--show-toplevel").stdout.rstrip("\n")
    base = _resolve(repo, target)
    branch_result = _git(repo, "symbolic-ref", "--quiet", "HEAD", check=False)
    if branch_result.returncode:
        raise PrBranchRefused("Detached HEAD: check out a branch first")
    branch = branch_result.stdout.strip().removeprefix("refs/heads/")
    if _git(repo, "status", "--porcelain", "--untracked-files=no").stdout:
        raise PrBranchRefused("Uncommitted changes to tracked files")
    original = _resolve(repo, "HEAD")
    commits = _commits(repo, base, original)
    if not commits:
        raise PrBranchRefused(f"Nothing ahead of {target}")
    pr_branch = f"{branch}-pr"
    if _git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{pr_branch}", check=False).returncode == 0:
        raise PrBranchRefused(f"Branch {pr_branch} already exists")
    merges = _git(repo, "rev-list", "--min-parents=2", f"{base}..{original}", "--").stdout.split()
    if merges:
        raise PrBranchRefused(f"Merge commit ahead of {target}: {merges[0]}")
    delivered = _delivered(repo, commits)
    plans = []
    touched = {path for _, path in _changes(repo, "diff", original, base)}
    report = PrBranchReport(branch=branch, target=target, pr_branch=pr_branch, original_commits=len(commits),
                            original_files=_file_count(repo, base, original),
                            next_step=f"git push -u origin {shlex.quote(pr_branch)} && gh pr create")
    for sha in commits:
        changes = _changes(repo, "show", "--no-show-signature", "--format=", sha)
        transient = _transient(changes, delivered)
        if changes and len(transient) == len(changes):
            subject = _git(repo, "show", "--no-show-signature", "-s", "--format=%s", sha).stdout.rstrip("\n")
            report.excluded.append({"sha": sha, "subject": subject})
        else:
            plans.append((sha, transient))
            touched.update(path for _, path in changes)
            if transient:
                report.stripped.append({"sha": sha, "paths": transient})

    # Include ignored files: git can otherwise overwrite them while replaying
    # a path that was added and then deleted on the original branch.
    untracked = _git(repo, "ls-files", "--others", "-z").stdout.split("\0")[:-1]
    for path in untracked:
        if any(path == other or path.startswith(other + "/") or other.startswith(path + "/")
               for other in touched):
            raise PrBranchRefused(f"Untracked file would be overwritten during replay: {path!r}")

    # Creation must succeed before entering cleanup: never delete an existing ref.
    _git(repo, "checkout", "--no-overwrite-ignore", "-b", pr_branch, base)
    try:
        for sha, transient in plans:
            _replay(repo, sha, transient)
        report.pr_commits = len(_commits(repo, base, "HEAD"))
        report.pr_files = _file_count(repo, base, "HEAD")
        report.leaked = leaked_paths(repo, base, pr_branch)
    except PrBranchRefused:
        # Abort may fail on directory/file conflicts or have no pick to abort
        # after --no-commit. Discard unmerged entries on the temporary branch
        # without moving any ref, then clear residual sequencing state.
        # Every cleanup step gets a chance; none replaces the original error.
        for args in (
            ("cherry-pick", "--abort"),
            ("read-tree", "--reset", "-u", "HEAD"),
            ("cherry-pick", "--quit"),
            ("checkout", "--no-overwrite-ignore", branch),
            ("branch", "-D", pr_branch),
        ):
            try:
                _git(repo, *args, check=False)
            except PrBranchRefused:
                continue
        raise
    _git(repo, "checkout", "--no-overwrite-ignore", branch)
    return report


def _file_count(repo: Path | str, target: str, ref: str) -> int:
    return len(_git(repo, "diff", "--name-only", "-z", target, ref, "--").stdout.split("\0")) - 1


def _run(args: argparse.Namespace) -> int:
    try:
        report = build_pr_branch(args.at or Path.cwd(), args.target)
    except PrBranchRefused as error:
        print(json.dumps({"error": error.reason}) if args.json else f"error: {error.reason}")
        return 1
    if args.json:
        print(json.dumps(asdict(report)))
    else:
        print(f"branch: {report.branch}\ntarget: {report.target}\npr_branch: {report.pr_branch}")
        print(f"original: {report.original_commits} commits / {report.original_files} files")
        print(f"pr: {report.pr_commits} commits / {report.pr_files} files")
        print(f"excluded: {len(report.excluded)} commits")
        for entry in report.excluded:
            print(f"  {entry['sha']} {entry['subject']}")
        print(f"stripped: {len(report.stripped)} commits")
        for entry in report.stripped:
            print(f"  {entry['sha']}: {json.dumps(entry['paths'])}")
        print(f"leaked: {len(report.leaked)} paths")
        for path in report.leaked:
            print(f"  {json.dumps(path)}")
        print(f"next_step: {report.next_step}")
    return 1 if report.leaked else 0


def register(sub: Any) -> None:
    """Add the `pr-branch` subcommand to DekBuilder's parser."""
    from dekbuilder.cli import register_pr_branch

    register_pr_branch(sub)
