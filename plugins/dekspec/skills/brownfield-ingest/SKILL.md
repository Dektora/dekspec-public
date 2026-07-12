---
name: brownfield-ingest
description: Drive the brownfield-ingest workflow — run `dekspec ingest` on an inherited markdown document, review the confidence-scored classification report, and triage which draft artifacts to promote via the `/dekspec:write-*` skills. Use when onboarding a brownfield repo whose prior-art prose (a Confluence export, an inherited PRD, a design wiki) needs classifying into DekSpec artifact slots.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Grep Glob Bash
argument-hint: [--help] [--teaching] [PATH]
---

Drive the end-to-end brownfield-ingest workflow: run `dekspec ingest` on an
inherited markdown document, walk the engineer through the confidence-scored
classification report, and hand the high-confidence draft artifacts off to the
existing `/dekspec:write-*` skills for promotion.

This skill is the prompt-time counterpart to the `dekspec ingest` CLI command.
The deterministic work — markdown sectioning, heuristic classification, draft-
artifact emission — lives entirely in that command (a deterministic heuristic
classifier, **no LLM call**). This skill orchestrates the command and the human
review around it; it does not reimplement classification.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill triages an inherited document into draft artifacts. Prior
> conversation context can bias the triage by anchoring on a mental model of
> the system that the source document itself does not support.
>
> First message → proceed. Prior history → ask "context may affect ingest
> triage quality, recommend /clear, continue? (y/n)" + wait.

## Mode Detection

Parse `$ARGUMENTS` for flags.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Default (workflow) mode** — no flag. The remaining `$ARGUMENTS` is the path
  to the markdown document to ingest. Proceed to **Workflow Mode**.

The mode catalog is deliberately minimal — three modes only. This skill has no
artifact lifecycle of its own (it promotes nothing), so it carries none of the
lifecycle modes (`--accept`, `--lock`, `--decompose`, …) the `/dekspec:write-*`
skills expose.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the
canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:brownfield-ingest"
one_line:   "Drive `dekspec ingest` on a brownfield markdown document and triage the draft artifacts"
modes:
  - { flag: "", args: "<path>", description: "Workflow mode: run `dekspec ingest` on the document, walk the classification report, triage drafts toward the /dekspec:write-* skills." }
  - { flag: "--teaching", args: "<path>", description: "Interactive tutorial — the same workflow, explained step-by-step for an engineer new to brownfield ingest." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:brownfield-ingest docs/legacy/notification-service.md"
  - "/dekspec:brownfield-ingest --teaching docs/inherited-prd.md"
  - "/dekspec:brownfield-ingest --help"
extra_sections:
  - heading: "INPUT"
    body:
      - "Markdown path   The inherited document to classify. Markdown (.md) is the"
      - "                only supported input format at this release — docx / pdf"
      - "                are deferred to a future Intent."
  - heading: "BOUNDARY"
    body:
      - "This skill writes no artifact and promotes nothing. `dekspec ingest`"
      - "writes draft artifacts into a staging directory; every promotion into"
      - "the live dekspec/ tree is an explicit engineer action via /dekspec:write-*."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

Teaching Mode walks an engineer who is new to brownfield ingest through the
same workflow as the default mode, but slowly and with explanation at each
step. It is **not** a re-run of a prior ingest and it is **not** a fast one-shot
— it is the workflow with teaching scaffolding.

Run the five **Workflow Mode** steps below, and before each step pause to
explain:

1. **Before step (a)** — explain what brownfield ingest is *for*: an inherited
   document is prose, not DekSpec artifacts; the ingest command does the first
   mechanical classification pass so adoption becomes a review pass rather than
   weeks of blank-page authoring. Explain that markdown is the only supported
   input at this release.
2. **Before step (b)** — explain that `dekspec ingest` is a deterministic
   heuristic classifier (section-header + keyword + structural-pattern
   matching, no LLM), so the same document always yields the same report —
   which is what makes the review pass auditable.
3. **Before step (c)** — explain the classification report: every source
   section is a row; the confidence score and the firing signals tell the
   reviewer *why* a section was routed the way it was. Low-confidence and
   `UNCLASSIFIED` rows are where the engineer's attention belongs.
4. **Before step (d)** — explain the hand-off: this skill does not promote
   anything. A high-confidence AE draft is brought into the spec tree by the
   engineer running `/dekspec:write-ae`; an ADR draft by `/dekspec:write-adr`;
   a WS draft by `/dekspec:write-ws`. The draft is *input* to those skills.
5. **Before step (e)** — explain the staging-directory boundary: nothing has
   landed in the live `dekspec/` tree; the drafts are unpromoted and the
   engineer copies the keepers in by hand as part of promotion.

After the walk-through, confirm the engineer can now run the default mode
unaided, and stop.

## Workflow Mode

The default mode. Drive the brownfield-ingest workflow end-to-end.

**(a) Confirm the input is a markdown document.**
The remaining `$ARGUMENTS` is the path to the source document. If it is not a
`.md` file (for example a `.docx` or `.pdf`), explain that `dekspec ingest`
supports markdown only at this release — `docx` / `pdf` input is deferred to a
future Intent — and stop. Do not attempt to convert the file.

**(b) Run `dekspec ingest`.**
Choose a fresh staging directory under the ephemeral scratch zone (`dekspec/.scratch/brownfield-ingest/`, gitignored per ADR-040 — never the repo root) and
run, via the Bash tool:

```
dekspec ingest <path> --out <staging-dir>
```

The command sections the document, classifies each section with the
deterministic heuristic classifier, writes one draft DekSpec artifact per
confidently-classified section group into the staging directory, and writes a
classification report alongside them. If the command exits non-zero, surface
its error verbatim and stop. Do not reimplement any of this — the command is
the deterministic substrate.

**(c) Present the classification report.**
Read the classification report `dekspec ingest` wrote into the staging
directory (`classification-report.md`) and present it to the engineer
section-by-section. For each source section, show: the heading text, the
classified IR type, the confidence score, and the firing signals. Draw the
engineer's attention to the low-confidence rows and any `UNCLASSIFIED` rows —
those are where review effort belongs; the high-confidence rows are the ones
the classifier is most sure about.

**(d) Triage with the engineer.**
Walk the report rows with the engineer:

- **High-confidence draft artifacts** are handed off to the matching existing
  authoring skill — `/dekspec:write-ae` for an emitted AE draft,
  `/dekspec:write-adr` for an ADR draft, `/dekspec:write-ws` for a WS draft.
  The engineer runs that skill with the draft as input to bring it through the
  normal authoring flow (`--analyze` / `--accept`). This skill names the
  hand-off; it does not run it.
- **Low-confidence rows and `UNCLASSIFIED` rows** are surfaced for the engineer
  to decide: author the artifact manually, or discard the section as not
  spec-worthy. This skill makes no decision here — it presents the row and the
  classifier's signals so the engineer can judge.

The artifact templates the downstream skills use are referenced by path
(`templates/architecture-element-template.md`,
`templates/adr-template.md`, `templates/working-spec-template.md`); this skill
does not inline template content.

**(e) Remind the engineer the drafts are unpromoted.**
Close by reminding the engineer that the emitted artifacts are unpromoted
drafts in the staging directory — nothing has landed in the live `dekspec/`
tree. Promotion is the engineer's explicit next step: review each draft against
the report, then copy the keepers into the real `dekspec/` tree as part of
running the `/dekspec:write-*` `--analyze` flow.

## Boundary — this skill writes nothing and promotes nothing

This skill produces conversational guidance only. It shells out to
`dekspec ingest` (which writes the draft artifacts into a staging directory)
and it reads the classification report. It does **not**:

- write or edit any artifact itself,
- edit anything under `dekspec/` (the live spec tree),
- set or change any artifact's status,
- run `--analyze` / `--accept` or any promotion flow.

Every promotion is an explicit engineer action through the existing
`/dekspec:write-*` skills. The classifier is deterministic — there is no LLM in
the `dekspec ingest` pipeline — and markdown is the only supported input format
at this release (docx / pdf support is a future Intent).
