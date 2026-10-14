"""Per-host install emitter (ds-iz3d).

Repackages the single ``plugins/dekspec`` skill / command / hook source into
the file tree a given harness host expects, so the DekSpec skill suite is
invocable on that host after one ``dekspec install --platform <host>`` command.

Design constraints (MSN-016 / ADR-024 / ADR-036 — harness-abstraction cluster):

  - **Build-time only.** This module *writes files*. It never spawns an
    executor, daemon, or subprocess; nothing here runs the emitted hooks.
  - **Single source -> per-host output.** Hosts share one
    ``skills`` / ``commands`` / ``hooks`` source. Bodies stay byte-identical;
    headers are projected per ADR-074 from the canonical field table.
  - **Six platforms only.** ``claude`` / ``codex`` / ``antigravity`` /
    ``cursor`` / ``copilot`` / ``pi``. Any other platform raises
    ``HarnessUnsupported("install", ...)`` and writes NOTHING (no partial tree).
  - **Idempotent.** Re-emitting into the same target overwrites/refreshes the
    same file set — no duplication, no error.
  - **Sandboxed writes.** Every write is confined to ``target_dir``; source
    paths that would escape the target (via ``..`` traversal) are rejected.

Hook config is emitted as DATA — Codex gets portable edit-hook commands;
other hosts get the plugin JSON verbatim. Emission never runs the commands.

Per-host layout
---------------
claude       ``<target>/.claude/skills/<skill>/...`` (recursive),
             ``<target>/.claude/commands/<cmd>.md``,
             hook config -> ``<target>/.claude/hooks.json``.
codex        ``<target>/AGENTS.md`` host marker + the skills/commands/hooks
             tree rooted under ``<target>/.codex/`` (hooks ->
             ``<target>/.codex/hooks.json``, handlers in ``.codex/hooks/``).
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

import json
import os
import shlex
import shutil
from collections.abc import Collection
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
    #: Absolute paths (files or directories) this emit writes nothing under.
    preserve: tuple[str, ...] = field(default=(), repr=False)
    #: Installation notices already explained by the emitter; CLI only prints.
    notices: list[str] = field(default_factory=list)
    #: Other products' header problems; those skills were installed unchanged.
    header_warnings: list[str] = field(default_factory=list)
    # Prepared before any layout writes; all other files retain byte copying.
    _skill_bytes: dict[Path, bytes] = field(default_factory=dict, repr=False)


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


# Historical plugin hook configs, from git history before/after the product
# move. Recognize content, never a filename or JSON shape, as library-owned.
# Before changing _codex_hook_config, append the old generated config
# content_digest here so reinstalls still recognize every shipped emission.
_SHIPPED_CODEX_HOOK_DIGESTS = frozenset({
    "7188b065450eeecdfec2a2a9e17ebf8559a4982a80e954f122590ea79933da55",
    "db074eb856bf9bdcff978ca7e8998b2e0b26028ac6c97d82b1214f5110ac3a38",
    "db47545728aa3f27a4e376b1ddd825a3c9bfcee0330992b9c296479ab2480ed2",
    "e92455f6571b1b68d29bef1c1f14e5f1e1482363c37ae5f5d8d431e2f36cb843",
    "ed730564b7482fbcb442a31c0e249b15fded1dcac5f5baa03ff1b2cac866c904",
})
_CODEX_EDIT_HANDLERS = {
    "PreToolUse": "pretooluse-locked-guard.py",
    "PostToolUse": "post-edit-audit.py",
}
_CODEX_PATCH_READER = "_patch_paths.py"


def _codex_hook_config() -> str:
    """Portable commands check dependencies before Python can exit 2.

    The launcher lives in the config itself so even a missing handler or
    shared reader can produce a warning. No install-time paths are embedded.
    """
    hooks = {}
    for event, handler in _CODEX_EDIT_HANDLERS.items():
        dependencies = f".codex/hooks/{handler} .codex/hooks/{_CODEX_PATCH_READER}"
        script = (
            'root=$(git rev-parse --show-toplevel 2>/dev/null) && '
            '[ -n "$root" ] && cd "$root" || { '
            'echo "[dekspec] Warning: repository root missing; DekSpec hook did not run." >&2; '
            'exit 0; }; '
            f'for file in {dependencies}; do '
            'if [ ! -f "$file" ]; then '
            'echo "[dekspec] Warning: missing $file; DekSpec hook did not run." >&2; '
            'exit 0; fi; done; '
            'command -v python3 >/dev/null 2>&1 || { '
            'echo "[dekspec] Warning: missing python3; DekSpec hook did not run." >&2; '
            'exit 0; }; '
            f'exec python3 -B .codex/hooks/{handler}'
        )
        hooks[event] = [{
            "matcher": "apply_patch",
            "hooks": [{"type": "command", "command": "sh -c " + shlex.quote(script)}],
        }]
    return json.dumps({"hooks": hooks}, indent=2) + "\n"


def _install_codex_hooks(source_dir: Path, target_dir: Path, result: EmitResult) -> None:
    """Own Codex's edit-hook layout, retirement and safe reinstallation."""
    from dekspec.roles.legacy import content_digest

    root = target_dir / ".codex"
    config = _codex_hook_config()
    shipped = _SHIPPED_CODEX_HOOK_DIGESTS | {content_digest(config.encode())}
    old = root / "hooks" / "hooks.json"
    if old.is_file():
        # Never follow a target's symlink outside the installation or remove
        # a path the caller has asked to preserve.
        if (not old.is_symlink() and target_dir.resolve() in old.resolve().parents
                and not _preserved(old, result) and content_digest(old.read_bytes()) in shipped):
            old.unlink()
            result.removed.append(old)
        else:
            result.preserved.append(old)
            result.notices.append("Kept .codex/hooks/hooks.json; Codex never loads this location.")

    dst = root / "hooks.json"
    if (dst.is_symlink() or _preserved(dst, result)
            or (dst.exists() and (not dst.is_file() or content_digest(dst.read_bytes()) not in shipped))):
        result.notices.append(
            "Kept .codex/hooks.json; DekSpec edit hooks are not active. "
            "Add the PreToolUse and PostToolUse entries matching apply_patch:\n" + config
        )
    else:
        _write_marker(dst, config, target_dir, result)

    # Only edit handlers and their reader: no session handler or unused file.
    for name in (*_CODEX_EDIT_HANDLERS.values(), _CODEX_PATCH_READER):
        src = source_dir / "hooks-handlers" / name
        if src.is_file():
            _copy_file(src, root / "hooks" / name, target_dir, result)


def emit(
    platform: str,
    *,
    source_dir: Path,
    target_dir: Path,
    preserve: Collection[Path] = (),
) -> EmitResult:
    """Emit the per-host tree for ``platform`` from ``source_dir`` into
    ``target_dir``.

    Every host gets the same projection of the one plugin source: the host
    layout, then the removal of retired core files an earlier install left
    behind (:data:`RETIRED_HOST_FILES`).

    ``preserve`` names paths (files or directories) the emission must leave
    alone: nothing is written at or under them, and they are not listed in
    ``written``. The caller decides why a path is off limits.

    Returns an :class:`EmitResult` listing the written paths. Raises
    :class:`HarnessUnsupported` (``primitive="install"``) for an unknown
    platform, writing nothing.
    """
    layout = _LAYOUTS.get(platform)
    if layout is None:
        # Typed error, never a partial tree.
        raise HarnessUnsupported("install", platform, "unknown platform")

    from .skill_headers import SkillHeaderError, frozen_release_tree, split_tree_problems
    from .skill_metadata import project_skill_md

    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    reported: list[str] = []
    if not frozen_release_tree(source_dir / "skills"):
        refused, reported = split_tree_problems(source_dir / "skills")
        if refused:
            raise SkillHeaderError("\n".join(refused))
    result = EmitResult(
        platform=platform,
        header_warnings=reported,
        preserve=tuple(os.path.abspath(p) for p in preserve),
    )
    result._skill_bytes = {
        path: project_skill_md(path, platform).encode("utf-8", errors="surrogateescape")
        for path in sorted((source_dir / "skills").glob("*/SKILL.md"))
        if path.is_file()
    }
    layout(source_dir, target_dir, result)
    _prune_retired_core(result)
    return result


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

    Refuses any ``dst`` that would resolve outside ``target_dir``. A ``dst``
    at or under a path the caller asked to preserve is skipped.
    """
    if _preserved(dst, result):
        return
    resolved = dst.resolve()
    if target_dir.resolve() not in resolved.parents and resolved != target_dir.resolve():
        raise HarnessUnsupported(
            "install", None, f"refusing to write outside target: {dst}"
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src in result._skill_bytes:
        dst.write_bytes(result._skill_bytes[src])
    else:
        shutil.copyfile(src, dst)
    result.written.append(dst)


def _preserved(dst: Path, result: EmitResult) -> bool:
    path = os.path.abspath(dst)
    return any(path == p or path.startswith(p + os.sep) for p in result.preserve)


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
    _install_codex_hooks(source_dir, target_dir, result)


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


def _layout_amp(source_dir: Path, target_dir: Path, result: EmitResult) -> None:
    """The isolated Amp project plugin (IB-194).

    Surface skeleton written with IB-194's acceptance tests: the platform is
    accepted and the layout writes nothing yet. The implementation replaces
    this body within IB-194's Scope.
    """
    return None


# Where each layout roots its skills/ + commands/ tree. Kept beside
# `_LAYOUTS` because the two must agree: code that inspects an emitted host
# tree (the retired-dispatch-wrapper checks, the upgrade migration) looks
# under exactly this directory.
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
    "amp": _layout_amp,
}
