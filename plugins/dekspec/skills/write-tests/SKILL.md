---
name: write-tests
description: Write an IB's acceptance tests — the pytest nodes its `## Acceptance` block names — behavior-first, each new assertion with a declared expectation basis, genuinely red (checked with `dekspec ib floor`) before authorization, then hand them to the independent oracle review (/review-ib) that must pass before `dekspec ib accept` baselines them. Use after the IB's Acceptance block is written and before /review-ib and `dekspec ib accept`.
mode: lite
reasoning_effort: high
allowed-tools: Read Write Edit Bash
argument-hint: [--help | --teaching | --audit | --revise] [IB-NNN] [notes]
related_skills: [write-ibs, write-evals, orchestrate-coding-session, review-pr]
disable-model-invocation: false
---

Write the acceptance tests an IB's acceptance conditions name, before anyone implements the IB.

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill derives assertions from the IB's acceptance conditions and binding obligations. Prior conversation context can smuggle in assumptions the contract does not make.
>
> Inline reasoning only (see mode manifest); substantive fan-out skips this check. First message → proceed. Prior history → ask "context may affect test derivation quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## What this skill owns

An IB's `## Acceptance` block (ADR-057) lists conditions. Each condition is verified by exactly one of: pytest nodes, a command, or an independent review. This skill writes the **pytest nodes**:

- **Acceptance tests are protected assets.** Every test file a condition names is hashed into the acceptance baseline, `Basis:` lines included. The implementing agent never edits them and never creates a missing one. A wrong one is an escalation, and after execution starts only `dekspec ib amend --reviewer … --reason …` changes it.
- **Mandatory, and written before authorization (ADR-062).** Every `pytest:` condition's nodes exist, are genuinely red and have passed the independent oracle review before `dekspec ib accept` takes the baseline. `/implement` readiness refuses an IB whose named nodes or declared assets are missing from its baseline, or whose baseline digest no passing floor review (a `Floor reviewed: PASS` row) names — a row recording a failed review does not count. The builder never writes them.
- **Every new assertion declares its expectation basis** — where its expected result comes from (see **Expectation Basis**). The oracle reviewer judges that basis; an expectation taken from the code under test is rejected.
- **Red first — on the missing behavior, never on a missing surface.** A test for an entry point that does not exist yet ships with a behavior-free **surface skeleton**, so its assertion fires; `dekspec ib floor` shows each new node genuine red (see **Red-Genuineness Check**).
- **No skip markers.** A skipped, xfail, deselected or uncollected node never satisfies its condition, and the builder may not remove a marker from a protected file. Ship the tests live and red, on the delivery branch, never the base branch.
- **The repository's own layout.** Put each node where the IB names it and where the project keeps tests of that kind. There is no bead layout and no one-file-per-unit rule.
- **Development tests are not acceptance assets.** Tests the implementer adds during execution stay editable. Only what the Acceptance block names, plus declared fixtures, is protected.

`command:` conditions whose threshold is probabilistic (model output) belong to `/dekspec:write-evals`. A deterministic `command:` condition has no test file: its basis is written in its `condition` text in the IB (what the command checks and why its result shows the behavior; see **Expectation Basis**). `review:` conditions are judged by a reviewer and have no test.

**The order (ADR-062).** Write the IB (`dekspec ib lint`, `dekspec ib propose`) → `/dekspec:write-tests` (basis, surface skeleton, genuine red with `dekspec ib floor`) → `/dekspec:review-ib`, whose `acceptance-oracle` lens judges the tests and the floor report and records a passing floor review as a `Floor reviewed:` Amendment Log row naming the floor digest → `dekspec ib accept`, run by the authorizer only after checking that the floor digest matches that row (the command itself does not check it; `/implement` readiness does). A pre-start change to the tests repeats the oracle review (a new row) before `dekspec ib baseline`.

## Starter Prompt

```prompt
/dekspec:write-tests IB-214

Write the acceptance tests IB-214's Acceptance block names — a basis per
assertion, genuinely red on `dekspec ib floor` — then hand them to the
oracle review before they are baselined.
```

**Roles (ADR-061).** This skill plays DekSpec's Agent Role Specifications; the engineer never selects one. Authoring, revise and resync modes play the **`specifier`** role, audit modes the **`auditor`** role: run `dekspec resource role specifier` or `dekspec resource role auditor` at the start of the mode and follow it (a delegated `*-author` agent loads `specifier` itself). See [`_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) §The role each universal mode plays and [`_lib/agent_roles.md`](../_lib/agent_roles.md).

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md). Default mode: **Acceptance Test Mode** (fans out to a fresh-context subagent per `ds-di2`).

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **Revise mode (fan-out)** — `--revise` flag. Proceed to **Fan-Out Mode**, then **Revise Mode**.
- **Acceptance test mode (fan-out, default)** — no flag. Proceed to **Fan-Out Mode**, then **Acceptance Test Mode**.

**Routing:** substantive work (fan-out via Agent tool): (no flag), `--revise`. Inline: `--help`, `--teaching`, `--audit`.

## Fan-Out Mode

Bundle source paths rather than parent summaries; preserve engineer guidance verbatim. Keep parsed mode/path fields and labeled orchestrator notes separate. Show the manifest and preserve fan-out/ingest provenance per the shared substrate; existing task authorization suffices for dispatch.

See [`_lib/fan_out.md`](../_lib/fan_out.md). Manifest:

- **subagent_type**: `general-purpose`.
- **substantive_modes**: [Acceptance Test Mode (default), `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--audit`]
- **bundle_list** (gathered BEFORE dispatch):
  1. The contract — `dekspec ib context IB-NNN --json`: acceptance conditions with their nodes, binding obligations with canonical text (ICs and WS sections carry the failure behavior and public shapes to test against), Scope, Protected Surfaces, implementation hypothesis. If it reports `problems`, stop: the contract is not ready.
  2. Engineer guidance — `$ARGUMENTS` verbatim (for `--revise`, the revision notes).
  3. Project context — `dekspec/project-context.md` (the SDET role), if present.
  4. Constraints — the **Rules**, **Expectation Basis**, **Scoping Role-Pass** and **Red-Genuineness Check** sections of this skill.
- **expected_output_path**: the test files named by the IB's `pytest:` nodes, plus the surface skeleton for any entry point they call that does not exist yet.
- **validation**: `pytest --collect-only <every named node>` must collect each node id exactly as the IB spells it. Then run the Red-Genuineness Check (`dekspec ib floor IB-NNN` must report the floor OK). Surface a failure verbatim per [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md); do not silently retry.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md). Manifest:

```yaml
skill_name: "/write-tests"
one_line:   "Write an IB's acceptance tests — a basis per assertion, genuinely red — before authorization"
modes:
  - { flag: "", args: "<IB-NNN>", description: "Write every pytest node the IB's Acceptance block names, each new assertion with a basis, confirm the floor is genuinely red with `dekspec ib floor`, then hand off to the oracle review." }
  - { flag: "--audit", args: "<IB-NNN>", description: "Read-only: every named node exists and collects, covers its condition, declares a basis, carries no skip marker, the floor report is OK, and a floor review names the baseline digest." }
  - { flag: "--revise", args: "<IB-NNN> <notes>", description: "Revise acceptance tests before execution starts; the oracle review is repeated before the re-baseline. After start, use the amendment path. Notes: inline text or a file path." }
  - { flag: "--teaching", args: "<IB-NNN>", description: "Interactive tutorial: derive behavior-first acceptance tests from an IB's conditions, one condition at a time. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-tests IB-214"
  - "/write-tests --audit IB-214"
  - "/write-tests --revise IB-214 \"AC-2 must also cover an empty input list\""
  - "/write-tests --help"
extra_sections:
  - heading: "WORKFLOW"
    body:
      - "1. IB with an Acceptance block:   /write-ibs"
      - "2. Acceptance tests (mandatory):  /write-tests <IB>   basis + skeleton; genuine red on: dekspec ib floor <IB>   (evals: /write-evals <IB>)"
      - "3. Oracle review:                 /review-ib <IB>   records `Floor reviewed: PASS — digest …` in the IB's Amendment Log"
      - "4. Protect them:                  dekspec ib accept IB-NNN  |  dekspec ib baseline IB-NNN --reason \"…\"  (before ib start; the authorizer first checks the floor digest matches the reviewed row)"
      - "5. Execute:                       /implement <IB>  or  /orchestrate-coding-session <IB>"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md). Parameters:

- **artifact_kind**: the acceptance tests for one IB
- **template_path**: not template-driven; tests derive from the IB's `## Acceptance` block
- **methodology_section**: §Test Strategy of `docs/dekspec-operating-guide.md`
- **exemplar_paths**: existing tests in this repository that exercise a public entry point
- **required_sections**: one or more tests per `pytest:` condition

Step 3 walks each condition: what observable behavior it names, which public surface demonstrates it, which inputs, outputs and failures to use, and where each expected result comes from (its basis). On exit the tests and any surface skeleton are on disk and `dekspec ib floor` shows them genuinely red; the independent oracle review (`/dekspec:review-ib`) is the next step, then authorization.

## Acceptance Test Mode (default)

> The subagent's contract (see **Fan-Out Mode**). The orchestrator checks collection and red-genuineness (`dekspec ib floor`) on return, then runs the **Closing Step**.

Input: `IB-NNN`. If none, list IBs whose named acceptance nodes do not exist yet, then ask.

**Safety check.** `dekspec ib status IB-NNN`. If the run has started, stop: the tests are protected, and a change is an amendment (`dekspec ib amend --reviewer … --reason …`) by someone other than the builder. If a named test file already exists, warn before touching it. A node whose test already existed unchanged before the IB was first committed is a preservation node: leave it as it is — it must pass, and it needs no added basis.

1. Read the bundle. Every `pytest:` condition names the node ids you must create. Its `condition` text is the behavior. Referenced obligations (IC shapes, WS failure rules, ADR constraints) define the public surface and the failure behavior.
2. For each condition, write the node(s) with exactly the file path and test name the IB gives. If a name cannot work (wrong file for this repository's layout, a condition not testable as a pytest node), stop and surface it. The Acceptance block is the contract, and changing it is an IB edit (`/dekspec:write-ibs`), not a test-author decision.
3. Cover what the conditions name, including integration through the real entry point and failure behavior where a condition names it. Invent nothing the conditions don't call for.
4. Record the **Expectation Basis** of every new assertion, and apply the **Scoping Role-Pass** to every assertion.
5. For every entry point the tests call that does not exist yet, write the **surface skeleton** (see **Rules**) inside the IB's Scope.
6. Declare any fixture or golden data the tests read under the IB's "Protected acceptance assets" list (an IB edit, through `/dekspec:write-ibs`); named test files are protected automatically.
7. Run the collect gate, then the **Red-Genuineness Check** (`dekspec ib floor IB-NNN`).

## Revise Mode

> Fan-out delegated; same contract as above.

Before execution starts: read the IB, the existing tests and the notes; present the plan (new, changed, removed assertions, each mapped to its condition, each new or changed one with its basis); apply on approval; re-run the Red-Genuineness Check; then the **Closing Step** — the changed tests go back through the oracle review, which records a new `Floor reviewed:` row, before the re-baseline. After execution starts this mode refuses: route to `dekspec ib amend`, whose change — basis included — the completing independent reviewer must oracle-judge before acknowledging it (ADR-057, ADR-062).

## Audit Mode

_Plays the **`auditor`** role — run `dekspec resource role auditor` first and follow it: deterministic `dekspec validate` / `dekspec audit` output is primary evidence; report findings, change nothing._

Read-only. For `IB-NNN`:

- every `pytest:` node the IB names collects under its exact id (`pytest --collect-only`);
- each covers its condition's behavior through a public surface (match on assertions, not names);
- every new node declares a basis (`dekspec ib floor IB-NNN` lists it; `basis: none declared` is a finding, an inherited-only basis is flagged for the reviewer); the audit reports a missing basis and never judges a basis's adequacy — that is the oracle reviewer's;
- before execution: the floor report is OK (new nodes genuine red, preserved nodes passing), and a `Floor reviewed: PASS` row in the IB's Amendment Log names the digest the baseline records (a `Floor reviewed: FAIL …` row does not count);
- no named node carries a skip or xfail marker;
- `dekspec ib status IB-NNN` shows the acceptance assets unchanged since the baseline, or each change amended.

```
TEST AUDIT — IB-214
  ✅ AC-1  tests/test_export.py::test_export_writes_csv — collects, covers condition, basis declared
  ❌ AC-2  tests/test_export.py::test_export_rejects_empty — not found
  ⚠️ AC-3  tests/test_cli.py::test_export_command — skip marker (can never satisfy AC-3)
  ⚠️ AC-4  tests/test_cli.py::test_export_help — import-error on the floor (not genuine red); no basis declared
```

## Rules

### What the tests are (ADR-036 / Constitution Article 3)

Independent, behavior-first acceptance tests, written up front and all at once. Writing a suite horizontally like this makes it easy to test imagined structure instead of behavior, so hold every test to these rules:

1. A test describes **behavior**, not implementation.
2. A test exercises the **public interface only**, preferring an Interface Contract surface or the real entry point over internal signatures.
3. A test **survives an internal refactor that changes no behavior**.
4. Each test is **minimal and focused**: one behavior, one logical assertion.
5. **Cover every named condition, and invent no behavior the contract does not call for.**

- Mock at **system boundaries only** (external services, persistence, time, randomness, file system). Never mock internal collaborators or the unit under test.
- **Surface skeleton, not a lazy import (ADR-062).** When a test calls an entry point that does not exist yet — a new command, option, module or function — write, in the IB's Scope and with the tests, the minimal contracted entry point with **no behavior**: it accepts the contracted arguments and returns a neutral result (`None`, an empty value, exit 0 with no output), so the test's assertion fires on the missing behavior. A skeleton that raises (`NotImplementedError` or any other) does not qualify, and neither does a test that relies on an import error, a missing symbol or an argument-parser usage exit to be red. The skeleton is committed with the tests, is shown to the oracle reviewer, and is replaced by the implementation within the IB's Scope.
- Derive import paths and signatures from the obligations and the IB's hypothesis. Never invent a module path the contract does not imply; surface the gap.
- Deterministic only. A probabilistic threshold is an eval (`/dekspec:write-evals`).

### Expectation Basis

Every new or changed assertion declares the basis of its expected result (ADR-062), so an independent reviewer can judge it before the tests are baselined:

1. **Write a `Basis:` line** beside the assertion (a comment inside the test) or once in the test's docstring when one basis covers all its assertions. For a parametrized test, a basis beside the case table or on the test covers the per-case expected values. A basis on a class or the module is allowed but is reported as *inherited* — the reviewer sees that the test itself gave none. `dekspec ib floor` reads exactly these forms, and reports the text after `Basis:` verbatim:
   - a comment that starts with the label: `# Basis: IC-012 §Errors — an empty list returns exit 3`;
   - a comment that carries the assertion stamp (see **Scoping Role-Pass**) and then the label: `# REQUIRED. Basis: …`, or `# REQUIRED: <stamp text> Basis: …` (likewise `GIVEN` and `INCIDENTAL`, the stamp followed by `.`, `:` or a space). Only the text after `Basis:` is the basis; a stamp without `Basis:` declares none;
   - a docstring line that starts with `Basis:` (the test's own, or a class or module docstring, which is inherited).
2. **Acceptable bases:** a worked example taken from an approved obligation (cite it, e.g. `Basis: IC-012 §Errors — an empty list returns exit 3`); an independently established fixture (say how it was established); an external reference (a standard, a published table, an independent library); an invariant or metamorphic property justified from the contract. A literal is not self-justifying: record its source and rationale. A property test stands when its property follows from the contract, not from the implementation.
3. **Not independent — rewrite it:** an expected value obtained by calling the system under test or its helpers and constants; one that repeats the implementation's derivation; one recorded from observed output with no independent check. Shared fixture plumbing and test utilities are fine unless a mistake they share with the implementation would let incorrect behavior pass.
4. **A `command:` condition's basis is its condition text.** It has no test file, so its `condition` in the IB states what the command checks and why that result shows the behavior. A pass criterion the change controls — a string the change itself prints, a count it computes — is not independent; route that fix through `/dekspec:write-ibs`.
5. **Preservation nodes** — tests that existed unchanged before the IB was first committed — are left as they are and need no added basis. A new test that pins existing behavior is new: it needs a basis. A new test that cannot be red belongs among the IB's declared protected assets, not its acceptance conditions.

### Scoping Role-Pass

Keep each assertion only as tight as the condition requires. This reinforces, and does not replace, the `fence-durable` and `fence-golden-path` norms:

1. **Fallback test per assertion.** Pair each strict assertion with a looser fallback test that pins the user-observable behavior the condition promises, independent of mechanism. It is the one that survives a legitimate refactor.
2. **Over-spec mirror check.** Would a correct implementation that made a legitimate, different in-spec choice still pass? If not, the assertion is over-specified. Delete it, or demote it to the behavior it guarded.
3. **REQUIRED / GIVEN / INCIDENTAL classifier.** Stamp every retained assertion: **REQUIRED** (contract behavior; pin it tightly), **GIVEN** (a precondition; keep it in setup), **INCIDENTAL** (an implementation detail; it must not survive the mirror check). Record the stamp as an inline comment, e.g. `# REQUIRED: returns the canonical id`.

## Red-Genuineness Check

`pytest --collect-only` proves only that a file parses. Genuine red is read from recorded evidence, not asserted: commit the IB first (the floor tells a new node from a preserved one by the IB's first commit; an uncommitted IB makes every node new), then run

```bash
# add --json for the machine-readable report
dekspec ib floor IB-NNN
```

It runs the acceptance runner and prints, per `pytest:` condition, each node with its class (`new` / `preserved`), its failure kind, its failure line and its declared basis (inherited ones marked), plus the **floor digest** the baseline would record. It never writes anything.

- **Every new node must be `genuine-red` with a declared basis:** its assertion fired on the intended behavior. `import-error`, `missing-symbol`, `usage-exit`, `collection-error`, `setup-error`, `skipped`, `xfail`, `deselected`, `not-collected` and `passed` are not genuine red. Fix the cause — a surface skeleton, a correct node id, an assertion pinned to the contracted message or exit code — never by loosening the assertion.
- **Every preserved node must pass.**
- **A subprocess usage exit is not genuine red.** An assertion that fired only because a command the test runs rejected its arguments (argparse exit 2, `unrecognized arguments`, `invalid choice`) or could not import its code is a usage or import failure, even though the test's own assertion fired. The report flags the signatures it recognizes in the failure message and captured output, read in full however long the failure's repr is (pytest's own quiet output may cut it); it cannot see intent, so read every failure line yourself.
- **The floor is OK** when the report's first line says so. Record the digest and one line per node (`<node> → genuine-red, basis: …`, or the correction you made) for the hand-off.

## Closing Step

The tests are handed to an independent oracle review before anyone protects them; you never review or record it yourself (ADR-062, ADR-061):

1. **Commit the specification commit** on the delivery branch: the acceptance tests, the surface skeleton and any declared fixtures, together.
2. **Hand off to `/dekspec:review-ib IB-NNN`** with the floor digest. Its `acceptance-oracle` lens, run by a fresh-context `spec-reviewer`, reads the test sources, the skeleton and the floor report. On a passing outcome the review-ib shell — never the test author — writes the `Floor reviewed: PASS — digest <64 hex> — …` row into the IB's Amendment Log. A blocking finding comes back to you: fix it and re-run the floor, then the review.
3. **Protect the reviewed floor** — the authorizer's step, taken only when `dekspec ib floor IB-NNN` still reports the digest the row names:
   - **PROPOSED** (or DRAFT, proposed first with `dekspec ib propose IB-NNN`) — `dekspec ib accept IB-NNN` takes the baseline, tests included.
   - **ACCEPTED, run not started** — `dekspec ib baseline IB-NNN --reason "acceptance tests written (/write-tests)"`. Every later pre-start change to the tests repeats the oracle review of the changed tests (a new row) before the next `ib baseline`.
   - **Run started** — you should not be here; see the Safety check.

Commit the baseline record (`.dekspec/execution/IB-NNN/`) with the IB.

## Common Pitfalls

- Don't add skip or xfail markers "so CI stays green". The node then never satisfies its condition, and the builder may not remove the marker.
- Don't rename a node or move it to another file than the IB names. `dekspec ib verify` reports a node that is not collected as unsatisfied.
- Don't write tests after `dekspec ib start`, or edit them afterwards without `dekspec ib amend`. The integrity check fails the run.
- Don't leave acceptance tests for the builder. They are mandatory before authorization; `/implement` readiness refuses an IB whose named nodes are missing from its baseline.
- Don't compute an expected value by calling the code under test, its helpers or its constants, and don't paste observed output in as the expected value. Write the independent basis, or surface that there is none.
- Don't let the assertion recompute the expected value the way the implementation will. `assert to_slug(title) == title.lower().replace(" ", "-")` is red before the change and green after it for any implementation that copies the test's formula, so it proves nothing about the behavior. Take the value from an independent source instead: `assert to_slug("Hello World") == "hello-world"`, with a basis citing the worked example in the contract. The oracle review rejects a copied derivation (ADR-062).
- Don't count an import error, a missing symbol or a usage exit — yours or a subprocess's — as red. Commit a surface skeleton instead; a skeleton that raises does not count.
- Don't record the `Floor reviewed:` row, and don't baseline tests the oracle review has not passed. The review is independent of you.
- Don't assert on shape (call counts, call order, private state, side-channel DB reads). If a behavior-preserving refactor would break the test, it tested the wrong thing.
- Don't drop an untestable condition silently. Surface it; it is a contract defect.

## Verification Checklist

- [ ] Every `pytest:` node the IB names exists under its exact id and collects.
- [ ] Every new assertion declares its expectation basis (`Basis:`), and none takes its expected value from the code under test.
- [ ] Every new entry point the tests call has a behavior-free, non-raising surface skeleton, committed with the tests.
- [ ] `dekspec ib floor IB-NNN` reports the floor OK: every new node genuine red with a basis, every preserved node passing.
- [ ] No named node carries a skip or xfail marker.
- [ ] Every retained assertion carries a REQUIRED / GIVEN / INCIDENTAL stamp, with a fallback test per behavioral condition.
- [ ] Fixtures and golden data the tests read are listed under the IB's Protected acceptance assets.
- [ ] The tests went to the oracle review (`/dekspec:review-ib`), and are baselined (`dekspec ib accept`, or `dekspec ib baseline --reason …` before `ib start`) only once a passing `Floor reviewed: PASS` row names the floor digest.
