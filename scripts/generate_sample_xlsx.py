#!/usr/bin/env python3
"""Generate a sample inventory spreadsheet for manual smoke-testing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import openpyxl

HEADERS: list[str] = [
    "Product Category",
    "Product Name",
    "Part Number",
    "Model",
    "SKU",
    "Type",
    "Quantity On Hand",
    "Unit Price",
    "Avg. Unit Cost",
    "Member Price",
    "Active?",
    "Inventory Item?",
    "QB Class",
    "Media URL",
    "Pays Commission",
    "Fixed Commission",
    "Percentage Comission",
    "Pays Bonus",
    "Fixed Bonus",
    "Percentage Bonus",
    "Pays Hours",
    "Primary Vendor",
    "Purchase Price",
    "Secondary Vendor",
    "Purchase Price",
    "Tertiary Vendor",
    "Purchase Price",
    "Related Products",
    "Purchase Description",
    "Description",
]

SAMPLE_ROWS: list[tuple[object, ...]] = [
    # 1. WPW10321304: Whirlpool filter, Marcone vendor, outdated price/cost
    (
        "Appliances", "WATER FILTER", "WPW10321304", "", "WPW10321304", "Inventory",
        5, 18.00, 10.00, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", 10.00, "", 0, "", 0, "", "Whirlpool Water Filter", "EveryDrop Filter 1",
    ),
    # 2. 240323002: Frigidaire door bin, Marcone vendor, empty price/cost
    (
        "Appliances", "DOOR BIN", "240323002", "", "240323002", "Inventory",
        2, None, None, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", None, "", 0, "", 0, "", "Frigidaire Door Bin", "Refrigerator door shelf bin",
    ),
    # 3. WB44T10010: GE bake element, Marcone vendor, zero prices
    (
        "Appliances", "BAKE ELEMENT", "WB44T10010", "", "WB44T10010", "Inventory",
        3, 0.0, 0.0, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", 0.0, "", 0, "", 0, "", "GE Oven Bake Element", "Heating element for GE range",
    ),
    # 4. DA62-00914B: Samsung water valve, Marcone vendor, outdated prices
    (
        "Appliances", "WATER VALVE", "DA62-00914B", "", "DA62-00914B", "Inventory",
        1, 40.00, 25.00, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", 25.00, "", 0, "", 0, "", "Samsung Water Inlet Valve", "Dual water inlet valve",
    ),
    # 5. 4681EA2001T: LG drain pump motor, Marcone vendor, outdated prices
    (
        "Appliances", "DRAIN PUMP MOTOR", "4681EA2001T", "", "4681EA2001T", "Inventory",
        4, 35.00, 20.00, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", 20.00, "", 0, "", 0, "", "LG Washer Drain Pump", "Washing machine pump motor",
    ),
    # 6. 5304506516: Frigidaire door gasket, blank vendor (tests blank supplier matching)
    (
        "Appliances", "DOOR GASKET", "5304506516", "", "5304506516", "Inventory",
        2, None, None, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "", None, "", 0, "", 0, "", "Frigidaire Gasket", "Magnetic refrigerator door gasket",
    ),
    # 7. W10837240: Whirlpool heating element, non-Marcone vendor (tests supplier filtering)
    (
        "Appliances", "HEATING ELEMENT", "W10837240", "", "W10837240", "Inventory",
        6, 25.00, 15.00, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Other Supplier", 15.00, "", 0, "", 0, "", "Whirlpool Dryer Element", "Dryer heating element",
    ),
    # 8. NOTFOUND999: Unknown part number (tests not-found handling in GUI)
    (
        "Appliances", "OBSOLETE PART", "NOTFOUND999", "", "NOTFOUND999", "Inventory",
        1, 12.00, 8.00, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", 8.00, "", 0, "", 0, "", "Unknown Obsolete Part", "Discontinued part",
    ),
    # 9. DC97-16782A: Samsung drum roller, Marcone vendor, empty prices
    (
        "Appliances", "DRUM ROLLER", "DC97-16782A", "", "DC97-16782A", "Inventory",
        8, None, None, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", None, "", 0, "", 0, "", "Samsung Dryer Roller", "Drum support roller assembly",
    ),
    # 10. 240356402: Frigidaire crisper pan, Marcone vendor, outdated prices
    (
        "Appliances", "CRISPER PAN", "240356402", "", "240356402", "Inventory",
        1, 45.00, 30.00, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", 30.00, "", 0, "", 0, "", "Frigidaire Crisper Pan", "Lower refrigerator crisper drawer",
    ),
    # 11. 3387747: Whirlpool thermostat, Marcone vendor, outdated prices
    (
        "Appliances", "DRYER THERMOSTAT", "3387747", "", "3387747", "Inventory",
        3, 10.00, 5.00, "", "Yes", "Yes", "", "", "No", 0, 0, "No", 0, 0, 0,
        "Marcone", 5.00, "", 0, "", 0, "", "Whirlpool Thermostat", "Dryer high-limit thermostat",
    ),
]


def generate_sample_inventory(output_path: str | Path | None = None) -> Path:
    """Generate sample inventory workbook at the specified path."""
    target = (
        Path(output_path)
        if output_path
        else Path(__file__).resolve().parent.parent / "samples" / "sample_inventory.xlsx"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Worksheet"
    ws.append(HEADERS)
    for row in SAMPLE_ROWS:
        ws.append(list(row))

    wb.save(target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate sample inventory spreadsheet for manual smoke-testing."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Target XLSX path (default: samples/sample_inventory.xlsx)",
    )
    args = parser.parse_args()
    path = generate_sample_inventory(args.output)
    print(f"Generated sample spreadsheet: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
