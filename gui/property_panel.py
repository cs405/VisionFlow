"""Property panel - dynamic form editor for node properties.

Ported from H.Controls.Form.PropertyItem + H.Controls.PropertyGrid.
Reads node's Property descriptors and generates appropriate input widgets.
"""

import cv2
import numpy as np
from enum import Enum
from typing import Any

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QFormLayout,
                              QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QComboBox, QLabel, QPushButton, QGroupBox,
                              QHBoxLayout, QFileDialog)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from core.node_base import (
    Property,
    PropertyGroupNames,
    NodeBase,
    VisionNodeData,
    ROINodeData,
    DrawROI,
    InputROI,
    FromROI,
    ConditionNodeData,
    VisionPropertyCondition,
)
from gui.color_picker import ColorPickerDialog
from gui.condition_editor import ConditionEditorDialog
from gui.roi_editor import RoiEditorDialog


class PropertyPanel(QWidget):
    """Right-side panel showing editable properties for the selected node.

    Dynamically generates form widgets based on the node's Property descriptors.
    """

    # Emitted when a property value changes
    property_changed = pyqtSignal(str, object, object)  # name, old_value, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_node: NodeBase | None = None
        self._image_viewer = None
        self._property_widgets: dict[str, QWidget] = {}
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(500)  # 500ms debounce
        self._refresh_timer.timeout.connect(self._do_refresh)
        self._setup_ui()

    def set_image_viewer(self, viewer):
        """Provide the shared image viewer for ROI/color picking workflows."""
        self._image_viewer = viewer

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
        while self._form_layout.count() > 1:
            item = self._form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
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
            prop_map = {name: desc for name, desc in props}
            consumed: set[str] = set()

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

            for suffix, label_text in (("low", "HSV下限"), ("high", "HSV上限")):
                hsv_names = [f"h_{suffix}", f"s_{suffix}", f"v_{suffix}"]
                if all(name in prop_map for name in hsv_names):
                    widget = self._create_hsv_triplet_widget(hsv_names, label_text)
                    if widget is not None:
                        form.addRow(self._make_label(label_text, "HSV 颜色范围编辑器"), widget)
                        consumed.update(hsv_names)

            for prop_name, prop_desc in props:
                if prop_name in consumed:
                    continue
                widget = self._create_widget(prop_name, prop_desc)
                if widget is None:
                    continue

                form.addRow(self._make_label(prop_desc.display_name or prop_name, prop_desc.description), widget)

            self._form_layout.insertWidget(self._form_layout.count() - 1, group_box)

    def _make_label(self, text: str, tooltip: str = "") -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #999; font-size: 11px; font-weight: normal;")
        if tooltip:
            label.setToolTip(tooltip)
        return label

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

        existing = {name for name, _ in result}
        if isinstance(self._current_node, ROINodeData) and "roi" not in existing:
            result.append(("roi", Property(
                None,
                name="ROI范围",
                group=PropertyGroupNames.BASE_PARAMETERS,
                description="设置 ROI 模式与矩形范围",
                order=1000,
            )))
        if isinstance(self._current_node, ConditionNodeData) and "conditions" not in existing:
            result.append(("conditions", Property(
                [],
                name="条件规则",
                group=PropertyGroupNames.RUN_PARAMETERS,
                description="编辑条件分支规则列表",
                order=900,
            )))
        return result

    def _create_widget(self, prop_name: str, prop_desc: Property) -> QWidget | None:
        """Create the appropriate widget for a property based on its type and value."""
        if isinstance(self._current_node, ROINodeData) and prop_name == "roi":
            return self._create_roi_widget()

        if isinstance(self._current_node, ConditionNodeData) and prop_name == "conditions":
            return self._create_condition_widget()

        current_value = getattr(self._current_node, prop_name, prop_desc.default)
        value_type = type(current_value) if current_value is not None else str

        if value_type is bool:
            widget = QCheckBox()
            widget.setChecked(bool(current_value))
            widget.toggled.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setEnabled(False)
            return widget

        elif value_type is int:
            widget = QSpinBox()
            widget.setRange(-999999, 999999)
            widget.setValue(int(current_value or 0))
            widget.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
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
            widget.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
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
                lambda idx, n=prop_name, w=widget: self._set_property_value(n, w.currentData()))
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
                widget.textChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
                if prop_desc.readonly:
                    widget.setReadOnly(True)
                    browse_btn.setEnabled(False)
                return container

            widget.textChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setReadOnly(True)
            return widget

    def _create_hsv_triplet_widget(self, prop_names: list[str], title: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        spin_boxes: dict[str, QSpinBox] = {}
        labels = {prop_names[0]: "H", prop_names[1]: "S", prop_names[2]: "V"}
        preview = QLabel()
        preview.setFixedSize(20, 20)
        preview.setStyleSheet("border: 1px solid #555; border-radius: 2px;")

        def current_hsv() -> tuple[int, int, int]:
            return tuple(spin_boxes[name].value() for name in prop_names)

        def update_preview():
            h, s, v = current_hsv()
            bgr = cv2.cvtColor(np.array([[[h, s, v]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0, 0]
            rgb = (int(bgr[2]), int(bgr[1]), int(bgr[0]))
            preview.setStyleSheet(
                "border: 1px solid #555; border-radius: 2px; background: #{:02X}{:02X}{:02X};".format(*rgb)
            )

        for index, prop_name in enumerate(prop_names):
            text = QLabel(labels[prop_name])
            text.setStyleSheet("color: #999; font-size: 11px;")
            layout.addWidget(text)

            spin = QSpinBox()
            spin.setRange(0, 179 if index == 0 else 255)
            spin.setValue(int(getattr(self._current_node, prop_name, 0)))
            spin.valueChanged.connect(lambda value, n=prop_name: self._set_property_value(n, value))
            spin.valueChanged.connect(lambda _=None: update_preview())
            layout.addWidget(spin)
            spin_boxes[prop_name] = spin

        layout.addWidget(preview)

        pick_btn = QPushButton("选色")
        pick_btn.setFixedHeight(24)

        def pick_color():
            dialog = ColorPickerDialog(viewer=self._image_viewer, parent=self)
            dialog.set_hsv(current_hsv())
            if dialog.exec_() == dialog.Accepted:
                h, s, v = dialog.get_hsv()
                spin_boxes[prop_names[0]].setValue(h)
                spin_boxes[prop_names[1]].setValue(s)
                spin_boxes[prop_names[2]].setValue(v)

        pick_btn.clicked.connect(pick_color)
        layout.addWidget(pick_btn)
        update_preview()
        return container

    def _get_current_image(self):
        if self._image_viewer is not None and getattr(self._image_viewer, "image", None) is not None:
            return self._image_viewer.image
        if isinstance(self._current_node, VisionNodeData):
            if self._current_node.mat is not None:
                return self._current_node.mat
            if isinstance(self._current_node.result_image_source, np.ndarray):
                return self._current_node.result_image_source
        return None

    def _snapshot_roi_value(self, node: ROINodeData) -> dict:
        rect = node.get_active_roi_rect()
        return {
            "mode": type(node.roi).__name__,
            "rect": tuple(rect) if rect else None,
        }

    def _format_roi_text(self, node: ROINodeData) -> str:
        rect = node.get_active_roi_rect()
        if rect is None:
            return f"当前模式: {node.roi.name}（无有效 ROI）"
        x, y, w, h = rect
        return f"当前模式: {node.roi.name} | X={x}, Y={y}, W={w}, H={h}"

    def _update_roi_overlay(self, node: ROINodeData):
        if self._image_viewer is None:
            return
        self._image_viewer.set_roi_rect(node.get_active_roi_rect(), label=node.roi.name if node.roi else "ROI")

    def _create_roi_widget(self) -> QWidget:
        node = self._current_node
        if not isinstance(node, ROINodeData):
            return None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        combo = QComboBox()
        roi_options = node.get_rois()
        for roi in roi_options:
            combo.addItem(roi.name, roi)
        current_index = next((i for i, roi in enumerate(roi_options) if type(roi) is type(node.roi)), 0)
        combo.setCurrentIndex(current_index)
        top.addWidget(combo, 1)

        edit_btn = QPushButton("编辑...")
        edit_btn.setFixedHeight(24)
        top.addWidget(edit_btn)

        summary = QLabel()
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #999; font-size: 11px;")

        layout.addLayout(top)
        layout.addWidget(summary)

        def refresh_state():
            summary.setText(self._format_roi_text(node))
            edit_btn.setEnabled(not isinstance(node.roi, FromROI))
            self._update_roi_overlay(node)

        def change_mode(index: int):
            old_value = self._snapshot_roi_value(node)
            node.roi = roi_options[index]
            self.property_changed.emit("roi", old_value, self._snapshot_roi_value(node))
            refresh_state()

        def edit_roi():
            if isinstance(node.roi, FromROI):
                return
            old_value = self._snapshot_roi_value(node)
            rect = RoiEditorDialog.edit_roi(
                image=self._get_current_image(),
                rect=node.get_active_roi_rect(),
                parent=self,
            )
            if rect is None:
                return

            if isinstance(node.roi, DrawROI):
                node.draw_roi.rect = tuple(rect)
                node.roi = node.draw_roi
            elif isinstance(node.roi, InputROI):
                node.input_roi.x, node.input_roi.y, node.input_roi.width, node.input_roi.height = rect
                node.roi = node.input_roi

            self.property_changed.emit("roi", old_value, self._snapshot_roi_value(node))
            refresh_state()

        combo.currentIndexChanged.connect(change_mode)
        edit_btn.clicked.connect(edit_roi)
        refresh_state()
        self._property_widgets["roi"] = container
        return container

    def _clone_conditions(self, conditions: list[VisionPropertyCondition]) -> list[VisionPropertyCondition]:
        return [VisionPropertyCondition.from_dict(condition.to_dict()) for condition in conditions]

    def _create_condition_widget(self) -> QWidget:
        node = self._current_node
        if not isinstance(node, ConditionNodeData):
            return None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)

        count_label = QLabel()
        count_label.setStyleSheet("color: #999; font-size: 11px;")
        top.addWidget(count_label, 1)

        edit_btn = QPushButton("编辑条件...")
        edit_btn.setFixedHeight(24)
        top.addWidget(edit_btn)

        summary = QLabel()
        summary.setWordWrap(True)
        summary.setStyleSheet("color: #999; font-size: 11px;")

        layout.addLayout(top)
        layout.addWidget(summary)

        def refresh_state():
            count_label.setText(f"已配置 {len(node.conditions)} 条条件")
            if node.conditions:
                summary.setText("\n".join(f"• {condition.display_text()}" for condition in node.conditions[:3]))
            else:
                summary.setText("尚未配置条件规则")

        def edit_conditions():
            old_value = self._clone_conditions(node.conditions)
            conditions = ConditionEditorDialog.edit_conditions(node, parent=self)
            if conditions is None:
                return
            node.conditions = conditions
            self.property_changed.emit("conditions", old_value, self._clone_conditions(node.conditions))
            refresh_state()

        edit_btn.clicked.connect(edit_conditions)
        refresh_state()
        self._property_widgets["conditions"] = container
        return container

    def _browse_file_path(self, line_edit: QLineEdit):
        """Open file browser for a path property."""
        path, _ = QFileDialog.getOpenFileName(self, "选择文件",
                                               line_edit.text(),
                                               "所有文件 (*.*);;图像文件 (*.png *.jpg *.bmp *.tiff)")
        if path:
            line_edit.setText(path)

    def _set_property_value(self, prop_name: str, new_value: Any, *, force: bool = False):
        """Set a property on the current node and emit the panel change signal."""
        if self._current_node is None:
            return
        old_value = getattr(self._current_node, prop_name, None)
        try:
            setattr(self._current_node, prop_name, new_value)
        except Exception:
            pass  # Ignore setting errors
            return

        current_value = getattr(self._current_node, prop_name, None)
        if force or old_value != current_value:
            self.property_changed.emit(prop_name, old_value, current_value)

    def refresh(self):
        """Force refresh of the property display."""
        if self._current_node:
            self._do_refresh()
