# Changelog

## Unreleased

`inventory-updater-gui --demo` runs the GUI against a fake Marcone client with
canned pricing and a bundled sample spreadsheet, so no credentials or network
access are needed.

Column detection no longer falls back to column positions. A spreadsheet whose
required headers are not recognized is refused with an error naming the missing
columns, and nothing is written. A cancelled in-place run writes nothing to the
workbook.

Credentials are always saved to the user configuration directory, never into
the current working directory. The CLI reads the same credentials and the same
price cache as the GUI. A `.env` in the current working directory is still
read.

The GUI cancels a running update and waits for it to stop before closing. The
price cache closes its database connections, so the file can be deleted
afterwards, including on Windows. A search result listing whose first matching
item has no price no longer ends the search before later items are checked. The
macOS bundle version follows the package version. `inventory-updater` now ships
a `py.typed` marker.

CI checks formatting with `ruff format --check`, runs on concurrency-limited
jobs with timeouts, and pins its reusable workflow. The version lives in the
three `pyproject.toml` files and is read from them by the PyInstaller spec and
the Windows installer. `scripts/release.sh` cuts a release from a clean `main`,
and `scripts/check-release.sh` checks the tag and `CHANGELOG.md` against the
package versions. The GitHub release body is the matching changelog section.

## 1.0.1

Fixes Marcone client parsing, rate limiting, and typing. Dependency and GitHub
Actions updates.

## 1.0.0

First release. A desktop GUI and a CLI update cost and price columns in an
inventory spreadsheet from Marcone lookups, with a local SQLite price cache.
Concurrency, throttling, and cache batch size are configurable in both. The
GUI has collapsible update options, an advanced settings dialog, and a
credentials dialog.
