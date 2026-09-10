"""Design tokens and stylesheet for Inventory Updater UI."""

MAIN_STYLESHEET = """
QMainWindow {
    background-color: #f8fafc;
}

QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
    color: #1e293b;
}

QGroupBox {
    font-weight: 600;
    font-size: 13px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #334155;
}

QLineEdit, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    color: #0f172a;
    selection-background-color: #2563eb;
}

QLineEdit:focus, QSpinBox:focus {
    border: 1.5px solid #2563eb;
    background-color: #ffffff;
}

QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
    color: #334155;
}

QPushButton:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
}

QPushButton:pressed {
    background-color: #e2e8f0;
}

QPushButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton#primaryBtn {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    font-size: 14px;
    font-weight: 600;
    border-radius: 6px;
    padding: 10px 20px;
}

QPushButton#primaryBtn:hover {
    background-color: #1d4ed8;
}

QPushButton#primaryBtn:pressed {
    background-color: #1e40af;
}

QPushButton#primaryBtn:disabled {
    background-color: #93c5fd;
    color: #eff6ff;
}

QPushButton#cancelBtn {
    background-color: #ef4444;
    color: #ffffff;
    border: none;
    font-size: 13px;
    font-weight: 600;
    border-radius: 6px;
    padding: 8px 16px;
}

QPushButton#cancelBtn:hover {
    background-color: #dc2626;
}

QPushButton#cancelBtn:disabled {
    background-color: #fca5a5;
    color: #ffffff;
}

QProgressBar {
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background-color: #e2e8f0;
    height: 14px;
    text-align: center;
    font-size: 11px;
    font-weight: 600;
    color: #1e293b;
}

QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 5px;
}

QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    gridline-color: #f1f5f9;
    font-size: 12px;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 600;
    font-size: 12px;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
}

QCheckBox, QRadioButton {
    spacing: 8px;
    color: #334155;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
"""
