"""Template manager dialog — WPF ListBoxPresenter + ManageTemplatesCommand port.

Shows all saved templates, allows delete and select-to-add.
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                              QListWidgetItem, QPushButton, QLabel, QMessageBox)
from PyQt5.QtCore import Qt

from core.project import ProjectItem


class TemplateManagerDialog(QDialog):
    """Template management dialog — WPF 模板管理 1:1 port."""

    def __init__(self, project: ProjectItem, parent=None):
        super().__init__(parent)
        self._project = project
        self._selected_index: int = -1
        self.setWindowTitle("模板管理")
        self.setMinimumSize(480, 320)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header = QLabel("流程图模板列表")
        header.setStyleSheet("font-size: 13px; font-weight: bold; color: #dcdcdc;")
        layout.addWidget(header)

        self._desc = QLabel()
        self._desc.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self._desc)

        # List
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget { background: #2d2d30; color: #dcdcdc; border: 1px solid #3f3f46; font-size: 12px; }
            QListWidget::item { padding: 6px 8px; }
            QListWidget::item:selected { background: #094771; }
            QListWidget::item:hover { background: #3e3e42; }
        """)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        delete_btn = QPushButton("删除选中")
        delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()

        self._add_btn = QPushButton("从此模板新建流程图")
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._on_add_from_template)
        self._add_btn.setStyleSheet(
            "QPushButton { background: #0078d4; color: white; border: none; border-radius: 2px;"
            " padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #1a8ae8; }"
            "QPushButton:disabled { background: #555; color: #999; }")
        btn_row.addWidget(self._add_btn)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            "QPushButton { background: #3c3c3c; color: #dcdcdc; border: 1px solid #555;"
            " border-radius: 2px; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #4a4a4a; }")
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _refresh(self):
        self._list.clear()
        templates = self._project.templates
        total_nodes = 0
        for i, t in enumerate(templates):
            node_count = len(t.workflow.get_all_nodes()) if t.workflow else 0
            link_count = len(t.workflow.get_all_links()) if t.workflow else 0
            total_nodes += node_count
            label = f"{t.name}  （节点: {node_count}, 连线: {link_count}）"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, i)
            self._list.addItem(item)
        self._desc.setText(f"共 {len(templates)} 个模板，合计 {total_nodes} 个节点")
        self._selected_index = -1
        self._add_btn.setEnabled(False)

    def _on_item_clicked(self, item: QListWidgetItem):
        self._selected_index = item.data(Qt.UserRole)
        self._add_btn.setEnabled(True)

    def _on_delete(self):
        if self._selected_index < 0:
            return
        template = self._project.templates[self._selected_index]
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除模板 \"{template.name}\" 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._project.remove_template(self._selected_index)
            self._refresh()

    def _on_add_from_template(self):
        if self._selected_index < 0:
            return
        clone = self._project.add_diagram_from_template(self._selected_index)
        if clone:
            self._added_diagram = clone
            self.accept()

    @property
    def added_diagram(self):
        return getattr(self, '_added_diagram', None)
