# tech2k-tools

Tools for appliance parts pricing and inventory synchronization.

## Workspace Layout

| Package | Directory | Description |
| --- | --- | --- |
| `inventory-updater` | `inventory_updater/` | Desktop GUI and CLI to update inventory spreadsheets from Marcone |
| `marcone` | `marcone/` | Python client library for the Marcone parts portal |

## Prerequisites

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/)

## Setup

```sh
uv sync
cp .env.example .env
```

Configure credentials in `.env` in the working directory, or save them from the GUI to the user configuration directory:

```sh
MARCONE_USERNAME=your_username
MARCONE_PASSWORD=your_password
MARCONE_ACCOUNT_NUMBER=optional_account_number
```

## Usage

Launch the desktop GUI:

```sh
uv run inventory-updater-gui
# Or run with fake client and canned pricing (no Marcone credentials required):
uv run inventory-updater-gui --demo
```

Run the CLI:

```sh
uv run inventory-updater --help
```

## Testing and Verification

Run test suite:

```sh
uv run pytest
```

Run code formatting and lint checks:

```sh
uv run ruff check .
uv run ruff format --check .
```

## Documentation

- [inventory-updater](inventory_updater/README.md)
- [marcone client](marcone/README.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Security](SECURITY.md)


