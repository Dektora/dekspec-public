---
name: forensics
description: Read-only post-mortem for stuck, failed, or anomalous DekSpec construction sessions — collects git/worktree/bead/linkage evidence, detects known failure fingerprints (stuck loop, orphaned worktree, mid-red crash, incomplete LOCK chain, IB drift, test regression, context-overflow, cross-session collision), and writes a structured forensic report with a root-cause hypothesis + recommended recovery commands. Never modifies any artifact. Use when a coding session hung, a wave was killed, worktrees were orphaned, or a merge/LOCK chain ended in a weird state.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Bash Write
argument-hint: [--help] [problem description]
related_skills: [diagnose, exec-coding-session, land-intent]
---

Run a **read-only post-mortem** on a DekSpec construction session that went
wrong. Construction (bead dispatch → worktree → red/green → merge → LOCK) fails
in a handful of recognizable ways; this skill collects the evidence, matches it
against those fingerprints, and writes a structured diagnostic report with a
root-cause hypothesis and concrete recovery commands. It **diagnoses, it does
not remediate** — it creates no beads, edits no artifacts, and the engineer
decides what to do with the findings.

This is the construction-session counterpart to `/dekspec:diagnose` (which
post-mortems a *bug* via a deterministic repro). Forensics post-mortems the
*session* via git/worktree/bead archaeology.

## Starter Prompt

```prompt
/dekspec:forensics the INT-204 coding session hung mid-wave and left worktrees behind

Investigate read-only: gather git/worktree/bead/linkage evidence, detect the
failure fingerprint (orphaned worktrees? mid-red crash? incomplete LOCK chain?),
and write a forensic report with a root-cause hypothesis and the exact recovery
commands. Change nothing.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Forensics mode**.

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Forensics mode** — no flag (default). The positional `$ARGUMENTS` is the
  free-text problem description; if empty, ask the engineer for one before
  proceeding. Run the loop below.

This skill exposes no lifecycle/audit/review flags — it is a read-only
investigation, not an artifact-lifecycle authoring skill (exempt from the
`_lib/mode_dispatcher.md` universal-mode set, which applies only to `write-*`).

## Forensics mode

### Step 1 — collect evidence (read-only)

Run, via the Bash tool (all read-only; if a `dekspec`/`br` call fails because the
tool is absent, note it and continue — the git evidence stands alone):

```bash
# Pick the integration base that actually exists (local-only repos have no origin/main).
BASE=$(git rev-parse --verify -q origin/main >/dev/null && echo origin/main || echo main)

# Git activity (current branch)
git log --oneline -30
git log --format="%H %ai %s" -30
git log --name-only --format="" -20 | sort | uniq -c | sort -rn | head -20   # hot files
git status --short
git diff --stat
git worktree list

# Branch-only work — orphaned-worktree + mid-red commits live on branches NOT
# reachable from the base, so the current-branch log above will NOT show them.
# Enumerate every branch and its unmerged commits against the base:
git branch -a
for b in $(git for-each-ref --format='%(refname:short)' refs/heads); do
  ahead=$(git log --oneline "$BASE..$b" 2>/dev/null)
  [ -n "$ahead" ] && printf '\n--- unmerged on %s ---\n%s\n' "$b" "$ahead"
done

# DekSpec health (canonical audit forms; note-and-continue if the CLI is absent)
dekspec audit doctor --at .
dekspec audit linkage --at .

# Bead state — `br` prints glyphs (○ open / ● closed), not the word CLOSED, so a
# `grep -v CLOSED` filter is a no-op. Use br's own status filter:
br list --status open
br ready
# IB drift: cross-check each open bead ID against the merge/feat history.
for id in $(br list --status open --json 2>/dev/null | grep -oE '"id":"[^"]+"' | cut -d'"' -f4); do
  git log --oneline --grep "$id" | head -1 | sed "s/^/open bead $id <- /"
done

# LOCK chain state
grep -rl "Status: PROPOSED" dekspec/ --include="*.md"
grep -rl "Status: LOCKED" dekspec/ --include="*.md"
```

### Step 2 — match the failure fingerprints

For each pattern, check the signal; record HIGH / MEDIUM / LOW with verbatim evidence:

- **Stuck loop** — the same `src/` or `tests/` file appears in 3+ consecutive commits in a short window (the hot-files count above). The construction agent is oscillating on one file.
- **Orphaned worktrees** — `git worktree list` shows scratch worktrees whose branch exists but never merged. Check `git log --oneline "$BASE..<branch>"` (the per-branch enumeration from Step 1) to see whether the work survived; surface the last commit SHA.
- **Mid-red crash** — a worktree branch carries a red checkpoint commit (`test(N.X): …`) with no following green commit and no merge into `int/`. The red commit is a durable checkpoint — surface the red SHA + the failing test files.
- **Incomplete LOCK chain** — `dekspec audit linkage` (or the PROPOSED/LOCKED grep cross-ref) shows a `PROPOSED` artifact whose dependents are already `LOCKED` (e.g. an ADR left PROPOSED after the WS/IB that cite it LOCKED).
- **IB drift** — `br list --all` shows beads still OPEN whose corresponding merge/feat commit already exists in `git log`.
- **Test regression** — commit messages with "fix test", "revert", "regression", or repeated red→green cycles on the same file.
- **Context-overflow fingerprint** — a construction branch has only partial work (a red commit, no green) and the session log shows a "Prompt is too long" cutoff; the recovery is to re-brief a fresh agent with "red tests = spec" from the last red SHA.
- **Cross-session collision** — `git status --short` is non-empty on the main worktree while another session's branch is checked out elsewhere; may indicate two sessions colliding (cf. concurrent-stash hazards).

### Step 3 — write the report (the only file this skill writes)

Write to `docs/workspace/<area>/pm/forensics/report-<UTC-timestamp>.md` when a
`docs/workspace/` tree exists; otherwise fall back to
`.dekspec-forensics/report-<UTC-timestamp>.md` (create the dir). Use this shape:

```markdown
# Forensic Report — DekSpec Construction

**Generated:** <ISO timestamp>
**Problem:** <engineer's description>
**Repo:** <pwd>   **Branch:** <current>

## Git Activity
- Last commit: <date> — "<message>"
- Uncommitted changes: <yes/no>
- Active worktrees: <list>

## DekSpec State
- Doctor: <CLEAN / findings>
- Linkage: <issues / clean>
- Open beads: <list>
- PROPOSED artifacts with LOCKED dependents: <list>

## Anomalies
### <Type> — <HIGH/MEDIUM/LOW>
**Evidence:** <verbatim>
**Interpretation:** <what it means>

## Root Cause Hypothesis
<1-3 sentences>

## Recommended Actions
1. <specific step with the exact command>
2. ...
```

### Step 4 — report back

Surface the report path + the root-cause hypothesis + the top recommended
action inline. **Remediate nothing** — no beads, no artifact edits, no
worktree rescue performed; the recovery commands are recommendations the
engineer runs deliberately.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:forensics"
one_line:   "Read-only post-mortem of a stuck/failed DekSpec construction session — collect git/worktree/bead/linkage evidence, match failure fingerprints, write a forensic report with a root-cause hypothesis + recovery commands. Remediates nothing."
modes:
  - { flag: "",       args: "[problem description]", description: "Forensics mode — collect read-only evidence, detect anomaly fingerprints, write a forensic report with root-cause hypothesis + recommended recovery commands." }
  - { flag: "--help", args: "",                      description: "Show this help message." }
examples:
  - "/dekspec:forensics the INT-204 coding session hung mid-wave"
  - "/dekspec:forensics orphaned worktrees after a wave kill"
  - "/dekspec:forensics --help"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## When to use

- A construction session hung, a wave was killed, worktrees were orphaned, or a
  merge / LOCK chain ended in an anomalous state and you need a systematic
  diagnosis before deciding how to recover.

## When NOT to use

- To reproduce and fix a *bug* — that is `/dekspec:diagnose` (deterministic repro
  loop), not a session post-mortem.
- To actually perform recovery (re-dispatch, worktree rescue, re-LOCK) — this
  skill only reports; remediation is the engineer's deliberate next step.

## Related

- `/dekspec:diagnose` — the bug-level post-mortem sibling (repro-first debugging).
- `/dekspec:exec-coding-session` — the construction surface this skill post-mortems.
- `/dekspec:land-intent` — the review-and-land phase whose partial completion forensics often diagnoses.
