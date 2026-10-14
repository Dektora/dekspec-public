"""Choose and prepare the disclosure shown after successful install or sync.

Keep notice policy, resolution and persistence together: callers receive output
only after the text is available and any required atomic record write succeeded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .role_disclosure import (
    RECORD_FILENAME,
    DisclosureRecordError,
    RoleChange,
    compare,
    read_record,
    record_disclosure,
)
from .vendoring import resolve_lib


class NoticeError(Exception):
    """The notice could not be prepared; nothing may be printed as disclosure."""


@dataclass(frozen=True)
class NoticeDecision:
    form: str
    notice: str | None
    changed_roles: tuple[RoleChange, ...] = ()
    written: bool = False

    def render(self) -> str:
        if self.notice is None:
            return f"Project rules disclosure recorded in {RECORD_FILENAME}.\n"
        text = self.notice
        if self.changed_roles:
            if not text.endswith("\n"):
                text += "\n"
            for change in self.changed_roles:
                old = change.recorded if change.recorded is not None else "none"
                new = change.current if change.current is not None else "none"
                text += f"  {change.role}: {old} -> {new}\n"
        return text

    def as_json(self) -> dict:
        return {
            "form": self.form,
            "notice": self.notice,
            "changed_roles": [
                {"id": c.role, "recorded": c.recorded, "current": c.current}
                for c in self.changed_roles
            ],
            "record": RECORD_FILENAME,
            "written": self.written,
        }


def prepare(
    repo_root: Path, *, release: str, platform: str | None = None,
    release_moved: bool = False, dry_run: bool = False,
) -> NoticeDecision:
    """Resolve the form and record it, after the caller's own work succeeds.

    A platform denotes install, whose empty targets never hold disclosure
    history. Sync compares release movement, rather than record release alone.
    Invalid history is missing history. Dry runs perform all reads, no writes.
    """
    records = platform is None or (repo_root / ".dekspec-version").is_file() or (
        repo_root / "dekspec"
    ).is_dir()
    try:
        previous = read_record(repo_root) if records else None
    except DisclosureRecordError:
        previous = None
    diff = compare(previous, release=release, platform=platform)
    due = diff.due if platform is not None else (
        previous is None or release_moved or bool(diff.role_changes)
    )
    form = "named-roles" if diff.role_changes else "full" if due else "recorded"
    notice = None
    if due:
        # Match `resource lib`: sync supplies --at; install has only --target,
        # which locates history and emitted files, not resource lookup.
        notice_root = repo_root if platform is None else Path.cwd()
        path = notice_root / "plugins/dekspec/skills/_lib/role-project-rules.md"
        try:
            resolved = resolve_lib("role-project-rules", repo_root=notice_root)
            if resolved is None:
                raise FileNotFoundError("notice not found in project or installed library")
            path = resolved
            notice = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise NoticeError(
                f"Cannot resolve {path} via dekspec resource lib role-project-rules: {exc}"
            ) from exc
    written = False
    if records and not dry_run:
        try:
            recorded = record_disclosure(repo_root, release=release, platform=platform)
        except (OSError, UnicodeError, DisclosureRecordError) as exc:
            raise NoticeError(f"Cannot write {repo_root / RECORD_FILENAME}: {exc}") from exc
        written = recorded != previous
    return NoticeDecision(form, notice, diff.role_changes, written)
