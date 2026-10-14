---
name: pr-branch
description: Build a clean PR branch by filtering out spec-only commits (Intent/BS/IB/ADR/IC/AE status bumps, index reconciliation, pm STATE/LEDGER) so code reviewers see only the implementation diff, not DekSpec artifact churn. Mixed code+spec commits are cherry-picked with the spec-only paths stripped. Pure git; creates `<branch>-pr` ready to push. Use before opening a code-review PR on a DekSpec-managed repo.
mode: lite
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Bash
argument-hint: [--help] [target-branch]
related_skills: [land-intent, orchestrate-coding-session]
---

Build a **clean PR branch** that carries only the code reviewers need to see.

DekSpec-managed repos interleave spec commits (ADR/Intent/BS/IB/IC/AE status
bumps, index reconciliation, `pm/` STATE+LEDGER rows, glossary edits) with code
commits. Opened as-is, a PR buries the implementation diff under `dekspec/` and
`docs/workspace/` churn, degrading review. This skill produces a sibling
`<branch>-pr` branch with the spec-only noise filtered out — code commits and
the code half of mixed commits, nothing else.

The `dekbuilder pr-branch` command uses **pure git**. The original branch is
never modified — the PR branch is built fresh from the target.

## Starter Prompt

```prompt
/dekbuilder:pr-branch main

Build a clean PR branch off main: classify each commit ahead of main, drop the
spec-only ones (Intent/BS/IB/ADR status bumps, index rows, pm STATE/LEDGER),
keep code + structural-governance commits, and strip spec-only files out of
mixed commits. Leave me a <branch>-pr branch with zero dekspec/ churn in the
diff, ready to push.
```

## Mode Detection

See `dekspec resource lib mode_detection_template.md` (Spec-owned `_lib/mode_detection_template.md`). Default mode: **PR-Branch mode**.

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **PR-Branch mode** — no flag (default). The optional positional `$ARGUMENTS`
  is the target branch to diff against (default: `main`). Run the command below.

This skill exposes no lifecycle/audit/review flags — it is a one-shot branch
builder, not an artifact-lifecycle authoring skill (exempt from the
`_lib/mode_dispatcher.md` universal-mode set, which applies only to the
`write-*` skills).

## PR-Branch mode

### Artifact classification

**EXCLUDE (transient spec-only noise — drop these):**

- `dekspec/intents/`, `dekspec/behavior-specs/`, `dekspec/impl-briefs/`,
  `dekspec/interface-contracts/`, `dekspec/architecture-elements/` —
  modified or deleted files (including status bumps, e.g. PROPOSED→ACCEPTED) — **except**
  the IBs this branch delivers (see INCLUDE ALWAYS)
- `dekspec/intent-index.md`, `dekspec/behavior-spec-index.md`, `dekspec/ib-index.md`,
  `dekspec/mission-index.md` — index reconciliation
- `docs/workspace/**/pm/STATE.md`, `docs/workspace/**/pm/LEDGER.md`, `pm/` —
  dark-execution ledger rows

Old-form repositories not yet migrated are still filtered: `dekspec/working-specs/`, `working-spec-index.md` and `ws-index.md` follow the same rules as `dekspec/behavior-specs/` and `behavior-spec-index.md`. <!-- dekspec:names-both-forms -->

A same-number move from an old-form file to a new-form file is transient on
both paths, even when the slug or content changes and git detects no rename.

**INCLUDE ALWAYS (substantive / structural governance):**

- `dekspec/domain-glossary.md`, `dekspec/constitution.md`, `dekspec/system-vision.md`
- **newly added** Intent / ADR / AE / BS / IC / IB files (except a same-number
  move); other transient paths in the same commit are still stripped
- `.dekspec/execution/**`, and every change to an IB whose execution record
  (`.dekspec/execution/<IB>/`) this branch changes — the IB's status is its
  authorization / completion decision, and `dekspec delivery check` reads both
  at the PR head (ADR-057, ADR-058)
- any commit touching `src/`, `tests/`, `infra/`, `pyproject.toml`, `setup.py`,
  `tooling/`, `plugins/`, `.github/`, or other real code/config

**MIXED (code + transient-spec):** include the commit, but strip the
transient-spec paths from it, restoring them to the PR branch’s state before
that commit. **CODE** has no transient path; **SPEC_ONLY** has only transient
paths and is skipped; **MIXED** has both kinds.

### Run the command

Run `dekbuilder pr-branch $ARGUMENTS` once and relay its report. The target
defaults to `main`. The command owns classification, replay and verification;
it reports original and PR commit/file counts, excluded commits, stripped
paths, any leaked paths, and the next step. It never pushes or forces, refuses
an existing `<branch>-pr`, and restores the original checkout after success.
On a cherry-pick conflict it aborts, deletes only the PR branch it created,
restores the original checkout, and names the failing commit. Relay refusals
and leaked paths to the operator; a leaked-path report leaves the PR branch
available for inspection.

### Evidence and the landing gate

Evidence and review verdicts bind to a **content** fingerprint, not to commit
SHAs (ADR-057), and IB status lines, index files and `.dekspec/execution/**`
are outside it. So:

- A pure commit-shape rewrite — same final content, different commits — keeps
  every IB's evidence and verdict valid.
- Dropping or stripping anything else the fingerprint covers (a `pm/` ledger
  row, a spec body edit) changes the head content: deterministic evidence goes
  stale and must be regenerated (`dekspec delivery verify` on `<branch>-pr`),
  and a verdict survives only if the dropped change touched none of its
  reviewed surfaces.
- Either way the head changed, so `dekspec delivery check` must pass again on
  `<branch>-pr` before merge. `/dekbuilder:land-intent` runs it; CI runs
  `dekspec delivery check --rerun` on the PR head independently.

### Edge cases

- **No spec-only commits** — the PR branch is a faithful clone of the original
  (every commit is `CODE`/`MIXED`); report that nothing was filtered.
- **Nothing ahead of target** — report and stop; no branch created.
- **A new-artifact ADR/AE add interleaved with status bumps in one commit** —
  keep the new artifact (the add is substantive) and strip the other
  transient paths in that commit.

## Help Mode

See `dekspec resource lib help_mode_template.md` (Spec-owned `_lib/help_mode_template.md`) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekbuilder:pr-branch"
one_line:   "Build a clean <branch>-pr branch with spec-only commits filtered out and spec-only files stripped from mixed commits, so code PRs show only the implementation diff."
modes:
  - { flag: "",       args: "[target-branch]", description: "PR-Branch mode — classify commits ahead of target (default main), drop spec-only ones, strip spec paths from mixed commits, emit <branch>-pr." }
  - { flag: "--help", args: "",                description: "Show this help message." }
examples:
  - "/dekbuilder:pr-branch"
  - "/dekbuilder:pr-branch main"
  - "/dekbuilder:pr-branch --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## When to use

- Before opening a **code-review PR** on a DekSpec-managed branch that mixed
  spec churn with implementation — so reviewers see only the code.

## When NOT to use

- To land/merge an Intent's PRs through review — that is `/dekbuilder:land-intent`.
- To dispatch the coding itself — that is `/dekbuilder:orchestrate-coding-session`.
- On a branch with no spec churn — it works, but it only clones the branch.

## Related

- `/dekbuilder:land-intent` — drives the resulting PR(s) through the review pipeline to a landed state.
- `/dekbuilder:orchestrate-coding-session` — produces the code commits this skill later separates from spec churn.
