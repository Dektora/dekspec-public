---
name: pr-branch
description: Build a clean PR branch by filtering out spec-only commits (Intent/WS/IB/ADR/IC/AE status bumps, index reconciliation, pm STATE/LEDGER) so code reviewers see only the implementation diff, not DekSpec artifact churn. Mixed code+spec commits are cherry-picked with the spec-only paths stripped. Pure git; creates `<branch>-pr` ready to push. Use before opening a code-review PR on a DekSpec-managed repo.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Bash
argument-hint: [--help] [target-branch]
related_skills: [land-intent, orchestrate-coding-session]
---

Build a **clean PR branch** that carries only the code reviewers need to see.

DekSpec-managed repos interleave spec commits (ADR/Intent/WS/IB/IC/AE status
bumps, index reconciliation, `pm/` STATE+LEDGER rows, glossary edits) with code
commits. Opened as-is, a PR buries the implementation diff under `dekspec/` and
`docs/workspace/` churn, degrading review. This skill produces a sibling
`<branch>-pr` branch with the spec-only noise filtered out — code commits and
the code half of mixed commits, nothing else.

It is **pure git**: no new Python, no DekSpec CLI. The original branch is never
modified — the PR branch is built fresh from the target.

## Starter Prompt

```prompt
/dekspec:pr-branch main

Build a clean PR branch off main: classify each commit ahead of main, drop the
spec-only ones (Intent/WS/IB/ADR status bumps, index rows, pm STATE/LEDGER),
keep code + structural-governance commits, and strip spec-only files out of
mixed commits. Leave me a <branch>-pr branch with zero dekspec/ churn in the
diff, ready to push.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **PR-Branch mode**.

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **PR-Branch mode** — no flag (default). The optional positional `$ARGUMENTS`
  is the target branch to diff against (default: `main`). Run the loop below.

This skill exposes no lifecycle/audit/review flags — it is a one-shot branch
builder, not an artifact-lifecycle authoring skill (exempt from the
`_lib/mode_dispatcher.md` universal-mode set, which applies only to the
`write-*` skills).

## PR-Branch mode

### Artifact classification

**EXCLUDE (transient spec-only noise — drop these):**

- `dekspec/intents/`, `dekspec/working-specs/`, `dekspec/impl-briefs/`,
  `dekspec/interface-contracts/`, `dekspec/architecture-elements/` —
  *status-bump-only* edits (PROPOSED→ACCEPTED→LOCKED, index rows)
- `dekspec/intent-index.md`, `dekspec/ws-index.md`, `dekspec/ib-index.md`,
  `dekspec/mission-index.md` — index reconciliation
- `docs/workspace/**/pm/STATE.md`, `docs/workspace/**/pm/LEDGER.md`, `pm/` —
  dark-execution ledger rows

**INCLUDE ALWAYS (substantive / structural governance):**

- `dekspec/domain-glossary.md`, `dekspec/constitution.md`, `dekspec/system-vision.md`
- commits that **ADD a new** ADR / AE / WS / IC / IB file (not just bump status)
- any commit touching `src/`, `tests/`, `infra/`, `pyproject.toml`, `setup.py`,
  `tooling/`, `plugins/`, `.github/`, or other real code/config

**MIXED (code + transient-spec):** include the commit, but strip the
transient-spec paths from it (`git rm --cached` after a `--no-commit`
cherry-pick).

### Algorithm (pure git)

1. **Resolve the target** — `$ARGUMENTS` or `main`. Confirm it exists
   (`git rev-parse --verify <target>`); if not, report and stop. Record the
   current branch as `<branch>`.
2. **Classify each commit** ahead of target (`git rev-list --reverse <target>..HEAD`).
   For each commit, list its files (`git show --name-only --format= <sha>`) and
   bucket them:
   - `NON_SPEC` — matches an INCLUDE-always code/config path
   - `STRUCTURAL_SPEC` — a new-artifact add or a glossary/constitution/SV edit
   - `TRANSIENT_SPEC` — an EXCLUDE path (status-bump-only / index / pm)
   - **Class:** `CODE` (NON_SPEC or STRUCTURAL_SPEC present → include) ·
     `SPEC_ONLY` (only TRANSIENT_SPEC → exclude) ·
     `MIXED` (code/structural **and** transient → include, strip transient)
3. **Create the PR branch** — `git checkout -b <branch>-pr <target>` (refuse if
   `<branch>-pr` already exists; ask the operator to delete it first).
4. **Replay commits in order:**
   - `CODE` → `git cherry-pick <sha>`
   - `MIXED` → `git cherry-pick --no-commit <sha>`, then reset each transient
     path back to the target's state and commit the code-only remainder:
     `git restore --source=HEAD --staged --worktree <each transient path>`
     then `git commit -C <sha>`. (`restore --source=HEAD` correctly handles
     both cases: a *status-bump modify* reverts to the target's version, so the
     spec file stays unchanged — no deletion in the diff; a *newly-added* spec
     file is dropped from index + worktree, leaving no untracked residue. Do
     NOT use `git rm` here — it would delete a pre-existing spec file and put a
     deletion in the PR diff.)
   - `SPEC_ONLY` → skip (do not cherry-pick)
   - On any cherry-pick **conflict**: `git cherry-pick --abort`, restore the
     original branch, and report the offending commit — **never force**.
5. **Verify** — the diff must contain zero transient-spec paths:
   ```bash
   git diff --name-only <target>..<branch>-pr \
     | grep -E '^dekspec/(intents|working-specs|impl-briefs|interface-contracts|architecture-elements)/|(^|/)(intent|ws|ib|mission)-index\.md$|^docs/workspace/.*/pm/|^pm/'
   ```
   Expect empty. If non-empty, a classification missed a path — report it.
6. **Report** — original N commits / F files; PR branch M commits / G files;
   K spec-only commits excluded; the new branch name; the next step
   (`git push -u origin <branch>-pr && gh pr create`).

### Edge cases

- **No spec-only commits** — the PR branch is a faithful clone of the original
  (every commit is `CODE`/`MIXED`); report that nothing was filtered.
- **Nothing ahead of target** — report and stop; no branch created.
- **A new-artifact ADR/AE add interleaved with status bumps in one commit** —
  that commit is `STRUCTURAL_SPEC` (the add is substantive); keep it whole.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:pr-branch"
one_line:   "Build a clean <branch>-pr branch with spec-only commits filtered out and spec-only files stripped from mixed commits, so code PRs show only the implementation diff."
modes:
  - { flag: "",       args: "[target-branch]", description: "PR-Branch mode — classify commits ahead of target (default main), drop spec-only ones, strip spec paths from mixed commits, emit <branch>-pr." }
  - { flag: "--help", args: "",                description: "Show this help message." }
examples:
  - "/dekspec:pr-branch"
  - "/dekspec:pr-branch main"
  - "/dekspec:pr-branch --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## When to use

- Before opening a **code-review PR** on a DekSpec-managed branch that mixed
  spec churn with implementation — so reviewers see only the code.

## When NOT to use

- To land/merge an Intent's PRs through review — that is `/dekspec:land-intent`.
- To dispatch the coding itself — that is `/dekspec:orchestrate-coding-session`.
- On a branch with no spec churn — it works, but it only clones the branch.

## Related

- `/dekspec:land-intent` — drives the resulting PR(s) through the review pipeline to a landed state.
- `/dekspec:orchestrate-coding-session` — produces the code commits this skill later separates from spec churn.
