"""
WPF左侧面板精确还原 — "流程资源" GroupBox
- GroupBox标题: "流程资源" + 右侧切换按钮(树/列表)
- 内容: QTreeWidget(分组层级显示节点) + 搜索过滤
- 支持拖拽创建节点
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QTreeWidget,
    QTreeWidgetItem, QLineEdit, QPushButton, QLabel
)
from PySide6.QtCore import Qt, QMimeData, QSize
from PySide6.QtGui import QFont, QDrag

from core.registry import NodeRegistry
from .theme import Colors


class FlowResourcePanel(QWidget):
    """WPF "流程资源" 面板 — 节点工具箱"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tree_mode = True  # True=树形视图, False=列表视图
        self._setup_ui()
        self._populate_nodes()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # GroupBox "流程资源"
        self.group_box = QGroupBox()
        self.group_box.setStyleSheet(f"""
            QGroupBox {{
                color: {Colors.Foreground};
                font: bold 12px "Microsoft YaHei";
                border: none;
                margin-top: 0;
                padding-top: 20px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 4px 8px;
                background: {Colors.BackgroundDark};
                border-radius: 3px;
            }}
        """)

        # 标题栏(含切换按钮)
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)

        self.toggle_btn = QPushButton("≡")
        self.toggle_btn.setFixedSize(24, 24)
        self.toggle_btn.setToolTip("切换视图 (树/列表)")
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.ForegroundDim};
                border: none;
                font-size: 14px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {Colors.Border};
                color: {Colors.Foreground};
            }}
        """)
        self.toggle_btn.clicked.connect(self._toggle_view)

        self.group_box_title = QLabel("流程资源")
        self.group_box_title.setStyleSheet(f"color: {Colors.Foreground}; font: bold 12px 'Microsoft YaHei'; background: transparent;")

        title_layout.addWidget(self.group_box_title)
        title_layout.addStretch()
        title_layout.addWidget(self.toggle_btn)

        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(4, 4, 4, 4)
        group_layout.setSpacing(4)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索节点...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search)
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background: {Colors.Border};
                color: {Colors.Foreground};
                border: 1px solid {Colors.BorderLight};
                border-radius: 4px;
                padding: 5px 8px;
                font: 11px "Microsoft YaHei";
            }}
            QLineEdit:focus {{
                border-color: {Colors.Accent};
            }}
        """)
        group_layout.addWidget(title_widget)
        group_layout.addWidget(self.search_box)

        # 节点树
        self.node_tree = QTreeWidget()
        self.node_tree.setHeaderHidden(True)
        self.node_tree.setIndentation(16)
        self.node_tree.setDragEnabled(True)
        self.node_tree.setDragDropMode(QTreeWidget.DragOnly)
        self.node_tree.setAnimated(True)
        self.node_tree.setStyleSheet(f"""
            QTreeWidget {{
                background: transparent;
                color: {Colors.Foreground};
                border: none;
                font: 11px "Microsoft YaHei";
            }}
            QTreeWidget::item {{
                padding: 3px 4px;
                border-radius: 2px;
                border: none;
            }}
            QTreeWidget::item:hover {{
                background: #2A2D2E;
            }}
            QTreeWidget::item:selected {{
                background: {Colors.Accent};
            }}
        """)

        group_layout.addWidget(self.node_tree)
        self.group_box.setLayout(group_layout)
        layout.addWidget(self.group_box)
        self.setLayout(layout)

    def _populate_nodes(self):
        """填充节点树 — WPF层级结构: Group → NodeData"""
        self.node_tree.clear()
        registry = NodeRegistry()
        categories = registry.get_categories()

        if not categories:
            item = QTreeWidgetItem(["暂无可用节点"])
            item.setFlags(Qt.NoItemFlags)
            self.node_tree.addTopLevelItem(item)
            return

        for category in sorted(categories.keys()):
            nodes = sorted(categories[category])
            cat_item = QTreeWidgetItem([f"  {category}"])
            cat_item.setExpanded(True)
            cat_font = QFont("Microsoft YaHei", 11, QFont.Bold)
            cat_item.setFont(0, cat_font)
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsDragEnabled)
            cat_item.setSizeHint(0, QSize(0, 28))

            for node_name in nodes:
                node_cls = registry.get_node_class(node_name)
                desc = getattr(node_cls, 'description', '') if node_cls else ''
                display = f"    {node_name}"
                node_item = QTreeWidgetItem([display])
                node_item.setData(0, Qt.UserRole, node_name)
                node_item.setToolTip(0, f"{node_name}\n{desc}" if desc else node_name)
                node_item.setFlags(node_item.flags() | Qt.ItemIsDragEnabled)
                node_item.setSizeHint(0, QSize(0, 24))
                cat_item.addChild(node_item)

            self.node_tree.addTopLevelItem(cat_item)

    def _toggle_view(self):
        """切换树/列表视图"""
        self._tree_mode = not self._tree_mode
        self.toggle_btn.setText("☰" if self._tree_mode else "≡")
        # 列表模式：全部展开为平级列表
        if not self._tree_mode:
            self.node_tree.setIndentation(0)
            for i in range(self.node_tree.topLevelItemCount()):
                cat = self.node_tree.topLevelItem(i)
                for j in range(cat.childCount()):
                    child = cat.child(j)
                    child.setHidden(False)
        else:
            self.node_tree.setIndentation(16)

    def _on_search(self, text: str):
        """搜索过滤"""
        search = text.lower().strip()
        for i in range(self.node_tree.topLevelItemCount()):
            cat = self.node_tree.topLevelItem(i)
            visible = False
            for j in range(cat.childCount()):
                node = cat.child(j)
                name = node.text(0).lower()
                matches = search == "" or search in name
                node.setHidden(not matches)
                if matches:
                    visible = True
            cat.setHidden(not visible)

    def refresh(self):
        self._populate_nodes()

    def startDrag(self, supportedActions):
        """允许拖拽"""
        item = self.node_tree.currentItem()
        if item and item.data(0, Qt.UserRole):
            node_name = item.data(0, Qt.UserRole)
            mime = QMimeData()
            mime.setText(node_name)
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.CopyAction)
