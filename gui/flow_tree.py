"""
流程管理树 — WPF风格流程层级管理
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from .theme import Colors, Fonts


class FlowTree(QWidget):
    """流程管理树"""

    flow_selected = Signal(str)  # 流程名称
    flow_added = Signal()
    flow_removed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        btn_style = f"""
            QPushButton {{
                background-color: {Colors.BackgroundLight};
                color: {Colors.Foreground};
                border: 1px solid {Colors.Border};
                border-radius: 3px;
                padding: 4px 8px;
                font: 10px "{Fonts.Family}";
            }}
            QPushButton:hover {{
                background-color: {Colors.BorderLight};
                border-color: {Colors.Accent};
            }}
        """

        self.btn_new = QPushButton("新建")
        self.btn_new.setStyleSheet(btn_style)
        self.btn_new.clicked.connect(self.flow_added)
        toolbar.addWidget(self.btn_new)

        self.btn_copy = QPushButton("复制")
        self.btn_copy.setStyleSheet(btn_style)
        toolbar.addWidget(self.btn_copy)

        self.btn_delete = QPushButton("删除")
        self.btn_delete.setStyleSheet(btn_style)
        self.btn_delete.clicked.connect(self._on_delete_flow)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 流程树
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setStyleSheet(f"""
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

        # 默认根节点
        self.root_item = QTreeWidgetItem(["📁 主流程"])
        root_font = QFont(Fonts.Family, 11, QFont.Bold)
        self.root_item.setFont(0, root_font)
        self.tree.addTopLevelItem(self.root_item)
        self.tree.expandAll()

        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        self.setLayout(layout)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """流程项点击"""
        flow_name = item.text(0).lstrip("📄📁 ")
        if item.parent():  # 子流程
            self.flow_selected.emit(flow_name)

    def _on_delete_flow(self):
        """删除选中流程"""
        selected = self.tree.selectedItems()
        if selected:
            item = selected[0]
            if item.parent():  # 不能删除根节点
                flow_name = item.text(0).lstrip("📄 ")
                self.flow_removed.emit(flow_name)
                item.parent().removeChild(item)

    def add_flow(self, name: str):
        """添加流程"""
        sub_item = QTreeWidgetItem([f"📄 {name}"])
        sub_item.setFont(0, QFont(Fonts.Family, 10))
        self.root_item.addChild(sub_item)
        self.tree.expandAll()

    def add_flows(self, names: list):
        """批量添加流程"""
        for name in names:
            self.add_flow(name)
