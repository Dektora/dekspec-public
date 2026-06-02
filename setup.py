"""Build hook that pre-populates `tooling/dekspec/_vendored/` from the
project-root `templates/` + cherry-picked `docs/` before standard build_py runs.

This is the wheel-bundling story for ds-md9 / INT-023 / IB-038. The
`_vendored/` content is what wheel-installed consumers consume via
`vendoring.library_root()` when no source-checkout layout is available.

Build hook fires for `python -m build --wheel` / `--sdist` and for
PEP 660 editable installs (`pip install -e .`). Source-checkout users who
edit `templates/<file>.md` directly and don't rebuild won't see their edits
reflected in `_vendored/` until the next build, but `library_root()`'s
resolution prefers the source-checkout layout when present, so the edits
ARE picked up via the source path — `_vendored/` only matters when the
source-checkout layout is unreachable.

The vendoring file list is the canonical mirror of
`tooling/dekspec/vendoring.py::iter_vendored_pairs()`. Keep them in sync.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

# Cherry-picked docs that vendor to consumers. Mirror of the doc_name tuple
# inside vendoring.py::iter_vendored_pairs().
_VENDORED_DOCS = (
    "dekspec-operating-guide.md",
    "dekspec-quick-reference.md",
    "architecture-frameworks-reference.md",
    "architecture.md",
    "cli-reference.md",
    "EXAMPLES.md",
    "amendment-log-types.md",
)


class VendoringBuildPy(build_py):
    """build_py subclass that materializes `tooling/dekspec/_vendored/`
    from the project-root vendored sources before the standard copy runs.
    """

    def run(self) -> None:  # type: ignore[override]
        project_root = Path(__file__).resolve().parent
        vendored_root = project_root / "tooling" / "dekspec" / "_vendored"

        # Templates: <root>/templates/*.md -> <vendored>/templates/*.md
        templates_src = project_root / "templates"
        templates_dst = vendored_root / "templates"
        if templates_dst.exists():
            shutil.rmtree(templates_dst)
        if templates_src.is_dir():
            shutil.copytree(templates_src, templates_dst)

        # Cherry-picked docs: <root>/docs/<name>.md -> <vendored>/docs/<name>.md
        docs_dst = vendored_root / "docs"
        if docs_dst.exists():
            shutil.rmtree(docs_dst)
        docs_dst.mkdir(parents=True, exist_ok=True)
        for doc_name in _VENDORED_DOCS:
            src = project_root / "docs" / doc_name
            if src.is_file():
                shutil.copy2(src, docs_dst / doc_name)

        # Skills: ONLY `_lib/` — the shared helpers + scripts the engine
        # imports at runtime (e.g., `dekspec._vendored.skills._lib.scripts
        # .artifact_ops`). User-facing skill bodies (write-*, archeology,
        # exec-coding-session, etc.) are NOT vendored — they ship
        # exclusively through the Claude Code plugin marketplace per
        # AE-006.
        skills_lib_src = project_root / "plugins" / "dekspec" / "skills" / "_lib"
        skills_lib_dst = vendored_root / "skills" / "_lib"
        skills_dst_root = vendored_root / "skills"
        if skills_dst_root.exists():
            shutil.rmtree(skills_dst_root)
        if skills_lib_src.is_dir():
            skills_dst_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skills_lib_src, skills_lib_dst)

        super().run()


setup(cmdclass={"build_py": VendoringBuildPy})
