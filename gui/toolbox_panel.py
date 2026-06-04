"""Toolbox panel - tree/grid display of available nodes with favorites.

Ported from H.Controls.FavoriteBox + H.Controls.TreeListView.
Shows nodes grouped by category. Supports favorites, search, and context menu.
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                              QLineEdit, QHBoxLayout, QLabel, QApplication,
                              QMenu, QAction, QToolButton)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings
from PyQt5.QtGui import QFont, QColor, QIcon

from core.node_group import node_data_group_manager, NodeGroup
from core.registry import node_registry


# Group color indicators + Unicode icons (matching WPF node group colors)
GROUP_META = {
    "数据源":     {"color": "#4a9eff", "icon": "📷"},
    "图像预处理":  {"color": "#ff8c00", "icon": "⚙"},
    "滤波模糊":    {"color": "#9c27b0", "icon": "🌊"},
    "图像分割":    {"color": "#e91e63", "icon": "✂"},
    "形态学":      {"color": "#00bcd4", "icon": "🔲"},
    "条件":        {"color": "#ff5722", "icon": "🔀"},
    "模板匹配":    {"color": "#4caf50", "icon": "🎯"},
    "检测":        {"color": "#f44336", "icon": "🔍"},
    "特征提取":    {"color": "#ff9800", "icon": "📊"},
    "其他":        {"color": "#607d8b", "icon": "📦"},
    "视频":        {"color": "#795548", "icon": "🎬"},
    "输出":        {"color": "#607d8b", "icon": "📤"},
    "ONNX":        {"color": "#e91e63", "icon": "🧠"},
    "网络通讯":    {"color": "#795548", "icon": "🌐"},
}

GROUP_COLORS = {k: v["color"] for k, v in GROUP_META.items()}
GROUP_ICONS = {k: v["icon"] for k, v in GROUP_META.items()}


class ToolboxPanel(QWidget):
    """Left panel showing available node types in categorized groups.

    Features:
      - Tree view with categorized groups
      - Favorites section with persistent storage
      - Search/filter
      - Context menu (add to favorites, create node)
      - Double-click to create node
    """

    node_type_selected = pyqtSignal(str)  # node type name
    favorites_changed = pyqtSignal()

    FAVORITES_KEY = "Toolbox/Favorites"
    FAVORITES_GROUP_NAME = "★ 收藏"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._favorites: list[str] = []
        self._load_favorites()
        self._setup_ui()
        self._load_groups()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 4, 0)
        h_layout.setSpacing(4)

        title = QLabel("流程功能列表")
        title.setStyleSheet("color: #dcdcdc; font-size: 12px; font-weight: bold;")
        h_layout.addWidget(title, 1)

        # View toggle buttons
        btn_style = """
            QToolButton { background: transparent; border: none; color: #999; padding: 2px 4px; }
            QToolButton:hover { color: #dcdcdc; }
            QToolButton:checked { color: #0078d4; }
        """
        self._tree_btn = QToolButton()
        self._tree_btn.setText("📂")
        self._tree_btn.setToolTip("树形视图")
        self._tree_btn.setCheckable(True)
        self._tree_btn.setChecked(True)
        self._tree_btn.setStyleSheet(btn_style)
        h_layout.addWidget(self._tree_btn)

        refresh_btn = QToolButton()
        refresh_btn.setText("↻")
        refresh_btn.setToolTip("刷新列表")
        refresh_btn.setStyleSheet(btn_style)
        refresh_btn.clicked.connect(self.refresh)
        h_layout.addWidget(refresh_btn)

        layout.addWidget(header)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索模块...")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: #333337; color: #dcdcdc; border: none;
                border-bottom: 1px solid #3f3f46; padding: 6px 8px; font-size: 12px;
            }
            QLineEdit:focus { border-bottom: 1px solid #0078d4; }
        """)
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(self.tree.DragOnly)
        self.tree.setFont(QFont("Segoe UI", 10))
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        # Stats footer
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("color: #666; font-size: 10px; padding: 3px 8px; background: #1e1e1e; border-top: 1px solid #3f3f46;")
        layout.addWidget(self._stats_label)

    # ── Favorites ────────────────────────────────────────────────────

    def _load_favorites(self):
        settings = QSettings()
        raw = settings.value(self.FAVORITES_KEY, [])
        if isinstance(raw, str):
            raw = [raw] if raw else []
        self._favorites = list(raw) if raw else []

    def _save_favorites(self):
        settings = QSettings()
        settings.setValue(self.FAVORITES_KEY, self._favorites)
        settings.sync()
        self.favorites_changed.emit()

    def is_favorite(self, type_name: str) -> bool:
        return type_name in self._favorites

    def add_favorite(self, type_name: str):
        if type_name and type_name not in self._favorites:
            self._favorites.append(type_name)
            self._save_favorites()
            self._load_groups()

    def remove_favorite(self, type_name: str):
        if type_name in self._favorites:
            self._favorites.remove(type_name)
            self._save_favorites()
            self._load_groups()

    def toggle_favorite(self, type_name: str):
        if self.is_favorite(type_name):
            self.remove_favorite(type_name)
        else:
            self.add_favorite(type_name)

    # ── Tree Population ──────────────────────────────────────────────

    def _load_groups(self):
        """Load all node groups into the tree, favorites first."""
        self.tree.clear()

        # Favorites section
        if self._favorites:
            fav_group = QTreeWidgetItem(self.tree)
            fav_group.setText(0, self.FAVORITES_GROUP_NAME)
            fav_group.setData(0, Qt.UserRole, "")
            fav_group.setFlags(fav_group.flags() & ~Qt.ItemIsDragEnabled)
            fav_font = QFont("Segoe UI", 10, QFont.Bold)
            fav_group.setFont(0, fav_font)
            fav_group.setForeground(0, QColor("#ffd700"))

            for type_name in self._favorites:
                node_type = node_registry.get_type(type_name)
                if node_type:
                    self._add_node_item(fav_group, node_type, is_fav=True)

            fav_group.setExpanded(True)

        # Regular groups
        total_groups = 0
        total_nodes = 0
        for group in node_data_group_manager.get_all_groups():
            if not group.node_types:
                continue

            total_groups += 1
            group_item = QTreeWidgetItem(self.tree)
            count = len(group.node_types)
            total_nodes += count
            icon = GROUP_ICONS.get(group.name, "📁")
            group_item.setText(0, f"{icon}  {group.name}  ({count})")
            group_item.setData(0, Qt.UserRole, "")  # empty = group
            group_item.setFlags(group_item.flags() & ~Qt.ItemIsDragEnabled)

            font = QFont("Segoe UI", 10, QFont.Bold)
            group_item.setFont(0, font)
            color = GROUP_COLORS.get(group.name, "#dcdcdc")
            group_item.setForeground(0, QColor(color))

            for node_type in group.node_types:
                self._add_node_item(group_item, node_type)

            group_item.setExpanded(True)

        self._stats_label.setText(f"  {total_groups} 个分组 · {total_nodes} 个节点"
                                  f"{' · ★ 收藏 ' + str(len(self._favorites)) + ' 个' if self._favorites else ''}")

    def _add_node_item(self, parent: QTreeWidgetItem, node_type: type, is_fav: bool = False):
        """Add a single node type entry under a group."""
        dn = node_type.__name__
        item = QTreeWidgetItem(parent)
        item.setText(0, f"  {dn}")
        item.setData(0, Qt.UserRole, node_type.__name__)
        item.setToolTip(0, (node_type.__doc__ or "").strip() or dn)

        # Visual distinction for favorites
        if is_fav:
            item.setForeground(0, QColor("#ffd700"))
        else:
            item.setForeground(0, QColor("#dcdcdc"))

    # ── Search ───────────────────────────────────────────────────────

    def _on_search(self, text: str):
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            group_visible = False
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if not text or text.lower() in child.text(0).lower():
                    child.setHidden(False)
                    group_visible = True
                else:
                    child.setHidden(True)
            group_item.setHidden(not group_visible)

    # ── Context Menu ─────────────────────────────────────────────────

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return

        type_name = item.data(0, Qt.UserRole)
        if not type_name:
            return  # it's a group header

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background: #0078d4; }
        """)

        create_act = QAction("创建节点", self)
        create_act.triggered.connect(lambda: self.node_type_selected.emit(type_name))
        menu.addAction(create_act)

        menu.addSeparator()

        if self.is_favorite(type_name):
            fav_act = QAction("★ 取消收藏", self)
            fav_act.triggered.connect(lambda: self.remove_favorite(type_name))
        else:
            fav_act = QAction("☆ 添加到收藏", self)
            fav_act.triggered.connect(lambda: self.add_favorite(type_name))
        menu.addAction(fav_act)

        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    # ── Actions ──────────────────────────────────────────────────────

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        type_name = item.data(0, Qt.UserRole)
        if type_name:
            self.node_type_selected.emit(type_name)

    def refresh(self):
        """Reload groups (e.g., after plugin discovery)."""
        self._load_favorites()
        self._load_groups()

    def get_selected_node_type(self) -> str | None:
        items = self.tree.selectedItems()
        if items:
            type_name = items[0].data(0, Qt.UserRole)
            if type_name:
                return type_name
        return None
