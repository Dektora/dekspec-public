---
description: Pre-Intent feasibility spike — invokes the /spike skill. When the approach is genuinely uncertain (algorithm choice, third-party integration, a performance characteristic), build a focused throwaway experiment that produces verified knowledge (hypothesis → VALIDATED/REFUTED/INCONCLUSIVE → recommendation) in a durable dekspec/spikes/<slug>/SPIKE.md the next Intent cites. No production leak; --wrap-up routes a load-bearing finding to an ADR candidate.
allowed-tools: Skill
argument-hint: [--help] [--wrap-up <slug>] [hypothesis or question]
disable-model-invocation: false
---

Invoke the `spike` skill to run a pre-Intent feasibility experiment.

## Steps

1. Invoke the `spike` skill via the Skill tool, forwarding `$ARGUMENTS` verbatim.
2. Relay the skill's output to the operator. The skill frames a falsifiable
   hypothesis, builds a minimal throwaway experiment under
   `dekspec/spikes/<slug>/`, runs it, and writes a durable `SPIKE.md` record
   (hypothesis / experiment / VALIDATED|REFUTED|INCONCLUSIVE result / recommendation)
   the next Intent's Motivation can cite. Experiment code is throwaway — never
   promoted into production (adoption goes through the Intent → WS → IB
   lifecycle). `--wrap-up <slug>` routes a load-bearing verified finding into an
   ADR candidate via `/dekspec:write-adr`; it authors nothing itself.
