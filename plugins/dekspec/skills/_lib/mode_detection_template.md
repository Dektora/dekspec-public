# Mode Detection — Canonical Substrate

**Status:** AUTHORITATIVE (per ds-di2, 2026-05-19; ds-int-007 / INT-008).
**Audience:** DekSpec skill authors. Every authoring skill at `plugins/dekspec/skills/write-*/SKILL.md` cites this file from its `## Mode Detection` section instead of inlining the redundant scaffolding prose.
**Lineage:** Extracted from the 12 authoring SKILL.md files during the dim-3 skills-audit refactor (cluster 2). Sister substrate: `_lib/mode_dispatcher.md` (defines the universal-mode contract + Teaching-Mode template). This file pins the per-skill *parse-and-route* surface that sits above the dispatcher's mode catalog.

---

## Why this file exists

Before extraction, every authoring SKILL.md opened its `## Mode Detection` section with three near-identical chunks of prose:

1. A boilerplate parse intro: *"Parse `$ARGUMENTS` for flags. If a flag is present, strip it and enter the corresponding mode. Otherwise, proceed with **<Default Mode>**."*
2. The per-skill flag-to-mode bulleted list.
3. A routing note citing `ds-di2` (2026-05-19) that named which of the skill's modes are *substantive-work* (fan-out via the `Agent` tool to a fresh-context subagent) versus *inline* (executed in the parent session).

Chunks (1) and (3) are pure substrate — the prose was copy-pasted with minor wording drift across skills. Chunk (2) is the only genuinely per-skill content: a skill's flag catalog cannot be centralized because the lifecycle / artifact-specific modes legitimately differ per artifact kind.

This file centralizes the parse contract and the routing-note pattern so:

- New skills can be authored without re-inventing or copy-pasting the scaffolding.
- A change to the parse contract (e.g., a future "argument quoting" rule) edits one file, not twelve.
- The per-skill SKILL.md focuses on its *load-bearing* content — the flag catalog and the substantive-vs-inline split — without burying it under boilerplate.

## Contract

Every authoring SKILL.md's `## Mode Detection` section MUST conform to the following three-part shape, in order:

### Part 1 — Parse contract (centralized; cite this file)

The parse contract is fixed for every authoring skill. The skill cites it via a sentence of the form:

> See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **<Default Mode>**.

The substrate's parse contract — applied uniformly — is:

> Parse `$ARGUMENTS` for flags. If a flag is present, strip it and enter the corresponding mode. Otherwise, proceed with the skill's **Default Mode**. If the argument doesn't fit any recognized pattern (e.g., a path to an unfamiliar file, or a flag this skill does not implement), ask the engineer what they want to do — don't guess.

The skill MUST name its Default Mode in the citation line. The Default Mode is the no-flag path (typically Creation Mode, but some skills use a content-shape sniff — e.g., `write-ibs` checks whether the file is a Working Spec or an Implementation Brief — in which case the Default Mode label SHOULD describe the dispatching behavior, not a single mode name).

### Part 2 — Per-skill flag-to-mode list (NOT centralized; verbatim per skill)

Each authoring skill enumerates its full flag catalog as a bulleted list immediately after the citation line. One bullet per flag, in this shape:

> - **<Mode label>** — `--<flag>` flag. Skip to **<Mode-Section-Name>**.

The flag catalog is per-skill because lifecycle / artifact-specific modes diverge across artifact kinds (e.g., ADRs have `--supersede`; Intents add `--decompose` / `--testpass` / `--sync` / `--amend`; Missions add `--activate` / `--complete` / `--kill`; GGC adds `--log` / `--add-term`; tests add `--all` / `--integration`). Centralizing this list would either lose those distinctions or balloon the substrate with conditionals.

The "no flag → Default Mode" bullet, if present, is the final entry.

### Part 3 — Routing note (centralized pattern; per-skill mode names)

Every authoring skill closes its `## Mode Detection` section with a routing note that names which of *its* modes are substantive-work (fan-out) and which are inline. The prose pattern is centralized here; only the mode names substitute per skill. Recommended shape:

> **Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
> - Substantive-work (fan-out via Agent tool): <list of this skill's substantive-work modes, by flag name or "(no flag)">
> - Inline (parent context): <list of this skill's inline modes, by flag name>

The routing distinction is binding per architectural directive `ds-di2` (2026-05-19): substantive-work modes MUST delegate to a fresh-context subagent via the Agent tool; inline modes run in the parent session. The full rationale + dispatch protocol lives in the skill's own `## Fan-Out Mode` section (which this substrate deliberately does NOT centralize — the bundle context, subagent type, and prompt template are too skill-specific to share).

## Recommended skill-side template

```markdown
## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **<Default Mode>**.

- **Help mode** — `--help` flag. Skip to **Help Mode**.
- **Teaching mode** — `--teaching` flag. Skip to **Teaching Mode**.
- **<Lifecycle mode>** — `--<flag>` flag. Skip to **<Mode-Section-Name>**.
- ... (one bullet per flag this skill implements; per-skill content) ...
- **<Default mode label>** — no flag. Proceed to **<Default-Section-Name>**.

**Routing (per [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md)):**
- Substantive-work (fan-out via Agent tool): <list>
- Inline (parent context): <list>
```

Placeholders to fill per skill:

- `<Default Mode>` / `<Default mode label>` / `<Default-Section-Name>` — the skill's no-flag default (e.g., Creation Mode for most authoring skills; "Fan-Out Mode (default authoring path)" for fan-out-by-default skills; a content-sniff dispatching label for `write-ibs`).
- `<Lifecycle mode>` / `--<flag>` / `<Mode-Section-Name>` — one bullet per flag in the skill's catalog. Keep flag names canonical (no aliases except where documented as a retained alias — e.g., `--approve` aliases `--accept` for `write-ibs`).
- The substantive-work and inline lists in the routing note — name modes by flag (`--accept`, `--revise`) or by "(no flag)" for the default. Be exhaustive: every flag bulleted in Part 2 must appear in exactly one of the two lists.

## Per-skill migration checklist

When refactoring an existing authoring skill to this substrate:

- [ ] Replace the opening "Parse `$ARGUMENTS` ..." paragraph with the citation line: `See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **<Default Mode>**.`
- [ ] Preserve the per-skill flag-to-mode bulleted list verbatim. Do NOT centralize, abridge, or re-order.
- [ ] Replace the existing routing-note prose (typically a `**Routing note (per ds-di2 ...)**` paragraph or the inline "(Inline — ...)" annotations scattered through the bullets) with the canonical routing-note block from Part 3. Fold any per-mode "(Inline — ...)" annotations into the routing note's two-list summary so the bullet list stays uncluttered.
- [ ] Confirm the `## Fan-Out Mode` section that follows is untouched — it remains skill-specific.
- [ ] Run `pytest tests/test_skills_dispatcher.py` — must be green. (The dispatcher lint enforces presence of universal modes + substrate citation; it does NOT enforce this file's citation, but the recommended shape keeps mode names visible to that test.)

## Reconsideration triggers

This substrate's contracts should be revisited if:

- A new authoring skill introduces a parse step the boilerplate cannot express (e.g., positional sub-commands that look unlike a flag). At that point, either extend the parse contract here or document the divergence in the skill.
- The substantive-vs-inline routing split (per `ds-di2`) is superseded by a different architectural directive. Update Part 3 here and the per-skill routing notes will follow on next edit.
- More than half of the authoring skills end up duplicating their flag-to-mode bullet shapes across artifacts (e.g., every lifecycle artifact ends up with the same `--lock` / `--unlock` / `--accept` / `--revise` quartet). At that point, consider promoting that quartet to a named lifecycle preset here and let per-skill bullets cite it.

## Links

- `_lib/mode_dispatcher.md` — the universal-mode contract + Help-Mode / Teaching-Mode templates (sister substrate).
- `ds-di2` (bead, 2026-05-19) — architectural directive establishing the substantive-vs-inline routing split.
- INT-008 / ds-int-007 — the parent Intent for the multi-mode-skills dispatcher work.
- AE-006 Skills Library — the AE this substrate lives within.
