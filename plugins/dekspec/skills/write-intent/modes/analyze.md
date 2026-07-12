# Analyze Mode

[← back to dispatcher](../SKILL.md)


Reads `<Intent-path>`. Refuses if Status is not `DRAFT` or `OVERSIZED` (analyze re-run after split is supported; later statuses do not analyze).

> **Fan-out delegated (ds-di2).** The orchestrator dispatches this mode's body to a fresh-context `dekspec:intent-author` subagent per **Fan-Out Mode** above. The steps below are the **subagent's contract**; on return, the orchestrator validates the edited Intent (`dekspec validate --kind intent <path>`) and confirms Coverage Report + Size Assessment + Status transition were populated as specified.

### Step 1: Validate

1. File exists at the path; status is `DRAFT` or `OVERSIZED`.
2. Type field is present and is in the controlled vocabulary (audit-v2 T13). If not, refuse with a fix prompt.
3. Autonomy field is present and is in `{manual, low, medium, high}` (audit-v2 T16). If not, refuse with a fix prompt.
4. Components affected is non-empty and is a file-glob list (audit-v2 T15). If not, refuse.
5. Linked Architecture Elements has at least one entry (Decision D12). If not, refuse.

### Step 1b: Risk Tier prompt (Phase 1.B / ds-d0as)

`risk_tier:` is an **optional, open-enum** observability field. Do NOT refuse on absence — audit rule `T-INT-RISK-TIER-VALID` is warn-only (P3 advisory at most). Behavior:

1. If `## Risk Tier` section is populated with any value, accept verbatim. Note (do not block) when the value is outside the recommended vocabulary (`default | schema-migration | auth | billing | concurrency | data-residency | external-api-surface`) so the engineer can confirm intent before promotion; downstream audit will surface the same advisory.

2. If `## Risk Tier` section is empty / contains only the bracketed placeholder, surface a one-line prompt to the engineer: *"This Intent has no `risk_tier`. Pick one of [default | schema-migration | auth | billing | concurrency | data-residency | external-api-surface], or supply a custom value (open enum), or leave blank to skip. Risk tier is forward-looking blast-radius observability — absent values are tolerated; the field gates nothing today."* Capture the engineer's choice if any; if they leave blank, do not write the field at all (absence is the documented zero-signal state).

3. Recommended-by-type defaults (advisory only — propose but do not auto-populate without engineer confirmation):
    - `bug` / `refactor` / `documentation` → `default`
    - `nfr` / `adr-driven` / `environment` → `default` (often, but reconsider if the change touches auth / billing / concurrency / data-residency surfaces)
    - `feature` touching auth → `auth`; billing → `billing`; new external API → `external-api-surface`; schema changes → `schema-migration`

The audit-v2 advisory `T-INT-RISK-TIER-VALID` continues to fire P3 on unknown values regardless of the prompt outcome (Fowler lint-on-boundary — the prompt is UX scaffolding; the audit is the durable enforcement).

### Step 2: Type-Specific Required Field Validation

Type-specific blocks must be populated for the Intent's type. Refuse PROPOSED if the required block is empty:

| Type | Required block (audit-v2 T13/T14 supporting) |
|---|---|
| `feature` | (no extra block; Desired Outcome must describe new behavior) |
| `bug` | `Reproduction:` (verbatim failing command, log, or steps) |
| `nfr` | `Metric:` and `Target:` |
| `adr-driven` | `ADR:` (must resolve to existing ADR-NNN) |
| `refactor` | `Behavior-Equivalence:` |
| `documentation` | `Coverage-Gap:` |
| `environment` | `Environment-Change:` |

### Step 3: Top-Down Coverage Check

For each Component listed in `Components affected:`, scan the corpus for missing prerequisites:

- Does the change require a new AE that is not yet authored?
- Does it imply a new Working Spec or revision to an existing WS?
- Does it require a new Interface Contract for any new boundary?
- Does it imply ADR-driven decisions that have not yet been recorded?

Each gap is logged as a blocking Open Issue with **Source: analyze** and a resolution proposal: write the prerequisite first (split into a separate Intent) or close inside this Intent.

### Step 3b: Retirement / Deprecation Gate

Before sizing or recommending anything, confirm the surface this Intent targets is **still alive**. An Intent that proposes building on a retired surface is not a small problem to flag later — it is the wrong Intent, and recommending it `CANONICAL` sends the engineer to author against architecture that no longer exists (or that a decision explicitly bans re-introducing). Pattern-matching a LOCKED precedent is not enough; precedent proves the surface *used to* live, not that it lives now.

Run two checks against the architecture this Intent touches:

1. **Linked-AE status.** Read each entry under `Linked Architecture Elements:` (and any AE that owns a path in `Components affected:`). If any touched AE carries `Status: DEPRECATED` / `RETIRED`, treat that as a stop condition, not a footnote.
2. **Governing-ADR ban.** Grep `dekspec/adrs/` for ADRs that govern the touched surface (search the surface's nouns — e.g. `executor`, `dispatch`, the component name). Read any hit for language that *retires or forbids* the surface ("excised", "no longer", "must not re-introduce", "removed wholesale", a superseding in-process/replacement model). A decision that bans the surface outranks a precedent that predates it.

**If the surface is retired or banned:** set the analyze verdict to **BLOCKED**, and recommend the correct disposition instead of `CANONICAL`:
- If the capability now lives in another repo or system (the ADR usually names the replacement — e.g. an out-of-tree implementation), recommend **re-route there**.
- If the capability was removed with no replacement, recommend the engineer **author an ADR to reverse the retirement first**, before any feature Intent against the surface.

Record the finding as a blocking Open Issue with **Source: analyze**, leave Status at `DRAFT` (do not promote), and stop here — do not continue to Size Assessment or Promote. Surfacing this as a P2 caveat while still recommending `CANONICAL` is exactly the failure this gate exists to prevent: the deprecation must *govern the verdict*, not merely annotate it.

If both checks are clean (touched AEs are live, no ADR bans the surface), proceed to Step 4.

### Step 4: Bottom-Up Archaeology

Invoke `/dekspec:archeology --scan <component-path>` for each Component listed. The scan output enumerates what exists today on the file paths the Intent will touch — public API, internal state, external callers. Apply the optional 5-phase deeper-investigation mental model (see archeology Scan Mode) to extract constraints / implicit decisions / gaps, and append the findings to the Intent's **Layer impact analysis** with explicit per-layer entries.

### Step 5: Size Assessment

**Step 5.0 — Ephemeral user-story scope probe (INT-168 / D6).** Before measuring the caps, enumerate the candidate *user-stories* this Intent would satisfy — one line per distinct "as a `<persona>`, I can `<observable capability>`" the Intent implies. This probe exists for one purpose: to expose scope so the IU/Component cap check below is honest (a hidden third and fourth user-story is the usual tell that an Intent is secretly OVERSIZED). The probe is **purely ephemeral**: the enumerated stories are **never persisted to the Intent body** and **never emitted as beads** — they are reasoning scaffolding for the size verdict only. Use them to inform the IU count, then discard them. If the story list itself reveals more than one cohesive capability surface, that is a strong OVERSIZED signal — feed it into the cap measurement, do not write it down.

Measure each hard cap (Decision #5). Cap-by-cap, populate the **Size Assessment** table with the measured value and verdict:

| Cap | Limit | How measured |
|---|---|---|
| Implementation Units (IBs / direct beads) | ≤ 3 | Count the IUs the Intent's `--decompose` would produce. Use bottom-up archaeology output. |
| Components affected | ≤ 3 | Count the entries in `Components affected:` (each named component counts as one even if it expands to multiple globs). |
| New L1 artifacts (AEs) | ≤ 1 | Count AEs the Intent introduces (not revises). Linked Architecture Elements that already exist do not count. |
| New + revised L2 artifacts (WSes + ICs) | ≤ 3 | Count net new + revised, summed across WSes and ICs. |
| Coverage gaps | ≤ 2 | Count blocking Open Issues from Step 3. |

If any cap is exceeded, set Status to `OVERSIZED` and run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from DRAFT --to OVERSIZED --note "Hard cap exceeded; transitioned to OVERSIZED via /write-intent --analyze"` to save the state in the file and indices. 

Immediately initiate the **Automated Oversized Splitting & Mission Scaffolding Flow**:

#### 🛠️ Automated Oversized Splitting & Mission Scaffolding Flow

See [`_lib/oversized_splitting.md`](../_lib/oversized_splitting.md) — the canonical 5-step flow for handling an `OVERSIZED` Intent. This skill enters that flow when the size assessment in Step 5 above reports a cap violation.

### Step 6: Verification Predicate Population

For the Intent's type, the Verification block was pre-populated at Creation from the CLAUDE.md library. Re-confirm here:

- All `cmd:` entries reference scripts/tools that resolve. Run
  `scripts/check_verification_cmds.py <Intent-path>` (in this skill's folder) —
  it parses the `## Verification` yaml block and classifies each cmd as
  `resolved` / `unresolved` / `pending` (a `<placeholder>` cmd left for
  `--decompose`). It checks resolvability only; it never executes the commands.
  Surface stderr on a non-zero exit (code 2 = unresolved cmd[s]). For TBD
  scripts (`measure-nfr.sh`, `check-test-files-unchanged.sh`, `lint-docs.sh`,
  `check-doc-refs.sh` — see CLAUDE.md script-status footnote), the unresolved
  result becomes a non-blocking warning naming the corresponding
  `dektora-mi-tbd-*` tracker bead. (`scripts/check-coverage.sh` exists from
  Phase 1 P1.3.)
- Type-specific placeholders are resolved or scheduled:
  - `<reproduction-test-path-from-IB-1>` may remain — `--decompose` (Part B) fills it in.
  - `<Metric>` / `<Target>` must be filled from the nfr block (refuse advance if not).
  - `<environment-smoke-script>` must be filled (refuse advance if not).

Audit-v2 L9 will WARN at Accept if any cmd does not resolve to an executable script, and HARD-FAIL at `--testpass` (Part B). Surface the warnings now so they do not surprise the engineer at Accept.

### Step 7: WS-Fan-In Per IU

For each Implementation Unit the Intent's `--decompose` would produce, identify the WSes the IU's spec content draws from. If any IU draws from ≥ 2 WSes, that IU requires an Implementation Brief at `--decompose` time (Decision #12). Record the IU → WS-fan-in mapping in the Layer impact analysis as a footnote — `--decompose` (Part B) consumes this directly.

### Step 8: Drift Checks

- **D19 — no measurable targets in Intent prose.** Scan Motivation, Desired Outcome, and prose around the type-specific block for sentences that contain numeric thresholds, latency targets, throughput targets, capacity targets, or coverage thresholds. Such content belongs in a Working Spec. Surface findings; refuse advance until each is rewritten or moved.
- **D20 — no decision rationale in Intent prose.** Scan for "we chose X over Y because…" patterns or option-comparison rhetoric. Such content belongs in an ADR. Surface findings; refuse advance until rewritten or moved.

### Step 9: Mission Autonomy Ceiling (if `mission:` is set)

If `Mission:` is populated, attempt to read `dekspec/missions/MSN-NNN-*.md`. If it exists, enforce `Intent.Autonomy ≤ Mission.Autonomy_ceiling` — refuse advance on violation. If the Mission file does not exist (Phase 1: Missions ship in Phase 2), log a non-blocking warning naming the missing file and proceed.

### Step 10: Promote

If all of the above pass cleanly:

1. Flip Status to `PROPOSED` and bump Modified — run `python ../_lib/scripts/artifact_ops.py transition <Intent-path> --from DRAFT --to PROPOSED` (surface stderr on non-zero exit and STOP).
2. Update `dekspec/intent-index.md` — run `python ../_lib/scripts/artifact_ops.py update-index dekspec/intent-index.md --id INT-NNN --status PROPOSED` (surface stderr on non-zero exit).
3. Tell the engineer the Intent is ready for `--accept`.

If anything fails, record the findings in Open Issues with Source `analyze`, leave Status as `DRAFT` (or set to `OVERSIZED` if a hard cap was exceeded), and surface the findings list for the engineer to act on. Do **not** silently close gaps.

**End of Analyze Mode.**
