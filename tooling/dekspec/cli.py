"""DekSpec CLI entry point.

v0.2.0 commands:
  dekspec compile <ic-path> [--emit ir|contract-test|ci-gate] [--output PATH]
                            [--treat-as-locked]
  dekspec runs ls [-n N] [--at REPO_PATH]
  dekspec runs show <run-id|latest|prefix> [--at REPO_PATH]
  dekspec --version
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    pass

from . import __version__
from . import platform_install
from .harness import HarnessUnsupported
from .constraint_compiler import (
    ADRParseError,
    AEParseError,
    CSParseError,
    GlossaryParseError,
    IBParseError,
    ICParseError,
    IntentParseError,
    MissionParseError,
    SPParseError,
    VisionParseError,
    WSParseError,
    agents_md,
    ci_gate,
    contract_test,
    parse,
    parse_adr,
    parse_ae,
    parse_constitution,
    parse_context_spec,
    parse_glossary,
    parse_ib,
    parse_intent,
    parse_mission,
    parse_security_profile,
    parse_vision,
    parse_ws,
    resolve_aes,
)
from .constraint_compiler import ConstitutionParseError
from .constraint_compiler.persistence import (
    open_run,
    repo_fingerprint,
    repo_state_dir,
)
import re as _re

_IC_PREFIX = _re.compile(r"^IC-\d{3,}-")
_AE_PREFIX = _re.compile(r"^AE-\d{3,}-")
_WS_PREFIX = _re.compile(r"^WS-\d{3,}-")
_ADR_PREFIX = _re.compile(r"^ADR-\d{3,}-")
_IB_PREFIX = _re.compile(r"^IB-\d{3,}-")
_INT_PREFIX = _re.compile(r"^INT-\d{3,}-")
_MSN_PREFIX = _re.compile(r"^MSN-\d{3,}-")
_SP_PREFIX = _re.compile(r"^SP-\d{3,}-")


class SubParserWrapper:
    def __init__(self, real_sub, override_name=None, suppress=False):
        self.real_sub = real_sub
        self.override_name = override_name
        self.suppress = suppress

    def add_parser(self, name, *args, **kwargs):
        actual_name = self.override_name if self.override_name else name
        p = self.real_sub.add_parser(actual_name, *args, **kwargs)
        if self.suppress:
            if hasattr(self.real_sub, "_choices_actions") and self.real_sub._choices_actions:
                self.real_sub._choices_actions.pop()
        return p


def _get_subparsers_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


LEGACY_COMMANDS = {
    "compile": ("check", "compile"),
    "runs": ("exec", "runs"),
    "aggregate": ("check", "aggregate"),
    "emit": ("check", "emit"),
    "graph": ("dev", "graph"),
    "relink": ("audit", "relink"),
    "init": ("repo", "init"),
    "validate": ("check", "validate"),
    "doctor": ("audit", "doctor"),
    "session": ("exec", "session"),
    "id": ("check", "allocate-ids"),
    "config": ("exec", "config"),
    "ingest": ("dev", "ingest"),
    "archeology": ("dev", "archeology"),
    "lint-ib": ("check", "lint-ib"),
}

# ADR-042 inversion — the flat verb is now the canonical form; the nested
# `<group> <sub>` form is the one-release deprecated alias. This reverse map
# (`group -> {sub -> flat}`) lets `main()` warn on a nested invocation and
# point at the flat successor. Built from LEGACY_COMMANDS plus the flat public
# verbs added directly (not routed through LEGACY_COMMANDS): `lock-ready`,
# `sync`, `regen-indexes`.
_NESTED_TO_FLAT: dict[str, dict[str, str]] = {}
for _flat, (_grp, _cmd) in LEGACY_COMMANDS.items():
    _NESTED_TO_FLAT.setdefault(_grp, {})[_cmd] = _flat
_NESTED_TO_FLAT.setdefault("audit", {})["lock-ready"] = "lock-ready"
_NESTED_TO_FLAT.setdefault("library", {})["sync"] = "sync"
_NESTED_TO_FLAT.setdefault("library", {})["regen-indexes"] = "regen-indexes"


def build_parser() -> tuple[argparse.ArgumentParser, dict[str, argparse.ArgumentParser]]:
    """Construct the full dekspec argparse tree.

    Extracted from ``main`` so tooling and tests can introspect the CLI surface
    (e.g. dry-``parse_args`` a doc-snippet invocation to catch wrong arg forms)
    without dispatching. Returns the top parser plus the group→subparser map
    ``main`` uses for its no-subcommand help fallback.
    """
    parser = argparse.ArgumentParser(
        prog="dekspec",
        description="DekSpec — shared library and Constraint Compiler for Dektora projects.",
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"dekspec {__version__}"
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # Top-level group subparsers
    
    # 1. check
    p_check = sub.add_parser("check", help="Single-file parsing, compilation, and validation.")
    sub_check = p_check.add_subparsers(dest="check_command", metavar="<check-command>")
    _add_validate_subparser(sub_check)
    _add_compile_subparser(sub_check)
    _add_emit_subparser(sub_check)
    _add_aggregate_subparser(sub_check)
    _add_id_subparser(SubParserWrapper(sub_check, override_name="allocate-ids"))
    _add_lint_ib_subparser(sub_check)

    # 2. audit
    _add_audit_subparser(sub)
    p_audit = sub.choices["audit"]
    # Update p_audit description/help for unified nesting description
    p_audit.description = "Spec-graph validation, compliance, and linkage audits."
    p_audit.help = "Spec-graph validation, compliance, and linkage audits."
    sub_audit = _get_subparsers_action(p_audit)
    _add_doctor_subparser(sub_audit)
    _add_relink_subparser(sub_audit)
    # ADR-042 — bare `dekspec audit` is the consolidated composite verb:
    # fix-to-convergence by default, `--check-only` reports without mutating.
    # (The `audit <sub>` forms above remain deprecated nested aliases.)
    p_audit.add_argument("--at", help="Path to anchor the repo (default: current working directory).")
    p_audit.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Path to the DekSpec content tree relative to repo root (default: dekspec).",
    )
    p_audit.add_argument("--json", action="store_true", help="Emit the rolled-up summary as JSON.")
    p_audit.add_argument("--profile", default=None, help="Audit-rule profile to enforce.")
    p_audit.add_argument(
        "--check-only",
        action="store_true",
        help="Report without applying any fix (the CI-safe path; default is fix-to-convergence).",
    )
    p_audit.set_defaults(func=cmd_audit)

    # 3. exec
    p_exec = sub.add_parser("exec", help="Session tracking + per-repo config.")
    sub_exec = p_exec.add_subparsers(dest="exec_command", metavar="<exec-command>")
    _add_session_subparser(sub_exec)
    _add_runs_subparser(sub_exec)
    _add_config_subparser(sub_exec)

    # 4. library — the canonical home for consumer-side dekspec-content
    # operations (INT-136 / ADR-033). It absorbs the former `repo` verbs
    # (init / new-provisional / author-target / regen-indexes / cow-stage)
    # and keeps the reconcile-only `sync` (INT-135 / ADR-032), dissolving the
    # transient `library sync` / `repo *` split INT-135 introduced.
    p_library = sub.add_parser(
        "library",
        help="Consumer-side dekspec-content operations (sync, init, provisional/index utilities).",
    )
    sub_library = p_library.add_subparsers(
        dest="library_command", metavar="<library-command>"
    )
    _add_sync_subparser(sub_library)
    _add_library_artifact_subparsers(sub_library)
    p_library.set_defaults(func=lambda _args: (p_library.print_help() or 0))

    # 4b. repo — DEPRECATION-ALIAS namespace (INT-136 / ADR-033). Every
    # `dekspec repo <verb>` parses identically to its `library` counterpart
    # but, on dispatch, prints a one-line `[DEPRECATED]` notice and forwards
    # to the SAME handler (no change to logic, flags, or stdout). Removal of
    # this alias namespace follows the next minor release. The retired
    # `promote-provisional` stub stays as-is. The `upgrade` acquisition verb
    # was removed (ds-d063): ADR-032 deprecated it as a one-release alias and
    # ADR-034 killed the in-CLI acquisition model — acquire out-of-band
    # (`pipx`/pip-from-git) and reconcile via `dekspec library sync`.
    p_repo = sub.add_parser(
        "repo",
        help="DEPRECATED — alias for `dekspec library <verb>` (one release).",
    )
    sub_repo = p_repo.add_subparsers(dest="repo_command", metavar="<repo-command>")
    _add_init_subparser(sub_repo)
    _add_promote_provisional_retired_subparser(sub_repo)
    _add_new_provisional_subparser(sub_repo)
    _add_author_target_subparser(sub_repo)
    _add_regen_indexes_subparser(sub_repo)
    _add_cow_stage_subparser(sub_repo)
    # Wrap each verb's handler to emit the deprecation notice then delegate to
    # the same handler. `promote-provisional` is skipped — it is a retired
    # stub that already returns a pointer to the hand-promote workflow.
    _wrap_repo_aliases_with_deprecation(sub_repo, skip={"promote-provisional"})

    # Top-level migrate pipeline (INT-098): one verb that runs verify →
    # migrate-ir → migrate-artifacts in sequence. The underlying three
    # subverbs are no longer registered — `dekspec migrate` is the only
    # blessed entry point for the upgrade-pipeline operations.
    _add_dekspec_migrate_pipeline_subparser(sub)

    # 5. dev
    p_dev = sub.add_parser("dev", help="Diagnostics, brownfield classification, and archaeology.")
    sub_dev = p_dev.add_subparsers(dest="dev_command", metavar="<dev-command>")
    _add_graph_subparser(sub_dev)
    _add_ingest_subparser(sub_dev)
    _add_archeology_subparser(sub_dev)

    # 6. resource — wheel-vendored asset resolver (INT-097)
    _add_resource_subparser(sub)

    # 7. install — per-host skill/command/hook emitter (ds-iz3d). Repackages
    # the single plugins/dekspec source into the file tree a given harness
    # host (claude/codex/antigravity/cursor/copilot/pi) expects. Build-time only:
    # writes files, never executes (ADR-024).
    _add_install_subparser(sub)

    # 8. slices — LLM-free structural slice-discovery (ds-mrsu). Thin adapter
    # over constraint_compiler.slice_discovery; all graph/clustering logic
    # lives in the engine (AE-005).
    _add_slices_subparser(sub)

    # ADR-042 — internal flat verbs: reachable but hidden from top-level help
    # (skill/hook/pipeline plumbing, not part of the advertised surface).
    _add_compile_subparser(SubParserWrapper(sub, suppress=True))
    _add_runs_subparser(SubParserWrapper(sub, suppress=True))
    _add_aggregate_subparser(SubParserWrapper(sub, suppress=True))
    _add_emit_subparser(SubParserWrapper(sub, suppress=True))
    _add_graph_subparser(SubParserWrapper(sub, suppress=True))
    _add_relink_subparser(SubParserWrapper(sub, suppress=True))
    _add_validate_subparser(SubParserWrapper(sub, suppress=True))
    _add_doctor_subparser(SubParserWrapper(sub, suppress=True))
    _add_session_subparser(SubParserWrapper(sub, suppress=True))
    _add_id_subparser(SubParserWrapper(sub, suppress=True))
    _add_config_subparser(SubParserWrapper(sub, suppress=True))
    _add_archeology_subparser(SubParserWrapper(sub, suppress=True))
    _add_lint_ib_subparser(SubParserWrapper(sub, suppress=True))
    # ADR-042 — the PUBLIC flat verbs, SHOWN in top-level help. Together with
    # the already-top-level audit / migrate / install, these are the nine
    # public verbs of the flattened surface (init, ingest, sync,
    # regen-indexes, lock-ready, find-spec-gaps).
    _add_init_subparser(sub)
    _add_ingest_subparser(sub)
    _add_sync_subparser(sub)
    _add_regen_indexes_subparser(sub)
    _add_lock_ready_flat_subparser(sub)
    _add_find_spec_gaps_subparser(sub)

    group_parsers = {
        "check": p_check,
        "audit": p_audit,
        "exec": p_exec,
        "repo": p_repo,
        "library": p_library,
        "dev": p_dev,
    }
    # ADR-042 — hide the deprecated nested group namespaces from top-level help.
    # They stay fully dispatchable (each nested `<group> <sub>` still works and
    # prints its deprecation notice), but the advertised surface is the flat
    # verbs. `audit` is NOT hidden — it is now a public verb (with the group's
    # subcommands as its deprecated aliases).
    _top = _get_subparsers_action(parser)
    if _top is not None and getattr(_top, "_choices_actions", None):
        _deprecated_groups = {"check", "exec", "repo", "library", "dev", "resource"}
        _top._choices_actions = [
            a for a in _top._choices_actions if a.dest not in _deprecated_groups
        ]
    return parser, group_parsers


def _ensure_utf8_output() -> None:
    """Make CLI output robust on Windows consoles (issue: cp1252 crash).

    The status glyphs the CLI prints (``✓ ✗ → ≥ ~`` …) raise
    ``UnicodeEncodeError: 'charmap' codec can't encode`` on a legacy cp1252
    Windows console. Reconfigure stdout/stderr to UTF-8 (equivalent to the
    ``PYTHONUTF8=1`` workaround) with ``errors="replace"`` as a
    belt-and-suspenders fallback so output degrades to ``?`` rather than
    crashing on any stream that can't be switched. No-op where the stream
    exposes no ``reconfigure`` (already-wrapped / redirected / non-TTY).
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - stream can't switch
            pass


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_output()
    parser, group_parsers = build_parser()

    check_args = argv if argv is not None else sys.argv[1:]
    # ADR-042: flat verbs are canonical (silent); the nested `<group> <sub>`
    # forms are one-release deprecated aliases that warn, pointing to the flat
    # successor. (The reverse: `dekspec doctor` is now silent; `dekspec audit
    # doctor` warns.)
    if len(check_args) >= 2 and check_args[0] in _NESTED_TO_FLAT:
        flat = _NESTED_TO_FLAT[check_args[0]].get(check_args[1])
        if flat:
            print(
                f"[DEPRECATED] 'dekspec {check_args[0]} {check_args[1]}' is deprecated. "
                f"Please use 'dekspec {flat}' instead.",
                file=sys.stderr,
            )

    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        if args.command in group_parsers:
            group_parsers[args.command].print_help()
        else:
            _sub = _get_subparsers_action(parser)
            if _sub is not None and args.command in _sub.choices:
                _sub.choices[args.command].print_help()
            else:
                parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


# --------------------------------------------------------------------------- #
# slices — structural slice discovery (ds-mrsu)
# --------------------------------------------------------------------------- #


def _add_slices_subparser(sub: argparse._SubParsersAction) -> None:
    """Register the `dekspec slices` verb (ds-mrsu).

    Thin adapter (AE-005): all import-graph / clustering logic lives in
    ``constraint_compiler.slice_discovery``. This registration only declares
    the CLI surface (`path` + `--json`) and wires the handler.
    """
    p = sub.add_parser(
        "slices",
        help="Discover structural slices of a Python repo (LLM-free).",
        description=(
            "Walk a target repo's Python package tree, build an intra-repo "
            "import graph via the stdlib ast module, cluster it by structural "
            "modularity, and write the RAW slice manifest to "
            "<repo>/.dekspec/slices.json. Pure static analysis — no LLM, no "
            "network."
        ),
    )
    p.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Target repo to slice (default: current directory).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit the slice array as JSON instead of a human summary.",
    )
    p.set_defaults(func=cmd_slices)


def cmd_slices(args: argparse.Namespace) -> int:
    """Thin adapter for `dekspec slices` (AE-005) — formats output only.

    All graph/cluster logic lives in the engine; this function imports it,
    invokes it, and renders the result.
    """
    from .constraint_compiler.slice_discovery import discover_slices

    repo = Path(args.path).resolve()
    slices = discover_slices(repo)

    if args.json:
        print(json.dumps(slices, indent=2, default=str))
        return 0

    if not slices:
        print(f"No slices discovered under {repo} (no importable Python modules).")
        return 0

    print(f"Discovered {len(slices)} slice(s) under {repo}:")
    for i, s in enumerate(slices, 1):
        members = s["member_modules"]
        print(f"  [{i}] {len(members)} module(s): {', '.join(members)}")
    return 0


# --------------------------------------------------------------------------- #
# library / repo namespace registration (INT-136 / ADR-033)
# --------------------------------------------------------------------------- #


def _add_library_artifact_subparsers(sub: argparse._SubParsersAction) -> None:
    """Register the former `repo` artifact/setup verbs under the canonical
    `library` group (INT-136 / ADR-033).

    Reuses the exact same arg-adders + handler funcs as the `repo` alias
    namespace — no handler logic is duplicated or altered. `library sync`
    (INT-135) is registered separately by the caller. There is no `upgrade`
    verb: the in-CLI acquisition model was removed (ADR-032 / ADR-034,
    ds-d063); reconcile via `library sync` after acquiring out-of-band.
    """
    _add_init_subparser(sub)
    _add_new_provisional_subparser(sub)
    _add_author_target_subparser(sub)
    _add_regen_indexes_subparser(sub)
    _add_cow_stage_subparser(sub)


def _add_lock_ready_flat_subparser(sub: argparse._SubParsersAction) -> None:
    """ADR-042 flat `lock-ready` — the gated ACCEPTED→LOCKED sweep, kept a
    distinct public verb (never folded into `audit`'s fix default). Dispatches
    to the same handler as `audit lock-ready`."""
    p = sub.add_parser(
        "lock-ready",
        help="Transition lock-ready ACCEPTED artifacts to LOCKED (gated action).",
    )
    p.add_argument("--at", help="Path to anchor the repo (default: current working directory).")
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Path to the DekSpec content tree relative to repo root (default: dekspec).",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Actually transition the lock-ready artifacts to LOCKED.",
    )
    p.add_argument(
        "--engineer",
        default="dekspec-audit-lock-ready",
        help="The engineer/agent identifier for the Amendment Log row.",
    )
    p.set_defaults(func=cmd_audit_lock_ready)


def _add_find_spec_gaps_subparser(sub: argparse._SubParsersAction) -> None:
    """ADR-042 flat `find-spec-gaps` — the flat rename of `dev archeology
    coverage`. Reports source files no LOCKED Intent claims; feeds the
    archeology recovery workflow."""
    p = sub.add_parser(
        "find-spec-gaps",
        help="Report source files no LOCKED Intent claims (spec-coverage gaps).",
    )
    p.add_argument("--at", default=".", help="Path to the repo to scan (default: current working directory).")
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit the gap report as a JSON array instead of a Markdown table.",
    )
    p.set_defaults(func=cmd_archeology_coverage)


def _make_deprecation_alias(verb: str, handler):
    """Wrap a verb handler so it prints a one-line `[DEPRECATED]` notice
    pointing at the `library` canonical form, then delegates to the SAME
    handler — identical logic, flags, exit code, and stdout.

    Per ADR-033: `repo <verb>` is a one-release deprecation alias.
    """

    def _aliased(args: argparse.Namespace) -> int:
        print(
            f"[DEPRECATED] 'dekspec repo {verb}' → use 'dekspec library {verb}'",
            file=sys.stderr,
        )
        return handler(args)

    return _aliased


def _wrap_repo_aliases_with_deprecation(
    sub_repo: argparse._SubParsersAction, *, skip: set[str]
) -> None:
    """Re-point every `repo <verb>` subparser's `func` default at a thin
    deprecation-alias wrapper around its existing handler (INT-136 / ADR-033).

    The verbs were registered by the shared `_add_*_subparser` funcs, so the
    handler logic is the canonical one — this only prepends the stderr notice.
    `skip` names verbs that must keep their own dispatch behavior
    (`promote-provisional` is a retired stub).
    """
    for verb, parser in sub_repo.choices.items():
        if verb in skip:
            continue
        original = parser.get_default("func")
        if original is None:
            continue
        parser.set_defaults(func=_make_deprecation_alias(verb, original))


# --------------------------------------------------------------------------- #
# compile
# --------------------------------------------------------------------------- #


def _add_compile_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "compile",
        help="Parse a DekSpec artifact and (optionally) emit an enforcement output.",
        description=(
            "Parse a DekSpec artifact (currently: Interface Contracts only). "
            "Without --emit, just parses + persists. With --emit, writes the chosen "
            "emitter's output to stdout (or to --output PATH)."
        ),
    )
    p.add_argument("path", help="Path to the source artifact (e.g., IC markdown).")
    p.add_argument(
        "--emit",
        choices=["ir", "contract-test", "ci-gate", "agents-md"],
        help="What to emit. Default: parse + persist only.",
    )
    p.add_argument(
        "--output", help="Write emitter output to PATH instead of stdout."
    )
    p.add_argument(
        "--treat-as-locked",
        action="store_true",
        help=(
            "Bypass the LOCKED-status enforcement. v0.1 PoC scaffold flag — "
            "real consumers must lock the artifact through the normal workflow."
        ),
    )
    p.add_argument(
        "--affected-paths",
        metavar="PATH1,PATH2,...",
        help=(
            "Comma-separated list of paths that override IR.affected_paths. "
            "v0.1 PoC scaffold for ICs that don't yet declare affected_paths — "
            "supplements / overrides --resolve-aes."
        ),
    )
    p.add_argument(
        "--resolve-aes",
        action="store_true",
        help=(
            "For ICs only: walk the conventional architecture-elements/ dir, "
            "parse each Provider/Consumer AE referenced via parties[].ae_id, "
            "and union their implements_globs into IC.affected_paths. "
            "Replaces v0.1's --affected-paths CLI scaffold once AEs declare "
            "their implements_globs in markdown."
        ),
    )
    p.set_defaults(func=cmd_compile)


def cmd_compile(args: argparse.Namespace) -> int:
    src = Path(args.path).resolve()
    if not src.exists():
        print(f"Error: source not found: {src}", file=sys.stderr)
        return 2

    command_str = _shell_quote_args(
        ["dekspec", "compile", str(src)]
        + (["--emit", args.emit] if args.emit else [])
        + (["--output", args.output] if args.output else [])
        + (["--treat-as-locked"] if args.treat_as_locked else [])
    )

    artifact_kind = _detect_artifact_kind(src.name)
    if artifact_kind is None:
        print(
            f"Error: cannot detect artifact kind from filename '{src.name}'. "
            f"Expected IC-NNN-*.md, AE-NNN-*.md, WS-NNN-*.md, ADR-NNN-*.md, "
            f"IB-NNN-*.md, INT-NNN-*.md, MSN-NNN-*.md, SP-NNN-*.md, "
            f"system-vision.md, domain-glossary.md, or constitution.md.",
            file=sys.stderr,
        )
        return 2

    with open_run(start=src, trigger="manual-compile", command=command_str) as run:
        try:
            if artifact_kind == "ic":
                ir = parse(src)
            elif artifact_kind == "ae":
                ir = parse_ae(src)
            elif artifact_kind == "ws":
                ir = parse_ws(src)
            elif artifact_kind == "adr":
                ir = parse_adr(src)
            elif artifact_kind == "ib":
                ir = parse_ib(src)
            elif artifact_kind == "intent":
                ir = parse_intent(src)
            elif artifact_kind == "mission":
                ir = parse_mission(src)
            elif artifact_kind == "sp":
                ir = parse_security_profile(src)
            elif artifact_kind == "vision":
                ir = parse_vision(src)
            elif artifact_kind == "constitution":
                ir = parse_constitution(src)
            else:  # glossary
                ir = parse_glossary(src)
        except (ICParseError, AEParseError, WSParseError, ADRParseError,
                IBParseError, IntentParseError, MissionParseError,
                SPParseError,
                VisionParseError, GlossaryParseError,
                ConstitutionParseError) as e:
            print(f"Parse error: {e}", file=sys.stderr)
            run.run.exit_code = 4
            run.run.errors += 1
            return 4

        # AE resolution (ICs and WSes; AEs and ADRs don't drive CI gate scoping
        # via affected_paths — ADRs feed AGENTS.md + lint rules, not per-file gates)
        if artifact_kind in {"ic", "ws"} and args.resolve_aes:
            resolve_aes(ir)
            run.event(
                kind="resolve_aes",
                affected_paths_after=ir.get("affected_paths", []),
            )

        # IR overrides — supplement / merge with --resolve-aes output
        if args.affected_paths:
            override = [p.strip() for p in args.affected_paths.split(",") if p.strip()]
            existing = ir.get("affected_paths", [])
            ir["affected_paths"] = list(dict.fromkeys(existing + override))
            run.event(
                kind="ir_override",
                field="affected_paths",
                value=ir["affected_paths"],
                source="--affected-paths CLI flag (merged with --resolve-aes output if any)",
            )

        run.record_artifact(ir)

        # Status enforcement (LOCKED-only by default; --treat-as-locked bypasses)
        status = ir.get("status")
        if status != "LOCKED" and not args.treat_as_locked:
            print(
                f"Error: {ir['id']} status is {status}, not LOCKED. "
                f"Pass --treat-as-locked to bypass (v0.1 PoC scaffold flag).",
                file=sys.stderr,
            )
            run.run.exit_code = 3
            run.run.errors += 1
            return 3

        if not args.emit:
            warning_count = len(ir.get("parse_warnings", []))
            print(
                f"Parsed {ir['id']} ({status}) — {warning_count} parse warning(s). "
                f"Run dir: {run.run_dir}"
            )
            return 0

        # contract-test / ci-gate are IC-only emitters; agents-md is AE/ADR/WS/IB/INT/MSN-only.
        # Singletons (vision, glossary) currently only support --emit ir.
        if artifact_kind != "ic" and args.emit in {"contract-test", "ci-gate"}:
            print(
                f"Error: --emit {args.emit} is only valid for ICs. "
                f"{artifact_kind.upper()} supports --emit ir"
                + (" or --emit agents-md."
                   if artifact_kind in {"ae", "ws", "adr", "ib", "intent", "mission"}
                   else "."),
                file=sys.stderr,
            )
            run.run.exit_code = 2
            run.run.errors += 1
            return 2
        if artifact_kind in {"ic", "vision", "glossary"} and args.emit == "agents-md":
            print(
                f"Error: --emit agents-md is only valid for AE/ADR/WS/IB/INT/MSN artifacts. "
                f"{artifact_kind.upper()}s currently do not have a per-artifact "
                f"agents-md emitter (singletons appear in the aggregator output).",
                file=sys.stderr,
            )
            run.run.exit_code = 2
            run.run.errors += 1
            return 2

        # Run the chosen emitter.
        if args.emit == "ir":
            output = json.dumps(ir, indent=2, default=str)
            emitter = "ir"
        elif args.emit == "contract-test":
            output = contract_test.emit(ir)
            emitter = "contract_test"
        elif args.emit == "ci-gate":
            output = ci_gate.emit(ir)
            emitter = "ci_gate"
        elif args.emit == "agents-md":
            output = agents_md.emit(ir)
            emitter = "agents_md"
        else:  # pragma: no cover — argparse choices guard this
            print(f"Unknown --emit value: {args.emit}", file=sys.stderr)
            return 2

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output, encoding="utf-8")
            run.record_emission(
                emitter=emitter,
                artifact_id=ir["id"],
                output_path=str(out_path),
                output_size=len(output),
            )
            print(f"Wrote {emitter} -> {out_path} ({len(output)} bytes)")
        else:
            run.record_emission(
                emitter=emitter,
                artifact_id=ir["id"],
                output_path=None,
                output_size=len(output),
            )
            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
        return 0


# --------------------------------------------------------------------------- #
# runs
# --------------------------------------------------------------------------- #


def _add_runs_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "runs",
        help="Inspect compile-run history persisted under $XDG_DATA_HOME/dekspec/.",
    )
    runs_sub = p.add_subparsers(dest="runs_command", metavar="<runs-command>")

    p_ls = runs_sub.add_parser("ls", help="List recent runs.")
    p_ls.add_argument(
        "-n", "--limit", type=int, default=20, help="Max runs to show (default: 20)."
    )
    p_ls.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_ls.add_argument(
        "--since", help="Only show runs at or after this ISO timestamp (e.g., 2026-05-01)."
    )
    p_ls.add_argument(
        "--until", help="Only show runs before this ISO timestamp."
    )
    p_ls.add_argument(
        "--artifact", help="Only show runs that touched this artifact id (e.g., AE-014)."
    )
    p_ls.add_argument(
        "--exit-code", type=int, help="Only show runs with this exit code."
    )
    p_ls.add_argument(
        "--milestone", action="store_true", help="Only show milestone runs."
    )
    p_ls.add_argument(
        "--min-warnings", type=int, help="Only show runs with at least N warnings."
    )
    p_ls.add_argument(
        "--json", action="store_true",
        help="Emit results as JSON instead of a formatted table.",
    )
    p_ls.set_defaults(func=cmd_runs_ls)

    p_reindex = runs_sub.add_parser(
        "reindex",
        help="Rebuild the SQLite index from on-disk manifest.json files.",
    )
    p_reindex.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_reindex.set_defaults(func=cmd_runs_reindex)

    p_gc = runs_sub.add_parser(
        "gc",
        help="Garbage-collect old runs (preserving milestone runs).",
    )
    p_gc.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_gc.add_argument(
        "--keep",
        type=int,
        default=200,
        help="Number of most recent non-milestone runs to keep (default: 200).",
    )
    p_gc.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be deleted without removing anything.",
    )
    p_gc.set_defaults(func=cmd_runs_gc)

    p_show = runs_sub.add_parser("show", help="Show a run's manifest and IR list.")
    p_show.add_argument(
        "run_id",
        help='Run ID, run-dir-name prefix, or "latest".',
    )
    p_show.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_show.add_argument(
        "--json", action="store_true",
        help="Emit the run as a single JSON document (manifest + IR refs + event count).",
    )
    p_show.set_defaults(func=cmd_runs_show)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


def cmd_runs_ls(args: argparse.Namespace) -> int:
    from .constraint_compiler.persistence_index import open_index, query_runs

    start = Path(args.at).resolve() if args.at else Path.cwd()
    state_dir = repo_state_dir(start)
    runs_dir = state_dir / "runs"
    if not runs_dir.exists():
        print(
            f"No runs yet for repo {repo_fingerprint(start)} (looked under {runs_dir})",
            file=sys.stderr,
        )
        return 0

    conn = open_index(state_dir)
    try:
        rows = query_runs(
            conn,
            since=args.since,
            until=args.until,
            artifact_id=args.artifact,
            exit_code=args.exit_code,
            milestone=True if args.milestone else None,
            min_warnings=args.min_warnings,
            limit=args.limit,
        )
    finally:
        conn.close()

    if args.json:
        print(json.dumps({
            "repo_root": str(start),
            "runs_dir": str(runs_dir),
            "row_count": len(rows),
            "rows": rows,
        }, indent=2, default=str))
        return 0

    if not rows:
        print(
            f"No runs match the filter at {runs_dir}. "
            f"(If you have on-disk runs but the index is empty, run `dekspec runs reindex`.)"
        )
        return 0

    print(f"Runs at {runs_dir} (showing {len(rows)} most recent matching filters):")
    print(f"  {'ms':>2} {'name':<48} {'A':>2} {'E':>2} {'W':>3} {'X':>1}")
    for row in rows:
        marker = " *" if row["milestone"] else "  "
        print(
            f"  {marker} {row['run_dir_name']:<48} "
            f"{row['artifact_count']:>2} "
            f"{row['emission_count']:>2} "
            f"{row['warnings']:>3} "
            f"{row['exit_code']:>1}"
        )
    print("\n  ms = milestone | A = artifacts | E = emissions | W = warnings | X = exit code")
    return 0


def cmd_runs_gc(args: argparse.Namespace) -> int:
    """Garbage-collect old runs (preserving milestone runs). Mirrors
    `_prune_runs` from persistence.py but exposed as an explicit CLI
    so users can gc without running a compile."""
    import shutil as _shutil
    from .constraint_compiler.persistence import _is_milestone
    from .constraint_compiler.persistence_index import (
        INDEX_FILENAME, open_index,
    )

    start = Path(args.at).resolve() if args.at else Path.cwd()
    state_dir = repo_state_dir(start)
    runs_dir = state_dir / "runs"
    if not runs_dir.exists():
        print(f"No runs dir at {runs_dir} — nothing to gc.")
        return 0

    all_runs = sorted(
        [d for d in runs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    candidates = all_runs[args.keep:]
    preserved: list[Path] = []
    to_delete: list[Path] = []
    for run_dir in candidates:
        if _is_milestone(run_dir):
            preserved.append(run_dir)
        else:
            to_delete.append(run_dir)

    if args.dry_run:
        print(f"DRY-RUN. Would delete {len(to_delete)} run(s); "
              f"preserve {len(preserved)} milestone(s) older than --keep.")
        for d in to_delete[:10]:
            print(f"  - {d.name}")
        if len(to_delete) > 10:
            print(f"  ... ({len(to_delete) - 10} more)")
        return 0

    deleted = 0
    for d in to_delete:
        _shutil.rmtree(d, ignore_errors=True)
        deleted += 1
    # CASCADE on the foreign key cleans up artifacts + emissions rows.
    if (state_dir / INDEX_FILENAME).exists():
        conn = open_index(state_dir)
        try:
            for d in to_delete:
                conn.execute(
                    "DELETE FROM runs WHERE run_dir_name = ?", (d.name,),
                )
            conn.commit()
        finally:
            conn.close()
    print(
        f"Garbage-collected {deleted} run(s); preserved "
        f"{len(preserved)} milestone(s) and {min(len(all_runs), args.keep)} most-recent run(s)."
    )
    return 0


def cmd_runs_reindex(args: argparse.Namespace) -> int:
    from .constraint_compiler.persistence_index import reindex

    start = Path(args.at).resolve() if args.at else Path.cwd()
    state_dir = repo_state_dir(start)
    if not state_dir.exists():
        print(f"No state dir at {state_dir} — nothing to reindex.", file=sys.stderr)
        return 0
    result = reindex(state_dir)
    print(
        f"Reindexed {result['runs_indexed']} runs, "
        f"skipped {result['manifests_skipped']} (missing/unreadable manifest)."
    )
    return 0


def cmd_runs_show(args: argparse.Namespace) -> int:
    start = Path(args.at).resolve() if args.at else Path.cwd()
    state_dir = repo_state_dir(start)
    runs_dir = state_dir / "runs"

    if args.run_id == "latest":
        latest = state_dir / "latest"
        if not latest.exists():
            print("No latest run.", file=sys.stderr)
            return 1
        run_dir = latest.resolve()
    else:
        if not runs_dir.exists():
            print(f"No runs at {runs_dir}", file=sys.stderr)
            return 1
        candidates = [
            d for d in runs_dir.iterdir() if d.is_dir() and args.run_id in d.name
        ]
        if not candidates:
            print(f"No run matching: {args.run_id}", file=sys.stderr)
            return 1
        run_dir = sorted(candidates, key=lambda d: d.name, reverse=True)[0]

    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"No manifest in {run_dir}", file=sys.stderr)
        return 1

    if args.json:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        irs_dir = run_dir / "irs"
        ir_files = (
            [f.name for f in sorted(irs_dir.iterdir())]
            if irs_dir.exists() else []
        )
        events_path = run_dir / "events.jsonl"
        event_count = (
            sum(1 for _ in events_path.open("r", encoding="utf-8"))
            if events_path.exists() else 0
        )
        envelope = {
            "run_dir": str(run_dir),
            "manifest": manifest_data,
            "ir_files": ir_files,
            "event_count": event_count,
        }
        print(json.dumps(envelope, indent=2, default=str))
        return 0

    print(f"Run: {run_dir}")
    print(manifest_path.read_text(encoding="utf-8"))
    irs_dir = run_dir / "irs"
    if irs_dir.exists():
        ir_files = sorted(irs_dir.iterdir())
        if ir_files:
            print(f"\nIRs ({len(ir_files)}):")
            for ir_file in ir_files:
                print(f"  {ir_file.name}  ({ir_file.stat().st_size} bytes)")
    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        n_events = sum(1 for _ in events_path.open("r", encoding="utf-8"))
        print(f"\nEvents: {n_events} (in {events_path.name})")
    return 0


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _add_audit_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "audit",
        help="Run fidelity-audit checks (Python implementation).",
        description=(
            "v0.3.0 first cut: L-series cross-artifact linkage integrity. "
            "Other check families (T/D/E) live in the inlined fidelity body of /doctor Stage 2."
        ),
    )
    audit_sub = p.add_subparsers(dest="audit_command", metavar="<audit-command>")

    p_link = audit_sub.add_parser(
        "linkage",
        help="L-series linkage integrity (ADR/WS/IC -> AE refs resolve; backlinks).",
    )
    p_link.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_link.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Path to the DekSpec content tree relative to repo root (default: dekspec).",
    )
    p_link.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as JSON instead of formatted table.",
    )
    p_link.add_argument(
        "--min-severity",
        choices=["P0", "P1", "P2", "P3"],
        default=None,
        help=(
            "Filter findings to severity >= threshold (P0 strictest, P3 broadest). "
            "Default (unset) includes every tier (equivalent to P3)."
        ),
    )
    # Legacy flag retained for one release cycle with a deprecation warning.
    # Routed through `_translate_legacy_severity_flag` at runtime; aliases
    # to `--min-severity P<n>` per the ADR-013 alias map.
    p_link.add_argument(
        "--severity",
        choices=["critical", "important", "minor", "all"],
        default=None,
        help=(
            "[DEPRECATED] Use --min-severity instead. Legacy alias retained "
            "for one release cycle; emits a deprecation warning to stderr."
        ),
    )
    p_link.add_argument(
        "--fix",
        action="store_true",
        help=(
            "Compute mechanical fix proposals (currently L6 backlink only) "
            "and show before/after diffs. Default is dry-run; pass --apply "
            "to write the changes to disk."
        ),
    )
    p_link.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Used with --fix. Actually write the proposed changes to disk. "
            "Without --apply, --fix only previews the diffs."
        ),
    )
    p_link.add_argument(
        "--profile",
        default=None,
        help=(
            "Audit-rule profile to enforce (default: v1, the baseline set). "
            "Profiles live in tooling/dekspec/fidelity_audit/profiles/<name>.yaml. "
            "List available profiles with `python -c \"from dekspec.api import "
            "list_audit_profiles; print(list_audit_profiles())\"`. Future "
            "profiles (v2+) tighten via additive rules + parameter overrides."
        ),
    )
    p_link.add_argument(
        "--write-fixes",
        default=None,
        help="Write computed mechanical fixes directly to a JSON file during an audit/fix sweep.",
    )
    p_link.add_argument(
        "--read-fixes",
        default=None,
        help="Load and apply mechanical fixes directly from a JSON file, completely bypassing graph compilation and scanning.",
    )
    p_link.set_defaults(func=cmd_audit_linkage)

    p_lock = audit_sub.add_parser(
        "lock-ready",
        help="Check or apply transition to LOCKED for ACCEPTED artifacts that are lock-ready.",
    )
    p_lock.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_lock.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Path to the DekSpec content tree relative to repo root (default: dekspec).",
    )
    p_lock.add_argument(
        "--apply",
        action="store_true",
        help="Actually transition the lock-ready artifacts to LOCKED.",
    )
    p_lock.add_argument(
        "--engineer",
        default="dekspec-audit-lock-ready",
        help="The engineer/agent identifier for the Amendment Log row (default: dekspec-audit-lock-ready).",
    )
    p_lock.set_defaults(func=cmd_audit_lock_ready)

    # INT-126 / ds-99ko — failure-classes aggregator.
    p_fc = audit_sub.add_parser(
        "failure-classes",
        help=(
            "Read-only walk over the bead corpus, grouped by failure_class "
            "(or type, risk-tier), cross-referenced bead → Intent → revert SHA."
        ),
    )
    p_fc.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_fc.add_argument(
        "--window",
        type=int,
        default=90,
        help="Window in days for bead updates (default: 90).",
    )
    p_fc.add_argument(
        "--by",
        choices=["class", "type", "risk-tier"],
        default="class",
        help="Aggregation axis (default: class).",
    )
    p_fc.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Report format (default: md).",
    )
    p_fc.add_argument(
        "--detect-reverts",
        action="store_true",
        help="Best-effort `git log --grep` revert SHA lookup (slower).",
    )
    p_fc.set_defaults(func=cmd_audit_failure_classes)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


def _print_t_status_sweep(result: dict[str, Any], apply: bool) -> None:
    """Render the bounded T-STATUS auto-transition sweep result.

    The sweep transitions every sub-ACCEPTED T-STATUS gating finding to
    ACCEPTED (ADR-020 bounded auto-fix). Band-4/5 transitions are never
    proposed — they stay in the P3 advisory report.
    """
    proposed = result.get("proposed", 0)
    if proposed == 0:
        return
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"## T-STATUS auto-transitions ({mode}): {proposed}")
    print()
    for det in result.get("details", []):
        verb = "transitioned" if det["applied"] else "skipped"
        line = (
            f"  {det['artifact_id']}: {det['from']} -> {det['to']} ({verb})"
        )
        if det.get("skipped_reason"):
            line += f" — {det['skipped_reason']}"
        elif det.get("index_reconciled"):
            line += " [index row reconciled]"
        print(line)
    print()
    print(
        f"T-STATUS summary: proposed={proposed} applied={result.get('applied', 0)} "
        f"skipped={result.get('skipped', 0)} dry_run={result.get('dry_run')}"
    )
    print()


def cmd_audit_linkage(args: argparse.Namespace) -> int:
    from .fidelity_audit import (
        apply_fixes,
        apply_status_fixes,
        audit_linkage,
        propose_fixes,
    )

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()

    if args.read_fixes:
        from .fidelity_audit.linkage import Fix
        try:
            with open(args.read_fixes, "r", encoding="utf-8") as f:
                data = json.load(f)
            fixes = []
            for item in data:
                fixes.append(Fix(**item))
        except Exception as e:
            print(f"Error loading cached fixes from {args.read_fixes}: {e}")
            return 1

        if not fixes:
            print(f"No mechanical fixes cached in {args.read_fixes}.")
            return 0

        mode = "APPLY" if args.apply else "DRY-RUN"

        by_rule: dict[str, int] = {}
        for f in fixes:
            by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
        rule_breakdown = ", ".join(
            f"{r}={n}" for r, n in sorted(by_rule.items())
        )
        print(f"Loaded cached mechanical fixes ({mode}): {len(fixes)} ({rule_breakdown})")
        print()

        for rule in sorted(by_rule):
            rule_fixes = [f for f in fixes if f.rule == rule]
            print(f"## {rule} ({len(rule_fixes)})")
            print()
            for f in rule_fixes:
                print(f"  [{f.rule}] {f.artifact_id} -> {f.section}: add {', '.join(f.added_ids)}")
                print(f"    {f.file_path}:{f.line_number}")
                print(f"    - {f.before}")
                print(f"    + {f.after}")
                print()
        result = apply_fixes(fixes, dry_run=not args.apply)
        print(
            f"Summary: proposed={result['proposed']} applied={result['applied']} "
            f"skipped_not_found={result['skipped_not_found']} "
            f"files_touched={result['files_touched']} "
            f"dry_run={result['dry_run']}"
        )
        if not args.apply:
            print(
                "\nDry-run only. Pass --apply to write changes to disk."
            )
        return 0

    if args.write_fixes:
        fixes = propose_fixes(repo_root, dekspec_root=args.dekspec_root)
        try:
            Path(args.write_fixes).parent.mkdir(parents=True, exist_ok=True)
            with open(args.write_fixes, "w", encoding="utf-8") as f:
                json.dump([fx.to_dict() for fx in fixes], f, indent=2)
            print(f"Cached {len(fixes)} mechanical fixes to {args.write_fixes}")
        except Exception as e:
            print(f"Error caching fixes to {args.write_fixes}: {e}")
            return 1

    # --fix path: propose (and optionally apply) mechanical fixes.
    # Findings still print so the engineer sees what's not auto-fixable.
    # Two families of auto-fix: the line-level mechanical fixes
    # (L6 / SI-01 / L7 / L8) flowing through propose_fixes()/apply_fixes(),
    # and the bounded T-STATUS auto-transition sweep (ADR-020 / INT-070) —
    # the latter is a multi-edit Status transition + index-row reconcile.
    if args.fix:
        fixes = propose_fixes(repo_root, dekspec_root=args.dekspec_root)
        status_result = apply_status_fixes(
            repo_root,
            dekspec_root=args.dekspec_root,
            dry_run=not args.apply,
        )
        if not fixes and status_result["proposed"] == 0:
            print(f"No mechanical fixes available for {repo_root} at this time.")
            return 0
        mode = "APPLY" if args.apply else "DRY-RUN"

        if fixes:
            # Group by rule family for the summary header
            by_rule: dict[str, int] = {}
            for f in fixes:
                by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
            rule_breakdown = ", ".join(
                f"{r}={n}" for r, n in sorted(by_rule.items())
            )
            print(f"Proposed mechanical fixes ({mode}): {len(fixes)} ({rule_breakdown})")
            print()

            # Group fixes by rule for the per-fix detail printout
            for rule in sorted(by_rule):
                rule_fixes = [f for f in fixes if f.rule == rule]
                print(f"## {rule} ({len(rule_fixes)})")
                print()
                for f in rule_fixes:
                    print(f"  [{f.rule}] {f.artifact_id} -> {f.section}: add {', '.join(f.added_ids)}")
                    print(f"    {f.file_path}:{f.line_number}")
                    print(f"    - {f.before}")
                    print(f"    + {f.after}")
                    print()
            result = apply_fixes(fixes, dry_run=not args.apply)
            print(
                f"Summary: proposed={result['proposed']} applied={result['applied']} "
                f"skipped_not_found={result['skipped_not_found']} "
                f"files_touched={result['files_touched']} "
                f"dry_run={result['dry_run']}"
            )
            print()

        _print_t_status_sweep(status_result, args.apply)

        if not args.apply:
            print(
                "Dry-run only. Pass --apply to write changes to disk. "
                "Other (non-mechanical) findings still need manual attention; "
                "rerun without --fix to see the full audit report."
            )
        return 0

    # Profile resolution (MSN-006 / INT-024 / IB-112): an explicit --profile
    # flag wins; otherwise resolve from `.dekspec/config.yaml methodology_profile`;
    # otherwise the v1 baseline. Precedence: CLI flag > config > default.
    profile = args.profile
    if profile is None:
        from . import dekspec_config

        profile = dekspec_config.resolve_audit_profile(
            dekspec_config.get_profile(repo_root)
        )
    findings = audit_linkage(repo_root, dekspec_root=args.dekspec_root, profile=profile)

    # Legacy --severity flag: translate to --min-severity with a stderr
    # deprecation warning. --min-severity wins if both are passed
    # (i.e. --min-severity is non-None on the parsed Namespace).
    translated_legacy: str | None = None
    if args.severity is not None:
        translated_legacy = _translate_legacy_severity_flag(args.severity)

    # Resolution precedence: explicit --min-severity > translated legacy
    # --severity > default "P3" (include everything).
    min_severity = args.min_severity or translated_legacy or "P3"

    # Canonical-tier filter: include any finding at or above the threshold
    # (P0 strictest = include only P0; P3 broadest = include everything).
    threshold_index = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}[min_severity]
    findings = [f for f in findings if _audit_severity_order.get(f.severity, 99) <= threshold_index]

    if args.json:
        by_rule: dict[str, int] = {}
        for f in findings:
            by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
        envelope = {
            "summary": {
                "total": len(findings),
                "P0": sum(1 for f in findings if f.severity == "P0"),
                "P1": sum(1 for f in findings if f.severity == "P1"),
                "P2": sum(1 for f in findings if f.severity == "P2"),
                "P3": sum(1 for f in findings if f.severity == "P3"),
                "by_rule": dict(sorted(by_rule.items())),
            },
            "repo_root": str(repo_root),
            "dekspec_root": args.dekspec_root,
            "findings": [f.to_dict() for f in findings],
        }
        print(json.dumps(envelope, indent=2))
        return 1 if any(f.severity in {"P0", "P1"} for f in findings) else 0

    if not findings:
        print(f"No linkage findings at severity '{min_severity}' or above for {repo_root}.")
        return 0

    # Bucket findings by canonical tier, iterate P0-first / P3-last.
    by_sev: dict[str, list[Any]] = {"P0": [], "P1": [], "P2": [], "P3": []}
    for f in findings:
        by_sev.setdefault(f.severity, []).append(f)

    print(f"DekSpec linkage audit — {repo_root}")
    print(
        f"Total findings: {len(findings)} "
        f"(P0={len(by_sev['P0'])} P1={len(by_sev['P1'])} "
        f"P2={len(by_sev['P2'])} P3={len(by_sev['P3'])})"
    )
    print()
    for sev in ["P0", "P1", "P2", "P3"]:
        items = by_sev[sev]
        if not items:
            continue
        print(f"## {sev} ({len(items)})")
        print()
        for f in items:
            print(f"  [{f.rule}] {f.artifact_id}  ({f.fix_kind})")
            print(f"    {f.message}")
            print()
    return 1 if (by_sev["P0"] or by_sev["P1"]) else 0


# Audit-side canonical-tier sort key. Mirrors `linkage.severity_order`
# but lives here to avoid forcing every CLI caller to import the audit
# module just to filter on severity. The two dicts MUST stay aligned;
# the `test_audit_severity_rekey.py::test_sort_order_canonical` test
# pins the audit-side ordering and we rely on that contract here.
_audit_severity_order: dict[str, int] = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


# Legacy --severity → canonical --min-severity alias map. Extends the
# audit-side map (`_AUDIT_SEVERITY_ALIAS_MAP` in
# `dekspec.fidelity_audit.linkage`) with `"all": "P3"` — `"all"` is a
# legacy CLI-flag value, not a legacy audit-emission value, so it lives
# only here.
_LEGACY_SEVERITY_TO_CANONICAL: dict[str, str] = {
    "critical": "P1",
    "important": "P2",
    "minor": "P3",
    "all": "P3",
}


def _translate_legacy_severity_flag(legacy_value: str) -> str:
    """Translate legacy --severity value to canonical --min-severity P<n>.

    Emits a deprecation warning to stderr (matching the existing CLI
    convention for operator-facing warnings). Returns the canonical
    P-tier string. The flag is scheduled for removal after one release
    cycle.
    """
    canonical = _LEGACY_SEVERITY_TO_CANONICAL[legacy_value]
    print(
        f"warning: --severity is deprecated; use --min-severity {canonical}",
        file=sys.stderr,
    )
    return canonical


def cmd_audit_failure_classes(args: argparse.Namespace) -> int:
    """`dekspec audit failure-classes` — read-only bead-corpus aggregator
    (INT-126 / ds-99ko). Walks `.beads/issues.jsonl`, groups beads
    carrying `failure-class:<class>` labels per the `--by` axis, and
    prints a markdown (default) or JSON report.
    """
    from dekspec.audit.failure_classes import aggregate, format_report
    repo_root = Path(args.at) if getattr(args, "at", None) else Path.cwd()
    agg = aggregate(
        repo_root=repo_root,
        by=args.by,
        window_days=args.window,
        detect_reverts=getattr(args, "detect_reverts", False),
    )
    print(format_report(agg, fmt=args.format))
    return 0


def cmd_audit_lock_ready(args: argparse.Namespace) -> int:
    from .constraint_compiler.graph import SpecGraph
    from .fidelity_audit.linkage import is_lock_ready, _T_STATUS_INDEX_FILES
    import subprocess

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    dekspec_root = args.dekspec_root

    try:
        graph = SpecGraph.load(repo_root, dekspec_root=dekspec_root)
    except Exception as e:
        print(f"Error loading spec graph: {e}", file=sys.stderr)
        return 1

    # Grab all artifacts that have status = ACCEPTED
    candidates = []
    for art in sorted(graph.all(), key=lambda x: x.get("id", "")):
        art_id = art.get("id", "")
        if not art_id:
            continue
        if not (art_id.startswith("AE-") or art_id.startswith("ADR-") or art_id.startswith("WS-") or art_id.startswith("IC-")):
            continue
        status = art.get("status")
        if status != "ACCEPTED":
            continue
        ready, reason = is_lock_ready(graph, art_id)
        candidates.append({
            "id": art_id,
            "kind": art_id.split("-")[0],
            "status": status,
            "ready": ready,
            "reason": reason,
            "path": art.get("source", {}).get("path") or art.get("path")
        })

    if not candidates:
        print(f"No ACCEPTED candidates found in {repo_root}.")
        return 0

    passers = [c for c in candidates if c["ready"]]
    skips = [c for c in candidates if not c["ready"]]

    print(f"DekSpec lock-ready sweep — {repo_root}")
    print(f"Total ACCEPTED candidates: {len(candidates)} (ready={len(passers)} skip={len(skips)})")
    print()

    if passers:
        print("## Lock-ready candidates (Passers)")
        print()
        print(f"  {'Artifact ID':<15} {'Kind':<10} {'Status':<10} Reason")
        print(f"  {'-' * 15} {'-' * 10} {'-' * 10} {'-' * 40}")
        for p in passers:
            print(f"  {p['id']:<15} {p['kind']:<10} {p['status']:<10} {p['reason']}")
        print()

    if skips:
        print("## Skipped candidates")
        print()
        print(f"  {'Artifact ID':<15} {'Kind':<10} {'Status':<10} Reason")
        print(f"  {'-' * 15} {'-' * 10} {'-' * 10} {'-' * 40}")
        for s in skips:
            print(f"  {s['id']:<15} {s['kind']:<10} {s['status']:<10} {s['reason']}")
        print()

    if not args.apply:
        print("Dry-run mode. No changes written. Pass --apply to lock passing candidates.")
        return 0

    if not passers:
        print("No lock-ready candidates to transition.")
        return 0

    # Confirmation step
    print(f"WARNING: Transitioning {len(passers)} artifacts to LOCKED.")
    print("This will flip Status to LOCKED, bump Modified, append an Amendment Log row,")
    print("and update the corresponding index file.")
    try:
        # Check if stdin is a tty or interactive
        if sys.stdin.isatty():
            ans = input("Proceed? [y/N]: ")
            if ans.strip().lower() not in ("y", "yes"):
                print("Aborted.")
                return 0
        else:
            print("Non-interactive mode: proceeding automatically.")
    except (IOError, EOFError):
        print("Non-interactive mode: proceeding automatically.")

    # Apply changes!
    from .vendoring import resolve_skill_script
    ops_script = resolve_skill_script("_lib/scripts/artifact_ops.py", repo_root=repo_root)
    if ops_script is None:
        print(
            "Error: artifact_ops.py script not found in any known layout "
            "(library plugins/, wheel _vendored/, or source-checkout via DEKSPEC_LIBRARY_ROOT). "
            "If dekspec is wheel-installed, verify the wheel built with the vendored skills tree.",
            file=sys.stderr,
        )
        return 1

    success_count = 0
    failure_count = 0

    for p in passers:
        art_id = p["id"]
        art_path = Path(p["path"])
        if not art_path.is_absolute():
            art_path = repo_root / art_path

        try:
            rel_path = art_path.relative_to(repo_root)
        except ValueError:
            rel_path = art_path
        print(f"Locking {art_id} ({rel_path})...")

        # 1. artifact_ops.py transition
        note_text = "Artifact locked after pre-lock audit passed"
        cmd_tr = [
            sys.executable,
            str(ops_script),
            "transition",
            str(art_path),
            "--from",
            "ACCEPTED",
            "--to",
            "LOCKED",
            "--note",
            note_text,
            "--engineer",
            args.engineer
        ]
        res_tr = subprocess.run(cmd_tr, capture_output=True, text=True)
        if res_tr.returncode != 0:
            print(f"  [FAIL] transition command failed: {res_tr.stderr.strip()}", file=sys.stderr)
            failure_count += 1
            continue

        # 2. artifact_ops.py update-index
        # Find index file
        index_file = None
        for prefix, index_name in _T_STATUS_INDEX_FILES.items():
            if art_id.startswith(prefix):
                if graph.dekspec_dir:
                    idx_p = graph.dekspec_dir / index_name
                    if idx_p.exists():
                        index_file = idx_p
                break

        if index_file:
            cmd_idx = [
                sys.executable,
                str(ops_script),
                "update-index",
                str(index_file),
                "--id",
                art_id,
                "--status",
                "LOCKED"
            ]
            res_idx = subprocess.run(cmd_idx, capture_output=True, text=True)
            if res_idx.returncode != 0:
                print(f"  [WARNING] update-index failed: {res_idx.stderr.strip()}", file=sys.stderr)

        # 3. Validate the candidate
        cmd_val = [
            sys.executable,
            "-m",
            "dekspec.cli",
            "validate",
            str(art_path)
        ]
        res_val = subprocess.run(cmd_val, capture_output=True, text=True)
        if res_val.returncode != 0:
            print(f"  [FAIL] validation check failed post-lock: {res_val.stderr.strip()}", file=sys.stderr)
            failure_count += 1
            continue

        print(f"  [OK] {art_id} is successfully locked and validated.")
        success_count += 1

    print()
    print(f"Mass-lock complete: {success_count} succeeded, {failure_count} failed.")
    return 1 if failure_count > 0 else 0


def _add_aggregate_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "aggregate",
        help="Aggregate compiled outputs across the whole spec graph.",
        description=(
            "Aggregator commands that walk the SpecGraph and produce a "
            "single combined output. Today: agents-md only."
        ),
    )
    agg_sub = p.add_subparsers(dest="aggregate_command", metavar="<aggregate-command>")

    p_md = agg_sub.add_parser(
        "agents-md",
        help="Walk the spec graph and write a project-wide AGENTS.md at repo root.",
        description=(
            "Aggregates per-artifact agents-md fragments (AE, ADR, WS) into a "
            "single AGENTS.md. Default status filter: LOCKED,ACCEPTED. Default "
            "output path: <repo_root>/AGENTS.md. Use --output to override."
        ),
    )
    p_md.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_md.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Path to the DekSpec content tree relative to repo root (default: dekspec).",
    )
    p_md.add_argument(
        "--output",
        help="Output path (default: <repo_root>/AGENTS.md). Use '-' for stdout.",
    )
    p_md.add_argument(
        "--status",
        default="LOCKED,ACCEPTED",
        help=(
            "Comma-separated status filter; only artifacts in any of these states "
            "are included. Pass 'all' to include every artifact. "
            "Default: LOCKED,ACCEPTED."
        ),
    )
    p_md.add_argument(
        "--include",
        default="CONSTITUTION,SECURITY_PROFILE,VISION,GLOSSARY,AE,ADR,WS,IB,INT,MSN",
        help=(
            "Comma-separated artifact kinds to include "
            "(any of CONSTITUTION,SECURITY_PROFILE,VISION,GLOSSARY,AE,ADR,WS,IB,INT,MSN). "
            "Default: CONSTITUTION,SECURITY_PROFILE,VISION,GLOSSARY,AE,ADR,WS,IB,INT,MSN."
        ),
    )
    p_md.set_defaults(func=cmd_aggregate_agents_md)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


# --------------------------------------------------------------------------- #
# emit — per-artifact compiled-output verb (today: security-profile only)
# --------------------------------------------------------------------------- #


def _add_emit_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "emit",
        help="Emit per-artifact compiled outputs (mid + hard enforcement layers).",
        description=(
            "Emit subcommands compile a single parsed artifact into a "
            "machine-consumable enforcement payload. Today: security-profile "
            "only (mid-layer pre-commit fragment + hard-layer CI gate "
            "fragment from a Security Profile). Soft-layer AGENTS.md "
            "composition lives under `dekspec aggregate agents-md` instead."
        ),
    )
    emit_sub = p.add_subparsers(dest="emit_command", metavar="<emit-command>")

    p_sp = emit_sub.add_parser(
        "security-profile",
        help="Emit Security Profile mid-layer pre-commit + hard-layer CI gate snippets.",
        description=(
            "Read a Security Profile markdown file via the WS-017 parser, "
            "then emit both the mid-layer .pre-commit-config.yaml fragment "
            "and the hard-layer .github/workflows/security.yml fragment. "
            "Default: both snippets to stdout separated by `---\\n` "
            "(precommit first, ci-gates second). Use --out-precommit / "
            "--out-ci-gates to route either snippet to a named file."
        ),
    )
    p_sp.add_argument(
        "path",
        help="Path to the Security Profile markdown file (SP-NNN-*.md).",
    )
    p_sp.add_argument(
        "--out-precommit",
        default=None,
        help=(
            "Optional path to write the mid-layer pre-commit snippet. "
            "When passed, the snippet goes to this file; the CI-gates "
            "snippet still goes to stdout unless --out-ci-gates is also "
            "passed."
        ),
    )
    p_sp.add_argument(
        "--out-ci-gates",
        default=None,
        help=(
            "Optional path to write the hard-layer CI gates snippet. "
            "When passed, the snippet goes to this file; the pre-commit "
            "snippet still goes to stdout unless --out-precommit is also "
            "passed."
        ),
    )
    p_sp.add_argument(
        "--platform",
        default="github_actions",
        help=(
            "CI platform discriminator for the hard-layer snippet. "
            "V1 supports `github_actions` only; any other value raises "
            "UnsupportedPlatformError (the future GitLab CI / Bitbucket "
            "Pipelines work is tracked under MSN-003 §Notes OI-2)."
        ),
    )
    p_sp.set_defaults(func=cmd_emit_security_profile)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


def cmd_emit_security_profile(args: argparse.Namespace) -> int:
    from .constraint_compiler.emitters.precommit import (
        SecurityProfileEmitterError,
        emit_security_profile_precommit,
    )
    from .constraint_compiler.emitters.ci_gates import (
        emit_security_profile_ci_gates,
    )

    src = Path(args.path).resolve()
    if not src.exists():
        print(f"Error: source not found: {src}", file=sys.stderr)
        return 2

    try:
        ir = parse_security_profile(src)
    except SPParseError as e:
        print(f"Parse error in {src}:\n{e}", file=sys.stderr)
        return 4

    # Both emitters consume the parsed IR directly. Per WS-019 BR9, this
    # dispatcher is a thin adapter — emitter typed errors propagate
    # unmodified so the engineer sees `UnsupportedPlatformError` /
    # `MissingRequiredFieldError` on stderr with a non-zero exit.
    try:
        precommit_snippet = emit_security_profile_precommit(ir)
        ci_gates_snippet = emit_security_profile_ci_gates(
            ir, platform=args.platform
        )
    except SecurityProfileEmitterError as e:
        print(f"Emit error: {type(e).__name__}: {e}", file=sys.stderr)
        return 4

    # Output routing matrix per BR8: four cases based on which output
    # flags are passed. File writes use newline="" so Python doesn't
    # translate \n to \r\n on Windows (mirrors the existing emitter
    # convention).
    out_pc: str | None = args.out_precommit
    out_ci: str | None = args.out_ci_gates
    if out_pc is None and out_ci is None:
        sys.stdout.write(precommit_snippet)
        if not precommit_snippet.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.write("---\n")
        sys.stdout.write(ci_gates_snippet)
        if not ci_gates_snippet.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    if out_pc is not None:
        _write_snippet(out_pc, precommit_snippet)
    if out_ci is not None:
        _write_snippet(out_ci, ci_gates_snippet)
    # Whichever snippet did NOT receive a file flag goes to stdout
    # instead.
    if out_pc is None:
        sys.stdout.write(precommit_snippet)
        if not precommit_snippet.endswith("\n"):
            sys.stdout.write("\n")
    if out_ci is None:
        sys.stdout.write(ci_gates_snippet)
        if not ci_gates_snippet.endswith("\n"):
            sys.stdout.write("\n")
    return 0


def _write_snippet(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        f.write(content)


def cmd_aggregate_agents_md(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone
    from .constraint_compiler.graph import SpecGraph

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    graph = SpecGraph.load(repo_root, dekspec_root=args.dekspec_root)

    # IB-116: under the `lite` methodology profile, emit a single-page AGENTS.md
    # (a one-page Constitution summary + the in-flight Intent) instead of the
    # full corpus dump. `compact_aggregate_for_profile` consults INT-024's
    # `get_profile()` — the single load-bearing profile read point — and returns
    # the compact render only when the profile is `lite`; it returns None
    # otherwise so the `full`-profile path below stays byte-identical.
    # `TESTFAIL` retired from the Intent enum 2026-05-25 (E3 audit).
    _in_flight_statuses = {"IMPLEMENTING", "TESTPASS"}
    _active_intent = next(
        (
            i
            for i in sorted(graph.intents(), key=lambda x: x["id"])
            if i.get("status", "").upper() in _in_flight_statuses
        ),
        None,
    )
    _compact = agents_md.compact_aggregate_for_profile(
        repo_root, graph.constitution(), _active_intent
    )
    if _compact is not None:
        if args.output == "-":
            sys.stdout.write(_compact)
            return 0
        out_path = Path(args.output) if args.output else (repo_root / "AGENTS.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(_compact, encoding="utf-8")
        print(
            f"Wrote AGENTS.md -> {out_path} "
            f"({len(_compact)} bytes; lite-profile compact single-page render)"
        )
        return 0

    status_filter: set[str] | None = None
    if args.status.lower() != "all":
        status_filter = {s.strip().upper() for s in args.status.split(",") if s.strip()}

    include_kinds = {k.strip().upper() for k in args.include.split(",") if k.strip()}
    valid_kinds = {
        "AE", "ADR", "WS", "IB", "INT", "MSN",
        "VISION", "GLOSSARY", "CONSTITUTION", "SECURITY_PROFILE",
    }
    bad = include_kinds - valid_kinds
    if bad:
        print(
            f"Error: --include contains unknown kinds: {sorted(bad)}. "
            f"Valid: {sorted(valid_kinds)}.",
            file=sys.stderr,
        )
        return 2

    def passes(ir: dict[str, Any]) -> bool:
        if status_filter is not None and ir.get("status", "").upper() not in status_filter:
            return False
        return True

    aes = sorted([ae for ae in graph.aes() if passes(ae)], key=lambda x: x["id"]) \
        if "AE" in include_kinds else []
    adrs = sorted([adr for adr in graph.adrs() if passes(adr)], key=lambda x: x["id"]) \
        if "ADR" in include_kinds else []
    wses = sorted([ws for ws in graph.wses() if passes(ws)], key=lambda x: x["id"]) \
        if "WS" in include_kinds else []
    ibs = sorted([ib for ib in graph.ibs() if passes(ib)], key=lambda x: x["id"]) \
        if "IB" in include_kinds else []
    intents = sorted([i for i in graph.intents() if passes(i)], key=lambda x: x["id"]) \
        if "INT" in include_kinds else []
    missions = sorted([m for m in graph.missions() if passes(m)], key=lambda x: x["id"]) \
        if "MSN" in include_kinds else []
    vision = graph.vision() if "VISION" in include_kinds else None
    glossary = graph.glossary() if "GLOSSARY" in include_kinds else None
    constitution = graph.constitution() if "CONSTITUTION" in include_kinds else None
    security_profiles = sorted(
        [sp for sp in graph.security_profiles() if passes(sp)],
        key=lambda x: x["id"],
    ) if "SECURITY_PROFILE" in include_kinds else []

    parts: list[str] = []
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts.append("<!--")
    parts.append("  AGENTS.md — auto-generated by dekspec aggregate agents-md")
    parts.append(f"  Source spec graph: {repo_root}/{args.dekspec_root}")
    parts.append(f"  Status filter: {args.status}")
    parts.append(f"  Included kinds: {','.join(sorted(include_kinds))}")
    parts.append(f"  Compiled: {timestamp}")
    parts.append(f"  Library: dekspec {__version__}")
    parts.append("")
    parts.append("  DO NOT EDIT THIS FILE BY HAND. Re-run `dekspec aggregate agents-md`")
    parts.append("  to regenerate after spec changes. Per-artifact fragments are")
    parts.append("  delimited by <!-- BEGIN/END dekspec-fragment: <id> --> markers.")
    parts.append("-->")
    parts.append("")
    parts.append("# AGENTS.md")
    parts.append("")
    parts.append(
        f"Compiled context for AI agents working in this repo. "
        f"{len(aes)} architecture element(s), {len(adrs)} decision record(s), "
        f"{len(wses)} working spec(s), {len(ibs)} implementation brief(s), "
        f"{len(intents)} intent(s), {len(missions)} mission(s)."
        + (f" Glossary: {len(glossary['terms'])} terms." if glossary else "")
        + (f" Vision: {vision['name']}." if vision else "")
        + (
            f" Constitution: {len(constitution['articles'])} article(s)."
            if constitution
            else ""
        )
        + (
            f" Security profiles: {len(security_profiles)}."
            if security_profiles
            else ""
        )
    )
    parts.append("")

    if constitution:
        parts.append("---")
        parts.append("")
        parts.append(f"# Constitution: {constitution['name']}")
        parts.append("")
        parts.append(
            "\n\n".join(agents_md.emit_constitution(constitution))
        )
        parts.append("")

    if security_profiles:
        parts.append("---")
        parts.append("")
        parts.append("## Security Profile")
        parts.append("")
        for sp in security_profiles:
            parts.append(f"### {sp['id']} — {sp['title']}")
            parts.append("")
            # Pre-flatten typed-record arrays into string arrays for the
            # soft emitter. Per IB-029, emit_security_profile_soft treats
            # string-array slots as `- <entry>` verbatim; the schema's
            # typed-record arrays carry the engineer-meaningful identifier
            # in the `name` field, so we project to strings here.
            # supply_chain.allowed_sources is already a string array;
            # owasp_coverage stays dict-shaped (its helper reads
            # `owasp_id` + `mitigation_strategy` directly).
            sp_for_emit = {
                **sp,
                "allowed_dataflows": [r["name"] for r in sp.get("allowed_dataflows", [])],
                "secret_stores": [r["name"] for r in sp.get("secret_stores", [])],
                "authn_methods": [r["name"] for r in sp.get("authn_methods", [])],
                "sast_tools": [r["name"] for r in sp.get("sast_tools", [])],
                "dast_tools": [r["name"] for r in sp.get("dast_tools", [])],
            }
            rewritten_fragments = [
                frag.replace("### ", "#### ", 1)
                for frag in agents_md.emit_security_profile_soft(sp_for_emit)
            ]
            parts.append("\n\n".join(rewritten_fragments))
            parts.append("")
        parts.append("---")
        parts.append("")

    if vision:
        parts.append("---")
        parts.append("")
        parts.append(f"# System Vision: {vision['name']}")
        parts.append("")
        if vision.get("preamble"):
            parts.append(vision["preamble"])
            parts.append("")
        if vision.get("what_this_is"):
            parts.append("## What this is")
            parts.append("")
            parts.append(vision["what_this_is"])
            parts.append("")
        if vision.get("what_we_are_not_building"):
            parts.append("## Out of scope (Vision-level)")
            parts.append("")
            for entry in vision["what_we_are_not_building"]:
                parts.append(f"- {entry}")
            parts.append("")

    if glossary:
        parts.append("---")
        parts.append("")
        parts.append("# Domain Glossary")
        parts.append("")
        parts.append(
            f"Canonical definitions for {len(glossary['terms'])} domain term(s) "
            f"across {len({t['category'] for t in glossary['terms']})} categor(y/ies). "
            f"Read this before introducing or interpreting any domain term."
        )
        parts.append("")
        # Group by category
        by_cat: dict[str, list[dict[str, Any]]] = {}
        for t in glossary["terms"]:
            by_cat.setdefault(t["category"], []).append(t)
        for cat in sorted(by_cat):
            parts.append(f"## {cat}")
            parts.append("")
            for t in by_cat[cat]:
                term = t["term"]
                defn = t.get("canonical_definition", "")
                if defn:
                    parts.append(f"- **{term}** — {defn}")
                else:
                    parts.append(f"- **{term}**")
            parts.append("")

    if aes:
        parts.append("---")
        parts.append("")
        parts.append("# Architecture Elements")
        parts.append("")
        parts.append(
            "Architectural slices that scope where each rule applies. "
            "When working in any path matched by an AE's `When working in` globs, "
            "treat its purpose, responsibilities, and boundaries as binding."
        )
        parts.append("")
        for ae in aes:
            parts.append(agents_md.emit_ae(ae))

    if adrs:
        parts.append("---")
        parts.append("")
        parts.append("# Architecture Decision Records")
        parts.append("")
        parts.append(
            "Decisions that shape one or more AEs. Honor each ACCEPTED/LOCKED "
            "decision unless its `Reconsider this decision if` triggers fire — "
            "in which case stop and surface to the human."
        )
        parts.append("")
        for adr in adrs:
            parts.append(agents_md.emit_adr(adr))

    if wses:
        parts.append("---")
        parts.append("")
        parts.append("# Working Specs")
        parts.append("")
        parts.append(
            "Behavioral contracts. Business rules and failure behaviors are "
            "testable assertions; treat them as required when implementing or "
            "modifying code in scope."
        )
        parts.append("")
        for ws in wses:
            parts.append(agents_md.emit_ws(ws))

    if ibs:
        parts.append("---")
        parts.append("")
        parts.append("# Implementation Briefs")
        parts.append("")
        parts.append(
            "Per-task implementation contracts. Each IB authorizes a specific "
            "scope of files-to-modify, lists Done When acceptance criteria, "
            "and points back at its parent Working Spec + Source AEs. When "
            "executing an IB, the listed scope is the only scope you are "
            "authorized to change."
        )
        parts.append("")
        for ib in ibs:
            parts.append(agents_md.emit_ib(ib))

    if missions:
        parts.append("---")
        parts.append("")
        parts.append("# Missions")
        parts.append("")
        parts.append(
            "Cross-Intent coordination artifacts. Each Mission binds a set of "
            "Intents to a single user-observable outcome with explicit "
            "out-of-scope, flag strategy, kill criteria, and a Mission Verification "
            "predicate that gates COMPLETING → COMPLETE."
        )
        parts.append("")
        for msn in missions:
            parts.append(agents_md.emit_mission(msn))

    if intents:
        parts.append("---")
        parts.append("")
        parts.append("# Intents")
        parts.append("")
        parts.append(
            "Captured engineer intent — what change is being made and why. "
            "Each Intent declares its components_affected (diff confinement) "
            "and a Verification predicate (the TESTPASS gate). Intents under "
            "a Mission inherit the Mission's autonomy ceiling."
        )
        parts.append("")
        for intent in intents:
            parts.append(agents_md.emit_intent(intent))

    output = "\n".join(parts)
    if not output.endswith("\n"):
        output += "\n"

    if args.output == "-":
        sys.stdout.write(output)
        return 0

    out_path = Path(args.output) if args.output else (repo_root / "AGENTS.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(
        f"Wrote AGENTS.md -> {out_path} "
        f"({len(output)} bytes; {len(aes)} AE, {len(adrs)} ADR, {len(wses)} WS"
        + (f", Constitution: {len(constitution['articles'])} articles" if constitution else "")
        + ")"
    )
    return 0


def _add_migrate_subparser(sub: argparse._SubParsersAction) -> None:
    """Register `migrate-ir` — migrates persisted IR JSON files forward
    through the schema migration registry.

    Renamed from `migrate` → `migrate-ir` in v0.50.0 to disambiguate from
    `migrate-artifacts` (which handles markdown). No back-compat alias —
    callers of the old name update on this release.
    """
    p = sub.add_parser(
        "migrate-ir",
        help="Migrate persisted IR JSON files forward through registered schema migrations.",
        description=(
            "Reads one or more IR JSON files (typically from a per-run "
            "<repo-state-dir>/runs/.../irs/<id>.ir.json), runs them through "
            "the migration registry (`dekspec.migrations.default_registry`), "
            "and writes the upgraded IR back. Dry-run by default — pass "
            "--apply to write."
        ),
    )
    p.add_argument(
        "path",
        nargs="+",
        help=(
            "One or more IR JSON file paths. Glob expansion is the shell's "
            "responsibility (e.g., `dekspec migrate-ir runs/*/irs/*.ir.json`)."
        ),
    )
    p.add_argument(
        "--to",
        metavar="VERSION",
        help=(
            "Target ir_schema_version (default: latest registered for the "
            "artifact type). Use this to stop at an intermediate version."
        ),
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Write the migrated IR back to disk. Without --apply, dry-run only.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit per-file results as JSON.",
    )
    p.set_defaults(func=cmd_migrate)


def cmd_migrate(args: argparse.Namespace) -> int:
    """Apply schema migrations to persisted IR JSON files."""
    from .migrations import MigrationError, default_registry

    problems = default_registry.validate_chains()
    if problems:
        print(
            "Migration registry has broken chains:\n  - "
            + "\n  - ".join(problems),
            file=sys.stderr,
        )
        return 2

    results: list[dict[str, Any]] = []
    any_error = False
    for path_str in args.path:
        path = Path(path_str).resolve()
        entry: dict[str, Any] = {"path": str(path), "status": "unchanged"}
        if not path.exists():
            entry["status"] = "missing"
            entry["error"] = "file not found"
            any_error = True
            results.append(entry)
            continue
        try:
            ir = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            entry["status"] = "errored"
            entry["error"] = f"{type(e).__name__}: {e}"
            any_error = True
            results.append(entry)
            continue
        entry["artifact_id"] = ir.get("id")
        entry["from_version"] = ir.get("ir_schema_version")
        try:
            migrated = default_registry.apply(ir, to_version=args.to)
        except MigrationError as e:
            entry["status"] = "errored"
            entry["error"] = str(e)
            any_error = True
            results.append(entry)
            continue
        entry["to_version"] = migrated.get("ir_schema_version")
        if entry["to_version"] == entry["from_version"]:
            entry["status"] = "unchanged"
        else:
            entry["status"] = "migrated" if args.apply else "would-migrate"
            if args.apply:
                path.write_text(
                    json.dumps(migrated, indent=2, default=str) + "\n",
                    encoding="utf-8",
                )
        results.append(entry)

    if args.json:
        print(json.dumps({
            "applied": args.apply,
            "files": len(results),
            "results": results,
        }, indent=2, default=str))
        return 1 if any_error else 0

    n_unchanged = sum(1 for r in results if r["status"] == "unchanged")
    n_would_or_did = sum(
        1 for r in results if r["status"] in {"migrated", "would-migrate"}
    )
    n_errored = sum(1 for r in results if r["status"] == "errored")
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"Migration ({mode}): {len(results)} file(s)  "
        f"[{n_would_or_did} would-migrate/migrated, "
        f"{n_unchanged} unchanged, {n_errored} errored]"
    )
    for r in results:
        if r["status"] == "unchanged":
            continue
        glyph = {
            "migrated": "✓",
            "would-migrate": "→",
            "errored": "✗",
            "missing": "?",
        }.get(r["status"], "·")
        line = f"  {glyph} [{r['status']:<14}] {r['path']}"
        if "from_version" in r and "to_version" in r:
            line += f"  ({r['from_version']} → {r['to_version']})"
        if "error" in r:
            line += f"  error: {r['error']}"
        print(line)
    return 1 if any_error else 0


def _add_doctor_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "doctor",
        help="Composite health check: vendoring drift + audit linkage + parse failures.",
        description=(
            "Runs verify-vendored, audit linkage, and parse-failure detection in "
            "one pass and rolls up a traffic-light summary. Auto-skips categories "
            "that don't apply to this repo (e.g., no vendored content → skip "
            "verify-vendored). Useful for new users + pre-commit hooks + CI."
        ),
    )
    p.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Path to the DekSpec content tree relative to repo root (default: dekspec).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit rolled-up summary as JSON instead of formatted text.",
    )
    p.add_argument(
        "--profile",
        default=None,
        help=(
            "Audit-rule profile to enforce. An explicit value overrides the "
            "`methodology_profile` field of `.dekspec/config.yaml`; when "
            "omitted, the config field is consulted, falling back to v1 "
            "(MSN-006 / INT-024)."
        ),
    )
    # INT-127 / ds-bqhf — audit-loop discipline flags.
    p.add_argument(
        "--loop",
        action="store_true",
        help=(
            "Run the mechanical-fixed-point loop: re-execute the audit rule "
            "family until quiescence, semantic-only stall, oscillation, or "
            "--pass-cap N (INT-127)."
        ),
    )
    p.add_argument(
        "--pass-cap",
        type=int,
        default=5,
        help=(
            "Max passes for --loop (default: 5; placeholder per cross-plan "
            "SOFT dep on DekFactory Phase 0 archeology, INT-127)."
        ),
    )
    p.add_argument(
        "--scope",
        choices=["artifact", "corpus"],
        default="corpus",
        help="Loop scope: one artifact or the whole tree (default: corpus).",
    )
    p.add_argument(
        "--axis",
        default=None,
        help=(
            "Comma-separated rule-family axes (e.g. T,L). Restricts the loop "
            "to those families. Default: all axes."
        ),
    )
    p.set_defaults(func=cmd_doctor)


def _fix_to_convergence(
    repo_root,
    dekspec_root: str = "dekspec",
    max_passes: int = 10,
    *,
    _propose=None,
    _apply=None,
) -> list[int]:
    """Run the mechanical fix sweep to a fixed point (ADR-042 / INT-127).

    Re-runs propose_fixes → apply_fixes until propose_fixes returns nothing
    (quiescence) or `max_passes` is reached. Only mechanical fixes flow through
    propose_fixes (L6 backlinks, status metadata) — reversible metadata moves,
    never semantic edits — so looping to convergence is safe. Returns the
    per-pass fix count (its length is the number of passes that did work).

    `_propose` / `_apply` are injectable for testing; they default to the
    tested primitives in fidelity_audit.linkage.
    """
    if _propose is None or _apply is None:
        from .fidelity_audit.linkage import apply_fixes as _a
        from .fidelity_audit.linkage import propose_fixes as _p

        _propose = _propose or _p
        _apply = _apply or _a

    rounds: list[int] = []
    for _ in range(max_passes):
        fixes = _propose(repo_root, dekspec_root=dekspec_root)
        if not fixes:
            break
        _apply(fixes, dry_run=False)
        rounds.append(len(fixes))
    return rounds


def cmd_audit(args: argparse.Namespace) -> int:
    """ADR-042 consolidated `audit` verb — the composite health check.

    Fixes to convergence by default (mechanical fixes only); ``--check-only``
    reports without mutating (the CI-safe path). Delegates to the doctor
    composite with ``--loop`` toggled by ``--check-only``. The nested
    ``audit <sub>`` forms remain as deprecated aliases.
    """
    doctor_args = argparse.Namespace(
        at=getattr(args, "at", None),
        dekspec_root=getattr(args, "dekspec_root", "dekspec"),
        json=getattr(args, "json", False),
        profile=getattr(args, "profile", None),
        loop=not getattr(args, "check_only", False),
        pass_cap=10,
        scope="corpus",
        axis=None,
    )
    return cmd_doctor(doctor_args)


def cmd_doctor(args: argparse.Namespace) -> int:
    """Composite health check. Exit 0 = clean OR advisory, 1 = warnings, 2 = critical.

    Per ADR-005 (severity-graded findings) and ds-cx6: P3 findings are
    advisory-by-design (L9-INT-CMD-RESOLVE and L10-GLOSSARY-COVERAGE both
    emit P3 intentionally on DRAFT/aspirational artifacts). The
    aggregation surfaces P3-only audit results as overall status
    `ADVISORY` — visible to the operator, but does NOT escalate the exit
    code and does NOT gate CI. P2 escalates to WARNING + exit 1; P1 or
    P0 escalate to CRITICAL + exit 2. The internal `worst_severity`
    state-machine vocabulary (`clean / advisory / warning / critical`)
    is preserved unchanged — the canonical P-tier ladder maps INTO it.
    """
    from .constraint_compiler.graph import SpecGraph
    from .fidelity_audit.linkage import audit_linkage
    from .vendoring import compute_drift

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()

    # ADR-042 / INT-127 — with --loop, drive the mechanical fix sweep to a
    # fixed point before reporting, so the composite reflects the post-fix
    # state. Mechanical fixes only (reversible metadata moves).
    if getattr(args, "loop", False):
        passes = _fix_to_convergence(
            repo_root,
            dekspec_root=getattr(args, "dekspec_root", "dekspec"),
            max_passes=getattr(args, "pass_cap", 10) or 10,
        )
        if passes:
            print(
                f"fix-to-convergence: {len(passes)} pass(es) applied "
                f"(fixes per pass = {passes})"
            )

    sections: list[dict[str, Any]] = []
    worst_severity = "clean"  # clean | advisory | warning | critical

    # Section 1: verify-vendored (auto-skip if no .dekspec-version + no vendored prefix)
    has_version_marker = (repo_root / ".dekspec-version").exists()
    has_vendor_manifest = (repo_root / ".dekspec-vendor-manifest").exists()
    has_vendored_templates = (repo_root / "dekspec" / "templates").exists()
    if has_version_marker or has_vendor_manifest or has_vendored_templates:
        try:
            drift = compute_drift(repo_root)
            unreliable = any(f.kind == "reference-unreliable" for f in drift)
            version_skew = next(
                (f for f in drift if f.kind in
                 ("engine-stale-vs-vendored", "vendored-stale-vs-engine")),
                None,
            )
            mod_count = sum(1 for f in drift if f.kind == "modified")
            missing_count = sum(1 for f in drift if f.kind == "missing")
            unknown_count = sum(1 for f in drift if f.kind == "unknown")
            version_count = sum(1 for f in drift if f.kind == "version")
            if version_skew is not None:
                status = "advisory"
                worst_severity = _worse(worst_severity, "advisory")
                _v_engine = __version__
                _mk = repo_root / ".dekspec-version"
                _v_vendored = (
                    _mk.read_text(encoding="utf-8").strip() if _mk.exists() else "?"
                )
                if version_skew.kind == "vendored-stale-vs-engine":
                    summary = (
                        f"vendored content stale — engine {_v_engine} is newer "
                        f"than vendored {_v_vendored}; run `dekspec sync`"
                    )
                else:
                    summary = (
                        f"engine stale — engine {_v_engine} is older than "
                        f"vendored {_v_vendored}; upgrade the engine"
                    )
            elif unreliable:
                status = "advisory"
                worst_severity = _worse(worst_severity, "advisory")
                summary = (
                    "reference unreliable — library is a dev checkout, not "
                    "a release; run `dekspec upgrade --dry-run` to verify"
                )
            else:
                status = "clean"
                if mod_count or missing_count or version_count:
                    status = "warning"
                    worst_severity = _worse(worst_severity, "warning")
                summary = (
                    f"modified={mod_count} missing={missing_count} "
                    f"unknown={unknown_count} version={version_count}"
                )
            sections.append({
                "name": "verify-vendored",
                "status": status,
                "summary": summary,
                "findings_count": len(drift),
            })
        except Exception as e:
            sections.append({
                "name": "verify-vendored",
                "status": "skipped",
                "summary": f"errored: {type(e).__name__}: {str(e)[:120]}",
                "findings_count": 0,
            })
    else:
        sections.append({
            "name": "verify-vendored",
            "status": "skipped",
            "summary": "no .dekspec-version, .dekspec-vendor-manifest, or dekspec/templates/ — not a vendored consumer",
            "findings_count": 0,
        })

    # Section 2: audit linkage (auto-skip if no dekspec content tree)
    dekspec_dir = repo_root / args.dekspec_root
    if dekspec_dir.exists():
        try:
            # Profile resolution mirrors `dekspec audit linkage`
            # (MSN-006 / INT-024 / IB-112): explicit --profile > config
            # `methodology_profile` > v1 default.
            doctor_profile = getattr(args, "profile", None)
            if doctor_profile is None:
                from . import dekspec_config

                doctor_profile = dekspec_config.resolve_audit_profile(
                    dekspec_config.get_profile(repo_root)
                )
            findings = audit_linkage(
                repo_root,
                dekspec_root=args.dekspec_root,
                profile=doctor_profile,
            )
            # Canonical-tier bucket counts (P0 highest → P3 lowest).
            p0 = sum(1 for f in findings if f.severity == "P0")
            p1 = sum(1 for f in findings if f.severity == "P1")
            p2 = sum(1 for f in findings if f.severity == "P2")
            p3 = sum(1 for f in findings if f.severity == "P3")
            status = "clean"
            # Canonical-to-internal-state-name translation per IB-024:
            # P0 or P1 → critical (exit 2); P2 → warning (exit 1);
            # P3 only → advisory (exit 0). The internal worst_severity
            # state machine + `_worse()` helper are preserved unchanged.
            if p0 or p1:
                status = "critical"
                worst_severity = _worse(worst_severity, "critical")
            elif p2:
                status = "warning"
                worst_severity = _worse(worst_severity, "warning")
            elif p3:
                # Per ds-cx6 / ADR-005: P3 findings are advisory by design
                # (L9 / L10 emit on DRAFT artifacts intentionally). Surface
                # them as ADVISORY — visible but non-blocking.
                status = "advisory"
                worst_severity = _worse(worst_severity, "advisory")
            sections.append({
                "name": "audit linkage",
                "status": status,
                "summary": f"P0={p0} P1={p1} P2={p2} P3={p3}",
                "findings_count": len(findings),
            })
        except Exception as e:
            sections.append({
                "name": "audit linkage",
                "status": "skipped",
                "summary": f"errored: {type(e).__name__}: {str(e)[:120]}",
                "findings_count": 0,
            })
    else:
        sections.append({
            "name": "audit linkage",
            "status": "skipped",
            "summary": f"no dekspec content tree at {dekspec_dir}",
            "findings_count": 0,
        })

    # Section 2b: provisional incubation tree (INT-079).
    # Walks `dekspec/provisional/` and reports non-empty incubation folders.
    # Always advisory — provisional artifacts are intentionally outside the
    # canonical gate. Empty `provisional/` reports CLEAN; presence reports
    # ADVISORY with one-line summary. Future INT-provisional-audit-treatment
    # adds per-folder L-PROVISIONAL-* rules; this section is the doctor-level
    # surface that ships with INT-079.
    provisional_dir = dekspec_dir / "provisional"
    if provisional_dir.exists():
        incubations = [
            p for p in provisional_dir.iterdir()
            if p.is_dir() and not p.name.startswith(".")
            and any(f.suffix == ".md" for f in p.iterdir() if f.is_file())
        ]
        if incubations:
            slugs = ", ".join(sorted(p.name for p in incubations))
            sections.append({
                "name": "provisional",
                "status": "advisory",
                "summary": f"{len(incubations)} incubation folder(s): {slugs}",
                "findings_count": len(incubations),
            })
            worst_severity = _worse(worst_severity, "advisory")
        else:
            sections.append({
                "name": "provisional",
                "status": "clean",
                "summary": "no incubation folders",
                "findings_count": 0,
            })
    else:
        sections.append({
            "name": "provisional",
            "status": "skipped",
            "summary": "dekspec/provisional/ not scaffolded — run `dekspec init`",
            "findings_count": 0,
        })

    # Section 2c: plugin-version drift (ds-unify-install-and-sync-docs-ajoo).
    # Checks whether the Claude Code plugin installed at
    # `~/.claude/plugins/cache/dekspec/dekspec/<version>/` matches the
    # CLI's `dekspec.__version__`. Informational — never escalates the
    # doctor's worst_severity. Drift is reported in the section summary
    # for operator visibility (re-run `bash scripts/install.sh` to sync).
    # The non-escalation is deliberate: between a CLI upgrade and a
    # plugin upgrade the two surfaces are EXPECTED to differ; surfacing
    # that as ADVISORY would force CI to fail during the install-flow
    # transition window. Engine behavior never depends on plugin
    # install state.
    plugin_drift = _check_plugin_version_drift()
    if plugin_drift is not None:
        kind, summary = plugin_drift
        if kind == "ok":
            sections.append({
                "name": "plugin version",
                "status": "clean",
                "summary": summary,
                "findings_count": 0,
            })
        elif kind == "skip":
            sections.append({
                "name": "plugin version",
                "status": "skipped",
                "summary": summary,
                "findings_count": 0,
            })
        else:  # drift — informational only; does not affect exit code
            sections.append({
                "name": "plugin version",
                "status": "clean",
                "summary": f"drift: {summary}",
                "findings_count": 0,
            })

    # Section 3: graph parse failures (auto-skip if no dekspec content tree)
    if dekspec_dir.exists():
        try:
            graph = SpecGraph.load(repo_root, dekspec_root=args.dekspec_root)
            failures = list(graph.parse_failures())
            ir_count = sum(1 for _ in graph.all())
            status = "clean" if not failures else "critical"
            if failures:
                worst_severity = _worse(worst_severity, "critical")
            sections.append({
                "name": "graph parse",
                "status": status,
                "summary": f"ir_count={ir_count} parse_failures={len(failures)}",
                "findings_count": len(failures),
            })
        except Exception as e:
            sections.append({
                "name": "graph parse",
                "status": "skipped",
                "summary": f"errored: {type(e).__name__}: {str(e)[:120]}",
                "findings_count": 0,
            })
    else:
        sections.append({
            "name": "graph parse",
            "status": "skipped",
            "summary": f"no dekspec content tree at {dekspec_dir}",
            "findings_count": 0,
        })

    exit_code = {"clean": 0, "advisory": 0, "warning": 1, "critical": 2}[worst_severity]

    if args.json:
        print(json.dumps({
            "overall_status": worst_severity,
            "exit_code": exit_code,
            "repo_root": str(repo_root),
            "dekspec_root": args.dekspec_root,
            "sections": sections,
        }, indent=2, default=str))
        return exit_code

    print(f"DekSpec doctor — {repo_root}")
    print(f"Overall: {_status_glyph(worst_severity)} {worst_severity.upper()}")
    print()
    print(f"  {'section':<20} {'status':<10} summary")
    print(f"  {'-' * 20} {'-' * 10} {'-' * 40}")
    for s in sections:
        glyph = _status_glyph(s["status"])
        print(f"  {s['name']:<20} {glyph} {s['status']:<8} {s['summary']}")
    print()
    if worst_severity == "clean":
        print("All clean. No further action needed.")
    elif worst_severity == "advisory":
        print("Advisory findings present (P3 only; non-blocking). Run:")
        for s in sections:
            if s["status"] == "advisory":
                print(f"  - `dekspec {_remedy_command(s['name'])}` for detail")
    elif worst_severity == "warning":
        print("Warnings present. Run:")
        for s in sections:
            if s["status"] == "warning":
                print(f"  - `dekspec {_remedy_command(s['name'])}` for detail")
    else:
        print("Critical issues present. Run:")
        for s in sections:
            if s["status"] == "critical":
                print(f"  - `dekspec {_remedy_command(s['name'])}` for detail")
    print()
    print(
        "Claude plugin + skills: install with `claude plugin install dekspec@dekspec` "
        "(update form: `claude plugin update dekspec@dekspec`) inside Claude Code."
    )
    return exit_code


def _worse(current: str, candidate: str) -> str:
    rank = {"clean": 0, "advisory": 1, "warning": 2, "critical": 3}
    return current if rank[current] >= rank[candidate] else candidate


def _status_glyph(status: str) -> str:
    return {
        "clean": "✓", "advisory": "~", "warning": "!", "critical": "✗", "skipped": "·",
    }.get(status, "?")


def _remedy_command(section_name: str) -> str:
    return {
        "verify-vendored": "audit doctor --json",
        "audit linkage": "audit linkage",
        "graph parse": "audit linkage  # parse failures surface as LX-PARSE findings",
        "plugin version": "# re-install: bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec/main/scripts/install.sh)",
    }.get(section_name, "doctor --json")


def _check_plugin_version_drift() -> tuple[str, str] | None:
    """Detect drift between the CLI version + the Claude Code plugin version.

    Returns one of:
      - `("ok", "<summary>")` — CLI version + plugin version agree.
      - `("drift", "<summary>")` — versions disagree; advisory finding.
      - `("skip", "<summary>")` — plugin not installed (or unreadable).
      - `None` — checker is unavailable; doctor section is omitted.

    The plugin's installed-version directory shape per Claude Code:
      `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`
    For dekspec: `~/.claude/plugins/cache/dekspec/dekspec/<version>/`.

    `dekspec.__version__` is the CLI version. When the two disagree the
    operator likely installed one surface and forgot the other; re-running
    `bash scripts/install.sh` syncs them.
    """
    try:
        import dekspec as _dekspec
        cli_version = getattr(_dekspec, "__version__", None)
        if not cli_version:
            return None
        plugin_cache = Path.home() / ".claude" / "plugins" / "cache" / "dekspec" / "dekspec"
        if not plugin_cache.is_dir():
            return ("skip", "plugin not installed under ~/.claude/plugins/cache/dekspec/dekspec/")
        version_dirs = [p.name for p in plugin_cache.iterdir() if p.is_dir()]
        if not version_dirs:
            return ("skip", "plugin cache dir exists but holds no version subdirs")

        # Pick the highest version SEMVER-wise, not lexicographically. A lex
        # sort ranks "0.99.0" above "0.106.0" (because "9" > "1" at the second
        # component), so a cache that still holds older subdirs left behind by
        # `claude plugin update` would report false drift (ds-ro98). Parse each
        # dir name into an int tuple; unparseable names (e.g. a git SHA) sort
        # last so a real X.Y.Z release always wins when present.
        def _semver_key(name: str) -> tuple[int, tuple[int, ...]]:
            try:
                return (1, tuple(int(p) for p in name.split(".")))
            except ValueError:
                return (0, ())

        plugin_version = max(version_dirs, key=_semver_key)
        if plugin_version == cli_version:
            return ("ok", f"CLI={cli_version} plugin={plugin_version}")
        return (
            "drift",
            f"CLI={cli_version} plugin={plugin_version} — re-install both for parity",
        )
    except Exception as exc:
        return ("skip", f"check failed: {type(exc).__name__}: {str(exc)[:80]}")


def _add_validate_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "validate",
        help="Quick parse-only check (no persistence side effect).",
        description=(
            "Parse an artifact and surface parse warnings + schema validation "
            "errors. No run dir is created, no IR is persisted, no events are "
            "written. Useful for editor integration / pre-commit hooks."
        ),
    )
    p.add_argument(
        "path", help="Path to the artifact markdown file (any of the 9 IR kinds)."
    )
    p.add_argument(
        "--kind",
        choices=[
            "ic", "ae", "ws", "adr", "ib", "intent", "mission",
            "sp", "contextspec", "vision", "glossary", "constitution",
        ],
        help=(
            "Override filename-based kind inference. Useful when the artifact "
            "lives at a non-conventional path (e.g., a scratch copy in /tmp, "
            "or when validating a Constitution at a non-`constitution.md` name)."
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit warnings as JSON instead of formatted text.",
    )
    p.set_defaults(func=cmd_validate)


def cmd_validate(args: argparse.Namespace) -> int:
    src = Path(args.path).resolve()
    if not src.exists():
        print(f"Error: source not found: {src}", file=sys.stderr)
        return 2
    artifact_kind = getattr(args, "kind", None) or _detect_artifact_kind(src.name)
    if artifact_kind is None:
        print(
            f"Error: cannot detect artifact kind from filename '{src.name}'. "
            f"Pass --kind to override.",
            file=sys.stderr,
        )
        return 2
    parsers = {
        "ic": parse, "ae": parse_ae, "ws": parse_ws, "adr": parse_adr,
        "ib": parse_ib, "intent": parse_intent, "mission": parse_mission,
        "sp": parse_security_profile,
        "contextspec": parse_context_spec,
        "vision": parse_vision, "glossary": parse_glossary,
        "constitution": parse_constitution,
    }
    parse_fn = parsers[artifact_kind]
    error_classes = (
        ICParseError, AEParseError, WSParseError, ADRParseError,
        IBParseError, IntentParseError, MissionParseError,
        SPParseError,
        CSParseError,
        VisionParseError, GlossaryParseError,
        ConstitutionParseError,
    )
    try:
        ir = parse_fn(src)
    except error_classes as e:
        if args.json:
            print(json.dumps({"ok": False, "error": str(e),
                              "error_type": type(e).__name__}))
        else:
            print(f"Parse error in {src}:\n{e}", file=sys.stderr)
        return 4
    warnings = ir.get("parse_warnings", [])
    if args.json:
        print(json.dumps({
            "ok": True,
            "id": ir.get("id"),
            "status": ir.get("status"),
            "kind": artifact_kind,
            "warnings": warnings,
        }, default=str))
    else:
        print(
            f"OK — {ir.get('id', '?')} ({ir.get('status', '?')}, kind={artifact_kind}). "
            f"{len(warnings)} parse warning(s)."
        )
        for w in warnings:
            print(f"  [{w.get('severity', '?')}] {w.get('field', '?')}: {w.get('reason', '')}")
    return 0


def _add_resource_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "resource",
        help="Resolve a wheel-vendored asset (template / methodology doc) to a usable path or content.",
        description=(
            "Resolve and emit a dekspec-vendored asset. Consumer-fs copies "
            "(`dekspec/templates/<name>.md`, `dekspec/<doc>.md`) override the "
            "wheel `_vendored/` fallback when present. Used by skills + agents "
            "so they work after a wheel-only `pip install dekspec` without "
            "requiring the consumer to first run `scripts/install-dekspec.sh` "
            "(INT-097)."
        ),
    )
    p.add_argument(
        "kind", choices=["template", "doc"],
        help="Kind of resource to resolve. `template` reads from "
        "templates/<name>.md; `doc` reads from docs/<name>.md (methodology + "
        "operating-guide family).",
    )
    p.add_argument(
        "name",
        help="Resource name. Examples: `intent` (for templates/intent-template.md), "
        "`operating-guide` (for docs/dekspec-operating-guide.md). The "
        "`-template` suffix and `dekspec-` prefix are appended automatically.",
    )
    p.add_argument(
        "--at",
        help="Consumer repo root (default: cwd). Consumer-fs override at "
        "<at>/dekspec/templates/ or <at>/dekspec/ takes precedence over the "
        "wheel fallback.",
    )
    p.add_argument(
        "--path-only", action="store_true", dest="path_only",
        help="Print only the resolved absolute path (default: print the file "
        "content). Useful for shell-side composition: "
        "`TEMPLATE=$(dekspec resource template intent --path-only)`.",
    )
    p.set_defaults(func=cmd_resource)


def cmd_resource(args: argparse.Namespace) -> int:
    """`dekspec resource <kind> <name>` — resolve a wheel-vendored asset
    (template or methodology doc) and emit either its path or content.
    Consumer-fs override wins over the wheel `_vendored/` fallback per the
    INT-097 self-contained-wheel resolution rule.

    Used by skills + agents so they work after a wheel-only
    `pip install dekspec` without requiring `scripts/install-dekspec.sh`.
    """
    from .vendoring import resolve_template, resolve_doc

    name = args.name.strip()
    if not name:
        print("error: resource name is empty", file=sys.stderr)
        return 2
    # Templates: strip a `-template` suffix the caller may have included so
    # both `intent` and `intent-template` resolve. The resolver normalizes
    # the `.md` suffix internally.
    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    if args.kind == "template":
        if not name.endswith("-template"):
            name = f"{name}-template"
        resolved = resolve_template(name, repo_root=repo_root)
    else:
        resolved = resolve_doc(name, repo_root=repo_root)
    if resolved is None:
        print(
            f"error: {args.kind} {args.name!r} not found in consumer-fs "
            f"({repo_root}/dekspec/) or wheel `_vendored/`",
            file=sys.stderr,
        )
        return 1
    if args.path_only:
        print(str(resolved))
    else:
        try:
            sys.stdout.write(resolved.read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"error: failed to read {resolved}: {exc}", file=sys.stderr)
            return 1
    return 0


def _add_init_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "init",
        help="Scaffold a new dekspec/ tree in the current repo.",
        description=(
            "Create the conventional dekspec subdirectories, empty index files, "
            "and a starter AGENTS.md note. Idempotent — existing files are "
            "preserved unless --force is passed."
        ),
    )
    p.add_argument(
        "--at",
        help="Path to the consumer repo (default: current working directory).",
    )
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Subdirectory to create relative to repo root (default: dekspec).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help=(
            "Overwrite existing index files / AGENTS.md placeholder, AND "
            "overwrite an existing `.dekspec/config.yaml`."
        ),
    )
    p.add_argument(
        "--methodology",
        choices=["lite", "team", "full"],
        help="Methodology profile for `.dekspec/config.yaml` (non-interactive).",
    )
    p.add_argument(
        "--profile",
        choices=["lite", "full"],
        default="full",
        help=(
            "DekSpec methodology profile for the scaffold (default: full). "
            "`full` scaffolds the complete dekspec/ tree. `lite` scaffolds a "
            "minimal tree — Constitution + Intent index only, no "
            "architecture-elements/, working-specs/, interface-contracts/, "
            "missions/, or impl-briefs/ directories — and persists "
            "`methodology_profile: lite` to `.dekspec/config.yaml`."
        ),
    )
    p.set_defaults(func=cmd_init)


_INIT_SUBDIRS = (
    "adrs",
    "architecture-elements",
    "working-specs",
    "interface-contracts",
    "impl-briefs/queued",
    "impl-briefs/active",
    "impl-briefs/completed",
    "intents",
    "missions",
    "security-profiles",
    "audits",
    "divergences",
    "provisional",
)

_INIT_INDEXES = (
    ("adr-index.md", "# ADR Index\n\n*Architecture Decision Records.*\n\n_None yet — author the first one with `/write-adr`._\n"),
    ("architecture-elements-index.md", "# Architecture Elements Index\n\n*The architectural slices of this system.*\n\n_None yet — author the first one with `/write-ae`._\n"),
    ("working-spec-index.md", "# Working Spec Index\n\n*Behavioral specs.*\n\n_None yet — author the first one with `/write-ws`._\n"),
    ("interface-contract-index.md", "# Interface Contract Index\n\n*Provider/Consumer wire contracts.*\n\n_None yet — author the first one with `/write-ic`._\n"),
    ("intent-index.md", "# Intent Index\n\n*Captured engineer intent.*\n\n_None yet — author the first one with `/write-intent`._\n"),
    ("mission-index.md", "# Mission Index\n\n*Cross-Intent coordination.*\n\n_None yet — author the first one with `/write-mission`._\n"),
)

# Audit-profile config files scaffolded under the full profile only. The
# spec-fitness-functions registry is the per-repo sibling-SSoT invariant
# catalog consumed by `/doctor` Stage 2 Phase 2J (inlined fidelity body). The
# placeholder is registry-shaped but empty; consumers hand-author
# invariants as their domain accumulates duplicable facts.
_INIT_AUDITS_FITNESS_FUNCTIONS = """\
<!--
  Sibling-SSoT Fitness Functions registry
  Consumed by `/doctor` Stage 2 Phase 2J (inlined fidelity body).

  Each invariant declares a domain fact whose canonical home should be the
  only place that fact is stated. The audit greps the configured scopes and
  emits findings when copies of the fact appear without citing the canonical
  home, when the fact's expected count drifts, or when forbidden phrasings
  reappear.

  Per-invariant schema:
    id:                      F-NN (sequential)
    fact:                    one-line plain-English description
    canonical_home:          path:section where the fact is defined
    pattern:                 grep-compatible regex
    scopes:                  list of glob roots to scan
    expected_count: N        bounded-occurrence rule (miscount = IMPORTANT)
    unbounded_with_citation: non-Amendment-Log hits must cite canonical_home
    forbidden: true          non-Amendment-Log hits are CRITICAL
    citation_distance_lines: optional integer (default 5)
    severity:                CRITICAL | IMPORTANT | MINOR

  Hand-author entries below and re-run `/doctor`.
  An empty registry is valid — Phase 2J no-ops and emits zero findings.
-->

# Sibling-SSoT Fitness Functions

_No invariants registered yet._
"""

_INIT_AUDIT_FILES = (
    ("audits/spec-fitness-functions.md", _INIT_AUDITS_FITNESS_FUNCTIONS),
)

# Framework-required L0/L1 singletons. Per ds-init-does-not-seed-l0-l1-singletons-dgh:
# every consumer is expected to have these files; audits + skills + the operating
# guide all assume they exist. Stubs are structurally parseable (so `dekspec
# doctor` on a fresh init remains CLEAN) but contain no real content — consumers
# author the real text via `/write-sv` and `/write-ggc`.
_INIT_SINGLETON_SYSTEM_VISION = """\
<!--
  System Vision — placeholder authored by `dekspec init`.
  L0 root document. Author the real content with `/write-sv`.
  This stub is structurally minimal but parser-valid so `dekspec doctor`
  stays CLEAN on a fresh tree.
-->

# System Vision: Untitled

## Status

TODO

## Created

2026-05-17

## Modified

2026-05-17

## What This Is

_Not yet authored. Run `/write-sv` to draft the L0 root._

## Who This Is For

_Not yet authored._

## Why This Exists

_Not yet authored._

## What Success Looks Like

- _Not yet authored — add bulleted success criteria via `/write-sv`._

## What We Are Not Building

- _Not yet authored — add bulleted non-goals via `/write-sv`._
"""

_INIT_SINGLETON_GLOSSARY = """\
<!--
  Domain Glossary — placeholder authored by `dekspec init`.
  Author and maintain with `/write-ggc`. Empty `terms` array is valid;
  populate as the corpus grows.
-->

# Domain Glossary

_No terms yet. Add the first one with `/write-ggc`._
"""

_INIT_SINGLETON_GUIDANCE = """\
<!--
  Guidance and Corrections — placeholder authored by `dekspec init`.
  Append corrections + standing guidance with `/write-ggc`.
  Not parsed by the IR pipeline today; it's a free-form companion to the
  Domain Glossary that consumers + agents read at session-load time.
-->

# Guidance and Corrections

_No corrections logged yet._
"""

_INIT_SINGLETONS = (
    ("system-vision.md", _INIT_SINGLETON_SYSTEM_VISION),
    ("domain-glossary.md", _INIT_SINGLETON_GLOSSARY),
    ("guidance-and-corrections.md", _INIT_SINGLETON_GUIDANCE),
)

# Constitution L0 singleton — placeholder authored by `dekspec init`.
# Scaffolded under the `lite` profile (MSN-006 / INT-067 / IB-115): the lite
# methodology grounds a solo engineer's single-repo work in the Constitution
# rather than a deep AE/WS/IC graph. The stub is structurally minimal but
# parser-valid (8 articles in canonical order; empty ref-arrays in Articles
# 4 + 7 so no dangling ADR/AE references) so `dekspec validate` /
# `dekspec doctor` accept a fresh lite tree. Consumers author the real text
# via `/write-constitution`.
_INIT_SINGLETON_CONSTITUTION = """\
<!--
  Constitution — placeholder authored by `dekspec init`.
  L0 root document. Author the real content with `/write-constitution`.
  This stub is structurally minimal but parser-valid (8 articles in
  canonical order) so `dekspec doctor` stays CLEAN on a fresh tree.
-->

# Constitution: Untitled

## Status

TODO

## Created

2026-05-21

## Modified

2026-05-21

## Article 1: Project Identity

**Summary:** Not yet authored. Run `/write-constitution` to draft the L0 Constitution.

**See Also:** dekspec/system-vision.md

## Article 2: Technology Stack

_Not yet authored — pin the standing technology choices via `/write-constitution`._

## Article 3: Quality Standards

_Not yet authored — name the standing quality gates via `/write-constitution`._

## Article 4: Architecture Principles

_Not yet authored — cite the load-bearing ADRs via `/write-constitution`._

## Article 5: Development Workflow

_Not yet authored — describe the standing workflow contract via `/write-constitution`._

## Article 6: Model Configuration

_Not yet authored — pin the model-tier policy via `/write-constitution`._

## Article 7: Boundaries

_Not yet authored — name the project's non-goal boundaries via `/write-constitution`._

## Article 8: Amendments

_No amendments yet._
"""

# --- Profile-conditional scaffold subsets (MSN-006 / INT-067 / IB-115) ----- #
# The `lite` profile scaffolds a minimal dekspec/ tree: a solo engineer
# governing single-repo work uses the Constitution + Intent index, not a
# deep AE/WS/IC/Mission/IB graph. The `full` profile is the default and
# scaffolds the complete tree exactly as before — the lite branch is purely
# additive.
_INIT_LITE_SUBDIRS = (
    "adrs",
    "intents",
    "divergences",
    "provisional",
)

_INIT_LITE_INDEX_NAMES = frozenset({"adr-index.md", "intent-index.md"})

# The L0 singletons scaffolded under `lite`: System Vision + Constitution
# anchor a solo engineer's lite governance. Domain Glossary +
# Guidance-and-Corrections stay full-profile-only — the lite tree omits
# them to keep the scaffold minimal.
_INIT_LITE_SINGLETON_NAMES = frozenset({"system-vision.md"})

_INIT_AGENTS_PLACEHOLDER = """\
<!--
  AGENTS.md — placeholder authored by `dekspec init`.
  Re-generate this file with `dekspec aggregate agents-md` once your
  spec graph contains LOCKED or ACCEPTED artifacts.
-->

# AGENTS.md

This file is the compiled context surface for AI agents working in this repo.
It will be regenerated by `dekspec aggregate agents-md` after artifacts land.

Until then, read the methodology via `dekspec resource doc operating-guide`
(resolves from the wheel; falls back to `dekspec/dekspec-operating-guide.md`
if your repo has vendored a customized copy).
"""


# CLAUDE.md placeholder — scaffold for the project-rules surface Claude
# Code (and similar harnesses) read on session start. Carries the
# DekSpec Guardrails section with the load-bearing authoring rules so
# every fresh consumer repo gets the discipline by default (R1 of
# INT-091 / ds-6ujt — the provisional-first authoring rule).
#
# Consumers MAY freely edit this file; `dekspec init` only writes it
# when absent (idempotent) unless --force is passed.
_INIT_CLAUDE_MD_PLACEHOLDER = """\
<!--
  CLAUDE.md — placeholder authored by `dekspec init`.
  This is the project-rules surface read by Claude Code (and similar
  AI coding harnesses) on session start. Edit freely; `dekspec init`
  re-writes this file only when absent.
-->

# Project rules

## DekSpec Guardrails

- **Provisional-first authoring.** NEW Intents (INT-NNN) and NEW Missions (MSN-NNN) ALWAYS start under `dekspec/provisional/<slug>/` via `dekspec repo cow-stage <slug>` (or by hand-creating the directory + `INT-provisional-<slug>.md` skeleton). Canonical IDs (INT-NNN / MSN-NNN) are allocated only at hand-promote time, not at draft time. Walk DRAFT → PROPOSED → ACCEPTED in provisional; promote via `dekspec.promote.plan_promotion(incubation_dir, dekspec_dir)` + `apply_promotion(steps, incubation_dir, repo_root)` Python helpers once the family is ACCEPTED. This rule prevents collision on the canonical ID space when multiple authors draft concurrently and keeps the canonical tree free of half-baked drafts.
- **No Specless Edits.** Before making any source-code edit that introduces new capability or modifies existing behavior, halt and check whether a DekSpec artifact (Intent, Mission, ADR, active Implementation Brief under `dekspec/`) should be authored or updated first. If yes, surface 1–3 context-aware artifact-action suggestions to the engineer; do not edit code until the spec context is established or explicitly deferred. Use `/dekspec:spec-mode --on` to toggle this guardrail on, `--off` to defer it for an exploratory session.
- **Library-side audit is the dogfood gate.** Run `dekspec audit doctor --at .` before any commit that touches `dekspec/` artifacts. CLEAN is the target; ADVISORY (P3-only findings) is tolerated for in-flight provisional work. P0 / P1 / P2 findings must be cleared before merge.
- **LOCKED artifacts are immutable.** Never edit an artifact whose Status is `LOCKED`. Unlock to `PROPOSED` first via the `--unlock` flag on the artifact's authoring skill, then re-lock via `--lock` after the edit cycle.

## Methodology reference

Resolve any vendored doc via `dekspec resource doc <name>` (consumer-fs
copy under `dekspec/` overrides the wheel fallback when present):

- `dekspec resource doc operating-guide` — master operating document.
- `dekspec resource doc quick-reference` — 5–10 minute onboarding.
- `dekspec/system-vision.md` — the project's L0 root (project-authored,
  always lives in the consumer tree; not a vendored asset).
"""


def _is_beads_rust_br(br_path: str) -> bool:
    """Identity check: does this `br` look like the beads-rust binary?

    The 2-letter name `br` collides with brotli's CLI (`br` on
    Debian/Ubuntu/Fedora when `brotli` is installed). A bare
    `shutil.which("br")` would happily resolve brotli and let the
    precheck pass — and DekSpec's bead-aware flows would then fail
    downstream with a confusing error. This helper runs `br --help`
    with a short timeout and looks for the substring `beads` in the
    combined stdout+stderr output (case-insensitive). Returns False on
    any subprocess error, timeout, or output that does not match.
    """
    try:
        proc = subprocess.run(
            [br_path, "--help"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    combined = (proc.stdout or "") + (proc.stderr or "")
    return "beads" in combined.lower()


def _init_dep_precheck() -> int:
    """Verify host-environment dependencies before scaffolding.

    Returns 0 when both required dependencies (`git` and `br`) are on
    PATH AND `br` is verified to be beads-rust (not brotli); returns 2
    with a checklist printed to stderr when either is missing or `br`
    fails the identity check. There is no override flag and no
    environment escape hatch: DekSpec's authoring + audit pipeline
    depends on git, and its coding loop and bead-failure-class audit
    rule depend on `br` end-to-end. Operating without either is
    unsupported.
    """
    failures: list[str] = []

    if shutil.which("git") is None:
        failures.append(
            "  ✗ git not found on PATH.\n"
            "    DekSpec's authoring + audit + executor flows all assume git "
            "is available.\n"
            "    Install git from https://git-scm.com/downloads, then re-run."
        )

    br_path = shutil.which("br")
    if br_path is None:
        failures.append(
            "  ✗ br (beads-rust) not found on PATH.\n"
            "    DekSpec's coding loop and the T-BEAD-FAILURE-CLASS-VALID "
            "audit rule are bead-aware end-to-end and read `.beads/issues.jsonl`.\n"
            "    Install br from https://github.com/Dicklesworthstone/beads_rust"
            " (releases publish prebuilt linux + macOS binaries), then re-run."
        )
    elif not _is_beads_rust_br(br_path):
        failures.append(
            f"  ✗ br on PATH at {br_path} does not look like beads-rust.\n"
            "    The 2-letter binary name `br` is also used by brotli (the "
            "compression tool) on many Linux distributions; DekSpec needs the "
            "beads-rust `br`, not brotli's.\n"
            "    Install beads-rust from https://github.com/Dicklesworthstone/beads_rust"
            " and ensure its `br` resolves first on PATH, then re-run."
        )

    if failures:
        print("Dependency precheck — required dependencies missing:", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 2

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    rc = _init_dep_precheck()
    if rc != 0:
        return rc

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    dekspec_dir = repo_root / args.dekspec_root

    # Profile selects the scaffold scope (MSN-006 / INT-067 / IB-115).
    # `full` (default / --profile full) scaffolds the complete tree exactly
    # as before; `lite` scaffolds a minimal tree — Constitution + Intent
    # index only. The lite branch is purely additive: the `full` path below
    # is byte-identical to the pre-IB-115 behaviour.
    profile = getattr(args, "profile", None) or "full"
    lite = profile == "lite"

    subdirs = _INIT_LITE_SUBDIRS if lite else _INIT_SUBDIRS
    # The full profile keeps the historical singleton set; the lite profile
    # scaffolds only System Vision (Constitution dependency) plus the
    # Constitution itself.
    singletons: tuple[tuple[str, str], ...] = (
        tuple(
            (name, content)
            for name, content in _INIT_SINGLETONS
            if name in _INIT_LITE_SINGLETON_NAMES
        )
        + (("constitution.md", _INIT_SINGLETON_CONSTITUTION),)
        if lite
        else _INIT_SINGLETONS
    )

    created: list[str] = []
    skipped: list[str] = []

    for sub in subdirs:
        d = dekspec_dir / sub
        if d.exists():
            skipped.append(f"dir  {d.relative_to(repo_root)}")
            continue
        d.mkdir(parents=True, exist_ok=True)
        gitkeep = d / ".gitkeep"
        gitkeep.touch()
        created.append(f"dir  {d.relative_to(repo_root)}")

    for filename, content in _INIT_INDEXES:
        # Under the lite profile only the Constitution-relevant indexes are
        # scaffolded — no AE / WS / IC / Mission index files.
        if lite and filename not in _INIT_LITE_INDEX_NAMES:
            continue
        p = dekspec_dir / filename
        if p.exists() and not args.force:
            skipped.append(f"file {p.relative_to(repo_root)}")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        created.append(f"file {p.relative_to(repo_root)}")

    # Audit-profile config files. Full profile only — the lite scaffold
    # omits audit registry surfaces since /doctor
    # Phase 2J is full-profile machinery.
    if not lite:
        for filename, content in _INIT_AUDIT_FILES:
            p = dekspec_dir / filename
            if p.exists() and not args.force:
                skipped.append(f"file {p.relative_to(repo_root)}")
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            created.append(f"file {p.relative_to(repo_root)}")

    # L0/L1 singletons. Under `full`: system-vision, domain-glossary,
    # guidance-and-corrections. Under `lite`: system-vision + constitution.
    # Idempotent by design: never overwrites real content unless --force is
    # passed. Per ds-init-does-not-seed-l0-l1-singletons-dgh.
    for filename, content in singletons:
        p = dekspec_dir / filename
        if p.exists() and not args.force:
            skipped.append(f"file {p.relative_to(repo_root)}")
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        created.append(f"file {p.relative_to(repo_root)}")

    agents = repo_root / "AGENTS.md"
    if agents.exists() and not args.force:
        skipped.append(f"file {agents.relative_to(repo_root)}")
    else:
        agents.write_text(_INIT_AGENTS_PLACEHOLDER, encoding="utf-8")
        created.append(f"file {agents.relative_to(repo_root)}")

    # CLAUDE.md — project-rules surface for Claude Code sessions. Carries
    # the DekSpec Guardrails (provisional-first, no-specless-edits,
    # dogfood-gate, locked-immutable) so every fresh consumer repo gets
    # the discipline by default (R1 of INT-091 / ds-6ujt).
    claude_md = repo_root / "CLAUDE.md"
    if claude_md.exists() and not args.force:
        skipped.append(f"file {claude_md.relative_to(repo_root)}")
    else:
        claude_md.write_text(_INIT_CLAUDE_MD_PLACEHOLDER, encoding="utf-8")
        created.append(f"file {claude_md.relative_to(repo_root)}")

    # --- .dekspec/config.yaml — the executor + methodology cleavage (INT-018) ---
    config_rc, config_warning = _init_write_config(args, repo_root, created, skipped)
    if config_rc != 0:
        return config_rc

    print(f"Initialized dekspec tree at {dekspec_dir}")
    if created:
        print(f"\nCreated ({len(created)}):")
        for line in created:
            print(f"  + {line}")
    if skipped:
        print(f"\nSkipped ({len(skipped)}, already present; use --force to overwrite indexes/AGENTS.md):")
        for line in skipped:
            print(f"  . {line}")
    next_steps = [
        "\nNext steps:",
        "  1. Install the CLI + Claude Code plugin (single-command, pins both at the same version):",
        "       bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec/main/scripts/install.sh)",
        "  2. Draft the L0 singletons: `/write-sv`, `/write-ggc`.",
        "  3. Author your first ADR / AE / WS via the matching skill (e.g., `/write-adr`).",
        "  4. Run `dekspec aggregate agents-md` once you have LOCKED + ACCEPTED artifacts.",
    ]
    if config_warning is not None:
        next_steps.append(
            "  5. Write `.dekspec/config.yaml` — re-run `dekspec init` with "
            "--executor / --endpoint / --methodology (no config was written)."
        )
    print("\n".join(next_steps))
    return 0


def _init_resolve_answer(
    flag_value: str | None,
    prompt: str,
    choices: tuple[str, ...],
    default: str,
) -> str:
    """Resolve one init Q&A answer: flag wins; else prompt a TTY; else default.

    Called only after the non-TTY-without-flags guard, so when `flag_value`
    is None here, stdin is guaranteed to be a TTY.
    """
    if flag_value is not None:
        return flag_value
    choice_str = "/".join(
        f"[{c}]" if c == default else c for c in choices
    )
    while True:
        raw = input(f"{prompt} ({choice_str}): ").strip().lower()
        if not raw:
            return default
        if raw in choices:
            return raw
        print(f"  Please choose one of: {', '.join(choices)}")


def _init_write_config(
    args: argparse.Namespace,
    repo_root: Path,
    created: list[str],
    skipped: list[str],
) -> tuple[int, str | None]:
    """Write `.dekspec/config.yaml` from init flags or a 2-question Q&A.

    Returns `(rc, warning)`:

    - `rc` is 0 on success / skip, non-zero on a hard error (a partial
      flag set in non-TTY, --executor dekfactory missing --endpoint, or a
      schema-validation failure).
    - `warning` is a non-None message when the config write was skipped
      because stdin is not a TTY and NO config flags were supplied — the
      tree still scaffolds (rc=0) but the engineer is told, clearly, that
      no config was written and which flags to pass. The config is NOT
      silently defaulted.
    """
    from . import dekspec_config

    cfg_path = dekspec_config.config_path(repo_root)
    if cfg_path.exists() and not args.force:
        skipped.append(f"file {cfg_path.relative_to(repo_root)}")
        return 0, None

    methodology_flag = getattr(args, "methodology", None)

    # `--profile lite` (MSN-006 / INT-067 / IB-115) persists the lite
    # methodology profile to `.dekspec/config.yaml`. The flag is a
    # self-sufficient non-interactive shorthand: it supplies the
    # methodology answer (`lite`). An explicit `--methodology` that
    # contradicts `--profile lite` is a hard error.
    if getattr(args, "profile", None) == "lite":
        if methodology_flag is not None and methodology_flag != "lite":
            print(
                "Error: --profile lite implies --methodology lite; "
                f"--methodology {methodology_flag} contradicts it. "
                "Drop one of the two flags.",
                file=sys.stderr,
            )
            return 2, None
        methodology_flag = "lite"

    if methodology_flag is None and not sys.stdin.isatty():
        msg = (
            "`dekspec init` did not write `.dekspec/config.yaml`: stdin is not "
            "a TTY (cannot run the interactive Q&A) and --methodology was not "
            "supplied.\n"
            "  Pass it non-interactively: --methodology <lite|team|full>."
        )
        print(f"Note: {msg}", file=sys.stderr)
        return 0, msg

    methodology = _init_resolve_answer(
        methodology_flag,
        "Methodology profile — how much DekSpec ceremony does the team apply?",
        ("lite", "team", "full"),
        "full",
    )

    config_doc = {
        "schema_version": dekspec_config.CONFIG_SCHEMA_VERSION,
        "methodology_profile": methodology,
    }
    try:
        dekspec_config.write_config(repo_root, config_doc, force=True)
    except dekspec_config.DekspecConfigError as err:
        print(f"Error: could not write {cfg_path}: {err}", file=sys.stderr)
        return 2, None
    created.append(f"file {cfg_path.relative_to(repo_root)}")
    return 0, None


# --------------------------------------------------------------------------- #
# config — get / set keys in `.dekspec/config.yaml`
# --------------------------------------------------------------------------- #
# config — get / set keys in `.dekspec/config.yaml`
# --------------------------------------------------------------------------- #


def _add_config_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "config",
        help="Read / write keys in the per-repo `.dekspec/config.yaml`.",
        description=(
            "Inspect or edit the per-repo DekSpec config. `dekspec config get "
            "<key>` prints a value; `dekspec config set <key> <value>` writes "
            "it (atomic, JSON-Schema-validated). Recognised keys: schema_version, "
            "methodology_profile (alias: profile), repo.scope, issue_tracker, "
            "ephemeral_scratch_dir, glossary_path, triage_labels.hitl, "
            "triage_labels.afk, triage_labels.buckets."
        ),
    )
    c_sub = p.add_subparsers(dest="config_command", metavar="<config-command>")

    p_get = c_sub.add_parser("get", help="Print the value of a dotted config key.")
    p_get.add_argument("key", help="Dotted key, e.g. methodology_profile.")
    p_get.add_argument(
        "--at", help="Repo root (default: current working directory)."
    )
    p_get.set_defaults(func=cmd_config_get)

    p_set = c_sub.add_parser(
        "set", help="Set a dotted config key (atomic, schema-validated)."
    )
    p_set.add_argument("key", help="Dotted key, e.g. methodology_profile.")
    p_set.add_argument("value", help="New value.")
    p_set.add_argument(
        "--at", help="Repo root (default: current working directory)."
    )
    p_set.set_defaults(func=cmd_config_set)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


def cmd_config_get(args: argparse.Namespace) -> int:
    from . import dekspec_config

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    # `profile` is the effective-methodology-profile query (MSN-006 / IB-112):
    # it resolves the active profile via `get_profile()`, which returns the
    # backwards-compatible `full` default when no `.dekspec/config.yaml`
    # exists — it never errors on a missing config. The raw config key
    # `methodology_profile` keeps the standard get_key behaviour (errors when
    # unset). The MSN-006 Mission Verification predicate runs `config get
    # profile`, so this path must resolve cleanly against a config-less repo.
    if args.key == "profile":
        try:
            print(dekspec_config.get_profile(repo_root))
        except dekspec_config.DekspecConfigError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 2
        return 0
    try:
        value = dekspec_config.get_key(repo_root, args.key)
    except dekspec_config.DekspecConfigError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2
    print("null" if value is None else value)
    return 0


def cmd_config_set(args: argparse.Namespace) -> int:
    from . import dekspec_config

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    try:
        path = dekspec_config.set_key(repo_root, args.key, args.value)
    except dekspec_config.DekspecConfigError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2
    print(f"Set {args.key} in {path}")
    return 0


def _add_graph_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "graph",
        help="Inspect or export the spec graph (the union of all parsed IRs).",
        description=(
            "Graph commands. Today: export only — walks the SpecGraph and "
            "dumps every IR as a single JSON document for downstream tooling."
        ),
    )
    g_sub = p.add_subparsers(dest="graph_command", metavar="<graph-command>")

    p_export = g_sub.add_parser(
        "export",
        help="Walk the spec graph and dump every IR as a single JSON document.",
    )
    p_export.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p_export.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Path to the DekSpec content tree relative to repo root (default: dekspec).",
    )
    p_export.add_argument(
        "--output",
        help="Write JSON to PATH instead of stdout.",
    )
    p_export.add_argument(
        "--include",
        default="ALL",
        help=(
            "Comma-separated artifact kinds to include "
            "(any of AE,ADR,WS,IC,IB,INT,MSN,GLOSSARY,VISION). "
            "Default: ALL (every kind)."
        ),
    )
    p_export.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON (indent=2). Default: compact (one IR per line). JSON format only.",
    )
    p_export.add_argument(
        "--format",
        choices=("text", "json", "mermaid", "dot"),
        default="text",
        help=(
            "Output format. `text` (default): a human-readable CLI render "
            "grouped by artifact kind. `json`: the full IR document (for "
            "tooling — pass this explicitly when piping). `mermaid` / `dot`: "
            "a node + edge dependency graph using the ADR-015 forward-link "
            "model, for visualization."
        ),
    )
    p_export.set_defaults(func=cmd_graph_export)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


def _graph_edges(graph: Any, irs: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Forward-link edges among the exported node set (ADR-015 model).

    Edges to artifacts outside the filtered `irs` set are dropped so the
    rendered graph stays self-contained with `--include`.
    """
    node_ids = {ir.get("id", "") for ir in irs}
    edges: list[tuple[str, str]] = []
    for ir in irs:
        src = ir.get("id", "")
        for tgt in graph.forward_links_of(src):
            if tgt in node_ids:
                edges.append((src, tgt))
    return edges


def _mermaid_node_id(artifact_id: str) -> str:
    """Mermaid node IDs must be alphanumeric/underscore — hyphens are unsafe."""
    return _re.sub(r"[^0-9A-Za-z_]", "_", artifact_id)


def _safe_label(text: str) -> str:
    """Strip characters that break a Mermaid quoted node label."""
    return _re.sub(r'["\[\](){}|]', " ", str(text)).strip()


def _render_graph_mermaid(
    irs: list[dict[str, Any]], edges: list[tuple[str, str]]
) -> str:
    lines = ["graph LR"]
    for ir in irs:
        aid = ir.get("id", "")
        name = _safe_label(ir.get("name", ""))
        label = f"{aid}: {name}" if name else aid
        lines.append(f'  {_mermaid_node_id(aid)}["{label}"]')
    for src, tgt in edges:
        lines.append(f"  {_mermaid_node_id(src)} --> {_mermaid_node_id(tgt)}")
    return "\n".join(lines) + "\n"


def _render_graph_dot(
    irs: list[dict[str, Any]], edges: list[tuple[str, str]]
) -> str:
    lines = ["digraph dekspec {", "  rankdir=LR;"]
    for ir in irs:
        aid = ir.get("id", "")
        name = str(ir.get("name", "")).replace('"', '\\"')
        label = f"{aid}: {name}" if name else aid
        lines.append(f'  "{aid}" [label="{label}"];')
    for src, tgt in edges:
        lines.append(f'  "{src}" -> "{tgt}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


# Kind grouping order for the human-readable `text` graph render.
_GRAPH_KIND_ORDER = [
    "SYSTEM-VISION", "CONSTITUTION", "AE", "ADR", "IC",
    "WS", "IB", "INT", "MSN", "SP", "DOMAIN-GLOSSARY",
]


def _id_kind(artifact_id: str) -> str:
    """Kind label for an artifact ID — the `TYPE-NNN` prefix, or the whole
    ID for the slug-only L0 singletons (ADR-012)."""
    if artifact_id in ("SYSTEM-VISION", "DOMAIN-GLOSSARY", "CONSTITUTION"):
        return artifact_id
    m = _re.match(r"([A-Z]+)-", artifact_id)
    return m.group(1) if m else artifact_id


def _render_graph_text(
    irs: list[dict[str, Any]], edges: list[tuple[str, str]]
) -> str:
    """Human-readable CLI render: artifacts grouped by kind, each node's
    forward-link edges shown inline as a `→` line."""
    by_src: dict[str, list[str]] = {}
    for src, tgt in edges:
        by_src.setdefault(src, []).append(tgt)
    groups: dict[str, list[dict[str, Any]]] = {}
    for ir in irs:
        groups.setdefault(_id_kind(ir.get("id", "")), []).append(ir)

    lines = [
        f"DekSpec artifact graph — {len(irs)} node(s), {len(edges)} edge(s)",
        "",
    ]
    ordered = [k for k in _GRAPH_KIND_ORDER if k in groups]
    ordered += sorted(k for k in groups if k not in _GRAPH_KIND_ORDER)
    for kind in ordered:
        members = groups[kind]
        lines.append(f"{kind}  ({len(members)})")
        for ir in members:
            aid = ir.get("id", "")
            name = str(ir.get("name", "")).strip()
            lines.append(f"  {aid}  {name}".rstrip())
            targets = by_src.get(aid)
            if targets:
                lines.append(f"      → {', '.join(targets)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def cmd_graph_export(args: argparse.Namespace) -> int:
    from .constraint_compiler.graph import SpecGraph

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    graph = SpecGraph.load(repo_root, dekspec_root=args.dekspec_root)

    if args.include.upper() == "ALL":
        prefix_filter: set[str] | None = None
    else:
        valid = {
            "AE", "ADR", "WS", "IC", "IB", "INT", "MSN", "SP",
            "GLOSSARY", "VISION", "CONSTITUTION",
        }
        kinds = {k.strip().upper() for k in args.include.split(",") if k.strip()}
        bad = kinds - valid
        if bad:
            print(
                f"Error: --include contains unknown kinds: {sorted(bad)}. "
                f"Valid: {sorted(valid)}.",
                file=sys.stderr,
            )
            return 2
        # Map kind name → id prefix used in irs_by_id
        prefix_map = {
            "AE": "AE-", "ADR": "ADR-", "WS": "WS-", "IC": "IC-",
            "IB": "IB-", "INT": "INT-", "MSN": "MSN-", "SP": "SP-",
            "GLOSSARY": "DOMAIN-GLOSSARY", "VISION": "SYSTEM-VISION",
            "CONSTITUTION": "CONSTITUTION",
        }
        prefix_filter = {prefix_map[k] for k in kinds}

    irs: list[dict[str, Any]] = []
    for ir in graph.all():
        artifact_id = ir.get("id", "")
        if prefix_filter is not None and not any(
            artifact_id.startswith(p) or artifact_id == p for p in prefix_filter
        ):
            continue
        irs.append(ir)
    irs.sort(key=lambda x: x.get("id", ""))

    if args.format == "json":
        document = {
            "schema_version": "1.0",
            "library_version": __version__,
            "repo_root": str(repo_root),
            "dekspec_root": args.dekspec_root,
            "exported_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ir_count": len(irs),
            "parse_failures": [
                {"path": pf.path, "kind": pf.artifact_kind,
                 "error_type": pf.error_type, "message": pf.message[:500]}
                for pf in graph.parse_failures()
            ],
            # ds-f2j: emit-side coverage summary documents which IR fields are
            # actively consumed by emitters vs which are parsed but informational.
            # Hand-maintained list — when a new field plumbs into an emitter,
            # move it from `parse_only` to `consumed_by` here. Authoritative
            # source is `tooling/dekspec/constraint_compiler/emitters/`.
            "emit_side_coverage": _emit_side_coverage(),
            "irs": irs,
        }
        output = json.dumps(
            document, indent=2 if args.pretty else None, default=str
        ) + "\n"
    else:
        edges = _graph_edges(graph, irs)
        if args.format == "mermaid":
            output = _render_graph_mermaid(irs, edges)
        elif args.format == "dot":
            output = _render_graph_dot(irs, edges)
        else:  # text
            output = _render_graph_text(irs, edges)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(
            f"Wrote {len(irs)} IRs ({len(output)} bytes) -> {out_path}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(output)
    return 0


# --------------------------------------------------------------------------- #
# relink — derive backlinks from the forward-link graph and rewrite the
# rendered `Linked Artifacts` sections (ADR-015 / INT-032 / IB-042).
# --------------------------------------------------------------------------- #


def _add_relink_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "relink",
        help="Recompute the derived `Linked Artifacts` backlinks for every artifact.",
        description=(
            "Graph-repair verb (ADR-015). Parses the artifact set at --at into "
            "a SpecGraph, derives every artifact's backlinks from the "
            "forward-link index, and rewrites each artifact's "
            "`## Linked Artifacts` section in place to the derived values. "
            "Idempotent: a second run against an already-relinked repo writes "
            "nothing. Dangling forward references (forward links to artifact "
            "IDs that do not resolve) are reported on stdout; their presence "
            "sets a non-zero exit code (1) as an advisory signal — the relink "
            "of the resolvable artifacts still completes. Exit 0 = relinked, "
            "no dangling refs; exit 1 = relinked, dangling refs found; exit 2 "
            "= usage error."
        ),
    )
    p.add_argument(
        "--at",
        help="Path to anchor the repo (default: current working directory).",
    )
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Path to the DekSpec content tree relative to repo root (default: dekspec).",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help=(
            "Dry-run: report what would change and the dangling refs, write "
            "nothing. Exits non-zero (1) if a relink would change files or if "
            "dangling forward refs are found."
        ),
    )
    p.set_defaults(func=cmd_relink)


# Artifact-kind directories + filename globs, mirroring SpecGraph.load's walk.
# (dir-name, glob, recursive)
_RELINK_ARTIFACT_DIRS: tuple[tuple[str, str, bool], ...] = (
    ("adrs", "ADR-*.md", False),
    ("architecture-elements", "AE-*.md", False),
    ("working-specs", "WS-*.md", False),
    ("security-profiles", "SP-*.md", False),
    ("interface-contracts", "IC-*.md", False),
    ("impl-briefs", "IB-*.md", True),
    ("intents", "INT-*.md", True),
    ("missions", "MSN-*.md", True),
)
# Singleton artifacts: filename -> the bare artifact ID SpecGraph keys them by.
_RELINK_SINGLETONS: tuple[tuple[str, str], ...] = (
    ("domain-glossary.md", "DOMAIN-GLOSSARY"),
    ("system-vision.md", "SYSTEM-VISION"),
    ("constitution.md", "CONSTITUTION"),
)
# An artifact ID embedded at the start of a filename: <ID>-slug.md or <ID>.md.
_RELINK_ID_RE = _re.compile(r"^((?:ADR|AE|WS|SP|IC|IB|INT|MSN)-\d+)(?:-.*)?$")


def _relink_artifact_paths(dekspec_dir: Path) -> dict[str, Path]:
    """Map bare artifact ID -> on-disk markdown path for a dekspec tree.

    Walks the same conventional layout SpecGraph.load walks. Keyed by the
    bare artifact ID (e.g. ``IB-042``) so it lines up with the bare-ID keys
    produced by :func:`SpecGraph.derive_backlinks`. If two files share a
    bare ID (e.g. two IBs named IB-001 under different Working Specs), the
    last one in sorted-walk order wins — matching ``SpecGraph.by_id``'s
    first-match-by-suffix ambiguity for composite-keyed IBs.
    """
    paths: dict[str, Path] = {}
    if not dekspec_dir.exists():
        return paths
    for dir_name, glob, recursive in _RELINK_ARTIFACT_DIRS:
        dir_path = dekspec_dir / dir_name
        if not dir_path.exists():
            continue
        iterator = dir_path.rglob(glob) if recursive else dir_path.glob(glob)
        for artifact_path in sorted(iterator):
            m = _RELINK_ID_RE.match(artifact_path.stem)
            if m is not None:
                paths[m.group(1)] = artifact_path
    for filename, artifact_id in _RELINK_SINGLETONS:
        singleton = dekspec_dir / filename
        if singleton.exists():
            paths[artifact_id] = singleton
    return paths


def cmd_relink(args: argparse.Namespace) -> int:
    """`dekspec relink` — thin dispatch shell over IB-041's derivation + emitter.

    Owns argument parsing, graph construction, file I/O, stdout reporting and
    exit-code selection only. All backlink derivation lives in
    ``SpecGraph.derive_backlinks`` and all markdown rendering lives in
    ``emit_linked_artifacts`` (the Constraint Compiler — IB-041).
    """
    from .constraint_compiler.emitters.linked_artifacts import emit_linked_artifacts
    from .constraint_compiler.graph import SpecGraph, artifact_id_sort_key

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    dekspec_dir = repo_root / args.dekspec_root

    graph = SpecGraph.load(repo_root, dekspec_root=args.dekspec_root)
    # IB-041: derive every artifact's backlinks + collect unresolved fwd refs.
    backlinks, unresolved = graph.derive_backlinks()
    id_to_path = _relink_artifact_paths(dekspec_dir)

    relinked: list[str] = []
    unchanged = 0
    no_section: list[str] = []
    missing_file: list[str] = []

    for artifact_id in sorted(backlinks, key=artifact_id_sort_key):
        artifact_path = id_to_path.get(artifact_id)
        if artifact_path is None:
            missing_file.append(artifact_id)
            continue
        current = artifact_path.read_text(encoding="utf-8")
        result = emit_linked_artifacts(current, backlinks[artifact_id])
        if not result.has_section:
            no_section.append(artifact_id)
            continue
        if not result.changed:
            unchanged += 1
            continue
        relinked.append(artifact_id)
        if not args.check:
            artifact_path.write_text(result.markdown, encoding="utf-8")

    # Dangling forward refs: for each unresolved target, name every referrer.
    dangling: list[tuple[str, str]] = []
    if unresolved:
        unresolved_set = set(unresolved)
        for referrer_id in sorted(
            (ir["id"] for ir in graph.all()),
            key=artifact_id_sort_key,
        ):
            for target_id in graph.forward_links_of(referrer_id):
                if target_id in unresolved_set:
                    dangling.append((referrer_id, target_id))

    mode = "would relink" if args.check else "relinked"
    print(
        f"dekspec relink — {repo_root}\n"
        f"  artifacts: {mode}={len(relinked)} unchanged={unchanged} "
        f"no-section={len(no_section)}"
    )
    if missing_file:
        print(
            f"  note: {len(missing_file)} artifact(s) parsed but no markdown "
            f"file located: {', '.join(missing_file)}"
        )
    if dangling:
        print(f"\nDangling forward references ({len(dangling)}):")
        for referrer_id, target_id in dangling:
            print(
                f"  {referrer_id}: forward-links {target_id} "
                f"which does not resolve to any artifact"
            )
    else:
        print("  dangling forward references: none")

    if args.check and relinked:
        print(
            "\n--check: a relink would change "
            f"{len(relinked)} artifact(s); no files written."
        )

    # Exit codes: 1 if dangling refs found (advisory); under --check, also 1
    # if a relink would change files. Otherwise 0.
    if dangling:
        return 1
    if args.check and relinked:
        return 1
    return 0


def _add_verify_vendored_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "verify-vendored",
        help="Compare the consumer's vendored DekSpec content against the library source-of-truth.",
        description=(
            "Walks the canonical vendoring manifest (skills, templates, "
            "methodology docs) and reports drift: modified files, missing "
            "files, unknown extra files, and version-marker mismatch. "
            "Run from the consumer repo root after upgrading the dekspec "
            "library to know what to refresh via install-dekspec.sh."
        ),
    )
    p.add_argument(
        "--at",
        help="Path to the consumer repo (default: current working directory).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit findings as JSON instead of formatted table.",
    )
    p.set_defaults(func=cmd_verify_vendored)


def cmd_verify_vendored(args: argparse.Namespace) -> int:
    from .vendoring import compute_drift

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    findings = compute_drift(repo_root)

    # Reference-unreliable short-circuit: the library reference is a dev
    # checkout, not a release — file-level drift was not computed. Not a
    # drift failure; exit 0 with a clear advisory.
    unreliable = next(
        (f for f in findings if f.kind == "reference-unreliable"), None
    )
    if unreliable is not None:
        if args.json:
            print(json.dumps([f.to_dict() for f in findings], indent=2))
            return 0
        print(f"DekSpec verify-vendored — {repo_root}")
        print(f"Library version: {__version__}")
        print()
        print("reference unreliable — file-level drift not checked")
        print(f"  {unreliable.detail}")
        return 0

    # Version-skew short-circuit: engine and vendored content are at different
    # versions. Per-file hashes would all mismatch by construction; return one
    # explanatory finding instead. Exit 0 — the remedy depends on direction
    # (upgrade the engine, or `dekspec sync` the vendored content).
    # (ds-upgrade-manifest-not-regenerated-3osq, 2026-05-28)
    version_skew = next(
        (f for f in findings if f.kind in
         ("engine-stale-vs-vendored", "vendored-stale-vs-engine")),
        None,
    )
    if version_skew is not None:
        if args.json:
            print(json.dumps([f.to_dict() for f in findings], indent=2))
            return 0
        _mk = repo_root / ".dekspec-version"
        _v_vendored = (
            _mk.read_text(encoding="utf-8").strip() if _mk.exists() else "?"
        )
        headline = (
            "vendored content stale vs engine — file-level drift not checked"
            if version_skew.kind == "vendored-stale-vs-engine"
            else "engine stale vs vendored — file-level drift not checked"
        )
        print(f"DekSpec verify-vendored — {repo_root}")
        print(f"Engine version: {__version__} | vendored version: {_v_vendored}")
        print()
        print(headline)
        print(f"  {version_skew.detail}")
        return 0

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
        return 1 if findings else 0

    if not findings:
        print(
            f"OK — vendored DekSpec content at {repo_root} is in sync with library v{__version__}."
        )
        return 0

    by_kind: dict[str, list[Any]] = {
        "modified": [], "missing": [], "unknown": [], "version": [],
    }
    for f in findings:
        by_kind.setdefault(f.kind, []).append(f)

    print(f"DekSpec verify-vendored — {repo_root}")
    print(f"Library version: {__version__}")
    print(
        f"Total drift findings: {len(findings)}  "
        f"(modified={len(by_kind['modified'])} missing={len(by_kind['missing'])} "
        f"unknown={len(by_kind['unknown'])} version={len(by_kind['version'])})"
    )
    print()
    for kind in ("version", "modified", "missing", "unknown"):
        items = by_kind[kind]
        if not items:
            continue
        print(f"## {kind.upper()} ({len(items)})")
        print()
        for f in items:
            print(f"  [{f.kind}] {f.consumer_path}")
            print(f"    {f.detail}")
            print()
    return 1


def _add_migrate_artifacts_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "migrate-artifacts",
        help="Apply markdown-artifact migrations to a consumer repo's dekspec/ tree.",
        description=(
            "Walks every dekspec artifact (AE/ADR/IC/WS/IB/Intent/Mission/"
            "Vision/Glossary) under <repo>/dekspec/, applies registered "
            "migrations for the requested library version span, and writes "
            "the modified files back. Emits an advisory report listing "
            "semantic transforms that need human review — consumed by the "
            "`/dekspec:migrate --walker-only` orchestrator skill."
        ),
    )
    p.add_argument(
        "--at",
        help="Path to the consumer repo (default: current working directory).",
    )
    p.add_argument(
        "--from",
        dest="from_version",
        help=(
            "Library version the artifacts were last vendored against. "
            "Defaults to the value in .dekspec-version if present."
        ),
    )
    p.add_argument(
        "--to",
        dest="to_version",
        help=f"Target library version. Defaults to the installed library ({__version__}).",
    )
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Subdirectory under --at where dekspec artifacts live (default: dekspec).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without modifying any files.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit the migration report as JSON.",
    )
    p.add_argument(
        "--no-advisory-file",
        action="store_true",
        help="Skip writing the advisory JSON file (advisories still appear in stdout).",
    )
    p.set_defaults(func=cmd_migrate_artifacts)


def cmd_migrate_artifacts(args: argparse.Namespace) -> int:
    from .migrations import (
        markdown_default_registry,
        migrate_markdown_artifacts,
        write_advisory_report,
    )

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    from_version = args.from_version
    if not from_version:
        marker = repo_root / ".dekspec-version"
        if marker.exists():
            from_version = marker.read_text(encoding="utf-8").strip()
        else:
            print(
                "error: --from is required when no .dekspec-version marker is "
                "present in the repo.",
                file=sys.stderr,
            )
            return 2
    to_version = args.to_version or __version__

    report = migrate_markdown_artifacts(
        repo_root,
        from_version,
        to_version,
        registry=markdown_default_registry,
        dekspec_root=args.dekspec_root,
        dry_run=args.dry_run,
    )

    advisory_path: Path | None = None
    if not args.no_advisory_file and not args.dry_run:
        advisory_path = write_advisory_report(
            repo_root, report, dekspec_root=args.dekspec_root,
        )

    if args.json:
        out = report.to_dict()
        if advisory_path is not None:
            out["advisory_report_path"] = str(advisory_path)
        print(json.dumps(out, indent=2))
        return 1 if (report.files_failed or report.advisories) else 0

    mode = "DRY RUN — " if args.dry_run else ""
    print(f"{mode}DekSpec migrate-artifacts — {repo_root}")
    print(f"Library version: {from_version} → {to_version}")
    print(
        f"Files scanned: {report.files_scanned}  "
        f"modified: {report.files_modified}  "
        f"unchanged: {report.files_unchanged}  "
        f"failed: {report.files_failed}"
    )
    print(f"Advisory items (human review needed): {len(report.advisories)}")
    if advisory_path is not None:
        print(f"Advisory report written to: {advisory_path}")
        print(
            "  → Run `/dekspec:migrate --walker-only` (orchestrator skill) to walk "
            "the advisory queue with Claude reasoning in the loop."
        )

    if report.advisories:
        print()
        print("## Advisory items")
        for i, adv in enumerate(report.advisories, start=1):
            print(f"  [{i}] {adv.change_type}: {adv.artifact_path}")
            print(f"      {adv.description}")
            if adv.suggested_transform:
                print(f"      hint: {adv.suggested_transform}")

    if report.errors:
        print()
        print("## Errors")
        for path, msg in report.errors.items():
            print(f"  {path}")
            print(f"    {msg}")

    return 1 if (report.files_failed or report.advisories) else 0


def _add_dekspec_migrate_pipeline_subparser(sub: argparse._SubParsersAction) -> None:
    """Register `dekspec migrate` — the consolidated upgrade pipeline (INT-098).

    Single top-level entry point that runs the three upgrade-related
    operations in sequence (verify-vendored drift check → migrate-ir on
    persisted IR JSON → migrate-artifacts on the dekspec/ markdown tree).
    Exits non-zero on the first failing stage. The three underlying
    subverbs (`repo verify`, `repo migrate-ir`, `repo migrate-artifacts`)
    are no longer separately registered — this verb is the only blessed
    entry point.
    """
    p = sub.add_parser(
        "migrate",
        help="Run the full upgrade pipeline: verify → migrate-ir → migrate-artifacts.",
        description=(
            "Single-command upgrade pipeline (INT-098). Runs three "
            "operations in sequence: (1) vendor-drift verify against the "
            "installed library version, (2) schema migration on persisted "
            "IR JSON files, (3) markdown-artifact migration over the "
            "consumer's dekspec/ tree. Exits non-zero on the first failure. "
            "If migrate-artifacts populates a non-empty advisory queue, "
            "the operator is directed to run `/dekspec:migrate --walker-only` "
            "(orchestrator skill) interactively in a Claude session."
        ),
    )
    p.add_argument(
        "--at",
        help="Path to the consumer repo (default: current working directory).",
    )
    p.add_argument(
        "--from",
        dest="from_version",
        help=(
            "Library version the artifacts were last vendored against. "
            "Defaults to the value in .dekspec-version if present. Forwarded "
            "to migrate-artifacts."
        ),
    )
    p.add_argument(
        "--to",
        dest="to_version",
        help=f"Target library version. Defaults to the installed library ({__version__}).",
    )
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Subdirectory under --at where dekspec artifacts live (default: dekspec).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without modifying any files.",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Apply migrate-ir changes to persisted IR JSON files. Without --apply, migrate-ir is dry-run only.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit per-stage results as JSON.",
    )
    p.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the vendor-drift verify stage. Use when the consumer has pip-only install (no vendored tree).",
    )
    p.set_defaults(func=cmd_dekspec_migrate_pipeline)


def cmd_dekspec_migrate_pipeline(args: argparse.Namespace) -> int:
    """Run the consolidated migrate pipeline.

    Stage 1 — verify: `cmd_verify_vendored` checks vendored content drift.
    Stage 2 — migrate-ir: `cmd_migrate` walks persisted IR JSON under the
              repo state dir.
    Stage 3 — migrate-artifacts: `cmd_migrate_artifacts` walks the
              dekspec/ markdown tree.

    First non-zero exit short-circuits. When migrate-artifacts populates
    an advisory queue, the existing hint is surfaced verbatim (it's already
    printed by `cmd_migrate_artifacts`).
    """
    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    is_json = bool(args.json)

    stage_results: list[dict[str, Any]] = []

    # --- Stage 1: verify-vendored ---
    if args.skip_verify:
        stage_results.append({"stage": "verify", "skipped": True, "reason": "--skip-verify"})
        if not is_json:
            print("[migrate stage 1] verify-vendored: skipped (--skip-verify)")
    else:
        if not is_json:
            print("[migrate stage 1] verify-vendored")
        verify_ns = argparse.Namespace(at=str(repo_root) if args.at else None, json=False)
        try:
            rc = cmd_verify_vendored(verify_ns)
        except Exception as e:  # noqa: BLE001
            stage_results.append({"stage": "verify", "exit_code": 2, "error": str(e)})
            if is_json:
                print(json.dumps({"stages": stage_results}, indent=2))
            else:
                print(f"  error: verify stage raised {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        stage_results.append({"stage": "verify", "exit_code": rc})
        if rc != 0:
            if is_json:
                print(json.dumps({"stages": stage_results}, indent=2))
            else:
                print(f"  verify-vendored exited {rc}; pipeline aborted.", file=sys.stderr)
            return rc

    # --- Stage 2: migrate-ir ---
    from .constraint_compiler.persistence import repo_runs_dir
    runs_dir = repo_runs_dir(repo_root)
    ir_files = sorted(str(p) for p in runs_dir.glob("*/irs/*.ir.json"))
    if not ir_files:
        stage_results.append({"stage": "migrate-ir", "skipped": True, "reason": "no IR JSON found"})
        if not is_json:
            print("[migrate stage 2] migrate-ir: skipped (no persisted IR JSON under repo state dir)")
    else:
        if not is_json:
            print(f"[migrate stage 2] migrate-ir: {len(ir_files)} file(s)")
        migrate_ns = argparse.Namespace(
            path=ir_files,
            to=None,
            apply=bool(args.apply),
            json=False,
        )
        try:
            rc = cmd_migrate(migrate_ns)
        except Exception as e:  # noqa: BLE001
            stage_results.append({"stage": "migrate-ir", "exit_code": 2, "error": str(e)})
            if is_json:
                print(json.dumps({"stages": stage_results}, indent=2))
            else:
                print(f"  error: migrate-ir stage raised {type(e).__name__}: {e}", file=sys.stderr)
            return 2
        stage_results.append({"stage": "migrate-ir", "exit_code": rc, "files": len(ir_files)})
        if rc != 0:
            if is_json:
                print(json.dumps({"stages": stage_results}, indent=2))
            else:
                print(f"  migrate-ir exited {rc}; pipeline aborted.", file=sys.stderr)
            return rc

    # --- Stage 3: migrate-artifacts ---
    if not is_json:
        print("[migrate stage 3] migrate-artifacts")
    artifacts_ns = argparse.Namespace(
        at=str(repo_root) if args.at else None,
        from_version=args.from_version,
        to_version=args.to_version,
        dekspec_root=args.dekspec_root,
        dry_run=bool(args.dry_run),
        json=False,
        no_advisory_file=False,
    )
    try:
        rc = cmd_migrate_artifacts(artifacts_ns)
    except Exception as e:  # noqa: BLE001
        stage_results.append({"stage": "migrate-artifacts", "exit_code": 2, "error": str(e)})
        if is_json:
            print(json.dumps({"stages": stage_results}, indent=2))
        else:
            print(f"  error: migrate-artifacts stage raised {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    stage_results.append({"stage": "migrate-artifacts", "exit_code": rc})

    if is_json:
        print(json.dumps({"stages": stage_results}, indent=2))

    return rc


def _add_sync_args(p: argparse.ArgumentParser) -> None:
    """Shared args for the reconcile verb (`library sync`) and its
    deprecation alias (`repo upgrade`). Reconcile takes NO version,
    NO source, NO acquisition toggles — only the reconcile-relevant flags."""
    p.add_argument(
        "--at",
        help="Path to the consumer repo (default: current working directory).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without modifying any files.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit the reconcile report as JSON.",
    )
    p.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help=(
            "Auto-confirm prompts (e.g. BREAKING-release confirmation). "
            "Useful for non-interactive sessions."
        ),
    )


def _add_sync_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "sync",
        help="Reconcile the consumer repo to the installed engine version.",
        description=(
            "Reconcile-only sync (INT-135 / ADR-032). Vendors content from "
            "the INSTALLED engine wheel (`dekspec resource` resolution — no "
            "git clone), runs `dekspec migrate` as a separate sub-step, "
            "checks the breaking-CHANGELOG guard, and reports drift — all "
            "against the already-installed `dekspec.__version__`. Performs NO "
            "acquisition: no network, no pip, no `claude plugin` shell, no "
            "version resolution. Acquire the engine + plugin out-of-band "
            "(`pipx install dekspec` + `claude plugin update dekspec@dekspec`). "
            "Idempotent: a second consecutive run is a no-op."
        ),
    )
    _add_sync_args(p)
    p.set_defaults(func=cmd_sync)


def cmd_sync(args: argparse.Namespace) -> int:
    """Reconcile the consumer repo to the ALREADY-INSTALLED engine version.

    Reconcile-only (ADR-032): NO network, NO pip, NO `claude plugin` shell,
    NO version resolution. The target version is the installed
    `dekspec.__version__`; the baseline is the consumer's `.dekspec-version`
    marker. Steps, in order:

      1. Vendoring — `vendoring.reconcile` copies content from the INSTALLED
         engine (the wheel's `_vendored/` tree resolved via `library_root()`,
         the same resolution `dekspec resource` uses; INT-097), NOT a git
         clone. Idempotent: a no-op when the marker already equals the
         installed version and no vendored file has drifted.
      2. Migrate — invokes the existing `dekspec migrate` pipeline
         (`cmd_dekspec_migrate_pipeline`) IN-PROCESS as a separate sub-step
         (no subprocess; migrate stays an independently-invocable verb).
      3. Breaking-CHANGELOG guard — reads the engine's bundled CHANGELOG and,
         on a BREAKING target, prompts for confirmation (unless --yes).
      4. Drift report — surfaces vendored drift via `cmd_verify_vendored`.
    """
    from .vendoring import (
        ReconcileReport,
        UpgradeError,
        extract_changelog_section,
        library_root,
        reconcile,
        section_is_breaking,
    )

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    target = __version__

    marker = repo_root / ".dekspec-version"
    baseline = (
        marker.read_text(encoding="utf-8").strip() if marker.exists() else None
    )

    # Breaking-CHANGELOG guard. The CHANGELOG ships with the engine; resolve
    # it from the installed library root (wheel `_vendored/` or source
    # checkout). Absent CHANGELOG → guard is a graceful no-op (None section).
    if not args.dry_run and not args.yes and baseline != target:
        changelog_path = library_root() / "CHANGELOG.md"
        section = extract_changelog_section(changelog_path, target)
        if section_is_breaking(section):
            print(f"\n\u26a0  Target v{target} contains BREAKING changes:\n",
                  file=sys.stderr)
            print(section, file=sys.stderr)
            print(file=sys.stderr)
            try:
                resp = input(f"Proceed with v{target} reconcile? (y/N) ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nAborted.", file=sys.stderr)
                return 1
            if resp not in ("y", "yes"):
                print("Aborted by operator.", file=sys.stderr)
                return 1

    # Step 1: vendoring (wheel-sourced reconcile — no clone, no network).
    try:
        report: ReconcileReport = reconcile(
            repo_root, target, dry_run=args.dry_run
        )
    except UpgradeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    mode_label = "DRY RUN \u2014 " if args.dry_run else ""
    print(f"{mode_label}DekSpec library sync \u2014 {repo_root}")
    print(f"Installed engine version: {target}")
    print(f"Consumer baseline (.dekspec-version): {baseline or 'none'}")

    if report.noop:
        print(
            f"  reconcile: no-op \u2014 already in sync at v{target} "
            "(marker matches installed engine, no vendored drift)."
        )
        return 0

    print(
        f"  vendored content: {report.files_written} written, "
        f"{report.files_unchanged} unchanged, {report.files_removed} removed."
    )
    if report.version_marker_written:
        print(f"  .dekspec-version: set to {target}.")
    print()

    if args.dry_run:
        print("  [dry-run] would run: dekspec migrate "
              "(verify \u2192 migrate-ir \u2192 migrate-artifacts)")
        print("  [dry-run] would report: vendored-content drift")
        return 0

    # Step 2: migrate \u2014 invoke the existing migrate pipeline IN-PROCESS as
    # a SEPARATE sub-step (migrate stays an independently-invocable verb; we
    # do NOT inline its logic). No subprocess: reconcile must not shell out.
    print("  running migrate pipeline (verify \u2192 migrate-ir \u2192 migrate-artifacts)")
    migrate_ns = argparse.Namespace(
        at=str(repo_root) if args.at else None,
        from_version=baseline,
        to_version=target,
        dekspec_root="dekspec",
        dry_run=False,
        apply=True,
        json=False,
        # Vendoring just refreshed content; verify would only confirm sync.
        skip_verify=True,
    )
    rc = cmd_dekspec_migrate_pipeline(migrate_ns)
    if rc not in (0, 1):
        print(f"  warning: migrate pipeline exited {rc}.", file=sys.stderr)

    # Step 3: drift report \u2014 read-only verify of vendored content vs the
    # installed engine. Informational; never gates the reconcile exit code.
    print("  reporting vendored-content drift: dekspec verify-vendored")
    verify_ns = argparse.Namespace(
        at=str(repo_root) if args.at else None, json=False
    )
    cmd_verify_vendored(verify_ns)

    print()
    print(f"Reconciled to installed engine v{target}.")
    print("  Review and commit the reconcile diff.")
    return 0


def _detect_artifact_kind(filename: str) -> str | None:
    """Return artifact kind from filename, None if unrecognized."""
    # ADR-043: a provisional `P-<KIND>-<NNN>-<slug>.md` file detects to its
    # underlying kind — strip the `P-` prefix so the per-kind checks match.
    from .provisional_ids import is_provisional_filename

    if is_provisional_filename(filename):
        filename = filename[len("P-"):]
    if filename == "system-vision.md":
        return "vision"
    if filename == "domain-glossary.md":
        return "glossary"
    if filename == "constitution.md":
        return "constitution"
    if _ADR_PREFIX.match(filename):
        return "adr"
    if _AE_PREFIX.match(filename):
        return "ae"
    if _IB_PREFIX.match(filename):
        return "ib"
    if _IC_PREFIX.match(filename):
        return "ic"
    if _INT_PREFIX.match(filename):
        return "intent"
    if _MSN_PREFIX.match(filename):
        return "mission"
    if _SP_PREFIX.match(filename):
        return "sp"
    if _WS_PREFIX.match(filename):
        return "ws"
    return None


def _shell_quote_args(parts: list[str]) -> str:
    """Quote a command for inclusion in manifest.command. Cheap shell-quoting."""
    out = []
    for p in parts:
        if any(c in p for c in " \t\"'$&|;()<>"):
            out.append('"' + p.replace('"', '\\"') + '"')
        else:
            out.append(p)
    return " ".join(out)


def _emit_side_coverage() -> dict[str, dict[str, list[str]]]:
    """ds-f2j: declarative summary of which parsed IR fields each emitter
    actively consumes vs leaves as parse-only.

    Hand-maintained — when an emitter is extended to read a new field,
    move it from `parse_only` to `consumed_by_agents_md` here. Source of
    truth is `tooling/dekspec/constraint_compiler/emitters/`. Audited
    against by `dekspec graph export` so engineers can see at a glance
    what's load-bearing.
    """
    return {
        "AE": {
            # IB-044 (INT-034 / ADR-015): the stored `related_*s` backlink
            # projections under `linked_artifacts` are retired — backlinks
            # are derived from forward links and emitted by `dekspec relink`,
            # not schema-validated input. Only `linked_artifacts.owners`
            # remains as a parsed field.
            "consumed_by_agents_md": [
                "id", "name", "subtype", "classification",
                "purpose_and_scope", "responsibilities",
                "boundaries_and_non_goals.non_goals",
                "implements_globs",
                "views.diagrams", "views.absence_justification",
                "runtime_behavior",
            ],
            "parse_only": [
                "relationships_and_dependencies", "data_and_state",
                "deployment_operational_shape", "constraints_and_quality_notes",
                "boundaries_and_non_goals.inside",
                "linked_artifacts.owners", "former_dn", "open_questions",
                "amendment_log",
            ],
        },
        "ADR": {
            "consumed_by_agents_md": [
                "id", "name", "status", "date", "decision",
                "options_considered", "consequences.positive",
                "consequences.negative",
                "validation.reconsideration_triggers", "validation.raw_prose",
                "related_architecture_elements", "supersession.superseded_by",
            ],
            "parse_only": [
                "context_and_decision_drivers", "deciders", "links",
                "open_issues", "amendment_log",
            ],
        },
        "WS": {
            "consumed_by_agents_md": [
                "id", "name", "status", "related_architecture_elements",
                "what_this_does.mechanism", "what_this_does.prose",
                "business_rules", "failure_behavior",
            ],
            "parse_only": [
                "silent_failure_domains", "expertise_audit", "governing_adrs",
                "what_this_does_not_do", "interfaces", "governing_formulas",
                "contracts", "refactor_targets", "eval_hooks",
                "open_issues", "amendment_log",
            ],
        },
        "IC": {
            "consumed_by_agents_md": [],
            "parse_only": [
                "id", "name", "status", "version", "purpose",
                "parties", "provider_ae", "consumer_aes",
                "relationship_pattern", "shared_conventions",
                "interface_definition", "domain_constraints",
                "error_semantics", "consistency_guarantees",
                "silent_failure_domains", "governing_adrs",
                "amendment_log",
            ],
            "note": "IC fragments are not emitted by agents_md; ICs surface to consumers via contract_test + ci_gate emitters instead.",
        },
        "IB": {
            "consumed_by_agents_md": [
                "id", "name", "status", "spec.id", "source_aes",
                "depends_on", "production_gate", "goal",
                "files_to_modify", "do_not_touch", "governing_adrs",
                "done_when", "constraints_and_decisions",
                "domain_constraints",
            ],
            "parse_only": [
                "intent", "open_issues", "amendment_log",
            ],
        },
        "Intent": {
            "consumed_by_agents_md": [
                "id", "name", "status", "intent_type", "autonomy",
                "mission.id", "linked_architecture_elements",
                "motivation", "desired_outcome",
                "type_specific.target", "type_specific.metric",
                "components_affected", "verification",
            ],
            "parse_only": [
                "audit_profile", "branch", "source_provenance",
                "superseded_by", "open_issues", "amendment_log",
            ],
        },
        "Mission": {
            "consumed_by_agents_md": [
                "id", "name", "status", "autonomy_ceiling", "owner",
                "outcome",
                "mission_verification",
                "out_of_scope",
                "flag_strategy.flag_name",
                "flag_strategy.default_state",
                "flag_strategy.removal_plan",
                # v0.2.0 (ds-zuy): rollback_plan + kill_criteria became
                # structured cmd-check predicates parallel to
                # mission_verification.
                "rollback_plan.trigger",
                "rollback_plan.steps",
                "kill_criteria",
                "intent_queue",
            ],
            "parse_only": [
                "amendment_log", "discovered_prerequisites",
                "notes", "first_intent",
            ],
        },
    }




# --------------------------------------------------------------------------- #
# session — INT-009 control plane (MSN-002).
# Single contiguous block. Thin adapter over tooling/dekspec/session_lifecycle.py
# (INT-008 data plane, WS-007 contract). No domain logic lives here per AE-005.
# Block placement (after _emit_side_coverage, before __main__ guard) chosen to
# minimise merge-conflict surface with sibling agents (ds-nj1 executor verbs;
# INT-010 install-hooks body when it lands).
# --------------------------------------------------------------------------- #
from . import session_lifecycle as _session_lifecycle  # noqa: E402


def _add_session_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "session",
        help="Open, close, and inspect a dekspec session (MSN-002).",
        description=(
            "The `dekspec session` verb family is the control-plane CLI for "
            "the MSN-002 session-lifecycle gate. Subcommands: `start` opens "
            "a session bound to a bead or Intent ID; `end` closes it; "
            "`status` inspects it (with `--machine-readable` for hook code); "
            "`install-hooks` writes the git-hook gate templates (INT-010 "
            "lands the install behaviour)."
        ),
    )
    session_sub = p.add_subparsers(
        dest="session_command", metavar="<session-command>"
    )

    p_start = session_sub.add_parser(
        "start",
        help="Open a new session bound to a bead or Intent ID.",
        description=(
            "Opens a new session at $XDG_STATE_HOME/dekspec/<repo-hash>/"
            "session.json. The <id> argument is routed by the data plane: "
            "ids matching `^INT-\\d{3,}$` populate bound_intent_id; otherwise "
            "they populate bound_bead_id."
        ),
    )
    p_start.add_argument(
        "id",
        help="Bead id (e.g. ds-int-009-foo-abc) or Intent id (e.g. INT-009).",
    )
    p_start.add_argument(
        "--branch",
        default=None,
        help=(
            "Branch name to bind. Defaults to `git rev-parse --abbrev-ref HEAD`. "
            "Required when not running inside a git repo."
        ),
    )
    p_start.set_defaults(func=cmd_session_start)

    p_end = session_sub.add_parser(
        "end",
        help="Close the active session.",
        description=(
            "Closes the active session, sets end_ts, and removes the state "
            "file. Optional --reason is reserved for future audit-side use."
        ),
    )
    p_end.add_argument(
        "--reason",
        default=None,
        help="Optional one-line reason for closing the session.",
    )
    p_end.set_defaults(func=cmd_session_end)

    p_status = session_sub.add_parser(
        "status",
        help="Inspect the active session.",
        description=(
            "Without --machine-readable: prints a human-readable summary; "
            "exits 0 when active or stale, 1 when no session is present. "
            "With --machine-readable: emits a single line of flat JSON with "
            "keys {active, session_id, bound_bead_id, bound_intent_id, "
            "branch, start_ts, stale} and ALWAYS exits 0; consumers must "
            "read the `active` key."
        ),
    )
    p_status.add_argument(
        "--machine-readable",
        action="store_true",
        help="Emit a single-line JSON envelope instead of human-readable text.",
    )
    p_status.set_defaults(func=cmd_session_status)

    p_hooks = session_sub.add_parser(
        "install-hooks",
        help="Install git hooks that enforce the session gate (INT-010).",
        description=(
            "Installs .git/hooks/pre-commit and .git/hooks/pre-push templates "
            "into the current repo. The install behaviour lands under INT-010; "
            "at INT-009's release the subcommand exits 2 with a clear error."
        ),
    )
    p_hooks.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing hook files (INT-010 behaviour; V1 stub ignores).",
    )
    p_hooks.set_defaults(func=cmd_session_install_hooks)

    p_vibe = session_sub.add_parser(
        "vibecoding-check",
        help="Classify staged files against the claimed Intent's Components affected.",
        description=(
            "Classify staged files against the claimed Intent's Components "
            "affected; exit 3 on off-spec drift (MSN-009). Resolves the active "
            "session to its parent Intent, reads that Intent's `Components "
            "affected` globs, and reports which staged files fall outside that "
            "scope by exact glob match. Exit 0 when every staged file is "
            "in-scope (or there is nothing to check); exit 3 when at least one "
            "file is off-spec. With --machine-readable, emits a stable JSON "
            "envelope. With --record, additionally appends an off-spec record "
            "to session state (used by the pre-commit hook)."
        ),
    )
    p_vibe.add_argument(
        "--machine-readable",
        action="store_true",
        help="Emit a single-line JSON envelope instead of human-readable text.",
    )
    p_vibe.add_argument(
        "--files",
        default=None,
        help=(
            "Comma- or newline-separated staged file paths. When absent, the "
            "verb computes the set via `git diff --cached --name-only`."
        ),
    )
    p_vibe.add_argument(
        "--record",
        action="store_true",
        help=(
            "On an off-spec result, append an off-spec record to session "
            "state via emit_off_spec. Off by default — the verb is a pure "
            "reporter unless --record is passed."
        ),
    )
    p_vibe.set_defaults(func=cmd_session_vibecoding_check)

    p_report = session_sub.add_parser(
        "report",
        help="Summarize off-spec (vibecoding) drift recorded during the active session.",
        description=(
            "Summarize off-spec (vibecoding) drift recorded during the active "
            "session (MSN-009). Reads the active session's off-spec commit log "
            "and prints an end-of-session summary — per-commit detail plus a "
            "ratify-or-revert prompt. Read-only: never mutates session state. "
            "With --machine-readable, emits a stable JSON envelope. Always "
            "exits 0 on a normal run."
        ),
    )
    p_report.add_argument(
        "--machine-readable",
        action="store_true",
        help="Emit a single-line JSON envelope instead of human-readable text.",
    )
    p_report.set_defaults(func=cmd_session_report)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


def _resolve_default_branch() -> str:
    """Derive the current branch via `git rev-parse --abbrev-ref HEAD`.

    Fail-loud (SystemExit(2)) when not inside a git repo; the caller would
    otherwise see the data plane's `SessionStateValidationError` on an empty
    branch string, which is a worse error message than this one.
    """
    import subprocess as _subprocess

    try:
        result = _subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print(
            "dekspec session start: git binary not on PATH "
            "(pass --branch <name> explicitly).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        print(
            "dekspec session start: not in a git repo "
            "(pass --branch <name> explicitly).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return branch


def _format_bound_display(state: Any) -> str:
    """Inline mirror of the data-plane bound-display helper.

    Inlined here per WS-012 BR9 (CLI MUST NOT call underscore-prefixed
    data-plane helpers). Promoted to a CLI-local helper to keep the
    dispatchers terse.
    """
    parts = [p for p in (state.bound_intent_id, state.bound_bead_id) if p]
    return " / ".join(parts) if parts else "<unbound>"


def cmd_session_start(args: argparse.Namespace) -> int:
    branch = args.branch if args.branch else _resolve_default_branch()
    try:
        state = _session_lifecycle.start(bound_id=args.id, branch=branch)
    except _session_lifecycle.SessionAlreadyActiveError as e:
        print(f"dekspec session start: {e}", file=sys.stderr)
        return 3
    except _session_lifecycle.SessionStateValidationError as e:
        print(f"dekspec session start: {e}", file=sys.stderr)
        return 2
    bound = _format_bound_display(state)
    print(
        f"Started session {state.session_id} bound to {bound} "
        f"on branch {state.branch}."
    )
    return 0


def cmd_session_end(args: argparse.Namespace) -> int:
    reason = args.reason if args.reason is not None else ""
    try:
        state = _session_lifecycle.end(reason=reason)
    except FileNotFoundError as e:
        print(f"dekspec session end: {e}", file=sys.stderr)
        return 4
    bound = _format_bound_display(state)
    from datetime import datetime as _datetime, timezone as _timezone

    _ts_fmt = "%Y-%m-%dT%H:%M:%SZ"
    start_dt = _datetime.strptime(state.start_ts, _ts_fmt).replace(tzinfo=_timezone.utc)
    end_dt = _datetime.strptime(state.end_ts, _ts_fmt).replace(tzinfo=_timezone.utc)
    total_minutes = int((end_dt - start_dt).total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    print(
        f"Ended session {state.session_id} (bound to {bound}, "
        f"duration {hours}h{minutes}m)."
    )
    return 0


def cmd_session_status(args: argparse.Namespace) -> int:
    machine = bool(getattr(args, "machine_readable", False))
    try:
        result = _session_lifecycle.status(machine_readable=machine)
    except _session_lifecycle.SessionStateValidationError as e:
        print(f"dekspec session status: {e}", file=sys.stderr)
        return 2
    if machine:
        # result is a dict mirroring WS-007 status(machine_readable=True).
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    # result is a str.
    print(result)
    if result.startswith("Active session") or result.startswith("Stale session"):
        return 0
    return 1


def cmd_session_install_hooks(args: argparse.Namespace) -> int:
    from . import git_hooks
    target = Path.cwd()
    try:
        written = git_hooks.install_hooks(target, force=bool(getattr(args, "force", False)))
    except git_hooks.GitHooksError as exc:
        print(f"dekspec session install-hooks: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(f"installed {path}")
    return 0


def cmd_session_vibecoding_check(args: argparse.Namespace) -> int:
    """Classify staged files against the claimed Intent's Components affected.

    Exit 0 when every staged file is in-scope (or nothing to check); exit 3
    on off-spec drift. The verb is a pure reporter unless --record is
    passed, in which case an off-spec result also appends an off-spec
    record to session state. The staged set comes from --files (comma- or
    newline-separated), else from `git diff --cached --name-only`; a git
    failure resolves to an empty set (best-effort staged-set discovery).
    """
    from . import vibecoding_guard

    files_arg = getattr(args, "files", None)
    if files_arg is not None:
        staged = [p.strip() for p in _re.split(r"[,\n]", files_arg) if p.strip()]
    else:
        import subprocess as _subprocess

        try:
            _diff = _subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                check=False,
            )
            staged = (
                [ln.strip() for ln in _diff.stdout.splitlines() if ln.strip()]
                if _diff.returncode == 0
                else []
            )
        except (FileNotFoundError, OSError):
            staged = []
    session = _session_lifecycle.load_active_session()
    result = vibecoding_guard.classify(session, staged)
    machine = bool(getattr(args, "machine_readable", False))
    record = bool(getattr(args, "record", False))
    off_spec = bool(result.off_spec_files)

    if record and off_spec:
        _session_lifecycle.emit_off_spec(
            "pending",
            result.off_spec_files,
            result.claimed_intent_id,
            result.reason,
        )

    exit_code = 0 if (not staged or result.reason == vibecoding_guard.REASON_ON_SPEC) else 3

    if machine:
        envelope = {
            "off_spec": off_spec,
            "off_spec_files": result.off_spec_files,
            "in_scope_files": result.in_scope_files,
            "claimed_intent": result.claimed_intent_id,
            "reason": result.reason,
        }
        print(json.dumps(envelope, sort_keys=True, ensure_ascii=False))
        return exit_code

    if exit_code == 0:
        claimed = result.claimed_intent_id or "the claimed Intent"
        print(
            f"vibecoding-check: all {len(staged)} staged file(s) "
            f"in scope of {claimed}."
        )
        return 0

    claimed = result.claimed_intent_id or "none — no session bound"
    print("dekspec: vibecoding-check OFF-SPEC — staged files outside the claimed scope.", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"  Claimed Intent: {claimed}", file=sys.stderr)
    print(f"  Reason: {result.reason}", file=sys.stderr)
    print("  Off-spec files:", file=sys.stderr)
    for path in result.off_spec_files:
        print(f"      {path}", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Two ways forward:", file=sys.stderr)
    print(
        "      1. Expand the claimed Intent's `Components affected` so the work is captured.",
        file=sys.stderr,
    )
    print(
        "      2. Set DEKSPEC_VIBECODING=1 to proceed as recorded vibecoding.",
        file=sys.stderr,
    )
    return 3


def cmd_session_report(args: argparse.Namespace) -> int:
    """Summarize off-spec drift recorded during the active session.

    Read-only — never mutates session state. Always exits 0 on a normal
    run; an off-spec count > 0 is reported, not treated as an error.
    """
    session = _session_lifecycle.load_active_session()
    machine = bool(getattr(args, "machine_readable", False))

    if session is None:
        if machine:
            print(
                json.dumps(
                    {"active": False, "off_spec_commit_count": 0, "off_spec_commits": []},
                    sort_keys=True,
                    ensure_ascii=False,
                )
            )
        else:
            print("No active session — nothing to report.")
        return 0

    records = list(session.off_spec_commits)
    if machine:
        print(
            json.dumps(
                {
                    "active": True,
                    "off_spec_commit_count": len(records),
                    "off_spec_commits": records,
                },
                sort_keys=True,
                ensure_ascii=False,
            )
        )
        return 0

    if not records:
        print("No off-spec drift recorded this session.")
        return 0

    print(
        f"Off-spec drift this session: {len(records)} commit(s) touched "
        "files outside the claimed Intent's scope."
    )
    for record in records:
        print("")
        print(f"  {record.get('ts', '?')}  (commit {record.get('commit_sha', '?')})")
        print(f"      reason: {record.get('reason', '?')}")
        print(f"      claimed Intent: {record.get('claimed_intent') or 'none'}")
        print("      off-spec files:")
        for path in record.get("off_spec_files", []):
            print(f"          {path}")
    print("")
    print("  Ratify or revert:")
    print(
        "      ratify — file an Intent, or expand the claimed Intent's "
        "`Components affected`, so the work is captured."
    )
    print("      revert — drop the off-spec changes.")
    return 0
# --------------------------------------------------------------------------- #
# id — DRAFT-slug temp-ID allocation (INT-020)
# --------------------------------------------------------------------------- #

# Artifact dirs scanned for DRAFT files. (dirname, recursive) — mirrors
# SpecGraph.load's layout.
_ID_ARTIFACT_DIRS: tuple[tuple[str, bool], ...] = (
    ("adrs", False),
    ("architecture-elements", False),
    ("working-specs", False),
    ("interface-contracts", False),
    ("security-profiles", False),
    ("impl-briefs", True),
    ("intents", True),
    ("missions", True),
)

# Per-kind canonical filename glob, used by reconcile --import-existing.
_ID_KIND_GLOBS: tuple[tuple[str, str, bool], ...] = (
    ("ADR", "adrs", False),
    ("AE", "architecture-elements", False),
    ("WS", "working-specs", False),
    ("IC", "interface-contracts", False),
    ("SP", "security-profiles", False),
    ("IB", "impl-briefs", True),
    ("INT", "intents", True),
    ("MSN", "missions", True),
)

_ID_IB_SPEC_RE = _re.compile(r"^\*\*Spec:\*\*\s.*?(WS-\d{3,})", _re.MULTILINE)
_ID_CANONICAL_FILENAME_RE = _re.compile(
    r"^(ADR|AE|WS|IC|IB|INT|MSN|SP)-(\d{3,})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)


def _add_id_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "id",
        help="Allocate canonical IDs to DRAFT-slug artifacts (INT-020).",
        description=(
            "ID-allocation toolchain. DekSpec artifacts authored concurrently "
            "carry temporary `<KIND>-DRAFT-<slug>` IDs during a session; "
            "`dekspec id allocate` assigns canonical `<KIND>-NNN` IDs at commit "
            "time against the append-only `dekspec/registry.yaml` ledger."
        ),
    )
    id_sub = p.add_subparsers(dest="id_command", metavar="<id-command>")

    p_alloc = id_sub.add_parser(
        "allocate",
        help="Assign canonical IDs to every DRAFT-slug artifact in the tree.",
    )
    p_alloc.add_argument(
        "--at", help="Repo root (default: current working directory)."
    )
    p_alloc.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="DekSpec content tree relative to repo root (default: dekspec).",
    )
    p_alloc.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the renumber plan without applying any change.",
    )
    p_alloc.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    p_alloc.set_defaults(func=cmd_id_allocate)

    p_recon = id_sub.add_parser(
        "reconcile",
        help="Re-run allocation post-merge, or import an existing corpus.",
    )
    p_recon.add_argument(
        "--at", help="Repo root (default: current working directory)."
    )
    p_recon.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="DekSpec content tree relative to repo root (default: dekspec).",
    )
    p_recon.add_argument(
        "--import-existing",
        action="store_true",
        help=(
            "One-time migration: walk the existing canonical "
            "`<KIND>-NNN-<slug>.md` corpus and populate "
            "`dekspec/registry.yaml`. Idempotent — IDs already present "
            "are skipped."
        ),
    )
    p_recon.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without applying any change.",
    )
    p_recon.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt.",
    )
    p_recon.set_defaults(func=cmd_id_reconcile)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


def _id_scan_draft_files(dekspec_dir: Path) -> list[Path]:
    """Return every `<KIND>-DRAFT-<slug>.md` file under the artifact dirs,
    sorted by path."""
    from .draft_ids import is_draft_filename

    found: list[Path] = []
    for dirname, recursive in _ID_ARTIFACT_DIRS:
        d = dekspec_dir / dirname
        if not d.exists():
            continue
        iterator = d.rglob("*.md") if recursive else d.glob("*.md")
        for p in iterator:
            if is_draft_filename(p.name):
                found.append(p)
    return sorted(found)


def _id_collect_corpus_ids(dekspec_dir: Path) -> dict[str, list[str]]:
    """Collect canonical IDs already on disk, grouped by kind prefix."""
    from .draft_ids import KINDS

    by_kind: dict[str, list[str]] = {k: [] for k in KINDS}
    for dirname, recursive in _ID_ARTIFACT_DIRS:
        d = dekspec_dir / dirname
        if not d.exists():
            continue
        iterator = d.rglob("*.md") if recursive else d.glob("*.md")
        for p in iterator:
            m = _ID_CANONICAL_FILENAME_RE.match(p.name)
            if m:
                by_kind.setdefault(m.group(1), []).append(
                    f"{m.group(1)}-{m.group(2)}"
                )
    return by_kind


def _id_ib_parent_ws(path: Path) -> str | None:
    """Best-effort extraction of an IB's parent WS ID from its **Spec:** line."""
    try:
        m = _ID_IB_SPEC_RE.search(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    return m.group(1) if m else None


def cmd_id_allocate(args: argparse.Namespace) -> int:
    import datetime as _dt

    from . import registry as _registry
    from .draft_ids import canonical_filename, draft_id, parse_draft_filename

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    dekspec_dir = repo_root / args.dekspec_root
    if not dekspec_dir.exists():
        print(f"Error: no DekSpec tree at {dekspec_dir}.", file=sys.stderr)
        return 2

    draft_files = _id_scan_draft_files(dekspec_dir)
    if not draft_files:
        print("No DRAFT-slug artifacts found — nothing to allocate.")
        return 0

    reg = _registry.load_registry(repo_root, args.dekspec_root)
    corpus_ids = _id_collect_corpus_ids(dekspec_dir)

    # Build the plan. `assigned` accumulates IDs already handed out this run
    # so two same-kind DRAFTs don't collide on the same next-free number.
    today = _dt.date.today().isoformat()
    plan: list[dict[str, Any]] = []
    assigned_by_kind: dict[str, list[str]] = {}
    new_entries: list[_registry.RegistryEntry] = []
    for path in draft_files:
        kind, slug = parse_draft_filename(path.name)
        pool = list(corpus_ids.get(kind, [])) + assigned_by_kind.get(kind, [])
        canonical = _registry.next_canonical_id(kind, reg, pool)
        assigned_by_kind.setdefault(kind, []).append(canonical)
        number = canonical.split("-", 1)[1]
        new_name = canonical_filename(kind, number, slug)
        old_id = draft_id(kind, slug)
        parent_ws = _id_ib_parent_ws(path) if kind == "IB" else None
        plan.append({
            "kind": kind,
            "slug": slug,
            "old_path": path,
            "new_path": path.with_name(new_name),
            "old_id": old_id,
            "new_id": canonical,
            "parent_ws_id": parent_ws,
        })
        new_entries.append(_registry.RegistryEntry(
            kind=kind,
            id=canonical,
            slug=slug,
            allocated=today,
            allocated_by="git-conflict",
            parent_ws_id=parent_ws,
        ))

    # Print the plan.
    print(f"Renumber plan — {len(plan)} DRAFT artifact(s):\n")
    for row in plan:
        rel_old = row["old_path"].relative_to(repo_root)
        rel_new = row["new_path"].relative_to(repo_root)
        print(f"  {row['old_id']}  ->  {row['new_id']}")
        print(f"    {rel_old}")
        print(f"    -> {rel_new}")
    print()

    if args.dry_run:
        print("[dry-run] no changes applied.")
        return 0

    # Confirmation gate.
    if not args.yes:
        if not sys.stdin.isatty():
            print(
                "Refusing to apply in a non-interactive context without "
                "--yes (or use --dry-run to preview).",
                file=sys.stderr,
            )
            return 2
        reply = input("Apply this renumber plan? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted — no changes applied.")
            return 1

    # Apply atomically: stage every write, then commit it. We rewrite IDs in
    # ALL artifact files (renamed DRAFT files + canonical siblings) so
    # cross-references resolve, then perform the renames, then append the
    # registry. The registry append is validated before write.
    id_map = {row["old_id"]: row["new_id"] for row in plan}
    rewrites = _id_build_rewrites(dekspec_dir, plan, id_map)

    for target_path, new_text in rewrites.items():
        target_path.write_text(new_text, encoding="utf-8")
    for row in plan:
        row["old_path"].rename(row["new_path"])
    _registry.append_entries(repo_root, new_entries, args.dekspec_root)

    print(
        f"Allocated {len(plan)} canonical ID(s); appended to "
        f"{_registry.registry_path(repo_root, args.dekspec_root).relative_to(repo_root)}."
    )
    return 0


def _id_build_rewrites(
    dekspec_dir: Path,
    plan: list[dict[str, Any]],
    id_map: dict[str, str],
) -> dict[Path, str]:
    """Compute the set of file edits: every artifact .md whose body contains
    a DRAFT ID being allocated gets that ID rewritten to its canonical form.

    Returns {path: new_text} for files that actually changed. The DRAFT files
    themselves are keyed by their *current* (pre-rename) path — the caller
    writes the new text, then renames.
    """
    # Whole-token regex per draft id so `IC-DRAFT-foo` does not partially
    # match inside `IC-DRAFT-foobar`.
    patterns = {
        old: _re.compile(r"(?<![\w-])" + _re.escape(old) + r"(?![\w-])")
        for old in id_map
    }
    rewrites: dict[Path, str] = {}
    for dirname, recursive in _ID_ARTIFACT_DIRS:
        d = dekspec_dir / dirname
        if not d.exists():
            continue
        iterator = d.rglob("*.md") if recursive else d.glob("*.md")
        for path in iterator:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            new_text = text
            for old, pat in patterns.items():
                new_text = pat.sub(id_map[old], new_text)
            if new_text != text:
                rewrites[path] = new_text
    return rewrites


def cmd_id_reconcile(args: argparse.Namespace) -> int:
    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    dekspec_dir = repo_root / args.dekspec_root
    if not dekspec_dir.exists():
        print(f"Error: no DekSpec tree at {dekspec_dir}.", file=sys.stderr)
        return 2

    if args.import_existing:
        return _id_reconcile_import(args, repo_root, dekspec_dir)

    # Plain reconcile: re-run allocation against the (possibly post-merge)
    # registry state — reassigns local DRAFT artifacts whose tentative IDs
    # now collide. Functionally identical to `allocate` from the working
    # tree's perspective: allocate always recomputes next-free against the
    # current registry + corpus.
    return cmd_id_allocate(args)


def _id_reconcile_import(
    args: argparse.Namespace, repo_root: Path, dekspec_dir: Path
) -> int:
    import datetime as _dt

    from . import registry as _registry

    reg = _registry.load_registry(repo_root, args.dekspec_root)
    existing_ids = {e.id for e in _registry.iter_entries(reg)}
    today = _dt.date.today().isoformat()

    new_entries: list[_registry.RegistryEntry] = []
    for kind, dirname, recursive in _ID_KIND_GLOBS:
        d = dekspec_dir / dirname
        if not d.exists():
            continue
        iterator = d.rglob("*.md") if recursive else d.glob("*.md")
        for path in sorted(iterator):
            m = _ID_CANONICAL_FILENAME_RE.match(path.name)
            if not m or m.group(1) != kind:
                continue
            canonical = f"{kind}-{m.group(2)}"
            slug = m.group(3)
            if canonical in existing_ids:
                continue  # idempotent — already imported
            parent_ws = _id_ib_parent_ws(path) if kind == "IB" else None
            new_entries.append(_registry.RegistryEntry(
                kind=kind,
                id=canonical,
                slug=slug,
                allocated=today,
                allocated_by="git-conflict",
                parent_ws_id=parent_ws,
            ))
            existing_ids.add(canonical)

    if not new_entries:
        print("Registry already covers every canonical artifact — nothing to import.")
        return 0

    print(f"Import plan — {len(new_entries)} canonical artifact(s):\n")
    for e in new_entries:
        print(f"  + {e.id}  ({e.slug})")
    print()

    if args.dry_run:
        print("[dry-run] no changes applied.")
        return 0

    if not args.yes:
        if not sys.stdin.isatty():
            print(
                "Refusing to apply in a non-interactive context without "
                "--yes (or use --dry-run to preview).",
                file=sys.stderr,
            )
            return 2
        reply = input(
            f"Import {len(new_entries)} entries into the registry? [y/N] "
        ).strip().lower()
        if reply not in ("y", "yes"):
            print("Aborted — no changes applied.")
            return 1

    _registry.append_entries(repo_root, new_entries, args.dekspec_root)
    print(
        f"Imported {len(new_entries)} entries into "
        f"{_registry.registry_path(repo_root, args.dekspec_root).relative_to(repo_root)}."
    )
    return 0


# --------------------------------------------------------------------------- #
# ingest
# --------------------------------------------------------------------------- #


def _add_ingest_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "ingest",
        help="Classify a brownfield markdown document into draft DekSpec artifacts.",
        description=(
            "Read an inherited markdown design document, classify each of its "
            "sections into a draft DekSpec IR type via a deterministic "
            "heuristic classifier, and write a directory of draft artifacts "
            "(status DRAFT) plus a confidence-scored classification report into "
            "a staging directory. No artifact is promoted automatically — every "
            "output is a draft for human review. Markdown is the only supported "
            "input format at this release."
        ),
    )
    p.add_argument(
        "path",
        help="Path to the source markdown document (.md) to ingest.",
    )
    p.add_argument(
        "--out",
        metavar="DIR",
        help=(
            "Staging directory for the draft artifacts + report. Defaults to a "
            "fresh ./dekspec-ingest-<timestamp>/ directory. Never the live "
            "dekspec/ tree."
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit the classification report as JSON instead of text.",
    )
    p.set_defaults(func=cmd_ingest)


def cmd_ingest(args: argparse.Namespace) -> int:
    """Thin adapter over `dekspec.ingest.run` — no domain logic here (AE-005)."""
    from .ingest import IngestError, run
    from .ingest.runner import result_json, result_summary

    try:
        result = run(args.path, out_dir=args.out)
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(result_json(result), end="")
    else:
        print(result_summary(result))
    return 0


# --------------------------------------------------------------------------- #
# archeology — brownfield spec-gap detection (INT-030 / IB-118)
# --------------------------------------------------------------------------- #


def _add_archeology_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "archeology",
        help="Brownfield spec-gap archeology — find code no LOCKED Intent claims.",
        description=(
            "The deterministic substrate behind the /dekspec:archeology skill. "
            "The `coverage` verb walks the repo, collects every LOCKED Intent's "
            "Components-affected glob set, and reports the files no Intent "
            "claims — the spec-orphaned surfaces a brownfield-recovery workflow "
            "should backfill. Implements INT-030."
        ),
    )
    arch_sub = p.add_subparsers(dest="archeology_command", metavar="<archeology-command>")

    p_cov = arch_sub.add_parser(
        "coverage",
        help="Report files not claimed by any LOCKED Intent's Components-affected globs.",
    )
    p_cov.add_argument(
        "--at",
        default=".",
        help="Path to the repo to scan (default: current working directory).",
    )
    p_cov.add_argument(
        "--json",
        action="store_true",
        help="Emit the gap report as a JSON array instead of a Markdown table.",
    )
    p_cov.set_defaults(func=cmd_archeology_coverage)

    p.set_defaults(func=lambda _args: (p.print_help() or 0))


def cmd_archeology_coverage(args: argparse.Namespace) -> int:
    """Thin adapter over `dekspec.archeology.coverage.run` — no domain logic
    here (AE-005). Calls `run`, then formats the result as a Markdown table
    (default) or a JSON array (`--json`); both share the single `run` call.
    """
    from .archeology import coverage as _coverage

    try:
        gaps = _coverage.run(args.at)
    except _coverage.CoverageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    repo_root = str(Path(args.at).resolve())

    if args.json:
        envelope = {
            "summary": {"total": len(gaps)},
            "repo_root": repo_root,
            "gaps": [g.to_dict() for g in gaps],
        }
        print(json.dumps(envelope, indent=2))
        return 0

    print(f"DekSpec archeology coverage — {repo_root}")
    print(f"Spec-orphaned files: {len(gaps)}")
    print()
    print("| Path | Last modified | Claimed by Intent |")
    print("|------|---------------|-------------------|")
    if not gaps:
        print("| _(none — every file is claimed by a LOCKED Intent)_ |  |  |")
    else:
        for g in gaps:
            claimed = g.claimed_by_intent or "—"
            print(f"| {g.path} | {g.last_modified} | {claimed} |")
    return 0


# --------------------------------------------------------------------------- #
# lint-ib — structural and syntactic Implementation Brief linter (INT-074)
# --------------------------------------------------------------------------- #


def _add_lint_ib_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "lint-ib",
        help="Lint an Implementation Brief structurally and syntactically.",
        description=(
            "Parse the target Implementation Brief markdown file, run structural and "
            "syntactic lint rules, and output a diagnostic report. If blocking issues "
            "are found, the tool returns a non-zero exit code."
        ),
    )
    p.add_argument(
        "path", help="Path to the Implementation Brief markdown file to lint."
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit lint violations as JSON instead of formatted text.",
    )
    p.set_defaults(func=cmd_lint_ib)


def cmd_lint_ib(args: argparse.Namespace) -> int:
    from .constraint_compiler.linter import lint_ib
    src = Path(args.path).resolve()
    if not src.exists():
        print(f"Error: file not found: {src}", file=sys.stderr)
        return 2

    violations = lint_ib(src)
    if args.json:
        print(json.dumps({"ok": len(violations) == 0, "violations": violations}, indent=2))
    else:
        if not violations:
            print(f"OK — {src.name} is structurally and syntactically clean.")
        else:
            print(f"Lint findings in {args.path}:", file=sys.stderr)
            for v in violations:
                line_str = f"L{v['line']}" if v["line"] is not None else "L?"
                severity = v.get("severity", "P1")
                print(f"  [{severity}] {line_str}: ({v['rule']}) {v['message']}", file=sys.stderr)

    blocking_violations = [v for v in violations if v.get("severity") in ("P1", "P2")]
    if blocking_violations:
        return 1
    return 0


_PROMOTE_PROVISIONAL_RETIRED_MESSAGE = (
    "Error: `dekspec repo promote-provisional` was retired 2026-05-25 (F2 audit: "
    "zero CLI invocations in repo history; every promotion was hand-promote). "
    "Promote provisional artifacts manually — see `docs/dekspec-operating-guide.md` "
    "§Provisional Promotion (hand-promote workflow). The underlying promotion "
    "helpers (dekspec.promote.plan_promotion / apply_promotion / render_plan) "
    "remain importable for tooling that needs them."
)


def _add_promote_provisional_retired_subparser(sub: argparse._SubParsersAction) -> None:
    """Retired-verb stub for `dekspec repo promote-provisional`.

    The CLI verb was retired 2026-05-25 per F2 audit; the underlying
    promotion logic in `dekspec.promote` stays for the hand-promote
    workflow. The subparser is preserved so invocations land on a
    helpful error rather than argparse's generic "invalid choice".
    """
    p = sub.add_parser(
        "promote-provisional",
        help="(retired 2026-05-25) Hand-promote provisional artifacts; see docs.",
        description=(
            "Retired 2026-05-25 (F2 audit). Promote provisional artifacts "
            "manually — see `docs/dekspec-operating-guide.md` §Provisional "
            "Promotion (hand-promote workflow)."
        ),
    )
    # Accept (and ignore) every legacy positional / flag so any historical
    # invocation lands on the retired-verb message rather than an argparse
    # "unrecognized arguments" error.
    p.add_argument("slug", nargs="?", help=argparse.SUPPRESS)
    p.add_argument("--at", help=argparse.SUPPRESS)
    p.add_argument("--dekspec-root", default="dekspec", help=argparse.SUPPRESS)
    p.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_promote_provisional_retired)


def cmd_promote_provisional_retired(args: argparse.Namespace) -> int:
    print(_PROMOTE_PROVISIONAL_RETIRED_MESSAGE, file=sys.stderr)
    return 2


_PROVISIONAL_BRANCH_PREFIX: dict[str, str] = {
    "INT": "int",
    "MSN": "mission",
    "ADR": "feat",
    "AE": "feat",
    "IC": "feat",
    "WS": "feat",
    "IB": "feat",
    "SP": "feat",
}

# Canonical directory (relative to the dekspec content root) per IR kind.
# ADR-043 generalizes provisional/canonical authoring beyond INT/MSN to every
# kind; this mirrors `promote.KIND_TO_DIR` (the promotion-target mapping) so a
# `--canonical` author-target and its eventual promotion agree on the home dir.
_CANONICAL_DIR_BY_KIND: dict[str, str] = {
    "INT": "intents",
    "MSN": "missions",
    "ADR": "adrs",
    "AE": "architecture-elements",
    "IC": "interface-contracts",
    "WS": "working-specs",
    "IB": "impl-briefs/queued",
    "SP": "security-profiles",
}


class AuthorTarget(NamedTuple):
    """Result of the provisional-vs-canonical routing decision (INT-133 /
    ADR-030).

    The single source of truth for where a Creation-mode artifact lands and
    whether a canonical id is allocated. Both /write-intent and /write-mission
    consult this via the `dekspec repo author-target` verb; no routing logic is
    duplicated in skill prose.

    Attributes:
        target_dir: directory the new artifact lands in, relative to the repo
            root (e.g. `dekspec/provisional`, `dekspec/provisional/<slug>`, or
            `dekspec/intents`). String-ified Path for JSON-friendliness.
        allocate_canonical: True iff a canonical id (INT-NNN / MSN-NNN) should
            be allocated for this artifact. False for the provisional default.
    """

    target_dir: str
    allocate_canonical: bool


def resolve_author_target(
    kind: str,
    canonical: bool,
    *,
    slug: str | None = None,
    dekspec_root: str = "dekspec",
) -> AuthorTarget:
    """Deterministic Creation-mode routing (INT-133 / ADR-030 hard default).

    Default posture (no opt-out): no canonical id is allocated and the artifact
    lands under `<dekspec_root>/provisional/` (nested under `<slug>/` when a
    slug is supplied, matching `repo new-provisional`'s layout). Passing
    `canonical=True` (the `--canonical` opt-out) routes to the canonical dir for
    the kind and signals that a canonical id should be allocated.

    Pure + importable: takes no filesystem or git state; the caller composes
    the returned relative dir with its repo root.
    """
    kind = kind.upper()
    if canonical:
        try:
            canonical_dir = _CANONICAL_DIR_BY_KIND[kind]
        except KeyError:
            raise ValueError(
                f"--canonical authoring not supported for kind {kind!r}; "
                f"known kinds: {sorted(_CANONICAL_DIR_BY_KIND)}"
            ) from None
        return AuthorTarget(
            target_dir=str(Path(dekspec_root) / canonical_dir),
            allocate_canonical=True,
        )
    provisional = Path(dekspec_root) / "provisional"
    if slug:
        provisional = provisional / slug
    return AuthorTarget(target_dir=str(provisional), allocate_canonical=False)


def _add_new_provisional_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "new-provisional",
        help="Scaffold a new provisional artifact + git branch.",
        description=(
            "Create a skeleton provisional artifact under "
            "dekspec/provisional/<incubation-slug>/ and (by default) check "
            "out a fresh git branch named for the artifact. Use to start "
            "exploratory work whose canonical ID has not yet been allocated."
        ),
    )
    p.add_argument(
        "kind",
        choices=sorted(["INT", "MSN", "ADR", "AE", "IC", "WS", "IB", "SP"]),
        help="IR kind (uppercase abbreviation).",
    )
    p.add_argument(
        "slug",
        help=(
            "Incubation slug. For Missions this names the folder; for child "
            "Intents it can match the parent Mission's incubation slug + a "
            "topic-specific suffix in the filename."
        ),
    )
    p.add_argument(
        "--title",
        default=None,
        help="Optional one-line title for the H1 heading.",
    )
    p.add_argument(
        "--at",
        help="Path to the consumer repo (default: current working directory).",
    )
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Subdirectory under repo root that holds the spec tree (default: dekspec).",
    )
    p.add_argument(
        "--incubation",
        default=None,
        help=(
            "Incubation folder name (default: derived from <slug>). Use when "
            "authoring a child artifact under an existing Mission's "
            "incubation folder."
        ),
    )
    p.add_argument(
        "--no-branch",
        action="store_true",
        help=(
            "Skip the `git checkout -b` step. By default a fresh branch is "
            "created (e.g. int/INT-provisional-<slug>)."
        ),
    )
    p.set_defaults(func=cmd_new_provisional)


def cmd_new_provisional(args: argparse.Namespace) -> int:
    """Scaffold a provisional artifact + branch."""
    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    dekspec_dir = repo_root / args.dekspec_root
    if not dekspec_dir.is_dir():
        print(
            f"Error: dekspec tree not found at {dekspec_dir}. "
            f"Run `dekspec init` first.",
            file=sys.stderr,
        )
        return 1
    kind = args.kind
    slug = args.slug
    incubation_name = args.incubation or slug
    incubation_dir = dekspec_dir / "provisional" / incubation_name
    artifact_path = incubation_dir / f"{kind}-provisional-{slug}.md"
    if artifact_path.exists():
        print(
            f"Error: {artifact_path.relative_to(repo_root)} already exists.",
            file=sys.stderr,
        )
        return 1
    incubation_dir.mkdir(parents=True, exist_ok=True)
    title = args.title or f"{kind}-provisional-{slug} — TODO: write title"
    body = _render_provisional_skeleton(kind, slug, title, incubation_name)
    artifact_path.write_text(body, encoding="utf-8")
    print(f"Created {artifact_path.relative_to(repo_root)}")

    if args.no_branch:
        print("(--no-branch) Skipped git branch creation.")
        return 0
    branch_prefix = _PROVISIONAL_BRANCH_PREFIX[kind]
    branch_name = f"{branch_prefix}/{kind}-provisional-{slug}".lower()
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            check=True,
            capture_output=True,
            cwd=str(repo_root),
        )
        print(f"Checked out branch `{branch_name}`.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Branch already exists (CalledProcessError) or git not on PATH.
        # Surface the failure but don't unwind the file creation; the
        # engineer can switch manually.
        stderr = ""
        if hasattr(e, "stderr") and e.stderr:
            stderr = e.stderr.decode("utf-8", errors="replace").strip()
        print(
            f"Branch checkout failed ({stderr or type(e).__name__}). "
            f"File created; switch branch manually if needed.",
            file=sys.stderr,
        )
        return 0
    return 0


def _add_author_target_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "author-target",
        help="Resolve where a Creation-mode artifact lands (provisional vs canonical).",
        description=(
            "The single source of truth for the Creation-mode routing decision "
            "(INT-133 / ADR-030 hard default). Prints JSON with the target "
            "directory and whether a canonical id should be allocated.\n\n"
            "Default posture (no flag): provisional — the artifact lands under "
            "`dekspec/provisional/` and NO canonical id is allocated. Passing "
            "`--canonical` opts into canonical-direct authoring: the target is "
            "the canonical dir for the kind (intents/ for INT, missions/ for "
            "MSN) and a canonical id is allocated. The /write-intent and "
            "/write-mission skills call this verb rather than duplicating the "
            "routing prose."
        ),
    )
    p.add_argument(
        "--kind",
        required=True,
        choices=sorted(_CANONICAL_DIR_BY_KIND),
        help="IR kind (uppercase abbreviation).",
    )
    p.add_argument(
        "--canonical",
        action="store_true",
        help=(
            "Opt into canonical-direct authoring: allocate a canonical id and "
            "land in the canonical dir. Default (omitted) routes to provisional."
        ),
    )
    p.add_argument(
        "--slug",
        default=None,
        help=(
            "Optional incubation slug. When supplied (and not --canonical), the "
            "provisional target nests under dekspec/provisional/<slug>/."
        ),
    )
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Subdirectory under repo root that holds the spec tree (default: dekspec).",
    )
    p.set_defaults(func=cmd_author_target)


def cmd_author_target(args: argparse.Namespace) -> int:
    """Thin wrapper over `resolve_author_target` — prints the routing decision
    as JSON for the authoring skills to consume."""
    target = resolve_author_target(
        args.kind,
        canonical=args.canonical,
        slug=args.slug,
        dekspec_root=args.dekspec_root,
    )
    print(
        json.dumps(
            {
                "kind": args.kind.upper(),
                "canonical": bool(args.canonical),
                "target_dir": target.target_dir,
                "allocate_canonical": target.allocate_canonical,
            },
            indent=2,
        )
    )
    return 0


def _render_provisional_skeleton(
    kind: str, slug: str, title: str, incubation_name: str
) -> str:
    """Minimal frontmatter + PROVISIONAL banner + status + amendment-log
    skeleton. Engineer fills in the rest via the corresponding write-*
    skill or manual editing."""
    kind_long = {
        "INT": "Intent",
        "MSN": "Mission",
        "ADR": "Architecture Decision Record",
        "AE":  "Architecture Element",
        "IC":  "Interface Contract",
        "WS":  "Working Spec",
        "IB":  "Implementation Brief",
        "SP":  "Security Profile",
    }[kind]
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Mission parser requires the literal "Mission" word in H1
    # (`# Mission MSN-NNN: <title>`). Other kinds use bare `# <id>: ...`.
    h1_prefix = "Mission " if kind == "MSN" else ""
    return (
        f"# {h1_prefix}{kind}-provisional-{slug}: {title}\n\n"
        f"> **PROVISIONAL.** This {kind_long} lives at "
        f"`dekspec/provisional/{incubation_name}/`. "
        f"Hand-promote to canonical via `dekspec repo promote-provisional "
        f"{incubation_name}` (or the procedure in INT-079 §Motivation) "
        f"when ready to ratify.\n\n"
        f"## Status\n\nDRAFT\n\n"
        f"## Created\n\n{today}\n\n"
        f"## Modified\n\n{today}\n\n"
        f"## Motivation\n\n_TODO: describe why this {kind_long} exists._\n\n"
        f"## Amendment Log\n\n"
        f"| Date | Type | Change | Author |\n"
        f"|---|---|---|---|\n"
        f"| {today} | Create | Scaffolded via `dekspec repo new-provisional "
        f"{kind} {slug}`. | TODO |\n"
    )


def _add_regen_indexes_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "regen-indexes",
        help="Deterministically regenerate derived index files.",
        description=(
            "Walks the canonical artifact tree via SpecGraph and rewrites the "
            "table region of each derived index file (intent-index.md "
            "today; mission-index + others land as follow-on). Prose around "
            "the table is preserved. Rows sort by numeric ID ascending so "
            "concurrent additions from multiple branches converge to the same "
            "ordering after merge, eliminating the index-line merge-conflict "
            "friction documented in INT-provisional-multi-user-coordination-"
            "analysis."
        ),
    )
    p.add_argument(
        "--at",
        help="Path to the consumer repo (default: current working directory).",
    )
    p.add_argument(
        "--dekspec-root",
        default="dekspec",
        help="Subdirectory under repo root that holds the spec tree (default: dekspec).",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Dry-run: report whether the index would change; do not write.",
    )
    p.set_defaults(func=cmd_regen_indexes)


def cmd_regen_indexes(args: argparse.Namespace) -> int:
    from . import index_ops

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    results = index_ops.regen_all(
        repo_root,
        dekspec_root=args.dekspec_root,
        dry_run=args.check,
    )
    any_changed = False
    for r in results:
        rel = r.path.relative_to(repo_root)
        if r.changed:
            verb = "would update" if args.check else "updated"
            print(f"  {verb}  {rel}  ({r.rows_emitted} rows)")
            any_changed = True
        else:
            print(f"  unchanged  {rel}  ({r.rows_emitted} rows)")
    if args.check and any_changed:
        return 1
    return 0


def _add_cow_stage_subparser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "cow-stage",
        help="Copy-on-write stage a canonical artifact into a provisional folder.",
        description=(
            "Look up which pre-ACCEPTED Intent (if any) claims the canonical "
            "artifact's path via its Components-affected globs. Copy the "
            "canonical to `dekspec/provisional/<incubation-slug>/`, rename "
            "using the `<KIND>-provisional-<slug>` convention, and stamp "
            "`replaces: <CANONICAL-ID>` in frontmatter. Returns the new path.\n\n"
            "This is the write-time half of the CoW spec staging discipline "
            "(INT-082). The authoring skills invoke this verb before any edit "
            "to a canonical artifact whose path is claimed by a pre-ACCEPTED "
            "Intent; the audit rule `T-COW-CANONICAL-EDITED` catches direct-"
            "edit bypasses that skip this verb."
        ),
    )
    p.add_argument(
        "canonical_path",
        help="Path to the canonical artifact to copy-on-write (relative to repo root).",
    )
    p.add_argument(
        "--incubation",
        default=None,
        help="Incubation folder name. Default: derived from the claiming Intent.",
    )
    p.add_argument(
        "--at",
        help="Path to the consumer repo (default: current working directory).",
    )
    p.set_defaults(func=cmd_cow_stage)


def cmd_cow_stage(args: argparse.Namespace) -> int:
    from . import cow_state

    repo_root = Path(args.at).resolve() if args.at else Path.cwd()
    target_rel = args.canonical_path
    claim = cow_state.is_path_claimed(repo_root, target_rel)
    incubation = args.incubation
    if incubation is None:
        if claim is None:
            print(
                f"Error: {target_rel} is not claimed by any pre-ACCEPTED Intent, "
                f"and no --incubation slug was supplied. "
                f"Either pass --incubation <slug> explicitly or stage the work "
                f"under a claiming Intent first.",
                file=sys.stderr,
            )
            return 1
        incubation = claim.incubation_slug
        if incubation is None:
            print(
                f"Error: claim found ({claim.intent_id}) but no incubation slug "
                f"could be derived. Pass --incubation <slug> explicitly.",
                file=sys.stderr,
            )
            return 1
    try:
        new_path = cow_state.cow_stage(repo_root, target_rel, incubation)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    rel = new_path.relative_to(repo_root)
    if claim:
        print(
            f"CoW staged: {target_rel}"
            f"\n  -> {rel}"
            f"\n  (claimed by {claim.intent_id} via `{claim.glob_pattern}`)"
        )
    else:
        print(
            f"CoW staged: {target_rel}"
            f"\n  -> {rel}"
            f"\n  (no Intent claim — staged under --incubation {incubation})"
        )
    print(
        "Edit the provisional copy; the canonical stays frozen. Run "
        "`dekspec repo promote-provisional " + incubation + "` when the "
        "originating Intent is ready to ACCEPT."
    )
    return 0


def _default_skills_source() -> Path:
    """Resolve the in-repo plugin source dir (`plugins/dekspec`).

    Walks up from this module to find a `plugins/dekspec` directory (repo
    layout). Returns the path even if absent — `emit` tolerates missing
    skills/commands/hooks subtrees gracefully.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "plugins" / "dekspec"
        if candidate.is_dir():
            return candidate
    # Fall back to the conventional location relative to the repo root.
    return here.parents[2] / "plugins" / "dekspec"


def _add_install_subparser(sub) -> None:
    p = sub.add_parser(
        "install",
        help="Emit the per-host skill/command/hook tree for a harness platform.",
        description=(
            "Repackage the single DekSpec plugin source into the file tree a "
            "harness host expects, so the skill suite is invocable on that "
            "host after one command. Writes files only — never executes."
        ),
    )
    p.add_argument(
        "--platform",
        required=True,
        choices=["claude", "codex", "antigravity", "cursor", "copilot", "pi"],
        help="Target harness host.",
    )
    p.add_argument(
        "--target",
        default=".",
        help="Directory to write the per-host tree into (default: cwd).",
    )
    p.add_argument(
        "--source",
        default=None,
        help=(
            "Plugin source dir (default: the in-repo plugins/dekspec). Used to "
            "override the skill/command/hook source."
        ),
    )
    p.set_defaults(func=cmd_install)


def cmd_install(args: argparse.Namespace) -> int:
    source_dir = Path(args.source) if args.source else _default_skills_source()
    target_dir = Path(args.target)
    try:
        result = platform_install.emit(
            args.platform, source_dir=source_dir, target_dir=target_dir
        )
    except HarnessUnsupported as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(
        f"Installed DekSpec for '{result.platform}' into {target_dir} "
        f"({len(result.written)} files):"
    )
    for path in result.written:
        try:
            shown = path.relative_to(target_dir)
        except ValueError:
            shown = path
        print(f"  {shown}")
    # Honesty guard: for non-claude hosts the skill/command/hook tree is copied
    # from the plugin source. A pip/pipx-installed engine does not carry that
    # source (the plugin is not bundled in the wheel), so only the host marker
    # gets written — don't let that look like a full install. Also point at the
    # separate command that actually updates vendored content + .dekspec-version.
    skills_present = (source_dir / "skills").is_dir()
    if not skills_present:
        print(
            f"\nWarning: only the host marker was written — the plugin "
            f"skills/commands/hooks tree was NOT found at {source_dir}. A "
            f"pip/pipx-installed engine does not bundle the plugin content, so "
            f"`dekspec install --platform {result.platform}` can emit only the "
            f"marker from it. Point --source at a `plugins/dekspec` checkout to "
            f"emit the full tree.",
            file=sys.stderr,
        )
    if result.platform != "claude":
        print(
            "\nNote: `dekspec install` emits only the per-host tree. To update "
            "vendored content + the .dekspec-version marker after an engine "
            "upgrade, run `dekspec sync` (that is what reconciles the version "
            "metadata, not `install`).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

