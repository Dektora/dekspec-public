---
name: write-evals
description: Write, audit, review, or revise the probabilistic evals an IB's acceptance conditions call for — each eval a `verify: command:` condition whose command enforces its own threshold, its files protected acceptance assets. Must run BEFORE the IB's execution starts.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help | --teaching | --audit | --review | --revise] [IB-NNN] [engineer notes or path to notes file]
related_skills: [write-ibs, write-tests, orchestrate-coding-session, review-pr]
---

> **Vendored asset paths:** template and doc paths below resolve via `dekspec resource template <name>` / `dekspec resource doc <name>`; see [`_lib/vendored_assets.md`](../_lib/vendored_assets.md).

Write the evals that prove an IB's model-output behavior. An eval is an **acceptance condition** (ADR-057): a `verify: command:` entry in the IB's `## Acceptance` block. `dekspec ib verify` runs the command and counts only exit status zero. The eval is authored before execution, by someone other than the builder: the candidate must never grade itself.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> Prior conversation context biases threshold selection and scenario design toward numbers remembered from earlier turns instead of the IB's conditions.
>
> First message → proceed. Prior history → ask "context may affect eval quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## The eval contract

- **The command enforces its own threshold.** It runs the pinned trials and exits non-zero when the threshold is missed, and also when the harness cannot run. Put the threshold where the builder cannot change it: in the command string (hashed with the IB contract) or in a protected asset. Never leave it in prose or in an unprotected config file.
- **One mandatory property per condition.** "Recall@5 ≥ 0.70" and "no fabrication on an empty corpus" are two conditions, two commands, two exit codes. Never average them into one score that lets a strong property hide a failing one.
- **Eval files are protected acceptance assets.** A `command:` condition does not protect the files it runs, so list every file the command reads under the IB's "Protected acceptance assets": harness, scenarios, fixtures, golden outputs, rubric, judge prompt. They are then hashed into the baseline, and the builder cannot edit them.
- **Written before execution.** Baseline them (`dekspec ib accept`, or `dekspec ib baseline --reason …` before `dekspec ib start`). After the run starts, a change goes only through `dekspec ib amend --reviewer … --reason …`, and the completing verdict must acknowledge it.
- **Reproducible.** The harness pins the model under test, the sampling settings (temperature, top_p, seed) and the trial count. An LLM judge uses a different model than the one under evaluation. Declare model or API access under the IB's Environment Prerequisites, so an unavailable service blocks the run truthfully instead of failing attempts.
- **Deterministic checks are tests, not evals.** Data shape, retry logic and persistence belong in `/dekspec:write-tests`.

Evals no longer have their own DRAFT/ACCEPTED status: the IB's `dekspec ib accept` is the authorization. There is no per-bead naming and no archive directory, and git history keeps retired scenarios.

```yaml
# In the IB's ## Acceptance block — one property per condition, threshold in the command
- id: AC-4
  condition: "Injected memory is used on ≥80% of known-fact trials (50 trials, seed 42)"
  verify:
    command: "python tests/evals/memory_injection.py --property uptake --min-rate 0.80 --trials 50 --seed 42"
  timeout: 3600
- id: AC-5
  condition: "No memory is fabricated when the corpus is empty (0 of 50 trials)"
  verify:
    command: "python tests/evals/memory_injection.py --property no-fabrication --max-failures 0 --trials 50 --seed 42"
```

## Starter Prompt

```prompt
/dekspec:write-evals IB-214

IB-214 injects retrieved memory into the prompt. Its Acceptance needs
"used on ≥80% of known-fact trials" and "no fabrication on an empty corpus".
Write the evals before execution starts.
```

**Roles (ADR-061).** This skill plays DekSpec's Agent Role Specifications; the engineer never selects one. Authoring, revise and resync modes play the **`specifier`** role, audit modes the **`auditor`** role: run `dekspec resource role specifier` or `dekspec resource role auditor` at the start of the mode and follow it (a delegated `*-author` agent loads `specifier` itself). See [`_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) §The role each universal mode plays and [`_lib/agent_roles.md`](../_lib/agent_roles.md).

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Creation Mode**.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **Review mode** — `--review` flag. Skip to **Review Mode**.
- **Revise mode** — `--revise` flag. Proceed to **Fan-Out Mode**, then **Revise Mode**.
- **Creation mode** — no flag. Proceed to **Fan-Out Mode**, then **Creation Mode**.

**Routing:** substantive work (fan-out via Agent tool): (no flag), `--revise`. Inline: `--help`, `--teaching`, `--audit`, `--review`.

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md). Manifest:

- **subagent_type**: `general-purpose`.
- **substantive_modes**: [Creation (default), `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--audit`, `--review`]
- **bundle_list** (gathered BEFORE dispatch):
  1. The contract — `dekspec ib context IB-NNN --json`: outcome, acceptance conditions, binding obligations with canonical text (an eval-policy ADR or model-pinning obligation arrives here), Environment Prerequisites. If it reports `problems`, stop.
  2. `dekspec/templates/checklists/eval-quality-checklist.md` — the four measurement layers (Retrieval, Injection, Awareness/Hierarchy Scoring, End-to-End).
  3. Existing eval files the IB names (for `--revise`).
  4. Engineer guidance — `$ARGUMENTS` verbatim.
  5. Constraints — **The eval contract** section above.
- **expected_output_path**: the eval files the IB's `command:` conditions run, placed in the repository's own test layout (`tests/evals/` when it has none).
- **validation**: re-run **Audit Mode** on the result; surface any critical or important finding verbatim per [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md).

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md). Manifest:

```yaml
skill_name: "/write-evals"
one_line:   "Write the probabilistic evals an IB's acceptance conditions call for"
modes:
  - { flag: "", args: "<IB-NNN>", description: "Write the eval harness and data for each model-output condition; one property per condition, threshold enforced by the command. Before execution starts. (Creation Mode)" }
  - { flag: "--audit", args: "<IB-NNN>", description: "Read-only check of the IB's eval conditions against the eval contract. (Audit Mode)" }
  - { flag: "--review", args: "<IB-NNN>", description: "Walk the IB's open issues about its eval conditions one at a time with the engineer. (Review Mode)" }
  - { flag: "--revise", args: "<IB-NNN> <notes>", description: "Revise evals before execution starts. After start, use the amendment path. Notes: inline text or a .md/.txt path. (Revise Mode)" }
  - { flag: "--teaching", args: "<IB-NNN>", description: "Interactive tutorial: turn one model-output behavior into a threshold-enforcing eval condition. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-evals IB-214"
  - "/write-evals --audit IB-214"
  - "/write-evals --review IB-214"
  - "/write-evals --revise IB-214 \"uptake threshold 80%→85%; add a malformed-input scenario\""
  - "/write-evals --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md). Parameters:

- **artifact_kind**: the eval conditions of one IB
- **template_path**: the Acceptance example in **The eval contract** above
- **methodology_section**: §Test Strategy of `docs/dekspec-methodology.md`
- **exemplar_paths**: existing eval harnesses in this repository, if any
- **required_sections**: per condition: property, layer, scenario, threshold, trials, model pin, sampling, failure meaning

Structural checks to surface as open issues: a threshold without a trial budget, several properties sharing one command, an eval file not listed as a protected asset.

## Creation Mode

> The subagent's contract (see **Fan-Out Mode**).

**When required.** An IB needs evals when a condition is about model output: a probabilistic threshold ("≥80% of trials", "Recall@5 ≥ 0.7", "no hallucination on empty input"), or a model interaction on the outcome's load-bearing path. Purely deterministic plumbing needs only `/dekspec:write-tests`.

**Safety check.** `dekspec ib status IB-NNN`. If the run has started, stop and route to `dekspec ib amend`. If eval files the IB names already exist, warn before overwriting.

1. **Identify the properties.** Each model-output behavior the IB's outcome and conditions require, plus the adversarial ones its failure behavior implies (empty, malformed, boundary input). Each property becomes its own condition.
2. **Elicit each eval with the engineer, field by field.** Do not draft everything in one pass:
   - property and measurement layer (cite the eval-quality-checklist subsection);
   - input scenario, concrete and reproducible, as data files;
   - threshold as a range or rate, never a single value, taken from the IB's conditions or asked of the engineer;
   - pass criterion with its trial budget (trials × runs);
   - model pin, sampling (temperature, top_p, seed) and a judge model different from the candidate;
   - what failure means, i.e. which assumption is wrong when it fails.
3. **Write the harness and data** so that the command exits 0 only when the threshold holds and non-zero on a miss or on any harness error. Pin the reproducibility fields inside it.
4. **Bring the IB into line.** Each property needs its own `command:` condition, with an optional `timeout:` for long runs, and every eval file must be listed under "Protected acceptance assets". The Acceptance block is the IB's contract: while the IB is DRAFT or PROPOSED, add these through `/dekspec:write-ibs`. For an ACCEPTED IB, the edit is a change to what was authorized, so the authorizer re-baselines it (**Closing Step**) before execution.
5. **Check it bites.** Run each command against a deliberately failing or stubbed candidate and confirm it exits non-zero because the threshold was missed, not because of a crash.

## Revise Mode

> Fan-out delegated; same contract as Creation.

Before execution starts: compare the eval files with the IB's current conditions and the engineer's notes (threshold changes, new or removed properties, requested changes); present the plan; apply it on approval; re-run **Audit Mode**; then the **Closing Step**. After execution starts this mode refuses and routes to `dekspec ib amend --reviewer … --reason …`.

## Review Mode

Walk the IB's `## Open Issues` entries about its eval conditions (thresholds, scenarios, measurement layer) one at a time: show the issue, the condition it maps to and the relevant checklist layer, then recommend keep / change threshold / add scenario / split the property / escalate. Apply an agreed change through Revise Mode before execution starts, or through `/dekspec:write-ibs` when it changes the Acceptance block.

## Audit Mode

_Plays the **`auditor`** role — run `dekspec resource role auditor` first and follow it: deterministic `dekspec validate` / `dekspec audit` output is primary evidence; report findings, change nothing._

Read-only. For each condition of `IB-NNN` about model output:

- [ ] It has a `command:` verification (not prose, not a review) that measures exactly one property.
- [ ] The harness exits non-zero on a threshold miss and on harness errors; nothing turns an error into a pass.
- [ ] The threshold and trial budget live in the command or a protected asset.
- [ ] Every file the command reads is listed under Protected acceptance assets.
- [ ] Model, sampling, seed and trials are pinned; any judge model differs from the candidate.
- [ ] Every model-output behavior in the outcome and conditions has an eval; failure-behavior conditions have an adversarial eval.
- [ ] `dekspec ib status IB-NNN` shows the eval assets unchanged since the baseline, or each change amended.

```
EVAL AUDIT — IB-214
  ✅ AC-4 uptake ≥80% / 50 trials — command enforces threshold; assets protected
  ❌ AC-6 "quality score ≥ 0.8" — averages relevance + faithfulness; split into two conditions
  ⚠️ AC-5 tests/evals/fixtures/empty_corpus.json not listed as a protected asset
```

## Closing Step

Protect the evals before execution:

- **DRAFT / PROPOSED IB** — `dekspec ib accept IB-NNN` takes the baseline, evals included.
- **ACCEPTED, run not started** — `dekspec ib baseline IB-NNN --reason "evals written (/write-evals)"`.
- **Run started** — only `dekspec ib amend`.

## Common Pitfalls

- Don't let the builder author, "help draft" or tune an eval. When grader and candidate are the same, the eval proves nothing.
- Don't fold several properties into one pass/fail. A composite score hides the failing property.
- Don't write a single expected value. Use a threshold over a pinned trial budget.
- Don't leave a harness, fixture or rubric off the Protected acceptance assets list. The builder could change what the eval means without tripping the baseline.
- Don't make a harness exit 0 when it cannot reach the model. Declare the dependency as an Environment Prerequisite so an outage blocks truthfully.
- Don't put deterministic checks here. They are tests.

## Verification Checklist

- [ ] Each model-output property is its own `command:` condition whose command enforces its threshold and fails on harness errors.
- [ ] Every eval file is listed under the IB's Protected acceptance assets.
- [ ] Model, sampling, seed, trial budget and judge model are pinned inside the harness.
- [ ] Each command was shown to fail against a failing candidate for the right reason.
- [ ] The evals are baselined (`dekspec ib accept`, or `dekspec ib baseline --reason …` before `ib start`).
- [ ] Audit Mode reports no critical or important finding.
