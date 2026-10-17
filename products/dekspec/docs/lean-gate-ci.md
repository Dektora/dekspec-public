# Run the lean gate in your project's CI

Copy this workflow into `.github/workflows/lean-gate.yml`, or copy its job into
an existing workflow that runs on every pull request. Make the check named
exactly `lean gate` required in your branch protection or ruleset. Lean refuses
to land a change without a passing check under that name.

The example is for a Node project using pnpm and vitest. Change the marked
runner, language setup and services to match your project. Keep your pnpm
version in `package.json`'s `packageManager` field and vitest in the project's
locked dependencies. The guard runs a lean brief's tests at the test author's
commit, so it needs the project's runner, dependencies and services, including
any database setup and environment variables those tests require. The runner
must support bash, git and Python virtual environments.

Do not edit the judging step. Its only setting is `DEKSPEC_SOURCE`, declared
once in the job's environment. Leave it as the public mirror below, or replace
it with the git URL of your own release mirror. That source must provide the
same `v<release>` tags. The judge line names the source used.

Commit `.dekspec-version` at the project root with a release such as `0.130.0`
(without the `v` prefix). The judge reads that file from the merge commit's first
parent, so a pull request that changes the pin is judged by the old release.
It installs that tag and its dependencies in a fresh environment, checks its
version, and then judges the merge commit's two parents. A missing pin, failed
install or wrong installed version fails with the base and cause. There is no
fallback to the head's pin, an existing installation or the latest release.
An older release without the guard passes with `judge predates lean`.

```yaml
name: Lean checks
on: pull_request
permissions:
  contents: read

jobs:
  lean-gate:
    name: lean gate
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest # Project: change to your runner.
    # Project: add the services your tests need (for example, PostgreSQL).
    services: {}
    env:
      DEKSPEC_SOURCE: https://github.com/Dektora/dekspec-public.git
    steps:
      - name: Checkout merge candidate with full history
        uses: actions/checkout@v5
        with:
          fetch-depth: 0
      # Project: change this language setup and dependency installation as needed.
      - name: Set up pnpm from package.json
        uses: pnpm/action-setup@v4
      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: pnpm
      - name: Install project dependencies, including vitest
        run: pnpm install --frozen-lockfile
      - name: Set up Python for the isolated judge
        uses: actions/setup-python@v6
        with:
          python-version: '3.13'
      - name: Judge with the base release (do not edit)
        shell: bash
        run: |
          set -euo pipefail
          unset PYTHONHOME PYTHONPATH DEKSPEC_BASE DEKSPEC_LIBRARY_ROOT
          judge_base=$(git rev-parse --verify HEAD^1)
          fail() {
            printf 'judge failed for base %s: %s\n' "$judge_base" "$*" >&2
            exit 1
          }
          trap 'fail "unexpected failure at line $LINENO"' ERR
          judge_head=$(git rev-parse --verify HEAD^2)
          if ! release=$(git show "$judge_base:.dekspec-version" 2>/dev/null); then
            fail 'missing or unreadable .dekspec-version'
          fi
          [ -n "$release" ] || fail 'empty .dekspec-version'
          printf 'judge: %s dekspec %s from %s\n' "$judge_base" "$release" "$DEKSPEC_SOURCE" \
            | tee -a "$GITHUB_STEP_SUMMARY"
          [[ "$release" =~ ^[0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.+-]*$ ]] \
            || fail "invalid release in .dekspec-version: $release"
          judge_root=$(mktemp -d "$RUNNER_TEMP/dekspec-judge.XXXXXX")
          python3 -I -m venv "$judge_root/venv" \
            || fail 'cannot create isolated judge environment'
          judge_python="$judge_root/venv/bin/python"
          judge_cli="$judge_root/venv/bin/dekspec"
          "$judge_python" -I -m pip install "git+$DEKSPEC_SOURCE@v$release" \
            || fail "cannot install release $release from $DEKSPEC_SOURCE"
          if ! installed=$("$judge_python" -I "$judge_cli" --version); then
            fail "cannot read installed judge version; expected $release"
          fi
          [ "$installed" = "dekspec $release" ] \
            || fail "wrong judge version: expected $release, got $installed"
          if ! judge_help=$("$judge_python" -I "$judge_cli" delivery --help); then
            if ! judge_help=$("$judge_python" -I "$judge_cli" --help); then
              fail "cannot inspect commands of release $release"
            fi
            if grep -qw 'delivery' <<< "$judge_help"; then
              fail "cannot inspect delivery commands of release $release"
            fi
            echo 'judge predates lean'
            exit 0
          fi
          if ! grep -qw 'lean-guard' <<< "$judge_help"; then
            echo 'judge predates lean'
            exit 0
          fi
          "$judge_python" -I "$judge_cli" delivery lean-guard \
            --base "$judge_base" --head "$judge_head" || {
              verdict=$?
              printf 'lean-guard failed for base %s (exit %s)\n' "$judge_base" "$verdict" >&2
              exit "$verdict"
            }
```

The first line of the judging step's log and its step summary identify the
base commit, release and source. Once the judge is installed and verified, the
step returns the guard's verdict; a change delivering no lean brief is an
ordinary pass. Keep the checkout on GitHub's pull request merge commit and
retain full history so the guard can read both parents and the author's commit.
