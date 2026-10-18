import tempfile
from pathlib import Path
from string import Template

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPalette, QPen, QPixmap

LIGHT = {
    "bg": "#f4f6fb", "surface": "#ffffff", "surface_alt": "#f8fafc", "border": "#dbe2ec", "text": "#1e293b",
    "muted": "#64748b", "accent": "#2563eb", "accent_hover": "#1d4ed8", "accent_soft": "#dbeafe",
    "danger": "#b91c1c", "danger_soft": "#fef2f2", "danger_border": "#fca5a5", "header_a": "#0f172a",
    "header_b": "#1e3a8a", "table_header": "#eef2f7", "input_bg": "#ffffff", "disabled_bg": "#f1f5f9",
    "disabled_text": "#9ca3af", "log_bg": "#0f172a", "log_text": "#e2e8f0", "ok_row": "#dcfce7",
    "ok_text": "#14532d", "warn": "#b45309", "indicator": "#94a3b8", "scroll": "#cbd5e1",
}
DARK = {
    "bg": "#0f172a", "surface": "#1e293b", "surface_alt": "#18243a", "border": "#334155", "text": "#e2e8f0",
    "muted": "#94a3b8", "accent": "#3b82f6", "accent_hover": "#60a5fa", "accent_soft": "#1e3a8a",
    "danger": "#f87171", "danger_soft": "#3b1d24", "danger_border": "#7f1d1d", "header_a": "#020617",
    "header_b": "#1e3a8a", "table_header": "#243247", "input_bg": "#0f172a", "disabled_bg": "#1e293b",
    "disabled_text": "#64748b", "log_bg": "#020617", "log_text": "#e2e8f0", "ok_row": "#14532d",
    "ok_text": "#dcfce7", "warn": "#fbbf24", "indicator": "#64748b", "scroll": "#475569",
}
THEMES = {"light": LIGHT, "dark": DARK}

# Widgets read colours from this dictionary, so one switch restyles everything.
tokens = dict(LIGHT)
current_name = "light"

STYLESHEET = Template("""
QWidget { color: $text; font-size: 13px; }
QMainWindow, QDialog, QMessageBox { background: $bg; }
QMessageBox QLabel { color: $text; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 4px; }
QFrame#header { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $header_a, stop:1 $header_b); }
QLabel#appTitle { color: white; font-size: 22px; font-weight: 700; }
QLabel#appSubtitle { color: #cbd5e1; }
QPushButton#themeButton { background: rgba(255,255,255,0.12); color: white; border: 1px solid rgba(255,255,255,0.3);
    border-radius: 14px; padding: 5px 14px; }
QPushButton#themeButton:hover { background: rgba(255,255,255,0.25); }
QTabWidget::pane { border: none; background: $bg; }
QTabBar { background: $bg; }
QTabBar::tab { background: transparent; padding: 8px 16px; margin: 8px 3px 6px 3px; color: $muted;
    font-weight: 600; border-radius: 16px; }
QTabBar::tab:selected { color: white; background: $accent; }
QTabBar::tab:hover:!selected { color: $text; background: $accent_soft; }
QGroupBox { background: $surface; border: 1px solid $border; border-radius: 12px; margin-top: 16px;
    padding: 18px 14px 12px 14px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 8px; color: $accent; }
QPushButton { background: $surface; border: 1px solid $border; border-radius: 8px; padding: 7px 16px; }
QPushButton:hover { background: $accent_soft; border-color: $accent; }
QPushButton:disabled { color: $disabled_text; background: $disabled_bg; border-color: $border; }
QPushButton[variant="primary"] { background: $accent; border-color: $accent; color: white; font-weight: 600; }
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:disabled { background: $disabled_bg; border-color: $border; color: $disabled_text; }
QPushButton[variant="danger"] { background: $danger_soft; border-color: $danger_border; color: $danger; font-weight: 600; }
QPushButton[variant="danger"]:hover { border-color: $danger; }
QPushButton[variant="danger"]:disabled { background: $disabled_bg; border-color: $border; color: $disabled_text; }
QPushButton[variant="pager"] { padding: 6px 0; font-weight: 700; }
QPushButton[variant="flat"] { border: none; background: transparent; color: $danger; padding: 4px 8px; }
QPushButton[variant="flat"]:hover { background: $danger_soft; }
QLineEdit, QComboBox, QSpinBox { background: $input_bg; border: 1px solid $border; border-radius: 8px;
    padding: 5px 10px; min-height: 22px; selection-background-color: $accent; selection-color: white; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid $accent; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { background: $disabled_bg; color: $disabled_text; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url($down_icon); width: 12px; height: 12px; }
QSpinBox::up-button, QSpinBox::down-button { width: 20px; border: none; background: transparent; }
QSpinBox::up-arrow { image: url($up_icon); width: 10px; height: 10px; }
QSpinBox::down-arrow { image: url($down_icon); width: 10px; height: 10px; }
QComboBox QAbstractItemView { background: $surface; color: $text; border: 1px solid $border;
    selection-background-color: $accent; selection-color: white; outline: none; }
QComboBox QAbstractItemView::item:disabled { color: $disabled_text; }
QCheckBox, QRadioButton { spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; border: 1px solid $indicator;
    background: $input_bg; }
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 9px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url($check_icon); }
QRadioButton::indicator:checked { border-color: $accent; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
    fx:0.5, fy:0.5, stop:0 $accent, stop:0.45 $accent, stop:0.5 $input_bg, stop:1 $input_bg); }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { background: $disabled_bg; border-color: $border; }
QTableView, QTableWidget { background: $surface; alternate-background-color: $surface_alt; border: 1px solid $border;
    border-radius: 8px; gridline-color: $border; selection-background-color: $accent_soft; selection-color: $text; }
QHeaderView::section { background: $table_header; color: $text; padding: 7px 8px; border: none;
    border-right: 1px solid $border; border-bottom: 1px solid $border; font-weight: 600; }
QTableCornerButton::section { background: $table_header; border: none; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 5px; min-height: 30px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 5px; min-width: 30px; margin: 2px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QProgressBar { border: none; background: $border; border-radius: 9px; text-align: center; min-height: 18px;
    color: $text; font-weight: 600; }
QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent_hover);
    border-radius: 9px; }
QPlainTextEdit { background: $log_bg; color: $log_text; font-family: Consolas, "Cascadia Mono", monospace;
    border-radius: 8px; padding: 8px; border: 1px solid $border; }
QFrame#card { background: $surface; border: 1px solid $border; border-radius: 14px; }
QLabel#cardValue { font-size: 30px; font-weight: 700; color: $accent; }
QLabel#cardCaption { color: $muted; }
QLabel#muted { color: $muted; }
QLabel#error { color: $danger; }
QLabel#emptyState { color: $muted; font-size: 15px; background: $surface; border: 1px dashed $border;
    border-radius: 10px; padding: 30px; }
QStatusBar { background: $surface; color: $muted; border-top: 1px solid $border; }
""")


def make_icon(name, color, shape):
    """Draws a small icon into a PNG file, because style sheets can only show pictures from files."""
    path = Path(tempfile.gettempdir()) / f"reposcope_{name}_{color.lstrip('#')}.png"
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    points = {"check": [(5, 12.5), (10, 17.5), (19, 7)], "down": [(5, 9), (12, 16), (19, 9)],
              "up": [(5, 16), (12, 9), (19, 16)]}[shape]
    painter.drawPolyline([QPointF(x, y) for x, y in points])
    painter.end()
    pixmap.save(str(path))
    return path.as_posix()


def build_stylesheet():
    return STYLESHEET.substitute(
        tokens,
        check_icon=make_icon("check", "#ffffff", "check"),
        down_icon=make_icon("down", tokens["muted"], "down"),
        up_icon=make_icon("up", tokens["muted"], "up"),
    )


def apply_theme(app, name="light"):
    """Switch the whole application to the "light" or "dark" theme."""
    global current_name
    current_name = name
    tokens.clear()
    tokens.update(THEMES[name])
    app.setStyle("Fusion")
    if hasattr(app.styleHints(), "setColorScheme"):
        # Also makes the native window title bar match on Windows.
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark if name == "dark" else Qt.ColorScheme.Light)
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: "bg", QPalette.ColorRole.WindowText: "text", QPalette.ColorRole.Base: "input_bg",
        QPalette.ColorRole.AlternateBase: "surface_alt", QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "surface", QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.ToolTipBase: "surface", QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.PlaceholderText: "disabled_text", QPalette.ColorRole.Highlight: "accent",
    }
    for role, key in roles.items():
        palette.setColor(role, QColor(tokens[key]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(build_stylesheet())


def system_theme_name(app):
    """"dark" when Windows (or the OS) is in dark mode. Call before apply_theme."""
    hints = app.styleHints()
    if hasattr(hints, "colorScheme") and hints.colorScheme() == Qt.ColorScheme.Dark:
        return "dark"
    return "light"
