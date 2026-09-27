---
description: Spec-aware security review for DekSpec — invokes the /security-review skill. Wraps proven vulnerability detection (Claude Code's built-in /security-review, the anthropics/claude-code-security-review action, or the SAST tools the repo's Security Profile declares) and adds the DekSpec layer: findings normalized into the review-pr shape (0-100 ladder, surface threshold 80, GO / NO-GO / INSUFFICIENT_EVIDENCE), prioritized by security-relevant Architecture Elements and Security-Profile surfaces, then routed into the bead flow. Host-agnostic across all six harnesses; degrades to an explicit NO_DETECTOR report rather than hand-rolling detection. Read-only — it routes, it never patches.
allowed-tools: Skill
argument-hint: [--help] [--repo] [--pr <N>] [--detector <name>] [--sidecar-dir <path>]
disable-model-invocation: false
---

Invoke the `security-review` skill to run a spec-aware security review that
wraps a proven detector rather than reimplementing detection.

## Steps

1. Invoke the `security-review` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill walks its detector ladder
   (`--detector` override → the SAST tools the repo's `SP-NNN` Security Profile
   declares → the configured CI security job → Claude Code's built-in
   `/security-review` where the host provides it → generic detectors on PATH),
   runs whatever resolves, and normalizes that detector's **own** output into the
   `review-pr` finding shape — every finding cites the tool and rule id that
   produced it. It then prioritizes by surface sensitivity derived from the
   Security Profile's secret stores / authn methods / dataflow boundaries and the
   owning Architecture Element's subtype + classification, runs a
   coverage-honesty pass (an OWASP row whose mapped tool did not run becomes an
   abstention, never a silent pass), and emits a GO / NO-GO /
   INSUFFICIENT_EVIDENCE verdict. Default scope is the working-tree + branch
   diff; `--repo` sweeps the whole tracked surface; `--pr <N>` reviews a pull
   request. With no detector available it emits one explicit `NO_DETECTOR`
   report (verdict `INSUFFICIENT_EVIDENCE`) naming what was probed and how to
   install one — it never substitutes its own eyeballing for a scan. The review
   is read-only: surfaced findings route to `/dekspec:write-issue-beads`, an
   architectural fix to `/dekspec:write-intent`, and a posture gap to
   `/dekspec:write-sp`; the skill patches nothing. Architecture quality remains
   `/dekspec:audit-codebase`'s concern and spec↔diff fidelity remains
   `/dekspec:review-pr`'s — this skill answers only whether the code is
   exploitable.
