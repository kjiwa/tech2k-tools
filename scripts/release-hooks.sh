# shellcheck shell=sh
# Sourced by `gh cut`; see https://github.com/kjiwa/gh-cut.

PYPROJECTS="pyproject.toml marcone/pyproject.toml inventory_updater/pyproject.toml"
# shellcheck disable=SC2034 # read by gh-cut
RELEASE_BY_WORKFLOW=1

release_version() {
  _release_version_first=""
  for _release_version_file in $PYPROJECTS; do
    _release_version_current=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$_release_version_file" | head -n1)
    [ -n "$_release_version_first" ] || _release_version_first=$_release_version_current
    [ "$_release_version_current" = "$_release_version_first" ] || return 1
  done
  printf '%s\n' "$_release_version_first"
}

release_bump() {
  for _release_bump_file in $PYPROJECTS; do
    sed "s/^version = \".*\"\$/version = \"$1\"/" "$_release_bump_file" >"$_release_bump_file.new"
    mv "$_release_bump_file.new" "$_release_bump_file"
  done
  uv lock
}

release_checks() {
  uv run ruff check .
  uv run ruff format --check .
  QT_QPA_PLATFORM=offscreen uv run pytest -q
}
