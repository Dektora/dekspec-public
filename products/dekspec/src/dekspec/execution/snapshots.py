"""Content-addressed manifests of reviewed content.

A review verdict is bound to a fingerprint; the manifest behind that
fingerprint is stored once at ``.dekspec/execution/<ID>/snapshots/<fp>.json``.
Because the file is named by the fingerprint of its own content, it is
self-verifying: :func:`load` recomputes the fingerprint and refuses a
snapshot that does not match its name. A later completion check diffs the
stored manifest against the current one to learn exactly which paths changed
since the review — no git history, path quoting or commit reachability needed.
"""

from __future__ import annotations

import json
from pathlib import Path

from dekspec.execution.fingerprint import fingerprint_of
from dekspec.execution.record import execution_root

__all__ = ["load", "save"]


def _path(repo_root: Path, artifact_id: str, fingerprint: str) -> Path:
    return execution_root(repo_root) / artifact_id / "snapshots" / f"{fingerprint}.json"


def save(repo_root: Path, artifact_id: str, manifest: dict[str, str]) -> str:
    fp = fingerprint_of(manifest)
    path = _path(repo_root, artifact_id, fp)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return fp


def load(repo_root: Path, artifact_id: str, fingerprint: str) -> dict[str, str] | None:
    """The manifest for ``fingerprint``, or None when missing or not genuine."""
    path = _path(repo_root, artifact_id, fingerprint)
    if not path.is_file():
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict) or fingerprint_of(manifest) != fingerprint:
        return None
    return manifest
