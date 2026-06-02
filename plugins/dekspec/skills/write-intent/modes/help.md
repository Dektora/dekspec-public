# Help Mode

[← back to dispatcher](../SKILL.md)


See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-intent"
one_line:   "Author, analyze, accept, decompose, testpass, or lock an Intent (Phase 1 complete)"
modes:
  - { flag: "", args: "<description>", description: "Create a new Intent from the engineer's description. Surfaces an advisory per-Mission serialization note (ADR-016 — never refuses), creates the int/INT-NNN-slug branch, writes the Intent file at dekspec/intents/INT-NNN-<slug>.md with Status DRAFT, populates Autonomy + Verification from the type defaults (CLAUDE.md §Verification Predicate Library), and adds an entry to intent-index.md." }
  - { flag: "--analyze", args: "<Intent-path>", description: "Top-down coverage check + bottom-up archaeology + size assessment + type-specific field validation + WS-fan-in per IU. Populates Coverage Report and Size Assessment sections; logs gaps as blocking Open Issues. Promotes DRAFT → PROPOSED on clean run, or DRAFT → OVERSIZED if any hard cap fails. Refuses to advance if a type-specific required field is missing." }
  - { flag: "--accept", args: "<Intent-path>", description: "Engineer-only gate. Promote PROPOSED → ACCEPTED. Re-runs the linkage / shape / drift checks one last time before promotion." }
  - { flag: "--decompose", args: "<Intent-path>", description: "Branch by IB-need (Decision #12) per IU recorded in the Layer impact analysis. For type: bug, scaffolds the failing-test bead as IB-1 via /write-beads --bug-reproduction and resolves the <reproduction-test-path-from-IB-1> placeholder in the Verification block. Multi-WS IUs route through /write-ibs first; single-WS IUs go directly to /write-beads with the Intent path. Re-checks size caps post- decomposition; reverts to OVERSIZED if exceeded. Promotes ACCEPTED → IMPLEMENTING." }
  - { flag: "--testpass", args: "<Intent-path>", description: "Diff-confinement check + Verification predicate evaluation. Diff confinement: every file changed on the Intent branch (vs its base) must match a glob in Components affected, else a TESTFAIL record is appended with reason out-of-scope-edits and Status stays IMPLEMENTING. Verification: runs every cmd in the Verification block; first non-zero exit appends a TESTFAIL record with the failing check's detail and Status stays IMPLEMENTING. All checks zero → IMPLEMENTING → TESTPASS with per-check results recorded in the Verification block. (`TESTFAIL` Status retired 2026-05-25 — E3 audit; the records section stays as a captured-failure log on the IMPLEMENTING → TESTPASS path.)" }
  - { flag: "--lock", args: "<Intent-path>", description: "Promotion to LOCKED via either of two sufficient paths (ADR-017). Runs from main. Path A — forward flow: Status MERGED, most recent --testpass result still true with no Verification edits since. Path B — every downstream WS/IC/IB the Intent produced is at status >= ACCEPTED (no MERGED, no --testpass record, no branch diff required). Either path is sufficient; if neither holds, refuses and names what each still needs. Transitions the Intent to LOCKED, moves its row from Active queue to Archive in intent-index.md, and (when mission: is set) appends to that Mission's Intent queue with status LOCKED." }
  - { flag: "--unlock", args: "<Intent-path>", description: "Walk a LOCKED Intent back to PROPOSED so an editorial correction can be applied (stale Components-affected glob, broken cross-reference, renamed-file path string). Reason-gated — the engineer must supply a full-sentence reason, recorded verbatim in the Amendment Log. Runs a downstream-impact scan, flips LOCKED → PROPOSED, moves the Intent's row from Archive back to the Active queue in intent-index.md, and (when mission: is set) walks the Mission's Intent-queue row back to PROPOSED. The editorial-correction precursor to --lock; substantive change still spawns a successor Intent (see --amend)." }
  - { flag: "--sync", args: "<Intent-path>", description: "Walk the Post-implementation sync checklist on a LOCKED Intent. Marks completed items, surfaces new ones (WS docstring fixes, test-promotion candidates, cross-ref repairs). Non-substantive cleanup only — substantive changes go through --amend." }
  - { flag: "--audit", args: "<Intent-path>", description: "Read-only health check. Re-runs every check --analyze / --accept / --testpass would run (linkage L7, components L7b, verification L9, drift D19/D20, size caps, type-specific fields), but mutates nothing. Reports findings and recommends the remedial mode." }
  - { flag: "--review", args: "<Intent-path>", description: "Interactive section-by-section walkthrough. Summarizes each major section, asks the engineer whether to revise, applies their edits if yes. Useful before --accept on an Intent someone else authored, or for periodic hygiene on ACCEPTED Intents that have been sitting." }
  - { flag: "--amend", args: "<Intent-path>", description: "Structured cascade for substantive mid-flight changes (Decision #10 / v5). Engineer states the change; the skill applies the edit and re-runs the invariants (size caps, components resolve, verification cmds resolve, D19/D20 drift). If a hard cap is broken, the Intent reverts to OVERSIZED. Logs a Substantive Amendment Log entry." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial walking a new author through writing an Intent section-by-section. Distinct from --review (audits existing) and from no-flag creation (assumes the author already knows Intents). (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-intent add file-attachment processing for image MIME types  (creation)"
  - "/write-intent --analyze dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --accept dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --decompose dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --testpass dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --lock dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --unlock dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --sync dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --audit dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --review dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --amend dekspec/intents/INT-005-attachment-mime-coverage.md"
  - "/write-intent --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.
