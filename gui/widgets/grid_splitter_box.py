"""GridSplitterBox — WPF H.Controls.GridSplitterBox 1:1 port.

Wraps left-side panel content with:
  - Width-threshold dual-mode switching (90px boundary)
  - Mode="Extend": panel slides out / collapses
  - Wide mode (>90px): GroupBox "流程资源" + tree/grid toggle
  - Narrow mode (≤90px): compact icon-only vertical list
  - Splitter handle on the right edge for resize

Ported from WPF MainWindow.xaml lines 209-260.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                              QFrame, QStackedWidget, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QTimer
from PyQt5.QtGui import QColor


# ── Constants matching WPF ─────────────────────────────────────────────────

MENU_MAX_WIDTH = 300
MENU_MIN_WIDTH = 24       # narrow mode compact width
WIDTH_THRESHOLD = 90       # switch between wide/narrow at 90px

# WPF Brushes equivalents
BORDER_BRUSH = "#3f3f46"
BORDER_BRUSH_TITLE = "#3f3f46"
BACKGROUND = "#252526"
HEADER_BG = "#2d2d30"


class GridSplitterBox(QWidget):
    """Left panel wrapper with width-threshold dual-mode switching.

    Emulates WPF GridSplitterBox:
      - Mode="Extend" with IsExpanded toggle
      - Width monitoring with 90px threshold
      - Two content slots: wide_content (GroupBox area) and narrow_content (compact list)

    Signals:
        width_changed(int): emitted when the panel width changes
        threshold_crossed(bool): True when entering wide mode, False for narrow
        expand_toggled(bool): True when expanded, False when collapsed
    """

    width_changed = pyqtSignal(int)
    threshold_crossed = pyqtSignal(bool)   # True = wide mode (>90px)
    expand_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._menu_width = 280
        self._is_expanded = True
        self._is_wide = True    # True = >90px
        self._mode = "Extend"   # Extend mode (slides out)

        self.setMinimumWidth(MENU_MIN_WIDTH)
        self.setMaximumWidth(MENU_MAX_WIDTH)

        # ── Layout ──
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content area (left part)
        self._content_area = QWidget()
        self._content_area.setStyleSheet(f"background: {BACKGROUND};")
        content_layout = QVBoxLayout(self._content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Stacked widget: switches between wide and narrow views
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {BACKGROUND};")

        # Slot 0: Wide mode (full panel)
        self._wide_widget = QWidget()
        self._wide_layout = QVBoxLayout(self._wide_widget)
        self._wide_layout.setContentsMargins(0, 0, 0, 0)
        self._wide_layout.setSpacing(0)
        self._stack.addWidget(self._wide_widget)

        # Slot 1: Narrow mode (compact)
        self._narrow_widget = QWidget()
        self._narrow_layout = QVBoxLayout(self._narrow_widget)
        self._narrow_layout.setContentsMargins(0, 0, 0, 0)
        self._narrow_layout.setSpacing(0)
        self._stack.addWidget(self._narrow_widget)

        content_layout.addWidget(self._stack, 1)
        main_layout.addWidget(self._content_area, 1)

        # Splitter handle on right edge (1px drag handle, matches WPF)
        self._handle = QFrame()
        self._handle.setFrameShape(QFrame.VLine)
        self._handle.setStyleSheet(
            f"background: {BORDER_BRUSH}; border: none;"
        )
        self._handle.setFixedWidth(2)
        self._handle.setCursor(Qt.SplitHCursor)
        main_layout.addWidget(self._handle)

        self._stack.setCurrentIndex(0)

        # ── Resize monitoring ──
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(50)
        self._resize_timer.timeout.connect(self._check_threshold)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_wide_content(self, widget: QWidget):
        """Set the widget displayed in wide mode (>90px)."""
        # Clear old content
        while self._wide_layout.count():
            item = self._wide_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._wide_layout.addWidget(widget)

    def set_narrow_content(self, widget: QWidget):
        """Set the widget displayed in narrow mode (≤90px)."""
        while self._narrow_layout.count():
            item = self._narrow_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._narrow_layout.addWidget(widget)

    def set_menu_width(self, width: int):
        """Programmatically set the panel width."""
        width = max(MENU_MIN_WIDTH, min(MENU_MAX_WIDTH, width))
        self._menu_width = width
        self.setFixedWidth(width)
        self.width_changed.emit(width)
        self._check_threshold()

    def menu_width(self) -> int:
        """Get current menu width."""
        return self._menu_width

    def toggle_expand(self):
        """Toggle between expanded and collapsed (Mode=Extend)."""
        if self._is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        """Expand the panel to its saved width."""
        if not self._is_expanded:
            self._is_expanded = True
            saved = max(MENU_MIN_WIDTH + 20, self._menu_width)
            self.set_menu_width(saved if saved > WIDTH_THRESHOLD else 280)
            self.expand_toggled.emit(True)

    def collapse(self):
        """Collapse the panel to minimum width."""
        if self._is_expanded:
            self._is_expanded = False
            self.set_menu_width(MENU_MIN_WIDTH)
            self.expand_toggled.emit(False)

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @property
    def is_wide(self) -> bool:
        """True when current width > 90px (wide mode)."""
        return self._is_wide

    # ── Internal ─────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._menu_width = self.width()
        self.width_changed.emit(self._menu_width)
        self._resize_timer.start()   # debounce

    def _check_threshold(self):
        """Check width against 90px threshold and switch modes."""
        was_wide = self._is_wide
        self._is_wide = self._menu_width > WIDTH_THRESHOLD

        if self._is_wide != was_wide:
            self.threshold_crossed.emit(self._is_wide)
            self._stack.setCurrentIndex(0 if self._is_wide else 1)
            # Force layout update
            self._stack.updateGeometry()

    # ── Splitter integration ─────────────────────────────────────────────────

    def install_on_splitter(self, splitter: QSplitter, index: int = 0):
        """Install this GridSplitterBox as a widget in a QSplitter.

        Hooks into the splitter's resize events to sync width changes
        and provides the drag handle behavior.
        """
        splitter.splitterMoved.connect(self._on_splitter_moved)
        self._parent_splitter = splitter

    def _on_splitter_moved(self, pos: int, index: int):
        """Sync internal state when parent splitter handle moves."""
        self._menu_width = self.width()
        self.width_changed.emit(self._menu_width)
        self._resize_timer.start()
