# Review Mode (interactive walkthrough)

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Interactive section-by-section walkthrough — the skill summarizes each major section, asks whether to revise, and applies the engineer's edits.

### Step 1: Validate

1. File exists; Status is `DRAFT`, `PROPOSED`, or `ACCEPTED`. Refuse on terminal statuses (LOCKED, SUPERSEDED, MERGED) and on lifecycle-mid statuses (IMPLEMENTING, TESTPASS, OVERSIZED) — review's purpose is pre-execution polish; mid-flight changes route through `--amend`.

### Step 2: Walkthrough

For each section in this order, summarize, ask, and apply:

1. **Title + Intent type + Autonomy** — confirm verb-first title; confirm type is the right choice from the 7-value enum; confirm autonomy is consistent with the Intent's risk + the Mission's ceiling (if any).
2. **Linked Architecture Elements** — for each linked AE, summarize what aspect this Intent shapes; ask whether the description is accurate; ask whether any additional AE should be linked.
3. **Motivation** — read the prose; check it stays at motivation level (no decision rationale per D20, no measurable targets per D19); ask whether to tighten / clarify / cite ADR or WS.
4. **Desired Outcome** — read the prose; check it describes observable system behavior; ask whether to sharpen.
5. **Type-specific block** — confirm the right block is populated (bug Reproduction / nfr Metric+Target / adr-driven ADR / refactor Behavior-Equivalence / documentation Coverage-Gap / environment Environment-Change / feature requires nothing); ask whether to refine.
6. **Components affected** — list every glob; ask whether each is still accurate; ask whether the size-cap-respecting set is the right one. Refuse to add a glob during review if the result would exceed the size cap (route to `--amend` instead).
7. **Verification** — list every cmd; for each, run `which <first-token>` (or check `scripts/<name>.sh` exists + is executable); flag unresolved cmds; ask whether to fix / replace / accept TBD.
8. **Open Issues** — list every open issue; for each, ask whether it has been resolved, is still blocking, or should be transferred to a new prerequisite Intent.

For each `yes, revise` response, run the Edit tool to apply the engineer's stated change in-place. For each `no, leave as is` response, move on.

### Step 2.5: Spec-Reviewer dispatch

This special-case hook attaches at the validate/exit boundary — after the Step 2 section walkthrough and before the Step 3 re-validate. It ADDS an adversarial Spec-Reviewer pass alongside the walkthrough; it does NOT replace it. Perform the shared `reviewer_mode` four-step dispatch (see [`_lib/reviewer_mode.md`](../../_lib/reviewer_mode.md)):

1. Load the `spec-reviewer` ContextSpec: `from dekspec.constraint_compiler.parser import parse_context_spec; context_spec = parse_context_spec("dekspec/context-specs/role-spec-reviewer.md")` (`context_spec["role_identity"] == "spec-reviewer"` — the same ContextSpec all six `--review` modes load).
2. Take the `ReviewerIntent` artifact this `--review` mode already holds (the Intent at `<Intent-path>`; the caller owns this IO, the dispatcher is IO-free).
3. Dispatch through the shared surface: `from dekspec.spec_review.reviewer import Reviewer; findings = Reviewer().dispatch(context_spec, artifact)` (`-> list[Finding]`, per IC-016).
4. Present each returned `Finding` to the engineer at its severity (default `P2` — approval-blocking, not auto-merge) alongside the Step 2 walkthrough sections. Do not reshape the records; they route into the AE-003 surface via the `SPEC-REVIEW` audit-rule family (`dekspec.spec_review.reviewer` → `spec_review_rules`).

### Step 3: Re-run schema validation

After walkthrough edits, re-parse via `parse_intent` to confirm the file still parses cleanly. If schema validation fails, surface the error and revert (`git checkout` the file) — the review session must end in a valid state.

### Step 4: Log and exit

1. Update Modified date.
2. Append an Amendment Log entry: `| <date> | Editorial | Review session: walked N sections, applied K revisions via /write-intent --review | <engineer-or-agent> |`
3. Save.
4. If Status is DRAFT and the walkthrough surfaced no blocking gaps, suggest running `/write-intent --analyze <path>` next. Otherwise leave the Status alone — review is editorial, never promotes status.

**End of Review Mode.**
