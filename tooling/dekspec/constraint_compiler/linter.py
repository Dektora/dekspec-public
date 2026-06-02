"""Implementation Brief structural and syntactic linter.

Defines rules to validate the structure, metadata keys, section headers, markdown tables,
checklist boxes, and path integrity of an Implementation Brief (IB) markdown file.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Known metadata keys required in the header block
REQUIRED_META_KEYS = {
    "Spec",
    "Intent",
    "Source AEs",
    "Depends on",
    "Production gate",
    "Status",
}

# Required H2 section headers
REQUIRED_H2_SECTIONS = [
    "Goal",
    "Out of Scope",
    "Files to Modify",
    "Do Not Touch",
    "Governing ADRs",
    "Constraints & Decisions",
    "Done When",
    "Open Issues",
]

# Name of the Reuse Firewall declaration section (ds-0a7w). Not in REQUIRED_H2_SECTIONS
# because it is required only on code-bearing IBs (see lint_ib section 3b).
REUSE_INVENTORY_SECTION = "Reuse Inventory"

# Exact placeholder phrases from the template to prevent unedited briefs
PLACEHOLDER_PATTERNS = [
    r"\[Component/Feature\]",
    r"\[slug\]",
    r"\[what changes\]",
    r"\[cuda:0 / cuda:1-7 / cpu / n/a\]",
    r"\[bfloat16 / float32 / n/a\]",
    r"\[shadow / neo4j / n/a\]",
    r"\[shadow\+buffered / neo4j_direct / n/a\]",
    r"\[max error specification / n/a\]",
    r"\[title\]",
    r"\[what to do — concrete, not a reference to a document\]",
    r"\[one-line summary of the finding that informed this IB\]",
    r"\[Specific observable outcome\]",
    r"\[concrete input with exact values\]",
    r"\[Issue description\]",
    r"\[initial draft / audit / review / resync / cascade from <artifact>\]",
    r"IC-NNN",
    r"WS-NNN",
    r"INT-NNN",
    r"AE-NNN",
    r"ADR-NNN",
]


def find_workspace_root(start_path: Path) -> Path | None:
    """Walk up parent directories to find the repository/workspace root."""
    curr = start_path.resolve()
    # If starting with a file, use its parent
    if curr.is_file():
        curr = curr.parent
    for parent in [curr] + list(curr.parents):
        if (parent / ".git").exists() or (parent / ".dekspec").exists():
            return parent
    return None


def lint_ib(text_or_path: str | Path, workspace_root: Path | None = None) -> list[dict[str, Any]]:
    """Parse and lint an Implementation Brief markdown file/text.

    Returns a list of dicts describing violations:
    {
        "rule": str,
        "severity": str ("P1" or "P2" or "P3"),
        "message": str,
        "line": int | None,
    }
    """
    violations: list[dict[str, Any]] = []

    # Resolve text and filepath
    text = ""
    file_path: Path | None = None
    if isinstance(text_or_path, Path):
        file_path = text_or_path.resolve()
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception as e:
            violations.append({
                "rule": "FILE_READ_ERROR",
                "severity": "P1",
                "message": f"Could not read file: {e}",
                "line": None,
            })
            return violations
    else:
        text = str(text_or_path)

    # 1. H1 Present & Format Checks
    h1_matches = list(re.finditer(r"^#\s+(.+)$", text, re.MULTILINE))
    if not h1_matches:
        violations.append({
            "rule": "H1_PRESENT",
            "severity": "P1",
            "message": "Missing top-level H1 heading.",
            "line": None,
        })
    elif len(h1_matches) > 1:
        violations.append({
            "rule": "H1_UNIQUE",
            "severity": "P1",
            "message": "Multiple H1 headings found (expected exactly one).",
            "line": get_line_number(text, h1_matches[1].start()),
        })
    else:
        h1_text = h1_matches[0].group(1).strip()
        if not h1_text.startswith("Implementation Brief:"):
            violations.append({
                "rule": "H1_FORM",
                "severity": "P1",
                "message": "H1 heading must start with '# Implementation Brief: '",
                "line": get_line_number(text, h1_matches[0].start()),
            })

    # 2. Metadata Keys check
    # Find H1 end and first H2 start to isolate the header block
    h1_end = h1_matches[0].end() if h1_matches else 0
    first_h2 = text.find("\n## ", h1_end)
    header_block = text[h1_end:first_h2] if first_h2 != -1 else text[h1_end:]

    meta_lines = list(re.finditer(r"^\*\*([^*]+?):\*\*\s*(.+?)\s*$", header_block, re.MULTILINE))
    found_keys = set()
    for m in meta_lines:
        key = m.group(1).strip()
        val = m.group(2).strip()
        found_keys.add(key)
        line_num = get_line_number(text, h1_end + m.start())

        if key not in REQUIRED_META_KEYS:
            violations.append({
                "rule": "METADATA_KEY_UNKNOWN",
                "severity": "P2",
                "message": f"Unknown metadata key in header block: '{key}'",
                "line": line_num,
            })
        
        # Path Integrity checking if workspace root is available
        if workspace_root is None and file_path is not None:
            workspace_root = find_workspace_root(file_path)

        if workspace_root:
            if key == "Spec":
                spec_path_str = val.strip("`").strip()
                if spec_path_str and spec_path_str.lower() != "none":
                    spec_path = workspace_root / spec_path_str
                    if not spec_path.exists():
                        violations.append({
                            "rule": "SPEC_PATH_INVALID",
                            "severity": "P1",
                            "message": f"Referenced Working Spec file does not exist: '{spec_path_str}'",
                            "line": line_num,
                        })
            elif key == "Intent":
                # Intent can be a markdown link like [INT-032](dekspec/intents/...)
                intent_path_str = val
                link_match = re.search(r"\[.+?\]\((.+?)\)", val)
                if link_match:
                    intent_path_str = link_match.group(1)
                else:
                    intent_path_str = val.strip("`").strip()
                
                if intent_path_str and intent_path_str.lower() != "none":
                    intent_path = workspace_root / intent_path_str
                    if not intent_path.exists():
                        violations.append({
                            "rule": "INTENT_PATH_INVALID",
                            "severity": "P1",
                            "message": f"Referenced Intent file does not exist: '{intent_path_str}'",
                            "line": line_num,
                        })

    missing_keys = REQUIRED_META_KEYS - found_keys
    if missing_keys:
        violations.append({
            "rule": "METADATA_KEYS_MISSING",
            "severity": "P1",
            "message": f"Missing required metadata keys in header block: {', '.join(sorted(missing_keys))}",
            "line": get_line_number(text, h1_end),
        })

    # 3. Required Sections checks
    sections = split_h2_sections(text)
    for sect_name in REQUIRED_H2_SECTIONS:
        if sect_name not in sections:
            violations.append({
                "rule": f"SECTION_{sect_name.upper().replace(' ', '_')}_MISSING",
                "severity": "P1",
                "message": f"Missing required H2 section: '## {sect_name}'",
                "line": None,
            })
        else:
            body = sections[sect_name].strip()
            line_num = get_section_line_number(text, sect_name)
            if not body:
                violations.append({
                    "rule": f"SECTION_{sect_name.upper().replace(' ', '_')}_EMPTY",
                    "severity": "P1",
                    "message": f"Required section '## {sect_name}' is empty.",
                    "line": line_num,
                })

    # 3b. Reuse Inventory required on code-bearing IBs (Reuse Firewall — upstream half, ds-0a7w)
    # An IB is "code-bearing" when its Files to Modify table has at least one concrete
    # (non-placeholder, non-empty) data row. Such briefs must declare what existing
    # capabilities the implementer is required to reuse instead of reimplementing.
    files_body = sections.get("Files to Modify", "")
    code_bearing = any(_row_is_real(r) for r in _table_data_rows(files_body))
    if code_bearing:
        reuse_body = sections.get(REUSE_INVENTORY_SECTION)
        if reuse_body is None:
            violations.append({
                "rule": "REUSE_INVENTORY_MISSING",
                "severity": "P2",
                "message": (
                    "Code-bearing IB must declare a '## Reuse Inventory' section naming "
                    "existing capabilities to reuse (use a single 'none' row if net-new)."
                ),
                "line": None,
            })
        elif not any(_row_is_real(r) for r in _table_data_rows(reuse_body)):
            violations.append({
                "rule": "REUSE_INVENTORY_EMPTY",
                "severity": "P2",
                "message": (
                    "'## Reuse Inventory' has no concrete entries. Name at least one capability "
                    "to reuse, or a single 'none' row for genuinely net-new work."
                ),
                "line": get_section_line_number(text, REUSE_INVENTORY_SECTION),
            })

    # 4. Placeholder text checks
    for pat in PLACEHOLDER_PATTERNS:
        matches = list(re.finditer(pat, text))
        for m in matches:
            violations.append({
                "rule": "PLACEHOLDER_FOUND",
                "severity": "P2",
                "message": f"Found unresolved template placeholder: '{m.group(0)}'",
                "line": get_line_number(text, m.start()),
            })

    # 5. Table validation checks
    # Find all table blocks (contiguous lines starting with '|')
    table_blocks = find_table_blocks(text)
    for start_idx, table_lines in table_blocks:
        if len(table_lines) < 2:
            violations.append({
                "rule": "TABLE_MALFORMED",
                "severity": "P1",
                "message": "Table block must contain at least a header row and a separator row.",
                "line": get_line_number(text, start_idx),
            })
            continue

        # Parse column separator row (row 2)
        separator_line = table_lines[1]
        sep_cells = [c.strip() for c in separator_line.strip("|").split("|")]
        is_valid_sep = all(re.fullmatch(r":?-{2,}:?", c) for c in sep_cells if c)
        if not is_valid_sep:
            violations.append({
                "rule": "TABLE_SEPARATOR_MISSING",
                "severity": "P1",
                "message": "Table header row must be followed immediately by a separator row (e.g. '|---|---|').",
                "line": get_line_number(text, start_idx) + 1,
            })

        # Columns count check
        header_cells_count = len([c for c in table_lines[0].strip("|").split("|")])
        for offset, line in enumerate(table_lines):
            # If it doesn't end with | or has mismatched cols
            cells = [c for c in line.strip("|").split("|")]
            if len(cells) != header_cells_count:
                violations.append({
                    "rule": "TABLE_COLUMN_MISMATCH",
                    "severity": "P1",
                    "message": f"Table row has {len(cells)} cells, but header has {header_cells_count}.",
                    "line": get_line_number(text, start_idx) + offset,
                })

    # 6. Checklist brackets checks (Done When & Open Issues)
    checklist_sections = ["Done When", "Open Issues"]
    for sect_name in checklist_sections:
        if sect_name in sections:
            body = sections[sect_name]
            sect_start = get_section_body_start_idx(text, sect_name)
            for m in re.finditer(r"^[-*]\s+(.+)$", body, re.MULTILINE):
                bullet_text = m.group(1).strip()
                bullet_start = m.start(1)
                line_num = get_line_number(text, sect_start + bullet_start)

                # Check if it starts with [ ] or [x] or [/]
                chk_match = re.match(r"^\[([\sxX/])\]\s*(.*)$", bullet_text)
                if not chk_match:
                    violations.append({
                        "rule": "CHECKLIST_BRACKETS_MALFORMED",
                        "severity": "P2",
                        "message": "Checklist item must start with a valid checkbox '[ ]', '[x]', or '[/]' followed by space.",
                        "line": line_num,
                    })
                elif chk_match.group(1) == " " and not chk_match.group(2).strip():
                    violations.append({
                        "rule": "CHECKLIST_ITEM_EMPTY",
                        "severity": "P2",
                        "message": "Checklist item text cannot be empty.",
                        "line": line_num,
                    })

    # Sort violations by line number (placing None/unknown at the end)
    violations.sort(key=lambda x: (x["line"] is None, x["line"]))
    return violations


def get_line_number(text: str, char_idx: int) -> int:
    """Return 1-indexed line number for a given character index in the text."""
    return text[:char_idx].count("\n") + 1


def get_section_line_number(text: str, heading: str) -> int | None:
    """Find line number of '## heading'."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if m:
        return get_line_number(text, m.start())
    return None


def get_section_body_start_idx(text: str, heading: str) -> int:
    """Find char index where the body of H2 section starts."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE)
    if m:
        return m.end()
    return 0


def split_h2_sections(text: str) -> dict[str, str]:
    """Split markdown text into a {h2_name: body} dict."""
    sections: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        h2_match = re.match(r"^##\s+(.+?)\s*$", line)
        if h2_match:
            if current_name is not None:
                sections[current_name] = "\n".join(current_lines).strip("\n")
            current_name = h2_match.group(1).strip()
            current_lines = []
        elif current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = "\n".join(current_lines).strip("\n")

    return sections


def find_table_blocks(text: str) -> list[tuple[int, list[str]]]:
    """Identify contiguous groups of markdown lines that comprise tables."""
    blocks: list[tuple[int, list[str]]] = []
    lines = text.splitlines()
    in_table = False
    current_lines: list[str] = []
    start_char_idx = 0
    accumulated_chars = 0

    for i, line in enumerate(lines):
        line_len = len(line) + 1  # include newline char
        if line.strip().startswith("|"):
            if not in_table:
                in_table = True
                start_char_idx = accumulated_chars
                current_lines = []
            current_lines.append(line)
        else:
            if in_table:
                blocks.append((start_char_idx, current_lines))
                in_table = False
        accumulated_chars += line_len

    if in_table:
        blocks.append((start_char_idx, current_lines))

    return blocks


def _table_data_rows(section_body: str) -> list[list[str]]:
    """Return the data rows (header + separator dropped) of every table in a section body."""
    rows: list[list[str]] = []
    for _start, table_lines in find_table_blocks(section_body):
        for line in table_lines[2:]:  # skip header + separator
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows.append(cells)
    return rows


def _row_is_real(cells: list[str]) -> bool:
    """A row is 'real' (author-edited) if it has content and no unresolved [bracket] placeholder."""
    if not any(c for c in cells):
        return False
    return not any(re.search(r"\[[^\]]+\]", c) for c in cells)
