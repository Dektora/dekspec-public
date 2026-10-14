---
description: Own the domain glossary — invokes the /write-glossary skill. Extracts glossary-term candidates from a corpus (proposes only; never auto-writes the glossary), adds a canonical term directly after a duplicate + synonym check, and composes the glossary row when the corrections pipeline promotes an entry at the 3-recurrence threshold. The glossary half of the terminology pipeline; corrections belong to /dekspec:write-corrections.
allowed-tools: Skill
argument-hint: [--provisional <slug>] [--help | --teaching | --extract | --add-term] [term details or corpus path]
disable-model-invocation: false
---

Invoke the `write-glossary` skill to operate on `dekspec/domain-glossary.md` — the project's
canonical vocabulary.

## Steps

1. Invoke the `write-glossary` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill runs one mode per invocation:
   `--extract` proposes a 3-way disposition per glossary-term candidate and writes nothing
   without per-candidate confirmation; `--add-term` runs the duplicate + synonym check and
   then adds the row; `--teaching` walks the row contract read-only; `--help` renders the
   mode catalog. A promotion hand-off from `/dekspec:write-corrections` composes or enriches
   one row and hands the result back to the caller.
3. Two things this command does not do, and where they live: logging a correction, counting
   recurrences, and the 3-recurrence threshold belong to `/dekspec:write-corrections`;
   glossary structural health (duplicate terms, missing definitions, dangling aliases,
   coverage) is the audit engine's — run `dekspec doctor`.
