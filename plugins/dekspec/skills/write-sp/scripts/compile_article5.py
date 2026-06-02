#!/usr/bin/env python3
"""Compile Constitution Article 5 security commitments into SP-shaped stubs.

write-sp Create Mode Step 3 reads `dekspec/constitution.md` Article 5
(Development Workflow) for any SAST / DAST / secret-store / supply-chain
commitments and compiles them into the SP's typed-record arrays. This script
does the mechanical extraction: it locates the Article that holds security
commitments, scans it for known tooling/keyword signals, and emits SP-shaped
typed-record stubs the authoring agent then refines.

The constitution Article number is configurable (`--article`, default 5) and
the heading is matched flexibly — the canonical DekSpec constitution puts
Development Workflow at Article 5, but a consumer's may differ.

Graceful degradation:
  * No constitution file            -> empty result + note, exit 0.
  * No matching Article             -> empty result + note, exit 0.
  * Article present, no security
    tooling mentioned                -> empty arrays + note, exit 0.

The stubs are intentionally minimal — the script extracts *signals*, not a
finished typed record. Each detected tool becomes a stub the agent fills with
the exact pinned name, scope, and OWASP mapping.

Stdlib-only. Importable + argparse CLI.

Runnable:   python compile_article5.py [--constitution PATH] [--article N]
Importable: from compile_article5 import compile_security_stubs
Exit codes: 0 always on a clean scan; 1 on an unexpected read error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Keyword signals -> SP typed-record array. Lower-cased substring match against
# the Article body. Tool names are illustrative; the agent pins the exact value.
_SAST_SIGNALS = ["sast", "bandit", "semgrep", "static analysis", "codeql"]
_DAST_SIGNALS = ["dast", "owasp zap", "dynamic analysis", "penetration test"]
_SECRET_SIGNALS = [
    "secret store",
    "secrets manager",
    "vault",
    "secret scanning",
    "gitleaks",
    "detect-secrets",
]
_SUPPLY_CHAIN_SIGNALS = [
    "supply chain",
    "supply-chain",
    "dependabot",
    "sbom",
    "pip-audit",
    "trivy",
    "allowed source",
    "dependency scanning",
]


def _find_article(text: str, article: int) -> str:
    """Return the body of `## Article N: ...`, or '' if not present.

    Falls back to any heading containing 'Development Workflow' when the
    numbered Article cannot be found.
    """
    pat = re.compile(
        rf"^#+[ \t]+Article[ \t]+{article}\b.*$", re.MULTILINE
    )
    m = pat.search(text)
    if not m:
        m = re.search(
            r"^#+[ \t]+.*Development Workflow.*$", text, re.MULTILINE
        )
    if not m:
        return ""
    body = text[m.end():]
    nxt = re.search(r"^#+[ \t]+\S", body, re.MULTILINE)
    return body[: nxt.start()] if nxt else body


def _detect(body_lc: str, signals: list[str]) -> list[str]:
    """Return the signal keywords present in the lower-cased Article body."""
    return [sig for sig in signals if sig in body_lc]


def compile_security_stubs(
    constitution_path: Path, article: int = 5
) -> dict[str, object]:
    """Parse the constitution Article; return SP-shaped typed-record stubs."""
    if not constitution_path.is_file():
        return {
            "constitution_found": False,
            "article": article,
            "note": (
                f"No constitution at {constitution_path}; "
                "SP typed-record arrays start empty."
            ),
            "stubs": {
                "sast_tools": [],
                "dast_tools": [],
                "secret_stores": [],
                "supply_chain_sources": [],
            },
        }

    text = constitution_path.read_text(encoding="utf-8")
    body = _find_article(text, article)
    if not body.strip():
        return {
            "constitution_found": True,
            "article": article,
            "note": (
                f"Constitution has no Article {article} / Development "
                "Workflow section; SP typed-record arrays start empty."
            ),
            "stubs": {
                "sast_tools": [],
                "dast_tools": [],
                "secret_stores": [],
                "supply_chain_sources": [],
            },
        }

    body_lc = body.lower()
    sast = _detect(body_lc, _SAST_SIGNALS)
    dast = _detect(body_lc, _DAST_SIGNALS)
    secrets = _detect(body_lc, _SECRET_SIGNALS)
    supply = _detect(body_lc, _SUPPLY_CHAIN_SIGNALS)

    def _stub_list(signals: list[str], kind: str) -> list[dict[str, str]]:
        return [
            {
                "name": "<engineer-fills-here>",
                "detected_signal": sig,
                "kind": kind,
            }
            for sig in signals
        ]

    stubs = {
        "sast_tools": _stub_list(sast, "sast"),
        "dast_tools": _stub_list(dast, "dast"),
        "secret_stores": _stub_list(secrets, "secret_store"),
        "supply_chain_sources": _stub_list(supply, "supply_chain_source"),
    }
    total = sum(len(v) for v in stubs.values())
    note = (
        f"Article {article} mentions no SAST/DAST/secret/supply-chain "
        "tooling; SP typed-record arrays start empty (honest-empty)."
        if total == 0
        else (
            f"Article {article} surfaced {total} security signal(s); "
            "each stub needs the engineer to pin the exact tool + scope."
        )
    )
    return {
        "constitution_found": True,
        "article": article,
        "note": note,
        "stubs": stubs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="compile_article5.py",
        description="Compile Constitution Article 5 into SP typed-record stubs.",
    )
    parser.add_argument(
        "--constitution",
        default="dekspec/constitution.md",
        help="Path to the constitution (default: dekspec/constitution.md).",
    )
    parser.add_argument(
        "--article",
        type=int,
        default=5,
        help="Article number holding security commitments (default: 5).",
    )
    args = parser.parse_args(argv)

    try:
        result = compile_security_stubs(
            Path(args.constitution), args.article
        )
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
