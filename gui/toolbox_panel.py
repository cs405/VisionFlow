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
                              QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QMimeData, QPoint
from PyQt5.QtGui import QDrag, QColor

from core.node_group import node_data_group_manager
from gui.font_icons import FontIcons, FontIconToggleButton
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
        self.setFixedSize(108, 78)
        self.setFrameShape(QFrame.NoFrame)
        self._build_ui(display_name, description)
        self._refresh_style()

    def _build_ui(self, display_name: str, description: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        icon = QLabel(self._icon_text)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(28, 28)
        icon.setStyleSheet(
            f"background: {self._color}; border-radius: 6px; color: white;"
            "font-size: 14px; font-weight: 700;"
            "font-family: 'Segoe UI Symbol', 'Microsoft YaHei UI';"
        )
        top.addWidget(icon)
        top.addStretch()

        fav = QLabel(FontIcons.FavoriteStar if self.is_favorite else "")
        fav.setStyleSheet("color: #d7ba7d; font-size: 12px; font-weight: bold;")
        top.addWidget(fav)
        layout.addLayout(top)

        title = QLabel(display_name)
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title.setStyleSheet("color: #dcdcdc; font-size: 11px; font-weight: 600;")
        title.setToolTip(description)
        layout.addWidget(title, 1)

        self.setToolTip(f"{display_name}\n{description}\n类型: {self.type_name}")

    def set_selected(self, selected: bool):
        self._selected = selected
        self._refresh_style()

    def _refresh_style(self):
        border = "#0078d4" if self._selected else ("#d7ba7d" if self.is_favorite else "#3f3f46")
        bg = "#2f3640" if self._selected else "#252526"
        self.setStyleSheet(
            f"_NodeTileButton {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
            f"_NodeTileButton:hover {{ background: #2d2d30; border-color: #0078d4; }}"
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


# ── Narrow mode compact button ─────────────────────────────────────────────

class _NarrowNodeButton(QPushButton):
    """Compact icon-only button for narrow (≤90px) mode."""

    activated = pyqtSignal(str)

    def __init__(self, type_name: str, display_name: str, group_name: str, parent=None):
        super().__init__(parent)
        self.type_name = type_name
        meta = _group_meta(group_name)
        self.setText(meta["icon"])
        self.setToolTip(f"{display_name}\n{group_name}\n类型: {type_name}")
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"_NarrowNodeButton {{ background: transparent; border: 1px solid #3f3f46;"
            f"border-radius: 4px; color: {meta['color']}; font-size: 14px; font-weight: bold;"
            f"font-family: 'Segoe UI Symbol', 'Microsoft YaHei UI'; }}"
            f"_NarrowNodeButton:hover {{ background: #3e3e42; border-color: #0078d4; }}"
        )
        self.clicked.connect(lambda: self.activated.emit(self.type_name))


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

        # ── Header: "流程资源" + tree/grid toggle ──
        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        h_layout = QHBoxLayout(header)
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
        main_layout.addWidget(header)

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

        # Narrow mode (compact vertical icon list)
        self._narrow_widget = QWidget()
        self._narrow_layout = QVBoxLayout(self._narrow_widget)
        self._narrow_layout.setContentsMargins(4, 12, 4, 4)
        self._narrow_layout.setSpacing(4)
        vf_layout.addWidget(self._narrow_widget)

        self._tree.hide()
        self._grid_scroll.show()
        self._narrow_widget.hide()
        main_layout.addWidget(self._view_frame, 1)

        # ── Stats footer ──
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet(
            "color: #666; font-size: 10px; padding: 3px 8px; background: #1e1e1e;"
            "border-top: 1px solid #3f3f46;"
        )
        main_layout.addWidget(self._stats_label)

    # ── Tree view ─────────────────────────────────────────────────────

    def _create_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
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
        """Show the correct view based on width + toggle state."""
        w = self.width()
        if w <= WIDTH_THRESHOLD:
            self._tree.hide()
            self._grid_scroll.hide()
            self._narrow_widget.show()
        elif self._view_is_tree:
            self._tree.show()
            self._grid_scroll.hide()
            self._narrow_widget.hide()
        else:
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
        self._update_stats(metas)

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

        vg = 0; vn = 0

        # Recents
        recents = [m for m in metas if m["type_name"] in self._recents]
        if recents:
            recents.sort(key=lambda m: self._recents.index(m["type_name"]))
            c = self._build_grid_group("🕐 最近使用", recents)
            vg += 1; vn += c

        # Favorites
        favs = [m for m in metas if m["is_favorite"]]
        if favs:
            c = self._build_grid_group("★ 收藏", favs)
            vg += 1; vn += c

        for grp in node_data_group_manager.get_all_groups():
            items = grouped.get(grp.name, [])
            if not items:
                continue
            c = self._build_grid_group(grp.name, items)
            vg += 1; vn += c

        self._grid_layout.addStretch(1)
        self._update_stats(metas, vg, vn)

    def _build_grid_group(self, group_name: str, metas: list[dict]) -> int:
        if not metas:
            return 0
        meta = _group_meta(group_name)
        section = QWidget()
        sl = QVBoxLayout(section); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(6)
        hdr = QLabel(f"{meta['icon']}  {group_name}")
        hdr.setStyleSheet(f"color: {meta['color']}; font-size: 12px; font-weight: bold; padding: 2px 2px;")
        sl.addWidget(hdr)

        host = QWidget()
        grid = QGridLayout(host); grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8); grid.setVerticalSpacing(8)

        for i, m in enumerate(metas):
            tile = _NodeTileButton(m["type_name"], m["display_name"], m["description"],
                                    m["group_name"], m["is_favorite"])
            tile.activated.connect(self.node_type_selected.emit)
            tile.selected.connect(self._set_selected_type)
            tile.favorite_toggled.connect(self.toggle_favorite)
            self._tile_widgets[m["type_name"]] = tile
            row, col = divmod(i, 2)
            grid.addWidget(tile, row, col)
            if m["type_name"] == self._selected_type:
                tile.set_selected(True)

        sl.addWidget(host)
        self._grid_layout.addWidget(section)
        return len(metas)

    def _refresh_narrow(self):
        """Build compact vertical icon-only list for narrow mode."""
        while self._narrow_layout.count():
            w = self._narrow_layout.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        metas = self._all_node_metas()
        grouped: dict[str, list[dict]] = {}
        for m in metas:
            grouped.setdefault(m["group_name"], []).append(m)

        favs = [m for m in metas if m["is_favorite"]]
        for m in favs[:4]:
            btn = _NarrowNodeButton(m["type_name"], m["display_name"], m["group_name"])
            btn.activated.connect(self.node_type_selected.emit)
            self._narrow_layout.addWidget(btn)

        for grp in node_data_group_manager.get_all_groups():
            for m in grouped.get(grp.name, [])[:2]:
                btn = _NarrowNodeButton(m["type_name"], m["display_name"], m["group_name"])
                btn.activated.connect(self.node_type_selected.emit)
                self._narrow_layout.addWidget(btn)

        self._narrow_layout.addStretch(1)
        self._update_stats(metas)

    def _set_selected_type(self, type_name: str):
        self._selected_type = type_name
        for current, tile in self._tile_widgets.items():
            tile.set_selected(current == type_name)

    def _update_stats(self, metas: list[dict], groups: int = 0, nodes: int = 0):
        if not groups:
            groups = len(set(m["group_name"] for m in metas))
            nodes = len(metas)
        parts = [f"  {groups} 个分组 · {nodes} 个节点"]
        if self._favorites:
            parts.append(f"★ 收藏 {len(self._favorites)} 个")
        self._stats_label.setText(" · ".join(parts))

    # ── Public API ──────────────────────────────────────────────────

    def get_selected_node_type(self) -> str | None:
        return self._selected_type
