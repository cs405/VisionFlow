"""ConditionNodeData规则的条件编辑器对话框。"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.node_base import ConditionNodeData, VisionPropertyCondition


class ConditionEditorDialog(QDialog):
    """编辑条件节点的VisionPropertyCondition条目列表"""

    # 表头列名
    HEADERS = ("属性", "操作符", "比较值", "输出分支")

    def __init__(self, node: ConditionNodeData, parent=None):
        """初始化条件编辑器对话框

        参数：
            node: 条件节点数据对象
            parent: 父对象
        """
        # 调用父类QDialog的构造函数
        super().__init__(parent)
        # 保存条件节点引用
        self.node = node
        # 设置窗口标题
        self.setWindowTitle("条件编辑器")
        # 设置窗口大小为820x420
        self.resize(820, 420)

        # 获取候选属性列表（从节点获取可用的条件候选）
        self._candidate_properties = [name for name, _ in node.get_condition_candidates()]
        # 输出节点列表：默认分支 + 下游节点
        self._output_nodes = [("默认", "")]
        # 遍历节点的下游节点，添加到输出节点列表
        self._output_nodes.extend((n.name or n.node_id, n.node_id) for n in node.to_node_datas)

        # 设置UI界面
        self._setup_ui()
        # 设置节点的条件列表
        self.set_conditions(node.conditions)

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(10, 10, 10, 10)
        # 设置布局间距
        layout.setSpacing(8)

        # 提示标签
        tip = QLabel('条件表达式按「上游节点名.结果属性」评估；比较值支持数字、文本、布尔文本。')
        # 允许换行
        tip.setWordWrap(True)
        # 设置样式
        tip.setStyleSheet("color: #999; font-size: 12px;")
        # 添加到布局
        layout.addWidget(tip)

        # 创建表格控件（0行，表头数量列）
        self.table = QTableWidget(0, len(self.HEADERS), self)
        # 设置水平表头标签
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        # 最后一列拉伸填充
        self.table.horizontalHeader().setStretchLastSection(True)
        # 隐藏垂直表头
        self.table.verticalHeader().setVisible(False)
        # 设置选择行为为选择行
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        # 添加表格到布局，拉伸因子为1
        layout.addWidget(self.table, 1)

        # 工具栏水平布局
        tool_row = QHBoxLayout()
        # 添加条件按钮
        add_btn = QPushButton("添加条件")
        # 连接点击信号到add_empty_row方法
        add_btn.clicked.connect(self.add_empty_row)
        # 添加到布局
        tool_row.addWidget(add_btn)

        # 删除选中按钮
        remove_btn = QPushButton("删除选中")
        # 连接点击信号到remove_selected_rows方法
        remove_btn.clicked.connect(self.remove_selected_rows)
        # 添加到布局
        tool_row.addWidget(remove_btn)

        # 测试当前结果按钮
        test_btn = QPushButton("测试当前结果")
        # 连接点击信号到_test_current_conditions方法
        test_btn.clicked.connect(self._test_current_conditions)
        # 添加到布局
        tool_row.addWidget(test_btn)

        # 添加弹性空间
        tool_row.addStretch()
        # 添加工具栏布局到主布局
        layout.addLayout(tool_row)

        # 按钮框（确定/取消）
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        # 连接确定按钮信号
        buttons.accepted.connect(self.accept)
        # 连接取消按钮信号
        buttons.rejected.connect(self.reject)
        # 添加到布局
        layout.addWidget(buttons)

    def _create_property_combo(self, current_text: str = "") -> QComboBox:
        """创建属性选择下拉框

        参数：
            current_text: 当前选中的文本

        返回：
            配置好的QComboBox对象
        """
        # 创建下拉框
        combo = QComboBox()
        # 设置为可编辑
        combo.setEditable(True)
        # 添加候选属性列表
        combo.addItems(self._candidate_properties)
        # 设置当前文本
        combo.setCurrentText(current_text)
        # 返回下拉框
        return combo

    def _create_operator_combo(self, current_text: str = ">") -> QComboBox:
        """创建操作符选择下拉框

        参数：
            current_text: 当前选中的文本

        返回：
            配置好的QComboBox对象
        """
        # 创建下拉框
        combo = QComboBox()
        # 添加支持的操作符列表
        combo.addItems(list(VisionPropertyCondition.SUPPORTED_OPERATORS))
        # 如果当前操作符在支持列表中则设置，否则默认">"
        combo.setCurrentText(current_text if current_text in VisionPropertyCondition.SUPPORTED_OPERATORS else ">")
        # 返回下拉框
        return combo

    def _create_output_combo(self, output_node_id: str = "") -> QComboBox:
        """创建输出分支选择下拉框

        参数：
            output_node_id: 当前选中的输出节点ID

        返回：
            配置好的QComboBox对象
        """
        # 创建下拉框
        combo = QComboBox()
        # 遍历输出节点列表
        for label, node_id in self._output_nodes:
            # 添加项，存储节点ID作为用户数据
            combo.addItem(label, node_id)
        # 查找数据索引
        index = combo.findData(output_node_id)
        # 设置当前索引（如果找不到设为0）
        combo.setCurrentIndex(index if index >= 0 else 0)
        # 返回下拉框
        return combo

    def add_row(self, condition: VisionPropertyCondition | None = None):
        """添加一行到表格

        参数：
            condition: 要添加的条件对象，如果为None则创建默认条件
        """
        # 如果未提供条件，创建默认条件对象
        condition = condition or VisionPropertyCondition()
        # 获取当前行数
        row = self.table.rowCount()
        # 插入新行
        self.table.insertRow(row)

        # 创建属性下拉框
        property_combo = self._create_property_combo(condition.property_name)
        # 创建操作符下拉框
        operator_combo = self._create_operator_combo(condition.operator)
        # 创建输出分支下拉框
        output_combo = self._create_output_combo(condition.output_node_id)

        # 创建比较值单元格项
        value_item = QTableWidgetItem(str(condition.threshold if condition.threshold is not None else ""))

        # 设置第一列为属性下拉框
        self.table.setCellWidget(row, 0, property_combo)
        # 设置第二列为操作符下拉框
        self.table.setCellWidget(row, 1, operator_combo)
        # 设置第三列为比较值文本
        self.table.setItem(row, 2, value_item)
        # 设置第四列为输出分支下拉框
        self.table.setCellWidget(row, 3, output_combo)

    def add_empty_row(self):
        """添加一个空行（使用默认属性）"""
        # 如果有候选属性，使用第一个，否则使用空字符串
        default_property = self._candidate_properties[0] if self._candidate_properties else ""
        # 添加一行空条件
        self.add_row(VisionPropertyCondition(property_name=default_property))

    def remove_selected_rows(self):
        """删除选中的行"""
        # 获取所有选中行的行号，去重后按降序排序（从后往前删避免索引问题）
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True)
        # 遍历行号
        for row in rows:
            # 删除该行
            self.table.removeRow(row)

    def set_conditions(self, conditions: list[VisionPropertyCondition]):
        """设置条件列表到表格

        参数：
            conditions: 条件对象列表
        """
        # 清空表格所有行
        self.table.setRowCount(0)
        # 如果条件列表为空
        if not conditions:
            # 添加一个空行
            self.add_empty_row()
            return
        # 遍历条件列表
        for condition in conditions:
            # 添加每一行
            self.add_row(condition)

    def get_conditions(self) -> list[VisionPropertyCondition]:
        """从表格获取条件列表

        返回：
            条件对象列表
        """
        # 条件列表
        conditions: list[VisionPropertyCondition] = []
        # 遍历所有行
        for row in range(self.table.rowCount()):
            # 获取属性下拉框
            property_combo = self.table.cellWidget(row, 0)
            # 获取操作符下拉框
            operator_combo = self.table.cellWidget(row, 1)
            # 获取输出分支下拉框
            output_combo = self.table.cellWidget(row, 3)
            # 获取比较值项
            value_item = self.table.item(row, 2)

            # 从下拉框获取属性名（去除首尾空格）
            property_name = property_combo.currentText().strip() if property_combo else ""
            # 从下拉框获取操作符（去除首尾空格）
            operator = operator_combo.currentText().strip() if operator_combo else ">"
            # 从单元格获取比较值（去除首尾空格）
            threshold = value_item.text().strip() if value_item else ""
            # 从下拉框获取输出节点ID
            output_node_id = output_combo.currentData() if output_combo else ""

            # 如果属性名为空，跳过
            if not property_name:
                continue

            # 创建条件对象并添加到列表
            conditions.append(VisionPropertyCondition(
                property_name=property_name,      # 属性名
                operator=operator,               # 操作符
                threshold=threshold,             # 比较值
                output_node_id=output_node_id or "",  # 输出节点ID
            ))
        # 返回条件列表
        return conditions

    def _test_current_conditions(self):
        """测试当前条件与上游结果"""
        # 获取当前上游结果的快照
        snapshot = self.node.collect_upstream_results()
        # 获取表格中的条件列表
        conditions = self.get_conditions()
        # 评估匹配的条件
        matches = [cond for cond in conditions if cond.evaluate(snapshot)]

        # 如果没有上游结果
        if not snapshot:
            # 显示信息对话框
            QMessageBox.information(self, "条件测试", "当前没有可用的上游结果值。")
            return

        # 构建上游结果详情字符串
        details = "\n".join(f"- {k} = {v}" for k, v in snapshot.items())
        # 构建匹配结果字符串
        matched = "\n".join(f"- {c.display_text()}" for c in matches) or "无匹配条件"
        # 显示信息对话框
        QMessageBox.information(
            self,
            "条件测试",
            f"上游结果:\n{details}\n\n匹配结果:\n{matched}",
        )

    @classmethod
    def edit_conditions(cls, node: ConditionNodeData, parent=None) -> list[VisionPropertyCondition] | None:
        """静态方法：打开条件编辑器编辑节点的条件

        参数：
            node: 条件节点数据对象
            parent: 父对象

        返回：
            如果确认则返回条件列表，否则返回None
        """
        # 创建对话框实例
        dialog = cls(node=node, parent=parent)
        # 如果用户确认
        if dialog.exec_() == QDialog.Accepted:
            # 返回条件列表
            return dialog.get_conditions()
        # 取消则返回None
        return None