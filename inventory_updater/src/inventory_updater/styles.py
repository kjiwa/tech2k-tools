"""Design tokens and stylesheet for Inventory Updater UI."""

from __future__ import annotations

LIGHT_TOKENS = {
    "bg_window": "#f8fafc",
    "bg_dialog": "#f8fafc",
    "bg_card": "#ffffff",
    "bg_subtle": "#f1f5f9",
    "border_subtle": "#e2e8f0",
    "border_input": "#cbd5e1",
    "border_focus": "#2563eb",
    "text_primary": "#0f172a",
    "text_secondary": "#334155",
    "text_muted": "#64748b",
    "primary": "#2563eb",
    "primary_hover": "#1d4ed8",
    "primary_pressed": "#1e40af",
    "primary_disabled": "#93c5fd",
    "primary_disabled_text": "#eff6ff",
    "cancel": "#ef4444",
    "cancel_hover": "#dc2626",
    "cancel_disabled": "#fca5a5",
    "drop_border": "#94a3b8",
    "drop_hover_border": "#2563eb",
    "drop_hover_bg": "#f8fafc",
    "drop_active_border": "#2563eb",
    "drop_active_bg": "#eff6ff",
    "table_header_bg": "#f8fafc",
    "table_grid": "#f1f5f9",
    "success_bg": "#dcfce7",
    "success_text": "#166534",
    "success_border": "#bbf7d0",
    "warning_bg": "#fef3c7",
    "warning_text": "#92400e",
    "danger_bg": "#fee2e2",
    "danger_text": "#991b1b",
    "info_bg": "#e0f2fe",
    "info_text": "#0369a1",
    "chip_unconfigured_bg": "#f1f5f9",
    "chip_unconfigured_text": "#64748b",
}

DARK_TOKENS = {
    "bg_window": "#0f172a",
    "bg_dialog": "#1e293b",
    "bg_card": "#1e293b",
    "bg_subtle": "#334155",
    "border_subtle": "#334155",
    "border_input": "#475569",
    "border_focus": "#3b82f6",
    "text_primary": "#f8fafc",
    "text_secondary": "#cbd5e1",
    "text_muted": "#94a3b8",
    "primary": "#3b82f6",
    "primary_hover": "#60a5fa",
    "primary_pressed": "#1d4ed8",
    "primary_disabled": "#1e3a5f",
    "primary_disabled_text": "#64748b",
    "cancel": "#ef4444",
    "cancel_hover": "#f87171",
    "cancel_disabled": "#7f1d1d",
    "drop_border": "#475569",
    "drop_hover_border": "#3b82f6",
    "drop_hover_bg": "#243044",
    "drop_active_border": "#3b82f6",
    "drop_active_bg": "#1e3a5f",
    "table_header_bg": "#0f172a",
    "table_grid": "#334155",
    "success_bg": "#064e3b",
    "success_text": "#6ee7b7",
    "success_border": "#047857",
    "warning_bg": "#78350f",
    "warning_text": "#fcd34d",
    "danger_bg": "#7f1d1d",
    "danger_text": "#fca5a5",
    "info_bg": "#0c4a6e",
    "info_text": "#7dd3fc",
    "chip_unconfigured_bg": "#334155",
    "chip_unconfigured_text": "#94a3b8",
}


def get_status_colors(dark: bool = False) -> dict[str, str]:
    """Return status hex colors for results table items."""
    if dark:
        return {
            "updated": "#4ade80",
            "not_found": "#fbbf24",
            "error": "#f87171",
            "skipped": "#94a3b8",
        }
    return {
        "updated": "#16a34a",
        "not_found": "#d97706",
        "error": "#dc2626",
        "skipped": "#64748b",
    }


def get_stylesheet(dark: bool = False) -> str:
    """Generate Qt stylesheet for light or dark mode."""
    t = DARK_TOKENS if dark else LIGHT_TOKENS
    return f"""
QMainWindow {{
    background-color: {t["bg_window"]};
}}

QDialog {{
    background-color: {t["bg_dialog"]};
}}

QWidget {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
    color: {t["text_primary"]};
}}

QLabel {{
    color: {t["text_primary"]};
}}

QLabel[role="caption"] {{
    color: {t["text_muted"]};
    font-size: 11px;
}}

QLabel[role="title"] {{
    font-size: 18px;
    font-weight: 700;
    color: {t["text_primary"]};
}}

QLabel[role="subtitle"] {{
    font-size: 12px;
    color: {t["text_muted"]};
}}

QLabel[role="heading"] {{
    font-size: 14px;
    font-weight: 600;
    color: {t["text_primary"]};
}}

QLabel[role="rowLabel"] {{
    font-weight: 600;
    color: {t["text_secondary"]};
    min-width: 105px;
}}

QGroupBox {{
    font-weight: 600;
    font-size: 13px;
    border: 1px solid {t["border_subtle"]};
    border-radius: 8px;
    margin-top: 0px;
    padding-top: 0px;
    background-color: {t["bg_card"]};
    color: {t["text_primary"]};
}}

QGroupBox::title {{
    height: 0px;
    width: 0px;
    padding: 0px;
    margin: 0px;
    color: transparent;
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {t["bg_card"]};
    border: 1px solid {t["border_input"]};
    border-radius: 6px;
    padding: 6px 10px;
    color: {t["text_primary"]};
    selection-background-color: {t["primary"]};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1.5px solid {t["border_focus"]};
}}

QComboBox {{
    padding-right: 24px;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left-width: 0px;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {t["text_muted"]};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {t["bg_card"]};
    border: 1px solid {t["border_input"]};
    border-radius: 6px;
    selection-background-color: {t["bg_subtle"]};
    selection-color: {t["text_primary"]};
    color: {t["text_primary"]};
    padding: 4px;
    outline: none;
}}

QPushButton {{
    background-color: {t["bg_card"]};
    border: 1px solid {t["border_input"]};
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
    color: {t["text_secondary"]};
}}

QPushButton:hover {{
    background-color: {t["bg_subtle"]};
    border-color: {t["border_focus"]};
    color: {t["text_primary"]};
}}

QPushButton:pressed {{
    background-color: {t["border_subtle"]};
}}

QPushButton:disabled {{
    background-color: {t["bg_subtle"]};
    color: {t["text_muted"]};
    border-color: {t["border_subtle"]};
}}

QPushButton#primaryBtn {{
    background-color: {t["primary"]};
    color: #ffffff;
    border: none;
    font-size: 14px;
    font-weight: 600;
    border-radius: 6px;
    padding: 10px 20px;
}}

QPushButton#primaryBtn:hover {{
    background-color: {t["primary_hover"]};
}}

QPushButton#primaryBtn:pressed {{
    background-color: {t["primary_pressed"]};
}}

QPushButton#primaryBtn:disabled {{
    background-color: {t["primary_disabled"]};
    color: {t["primary_disabled_text"]};
}}

QPushButton#cancelBtn {{
    background-color: {t["cancel"]};
    color: #ffffff;
    border: none;
    font-size: 13px;
    font-weight: 600;
    border-radius: 6px;
    padding: 8px 16px;
}}

QPushButton#cancelBtn:hover {{
    background-color: {t["cancel_hover"]};
}}

QPushButton#cancelBtn:disabled {{
    background-color: {t["cancel_disabled"]};
    color: #ffffff;
}}

QPushButton#optionsToggleBtn {{
    background: transparent;
    border: none;
    font-weight: 600;
    font-size: 13px;
    text-align: left;
    padding: 3px 6px;
    border-radius: 4px;
    color: {t["text_secondary"]};
}}

QPushButton#optionsToggleBtn:hover {{
    color: {t["text_primary"]};
    background-color: {t["bg_subtle"]};
}}

QProgressBar {{
    border: 1px solid {t["border_subtle"]};
    border-radius: 6px;
    background-color: {t["bg_subtle"]};
    height: 14px;
    text-align: center;
    font-size: 11px;
    font-weight: 600;
    color: {t["text_primary"]};
}}

QProgressBar::chunk {{
    background-color: {t["primary"]};
    border-radius: 5px;
}}

QTableWidget {{
    background-color: {t["bg_card"]};
    border: 1px solid {t["border_subtle"]};
    border-radius: 6px;
    gridline-color: {t["table_grid"]};
    font-size: 12px;
    color: {t["text_primary"]};
}}

QHeaderView::section {{
    background-color: {t["table_header_bg"]};
    color: {t["text_secondary"]};
    font-weight: 600;
    font-size: 12px;
    padding: 6px;
    border: none;
    border-bottom: 1px solid {t["border_subtle"]};
}}

QCheckBox, QRadioButton {{
    spacing: 8px;
    color: {t["text_secondary"]};
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}

#dropArea {{
    border: 2px dashed {t["drop_border"]};
    border-radius: 10px;
    background-color: {t["bg_card"]};
    padding: 10px;
}}

#dropArea:hover {{
    border-color: {t["drop_hover_border"]};
    background-color: {t["drop_hover_bg"]};
}}

#dropArea[dragOver="true"] {{
    border: 2px dashed {t["drop_active_border"]};
    border-radius: 10px;
    background-color: {t["drop_active_bg"]};
    padding: 10px;
}}

#optionsSummary {{
    color: {t["text_muted"]};
    font-size: 11px;
}}

#connChipConfigured {{
    padding: 5px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    background-color: {t["success_bg"]};
    color: {t["success_text"]};
}}

#connChipUnconfigured {{
    padding: 5px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    background-color: {t["chip_unconfigured_bg"]};
    color: {t["chip_unconfigured_text"]};
}}

#badgeUpdated {{
    padding: 4px 8px;
    border-radius: 4px;
    background-color: {t["success_bg"]};
    color: {t["success_text"]};
    font-weight: 600;
    font-size: 11px;
}}

#badgeNotFound {{
    padding: 4px 8px;
    border-radius: 4px;
    background-color: {t["warning_bg"]};
    color: {t["warning_text"]};
    font-weight: 600;
    font-size: 11px;
}}

#badgeSkipped {{
    padding: 4px 8px;
    border-radius: 4px;
    background-color: {t["bg_subtle"]};
    color: {t["text_secondary"]};
    font-weight: 600;
    font-size: 11px;
}}

#badgeErrors {{
    padding: 4px 8px;
    border-radius: 4px;
    background-color: {t["danger_bg"]};
    color: {t["danger_text"]};
    font-weight: 600;
    font-size: 11px;
}}

#fileBadgeRow {{
    background-color: {t["success_bg"]};
    color: {t["success_text"]};
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 11px;
}}

#fileBadgeColOk {{
    background-color: {t["info_bg"]};
    color: {t["info_text"]};
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 11px;
}}

#fileBadgeColWarn {{
    background-color: {t["danger_bg"]};
    color: {t["danger_text"]};
    padding: 3px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 11px;
}}

#successFrame {{
    background-color: {t["success_bg"]};
    border: 1px solid {t["success_border"]};
    border-radius: 8px;
    padding: 10px;
}}

#successFrame QLabel {{
    font-weight: 600;
    color: {t["success_text"]};
}}
"""


MAIN_STYLESHEET = get_stylesheet(dark=False)
