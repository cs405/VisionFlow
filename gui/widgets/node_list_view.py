"""Node list view — WPF 流程资源 panel 1:1 port.

Compound widget matching WPF MainWindow.xaml GroupBox "流程资源" + dual-view pattern:

Wide mode (>90px):
  ┌─────────────────────────────┐
  │ 流程资源            [≡|⊞]  │  ← header + FontIconToggleButton (tree/grid)
  ├─────────────────────────────┤
  │ 🔍 搜索模块...              │  ← search bar
  ├─────────────────────────────┤
  │ ★ 收藏                     │  ← favorites section
  │   [icon] [icon] ...         │
  │ 图像数据源                  │  ← groups
  │   [icon] [icon] ...         │
  │ ...                         │
  ├─────────────────────────────┤
  │  5 个分组 · 32 个节点 ★ 3  │  ← stats footer
  └─────────────────────────────┘

Narrow mode (≤90px):
  ┌────┐
  │ S  │  ← compact vertical icon-only list
  │ P  │     with tooltip on hover
  │ B  │
  │ M  │
  │ ...│
  └────┘

Tree view: QTreeWidget with groups → nodes, Name + Description columns
Grid view: QScrollArea + QGridLayout tiled icon buttons (existing ToolboxPanel pattern)
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QScrollArea, QFrame, QGridLayout,
                              QTreeWidget, QTreeWidgetItem, QPushButton,
                              QSizePolicy, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QMimeData, QPoint, QSize
from PyQt5.QtGui import QDrag, QFont, QColor, QIcon, QPainter, QPixmap

from core.node_group import node_data_group_manager, NodeGroup
from core.node_base import NodeBase
from gui.font_icons import FontIcons, FontIconTextBlock, FontIconToggleButton, icon_font


# ── Group metadata matching WPF colors ─────────────────────────────────────

GROUP_META = {
    "图像数据源":   {"color": "#4a9eff", "icon": FontIcons.Photo2},
    "系统数据源":   {"color": "#5c6bc0", "icon": FontIcons.Folder},
    "图像预处理模块": {"color": "#ff8c00", "icon": FontIcons.Color},
    "滤波模块":     {"color": "#9c27b0", "icon": FontIcons.Filter},
    "图像分割提取模块": {"color": "#e91e63", "icon": FontIcons.Cut},
    "形态学模块":   {"color": "#00bcd4", "icon": "⬒"},
    "逻辑模块":     {"color": "#ff5722", "icon": "⇄"},
    "模板匹配模块": {"color": "#4caf50", "icon": "⌖"},
    "对象识别模块": {"color": "#f44336", "icon": "◉"},
    "特征提取模块": {"color": "#ff9800", "icon": "✣"},
    "网络通讯模块": {"color": "#795548", "icon": "⌁"},
    "结果输出模块": {"color": "#607d8b", "icon": "↗"},
    "Onnx通用模型": {"color": "#c2185b", "icon": "AI"},
    "其他模块":     {"color": "#607d8b", "icon": "◇"},
    "视频处理模块": {"color": "#8d6e63", "icon": FontIcons.Video},
    "★ 收藏":      {"color": "#d7ba7d", "icon": FontIcons.FavoriteStar},
}


def _group_meta(group_name: str):
    return GROUP_META.get(group_name, {"color": "#607d8b", "icon": "🧩"})


# ── Node tile (grid view) ──────────────────────────────────────────────────

class NodeTileButton(QFrame):
    """Tiled node button for the grid view — drag source + click to add."""

    activated = pyqtSignal(str)
    selected = pyqtSignal(str)
    favorite_toggled = pyqtSignal(str)

    TILE_W = 108
    TILE_H = 78

    def __init__(self, type_name: str, display_name: str, description: str,
                 group_name: str, is_favorite: bool = False, parent=None):
        super().__init__(parent)
        self.type_name = type_name
        self.display_name = display_name
        self.description = description
        self.group_name = group_name
        self.is_favorite = is_favorite
        self._selected = False
        self._drag_start_pos = QPoint()
        self._drag_started = False

        meta = _group_meta(group_name)
        self._color = meta["color"]
        self._icon_text = meta["icon"]

        self.setCursor(Qt.OpenHandCursor)
        self.setFixedSize(self.TILE_W, self.TILE_H)
        self.setFrameShape(QFrame.NoFrame)
        self._build_ui()
        self._refresh_style()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        # Icon badge
        icon_badge = QLabel(self._icon_text)
        icon_badge.setAlignment(Qt.AlignCenter)
        icon_badge.setFixedSize(28, 28)
        icon_badge.setStyleSheet(
            f"background: {self._color}; border-radius: 6px; color: white;"
            "font-size: 14px; font-weight: 700;"
            "font-family: 'Segoe UI Symbol', 'Microsoft YaHei UI';"
        )
        top.addWidget(icon_badge)
        top.addStretch()

        # Star
        fav = QLabel(FontIcons.FavoriteStar if self.is_favorite else "")
        fav.setStyleSheet("color: #d7ba7d; font-size: 12px; font-weight: bold;")
        top.addWidget(fav)
        layout.addLayout(top)

        # Title
        title = QLabel(self.display_name)
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        title.setStyleSheet("color: #dcdcdc; font-size: 11px; font-weight: 600;")
        title.setToolTip(self.description)
        layout.addWidget(title, 1)

        self.setToolTip(f"{self.display_name}\n{self.description}\n类型: {self.type_name}")

    def set_selected(self, selected: bool):
        self._selected = selected
        self._refresh_style()

    def _refresh_style(self):
        border = "#0078d4" if self._selected else ("#d7ba7d" if self.is_favorite else "#3f3f46")
        bg = "#2f3640" if self._selected else "#252526"
        self.setStyleSheet(
            f"NodeTileButton {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
            f"NodeTileButton:hover {{ background: #2d2d30; border-color: #0078d4; }}"
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
        self._start_drag()
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

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.type_name)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self.rect().center())
        drag.exec_(Qt.CopyAction)


# ── Compact narrow-mode tile ───────────────────────────────────────────────

class NarrowNodeButton(QPushButton):
    """Compact icon-only button for the narrow mode (≤90px) vertical list."""

    activated = pyqtSignal(str)

    def __init__(self, type_name: str, display_name: str, group_name: str,
                 parent=None):
        super().__init__(parent)
        self.type_name = type_name
        self.display_name = display_name
        meta = _group_meta(group_name)
        self._color = meta["color"]
        self._icon = meta["icon"]

        self.setText(self._icon)
        self.setToolTip(f"{display_name}\n{group_name}")
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet(
            f"NarrowNodeButton {{ background: transparent; border: 1px solid #3f3f46;"
            f"border-radius: 4px; color: {self._color}; font-size: 14px; font-weight: bold;"
            f"font-family: 'Segoe UI Symbol', 'Microsoft YaHei UI'; }}"
            f"NarrowNodeButton:hover {{ background: #3e3e42; border-color: #0078d4; }}"
        )
        self.clicked.connect(lambda: self.activated.emit(self.type_name))


# ═══════════════════════════════════════════════════════════════════════════
# Main compound widget
# ═══════════════════════════════════════════════════════════════════════════

class NodeListView(QWidget):
    """Full node list with header, search, tree/grid toggle, and narrow mode.

    This is the content that goes inside GridSplitterBox.  It handles both
    wide (>90px) and narrow (≤90px) layouts internally via stacked views.

    Signals:
        node_type_selected(str): when user selects a node type
        node_type_activated(str): when user double-clicks / confirms
    """

    node_type_selected = pyqtSignal(str)
    node_type_activated = pyqtSignal(str)
    favorites_changed = pyqtSignal()

    FAVORITES_KEY = "Toolbox/Favorites"
    RECENTS_KEY = "Toolbox/Recents"
    FAVORITES_GROUP_NAME = "★ 收藏"
    RECENTS_GROUP_NAME = "🕐 最近使用"
    MAX_RECENTS = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._favorites: list[str] = []
        self._recents: list[str] = []
        self._selected_type: str | None = None
        self._tile_widgets: dict[str, NodeTileButton] = {}
        self._narrow_buttons: dict[str, NarrowNodeButton] = {}
        self._view_is_tree = False  # False = grid (default)

        self._load_persisted_lists()
        self._setup_ui()
        self.refresh()

    # ── Persistence ─────────────────────────────────────────────────────

    def _load_persisted_lists(self):
        s = QSettings()
        favs = s.value(self.FAVORITES_KEY, [])
        if isinstance(favs, str):
            favs = [favs] if favs else []
        self._favorites = list(favs) if favs else []

        recs = s.value(self.RECENTS_KEY, [])
        if isinstance(recs, str):
            recs = [recs] if recs else []
        self._recents = list(recs) if recs else []

    def _save_favorites(self):
        s = QSettings()
        s.setValue(self.FAVORITES_KEY, self._favorites)
        s.sync()
        self.favorites_changed.emit()

    def _save_recents(self):
        s = QSettings()
        s.setValue(self.RECENTS_KEY, self._recents[:self.MAX_RECENTS])
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
        """Record node type usage (for recent list)."""
        if type_name in self._recents:
            self._recents.remove(type_name)
        self._recents.insert(0, type_name)
        self._recents = self._recents[:self.MAX_RECENTS]
        self._save_recents()

    # ── UI Setup ────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header bar: "流程资源" + tree/grid toggle on right ──
        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 2, 0)
        h_layout.setSpacing(2)

        title = QLabel("流程资源")
        title.setStyleSheet("color: #dcdcdc; font-size: 12px; font-weight: bold; background: transparent;")
        h_layout.addWidget(title, 1)

        # Toggle: tree (AlignLeft) / grid (CaretBottomRightSolidCenter8)
        self._view_toggle = FontIconToggleButton(
            checked_icon=FontIcons.AlignLeft,
            unchecked_icon=FontIcons.CaretBottomRightSolidCenter8,
            font_size=12,
        )
        self._view_toggle.setChecked(False)   # default: grid view
        self._view_toggle.setToolTip("切换树/网格视图")
        self._view_toggle.setFixedSize(26, 24)
        self._view_toggle.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #999; padding: 2px; }"
            "QPushButton:hover { background: #3e3e42; color: #dcdcdc; }"
            "QPushButton:checked { color: #dcdcdc; }"
        )
        self._view_toggle.toggled.connect(self._on_view_toggled)
        h_layout.addWidget(self._view_toggle)
        layout.addWidget(header)

        # ── Search bar ──
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("搜索模块 / 中文名称...")
        self._search_box.setStyleSheet(
            "QLineEdit { background: #333337; color: #dcdcdc; border: none;"
            "border-bottom: 1px solid #3f3f46; padding: 6px 8px; font-size: 12px; }"
            "QLineEdit:focus { border-bottom: 1px solid #0078d4; }"
        )
        self._search_box.textChanged.connect(lambda: self.refresh())
        layout.addWidget(self._search_box)

        # ── Stacked views: tree / grid ──
        self._view_stack = QFrame()
        self._view_stack.setFrameShape(QFrame.NoFrame)
        view_stack_layout = QVBoxLayout(self._view_stack)
        view_stack_layout.setContentsMargins(0, 0, 0, 0)
        view_stack_layout.setSpacing(0)

        # Tree view
        self._tree = self._create_tree_view()
        view_stack_layout.addWidget(self._tree)

        # Grid view
        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setFrameShape(QFrame.NoFrame)
        self._grid_scroll.setStyleSheet("QScrollArea { background: #252526; border: none; }")
        self._grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._grid_content = QWidget()
        self._grid_content_layout = QVBoxLayout(self._grid_content)
        self._grid_content_layout.setContentsMargins(8, 8, 8, 8)
        self._grid_content_layout.setSpacing(10)
        self._grid_scroll.setWidget(self._grid_content)
        view_stack_layout.addWidget(self._grid_scroll)

        # Default: grid visible
        self._tree.hide()
        self._grid_scroll.show()

        layout.addWidget(self._view_stack, 1)

        # ── Stats label (footer) ──
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet(
            "color: #666; font-size: 10px; padding: 3px 8px; background: #1e1e1e;"
            "border-top: 1px solid #3f3f46;"
        )
        layout.addWidget(self._stats_label)

    # ── Tree view ───────────────────────────────────────────────────────

    def _create_tree_view(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderLabels(["模块名称", "描述"])
        tree.setColumnWidth(0, 130)
        tree.setColumnWidth(1, 120)
        tree.setIndentation(16)
        tree.setRootIsDecorated(True)
        tree.setAnimated(True)
        tree.setExpandsOnDoubleClick(True)
        tree.setStyleSheet("""
            QTreeWidget {
                background: #252526; color: #dcdcdc; border: none;
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 3px 4px;
                border: none;
            }
            QTreeWidget::item:hover {
                background: #2d2d30;
            }
            QTreeWidget::item:selected {
                background: #094771;
            }
            QTreeWidget::branch {
                background: transparent;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
            }
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
            self.node_type_selected.emit(type_name)

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        type_name = item.data(0, Qt.UserRole)
        if type_name:
            self.node_type_activated.emit(type_name)

    # ── View toggle ────────────────────────────────────────────────────

    def _on_view_toggled(self, checked: bool):
        self._view_is_tree = checked
        self._tree.setVisible(checked)
        self._grid_scroll.setVisible(not checked)
        self.refresh()

    def set_view_mode(self, tree: bool):
        """Programmatically switch between tree (True) and grid (False)."""
        self._view_toggle.setChecked(tree)

    # ── Data building ──────────────────────────────────────────────────

    def _all_node_metas(self, keyword: str = "") -> list[dict]:
        """Collect all node type metadata, optionally filtered by keyword."""
        result = []
        type_registry = {}  # type_name -> NodeType

        for group in node_data_group_manager.get_all_groups():
            for node_type in group.node_types:
                type_name = node_type.__name__
                type_registry[type_name] = node_type

                # Resolve display name
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

                meta = _group_meta(group.name)
                result.append({
                    "type_name": type_name,
                    "display_name": display_name,
                    "description": description,
                    "group_name": group.name,
                    "color": meta["color"],
                    "icon": meta["icon"],
                    "is_favorite": self.is_favorite(type_name),
                    "is_recent": type_name in self._recents,
                })

        if keyword:
            kw = keyword.lower()
            result = [
                m for m in result
                if kw in f"{m['display_name']} {m['description']} {m['type_name']} {m['group_name']}".lower()
            ]

        return result

    # ── Refresh ────────────────────────────────────────────────────────

    def refresh(self):
        """Rebuild the active view (tree or grid)."""
        if self._view_is_tree:
            self._refresh_tree()
        else:
            self._refresh_grid()

    def _refresh_tree(self):
        """Populate the tree view."""
        self._tree.clear()
        keyword = self.search_keyword

        # Gather data
        all_metas = self._all_node_metas(keyword)
        grouped: dict[str, list[dict]] = {}
        for m in all_metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # Add special sections first
        if self._recents:
            recent_metas = [m for m in all_metas if m["type_name"] in self._recents]
            if recent_metas:
                recent_metas.sort(key=lambda m: self._recents.index(m["type_name"]))
                parent = self._add_tree_group(self._tree, self.RECENTS_GROUP_NAME, "#d7ba7d")
                for m in recent_metas:
                    self._add_tree_node(parent, m)

        if self._favorites:
            fav_metas = [m for m in all_metas if m["is_favorite"]]
            if fav_metas:
                parent = self._add_tree_group(self._tree, self.FAVORITES_GROUP_NAME, "#d7ba7d")
                for m in fav_metas:
                    self._add_tree_node(parent, m)

        # Standard groups in order
        for group in node_data_group_manager.get_all_groups():
            metas = grouped.get(group.name, [])
            if not metas:
                continue
            parent = self._add_tree_group(self._tree, group.name, _group_meta(group.name)["color"])
            for m in metas:
                self._add_tree_node(parent, m)

        self._tree.expandAll()
        self._update_stats(all_metas)

    def _add_tree_group(self, tree: QTreeWidget, name: str, color: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem(tree)
        item.setText(0, name)
        item.setForeground(0, QColor(color))
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled)
        return item

    def _add_tree_node(self, parent: QTreeWidgetItem, meta: dict):
        item = QTreeWidgetItem(parent)
        item.setText(0, meta["display_name"])
        item.setText(1, meta["description"])
        item.setData(0, Qt.UserRole, meta["type_name"])
        item.setToolTip(0, f"{meta['display_name']}\n{meta['description']}\n类型: {meta['type_name']}")
        item.setToolTip(1, meta["description"])
        # Icon in first column
        icon_label = QLabel(meta["icon"])
        # Color the icon via foreground
        item.setForeground(0, QColor(meta["color"]))
        return item

    def _refresh_grid(self):
        """Populate the grid view."""
        # Clear
        while self._grid_content_layout.count():
            item = self._grid_content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._tile_widgets.clear()

        keyword = self.search_keyword
        all_metas = self._all_node_metas(keyword)

        visible_groups = 0
        visible_nodes = 0

        # Recent section
        if self._recents:
            recent_metas = [m for m in all_metas if m["type_name"] in self._recents]
            if recent_metas:
                recent_metas.sort(key=lambda m: self._recents.index(m["type_name"]))
                count = self._build_grid_group(self.RECENTS_GROUP_NAME, recent_metas)
                visible_groups += 1
                visible_nodes += count

        # Favorites section
        if self._favorites:
            fav_metas = [m for m in all_metas if m["is_favorite"]]
            if fav_metas:
                count = self._build_grid_group(self.FAVORITES_GROUP_NAME, fav_metas)
                visible_groups += 1
                visible_nodes += count

        # Standard groups
        grouped: dict[str, list[dict]] = {}
        for m in all_metas:
            grouped.setdefault(m["group_name"], []).append(m)

        for group in node_data_group_manager.get_all_groups():
            metas = grouped.get(group.name, [])
            if not metas:
                continue
            count = self._build_grid_group(group.name, metas)
            visible_groups += 1
            visible_nodes += count

        self._grid_content_layout.addStretch(1)
        self._update_stats(all_metas, visible_groups, visible_nodes)

    def _build_grid_group(self, group_name: str, metas: list[dict]) -> int:
        """Build a grid group section. Returns count of visible nodes."""
        if not metas:
            return 0

        meta = _group_meta(group_name)
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        header = QLabel(f"{meta['icon']}  {group_name}")
        header.setStyleSheet(
            f"color: {meta['color']}; font-size: 12px; font-weight: bold; padding: 2px 2px;"
        )
        section_layout.addWidget(header)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for i, m in enumerate(metas):
            tile = NodeTileButton(
                type_name=m["type_name"],
                display_name=m["display_name"],
                description=m["description"],
                group_name=m["group_name"],
                is_favorite=m["is_favorite"],
            )
            tile.activated.connect(self._on_tile_activated)
            tile.selected.connect(self._set_selected_type)
            tile.favorite_toggled.connect(self.toggle_favorite)
            self._tile_widgets[m["type_name"]] = tile
            row, col = divmod(i, 2)
            grid.addWidget(tile, row, col)

            if m["type_name"] == self._selected_type:
                tile.set_selected(True)

        section_layout.addWidget(grid_host)
        self._grid_content_layout.addWidget(section)
        return len(metas)

    def _set_selected_type(self, type_name: str):
        self._selected_type = type_name
        for current, tile in self._tile_widgets.items():
            tile.set_selected(current == type_name)

    def _on_tile_activated(self, type_name: str):
        self.node_type_activated.emit(type_name)

    def _update_stats(self, metas: list[dict], groups: int = 0, nodes: int = 0):
        keyword = self.search_keyword
        if not groups:
            groups_set = set(m["group_name"] for m in metas)
            groups = len(groups_set)
            nodes = len(metas)
        parts = [f"  {groups} 个分组 · {nodes} 个节点"]
        if self._favorites:
            parts.append(f"★ 收藏 {len(self._favorites)} 个")
        if self._recents:
            parts.append(f"🕐 最近 {len(self._recents)} 个")
        self._stats_label.setText(" · ".join(parts))

    # ── Narrow mode ─────────────────────────────────────────────────────

    def create_narrow_widget(self) -> QWidget:
        """Create the compact narrow-mode vertical icon list (≤90px).

        Returns a QWidget suitable for GridSplitterBox.set_narrow_content().
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 12, 4, 4)
        layout.setSpacing(4)

        all_metas = self._all_node_metas()
        grouped: dict[str, list[dict]] = {}
        for m in all_metas:
            grouped.setdefault(m["group_name"], []).append(m)

        # Show favorites first, then groups
        if self._favorites:
            fav_metas = [m for m in all_metas if m["is_favorite"]]
            for m in fav_metas[:6]:  # limit in narrow mode
                btn = NarrowNodeButton(m["type_name"], m["display_name"], m["group_name"])
                btn.activated.connect(self.node_type_activated.emit)
                layout.addWidget(btn)
                self._narrow_buttons[m["type_name"]] = btn

        for group in node_data_group_manager.get_all_groups():
            metas = grouped.get(group.name, [])
            for m in metas[:3]:  # limit per group in narrow mode
                btn = NarrowNodeButton(m["type_name"], m["display_name"], m["group_name"])
                btn.activated.connect(self.node_type_activated.emit)
                layout.addWidget(btn)
                self._narrow_buttons[m["type_name"]] = btn

        layout.addStretch(1)
        return widget

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def search_keyword(self) -> str:
        return self._search_box.text().strip().lower()

    def get_selected_node_type(self) -> str | None:
        return self._selected_type
