---
name: use-worktrees
description: Create/enter/clean up a delivery-scoped git worktree (ib/<slug> for a standalone IB, int/<slug> for an Intent, msn/<slug> for a Mission) per ADR-048 and ADR-058 — one worktree = one branch = one pull request = one delivery unit. Bootstrap it, write the statusline active_worktree hint, and remove it on land.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
# override-reason: pure-git worktree mechanic — runs setup-worktree.sh, authors no spec files
allowed-tools: Read Bash
disable-model-invocation: false
argument-hint: [--help] [--scope ib|intent|mission] [--slug <slug>] [--cleanup]
---

Create, enter, and clean up a **delivery-scoped git worktree** — the delivery mechanic of ADR-048 as revised by ADR-058: **one worktree = one branch = one pull request = one delivery unit**. The delivery unit is a single IB, an Intent's IBs, or a Mission cluster; acceptance stays per IB, and verification and review cover the delivery's final head (`dekspec delivery verify`, `dekspec delivery check`). An **Intent** gets its own `int/<slug>` worktree; a **Mission** cluster gets a shared `msn/<slug>` worktree. A standalone IB needs no parent artifact (ADR-056): a small one may skip the worktree (ADR-048 allows it); a larger one gets its own `ib/<slug>` worktree (`--scope ib`). This is a **core** skill — it *is* the delivery mechanic (fails the ADR-047 removability test), not a DekTools convenience.

> **Structural isolation.** Working an Intent/Mission in its own worktree keeps parallel work from contaminating each other's tree and keeps `main` clean of in-flight cluster work. The one job this skill does that habit doesn't: it **bootstraps** the fresh worktree so an agent dropped into it doesn't fail on missing gitignored state, and it writes the statusline `active_worktree` hint so you can see which worktree is live.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/use-worktrees"
one_line:   "Create/enter/clean up a delivery-scoped git worktree (ADR-048)"
modes:
  - { flag: "--scope", args: "ib|intent|mission", description: "Delivery scope: `ib` -> `ib/<slug>` worktree (a standalone IB); `intent` -> `int/<slug>` worktree (one Intent's IBs); `mission` -> `msn/<slug>` shared worktree (a Mission cluster)." }
  - { flag: "--slug", args: "<slug>", description: "The Intent/Mission slug the branch + worktree are named for." }
  - { flag: "--cleanup", args: "", description: "Remove the worktree + its branch, prune, and clear the statusline hint. Run on land." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/use-worktrees --scope intent --slug INT-190-use-worktrees-skill"
  - "/use-worktrees --scope mission --slug msn-020-agentic-best-practices"
  - "/use-worktrees --cleanup --scope intent --slug INT-190-use-worktrees-skill"
  - "/use-worktrees --help"
extra_sections:
  - heading: "WHEN TO USE"
    body:
      - "Starting a standalone IB large enough to isolate -> --scope ib"
      - "Starting an Intent's delivery -> --scope intent"
      - "Starting a Mission cluster (shared branch of related Intents) -> --scope mission"
      - "On land, after /dekspec:land-intent's operator-confirmed merge -> --cleanup"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

## Mode Detection

Parse `$ARGUMENTS` and route:

- `--help` present → render **Help Mode** above and stop.
- `--cleanup` present → **cleanup branch**: run `setup-worktree.sh --cleanup` with the resolved `--scope`/`--slug`, then surface its output (Step 3–5 below).
- otherwise → **create branch**: resolve `--scope` (`ib` | `intent` | `mission`) and `--slug`, then run `setup-worktree.sh` to create/enter the worktree (Step 2–5 below).

Both `--scope` and `--slug` are required for the create and cleanup branches; if either is missing, the script exits non-zero — surface the message and stop.

## Steps

1. **Parse** `$ARGUMENTS` for `--scope`, `--slug`, `--cleanup`, `--help` per Mode Detection above.
2. **Confirm the delivery scope matches ADR-048 / ADR-058:** an Intent's IBs (or a standalone IB) are `intent`; a Mission cluster is `mission`. If the caller is mid-Mission, use `mission`; otherwise `intent`. Everything the delivery lands — code, specs, and the IBs' execution records under `.dekspec/execution/` — is committed on this branch; the landing gate and CI read the records at the pull-request head.
3. **Run the mechanical core** — `scripts/setup-worktree.sh` — forwarding the resolved flags:
   ```bash
   bash "$(dirname "$0")/scripts/setup-worktree.sh" --scope <scope> --slug <slug>
   # or, on land:
   bash "$(dirname "$0")/scripts/setup-worktree.sh" --cleanup --scope <scope> --slug <slug>
   ```
4. **Surface the script's output verbatim** — the worktree path, the branch, the statusline-hint path, and the DekSpec-adapted bootstrap checklist (copy `.env`-class files; run this worktree's code via `PYTHONPATH=tooling python3 -m dekspec.cli …` because the editable `dekspec` on PATH pins to the primary checkout; rebuild `_vendored` if you touched templates/docs/plugins; hydrate the `br` tracker workspaces by running `br` once in each — never hand-copy a DB).
5. **On create**, `cd` into the new worktree before doing task work. **On land**, run `--cleanup` only after `/dekspec:land-intent` has passed `dekspec delivery check` and the operator-confirmed merge is done — and warn that uncommitted work (including uncommitted execution records) in a removed worktree is gone.

## Notes

- Scope naming is fixed by ADR-048: `int/<slug>` + `<repo>-int-<slug>` for Intents, `msn/<slug>` + `<repo>-msn-<slug>` for Missions. There is no per-IB or per-task pull request (ADR-058).
- The bootstrap checklist is *surfaced*, not run blindly — copying env files and installing deps are environment-specific, so the operator/agent runs them in the fresh worktree.
- Mechanics harvested from the generic `davidondrej/skills` git-worktree guide (the primary-vs-worktree detection one-liner + the "make the worktree complete" checklist), adapted to DekSpec's bootstrap quirks. The generic skill is not vendored.
