# Domain Glossary

Canonical definitions for every domain term used across this system's artifacts. This is the singleton document at `dekspec/domain-glossary.md`. It is authored continuously — every time `/write-ggc --add-term` adds a term, or the recurrence pipeline auto-promotes a `/write-ggc --log` entry past the threshold, a row lands here.

Read this document before introducing any new domain term in an artifact. If a term you need is missing, run `/write-ggc --add-term` to add it.

## Created

[YYYY-MM-DD]

## Modified

[YYYY-MM-DD]

## Purpose

[1-2 paragraphs: why this glossary exists for this specific system. Typically: the system has a vocabulary that drifted across early artifacts; the glossary is the canonical resolution. Cite the originating correction or recurrence-promotion pipeline if relevant. This section is optional but recommended.]

*Severity vocabulary note:* if a glossary entry or amendment-log row cites severity (e.g., a `P1` finding the entry remediates), use the canonical `P0` / `P1` / `P2` / `P3` ladder per ADR-013. Historical aliases (`blocking` → `P1`, `non_blocking` → `P3`, `critical` → `P1`, `important` / `warning` → `P2`, `minor` / `info` → `P3`) remain accepted indefinitely — see `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder and alias map.

## [Category 1 — rename per your system]

[Each H2 below the metadata sections is a category of terms. Categories are arbitrary groupings you choose for your system — there is no required category list. The parser walks every H2 (except `Created`, `Modified`, `Purpose`, `Amendment Log`, `Status`, `Source`) and treats it as a category, then reads the markdown table inside that section as the term list for that category.]

| Term | Canonical Definition | NOT this | Code convention |
|------|---------------------|----------|-----------------|
| **[term]** | [what the term means in this system] | [common misinterpretations to avoid; `—` if none yet] | [variable/function naming pattern; `—` if not applicable] |
| **[term]** | [definition] | [anti-definition] | [convention] |

## [Category 2 — rename per your system]

| Term | Canonical Definition | NOT this | Code convention |
|------|---------------------|----------|-----------------|
| **[term]** | [definition] | [anti-definition] | [convention] |

## Amendment Log

*Add an entry for every change after the glossary's first row is added. The glossary has no status field — it is a living document that grows continuously via `/write-ggc`.*

| Date | Type | Change | Author |
|------|------|--------|--------|
| YYYY-MM-DD | Addition / Correction / Removal | [what changed and why] | [name or agent] |
