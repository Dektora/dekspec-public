---
name: security-review
description: Spec-aware security review that WRAPS proven vulnerability detection — Claude Code's built-in `/security-review`, the `anthropics/claude-code-security-review` action, or the SAST tools the repo's Security Profile (SP-NNN) declares — and adds the DekSpec layer on top: detector output normalized into the `review-pr` finding shape (0-100 confidence ladder, surface threshold 80, GO / NO-GO / INSUFFICIENT_EVIDENCE), prioritized by the security-relevant Architecture Elements and Security-Profile surfaces the repo declares, with surfaced findings routed into the bead flow. Host-agnostic across all six harnesses (the built-in is Claude-Code-only); degrades to an explicit NO_DETECTOR report rather than hand-rolling detection. Use when the engineer asks for a security review, a vulnerability scan, a secrets/injection/authz check, or a security pass over a diff, branch, or PR.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Grep Glob Bash Agent
argument-hint: [--help] [--repo] [--pr <N>] [--detector <name>] [--sidecar-dir <path>]
related_skills: [audit-codebase, review-pr, write-sp, write-issue-beads, write-intent]
---

> **Preflight (ADR-047).** This is a `dekspec-required` tool. From this skill's own directory run `python ../../scripts/dependency_guard.py security-review` before anything else — it exits non-zero with install instructions when the DekSpec engine is absent. (The path is relative to this file so it resolves identically in the monorepo, a packaged plugin install, and an emitted per-host tree.) If it fires, stop and surface its message; do not proceed.

> **Shared `_lib` lives in the DekSpec core plugin** (ADR-047). Resolve it with `dekspec resource lib <name> --path-only`, then read that path — a relative `../_lib/` link does not cross the plugin boundary.
Run a **spec-aware security review**: delegate vulnerability *detection* to a
proven detector, then add the DekSpec layer the detector cannot supply —
review-pr-shaped findings, Security-Profile-grounded prioritization, an honest
verdict, and a route into the bead flow.

## Scope — the integration delta, NOT a new detector

This skill **wraps and orchestrates** detection. It does not perform it.

**You MUST NOT** author vulnerability patterns, grep heuristics, taint rules, or
a vuln-class taxonomy of your own. Every finding this skill emits must be
traceable to a **named detector's own output** — a tool name plus the line,
rule id, or message that detector produced. A finding you cannot attribute that
way is not a finding; drop it.

Why: detection is a solved, heavily-calibrated problem and a hand-rolled
re-implementation is strictly worse than the tools that already exist. The value
this skill adds is everything *around* the detector:

| Delta | What it means here |
|---|---|
| Finding shape | Detector output normalized into the `review-pr` finding shape, so it feeds the same audit / bead flow as a review verdict instead of being loose prose. |
| Spec-aware | Scores are prioritized by the repo's **Security Profile** (`SP-NNN`) and its security-relevant **Architecture Elements**, so a finding in a declared secret store or authn surface outranks the same class of finding in a leaf utility. |
| Coverage honesty | An OWASP row the Security Profile claims is mitigated by a tool that **did not run** becomes an abstention, never a silent pass. |
| Host-agnostic | The built-in `/security-review` exists only on Claude Code. The detector ladder below resolves on all six harnesses, and says so plainly when it cannot. |
| À-la-carte | A `dekspec-required` DekTools tool, selected per installation via the tool catalog (ADR-047). Nothing is on by default. |
| Clear degrade | No detector available → one explicit `NO_DETECTOR` report naming what was probed and how to install one. Never a quiet best-effort eyeball pass dressed up as a scan. |

## Boundary — three neighbours, three concerns

- **`/dekspec:security-review`** (this) → *is the code **exploitable**?* Wraps a
  detector; emits attributed vulnerability findings in the review-pr shape.
- **`/dekspec:audit-codebase`** → *does the code have good **architecture**?*
  Deep vs shallow modules, information hiding, seams, folderization; emits
  `DM-*`/`SH-*`/`IH-*`/… findings. **Stay off its territory.** Do not emit
  module-depth, folderization, or code-quality findings here, and do not
  re-run its rubric. A module that is shallow but not exploitable is its
  finding, not yours.
- **`/dekspec:review-pr`** → *does this PR implement the **IB** it claims to?*
  Spec↔diff fidelity against an Implementation Brief. This skill borrows its
  finding/verdict **shape**, not its question, and never drives the IB state
  machine.

Also distinct from `dekspec doctor` / the fidelity-audit engine, which checks
**spec-artifact linkage** (`T-*`/`D-*`/`L-*`), not source.

## Read-only

Every mode is read-only with respect to source: this skill runs detectors and
reads spec artifacts. It never edits, patches, or rewrites the code it reviews —
`allowed-tools` carries no `Write` and no `Edit`, which holds that structurally.
The one file it may create is the durable **sidecar**, written via `Bash` only
when the engineer asks for one or passes `--sidecar-dir` (see **Sidecar**).
Remediation is a downstream action through the bead flow, never part of the
review.

## Detector ladder

Probe in order and use the **first** rung that resolves. Record which rung fired
— it is part of the report, because a verdict's trustworthiness depends on what
actually ran. Never install anything; probe only.

1. **`--detector <name>` override.** The engineer named the detector. Use it; if
   it is not available, stop and say so rather than silently falling through.
2. **Security-Profile-declared SAST tools.** Read every
   `dekspec/security-profiles/SP-*.md` and take the `## SAST Tools` rows
   (`name` / `language` / `ruleset`). For each, probe `command -v <name>`. This
   rung is first among the automatic ones because it is the posture the repo has
   **committed to**. For the canonical invocation, render the profile's own
   enforcement fragments rather than inventing flags:

   ```bash
   dekspec emit security-profile dekspec/security-profiles/SP-001-<slug>.md
   ```

   which prints the mid-layer pre-commit fragment and the hard-layer CI-gate
   fragment the profile compiles to. Run the tool the way those fragments run it.
3. **The repo's configured CI security job.** Grep `.github/workflows/*.y*ml`
   for `claude-code-security-review` (or another security job). If the review
   target is a PR and `gh` is available, prefer **reading that job's findings
   off the PR checks** over re-running it locally — the configured paths,
   exclusions, and ruleset are already right there.
4. **Claude Code's built-in `/security-review`.** Only when the host is Claude
   Code. Hand it the review target and consume its findings as detector output.
   This rung is deliberately low in the ladder: it is the one rung that does not
   exist on the other five harnesses, so a skill that reached for it first would
   behave differently per host.
5. **Generic detectors on PATH.** Probe `command -v` for `semgrep`, `gitleaks`,
   `trufflehog`, `bandit`, `pip-audit`, `osv-scanner`, `trivy`, `npm` (for
   `npm audit`). Run only the ones present and appropriate to the repo's
   languages. Two rungs may both run (e.g. a secrets scanner alongside a SAST
   tool); record every tool that contributed.
6. **Nothing resolved** → **NO_DETECTOR** (see **Degradation**).

## Mode Detection

See ``_lib/mode_detection_template.md`` (resolve: `dekspec resource lib mode_detection_template`). Default mode: **Diff review**.

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Repo mode** — `--repo` flag. Review the whole tracked source surface rather
  than a diff. Slower and noisier; use for a first-time baseline.
- **PR mode** — `--pr <N>` flag. Review the diff of pull request `<N>`
  (`gh pr diff <N>`, or the forge equivalent). Prefer rung 3's already-computed
  CI findings when they exist for that PR head.
- **Diff review** — no flag (default). Review the working-tree changes plus the
  current branch's diff against its merge base.

Two modifiers combine with any of the above (they are modifiers, not modes —
neither one selects a workflow on its own):

- `--detector <name>` — pin rung 1 of the detector ladder.
- `--sidecar-dir <path>` — write the durable sidecar to `<path>` instead of the
  default `dekspec/reviews/`. Passing it also *opts in* to writing one.

This skill exposes no lifecycle/audit/review flags — it promotes nothing and
lands nothing, so it carries none of the `write-*` lifecycle modes.

## Help Mode

See ``_lib/help_mode_template.md`` (resolve: `dekspec resource lib help_mode_template`) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:security-review"
one_line:   "Spec-aware security review — wraps a proven detector (built-in /security-review, the claude-code-security-review action, or the SAST tools the Security Profile declares), normalizes findings into the review-pr shape, prioritizes by security-relevant AEs + SP surfaces, and degrades to an explicit NO_DETECTOR report. Wraps detection; never reimplements it."
modes:
  - { flag: "",       args: "",       description: "Diff review (default) — review the working-tree changes plus the branch diff against its merge base." }
  - { flag: "--repo", args: "",       description: "Baseline sweep over the whole tracked source surface instead of a diff. Slower and noisier; use once, then stay on diffs." }
  - { flag: "--pr",   args: "<N>",    description: "Review pull request <N>'s diff; prefers findings already computed by the repo's CI security job for that head." }
  - { flag: "--help", args: "",       description: "Show this help message." }
examples:
  - "/dekspec:security-review"
  - "/dekspec:security-review --pr 42"
  - "/dekspec:security-review --repo --detector semgrep"
  - "/dekspec:security-review --help"
extra_sections:
  - heading: "BOUNDARY"
    body:
      - "WRAPS detection; never reimplements it. Every finding cites a named"
      - "detector's own output. Architecture quality is /dekspec:audit-codebase;"
      - "spec-artifact linkage is `dekspec doctor`; spec-vs-diff fidelity is"
      - "/dekspec:review-pr. This skill answers only: is the code exploitable?"
  - heading: "MODIFIERS"
    body:
      - "--detector <name>   pin the detector (rung 1 of the ladder)."
      - "--sidecar-dir PATH  write the durable sidecar here (default dekspec/reviews/)."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Workflow

### Step 1 — resolve the review target

Per the mode: working-tree + branch diff (default), the full tracked source
surface (`--repo`), or a PR diff (`--pr <N>`). Record the head SHA — a verdict
without the SHA it was computed against is not reproducible.

If the diff is very large, say so and recommend reviewing it in slices; a
detector will still run, but the prioritization pass below degrades on a diff
nobody can hold in view.

### Step 2 — load the spec context

Read, and note which of these are absent (absence is reportable, not fatal):

| Input | Source | Used for |
|---|---|---|
| Security Profiles | `dekspec/security-profiles/SP-*.md` | detector ladder rung 2; sensitive-surface map; OWASP coverage honesty |
| Architecture Elements | `dekspec/architecture-elements/AE-*.md` | mapping changed files → owning AE via `implements_globs`; subtype + classification drive priority |
| Audit snapshot | `dekspec doctor --json --at .` | cross-referencing an AE/SP the audit already reports as broken, so a finding is not blamed on a surface that is simply unlinked |

A repo with **no** Security Profile is a supported case: the review still runs
on the detector ladder's other rungs, the prioritization pass falls back to AE
classification alone, and the report recommends `/dekspec:write-sp --create` so
the next run has a posture to key off.

### Step 3 — build the sensitive-surface map

From the spec context, derive the priority tier of every path the diff touches.
This is the spec-aware half of the skill and it is deterministic — no judgement
calls beyond what the artifacts declare:

- **Tier S (most sensitive)** — the path is named by a Security Profile's
  `## Secret Stores`, `## Authn Methods`, or sits on an `## Allowed Dataflows`
  boundary; or it is inside the `implements_globs` of an AE whose subtype is
  `cross_cutting_concern` or `platform_concern` and whose classification is
  `Core`.
- **Tier A** — inside the `implements_globs` of any AE classified `Core`, or of
  an `interface_surface` AE (an externally reachable boundary).
- **Tier B** — inside any other AE's `implements_globs`, or covered by a
  Security Profile's `## Supply Chain` declaration.
- **Tier C** — claimed by no AE and no Security Profile. Note these: an
  unclaimed path carrying a security finding is also a spec-coverage gap
  (`dekspec find-spec-gaps` is the surface for that conversation).

### Step 4 — run the detector

Walk the detector ladder, run what resolves, and **capture the raw output
verbatim**. Do not summarize before you have it; the raw line is the evidence
every finding must cite. Record: which rung fired, every tool that ran, its
version if cheaply available, and its exit code.

If nothing resolves, go to **Degradation** and stop.

### Step 5 — normalize and score

Turn each raw detector finding into one finding in the **Finding shape** below.

- `rule` — the **detector's own** rule id (`semgrep` check id, `gitleaks` rule,
  `bandit` `B###`, the built-in's class label). Never a code you invented.
- `owasp` — the OWASP id **only if the detector or the Security Profile's
  coverage matrix supplies the mapping**. Unknown → `unmapped`. Do not guess.
- `confidence` — the shared 0-100 ladder
  (`dekspec resource lib review_confidence_rubric --path-only`), surface
  threshold **80**.

Start from the detector's own severity mapped onto the ladder, then apply the
**one** spec-aware adjustment this skill is entitled to make:

| Surface tier | Adjustment |
|---|---|
| Tier S | promote into the `critical` band (91-100) — a real finding on a declared secret store, authn surface, or dataflow boundary vetoes the verdict |
| Tier A | +10 |
| Tier B | no change |
| Tier C | no change; additionally note the spec-coverage gap |

Adjustment moves a finding the detector already produced. It never **creates**
one, and it never rescues a finding the detector scored as a false positive.
Record the pre-adjustment score alongside the final one so the promotion is
auditable.

### Step 6 — the coverage-honesty pass

For every `## OWASP Coverage` row in every Security Profile, check whether its
`mapped_tool` actually ran in step 4. A row whose mapped tool did **not** run is
an **abstention**, not a pass: the repo has asserted that class is mitigated by
a tool this review never executed, so this review cannot speak to it. List each
one. Abstentions drive the verdict per **Verdict semantics** below.

This pass is the reason a green detector run does not automatically produce GO.

### Step 7 — emit

Report to chat in the shape below. Write the sidecar only if the engineer asked
for a durable record or passed `--sidecar-dir`.

### Step 8 — route, do not fix

Findings are observations. Remediation goes through the normal governed path:

- Surfaced findings (≥80) → `/dekspec:write-issue-beads`, one bead per finding,
  carrying the detector, the rule id, the path, and the surface tier.
- A finding whose fix is architectural (a boundary moves, a dataflow changes) →
  `/dekspec:write-intent`, citing this review.
- A posture gap — a detector the profile declares but the repo does not have, an
  OWASP row with no mapped tool, a Tier-S path no profile names → the Security
  Profile is out of date; recommend `/dekspec:write-sp --revise`.

Do not patch the code in this skill, and do not open a fix branch.

## Finding shape

The `review-pr` shape, extended with the two fields a security finding needs
(`detector`, `owasp`) and the spec-aware `surface_tier`:

```yaml
- id: <short-slug>
  detector: <tool name>@<version or "unknown">
  rule: <the detector's own rule id>
  owasp: <A01..A10 | unmapped>
  file: <path>:<line>
  surface_tier: S|A|B|C
  owning_ae: <AE-NNN | none>
  security_profile: <SP-NNN | none>
  confidence: <0-100>            # post-adjustment, shared rubric
  raw_confidence: <0-100>        # detector's severity mapped onto the ladder
  band: false-positive|nitpick|low-impact|important|critical
  surfaces: true|false           # true iff confidence >= 80
  evidence: |
    <the detector's own output, verbatim>
  message: <what is exploitable, in one sentence>
  recommendation: <the next governed action; never a patch>
```

Bands and the 80 surface threshold are **not** redefinable here — they come from
the shared rubric and are load-bearing for the review pipeline's calibration.

## Verdict semantics

Asymmetric, mirroring ADR-026:

- **GO** — a detector ran, every finding scored <80, and no OWASP coverage row
  was left unchecked.
- **NO-GO** — at least one finding at ≥80. Name it, its detector, and its
  surface tier.
- **INSUFFICIENT_EVIDENCE** — no finding ≥80 **and** at least one abstention:
  a Security-Profile OWASP row whose mapped tool did not run, a detector that
  exited non-zero, a diff too large to review reliably, or a partial rung.

`NO_DETECTOR` is reported as `INSUFFICIENT_EVIDENCE` with the detector ladder's
probe results attached — never as GO.

The verdict is **advisory**. This skill does not drive the IB state machine and
does not write the review flywheel; that is core's `/dekspec:review-pr` path.

## Sidecar

When a durable record is requested, write
`dekspec/reviews/<scope>-security-review-<UTC-timestamp>.md` (or under
`--sidecar-dir`), where `<scope>` is `PR-<N>`, the branch name, or `repo`. The
`-security-review-` infix keeps it distinct from the `-review-` and `-review-pr-`
sidecars core writes. Carry: verdict · head SHA · detector rung + every tool that
ran · surfaced findings · abstentions · Security Profiles and AEs consulted ·
timestamp.

## Degradation — NO_DETECTOR

If the ladder resolves nothing, emit **one** clear report and stop. Do not
substitute your own inspection for a scanner — an LLM eyeballing a diff and
calling it a security scan is exactly the false assurance this skill exists to
avoid.

```
SECURITY REVIEW — NO_DETECTOR   (verdict: INSUFFICIENT_EVIDENCE)

No security detector is available in this environment, so no scan was run.
Nothing below should be read as "no vulnerabilities found".

Probed:
  --detector override ......... not supplied
  Security Profile SAST tools . <names, or "no SP declares any">
  CI security job ............. <workflow path, or "none found">
  Built-in /security-review ... <"available" | "not on this host (<host>)">
  Generic tools on PATH ....... semgrep, gitleaks, bandit, pip-audit,
                                osv-scanner, trivy, npm — none found

To get a real result, install one detector, then re-run:
  pipx install semgrep          # broad SAST, multi-language
  pipx install pip-audit        # Python dependency CVEs
  # or run on Claude Code, where the built-in /security-review is available
  # or add anthropics/claude-code-security-review to CI and review a PR

If this repo has a Security Profile, the tools it declares are the ones to
install first — they are the posture it has committed to.
```

## Host-agnostic notes

Only rung 4 is Claude-Code-specific. On `codex`, `antigravity`, `cursor`,
`copilot`, and `pi.dev` the ladder simply skips it, and rungs 1-3 and 5 carry the
review — which is the whole point of shipping this rather than telling operators
to use the built-in. State the resolved rung in the report so a verdict produced
on one host is comparable with one produced on another.

## When to use

- Before opening or merging a PR that touches authn, secrets, input parsing,
  deserialization, file paths, subprocess invocation, or a dependency manifest.
- As a first baseline on an inherited repo (`--repo`), once.
- After `/dekspec:write-sp` declares a posture, to check the code against the
  tools that posture names.

## When NOT to use

- To assess module depth, information hiding, or folderization — that is
  `/dekspec:audit-codebase`.
- To check spec-artifact linkage — that is `dekspec doctor`.
- To review a PR against the IB it claims to implement — that is
  `/dekspec:review-pr`.
- To author or amend the Security Profile itself — that is `/dekspec:write-sp`.
- To fix what it finds. It routes; it does not patch.

## Related

- `/dekspec:audit-codebase` — the architecture-quality sibling in the same
  DekTools category. Disjoint concern; see **Boundary**.
- `/dekspec:review-pr` — the finding/verdict shape this skill reuses.
- `/dekspec:write-sp` — authors the Security Profile this skill keys off.
- `/dekspec:write-issue-beads` — where surfaced findings land.
- `/dekspec:write-intent` — where an architectural fix is committed.

## Cross-references

- **ADR-047** — core/toolkit boundary; this skill's `dekspec-required` tier,
  its dependency guard, and its à-la-carte selection.
- **ADR-026** — the review verdict semantics mirrored here.
- **ADR-011** — the Security Profile IR kind (`SP-NNN`) this skill consumes.
- **AE-006** — Skills Library (host AE).
- `_lib/review_confidence_rubric.md` — the shared 0-100 ladder and the
  load-bearing 80 surface threshold.
