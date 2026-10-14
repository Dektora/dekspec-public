# Harness Seam — skill-author reference

DekSpec talks to its host (Claude Code, and future siblings) through ONE narrow
interface: the **harness seam**. Skill authors never call host tools directly —
they go through `dekspec.harness`.

## The five capabilities

| Primitive            | What it does                                        |
| -------------------- | --------------------------------------------------- |
| `dispatch_subagents` | Fan a set of tasks out to sub-agents.               |
| `invoke_skill`       | Invoke a named skill.                               |
| `ask_user`           | Ask the operator a question.                        |
| `register_hook`      | Wire a lifecycle hook (registration-only).          |
| `capabilities()`     | Report the per-primitive capability matrix.         |

Each primitive reports `"native"`, `"degraded"`, or `"unsupported"` per host via
`capabilities()`. On Claude, all four are `native`. On Codex
(`get_adapter("codex")`), all four are `native` too (spike 2026-06-15). On
Antigravity (`get_adapter("antigravity")`), all four are `native` as well
(spike 2026-06-15: dynamic parallel subagents + extension hooks). On Cursor
(`get_adapter("cursor")`), all four are `native` too — including
`dispatch_subagents` (spike 2026-06-15 overturned the "Cursor sequential-only"
premise: Cursor 2.5+ has async nested parallel sub-agents). On Copilot
(`get_adapter("copilot")`), all four are `native` as well — the adapter
targets the *interactive* surface (VS Code agent mode + Copilot CLI `/fleet`
parallel subagents, the open Agent Skills standard, interactive prompts, and
`.github/hooks/*.json`; spike 2026-06-16). On Pi (`get_adapter("pi")`), all
four are `native` too — Pi (pi.dev minimal terminal harness) realizes parallel
`dispatch_subagents` via the community `@tintinweb/pi-subagents` extension, with
the open Agent Skills standard, interactive prompts, and `pi.events` lifecycle
hooks (spike 2026-06-16). The extension dependency is a documented note, not a
new capability value (IC-017's vocabulary is LOCKED).

## The in-process invariant (ADR-024)

The seam is **in-process only**. There is no out-of-process executor, no
subprocess dispatch backend, and no lifecycle DB. The adapter guarantees result
*shape*, *ordering* (index-aligned: `result[i]` ↔ `tasks[i]`), and per-task
*failure isolation* — but the per-task work is delegated to an injectable
executor. An unsatisfiable, non-degradable request raises a typed
`HarnessUnsupported(primitive, host, reason)` — never a partial/fabricated
result.

## Using it

```python
from dekspec.harness import get_adapter

adapter = get_adapter()        # baseline Claude adapter
adapter.capabilities()         # {"dispatch_subagents": "native", ...}
```

`get_adapter(host)` resolves `None`/`"claude"` to the Claude adapter,
`"codex"` to the Codex adapter, `"antigravity"` to the Antigravity adapter,
`"cursor"` to the Cursor adapter, `"copilot"` to the Copilot adapter, and
`"pi"` to the Pi adapter; any other host raises `HarnessUnsupported`. See
`tooling/dekspec/harness/`.
