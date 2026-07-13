---
name: archeology
description: Brownfield spec-gap recovery — start from an orphaned code surface and work back to a ratifiable Intent. Scan a file's public API, find which files no LOCKED Intent claims, draft a retroactive Intent skeleton, cross-reference a symbol to its likely contract surface, and route ratification through /dekspec:write-intent. Use when adopting DekSpec on a brownfield repo, backfilling vibecoded work, or recovering from code-vs-spec drift.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Grep Glob Bash
argument-hint: [--help] [--teaching] [--scan PATH] [--propose-intent PATH] [--coverage-gap-report] [--ratify DRAFT_PATH --as INT_ID] [--cross-ref SYMBOL]
related_skills: [brownfield-ingest, write-intent, write-ic, write-adr]
---

Walk an engineer from an orphaned code surface back to a ratifiable Intent.

This is the first **recovery-flow** skill in the DekSpec catalog. Every other
skill (`/dekspec:write-ae`, `/dekspec:write-intent`, …) is an *authoring* skill
that assumes a greenfield drafting context — the engineer already knows the
artifact type and the contract surface. Archeology assumes the opposite: the
engineer is staring at code that has *no* spec, does not know which artifact
type should claim it, and needs the skill to start from the code and reason
back toward the spec.

The deterministic work — the AST walk, the symbol enumeration, the
gap-detection against LOCKED Intents' §Components-affected globs — lives in the
`tooling/dekspec/archeology/` substrate and the `dekspec find-spec-gaps`
CLI verb. This skill orchestrates that substrate plus the human judgment around
it. It does not reimplement scanning or gap detection.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill reasons backward from code to spec. Prior conversation context can
> bias the reconstruction by anchoring on a mental model of the system the code
> itself does not support.
>
> First message → proceed. Prior history → ask "context may affect archeology
> reconstruction quality, recommend /clear, continue? (y/n)" + wait.

## Starter Prompt

```prompt
/dekspec:archeology --propose-intent tooling/dekspec/lifecycle.py

This file pre-dates our DekSpec adoption and no LOCKED Intent claims it. Scan
its public API and callers, then draft a retroactive Intent skeleton I can
review and route through /dekspec:write-intent.
```

## Mode Detection

Parse `$ARGUMENTS` for flags. The mode catalog is eight modes — a default
conversational entry mode plus seven explicit handlers.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Scan mode** — `--scan` flag. The remaining `$ARGUMENTS` is a path to a
  Python file or directory. Skip to **Scan Mode**.
- **Propose-intent mode** — `--propose-intent` flag. The remaining
  `$ARGUMENTS` is a path. Skip to **Propose-Intent Mode**.
- **Coverage-gap-report mode** — `--coverage-gap-report` flag. Skip to
  **Coverage-Gap-Report Mode**.
- **Ratify mode** — `--ratify` flag, with `--as <INT-NNN>`. The remaining
  `$ARGUMENTS` is a path to a draft Intent. Skip to **Ratify Mode**.
- **Cross-ref mode** — `--cross-ref` flag. The remaining `$ARGUMENTS` is a
  symbol name. Skip to **Cross-Ref Mode**.
- **Default (conversational) mode** — no flag. Proceed to **Default Mode**.

## Default Mode

The conversational entry point for an engineer who knows they have a
brownfield spec gap but does not yet know which mode they need. Do not run any
deterministic tool yet — first orient the engineer:

1. Ask what they are looking at — a whole repo they are adopting DekSpec on, a
   single file they suspect is orphaned, a symbol they cannot place, or a draft
   Intent they want to promote.
2. Route them to the right mode:
   - Adopting DekSpec on a repo / want the full gap list → **`--coverage-gap-report`**.
   - One file, "what does this even do?" → **`--scan <path>`**.
   - One file, "this needs an Intent" → **`--propose-intent <path>`**.
   - A symbol, "where does this belong?" → **`--cross-ref <symbol>`**.
   - A draft Intent ready to become real → **`--ratify <draft> --as INT-NNN`**.
3. If they are mid-recovery and unsure, walk the canonical flow with them:
   `--coverage-gap-report` to find the gaps → `--scan` / `--propose-intent`
   per gap → `--ratify` once a draft is reviewed.

This skill writes no artifact and promotes nothing — say so plainly if the
engineer expects it to.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the
canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:archeology"
one_line:   "Brownfield spec-gap recovery — from an orphaned code surface back to a ratifiable Intent"
modes:
  - { flag: "", args: "", description: "Conversational mode: orient the engineer and route them to the right recovery mode." }
  - { flag: "--scan", args: "<path>", description: "Summarize a file or directory's public API, internal state, and external callers (shells out to the scan substrate)." }
  - { flag: "--propose-intent", args: "<path>", description: "Draft a retroactive Intent skeleton — §Motivation + §Desired-Outcome + §Components-affected only — returned to the engineer for ratification, written to no file." }
  - { flag: "--coverage-gap-report", args: "", description: "Run `dekspec find-spec-gaps` and render the gap report — files no LOCKED Intent claims — inline in the transcript." }
  - { flag: "--ratify", args: "<draft> --as INT-NNN", description: "Promote a reviewed draft Intent by routing through the engineer's /dekspec:write-intent --accept flow." }
  - { flag: "--cross-ref", args: "<symbol>", description: "Find usages of a symbol across the repo and suggest which Interface Contract surface it likely belongs to." }
  - { flag: "--teaching", args: "", description: "Interactive tutorial — the brownfield-recovery workflow explained step-by-step." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:archeology --coverage-gap-report"
  - "/dekspec:archeology --scan tooling/dekspec/lifecycle.py"
  - "/dekspec:archeology --propose-intent tooling/dekspec/lifecycle.py"
  - "/dekspec:archeology --cross-ref open_run"
  - "/dekspec:archeology --ratify ./drafts/INT-draft-recovery.md --as INT-061"
  - "/dekspec:archeology --teaching"
extra_sections:
  - heading: "BOUNDARY"
    body:
      - "This skill writes no artifact and promotes nothing. --propose-intent"
      - "returns an engineer-reviewable Markdown skeleton; --ratify routes"
      - "through /dekspec:write-intent --accept. Every file write is an"
      - "explicit engineer action through the standard authoring skills."
  - heading: "EXCLUDE FILE"
    body:
      - "The coverage gap detector honors a per-repo exclude file at"
      - ".dekspec/archeology-exclude — newline-delimited glob patterns,"
      - "# comments ignored — that extends a built-in default exclude set"
      - "(__pycache__, .venv, node_modules, build, dist, _vendored, …)."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

Teaching Mode walks an engineer new to brownfield recovery through the same
workflow as the default mode, but slowly and with explanation at each step. It
is **not** a re-run of a prior recovery and it is **not** a fast one-shot.

Run the canonical recovery flow below, and before each step pause to explain:

1. **Before the gap report** — explain what a spec gap *is*: in any
   non-greenfield repo, code surfaces exist that no Intent / WS / IB claims —
   work that pre-dated DekSpec, was vibecoded under-spec, or drifted past its
   spec. Explain that `dekspec find-spec-gaps` is deterministic — it
   collects every LOCKED Intent's §Components-affected globs and reports the
   files no glob matches — so the same repo always yields the same gap list.
2. **Before scanning** — explain that `--scan` is an AST walk, not an LLM
   guess: it enumerates the file's public API, module-level state, and the
   other modules that import it, so the engineer reasons from facts about the
   code rather than from memory.
3. **Before proposing** — explain that `--propose-intent` populates only the
   factual sections of an Intent (§Motivation, §Desired-Outcome,
   §Components-affected) and deliberately leaves the judgment-laden sizing
   sections empty with a TODO marker — the LLM does not know the full spec
   graph and a guessed §Size assessment is noise the engineer must clean up.
4. **Before ratifying** — explain that `--ratify` does not write the Intent
   itself: it hands the reviewed draft to `/dekspec:write-intent --accept`, the
   standard authoring flow, so the retroactive Intent goes through the same
   review and audit gates as a greenfield one.

After the walk-through, confirm the engineer can run the modes unaided, and
stop.

## Scan Mode

Summarize a code surface so the engineer can reason about it.

1. The remaining `$ARGUMENTS` is a path to a Python file or directory. If it is
   not a `.py` file or a directory, say so and stop.
2. Shell out to the `scan` substrate via the Bash tool — for example:

   ```
   PYTHONPATH=tooling python -c "import json, sys; from dekspec.archeology import scan; print(json.dumps([s.to_dict() for s in scan.scan(sys.argv[1])], indent=2))" <path>
   ```

   (or, if the package is installed, drop the `PYTHONPATH=tooling` prefix.)
3. Present the result conversationally: the file's **public API** (module-level
   functions, classes, public methods), its **internal state** (module-level
   assignments), and its **external callers** (other modules that import it).
   Do not reimplement the AST walk — the substrate is the deterministic source.
4. Close by naming the obvious next step: if the file looks spec-orphaned, run
   `--propose-intent <path>`; if a single symbol is the question, run
   `--cross-ref <symbol>`.

### Optional deeper investigation (manual, post-scan)

The scan substrate is deliberately shallow — it gives the engineer the *factual
surface* (public API, internal state, callers) without inferring intent. When
the engineer wants to reason about what *cannot change* before drafting an
Intent, the following 5-phase mental model — applied manually by the engineer
on top of the scan output, not driven by this skill — is the canonical depth:

1. **Call graph** — who calls the target, with what arguments, using the return
   how. (Scan substrate's `external_callers` is the starting set.)
2. **Data flow** — for each significant function, what type enters, what type
   exits, what is mutated, where data is sourced and where it is persisted.
3. **Constraint extraction** — classify each constraint found:
   - *Hard dependency* — external service / DB schema / wire format. Changing
     requires coordinated change elsewhere.
   - *Implicit contract* — what callers assume about behavior (return shape,
     error type, side effects) that is not documented.
   - *Performance constraint* — hot-path assumption, pre-allocation pattern,
     loop-avoidance idiom.
   - *Tenant / isolation constraint* — boundary enforcement that is currently
     load-bearing in production.
   - *Precision / serialization constraint* — round-trip assumption,
     quantization level, dtype expectation.
4. **Implicit decision recovery** — for each non-obvious pattern, state the
   decision factually and the likely rationale. Anything load-bearing belongs
   in an ADR (route through `/dekspec:write-adr`).
5. **Gap analysis** — error-handling gaps, untested branches, undocumented
   assumptions, hardcoded thresholds. These become Open Issues on the
   retroactive Intent.

This mental model is not a skill mode and does not write any artifact. If the
investigation produces material the engineer wants to keep, capture it in the
retroactive Intent's §Motivation and §Open Issues sections, drafted via
`--propose-intent` and ratified via `--ratify`. Do not produce parallel
"archaeology documents" outside the DekSpec artifact tree.

## Propose-Intent Mode

Draft a retroactive Intent skeleton for an orphaned file — returned to the
engineer, written to no file.

1. Scan the path (as in **Scan Mode**) to gather the factual surface.
2. Draft an Intent skeleton in Markdown and present it inline in the
   transcript. Populate **only these three sections** from the scan:
   - **§Motivation** — what the file does and why it lacks a spec (brownfield /
     vibecoded / drifted), grounded in the scanned public API + callers.
   - **§Desired Outcome** — the user-observable state once the retroactive
     Intent is LOCKED (the file is claimed; its behavior is contractually
     pinned).
   - **§Components affected** — the glob(s) covering the scanned path.
3. Leave **§Size assessment**, **§Coverage report**, and **§Layer impact
   analysis** empty, each carrying an explicit TODO marker:

   ```
   <!-- TODO: run /dekspec:write-intent --analyze to populate this section.
        Sizing is judgment-laden and is deliberately not auto-proposed. -->
   ```

4. Return the skeleton to the engineer for review. Do **not** write it to disk.
   Tell the engineer the next step is `/dekspec:write-intent --analyze` on the
   reviewed skeleton, then `--ratify` once they are satisfied.

## Coverage-Gap-Report Mode

Surface every file no LOCKED Intent claims.

1. Shell out to the CLI verb via the Bash tool:

   ```
   dekspec find-spec-gaps --at .
   ```

2. The verb walks the repo, collects every LOCKED Intent's §Components-affected
   globs, honors the `.dekspec/archeology-exclude` per-repo exclude file plus
   the built-in default exclude set, and prints a Markdown table of the
   spec-orphaned files. If the verb exits non-zero, surface its error verbatim
   and stop.
3. Render the table inline in the transcript and help the engineer triage:
   high-value source files are candidates for `--propose-intent`; vendored /
   generated noise the engineer wants permanently ignored belongs in
   `.dekspec/archeology-exclude`.
4. Do not reimplement gap detection — the CLI verb is the deterministic
   substrate.

## Ratify Mode

Promote a reviewed draft Intent into a real Intent.

1. The remaining `$ARGUMENTS` is a path to a draft Intent; `--as <INT-NNN>` is
   the target Intent id. If either is missing, ask for it and stop.
2. Confirm with the engineer that the draft has been reviewed (and ideally run
   through `/dekspec:write-intent --analyze` to fill the sizing sections).
3. Route the promotion through the engineer's standard flow — hand the draft to
   `/dekspec:write-intent --accept`. This skill does **not** write the Intent
   file, does **not** auto-commit, and does **not** set the artifact's status
   itself. The retroactive Intent goes through the same review and audit gates
   as a greenfield Intent.

## Cross-Ref Mode

Place a symbol — find where it is used and which contract surface owns it.

1. The remaining `$ARGUMENTS` is a symbol name.
2. Use the `scan` substrate plus the Grep tool to find the symbol's definition
   and its usages across the repo. The substrate's `external_callers` data
   identifies the modules that import the symbol's home module.
3. Suggest which Interface Contract surface the symbol likely belongs to — a
   symbol crossing a package boundary with multiple external callers is a
   candidate for an IC; a symbol used only within one package is internal.
4. This is a suggestion for the engineer's judgment, not a decision — name the
   evidence (caller count, package spread) and let the engineer decide whether
   an IC is warranted.

## Boundary — this skill writes nothing and promotes nothing

This skill produces conversational guidance only. It shells out to the
`tooling/dekspec/archeology/` substrate and the `dekspec find-spec-gaps`
CLI verb (both read-only against the repo), and it reads scan / gap-report
output. It does **not**:

- write or edit any artifact itself,
- edit anything under `dekspec/` (the live spec tree),
- set or change any artifact's status,
- auto-commit or auto-promote.

Every `--propose-intent` draft is returned to the engineer as Markdown for
review. Every `--ratify` promotion routes through `/dekspec:write-intent
--accept`. The scan + gap-detection substrate is deterministic — there is no
LLM in `dekspec find-spec-gaps`.

## Common Pitfalls

- Don't reimplement the AST walk or gap detection in the LLM — always shell out
  to the `tooling/dekspec/archeology/` substrate and `dekspec archeology
  coverage`; they are the deterministic source and a hand-rolled scan drifts.
- Don't populate §Size assessment, §Coverage report, or §Layer impact analysis
  in a `--propose-intent` skeleton — leave them as TODO markers; guessed sizing
  is noise the engineer must clean up before `/dekspec:write-intent --analyze`.
- Don't write the proposed skeleton or the ratified Intent to disk from this
  skill — return drafts inline and route every file write through
  `/dekspec:write-intent`; archeology promotes and commits nothing.
- Don't treat a `--cross-ref` result as a verdict — name the caller count and
  package spread as evidence and let the engineer decide whether an IC is
  warranted; this skill suggests, it does not decide.
- Don't reconstruct from memory or prior conversation — honor the CONTEXT CHECK
  and recommend `/clear` on a stale thread, then reason only from scanned facts.
- Don't dump vendored / generated files into `--propose-intent` — triage them
  into `.dekspec/archeology-exclude` so the gap report stays high-signal.

## Verification Checklist

- [ ] Every scan / coverage result came from shelling out to the substrate or
      CLI verb, not from an LLM-reconstructed file summary.
- [ ] A `--propose-intent` skeleton populated only §Motivation, §Desired
      Outcome, and §Components affected, each grounded in scanned facts.
- [ ] The three sizing/coverage/layer sections carry explicit TODO markers, not
      guessed content.
- [ ] No artifact was written, edited, status-changed, or committed by this
      skill; drafts were returned inline for engineer review.
- [ ] Any `--ratify` promotion was routed through `/dekspec:write-intent
      --accept` rather than writing the Intent file directly.
- [ ] A `--cross-ref` suggestion stated its evidence (caller count, package
      spread) and left the IC decision to the engineer.
- [ ] The CONTEXT CHECK was honored — proceeded on a first message, or prompted
      for `/clear` on a thread with prior history.
