"""Build-time materialization of `tooling/dekspec/_vendored/`.

Extracted from `setup.py` so the vendoring copy is unit-testable (INT-179).
Pure stdlib — no setuptools import — so a test can call it directly and the
build hook can import it with `tooling/` on `sys.path`.

`_vendored/` is what wheel-installed consumers consume via
`vendoring.library_root()` when no source-checkout layout is available. It
carries: templates, cherry-picked methodology docs, and — since ADR-045 — the
FULL plugin skill/command/hook tree, so `dekspec install --platform <host>`
works off a bare pip/pipx engine on a non-Claude host (ds-t50g). The file list
here is the canonical mirror of `vendoring.py::iter_vendored_pairs()` (templates
+ docs) plus the plugin tree; keep them in sync.
"""
from __future__ import annotations

import shutil
from pathlib import Path

# Cherry-picked docs that vendor to consumers. Mirror of the doc_name tuple
# inside vendoring.py::iter_vendored_pairs().
VENDORED_DOCS = (
    "dekspec-operating-guide.md",
    "dekspec-quick-reference.md",
    "architecture-frameworks-reference.md",
    "architecture.md",
    "cli-reference.md",
    "EXAMPLES.md",
    "amendment-log-types.md",
)

# Plugin subtrees vendored whole (ADR-045). `install --platform` repackages
# these for each non-Claude host; Claude keeps using the marketplace plugin.
_PLUGIN_SUBTREES = ("skills", "commands", "hooks")


def materialize_vendored(project_root: Path, vendored_root: Path) -> None:
    """Populate `vendored_root` from the project's vendored sources.

    Idempotent: each managed subtree is replaced wholesale. Absent sources are
    skipped (a partial checkout still builds).
    """
    project_root = Path(project_root)
    vendored_root = Path(vendored_root)
    vendored_root.mkdir(parents=True, exist_ok=True)

    # Templates: <root>/templates/** -> <vendored>/templates/**
    templates_dst = vendored_root / "templates"
    if templates_dst.exists():
        shutil.rmtree(templates_dst)
    templates_src = project_root / "templates"
    if templates_src.is_dir():
        shutil.copytree(templates_src, templates_dst)

    # Cherry-picked docs: <root>/docs/<name>.md -> <vendored>/docs/<name>.md
    docs_dst = vendored_root / "docs"
    if docs_dst.exists():
        shutil.rmtree(docs_dst)
    docs_dst.mkdir(parents=True, exist_ok=True)
    for doc_name in VENDORED_DOCS:
        src = project_root / "docs" / doc_name
        if src.is_file():
            shutil.copy2(src, docs_dst / doc_name)

    # Plugin tree (ADR-045): the FULL skills/ (including _lib), commands/, and
    # hooks/ — so `install --platform` off a pipx engine emits a complete
    # per-host tree, not just the marker.
    plugin_src = project_root / "plugins" / "dekspec"
    for sub in _PLUGIN_SUBTREES:
        dst = vendored_root / sub
        if dst.exists():
            shutil.rmtree(dst)
        src = plugin_src / sub
        if src.is_dir():
            shutil.copytree(src, dst)
