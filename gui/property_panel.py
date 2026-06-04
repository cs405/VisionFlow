"""Property panel - dynamic form editor for node properties.

Ported from H.Controls.Form.PropertyItem + H.Controls.PropertyGrid.
Reads node's Property descriptors and generates appropriate input widgets.
"""

from enum import Enum
from typing import Any

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QFormLayout,
                              QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QComboBox, QLabel, QPushButton, QGroupBox,
                              QHBoxLayout, QFileDialog, QSlider, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from core.node_base import Property, PropertyGroupNames, NodeBase, VisionNodeData, ROINodeData


class PropertyPanel(QWidget):
    """Right-side panel showing editable properties for the selected node.

    Dynamically generates form widgets based on the node's Property descriptors.
    """

    # Emitted when a property value changes
    property_changed = pyqtSignal(str, object, object)  # name, old_value, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_node: NodeBase | None = None
        self._property_widgets: dict[str, QWidget] = {}
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(500)  # 500ms debounce
        self._refresh_timer.timeout.connect(self._do_refresh)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title
        title = QLabel("  属性面板")
        title.setStyleSheet("""
            QLabel {
                background: #2d2d30;
                color: #dcdcdc;
                padding: 8px;
                font-size: 13px;
                font-weight: bold;
                border-bottom: 1px solid #3f3f46;
            }
        """)
        layout.addWidget(title)

        # Scroll area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: #252526; border: none; }")

        self._form_widget = QWidget()
        self._form_layout = QVBoxLayout(self._form_widget)
        self._form_layout.setContentsMargins(8, 4, 8, 4)
        self._form_layout.setSpacing(0)
        self._form_layout.addStretch()

        scroll.setWidget(self._form_widget)
        layout.addWidget(scroll)

    # -- Node binding --

    def set_node(self, node: NodeBase | None):
        """Set the current node to display properties for."""
        if node is self._current_node:
            return
        self._current_node = node
        self._refresh_timer.start()

    def _do_refresh(self):
        """Rebuild the property form for the current node."""
        # Clear existing
        for group in list(self._form_layout.children()):
            if isinstance(group, QGroupBox):
                self._form_layout.removeWidget(group)
                group.deleteLater()
        for w in list(self._property_widgets.values()):
            w.deleteLater()
        self._property_widgets.clear()

        if self._current_node is None:
            # Show empty state
            empty = QLabel("未选择节点\n\n选择工作流中的节点后可编辑参数")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #666; font-size: 12px; padding: 20px;")
            self._form_layout.insertWidget(self._form_layout.count() - 1, empty)
            return

        # Find all Property descriptors on the node's class
        properties = self._discover_properties()

        # Group properties by their 'group' attribute
        groups: dict[str, list] = {}
        for prop_name, prop_desc in properties:
            group = prop_desc.group or PropertyGroupNames.OTHER_PARAMETERS
            groups.setdefault(group, []).append((prop_name, prop_desc))

        # Sort groups in standard order
        group_order = [
            PropertyGroupNames.BASE_PARAMETERS,
            PropertyGroupNames.RUN_PARAMETERS,
            PropertyGroupNames.FLOW_PARAMETERS,
            PropertyGroupNames.DISPLAY_PARAMETERS,
            PropertyGroupNames.RESULT_PARAMETERS,
            PropertyGroupNames.OTHER_PARAMETERS,
        ]

        for group_name in group_order:
            props = groups.get(group_name, [])
            if not props:
                continue
            # Sort by order
            props.sort(key=lambda x: x[1].order)

            group_box = QGroupBox(group_name)
            group_box.setStyleSheet("""
                QGroupBox {
                    color: #0078d4;
                    border: 1px solid #3f3f46;
                    border-radius: 3px;
                    margin-top: 10px;
                    padding-top: 14px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 8px;
                    padding: 0 4px;
                }
            """)

            form = QFormLayout(group_box)
            form.setLabelAlignment(Qt.AlignLeft)
            form.setContentsMargins(4, 4, 4, 4)
            form.setSpacing(4)

            for prop_name, prop_desc in props:
                widget = self._create_widget(prop_name, prop_desc)
                if widget is None:
                    continue

                label = QLabel(prop_desc.display_name or prop_name)
                label.setStyleSheet("color: #999; font-size: 11px; font-weight: normal;")
                if prop_desc.description:
                    label.setToolTip(prop_desc.description)

                form.addRow(label, widget)

            self._form_layout.insertWidget(self._form_layout.count() - 1, group_box)

    def _discover_properties(self) -> list[tuple[str, Property]]:
        """Discover all Property descriptors on the current node's class hierarchy."""
        result = []
        for cls in type(self._current_node).__mro__:
            if cls is object:
                break
            for name, desc in cls.__dict__.items():
                if isinstance(desc, Property):
                    # Avoid duplicates from parent classes
                    if name not in [r[0] for r in result]:
                        result.append((name, desc))
        return result

    def _create_widget(self, prop_name: str, prop_desc: Property) -> QWidget | None:
        """Create the appropriate widget for a property based on its type and value."""
        current_value = getattr(self._current_node, prop_name, prop_desc.default)
        value_type = type(current_value) if current_value is not None else str

        if value_type is bool:
            widget = QCheckBox()
            widget.setChecked(bool(current_value))
            widget.toggled.connect(lambda v, n=prop_name: self._on_value_changed(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setEnabled(False)
            return widget

        elif value_type is int:
            widget = QSpinBox()
            widget.setRange(-999999, 999999)
            widget.setValue(int(current_value or 0))
            widget.valueChanged.connect(lambda v, n=prop_name: self._on_value_changed(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setReadOnly(True)
            return widget

        elif value_type is float:
            widget = QDoubleSpinBox()
            widget.setRange(-999999.0, 999999.0)
            widget.setDecimals(3)
            widget.setSingleStep(0.1)
            widget.setValue(float(current_value or 0.0))
            widget.valueChanged.connect(lambda v, n=prop_name: self._on_value_changed(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setReadOnly(True)
            return widget

        elif isinstance(current_value, Enum):
            widget = QComboBox()
            enum_type = type(current_value)
            for member in enum_type:
                widget.addItem(member.value, member)
            widget.setCurrentText(current_value.value if current_value else "")
            widget.currentIndexChanged.connect(
                lambda idx, n=prop_name, w=widget: self._on_value_changed(n, w.currentData()))
            self._property_widgets[prop_name] = widget
            return widget

        elif isinstance(current_value, list):
            # List - show as readonly text with count
            container = QWidget()
            hbox = QHBoxLayout(container)
            hbox.setContentsMargins(0, 0, 0, 0)

            label = QLabel(f"[{len(current_value)} 项]")
            label.setStyleSheet("color: #999; font-size: 11px;")
            hbox.addWidget(label)

            if not prop_desc.readonly:
                btn = QPushButton("...")
                btn.setFixedWidth(30)
                btn.setFixedHeight(22)
                hbox.addWidget(btn)

            self._property_widgets[prop_name] = container
            return container

        else:
            # String or other - use QLineEdit
            widget = QLineEdit()
            widget.setText(str(current_value or ""))

            if "path" in prop_name.lower() or "file" in prop_name.lower() or "src" in prop_name.lower():
                # File path: add browse button
                container = QWidget()
                hbox = QHBoxLayout(container)
                hbox.setContentsMargins(0, 0, 0, 0)
                hbox.setSpacing(2)
                hbox.addWidget(widget)

                browse_btn = QPushButton("...")
                browse_btn.setFixedWidth(28)
                browse_btn.setFixedHeight(22)
                browse_btn.clicked.connect(lambda _, w=widget: self._browse_file_path(w))
                hbox.addWidget(browse_btn)

                self._property_widgets[prop_name] = container
                widget.textChanged.connect(lambda v, n=prop_name: self._on_value_changed(n, v))
                if prop_desc.readonly:
                    widget.setReadOnly(True)
                    browse_btn.setEnabled(False)
                return container

            widget.textChanged.connect(lambda v, n=prop_name: self._on_value_changed(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setReadOnly(True)
            return widget

    def _browse_file_path(self, line_edit: QLineEdit):
        """Open file browser for a path property."""
        path, _ = QFileDialog.getOpenFileName(self, "选择文件",
                                               line_edit.text(),
                                               "所有文件 (*.*);;图像文件 (*.png *.jpg *.bmp *.tiff)")
        if path:
            line_edit.setText(path)

    def _on_value_changed(self, prop_name: str, new_value: Any):
        """Handle a property value change from the UI."""
        if self._current_node is None:
            return
        old_value = getattr(self._current_node, prop_name, None)
        try:
            setattr(self._current_node, prop_name, new_value)
            self.property_changed.emit(prop_name, old_value, new_value)
        except Exception:
            pass  # Ignore setting errors

    def refresh(self):
        """Force refresh of the property display."""
        if self._current_node:
            self._do_refresh()
