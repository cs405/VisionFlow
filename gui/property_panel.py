"""
属性面板 - 显示和编辑选中节点的参数
严格解耦：只通过EventBus与Core层通信
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QScrollArea,
    QLabel, QSpinBox, QDoubleSpinBox, QSlider, QComboBox,
    QLineEdit, QCheckBox, QPushButton, QGroupBox, QHBoxLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from core.events import EventBus, Event, EventType
from core.node_base import ParamType


class PropertyPanel(QWidget):
    """
    属性面板
    显示当前选中节点的参数，支持动态生成控件
    """

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.current_node_id = None
        self.current_node_metadata = {}
        self.param_widgets = {}  # 参数名 -> 控件映射

        self.setMinimumWidth(280)
        self.setMaximumWidth(350)

        # 订阅事件
        self._subscribe_events()

        # 创建UI
        self._setup_ui()

        # 初始状态
        self.clear()

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.NODE_SELECTED, self._on_node_selected)
        self.event_bus.subscribe(EventType.NODE_PARAM_CHANGED, self._on_param_changed_from_core)
        self.event_bus.subscribe(EventType.WORKFLOW_NODE_REMOVED, self._on_node_removed)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏
        self.title_widget = QWidget()
        self.title_widget.setStyleSheet("""
            QWidget {
                background-color: #2D2D2D;
                border-bottom: 1px solid #3D3D3D;
            }
        """)
        title_layout = QHBoxLayout(self.title_widget)
        title_layout.setContentsMargins(10, 8, 10, 8)

        self.title_label = QLabel("属性面板")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #E0E0E0;")
        title_layout.addWidget(self.title_label)

        layout.addWidget(self.title_widget)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1E1E1E;
            }
        """)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(10)

        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)

        self.setLayout(layout)

    def _on_node_selected(self, event: Event):
        """节点选中事件"""
        self.current_node_id = event.data.get("node_id")
        self.current_node_metadata = event.data.get("node_metadata", {})
        self._rebuild_form()

    def _on_param_changed_from_core(self, event: Event):
        """Core层参数变化事件"""
        node_id = event.data.get("node_id")
        param_name = event.data.get("param_name")
        new_value = event.data.get("new_value")

        if node_id == self.current_node_id:
            self._update_ui_value(param_name, new_value)

    def _on_node_removed(self, event: Event):
        """节点删除事件"""
        node_id = event.data.get("node_id")
        if node_id == self.current_node_id:
            self.clear()

    def _rebuild_form(self):
        """重建表单"""
        # 清空现有内容
        self._clear_layout(self.content_layout)
        self.param_widgets.clear()

        if not self.current_node_id:
            # 显示空状态
            empty_label = QLabel("未选中节点\n\n请点击画布中的节点查看属性")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #808080; padding: 20px;")
            self.content_layout.addWidget(empty_label)
            self.title_label.setText("属性面板")
            return

        # 更新标题
        node_name = self.current_node_metadata.get("name", "未知节点")
        self.title_label.setText(f"属性面板 - {node_name}")

        # 节点信息分组
        info_group = QGroupBox("节点信息")
        info_layout = QFormLayout(info_group)
        info_layout.setSpacing(8)

        info_layout.addRow("ID:", QLabel(self.current_node_id[:12] + "..."))
        info_layout.addRow("类型:", QLabel(self.current_node_metadata.get("name", "未知")))
        info_layout.addRow("分类:", QLabel(self.current_node_metadata.get("category", "通用")))

        description = self.current_node_metadata.get("description", "")
        if description:
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #A0A0A0; font-size: 10px;")
            info_layout.addRow("描述:", desc_label)

        self.content_layout.addWidget(info_group)

        # 参数分组
        parameters = self.current_node_metadata.get("parameters", [])
        if parameters:
            param_group = QGroupBox("参数设置")
            param_layout = QFormLayout(param_group)
            param_layout.setSpacing(8)

            for param in parameters:
                param_name = param.get("name")
                param_label = param.get("label", param_name)
                param_type = param.get("type")
                default_value = param.get("default")

                # 获取当前值（从metadata或使用默认值）
                current_value = self.current_node_metadata.get("param_values", {}).get(param_name, default_value)

                # 创建控件
                control = self._create_control(param, current_value)
                if control:
                    self.param_widgets[param_name] = control
                    param_layout.addRow(f"{param_label}:", control)

            self.content_layout.addWidget(param_group)

        # 添加弹性空间
        self.content_layout.addStretch()

    def _create_control(self, param: dict, current_value):
        """根据参数类型创建控件"""
        param_type = param.get("type")
        param_name = param.get("name")

        if param_type in ["int", ParamType.INT.value, ParamType.SLIDER.value]:
            spin = QSpinBox()
            if param.get("min") is not None:
                spin.setMinimum(param.get("min"))
            if param.get("max") is not None:
                spin.setMaximum(param.get("max"))
            if param.get("step"):
                spin.setSingleStep(param.get("step"))
            spin.setValue(int(current_value) if current_value else 0)
            spin.valueChanged.connect(lambda v, n=param_name: self._on_param_changed(n, v))
            return spin

        elif param_type in ["float", ParamType.FLOAT.value, ParamType.FLOAT_SLIDER.value]:
            spin = QDoubleSpinBox()
            if param.get("min") is not None:
                spin.setMinimum(param.get("min"))
            if param.get("max") is not None:
                spin.setMaximum(param.get("max"))
            if param.get("step"):
                spin.setSingleStep(param.get("step"))
            spin.setValue(float(current_value) if current_value else 0.0)
            spin.valueChanged.connect(lambda v, n=param_name: self._on_param_changed(n, v))
            return spin

        elif param_type in ["bool", ParamType.BOOL.value]:
            check = QCheckBox()
            check.setChecked(bool(current_value))
            check.toggled.connect(lambda v, n=param_name: self._on_param_changed(n, v))
            return check

        elif param_type in ["enum", ParamType.ENUM.value]:
            combo = QComboBox()
            options = param.get("options", [])
            combo.addItems(options)
            if str(current_value) in options:
                combo.setCurrentText(str(current_value))
            combo.currentTextChanged.connect(lambda v, n=param_name: self._on_param_changed(n, v))
            return combo

        elif param_type in ["str", ParamType.STRING.value]:
            edit = QLineEdit(str(current_value) if current_value else "")
            edit.textChanged.connect(lambda v, n=param_name: self._on_param_changed(n, v))
            return edit

        else:
            label = QLabel(str(current_value))
            return label

    def _on_param_changed(self, param_name: str, value):
        """参数改变 - 发送事件到Core层"""
        if self.current_node_id:
            self.event_bus.emit(Event(
                type=EventType.NODE_PARAM_CHANGE_REQUEST,
                data={
                    "node_id": self.current_node_id,
                    "param_name": param_name,
                    "value": value
                }
            ))

    def _update_ui_value(self, param_name: str, value):
        """更新UI中的参数值"""
        widget = self.param_widgets.get(param_name)
        if not widget:
            return

        # 根据控件类型更新值
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

    def _clear_layout(self, layout):
        """清空布局"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def set_current_node(self, node_id: str, node_metadata: dict):
        """设置当前节点（供外部调用）"""
        self.current_node_id = node_id
        self.current_node_metadata = node_metadata
        self._rebuild_form()

    def update_param_value(self, node_id: str, param_name: str, value):
        """更新参数值（供外部调用）"""
        if node_id == self.current_node_id:
            self._update_ui_value(param_name, value)

    def clear(self):
        """清空面板"""
        self.current_node_id = None
        self.current_node_metadata = {}
        self._rebuild_form()