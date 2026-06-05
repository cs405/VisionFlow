"""Toolbox panel — WPF GridSplitterBox + GroupBox "流程资源" 1:1 port.

Aligns with WPF MainWindow.xaml left-side panel:
  - GridSplitterBox wrapper (Mode=Extend, IsExpanded=False)
  - Width-threshold dual-mode at 90px:
    - Wide (>90px): GroupBox "流程资源" with tree/grid toggle + search + favorites
    - Narrow (≤90px): compact vertical icon-only list
  - ToggleButton (AlignLeft ⇄ CaretBottomRightSolidCenter8) switches tree/grid
  - Favorites via QSettings persistence
  - Search filtering
  - Recent nodes tracking
  - Drag-to-canvas support in both grid and tree modes
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QScrollArea, QFrame, QGridLayout,
                              QTreeWidget, QTreeWidgetItem, QPushButton,
                              QApplication, QLayout)
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, QSettings, QMimeData, QPoint, QRect, QSize
from PyQt5.QtGui import QDrag, QColor

from core.node_group import node_data_group_manager
from gui.font_icons import FontIcons, FontIconToggleButton, ICON_FONT_FAMILY
from gui.widgets.grid_splitter_box import GridSplitterBox, WIDTH_THRESHOLD
from core.constants import get_group_meta as _group_meta


# ── Node tile button (grid view) ───────────────────────────────────────────

class _NodeTileButton(QFrame):
    """Tiled node button for grid view. Drag source + click/double-click."""

    activated = pyqtSignal(str)
    selected = pyqtSignal(str)
    favorite_toggled = pyqtSignal(str)

    def __init__(self, type_name: str, display_name: str, description: str,
                 group_name: str, is_favorite: bool = False, parent=None):
        super().__init__(parent)
        self.type_name = type_name
        self.is_favorite = is_favorite
        self._selected = False
        self._drag_start_pos = QPoint()
        self._drag_started = False

        meta = _group_meta(group_name)
        self._color = meta["color"]
        self._icon_text = meta["icon"]

        self.setCursor(Qt.OpenHandCursor)
        self.setFixedSize(105, 52)
        self.setFrameShape(QFrame.NoFrame)
        self._build_ui(display_name, description)
        self._refresh_style()

    def _build_ui(self, display_name: str, description: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 5, 6, 5)
        layout.setSpacing(2)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        icon = QLabel(self._icon_text)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(24, 24)
        icon.setStyleSheet(
            f"color: {self._color}; font-size: 16px; font-weight: bold;"
            f"font-family: '{ICON_FONT_FAMILY}';"
            "background: transparent; border: none;"
        )
        top.addWidget(icon)
        top.addStretch()

        fav = QLabel(FontIcons.FavoriteStar if self.is_favorite else "")
        fav.setStyleSheet("color: #d7ba7d; font-size: 11px; font-weight: bold;")
        top.addWidget(fav)
        layout.addLayout(top)

        title = QLabel(display_name)
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title.setStyleSheet("color: #1e1e1e; font-size: 10px; font-weight: 600;")
        title.setToolTip(description)
        layout.addWidget(title, 1)

        self.setToolTip(f"{display_name}\n{description}\n类型: {self.type_name}")

    def set_selected(self, selected: bool):
        self._selected = selected
        self._refresh_style()

    def _refresh_style(self):
        border = "#0078d4" if self._selected else ("#d7ba7d" if self.is_favorite else "#d0d0d0")
        bg = "#e8f0fe" if self._selected else "#ffffff"
        self.setStyleSheet(
            f"_NodeTileButton {{ background: {bg}; border: 1px solid {border}; border-radius: 4px; }}"
            f"_NodeTileButton:hover {{ background: #f0f0f0; border-color: #0078d4; }}"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_started = False
            self.selected.emit(self.type_name)
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self._drag_started = True
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.type_name)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self.rect().center())
        drag.exec_(Qt.CopyAction)
        self.setCursor(Qt.OpenHandCursor)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        if event.button() == Qt.LeftButton and not self._drag_started:
            self.selected.emit(self.type_name)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.type_name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


# ── Narrow mode: group icon buttons + popup (WPF ContextMenuPresenter) ──────

# Track currently-active narrow popup for mutual exclusion
_active_popup_button = None


class _DraggableCard(QPushButton):
    """Popup node card with click-select and drag-to-canvas (WPF StyleNodeDataBase)."""

    def __init__(self, type_name: str, display_name: str, color: str, icon: str, parent=None):
        super().__init__(parent)
        self._type_name = type_name
        self._drag_start_pos = QPoint()
        self._drag_started = False

        self.setFixedSize(105, 52)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"{display_name}\n类型: {type_name}")
        self.setStyleSheet(
            "QPushButton {"
            "background: white; border: 1px solid #d0d0d0; border-radius: 4px;"
            "color: #1e1e1e; font-size: 11px; font-weight: 600;"
            "}"
            "QPushButton:hover {"
            "background: #f0f0f0; border-color: #0078d4;"
            "}"
        )

        inner = QVBoxLayout(self)
        inner.setContentsMargins(4, 4, 4, 4)
        inner.setSpacing(2)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f"color: {color}; font-size: 16px; font-weight: bold;"
            f"font-family: '{ICON_FONT_FAMILY}';"
            "background: transparent; border: none;"
        )
        inner.addWidget(icon_lbl)

        text_lbl = QLabel(display_name)
        text_lbl.setAlignment(Qt.AlignCenter)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet(
            "color: #1e1e1e; font-size: 10px; background: transparent; border: none;"
        )
        inner.addWidget(text_lbl)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_started = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.pos() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self._drag_started = True
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self._type_name)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self.rect().center())
        drag.exec_(Qt.CopyAction)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and not self._drag_started:
            self.clicked.emit()  # triggers the connected slot
        super().mouseReleaseEvent(event)


class _NarrowGroupPopup(QFrame):
    """Popup matching WPF ContextMenu + GroupBox with CaptionRightTemplate.

    WPF structure:
      GroupBox Header=\"{Binding Name}\" (name left)
        CaptionRightTemplate → icon (right)
        UniformGrid Columns=\"2\" → node items
    """

    node_type_selected = pyqtSignal(str)

    def __init__(self, group_name: str, icon: str, color: str, metas: list[dict], parent=None):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(
            "_NarrowGroupPopup { background: #2d2d30; border: 1px solid #555; border-radius: 6px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: group name (left) + icon (right) — WPF CaptionRightTemplate
        header = QWidget()
        header.setStyleSheet("background: #353538; border-radius: 6px 6px 0 0;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 6, 8, 6)
        hl.setSpacing(4)

        name_lbl = QLabel(group_name)
        name_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        hl.addWidget(name_lbl, 1)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: bold;"
            f"font-family: '{ICON_FONT_FAMILY}';"
            "background: transparent; border: none;"
        )
        hl.addWidget(icon_lbl)

        layout.addWidget(header)

        # 2-column grid — WPF UniformGrid Columns="2"
        body = QWidget()
        body.setStyleSheet("background: #2d2d30; border-radius: 0 0 6px 6px;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(8, 8, 8, 8)
        bl.setSpacing(6)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)

        for i, m in enumerate(metas):
            row, col = divmod(i, 2)
            grid.addWidget(self._make_node_card(m), row, col)

        bl.addWidget(grid_widget)
        layout.addWidget(body)
        self.adjustSize()

    def _make_node_card(self, m: dict) -> QPushButton:
        """WPF StyleNodeDataBase card: white bg, icon + text stacked, drag-to-canvas."""
        btn = _DraggableCard(m["type_name"], m["display_name"], m["color"], m["icon"])
        btn.clicked.connect(lambda checked, tn=m["type_name"]: self._on_node_clicked(tn))
        return btn

    def _on_node_clicked(self, type_name: str):
        self.node_type_selected.emit(type_name)
        self.close()


class _NarrowGroupButton(QPushButton):
    """Group-icon button for narrow mode — 1:1 WPF FontIconToggleButton.

    WPF: <FontIconToggleButton Margin=\"0,5\" FontSize=\"25\"
             UncheckedGlyph=\"{Binding Icon}\" />

    No border, no background — just the icon glyph at large font size.
    Mutual exclusion: only one button's popup is open at a time.
    """

    node_type_selected = pyqtSignal(str)

    def __init__(self, group_name: str, icon: str, color: str, metas: list[dict], parent=None):
        super().__init__(parent)
        self._group_name = group_name
        self._icon = icon
        self._color = color
        self._metas = metas
        self._popup = None

        self.setText(icon)
        self.setToolTip(group_name)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"_NarrowGroupButton {{"
            f"background: transparent; border: none;"
            f"color: {color}; font-size: 25px;"
            f"font-family: '{ICON_FONT_FAMILY}';"
            f"padding: 2px 0;"
            f"}}"
            f"_NarrowGroupButton:hover {{ color: #dcdcdc; }}"
            f"_NarrowGroupButton:checked {{ color: #0078d4; }}"
        )
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool):
        if checked:
            self._show_popup()
        else:
            self._hide_popup()

    def _show_popup(self):
        global _active_popup_button
        # Close previously-active popup (mutual exclusion)
        if _active_popup_button and _active_popup_button is not self:
            _active_popup_button.setChecked(False)
        _active_popup_button = self

        self._hide_popup()
        gmeta = _group_meta(self._group_name)
        icon = gmeta.get("icon", self._icon)
        self._popup = _NarrowGroupPopup(self._group_name, icon, self._color, self._metas)
        self._popup.node_type_selected.connect(self._on_node_selected)
        self._popup.installEventFilter(self)
        pos = self.mapToGlobal(QPoint(self.width() + 4, 0))
        self._popup.move(pos)
        self._popup.show()

    def _hide_popup(self):
        global _active_popup_button
        if _active_popup_button is self:
            _active_popup_button = None
        if self._popup:
            self._popup.removeEventFilter(self)
            self._popup.close()
            self._popup.deleteLater()
            self._popup = None

    def _on_node_selected(self, type_name: str):
        self.node_type_selected.emit(type_name)
        self.setChecked(False)

    def eventFilter(self, obj, event):
        if obj is self._popup and event.type() == QEvent.Hide:
            self.setChecked(False)
        return super().eventFilter(obj, event)


# ── Flow layout (WPF WrapPanel port) ────────────────────────────────────────

class FlowLayout(QLayout):
    """Horizontal flow layout — items wrap to next row (WPF WrapPanel)."""

    def __init__(self, parent=None, margin=0, h_spacing=8, v_spacing=8):
        super().__init__(parent)
        self._items: list[QLayout] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, dry_run=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for item in self._items:
            s = s.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, dry_run: bool) -> int:
        m = self.contentsMargins()
        x = rect.x() + m.left()
        y = rect.y() + m.top()
        line_h = 0
        right = rect.right() - m.right()

        for item in self._items:
            hint = item.sizeHint()
            space_x = self._h_spacing if x > rect.x() + m.left() else 0
            if x + space_x + hint.width() > right and line_h > 0:
                x = rect.x() + m.left()
                y += line_h + self._v_spacing
                line_h = 0
                space_x = 0
            if not dry_run:
                item.setGeometry(QRect(QPoint(x + space_x, y), hint))
            x += space_x + hint.width()
            line_h = max(line_h, hint.height())

        return y + line_h - rect.y() + m.bottom()


# ── Collapsible group section (WPF Expander port) ────────────────────────────

class _CollapsibleGroup(QWidget):
    """Collapsible group panel matching WPF Expander.

    Header: expand arrow + icon + group name, clickable.
    Body: FlowLayout of _NodeTileButton, hidden when collapsed.
    WPF default: IsExpanded=\"False\".
    """

    def __init__(self, group_name: str, icon: str, color: str,
                 metas: list[dict], expanded: bool = False, parent=None):
        super().__init__(parent)
        self._expanded = expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header (clickable toggle) — WPF Expander with CaptionRightTemplate ──
        self._header = QPushButton()
        self._header.setFlat(True)
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setStyleSheet(
            "QPushButton { background: #2d2d30; border: none;"
            "border-bottom: 1px solid #3f3f46; padding: 5px 6px; text-align: left; }"
            "QPushButton:hover { background: #353538; }"
        )
        self._header.clicked.connect(self._toggle)

        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)

        self._arrow = QLabel("▾" if self._expanded else "▸")
        self._arrow.setFixedWidth(14)
        self._arrow.setStyleSheet(
            "color: #999; font-size: 10px; background: transparent; border: none;"
        )
        hl.addWidget(self._arrow)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            f"color: {color}; font-size: 14px; font-weight: bold;"
            f"font-family: '{ICON_FONT_FAMILY}';"
            "background: transparent; border: none;"
        )
        hl.addWidget(icon_lbl)

        name_lbl = QLabel(group_name)
        name_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; font-weight: bold;"
            "background: transparent; border: none;"
        )
        hl.addWidget(name_lbl, 1)

        count_lbl = QLabel(str(len(metas)))
        count_lbl.setStyleSheet(
            "color: #888; font-size: 10px; background: transparent; border: none;"
        )
        hl.addWidget(count_lbl)

        layout.addWidget(self._header)

        # ── Body (collapsible, FlowLayout) ──
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._body_layout = FlowLayout(self._body, margin=6, h_spacing=6, v_spacing=6)
        self._body.setVisible(self._expanded)
        layout.addWidget(self._body)

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._arrow.setText("▾" if self._expanded else "▸")

    def flow_layout(self) -> FlowLayout:
        return self._body_layout


# ── Draggable tree widget ──────────────────────────────────────────────────

class _DraggableTreeWidget(QTreeWidget):
    """QTreeWidget with proper drag mime data for node type names."""

    def mimeData(self, items):
        mime = super().mimeData(items)
        if items:
            type_name = items[0].data(0, Qt.UserRole)
            if type_name:
                mime.setText(type_name)
        return mime


# ═══════════════════════════════════════════════════════════════════════════
# Main ToolboxPanel
# ═══════════════════════════════════════════════════════════════════════════

class ToolboxPanel(QWidget):
    """WPF-aligned left panel: GridSplitterBox wrapper with wide/narrow modes.

    Public API (backward-compatible with existing MainWindow usage):
      - node_type_selected signal
      - refresh()
      - set_view_mode(tree: bool)
    """

    node_type_selected = pyqtSignal(str)
    favorites_changed = pyqtSignal()

    FAVORITES_KEY = "Toolbox/Favorites"
    RECENTS_KEY = "Toolbox/Recents"
    VIEW_MODE_KEY = "Toolbox/ViewMode"
    MAX_RECENTS = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._favorites: list[str] = []
        self._recents: list[str] = []
        self._selected_type: str | None = None
        self._tile_widgets: dict[str, _NodeTileButton] = {}
        self._view_is_tree = False

        self._load_persisted()
        self._setup_ui()
        self.refresh()

    # ── Persistence ────────────────────────────────────────────────────

    def _load_persisted(self):
        s = QSettings()
        favs = s.value(self.FAVORITES_KEY, [])
        if isinstance(favs, str):
            favs = [favs] if favs else []
        self._favorites = list(favs) if favs else []

        recs = s.value(self.RECENTS_KEY, [])
        if isinstance(recs, str):
            recs = [recs] if recs else []
        self._recents = list(recs) if recs else []

        tree_mode = s.value(self.VIEW_MODE_KEY, "false")
        self._view_is_tree = str(tree_mode).lower() == "true"

    def _save_favorites(self):
        s = QSettings()
        s.setValue(self.FAVORITES_KEY, self._favorites)
        s.sync()
        self.favorites_changed.emit()

    def _save_recents(self):
        s = QSettings()
        s.setValue(self.RECENTS_KEY, self._recents[:self.MAX_RECENTS])
        s.sync()

    def _save_view_mode(self):
        s = QSettings()
        s.setValue(self.VIEW_MODE_KEY, "true" if self._view_is_tree else "false")
        s.sync()

    def is_favorite(self, type_name: str) -> bool:
        return type_name in self._favorites

    def add_favorite(self, type_name: str):
        if type_name and type_name not in self._favorites:
            self._favorites.append(type_name)
            self._save_favorites()
            self.refresh()

    def remove_favorite(self, type_name: str):
        if type_name in self._favorites:
            self._favorites.remove(type_name)
            self._save_favorites()
            self.refresh()

    def toggle_favorite(self, type_name: str):
        if self.is_favorite(type_name):
            self.remove_favorite(type_name)
        else:
            self.add_favorite(type_name)

    def record_use(self, type_name: str):
        if type_name in self._recents:
            self._recents.remove(type_name)
        self._recents.insert(0, type_name)
        self._recents = self._recents[:self.MAX_RECENTS]
        self._save_recents()

    # ── UI setup ───────────────────────────────────────────────────────

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header: "流程资源" + tree/grid toggle (hidden in narrow mode) ──
        self._header = QWidget()
        self._header.setFixedHeight(32)
        self._header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        h_layout = QHBoxLayout(self._header)
        h_layout.setContentsMargins(8, 0, 2, 0)
        h_layout.setSpacing(2)

        title = QLabel("流程资源")
        title.setStyleSheet("color: #dcdcdc; font-size: 12px; font-weight: bold; background: transparent; border: none;")
        h_layout.addWidget(title, 1)

        # Toggle: AlignLeft (tree) ⇄ CaretBottomRightSolidCenter8 (grid)
        self._view_toggle = FontIconToggleButton(
            checked_icon=FontIcons.AlignLeft,
            unchecked_icon=FontIcons.CaretBottomRightSolidCenter8,
            font_size=12,
        )
        self._view_toggle.setChecked(self._view_is_tree)
        self._view_toggle.setToolTip("树形 / 网格切换")
        self._view_toggle.setFixedSize(26, 24)
        self._view_toggle.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #999; padding: 2px; }"
            "QPushButton:hover { background: #3e3e42; color: #dcdcdc; }"
            "QPushButton:checked { color: #dcdcdc; }"
        )
        self._view_toggle.toggled.connect(self._on_view_toggled)
        h_layout.addWidget(self._view_toggle)
        main_layout.addWidget(self._header)

        # ── Search bar ──
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索模块 / 中文名称...")
        self._search_box.setStyleSheet(
            "QLineEdit { background: #333337; color: #dcdcdc; border: none;"
            "border-bottom: 1px solid #3f3f46; padding: 6px 8px; font-size: 12px; }"
            "QLineEdit:focus { border-bottom: 1px solid #0078d4; }"
        )
        self._search_box.textChanged.connect(lambda: self.refresh())
        main_layout.addWidget(self._search_box)

        # ── Stacked views: tree | grid | narrow ──
        self._view_frame = QFrame()
        self._view_frame.setFrameShape(QFrame.NoFrame)
        vf_layout = QVBoxLayout(self._view_frame)
        vf_layout.setContentsMargins(0, 0, 0, 0)
        vf_layout.setSpacing(0)

        # Tree view
        self._tree = self._create_tree()
        vf_layout.addWidget(self._tree)

        # Grid view
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        self._grid_scroll.setStyleSheet("QScrollArea { background: #252526; border: none; }")
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._grid_content = QWidget()
        self._grid_layout = QVBoxLayout(self._grid_content)
        self._grid_layout.setContentsMargins(8, 8, 8, 8)
        self._grid_layout.setSpacing(10)
        self._grid_scroll.setWidget(self._grid_content)
        vf_layout.addWidget(self._grid_scroll)

        # Narrow mode (compact vertical icon list — WPF ContextMenu presenter)
        self._narrow_widget = QWidget()
        self._narrow_layout = QVBoxLayout(self._narrow_widget)
        self._narrow_layout.setContentsMargins(0, 20, 0, 0)
        self._narrow_layout.setSpacing(5)
        self._narrow_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        vf_layout.addWidget(self._narrow_widget)

        self._tree.hide()
        self._grid_scroll.show()
        self._narrow_widget.hide()
        main_layout.addWidget(self._view_frame, 1)

    # ── Tree view ─────────────────────────────────────────────────────

    def _create_tree(self) -> QTreeWidget:
        tree = _DraggableTreeWidget()
        tree.setHeaderLabels(["模块名称", "描述"])
        tree.setColumnWidth(0, 140)
        tree.setIndentation(16)
        tree.setRootIsDecorated(True)
        tree.setAnimated(True)
        tree.setExpandsOnDoubleClick(True)
        tree.setStyleSheet("""
            QTreeWidget {
                background: #252526; color: #dcdcdc; border: none; font-size: 11px;
            }
            QTreeWidget::item { padding: 3px 4px; border: none; }
            QTreeWidget::item:hover { background: #2d2d30; }
            QTreeWidget::item:selected { background: #094771; }
            QTreeWidget::branch { background: transparent; }
            QHeaderView::section {
                background: #2d2d30; color: #999; padding: 4px 8px;
                border: none; border-bottom: 1px solid #3f3f46; font-size: 11px;
            }
        """)
        tree.setDragEnabled(True)
        tree.itemClicked.connect(self._on_tree_item_clicked)
        tree.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        return tree

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, col: int):
        type_name = item.data(0, Qt.UserRole)
        if type_name:
            self._set_selected_type(type_name)
            self.node_type_selected.emit(type_name)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        type_name = item.data(0, Qt.UserRole)
        if type_name:
            self.node_type_selected.emit(type_name)

    # ── View toggle ──────────────────────────────────────────────────

    def _on_view_toggled(self, checked: bool):
        self._view_is_tree = checked
        self._save_view_mode()
        self._apply_view()

    def set_view_mode(self, tree: bool):
        """Programmatically switch between tree (True) and grid (False)."""
        if self._view_toggle.isChecked() != tree:
            self._view_toggle.setChecked(tree)

    def _apply_view(self):
        """Show the correct view based on width + toggle state.

        WPF DataTrigger: MenuWidth < 90 → hide GroupBox, show icon bar.
        """
        w = self.width()
        if w <= WIDTH_THRESHOLD:
            # Narrow: hide header + search, show only group icon bar (WPF ContextMenu)
            self._header.hide()
            self._search_box.hide()
            self._tree.hide()
            self._grid_scroll.hide()
            self._narrow_widget.show()
        elif self._view_is_tree:
            self._header.show()
            self._search_box.show()
            self._tree.show()
            self._grid_scroll.hide()
            self._narrow_widget.hide()
        else:
            self._header.show()
            self._search_box.show()
            self._tree.hide()
            self._grid_scroll.show()
            self._narrow_widget.hide()

    def resizeEvent(self, event):
        """React to width changes — switch between wide and narrow modes."""
        super().resizeEvent(event)
        self._apply_view()
        if event.oldSize().width() != event.size().width():
            self.refresh()

    # ── Data building ────────────────────────────────────────────────

    def _all_node_metas(self) -> list[dict]:
        keyword = self._search_box.text().strip().lower()
        result = []
        for group in node_data_group_manager.get_all_groups():
            for node_type in group.node_types:
                type_name = node_type.__name__
                display_name = type_name
                try:
                    instance = node_type()
                    candidate = getattr(instance, 'display_name', '') or getattr(instance, 'name', '')
                    if isinstance(candidate, str) and candidate.strip():
                        display_name = candidate.strip()
                except Exception:
                    pass

                doc = (node_type.__doc__ or '').strip().splitlines()
                description = doc[0] if doc else display_name

                if keyword and keyword not in f"{display_name} {description} {type_name} {group.name}".lower():
                    continue

                meta = _group_meta(group.name)
                result.append({
                    "type_name": type_name,
                    "display_name": display_name,
                    "description": description,
                    "group_name": group.name,
                    "color": meta["color"],
                    "icon": meta["icon"],
                    "is_favorite": self.is_favorite(type_name),
                })
        return result

    # ── Refresh ──────────────────────────────────────────────────────

    def refresh(self):
        """Rebuild the active view."""
        w = self.width()
        if w <= WIDTH_THRESHOLD:
            self._refresh_narrow()
        elif self._view_is_tree:
            self._refresh_tree()
        else:
            self._refresh_grid()

    def _refresh_tree(self):
        self._tree.clear()
        metas = self._all_node_metas()
        grouped: dict[str, list[dict]] = {}
        for m in metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # Recents
        recents = [m for m in metas if m["type_name"] in self._recents]
        if recents:
            recents.sort(key=lambda m: self._recents.index(m["type_name"]))
            p = self._add_tree_group("🕐 最近使用", "#d7ba7d")
            for m in recents:
                self._add_tree_node(p, m)

        # Favorites
        favs = [m for m in metas if m["is_favorite"]]
        if favs:
            p = self._add_tree_group("★ 收藏", "#d7ba7d")
            for m in favs:
                self._add_tree_node(p, m)

        for grp in node_data_group_manager.get_all_groups():
            items = grouped.get(grp.name, [])
            if not items:
                continue
            p = self._add_tree_group(grp.name, _group_meta(grp.name)["color"])
            for m in items:
                self._add_tree_node(p, m)

        self._tree.expandAll()

    def _add_tree_group(self, name: str, color: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(self._tree)
        item.setText(0, name)
        item.setForeground(0, QColor(color))
        font = item.font(0); font.setBold(True); item.setFont(0, font)
        item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled)
        return item

    def _add_tree_node(self, parent: QTreeWidgetItem, meta: dict):
        item = QTreeWidgetItem(parent)
        item.setText(0, meta["display_name"])
        item.setText(1, meta["description"])
        item.setData(0, Qt.UserRole, meta["type_name"])
        item.setToolTip(0, f"{meta['display_name']}\n{meta['description']}")
        item.setForeground(0, QColor(meta["color"]))
        return item

    def _refresh_grid(self):
        while self._grid_layout.count():
            w = self._grid_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()
        self._tile_widgets.clear()

        metas = self._all_node_metas()
        grouped: dict[str, list[dict]] = {}
        for m in metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # Recents
        recents = [m for m in metas if m["type_name"] in self._recents]
        if recents:
            recents.sort(key=lambda m: self._recents.index(m["type_name"]))
            self._build_grid_group("🕐 最近使用", recents)

        # Favorites
        favs = [m for m in metas if m["is_favorite"]]
        if favs:
            self._build_grid_group("★ 收藏", favs)

        for grp in node_data_group_manager.get_all_groups():
            items = grouped.get(grp.name, [])
            if not items:
                continue
            self._build_grid_group(grp.name, items)

        self._grid_layout.addStretch(1)

    def _build_grid_group(self, group_name: str, metas: list[dict]) -> int:
        """Build a collapsible group section (WPF Expander + WrapPanel)."""
        if not metas:
            return 0
        meta = _group_meta(group_name)
        section = _CollapsibleGroup(group_name, meta["icon"], meta["color"], metas)

        for m in metas:
            tile = _NodeTileButton(m["type_name"], m["display_name"], m["description"],
                                    m["group_name"], m["is_favorite"])
            tile.activated.connect(self.node_type_selected.emit)
            # single click also adds to canvas (WPF behaviour)
            tile.selected.connect(self.node_type_selected.emit)
            tile.favorite_toggled.connect(self.toggle_favorite)
            self._tile_widgets[m["type_name"]] = tile
            if m["type_name"] == self._selected_type:
                tile.set_selected(True)
            section.flow_layout().addWidget(tile)

        self._grid_layout.addWidget(section)
        return len(metas)

    def _refresh_narrow(self):
        """Build compact group-icon list (WPF ContextMenuPresenter).

        One button per node group. Clicking a group icon opens a popup
        showing that group's nodes in a 2-column grid.
        """
        while self._narrow_layout.count():
            w = self._narrow_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        metas = self._all_node_metas()
        grouped: dict[str, list[dict]] = {}
        for m in metas:
            grouped.setdefault(m["group_name"], []).append(m)

        for grp in node_data_group_manager.get_all_groups():
            items = grouped.get(grp.name, [])
            if not items:
                continue
            gmeta = _group_meta(grp.name)
            btn = _NarrowGroupButton(grp.name, gmeta["icon"], gmeta["color"], items)
            btn.node_type_selected.connect(self.node_type_selected.emit)
            self._narrow_layout.addWidget(btn)

        self._narrow_layout.addStretch(1)

    def _set_selected_type(self, type_name: str):
        self._selected_type = type_name
        for current, tile in self._tile_widgets.items():
            tile.set_selected(current == type_name)

    # ── Public API ──────────────────────────────────────────────────

    def get_selected_node_type(self) -> str | None:
        return self._selected_type
