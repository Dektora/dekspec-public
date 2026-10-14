---
description: Manage the terminology corrections log — invokes the /write-corrections skill. Records a misinterpretation against `dekspec/terminology-corrections.md`, counts its recurrences, walks open entries interactively, audits the log's structural health, and at the 3-recurrence threshold marks the entry promoted and hands its correction text to /dekspec:write-glossary to compose the row.
allowed-tools: Skill
argument-hint: [--help] [--teaching | --log | --review | --audit] [correction text]
disable-model-invocation: false
---

Invoke the `write-corrections` skill to operate the corrections half of the
terminology pipeline — the recurrence-counted log at
`dekspec/terminology-corrections.md`.

## Steps

1. Invoke the `write-corrections` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill logs a correction or adds a
   recurrence to an existing one (`--log`), walks the log's open issues one at a time
   with a recommendation per issue (`--review`), or reports the log's structural health
   (`--audit`). At three recurrences it flips the entry's status and hands the correction
   text to `/dekspec:write-glossary --add-term`, which is the only writer of
   `dekspec/domain-glossary.md`.
3. If the request is actually a glossary operation — adding a term, extracting term
   candidates from a corpus, or a duplicate/synonym check — route it to
   `/dekspec:write-glossary` instead. The two skills partition by artifact: this one
   owns the corrections log, that one owns the glossary.
