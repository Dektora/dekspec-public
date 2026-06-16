---
name: write-tests
description: Author the independent, behavior-first acceptance-test floor for a bead — public-interface tests under strong-TDD red-first timing, derived from the spec, before the coding session. Use after /write-code-beads, before /exec-coding-session.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
allowed-tools: Read Write Edit Bash
argument-hint: [--help | --teaching | --audit | --all | --integration | --revise] [BEAD-NNN or IB-path] [notes]
related_skills: [write-code-beads, exec-coding-session, write-evals, write-ibs]
disable-model-invocation: false
---

Write deterministic tests from bead acceptance criteria (TDD-style).

> **⛔ CONTEXT CHECK** — see [`_lib/context_check.md`](../_lib/context_check.md)
>
> This skill derives test assertions directly from bead acceptance criteria and IB constraints. Prior conversation context can introduce assumptions not in the spec.
>
> First message → proceed. Prior history → ask "context may affect test derivation quality, recommend /clear, continue? (y/n)" + wait.

**Mode dispatcher pattern:** see [`skills/_lib/mode_dispatcher.md`](../_lib/mode_dispatcher.md) for canonical mode semantics + the universal `--teaching` mode (per ds-int-007 / INT-008).

## Starter Prompt

```prompt
/dekspec:write-tests BEAD-42

Write deterministic stub tests for this bead from its acceptance criteria.
One test file at tests/bead/, real assertions, all marked skip for the coding agent.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Bead Test Mode** (default test-authoring path; fans out to a fresh-context subagent per `ds-di2`). The **Bead Test Mode** section below is the **subagent's contract**, not the parent's inline workflow.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **Audit mode** — `--audit` flag. Skip to **Audit Mode**.
- **All mode (fan-out)** — `--all` flag. Proceed to **Fan-Out Mode (default test-authoring path)** (one subagent per bead in the batch).
- **Revise mode (fan-out)** — `--revise` flag. Proceed to **Fan-Out Mode (default test-authoring path)**.
- **Integration mode (fan-out)** — `--integration` flag. Proceed to **Fan-Out Mode (default test-authoring path)**.
- **Bead test mode (fan-out, default)** — no flag. Proceed to **Fan-Out Mode (default test-authoring path)** below.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): (no flag), `--all`, `--integration`, `--revise`
- Inline (parent context): `--help`, `--teaching`, `--audit`

## Fan-Out Mode

See [`_lib/fan_out.md`](../_lib/fan_out.md) for the canonical ds-di2 orchestrator/subagent contract. Manifest for this skill:

- **subagent_type**: `general-purpose` (no dedicated `dekspec:tests-author` type today; v1 carrier per ds-di2 OI-1).
- **substantive_modes**: [Bead Test Mode (default), `--all`, `--integration`, `--revise`]
- **inline_modes**: [`--help`, `--teaching`, `--audit`]
- **bundle_list** (Step 1 context, gathered BEFORE dispatch):
  1. Parent bead — full path or ID and the JSON body from `br show <id> --json` (acceptance criteria, description, Files, Constraints, `external_ref` to the parent IB).
  2. Bead context chain (IB / WS / Intent / files-under-test) — run `python ../_lib/scripts/resolve_bead_context.py <bead-id>`; bundle the JSON output. It resolves, deterministically: `ib_path` (the parent IB — bead-level spec context + failure-behavior constraints the subagent derives error-path tests from), `ws_path` (the parent Working Spec — the **authoritative source of acceptance criteria + business rules**), `intent_id` (the parent Intent), and `files` (the files under test, from the IB's `## Files to Modify` table — subagent reads to derive imports / signatures / types). If `ws_path` is `null` or the `notes` array flags a broken hop, surface it as a bundle gap and refuse to dispatch. Pre-implementation source files may not exist yet — the subagent derives expected interfaces from the IB's spec context.
  3. Engineer guidance — `$ARGUMENTS` verbatim (extra notes after the bead/IB arg; for `--revise`, engineer's revision notes inline or file path; for `--integration`, the IB path).
  4. Project context — `dekspec/project-context.md` (the SDET role the subagent must adopt).
  5. Constraints — the **Test Derivation Rules**, **Test File Format**, **Rules**, and **Red-Genuineness Check** sections of this skill (deterministic-only; one criterion → ≥1 test; real assertions / stub implementations marked `@pytest.mark.skip(reason="pre-implementation — coding agent removes skip")`; edge cases from domain constraints + error paths from IB failure-behavior; import paths from bead's Files (not invented); mock external dependencies only — never internal modules; Test File Format block; and the Red-Genuineness Check — transiently unskip + run each test to confirm it fails because its assertion fired, not via a spurious non-zero exit or an import error).
- **expected_output_path**: `tests/bead/test_<bead-slug>.py` (default + `--all` + `--revise`); `tests/integration/test_<ib-slug>.py` (`--integration`). For `--all`, one path per bead in the batch.
- **validation**: `pytest --collect-only <output-path>` — confirms syntactic validity + that all tests collect (skip markers fine; collection errors not). This is a *syntactic* gate only; it never runs an assertion, so pair it with the **Red-Genuineness Check** (transiently unskip + run each test to confirm a genuine red) before reporting back. Validation/surface contract: see [`_lib/validate_and_surface.md`](../_lib/validate_and_surface.md) — test files have no `dekspec check validate --kind` form, so `pytest --collect-only` is the equivalent gate; non-zero exit → surface verbatim and stop, do not silently retry. Mode-specific post-checks: every acceptance criterion in the parent bead is referenced by ≥1 test docstring (default + `--all` + `--revise`); every bead-to-bead boundary in the IB has a data-contract test (`--integration`); parent bead's `--acceptance-criteria` updated to reference the test file (default + `--all`); no pre-existing passing tests deleted (`--revise`).

For **`--all`**: the orchestrator iterates the batch (per the existing All Mode steps 1–5), then fans out one subagent **per bead** in parallel; collects subagent reports and emits the batch summary in step 7 of All Mode.

**End of Fan-Out Mode.**

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/write-tests"
one_line:   "Write deterministic tests from bead/IB acceptance criteria"
modes:
  - { flag: "", args: "<BEAD-NNN>", description: "Write bead-level tests from acceptance criteria. One test file per bead. Tests are stubs with real assertions — the coding agent makes them pass." }
  - { flag: "--all", args: "", description: "Write tests for all open beads that don't have test files yet. Batch mode." }
  - { flag: "--integration", args: "<IB-path>", description: "Write integration tests across all beads for an IB. Tests data flow and composition between beads." }
  - { flag: "--audit", args: "<BEAD-NNN|\"all\">", description: "Check existing tests against acceptance criteria. Reports coverage gaps and stale tests." }
  - { flag: "--revise", args: "<BEAD-NNN> <notes> Update existing tests after bead or IB changes.", description: "Notes: inline text or path to file." }
  - { flag: "--teaching", args: "<BEAD-NNN>", description: "Interactive tutorial walking a new author through writing deterministic bead-level tests from acceptance criteria. (Teaching Mode)" }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/write-tests BEAD-42"
  - "/write-tests --all"
  - "/write-tests --integration dekspec/impl-briefs/IB-001-component-brief.md"
  - "/write-tests --audit BEAD-42"
  - "/write-tests --audit all"
  - "/write-tests --revise BEAD-42 \"add edge case for empty input list\""
  - "/write-tests --help"
extra_sections:
  - heading: "TEST LOCATIONS"
    body:
      - "Bead-level:     tests/bead/test_<bead-slug>.py"
      - "Integration:    tests/integration/test_<ib-slug>.py"
  - heading: "WORKFLOW"
    body:
      - "1. Create beads:    /write-code-beads <IB>"
      - "2. Write evals:     /write-evals <bead>         (if model output)"
      - "3. Write tests:     /write-tests <bead>          (for each bead)"
      - "4. Integration:     /write-tests --integration <IB>  (optional)"
      - "5. Code:            /exec-coding-session"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Teaching Mode

See [`_lib/teaching_mode.md`](../_lib/teaching_mode.md) for the canonical 4-step ritual. Parameters for this skill:

- **artifact_kind**: Deterministic test set (one file per bead at `tests/bead/test_<bead-slug>.py`)
- **template_path**: not template-driven; tests are derived directly from a BEAD-NNN's acceptance criteria
- **methodology_section**: §Test Strategy + §Test Pyramid of `docs/dekspec-operating-guide.md`
- **exemplar_paths**: existing files in `tests/bead/`, falling back to `tests/fixtures/`
- **required_sections**: one test per acceptance criterion in the bead (the criteria list takes the place of template H2 sections)

Skill-specific structural checks to surface as Open Issues: any acceptance criterion with no covering test (coverage gap).

**Skill-unique contract — the test set is not template-driven:**

Step 1 of the ritual is replaced with the deterministic-test contract: probabilistic checks belong in `/write-evals`, not here; tests are stubs with REAL assertions (the coding agent's job is to make them pass); one test file per bead. Step 3 walks each acceptance criterion in the bead, discusses what test shape covers it (unit / integration / property-based / golden I/O), and prompts the engineer for inputs, expected outputs, and fixtures. Validate that each test the engineer drafts maps to at least one acceptance criterion before accepting it.

On exit, the test file is written to disk; the engineer runs `pytest` to confirm tests fail (correctly — making them pass is the coding agent's job, not Teaching Mode's).

## All Mode

> **Fan-out delegated (ds-di2).** The orchestrator runs steps 1–5 inline (batch discovery + the plan-confirm gate), then dispatches **one fresh-context subagent per bead** in step 6 via **Fan-Out Mode** above (using the Bead Test Mode contract as each subagent's mode body). The orchestrator collects subagent reports and emits the batch summary in step 7. On return, the orchestrator runs `pytest --collect-only` against each produced test file.

Write tests for all open beads that don't have test files yet.

1. Run `br list --json --status open` to get all open beads
2. For each bead, derive the expected test path: `tests/bead/test_<bead-slug>.py`
3. Check if the test file exists — skip beads that already have tests
4. Present the plan:
   ```
   BATCH TEST PLAN — [N] beads need tests:
     BEAD-42: [title] → tests/bead/test_<slug>.py
     BEAD-43: [title] → tests/bead/test_<slug>.py
     BEAD-44: [title] → (already has tests, skipping)
     ...

   Proceed? (y/n)
   ```
5. Wait for engineer confirmation.
6. For each bead needing tests, run the **Bead Test Mode** workflow (steps 1-6 from that section).
7. Report summary:
   ```
   BATCH COMPLETE — [N] test files written:
     ✅ BEAD-42: tests/bead/test_<slug>.py (8 tests)
     ✅ BEAD-43: tests/bead/test_<slug>.py (5 tests)
     ⏭️  BEAD-44: skipped (tests exist)
   ```

**End of All Mode.**

## Audit Mode

Check existing tests against acceptance criteria for coverage gaps.

### Input

Bead ID(s): the argument after `--audit`. Accepts `BEAD-NNN`, multiple bead IDs, or `all`.

### Steps

1. Read the bead(s) via `br show <id> --json`
2. For each bead, read the test file at `tests/bead/test_<bead-slug>.py`
   - If no test file exists, report as a gap
3. Read the bead's acceptance criteria
4. For each acceptance criterion, check if at least one test case covers it:
   - Match by assertion content, not just test name
   - Check that edge cases from domain constraints are covered
   - Check that error paths are covered
5. Report:

```
TEST AUDIT:
  ✅ BEAD-42: 8/8 acceptance criteria covered
  ❌ BEAD-43: 5/7 acceptance criteria covered
     Missing:
     - "endpoint returns 400 for malformed input" — no test case
     - "all pre-existing tests continue to pass" — no regression guard
  ⚠️  BEAD-44: test file not found at tests/bead/test_<slug>.py
```

Read-only — no changes made.

**End of Audit Mode.**

## Revise Mode

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `general-purpose` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles parent bead + parent IB + parent WS + engineer notes + the existing test file into the prompt; the subagent executes them in fresh context; the orchestrator runs `pytest --collect-only` on the edited test file on return and confirms no pre-existing passing tests were deleted.

Update existing tests after bead or IB changes, or incorporate engineer feedback.

Arguments after the bead ID are the engineer's notes — inline text or a path to a `.md`/`.txt` file.

1. Read the bead and its test file
2. Read the engineer's notes (inline or from file)
3. Read the current acceptance criteria from the bead
4. Identify what changed:
   - **New criteria** — acceptance criteria added since tests were written
   - **Changed criteria** — thresholds or conditions modified
   - **Engineer requests** — specific test additions or modifications
5. Present the revision plan:
   ```
   TEST REVISION PLAN for BEAD-NNN:

   New test cases needed:
     - [criterion] → test_[name]: [assertion]

   Modified test cases:
     - test_[name]: [what changes]

   Engineer requests:
     - [note] → [proposed test change]

   Proceed? (y/n)
   ```
6. Wait for engineer approval.
7. Update the test file. Preserve existing passing tests — add or modify, don't delete unless stale.

**End of Revise Mode.**

## Bead Test Mode (default)

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `general-purpose` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles parent bead + parent IB + parent WS (for acceptance criteria + business rules) + engineer guidance + the Files-under-test paths into the prompt; the subagent executes them in fresh context; the orchestrator runs `pytest --collect-only tests/bead/test_<slug>.py` on return and confirms every acceptance criterion is referenced by at least one test docstring before reporting success.

Write test cases for a single bead's acceptance criteria.

### Input

Bead ID: `$ARGUMENTS`

If no input is provided, list open beads that have no test file yet and ask the engineer to select.

### Safety Check

- If the bead is `closed` — warn: "This bead is already closed. Writing tests after completion is unusual. Continue or abort?"
- If a test file already exists at `tests/bead/test_<bead-slug>.py` — warn: "Tests already exist. Continuing will overwrite. Continue or abort?"

Wait for engineer confirmation.

### Workflow

1. Read the SDET role from `dekspec/project-context.md` — adopt this mindset for all test writing in this session
2. Read the bead via `br show <id> --json`
3. Read the referenced IB from the bead's `external_ref`
4. Read the bead's `--acceptance-criteria` section — this is the primary source
5. Read the bead's `--description` for:
   - Files to understand the interfaces being tested
   - Domain constraints for edge cases
   - Constraints and Decisions for behavioral rules
6. Read the actual source files listed in the bead's Files section — understand the current interfaces, function signatures, and types. If the files don't exist yet (pre-implementation), derive expected interfaces from the IB's spec context.
7. For each acceptance criterion, write one or more test cases:

### Test Derivation Rules

- **One criterion, one or more tests.** Each acceptance criterion maps to at least one test. Complex criteria get multiple tests (happy path + edge cases).
- **Real assertions, stub implementations.** Tests have complete assertion logic but call functions/methods that may not exist yet. Mark with `pytest.mark.skip(reason="pre-implementation — coding agent removes skip")`.
- **Edge cases from domain constraints.** If the bead has `cuda_device: cuda:0`, write a test that verifies the output is on the correct device. If `tensor_dtype_out: bfloat16`, assert the output dtype.
- **Error paths from constraints.** If the IB specifies failure behavior, write a test that triggers the failure and asserts the behavior.
- **No mocking internal implementation.** Tests call the public interface. Mock only external dependencies (HTTP calls, database, model server).
- **Import paths from the bead's Files list.** Use the actual file paths to derive import statements.

### Scoping Role-Pass

After deriving the assertions for a criterion (Test Derivation Rules above), run the **scoping role-pass** over them before saving. The role-pass keeps each test's fence **as tight as the bead's intent and no tighter** — it borrows the intention-test scoping discipline (INT-151) and *reinforces*, rather than replaces, the existing `fence-durable` and `fence-golden-path` norms. Apply all three steps to every derived assertion:

1. **Fallback test per assertion.** For each acceptance-derived assertion, also emit a **fallback test** — a looser companion that pins the user-observable *behavior* the criterion actually promises, independent of the specific mechanism the strict assertion happens to encode. The fallback test is the one that survives a legitimate refactor; the strict assertion is allowed to be more brittle only when the mechanism itself is the contract.

2. **Over-spec mirror check.** Mirror each assertion against a hypothetical *satisfactory-but-different* implementation: would a correct implementation that made a legitimate, in-spec choice differently still pass this assertion? If a satisfactory implementation could legitimately violate the assertion, the assertion is over-specified — **delete it** (or demote it to the fallback behavior it was really guarding). The over-spec mirror check is what prevents incidental implementation mechanics from being frozen into the test suite.

3. **REQUIRED / GIVEN / INCIDENTAL classifier.** Stamp every *retained* assertion with the mechanism it pins:
   - **REQUIRED** — the behavior is part of the contract; the test must pin it tightly. Keep.
   - **GIVEN** — a precondition / fixture the test depends on but does not itself assert as the outcome. Keep, but scope it to setup, not to the behavioral assertion.
   - **INCIDENTAL** — an implementation detail (a log string format, an internal call order, a private field name) that a satisfactory implementation could change. An assertion that pins an INCIDENTAL mechanism must not survive the over-spec mirror check — drop it.

   Record the stamp as a short inline comment on each retained assertion (e.g. `# REQUIRED: return value is the canonical id`) so the fence altitude is auditable.

The output of the role-pass is the set of assertions that survive the mirror check, each carrying a REQUIRED/GIVEN/INCIDENTAL stamp, plus one fallback test per behavioral criterion.

### Test File Format

```python
"""
Tests for bead [ID]: [title]

Derived from acceptance criteria in [IB path].
Pre-written by /write-tests — coding agent removes skip markers
as implementation is completed.

DO NOT delete or weaken these tests. They are the spec.
Add additional tests for behaviors discovered during implementation.
"""
import pytest

# --- Acceptance Criterion: [criterion text] ---

@pytest.mark.skip(reason="pre-implementation — coding agent removes skip")
def test_[descriptive_name]():
    """[What this test verifies — maps to: criterion text]"""
    # Arrange
    [setup]

    # Act
    [call the interface]

    # Assert
    [concrete assertion derived from the criterion]


@pytest.mark.skip(reason="pre-implementation — coding agent removes skip")
def test_[edge_case_name]():
    """Edge case: [what edge case and why it matters]"""
    ...
```

### Save

1. Create `tests/bead/` directory if it doesn't exist
2. Save to `tests/bead/test_<bead-slug>.py` where `<bead-slug>` is derived from the bead title (lowercase, hyphens to underscores)
3. Update the bead's `--acceptance-criteria` to reference the test file:
   ```bash
   br update <id> --acceptance-criteria "$(cat <<'EOF'
   ## Acceptance Criteria
   - [ ] [criterion] — verified by tests/bead/test_<slug>.py::test_name
   ...

   ## Test File
   tests/bead/test_<bead-slug>.py — pre-written by /write-tests

   ## Evals
   ...
   EOF
   )"
   ```
4. If present is running, serve the test file for review.

### Output

```
TESTS WRITTEN for BEAD-NNN: [title]

File: tests/bead/test_<slug>.py
Tests: [N] test cases covering [M] acceptance criteria
  - test_[name]: [criterion]
  - test_[name]: [criterion]
  - test_[edge_case]: [what it covers]
  ...

All tests are marked @pytest.mark.skip — coding agent removes skip markers
as implementation is completed.
```

## Integration Mode

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `general-purpose` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract** — the orchestrator bundles the IB + all beads referencing it (the bead-to-bead data flow map) + the parent WS (for boundary contracts) into the prompt; the subagent executes them in fresh context; the orchestrator runs `pytest --collect-only tests/integration/test_<ib-slug>.py` on return and confirms every bead-to-bead boundary has a data-contract test before reporting success.

Write integration tests that verify multiple beads from the same IB compose correctly.

### Input

IB path: the argument after `--integration`.

### Safety Check

- Read the IB and find all beads referencing it via `br search --json`
- If any bead is `open` (not yet coded) — warn: "Not all beads for this IB are completed. Integration tests may be premature. Continue or abort?"
- If integration tests already exist at `tests/integration/test_<ib-slug>.py` — warn: "Integration tests already exist. Continuing will overwrite. Continue or abort?"

### Workflow

1. Read the IB
2. Read all beads for this IB (via `br search --json` matching `external_ref`)
3. Map the data flow between beads:
   - Which bead's output feeds into which bead's input?
   - What are the boundary types between them (function call, HTTP, database, queue)?
4. For each bead-to-bead boundary, write test cases:
   - **Data contract tests** — bead A's output type/shape/schema matches what bead B expects
   - **End-to-end path tests** — trace a realistic input through the full chain of beads
   - **Failure propagation tests** — if bead A fails, does bead B handle it as specified?
5. Use the same format as bead tests but with `pytest.mark.skip` on tests that depend on unimplemented beads, and live assertions for beads that are already coded.

### Save

1. Create `tests/integration/` directory if it doesn't exist
2. Save to `tests/integration/test_<ib-slug>.py`
3. If present is running, serve the test file for review.

## Rules

### What this skill is (ADR-036 / Constitution Article 3)

This skill authors the **independent, behavior-first acceptance-test floor** for a bead — the up-front, public-interface suite that proves observable behavior, written before the coding session under strong-TDD red-first timing. It owns the *independent* floor; the implementer adds discovered-behavior tests **vertically** during `/exec-coding-session` (hybrid-vertical TDD, ADR-036). Because this skill writes the suite **horizontally** (the whole floor up front, not via a vertical implement-as-you-go loop), it is *more* prone to testing imagined shape instead of real behavior. Guard against that: every test must assert an **observable behavior through the public interface**, and the Red-Genuineness Check below must confirm the *assertion* fires (not merely that some shape exists).

### The SDET's per-cycle rules (ADR-036)

Apply these to every test you write:

1. A test describes **behavior**, not implementation.
2. A test exercises the **public interface only**.
3. A test **survives an internal refactor that changes no behavior** — if a rename or restructuring with no behavior change breaks it, it tested the wrong thing.
4. Each test is **minimal and focused** — one behavior, one logical assertion.
5. *(Loosened for up-front authoring)* **Cover every acceptance criterion the bead names, but invent no behavior the spec does not call for.** The vertical implementer (rule 5's tighter form) adds tests as behavior is discovered; here you cover the named criteria and stop.

Rules 1–4 are firm. Rule 5 is the only one loosened by the up-front context.

### Public-boundary binding (the load-bearing rule)

Anchor each test to the **Interface Contract / public surface** wherever one exists — bind to a brief's internal signatures only when the bead is a genuinely internal unit with **no public boundary**. Binding to the public surface is what keeps a test surviving internal churn (rule 3) and stops the suite from being held hostage to the quality of an internal interface that may still change.

- Tests are the spec in code form. They are derived from acceptance criteria, not invented.
- Never weaken a test to make it pass — if a test fails, the implementation is wrong.
- Pre-written tests use `pytest.mark.skip` — the coding agent removes the skip as it implements.
- Tests call public interfaces only. No testing private methods or internal state.
- Mock at **system boundaries only** — external services, persistence, time, randomness, file system — never internal collaborators. Design those boundary interfaces *for* mockability: inject dependencies (pass deps in, don't construct them inside the unit), and prefer SDK-style operation-specific surfaces over one generic fetcher, so each mock returns one shape and the test setup carries no conditional logic.
- Every acceptance criterion must have at least one test. If a criterion is untestable, surface it to the engineer.
- Integration tests are optional but recommended for IBs with 3+ beads.
- Test files are working code — they must parse and be discoverable by pytest even before implementation (all tests skip cleanly).

## Common Pitfalls

- Don't write probabilistic / tolerance-based output checks here — route model-quality and non-deterministic assertions to `/dekspec:write-evals`; this skill is deterministic-only.
- Don't invent import paths or function signatures — derive them from the bead's Files list and the IB spec context; never guess a module path the bead doesn't name.
- Don't ship tests that pass on green at write time — pre-implementation tests must carry `@pytest.mark.skip(reason="pre-implementation — coding agent removes skip")` so the coding agent owns turning them green.
- Don't ship a **false red** — a test marked skip still has to fail *for the right reason* once unskipped. `pytest --collect-only` only proves the file parses; it never runs the assertion, so a test that passes spuriously or fails for the wrong reason sails through and the coding agent inherits a test that proves nothing. Run the Red-Genuineness Check below before the collect gate.
- Don't assert a bare non-zero exit for a "should-fail / should-gate" test — an *unrecognized* flag or arg makes the CLI exit non-zero (argparse exits 2) on its own, so `assert rc != 0` passes for the wrong reason. Pin the failure to the feature: also assert the error text is NOT `unrecognized arguments` / `invalid choice`, or assert the specific exit code / message the feature is contracted to produce.
- Don't let an import error masquerade as the red — `from pkg.notyet import thing` failing at import time makes the whole test error before the assertion runs, which looks red but tests the import, not the behavior. Import lazily inside the test (or via the public CLI / a subprocess) so the *assertion* is what fails.
- Don't mock internal modules to force a test to collect — mock only external dependencies (HTTP, database, model server); a test that mocks the unit under test proves nothing.
- Don't assert on **shape instead of behavior** (ADR-036 / Constitution Article 3) — red flags: asserting on call counts or call order; verifying through a side channel (e.g. querying the DB directly) instead of the public interface; testing private methods or internal state; a test that breaks on a rename with no behavior change. The litmus test: *if it breaks on an internal refactor that changed no behavior, it tested the wrong thing.*
- Don't weaken or delete a pre-existing passing test to resolve a conflict (`--revise`) — add or amend; tests are the spec, not an obstacle.
- Don't skip the `--acceptance-criteria` backlink update (default + `--all`) — an orphaned test file the bead can't point to fails the post-check.
- Don't drop an untestable acceptance criterion silently — surface it to the engineer rather than leaving a coverage gap.

## Red-Genuineness Check

The `@pytest.mark.skip` markers exist so a half-built suite collects cleanly and never breaks CI before the feature lands — they are **not** a substitute for confirming each test is genuinely red. ADR-029 strong-TDD turns on the test failing *for the intended reason* first; a skipped test that has never been run can hide a false red (passes spuriously, or errors at import before the assertion). Close that hole before the collect gate:

For each pre-implementation test you wrote, in a scratch copy of the file (never the shipped one):

1. Remove that test's `@pytest.mark.skip` marker.
2. Run it: `PYTHONPATH=<repo>/tooling python3 -m pytest <scratch-file>::<test> -q` (or invoke the public CLI / subprocess the test targets).
3. Confirm it **FAILS, and the failure is the assertion firing** — not a collection/import error, and not a spurious pass. Apply the two traps from Common Pitfalls: a bare non-zero exit can come from argparse rejecting an unknown flag (exit 2), and an import error can mask the assertion entirely. If the test passes or errors for the wrong reason, fix the test (pin the failure to the feature's contracted behavior) and re-run until the red is genuine.
4. Discard the scratch copy — the shipped test keeps its skip marker for the coding agent to remove.

Record one line per test in your report: `<test> → red (assertion fired)` or the correction you made. This is the step that makes the suite a real red-first contract rather than a parked stub.

## Verification Checklist

- [ ] Every acceptance criterion in the parent bead is referenced by at least one test docstring (default / `--all` / `--revise`).
- [ ] Every test that exercises unimplemented code carries the `@pytest.mark.skip(reason="pre-implementation — …")` marker.
- [ ] **Red-Genuineness Check done** — each pre-implementation test was transiently unskipped and run, and confirmed to fail because its assertion fired (not a collection/import error, not a spurious non-zero exit).
- [ ] `pytest --collect-only <output-path>` exits zero — the test file parses and all tests collect.
- [ ] All import paths trace to the bead's Files list or IB spec context (none invented).
- [ ] Only external dependencies are mocked; no internal module under test is mocked.
- [ ] The parent bead's `--acceptance-criteria` was updated to reference the written test file (default / `--all`).
- [ ] (`--integration`) Every bead-to-bead boundary in the IB has a data-contract test.
- [ ] (`--revise`) No pre-existing passing test was deleted or weakened.

## Closing Step

**Mandatory closing step for every substantive mode of this skill** (the modes that write or revise a test suite — All Mode, Bead Test Mode, Integration Mode, `--revise`). After the test file(s) are saved, run:

```
dekspec audit relink
```

against the repo root. This deterministically re-derives and renders the cross-artifact `Linked Artifacts` backlinks from the forward links the artifact declares, stitching the spec graph in one pass. This is a required action, not a reminder — do not defer it, do not surface a "backfill the backlinks later" note to the engineer. `dekspec audit relink` is the graph-repair pass; running it is the last thing the skill does before reporting back.
