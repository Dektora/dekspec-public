# Security Checklist

Reference this from Implementation Briefs when the IB touches user input handling,
prompt construction, tool execution, persistent writes, or tenant boundaries.

---

## Prompt Injection

- [ ] User-controlled text that reaches the model is structurally isolated from instruction text (separate message roles, not string interpolation)
- [ ] Retrieved content from any store or external API (records, metadata, documents) is not interpolated directly into prompts
- [ ] Tool results are injected as `tool` role messages, not embedded in `assistant` or `system` messages
- [ ] No f-string, template, or concatenation mixes trusted instructions with untrusted content without a clear boundary

## Tool Call Safety

- [ ] All tool inputs are validated against a strict schema before execution
- [ ] Tool output is treated as untrusted data before being passed back to the model
- [ ] Agent loops have a maximum iteration bound
- [ ] Tools with write access have idempotency guarantees
- [ ] Tool access is scoped to minimum necessary — read-only tools have no write code path
- [ ] Model cannot invoke tools that weren't offered in the current turn

## Tenant Isolation

- [ ] Graph or database queries enforce tenant scope structurally, not just as a filter parameter
- [ ] Recursive queries and graph traversals have a maximum depth bound
- [ ] Similarity and search queries are tenant-scoped before ranking (not filtered after)
- [ ] Cache keys include tenant ID
- [ ] Logging/observability data with tenant-identifying content has access control

## Memory Poisoning

- [ ] Write paths to any persistent store that accept model-generated content have structural validation
- [ ] Stored content cannot later be retrieved and re-injected as system-level instructions
- [ ] All persistent writes carry provenance metadata (author, timestamp, session ID)
- [ ] Context assembly cannot be steered by injected stored content to prioritize attacker-controlled records

## Context Window Manipulation

- [ ] Inputs cannot push safety instructions out of effective attention window through padding/repetition
- [ ] Retrieved context cannot dominate the context window and crowd out system prompt instructions
- [ ] Token budget is bounded — inputs crafted to maximize context consumption are rejected

---

## Design Principles

1. **Structural isolation over sanitization** — sanitization is fragile. Separate message roles, parameterized queries, strict schemas make injection geometrically harder.
2. **Least privilege at every boundary** — model sees only what it needs; tools have minimal permissions; tenant context enforced at query layer.
3. **Assume retrieved content is adversarial** — retrieved content from any store or external API is potentially attacker-controlled.
4. **Audit trails for persistent writes** — any write from model output must carry provenance.

---

## Red Flags — Stop and Fix

- Model output written to persistent storage without structural validation
- Tenant ID enforced only in application code, not at the query layer
- Tool call inputs constructed from raw model output strings
- Retrieved content interpolated directly into system or user prompts
- Agent loops with no maximum iteration count
- Cross-tenant similarity results filtered after ranking rather than before
- A single compromised session can modify stored content affecting other sessions or tenants
