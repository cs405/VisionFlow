"""Condition editor dialog for ConditionNodeData rules."""

from __future__ import annotations

from PyQt5.QtCore import Qt
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
    QWidget,
)

from core.node_base import ConditionNodeData, VisionPropertyCondition


class ConditionEditorDialog(QDialog):
    """Edit a list of VisionPropertyCondition entries for a condition node."""

    HEADERS = ("属性", "操作符", "比较值", "输出分支")

    def __init__(self, node: ConditionNodeData, parent=None):
        super().__init__(parent)
        self.node = node
        self.setWindowTitle("条件编辑器")
        self.resize(820, 420)

        self._candidate_properties = [name for name, _ in node.get_condition_candidates()]
        self._output_nodes = [("默认", "")]
        self._output_nodes.extend((n.name or n.node_id, n.node_id) for n in node.to_node_datas)

        self._setup_ui()
        self.set_conditions(node.conditions)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        tip = QLabel("条件表达式按“上游节点名.结果属性”评估；比较值支持数字、文本、布尔文本。")
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
        add_btn = QPushButton("添加条件")
        add_btn.clicked.connect(self.add_empty_row)
        tool_row.addWidget(add_btn)

        remove_btn = QPushButton("删除选中")
        remove_btn.clicked.connect(self.remove_selected_rows)
        tool_row.addWidget(remove_btn)

        test_btn = QPushButton("测试当前结果")
        test_btn.clicked.connect(self._test_current_conditions)
        tool_row.addWidget(test_btn)

        tool_row.addStretch()
        layout.addLayout(tool_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_property_combo(self, current_text: str = "") -> QComboBox:
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems(self._candidate_properties)
        combo.setCurrentText(current_text)
        return combo

    def _create_operator_combo(self, current_text: str = ">") -> QComboBox:
        combo = QComboBox()
        combo.addItems(list(VisionPropertyCondition.SUPPORTED_OPERATORS))
        combo.setCurrentText(current_text if current_text in VisionPropertyCondition.SUPPORTED_OPERATORS else ">")
        return combo

    def _create_output_combo(self, output_node_id: str = "") -> QComboBox:
        combo = QComboBox()
        for label, node_id in self._output_nodes:
            combo.addItem(label, node_id)
        index = combo.findData(output_node_id)
        combo.setCurrentIndex(index if index >= 0 else 0)
        return combo

    def add_row(self, condition: VisionPropertyCondition | None = None):
        condition = condition or VisionPropertyCondition()
        row = self.table.rowCount()
        self.table.insertRow(row)

        property_combo = self._create_property_combo(condition.property_name)
        operator_combo = self._create_operator_combo(condition.operator)
        output_combo = self._create_output_combo(condition.output_node_id)

        value_item = QTableWidgetItem(str(condition.threshold if condition.threshold is not None else ""))

        self.table.setCellWidget(row, 0, property_combo)
        self.table.setCellWidget(row, 1, operator_combo)
        self.table.setItem(row, 2, value_item)
        self.table.setCellWidget(row, 3, output_combo)

    def add_empty_row(self):
        default_property = self._candidate_properties[0] if self._candidate_properties else ""
        self.add_row(VisionPropertyCondition(property_name=default_property))

    def remove_selected_rows(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def set_conditions(self, conditions: list[VisionPropertyCondition]):
        self.table.setRowCount(0)
        if not conditions:
            self.add_empty_row()
            return
        for condition in conditions:
            self.add_row(condition)

    def get_conditions(self) -> list[VisionPropertyCondition]:
        conditions: list[VisionPropertyCondition] = []
        for row in range(self.table.rowCount()):
            property_combo = self.table.cellWidget(row, 0)
            operator_combo = self.table.cellWidget(row, 1)
            output_combo = self.table.cellWidget(row, 3)
            value_item = self.table.item(row, 2)

            property_name = property_combo.currentText().strip() if property_combo else ""
            operator = operator_combo.currentText().strip() if operator_combo else ">"
            threshold = value_item.text().strip() if value_item else ""
            output_node_id = output_combo.currentData() if output_combo else ""

            if not property_name:
                continue

            conditions.append(VisionPropertyCondition(
                property_name=property_name,
                operator=operator,
                threshold=threshold,
                output_node_id=output_node_id or "",
            ))
        return conditions

    def _test_current_conditions(self):
        snapshot = self.node.collect_upstream_results()
        conditions = self.get_conditions()
        matches = [cond for cond in conditions if cond.evaluate(snapshot)]

        if not snapshot:
            QMessageBox.information(self, "条件测试", "当前没有可用的上游结果值。")
            return

        details = "\n".join(f"- {k} = {v}" for k, v in snapshot.items())
        matched = "\n".join(f"- {c.display_text()}" for c in matches) or "无匹配条件"
        QMessageBox.information(
            self,
            "条件测试",
            f"上游结果:\n{details}\n\n匹配结果:\n{matched}",
        )

    @classmethod
    def edit_conditions(cls, node: ConditionNodeData, parent=None) -> list[VisionPropertyCondition] | None:
        dialog = cls(node=node, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_conditions()
        return None

