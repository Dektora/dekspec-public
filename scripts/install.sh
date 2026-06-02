#!/usr/bin/env bash
# Unified DekSpec installer — lands the Python CLI, the vendored content, and
# the Claude Code plugin at the same version in one command.
#
# Usage:
#   bash scripts/install.sh [VERSION]
#
# Where VERSION is a semver tag (e.g., v0.95.0) or "latest" (default). The
# engine is acquired with pip-from-git against the curated PUBLIC MIRROR repo
# (ADR-034). For "latest" the highest release tag on the mirror is resolved via
# `git ls-remote --tags`; an explicit version arg short-circuits the resolve.
# pip-from-git pulls transitive dependencies from PyPI by default — there is no
# bespoke package index to configure.
#
# Layering — acquire, then reconcile, then plugin (plugin LAST, because it
# depends on the engine + the reconciled vendored content):
#
#   1. Resolve the target ref (highest mirror tag for `latest`; explicit
#      version arg short-circuits the resolve).
#   2. CLI:     pipx install "git+https://github.com/<MIRROR_REPO>.git@<REF>"
#               (transitive deps resolve from PyPI).
#   3. Content: dekspec library sync  (reconcile-only — vendoring-from-wheel +
#               migrate + breaking-guard + drift, against the just-installed
#               engine; no network, no pip, no plugin shell).
#   4. Plugin:  claude plugin marketplace add <MIRROR_REPO> (idempotent)
#               + claude plugin update dekspec@dekspec  (install on first-time).
#
# Re-running the script upgrades all three surfaces to the same version. The
# DekSpec source-of-truth repo is PRIVATE; consumers acquire everything from the
# curated public mirror (ADR-034) which carries only the redistributable
# surface (tooling/, plugin, templates, vendored docs, packaging, this script).
#
# Requirements: bash, git, pipx, claude CLI.

set -euo pipefail

# Curated public mirror repo (ADR-034). Single greppable constant — if the
# operator renames the mirror, change it here only.
MIRROR_REPO="Dektora/dekspec-public"
MIRROR_GIT_URL="https://github.com/${MIRROR_REPO}.git"

require_cmd() {
  local cmd="$1"
  local hint="${2:-}"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: \`$cmd\` is required but not on PATH." >&2
    [[ -n "$hint" ]] && echo "  Install: $hint" >&2
    exit 1
  fi
}

require_cmd git "https://git-scm.com/downloads"
require_cmd pipx "https://pipx.pypa.io/stable/installation/"
require_cmd claude "https://docs.claude.com/en/docs/claude-code/cli"

# Resolve the highest release tag on the mirror via `git ls-remote --tags`.
# Echoes a bare "vX.Y.Z" or empty (caller falls back to @main). No package
# index, no Python bootstrap — just git against the public mirror.
resolve_latest_tag() {
  git ls-remote --tags "$MIRROR_GIT_URL" 2>/dev/null \
    | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+$' \
    | sort -V \
    | tail -1
}

VERSION="${1:-latest}"
if [[ "$VERSION" == "latest" ]]; then
  echo "Resolving latest dekspec release tag from ${MIRROR_REPO}…"
  REF="$(resolve_latest_tag || true)"
  if [[ -z "$REF" ]]; then
    echo "Warning: no release tag found on ${MIRROR_REPO}; falling back to @main." >&2
    REF="main"
  fi
else
  # Explicit version: normalize to a v-prefixed tag ref.
  REF="$VERSION"
  [[ "$VERSION" != v* ]] && REF="v$VERSION"
fi

echo "Installing dekspec ${REF} (CLI + vendored content + plugin) from ${MIRROR_REPO}"
echo

echo "=== 1/3 CLI (pipx → pip-from-git, public mirror) ==="
pipx install --force "git+${MIRROR_GIT_URL}@${REF}"
echo

echo "=== 2/3 Content (dekspec library sync — reconcile against the installed engine) ==="
# Reconcile-only: vendors content from the just-installed wheel, runs migrate,
# checks the breaking-CHANGELOG guard, and reports drift. No network, no pip,
# no plugin shell — acquisition already happened in step 1. --yes auto-confirms
# the BREAKING-release prompt for non-interactive installs.
dekspec library sync --yes
echo

echo "=== 3/3 Claude Code plugin (marketplace) ==="
# `marketplace add` is idempotent; safe to re-run on every install.
claude plugin marketplace add "$MIRROR_REPO" 2>&1 | tail -2 || true
# Prefer `update` (refreshes existing consumers); `install` is a silent no-op
# when already present at the same scope. Fall back to `install` for first-time
# consumers when `update` reports the plugin is not yet installed.
if ! claude plugin update dekspec@dekspec 2>&1 | tail -3; then
  claude plugin install dekspec@dekspec 2>&1 | tail -3
fi
echo

echo "=== Verification ==="
echo "CLI version:    $(dekspec --version)"
echo "Plugin install: see \`claude plugin list\`"
echo
echo "Install complete. CLI + content + plugin at ${REF}."
