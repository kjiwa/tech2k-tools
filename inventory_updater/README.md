# inventory-updater

CLI tool to synchronize inventory Excel files (`InventoryItems.xlsx`) with pricing from Marcone.

## Prerequisites

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/)

## Setup

1. Install workspace dependencies:

```sh
uv sync
```

2. Configure Marcone credentials:

```sh
cp .env.example .env
```

Edit `.env` and set:
- `MARCONE_USERNAME`: Marcone portal username or email.
- `MARCONE_PASSWORD`: Marcone portal password.
- `MARCONE_ACCOUNT_NUMBER`: Optional account number if your login requires one.

Credentials can also be provided directly via `--username`, `--password`, and `--account-number`.

## Usage

Execute through `uv run`:

```sh
uv run inventory-updater [options]
```

By default, the tool reads `InventoryItems.xlsx` in the working directory and outputs changes to `InventoryItems_updated.xlsx`.

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-f, --file` | Path to the inventory Excel file | `Service Fusion Inventory.xlsx` |
| `-o, --output` | Path for the output Excel file | `<file>_updated.xlsx` |
| `--in-place` | Overwrite the input file directly | `false` |
| `--field` | Fields to update: `cost`, `price`, or `both` | `both` |
| `--supplier-filter` | Only update rows where current Supplier Name contains this text | `Marcone` |
| `--no-allow-blank-supplier` | Do not update rows where supplier is blank | `false` (blanks allowed) |
| `--set-supplier` | Set Supplier Name column to this value on updated rows | None |
| `--only-missing` | Only look up rows where cost or price is blank or zero | `false` |
| `--dry-run` | Look up prices and print stats without modifying any file | `false` |
| `--limit` | Limit number of updated parts (useful for testing) | None |
| `--cache-file` | SQLite database path for price cache | `.cache/marcone_prices.sqlite` |
| `--cache-ttl-days` | Cache lifetime in days | `7.0` |
| `--username` | Marcone username/email override | `MARCONE_USERNAME` env var |
| `--password` | Marcone password override | `MARCONE_PASSWORD` env var |
| `--account-number` | Marcone customer account number override | `MARCONE_ACCOUNT_NUMBER` env var |
| `-v, --verbose` | Enable debug logging | `false` |

### Examples

Dry run on the first 5 parts:

```sh
uv run inventory-updater --dry-run --limit 5
```

Update an inventory spreadsheet in place:

```sh
uv run inventory-updater --file InventoryItems.xlsx --in-place
```

Update only missing costs and prices for Marcone items:

```sh
uv run inventory-updater --supplier-filter Marcone --only-missing
```

Assign supplier name to Marcone on all updated items and write to a new file:

```sh
uv run inventory-updater --set-supplier Marcone -o output.xlsx
```

