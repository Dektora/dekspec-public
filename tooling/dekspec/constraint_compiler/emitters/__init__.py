"""Constraint Compiler emitters — IR -> enforcement artifact strings.

Each emitter is a pure function: given a validated IR, return a string
(or structured object) ready to be written to a consumer repo.

v0.1 ships:
  - contract_test.emit(ir) -> pytest module string
  - ci_gate.emit(ir)       -> GitLab CI job YAML string

Emitters do not perform I/O. The CLI / persistence layer write to disk.
"""
