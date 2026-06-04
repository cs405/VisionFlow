"""Toolbox panel - tree/grid display of available nodes with favorites.

Ported from H.Controls.FavoriteBox + H.Controls.TreeListView.
Shows nodes grouped by category. Supports favorites, search, and context menu.
"""

from dataclasses import dataclass

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication,
                              QMenu, QAction, QToolButton, QLineEdit, QScrollArea,
                              QFrame, QGridLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QPoint, QMimeData
from PyQt5.QtGui import QDrag

from core.node_group import node_data_group_manager


GROUP_META = {
    "图像数据源": {"color": "#4a9eff", "icon": "◎"},
    "系统数据源": {"color": "#5c6bc0", "icon": "◫"},
    "图像预处理模块": {"color": "#ff8c00", "icon": "◌"},
    "滤波模块": {"color": "#9c27b0", "icon": "≈"},
    "图像分割提取模块": {"color": "#e91e63", "icon": "✂"},
    "形态学模块": {"color": "#00bcd4", "icon": "⬒"},
    "逻辑模块": {"color": "#ff5722", "icon": "⇄"},
    "模板匹配模块": {"color": "#4caf50", "icon": "⌖"},
    "对象识别模块": {"color": "#f44336", "icon": "◉"},
    "特征提取模块": {"color": "#ff9800", "icon": "✣"},
    "网络通讯模块": {"color": "#795548", "icon": "⌁"},
    "结果输出模块": {"color": "#607d8b", "icon": "↗"},
    "Onnx通用模型": {"color": "#c2185b", "icon": "AI"},
    "其他模块": {"color": "#607d8b", "icon": "◇"},
    "视频处理模块": {"color": "#8d6e63", "icon": "▶"},
    "★ 收藏": {"color": "#d7ba7d", "icon": "★"},
}


@dataclass(slots=True)
class NodeMeta:
    type_name: str
    display_name: str
    description: str
    group_name: str
    color: str
    icon_text: str


class NodeTileButton(QFrame):
    activated = pyqtSignal(str)
    selected = pyqtSignal(str)
    favorite_toggled = pyqtSignal(str)

    def __init__(self, meta: NodeMeta, is_favorite: bool = False, parent=None):
        super().__init__(parent)
        self.meta = meta
        self.is_favorite = is_favorite
        self._selected = False
        self._press_pos = QPoint()
        self._drag_started = False
        self.setCursor(Qt.OpenHandCursor)
        self.setFixedSize(108, 78)
        self.setFrameShape(QFrame.NoFrame)
        self._build_ui()
        self._refresh_style()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(4)

        self._icon_label = QLabel(self.meta.icon_text)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setFixedSize(28, 28)
        self._icon_label.setStyleSheet(
            f"background: {self.meta.color}; border-radius: 6px; color: white;"
            "font-size: 14px; font-weight: 700; font-family: 'Segoe UI Symbol', 'Microsoft YaHei UI';"
        )
        top_row.addWidget(self._icon_label)

        top_row.addStretch()

        self._fav_label = QLabel("★" if self.is_favorite else "")
        self._fav_label.setStyleSheet("color: #d7ba7d; font-size: 12px; font-weight: bold;")
        top_row.addWidget(self._fav_label)
        layout.addLayout(top_row)

        self._title_label = QLabel(self.meta.display_name)
        self._title_label.setWordWrap(True)
        self._title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._title_label.setStyleSheet("color: #dcdcdc; font-size: 11px; font-weight: 600;")
        self._title_label.setToolTip(self.meta.description)
        layout.addWidget(self._title_label, 1)

        self.setToolTip(f"{self.meta.display_name}\n{self.meta.description}\n类型: {self.meta.type_name}")

    def set_selected(self, selected: bool):
        self._selected = selected
        self._refresh_style()

    def _refresh_style(self):
        border = "#0078d4" if self._selected else ("#d7ba7d" if self.is_favorite else "#3f3f46")
        bg = "#2f3640" if self._selected else "#252526"
        self.setStyleSheet(
            "QFrame {"
            f"background: {bg};"
            f"border: 1px solid {border};"
            "border-radius: 8px;"
            "}"
            "QFrame:hover { background: #2d2d30; border-color: #0078d4; }"
        )
        self._fav_label.setText("★" if self.is_favorite else "")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
            self._drag_started = False
            self.selected.emit(self.meta.type_name)
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if (event.pos() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return
        self._drag_started = True
        self._start_drag()
        self.setCursor(Qt.OpenHandCursor)
        event.accept()

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        if event.button() == Qt.LeftButton and not self._drag_started:
            self.selected.emit(self.meta.type_name)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.meta.type_name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #2d2d30; color: #dcdcdc; border: 1px solid #505050; }"
            "QMenu::item { padding: 6px 20px; }"
            "QMenu::item:selected { background: #0078d4; }"
        )
        create_act = QAction("创建节点", self)
        create_act.triggered.connect(lambda: self.activated.emit(self.meta.type_name))
        menu.addAction(create_act)
        menu.addSeparator()
        fav_act = QAction("★ 取消收藏" if self.is_favorite else "☆ 添加到收藏", self)
        fav_act.triggered.connect(lambda: self.favorite_toggled.emit(self.meta.type_name))
        menu.addAction(fav_act)
        menu.exec_(event.globalPos())

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.meta.type_name)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self.rect().center())
        drag.exec_(Qt.CopyAction)


class ToolboxPanel(QWidget):
    """WPF 风格的左侧流程资源栏：按分组展示图标节点，支持搜索、收藏和拖拽到画布。"""

    node_type_selected = pyqtSignal(str)
    favorites_changed = pyqtSignal()

    FAVORITES_KEY = "Toolbox/Favorites"
    FAVORITES_GROUP_NAME = "★ 收藏"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._favorites: list[str] = []
        self._selected_type: str | None = None
        self._tile_widgets: dict[str, NodeTileButton] = {}
        self._load_favorites()
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(32)
        header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 4, 0)
        h_layout.setSpacing(4)

        title = QLabel("流程资源")
        title.setStyleSheet("color: #dcdcdc; font-size: 12px; font-weight: bold;")
        h_layout.addWidget(title, 1)

        refresh_btn = QToolButton()
        refresh_btn.setText("↻")
        refresh_btn.setToolTip("刷新节点列表")
        refresh_btn.setStyleSheet(
            "QToolButton { background: transparent; border: none; color: #999; padding: 2px 6px; }"
            "QToolButton:hover { color: #dcdcdc; background: #3e3e42; }"
        )
        refresh_btn.clicked.connect(self.refresh)
        h_layout.addWidget(refresh_btn)
        layout.addWidget(header)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索模块 / 中文名称...")
        self.search_box.setStyleSheet(
            "QLineEdit { background: #333337; color: #dcdcdc; border: none;"
            "border-bottom: 1px solid #3f3f46; padding: 6px 8px; font-size: 12px; }"
            "QLineEdit:focus { border-bottom: 1px solid #0078d4; }"
        )
        self.search_box.textChanged.connect(lambda: self.refresh())
        layout.addWidget(self.search_box)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: #252526; border: none; }")
        layout.addWidget(self._scroll, 1)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_layout.setSpacing(10)
        self._scroll.setWidget(self._content)

        self._stats_label = QLabel()
        self._stats_label.setStyleSheet(
            "color: #666; font-size: 10px; padding: 3px 8px; background: #1e1e1e;"
            "border-top: 1px solid #3f3f46;"
        )
        layout.addWidget(self._stats_label)

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

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                while child_layout.count():
                    child_item = child_layout.takeAt(0)
                    if child_item.widget() is not None:
                        child_item.widget().deleteLater()
        self._tile_widgets.clear()

    def _describe_node_type(self, node_type, group_name: str) -> NodeMeta:
        display_name = ""
        try:
            instance = node_type()
            candidate = getattr(instance, 'display_name', '') or getattr(instance, 'name', '')
            if isinstance(candidate, str):
                display_name = candidate.strip()
        except Exception:
            display_name = ""
        if not display_name:
            display_name = node_type.__name__
        doc = (node_type.__doc__ or '').strip().splitlines()
        description = doc[0] if doc else display_name
        group_meta = GROUP_META.get(group_name, {"color": "#607d8b", "icon": "🧩"})
        return NodeMeta(
            type_name=node_type.__name__,
            display_name=display_name,
            description=description,
            group_name=group_name,
            color=group_meta["color"],
            icon_text=group_meta["icon"],
        )

    def _matches_search(self, meta: NodeMeta, keyword: str) -> bool:
        if not keyword:
            return True
        haystack = f"{meta.display_name} {meta.description} {meta.type_name} {meta.group_name}".lower()
        return keyword in haystack

    def _build_group_section(self, title: str, metas: list[NodeMeta]):
        if not metas:
            return
        group_meta = GROUP_META.get(title, {"color": "#607d8b", "icon": "🧩"})

        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        header = QLabel(f"{group_meta['icon']}  {title}")
        header.setStyleSheet(
            f"color: {group_meta['color']}; font-size: 12px; font-weight: bold; padding: 2px 2px;"
        )
        section_layout.addWidget(header)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        for index, meta in enumerate(metas):
            tile = NodeTileButton(meta, is_favorite=self.is_favorite(meta.type_name))
            tile.activated.connect(self.node_type_selected.emit)
            tile.selected.connect(self._set_selected_type)
            tile.favorite_toggled.connect(self.toggle_favorite)
            self._tile_widgets[meta.type_name] = tile
            row, col = divmod(index, 2)
            grid.addWidget(tile, row, col)
            if meta.type_name == self._selected_type:
                tile.set_selected(True)

        section_layout.addWidget(grid_host)
        self._content_layout.addWidget(section)

    def _set_selected_type(self, type_name: str):
        self._selected_type = type_name
        for current_type, tile in self._tile_widgets.items():
            tile.set_selected(current_type == type_name)

    def refresh(self):
        self._clear_content()
        keyword = self.search_box.text().strip().lower()

        visible_groups = 0
        visible_nodes = 0

        if self._favorites:
            favorite_metas = []
            type_lookup = {
                node_type.__name__: node_type
                for group in node_data_group_manager.get_all_groups()
                for node_type in group.node_types
            }
            for type_name in self._favorites:
                node_type = type_lookup.get(type_name)
                if node_type is None:
                    continue
                group_name = getattr(node_type, '__group__', '') or self.FAVORITES_GROUP_NAME
                meta = self._describe_node_type(node_type, group_name)
                if self._matches_search(meta, keyword):
                    favorite_metas.append(meta)
            if favorite_metas:
                self._build_group_section(self.FAVORITES_GROUP_NAME, favorite_metas)
                visible_groups += 1
                visible_nodes += len(favorite_metas)

        for group in node_data_group_manager.get_all_groups():
            if not group.node_types:
                continue
            metas = []
            for node_type in group.node_types:
                meta = self._describe_node_type(node_type, group.name)
                if self._matches_search(meta, keyword):
                    metas.append(meta)
            if not metas:
                continue
            self._build_group_section(group.name, metas)
            visible_groups += 1
            visible_nodes += len(metas)

        self._content_layout.addStretch(1)
        self._stats_label.setText(
            f"  {visible_groups} 个分组 · {visible_nodes} 个节点"
            f"{' · ★ 收藏 ' + str(len(self._favorites)) + ' 个' if self._favorites else ''}"
        )

    def get_selected_node_type(self) -> str | None:
        return self._selected_type
