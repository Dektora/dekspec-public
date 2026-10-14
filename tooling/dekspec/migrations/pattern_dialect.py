"""Repository-wide, file-atomic ADR-068 conversion and diagnostics.

Only this migration interprets old patterns. Engine readers always use the
new dialect, regardless of whether a repository has been converted yet.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import yaml

from dekspec.dekspec_config import _validate
from dekspec.constraint_compiler.parser import IBParseError, _INT_GLOB_BULLET, _parse_ib_text
from dekspec.execution.artifact_edit import append_amendment_row
from dekspec.execution.contract import _legacy_protected
from dekspec.file_patterns import convert, legacy_matches, matches_any
from dekspec.file_pattern_paths import repository_paths, resolve_pattern
from dekspec.file_patterns.legacy import resolve_legacy
from dekspec.vibecoding_guard import _read_components_affected

MARKER = "folder-local"
HISTORY = {"COMPLETE", "COMPLETED", "SUPERSEDED", "DEPRECATED", "KILLED"}


@dataclass(frozen=True)
class Entry:
    file: str
    line: int
    pattern: str
    reading: str
    history: bool = False
    locked: bool = False
    suffix: str = ""
    source: str = ""
    inline: bool = False


def artifact_files(root: Path, spec_root: str = "dekspec") -> list[Path]:
    return sorted(p for folder, prefix in (("impl-briefs", "IB"), ("intents", "INT"), ("missions", "MSN"))
                  for p in (root / spec_root / folder).rglob(f"{prefix}-*.md"))


def marked(root: Path) -> bool:
    path = root / ".dekspec/config.yaml"
    if not path.exists():
        return False
    # Execution-only repositories can carry partial configuration; reading this
    # marker must not impose unrelated init-schema requirements on their lint.
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return isinstance(data, dict) and data.get("pattern_dialect") == MARKER


def _status(text: str) -> str:
    inline = re.search(r"^\*\*Status:\*\*[ \t]*(.+)$", text, re.M)
    if inline:
        return inline.group(1).split()[0].strip("`*_").upper()
    section = re.search(r"^##[ \t]+Status[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if section:
        return next((line.split()[0].strip("`*_").upper()
                     for line in section.group(1).splitlines() if line.strip()), "")
    return ""


def entries(root: Path, spec_root: str = "dekspec", *, problems: list[dict] | None = None) -> list[Entry]:
    """Locate patterns on their authored lines; prose and hypotheses are not patterns."""
    out = []
    for path in artifact_files(root, spec_root):
        text = path.read_text(encoding="utf-8")
        status = _status(text)
        brief = path.name.startswith("IB-")
        sections = {"Scope", "Protected Surfaces", "Do Not Touch", "Files to Modify"} if brief else {"components affected"}
        allowed = None
        first_entry = len(out)
        if brief:
            # The earlier lifecycle stage is only projected in a dry-run. Parse
            # its status successor in memory, keeping original lines and the
            # authored history/LOCKED classification for this conversion.
            from .disciplined_delegation import _STATUS_MAPS
            successor = _STATUS_MAPS["implementation_brief"].get(status)
            snapshot = text
            if successor:
                snapshot = re.sub(
                    rf"(^\*\*Status:\*\*[ \t]*`?){re.escape(status)}|(^## Status\s*\n\s*){re.escape(status)}",
                    lambda m: (m.group(1) or m.group(2)) + successor, text, count=1, flags=re.M)
            try:
                ir = _parse_ib_text(path, snapshot)
            except IBParseError as error:
                if problems is not None:
                    problems.append({"file": path.relative_to(root).as_posix(), "line": 1,
                                     "pattern": "", "history": status in HISTORY,
                                     "reason": f"cannot read brief patterns: {error}"})
                continue
            if ir.get("authority_policy") == "delegated":
                allowed = {s["glob"] for s in ir.get("scope", [])} | {s["surface"] for s in ir.get("protected_surfaces", [])}
            else:
                allowed = {f["file"].strip("`") for f in ir.get("files_to_modify", []) if f.get("file")}
                allowed.update(ir.get("do_not_touch") or _legacy_protected(text))
        else:
            allowed = set(_read_components_affected(path))
        section = ""
        for number, line in enumerate(text.splitlines(), 1):
            if line.startswith("## "):
                section = line[3:].strip().split(" (")[0]
                if not brief:
                    section = section.lower()
            if section not in sections or not re.match(r"\s*(?:[-*+]|\|)", line):
                continue
            field = line.split("|")[1].strip() if line.lstrip().startswith("|") else re.sub(r"^\s*[-*+]\s+", "", line).strip()
            tokens = re.findall(r"`([^`]+)`", field)
            if not brief:
                match = _INT_GLOB_BULLET.fullmatch(line)
                token = match.group(1).strip() if match else ""
                candidates = [(token, "`" + match.group(1) + "`")] if token and not token.startswith("path/") else []
            elif field.strip("`") in allowed:
                candidates = [(field.strip("`"), field)]
            elif brief and field in allowed:
                candidates = [(field, field)]
            else:
                candidates = [(token, "`" + token + "`") for token in tokens
                              if allowed is None or token in allowed]
            for token, source in candidates:
                pattern, sep, symbol = token.partition("::")
                out.append(Entry(path.relative_to(root).as_posix(), number, pattern,
                                 "brief" if brief else "components", status in HISTORY,
                                 status == "LOCKED", sep + symbol, source,
                                 section == "Do Not Touch" and line.lstrip().startswith("|")))
        # Use the same IR fields as load_contract (including legacy fallback),
        # and the actual Components reader, as an independent completeness floor.
        # A locator gap must never let a partially rewritten file gain the marker
        # silently. Unknown source positions are reported at the file's first line.
        located = {e.pattern + e.suffix for e in out[first_entry:]}
        reading = "brief" if brief else "components"
        for token in sorted(allowed - located):
            pattern = token.partition("::")[0] if brief else token
            if convert(pattern, reading).status != "unchanged" and problems is not None:
                problems.append({"file": path.relative_to(root).as_posix(), "line": 1,
                                 "pattern": pattern, "history": status in HISTORY,
                                 "reason": f"cannot locate old pattern dialect `{pattern}`; file left unchanged"})
    config = root / ".dekspec/config.yaml"
    if config.exists():
        # YAML nodes provide exact source lines, even for flow-style lists.
        doc = yaml.compose(config.read_text(encoding="utf-8"))
        def child(node, key):
            return next((v for k, v in node.value if k.value == key), None) if isinstance(node, yaml.MappingNode) else None
        values = child(child(doc, "execution"), "fingerprint_exclude")
        if isinstance(values, yaml.SequenceNode):
            out.extend(Entry(".dekspec/config.yaml", n.start_mark.line + 1, n.value, "brief") for n in values.value)
    path = root / ".dekspec/archeology-exclude"
    if path.exists():
        out.extend(Entry(".dekspec/archeology-exclude", i, line.strip(), "archeology-exclude")
                   for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                   if line.strip() and not line.lstrip().startswith("#"))
    return out


def unconverted(root: Path, spec_root: str = "dekspec") -> list[str]:
    if marked(root):
        return []
    problems: list[dict] = []
    located = entries(root, spec_root, problems=problems)
    return [f"{e.file}:{e.line}: old pattern dialect `{e.pattern}`; run dekspec migrate --apply"
            for e in located if not e.history and convert(e.pattern, e.reading).status != "unchanged"] + [
                f"{p['file']}:{p['line']}: {p['reason']}" for p in problems if not p["history"]]


def migrate(root: Path, *, apply: bool, spec_root: str = "dekspec") -> dict:
    report = {"stage": "pattern-dialect", "converted": [], "stopped": [], "history": [], "resolve_changes": []}
    if marked(root):
        report["already_converted"] = True
        return report
    grouped = {}
    paths = repository_paths(root)
    for entry in entries(root, spec_root, problems=report["stopped"]):
        result = convert(entry.pattern, entry.reading)
        item = asdict(entry)
        if entry.history:
            if result.status != "unchanged":
                item["gained"] = [p for p in paths if matches_any(p, [entry.pattern]) and not legacy_matches(entry.reading, p, entry.pattern)]
                item["lost"] = [p for p in paths if legacy_matches(entry.reading, p, entry.pattern) and not matches_any(p, [entry.pattern])]
                report["history"].append(item)
            continue
        grouped.setdefault(entry.file, []).append((entry, result))
    updates = {}
    unlocated_files = {p["file"] for p in report["stopped"]}
    for rel, group in grouped.items():
        stopped = [(e, r) for e, r in group if r.status == "stopped" or e.locked and r.status != "unchanged"]
        for entry, result in group:
            if entry.reading != "components":
                continue
            old_l7 = resolve_legacy(root, entry.pattern, braces=True)
            old_claim = resolve_legacy(root, entry.pattern)
            patterns = (entry.pattern,) if stopped or rel in unlocated_files else result.patterns
            new_resolve = any(resolve_pattern(root, p, paths=paths) for p in patterns)
            if old_l7 != new_resolve or old_claim != new_resolve:
                report["resolve_changes"].append({**asdict(entry), "old_l7_resolves": old_l7,
                                                  "old_claim_resolves": old_claim,
                                                  "new_resolves": new_resolve})
        if stopped:
            report["stopped"].extend({**asdict(e), "reason": "LOCKED: unlock normally before conversion" if e.locked else r.reason} for e, r in stopped)
            continue
        if rel in unlocated_files:
            continue
        changes = [(e, r) for e, r in group if r.status == "converted"]
        if not changes:
            continue
        text = (root / rel).read_bytes().decode("utf-8")
        if rel == ".dekspec/config.yaml":
            # Preserve all unrelated YAML, including retired executor/auth blocks.
            node = yaml.compose(text)
            execution = next(v for k, v in node.value if k.value == "execution")
            values = next(v for k, v in execution.value if k.value == "fingerprint_exclude")
            newline = "\r\n" if "\r\n" in text else "\n"
            starts = {scalar.start_mark.index for scalar in values.value}
            if (
                any(scalar.style in {"|", ">"} for scalar in values.value)
                or len(starts) != len(values.value)
                or any(index < values.start_mark.index or index >= values.end_mark.index for index in starts)
            ):
                # Aliases share their anchor's node marks, possibly in another
                # setting; block scalars include their terminating newline.
                # Render the sequence's values without editing those spans.
                rendered = json.dumps([p for _entry, result in group for p in result.patterns])
                if not values.flow_style:
                    # Extra indentation also supports YAML's indentless lists;
                    # keep comments before the sequence separate from its value.
                    rendered = "  " + rendered + newline + " " * values.end_mark.column
                text = text[:values.start_mark.index] + rendered + text[values.end_mark.index:]
            else:
                for scalar, (_entry, result) in reversed(list(zip(values.value, group))):
                    if result.status != "converted":
                        continue
                    # Replace only the scalar, keeping the key, comments, item
                    # delimiters and neighboring settings at their authored positions.
                    separator = (", " if values.flow_style else
                                 newline + " " * (scalar.start_mark.column - 2) + "- ")
                    rendered = separator.join(json.dumps(p) for p in result.patterns)
                    text = text[:scalar.start_mark.index] + rendered + text[scalar.end_mark.index:]
        else:
            lines = text.splitlines(keepends=True)
            for e, r in reversed(changes):
                original = lines[e.line - 1]
                if rel == ".dekspec/archeology-exclude":
                    lines[e.line - 1] = "".join(p + "\n" for p in r.patterns)
                else:
                    token = e.source
                    replacements = ["`" + p + e.suffix + "`" for p in r.patterns]
                    if e.inline:
                        lines[e.line - 1] = original.replace(token, ", ".join(replacements), 1)
                    else:
                        lines[e.line - 1] = "".join(original.replace(token, p, 1) for p in replacements)
            text = "".join(lines)
            if rel.endswith(".md"):
                text = append_amendment_row(text, f"| {date.today().isoformat()} | Editorial | ADR-068: convert file patterns preserving their exact coverage. | dekspec migrate |")
        updates[rel] = text
        report["converted"].append(rel)
    config_rel = ".dekspec/config.yaml"
    config_path = root / config_rel
    config_text = updates.get(config_rel, config_path.read_bytes().decode("utf-8") if config_path.exists() else "schema_version: 0.1.0\nmethodology_profile: full\n")
    # O-20: even a stopped exclusion file gets the marker, without rewriting
    # any existing line. Otherwise a rerun would convert other files twice.
    separator = "" if config_text.endswith("\n") else "\n"
    config_text += separator + "pattern_dialect: folder-local\n"
    data = yaml.safe_load(config_text)
    _validate({k: v for k, v in data.items() if k not in {"executor", "auth"}}, config_path)
    updates[config_rel] = config_text
    if apply:
        for rel, text in updates.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
    report["applied"] = apply
    return report
