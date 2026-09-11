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
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
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

from inventory_updater.cache import PriceCache, get_default_cache_path
from inventory_updater.credentials import (
    check_connection,
    load_credentials,
    save_credentials,
)
from inventory_updater.styles import (
    get_status_colors,
    get_stylesheet,
)
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
        cache_file: str | None = None,
        cache_ttl_days: float = 7.0,
        workers: int = 3,
        throttle_seconds: float = 0.2,
        cache_chunk_size: int = 500,
        lookahead: int | None = None,
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
        self.cache_file = cache_file or get_default_cache_path()
        self.cache_ttl_days = cache_ttl_days
        self.workers = workers
        self.throttle_seconds = throttle_seconds
        self.cache_chunk_size = cache_chunk_size
        self.lookahead = lookahead
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        client = MarconeClient(throttle_seconds=self.throttle_seconds)
        try:
            self.status_signal.emit(f"Connecting to Marcone as {self.username}...")
            client.login(
                username=self.username,
                password=self.password,
                customer_number=self.account_number or None,
            )

            self.status_signal.emit("Initializing price cache...")
            cache = PriceCache(
                db_path=self.cache_file, chunk_size=self.cache_chunk_size
            )
            updater = InventoryUpdater(
                client=client,
                cache=cache,
                cache_ttl_seconds=self.cache_ttl_days * 86400,
                workers=self.workers,
                cache_chunk_size=self.cache_chunk_size,
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
                workers=self.workers,
                lookahead=self.lookahead,
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
        self.setMinimumWidth(460)
        self.test_worker: ConnectionTestWorker | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title_lbl = QLabel("Enter your Marcone Portal Credentials")
        title_lbl.setProperty("role", "heading")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "These credentials are used to query live wholesale pricing from Marcone."
        )
        desc_lbl.setProperty("role", "caption")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        u_box = QVBoxLayout()
        u_box.setSpacing(2)
        lbl_user = QLabel("Account Number or Username:")
        lbl_user.setProperty("role", "rowLabel")
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("e.g. 123456 or user@example.com")
        self.user_input.setToolTip(
            "Enter your primary Marcone customer account number or portal login username."
        )
        user_cap = QLabel(
            "Your Marcone customer account number or portal login username."
        )
        user_cap.setProperty("role", "caption")
        user_cap.setWordWrap(True)
        u_box.addWidget(lbl_user)
        u_box.addWidget(self.user_input)
        u_box.addWidget(user_cap)
        form_layout.addLayout(u_box)

        p_box = QVBoxLayout()
        p_box.setSpacing(2)
        lbl_pass = QLabel("Password:")
        lbl_pass.setProperty("role", "rowLabel")
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setPlaceholderText("Your Marcone password")
        self.pass_input.setToolTip("Enter your Marcone portal account password.")
        pass_cap = QLabel("Your Marcone portal account password.")
        pass_cap.setProperty("role", "caption")
        pass_cap.setWordWrap(True)
        p_box.addWidget(lbl_pass)
        p_box.addWidget(self.pass_input)
        p_box.addWidget(pass_cap)
        form_layout.addLayout(p_box)

        a_box = QVBoxLayout()
        a_box.setSpacing(2)
        lbl_acc = QLabel("Sub-Account / Ship-To (Optional):")
        lbl_acc.setProperty("role", "rowLabel")
        self.acc_input = QLineEdit()
        self.acc_input.setPlaceholderText("Leave blank if not required")
        self.acc_input.setToolTip(
            "Optional customer sub-account or ship-to ID. Leave blank if your account has a single location."
        )
        acc_cap = QLabel(
            "Only required for parent accounts that manage multiple ship-to location IDs."
        )
        acc_cap.setProperty("role", "caption")
        acc_cap.setWordWrap(True)
        a_box.addWidget(lbl_acc)
        a_box.addWidget(self.acc_input)
        a_box.addWidget(acc_cap)
        form_layout.addLayout(a_box)

        layout.addLayout(form_layout)

        self.test_btn = QPushButton("Test Connection")
        self.test_btn.setToolTip("Verify these credentials against Marcone servers.")
        self.test_btn.clicked.connect(self._on_test_connection)
        self.test_status_lbl = QLabel("")
        self.test_status_lbl.setProperty("role", "caption")
        self.test_status_lbl.setWordWrap(True)

        test_row = QHBoxLayout()
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status_lbl, 1)
        layout.addLayout(test_row)

        rem_box = QVBoxLayout()
        rem_box.setSpacing(2)
        self.remember_cb = QCheckBox("Save credentials to .env file")
        self.remember_cb.setChecked(True)
        self.remember_cb.setToolTip(
            "Store credentials in local .env configuration so you don't have to re-enter them."
        )
        rem_cap = QLabel(
            "Saves credentials locally in .env. Uncheck to keep credentials in memory for this session only."
        )
        rem_cap.setProperty("role", "caption")
        rem_cap.setWordWrap(True)
        rem_box.addWidget(self.remember_cb)
        rem_box.addWidget(rem_cap)
        layout.addLayout(rem_box)

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
        self.user_input.setText(creds.get("username", ""))
        self.pass_input.setText(creds.get("password", ""))
        self.acc_input.setText(creds.get("account_number", ""))

    def _on_test_connection(self) -> None:
        user = self.user_input.text().strip()
        pwd = self.pass_input.text().strip()
        acc = self.acc_input.text().strip()

        if not user or not pwd:
            self.test_status_lbl.setText("Enter username and password first.")
            self.test_status_lbl.setStyleSheet("color: #dc2626;")
            return

        self.test_btn.setEnabled(False)
        self.test_status_lbl.setText("Testing connection...")
        self.test_status_lbl.setStyleSheet("color: #2563eb;")

        self.test_worker = ConnectionTestWorker(user, pwd, acc, self)
        self.test_worker.result_signal.connect(self._on_test_result)
        self.test_worker.start()

    def _on_test_result(self, success: bool, msg: str) -> None:
        self.test_btn.setEnabled(True)
        if success:
            self.test_status_lbl.setText("Login verified successfully!")
            self.test_status_lbl.setStyleSheet("color: #16a34a; font-weight: 600;")
        else:
            self.test_status_lbl.setText(msg)
            self.test_status_lbl.setStyleSheet("color: #dc2626;")

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

        self.accept()


class AdvancedSettingsDialog(QDialog):
    """Modal dialog for configuring concurrency, throttling, and caching."""

    def __init__(
        self,
        workers: int = 3,
        throttle_seconds: float = 0.20,
        cache_chunk_size: int = 500,
        lookahead: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Performance & Concurrency Settings")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title_lbl = QLabel("Performance & Concurrency Settings")
        title_lbl.setProperty("role", "heading")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Configure worker threads, network rate throttling, and cache batching for inventory updates."
        )
        desc_lbl.setProperty("role", "caption")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        form_layout = QGridLayout()
        form_layout.setVerticalSpacing(12)
        form_layout.setHorizontalSpacing(14)

        lbl_workers = QLabel("Worker Threads:")
        lbl_workers.setProperty("role", "rowLabel")
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 16)
        self.workers_spin.setValue(workers)
        self.workers_spin.setFixedWidth(80)
        self.workers_spin.setToolTip(
            "Number of parallel worker threads querying Marcone (corresponds to --workers in CLI)."
        )
        workers_box = QVBoxLayout()
        w_row = QHBoxLayout()
        w_row.addWidget(self.workers_spin)
        w_suffix = QLabel("threads (default: 3)")
        w_suffix.setProperty("role", "caption")
        w_row.addWidget(w_suffix)
        w_row.addStretch(1)
        workers_box.addLayout(w_row)
        workers_cap = QLabel(
            "Number of simultaneous requests to Marcone. Higher values speed up large catalogs but increase network load."
        )
        workers_cap.setProperty("role", "caption")
        workers_cap.setWordWrap(True)
        workers_box.addWidget(workers_cap)

        form_layout.addWidget(lbl_workers, 0, 0, Qt.AlignmentFlag.AlignTop)
        form_layout.addLayout(workers_box, 0, 1)

        lbl_throttle = QLabel("Request Throttle:")
        lbl_throttle.setProperty("role", "rowLabel")
        self.throttle_spin = QDoubleSpinBox()
        self.throttle_spin.setRange(0.0, 5.0)
        self.throttle_spin.setSingleStep(0.05)
        self.throttle_spin.setDecimals(2)
        self.throttle_spin.setValue(throttle_seconds)
        self.throttle_spin.setSuffix(" s")
        self.throttle_spin.setFixedWidth(80)
        self.throttle_spin.setToolTip(
            "Minimum delay between HTTP requests across all threads (corresponds to --throttle in CLI)."
        )
        throttle_box = QVBoxLayout()
        t_row = QHBoxLayout()
        t_row.addWidget(self.throttle_spin)
        t_suffix = QLabel("delay (default: 0.20 s)")
        t_suffix.setProperty("role", "caption")
        t_row.addWidget(t_suffix)
        t_row.addStretch(1)
        throttle_box.addLayout(t_row)
        throttle_cap = QLabel(
            "Enforces a minimum pause between requests to prevent triggering rate limits or bans from Marcone."
        )
        throttle_cap.setProperty("role", "caption")
        throttle_cap.setWordWrap(True)
        throttle_box.addWidget(throttle_cap)

        form_layout.addWidget(lbl_throttle, 1, 0, Qt.AlignmentFlag.AlignTop)
        form_layout.addLayout(throttle_box, 1, 1)

        lbl_batch = QLabel("Cache Batch Size:")
        lbl_batch.setProperty("role", "rowLabel")
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(50, 2000)
        self.batch_spin.setSingleStep(50)
        self.batch_spin.setValue(cache_chunk_size)
        self.batch_spin.setFixedWidth(80)
        self.batch_spin.setToolTip(
            "Number of items per SQLite cache query chunk (corresponds to --cache-chunk-size in CLI)."
        )
        batch_box = QVBoxLayout()
        b_row = QHBoxLayout()
        b_row.addWidget(self.batch_spin)
        b_suffix = QLabel("items (default: 500)")
        b_suffix.setProperty("role", "caption")
        b_row.addWidget(b_suffix)
        b_row.addStretch(1)
        batch_box.addLayout(b_row)
        batch_cap = QLabel(
            "Number of rows fetched per SQLite query when checking local cache before sending web requests."
        )
        batch_cap.setProperty("role", "caption")
        batch_cap.setWordWrap(True)
        batch_box.addWidget(batch_cap)

        form_layout.addWidget(lbl_batch, 2, 0, Qt.AlignmentFlag.AlignTop)
        form_layout.addLayout(batch_box, 2, 1)

        lbl_lookahead = QLabel("Prefetch Window:")
        lbl_lookahead.setProperty("role", "rowLabel")
        self.lookahead_spin = QSpinBox()
        self.lookahead_spin.setRange(0, 500)
        self.lookahead_spin.setSingleStep(10)
        self.lookahead_spin.setValue(lookahead)
        self.lookahead_spin.setFixedWidth(80)
        self.lookahead_spin.setToolTip(
            "Number of upcoming rows to pre-queue for worker threads (0 = auto-calculate from thread count)."
        )
        lookahead_box = QVBoxLayout()
        l_row = QHBoxLayout()
        l_row.addWidget(self.lookahead_spin)
        l_suffix = QLabel("rows (0 = auto)")
        l_suffix.setProperty("role", "caption")
        l_row.addWidget(l_suffix)
        l_row.addStretch(1)
        lookahead_box.addLayout(l_row)
        lookahead_cap = QLabel(
            "Controls buffer depth for feeding worker threads. 0 automatically scales with thread count."
        )
        lookahead_cap.setProperty("role", "caption")
        lookahead_cap.setWordWrap(True)
        lookahead_box.addWidget(lookahead_cap)

        form_layout.addWidget(lbl_lookahead, 3, 0, Qt.AlignmentFlag.AlignTop)
        form_layout.addLayout(lookahead_box, 3, 1)

        layout.addLayout(form_layout)

        btn_row = QHBoxLayout()
        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.setToolTip("Reset all settings to recommended default values.")
        self.reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(self.reset_btn)

        btn_row.addStretch(1)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.clicked.connect(self.accept)

        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

    def _reset_defaults(self) -> None:
        self.workers_spin.setValue(3)
        self.throttle_spin.setValue(0.20)
        self.batch_spin.setValue(500)
        self.lookahead_spin.setValue(0)


class FileDropArea(QFrame):
    """Drag-and-drop zone and file picker card."""

    file_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")

        self.file_info: dict[str, Any] | None = None

        self.layout = QVBoxLayout(self)
        self.layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.layout.setContentsMargins(12, 8, 12, 8)
        self.layout.setSpacing(6)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(4)

        icon_lbl = QLabel("📊")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_font = QFont()
        icon_font.setPointSize(26)
        icon_lbl.setFont(icon_font)
        empty_layout.addWidget(icon_lbl)

        prompt_lbl = QLabel("Drag & drop an inventory spreadsheet here (.xlsx)")
        prompt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt_lbl.setProperty("role", "heading")
        empty_layout.addWidget(prompt_lbl)

        sub_lbl = QLabel("or select a file from your computer")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setProperty("role", "subtitle")
        empty_layout.addWidget(sub_lbl)

        self.browse_btn = QPushButton("Browse Files...")
        self.browse_btn.setFixedWidth(140)
        self.browse_btn.setToolTip(
            "Choose an Excel spreadsheet (.xlsx) from your computer."
        )
        self.browse_btn.clicked.connect(self._on_browse)
        empty_layout.addWidget(self.browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.layout.addWidget(self.empty_widget)

        self.selected_widget = QWidget()
        self.selected_widget.setVisible(False)
        sel_layout = QVBoxLayout(self.selected_widget)
        sel_layout.setSpacing(6)

        sel_top_row = QHBoxLayout()
        self.file_name_lbl = QLabel("")
        self.file_name_lbl.setProperty("role", "heading")
        sel_top_row.addWidget(self.file_name_lbl, 1)

        self.change_btn = QPushButton("Change File")
        self.change_btn.setToolTip("Select a different inventory spreadsheet.")
        self.change_btn.clicked.connect(self._on_browse)
        sel_top_row.addWidget(self.change_btn)
        sel_layout.addLayout(sel_top_row)

        self.file_path_lbl = QLabel("")
        self.file_path_lbl.setProperty("role", "caption")
        sel_layout.addWidget(self.file_path_lbl)

        self.badges_layout = QHBoxLayout()
        self.badges_layout.setSpacing(8)
        self.row_badge = QLabel("")
        self.row_badge.setObjectName("fileBadgeRow")
        self.col_badge = QLabel("")
        self.col_badge.setObjectName("fileBadgeColOk")
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
                self.setProperty("dragOver", True)
                self.style().unpolish(self)
                self.style().polish(self)

    def dragLeaveEvent(self, event: Any) -> None:
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)

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

    def _update_badges(self, info: dict[str, Any]) -> None:
        self.row_badge.setText(f"✓ {info['row_count']:,} items")
        self.row_badge.setObjectName("fileBadgeRow")
        self.row_badge.style().unpolish(self.row_badge)
        self.row_badge.style().polish(self.row_badge)

        cols_verified = info["has_part_col"] and (
            info["has_cost_col"] or info["has_price_col"]
        )
        if cols_verified:
            self.col_badge.setText("✓ Columns detected")
            self.col_badge.setObjectName("fileBadgeColOk")
        else:
            self.col_badge.setText("⚠ Missing part/price columns")
            self.col_badge.setObjectName("fileBadgeColWarn")
        self.col_badge.style().unpolish(self.col_badge)
        self.col_badge.style().polish(self.col_badge)

    def set_file(self, file_path: str) -> None:
        path = Path(file_path)
        try:
            info = get_file_info(path)
            self.file_info = info
            self.empty_widget.setVisible(False)
            self.selected_widget.setVisible(True)

            self.file_name_lbl.setText(f"📄 {path.name}")
            self.file_path_lbl.setText(str(path))
            self._update_badges(info)
            self.file_selected.emit(str(path))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Invalid File", f"Could not inspect Excel file:\n{exc}"
            )


class MainWindow(QMainWindow):
    """Main desktop application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tech 2000 Inventory Price Updater")
        self.resize(980, 750)
        self.setMinimumSize(840, 640)

        app_icon = self._load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)

        self.selected_file_path: Path | None = None
        self.output_file_path: Path | None = None
        self.worker: UpdateWorker | None = None

        self.adv_dialog = AdvancedSettingsDialog(parent=self)
        self.workers_spin = self.adv_dialog.workers_spin
        self.throttle_spin = self.adv_dialog.throttle_spin
        self.batch_spin = self.adv_dialog.batch_spin
        self.lookahead_spin = self.adv_dialog.lookahead_spin

        app = QApplication.instance()
        if app and hasattr(app, "styleHints") and hasattr(Qt, "ColorScheme"):
            hints = app.styleHints()
            if hasattr(hints, "colorSchemeChanged"):
                hints.colorSchemeChanged.connect(self._on_color_scheme_changed)

        self._init_ui()
        min_width = max(840, self.centralWidget().minimumSizeHint().width())
        self.setMinimumSize(min_width, 640)
        self._apply_theme()
        self._update_connection_chip()

    @staticmethod
    def _is_dark_mode() -> bool:
        app = QApplication.instance()
        if app and hasattr(app, "styleHints") and hasattr(Qt, "ColorScheme"):
            hints = app.styleHints()
            if hasattr(hints, "colorScheme"):
                return hints.colorScheme() == Qt.ColorScheme.Dark
        return False

    def _on_color_scheme_changed(self, _scheme: Any = None) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        is_dark = self._is_dark_mode()
        if app:
            app.setStyleSheet(get_stylesheet(dark=is_dark))
        if hasattr(self, "table"):
            for r in range(self.table.rowCount()):
                status_item = self.table.item(r, 2)
                if status_item:
                    status_item.setForeground(self._status_color(status_item.text()))

    def _status_color(self, status: str) -> QColor:
        status_key = status.strip().lower().replace(" ", "_")
        colors = get_status_colors(self._is_dark_mode())
        hex_color = colors.get(
            status_key,
            "#94a3b8" if self._is_dark_mode() else "#64748b",
        )
        return QColor(hex_color)

    def _open_advanced(self) -> None:
        self.adv_dialog.exec()

    @staticmethod
    def _load_app_icon() -> QIcon:
        """Find and load application icon across package and bundle paths."""
        candidates = [
            Path(__file__).parent / "assets" / "icon.png",
            Path(__file__).parent / "assets" / "icon.ico",
        ]
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            meipass = Path(sys._MEIPASS)
            candidates.extend(
                [
                    meipass / "packaging" / "icon.png",
                    meipass / "packaging" / "icon.ico",
                    meipass / "icon.ico",
                    meipass / "icon.png",
                ]
            )
        for candidate in candidates:
            if candidate.exists():
                icon = QIcon(str(candidate))
                if not icon.isNull():
                    return icon
        return QIcon()

    def _build_header(self) -> QHBoxLayout:
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        app_title = QLabel("Tech 2000 Inventory Price Updater")
        app_title.setProperty("role", "title")
        app_sub = QLabel(
            "Sync Excel inventory spreadsheets with live wholesale pricing from Marcone"
        )
        app_sub.setProperty("role", "subtitle")
        app_sub.setMinimumWidth(app_sub.sizeHint().width())
        title_box.addWidget(app_title)
        title_box.addWidget(app_sub)
        header_row.addLayout(title_box, 1)

        self.conn_chip = QLabel("○ Marcone: Not configured")
        self.conn_chip.setObjectName("connChipUnconfigured")
        self.creds_btn = QPushButton("Credentials...")
        self.creds_btn.setToolTip("View or update Marcone portal login credentials.")
        self.creds_btn.clicked.connect(self._open_credentials)

        self.adv_btn = QPushButton("Advanced...")
        self.adv_btn.setToolTip(
            "Configure worker threads, network throttling delay, and cache batch size."
        )
        self.adv_btn.clicked.connect(self._open_advanced)

        header_row.addWidget(self.conn_chip)
        header_row.addWidget(self.creds_btn)
        header_row.addWidget(self.adv_btn)
        return header_row

    def _build_options_group(self) -> QGroupBox:
        options_group = QGroupBox("Update Options")
        group_layout = QVBoxLayout(options_group)
        group_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        group_layout.setContentsMargins(14, 10, 14, 12)
        group_layout.setSpacing(8)

        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)
        self.options_toggle_btn = QPushButton("▾  Update Options")
        self.options_toggle_btn.setObjectName("optionsToggleBtn")
        self.options_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.options_toggle_btn.setToolTip(
            "Click to collapse or expand update options."
        )
        self.options_toggle_btn.clicked.connect(self._toggle_options)
        header_bar.addWidget(self.options_toggle_btn)

        self.options_summary_lbl = QLabel("")
        self.options_summary_lbl.setObjectName("optionsSummary")
        self.options_summary_lbl.setProperty("role", "caption")
        self.options_summary_lbl.setVisible(False)
        header_bar.addSpacing(10)
        header_bar.addWidget(self.options_summary_lbl)
        header_bar.addStretch(1)
        group_layout.addLayout(header_bar)

        self.options_content = QWidget()
        content_layout = QVBoxLayout(self.options_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        grid = QGridLayout()
        grid.setVerticalSpacing(8)
        grid.setHorizontalSpacing(16)

        def make_row_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setProperty("role", "rowLabel")
            return lbl

        grid.addWidget(
            make_row_label("Output file:"), 0, 0, Qt.AlignmentFlag.AlignVCenter
        )
        self.radio_new_file = QRadioButton("Save to new file (<name>_updated.xlsx)")
        self.radio_new_file.setChecked(True)
        self.radio_new_file.setToolTip(
            "Create a new Excel file with '_updated' appended to the filename, preserving original data."
        )
        self.radio_overwrite = QRadioButton("Overwrite original spreadsheet")
        self.radio_overwrite.setToolTip(
            "Directly update the original Excel file in place (corresponds to --in-place in CLI)."
        )
        grid.addWidget(self.radio_new_file, 0, 1, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.radio_overwrite, 0, 2, Qt.AlignmentFlag.AlignVCenter)

        grid.addWidget(
            make_row_label("Supplier filter:"), 1, 0, Qt.AlignmentFlag.AlignVCenter
        )
        self.supplier_combo = QComboBox()
        self.supplier_combo.setEditable(True)
        self.supplier_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.supplier_combo.setFixedWidth(230)
        self.supplier_combo.lineEdit().setPlaceholderText("Filter or type vendor...")
        self.supplier_combo.addItem("(All Suppliers - No Filter)")
        self.supplier_combo.addItem("Marcone")
        self.supplier_combo.setCurrentText("Marcone")
        self.supplier_combo.setToolTip(
            "Only update parts where the vendor matches this text (case-insensitive).\n"
            "Pick from detected spreadsheet vendors or type a custom filter (corresponds to --supplier-filter in CLI)."
        )
        self.supplier_input = self.supplier_combo.lineEdit()
        grid.addWidget(self.supplier_combo, 1, 1, Qt.AlignmentFlag.AlignVCenter)

        self.cb_blank_supplier = QCheckBox("Allow blank suppliers")
        self.cb_blank_supplier.setChecked(True)
        self.cb_blank_supplier.setToolTip(
            "When checked, rows with an empty vendor column are also updated.\n"
            "Uncheck to only update items with an explicit vendor match (corresponds to --no-allow-blank-supplier in CLI)."
        )
        grid.addWidget(self.cb_blank_supplier, 1, 2, Qt.AlignmentFlag.AlignVCenter)

        grid.addWidget(
            make_row_label("Row limit:"), 2, 0, Qt.AlignmentFlag.AlignVCenter
        )
        lim_row = QHBoxLayout()
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 100000)
        self.limit_spin.setValue(0)
        self.limit_spin.setFixedWidth(90)
        self.limit_spin.setToolTip(
            "Cap the number of updated items (0 = all rows).\n"
            "Useful for testing a small batch before running full catalog (corresponds to --limit in CLI)."
        )
        lim_row.addWidget(self.limit_spin)
        lbl_rows = QLabel("rows")
        lbl_rows.setProperty("role", "caption")
        lim_row.addWidget(lbl_rows)
        lim_row.addStretch(1)
        grid.addLayout(lim_row, 2, 1)

        lbl_limit_help = QLabel("(0 = process all matching rows)")
        lbl_limit_help.setProperty("role", "caption")
        grid.addWidget(lbl_limit_help, 2, 2, Qt.AlignmentFlag.AlignVCenter)

        grid.addWidget(
            make_row_label("Update rules:"), 3, 0, Qt.AlignmentFlag.AlignVCenter
        )
        self.cb_missing_only = QCheckBox("Only update missing prices (blank or zero)")
        self.cb_missing_only.setChecked(False)
        self.cb_missing_only.setToolTip(
            "Only look up parts where cost or price is currently empty or $0.00.\n"
            "Existing pricing will be preserved (corresponds to --only-missing in CLI)."
        )
        grid.addWidget(self.cb_missing_only, 3, 1, Qt.AlignmentFlag.AlignVCenter)

        self.cb_dry_run = QCheckBox("Dry run (preview changes without writing)")
        self.cb_dry_run.setChecked(False)
        self.cb_dry_run.setToolTip(
            "Look up parts and preview changes in the table below without modifying any files (corresponds to --dry-run in CLI)."
        )
        grid.addWidget(self.cb_dry_run, 3, 2, Qt.AlignmentFlag.AlignVCenter)

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)

        content_layout.addLayout(grid)
        group_layout.addWidget(self.options_content)

        self.supplier_combo.currentTextChanged.connect(
            lambda _: self._update_options_summary()
        )
        self.radio_new_file.toggled.connect(lambda _: self._update_options_summary())
        self.limit_spin.valueChanged.connect(lambda _: self._update_options_summary())
        self.cb_missing_only.toggled.connect(lambda _: self._update_options_summary())
        self.cb_dry_run.toggled.connect(lambda _: self._update_options_summary())
        self._update_options_summary()

        return options_group

    def _toggle_options(self) -> None:
        is_visible = self.options_content.isVisible()
        self.options_content.setVisible(not is_visible)
        if is_visible:
            self.options_toggle_btn.setText("▸  Update Options")
            self._update_options_summary()
            self.options_summary_lbl.setVisible(True)
        else:
            self.options_toggle_btn.setText("▾  Update Options")
            self.options_summary_lbl.setVisible(False)

    def _update_options_summary(self) -> None:
        parts: list[str] = []
        supp = self.supplier_combo.currentText().strip()
        if not supp or supp == "(All Suppliers - No Filter)":
            parts.append("All Suppliers")
        else:
            parts.append(supp)
        parts.append(
            "Save to new file"
            if self.radio_new_file.isChecked()
            else "Overwrite original"
        )
        limit_val = self.limit_spin.value()
        if limit_val > 0:
            parts.append(f"Limit: {limit_val:,}")
        if self.cb_missing_only.isChecked():
            parts.append("Missing prices only")
        if self.cb_dry_run.isChecked():
            parts.append("Dry run")
        self.options_summary_lbl.setText(" • ".join(parts))

    def _build_action_bar(self) -> QHBoxLayout:
        act_row = QHBoxLayout()
        self.start_btn = QPushButton("Start Price Update")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setEnabled(False)
        self.start_btn.setToolTip(
            "Start querying Marcone and updating spreadsheet prices."
        )
        self.start_btn.clicked.connect(self._on_start)
        act_row.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip("Gracefully stop in-progress inventory updates.")
        self.cancel_btn.clicked.connect(self._on_cancel)
        act_row.addWidget(self.cancel_btn)
        act_row.addStretch(1)

        self.lbl_updated = QLabel("Updated: 0")
        self.lbl_updated.setObjectName("badgeUpdated")
        self.lbl_notfound = QLabel("Not Found: 0")
        self.lbl_notfound.setObjectName("badgeNotFound")
        self.lbl_skipped = QLabel("Skipped: 0")
        self.lbl_skipped.setObjectName("badgeSkipped")
        self.lbl_errors = QLabel("Errors: 0")
        self.lbl_errors.setObjectName("badgeErrors")

        act_row.addWidget(self.lbl_updated)
        act_row.addWidget(self.lbl_notfound)
        act_row.addWidget(self.lbl_skipped)
        act_row.addWidget(self.lbl_errors)
        return act_row

    def _build_success_frame(self) -> QFrame:
        self.success_frame = QFrame()
        self.success_frame.setObjectName("successFrame")
        self.success_frame.setVisible(False)
        succ_layout = QHBoxLayout(self.success_frame)
        self.succ_lbl = QLabel("Update completed successfully!")
        succ_layout.addWidget(self.succ_lbl, 1)

        self.open_excel_btn = QPushButton("Open in Excel")
        self.open_excel_btn.setToolTip(
            "Open the updated spreadsheet in your default spreadsheet app."
        )
        self.open_excel_btn.clicked.connect(self._open_in_excel)
        succ_layout.addWidget(self.open_excel_btn)

        self.show_folder_btn = QPushButton("Show in Folder")
        self.show_folder_btn.setToolTip(
            "Reveal the updated Excel file in Finder or File Explorer."
        )
        self.show_folder_btn.clicked.connect(self._show_in_folder)
        succ_layout.addWidget(self.show_folder_btn)
        return self.success_frame

    def _build_results_table(self) -> QTableWidget:
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
        return self.table

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 14, 16, 14)

        main_layout.addLayout(self._build_header())

        self.drop_area = FileDropArea()
        self.drop_area.file_selected.connect(self._on_file_selected)
        main_layout.addWidget(self.drop_area)

        main_layout.addWidget(self._build_options_group())
        main_layout.addLayout(self._build_action_bar())

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready. Select a spreadsheet to begin.")
        self.status_lbl.setProperty("role", "caption")
        main_layout.addWidget(self.status_lbl)

        main_layout.addWidget(self._build_success_frame())
        main_layout.addWidget(self._build_results_table(), 1)

    def _update_connection_chip(self) -> None:
        creds = load_credentials()
        if creds.get("username"):
            self.conn_chip.setText(f"● Marcone: {creds['username']}")
            self.conn_chip.setObjectName("connChipConfigured")
        else:
            self.conn_chip.setText("○ Marcone: Not configured")
            self.conn_chip.setObjectName("connChipUnconfigured")
        self.conn_chip.style().unpolish(self.conn_chip)
        self.conn_chip.style().polish(self.conn_chip)

    def _open_credentials(self) -> None:
        dlg = CredentialsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._update_connection_chip()
            if self.selected_file_path:
                self.start_btn.setEnabled(True)

    def _on_file_selected(self, file_path: str) -> None:
        self.selected_file_path = Path(file_path)
        self._populate_suppliers()
        creds = load_credentials()
        if creds.get("username") and creds.get("password"):
            self.start_btn.setEnabled(True)
        else:
            self.start_btn.setEnabled(False)
            self._open_credentials()

    def _populate_suppliers(self) -> None:
        if not self.drop_area.file_info:
            return
        suppliers = self.drop_area.file_info.get("suppliers", [])
        current_text = self.supplier_combo.currentText().strip()

        self.supplier_combo.blockSignals(True)
        self.supplier_combo.clear()
        self.supplier_combo.addItem("(All Suppliers - No Filter)")
        for s in suppliers:
            self.supplier_combo.addItem(s)
        if "Marcone" not in suppliers:
            self.supplier_combo.addItem("Marcone")

        if current_text and current_text not in ("(All Suppliers - No Filter)", ""):
            self.supplier_combo.setCurrentText(current_text)
        elif "Marcone" in suppliers or "Marcone" in [
            self.supplier_combo.itemText(i) for i in range(self.supplier_combo.count())
        ]:
            self.supplier_combo.setCurrentText("Marcone")
        else:
            self.supplier_combo.setCurrentIndex(0)
        self.supplier_combo.blockSignals(False)

    def _determine_output_path(self, input_path: Path) -> Path:
        if self.radio_new_file.isChecked():
            return input_path.with_name(f"{input_path.stem}_updated{input_path.suffix}")
        return input_path

    def _determine_supplier_filter(self) -> str | None:
        supplier_raw = self.supplier_combo.currentText().strip()
        if not supplier_raw or supplier_raw.startswith("(All"):
            return None
        return supplier_raw

    def _reset_run_state(self) -> None:
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.success_frame.setVisible(False)
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.lbl_updated.setText("Updated: 0")
        self.lbl_notfound.setText("Not Found: 0")
        self.lbl_skipped.setText("Skipped: 0")
        self.lbl_errors.setText("Errors: 0")

    @staticmethod
    def _format_cost_diff(res: RowUpdateResult) -> str:
        if res.new_cost is not None and res.old_cost is not None:
            return f"${res.old_cost:.2f} → ${res.new_cost:.2f}"
        if res.new_cost is not None:
            return f"${res.new_cost:.2f}"
        return "-"

    @staticmethod
    def _format_price_diff(res: RowUpdateResult) -> str:
        if res.new_price is not None and res.old_price is not None:
            price_str = f"${res.old_price:.2f} → ${res.new_price:.2f}"
        elif res.new_price is not None:
            price_str = f"${res.new_price:.2f}"
        else:
            price_str = "-"
        return f"{price_str}  ({res.message})" if res.message else price_str

    def _on_start(self) -> None:
        if not self.selected_file_path:
            return

        creds = load_credentials()
        if not creds.get("username") or not creds.get("password"):
            self._open_credentials()
            return

        self.output_file_path = self._determine_output_path(self.selected_file_path)
        self._reset_run_state()

        supplier_filter = self._determine_supplier_filter()
        limit_val = self.limit_spin.value() or None
        lookahead_val = self.lookahead_spin.value() or None

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
            workers=self.workers_spin.value(),
            throttle_seconds=self.throttle_spin.value(),
            cache_chunk_size=self.batch_spin.value(),
            lookahead=lookahead_val,
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
        item_status.setForeground(self._status_color(res.status))
        self.table.setItem(row_pos, 2, item_status)

        item_cost = QTableWidgetItem(self._format_cost_diff(res))
        self.table.setItem(row_pos, 3, item_cost)

        item_price = QTableWidgetItem(self._format_price_diff(res))
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
    app.setApplicationName("Tech 2000 Inventory Price Updater")
    app.setApplicationDisplayName("Tech 2000 Inventory Price Updater")
    app_icon = MainWindow._load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    is_dark = False
    if hasattr(app, "styleHints") and hasattr(Qt, "ColorScheme"):
        hints = app.styleHints()
        if hasattr(hints, "colorScheme"):
            is_dark = hints.colorScheme() == Qt.ColorScheme.Dark
    app.setStyleSheet(get_stylesheet(dark=is_dark))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
