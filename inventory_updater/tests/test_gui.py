import os
from unittest.mock import patch

import openpyxl
import pytest

# Ensure offscreen Qt platform for testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from inventory_updater.gui import (
    AdvancedSettingsDialog,
    CredentialsDialog,
    FileDropArea,
    MainWindow,
    UpdateWorker,
)
from inventory_updater.styles import get_status_colors, get_stylesheet
from inventory_updater.updater import RowUpdateResult, UpdateStats
from PySide6.QtWidgets import QApplication, QDialog, QGroupBox, QLabel, QLayout


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def test_excel_file(tmp_path):
    file_path = tmp_path / "test_inventory.xlsx"
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Items"
    sheet.append(["Item #", "Cost", "Price", "Vendor"])
    sheet.append(["WPW10321304", 10.0, 20.0, "Marcone"])
    sheet.append(["240323002", "", 0, "Marcone"])
    wb.save(file_path)
    return file_path


def test_file_drop_area(qapp, test_excel_file):
    drop_area = FileDropArea()
    drop_area.show()
    selected_paths = []
    drop_area.file_selected.connect(selected_paths.append)

    drop_area.set_file(str(test_excel_file))

    assert not drop_area.selected_widget.isHidden()
    assert drop_area.empty_widget.isHidden()
    assert test_excel_file.name in drop_area.file_name_lbl.text()
    assert "2 items" in drop_area.row_badge.text()
    assert "Columns detected" in drop_area.col_badge.text()
    assert len(selected_paths) == 1
    assert selected_paths[0] == str(test_excel_file)


def test_main_window_init(qapp):
    with patch(
        "inventory_updater.gui.load_credentials",
        return_value={"username": "testuser", "password": "pw"},
    ):
        window = MainWindow()
        assert window.windowTitle() == "Tech 2000 Inventory Price Updater"
        assert window.table.columnCount() == 5
        assert "Marcone: testuser" in window.conn_chip.text()
        assert window.start_btn.isEnabled() is False
        assert window.supplier_combo.isEditable()
        assert window.supplier_combo.currentText() == "Marcone"
        assert window.cb_blank_supplier.isChecked() is True
        assert window.cb_missing_only.isChecked() is False
        assert window.cb_dry_run.isChecked() is False
        assert window.limit_spin.value() == 0
        assert window.workers_spin.value() == 3
        assert window.throttle_spin.value() == 0.20
        assert window.batch_spin.value() == 500
        assert window.lookahead_spin.value() == 0


def test_main_window_file_selection_and_options(qapp, test_excel_file):
    with patch(
        "inventory_updater.gui.load_credentials",
        return_value={"username": "testuser", "password": "pw"},
    ):
        window = MainWindow()
        window.drop_area.set_file(str(test_excel_file))
        assert window.selected_file_path == test_excel_file
        assert window.start_btn.isEnabled() is True
        # Check supplier combo population
        items = [
            window.supplier_combo.itemText(i)
            for i in range(window.supplier_combo.count())
        ]
        assert "(All Suppliers - No Filter)" in items
        assert "Marcone" in items
        assert window.supplier_combo.currentText() == "Marcone"


def test_main_window_supplier_filter_selection(qapp, tmp_path):
    multi_vendor_file = tmp_path / "multi_vendor.xlsx"
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Items"
    sheet.append(["Item #", "Cost", "Price", "Vendor"])
    sheet.append(["PART-1", 10.0, 20.0, "Reliable"])
    sheet.append(["PART-2", "", 0, "Encompass"])
    sheet.append(["PART-3", "", 0, "Marcone"])
    wb.save(multi_vendor_file)

    with (
        patch(
            "inventory_updater.gui.load_credentials",
            return_value={"username": "testuser", "password": "pw"},
        ),
        patch("inventory_updater.gui.UpdateWorker") as mock_worker_cls,
    ):
        window = MainWindow()
        window.drop_area.set_file(str(multi_vendor_file))

        items = [
            window.supplier_combo.itemText(i)
            for i in range(window.supplier_combo.count())
        ]
        assert items == [
            "(All Suppliers - No Filter)",
            "Encompass",
            "Marcone",
            "Reliable",
        ]
        assert window.supplier_combo.currentText() == "Marcone"

        # Test selecting "(All Suppliers - No Filter)"
        window.supplier_combo.setCurrentIndex(0)
        window._on_start()
        assert mock_worker_cls.call_args.kwargs["supplier_filter"] is None

        # Test setting a custom typed filter
        window.supplier_combo.setEditText("CustomVendor")
        window._on_start()
        assert mock_worker_cls.call_args.kwargs["supplier_filter"] == "CustomVendor"


def test_main_window_progress_and_row_results(qapp):
    window = MainWindow()

    window._on_progress(5, 10, "WPW10321304")
    assert window.progress_bar.value() == 50
    assert "Checking row 5 of 10" in window.status_lbl.text()

    result = RowUpdateResult(
        row_idx=2,
        part_no="WPW10321304",
        status="updated",
        old_cost=10.0,
        new_cost=15.5,
        old_price=20.0,
        new_price=29.99,
    )
    window._on_row_result(result)
    assert window.table.rowCount() == 1
    assert window.table.item(0, 0).text() == "2"
    assert window.table.item(0, 1).text() == "WPW10321304"
    assert window.table.item(0, 2).text() == "UPDATED"
    assert "$10.00 → $15.50" in window.table.item(0, 3).text()
    assert "$20.00 → $29.99" in window.table.item(0, 4).text()


def test_main_window_worker_finished(qapp, tmp_path):
    window = MainWindow()
    window.show()
    window.output_file_path = tmp_path / "out.xlsx"
    window.cb_dry_run.setChecked(False)

    stats = UpdateStats(total_rows=10, updated=8, not_found=1, skipped=1, errors=0)
    window._on_worker_finished(stats)

    assert "Finished! 8 prices updated" in window.status_lbl.text()
    assert window.lbl_updated.text() == "Updated: 8"
    assert window.lbl_notfound.text() == "Not Found: 1"
    assert window.lbl_skipped.text() == "Skipped: 1"
    assert window.lbl_errors.text() == "Errors: 0"
    assert not window.success_frame.isHidden()
    assert window.start_btn.isEnabled() is True
    assert window.cancel_btn.isEnabled() is False


def test_update_worker_init_and_cancel(qapp, tmp_path):
    dummy_file = tmp_path / "dummy.xlsx"
    worker = UpdateWorker(
        input_file=dummy_file,
        output_file=dummy_file,
        field="both",
        dry_run=True,
        supplier_filter="Marcone",
        allow_blank_supplier=True,
        only_missing=True,
        limit=5,
        username="user",
        password="pwd",
    )
    assert worker.workers == 3
    assert worker.throttle_seconds == 0.2
    assert worker.cache_chunk_size == 500
    assert worker._is_cancelled is False
    worker.cancel()
    assert worker._is_cancelled is True


def test_main_window_concurrency_options(qapp, test_excel_file):
    with (
        patch(
            "inventory_updater.gui.load_credentials",
            return_value={"username": "testuser", "password": "pw"},
        ),
        patch("inventory_updater.gui.UpdateWorker") as mock_worker_cls,
    ):
        window = MainWindow()
        window.drop_area.set_file(str(test_excel_file))
        window.workers_spin.setValue(6)
        window.throttle_spin.setValue(0.45)
        window.batch_spin.setValue(250)

        window._on_start()

        assert mock_worker_cls.call_args.kwargs["workers"] == 6
        assert (
            pytest.approx(mock_worker_cls.call_args.kwargs["throttle_seconds"]) == 0.45
        )
        assert mock_worker_cls.call_args.kwargs["cache_chunk_size"] == 250


def test_credentials_dialog_save_and_accept(qapp):
    with patch("inventory_updater.gui.save_credentials") as mock_save:
        dlg = CredentialsDialog()
        dlg.user_input.setText("myuser")
        dlg.pass_input.setText("mypass")
        dlg.acc_input.setText("12345")
        dlg.remember_cb.setChecked(True)

        dlg._on_save()

        mock_save.assert_called_once_with("myuser", "mypass", "12345")
        assert dlg.result() == QDialog.DialogCode.Accepted


def test_main_window_open_credentials_updates_chip_and_start_btn(qapp, test_excel_file):
    current_creds = {"username": "", "password": "", "account_number": ""}

    with patch(
        "inventory_updater.gui.load_credentials",
        side_effect=lambda: current_creds,
    ):
        window = MainWindow()
        window.selected_file_path = test_excel_file
        assert "Not configured" in window.conn_chip.text()
        assert window.start_btn.isEnabled() is False

        def mock_exec(self):
            current_creds["username"] = "newuser"
            current_creds["password"] = "newpassword"
            return QDialog.DialogCode.Accepted

        with patch("inventory_updater.gui.CredentialsDialog.exec", mock_exec):
            window._open_credentials()

        assert "Marcone: newuser" in window.conn_chip.text()
        assert window.start_btn.isEnabled() is True


def test_advanced_settings_dialog_defaults_and_reset(qapp):
    dlg = AdvancedSettingsDialog()
    assert dlg.workers_spin.value() == 3
    assert pytest.approx(dlg.throttle_spin.value()) == 0.20
    assert dlg.batch_spin.value() == 500
    assert dlg.lookahead_spin.value() == 0

    dlg.workers_spin.setValue(8)
    dlg.throttle_spin.setValue(0.50)
    dlg.batch_spin.setValue(1000)
    dlg.lookahead_spin.setValue(50)

    dlg._reset_defaults()
    assert dlg.workers_spin.value() == 3
    assert pytest.approx(dlg.throttle_spin.value()) == 0.20
    assert dlg.batch_spin.value() == 500
    assert dlg.lookahead_spin.value() == 0


def test_advanced_settings_dialog_custom_init(qapp):
    dlg = AdvancedSettingsDialog(
        workers=6,
        throttle_seconds=0.35,
        cache_chunk_size=750,
        lookahead=20,
    )
    assert dlg.workers_spin.value() == 6
    assert pytest.approx(dlg.throttle_spin.value()) == 0.35
    assert dlg.batch_spin.value() == 750
    assert dlg.lookahead_spin.value() == 20


def test_main_window_open_advanced_settings(qapp):
    window = MainWindow()
    assert window.adv_btn.text() == "Advanced..."
    with patch.object(window.adv_dialog, "exec") as mock_exec:
        window.adv_btn.click()
        mock_exec.assert_called_once()


def test_main_window_layout_constraints_and_no_performance_row(qapp):
    window = MainWindow()
    window.show()

    min_size = window.minimumSize()
    assert min_size.width() >= 800
    assert min_size.height() >= 640

    options_group = None
    for child in window.centralWidget().findChildren(QGroupBox):
        if child.title() == "Update Options":
            options_group = child
            break
    assert options_group is not None

    labels = [lbl.text() for lbl in options_group.findChildren(QLabel)]
    assert not any("Performance" in text for text in labels)
    assert not any("request throttling" in text for text in labels)

    assert (
        options_group.layout().sizeConstraint() == QLayout.SizeConstraint.SetMinimumSize
    )

    window.resize(800, 640)
    assert options_group.height() >= 200


def test_dark_mode_stylesheets_and_palette():
    light_css = get_stylesheet(dark=False)
    dark_css = get_stylesheet(dark=True)

    assert "#f8fafc" in light_css
    assert "#0f172a" in dark_css

    light_colors = get_status_colors(dark=False)
    dark_colors = get_status_colors(dark=True)

    assert light_colors["updated"] == "#16a34a"
    assert dark_colors["updated"] == "#4ade80"
    assert light_colors["not_found"] == "#d97706"
    assert dark_colors["not_found"] == "#fbbf24"
    assert light_colors["error"] == "#dc2626"
    assert dark_colors["error"] == "#f87171"


def test_main_window_theme_switching(qapp):
    window = MainWindow()
    result = RowUpdateResult(
        row_idx=2,
        part_no="WPW10321304",
        status="updated",
        old_cost=10.0,
        new_cost=15.5,
        old_price=20.0,
        new_price=29.99,
    )
    window._on_row_result(result)
    item = window.table.item(0, 2)
    assert item is not None

    with patch.object(MainWindow, "_is_dark_mode", return_value=False):
        window._apply_theme()
        assert item.foreground().color().name().lower() == "#16a34a"

    with patch.object(MainWindow, "_is_dark_mode", return_value=True):
        window._apply_theme()
        assert item.foreground().color().name().lower() == "#4ade80"


def test_credentials_dialog_fields_and_subaccount(qapp):
    dlg = CredentialsDialog()
    assert dlg.user_input.placeholderText() == "e.g. 123456 or user@example.com"
    assert dlg.pass_input.placeholderText() == "Your Marcone password"
    assert dlg.acc_input.placeholderText() == "Leave blank if not required"
