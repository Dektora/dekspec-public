---
name: security-review
description: Review applicable security coverage and findings without inventing confidence.
mode: lite
interaction: natural-language
reasoning_effort: high
disable-model-invocation: true
allowed-tools: Read Grep Glob Bash Agent
argument-hint: "[request or target]"
---

Identify target repository/revision, dirty changes, relevant Security Profile,
and configured scanners. Run `python3 scripts/review.py --at REPO` from this
skill directory. It runs all applicable supported detectors (Bandit for Python,
pip-audit for requirements.txt, Gitleaks for secrets); inspect help for explicit
configured detector selection and raw evidence output. Unsupported languages or
lockfiles and unavailable scanners are coverage gaps, not clean results. Never
install or run arbitrary new scanners without normal dependency authorization.

Keep detector-native severity, confidence and evidence. Specification-derived
priority is a separate field: sensitive paths can raise priority but must never
raise confidence. Add agent analysis separately, labeled with evidence and
uncertainty. Scanner findings exit codes are not crashes; parsing/runtime errors
are failures. Review relevant flows beyond what these narrow adapters can assess.

A scoped clean scan is never an unqualified security GO. Report run, failed,
unavailable, unsupported and unassessed coverage for source, dependencies and
secrets. Missing Security Profile does not imply adequate coverage. CI results
must match the exact reviewed revision AND dirty-tree identity; reject stale
results. Keep raw scanner evidence in external state, not committed source.

Report exploitable findings first with file/rule/evidence, native confidence,
separate priority, detector versions and coverage limits. Route authorized fixes
through core implementation. Examples: “review this branch”; “check these auth
changes”. On no detectors, explicitly say no scanner-backed assessment occurred.

## Help

When asked what this tool does or how to use it, explain its purpose, examples,
required capabilities and recovery options above without starting the workflow.
