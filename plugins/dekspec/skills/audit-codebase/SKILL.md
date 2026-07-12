---
name: audit-codebase
description: Audit a codebase for source-code architecture quality — deep vs shallow modules, information hiding, pull-complexity-downward, error complexity, test-surface gaps, and folderization fit — grounded in the bundled APOSD reference. Use when the engineer asks for a repo-wide audit, codebase audit, architecture audit, deep-module audit, code-quality review, or a structured assessment of code structure rather than an immediate refactor.
mode: lite
# override-reason: latest Opus tier per CLAUDE.md model policy; suite default (claude-opus-4-7) predates 4-8
model: claude-opus-4-8
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Grep Glob Bash Agent
argument-hint: [--help] [--fix]
---

Perform a structured, **read-only** audit of a codebase's source-code
architecture quality. The skill classifies modules by depth, names where
information leaks across seams, and emits evidence-backed findings in a fixed
YAML shape with a stable rule taxonomy. It starts with architecture depth and is
organized so more code-quality sections can be added over time.

## Boundary — source-code architecture, NOT spec-artifact linkage

This skill audits **source-code architecture** quality — how the *code* is
shaped (module depth, information hiding, seams, folderization). It does **not**
audit **spec-artifact linkage** — that is a different concern owned by
`dekspec audit` (the `tooling/dekspec/fidelity_audit` subsystem described by
**AE-003**), which checks that DekSpec artifacts under `dekspec/` reference each
other coherently (Intent → AE → WS → IB graph integrity, status gates, drift).

Keep the two distinct:

- **`/dekspec:audit-codebase`** (this skill) → *does the **code** have good
  architecture?* Reads `.py` files; emits `DM-*`/`SH-*`/`IH-*`/… findings.
- **`dekspec audit`** (the CLI + fidelity_audit engine) → *do the **spec
  artifacts** link up correctly?* Reads `dekspec/**.md`; emits `T-*`/`D-*`/`L-*`
  findings.

This skill emits the inherited finding YAML shape **itself**. It is standalone —
it does **not** import or call AE-003's Python `Finding`/severity classes. The
two finding vocabularies are deliberately separate.

## Read-only by default

The no-flag (default) invocation **mutates nothing**. It reads source, classifies
modules, and emits findings to chat. It never edits, refactors, or rewrites the
audited source. A durable audit document is written into the repo **only when the
engineer explicitly asks** for one (see step 6); absent that request, the audit
answers in chat. The `allowed-tools` carry no `Write` and no `Edit`, which
reinforces the read-only contract structurally: the default path is **read-only**
and stays read-only even if asked to mutate code mid-run.

The **off-default**, opt-in `--fix` flag is the **only** mutating path (see
**Fix Mode** below). It does **not** widen `allowed-tools` — it grants no blanket
`Write`/`Edit`. It restructures only by invoking the folderize helper's Bash
routine (`mv` + `py_compile`) behind a confirmation gate, and only on a flagged
module the read-only audit already emitted a finding for. The no-flag run still
**mutates nothing**.

Findings are observations, not edits. The skill **separates findings from
recommendations**: a finding is the observed current state; a recommendation is a
possible next action. It does not refactor unless the engineer explicitly asks,
and even then a fix is a downstream action, not part of this read-only audit.

## Sources

Before auditing, read the bundled reference:

- [`references/architecture_principles.md`](references/architecture_principles.md)

This skill is self-contained. It does not require external architecture skills or
external book/source files to be present. The bundled reference carries the audit
vocabulary and principle summaries needed here, condensed from
*A Philosophy of Software Design*
(`../../../../docs/a-philosophy-of-software-design-ai-reference.md`), which is the
canonical authority for the vocabulary and the deep-module rubric. Don't
re-derive the definitions or invent new architecture terms.

## Mode Detection

Parse `$ARGUMENTS` for flags.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Default (audit) mode** — no flag. Proceed to **Workflow**, performing the
  read-only audit described below.
- **Fix mode** — `--fix` flag. Proceed to **Workflow**, then apply a fix to a
  flagged finding via **Fix Mode** below.

The mode catalog is deliberately minimal. This skill has no artifact lifecycle of
its own (it promotes nothing, lands nothing), so it carries none of the lifecycle
modes (`--accept`, `--lock`, `--decompose`, …) the `/dekspec:write-*` skills
expose. The default mode is read-only. The one additive, off-default mutating
mode is `--fix`; it is opt-in (never the default), it does not widen
`allowed-tools`, and it mutates only by invoking the folderize helper behind a
confirmation gate.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the
canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:audit-codebase"
one_line:   "Audit a codebase for source-code architecture quality — deep vs shallow modules, information hiding, pull-complexity-downward, error complexity, test-surface gaps, and folderization fit — grounded in the bundled APOSD reference. Use when the engineer asks for a repo-wide audit, codebase audit, architecture audit, deep-module audit, code-quality review, or a structured assessment of code structure rather than an immediate refactor."
modes:
  - { flag: "", args: "", description: "Default mode: a read-only architecture audit. Classifies modules by depth, applies the deletion test, and emits evidence-backed findings in the inherited YAML shape. Mutates nothing." }
  - { flag: "--fix", args: "<finding|module>", description: "OFF-DEFAULT, opt-in mutating mode. Acts on an emitted finding: invokes the folderize helper to restructure a flagged deep module (should-folderize / FOLD-*). Confirms (dry-run preview) before mutating. The default no-flag run remains read-only." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:audit-codebase"
  - "/dekspec:audit-codebase --help"
extra_sections:
  - heading: "BOUNDARY"
    body:
      - "Audits SOURCE-CODE architecture quality, not spec-artifact linkage."
      - "Spec-artifact linkage is `dekspec audit` (the fidelity_audit / AE-003"
      - "subsystem). This skill is read-only and emits its own finding YAML."
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Workflow

The default mode. Read, classify, emit findings — and stop. This skill **reads**
the codebase; it never writes to it.

1. **Establish scope.**
   - Default to production code, not tests/docs.
   - Use tests as *evidence* for interface behavior, not as audit targets.
   - Identify a baseline commit only if the engineer asks for a before/after.
2. **Read domain context.**
   - `CONTEXT.md` if present.
   - The repo's ADRs/specs relevant to the audited area (under `dekspec/adrs/`
     in this repo) so the audit doesn't re-litigate settled decisions.
3. **Inventory candidate modules.**
   - Files, packages, and tier-spanning slices with a public interface.
   - Their direct callers.
   - Their direct tests.
4. **Score each audit section** against the rubric below (see **Section: Deep
   Modules**), using the vocabulary from
   [`references/architecture_principles.md`](references/architecture_principles.md).
5. **Emit findings** using the **Finding Format** and **Rule Taxonomy** below.
6. **Deliver.** Produce a durable audit document in the repo **only when the
   engineer explicitly asks** for one; otherwise answer in chat. Either way the
   audited source is left untouched.
7. **Separate findings from recommendations.**
   - finding = observed current state.
   - recommendation = possible next action.
   - Do not refactor unless the engineer explicitly asks — and a fix is a
     downstream action, never part of this read-only audit.

## Finding Format

Every concrete finding uses this shape:

```yaml
rule: <CODE>
severity: P0|P1|P2|P3
confidence: high|medium|low
module: <path or logical module>
evidence:
  - <file:line, test name, caller path, or command output>
message: <observed problem or classification>
recommendation: <next action, or "none" when informational>
```

Severity bands:

- `P0` — correctness or operability risk that can silently corrupt behavior,
  data, persistence, tensor/model identity, or runtime safety.
- `P1` — high-leverage architecture issue: repeated policy, leaked invariant,
  weak interface, missing interface test, or module shape blocking safe change.
- `P2` — maintainability issue with local blast radius or a clear cleanup path.
- `P3` — speculative, stylistic, or follow-up review item.

Confidence:

- `high` — directly supported by code/tests/callers.
- `medium` — supported by evidence but needs local design judgment.
- `low` — plausible smell; create a review follow-up rather than coding from it.

## Rule Taxonomy

Use these rule families in finding codes (full definitions and example codes in
[`references/architecture_principles.md`](references/architecture_principles.md)):

- `DM-*` — deep module classification and depth problems.
- `SH-*` — shallow module or pass-through module.
- `IH-*` — information hiding or information leakage.
- `PT-*` — pass-through layer or same-abstraction layering.
- `PCD-*` — pull complexity downward.
- `BTA-*` — better together / better apart.
- `ERR-*` — error complexity.
- `DOC-*` — comments and design intent.
- `TEST-*` — test-surface quality.
- `FOLD-*` — folderization fit.

Profiles are labels for audit scope only; do not implement profile loading yet:

- `full` — all rule families.
- `depth` — `DM`, `SH`, `TEST`, `FOLD`.
- `quality` — `IH`, `PT`, `PCD`, `BTA`, `ERR`, `DOC`, `TEST`.
- `lite` — only findings that would be `P0` or `P1`.

## Section: Deep Modules

Audit modules in the deep-module sense. A module is **deep** when a small
interface provides high leverage over substantial implementation behavior.

### Rubric

Count a module as **deep** when:

- Callers use a small interface.
- The implementation hides meaningful policy, ordering, invariants, error
  behavior, tensor/device rules, persistence grammar, transport behavior, or
  domain workflow.
- The deletion test says removing it would scatter complexity across callers.
- Tests can lock behavior through the interface.

Mark a module **shallow** when:

- The interface is nearly as complex as the implementation.
- It mostly passes through to another module.
- Callers must know internal sequencing or data-shape rules.
- Tests patch internals because the interface does not expose the behavior seam.

### Folderization Guideline

Folderization is secondary to depth in Python. Folderize a deep module **only
when**:

- one file has enough internal parts that it is hard to navigate,
- a package-level `__init__.py` can expose a smaller public interface,
- private submodules let callers think about less,
- internal parts are stable enough to name privately.

Keep a deep module as one `.py` file when:

- the abstraction is coherent and readable in one place,
- splitting would create more imports/names without more hiding,
- callers would need to know the submodule layout,
- the folder would only signal importance.

Good package shape:

```text
module_name/
  __init__.py        # public interface only, explicit __all__
  _types.py          # public dataclasses/protocols if large
  _implementation.py # default implementation
  _adapters.py       # only for real adapters
  _errors.py         # public errors when owned by the interface
```

Prefer domain-specific private names over a generic `utils.py`.

### Deep Module Audit Output

For each deep module, record:

- module path,
- public interface,
- hidden implementation complexity,
- direct callers,
- tests locking the interface,
- folderization status: `single-file-ok`, `should-folderize`,
  `already-folderized`, or `folderized-but-questionable`,
- recommendation, if any,
- finding records for any `DM-*`, `TEST-*`, or `FOLD-*` issues.

Summary counts:

- total deep modules,
- deep modules already folderized,
- deep modules that should be folderized,
- deep modules missing direct interface tests,
- shallow modules that should be deepened.

## Section: Module-Depth Bands and Over-Decomposition (ADR-039 / ADR-038)

This section AUGMENTS the qualitative deep-module rubric above with quantitative
band counts and over-decomposition candidates. It does **not** replace the
inherited finding taxonomy or the read-only finding output — it adds a numeric
companion to it. Like the rest of this skill, it is **read-only**: it runs an
analyzer and reports its output, mutating nothing.

It does **not** re-derive depth, cohesion, or facade logic. It **invokes the
bundled analyzer** [`scripts/depth_classify.py`](scripts/depth_classify.py),
which ships **inside this skill's own directory** so the skill stays
self-contained when vendored into any consumer repo. The analyzer is pure
stdlib (no `dekspec` package import) — it runs anywhere Python 3 runs. Its
thresholds and logic are frozen here; do not re-derive them. The canonical
upstream copy lives at the library repo's `scripts/depth_classify.py`; this
bundled copy is the distributed one.

Resolve the script path **relative to this skill's directory** (the directory
containing this SKILL.md), not the audited repo. The audited repo path is the
analyzer's *argument*, not where the script lives.

### Bands and concentration (ADR-039)

Run the bundled analyzer's CLI for the per-module depth bands (substitute the
skill directory for `<skill-dir>` and the audited repo root for `<repo-root>`):

```bash
python3 <skill-dir>/scripts/depth_classify.py <repo-root>
```

Report the four bands and the concentration figure exactly as the analyzer
classifies them:

- **shallow** — interface ~= implementation (low depth).
- **sound** — the healthy default: at/above the shallow ceiling, not deep.
- **deep** — top quintile by depth AND at/above the absolute floor
  (relative-with-floor).
- **overexposed** — an orthogonal flag: the interface is too wide (a module may
  be both deep AND overexposed).

Also report the **concentration** figure — the deep band's share of
implementation mass. Concentration is **reported, never a target**: do not tell
the engineer to raise or lower it. The analyzer flags it ADVISORY
(`concentration_advisory`) when the deep-band mass share is below the floor (the
"complexity smeared across modules, not pulled down" smell). Surface that
advisory as an observation, not a defect to fix.

### Over-decomposition candidates (ADR-038)

The CLI prints only the ADR-039 bands. For the ADR-038 over-decomposition
candidates, call `classify_clusters` via import. Put the bundled analyzer's
directory (this skill's `scripts/`) on `sys.path` via `PYTHONPATH=<skill-dir>/scripts`:

```bash
PYTHONPATH=<skill-dir>/scripts python3 -c "from depth_classify import classify_clusters; \
cands=classify_clusters('<repo-root>'); \
[print(c.package, c.n_public, round(c.cohesion,2), round(c.facade_ratio,2), c.public_modules) for c in cands]"
```

`classify_clusters` surfaces candidate packages by cohesion x low
external-facade ratio, with the private-submodule rollup applied so an
already-folderized deep module is never flagged. Report these candidates as
**ADVISORY ONLY**: each is a package to put to the deletion test under engineer
judgment, **never** auto-merge. The skill surfaces candidates; it does not merge
packages, and it never auto-merges.

For traceability, cite **ADR-039** (bands + concentration) and **ADR-038**
(over-decomposition) when you report this section.

## Fix Mode (--fix)

`--fix` is **off by default** — it is the one **off-default**, **opt-in** mode of
this skill, and it is the **only** mutating path. The default no-flag run stays
**read-only** and **mutates nothing**; adding `--fix` does not weaken that
contract.

**`--fix` acts on an emitted finding.** It consumes an emitted `FOLD-*` finding
(typically a deep module marked `should-folderize`) as its input — it does
**not** re-derive findings. It reads the read-only audit's output and picks the
flagged module named by the finding (or the `<finding|module>` argument). If no
finding has been emitted yet, run the **Workflow** first so a finding exists for
`--fix` to act on.

**`--fix` invokes the folderize helper.** Restructuring is performed by calling
the referenced-not-owned helper
[`_lib/folderize_deep_module.md`](../_lib/folderize_deep_module.md) on the
flagged **deep module** (the `should-folderize` candidate). That helper is
**referenced-not-owned**: call it, never edit it. The sibling
`analyze-module-depth` skill calls the same helper.

**Confirmation gate — never silent mutation.** Before touching the tree, `--fix`
previews the planned restructuring (a **dry-run** preview of the new package
layout: which file moves where, which `__init__.py` is created) and **confirms**
with the engineer. It mutates only after explicit confirmation.

**How it mutates (no blanket Write/Edit).** `--fix` does not grant `Write` or
`Edit`. The folderize helper restructures through **Bash** alone — `mv` to move
files into the new `module_name/` package and `python -m py_compile` to verify
the result imports — and the change is **behavior-preserving** per the helper's
own verify steps. The skill's `allowed-tools` stay `Read Grep Glob Bash Agent`,
so the read-only default path remains structurally read-only.

## Audit Report Shape

When the engineer asks for a durable audit document, use this structure unless
they ask otherwise:

```markdown
# Codebase Audit - <date>
## Scope
## Summary
## Finding Index
## Deep Modules
## Module-Depth Bands
## Folderization Candidates
## Over-Decomposition Candidates
## Test-Surface Gaps
## Shallow / Pass-Through Modules
## Recommended Next Passes
```

Keep claims evidence-backed with file paths and tests. If a count is a judgment,
state the rubric used. The report is the **only** artifact this skill writes, and
only on explicit request — the audited source is never modified.
