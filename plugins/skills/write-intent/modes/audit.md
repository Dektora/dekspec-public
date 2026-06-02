# Audit Mode (read-only health check)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Re-runs every check the lifecycle methods enforce, but mutates nothing — no Status transitions, no Amendment Log entries, no Intent-file edits.

**Schema-vs-linkage division of labor (ds-52p, D-14).** Some Intent checks are enforced by `jsonschema` validation *at parse time* — Intent type enum, autonomy tier enum, components_affected glob shape. Those never reach the audit; if the Intent's IR validates, those constraints are satisfied. Other checks (L7a-INT-AE-MISSING, L7b-INT-COMPONENTS-RESOLVE, T14-INT-VERIFICATION, D19/D20 prose drift) run in `linkage.py` against the IR graph. This skill's audit-mode report lists findings from both layers without distinguishing them; the split affects only where the check lives in code.

### Step 1: Validate

1. File exists. Audit runs in any status — DRAFT, PROPOSED, OVERSIZED, ACCEPTED, IMPLEMENTING, TESTPASS, MERGED, LOCKED. Refuse only for SUPERSEDED (the successor Intent is what should be audited). (`TODO` + `TESTFAIL` retired 2026-05-25 — E3 audit.)

### Step 2: Run the full check battery

Run each check the corresponding lifecycle mode would run, in this order:

1. **Schema validation** — parse via `dekspec.constraint_compiler.parse_intent`. Surface parse warnings as findings.
2. **Linkage** — audit-v2 L7a (linked_architecture_elements references resolve), L7b (components_affected globs each match ≥1 path), T13 (intent_type from enum), T14 (verification has ≥1 cmd entry), T15 (components_affected non-empty), T16 (autonomy from enum), L9 (each Verification cmd resolves to an executable script or known tool). The mechanical halves of L7b and L9 are scripted: run `scripts/check_components_resolve.py <Intent-path>` (each `## Components affected` entry must glob to ≥1 path; non-zero exit lists the unresolved entries) and `scripts/check_verification_cmds.py <Intent-path>` (each Verification `cmd:` must resolve; resolvability only, no execution). Surface each script's stderr on a non-zero exit and fold the findings into the report.
3. **Drift** — audit-v2 D19 (no measurable targets in motivation/desired_outcome prose outside WS citations), D20 (no decision rationale in motivation/desired_outcome prose outside ADR citations).
4. **Size assessment** — same five hard caps as `--analyze` Step 3 (IUs ≤ 3, Components affected ≤ 3, new L1 ≤ 1, new+revised L2 ≤ 3, coverage gaps ≤ 2). Recompute live; do NOT trust the cached `## Size assessment` table.
5. **Coverage report** — bottom-up archaeology against the current corpus state. Report deltas between the cached `## Coverage report` and the live result.
6. **Mission linkage (L8)** — if `Mission:` is populated, check (a) the Mission file exists, (b) the Mission's Intent queue lists this Intent (when Intent is past DRAFT), (c) this Intent's Autonomy ≤ Mission's Autonomy ceiling.
7. **Status-coherence** — flag any state-machine inconsistency: e.g., status TESTPASS but the Verification block has been edited since the most recent `--testpass` Amendment Log entry (would fail `--lock`); status LOCKED but the Intent isn't in the Archive table of `intent-index.md`; status IMPLEMENTING but no IBs/beads referenced.

### Step 3: Report

Print a findings table grouped by severity (CRITICAL / IMPORTANT / MINOR), each row:

```
[severity] <rule code> <one-sentence finding>
  Fix: <recommended remedial mode>
```

Examples:
- `[CRITICAL] L7a-INT-AE-EXISTS: AE-099 referenced in Linked Architecture Elements does not exist. Fix: --amend to rewrite the AE reference, or author the missing AE.`
- `[IMPORTANT] L9-INT-CMD-RESOLVE: scripts/measure-nfr.sh in verification[1].cmd is not executable. Fix: chmod or replace.`
- `[MINOR] D19-INT-NUMERIC-NO-WS-CITE: motivation contains "≤ 250 ms" without a WS citation. Fix: --amend to move the target to a WS or add the WS reference.`

Print exit code `0` if no CRITICAL findings, `1` if any CRITICAL.

### Step 4: Recommend next mode

End with a one-line recommendation:

- All clean → "No findings. The Intent is well-formed at its current status."
- Findings present → "Run `/write-intent --amend <path>` to apply substantive fixes, or `/write-intent --review <path>` for an interactive walkthrough of editorial concerns."

No file is written. No Amendment Log entry is added. Audit is strictly read-only.

**End of Audit Mode.**
