# Interface Design

When the engineer wants alternative interfaces for a chosen deepening candidate,
use this parallel sub-agent pattern. Based on "Design It Twice" (Ousterhout).
Uses [language.md](language.md) vocabulary.

## Process

1. **Frame the problem space.** Before spawning sub-agents, write a user-facing
   explanation: the constraints any new interface must satisfy; the dependencies
   plus their category (see [deepening.md](deepening.md)); a rough illustrative
   code sketch (not a proposal, just grounding). Show it to the engineer, then
   proceed to step 2 (the engineer reads while sub-agents work).
2. **Spawn sub-agents.** 3+ in parallel via the Agent tool, each producing a
   radically different interface. Prompt each with a separate technical brief
   (file paths, coupling, dependency category from [deepening.md](deepening.md),
   what's behind the seam). Give each a different constraint: Agent 1 minimise
   the interface (1-3 entry points, max leverage); Agent 2 maximise flexibility;
   Agent 3 optimise the common caller; Agent 4 (if applicable) ports & adapters
   for cross-seam deps. Include both [language.md](language.md) vocabulary and
   the project's domain vocabulary from `dekspec/domain-glossary.md` in the
   brief. Each outputs: the interface (types / methods / params + invariants /
   ordering / errors), a usage example, what's hidden behind the seam, the
   dependency strategy + adapters, and trade-offs.
3. **Present and compare.** Sequentially, then compare in prose by depth /
   locality / seam placement. Give your own recommendation; propose a hybrid if
   elements combine well. Be opinionated.

When the chosen interface implies a single file with enough internal parts that
it should become a package, hand the folderization off per
[`../_lib/folderize_deep_module.md`](../_lib/folderize_deep_module.md) — the
owned helper that turns a deep module into a package with a private internal
layout and a small public interface.
