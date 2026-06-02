# Provisional Mode

[← back to dispatcher](../SKILL.md)


`--provisional <incubation-slug>` redirects authoring into the provisional staging area (`dekspec/provisional/<incubation-slug>/`) instead of the canonical `dekspec/intents/` directory. The canonical Status transition + audit walker pick the work up only after the hand-promote workflow (see [`docs/dekspec-operating-guide.md` §Provisional Promotion](../../../../../docs/dekspec-operating-guide.md#step-4--provisional-promotion-hand-promote-workflow)) is run later. (The previous CLI verb was retired 2026-05-25; see `plugins/dekspec/skills/_lib/cli_verbs.md` for the rename history.)

Use this mode when:
- The exploration may span many commits before ratification.
- Companion artifacts (ADRs / AEs / ICs that this Intent depends on) will be authored alongside in the same incubation folder.
- The canonical ID should NOT be claimed until the originating Intent reaches ACCEPTED.

### Steps

1. Parse `$ARGUMENTS` for `--provisional <slug>`. Strip the flag pair before proceeding so the remaining args feed normal authoring.
2. **Worktree-collision guard (ds-2tky).** `new-provisional` default-creates a git branch (`int/INT-provisional-<slug>`) on the shared tree; run the guard first so a concurrent Intent lifecycle in this checkout cannot flip HEAD against it:
   ```
   python plugins/dekspec/skills/write-intent/scripts/worktree_guard.py --new-branch int/INT-provisional-<slug>
   ```
   - Exit `2` → HEAD is on another `int/INT-*` branch. Scaffold with `--no-branch` and run the lifecycle in an isolated worktree from a clean base (the guard prints the `git worktree add` command); do **not** let `new-provisional` cut a branch on the shared tree.
   - Exit `0` → safe; proceed (heed any advisory about other in-flight Intent branches).
3. If the incubation folder `dekspec/provisional/<slug>/` does not exist OR does not yet contain a `INT-provisional-*.md` file for this work, scaffold via:
   ```
   dekspec library new-provisional INT <slug> --title "<H1 title from remaining $ARGUMENTS>" [--incubation <slug>] [--no-branch]
   ```
   The CLI scaffolds the folder + skeleton + (by default) a git branch named per kind. Surface its stderr on non-zero exit and STOP.
4. Read the scaffolded file at `dekspec/provisional/<slug>/INT-provisional-<title-slug>.md` (the CLI prints the path).
5. **Populate the skeleton with this skill's authoring discipline** — every section the canonical-mode flow would fill in goes here (Motivation, Linked AEs, Components affected, Verification, etc.). The PROVISIONAL banner at the top stays.
6. **Reject `--lock`** in combination with `--provisional`. LOCKED state requires linkage-walker visibility that provisional artifacts deliberately lack. The hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion) is the canonical path to LOCKED.
7. **`--analyze` and `--review`** remain available in provisional mode — they operate on the provisional file's content without requiring canonical-graph visibility.
8. Closing step: surface to the engineer the path of the provisional file, the branch (if created), and the next-step hand-promote workflow (see `docs/dekspec-operating-guide.md` §Provisional Promotion).

### Cross-references

- `INT-079` — provisional folder substrate (parser-ignore, doctor advisory).
- `INT-082` — copy-on-write spec staging (`replaces:` frontmatter, sibling-collision audit).
- `INT-083` — atomic promotion (CLI verb retired 2026-05-25; the hand-promote workflow is canonical — see `_lib/cli_verbs.md`).
- `INT-084` — `dekspec library new-provisional` scaffold + auto-branch.

**End of Provisional Mode.**
