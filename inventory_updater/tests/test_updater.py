from unittest.mock import MagicMock, patch

import openpyxl
import pytest
from inventory_updater.cache import PriceCache
from inventory_updater.updater import (
    InventoryUpdater,
    MissingColumnsError,
    get_file_info,
)
from marcone.client import MarconeClient
from marcone.exceptions import PartNotFoundError
from marcone.models import PartPricing


@pytest.fixture
def sample_excel(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Items"

    headers = [
        "Part No",
        "Item Name *",
        "Item Description",
        "Primary Category",
        "Secondary Category",
        "Barcode",
        "Vendor Part No",
        "Supplier Cost",
        "Cost Type",
        "Price *",
        "Price Type",
        "Taxable",
        "Manufacturer",
        "Supplier Name",
        "Status",
    ]
    ws.append(headers)
    ws.append(
        [
            "WPW10321304",
            "FILTER",
            "",
            "",
            "",
            "",
            "",
            10.0,
            "Flat",
            18.0,
            "Flat",
            "Yes",
            "WPL",
            "Marcone",
            "Active",
        ]
    )
    ws.append(
        [
            "240323002",
            "BIN",
            "",
            "",
            "",
            "",
            "",
            None,
            "Flat",
            None,
            "Flat",
            "Yes",
            "FRG",
            "",
            "Active",
        ]
    )
    ws.append(
        [
            "NOTFOUND99",
            "UNKNOWN",
            "",
            "",
            "",
            "",
            "",
            None,
            "Flat",
            None,
            "Flat",
            "Yes",
            "",
            "",
            "Active",
        ]
    )

    file_path = tmp_path / "InventoryItems.xlsx"
    wb.save(file_path)
    return file_path


def test_updater_both_fields(tmp_path, sample_excel):
    mock_client = MagicMock(spec=MarconeClient)

    def fake_lookup(part_no):
        if part_no == "WPW10321304":
            return PartPricing(part_number=part_no, customer_cost=15.25, list_price=27.50)
        elif part_no == "240323002":
            return PartPricing(part_number=part_no, customer_cost=18.45, list_price=30.00)
        raise PartNotFoundError(part_no)

    mock_client.lookup_part.side_effect = fake_lookup

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    output_path = tmp_path / "InventoryItems_updated.xlsx"
    stats = updater.update_file(input_file=sample_excel, output_file=output_path, field="both")

    assert stats.total_rows == 3
    assert stats.updated == 2
    assert stats.not_found == 1

    updated_wb = openpyxl.load_workbook(output_path)
    sheet = updated_wb.active

    # Row 2 (WPW10321304): cost col 8, price col 10
    assert sheet.cell(row=2, column=8).value == 15.25
    assert sheet.cell(row=2, column=10).value == 27.50

    # Row 3 (240323002)
    assert sheet.cell(row=3, column=8).value == 18.45
    assert sheet.cell(row=3, column=10).value == 30.00


def test_updater_cost_only(tmp_path, sample_excel):
    mock_client = MagicMock(spec=MarconeClient)
    mock_client.lookup_part.return_value = PartPricing(
        part_number="WPW10321304", customer_cost=15.25, list_price=27.50
    )

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    output_path = tmp_path / "out.xlsx"
    updater.update_file(input_file=sample_excel, output_file=output_path, field="cost", limit=1)

    updated_wb = openpyxl.load_workbook(output_path)
    sheet = updated_wb.active
    assert sheet.cell(row=2, column=8).value == 15.25
    assert sheet.cell(row=2, column=10).value == 18.0  # unchanged list price


def test_updater_supplier_filter_strict(tmp_path, sample_excel):
    mock_client = MagicMock(spec=MarconeClient)
    mock_client.lookup_part.return_value = PartPricing(
        part_number="WPW10321304", customer_cost=15.25, list_price=27.50
    )

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    output_path = tmp_path / "out.xlsx"
    stats = updater.update_file(
        input_file=sample_excel,
        output_file=output_path,
        supplier_filter="Marcone",
        allow_blank_supplier=False,
    )

    assert stats.updated == 1
    assert stats.skipped == 2


def test_updater_supplier_filter_allows_blank_and_skips_others(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Worksheet"
    ws.append(["Part Number", "Unit Price", "Avg. Unit Cost", "Primary Vendor"])
    ws.append(["WPW10321304", 18.0, 10.0, "Marcone"])
    ws.append(["240323002", 0.0, 0.0, ""])
    ws.append(["VENMAR001", 10.0, 5.0, "Venmar"])
    ws.append(["AMRE002", 20.0, 12.0, "Amre Supply"])

    excel_path = tmp_path / "vendor_test.xlsx"
    wb.save(excel_path)

    mock_client = MagicMock(spec=MarconeClient)

    def fake_lookup(part_no):
        if part_no == "WPW10321304":
            return PartPricing(part_number=part_no, customer_cost=15.25, list_price=27.50)
        elif part_no == "240323002":
            return PartPricing(part_number=part_no, customer_cost=18.45, list_price=30.00)
        raise PartNotFoundError(part_no)

    mock_client.lookup_part.side_effect = fake_lookup

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    output_path = tmp_path / "vendor_test_out.xlsx"
    stats = updater.update_file(
        input_file=excel_path,
        output_file=output_path,
        supplier_filter="Marcone",
        allow_blank_supplier=True,
    )

    # 4 rows: 2 updated (Marcone and blank), 2 skipped (Venmar and Amre Supply)
    assert stats.total_rows == 4
    assert stats.updated == 2
    assert stats.skipped == 2
    assert stats.not_found == 0


def test_updater_missing_part_logged_and_counted(tmp_path, caplog):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Part Number", "Unit Price", "Avg. Unit Cost", "Primary Vendor"])
    ws.append(["UNKNOWN_PART_XYZ", 0.0, 0.0, "Marcone"])

    excel_path = tmp_path / "missing_test.xlsx"
    wb.save(excel_path)

    mock_client = MagicMock(spec=MarconeClient)
    mock_client.lookup_part.side_effect = PartNotFoundError("UNKNOWN_PART_XYZ")

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    with caplog.at_level("WARNING"):
        stats = updater.update_file(input_file=excel_path)

    assert stats.not_found == 1
    assert stats.updated == 0
    assert "Part UNKNOWN_PART_XYZ not found in Marcone catalog" in caplog.text


def test_updater_unexpected_error_logged_and_counted(tmp_path, caplog):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Part Number", "Unit Price", "Avg. Unit Cost", "Primary Vendor"])
    ws.append(["ERROR_PART_XYZ", 0.0, 0.0, "Marcone"])

    excel_path = tmp_path / "unexpected_error_test.xlsx"
    wb.save(excel_path)

    mock_client = MagicMock(spec=MarconeClient)
    mock_client.lookup_part.side_effect = RuntimeError("Database disk corruption")

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    with caplog.at_level("ERROR"):
        stats = updater.update_file(input_file=excel_path)

    assert stats.errors == 1
    assert stats.updated == 0
    assert (
        "Unexpected error looking up part ERROR_PART_XYZ: Database disk corruption" in caplog.text
    )


def test_updater_set_supplier(tmp_path, sample_excel):
    mock_client = MagicMock(spec=MarconeClient)
    mock_client.lookup_part.return_value = PartPricing(
        part_number="240323002", customer_cost=18.45, list_price=30.00
    )

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    output_path = tmp_path / "out.xlsx"
    updater.update_file(
        input_file=sample_excel,
        output_file=output_path,
        only_missing=True,
        set_supplier="Marcone Supply",
    )

    updated_wb = openpyxl.load_workbook(output_path)
    sheet = updated_wb.active
    # Row 3 supplier name is at column 14
    assert sheet.cell(row=3, column=14).value == "Marcone Supply"


def test_updater_dry_run(tmp_path, sample_excel):
    mock_client = MagicMock(spec=MarconeClient)
    mock_client.lookup_part.return_value = PartPricing(
        part_number="WPW10321304", customer_cost=15.25, list_price=27.50
    )

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    output_path = tmp_path / "should_not_exist.xlsx"
    stats = updater.update_file(
        input_file=sample_excel,
        output_file=output_path,
        dry_run=True,
        limit=1,
    )

    assert stats.updated == 1
    assert not output_path.exists()


@pytest.fixture
def service_fusion_excel(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Worksheet"

    headers = [
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
    ws.append(headers)
    ws.append(
        [
            "Parts",
            "FILTER",
            "WPW10321304",
            "",
            "",
            "",
            "1",
            18.0,
            10.0,
            "",
            "Yes",
            "Yes",
            "",
            "",
            "No",
            0,
            0,
            "No",
            0,
            0,
            0,
            "Marcone",
            10.0,
            "",
            0,
            "",
            0,
            "",
            "",
            "FILTER",
        ]
    )
    ws.append(
        [
            "Parts",
            "BIN",
            "240323002",
            "",
            "",
            "",
            "0",
            0.0,
            0.0,
            "",
            "Yes",
            "Yes",
            "",
            "",
            "No",
            0,
            0,
            "No",
            0,
            0,
            0,
            "",
            0.0,
            "",
            0,
            "",
            0,
            "",
            "",
            "BIN",
        ]
    )

    file_path = tmp_path / "Service_Fusion_Inventory.xlsx"
    wb.save(file_path)
    return file_path


def test_updater_service_fusion_format(tmp_path, service_fusion_excel):
    mock_client = MagicMock(spec=MarconeClient)

    def fake_lookup(part_no):
        if part_no == "WPW10321304":
            return PartPricing(part_number=part_no, customer_cost=15.25, list_price=27.50)
        elif part_no == "240323002":
            return PartPricing(part_number=part_no, customer_cost=18.45, list_price=30.00)
        raise PartNotFoundError(part_no)

    mock_client.lookup_part.side_effect = fake_lookup

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    output_path = tmp_path / "Service_Fusion_Inventory_updated.xlsx"
    stats = updater.update_file(
        input_file=service_fusion_excel,
        output_file=output_path,
        field="both",
        set_supplier="Marcone",
    )

    assert stats.total_rows == 2
    assert stats.updated == 2

    updated_wb = openpyxl.load_workbook(output_path)
    sheet = updated_wb.active

    # Row 2 (WPW10321304): unit_price col 8, avg_cost col 9, purchase_price col 23, vendor col 22
    assert sheet.cell(row=2, column=8).value == 27.50
    assert sheet.cell(row=2, column=9).value == 15.25
    assert sheet.cell(row=2, column=23).value == 15.25
    assert sheet.cell(row=2, column=22).value == "Marcone"

    # Row 3 (240323002)
    assert sheet.cell(row=3, column=8).value == 30.00
    assert sheet.cell(row=3, column=9).value == 18.45
    assert sheet.cell(row=3, column=23).value == 18.45
    assert sheet.cell(row=3, column=22).value == "Marcone"


def test_get_file_info(sample_excel):
    from inventory_updater.updater import get_file_info

    info = get_file_info(sample_excel)
    assert info["file_name"] == "InventoryItems.xlsx"
    assert info["sheet_name"] == "Items"
    assert info["row_count"] == 3
    assert info["has_part_col"] is True
    assert info["has_cost_col"] is True
    assert info["has_price_col"] is True
    assert info["has_supplier_col"] is True
    assert info["suppliers"] == ["Marcone"]


def test_get_file_info_no_recognized_columns(tmp_path):
    from inventory_updater.updater import get_file_info

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Foo", "Bar", "Baz"])
    ws.append(["x", "y", "z"])
    path = tmp_path / "unrecognized.xlsx"
    wb.save(path)

    info = get_file_info(path)
    assert info["has_part_col"] is False
    assert info["has_cost_col"] is False
    assert info["has_price_col"] is False
    assert info["has_supplier_col"] is False


def test_updater_row_callback_and_cancellation(tmp_path, sample_excel):
    mock_client = MagicMock(spec=MarconeClient)

    def fake_lookup(part_no):
        if part_no == "WPW10321304":
            return PartPricing(part_number=part_no, customer_cost=15.25, list_price=27.50)
        return PartPricing(part_number=part_no, customer_cost=18.45, list_price=30.00)

    mock_client.lookup_part.side_effect = fake_lookup

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache)

    row_results = []

    def cancel_after_first():
        return len(row_results) >= 1

    stats = updater.update_file(
        input_file=sample_excel,
        row_cb=row_results.append,
        cancel_check=cancel_after_first,
    )

    assert stats.cancelled is True
    assert len(row_results) == 1
    assert row_results[0].part_no == "WPW10321304"
    assert row_results[0].status == "updated"
    assert row_results[0].new_cost == 15.25
    assert row_results[0].new_price == 27.50


def test_updater_multi_worker_and_deduplication(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Part Number", "Supplier Cost", "Unit Price", "Supplier"])
    # 6 rows with 2 distinct parts
    for _ in range(3):
        ws.append(["PART_A", None, None, "Marcone"])
        ws.append(["PART_B", None, None, "Marcone"])
    file_path = tmp_path / "repeated_parts.xlsx"
    wb.save(file_path)

    mock_client = MagicMock(spec=MarconeClient)
    mock_client.lookup_part.side_effect = lambda p: PartPricing(
        part_number=p,
        customer_cost=10.0 if p == "PART_A" else 20.0,
        list_price=15.0 if p == "PART_A" else 25.0,
    )

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    updater = InventoryUpdater(client=mock_client, cache=cache, workers=4)

    out_path = tmp_path / "repeated_parts_out.xlsx"
    stats = updater.update_file(input_file=file_path, output_file=out_path)

    assert stats.total_rows == 6
    assert stats.updated == 6
    # Each unique part queried only once
    assert mock_client.lookup_part.call_count == 2

    # Verify cached
    assert cache.get("PART_A").customer_cost == 10.0
    assert cache.get("PART_B").customer_cost == 20.0


def test_updater_cache_batching_avoids_lookups(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Part Number", "Supplier Cost", "Unit Price", "Supplier"])
    ws.append(["CACHED_1", None, None, "Marcone"])
    ws.append(["CACHED_2", None, None, "Marcone"])
    file_path = tmp_path / "cached_test.xlsx"
    wb.save(file_path)

    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    cache.set(PartPricing(part_number="CACHED_1", customer_cost=11.0, list_price=22.0))
    cache.set(PartPricing(part_number="CACHED_2", customer_cost=33.0, list_price=44.0))

    mock_client = MagicMock(spec=MarconeClient)
    updater = InventoryUpdater(client=mock_client, cache=cache, workers=3)

    out_path = tmp_path / "cached_out.xlsx"
    stats = updater.update_file(input_file=file_path, output_file=out_path)

    assert stats.total_rows == 2
    assert stats.updated == 2
    assert mock_client.lookup_part.call_count == 0


def _write_workbook(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)
    return path


def _updater(tmp_path, lookup=None):
    mock_client = MagicMock(spec=MarconeClient)
    mock_client.lookup_part.side_effect = lookup or (
        lambda p: PartPricing(part_number=p, customer_cost=1.0, list_price=2.0)
    )
    cache = PriceCache(db_path=str(tmp_path / "cache.sqlite"))
    return mock_client, InventoryUpdater(client=mock_client, cache=cache)


@pytest.mark.parametrize(
    "rows",
    [
        [["WPW10321304", 1, 2, 3], ["240323002", 4, 5, 6]],
        [["Foo", "Bar", "Baz"], ["WPW10321304", 1.0, 2.0]],
    ],
    ids=["headerless", "unrecognized-headers"],
)
def test_update_file_refuses_unrecognized_headers(tmp_path, rows):
    path = _write_workbook(tmp_path / "in.xlsx", rows)
    before = path.read_bytes()
    mock_client, updater = _updater(tmp_path)

    with pytest.raises(MissingColumnsError) as exc_info:
        updater.update_file(input_file=path)

    assert "Part Number" in str(exc_info.value)
    assert "Cost" in str(exc_info.value)
    assert "Price" in str(exc_info.value)
    assert path.read_bytes() == before
    mock_client.lookup_part.assert_not_called()


@pytest.mark.parametrize(
    ("headers", "field", "missing", "present"),
    [
        (["Part Number", "Unit Price"], "both", ["Cost"], ["Price", "Part Number"]),
        (["Part Number", "Unit Price"], "cost", ["Cost"], ["Price"]),
        (["Part Number", "Cost"], "both", ["Price"], ["Cost"]),
        (["Part Number", "Cost"], "price", ["Price"], ["Cost"]),
        (["Cost", "Unit Price"], "price", ["Part Number"], ["Price", "Cost"]),
    ],
)
def test_update_file_missing_columns_named_per_field(tmp_path, headers, field, missing, present):
    path = _write_workbook(tmp_path / "in.xlsx", [headers, ["WPW10321304", 1.0]])
    _, updater = _updater(tmp_path)

    with pytest.raises(MissingColumnsError) as exc_info:
        updater.update_file(input_file=path, field=field)

    message = str(exc_info.value)
    assert all(name in message for name in missing)
    assert not any(name in message for name in present)


def test_update_file_price_only_does_not_require_cost(tmp_path):
    path = _write_workbook(
        tmp_path / "in.xlsx", [["Part Number", "Unit Price"], ["WPW10321304", 1.0]]
    )
    _, updater = _updater(tmp_path)

    stats = updater.update_file(input_file=path, field="price", supplier_filter=None)

    assert stats.updated == 1


def test_get_file_info_reports_missing_columns(tmp_path):
    path = _write_workbook(
        tmp_path / "in.xlsx", [["Part Number", "Unit Price"], ["WPW10321304", 1.0]]
    )
    assert get_file_info(path)["missing_columns"] == ["Cost"]


def test_cancelled_in_place_run_writes_nothing(tmp_path, sample_excel):
    before = sample_excel.read_bytes()
    _, updater = _updater(tmp_path)
    row_results = []

    stats = updater.update_file(
        input_file=sample_excel,
        row_cb=row_results.append,
        cancel_check=lambda: len(row_results) >= 1,
    )

    assert stats.cancelled is True
    assert stats.updated == 1
    assert sample_excel.read_bytes() == before


def test_cancelled_run_does_not_write_output_file(tmp_path, sample_excel):
    out = tmp_path / "out.xlsx"
    _, updater = _updater(tmp_path)
    row_results = []

    updater.update_file(
        input_file=sample_excel,
        output_file=out,
        row_cb=row_results.append,
        cancel_check=lambda: len(row_results) >= 1,
    )

    assert not out.exists()


def test_progress_counts_skipped_rows_and_reaches_total(tmp_path):
    path = _write_workbook(
        tmp_path / "in.xlsx",
        [
            ["Part Number", "Unit Price", "Avg. Unit Cost", "Primary Vendor"],
            ["A1", 1.0, 1.0, "Other"],
            ["", 1.0, 1.0, "Marcone"],
            ["B2", 1.0, 1.0, "Other"],
            ["C3", 0.0, 0.0, "Marcone"],
        ],
    )
    _, updater = _updater(tmp_path)
    progress = []

    stats = updater.update_file(
        input_file=path,
        allow_blank_supplier=False,
        progress_cb=lambda cur, tot, part: progress.append((cur, tot)),
    )

    assert stats.total_rows == 4
    assert progress == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_executor_shut_down_with_wait_and_cancel_futures(tmp_path, sample_excel):
    _, updater = _updater(tmp_path)
    with patch("inventory_updater.updater.concurrent.futures.ThreadPoolExecutor") as pool_cls:
        pool = pool_cls.return_value
        pool.submit.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            updater.update_file(input_file=sample_excel)

    pool.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
