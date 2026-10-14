"""Runtime admission composed with the single Spec-owned authority assessment."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from dekbuilder._spec import require_spec

from dekspec.builder_compat import (
    Engine, IBContract, Missing, Readiness, ReadinessTarget, TargetReadiness, assess_authority,
    check_delivery_source, intent_completion,
)
from dekbuilder.implement.config import IntegrationSettings, load_integration
from dekbuilder.implement.targets import Target
from dekbuilder.implement.environment import EnvironmentUnavailable, checkout_environment, run_coordinator_operation

__all__ = ["Missing", "Readiness", "TargetReadiness", "assess", "authoritative_base", "intent_completion"]

def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True)


def _resolves(root: Path, ref: str) -> bool:
    return _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}").returncode == 0


def authoritative_base(root: Path, integration: IntegrationSettings) -> tuple[str, str]:
    """The delivery base as the driver integrates into it: its branch name, and the
    ref that is authoritative for it — the local branch for `merge`, the configured
    remote's tracking branch for a forge method — returned whether or not it
    resolves here. Nothing is substituted for it: a local branch is not the forge's
    history, so an unfetched remote base is unknown, never local `main` (ADR-061).
    With no configured base the name is `main` or `master`, as the authoritative refs
    (else the local branches) show; the local branch names it, never its history."""
    from dekbuilder.implement.integration import base_ref

    name = integration.base or next(
        (b for b in ("main", "master") if _resolves(root, base_ref(root, b, integration, fetch=False))), None) or next(
        (b for b in ("main", "master") if _resolves(root, f"refs/heads/{b}")), "main")
    return name, base_ref(root, name, integration, fetch=False)


def _shown(ref: str) -> str:
    for prefix in ("refs/remotes/", "refs/heads/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def _base_tip(root: Path, ref: str) -> str | None:
    """The commit the delivery integrates into, without fetching."""
    proc = _git(root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
    return proc.stdout.strip() if proc.returncode == 0 else None


def _environment(engine: Engine, integration: IntegrationSettings, contracts: dict[str, IBContract],
                 spec_paths: list[str], readiness: Readiness) -> None:
    root = engine.repo_root
    add = lambda code, detail, fix: readiness.missing.append(Missing("environment", code, detail, fix))  # noqa: E731
    if _git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        add("not-a-repository", f"{root} is not a git repository", "run `/implement` inside the repository")
        return
    tip = _base_tip(root, engine.base) if engine.base else None
    if tip is None:
        add("no-integration-base", f"the integration base `{readiness.base or 'main'}` does not resolve here"
            + (f" (the driver integrates into `{_shown(engine.base or '')}`)"
               if integration.method == "github" else ""),
            "fetch it, or set `integration.base` in `.dekspec/config.yaml`")
    elif _git(root, "merge-base", "--is-ancestor", tip, "HEAD").returncode != 0:
        add("checkout-behind-base", f"the current checkout does not contain the tip of `{readiness.base}`",
            f"update this checkout from `{readiness.base}` first")
    else:
        ahead = check_delivery_source(engine, tip=tip, contracts=contracts, spec_paths=spec_paths)
        if ahead:
            add("checkout-ahead-of-base",
                f"this checkout carries changes `{readiness.base}` does not have, and the delivery starts from it, "
                "so they would be charged to the run: " + ", ".join(ahead[:6]) + (" …" if len(ahead) > 6 else ""),
                f"run `/implement` from a checkout of `{readiness.base}` with the specifications committed, or "
                f"integrate these changes into `{readiness.base}` first")
    dirty = [line[3:] for line in _git(root, "status", "--porcelain", "--", *spec_paths).stdout.splitlines()]
    if dirty:
        add("uncommitted-spec", "specifications for the targets are not committed: " + ", ".join(dirty[:6]),
            "commit them — the delivery starts from the committed checkout")
    readiness.integration = {"method": integration.method, "base": readiness.base, "remote": integration.remote,
                             "push": integration.push}
    if integration.method == "github":
        if not shutil.which("gh"):
            add("forge-cli-missing", "integration.method is github but `gh` is not installed",
                "install the GitHub CLI, or set `integration.method: merge`")
        elif subprocess.run(["gh", "auth", "status"], cwd=str(root), capture_output=True).returncode != 0:
            add("forge-unauthenticated", "`gh auth status` fails", "authenticate: `gh auth login`")
        if _git(root, "remote", "get-url", integration.remote).returncode != 0:
            add("forge-remote-missing", f"no git remote `{integration.remote}`",
                "add the remote, or set `integration.remote`")
    elif integration.push and _git(root, "remote", "get-url", integration.remote).returncode != 0:
        add("push-remote-missing", f"integration.push is set but there is no remote `{integration.remote}`",
            "add the remote, or unset `integration.push`")
    environment = checkout_environment(root, configured_python=engine.settings.python)
    if any(a.kind == "pytest" for c in contracts.values() for a in c.acceptance):
        try:
            has_pytest = run_coordinator_operation(environment, {"verb": "test-interpreter", "root": str(root)})["ok"]
        except EnvironmentUnavailable as exc:
            add(exc.kind, str(exc), "repair the project environment, or set `execution.python`")
        else:
            if not has_pytest:
                add("no-test-interpreter", f"no pytest in selected interpreter {environment.python}",
                    "set `execution.python`, or install pytest into the project environment")
    for c in contracts.values():
        if c.status != "ACCEPTED" or not c.prerequisites:
            continue
        try:
            result = run_coordinator_operation(environment, {"verb": "probes", "root": str(root), "ib": c.ib_id})
            detail = "; ".join(f"`{p['probe']}`: {'passed' if p['ok'] else 'failed'}" for p in result["results"])
        except EnvironmentUnavailable as exc:
            detail = str(exc)
        advisory = Missing(c.ib_id, "prerequisite-advisory",
                           f"Advisory probe with {environment.python}: {detail}. "
                           "The delivery repeats the probe in its own environment after setup; only that probe decides start.",
                           "continue to prepare the delivery")
        for target in readiness.targets:
            if c.ib_id in target.ibs:
                target.advisories.append(advisory)


def assess(repo_root: Path, targets: list[Target], *, spec_root: str = "dekspec",
           check_environment: bool = True) -> Readiness:
    require_spec()
    root = Path(repo_root)
    integration = load_integration(root)
    name, ref = authoritative_base(root, integration)
    neutral = [ReadinessTarget(t.id, t.kind, t.path, t.status, t.name, t.provisional) for t in targets]
    assessment = assess_authority(root, neutral, spec_root=spec_root, base=ref, base_name=name)
    readiness = assessment.readiness
    if check_environment and any(t.outcome == "ready" for t in readiness.targets):
        engine = Engine(root, spec_root=spec_root, base=ref)
        _environment(engine, integration, assessment.contracts, assessment.spec_paths, readiness)
    return readiness
