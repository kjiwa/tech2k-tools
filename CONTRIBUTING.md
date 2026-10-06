# Contributing

## Setup and checks

```sh
uv sync
uv run ruff check . && uv run ruff format --check . && QT_QPA_PLATFORM=offscreen uv run pytest -q
```

CI runs the same checks on every supported Python version, then builds and
smoke-tests the packaged app.

A defect found in review is fixed with a test for its class, not only its
instance.

## Releasing

```sh
sh scripts/release.sh [--dry-run] <version>
```

`<version>` is bare (`1.1.0`, not `v1.1.0`). Run it on a clean, synced `main`
after adding a `## <version>` section to `CHANGELOG.md`. The script runs the
checks, opens a `release-<version>` PR with the version bump in the three
`pyproject.toml` files, waits for its checks, squash-merges it, and pushes the
tag. The tag triggers `release.yml`, which re-runs `scripts/check-release.sh`,
builds the installers, and publishes the GitHub release with the changelog
section as its body. `--dry-run` prints each mutating command instead of
running it.
