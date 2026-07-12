# DekSpec Help Mode — Canonical Substrate

**Status:** AUTHORITATIVE.
**Audience:** DekSpec skill authors. Every skill that exposes a `--help` flag (every authoring skill at `skills/write-*/SKILL.md`, plus the non-authoring orchestration skills such as `write-code-beads`, `orchestrate-coding-session`, `archeology`) cites this file in its `## Help Mode` section and supplies a manifest. The canonical rendering contract below is enforced uniformly across skills.
**Sibling substrates:** `_lib/mode_dispatcher.md` (universal mode catalog + Mode-Detection prose), `_lib/teaching_mode.md` (Teaching Mode contract), `_lib/lock_unlock.md` (lifecycle promotion prose).

---

## Why this file exists

Before this substrate landed, every skill's `## Help Mode` section embedded the same framing prose verbatim:

- `Display this and stop:` as a single intro sentence
- A fenced code block in the USAGE / MODES / EXAMPLES shape
- `**End of Help Mode.**` as the terminator
- A `--help` row that is literally identical across all skills (`Show this help message.`)
- A `--teaching` row whose description varies only in the artifact-kind noun (and most skills duplicate the same `Interactive tutorial walking a new author through writing a <kind> section-by-section. Distinct from --review (audits existing) and from no-flag creation (assumes the author already knows <kind>s).` paragraph)

Three concrete consequences:

1. **Help drift across skills.** When the universal `--help` row gained "Show this help." vs "Show this help message.", four skills were updated and the rest were not. The dispatcher test only checks that the `--help` token exists somewhere in the file; it cannot detect framing divergence.
2. **Help authoring is high-friction.** A new skill author copies an entire ~50-line `## Help Mode` block from the nearest sibling, then hand-edits every row. Mistakes compound (wrong skill name in EXAMPLES, missing `--teaching`, mis-formatted MODE column).
3. **No canonical rendering contract.** When the engineer asked "what should --help print?", the answer was implicit in the copy-paste pattern, not documented anywhere.

This file is the source of truth. Each consuming SKILL.md cites it, supplies a YAML manifest with only the variable parts, and includes the canonical sentence `render the manifest per _lib/help_mode_template.md and stop`. At runtime the skill renders the manifest into the canonical USAGE / MODES / EXAMPLES block defined below.

## Canonical Help Mode rendering contract

When a skill enters Help Mode (`--help` flag), it MUST emit exactly this shape, then stop:

1. The literal sentence `Display this and stop:` on its own line, followed by a blank line.
2. A single fenced code block (triple-backtick, no language tag) containing:

   ```
   <skill_name> — <one_line>

   USAGE:
     <skill_name> [FLAG] <target> [notes]

   MODES:
     <flag> <args>              <description, wrapped at column 78 with two-
                                space hanging indent>
     ...one row per mode, in the order given in the manifest...

   EXAMPLES:
     <example-1>
     <example-2>
     ...
   ```

   The optional `STORAGE:` section appears after `EXAMPLES:` when the manifest sets `storage`. Skill-unique rows (e.g., `WORKFLOW`, `TARGET`, `WHEN TO RUN`, `SCOPE FILTERS`, `TYPICALLY CALLED BY`, `INFRASTRUCTURE`, `TEST LOCATIONS`) appear after `EXAMPLES:` (and after `STORAGE:` if present) when the manifest sets `extra_sections`. Each extra section is rendered as its uppercase heading + the supplied body lines.

3. The literal `**End of Help Mode.**` on its own line after the closing fence.

The rendered MODES table MUST end with:

- `--help                       Show this help message.`

The rendered MODES table MUST include `--teaching` when the skill is an authoring skill subject to `_lib/mode_dispatcher.md` (i.e., every `skills/write-*` skill except per its exemption table). Non-authoring skills (`write-code-beads`, `orchestrate-coding-session`, `archeology`) MAY omit `--teaching` per the dispatcher-test exemption list.

The skill MUST NOT emit any prose after `**End of Help Mode.**` — the help invocation terminates the skill.

## YAML manifest schema

Each consuming SKILL.md supplies a YAML block with the per-skill variable parts:

```yaml
skill_name:    "/dekspec:<slug>"      # required. The user-facing slash-command form.
one_line:      "<purpose>"            # required. Matches the front-matter `description` field.
usage_target:  "<description or path> [notes]"  # optional; default "<target>"
modes:                                # required. Ordered list of per-flag rows.
  - flag:        "--<flag>"           # required. The literal flag string.
    args:        "<target>"           # optional; default "" (no arg slot)
    description: "<one-or-multi-line description>"  # required.
  # ...
examples:                             # required. List of one-line invocation strings.
  - "<skill_name> <example-1>"
  - "<skill_name> <example-2>"
storage:        "<path-pattern>"      # optional. Rendered as STORAGE: section if present.
extra_sections:                       # optional. Skill-unique section blocks (rare).
  - heading: "WORKFLOW"
    body:
      - "Phase 1: ..."
      - "Phase 2: ..."
```

Field contract:

- `skill_name` MUST start with `/`. The Dektora plugin convention is `/dekspec:<slug>`; legacy skills may use `/<slug>`. Use the plugin-prefixed form for newly authored skills.
- `one_line` SHOULD match the YAML front-matter `description` field byte-for-byte. Drift between front-matter and Help is one of the most common UX regressions; keeping them aligned via a single edit point is one of the substrate's purposes.
- `modes` is rendered in the manifest's order. By convention: creation row first (flag `""`), then lifecycle/artifact-specific modes, then `--teaching`, then `--help` last. The renderer does NOT auto-sort.
- `modes[].description` may contain embedded newlines; the renderer applies the two-space hanging indent so multi-line descriptions align under the column where the first description char began.
- `examples` lines are emitted verbatim under `EXAMPLES:` with two-space indent. The first token of each example should be `skill_name` so the engineer can copy-paste directly.
- `storage` is rendered as a single-line `STORAGE:` section: `  <storage_value>`. Use for artifact-storage paths (e.g., `dekspec/security-profiles/SP-NNN-<slug>.md`).
- `extra_sections` is the escape hatch for skills with genuinely unique Help structure (e.g., `orchestrate-coding-session`'s `WORKFLOW:` phase list, `archeology`'s `BOUNDARY:` and `EXCLUDE FILE:` blocks). Use sparingly — if more than two skills need the same extra section, promote it to a first-class manifest field.

## Universal-mode rows (every authoring skill includes verbatim)

The following manifest rows are required for every authoring skill subject to `_lib/mode_dispatcher.md`. Copy them as-is into the `modes:` array (adjusting only artifact-kind nouns):

```yaml
- { flag: "--teaching", args: "",       description: "Interactive tutorial walking a new author through writing a <kind> section-by-section. Distinct from --review (audits existing) and from no-flag creation (assumes the author already knows <kind>s)." }
- { flag: "--help",     args: "",       description: "Show this help message." }
```

`--teaching` MUST appear before `--help`. `--help` MUST be the last row. The dispatcher test enforces presence of both tokens but does not enforce row order; the substrate enforces row order as a stylistic invariant so the rendered output is stable across skills.

## Recommended skill-side template

Replace the existing `## Help Mode` body with the following template, populating the manifest's fields for this skill:

```markdown
## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

\`\`\`yaml
skill_name: "/dekspec:<slug>"
one_line:   "<purpose — matches front-matter description>"
modes:
  - { flag: "",           args: "<target>",  description: "<creation-mode description>" }
  - { flag: "--audit",    args: "<target>",  description: "<audit-mode description>" }
  - { flag: "--review",   args: "<target>",  description: "<review-mode description>" }
  # ... lifecycle / artifact-specific modes ...
  - { flag: "--teaching", args: "",          description: "Interactive tutorial walking a new author through writing a <kind> section-by-section. Distinct from --review (audits existing) and from no-flag creation (assumes the author already knows <kind>s)." }
  - { flag: "--help",     args: "",          description: "Show this help message." }
examples:
  - "/dekspec:<slug> <typical creation example>"
  - "/dekspec:<slug> --audit <example path>"
  - "/dekspec:<slug> --help"
storage: "<artifact-storage path pattern, if applicable>"
\`\`\`

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.
```

The fenced YAML inside the SKILL.md is rendered to the canonical USAGE / MODES / EXAMPLES shape at invocation time. The skill author does NOT hand-write the rendered output; the YAML manifest IS the source of truth.

## Per-skill migration checklist

When refactoring a skill onto the substrate:

- [ ] Replace the existing `## Help Mode` body with the template above (citation + manifest + render sentence).
- [ ] Populate the manifest from the skill's existing Help block. Preserve descriptions verbatim where they are skill-specific; collapse `Show this help message.` and the `--teaching` paragraph onto the universal rows above.
- [ ] If the existing Help block has skill-unique sections (`WORKFLOW`, `TARGET`, `WHEN TO RUN`, `SCOPE FILTERS`, etc.) that don't fit the manifest's flat shape, transcribe them into `extra_sections:` with the appropriate heading.
- [ ] Verify the dispatcher test still passes (`pytest tests/test_skills_dispatcher.py`).
- [ ] If the skill has a dedicated structural test (`tests/test_skill_*.py`), re-run it. The two known tests are:
  - `tests/test_skill_write_constitution.py::test_each_mode_has_invocation_example` — asserts `/write-constitution.*--help` matches somewhere in the Help section. The manifest's `examples:` array satisfies this provided one example is `/write-constitution --help`.
  - `tests/test_write_security_profile_skill.py::test_skill_help_block_enumerates_all_eight_modes` — extracts the first fenced code block under `## Help Mode` and asserts each canonical mode name appears within. The manifest YAML lists every flag (e.g., `--create`, `--analyze`, `--accept`), so substring matches on the bare mode-name tokens hold.

## Reconsideration triggers

This substrate's contract should be revisited if:

- A new manifest field is needed in more than two skills (promote `extra_sections` patterns into first-class fields).
- The rendered Help output diverges from the canonical shape in practice (sign that the manifest is under-specified or that the renderer is being skipped). Re-tighten the contract here, then resync skills.
- The dispatcher pattern itself evolves (e.g., the universal-mode set changes per `_lib/mode_dispatcher.md`). Mirror the change in the universal-mode-rows section above so consumers stay in sync.

## Links

- `_lib/mode_dispatcher.md` — sibling substrate for mode catalog + Mode-Detection prose.
- `_lib/teaching_mode.md` — sibling substrate for Teaching Mode contract.
- `_lib/lock_unlock.md` — sibling substrate for lifecycle promotion prose.
- INT-008-multi-mode-skills-dispatcher.md — parent Intent for the multi-mode refactor.
- AE-006 Skills Library — the AE this substrate lives within.
