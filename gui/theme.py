"""Theme system - ported from H.Themes.Colors (Dark/Technology Blue).

Provides consistent color palettes, stylesheet management, and theme switching.
"""

from enum import Enum

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt


class ThemeType(Enum):
    DARK = "dark"
    LIGHT = "light"
    TECHNOLOGY_BLUE_DARK = "technology_blue_dark"


# Brand colors - matching VisionMaster visual identity
BRAND_COLORS = {
    "accent": "#0078d4",       # Blue accent (matches WPF status bar)
    "accent_hover": "#1a8ad4",
    "accent_pressed": "#005a9e",
    "success": "#4caf50",
    "warning": "#ff9800",
    "error": "#f44336",
    "info": "#2196f3",
    "fatal": "#d32f2f",
    "orange": "#FF8C00",       # Link/port color (from OpenCVFlowablePortData)
}


class ThemeColors:
    """Color tokens for the application."""

    def __init__(self):
        # Window chrome
        self.window_bg = QColor(45, 45, 48)
        self.title_bar_bg = QColor(30, 30, 30)
        self.title_bar_text = QColor(220, 220, 220)

        # Surfaces
        self.surface = QColor(37, 37, 38)
        self.surface_raised = QColor(52, 52, 55)
        self.surface_hover = QColor(62, 62, 66)

        # Text
        self.text_primary = QColor(220, 220, 220)
        self.text_secondary = QColor(153, 153, 153)
        self.text_disabled = QColor(100, 100, 100)

        # Borders
        self.border = QColor(63, 63, 70)
        self.border_focus = QColor(0, 120, 212)
        self.border_title = QColor(0, 122, 204)  # Blue title border

        # Accent
        self.accent = QColor("#0078d4")
        self.accent_text = QColor(255, 255, 255)

        # Node colors (by group)
        self.node_src = QColor("#4a9eff")        # Blue - source nodes
        self.node_preprocess = QColor("#ff8c00")  # Orange
        self.node_blur = QColor("#9c27b0")        # Purple
        self.node_morph = QColor("#00bcd4")       # Cyan
        self.node_detect = QColor("#f44336")      # Red
        self.node_match = QColor("#4caf50")       # Green
        self.node_output = QColor("#607d8b")      # Blue gray
        self.node_network = QColor("#795548")      # Brown
        self.node_onnx = QColor("#e91e63")         # Pink

        # Status
        self.status_ok = QColor("#4caf50")
        self.status_error = QColor("#f44336")
        self.status_running = QColor("#2196f3")
        self.status_idle = QColor("#999999")

        # Port colors
        self.port_input = QColor("#FFFFFF")
        self.port_output = QColor("#FF8C00")

        # Link color
        self.link = QColor("#FF8C00")

        # Grid
        self.grid_major = QColor(60, 60, 60)
        self.grid_minor = QColor(50, 50, 50)

        # Canvas
        self.canvas_bg = QColor(30, 30, 30)

    def to_palette(self) -> QPalette:
        """Convert to QPalette."""
        p = QPalette()
        p.setColor(QPalette.Window, self.surface)
        p.setColor(QPalette.WindowText, self.text_primary)
        p.setColor(QPalette.Base, QColor(30, 30, 30))
        p.setColor(QPalette.AlternateBase, self.surface)
        p.setColor(QPalette.ToolTipBase, QColor(60, 60, 60))
        p.setColor(QPalette.ToolTipText, self.text_primary)
        p.setColor(QPalette.Text, self.text_primary)
        p.setColor(QPalette.Button, self.surface)
        p.setColor(QPalette.ButtonText, self.text_primary)
        p.setColor(QPalette.BrightText, Qt.red)
        p.setColor(QPalette.Link, QColor(42, 130, 218))
        p.setColor(QPalette.Highlight, QColor(0, 120, 212))
        p.setColor(QPalette.HighlightedText, Qt.white)
        p.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
        p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
        return p


class ThemeManager:
    """Manages the current theme and notifies on changes."""

    def __init__(self):
        self._theme = ThemeType.DARK
        self.colors = ThemeColors()

    @property
    def theme(self) -> ThemeType:
        return self._theme

    @theme.setter
    def theme(self, value: ThemeType):
        self._theme = value
        self._apply_theme()

    def _apply_theme(self):
        """Apply the current theme to the app."""
        self.colors = ThemeColors()  # Could load different themes here

    def get_stylesheet(self) -> str:
        """Get the application-wide stylesheet."""
        return """
            QToolTip {
                color: #dcdcdc;
                background-color: #3c3c3c;
                border: 1px solid #505050;
                padding: 4px;
            }
            QDockWidget {
                color: #dcdcdc;
                titlebar-close-icon: none;
            }
            QDockWidget::title {
                background: #2d2d30;
                padding: 6px 10px;
                text-align: left;
            }
            QMenuBar {
                background: #2d2d30;
                color: #dcdcdc;
                padding: 1px;
            }
            QMenuBar::item {
                padding: 4px 12px;
                background: transparent;
            }
            QMenuBar::item:selected {
                background: #3e3e42;
            }
            QMenu {
                background: #2d2d30;
                color: #dcdcdc;
                border: 1px solid #505050;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 30px 6px 20px;
            }
            QMenu::item:selected {
                background: #0078d4;
            }
            QMenu::separator {
                height: 1px;
                background: #505050;
                margin: 4px 10px;
            }
            QStatusBar {
                background: #007acc;
                color: white;
                padding: 0;
            }
            QStatusBar::item {
                border: none;
            }
            QToolBar {
                background: #2d2d30;
                border: none;
                padding: 2px;
                spacing: 2px;
            }
            QToolBar::separator {
                width: 1px;
                margin: 4px 4px;
                background: #505050;
            }
            QToolButton {
                background: transparent;
                color: #dcdcdc;
                border: none;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QToolButton:hover {
                background: #3e3e42;
            }
            QToolButton:pressed {
                background: #0078d4;
            }
            QScrollBar:vertical {
                background: #1e1e1e;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #505050;
                min-height: 20px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #686868;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: #1e1e1e;
                height: 10px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #505050;
                min-width: 20px;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #686868;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0;
            }
            QTreeWidget {
                background: #252526;
                color: #dcdcdc;
                border: none;
                outline: none;
            }
            QTreeWidget::item {
                padding: 3px 4px;
            }
            QTreeWidget::item:hover {
                background: #2a2d2e;
            }
            QTreeWidget::item:selected {
                background: #094771;
            }
            QSplitter::handle {
                background: #505050;
            }
            QSplitter::handle:horizontal {
                width: 2px;
            }
            QSplitter::handle:vertical {
                height: 2px;
            }
            QTabWidget::pane {
                border: 1px solid #3f3f46;
                background: #252526;
            }
            QTabBar::tab {
                background: #2d2d30;
                color: #dcdcdc;
                padding: 8px 16px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                background: #252526;
                border-bottom: 2px solid #0078d4;
            }
            QTabBar::tab:hover {
                background: #3e3e42;
            }
            QGroupBox {
                color: #dcdcdc;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }
            QTableView, QTableWidget {
                background: #252526;
                color: #dcdcdc;
                border: 1px solid #3f3f46;
                gridline-color: #3f3f46;
                selection-background-color: #094771;
            }
            QHeaderView::section {
                background: #2d2d30;
                color: #dcdcdc;
                padding: 4px 8px;
                border: none;
                border-right: 1px solid #3f3f46;
                border-bottom: 1px solid #3f3f46;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background: #333337;
                color: #dcdcdc;
                border: 1px solid #3f3f46;
                padding: 4px 8px;
                border-radius: 3px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #0078d4;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #2d2d30;
                color: #dcdcdc;
                selection-background-color: #0078d4;
            }
            QCheckBox {
                color: #dcdcdc;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QPushButton {
                background: #0078d4;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background: #1a8ad4;
            }
            QPushButton:pressed {
                background: #005a9e;
            }
            QPushButton:disabled {
                background: #505050;
                color: #888;
            }
            QLabel {
                color: #dcdcdc;
            }
        """


# Global instance
theme_manager = ThemeManager()
