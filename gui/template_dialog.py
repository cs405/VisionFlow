"""
模板管理器对话框
显示所有保存的模板，支持删除和选择添加。
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                              QListWidgetItem, QPushButton, QLabel, QMessageBox)
from PyQt5.QtCore import Qt

from core.project import ProjectItem


class TemplateManagerDialog(QDialog):
    """模板对话框 — 支持两种模式：add（从模板新建）和 manage（管理/删除）"""

    def __init__(self, project: ProjectItem, parent=None, mode: str = "manage"):
        """初始化模板对话框

        参数：
            project: 项目对象
            parent: 父对象
            mode: "add" 仅选择并添加, "manage" 可删除模板
        """
        super().__init__(parent)
        self._project = project
        self._selected_index: int = -1
        self._mode = mode

        title = "从模板新建流程图" if mode == "add" else "模板管理"
        self.setWindowTitle(title)
        self.setMinimumSize(480, 320)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局间距为8
        layout.setSpacing(8)

        # 头部标签
        header = QLabel("流程图模板列表")
        # 设置头部样式
        header.setStyleSheet("font-size: 13px; font-weight: bold; color: #dcdcdc;")
        # 添加到布局
        layout.addWidget(header)

        # 描述标签（显示模板统计信息）
        self._desc = QLabel()
        # 设置样式
        self._desc.setStyleSheet("color: #999; font-size: 11px;")
        # 添加到布局
        layout.addWidget(self._desc)

        # 模板列表
        self._list = QListWidget()
        # 设置列表样式
        self._list.setStyleSheet("""
            QListWidget { background: #2d2d30; color: #dcdcdc; border: 1px solid #3f3f46; font-size: 12px; }
            QListWidget::item { padding: 6px 8px; }
            QListWidget::item:selected { background: #094771; }
            QListWidget::item:hover { background: #3e3e42; }
        """)
        # 连接项点击信号
        self._list.itemClicked.connect(self._on_item_clicked)
        # 添加到布局，拉伸因子为1
        layout.addWidget(self._list, 1)

        # 按钮行
        btn_row = QHBoxLayout()
        # 设置按钮间距为6
        btn_row.setSpacing(6)

        # 删除按钮（仅管理模式显示）
        self._delete_btn = QPushButton("删除选中")
        self._delete_btn.clicked.connect(self._on_delete)
        if self._mode == "add":
            self._delete_btn.setVisible(False)
        btn_row.addWidget(self._delete_btn)

        # 添加弹性空间
        btn_row.addStretch()

        # 添加按钮（从模板新建流程图）
        self._add_btn = QPushButton("从此模板新建流程图")
        # 初始禁用
        self._add_btn.setEnabled(False)
        # 连接点击信号
        self._add_btn.clicked.connect(self._on_add_from_template)
        # 设置样式
        self._add_btn.setStyleSheet(
            "QPushButton { background: #0078d4; color: white; border: none; border-radius: 2px;"
            " padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #1a8ae8; }"
            "QPushButton:disabled { background: #555; color: #999; }")
        # 添加到按钮行
        btn_row.addWidget(self._add_btn)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        # 连接点击信号
        close_btn.clicked.connect(self.accept)
        # 设置样式
        close_btn.setStyleSheet(
            "QPushButton { background: #3c3c3c; color: #dcdcdc; border: 1px solid #555;"
            " border-radius: 2px; padding: 6px 16px; font-size: 12px; }"
            "QPushButton:hover { background: #4a4a4a; }")
        # 添加到按钮行
        btn_row.addWidget(close_btn)

        # 添加按钮行到布局
        layout.addLayout(btn_row)

    def _refresh(self):
        """刷新模板列表"""
        # 清空列表
        self._list.clear()
        # 获取模板列表
        templates = self._project.templates
        # 统计总节点数
        total_nodes = 0
        # 遍历模板
        for i, t in enumerate(templates):
            # 获取模板的节点数量
            node_count = len(t.workflow.get_all_nodes()) if t.workflow else 0
            # 获取模板的连线数量
            link_count = len(t.workflow.get_all_links()) if t.workflow else 0
            # 累加节点数
            total_nodes += node_count
            # 构建显示标签
            label = f"{t.name}  （节点: {node_count}, 连线: {link_count}）"
            # 创建列表项
            item = QListWidgetItem(label)
            # 存储模板索引到用户数据
            item.setData(Qt.UserRole, i)
            # 添加到列表
            self._list.addItem(item)
        # 更新描述标签
        self._desc.setText(f"共 {len(templates)} 个模板，合计 {total_nodes} 个节点")
        # 重置选中索引
        self._selected_index = -1
        # 禁用添加按钮
        self._add_btn.setEnabled(False)

    def _on_item_clicked(self, item: QListWidgetItem):
        """列表项点击事件处理

        参数：
            item: 被点击的列表项
        """
        # 保存选中的模板索引
        self._selected_index = item.data(Qt.UserRole)
        # 启用添加按钮
        self._add_btn.setEnabled(True)

    def _on_delete(self):
        """删除选中的模板"""
        # 如果没有选中项，返回
        if self._selected_index < 0:
            return
        # 获取模板对象
        template = self._project.templates[self._selected_index]
        # 显示确认对话框
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除模板 \"{template.name}\" 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        # 如果用户确认
        if reply == QMessageBox.Yes:
            # 删除模板
            self._project.remove_template(self._selected_index)
            # 刷新列表
            self._refresh()

    def _on_add_from_template(self):
        """从选中的模板创建新流程图"""
        # 如果没有选中项，返回
        if self._selected_index < 0:
            return
        # 从模板添加新图表
        clone = self._project.add_diagram_from_template(self._selected_index)
        # 如果添加成功
        if clone:
            # 保存添加的图表
            self._added_diagram = clone
            # 关闭对话框
            self.accept()

    @property
    def added_diagram(self):
        """获取从模板添加的图表

        返回：
            添加的图表对象，如果没有则返回None
        """
        # 返回_added_diagram属性，如果不存在则返回None
        return getattr(self, '_added_diagram', None)