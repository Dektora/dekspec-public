---
name: rotation-handoff
description: Native DekSpec session continuity — emit and read a structured, secret-redacted handoff record (objective, artifacts touched, decisions, open questions, commands run, test status, files changed, next safest action) under `dekspec/.scratch/rotation-handoff/`, so a rotated or compacted session resumes from a DekSpec-authored record with zero runtime dependency on `claude-mem`. Artifacts are referenced by path, never copied. Front-ends the same native engine the session-end/session-start hooks drive.
mode: lite
model: claude-opus-4-7
reasoning_effort: high
disable-model-invocation: false
allowed-tools: Read Write Edit Bash
argument-hint: [--help] [--write | --read] [--at PATH]
related_skills: [using-dekspec, setup-dekspec, diagnose-bug]
---

Generate or resume a **structured session handoff** so long-running DekSpec work
survives a context rotation or compaction without starting cold. This is the
on-demand front for the native rotation-handoff engine
(`dekspec.rotation_handoff`) — the same engine the session-lifecycle hooks
(`session-end-summary.py` emit, `session-start-bootstrap.py` read) drive
automatically on `Stop` / `SessionEnd` / `PreCompact` / `SessionStart`.

DekSpec owns continuity natively (MSN-020 D13 / INT-176): there is **zero
runtime dependency** on the external `claude-mem` plugin. `claude-mem` may
remain installed and coexist, but rotation-handoff is authoritative for DekSpec
continuity — it reads and writes only its own `dekspec/.scratch/rotation-handoff/`
store and does not consult, suppress, or double-inject into `claude-mem`.

## Starter Prompt

```prompt
/dekspec:rotation-handoff --write --at .

Write a structured handoff record for the current session: capture the
objective, the artifacts I touched (by path), decisions made, open questions,
commands run, test status, files changed, and the single next-safest-action a
fresh session should take. Apply secret-redaction before writing.
```

## Mode Detection

See [`_lib/mode_detection_template.md`](../_lib/mode_detection_template.md) for the canonical parse/routing contract. Default mode: **Write Mode**.

Parse `$ARGUMENTS` for the mode flag:

- **Help mode** — `--help` flag. Render the Help manifest below and stop.
- **Write mode** — `--write` flag (default). Optional `--at PATH` names the repo root (default: cwd). Assemble the structured handoff record and persist it.
- **Read mode** — `--read` flag. Read the most recent handoff record back and surface the prior objective + next-safest-action.

This skill exposes no lifecycle/audit/review flags of its own — it is a thin
continuity front, not an artifact-lifecycle authoring skill. (It is therefore
exempt from the `_lib/mode_dispatcher.md` universal-mode set, which applies only
to the `write-*` artifact-lifecycle skills.)

## Write Mode

Assemble the eight required fields from the session, then persist them via the
native engine. The engine applies secret-redaction, references artifacts by
path (never copying file bodies), and prunes to the retention limit.

1. **objective** — the one-line goal the session is pursuing.
2. **artifacts_touched** — repo-relative *path strings* for each artifact/file
   read or written (paths only — never inline file contents).
3. **decisions** — load-bearing decisions made this session.
4. **open_questions** — unresolved questions a fresh session must carry.
5. **commands_run** — notable commands (the engine redacts secrets in them).
6. **test_status** — the current test/verification signal (e.g. `pytest -q: green`).
7. **files_changed** — repo-relative paths of changed files (paths only).
8. **next_safest_action** — the single safest next step for a fresh session.

Persist by calling the engine (records land at
`<root>/dekspec/.scratch/rotation-handoff/handoff-<UTC-timestamp>.json`):

```bash
PYTHONPATH=tooling python3 - <<'PY'
from pathlib import Path
from dekspec.rotation_handoff import write_handoff
record = { ... the eight fields ... }
print(write_handoff(Path("."), record))
PY
```

The engine retains the newest `N = 10` records (`DEKSPEC_HANDOFF_KEEP` env
override) and prunes older ones by mtime.

### Secret-redaction (what the engine strips before write)

The engine applies a fixed initial pattern set to every captured string:
shell-style `KEY=value` env assignments whose key matches
`*_SECRET` / `*_TOKEN` / `*_KEY` / `*_PASSWORD` / `*_PASSWD` / `*_API*`, plus
bearer-token-looking blobs (`ghp_…`, `sk-…`, `xox*-…`, AWS `AKIA…`, and long
base64/hex runs). Never paste a raw secret into a field expecting the prose to
carry it — redaction is defensive, not a license to capture secrets. The
pattern set is the `_REDACTION_PATTERNS` tuple in
`tooling/dekspec/rotation_handoff.py` (documented expansion point).

## Read Mode

Read the newest handoff (by mtime) and surface the prior `objective` +
`next_safest_action` so the session resumes with continuity:

```bash
PYTHONPATH=tooling python3 - <<'PY'
from pathlib import Path
from dekspec.rotation_handoff import read_latest_handoff
print(read_latest_handoff(Path(".")))
PY
```

If no handoff exists, stay silent — there is nothing to resume.

## Help Mode

See [`_lib/help_mode_template.md`](../_lib/help_mode_template.md) for the canonical Help rendering contract. Manifest for this skill:

```yaml
skill_name: "/dekspec:rotation-handoff"
one_line:   "Native session continuity — emit/read a structured, secret-redacted handoff under dekspec/.scratch/rotation-handoff/ (zero claude-mem dependency)"
modes:
  - { flag: "--write", args: "[--at PATH]", description: "Write mode (default) — assemble the eight-field structured handoff (objective / artifacts touched / decisions / open questions / commands run / test status / files changed / next safest action) and persist it secret-redacted, artifacts by path, to dekspec/.scratch/rotation-handoff/." }
  - { flag: "--read", args: "[--at PATH]", description: "Read mode — read the most recent handoff back and surface the prior objective + next-safest-action to resume." }
  - { flag: "--help", args: "", description: "Show this help message." }
examples:
  - "/dekspec:rotation-handoff --write --at ."
  - "/dekspec:rotation-handoff --read"
  - "/dekspec:rotation-handoff --help"
storage: "dekspec/.scratch/rotation-handoff/handoff-<UTC-timestamp>.json (gitignored ephemeral zone; newest N=10 retained)"
```

At runtime, render the manifest per `_lib/help_mode_template.md` and stop.

**End of Help Mode.**

## When to use

- Before a deliberate context rotation/compaction, to capture a structured record of where the session is so a fresh session resumes cleanly.
- At the start of a fresh session, to resume from the most recent handoff (the session-start hook does this automatically; this skill is the manual equivalent).
- When `claude-mem` is uninstalled and you want native DekSpec continuity to stand on its own.

## When NOT to use

- To persist durable spec decisions — those belong in DekSpec artifacts via `/write-*`, not in the ephemeral `.scratch/` handoff.
- To store secrets — `.scratch/` is gitignored but the handoff is a continuity aid, not a secret store; the engine redacts defensively.

## Related

- `session-end-summary.py` / `session-start-bootstrap.py` — the session-lifecycle hooks that drive the same engine automatically (`Stop` / `SessionEnd` / `PreCompact` / `SessionStart`).
- `tooling/dekspec/rotation_handoff.py` — the native engine this skill front-ends.
- `/dekspec:using-dekspec` — the onboarding entry point + catalog.
- AE-006 (Skills Library) — the AE this skill and the session-lifecycle hooks register under.
- ADR-040 / INT-165 (α) — the `dekspec/.scratch/` ephemeral governed zone the handoff writes into.
