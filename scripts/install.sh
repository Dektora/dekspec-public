#!/usr/bin/env bash
# Unified DekSpec installer — lands the Python CLI, the vendored content, and
# the per-host delivery for one harness platform at the same version in one
# command.
#
# Usage:
#   bash scripts/install.sh [VERSION] [--platform <host>]
#
# Where VERSION is a semver tag (e.g., v0.95.0) or "latest" (default), and
# <host> is one of: claude (default), codex, antigravity, cursor, copilot, pi.
# The engine is acquired with pip-from-git against the curated PUBLIC MIRROR
# repo (ADR-034). For "latest" the highest release tag on the mirror is resolved
# via `git ls-remote --tags`; an explicit version arg short-circuits the
# resolve. pip-from-git pulls transitive dependencies from PyPI by default —
# there is no bespoke package index to configure.
#
# Layering — acquire, then reconcile, then deliver per host (delivery LAST,
# because it depends on the engine + the reconciled vendored content):
#
#   1. Resolve the target ref (highest mirror tag for `latest`; explicit
#      version arg short-circuits the resolve).
#   2. CLI:     pipx install "git+https://github.com/<MIRROR_REPO>.git@<REF>"
#               (transitive deps resolve from PyPI).
#   3. Content: dekspec sync  (reconcile-only — vendoring-from-wheel +
#               migrate + breaking-guard + drift, against the just-installed
#               engine; no network, no pip, no plugin shell).
#   4. Deliver (per --platform):
#               claude → claude plugin marketplace add <MIRROR_REPO> + update
#                        (the managed Claude Code marketplace plugin path).
#               others → dekspec install --platform <host>  (emit the per-host
#                        skill/command/hook file tree into the cwd; INT-147).
#
# Steps 1–2 are host-agnostic; only step 4 differs per host. Re-running the
# script upgrades all surfaces to the same version. The DekSpec source-of-truth
# repo is PRIVATE; consumers acquire everything from the curated public mirror
# (ADR-034) which carries only the redistributable surface (tooling/, plugin,
# templates, vendored docs, packaging, this script).
#
# Requirements: bash, git, pipx (+ claude CLI only when --platform claude).

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

# Supported harness platforms (mirrors `dekspec install --platform` choices).
SUPPORTED_PLATFORMS="claude codex antigravity cursor copilot pi"

require_cmd git "https://git-scm.com/downloads"
require_cmd pipx "https://pipx.pypa.io/stable/installation/"
# `claude` is required only for the managed Claude plugin path (--platform
# claude); the require check runs after arg parsing, below.

# Resolve the highest release tag on the mirror via `git ls-remote --tags`.
# Echoes a bare "vX.Y.Z" or empty (caller falls back to @main). No package
# index, no Python bootstrap — just git against the public mirror.
resolve_latest_tag() {
  git ls-remote --tags "$MIRROR_GIT_URL" 2>/dev/null \
    | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+$' \
    | sort -V \
    | tail -1
}

# Parse args: an optional positional VERSION + an optional `--platform <host>`.
# Order-independent; VERSION defaults to "latest", platform to "claude".
VERSION="latest"
PLATFORM="claude"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform)
      [[ $# -ge 2 ]] || { echo "Error: --platform needs a value." >&2; exit 1; }
      PLATFORM="$2"; shift 2 ;;
    --platform=*)
      PLATFORM="${1#*=}"; shift ;;
    -h|--help)
      echo "Usage: bash scripts/install.sh [VERSION] [--platform <host>]"
      echo "  host: ${SUPPORTED_PLATFORMS// /, }"
      exit 0 ;;
    -*)
      echo "Error: unknown flag '$1'." >&2; exit 1 ;;
    *)
      VERSION="$1"; shift ;;
  esac
done

# Validate the platform against the supported set.
case " $SUPPORTED_PLATFORMS " in
  *" $PLATFORM "*) ;;
  *) echo "Error: unsupported --platform '$PLATFORM' (choose: ${SUPPORTED_PLATFORMS// /, })." >&2; exit 1 ;;
esac

# The managed Claude plugin path needs the `claude` CLI; other hosts do not.
if [[ "$PLATFORM" == "claude" ]]; then
  require_cmd claude "https://docs.claude.com/en/docs/claude-code/cli"
fi

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

echo "Installing dekspec ${REF} (CLI + vendored content + ${PLATFORM} delivery) from ${MIRROR_REPO}"
echo

echo "=== 1/3 CLI (pipx → pip-from-git, public mirror) ==="
pipx install --force "git+${MIRROR_GIT_URL}@${REF}"
echo

echo "=== 2/3 Content (dekspec sync — reconcile against the installed engine) ==="
# Reconcile-only: vendors content from the just-installed wheel, runs migrate,
# checks the breaking-CHANGELOG guard, and reports drift. No network, no pip,
# no plugin shell — acquisition already happened in step 1. --yes auto-confirms
# the BREAKING-release prompt for non-interactive installs.
dekspec sync --yes
echo

if [[ "$PLATFORM" == "claude" ]]; then
  echo "=== 3/3 Claude Code plugin (marketplace) ==="
  # `marketplace add` is idempotent; safe to re-run on every install.
  claude plugin marketplace add "$MIRROR_REPO" 2>&1 | tail -2 || true
  # Prefer `update` (refreshes existing consumers); `install` is a silent no-op
  # when already present at the same scope. Fall back to `install` for first-time
  # consumers when `update` reports the plugin is not yet installed.
  if ! claude plugin update dekspec@dekspec 2>&1 | tail -3; then
    claude plugin install dekspec@dekspec 2>&1 | tail -3
  fi
else
  echo "=== 3/3 Per-host delivery (dekspec install --platform ${PLATFORM}) ==="
  # Emit the per-host skill/command/hook tree into the cwd (INT-147). Writes
  # files only — never executes. The host picks the tree up natively.
  #
  # The plugin source (skills/commands/hooks) is NOT bundled in the wheel
  # (ADR-009 — it ships to Claude via the marketplace), so the just-installed
  # engine has no local plugin tree to emit from. Fetch the plugin from the
  # mirror at the SAME ref and pass it as --source. Shallow, blob-filtered,
  # sparse to just `plugins/` for speed; cleaned up on exit.
  PLUGIN_SRC="$(mktemp -d)"
  trap 'rm -rf "$PLUGIN_SRC"' EXIT
  echo "Fetching plugin source from ${MIRROR_REPO}@${REF}…"
  git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$REF" \
    --filter=blob:none --sparse "$MIRROR_GIT_URL" "$PLUGIN_SRC/repo"
  git -C "$PLUGIN_SRC/repo" sparse-checkout set plugins/dekspec >/dev/null
  PLUGIN_DIR="$PLUGIN_SRC/repo/plugins/dekspec"
  if [[ ! -d "$PLUGIN_DIR" ]]; then
    echo "Error: plugin tree not found at ${MIRROR_REPO}@${REF} (plugins/dekspec)." >&2
    exit 1
  fi
  dekspec install --platform "$PLATFORM" --source "$PLUGIN_DIR"
fi
echo

echo "=== Verification ==="
echo "CLI version:    $(dekspec --version)"
if [[ "$PLATFORM" == "claude" ]]; then
  echo "Plugin install: see \`claude plugin list\`"
else
  echo "Host delivery:  dekspec tree emitted for '${PLATFORM}' in $(pwd)"
fi
echo
echo "Install complete. CLI + content + ${PLATFORM} delivery at ${REF}."
