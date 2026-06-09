"""Constraint Compiler — transforms LOCKED DekSpec artifacts into enforcement representations.

Pipeline: markdown source -> parser -> IR -> emitters -> contract tests, CI gates, ...

The IR is the load-bearing contract between parser and emitters. Schemas live in
`dekspec.schemas`.

v0.1 PoC ships:
  - parse(path) for Interface Contracts
  - emitters.contract_test.emit(ir) -> pytest stub string
  - emitters.ci_gate.emit(ir) -> GitLab CI job YAML

See docs/architecture.md for the source -> IR -> compiled outputs -> runtime mental
model that this package implements.
"""

from .parser import (
    ADRParseError,
    AEParseError,
    CSParseError,
    ConstitutionParseError,
    GlossaryParseError,
    IBParseError,
    ICParseError,
    IR_SCHEMA_VERSION,
    IntentParseError,
    MissionParseError,
    PARSER_VERSION,
    ParseError,
    SPParseError,
    VisionParseError,
    WSParseError,
    emit_constitution_markdown,
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
from .graph import SpecGraph, ParseFailure
from .emitters import agents_md, ci_gate, contract_test
from .linter import lint_ib

__all__ = [
    "parse",
    "parse_adr",
    "parse_ae",
    "parse_constitution",
    "parse_context_spec",
    "parse_glossary",
    "parse_ib",
    "parse_intent",
    "parse_mission",
    "parse_security_profile",
    "parse_vision",
    "parse_ws",
    "emit_constitution_markdown",
    "resolve_aes",
    "SpecGraph",
    "ParseFailure",
    "ICParseError",
    "ADRParseError",
    "AEParseError",
    "CSParseError",
    "ConstitutionParseError",
    "GlossaryParseError",
    "IBParseError",
    "IntentParseError",
    "MissionParseError",
    "ParseError",
    "SPParseError",
    "VisionParseError",
    "WSParseError",
    "IR_SCHEMA_VERSION",
    "PARSER_VERSION",
    "contract_test",
    "ci_gate",
    "agents_md",
    "lint_ib",
]

