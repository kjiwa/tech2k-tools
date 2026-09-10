# tech2k-tools

Tools for inventory and catalog automation.

## Quickstart

1. Install dependencies:
   ```sh
   uv sync
   ```
2. Configure credentials:
   ```sh
   cp .env.example .env
   ```
   Set `MARCONE_USERNAME` and `MARCONE_PASSWORD` in `.env`.
3. Run `inventory-updater`:
   ```sh
   uv run inventory-updater --dry-run --limit 5
   ```

Detailed instructions and CLI options are documented in [inventory_updater/README.md](inventory_updater/README.md).
