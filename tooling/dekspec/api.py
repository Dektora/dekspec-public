"""Public Python API for DekSpec.

This module re-exports the most useful classes + functions from across
the dekspec package so consumers can use a single, stable import path
instead of digging into submodules.

Stable as of v0.33.0. Anything imported through `dekspec.api` is a
public contract — breaking changes here will be called out in CHANGELOG
+ versioned per semver.

Quick start::

    from dekspec.api import (
        SpecGraph,
        audit_linkage,
        propose_fixes,
        apply_fixes,
        parse_ae,
        parse_adr,
        parse_ws,
        parse_intent,
        parse_mission,
    )

    # Load the whole spec graph from disk
    graph = SpecGraph.load("/path/to/repo", dekspec_root="dekspec")

    # Iterate by kind
    for ae in graph.aes():
        print(ae["id"], ae.get("status"))

    # Run the full audit battery
    findings = audit_linkage("/path/to/repo", dekspec_root="dekspec")

    # Auto-fix mechanical findings (L6/L7/L8 mirror gaps)
    fixes = propose_fixes("/path/to/repo")
    result = apply_fixes(fixes, dry_run=False)
    print(f"Applied {result['applied']} of {result['proposed']} fixes")

    # Parse a single artifact directly
    ir = parse_ae("/path/to/repo/dekspec/architecture-elements/AE-001-foo.md")
    print(ir["name"], ir.get("subtype"))
"""
from __future__ import annotations

# Library version
from . import __version__

from typing import TYPE_CHECKING as _TYPE_CHECKING

if _TYPE_CHECKING:
    # Specification policy (owned by DekSpec, consumed by orchestration clients)
    from .specification_policy import ReferencePolicy, ReferencePolicyError, load_policy

    # IR schema + parser version constants
    from .constraint_compiler import IR_SCHEMA_VERSION, PARSER_VERSION

    # Parser entry points (one per artifact type)
    from .constraint_compiler import (
        parse,           # alias for parse_ic; parses Interface Contracts
        parse_adr,
        parse_ae,
        parse_bs,
        parse_constitution,
        parse_glossary,
        parse_ib,
        parse_intent,
        parse_mission,
        parse_security_profile,
        parse_vision,
        parse_ws,
        lint_ib,
    )

    # Parse-error classes (per artifact type)
    from .constraint_compiler import (
        ADRParseError,
        AEParseError,
        BSParseError,
        ConstitutionParseError,
        GlossaryParseError,
        IBParseError,
        ICParseError,
        IntentParseError,
        MissionParseError,
        SPParseError,
        VisionParseError,
        WSParseError,
    )

    # The Behavior Specification kind's shared alias map (IB-207, O-12), and the
    # audit rule-id alias table it holds (IB-212, O-10)
    from .spec_kinds import (
        BEHAVIOR_SPEC_NAMES,
        RETIRED_RULE_ID_RENAMES,
        RULE_ID_ALIASES,
        canonical_rule_id,
    )

    # Constitution emitter (soft-layer L0 AGENTS.md emission)
    from .constraint_compiler import emit_constitution_markdown

    # Cross-artifact resolution (e.g., union AE implements_globs into IC.affected_paths)
    from .constraint_compiler import resolve_aes

    # SpecGraph — the load-once-and-query container
    from .constraint_compiler import SpecGraph, ParseFailure

    # Emitters
    from .constraint_compiler import agents_md, ci_gate, contract_test

    # Fidelity audit
    from .fidelity_audit import (
        Finding,
        Fix,
        apply_fixes,
        apply_status_fixes,
        audit_linkage,
        propose_fixes,
    )

    # Provisional → canonical promotion
    from .promote import PromoteError
    from .fidelity_audit.profiles import (
        AuditProfile,
        ProfileLoadError,
        ProfileNotFoundError,
        list_profiles as list_audit_profiles,
        load_profile as load_audit_profile,
    )

    # Run persistence + SQLite index
    from .constraint_compiler.persistence import (
        Run,
        RunWriter,
        open_run,
        repo_fingerprint,
        repo_runs_dir,
        repo_state_dir,
        xdg_data_root,
    )
    from .constraint_compiler.persistence_index import (
        INDEX_FILENAME,
        INDEX_SCHEMA_VERSION,
        open_index,
        query_runs,
        record_run,
        reindex,
    )

    # Vendoring drift detection (for consumer repos)
    from .vendoring import (
        DriftFinding,
        compute_drift,
        iter_vendored_pairs,
        library_root,
    )

    # Schema migrations
    from .migrations import (
        Migration,
        MigrationError,
        Registry,
        default_registry,
        migrate_ir,
        target_version_for,
    )

    # Schema access
    from .schemas import (
        LATEST_VERSIONS,
        SCHEMA_FILENAMES,
        SchemaNotFoundError,
        list_schemas,
        load_schema,
    )


# Brief identity remains eager: IB-241 requires these names in the API namespace.
from .brief_identity import (
    BriefIdentityError,
    BriefRef,
    list_briefs,
    resolve_brief,
)


# Resolve the remaining public exports on first access.
_LAZY_EXPORTS = {
    "ReferencePolicy": (".specification_policy", "ReferencePolicy"),
    "ReferencePolicyError": (".specification_policy", "ReferencePolicyError"),
    "load_policy": (".specification_policy", "load_policy"),
    "IR_SCHEMA_VERSION": (".constraint_compiler", "IR_SCHEMA_VERSION"),
    "PARSER_VERSION": (".constraint_compiler", "PARSER_VERSION"),
    "parse": (".constraint_compiler", "parse"),
    "parse_adr": (".constraint_compiler", "parse_adr"),
    "parse_ae": (".constraint_compiler", "parse_ae"),
    "parse_bs": (".constraint_compiler", "parse_bs"),
    "parse_constitution": (".constraint_compiler", "parse_constitution"),
    "parse_glossary": (".constraint_compiler", "parse_glossary"),
    "parse_ib": (".constraint_compiler", "parse_ib"),
    "parse_intent": (".constraint_compiler", "parse_intent"),
    "parse_mission": (".constraint_compiler", "parse_mission"),
    "parse_security_profile": (".constraint_compiler", "parse_security_profile"),
    "parse_vision": (".constraint_compiler", "parse_vision"),
    "parse_ws": (".constraint_compiler", "parse_ws"),
    "lint_ib": (".constraint_compiler", "lint_ib"),
    "ADRParseError": (".constraint_compiler", "ADRParseError"),
    "AEParseError": (".constraint_compiler", "AEParseError"),
    "BSParseError": (".constraint_compiler", "BSParseError"),
    "ConstitutionParseError": (".constraint_compiler", "ConstitutionParseError"),
    "GlossaryParseError": (".constraint_compiler", "GlossaryParseError"),
    "IBParseError": (".constraint_compiler", "IBParseError"),
    "ICParseError": (".constraint_compiler", "ICParseError"),
    "IntentParseError": (".constraint_compiler", "IntentParseError"),
    "MissionParseError": (".constraint_compiler", "MissionParseError"),
    "SPParseError": (".constraint_compiler", "SPParseError"),
    "VisionParseError": (".constraint_compiler", "VisionParseError"),
    "WSParseError": (".constraint_compiler", "WSParseError"),
    "BEHAVIOR_SPEC_NAMES": (".spec_kinds", "BEHAVIOR_SPEC_NAMES"),
    "RETIRED_RULE_ID_RENAMES": (".spec_kinds", "RETIRED_RULE_ID_RENAMES"),
    "RULE_ID_ALIASES": (".spec_kinds", "RULE_ID_ALIASES"),
    "canonical_rule_id": (".spec_kinds", "canonical_rule_id"),
    "emit_constitution_markdown": (".constraint_compiler", "emit_constitution_markdown"),
    "resolve_aes": (".constraint_compiler", "resolve_aes"),
    "SpecGraph": (".constraint_compiler", "SpecGraph"),
    "ParseFailure": (".constraint_compiler", "ParseFailure"),
    "agents_md": (".constraint_compiler", "agents_md"),
    "ci_gate": (".constraint_compiler", "ci_gate"),
    "contract_test": (".constraint_compiler", "contract_test"),
    "Finding": (".fidelity_audit", "Finding"),
    "Fix": (".fidelity_audit", "Fix"),
    "apply_fixes": (".fidelity_audit", "apply_fixes"),
    "apply_status_fixes": (".fidelity_audit", "apply_status_fixes"),
    "audit_linkage": (".fidelity_audit", "audit_linkage"),
    "propose_fixes": (".fidelity_audit", "propose_fixes"),
    "PromoteError": (".promote", "PromoteError"),
    "AuditProfile": (".fidelity_audit.profiles", "AuditProfile"),
    "ProfileLoadError": (".fidelity_audit.profiles", "ProfileLoadError"),
    "ProfileNotFoundError": (".fidelity_audit.profiles", "ProfileNotFoundError"),
    "list_audit_profiles": (".fidelity_audit.profiles", "list_profiles"),
    "load_audit_profile": (".fidelity_audit.profiles", "load_profile"),
    "Run": (".constraint_compiler.persistence", "Run"),
    "RunWriter": (".constraint_compiler.persistence", "RunWriter"),
    "open_run": (".constraint_compiler.persistence", "open_run"),
    "repo_fingerprint": (".constraint_compiler.persistence", "repo_fingerprint"),
    "repo_runs_dir": (".constraint_compiler.persistence", "repo_runs_dir"),
    "repo_state_dir": (".constraint_compiler.persistence", "repo_state_dir"),
    "xdg_data_root": (".constraint_compiler.persistence", "xdg_data_root"),
    "INDEX_FILENAME": (".constraint_compiler.persistence_index", "INDEX_FILENAME"),
    "INDEX_SCHEMA_VERSION": (".constraint_compiler.persistence_index", "INDEX_SCHEMA_VERSION"),
    "open_index": (".constraint_compiler.persistence_index", "open_index"),
    "query_runs": (".constraint_compiler.persistence_index", "query_runs"),
    "record_run": (".constraint_compiler.persistence_index", "record_run"),
    "reindex": (".constraint_compiler.persistence_index", "reindex"),
    "DriftFinding": (".vendoring", "DriftFinding"),
    "compute_drift": (".vendoring", "compute_drift"),
    "iter_vendored_pairs": (".vendoring", "iter_vendored_pairs"),
    "library_root": (".vendoring", "library_root"),
    "Migration": (".migrations", "Migration"),
    "MigrationError": (".migrations", "MigrationError"),
    "Registry": (".migrations", "Registry"),
    "default_registry": (".migrations", "default_registry"),
    "migrate_ir": (".migrations", "migrate_ir"),
    "target_version_for": (".migrations", "target_version_for"),
    "LATEST_VERSIONS": (".schemas", "LATEST_VERSIONS"),
    "SCHEMA_FILENAMES": (".schemas", "SCHEMA_FILENAMES"),
    "SchemaNotFoundError": (".schemas", "SchemaNotFoundError"),
    "list_schemas": (".schemas", "list_schemas"),
    "load_schema": (".schemas", "load_schema"),
}

# Reloading this module invalidates values resolved by an earlier import.
for _export in _LAZY_EXPORTS:
    globals().pop(_export, None)
del _export

__all__ = [
    "ReferencePolicy", "ReferencePolicyError", "load_policy",
    # Versions
    "__version__",
    "IR_SCHEMA_VERSION",
    "PARSER_VERSION",
    # Parsers
    "parse",
    "parse_adr",
    "parse_ae",
    "parse_bs",
    "parse_constitution",
    "parse_glossary",
    "parse_ib",
    "parse_intent",
    "parse_mission",
    "parse_security_profile",
    "parse_vision",
    "parse_ws",
    "resolve_aes",
    "lint_ib",
    # Parse errors
    "ADRParseError",
    "AEParseError",
    "BSParseError",
    "ConstitutionParseError",
    "GlossaryParseError",
    "IBParseError",
    "ICParseError",
    "IntentParseError",
    "MissionParseError",
    "SPParseError",
    "VisionParseError",
    "WSParseError",
    # The Behavior Specification alias map
    "BEHAVIOR_SPEC_NAMES",
    # Audit rule-id aliases (IB-212)
    "RULE_ID_ALIASES",
    "RETIRED_RULE_ID_RENAMES",
    "canonical_rule_id",
    # Brief identity (IB-241)
    "BriefIdentityError",
    "BriefRef",
    "list_briefs",
    "resolve_brief",
    # Graph
    "SpecGraph",
    "ParseFailure",
    # Emitters
    "agents_md",
    "ci_gate",
    "contract_test",
    "emit_constitution_markdown",
    # Audit
    "Finding",
    "Fix",
    "apply_fixes",
    "apply_status_fixes",
    "audit_linkage",
    "propose_fixes",
    # Promotion
    "PromoteError",
    # Audit profile registry (F-3 phase 2)
    "AuditProfile",
    "ProfileLoadError",
    "ProfileNotFoundError",
    "list_audit_profiles",
    "load_audit_profile",
    # Persistence
    "Run",
    "RunWriter",
    "open_run",
    "repo_fingerprint",
    "repo_runs_dir",
    "repo_state_dir",
    "xdg_data_root",
    "INDEX_FILENAME",
    "INDEX_SCHEMA_VERSION",
    "open_index",
    "query_runs",
    "record_run",
    "reindex",
    # Vendoring
    "DriftFinding",
    "compute_drift",
    "iter_vendored_pairs",
    "library_root",
    # Migrations
    "Migration",
    "MigrationError",
    "Registry",
    "default_registry",
    "migrate_ir",
    "target_version_for",
    # Schema access
    "LATEST_VERSIONS",
    "SCHEMA_FILENAMES",
    "SchemaNotFoundError",
    "list_schemas",
    "load_schema",
]


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module, attribute = _LAZY_EXPORTS[name]
    value = getattr(import_module(module, __package__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    # Keep eager-module introspection, including caller-added attributes, while
    # hiding only the machinery introduced by lazy resolution.
    hidden = {"_LAZY_EXPORTS", "_TYPE_CHECKING", "__getattr__", "__dir__"}
    return sorted((set(globals()) - hidden) | set(_LAZY_EXPORTS))
