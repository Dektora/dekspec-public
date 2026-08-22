#!/usr/bin/env bash
# setup-worktree.sh — the mechanical core of the /use-worktrees skill (INT-190).
#
# Creates/enters a delivery-scoped git worktree per ADR-048 (worktree scope
# tracks delivery granularity), writes the statusline `active_worktree` hint,
# and cleans up on land. The SKILL.md is the guided front-end; this script is
# the deterministic, testable heart.
#
# Scope naming (ADR-048):
#   intent   -> branch int/<slug>      worktree <worktrees-root>/<repo>-int-<slug>
#   mission  -> branch msn-<slug>      worktree <worktrees-root>/<repo>-msn-<slug>
#
# Usage:
#   setup-worktree.sh --scope intent|mission --slug <slug> [--worktrees-root DIR] [--hint-root DIR]
#   setup-worktree.sh --cleanup --scope intent|mission --slug <slug> [--worktrees-root DIR] [--hint-root DIR]
#
# Env/flag overrides (mainly for tests):
#   --worktrees-root  where worktrees are created (default: parent of the repo)
#   --hint-root       statusline hint base (default: ~/.claude/projects)
#
# Bootstrap (DekSpec-adapted "make the worktree complete" checklist) is emitted
# as guidance to stdout rather than run blindly — copying .env-class files and
# installing deps are environment-specific and destructive-adjacent, so the
# skill surfaces them for the operator/agent to run in the fresh worktree.
set -euo pipefail

SCOPE="" SLUG="" CLEANUP=0 WORKTREES_ROOT="" HINT_ROOT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --scope) SCOPE="$2"; shift 2 ;;
    --slug) SLUG="$2"; shift 2 ;;
    --cleanup) CLEANUP=1; shift ;;
    --worktrees-root) WORKTREES_ROOT="$2"; shift 2 ;;
    --hint-root) HINT_ROOT="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "setup-worktree.sh: unknown arg '$1'" >&2; exit 2 ;;
  esac
done

[ -n "$SCOPE" ] && [ -n "$SLUG" ] || { echo "setup-worktree.sh: --scope and --slug are required" >&2; exit 2; }
case "$SCOPE" in
  intent) PREFIX="int" ;;
  mission) PREFIX="msn" ;;
  *) echo "setup-worktree.sh: --scope must be 'intent' or 'mission' (ADR-048)" >&2; exit 2 ;;
esac

# Detect primary checkout vs worktree; resolve the primary checkout path.
GIT_DIR="$(git rev-parse --path-format=absolute --git-dir)"
GIT_COMMON="$(git rev-parse --path-format=absolute --git-common-dir)"
PRIMARY="$(dirname "$GIT_COMMON")"
REPO="$(basename "$PRIMARY")"

BRANCH="${PREFIX}/${SLUG}"
: "${WORKTREES_ROOT:=$(dirname "$PRIMARY")}"
WORKTREE="${WORKTREES_ROOT}/${REPO}-${PREFIX}-${SLUG}"
: "${HINT_ROOT:=${HOME}/.claude/projects}"
HINT_FILE="${HINT_ROOT}/${REPO}/active_worktree"

if [ "$CLEANUP" -eq 1 ]; then
  # Land cleanup: remove the worktree + its branch, prune, clear the hint.
  if git -C "$PRIMARY" worktree list --porcelain | grep -qxF "worktree ${WORKTREE}"; then
    git -C "$PRIMARY" worktree remove --force "$WORKTREE"
  fi
  git -C "$PRIMARY" worktree prune
  if git -C "$PRIMARY" show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    git -C "$PRIMARY" branch -D "$BRANCH" >/dev/null 2>&1 || true
  fi
  rm -f "$HINT_FILE"
  echo "cleaned up worktree ${WORKTREE} + branch ${BRANCH} (hint cleared)"
  echo "NOTE: uncommitted work in a removed worktree is gone — commit early/often."
  exit 0
fi

# Create (or reuse) the worktree on its branch.
if [ -d "$WORKTREE" ]; then
  echo "worktree already exists: ${WORKTREE}"
else
  if git -C "$PRIMARY" show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    git -C "$PRIMARY" worktree add "$WORKTREE" "$BRANCH"
  else
    git -C "$PRIMARY" worktree add -b "$BRANCH" "$WORKTREE"
  fi
fi

# Statusline hint (24h TTL is enforced by the reader; we just write the path).
mkdir -p "$(dirname "$HINT_FILE")"
printf '%s\n' "$WORKTREE" > "$HINT_FILE"

cat <<EOF
worktree ready: ${WORKTREE}  (branch ${BRANCH}, scope ${SCOPE})
statusline hint written: ${HINT_FILE}

Bootstrap the fresh worktree before working (gitignored state is NOT copied):
  cd "${WORKTREE}"
  # 1. Copy env/secret files from the primary checkout (copy, never symlink):
  #      cp "${PRIMARY}/.env" .env  2>/dev/null || true   (if present)
  # 2. Python: this repo runs from source via PYTHONPATH=tooling; the pipx/
  #      editable 'dekspec' on PATH pins to the PRIMARY checkout, so exercise
  #      THIS worktree's code with:  PYTHONPATH=tooling python3 -m dekspec.cli ...
  # 3. Rebuild vendored content if you touched templates/docs/plugins:
  #      the _vendored tree is a build output (setup.py VendoringBuildPy).
  # 4. .beads: the SQLite DB re-derives from the tracked .beads/issues.jsonl —
  #      run 'br' once in the worktree to hydrate it; never hand-copy the DB.
  # 5. Delete this worktree on land:  setup-worktree.sh --cleanup --scope ${SCOPE} --slug ${SLUG}
EOF
