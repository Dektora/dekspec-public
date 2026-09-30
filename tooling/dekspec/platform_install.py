"""Per-host install emitter (ds-iz3d).

Repackages the single ``plugins/dekspec`` skill / command / hook source into
the file tree a given harness host expects, so the DekSpec skill suite is
invocable on that host after one ``dekspec install --platform <host>`` command.

Design constraints (MSN-016 / ADR-024 / ADR-036 — harness-abstraction cluster):

  - **Build-time only.** This module *writes files*. It never spawns an
    executor, daemon, or subprocess; nothing here runs the emitted hooks.
  - **Single source -> per-host output.** All four hosts are projections of the
    same ``skills`` / ``commands`` / ``hooks`` source. Skill bodies are NEVER
    forked or rewritten per host — only relocated into the host's layout.
  - **Six platforms only.** ``claude`` / ``codex`` / ``antigravity`` /
    ``cursor`` / ``copilot`` / ``pi``. Any other platform raises
    ``HarnessUnsupported("install", ...)`` and writes NOTHING (no partial tree).
  - **Idempotent.** Re-emitting into the same target overwrites/refreshes the
    same file set — no duplication, no error.
  - **Sandboxed writes.** Every write is confined to ``target_dir``; source
    paths that would escape the target (via ``..`` traversal) are rejected.

Hook config is emitted as DATA — the JSON (which may contain shell-command
strings) is copied verbatim into the host's hook-config location. It is never
parsed-for-execution or run.

Per-host layout
---------------
claude       ``<target>/.claude/skills/<skill>/...`` (recursive),
             ``<target>/.claude/commands/<cmd>.md``,
             hook config -> ``<target>/.claude/hooks.json``.
codex        ``<target>/AGENTS.md`` host marker + the skills/commands/hooks
             tree rooted under ``<target>/.codex/`` (hooks ->
             ``<target>/.codex/hooks/hooks.json``).
antigravity  ``<target>/.antigravity/skills|commands/...`` + hook config ->
             ``<target>/.antigravity/hooks/hooks.json``.
cursor       ``<target>/.cursor/...``. **P3 design choice:** Cursor reads its
             own native ``.cursor/`` surfaces, so we emit the *native* cursor
             tree (``.cursor/skills`` + ``.cursor/commands`` + a
             ``.cursor/rules/dekspec.md`` agent-rules pointer), NOT a
             ``.claude/`` read-compat shim. One source of truth, host-native
             output, no second copy to drift.
copilot      ``<target>/.github/...``. Targets the *interactive* Copilot
             surface (VS Code agent mode + Copilot CLI). Skills and commands
             land under ``.github/skills`` / ``.github/commands`` (the open
             Agent Skills standard), and the hook config is copied as data
             into ``.github/hooks/hooks.json``. Writes confined to
             ``target_dir``; hook JSON is data, never execed.
pi           ``<target>/.pi/...``. Pi (pi.dev) minimal terminal harness.
             Skills/commands land under the open Agent Skills standard at
             ``.pi/skills`` / ``.pi/commands``; an ``.pi/extensions/`` note
             records the ``@tintinweb/pi-subagents`` dependency that realizes
             parallel sub-agent dispatch; the hook config is copied as data
             into ``.pi/hooks/hooks.json`` (Pi's ``pi.events`` bus), never
             execed. Writes confined to ``target_dir``.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .harness import HarnessUnsupported

__all__ = ["EmitResult", "emit"]


@dataclass
class EmitResult:
    """The outcome of an :func:`emit` call.

    ``platform`` is the host emitted for; ``written`` lists every file path
    written (absolute, under ``target_dir``), in emission order.
    """

    platform: str
    written: list[Path] = field(default_factory=list)
    #: Retired core files removed on re-install (unmodified shipped copies).
    removed: list[Path] = field(default_factory=list)
    #: Retired core files kept because they differ from every shipped version.
    preserved: list[Path] = field(default_factory=list)


#: Core files a release retired, relative to a host's root (the directory
#: holding its ``skills/`` and ``commands/``) → the content digest (see
#: ``dekspec.roles.legacy.content_digest``) of every version the library
#: shipped. A re-install removes an unmodified copy and keeps a modified one
#: (reported), exactly like the vendoring prune.
RETIRED_HOST_FILES: dict[str, frozenset[str]] = {
    # ADR-061: the placeholder spec-review dispatch contract.
    "skills/_lib/reviewer_mode.md": frozenset({
        "11a9f68d27532f350b276e8d53ca3bbca86f687a0e9704b4bbe6bce7941d4b63",
    }),
    # IB-144 (ds-9tvmm): the Skill-tool wrappers of the two user-only dispatch
    # skills. Each skill is its own slash entry; a wrapper left behind by an
    # earlier install would keep dispatching it through the Skill tool.
    "commands/implement.md": frozenset({
        "2a056b78f433d3c497f96745d7019fd2f08c6ee546a98664b091a07f0a669a07",
    }),
    "commands/orchestrate-coding-session.md": frozenset({
        "82f1c0f37d159704b4cf6fb5d3fa823c8052f6b242916357111bd8ed3631126b",
        "efb4b4dbf089786a8abd4d917f2a09677ab3fe5aa950eb78863b7a59c073201d",
        "f4c1fa7e5053feac3102697b8f612847f2cfbfb9280ebe29aaee9235970d22f7",
    }),
}


def emit(
    platform: str,
    *,
    source_dir: Path,
    target_dir: Path,
    dektools_source: Path | None = None,
    dektools_tools: Iterable[str] = (),
    dektools_only: bool = False,
) -> EmitResult:
    """Emit the per-host tree for ``platform`` from ``source_dir`` into
    ``target_dir``.

    ``dektools_source`` + ``dektools_tools`` add the à-la-carte DekTools
    selection (ADR-047): exactly the named tools are emitted alongside core,
    and catalogued tools that are *not* named are pruned, so re-running after
    a selection change both adds and removes. Omitting them — or passing an
    empty selection with a toolkit distribution — emits setup only. With no
    toolkit distribution, core output is unchanged.

    ``dektools_only`` is for a host whose plugin system already delivers core
    and setup (ADR-060): only the selected tools and their support files are
    emitted, so nothing shadows the installed plugins.

    Returns an :class:`EmitResult` listing the written paths. Raises
    :class:`HarnessUnsupported` (``primitive="install"``) for an unknown
    platform, writing nothing.
    """
    layout = _LAYOUTS.get(platform)
    if layout is None:
        # Typed error, never a partial tree.
        raise HarnessUnsupported("install", platform, "unknown platform")

    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    result = EmitResult(platform=platform)
    if not dektools_only:
        layout(source_dir, target_dir, result)
        _prune_retired_core(result)
    _apply_dektools_selection(
        platform, dektools_source, dektools_tools, target_dir, result,
        include_setup=not dektools_only,
    )
    return result


# --------------------------------------------------------------------------- #
# DekTools a-la-carte selection (ADR-047)
# --------------------------------------------------------------------------- #
def _catalogued_tools(dektools_source: Path) -> set[str]:
    """Every tool name the DekTools catalog declares.

    Read from the source tree rather than via `dekspec_config` so this module
    keeps its single responsibility (and no import cycle): the plugin source
    is the thing that knows its own catalog.
    """
    path = dektools_source / "tool-catalog.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HarnessUnsupported("install", None, f"invalid toolkit catalog: {exc}") from exc
    return {t["name"] for t in payload.get("tools", []) if "name" in t}


def _apply_dektools_selection(
    platform: str,
    dektools_source: Path | None,
    tools: Iterable[str],
    target_dir: Path,
    result: EmitResult,
    include_setup: bool = True,
) -> None:
    """Emit the selected DekTools tools and prune the deselected ones."""
    if dektools_source is None:
        return
    dektools_source = Path(dektools_source)
    if not dektools_source.is_dir():
        # A pip/pipx-installed engine carries no plugin tree. Core is
        # self-sufficient, so this is silence, not an error.
        return

    host_root = target_dir / _HOST_ROOTS[platform]
    catalogued = _catalogued_tools(dektools_source)
    requested = set(tools)
    unknown = requested - catalogued
    if unknown:
        raise HarnessUnsupported("install", platform, f"unknown DekTools tools: {sorted(unknown)}")
    # Setup is never a selectable tool: always emitted on a full tree, never
    # on a host whose plugin already delivers it — even if an older selection
    # names it explicitly.
    requested.discard("setup-dektools")
    always = {"setup-dektools"} if include_setup else set()
    selected = sorted((requested | always) & catalogued)
    # Pre-manifest installations cannot be safely claimed by directory name.
    # Refuse stale registrations with a concrete recovery path instead of
    # deleting unknown content or claiming the disabled tool disappeared.
    catalog_data = json.loads((dektools_source / "tool-catalog.json").read_text())
    legacy_names = set(catalog_data.get("renamed_tools", {}))
    manifest = host_root / ".dektools-install.json"

    def contained(path: Path) -> None:
        # Do not follow even in-tree symlinks: another generated path is not
        # evidence of ownership of its referent.
        if not path.resolve().is_relative_to(target_dir.resolve()):
            raise HarnessUnsupported("install", platform, f"unsafe toolkit path: {path}")
        for part in (path, *path.parents):
            if part == target_dir:
                break
            if part.is_symlink():
                raise HarnessUnsupported("install", platform, f"symlink toolkit path: {path}")

    contained(manifest)
    try:
        previous = json.loads(manifest.read_text()) if manifest.exists() else {}
        owned = previous.get("files", {})
        if not isinstance(owned, dict):
            raise ValueError("files must be a mapping")
    except (OSError, ValueError) as exc:
        raise HarnessUnsupported("install", platform, f"invalid toolkit manifest: {exc}") from exc
    desired: dict[str, Path] = {}
    for name in selected:
        src = dektools_source / ("skills" if name == "setup-dektools" else "tools") / name
        # Old-source fixtures/distributions can still be emitted during upgrade.
        if not src.is_dir():
            src = dektools_source / "skills" / name
        if not (src / "SKILL.md").is_file():
            raise HarnessUnsupported("install", platform, f"missing toolkit skill: {name}")
        for file in sorted(src.rglob("*")):
            if file.is_file() and "__pycache__" not in file.parts and file.suffix != ".pyc":
                desired[str(Path("skills") / name / file.relative_to(src))] = file
    # Support files serve emitted skills; with none emitted they are clutter.
    support = [str(p.relative_to(dektools_source)) for p in (dektools_source / "scripts").glob("*.py")]
    for rel in ([*support, "tool-catalog.json"] if selected else []):
        if (dektools_source / rel).is_file():
            desired[rel] = dektools_source / rel

    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    # Validate the complete change before touching any toolkit content.
    conflicts = []
    for legacy in legacy_names:
        for rel in (f"skills/{legacy}/SKILL.md", f"commands/{legacy}.md"):
            if (host_root / rel).exists() and rel not in owned:
                conflicts.append(rel)
    for name in catalogued - set(selected):
        rel = f"skills/{name}/SKILL.md"
        if (host_root / rel).exists() and rel not in owned:
            conflicts.append(rel)
    for rel in set(owned) | set(desired):
        dst = host_root / rel
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise HarnessUnsupported("install", platform, f"invalid owned path: {rel}")
        contained(dst)
        if dst.exists():
            current = digest(dst)
            if rel in desired:
                if current != owned.get(rel) and current != digest(desired[rel]):
                    conflicts.append(rel)
            elif current != owned[rel]:
                conflicts.append(rel)
    if conflicts:
        raise HarnessUnsupported(
            "install", platform,
            "preserved modified/unowned toolkit files: " + ", ".join(sorted(conflicts))
            + "; move these files aside after review, then reapply selection",
        )
    for rel in sorted(set(owned) - set(desired)):
        dst = host_root / rel
        dst.unlink(missing_ok=True)
        parent = dst.parent
        while parent != host_root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    hashes = {}
    for rel, src in desired.items():
        _copy_file(src, host_root / rel, target_dir, result)
        hashes[rel] = digest(src)
    host_root.mkdir(parents=True, exist_ok=True)
    temp = manifest.with_suffix(".tmp")
    contained(temp)
    temp.write_text(json.dumps({"version": 1, "enabled": sorted(requested), "files": hashes}, indent=2) + "\n")
    temp.replace(manifest)
    result.written.append(manifest)


# --------------------------------------------------------------------------- #
# write primitives
# --------------------------------------------------------------------------- #
def _prune_retired_core(result: EmitResult) -> None:
    """Remove retired core files left by an earlier install of this host tree.

    The host roots are the parents of the skills roots this emit wrote a
    ``_lib/`` file into, so only trees DekSpec itself installs are touched. A
    file whose content matches no shipped version was edited locally: it is
    kept and reported.
    """
    from dekspec.roles.legacy import content_digest

    written = {p.resolve() for p in result.written}
    roots = {p.parent.parent.parent for p in result.written if p.parent.name == "_lib"}
    for root in sorted(roots):
        for rel, shipped in RETIRED_HOST_FILES.items():
            path = root / rel
            if not path.is_file() or path.resolve() in written:
                continue
            if content_digest(path.read_bytes()) in shipped:
                path.unlink()
                result.removed.append(path)
            else:
                result.preserved.append(path)


def _copy_file(src: Path, dst: Path, target_dir: Path, result: EmitResult) -> None:
    """Copy one file ``src`` -> ``dst`` (overwrite), recording ``dst``.

    Refuses any ``dst`` that would resolve outside ``target_dir``.
    """
    resolved = dst.resolve()
    if target_dir.resolve() not in resolved.parents and resolved != target_dir.resolve():
        raise HarnessUnsupported(
            "install", None, f"refusing to write outside target: {dst}"
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    result.written.append(dst)


def _copy_tree(src_dir: Path, dst_dir: Path, target_dir: Path, result: EmitResult) -> None:
    """Recursively mirror every file under ``src_dir`` into ``dst_dir``."""
    if not src_dir.is_dir():
        return
    for src in sorted(src_dir.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(src_dir)
        _copy_file(src, dst_dir / rel, target_dir, result)


def _copy_skills_and_commands(
    source_dir: Path, host_root: Path, target_dir: Path, result: EmitResult
) -> None:
    """Shared body: mirror skills/ and commands/ under ``host_root``."""
    _copy_tree(source_dir / "skills", host_root / "skills", target_dir, result)
    _copy_tree(source_dir / "commands", host_root / "commands", target_dir, result)


def _copy_hooks(
    source_dir: Path, dst: Path, target_dir: Path, result: EmitResult
) -> None:
    """Copy the hook config (as data) to ``dst`` if a source hooks.json exists."""
    src = source_dir / "hooks" / "hooks.json"
    if src.is_file():
        _copy_file(src, dst, target_dir, result)


# --------------------------------------------------------------------------- #
# per-host layouts
# --------------------------------------------------------------------------- #
def _layout_claude(source_dir: Path, target_dir: Path, result: EmitResult) -> None:
    root = target_dir / ".claude"
    _copy_skills_and_commands(source_dir, root, target_dir, result)
    _copy_hooks(source_dir, root / "hooks.json", target_dir, result)


def _layout_codex(source_dir: Path, target_dir: Path, result: EmitResult) -> None:
    # AGENTS.md is the Codex host's entry document. It is created only when
    # absent — an existing instruction file is never overwritten (ADR-063) —
    # with an empty DekSpec-owned region that `dekspec aggregate agents-md`
    # fills without a migration.
    agents = target_dir / "AGENTS.md"
    if not (agents.exists() or agents.is_symlink()):
        _write_marker(
            agents,
            "# DekSpec (Codex)\n\n"
            "DekSpec skill suite installed under `.codex/`. "
            "Skills live in `.codex/skills/`, commands in `.codex/commands/`.\n\n"
            "<!-- dekspec:agents-md begin -->\n"
            "<!-- dekspec:agents-md end -->\n",
            target_dir,
            result,
        )
    root = target_dir / ".codex"
    _copy_skills_and_commands(source_dir, root, target_dir, result)
    _copy_hooks(source_dir, root / "hooks" / "hooks.json", target_dir, result)


def _layout_antigravity(source_dir: Path, target_dir: Path, result: EmitResult) -> None:
    root = target_dir / ".antigravity"
    _copy_skills_and_commands(source_dir, root, target_dir, result)
    _copy_hooks(source_dir, root / "hooks" / "hooks.json", target_dir, result)


def _layout_cursor(source_dir: Path, target_dir: Path, result: EmitResult) -> None:
    # P3 choice: native .cursor/ tree, not a .claude/ read-compat shim.
    root = target_dir / ".cursor"
    _copy_skills_and_commands(source_dir, root, target_dir, result)
    _copy_hooks(source_dir, root / "hooks" / "hooks.json", target_dir, result)
    # Cursor surfaces agent behavior via rules; emit a pointer rule.
    _write_marker(
        root / "rules" / "dekspec.md",
        "# DekSpec rules (Cursor)\n\n"
        "DekSpec skills are installed under `.cursor/skills/` and commands "
        "under `.cursor/commands/`. Invoke a skill by name.\n",
        target_dir,
        result,
    )


def _layout_copilot(source_dir: Path, target_dir: Path, result: EmitResult) -> None:
    # Interactive Copilot host: VS Code agent mode + Copilot CLI. Skills/commands
    # land under the open Agent Skills standard at .github/skills + .github/commands;
    # the hook config is copied as data to .github/hooks/hooks.json (never execed).
    root = target_dir / ".github"
    _copy_skills_and_commands(source_dir, root, target_dir, result)
    _copy_hooks(source_dir, root / "hooks" / "hooks.json", target_dir, result)


def _layout_pi(source_dir: Path, target_dir: Path, result: EmitResult) -> None:
    # Pi (pi.dev) host: a minimal terminal coding harness (Environment +
    # Harness + Loop). Skills land under the open Agent Skills standard at
    # .pi/skills, prompt-template commands under .pi/commands, and the parallel-
    # subagent primitive is realized by the community @tintinweb/pi-subagents
    # extension, so we emit an extensions/ folder under .pi/. The hook config is
    # copied as data to .pi/hooks/hooks.json (Pi's pi.events bus); never execed.
    root = target_dir / ".pi"
    _copy_skills_and_commands(source_dir, root, target_dir, result)
    _copy_hooks(source_dir, root / "hooks" / "hooks.json", target_dir, result)
    # Pi realizes parallel subagents via the @tintinweb/pi-subagents extension;
    # emit a pointer note into the extensions/ folder (data only).
    _write_marker(
        root / "extensions" / "dekspec.md",
        "# DekSpec extensions (Pi)\n\n"
        "DekSpec skills are installed under `.pi/skills/` and commands under "
        "`.pi/commands/`. Parallel sub-agent dispatch depends on the community "
        "`@tintinweb/pi-subagents` extension; install it to enable parallel "
        "fan-out (the seam falls back to sequential dispatch when it is "
        "absent).\n",
        target_dir,
        result,
    )


def _write_marker(dst: Path, text: str, target_dir: Path, result: EmitResult) -> None:
    resolved = dst.resolve()
    if target_dir.resolve() not in resolved.parents and resolved != target_dir.resolve():
        raise HarnessUnsupported(
            "install", None, f"refusing to write outside target: {dst}"
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text)
    result.written.append(dst)


# Where each layout roots its skills/ + commands/ tree. Kept beside
# `_LAYOUTS` because the two must agree: the DekTools selection pass writes
# and prunes under exactly this directory.
_HOST_ROOTS = {
    "claude": ".claude",
    "codex": ".codex",
    "antigravity": ".antigravity",
    "cursor": ".cursor",
    "copilot": ".github",
    "pi": ".pi",
}

_LAYOUTS = {
    "claude": _layout_claude,
    "codex": _layout_codex,
    "antigravity": _layout_antigravity,
    "cursor": _layout_cursor,
    "copilot": _layout_copilot,
    "pi": _layout_pi,
}
