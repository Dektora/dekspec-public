"""Build hook that pre-populates `tooling/dekspec/_vendored/` from the
project-root `templates/`, cherry-picked `docs/`, and (since ADR-045) the full
plugin skill/command/hook tree, before standard build_py runs.

This is the wheel-bundling story for ds-md9 / INT-023 / IB-038 (templates +
docs) and ADR-045 / INT-179 (plugin tree). The `_vendored/` content is what
wheel-installed consumers consume via `vendoring.library_root()` when no
source-checkout layout is available — including `dekspec install --platform`,
which repackages the vendored plugin for non-Claude hosts off a pipx engine.

Build hook fires for `python -m build --wheel` / `--sdist` and for
PEP 660 editable installs (`pip install -e .`). The actual copy lives in the
importable, unit-tested `dekspec._build_vendoring.materialize_vendored`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

_PROJECT_ROOT = Path(__file__).resolve().parent
# Make the package importable at build time so we can reuse the vendoring
# helper (the package sources live under tooling/ per pyproject packages.find).
sys.path.insert(0, str(_PROJECT_ROOT / "tooling"))


class VendoringBuildPy(build_py):
    """build_py subclass that materializes `tooling/dekspec/_vendored/`
    from the project-root vendored sources before the standard copy runs.
    """

    def run(self) -> None:  # type: ignore[override]
        from dekspec._build_vendoring import materialize_vendored

        materialize_vendored(
            _PROJECT_ROOT, _PROJECT_ROOT / "tooling" / "dekspec" / "_vendored"
        )
        super().run()


setup(cmdclass={"build_py": VendoringBuildPy})
