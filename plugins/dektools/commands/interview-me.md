---
description: Docs-anchored decision-tree interview — invokes the /interview-me skill. Asks one question at a time, recommends an answer per question, explores the repo for discoverable answers, cites the domain glossary + governing ADRs/AEs and flags conflicts, sharpens fuzzy/overloaded terms, and stress-tests asserted relationships with scenarios. Writes resolved decisions to a scratch hand-off log for the host authoring skill to fold in. Composed default-on by the high-judgment authoring skills.
allowed-tools: Skill
argument-hint: [--help] [artifact-id or fuzzy description of the thing being authored]
disable-model-invocation: false
---

Invoke the `interview-me` skill to run a docs-anchored, one-question-at-a-time
interview that sharpens a fuzzy or underspecified input into resolved design
decisions before they get committed to a DekSpec artifact.

## Steps

1. Invoke the `interview-me` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill asks one decision-tree question at a time (recommending an answer per question), explores the repo for discoverable answers, cites `dekspec/domain-glossary.md` + governing ADRs/AEs while flagging conflicts, sharpens fuzzy terms, stress-tests asserted relationships with scenarios, and writes the resolved decisions to `dekspec/.scratch/interview-me/<artifact-id>.md` — the ephemeral hand-off log the host authoring skill reads and folds into the artifact at interview end. Domain-term clarifications route to `/dekspec:write-ggc`.
