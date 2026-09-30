# DekTools

Optional tools around DekSpec. Core owns readiness and autonomous `/implement`;
none of these tools is required to use core.

| Tool | Purpose |
| --- | --- |
| project-board | br-backed boards, issue intake, duplicate detection and snapshots |
| debug | Evidence-driven diagnosis and authorized repair through core |
| audit-codebase | Architecture, information hiding and module-depth assessment |
| deepen | Repeated architectural improvement, verification and reassessment |
| security-review | Detector-backed findings with explicit coverage limits |
| ingest-docs | Provisional artifacts from Markdown with provenance |
| recover-specs | Code/history evidence and gaps in specification coverage |
| handoff | Prepare/resume work with identity and freshness checks |
| diagnose-session | Read-only repository/session facts and causal analysis |
| interview-me | Resolve the decisions needed to proceed |
| spike | Bounded feasibility experiments |
| prototype | Disposable exploration of a design shape |
| setup-dektools | Discover, enable, disable or repair optional tools |

Skills accept ordinary requests: `/debug the failing checkout test`,
`/deepen the parser`, `/handoff resume`. Users do not need mode flags.

## Install and select

Install the matching DekSpec engine release using the repository's installation
instructions. For Claude, install `dektools@dekspec` from the DekSpec marketplace.
The plugin automatically registers **setup only**. Its `tools/` distribution
corpus is outside automatic skill discovery; it does not register all tools.

Say `/dektools:setup-dektools enable debugging and handoff`. Setup persists
`dektools.enabled` in the target repository's `.dekspec/config.yaml` and invokes
`dekspec install` to emit selected repository-local skills. These are normally
invoked as `/debug` and `/handoff`; follow the actual names your host advertises.
For other hosts, `dekspec install --platform HOST --target REPO` installs setup
and the selected set. The wheel includes the same single-source toolkit corpus.

Setup with no request shows purposes, desired selection, installed state and
repair options. “Disable handoff” removes its owned skill files on the next emit;
“repair the installation” reapplies selection. Setup stays available at zero tools.
Reload the host after changes. Upgrade/reload any older whole-toolkit plugin;
a running session can retain old registrations. Never edit a plugin cache.

The installer hashes owned files in `.dektools-install.json`. Unknown files and
modified generated files survive. Conflicts identify exact paths to review or
move aside before retry. Old enabled names migrate as data; there are no old
invocation aliases. Existing boards, diagnostic logs and handoff records remain.

## Capability requirements

The catalog is authoritative. Project-board, audit-codebase, security-review,
diagnose-session, interview-me, spike and prototype provide standalone value.
Their optional DekSpec integration requires core. Project-board needs `br`;
security review needs applicable scanners. Unavailable coverage is explicit.
Ingest, recovery, handoff, deepening and governed debug use installed core helpers.
Setup needs the engine for config and emission. The per-tool preflight checks
required CLI capabilities and gives a correction, not just a binary-presence test.

Security adapters currently support Bandit (Python source), pip-audit
(requirements.txt), and Gitleaks (working-tree secrets). Native confidence remains
separate from severity and spec-derived priority. Results bind to revision and
local file contents; partial coverage never produces a broad security pass.

Deepening carries rejected candidates, evidence, unfinished opportunities and
cost across passes. Stops distinguish convergence, stall, budget and blocker.
Governed repair and deepening execute through core `/implement` (ADR-059,
`dekspec implement resolve|ready|next|ack|status`). With an older core that lacks
it, repair execution is blocked, not useful diagnosis/investigation. Existing
runs resume from core records; only integrated, verified completion counts as
success. Tools preserve readiness diagnostics and never change autonomy or
approve specifications just to bypass them.
There is no fallback builder in DekTools.

Runtime records use `XDG_STATE_HOME/dekspec/<repo-hash>/`; legacy handoffs are
read from their old scratch location when no current record exists. Raw scanner
reports stay in external state. Core continuity remains independent of handoff.

## Distribution

`skills/setup-dektools/` is the bootstrap. `tools/<name>/` contains the optional
skills. `scripts/` contains shared stdlib helpers, and `tool-catalog.json` defines
names, tiers and selection migration. There are no duplicate command wrappers.

The monorepo releases both plugins in lockstep. See `RELEASING.md`; selecting or
implementing toolkit changes does not publish a release or update consumers.
