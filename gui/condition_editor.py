"""ConditionNodeData 的条件分支编辑器对话框。
每个条件分支 = 输入节点 + 条件组合模式 + 属性条件 + 输出节点。
"""

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

from core.node_base import ConditionNodeData, VisionNodeData
from core.conditions import (
    ConditionBranch,
    ConditionOperate,
    ConditionsPresenter,
    FilterOperate,
    PropertyCondition,
)


class ConditionEditorDialog(QDialog):
    """编辑条件节点的 ConditionBranch 条目列表。

    表列: 输入节点 | 条件组合 | 属性 | 操作符 | 比较值 | 输出分支
    """

    HEADERS = ("输入节点", "条件组合", "属性", "操作符", "比较值", "输出分支")

    def __init__(self, node: ConditionNodeData, parent=None):
        super().__init__(parent)
        self.node = node
        self.setWindowTitle("条件编辑器")
        self.resize(950, 460)

        # 获取图中所有节点（用于输入/输出节点选择器）
        all_nodes: list = []
        diagram = node.diagram_data
        if diagram and hasattr(diagram, 'get_all_nodes'):
            all_nodes = [n for n in diagram.get_all_nodes() if n.node_id != node.node_id]

        # 输入节点: 自身 + 所有上游节点 + 图中其他节点。优先级：上游=自身 > 其他
        upstream_ids = {n.node_id for n in node.get_all_from_this_node_datas()}
        input_seen = {node.node_id}
        self._input_nodes: list[tuple[str, str]] = [
            (f"自身 [{node.node_id}]", node.node_id)
        ]
        # 直接上游节点（前缀 → 区分于其他节点）
        for n in node.from_node_datas:
            if n.node_id not in input_seen:
                input_seen.add(n.node_id)
                label = f"→ {n.name or type(n).__name__} [{n.node_id}]"
                self._input_nodes.append((label, n.node_id))
        # 其他节点（间接/无关，无前缀）
        for n in all_nodes:
            if n.node_id not in input_seen:
                input_seen.add(n.node_id)
                label = f"{n.name or type(n).__name__} [{n.node_id}]"
                self._input_nodes.append((label, n.node_id))

        # 输出节点: 直接下游 + 图中所有其他节点。"默认" = 不指定输出（流程走默认端口）
        output_seen: set[str] = set()
        self._output_nodes: list[tuple[str, str]] = [
            ("默认（不指定输出节点，走默认端口）", "")
        ]
        for n in node.to_node_datas:
            if n.node_id not in output_seen:
                output_seen.add(n.node_id)
                label = f"{n.name or type(n).__name__} [{n.node_id}]"
                self._output_nodes.append((label, n.node_id))
        for n in all_nodes:
            if n.node_id not in output_seen:
                output_seen.add(n.node_id)
                label = f"{n.name or type(n).__name__} [{n.node_id}]"
                self._output_nodes.append((label, n.node_id))

        # 候选属性名
        self._candidate_properties = [name for name, _ in node.get_condition_candidates()]

        self._setup_ui()
        self.set_branches(node.conditions_presenter.branches)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        tip = QLabel(
            "每行一个条件分支。条件组合模式: ALL=全部满足, ANY=任一满足, "
            "ANY_NOT=任一不满足, NONE=全不满足。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        self.table = QTableWidget(0, len(self.HEADERS), self)
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table, 1)

        tool_row = QHBoxLayout()
        add_btn = QPushButton("添加分支")
        add_btn.clicked.connect(self._add_empty_row)
        tool_row.addWidget(add_btn)
        remove_btn = QPushButton("删除选中")
        remove_btn.clicked.connect(self._remove_selected_rows)
        tool_row.addWidget(remove_btn)
        test_btn = QPushButton("测试条件")
        test_btn.clicked.connect(self._test_current_conditions)
        tool_row.addWidget(test_btn)
        tool_row.addStretch()
        layout.addLayout(tool_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # -- combo factories --

    def _create_input_combo(self, node_id: str = "") -> QComboBox:
        combo = QComboBox()
        for label, nid in self._input_nodes:
            combo.addItem(label, nid)
        idx = combo.findData(node_id)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    def _create_operate_combo(self, operate: ConditionOperate = ConditionOperate.ALL) -> QComboBox:
        combo = QComboBox()
        items = [
            (ConditionOperate.ALL, "满足所有 (AND)"),
            (ConditionOperate.ANY, "满足任一 (OR)"),
            (ConditionOperate.ANY_NOT, "任一不满足 (NOT ANY)"),
            (ConditionOperate.NONE, "全不满足 (NOT ALL)"),
        ]
        for op, label in items:
            combo.addItem(label, op)
        idx = combo.findData(operate)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    def _create_property_combo(self, current_text: str = "") -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(self._candidate_properties)
        combo.setCurrentText(current_text)
        return combo

    def _create_filter_combo(self, current_op: FilterOperate = FilterOperate.EQUALS) -> QComboBox:
        combo = QComboBox()
        for op in FilterOperate:
            combo.addItem(op.value, op)
        idx = combo.findData(current_op)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    def _create_output_combo(self, node_id: str = "") -> QComboBox:
        combo = QComboBox()
        for label, nid in self._output_nodes:
            combo.addItem(label, nid)
        idx = combo.findData(node_id)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        return combo

    # -- row management --

    def _add_row(self, branch: ConditionBranch):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 第一个条件（或空）
        cond = branch.conditions[0] if branch.conditions else PropertyCondition()

        self.table.setCellWidget(row, 0, self._create_input_combo(branch.selected_input_node_id))
        self.table.setCellWidget(row, 1, self._create_operate_combo(branch.condition_operate))
        self.table.setCellWidget(row, 2, self._create_property_combo(cond.property_name))
        self.table.setCellWidget(row, 3, self._create_filter_combo(cond.filter_operate))
        self.table.setItem(row, 4, QTableWidgetItem(str(cond.value if cond.value is not None else "")))
        self.table.setCellWidget(row, 5, self._create_output_combo(branch.selected_output_node_id))

    def _add_empty_row(self):
        branch = ConditionBranch()
        branch.condition_operate = ConditionOperate.ALL
        self._add_row(branch)

    def _remove_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    # -- data transfer --

    def set_branches(self, branches: list[ConditionBranch]):
        self.table.setRowCount(0)
        if not branches:
            self._add_empty_row()
            return
        for branch in branches:
            self._add_row(branch)

    def get_branches(self) -> list[ConditionBranch]:
        branches: list[ConditionBranch] = []
        for row in range(self.table.rowCount()):
            input_combo = self.table.cellWidget(row, 0)
            operate_combo = self.table.cellWidget(row, 1)
            property_combo = self.table.cellWidget(row, 2)
            filter_combo = self.table.cellWidget(row, 3)
            value_item = self.table.item(row, 4)
            output_combo = self.table.cellWidget(row, 5)

            prop_name = property_combo.currentText().strip() if property_combo else ""
            if not prop_name:
                continue

            filter_op = filter_combo.currentData() if filter_combo else FilterOperate.EQUALS
            operate = operate_combo.currentData() if operate_combo else ConditionOperate.ALL
            input_id = input_combo.currentData() if input_combo else ""
            output_id = output_combo.currentData() if output_combo else ""

            value_text = value_item.text().strip() if value_item else ""
            # 委托给 PropertyCondition 的值处理逻辑（与 core 的 _str_to_bool / _values_equal 一致）
            value: str | float | int = value_text
            if value_text:
                try:
                    value = int(value_text)
                except ValueError:
                    try:
                        value = float(value_text)
                    except ValueError:
                        from core.conditions import PropertyCondition as PC
                        value = PC._str_to_bool(value_text)

            cond = PropertyCondition(
                property_name=prop_name,
                filter_operate=filter_op,
                value=value,
            )
            branch = ConditionBranch()
            branch.selected_input_node_id = input_id
            branch.selected_output_node_id = output_id
            branch.condition_operate = operate
            branch.conditions = [cond]
            branches.append(branch)
        return branches

    def _test_current_conditions(self):
        presenter = self.node.conditions_presenter
        presenter.load_data(self.node)
        presenter.branches = self.get_branches()

        snapshots = presenter.collect_upstream_snapshots()
        if not snapshots:
            QMessageBox.information(self, "条件测试", "当前没有可用的上游节点。")
            return

        matches = presenter.get_matching_branches(snapshots)
        lines = ["=== 上游节点属性 ==="]
        for node_id, props in snapshots.items():
            lines.append(f"\n节点 [{node_id}]:")
            for k, v in props.items():
                if not k.startswith("mat"):  # 跳过大对象
                    lines.append(f"  {k} = {v}")
        lines.append(f"\n=== 匹配的分支: {len(matches)} 个 ===")
        for b in matches:
            lines.append(f"  → 输出节点 [{b.selected_output_node_id}]")
        if not matches:
            lines.append("  无匹配分支")

        QMessageBox.information(self, "条件测试", "\n".join(lines))

    # -- static entry point --

    @classmethod
    def edit_conditions(cls, node: ConditionNodeData, parent=None) -> ConditionsPresenter | None:
        dialog = cls(node=node, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            presenter = node.conditions_presenter
            presenter.branches = dialog.get_branches()
            return presenter
        return None
