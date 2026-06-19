---
description: Read-only post-mortem for stuck/failed/anomalous DekSpec construction sessions — invokes the /forensics skill. Collects git/worktree/bead/linkage evidence, matches known failure fingerprints (stuck loop, orphaned worktree, mid-red crash, incomplete LOCK chain, IB drift, test regression, context-overflow, cross-session collision), and writes a structured forensic report with a root-cause hypothesis + recovery commands. Remediates nothing.
allowed-tools: Skill
argument-hint: [--help] [problem description]
disable-model-invocation: false
---

Invoke the `forensics` skill to run a read-only post-mortem on a DekSpec
construction session that went wrong.

## Steps

1. Invoke the `forensics` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill is read-only: it gathers
   git/worktree/bead/linkage evidence, matches it against the known construction
   failure fingerprints, and writes ONE file — a forensic report under
   `docs/workspace/<area>/pm/forensics/` (or `.dekspec-forensics/` as fallback) —
   carrying the evidence, a root-cause hypothesis, and recommended recovery
   commands. It creates no beads, edits no artifacts, and performs no recovery;
   remediation is the engineer's deliberate next step.
