from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from marcone.client import MarconeClient
from marcone.exceptions import AuthenticationError, MarconeError
from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inventory_updater.cache import PriceCache
from inventory_updater.credentials import (
    check_connection,
    load_credentials,
    save_credentials,
)
from inventory_updater.styles import MAIN_STYLESHEET
from inventory_updater.updater import (
    InventoryUpdater,
    RowUpdateResult,
    UpdateStats,
    get_file_info,
)


class UpdateWorker(QThread):
    """Background thread executing the inventory update."""

    progress_signal = Signal(int, int, str)
    row_result_signal = Signal(object)
    status_signal = Signal(str)
    finished_signal = Signal(object)
    error_signal = Signal(str)

    def __init__(
        self,
        input_file: Path,
        output_file: Path,
        field: str,
        dry_run: bool,
        supplier_filter: str | None,
        allow_blank_supplier: bool,
        only_missing: bool,
        limit: int | None,
        username: str,
        password: str,
        account_number: str = "",
        cache_file: str = ".cache/marcone_prices.sqlite",
        cache_ttl_days: float = 7.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.input_file = input_file
        self.output_file = output_file
        self.field = field
        self.dry_run = dry_run
        self.supplier_filter = supplier_filter
        self.allow_blank_supplier = allow_blank_supplier
        self.only_missing = only_missing
        self.limit = limit
        self.username = username
        self.password = password
        self.account_number = account_number
        self.cache_file = cache_file
        self.cache_ttl_days = cache_ttl_days
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        client = MarconeClient()
        try:
            self.status_signal.emit(f"Connecting to Marcone as {self.username}...")
            client.login(
                username=self.username,
                password=self.password,
                customer_number=self.account_number or None,
            )

            self.status_signal.emit("Initializing price cache...")
            cache = PriceCache(db_path=self.cache_file)
            updater = InventoryUpdater(
                client=client,
                cache=cache,
                cache_ttl_seconds=self.cache_ttl_days * 86400,
            )

            def on_progress(cur: int, tot: int, part: str) -> None:
                self.progress_signal.emit(cur, tot, part)

            def on_row(res: RowUpdateResult) -> None:
                self.row_result_signal.emit(res)

            self.status_signal.emit(f"Processing '{self.input_file.name}'...")
            stats = updater.update_file(
                input_file=self.input_file,
                output_file=self.output_file,
                field=self.field,
                dry_run=self.dry_run,
                limit=self.limit,
                supplier_filter=self.supplier_filter,
                allow_blank_supplier=self.allow_blank_supplier,
                only_missing=self.only_missing,
                progress_cb=on_progress,
                row_cb=on_row,
                cancel_check=lambda: self._is_cancelled,
            )
            self.finished_signal.emit(stats)
        except AuthenticationError as exc:
            self.error_signal.emit(f"Marcone login failed: {exc}")
        except MarconeError as exc:
            self.error_signal.emit(f"Marcone service error: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.error_signal.emit(f"Unexpected error: {exc}")
        finally:
            client.close()


class ConnectionTestWorker(QThread):
    """Background worker to test credentials without freezing the UI."""

    result_signal = Signal(bool, str)

    def __init__(
        self,
        username: str,
        password: str,
        account_number: str = "",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.username = username
        self.password = password
        self.account_number = account_number

    def run(self) -> None:
        success, msg = check_connection(
            self.username, self.password, self.account_number
        )
        self.result_signal.emit(success, msg)


class CredentialsDialog(QDialog):
    """Modal dialog for managing Marcone credentials."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Marcone Credentials")
        self.setMinimumWidth(440)
        self.test_worker: ConnectionTestWorker | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title_lbl = QLabel("Enter your Marcone Portal Credentials")
        title_lbl.setStyleSheet("font-weight: 600; font-size: 14px; color: #0f172a;")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "These credentials are used to query wholesale pricing from Marcone."
        )
        desc_lbl.setStyleSheet("color: #64748b; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)

        form_layout.addWidget(QLabel("Username or Email:"))
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("e.g. user@example.com")
        form_layout.addWidget(self.user_input)

        form_layout.addWidget(QLabel("Password:"))
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setPlaceholderText("Your Marcone password")
        form_layout.addWidget(self.pass_input)

        form_layout.addWidget(QLabel("Account Number (Optional):"))
        self.acc_input = QLineEdit()
        self.acc_input.setPlaceholderText("Leave blank if not required")
        form_layout.addWidget(self.acc_input)

        layout.addLayout(form_layout)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._on_test_connection)
        self.test_status_lbl = QLabel("")
        self.test_status_lbl.setStyleSheet("font-size: 12px; font-weight: 500;")
        self.test_status_lbl.setWordWrap(True)

        test_row = QHBoxLayout()
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status_lbl, 1)
        layout.addLayout(test_row)

        self.remember_cb = QCheckBox("Save credentials to .env file")
        self.remember_cb.setChecked(True)
        layout.addWidget(self.remember_cb)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save & Use")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self._on_save)

        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self._load_current()

    def _load_current(self) -> None:
        creds = load_credentials()
        self.user_input.setText(creds["username"])
        self.pass_input.setText(creds["password"])
        self.acc_input.setText(creds["account_number"])

    def _on_test_connection(self) -> None:
        user = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()
        acc = self.acc_input.text().strip()

        if not user or not pwd:
            self.test_status_lbl.setText("Enter username and password first.")
            self.test_status_lbl.setStyleSheet("color: #dc2626; font-size: 12px;")
            return

        self.test_btn.setEnabled(False)
        self.test_status_lbl.setText("Testing connection...")
        self.test_status_lbl.setStyleSheet("color: #2563eb; font-size: 12px;")

        self.test_worker = ConnectionTestWorker(user, pwd, acc, self)
        self.test_worker.result_signal.connect(self._on_test_result)
        self.test_worker.start()

    def _on_test_result(self, success: bool, msg: str) -> None:
        self.test_btn.setEnabled(True)
        if success:
            self.test_status_lbl.setText("Login verified successfully!")
            self.test_status_lbl.setStyleSheet(
                "color: #16a34a; font-size: 12px; font-weight: 600;"
            )
        else:
            self.test_status_lbl.setText(msg)
            self.test_status_lbl.setStyleSheet("color: #dc2626; font-size: 12px;")

    def _on_save(self) -> None:
        user = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()
        acc = self.acc_input.text().strip()

        if not user or not pwd:
            QMessageBox.warning(
                self, "Required Fields", "Username and password are required."
            )
            return

        if self.remember_cb.isChecked():
            save_credentials(user, pwd, acc)
        else:
            os.environ["MARCONE_USERNAME"] = user
            os.environ["MARCONE_PASSWORD"] = pwd
            if acc:
                os.environ["MARCONE_ACCOUNT_NUMBER"] = acc


class FileDropArea(QFrame):
    """Drag-and-drop zone and file picker card."""

    file_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setStyleSheet(
            """
            #dropArea {
                border: 2px dashed #94a3b8;
                border-radius: 10px;
                background-color: #ffffff;
                padding: 18px;
            }
            #dropArea:hover {
                border-color: #2563eb;
                background-color: #f8fafc;
            }
            """
        )

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(8)

        icon_lbl = QLabel("📊")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_lbl.setFont(icon_font)
        empty_layout.addWidget(icon_lbl)

        prompt_lbl = QLabel("Drag & drop an inventory spreadsheet here (.xlsx)")
        prompt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #1e293b;")
        empty_layout.addWidget(prompt_lbl)

        sub_lbl = QLabel("or select a file from your computer")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
        empty_layout.addWidget(sub_lbl)

        self.browse_btn = QPushButton("Browse Files...")
        self.browse_btn.setFixedWidth(140)
        self.browse_btn.setStyleSheet("margin-top: 4px; padding: 8px 16px;")
        self.browse_btn.clicked.connect(self._on_browse)
        empty_layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.layout.addWidget(self.empty_widget)

        self.selected_widget = QWidget()
        self.selected_widget.setVisible(False)
        sel_layout = QVBoxLayout(self.selected_widget)
        sel_layout.setSpacing(6)

        sel_top_row = QHBoxLayout()
        self.file_name_lbl = QLabel("")
        self.file_name_lbl.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #0f172a;"
        )
        sel_top_row.addWidget(self.file_name_lbl, 1)

        self.change_btn = QPushButton("Change File")
        self.change_btn.clicked.connect(self._on_browse)
        sel_top_row.addWidget(self.change_btn)
        sel_layout.addLayout(sel_top_row)

        self.file_path_lbl = QLabel("")
        self.file_path_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        sel_layout.addWidget(self.file_path_lbl)

        self.badges_layout = QHBoxLayout()
        self.badges_layout.setSpacing(8)
        self.row_badge = QLabel("")
        self.col_badge = QLabel("")
        self.badges_layout.addWidget(self.row_badge)
        self.badges_layout.addWidget(self.col_badge)
        self.badges_layout.addStretch(1)
        sel_layout.addLayout(self.badges_layout)

        self.layout.addWidget(self.selected_widget)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith((".xlsx", ".xslx")) for u in urls):
                event.acceptProposedAction()
                self.setStyleSheet(
                    """
                    #dropArea {
                        border: 2px dashed #2563eb;
                        border-radius: 10px;
                        background-color: #eff6ff;
                        padding: 18px;
                    }
                    """
                )

    def dragLeaveEvent(self, event: Any) -> None:
        self.setStyleSheet(
            """
            #dropArea {
                border: 2px dashed #94a3b8;
                border-radius: 10px;
                background-color: #ffffff;
                padding: 18px;
            }
            #dropArea:hover {
                border-color: #2563eb;
                background-color: #f8fafc;
            }
            """
        )

    def dropEvent(self, event: QDropEvent) -> None:
        self.dragLeaveEvent(None)
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if local_path.lower().endswith((".xlsx", ".xslx")):
                self.set_file(local_path)
                break

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Inventory Excel Spreadsheet",
            str(Path.home()),
            "Excel Spreadsheets (*.xlsx *.xslx);;All Files (*)",
        )
        if path:
            self.set_file(path)

    def set_file(self, file_path: str) -> None:
        path = Path(file_path)
        try:
            info = get_file_info(path)
            self.empty_widget.setVisible(False)
            self.selected_widget.setVisible(True)

            self.file_name_lbl.setText(f"📄 {path.name}")
            self.file_path_lbl.setText(str(path))

            self.row_badge.setText(f"✓ {info['row_count']:,} items")
            self.row_badge.setStyleSheet(
                "background-color: #dcfce7; color: #166534; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;"
            )

            cols_verified = info["has_part_col"] and (
                info["has_cost_col"] or info["has_price_col"]
            )
            if cols_verified:
                self.col_badge.setText("✓ Columns detected")
                self.col_badge.setStyleSheet(
                    "background-color: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;"
                )
            else:
                self.col_badge.setText("⚠ Missing part/price columns")
                self.col_badge.setStyleSheet(
                    "background-color: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;"
                )

            self.file_selected.emit(str(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Invalid File", f"Could not inspect Excel file:\n{exc}"
            )


class MainWindow(QMainWindow):
    """Main desktop application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tech2K Inventory Pricing Updater")
        self.resize(980, 750)
        self.setMinimumSize(820, 600)

        self.selected_file_path: Path | None = None
        self.output_file_path: Path | None = None
        self.worker: UpdateWorker | None = None

        self._init_ui()
        self._update_connection_chip()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(24, 20, 24, 20)

        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        app_title = QLabel("Tech2K Inventory Pricing Updater")
        app_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0f172a;")
        app_sub = QLabel(
            "Sync Excel inventory spreadsheets with live wholesale pricing from Marcone"
        )
        app_sub.setStyleSheet("font-size: 12px; color: #64748b;")
        title_box.addWidget(app_title)
        title_box.addWidget(app_sub)
        header_row.addLayout(title_box, 1)

        self.conn_chip = QLabel("○ Marcone: Not configured")
        self.conn_chip.setStyleSheet(
            "padding: 5px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; background-color: #f1f5f9; color: #64748b;"
        )
        self.creds_btn = QPushButton("Credentials...")
        self.creds_btn.clicked.connect(self._open_credentials)

        header_row.addWidget(self.conn_chip)
        header_row.addWidget(self.creds_btn)
        main_layout.addLayout(header_row)

        self.drop_area = FileDropArea()
        self.drop_area.file_selected.connect(self._on_file_selected)
        main_layout.addWidget(self.drop_area)

        options_group = QGroupBox("Update Options")
        options_layout = QVBoxLayout(options_group)
        options_layout.setSpacing(10)
        options_layout.setContentsMargins(16, 16, 16, 14)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Output file:"))
        self.radio_new_file = QRadioButton("Save to new file (<name>_updated.xlsx)")
        self.radio_new_file.setChecked(True)
        self.radio_overwrite = QRadioButton("Overwrite original spreadsheet")
        dest_row.addWidget(self.radio_new_file)
        dest_row.addWidget(self.radio_overwrite)
        dest_row.addStretch(1)
        options_layout.addLayout(dest_row)

        opts_row = QHBoxLayout()
        self.cb_missing_only = QCheckBox("Only update missing prices (blank or zero)")
        self.cb_missing_only.setChecked(True)
        self.cb_dry_run = QCheckBox("Dry run (Preview changes without writing)")
        opts_row.addWidget(self.cb_missing_only)
        opts_row.addWidget(self.cb_dry_run)
        opts_row.addStretch(1)
        options_layout.addLayout(opts_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Supplier filter:"))
        self.supplier_input = QLineEdit("Marcone")
        self.supplier_input.setFixedWidth(120)
        filter_row.addWidget(self.supplier_input)

        self.cb_blank_supplier = QCheckBox("Allow blank suppliers")
        self.cb_blank_supplier.setChecked(True)
        filter_row.addWidget(self.cb_blank_supplier)

        filter_row.addSpacing(20)
        filter_row.addWidget(QLabel("Row limit (0 = all):"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 100000)
        self.limit_spin.setValue(0)
        self.limit_spin.setFixedWidth(80)
        filter_row.addWidget(self.limit_spin)
        filter_row.addStretch(1)

        options_layout.addLayout(filter_row)
        main_layout.addWidget(options_group)

        # Action Buttons
        act_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Price Update")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._on_start)
        act_row.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        act_row.addWidget(self.cancel_btn)

        act_row.addStretch(1)

        self.lbl_updated = QLabel("Updated: 0")
        self.lbl_updated.setStyleSheet(
            "padding: 4px 8px; border-radius: 4px; background-color: #dcfce7; color: #166534; font-weight: 600; font-size: 11px;"
        )
        self.lbl_notfound = QLabel("Not Found: 0")
        self.lbl_notfound.setStyleSheet(
            "padding: 4px 8px; border-radius: 4px; background-color: #fef3c7; color: #92400e; font-weight: 600; font-size: 11px;"
        )
        self.lbl_skipped = QLabel("Skipped: 0")
        self.lbl_skipped.setStyleSheet(
            "padding: 4px 8px; border-radius: 4px; background-color: #f1f5f9; color: #475569; font-weight: 600; font-size: 11px;"
        )
        self.lbl_errors = QLabel("Errors: 0")
        self.lbl_errors.setStyleSheet(
            "padding: 4px 8px; border-radius: 4px; background-color: #fee2e2; color: #991b1b; font-weight: 600; font-size: 11px;"
        )

        act_row.addWidget(self.lbl_updated)
        act_row.addWidget(self.lbl_notfound)
        act_row.addWidget(self.lbl_skipped)
        act_row.addWidget(self.lbl_errors)
        main_layout.addLayout(act_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready. Select a spreadsheet to begin.")
        self.status_lbl.setStyleSheet("font-size: 12px; color: #64748b;")
        main_layout.addWidget(self.status_lbl)

        self.success_frame = QFrame()
        self.success_frame.setVisible(False)
        self.success_frame.setStyleSheet(
            "background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px;"
        )
        succ_layout = QHBoxLayout(self.success_frame)
        self.succ_lbl = QLabel("Update completed successfully!")
        self.succ_lbl.setStyleSheet("font-weight: 600; color: #166534;")
        succ_layout.addWidget(self.succ_lbl, 1)

        self.open_excel_btn = QPushButton("Open in Excel")
        self.open_excel_btn.clicked.connect(self._open_in_excel)
        succ_layout.addWidget(self.open_excel_btn)

        self.show_folder_btn = QPushButton("Show in Folder")
        self.show_folder_btn.clicked.connect(self._show_in_folder)
        succ_layout.addWidget(self.show_folder_btn)
        main_layout.addWidget(self.success_frame)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Row", "Part Number", "Status", "Cost", "Price"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        main_layout.addWidget(self.table, 1)

    def _update_connection_chip(self) -> None:
        creds = load_credentials()
        if creds.get("username"):
            self.conn_chip.setText(f"● Marcone: {creds['username']}")
            self.conn_chip.setStyleSheet(
                "padding: 5px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; background-color: #dcfce7; color: #166534;"
            )
        else:
            self.conn_chip.setText("○ Marcone: Not configured")
            self.conn_chip.setStyleSheet(
                "padding: 5px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; background-color: #f1f5f9; color: #64748b;"
            )

    def _open_credentials(self) -> None:
        dlg = CredentialsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._update_connection_chip()
            if self.selected_file_path:
                self.start_btn.setEnabled(True)

    def _on_file_selected(self, file_path: str) -> None:
        self.selected_file_path = Path(file_path)
        creds = load_credentials()
        if creds.get("username") and creds.get("password"):
            self.start_btn.setEnabled(True)
        else:
            self.start_btn.setEnabled(False)
            self._open_credentials()

    def _on_start(self) -> None:
        if not self.selected_file_path:
            return

        creds = load_credentials()
        if not creds.get("username") or not creds.get("password"):
            self._open_credentials()
            return

        if self.radio_new_file.isChecked():
            stem = self.selected_file_path.stem
            ext = self.selected_file_path.suffix
            self.output_file_path = self.selected_file_path.with_name(
                f"{stem}_updated{ext}"
            )
        else:
            self.output_file_path = self.selected_file_path

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.success_frame.setVisible(False)
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.lbl_updated.setText("Updated: 0")
        self.lbl_notfound.setText("Not Found: 0")
        self.lbl_skipped.setText("Skipped: 0")
        self.lbl_errors.setText("Errors: 0")

        supplier_filter = self.supplier_input.text().strip() or None
        limit_val = self.limit_spin.value() or None

        self.worker = UpdateWorker(
            input_file=self.selected_file_path,
            output_file=self.output_file_path,
            field="both",
            dry_run=self.cb_dry_run.isChecked(),
            supplier_filter=supplier_filter,
            allow_blank_supplier=self.cb_blank_supplier.isChecked(),
            only_missing=self.cb_missing_only.isChecked(),
            limit=limit_val,
            username=creds["username"],
            password=creds["password"],
            account_number=creds.get("account_number", ""),
            parent=self,
        )

        self.worker.progress_signal.connect(self._on_progress)
        self.worker.row_result_signal.connect(self._on_row_result)
        self.worker.status_signal.connect(self._on_status)
        self.worker.finished_signal.connect(self._on_worker_finished)
        self.worker.error_signal.connect(self._on_worker_error)
        self.worker.start()

    def _on_cancel(self) -> None:
        if self.worker:
            self.status_lbl.setText("Cancelling update gracefully...")
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)

    def _on_status(self, msg: str) -> None:
        self.status_lbl.setText(msg)

    def _on_progress(self, current: int, total: int, part_no: str) -> None:
        pct = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.status_lbl.setText(f"Checking row {current:,} of {total:,} ({part_no})...")

    def _on_row_result(self, res: RowUpdateResult) -> None:
        row_pos = self.table.rowCount()
        self.table.insertRow(row_pos)

        item_row = QTableWidgetItem(str(res.row_idx))
        item_row.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row_pos, 0, item_row)

        item_part = QTableWidgetItem(res.part_no)
        self.table.setItem(row_pos, 1, item_part)

        item_status = QTableWidgetItem(res.status.upper())
        item_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if res.status == "updated":
            item_status.setForeground(QColor("#16a34a"))
        elif res.status == "not_found":
            item_status.setForeground(QColor("#d97706"))
        elif res.status == "error":
            item_status.setForeground(QColor("#dc2626"))
        else:
            item_status.setForeground(QColor("#64748b"))
        self.table.setItem(row_pos, 2, item_status)

        cost_str = (
            f"${res.old_cost:.2f} → ${res.new_cost:.2f}"
            if res.new_cost is not None and res.old_cost is not None
            else (f"${res.new_cost:.2f}" if res.new_cost is not None else "-")
        )
        item_cost = QTableWidgetItem(cost_str)
        self.table.setItem(row_pos, 3, item_cost)

        price_str = (
            f"${res.old_price:.2f} → ${res.new_price:.2f}"
            if res.new_price is not None and res.old_price is not None
            else (f"${res.new_price:.2f}" if res.new_price is not None else "-")
        )
        details = f"{price_str}  ({res.message})" if res.message else price_str
        item_price = QTableWidgetItem(details)
        self.table.setItem(row_pos, 4, item_price)

        self.table.scrollToBottom()

    def _on_worker_finished(self, stats: UpdateStats) -> None:
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setValue(100)

        self.lbl_updated.setText(f"Updated: {stats.updated:,}")
        self.lbl_notfound.setText(f"Not Found: {stats.not_found:,}")
        self.lbl_skipped.setText(f"Skipped: {stats.skipped:,}")
        self.lbl_errors.setText(f"Errors: {stats.errors:,}")

        if stats.cancelled:
            self.status_lbl.setText("Operation cancelled by user.")
        else:
            self.status_lbl.setText(
                f"Finished! {stats.updated:,} prices updated out of {stats.total_rows:,} rows."
            )
            if not self.cb_dry_run.isChecked() and stats.updated > 0:
                self.success_frame.setVisible(True)
                self.succ_lbl.setText(
                    f"Saved {stats.updated:,} updated prices to '{self.output_file_path.name}'."
                )

    def _on_worker_error(self, err_msg: str) -> None:
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_lbl.setText(f"Error: {err_msg}")
        QMessageBox.critical(self, "Update Error", f"An error occurred:\n{err_msg}")

    def _open_in_excel(self) -> None:
        if self.output_file_path and self.output_file_path.exists():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.output_file_path.resolve()))
            )

    def _show_in_folder(self) -> None:
        if not self.output_file_path or not self.output_file_path.exists():
            return
        target = str(self.output_file_path.resolve())
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", "-R", target], check=False)
        elif system == "Windows":
            subprocess.run(["explorer", f"/select,{target}"], check=False)
        else:
            folder = str(self.output_file_path.parent.resolve())
            subprocess.run(["xdg-open", folder], check=False)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the GUI application."""
    app = QApplication(argv or sys.argv)
    app.setStyleSheet(MAIN_STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
