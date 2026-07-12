# DekSpec Lock / Unlock Mode — Canonical Substrate

**Status:** AUTHORITATIVE (per the skills-library audit / Dim 3 cluster 4 refactor).
**Audience:** DekSpec skill authors. Every L0/L1/L2 authoring skill whose artifact carries a `LOCKED` lifecycle state cites this file from its `## Lock Mode` and `## Unlock Mode` sections and inlines a per-skill parameter manifest.
**Lineage:** Derived by deduplicating the Lock/Unlock prose previously copied across `write-{adr,ae,ic,ws,sp,sv}` SKILL.md files. Pattern extends the mode-dispatcher substrate at [`_lib/mode_dispatcher.md`](mode_dispatcher.md) for the lifecycle-bound `--lock` / `--unlock` flags.

---

## Why this file exists

Before this substrate landed, every lifecycle-aware authoring skill rolled its own Lock and Unlock prose. Three concrete consequences:

1. **Step semantics drifted across skills.** Some skills reported the audit and then asked for confirmation; others bundled the audit and the status flip into one step. Some appended Amendment Log entries before the index update, others after. Engineers reading the prose had to re-learn the contract per skill.
2. **Index-update plumbing was hand-copied.** Each skill's Step 4 named its own index file (`dekspec/adr-index.md`, `dekspec/architecture-elements-index.md`, etc.) and described the same row-edit in slightly different words.
3. **The "ask for unlock reason" contract was unenforceable as prose.** Some skills demanded "at least a sentence"; others accepted any non-empty string; one accepted silence. The substrate makes the gate explicit and uniform.

This file is the source of truth. Each lifecycle SKILL.md replaces its in-body Lock / Unlock steps with a citation to this file plus a parameter manifest naming the artifact kind, the source / destination statuses, the artifact's index file, and the pre-lock audit reference.

## Lock — canonical 4-step contract (ACCEPTED → LOCKED)

The Lock mode promotes an artifact from its accepted-but-mutable state to its frozen reference state. Once an artifact is LOCKED, downstream artifacts may rely on its shape; substantive edits require `--unlock` first.

### Parameters every caller must supply

- **artifact_kind_singular** — the human-readable noun for one instance of this artifact (e.g., `ADR`, `architecture element`, `Working Spec`, `Interface Contract`, `Security Profile`, `System Vision`).
- **status_before** — the lifecycle status the artifact must be in to lock. Canonical value: `ACCEPTED`. Skills with a non-canonical source status declare it here (e.g., write-intent locks from `MERGED`, not from `ACCEPTED`; that skill does not use this substrate for its Lock step).
- **status_after** — the lifecycle status to flip to. Canonical value: `LOCKED`.
- **pre_lock_audit_ref** — pointer to the audit checklist Step 2 must execute. Typically `§Audit Mode of this skill`, optionally with a skill-specific extension that names additional blocking rules (e.g., "L1-GLOSSARY is BLOCKING at Lock" for write-ae).
- **artifact_index_path** — the index file whose status column for this artifact must also flip (e.g., `dekspec/adr-index.md`). Skills whose artifact is a singleton with no index row (write-sv, write-constitution) may omit this and say so in the manifest.

### Step 1: Validate

Read the artifact at the path the engineer supplied. Verify the artifact's current `Status` field equals **status_before**. If it does not, refuse and explain why in one sentence — naming both the current status and the expected status. Suggest the right mode to reach **status_before** if one exists (e.g., `--accept` to promote PROPOSED → ACCEPTED before locking). Do not proceed past this step on a mismatch.

### Step 2: Pre-lock audit

Run the audit checklist referenced by **pre_lock_audit_ref** in full. Report each check's pass/fail status and the count of passed-vs-total. Any failure blocks the lock — no exceptions, no per-failure waivers from inside the substrate. (Skill-specific extensions may add additional blocking rules; they may not relax the substrate's own.) Surface a concise report to the engineer in this shape:

```
PRE-LOCK AUDIT: <path>

Passed: <N>/<total>
Failed:
  - <one-line per failure>

[If all passed]  Ready to lock. Confirm? (yes / no)
[If any failed]  Cannot lock — resolve failures first.
```

If any check failed, stop here. Do not prompt for confirmation; the engineer must fix the failures and re-run `--lock`. If all checks passed, wait for the engineer to type `yes`. Any other response (including silence, `no`, "later", a question) aborts the mode without writing.

### Step 3: Promote and log

Only on explicit `yes`:

1. Flip `Status` to **status_after**, bump `Modified` to today, and append the Amendment Log entry — this is a deterministic edit, so delegate it: run `python ../_lib/scripts/artifact_ops.py transition <artifact-path> --from <status_before> --to <status_after> --note "Artifact locked after pre-lock audit passed" --engineer <engineer-or-agent>`. Surface stderr on a non-zero exit and STOP. The canonical Amendment Log row the script writes is `| <today> | Lock | Artifact locked after pre-lock audit passed | <engineer-or-agent> |`. Skills whose Amendment Log uses a non-`Substantive`/non-`Lock` row convention (e.g. SP / Constitution lowercase lifecycle types) instead run `transition` without `--note` and hand-author the log row — those skills declare the variance in their own manifest.
2. If **artifact_index_path** is set, update the matching row's `Status` cell to **status_after** — run `python ../_lib/scripts/artifact_ops.py update-index <artifact_index_path> --id <artifact-id> --status <status_after>` (surface stderr on a non-zero exit). Omit this step for singletons with no index.

### Step 4: Validate the written artifact

Re-run `dekspec validate <path>` (or `dekspec validate` over the singleton if the artifact has no path argument). Surface any validation error and stop — the lock has written but the artifact is structurally broken; the engineer must fix and re-lock.

If validation passes, surface a closing line confirming the new status, the new Modified date, and the index row update (if applicable). Skills may extend this with cascade reminders (e.g., "downstream IBs may need `--resync`"), but the four substrate steps are non-negotiable.

## Unlock — canonical 4-step contract (LOCKED → PROPOSED)

The Unlock mode walks an artifact back from its frozen state to a mutable state so a substantive edit can be applied. Unlock is deliberately reason-gated — the Amendment Log must record why a previously-frozen artifact is being reopened, so the trail survives future audits.

### Parameters every caller must supply

- **artifact_kind_singular** — same as Lock.
- **status_before** — the lifecycle status the artifact must be in to unlock. Canonical value: `LOCKED`.
- **status_after** — the lifecycle status to flip to. Canonical value: `PROPOSED`. Skills whose unlock walks to a different mutable state (e.g., write-sp unlocks `LOCKED → ACCEPTED` rather than `LOCKED → PROPOSED`, on the rationale that an unlocked SP is one edit away from re-lock, not back at the proposal stage) declare the variance here.
- **artifact_index_path** — same as Lock; omit for singletons with no index row.

### Step 1: Validate

Read the artifact at the path the engineer supplied. Verify the artifact's current `Status` field equals **status_before** (canonically `LOCKED`). If it does not, refuse with a one-sentence explanation naming both the current and expected status. Do not proceed past this step on a mismatch.

### Step 2: Reason gate

Ask the engineer: "Why is this <artifact_kind_singular> being unlocked? (This will be recorded verbatim in the Amendment Log.)" Wait for a written reason. Reject empty replies, single-word replies (`"typo"`, `"fix"`, `"because"`), and bare punctuation. Demand at least one full sentence naming the trigger — what is changing and why now. Loop until a substantive reason is given, or abort if the engineer declines to supply one.

Skills with a downstream-impact surface SHOULD also run a quick downstream scan at this step (grep specs / IBs / beads for references to the artifact and list affected items with their current status) and present the impact list alongside the reason prompt. The substrate does not require this — it requires the reason — but skills whose downstream blast radius is non-trivial (write-ws, write-ic, write-ae) are expected to show the engineer what they are about to disturb before asking for confirmation.

### Step 3: Demote and log

After a valid reason is supplied (and any impact list has been shown):

1. Flip `Status` to **status_after**, bump `Modified` to today, and append the Amendment Log entry — delegate the deterministic edit: run `python ../_lib/scripts/artifact_ops.py transition <artifact-path> --from <status_before> --to <status_after> --note "<engineer's reason verbatim>" --engineer <engineer-or-agent>`. Surface stderr on a non-zero exit and STOP. The reason text passed via `--note` MUST be the engineer's words verbatim — the substrate forbids paraphrasing, summarizing, or "cleaning up" the reason; the engineer's words are the audit trail. The script writes the canonical row `| <today> | Unlock | <engineer's reason verbatim> | <engineer-or-agent> |`. Skills with a non-`Substantive` log convention run `transition` without `--note` and hand-author the row, carrying the reason verbatim.
2. If **artifact_index_path** is set, update the matching row's `Status` cell to **status_after** — run `python ../_lib/scripts/artifact_ops.py update-index <artifact_index_path> --id <artifact-id> --status <status_after>` (surface stderr on a non-zero exit). Omit this step for singletons with no index.

### Step 4: Validate the written artifact

Re-run `dekspec validate <path>` (or the singleton equivalent). Surface any validation error and stop.

If validation passes, surface a closing reminder pointing the engineer at the right follow-on mode for applying the substantive change (typically `--revise` or `--review`), and noting that a fresh `--accept` and `--lock` will be needed when the change is complete. Skills with non-trivial cascade implications (downstream artifacts referencing this one) SHOULD also surface a cascade reminder enumerating the IB-resync / bead-recreation / dependent-artifact-review steps the engineer will need to do after the substantive edit.

## When NOT to use this substrate

This substrate covers the canonical ACCEPTED → LOCKED → PROPOSED cycle for L0/L1/L2 lifecycle artifacts. Skills whose Lock or Unlock semantics diverge fundamentally from that shape should NOT cite this file — they should keep their bespoke prose and document the divergence at the top of their own Lock/Unlock section.

Known divergent cases (as of the substrate's first landing):

- **`write-intent` Lock Mode is MERGED → LOCKED, not ACCEPTED → LOCKED.** Intents are locked post-merge on the `main` branch, with a branch-name gate, a verification-block re-equality check, and a Mission-queue append. None of those fit the substrate's parameter slots, so write-intent keeps its bespoke Lock prose. write-intent's **Unlock Mode** (`LOCKED → PROPOSED`) cites this file's §Unlock Step 2 reason-gate but keeps a bespoke status flip and a two-table index move (Archive ↔ Active queue); `--unlock` is the editorial-correction path only — a LOCKED Intent needing a *substantive* change still spawns a successor Intent and marks the original `SUPERSEDED`.
- **`write-constitution` and `write-mission`** have no Lock or Unlock modes in their lifecycle and therefore do not interact with this substrate. Constitutions live in their own L0 cycle (no LOCKED state today); Missions transition via `--activate` / `--complete` / `--kill` / `--supersede`.
- **`write-sv` (System Vision)** uses the substrate but declares an "extra-loud warning" Step 1 addendum — the System Vision is the L0 root and locking signals "any change cascades to every dependent artifact." Skill manifests should call this out explicitly.

## Per-skill migration checklist

When refactoring an existing lifecycle-aware authoring skill to the substrate:

- [ ] Replace the existing `## Lock Mode (ACCEPTED → LOCKED)` body with a citation to this file plus a parameter manifest naming `artifact_kind_singular`, `status_before`, `status_after`, `pre_lock_audit_ref`, and `artifact_index_path`.
- [ ] Replace the existing `## Unlock Mode (LOCKED → PROPOSED)` body with a citation plus the four Unlock parameters.
- [ ] Preserve any genuinely skill-unique gating (extra blocking audit rules, cascade reminders with non-trivial downstream surfaces, the System Vision's extra-loud warning) as named extensions inside the manifest — not as competing prose alongside the citation.
- [ ] Confirm `dekspec validate` is the closing validation tool referenced; skills that historically called a different validator should switch.
- [ ] Run the skills-library test suite — must be green.

## Reconsideration triggers

This substrate's contract should be revisited if:

- A new lifecycle artifact enters DekSpec whose Lock or Unlock shape does not fit the 4-step contract here (per the "When NOT to use" list growing past three entries — that would be a sign the substrate is under-fitting and the canonical contract needs to be widened or split).
- The "reason gate" in Step 2 of Unlock degrades in practice into a checkbox the engineer types `"unlock"` past — sign that the gate needs to demand a structured reason (a typed enum: `editorial`, `substantive`, `scope-change`, `error-correction`) rather than free-form prose.
- The substrate's pre-lock audit step becomes the place skill-specific audit rules are added (rather than the skills' own Audit Mode) — sign that the audit-rule surface is leaking into the substrate and should be re-located.

## Links

- [`_lib/mode_dispatcher.md`](mode_dispatcher.md) — the parent multi-mode dispatcher pattern; `--lock` / `--unlock` are lifecycle-bound modes in that catalog.
- AE-006 Skills Library — the AE this substrate lives within.
