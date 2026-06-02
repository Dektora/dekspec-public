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

# IR schema + parser version constants
from .constraint_compiler import IR_SCHEMA_VERSION, PARSER_VERSION

# Parser entry points (one per artifact type)
from .constraint_compiler import (
    parse,           # alias for parse_ic; parses Interface Contracts
    parse_adr,
    parse_ae,
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

__all__ = [
    # Versions
    "__version__",
    "IR_SCHEMA_VERSION",
    "PARSER_VERSION",
    # Parsers
    "parse",
    "parse_adr",
    "parse_ae",
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
    "ConstitutionParseError",
    "GlossaryParseError",
    "IBParseError",
    "ICParseError",
    "IntentParseError",
    "MissionParseError",
    "SPParseError",
    "VisionParseError",
    "WSParseError",
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
