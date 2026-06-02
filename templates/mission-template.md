# Mission MSN-NNN: [Verb-first title]

**Mission ID:** MSN-NNN
**Status:** TODO | ACTIVE | COMPLETING | COMPLETE | KILLED
**Owner:** [single human accountable]
**Created:** [YYYY-MM-DD]
**Modified:** [YYYY-MM-DD]
**Autonomy ceiling:** manual | low | medium | high

*Valid statuses:* `TODO` → `ACTIVE` → `COMPLETING` → `COMPLETE` | any non-terminal stage → `KILLED`

- **TODO** — Mission file created; up-front section written; no Intents yet
- **ACTIVE** — at least one Intent has reached `LOCKED` under this Mission
- **COMPLETING** — flag is on, all known Intents `LOCKED`, awaiting Mission Verification predicate to evaluate true
- **COMPLETE** — Mission Verification predicate evaluated true; flag-removal Intent (if any) `LOCKED`; Mission archived
- **KILLED** — kill criteria triggered or owner declared abandonment; rollback executed; archived with reason

---

## Near-immutable section

*The fields below are written before any Intent leaves DRAFT and are not edited routinely. Substantive changes happen only via `/write-mission --supersede`, which creates a successor Mission and marks the current one `SUPERSEDED`. Routine `/write-mission --review` revisions edit only the live section below.*

### Outcome

[One paragraph describing the user-observable change. If this changes, the Mission is wrong-shaped — supersede it, don't edit it.]

### Mission Verification

[Machine-checkable, user-observable predicate that defines "Mission complete." Stronger than any single Intent's Verification — typically a behavioral assertion across the integrated system. Required (audit-v2 T17): at least one named cmd check.]

```yaml
- name: <user-observable-check-1>
  cmd: <command that exits 0 only when the Mission outcome is true>
- name: <integration-or-behavioral-check-2>
  cmd: <command>
```

*Like Intent Verification, every cmd entry must resolve to an executable script or recognized tool. The Mission Verification predicate is the gate on the `COMPLETING → COMPLETE` transition (run by `/write-mission --complete`).*

### Out-of-scope

[Explicit non-goals. What this Mission deliberately won't change. Drift detection lives here — when scope creep tries to land in a child Intent, the out-of-scope contract is the gate that rejects it.]

- [non-goal 1]
- [non-goal 2]

### Flag strategy

[How a feature flag (if any) guards partial state during rollout. If no flag is needed — e.g., a bug-fix-shaped Mission with no user-visible partial state — say `none` with a one-line rationale.]

- **Flag name:** `<flag-name>` or `none`
- **Default state during Mission:** off | on | n/a
- **Who flips it on:** [role / event]
- **Removal plan:** [the Intent that removes the flag once the Mission is COMPLETE, or "n/a"]

### Rollback plan

[Structured rollback predicate. `Trigger` is the prose circumstance that calls for rollback. `Steps` is an ordered, executable cmd list parallel to Mission Verification — each step has a `name` (observable, grep-able) and a `cmd` (exits non-zero only when the step has failed). The plan must be executable without the original author present. Mission IR schema v0.2.0 (ds-zuy).]

**Trigger:** [one-paragraph prose — when does rollback fire?]

```yaml
- name: <revert-step-1>
  cmd: <command that performs the step and exits 0 on success>
- name: <revert-step-2>
  cmd: <command>
```

*Like Mission Verification, every step's `cmd` is resolved by audit-v2 L9 against the executable surface. Use the `_legacy_prose` sentinel name + `echo SKIP_LEGACY_ROLLBACK` cmd if the rollback is intentionally human-attended and cannot be automated yet — it will surface in the advisory queue rather than the L9 strict-fail set.*

### Kill criteria

[Observable abandonment conditions, each a named cmd check parallel to Mission Verification. Each criterion's cmd exits non-zero when the kill condition is true. Mission IR schema v0.2.0 (ds-zuy).]

```yaml
- name: <e.g., latency-regression-too-large>
  cmd: <command — e.g., scripts/check-latency-budget.sh --threshold 10pct>
- name: <e.g., two-consecutive-testfails>
  cmd: <command>
```

*If a kill criterion is intentionally subjective ("owner declares abandonment"), use the `_legacy_prose_N` sentinel name + `echo SKIP_LEGACY_KILL` cmd. Mixing structured and prose entries is allowed.*

### First Intent

[The first Intent the Mission will create. Concrete enough to start; no commitment to subsequent Intents at this stage. The Intent ID may be a sketch (`INT-???`) until `/write-intent` is run for it; subsequent Intents are added to the live Intent queue below as they emerge.]

INT-NNN — [title]

### Autonomy ceiling

[Maximum Autonomy any constituent Intent may carry. No child Intent may exceed this. Phase-1-era default: `manual`. Higher ceilings opt up only when the Mission's rigor justifies it.]

`manual` | `low` | `medium` | `high`

---

## Live section

*The fields below are revised continuously via `/write-mission --review` after each Intent transitions. They reflect the Mission's runtime state, not its commitments.*

### Intent queue

[Ordered list of Intents under this Mission. As the Mission proceeds, sketches become drafts, drafts become LOCKED. The order is execution order — at most one Intent in active status at a time across the repo (Decision #9), so the queue is also the serialization queue.]

| INT | Title | Type | Status | Notes |
|---|---|---|---|---|
| INT-NNN | [title] | feature \| bug \| nfr \| ... | LOCKED | [post-LOCK note, e.g., merged-date] |
| INT-NNN | [title] | feature | DRAFT | [working note] |
| (sketch) | [title] | feature | — | tentative; not yet authored |

### Discovered prerequisites

[Coverage gaps surfaced during child Intent `--analyze` runs that retroactively belong to the Mission. These are gaps that the Mission as a whole must close before its Verification predicate can evaluate true — even if no single child Intent owns them.]

- [prerequisite 1] — **Source:** [child Intent that surfaced it] — **Resolution:** [Intent number or "deferred to follow-on"]

### Burndown

LOCKED: [N] / Estimated total: [M] / Sketches: [K]

*Surfaces remaining work for the engineer. Not a hard gate — `/write-mission --complete` evaluates the Verification predicate, not the burndown count.*

### Flag transitions

[Every flag flip is recorded with date, the action taken, and the observed effect on integration metrics or user behavior.]

| Date | Action | Effect observed |
|---|---|---|
| [YYYY-MM-DD] | flipped on for cohort A | [observation] |

### Notes

[Working notes, decisions surfaced mid-Mission, links to related artifacts. The §Notes section is where calibration findings about the Mission rigor itself land — when the 10 near-immutable fields prove the wrong shape, the finding is recorded here and surfaced for the rigor-recalibration follow-on (FOLLOW.2). If a calibration finding or follow-on note carries a severity tag, use the canonical `P0` / `P1` / `P2` / `P3` ladder per ADR-013 (historical aliases `blocking` → `P1`, `non_blocking` → `P3`, `critical` → `P1`, `important` / `warning` → `P2`, `minor` / `info` → `P3` remain accepted indefinitely — see `docs/dekspec-methodology.md#severity-vocabulary` for the full ladder and alias map).]

---

## Amendment Log

*Add an entry for every change made after `ACTIVE` status, or when a near-immutable field is revised via `/write-mission --supersede` (which creates a successor Mission rather than editing in place).*

| Date | Type | Change | Author |
|------|------|--------|--------|
| YYYY-MM-DD | Activate / Review / Complete / Kill / Supersede | <one-sentence summary + delta / commit reference> | [name or agent] |
