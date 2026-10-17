# DekTools

Standalone craft workflows: audit-codebase, debug, deepen, diagnose-session,
handoff, project-board, prototype, security-review, and spike.

Build this directory with `python3 -m build`, then install its wheel in a clean
environment. `dektools` shows current continuity state; `dektools handoff
read --at REPO` reads saved work and `dektools deepen-record status --at REPO`
shows the current assessment run. Every subcommand accepts `--help`.

The craft resource payload includes its scripts and references. Neither Spec
nor Builder is required for handoffs, diagnosis, project boards, architectural
assessment, or pure deepening reassessment. Explicit governed deepening reads
`dekbuilder implement receipt TARGET --at REPO --json`; unavailable receipts
preserve pending evidence and refuse completion. Spec remains the sole judge
of governed evidence. Existing continuity state paths stay readable.

Run the owned suite with `python3 -m pytest -c pyproject.toml tests/dektools_tests`
against the installed wheel, and run `python3 scripts/check-version.py` for
local metadata consistency. The source product alone builds outside the shared
repository; 0.130.0 is published on the public
mirror with DekSpec and DekBuilder under one tag (`#subdirectory=products/dektools`).
