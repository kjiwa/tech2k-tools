from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from marcone.client import MarconeClient
from marcone.exceptions import AuthenticationError, MarconeError

from inventory_updater.cache import PriceCache
from inventory_updater.updater import InventoryUpdater


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update InventoryItems.xlsx with current Marcone supplier cost and list price."
    )
    parser.add_argument(
        "--file",
        "-f",
        default="InventoryItems.xlsx",
        help="Path to the inventory Excel file (default: InventoryItems.xlsx)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Path for output Excel file (default: <file>_updated.xlsx)",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input Excel file directly instead of writing to a new file",
    )
    parser.add_argument(
        "--field",
        choices=["both", "cost", "price"],
        default="both",
        help="Which fields to update: cost (Supplier Cost), price (Price *), or both (default: both)",
    )
    parser.add_argument(
        "--supplier-filter",
        help="Only update items where current Supplier Name contains this string (e.g. 'Marcone')",
    )
    parser.add_argument(
        "--set-supplier",
        help="Set the Supplier Name column to this value for all updated parts (e.g. 'Marcone')",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only look up and update rows where cost or price is currently empty or zero",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform lookups and report changes without modifying files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of parts updated (useful for testing)",
    )
    parser.add_argument(
        "--cache-file",
        default=".cache/marcone_prices.sqlite",
        help="SQLite cache file path (default: .cache/marcone_prices.sqlite)",
    )
    parser.add_argument(
        "--cache-ttl-days",
        type=float,
        default=7.0,
        help="Cache time-to-live in days (default: 7.0)",
    )
    parser.add_argument(
        "--username",
        help="Marcone username/email (defaults to MARCONE_USERNAME env var)",
    )
    parser.add_argument(
        "--password",
        help="Marcone password (defaults to MARCONE_PASSWORD env var)",
    )
    parser.add_argument(
        "--account-number",
        help="Marcone account/customer number (defaults to MARCONE_ACCOUNT_NUMBER env var)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args(args)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    setup_logging(args.verbose)

    input_path = Path(args.file)
    if not input_path.exists():
        sys.stderr.write(f"Error: Inventory file '{input_path}' not found.\n")
        return 1

    if args.in_place:
        output_path = input_path
    elif args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_name(f"{input_path.stem}_updated{input_path.suffix}")

    username = args.username or os.getenv("MARCONE_USERNAME")
    password = args.password or os.getenv("MARCONE_PASSWORD")
    account_number = args.account_number or os.getenv("MARCONE_ACCOUNT_NUMBER")

    if not username or not password:
        sys.stderr.write(
            "Error: Marcone credentials required. Set MARCONE_USERNAME and MARCONE_PASSWORD "
            "in your environment or .env file, or pass --username and --password.\n"
        )
        return 1

    client = MarconeClient()
    try:
        print(f"Logging in to Marcone as {username}...")
        client.login(username=username, password=password, customer_number=account_number)
    except AuthenticationError as exc:
        sys.stderr.write(f"Authentication failed: {exc}\n")
        return 2
    except MarconeError as exc:
        sys.stderr.write(f"Marcone connection error: {exc}\n")
        return 2

    cache = PriceCache(db_path=args.cache_file)
    updater = InventoryUpdater(
        client=client,
        cache=cache,
        cache_ttl_seconds=args.cache_ttl_days * 86400,
    )

    def progress_callback(current: int, total: int, part_no: str) -> None:
        if args.verbose or current % 25 == 0 or current == 1:
            print(f"[{current}/{total}] Looking up part {part_no}...")

    print(f"Processing '{input_path}'...")
    if args.dry_run:
        print("[DRY RUN] No files will be modified.")

    try:
        stats = updater.update_file(
            input_file=input_path,
            output_file=output_path,
            field=args.field,
            dry_run=args.dry_run,
            limit=args.limit,
            supplier_filter=args.supplier_filter,
            set_supplier=args.set_supplier,
            only_missing=args.only_missing,
            progress_cb=progress_callback,
        )
    finally:
        client.close()

    print("\nSummary:")
    print(f"  Total rows: {stats.total_rows}")
    print(f"  Updated:    {stats.updated}")
    print(f"  Skipped:    {stats.skipped}")
    print(f"  Not found:  {stats.not_found}")
    print(f"  Errors:     {stats.errors}")
    if not args.dry_run and stats.updated > 0:
        print(f"Output saved to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
