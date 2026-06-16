---
name: interview-me
description: Docs-anchored decision-tree interview — ask one question at a time, recommend an answer per question, explore the repo for discoverable answers, cite the domain glossary + governing ADRs/AEs and flag conflicts, sharpen fuzzy/overloaded terms, and stress-test asserted relationships with scenarios. Composed default-on by the high-judgment authoring skills.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] [artifact-id or fuzzy description of the thing being authored]
related_skills: [write-intent, write-mission, write-ae, write-adr, write-ggc]
---

Run a docs-anchored, one-question-at-a-time interview that sharpens a fuzzy or
underspecified input into a set of resolved design decisions, BEFORE those
decisions get committed to a DekSpec artifact. This is DekSpec's native,
zero-external-dependency interview capability (INT-167 / D13): it re-homes the
external "grilling" + "docs-anchored grilling" best practices into ONE owned
skill so no runtime dependency on an uninstallable harness skill remains.

`interview-me` is **composed** by the four high-judgment authoring skills
(`write-intent`, `write-mission`, `write-ae`, `write-adr`) default-on — it is
not a `--grill` flag and the interview prose is not re-authored per skill.

## Starter Prompt

```prompt
/dekspec:interview-me INT-167

The input is fuzzy — interview me one question at a time, recommend an answer
per question, explore the repo where the answer is discoverable rather than
asking me, cite the glossary + governing ADRs/AEs and flag any conflicts, and
write the resolved decisions to the scratch log so the authoring skill can fold
them in.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Interview Mode**.

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Interview mode** — no flag (default). The positional argument is the artifact id (`INT-NNN` / `MSN-NNN` / `AE-NNN` / `ADR-NNN`) or a fuzzy free-text description of the thing being authored. Run the interview contract below.

This skill exposes no lifecycle/audit/review flags of its own — it is an inline
interview helper, not an artifact-lifecycle authoring skill. (It is therefore
exempt from the `_lib/mode_dispatcher.md` universal-mode set, which applies only
to the `write-*` artifact-lifecycle skills.)

## Interview Mode

Run a depth-first decision-tree interview. The discipline:

1. **One question at a time.** Never batch. Ask the single most decision-load-bearing open question, wait for the answer, then branch.
2. **Recommend an answer per question.** Every question carries your recommended answer + a one-line rationale, so the engineer is reviewing a proposal rather than answering an open prompt.
3. **Explore the repo before asking.** When the answer is discoverable from the codebase — an existing ADR decision, an AE contract, a glossary entry, a prior Intent, the actual code — read it and state the discovered answer instead of asking. Only ask when the repo is genuinely silent or contradictory.
4. **Cite the glossary + governing decisions; flag conflicts.** Read `dekspec/domain-glossary.md` plus the governing ADRs (`dekspec/adrs/`) and AEs (`dekspec/architecture-elements/`) relevant to the artifact. Cite the specific term/ADR/AE the answer touches. If the engineer's asserted direction conflicts with a LOCKED decision or a defined term, surface the conflict explicitly and stop to resolve it before proceeding.
5. **Sharpen fuzzy/overloaded terms.** When a term in the input is vague, overloaded, or undefined, pin its meaning before it enters the artifact. If the clarification is a genuine domain-term question (a new Title-Case term, a redefinition, a recurring misinterpretation), route it to `/dekspec:write-ggc` rather than inventing a definition inline.
6. **Stress-test asserted relationships with scenarios.** When the input asserts a relationship ("X depends on Y", "this replaces Z", "A and B are the same"), construct a concrete scenario that would break the assertion and walk it. If the scenario holds, the relationship is confirmed; if it breaks, the assertion is revised before it's committed.

### Output routing (DekSpec-native)

- Resolved decisions are written to `dekspec/.scratch/interview-me/<artifact-id>.md` — the ephemeral hand-off zone landed by INT-165 (the `dekspec/.scratch/<skill>/` convention, gitignored, disposable). Use the artifact id as the filename stem (`INT-167.md`); for a not-yet-id'd fuzzy input, use a slug.
- `interview-me` is **never a durable writer**: it does not edit the artifact itself. At interview end the host authoring skill reads the scratch log and folds the resolved decisions into the artifact being authored.
- Domain-term clarifications route to `/dekspec:write-ggc` (`--add-term` / `--log`), not into any external glossary or notes file.

### Closing step

When the decision tree is exhausted (no load-bearing open questions remain),
write the final `dekspec/.scratch/interview-me/<artifact-id>.md` log — a flat
list of `Decision → resolution → source/citation` rows — and tell the host
skill the log is ready to fold in. Then stop.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:interview-me"
one_line:   "Docs-anchored one-question-at-a-time interview that sharpens fuzzy input into resolved decisions"
modes:
  - { flag: "", args: "<artifact-id | fuzzy description>", description: "Interview mode — ask one decision-tree question at a time, recommend an answer per question, explore the repo for discoverable answers, cite the glossary + governing ADRs/AEs and flag conflicts, sharpen fuzzy terms, stress-test asserted relationships, and write resolved decisions to dekspec/.scratch/interview-me/<artifact-id>.md for the host skill to fold in." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:interview-me INT-167"
  - "/dekspec:interview-me \"a new skill that records architecture decisions\""
  - "/dekspec:interview-me --help"
storage: "dekspec/.scratch/interview-me/<artifact-id>.md (ephemeral hand-off log; gitignored)"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

**End of Help Mode.**

## When to use

- Composed automatically by `/dekspec:write-intent`, `/dekspec:write-mission`, `/dekspec:write-ae`, `/dekspec:write-adr` in Creation (no-flag) and `--analyze` modes when the input is fuzzy/underspecified.
- Directly, when an engineer wants to sharpen a fuzzy direction before authoring any artifact.

## When NOT to use

- For trivial/editorial passes (`--lite`, `--editorial`) — the host skills auto-skip the interview there; an explicit `--no-interview` escape on the host skill skips it on demand.
- As a writer of the artifact — `interview-me` only produces the scratch decision log; the host authoring skill folds it in.

## Related

- `/dekspec:write-intent`, `/dekspec:write-mission`, `/dekspec:write-ae`, `/dekspec:write-adr` — the high-judgment authoring skills that compose this skill default-on.
- `/dekspec:write-ggc` — domain-term clarifications route here.
- `dekspec/domain-glossary.md` — the term corpus this interview cites.
- AE-006 (Skills Library) — the AE this skill registers under.
