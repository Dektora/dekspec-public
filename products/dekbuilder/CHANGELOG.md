# Changelog

## 0.129.0 — 2026-10-14

Released with DekSpec and DekTools 0.129.0 under one tag on the public mirror; requires `dekspec==0.129.0`.
Install it from `products/dekbuilder` of that tag into DekSpec's environment (`scripts/install.sh` does this). The repository changelog's v0.129.0 entry has the full notes and known limits. The notes under
0.128.0 below were never published on their own and ship in this release.

- Land completed lean briefs through a shared, recoverable queue with one candidate CI run, guarded base/head/content checks and bounded repair; wait for required checks to register for every delivery.

- Add `wave next` and read-only `wave status`: start ready briefs up to
  `integration.parallel_briefs` (default 2), report stage times and stop causes,
  and document the implement skill’s wave loop.
- Build lean briefs tests-first with independent floor review, bounded interface returns and guard repairs.
- `dekbuilder pr-branch [target]` builds a clean `<branch>-pr` branch in pure git and leaves out commits that
  only change Behavior Specification files, in both name forms (IB-232). Review and dispatch text names the
  Behavior Specification (IB-233).
- `dekbuilder install` is accepted and writes nothing yet.

## 0.128.0

- `implement status` reports each dispatch's canonical worktree, run, id, role,
  key, recorded prompt hash and run-record state in JSON and text output.

Unpublished structural extraction of existing governed construction into Deck
Builder, using installed Spec through IC-020 S0. Original behavior and repair
histories are retained; full provider conformance and public distribution are
later work.


IB-264: delivery acceptance and integration commands use their checkout's
cleaned environment, preserving command-local variables. Results and run events
name the interpreter and driver/engine copy. Setup runs first and failures
block; broken own interpreters and copies never silently fall back. Readiness
probes are advisory; delivery probes decide start after setup. Deliveries with
both packages run their own driver, and reviewers are told when those gates
change. Integrated-revision re-checks build their own environments. Existing
verification reuse remains covered unchanged.
