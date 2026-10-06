#!/bin/sh
# Cut a release: land the version bump through a pull request, run the checks
# CI runs, and push an annotated tag on the merged commit. The tag triggers
# .github/workflows/release.yml, which builds the artifacts and publishes the
# GitHub release from the matching CHANGELOG section.
#
# Usage: sh scripts/release.sh [--dry-run] <version>
#
# <version> is bare (1.1.0, not v1.1.0). CHANGELOG.md must already have a
# "## <version>" heading. --dry-run runs every check and prints each mutating
# command instead of running it.
#
# The bump goes through a squash-merged PR: the main ruleset requires one and
# GitHub signs the squash commit. If every pyproject.toml on main already
# reads <version>, the PR steps are skipped and the script only tags.
set -eu

_run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "+ $*"
  else
    "$@"
  fi
}

_parse_args() {
  _parse_args_dry_run=0
  _parse_args_version=""
  while [ $# -gt 0 ]; do
    case $1 in
      --dry-run)
        _parse_args_dry_run=1
        shift
        ;;
      -*)
        echo "release: unknown option '$1'" >&2
        exit 2
        ;;
      *)
        if [ -n "$_parse_args_version" ]; then
          echo "release: unexpected argument '$1'" >&2
          exit 2
        fi
        _parse_args_version=$1
        shift
        ;;
    esac
  done

  if [ -z "$_parse_args_version" ]; then
    echo "usage: sh scripts/release.sh [--dry-run] <version>" >&2
    exit 2
  fi
  if ! echo "$_parse_args_version" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "release: version '$_parse_args_version' does not match X.Y.Z" >&2
    exit 1
  fi
  DRY_RUN=$_parse_args_dry_run
  VERSION=$_parse_args_version
  TAG="v$VERSION"
  BRANCH="release-$VERSION"
  readonly DRY_RUN VERSION TAG BRANCH
}

_check_preconditions() {
  sh "$REPO_ROOT/scripts/check-release.sh" --changelog "$TAG"

  _check_preconditions_branch=$(git -C "$REPO_ROOT" branch --show-current)
  if [ "$_check_preconditions_branch" != "main" ]; then
    echo "release: must be on main, not '$_check_preconditions_branch'" >&2
    exit 1
  fi

  if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
    echo "release: worktree is not clean" >&2
    exit 1
  fi

  git -C "$REPO_ROOT" fetch origin main

  _check_preconditions_local=$(git -C "$REPO_ROOT" rev-parse main)
  _check_preconditions_remote=$(git -C "$REPO_ROOT" rev-parse origin/main)
  if [ "$_check_preconditions_local" != "$_check_preconditions_remote" ]; then
    echo "release: main has diverged from origin/main" >&2
    exit 1
  fi

  if git -C "$REPO_ROOT" tag --list "$TAG" | grep -Fxq "$TAG"; then
    echo "release: tag '$TAG' already exists locally" >&2
    exit 1
  fi

  if git -C "$REPO_ROOT" ls-remote --tags origin "$TAG" | grep -q "$TAG"; then
    echo "release: tag '$TAG' already exists on origin" >&2
    exit 1
  fi

  if gh release view "$TAG" >/dev/null 2>&1; then
    echo "release: release '$TAG' already exists" >&2
    exit 1
  fi
}

_set_versions() {
  for _set_versions_file in $PYPROJECTS; do
    _set_versions_tmp=$(mktemp "${TMPDIR:-/tmp}/release-pyproject.XXXXXX")
    sed "s/^version = \".*\"\$/version = \"$1\"/" "$_set_versions_file" >"$_set_versions_tmp"
    cat "$_set_versions_tmp" >"$_set_versions_file"
    rm -f "$_set_versions_tmp"
  done
}

_bump_version() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "+ set version to $VERSION in $PYPROJECTS"
    return
  fi
  _set_versions "$VERSION"
  (cd "$REPO_ROOT" && uv lock)
}

_run_release_check() {
  # --dry-run never writes the bump, so simulate it for this one check and
  # restore the files afterwards.
  if [ "$DRY_RUN" -eq 1 ]; then
    _run_release_check_backup=$(mktemp -d "${TMPDIR:-/tmp}/release-backup.XXXXXX")
    _run_release_check_index=0
    for _run_release_check_file in $PYPROJECTS; do
      _run_release_check_index=$((_run_release_check_index + 1))
      cp "$_run_release_check_file" "$_run_release_check_backup/$_run_release_check_index"
    done
    trap '_restore_versions "$_run_release_check_backup"' EXIT
    trap 'exit 130' INT TERM
    _set_versions "$VERSION"
    _run_release_check_status=0
    sh "$REPO_ROOT/scripts/check-release.sh" "$TAG" || _run_release_check_status=$?
    _restore_versions "$_run_release_check_backup"
    trap - EXIT INT TERM
    return "$_run_release_check_status"
  fi
  sh "$REPO_ROOT/scripts/check-release.sh" "$TAG"
}

_restore_versions() {
  _restore_versions_index=0
  for _restore_versions_file in $PYPROJECTS; do
    _restore_versions_index=$((_restore_versions_index + 1))
    cat "$1/$_restore_versions_index" >"$_restore_versions_file"
  done
  rm -rf "$1"
}

_run_tests() {
  (
    cd "$REPO_ROOT"
    uv run ruff check .
    uv run ruff format --check .
    QT_QPA_PLATFORM=offscreen uv run pytest -q
  )
}

_is_bumped() {
  for _is_bumped_file in $PYPROJECTS; do
    _is_bumped_current=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$_is_bumped_file" | head -n1)
    [ "$_is_bumped_current" = "$VERSION" ] || return 1
  done
}

_check_branch_absent() {
  if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$BRANCH"; then
    echo "release: branch '$BRANCH' already exists locally" >&2
    exit 1
  fi
  if git -C "$REPO_ROOT" ls-remote --heads origin "$BRANCH" | grep -q .; then
    echo "release: branch '$BRANCH' already exists on origin" >&2
    exit 1
  fi
}

_commit_and_push_branch() {
  # shellcheck disable=SC2086 # PYPROJECTS is a space-separated path list
  _run git -C "$REPO_ROOT" add $PYPROJECTS "$REPO_ROOT/uv.lock"
  _run git -C "$REPO_ROOT" commit -m "Release $VERSION"
  _run git -C "$REPO_ROOT" push -u origin "$BRANCH"
  _run git -C "$REPO_ROOT" switch main
}

_open_pr() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "+ gh pr create --base main --head $BRANCH --title 'Release $VERSION'" >&2
    echo "<pr-url>"
    return
  fi
  gh pr create --base main --head "$BRANCH" --title "Release $VERSION" \
    --body "Version bump for $VERSION; scripts/release.sh tags after merge and release.yml publishes."
}

_await_checks() {
  _await_checks_pr_url=$1
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "+ gh pr checks $_await_checks_pr_url --watch --fail-fast"
    return
  fi
  # A new PR reports no checks for a few seconds, and --watch on none exits
  # at once, so wait for the first check to register.
  _await_checks_tries=0
  while [ "$(gh pr checks "$_await_checks_pr_url" --json name --jq length 2>/dev/null || echo 0)" -eq 0 ]; do
    _await_checks_tries=$((_await_checks_tries + 1))
    if [ "$_await_checks_tries" -gt 24 ]; then
      echo "release: no checks reported on $_await_checks_pr_url after 2 minutes" >&2
      exit 1
    fi
    sleep 5
  done
  gh pr checks "$_await_checks_pr_url" --watch --fail-fast
}

_merge_pr() {
  _merge_pr_pr_url=$1
  # --match-head-commit refuses to merge if the branch moved during the wait.
  # No --admin: bypassing the ruleset leaves the commit unsigned.
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "+ gh pr merge $_merge_pr_pr_url --squash --delete-branch --match-head-commit <branch-head>"
    return
  fi
  gh pr merge "$_merge_pr_pr_url" --squash --delete-branch \
    --match-head-commit "$(git -C "$REPO_ROOT" rev-parse "$BRANCH")"
}

_sync_main() {
  _sync_main_pr_url=$1
  _run git -C "$REPO_ROOT" pull --ff-only origin main
  if [ "$DRY_RUN" -eq 1 ]; then
    return
  fi
  # Tags go on HEAD, so HEAD must be the merge commit, not a later push.
  _sync_main_merged=$(gh pr view "$_sync_main_pr_url" --json mergeCommit --jq .mergeCommit.oid)
  if [ "$(git -C "$REPO_ROOT" rev-parse HEAD)" != "$_sync_main_merged" ]; then
    echo "release: main moved past the release commit $_sync_main_merged" >&2
    exit 1
  fi
}

_land_bump() {
  _check_branch_absent
  _run git -C "$REPO_ROOT" switch -c "$BRANCH"
  _bump_version
  _run_release_check
  _run_tests
  _commit_and_push_branch
  _land_bump_pr_url=$(_open_pr)
  _await_checks "$_land_bump_pr_url"
  _merge_pr "$_land_bump_pr_url"
  _sync_main "$_land_bump_pr_url"
}

_tag_and_push() {
  _run git -C "$REPO_ROOT" tag -a "$TAG" -m "$TAG"
  _run git -C "$REPO_ROOT" push origin "$TAG"
}

main() {
  REPO_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
  readonly REPO_ROOT
  readonly PYPROJECTS="$REPO_ROOT/pyproject.toml $REPO_ROOT/marcone/pyproject.toml $REPO_ROOT/inventory_updater/pyproject.toml"

  _parse_args "$@"
  _check_preconditions
  if _is_bumped; then
    _run_release_check
  else
    _land_bump
  fi
  _tag_and_push
}

main "$@"
