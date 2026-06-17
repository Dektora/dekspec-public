#!/usr/bin/env python3
"""Module-depth classifier — the AST metric behind the code-quality audit's
deep-module band counts (ADR-039, INT-provisional-depth-band-recalibration).

Classifies each *reusable abstraction* in a target repository into one of four
bands from a single depth signal:

    depth = noncomment_implementation_LOC / public_interface_token_count

Bands (ADR-039):
  - shallow     depth < shallow_ceiling          (interface ~= implementation)
  - deep        depth in the top quintile AND >= absolute floor  (relative-with-floor)
  - sound       at/above the shallow ceiling, not deep           (the healthy default)
  - overexposed ORTHOGONAL flag: interface tokens > cutoff (a module may be deep
                AND overexposed)

Gating: test modules, scripts, ``__main__`` entrypoints, and package aggregators
are excluded. A private ``_submodule.py`` of a folderized package rolls up into
its package, so a folderized deep module is counted once.

Concentration: the deep band's share of implementation mass is reported and
advisory-flagged when below the floor (the "complexity smeared, not pulled down"
smell). It is a signal to watch, never a target to maximize.

This module is consumed by the ``audit-codebase`` skill and exercised by
``tests/test_depth_classification.py``.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Tunable defaults — calibration origin: the `dektora` consumer run, 2026-06-15.
# Owned here (per ADR-039, thresholds live with the analyzer, not the ADR).
SHALLOW_CEILING = 3.0
DEEP_QUINTILE = 0.20
DEPTH_FLOOR = 12.0
OVEREXPOSURE_CUTOFF = 40
CONCENTRATION_FLOOR = 0.40
PARSE_FAILURE_BOUND = 0.50

_EXCLUDED_SEGMENTS = frozenset({
    "tests", "scripts", "experiments", ".venv", "venv", "site-packages",
    "node_modules", "build", "dist", ".tox", ".git", "__pycache__", "third_party",
})


class TargetRepoError(ValueError):
    """The target path is absent or not a directory."""


class NoAbstractionsError(ValueError):
    """No classifiable reusable abstraction was found in the tree."""


class ParseCoverageError(RuntimeError):
    """Too large a fraction of source files failed to parse to trust the result."""


@dataclass(frozen=True)
class ModuleClass:
    path: str          # posix path relative to the repo root
    loc: int           # noncomment implementation LOC (rolled-up for packages)
    iface: int         # public interface token count
    depth: float
    band: str          # "shallow" | "sound" | "deep"
    overexposed: bool


@dataclass(frozen=True)
class Report:
    modules: list[ModuleClass]
    counts: dict[str, int]
    overexposed: list[str]
    concentration: float          # deep-band share of total classified impl LOC
    concentration_advisory: bool
    unparseable: list[str] = field(default_factory=list)


def _noncomment_loc(src: str) -> int:
    return sum(
        1 for line in src.splitlines()
        if (s := line.strip()) and not s.startswith("#")
    )


def _params(node: ast.AST) -> int:
    a = node.args
    names = [p.arg for p in (*a.posonlyargs, *a.args, *a.kwonlyargs)]
    return sum(1 for n in names if n not in ("self", "cls"))


def _dunder_all(tree: ast.Module) -> list[str] | None:
    """Public names declared in a literal ``__all__`` (the authoritative surface), or None."""
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) else [])
        if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            val = node.value
            if isinstance(val, (ast.List, ast.Tuple)):
                names = [e.value for e in val.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                return [n for n in names if not n.startswith("_")]
    return None


def _interface_tokens(tree: ast.Module) -> int:
    # A literal __all__ is the authoritative public surface (captures re-exports
    # an aggregator __init__ forwards but does not define) — count its entries.
    declared = _dunder_all(tree)
    if declared is not None:
        return len(declared)

    iface = 0
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            iface += 1 + _params(node)
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            iface += 1
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("_"):
                    iface += 1 + _params(m)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # Re-exported public names (e.g. a package __init__ forwarding its impl).
            for alias in node.names:
                name = (alias.asname or alias.name).split(".")[0]
                if name != "*" and not name.startswith("_"):
                    iface += 1
    return iface


def _excluded(rel: str, src: str) -> bool:
    parts = Path(rel).parts
    if any(seg in _EXCLUDED_SEGMENTS for seg in parts):
        return True
    base = parts[-1]
    if base.startswith("test_") or base == "conftest.py":
        return True
    if "__main__" in src:  # entrypoint / runnable script
        return True
    return False


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def classify_repo(
    root: str,
    *,
    shallow_ceiling: float = SHALLOW_CEILING,
    deep_quintile: float = DEEP_QUINTILE,
    depth_floor: float = DEPTH_FLOOR,
    overexposure_cutoff: int = OVEREXPOSURE_CUTOFF,
    concentration_floor: float = CONCENTRATION_FLOOR,
    parse_failure_bound: float = PARSE_FAILURE_BOUND,
) -> Report:
    root_path = Path(root)
    if not root_path.is_dir():
        raise TargetRepoError(f"not a directory: {root}")

    py_files = [p for p in root_path.rglob("*.py")]
    rel = {p: p.relative_to(root_path).as_posix() for p in py_files}

    # Package dirs = directories containing __init__.py. Private (_name.py) siblings
    # roll up into the package; public submodules stay standalone.
    pkg_dirs = {p.parent for p in py_files if p.name == "__init__.py"}
    consumed: set[Path] = set()
    units: list[tuple[str, int, int]] = []  # (rel_path, loc, iface)
    unparseable: list[str] = []
    total_parse_attempts = 0

    def _parse(p: Path) -> ast.Module | None:
        nonlocal total_parse_attempts
        total_parse_attempts += 1
        try:
            return ast.parse(_read(p))
        except (SyntaxError, ValueError):
            unparseable.append(rel[p])
            return None

    # 1) package units (rolled up)
    for d in pkg_dirs:
        init = d / "__init__.py"
        if init not in rel:
            continue
        src = _read(init)
        if _excluded(rel[init], src):
            consumed.add(init)
            continue
        members = [init] + [
            f for f in py_files
            if f.parent == d and f.name != "__init__.py" and f.name.startswith("_")
        ]
        tree = _parse(init)
        if tree is None:
            consumed.update(members)
            continue
        loc = sum(_noncomment_loc(_read(f)) for f in members)
        iface = _interface_tokens(tree)
        consumed.update(members)
        if loc > 0:
            units.append((rel[init], loc, iface))

    # 2) standalone modules (incl. public submodules of packages)
    for p in py_files:
        if p in consumed:
            continue
        src = _read(p)
        if _excluded(rel[p], src):
            continue
        tree = _parse(p)
        if tree is None:
            continue
        loc = _noncomment_loc(src)
        if loc == 0:
            continue
        units.append((rel[p], loc, _interface_tokens(tree)))

    if total_parse_attempts and len(unparseable) / total_parse_attempts > parse_failure_bound:
        raise ParseCoverageError(
            f"{len(unparseable)}/{total_parse_attempts} files failed to parse"
        )
    if not units:
        raise NoAbstractionsError(f"no classifiable abstractions under {root}")

    depths = sorted(loc / max(iface, 1) for _, loc, iface in units)
    n = len(depths)
    thr = depths[min(int(n * (1 - deep_quintile)), n - 1)]

    modules: list[ModuleClass] = []
    for path, loc, iface in units:
        depth = loc / max(iface, 1)
        if depth < shallow_ceiling:
            band = "shallow"
        elif depth >= thr and depth >= depth_floor:
            band = "deep"
        else:
            band = "sound"
        modules.append(ModuleClass(
            path=path, loc=loc, iface=iface, depth=depth,
            band=band, overexposed=iface > overexposure_cutoff,
        ))

    counts = Counter(m.band for m in modules)
    total_loc = sum(m.loc for m in modules)
    deep_loc = sum(m.loc for m in modules if m.band == "deep")
    concentration = deep_loc / total_loc if total_loc else 0.0

    return Report(
        modules=modules,
        counts={b: counts.get(b, 0) for b in ("shallow", "sound", "deep")},
        overexposed=sorted(m.path for m in modules if m.overexposed),
        concentration=concentration,
        concentration_advisory=concentration < concentration_floor,
        unparseable=unparseable,
    )


@dataclass(frozen=True)
class ClusterCandidate:
    """An over-decomposition candidate package (ADR-038): small public sibling
    modules, high cohesion, low external-facade ratio."""
    package: str
    n_public: int
    avg_loc: int
    cohesion: float
    facade_ratio: float
    public_modules: list[str]
    private_count: int
    external_symbols: list[str]


def classify_clusters(
    root: str,
    *,
    min_public_modules: int = 3,
    max_avg_loc: int = 120,
    min_cohesion: float = 0.4,
    max_facade_ratio: float = 0.45,
) -> list[ClusterCandidate]:
    """Detect over-decomposition at package granularity (ADR-038).

    Three composed signals: a package's ``_private.py`` submodules + facade
    ``__init__`` are an already-folderized deep module (rolled up, never flagged);
    only PUBLIC sibling modules are counted. A candidate is >= min_public_modules
    small public siblings with high cohesion (they import each other) AND a low
    external-facade ratio (little of their public surface escapes the package).
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise TargetRepoError(f"not a directory: {root}")

    recs = {}
    for p in root_path.rglob("*.py"):
        rel = p.relative_to(root_path).as_posix()
        if any(seg in _EXCLUDED_SEGMENTS for seg in Path(rel).parts):
            continue
        src = _read(p)
        if "__main__" in src:
            continue
        try:
            tree = ast.parse(src)
        except (SyntaxError, ValueError):
            continue
        pkg = Path(rel).parent.as_posix()
        if pkg == ".":
            pkg = ""
        pubs = {n.name for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and not n.name.startswith("_")}
        recs[rel] = {"pkg": pkg, "base": Path(rel).name, "loc": _noncomment_loc(src),
                     "pubs": pubs, "tree": tree}

    # dotted module path -> owning package (for resolving absolute imports)
    dotted2pkg = {}
    for rel, r in recs.items():
        d = rel[:-3].replace("/", ".")
        dotted2pkg[d] = r["pkg"]
        if r["base"] == "__init__.py":
            dotted2pkg[d.rsplit(".__init__", 1)[0]] = r["pkg"]

    pkgs = defaultdict(lambda: {"pub": [], "priv": 0, "publoc": 0, "pubsyms": set()})
    for rel, r in recs.items():
        if r["base"] == "__init__.py":
            pkgs[r["pkg"]]  # ensure the package exists
            continue
        d = pkgs[r["pkg"]]
        if r["base"].startswith("_"):
            d["priv"] += 1                                  # folderized internal — rolled up
        else:
            d["pub"].append(r["base"])
            d["publoc"] += r["loc"]
            d["pubsyms"] |= r["pubs"]

    intra, inter = Counter(), Counter()
    extsyms = defaultdict(set)

    def resolve(mod):
        if mod in dotted2pkg:
            return dotted2pkg[mod]
        return dotted2pkg.get(mod.rsplit(".", 1)[0]) if "." in mod else None

    for rel, r in recs.items():
        ipkg = r["pkg"]
        for n in ast.walk(r["tree"]):
            if not isinstance(n, ast.ImportFrom):
                continue
            if n.level and n.level > 0:                     # relative import -> intra-package
                intra[ipkg] += len(n.names)
                continue
            if not n.module:
                continue
            src = resolve(n.module)
            if src is None:
                continue
            if src == ipkg:
                intra[ipkg] += len(n.names)
            else:
                inter[ipkg] += len(n.names)
                for a in n.names:
                    if a.name in pkgs[src]["pubsyms"]:
                        extsyms[src].add(a.name)            # public symbol escaping its package

    out = []
    for pk, d in pkgs.items():
        npub = len(d["pub"])
        if npub < min_public_modules:
            continue
        avg = d["publoc"] // npub
        if avg >= max_avg_loc:
            continue
        tot = len(d["pubsyms"]) or 1
        coh = intra[pk] / (intra[pk] + inter[pk]) if (intra[pk] + inter[pk]) else 0.0
        fac = len(extsyms[pk]) / tot
        if coh >= min_cohesion and fac <= max_facade_ratio:
            out.append(ClusterCandidate(
                package=pk, n_public=npub, avg_loc=avg, cohesion=coh, facade_ratio=fac,
                public_modules=sorted(d["pub"]), private_count=d["priv"],
                external_symbols=sorted(extsyms[pk])))
    out.sort(key=lambda c: -(c.n_public * c.cohesion * (1 - c.facade_ratio)))
    return out


def _format(report: Report) -> str:
    c = report.counts
    lines = [
        "Module-depth classification (ADR-039)",
        f"  shallow={c['shallow']}  sound={c['sound']}  deep={c['deep']}"
        f"  overexposed={len(report.overexposed)}  (classified={len(report.modules)})",
        f"  concentration (deep-band mass share) = {report.concentration:.0%}"
        + ("  [ADVISORY: complexity smeared, not pulled down]" if report.concentration_advisory else ""),
    ]
    deep = sorted((m for m in report.modules if m.band == "deep"), key=lambda m: -m.depth)
    if deep:
        lines.append("  deep modules:")
        lines += [f"    d={m.depth:6.1f} loc={m.loc:5d} iface={m.iface:3d} {m.path}" for m in deep]
    if report.overexposed:
        lines.append("  overexposed (interface too wide): " + ", ".join(report.overexposed))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Classify module depth (ADR-039 bands).")
    ap.add_argument("root", help="target repository root")
    args = ap.parse_args(argv)
    try:
        report = classify_repo(args.root)
    except (TargetRepoError, NoAbstractionsError, ParseCoverageError) as e:
        print(f"depth_classify: {e}")
        return 2
    print(_format(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
