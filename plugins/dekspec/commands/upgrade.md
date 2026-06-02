---
description: Upgrade dekspec in this repo via the standard flow — pipx install + `dekspec library sync` (reconcile) + `claude plugin update`. The bespoke `dekspec repo upgrade` acquisition verb is DEPRECATED (ADR-032).
allowed-tools: Bash(dekspec library sync:*), Bash(dekspec --version:*), Bash(pipx install:*), Bash(claude plugin:*), Bash(git status:*), Bash(git diff:*)
argument-hint: [version]
disable-model-invocation: false
---

Upgrade dekspec in this repo. Per **ADR-032**, acquisition is done with
standard tools and reconcile is `dekspec library sync` — the old one-shot
`dekspec repo upgrade` acquisition verb is **deprecated** (it now just prints a
note and forwards to reconcile; it no longer acquires anything).

The canonical one-command path is the install script, which performs exactly
the three steps below in order:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Dektora/dekspec/main/scripts/install.sh) $ARGUMENTS
```

If you'd rather run the steps yourself, do them **in this order** (plugin LAST
— it depends on the upgraded engine and the reconciled content):

## Steps

1. Parse `$ARGUMENTS`. The version arg is optional — with a version
   (e.g. `0.53.0` or `v0.53.0`) pin it as a `@vX.Y.Z` ref; without one, use
   `@main` (latest) on the public mirror.

2. **Pre-flight**: run `git status --porcelain` via Bash. If there are
   uncommitted changes touching `dekspec/`, `.claude/skills/`,
   `.claude-plugin/`, or `pyproject.toml`, warn the operator and ask whether to
   proceed (they may want to commit first so the upgrade diff is isolable).

3. **Acquire the engine (pipx, pip-from-git against the public mirror).** Pin
   the version if one was given (`@vX.Y.Z`), else take the latest (`@main`):
   ```bash
   pipx install --force "git+https://github.com/Dektora/dekspec-public.git@vX.Y.Z"
   ```
   (pip-from-git pulls transitive deps from PyPI by default. Use `pip install`
   instead of `pipx` if dekspec lives in a project venv.)

4. **Reconcile the content** against the just-installed engine:
   ```bash
   dekspec library sync $ARGUMENTS
   ```
   This vendors content from the installed wheel, runs `dekspec migrate`,
   checks the breaking-CHANGELOG guard, and reports drift. It performs **no
   acquisition** (no network / pip / plugin shell) — that already happened in
   step 3. Pass `--dry-run` first if you want to preview the diff.

5. **Update the plugin** (LAST):
   ```bash
   claude plugin marketplace add Dektora/dekspec-public   # idempotent
   claude plugin update dekspec@dekspec             # `install` on first-time
   ```

6. On success, surface to the operator:
   - The before/after CLI version (`dekspec --version`).
   - The reconcile summary from `dekspec library sync` (vendored content
     counts; drift findings; migration results).
   - The plugin refresh result — remind them to restart Claude Code or run
     `/reload-plugins` so the new plugin content activates in their session.
   - The remaining manual step: review + commit the upgrade diff.

7. On error, surface the failing command's message. Common causes: pip index
   auth/conflict; local edits that conflict with vendored content (reconcile
   reports these as drift); plugin marketplace fetch failure.
