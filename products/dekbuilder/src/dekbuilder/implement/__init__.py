"""Autonomous implementation of ready work (ADR-059).

`/implement` resolves a request to approved targets, checks the READY
predicate, and drives each delivery to integrated, verified completion. The
deterministic parts live here — target resolution (:mod:`targets`), readiness
(:mod:`readiness`), the per-delivery driver that decides every next step
(:mod:`driver`), integration (:mod:`integration`) and worker prompts
(:mod:`prompts`); the agent harness executes the steps only an agent can take.
"""
