"""Theme system — WPF H.Themes 1:1 port.

Supports dark/light theme switching at runtime with signal notifications.
Ported from H.Themes.Colors + ISwitchThemeViewPresenter.
"""

from enum import Enum

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtCore import Qt, pyqtSignal, QObject


class ThemeType(Enum):
    DARK = "dark"
    LIGHT = "light"


# ═══════════════════════════════════════════════════════════════════════════
# Color tokens
# ═══════════════════════════════════════════════════════════════════════════

class ThemeColors:
    """Dark theme color tokens (WPF Dark / Technology Blue palette)."""

    def __init__(self):
        # Window chrome
        self.window_bg = QColor(45, 45, 48)
        self.title_bar_bg = QColor(30, 30, 30)
        self.title_bar_text = QColor(220, 220, 220)

        # Surfaces
        self.surface = QColor(37, 37, 38)      # #252526
        self.surface_raised = QColor(52, 52, 55)  # #343437
        self.surface_hover = QColor(62, 62, 66)   # #3e3e42
        self.surface_input = QColor(51, 51, 55)   # #333337
        self.surface_deep = QColor(30, 30, 30)    # #1e1e1e

        # Text
        self.text_primary = QColor(220, 220, 220)
        self.text_secondary = QColor(153, 153, 153)
        self.text_disabled = QColor(100, 100, 100)

        # Borders
        self.border = QColor(63, 63, 70)         # #3f3f46
        self.border_focus = QColor(0, 120, 212)   # #0078d4
        self.border_title = QColor(0, 122, 204)

        # Accent
        self.accent = QColor("#0078d4")
        self.accent_text = QColor(255, 255, 255)

        # Node group colors
        self.node_src = QColor("#4a9eff")
        self.node_preprocess = QColor("#ff8c00")
        self.node_blur = QColor("#9c27b0")
        self.node_morph = QColor("#00bcd4")
        self.node_detect = QColor("#f44336")
        self.node_match = QColor("#4caf50")
        self.node_output = QColor("#607d8b")
        self.node_network = QColor("#795548")
        self.node_onnx = QColor("#e91e63")

        # Status
        self.status_ok = QColor("#4caf50")
        self.status_error = QColor("#f44336")
        self.status_running = QColor("#2196f3")
        self.status_idle = QColor("#999999")

        # Port / Link
        self.port_input = QColor("#FFFFFF")
        self.port_output = QColor("#FF8C00")
        self.link = QColor("#FF8C00")
        self.link_selected = QColor("#FFA726")

        # Grid / Canvas (checkerboard matching WPF Dark0 / Dark0_1)
        self.checker_base = QColor("#121317")   # WPF Dark0
        self.checker_alt = QColor("#191a20")    # WPF Dark0_1
        self.canvas_bg = QColor("#121317")

        # Node body
        self.node_bg = QColor("#3c3c3c")
        self.node_bg_hover = QColor("#4a4a4a")
        self.node_bg_selected = QColor("#4a4a4a")
        self.node_border = QColor("#555555")
        self.node_border_selected = QColor("#FF8C00")
        self.node_text = QColor("#dcdcdc")
        self.node_flag_default = QColor("#888888")
        self.node_shadow = QColor(0, 0, 0, 60)

        # Scroll bar
        self.scroll_bg = QColor("#1e1e1e")
        self.scroll_handle = QColor("#505050")
        self.scroll_handle_hover = QColor("#686868")

    def to_palette(self) -> QPalette:
        p = QPalette()
        p.setColor(QPalette.Window, self.surface)
        p.setColor(QPalette.WindowText, self.text_primary)
        p.setColor(QPalette.Base, self.surface_deep)
        p.setColor(QPalette.AlternateBase, self.surface)
        p.setColor(QPalette.ToolTipBase, QColor(60, 60, 60))
        p.setColor(QPalette.ToolTipText, self.text_primary)
        p.setColor(QPalette.Text, self.text_primary)
        p.setColor(QPalette.Button, self.surface)
        p.setColor(QPalette.ButtonText, self.text_primary)
        p.setColor(QPalette.Link, self.accent)
        p.setColor(QPalette.Highlight, self.accent)
        p.setColor(QPalette.HighlightedText, self.accent_text)
        p.setColor(QPalette.Disabled, QPalette.Text, QColor(128, 128, 128))
        p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(128, 128, 128))
        return p

    @property
    def stylesheet(self) -> str:
        """Dark theme QSS."""
        return f"""
            QToolTip {{ color: {self.text_primary.name()}; background: #3c3c3c; border: 1px solid #505050; padding: 4px; }}
            QMenuBar {{ background: #2d2d30; color: {self.text_primary.name()}; }}
            QMenuBar::item:selected {{ background: #3e3e42; }}
            QMenu {{ background: #2d2d30; color: {self.text_primary.name()}; border: 1px solid #505050; }}
            QMenu::item:selected {{ background: {self.accent.name()}; }}
            QMenu::separator {{ height: 1px; background: #505050; margin: 4px 10px; }}
            QStatusBar {{ background: #007acc; color: white; }}
            QScrollBar:vertical {{ background: #1e1e1e; width: 10px; }}
            QScrollBar::handle:vertical {{ background: #505050; min-height: 20px; border-radius: 5px; }}
            QScrollBar::handle:vertical:hover {{ background: #686868; }}
            QScrollBar:horizontal {{ background: #1e1e1e; height: 10px; }}
            QScrollBar::handle:horizontal {{ background: #505050; min-width: 20px; border-radius: 5px; }}
            QScrollBar::handle:horizontal:hover {{ background: #686868; }}
            QTreeWidget {{ background: #252526; color: {self.text_primary.name()}; border: none; }}
            QTreeWidget::item:hover {{ background: #2a2d2e; }}
            QTreeWidget::item:selected {{ background: #094771; }}
            QSplitter::handle {{ background: #505050; }}
            QTabWidget::pane {{ border: 1px solid {self.border.name()}; background: #252526; }}
            QTabBar::tab {{ background: #2d2d30; color: {self.text_primary.name()}; padding: 6px 12px; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ background: #252526; border-bottom: 2px solid {self.accent.name()}; }}
            QTabBar::tab:hover {{ background: #3e3e42; }}
            QTableView, QTableWidget {{ background: #252526; color: {self.text_primary.name()}; border: 1px solid {self.border.name()}; gridline-color: {self.border.name()}; selection-background-color: #094771; }}
            QHeaderView::section {{ background: #2d2d30; color: {self.text_primary.name()}; padding: 4px 8px; border: none; border-right: 1px solid {self.border.name()}; border-bottom: 1px solid {self.border.name()}; }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: #333337; color: {self.text_primary.name()}; border: 1px solid {self.border.name()}; padding: 4px 8px; border-radius: 3px; }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {self.accent.name()}; }}
            QComboBox QAbstractItemView {{ background: #2d2d30; color: {self.text_primary.name()}; selection-background-color: {self.accent.name()}; }}
            QCheckBox {{ color: {self.text_primary.name()}; }}
            QPushButton {{ background: {self.accent.name()}; color: white; border: none; padding: 6px 16px; border-radius: 3px; }}
            QPushButton:hover {{ background: #1a8ad4; }}
            QPushButton:pressed {{ background: #005a9e; }}
            QPushButton:disabled {{ background: #505050; color: #888; }}
            QLabel {{ color: {self.text_primary.name()}; }}
        """


class ThemeColorsLight(ThemeColors):
    """Light theme (WPF White / Light Gray palette)."""

    def __init__(self):
        super().__init__()
        # Window chrome
        self.window_bg = QColor(245, 245, 245)
        self.title_bar_bg = QColor(255, 255, 255)
        self.title_bar_text = QColor(30, 30, 30)

        # Surfaces
        self.surface = QColor(255, 255, 255)      # white
        self.surface_raised = QColor(245, 245, 245)
        self.surface_hover = QColor(230, 230, 230)
        self.surface_input = QColor(255, 255, 255)
        self.surface_deep = QColor(240, 240, 240)

        # Text
        self.text_primary = QColor(30, 30, 30)
        self.text_secondary = QColor(100, 100, 100)
        self.text_disabled = QColor(170, 170, 170)

        # Borders
        self.border = QColor(220, 220, 220)
        self.border_focus = QColor(0, 120, 212)
        self.border_title = QColor(0, 122, 204)

        # Accent
        self.accent = QColor("#0078d4")
        self.accent_text = QColor(255, 255, 255)

        # Grid / Canvas (checkerboard matching WPF Dark0 / Dark0_1 in light theme)
        self.checker_base = QColor("#ffffff")   # WPF Dark0 (light)
        self.checker_alt = QColor("#fafafa")    # WPF Dark0_1 (light)
        self.canvas_bg = QColor("#ffffff")

        # Node body (WPF light theme: white bg, black text)
        self.node_bg = QColor("#FFFFFF")
        self.node_bg_hover = QColor("#F0F0F0")
        self.node_bg_selected = QColor("#F0F0F0")
        self.node_border = QColor("#CCCCCC")
        self.node_border_selected = QColor("#FF8C00")
        self.node_text = QColor("#1E1E1E")
        self.node_flag_default = QColor("#888888")
        self.node_shadow = QColor(0, 0, 0, 30)

        # Scroll
        self.scroll_bg = QColor("#F0F0F0")
        self.scroll_handle = QColor("#C0C0C0")
        self.scroll_handle_hover = QColor("#A0A0A0")

    def to_palette(self) -> QPalette:
        p = QPalette()
        p.setColor(QPalette.Window, self.surface)
        p.setColor(QPalette.WindowText, self.text_primary)
        p.setColor(QPalette.Base, self.surface)
        p.setColor(QPalette.AlternateBase, self.surface_raised)
        p.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        p.setColor(QPalette.ToolTipText, self.text_primary)
        p.setColor(QPalette.Text, self.text_primary)
        p.setColor(QPalette.Button, self.surface_raised)
        p.setColor(QPalette.ButtonText, self.text_primary)
        p.setColor(QPalette.Link, self.accent)
        p.setColor(QPalette.Highlight, self.accent)
        p.setColor(QPalette.HighlightedText, self.accent_text)
        p.setColor(QPalette.Disabled, QPalette.Text, QColor(170, 170, 170))
        p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(170, 170, 170))
        return p

    @property
    def stylesheet(self) -> str:
        """Light theme QSS."""
        return f"""
            QToolTip {{ color: #1e1e1e; background: #ffffff; border: 1px solid #ccc; padding: 4px; }}
            QMenuBar {{ background: #ffffff; color: #1e1e1e; }}
            QMenuBar::item:selected {{ background: #e0e0e0; }}
            QMenu {{ background: #ffffff; color: #1e1e1e; border: 1px solid #ccc; }}
            QMenu::item:selected {{ background: {self.accent.name()}; color: white; }}
            QMenu::separator {{ height: 1px; background: #e0e0e0; margin: 4px 10px; }}
            QStatusBar {{ background: #007acc; color: white; }}
            QScrollBar:vertical {{ background: #f0f0f0; width: 10px; }}
            QScrollBar::handle:vertical {{ background: #c0c0c0; min-height: 20px; border-radius: 5px; }}
            QScrollBar::handle:vertical:hover {{ background: #a0a0a0; }}
            QScrollBar:horizontal {{ background: #f0f0f0; height: 10px; }}
            QScrollBar::handle:horizontal {{ background: #c0c0c0; min-width: 20px; border-radius: 5px; }}
            QScrollBar::handle:horizontal:hover {{ background: #a0a0a0; }}
            QTreeWidget {{ background: #ffffff; color: #1e1e1e; border: none; }}
            QTreeWidget::item:hover {{ background: #f0f0f0; }}
            QTreeWidget::item:selected {{ background: {self.accent.name()}; color: white; }}
            QSplitter::handle {{ background: #ccc; }}
            QTabWidget::pane {{ border: 1px solid #e0e0e0; background: #ffffff; }}
            QTabBar::tab {{ background: #f5f5f5; color: #1e1e1e; padding: 6px 12px; border-bottom: 2px solid transparent; }}
            QTabBar::tab:selected {{ background: #ffffff; border-bottom: 2px solid {self.accent.name()}; }}
            QTabBar::tab:hover {{ background: #e8e8e8; }}
            QTableView, QTableWidget {{ background: #ffffff; color: #1e1e1e; border: 1px solid #e0e0e0; gridline-color: #e0e0e0; selection-background-color: {self.accent.name()}; }}
            QHeaderView::section {{ background: #f5f5f5; color: #1e1e1e; padding: 4px 8px; border: none; border-right: 1px solid #e0e0e0; border-bottom: 1px solid #e0e0e0; }}
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: #ffffff; color: #1e1e1e; border: 1px solid #ccc; padding: 4px 8px; border-radius: 3px; }}
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {self.accent.name()}; }}
            QComboBox QAbstractItemView {{ background: #ffffff; color: #1e1e1e; selection-background-color: {self.accent.name()}; }}
            QCheckBox {{ color: #1e1e1e; }}
            QPushButton {{ background: {self.accent.name()}; color: white; border: none; padding: 6px 16px; border-radius: 3px; }}
            QPushButton:hover {{ background: #1a8ad4; }}
            QPushButton:pressed {{ background: #005a9e; }}
            QPushButton:disabled {{ background: #ccc; color: #999; }}
            QLabel {{ color: #1e1e1e; }}
        """


# ═══════════════════════════════════════════════════════════════════════════
# Theme manager with signal
# ═══════════════════════════════════════════════════════════════════════════

class ThemeManager(QObject):
    """Manages current theme, notifies all widgets on change (WPF ThemeService)."""

    theme_changed = pyqtSignal(ThemeType)

    def __init__(self):
        super().__init__()
        self._theme = ThemeType.DARK
        self.colors = ThemeColors()

    @property
    def theme(self) -> ThemeType:
        return self._theme

    @theme.setter
    def theme(self, value: ThemeType):
        if value == self._theme:
            return
        self._theme = value
        self.colors = ThemeColorsLight() if value == ThemeType.LIGHT else ThemeColors()
        self.theme_changed.emit(value)

    def toggle(self):
        """Toggle between dark and light themes."""
        self.theme = ThemeType.LIGHT if self._theme == ThemeType.DARK else ThemeType.DARK

    def get_stylesheet(self) -> str:
        """Get the current theme's stylesheet."""
        return self.colors.stylesheet

    @property
    def is_dark(self) -> bool:
        return self._theme == ThemeType.DARK


# Global instance
theme_manager = ThemeManager()
