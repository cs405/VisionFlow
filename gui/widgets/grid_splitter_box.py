"""GridSplitterBox — WPF H.Controls.GridSplitterBox 1:1 port.

Collapsible side-panel container with:
  - Mode="Extend": panel resizes between min/max width (never hidden)
  - Drag handle on the trailing edge for user resize
  - Pin toggle button at bottom (WPF FontIconToggleButton)
  - Width-threshold signal at 90px (expand view ↔ icon bar)

Wired as the left-panel container in MainWindow, replacing manual QSplitter
manipulation. Width-threshold switching remains inside ToolboxPanel (reacts
to resizeEvent when GridSplitterBox changes its width).
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from gui.font_icons import FontIcons, FontIconToggleButton


MENU_MAX_WIDTH = 300
MENU_MIN_WIDTH = 50        # narrow mode compact width (WPF default: 50)
WIDTH_THRESHOLD = 90       # switch between wide/narrow at 90px
DEFAULT_WIDTH = 280

BORDER_BRUSH = "#3f3f46"
BACKGROUND = "#252526"


class GridSplitterBox(QWidget):
    """Left panel wrapper with WPF Mode=\"Extend\" expand/collapse behaviour.

    WPF equivalent: <h:GridSplitterBox Mode=\"Extend\" IsExpanded=\"False\"
                       ToggleVerticalAlignment=\"Bottom\">

    The pin toggle button at the bottom matches WPF's FontIconToggleButton
    with OpenGeometry (Pinned) / CloseGeometry (List) glyphs.

    Signals:
        width_changed(int): emitted when the panel width changes
        threshold_crossed(bool): True when entering wide mode (>90px), False for narrow
        expand_toggled(bool): True when expanded, False when collapsed
    """

    width_changed = pyqtSignal(int)
    threshold_crossed = pyqtSignal(bool)   # True = wide mode (>90px)
    expand_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._menu_width = DEFAULT_WIDTH
        self._is_expanded = True
        self._is_wide = True
        self._saved_width = DEFAULT_WIDTH

        self.setMinimumWidth(MENU_MIN_WIDTH)
        self.setMaximumWidth(MENU_MAX_WIDTH)
        self.setFixedWidth(DEFAULT_WIDTH)

        # ── Layout: [content + toggle btn] + drag handle ──
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Content area (vertical: content widget | toggle button)
        self._content_area = QWidget()
        self._content_area.setStyleSheet(f"background: {BACKGROUND};")
        content_vl = QVBoxLayout(self._content_area)
        content_vl.setContentsMargins(0, 0, 0, 0)
        content_vl.setSpacing(0)

        # Content slot
        self._content_host = QWidget()
        self._content_host.setStyleSheet("background: transparent;")
        self._host_layout = QVBoxLayout(self._content_host)
        self._host_layout.setContentsMargins(0, 0, 0, 0)
        self._host_layout.setSpacing(0)
        content_vl.addWidget(self._content_host, 1)

        # Pin toggle button at bottom (WPF FontIconToggleButton)
        # Expanded → Pin icon (pinned), Collapsed → GlobalNavButton (list/menu)
        self._toggle_btn = FontIconToggleButton(
            checked_icon=FontIcons.Pin,
            unchecked_icon=FontIcons.GlobalNavButton,
            font_size=14,
        )
        self._toggle_btn.setChecked(True)  # initially expanded
        self._toggle_btn.setToolTip("锁定面板 / 收起面板")
        self._toggle_btn.setFixedHeight(26)
        self._toggle_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            "border-top: 1px solid #3f3f46; color: #888; padding: 3px 0; }"
            "QPushButton:hover { background: #3e3e42; color: #dcdcdc; }"
            "QPushButton:checked { color: #dcdcdc; }"
        )
        self._toggle_btn.toggled.connect(self._on_toggle_btn)
        content_vl.addWidget(self._toggle_btn)

        main_layout.addWidget(self._content_area, 1)

        # Drag handle on right edge (matching WPF GridSplitter)
        self._handle = QFrame()
        self._handle.setFrameShape(QFrame.VLine)
        self._handle.setStyleSheet(f"background: {BORDER_BRUSH}; border: none;")
        self._handle.setFixedWidth(3)
        self._handle.setCursor(Qt.SplitHCursor)
        main_layout.addWidget(self._handle)

        # ── Resize debounce ──
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(50)
        self._resize_timer.timeout.connect(self._check_threshold)

        self._drag_start_x = 0
        self._drag_start_width = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def set_content(self, widget: QWidget):
        """Set the main content widget displayed inside this container."""
        while self._host_layout.count():
            item = self._host_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._host_layout.addWidget(widget)

    def set_menu_width(self, width: int):
        """Programmatically set panel width (clamped to min/max)."""
        width = max(MENU_MIN_WIDTH, min(MENU_MAX_WIDTH, width))
        self._menu_width = width
        self.setFixedWidth(width)
        self.width_changed.emit(width)
        if width > WIDTH_THRESHOLD:
            self._saved_width = width
        self._check_threshold()

    def menu_width(self) -> int:
        return self._menu_width

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @property
    def is_wide(self) -> bool:
        """True when current width > 90px (wide mode)."""
        return self._is_wide

    def toggle_expand(self):
        """Toggle between expanded (saved width) and collapsed (min width)."""
        if self._is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        """Expand to saved width (Mode=Extend)."""
        if not self._is_expanded:
            self._is_expanded = True
            w = self._saved_width if self._saved_width > WIDTH_THRESHOLD else DEFAULT_WIDTH
            self.set_menu_width(w)
            self._sync_toggle_btn()
            self.expand_toggled.emit(True)

    def collapse(self):
        """Collapse to minimum width (Mode=Extend)."""
        if self._is_expanded:
            self._saved_width = self._menu_width
            self._is_expanded = False
            self.set_menu_width(MENU_MIN_WIDTH)
            self._sync_toggle_btn()
            self.expand_toggled.emit(False)

    # ── Pin toggle button ────────────────────────────────────────────────────

    def _on_toggle_btn(self, checked: bool):
        """WPF FontIconToggleButton click → toggle expand/collapse."""
        if checked and not self._is_expanded:
            self.expand()
        elif not checked and self._is_expanded:
            self.collapse()

    def _sync_toggle_btn(self):
        """Sync toggle button checked state with panel expand state."""
        self._toggle_btn.blockSignals(True)
        self._toggle_btn.setChecked(self._is_expanded)
        self._toggle_btn.blockSignals(False)

    # ── Drag-to-resize ──────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if self._handle.underMouse() or self._in_handle_zone(event.pos()):
            self._drag_start_x = event.globalX()
            self._drag_start_width = self.width()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, '_drag_start_x') and self._drag_start_x:
            delta = event.globalX() - self._drag_start_x
            new_w = max(MENU_MIN_WIDTH, min(MENU_MAX_WIDTH,
                         self._drag_start_width + delta))
            self.set_menu_width(new_w)
            if new_w > WIDTH_THRESHOLD and not self._is_expanded:
                self._is_expanded = True
                self._sync_toggle_btn()
                self.expand_toggled.emit(True)
            elif new_w <= WIDTH_THRESHOLD and self._is_expanded:
                self._is_expanded = False
                self._sync_toggle_btn()
                self.expand_toggled.emit(False)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if hasattr(self, '_drag_start_x') and self._drag_start_x:
            self._drag_start_x = 0
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _in_handle_zone(self, pos) -> bool:
        """Check if pos is within 6px of the right edge (drag zone)."""
        return self.width() - pos.x() <= 6

    def enterEvent(self, event):
        if self._in_handle_zone(event.pos()):
            self.setCursor(Qt.SplitHCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)

    # ── Width threshold ─────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._menu_width = self.width()
        self.width_changed.emit(self._menu_width)
        self._resize_timer.start()

    def _check_threshold(self):
        """Check width against 90px threshold and emit signal on change."""
        was_wide = self._is_wide
        self._is_wide = self._menu_width > WIDTH_THRESHOLD
        if self._is_wide != was_wide:
            self.threshold_crossed.emit(self._is_wide)
        if self._is_wide and self._menu_width > MENU_MIN_WIDTH:
            self._saved_width = self._menu_width
