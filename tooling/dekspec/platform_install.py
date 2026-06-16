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

import shutil
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


def emit(platform: str, *, source_dir: Path, target_dir: Path) -> EmitResult:
    """Emit the per-host tree for ``platform`` from ``source_dir`` into
    ``target_dir``.

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
    layout(source_dir, target_dir, result)
    return result


# --------------------------------------------------------------------------- #
# write primitives
# --------------------------------------------------------------------------- #
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
    # AGENTS.md is the Codex host marker / entry document.
    _write_marker(
        target_dir / "AGENTS.md",
        "# DekSpec (Codex)\n\n"
        "DekSpec skill suite installed under `.codex/`. "
        "Skills live in `.codex/skills/`, commands in `.codex/commands/`.\n",
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


_LAYOUTS = {
    "claude": _layout_claude,
    "codex": _layout_codex,
    "antigravity": _layout_antigravity,
    "cursor": _layout_cursor,
    "copilot": _layout_copilot,
    "pi": _layout_pi,
}
