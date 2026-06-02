"""Promotion atomic for `dekspec/provisional/<slug>/` incubation folders.

Walks an incubation folder, assigns the next-free canonical ID per IR
kind, rewrites every artifact's ID heading + `**<Kind> ID:**` field +
intra-folder cross-references, atomically moves each file to its
canonical directory, and deletes the now-empty incubation folder.

Implements the closing-the-loop verb described in
INT-provisional-promote-verb (provisional Intent under MSN-014).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


# IR kind -> canonical directory under `dekspec/`. IB goes to the
# `queued/` lane (IB lifecycle band 0–2 lands there per
# T-STATUS-IB-FOLDER); engineers transition through active/completed
# via the IB status walk after promotion.
KIND_TO_DIR: dict[str, str] = {
    "INT": "intents",
    "MSN": "missions",
    "ADR": "adrs",
    "AE": "architecture-elements",
    "IC": "interface-contracts",
    "WS": "working-specs",
    "IB": "impl-briefs/queued",
    "SP": "security-profiles",
}


@dataclass(frozen=True)
class PromotionStep:
    """One file's transition from provisional to canonical."""

    kind: str          # e.g. "INT"
    old_id: str        # e.g. "INT-provisional-foundation"
    new_id: str        # e.g. "INT-081" (canonical, post-promotion)
    old_path: Path     # full absolute path before promotion
    new_path: Path     # full absolute path after promotion
    mode: str = "new"  # "new" (next-free ID) | "replace" (preserved ID)


class PromoteError(Exception):
    pass


_KIND_FILE_RE = re.compile(r"^([A-Z]+)-provisional-(.+)\.md$")

# Matches a `replaces: <KIND-NNN>` line inside the YAML frontmatter (or
# anywhere in the file body — the rule is permissive). Supports
# `replaces: AE-007` and `replaces: ADR-019` shapes.
_REPLACES_RE = re.compile(r"^\s*replaces\s*:\s*([A-Z]+-\d{3,})\s*$", re.MULTILINE)


def parse_replaces_id(path: Path) -> str | None:
    """Return the canonical ID declared in this provisional artifact's
    `replaces:` frontmatter field, or None if absent.

    The convention from INT-provisional-cow-spec-staging: when a
    provisional artifact is a copy-on-write of a canonical artifact,
    its frontmatter carries `replaces: <KIND-NNN>` naming the
    canonical it intends to replace at promotion time.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return None
    rm = _REPLACES_RE.search(m.group(1))
    return rm.group(1) if rm else None


def find_canonical_path(canonical_id: str, dekspec_dir: Path) -> Path | None:
    """Find the existing canonical artifact file for `canonical_id`.

    Returns the first `<kind>-NNN-*.md` matching in the canonical
    directory, or None if not found. For IBs, searches all 3 lifecycle
    subdirs (queued, active, completed).
    """
    parts = canonical_id.split("-", 1)
    if len(parts) != 2:
        return None
    kind = parts[0]
    if kind not in KIND_TO_DIR:
        return None
    if kind == "IB":
        for sub in ("queued", "active", "completed"):
            d = dekspec_dir / "impl-briefs" / sub
            if d.is_dir():
                for p in d.glob(f"{canonical_id}-*.md"):
                    return p
        return None
    d = dekspec_dir / KIND_TO_DIR[kind]
    if not d.is_dir():
        return None
    for p in d.glob(f"{canonical_id}-*.md"):
        return p
    return None


def _find_next_canonical_id(kind: str, dekspec_dir: Path) -> int:
    """Scan the canonical directory for the highest existing
    `<kind>-NNN-*.md` and return the next-free integer."""
    if kind not in KIND_TO_DIR:
        raise PromoteError(f"Unknown IR kind: {kind!r}")
    if kind == "IB":
        # IB lifecycle uses 3 subdirs; scan all of them.
        search_root = dekspec_dir / "impl-briefs"
        files = list(search_root.rglob(f"{kind}-*.md"))
    else:
        search_root = dekspec_dir / KIND_TO_DIR[kind]
        files = list(search_root.glob(f"{kind}-*.md")) if search_root.exists() else []
    nums: list[int] = []
    for f in files:
        m = re.match(rf"^{kind}-(\d+)-", f.name)
        if m:
            n = int(m.group(1))
            # INT-999 / similar sentinel IDs are reserved markers; ignore.
            if n < 900:
                nums.append(n)
    return max(nums, default=0) + 1


def plan_promotion(
    incubation_dir: Path, dekspec_dir: Path
) -> list[PromotionStep]:
    """Walk `incubation_dir` and build the renumber plan.

    Files are scanned in filename order so the renumbering is
    deterministic across runs (same set of files in same order ->
    same canonical IDs assigned).
    """
    if not incubation_dir.is_dir():
        raise PromoteError(f"Incubation folder not found: {incubation_dir}")

    steps: list[PromotionStep] = []
    next_id_per_kind: dict[str, int] = {}
    for f in sorted(incubation_dir.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue
        m = _KIND_FILE_RE.match(f.name)
        if not m:
            continue
        kind, slug = m.group(1), m.group(2)
        if kind not in KIND_TO_DIR:
            continue
        old_id = f"{kind}-provisional-{slug}"

        # REPLACE mode: provisional artifact declares `replaces:
        # <KIND-NNN>` -> preserve the canonical ID; overwrite the
        # canonical file at its existing path.
        replaces_id = parse_replaces_id(f)
        if replaces_id is not None and replaces_id.split("-", 1)[0] == kind:
            canonical_path = find_canonical_path(replaces_id, dekspec_dir)
            if canonical_path is None:
                raise PromoteError(
                    f"{f.name} declares `replaces: {replaces_id}` but no "
                    f"canonical {replaces_id}-*.md exists in the spec tree. "
                    f"Either remove the `replaces:` line (NEW mode) or fix "
                    f"the target ID."
                )
            steps.append(
                PromotionStep(
                    kind=kind,
                    old_id=old_id,
                    new_id=replaces_id,
                    old_path=f,
                    new_path=canonical_path,
                    mode="replace",
                )
            )
            continue

        # NEW mode: allocate next-free canonical ID.
        if kind not in next_id_per_kind:
            next_id_per_kind[kind] = _find_next_canonical_id(kind, dekspec_dir)
        new_num = next_id_per_kind[kind]
        next_id_per_kind[kind] += 1
        new_id = f"{kind}-{new_num:03d}"
        new_filename = f"{new_id}-{slug}.md"
        target_dir = dekspec_dir / KIND_TO_DIR[kind]
        steps.append(
            PromotionStep(
                kind=kind,
                old_id=old_id,
                new_id=new_id,
                old_path=f,
                new_path=target_dir / new_filename,
                mode="new",
            )
        )
    return steps


def _rewrite_file_contents(
    path: Path,
    own_old_id: str,
    own_new_id: str,
    rewrites: dict[str, str],
) -> None:
    """Rewrite a single artifact's body.

    1. Replace the H1 heading `# {own_old_id}` -> `# {own_new_id}`
       (first occurrence only). For Mission artifacts, the parser
       requires the literal `Mission ` prefix before the ID
       (`# Mission MSN-NNN: <title>`); the rewriter handles both
       shapes:
         - `# MSN-provisional-<slug>: <title>` -> `# Mission MSN-NNN: <title>`
         - `# Mission MSN-provisional-<slug>: <title>` -> `# Mission MSN-NNN: <title>`
    2. Replace `**Mission ID:** {old}` -> `**Mission ID:** {new}` and
       similarly for `**Intent ID:**`, both if the value matches the
       artifact's own old id.
    3. Replace every `{old_id}` -> `{new_id}` substring elsewhere in
       the body (cross-references to sibling provisional artifacts).
    """
    content = path.read_text(encoding="utf-8")

    # 1. Own H1 heading. Special-case Mission so the canonical
    # `# Mission MSN-NNN: ...` shape is always produced.
    is_mission = own_old_id.startswith("MSN-")
    if is_mission:
        # Match either bare or `Mission `-prefixed form.
        content = re.sub(
            rf"^# (?:Mission )?{re.escape(own_old_id)}\b",
            f"# Mission {own_new_id}",
            content,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        content = re.sub(
            rf"^# {re.escape(own_old_id)}\b",
            f"# {own_new_id}",
            content,
            count=1,
            flags=re.MULTILINE,
        )

    # 2. Mission ID / Intent ID fields (matching the own id only).
    for field in ("Mission ID", "Intent ID"):
        content = re.sub(
            rf"^\*\*{field}:\*\*\s+{re.escape(own_old_id)}\b",
            f"**{field}:** {own_new_id}",
            content,
            flags=re.MULTILINE,
        )

    # 3. Cross-references (every old_id -> new_id, including own).
    # Sort by length descending so longer slugs are matched before any
    # prefix-overlapping shorter slug (defensive; provisional slugs
    # rarely overlap in practice).
    for old, new in sorted(rewrites.items(), key=lambda kv: -len(kv[0])):
        content = content.replace(old, new)

    path.write_text(content, encoding="utf-8")


def _git_mv(src: Path, dst: Path, repo_root: Path, overwrite: bool = False) -> None:
    """Move a file with `git mv` when possible, falling back to
    `shutil.move` if git isn't available or the source isn't tracked.

    When `overwrite=True` (REPLACE mode), the destination is removed
    first so `git mv` doesn't refuse on the already-tracked target.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and dst.exists():
        try:
            subprocess.run(
                ["git", "rm", "-f", str(dst)],
                check=True,
                capture_output=True,
                cwd=str(repo_root),
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            dst.unlink()
    try:
        subprocess.run(
            ["git", "mv", str(src), str(dst)],
            check=True,
            capture_output=True,
            cwd=str(repo_root),
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        shutil.move(str(src), str(dst))


def apply_promotion(
    steps: list[PromotionStep],
    incubation_dir: Path,
    repo_root: Path,
) -> None:
    """Apply the renumber plan: rewrite contents, move files,
    delete the incubation folder if empty."""
    rewrites: dict[str, str] = {s.old_id: s.new_id for s in steps}
    for step in steps:
        _rewrite_file_contents(
            step.old_path,
            own_old_id=step.old_id,
            own_new_id=step.new_id,
            rewrites=rewrites,
        )
    for step in steps:
        _git_mv(
            step.old_path,
            step.new_path,
            repo_root,
            overwrite=(step.mode == "replace"),
        )
    # Best-effort folder cleanup; the audit rule
    # L-PROVISIONAL-TREE-PRESENT surfaces lingering non-empty folders.
    try:
        incubation_dir.rmdir()
    except OSError:
        pass


def render_plan(steps: list[PromotionStep], repo_root: Path) -> str:
    """Pretty-print the renumber plan as a scannable table."""
    if not steps:
        return "  (no artifacts to promote)\n"
    lines = []
    lines.append("  Mode     Kind  Provisional ID                               Canonical ID")
    lines.append("  -------  ----  -------------------------------------------  -----------")
    for s in steps:
        mode_label = "REPLACE" if s.mode == "replace" else "NEW    "
        lines.append(
            f"  {mode_label}  {s.kind:4s}  {s.old_id:<43s}  {s.new_id}"
        )
    lines.append("")
    lines.append("  Files will be moved to:")
    for s in steps:
        suffix = "  (overwrites existing canonical)" if s.mode == "replace" else ""
        lines.append(f"    {s.new_path.relative_to(repo_root)}{suffix}")
    return "\n".join(lines) + "\n"
