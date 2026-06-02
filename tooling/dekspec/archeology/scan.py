"""AST-walk + symbol-enumeration helper for the archeology substrate.

`scan` reads a Python source file (or walks a directory of them) via the
stdlib `ast` module and produces a deterministic structured summary:

- **public API** — module-level functions, classes, and public methods
  (names not prefixed with `_`),
- **internal state** — module-level assignments (`NAME = ...`),
- **external callers** — best-effort: other modules across the repo that
  `import` the scanned module.

The helper is pure-Python: it has no CLI concern and no LLM concern. The
`/dekspec:archeology` skill's `--scan` and `--cross-ref` modes shell out to
it. Per INT-030 / IB-118.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "FileScan",
    "ScanError",
    "module_dotted_name",
    "scan",
    "scan_file",
]


class ScanError(Exception):
    """Raised when a scan target cannot be read or parsed."""


@dataclass
class FileScan:
    """Structured summary of one Python source file's surface.

    `path` is the file's path (as given, not resolved). `public_api` is the
    sorted list of module-level function / class names plus `Class.method`
    entries for public methods. `internal_state` is the sorted list of
    module-level assignment target names. `imports` is the sorted list of
    dotted module names the file imports. `external_callers` is the sorted
    list of repo-relative paths of other files that import this module
    (populated only when `scan` is given a repo root to cross-reference
    against; empty for a bare single-file scan).
    """

    path: str
    public_api: list[str] = field(default_factory=list)
    internal_state: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    external_callers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "public_api": list(self.public_api),
            "internal_state": list(self.internal_state),
            "imports": list(self.imports),
            "external_callers": list(self.external_callers),
        }


def module_dotted_name(file_path: Path, repo_root: Path) -> str:
    """Best-effort dotted module name for `file_path` relative to `repo_root`.

    `tooling/dekspec/lifecycle.py` under a repo whose import root is
    `tooling/` resolves to `dekspec.lifecycle`. The leading `tooling`
    segment is dropped because it is a packaging root, not part of the
    importable name; `__init__.py` collapses to the package name.
    """
    try:
        rel = file_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        rel = Path(file_path.name)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[0] == "tooling":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _parse(path: Path) -> ast.Module:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # unreadable file
        raise ScanError(f"cannot read {path}: {exc}") from exc
    try:
        return ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        raise ScanError(f"cannot parse {path}: {exc}") from exc


def _collect_public_api(tree: ast.Module) -> list[str]:
    """Module-level functions, classes, and public methods of those classes."""
    api: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                api.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            api.add(node.name)
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Public methods, plus the dunder `__init__` constructor.
                    if not member.name.startswith("_") or member.name == "__init__":
                        api.add(f"{node.name}.{member.name}")
    return sorted(api)


def _collect_internal_state(tree: ast.Module) -> list[str]:
    """Module-level assignment target names (plain + annotated assignments)."""
    state: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    state.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                state.add(node.target.id)
    return sorted(state)


def _collect_imports(tree: ast.Module) -> list[str]:
    """Dotted module names the file imports (`import x`, `from x import y`)."""
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return sorted(imports)


def scan_file(path: str | Path) -> FileScan:
    """Scan a single Python file. No cross-reference; `external_callers` empty.

    Raises `ScanError` if the file is unreadable, not a `.py` file, or has a
    syntax error.
    """
    p = Path(path)
    if p.suffix != ".py":
        raise ScanError(f"not a Python source file: {path}")
    if not p.is_file():
        raise ScanError(f"not a file: {path}")
    tree = _parse(p)
    return FileScan(
        path=str(path),
        public_api=_collect_public_api(tree),
        internal_state=_collect_internal_state(tree),
        imports=_collect_imports(tree),
    )


def _iter_python_files(root: Path) -> list[Path]:
    """Every `.py` file under `root`, skipping cache / venv noise dirs."""
    skip = {"__pycache__", ".venv", "node_modules", ".git", "build", "dist"}
    out: list[Path] = []
    for p in sorted(root.rglob("*.py")):
        if any(part in skip for part in p.parts):
            continue
        out.append(p)
    return out


def _find_external_callers(
    target: Path, repo_root: Path
) -> list[str]:
    """Repo-relative paths of files that import the target module.

    Best-effort: matches an importer if any of its imported dotted names is,
    or is a dotted-prefix descendant of, the target's dotted module name.
    """
    dotted = module_dotted_name(target, repo_root)
    if not dotted:
        return []
    target_resolved = target.resolve()
    callers: set[str] = set()
    for candidate in _iter_python_files(repo_root):
        if candidate.resolve() == target_resolved:
            continue
        try:
            tree = _parse(candidate)
        except ScanError:
            continue  # skip files we cannot parse — best-effort
        for imported in _collect_imports(tree):
            if imported == dotted or imported.startswith(dotted + "."):
                try:
                    rel = candidate.resolve().relative_to(repo_root.resolve())
                except ValueError:
                    rel = candidate
                callers.add(str(rel))
                break
    return sorted(callers)


def scan(
    path: str | Path, *, repo_root: str | Path | None = None
) -> list[FileScan]:
    """Scan a Python file or a directory tree of them.

    For a single `.py` file, returns a one-element list. For a directory,
    walks every `.py` file under it (skipping `__pycache__` / `.venv` /
    `node_modules` / `build` / `dist`).

    When `repo_root` is given, every result's `external_callers` is
    populated with the repo-relative paths of other files that import the
    scanned module — a best-effort cross-reference. Without `repo_root`,
    `external_callers` is left empty.

    Raises `ScanError` on an unreadable / unparseable / non-existent target.
    """
    p = Path(path)
    root = Path(repo_root) if repo_root is not None else None

    if p.is_dir():
        targets = _iter_python_files(p)
        if not targets:
            return []
    elif p.is_file():
        targets = [p]
    else:
        raise ScanError(f"scan target does not exist: {path}")

    results: list[FileScan] = []
    for target in targets:
        result = scan_file(target)
        if root is not None:
            result.external_callers = _find_external_callers(target, root)
        results.append(result)
    return results


def summarize(file_scan: FileScan) -> str:
    """Render a `FileScan` as a human-readable plain-text summary.

    Used by the skill's `--scan` mode for the in-harness transcript.
    """
    lines = [f"# Scan: {file_scan.path}", ""]
    lines.append(f"## Public API ({len(file_scan.public_api)})")
    if file_scan.public_api:
        lines += [f"  - {name}" for name in file_scan.public_api]
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append(f"## Internal state ({len(file_scan.internal_state)})")
    if file_scan.internal_state:
        lines += [f"  - {name}" for name in file_scan.internal_state]
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append(f"## External callers ({len(file_scan.external_callers)})")
    if file_scan.external_callers:
        lines += [f"  - {name}" for name in file_scan.external_callers]
    else:
        lines.append("  (none detected)")
    return "\n".join(lines)
