# Debug session — <slug>

<!--
Persistent state file for `/dekspec:debug-testfail`. Live audit trail kept under
`dekspec/debug/<slug>.md`. The file is updated *as the hunt proceeds* (not at
the end) so a context reset is recoverable via `/dekspec:debug-testfail continue <slug>`.

Section shape borrowed from the gsd-debug `.planning/debug/` template.
-->

- **Intent:** INT-NNN
- **TESTFAIL row:** <date> | <slug> | <one-line symptom>
- **Repro command:** `<deterministic command whose exit code is the signal>`
- **Last checkpoint:** Rule N — <short label>

---

## Observation

Facts only. What has been directly observed — stack traces, error
messages, command outputs, file contents, control-flow notes. Copy
evidence verbatim; do not paraphrase.

- <observation 1>
- <observation 2>

---

## Theory

The currently-open hypothesis. State it as a falsifiable claim and pair
it with the probe that will confirm or kill it. Only one open theory at
a time — when a theory is killed, move it to `## Disproved` and write a
new one here.

- **Claim:** <falsifiable claim — "the bug is that X returns Y when it should return Z">
- **Probe:** <single-variable experiment that will confirm or kill the claim>
- **Expected outcome if claim true:** <what the probe will show>
- **Expected outcome if claim false:** <what the probe will show>

---

## Disproved

Every theory the hunt has killed. Theory + the evidence that killed it.
**This section is the most valuable one** — it prevents a resumed session
(or a fresh-view agent) from re-walking dead branches.

- **Theory:** <killed claim>
  - **Killed by:** <observation/probe result that contradicted it>
  - **Date:** <when>

---

## Root Cause Report

Fill in only after the nine-rules walk converges and Rule 9 ("If you
didn't fix it, it ain't fixed") is satisfied — i.e. the recommended fix
direction has been confirmed to flip the repro green.

- **Intent:** INT-NNN
- **Symptom:** <one-line — the failing observable behavior>
- **Reproduction:** <command that flips the bug red>
- **Root cause:** <one-paragraph technical explanation — the buggy line(s),
  the wrong assumption, the missing case>
- **Believed-buggy location:** <file:line — read-only reference>
- **Disproved theories:** <bulleted summary of `## Disproved` above>
- **Recommended fix shape:** <one-paragraph — the *direction* of the fix>
- **Regression-test seed:** <the deterministic repro that becomes the
  red-first outcome test the Intent's next bead lands>
