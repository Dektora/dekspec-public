# Vendored asset resolution (INT-097)

This library uses a small set of vendored assets — templates, methodology
docs, the operating guide. Skills and agents reference them by their
**consumer-vendored paths** (e.g., `dekspec/templates/intent-template.md`,
`dekspec/dekspec-operating-guide.md`) for historical consistency.

After INT-097, those paths are *one* of two valid resolution layouts:

1. **Consumer-vendored copy** (`dekspec/templates/<x>-template.md`,
   `dekspec/<doc>.md`). Present when the consumer has run
   `scripts/install-dekspec.sh` or has authored a customised override.
2. **Wheel `_vendored/` fallback** — populated automatically by
   `pip install dekspec`. Resolved by the CLI verb introduced in INT-097.

When the consumer-vendored path does not exist (pip-only install, no
custom override), resolve any vendored reference via the
`dekspec resource` CLI verb:

```bash
# Templates — resolve by short name. `-template` suffix is auto-appended.
#   "intent" → templates/intent-template.md
dekspec resource template intent --path-only   # absolute path
dekspec resource template intent               # file content

# Methodology docs — resolve by short name. `dekspec-` prefix is auto-appended.
#   "operating-guide" → docs/dekspec-operating-guide.md
dekspec resource doc operating-guide --path-only
dekspec resource doc operating-guide
```

Consumer-fs copies override the wheel fallback when both exist
(customization wins; the wheel is the default-on-install). The resolver
implementation lives at `dekspec.vendoring.resolve_template()` and
`dekspec.vendoring.resolve_doc()`.

**For skill / agent prose:** when you cite a path like
`dekspec/templates/X-template.md`, the consuming LLM agent should treat it
as a reference — if the literal path does not exist in the consumer
repo, fall back to `dekspec resource template X` (or `dekspec resource
doc <name>` for methodology docs).
