# Help Mode

[← back to dispatcher](../SKILL.md)


See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-intent"
one_line:   "Author, analyze, accept, decompose into IBs, or complete an Intent"
modes:
  - { flag: "", args: "<description>", description: "Create a new Intent from the engineer's description (provisional by default; --canonical allocates INT-NNN). Surfaces an advisory per-Mission serialization note (ADR-016 — never refuses), writes the Intent with Status DRAFT, populates Autonomy `medium` (ADR-059; capped by the Mission ceiling) and the type-default Verification, and (canonical) adds an entry to intent-index.md." }
  - { flag: "--analyze", args: "<Intent-path>", description: "Top-down coverage check + bottom-up archaeology + size assessment + type-specific field validation + WS-fan-in per IU. Populates Coverage Report and Size Assessment sections; logs gaps as blocking Open Issues. Promotes DRAFT → PROPOSED on a clean run; if any hard cap fails it records a P2 re-split open issue and Status stays DRAFT. Refuses to advance if a type-specific required field is missing." }
  - { flag: "--accept", args: "<Intent-path>", description: "Engineer-only gate. Promote PROPOSED → ACCEPTED. Re-runs the linkage / shape / drift checks one last time before promotion." }
  - { flag: "--decompose", args: "<Intent-path>", description: "Author the Intent's child IBs via /write-ibs — delegated IBs with **Parent:** INT-NNN, obligations referenced not copied, Scope inside Components affected. For type: bug, one IB's acceptance names the red-first reproduction test and the <reproduction-test-path-from-IB-1> placeholder is resolved. Re-checks the size caps (an over-cap result is a P2 re-split finding). Status stays ACCEPTED; no beads, no branch requirement." }
  - { flag: "--lock", args: "<Intent-path>", description: "Complete the Intent (ACCEPTED -> COMPLETE, ADR-057; the flag name is retained — Intents never lock). Runs `dekspec intent verify` (Verification + outcome test; manual entries need an independent `dekspec intent review` verdict), then `dekspec intent complete`, which refuses unless every child IB is COMPLETE and the outcome evidence is current. Moves the row to the Archive in intent-index.md and updates the Mission's Intent queue when mission: is set." }
  - { flag: "--sync", args: "<Intent-path>", description: "Walk the Post-implementation sync checklist on a COMPLETE Intent. Marks completed items, surfaces new ones (WS docstring fixes, test-promotion candidates, cross-ref repairs). Non-substantive cleanup only — substantive changes go through --amend." }
  - { flag: "--supersede", args: "<Intent-path> --by <INT-NNN|MSN-NNN>", description: "Transition a not-yet-complete Intent (DRAFT/PROPOSED/ACCEPTED) absorbed by a named successor artifact to SUPERSEDED; records Superseded-By, surfaces its child IBs for a decision, and moves the index row to Archive (ADR-035). Refuses COMPLETE (the ADR-028 successor-Intent path) and already-terminal." }
  - { flag: "--audit", args: "<Intent-path>", description: "Read-only health check. Re-runs every check --analyze / --accept / --lock would run (linkage L7, components L7b, verification L9, drift D19/D20, size caps, type-specific fields), but mutates nothing. Reports findings and recommends the remedial mode." }
  - { flag: "--review", args: "<Intent-path>", description: "Interactive section-by-section walkthrough. Summarizes each major section, asks the engineer whether to revise, applies their edits if yes. Useful before --accept on an Intent someone else authored, or for periodic hygiene on ACCEPTED Intents that have been sitting." }
  - { flag: "--amend", args: "<Intent-path>", description: "Structured cascade for substantive mid-flight changes (Decision #10 / v5). Engineer states the change; the skill applies the edit and re-runs the invariants (size caps, components resolve, verification cmds resolve, D19/D20 drift). Status cascades back to DRAFT for re-analysis; a broken hard cap records the P2 re-split finding. Logs a Substantive Amendment Log entry." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing an Intent section-by-section. Distinct from --review (audits existing) and from no-flag creation (assumes the author already knows Intents). (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-intent add file-attachment processing for image MIME types  (creation)"
  - "/write-intent --analyze dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --accept dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --decompose dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --lock dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --sync dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --supersede dekspec/intents/INT-005-attachment-mime-coverage.md --by MSN-001"
  - "/write-intent --audit dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --review dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --amend dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.
