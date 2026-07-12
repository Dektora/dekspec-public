---
description: DekSpec overview — philosophy, the nine IR types, status lifecycles, audit families, and a typical end-to-end workflow. The in-Claude-Code analogue of a unix man page.
allowed-tools: Read
argument-hint: [no arguments]
disable-model-invocation: false
---

Display the DekSpec overview document.

## Steps

1. Resolve the overview path. Probe in this order; use the first hit:
   - `docs/dekspec-overview.md` (library-side path; matches when cwd is the dekspec repo itself OR when a consumer vendored `docs/` into its tree)
   - `dekspec/dekspec-overview.md` (consumer-side override path, when present)
   - Output of `dekspec resource doc overview --path-only` (wheel-bundled fallback; INT-097)
   - `${CLAUDE_PLUGIN_ROOT}/../../docs/dekspec-overview.md` (plugin-side fallback)
2. Read the overview file at the resolved path.
3. Render the body verbatim in the chat. Do not summarize, paraphrase, or restructure — operators reading `man <thing>` expect the canonical document, not a re-derivation.
4. If no candidate path resolved, surface: "DekSpec overview document not found. Re-install dekspec (`pip install --upgrade dekspec`, or `pipx install dekspec`) then run `dekspec sync` to refresh vendored content." and stop.

## When to use

- First time touching DekSpec in a session — orient on philosophy + artifact spine before diving into a specific authoring skill.
- Onboarding a new operator to the framework's mental model.
- Re-reading the workflow loop when a specific lifecycle step is unclear (use `/dekspec:doctor` for a graph-level audit, `/dekspec:using-dekspec` for skill-by-skill onboarding).

## Related

- `/dekspec:using-dekspec` — operator-facing skill catalog + onboarding walker.
- `/dekspec:doctor` — full audit (schema + linkage + drift + T/D/L fidelity).
- `docs/dekspec-methodology.md` — the long-form methodology reference (linked from the overview's See also section).
