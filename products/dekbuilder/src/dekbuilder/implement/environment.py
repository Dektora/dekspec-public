"""Checkout execution and provenance, shared by the driver and host preflights.

Only this module constructs checkout environments. Package discovery runs in a
fresh interpreter: the coordinator's already-imported modules cannot influence
whether a delivery supplies its own driver.
"""
from __future__ import annotations

import filecmp
import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class CheckoutEnvironment:
    env: dict[str, str]
    cwd: Path
    python: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return {"python": self.python, "checkout": str(self.cwd), "source": self.source}


def checkout_environment(checkout: Path | str, *, configured_python: str | None = None) -> CheckoutEnvironment:
    """Select a checkout's interpreter without falling back from its own venv.

    Paths to virtual-environment executables are deliberately not dereferenced:
    a symlink to system Python still starts the virtual environment.
    """
    root = Path(checkout).resolve()
    env = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"):
        env.pop(key, None)
    venv = root / ".venv"
    bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    if venv.exists():
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", os.defpath)
        env["VIRTUAL_ENV"] = str(venv)
    else:
        env.pop("VIRTUAL_ENV", None)
    if configured_python:
        candidate = Path(configured_python).expanduser()
        if not candidate.is_absolute():
            candidate = (root / candidate if len(candidate.parts) > 1 else
                         Path(shutil.which(str(candidate), path=env.get("PATH", os.defpath)) or root / candidate))
        python = str(candidate.absolute())
        source = "own" if candidate.absolute().is_relative_to(root) else "configured"
    elif venv.exists():
        python, source = str(bin_dir / ("python.exe" if os.name == "nt" else "python")), "own"
    else:
        python = (shutil.which("python3", path=env.get("PATH", os.defpath)) or
                  shutil.which("python", path=env.get("PATH", os.defpath)) or "python3")
        source = "none-in-project"
    return CheckoutEnvironment(env, root, python, source)


class EnvironmentUnavailable(RuntimeError):
    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind


def _run(environment: CheckoutEnvironment, code: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([environment.python, "-c", code], cwd=environment.cwd, env=environment.env,
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EnvironmentUnavailable("environment-unavailable", f"{environment.python}: {exc}") from exc


def own_copy(environment: CheckoutEnvironment) -> dict[str, Any] | None:
    """Find both packages before importing either, distinguishing absent from broken."""
    probe = _run(environment, "import json, importlib.util; print(json.dumps({n: "
                 "(s.origin if (s := importlib.util.find_spec(n)) else None) "
                 "for n in ('dekbuilder', 'dekspec')}))")
    if probe.returncode:
        raise EnvironmentUnavailable("environment-unavailable",
                                     f"{environment.python}: {(probe.stderr or probe.stdout)[-1500:]}")
    try:
        paths = json.loads(probe.stdout)
    except ValueError as exc:
        raise EnvironmentUnavailable("environment-unavailable",
                                     f"{environment.python}: invalid interpreter response: {probe.stdout[-500:]}") from exc
    if not all(paths.values()):
        return None
    try:
        imported = _run(environment, "import json, dekbuilder, dekspec.api as spec; print(json.dumps({"
                        "n: {'path': m.__file__, 'version': m.__version__} "
                        "for n, m in (('dekbuilder', dekbuilder), ('dekspec', spec))}))")
    except EnvironmentUnavailable as exc:
        raise EnvironmentUnavailable("delivery-copy-unavailable", f"{paths}: {exc}") from exc
    try:
        packages = json.loads(imported.stdout) if imported.returncode == 0 else None
    except ValueError:
        packages = None
    if packages is None:
        raise EnvironmentUnavailable("delivery-copy-unavailable",
                                     f"{paths}; {environment.python}: "
                                     f"{(imported.stderr or imported.stdout)[-1500:]}")
    return packages


def copy_provenance(packages: dict[str, Any], source: str) -> dict[str, Any]:
    """Describe the loaded copy, including its source checkout at operation entry."""
    folder = Path(packages["dekbuilder"]["path"]).resolve().parent
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=folder,
                         capture_output=True, text=True)
    revision, dirty = None, False
    if top.returncode == 0:
        root = top.stdout.strip()
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                  capture_output=True, text=True).stdout.strip() or None
        dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root,
                                    capture_output=True, text=True).stdout.strip())
    return {**packages, "revision": revision, "dirty": dirty, "source": source}


def coordinator_packages() -> dict[str, Any]:
    import dekbuilder
    import dekspec.api as spec

    return {name: {"path": module.__file__, "version": module.__version__}
            for name, module in (("dekbuilder", dekbuilder), ("dekspec", spec))}


_process_environment_lock = RLock()


@contextmanager
def _entered_environment(environment: CheckoutEnvironment):
    """Give the current copy the checkout context for its synchronous operation.

    Serialize entries because cwd and environ are process-wide, and restore both
    even when the operation fails. Child commands inherit this same context.
    """
    with _process_environment_lock:
        previous_env, previous_cwd = dict(os.environ), Path.cwd()
        try:
            os.chdir(environment.cwd)
            os.environ.clear()
            os.environ.update(environment.env)
            yield
        finally:
            os.environ.clear()
            os.environ.update(previous_env)
            os.chdir(previous_cwd)


def run_coordinator_operation(environment: CheckoutEnvironment, operation: dict[str, Any]) -> dict[str, Any]:
    """Run pre-delivery admission on the coordinator with the selected interpreter.

    Root-checkout packages never choose the planning implementation. Check that
    its interpreter starts separately from checking a dependency such as pytest,
    so a startup failure retains its actual diagnosis.
    """
    from dekbuilder.implement.driver import _operation

    probe = _run(environment, "pass")
    if probe.returncode:
        raise EnvironmentUnavailable("environment-unavailable",
                                     f"{environment.python}: {(probe.stderr or probe.stdout)[-1500:]}")
    payload = {**operation, "environment": environment.as_dict(),
               "copy": copy_provenance(coordinator_packages(), "coordinator")}
    with _entered_environment(environment):
        return _operation(payload)


def run_operation(environment: CheckoutEnvironment, operation: dict[str, Any]) -> dict[str, Any]:
    """Run one delivery operation using its copy, or explicitly load the coordinator.

    Bootstrap locations affect only this driver process's imports, never a
    project's command environment. No inherited PYTHONPATH is consulted.
    """
    import sys

    packages = own_copy(environment)
    source = "delivery" if packages else "coordinator"
    packages = packages or coordinator_packages()
    roots = [] if source == "delivery" else list(dict.fromkeys(
        str(Path(info["path"]).resolve().parents[1]) for info in packages.values()))
    operation = {**operation, "environment": environment.as_dict(),
                 "copy": copy_provenance(packages, source)}
    # A selected runtime may already be the one hosting this call (notably a
    # coordinator-only consumer). Keep its loaded policy and boundary adapters.
    # Matching the executable directory as well as the executable preserves
    # virtual-environment identity when multiple venvs share one Python binary.
    # venv can copy its python/python3 aliases instead of symlinking them.
    python = environment.python if source == "delivery" else sys.executable
    if (packages == coordinator_packages()
            and Path(python).absolute().parent == Path(sys.executable).absolute().parent
            and (Path(python).samefile(sys.executable)
                 or filecmp.cmp(python, sys.executable, shallow=False))):
        from dekbuilder.implement.driver import _operation

        with _entered_environment(environment):
            return _operation(operation)
    bootstrap = ("import json, sys; " + (f"sys.path[:0] = {roots!r}; " if roots else "") +
                 "from dekbuilder.implement.driver import _operation; "
                 "print(json.dumps(_operation(json.load(sys.stdin))))")
    try:
        proc = subprocess.run([python, "-c", bootstrap], input=json.dumps(operation),
                              cwd=environment.cwd, env=environment.env, capture_output=True, text=True)
    except OSError as exc:
        raise EnvironmentUnavailable("delivery-copy-unavailable", f"{packages}: {exc}") from exc
    if proc.returncode:
        raise EnvironmentUnavailable("delivery-copy-unavailable",
                                     f"{packages}: {(proc.stderr or proc.stdout)[-2000:]}")
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise EnvironmentUnavailable("delivery-copy-unavailable",
                                     f"{packages}: invalid step JSON: {proc.stdout[-1000:]}") from exc


def run_module(environment: CheckoutEnvironment, module: str, arguments: list[str]) -> subprocess.CompletedProcess:
    """Start a package CLI using the selected copy and the checkout environment."""
    import sys

    packages = own_copy(environment)
    roots = [] if packages else list(dict.fromkeys(
        str(Path(info["path"]).resolve().parents[1]) for info in coordinator_packages().values()))
    bootstrap = ("import runpy, sys; " + (f"sys.path[:0] = {roots!r}; " if roots else "") +
                 f"sys.argv = {[module, *arguments]!r}; runpy.run_module({module!r}, run_name='__main__')")
    return subprocess.run([environment.python if packages else sys.executable, "-c", bootstrap],
                          cwd=environment.cwd, env=environment.env, capture_output=True, text=True)
