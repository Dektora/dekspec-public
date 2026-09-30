"""Stdlib evidence primitives shared by standalone optional tools."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)


def identity(repo):
    root = git(repo, "rev-parse", "--show-toplevel")
    if root.returncode:
        raise ValueError("Target is not a Git repository")
    repo = Path(root.stdout.decode().strip()).resolve()
    revision = git(repo, "rev-parse", "HEAD")
    if revision.returncode:
        raise ValueError("Target has no committed revision")
    # Bind evidence to tracked changes and untracked, nonignored file contents.
    digest = hashlib.sha256(revision.stdout)
    digest.update(git(repo, "diff", "HEAD", "--binary").stdout)
    for raw in sorted(git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout.split(b"\0")):
        if not raw:
            continue
        path = repo / os.fsdecode(raw)
        digest.update(raw)
        if path.is_symlink():
            digest.update(os.readlink(path).encode())
        elif path.is_file():
            digest.update(path.read_bytes())
    return {"repo": str(repo), "revision": revision.stdout.decode().strip(),
            "branch": git(repo, "branch", "--show-current").stdout.decode().strip(),
            "tree": digest.hexdigest()}


def state_dir(repo, name):
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    repo_id = hashlib.sha256(str(Path(repo).resolve()).encode()).hexdigest()[:12]
    path = root / "dekspec" / repo_id / name
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def emit(data, full=False):
    if full:
        print(json.dumps(data, indent=2))
    else:
        for key, value in data.items():
            # Quoted JSON scalar payloads are valid TOON scalars, unlike JSON
            # arrays/objects masquerading as native TOON collections.
            if isinstance(value, (list, dict)):
                print(f"{key}: {json.dumps(json.dumps(value, separators=(',', ':')))}")
            else:
                print(f"{key}: {json.dumps(value)}")
