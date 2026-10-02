import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openpyxl
from inventory_updater.updater import get_file_info

from scripts.generate_sample_xlsx import HEADERS, SAMPLE_ROWS, generate_sample_inventory


def test_generate_sample_inventory(tmp_path):
    out_file = tmp_path / "test_sample.xlsx"
    path = generate_sample_inventory(out_file)
    assert path.exists()

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    assert ws.title == "Worksheet"
    assert ws.max_row == len(SAMPLE_ROWS) + 1
    assert ws.max_column == len(HEADERS)

    info = get_file_info(path)
    assert info["row_count"] == len(SAMPLE_ROWS)
    assert info["has_part_col"] is True
    assert info["has_cost_col"] is True
    assert info["has_price_col"] is True
    assert info["has_supplier_col"] is True
    assert "Marcone" in info["suppliers"]
    assert "Other Supplier" in info["suppliers"]


def test_committed_sample_inventory_exists():
    sample_file = ROOT / "samples" / "sample_inventory.xlsx"
    assert sample_file.exists(), f"Expected committed sample at {sample_file}"

    info = get_file_info(sample_file)
    assert info["row_count"] == len(SAMPLE_ROWS)
    assert info["has_part_col"] is True
    assert info["has_cost_col"] is True
    assert info["has_price_col"] is True
