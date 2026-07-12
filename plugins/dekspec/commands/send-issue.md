---
description: File a GitHub issue against Dektora/dekspec. Aggressively auto-fills every section the LLM can reasonably infer from the conversation context, the repo state, recent commits, the CHANGELOG, and open `br` beads. The operator's role is to *review* a near-complete issue, not to dictate its content. Confirms before `gh issue create` fires.
allowed-tools: Bash(gh issue create:*), Bash(gh issue list:*), Bash(gh issue view:*), Bash(gh auth status:*), Bash(gh repo view:*), Bash(gh search issues:*), Bash(git rev-parse:*), Bash(git log:*), Bash(git status:*), Bash(git remote:*), Bash(git diff:*), Bash(git blame:*), Bash(br list:*), Bash(br search:*), Bash(br ready:*), Bash(grep:*), Bash(rg:*), Bash(mktemp:*), Bash(cat:*), Bash(rm:*), Read, Grep, Glob, AskUserQuestion
argument-hint: [optional seed words; the LLM will expand from session context if the seed is sparse or absent]
disable-model-invocation: false
---

File a GitHub issue against `Dektora/dekspec`, leaning on the in-session LLM context to **pre-fill every section that can be inferred**. The operator's argument string is a *seed*, not a ceiling — the command will expand, classify, prioritize, search for dupes and related artifacts, and draft a near-final body. The operator's job is to review the draft, not to dictate it.

**Bias toward over-filling.** Section blank because evidence is genuinely absent is acceptable; section blank because the LLM didn't bother to look is not. If the conversation, the repo state, the CHANGELOG, or `br` history contains relevant material, surface it in the draft.

## Preconditions

1. `gh auth status` exits 0. If not: surface `gh auth login --hostname github.com --web` and stop. Do **not** prompt the operator to paste a PAT in chat.
2. The repo `Dektora/dekspec` is reachable via `gh repo view Dektora/dekspec --json name`. If the request fails with `HTTP 404` or `HTTP 403`, surface the error verbatim and stop — the operator's auth principal may not have access to the proprietary repo.

## Steps

### 1. Gather inputs (aggressive auto-fill expected)

The operator's argument string is a **seed**, not the issue body. If absent or sparse (one word, fragment, "the bump-version thing"), expand it — do not stop and ask the operator what they meant. The expansion comes from:

- **The full available conversation context** — not just the last few turns. Look back across this session for: the specific topic the operator was working on, errors they hit, files they modified, commands they ran, decisions they made, surprise they expressed, follow-ups they deferred. The LLM has this in working memory; use it.
- **The operator's wording style and severity cues** — "broken", "weird", "this is annoying", "would be nice if", "why does X work this way" each signal a different category + severity. Mine the tone.
- **Implicit references** — "the precheck change" / "the install script removal" / "the new command" should resolve to concrete commits, files, or PRs without asking the operator to restate them.

Run these **read-only** captures and incorporate every relevant signal:

- `git rev-parse --abbrev-ref HEAD` → current branch.
- `git rev-parse HEAD` → current commit SHA.
- `git status --short` → uncommitted state if any (mention dirty files only if they touch the topic of the issue).
- `git log -1 --format='%h %s'` → tip commit subject.
- `git remote get-url origin` → upstream URL.
- `git log --oneline -20` → recent commit history (mine for the commit most likely to be the cause if this is a bug, or the commit that introduced the surface the operator is reporting on).
- `tooling/dekspec/__init__.py::__version__` → dekspec library version (via `Read`).

### 1b. Research phase — pre-fill Related + dupe-check

Before drafting, do the legwork the operator would otherwise have to do:

- **Dupe search via GitHub**: `gh search issues "<topic keyword>" --repo Dektora/dekspec --state open --limit 5`. If any open issue's title overlaps materially with the proposed topic, surface the candidate(s) in the preview as `## Related → potential duplicate` and **invite the operator to choose** between filing-anyway / piggybacking on the existing issue (via the preview gate in step 5).
- **Related LOCKED dekspec/ artifacts**: `Grep` under `dekspec/intents/`, `dekspec/architecture-elements/`, `dekspec/adrs/` for the topic keyword. Cite any matches by ID + one-line gloss in `## Related`.
- **Related CHANGELOG entries**: `Grep` `CHANGELOG.md` for the topic keyword. Cite the most-recent matching `## [vX.Y.Z]` heading + one-liner so the issue records "this surface last changed in vX.Y.Z".
- **Related open `br` beads**: `br list --status open` (parse, filter for topic-keyword matches in title/body). If any match, surface them in `## Related` so the operator can decide whether the GitHub issue is even needed (a `br` bead may already cover it for in-repo work).
- **Related recent commits**: pick the 1–3 most-recent commits from `git log --oneline -20` whose subject matches the topic. Cite them by short SHA + subject.

Skip any of these silently if a tool returns an error or no matches — the goal is *speed*, not exhaustive coverage.

### 2. Classify the report

Pick exactly one of the following categories. Match against the labels that already exist on `Dektora/dekspec` (verified by `gh label list` before this command shipped):

| Category   | GitHub label    | When to use |
|-----------:|-----------------|-------------|
| Bug        | `bug`           | Something that worked (or is documented to work) is broken. Includes regressions, crashes, wrong output. |
| Feature    | `enhancement`   | New capability or extension of an existing one. Includes "would be nice if dekspec could…" requests. |
| Feedback   | `enhancement`   | Workflow / ergonomics critique that isn't quite a feature request yet. Falls back to `enhancement` since the repo has no `feedback` label today. |
| Question   | `question`      | Asking how something works, why a decision was made, or whether a behavior is intentional. |
| Docs       | `documentation` | Methodology docs, CLI help text, skill prose, README, CHANGELOG — anything wrong or missing in a written surface. |

If genuinely ambiguous between two categories, prefer the more specific one (Bug > Docs > Question > Feature > Feedback).

### 3. Infer priority and severity

These do NOT map to GitHub labels (the repo's label set is intentionally vanilla); they go into the **issue body** as a structured block so they are grep-able from the operator's GitHub web UI and from `gh issue list --search`.

**Severity** — how bad is the impact when this is hit?

| Severity | Use when |
|---------:|----------|
| `S0` critical | Data loss, security exposure, audit-gate bypass, or a complete blocker for any consumer install. Choose this sparingly. |
| `S1` high     | Workflow-blocking for an active operator. No clean workaround. Examples: an authoring skill crashes mid-flow, audit doctor exits non-zero on a clean tree. |
| `S2` medium   | Annoying but workaround-able. Examples: an error message references a retired surface, a help string is wrong, a non-critical drift warning. |
| `S3` low      | Cosmetic, documentation polish, nice-to-have. |

**Priority** — when should this be picked up relative to other open work?

| Priority | Use when |
|---------:|----------|
| `P0` now      | Hold-the-line; pick up this sprint. Reserved for `S0` plus a small slice of `S1`. |
| `P1` next     | Pick up in the next planning cycle. |
| `P2` later    | Backlog; pick up when adjacent work touches the same surface. |
| `P3` someday  | Recorded for completeness; no commitment to land it. |

**Inference is aggressive.** Triangulate from: the operator's tone words, the specificity of evidence, whether a fix would change consumer-visible behavior, whether the issue blocks a current branch's CI, whether it touches a LOCKED `dekspec/` artifact, whether it duplicates an existing `br` bead or open GH issue. Make a confident call and **state the reasoning in one sentence** under the Classification block so the operator can sanity-check the inference rather than re-derive it.

The only override paths are:
- The operator's argument explicitly names a severity or priority ("P0", "critical", "blocker", "S0", "drop-everything", "nice-to-have", "low priority", "S3", etc.) — honor it verbatim, do not re-derive.
- The operator picks **Edit** at the preview gate and instructs a change.

Do not default to `S2` / `P2` as a hedge — pick the call the evidence actually supports.

### 4. Draft title + body

**Title format:**

```
[<CATEGORY>] <one-line summary, ≤72 chars, sentence case, no trailing period>
```

Where `<CATEGORY>` is one of: `Bug`, `Feature`, `Feedback`, `Question`, `Docs`. (Category goes into the title for visual scanning; the GitHub label provides the machine-grep surface.)

**Body template (markdown).** Every section is auto-filled by the LLM. Operator review happens at the preview gate (step 5), not during drafting.

```markdown
## Summary

<one paragraph. State what's wrong / what's wanted / what's being asked. Do not restate the title. If this is a bug, lead with the symptom, not the suspected cause.>

## Classification

- **Category:** <Bug | Feature | Feedback | Question | Docs>
- **Severity:** <S0 critical | S1 high | S2 medium | S3 low>
- **Priority:** <P0 now | P1 next | P2 later | P3 someday>
- **Reasoning:** <one sentence on WHY this severity and priority — e.g. "S1/P1: workflow-blocking for any consumer running `dekspec init` since v0.91.0, no override.">
- **Drafted by:** Claude (via /send-issue), reviewed by operator before send.

## Context

<3–8 bullets. Supporting evidence from the conversation, the repo state, recent commits, the CHANGELOG. File paths in backticks. Commands in fenced code blocks. Error strings quoted verbatim. Concrete > abstract. Drop the section only if the conversation truly contains zero relevant signal.>

## Reproduction (Bug + Docs)

<numbered steps. Bug = how to trigger the misbehavior. Docs = where the wrong/missing doc is and how to encounter it. Include exact command lines in fenced code blocks. Required for Bug; optional but encouraged for Docs.>

## Expected vs actual (Bug)

- **Expected:** <one line>
- **Actual:** <one line — include the error message verbatim in a fenced code block if applicable>

## Proposed direction (Feature + Feedback)

<rough sketch of the desired behavior or capability. Not a spec. Cite any existing skill/CLI/audit-rule the proposal would extend or replace. Skip for Bug / Question / Docs.>

## What I've already tried (Question)

<numbered list: documents read, commands run, hypotheses ruled out. This is what makes a question productive instead of a "please educate me" ask. Skip for non-Question.>

## Trigger (Feedback)

<one or two sentences on the situation that surfaced the feedback — what workflow was the operator in, what made the friction visible. Skip for non-Feedback.>

## Environment

- **Branch:** `<value from git rev-parse --abbrev-ref HEAD>`
- **Commit:** `<short SHA + subject from git log -1>`
- **Origin:** `<value from git remote get-url origin>`
- **Working tree:** `<clean | dirty (N uncommitted files; list any that touch this issue)>`
- **dekspec version:** `<value from tooling/dekspec/__init__.py>`
- **Platform:** <linux | macos | other — mention only if relevant to the report>

## Related

<This section MUST be filled when the research phase (step 1b) found anything. Format as a bulleted list, each item one line:>

- **Potential duplicate (GitHub):** #<NN> "<title>" — <one-line gloss of overlap>
- **Related Intent / AE / ADR:** `<ID>` "<one-line gloss>"
- **Last changed in CHANGELOG:** `vX.Y.Z` — <one-line gloss of the entry>
- **Related open `br` bead:** `<bead-id>` "<title>" — <one-line gloss>
- **Possibly-causal commit:** `<short SHA>` <subject>

<Omit the entire section ONLY if the research phase legitimately found nothing. Do not write "N/A" or "none found" — the absence of the section IS the signal.>
```

Sections marked `(<category>)` apply when the classification matches. Omit the section header entirely when it doesn't apply — do not render an empty header with no body.

### 5. Preview + confirm

Render the proposed title, label, and full body verbatim in chat (in a fenced markdown block so the operator can copy-edit if they pick Edit). Above the rendered draft, surface a **one-line confidence summary** of what the LLM auto-filled vs. what is genuinely thin — e.g. *"Category + severity inferred from 4 conversation turns; 1 likely-duplicate GH issue found (#41); reproduction steps reconstructed from the operator's earlier `bash scripts/install-dekspec.sh` invocation."* This lets the operator skim the high-signal bits before reading the full body.

Then invoke `AskUserQuestion` with these options. **Recommended option goes first** per session convention; default to **Send as drafted** unless the dupe search surfaced a strong match, in which case lead with **Piggyback on existing**.

- **Send as drafted** — proceed to step 6 with the body unchanged.
- **Piggyback on existing** (only if step 1b found a likely duplicate) — abandon the draft and instead `gh issue comment <NN> --body-file ...` against the duplicate. Same body, no new issue created. Surfaces only when the dupe-search hit ranks above a clear threshold.
- **Edit before send** — accept a freeform revision instruction from the operator (in chat prose), apply it, regenerate the body, loop back to step 5 with the revised draft. Do not loop to step 4 — the classification + research already happened.
- **Cancel** — stop without filing anything. Confirm the cancellation in one line.

Operator picks `Other` and writes a freeform note → treat as **Edit before send** with the note as the change request.

### 6. Send

Build the `gh issue create` command. Pass the body via a `--body-file` argument (write the body to a temp file first; do NOT inline a long body via `--body "..."` because shell quoting becomes a hazard at length).

```bash
TMP=$(mktemp -t dekspec-issue.XXXXXX.md)
cat > "$TMP" <<'ISSUE_BODY_EOF'
<the rendered body, verbatim>
ISSUE_BODY_EOF
gh issue create \
  --repo Dektora/dekspec \
  --title "<the rendered title>" \
  --label "<the chosen GitHub label>" \
  --body-file "$TMP"
rm -f "$TMP"
```

On success, `gh issue create` prints the issue URL on stdout. Surface that URL on its own line back to the operator. On non-zero exit, surface stderr verbatim, leave the temp file in place, and tell the operator the path so they can retry manually.

### 7. Post-send

- Echo the issue URL.
- One sentence reminding the operator that a `br` bead is a *separate* tracker for **in-repo** work (per `CLAUDE.md` § Issue tracking) — GitHub issues are the **public** report surface. Do not auto-create a paired `br` bead.

## When to use

- An operator hits unexpected behavior, polish issue, missing feature, or has a question they want recorded against the public repo rather than the in-repo `br` tracker.
- Best fired right after the surprising-thing happens, while the relevant conversation context is fresh — `/send-issue` will pull from that context to populate `## Context`.

## When NOT to use

- For **in-repo, claim-and-execute** work — use `br create` and the bead workflow per `CLAUDE.md` § Issue tracking.
- For **library-self-spec changes** (anything under `dekspec/`) — use `/dekspec:write-intent` instead. The issue surface is for *reports*, not authoring.
- For **DIV-NNN handoffs from consumer repos** — those flow upstream as `br` beads with `--labels div-handoff,dekspec` per `CLAUDE.md` § Cross-repo discipline.

## Related

- `CLAUDE.md` § Issue tracking — `br` is the canonical in-repo tracker.
- `CLAUDE.md` § Cross-repo discipline — DIV-NNN handoff playbook.
- `/dekspec:write-intent` — for authoring a real Intent, not a report.
