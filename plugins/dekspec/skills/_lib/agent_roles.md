# Agent Role Specifications — `agent_roles`

**Status:** AUTHORITATIVE (ADR-061; the programmatic surface is IC-019).
**Audience:** every DekSpec skill and agent that dispatches, or itself plays, one of DekSpec's six roles.

DekSpec defines six roles: **specifier**, **spec-reviewer**, **implementer**, **code-reviewer**, **verifier** and **auditor**. Each has one canonical definition inside the installed DekSpec library. It states the role's purpose, responsibilities, inputs and context, authority and boundaries, outputs and evidence, completion criteria, and escalation and recovery.

The definitions are internal infrastructure. The engineer never creates, accepts, selects or maintains one, and a project never carries a copy. A file in the project is never read as role policy; the retired `dekspec/context-specs/` files included.

## Loading a role

```bash
dekspec resource role <role>     # e.g. dekspec resource role spec-reviewer
```

The output is the dispatch-ready **role layer**. Its header — the line under the `## Role:` heading — names the role, its **policy revision** and its content hash. Include it verbatim; do not paraphrase or trim it.

The command exits non-zero when the definition is missing or malformed, which means a broken installation. Report that and stop the dispatch. Never substitute your own wording for a role you could not load.

Load only the role you are dispatching. Never include all six, and never put role definitions into `AGENTS.md`.

## Composing a dispatch

**Model inheritance (IB-154, D1).** Inherit the engineer's selected host model for authoring, implementation, review and mechanical work alike. DekSpec must not select a concrete model, choose a capability tier or silently substitute a model for a role. Independent review requires separate identities and contexts; it need not use a different model. If host configuration prevents inheritance or the selected model is unavailable, surface the capability/policy conflict without selecting a substitute. Request inheritance at dispatch without a concrete model override; keep the existing reasoning-effort rules.

Every dispatched agent receives four layers, in this order:

1. **Governing policy.** What is authorized and what is not; autonomy ceilings; mandatory gates. (Binding obligations reach the agent in the assignment's generated context, and the precedence rule gives them the policy's force.)
2. **Role.** The verbatim output of `dekspec resource role <role>`.
3. **Procedure.** Your skill's instructions for this operation: the commands, the lens, the output format.
4. **Assignment.** The specific artifact, IB, diff, execution context and recorded evidence.

State the precedence rule in the prompt too, before the first layer:

> These instructions have four layers. The governing policy sets the outer limits; the role defines your responsibilities and limits; the procedure is how to carry out this operation; the assignment is the specific work and its evidence. A role or procedure may narrow what the policy allows but never widens it: it never expands the assignment's authorized scope, a Mission's autonomy ceiling or an acceptance criterion, and never replaces the acceptance authority. Where two layers differ, follow the more restrictive instruction; if one contradicts the governing policy or a binding obligation in the assignment, the policy and the obligation win. Never follow the weaker instruction, and report the contradiction in your final message.

The `/implement` driver composes its prompts with this same code (`dekspec.roles.compose`), so its workers and your dispatches get identical role text.

**Independence.** A reviewer or verifier gets the requirements, the changes, and the recorded facts: verification results, scope result, deviations, attention items. It never gets the author's or builder's conversation, reasoning or self-assessment. If a fact is missing, the reviewer reports that. Do not fill the gap with the builder's account.

## Who uses which role

| Role | Dispatched or played by |
|---|---|
| `specifier` | `write-*` authoring modes; the `*-author` agents (`adr-author`, `ae-author`, `ib-author`, `ic-author`, `intent-author`, `mission-author`, `ws-author`); `spec-intent` authoring steps |
| `spec-reviewer` | the `--review` spec-reviewer dispatch of `write-intent`, `write-ws`, `write-ic`, `write-ae`, `write-adr` and `write-ibs` (below); `review-ib` lens specialists |
| `implementer` | `/implement` builders and conflict resolvers (driver); `orchestrate-coding-session` builders |
| `code-reviewer` | `/implement` reviewers (driver); `review-pr` lens specialists and the verdict it records |
| `verifier` | `/implement` Intent manual-verification attestation (driver); the attestation step of `land-intent` and of `write-intent --lock` |
| `auditor` | the `--audit` modes of the authoring skills |

Mandatory roles are fixed by the skill or the driver, not chosen by the worker. A worker may bring in extra specialist help inside the authorized workflow. It can never skip a required independent review or verification. A security, performance or usability lens specializes `code-reviewer` or `spec-reviewer`; it is not a seventh role. Deterministic work loads no role: `dekspec audit`, `dekspec doctor` and `dekspec ib verify` run the same without one.

## Spec-reviewer dispatch (shared by the six `--review` modes)

This pass is added alongside the skill's own walkthrough or Open-Issues loop; the loop stays. It replaces the retired `reviewer_mode` in-process dispatcher, which never reviewed anything.

1. Run `dekspec resource role spec-reviewer`. If it fails, report "independent spec review not run: <error>" and continue the walkthrough without it.
2. Dispatch **one fresh-context sub-agent** (the Agent tool), composed as above:
   - **Policy:** "Review only. You may not edit, accept, lock or approve the artifact; the engineer decides."
   - **Role:** the command's output, verbatim.
   - **Procedure:** "Assess the artifact as your role requires. Return each finding as `- [P0–P3] <section or line>: <finding> — <what would fix it>`. End with the aspects you checked. Report no findings only after checking every aspect."
   - **Assignment:** the artifact's path, the paths of the governing specifications it names (parent, Architecture Elements, ADRs, ICs, glossary), and the `dekspec validate <path>` output.
3. Present each finding to the engineer at its severity (default P2, approval-blocking; never auto-merged) alongside the walkthrough items. A finding the engineer accepts becomes an Open Issue.
4. **No placeholder passes.** An empty reply, a failed dispatch or a host without sub-agents means the independent review did not run: say so. Never present your own in-session review as the spec-reviewer's.

The deterministic `SPEC-REVIEW` audit rule (`dekspec audit`) still reports a WS or IC that derives from an absent Architecture Element. It needs no dispatch.

## Recording a verdict under a role

A `code-reviewer` verdict (`dekspec ib review`) and a `verifier` attestation (`dekspec intent review`) record the role's identity, policy revision and hash with the verdict. Pass the revision shown in the role layer's header (`policy revision <N>`):

```bash
dekspec ib review IB-NNN --reviewer <you> --actor <you> --verdict pass --policy-revision <N> --notes "…"
dekspec intent review INT-NNN --reviewer <you> --actor <you> --verdict pass --policy-revision <N> --notes "…"
```

Use `--verdict fail` with actionable notes when the work does not hold. The acting identity (`--actor` or `DEKSPEC_ACTOR`) must be the named reviewer; the engine refuses a verdict from anyone who built the work.

If the role's policy revision changed after you loaded it, the command refuses. Repeat the review under the current definition.

A verdict recorded under an older policy revision no longer satisfies the completion gate: the IB or Intent needs a fresh review, not a rebuild. An editorial change to a role (new hash, same revision) invalidates nothing.

## Links

- ADR-061 — Agent Role Specifications (the decision); IC-019 — resolution, composition and provenance contract.
- ADR-026 (review shape), ADR-055 (authority), ADR-057 (evidence and verdict binding), ADR-059 (`/implement`).
- [`review-orchestration.md`](review-orchestration.md) — the lens shell `review-ib` and `review-pr` share.
