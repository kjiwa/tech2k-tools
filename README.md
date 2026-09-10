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
   Set `MARCONE_USERNAME` and `MARCONE_PASSWORD` in `.env` (or configure them directly in the GUI).
3. Run the desktop GUI:
   ```sh
   uv run inventory-updater-gui
   ```
   Or run via CLI:
   ```sh
   uv run inventory-updater --dry-run --limit 5
   ```

Detailed instructions, GUI features, and CLI options are documented in [inventory_updater/README.md](inventory_updater/README.md).

