"""Integration policy for `/implement` (ADR-059): ``.dekspec/config.yaml`` ``integration:``.

Read leniently, like the execution settings: a malformed or absent block
yields the safe default — merge the verified head into the base branch
locally, without pushing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["METHODS", "IntegrationSettings", "load_integration"]

METHODS = ("merge", "github")


@dataclass(frozen=True)
class IntegrationSettings:
    #: ``merge`` fast-forwards the base branch to the verified head; ``github``
    #: lands it through a pull request (``gh``), after its required checks.
    method: str = "merge"
    #: Base branch; ``None`` resolves ``main`` / ``master``.
    base: str | None = None
    #: Remote used by ``push`` and by the ``github`` method.
    remote: str = "origin"
    #: ``merge`` only: also push the updated base branch.
    push: bool = False
    #: Command run once in a new delivery worktree (e.g. create its venv).
    worktree_setup: str | None = None


def load_integration(repo_root: Path) -> IntegrationSettings:
    import yaml

    cfg = Path(repo_root) / ".dekspec" / "config.yaml"
    raw: dict = {}
    try:
        loaded = yaml.safe_load(cfg.read_text(encoding="utf-8")) if cfg.is_file() else {}
        raw = (loaded.get("integration") or {}) if isinstance(loaded, dict) else {}
    except yaml.YAMLError:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    method = str(raw.get("method") or "merge").lower()
    return IntegrationSettings(
        method=method if method in METHODS else "merge",
        base=str(raw["base"]) if raw.get("base") else None,
        remote=str(raw.get("remote") or "origin"),
        push=bool(raw.get("push", False)),
        worktree_setup=str(raw["worktree_setup"]) if raw.get("worktree_setup") else None,
    )
