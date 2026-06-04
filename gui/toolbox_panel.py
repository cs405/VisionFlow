"""
节点工具箱 — WPF风格，支持搜索过滤和拖拽创建节点
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QTreeWidget,
    QTreeWidgetItem, QLabel
)
from PySide6.QtCore import Qt, QMimeData, QSize
from PySide6.QtGui import QDrag, QFont

from core.registry import NodeRegistry

from .theme import Colors, Fonts


class ToolboxPanel(QWidget):
    """节点工具箱面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._populate_nodes()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索节点...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search)
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.Border};
                color: {Colors.Foreground};
                border: 1px solid {Colors.BorderLight};
                border-radius: 4px;
                padding: 6px 8px;
                font: 11px "{Fonts.Family}";
            }}
            QLineEdit:focus {{
                border-color: {Colors.Accent};
            }}
        """)
        layout.addWidget(self.search_box)

        # 节点树
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderHidden(True)
        self.node_tree.setIndentation(16)
        self.node_tree.setDragEnabled(True)
        self.node_tree.setDragDropMode(QTreeWidget.DragOnly)
        self.node_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: transparent;
                color: {Colors.Foreground};
                border: none;
                font: 11px "{Fonts.Family}";
            }}
            QTreeWidget::item {{
                padding: 5px 4px;
                border-radius: 2px;
            }}
            QTreeWidget::item:hover {{
                background-color: #2A2D2E;
            }}
            QTreeWidget::item:selected {{
                background-color: {Colors.Accent};
            }}
        """)

        layout.addWidget(self.node_tree)
        self.setLayout(layout)

    def _populate_nodes(self):
        """填充节点列表"""
        self.node_tree.clear()
        registry = NodeRegistry()
        categories = registry.get_categories()

        if not categories:
            empty_item = QTreeWidgetItem(["暂无可用节点"])
            empty_item.setFlags(Qt.NoItemFlags)
            self.node_tree.addTopLevelItem(empty_item)
            return

        for category in sorted(categories.keys()):
            nodes = sorted(categories[category])
            cat_item = QTreeWidgetItem([f"  {category}  ({len(nodes)})"])
            cat_item.setExpanded(True)
            cat_font = QFont(Fonts.Family, 11, QFont.Bold)
            cat_item.setFont(0, cat_font)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsDragEnabled)

            for node_name in nodes:
                node_class = registry.get_node_class(node_name)
                node_item = QTreeWidgetItem([f"    {node_name}"])
                node_item.setData(0, Qt.UserRole, node_name)
                node_item.setToolTip(0, getattr(node_class, 'description', node_name) if node_class else node_name)
                node_item.setFlags(node_item.flags() | Qt.ItemIsDragEnabled)
                node_item.setSizeHint(0, QSize(0, 24))
                cat_item.addChild(node_item)

            self.node_tree.addTopLevelItem(cat_item)

    def _on_search(self, text: str):
        """搜索过滤节点"""
        search_text = text.lower().strip()

        for i in range(self.node_tree.topLevelItemCount()):
            cat_item = self.node_tree.topLevelItem(i)
            visible = False

            for j in range(cat_item.childCount()):
                node_item = cat_item.child(j)
                node_name = node_item.text(0).lower()
                matches = search_text == "" or search_text in node_name
                node_item.setHidden(not matches)
                if matches:
                    visible = True

            cat_item.setHidden(not visible)

    def refresh(self):
        """刷新节点列表"""
        self._populate_nodes()

    def start_drag(self, item: QTreeWidgetItem):
        """开始拖拽"""
        node_name = item.data(0, Qt.UserRole)
        if not node_name:
            return

        mime_data = QMimeData()
        mime_data.setText(node_name)
        mime_data.setData("application/x-node-type", node_name.encode())

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction)
