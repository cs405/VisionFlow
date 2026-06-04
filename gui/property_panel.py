"""
属性面板 - 显示和编辑选中节点的参数
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QScrollArea,
    QLabel, QSpinBox, QDoubleSpinBox, QSlider, QComboBox,
    QLineEdit, QCheckBox, QPushButton, QGroupBox
)
from PySide6.QtCore import Qt, Signal

from core.node_base import NodeBase, ParamType
from core.events import EventBus, Event, EventType


class PropertyPanel(QWidget):
    """属性面板"""

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.current_node: NodeBase = None

        self.setMinimumWidth(250)
        self.setMaximumWidth(350)

        # 布局
        layout = QVBoxLayout()

        # 标题
        self.title_label = QLabel("属性面板")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(self.title_label)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        self.content_widget = QWidget()
        self.form_layout = QFormLayout(self.content_widget)
        self.form_layout.setSpacing(10)

        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)

        self.setLayout(layout)

        # 订阅事件
        self._subscribe_events()

        self.clear()

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.NODE_SELECTED, self._on_node_selected)
        self.event_bus.subscribe(EventType.NODE_PARAM_CHANGED, self._on_param_changed)

    def _on_node_selected(self, event: Event):
        """节点选中事件"""
        node_id = event.data.get("node_id")
        workflow = self._get_workflow()

        if workflow:
            self.current_node = workflow.get_node(node_id)
            self._rebuild_form()

    def _on_param_changed(self, event: Event):
        """参数变化事件"""
        if self.current_node and event.data.get("node_id") == self.current_node.node_id:
            # 更新UI中的值
            self._update_ui_value(
                event.data.get("param_name"),
                event.data.get("new_value")
            )

    def _get_workflow(self):
        """获取工作流实例（通过事件总线间接获取）"""
        # 简化实现：直接返回None，实际应该通过主窗口获取
        # 更好的做法是通过事件系统请求
        return getattr(self, '_workflow', None)

    def set_workflow(self, workflow):
        """设置工作流引用"""
        self._workflow = workflow

    def _rebuild_form(self):
        """重建表单"""
        # 清空现有控件
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.current_node:
            self.title_label.setText("未选中节点")
            return

        # 设置标题
        self.title_label.setText(f"节点属性: {self.current_node.name}")

        # 添加节点信息
        info_group = QGroupBox("节点信息")
        info_layout = QFormLayout(info_group)
        info_layout.addRow("ID:", QLabel(self.current_node.node_id[:8] + "..."))
        info_layout.addRow("类型:", QLabel(self.current_node.__class__.__name__))
        info_layout.addRow("分类:", QLabel(self.current_node.category))

        if self.current_node.description:
            info_layout.addRow("描述:", QLabel(self.current_node.description))

        self.form_layout.addRow(info_group)

        # 添加参数控件
        if self.current_node.parameters:
            param_group = QGroupBox("参数设置")
            param_layout = QFormLayout(param_group)

            for name, param in self.current_node.parameters.items():
                value = self.current_node.get_param(name)
                control = self._create_control(param, value)
                if control:
                    param_layout.addRow(f"{param.label}:", control)

            self.form_layout.addRow(param_group)

    def _create_control(self, param, value):
        """创建参数控件"""
        if param.type in [ParamType.INT, ParamType.SLIDER]:
            spin = QSpinBox()
            if param.min is not None:
                spin.setMinimum(param.min)
            if param.max is not None:
                spin.setMaximum(param.max)
            if param.step:
                spin.setSingleStep(param.step)
            spin.setValue(int(value))
            spin.valueChanged.connect(lambda v, n=param.name: self._on_param_changed_ui(n, v))
            return spin

        elif param.type in [ParamType.FLOAT, ParamType.FLOAT_SLIDER]:
            spin = QDoubleSpinBox()
            if param.min is not None:
                spin.setMinimum(param.min)
            if param.max is not None:
                spin.setMaximum(param.max)
            if param.step:
                spin.setSingleStep(param.step)
            spin.setValue(float(value))
            spin.valueChanged.connect(lambda v, n=param.name: self._on_param_changed_ui(n, v))
            return spin

        elif param.type == ParamType.BOOL:
            check = QCheckBox()
            check.setChecked(bool(value))
            check.toggled.connect(lambda v, n=param.name: self._on_param_changed_ui(n, v))
            return check

        elif param.type == ParamType.ENUM:
            combo = QComboBox()
            if param.options:
                combo.addItems(param.options)
            if str(value) in param.options:
                combo.setCurrentText(str(value))
            combo.currentTextChanged.connect(lambda v, n=param.name: self._on_param_changed_ui(n, v))
            return combo

        elif param.type == ParamType.STRING:
            edit = QLineEdit(str(value))
            edit.textChanged.connect(lambda v, n=param.name: self._on_param_changed_ui(n, v))
            return edit

        else:
            label = QLabel(str(value))
            return label

    def _on_param_changed_ui(self, param_name: str, value):
        """UI参数改变"""
        if self.current_node:
            self.current_node.set_param(param_name, value)

    def _update_ui_value(self, param_name: str, value):
        """更新UI中的参数值"""
        # 遍历表单查找对应控件并更新
        for i in range(self.form_layout.rowCount()):
            item = self.form_layout.itemAt(i, QFormLayout.FieldRole)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, QSpinBox):
                    widget.blockSignals(True)
                    widget.setValue(int(value))
                    widget.blockSignals(False)
                elif isinstance(widget, QDoubleSpinBox):
                    widget.blockSignals(True)
                    widget.setValue(float(value))
                    widget.blockSignals(False)
                elif isinstance(widget, QCheckBox):
                    widget.blockSignals(True)
                    widget.setChecked(bool(value))
                    widget.blockSignals(False)
                elif isinstance(widget, QComboBox):
                    widget.blockSignals(True)
                    widget.setCurrentText(str(value))
                    widget.blockSignals(False)
                elif isinstance(widget, QLineEdit):
                    widget.blockSignals(True)
                    widget.setText(str(value))
                    widget.blockSignals(False)

    def clear(self):
        """清空面板"""
        self.current_node = None
        self._rebuild_form()