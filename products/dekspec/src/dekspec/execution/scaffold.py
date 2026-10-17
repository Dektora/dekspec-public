"""Hides which form a new brief takes, where that form is read from (the project's own copy first, then the installed library) and how the author's choices are written into it; the lean switch is read here, never by callers.
new_brief(repo_root, slug, *, author, title=None, parent=None, form=None, runner="pytest", spec_root="dekspec") writes the next free IB-NNN as DRAFT and returns NewBrief(ib, path, form, notice), path absolute; `dekspec ib new <slug>` takes --title, --parent, --form lean|delegated and --runner NAME, and its --json prints ib, path, form and notice.
form None means lean when lean is switched on, else delegated; "delegated" is written exactly as today whatever the runner; "lean" while lean is off is still written, and notice says acceptance refuses it until lean is switched on (notice is "" otherwise); title defaults to the slug's words.
Callers never know template file names, the fallback order or where the switch is kept; the runner is written as given and never judged, so an unfamiliar runner is not an error.
ExecutionError (REFUSED, exit 1 from the CLI) names an unknown form, or the form when neither the project nor the installed library has it, and then nothing is written.
Alternatives: (a) flags handled inline in cmd_new; (b) a form object the caller resolves, renders and then writes; (c) one call returning one value. (c) wins: the CLI, which /write-ibs drives, needs one step and one answer; (a) keeps template and switch knowledge in the CLI, and (b) makes callers sequence calls and own the write. --form takes free text rather than argparse choices, so an unknown form is this REFUSED (exit 1, named) and not a usage error (exit 2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dekspec.execution.engine import ExecutionError
from dekspec.execution.settings import load_settings

__all__ = ["NewBrief", "new_brief"]

# Each form and the template that holds it; the project's copy of a template
# overrides the installed one by the rule every template follows
# (`dekspec.vendoring.resolve_template`).
_TEMPLATES = {"delegated": "implementation-brief", "lean": "implementation-brief-lean"}
_TITLE = "[bounded outcome, in a few words]"
_LOG_HEADER = "| Date | Type | Change | Author |\n|------|------|--------|--------|"
_LEAN_OFF = ("this brief is in the lean form, and `dekspec ib accept` refuses it until lean "
             "is switched on (execution.lean: true in .dekspec/config.yaml)")


@dataclass(frozen=True)
class NewBrief:
    """One brief just written: its id, its file, the form it took, and a notice for the author ("" when none)."""

    ib: str
    path: Path
    form: str
    notice: str


def new_brief(repo_root: Path, slug: str, *, author: str, title: str | None = None,
              parent: str | None = None, form: str | None = None, runner: str = "pytest",
              spec_root: str = "dekspec") -> NewBrief:
    """Write a new DRAFT brief as the module note states and describe it."""
    from dekspec.vendoring import resolve_template

    root = Path(repo_root).resolve()
    lean_on = load_settings(root, spec_root=spec_root).lean
    chosen = form if form is not None else ("lean" if lean_on else "delegated")
    if chosen not in _TEMPLATES:
        raise ExecutionError(f"unknown brief form {chosen!r}: choose lean or delegated")
    template = resolve_template(_TEMPLATES[chosen], root)
    if template is None:
        raise ExecutionError(f"the {chosen} brief form was found neither in this project "
                             "nor in the installed DekSpec library")

    # Numbering and file naming are today's: the next number after every IB in
    # the spec tree, provisional ones included.
    tree = root / spec_root
    used = [int(m.group(1)) for p in tree.rglob("IB-*.md")
            if (m := re.match(r"(?:P-)?IB-(\d{3,})-", p.name))]
    ib = f"IB-{(max(used) + 1 if used else 1):03d}"
    name = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")

    text = template.read_text(encoding="utf-8").replace(_TITLE, title or name.replace("-", " "), 1)
    if parent:
        text = text.replace("**Parent:** none", f"**Parent:** {parent}", 1)
    if chosen == "delegated":
        # Exactly what `ib new` wrote before the lean form existed (IB-300 O-3).
        text = text.replace(_LOG_HEADER, f"{_LOG_HEADER}\n| {date.today().isoformat()} | Create | "
                            f"Scaffolded with `dekspec ib new`. | {author} |", 1)
    else:
        # The lean form keeps no Amendment Log (ADR-079 item 7); its one
        # condition names its tests under the author's runner, unjudged.
        text = re.sub(r"(?m)^(\s+)pytest:", lambda m: f"{m.group(1)}{runner}:", text, count=1)

    folder = tree / "impl-briefs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{ib}-{name}.md"
    path.write_text(text, encoding="utf-8")
    notice = _LEAN_OFF if chosen == "lean" and not lean_on else ""
    return NewBrief(ib=ib, path=path, form=chosen, notice=notice)
