"""LLM-free structural slice-discovery engine (ds-mrsu).

Walks a target repo's Python package tree, parses each ``.py`` with the
stdlib :mod:`ast` module (no LLM, no network — pure static analysis), builds
a directed intra-repo import graph, and clusters that graph by structural
modularity into dense-within / sparse-between communities. Each community is
emitted as a RAW slice dict and the array is written to
``<repo>/.dekspec/slices.json``.

Placement (ds-mrsu): this module lives in the ``constraint_compiler`` package
because that package IS the AE-002 engine home (it already holds ``graph.py``,
``parser.py`` and ``emitters/``); a slice-discovery engine that builds an
import graph belongs alongside the existing graph code, not as a loose
top-level adjacent module.

Clustering routine (ds-mrsu): a hand-rolled, dependency-light, deterministic
greedy modularity merge over the undirected projection of the import graph.
Connected components alone would NOT split two dense clusters joined by even
one thin edge, so a modularity objective is required. The merge is seeded
deterministically (nodes sorted, fixed tie-breaks) so identical source always
yields identical membership.

Zero-importable-module behaviour (ds-mrsu): write an empty JSON array ``[]``
to the manifest, emit a warning to stderr, and return ``[]`` — never crash.

RAW slices only: the engine owns ``member_modules`` / ``globs`` /
``cohesion_stats`` / ``coupling_stats``. The ``name`` / ``domain_name`` fields
are a separate concern (ds-h60i) and are deliberately NOT emitted here.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from typing import Any

__all__ = ["discover_slices"]


# --------------------------------------------------------------------------- #
# Static import-graph construction (stdlib ast only)
# --------------------------------------------------------------------------- #


def _iter_python_files(repo: Path) -> list[Path]:
    """All ``.py`` files under ``repo``, sorted for determinism.

    Skips hidden directories (``.git``, ``.dekspec``, …) and common virtual-
    environment / cache dirs so the graph reflects first-party source only.
    """
    skip = {".git", ".dekspec", ".venv", "venv", "__pycache__", ".tox",
            ".mypy_cache", ".pytest_cache", "node_modules", ".hg", ".svn"}
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = sorted(d for d in dirnames if d not in skip and not d.startswith("."))
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                out.append(Path(dirpath) / fn)
    return sorted(out)


def _module_name_for(path: Path, repo: Path) -> str:
    """Dotted module name for a repo-relative ``.py`` path.

    ``alpha/a1.py`` -> ``alpha.a1``; ``alpha/__init__.py`` -> ``alpha``.
    """
    rel = path.relative_to(repo)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # strip .py
    return ".".join(parts)


def _imported_names(tree: ast.AST) -> list[str]:
    """Dotted names an AST imports (both ``import x`` and ``from x import y``).

    ``from x import y`` yields both ``x`` and ``x.y`` candidates so the
    resolver can match either a sub-package import or a symbol import. Relative
    imports (``from . import y``) are skipped here — they are resolved against
    the package context by the caller via the absolute fallback only.
    """
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # relative import — not resolved in v1
                continue
            mod = node.module or ""
            if not mod:
                continue
            names.append(mod)
            for alias in node.names:
                names.append(f"{mod}.{alias.name}")
    return names


def build_import_graph(repo: Path) -> tuple[list[str], dict[str, set[str]]]:
    """Build the intra-repo directed import graph.

    Returns ``(modules, edges)`` where ``modules`` is the sorted list of
    repo-relative module path strings (e.g. ``alpha/a1.py``) and ``edges`` maps
    each module path to the set of repo-relative module paths it imports.
    Only edges that resolve to an in-repo module are kept; stdlib / third-party
    imports are ignored.
    """
    repo = repo.resolve()
    files = _iter_python_files(repo)

    # dotted-name -> repo-relative path, and the inverse for edge resolution
    name_to_relpath: dict[str, str] = {}
    relpaths: list[str] = []
    for f in files:
        rel = f.relative_to(repo).as_posix()
        relpaths.append(rel)
        name_to_relpath[_module_name_for(f, repo)] = rel
    relpaths = sorted(relpaths)

    edges: dict[str, set[str]] = {rp: set() for rp in relpaths}

    for f in files:
        src_rel = f.relative_to(repo).as_posix()
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        for imported in _imported_names(tree):
            target = _resolve_import(imported, name_to_relpath)
            if target is not None and target != src_rel:
                edges[src_rel].add(target)

    return relpaths, edges


def _resolve_import(dotted: str, name_to_relpath: dict[str, str]) -> str | None:
    """Resolve a dotted import name to a repo-relative module path, or None.

    Tries the full dotted name, then progressively drops trailing components
    (so ``alpha.a2.something`` resolves to ``alpha.a2`` if that is a module).
    """
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in name_to_relpath:
            return name_to_relpath[cand]
    return None


# --------------------------------------------------------------------------- #
# Deterministic greedy-modularity community detection
# --------------------------------------------------------------------------- #


def _undirected_weights(
    modules: list[str], edges: dict[str, set[str]]
) -> dict[frozenset[str], int]:
    """Undirected projection edge weights (a->b and b->a collapse + sum)."""
    weights: dict[frozenset[str], int] = {}
    for src, dsts in edges.items():
        for dst in dsts:
            if src == dst:
                continue
            key = frozenset((src, dst))
            weights[key] = weights.get(key, 0) + 1
    return weights


def detect_communities(
    modules: list[str], edges: dict[str, set[str]]
) -> list[list[str]]:
    """Deterministic greedy modularity-merge community detection.

    Starts with every module in its own community, then repeatedly merges the
    pair of communities whose merge yields the greatest positive modularity
    gain, until no positive-gain merge remains. Isolated nodes (no intra-repo
    edges) each form a singleton community. Deterministic: nodes are sorted,
    candidate pairs are evaluated in sorted order, and ties break on the
    lexicographically smallest community pair.

    Returns a sorted list of communities; each community is a sorted list of
    repo-relative module paths. Empty input yields an empty list.
    """
    modules = sorted(modules)
    if not modules:
        return []

    weights = _undirected_weights(modules, edges)
    m = sum(weights.values())  # total undirected edge weight

    if m == 0:
        # No intra-repo edges: every module is its own singleton community.
        return [[mod] for mod in modules]

    # Weighted degree per node.
    degree: dict[str, int] = {mod: 0 for mod in modules}
    for pair, w in weights.items():
        a, b = sorted(pair)
        degree[a] += w
        degree[b] += w

    # Adjacency weight lookup between two single nodes.
    def edge_w(a: str, b: str) -> int:
        return weights.get(frozenset((a, b)), 0)

    # Communities keyed by a stable representative; membership as sorted list.
    comm: dict[str, list[str]] = {mod: [mod] for mod in modules}

    def modularity_gain(ca: list[str], cb: list[str]) -> float:
        """Delta-Q from merging communities ca and cb (undirected, weight m)."""
        inter = 0
        for a in ca:
            for b in cb:
                inter += edge_w(a, b)
        deg_a = sum(degree[x] for x in ca)
        deg_b = sum(degree[x] for x in cb)
        # Standard modularity gain for merging two communities:
        #   dQ = inter/(2m) - (deg_a * deg_b) / (2m)^2
        return inter / (2 * m) - (deg_a * deg_b) / ((2 * m) ** 2)

    while True:
        keys = sorted(comm.keys())
        best_gain = 0.0
        best_pair: tuple[str, str] | None = None
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                ka, kb = keys[i], keys[j]
                gain = modularity_gain(comm[ka], comm[kb])
                # strict-improvement merge; deterministic tie handling by
                # sorted-key iteration order (first best wins).
                if gain > best_gain + 1e-12:
                    best_gain = gain
                    best_pair = (ka, kb)
        if best_pair is None:
            break
        ka, kb = best_pair
        merged = sorted(comm[ka] + comm[kb])
        rep = merged[0]  # stable representative = lexicographically smallest
        del comm[ka]
        del comm[kb]
        comm[rep] = merged

    communities = sorted((sorted(members) for members in comm.values()))
    return communities


# --------------------------------------------------------------------------- #
# Slice emission
# --------------------------------------------------------------------------- #


def _globs_for(members: list[str]) -> list[str]:
    """Derive non-empty repo-relative glob selectors from member paths.

    Groups members by their parent directory and emits ``<dir>/**`` for each
    distinct directory; for a top-level module with no directory the explicit
    file path is used. Sorted + deduped for determinism.
    """
    globs: set[str] = set()
    for mod in members:
        parent = str(Path(mod).parent.as_posix())
        if parent and parent != ".":
            globs.add(f"{parent}/**")
        else:
            globs.add(mod)
    return sorted(globs)


def _slice_stats(
    members: list[str], edges: dict[str, set[str]]
) -> tuple[dict[str, float], dict[str, float]]:
    """Compute cohesion (internal density) + coupling (external ratio)."""
    member_set = set(members)
    internal = 0
    external = 0
    for src in members:
        for dst in edges.get(src, ()):  # outgoing edges
            if dst in member_set:
                internal += 1
            else:
                external += 1
    n = len(members)
    max_internal = n * (n - 1)  # directed, no self-loops
    density = (internal / max_internal) if max_internal else 0.0
    total = internal + external
    ext_ratio = (external / total) if total else 0.0
    cohesion = {"internal_edge_density": round(density, 6)}
    coupling = {"external_edge_ratio": round(ext_ratio, 6)}
    return cohesion, coupling


def _build_slices(
    communities: list[list[str]], edges: dict[str, set[str]]
) -> list[dict[str, Any]]:
    slices: list[dict[str, Any]] = []
    for members in communities:
        members = sorted(members)
        globs = _globs_for(members)
        cohesion, coupling = _slice_stats(members, edges)
        slices.append(
            {
                "member_modules": members,
                "globs": globs,
                "cohesion_stats": cohesion,
                "coupling_stats": coupling,
            }
        )
    # deterministic slice order: by first member path
    slices.sort(key=lambda s: s["member_modules"][0])
    return slices


# --------------------------------------------------------------------------- #
# Manifest write (lazy .dekspec/ — mirrors session_lifecycle idiom)
# --------------------------------------------------------------------------- #


def _write_manifest(repo: Path, slices: list[dict[str, Any]]) -> Path:
    """Write the slice array to ``<repo>/.dekspec/slices.json``.

    Creates ``.dekspec/`` lazily on first write, mirroring the
    ``mkdir(parents=True, exist_ok=True)`` idiom from
    ``session_lifecycle._ensure_state_dir`` (but anchored to the *target* repo
    dir rather than cwd). UTF-8, two-space indented JSON array.
    """
    state_dir = repo / ".dekspec"
    state_dir.mkdir(parents=True, exist_ok=True)
    manifest = state_dir / "slices.json"
    manifest.write_text(
        json.dumps(slices, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def discover_slices(repo: str | Path) -> list[dict[str, Any]]:
    """Discover structural slices for a Python repo and write the manifest.

    Pure static analysis (stdlib ``ast``); no LLM, no network. Returns the RAW
    slice array and writes it to ``<repo>/.dekspec/slices.json``. On a repo
    with no importable Python modules, writes an empty array, warns on stderr,
    and returns ``[]`` rather than crashing.
    """
    repo_path = Path(repo).resolve()
    modules, edges = build_import_graph(repo_path)

    if not modules:
        print(
            f"warning: no importable Python modules found under {repo_path}; "
            "writing empty slice manifest.",
            file=sys.stderr,
        )
        _write_manifest(repo_path, [])
        return []

    communities = detect_communities(modules, edges)
    slices = _build_slices(communities, edges)
    _write_manifest(repo_path, slices)
    return slices
