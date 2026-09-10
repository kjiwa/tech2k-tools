# inventory-updater

Synchronize inventory Excel files (`Service Fusion Inventory.xlsx`, `InventoryItems.xlsx`) with pricing from Marcone via desktop GUI or CLI.

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

Alternatively, configure credentials directly in the GUI using the "Configure Marcone Credentials" dialog. Credentials can also be provided on the CLI via `--username`, `--password`, and `--account-number`.

## Desktop GUI

Launch the graphical interface:

```sh
uv run inventory-updater-gui
```

### GUI Features

- **Drag and Drop**: Drag an Excel spreadsheet directly into the drop zone or browse using the file dialog.
- **Pre-flight Column Validation**: Automatically detects and validates Item Number, Cost, Price, and Supplier headers, displaying row counts before processing.
- **Update Options**:
  - Choose pricing fields to update: Both Cost and List Price, Customer Cost Only, or List Price Only.
  - Set supplier filters and toggle blank supplier handling.
  - Run dry runs to preview changes without modifying files.
  - Set row limits for testing.
- **Live Streaming Table**: Displays row number, part number, lookup status, returned cost, and list price in real time.
- **Cooperative Cancellation**: Stop an active update at any time without leaving corrupted or half-written workbooks.
- **One-Click Post Actions**: Once finished, open the resulting spreadsheet directly in Excel or reveal it in Finder/File Explorer.
- **Credentials & Connection Testing**: Verify Marcone login credentials against the portal with immediate connection status feedback.

## CLI Usage

Execute through `uv run`:

```sh
uv run inventory-updater [options]
```

By default, the tool reads `Service Fusion Inventory.xlsx` in the working directory and outputs changes to `<file>_updated.xlsx`.

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

### CLI Examples

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


