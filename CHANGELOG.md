# Changelog

All notable changes to DekSpec are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/); versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [v0.120.0] — 2026-06-19

> Audit + skills batch: ContextSpec becomes a first-class audited IR, four new utility skills land, the components-affected glob audit catches refactor-stale paths across the whole lifecycle, and a dead schema-resolution path that contradicted a LOCKED ADR is removed. No breaking changes (public schema API unchanged).

### Added — ContextSpec wired into the SpecGraph (INT-139 / ds-uqnx)

The 11th IR kind was parsed + schema-validated + CLI-resolvable but never entered the SpecGraph (no loader, no iterator, no linkage rule) — advertised as live yet governance-inert. It now loads (`dekspec/context-specs/role-*.md`), is exposed via `SpecGraph.context_specs()`, and participates in a new `L-CS-ROLE-UNIQUE` linkage rule (P2): each `role_identity` is claimed by at most one ContextSpec, so the reviewer dispatcher's role→scope resolution is unambiguous.

### Added — four utility skills

- **`/dekspec:pr-branch`** (ds-40sh) — build a clean `<branch>-pr` that filters spec-only commits (status bumps, index reconciliation, pm ledgers) and strips spec-only files from mixed commits, so code PRs show only the implementation diff. Pure git; never touches `main`.
- **`/dekspec:forensics`** (ds-avxp) — read-only post-mortem for stuck/failed construction sessions: collects git/worktree/bead/linkage evidence, matches known failure fingerprints, writes a forensic report with a root-cause hypothesis. Remediates nothing.
- **`/dekspec:spike`** (ds-dekspec-spike) — pre-Intent feasibility spike: a throwaway experiment that produces a verified-knowledge record (hypothesis → VALIDATED/REFUTED/INCONCLUSIVE → recommendation) the next Intent cites. No production leak.
- **`/dekspec:goal-loop`** — write verifiable goal contracts (Objective / Constraints / Validate / Stop) for long-running autonomous runs; drive via `/loop`, a background agent, `/schedule`, or `exec-coding-session`.

### Added — `review-ib` sibling-ib-coherence lens (ds-review-ib-scope-creep-sibling-ib)

A 16th REVIEW_IB lens that flags sibling IBs under the same parent Intent modifying overlapping files with no `depends_on` ordering edge — a cross-IB coherence gap the `scope-creep` lens (which only diffs against the parent Intent's globs) was structurally blind to.

### Changed — L7b stale-glob detection across all statuses (ds-to7s)

`L7b-INT-COMPONENTS-RESOLVE` now checks every non-terminal Intent. The build-underway band (IMPLEMENTING/TESTPASS/MERGED), previously fully exempt, now emits a `P3` advisory so a refactor-stale `components_affected` glob surfaces instead of hiding; LOCKED keeps `P2` (the sole gating severity). One canonical glob gate, reconciled with the existing rule per ADR-019.

### Fixed

- **schemas (ds-99ai):** removed the dead archive/version-pinned schema-resolution path (`load_schema(version=)` archive read + `list_schemas` archive walk). It had no caller and no archive directory, and its docstring described a version-pinned model that contradicted the LOCKED **ADR-008** lazy-migration-registry (migrate IR → validate against current). Public API + tests unchanged.
- **skill flag-defaults:** registered the new utility skills (pr-branch, forensics, spike, goal-loop) in `_SKILL_CLASS_DEFAULTS` + `docs/dekspec-skill-flag-defaults.md`, clearing `T-SKILL-FRONTMATTER-NORMAL` P2 findings.

## [v0.119.0] — 2026-06-17

> Governance + onboarding hardening: write-time LOCKED enforcement, a debugging skill, a doc-honesty sweep, and a deeper mirror leak-guard. No breaking changes.

### Added — `/dekspec:debug` skill (INT-177)

A `/dekspec:debug` skill adopting the debugging-9-rules protocol with persistent investigation state (survives context resets / handoffs), wired into the `--testpass` failure path and registered in the canonical skill flag-defaults.

### Added — write-time LOCKED-artifact enforcement (ds-k24i)

A `PreToolUse(Edit|Write|MultiEdit)` hook mechanically **blocks** a direct Edit/Write to a LOCKED artifact under `dekspec/` (exit-2 + a clear reason). LOCKED immutability was previously honor-system (only a post-edit audit, after the fact). The legitimate paths stay exempt: status transitions run via `artifact_ops` (Bash, not the Edit tool), and `/write-intent --sync` drops a staleness-guarded marker the hook honors; `DEKSPEC_HOOK_DISABLE=1` overrides.

### Added — skill-lint + mirror leak-guard hardening

- `skill_lint` gains C5 (deprecated-CLI invocations), C6 (dead related-skill references), and C7 (skill-markdown `dekspec …` arg forms linted against the live CLI).
- The mirror leak-guard now asserts the **materialized** curated tree (release.yml post-rsync guard + a test that materializes the git-tracked tree), not just the include-manifest text — catching a forbidden path a glob expands into, or build junk `rsync` would carry (ds-609x).

### Fixed / Changed — doc-honesty sweep + skill-reference repairs

- Doc-honesty sweep (ds-52ol): README runnable quick-start verbs canonicalized (`library init` / `audit doctor` / `check validate` / `check aggregate` / `dev graph`); nonexistent onboarding skill/command references removed and test-guarded; a canonical smallest-path `--lite` recipe added; the fresh-user next-step nudge no longer points at `/write-ae`; the overclaimed immutability statement made accurate (now backed by the ds-k24i hook).
- Repaired stale references + dead/deprecated CLI invocations across 6 skills; corrected the `check validate` arg form in `write-sv` / `write-constitution`; optimized the `write-intent` skill description for triggering (ds-gvg1); bundled `depth_classify.py` into `audit-codebase` for vendor portability.

## [v0.118.0] — 2026-06-17

> Docs patch release: fixes the consumer-facing install URL (P0) and documents the platform-aware installer.

### Fixed — README quick-start install URL 404'd for consumers (ds-9svk, P0)

The README quick-start curl blocks pointed at the **private** source repo (`raw.githubusercontent.com/Dektora/dekspec/main/scripts/install.sh`), so a new consumer's first command 404'd. All three blocks now point at the curated **public mirror** (`Dektora/dekspec-public`, ADR-034), matching `install.sh`'s `MIRROR_REPO` and the Installation section. A new guard — `tests/test_no_private_install_url.py` — bans the private install-script path from install-facing docs (README / RELEASING / docs) so the regression cannot reappear.

### Changed — README documents `install.sh --platform <host>`

The single-command install section now shows the per-host form (`install.sh [VERSION] [--platform <host>]`) with examples for the default `claude` and the other hosts, the platform-aware step list (host-agnostic steps 1–3; step 4 dispatches `claude` → marketplace, every other host → `dekspec install --platform <host>`), and the `claude` CLI requirement scoped to `--platform claude`.

## [v0.117.0] — 2026-06-16

> Patch release: fixes per-host `install.sh` delivery for non-Claude hosts — a defect in the v0.116.0 platform-aware installer surfaced by a live install test.

### Fixed — non-Claude `install.sh --platform <host>` emitted an empty tree

`dekspec install --platform <host>` sources its skill/command/hook tree from `plugins/dekspec`, which is **not bundled in the wheel** (ADR-009 — the plugin ships to Claude via the marketplace). On a wheel/pipx install the per-host emit therefore wrote only the `extensions` marker and no skills, commands, or hooks. `scripts/install.sh` now shallow + sparse-clones `plugins/dekspec` from the mirror at the install ref and passes it as `--source`, so non-Claude hosts (**codex / antigravity / cursor / copilot / pi**) receive the full per-host tree. The Claude marketplace path is unchanged.

## [v0.116.0] — 2026-06-16

> Large feature release covering five clusters landed since v0.115.0. No breaking changes (minor bump). New surfaces: **9 skills**, **5 ADRs** (ADR-036…040), **AE-010**, **5 audit rules**, and host-portable install.

### Added — harness abstraction + multi-host adapters (MSN-021, ADR-037, AE-010)

A host-abstraction seam (`get_adapter(host)`) plus first-party adapters for **codex / antigravity / cursor / copilot / pi**, the fan-out seam wiring, and an install emitter. `scripts/install.sh` is now platform-aware (`install.sh [VERSION] [--platform <host>]`): host-agnostic steps 1–3 (resolve ref → pipx install → `dekspec library sync`) then per-host delivery — `claude` via the managed marketplace, every other host via `dekspec install --platform <host>` emitting the per-host skill/command/hook tree.

### Added — architecture-deepening + over-decomposition detection (ADR-038, ADR-039)

New `audit-codebase`, `deepen-codebase-architecture`, and `orchestrate-deepening` skills (APOSD-grounded concentration-raising), plus over-decomposition detection by cohesion + facade-ratio (ADR-038) and Pareto-band module-depth classification with a floor (ADR-039). Adds the `codebase-audit` / `codebase-slice-discovery` surfaces and the `T-TO-MISSION` rule.

### Added — behavior-first TDD + deep-module discipline (ADR-036)

Codifies behavior-first / strong-TDD timing and deep-module preference as a governing decision (PR #97), feeding the review pipeline + detector wiring (PR #98).

### Added — agentic-workflow best-practices adoption (MSN-020, ADR-040)

Native, zero-external-dependency adoption of proven agentic-workflow best practices:
- **6 new skills:** `interview-me` (docs-anchored one-question-at-a-time interview rigor, default-on/skippable in write-intent/mission/ae/adr); `diagnose` (deterministic repro-signal-first → promotes a bug Intent); `prototype` (throwaway exploration → `dekspec/.scratch/prototypes/`, findings route to governed artifacts); `write-issue-beads` (non-coding bead lifecycle: ingest → vertical-slice decompose → product-gated escalation → backlog grooming); `setup-dekspec` (initial `.dekspec/config.yaml` config front-end via `dekspec exec config`); `rotation-handoff` (native session continuity — structured, secret-redacted handoff to `dekspec/.scratch/`, read back at session start; `PreCompact`/`SessionEnd` registered so compaction rotations are captured; zero `claude-mem` dependency).
- **`write-beads` renamed to `write-code-beads`** (coding-pure, no alias).
- **`write-ggc`** gains a no-auto-write extraction capture stage (mines glossary-term candidates from conversation + governed artifacts, 3-way canonical/ambiguous/drop triage, never writes the glossary directly).
- **`write-intent`** gains problem/user framing, an optional Non-Goals section for Mission-less Intents, and a behavior-preserving-vs-changing refactor split; **`write-ic`** gains a Phase-2 design-twice pass + an Options Considered/Rejected section.
- **Cross-cutting file-locality `dekspec/.scratch/` convention** (ADR-040): ephemeral skill output → gitignored `.scratch/`; in-formulation → `dekspec/provisional/`; finalized → committed governed folders. Retrofitted the three repo-root `*-workspace/`-emitting skills.
- **Installable hook templates:** a Python quality gate (pre-commit/ruff/pytest/dekspec-doctor) + a destructive-git-command deny guard, installed via `setup-dekspec`.
- **3 new P3 advisory audit rules:** `T-INT-NON-GOALS-MISSING`, `T-BUG-REPRO-GATE`, `T-IC-OPTIONS-MISSING`.

### Added — vendored utility skills

Nine `jeffhaskin-` utility skills vendored (two infra skills gated from the public mirror).

## [v0.115.0] — 2026-06-12

> Closes out **ds-aov7**: the two facets deferred from INT-142's scope split (2026-06-09) — the `verification.manual` per-check skip (ds-cjqi) and the `/write-intent --supersede` flag (ds-9hma) — now both shipped.

### Added — per-check manual attestation in the Verification predicate (ds-cjqi)

A Verification check may now carry `manual: true` + `manual_rationale: <why>`. `/write-intent --testpass` does **not** execute such a check's `cmd:` — it requires the rationale (refusing without one) and records a `MANUAL-TESTPASS` row carrying the rationale instead of an exit code; manual checks never trigger the fast-fail. For predicates needing infrastructure the local box lacks (e.g. a GPU smoke stack on a CPU dev box) — sanctioned in operating guidance, previously unimplemented (`--testpass` hard-ran every cmd). Deterministic surface: `intent.schema.yaml` adds the two optional fields with an `if/then` requiring the rationale when `manual: true`, and `parser._extract_intent_verification` exposes both fields (stripping them from the cmd capture) and raises on `manual: true` without a non-empty rationale. `modes/testpass.md` Step 3 + the Intent template document the semantics.

### Added — `/write-intent --supersede` + ADR-035 non-LOCKED absorption carve-out (ds-9hma)

The bead's architectural blocker (conflict with LOCKED ADR-028) is resolved by **ADR-035** (LOCKED): a non-LOCKED, pre-implementation Intent (`DRAFT`/`OVERSIZED`/`PROPOSED`/`ACCEPTED`) whose committed direction was absorbed by a **named successor artifact** (`INT-NNN` or `MSN-NNN`) may transition to `SUPERSEDED` — a refinement alongside ADR-028, not a supersession of it (PEEL-OFF stays the OVERSIZED default; LOCKED-override stays the successor-Intent path). The new `--supersede <Intent-path> --by <INT-NNN|MSN-NNN>` mode (`modes/supersede.md`) drives a new deterministic `artifact_ops.py supersede` helper: enforces the allowed status set (refusing `LOCKED`, `IMPLEMENTING`/`TESTPASS`/`MERGED`, already-`SUPERSEDED`, and unnamed successors), rewrites `## Superseded-By`, bumps Modified, appends the Amendment Log row; the skill mode then moves the index row from Active queue to Archive. The Intent IR `superseded_by` field (schema + parser) now accepts `MSN-NNN` successors (was INT-only).

## [v0.114.0] — 2026-06-09

### Added — `/write-intent --lock` Path C: retroactive post-merge lock for direct-bead Intents (INT-142, ds-aov7)

A sanctioned `--lock` path for a zero-downstream direct-bead Intent whose work already merged to `main`. Such an Intent could previously reach neither Path A (no live `int/` branch left to `--testpass`) nor ADR-017 Path B (no downstream WS/IC/IBs), so it sat at `MERGED` indefinitely and hand-editing Status to `LOCKED` is guardrail-forbidden. Path C gates on: `MERGED` + zero downstream Implementation Briefs + every bead in the Intent's Layer impact analysis closed + the Verification predicate re-passing from `main`. The bead-closure portion is enforced by a new deterministic `artifact_ops.py check-retro-lock <Intent-path>` helper (validates bead-shaped tokens against the beads DB, so hyphenated prose is ignored, and requires ≥1 resolvable closed bead), wired into `modes/lock.md`. The L13 lock-coherence rule is unchanged — it already stays silent on a zero-downstream LOCKED Intent (INT-036 OI-3). Scoped to this one facet of ds-aov7; the sibling `verification.manual` skip (ds-cjqi) and `--supersede` flag (ds-9hma) are tracked separately.

### Fixed — release pipeline: marketplace-ref gate + frozen mirror tag (ds-dv6r)

Two latent release-pipeline defects surfaced shipping v0.113.0 (the plugin half needed manual recovery despite engine/vendored/plugin.json all correct). (1) `.claude-plugin/marketplace.json::source.ref` — the ref `claude plugin update` actually resolves — was an unchecked version location: the release version check asserted only tag/`__version__`/CHANGELOG, so a stale ref shipped silently. The check is now a *quad* (adds the marketplace ref) and a `bump-version.py --check` step gates every hardcoded mirror against `__version__`. (2) The mirror-sync tag push was skip-if-exists/non-force, so re-pointing a release tag (a documented recovery) advanced mirror `main` but left the mirror *tag* frozen at its first-creation commit. The tag-alignment decision is extracted into `scripts/mirror_tag_align.sh` (force-align to HEAD unless already there; true duplicate fires — ds-rqj5 — left untouched), called by `release.yml` and covered by a `test_upgrade_e2e.py` re-point regression test. Also synced the README / EXAMPLES / methodology version mirrors that the v0.113.0 release left at v0.112.0.

### Fixed — self-spec: cleared MSN-019 daughter audit drift (ds-ranf)

The eat-own-cooking dogfood gate (`dekspec audit doctor`) had been red since the MSN-019 daughters landed: 7 P2 findings on the LOCKED Intents INT-139/140/141 — `§Linked Architecture Elements` bullets used an unparseable `- AE-NNN (Name; STATUS) —` paren format (`L7a-INT-AE-MISSING`, reformatted to the parser's `- AE-NNN: Name —` colon form), empty `verification: []` blocks (`T14-INT-VERIFICATION`, backfilled), and unfilled Outcome Verification placeholders (`T-VERIFICATION-OUTCOME`, declared against the shipped tests). Fixed via the sanctioned `--unlock` → edit → `--lock` (Path B) round-trip; `audit linkage` P2 7→0, `audit doctor` back to `ADVISORY`. No behavioral change to shipped code.

## [v0.113.0] — 2026-06-09

> **MSN-019 — the Spec Reviewer + ContextSpec substrate.** Three serialized daughter Intents (INT-139 → INT-140 → INT-141, ADR-016) generalize the dekfactory Phase-0 single-role reviewer prototype into a first-class, parser-validated, six-role reviewer substrate. All additive (ADR-011 Option B zero-coupling) — existing `--review` modes, audit rules, and the MSN-017 SQLite review-flywheel are untouched.

### Added — `context_spec` IR kind: the 11th first-class IR kind (INT-139)

A new IR kind generalizing per-role reviewer input-scoping into an addressable, parser-validated artifact. Ships `tooling/dekspec/schemas/context-spec.schema.yaml` (closed under `additionalProperties: false` at every level), `parse_context_spec(path)` in `constraint_compiler/parser.py` (purely additive, modeled on `parse_security_profile` per ADR-011 Option B; re-exported from `constraint_compiler/__init__.py`), `SCHEMA_FILENAMES`/`LATEST_VERSIONS` registry rows, the `CS-` migration ID-prefix, `templates/context-spec-template.md` (AE-007 convention), and six canonical instances `dekspec/context-specs/role-{specifier,spec-reviewer,implementer,code-reviewer,verifier,auditor}.md` (CS-001…006). `dekspec check validate --kind contextspec <path>` validates them via the CLI. Generalizes `dekfactory/.../reviewer_context_spec.schema.json` (INT-075 Phase 0; AE-014 §4.2 adversarial-separation invariant) to all six pipeline-role identities. Governed by AE-004 + AE-007.

### Added — shared `Reviewer<ArtifactType>` dispatcher + IC-016 contract (INT-140)

A new dispatcher module `tooling/dekspec/spec_review/reviewer.py` (sibling of — and non-colliding with — the LOCKED MSN-017 `tooling/dekspec/review/`): `Reviewer.dispatch(context_spec: dict, artifact) -> list[Finding]`, IO-free (the caller parses the ContextSpec via the LOCKED `parse_context_spec` and passes the typed dict; `dispatch` performs no file IO), routing on the dict's `role_identity` and returning the LOCKED AE-003 `Finding` dataclass verbatim at default severity P2. The boundary is pinned in **IC-016** (`reviewer-dispatcher-contract`, v1.0.0, LOCKED): the signature, the finding-shape, and the P2 default-severity contract that the six consuming `--review` modes register against. Governed by AE-006 + AE-003.

### Added — six `/write-*` `--review` modes dispatch through a shared reviewer lib + `SPEC-REVIEW` audit family (INT-141)

A new shared `plugins/dekspec/skills/_lib/reviewer_mode.md` `--review`-mode contract that all six `/write-*` skills (`write-intent`, `write-ws`, `write-ic`, `write-ae`, `write-adr`, `write-ibs`) now dispatch through — loading the `spec-reviewer` ContextSpec, invoking `Reviewer.dispatch`, and routing the returned findings into the audit surface — instead of each carrying ad-hoc reviewer prose (existing interactive walkthroughs preserved). A new additive audit-rule family `tooling/dekspec/fidelity_audit/spec_review_rules.py` (`spec_review_rules(graph, profile)`, mirroring `prose_shape_rules`, extended into `audit_linkage`) registers the `SPEC-REVIEW` rule code in the `v1`/`lite`/`team` profiles at P2 and surfaces a hand-authored artifact's missing-derivation-source ambiguity (a spec deriving from an Architecture Element absent from review scope) as a P2 finding through the LOCKED AE-003 surface. **Behavior note:** a newly-authored or `--unlock`-revised WS/IC that references an absent AE now surfaces a `SPEC-REVIEW` P2 (approval-blocking) finding at `audit`/`--analyze` time; existing LOCKED artifacts are not retroactively reviewed. Governed by AE-006 + AE-003.

### Fixed — MSN-019 Mission Verification predicate corrections + `run_verification.py` generic-token workaround

Five of MSN-019's 16 Mission Verification predicates were authored speculatively at Mission-creation (before the substrate existed) and did not match the shipped CLI surface: `audit doctor` has no `--min-severity` flag and prints no rule codes (corrected to `audit linkage --at <fixture> --dekspec-root . --min-severity P2 --json | grep SPEC-REVIEW`); the IC status grep `^Status.*LOCKED` never matched the `## Status` / bare-`LOCKED` IC format (corrected to a bare-line match); and a clean-repo `--at .` finding-grep was repointed at the acceptance fixture. Two predicates also tripped `write-mission/scripts/run_verification.py`'s placeholder guard (`re.compile(r"<[^>]+>")`), which rejects any `cmd:` containing a literal generic-typed token such as `Reviewer<ArtifactType>` as an unresolved `<placeholder>`; worked around with a regex (`Reviewer.ArtifactType`). The guard should be hardened upstream to whitelist known literals or only fire on lowercase-kebab `<placeholder>` forms.

## [v0.112.0] — 2026-06-02

### Fixed — `update_index` appends into the data table, not a leading legend (ds-update-index-wrong-table-shape-z765)

`artifact_ops.py::update_index`'s no-existing-row append path derived both the row shape and the insert position from the **first** markdown table in the file. An index that opens with a legend table — `intent-index.md`'s `| Status | Meaning |` lifecycle legend (2 columns, header col 0 literally `Status`) — produced a malformed row: `n_cols` came from the legend (2, not the 8-col data table), the Status-column finder matched the legend's col-0 `Status`, and the status then **overwrote the id cell** (`| <STATUS> ||`), inserted at the file's last table (Archive) rather than the shape-source table. Repeated calls appended one garbage row each and never created the real data row (silent, exit 0). Fix: a new `_find_data_table` selects the first table whose `Status` column is at index > 0 (skipping ≤2-col `Status`/`Meaning` legend tables; falls back to the first table for legacy 3-column indexes), and the append derives its shape **and** inserts into that same data table; a `status_col == 0` guard ensures the status can never overwrite the id cell.

## [v0.111.0] — 2026-06-02

### Added — `/dekspec:orchestrate-intent` + `/dekspec:spec-intent` accept a provisional Intent as entry (ds-jtfn)

The conductor and spec phase-executor previously resolved only a canonical `INT-NNN`/path, so they could not pick up a provisional incubation (`dekspec/provisional/<slug>/`, no canonical id) — yet the provisional-first default (INT-133) means most Intents start there. A new shared resolver `plugins/dekspec/skills/_lib/scripts/resolve_intent_target.py` resolves `INT-NNN` / canonical path / provisional slug / provisional path → `{kind, path, intent_id, status, is_provisional}` (an ambiguous multi-Intent incubation demands the explicit path). Both conductors' target identification and `--status`/`--verify` use it; a provisional target surfaces a state card noting the canonical id is allocated at the accept gate, and the provisional path is passed to the dispatched executor. No new gate or ADR-021 row was needed — promotion already rides `--accept` Step 3 (INT-082 Provisional Promotion), which `--auto` governs via the existing `analyze-complete` → `accept-clean` pre-conditions.

### Added — Vendored grep-loop review-fix workflow (`_lib/grep_loop_review_workflow.md`, ds-5oc9)

The grep-loop review-fix discipline that the `REVIEW_PR_FAIL` handler leans on existed only as inlined prose plus a non-vendored personal skill (consumers never received it). It is now a dekspec-owned bundled doc at `plugins/dekspec/skills/_lib/grep_loop_review_workflow.md` (MIT, adapted from the David Ondrej / Michael Shimeles `grep-loop-review-workflow` notes): the six review-fix rules, PR-size pre-flight, guardrails/pitfalls, and the dekspec REVIEW_PR bindings (`/code-review --comment` seed, the sidecar, `context.ib_branch` landing, RECOMMEND-only per ADR-026). `review_pr_fail.md` now cites the owned doc instead of duplicating the prose.

## [v0.110.0] — 2026-06-02

### Added — `/dekspec:write-adr --amend` editorial-at-LOCKED mode (ds-qxpq)

Mirrors `/write-intent --amend --editorial` for ADRs: a new `--amend` inline mode records a surface-only correction (Decision-opening prose, `Links`, Related Architecture Elements) with an `editorial` Amendment Log row + `Modified` bump, **without** the `--unlock` → `--lock` cycle and without flipping Status. The shared `artifact_ops.py editorial-amend` helper is now **kind-aware**: ADRs route through a new `classify_adr_diff` whose deny-list (`Status`, supersession fields, `Context`, `Options Considered`, `Consequences`, `Validation`) refuses decision-altering diffs with an ADR-specific message pointing at `--unlock` + `--lock`; Intents keep `classify_intent_diff` + the PROPOSED→DRAFT cascade message.

### Fixed — Intent spec-phase: no-WS bead-gate + concurrent-worktree collision (ds-1k2m, ds-2tky)

- `--accept`'s Bead Authoring Gate now branches on WS/IB presence: a no-WS Intent (refactor/env/doc, WS fan-in 0 → direct-bead at `--decompose`) treats the gate as **N/A** rather than as an unsatisfiable `beads_before_accept: true` (IBs don't exist until `--decompose`, which runs post-ACCEPTED — the prior chicken-and-egg).
- New `worktree_guard.py` refuses `git checkout -b` of a new Intent branch while HEAD sits on another `int/INT-*` branch (the concurrency collision that leaked one Intent's commits into another's ancestry) and prints the isolated `git worktree add … -b int/INT-NNN main` command instead. Wired into Creation + provisional branch creation.

### Fixed — P3 batch: semver plugin-drift, provisional find-beads, phantom `--bug-reproduction` (ds-ro98, ds-nv1i, ds-16ti)

- `dekspec doctor` plugin-version-drift now selects the **semver-max** cache dir, not the lexicographic max (a stale `0.99.0` no longer false-drifts a real `0.108.0`/`0.109.0`).
- `find_beads_for_ib.py` accepts **provisional bare-slug** IB paths (literal filename-stem match against `external_ref` when there's no `IB-NNN`/`INT-NNN` token), unblocking the Path A bead-first workflow on provisional IBs; canonical token matching is unchanged.
- Dropped the phantom `/write-beads --bug-reproduction` invoke from `--decompose` + both Intent templates; per ADR-029 the bug reproduction test **is** the per-Intent Outcome Verification test (red-first), produced via the normal `/write-beads` flow.

### Docs — Sweep stale `install-dekspec.sh` advisory note across 10 `/write-*` skills (ds-7c67)

The shared INT-097 callout in the 10 `/dekspec:write-*` SKILL bodies referenced the (now-removed) `scripts/install-dekspec.sh` with conditional "if your install is pip-only" framing — doubly stale post-ADR-034 (the public mirror + `pipx` pip-from-git is the only path). Replaced each with an unconditional one-liner pointing at the centralized `_lib/vendored_assets.md`.

## [v0.109.0] — 2026-06-02

### Removed — Deprecated `dekspec repo upgrade` / `dekspec upgrade` CLI alias + `/dekspec:upgrade` slash command (ds-d063)

- Removed the `dekspec repo upgrade` / top-level `dekspec upgrade` acquisition alias and the `/dekspec:upgrade` slash command. ADR-032 deprecated the alias as a one-release forward-to-reconcile shim (v0.106); ADR-034 (v0.108) killed the in-CLI acquisition model entirely. With the deprecation window elapsed, the verb and its residual acquisition machinery (`cmd_upgrade`, `_add_upgrade_subparser`, the plugin-version snapshot/downgrade detectors, the install-method/plugin-verb probes) are gone. Acquire the engine + plugin out-of-band (`pipx`/pip-from-git + `claude plugin update`) and reconcile vendored content with `dekspec library sync`.

### Fixed — `/exec-coding-session` synced to the post-MSN-016 (no-factory) reality (ds-3xx1, ds-76sq, ds-5dfj)

- The `exec-coding-session` skill still invoked CLI verbs that **MSN-016** (COMPLETE; governed by **ADR-024**, the no-factory in-process-only execution model) retired wholesale — the package builder (`dekspec package build`), the SQLite lifecycle DB + `dekspec executions` verb (whose contract **IC-004** is DEPRECATED), and the pre-`dekspec exec` `session`/`runs` paths. The skill was never swept, so `/exec-coding-session INT-NNN` failed on the package-build step and the IC-004 lifecycle writes errored on 0.107–0.108. Now: the package-build auto-resolution and `--package` mode are dropped (an IB/Intent arg routes directly into Phase 1 `br ready` discovery); the dead IC-004 lifecycle-DB writes are removed (no replacement verb — the obligations retired with the executor abstraction); `dekspec session …`/`dekspec runs` move to `dekspec exec session …`/`dekspec exec runs`; and the lifecycle-write-only helper `resolve_parent_intent.py` is deleted.
- `preflight_quality_gates.py` no longer false-STOPs on greenfield IBs: a referenced test file that is missing on disk but **claimed by a bead's "Files to Modify"** is treated as an expected deliverable; the gate STOPs only when a referenced file is missing **and** unclaimed by any bead in the set.

### Removed — Stray `run-coding-session.md` command file (ds-jhbw)

- The frontmatter-less `plugins/dekspec/commands/run-coding-session.md` (the command was renamed to `/exec-coding-session` in INT-098, but the file lingered and INT-123 had written its IB-lifecycle/TESTFAIL wiring docs into it) is deleted; the wiring is relocated into the canonical `exec-coding-session.md`. INT-123's Verification/Components/Outcome references were repointed to the new surface and the Intent re-locked.

## [v0.108.0] — 2026-06-02

### Changed — Distribute via a curated public mirror repo; retire Cloudsmith + the latest-resolver (INT-137, ADR-034)

DekSpec and its Claude Code plugin now distribute through a curated **public mirror** repo (`Dektora/dekspec-public`) that carries only the distributable subset — `tooling/`, `plugins/dekspec/`, `templates/`, the cherry-picked `docs/`, `setup.py`/`pyproject.toml`, `scripts/install.sh`, `.claude-plugin/marketplace.json`, `README`/`CHANGELOG`. The existing `Dektora/dekspec` repo **stays private** as the source of truth; the self-spec (`dekspec/`), tests, and internal docs are never mirrored. **Engine** installs anonymously via `pipx install "git+https://github.com/Dektora/dekspec-public.git@vX.Y.Z"` — pip builds the wheel from the mirrored tagged source, so every published tag is inherently installable (this dissolves the #73 tag-without-artifact problem at the root). **Plugin** installs anonymously via the existing `git-subdir` marketplace source pointed at the mirror (`claude plugin marketplace add Dektora/dekspec-public`). A release-time **mirror-sync** job in the private repo's `release.yml` pushes the curated subset (a fresh-tree push from `scripts/mirror-include.txt`, no private history) to the mirror, tagged to match the release; it is guarded on the `DEKSPEC_PUBLIC_MIRROR_TOKEN` secret and skips cleanly when absent.

**Retired:** the Cloudsmith index dependency, `resolve_latest_version` + the configurable-index resolver (INT-134), and the `release.yml` Cloudsmith publish job. `dekspec library sync` (INT-135) and the `library` namespace (INT-136) are unchanged. ADR-034 supersedes ADR-002 (proprietary git-URL distribution), ADR-009 (Cloudsmith vendoring/rsync drift), and ADR-031 (Cloudsmith latest-resolution); it partially retires INT-134 (the resolver dies; the wheel↔plugin bootstrap guidance survives, reframed for the mirror).

## [v0.107.0] — 2026-06-01

### Changed — Split `dekspec repo upgrade`: standard-tools acquisition + reconcile-only `dekspec library sync` (INT-135, ADR-032)

The conflated `dekspec repo upgrade` verb is decomposed by responsibility. **Acquisition** (installing the wheel + the Claude plugin) now delegates to standard tooling: `pip install dekspec` / `pipx install dekspec --index-url …` for the engine, `claude plugin update dekspec@dekspec` for the plugin. The engine keeps only a **reconcile-only** verb, the new **`dekspec library sync`**: run after the wheel is installed, it reconciles the consumer repo to the installed `dekspec.__version__` — vendoring (sourced from the installed wheel via `dekspec resource`, **not a git clone**), artifact/IR migration (the existing `dekspec migrate`, called as a sub-step), the breaking-release CHANGELOG guard, and the drift report — and is **idempotent** (no network, no pip, no plugin shelling, no version resolution). `scripts/install.sh` remains the one-command path, re-layered to `resolve → pipx install → dekspec library sync → claude plugin update` (plugin last; the end-to-end outcome is unchanged).

**Deprecation:** `dekspec repo upgrade` remains as a **deprecation alias** for one transition release — it prints a notice pointing at the standard tools + `dekspec library sync`, performs no acquisition, and forwards to the reconcile path. The `--no-install` / `--no-plugin` / `--engine-only` flags are removed. Scripted callers should migrate to the standard acquisition flow + `dekspec library sync`; the alias is slated for removal next minor. (The `repo` → `library` namespace migration of the other verbs is tracked separately.)

## [v0.106.0] — 2026-06-01

### Added — Cloudsmith latest-resolution + wheel↔plugin mutual bootstrap (INT-134, ADR-031)

`dekspec repo upgrade` and `scripts/install.sh` now resolve "latest" (no version arg) from the **configured Python simple-index** — the artifact channel — instead of the GitHub `/tags` source channel (ADR-031). The index URL is **not hardcoded**: precedence is `.dekspec/config.yaml` `index_url` > `PIP_INDEX_URL` / `PIP_EXTRA_INDEX_URL` > the Cloudsmith public-read default. Selection is over published wheel filenames (highest PEP 440 final release; prereleases excluded), so a git tag with no published wheel — e.g. a retained failed-release marker like `v0.101.0` — is never selectable as "latest". GitHub `/tags` is now an explicit `dekspec repo upgrade --source github` opt-in; the vendored-markdown git checkout step is unchanged. A new `index_url` field is allowed in the `.dekspec` config schema. **Mutual bootstrap:** the plugin's new SessionStart hook posts the `pipx install dekspec --index-url …` line (no version pin → latest) when the engine CLI is absent/stale, and `dekspec doctor` + `repo upgrade` now print `claude plugin install/update dekspec@dekspec` — each package surfaces the install/upgrade path to the other. Closes #73.

### Changed — Creation modes hard-default to provisional incubation (INT-133, ADR-030)

`/write-intent` and `/write-mission` **Creation modes now default to provisional incubation** (`dekspec/provisional/<slug>/`, no canonical id allocated, canonical graph untouched). Canonical-direct authoring requires an explicit `--canonical` opt-out. The provisional-vs-canonical routing is decided by a new deterministic `dekspec repo author-target --kind <K> [--canonical]` CLI verb that both skills call (one unit-testable source of truth). Supersedes the slice of INT-128's `/write-mission` §1a.0 ask→route commitment prompt (INT-128 stays LOCKED; its `T-MISSION-CANONICAL-WITHOUT-CHILD` audit rule and operating-guide section remain valid). The operating-guide §Provisional vs. Canonical section is updated to the hard default.

### Fixed — `find_beads_for_ib` accepts Intent paths (ds-frua)

`find_beads_for_ib.py` only parsed `IB-NNN` tokens, so the `--decompose` single-WS-fan-in direct-bead path (`/write-beads <Intent-path>`) errored `could not parse an IB-NNN id`. The token regex now matches `(?:IB|INT)-NNN`, unblocking direct-bead decomposition for no-WS Intents. (Subsumes ds-x6qv.)

## [v0.105.0] — 2026-06-01

### Added — No-IB pre-implementation review gate (INT-132)

Closes the no-IB `REVIEW_IB` coverage gap: the direct-bead decompose shortcut (WS-fan-in=0, no Implementation Brief) previously produced no IB, so the math-olympiad pre-implementation review never fired — such Intents reached coding with no adversarial review of their spec packet or bead decomposition. `spec-intent` now runs a synchronous **no-IB review gate** (Phase 3b): on the direct-bead path it assembles an `intent_spec_packet` slice (Intent body + parent WS acceptance + source-AE bounded contexts + glossary + bead decomposition) and runs it through the existing INT-105 orchestration shell with the REVIEW_IB lens pack before `ACCEPTED → IMPLEMENTING`; a NO-GO holds the Intent at ACCEPTED. The scoring engine is reused unchanged (RECOMMEND-only, ADR-026). IB-bearing Intents are unaffected (already covered via `/write-ibs --accept → REVIEW_IB`, INT-122).

### Changed — operating guide + AE-006 catalog (docs)

`docs/dekspec-operating-guide.md` §The Workflow documents the conductor + Intent-granular phase-executor trio and an Intent-initiated end-to-end flow (v1.3.0). AE-006 (Skills Library) catalog refreshed to enumerate the trio, the conductor, and the review/recovery skills.

### Added — Intent-granular phase-executor trio + orchestrate-intent conductor (MSN-018)

`/dekspec:orchestrate-intent` becomes a thin **top-level conductor** that owns sequencing + lock/propagation and delegates each lifecycle phase to a fresh-context, independently-launchable, Intent-granular phase-executor. Two new executors join the existing `/exec-coding-session`:

- **`/dekspec:spec-intent <intent>`** (INT-130) — specification phase-executor: drives an Intent DRAFT → ready-for-coding by sequencing `/write-intent --analyze`/`--accept`(engineer-gated)/`--decompose` + the `write-*` authoring skills; stops at the coding boundary.
- **`/dekspec:land-intent <intent>`** (INT-129) — review-and-land phase-executor: drives every IB-aggregate PR through `review-pr` + the `REVIEW_PR_FAIL` grep-loop to a terminal verdict and presents each squash-merge for explicit operator confirmation. Never auto-merges (ADR-026 RECOMMEND-only; unattended merge-on-GO stays gated on the INT-117 calibration corpus).
- **`/dekspec:orchestrate-intent` refactor** (INT-131) — Step 2 is now a 4-gate conductor (Specification → spec-intent, Implement → exec-coding-session, Land → land-intent, Lock → `/write-intent --lock`); the inline spec-driving body is removed (delegated to spec-intent) and a real land gate replaces the prior assume-already-merged step. `--auto` walks the same delegated sequence (ADR-021 preserved). Behavior-equivalent (same transitions, delegated not inline).

Delegation is structural: the coding executor and the review pipeline depend on context isolation (ADR-026), which an inline conductor body would defeat. Both new skills carry the canonical T-SKILL frontmatter (utility class) + slash-command wrappers + the ds-gxbg craft blocks.

### Added — Skill-craft upgrades across the authoring skill family (ds-gxbg)

Four authoring-DX blocks added to all 14 `write-*` skills plus `exec-coding-session` and `archeology` (16 SKILL.md files): (1) a copy-paste **Starter Prompt** — a drop-in `prompt`-fenced operator invocation for the skill's most common path, not just process prose; (2) a checkbox **Verification Checklist** — terminal-state binary self-audit symmetric with each skill's workflow steps (gameable-resistant done-criteria); (3) a **Common Pitfalls** stanza — skill-specific anti-patterns (negative space); (4) a `related_skills` **frontmatter** field making the implicit lifecycle graph (e.g. `write-ws → write-ibs → write-beads → write-tests → exec-coding-session`) machine-navigable. Skill-body/template authoring polish only — no schema or IR change; `related_skills` is additive frontmatter the `T-SKILL-FRONTMATTER-NORMAL` audit does not gate on.

### Added — Supply-chain hygiene advisory: 14-day new-package rule + breach-scan (ds-tygt)

New audit advisory `T-SUPPLY-CHAIN-NEW-DEPENDENCY` (P3) in the security-profile audit family. Encodes the "14-day new-package rule": flag a dependency pinned to a version published fewer than 14 days ago (the prime window for typosquat / account-takeover supply-chain attacks). It is a sibling to the SP-IR-pure `T-SEC-*` family — gated on the presence of at least one Security Profile, but consults `graph.repo_root`, so it is deliberately not named `T-SEC-*` (the ADR-011 isolation invariant forbids `T-SEC-*` bodies from reading repo state).

Publish dates resolve **offline** from a cache the repo maintains at `.dekspec/package-publish-dates.json` (a JSON map of `"name==version"` → `"YYYY-MM-DD"`). Absent / malformed cache, or an unparseable / future date → no finding ("metadata not resolvable" is a clean state, never an advisory). The audit makes **no network call**; a registry-backed resolver that populates the cache is an explicit downstream opt-in, kept out of the deterministic audit path.

The breach-scan recommendation (when a breach trends for a package, scan local projects for that package/version and pin away) plus the cache convention are documented in `templates/security-profile-template.md` (§Supply Chain) and the `write-sp` skill's Teaching Mode. Advisory-only — does not hard-fail the audit; dogfood-safe (no cache in this repo → no findings; `audit doctor` stays ADVISORY).

### Added — Reuse Inventory IB section + linter rule (ds-0a7w, Reuse Firewall upstream half)

The IB template (`templates/implementation-brief-template.md`) gains a `## Reuse Inventory` section: the Specifier names existing capabilities the implementer must reuse ("use X, do not reimplement"). This is the durable, compiled reuse-intent contract that travels with every brief; the live "what code exists" truth and the active gate live downstream at build time (capability index + Code Reviewer calibrated gate), not in DekSpec.

The upstream IB linter (`dekspec check lint-ib`, INT-074 machinery) now enforces the section's presence on **code-bearing** IBs — any brief with at least one concrete (non-placeholder) row in `## Files to Modify`. Two new advisory rules (P2): `REUSE_INVENTORY_MISSING` (section absent) and `REUSE_INVENTORY_EMPTY` (present but only placeholder rows). Non-code-bearing briefs are unaffected; net-new work declares a single `| none | — | net-new capability |` row.

Coordinates-with the DekFactory Reuse Firewall ADR (df-mmvv). Consumed by DekFactory via `dekspec upgrade`.

## [v0.104.1] — 2026-05-30

Corpus cleanup follow-up to v0.104.0: MSN-010 (multi-engineer coordination) demoted to provisional + 12 canonical cross-references scrubbed. T-MISSION-CANONICAL-WITHOUT-CHILD (INT-128, shipped in v0.104.0) no longer fires on the live audit. Dogfoods the new guardrail end-to-end.

### Changed — MSN-010 demoted to provisional

MSN-010 was misclassified canonical at authoring 2026-05-21 — should have been provisional per MSN-014's substrate. The scope was speculative (multi-engineer coordination work in a solo-operator repo with no concurrent-engineer pressure). T-MISSION-CANONICAL-WITHOUT-CHILD caught it.

Demotion (not kill, not eradication — proportional middle path):

- `git mv dekspec/missions/MSN-010-multi-engineer-coordination.md → dekspec/provisional/multi-engineer-coordination/MSN-provisional-multi-engineer-coordination.md` per MSN-014's `<KIND>-provisional-<slug>` convention.
- Mission ID renamed `MSN-010` → `MSN-provisional-multi-engineer-coordination`.
- Status reset KILLED → TODO (the prior kill was wrong off-ramp; work isn't abandoned, just not-canonical-yet).
- mission-index.md row removed entirely (provisional artifacts are invisible to canonical indices per MSN-014).
- 12 canonical cross-references scrubbed across 7 LOCKED artifacts (AE-003, INT-030, INT-059, INT-086, INT-094, INT-098, ADR-024) via unlock→edit→relock cycles, 3 ACCEPTED artifacts (AE-005, AE-006, system-vision), 1 active impl-brief (IB-118), and mission-index.
- INT-094 branch-name token `int/MSN-010-fix-constant-embedding-import-shape` left intact (literal historical incident, not a Mission reference).
- INT-086 (the analysis Intent that builds reasoning ON TOP of MSN-010) edited to reference "the multi-engineer-coordination provisional" instead of the canonical name; load-bearing narrative preserved.

The substantive scope (divergence detection, vision-coherence audit, deconfliction skill, coherence CLI verb group, audit rules for cycle + drift, engineer-attribution cascade) stays intact for future graduation if real concurrent-engineer pressure surfaces.

### Validation

- T-MISSION-CANONICAL-WITHOUT-CHILD (INT-128, registered in `v1` profile in v0.104.0) no longer fires on MSN-010 because the Mission no longer lives under canonical `dekspec/missions/`. End-to-end dogfood of the guardrail rule + the demotion path.
- `dekspec audit linkage --at . --min-severity P1`: clean.
- `dekspec audit relink`: 0 dangling forward references.
- Full suite 2786 passed (no test changes — pure corpus cleanup).

### Lesson captured

Three off-ramps for canonical Missions that should have been provisional:

| Off-ramp | When | Cost |
|---|---|---|
| **Kill** (status KILLED, file stays canonical) | Work is abandoned; preserve cross-refs as history | ~5 min, 1-2 commits |
| **Demote to provisional** (this v0.104.1 path) | Work isn't abandoned; just speculative + premature canonical | ~30 min, 12+ artifact unlock cycles, 1 commit |
| **Eradicate** (file deleted, all refs scrubbed, no artifact survives) | Work AND its name should not exist | ~30 min, 12+ artifact unlock cycles, multiple commits (MSN-011 case in v0.104.0) |

Demote is the proportional middle path between kill (over-commits to abandonment) and eradicate (over-commits to history-rewrite). Documented as a follow-up in the next operating-guide revision.

## [v0.104.0] — 2026-05-30

Provisional-promotion guardrails (INT-128) + MSN-011 eradication + 3 stale ADR closeouts.

### Added — Provisional promotion guardrails (INT-128 / ds-provisional-promotion-guardrails)

- **`T-MISSION-CANONICAL-WITHOUT-CHILD` advisory P3 audit rule** — fires when a Mission file under canonical `dekspec/missions/` has status TODO + Created ≥7 days ago + zero child Intents declaring it via their `Mission:` field. Skips provisional/, non-TODO statuses, missions with children. Registered in `v1` profile. Surfaces drift in `dekspec audit doctor` without gating. Already firing on MSN-010 in live audit output as the validation case.
- **`/dekspec:write-mission` Creation Mode §1a.0 commitment prompt** — before dispatching the mission-author subagent, asks the engineer: "Will the First Intent's body be authored within this same session?". `no` routes through the `--provisional <slug>` codepath. Flag becomes implicit-from-answer instead of opt-in-from-knowledge.
- **`docs/dekspec-operating-guide.md` §Provisional vs. Canonical** section — decision rule ("if you cannot name the First Intent's body NOW, the Mission is provisional"), MSN-011 eradication cost data (12 commits / ~30 min / 5 LOCKED-artifact unlock cycles vs. `rm -rf` one-liner), substrate inventory, audit backstop description, decision tree.
- 7 contract assertions TDD-first per ADR-029.

### Removed — MSN-011 (Builder Integration Protocol umbrella)

Mission file eradicated 2026-05-30 — never activated, premature canonical promotion. Authored 2026-05-21 with intent to fan out IC-005's 7 forward-referenced sub-IC capability surfaces, but no concrete near-term builder consumer surfaced and YAGNI made the 9-sub-IC pinning premature.

- `dekspec/missions/MSN-011-builder-integration-protocol.md` deleted.
- `mission-index.md` row removed entirely (not archived).
- 11 cross-references scrubbed across 5 LOCKED artifacts (INT-028 / INT-030 / INT-059 / INT-098 / IC-005), 3 ACCEPTED Architecture Elements (AE-001 / AE-005 / AE-006), 2 Missions (MSN-010 / MSN-012), and the operating-guide narrative. LOCKED artifacts went through unlock → edit → relock cycles per the CLAUDE.md guardrail. Audit trail preserved in each touched artifact's Amendment Log.
- IC-005 the umbrella stays untouched: 7 capabilities remain forward-referenced for a future Builder Integration Protocol Mission to pick up if real builder pressure surfaces. INT-028's IC-005 cross-references remain valid.
- Companion research surfaced as `ds-provisional-promotion-guardrails-i0m8` and shipped via INT-128.

### Changed — Stale ADR cleanup

Three ADRs that had been PROPOSED/ACCEPTED for 5-12 days walked to LOCKED:

- **ADR-014** (AE precedence over Constitution) — PROPOSED 2026-05-18 → LOCKED 2026-05-30.
- **ADR-019** (in-flight exemptions for L7b/L8 linkage rules) — PROPOSED 2026-05-21 → LOCKED 2026-05-30.
- **ADR-021** (`/orchestrate-intent --auto` safety contract) — ACCEPTED 2026-05-25 → LOCKED 2026-05-30.

Pre-lock audit clean; zero downstream contradictions; all 3 govern work that has since shipped.

### Documentation — Research notes

Two research surveys filed at `docs/workspace/` (companions to INT-128, no implementation commitment):

- **`cc_dark-factory-workflow-simplification-survey.md`** — canonical workflow trace (18+ status flips, 10+ skill invocations per Intent post-MSN-017), 7 spec-discipline invariants any simplification must preserve, 5 highest-leverage simplifications with go/no-go per profile, `dark-factory` operating profile sketch alongside lite/team/full (INT-024 substrate). Closes `ds-simplify-workflow-state-machine-dark-factory-0fof`.
- **`cc_folder-based-state-tracking-research.md`** — hypothesis that an artifact's directory IS the workflow status (`git mv` = transition, `ls` = queue browser, `git log --follow` = lifecycle viewer); falsifying counter-hypotheses; recommendation PROBE-not-commit (convert IBs first per INT-072 precedent). Closes `ds-folder-based-state-workflow-tracking-4szy`.
- **`cc_provisional-promotion-guardrails-survey.md`** — substrate inventory, root-cause analysis, proposed guardrails (§4.1/4.2/4.3 folded into INT-128). Closes `ds-provisional-promotion-guardrails-i0m8`.

### Audit profile (`v1.yaml`)

- New rule registered: `T-MISSION-CANONICAL-WITHOUT-CHILD`.

### Tests

- 7 new tests (2779 → 2786). All TDD-first per ADR-029.

## [v0.103.0] — 2026-05-30

MSN-017 two-tier non-sycophantic review pipeline LANDED (23 child Intents LOCKED) + Constitution §Class Lanes structured IR + failure-class aggregator + audit-loop discipline + plugin-downgrade detection.

### Added — MSN-017 review pipeline

- **`/dekspec:review-ib`** skill (INT-106) + 13-lens REVIEW_IB pack: scope-creep, acceptance-falsifiability, test-plan-coverage, dependency-readiness, source-spec-fidelity, rollout-risk-plan, ambiguity-audit, constraint-completeness, glossary-discipline, bead-coverage, bead-granularity, bead-dependency-graph, bead-to-ib-fidelity. Pre-implementation review of IB spec packet + bead decomposition.
- **`/dekspec:review-pr`** skill (INT-107) + 9-lens REVIEW_PR pack: claude-md-compliance, done-when-satisfied, diff-scope-vs-ib, bug-scan, test-plan-execution, audit-rule-preflight, doc-changelog-entry, spec-mode-discipline, git-blame-prior-pr. Post-implementation review of IB-aggregate PR diff.
- **`plugins/dekspec/skills/_lib/review-orchestration.md`** (INT-105) — shared math-olympiad orchestration shell. Context-isolated lens runner + 0-100 confidence rubric (80-threshold surface) + asymmetric voting (single lens veto = NO-GO) + calibrated INSUFFICIENT_EVIDENCE abstention + audit-doctor cache reuse.
- **Python action-handler registry** (`tooling/dekspec/action_handlers/`, INT-121) — `register(state, handler)` / `dispatch(fail_state, context) → HandlerResult`. Idempotent registration; `ConflictingHandlerError` on different-handler re-register; `UnregisteredFailStateError` on dispatch of unregistered state. Mode-aware (RECOMMEND / MIXED / AUTO).
- **3 concrete handlers** wired against the 3 FAIL states: `review_ib_fail.py` (INT-113), `testfail.py` (INT-114), `review_pr_fail.py` (INT-115). Each invokes the registered remediation skill + signals operator (RECOMMEND) or auto-advances (AUTO).
- **`dekspec.review`** sub-package — `db.py` (SQLite flywheel `reviews.db` with 10-column schema; INT-109), `calibration.py` (per-lens silver/gold threshold proposal with configurable FPR target; INT-117), `config.py` (three-mode resolver with thresholds-absent revert; INT-118).
- **`dekspec review` CLI verb family** (INT-116): `status <IB>`, `history <IB>`, `calibrate`, `trigger {review-ib|review-pr} <ref>`.
- **TESTFAIL un-retirement at IB level** (ADR-027 / INT-110) — re-introduced as first-class IB status with `/exec-coding-session --retry` action handler. Intent-level retirement (2026-05-25 E3) stands; IB-level re-introduction is new.
- **State-machine wiring**: `plugins/dekspec/skills/write-ibs/SKILL.md` — full transition matrix (PROPOSED→ACCEPTED→REVIEW_IB→IMPLEMENTING→TESTPASS→REVIEW_PR→MERGED + FAIL branches). `plugins/dekspec/commands/run-coding-session.md` — IMPLEMENTING ↔ TESTPASS/TESTFAIL transitions per INT-123.

### Added — Constitution §Class Lanes (INT-125 / ds-zhhk)

- **`class_lanes` typed array** on Constitution IR with 11 required fields per row: `intent_type`, `risk_tier`, `lane` (enum `dark|canary|gated`), `budget_cap_tokens`, `budget_cap_dollars`, `max_attempts_per_attempt`, `max_attempts_per_bead`, `promotion_threshold_clean_runs`, `demotion_threshold_reverts`, `effective_model_snapshot`, `effective_corpus_volume`. Last two fields close the Fowler R3 + Wu R2 model-drift gap.
- **`amendment_log` promoted to first-class IR object** (typed array of `{date, type, change, author}` rows). Closes the Nygard MUST-NOT on prose-only amendment logs.
- **3 new audit rules** in `v1` profile: `T-CONST-CLASS-LANE-COVERAGE-UNIQUE` (every `(intent_type, risk_tier)` tuple resolves to exactly one row), `T-CONST-CLASS-LANE-THRESHOLDS-WELL-FORMED` (numeric sanity), `L-CONST-CLASS-LANE-INTENT-EXISTS` (Intent's tuple must match a row).
- **Constitution template + `/dekspec:write-constitution` skill** updated: §Class Lanes is writeable; `--amend --editorial` is the path for class promotion/demotion.

### Added — Failure-class aggregator (INT-126 / ds-99ko)

- **`dekspec audit failure-classes [--at] [--window N] [--by class|type|risk-tier] [--format md|json] [--detect-reverts]`** — read-only walk over `.beads/issues.jsonl`, groups beads carrying `failure-class:*` labels, cross-references each bead's `external_ref` (bead → Intent → IB), optional `git log --grep` revert SHA lookup.
- **§Post-mortem ritual** section in `docs/dekspec-operating-guide.md` — 5-step engineer flow (revert → tag bead → aggregator → decide → `/dekspec:write-constitution --amend --editorial`) + class-name conventions.

### Added — Audit-loop discipline (INT-127 / ds-bqhf)

- **`dekspec audit doctor --loop [--pass-cap N] [--scope artifact|corpus] [--axis T,L]`** — mechanical-fixed-point loop with 4 termination conditions: quiescence, semantic-only stall, oscillation, pass-cap. Default `--pass-cap 5` (placeholder per cross-plan SOFT dep on DekFactory Phase 0 archeology). Strict additive — bare `audit doctor` unchanged.
- **Semantic-identity oscillation detection** via `FindingId(rule, artifact, field)` — NOT finding-hash, per Nygard R1 (line numbers shift across passes).
- **§Audit-loop discipline** section in `docs/dekspec-operating-guide.md` — pseudocode (illustration only) + property-based convergence spec (the actual contract) + cadence-by-trigger matrix (pre-commit / CI / nightly / pre-release / post-incident / engineer-initiated) + B-axis + P-axis placeholder note.

### Added — Outcome-test + strong-TDD discipline (INT-112 / INT-119 / INT-120 / ADR-029)

- **`outcome_verification` IR field + `outcome_verification_grandfathered` flag** on Intent schema (INT-112). Lazy-grandfather convention for pre-existing Intents (no migration script).
- **`## Outcome Verification` template section** with strong-TDD prose: outcome test landed first (red), implementation makes it green, no other test files modified.
- **`T-VERIFICATION-OUTCOME` advisory P2 audit rule** (INT-119) — fires when an Intent at status ≥ ACCEPTED lacks `outcome_verification` AND is not grandfathered.
- **REVIEW_IB outcome-test discipline lens** (INT-120) wires the TDD check via git-blame into the math-olympiad orchestration.
- **`/write-beads` acceptance-criteria convention** + **CLAUDE.md §Verification Predicate Library** section pinning outcome-cmd alongside `pytest -q`.

### Added — OVERSIZED peel-off policy (INT-111 / ADR-028)

- Default OVERSIZED Automated Splitting flow flips from SUPERSEDE+N to PEEL-OFF (narrow parent in-place + scaffold N-1 siblings). SUPERSEDE reserved for LOCKED override / deprecation. `/write-intent` + `/orchestrate-intent` SKILL.md prose updated with ADR-028 backpointers.

### Added — Supporting ADRs (all LOCKED 2026-05-29 / 2026-05-30)

- **ADR-026** — Adopt math-olympiad orchestration as DekSpec's review standard.
- **ADR-027** — Reverse the 2026-05-25 TESTFAIL retirement at IB level; engineered round-trip via INT-114 handler.
- **ADR-028** — Default OVERSIZED handling to PEEL-OFF; reserve SUPERSEDE for LOCKED override.
- **ADR-029** — Require per-Intent outcome test + strong-TDD timing.

### Fixed

- **`dekspec repo upgrade`** silent plugin downgrade (ds-upgrade-plugin-marketplace-lags-git-tags-nipi). `_snapshot_plugin_version()` + `_detect_plugin_downgrade(pre, post)` helpers snapshot before + after `claude plugin update`; warn loudly with exact `pipx install --force git+...@vX.Y.Z` + `claude plugin install` remediation when downgrade detected.

### Audit profile (`v1.yaml`)

- New rules registered: `T-VERIFICATION-OUTCOME`, `T-CONST-CLASS-LANE-COVERAGE-UNIQUE`, `T-CONST-CLASS-LANE-THRESHOLDS-WELL-FORMED`, `L-CONST-CLASS-LANE-INTENT-EXISTS`.

### Domain glossary

- (No new entries — existing Status-Maturity Coherence + Security Profile categories cover the round.)

### Tests

- 56 new tests across the round (2723 → 2779). All implementations followed ADR-029 strong-TDD: outcome test landed first (red), implementation made it green, no other test files modified.

## [v0.102.0] — 2026-05-29

Two IR schema bumps + new audit rule + Path A methodology shift + peel-off / convert-to-Mission policy formalization + corpus cleanup of false-positive SUPERSEDED Intents.

### IR schema bumps (consumers MUST run `dekspec repo migrate-artifacts` after upgrade)

- **Implementation Brief IR `0.2.0 → 0.3.0`** (INT-102): adds 5 new statuses to the IB status enum — `REVIEW_IB`, `REVIEW_IB_FAIL`, `REVIEW_PR`, `REVIEW_PR_FAIL`, `TESTFAIL` — for the two-tier review pipeline under MSN-017. Adds optional `review_grandfathered: bool` field (default `false`). Ships markdown migration `tooling/dekspec/migrations/ib_review_statuses.py` that stamps existing ACCEPTED / TESTPASS IBs with `review_grandfathered: true` in a single idempotent pass.

- **Intent IR `0.2.0 → 0.3.0`** (INT-103): adds optional `beads_before_accept: bool` field (default `true`) to the Intent IR. Parser gains `_extract_intent_beads_before_accept` (mirrors the `_extract_intent_risk_tier` pattern). Ships markdown migration `tooling/dekspec/migrations/intent_beads_before_accept.py` that stamps every pre-Path-A Intent with `beads_before_accept: false` (87 Intents grandfathered).

### Path A methodology shift (ADR-025-governed)

- **ADR-025 LOCKED** — _Standardize bead = commit-cluster on IB branch; IB = one PR to main_. Supersedes the operating-guide's "one bead = one PR" doctrine. Per-bead PRs to main are no longer part of the skill surface; beads land as commit-clusters on the IB branch, and the IB opens a single PR to main carrying the aggregate diff.

- **`/write-intent --accept` Step 4.0** (INT-104): the accept-mode subagent invokes `/write-beads` BEFORE the `artifact_ops.py transition PROPOSED → ACCEPTED` call for any Intent with `beads_before_accept: true`. Grandfathered Intents (`beads_before_accept: false`) skip the invocation. The Plan phase of EPCV now happens at PROPOSED → ACCEPTED, not at `--decompose`.

- **`L16-INT-BEADS-BEFORE-ACCEPT` audit rule** (INT-104) — `P2` advisory. Fires when an Intent at status ≥ ACCEPTED has `beads_before_accept: true` and zero beads under it in `.beads/issues.jsonl`. Registered in `tooling/dekspec/fidelity_audit/profiles/v1.yaml`, `lite.yaml`, `team.yaml`. (L12-L15 were all taken; L16 was the next-free identifier.)

- **`docs/dekspec-operating-guide.md` doctrine update** — Decision-#19 EPCV section rewritten to reflect beads-before-accept ordering. Four bead-PR mapping hits at L134 / L314 / L732 / L830 replaced per ADR-025 ("bead = commit-cluster on IB branch; IB = one PR to main").

### Peel-off and Convert-to-Mission policy (methodology default change)

`SUPERSEDED` now means strictly "this artifact was overridden or deprecated" and is reserved for LOCKED Intents that shipped. Provisional state (DRAFT / OVERSIZED / PROPOSED / ACCEPTED / IMPLEMENTING — never shipped) resolves OVERSIZED via one of two non-SUPERSEDE paths:

- **PEEL-OFF** (default when the OVERSIZED Intent has a natural core slice): narrow the parent in place + scaffold N-1 sibling Intents under the same Mission. Parent keeps its identity, slot, history.
- **CONVERT-TO-MISSION** (default when the OVERSIZED Intent's scope is an umbrella over N capability surfaces): extract the Intent's substance into a new Mission's near-immutable section, scaffold child Intents, **delete the OVERSIZED Intent file**, no Archive row, no SUPERSEDED status.

SUPERSEDE+N (mark parent SUPERSEDED + scaffold N brand-new children) is no longer the default for OVERSIZED handling.

- New shared decision tree at `plugins/dekspec/skills/_lib/oversized_splitting.md` (single source of truth across `/write-intent`, `/orchestrate-intent`, and `/write-mission`).
- Policy is explicitly stated in `/write-intent` Rules block and `/write-mission` Rules block — operators do not need a memory note.
- `/write-mission` Creation Mode gains a `from-oversized: <INT-NNN-path>` Decision Gate entry. Step 1a.1 handler extracts the OVERSIZED Intent's substance into the Mission's near-immutable section (Outcome, Mission Verification, Out-of-scope, Flag strategy, Rollback plan, Kill criteria, Autonomy ceiling, First Intent), scaffolds child Intents per a per-section sourcing table (Step 3b), appends rows to `intent-index.md` Active queue + the Mission's Intent queue (live section), deletes the OVERSIZED Intent file, and runs `dekspec audit relink`. Branch creation is deferred to `--analyze` / cluster-worktree time.

### Corpus cleanup

Nine false-positive SUPERSEDED Intent shells deleted (provisional-state orphans from the old SUPERSEDE+N flow). None shipped; all had their substance absorbed by parent Missions:

- INT-001 → MSN-001 (Constitution L0)
- INT-005 → MSN-002 (session lifecycle)
- INT-006 → MSN-006 (lite profile)
- INT-007 → MSN-003 (Security Profile)
- INT-025 → INT-033 (rejected by ADR-015; INT-033 shipped the chosen approach)
- INT-027 → MSN-011 (Builder Integration Protocol)
- INT-029 → MSN-010 (multi-engineer coordination)
- INT-031 → MSN-005 (relink + retire L6)
- INT-100 → MSN-016 (excise executor concept)

Plus IB-039 (orphan DRAFT IB downstream of the deleted INT-025). Bulk prose sweep across 83 surviving files normalized references to the absorbing Missions (or to INT-033 for the INT-025 case). Intent index Archive shrank from 99 rows to 84 rows.

### Retroactive renumbering

INT-104 / INT-105 (the original SUPERSEDE+N split of the OVERSIZED Path A Intent) renumbered to INT-103 / INT-104 per the new peel-off policy applied retroactively. The original INT-103 SUPERSEDED shell was deleted; the new INT-103 (was INT-104) inherits the slot.

### Audit + housekeeping

- MSN-017 Intent queue format normalized: stripped markdown links from the first cell to bare `INT-NNN` IDs (matching every other Mission's convention). Resolves 3 P2 `L8-INT-MSN-MIRROR` findings; `dekspec doctor` returns ADVISORY (P3-only) on the library's self-spec.

## [v0.101.1] — 2026-05-29

CI plumbing patch on top of v0.101.0. The v0.101.0 tag was pushed but its `release.yml` pre-release pytest job failed with 83 init-flow test failures (all `assert 2 == 0` — the new `_init_dep_precheck` returning exit 2 because `br` was not on PATH). The same install-step that landed in `.github/workflows/ci.yml` during the v0.101.0 cycle did NOT get mirrored into `.github/workflows/release.yml`; this release closes that gap. No DekSpec code changes — pure CI plumbing.

### Fixed

- **`.github/workflows/release.yml` installs `br` (beads-rust) v0.2.11 before pytest**, mirroring the step that landed in `ci.yml` during the v0.101.0 cycle. Without it the new `dekspec repo init` host-dependency precheck (added in v0.101.0) hard-fails every init-flow test in the release-gate pytest run, blocking Cloudsmith publish. The v0.101.0 tag is retained as a failed-release marker in tag history; v0.101.1 is the first artifact that actually reaches Cloudsmith.

## [v0.101.0] — 2026-05-29

Operator-quality patch: hard-required dependency precheck on `dekspec repo init`, a new LLM-driven `/dekspec:send-issue` slash command for filing classified GitHub issues against this repo, and the executed deprecation of the v0.91.0 install-shim. Methodology-side: MSN-017 (non-sycophantic two-tier review pipeline) seeded as a TODO Mission; INT-1000 (lifecycle correctness hardening) killed as an out-of-range orphan.

### Added

- **`dekspec repo init` host-dependency precheck**. Hard-fails with exit code 2 + a checklist on stderr if either `git` or `br` (beads-rust) is missing from PATH. No override flag, no environment escape hatch: DekSpec's authoring + audit pipeline depends on git, and its coding loop + the `T-BEAD-FAILURE-CLASS-VALID` audit rule depend on `br` end-to-end. Fires on both the canonical `dekspec repo init` and the deprecated `dekspec init` alias. Implementation: `tooling/dekspec/cli.py::_init_dep_precheck`; coverage in `tests/test_cli_init_dep_precheck.py` (6 cases: happy path, git-missing, br-missing, both-missing, env-var-ignored, scaffolding-aborted-before-mkdir).
- **`br` identity check** inside the precheck — `_is_beads_rust_br` runs `br --help` and matches the substring `beads` to reject the brotli `br` binary (same name, different tool) that ships on many Linux distros. CI bug found in PR #52; tightened in commit 8f22962.
- **`/dekspec:send-issue` slash command** in the dekspec Claude Code plugin. LLM-driven GitHub issue filer that classifies the operator's report into one of five categories (`bug` / `feature` / `feedback` / `question` / `docs`), infers severity (S0–S3) + priority (P0–P3) from the context, runs a research phase (dupe-check via `gh search`, related-artifacts grep across Intents/AEs/ADRs/CHANGELOG, related-bead lookup via `br list`), drafts a structured issue body, and surfaces a preview/Send/Edit/Cancel gate via `AskUserQuestion` before `gh issue create` fires. Sources: `plugins/dekspec/commands/send-issue.md`; merged via PR #53.
- **CI install step for `br` (beads-rust)** at `.github/workflows/ci.yml` — pins to `Dicklesworthstone/beads_rust` v0.2.11, downloads the linux_amd64 tarball, installs to `/usr/local/bin/br` before pytest runs. Required by the new `dekspec repo init` precheck so the test suite's init-flow coverage doesn't fail on missing dep.

### Library self-spec

- **MSN-017 (TODO) — Land a non-sycophantic two-tier review pipeline with first-class failure states, action handlers, and flywheel-driven auto-mode graduation.** Mission seed only; child Intents queue still being authored. The locked design substrate (`reference_review_pipeline_design.md` in operator memory) covers REVIEW_IB + REVIEW_PR at the IB level, math-olympiad-style orchestration (context-isolated lens specialists + per-issue Haiku confidence scorer + per-lens veto thresholds + 0-100 rubric), Path A methodology shift (beads-before-accept), bead = commit-cluster on IB branch + IB = one PR to main, TESTFAIL re-introduction, three paired failure states, three-mode plumbing (RECOMMEND today, MIXED + AUTO future). First child INT-102 (IB IR status enum bump + grandfather migration) is in flight on a worktree branch — not in this release.

### Removed

- **`scripts/install-dekspec.sh`** is gone. The script has been a no-op deprecation shim since v0.91.0 (INT-097, self-contained wheel). The deferred-removal note inside the script is now executed: any remaining CI lines still invoking `bash scripts/install-dekspec.sh` will break with `No such file or directory`. Migrate to the recommended install path: `bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec/main/scripts/install.sh)` (single-command CLI + plugin) or `pip install dekspec==X.Y.Z` (CLI only). Skill bodies and historical Intents still mention the script as record of how onboarding used to work — they are not call sites.
- **Live `install-dekspec.sh` references** scrubbed from `CLAUDE.md` (repo overview), `README.md` (Quick start, Routine upgrade, Major upgrade), `plugins/dekspec/README.md` (architecture section), and `plugins/dekspec/commands/man.md` (overview-missing error message). LOCKED `dekspec/` self-spec artifacts and the auto-generated `AGENTS.md` aggregator were left untouched. The ten `/dekspec:write-*` skill bodies still carry the INT-097 advisory note ("if your install is pip-only (no `scripts/install-dekspec.sh` run)..."); those advisory notes remain factually correct (every install is now pip-only) and are queued for a separate sweep.
- **INT-1000 (Lifecycle correctness hardening)** killed as an out-of-range orphan Intent — the `1000` ID was an accidental placeholder that grew a real branch + two implemented beads (ds-6ety LifecycleStateError + terminal-state guards, ds-1yjb `dekspec lifecycle reap-stale` CLI + `scripts/check-stale-open-attempts.sh` wrapper) but never landed on main and never advanced past ACCEPTED. Local branch `int/INT-1000-lifecycle-hardening` deleted; remote never existed. Bead history preserved with comments noting close-reasons reference unreachable commits.

### Verification

- Version triad in sync (`__version__` = CHANGELOG[0] = 0.101.0).
- 2536+ tests pass; ruff clean; `dekspec audit doctor --at .` ADVISORY (P3 only; no regression).


## [v0.100.0] — 2026-05-28

Phase 1.B complete — DekSpec gains an open-enum + lint-on-boundary observability surface for Intent risk tiers + bead failure classes. Additive across schema + parser + audit + template + skill body. Closes umbrella ds-d0as + 7 sub-beads A–G. Originated in the dekfactory review synthesis (Phase 1.B); unblocks downstream dekfactory df-l910 (Phase 2.B schema-adoption) + df-c4in (Phase 2.G Verifier reads risk_tier).

### Added — Intent IR

- **`risk_tier`** optional property on Intent IR (open-enum string, no schema constraint). Schema at `tooling/dekspec/schemas/intent.schema.yaml`; parser hook `_extract_intent_risk_tier` reads the `## Risk Tier` markdown section. Recommended vocabulary (lint-on-boundary, not schema-enforced): `default | schema-migration | auth | billing | concurrency | data-residency | external-api-surface`. (sub-bead A / ds-gkhm)

### Added — Bead body convention

- **`failure_class:` + `failure_notes:`** optional markdown body lines for bead descriptions. No beads-rust schema change — convention-only, parsed via the new `tooling/dekspec/fidelity_audit/bead_body.py` module (functions: `extract_from_body`, `parse_bead_failure_class`, `parse_bead_failure_class_all`). Recommended `failure_class` vocabulary: `wrong-spec | correlated-AI-miss | production-only-failure | flaky-test-masked-bug | scope-creep-undetected | dependency-version-conflict | concurrency-race | other`. (sub-bead B / ds-g3gh)

### Added — Audit rules (warn-only P3 advisories)

- **`T-INT-RISK-TIER-VALID`** — walks Intent IRs, emits one P3 advisory per Intent whose `risk_tier` value is set AND outside the recommended vocabulary. Absent values produce no findings. Recommended-vocab constant `_INT_RECOMMENDED_RISK_TIERS` in `linkage.py`. (sub-bead C / ds-puvi)
- **`T-BEAD-FAILURE-CLASS-VALID`** — walks `.beads/issues.jsonl` via `parse_bead_failure_class`, emits one P3 advisory per bead whose `failure_class` is set AND outside the recommended vocabulary. Skipped silently when `.beads/issues.jsonl` is absent (consumer repos without bead tracker). Recommended-vocab constant `_BEAD_RECOMMENDED_FAILURE_CLASSES`. (sub-bead D / ds-27ld)

Both rules registered in the baseline `v1` audit profile at `tooling/dekspec/fidelity_audit/profiles/v1.yaml`.

### Added — Template + skill UX

- **`## Risk Tier` section** in `templates/intent-template.md` between `## Autonomy` and `## Branch`. Documents the open enum + custom-value tolerance + the audit-v2 lint-on-boundary contract + the field's complementary role to Autonomy and Intent type. (sub-bead E / ds-8mhg)
- **`/dekspec:write-intent --analyze` Step 1b prompt** in `plugins/dekspec/skills/write-intent/modes/analyze.md`. Surfaces a one-line prompt asking the engineer to pick a risk_tier when the section is empty; recommended-by-type defaults inline (bug / refactor / documentation → `default`; feature touching auth/billing/concurrency/data-residency → matching value). Open-enum: never blocks promotion. (sub-bead E / ds-8mhg)
- **`/dekspec:write-beads` SKILL body** in `plugins/dekspec/skills/write-beads/SKILL.md` gains an "Optional body lines — failure_class + failure_notes" sub-section under §Bead Format. 8-row vocabulary table with per-value when-to-use guidance; pointer to the canonical parser. (sub-bead F / ds-g7m2)

### Added — Methodology doc

- **Bead body conventions (Phase 1.B+)** sub-section under §16 of `docs/dekspec-methodology.md` documenting the `failure_class:` + `failure_notes:` body convention + the parser location. Pairs with the Intent IR risk_tier field — `risk_tier` flags blast radius pre-work; `failure_class` captures failure mode post-resolution.

### Engine internals

- Both audit rules use lazy imports (`bead_body` from `linkage.py`) to keep the dep arrow narrow.
- Parser changes are additive (no schema-required field); existing Intents continue to validate cleanly without `## Risk Tier`.

### Reverted

- **`tooling/dekspec/schemas/dekfactory-manifest.schema.yaml`** — schema was retired in MSN-016 (engine excision, commit cc6f5b9) and got accidentally re-added during the sub-bead E commit (c0c492d) via an unrelated `git add -A`. Deleted in commit f88f9ec to restore the post-MSN-016 state.

### Verification

- 2536 tests pass (was 2493 at v0.98.0 baseline; +43 tests across sub-beads A–D covering parser extraction, JSONL walk, regex-extraction edge cases, audit-rule absent/recommended/unknown paths).
- ruff clean.
- `dekspec audit doctor --at .` ADVISORY (P3 only; no regression — the new rules can't fire on the library's own dekspec/ tree because no Intent there carries a risk_tier yet and the library's `.beads/issues.jsonl` carries no `failure_class:` lines).
- Version triad in sync (`__version__` = CHANGELOG[0] = 0.100.0).

### Downstream

- DekFactory df-l910 (Phase 2.B schema adoption) + df-c4in (Phase 2.G Verifier reads risk_tier) unblock with this release.

## [v0.99.0] — 2026-05-28

Operator-facing overview surface + Phase 1.B bead decomposition. No engine code changes; additive plugin + docs only.

### Added

- **`/dekspec:man` slash command** (INT-101) — the in-Claude-Code analogue of a unix man page. Renders `docs/dekspec-overview.md` verbatim: philosophy (5 convictions), the ten IR types (L0 singletons including Constitution + L1 AE/ADR + L2 WS/IC + L3 IB + Intent/Mission), audit families (L/T/D/SI series), status lifecycle, typical end-to-end workflow loop, surface inventory. The slash command body resolves the doc via three candidate paths (library-side / consumer-vendored / plugin-side) so it works from a library self-dev session, a vendored consumer repo, or a pip-only install path.
- **`docs/dekspec-overview.md`** — the source document `/dekspec:man` renders. New `## Getting started` section tells operators to begin every session with `/dekspec:using-dekspec` (scaffold + No-Specless-Edits guardrail + skill catalog walkthrough). Constitution L0 artifact documented alongside System Vision + Domain Glossary; IR-types count updated from nine to ten.
- **Plugin catalog updates** — `/dekspec:man` listed in `plugins/dekspec/README.md` + `plugins/dekspec/CONVENTIONS.md` under Pattern-A (doc-render pattern).

### Self-spec

- **INT-101 LOCKED** — `Ship /dekspec:man slash command + docs/dekspec-overview.md`. Direct DRAFT → LOCKED transition per bead-as-spec pattern (≤3-file feature scope; Verification predicate ran green). Linked AEs: AE-006 (Skills Library), AE-007 (Templates Library).

### Beads

- **ds-d0as decomposed into 7 sub-beads A–G** for Phase 1.B (risk_tier + failure_class schema). Umbrella stays open + blocked-by all seven. `br ready` surfaces ds-gkhm (Intent IR `risk_tier` schema + parser) + ds-g3gh (bead body convention) as the foundational unblocked work; downstream audit rules + template/skill updates unblock as A + B close.

## [v0.98.0] — 2026-05-28

Plugin surface consolidation + post-MSN-016 verify-vendored sweep. Closes two P2 bug reports filed from a downstream consumer (dektora repo, dekspec 0.97.0): the stale `dekspec verify-vendored` hint pointed at a nonexistent CLI surface, and the post-upgrade doctor flagged drift when the engine pip install was skipped. No new skills/commands.

### Bug fixes

- **`compute_drift` engine-stale short-circuit** (`tooling/dekspec/vendoring.py`) — when `.dekspec-version` content differs from installed `__version__`, return a single `engine-stale-vs-vendored` advisory finding instead of per-file `modified` hashes that would all mismatch by construction (the lib reference and consumer content are from different versions). Closes ds-upgrade-manifest-not-regenerated-3osq.
- **Doctor `_remedy_command` hint** (`tooling/dekspec/cli.py`) — verify-vendored section's remedy points at `dekspec audit doctor --json` (existing surface, gives JSON detail of all sections) instead of the retired standalone `dekspec verify-vendored` verb. Closes ds-doctor-stale-verify-vendored-hint-wbnm.
- **Session-end summary hook** (`plugins/dekspec/hooks-handlers/session-end-summary.py`) — rewrote to dispatch a single `dekspec audit doctor --json` and parse the verify-vendored section from the response, instead of the broken `dekspec verify-vendored --json` subprocess that no longer exists.

### Plugin surface consolidation

- **`/dekspec:doctor-fidelity` retired** — body inlined into `/dekspec:doctor` as Stage 2. The `plugins/dekspec/skills/doctor-fidelity/` skill directory is deleted; `scripts/apply_path_overrides.py` relocated to `plugins/dekspec/scripts/doctor/`. `/doctor` remains the single operator surface; `--fidelity-only` / `--skip-fidelity` flags preserved.
- **`/dekspec:basic-audit` retired** — functionality fully covered by `/dekspec:doctor` Stage 1 (`dekspec audit doctor` already runs schema validate + linkage + drift in one pass). The retired-command file is deleted.
- **`/dekspec:validate` renamed to `/dekspec:validate-artifact`** — clarifies scope (single-artifact schema validation) vs the broader `/dekspec:doctor` graph audit. The retired name resolves nothing; the file rename is the migration.
- **Five obsolete smoke scripts deleted** — `scripts/smoke-remote-builder.sh`, `scripts/smoke-init-lite.sh`, `scripts/smoke-init-dekfactory.sh`, `scripts/smoke-dispatch-against-stub.sh`, `scripts/check-stale-open-attempts.sh`. All invoked CLI surface that was removed in MSN-016 (executor excision); they were broken at runtime.

### Documentation alignment

- Plugin commands swept: `migrate.md` + `upgrade.md` rephrase the verify-vendored pipeline stage label (it's an internal stage, not a standalone CLI verb).
- README + `docs/dekspec-methodology.md` + `plugins/dekspec/CONVENTIONS.md` + `plugins/dekspec/skills/using-dekspec/SKILL.md` updated to reflect the retired surfaces.
- Tripwire test (`tests/test_stale_terms_tripwire.py`) gains four new retired-term patterns (`/basic-audit`, `/dekspec:basic-audit`, `/doctor-fidelity`, `/dekspec:doctor-fidelity`) plus the legacy `dekspec verify-vendored` CLI verb.

### Engine internals

- `_SKILL_CLASS_DEFAULTS` in `tooling/dekspec/fidelity_audit/linkage.py` drops the `doctor-fidelity` "audit" class row (skill retired).
- `docs/dekspec-skill-flag-defaults.md` audit-class row removed in lockstep.

### Self-spec amendments

- INT-018, INT-089, INT-096 (LOCKED) gain editorial comments noting that their `## Components affected` globs point at files retired by v0.98.0 (the smoke scripts + doctor-fidelity skill); the Intents themselves remain LOCKED, the retired globs are commented out with provenance notes for L7b cleanup.

## [v0.97.0] — 2026-05-28

Phase 1.A: Operating Principle template support. Adds the recommended §Operating Principle section to the Constitution and System Vision templates, and codifies the design heuristic table in `docs/dekspec-methodology.md` + `docs/dekspec-operating-guide.md`. Originates from the dekfactory dark-execution strategy plan (Phase 1.A). Unblocks dekfactory df-0fz0 (Phase 2.E Spec Reviewer).

### Added

- **`## Operating Principle` section in `templates/constitution-template.md`** — inserted between `## Modified` and `## Article 1`. One-sentence mantra recommended (not schema-required) per Constitution; sits above the 8 canonical Articles so its framing scopes them. Parser-ignored (not in IR); surfaces to readers + AGENTS.md aggregator. Exemplar mantra documented in inline comments: "Human in forging, dark on derived" (Dektora/dekfactory, 2026-05-28).
- **`## Operating Principles` section in `templates/system-vision-template.md`** — inserted between `## Why This Exists` and `## What Success Looks Like`. 1-to-3-item list framing HOW the system operates; the Constitution's single-sentence mantra typically derives from this section. Parser-ignored (not in IR); surfaces to readers + AGENTS.md aggregator.
- **`## Operating Principles` section in `docs/dekspec-methodology.md`** — new section between §4 (artifact spine) and §5 (status lifecycles). Three sub-points: principles name a stance not a policy; they compress; they cascade. Exemplar mantra unpacked with the forging-vs-derived heuristic table mapping 11 activities → human-in-chair vs autonomous-AI defaults. "Cascade" subsection enumerates the six downstream surfaces that change when the mantra changes (Constitution Articles 5+7, AE autonomy field, Mission autonomy ceiling, audit-rule severity tuning, skill catalog filtering, regenerated AGENTS.md).
- **`## Operating Principles — the design heuristic` in `docs/dekspec-operating-guide.md`** — new section between the workflow intro and the `## The Workflow` ASCII diagram. Same heuristic table as the methodology doc, reused as the daily-judgment-call litmus test.

### Notes

- No new skills/commands. The existing `/dekspec:write-constitution` + `/dekspec:write-sv` skills consume the new sections via their amend modes; consumers re-run `--amend` (LOCKED → unlock → edit → relock) to add an Operating Principle to an existing artifact.
- Parser safety: both Constitution and System Vision parsers extract only KNOWN sections into the IR. The new `## Operating Principle(s)` H2s are silently dropped from the IR, so schema validation continues to pass on artifacts that include the new sections. No schema bump required.
- Library Constitution + System Vision continue to validate cleanly (`dekspec check validate` returns OK with 0 parse warnings on both).
- Closes ds-febo. Unblocks dekfactory-side Phase 2.E (df-0fz0) which blocks-on this template surface.

## [v0.96.0] — 2026-05-28

Plugin-surface cleanup + install-UX overhaul. Three beads land: `dekspec-maintainer` plugin excised, repo-wide help-text accuracy sweep, unified single-command installer + plugin-version drift detection.

### Breaking

- **`dekspec-maintainer` plugin removed from the marketplace.** Usage audit found zero invocations across the last ten releases (v0.89.1 → v0.95.0 all hand-crafted from RELEASING.md). The `plugins/dekspec-maintainer/` directory, its marketplace entry, the `scripts/smoke-release-skill-*.sh` smoke-test pair, and the maintainer-plugin mirror in `scripts/bump-version.py` are all removed. Consumers who had it installed should `claude plugin uninstall dekspec-maintainer@dekspec` (it no longer gets updates).
- **`tooling/dekspec/_vendored/skills/` narrowed to `_lib/` only.** User-facing skill bodies (`write-*`, `archeology`, `exec-coding-session`, etc.) are no longer vendored into the wheel — they ship exclusively through the Claude Code plugin marketplace per AE-006. The wheel's `_vendored/skills/_lib/` still holds the runtime-imported shared scripts (`artifact_ops.py` etc.); only the user-facing skill markdown bodies were dropped. The `pyproject.toml` package-data pattern + `setup.py::VendoringBuildPy` hook updated in lockstep.

### Added

- **`scripts/install.sh` — single-command unified installer.** Pulls both the Python CLI (via pipx from the Cloudsmith public index) and the Claude Code plugin (via `claude plugin marketplace add` + `claude plugin install`) at the same version in one shot. Resolves `latest` from GitHub releases or accepts an explicit `vX.Y.Z` argument. Re-running upgrades both. README + RELEASING.md updated to point at it as the canonical install path.
- **`plugin version` section in `dekspec audit doctor`.** New `_check_plugin_version_drift()` helper reads `~/.claude/plugins/cache/dekspec/dekspec/<version>/` and compares to `dekspec.__version__`. Section reports `clean` when versions agree, `advisory` (P3-equivalent) when they drift, `skipped` when the plugin isn't installed. Surfaces install-state drift to the operator without escalating exit code.
- **`DEPRECATED` status enum for Interface Contracts.** `tooling/dekspec/constraint_compiler/parser.py::_VALID_STATUSES` and `tooling/dekspec/schemas/interface-contract.schema.yaml::status` both extended. (Previously only AE/WS accepted DEPRECATED; this release brings IC into parity. Required because MSN-016 transitioned IC-004 / IC-006 / IC-999 to DEPRECATED.)
- **Stale-term tripwire test** (`tests/test_stale_terms_tripwire.py`). Fails at PR time if any retired-surface term (`/fidelity-audit`, `/create-beads`, `/local-coding-session`, `/run-coding-session`, `/record-divergence`, `/migrate-artifact-format`, `/dekspec-maintainer:release`, `dekspec exec dispatch|executions|lifecycle|active|package|manifest`) re-appears on a live operator-facing path (plugin tree, methodology docs, READMEs, CLI argparse). Historical record-keepers (CHANGELOG, locked Intents, DEPRECATED self-spec, archived workspace docs) are allowlisted.

### Changed

- **Repo-wide help-text accuracy sweep.** Stale slash-command and CLI-verb names from MSN-016 + the plugin-cleanup sprint replaced with current names across:
  - `README.md` — `skills/` row pivoted to `plugins/dekspec/skills/` with the post-cleanup roster + new sibling `plugins/dekspec/commands/` row.
  - `docs/cli-reference.md`, `docs/dekspec-quick-reference.md`, `docs/dekspec-operating-guide.md`, `docs/dekspec-methodology.md`, `docs/architecture.md` — `/fidelity-audit` → `/doctor`, `/record-divergence` removed, `/exec-coding-session` for the dispatch op.
  - `plugins/dekspec/skills/doctor-fidelity/SKILL.md` — internal self-references to the old `fidelity-audit` skill name fixed (scripts paths, help-mode manifest, examples).
  - `plugins/dekspec/skills/write-ibs/SKILL.md` — `dekspec exec dispatch` language replaced with downstream-consumer phrasing (`/write-beads`, `/write-tests` + the shared `_assert_ib_locked` gate).
  - `tooling/dekspec/cli.py` — `/fidelity-audit` references in the spec-fitness-functions scaffold prose updated to `/doctor`.
- **`AGENTS.md` regenerated** via `dekspec check aggregate agents-md` to capture current AE / ADR / WS state.
- **`RELEASING.md` §Cutting a release** — dropped the `/dekspec-maintainer:release` canonical-path callout (retired plugin); now describes the hand-crafted release flow as canonical.
- **AE-006 (Skills Library)** + **INT-017** (release skill Intent) get Amendment-Log entries recording the maintainer-plugin retirement + editorial corrections to stale globs.

### Fixed

- **Library docs no longer contradict tool behavior.** The post-MSN-016 doc-drift inventory (5 methodology docs + 2 skill bodies + cli.py prose) is cleaned.

### Removed

Code + content:
- `plugins/dekspec-maintainer/` (entire plugin: 4 files).
- `scripts/smoke-release-skill-dry-run.sh`, `scripts/smoke-release-skill-classification.sh`.
- 7 stale user-facing skill dirs from `tooling/dekspec/_vendored/skills/` (`create-beads`, `fidelity-audit`, `local-coding-session`, `migrate-artifact-format`, `record-divergence`, `run-coding-session`, `run-dekspec-fidelity-audit` — all retired by prior sprints; their vendored copies were leftover noise per AE-006 single-channel-delivery).

### Verification

- `dekspec audit doctor --at .`: ADVISORY (P0=0 P1=0 P2=0 P3=7) — baseline preserved.
- `dekspec audit linkage --min-severity P2`: zero findings.
- `python3 -m pytest -q --ignore=tests/test_mcp_server.py`: 2493 pass / 111 skip / 0 fail.
- `ruff check tooling tests`: clean.
- `bash -n scripts/install.sh`: clean syntax.

### Notes

Closes three beads filed during dogfood install + scaffold test 2026-05-28: `ds-excise-dekspec-maintainer-plugin-2s1x`, `ds-help-text-accuracy-sweep-essg`, `ds-unify-install-and-sync-docs-ajoo`.

## [v0.95.0] — 2026-05-28

Major architectural simplification. Per ADR-024 (no-factory in-process-only execution model, LOCKED 2026-05-28), the executor abstraction is excised wholesale from the engine, schema, self-spec, and plugin. DekSpec is now what it actually was: a single-process Constraint Compiler + Fidelity Audit Engine + CLI + Claude Code plugin. No out-of-process dispatch surface. Lands MSN-016 (executor excision Mission, COMPLETE).

### Breaking

- **`executor` config property removed** from `tooling/dekspec/schemas/dekspec-config.schema.yaml`. Consumers with an `executor:` block in `.dekspec/config.yaml` continue to load — `load_config()` silently strips the retired block before validation — but the field is no longer accepted as input on `write_config()`. The acute P1 patch in v0.94.0 made the field optional; this release removes it entirely.
- **`auth` config property removed**. Stripped silently from legacy configs alongside `executor`.
- **Six CLI subcommand families removed**:
  - `dekspec exec dispatch` (+ `--to inbox`, `dispatch reap`, `dispatch status`)
  - `dekspec exec package` (`build`, `show`, `submit`)
  - `dekspec exec executions` (`ls`, `show`, `metrics`, `tag`, `amend`, `link`)
  - `dekspec exec lifecycle` (cross-attempt watchdog)
  - `dekspec exec active` (executor registry)
  - `dekspec exec manifest` (executor manifest fetcher)
  - `dekspec exec config validate` (dispatch-config validator)
- **`--executor` / `--endpoint` flags removed** from `dekspec repo init` (formerly `dekspec init`). The Q&A now asks only for `--methodology`.
- **Python API removed**: `dekspec.executor_abc`, `dekspec.executor` (entire module), `dekspec.lifecycle`, `dekspec.transport`, `dekspec.package`. Importing any of these raises `ModuleNotFoundError`.
- **Six self-spec artifacts DEPRECATED** with supersession breadcrumbs pointing at ADR-024 + MSN-016:
  - `dekspec/architecture-elements/AE-009-async-dispatch-workflow.md`
  - `dekspec/interface-contracts/IC-004-executor-contract.md`
  - `dekspec/interface-contracts/IC-006-dekfactory-dispatch-payload.md`
  - `dekspec/interface-contracts/IC-999-connection-verification.md`
  - `dekspec/working-specs/WS-003-executor-swap-contract.md`
  - `dekspec/working-specs/WS-011-executor-selection-cli-contract.md`
- **20+ tests deleted** that exercised executor / dispatch / package / lifecycle / transport surfaces (`test_executor_*`, `test_dispatch*`, `test_package*`, `test_lifecycle*`, `test_dekfactory_*`, `test_transport_sftp`, `test_cli_exec_dispatch_*`, `test_cli_exec_manifest`, `test_cli_outbox_read`, `test_cli_config_validate`, `test_ws003_executor_parity`).

### Added

- **ADR-024 (no-factory in-process-only execution model)** — LOCKED 2026-05-28. Documents the architectural posture this release ratifies.
- **MSN-016 (executor abstraction excision)** — COMPLETE 2026-05-28. The Mission that owns the removal work end-to-end. 5 verification cmd checks pass: zero `config.executor` reads in engine, zero `executor:` in schema required array, all 6 self-spec DEPRECATED, dispatch CLI verbs gone, library self-audit at P3-only baseline.
- **`DEPRECATED` status enum** added to Interface Contracts — `tooling/dekspec/constraint_compiler/parser.py::_VALID_STATUSES` and `tooling/dekspec/schemas/interface-contract.schema.yaml::status` both extended. Brings IC into parity with AE/WS (which already accepted DEPRECATED). Required because this release transitions 3 LOCKED ICs to DEPRECATED.
- **Legacy-config strip behavior in `dekspec_config.load_config()`** — `executor:` and `auth:` blocks are silently removed from in-memory loaded configs before schema validation. Pre-MSN-016 on-disk configs continue to validate cleanly without operator intervention.

### Fixed

- **L7b cascade post-engine-excision** — 14 LOCKED Intents (INT-018, INT-019, INT-022, INT-026, INT-028, INT-040, INT-041, INT-042, INT-069, INT-075, INT-089, INT-090, INT-092, INT-093) carried `components_affected:` globs pointing at code this release deletes. Each got the stale globs stripped + an Amendment Log entry recording the MSN-016-driven editorial correction. INT-026's empty section got a placeholder glob pointing at MSN-016 (T15-INT-COMPONENTS-NONEMPTY satisfied).
- **MSN-016 intent_queue** — INT-100 / INT-101 / INT-102 references removed (the work was direct-implemented on the integration branch rather than authored as formal Intent artifacts). L8-MSN-INT-EXISTS resolves clean.

### Changed

- **INT-100 transitioned OVERSIZED → SUPERSEDED**, Superseded-By: MSN-016. The single-Intent shape originally proposed for the full excision tripped 5 size caps on `/write-intent --analyze`; the multi-Intent shape (MSN-016) was the structural answer.
- **Plugin narrative sweep** — `plugins/dekspec/skills/_lib/cli_verbs.md` drops the 6 retired exec-group rows; `plugins/dekspec/skills/exec-coding-session/SKILL.md` + `plugins/dekspec/agents/coding-orchestrator.md` reframe IC-004 / executor-abstraction language as DEPRECATED / retired-surface footnotes; the in-process dispatch path survives unchanged.
- **AE-001 (System AE), AE-005 (CLI AE), AE-006 (Skills Library)** — backlinks refreshed via `dekspec audit relink`; surviving prose reflects the no-factory posture.

### Removed

Code:
- `tooling/dekspec/executor_abc.py` (168 LOC)
- `tooling/dekspec/executor/` (5 files, ~1,400 LOC: `__init__.py`, `registry.py`, `local_agent.py`, `dekfactory.py`, `dekfactory_manifest.py`)
- `tooling/dekspec/lifecycle.py` (886 LOC)
- `tooling/dekspec/transport.py` (566 LOC)
- `tooling/dekspec/package/` (2 files, ~800 LOC)
- `tooling/dekspec/schemas/dekfactory-manifest.schema.yaml`
- ~3,543 lines from `tooling/dekspec/cli.py` (dispatch + package + executions + lifecycle + active + manifest subparsers and their `cmd_*` handlers)

### Verification

- `dekspec audit doctor --at .`: ADVISORY (P0=0 P1=0 P2=0 P3=7) — baseline preserved.
- `dekspec audit linkage --min-severity P2`: zero findings.
- `python3 -m pytest -q --ignore=tests/test_mcp_server.py`: 2492 pass / 111 skip / 0 fail.
- `ruff check tooling tests`: clean.
- 5/5 Mission Verification cmd checks green.

### Notes

Closes bug bead `ds-remove-executor-concept-yv0a` (the consumer-blocking `DekspecConfigError: 'executor' is a required property` reported 2026-05-27). The acute symptom was patched in v0.94.0 (schema field made optional); this release ships the full architectural answer.

This release is BREAKING for any consumer that was actually using the executor abstraction (none known internally). The architectural successor for async dispatch is the redesigned dekfactory plugin in `Dektora/dekfactory`, which lives outside this library by deliberate cross-repo split (INT-099, 2026-05-27).

## [v0.94.1] — 2026-05-27

Patch. Install-command doc fix for the v0.94.0 Cloudsmith public-read transition.

### Fixed

- **`pip install` command across `RELEASING.md` + `scripts/install-dekspec.sh`** now includes `--extra-index-url https://pypi.org/simple/` so dekspec's transitive PyPI dependencies (pyyaml, jsonschema, etc.) resolve. Pure `--index-url <cloudsmith>` (as shipped in v0.94.0) replaces PyPI rather than adding to it, causing dep resolution to fail on a fresh venv with `Could not find a version that satisfies the requirement pyyaml>=6.0`. The corrected one-liner: `pip install --index-url https://dl.cloudsmith.io/public/dektora/python-public/python/simple/ --extra-index-url https://pypi.org/simple/ dekspec==X.Y.Z`. Verified end-to-end in a fresh venv against the live Cloudsmith index.

## [v0.94.0] — 2026-05-27

Distribution-channel change. Cloudsmith repo renamed `dektora/python-private` → `dektora/python-public` and visibility flipped to public-read. Consumers no longer need a Doppler-held entitlement token (`DEKSPEC_CLOUDSMITH_INDEX_URL`); the install URL is hardcoded across docs + scripts. No code changes; no schema changes.

### Breaking (consumer side)

- **Cloudsmith install URL changed.** Consumers must update their `pip install --index-url <url>` invocations:
  - **Old**: `pip install --index-url "$DEKSPEC_CLOUDSMITH_INDEX_URL" dekspec==X.Y.Z` (entitlement-token-bearing URL held in Doppler)
  - **New**: `pip install --index-url https://dl.cloudsmith.io/public/dektora/python-public/python/simple/ dekspec==X.Y.Z` (anonymous public-read; hardcodable everywhere)
- **Cloudsmith repo renamed**: `dektora/python-private` → `dektora/python-public`. Cloudsmith preserves package history on rename, so existing v0.91.x–v0.93.0 wheels survive the move and remain installable at the new URL. CI publish target updated.
- **Doppler dependency removed** for the install path. The `DEKSPEC_CLOUDSMITH_INDEX_URL` secret is no longer required by consumers, install-dekspec.sh, or any documentation. (The `CLOUDSMITH_API_KEY` secret is still required on the CI side for pushing wheels.)

### Changed

- **`.github/workflows/release.yml`** — push target is now `dektora/python-public`; header docs rewritten to describe the public-read distribution model.
- **`RELEASING.md`** — narrative reframed: source remains proprietary (private GitHub repo), but the wheel is distributed via a public-read Cloudsmith index. Failure-mode quick-reference updated; section header renamed "Distribution: Cloudsmith public index". Doppler / `DEKSPEC_CLOUDSMITH_INDEX_URL` references removed.
- **`scripts/install-dekspec.sh`** — `--help` text + comment header reflect the new hardcoded install URL (both occurrences swept).

### Notes

- License posture stays "Proprietary" — public wheel distribution does not imply OSS licensing. Re-evaluate the `pyproject.toml::license` field + the public-PyPI question separately if/when the source licensing changes.
- The `git+https://github.com/Dektora/dekspec.git@vX.Y.Z` install path remains supported as the no-pip-config fallback (uses the consumer's existing GitHub auth).

## [v0.93.0] — 2026-05-27

Minor release. Plugin-surface cleanup sprint (12 beads B1–B12) + dispatch-payload determinism fix. No new IRs, no schema changes. Doctor: P0=0 P1=0 P2=0 P3=5 baseline (unchanged). 2892 pass / 112 skip.

### Breaking

- **`/audit` renamed to `/basic-audit`** (B5). Pairs with `/doctor` as narrow-vs-full audit surfaces.
- **`/fidelity-audit` collapsed into `/doctor`** (B11). `commands/fidelity-audit.md` deleted; `skills/fidelity-audit/` renamed → `skills/doctor-fidelity/`. `/doctor` now runs CLI doctor (Stage 1) + the `doctor-fidelity` skill body (Stage 2: T/D/L family fidelity audit) in one invocation. New stage-control flags: `--skip-fidelity`, `--fidelity-only`.
- **`/local-coding-session` renamed to `/exec-coding-session`** (B3). Third rename for this surface (after `/run-coding-session` → `/local-coding-session` in INT-098). Aligns with the `dekspec exec dispatch` CLI verb. Both command + skill paths renamed; 24-file cross-ref sweep.
- **`/migrate-artifact-format` skill removed** (B2). Walker body folded into `/dekspec:migrate` as Stage 2 (the interactive advisory-queue walker). Helper script `advisory_io.py` relocated to `plugins/dekspec/scripts/migrate/`. New flags on `/migrate`: `--skip-walker`, `--walker-only`, `--skip <n>`, `--auto-approve`.
- **`/record-divergence` skill removed** (B6). The methodology stays — divergence notes are still authored as markdown files under `dekspec/divergences/` per the README's file shape — but the Claude-side authoring skill is retired.
- **`/write-beads` slash-command wrapper dropped** (B1). Skill at `plugins/dekspec/skills/write-beads/` stays. Restores the convention that the 12 write-* authoring skills are skill-only (no command wrapper); INT-098's rename-alias wrapper is no longer load-bearing.

### Added

- **`/dekspec:using-dekspec` slash-command wrapper** (B8). Onboarding entry point — typeable handle for the `using-dekspec` skill (init + spec-mode + catalog merge per INT-096). Mirrors the Superpowers plugin convention.
- **`/dekspec:orchestrate-intent` slash-command wrapper** (B9). Typeable handle for the interactive Intent lifecycle walker.
- **`plugins/dekspec/CONVENTIONS.md`** (B12). Codifies the three-pattern surface classification (CLI-wrapper command-only, skill-only authoring, command+skill pair) + the hybrid exceptions for `/doctor` and `/migrate`. Bucket assignments listed for every current surface.

### Changed

- **`/archeology` + `/brownfield-ingest` standardized to Skill-wrapper pattern** (B7). Both command bodies previously duplicated the skill's mode-dispatch prose with non-Skill `allowed-tools`. Trimmed to canonical 2-step Skill-wrapper stubs mirroring `/exec-coding-session` / `/doctor`-pre-collapse shape.
- **AE-006 (Skills Library)** updated for the catalog rebuild (skill enumeration, Mermaid diagram, Amendment-Log entries covering B6/B10/B11/B3).
- **`docs/dekspec-skill-flag-defaults.md`** — recovery class drops `migrate-artifact-format`; audit class becomes `doctor-fidelity`; utility class drops `record-divergence`. Per-skill overrides table cleared (the lone `record-divergence` haiku override was retired with the skill).
- **`tooling/dekspec/fidelity_audit/linkage.py::_SKILL_CLASS_DEFAULTS`** — registry mirrors the docs sweep.
- **README.md** — slash-command roster refreshed (drops retired `/dekspec:init` / `/dekspec:verify-vendored` / malformed `/dekspec-migrate` slugs; adds `/dekspec:validate`).

### Fixed

- **Dispatch-payload determinism flake** (closed ds-int-098-migrate-toplevel-help-yf3o, retitled). `test_dispatch_to_inbox_idempotent_redispatch` flaked at ~20% because two wall-clock timestamps leaked into the inbox tarball bytes: (1) `manifest.yaml::created_at` (set in `build_package`, not scrubbed by `_write_tarball`); (2) `compiled_outputs.{intent,ib}.source.parsed_at` (set by `parse_intent`/`parse_ib`, embedded in both `manifest.yaml::compiled_outputs` AND `dispatch_payload.json::compiled_outputs`). Both scrubbed to the existing `_HASH_TIMESTAMP_SENTINEL` / a new `_DISPATCH_PARSED_AT_SENTINEL` before tarball assembly. 50/50 idempotency-loop runs green post-fix.
- **L7b cascade cleanup for B3 + B11** — 3 LOCKED Intents (INT-011, INT-054, INT-056) had `Components affected:` globs pointing at `plugins/dekspec/skills/local-coding-session/SKILL.md`; 1 LOCKED Intent (INT-096) referenced `plugins/dekspec/skills/fidelity-audit/`. All cleared via editorial Amendment-Log row + glob update.

### Removed

- Three legacy stub skill directories deleted (B10): `skills/create-beads/`, `skills/run-coding-session/`, `skills/run-dekspec-fidelity-audit/`. Each held only `__pycache__/*.pyc` (no tracked SKILL.md or source); pure tree bloat from prior INT-098/INT-096 renames.

### Notes

- 12-bead sprint executed serially with bead-as-spec direct-implement; no Intent ceremony (each bead's Acceptance served as the spec).
- B4 (rename `/fidelity-audit` → `/comprehensive-audit`) was filed then closed as superseded by B11 (collapse into `/doctor`) — the intermediate rename would have been wasteful.
- Three P4 beads (ds-sa9 / ds-s1e / ds-c76) labeled `v1-candidate` and deferred to 2026-11-27 (`br ready` queue now empty).

## [v0.92.0] — 2026-05-27

Minor release. Two LOCKED Intents — INT-098 (plugin surface cleanup) and INT-099 (factory surface excision). Breaking surface changes: 3 skill renames, 4 deprecated CLI verbs collapsed into one pipeline, antigravity-compat surface removed, factory skill family excised. Doctor returns ADVISORY (P0=0 P1=0 P2=0 P3=5 baseline). 2916 pass / 112 skip.

### Breaking

- **3 skill + slash-command renames** (INT-098 IU-1, no transition aliases per repo no-backcompat policy):
  - `dekspec:run-dekspec-fidelity-audit` → `dekspec:fidelity-audit`
  - `dekspec:run-coding-session` → `dekspec:local-coding-session`
  - `dekspec:create-beads` → `dekspec:write-beads`
- **Migrate-family CLI verbs consolidated** (INT-098 IU-2). `dekspec migrate` is now a top-level pipeline verb that runs `verify` → `migrate-ir` → `migrate-artifacts` in sequence. Removed bare-verb aliases (`verify-vendored`, `migrate-ir`, `migrate-artifacts`) from `LEGACY_COMMANDS` AND removed the underlying `dekspec repo verify` / `dekspec repo migrate-ir` / `dekspec migrate-artifacts` subverb parsers themselves. Single user-facing entry point. `dekspec upgrade` automatically chains `dekspec migrate` after the install + plugin-refresh phase.
- **Antigravity-compat surface removed** (INT-098 IU-1). `plugins/dekspec/commands/antigravity-compat.md` + `plugins/dekspec/hooks-handlers/antigravity-compat.py` deleted.
- **Factory skill family excised from the dekspec plugin** (INT-099 — delete-side of dekfactory cross-repo split). Deleted 3 skill directories (`factory`, `factory-listen`, `factory-dispatch-intent`) + 4 slash-command files (`factory.md`, `factory-listen.md`, `factory-dispatch.md`, `factory-dispatch-intent.md`) from `plugins/dekspec/`. Factory functionality is intentionally removed from this library; a redesigned async-dispatch surface will live in a separate `dekfactory` plugin in `Dektora/dekfactory` (independent rework, NOT a 1:1 port — different architecture, different surface, different version, tracked by `df-df-plugin-create-xv38`). Consumers using factory features should expect a gap window during transition. The `dekfactory` executor backend (CLI/contract surface in WS-003 / WS-011 / IC-005 / IC-006) is preserved unchanged.

### Changed

- **AE-009 (Async Dispatch Workflow) substantively revised** (INT-099 IU-2). Reframed as the contract this library DEFINES while implementation moves out of scope. Dropped stale `Implements:` glob `plugins/dekspec/skills/dispatch-inbox-listener/**` (already non-existent since INT-090) and the now-leaving `factory*/` skill globs. Kept CLI dispatch verb globs intact. Added §External-Implementations row pointing at the `dekfactory` plugin in `Dektora/dekfactory` as the listener-side counterpart. AE-009 stays ACTIVE (not DEPRECATED).
- **AE-006 (Skills Library)** narrowed for the renames + antigravity-compat removal (INT-098) and for the factory excision (INT-099).
- **AE-005 (CLI)** updated for the migrate consolidation and subverb removal.
- **Docs sweep**: `docs/dekspec-skill-flag-defaults.md` lines 43-44 drop factory rows; `docs/dekspec-methodology.md` + `docs/dekspec-operating-guide.md` drop stale `/dekspec:dispatch-inbox-listener` mentions (pre-existing stale from the INT-090 rename, in-scope for INT-099 IU-3 docs sweep).

### Fixed

- **L7b cascade cleanup post-INT-098 + INT-099** — 11 LOCKED Intents had stale `Components affected:` globs that pointed at paths renamed or deleted by the two Intents (INT-011, INT-054, INT-056, INT-078, INT-080, INT-096 from INT-098 fallout; INT-043, INT-055, INT-076, INT-078, INT-090 from INT-099 fallout). Cleared inline on each Intent's branch via the unlock → update-glob → lock cycle per ADR-017 Path B (precedent: `6b44ffc`). Closes `ds-stale-l7b-post-098-xjvc` + `ds-stale-l7b-post-099-1978`.

### Notes

- INT-098 retroactively designated OVERSIZED after `Components affected:` expansion from 3 → 4 globs (`plugins/dekspec/**`, `tooling/**`, `tests/**`, `docs/**`). The rename-cascade legitimately touches 4 top-level directories; engineer accepted the OVERSIZED designation and locked via Path B (vacuously satisfied — zero downstream WS/IC/IB).
- INT-099's cross-repo P1 sequencing gate (OI-1) was dissolved by engineer decision 2026-05-27. Factory plugin in `Dektora/dekfactory` is independent rework, not a 1:1 port — consumer gap window during transition is accepted.
- New memory pattern recorded: "accept-removal-gaps-when-downstream-is-rework" — don't default to "downstream-must-ship-first" sequencing gates when the downstream is a redesign, not a port.

### Follow-up beads

- `ds-int-098-migrate-toplevel-help-yf3o` (P3) — investigate the `dekspec migrate` top-level help discovery (9 transient-order test failures observed on INT-098 branch; suite passes on merged main but may need argparse surface fix for stability).
- `df-df-plugin-create-xv38` (in `Dektora/dekfactory`) — independent feature work to author the dekfactory Claude Code plugin with new architecture. No longer gates INT-099.

## [v0.91.2] — 2026-05-27

Patch release. Adds the `dekspec exec config validate` verb (ds-utik follow-up) and clears the rename-cascade fallout from v0.91.0. Doctor returns ADVISORY (P0=0 P1=0 P2=0 P3=5 baseline) — the cleanest dogfood gate the library has had since the INT-095/096 renames landed. 2934 pass / 112 skip.

### Added

- **`dekspec exec config validate [--at <repo>] [--config <path>]`** (ds-ds-utik-config-validate-ks28, commit `b58f60a`). Lint `.dekspec/config.yaml` at config-load time, not at dispatch time. Structured stderr codes mirror the dispatch-verb refusal vocabulary so CI scripts see the same codes here as on a real dispatch refusal: `EXECUTOR_KIND_UNKNOWN`, `ENDPOINT_MISSING`, `ENDPOINT_MALFORMED`, `INBOX_URI_SCHEME_UNSUPPORTED`, `AUTH_KIND_UNKNOWN`, `IDENTITY_FILE_MISSING`, `AUTH_SECRET_REF_MISSING`, `CONFIG_LOAD_FAILED`. Exit 0 on clean config (including no config file at all — local-default state); exit 1 with the structured code on the first violation. 13 unit tests cover every code path.

### Fixed

- **Dogfood gate cleared** (ds-stale-l7b-globs-post-095-096-yjwo, commit `6b44ffc`). Six LOCKED Intents (INT-030, INT-059, INT-077, INT-078, INT-091, INT-096) carried `Components affected` globs that pointed at paths renamed or retired by INT-095 + INT-096. Each Intent walked the editorial-correction cycle per ADR-017 + the CLAUDE.md unlock guardrail: `artifact_ops.py transition LOCKED → PROPOSED` with the engineer's full-sentence reason recorded verbatim in the Amendment Log; in-place backtick-scoped glob rewrite (left historical-path prose mentions alone); `artifact_ops.py transition PROPOSED → LOCKED` via Path B (0-downstream re-lock; net Archive → Active → Archive). 11 stale globs cleared.

- **8 pre-existing inbox-dispatch test failures repaired** (commit `b58f60a` adjacent fix). A concurrent-session commit `dc2fed4` made `repo.scope` mandatory in dispatch payloads, breaking the synthetic-consumer fixtures in `tests/test_dispatch.py` and `tests/test_transport_sftp.py`. Both fixtures now seed `.dekspec/config.yaml` with `repo.scope: Dektora/test-fixture`; two tests that overwrote the config also re-include the `repo:` block.

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY with exit code 0 (P0=0 P1=0 P2=0 P3=5 — baseline P3 advisories on the library's own self-spec, unchanged since pre-INT-095/096). First fully-clean gate at this severity tier since 2026-05-25.

## [v0.91.1] — 2026-05-27

Patch release. Fixes ds-nw7x: `dekspec exec dispatch --to inbox` shipped tarballs whose filename SHA did NOT equal `sha256(file content bytes)`, so the INT-066 watcher rejected every inbox dispatch with `sha_mismatch`. 100% of inbox transport dispatches failed at v0.91.0. Doctor remains WARNING with exit 0 (P0=P1=0). 2919 pass / 112 skip (+2 new ds-nw7x regression tests).

### Fixed

- **`pack()` produces a tarball whose filename SHA equals `sha256(file content bytes)`** (ds-inbox-sha-mismatch-filename-vs-content-nw7x, commit `0250ad8`). Two root causes addressed:
  - Pre-fix the gzip header carried `mtime = time.time()` (Python `tarfile.open(name, mode="w:gz")` default), and every TarInfo inherited the source file's `mtime`/`uid`/`gid`/`uname`/`gname`/`mode`. The bytes varied per write even when the manifest and bundle were identical.
  - The filename SHA was computed from a canonicalized-manifest + bundle-content-hash string, NOT from the file's gzipped bytes. The watcher hashes the file bytes (the only thing it has on disk).
  - Fix: deterministic bytes — `gzip.GzipFile(fileobj=raw, mode="wb", mtime=0)` wrapping `tarfile.open(fileobj=gz, mode="w")` + normalized TarInfo (`mtime=0`, `uid=0`, `gid=0`, `uname=""`, `gname=""`, `mode=0o644`, `type=REGTYPE`, `linkname=""`). Files added via in-memory `addfile(info, BytesIO(src_bytes))` so source-file metadata is not inherited. Then write to a `.pack-XXX.tmp` temp path, hash the bytes, and `os.replace` to `<sha>.tar.gz` — the filename SHA is the file content SHA by construction.
  - Manifest YAML written *inside* the tarball carries `package_id: ""` to avoid a chicken-and-egg cycle with the file hash that names the tarball; the filename is canonical. `package/inspect.py::inspect()` surfaces the filename-derived SHA when the in-tarball manifest's `package_id` is empty so `dekspec exec package show <sha>` output reflects the real content address.

Two new regression tests assert the invariant: `test_pack_filename_sha_matches_content_sha_ds_nw7x` (filename SHA == `sha256(file bytes)`); `test_pack_byte_identical_on_repack_ds_nw7x` (deterministic-bytes contract: two `pack()` calls produce byte-identical tarballs). End-to-end smoke confirmed: filename and content SHA match exactly.

### Dogfood gate

`dekspec audit doctor --at .` returns WARNING with exit code 0 (P0=0 P1=0 P2=10 P3=5) — unchanged from v0.91.0; the pre-existing P2 stale-glob refs from the INT-095/INT-096 rename cascade and INT-096 self-cascade in its own Components-affected globs are tracked in `ds-stale-l7b-globs-post-095-096-yjwo`. No blockers.

## [v0.91.0] — 2026-05-27

Minor release. Three locked Intents: skill-command name shortening, an `using-dekspec` merged onboarding skill, and a self-contained wheel that removes the `scripts/install-dekspec.sh` precondition. The headline change: `pip install dekspec==0.91.0` is now sufficient to use dekspec — templates and methodology docs resolve directly from the installed wheel package data via the new `dekspec resource` CLI verb. Consumer-vendored copies still override the wheel fallback when present. Doctor remains ADVISORY/WARNING (P0=P1=0; pre-existing P2 stale-glob refs from the rename cascade tracked separately). 2919 pass / 112 skip (+14 new resolver tests).

### Added

- **`dekspec resource template <name>` and `dekspec resource doc <name>` CLI verbs** (INT-097 / commit `1f0a978`). Resolve a wheel-vendored asset (template or methodology doc) by short name with consumer-fs override winning over the wheel `_vendored/` fallback. Default mode emits file content to stdout; `--path-only` emits the absolute path for shell composition (e.g. `TEMPLATE=$(dekspec resource template intent --path-only)`). Name normalization: the `-template` suffix is auto-appended for templates; the `dekspec-` prefix is auto-appended for canonical docs. Skills and agents that previously hard-coded `dekspec/templates/<x>-template.md` and `dekspec/dekspec-<doc>.md` paths now cite the resolution rule via `plugins/dekspec/skills/_lib/vendored_assets.md` so an LLM session can fall back to the wheel-resolved path when the consumer-fs copy does not exist (post-pip-install layout). New `resolve_template()` and `resolve_doc()` helpers in `tooling/dekspec/vendoring.py`. Closes the wheel-self-contained gap that previously required consumers to clone the dekspec repo + run `scripts/install-dekspec.sh` before any skill could read a template.

- **`/dekspec:using-dekspec` merged onboarding skill** (INT-096, commit `3e02ae8`). Single entry point replacing three legacy surfaces (`/dekspec:spec-mode`, `/dekspec:skills`, `/dekspec:init`). Four modes: `--init` (scaffold artifact tree), `--spec-mode --on|--off|--status` (toggle the No Specless Edits guardrail), `--catalog` (skill catalog listing), and a default walkthrough that touches all three in onboarding order. Spec-mode behavior — including the INT-091 R1 provisional-first reminder block — is preserved verbatim.

### Changed

- **13 plugin slash-commands renamed to drop the redundant `dekspec-` prefix** (INT-095, commit `6892c3b`). Invocations shorten from `/dekspec:dekspec-init` to `/dekspec:init`, `/dekspec:dekspec-doctor` to `/dekspec:doctor`, etc. Two commands carried explicit `name:` frontmatter (`antigravity-compat`, `skills`) — those fields updated in lockstep with the filename. The other 11 derive the command name from the filename automatically. Cross-references swept across 11 SKILL.md / agent / hook / doc files (`/dekspec-<cmd>` → `/dekspec:<cmd>`). The `factory-*` family carries a different non-redundant prefix and stays out of scope.

- **`run-dekspec-fidelity-audit-v2/` renamed to `run-dekspec-fidelity-audit/`** (INT-096, commit `3e02ae8`). The v1 audit skill was historically frozen; the `-v2` suffix is no longer informative. 17 in-repo cross-references swept across SKILL.md bodies, `_lib/` templates, docs, tests, and `tooling/dekspec/{cli.py,fidelity_audit/*.py}`. The Claude Code plugin manifest registers the renamed skill at the same invocation surface.

### Deprecated

- **`scripts/install-dekspec.sh` is now a no-op shim** (INT-097, commit `1f0a978`). The wheel is self-contained since this release; the script accepts and ignores all pre-INT-097 flags (`--with-plugin`, `--via cloudsmith`, `--version vX.Y.Z`, `--installer pipx`, etc.) so existing CI lines (Doppler-wrapped invocations, devbox post-install hooks) keep working. Emits a deprecation notice on stderr + exits 0. Full removal deferred to a later major bump.

### Internal

- **INT-999 + IB-999 connection-verification fixtures moved out of the canonical tree** (commit `6ca332e`). `dekspec/intents/INT-999-*.md` and `dekspec/impl-briefs/completed/IB-999-*.md` are now under `tests/fixtures/canonical_intents/`. The fixture's presence in the canonical tree had been skewing `artifact_ops.py next-id` (max+1 returned INT-1000 because INT-999 was a sentinel, not a production Intent). Post-move: `dekspec dev next-id intent` returns the real next sequential cleanly.

- **`scripts/test-wheel-self-contained.sh` smoke test** (INT-097). Builds the wheel, pip-installs into a throwaway venv with no consumer-vendored content, asserts `dekspec resource template intent` and `dekspec resource doc operating-guide` resolve from `_vendored/` with non-empty content. The smoke test is the third Verification predicate check on INT-097.

### Follow-ups filed

- `ds-stale-l7b-globs-post-095-096-yjwo` (P3) — 6 pre-existing P2 stale-glob refs in older LOCKED Intents (INT-030, INT-059, INT-077, INT-078, INT-091) reference paths renamed by INT-095 + INT-096. Fix requires `--unlock` ceremonies on 5 LOCKED Intents; deferred.

### Dogfood gate

`dekspec audit doctor --at .` returns WARNING with exit code 0 (P0=0 P1=0 P2=10 P3=5). 6 P2 findings are the rename-cascade in the follow-up bead above; 4 are INT-096 self-cascade in its own Components-affected globs; none are blockers.

## [v0.90.0] — 2026-05-27

Minor release. Lands the workstation-side half of the inbox/sftp dispatch transport (ds-utik + ds-1s2c) and tightens the dispatch source-sync gate with two new unconditional refusals (ds-5e4u). Together these kill the bearer-token + Doppler + direnv ceremony for inbox-driven dispatch and close the silent-correctness window where the factory would clone a stale origin ref while the operator believed the dispatched package matched their local tree. Doctor remains ADVISORY (P0=P1=P2=0; P3=5). 2905 pass / 112 skip (+40 new tests).

### Added

- **`dekspec exec dispatch --to inbox --inbox-uri sftp://<host>/<path>`** (ds-inbox-sftp-push-utik, commit `caa1574`). New remote-inbox transport pushes the content-addressed Package tarball to the executor host's local inbox via `scp` + `ssh mv` with atomic temp-name + rename semantics. Implementation deliberately shells out to OpenSSH rather than adding paramiko / asyncssh as a Python dep — the operator already has SSH-agent / `~/.ssh/config` trust from git push. Supported URI schemes: `file://<path>` (and bare paths) preserve the legacy local-FS behavior; `sftp://<host>[:<port>]/<absolute-path>` triggers the SSH-key path. Config schema extends `.dekspec/config.yaml` with `executor.inbox_uri`, `executor.outbox_uri`, and an `auth.kind` (`ssh_agent` default, `identity_file` opt-in with `auth.identity_file: <path>`). New flags: `--inbox-uri <uri>` (overrides config), `--inbox-identity-file <path>` (overrides `auth.identity_file`). Refusal codes (BEFORE Package build): `INBOX_URI_SCHEME_UNSUPPORTED`, `INBOX_REMOTE_UNREACHABLE`, `INBOX_REMOTE_WRITE_FAILED`. Precedence: CLI flag > config > local-FS default. Backward-compatible: omitting both flag and config preserves the pre-v0.90.0 stdout contract (`path=.dekspec/inbox/<sha>.tar.gz`).

- **`dekspec exec executions show <id>` + `dekspec exec dispatch status <sha>` read terminal-state from outbox URI** (ds-inbox-outbox-read-1s2c, commit `a101cba`). New `executor.outbox_uri` config field (sftp:// or file://) — when set, `executions show` fetches the listener-written `<sha>.json` record and merges remote terminal-state fields (`ci_status`, `merged`, `merge_commit_sha`, `completed_at`, `pr_url`, `escalation_required`, `constraint_violations_count`) into the rendered output. Rendered output now labels the view (`local-only` / `merged (remote)` / `merged (cache)`) so operators do not mistake stale local state for ground truth. `dispatch status` falls through to the same remote outbox on local IC-007 three-tier miss; the four-state classification (`inbox` / `claimed` / `outbox` / `unknown`) replaces the previous "no package found" hard error when `executor.kind=inbox`. New flags on both verbs: `--no-remote-fetch` (forensic / offline use), `--cache-ttl <seconds>` (default 30), `--no-cache` (bypass cache), `--outbox-uri <uri>` (per-invocation override). `executions show` adds `--persist`, which commits the merged remote state back into the local lifecycle row via `complete_execution_attempt` (idempotent: only fires when the local row is in-flight AND the remote record carries `ci_status`). File-backed cache lives under `$XDG_RUNTIME_DIR/dekspec/outbox-cache/` (falls back to `~/.cache/dekspec/outbox-cache/`); keyed on `sha256(uri + sha)[:16]` so URIs do not leak in raw form. Outbox-read failures degrade gracefully — `WARN:` to stderr + local-only render + exit 0 (never a hard error). Warning vocabulary: `OUTBOX_REMOTE_UNREACHABLE`, `OUTBOX_REMOTE_READ_FAILED`.

### Fixed

- **`dekspec exec dispatch` refuses on dirty working tree or local-ahead branch** (ds-dispatch-refuses-dirty-or-ahead-5e4u, commit `49ced1a`). Two new sender-side pre-flight refusal codes added alongside the existing IC-006 v3 `BASE_BRANCH_*` set, closing a silent-correctness window where the factory cloned a stale origin ref while the operator believed the dispatched package matched their local tree: `WORKING_TREE_DIRTY` (refuses when `git status --porcelain` is non-empty; refusal enumerates up to 5 modified paths with `(+N more)` suffix); `BASE_BRANCH_LOCAL_AHEAD_OF_REMOTE` (split out from the previously-bundled `BASE_BRANCH_NOT_ON_REMOTE` code so CI can distinguish the push-first case from the never-pushed case; refusal enumerates up to 3 unpushed short-sha + subject pairs). Both checks fire for `executor.kind` in `{dekfactory, inbox}` and skip entirely for `local`. Refusal is unconditional — no `--force`, no `--allow-dirty`, no env-var bypass. Both checks fire BEFORE Package build / HTTP POST so a refused dispatch leaves no lifecycle row, no `.dekspec/packages/<sha>.tar.gz`, no `.dekspec/inbox/<sha>.tar.gz`.

### Follow-ups filed (LOCKED-artifact ceremonies)

- `ds-ic006-bump-5e4u-l4qz` (P2) — IC-006 v3.2 enum doc bump for the two new refusal codes (additive, MINOR-evolution). Requires `--unlock`/`--lock` via `/dekspec:write-ic`.
- `ds-ds-utik-doc-bump-3i84` (P3) — operating-guide §Dispatch SFTP example + auth setup + Host stanza recommendation.
- `ds-ds-utik-config-validate-ks28` (P3) — new `dekspec exec config validate` verb to lint `.dekspec/config.yaml` at config-load time (no validate verb exists today, only `config get`/`config set`).
- `ds-ds-1s2c-doc-bump-utly` (P3) — operating-guide §Lifecycle Inspection remote-outbox flow + `--no-remote-fetch` / `--persist` guidance.

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=5) — baseline library state, unchanged by this release.

## [v0.89.1] — 2026-05-26

Patch release. Fixes `dekspec audit lock-ready --apply` in consumer repos, which died with a hardcoded path error pointing at `<consumer-repo>/plugins/dekspec/skills/_lib/scripts/artifact_ops.py` — a location that only exists in the dekspec library source tree. Consumers install dekspec via pip (wheel `_vendored/` snapshot) or the Claude Code plugin cache; neither places the script at the consumer's repo root. Doctor remains ADVISORY (P0=P1=P2=0; P3=5). 2854 pass / 112 skip.

### Fixed

- **`dekspec audit lock-ready --apply` now resolves `artifact_ops.py` across all three dekspec layouts** (ds-rzq2, commit `0b8ff5f`). Introduces `vendoring.resolve_skill_script(relpath, repo_root, lib_root)` which probes (1) library self-dev under `<repo_root>/plugins/dekspec/skills/`, (2) wheel `_vendored/` under `<library_root>/skills/` (the `_vendored/` layout strips the `plugins/dekspec/` prefix), and (3) source-checkout layout under `<library_root>/plugins/dekspec/skills/` reached via `library_root()` or `DEKSPEC_LIBRARY_ROOT`. Returns the first existing path or `None` for a friendly error message. `tooling/dekspec/cli.py::cmd_audit_lock_ready` replaces the hardcoded `repo_root / "plugins/dekspec/skills/_lib/scripts/artifact_ops.py"` with a call to the resolver. Same class of library-vs-consumer path-resolution issue as ds-a4h (`--library-self-audit`, v0.82.x).

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=5) — baseline library state.

## [v0.89.0] — 2026-05-26

Minor release. Shifts `/dekspec:write-intent` Creation Mode's `Autonomy` default from a flat `manual` to type-dispatched: `medium` for `bug` / `refactor` / `documentation` (categories where CI green is sufficient proof of correctness); `manual` for `feature` / `nfr` / `adr-driven` / `environment` (categories warranting explicit operator sign-off). Engineers retain the override via the inline `autonomy:` cue. Behavioral change visible to consumers — new Intents authored on this version stamp different defaults than prior versions. Doctor remains ADVISORY (P0=P1=P2=0; P3=5). 2849 pass / 112 skip.

### Changed

- **Type-dispatched Intent autonomy default** (INT-094, PR #51, merge `00c3ffb`, lock `b464bd6`). `plugins/dekspec/skills/write-intent/modes/create.md` Step 1 cue description + Step 4 Autonomy resolution prose now select `medium` for `bug` / `refactor` / `documentation` types and `manual` for `feature` / `nfr` / `adr-driven` / `environment` types when the engineer does not pass an explicit `autonomy:` cue. `templates/intent-template.md` `## Autonomy` section gains a "Recommended default by Intent type (INT-094)" callout after the autonomy tier bullets. `docs/dekspec-operating-guide.md` gains a "Type-default Autonomy (INT-094)" back-reference after the Intent lifecycle table. Rationale: post-INT-063 (DekFactory's auto-merge for `auto-medium`+ MRs once CI is green), defaulting `bug` / `refactor` / `documentation` Intents to `manual` silently opted out of a verification path the consumer already paid to build. First live exercise: a dektora `bug` Intent dispatch parked in `mr-opened` for ~4 hours on 2026-05-26 because Autonomy was `low`. No schema change; no breaking change to existing Intents (per-type default applies only at fresh authoring; existing Intents keep their authored value).

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=5) — baseline library state.

## [v0.88.4] — 2026-05-26

Spec-only release. Persists in-flight workspace plans + an incubation family of provisional artifacts under `dekspec/provisional/no-specless-edits-hybrid/` (1 MSN + 4 INTs) drafting the spec-mode mechanical-reinforcement family that addresses the recurring CLAUDE.md No-Specless-Edits guardrail tension. No code, schema, CLI, or skill behavior changes — vendoring driver does not copy `dekspec/provisional/` or `docs/workspace/` to consumers, so this is library-side only. Doctor remains ADVISORY (P0=P1=P2=0; P3=6).

### Added

- `dekspec/provisional/no-specless-edits-hybrid/` — 5 provisional artifacts (`MSN-provisional-spec-mode-mechanical-reinforcement`, `INT-provisional-no-specless-edits-hybrid`, `INT-provisional-spec-mode-hooks`, `INT-provisional-spec-mode-subagent-bridge`, `INT-provisional-spec-mode-substrate`). Library self-spec incubation; not vendored.
- `agy_implementation_plan.md` + `docs/workspace/cc_flywheel-plan.md` + `docs/workspace/cc_flywheel-synthesis-prompt.md` + `docs/workspace/cdx_feedback_flywheel_option_d_plan.md` — in-flight planning scratch.

## [v0.88.3] — 2026-05-26

Patch release. Three companion fixes around the dispatch + testpass flows surfaced from dektora's first DekFactory dispatch (MSN-001 INT-023). `/write-intent --testpass` no longer fires TESTFAIL on spec-graph lifecycle paths the Intent's lifecycle itself mutates (`dekspec/**`, `.beads/**`, `.dekspec/**`); dispatch payload's `beads` list now contains the real bead IDs the tracker holds against the IB instead of the `<unclaimed-for-IB-XXX>` sentinel; and `DekFactoryExecutor` HTTPError responses now surface the response body in the raised exception (400s were previously opaque without source-patching). 28 new tests; full suite 2849 pass / 112 skip.

### Fixed

- **`/write-intent --testpass` admits spec-graph lifecycle paths** (closes `ds-p4tt` — PR #48). New `tooling/dekspec/diff_confinement.py` helper + `IMPLICIT_LIFECYCLE_GLOBS = ["dekspec/**", ".beads/**", ".dekspec/**"]` admit-set. A changed file passes diff-confinement if it matches ANY of: (a) a glob in `Components affected:`, OR (b) a glob in the implicit lifecycle set. Resolves the 2026-05-26 INT-023 case where every Intent's `dekspec/intents/INT-NNN-*.md` + `dekspec/intent-index.md` + `.beads/issues.jsonl` updates correctly tripped TESTFAIL despite zero behavioral out-of-scope edits. 12 new tests cover the canonical case + negative case for genuine out-of-scope edits.
- **`dekspec exec dispatch` ships real bead IDs from the tracker** (closes `ds-j4a2` — PR #50). `_build_dispatch_payload` now calls `_resolve_beads_for_ib(repo_root, ib_id)` which reads `.beads/issues.jsonl` and returns sorted IDs of beads whose `external_ref` carries the IB-NNN token (filtered to `open` / `in_progress`). Replaces the legacy `<unclaimed-for-IB-XXX>` sentinel. Silent failure → empty list (no `.beads/`, decode errors, etc.). 7 new tests cover positive + empty + closed-exclusion + malformed-line tolerance.
- **`DekFactoryExecutor` HTTPError handler surfaces response body** (closes `ds-11l6` — PR #49). New `_read_error_body(exc)` helper reads `exc.read()` once, UTF-8 decodes with `errors="replace"`, falls through to `"<unreadable>"` if `.read()` raises. Both HTTPError handlers (`_post_json` dispatch path + `fetch_status` path) now append `:: body=<text>` to the raised `DekFactoryExecutorError` message. Resolves the diagnosis pain reported in `ds-a761` (operator had to source-patch the executor to surface the body). 9 new tests cover 400/500 surfacing, non-UTF8 graceful degradation, `.read()` failure sentinel.

### Closed beads

- `ds-p4tt` (P1) — testpass diff-confinement.
- `ds-j4a2` (P2) — dispatch beads list.
- `ds-11l6` (P3) — HTTPError body surface.

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=6) — baseline library state.

## [v0.88.2] — 2026-05-26

Patch release. Two more dispatch-blocking fixes layered on top of v0.88.1's `compiled_outputs` populate: now `repository_scope` ships in the IC-006 payload (so DekFactory knows which tenant repo to clone — no more silent fallback to `Dektora/dekfactory`), and `ib_path` is repo-relative (so the receiver's per-job clone can actually find the file). IC-006 amended v3.0.0 → v3.1.0 (additive MINOR within `dekfactory-ic-006/v3`; no protocol_version literal change — pre-feature servers continue to interoperate via the absent-field fallback). 5 new tests; full suite 2821 pass / 112 skip.

### Fixed

- **`dekspec exec dispatch` populates `repository_scope`** (closes `ds-lwx9` — PR #47). `tooling/dekspec/cli.py::_build_dispatch_payload` resolves the dispatching repo's name from (1) explicit `repo.scope` in `.dekspec/config.yaml`, (2) fallback to parsing `git remote get-url origin` (HTTPS + SSH URL shapes). Refuses-typed with structured code `missing-repository-scope` when neither resolves; never ships an empty / fabricated scope. Threaded through `Executor.dispatch` ABC + `DekFactoryExecutor.dispatch` + `LocalAgentExecutor.dispatch` + `dispatch_lite`. Resolves the 2026-05-25 dektora `$0.29` wasted dispatch root-cause (DekFactory orchestrator's hardcoded `repository_scope="Dektora/dekfactory"` v0 default fired regardless of dispatching tenant).
- **`dekspec exec dispatch` ships repo-relative `ib_path`** (closes `ds-0xqd` + duplicate `ds-f7df` — same PR #47). `_build_dispatch_payload` now computes `Path(ib_path).resolve().relative_to(repo_root)` where `repo_root = Path(at).resolve()`. Sends the relative path. Refuses-typed when the IB lives outside the consumer repo root (cross-repo IB dispatch is not supported in v0). Resolves the symptom where DekFactory's per-job clone could not locate the IB at the dispatcher's absolute filesystem path.

### Changed

- **IC-006 minor amend** v3.0.0 → v3.1.0: `repository_scope` field added to the dispatch payload schema; refusal vocabulary documented (`missing-repository-scope`, plus the existing cross-repo IB refusal). No `protocol_version` literal change — additive within the v3 protocol. Companion `dekspec/interface-contracts/IC-006-...md` carries the amend; doctor remains clean.

### Closed beads

- `ds-lwx9` (P1) — re-opened from bogus-CLOSED + fixed properly via PR #47.
- `ds-0xqd` (P1) — closed via PR #47 (sibling fix in same commit).
- `ds-f7df` (P2) — closed as duplicate of `ds-0xqd` (both shipped together).

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=5) — baseline library state.

## [v0.88.1] — 2026-05-26

Patch release. Critical dispatch fix: `dekspec exec dispatch` was shipping `compiled_outputs: {}` (empty object) in every IC-006 payload, which DekFactory's post-df-obrx server now hard-rejects with HTTP 400 `empty-compiled-outputs` precondition error. `ds-a761` was bogus-CLOSED on 2026-05-25 with a close-reason claiming the fix landed when the code still hardcoded the empty map. Reopened, fixed properly, re-closed. 4 new tests; full suite 2807 pass / 112 skip.

### Fixed

- **`dekspec exec dispatch` populates `compiled_outputs` via inline compile** (closes `ds-a761` — PR #46). `tooling/dekspec/cli.py::_build_dispatch_payload` now invokes a new `_compile_intent_for_dispatch` helper before assembling the payload — locates the parent Intent via `SpecGraph` (IB metadata + convention-based fallbacks), re-runs `parse_intent` against on-disk markdown (same code path `dekspec check compile` uses), and threads the produced IR JSON into the dispatch payload as `{"intent": <ir_json>, "ib": <ir_json>}`. Refuses-typed on compile failure via new `CompilePreconditionRefusal` exception (structured stderr code `COMPILE_FAILED_BEFORE_DISPATCH`); refusal fires BEFORE the HTTP POST, exits non-zero, never ships an empty map as fallback. Adds `DEKSPEC_DEBUG=1` breadcrumb: prints `dekspec: compiled_outputs: <size>KB, <N> artifacts` to stderr so operators can verify compile actually ran. Smoke test on real LOCKED `IB-001` produced 26.58KB / 2 artifacts for parent Intent. 4 new tests in `tests/test_cli_exec_dispatch_compiled_outputs.py` (happy-path / missing-Intent refuse / mocked parse-error refuse / debug breadcrumb).

### Filed (companion beads — not yet shipped)

Three sibling bugs surfaced by the same monkey-patch trace that landed `ds-a761`; queued for a follow-up release:

- **`ds-j4a2`** (P2 bug): dispatch CLI ships placeholder beads list (`["<unclaimed-for-IB-XXX>"]`) — doesn't consult local `.beads/issues.jsonl` for the actually-claimed beads on the dispatched IB. Even with `compiled_outputs` populated, the executor won't know which bead it's working on.
- **`ds-f7df`** (P2 bug): `ib_path` in the dispatch payload is an absolute filesystem path (e.g., `/home/dfxop/projects/dektora/...`); won't resolve in DekFactory's per-job fresh-clone workspace. Should be repo-relative.
- **`ds-11l6`** (P3 bug): `tooling/dekspec/executor/dekfactory.py:354-357` swallows the `HTTPError` response body — 400s are opaque without source-patching. Recommends `except HTTPError as e: body = e.read(); raise type(e)(f'{e} :: {body!r}') from e` pattern.

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=6) — baseline library state.

## [v0.88.0] — 2026-05-26

Minor bump shipping **INT-093** (sender-side IC-006 mirror of `registered_executor_identities` + new `EXECUTOR_OVERRIDE_NOT_ADMITTED` refusal + IC-006 v3 bump + ADR-023) plus the `ds-j83x` bug fix on the `/dekspec:factory` skill mode bodies. 2 beads closed (`ds-gu70`, `ds-j83x`); 18 new tests; full suite 2803 pass / 112 skip.

### Added

- **INT-093 — Sender-side IC-006 mirror: `registered_executor_identities` + `EXECUTOR_OVERRIDE_NOT_ADMITTED` refusal + v3 bump** (closes `ds-gu70`; pairs with dekfactory `df-6qbl`):
  - `tooling/dekspec/schemas/dekfactory-manifest.schema.yaml` gains an optional top-level `registered_executor_identities` array. Each element is a typed record `{identity, capability_tags, key_sourcing, residency_posture}` (`additionalProperties: false` preserved). Forward-compatible: pre-feature manifests omit the field; absent / empty list means the server does not advertise admitted identities (v2-equivalent behavior preserved).
  - `SUPPORTED_PROTOCOL_VERSIONS` widened to `("dekfactory-ic-006/v1", "dekfactory-ic-006/v2", "dekfactory-ic-006/v3")` so v1/v2 servers + v1/v2 clients continue to interoperate.
  - `dekspec exec manifest` text renderer surfaces a `registered_executor_identities (IC-006 v3)` block with one entry per identity (`capability_tags`, `key_sourcing`, `residency_posture` columns); `--json` carries the full structured payload unchanged.
  - `dekspec exec dispatch --executor-override <identity>` cross-checks the override against the manifest's `registered_executor_identities` set BEFORE the HTTP POST. New structured stderr refusal code `EXECUTOR_OVERRIDE_NOT_ADMITTED` fires when the set is non-empty and the override is missing. Degrades to a one-line stderr warning (and proceeds) when the server omits or empty-publishes the set (v2-equivalent MINOR-evolution behavior preserved).
  - IC-006 amended to v3 (`dekfactory-ic-006/v3`); new sender-side refusal vocabulary documented under §Error Semantics; new §Shared Conventions §Registered identity discovery row.
  - Companion **ADR-023** pins the sender-side responsibility: receiver advertises, sender mirrors + cross-checks, server-side admission enforcement is downstream.
  - 18 new tests across `tests/test_dekfactory_manifest.py` (schema validation) + `tests/test_cli_exec_manifest.py` (text + JSON rendering) + `tests/test_cli_exec_dispatch_executor_override.py` (cross-check refusal + warn-only degraded path).

### Fixed

- **`/dekspec:factory` mode bodies** (closes `ds-j83x`): replaced stale `--machine-readable` flag with the actually-accepted `--json` flag across the `executions ls` invocations in `logs.md`, `health.md`, `doctor.md`. Also fixed `logs.md` Step 2 JSON field list to match the actual `dekspec exec executions ls --json` shape (was `package_sha`; correct field is `compile_run_id`); column header `PACKAGE` → `RUN-ID`. Scope-corrected mid-flight: bead body claimed 6 files needed the swap but `dekspec exec active list` correctly accepts `--machine-readable` (not `--json`); only the 4 `executions ls` invocations across 3 files were broken. Operator divergence noted in PR #44.

### Cross-repo pairing

INT-093 is the dekspec sender-side half of a paired feature. The DekFactory receiver-side (`df-6qbl` — schema add + manifest builder + WS-015 BR row) ships separately in the dekfactory repo. Existing pre-INT-093 dekspec clients continue to dispatch without the cross-check; v3-aware clients gain it when the server advertises the set; pre-v3 servers continue to interoperate unchanged via the warn-only degraded path.

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=5) — baseline library state.

## [v0.87.0] — 2026-05-26

Minor bump shipping two LOCKED Intents: **INT-091** (spec-mode + authoring discipline guardrails — provisional-first reminder, `intent-author` DRAFT default, `update-index` variable-column rows) and **INT-092** (sender-side `DispatchPayload.base_branch` support — derives from cwd HEAD, push-first refusals, IC-006 v2 amend, ADR-022). 6 IU beads closed (`ds-2hxc` + `ds-9ba7` + `ds-8r7m` under INT-091; INT-092 went bead-as-spec direct). ds-wu45 closed WONTFIX (deprecation aliases unnecessary for pre-1.0 library with 2 known consumers). 21 new tests across the two Intents; full suite 2777 pass / 112 skip.

### Added

- **INT-091 — spec-mode + authoring discipline guardrails** (closes `ds-6ujt`):
  - **R1** — `/dekspec:spec-mode --on` now emits a provisional-first authoring-discipline reminder block when the next request would author a NEW Intent or Mission (heuristic: user message mentions "draft an Intent / Mission / INT-NNN / MSN-NNN" without a current provisional dir). `dekspec repo init` scaffolds a consumer-side `CLAUDE.md` carrying `## DekSpec Guardrails` (provisional-first, no-specless-edits, dogfood-gate, locked-immutable). 6 new tests. Bead `ds-2hxc`.
  - **R2** — `plugins/dekspec/agents/intent-author.md` hardened: status MUST be `DRAFT` at creation time (was "defaults to DRAFT" — drift target); explicit refuse-typed exception for `PROPOSED`-at-create requiring `--analyzed` evidence; mandatory 7-section scratch-pad scaffolding. 5 new tests. Bead `ds-9ba7`.
  - **R3** — `plugins/dekspec/skills/_lib/scripts/artifact_ops.py::update_index()` derives the appended-row shape from the index header (variable column count, Status placed in the `Status`-labelled column), refuses-typed via `ValueError` when no header is present. Back-compat preserved for callers that already pass shape-correct rows. 6 new tests. Bead `ds-8r7m`.
- **INT-092 — Sender-side `DispatchPayload.base_branch` support** (closes `ds-vzpz`; pairs with dekfactory `INT-053`):
  - New optional `--base-branch <ref>` flag on `dekspec exec dispatch`; when absent, the sender derives the value from `git -C <cwd> rev-parse --abbrev-ref HEAD`. Three new structured stderr refusal codes fire BEFORE the HTTP POST: `BASE_BRANCH_DETACHED_HEAD`, `BASE_BRANCH_NOT_ON_REMOTE`, `BASE_BRANCH_EXPLICIT_OVERRIDE_INVALID`.
  - `DekFactoryExecutor.dispatch(...)` gains optional `base_branch` kwarg (forward-compatible default `None`); when present, the value is threaded into the IC-006 dispatch payload as a top-level `base_branch` field.
  - IC-006 amended to v2 (`dekfactory-ic-006/v2`); `SUPPORTED_PROTOCOL_VERSIONS` widened to `("dekfactory-ic-006/v1", "dekfactory-ic-006/v2")` so v1 and v2 servers continue to interoperate.
  - Companion **ADR-022** pins the sender-side derivation + validation responsibility (receiver-side MR-target choice is downstream).
  - 10 new tests in `tests/test_cli_exec_dispatch_base_branch.py` (real git fixtures with origin remotes — no mocks).

### Cross-repo pairing

INT-092 is the dekspec sender-side half of a paired feature. The DekFactory receiver-side (INT-053 — `base_branch` clone-branch override + MR-target shift) ships separately in the dekfactory repo. Existing pre-v0.87.0 dekspec clients continue to dispatch without `base_branch`; v0.87.0+ clients send it; v0.87.0+ dekfactory honors it; the pre-feature DekFactory default-branch fallback path remains the no-`base_branch` behavior for forward+backward compatibility.

### Closed beads (operator decision)

- `ds-wu45` — `/dekspec:factory-*` deprecation aliases — closed WONTFIX. Pre-1.0 library + 2 known consumers (Dektora + DekFactory) make alias plumbing unnecessary; consumers update slash-command invocations to factory-* names directly per the v0.86.0 migration table.

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=4) — baseline library state.

## [v0.86.0] — 2026-05-25

Minor bump shipping the **/dekspec:factory skill family** + supporting **`dekspec exec` CLI substrate** per INT-090. Three existing executor-side skills are renamed under a unified `factory-*` prefix to expose the conceptual model — every executor backend (local subprocess, inbox queue, dekfactory HTTP) is a *factory* that consumes LOCKED IBs and produces code. A new `/dekspec:factory` diagnostics skill exposes 8 modes via the INT-087 Mode Index lazy-load pattern (2nd user of the convention). Two new CLI verbs land — `dekspec exec dispatch --executor-override <identity>` (pin runner identity per dispatch) and `dekspec exec manifest` (fetch admitted runner identities from the active executor). 4 prior beads close by folding (ds-1p2c dup; ds-gs9o /write-ibs --lock; ds-qddf + ds-63ec folded into ds-isv9). 20 new tests; full suite 2753 pass / 112 skip.

### Added

- **INT-090 — /dekspec:factory diagnostics skill** with 8 modes (`--manifest`, `--active`, `--config`, `--ping`, `--health`, `--doctor`, `--logs`, `--help`) via INT-087 Mode Index lazy-load. Per-mode bodies in `plugins/dekspec/skills/factory/modes/<mode>.md`; top-level `SKILL.md` is dispatcher-only. Wraps existing `dekspec exec active` / `dekspec exec config` verbs + the new `dekspec exec manifest` verb shipped in the same bead set. Closes `ds-wdqg`.
- **`dekspec exec dispatch --executor-override <identity>`** flag — opt-in; absence preserves current default-executor behavior. Per-kind semantics: `local` = no-op + stderr warn; `inbox` = warn (heterogeneous workers undiscoverable from dekspec side); `dekfactory` = threaded into POST body as optional top-level `executor_identity` field (IC-006 v1 MINOR-path evolution per §Change impact). Closes `ds-qddf`.
- **`dekspec exec manifest [--at <repo>] [--config <path>] [--json]`** verb — fetches the active executor's manifest (admitted runner identities, protocol_version, capabilities). Per-kind: `local` synthesizes single-identity manifest; `inbox` synthesizes per-claim note; `dekfactory` HTTP fetch via existing `DekFactoryExecutor._manifest()`. Default human-readable; `--json` for machines. Exit codes 0/2/3 (success/transport/protocol_version mismatch). `dekspec manifest` shortcut wired via LEGACY_COMMANDS. Closes `ds-63ec`.
- **`scripts/check-factory-aliases.sh`** — CI gate asserting all 3 legacy slugs (`dekspec-run-session`, `dispatch-intent`, `dispatch-inbox-listener`) resolve to their `factory-*` siblings. Verification predicate of INT-090.
- **2 new test files**: `tests/test_cli_exec_manifest.py` (14 tests), `tests/test_cli_exec_dispatch_executor_override.py` (6 tests).
- **PR #40 — `/write-ibs --lock` mode body** (closes `ds-gs9o`). Previously the routing listed `--lock` in `inline_modes` but no `## Lock Mode` body existed, making LOCKED IBs unreachable through the canonical authoring skill. New 6-step Lock Mode body: status check → parent-WS gate → cohort-coherence gate → audit re-run → `artifact_ops.py transition --from ACCEPTED --to LOCKED` → report. 9 new tests in `tests/test_skills_write_ibs_lock.py`.

### Changed

- **BREAKING (skill catalog)**: 3 executor-side skill slug renames per INT-090 IU-1:
  - `dekspec-run-session` → `factory-dispatch` (command-shim rename)
  - `dispatch-intent` → `factory-dispatch-intent` (skill-directory rename via `git mv`)
  - `dispatch-inbox-listener` → `factory-listen` (skill-directory rename via `git mv`)
  - SKILL.md body bytes preserved; only `name:` frontmatter + on-disk slug + manifest entry changed.
  - **Deprecation-alias plumbing**: NOT shipped in this release — the Claude Code plugin framework does not currently support a `command_aliases` field. Follow-up bead `ds-wu45` tracks the alias work for when upstream lands the capability. Consumer scripts using the old slugs MUST update to the new names.
- **INT-043, INT-055, INT-076** (LOCKED Intents): `components_affected` globs refreshed via `--unlock` + edit + `--lock` cycle to retarget the renamed skill directories. Amendment Log on each carries the verbatim reason "Update stale components_affected glob string after IU-1 of INT-090 renamed the underlying skill — pure path-string fix, no behavioral change".
- **`tooling/dekspec/fidelity_audit/linkage.py::_SKILL_CLASS_DEFAULTS`** registry — register `factory`, `factory-dispatch-intent`, `factory-listen` (mirror the dispatch-intent / dispatch-inbox-listener entries that already existed pre-rename; add `factory` under a new `diagnostic` skill class with `Read Bash` allowed tools and `disable-model-invocation: true`).
- **`docs/dekspec-skill-flag-defaults.md`** — mirror the defaults table additions; bumped skill-class count 5 → 6.

### Deprecated

- The 3 legacy skill slugs (`dekspec-run-session`, `dispatch-intent`, `dispatch-inbox-listener`) — removed entirely (no alias window per the above; `ds-wu45` tracks the alias work for a future release when upstream supports it).

### Migration notes (consumer-facing)

Consumer repos that invoke any of these slash-commands must update:

| Old | New |
|---|---|
| `/dekspec:dekspec-run-session` | `/dekspec:factory-dispatch` |
| `/dekspec:dispatch-intent` | `/dekspec:factory-dispatch-intent` |
| `/dekspec:dispatch-inbox-listener` | `/dekspec:factory-listen` |

CLI verbs (`dekspec exec ...`) are NOT renamed. The new `dekspec exec dispatch --executor-override` flag is purely additive (opt-in).

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=3) — baseline library state.

## [v0.85.1] — 2026-05-25

Patch release. Brownfield-recovery hygiene: the lifecycle-correctness-hardening work that shipped in PR #37 (terminal-state guards + `LifecycleStateError` + `reap_stale_attempts` + `migrate()` PRAGMA driver + `dekspec lifecycle reap-stale` CLI verb + `scripts/check-stale-open-attempts.sh` wrapper) was off-spec — no LOCKED Intent claimed those four behaviors. INT-089 retroactively claims them via `/dekspec:archeology --propose-intent` and walks the full DRAFT → PROPOSED → ACCEPTED → LOCKED lifecycle (ADR-017 Path B; 0 downstream WS/IC/IB). Also gitignores the local `.flywheel-source-of-record/` snapshot directory used for the deferred Phase B-2 (MSN-016 provisional re-authoring) work. No tooling code, schema, CLI verb, or audit-rule changes — library version travels because the self-spec graph did.

### Added

- **INT-089 (LOCKED) — Retroactive Lifecycle Correctness Hardening.** Authored via `/dekspec:archeology --propose-intent tooling/dekspec/lifecycle.py` after PR #39 (the original canonical-numbering MSN-016 spec-layer attempt) was closed unmerged. Captures the four behaviors that shipped on main without a containing LOCKED Intent — `LifecycleStateError`, `reap_stale_attempts`, `migrate()`, and the `dekspec lifecycle reap-stale` CLI verb + `scripts/check-stale-open-attempts.sh` wrapper. Linked AE-001. Locked via ADR-017 Path B because 0 downstream WS/IC/IBs were produced (the 3 IUs are closed beads `ds-6ety` + `ds-1yjb` + `ds-kcdu`; L4 beads are excluded from the Path B gate per ADR-017).
- **`.gitignore`** — adds `.flywheel-source-of-record/` so the 32-file local snapshot of the closed PR #39 content (held for the Phase B-2 provisional re-author pass under `dekspec/provisional/msn-016-flywheel/`) doesn't accidentally get tracked.

### Changed

- **`dekspec/intent-index.md`** — new INT-089 row in the Archive table (Status `LOCKED`).
- **`dekspec/architecture-elements/AE-001-dekspec.md`** — `Related Intents` backlink updated to include INT-089 via `dekspec audit relink`.

### Dogfood gate

`dekspec audit doctor --at .` returns ADVISORY (P0=0 P1=0 P2=0 P3=3) — baseline library state.

## [v0.85.0] — 2026-05-25

Minor bump with two breaking changes (Intent statuses + CLI verb retirement), the write-intent Mode Index lazy-load refactor, three new ergonomics flags on `/write-intent` and `/orchestrate-intent`, a new lifecycle stats verb, three P2 parser/audit/index bug fixes, and a stack of skill-body governance work (CLI verb drift gate, OVERSIZED flow extraction, audit-surface description harmonization). Closes the critique-2026-05-25 surface-batch (12 beads) plus 4 follow-up beads. 47 new tests; full suite 2722 pass / 112 skip.

### Added

- **INT-088 — `/write-intent --amend --editorial` flag** for editorial diffs that should NOT trigger the PROPOSED → DRAFT or ACCEPTED → DRAFT status cascade. Records the change with `Type=editorial` in the Amendment Log. REFUSES with a named-field error if the diff touches any behavioral field (Verification, Components affected, Acceptance Criteria, IU list). Helper lives in `plugins/dekspec/skills/_lib/scripts/artifact_ops.py` (`classify_intent_diff` + `editorial_amend` + the `editorial-amend` CLI subcommand); re-exported via `plugins/dekspec/skills/write-intent/_lib/editorial_guard.py`. 15 tests (`tests/test_skills_write_intent_editorial.py`). Tracks `ds-write-intent-amend-editorial-flag-4n83`.
- **INT-088 — `/write-intent --lite` path** for single-IU single-component Intents. Skips `--analyze` and `/create-beads`; routes the Intent itself to `/run-coding-session` as the work unit. `--testpass` still runs. Hard-gates: REFUSES unless `components ≤ 1 AND ius ≤ 1 AND adrs:[] AND ics:[]`. Sets `lite: true` frontmatter marker so auditors can identify lite-path Intents in retrospect. Helper in the same `artifact_ops.py` (`lite_gate_check` + `lite_mark` + `lite-gate` / `lite-mark` CLI subcommands); re-exported via `plugins/dekspec/skills/write-intent/_lib/lite_gate.py`. Audit script `scripts/audit-lite-path-intent.sh`. 19 tests (`tests/test_skills_write_intent_lite.py`). Tracks `ds-write-intent-lite-single-iu-path-k5cl`.
- **INT-088 — `/dekspec:orchestrate-intent --auto` mode** drives the full Intent lifecycle (PROPOSED → ACCEPTED → DECOMPOSE → IMPLEMENTING → TESTPASS → LOCK) without per-step engineer prompts. REFUSES on the first unmet pre-condition with a named-gate error; the Intent stays in its starting state. MUST NOT unlock any LOCKable artifact. MUST NOT bypass `--testpass`. Optional retrospective summary card (informational, not gating). Governed by ADR-021. Tracks `ds-opt-orchestrate-intent-interactivity-marketing-4jrl`.
- **ADR-021 — `/orchestrate-intent --auto` lifecycle walker safety contract.** Authored under INT-088 §Open Issue OI-B, accepted 2026-05-25. Documents the refuse-on-unmet-precondition / never-unlock / no-bypass-of-testpass contract end-to-end (`dekspec/adrs/ADR-021-orchestrate-intent-auto-safety-contract.md`).
- **INT-087 — `/write-intent` Mode Index lazy-load refactor.** `plugins/dekspec/skills/write-intent/SKILL.md` rewritten as a Mode Index + dispatcher (841 → 200 lines); per-mode bodies live in `plugins/dekspec/skills/write-intent/modes/<mode-name>.md` (16 files: create, analyze, accept, decompose, testpass, lock, unlock, sync, audit, review, amend, approve, help, teaching, fan-out, provisional). Per-mode load (scaffolding + one mode body) is now < 9,500 tokens — verified by `scripts/measure-skill-load.sh`. Byte-equivalence parity check at `scripts/check-write-intent-mode-parity.sh` (with snapshot baselines under `tests/baselines/write-intent-modes/`). Tracks `ds-write-intent-skill-split-lazy-load-0tb4`.
- **AE-006 — Mode Index lazy-load pattern documentation.** New §Patterns section in `dekspec/architecture-elements/AE-006-skills-library.md` describing the per-mode body split pattern + reference scripts + first instance (INT-087).
- **CLI verb drift gate** at `scripts/check-cli-verb-drift.sh` + the canonical-CLI-invocations doc at `plugins/dekspec/skills/_lib/cli_verbs.md`. CI step wired in `.github/workflows/ci.yml` between lint and pytest. Skills referencing a retired DekSpec CLI verb fail the gate. Active + retired verb registry maintained centrally.
- **OVERSIZED Splitting & Mission Scaffolding Flow** extracted to `plugins/dekspec/skills/_lib/oversized_splitting.md` (previously duplicated verbatim across `/write-intent` and `/dekspec:orchestrate-intent` skill bodies).
- **Mission Verification worked examples** appended to `plugins/dekspec/skills/write-mission/SKILL.md` § Rules — one workflow-shaped, one safety-shaped, each with explicit "What this is NOT" anti-example to discourage pytest-fallback shapes.
- **`dekspec lifecycle stats` CLI verb** documenting attempt-window vs merge-window semantics in `--help`. Output annotates each metric with the appropriate window label. Delegates to `lifecycle.metrics()`. 4 terminal-guard tests in `tests/test_lifecycle.py` (record_execution_event on completed, double-complete, reap-stale --dry-run, reap-stale --apply). Tracks `ds-kcdu`.
- **`tooling/dekspec/lifecycle.py`** — `LifecycleStateError`, terminal-state guards on `record_execution_event` and `complete_execution_attempt`, `migrate()` driver. (Tracks `ds-6ety`.)
- **`scripts/check-stale-open-attempts.sh`** — stale-attempt audit script for the lifecycle table. (Tracks `ds-1yjb`.)
- **Two retirement followup beads filed:** `ds-retire-intent-status-todo-testfail-ppyx` (E3 audit Tier 1) and `ds-retire-promote-provisional-cli-verb-5nul` (F2 audit) — both closed in this release.

### Changed

- **CLI verbs forward-renamed across 16 skill body files** to match the current canonical forms: `dekspec validate` → `dekspec check validate` (9 skills); `dekspec relink` → `dekspec audit relink` (11 skills, with overlap). Eliminates the `[DEPRECATED]` noise that fired on every skill close-step pass.
- **`/dekspec:dekspec-validate` / `/dekspec:dekspec-audit` / `/dekspec:dekspec-doctor` descriptions harmonized** so each one names the others and locates the asker on the narrowing scale (validate ⊂ audit ⊂ doctor).
- **`/dekspec:orchestrate-intent` description + body rewritten** to drop the "premium orchestrator" framing and accurately surface the skill as a guided, interactive lifecycle walker (engineer-in-the-loop; not autonomous — autonomous walks now happen via `--auto`, see above).
- **12 skill body files scrubbed** of the retired `dekspec repo promote-provisional` CLI verb. 42 occurrences replaced with hand-promote workflow references pointing at `docs/dekspec-operating-guide.md` §Provisional Promotion: `write-ae`, `write-adr`, `write-ws`, `write-sp`, `write-ibs`, `write-ic`, `write-mission` (×6), `write-sv`, `write-constitution`, `write-ggc`, `write-intent/modes/provisional.md` (×4), `write-intent/modes/accept.md` (×2). Tracks `ds-scrub-promote-provisional-skill-bodies-ncjw`.
- **ADR-021 editorial doc-drift fix** — three sites referencing TESTFAIL as a Status value (stale post-retirement) updated to the correct post-retirement semantics (TESTFAIL is a log-row label; Status stays at IMPLEMENTING). Dogfooded `/write-intent --amend --editorial` on INT-087 4× D19 numeric-target findings; the cascade contract held end-to-end.

### Fixed

- **L15-INDEX-FILE-COHERENCE substring collision** — the L15 audit rule used `INT-\d{3,}` with `re.search()` which matched `INT-007` as a substring of `P-INT-007` link cells, letting a provisional row shadow the canonical row's index entry. Fixed by anchoring each ID pattern with `(?<![A-Za-z0-9-])` left guard + `(?!\d)` right guard, applied uniformly across all six index targets (ADR, AE, IC, INT, WS, MSN). 3 regression tests. Tracks `ds-audit-linkage-l15-substring-collision-rgrx`.
- **WS Open Issues severity regex** rejected backtick-quoted forms (e.g. `` `P3` ``) even though the WS template seeded rows with them. Regex widened to accept optional surrounding backticks + leading-whitespace mis-capture fix. The normalizer remains the single source of truth for canonical severity mapping. 10 regression tests. Tracks `ds-ws-open-issues-severity-backtick-parse-w0ut`.
- **`artifact_ops.py update_index` substring match** flipped the wrong row when the target ID appeared verbatim inside another row's body cell (Title / description). Match now anchored on the row's ID cell (column 1) only. 1 regression test. Tracks `ds-update-index-substring-match-wrong-row-bbhe`.

### Removed

- **`dekspec repo promote-provisional <slug>` CLI verb retired** (per F2 audit 2026-05-25 — zero invocations in repo history; every promotion was hand-promote). The underlying promotion logic (`dekspec.promote.plan_promotion` / `apply_promotion` / `render_plan` / `PromoteError` / `PromotionStep`) stays for the hand-promote workflow and tooling that needs to drive the renumber programmatically; see `docs/dekspec-operating-guide.md` §Provisional Promotion. The drift gate (`scripts/check-cli-verb-drift.sh`) now flags the verb so it can't resurface in skill bodies.
- **Intent statuses `TODO` and `TESTFAIL` retired** (per E3 audit 2026-05-25 — neither status had been observed across 99 Intents in repo history; the `TESTFAIL ↔ TESTPASS` round-trip never fired). `dekspec check validate` now rejects Intent files setting these values with a targeted error message that names the retired token and points at the replacement (`DRAFT` for `TODO`, `IMPLEMENTING` for `TESTFAIL`). The TESTFAIL records section in the Intent template stays as a captured-failure log on the IMPLEMENTING → TESTPASS path; a failed `--testpass` now appends a record and leaves Status at `IMPLEMENTING` rather than flipping to a (now-defunct) `TESTFAIL` status. Affected surfaces: Intent IR schema enum (`tooling/dekspec/schemas/intent.schema.yaml`), parser `_INT_VALID_STATUSES` + status extractor (`tooling/dekspec/constraint_compiler/parser.py`), Intent-index active-queue set (`tooling/dekspec/index_ops.py`), AGENTS.md in-flight statuses (`tooling/dekspec/cli.py`), audit-engine status sets (`tooling/dekspec/fidelity_audit/linkage.py`), Intent + lite-intent templates (`templates/intent-template.md` + `templates/lite-intent-template.md`), `/write-intent` + `/orchestrate-intent` skill bodies, the serialization advisory, the index-update helper, the methodology + operating-guide docs. Tracks `ds-retire-intent-status-todo-testfail-ppyx`.

## [v0.84.3] — 2026-05-24

Patch: fix the release skill's documented invocation namespace. The skill lives in the `dekspec-maintainer` plugin (per its `plugin.json` `name` field), so the correct route under Claude Code's `<plugin-name>:<skill-name>` convention is `/dekspec-maintainer:release` — but every prose mention across the plugin tree said `/dekspec:release`, which routes against the consumer `dekspec` plugin where no `release` skill exists. The harness fuzzy-matches an unknown skill against the addressed plugin's catalog; operators invoking `/dekspec:release` would land on `create-beads` or another near-name miss instead of the release flow.

### Fixed

- **Renamed `/dekspec:release` → `/dekspec-maintainer:release` across the plugin-surface prose.** Six files updated, in lockstep:
  - `plugins/dekspec-maintainer/.claude-plugin/plugin.json` (description).
  - `plugins/dekspec-maintainer/commands/dekspec-release.md` (frontmatter description).
  - `plugins/dekspec-maintainer/skills/release/SKILL.md` (7 mentions — title heading, argument-grammar block, every reference to `--apply` / `--push` / dry-run / done states).
  - `plugins/dekspec-maintainer/README.md` (2 mentions — top-of-file pitch + architecture-rationale autocomplete callout).
  - `.claude-plugin/marketplace.json` (description; also names the shorter `/dekspec-release` slash-command alias).
  - `RELEASING.md` (canonical-path line; also surfaces the `/dekspec-release` slash-command alias).

### Notes

- The slash-command surface at `plugins/dekspec-maintainer/commands/dekspec-release.md` already routed correctly as `/dekspec-release` (slash commands take the file basename, not the plugin namespace). Operators preferring the shorter form can continue to use that — both surfaces delegate to the same `skills/release/SKILL.md` body.
- Self-spec mentions of `/dekspec:release` under `dekspec/` (INT-017 title, AE-006 amendment-log entry, MSN-012 §154 comparison, `dekspec/intent-index.md` row) and the auto-generated `AGENTS.md` are intentionally left as-is: LOCKED artifacts cannot be edited without going through the artifact's skill's `--unlock` / `--lock` cycle, and AGENTS.md is regenerated from the same source files. A future engineer-driven update can refresh those if the historical-title drift becomes a discoverability problem.

## [v0.84.2] — 2026-05-24

Patch: extend the `dekspec dev graph export --include` filter to cover SP + CONSTITUTION.

### Fixed

- **`dekspec dev graph export --include SP` and `--include CONSTITUTION` now work.** `cmd_graph_export` valid-kinds set previously enumerated `{AE, ADR, WS, IC, IB, INT, MSN, GLOSSARY, VISION}` — omitting SP and CONSTITUTION even though both have first-class IR shapes, schemas, and parsers, and the graph loader resolves both as nodes. Added "SP" + "CONSTITUTION" to both the valid set and the prefix_map (using `SP-` for SP and the literal singleton id `CONSTITUTION` for the L0 constitution, mirroring the existing SYSTEM-VISION / DOMAIN-GLOSSARY handling). Verified `dekspec dev graph export --include SP --at .` returns the SP-001 node and `--include CONSTITUTION` returns the CONSTITUTION node.

### Known gaps still open (called out for the next cycle)

- `_emit_side_coverage` (`tooling/dekspec/cli.py`) still declares the consumed-vs-parse-only field split for AE / ADR / WS / IC / IB / Intent / Mission only — SP, VISION, GLOSSARY, CONSTITUTION rows are missing. The aggregator emits fragments for these kinds, but the declarative summary engineers can grep doesn't list their field splits. Additive doc-only task; needs per-emitter field knowledge.
- `cmd_audit_lock_ready` filter at `tooling/dekspec/cli.py` still restricts to AE / ADR / WS / IC. Extending requires ADR-020 per-kind lock-readiness criteria for INT / MSN / SP / IB to be defined first.
- `docs/cli-reference.md` regen — no `scripts/gen-cli-reference.py` exists in the tree. Needs an authoring IB.

## [v0.84.1] — 2026-05-24

Patch: widen L15 audit coverage to include WS + MSN indexes (rule was half-blind by oversight), and refresh the stale AGENTS.md stamp.

### Fixed

- **`L15-INDEX-FILE-COHERENCE` now audits `working-spec-index.md` and `mission-index.md`.** `_INDEX_COHERENCE_TARGETS` previously enumerated ADR / AE / IC / Intent indexes only — the rule's own comment ("No index is excluded") was factually wrong. WS + MSN are now covered; drift between an artifact's Status and its index row is detected for both kinds. Underlying loop reuses the same parser code path already exhaustively tested via the existing 13 L15 tests; no new fixtures needed because the additions are pure data, not behavior.
- **AGENTS.md regenerated.** The compiled aggregate was stamped `dekspec 0.75.1` (five releases stale). Re-ran `dekspec check aggregate agents-md`; byte-stable beyond the (excluded-by-design) timestamp + version preamble lines.

### Notes

- AGENTS.md will be regenerated again as part of subsequent release cycles when the spec graph changes. The post-merge hook surfaces drift but does not auto-regen.

## [v0.84.0] — 2026-05-24

Init-scaffold completeness sweep. Two artifact subdirectories that consumers were silently missing on first `dekspec init` are now scaffolded, and the audit-v2 Phase 2J fitness-functions registry gets a placeholder stub so the audit no-ops cleanly instead of emitting `[fidelity:fan-out-unrunnable]`. Additive only.

### Added — `_INIT_SUBDIRS`

- **`security-profiles/` added to the full-profile init scaffold.** Previously missing — SP-001 has been a tracked artifact since INT-007 / ADR-011, but `dekspec init` did not scaffold its home directory, forcing `/write-sp` to mkdir on first use and leaving `dekspec audit doctor` on a just-initialized repo with a silently-absent canonical home. Lite profile unchanged (SP is full-profile material).
- **`audits/` added to the full-profile init scaffold.** New canonical home for audit-profile configuration files, ahead of the registry add below.

### Added — Audit fitness-functions registry

- **`dekspec/audits/spec-fitness-functions.md` placeholder.** Hand-authored registry consumed by `/run-dekspec-fidelity-audit-v2` Phase 2J as the Sibling-SSoT duplication-scan invariant catalog. New `_INIT_AUDIT_FILES` tuple + write loop in `dekspec init` seeds an empty-registry-shaped stub on full-profile init (lite skips it). Placeholder body documents the per-invariant schema (id / fact / canonical_home / pattern / scopes / one-of(expected_count|unbounded_with_citation|forbidden) / severity / optional citation_distance_lines) and says "No invariants registered yet" so Phase 2J no-ops without finding-noise.
- **Library-side seed file at `dekspec/audits/spec-fitness-functions.md`.** Empty body with a note that the version-triad mirrors are already covered by `scripts/bump-version.py --check`, so the first invariant should not be wasted on that case — registry stays empty until a recurring sibling-SSoT drift source emerges.

### Fixed — Test drift

- **`tests/test_init.py::test_init_creates_full_tree` realigned.** Expected-dirs list was already drifted before this release (missing `provisional/` even though it has been in `_INIT_SUBDIRS` since the provisional-folder design landed). Now covers the full set: `adrs`, `architecture-elements`, `working-specs`, `interface-contracts`, `impl-briefs/{queued,active,completed}`, `intents`, `missions`, `security-profiles`, `audits`, `divergences`, `provisional`. Plus an explicit assertion that `dekspec/audits/spec-fitness-functions.md` is a file post-init.
- **`tests/test_lite_init.py::_FULL_ONLY_DIRS`** gains `security-profiles` and `audits` so the lite-omits-this-dir assertion covers both new full-profile subdirs.

### Notes

- No behavior change for already-initialized repos (init is idempotent; existing dirs are skipped). Behavior change is for fresh inits only: they now get `dekspec/security-profiles/.gitkeep` + `dekspec/audits/.gitkeep` + `dekspec/audits/spec-fitness-functions.md` out of the box.

## [v0.83.2] — 2026-05-24

Tracking-only patch. Brings the library's own self-spec into alignment with what `dekspec init` actually writes.

### Added

- **`dekspec/guidance-and-corrections.md` now tracked at the library level.** Co-equal `dekspec init` singleton alongside `system-vision.md` and `domain-glossary.md`; the other two were tracked but g&c was never staged. Empty placeholder content (`_No corrections logged yet._`) — future `/write-ggc --log` runs against this repo now append to a checked-in file, and the `/run-dekspec-fidelity-audit-v2` Phase 2H composite-term auto-promotion sink resolves cleanly under ADR-007 eat-own-cooking.

## [v0.83.1] — 2026-05-24

Docs-only patch. Preserves the 2026-05-24 audit verification report that drove v0.82.0 + v0.83.0 as a permanent archive record.

### Added

- **`docs/archive/audit-2026-05-24-vendoring-reconcile-audit.md`** — archived copy of the consolidated audit verification report (formerly at the untracked `dekspec/workspace/consolidated_audit_verification_report.md`) with a 5-line preface mapping its verified items to the resolution commits (`6010a55`, `de01a3f`, `65d549c`) and noting the items still open as of the archive date.

### Removed

- **`dekspec/workspace/` directory** — the six scaffolding files (per-model raw reports + intermediate consolidated analysis / tradeoff documents) were deleted as ephemeral. Only the verification report had load-bearing forensic value; it landed under `docs/archive/`.

### Notes

- Follows the existing precedent at `docs/archive/audit-2026-05-11-system-audit.md`.

## [v0.83.0] — 2026-05-24

Vendoring spec reconcile. Closes the long-running ADR-009 ↔ AE-008 contradiction (ADR-009 declared an `rsync` + skills-vendoring pipeline; AE-008 + the installer + the Python vendoring module had all moved to plugin-only skills + `find`/`cp` + snapshot-based pruning, leaving the load-bearing ADR factually wrong). Walked ADR-009 through the full canonical `--accept` / `--lock` lifecycle via `/dekspec:write-adr`. Also adds methodology-doc vendoring, which the installer had been quietly omitting despite CLAUDE.md "Foundational reading order" #2 pointing consumers at it.

### Changed — Spec reconcile (ADR-009)

- **ADR-009 body amended.** New title: "Vendoring via manifest-aware file copy + drift verification (plugin-only skills)" (was "Vendoring via rsync + drift verification"). Decision and Consequences sections rewritten to record that (a) skills / commands / agents / hooks ship exclusively through the Claude Code plugin marketplace at `plugins/dekspec/` per AE-006 (not vendored by the installer), (b) the installer copies templates + cherry-picked methodology docs via portable `find` / `cp` (no `rsync` runtime dependency), and (c) pruning is snapshot-based via `.dekspec-vendor-manifest`, not `rsync --delete`. Filename retained for stable link identity; a "Filename note" section documents the historical-title vs canonical-title divergence.
- **ADR-009 walked LOCKED → PROPOSED → ACCEPTED → LOCKED via `/dekspec:write-adr`.** `--accept` Step 2 fan-out audit returned PASS 11/11 with clean supersession check (subagent scanned ADR-010 through ADR-020 for contradiction; none found). `--lock` Step 2 inline pre-lock audit re-verified the same checks plus the ADR-specific extensions (validation criteria concrete + observable, supersession fields accurate both directions, no downstream contradiction). Two non-blocking informational notes about `INT-023:135` + `IB-038:128` still using the pre-amendment "rsync" label in cross-reference rows (historical artifacts whose substantive content matches the amended ADR).
- **AE-008 untouched.** The AE already encoded Shape A reality (plugin-only skills at lines 41-43; snapshot-based pruning; "Plugin vs vendoring are disjoint" constraint). The provisional Intent was filed because ADR-009 had drifted from this AE, not because the AE itself was wrong.

### Added — Methodology doc vendoring

- **`docs/dekspec-methodology.md` joins the vendored doc set.** `scripts/install-dekspec.sh` and `tooling/dekspec/vendoring.py::iter_vendored_pairs()` both now ship the methodology doc to consumers' `dekspec/dekspec-methodology.md`. The vendoring module's docstring layout table updated to match.

### Changed — Doc reconcile

- **CLAUDE.md "What lives where" rewritten.** The `skills/` bullet (which described a non-existent `dekspec/skills/` canonical layout + `.claude/skills/<name>` shim) is replaced with a `plugins/dekspec/` bullet pointing at the actual delivery channel. The `docs/` bullet enumerates the full vendored doc set in manifest order (including the newly added `dekspec-methodology.md`). The `templates/` bullet names the `find`/`cp` manifest-aware copy mechanism.

### Closed out — Provisional Intents

- **`dekspec/provisional/vendoring-reality-reconcile/` pruned.** Work landed via ADR-009 amendment + AE-008 untouched-because-already-correct + CLAUDE.md rewrite. Shape A selected.
- **`dekspec/provisional/methodology-doc-vendoring/` pruned.** Work landed via installer + vendoring.py methodology-doc addition. Shape A selected.

### Notes

- The `--accept` audit subagent flagged two historical-title references (`INT-023` Layer-impact note + `IB-038` cross-reference row) as informational. Both are LOCKED archived artifacts whose substantive content (`.dekspec-vendor-manifest`, snapshot pruning, `vendor_from()`) is consistent with the amended ADR — only the human-readable ADR title in their cross-reference rows is stale. Not blocking; an editorial cleanup bead may be filed later if the stale labels become a source of confusion.
- `dekspec/adr-index.md` row for ADR-009 updated to the new title at PROPOSED, then ACCEPTED, then LOCKED in lockstep with each transition via `artifact_ops.py update-index`.

## [v0.82.0] — 2026-05-24

P1 stabilization sweep against the consolidated 2026-05-24 audit verification report (archived later this release cycle at `docs/archive/audit-2026-05-24-vendoring-reconcile-audit.md`). Surface-area additions to `dekspec.api` plus a chain of small bug fixes that close gaps in validate / migration / persistence / template / skill / docs coverage. No spec-level changes — those land in v0.83.0.

### Added — Public API surface

- **`dekspec.api` re-exports.** Added `parse_constitution`, `parse_security_profile`, `emit_constitution_markdown`, `ConstitutionParseError`, `SPParseError`, `apply_status_fixes`, and `PromoteError` (both as imports and in `__all__`). These were already exported from their submodules; the public-API facade was simply incomplete relative to the L0 Constitution + SP-001 surfaces shipped in earlier releases.

### Fixed

- **`cmd_validate` now catches `ConstitutionParseError`.** The `error_classes` tuple at `tooling/dekspec/cli.py` listed every other parse-error class but omitted the Constitution one — a Constitution parse error fell through to an uncaught exception. `cmd_compile` already caught it; the validate dispatch is now symmetric.
- **Migration coverage extended to SP + Constitution.** `_artifact_type_from_id` (registry), `_PREFIX_TO_TYPE` + `detect_artifact_type` (markdown walker), `_ARTIFACT_SUBDIRS` (adds `security-profiles` + `provisional`), and the singleton-walker loop now recognize `SP-` prefixed files and the `constitution.md` top-level singleton. `tests/test_markdown_migrations.py` fixture matrix gains the two missing rows.
- **`_kind_from_artifact_id` in `persistence_index.py` widened.** Recognizes INT / MSN / SP and the singleton SYSTEM-VISION / DOMAIN-GLOSSARY / CONSTITUTION ids. Previously returned `unknown` for any artifact outside the original five (ADR / AE / WS / IC / IB) — index queries on newer kinds silently fell into the `unknown` bucket.
- **`templates/dekspec-config-template.yaml` `executor.kind` flipped `lite` → `local`.** Template wrote the legacy `lite` value, which the loader silently coerces to `local` before schema validation. Prose updated to enumerate the canonical `local` / `inbox` / `dekfactory` set; the schema enum has not contained `lite` since the executor cleavage landed.
- **`/write-intent` SKILL.md validation invocation corrected.** Step 3 fan-out manifest read `dekspec validate intent <output-path>` — a positional shape that errors under the current namespaced CLI. Replaced with `dekspec check validate --kind intent <output-path>`.
- **CLAUDE.md "dogfood gate" claim softened.** Previously declared `dekspec audit doctor --at .` "returns CLEAN today"; the live state has been ADVISORY (P3 + provisional folders tolerated) for some time. Updated to name the actual hard floor (`P0/P1/P2 = 0`).
- **`RELEASING.md` drift fixes.** Wheel-only distribution (sdist publication was dropped per `ds-release-yml-drop-sdist-publish-mh2`; the runbook still claimed "wheel + sdist"). Release skill path corrected from the non-existent `skills/release/SKILL.md` to the actual `plugins/dekspec-maintainer/skills/release/SKILL.md`.

### Notes

- Two provisional Intents (`dekspec/provisional/vendoring-reality-reconcile/` and `dekspec/provisional/methodology-doc-vendoring/`) were also staged this cycle to enumerate Shape A vs Shape B decisions for the engineer on the still-unresolved ADR-009 ↔ AE-008 vendoring contradiction. They land here and are resolved + pruned in v0.83.0.
- Concurrent session appended one new bug row to `.beads/issues.jsonl` (`ds-ws-open-issues-severity-backtick-parse-w0ut`) — tracker state is checked in by design, lands with this release.

## [v0.81.0] — 2026-05-24

Six feature waves consolidated into a single release. Spec coverage spans MSN-014 (provisional artifact incubation system), MSN-015 (deterministic regen of derived outputs), and INT-080/086 (standalone). Eight new LOCKED Intents (INT-079..086), three Missions reaching COMPLETE (MSN-013/014/015), 7 new audit rules, 4 new CLI verbs, 22 Open Issues closed, audit fully CLEAN at the end of the cycle.

### Added — Provisional artifact incubation system (MSN-014; INT-079/082/083/084)

- **`dekspec/provisional/<incubation-slug>/` staging tree.** New directory created by `dekspec repo init`. The constraint compiler walker + linkage audit + AGENTS.md emitter all skip the tree; `<KIND>-provisional-<kebab-slug>` IDs are recognized but unwalked. Spec coverage: INT-079.
- **`dekspec repo new-provisional <KIND> <slug>` CLI verb.** Scaffolds a fresh provisional artifact at `dekspec/provisional/<slug>/<KIND>-provisional-<slug>.md` using the canonical template body. Auto-creates a working-tree branch (`int/INT-...`, `mission/MSN-...`, `feat/<slug>` for others) unless `--no-branch`. Special-cases Mission kind to emit canonical `# Mission MSN-...:` H1 shape. Spec coverage: INT-084.
- **`dekspec repo promote-provisional <slug> [--dry-run]` CLI verb.** Atomic provisional → canonical migration. Classifies each artifact as NEW (no `replaces:`) or REPLACE (carries `replaces: <KIND-NNN>` frontmatter). NEW-mode allocates next-free `<KIND>-NNN`; REPLACE-mode preserves canonical ID + overwrites. Cross-refs inside the bundle are rewritten in lockstep. Mission queue rows are appended. Spec coverage: INT-083.
- **`dekspec repo cow-stage <canonical-path> --incubation <slug>` CLI verb.** Copy-on-write canonical staging — copies a canonical artifact into the incubation folder, stamps `replaces: <KIND-NNN>` frontmatter, idempotent. Singletons use path-as-id (`replaces: constitution`, `replaces: system-vision`, `replaces: domain-glossary`). Spec coverage: INT-082.
- **`--provisional <incubation-slug>` flag on 8 authoring skills** — `/dekspec:write-mission`, `/write-intent`, `/write-adr`, `/write-ae`, `/write-ic`, `/write-ws`, `/write-ibs`, `/write-sp`. Writes to `dekspec/provisional/<slug>/`; `<KIND>-provisional-<slug>` ID shape; prepends `> **PROVISIONAL.**` banner; rejects `--lock`; permits `--review` + `--analyze`. Five skills (`/write-constitution`, `/write-sv`, `/write-ggc`, `/write-evals`, `/write-tests`) intentionally do not accept the flag.
- **`tooling/dekspec/cow_state.py` write-time CoW guard substrate.** `is_path_claimed(repo_root, target)` walks SpecGraph live (no cached state file) to detect canonical edits inside a pre-ACCEPTED Intent's claimed paths. `cow_stage(repo_root, canonical_path, incubation_slug)` performs the copy + `replaces:` stamp.
- **Write-time CoW guard on 11 authoring skills** + ACCEPTED-transition gate with promotion-plan diff + explicit `yes` confirmation + session-start reminder on `/write-intent` + `/write-mission`.
- **`dekspec audit doctor` gains a `provisional` section** between `audit linkage` and `graph parse`. Reports the count of non-empty incubation folders.

### Added — Deterministic regen of derived outputs (MSN-015; INT-085)

- **`dekspec repo regen-indexes [--check] [--at]` CLI verb.** Deterministically rebuilds the 6 derived index files (`intent-index.md`, `mission-index.md`, `adr-index.md`, `architecture-elements-index.md`, `working-spec-index.md`, `interface-contract-index.md`) from the canonical artifact tree. Active queue + Archive table sorted by numeric ID ascending → no merge conflicts on concurrent additions. `--check` reports drift without writing. Per-kind row formatters share a `_regen_single_table_index()` helper.
- **Post-merge git hook.** `templates/git-hooks/post-merge.template` runs `regen-indexes --check` + AGENTS.md drift advisory after every merge. `DEKSPEC_SKIP_POSTMERGE=1` escape hatch. Bootstrap-lenient. `git_hooks.py::_HOOK_NAMES` extended to `("pre-commit", "pre-push", "post-merge")`.

### Added — Skill flag normalization (INT-080)

- **`docs/dekspec-skill-flag-defaults.md`** — canonical defaults table. Five skill classes (authoring / dispatch / recovery / audit / utility); each row pins default `model`, `mode`, `reasoning_effort`, `disable-model-invocation`, `allowed-tools`. Per-skill overrides recorded inline via `# override-reason:` comment.
- **Catalog conformance sweep.** All 24 SKILL.md files normalized to the canonical defaults table.
- **Methodology §Skills section** gains cross-reference to `dekspec-skill-flag-defaults.md` + the T-SKILL-* audit rule trio.

### Added — Seven new audit rules

- **`L-PROVISIONAL-TREE-PRESENT`** (P3 advisory) — one finding per non-empty incubation folder under `dekspec/provisional/`. Reports the slug, the count of artifacts, and the age of the oldest file (mtime-based). Spec coverage: INT-081.
- **`L-PROVISIONAL-STALE`** (P3 advisory) — one finding per incubation folder whose oldest artifact exceeds the configured staleness threshold (one-month default; `audit.provisional_stale_days` tunable). Spec coverage: INT-081.
- **`L-COW-SIBLING-COLLISION`** (P2 semantic) — fires when 2+ pre-ACCEPTED Intents each have a provisional copy of the same canonical artifact. Spec coverage: INT-082.
- **`T-COW-CANONICAL-EDITED`** (P2 mechanical) — fires when `git diff --name-only main` shows a canonical artifact modified while a pre-ACCEPTED Intent claims its glob and no matching CoW staging copy exists. Catches direct-`vim` edits that bypass the skill-level guard. Spec coverage: INT-082.
- **`T-SKILL-FRONTMATTER-NORMAL`** (P2 mechanical) — validates every `plugins/dekspec/skills/<skill>/SKILL.md` frontmatter against the per-class defaults table. Spec coverage: INT-080.
- **`T-SKILL-HELP-MODE-PRESENT`** (P2 mechanical) — asserts every skill exposes a `--help` mode. Spec coverage: INT-080.
- **`T-SKILL-ARG-HINT-COMPLETE`** (P2 mechanical) — asserts every documented argument appears in the skill's `argument-hint:` frontmatter. Spec coverage: INT-080.

### Added — Documentation

- **Operating-guide §Provisional incubation section.** Five-step lifecycle walkthrough (scaffold → CoW → edit + iterate → promote = accept-gate → post-promotion).
- **Operating-guide §Multi-User Coordination section.** Three-layer model: mechanical (INT-020 DRAFT-slug + `id allocate`), cross-MR exploratory (MSN-014 provisional folder), semantic (MSN-010 TODO). Decision rubric + derived-output regen subsection + remaining-gaps deferral list. Spec coverage: INT-086.
- **Quick-reference §Provisional Incubation block** + `--provisional` flag row in §Common Flags + provisional/CoW audit-rule list in §System Integrity + missions/provisional/divergences rows in §Where Things Live.
- **System-vision §What Success Looks Like** gains bullet cross-linking the operating-guide §Provisional incubation + §Multi-User Coordination sections.
- **AE-006 Amendment Log** documents the 5-skill carve-out from the `--provisional` flag.

### Added — Spec artifacts LOCKED

- **8 new Intents LOCKED:** INT-079 (provisional folder scaffold), INT-080 (skill flag normalization), INT-081 (audit treatment), INT-082 (CoW spec staging), INT-083 (promote verb), INT-084 (skill integration), INT-085 (regen-indexes), INT-086 (multi-user coordination analysis).
- **3 Missions COMPLETE:** MSN-013 (multi-CLI reach), MSN-014 (provisional artifact incubation), MSN-015 (deterministic regen of derived outputs).
- **DIV-017 §Resolution appended.** LOCKED-Intent stale globs after skill renames retargeted.

### Changed

- **Antigravity-compat patcher strip-list narrowed.** `plugins/dekspec/hooks-handlers/antigravity-compat.py` strip regex changed from `^reasoning_effort\s*:` (any value) to `^reasoning_effort\s*:\s*max\s*(#.*)?$` (only `max`, plus optional inline override-reason comment). Non-max values (`high`/`medium`/`low`/`minimal`) now pass through to Antigravity unchanged — Antigravity's allowlist accepts them, only `max` is rejected.
- **41 artifacts walked ACCEPTED → LOCKED in a single sweep.** 17 ADRs, 4 AEs (AE-003/004/007/008), 4 ICs (IC-001/002/003/005), 16 WSes. Cleared the long-standing T-STATUS-LOCK-READY P3 advisory queue.
- **WS-016 driven DRAFT → LOCKED.** Three Open Issues settled (plugin-manifest exact path resolved in IB-026 at authoring time but never propagated back; pre-commit hook compat stay-narrow; Cloudsmith URL stability not-a-BR). T-STATUS-INVERSION cleared.
- **22 Open Issues closed across 7 Intents** (INT-079/081/082/083/084/086 + WS-016). Each resolution recorded inline with cite to the implementation that satisfies it.
- **3 P3 deferred `br` beads filed** for INT-086 Remaining Gaps #2/#4/#5 (`ds-int-086-gap-2-unlock-guard-z7qz`, `ds-int-086-gap-4-dekspec-skills-autogen-hjbw`, `ds-int-086-gap-5-migration-concurrency-nfvm`).
- **CLAUDE.md §Cross-repo discipline + §Releasing scrubbed of consumer-notification reminder.**

### Fixed

- **`artifact_ops.read_status()` parser bug.** Status reader previously matched the first inline `**Status:** <val>` body line and short-circuited the `## Status` section heading. IC-005 hit it because two capability subsections used `**Status:** scaffold-only.` as prose. Fixed by flipping precedence in `_read_field`: section heading first, inline only as fallback. Symmetric `_replace_in_section` helper extracted; `_replace_status` + `_replace_modified` mirror the read-side precedence. 2 regression tests added.
- **IC-005 inline `**Status:** scaffold-only.` body lines renamed to `**Capability status:**`.** Tactical workaround pre-parser-fix; kept post-fix because the renamed phrasing is clearer prose.
- **`.gitignore` untracks `tooling/dekspec/_vendored/skills/`.** Materialized by `setup.py::VendoringBuildPy` at wheel-build time like the already-ignored `templates/` and `docs/` siblings.

### Test coverage

- `tests/test_new_provisional.py` (10), `tests/test_promote_provisional.py` (16), `tests/test_cow_state.py` (13), `tests/test_cow_spec_staging.py` (11), `tests/test_cow_canonical_edited.py` (7), `tests/test_provisional_audit_rules.py` (9), `tests/test_skill_audit_rules.py` (15), `tests/test_index_ops.py` (11). Plus 2 regression tests on the `artifact_ops` Status reader.

### Final state

- **Audit fully CLEAN:** P0=P1=P2=P3=0. ir_count=237.
- **Tests:** 2674 passed, 110 skipped.

## [v0.75.1] — 2026-05-23

### Added

- **`dekspec-mcp` MCP server (`tooling/dekspec/mcp/`).** New Anthropic MCP server exposing DekSpec CLI verbs to MCP-aware tools (Claude Desktop, etc.) over the standard transport. New `dekspec-mcp` console-script entry point in `pyproject.toml`. Spec coverage: INT-078 / IB-123.
- **Wheel-time skills vendoring.** `setup.py::VendoringBuildPy` now mirrors `plugins/dekspec/skills/` → `tooling/dekspec/_vendored/skills/` at build, and `pyproject.toml` ships them as wheel package data. This is the prerequisite infrastructure for the MCP server's runtime skill discovery via `vendoring.library_root()` in pip-installed environments where `plugins/` is unreachable. Spec coverage: INT-078 / IB-123.
- **`/dekspec-antigravity-compat` slash command + hooks-handler.** Adapts installed DekSpec plugin skills for Google Antigravity CLI compatibility by stripping Claude Code-specific frontmatter (`reasoning_effort`, `Agent`/`Grep`/`Skill` in `allowed-tools`) in place from `${CLAUDE_PLUGIN_ROOT}/skills/**/SKILL.md`. Idempotent. Spec coverage: INT-078 / IB-122.
- **`/dekspec-skills` discoverability command.** Lists all DekSpec skills and how to trigger them in either Claude Code or Antigravity sessions.
- **`/dekspec:listen` (IB-120) — listener-skill harness-compatibility fixes.** (a) CLI verb rename `dekspec dispatch reap` → `dekspec exec dispatch reap` so the alias-deprecation notice no longer fires on every reaper pass; (b) pin `LISTENER_ID` once at startup, persist to `/tmp/dekspec-listener-<sha-of-cwd>.id`, source on every reuse — the Claude Code harness spawns a fresh shell per Bash tool call so `$$` drifts otherwise; (c) §Pre-flight block that verifies `.dekspec/` exists at cwd before mkdir / reaper / poll, refuses silent filesystem pollution outside an established DekSpec repo.
- **Spec artifacts authored.** INT-078 (cross-CLI integration), IB-120 (listen harness-compat, ACCEPTED), IB-121 (listen narrative dispatch-verb scrub, PROPOSED), IB-122 (antigravity-compat adapter, PROPOSED), IB-123 (MCP server + wheel skills vendoring, PROPOSED). DIVs 013–016 record observational gaps (DIV-013 upgrade-vendors-into-library-repo; DIV-014 stale dispatch verb; DIV-015 LISTENER_ID drift in harness; DIV-016 listen-skill no cwd preflight).

### Fixed

- **Antigravity-compat tokenizer.** `plugins/dekspec/hooks-handlers/antigravity-compat.py` and `tests/test_compat_patch.py` previously tokenized `allowed-tools:` via `tools_part.replace(",", " ").split()`, corrupting `Bash(verb:*)` tokens with internal spaces (~37 plugin files damaged on first run). Replaced with `re.findall(r"Bash\([^)]*\)|[A-Za-z_][A-Za-z_0-9]*", tools_part)` which respects `Bash(...)` as a single token.
- **`dekspec-antigravity-compat.md` self-damaged frontmatter.** The original tokenizer corrupted the command's own `allowed-tools: Bash(python3:*)` line into the unparseable `allowed-tools: Bash *)`. Restored.
- **`tests/test_compat_patch.py::test_run_patch` gated.** Test previously mutated real user filesystem (`~/.gemini`, `~/.claude`, workspace plugins) on every pytest run. Now `@pytest.mark.skip`'d pending rewrite with `tmp_path` fixture (INT-078 OI-2).
- **Unused-import lint cleanup.** Removed unused `os`/`yaml`/`re` imports from `tooling/dekspec/mcp/server.py`; removed unused `os` from `tests/test_compat_patch.py`; removed unused `pytest` from `tests/test_resolve_intent_ibs.py`.

## [v0.75.0] — 2026-05-22

### Added

- **Added `/dekspec:dispatch-intent` new skill.** Resolves locked child Implementation Briefs for target Intents and dispatches them sequentially to the active or overridden executor, safely preserving and restoring original executor settings.
- **Added SpecGraph IB resolver helper script.** Introduced `resolve_intent_ibs.py` and its unit tests to query the SpecGraph, map Intents to IBs, and validate locked-status compliance.
- **Upgraded `/dekspec:spec-mode` new skill.** Overhauled the agent guardrail with wide-latitude capability checks that immediately halt development of specless features and serve 1 to 3 context-aware retroactive/proactive specification recommendations.


## [v0.74.1] — 2026-05-22

### Changed

- **Renamed guardrail skill to `spec-mode` (`/dekspec:spec-mode`).** Refactored skill metadata, namespace, and CLI mapping structures to rename `/dekspec:guardrail` to `/dekspec:spec-mode`. This aligns the skill with its primary role of toggling and auditing the "No Specless Edits" spec mode in `CLAUDE.md`. All description text, arguments, examples, and diagnostics are fully modernized to canonicalize on this namespace.

## [v0.74.0] — 2026-05-22

### Added

- **Three-backend executor support (`local`, `inbox`, `dekfactory`).** Formally redesigned the executor configuration schema and cli layers to support the `local` (packaged & db-logged local agent execution), `inbox` (queued file-system package transfer), and `dekfactory` (network-dispatched remote orchestrator execution) backend taxonomy—completely deprecating legacy `"lite"` references and transparently coercing them to `"local"` on the fly.
- **Bearer Token authentication support.** Integrated native `auth` Pydantic models into config loading and verification pipelines, enabling dotted-key config setting operations for auth parameters (`auth.kind`, `auth.secret_ref`) via standard CLI commands.
- **SSL/TLS unverified context bypass for local development.** Patched the library client request wrappers to check for a new `DEKFACTORY_SSL_NO_VERIFY` environment variable. When set to `1` or `true`, urllib requests cleanly bypass SSL certificate checks, fully accommodating local Caddy-backed Tailscale targets with auto-signed Local Authority certificates.
- **E2E connection verification pipelines.** Authored a live remote integration test suite `tests/test_dekfactory_integration.py` and diagnostic smoke script `scripts/smoke-remote-builder.sh` mapping to synthetic connection verification specs (`INT-999`, `IC-999`, `IB-999`) to ensure robust orchestrator communication.

### Changed

- **Standardized non-deprecated CLI dispatch verb usage.** Standardized all test suites and scripts to execute `dekspec exec dispatch` instead of deprecated `dekspec dispatch` aliases, eliminating warning noise from test runners.

## [v0.73.0] — 2026-05-22


### Fixed

- **Reclassified `--decompose` to run inline inside `/write-intent`.** Updated `/write-intent` interactive skill routing to execute `--decompose` inline under the parent context instead of fanning out. This resolves the subagent skill cleavage where isolated subagents lacked the `Skill` tool required to invoke sibling skills like `/write-ibs` and `/create-beads`.
- **Auto-resolved git user identity in `artifact_ops.py` transition.** Refactored `artifact_ops.py` transition logic to attempt resolving the engineer's email from `git config user.email` prior to falling back to `"unknown"`, ensuring clean and fully attributed Amendment Logs.

## [v0.72.0] — 2026-05-22

### Fixed

- **T-STATUS-IB-FOLDER auto-fix relocation for duplicate IDs.** Fixed a bug where multiple Working Specs or Implementation Briefs sharing duplicate IDs (e.g. `IB-001` across different working specs) were improperly deduplicated by `artifact_id` during proposing relocations, causing all but the first to be skipped. Additionally, `_get_ib_relocation` now uses the precise file path from the audit `Finding` to look up the target brief, preventing lookup ambiguity and silent folder mismatch/overwrite errors.

## [v0.71.0] — 2026-05-22

### Added

- **Hierarchical Subcommand Namespaces (`check`, `audit`, `exec`, `repo`, `dev`).** Streamlined and reorganized the 24 flat top-level CLI commands into 5 semantic, nested namespaces for a modern, clean, and logical developer experience:
  - `check`: Single-file tasks (`validate`, `compile`, `emit`, `aggregate`, `allocate-ids`).
  - `audit`: Compliance and linkage validation (`linkage`, `doctor`, `relink`, `lock-ready`).
  - `exec`: Runtime tracking and orchestrator dispatching (`session`, `dispatch`, `runs`, `executions`, `lifecycle`, `active`, `package`, `config`).
  - `repo`: Setup, vendoring verification, and migrations (`init`, `upgrade`, `verify`, `migrate-ir`, `migrate-artifacts`).
  - `dev`: Brownfield archaeology and graph diagnostics (`graph`, `ingest`, `archeology`).
- **Claude Plugin Autocomplete Shadow Prompts.** Overhauled the `argument-hint` metadata blocks across all 12 Claude Plugin slash-commands (such as `dekspec-validate.md`, `dekspec-archeology.md`, `dekspec-ingest-document.md`) to explicitly declare all options, flags, and values—providing instant, comprehensive shadow prompts/hints for seamless agent and developer interactions.

### Changed

- **CLI Compatibility Deprecation Interceptor.** Added a top-level pre-parsing routing layer. Calls to old flat commands (e.g. `dekspec doctor`) print a clear deprecation notice to `sys.stderr` and seamlessly dispatch the invocation directly to their new nested verb counterparts (e.g. `dekspec audit doctor`), ensuring zero pipeline breakage.
- **Interactive Recovery Skills Namespacing.** Ported internal execution pathways inside interactive skills (`archeology/SKILL.md`, `ingest-document/SKILL.md`) to run the new namespaced CLI verbs directly.

### Fixed

- **`/write-intent` verification-cmd parser.** `check_verification_cmds.py` (the L9 helper behind `/write-intent --analyze` and `--accept`) bounded the `## Verification` section with a next-heading scan that also matched single-`#` YAML comment lines inside the fenced `verification:` block — the Intent template carries comment lines like `# Verification predicate for this Intent.`. The body was truncated before the fence, so zero verification records parsed. `--analyze` tolerated the empty result as a warning; `--accept` (strict L9) then refused every Intent authored from the current template. The next-heading scan now requires H2+ (`##`); single-`#` YAML comments no longer truncate the block.

## [v0.70.0] — 2026-05-22

### Added

- **`dekspec graph export --format text|json|mermaid|dot`.** `graph export` now renders the artifact dependency graph in four formats. The new default is **`text`** — a human-readable CLI render grouped by artifact kind, with each node's forward-link edges shown inline. `mermaid` / `dot` emit a visualization graph; `json` emits the full IR document. Nodes are the exported IRs; edges follow the ADR-015 forward-link model (`SpecGraph.forward_links_of`), so every non-JSON render stays consistent with the linkage audit.
- **`dekspec upgrade --no-migrate` / `--no-doctor`.** New flags to opt out of the post-upgrade migration / audit steps — for CI, or when those steps run separately. `--engine-only` implies both.

### Changed

- **`dekspec graph export` default format is now `text`, not `json`.** A bare `dekspec graph export` prints the human-readable render. Scripts that consume the JSON document must now pass `--format json` explicitly.
- **`dekspec upgrade` is now one-shot.** After vendoring + engine install + plugin refresh, `upgrade` also runs `migrate-artifacts` (markdown tree, old → new), `migrate-ir` (persisted run IR JSON), and `dekspec doctor` — all inline, as subprocesses against the freshly-installed engine so they see the new migration registry. These were previously manual follow-up steps; the migrations are no-ops when no schema changed.

### Fixed

- **`/dekspec:dekspec-graph-export` skill drift.** The skill and its command doc defaulted to `--format mermaid` and referenced a `--out` flag — but the engine's `graph export` never implemented `--format`, and the flag is `--output`. The engine now provides `--format`; the command doc's flag name is corrected.
- **`verify-vendored` false drift against a development checkout.** When the dekspec library is editable-installed from a development checkout, `verify-vendored` (and `doctor`'s vendoring section) compared a consumer's vendored content against the checkout's live, unreleased `docs/`/`templates/` — reporting drift against a reference that corresponds to no published release, while `dekspec upgrade` (which vendors from the pinned release tag) reported clean. `compute_drift` now detects when the library reference is a git checkout diverging from its `v<version>` tag and emits a single `reference-unreliable` advisory instead of false per-file findings, pointing to `dekspec upgrade --dry-run` for the version-accurate check. `verify-vendored` exits 0 (advisory, not a drift failure); `doctor` reports it as advisory, not warning.

## [v0.69.0] — 2026-05-21

> **Versioning note.** v0.64.0–v0.68.0 were not cut as individual releases. v0.69.0 is a catch-up release consolidating all work merged to `main` since v0.63.0 (75 commits, 107 files). The intermediate numbers were never published — consumers should treat them as nonexistent, not yanked.

### Added

- **Brownfield ingest pipeline (INT-059).** Adds a new CLI subcommand `dekspec ingest` plus the `/dekspec:ingest-document` authoring skill and slash command, for pulling existing documents into the DekSpec artifact model. Ships a deterministic heuristic classifier engine, a report emitter, and a draft writer.
- **`/dekspec:archeology` skill (INT-030).** New brownfield spec-gap skill that reverse-engineers system intent from an existing codebase, paired with a new `coverage` CLI verb.
- **`/dekspec-run-session` plugin command (INT-055).** New executor-dispatch plugin command for running a coding session against a compiled Package.
- **`dekspec:coding-orchestrator` subagent (INT-056).** New dispatch subagent that orchestrates a coding session end-to-end.
- **T-PROSE-\* audit rule family (INT-065).** A new audit rule family — prose-shape heuristics — wired into the v1 audit profile with tunable parameters.
- **`dekspec lifecycle reap` watchdog (INT-022).** New stale-heartbeat watchdog subcommand that reaps abandoned lifecycle runs.
- **Executor ABC (INT-026).** Completed the executor abstract base class with a `CANONICAL_EVENT_TYPES` registry and test coverage.
- **Local async dispatch (MSN-007).** Inbox/listener-based local asynchronous dispatch path.
- **`--unlock` mode on `/write-intent`.** Unlocks a LOCKED Intent back to PROPOSED for revision.
- **New linkage audit findings.** L14 backlog-health, L15 index-coherence, and L8-MSN-INT-SERIALIZED per-Mission Intent serialization checks.

### Changed

- **CI action pins** bumped ahead of the forced Node-20 upgrade.

### Fixed

- **`dekspec upgrade`** now skips the engine install step when `pyproject.toml` carries no dekspec dependency pin (engine managed externally via pipx / venv / system package) instead of misfiring.
- **`/dekspec:release` empty-`[Unreleased]` handling.** An empty `[Unreleased]` body is now an advisory (`No release warranted: [Unreleased] section is empty.`, exit 0), distinct from a genuinely missing `## [Unreleased]` heading (refuse, exit non-zero). The dry-run smoke script and the release SKILL.md were corrected to match WS-016 §Failure Behavior; the smoke check also tolerates pre-existing sentinel files.
- **Audit fixes.** Corrected the INT-026 component glob (executor registry path) and 4 stale L7b component globs on LOCKED Intents.
- **Severity normalization.** Fixed an invalid-escape `SyntaxWarning` in the `_normalize_severity_alias` docstring.

## [v0.63.0] — 2026-05-21

### Changed

- **L7b / L8 linkage rules — in-flight exemption (INT-068 / ADR-019).** `L7b-INT-COMPONENTS-RESOLVE` now tracks the Intent lifecycle instead of grading every ACCEPTED-or-later Intent at `P2`. DRAFT / PROPOSED / ACCEPTED emit a `P3` advisory — a declared component glob is a forward commitment, not a claim that the code already exists. The build-underway band (IMPLEMENTING / TESTFAIL / TESTPASS / MERGED) is **exempt**: an unresolved glob mid-build is the expected shadow of authoring specs ahead of code, not linkage drift. Only `LOCKED` — which asserts the work is complete — retains the `P2` grade. `L8-INT-MSN-MIRROR` now exempts `OVERSIZED` and `SUPERSEDED` design-parent Intents, which carry a Mission reference for provenance but are deliberately not queue members; the matching L8 fix proposer gains the same guard so it never proposes a queue row that contradicts a Mission's authored decomposition.
- **Consumer-visible behaviour change.** An Intent with a genuinely mistyped component glob no longer surfaces at `P2` until it reaches `LOCKED` — a consumer that relied on the old `P2`-at-`ACCEPTED` behaviour as a tripwire will see a quieter audit. This is intended (ADR-019); the `LOCKED` gate is the hard backstop. On the library's own self-spec the rescope clears 22 of 28 standing `P2` findings (`dekspec doctor`: P2 26 → 4); the 4 survivors are `LOCKED` Intents with genuinely stale component globs and are tracked separately, not suppressed.

## [v0.62.0] — 2026-05-21

> **Versioning note.** v0.60.0 and v0.61.0 were intentionally skipped; the version advanced directly from v0.59.0 to v0.62.0. No artifacts were ever published under the skipped numbers — consumers should treat them as nonexistent, not yanked.

### Added

- **Lite methodology profile (MSN-006 / INT-024).** DekSpec now ships two methodology profiles — `lite` and `full` — selected per repo via the `methodology_profile` field of `.dekspec/config.yaml`. `lite` scales the ceremony down for a solo engineer governing single-repo work: the Constitution + Intents replace a deep AE → WS → IC → IB graph. `full` remains the default; existing repos are unaffected.
- **`dekspec init --profile lite` (INT-067 / IB-115).** Scaffolds a minimal `dekspec/` tree — System Vision + Constitution singletons, the `adrs/` / `intents/` / `divergences/` directories, and the ADR + Intent indexes only. It does not scaffold `architecture-elements/`, `working-specs/`, `interface-contracts/`, `missions/`, or `impl-briefs/`. `--profile lite` also persists `methodology_profile: lite` to `.dekspec/config.yaml` and defaults the executor to `lite`. The `full` scaffold path is byte-identical to prior behaviour.
- **Compact AGENTS.md emitter (INT-067 / IB-116).** Under the `lite` profile, `dekspec aggregate agents-md` emits a single-page artifact — a one-page Constitution summary plus the in-flight Intent's title + Desired Outcome — instead of the full corpus dump. New `emit_compact_aggregate` / `compact_aggregate_for_profile` functions in the AGENTS.md emitter; the `full`-profile render path is untouched.
- **`profile` config-key alias (IB-112).** `dekspec config get profile` / `set profile` resolve to the `methodology_profile` field. `get profile` reports the effective profile, returning the backwards-compatible `full` default when `.dekspec/config.yaml` is absent or omits the field. New `dekspec_config.get_profile()` / `resolve_audit_profile()` helpers and `DEKSPEC_CONFIG_KEY_ALIASES`.
- **`--profile` flag on `dekspec doctor`** — mirrors the existing `dekspec audit linkage --profile` flag for per-run audit-profile selection.
- **Skill `mode` frontmatter tag (INT-066 / IB-114).** Authoring skills now carry a `mode` field, enabling the skill catalog to filter by methodology profile.
- **"Lite vs full" quick-reference section (IB-117)** — `docs/dekspec-quick-reference.md` documents the two profiles, the trimmed lite artifact set, the monotonic `lite → full` escalation path, and a decision rubric.

### Changed

- **Audit-profile resolution now consults `.dekspec/config.yaml` (IB-112).** When `dekspec audit linkage` / `dekspec doctor` run without an explicit `--profile` flag, the audit profile is resolved from the repo's `methodology_profile` (`full` → `v1`, `lite` → `lite`, `team` → `team`). Precedence: CLI flag > config field > `v1` default. Behaviour is unchanged for repos with no config file.

### Fixed

- **DIV-011 — Amendment Log row placement.** A transition-appended Amendment Log row now lands below the `|---|` table separator instead of being spliced between the header and the separator, keeping the table well-formed across successive transitions.

## [v0.59.0] — 2026-05-20

### Added

- **`dekspec relink` — deterministic cross-artifact linkage maintenance (ADR-015, MSN-005).** A new CLI verb that derives every artifact's reciprocal backlinks from the forward-link graph, emits them into each `## Linked Artifacts` section, and reports dangling forward references. Idempotent; `--check` runs a no-write dry-run. Backed by `SpecGraph.derive_backlinks()` and a `Linked Artifacts` emitter in the Constraint Compiler. Wired as the mandatory closing step of all 13 `write-*` authoring skills and as a CI gate (`Linked Artifacts relink gate`).
- **ADR-016 / ADR-017 / ADR-018** ratified — the Intent serialization model, a second path to Intent `LOCKED`, and the Mission-completion gate scope (see Changed).
- **AE-009** (Async Dispatch Workflow) and **IC-007** (inter-Claude-Code handoff) authored; **MSN-005–MSN-009** plus ~20 Intents and ~44 Implementation Briefs decomposed across the open bead queue.

### Changed

- **Backlinks are now derived, not stored.** The Architecture Element schema's stored `related_*s` backlink fields are retired (AE schema `0.1.0 → 0.2.0`, with a registered IR migration `retire_stored_backlinks`); the parser no longer projects them. Backlinks exist only as `dekspec relink`-emitted rendered output — the AE template documents the `Related *` lines as auto-populated.
- **Intent serialization rescoped (ADR-016).** The repo-wide "one active Intent at a time" hard refuse — never ratified in an ADR, in practice violated by nearly every Intent — is retired. Serialization is now per-Mission and advisory (surfaced as a `dekspec audit linkage` finding), never a creation block.
- **Second path to Intent `LOCKED` (ADR-017).** `/write-intent` Lock Mode now also locks an Intent when every downstream WS/IC/IB is at status `≥ ACCEPTED` *and* every bead decomposed from those IBs is closed — independent of branch / merge / `--testpass` state.
- **Mission-completion gate rescoped (ADR-018).** A Mission's verification predicate gates on P0/P1-clean (no critical or blocking audit findings), not on whole-repo zero-findings.
- **`git_hooks` template resolution** now works for installed (pipx / wheel) dekspec, not only the editable / source-checkout layout — `dekspec session install-hooks` was previously broken for every non-editable install.

### Removed

- **The `L6-BACKLINK` audit rule** and its v1-profile registration. With backlinks derived from forward links, the rule that policed stored-backlink sync is obsolete.

### Fixed

- `run_verification.py` / `mission_audit.py` mangled `sh -c '...'` verification commands by stripping unmatched quote characters; fixed with a matched-pair `_unquote` helper.

## [v0.58.0] — 2026-05-20

### Changed

- **Skills audit — visibility, determinism, composability (17 PRs).** Every `write-*` / `run-dekspec-*` authoring/audit skill was audited and refactored along three axes. (1) **Visibility:** `disable-model-invocation: true` added to 13 mutating skills so Claude cannot auto-fire artifact mutation from conversational drift — these skills must be explicitly invoked. (2) **Composability:** seven shared substrates extracted to `plugins/dekspec/skills/_lib/` (`context_check`, `mode_detection_template`, `teaching_mode`, `lock_unlock`, `help_mode_template`, `fan_out`, `validate_and_surface`); skill bodies became citation + parameter-manifest form, removing ~800 lines of duplicated prose. (3) **Determinism:** deterministic skill steps (next-id allocation, status transitions, ADR supersession-chain walks, related-artifact linkage scans, bead→IB→WS→Intent resolution, structural pre-save checks, audit-trigger regex sweeps, bead emission) extracted into ~25 tested stdlib-only Python helpers — four shared under `_lib/scripts/` (`artifact_ops`, `resolve_supersession`, `bundle_related`, `resolve_bead_context`) and the rest in per-skill `scripts/` folders. ~480 new tests.
- **Interface Contract directory renamed `dekspec/api-contracts/` → `dekspec/interface-contracts/`.** The artifact kind is "Interface Contract" (IC) and not all ICs are APIs (some are consistency / adapter contracts), so `api-contracts/` was a misnomer; the index file was already named `interface-contract-index.md`. Every reference across the engine (`cli.py`, `fidelity_audit/linkage.py`, `package/build.py`, `migrations/markdown.py`, `constraint_compiler/{parser,graph}.py`, `constraint_compiler/emitters/ci_gate.py`), the test suite, the skills/agents, the methodology docs, and the JSON Schemas was updated. `dekspec init` now scaffolds `interface-contracts/`.
- **Consumer migration:** `scripts/install-dekspec.sh` gained an idempotent one-shot directory rename in STEP 1 — if a consumer repo has `dekspec/api-contracts/` and no `dekspec/interface-contracts/`, the directory is moved (via `git mv` when tracked, else plain `mv`) before `dekspec init` and `dekspec migrate-artifacts` run, so existing consumers pick up the new layout on their next upgrade.

### Fixed

- **Stale path references in skill prose.** `write-ibs/SKILL.md` (6 refs), `write-evals/SKILL.md` (3 refs), and `write-tests/SKILL.md` (1 ref) pointed at the obsolete `impl-briefs/queued/` and `impl-briefs/active/` subdirectories; `dekspec/impl-briefs/` is flat. `write-evals/SKILL.md` also referenced the non-existent `.beads/beads.jsonl` (the real file is `.beads/issues.jsonl`). `record-divergence/SKILL.md` referenced a non-existent `dekspec/divergences/README.md`; the SKILL.md body is itself the format source, so the dead reference was removed.

## [v0.57.0] — 2026-05-19

### Added — ds-di2 fan-out pattern across 13 authoring/audit skills

- All `write-*` and `run-dekspec-*` skill bodies now delegate substantive-work
  modes (create / accept / revise / supersede / lock / unlock / dry-run) to
  fresh-context subagents via the `Agent` tool. The orchestrator skill body
  bundles a self-contained context packet (template, parent linkage, engineer
  guidance, output path, validation contract) and dispatches; the subagent
  authors against clean context with no cross-conversation pollution.
- L1 (static) + L2 (functional smoke) + L3 (failure-mode probe) testing
  validated the pattern: 6/6 L3 probes refused loudly with INSUFFICIENT_INPUT
  on deliberately-incomplete dispatches (write-ibs, write-ae, write-ic,
  write-sv, write-evals, write-tests); zero invent-silently. L2 functional
  smoke on write-sv confirmed end-to-end author → validate green.
- Closes ds-di2.

### Added — `dekspec validate --kind` flag (new public API surface)

- New CLI flag `dekspec validate --kind {ic|ae|ws|adr|ib|intent|mission|sp|
  vision|glossary|constitution}` overrides filename-based artifact-kind
  inference. Lets non-conventional paths validate without rename ceremony
  (scratch SVs in `/tmp/`, Constitution at any filename, fan-out subagent
  output paths). Filename-based inference remains the default when `--kind`
  is absent.

### Changed — skill rename for consistency

- `write-interface-contract` → `write-ic`
- `write-working-spec` → `write-ws`
- `write-security-profile` → `write-sp`
- `write-system-vision` → `write-sv`
- `write-sp` flag rename: `--amend` → `--revise` (aligns with sibling 8-mode
  skills' canonical mode catalog).

### Fixed — WS template severity backtick-parsing

- `_normalize_severity_alias` now strips backticks before alias-map lookup,
  so the WS template's `**Severity:** \`P3\`` convention parses cleanly.
  Previously trip a ParseError on every backtick-wrapped severity literal.

## [v0.54.1] — 2026-05-19

### Added — `/run-coding-session --package <sha>` flag (Option 1 of Claude-Code-as-executor)

Drive the in-session orchestrator from a content-addressed Package (built by `dekspec package build <intent-id>`) instead of querying `br ready`. The Package's manifest names the exact `bead_set` + `intent_id` + `ib_path` to run; the skill skips br-ready discovery, treats the manifest's bead_set as the candidate list, and proceeds with the standard claim + Phase 2-5 fan-out flow unchanged.

Use cases:

- **Dispatch replay** — same SHA = same inputs = same dispatch (audit-friendly)
- **Cross-session handoff** — drop a packet in `.dekspec/inbox/` (future Option 2 pattern; see bead `ds-b6q`); a listener session picks it up
- **CI gates** pinned to a specific bundle
- **Local sync execution** against a pre-built Package without the inbox dance: `dekspec package build INT-NNN` → `/run-coding-session --package <sha>` in the same session

Implementation: skill-body edit at `plugins/dekspec/skills/run-coding-session/SKILL.md` — front-matter argument-hint, help text, Mode Detection, and Phase 1 §Step 1 branch all updated. The bash block in Phase 1 resolves SHA → tarball → manifest.yaml → extracts `intent_id` + `ib_path` + `bead_set` into shell vars; the rest of Phase 1's claim + filter logic operates on `$PKG_BEAD_SET` instead of `br ready` JSON output.

Companion architecture (Option 2, async cross-session dispatch) tracked at `ds-b6q` — not in this release.

**Action required for consumers:** None. The flag is additive; existing `/run-coding-session` invocations work unchanged. To use the new path, refresh the Claude Code plugin (`claude plugin update dekspec@dekspec` or `/reload-plugins`) after upgrading.

## [v0.54.0] — 2026-05-19

### Added — `dekspec dispatch` + `DekFactoryExecutor` + IC-006 dispatch payload (new public API, closes INT-019)

The DekFactory side of MSN-004's executor cleavage lands. Three new public API surfaces:

```bash
dekspec dispatch <ib-path>          # POST IC-006 dispatch payload to the manifest's dispatch endpoint
dekspec dispatch status <job_id>    # GET status; reconcile terminal state into local lifecycle DB
```

Python API: `from dekspec.executor.dekfactory import DekFactoryExecutor` — subclasses the `Executor` ABC, implements all four IC-004 capabilities (dispatch / report_event / complete / enforce_autonomy) against an HTTP transport.

**New IC-006** (`dekspec/api-contracts/IC-006-dekfactory-dispatch-payload.md`, ACCEPTED) pins the wire contract: manifest envelope shape (`.well-known/dekspec-manifest.yaml`), dispatch request shape, synchronous ACK shape (`{job_id, status: queued, queue_position?, eta_seconds?}`), status request/response shapes for non-terminal + terminal-success (`{merge_commit_sha, pr_url, ci_status}`) + terminal-failure (`{error_code, error_message, escalation_required}`) lifecycle states. IC-006 LOCK is gated on a real DekFactory server publishing the manifest endpoint (cross-repo work tracked at `Dektora/dekfactory#dekfactory-vxk` P1).

**New JSON Schema** (`tooling/dekspec/schemas/dekfactory-manifest.schema.yaml`, Draft 2020-12) validates the manifest envelope; `additionalProperties: false` at every nest catches schema drift before dispatch fires.

**`tooling/dekspec/executor/` package**: the existing single-file `executor.py` (per-repo registry + entrypoint discovery) was converted to a package. The legacy `executor.py` module body moved verbatim to `executor/registry.py`; `executor/__init__.py` re-exports every existing public + private symbol (`ExecutorRecord`, `configure_active`, `get_active`, `list_executors`, `UnknownExecutorError`, `ExecutorRegistryError`, `ExecutorConfigError`). New modules live alongside: `executor/dekfactory.py` (the executor), `executor/dekfactory_manifest.py` (fetch + JSON Schema validate + on-disk TTL cache + `UnsupportedProtocolVersionError`).

**IC-004 ABC forward-ratified** at `tooling/dekspec/executor_abc.py` so `DekFactoryExecutor` can subclass it. The ABC's signature surface mirrors IC-004 §Capability 1-4 byte-for-byte. INT-026/IB-040 remain the planned home for full signature-conformance tests + `CANONICAL_EVENT_TYPES` parity check on top of this inline scaffold.

**Tests**: 49 new (14 manifest + 21 executor + 14 CLI dispatch) against a local-mock HTTP server. Full suite 1564 passed (was 1515 at v0.53.0); zero regressions.

**Lifecycle integration**: `DekFactoryExecutor.dispatch()` opens a local `execution_attempts` row via `record_execution_attempt` AND records a `custom` event of type `dekfactory_job_id` against it — so the local DB can reconcile with DekFactory's job ledger via `dekspec dispatch status <job_id>` (which calls `complete_execution_attempt` on terminal state).

**Deviations from INT-019 §Desired Outcome** (recorded in INT-019 Amendment Log):

- No new pyproject.toml deps — stdlib `urllib.request` instead of `httpx`; env/literal secret resolver instead of `keyring` (OS keychain deferred to a future IC-008 auth sub-IC)
- `compiled_outputs` payload field structurally present but populated as empty dict in v1 (full hydration deferred to a follow-on Intent)
- IC filename pinned as `IC-006-*.md` (manual claim; INT-020 `dekspec id allocate` hasn't landed yet)
- `scripts/smoke-dispatch-against-stub.sh` not authored as a separate file — the 14 CLI dispatch tests cover the smoke surface end-to-end

INT-019 walked PROPOSED → ACCEPTED → MERGED → LOCKED in this release. IC-006 walked PROPOSED → ACCEPTED (LOCK pending cross-repo). `ds-ki9` (plugin slash command + subagent for executor dispatch) commented as unblocked — second concrete executor exists, IC-004 LOCK gate effectively cleared once `dekfactory-vxk` server-side work lands.

**Action required for consumers:** None unless adopting DekFactory dispatch. To opt in:

```yaml
# .dekspec/config.yaml
executor:
  kind: dekfactory
  endpoint: https://<your-dekfactory-server>
auth:
  secret_ref: env:DEKFACTORY_TOKEN  # or literal:<token>
```

## [v0.53.0] — 2026-05-19

### Added — `dekspec package` — content-addressed dispatch unit (new public API, closes ds-o57 / implements INT-028)

New public API surface: `tooling/dekspec/package/` module + `dekspec package` CLI verb group. The **Package** abstraction is the content-addressed bundle that flows through IC-004's `dispatch()` call — every input an executor needs to do one Intent's work, frozen into a tarball with a SHA-256 identity.

```bash
dekspec package build <intent-id>                # bundles Intent + IB + Mission + spec refs into .dekspec/packages/<sha>.tar.gz
dekspec package show <sha-or-path>               # pretty-prints the manifest
dekspec package submit <sha> --to <executor>     # opens a lifecycle row (named executor runs the agent loop)
```

Python API: `from dekspec.package import Package, build_package, pack, inspect`.

Eight failure modes from `ds-o57` become addressable: **replay** (re-dispatching quotes the SHA), **portability** (hand the tarball to a different builder), **debugging** (unpack to see exactly what the agent saw), **offline review** (compare tarball ↔ PR without re-running `dekspec compile`), **audit** (sign the tarball), **approval gates** (signatures live on the package, not on the Intent), **caching** (builders short-circuit on identical SHA), **first-pass-success metrics** (group attempts by Package SHA).

**Determinism:** the `package_id` is SHA-256 of a canonicalized manifest. Two builds against an unchanged tree produce bit-identical IDs.

**Deviations from INT-028 spec** (recorded in INT-028 §Amendment Log):

- gzip (`.tar.gz`) instead of zstd (`.tar.zst`) — gzip is stdlib-only, no new `zstandard` dependency
- `inspect` accepts SHA prefixes in addition to full SHAs / tarball paths (UX improvement)
- `submit` is contract-scoped to opening a lifecycle row via `record_execution_attempt` (per IC-004 §Capability 1); the actual agent-run-loop is the named executor's responsibility (today's `/run-coding-session`; tomorrow's INT-018 LocalAgentExecutor)

INT-028 walked PROPOSED → ACCEPTED → MERGED → LOCKED in this release.

**Action required for consumers:** None. New module + verb group are additive; existing dispatch flows (`dekspec dispatch <IB>` from INT-019) are unchanged.

## [v0.52.5] — 2026-05-19

### Added — End-to-end smoke gating the upgrade flow (closes ds-a11)

The v0.52.0 → v0.52.4 release chain shipped 6 patches in 48 hours because every defect (ds-b3h /tags resolver, ds-u3w pin regex, ds-zrp install-vs-update, slash-command prose) lived in a layer the unit tests mocked. Each unit test passed; each defect surfaced only via manual consumer-side smoke.

`tests/test_upgrade_e2e.py` (8 tests, `@pytest.mark.e2e`) subprocess-invokes the real `dekspec upgrade` CLI against a local HTTP mock standing in for the GitHub `/tags` API + fake `claude` shims recording invocations. Coverage:

- Auto-resolve picks the highest semver tag from the mock API (ds-b3h regression guard)
- All three pin shapes (URL / RANGE / EXACT) bump correctly (ds-u3w guard, 3 tests)
- Plugin verb dispatcher picks `update` when already installed, `install` when not (ds-zrp guard, 2 tests)
- Slash-command markdown doesn't refuse no-args invocation + `argument-hint` marks version optional (slash-prose guard, 2 tests)

Two new env-var test hooks (off-default in real use; the e2e fixture sets them):

- `DEKSPEC_GITHUB_API_BASE` overrides `https://api.github.com` for the resolver
- `DEKSPEC_LIB_ROOT_OVERRIDE` bypasses `git clone` for `upgrade_to` (uses a local library tree instead)

CI: `.github/workflows/release.yml` now runs `pytest -m e2e tests/test_upgrade_e2e.py` as a gating step in the test job. Future regressions in any of the v0.52.x defect classes break the release gate.

**Action required for consumers:** None. Test-only addition; no public API or behavior change at the upgrade-flow surface.

## [v0.52.4] — 2026-05-19

### Fixed — `/dekspec:dekspec-upgrade` slash command no longer requires a version arg

Pre-v0.52.0, the slash command's prose at step 1 said *"If version is missing, show usage and stop"* — correct for the old 2-step CLI. v0.52.0 made the version arg optional (auto-resolve from GitHub `/tags`), but the slash command's prose wasn't updated. Engineers running `/dekspec:dekspec-upgrade` (no arg) got refused at the slash-command layer before the CLI ever saw the call — masking the seamless flow's auto-resolve behavior entirely.

Slash command body now reflects the full v0.52.3 capability surface: optional positional version, `GITHUB_TOKEN` hint for private repos, all flags surfaced in `argument-hint` (`--dry-run`, `--at`, `--no-install`, `--no-plugin`, `--engine-only`, `--yes`), step 3 enumerates the actual end-to-end CLI behavior, step 4 instructs the slash to relay the *"Restart Claude Code / `/reload-plugins`"* hint verbatim when the plugin was refreshed, and `/dekspec-migrate-ir` replaces the old `/dekspec-migrate` name in the post-upgrade manual step.

**Action required for consumers:** None. Your next `dekspec upgrade` refreshes the plugin cache (per the v0.52.3 fix), so the new slash-command behavior activates after `/reload-plugins`.

## [v0.52.3] — 2026-05-19

### Fixed — `dekspec upgrade` actually refreshes the Claude Code plugin (closes ds-zrp)

The seamless-upgrade plugin step (since v0.52.0) ran `claude plugin install dekspec@dekspec` unconditionally. For first-time consumers this works — but for **existing consumers** (every consumer who has already adopted dekspec), the Claude CLI treats `install` of an already-installed plugin as a silent no-op (reports `"Plugin already installed"`, exits 0, pulls no new content). Net effect: `dekspec upgrade` reported plugin refresh as successful while the plugin cache stayed frozen at first-install version. DekFactory's plugin cache had drifted 3 releases behind (0.49.0 vs 0.52.2) before this was caught.

`dekspec upgrade` now detects whether `dekspec@dekspec` is already installed (via `claude plugin list` output parsing) and dispatches accordingly:

- **Already installed** → `claude plugin update dekspec@dekspec` (the verb that actually pulls)
- **First-time consumer** → `claude plugin install dekspec@dekspec` (existing behavior)
- **Detection failure** (older CLI without `plugin list`, OS error) → falls back to `install`. First-time installs continue to work; a misclassified-as-install on existing consumers is no worse than the pre-fix behavior.

Successful `update` now prints an explicit hint: *"Restart Claude Code or run `/reload-plugins` to activate the new skills/commands/agents."* First-time `install` doesn't print the hint — first-time consumers don't have a running session that needs reloading.

**Action required for consumers:** None. Your next `dekspec upgrade` will actually refresh the plugin cache.

## [v0.52.2] — 2026-05-19

### Fixed — `resolve_latest_version` uses GitHub `/tags`, not `/releases/latest` (closes ds-b3h)

The seamless-upgrade flow shipped in v0.52.0 (and patched in v0.52.1) was **unreachable in practice**: the resolver hit the GitHub `/releases/latest` endpoint, which only finds formal GitHub release objects. `dekspec` ships releases via raw `git tag` + `git push --tags` without running `gh release create`, so the endpoint always returned 404 — even with a valid `GITHUB_TOKEN`. `dekspec upgrade` (no args) failed with `"GitHub releases API returned 404"` on every invocation against the canonical Dektora/dekspec repo.

Switched to the GitHub `/tags?per_page=100` endpoint, the same source of truth dekspec already uses for install URLs (`git+https://...@vTAG`). The resolver fetches the tag list, filters to strict semver (`^v\d+\.\d+\.\d+$`), sorts by parsed `(major, minor, patch)` tuple (so `v0.10.0` > `v0.9.0`, not lexically reversed), and returns the highest.

The seamless `dekspec upgrade` (no args) flow now works end-to-end. Verified against the live Dektora/dekspec API: resolves the highest semver tag, recognizes the standard PEP 440 `>=,<` pin shape (ds-u3w fix from v0.52.1), and previews the would-run pip + plugin steps correctly.

**Action required for consumers:** None. The fix is in the resolver only; downstream `pip install` + `claude plugin install` behavior is unchanged.

## [v0.52.1] — 2026-05-19

### Fixed — `bump_pyproject_pin` recognizes standard PEP 440 `>=,<` and `==` pin shapes (closes ds-u3w)

The previous regex only matched the PEP 508 direct-URL pin shape (`dekspec @ git+https://...@vX.Y.Z`), silently no-op-ing on the standard PEP 440 forms most production consumers use:

- `"dekspec>=0.51.1,<0.52.0"` (RANGE — Cloudsmith / standard)
- `"dekspec==0.51.1"` (EXACT — pinned-deps style)

When `dekspec upgrade` ran against a consumer using the RANGE form, the operator-facing message read `"no dekspec pin matched the expected pattern; update it manually if needed"` — leaving the pin un-bumped while vendoring proceeded. This broke v0.52.0's seamless one-command upgrade flow for the common consumer case (observed on DekFactory's v0.51.1 → v0.52.0 upgrade, 2026-05-19).

`bump_pyproject_pin` now recognizes all three shapes and **preserves the original shape** on bump:

- RANGE: lower bound becomes the target; upper bound rolls to `<X.(Y+1).0` (next-minor ceiling)
- EXACT: version is swapped in place
- URL: version tag is swapped (existing behavior)

**Action required for consumers:** None. Any consumer whose `dekspec upgrade` previously emitted "no pin matched the expected pattern" will now have their pin bumped automatically.

## [v0.52.0] — 2026-05-19

### Added — `dekspec upgrade` is now a true one-shot end-to-end upgrade (closes ds-v3q)

`dekspec upgrade` previously did only half the upgrade: it bumped the pyproject pin and re-vendored templates, but left the engineer to manually run `pip install -e .` and `claude plugin install dekspec@dekspec` as follow-up commands. With this release, **one command does the whole upgrade**:

```bash
dekspec upgrade            # auto-resolve latest tag from GitHub releases API,
                           # vendor templates + docs, install the new engine
                           # wheel, and refresh the Claude Code plugin
dekspec upgrade v0.51.1    # explicit version override (positional arg is now optional)
```

The new public API:

- Positional `version` is now **optional**. With no arg, the latest tag is resolved from `https://api.github.com/repos/Dektora/dekspec/releases/latest`. Set `GITHUB_TOKEN` for private-repo access or rate-limit relief.
- **Auto pip install** (`pip install -e .` for editable consumers, `pip install -U git+...@vX.Y.Z` for git-pin consumers) runs automatically after vendoring. Detected via `pyproject.toml` inspection; uses the same Python interpreter that's running dekspec (so the right venv is targeted).
- **Auto plugin refresh** (`claude plugin install dekspec@dekspec`) runs if `claude` is on PATH. Soft warning on absence or failure — vendoring + engine install are load-bearing; plugin refresh is best-effort.
- **BREAKING-release confirmation prompt**: if the resolved target's CHANGELOG section contains `BREAKING`, the operator is prompted before any changes land. Skippable with `--yes` for non-interactive sessions.

New flags for CI / power-user scenarios that need to opt OUT of bundled steps:

- `--no-install`   — skip the pip-install step (Poetry/uv-managed consumers)
- `--no-plugin`    — skip the plugin refresh (headless CI)
- `--engine-only`  — bump pyproject + install engine wheel only; skips vendoring + plugin
- `--yes` / `-y`   — auto-confirm BREAKING-release prompt

**Backward compatibility:** every existing CI call that passes a positional version continues to work unchanged. The new default behavior (auto-resolve + auto-install + auto-plugin) kicks in only when no version is provided.

**Action required for consumers:** None. The behavior is strictly additive; the old 4-step flow still works.

## [v0.51.1] — 2026-05-19

### Fixed — Wheel installs now ship `templates/` + cherry-picked `docs/` (closes ds-md9)

Wheel installs of `dekspec` (`pip install dekspec`, `pipx install dekspec`, `pip install dekspec @ git+...@vX.Y.Z`) previously shipped only the Python package — no `templates/`, no `docs/`. `library_root()` resolved to the wheel install directory, and `dekspec verify-vendored` saw an empty library-side manifest, then falsely flagged every consumer-side `dekspec/templates/<file>.md` as `unknown` ("present in consumer but not in current library manifest"). At least one consumer (DekFactory, 2026-05-19) interpreted the output as "upstream removed these templates" and deleted live, current templates from their tree.

The fix bundles the vendored content **inside the wheel**:

- A new `setup.py::VendoringBuildPy` build hook copies project-root `templates/*` + 7 cherry-picked `docs/*.md` into `tooling/dekspec/_vendored/{templates,docs}/` before standard `build_py` runs.
- `pyproject.toml` declares `"dekspec._vendored" = ["templates/**/*", "docs/**/*"]` package-data so the build-hook output ships in the wheel.
- `vendoring.library_root()` resolution preference: env-var (`DEKSPEC_LIBRARY_ROOT`) → source-checkout layout (`<root>/templates/`) → wheel-install layout (`<package>/_vendored/templates/`). Source-checkout wins when both layouts exist — editable installs see source edits immediately, no stale-vendored footgun.
- `.github/workflows/release.yml` asserts the built wheel contains `_vendored/templates/*.md` + `_vendored/docs/*.md` before publish; future releases cannot ship without the bundled content.

The `DEKSPEC_LIBRARY_ROOT` env-var escape hatch (from `ds-verify-vendored-false-positive-when-installed-fr-c2l`) remains available but is no longer required for the common wheel-install case.

**Action required for consumers:**

1. Upgrade to v0.51.1 (`dekspec upgrade v0.51.1` or `pip install --upgrade dekspec`).
2. If you ran `dekspec verify-vendored` against v0.50.0 / v0.51.0 and deleted templates flagged as `unknown`, restore them from the v0.51.1 source tree (see DekFactory bead `dekfactory-nak` for restore paths).
3. After upgrade, re-run `dekspec verify-vendored` — it should now correctly identify drift instead of reporting every template as unknown.

## [v0.51.0] — 2026-05-18

### Added — `L5-IB-INTENT-EXISTS` new audit rule code

Companion to the L5-IB-SPEC-MISSING extension below. Fires (severity P1, mirrors L5-IB-WS-EXISTS) when an IB's `**Intent:**` line points at an `INT-NNN` ID that does not resolve to an existing artifact in the registry. Catches dangling Intent backlinks that the previous parent-link rule would have missed.

The v1 audit profile registers the new rule code automatically. Consumers re-running `dekspec doctor` on next library upgrade will see the new code surface if any of their IBs cite missing Intents.

### Changed — `L5-IB-SPEC-MISSING` audit rule accepts Intent-only IBs

The L5 parent-link audit rule previously required every IB to carry a `**Spec:**` line resolving to a Working Spec (WS-NNN). This produced false-positive findings against the Mission-less single-IB decomposition pattern — where an IB decomposes directly from an Intent with no intervening WS (e.g., the Intent is small enough that a separate behavior spec adds no value).

The rule now treats **either** a resolvable `**Spec:**` line **or** a resolvable `**Intent:**` line as satisfying the parent-link requirement. WS-backed IBs continue to validate exactly as before; Intent-only IBs become first-class.

**Action required for consumers:** None. The rule is strictly more lenient on previously-failing inputs; no existing valid IB shape becomes newly-invalid.

### Notes

This release ships no new templates, no new skills, no new CLI subcommands, and no new IR kinds. The library's own self-spec gained INT-022 through INT-026, IB-037 through IB-040, and ADR-014 over this cycle (all under `dekspec/` self-spec — visible in the library repo but not vendored to consumers). Consumer-facing surface change is limited to the two audit-rule entries above.

## [v0.50.0] — 2026-05-18

### Changed — Renamed `dekspec migrate` → `dekspec migrate-ir` (BREAKING)

The CLI subcommand that migrates persisted IR JSON files is now
`dekspec migrate-ir`. The old `dekspec migrate` name was ambiguous next
to `dekspec migrate-artifacts` (which migrates source markdown). No
back-compat alias — callers of the old name fail with the standard
argparse "invalid choice" error.

**Action required for consumers:**
- Scripts and CI jobs that call `dekspec migrate ...` must update to `dekspec migrate-ir ...`.
- Same arguments and flags — only the subcommand name changes.

Internally renamed: `plugins/dekspec/commands/dekspec-migrate.md` →
`plugins/dekspec/commands/dekspec-migrate-ir.md`. The slash-command
discovery surface is now `/dekspec:dekspec-migrate-ir`.

Docs updated in lockstep: README CLI table, `docs/cli-reference.md`,
`docs/EXAMPLES.md`, `docs/dekspec-methodology.md`, the install script's
upgrade next-steps prose, and the `dekspec upgrade` subcommand
description.

### Changed — Release skill ships in a separate `dekspec-maintainer` plugin (BREAKING for repo owners)

The marketplace at `Dektora/dekspec` now publishes **two** plugins:

- `dekspec` — consumer plugin. Authoring + audit + migration skills.
  Install on every consumer repo.
- `dekspec-maintainer` — maintainer-only plugin. Contains exactly the
  `/dekspec:release` skill (and its slash-command discovery file).
  Install **only if** you are a Dektora/dekspec repo owner who cuts
  releases.

The release skill moved:
`plugins/dekspec/skills/release/` → `plugins/dekspec-maintainer/skills/release/`
`plugins/dekspec/commands/dekspec-release.md` → `plugins/dekspec-maintainer/commands/dekspec-release.md`.

**Action required for Dektora/dekspec repo owners:** after upgrading to
v0.50.0, the `/dekspec:release` command disappears from the consumer
plugin's surface. Re-install the maintainer plugin to restore it:

```
claude plugin install dekspec-maintainer@dekspec
```

**No action required for consumers** — the release skill was never
yours to drive; this change simply removes a foot-gun (you couldn't
have invoked it usefully against your own repo anyway).

`install-dekspec.sh --with-plugin` continues to install only the
consumer plugin, and prints a one-line maintainer hint at the end.

### Self-spec updates

- `AE-005-cli.md` — Amendment Log row documenting the `migrate` → `migrate-ir` rename.
- `AE-006-skills-library.md` — Amendment Log row documenting the consumer/maintainer plugin split.
- `INT-017` — `Components affected` skill path updated to the new `plugins/dekspec-maintainer/` location.

## [v0.49.0] — 2026-05-18

### Changed — Skills/commands/agents now ship exclusively via the Claude Code plugin (`ds-skills-plugin-only`)

Skills, slash commands, agents, and hooks no longer travel through the
vendoring path. The library's `skills/` tree has moved to
`plugins/dekspec/skills/` and is delivered to consumers exclusively by
`claude plugin install dekspec@dekspec`. The earlier dual-delivery
scheme (vendored `dekspec/skills/` + `.claude/skills/<name>` shim
symlinks) caused the project-scope shims to shadow the plugin's skill
surface — the plugin appeared installed in `/plugin list` but its
commands and skills were invisible to Claude Code.

**Breaking — re-install required for existing consumers.** Running
`bash scripts/install-dekspec.sh` against an existing consumer will:
1. Vendor the new (templates + docs only) manifest with snapshot-based
   pruning — see below.
2. Remove the legacy `.claude/skills/<name>` shim symlinks that point at
   `../../dekspec/skills/<name>` (scoped — entries with other targets
   or real-directory entries are left alone).
3. Remove `dekspec/skills/<name>` directories whose names appeared in
   the prior `.dekspec-vendor-manifest` (user-authored directories
   under `dekspec/skills/` are preserved).
4. Print a notice when the legacy cleanup fires.

Consumers must run `claude plugin install dekspec@dekspec` (with
`marketplace add Dektora/dekspec` first if not yet registered) to
restore the skill/command surface. The `--with-plugin` flag on
`install-dekspec.sh` does both in one shot.

### Changed — Snapshot-based vendor pruning replaces `rsync --delete` (`ds-vendor-snapshot-pruning`)

The install script + `dekspec upgrade` no longer use `rsync --delete`
on the vendored prefixes. Instead, each install writes a
`.dekspec-vendor-manifest` file listing every consumer-relative path
the library shipped. On the next install, files in the prior manifest
that are NOT in the new manifest are deleted; files outside the prior
manifest (user-authored entries inside `dekspec/templates/`, custom
edits, etc.) are never touched. Replaces the prior behavior where any
file the consumer added to `dekspec/templates/` was wiped on the next
install.

### Changed — Self-spec: AE-006 (Skills Library) + AE-008 (Vendoring) amended

- `dekspec/architecture-elements/AE-006-skills-library.md` — skills now ship via the plugin only; `Implements` glob switched to `plugins/dekspec/skills/**/*.md`; non-goal added clarifying that vendoring (AE-008) and skills delivery are disjoint channels.
- `dekspec/architecture-elements/AE-008-vendoring.md` — vendoring scope narrowed to templates + methodology docs; snapshot-based pruning documented; `cleanup_legacy_skill_layout()` responsibility added.
- `dekspec/intents/INT-003 / INT-005 / INT-006 / INT-007 / INT-011 / INT-012 / INT-017 / INT-021` — `Components affected` skill paths updated to `plugins/dekspec/skills/...` (path-track follow-on).

### Added — `cleanup_legacy_skill_layout()` (`tooling/dekspec/vendoring.py`)

One-shot migration helper invoked by `vendor_from()` (and by the bash
install script's legacy-cleanup block). Removes only entries that match
the prior install's manifest or the canonical shim target shape; safe
against user-authored content.

### Removed — `refresh_skills_shim_symlinks()` + the `.claude/skills/` shim layer

The Python helper that created `.claude/skills/<name>` symlinks is
gone; new installs do not write to `.claude/skills/` at all.

---

## [v0.48.x] — pre-v0.49 (see prior entries below)

### Added — L12-WS-BLOCKING-PRE-IB-CLEAN audit rule + `/write-ibs` precondition (`ds-l12-ws-blocking-pre-ib-clean-5tp`)

- **`tooling/dekspec/fidelity_audit/linkage.py`** — new `_l12_ws_blocking_pre_ib_clean(graph)` audit rule. Fires P1 on any Working Spec at status=ACCEPTED or higher (ACCEPTED / IMPLEMENTING / TESTPASS / TESTFAIL / MERGED / LOCKED) that carries an `open_issue` with `severity=P1` — the canonical severity for the legacy `blocking_pre_ib` / `blocking_pre_code` / `blocking` artifact-side aliases per ADR-013. DRAFT and PROPOSED WSes are silent (P1 open_issues are expected during authoring; the field exists exactly for that). Realises the contract documented in `templates/working-spec-template.md` line 166 ("Zero `blocking (pre-IB)` open issues must remain when `/write-ibs` is invoked.") as a mechanical doctor-time gate.
- **`skills/write-ibs/SKILL.md`** — new `## L12 Precondition` section between Safety Check and Workflow. Before decomposing a parent WS into IBs, the skill runs `dekspec validate <spec-path> --json`, filters `open_issues` for `severity == "P1"`, and **refuses** with a specific error naming each unresolved issue if the WS is at ACCEPTED or higher. No bypass flag — to unblock, settle the issue in the WS body (demote to P2/P3 with a resolution note or check `[x]`) or unlock the WS back to PROPOSED.
- **`tooling/dekspec/fidelity_audit/profiles/v1.yaml`** — registers `L12-WS-BLOCKING-PRE-IB-CLEAN` in the v1 rule set so the audit fires through `dekspec doctor` and `dekspec audit linkage`.
- **Tests:** new `tests/test_l12_ws_blocking_pre_ib_clean.py` — 11 cases covering: P1 on ACCEPTED fires; DRAFT / PROPOSED exemption; P2/P3 silent on ACCEPTED; LOCKED / TESTPASS still gate; multiple P1 issues emit multiple findings; unknown/empty status defensive silence; long-text preview truncation. Full suite: 1277 → 1288 passing.

**Dogfood gate:** the library's own self-spec has zero L12 violations at landing time (no library WS at ACCEPTED+ carries P1 open_issues) — `dekspec doctor` stays ADVISORY. Closes `ds-l12-ws-blocking-pre-ib-clean-5tp`.

### Fixed — `verify-vendored` false-positive `unknown` findings under wheel installs (`ds-verify-vendored-false-positive-when-installed-fr-c2l`)

- **`tooling/dekspec/vendoring.py`** — `compute_drift()` now short-circuits with a single `library-missing-content` finding when the resolved library root has no `skills/` or `templates/` directories, instead of silently emitting N false-positive `unknown` findings (one per consumer file under `.claude/skills/` + `dekspec/templates/`). The wheel build does not currently ship the vendored content as package data, so `library_root()` resolved from a wheel-installed copy returns `<venv>/lib/python3.12/` — a directory with no skills or templates. Net effect: `dekspec doctor` no longer reports tens of phantom `unknown` findings on pipx/pip installs, just one clear advisory that explains the situation and points at the workaround.
- **`tooling/dekspec/vendoring.py::library_root()`** — now honors `DEKSPEC_LIBRARY_ROOT` env var as an escape hatch for wheel installs. Set it to a source checkout of `Dektora/dekspec` to make `verify-vendored` work end-to-end without changing the install method.
- **New helper:** `library_has_vendored_content(lib_root)` (public) — returns whether the library root has `skills/` or `templates/`. Useful for callers that want to gate `verify-vendored` invocations on install method.
- **New `DriftFinding.kind`:** `library-missing-content` — joins the existing `modified` / `missing` / `unknown` / `version` set. Renders cleanly through the existing CLI table + JSON paths.
- **Tests:** +5 new cases in `tests/test_vendoring.py` covering the env-var override, the helper, and the short-circuit behavior. Full suite: 1272 → 1277 passing.

The proper fix (bundle `skills/` + `templates/` as wheel package data so `verify-vendored` works end-to-end from any install method) is tracked as a follow-on; this fix is the fail-fast safety net + escape hatch portion. Closes `ds-verify-vendored-false-positive-when-installed-fr-c2l`.

### Added — `install-dekspec.sh --via cloudsmith` mode (`ds-install-script-cloudsmith-mode-xbp`)

- **`scripts/install-dekspec.sh`** — new `--via <git|cloudsmith>` flag (default `git` for back-compat) + `DEKSPEC_VIA` env-var equivalent. `--via cloudsmith` switches the pip / pipx install target from `git+${DEKSPEC_REPO}@vX.Y.Z` to `dekspec==X.Y.Z` with `--index-url $DEKSPEC_CLOUDSMITH_INDEX_URL`. Cleans up the canonical-channel ergonomics gap surfaced during the v0.48.0 cut — consumers wanting the preferred Cloudsmith distribution path (per RELEASING.md + ADR-002) no longer need to two-step the install (skip-pip + manual pip install). The `--via cloudsmith` path refuses without `DEKSPEC_CLOUDSMITH_INDEX_URL` set in the environment (typically sourced from Doppler); PEP-668 fallback hints + retry-manually messages render the Cloudsmith form when the cloudsmith path is active. Closes `ds-install-script-cloudsmith-mode-xbp`.

## [v0.48.0] — 2026-05-17

Substantial release. Lands the full **INT-016 severity vocabulary unification** trilogy (IB-023 parser + IR + migration, IB-024 audit emission + CLI, IB-025 templates + docs + glossary), the **new `/dekspec:release` skill** that wraps the operator-driven release flow, and a wave of spec ratchet across the methodology surface.

### Added — Canonical severity ladder `P0..P3` across all surfaces (INT-016 / ADR-013)

- **`tooling/dekspec/severity.py`** (new module) — single source of truth for the canonical severity ladder. Exposes `CANONICAL_VALUES = ("P0", "P1", "P2", "P3")`, `is_canonical(value)`, and the alias map fixing legacy strings (`blocking_pre_ib` → `P0`, `blocking` / `blocking-pre-code` → `P1`, `non-blocking` / `non_blocking` → `P3`, prefix-match for parenthetical qualifiers like `blocking (gates X)` → `P1`).
- **`tooling/dekspec/constraint_compiler/parser.py`** — every parser callsite (Open Issues across WS / IB / Intent / ADR / IC) routes severity strings through `_normalize_severity_alias`. Unknown severities raise a new structured `ParseError` (subclass of the existing `<L0Kind>ParseError` family). Schema validation runs after normalization, so persisted IR JSON files only contain canonical `P0..P3` values.
- **`tooling/dekspec/migrations/severity_unification.py`** (new migration module) — one `Migration` per artifact kind (ADR / WS / IC / IB / Intent) rewrites legacy severity values to canonical at IR-load time. Idempotent (per-run, per-IR); registered with the default migration registry.
- **`tooling/dekspec/schemas/{adr,working-spec,interface-contract,implementation-brief,intent}.schema.yaml`** — every IR schema's severity field is now `enum: [P0, P1, P2, P3]` only. Legacy strings on disk are auto-migrated before validation.
- **`tooling/dekspec/fidelity_audit/linkage.py`** — every `Finding(severity=...)` emission moved from `critical / important / minor` to `P0 / P1 / P2 / P3`. The 70 callsites (per WS-014 grep) all flow through a single `_to_canonical` helper.
- **`tooling/dekspec/cli.py`** — `dekspec doctor`, `dekspec audit linkage`, and the JSON output channels now emit canonical labels. The legacy `--severity critical/important/minor` flag is accepted as an alias-for-back-compat for one minor cycle, then removed in v0.49.0 (deprecation message emitted on the legacy form).
- **`templates/*.md`** + **`docs/dekspec-operating-guide.md`** + **`docs/dekspec-quick-reference.md`** + **`dekspec/domain-glossary.md`** — all authored references to severity vocabulary updated to canonical `P0..P3`. Open Issues sections in templates show the new vocabulary; legacy strings retained in prose only where authoring vocabulary is load-bearing (e.g., `blocking (pre-code)` as a template-authoring concept that collapses to `P1` in the IR).

**Governing decisions:** ADR-013 (ACCEPTED). Parent Intent: INT-016 (ACCEPTED). Implementation: IB-023 (commit `da69b7f`) + IB-024 (commit `bf9b0b0`) + IB-025 (commit `9ec09c9`).

**Consumer impact:** persisted IR JSON files from v0.47.x or earlier are auto-migrated on load; no manual cleanup required. Library code calling `dekspec.fidelity_audit` programmatically gets the new severity vocabulary in returned `Finding` objects. `dekspec doctor --json` consumers should switch to canonical labels — the legacy alias path is documented but slated for removal in v0.49.0.

### Added — New `/dekspec:release` Claude Code skill

- **`skills/release/SKILL.md`** — new authoring skill wrapping the operator-driven half of the `RELEASING.md` flow (version-mirror sync, CHANGELOG `[Unreleased]` promotion, local pre-flight, commit, tag, push). Four invocation arms: no-arg dry-run (default), explicit-version dry-run, `--apply` (bump + promote + pre-flight + sentinel), `--push` (sentinel-gated commit + tag + push). Includes a pure-bash semver-classification decision tree (`major` / `minor` / `patch` / `none` with mixed-signal refusal) that reads only the `[Unreleased]` body, never `git diff` or commit messages.
- **`plugins/dekspec/commands/dekspec-release.md`** — per-command plugin registration making `/dekspec:release` discoverable alongside the existing 9 `dekspec:*` commands.
- **`scripts/smoke-release-skill-classification.sh`** — bash smoke exercising the classifier against 4 arm fixtures + 1 mixed-signal + 3 historical spot-checks (`v0.43.5` → `patch`, `v0.47.0` → `minor`, `v0.47.1` → `patch`).
- **`scripts/smoke-release-skill-dry-run.sh`** — bash smoke driving the live `[Unreleased]` through the classifier, asserting no working-tree mutation + no sentinel written + plugin discoverability.
- **`tests/fixtures/release-skill-classification/`** — 9 fixture files anchoring the classification regression matrix.
- **`RELEASING.md`** — canonical-path pointer line added at the top of `## Cutting a release`; the existing 5-step manual flow stays as fallback documentation.

**Cloudsmith publish stays in CI** (BR1 invariant) — the skill's contract ends at `git push --follow-tags`; the tag-push trigger fires `release.yml`'s version-triad assertion + wheel build + Cloudsmith publish job.

**Governing decisions:** INT-017 (PROPOSED). Spec chain: INT-017 → WS-016 → IB-026 (all authored under this release).

### Changed — Release pipeline: wheel-only Cloudsmith publish

- **`.github/workflows/release.yml`** — drops sdist build + push to Cloudsmith. Previous releases pushed both wheel and sdist, but the sdist (`.tar.gz`) was server-side mis-classified by Cloudsmith's auto-detect (cosmetic noise — `pip install` via the index URL always resolved the wheel correctly because pip prefers wheels). The wheel is `py3-none-any` so it serves every consumer; source traceability stays via the GitHub tag and the `pip install dekspec @ git+...@vX.Y.Z` fallback in RELEASING.md. (`ds-release-yml-drop-sdist-publish-mh2`)

### Added — MSN-003 Security Profile Mission introduced (TODO)

- **`dekspec/missions/MSN-003-introduce-security-profile.md`** (TODO) — net-new Mission framing the Security Profile as the 10th DekSpec IR kind. Decomposes into 4 child Intents at PROPOSED: INT-012 (data plane + authoring surface), INT-013 (soft-layer AGENTS.md emitter), INT-014 (mid-layer pre-commit + hard-layer CI gate emitters), INT-015 (T-SEC-* audit rule family). Governing decision: ADR-011 (ACCEPTED). No tooling lands yet — the Mission is the frame; implementation arrives via the children's IBs in a future release.

### Changed — Spec ratchet (governance hygiene)

- 30 sub-ACCEPTED artifacts walked to ACCEPTED in batched audit passes (WS-004/005/006/007/009/010/011/012 + IB-001 through IB-022 spanning the Constitution + session lifecycle families whose implementations had already shipped under INT-002/003/004/008/009/010/011).
- INT-016 (ACCEPTED), INT-017 (PROPOSED), INT-006 walked DRAFT → OVERSIZED with 7 design rulings recorded (compact/lite labeling, profile activation mechanism, Mission optionality under lite, Constitution-under-lite shape, hook-installer sequencing, cross-machine session-state location, 3-child Mission shape).
- ADR-013 walked DRAFT → ACCEPTED (severity unification governing decision).
- AE-002/003/004/005/006/007 L6 backlink cascade — added the WS / IB / Intent references that landed since the last release; the entire L6-BACKLINK advisory cluster cleared (105 → 0 in the dogfood doctor pass).
- IB-002 severity-string typo fixed (`blocking-IB-002-internal` → canonical `P1`).

### Tests

- pytest baseline: 910 → **1272 passing** / 110 skipped (+362 across the IB-023/024/025 + release-skill landings).
- Two new smoke scripts (`smoke-release-skill-classification.sh` + `smoke-release-skill-dry-run.sh`) join the existing `smoke-install-hooks.sh` + `smoke-session-cli.sh` suite.

## [v0.47.1] — 2026-05-17

Patch release. Brings in one new LOCKED artifact + internal renumbering + an audit-parser fix. No code behavior changes; no new public surface beyond the new normative directive's AGENTS.md emission.

### Added — WS-008 Anti-Sycophancy Planner Directive (LOCKED)

- **`dekspec/working-specs/WS-008-anti-sycophancy-planner-directive.md`** — New LOCKED Working Spec authored as the upstream source artifact for DekFactory bead `dekfactory-upstream-dekspec-anti-sycophancy-directive-e3e` (consumer Intent DF-INT-001). Pins the verbatim text that planner agents read at session-load via the existing `emit_ws(ir)` → AGENTS.md path. Single source of truth across Dektora / DekFactory / future sibling consumers — wording changes to BR1 are a planner-context breaking change.

### Changed — WS renumber (internal hygiene; no consumer-facing impact)

- **`WS-008-session-cli-verb-family-contract.md` → `WS-012-session-cli-verb-family-contract.md`** — Session-CLI WS renumbered to free WS-008 for the anti-sycophancy directive. 13 internal references updated (CHANGELOG, indexes, MSN-002, INT-009, IB-012/013/014, IB-018 mcp-guard, WS-010 mcp-guard, cli.py, test_session_cli.py).
- **`tests/test_executor_cli.py`** — Stale WS-008 references (left over from the v0.47.0 cross-merge that renamed the executor WS to WS-011) updated to WS-011.

### Fixed — INT-016 §Components affected nested-bullet parsing

- **`dekspec/intents/INT-016-severity-vocabulary-unification.md`** — Components-affected globs were nested under per-surface group bullets; the parser's `_extract_components_affected` only sees top-level `- ` bullets, so it saw zero globs and L7b-INT-COMPONENTS-MISSING fired as IMPORTANT. Flattened to a top-level list with the three-surface grouping preserved as trailing prose. Doctor returns ADVISORY (0 important, 54 minor).

## [v0.47.0] — 2026-05-17

Substantial release. Lands four consumer-facing changes since v0.43.5:

1. **Mission IR schema v0.1.0 → v0.2.0** with back-compat parser (ds-zuy).
2. **Breaking behavior change**: `lifecycle.query_executions` default ordering (ds-lifecycle-query-attempt-number-order-208).
3. **New session-lifecycle enforcement gate** (MSN-002 family: INT-008 / INT-009 / INT-010 / INT-011).
4. **New executor selection CLI** (ds-nj1).

Plus methodology-layer additions framing MSN-003 (Security Profile) and the INT-007 OVERSIZED parent.

### ⚠ Breaking — `lifecycle.query_executions` default ordering (closes ds-lifecycle-query-attempt-number-order-208)

`lifecycle.query_executions(intent_id=...)` previously ordered rows by `started_at DESC` (newest first). It now orders by `attempt_number ASC, id ASC` to satisfy WS-003 BR9 literal text. If you call this function directly and rely on time-DESC order, update your caller — either reverse the result client-side or filter on `started_at` explicitly.

- **`tooling/dekspec/lifecycle.py`** — SQL `ORDER BY` changed to `attempt_number ASC, id ASC`. The secondary `id ASC` tiebreaker keeps multi-intent queries deterministic when attempt_numbers collide across intents.
- **`tooling/dekspec/cli.py::cmd_executions_ls`** — banner updated `"newest first"` → `"attempt_number order"`. User-visible behavior shift in `dekspec executions ls`.
- All 14 internal call sites audited; only the BR9 parity test needed adjustment (dropped client-side sort, asserts raw ordering).

### Added — Session-lifecycle enforcement gate (MSN-002)

Bind every commit and push to a named bead or Intent. Opt in per consumer repo via `dekspec session install-hooks`.

- **`dekspec session start <id> [--branch <name>]`** — Opens a session bound to a bead OR Intent ID (regex routing `^INT-\d{3,}$` → Intent, else bead). Persists state to `XDG_STATE_HOME/dekspec/<repo-hash>/session.json` where `<repo-hash> = sha256(absolute_repo_path)[:12]` (worktree-aware).
- **`dekspec session end [--reason <text>]`** — Closes the active session.
- **`dekspec session status [--machine-readable]`** — Reports active session; `--machine-readable` emits flat single-line JSON envelope `{active, session_id, bound_bead_id, bound_intent_id, branch, start_ts, stale}`.
- **`dekspec session install-hooks [--force]`** — Writes `pre-commit` + `pre-push` templates into the current repo's `.git/hooks/`. Two-phase clobber validation (refuses non-DekSpec hooks without `--force`; managed hooks always overwritten).
- **`dekspec.session_lifecycle`** — New module. Public API: `start`, `end`, `status`, `reap`, `emit_bypass`, `SessionState` dataclass, `SessionStateValidationError`, `SessionAlreadyActiveError`. File locking via `fcntl.flock`. TTL = 4h default, `DEKSPEC_SESSION_TTL_HOURS` env override, explicit `reap()` API.
- **`dekspec.git_hooks`** — New module. Public API: `install_hooks(target_repo, *, force=False)`, `uninstall_hooks`, `hooks_installed`, `GitHooksError`. Worktree-aware via `gitdir:` parse.
- **`dekspec.mcp_guard`** — New module. Public API: `is_session_active`, `guard_commit`, `guard_push`, `GuardResult` frozen dataclass. Fail-closed by default; honors `DEKSPEC_BYPASS_SESSION=1` (allow + bypass-log) and `DEKSPEC_MCP_GUARD_MODE=warn` (allow + warn-log).
- **`templates/git-hooks/pre-commit.template`** + **`pre-push.template`** — POSIX-portable hook templates that consult `dekspec session status --machine-readable`. Escape hatches: `DEKSPEC_BYPASS_SESSION=1`, `git commit --no-verify`. Bootstrap-lenient when `dekspec/` self-spec doesn't exist.
- **`tooling/dekspec/schemas/session_state.schema.yaml`** — New schema with `additionalProperties: false`.
- **`skills/run-coding-session/SKILL.md`** — New `## Session Lifecycle Wiring` section: skill calls `dekspec session start <bead-id>` on entry and `dekspec session end` on exit. Outer-session detection skips wiring when nested inside an active session.
- **`docs/dekspec-operating-guide.md`** — New `## Session discipline` section covering primary gate (hooks) + secondary gate (MCP) + escape hatches + library-side self-exemption + consumer adoption steps.
- **123 new tests** across `tests/test_session_lifecycle.py` (42), `tests/test_session_cli.py` (31), `tests/test_git_hooks.py` (21), `tests/test_mcp_guard.py` (29).

Library's own `dekspec/` self-spec remains exempt from the gate by documented policy (library-side guardrails are session-rules per `CLAUDE.md`, not hook-enforced).

### Added — Executor selection CLI (closes ds-nj1)

- **`dekspec executor list [--machine-readable]`** — Enumerates registered executors. Output: byte-stable JSON array of `{name, type, source, active}` per row, sorted by name.
- **`dekspec executor configure <name>`** — Sets the active executor preference. Persisted to `XDG_CONFIG_HOME/dekspec/<repo-hash>/config.json`.
- **`dekspec.executor`** — New module. Public API: `list_executors`, `configure_active`, `get_active`, `ExecutorRecord` frozen dataclass, `UnknownExecutorError`, `ExecutorRegistryError`, `ExecutorConfigError`.
- **Hybrid discovery**: built-in `local` executor (always present, reserved name) + `importlib.metadata.entry_points(group="dekspec.executors")` plugins.
- **Configure-time validation** — Unknown names raise `UnknownExecutorError` and do NOT write config. Atomic write via `.tmp` + `os.replace`.
- 28 new tests in `tests/test_executor_cli.py`.

### Added — Stub DekFactory executor fixture (closes ds-jzg)

- **`tests/fixtures/stub_dekfactory_executor.py`** — Fixture-only Python class satisfying IC-004's `dispatch / record_event / complete / enforce_autonomy` by calling `dekspec.lifecycle.*` directly (no subprocess). Used by `tests/test_ws003_executor_parity.py` (14 new tests covering WS-003 AC1, BR1/BR2/BR3/BR5/BR9). NOT shipped to consumers.

### Added — Methodology framing (self-spec)

- **MSN-002** (Introduce session-lifecycle enforcement gate) — ACTIVE; child Intents INT-008 (LOCKED), INT-009/010/011 (TESTPASS). Driven by the bead `ds-session-lifecycle-commit-gate-6c9` (P1, now closed).
- **MSN-003** (Introduce Security Profile) — TODO; child Intents INT-012/013/014/015 (PROPOSED). Frames INT-007's OVERSIZED parent decomposition.
- **INT-005** (Session-lifecycle design parent) → OVERSIZED; SUPERSEDED transition deferred to MSN-002 close.
- **INT-007** (Security Profile design parent) → OVERSIZED; SUPERSEDED transition deferred to MSN-003 close.
- **5 new Working Specs** (WS-007 session-state lifecycle, WS-012 session CLI, WS-009 git-hooks, WS-010 MCP guard, WS-011 executor selection).
- **14 new Implementation Briefs** (IB-009 through IB-022; numbering renumbered at cross-merge to disambiguate parallel-agent collisions — see commit `52be747` and `45c1773`).

### Changed — Mission IR schema v0.1.0 → v0.2.0 (closes ds-zuy)

First real schema-evolution migration. Captures the schema-shape half of FOLLOW.2 Mission rigor calibration — the part the bead explicitly carves out as non-data-gated. The data-driven per-field hypothesis calibration stays deferred to its triggers (≥3 Missions, supersede invocation, or specific engineer friction).

- **`tooling/dekspec/schemas/mission.schema.yaml`** — `rollback_plan` becomes an object `{trigger: string, steps: [{name, cmd}]}` parallel to `mission_verification`. `kill_criteria` becomes `[{name, cmd}]` (was `[string]`). `ir_schema_version` const bumped `0.1.0 → 0.2.0`. `LATEST_VERSIONS["mission"]` synced.
- **`tooling/dekspec/migrations/mission.py`** — new forward migration `0.1.0 → 0.2.0`. Legacy prose is preserved: `rollback_plan` prose moves into the new `trigger` field with a sentinel `steps[0] = {name: "_legacy_prose", cmd: "echo SKIP_LEGACY_ROLLBACK"}`; `kill_criteria` prose bullets become `{name: "_legacy_prose_N: <prose>", cmd: "echo SKIP_LEGACY_KILL"}` entries. Runners that try to execute the cmds fail loud, not silent.
- **`tooling/dekspec/migrations/mission_markdown.py`** — companion advisory markdown migration: when a Mission .md still carries prose-form §Rollback plan / §Kill criteria, emit an `AdvisoryItem` for `/migrate-artifacts-assist` instead of auto-editing.
- **`tooling/dekspec/constraint_compiler/parser.py`** — `parse_mission` emits `ir_schema_version: 0.2.0`, accepts both v0.2.0 structured (fenced yaml + `**Trigger:**`) and v0.1.0 prose forms. Legacy prose is coerced into the structured shape with the `_legacy_prose` sentinel so existing LOCKED Missions (e.g., MSN-001) validate without edits.
- **`tooling/dekspec/fidelity_audit/linkage.py`** — `T17-MSN-ROLLBACK` checks the new structured shape (either trigger prose or steps populated passes; both empty fires). `L9-MSN-CMD-RESOLVE` extends to `rollback_plan.steps[].cmd` and `kill_criteria[].cmd`, skipping `_legacy_prose` sentinels (`echo SKIP_LEGACY_*`).
- **`tooling/dekspec/constraint_compiler/emitters/agents_md.py`** — `emit_mission` renders the structured rollback trigger + steps and kill_criteria cmd entries; back-compat path retained for any pre-migration string rollback.
- **`templates/mission-template.md`**, **`skills/write-mission/SKILL.md`**, **`skills/run-dekspec-fidelity-audit-v2/SKILL.md`** — updated to teach the v0.2.0 shape, including the `_legacy_prose` / `_legacy_prose_N` sentinel convention for intentionally human-attended steps.

**Explicitly deferred:** `priority` / `concurrency_policy` / `deadline` fields. These belong with the Phase-4 scheduler interface (ds-j8x / FOLLOW.1) — their semantics aren't pinned until an executor binding exists. Adding them now would be the "future-proof hook" the bead warns against.

## [v0.43.5] — 2026-05-17

Infra-only patch. Adds Cloudsmith publishing to the release workflow so tagged builds land on the private `dektora/python-private` index.

### Added — Cloudsmith publish job in release workflow

- **`.github/workflows/release.yml`** — New `publish` job runs after `build` on tag pushes only (`if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')`). Downloads the verified `dist/` artifact produced by `build`, installs `cloudsmith-cli`, and pushes wheel + sdist to `dektora/python-private` using the `CLOUDSMITH_API_KEY` repo secret. Reuses (does not duplicate) the existing test/build pipeline so the same pytest + ruff + version-triad gates protect every published artifact.
- **`RELEASING.md`** — "Post-GitLab migration" section replaced with a "Distribution: Cloudsmith private index" section reflecting the chosen path. Consumer install instructions documented for both the Cloudsmith index URL (held in Doppler as `DEKSPEC_CLOUDSMITH_INDEX_URL`) and the legacy `pip install git+https://...@vX.Y.Z` fallback. GitLab migration sketch retained as a smaller forward-looking note since it remains a possible future state.

### Operator notes

First publish from this version requires the `CLOUDSMITH_API_KEY` repo Actions secret to be in place (User API Key from the `platform-principal@dektora.ai` Cloudsmith account). Cloudsmith org/repo path is hardcoded as `dektora/python-private` in the workflow — not secret-ified.

## [v0.43.4] — 2026-05-17

Patch release. Bundles 8 closed fixes / refactors authored in a single fix-cycle session: 4 audit-rule semantics fixes, 1 doctor UX fix, 1 schema extension, 1 documentation ADR, 1 methodology refactor (skills dispatcher substrate), and 1 L2 artifact promotion.

### Added — ADR-012 (L0 singleton filename convention) (closes ds-ipt)

- **`dekspec/adrs/ADR-012-l0-singleton-filename-convention.md`** (`0aa1e34`) — Documents the convention already encoded in `_detect_artifact_kind` + `_INIT_SINGLETONS`: L0 singletons use slug-only filenames (`system-vision.md`, `domain-glossary.md`, `guidance-and-corrections.md`); L1+ artifacts use `TYPE-NNN-slug.md` (AE/ADR/WS/IC/IB/INT/MSN). `docs/dekspec-methodology.md` §4 + `docs/dekspec-operating-guide.md` §The Artifacts both gained a subsection citing the ADR. Backlinks mirrored on AE-002 + AE-005. Regression tests in `tests/test_init_seeds_l0_singletons.py` pin both halves of the rule.

### Added — `skills/_lib/mode_dispatcher.md` canonical substrate + universal `--teaching` mode (closes ds-int-007)

- **`skills/_lib/mode_dispatcher.md`** (`8a3e7e0`) — New substrate documenting the canonical multi-mode dispatch pattern: universal mode contracts (`--help`, `--audit`, `--review`, `--teaching`), lifecycle mode contracts (`--accept`, `--lock`, `--unlock`, `--revise`, `--resync`, `--dry-run`, `--deprecate`), artifact-specific modes, canonical Mode-Detection + Help Mode + Teaching Mode templates, and a per-skill migration checklist.
- All 12 authoring skills (`write-adr`, `write-ae`, `write-constitution`, `write-evals`, `write-ggc`, `write-ibs`, `write-intent`, `write-ic`, `write-mission`, `write-sv`, `write-tests`, `write-ws`) refactored to cite the substrate, include `--teaching` in `argument-hint` + Mode Detection + Help Mode blocks, and gained a parameterized `## Teaching Mode` H2 section.
- New `tests/test_skills_dispatcher.py` lint test parametrically asserts every authoring SKILL.md cites the substrate + implements universal modes + lists `--teaching` in `argument-hint` + has the Teaching Mode section. `write-tests` documented-exempt from `--review` (deterministic test code has no Open Issues surface).

### Added — AE schema `related_intents` field + L6 backlink integrity over Intents (closes ds-u69)

- **`tooling/dekspec/schemas/architecture-element.schema.yaml`** + parser + graph + L6 fixer (`68b1337`) — `linked_artifacts.related_intents` is now a first-class AE field. `_extract_linked_artifacts` parses `**Related Intents:**` (and the short `**Related INTs:**`) bullets. `graph.consumers_of_ae` walks Intent → AE references and surfaces them as `('INT-NNN', 'intent', 'linked_architecture_elements')` tuples. `_LABEL_BY_KIND` gains `intent: "Intents"` so the L6 fixer can mechanically backfill. Mission backlinks are intentionally NOT mirrored (Missions reach AEs only transitively via `intent_queue`, so a Mission → AE mirror would be transitive rather than direct).
- Self-spec backfill: all 7 library AEs with Intent consumers updated; AE-008 + the AE template seeded with `Related Intents: none` placeholder.
- AE template (`templates/architecture-element-template.md`) updated with the new placeholder row.
- 6 new tests covering parser, graph, L6 rule, and L6 fixer; existing `test_l6_finding_when_backlink_missing` parametric row added for `intent` kind.

### Fixed — doctor minor-only findings now surface as ADVISORY (exit 0), not WARNING (exit 1) (closes ds-cx6)

- **`tooling/dekspec/cli.py::cmd_doctor`** (`59d8732`) — Aggregation rewritten with a 4-state contract: `clean` (0 findings, exit 0), `advisory` (minor only, exit 0, non-blocking by design), `warning` (any important, exit 1), `critical` (any critical, exit 2). Resolves the standing tension between CLAUDE.md guardrail "doctor returns CLEAN" and audit rules (L9, L10) that emit advisory minors on intentionally-aspirational artifacts.
- **ADR-005** amended with the doctor-aggregation gating table + Validation citation; Modified bumped + Amendment Log entry.
- **CLAUDE.md** guardrail reinterpreted: "CLEAN or ADVISORY (minor-only) today; exits 0. Only important and critical gate."
- 5 new tests covering all 4 state transitions + JSON-mode advisory + graph-parse-critical-dominates-audit-advisory cross-section ordering.

### Fixed — L7b-INT-COMPONENTS-RESOLVE severity now tracks Intent status per SKILL.md (closes ds-eua)

- **`tooling/dekspec/fidelity_audit/linkage.py::_l7_intent_linkage`** (`3cec0a3`) — L7b severity is now status-conditional per the SKILL.md spec ("HARD FAIL at ACCEPT"). DRAFT and PROPOSED Intents emit `minor` (advisory; paths may be aspirational while the Intent is being authored); ACCEPTED, IMPLEMENTING, TESTFAIL, TESTPASS, MERGED, and LOCKED Intents emit `important` (committed; missing match is a real linkage break). DEPRECATED + SUPERSEDED still skip entirely. First L-rule with per-(rule, status) severity; pattern parallels `_l9_verification_resolves`.
- 7 new tests in `tests/test_l7_intent.py` pin every status transition + the existing test now asserts severity=minor on DRAFT.

### Fixed — L10 glossary-coverage no longer over-flags §-refs, artifact-title cross-refs, template section names, proper nouns (closes ds-q3t)

- **`tooling/dekspec/fidelity_audit/linkage.py::_l10_glossary_coverage`** + `_TITLECASE_PHRASE` regex + `_L10_STOPWORDS` (`0a03ca2`) — Four heuristic improvements: (a) negative-lookbehind on `§` skips section-pointer phrases (`§Mission Verification`, `MSN-001 §Mission Verification`); (b) Title-Case phrases from every loaded artifact's H1 `name` field are added to the `known` set so cross-refs to another artifact's title (or self-references) don't flag; (c) `_L10_STOPWORDS` extended with template-mandated section names (`Mission Verification`, `Business Rules`, `Acceptance Criteria`, `Constitution Article`, `Failure Behavior`, `Provider AE`, etc.) and IR kind names; (d) small proper-noun allowlist (`Apple Silicon`, `GitHub Actions`, `North America`, etc.).
- Library doctor went from `minor=2` to `minor=0` — the previous advisories on `Mission Verification` (INT-004) and `Constitution Article` + `Security Profile` (INT-007) were all false positives correctly suppressed by the refined heuristic. The rule still fires on genuine recurring undefined Title-Case jargon (regression test included).

### Fixed — IC-004 + WS-003 autonomy enum vocab aligned with schema (closes ds-mm4)

- **`dekspec/api-contracts/IC-004-executor-contract.md`** + **`dekspec/working-specs/WS-003-executor-swap-contract.md`** (`f926c2b`) — IC-004's `enforce_autonomy` parameter table used a stale `manual / assisted / supervised / autonomous` vocabulary inherited from initial draft; replaced with the schema enum (`manual / low / medium / high`) per `mission.schema.yaml::autonomy_ceiling` + `intent.schema.yaml::autonomy`. The L8-INT-AUTONOMY-EXCEEDS audit rule already used the correct vocabulary. Two open questions (one in each artifact) resolved with a documented mapping for legacy phrasing.

### Changed — IC-004 + WS-003 promoted PROPOSED → ACCEPTED (closes ds-zlz)

- **`dekspec/api-contracts/IC-004-executor-contract.md`** + **`dekspec/working-specs/WS-003-executor-swap-contract.md`** (`38b64d7`) — Review pass completed; both promoted to ACCEPTED. IC-004 has 3 remaining open issues, all non-blocking and deferred (lifecycle instrumentation, Provider AE split when DekFactory lands, heartbeat watchdog choice). WS-003 has 2 remaining non-blocking (stale-heartbeat default, stub DekFactory fixture — the latter blocks the eventual LOCKED promotion and is tracked as `ds-jzg`).

### Systemic note

This release closes 8 of 9 beads from a single session-end fix queue. The 9th (`ds-kyt`, "Decide Executor IC split when DekFactory AE lands") is intentionally deferred — explicitly contingent on the DekFactory AE which does not yet exist in `dekspec/`.

### Net

- 725 passing tests (was 618 at start of this fix-cycle; +107 new tests across L7b status, L10 heuristic, L6 Intent backlinks, doctor 4-state, init filename convention, skills-dispatcher lint). 110 skipped, zero failures.
- Ruff clean.
- `dekspec doctor --at .` audit linkage: `critical=0 important=0 minor=0` CLEAN. `ir_count`: 48 → 49 (+1, ADR-012).
- Exit code: 0.

### Upgrade note for consumers

- Doctor's exit code on minor-only findings changed from 1 (WARNING) to 0 (ADVISORY). CI consumers that branch on `dekspec doctor` exit code will see fewer non-blocking failures; this is the intended behavior per ds-cx6. If a consumer's CI was relying on minor-only failures to fail-fast, switch to `dekspec audit linkage --severity minor` for the strict gate.
- L7b-INT-COMPONENTS-RESOLVE severity changed from status-agnostic `important` to status-conditional (`minor` at DRAFT/PROPOSED, `important` at ACCEPTED+). Consumers with DRAFT Intents that reference aspirational paths will see those findings drop from `important` to `minor` (and thus from `WARNING` to `ADVISORY` overall). ACCEPTED+ Intents see no change.
- L10-GLOSSARY-COVERAGE will fire on substantially fewer Title-Case phrases. Consumers should re-audit and may find previously-suppressed false-positive advisories are no longer surfaced. The rule still fires on genuine recurring undefined jargon.
- AE schema gains `related_intents` as an optional field; existing AEs continue to validate without changes. Authors who want explicit Intent → AE backlinks should add `**Related Intents:** INT-NNN, INT-NNN` rows under `## Linked Artifacts`. L6-BACKLINK now surfaces missing Intent backlinks (advisory, non-blocking under the new doctor ADVISORY semantics).
- All 12 authoring skills (`/write-ae`, `/write-adr`, `/write-ws`, `/write-ic`, `/write-ib`, `/write-intent`, `/write-mission`, `/write-evals`, `/write-tests`, `/write-sv`, `/write-ggc`, `/write-constitution`) gain a new universal `--teaching` mode (interactive tutorial for new authors). All cite the new substrate at `skills/_lib/mode_dispatcher.md`.

## [v0.43.3] — 2026-05-17

Patch release. Single bug fix to D-15a + INT-005 design Intent for session-lifecycle work. Closes the v0.43.x patch stream initiated by the L6 + T11 + LX-DUP + D-15a systemic-alignment work today.

### Fixed — D-15a-WS-RATIONALE-NO-ADR-CITE silently never fired (ds-rv1)

- **`tooling/dekspec/fidelity_audit/linkage.py::_d15_prose_drift_wsicib`** (ea890f5) — D-15a's WS code path read `ws.get("goal")` + `ws.get("motivation")` for prose scanning. Neither field is emitted by `parse_ws` (the WS schema doesn't define them either). Because the read used `.get()` with implicit None handling, `prose_chunks` was always empty and D-15a never produced a finding on any corpus. **Silent feature loss** — the rule was registered + counted but didn't actually run.
- Surfaced by the systemic audit-rule alignment pass run after fixing L6 (`ds-216`), LX-DUP (`ds-audit-lx-dup-...-ae1`), and T11 (`ds-pto`). The Explore-agent scan of all ~50 rules' IR-field reads against `parser.py` emissions caught this as the only additional same-shape misalignment.
- **Fix:** D-15a now reads `what_this_does.prose` + `what_this_does.mechanism` (the WS's actual prose surfaces). Parallels the D-15c (IB) pattern of reading `ib.get("goal")` + `ib.get("constraints_and_decisions", [])` — both real fields on their respective artifact kind.
- **Severity direction:** distinct from L6 / T11 / LX-DUP. Those three caused OVERfire (false findings on artifacts that should pass). D-15a caused UNDERfire (silent feature loss — no false findings, but no true findings either). Same shape; different blast radius.
- **Tests:** `tests/test_linkage.py` — 7 new cases on a `_FakeWSGraph` stub: fires on `.prose`, fires on `.mechanism`, silent when ADR-cited in the same sentence, silent when WS has no `what_this_does`, status-gate on DEPRECATED / SUPERSEDED / TODO (×3 parametrized). `tests/test_ds_52p_rules.py` — 2 pre-existing D-15a tests updated to use the correct field shape (they were green only because they stubbed the broken-side field shape, masking the production noop).

### Added — INT-005 design Intent (session-lifecycle enforcement gate)

- **`dekspec/intents/INT-005-session-lifecycle-and-enforcement-gate.md`** (8fab7d9) — DRAFT design parent Intent for `ds-session-lifecycle-commit-gate-6c9`. 227 lines. §Size assessment OVERSIZED on 3 axes (Implementation Units ~5-6, Components affected ~9 paths, Coverage gaps 8). §Mission decomposition plan lays out 4 child Intents (data plane / control plane / enforcement plane / orchestration plane) plus an alternative 5-child shape that carves out audit-trail. Pattern-matched on INT-001's role for MSN-001's Constitution work. Terminal walk planned: DRAFT → OVERSIZED → SUPERSEDED once child Intents + Mission frame land. Authored via `dekspec:intent-author` subagent per CLAUDE.md self-spec edit guardrails.

### Systemic note

Four checker/parser disagreements found and fixed in this single release stream (v0.43.0 → v0.43.3 across one calendar day): L6-BACKLINK (ds-216), T11-AE-BOUNDARY (ds-pto), LX-DUP (pre-existing), and now D-15a (ds-rv1). All share the same shape — parser emits field/shape X, checker assumes field/shape Y, they diverge silently. The underlying cause: manually-authored parallel field-name dictionaries between parser and checker. A higher-level structural fix (shared IR-field constants module, or schema-driven introspection of parser emissions) is worth scheduling as a separate Intent — surfaced as a follow-on candidate in the v0.43.2 + v0.43.3 commit messages.

### Net

- 616 passing tests (was 609 at v0.43.2; +7 new D-15a parametrized cases), 109 skipped, zero failures.
- Ruff clean.
- `dekspec doctor --at .` audit linkage: `critical=0 important=0 minor=1` (unchanged from v0.43.2 — the library's own WS prose doesn't trigger D-15a phrases without ADR cites, so the fix is purely additive on the dogfood corpus). `ir_count`: 44 → 45 (+1, INT-005).

### Upgrade note for consumers

Consumers with WSes that contain decision-rationale prose ("we chose X", "the rationale is", etc.) outside ADR citations will newly see D-15a-WS-RATIONALE-NO-ADR-CITE findings after bumping to v0.43.3. These were always supposed to fire; the upstream rule was silently broken until this patch. No false-positive risk; the findings reflect real ungoverned decision rationale that should be routed to an ADR.

## [v0.43.2] — 2026-05-17

Patch release. Single bug fix to the AE non-goal parser + T11 audit message.

### Fixed — T11-AE-BOUNDARY parser accepts em-dash separator (ds-pto; closes downstream `ds-t11-non-goal-with-why-template-parser-checker-fo-l2g`)

- **`tooling/dekspec/constraint_compiler/parser.py`** (4b7e762) — `_NON_GOAL_BULLET` only matched `- **Name.** prose.` (bold-led, period-split). The AE template + the T11 audit message both prescribe `- text — why` (em-dash separator), so every template-following AE silently dropped the `why` field and failed T11 — 16 AEs flagged in dektora today were following the template literally and getting penalized for it.
- **Fix:** added `_NON_GOAL_BULLET_DASH` regex matching the em-dash separator form. `_extract_boundaries` now does two passes — bold-led first (span-tracked), then em-dash on uncaptured spans (avoids double-counting `- **Not X.** prose with — inside.`). Plain-text fallback unchanged: bullets matching neither form get `{text}` only and no `why`, so T11 correctly flags those.
- **Audit message rewritten** in `tooling/dekspec/fidelity_audit/linkage.py::_t_artifact_completeness` to name BOTH supported forms instead of `T11 requires a \`— \` why clause` (which actively misled authors trying to fix the finding by adding em-dashes that the parser then ignored).
- **Tests:** `tests/test_parser_ae.py` — 5 new cases on a `_make_ae_with_boundaries` tmp_path fixture: em-dash form, bold-led form (regression), mixed forms in the same section, plain-text fallback, bold-led with em-dash inside the why (overlap-dedup).

### Systemic note

This is the third checker/format disagreement found in dekspec's audit engine in this same release stream (`ds-216` L6, `ds-audit-lx-dup-...-ae1` LX-DUP, and now `ds-pto` T11), all sharing the same shape — parser produces X, checker expects Y. A higher-level audit pass over every rule's parser-output vs checker-expected alignment may be worth scheduling.

### Net

- 609 passing tests (was 604 at v0.43.1; +5 new parametrized T11 cases), 109 skipped, zero failures.
- Ruff clean.
- `dekspec doctor --at .` audit linkage: `critical=0 important=0 minor=1` (unchanged from v0.43.1 — the library's own AEs already use the bold-led form, so this fix is purely additive on the dogfood corpus).

### Upgrade note for consumers

Consumers whose AEs use the `- Not X — reason` em-dash separator (the AE template's suggested form) will see T11-AE-BOUNDARY findings drop substantially after bumping to v0.43.2. For dektora specifically, the 15 AEs flagged in the bump-bead `bd-ujpq` will clear automatically after this version is picked up — no AE edits required.

## [v0.43.1] — 2026-05-17

Patch release. Single bug fix to the L6-BACKLINK audit rule.

### Fixed — L6-BACKLINK checker reads `related_ibs` (ds-216; closes downstream `ds-audit-fix-apply-is-noop-audit-checker-disagrees-rud`)

- **`tooling/dekspec/fidelity_audit/linkage.py::_l6_backlink_integrity`** (2c376d0) — the L6 checker hardcoded a 3-entry dict (`adr` / `ws` / `ic`) and defaulted `kind="ib"` to `set()`. Because `consumers_of_ae()` correctly returns IB-kind consumers (D-17, since v0.40.0), the checker silently skipped them and always emitted a finding — even when the AE's `linked_artifacts.related_ibs` listed the IB. The fix-proposer (`_propose_l6_fixes`) uses `f"related_{kind}s"` dynamically and handles all 4 kinds correctly, so the checker and fixer disagreed: `dekspec audit linkage --fix --apply` wrote correct content; the re-audit kept flagging the same artifacts. Symptom: `--fix --apply` was a side-effect-only noop — modified files, never reduced the audit count.
- **Fix:** replaced the hardcoded dict with `linked.get(f"related_{kind}s", [])` to mirror the fix-proposer's pattern. Also forward-compatible with `ds-u69` (Intent / Mission AE backlinks).
- **Tests:** `tests/test_linkage.py` — 8 new parametrized regression cases on a `_FakeL6Graph` stub: `test_l6_no_finding_when_backlink_present[adr/ws/ic/ib]` + `test_l6_finding_when_backlink_missing[adr/ws/ic/ib]`. Without this fix the IB-kind no-finding case fails (finding fires); with it, all 4 kinds × both directions pass.
- **Dogfood:** the library's own corpus was hiding 11 IB-kind backlink gaps behind this bug. With the rule corrected and `--fix --apply` re-run on the library, 12 backlink fills landed across 6 AE files (AE-001/002/003/004/006/007). Doctor: `critical=0 important=0 minor=19 → critical=0 important=0 minor=1` (sole remaining minor is an L10-GLOSSARY advisory on "Mission Verification", tracked by `ds-l10-glossary-coverage-overly-aggressive-on-cross-q3t`).

### Net

- 604 passing tests (was 596 at v0.43.0; +8 new parametrized L6 cases), 109 skipped, zero failures.
- Ruff clean.
- `dekspec doctor --at .` audit linkage: `critical=0 important=0 minor=1`.

### Upgrade note for consumers

Consumers pinned at any v0.43.x or earlier where `--fix --apply` was being relied on for L6 auto-remediation should bump to v0.43.1. Running `dekspec audit linkage --fix --apply` after the bump may newly surface previously-hidden IB-kind backlink gaps; the fix-proposer will offer mechanical fills for them in the same run.

## [v0.43.0] — 2026-05-17

Minor release. Headline: **Constitution L0 singleton** — DekSpec's L0 ring grows from two singletons (System Vision + Domain Glossary) to three. The Constitution is a typed 8-article artifact (Project Identity, Technology Stack, Quality Standards, Architecture Principles, Development Workflow, Model Configuration, Boundaries, Amendments) that names the project's non-negotiable operational commitments and is composed at the top of the rendered `AGENTS.md` so agents working in the repo cite Articles by name in their reasoning output. The library ships the schema, parser, round-trip emitter, T-/L-CONSTITUTION audit rules, the `/write-constitution` 8-mode authoring skill, the AGENTS.md fragment emitter + aggregator composition, a regeneration-byte-stability CI gate, and the library's own self-spec Constitution as the first dogfood instance. Closes MSN-001 (Introduce Constitution L0 singleton — TODO → COMPLETE 2026-05-17) and supersedes INT-001 via INT-002 / INT-003 / INT-004. Plus install-script UX hardening (PEP 668 + pipx fallback, 5 P1 ordering bugs fixed), L0/L1 init seeding so a fresh `dekspec init` is doctor-CLEAN out of the box, and an LX-DUP audit scoping fix.

### Added — Constitution L0 schema + parser + library instance (INT-002)

- **`tooling/dekspec/schemas/constitution.schema.yaml`** (1360e4d) — 9th IR schema. `prefixItems` + `minItems: 8` + `maxItems: 8` + `additionalProperties: false` pins the 8-article structure positionally; per-article shapes split across `pointer` (Article 1: `summary` ≤ 500 chars + `see_also` path), `text` (Articles 2/3/5/6/8: opaque markdown body), and `ref-array` (Article 4: typed `adr_refs`; Article 7: typed `adr_refs` + `ae_refs`). Authored under IB-001 with 43 regression tests.
- **`templates/constitution-template.md`** (1360e4d) — canonical authoring template for consumer `/write-constitution --create` use.
- **`parse_constitution(path) → IR`** + **`emit_constitution_markdown(ir) → str`** + **`ConstitutionParseError`** (d2f97f5) in `tooling/dekspec/constraint_compiler/parser.py`. Round-trip emit(parse(p)) byte-equals read(p) for canonical-style fixtures (WS-004 BR6). `SpecGraph.constitution()` accessor mirrors `vision()` / `glossary()`. CLI dispatch recognizes `constitution.md` basename. Smoke fixture + 4 smoke tests under IB-002. Two parser regex bugs surfaced + fixed: newline-eating `\s*` in pointer label regexes → `[ \t]+`; silently-skipped malformed bullets → `_REF_BULLET_ANY` guard raises `ConstitutionParseError`.
- **`dekspec/constitution.md`** (3a48f68) — library's own self-spec Constitution as the dogfood corpus. Round-trip byte-equal verified. 9 rejection fixtures + 18-case comprehensive parser matrix under IB-003.

### Added — Constitution audit rules + authoring skill (INT-003)

- **T-CONSTITUTION-ARTICLE-PRESENT** (critical) + **T-CONSTITUTION-ARTICLE-POPULATED** (important) (f32b1fd) — structural-completeness checks landed in `tooling/dekspec/fidelity_audit/linkage.py`. Registered in `profiles/v1.yaml`. 14 tests under IB-004.
- **L-CONSTITUTION-ARTICLE-1-SV-REF** + **L-CONSTITUTION-ARTICLE-4-ADR-REFS** + **L-CONSTITUTION-ARTICLE-7-BOUNDARY-REFS** (0ba1c96) — three linkage rules wired against `SpecGraph.has()` resolution. Library Constitution dogfood test in `tests/test_constitution_audit_l_rules.py`. `tests/_specgraph_stubs.py` promoted to shared module for T-rule + L-rule + future emitter test reuse. ADR-007 dogfood-gate enforced.
- **`/write-constitution` 8-mode authoring skill** (a81ae56) — Creation / Audit / Review / Resync / Revise / Accept / Dry-run / Help catalog at `skills/write-constitution/SKILL.md` modeled on the `/write-evals` v0.40.0 rebuild. 14 structural smoke tests under IB-006.

### Added — Constitution AGENTS.md emitter + determinism gate (INT-004)

- **`emit_constitution(ir) → list[str]`** (09069a1) in `tooling/dekspec/constraint_compiler/emitters/agents_md.py`. Returns exactly 8 fragments in canonical article order; dispatch by article `kind` (pointer / text / ref-array, with Article 7's dual-sub-list special-cased). Per-fragment byte-stable determinism via insertion-ordered iteration and zero wall-clock / hash / set / sorted calls. 20 smoke tests in `tests/test_emitter_constitution_smoke.py` covering BR1-7.
- **Aggregator composition** (09069a1) — `cmd_aggregate_agents_md` in `tooling/dekspec/cli.py` extended to compose the 8 Constitution fragments at the top of `AGENTS.md` (before System Vision / Glossary / AE / ADR / WS / IB / Intent / Mission sections); skipped entirely when `graph.constitution() is None`. `--include CONSTITUTION` wired into `valid_kinds` + default flag.
- **`tests/test_emitter_constitution.py`** (c95a67c) — IB-008 comprehensive matrix. `test_determinism` (MSN-001 §Mission Verification pinned name) runs `dekspec aggregate agents-md --at .` N=10 against the library's own corpus and asserts byte-equal output after stripping `Compiled: <timestamp>` lines. Plus `test_aggregator_regeneration_byte_stable` (descriptive companion), `test_aggregator_includes_library_constitution` (all 8 headings render), `test_no_lossy_round_trip` (every IR text fragment appears in the rendered slice), `test_aggregator_omits_constitution_when_absent` (tmp_path corpus without Constitution still composes successfully).

### Added — init now seeds L0/L1 singletons (closes ds-init-does-not-seed-l0-l1-singletons-dgh)

- **`dekspec init`** (1ba261e) now writes `system-vision.md` + `domain-glossary.md` + `guidance-and-corrections.md` parser-valid stubs to the new `dekspec/` tree. A fresh `dekspec init` followed by `dekspec doctor --at .` returns CLEAN — no T-VISION-INCOMPLETE finding fires on a brand-new corpus. Stubs are structurally minimal but distinguish authored-content from placeholder via inline guidance pointing at `/write-sv` and `/write-ggc`.

### Fixed — install script UX hardening (closes ds-install-script-ux-hardening-1jc)

- **`scripts/install-dekspec.sh`** (5627b69) — PEP 668 detection (Ubuntu 23.04+, Debian 12+, Fedora 38+) with automatic pipx fallback when pipx is on PATH; `--installer {auto,pip,pipx}` flag for explicit control. README + docs + script docstring transitioned from `curl | bash` to `gh repo clone` bootstrap to avoid pipe-into-shell trust patterns.
- **`scripts/install-dekspec.sh`** (0f47b26) — fixed 5 P1 ordering + architecture bugs: skills-vendoring architecture pinned to Option A (canonical at `dekspec/skills/`, shims at `.claude/skills/<name>` symlinking back); `dekspec init` no longer skipped on upgrade; `migrate-artifacts --from-default` ordering corrected; install next-steps reference the correct `migrate` command form; version marker written after pip install, not before.
- **`scripts/install-dekspec.sh`** (1873a72) — added pre-migration notice + 7→0 countdown before `migrate-artifacts --apply` so consumers can interrupt if the migration target is wrong.

### Fixed — LX-DUP audit scoping (closes ds-audit-lx-dup-ignores-ib-ws-scope-ae1)

- **LX-DUP rule** (ed718a5) in `tooling/dekspec/fidelity_audit/linkage.py` — composite `<spec_id>:<ib_id>` storage key in SpecGraph + parent-scoped grouping in `_lx_duplicate_ids`. IBs with the same ID under different parent WSes no longer false-fire the LX-DUP critical finding. Added `SpecGraph.ib_by_scope(spec_id, ib_id)` accessor for unambiguous IB lookup.

### Mission / Intent closures

- **MSN-001** (023ed86) — Introduce Constitution L0 singleton: TODO → ACTIVE → COMPLETING → COMPLETE 2026-05-17. All 4 Mission Verification predicates green (`full-suite-green`, `library-constitution-validates`, `doctor-clean`, `agents-md-determinism`).
- **INT-001** (023ed86) — Constitution artifact (design parent): DRAFT → OVERSIZED → SUPERSEDED by INT-002/003/004.
- **INT-002 / INT-003 / INT-004** (023ed86) — all walked DRAFT → LOCKED in a single strict-ceremony Amendment Log row each, citing IB-001..008 commit refs as proof.

### Net

- 596 passing tests (was 452 at v0.42.0; +144 new tests across the 8 Constitution IBs + init seeding), 109 skipped, zero failures.
- Ruff clean.
- `dekspec doctor --at .` audit linkage: critical=0 important=0 minor=19 (carryover-baseline-acknowledged minor findings; ADR-007 dogfood gate satisfied at critical + important tiers).
- 9 self-spec artifacts authored or transitioned this release: 1 mission (MSN-001), 4 intents (INT-001 superseded; INT-002/003/004 locked), 3 working specs (WS-004 / WS-005 / WS-006), 8 implementation briefs (IB-001..008), and 1 L0 singleton (the library's own `dekspec/constitution.md`).

## [v0.42.0] — 2026-05-16

Minor release. Pins the **executor contract** that DekFactory (and any other future runtime executor) will implement: `IC-004-executor-contract` defines the dispatch/event/complete surface against `dekspec.lifecycle`, and `WS-003-executor-swap-contract` pins the behavioral guarantees that hold across any conforming executor. Today's `/run-coding-session` skill is now itself a conforming executor — it writes to the execution-attempt lifecycle DB through three new CLI write subcommands. Earlier the flywheel substrate was effectively blind to the only executor that existed.

### Added — executor contract layer

- **IC-004-executor-contract** (e490f66, PROPOSED) — pins the Executor ↔ Dispatch caller boundary at `dekspec/api-contracts/IC-004-executor-contract.md`. Four capabilities (`dispatch`, `report_event`, `complete`, `enforce_autonomy`) mapped to `dekspec.lifecycle` calls. Granularity rule: one execution attempt = one Intent's worth of work; per-bead state lives in events. Idempotency on `(intent_id, attempt_number)`; cross-Intent dispatch refused before any lifecycle write; CI failure is NOT a contract error.
- **WS-003-executor-swap-contract** (e490f66, PROPOSED) — pins 9 BRs across `dekspec/working-specs/WS-003-executor-swap-contract.md`: verification equivalence, autonomy bounded, lifecycle-DB consistency, engineer-visible parity, fail-closed on DB unavailable, no silent reconciliation, partial-swap mode, attempt ordering. 3 ACs map to BRs and are verifiable once a stub second executor exists (ds-jzg).

### Added — executor write CLI surface

- `dekspec executions record-attempt --intent --agent --attempt N [--mission] [--compile-run] [--audit-profile] [--at] [--json]` (7816e8a) — insert a new `execution_attempts` row; idempotent on `(intent_id, attempt_number)`; `--json` emits `{"attempt_id": N}` for shell callers.
- `dekspec executions record-event --attempt N --type EVENT_TYPE [--payload JSON] [--custom-type LABEL] [--agent]` (7816e8a) — append a structured event to an in-flight attempt; `--type` validated against the canonical set (`agent_question` / `first_pass_fail` / `ci_failure` / `constraint_violation` / `escalation_request` / `retry` / `kill_triggered`) or `custom` + `--custom-type`.
- `dekspec executions complete --attempt N --ci-status {pass,fail,skipped,error} [--violations N] [--escalation] [--merged --merge-commit SHA] [--notes]` (7816e8a) — finalize an in-flight attempt; `--merged` requires `--merge-commit` (CLI-side check). Auto-recomputes `merge_outcomes` for the Intent.
- Together these complete `dekspec.lifecycle`'s producer-side surface: any executor (markdown skill, Python CLI consumer, future DekFactory binary) can now write through a stable CLI on-ramp without importing the Python package.

### Changed — `/run-coding-session` is now an IC-004 executor

- `skills/run-coding-session/SKILL.md` (a93dd48) gains a "Lifecycle DB writes (IC-004 compliance)" section before Phase 1 that instructs the orchestrator to invoke the new write CLI at the right phases: Phase 1 `record-attempt` per unique Intent in the dispatch set, Phase 2-3 `record-event` per significant bead event (canonical types), Phase 4 `complete` with aggregate outcome. Per WS-003 FB3, the skill now fails closed if `dekspec executions` is unavailable rather than running blind. The change is instruction-only — the underlying CLI commands are deterministic, but whether the orchestrator follows the skill in every dispatch is a "model follows instructions" question (a Python ABC + conformance test stub are queued as ds-ehb + ds-jzg).

### Net

- 452 passing tests (was 447; +5 new for the executions write CLI), zero failures.
- Ruff clean.
- `dekspec doctor --at .` returns ✓ CLEAN (audit linkage critical=0 important=0 minor=0, ir_count=28, parse_failures=0).
- 8 follow-up beads filed (5416ba8): `ds-nj1` (dekspec executor CLI family), `ds-jzg` (stub DekFactory executor for WS-003 AC1 fixtures), `ds-ntp` (stale-heartbeat watchdog), `ds-ki9` (plugin slash command + subagent for executor dispatch), `ds-mm4` (autonomy enum vocabulary), `ds-ehb` (Python ABC for IC-004 conformance), `ds-kyt` (Executor IC split when DekFactory AE lands), `ds-zlz` (review pass + LOCKED promotion).

## [v0.41.0] — 2026-05-16

Minor release. Three headline additions: the **DekSpec Claude Code plugin** (slash-command wrappers, schema-aware authoring agents, audit/drift hooks), **`dekspec upgrade` + `dekspec migrate-artifacts` CLI subcommands** (atomic engine + content bumps), and a **one-shot install script** (`install-dekspec.sh --with-plugin` collapses installation from 7 commands across 3 surfaces to one). Plus self-spec maturation (INT-001 Constitution Intent + first L2 Working Specs) and an L9 audit fix.

### Added

- **Claude Code plugin** at `plugins/dekspec/` (c4d0b3e, f4b2d9a, 334ed7c) — 9 slash commands wrapping the dekspec CLI (`/dekspec-doctor`, `/dekspec-audit`, `/dekspec-compile`, `/dekspec-init`, `/dekspec-graph-export`, `/dekspec-verify-vendored`, `/dekspec-migrate`, `/dekspec-upgrade`), 7 schema-aware authoring agents (ae / adr / ic / ws / intent / ib / mission), and 2 hooks (audit-drift, session-end). Distributed via `.claude-plugin/marketplace.json` against the same git URL as the library. `bump-version.py` keeps `plugins/dekspec/.claude-plugin/plugin.json` and the marketplace ref in lockstep with `__version__`.
- **`/migrate-artifacts-assist` orchestrator skill** (5539bb7) — guided dekspec/ tree migrations.
- **`dekspec upgrade` + `dekspec migrate-artifacts` CLI** (4bc3dd6) — atomic engine + vendored-content bumps; markdown migration framework underneath.
- **`--library-self-audit` audit mode** (c4d0b3e) — enables self-spec audits with library-internal context (closes ds-a4h).
- **First L2 Working Specs: WS-001 + WS-002** (66ed9ee) — first L2 authoring on the library's own self-spec (closes ds-71x).
- **INT-001 Constitution Intent + intent-index** (e45aaf2) — captures the foundational constitution work (closes ds-int-001).

### Changed — install + README

- **`scripts/install-dekspec.sh`** (ba286da, 27aa44f) — new `--with-plugin` / `--skip-pip` / `--version` flags; pip-installs the engine after vendoring; auto-installs the Claude Code plugin via `claude plugin install` when `--with-plugin` and `claude` is on PATH; detects prior `.dekspec-version` to print upgrade-specific next-steps (`dekspec migrate` + `dekspec audit linkage --fix --apply`); suppresses git's detached-HEAD advisory. End-to-end tested in a scratch consumer project across fresh-install, upgrade, re-install, `--skip-pip`, and three `--with-plugin` scenarios (real claude binary + mock-claude success/failure/not-on-PATH).
- **`README.md`** (ba286da) — Quick Start collapsed from 6 steps to one command; Installation restructured into single-command / flags / manual / auth / vendored subsections; "Sync procedure for consumers" replaced with full "Upgrading dekspec in your project" section covering routine + major-version upgrades, the `dekspec upgrade` CLI alternative, and what each upgrade does (and does not) touch.

### Fixed

- **L9 resolver recognizes venv-installed Python tools** (663190c) — `_resolves()` previously checked only `shutil.which()`, which misses pytest / ruff / dekspec when invoking `.venv/bin/python` directly without venv activation. Now also tries `importlib.util.find_spec()`. Effect: INT-001's 5 `verification[].cmd` entries stop firing L9 findings; 4 previously-failing tests (`test_resolves_pytest_when_on_path`, `test_l9_int_cmd_resolve_real_pytest`, two e2e doctor tests) pass.
- **Install script uses correct `claude plugin` subcommand** (27aa44f) — `claude /plugin install ...` is interactive-only and silently returns exit 0 when invoked from a shell, fooling earlier wiring. Replaced with `claude plugin install ...` (non-interactive). Real-world test confirmed exit-code propagation now works.

### Net

- 447 passing tests (was 400 at v0.40.1, +47 net; the 4 prior failures fixed).
- Ruff clean.
- `dekspec doctor --at .` returns ✓ CLEAN (audit linkage critical=0 important=0 minor=0, ir_count=26, parse_failures=0).
- Plugin install requires the marketplace ref to point at a tag that contains `plugins/dekspec/` — this release is the first such tag.

## [v0.40.1] — 2026-05-15

Patch release. Doc-only. Rolls up the two post-v0.40.0 commits on `main` into a clean consumer-pickup tag. Zero code / schema / rule changes; tests + ruff + `dekspec doctor --at .` unchanged from v0.40.0.

### Changed — layer model framing for Intent + Mission (5949bee)

Sharpens the methodology framing across all three docs to consistently describe Intent + Mission as **L1-anchored, reaching through L2-L4** (their typed graph link is `linked_architecture_elements`, but their behavioral reach spans L2 WSs / ICs, L3 IBs, and L4 verification surfaces). Replaces inconsistent prior framings ("cross-layer pair" / "orthogonal to L1-L4" / omitted from layer table).

- `docs/dekspec-methodology.md` §4 intro rewritten — 9 IRs enumerated as 2 L0 singletons + 4 L1-L3 typed layers + 2 L1-anchored intent vehicles. "Cross-layer" subsection retitled "L1-anchored, reaching through L2-L4".
- `docs/dekspec-quick-reference.md` §Four Layers — new callout paragraph between the layer table and the Hierarchy paragraph.
- `docs/dekspec-operating-guide.md` §Intents — preserves the horizontal "orthogonal to L1-L4" framing and adds the complementary vertical L1-anchored-reaching framing.

### Fixed — self-audit fix bundle, 11 findings closed (3d5ad75)

Post-v0.40.0 self-audit (the library running its own v2 audit against its own `dekspec/` self-spec) surfaced 4 IMPORTANT + 7 MINOR findings. All closed in this bundle.

**IMPORTANT (4):**
- **I-1, I-4** — `docs/dekspec-operating-guide.md` §"System health": phantom `/run-dekspec-fidelity-audit` reference replaced with `/run-dekspec-fidelity-audit-v2`, with a note clarifying v1's frozen-for-history posture per the DN→AE migration.
- **I-2** — Authored repo-root `AGENTS.md` (661 lines) by running `dekspec aggregate agents-md --at . --output AGENTS.md` against the library's own self-spec. The library now has its own AGENTS.md (8 AE + 10 ADR + 18 glossary terms + the library's System Vision), shaped exactly like consumer-side AGENTS.md.
- **I-3** — Authored repo-root `CLAUDE.md` with library-side session rules: project status, repo layout, DekSpec guardrails for the library itself, cross-repo discipline (bead-only consumer notification), release summary, model policy, foundational reading order.

**MINOR (7):**
- **M-1** — Backfilled `## Open Issues` section into all 10 self-spec ADRs (between §Links and §Amendment Log; populated with "None.").
- **M-2** — Backfilled `## Silent Failure Domain(s)` section into all 3 self-spec ICs. Dektora-product-specific checkboxes are intentionally unchecked with a note pointing at DIV-004's outstanding scope; project-neutral failure domains (Emit-format drift / IR-contract drift / Determinism) surfaced as load-bearing notes.
- **M-3** — Filed `ds-71x` (P3) for deferred L2 extension (≥1 WS authoring for a load-bearing library surface).
- **M-4** — `docs/dekspec-operating-guide.md` §Repository Structure: new "Library-side layout (`Dektora/dekspec` repo itself)" subsection explaining that the existing tree describes consumer-side post-vendoring layout, with a full library-side tree.
- **M-5** — `docs/dekspec-operating-guide.md`: new §"Auxiliary skills" block enumerating /function-planner, /high-level-docs, /record-divergence, /do-code-archaeology, /write-ggc with one-line purposes.
- **M-6, M-7** — Remaining MINOR findings addressed in the same bundle (see commit 3d5ad75 for full detail).

### Net

- 400 passing tests (unchanged from v0.40.0).
- Ruff clean (no Python touched).
- `dekspec doctor --at .` returns `✓ CLEAN` (ir_count=23, parse_failures=0, audit linkage critical=0 important=0 minor=0).

### Notes for consumers

Doc-only patch. Re-vendoring via `bash scripts/install-dekspec.sh` is safe but produces no consumer-visible diffs in `dekspec/` (consumer artifacts unchanged); it does refresh the methodology docs vendored to `dekspec/docs/`. Bumping the pin from `v0.40.0` → `v0.40.1` and re-running the v2 audit is recommended but not load-bearing.

## [v0.40.0] — 2026-05-15

Minor release. Bundles five P1/P2 bead closures into a single tag: ds-ibx, ds-i3g, ds-jlk, ds-52p, ds-f2j. Minor bump justified by the new public surface (D-15 + T-glossary + T-vision audit rules in `linkage.py`, the glossary aliases schema field, the `emit_side_coverage` summary on `dekspec graph export`, and the bootstrap of the library's own `dekspec/` self-spec tree under this repo). All parser/audit changes are tolerance-broadening or additive — no consumer markup must change.

### Added — IB IR plumbing (closes ds-ibx)

- **Schema** `implementation-brief.schema.yaml` gains optional `constraints_and_decisions: array<{topic, rule}>` + `domain_constraints: array<{constraint, value}>`. Additive; no `ir_schema_version` bump (existing 0.1.0 IRs continue to validate).
- **Parser** `parse_ib` extracts both sections; `_extract_constraints_and_decisions` recognizes `- **topic:** rule` bullets and skips bracket-topic template placeholders; `_extract_ib_domain_constraints` reads the `| constraint | value |` table and drops bare-`n/a` + bracket-only rows. A `parse_warning` fires when a §Constraints & Decisions section is present but contains only template placeholder text.
- **IB template HTML-comment header** moved both sections from "author scratch pad" to "canonical" with a versioned note.
- Closes audit divergence D-11 (IB portion). DekFactory's stopgap `ib_raw_sections.py` raw-section grabber is no longer needed.
- Tests: 5 new in `tests/test_parser_ib.py`.

### Added — DekSpec self-spec bootstrap (closes ds-i3g, audit divergence D-28)

F-6 Path 1 — DekSpec eats its own cooking. The library now has its own `dekspec/` artifact tree under this repo root, audited by the library's own engine on every PR via `.github/workflows/ci.yml`'s Self-dogfood step (previously a no-op when `dekspec/` didn't exist; now substantive, any finding fails the build).

- `dekspec/system-vision.md` ACCEPTED with all 5 required H2 sections.
- 8 Architecture Elements ACCEPTED under `dekspec/architecture-elements/`: AE-001 DekSpec (umbrella), AE-002 Constraint Compiler, AE-003 Fidelity Audit Engine, AE-004 IR Schemas & Migrations, AE-005 CLI, AE-006 Skills Library, AE-007 Templates Library, AE-008 Vendoring. All structural subtypes carry a `## Views` section.
- 10 ADRs ACCEPTED under `dekspec/adrs/`: extract-as-library, proprietary git distribution, compiler pipeline shape, audit as separate subsystem, severity grading + named audit profiles, JSON Schema with additionalProperties:false discipline, eat-own-cooking, lazy migration registry, vendoring via rsync + drift verification, skills/templates split.
- 3 Interface Contracts ACCEPTED under `dekspec/api-contracts/`: emit_contract_test, emit_ci_gate, emit_agents_md.
- 1 Domain Glossary at `dekspec/domain-glossary.md` (16 terms across Library Surface / Audit Concepts / Methodology categories).
- 3 indexes: `architecture-elements-index.md`, `adr-index.md`, `interface-contract-index.md`.
- `dekspec doctor --at .` returns `✓ CLEAN` (ir_count=23, parse_failures=0, audit linkage critical=0 important=0 minor=0).

### Changed — `/write-evals` rebuilt on `/write-ibs` skeleton (closes ds-jlk)

- `skills/write-evals/SKILL.md` grew from 178 → 508 lines.
- Mode catalog expanded from 3 (Creation / Audit / Revise) to 8 (Creation / Audit / Review / Resync / Revise / Accept / Dry-run / Help) — matches the rest of the `/write-*` family.
- Per-eval 10-field elicitation in Creation Mode (scenario / type / measurement layer / input / expected range / pass criterion / model pin / sampling strategy / failure meaning / open issues).
- Candidate audit-rule names documented in a forward-looking section: `T-EVAL-FIELDS` / `T-EVAL-COVERAGE` / `T-EVAL-SET`. These do not yet have implementations in `linkage.py` (no eval IR exists yet); they become mechanical when a future bead lands the eval IR + schema.
- 9 cross-references to `templates/checklists/eval-quality-checklist.md` (Audit + Review + Resync + Dry-Run + Creation modes all ground in the canonical four-layer measurement guidance).
- `docs/dekspec-quick-reference.md` table entry expanded to list the mode catalog.

### Added — D-15 prose drift on WS / IC / IB + singleton self-consistency + IB-aware L6 (closes ds-52p)

Closes audit divergences D-14, D-15, D-16, D-17, D-42, D-43.

- **4 new D-15 rules** in `linkage.py::_d15_prose_drift_wsicib`, registered in profile `v1`. Mirror of D17/D18 onto WS / IC / IB:
  - `D-15a-WS-RATIONALE-NO-ADR-CITE` — WS.goal / WS.motivation
  - `D-15b-IC-RATIONALE-NO-ADR-CITE` — IC.purpose / IC.shared_conventions
  - `D-15c-IB-RATIONALE-NO-ADR-CITE` — IB.goal / IB.constraints_and_decisions
  - `D-15d-IC-NUMERIC-NO-WS-CITE` — IC.purpose / IC.shared_conventions
  Heuristics reused unchanged from D17/D18 (`_D17_NUMERIC_UNIT`, `_D18_RATIONALE_PHRASES`); citation suppression unchanged.
- **5 new T-rules** for singleton self-consistency:
  - `T-GLOSSARY-DUPLICATE` (case-insensitive)
  - `T-GLOSSARY-MISSING-DEFINITION`
  - `T-GLOSSARY-DANGLING-ALIAS`
  - `T-VISION-MISSING-WHY`
  - `T-VISION-INCOMPLETE` (de-dup with `T-VISION-MISSING-WHY` when only `why` is empty)
- **Schema extension** — `domain-glossary.schema.yaml` gains optional `aliases: array<string>` on each term entry. Additive; existing 4-column glossaries continue to parse unchanged. `parse_glossary` reads a 5th comma-separated "Aliases" column when present (both H2-category and top-level-table paths).
- **IB-aware L6-BACKLINK** — `graph.consumers_of_ae` now walks IBs and emits their `source_aes` references; the existing L6 rule and its mechanical-fix proposer automatically surface missing `related_ibs` on the AE side. `_LABEL_BY_KIND` already mapped `"ib" → "IBs"`.
- **Docs** — `README.md §Audit rule families` gains three subsections: schema-validation-vs-linkage division of labor (D-14), what does NOT live here (checklists author-time only, D-42), and L2 reserved (D-43). `skills/write-ae/SKILL.md` and `skills/write-intent/SKILL.md` Audit Mode preambles gain short paragraphs explaining the split.

### Added — parse-and-drop field plumbing into agents_md + emit_side_coverage (closes ds-f2j)

Closes audit divergence D-10. Selected the load-bearing fields from the audit's parse-and-drop enumeration and routed them through the relevant `emit_*` function in `tooling/dekspec/constraint_compiler/emitters/agents_md.py`:

- **AE** — `views.diagrams` (top 4: kind + description), `views.absence_justification` fallback, `runtime_behavior` subsection.
- **ADR** — `options_considered` (option names, top 4), `consequences.positive` and `consequences.negative` (top 3 each with `(+) / (−)` markers).
- **IB** — `constraints_and_decisions` (top 10 as `**topic.** rule` bullets), `domain_constraints` (top 8 as `constraint: value` pairs).

Fields not selected (per-AE relationships_and_dependencies, AE.data_and_state, WS.silent_failure_domains, etc.) stay as parse-only — documented in the new `emit_side_coverage: {<type>: {consumed_by_agents_md: [...], parse_only: [...]}}` summary that `dekspec graph export` now emits at the top level. Hand-maintained in `cli.py::_emit_side_coverage`; authoritative source is `tooling/dekspec/constraint_compiler/emitters/`.

The IC type carries an explicit `note` clarifying that ICs don't have an agents_md emitter today — they surface to consumers via the `contract_test` and `ci_gate` emitters instead.

### Net

- 352 → 400 passing tests (+48 across 7 new + extended test files: `test_parser_ib.py`, `test_parser_glossary.py`, `test_parser_ae.py`, `test_t12_views.py`, `test_parser_adr.py`, `test_parser.py`, `test_ds_52p_rules.py`, `test_emitter_agents_md.py`).
- 109 skipped (CI-equivalent skips unchanged).
- Ruff clean.
- `dekspec doctor --at .` returns `✓ CLEAN` on the library's own self-spec.

### Internal

- Beads closed in this release: `ds-ibx`, `ds-i3g`, `ds-jlk`, `ds-52p`, `ds-f2j`.
- v0.39.0's `[Unreleased]` references to v0.39.0 for ds-i3g done-when #7 and ds-52p done-when #9 reinterpreted as v0.40.0 (this release); the criteria are met here.
- Audit-rule families list in `README.md` updated to include the new T-glossary, T-vision, and D-15 rules; the `v1` profile YAML enumerates all 9 new rule codes.

## [v0.39.0] — 2026-05-15

Minor release. Bundles four upstream-DIV bug-fixes from `Dektora/dekfactory`'s 2026-05-15 L1 reconciliation handoff (ds-47c — LOCKED-blocker, plus ds-og8 / ds-59l / ds-cdg) with the F-3 phase 2 audit-profile-registry feature (ds-j9z) and the ds-re2 test-coverage additions previously staged in `[Unreleased]`. Minor bump justified by the new public-API surface (`load_audit_profile`, `list_audit_profiles`, `AuditProfile`, `--profile` CLI flag). All parser/audit changes are tolerance-broadening — no consumer markup must change.

### Fixed — upstream-DIV handoff from `Dektora/dekfactory` (closes ds-47c, ds-og8, ds-59l, ds-cdg)

Four bug-fixes opened by `Dektora/dekfactory`'s 2026-05-15 L1 reconciliation. ds-47c is the LOCKED-blocker for dekfactory's L1 slate (AE-005/006/007/009/010); the other three are P3 consumer-pain reductions. Acceptance test for the bundle: `dekspec audit linkage --at /home/dfxop/projects/dekfactory` produces zero L10/T12/L4/L6 false-positives on the consumer's ACCEPTED slate.

- **`tooling/dekspec/constraint_compiler/parser.py::_extract_views`** (ds-47c): now extracts H3-with-fenced-source view blocks (`### Deployment view — title` + ```` ```mermaid ```` block) into `views.diagrams[].kind` + `views.diagrams[].inline`. Recognized kinds: context, container, component, dynamic, deployment. Pre-existing italic absence-justification detection preserved. Unblocks T12-AE-VIEWS lock-ceremony on five dekfactory AEs.
- **`tooling/dekspec/constraint_compiler/parser.py::parse_glossary`** (ds-47c): falls back to a top-level markdown table directly under the H1 when no H2 category sections yield rows. Bold-wrapped term cells (`| **Term** | def |`) keep working (pre-existing `strip("`*_")` did this; now it also works in the fallback path). Categories default to "Terms" when the fallback fires.
- **`tooling/dekspec/fidelity_audit/linkage.py::_L10_STOPWORDS`** (ds-47c): added "Options Considered", "Decision Drivers" — ADR section-name references in AE body prose are framework vocabulary, not domain jargon.
- **`tooling/dekspec/constraint_compiler/parser.py::_AE_REF_BULLET`** (ds-og8): regex extended to recognize the bold-wrapped Related-AE bullet form `- **AE-NNN Title** — desc`. Previously this form parsed silently as zero AE refs, causing L1-ADR-AE-MISSING false-positives on every bold-wrapped ADR. All four conventional forms (plain unbulleted, bulleted-with-colon, markdown-link, bold-wrapped) now parse equivalently.
- **`tooling/dekspec/constraint_compiler/parser.py::_extract_parties`** (ds-59l): removed the prose-scan that lifted AE-NNN mentions from Party description prose into `parties[].ae_id`. Party-AE linkage is now structured-only — declared exclusively in the `### Provider AE` / `### Consumer AEs` H3 subsections of §Parties. Prose mentions remain as narrative context but do not produce L4-IC-AE-MISSING / L6-BACKLINK side-effects.
- **`templates/interface-contract-template.md`** (ds-59l + ds-cdg):
  - §Parties: added a paragraph stating Party-AE linkage is structured-only — declare each AE in the H3 subsections; prose mentions are references, not links.
  - §Domain Constraints: generalized — now explicitly optional, with project-neutral framing (example rows kept inline but marked as illustrative; section can be deleted when the project has no boundary-level cross-cutting constraints to inline).
- **`templates/adr-template.md`** (ds-og8): authoring guidance enumerates all four recognized Related-AE bullet shapes so consumers don't discover the constraint at audit time.
- **`skills/write-ic/SKILL.md`** (ds-cdg): mandatory-sections list adjusted — Domain Constraints moved to optional with project-neutral framing; structured-only Party-AE linkage cross-referenced.

**Tests added:**

- `tests/test_parser_ae.py` — five new tests for the H3+fenced-source view extraction path (all five C4 kinds, externalized-diagram form, untyped-H3 skipping, absence-justification regression).
- `tests/test_parser_glossary.py` — two new tests for the top-level table fallback (with and without bold-wrapped term cells).
- `tests/test_t12_views.py` — new file with five tests covering T12-AE-VIEWS firing/clearing semantics over `views.diagrams` vs `views.absence_justification` vs missing-views, plus subtype-scope.
- `tests/test_parser_adr.py` — three new tests for `_extract_related_aes_ws` across all four bullet forms (plain, bulleted-with-colon, markdown-link, bold-wrapped).
- `tests/test_parser.py` — two new tests for IC Party prose scan removal (prose mentions don't populate `ae_id`; structured H3 subsections remain authoritative).

**Net:** 352 → 369 passing tests (+17), 109 skipped, ruff-clean. Run time 3s.

### Added — F-3 phase 2: audit profile registry (closes ds-j9z)

- **`tooling/dekspec/fidelity_audit/profiles/`** (new module + package data). YAML-manifest registry for named audit-rule profiles. Mechanics decided in the 2026-05-12 flywheel session (category-2 decision 2, option A — named bundles + inheritance).
- **`profiles/v1.yaml`** enumerates all 50 rule codes currently emitted by `linkage.py` + the L11-MSN-STALE.days_threshold=90 parameter. v1 is the default profile when an artifact's `audit_profile` field is absent. L2 is intentionally absent (reserved for a future ADR→ADR non-supersession reference rule).
- **`load_profile(name)` + `list_profiles()` + `AuditProfile` dataclass** re-exported via `dekspec.api` as `load_audit_profile`, `list_audit_profiles`, `AuditProfile`. Plus `ProfileNotFoundError` and `ProfileLoadError`.
- **`audit_linkage(..., profile=None)`** accepts a profile name. Findings whose rule isn't in the active profile's rule set are filtered out before return. `L11-MSN-STALE.days_threshold` is now threaded through the profile (defaults to 90 = v1 setting).
- **`dekspec audit linkage --profile <name>`** CLI flag. Without `--profile`, the default is v1 (no behavior change from prior releases — semantic identity test in `test_audit_profiles.py`).
- **Tests:** `tests/test_audit_profiles.py` (16 new tests) — v1 enumeration + linkage-emission identity, inheritance composition (synthetic v2 fixture), cycle detection, name-mismatch detection, public API re-export, `audit_linkage` integration.
- **`pyproject.toml`** package-data extended for `dekspec.fidelity_audit.profiles = ["*.yaml"]`.

### Added — ds-re2 mechanical test additions (closes D-32, D-34, D-36, D-37, partial D-33 + D-35 + D-38)

- **`tests/test_audit_profiles.py`** (16 tests) — profile registry coverage (counted under F-3 above).
- **`tests/test_cli_compile.py`** (6 tests, D-32) — behavioral coverage for `dekspec compile`: parse-only persistence, `--emit ir/contract-test/ci-gate`, output-path writing, missing-source error, argparse rejection of unknown emitters.
- **`tests/test_find_cycles.py`** (11 tests, D-36) — synthetic cycle-detection fixtures: empty graph, self-loop, 2/3-node cycles, DAGs, disjoint cycles, nested cycles, edges to leaf nodes.
- **`tests/test_d_rules_synthetic.py`** (11 tests, D-35 D-rule subset) — synthetic fixtures for D17/D18/D19/D20: positive fires + WS/ADR-citation suppression + terminal-status skips + clean-prose negatives.
- **`tests/test_lx_parse_synthetic.py`** (2 tests, D-35 LX-PARSE) — synthetic parse-failure fixture (malformed IB Status) confirms LX-PARSE surfaces at critical severity.
- **`tests/test_validate_higher_ir.py`** (6 tests, D-33 partial) — validate-coverage for the 4 IR types not in the main e2e pipeline: Domain Glossary singleton, System Vision singleton, Implementation Brief, Mission. Plus a parametrized `--json` envelope test for the singletons.
- **`tests/test_public_api.py::test_api_parse_alias_resolves_to_parse_ic`** (1 test, D-37) — `dekspec.api.parse is parse_ic` identity assertion.
- **`tests/test_l8_mission.py::test_l8_autonomy_exceeds_full_rank_matrix`** (16 parametrized cases, D-34) — exhaustive walk of the `manual < low < medium < high` autonomy-rank ladder. Catches accidental rank-table edits or off-by-one comparison errors.
- **`tests/test_vendoring.py`** (3 new tests, D-38) — vendoring manifest + drift detection against a synthetic library-root in `tmp_path` (not the real source tree). Lets these tests run under wheel installs.

**Net:** 280 → 352 passing tests (+72), 109 skipped (CI-equivalent skips unchanged), ruff clean. Tests run in 5s.

### Internal

- `ds-j9z` (F-3 phase 2 profile registry) closed in this release.
- `ds-re2` (audit-rule + test-coverage fill) — test-additions subset closed. Rule-additions + docs subset carved out to `ds-52p` with design decisions baked in (D-14 docs, D-15 four rules, D-16 five rules + glossary alias schema extension, D-17 mirror, D-42 docs, D-43 reserved).
- Smaller decisions called unilaterally on this PR per "defensible defaults" carve-out: D-17 mirror = extend L6-BACKLINK; D-42 = document checklists as IB-author-time only; D-43 = document L2 as reserved.

### Removed — public PyPI publish workflow

Rationale: DekSpec is proprietary (`pyproject.toml` classifier `License :: Other/Proprietary License`) and is consumed only by Dektora-owned repos (Dektora + DekFactory). The public-PyPI publish step has failed `invalid-publisher` on every release we've cut (v0.37.0 through v0.38.1) and would have published proprietary code to a public index if it had ever succeeded. Both legitimate consumers install via `pip install git+https://github.com/Dektora/dekspec.git@vX.Y.Z`, which works today and gives identical version-pinning guarantees.

Concrete changes:

- **`.github/workflows/publish.yml` renamed → `.github/workflows/release.yml`.** The workflow no longer publishes to any external index — it now exists only to: (a) run pre-release pytest + ruff matrix, (b) build wheel + sdist + smoke-test, (c) assert version-triad (tag == `__version__` == CHANGELOG[0]), (d) upload `dist/*` as a 90-day workflow artifact.
- **`publish-pypi` + `publish-testpypi` jobs deleted.**
- **`workflow_dispatch.inputs.target` (testpypi/pypi choice) deleted.** `workflow_dispatch` still works without inputs for manual reruns.
- **`RELEASING.md` rewritten.** All trusted-publisher / TestPyPI / PyPI yanking sections removed. Documents consumer install via `git+https://...@vX.Y.Z` as the canonical path. Adds a "Post-GitLab migration" section sketching the future `.gitlab-ci.yml` + GitLab Package Registry shape.
- **`README.md` §Installation** updated — `pip install dekspec` recipe removed; only the `git+https://...` recipe remains. Status §Open follow-ons section updated to point at the GitLab Package Registry as the planned end state.
- **`scripts/bump-version.py` docstring + post-bump hint** updated to reference `release.yml` not `publish.yml`.

GitLab migration path: when DekSpec moves to the self-hosted GitLab instance (per DekFactory ADR-003), the workflow ports to `.gitlab-ci.yml` and gains a `twine upload` step targeting `https://${CI_SERVER_HOST}/api/v4/projects/${CI_PROJECT_ID}/packages/pypi`. Consumers gain native `pip install dekspec==X.Y.Z` UX with private auth via the same GitLab tokens they already hold. Sketch in `RELEASING.md`.

No `__version__` bump for this entry — the changes affect release-machinery only, not the library surface or any consumed module.

## [v0.38.1] — 2026-05-12

Patch release. Closes 7 audit divergences from the ds-06n IR-pipeline-tightening bundle: D-10, D-11, D-12, D-13, D-18, D-39, D-41. All changes are additive (parse_warnings emissions, documentation, schema docstrings) or pure removal (v1 fidelity-audit skill); no schema field changes, no breaking parser semantics.

### Added — parse_warnings emissions on Glossary + Vision (D-12)

`parse_glossary` and `parse_vision` now populate the `parse_warnings` field that both schemas have always declared but neither parser previously appended to. The field was structurally orphan — declared, but `len(ir["parse_warnings"]) == 0` was the only achievable outcome. Now warnings fire on:

- `parse_glossary` empty-terms case (info)
- `parse_glossary` blank-term-with-definition row (warning) — likely typo, not silent skip
- `parse_vision` missing-preamble case (info)
- `parse_vision` empty-required-section case (warning)

Three new tests in `tests/test_parser_glossary.py` + `tests/test_parser_vision.py`.

**Behavior change for consumers:** code that asserted "no parse warnings" as a healthy state may now see info/warning-level entries for previously-empty fields. The audit engine treats these as advisory only; no critical/important findings escalate.

### Added — `docs/amendment-log-types.md` reference doc (D-13)

5.5 KB canonical reference for the per-IR `amendment_log.type` enum vocabulary. Documents the three families (A: artifact-lifecycle, B: mission-state-transition, C: intent-minimal), the per-IR family matrix, the `supersession` vs `supersede` naming inconsistency flagged for future unification, and the author's "which type to pick" rule. Vendored to consumers as `dekspec/amendment-log-types.md`. Cross-referenced from inline comments in 6 schemas (adr, architecture-element, intent, interface-contract, mission, working-spec).

### Added — IB + Intent template canonical-vs-scratch-pad markers (D-11)

Both `templates/implementation-brief-template.md` and `templates/intent-template.md` gain HTML comment headers enumerating canonical sections (extracted by parser → schema-validated → emitter-available) vs author scratch pad (rendered for the implementing agent, NOT in the IR). Authors no longer wonder "did this section flow into the IR?" — the template tells them.

### Changed — schema docstring honesty (D-10)

Per-schema top-of-file docstrings in `adr.schema.yaml`, `working-spec.schema.yaml`, `interface-contract.schema.yaml` now enumerate current emit-side coverage explicitly and list the "parsed but no emitter consumes" set. The `interface-contract.schema.yaml::domain_constraints` description corrects the load-bearing-claim mismatch ("Intended as assertion targets ... no emitter consumes this field as of v0.38.x"). Authors still populate; agents_md plumbing is on the near-term roadmap.

### Changed — `contract_test` emitter roadmap (D-39)

`emitters/contract_test.py` module docstring gains an explicit ROADMAP block. Documents the three-phase trajectory:

- Phase 1 (today): skip-stubs only (every assertion `pytest.skip("CONTRACT_STUB: ...")`).
- Phase 2 (TBD): type-narrowed assertions for self-describing operations.
- Phase 3 (TBD/maybe-never): runtime fixture generation (crosses the consumer-isolation boundary).

And calls out the "green test suite ≠ implementation conforms to IC" pitfall the skip-stubs create.

### Removed — v1 fidelity-audit skill (D-18)

`skills/run-dekspec-fidelity-audit/` (16 KB, v1) deleted. README has advertised only v2 since v0.34.0; consumers' next `install-dekspec.sh` run drops the stale v1 copy via `rsync --delete`.

### Changed — schema description normalization (D-41)

Added root-level `description:` blocks to `domain-glossary.schema.yaml`, `mission.schema.yaml`, `system-vision.schema.yaml`. Previously 6/9 schemas had them; now 9/9. Stylistic consistency only — no functional change.

### Internal

- ds-whn bead closed (all done-when items landed in v0.38.0).
- ds-06n bead status: D-3 / D-4 / D-40 / D-44 closed in v0.38.0; D-10 / D-11 / D-12 / D-13 / D-18 / D-39 / D-41 closed in v0.38.1. Still open in ds-06n: per-field plumbing pass for D-10 (IC `domain_constraints`, ADR `options_considered` / `consequences`, AE `views` / `runtime_behavior`), D-19 (/write-evals rebuild).

[v0.38.1]: https://github.com/Dektora/dekspec/releases/tag/v0.38.1

## [v0.38.0] — 2026-05-12

Minor release. Bundles three audit/flywheel PRs plus a doc-drift closeout landed since v0.37.2:

1. **Stop-the-bleeding** (NOW PR from 2026-05-11 audit) — D-1, D-2, D-26, D-27.
2. **Singleton IR remediation** (SOON PR from 2026-05-11 audit) — D-3, D-4, D-40, D-44, plus a conftest fix surfaced while writing the SOON tests.
3. **Flywheel category-1** — F-1 lifecycle DB + F-3 phase 1 audit_profile field. New module: `dekspec.lifecycle`. New CLI: `dekspec executions ls/show/metrics/tag/amend/link`. New schema field: `audit_profile` on Intent / IB / Mission / WS. SQLite index schema version bumps 1 → 2 with in-place auto-migration of existing v1 DBs.
4. **Doc-drift closeout** — D-20, D-21, D-22, D-23, D-24, partial D-25, partial D-28. README CLI table updated for `migrate` + `runs gc`, header corrected to "eleven subcommands", `docs/cli-reference.md` added + vendored, `docs/EXAMPLES.md` added to the vendor manifest, EXAMPLES.md TOC expanded for the 6 previously-undemonstrated API surfaces (ci_gate / contract_test / schemas / migrations / persistence / vendoring). `scripts/bump-version.py` utility added to keep `__version__` / install-script fallback / README install-URL / EXAMPLES GHA pin in lockstep. `ci.yml` extended with two new steps: a version-mirror drift check (`bump-version.py --check`) that fails on any stale mirror, and a `dekspec doctor` self-dogfood step gated on the presence of a `dekspec/` self-spec tree at repo root (no-ops today; substantive once the library bootstraps F-6 Path 1).
5. **IR-pipeline tightening** (ds-06n bundle 2 of 3, 2026-05-11 audit) — D-12, D-18, D-39, D-41, plus documentation passes for D-10 / D-11 / D-13. v1 fidelity-audit skill deleted; `parse_glossary` + `parse_vision` now populate `parse_warnings`; `contract_test` emitter explicitly tagged as a stub generator with a published roadmap; root-level schema `description:` blocks normalized 6/9 → 9/9; per-IR rationale for the divergent `amendment_log.type` enum vocabularies captured in a new `docs/amendment-log-types.md`. IB + Intent templates now carry an explicit "author scratch pad" comment listing which sections flow into the IR vs which are prompt-time scaffolding. False "load-bearing" claims demoted in WS + IC + ADR schema comments (each schema now states which fields are actively consumed by emitters today vs informational). The two remaining substantial items (`/write-evals` rebuild on /write-ibs skeleton, deep per-field plumbing-or-drop pass on parse-and-drop fields) split out as fresh beads (ds-jlk, ds-f2j) — both are additive work that doesn't gate this release.

### Breaking note for consumers

- **`# Vision Note: X` H1 in `system-vision.md` is now rejected** by `parse_vision` (the singleton parser). The supported H1 forms are `# System Vision: <Name>` or a plain `# <Name>`. Pre-v0.38 the regex accepted both — which meant subsystem Vision Notes could silently collide with the SYSTEM-VISION singleton id. Consumers using the `Vision Note:` prefix must rename their H1 line; the artifact body is otherwise unchanged.
- **`templates/vision-note-template.md` removed**, replaced by **`templates/system-vision-template.md`** (with the schema-required `§Why This Exists` H2 added). On next `bash scripts/install-dekspec.sh`, rsync `--delete` removes the obsolete template and lands the renamed one. Consumer-authored `system-vision.md` artifacts are untouched.

### Sync procedure for v0.37.x → v0.38.0

1. `pip install -U dekspec` (or `pip install git+https://github.com/Dektora/dekspec.git@v0.38.0`).
2. `bash scripts/install-dekspec.sh` — refreshes vendored content; `.dekspec-version` updates.
3. `dekspec doctor` — composite health check.
4. `dekspec audit linkage --fix --apply` — auto-applies L6/L7/L8 mechanical fixes for any backlink drift.
5. `dekspec aggregate agents-md` — regenerate AGENTS.md.
6. Commit as `chore(dekspec): bump to v0.38.0`.

### Added — flywheel category-1 (F-1 + F-3.phase1)

- **`tooling/dekspec/lifecycle.py`** (new module, ~480 LOC) — the execution-attempt lifecycle public API for DekFactory (or any other executor) to write to. Surface: `record_execution_attempt`, `record_execution_event`, `complete_execution_attempt`, `tag_attempt`, `amend_attempt`, `link_attempt`, `query_executions`, `query_events`, `query_merge_outcomes`, `metrics`. Plus dataclasses `ExecutionAttempt`, `ExecutionEvent`, `MergeOutcome` and the `LifecycleError` exception. All functions accept an `at=<path>` kwarg for repo anchoring; default is cwd.
- **SQLite schema v2** in `tooling/dekspec/constraint_compiler/persistence_index.py` — three additive tables (`execution_attempts`, `execution_events`, `merge_outcomes`) with foreign keys, indexes, and an event-type canonical enum + free-form `custom_event_type` escape hatch. `init_schema` migrates v1 DBs in place (CREATE TABLE IF NOT EXISTS guards). `INDEX_SCHEMA_VERSION` bumps from `1` to `2`.
- **`dekspec executions` CLI subcommand** with six verbs: `ls` (filtered query), `show` (one attempt + optional events), `metrics` (aggregate flywheel health), `tag` (key=value annotation), `amend` (append note), `link` (PR URL shortcut). All read-side commands support `--json`. Wired into `cli.py:main` and parametrized in `tests/test_cli_help.py`.
- **`audit_profile` field** added to `intent.schema.yaml`, `implementation-brief.schema.yaml`, `mission.schema.yaml`, `working-spec.schema.yaml`. Optional, defaults to `"v1"`, pattern `^v[0-9]+$`. Today's audit engine ignores it; reserved for the F-3 phase 2 profile registry (named-bundle YAMLs with inheritance, decided 2026-05-12). Backward compatible — existing artifacts continue to validate.
- **`dekspec.api` re-exports** for the entire lifecycle surface plus the four dataclasses + `CI_STATUSES` constant. `metrics` re-exported as `execution_metrics` to avoid colliding with a future generic name.

### Tests — flywheel category-1

- **`tests/test_lifecycle.py`** (new, 28 tests) — covers schema migration v1→v2 in place, recording attempt + event idempotency, validation of inputs (ci_status / merge_commit_sha / canonical event types / non-empty amend), merge-outcome recompute on first-pass merge AND multi-attempt merge (incl. time-to-merge math), tag/amend/link annotations, query filters compose, events chronological order, metrics aggregation (empty corpus, first-pass-rate math, by-agent-model split), six CLI verbs (ls/show/metrics/tag/link/error paths), public API re-export.
- **`tests/test_persistence_index.py::test_open_index_creates_db_with_schema`** updated to reference `INDEX_SCHEMA_VERSION` constant + assert the three new tables exist alongside the v1 trio.
- **`tests/test_cli_help.py`** parametrized lists extended — `executions` added to TOP_LEVEL_COMMANDS, all six nested verbs added to NESTED_COMMANDS.

### Roadmap context

This PR builds the substrate; it does not turn the flywheel. Nothing produces execution-attempt rows yet — DekFactory's executor is the intended producer (currently v0.1.0, init-only). Once DekFactory Phase 2 (single-tenant intake → plan → execute → MR loop) lands, every run flows through `record_execution_attempt` and the lifecycle DB starts filling. The category-1 work makes that work consistent from the first run.

Out of scope for this PR (deferred per category-2 design decisions of 2026-05-12):
- F-3 phase 2 profile registry (named-bundle YAMLs in `fidelity_audit/profiles/`) — lands when v2 audit rules are actually authored, likely quarters out.
- F-4 pattern promotion (`templates/intent-patterns/` + `dekspec promote` CLI) — lands once ≥30 days of execution data exists to make promotion eligibility non-speculative.
- F-2 hot fields in Intent IR (Option C of decision 1) — speculative add deferred until usage tells us which fields are actually hot-read.

### Earlier in this Unreleased batch (from prior PRs)

### Added — singleton IR remediation (D-3, D-4)

- **`templates/glossary-template.md`** (new) — first first-class authoring template for the `DOMAIN-GLOSSARY` singleton. Previously the glossary's structure was embedded only inside `skills/write-ggc/SKILL.md` and authors had no reference template to copy from. Template ships with two example categories + the four-column term table and an Amendment Log scaffold.
- **`skills/write-sv/SKILL.md`** (new) — authoring + lifecycle skill for the `SYSTEM-VISION` singleton, modeled on the `/write-mission` skeleton. Modes: creation (default), `--review`, `--audit`, `--accept`, `--lock`, `--unlock`, `--deprecate`, `--help`. Enforces the singleton invariant (refuses creation if a non-DEPRECATED Vision already exists). Refuses creation without a `Why This Exists` rationale.

### Changed — singleton IR remediation (D-44, D-40)

- **`templates/vision-note-template.md` → `templates/system-vision-template.md`** (rename). The prior name lagged the IR rename to `SYSTEM-VISION`. Template rewritten to add `§Why This Exists` (required by `system-vision.schema.yaml`'s `why_this_exists` field; previously missing from the template even though the schema declared the field). H1 form is now `# System Vision: <Name>` to match the parser's preferred form.
- **`tooling/dekspec/constraint_compiler/parser.py`** — `_extract_vision_name` now explicitly rejects `# Vision Note:` H1 form with a clear `VisionParseError`. Prior to this change the regex matched both `System Vision: X` and `Vision Note: X` ambiguously, which meant subsystem-level Vision Notes could silently collide with the `SYSTEM-VISION` singleton id. Plain `# <Name>` H1 (no prefix) remains supported.
- **`docs/dekspec-operating-guide.md`** — reference updated from `dekspec/templates/vision-note-template.md` to `dekspec/templates/system-vision-template.md`; clarified that subsystem descriptions belong in Architecture Elements, not in additional Vision documents.
- **`README.md`** — `/write-sv` added to the skills inventory line.

### Changed — `tests/conftest.py` (conftest scope-creep fix)

Per-test (rather than per-file) detection of dektora2-fixture dependence. The previous heuristic skipped every test in any file containing the literal `/data/projects/dektora2` string, which over-skipped tmp_path-based synthetic tests that happened to share a file with dektora2-bound tests. The new heuristic inspects each test function's source body for (a) the literal path string, (b) a `DEKTORA2_*` name, or (c) any module-level constant whose value contains the dektora2 path. Test count under the CI auto-skip moves from 186 pass / 162 skip to 242 pass / 109 skip — 53 previously-hidden synthetic tests now actually execute. No tests were modified.

### Added (tests)

- `tests/test_parser_vision.py::test_parse_vision_rejects_vision_note_h1` — proves the `# Vision Note:` H1 form now raises `VisionParseError` with a clear message.
- `tests/test_parser_vision.py::test_parse_vision_template_parses_when_filled` — proves the renamed `system-vision-template.md` (after placeholder replacement) parses + schema-validates cleanly with all six required sections populating in the IR.
- `tests/test_parser_glossary.py::test_parse_glossary_template_parses_when_filled` — proves the new `glossary-template.md` parses + schema-validates cleanly with two categories.

### Stop-the-bleeding subset (D-1, D-2, D-26, D-27) — unchanged from prior NOW PR

Closes the four highest-leverage / lowest-effort fixes from the doc-drift-cleanup bead (`ds-whn`).

### Changed (`scripts/install-dekspec.sh`)

- Default `DEKSPEC_VERSION` now resolves to the latest `vX.Y.Z` tag on the remote via `git ls-remote --sort=-v:refname` (D-1). Hardcoded fallback is the current `__version__` (`0.37.2`) and is only used if the remote query fails. Previously the default was pinned to `0.7.0` — 30+ patch/minor releases stale — so the curl-bash recipe in `README.md` silently downgraded consumers below the schemas, persistence, and audit-engine layers shipped between v0.7.0 and v0.37.x.

### Changed (`README.md`)

- Current-version stamp at the top of the file: `v0.34.0` → `v0.37.2` (D-2).
- Quick-start + Installation install-URL pins: `@v0.29.0` → `@v0.37.2` (D-2). Previously the `pip install git+…@v0.29.0` recipe pinned consumers 8 versions behind `__version__`.
- Status-line version stamp: `v0.34.0` → `v0.37.2` (D-2).

### Changed (`.github/workflows/publish.yml`)

- **New `test` job** runs `ruff check tooling tests` + `pytest -q` and `build` now `needs: test` (D-26). Previously the publish workflow only verified that the wheel built and `dekspec --version` ran — a regression that passed import-time but failed its own test suite or lint could still publish.
- **Version-triad assertion** before artifact upload, gated on `github.event_name == 'push'`: parses the git tag (`${GITHUB_REF_NAME#v}`), reads `dekspec.__version__`, extracts the first `## [vX.Y.Z]` heading from `CHANGELOG.md`, fails the job unless all three agree (D-27). Catches the case where a tag is pushed against unbumped `__version__` or an unwritten changelog entry.

### Added — vendored docs expansion (closes D-23, D-24)

- **`docs/cli-reference.md`** (new) — full CLI reference page now vendored to consumers as `dekspec/cli-reference.md`. Previously the vendored quick-reference covered skills only; CLI usage lived in the README + `--help` output. (D-23.)
- **`docs/EXAMPLES.md`** is now vendored to consumers as `dekspec/EXAMPLES.md`. Previously consumers were directed to `dekspec.api` without the cookbook on disk. (D-24.)
- `scripts/install-dekspec.sh` and `tooling/dekspec/vendoring.py` manifest both updated to include the two new docs. `dekspec verify-vendored` will report drift correctly for them.

### ds-whn closeout (D-20, D-21, D-22, D-25 partial, D-28 partial)

- **`README.md` CLI table** — added `dekspec migrate` row (D-20) and renamed the `runs` row to `runs ls/show/reindex/gc` with a one-line description of `gc` (D-21). Header heading promoted from "nine subcommands" to "eleven subcommands" to match the live argparse surface (D-22). The status line at the bottom of the README similarly went from "10 CLI subcommands" to "11 CLI subcommands". A cross-link to `docs/cli-reference.md` now appears immediately under the table.
- **`docs/EXAMPLES.md` API-symbol coverage** — six new sections expanding the cookbook from the originally-covered ~30 symbols to ~50: `Apply migrations programmatically`, `Inspect schemas at runtime`, `Emit a CI gate from an IC IR`, `Generate a contract-test stub from an IC IR`, `Open a compile run and persist IRs directly`, `Walk the vendoring manifest`. Each section demonstrates the public types + their canonical use site. (D-25.)
- **`scripts/bump-version.py`** (new) — single-shot updater + `--check` drift detector. Reads canonical `__version__` from `tooling/dekspec/__init__.py` and substitutes it across `scripts/install-dekspec.sh` fallback, README install-URL + status stamps, EXAMPLES.md GHA pin, and the methodology stamp. Wired into `ci.yml` (next entry); fails the build on any mirror drift. (D-1/D-2 follow-through.)
- **`.github/workflows/ci.yml` — two new steps:** (a) `python scripts/bump-version.py --check` — fails the build if any mirror drifts from `__version__`; (b) `dekspec doctor` self-dogfood gated on the presence of a `dekspec/` self-spec tree at repo root. Skip-if-absent: the dekspec library itself doesn't currently self-spec, so the step no-ops today and becomes substantive once F-6 (the library bootstraps its own dekspec/ tree) lands. (D-28 partial.)
- **`tests/test_vendoring.py`** asserts the two new docs (`cli-reference.md`, `EXAMPLES.md`) appear in the `iter_vendored_pairs` manifest. 277 passing, 109 skipped, ruff clean.

## [v0.37.2] — 2026-05-11

Patch release. PEP 561 `py.typed` marker — type-checkers (mypy / pyright / pyre) now treat dekspec as a typed package instead of falling back to `Any` for every imported symbol.

### Added (`tooling/dekspec/py.typed`)

Empty marker file per PEP 561. Required for any type-checker to honor the `Typing :: Typed` classifier already declared in `pyproject.toml`. Without it, the classifier is aspirational only — type-checkers silently downgrade every import from `dekspec.api` to `Any`.

### Changed (`pyproject.toml`)

```toml
[tool.setuptools.package-data]
"dekspec" = ["py.typed"]            # new
"dekspec.schemas" = ["*.yaml"]
```

Verified: rebuilt wheel includes `dekspec/py.typed` at the expected location alongside the 9 schema YAMLs.

### Added (test)

`tests/test_public_api.py::test_pep_561_py_typed_marker_present` — confirms the marker ships in the installed package via `importlib.resources`. Catches accidental removal in future packaging changes.

186 passing, 162 skipped, ruff clean.

[v0.38.0]: https://github.com/Dektora/dekspec/releases/tag/v0.38.0
[v0.37.2]: https://github.com/Dektora/dekspec/releases/tag/v0.37.2

## [v0.37.1] — 2026-05-11

Patch release. Test-only additions — comprehensive `--help` smoke tests across all 11 CLI subcommands + 7 nested commands.

### Added (`tests/test_cli_help.py`)

23 parametrized tests covering every CLI surface:

- `test_top_level_help_returns_zero` — `dekspec --help` mentions every top-level subcommand.
- `test_version_flag_returns_zero` — `dekspec --version` prints `__version__`.
- `test_subcommand_help_returns_zero[X]` — 10 parametrized tests covering `compile`, `audit`, `aggregate`, `verify-vendored`, `graph`, `init`, `validate`, `doctor`, `migrate`, `runs`.
- `test_nested_subcommand_help_returns_zero[X-Y]` — 7 parametrized tests covering `audit linkage`, `aggregate agents-md`, `graph export`, `runs ls/show/reindex/gc`.
- `test_no_args_prints_help_returns_zero` — calling `dekspec` with no args prints help.
- `test_unknown_subcommand_returns_nonzero` — `dekspec foo` errors out.
- `test_help_for_all_top_level_includes_description` — every subcommand has a `description` block, not just a `usage:` line.
- `test_cli_as_module_returns_help` — `python -m dekspec.cli --help` works via subprocess (smoke-tests the entry-point path).

### Why this matters

A broken argparse setup is silent under the existing test suite — each command's main-path tests skip argparse validation when given the right args. A regression that breaks `--help` (e.g., a required positional with no metavar, an invalid `action=` for an `--xyz` flag, a syntax error in an `add_argument` call) wouldn't show up until a user runs the tool. The help-text smoke tests catch this in CI.

`TOP_LEVEL_COMMANDS` and `NESTED_COMMANDS` lists at the top of the file are the canonical CLI inventory — every time a new subcommand lands, add an entry there and the parametrized tests run automatically.

185 passing, 162 skipped, ruff clean.

[v0.37.1]: https://github.com/Dektora/dekspec/releases/tag/v0.37.1

## [v0.37.0] — 2026-05-11

Minor bump (refactor; no behavior change). 9 private `_load_*_schema()` functions in `parser.py` now delegate to the public `dekspec.schemas.load_schema()` introduced in v0.36.0.

### Changed (parser internals)

Each of the 9 private schema-loaders was 6 lines of duplicated `importlib.resources.files(...)` + `yaml.safe_load(...)`. Each is now a 3-line wrapper around `load_schema()`:

```python
# Before
@lru_cache(maxsize=4)
def _load_X_schema() -> dict[str, Any]:
    schema_dir = files("dekspec.schemas")
    schema_path = schema_dir / "X.schema.yaml"
    with schema_path.open("rb") as f:
        return yaml.safe_load(f)

# After
def _load_X_schema() -> dict[str, Any]:
    from ..schemas import load_schema as _load
    return _load("X")
```

The `@lru_cache(maxsize=4)` decorator on each private loader is now redundant — `load_schema()` itself has `@lru_cache(maxsize=64)`. Net: ~45 fewer lines of code in `parser.py`, no behavior change, single code path for all schema reads.

Two unused imports (`functools.lru_cache`, `importlib.resources.files`) dropped from `parser.py` as a side effect.

### Why this matters for future schema evolution

When the first real schema bump lands (e.g., `ds-zuy`), only `dekspec.schemas` knows where each schema-version-pair lives on disk. The parsers don't need to think about it. Future archive/v0.1.0/ moves stay invisible to `parser.py`.

### Verified

All 162 tests still pass with no changes to assertions — the refactor is a no-op at the behavior level.

[v0.37.0]: https://github.com/Dektora/dekspec/releases/tag/v0.37.0

## [v0.36.0] — 2026-05-11

Minor bump (additive). Public schema-loader module `dekspec.schemas` — the read-side counterpart to v0.35.0's migration framework.

### Added (`dekspec.schemas` public API)

The schemas package was previously just a docstring; the loader logic was duplicated across 9 private `_load_*_schema()` functions inside the parser. Now centralized through a public loader:

```python
from dekspec.api import load_schema, list_schemas, LATEST_VERSIONS

# Load the latest schema for an artifact type
mission_schema = load_schema("mission")

# Pin to a specific version (today only 0.1.0 exists)
mission_v_0_1_0 = load_schema("mission", version="0.1.0")

# List every (artifact_type, version) the library ships
for artifact_type, version in list_schemas():
    print(artifact_type, version)
```

**Exports:**
- `SCHEMA_FILENAMES: dict[str, str]` — canonical map from artifact_type (underscore form) to schema filename. 9 entries.
- `LATEST_VERSIONS: dict[str, str]` — latest published version per artifact type. Today every value is `"0.1.0"`.
- `load_schema(artifact_type, version=None) -> dict` — load + parse the YAML schema. Cached via `lru_cache`. Raises `KeyError` for unknown artifact types; `SchemaNotFoundError` for unknown versions.
- `list_schemas() -> list[tuple[str, str]]` — every shipped (artifact_type, version) pair, sorted.
- `SchemaNotFoundError` — single exception for missing-version failures.

### Future archive layout

When the first schema retires (e.g., when `ds-zuy` calibration ships `mission` v0.2.0), the v0.1.0 schema moves to `schemas/archive/v0.1.0/mission.schema.yaml`. The loader transparently picks the archived schema when `version="0.1.0"` is requested explicitly.

Today the `archive/` directory doesn't exist; `list_schemas()` returns only the 9 latest entries. The future layout is documented in the module docstring so the first schema retirement is a one-file move + one-line `LATEST_VERSIONS` bump.

### Pairs with v0.35.0

The migration framework upgrades persisted IRs forward through registered Migration functions. The schema loader lets consumers validate old IRs against their declared `ir_schema_version` *without* migrating first — useful for audit-time inspection of historical IRs, library debugging, and backwards-compatibility testing.

Combined, the two systems mean schema evolution is fully self-contained: add the new schema file, register the migration, bump `LATEST_VERSIONS`, ship.

### Added (12 new tests; 162 passing, 162 skipped)

`tests/test_schemas.py`:
- `test_schema_filenames_cover_all_nine_artifact_types`
- `test_latest_versions_match_schema_filenames` — every artifact_type has a LATEST_VERSIONS entry.
- `test_latest_versions_today_are_all_0_1_0` — codifies today's state; updated alongside the first schema bump.
- `test_load_schema_returns_dict_for_each_type`
- `test_load_schema_ir_schema_version_const_matches_latest` — schema file's `const` matches the LATEST_VERSIONS entry.
- `test_load_schema_explicit_version_today_works_for_latest`
- `test_load_schema_unknown_artifact_type_raises`
- `test_load_schema_unknown_version_raises`
- `test_list_schemas_includes_every_latest`
- `test_list_schemas_returns_sorted`
- `test_load_schema_is_cached`
- `test_api_module_exports_schemas`

[v0.36.0]: https://github.com/Dektora/dekspec/releases/tag/v0.36.0

## [v0.35.0] — 2026-05-11

Minor bump (additive). IR schema-migration infrastructure — the pre-positioning that unblocks `ds-zuy` (Mission rigor calibration) and any future schema change.

### Why this ships now

Every IR is currently at `ir_schema_version: "0.1.0"`. When the first real schema change lands (e.g., the ds-zuy calibration collapsing Mission's `out_of_scope` + `kill_criteria` into a `negative_scope` list), the dekspec library needs:

1. A way to define the new schema alongside the old.
2. A migration function from old IR shape to new IR shape.
3. A registry that composes migrations into multi-step chains.
4. A CLI to apply migrations to persisted IR JSON files.

Without this, every schema evolution becomes a coordinated cross-file rewrite (schema YAML + parser + tests + migration script + persisted-data backfill). With this, schema evolution becomes a small incremental PR.

### Added (`dekspec.migrations` module)

- **`Migration` dataclass** — captures one step: `(artifact_type, from_version, to_version, migrate_fn, description)`.
- **`Registry` class** — composes Migrations into chains. Methods:
  - `register(migration)` — add a step. Raises on conflict (chain must be linear per artifact type).
  - `chain(artifact_type, from_version, to_version)` — return the ordered step list. Refuses downgrades.
  - `apply(ir, to_version=None)` — apply the chain to an IR; defaults to the latest registered version. Validates each step's output `ir_schema_version`.
  - `target_version_for(artifact_type, default)` — query the latest registered target.
  - `validate_chains()` — registry-wide sanity check; surfaces broken/non-linear chains.
- **`default_registry`** — module-level singleton. Sub-modules under `dekspec.migrations` register against this at import time. Today empty (no real migrations yet).
- **`migrate_ir(ir, to_version=None, registry=None)`** — convenience wrapper around `Registry.apply`.
- **`MigrationError`** — single exception class for all migration-time failures (missing step, downgrade attempt, malformed IR, output-version mismatch, unknown artifact-id prefix).
- Artifact-id → artifact-type inference: ADR-/AE-/WS-/IC-/IB-/INT-/MSN-/`DOMAIN-GLOSSARY`/`SYSTEM-VISION` all map to canonical underscore names. Unknown prefixes raise.

All exposed via `dekspec.api` so consumers do `from dekspec.api import migrate_ir, Migration, Registry`.

### Added (`dekspec migrate` CLI)

```
dekspec migrate <path> [<path> ...] [--to VERSION] [--apply] [--json]
```

Reads one or more IR JSON files (typically from `<repo-state-dir>/runs/.../irs/<id>.ir.json`), runs them through `default_registry`, and writes the upgraded IR back. Dry-run by default — `--apply` writes.

Output (text mode) groups per-file results by status:

```
Migration (DRY-RUN): 4 file(s)  [2 would-migrate, 1 unchanged, 1 errored]
  → [would-migrate ] runs/.../irs/MSN-001.ir.json  (0.1.0 → 0.2.0)
  → [would-migrate ] runs/.../irs/MSN-002.ir.json  (0.1.0 → 0.2.0)
  ✗ [errored       ] runs/.../irs/bad.ir.json  error: ...
```

`--json` mode emits a structured envelope (`{applied, files, results: [...]}`) for CI integration.

The CLI validates the registry's chains via `validate_chains()` before processing any file. If chains are broken (e.g., a v0.2.0 was registered without a corresponding v0.1.0 → v0.2.0 bridge), the command refuses with exit code 2 and surfaces the gap.

### Authoring a future migration (for reference)

The module docstring contains a worked example. The procedure is:

1. Define the new schema (e.g., `tooling/dekspec/schemas/mission.schema.yaml` with `const: "0.2.0"`).
2. Move the old schema to `tooling/dekspec/schemas/archive/` (optional — kept for reference).
3. Author the migration function in a new sub-module (e.g., `tooling/dekspec/migrations/mission.py`).
4. Register against `default_registry`.
5. Bump the parser's emitted `ir_schema_version`.
6. Add a unit test in `tests/test_migrations.py` exercising the new step end-to-end.

### Added (27 new tests; 150 total passing, 162 skipped)

`tests/test_migrations.py`:

**Registry mechanics (8):**
- `test_registry_records_latest_target`
- `test_registry_chain_zero_steps_when_versions_match`
- `test_registry_chain_single_step`
- `test_registry_chain_multi_step`
- `test_registry_chain_missing_step_raises`
- `test_registry_chain_downgrade_refused`
- `test_registry_register_conflict_raises`
- `test_registry_validate_chains_detects_gap`
- `test_registry_validate_chains_clean_for_linear_chain`

**Apply / migrate_ir (5):**
- `test_apply_single_step`
- `test_apply_multi_step_chain`
- `test_apply_defaults_to_latest_registered`
- `test_apply_no_migrations_returns_same_version`
- `test_apply_missing_version_raises`
- `test_apply_migration_returns_wrong_version_raises`

**Artifact-id mapping (2):**
- `test_artifact_type_inferred_from_id`
- `test_artifact_type_unknown_prefix_raises`

**Default-registry state (3):**
- `test_default_registry_is_empty_today` — codifies "no real migrations yet"
- `test_default_registry_migrate_ir_is_noop_today`
- `test_target_version_for_default_registry_helper`

**CLI (5):**
- `test_cli_migrate_dry_run_on_current_version_ir`
- `test_cli_migrate_json_output`
- `test_cli_migrate_missing_file_returns_one`
- `test_cli_migrate_malformed_json_returns_one`
- `test_cli_migrate_unknown_artifact_prefix_returns_one`
- `test_cli_migrate_apply_writes_back` — toy migration registered + applied + restored

**Public API (1):**
- `test_api_module_exports_migrations`

Each test uses synthetic Mission v0.1.0 → v0.2.0 → v0.3.0 toy migrations to exercise the framework without touching the today-empty default registry.

### What unblocks

`ds-zuy` Mission rigor calibration can now ship as a small incremental PR:
1. Update `mission.schema.yaml` to `const: "0.2.0"` with the new field set.
2. Add `tooling/dekspec/migrations/mission.py` with the v0.1.0 → v0.2.0 step.
3. Bump `PARSER_VERSION` if the parser emits `ir_schema_version: "0.2.0"`.
4. One unit test demonstrating the migration on a real Mission IR.

[v0.35.0]: https://github.com/Dektora/dekspec/releases/tag/v0.35.0

## [v0.34.0] — 2026-05-11

Minor bump (additive). `--json` output for `runs ls` + `runs show`. Completes the JSON-output-everywhere pattern across CLI commands.

### Added (`dekspec runs ls --json`)

Emits a structured envelope:

```json
{
  "repo_root": "/path/to/repo",
  "runs_dir": "/home/.../<fingerprint>/runs",
  "row_count": 20,
  "rows": [
    {
      "run_id": "...",
      "timestamp": "2026-05-11T12:00:00Z",
      "trigger": "manual-compile",
      "command": "dekspec compile foo.md",
      "dekspec_version": "0.34.0",
      "artifact_count": 1,
      "emission_count": 0,
      "warnings": 0,
      "errors": 0,
      "exit_code": 0,
      "duration_ms": 42,
      "milestone": 0,
      "run_dir_name": "2026-05-11T12-00-00Z-..."
    },
    ...
  ]
}
```

Honors all existing `--since` / `--until` / `--artifact` / `--exit-code` / `--milestone` / `--min-warnings` filters.

### Added (`dekspec runs show --json`)

Emits a single-run envelope:

```json
{
  "run_dir": "/path/to/run-dir",
  "manifest": { ... full manifest.json contents ... },
  "ir_files": ["AE-014.ir.json", "WS-016.ir.json"],
  "event_count": 12
}
```

The `manifest` field is the manifest verbatim; `ir_files` lists the IR captures under `irs/`; `event_count` is the line count of `events.jsonl`.

### Added (5 new tests; 123 passing, 162 skipped)

`tests/test_runs_json.py`:
- `test_runs_ls_json_envelope` — confirms envelope shape with 3 seeded runs.
- `test_runs_ls_json_with_artifact_filter` — `--artifact AE-001 --json` narrows to 1 row.
- `test_runs_show_json_includes_manifest_ir_files_event_count` — confirms all three fields.
- `test_runs_show_json_no_runs_returns_one` — missing run → exit 1.
- `test_runs_ls_json_empty_when_no_runs` — graceful empty-state handling.

### CLI JSON-output coverage now complete

After v0.34.0, every CLI subcommand that produces structured output supports `--json`:

| Command | --json shape |
|---------|--------------|
| `audit linkage` | envelope: `{summary, repo_root, dekspec_root, findings}` (v0.32.0) |
| `aggregate agents-md` | (text-only by design — Markdown output) |
| `compile` | `--emit ir` for JSON IR; other emitters are domain-specific |
| `doctor` | envelope: `{overall_status, exit_code, repo_root, dekspec_root, sections}` (v0.29.0) |
| `graph export` | envelope: `{schema_version, library_version, repo_root, dekspec_root, exported_at, ir_count, parse_failures, irs}` (v0.24.0) |
| `init` | (text-only — primarily side-effecting) |
| `runs gc` | (text-only — primarily side-effecting) |
| `runs ls` | envelope: `{repo_root, runs_dir, row_count, rows}` (v0.34.0) |
| `runs reindex` | (text-only — primarily side-effecting) |
| `runs show` | envelope: `{run_dir, manifest, ir_files, event_count}` (v0.34.0) |
| `validate` | envelope: `{ok, id, status, kind, warnings}` or `{ok: false, error, error_type}` (v0.26.0) |
| `verify-vendored` | array of `DriftFinding` dicts (v0.8.0) |

[v0.34.0]: https://github.com/Dektora/dekspec/releases/tag/v0.34.0

## [v0.33.0] — 2026-05-11

Minor bump (additive). New `dekspec.api` module — the official public Python API.

### Added (`dekspec.api`)

A single, stable import path for everything a consumer needs from the Python side. Before:

```python
from dekspec.constraint_compiler.graph import SpecGraph
from dekspec.fidelity_audit.linkage import audit_linkage, propose_fixes, apply_fixes
from dekspec.constraint_compiler.parser import parse_ae, parse_intent, ICParseError
from dekspec.vendoring import compute_drift
# ... etc
```

After:

```python
from dekspec.api import (
    SpecGraph,
    audit_linkage, propose_fixes, apply_fixes,
    parse_ae, parse_intent, ICParseError,
    compute_drift,
)
```

`dekspec.api.__all__` is the public contract:

| Category | Exports |
|----------|---------|
| Versions | `__version__`, `IR_SCHEMA_VERSION`, `PARSER_VERSION` |
| Parsers (9 + resolve_aes) | `parse` (alias for parse_ic), `parse_adr`, `parse_ae`, `parse_glossary`, `parse_ib`, `parse_intent`, `parse_mission`, `parse_vision`, `parse_ws`, `resolve_aes` |
| Parse errors (9) | `ADRParseError`, `AEParseError`, `GlossaryParseError`, `IBParseError`, `ICParseError`, `IntentParseError`, `MissionParseError`, `VisionParseError`, `WSParseError` |
| Graph | `SpecGraph`, `ParseFailure` |
| Emitters | `agents_md`, `ci_gate`, `contract_test` |
| Audit | `Finding`, `Fix`, `apply_fixes`, `audit_linkage`, `propose_fixes` |
| Persistence | `Run`, `RunWriter`, `open_run`, `repo_fingerprint`, `repo_runs_dir`, `repo_state_dir`, `xdg_data_root`, `INDEX_FILENAME`, `INDEX_SCHEMA_VERSION`, `open_index`, `query_runs`, `record_run`, `reindex` |
| Vendoring | `DriftFinding`, `compute_drift`, `iter_vendored_pairs`, `library_root` |

The old import paths (`dekspec.constraint_compiler.graph`, `dekspec.fidelity_audit.linkage`, etc.) continue to work unchanged — `dekspec.api` is purely additive. Existing consumer code keeps working.

### Stability commitment

Every name in `dekspec.api.__all__` is a public contract. Removing or renaming one is a breaking change that bumps the major version + adds a deprecation note in CHANGELOG. Adding new exports is an additive minor bump.

### Added (11 new tests; 118 total passing, 162 skipped)

`tests/test_public_api.py`:
- `test_api_exports_versions`
- `test_api_exports_all_parsers` (verifies all 9 + resolve_aes)
- `test_api_exports_all_parse_errors` (verifies all 9 are Exception subclasses)
- `test_api_exports_spec_graph`
- `test_api_exports_emitters`
- `test_api_exports_audit`
- `test_api_exports_persistence`
- `test_api_exports_vendoring`
- `test_api_specgraph_round_trip_against_fresh_repo` — end-to-end through the api module
- `test_api_audit_linkage_round_trip`
- `test_api_module_dunder_all_is_complete` — every name in `__all__` is actually present

### README + docs

The README's "Quick start" + "Working with an existing dekspec tree" sections continue to favor the CLI for first-time users; the new `dekspec.api` module is the Python-API equivalent for library integrators. A follow-up `docs/EXAMPLES.md` may document common API patterns in more depth.

[v0.33.0]: https://github.com/Dektora/dekspec/releases/tag/v0.33.0

## [v0.32.1] — 2026-05-11

Patch release. e2e fixture expanded to include IC — closes the v0.31.0 known limitation that the e2e test suite couldn't cover IC because of parser rigor.

### Added (`tests/test_e2e_pipeline.py::_IC_FIXTURE`)

Authored a minimal-but-coherent IC fixture satisfying every required field the IC parser validates:
- Status, Created, Modified, Version (semver), Silent Failure Domain(s), Governing ADRs, Purpose
- Parties with Provider AE / Consumer AEs H3 subsections (L4-IC-AE source-of-truth)
- Relationship Pattern (Open Host Service)
- Shared Conventions
- Interface Definition (single GET endpoint)
- Error Semantics table
- Consistency Guarantees

Now `_write_minimal_corpus` lays down all 5 main artifact types (AE + ADR + WS + IC + Intent) plus the stub source file. The AE's `Linked Artifacts.Related ICs` line includes IC-001 to keep L6 backlinks clean.

### Effect on e2e coverage

- `test_e2e_validate_every_artifact` now validates 5 artifact types (was 4).
- `test_e2e_graph_export_round_trip` confirms IC-001 in the exported graph.
- `test_e2e_audit_linkage_clean`, `test_e2e_doctor_clean_on_populated_repo`, and `test_e2e_full_pipeline_in_sequence` all exercise the full 5-type corpus with zero findings.

Total passing: 107 (unchanged count, but each e2e test now covers more ground).

[v0.32.1]: https://github.com/Dektora/dekspec/releases/tag/v0.32.1

## [v0.32.0] — 2026-05-11

Minor bump (mostly additive; one small breaking change to `--json` output shape — pre-1.0 SDK behavior).

### Changed (breaking) — `dekspec audit linkage --json` output shape

The `--json` output is now an **envelope** with a `summary` block + a `findings` array, instead of a bare findings array:

```json
{
  "summary": {
    "total": 1,
    "critical": 0,
    "important": 1,
    "minor": 0,
    "by_rule": {"T11-AE-BOUNDARY": 1}
  },
  "repo_root": "/path/to/repo",
  "dekspec_root": "dekspec",
  "findings": [
    {"severity": "important", "rule": "T11-AE-BOUNDARY", "artifact_id": "AE-001", ...}
  ]
}
```

The `summary.by_rule` map groups findings by rule code, making it trivial to write a single-line CI status check like `jq -r '.summary.critical' < audit.json`. The previous bare-array form forced consumers to write their own aggregation.

**Migration:** existing scripts that did `findings = json.loads(out)` must change to `doc = json.loads(out); findings = doc["findings"]`. The library is pre-1.0; we ship this as a minor bump per the published versioning policy (additive changes can include CLI-output shape).

### Added (`dekspec runs gc`)

```
dekspec runs gc [--at REPO] [--keep N] [--dry-run]
```

Explicit garbage-collect for the per-repo run history at `$XDG_DATA_HOME/dekspec/<fingerprint>/runs/`. Removes runs older than the `--keep`th most recent (default 200) **except** milestone runs, which are always preserved. Drops the corresponding rows from the SQLite index (CASCADE cleans up `artifacts` + `emissions` child rows automatically).

- `--dry-run`: list what would be deleted without removing anything. Shows the first 10 candidate dirs + a count of the rest.
- Without `--dry-run`: deletes + prints a one-line summary `Garbage-collected N run(s); preserved M milestone(s) and K most-recent run(s).`

This duplicates the auto-prune that `open_run` already does on every `compile` exit, but exposes it as an explicit command so users can gc the history without running a compile. Useful when:
- A user disabled auto-prune via a CI knob and wants to clean up manually.
- An ops sweep clears old runs across many repos.
- The user wants to inspect what would be removed before pulling the trigger.

### Added (4 + 2 new tests; 107 passing in dev mode, 162 skipped)

`tests/test_runs_gc_and_json_envelope.py`:
- `test_audit_json_envelope_has_summary_and_findings` — confirms the new envelope shape.
- `test_audit_json_envelope_empty_clean_corpus` — clean corpus → `total: 0`, empty `findings`.
- `test_runs_gc_no_runs_dir_returns_zero` — graceful handling of repos with no run history.
- `test_runs_gc_dry_run_does_not_delete` — `--dry-run` leaves dirs intact.
- `test_runs_gc_deletes_old_non_milestone_runs` — gc removes the right runs.
- `test_runs_gc_preserves_milestone_runs` — milestone preservation works (the canonical correctness test).

[v0.32.0]: https://github.com/Dektora/dekspec/releases/tag/v0.32.0

## [v0.31.0] — 2026-05-11

Minor bump (additive). End-to-end CLI pipeline test suite — exercises every CLI command in sequence against a synthesized minimal corpus.

### Added (`tests/test_e2e_pipeline.py`)

New test file authors a coherent minimal spec corpus (1 AE + 1 ADR + 1 WS + 1 Intent + 1 stub source file) in `tmp_path` and exercises the canonical consumer flow:

```
dekspec init
  → write minimal corpus
  → dekspec validate <each artifact>
  → dekspec audit linkage
  → dekspec aggregate agents-md
  → dekspec graph export
  → dekspec doctor
```

9 tests covering:

- `test_e2e_init_creates_scaffold` — `dekspec init` produces the expected directory tree.
- `test_e2e_validate_every_artifact` — every fixture artifact parses cleanly.
- `test_e2e_audit_linkage_clean` — coherent fixture → 0 CRITICAL audit findings.
- `test_e2e_aggregate_agents_md_produces_output` — aggregator builds AGENTS.md with ACCEPTED artifacts.
- `test_e2e_aggregate_includes_draft_with_status_all` — `--status all` includes DRAFT Intent.
- `test_e2e_graph_export_round_trip` — `graph export` JSON includes all 4 artifact IDs + 0 parse failures.
- `test_e2e_doctor_clean_on_populated_repo` — doctor reports CLEAN on coherent fixture.
- `test_e2e_doctor_critical_when_broken` — broken AE injected → doctor reports CRITICAL exit 2.
- `test_e2e_full_pipeline_in_sequence` — the canonical sequence in one shot, end-to-end.

**Total: 101 passing (was 92), 162 skipped, ruff clean.** These tests are the canonical regression gate for the consumer experience — any CLI breakage shows up here first.

### Why this matters

The unit + integration tests cover each parser/emitter/audit rule in isolation, but didn't catch the *interactions* between commands. The e2e suite specifically tests "the README's quickstart works." If you ever wonder whether shipping a change to the CLI broke the actual user flow, these tests give a yes/no answer in < 1 second.

### Fixture-construction notes

- IC was deliberately excluded from the fixture: IC requires a Version field (semver), Silent Failure Domain(s), and Governing ADRs sections — much more substantial than the other artifact types. The e2e flow exercises AE + ADR + WS + Intent which is sufficient coverage.
- The Intent's `components_affected:` glob (`services/example.py`) requires an actual stub source file in the repo for L7b-INT-COMPONENTS-RESOLVE to pass. The fixture creates this stub alongside the corpus.
- AE non-goals must use the `- **Label.** Why-prose` format (matched by `_NON_GOAL_BULLET`); plain `— ` separator doesn't extract the `why` clause and would fail T11-AE-BOUNDARY.

[v0.31.0]: https://github.com/Dektora/dekspec/releases/tag/v0.31.0

## [v0.30.1] — 2026-05-11

Patch release. Two bug fixes + one UX polish surfaced by v0.30.0's wheel smoke-test.

### Fixed (pytest collection under wheel install)

Installing the built wheel (`pip install dist/dekspec-*.whl`) then running `pytest` caused a collection error:

```
import file mismatch:
imported module 'dekspec.constraint_compiler.emitters.contract_test' has __file__
attribute .venv/lib/python3.13/site-packages/dekspec/.../contract_test.py
which is not the same as the test file we want to collect:
tooling/dekspec/constraint_compiler/emitters/contract_test.py
HINT: remove __pycache__ / .pyc files and/or use a unique basename for your test file modules
```

pytest was auto-discovering `contract_test.py` (the emitter module — `*_test.py` matches its default `python_files` glob) and choking on the source-tree-vs-wheel ambiguity. Two-part fix in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

`testpaths` restricts discovery to `tests/`; `python_files = ["test_*.py"]` drops the `*_test.py` glob so `contract_test.py` is never collected even if a future tool overrides `testpaths`.

### Fixed (vendoring tests fail under wheel install)

`tests/test_vendoring.py` assumes `library_root()` resolves to a source tree containing `skills/`, `templates/`, and `docs/`. When installed from a wheel, those directories aren't bundled (the markdown content vendors separately via `install-dekspec.sh`), so the tests failed. Added a second auto-skip in `tests/conftest.py`:

- If `(library_root() / "skills").is_dir()` is False, mark all tests in `test_vendoring.py` as skipped with reason "library installed from wheel".

Result:
- **Editable install (dev case):** 92 pass, 162 skipped (dektora2-fixture tests skip; vendoring tests run).
- **Wheel install (smoke-test case):** 82 pass, 172 skipped (dektora2-fixture + vendoring tests both skip).
- Neither install mode produces test errors.

### Changed (`audit linkage --fix` output groups by rule)

The fix proposal printout previously listed every fix in a flat sequence. With 14+ fixes that's noisy. Now grouped by rule family with per-rule counts in the header summary:

```
Proposed mechanical fixes (DRY-RUN): 14 (L6-BACKLINK=11, L7-ADR-SUPER-MIRROR=2, L8-MSN-INT-MIRROR=1)

## L6-BACKLINK (11)

  [L6-BACKLINK] AE-001 -> related_wss: add WS-009
    ...

## L7-ADR-SUPER-MIRROR (2)

  ...
```

Easier to scan; CI/grep-friendly per-rule sections.

[v0.30.1]: https://github.com/Dektora/dekspec/releases/tag/v0.30.1

## [v0.30.0] — 2026-05-11

Minor bump (PyPI publication prep). The package is now ready to publish — wheel + sdist build cleanly, all 9 schemas are correctly included as package-data, metadata is filled out for a respectable PyPI listing, and a manually-triggered + tag-driven publish workflow is wired in.

### Changed (`pyproject.toml` metadata)

- **Description** updated from the generic "Shared DekSpec library …" to the actual value proposition: "Spec-Driven Development framework for AI-augmented engineering: typed artifact IRs, audit engine, AGENTS.md aggregator, and Claude Code skills."
- **Development Status** classifier bumped 3-Alpha → 4-Beta (we're at v0.30 with 9 IRs, ~30 audit rules, 9 CLI subcommands, 232+ tests).
- **License classifier** added: `License :: Other/Proprietary License` (matches the existing `license = { text = "Proprietary" }` field).
- **OS classifiers** added: POSIX / Linux / MacOS (the framework is portable but skills + tooling have been exercised primarily on Linux + macOS).
- **Topic classifiers** added: Build Tools, Documentation, Quality Assurance, Testing.
- **Typing :: Typed** classifier added.
- **Keywords** expanded: added `sdd`, `claude-code`, `ai-augmented-engineering`, `constraint-compiler`, `audit`.
- **`[project.urls]`** added: Homepage, Repository, Changelog, Issues, Documentation — all pointing at `github.com/Dektora/dekspec` paths.

### Added (`.github/workflows/publish.yml`)

Publish workflow with three jobs (build → publish-testpypi → publish-pypi). Triggers:

- **Tag push (`v*.*.*`)** → builds + publishes to PyPI automatically.
- **`workflow_dispatch`** → manual trigger from the GitHub Actions UI, with a `target` input choosing `testpypi` or `pypi`.

Build job verifies the wheel installs + `dekspec --version` works before any publish job runs. Publish jobs use **PyPI trusted publishing** (OIDC, no long-lived tokens) via `pypa/gh-action-pypi-publish@release/v1`. Both `testpypi` and `pypi` are configured as protected GitHub environments (operator can add required reviewers on the `pypi` environment for an extra approval gate).

### Added (`RELEASING.md`)

New file documents:
- One-time PyPI / TestPyPI trusted-publisher setup (pending-publisher entries on the index, protected environments on GitHub).
- Cut-a-release procedure (bump `__version__`, CHANGELOG entry, commit, tag, push).
- TestPyPI staging procedure for breaking-change releases.
- Local smoke-test recipe for the built wheel.
- License-posture note explaining the public-but-proprietary stance.
- Yank procedure for broken releases.
- Versioning recap (Major / Minor / Patch).

### Verified

- `python -m build` produces a clean wheel (106 KB) + sdist (124 KB).
- Wheel contents include all 9 schemas (adr / architecture-element / domain-glossary / implementation-brief / intent / interface-contract / mission / system-vision / working-spec), the CLI entry point, every Python module, and proper METADATA + WHEEL + entry_points.txt records.
- `pip install --force-reinstall dist/dekspec-0.30.0-py3-none-any.whl && dekspec --version` works.
- `dekspec doctor` runs correctly from the installed wheel.
- Editable install (`pip install -e .`) continues to work for development; reinstall it after smoke-testing the wheel since the wheel install causes pytest to double-collect `emitters/contract_test.py`.

[v0.30.0]: https://github.com/Dektora/dekspec/releases/tag/v0.30.0

## [v0.29.0] — 2026-05-11

Minor bump (additive). New `dekspec doctor` composite health check CLI.

### Added (`dekspec doctor`)

```
dekspec doctor [--at REPO] [--dekspec-root DEKSPEC_ROOT] [--json]
```

Runs three checks in sequence and rolls up a traffic-light summary:

1. **verify-vendored** — drift between consumer repo and library source-of-truth. Auto-skipped when the repo isn't a vendored consumer (no `.dekspec-version`, no `.claude/skills/`, no `dekspec/templates/`).
2. **audit linkage** — full audit battery (all L1-L11 + T-series + D-series). Auto-skipped when no `<dekspec-root>/` content tree exists.
3. **graph parse** — count + list parse failures across the spec graph. Auto-skipped when no `<dekspec-root>/` content tree exists.

Exit codes:
- `0` = clean (all sections green or skipped)
- `1` = warning (drift detected or important/minor audit findings)
- `2` = critical (parse failures or critical audit findings)

`--json` mode emits a structured object: `{overall_status, exit_code, repo_root, dekspec_root, sections: [{name, status, summary, findings_count}]}`.

Text mode includes a per-section status table with traffic-light glyphs (`✓` clean, `!` warning, `✗` critical, `·` skipped) plus a "Run X for detail" remedy line for each non-clean section.

### Verified scenarios

- **dekspec library itself** (no dekspec/ tree, no vendored prefix): exit 0, all sections skipped.
- **Fresh `dekspec init` tmp tree**: exit 0, audit + parse sections clean (empty corpus parses cleanly).
- **Repo with a broken AE markdown file**: exit 2, audit + parse sections critical, output names `audit linkage` as the remedy.
- **Vendored consumer with stale `.dekspec-version`**: exit 1, verify-vendored section warning.

### Added (9 new tests; ~12 net new with auto-skipping; 92 + library-only passing today)

`tests/test_doctor.py`:
- `test_doctor_clean_repo_returns_zero`
- `test_doctor_fresh_init_is_clean`
- `test_doctor_broken_artifact_returns_two`
- `test_doctor_vendored_repo_with_drift_returns_warning`
- `test_doctor_json_emits_structured`
- `test_doctor_json_critical_exit_code_two`
- `test_doctor_skips_audit_when_no_dekspec_tree`
- `test_doctor_recommends_remedy_on_findings`
- `test_doctor_clean_vendored_repo_with_marker_is_clean`

[v0.29.0]: https://github.com/Dektora/dekspec/releases/tag/v0.29.0

## [v0.28.0] — 2026-05-11

Minor bump (additive). Phase 3 chain complete — 4 new `/write-intent` modes + 1 new `/write-mission` mode, plus the Phase 3 close-out gate sweep.

### Added (`/write-intent` Phase 3 modes — P3.1–P3.4)

`skills/write-intent/SKILL.md` gains four new Mode sections:

- **`--sync` (P3.1)** — post-merge cleanup on LOCKED Intents. Walks the `## Post-implementation sync` checklist (marks `[x]` items via `git log` / file-existence checks), discovers new bullets (test-promotion candidates, cross-reference rot, WS docstring lag), applies single-file edits within the original `Components affected:` scope, and logs an Editorial Amendment Log entry. Refuses to touch anything outside the original scope — substantive scope expansion routes through `--amend`.
- **`--audit` (P3.2)** — read-only health check on any non-terminal status. Re-runs every check `--analyze`/`--accept`/`--testpass` would run (schema validation; L7a + L7b + T13–T16 + L9 linkage; D19 + D20 drift; live size-cap recomputation; live coverage-report archaeology; L8 Mission linkage when set; Status-coherence). Reports findings table with CRITICAL/IMPORTANT/MINOR + recommended remedial mode. Exit code 0/1. Mutates nothing.
- **`--review` (P3.3)** — interactive section-by-section walkthrough on DRAFT/PROPOSED/ACCEPTED. Summarizes each major section (Title+Type+Autonomy, Linked AEs, Motivation, Desired Outcome, Type-specific block, Components affected, Verification, Open Issues), asks the engineer whether to revise, applies their edits. Re-parses to confirm schema validity after each walkthrough; reverts via `git checkout` if validation fails. Logs an Editorial Amendment Log entry. Never promotes Status.
- **`--amend` (P3.4)** — substantive mid-flight change with invariant re-check + Status cascade on DRAFT/PROPOSED/ACCEPTED/IMPLEMENTING/TESTFAIL/OVERSIZED. Engineer captures field + change-kind + old + new values before applying. After the edit, re-runs schema validation, all five hard caps, full linkage battery, drift checks, and Mission L8. On hard-cap violation → transitions to OVERSIZED. On audit-v2 CRITICAL → reverts. On non-violating edit → cascades Status backwards if the change invalidates prior state (PROPOSED → DRAFT because `--analyze` cache no longer matches; ACCEPTED → DRAFT because `--accept` validation is no longer current). Logs a Substantive Amendment Log entry. Refuses TESTPASS/MERGED/LOCKED/SUPERSEDED — locked Intents that need substantive change spawn a successor Intent.

Help Mode + Rules + Output sections updated to reflect all four flags. Frontmatter `argument-hint` extended. The `Out-of-scope flags` rule (which previously refused all four) replaced with five Phase-3-specific rules clarifying audit/sync/review/amend invariants. Skill grew from 482 → 710 lines.

### Added (`/write-mission` Phase 3 mode — P3.5)

`skills/write-mission/SKILL.md` gains a new **`--audit`** mode parallel to `/write-intent --audit`. Read-only health check on any non-terminal Mission status. Re-runs:

- Schema validation via `parse_mission`.
- T17 completeness (T17-MSN-VERIFICATION + T17-MSN-OUTCOME + T17-MSN-ROLLBACK).
- L8 bidirectional Intent linkage (L8-MSN-INT-EXISTS + L8-MSN-INT-MIRROR + L8-INT-AUTONOMY-EXCEEDS) per queue row.
- L9 Mission Verification cmd-resolve.
- L11 stale-ACTIVE check.
- Status-coherence (ACTIVE with no LOCKED child Intent; COMPLETE still in Active queue; etc.).

Findings table grouped by severity with recommended remedial action per row. Exit code 0/1. Mutates nothing.

### Closed (Phase 3 chain — 8 beads)

13 → 2 open beads after this commit. The Phase 3 chain (ds-2rz → ds-ob5 → ds-ngh → ds-zrf → ds-kz1 → ds-3o3 → ds-b9r → ds-why) is fully retired:

- **ds-2rz / ds-ob5 / ds-ngh / ds-zrf (P3.1–P3.4)**: `/write-intent --sync`/`--audit`/`--review`/`--amend` shipped in this release.
- **ds-kz1 (P3.5)**: Mission operational refinement shipped as `/write-mission --audit`.
- **ds-3o3 (P3.6)**: Tracker mirror prototype deferred per default (Decision D3 / v5 §22 — no observed board-view friction).
- **ds-b9r (P3.7)**: Symlink retirement confirmed no-op (D10 hard-cutover honored; no symlink or `write-change-request` skill ever created).
- **ds-why (P1 close-out gate)**: sweep complete — 0 open `dektora-mi-tbd-*` trackers in dekspec scope. Operator declaration is the actual exit signal.

Plus the three hygiene beads closed in the prior commit (ds-caf / ds-ab1 / ds-65a) were already-done.

**Remaining open: 2 (both deferred follow-ons).** ds-zuy = Mission rigor calibration after lived MSN execution data; ds-j8x = Phase 4 orchestration brain design (explicitly out of Phase 1–3 plan scope).

[v0.28.0]: https://github.com/Dektora/dekspec/releases/tag/v0.28.0

## [v0.27.0] — 2026-05-11

Minor bump (additive). `propose_fixes()` gains two new auto-fix families: L7-ADR-SUPER-MIRROR + L8 (MSN-INT-MIRROR / INT-MSN-MIRROR). Three of the previously-audit-only mirror rules can now be auto-applied via `dekspec audit linkage --fix --apply`.

### Added (L7-ADR-SUPER-MIRROR fix)

When `ADR-A.supersedes` contains `ADR-B` but `ADR-B.superseded_by` doesn't list `ADR-A`, propose a Fix that edits ADR-B's `*Superseded by:* ...` line in its `## Supersession` section.

- `*Superseded by:* none` → `*Superseded by:* ADR-A`
- `*Superseded by:* ADR-X` → `*Superseded by:* ADR-X, ADR-A` (preserves existing back-pointers)
- Multiple supersedes-by relationships against the same target are batched into one edit.

### Added (L8-MSN-INT-MIRROR fix)

When a Mission lists `INT-X` in its `intent_queue` but `INT-X.mission` is unset, propose a Fix that edits the Intent's `## Mission` section value from `none` (or the template placeholder `[ MSN-NNN or "none" ]`) to the Mission ID.

**Conservative:** if the Intent already references a *different* Mission, the fix proposer skips it — the engineer must resolve the conflict by hand (don't silently overwrite a real cross-reference).

### Added (L8-INT-MSN-MIRROR fix)

When `Intent.mission` references `MSN-Y` but `MSN-Y.intent_queue` has no row for the Intent, propose a Fix that **appends** a queue row to the Mission's `### Intent queue` table:

```
| INT-NNN | <intent name> | <intent_type> | <intent status> | added by L8 mirror fix |
```

Title, type, and status are pulled from the Intent's IR. Existing rows are preserved.

### Verified against dektora2

`dekspec audit linkage --at /data/projects/dektora2 --dekspec-root docs/dekspec --fix` now proposes 2 L7-ADR-SUPER-MIRROR fixes (the same 2 mirror gaps L7 has been surfacing since v0.6.0):
- ADR-009 ← ADR-039 (`*Superseded by:* none` → `*Superseded by:* ADR-039`)
- ADR-014 ← ADR-055 (`*Superseded by:* none` → `*Superseded by:* ADR-055`)

dektora2 has 0 Intents/Missions, so 0 L8 fixes proposed against the real corpus today (the rules are ready for when Intents start landing).

### Changed (`propose_fixes()` returns multiple families)

- `propose_fixes(repo_root, dekspec_root)` now returns L6 + L7 + L8 fixes in one call.
- Older callers that expected only L6 must filter by `fx.rule == "L6-BACKLINK"`.
- `apply_fixes(fixes, dry_run)` is unchanged — handles all four rule families uniformly via the existing `before`/`after` line-replace contract.

### Added (8 new tests; 232 total passing, 13 skipped)

`tests/test_l7_l8_fixes.py`:
- `test_l7_fix_adds_back_pointer_when_target_says_none` — apply round-trip on tmp file.
- `test_l7_fix_appends_to_existing_list` — preserves prior back-pointers.
- `test_l7_fix_skips_when_back_pointer_already_present` — no-op idempotence.
- `test_l7_fix_against_real_dektora2_dektora2_yields_two` — copy ADR-009 + ADR-014 + their successors into a tmp tree, confirm both fixes propose cleanly.
- `test_l8_msn_int_mirror_writes_mission_into_intent_section`
- `test_l8_int_msn_mirror_appends_queue_row` — confirms new row appended after existing rows.
- `test_l8_skips_when_already_mirrored`
- `test_l8_msn_int_mirror_skips_when_intent_mission_already_set` — conservative skip for conflicting cross-refs.

Plus updated `test_propose_fixes_only_l6_in_v0_5` → `test_propose_fixes_families_v0_27` to assert L7 mirrors surface against dektora2.

[v0.27.0]: https://github.com/Dektora/dekspec/releases/tag/v0.27.0

## [v0.26.0] — 2026-05-11

Minor bump (additive). New `dekspec validate` CLI + L11 Mission-stale advisory audit.

### Added (`dekspec validate`)

```
dekspec validate <file> [--json]
```

Quick parse-only check with **no persistence side effect** — no run dir, no IR persisted, no events written. Useful for editor integrations and pre-commit hooks. Auto-detects artifact kind from filename. Reports schema validation errors + parse warnings.

Exit codes:
- `0` — file parses cleanly (warnings are not errors).
- `2` — unrecognized filename / file not found.
- `4` — parse error (schema validation failure).

`--json` mode emits a structured object: `{ok, id, status, kind, warnings}` on success or `{ok: false, error, error_type}` on failure.

### Added (L11 Mission-stale advisory)

- **L11-MSN-STALE** (minor): a Mission with `status=ACTIVE` for more than **90 days** since its `modified` (or `created` as fallback) date is flagged. Either record progress (and bump `Modified:`) or advance to COMPLETING / KILLED.

Skipped for non-ACTIVE missions and for missions with no `modified`/`created` field. Invalid date strings skip gracefully.

### Added (11 new tests; 223 total passing, 14 skipped)

`tests/test_validate_and_l11.py`:
- `test_validate_succeeds_on_real_dektora2_ae`
- `test_validate_json_emits_structured`
- `test_validate_returns_4_on_parse_error`
- `test_validate_unknown_filename_returns_2`
- `test_validate_singleton_glossary` — confirms singleton kind detection works.
- `test_l11_fires_for_active_mission_older_than_90_days`
- `test_l11_skips_recent_active_mission`
- `test_l11_skips_complete_mission_even_if_old`
- `test_l11_skips_when_no_modified_field`
- `test_l11_falls_back_to_created_when_modified_absent`
- `test_l11_invalid_date_skips_gracefully`

[v0.26.0]: https://github.com/Dektora/dekspec/releases/tag/v0.26.0

## [v0.25.0] — 2026-05-11

Minor bump (additive). New `dekspec init` CLI — bootstrap a new dekspec/ tree in a consumer repo.

### Added (`dekspec init`)

```
dekspec init [--at REPO] [--dekspec-root dekspec] [--force]
```

Creates the conventional dekspec subdirectory tree, empty index files, and a starter `AGENTS.md` placeholder. Idempotent — existing files are preserved unless `--force` is passed.

Subdirectories created (each with a `.gitkeep` so empty dirs survive in git):
- `dekspec/adrs/`
- `dekspec/architecture-elements/`
- `dekspec/working-specs/`
- `dekspec/api-contracts/`
- `dekspec/impl-briefs/{queued,active,completed}/`
- `dekspec/intents/`
- `dekspec/missions/`
- `dekspec/divergences/`

Index files seeded with a one-line "no entries yet — author the first one with `/write-<kind>`" hint:
- `dekspec/adr-index.md`
- `dekspec/architecture-elements-index.md`
- `dekspec/working-spec-index.md`
- `dekspec/interface-contract-index.md`
- `dekspec/intent-index.md`
- `dekspec/mission-index.md`

`AGENTS.md` at repo root: placeholder with a DO-NOT-EDIT note pointing at `dekspec aggregate agents-md` for regeneration once artifacts land.

Output ends with a 3-step "Next steps" hint: vendor skills via install-dekspec.sh, author the first artifact, run aggregate agents-md.

### Added (5 new tests; 212 total passing, 14 skipped)

`tests/test_init.py`:
- `test_init_creates_full_tree` — confirms all 10 subdirs + 6 index files + AGENTS.md.
- `test_init_is_idempotent` — running twice doesn't fail; custom edits to indexes are preserved.
- `test_init_force_overwrites_indexes` — `--force` overwrites custom content with the default scaffold.
- `test_init_custom_dekspec_root` — `--dekspec-root specs` uses a non-default subdir.
- `test_init_output_lists_created_and_skipped` — output contains "Created" + "Next steps" sections.

[v0.25.0]: https://github.com/Dektora/dekspec/releases/tag/v0.25.0

## [v0.24.0] — 2026-05-11

Minor bump (additive). New `dekspec graph export` CLI — dump the entire SpecGraph as a single JSON document for downstream tooling.

### Added (`dekspec graph export`)

```
dekspec graph export [--at REPO] [--dekspec-root DEKSPEC_ROOT]
                     [--output PATH] [--include KIND,...] [--pretty]
```

Walks the SpecGraph and writes a single JSON document containing every IR. Useful for downstream tooling (eval pipelines, AI agents, doc generators, CI checks) that want the spec graph as data without reimplementing the parsers.

Output schema (v1.0):
```json
{
  "schema_version": "1.0",
  "library_version": "0.24.0",
  "repo_root": "/data/projects/dektora2",
  "dekspec_root": "docs/dekspec",
  "exported_at": "2026-05-11T05:18:00Z",
  "ir_count": 169,
  "parse_failures": [...],
  "irs": [...]
}
```

- `--include`: comma-separated kinds (any of `AE,ADR,WS,IC,IB,INT,MSN,GLOSSARY,VISION`). Default: `ALL` (every kind).
- `--pretty`: indent JSON. Default: compact.
- `--output`: write to file. Default: stdout.

IRs are sorted by `id` for stable diffs across runs.

### Verified against dektora2

`dekspec graph export --at /data/projects/dektora2 --dekspec-root docs/dekspec --output /tmp/dektora2-graph.json --pretty` produces a 2.9 MB JSON document with 169 IRs:
- 59 ADR
- 45 WS
- 39 AE
- 14 IC
- 10 IB
- 1 DOMAIN-GLOSSARY (98 terms)
- 1 SYSTEM-VISION

### Added (7 new tests; 207 total passing, 14 skipped)

`tests/test_graph_export.py`:
- `test_graph_export_writes_full_document_to_file` — schema version + ir_count + parse_failures shape.
- `test_graph_export_irs_are_sorted_by_id` — stable ordering.
- `test_graph_export_filter_by_kind_only_aes` — `--include AE` filter.
- `test_graph_export_filter_includes_singleton_glossary` — singleton inclusion via `--include GLOSSARY`.
- `test_graph_export_unknown_kind_errors` — unknown kind exits 2.
- `test_graph_export_stdout_default` — stdout mode for piping.
- `test_graph_export_includes_library_version` — `library_version` field tracks the package version.

[v0.24.0]: https://github.com/Dektora/dekspec/releases/tag/v0.24.0

## [v0.23.0] — 2026-05-11

Minor bump (additive). Aggregator gains glossary + vision sections; CLI compile accepts both singletons.

### Changed (`dekspec aggregate agents-md` includes singletons)

- `--include` default expanded from `AE,ADR,WS,IB,INT,MSN` to `VISION,GLOSSARY,AE,ADR,WS,IB,INT,MSN`. New valid kinds: `VISION`, `GLOSSARY`.
- New `# System Vision: <name>` section appears at the top (after the header comment + summary). Includes the H1 preamble (elevator pitch), `## What this is`, and `## Out of scope (Vision-level)` (from `what_we_are_not_building`).
- New `# Domain Glossary` section appears between System Vision and Architecture Elements. Lists every term grouped by category (one H2 per category), each rendered as `- **Term** — Canonical definition`.
- Header summary line gains glossary term count and vision name when present.

### Changed (`dekspec compile` accepts singletons)

- `_detect_artifact_kind` now recognizes `system-vision.md` (kind=`vision`) and `domain-glossary.md` (kind=`glossary`).
- `dekspec compile system-vision.md --emit ir --treat-as-locked` produces a validated IR.
- `dekspec compile domain-glossary.md --emit ir --treat-as-locked` produces a validated IR.
- `--emit contract-test`, `--emit ci-gate`, and `--emit agents-md` all correctly reject singletons (no per-singleton emitter beyond IR yet — singletons appear in the aggregator output).

### Verified against dektora2

`dekspec aggregate agents-md --at /data/projects/dektora2 --dekspec-root docs/dekspec --status all` now produces output with this top-level structure:

```
# AGENTS.md
Compiled context ... 39 AE, 59 ADR, 45 WS, 10 IB, 0 INT, 0 MSN. Glossary: 98 terms. Vision: Dektora.

# System Vision: Dektora
# Domain Glossary
# Architecture Elements
# Architecture Decision Records
# Working Specs
# Implementation Briefs
```

### Added (3 new tests; 200 total passing, 14 skipped)

- `test_aggregate_includes_vision_section_by_default` — confirms `# System Vision: Dektora` appears with default `--include`.
- `test_aggregate_includes_glossary_section_by_default` — confirms `# Domain Glossary` + 98-term count.
- `test_aggregate_include_only_glossary` — `--include GLOSSARY` produces a glossary-only AGENTS.md.

[v0.23.0]: https://github.com/Dektora/dekspec/releases/tag/v0.23.0

## [v0.22.0] — 2026-05-11

Minor bump (additive). L10 glossary-coverage advisory audit — surfaces likely-jargon Title-Case phrases that aren't in the Domain Glossary.

### Added (`L10-GLOSSARY-COVERAGE`)

For each artifact body, scan the prose surfaces (`purpose_and_scope`, `key_concepts`, `constraints_and_quality_notes`, `motivation`, `desired_outcome`, `outcome`, `decision`, `goal`, `what_this_does`, `what_this_is`, plus all `responsibilities[]` entries) for multi-word Title-Case phrases (2-4 words, each starting with a capital letter, not preceded by sentence-ending punctuation).

A phrase fires `L10-GLOSSARY-COVERAGE` (minor, advisory) when:
1. The Domain Glossary is present.
2. The phrase isn't in the glossary (case-insensitive, with cheap singular/plural variants).
3. The phrase isn't in the framework stopword set (`Working Spec`, `Implementation Brief`, `Architecture Element`, etc., plus generic Title-Case stopwords like `Pull Request`, `United States`).
4. The phrase appears **at least 2 times** in the artifact's prose (cheap recurrence signal that distinguishes real domain terms from one-off proper-noun mentions).

Findings are rolled up to **one per artifact** listing the top 5 candidates by occurrence, e.g.:
```
[L10-GLOSSARY-COVERAGE] AE-015  (semantic)
  AE-015 uses 1 likely-jargon Title-Case phrase(s) not present in the Domain
  Glossary (top 5 by occurrence): `Tensor Dtype Lifecycle Contract`×2.
  Per audit-v2 (advisory), either add a glossary entry or rephrase if the
  term is not actually domain jargon.
```

DEPRECATED + SUPERSEDED + TODO artifacts skipped. The glossary itself + system-vision are skipped.

Skipped entirely when `graph.glossary()` returns None (consumer repos without a glossary file).

### Verified against dektora2

11 L10 findings surfaced — examples: `Vision Input Constraints` in ADR-002, `Cache Implementation` in ADR-020, `Apple Silicon` in ADR-032 (false positive — proper noun), `Tensor Dtype Lifecycle Contract` in AE-015 (genuine candidate for glossary entry). Total dektora2 findings: 39 → 50.

### Added (7 new tests; 197 total passing, 14 skipped)

`tests/test_l10_glossary.py`:
- `test_l10_skips_when_no_glossary` — glossary=None → 0 findings.
- `test_l10_skips_when_glossary_has_term` — known term → 0 findings.
- `test_l10_fires_for_unknown_recurring_jargon` — `Spline Compression Engine` × 3 → fires.
- `test_l10_skips_one_off_phrases` — single occurrence → 0 findings.
- `test_l10_skips_stopwords` — `Working Spec` + `Implementation Brief` recurrences → 0 findings.
- `test_l10_skips_glossary_artifacts_themselves` — DOMAIN-GLOSSARY id excluded from the audit.
- `test_l10_caps_at_top_5` — single rolled-up finding per artifact, listing top 5.

[v0.22.0]: https://github.com/Dektora/dekspec/releases/tag/v0.22.0

## [v0.21.0] — 2026-05-11

Minor bump (additive). Ninth artifact-type IR — System Vision (singleton) — and SpecGraph integration for both singletons (Domain Glossary + System Vision).

### Added (System Vision IR)

- `dekspec/schemas/system-vision.schema.yaml` — JSON Schema Draft 2020-12 for the singleton `<dekspec-root>/system-vision.md`. Captures: ir_schema_version, id (const `SYSTEM-VISION`), name (from H1, with optional `System Vision:` / `Vision Note:` prefix stripped), source, optional status / created / modified / preamble (text between H1 and first H2) / what_this_is / who_this_is_for / why_this_exists / what_success_looks_like (bullet list) / what_we_are_not_building (bullet list) / parse_warnings.
- `dekspec.constraint_compiler.parser.parse_vision(path)` — produces a validated IR.
- `dekspec.constraint_compiler.VisionParseError` exposed alongside the other parse-error classes.

### Added (SpecGraph singleton integration)

- `SpecGraph.load()` now also loads `<dekspec-root>/domain-glossary.md` and `<dekspec-root>/system-vision.md` when present. They live in `irs_by_id` keyed by `DOMAIN-GLOSSARY` / `SYSTEM-VISION`.
- New accessors: `SpecGraph.glossary() -> dict | None` and `SpecGraph.vision() -> dict | None`. Both return `None` when the singleton isn't present.
- Parse failures on either singleton are surfaced via `graph.parse_failures()` with `artifact_kind='glossary'` or `'vision'`.
- dektora2 SpecGraph total: 167 → 169 IRs.

### Verified against dektora2

`SpecGraph.load('/data/projects/dektora2', dekspec_root='docs/dekspec')`:
- `g.vision().name` → `'Dektora'`
- `len(g.glossary()['terms'])` → 98
- 0 parse failures.

### Added (9 new tests; 190 total passing, 14 skipped)

`tests/test_parser_vision.py` (6 tests):
- `test_parse_vision_real_dektora2_succeeds`
- `test_parse_vision_extracts_preamble_and_sections`
- `test_parse_vision_synthetic_minimal`
- `test_parse_vision_h1_without_prefix_works` (just `# Title`, no `System Vision:` prefix)
- `test_parse_vision_missing_h1_raises`
- `test_parse_vision_missing_file_raises`

`tests/test_graph.py` (2 new tests):
- `test_graph_loads_singleton_glossary_and_vision` — confirms both load + accessors return populated IRs.
- `test_graph_glossary_is_none_when_absent` — clean tmp_path → both accessors return None.

[v0.21.0]: https://github.com/Dektora/dekspec/releases/tag/v0.21.0

## [v0.20.0] — 2026-05-11

Minor bump (additive). Eighth artifact-type IR — Domain Glossary (singleton).

### Added (Domain Glossary IR)

- `dekspec/schemas/domain-glossary.schema.yaml` — JSON Schema Draft 2020-12 for the singleton `<dekspec-root>/domain-glossary.md`. Captures: ir_schema_version, id (const `DOMAIN-GLOSSARY`), source, optional created/modified/purpose, and a flat list of `terms` where each entry has `term`, `category` (the H2 section the term lives under), and optional `canonical_definition`, `not_this`, `code_convention`.
- `dekspec.constraint_compiler.parser.parse_glossary(path)` — produces a validated IR. Walks H2 sections (each is a category) for markdown tables of `(Term | Canonical Definition | NOT this | Code convention)`. Skips meta H2s like `Created`, `Modified`, `Purpose`, `Amendment Log`, `Status`, `Source`.
- `dekspec.constraint_compiler.GlossaryParseError` exposed alongside the other parse-error classes.

### Verified against dektora2

`parse_glossary('/data/projects/dektora2/docs/dekspec/domain-glossary.md')` extracts **98 terms across 11 categories**: API & Content Types, Architecture & Pipeline, DekSpec Artifacts (Layer 1), Document Hierarchy Rules, Embedding & Tensor, Graph & Storage, Numeric Constraints, Position & Injection, Quantization & Compression, Scoring & Geometry, Timeline & Topics.

(Glossary-coverage audit — every artifact body's introduced jargon term has a glossary entry — is left for a future task. The IR is the prerequisite that unblocks it.)

### Added (7 new tests; 182 total passing, 14 skipped)

`tests/test_parser_glossary.py`:
- `test_parse_glossary_real_dektora2_succeeds` — bulk parse of 98-term real glossary.
- `test_parse_glossary_extracts_categories` — confirms category coverage.
- `test_parse_glossary_extracts_canonical_definition` — confirms field extraction.
- `test_parse_glossary_synthetic_minimal` — minimal one-category-one-term fixture.
- `test_parse_glossary_skips_meta_sections` — Created/Purpose/Amendment Log H2s are NOT term categories.
- `test_parse_glossary_invalid_file_path_raises` — missing file → FileNotFoundError.
- `test_parse_glossary_handles_partial_rows` — rows with only a term (no definition) still extract.

[v0.20.0]: https://github.com/Dektora/dekspec/releases/tag/v0.20.0

## [v0.19.0] — 2026-05-11

Minor bump (additive). Closes the agents-md emitter loop for all 7 artifact types (Intent + Mission emitters land here) and adds L9 verification-cmd-resolves audit.

### Added (`emit_intent` + `emit_mission`)

- `emit_intent(ir)` — per-Intent fragment with status/type/autonomy line, optional Mission backlink, Shapes (linked AEs), Motivation, Desired outcome, NFR target line (when type_specific.metric+target are present), Components affected (capped at 10), and Verification predicate (capped at 8). Wrapped in canonical BEGIN/END markers.
- `emit_mission(ir)` — per-Mission fragment with status/autonomy-ceiling/owner line, Outcome, Mission Verification, Out-of-scope, Flag (when not "none"), Rollback, Kill criteria, and Intent queue (each row showing INT id + title + status; capped at 10).
- `emit(ir)` dispatcher routes INT-NNN → `emit_intent`, MSN-NNN → `emit_mission`. All 7 artifact types now have AGENTS.md emitters: AE, ADR, WS, IB, INT, MSN. (IC remains the only kind without an agents-md emitter — ICs use `--emit contract-test` or `--emit ci-gate` instead.)

### Changed (aggregator includes Intents + Missions)

- `dekspec aggregate agents-md`'s `--include` default expanded from `AE,ADR,WS,IB` to `AE,ADR,WS,IB,INT,MSN`.
- New `# Missions` section appears between `# Implementation Briefs` and `# Intents`.
- New `# Intents` section appears at the bottom (the leaf artifacts).
- Header summary line now reports Intent + Mission counts.

### Changed (`dekspec compile --emit agents-md` accepts INT + MSN)

- Previously rejected; now produces fragments using `emit_intent` / `emit_mission`.

### Added (L9 verification-cmd-resolves audit)

- **L9-INT-CMD-RESOLVE** (minor): each Intent.verification cmd should resolve to an executable script or known tool.
- **L9-MSN-CMD-RESOLVE** (minor): each Mission.mission_verification cmd should resolve.

Resolution rules (in `_resolves(cmd, repo_root)`):
1. `pytest` (and any flag) resolves if `pytest` is on PATH (via `shutil.which`).
2. `scripts/<name>.sh` resolves if the file exists and is executable, relative to `repo_root`.
3. Other commands resolve if `which <first-token>` finds them.

WARNING-level by design — Intents in DRAFT often cite scripts that don't exist yet (per audit-v2's `dektora-mi-tbd-*` deferral pattern).

DEPRECATED + SUPERSEDED + COMPLETE Intents and COMPLETE/KILLED/SUPERSEDED Missions are skipped.

### Added (12 new tests; 175 total passing, 14 skipped)

- `tests/test_emitter_agents_md.py::test_emit_intent_includes_status_type_motivation_components` — synthesized Intent fixture confirms fragment shape.
- `tests/test_emitter_agents_md.py::test_emit_mission_includes_outcome_verification_queue` — synthesized Mission fixture confirms fragment shape.
- `tests/test_emitter_agents_md.py::test_emit_dispatches_by_id_prefix` — extended (now uses tmp_path because dektora2 has no INT/MSN).
- `tests/test_l9_verification.py` (9 tests):
  - `test_resolves_pytest_when_on_path` (verifies `pytest` resolves via `shutil.which`).
  - `test_resolves_unknown_binary_returns_false`.
  - `test_resolves_scripts_path_when_file_exists`.
  - `test_resolves_scripts_path_missing_returns_false`.
  - `test_l9_int_cmd_resolve_real_pytest` (passes — no false-positives).
  - `test_l9_int_cmd_resolve_unknown_command_fires`.
  - `test_l9_msn_cmd_resolve_unknown_command_fires`.
  - `test_l9_skips_terminal_intents`.
  - `test_l9_skips_terminal_missions`.
  - `test_l9_message_includes_cmd_and_artifact_id`.

[v0.19.0]: https://github.com/Dektora/dekspec/releases/tag/v0.19.0

## [v0.18.0] — 2026-05-11

Minor bump (additive). M1 — improve ADR `reconsideration_triggers` extraction precision for grandfathered ADRs that use the pre-2026-04-24 prose-form Validation section.

### Changed (`_extract_validation`)

- New `_RECONSIDER_PROSE` regex matches sentences (or clauses) that begin with one of: `revisit if`, `revisit when`, `revisit on`, `revisit once`, `revisit after`, `reconsider if/when/on/once/after`, optionally with `this`, `this decision`, or `should be` modifiers in front of the trigger word.
- When `_extract_validation` falls back to `raw_prose` for a grandfathered ADR (no `**Reconsideration triggers:**` heading), it now also runs `_RECONSIDER_PROSE.findall(prose)` against the same prose and, if any matches are found, populates `reconsideration_triggers` with the joined matches alongside `raw_prose`.
- This means the `agents-md` emitter (which prefers `reconsideration_triggers` over `raw_prose`) now produces a useful "Reconsider this decision if..." line for grandfathered ADRs without forcing the engineer to migrate to the post-2026-04-24 split form.

### Verified against dektora2

4 grandfathered ADRs newly surface a `reconsideration_triggers` field that previously was only `raw_prose`:
- ADR-033 — "reconsider if the sentence-level chunking produces poor mind map structure..."
- ADR-034 — "reconsider if the number of routing fields grows beyond what embedded JSON..."
- ADR-055 — "reconsider if the per-segment O(N²) similarity cost becomes a measurable hot-path burden..."
- ADR-057 — "reconsider if intra-node asymmetric compression becomes necessary..."

These now contribute to the `dekspec aggregate agents-md` output's "Reconsider this decision if" lines.

### Added (4 new tests; 163 total passing, 14 skipped)

- `test_parse_adr_extracts_reconsider_from_prose_grandfathered` — `We will reconsider if X` extracts a trigger.
- `test_parse_adr_extracts_reconsider_with_revisit_marker` — `Revisit when X` also extracts.
- `test_parse_adr_no_reconsider_phrase_falls_back_to_prose_only` — no marker → raw_prose only (no false-positive trigger).
- `test_parse_adr_real_dektora2_grandfathered_extracted` — confirms ADR-033 + ADR-055 are surfaced from the real corpus.

[v0.18.0]: https://github.com/Dektora/dekspec/releases/tag/v0.18.0

## [v0.17.0] — 2026-05-11

Minor bump (additive). D19 + D20 Intent prose content-drift checks — mirror of D17/D18 for AE prose, applied to Intent.motivation and Intent.desired_outcome.

### Added (D19 + D20)

- **D19-INT-NUMERIC-NO-WS-CITE** (important): Intent.motivation or Intent.desired_outcome contains a numeric value with a unit (`ms`, `MiB`, `tokens`, `req/s`, `%`, etc.) outside a sentence that also cites a `WS-NNN`. Per audit-v2 D19, route quantitative targets to a WS.
- **D20-INT-RATIONALE-NO-ADR-CITE** (important): Intent.motivation or Intent.desired_outcome contains a rationale-marker phrase outside a sentence that also cites an `ADR-NNN`. Per audit-v2 D20, route rationale to an ADR.

NFR Intents may put a Target in `type_specific.target` — that field is **exempt by design** (the predicate's whole point is the numeric Target). D19/D20 only walk `motivation` and `desired_outcome`, never the type-specific block.

DEPRECATED + SUPERSEDED + TODO Intents are skipped.

### Verified against dektora2

dektora2 has 0 Intents currently, so D19/D20 fire 0 findings against the corpus today. The library is ready for when Intents start landing.

### Added (4 new tests; 159 total passing, 14 skipped)

- `test_d_series_d19_int_numeric_synthetic` — `42 ms` in motivation triggers D19.
- `test_d_series_d19_skips_when_ws_cited_in_intent` — `WS-039 §Latency targets pins this to 42 ms` does NOT fire.
- `test_d_series_d20_int_rationale_synthetic` — `We chose ... because` triggers D20.
- `test_d_series_skips_superseded_intent` — SUPERSEDED Intents produce 0 D-series findings.

Plus updated 4 existing AE-D-series FakeGraph fixtures to add `def intents(self): return []` so they remain compatible after `_d_artifact_drift` started walking intents too.

[v0.17.0]: https://github.com/Dektora/dekspec/releases/tag/v0.17.0

## [v0.16.0] — 2026-05-11

Minor bump (additive). Seventh artifact-type IR — Mission — plus L8 Mission ↔ Intent bidirectional linkage + T17 Mission completeness checks + LX-DUP coverage for missions.

### Added (Mission IR)

- `dekspec/schemas/mission.schema.yaml` — JSON Schema Draft 2020-12 for `MSN-NNN-*.md`. Captures: id, name, status (TODO/ACTIVE/COMPLETING/COMPLETE/KILLED/SUPERSEDED), source, owner, created/modified, autonomy_ceiling, outcome, mission_verification (≥1 named cmd checks per T17), out_of_scope, flag_strategy (flag_name/default_state/who_flips_it_on/removal_plan), rollback_plan, kill_criteria, first_intent (INT-NNN or sketch), intent_queue (table of {id,title,type,status,notes}), discovered_prerequisites, notes, amendment_log, parse_warnings.

- `dekspec.constraint_compiler.parser.parse_mission(path)` — produces a validated IR. Handles the Mission template's H3-inside-H2-wrapper structure: `Near-immutable section` and `Live section` H2 wrappers each contain the substantive H3 subsections, which the parser flattens into a single name→body map. Top metadata uses `**Key:** value` lines (not `## Status` H2). Falls back to H2 for `Amendment Log` which lives outside the wrappers.
- New helper `_split_h3_sections(body)` mirrors `_split_sections` for H3 headings.
- `dekspec.constraint_compiler.MissionParseError` exposed alongside the other parse-error classes.
- `SpecGraph.missions()` iterator + recursive loader for `dekspec/missions/`. LX-DUP now walks missions too.

### Added (L8 Mission ↔ Intent bidirectional linkage)

- **L8-MSN-INT-MIRROR** (important): if Mission lists INT-X in intent_queue, INT-X.mission must reference this Mission.
- **L8-INT-MSN-MIRROR** (important): if Intent.mission references MSN-Y, MSN-Y.intent_queue must list this Intent.
- **L8-MSN-INT-EXISTS** (critical): each MSN.intent_queue[].id must resolve.
- **L8-INT-MSN-EXISTS** (critical): Intent.mission must resolve.
- **L8-INT-AUTONOMY-EXCEEDS** (critical): Intent.autonomy must NOT exceed Mission.autonomy_ceiling. Ordering: `manual` < `low` < `medium` < `high`.

### Added (T17 Mission completeness)

- **T17-MSN-VERIFICATION** (important): no `mission_verification` cmd checks.
- **T17-MSN-OUTCOME** (important): no §Outcome paragraph.
- **T17-MSN-ROLLBACK** (important): no §Rollback plan paragraph.

DEPRECATED + KILLED + COMPLETE + SUPERSEDED Missions are skipped for non-critical T17 checks.

### Changed (`dekspec compile` accepts MSN-NNN-*.md)

- New `--detect-artifact-kind` branch for `MSN-NNN-*.md`; `--emit ir` works on Missions; other emitters correctly reject.

### Added (21 new tests; 155 total passing, 14 skipped)

`tests/test_parser_mission.py` (10 tests) — synthesized 60-line Mission fixture exercising every section: status, owner, autonomy ceiling, mission_verification yaml, out_of_scope bullets, flag_strategy fields, kill criteria, first intent extraction, intent queue table, malformed filename + invalid status rejection.

`tests/test_l8_mission.py` (11 tests) — covers all 5 L8 sub-rules + all 3 T17 sub-rules with FakeGraph fixtures: T17 absences, T17 skipped for terminal missions, MSN→INT mirror gap, INT→MSN mirror gap, queue references unknown intent, mission ref unknown, autonomy exceeds ceiling, autonomy at ceiling passes, clean bidirectional passes.

[v0.16.0]: https://github.com/Dektora/dekspec/releases/tag/v0.16.0

## [v0.15.0] — 2026-05-11

Minor bump (additive). Sixth artifact-type IR — Intent — plus L7-Intent linkage rules + LX-DUP coverage for intents.

### Added (Intent IR)

- `dekspec/schemas/intent.schema.yaml` — JSON Schema Draft 2020-12 for `INT-NNN-*.md`. Captures id, name, status (11 lifecycle values: TODO/DRAFT/OVERSIZED/PROPOSED/ACCEPTED/IMPLEMENTING/TESTFAIL/TESTPASS/MERGED/LOCKED/SUPERSEDED), source, intent_type (7-value enum: feature/bug/nfr/adr-driven/refactor/documentation/environment), autonomy (manual/low/medium/high), branch, mission (parent MSN-NNN ref), source_provenance, superseded_by, created/modified, linked_architecture_elements, motivation, desired_outcome, type_specific (per-type fields: reproduction/metric+target/adr/behavior_equivalence/coverage_gap/environment_change), components_affected (file globs), verification (named cmd checks), open_issues, amendment_log, parse_warnings.

- `dekspec.constraint_compiler.parser.parse_intent(path)` — produces a validated IR. Lossy by design; missing fields surface as `parse_warnings`.
- `dekspec.constraint_compiler.IntentParseError` — exposed alongside the other parse-error classes.
- `SpecGraph.intents()` — yields Intent IRs.
- Loader recurses into `dekspec/intents/*.md`; LX-DUP now also walks intents.

### Added (L7-Intent linkage rules)

- **L7a-INT-AE-MISSING** (important): Intent has empty `linked_architecture_elements`.
- **L7a-INT-AE-EXISTS** (critical): each linked AE-NNN must resolve in the registry.
- **L7b-INT-COMPONENTS-MISSING** (important): Intent has empty `components_affected`.
- **L7b-INT-COMPONENTS-RESOLVE** (important): each glob in `components_affected` must match ≥1 path under `repo_root` (uses `glob.glob(..., recursive=True)`). Skipped when graph has no `repo_root`.
- **T14-INT-VERIFICATION** (important): Intent has no `verification` cmd checks.

DEPRECATED + SUPERSEDED Intents are skipped.

(Note: rule prefix `L7-` here covers Intent linkage per audit-v2; it does NOT collide with the existing `L7-ADR-SUPER-*` family because each rule has its own unique full code and the `artifact_id` namespace disambiguates.)

### Changed (`dekspec compile` accepts INT-NNN-*.md)

- New `--detect-artifact-kind` branch for `INT-NNN-*.md` filenames.
- `--emit ir` works on Intents; `--emit contract-test`, `--emit ci-gate`, and `--emit agents-md` correctly reject Intents (Intent agents-md fragment is a future task).

### Added (17 new tests; 134 total passing, 14 skipped)

`tests/test_parser_intent.py` (10 tests):
- `test_parse_intent_succeeds`, `test_parse_intent_extracts_type_and_autonomy`, `test_parse_intent_extracts_mission`, `test_parse_intent_extracts_linked_aes`, `test_parse_intent_extracts_components_affected`, `test_parse_intent_extracts_verification_yaml`, `test_parse_intent_extracts_amendment_log`, `test_parse_intent_bad_filename_raises`, `test_parse_intent_nfr_type_extracts_metric_target`, `test_parse_intent_invalid_status_raises`.

`tests/test_l7_intent.py` (7 tests):
- `test_l7a_int_ae_missing_when_no_aes`, `test_l7a_int_ae_exists_for_unknown_ae`, `test_l7a_int_ae_exists_passes_when_ae_resolves`, `test_l7b_components_missing`, `test_l7b_components_resolve_with_real_repo` (creates real files in tmp_path), `test_t14_verification_missing`, `test_l7_skips_superseded_intents`.

[v0.15.0]: https://github.com/Dektora/dekspec/releases/tag/v0.15.0

## [v0.14.0] — 2026-05-11

Minor bump (additive). D-series content-drift checks for AE prose — D17 (no measurable targets in AE) + D18 (no decision rationale in AE).

### Added (D-series)

- **D17-AE-NUMERIC-NO-WS-CITE** (important): AE prose contains a numeric value with a unit (`ms`, `MiB`, `GiB`, `tokens`, `req/s`, `%`, etc.) outside a sentence that also cites a `WS-NNN`. Per audit-v2 D17, quantitative SLOs belong in WS, with AE citing the WS that holds the number.
- **D18-AE-RATIONALE-NO-ADR-CITE** (important): AE prose contains a rationale-marker phrase (`we chose`, `the tradeoff is`, `instead of choosing`, `rather than using`, `to avoid the`, `the alternative was`, `considered alternatives`, `the rationale is`, etc.) outside a sentence that also cites an `ADR-NNN`. Per audit-v2 D18, decision rationale belongs in ADRs, with AE citing the ADR.

Both run on these AE prose surfaces:
- `purpose_and_scope`
- each `responsibilities[]` entry
- `key_concepts` (legacy DN-era field; preserved on migrated AEs)
- `constraints_and_quality_notes`

DEPRECATED and TODO AEs are skipped.

The check splits prose into sentences (`(?<=[.!?])\s+(?=[A-Z(])`) and filters by per-sentence citation presence — so a sentence that contains both the trigger phrase AND its citation does not fire. False-positive rate is low: the dektora2 corpus surfaces 2 real D18 findings (AE-005's "The tradeoff is..." and AE-025's "rather than using..."), 0 D17 findings (the corpus was already cleaned during the dn-ae migration).

### Verified against dektora2

dektora2 audit went from 37 findings to 39: same 37 L/LX/T plus 2 new D18 findings.

### Added (5 new tests; 117 total passing, 14 skipped)

- `test_d_series_d18_rationale_real_dektora2` — confirms AE-005 + AE-025 surface.
- `test_d_series_d17_numeric_no_ws_cite_synthetic` — fake AE with `42 ms` + `100 req/s` triggers two D17 findings.
- `test_d_series_d17_skips_when_ws_cited` — `WS-039 §Latency targets pins this to 42 ms` does NOT fire.
- `test_d_series_d18_skips_when_adr_cited` — `Per ADR-044, we chose ...` does NOT fire.
- `test_d_series_skips_deprecated_artifacts` — DEPRECATED AEs produce 0 D-series findings.

[v0.14.0]: https://github.com/Dektora/dekspec/releases/tag/v0.14.0

## [v0.13.0] — 2026-05-11

Minor bump (additive). Persistence v0.2 — SQLite index for runs. The on-disk JSON + IRs format is unchanged; the SQLite index is a derived view that lets `dekspec runs ls` filter by date range, artifact id, exit code, milestone, and warning count without walking 200+ run directories.

### Added (`dekspec.constraint_compiler.persistence_index`)

- New module `persistence_index.py` (≈250 LOC).
- `INDEX_FILENAME = "index.db"` placed at `<repo-state-dir>/index.db` (the slot `persistence.py` reserved in v0.1).
- Schema versioned via `PRAGMA user_version` (currently 1):
  - `runs(run_id PK, timestamp, trigger, command, dekspec_version, artifact_count, emission_count, warnings, errors, exit_code, duration_ms, milestone, run_dir_name UNIQUE)` + indexes on `timestamp DESC`, `exit_code`, `milestone`.
  - `artifacts(run_id, artifact_id, kind, status, source_sha256, warnings, PRIMARY KEY (run_id, artifact_id))` + indexes on `artifact_id` and `kind`. `kind` is inferred from the artifact-id prefix (`adr`/`ae`/`ws`/`ic`/`ib`).
  - `emissions(run_id, emitter, artifact_id, output_path, output_size)` + index on `emitter`.
  - Foreign keys with `ON DELETE CASCADE` so deleting a run row cleans up its child rows.
- Public API: `open_index(state_dir)`, `init_schema(conn)`, `record_run(conn, run, run_dir_name)` (uses `INSERT OR REPLACE` so re-recording a run is idempotent), `query_runs(conn, **filters)`, `reindex(state_dir)`.

### Changed (`open_run` writes to the index)

- `persistence.open_run()` now calls `_record_in_index()` in its `finally` block alongside `flush_manifest`/`update_latest_symlink`/`update_lock_states`.
- The wrapper swallows any exception from the index path so a corrupt or read-only index never blocks the primary on-disk persistence. The index can always be rebuilt via `dekspec runs reindex`.
- `PERSISTENCE_VERSION` bumped from `"0.1.0"` to `"0.2.0"`.

### Changed (`dekspec runs ls` uses SQLite + new filters)

```
dekspec runs ls [-n N] [--at REPO]
                [--since ISO] [--until ISO]
                [--artifact ID] [--exit-code N]
                [--milestone] [--min-warnings N]
```

- Reads from `index.db` instead of walking run dirs and parsing manifests (≈100× faster on large run histories).
- New filters:
  - `--since <ISO>`: only runs at or after the timestamp.
  - `--until <ISO>`: only runs strictly before the timestamp.
  - `--artifact <ID>`: only runs that touched this artifact id (e.g., `AE-014`).
  - `--exit-code <N>`: only runs with this exit code (use `0` for clean, `2`+ for failures).
  - `--milestone`: only milestone runs (preserved-from-pruning).
  - `--min-warnings <N>`: only runs with at least N parse warnings.
- Backward compatible: with no filters, behaves exactly like v0.1's run-dir walk.
- If the index is empty, `ls` prints a helpful "run `dekspec runs reindex`" hint.

### Added (`dekspec runs reindex`)

```
dekspec runs reindex [--at REPO]
```

Drops the SQLite db and rebuilds it from the on-disk `manifest.json` files. Use after upgrading from v0.1, after manual JSON edits, or when the index gets corrupt. Walked the local dektora2 history during smoke-test: 20 manifests indexed in <100ms.

### Added (11 new tests; 112 total passing, 14 skipped)

`tests/test_persistence_index.py`:
- `test_open_index_creates_db_with_schema` — confirms tables + user_version=1.
- `test_record_run_inserts_run_artifacts_and_emissions` — round-trip a Run.
- `test_query_runs_filter_by_artifact_id` — artifact-id filter (the v0.2 headline feature).
- `test_query_runs_filter_by_exit_code_and_milestone` — exit_code + milestone filters.
- `test_query_runs_filter_by_since_and_until` — date-range filtering.
- `test_record_run_replaces_existing` — INSERT OR REPLACE idempotence; child rows wiped not duplicated.
- `test_reindex_rebuilds_from_disk` — read 3 fake manifests, confirm 3 rows.
- `test_cli_runs_ls_uses_sqlite_index` — end-to-end CLI smoke (writes manifest, reindexes, ls finds it).
- `test_open_run_records_into_index` — confirm the open_run lifecycle populates the index automatically.
- `test_kind_inferred_from_artifact_id_prefix` — all 5 prefixes resolve to the right kind enum.
- `test_record_in_index_swallows_errors` — corrupt + read-only index path doesn't break persistence.

CI sim (no dektora2 fixture): 23 passing (was 12 before this round).

[v0.13.0]: https://github.com/Dektora/dekspec/releases/tag/v0.13.0

## [v0.12.0] — 2026-05-11

Minor bump (additive). T-series structural-completeness audit rules — content-presence checks complementing the L-series linkage checks.

### Added (T-series)

`_t_artifact_completeness` runs after the L-series and surfaces structural-content gaps that the schema doesn't enforce:

- **T11-AE-BOUNDARY** (important): boundaries_and_non_goals must contain ≥1 inside item AND ≥1 non-goal with a `— ` why clause.
- **T12-AE-VIEWS** (minor): for AE subtypes that need views (System / Subsystem / Container / Pipeline / Platform Concern), the Views section must contain a diagram or an explicit absence justification.
- **T-AE-PURPOSE** (minor): purpose_and_scope content present.
- **T-AE-RESPONSIBILITIES** (minor): at least one responsibility entry.
- **T20-WS-BUSINESS-RULES** (important): at least one business rule.
- **T21-WS-FAILURE-BEHAVIOR** (important): at least one failure-behavior entry.
- **T30-ADR-DECISION** (critical): §Decision section content.
- **T31-ADR-VALIDATION** (minor): §Validation content (raw_prose form OK for grandfathered ADRs).
- **T40-IB-GOAL** (important): §Goal content.
- **T41-IB-DONE-WHEN** (important): at least one Done When criterion.

DEPRECATED artifacts are skipped for non-critical T-checks; SUPERSEDED ADRs are skipped for T30/T31.

(T10-AE-SUBTYPE was already enforced via schema validation; not duplicated as an audit finding.)

### Verified against dektora2

dektora2 audit went from 16 findings to 37: same 16 L-series + LX findings plus 21 new T-series findings:
- 16 T11-AE-BOUNDARY (most AEs have non-goals without `— why` clauses).
- 1 T12-AE-VIEWS (AE missing the structural view + no absence justification).
- 1 T-AE-RESPONSIBILITIES + 1 T-AE-PURPOSE.
- 1 T20-WS-BUSINESS-RULES + 1 T21-WS-FAILURE-BEHAVIOR.

These are real backfill items for the dektora2 maintainer; the dekspec library is just surfacing them now.

### Added (4 new tests; 101 total passing, 14 skipped)

- `test_t_series_t11_ae_boundary_real_dektora2` — confirms AE-002 (and others) flag T11.
- `test_t_series_t30_adr_decision_required` — fake graph with a decision-less ADR.
- `test_t_series_skips_deprecated_artifacts` — DEPRECATED across AE/WS/ADR/IB → 0 findings.
- `test_t_series_t40_ib_goal_and_t41_done_when` — fake IB missing both fields produces both findings.

[v0.12.0]: https://github.com/Dektora/dekspec/releases/tag/v0.12.0

## [v0.11.0] — 2026-05-11

Minor bump (additive). IB AGENTS.md fragment emitter — closes the agents-md emitter loop for all five artifact types — plus IB-aware duplicate detection.

### Added (`emit_ib`)

- `dekspec.constraint_compiler.emitters.agents_md.emit_ib(ir)` — per-IB AGENTS.md fragment.
- Fragment shape: status + parent WS + Source AEs + Depends on + Production gate + Goal + Files to modify (capped at 12) + Do NOT touch + Governing ADRs + Done When (capped at 8). All wrapped in the canonical `<!-- BEGIN/END dekspec-fragment: <id> -->` markers.
- Dispatch: `emit(ir)` now routes IB-NNN ids to `emit_ib`; previously raised `ValueError`.

### Added (aggregator includes IBs)

- `dekspec aggregate agents-md`'s `--include` default expanded from `AE,ADR,WS` to `AE,ADR,WS,IB`.
- New `# Implementation Briefs` section appears after `# Working Specs` with a one-paragraph framing about per-task scope authorization.
- Header summary line now reports IB count alongside the others.

### Changed (`dekspec compile --emit agents-md` accepts IBs)

- Previously rejected IBs ("no agents-md emitter for IB yet"); now produces a per-IB fragment using `emit_ib`. IC remains the only artifact kind that doesn't have an agents-md emitter (ICs use `--emit contract-test` or `--emit ci-gate`).

### Added (LX-DUP catches IB duplicates)

- `_lx_duplicate_ids` now walks `dekspec/impl-briefs/` recursively (the only artifact directory that recurses across queued/active/completed). IB IDs that appear in more than one lifecycle directory now produce LX-DUP findings.
- Surfaced 6 real IB-ID duplicates in dektora2: IB-001 through IB-006 each have copies in both `queued/` and `completed/`. Without this, the SpecGraph silently dropped 22 of the 32 IB files (last-loaded-wins).
- `_lx_duplicate_ids` also now uses `graph.dekspec_dir` (the actual loaded path) instead of hardcoding `docs/dekspec`. Respects `--dekspec-root` correctly.

### Changed (`SpecGraph.dekspec_dir` field)

- New `dekspec_dir: Path | None` field on `SpecGraph`, set by `SpecGraph.load`. Lets downstream code (audits, emitters) know which dekspec content tree the graph was loaded from without needing to re-derive it from `repo_root + dekspec_root`.

### Added (3 new tests; 97 total passing, 14 skipped)

- `tests/test_emitter_agents_md.py::test_emit_ib_includes_delimiters_spec_and_files` — fragment shape verification.
- `tests/test_emitter_agents_md.py::test_emit_dispatches_by_id_prefix` — extended to cover the IB dispatch case.
- `tests/test_aggregate_agents_md.py::test_aggregate_include_ib_section_present` — IB section appears by default.
- `tests/test_aggregate_agents_md.py::test_aggregate_include_only_ib` — `--include IB` produces an IB-only AGENTS.md.
- Updated `test_audit_linkage_includes_lx_dup_for_dektora2` to assert both 3 IC dups and 6 IB dups.

[v0.11.0]: https://github.com/Dektora/dekspec/releases/tag/v0.11.0

## [v0.10.0] — 2026-05-11

Minor bump (additive). Fifth artifact-type IR — Implementation Brief (IB) — completes the constraint-compiler graph end-to-end (ADR/AE/IB/IC/WS).

### Added (IB IR)

- `dekspec/schemas/implementation-brief.schema.yaml` — JSON Schema Draft 2020-12.
  Captures IB structure: `id`, `name`, `status` (8 valid: TODO/DRAFT/PROPOSED/ACCEPTED/LOCKED/QUEUED/ACTIVE/COMPLETED), `source` (path/sha256/parser_version/parsed_at), `spec` (parent WS), `intent` (parent INT), `source_aes` (canonical L5 IB→AE link per template post-v5), `depends_on` (other IBs), `production_gate`, `goal`, `out_of_scope`, `governing_adrs`, `files_to_modify`, `do_not_touch`, `done_when`, `open_issues`, `parse_warnings`.

- `dekspec.constraint_compiler.parser.parse_ib(path)` — produces a validated IR.
  Lossy by design (missing fields surface as `parse_warnings`); same convention as the four existing parsers. Smoke-tested against all 32 dektora2 IBs — every one parses without raising.

- `dekspec.constraint_compiler.IBParseError` — exposed alongside the other parse-error classes.

- `SpecGraph.ibs()` + `SpecGraph.aes_of_ib(ib_id)` — graph integration.
  - Loader recurses into `dekspec/impl-briefs/{queued,active,completed}/` (the only artifact directory that recurses).
  - `aes_of_ib` returns IB.source_aes if present, otherwise transitive via spec.id → WS.related_architecture_elements.

### Changed (`dekspec compile` accepts IB)

- New `--detect-artifact-kind` branch for `IB-NNN-*.md` filenames; `--emit ir` works on IBs.
- `--emit contract-test` / `--emit ci-gate` correctly reject IBs (those are IC-only emitters).
- `--emit agents-md` correctly rejects IBs (no IB-fragment emitter yet — planned follow-up).

### Changed (L5 audit upgraded from regex to graph-based)

The v0.6.0 L5 family was a regex-only sketch (no IB IR available at the time). v0.10.0 rewrites L5 around `graph.ibs()`:

- `L5-IB-SPEC-MISSING` (important): IB has no `**Spec:**` line.
- `L5-IB-WS-EXISTS` (critical): spec.id not in registry.
- `L5-IB-AE-EXISTS` (critical, new): each IB.source_aes ID must resolve to an existing AE.
- `L5-IB-AE-MISSING` (minor): no source_aes AND parent WS has no related_architecture_elements.
- `L5-IB-DEPENDS-EXISTS` (critical, new): each depends_on IB must resolve.

Removed `L5-IB-SPEC-PARSE` (subsumed by parser-level rejection — IBs whose Spec line can't yield a WS-NNN now produce `parse_warnings`, surfaced via `LX-PARSE`).

dektora2 audit unchanged: still 10 findings (3 LX-DUP, 2 L4-IC-AE-MISSING, 3 L6-BACKLINK on AE-039, 2 L7-ADR-SUPER-MIRROR), 0 L5.

### Added (8 new tests; 94 total passing, 14 skipped)

`tests/test_parser_ib.py`:
- `test_parse_ib_001_succeeds`
- `test_parse_ib_extracts_spec_with_ws_id`
- `test_parse_ib_extracts_metadata_fields`
- `test_parse_ib_extracts_files_to_modify`
- `test_parse_ib_all_dektora2_ibs_parse` — bulk parse of all 32 dektora2 IBs.
- `test_parse_ib_bad_filename_raises`
- `test_parse_ib_extracts_source_aes_when_present` — synthesized IB with `**Source AEs:** AE-005, AE-007` confirms canonical L5 source extraction.
- `test_parse_ib_status_values` — all 8 valid statuses parse.

Also rewrote `test_l5_ib_ws_missing_detected` to use the new graph-based L5 (FakeGraph has `ibs()` instead of file-system regex scan).

[v0.10.0]: https://github.com/Dektora/dekspec/releases/tag/v0.10.0

## [v0.9.0] — 2026-05-11

Minor bump (additive). First-class GitHub Actions CI for the dekspec library itself + dynamic version metadata + pytest auto-skip for fixture-bound tests.

### Added (CI)

- `.github/workflows/ci.yml` — runs on every push to `main` and every PR.
  - Matrix: Python 3.11, 3.12, 3.13.
  - Caches pip via `actions/setup-python@v5` keyed on `pyproject.toml`.
  - Lint step: `ruff check tooling tests`.
  - Test step: full `pytest -q` — fixture-bound tests auto-skip in CI via the new `tests/conftest.py`.
  - Concurrency: `ci-${{ github.ref }}` with `cancel-in-progress: true` so newer pushes preempt older runs.

### Added (`tests/conftest.py` — fixture auto-skip)

- `pytest_collection_modifyitems` hook scans each test source for the canonical fixture path string `/data/projects/dektora2`. If the fixture directory isn't present (CI case), every test in those files is auto-skipped with a clear reason.
- Override path via `DEKSPEC_DEKTORA2_FIXTURE` env var for testing the skip path locally.
- Local dev (fixture present): 86 passing, 14 skipped (PoC stubs).
- CI sim (fixture absent): 12 passing, 88 skipped — pure-library tests still cover the constraint compiler, vendoring drift detection, and CLI smoke against tmp_path.

### Fixed (pyproject version drift)

- `pyproject.toml` previously hardcoded `version = "0.5.0"` while `dekspec.__version__` was `0.8.0` — installed wheel reported the wrong version.
- Switched to `dynamic = ["version"]` + `[tool.setuptools.dynamic] version = { attr = "dekspec.__version__" }`. The single source of truth is now `tooling/dekspec/__init__.py`; pyproject reads from it at build time.
- Added `Programming Language :: Python :: 3.13` classifier (was missing).

### Changed (ruff)

- Removed 18 `F541` (f-string without placeholders) lint findings across `tooling/dekspec/vendoring.py`, `tooling/dekspec/fidelity_audit/linkage.py`, and three test files via `ruff check --fix`. No behavior change; converts redundant f-strings to plain strings.
- `tools/test_aggregate_agents_md.py` and `tests/test_vendoring.py` had unused imports removed by ruff.

[v0.9.0]: https://github.com/Dektora/dekspec/releases/tag/v0.9.0

## [v0.8.0] — 2026-05-11

Minor bump (additive). New `dekspec verify-vendored` CLI subcommand + companion `dekspec.vendoring` module.

### Added (`dekspec verify-vendored`)

```
dekspec verify-vendored [--at REPO_PATH] [--json]
```

Walks the canonical vendoring manifest defined in `dekspec.vendoring.iter_vendored_pairs` (skills, templates, methodology docs — mirroring `scripts/install-dekspec.sh`) and reports four kinds of drift:

- **modified** — file exists in both places but sha256 mismatches.
- **missing** — library publishes the file but the consumer doesn't have it (incomplete install or partial vendor).
- **unknown** — consumer has a file under `.claude/skills/` or `dekspec/templates/` that the current library manifest doesn't ship (previous version vendored a now-retired file).
- **version** — `.dekspec-version` marker absent or doesn't match the installed library version.

Exit code is 0 when the consumer's vendored content is fully in sync with the library, 1 when any drift is detected. JSON mode emits the findings as an array for scripting.

Smoke-tested against dektora2 (which is pre-marker, pre-v0.4.x layout): 43 findings (1 version, 18 modified, 16 missing, 8 unknown) — exactly the expected drift for a repo that hasn't been re-vendored since v0.3.x.

### Added (`dekspec.vendoring` module)

- `library_root()` — returns the dekspec library source root (parent of `tooling/`), so the CLI can find the source-of-truth files regardless of where it's invoked from.
- `iter_vendored_pairs(lib_root, repo_root)` — yields `(library_source_path, consumer_destination_path)` for every file the install script vendors. Walks `skills/`, `templates/`, and the cherry-picked methodology docs (`dekspec-operating-guide.md`, `dekspec-quick-reference.md`, `architecture-frameworks-reference.md`, `architecture.md`). Public API for any tooling that needs to know the manifest.
- `compute_drift(repo_root)` — returns a list of `DriftFinding` objects.
- `DriftFinding` dataclass — `kind`, `library_path`, `consumer_path`, `detail`, `to_dict()`.

### Changed (install-dekspec.sh default version)

- `DEKSPEC_VERSION` default bumped from 0.5.0 to 0.7.0 (now 0.8.0 with this bump). Consumers running the bare install script without an env override now pull the current major-feature line.

### Added (10 new tests; 86 total passing, 14 skipped)

`tests/test_vendoring.py`:
- `test_library_root_resolves_to_repo_root`
- `test_iter_vendored_pairs_yields_known_categories`
- `test_compute_drift_empty_repo_reports_all_missing`
- `test_compute_drift_perfect_install_reports_no_drift`
- `test_compute_drift_modified_file_detected`
- `test_compute_drift_unknown_file_detected`
- `test_compute_drift_version_mismatch_detected`
- `test_cli_verify_vendored_clean_repo_returns_zero`
- `test_cli_verify_vendored_drift_returns_one_with_table`
- `test_cli_verify_vendored_json_mode`

[v0.8.0]: https://github.com/Dektora/dekspec/releases/tag/v0.8.0

## [v0.7.0] — 2026-05-11

Minor bump (additive). New top-level CLI subcommand `dekspec aggregate agents-md` — the keystone library feature that the per-artifact `agents_md` emitters were always meant to feed.

### Added (`dekspec aggregate agents-md`)

```
dekspec aggregate agents-md [--at REPO_PATH] [--dekspec-root DEKSPEC_ROOT]
                            [--output PATH] [--status STATUS,STATUS,...]
                            [--include AE,ADR,WS]
```

Walks the SpecGraph and writes a project-wide `AGENTS.md` at repo root (default) by aggregating per-artifact fragments from `constraint_compiler.emitters.agents_md`. Output structure:
- Header HTML comment (auto-gen note + status filter + included kinds + UTC timestamp + library version + DO-NOT-EDIT warning).
- `# AGENTS.md` H1 with summary count.
- `# Architecture Elements` section with one fragment per AE.
- `# Architecture Decision Records` section with one fragment per ADR.
- `# Working Specs` section with one fragment per WS.

Each fragment is wrapped with `<!-- BEGIN/END dekspec-fragment: <id> -->` markers so consumers can replace fragments programmatically.

Defaults:
- Status filter: `LOCKED,ACCEPTED` (use `--status all` to include DRAFT/PROPOSED/etc).
- Included kinds: `AE,ADR,WS` (use `--include AE` for AE-only, etc).
- Output: `<repo_root>/AGENTS.md` (use `--output -` for stdout).

Smoke-tested against dektora2 (39 AE + 59 ADR + 45 WS = 143 artifacts; default LOCKED+ACCEPTED filter yields a 16 KB AGENTS.md with 1 AE + 3 ADR + 2 WS — all that is currently fully locked in dektora2's PROPOSED-dominated corpus).

### Added (7 new tests; 76 total passing, 14 skipped)

`tests/test_aggregate_agents_md.py`:
- `test_aggregate_writes_to_default_path`
- `test_aggregate_default_status_filter_is_locked_accepted`
- `test_aggregate_status_all_includes_proposed`
- `test_aggregate_include_only_ae`
- `test_aggregate_unknown_include_kind_errors`
- `test_aggregate_stdout_output`
- `test_aggregate_stable_fragment_delimiters` — every BEGIN matches an END for the same id, no duplicates.

[v0.7.0]: https://github.com/Dektora/dekspec/releases/tag/v0.7.0

## [v0.6.0] — 2026-05-11

Minor bump (additive). Two new audit rule families (L5, L7) + a small `--fix` capability extension.

### Added (L5 IB→WS basic check)

- `_l5_ib_ws_links()` walks `docs/dekspec/impl-briefs/{queued,active,completed}/IB-*.md`, parses each IB's `**Spec:**` line via regex (no IB IR yet — that's planned for the IB IR landing), and emits findings for:
  - `L5-IB-SPEC-MISSING` (important): no `**Spec:**` line present.
  - `L5-IB-SPEC-PARSE` (important): line exists but contains no recognizable `WS-NNN`.
  - `L5-IB-WS-EXISTS` (critical): IB's parent WS is not in the registry.
  - `L5-IB-AE-TRANSITIVE` (minor): parent WS exists but has no Related Architecture Elements, so the IB cannot resolve any AE transitively.
- All 32 dektora2 IBs pass the L5 check after the v0.6.0 dektora2 doc backfills (see "Verified against dektora2" below).

### Added (L7 ADR supersession integrity)

- `_l7_adr_supersession_integrity()` validates `ADR.supersession` references with five sub-rules:
  - `L7-ADR-SUPER-EXISTS` (critical): every supersedes/superseded_by ID resolves.
  - `L7-ADR-SUPER-SELF` (critical): no ADR can supersede itself.
  - `L7-ADR-SUPER-MIRROR` (important): if A.supersedes contains B, B.superseded_by must contain A.
  - `L7-ADR-SUPER-CYCLE` (critical): the supersedes graph must be acyclic (DFS-based detection; deduped by node-set).
  - `L7-ADR-SUPER-STATUS` (important): ADRs with `status=SUPERSEDED` must populate `supersession.superseded_by`.
- Caught 2 real mirror-violation findings against dektora2 (ADR-009 missing back-pointer to ADR-039; ADR-014 missing back-pointer to ADR-055).

### Changed (`propose_l6_fixes` handles markdown-link form)

- `_build_l6_line_edit` now appends missing IDs in plain form even when the existing `Related <Kind>:` line uses the `[ID](path) — Title` markdown-link decoration (previously the function returned None and skipped those lines). Original markdown links are preserved; appended IDs use plain comma form for parser compatibility — re-decoration happens at next `/write-ae --revise`.
- Defensive change — no AE files in dektora2 currently use markdown-link form for backlinks, so this affects 0 outstanding fixes today. New test (`test_propose_fixes_handles_markdown_link_form`) confirms the behavior.

### Added (5 new tests; 69 total)

- `tests/test_linkage.py`:
  - `test_propose_fixes_handles_markdown_link_form` — verifies the L6 fixer no longer skips markdown-link form.
  - `test_l5_ib_ws_exists_real_dektora2` — sanity check that all 32 dektora2 IBs reference existing WSes.
  - `test_l5_ib_ws_missing_detected` — fake-graph fixture confirming L5-IB-WS-EXISTS triggers when the parent WS is absent.
  - `test_l7_supersession_self_loop_detected` — minimal fake-graph confirms L7-ADR-SUPER-SELF.
  - `test_l7_supersession_cycle_detected` — A↔B cycle confirms L7-ADR-SUPER-CYCLE.
  - `test_l7_supersession_mirror_real_dektora2` — verifies the 2 real ADR-009 / ADR-014 mirror violations surface.

### Changed (test fixture)

- `tests/test_graph.py::test_implements_globs_for_unions_across_aes` — was a sentinel asserting "no AE has implements_globs yet". Updated for the AE-014 backfill: now asserts `services/config.py`, `services/track_timeline.py`, and `services/score_hierarchy.py` resolve through IC-007.

### Verified against dektora2

Companion dektora2 doc backfills applied via the v0.6.0 audit + fix tooling (uncommitted in dektora2 working tree, pending dektora2 maintainer commit):

- **AE-014** received its first `## Implements` section (3 globs, 1 AE) — first dektora2 AE to populate `implements_globs`.
- **13 ADRs backfilled** with `## Related Architecture Elements`: ADR-000, 025, 043, 044, 048, 050, 052, 053, 054, 055, 056, 057, 058. Mapping derived from §Decision + §Context analysis. Cleared all 13 `L1-ADR-AE-MISSING` findings.
- **8 WSes backfilled** with parser-friendly bullet form in `## Related Architecture Elements` (preserving the original prose where present): WS-030, 031, 032, 037, 042, 043, 044, 045. Cleared all 8 `L3-WS-AE-MISSING` findings.
- **14 AE backlink mechanical fixes auto-applied** (11 from the ADR backfill cascade + 3 from the WS backfill cascade) via `dekspec audit linkage --fix --apply`.
- Total dektora2 findings: 24 → 10. Remaining 10 are: 3 LX-DUP (IC-001/002/005 duplicates needing semantic renumbering), 2 L4-IC-AE-MISSING (downstream of the duplicates), 3 L6-BACKLINK on AE-039 (predates `## Linked Artifacts` convention — needs structural cleanup), 2 L7-ADR-SUPER-MIRROR (mechanical back-pointer additions).

[v0.6.0]: https://github.com/Dektora/dekspec/releases/tag/v0.6.0

## [v0.5.0] — 2026-05-11

Minor bump (additive). Two cross-cutting capabilities + a defensive test sweep + a real parser bug uncovered along the way.

### Added (audit linkage --fix mode)

- `dekspec audit linkage --fix` now computes mechanical fix proposals and prints before/after diffs (default dry-run). `--fix --apply` actually writes the changes.
- v0.5.0 first cut handles `L6-BACKLINK` only — when an AE is referenced by ADR/WS/IC-Y but doesn't list Y back in `linked_artifacts.related_<kind>s`, the fixer appends Y to the appropriate line. Either replaces a `none` / `none referenced in body` value, or appends to an existing comma-separated list.
- New `Fix` dataclass (severity-style sibling of `Finding`) carries `rule`, `artifact_id`, `file_path`, `section`, `added_ids`, `before`, `after`, `line_number`. Per-file fixes are batched into a single read-modify-write pass.
- Skips markdown-link-form `Linked Artifacts` lines (used by ADRs that list AEs as `[AE-NNN](path) — Title`); those need a v0.5.x extension. Skips lines whose `before` text isn't found in the file (e.g., file edited between propose and apply).
- Surfaced 20 legitimate L6 fixes against dektora2 — replaces the v0.4.x `L6-BACKLINK` advisory load.

### Fixed (parser bug uncovered while building --fix)

- **`parser._extract_linked_artifacts` was silently dropping `Related WSs:` lines** in AE files because `m.group("kind").upper().rstrip("S")` turned `"WSs"` → `"WSS"` → `"W"` (rstrip strips ALL trailing S, not one). The dropped section caused 20 phantom `L6-BACKLINK` findings against dektora2 that the audit kept flagging despite the AE files literally containing the right backlink. Total dektora2 findings dropped 83 → 63 after the parser fix.
- Replaced the `rstrip("S")` heuristic with an explicit `kind_normalize` map that handles both singular and plural forms (`ADR`/`ADRS`, `WS`/`WSS`, etc.) deterministically.
- Pre-existing bug since v0.2.1; affected any AE whose `Related WSs:` line was populated. 35/39 dektora2 AEs now correctly extract `related_wss`.

### Added (defensive tests for v0.3.x/v0.4.x modules)

- `tests/test_parser_ae.py` (6 tests) — AE-014 fixture; confirms subtype slug, former_dn, linked_artifacts (regression test for the rstrip bug), bad-filename rejection.
- `tests/test_parser_ws.py` (7 tests) — WS-016 fixture; confirms related AE linkage, business rules with domain tags, failure behavior table, conditional contracts, expertise audit normalization.
- `tests/test_parser_adr.py` (7 tests) — ADR-022 fixture; confirms 3-date model, markdown-link AE refs, options considered, consequences split, grandfathered Validation prose.
- `tests/test_graph.py` (10 tests) — SpecGraph load + queries (`by_id, has, consumers_of_ae, aes_of_adr, aes_of_ws, aes_of_ic, implements_globs_for, parse_failures`); confirms IC AE refs read from `provider_ae + consumer_aes` post-v0.3.1.
- `tests/test_emitter_agents_md.py` (7 tests) — fragment shape per artifact kind, dispatch logic, IC rejection, suggested_filename, prose truncation.
- `tests/test_linkage.py` (8 tests) — audit returns findings + sorting + LX-DUP for dektora2; propose_fixes is L6-only in v0.5; no-duplicate-insert regression; dry_run does not modify files; isolated apply test.

**Total: 64 unit tests pass (was 20 before v0.5.0 sweep), 13 skipped (PoC stubs intentionally skip).**

### Verified against dektora2

- `dekspec audit linkage --at /data/projects/dektora2 --dekspec-root docs/dekspec` — 63 findings (was 83 before parser fix; phantom L6 findings cleared).
- `dekspec audit linkage --at /data/projects/dektora2 --dekspec-root docs/dekspec --fix` — 20 mechanical L6 fixes proposed, all clean (no false-add-existing).
- 35/39 AEs now correctly extract `related_wss` and `related_ics` (was minimal due to rstrip bug).

[v0.5.0]: https://github.com/Dektora/dekspec/releases/tag/v0.5.0

## [v0.4.1] — 2026-05-11

### Changed (filename casing convention codified + applied)

Codifies a single filename rule for DekSpec content and applies it across the library:

> **Inside `dekspec/`**: artifact files keep their UPPERCASE label prefix (`ADR-NNN-…`, `AE-NNN-…`, `WS-NNN-…`, `IC-NNN-…`, `IB-NNN-…`, `INT-NNN-…`, `MSN-NNN-…`, `CR-NNN-…`, `DIV-NNN-…`). Everything else is lowercase + hyphenated.

The exception allowlist (9 files) is documented in `dekspec/dekspec-operating-guide.md §Filename Conventions`. Within `dekspec/` itself, **no exceptions** — only the artifact-label prefix is UPPERCASE.

**Renames (library-side):**
- `docs/ARCHITECTURE.md` → `docs/architecture.md` (vendored as `dekspec/architecture.md` after install).
- `skills/function-planner/TEMPLATE.md` → `skills/function-planner/template.md` (the function-plan output starter scaffold).

**Reference sweep (library-side, ~40 hits across skills + templates + docs):**
- `Working-Spec-Index.md` → `working-spec-index.md`
- `Interface-Contract-Index.md` → `interface-contract-index.md`
- `ADR-Index.md` → `adr-index.md`
- `Intent-Index.md` → `intent-index.md`
- `Mission-Index.md` → `mission-index.md`
- `ARCHITECTURE.md` → `architecture.md`
- `TEMPLATE.md` → `template.md`

`install-dekspec.sh` vendor source path updated to use the renamed `docs/architecture.md`.

### Added (DIV-NNN divergence-file convention)

Per the artifact-label convention, divergence files now follow the `DIV-NNN-<slug>.md` pattern in `dekspec/divergences/` (was: ad-hoc numeric prefix like `001_skips_wireups.md`, OR consolidated `divergence-ledger-*.md` files at random locations under `docs/workspace/`).

**Reference sweep:**
- `dekspec/divergence-ledger-*.md` → `dekspec/divergences/DIV-NNN-*.md` (in templates: adr, working-spec, intent, architecture-element)
- `docs/workspace/archive/convergence/divergence-ledger-dektora.md` → `dekspec/divergences/DIV-NNN-*.md` (in adr, working-spec templates)
- Skills: `write-ae`, `run-dekspec-fidelity-audit-v2`, operating-guide all updated.

The migration prompt for consumers (dektora2, dekfactory) covers renaming existing divergence files to the new format.

### Added (filename-conventions section in the operating guide)

New `## Filename Conventions` section in `dekspec/dekspec-operating-guide.md` codifies the rule + the 9-item UPPERCASE exception allowlist + the rationale (greppable corpus, single rule with one labeled escape valve).

### Verified

- 20 unit tests still pass; no regressions.
- `dekspec audit linkage --at /data/projects/dektora2 --dekspec-root docs/dekspec` still surfaces 83 findings (legacy dektora2 layout is still parseable via the override flag).

### Migration prompt for consumers

A migration prompt for the dekfactory + dektora2 maintainers ships at:
`/data/projects/dekfactory/docs/workspace/dekfactory/prompts/dekspec-filename-casing-and-divergence-format-2026-05-11.md`.

Per the prompt, the consumer-side work is: rename Title-Case index files (`Working-Spec-Index.md` → `working-spec-index.md` etc.), rename existing `divergences/<num>_<slug>.md` to `DIV-NNN-<slug>.md`, lowercase any workspace closeouts that aren't artifact-labeled.

[v0.4.1]: https://github.com/Dektora/dekspec/releases/tag/v0.4.1

## [v0.4.0] — 2026-05-11

### Changed (BREAKING for consumers — root location moves to `dekspec/`)

DekSpec's content tree now lives at the consumer repo root as `dekspec/`, not under `docs/dekspec/`. The argument: DekSpec content is *spec, not documentation* — machine-consumable artifacts (IRs, schemas, indexes, ADRs/AEs/WSes/ICs that compile to enforcement). Putting them under `docs/` undersold what they were and invited confusion with doc-build pipelines (mkdocs/sphinx). Root `dekspec/` puts them in the right semantic neighborhood as `.beads/`, `.claude/`, `tooling/` — all top-level project state.

The library defaults all flip in this release. Consumers must `git mv docs/dekspec dekspec` (no other code change required for most uses — the parser walks paths relative to the source artifact, so internal cross-refs survive the move automatically).

**Library changes:**
- `install-dekspec.sh` vendor target: `docs/dekspec/templates/` → `dekspec/templates/`; methodology docs now land at `dekspec/{operating-guide,quick-reference,architecture-frameworks-reference,ARCHITECTURE}.md`.
- `SpecGraph.load(repo_root, dekspec_root='dekspec')` — default flipped from `docs/dekspec`.
- `dekspec audit linkage --dekspec-root` default flipped to `dekspec` (was `docs/dekspec`).
- `parser._infer_ae_dir()` — no code change; the function walks parent dirs relative to the source IC/WS path so it works for either layout automatically.

**Methodology / template / skill sweep:**
- 298 references swept in 37 files: README, CHANGELOG (new entries only), ARCHITECTURE.md, operating guide, quick reference, ecosystem-tools.md, all 18 vendored skills, and templates (architecture-element, working-spec, intent, implementation-brief).

**No breaking change to dekspec's library API** — `parse / parse_ae / parse_ws / parse_adr / resolve_aes / SpecGraph.load / audit_linkage / emit / contract_test / ci_gate / agents_md` signatures unchanged. The breaking change is purely the *default expected location* on the consumer's filesystem.

### Migration path for consumers (e.g., dektora2, dekfactory)

```bash
# In consumer repo:
git mv docs/dekspec dekspec
# Sweep any internal absolute-path refs (rare; usually relative paths just work):
grep -rn 'docs/dekspec' .
# Then re-vendor dekspec content:
bash scripts/install-dekspec.sh
```

Until a consumer migrates, override the library default at the call site:

```bash
dekspec audit linkage --at /path/to/consumer --dekspec-root docs/dekspec
```

A standalone migration prompt for the dekfactory maintainer ships alongside this release: `/data/projects/dekfactory/docs/workspace/dekfactory/prompts/dekspec-root-relocation-2026-05-11.md`.

### Excluded from the sweep (preserved as historical record or auto-regenerated)

- `CHANGELOG.md` — prior version entries preserved with their `docs/dekspec/` references intact (those are historical truth — what the library *did* in v0.2.x / v0.3.x).
- `tests/test_parser.py`, `tests/test_emitter_ci_gate.py`, `tests/test_emitter_contract_test.py` — fixture paths point at `/data/projects/dektora2/docs/dekspec/api-contracts/` which is the still-current dektora2 layout; updates when dektora2 migrates.
- `tests/poc/contracts/*.py`, `tests/poc/ic-007.gitlab-ci.yml` — auto-generated by emitters; will refresh on the next `dekspec compile` against a migrated source.

[v0.4.0]: https://github.com/Dektora/dekspec/releases/tag/v0.4.0

## [v0.3.1] — 2026-05-10

### Fixed (C1 — IC parser was missing post-DN→AE-migration AE refs)

The post-DN→AE-migration IC template (vendored 2026-04-27) puts AE refs in dedicated `### Provider AE` and `### Consumer AEs` H3 subsections nested inside `## Parties`. The v0.3.0 IC parser only looked for `AE-NNN` inline in party-bullet description text, so it found ae_ids on essentially zero real ICs in dektora2. This blocked the v0.3 IC→AE→implements_globs cross-artifact resolution from being functional.

Fix lands as a small additive schema change + parser extractor + graph integration:

- **Schema**: added `provider_ae` (string) and `consumer_aes` (array of unique AE-NNN strings) as optional top-level IC IR fields. The legacy `parties[].ae_id` remains as a fallback for ICs that haven't migrated to the H3-subsection form.
- **Parser**: new `_extract_party_ae_subsections(body)` walks H3 subsections inside `## Parties` for `### Provider AE` and `### Consumer AEs`, extracts the AE-NNN values into the new top-level fields.
- **Graph**: `SpecGraph.aes_of_ic(ic_id)` reads from `provider_ae + consumer_aes` first, falling back to `parties[].ae_id`. `consumers_of_ae(ae_id)` distinguishes the where_referenced source ('provider_ae' / 'consumer_aes' / 'parties[].ae_id').
- **resolve_aes()**: same extension — reads top-level fields first.

### Verified against dektora2

- 14/17 IC files now extract `provider_ae`; 13/17 extract `consumer_aes`. The 3 misses are early-stage IC-001/002/005 DRAFT/TODO versions (expected — those ICs predate the H3-subsection template).
- **`L4-IC-AE-MISSING` finding count: 12 → 2** (~83% reduction). The 2 remaining are duplicate-ID DRAFT files (related to C3, not C1).
- IC-007 (the keystone trace artifact): now extracts `provider_ae=AE-014, consumer_aes=[AE-001]` cleanly.
- Total `dekspec audit linkage` findings against dektora2: 73 → 83. The +10 is `L6-BACKLINK` correctly catching new IC→AE edges that AEs don't backlink — real signal, not a regression.

### Other issues from v0.3.0 still open (deferred)

- **C2** — No AE in dektora2 has `implements_globs` populated. The `## Implements` section needs to be authored per AE before `--resolve-aes` produces non-empty `affected_paths`. Content fix in dektora2.
- **C3** — 3 duplicate IC IDs in dektora2 (IC-001/002/005). Content fix in dektora2.
- **M1** — ADR fragment "Reconsider this decision if" still dumps the whole grandfathered Validation prose. Cosmetic.
- **M2** — No unit tests for v0.3.0/v0.3.1 modules (agents_md, graph, linkage, IC AE-subsection extractor). 20 existing tests still pass.

[v0.3.1]: https://github.com/Dektora/dekspec/releases/tag/v0.3.1

## [v0.3.0] — 2026-05-10

Minor bump — three additive capabilities on top of v0.2.3's complete artifact-type IR layer.

### Added (AGENTS.md fragment emitter)

- `tooling/dekspec/constraint_compiler/emitters/agents_md.py` — emits worker-context AGENTS.md fragments from AE / ADR / WS IRs. Three tuned shapes:
  - **AE fragment** — type, purpose excerpt, top-6 responsibilities, top-5 non-goals with rationale, `implements_globs` "when working in" pointer, cross-refs.
  - **ADR fragment** — status + decision date, decision excerpt, reconsideration triggers, `Shapes:` AE list. Notes superseded-by status when present.
  - **WS fragment** — status + AE backlink, mechanism sentence (or prose excerpt), top-10 business rules with domain tag, top-10 failure behaviors.
- Worker-context-budget aware: long prose excerpted at sentence boundaries to ~600 chars; lists capped at 5-10 items with overflow note.
- HTML comment delimiters (`<!-- BEGIN dekspec-fragment: <id> --> / <!-- END ... -->`) for programmatic aggregation/replacement.
- CLI: `dekspec compile <ae|adr|ws-path> --emit agents-md [--output PATH]`. ICs reject this emit (`--emit agents-md` is AE/ADR/WS-only).

### Added (SpecGraph — in-memory artifact-graph traversal)

- `tooling/dekspec/constraint_compiler/graph.py` — `SpecGraph` class. `SpecGraph.load(repo_root)` walks `docs/dekspec/{adrs,architecture-elements,working-specs,api-contracts}/` and parses every artifact via `parse / parse_ae / parse_ws / parse_adr`. Parse failures captured in `graph.failures` rather than raised.
- Cross-artifact queries:
  - `aes() / adrs() / wses() / ics()` — kind iterators
  - `by_id(artifact_id)` — single lookup
  - `consumers_of_ae(ae_id)` — every artifact that references this AE (via ADR/WS related_architecture_elements OR IC parties[].ae_id)
  - `aes_of_adr / aes_of_ws / aes_of_ic` — extract referenced AE-NNNs from a given artifact
  - `implements_globs_for(artifact_id)` — derives the union of `implements_globs` across referenced AEs (used by IC/WS gate scoping)
- Smoke test against dektora2: 59 ADRs + 39 AEs + 45 WSes + 14 ICs loaded (note: 17 IC files but 3 IDs collide → 14 unique IDs; LX-DUP finding surfaces this).

### Added (Fidelity audit Python implementation — first cut)

- `tooling/dekspec/fidelity_audit/linkage.py` — first Python implementation of the v2 skill's L-series cross-artifact consistency checks. Produces `Finding` objects with severity / rule code / artifact_id / message / fix_kind.
- Rules implemented (v0.3.0 first cut):
  - `LX-PARSE` (critical) — surfaces parse failures captured during `SpecGraph.load()`.
  - `LX-DUP` (critical) — duplicate artifact IDs in the same dir (silent overwrite during graph load).
  - `L1-ADR-AE-EXISTS` (critical) / `L1-ADR-AE-MISSING` (minor — grandfathered).
  - `L3-WS-AE-EXISTS` (critical) / `L3-WS-AE-MISSING` (important — required at LOCK).
  - `L4-IC-AE-EXISTS` (critical) / `L4-IC-AE-MISSING` (minor).
  - `L6-BACKLINK` (minor — backlinks lag during cascade by design).
- CLI: `dekspec audit linkage [--at PATH] [--dekspec-root REL] [--severity critical|important|minor|all] [--json]`. Exit code 1 if any critical findings.
- Surfaced 73 findings against dektora2 on first run (3 critical / 8 important / 62 minor) — real signal about where the spec graph has gaps.

### Other check families deferred

- **T-series** (template completeness, audit T1-T12) — remains in `/run-dekspec-fidelity-audit-v2` skill until v0.3.x.
- **D-series** (drift / D17-D18 measurable-targets-in-AE / decision-rationale-in-AE) — same.
- **E-series** (extraction-landing post-convergence) — same.
- **2H** (glossary consistency) — domain-glossary IR not yet shipped.

### Known issues surfaced during v0.3.0 development

See "Known issues" section below the changelog or run `dekspec audit linkage --at <consumer-repo>` for the live picture in your repo.

[v0.3.0]: https://github.com/Dektora/dekspec/releases/tag/v0.3.0

## [v0.2.3] — 2026-05-10

### Added (ADR IR — fourth and final v0.2-roadmap artifact-type IR)

Completes the 4-artifact spec graph (IC + AE + WS + ADR). All four artifact types in dektora2's corpus now parse end-to-end with 0 warnings:
- 17/17 ICs (v0.2.0)
- 39/39 AEs (v0.2.1)
- 45/45 WSes (v0.2.2)
- **59/59 ADRs (v0.2.3)** — including the SUPERSEDED case and grandfathered Validation prose form

- `tooling/dekspec/schemas/adr.schema.yaml` — per-ADR IR schema (Draft 2020-12). 20 top-level fields. Required: `id (ADR-NNN), name (verb-first), status, source`. Status enum includes the ADR-specific `SUPERSEDED` terminal state. `supersession` carries opaque `supersedes` / `superseded_by` ADR-NNN ref lists. Three date fields: `created` (ADR document write date), `modified` (last revision), `date` (when the decision was made — may predate document creation). `validation` accepts both the post-2026-04-24 split structure (`observable_confirmation` + `reconsideration_triggers`) AND the grandfathered `raw_prose` form for older ADRs. No `affected_paths` field — per the playbook, ADRs feed AGENTS.md fragments + structural lint rules, not per-file CI gate scoping.
- `tooling/dekspec/constraint_compiler/parser.parse_adr(path)` — markdown → ADR IR. Reuses existing helpers (`_split_sections, _extract_table, _extract_bullets, _extract_first_date, _extract_open_issues, _split_h3, _extract_related_aes_ws`). Adds ADR-specific `_extract_supersession` (italic `*Supersedes:* / *Superseded by:*` line parsing), `_extract_context_and_decision_drivers` (context prose + Decision drivers bullets + Technical story link), `_extract_options_considered` (H3-per-option with `**Pros:** / **Cons:**` lines), `_extract_consequences` (Positive/Negative bullet blocks), `_extract_validation` (split structure with grandfathered-prose fallback).
- `_AE_REF_BULLET` regex generalized to handle the markdown link form (`[AE-NNN](path) — desc`) used in ADR `Related Architecture Elements` sections, alongside the existing `AE-NNN: Title — desc` plain form used by WSes.
- CLI: filename detection extended to `ADR-NNN-*.md`. ADRs only support `--emit ir` (no ADR-specific emitters yet); `--emit contract-test|ci-gate` returns exit 2.

### Roadmap completion status

The v0.2.0 PoC's stated v0.2/0.3 roadmap items "AE registry IR + WS IR + ADR IR (light)" are now all shipped:
- ✅ IC IR (v0.2.0) — keystone proof, contract_test + ci_gate emitters, 17 ICs validated
- ✅ AE IR (v0.2.1) — implements_globs cross-artifact resolution, 39 AEs validated
- ✅ WS IR (v0.2.2) — extended resolve_aes() to WS shape, 45 WSes validated
- ✅ ADR IR (v0.2.3) — supersession links, grandfathered Validation prose, 59 ADRs validated

### Deferred to v0.3.0+

- **Emitters per artifact type** — AGENTS.md fragments (from ADR + WS + AE), structural lint rules (from ADR), acceptance-criteria contract tests (from WS).
- **Fidelity audit Python implementation** — current `/run-dekspec-fidelity-audit` skill operates on artifact files directly; v0.3 ports to a Python backend that consumes the IRs.
- **AE registry full graph traversal** — currently `resolve_aes()` looks up one AE per IC/WS reference; v0.3 builds the full graph at session start for queries like "show all WSes implementing AE-014" or "all ADRs governing AE-014".

[v0.2.3]: https://github.com/Dektora/dekspec/releases/tag/v0.2.3

## [v0.2.2] — 2026-05-10

### Added (Working Spec IR — third artifact-type IR)

- `tooling/dekspec/schemas/working-spec.schema.yaml` — per-WS IR schema (Draft 2020-12). 27 top-level fields, 4 conditional contract sections (`model_behavior, graph_behavior, timeline_behavior, quantization`). Includes the new 3-tier severity for `open_issues` (`blocking_pre_ib, blocking_pre_code, non_blocking`) and `role` enum (`regular, refactoring-ws`) for the conditional Refactor Targets section. Captures L3 linkage via `related_architecture_elements`.
- `tooling/dekspec/constraint_compiler/parser.parse_ws(path)` — markdown → WS IR. Reuses IC parser helpers (`_split_sections`, `_extract_table`, `_extract_governing_adrs`, `_extract_domains`); adds WS-specific `_extract_expertise_audit`, `_extract_related_aes_ws`, `_extract_what_this_does` (with Mechanism: extraction), `_extract_business_rules` (numbered + domain-tagged), `_extract_open_issues_ws` (3-tier severity + skip-resolved-checkboxes), `_extract_ws_contracts` (4 conditional sections via field-label regex). **Tested across all 45 WSes in dektora2: 45/45 parse with 0 warnings, 0 failures.**
- CLI: filename detection extended to `WS-NNN-*.md`. `dekspec compile <ws-path> --emit ir` works. WSes only support `--emit ir` (no WS-specific emitters yet); `--emit contract-test|ci-gate` returns exit 2.
- `resolve_aes()` extended to handle WS IRs (reads `related_architecture_elements[].id` instead of `parties[].ae_id`). Same auto-infer-from-source-path convention. WSes can now derive `affected_paths` from their AE refs the same way ICs do.

### Changed

- `resolve_aes(ic_ir, ae_dir)` first parameter renamed `ic_ir → ir` in the function body to reflect that it now accepts both IC and WS IRs. External signature unchanged at the keyword level — `resolve_aes(ir)` continues to work as before.

### Deferred

- WS-specific emitters (AGENTS.md skill fragment, acceptance-criteria contract tests). v0.4 work per the v0.2.0 roadmap.
- ADR IR + parser (the 4th artifact-type IR — last in the v0.2.0 roadmap before fidelity audit Python implementation).
- Fidelity audit Python implementation (current `/run-dekspec-fidelity-audit` skill operates on artifact files directly).

[v0.2.2]: https://github.com/Dektora/dekspec/releases/tag/v0.2.2

## [v0.2.1] — 2026-05-10

### Added (Architecture Element IR — first cross-artifact resolution layer)

- `tooling/dekspec/schemas/architecture-element.schema.yaml` — per-AE IR schema (Draft 2020-12). Required: `id, name, status, subtype, source`. Subtype is snake_case slug from the C4-aligned 10-enum (`system, subsystem, container, component, pipeline, data_model, cross_cutting_concern, platform_concern, interface_surface, workflow_process`). Status includes `DEPRECATED`. Carries optional legacy DN-era fields (`key_concepts, what_success_looks_like`) so migrated AEs validate without rewrite.
- `templates/architecture-element-template.md` — new `## Implements` section between Linked Artifacts and Purpose and Scope. Holds file globs (relative to consumer repo root) that this AE is implemented by. Optional at DRAFT, expected at PROPOSED+.
- `tooling/dekspec/constraint_compiler/parser.parse_ae(path)` — markdown → AE IR. Mirrors IC parser's lossy-by-design contract. Tested across all 39 AEs in dektora2: 36/39 parse with 0 warnings; 3 (DEPRECATED Container AEs) have a single warning each because they declare `Container (DEPRECATED)` as Subtype rather than Status.
- `tooling/dekspec/constraint_compiler/parser.resolve_aes(ic_ir, ae_dir=None)` — populates IC.affected_paths from the union of `implements_globs` across each `parties[].ae_id`. Auto-infers `ae_dir` from the IC's conventional sibling location. Falls back gracefully (logs to parse_warnings, doesn't fail) when AEs are missing.
- CLI: `dekspec compile` now dispatches by filename — `IC-NNN-*.md` → `parse()`, `AE-NNN-*.md` → `parse_ae()`. New `--resolve-aes` flag (ICs only) runs cross-artifact resolution. AEs only support `--emit ir`; `--emit contract-test|ci-gate` on an AE returns exit 2.
- CLI: `--affected-paths` is now a SUPPLEMENT to `--resolve-aes` (union, dedupe) rather than a pure override.

### Changed

- `--affected-paths` semantics: pre-v0.2.1 it overrode IR.affected_paths wholesale; v0.2.1 unions with whatever `--resolve-aes` produced (dedupe-preserve-order). Allows the v0.1 PoC scaffold to fill gaps when an AE's `implements_globs` isn't yet authored.

### Deferred

- Formal `tests/test_parser_ae.py` + `tests/test_resolve_aes.py` (the 39-AE smoke test in this commit serves as the de-facto coverage; formal unit tests land in v0.2.2).
- Default-ON `--resolve-aes` (waiting until at least one consumer repo populates `implements_globs`).
- WS IR + ADR IR (next two artifact types per the v0.2.0 roadmap).

[v0.2.1]: https://github.com/Dektora/dekspec/releases/tag/v0.2.1

## [v0.2.0] — 2026-05-10

### Added (Constraint Compiler v0.1 PoC — keystone proof shipped)

- `tooling/dekspec/schemas/interface-contract.schema.yaml` — JSON Schema (Draft 2020-12) for the IC IR. Forward-compat opaque ID refs (governing_adrs, parties[].ae_id, serves_intents). `parse_warnings` field captured in IR for cross-run analysis.
- `tooling/dekspec/constraint_compiler/parser.py` — markdown → IC IR. Lossy by design; missing fields populate parse_warnings. Validated against all 17 ICs in dektora2 (17/17 parse).
- `tooling/dekspec/constraint_compiler/emitters/contract_test.py` — IC IR → pytest module string. Skipped stubs by default with rich docstrings carrying contract claims verbatim. Per-operation fixtures (e.g., `evaluate_impl`) provided by consumer's conftest.py.
- `tooling/dekspec/constraint_compiler/emitters/ci_gate.py` — IC IR → GitLab CI job YAML fragment (single includable job). `rules.changes:` scoped to IC source + IR.affected_paths. Configurable via env vars (CONTRACT_TEST_IMAGE, CONTRACT_TEST_REQUIREMENTS, CONTRACT_TEST_DIR).
- `tooling/dekspec/constraint_compiler/persistence.py` — per-compile-invocation logging to `$XDG_DATA_HOME/dekspec/<repo-fingerprint>/runs/<timestamp>-<run-id>/`. manifest.json + events.jsonl + irs/. Per-repo `latest` symlink + lock-states.json ledger. Count-based retention (default 200), milestone flag captured for v0.2+ tiering.
- `tooling/dekspec/cli.py` — full CLI: `dekspec compile <ic-path> [--emit ir|contract-test|ci-gate] [--output PATH] [--treat-as-locked] [--affected-paths PATH1,PATH2,...]`, `dekspec runs ls`, `dekspec runs show <run-id|latest>`. LOCKED-status enforcement at compile time (exit 3 unless --treat-as-locked).
- `tests/poc/` — end-to-end PoC validation: working evaluate impl + conftest + auto-emitted contract test + hand-written assertion. Demonstrates the keystone — breaking the impl's `math.isfinite` check causes the contract assertion to fail with `Failed: DID NOT RAISE`. See `tests/poc/README.md` for the reproduction.
- `tests/test_parser.py`, `tests/test_emitter_contract_test.py`, `tests/test_emitter_ci_gate.py` — happy-path unit tests for parser + each emitter (17 tests total).

### Added (DN→AE migration completion)

- `templates/architecture-element-template.md` — vendored from dekspec-rf. Canonical post-migration shape: `Subtype` enum (System / Subsystem / Container / Component / Pipeline / Data Model / Cross-Cutting Concern / Platform Concern / Interface Surface / Workflow / Process), `Boundaries and Non-Goals` (mandatory non-goals), `Linked Artifacts` (mandatory ADR/WS/IC/IB/Owner refs), `Views` (with absence justification), `Constraints and Quality Notes` (no measurable targets — those go in WSs), `Open Questions / Planned Follow-ons`.

### Changed

- **Templates vendored from dekspec-rf** with AE-cascade fixes: `working-spec-template.md` (Source DN → Source AEs, multiple AEs allowed), `adr-template.md` (+ Related Architecture Elements section, + DEPRECATED + SUPERSEDED status defs, + Validation split into Observable Confirmation / Reconsideration Triggers, + compressed AL policy), `interface-contract-template.md` (+ Provider AE / Consumer AEs subsections, + DEPRECATED status), `implementation-brief-template.md` (+ Intent / Source AEs fields, spec-path typo fix), `vision-note-template.md` (+ DEPRECATED), `intent-template.md` (spec-path typo fix).
- `skills/write-ae/SKILL.md` — scrubbed for DN-leakage that persisted in both dekspec and dekspec-rf: index path, template path, filename pattern (DN-NNN → AE-NNN), workflow-step section names, T1/T2/T3/T5/T7 audit checks updated to AE-template section names + Subtype enum, deprecation pointer format updated.
- `skills/{write-adr,write-ws,write-ic,write-ggc,run-dekspec-fidelity-audit,run-dekspec-fidelity-audit-v2,do-code-archaeology}/SKILL.md` — DN/Design Note prose updated to AE/Architecture Element. `working-working-specs/` typo corrected to `working-specs/` (10 occurrences across 4 skills).
- `docs/{ARCHITECTURE,dekspec-operating-guide,dekspec-quick-reference}.md` and `README.md` — DN/Design Note language updated to AE/Architecture Element. `schemas/` references updated to `tooling/dekspec/schemas/` (the actual install location after the package-data move).
- Schemas relocated under the package: `schemas/` → `tooling/dekspec/schemas/` so wheel installs include them as package data via `importlib.resources`.

### Removed

- `templates/design-note-template.md` — fully replaced by `architecture-element-template.md`.
- `skills/write-design-note/` — fully retired. Use `/write-ae`. No deprecated alias kept; the DN concept is gone.

### Fixed (fidelity audit v2 — 2026-05-09)

Ran `/run-dekspec-fidelity-audit-v2` against dekspec post-AE-migration. Found 7 issues, all pre-existing (none introduced by the AE migration). All 7 fixed:

- **C1 (critical)** — `skills/create-beads/SKILL.md` and `skills/run-coding-session/SKILL.md` had `## name:` (markdown H2) inside the YAML frontmatter instead of `name:`, AND no closing `---` delimiter. The skills would have failed to register as `/create-beads` and `/run-coding-session` slash commands in any consumer install. Fixed: removed `## ` prefix, added closing `---`.
- **I1** — 4 references to phantom skill `/write-implementation-briefs` (correct name: `/write-ibs`) in `skills/write-intent/SKILL.md` and `docs/dekspec-operating-guide.md`. Fixed.
- **I2** — `dekspec-quick-reference.md` Skills table listed deleted skill `/write-design-note`. Fixed: row removed, AE migration history captured in CHANGELOG instead.
- **I3** — `dekspec-quick-reference.md` Skills table missing 5 skills: `/function-planner`, `/high-level-docs`, `/run-dekspec-fidelity-audit-v2`, `/write-intent`, `/write-mission`. Fixed: all 5 added with brief descriptions matching existing-row style; v2 audit marked canonical and v1 marked frozen-for-historical-reproduction; auxiliary skills (`/function-planner`, `/high-level-docs`) annotated as such.
- **I4** — `scripts/install-dekspec.sh` did not vendor `docs/ARCHITECTURE.md` to consumers. Fixed: added the cp.
- **M1** — `skills/function-planner/SKILL.md` and `skills/high-level-docs/SKILL.md` lacked `model:` field in frontmatter (every other skill declares one). Fixed: added `model: claude-opus-4-6`.
- **M2** — Quick-ref pipeline step 7 referenced `/present` without the `*(user-level)*` annotation present elsewhere. Fixed: annotation added.

### Added (ecosystem-tools sweep — 2026-05-10)

Triggered by a downstream finding from `Dektora/dekfactory` (Phase 0 paper-work session) that `/present AE-001` failed to resolve due to the user-scope `/present` skill carrying pre-migration `docs/sdd/` paths and `DN-NNN`-only artifact-ID resolution. Root cause: the DN→AE migration scope didn't include consumer-facing tools that live outside the dekspec git boundary.

- `docs/ecosystem-tools.md` — new registry cataloging tools/skills/scripts that depend on DekSpec artifact-ID conventions or path layouts. Future migrations get a checklist instead of discovering staleness in production.
- `~/.claude/skills/present/SKILL.md` *(out-of-band update; user-scope, not vendored by dekspec)* — comprehensive AE-awareness pass: added `AE-NNN` to the resolution table, made `docs/dekspec/` the canonical root with `docs/sdd/` as a deprecated fallback (emits a one-line warning on hit), accepted `DN-NNN` as a deprecated alias for `AE-NNN` (emits a warning), updated `--review` filter table (added `ae`, marked `dn` deprecated alias), updated all examples and prose ("Dektora SDD" → "DekSpec"). Decision on `/present`'s home: **left user-scope** (it's a presentation tool, not part of the L1-L4 spec authoring chain; vending it would stretch dekspec's scope). The new ecosystem registry mitigates the future-coverage risk.
- Sweep verified: the other 6 user-scope skills (`bd-to-br-migration`, `casr`, `dsr`, `novita-docs`, `process-triage`, `rch`) carry zero DN/SDD references.

### Deferred to v0.3.0+

- Fidelity audit Python implementation (skill currently operates on artifact files directly).
- AGENTS.md compiler output.
- Lint rule / fitness function compiler outputs beyond the single PoC target.
- AE registry IR (`schemas/ae-registry.schema.yaml`) — provides `implements_globs` so `affected_paths` can be derived rather than hand-authored.
- Working Spec IR (`schemas/working-spec.schema.yaml`) and ADR IR (`schemas/adr.schema.yaml`).
- Tiered + compressed retention for run persistence (auto-gzip after 30d, weekly aggregation after 6mo, milestone-forever rule). v0.2 ships the structure but not the tiering logic.
- SQLite index over runs (for `dekspec runs query`).
- `dekspec verify-vendored` CLI (vendored markdown ↔ installed package drift check).

[v0.2.0]: https://github.com/Dektora/dekspec/releases/tag/v0.2.0

## [v0.1.0] — 2026-05-09

### Added

- Initial extraction from `Dektora/dektora`. Pure porting task; no behavior changes from the embedded version.
- 19 skills in `skills/`: write-adr, write-ws, write-ic, write-design-note, write-ibs, write-evals, write-tests, write-intent, write-mission, write-ggc, write-ae, create-beads, run-coding-session, run-dekspec-fidelity-audit, run-dekspec-fidelity-audit-v2, do-code-archaeology, function-planner, high-level-docs, record-divergence.
- Artifact templates in `templates/`: adr, working-spec, interface-contract, design-note, implementation-brief, intent, mission, vision-note. Plus `templates/checklists/`.
- Methodology docs in `docs/`: `dekspec-operating-guide.md`, `dekspec-quick-reference.md`, `architecture-frameworks-reference.md`.
- `docs/ARCHITECTURE.md` — fresh: defines the Mental Model (source → IR → compiled outputs → runtime), tight-vs-swappable boundaries, anti-patterns.
- `scripts/install-dekspec.sh` — vendors skills + templates + docs into a consuming repo; writes `.dekspec-version` marker.
- `pyproject.toml` — Python package skeleton (depends on `pyyaml`, `jsonschema`).
- `tooling/dekspec/` — Python package scaffolding; `cli.py` stub with `--version`.

### Stubbed (implementation lands later)

- `tooling/dekspec/constraint_compiler/` — Phase 0 Check B target per the DekFactory MVP playbook (Interface Contract IR → contract-test stub + GitLab CI gate). Implementation lands in v0.2.0.
- `tooling/dekspec/fidelity_audit/` — Python implementation pending; current `/run-dekspec-fidelity-audit` skill operates on artifact files directly. Implementation in v0.2.0+.
- `schemas/` — empty. IR schemas for IC, ADR, Working Spec land in v0.2.0 alongside the Constraint Compiler v0.1 implementation.

### Known gaps

- No tests yet.
- No CI yet.
- `dekspec verify-vendored` CLI not implemented (planned v0.2.0).
- AGENTS.md compiler output not implemented (planned v0.2.0).
- Lint rule / fitness function / CI gate compiler outputs beyond the single PoC target not implemented (planned v0.3.0).

[v0.1.0]: https://github.com/Dektora/dekspec/releases/tag/v0.1.0
