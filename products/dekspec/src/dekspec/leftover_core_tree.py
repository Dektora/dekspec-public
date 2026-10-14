"""Read-only warning for unowned Claude trees that can shadow the marketplace plugin."""
from __future__ import annotations

import json
from pathlib import Path

# Union of the skill folders and command .md files from v0.124.0, v0.126.0,
# v0.127.0 and v0.128.0. Regenerate each tag's listing with:
# git ls-tree <tag> plugins/dekspec/skills/ plugins/dekspec/commands/
# No git dependency is needed on the installed host.
_FROZEN_SKILLS = frozenset({
    "_lib",
    "audit-codebase",
    "debug",
    "deepen",
    "diagnose-session",
    "handoff",
    "implement",
    "ingest-docs",
    "interview-me",
    "land-intent",
    "orchestrate-coding-session",
    "orchestrate-intent",
    "pr-branch",
    "project-board",
    "prototype",
    "recover-specs",
    "review-ib",
    "review-pr",
    "security-review",
    "setup-dekspec",
    "spec-intent",
    "spike",
    "use-worktrees",
    "using-dekspec",
    "write-adr",
    "write-ae",
    "write-code-beads",
    "write-constitution",
    "write-corrections",
    "write-evals",
    "write-glossary",
    "write-goal-loop-contract",
    "write-ibs",
    "write-ic",
    "write-intent",
    "write-mission",
    "write-sp",
    "write-sv",
    "write-tests",
    "write-ws",
})

_FROZEN_COMMANDS = frozenset({
    "compile.md",
    "deepen-until-dry.md",
    "doctor.md",
    "graph-export.md",
    "land-intent.md",
    "man.md",
    "migrate.md",
    "orchestrate-coding-session.md",
    "orchestrate-intent.md",
    "pr-branch.md",
    "send-issue.md",
    "setup-dekspec.md",
    "spec-intent.md",
    "use-worktrees.md",
    "using-dekspec.md",
    "validate-artifact.md",
    "write-corrections.md",
    "write-glossary.md",
    "write-goal-loop-contract.md",
})

# IB-201 O-6: only these v0.124.0 DekTools setup/retired names apply,
# in either their skill-folder or command-file form.
_V0124_NAMES = frozenset({
    "setup-dektools", "analyze-module-depth", "archeology", "brownfield-ingest",
    "coding-session-forensics", "debug-testfail", "diagnose-bug",
    "orchestrate-module-deepening", "prj-mgr", "rotation-handoff", "write-issue-beads",
})
_MARKERS = ("_lib", "using-dekspec", "setup-dektools")


def _entry_names(folder: Path, *, skills: bool) -> set[str]:
    """Read one level only; an unavailable folder supplies no names."""
    try:
        return {
            entry.name for entry in folder.iterdir()
            if (entry.is_dir() if skills else entry.suffix == ".md" and entry.is_file())
        }
    except OSError:
        return set()


def _plugin_installed(home: Path) -> bool:
    plugins = home / ".claude" / "plugins"
    try:
        record = json.loads((plugins / "installed_plugins.json").read_text(encoding="utf-8"))
        installed = record.get("plugins") if isinstance(record, dict) else None
        entries = installed.get("dekspec@dekspec") if isinstance(installed, dict) else None
        if isinstance(entries, list) and entries:
            return True
    except (OSError, ValueError, RecursionError):
        # Bad JSON, invalid UTF-8 or an unreadable record does not veto the
        # independent cache signal.
        pass
    return bool(_entry_names(plugins / "cache" / "dekspec" / "dekspec", skills=True))


def leftover_core_tree_report(
    target_dir: Path, source_dir: Path, *, home: Path | None = None,
) -> str | None:
    """Return an advisory warning after install, or None when it does not apply.

    Read only the plugin signals and immediate skill/command entries. Ownership
    records suppress the warning; filesystem failures never fail the install.
    The caller prints the returned text to stderr without changing its status.
    """
    try:
        if not _plugin_installed(Path.home() if home is None else home):
            return None
        root = target_dir / ".claude"
        if (root / ".dektools-install.json").exists():
            return None
        if not any((root / "skills" / marker).is_dir() for marker in _MARKERS):
            return None
        skills = _entry_names(root / "skills", skills=True) & (
            _FROZEN_SKILLS | _V0124_NAMES | _entry_names(source_dir / "skills", skills=True)
        )
        commands = _entry_names(root / "commands", skills=False) & (
            _FROZEN_COMMANDS | {name + ".md" for name in _V0124_NAMES}
            | _entry_names(source_dir / "commands", skills=False)
        )
    except (OSError, RuntimeError):
        # Path.home can also fail when the host cannot resolve a home folder.
        return None
    paths = sorted(
        [f".claude/skills/{name}" for name in skills]
        + [f".claude/commands/{name}" for name in commands]
    )
    if not paths:
        return None
    lines = [
        "Warning: an unowned DekSpec core tree can shadow the installed "
        "dekspec@dekspec plugin. Review these paths relative to the install target:",
        *(f"  {path}" for path in paths),
    ]
    if skills & _V0124_NAMES or {name[:-3] for name in commands} & _V0124_NAMES:
        lines.append(
            "A v0.124.0 DekTools setup run wrote these setup/retired-name files "
            "without an ownership record. That is why the first run after upgrading "
            "reports the retired-name entries and setup-dektools copy instead of pruning them."
        )
    lines.append(
        "Manual removal: review the listed paths, keep anything written or edited "
        "by hand, and delete only the rest of the listed paths by hand. "
        "DekSpec deleted nothing because it cannot prove who wrote these files."
    )
    return "\n".join(lines)
