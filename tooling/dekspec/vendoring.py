"""Vendoring manifest, drift detection, and atomic upgrade.

The DekSpec library publishes templates + methodology docs that consumer
repos can optionally vendor on disk to override the wheel-bundled
defaults. Since v0.91.0 (INT-097) the wheel is self-contained — templates
and docs resolve via `dekspec resource template <name>` /
`dekspec resource doc <name>` with the consumer-fs copy winning when
present. `dekspec repo upgrade` refreshes the on-disk copies for
consumers who want them. Skills/commands/agents ship exclusively through
the Claude Code plugin (`claude plugin install dekspec@dekspec`) and
never travel through the vendoring path. After upgrading, consumers can
run `dekspec audit doctor` to check for drift between any on-disk
vendored copies and the installed library.

`dekspec upgrade <version>` atomically bumps the engine pin in
`pyproject.toml` AND refreshes vendored content from the same version
tag, so engine + vendored content cannot drift apart on the happy path.

Vendoring layout:

  Library source                            Consumer destination
  --------------                            --------------------
  templates/...                             dekspec/templates/...
  docs/dekspec-operating-guide.md           dekspec/dekspec-operating-guide.md
  docs/dekspec-quick-reference.md           dekspec/dekspec-quick-reference.md
  docs/dekspec-methodology.md               dekspec/dekspec-methodology.md
  docs/architecture-frameworks-reference.md dekspec/architecture-frameworks-reference.md
  docs/architecture.md                      dekspec/architecture.md
  docs/cli-reference.md                     dekspec/cli-reference.md
  docs/EXAMPLES.md                          dekspec/EXAMPLES.md
  docs/amendment-log-types.md               dekspec/amendment-log-types.md

Snapshot-based pruning: on every vendor, a `.dekspec-vendor-manifest`
file is written listing every consumer-relative path the library
shipped. On the next vendor, files in the *prior* manifest that are not
in the *new* manifest are deleted; files outside the manifest (e.g.,
user-authored entries in `dekspec/templates/`) are never touched. This
replaces the older `rsync --delete` sweep, which would also wipe
user-authored content.

Drift kinds:
  - 'modified' : both files exist, contents differ
  - 'missing'  : library has it, consumer doesn't
  - 'unknown'  : consumer has a file under the vendored prefix that
                 doesn't exist in the library (rare; previous version
                 vendored a file the new version retired)
  - 'version'  : .dekspec-version differs from the installed library version
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterator

from . import __version__

DEFAULT_REPO_URL = "https://github.com/Dektora/dekspec.git"

# Vendored prefix roots in the consumer repo. Used by `compute_drift()` to
# emit 'unknown' findings for files inside these trees that the library
# doesn't ship. Pruning during vendoring is *not* prefix-wide: see
# `_load_vendor_manifest` / `_save_vendor_manifest` for the per-file
# snapshot mechanism that protects user-authored entries.
_DRIFT_PREFIXES_CONSUMER = (
    Path("dekspec") / "templates",
)

# Sibling of `.dekspec-version`. Each install writes a sorted list of every
# consumer-relative path the library shipped, one per line. On the next
# install, files in the *prior* manifest that aren't in the *new* manifest
# are deleted; entries outside the manifest (user-authored templates, etc.)
# are never touched.
_VENDOR_MANIFEST_FILENAME = ".dekspec-vendor-manifest"


@dataclass
class DriftFinding:
    kind: str  # 'modified' | 'missing' | 'unknown' | 'version' | 'library-missing-content' | 'reference-unreliable' | 'engine-stale-vs-vendored'
    library_path: str | None  # absolute path to library source-of-truth (None for 'unknown')
    consumer_path: str  # absolute path inside the consumer repo
    detail: str  # human-readable detail (sha mismatch / version mismatch / etc)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _resolve_library_root(here: Path, env_override: str | None) -> Path:
    """Pure resolution logic for `library_root()`. Separated so tests can
    exercise the layout-preference rules against synthetic filesystem
    fixtures without monkeypatching the module-level `__file__`.

    `here` is the directory containing this module (i.e., the resolved
    `Path(__file__).parent` of `vendoring.py`).
    """
    if env_override:
        return Path(env_override).resolve()
    source_root = here.parent.parent
    if (source_root / "templates").is_dir():
        return source_root
    vendored = here / "_vendored"
    if (vendored / "templates").is_dir():
        return vendored
    return source_root


def library_root() -> Path:
    """Path to the dekspec library source root (the directory containing
    `templates/` and `docs/`).

    Resolution order:
      1. `DEKSPEC_LIBRARY_ROOT` env var (escape hatch for any layout where
         the auto-detection below picks the wrong path; see
         ds-verify-vendored-false-positive-when-installed-fr-c2l).
      2. `Path(__file__).resolve().parent.parent.parent` if its `templates/`
         exists (source-checkout / editable-install layout — the parent of
         `tooling/` is the project root).
      3. `Path(__file__).resolve().parent / "_vendored"` if its `templates/`
         exists (wheel-install layout — `_vendored/` is populated at build
         time by `setup.py::VendoringBuildPy`; closes ds-md9).
      4. Fallback: source-checkout path (parent of `tooling/`) even if
         `templates/` is missing there. `library_has_vendored_content()`
         will then return False and drift detection short-circuits cleanly.
    """
    override = os.environ.get("DEKSPEC_LIBRARY_ROOT", "").strip() or None
    return _resolve_library_root(Path(__file__).resolve().parent, override)


def library_has_vendored_content(lib_root: Path | None = None) -> bool:
    """Whether the library root carries the vendored content directory
    (`templates/`) that drift detection depends on.

    Returns False when dekspec is wheel-installed (pip / pipx) without
    `DEKSPEC_LIBRARY_ROOT` set, since the wheel does not ship the
    vendored content. Drift detection short-circuits in that case to
    avoid emitting N false-positive `unknown` findings.
    """
    lib = lib_root if lib_root is not None else library_root()
    return (lib / "templates").is_dir()


def resolve_skill_script(
    relpath: str,
    repo_root: Path | None = None,
    lib_root: Path | None = None,
) -> Path | None:
    """Resolve a skills-tree helper script (e.g. ``_lib/scripts/artifact_ops.py``)
    across the three layouts where dekspec lives: library source checkout,
    wheel `_vendored/` snapshot, and consumer repo.

    `relpath` is the path **below** the skills root — e.g.
    ``_lib/scripts/artifact_ops.py`` for the artifact-ops helper. Callers
    pass the same suffix regardless of layout; this function handles the
    prefix differences:

      1. ``<repo_root>/plugins/dekspec/skills/<relpath>`` — library
         self-dev (cwd IS the dekspec source tree).
      2. ``<library_root>/skills/<relpath>`` — wheel `_vendored/` layout
         (consumer with pip-installed dekspec). `_vendored/` strips the
         ``plugins/dekspec/`` prefix.
      3. ``<library_root>/plugins/dekspec/skills/<relpath>`` — source-
         checkout layout reached via `DEKSPEC_LIBRARY_ROOT` env override
         or `library_root()`'s source-tree branch from a non-library cwd.

    Returns the first hit as an absolute path, or ``None`` if no layout
    yields an existing file. Callers print a clear error on ``None``
    (the bare path doesn't help debugging since no one of the three
    fallbacks is canonical).
    """
    repo = repo_root if repo_root is not None else Path.cwd()
    lib = lib_root if lib_root is not None else library_root()
    candidates = [
        repo / "plugins" / "dekspec" / "skills" / relpath,
        lib / "skills" / relpath,
        lib / "plugins" / "dekspec" / "skills" / relpath,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


_VENDORED_DOC_NAMES = (
    "dekspec-operating-guide.md",
    "dekspec-quick-reference.md",
    "dekspec-methodology.md",
    "architecture-frameworks-reference.md",
    "architecture.md",
    "cli-reference.md",
    "EXAMPLES.md",
    "amendment-log-types.md",
)


def resolve_template(name: str, repo_root: Path | None = None) -> Path | None:
    """Resolve a template file by name (e.g. ``intent``, ``intent-template``,
    or ``intent-template.md``), with consumer-fs override winning over the
    wheel ``_vendored/templates/`` fallback (INT-097).

    Resolution order:

      1. ``<repo_root>/dekspec/templates/<resolved-name>`` — consumer customization.
      2. ``<library_root>/templates/<resolved-name>`` — wheel ``_vendored/`` or
         source-checkout, via :func:`library_root`.

    Returns the first hit as an absolute :class:`Path`, or ``None`` when
    neither layout carries the named file. Name normalization: the
    ``-template`` suffix is appended when ``name`` does not already end with
    it AND does not already end with ``.md`` (so ``intent`` →
    ``intent-template.md``, ``intent-template`` → ``intent-template.md``,
    ``intent-template.md`` → ``intent-template.md``).
    """
    if not name.endswith(".md") and not name.endswith("-template"):
        name = f"{name}-template"
    if not name.endswith(".md"):
        name = f"{name}.md"
    repo = repo_root if repo_root is not None else Path.cwd()
    consumer = repo / "dekspec" / "templates" / name
    if consumer.is_file():
        return consumer.resolve()
    lib_template = library_root() / "templates" / name
    if lib_template.is_file():
        return lib_template.resolve()
    return None


def resolve_doc(name: str, repo_root: Path | None = None) -> Path | None:
    """Resolve a methodology doc file by name (e.g. ``operating-guide``,
    ``dekspec-operating-guide``, or ``dekspec-operating-guide.md``), with
    consumer-fs override winning over the wheel ``_vendored/docs/`` fallback
    (INT-097).

    Resolution order:

      1. ``<repo_root>/dekspec/<resolved-name>.md`` — consumer customization
         (vendored copy at the canonical consumer path).
      2. ``<library_root>/docs/<resolved-name>.md`` — wheel ``_vendored/``
         or source-checkout, via :func:`library_root`.

    Returns the first hit as an absolute :class:`Path`, or ``None`` when
    neither layout carries the named file. The ``.md`` suffix is appended
    automatically. The ``dekspec-`` prefix is also appended when ``name``
    matches the trailing form of one of the canonical doc names — e.g.
    ``operating-guide`` resolves to ``dekspec-operating-guide.md``.
    """
    if not name.endswith(".md"):
        name = f"{name}.md"
    if name not in _VENDORED_DOC_NAMES:
        prefixed = f"dekspec-{name}"
        if prefixed in _VENDORED_DOC_NAMES:
            name = prefixed
    repo = repo_root if repo_root is not None else Path.cwd()
    consumer = repo / "dekspec" / name
    if consumer.is_file():
        return consumer.resolve()
    lib_doc = library_root() / "docs" / name
    if lib_doc.is_file():
        return lib_doc.resolve()
    return None


def iter_vendored_pairs(
    lib_root: Path | None = None,
    repo_root: Path | None = None,
) -> Iterator[tuple[Path, Path]]:
    """Yield (library_source_path, consumer_destination_path) for every
    file the install script vendors. Both paths are absolute.

    Skills/commands/agents are delivered via the Claude Code plugin and
    are not enumerated here.

    repo_root defaults to cwd if not provided.
    """
    lib = lib_root if lib_root is not None else library_root()
    repo = repo_root if repo_root is not None else Path.cwd()

    # Templates: templates/... → dekspec/templates/...
    templates_src = lib / "templates"
    if templates_src.exists():
        for path in sorted(templates_src.rglob("*")):
            if path.is_file():
                rel = path.relative_to(templates_src)
                yield path, repo / "dekspec" / "templates" / rel

    # Methodology docs (cherry-picked single files)
    for doc_name in _VENDORED_DOC_NAMES:
        src = lib / "docs" / doc_name
        if src.exists():
            yield src, repo / "dekspec" / doc_name


def _load_vendor_manifest(repo_root: Path) -> set[Path]:
    """Load the prior install's vendor manifest as a set of absolute paths.

    Returns an empty set if no manifest exists (first install, or a
    pre-snapshot upgrade). Lines are consumer-relative; we resolve them
    against repo_root.
    """
    manifest_path = repo_root / _VENDOR_MANIFEST_FILENAME
    if not manifest_path.exists():
        return set()
    prior: set[Path] = set()
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        prior.add((repo_root / line).resolve())
    return prior


def _save_vendor_manifest(repo_root: Path, vendored: set[Path]) -> None:
    """Write the new install's vendor manifest. One consumer-relative path
    per line, sorted, ASCII-only file."""
    manifest_path = repo_root / _VENDOR_MANIFEST_FILENAME
    rels = sorted(
        str(p.relative_to(repo_root.resolve())) for p in vendored
    )
    body = (
        "# Files vendored by dekspec — managed by `dekspec upgrade`.\n"
        "# Used for snapshot-based pruning on upgrade.\n"
        "# Do not edit by hand.\n"
    )
    body += "\n".join(rels) + "\n"
    manifest_path.write_text(body, encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _library_reference_is_release(lib_root: Path) -> tuple[bool, str]:
    """Whether `lib_root` is a trustworthy *release* reference for drift checks.

    Returns ``(is_release, reason)``. A reference is NOT a release when it is a
    git checkout whose vendored surfaces (`docs/`, `templates/`) diverge from
    the `v<__version__>` tag — i.e. a development checkout carrying unreleased
    or uncommitted changes. Comparing a consumer's vendored content against
    such a moving reference reports false drift: the consumer is fine, the
    library checkout is simply ahead of any release. `dekspec upgrade` does not
    hit this because it vendors from the pinned release tag, not the checkout.

    Non-git roots (wheel / pipx `_vendored/`, synthetic test libraries) are
    always treated as releases — a wheel's `_vendored/` snapshot corresponds to
    the wheel's published version by construction.
    """
    if not (lib_root / ".git").exists():
        return True, ""
    tag = f"v{__version__}"
    rev = subprocess.run(
        ["git", "-C", str(lib_root), "rev-parse", "-q", "--verify",
         f"refs/tags/{tag}"],
        capture_output=True, text=True,
    )
    if rev.returncode != 0:
        return False, (
            f"the dekspec library reference is a git checkout at {lib_root} "
            f"with no {tag} tag — it is ahead of any published release"
        )
    diff = subprocess.run(
        ["git", "-C", str(lib_root), "diff", "--quiet", tag, "--",
         "docs", "templates"],
        capture_output=True,
    )
    if diff.returncode != 0:
        return False, (
            f"the dekspec library reference is a development checkout at "
            f"{lib_root} whose docs/ or templates/ diverge from its {tag} tag "
            f"(uncommitted or unreleased changes)"
        )
    return True, ""


def compute_drift(
    repo_root: Path,
    lib_root: Path | None = None,
) -> list[DriftFinding]:
    """Walk the canonical vendoring manifest and report drift.

    Reports modified/missing files, version mismatch, and (best-effort)
    'unknown' files in `.claude/skills/`, `dekspec/templates/`, and the
    cherry-picked dekspec/*.md methodology files that don't appear in
    the current library manifest.

    When the library reference is a development checkout that does not
    correspond to a published release (see `_library_reference_is_release`),
    file-level drift is NOT computed — a single `reference-unreliable` finding
    is returned instead, since cross-reference diffing would report false
    drift.
    """
    lib = lib_root if lib_root is not None else library_root()

    # Fail-fast safety net: if the library root has no `templates/`, the
    # verifier can't compute drift and would otherwise silently emit N
    # false-positive `unknown` findings (one per file under the consumer's
    # vendored prefixes). Return a single explanatory finding instead.
    # Common trigger: dekspec wheel-installed (pip / pipx) without
    # DEKSPEC_LIBRARY_ROOT set — the wheel does not ship the vendored
    # content.
    if not library_has_vendored_content(lib):
        return [DriftFinding(
            kind="library-missing-content",
            library_path=str(lib),
            consumer_path=str(repo_root),
            detail=(
                f"library root {lib} has no templates/ subdirectory. "
                f"This typically means dekspec is wheel-installed (pip / pipx); the "
                f"wheel does not ship the vendored content. "
                f"Workaround: set DEKSPEC_LIBRARY_ROOT to a path containing templates/ "
                f"(e.g., a source checkout of Dektora/dekspec)."
            ),
        )]

    # Engine-stale guard: when the installed dekspec CLI is older than the
    # consumer's vendored content (e.g., `dekspec repo upgrade` vendored
    # 0.97.0 content but the PATH-resolved engine is still 0.95.0 because
    # the consumer has no dekspec pin in pyproject.toml), every per-file
    # hash will mismatch — the installed wheel's library reference is from
    # the OLDER release. Short-circuit with a single explanatory finding
    # instead of N false-positive `modified` findings.
    # (ds-upgrade-manifest-not-regenerated-3osq, 2026-05-28)
    marker = repo_root / ".dekspec-version"
    if marker.exists():
        vendored_version = marker.read_text(encoding="utf-8").strip()
        if vendored_version and vendored_version != __version__:
            return [DriftFinding(
                kind="engine-stale-vs-vendored",
                library_path=str(lib),
                consumer_path=str(repo_root),
                detail=(
                    f"Consumer vendored content is at {vendored_version} but "
                    f"the installed dekspec engine is {__version__}. File-level "
                    f"drift was NOT computed: comparing newer vendored content "
                    f"against an older installed library reports false drift. "
                    f"Upgrade the engine (pipx upgrade dekspec, pip install "
                    f"--upgrade dekspec, or the equivalent for your install "
                    f"method) so it matches the vendored version, or downgrade "
                    f"vendored content via `dekspec repo upgrade v{__version__}`."
                ),
            )]

    # Reference-reliability guard: a development checkout ahead of its
    # release tag is not a valid drift reference — diffing against it
    # reports false drift. Short-circuit with a single explanatory finding.
    is_release, ref_reason = _library_reference_is_release(lib)
    if not is_release:
        marker = repo_root / ".dekspec-version"
        consumer_version = (
            marker.read_text(encoding="utf-8").strip()
            if marker.exists() else None
        )
        cv = (
            f"Consumer pinned dekspec {consumer_version}; "
            if consumer_version else ""
        )
        return [DriftFinding(
            kind="reference-unreliable",
            library_path=str(lib),
            consumer_path=str(repo_root),
            detail=(
                f"{cv}{ref_reason}. File-level vendoring drift was NOT "
                f"computed: diffing vendored content against a non-release "
                f"library reference reports false drift. Run "
                f"`dekspec upgrade --dry-run` for the version-accurate "
                f"vendoring check (it vendors from the pinned release tag), "
                f"or `dekspec upgrade` to re-sync."
            ),
        )]

    findings: list[DriftFinding] = []
    expected_consumer_paths: set[Path] = set()

    for src, dst in iter_vendored_pairs(lib_root=lib, repo_root=repo_root):
        expected_consumer_paths.add(dst.resolve())
        if not dst.exists():
            findings.append(DriftFinding(
                kind="missing",
                library_path=str(src),
                consumer_path=str(dst),
                detail="vendored file absent from consumer repo (library publishes it)",
            ))
            continue
        src_hash = _sha256(src)
        dst_hash = _sha256(dst)
        if src_hash != dst_hash:
            findings.append(DriftFinding(
                kind="modified",
                library_path=str(src),
                consumer_path=str(dst),
                detail=f"sha256 mismatch (library={src_hash[:12]}... consumer={dst_hash[:12]}...)",
            ))

    # Best-effort 'unknown' detection: walk the consumer's vendored prefix
    # and flag any file that the library doesn't ship. Note: files added
    # by the consumer (e.g., custom templates) will still surface as
    # 'unknown'; that's the intended signal — they're present under a
    # library-managed prefix and the consumer should know.
    for prefix in _DRIFT_PREFIXES_CONSUMER:
        full = repo_root / prefix
        if not full.exists():
            continue
        for path in full.rglob("*"):
            if not path.is_file():
                continue
            if path.resolve() not in expected_consumer_paths:
                findings.append(DriftFinding(
                    kind="unknown",
                    library_path=None,
                    consumer_path=str(path),
                    detail="present in consumer but not in current library manifest",
                ))

    # Version marker check (.dekspec-version)
    version_marker = repo_root / ".dekspec-version"
    if version_marker.exists():
        installed = version_marker.read_text(encoding="utf-8").strip()
        if installed != __version__:
            findings.append(DriftFinding(
                kind="version",
                library_path=None,
                consumer_path=str(version_marker),
                detail=(
                    f"consumer pinned to dekspec {installed}, library is {__version__}. "
                    f"Run `dekspec repo upgrade` or `pip install --upgrade dekspec` "
                    f"to refresh."
                ),
            ))
    else:
        findings.append(DriftFinding(
            kind="version",
            library_path=None,
            consumer_path=str(version_marker),
            detail=(
                ".dekspec-version marker missing. Either this repo was vendored "
                "pre-v0.4.x (pre-marker) or never vendored at all. "
                "Run `dekspec repo upgrade` to refresh."
            ),
        ))

    return findings


# --------------------------------------------------------------------------- #
# Upgrade orchestration
# --------------------------------------------------------------------------- #


class UpgradeError(Exception):
    """Raised when `upgrade_to` cannot complete cleanly."""


@dataclass
class UpgradeReport:
    """Summary of an upgrade run, returned by `upgrade_to`."""
    target_version: str
    pyproject_updated: bool
    pyproject_path: str | None
    pyproject_old_version: str | None
    files_written: int
    files_unchanged: int
    files_removed: int
    version_marker_written: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReconcileReport:
    """Summary of a reconcile run, returned by `reconcile`.

    Reconcile is the network-free, wheel-sourced counterpart to
    `upgrade_to`: it vendors content from the INSTALLED library
    (`library_root()` — the wheel's `_vendored/` snapshot or, in a source
    checkout, the project root) into the consumer repo and rewrites the
    `.dekspec-version` marker. No git clone, no pip, no version resolution.
    """
    target_version: str
    baseline_version: str | None
    files_written: int
    files_unchanged: int
    files_removed: int
    version_marker_written: bool
    noop: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reconcile(
    repo_root: Path,
    target_version: str,
    *,
    dry_run: bool = False,
    lib_root: Path | None = None,
) -> ReconcileReport:
    """Reconcile the consumer repo to the already-installed library version.

    This is the engine behind `dekspec library sync`. Unlike `upgrade_to`
    it performs NO acquisition: no git clone, no network, no pip, no version
    resolution. Content is sourced from the INSTALLED library tree
    (`library_root()` — the wheel's `_vendored/` snapshot, or the source
    checkout when running from the library repo itself), the same resolution
    `dekspec resource` uses (INT-097).

    Steps:
      1. Determine the consumer's current `.dekspec-version` baseline.
      2. Idempotent short-circuit: if the baseline already equals
         `target_version` AND every vendored file is already in sync,
         return a no-op report without writing anything destructive.
      3. Otherwise vendor the installed content into the consumer repo
         (snapshot-based prune, never touching user-authored files).
      4. Rewrite the `.dekspec-version` marker to `target_version`.

    In dry-run mode no files are modified; the report reflects what would
    happen. `lib_root` overrides the installed-library resolution (test hook
    / `DEKSPEC_LIB_ROOT_OVERRIDE` env var), mirroring `upgrade_to`.
    """
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise UpgradeError(f"consumer repo root does not exist: {repo_root}")

    if lib_root is None:
        env_override = os.environ.get("DEKSPEC_LIB_ROOT_OVERRIDE", "").strip()
        if env_override:
            lib_root = Path(env_override)
    lib = (lib_root.resolve() if lib_root is not None else library_root())

    marker = repo_root / ".dekspec-version"
    baseline = (
        marker.read_text(encoding="utf-8").strip()
        if marker.exists()
        else None
    )

    # Idempotent short-circuit: marker already at target AND no content drift.
    if baseline == target_version:
        drift = any(
            not (dst.exists() and _sha256(src) == _sha256(dst))
            for src, dst in iter_vendored_pairs(lib_root=lib, repo_root=repo_root)
        )
        if not drift:
            return ReconcileReport(
                target_version=target_version,
                baseline_version=baseline,
                files_written=0,
                files_unchanged=0,
                files_removed=0,
                version_marker_written=False,
                noop=True,
            )

    files_written, files_unchanged, files_removed = vendor_from(
        lib, repo_root, dry_run=dry_run,
    )
    marker_written = _write_version_marker(
        repo_root, target_version, dry_run=dry_run
    )
    return ReconcileReport(
        target_version=target_version,
        baseline_version=baseline,
        files_written=files_written,
        files_unchanged=files_unchanged,
        files_removed=files_removed,
        version_marker_written=marker_written,
        noop=False,
    )


# ds-u3w: three pin shapes seen in the wild. The bump preserves the shape
# (range→range, exact→exact, url→url) — never rewrites between forms.
#
# Shape 1 (URL):   dekspec @ git+https://github.com/Dektora/dekspec.git@v0.51.1
# Shape 2 (RANGE): "dekspec>=0.51.1,<0.52.0"      ← Cloudsmith / standard pin
# Shape 3 (EXACT): "dekspec==0.51.1"               ← pinned-deps style
#
# Match order: URL → RANGE → EXACT. A pyproject.toml is expected to carry
# exactly one dekspec pin; if multiple are present (rare), the first matched
# shape wins.

_PYPROJECT_PIN_URL_RE = re.compile(
    r"(dekspec\s*@\s*git\+https?://[^@\s\"']+\.git\s*@\s*v?)(\d+\.\d+\.\d+)",
)
_PYPROJECT_PIN_RANGE_RE = re.compile(
    r"(dekspec)(>=)(\d+\.\d+\.\d+)(\s*,\s*<)(\d+\.\d+\.\d+)",
)
_PYPROJECT_PIN_EXACT_RE = re.compile(
    r"(dekspec)(==)(\d+\.\d+\.\d+)",
)


def _next_minor_ceiling(version: str) -> str:
    """`0.51.1` → `0.52.0`. The "<X.(Y+1).0" upper bound a RANGE pin moves to
    when the lower bound is bumped to `version`."""
    parts = version.split(".")
    return f"{parts[0]}.{int(parts[1]) + 1}.0"


def bump_pyproject_pin(
    repo_root: Path,
    target_version: str,
    *,
    dry_run: bool = False,
) -> tuple[bool, str | None, str | None]:
    """Update the dekspec dependency pin in `pyproject.toml`.

    Recognizes three pin shapes (see module-level regex docs). Preserves
    the original shape — bumping a `>=,<` pin produces a `>=,<` pin (with
    the upper bound rolled to the next-minor ceiling); bumping an `==`
    produces an `==`; bumping a `git+https` direct-URL produces a direct-URL.

    Returns (changed, pyproject_path, old_version).
    - changed: True if the pin moved to target_version (or would, in dry-run).
    - pyproject_path: absolute path string, or None if no pyproject.toml.
    - old_version: the previous pin's lower-bound / exact / url-tag value,
      or None if no recognizable pin was found.

    Idempotent: if the pin is already at target_version, returns
    (False, path, target_version).
    """
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return False, None, None
    text = pyproject.read_text(encoding="utf-8")

    # Try each shape in order: URL → RANGE → EXACT.
    m = _PYPROJECT_PIN_URL_RE.search(text)
    if m:
        old_version = m.group(2)
        if old_version == target_version:
            return False, str(pyproject), old_version
        new_text = _PYPROJECT_PIN_URL_RE.sub(
            lambda mm: mm.group(1) + target_version, text
        )
        if not dry_run:
            pyproject.write_text(new_text, encoding="utf-8")
        return True, str(pyproject), old_version

    m = _PYPROJECT_PIN_RANGE_RE.search(text)
    if m:
        old_version = m.group(3)
        if old_version == target_version:
            # Already at target on the lower bound. Leave alone (upper bound
            # is operator's call — they may have widened it intentionally).
            return False, str(pyproject), old_version
        new_upper = _next_minor_ceiling(target_version)
        new_text = _PYPROJECT_PIN_RANGE_RE.sub(
            lambda mm: (
                mm.group(1)
                + mm.group(2)
                + target_version
                + mm.group(4)
                + new_upper
            ),
            text,
        )
        if not dry_run:
            pyproject.write_text(new_text, encoding="utf-8")
        return True, str(pyproject), old_version

    m = _PYPROJECT_PIN_EXACT_RE.search(text)
    if m:
        old_version = m.group(3)
        if old_version == target_version:
            return False, str(pyproject), old_version
        new_text = _PYPROJECT_PIN_EXACT_RE.sub(
            lambda mm: mm.group(1) + mm.group(2) + target_version,
            text,
        )
        if not dry_run:
            pyproject.write_text(new_text, encoding="utf-8")
        return True, str(pyproject), old_version

    return False, str(pyproject), None


# Back-compat alias — some tests / external callers reference the old name.
_PYPROJECT_PIN_RE = _PYPROJECT_PIN_URL_RE


def cleanup_legacy_skill_layout(
    repo_root: Path,
    *,
    dry_run: bool = False,
) -> tuple[list[Path], list[Path]]:
    """One-shot migration from the pre-plugin skill layout.

    Older releases vendored skills into `dekspec/skills/<name>/` and
    created `.claude/skills/<name>` directory-level symlinks pointing
    back. Skills are now delivered exclusively via the Claude Code
    plugin (`claude plugin install dekspec@dekspec`), so both locations
    are obsolete and (worse) shadow the plugin's surface.

    Cleanup rules — never touch user-authored entries:

      `.claude/skills/<name>`:
        Removed only if it's a symlink pointing at `../../dekspec/skills/<name>`
        (the canonical legacy shim target). Real directories and symlinks
        pointing elsewhere are left alone — those were authored by the
        consumer, not the install script.

      `dekspec/skills/<name>`:
        Removed only if its name appears in the prior vendor manifest
        (sibling `.dekspec-vendor-manifest`) — meaning the entry was
        library-shipped on the last install. Entries the consumer added
        post-install are not in the manifest and survive.

      `dekspec/skills/` (the directory itself):
        Removed if empty after cleanup. Otherwise left in place with
        whatever user-authored content remains.

    Returns (removed_shims, removed_canonical_dirs) — both lists may be
    empty. In dry-run mode the lists describe what *would* be removed.
    """
    removed_shims: list[Path] = []
    removed_canonical_dirs: list[Path] = []

    # 1. Legacy `.claude/skills/<name>` shim symlinks.
    shim_root = repo_root / ".claude" / "skills"
    if shim_root.is_dir():
        for entry in sorted(shim_root.iterdir()):
            if not entry.is_symlink():
                continue
            try:
                target = os.readlink(entry)
            except OSError:
                continue
            expected = f"../../dekspec/skills/{entry.name}"
            if target == expected:
                removed_shims.append(entry)
                if not dry_run:
                    entry.unlink()

    # 2. Legacy `dekspec/skills/<name>` directories that the prior install
    #    shipped. The prior vendor manifest is the source of truth — entries
    #    listed there were library content; everything else is user-authored.
    canonical_root = repo_root / "dekspec" / "skills"
    if canonical_root.is_dir():
        prior = _load_vendor_manifest(repo_root)
        prior_skill_names: set[str] = set()
        skill_prefix = (repo_root / "dekspec" / "skills").resolve()
        for entry in prior:
            try:
                rel = entry.relative_to(skill_prefix)
            except ValueError:
                continue
            if rel.parts:
                prior_skill_names.add(rel.parts[0])

        for skill_dir in sorted(canonical_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            if skill_dir.name not in prior_skill_names:
                continue
            removed_canonical_dirs.append(skill_dir)
            if not dry_run:
                shutil.rmtree(skill_dir)

        if not dry_run and canonical_root.exists() and not any(canonical_root.iterdir()):
            canonical_root.rmdir()

    return removed_shims, removed_canonical_dirs


def migrate_legacy_directories(
    repo_root: Path,
    *,
    dry_run: bool = False,
) -> None:
    """One-shot migration from the legacy api-contracts directory.

    In older releases, the Interface Contract directory was named
    `dekspec/api-contracts/`. It has been renamed to `dekspec/interface-contracts/`
    to align with the proper domain kind name. This renames the directory
    safely using git mv when tracked in git to preserve history, otherwise
    falls back to shutil.move().
    """
    legacy_ic_dir = repo_root / "dekspec" / "api-contracts"
    new_ic_dir = repo_root / "dekspec" / "interface-contracts"

    if legacy_ic_dir.is_dir() and not new_ic_dir.is_dir():
        if dry_run:
            print("  [dry-run] would rename dekspec/api-contracts/ -> dekspec/interface-contracts/")
            return

        is_git = False
        try:
            res = subprocess.run(
                ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                text=True,
                check=False,
            )
            is_git = res.returncode == 0
        except Exception:
            pass

        is_tracked = False
        if is_git:
            try:
                res = subprocess.run(
                    ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", "dekspec/api-contracts"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                is_tracked = res.returncode == 0
            except Exception:
                pass

        if is_tracked:
            try:
                subprocess.run(
                    ["git", "-C", str(repo_root), "mv", "dekspec/api-contracts", "dekspec/interface-contracts"],
                    check=True,
                    capture_output=True,
                )
                print("  Renamed dekspec/api-contracts/ -> dekspec/interface-contracts/ (git mv, history preserved)")
            except Exception as e:
                shutil.move(str(legacy_ic_dir), str(new_ic_dir))
                print(f"  Renamed dekspec/api-contracts/ -> dekspec/interface-contracts/ (git mv failed, fallback to move: {e})")
        else:
            shutil.move(str(legacy_ic_dir), str(new_ic_dir))
            print("  Renamed dekspec/api-contracts/ -> dekspec/interface-contracts/")

    elif legacy_ic_dir.is_dir() and new_ic_dir.is_dir():
        print(
            "  WARNING: both dekspec/api-contracts/ and dekspec/interface-contracts/ exist.\n"
            "  The IC directory was renamed; merge any files from api-contracts/ into\n"
            "  interface-contracts/ by hand, then remove the stale api-contracts/ dir.",
            file=sys.stderr,
        )


def vendor_from(
    lib_root: Path,
    repo_root: Path,
    *,
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Copy all vendored files from `lib_root` into `repo_root`.

    Pruning is snapshot-based: only files that appear in the *prior*
    vendor manifest (`.dekspec-vendor-manifest`) but not in the *new*
    library manifest are removed. User-authored files inside vendored
    prefixes are never touched — they were never in the prior manifest.

    Behaviour:
    - Templates land in `dekspec/templates/...`.
    - Methodology docs land in `dekspec/<doc>.md` (cherry-picked).
    - After vendoring, the new manifest is written for the next install
      to read.
    - Legacy skill artifacts (pre-plugin layout) are also cleaned up via
      `cleanup_legacy_skill_layout()`.

    Returns (files_written, files_unchanged, files_removed). In dry-run
    mode no files are modified; counts reflect what would happen.
    """
    files_written = 0
    files_unchanged = 0
    files_removed = 0

    new_manifest: set[Path] = set()

    for src, dst in iter_vendored_pairs(lib_root=lib_root, repo_root=repo_root):
        new_manifest.add(dst.resolve())
        if dst.exists() and _sha256(src) == _sha256(dst):
            files_unchanged += 1
            continue
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        files_written += 1

    # Snapshot-based prune: anything in the prior manifest that's not in
    # the new manifest gets removed. Files outside the prior manifest
    # (user-authored, etc.) are never deleted.
    prior_manifest = _load_vendor_manifest(repo_root)
    for stale in sorted(prior_manifest - new_manifest):
        try:
            relative_marker = stale.relative_to(repo_root.resolve())
        except ValueError:
            # Path escaped the repo (shouldn't happen for sane manifests);
            # skip rather than risk removing something outside the tree.
            continue
        if not stale.exists():
            continue
        if not dry_run:
            stale.unlink()
            # Walk parents upward, pruning any now-empty directory inside
            # the consumer's dekspec/ prefix.
            parent = stale.parent
            stop = (repo_root / relative_marker.parts[0]).resolve()
            while parent != stop and parent != repo_root.resolve():
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
        files_removed += 1

    # One-shot migration: clean up legacy `dekspec/skills/` + `.claude/skills/`
    # shim layout from pre-plugin releases.
    cleanup_legacy_skill_layout(repo_root, dry_run=dry_run)

    # One-shot directory migration: api-contracts -> interface-contracts
    migrate_legacy_directories(repo_root, dry_run=dry_run)

    if not dry_run:
        _save_vendor_manifest(repo_root, new_manifest)

    return files_written, files_unchanged, files_removed


def _clone_library_at(
    target_version: str,
    repo_url: str,
    dest: Path,
) -> None:
    """Shallow-clone the dekspec repo at tag v<target_version> into dest.

    Raises UpgradeError on failure.
    """
    tag = f"v{target_version}"
    cmd = [
        "git", "clone", "--quiet", "--depth", "1",
        "--branch", tag, repo_url, str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise UpgradeError(
            f"git clone failed for {repo_url}@{tag}:\n"
            f"  stdout: {proc.stdout.strip()}\n"
            f"  stderr: {proc.stderr.strip()}"
        )


def extract_changelog_section(
    changelog_path: Path,
    target_version: str,
) -> str | None:
    """Return the body of `## [vX.Y.Z]` section from CHANGELOG.md, or None
    if no such heading exists. The body runs from the line AFTER the heading
    to the line BEFORE the next `## [` heading. Whitespace-trimmed."""
    if not changelog_path.is_file():
        return None
    target = target_version.lstrip("v")
    text = changelog_path.read_text(encoding="utf-8")
    in_section = False
    body_lines: list[str] = []
    for line in text.splitlines():
        if in_section and line.startswith("## ["):
            break
        if in_section:
            body_lines.append(line)
            continue
        if line.startswith("## [v") and target in line:
            # Match `## [vX.Y.Z]` or `## [vX.Y.Z] — DATE`.
            if line.startswith(f"## [v{target}]"):
                in_section = True
    if not in_section:
        return None
    return "\n".join(body_lines).strip()


_BREAKING_RE = re.compile(r"(^|[^A-Za-z0-9])BREAKING([^A-Za-z0-9]|$)|⚠ BREAKING")


def section_is_breaking(section_body: str | None) -> bool:
    """Return True if the CHANGELOG section body contains a BREAKING marker.
    Mirrors the release-skill classifier's major arm regex so the same
    sources of truth apply at upgrade-target time."""
    if not section_body:
        return False
    return bool(_BREAKING_RE.search(section_body))


def upgrade_to(
    repo_root: Path,
    target_version: str,
    *,
    repo_url: str = DEFAULT_REPO_URL,
    dry_run: bool = False,
    lib_root: Path | None = None,
) -> UpgradeReport:
    """Atomically upgrade the consumer repo to `target_version`.

    Steps:
      1. Clone the dekspec repo at v<target_version> to a temp dir (skipped
         if `lib_root` is supplied, which is used by tests).
      2. Bump the dekspec dependency pin in pyproject.toml (if present).
      3. Vendor the new content into the consumer repo.
      4. Write the new `.dekspec-version` marker.

    In dry-run mode, no files are modified; the returned report reflects
    what would happen.

    The temp clone is cleaned up on success or failure.
    """
    if not re.fullmatch(r"\d+\.\d+\.\d+", target_version):
        raise UpgradeError(
            f"target version must be SemVer X.Y.Z, got {target_version!r}"
        )
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise UpgradeError(f"consumer repo root does not exist: {repo_root}")

    pyproject_changed, pyproject_path, old_version = bump_pyproject_pin(
        repo_root, target_version, dry_run=dry_run,
    )

    # ds-a11: env-var override for the clone step, mirroring the kwarg-
    # based test hook. Lets the e2e smoke (which subprocesses the CLI)
    # point at a pre-staged library tree instead of doing a real git clone.
    if lib_root is None:
        env_override = os.environ.get("DEKSPEC_LIB_ROOT_OVERRIDE", "").strip()
        if env_override:
            lib_root = Path(env_override)

    if lib_root is not None:
        # Test path — caller provides a pre-staged library tree.
        files_written, files_unchanged, files_removed = vendor_from(
            lib_root.resolve(), repo_root, dry_run=dry_run,
        )
        marker_written = _write_version_marker(repo_root, target_version, dry_run=dry_run)
        return UpgradeReport(
            target_version=target_version,
            pyproject_updated=pyproject_changed,
            pyproject_path=pyproject_path,
            pyproject_old_version=old_version,
            files_written=files_written,
            files_unchanged=files_unchanged,
            files_removed=files_removed,
            version_marker_written=marker_written,
        )

    with tempfile.TemporaryDirectory(prefix="dekspec-upgrade-") as tmp:
        clone_dest = Path(tmp) / "dekspec"
        _clone_library_at(target_version, repo_url, clone_dest)
        files_written, files_unchanged, files_removed = vendor_from(
            clone_dest, repo_root, dry_run=dry_run,
        )
        marker_written = _write_version_marker(repo_root, target_version, dry_run=dry_run)

    return UpgradeReport(
        target_version=target_version,
        pyproject_updated=pyproject_changed,
        pyproject_path=pyproject_path,
        pyproject_old_version=old_version,
        files_written=files_written,
        files_unchanged=files_unchanged,
        files_removed=files_removed,
        version_marker_written=marker_written,
    )


def _write_version_marker(
    repo_root: Path,
    version: str,
    *,
    dry_run: bool = False,
) -> bool:
    """Write `.dekspec-version`. Returns True if the file was created or
    updated (or would be, in dry-run mode)."""
    marker = repo_root / ".dekspec-version"
    desired = f"{version}\n"
    if marker.exists() and marker.read_text(encoding="utf-8") == desired:
        return False
    if not dry_run:
        marker.write_text(desired, encoding="utf-8")
    return True
