#!/bin/sh
# Check that a release tag matches the version in every pyproject.toml and
# that CHANGELOG.md has a matching heading.
#
# Usage: sh scripts/check-release.sh <tag>
#        sh scripts/check-release.sh --changelog <tag>
#        sh scripts/check-release.sh --notes <version>
#
# --changelog checks only the CHANGELOG heading, for use before the version
# bump has landed. --notes prints the body of the "## <version>" section.
set -eu

_check_tag_shape() {
  _check_tag_shape_tag=$1
  if ! echo "$_check_tag_shape_tag" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "check-release: tag '$_check_tag_shape_tag' does not match vX.Y.Z" >&2
    return 1
  fi
}

_check_tag_matches_pyproject() {
  _check_tag_matches_pyproject_tag=$1
  _check_tag_matches_pyproject_file=$2
  _check_tag_matches_pyproject_version=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$_check_tag_matches_pyproject_file" | head -n1)
  if [ -z "$_check_tag_matches_pyproject_version" ]; then
    echo "check-release: could not read version from $_check_tag_matches_pyproject_file" >&2
    return 1
  fi
  if [ "$_check_tag_matches_pyproject_tag" != "v$_check_tag_matches_pyproject_version" ]; then
    echo "check-release: tag '$_check_tag_matches_pyproject_tag' does not match $_check_tag_matches_pyproject_file version '$_check_tag_matches_pyproject_version'" >&2
    return 1
  fi
}

_check_tag_matches_versions() {
  _check_tag_matches_versions_status=0
  for _check_tag_matches_versions_file in $PYPROJECTS; do
    _check_tag_matches_pyproject "$1" "$_check_tag_matches_versions_file" || _check_tag_matches_versions_status=1
  done
  return "$_check_tag_matches_versions_status"
}

_check_changelog_heading() {
  _check_changelog_heading_version=${1#v}
  if ! grep -Fxq "## $_check_changelog_heading_version" "$CHANGELOG"; then
    echo "check-release: CHANGELOG.md has no '## $_check_changelog_heading_version' heading" >&2
    return 1
  fi
}

_print_notes() {
  _check_changelog_heading "$1"
  awk -v ver="## $1" '
    $0 == ver { found = 1; next }
    found && /^## / { exit }
    found { print }
  ' "$CHANGELOG"
}

_usage() {
  echo "usage: sh scripts/check-release.sh <tag>" >&2
  echo "       sh scripts/check-release.sh --changelog <tag>" >&2
  echo "       sh scripts/check-release.sh --notes <version>" >&2
  exit 2
}

main() {
  REPO_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
  readonly REPO_ROOT
  readonly PYPROJECTS="$REPO_ROOT/pyproject.toml $REPO_ROOT/marcone/pyproject.toml $REPO_ROOT/inventory_updater/pyproject.toml"
  readonly CHANGELOG="$REPO_ROOT/CHANGELOG.md"

  if [ $# -eq 2 ] && [ "$1" = "--changelog" ]; then
    _check_changelog_heading "$2"
    exit $?
  fi
  if [ $# -eq 2 ] && [ "$1" = "--notes" ]; then
    _print_notes "$2"
    exit $?
  fi
  if [ $# -ne 1 ]; then
    _usage
  fi

  _main_status=0
  _check_tag_shape "$1" || _main_status=1
  if [ "$_main_status" -eq 0 ]; then
    _check_tag_matches_versions "$1" || _main_status=1
  fi
  _check_changelog_heading "$1" || _main_status=1

  exit "$_main_status"
}

main "$@"
