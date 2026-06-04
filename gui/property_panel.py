"""Property panel - dynamic form editor for node properties with custom editor registry.

Ported from H.Controls.Form.PropertyItem + H.Controls.PropertyGrid.
Reads node's Property descriptors and generates appropriate input widgets.

Features:
  - Editor registry: property type -> custom editor widget
  - Extended metadata: choices, range bounds, validator, step/decimals
  - Grouped property display with collapsible sections
  - Inline HSV triplet editor for color range properties
  - ROI editor with viewer integration
  - Condition editor for condition nodes
"""

import cv2
import os
import numpy as np
from enum import Enum
from typing import Any, Callable

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QScrollArea, QFormLayout,
                              QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
                              QComboBox, QLabel, QPushButton, QGroupBox,
                              QHBoxLayout, QFileDialog, QSlider, QListWidget)
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
from gui.crop_dialog import CropDialog


# ── Editor Registry ───────────────────────────────────────────────────────

class EditorRegistry:
    """Registry for custom property editors keyed by editor hint or type."""

    def __init__(self):
        self._editors: dict[str, Callable] = {}

    def register(self, editor_hint: str, factory: Callable):
        """Register a custom editor factory.

        Args:
            editor_hint: matches Property.editor field (e.g. "color", "file", "slider")
            factory: callable(parent, prop_name, prop_desc, current_value) -> QWidget
        """
        self._editors[editor_hint] = factory

    def get(self, editor_hint: str) -> Callable | None:
        return self._editors.get(editor_hint)

    def has(self, editor_hint: str) -> bool:
        return editor_hint in self._editors


# Global editor registry
editor_registry = EditorRegistry()


def register_editor(hint: str):
    """Decorator to register a factory as a custom editor."""
    def decorator(func):
        editor_registry.register(hint, func)
        return func
    return decorator


# ── Built-in Custom Editors ────────────────────────────────────────────────

@register_editor("slider")
def _create_slider_editor(parent, prop_name, prop_desc, current_value):
    """Slider + spinbox combo editor."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    slider = QSlider(Qt.Horizontal)
    spin = QSpinBox()

    min_v = prop_desc.min_val if prop_desc.min_val is not None else -999999
    max_v = prop_desc.max_val if prop_desc.max_val is not None else 999999
    slider.setRange(int(min_v), int(max_v))
    spin.setRange(int(min_v), int(max_v))
    slider.setValue(int(current_value or 0))
    spin.setValue(int(current_value or 0))

    slider.valueChanged.connect(spin.setValue)
    spin.valueChanged.connect(slider.setValue)
    layout.addWidget(slider, 1)
    layout.addWidget(spin)

    if prop_desc.readonly:
        slider.setEnabled(False)
        spin.setReadOnly(True)

    return container, slider


@register_editor("choices")
def _create_choices_editor(parent, prop_name, prop_desc, current_value):
    """Dropdown selector for discrete choices."""
    combo = QComboBox(parent)
    choices = prop_desc.choices or []
    for choice in choices:
        combo.addItem(str(choice), choice)

    if isinstance(current_value, str) and current_value in [str(c) for c in choices]:
        combo.setCurrentText(str(current_value))
    elif current_value in choices:
        combo.setCurrentText(str(current_value))

    if prop_desc.readonly:
        combo.setEnabled(False)

    return combo, combo


@register_editor("color")
def _create_color_editor(parent, prop_name, prop_desc, current_value):
    """Color picker button with preview."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    preview = QLabel()
    preview.setFixedSize(24, 24)

    btn = QPushButton("选择颜色...")
    btn.setFixedHeight(24)

    def _update_preview(val):
        try:
            if isinstance(val, str) and val.startswith("#"):
                preview.setStyleSheet(f"border: 1px solid #555; border-radius: 2px; background: {val};")
        except Exception:
            pass

    def _pick():
        # Try custom ColorPickerDialog first (RGB/HSV sync + image sampling)
        try:
            from gui.color_picker import ColorPickerDialog
            initial = current_value or "#FFFFFF"
            if isinstance(initial, str) and initial.startswith("#"):
                r, g, b = int(initial[1:3], 16), int(initial[3:5], 16), int(initial[5:7], 16)
            else:
                r, g, b = 255, 255, 255
            result = ColorPickerDialog.get_color(rgb=(r, g, b), parent=parent)
            if result:
                hex_val = result.get("hex", initial)
                _update_preview(hex_val)
                return
        except Exception:
            pass
        # Fallback: system color dialog
        from PyQt5.QtWidgets import QColorDialog
        from PyQt5.QtGui import QColor
        color = QColorDialog.getColor(parent=parent)
        if color.isValid():
            hex_val = "#{:02X}{:02X}{:02X}".format(color.red(), color.green(), color.blue())
            _update_preview(hex_val)

    btn.clicked.connect(_pick)
    _update_preview(current_value)

    layout.addWidget(preview)
    layout.addWidget(btn, 1)

    if prop_desc.readonly:
        btn.setEnabled(False)

    return container, btn


@register_editor("crop")
def _create_crop_editor(parent, prop_name, prop_desc, current_value):
    """Template crop button that opens CropDialog and sets Base64 result."""
    container = QWidget(parent)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    preview = QLabel("(未设置)")
    preview.setStyleSheet("color: #999; font-size: 11px;")

    btn = QPushButton("裁剪模板...")
    btn.setFixedHeight(24)

    def _crop():
        # Try to get source image from the node or its upstream
        import numpy as np
        from PyQt5.QtWidgets import QApplication
        image = None
        parent_node = getattr(parent, '_current_node', None)
        if parent_node:
            if hasattr(parent_node, 'mat') and parent_node.mat is not None:
                image = parent_node.mat
            elif hasattr(parent_node, 'get_template_image'):
                image = parent_node.get_template_image()
        if image is None:
            # Create a blank placeholder
            image = np.zeros((480, 640, 3), dtype=np.uint8)

        result = CropDialog.crop_image(image, parent=parent)
        if result and result.get("base64"):
            b64 = result["base64"]
            preview.setText(f"✓ {result['rect'][2]}x{result['rect'][3]} px, {len(b64)} chars")
            # Set the base64 value on the node
            if parent_node and hasattr(parent_node, 'base64_string'):
                parent_node.base64_string = b64
                parent_node.set_template_from_image(result["image"])

    btn.clicked.connect(_crop)

    layout.addWidget(preview)
    layout.addWidget(btn)
    if prop_desc.readonly:
        btn.setEnabled(False)
    return container, btn


@register_editor("file_collection")
def _create_file_collection_editor(parent, prop_name, prop_desc, current_value):
    """Multi-file path editor with list display and add/remove buttons."""
    container = QWidget(parent)
    lo = QVBoxLayout(container)
    lo.setContentsMargins(0, 0, 0, 0)
    lo.setSpacing(4)

    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(4)

    label = QLabel(f"{len(current_value) if isinstance(current_value, list) else 0} 个文件")
    label.setStyleSheet("color: #999; font-size: 11px;")
    top.addWidget(label, 1)

    add_btn = QPushButton("添加文件")
    add_btn.setFixedHeight(24)
    top.addWidget(add_btn)

    add_dir_btn = QPushButton("添加文件夹")
    add_dir_btn.setFixedHeight(24)
    top.addWidget(add_dir_btn)

    clr_btn = QPushButton("清空")
    clr_btn.setFixedHeight(24)
    top.addWidget(clr_btn)

    lo.addLayout(top)

    list_w = QListWidget()
    list_w.setMaximumHeight(80)
    list_w.setStyleSheet("QListWidget { background: #333337; border: 1px solid #3f3f46; color: #dcdcdc; font-size: 11px; }")
    lo.addWidget(list_w)

    def _refresh():
        files = getattr(parent._current_node, prop_name, []) if parent._current_node else []
        if not isinstance(files, list):
            files = [files] if files else []
        list_w.clear()
        for f in files:
            list_w.addItem(os.path.basename(str(f)) if isinstance(f, str) else str(f))
        label.setText(f"{len(files)} 个文件")

    def _add():
        from PyQt5.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(parent, "选择文件", "",
                                                  "图像文件 (*.png *.jpg *.bmp *.tiff);;所有文件 (*.*)")
        if paths and parent._current_node:
            existing = list(getattr(parent._current_node, prop_name, []) or [])
            for p in paths:
                if p not in existing:
                    existing.append(p)
            parent._set_property_value(prop_name, existing)
            _refresh()

    def _add_dir():
        from PyQt5.QtWidgets import QFileDialog
        import os as _os
        folder = QFileDialog.getExistingDirectory(parent, "选择文件夹")
        if folder and parent._current_node:
            existing = list(getattr(parent._current_node, prop_name, []) or [])
            for fn in _os.listdir(folder):
                fp = _os.path.join(folder, fn)
                if _os.path.isfile(fp) and fp not in existing:
                    existing.append(fp)
            parent._set_property_value(prop_name, existing)
            _refresh()

    def _clear():
        if parent._current_node:
            parent._set_property_value(prop_name, [])
            _refresh()

    add_btn.clicked.connect(_add)
    add_dir_btn.clicked.connect(_add_dir)
    clr_btn.clicked.connect(_clear)
    _refresh()

    if prop_desc.readonly:
        add_btn.setEnabled(False); add_dir_btn.setEnabled(False); clr_btn.setEnabled(False)

    return container, add_btn


@register_editor("image_selector")
def _create_image_selector_editor(parent, prop_name, prop_desc, current_value):
    """Dropdown selector for available result images."""
    combo = QComboBox(parent)
    combo.addItem("(自动)", None)
    if parent._current_node and hasattr(parent._current_node, 'result_images'):
        for img in parent._current_node.result_images:
            combo.addItem(img.name, img)
    combo.setStyleSheet("QComboBox { background: #333337; color: #dcdcdc; border: 1px solid #3f3f46; padding: 4px 8px; }")
    if prop_desc.readonly:
        combo.setEnabled(False)
    return combo, combo


# ── Property Panel ────────────────────────────────────────────────────────

class PropertyPanel(QWidget):
    """Right-side panel showing editable properties for the selected node.

    Dynamically generates form widgets based on the node's Property descriptors.
    Uses the editor registry to resolve custom editors.
    """

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
        self._image_viewer = viewer

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("  属性面板")
        title.setStyleSheet("""
            QLabel {
                background: #2d2d30; color: #dcdcdc; padding: 8px;
                font-size: 13px; font-weight: bold; border-bottom: 1px solid #3f3f46;
            }
        """)
        layout.addWidget(title)

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

    # ── Node binding ──────────────────────────────────────────────────

    def set_node(self, node: NodeBase | None):
        if node is self._current_node:
            return
        self._current_node = node
        self._refresh_timer.start()

    def _do_refresh(self):
        """Rebuild the property form for the current node."""
        # Clear old widgets
        while self._form_layout.count() > 1:
            item = self._form_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for w in list(self._property_widgets.values()):
            w.deleteLater()
        self._property_widgets.clear()

        if self._current_node is None:
            empty = QLabel("未选择节点\n\n选择工作流中的节点后可编辑参数")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #666; font-size: 12px; padding: 20px;")
            self._form_layout.insertWidget(self._form_layout.count() - 1, empty)
            return

        # Discover properties
        properties = self._discover_properties()

        # Group by property group
        groups: dict[str, list] = {}
        for prop_name, prop_desc in properties:
            group = prop_desc.group or PropertyGroupNames.OTHER_PARAMETERS
            groups.setdefault(group, []).append((prop_name, prop_desc))

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
            props.sort(key=lambda x: x[1].order)
            prop_map = {name: desc for name, desc in props}
            consumed: set[str] = set()

            group_box = QGroupBox(group_name)
            group_box.setStyleSheet("""
                QGroupBox {
                    color: #0078d4; border: 1px solid #3f3f46; border-radius: 3px;
                    margin-top: 10px; padding-top: 14px; font-weight: bold; font-size: 11px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin; left: 8px; padding: 0 4px;
                }
            """)

            form = QFormLayout(group_box)
            form.setLabelAlignment(Qt.AlignLeft)
            form.setContentsMargins(4, 4, 4, 4)
            form.setSpacing(4)

            # HSV triplet detection
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
                form.addRow(
                    self._make_label(prop_desc.display_name or prop_name, prop_desc.description),
                    widget,
                )

            self._form_layout.insertWidget(self._form_layout.count() - 1, group_box)

    def _make_label(self, text: str, tooltip: str = "") -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #999; font-size: 11px; font-weight: normal;")
        if tooltip:
            label.setToolTip(tooltip)
        return label

    def _discover_properties(self) -> list[tuple[str, Property]]:
        result = []
        for cls in type(self._current_node).__mro__:
            if cls is object:
                break
            for name, desc in cls.__dict__.items():
                if isinstance(desc, Property):
                    if name not in [r[0] for r in result]:
                        result.append((name, desc))

        # Inject synthetic properties for special node types
        existing = {name for name, _ in result}
        if isinstance(self._current_node, ROINodeData) and "roi" not in existing:
            result.append(("roi", Property(
                None, name="ROI范围", group=PropertyGroupNames.BASE_PARAMETERS,
                description="设置 ROI 模式与矩形范围", order=1000,
            )))
        if isinstance(self._current_node, ConditionNodeData) and "conditions" not in existing:
            result.append(("conditions", Property(
                [], name="条件规则", group=PropertyGroupNames.RUN_PARAMETERS,
                description="编辑条件分支规则列表", order=900,
            )))
        return result

    # ── Widget Factory ────────────────────────────────────────────────

    def _create_widget(self, prop_name: str, prop_desc: Property) -> QWidget | None:
        """Create the appropriate widget for a property based on its type and editor hint."""

        # Special synthetic properties
        if isinstance(self._current_node, ROINodeData) and prop_name == "roi":
            return self._create_roi_widget()
        if isinstance(self._current_node, ConditionNodeData) and prop_name == "conditions":
            return self._create_condition_widget()

        current_value = getattr(self._current_node, prop_name, prop_desc.default)

        # Check for custom editor hint
        if prop_desc.editor and editor_registry.has(prop_desc.editor):
            widget, control = editor_registry.get(prop_desc.editor)(
                self, prop_name, prop_desc, current_value)
            self._wire_control(control, widget, prop_name, prop_desc, current_value)
            return widget

        value_type = type(current_value) if current_value is not None else str

        # Boolean
        if value_type is bool:
            widget = QCheckBox()
            widget.setChecked(bool(current_value))
            widget.toggled.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setEnabled(False)
            return widget

        # Integer
        elif value_type is int:
            widget = QSpinBox()
            min_v = int(prop_desc.min_val) if prop_desc.min_val is not None else -999999
            max_v = int(prop_desc.max_val) if prop_desc.max_val is not None else 999999
            widget.setRange(min_v, max_v)
            widget.setValue(int(current_value or 0))
            widget.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setReadOnly(True)
            return widget

        # Float
        elif value_type is float:
            widget = QDoubleSpinBox()
            min_v = float(prop_desc.min_val) if prop_desc.min_val is not None else -999999.0
            max_v = float(prop_desc.max_val) if prop_desc.max_val is not None else 999999.0
            widget.setRange(min_v, max_v)
            widget.setDecimals(prop_desc.decimals)
            widget.setSingleStep(prop_desc.step)
            widget.setValue(float(current_value or 0.0))
            widget.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setReadOnly(True)
            return widget

        # Enum
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

        # List
        elif isinstance(current_value, list):
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

        # String / other
        else:
            widget = QLineEdit()
            widget.setText(str(current_value or ""))

            # File path detection
            is_path = any(kw in prop_name.lower() for kw in ["path", "file", "src", "dir", "folder"])

            if is_path and not prop_desc.readonly:
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
                return container

            widget.textChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
            self._property_widgets[prop_name] = widget
            if prop_desc.readonly:
                widget.setReadOnly(True)
            return widget

    def _wire_control(self, control, container, prop_name, prop_desc, current_value):
        """Wire a custom editor's control to the property system."""
        self._property_widgets[prop_name] = container
        if isinstance(control, QSpinBox):
            control.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
        elif isinstance(control, QDoubleSpinBox):
            control.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
        elif isinstance(control, QCheckBox):
            control.toggled.connect(lambda v, n=prop_name: self._set_property_value(n, v))
        elif isinstance(control, QComboBox):
            control.currentIndexChanged.connect(
                lambda idx, n=prop_name, c=control: self._set_property_value(n, c.currentData() or c.currentText()))
        elif isinstance(control, QLineEdit):
            control.textChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))
        elif isinstance(control, QSlider):
            control.valueChanged.connect(lambda v, n=prop_name: self._set_property_value(n, v))

        # Validation feedback
        if prop_desc.validator and isinstance(control, (QLineEdit, QSpinBox, QDoubleSpinBox)):
            def _validate(val=None, ctrl=control, vfn=prop_desc.validator):
                ok, msg = vfn(val if val is not None else (
                    ctrl.value() if hasattr(ctrl, 'value') else ctrl.text()))
                style = "border: 1px solid #3f3f46;" if ok else "border: 1px solid #f44336;"
                if isinstance(ctrl, QLineEdit):
                    ctrl.setStyleSheet(f"background: #333337; color: #dcdcdc; {style} padding: 4px 8px;")
                if not ok:
                    ctrl.setToolTip(msg)
            if isinstance(control, QLineEdit):
                control.textChanged.connect(_validate)
            elif isinstance(control, (QSpinBox, QDoubleSpinBox)):
                control.valueChanged.connect(_validate)

    # ── HSV Triplet ───────────────────────────────────────────────────

    def _create_hsv_triplet_widget(self, prop_names: list[str], title: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        spin_boxes: dict[str, QSpinBox] = {}
        labels_map = {prop_names[0]: "H", prop_names[1]: "S", prop_names[2]: "V"}
        preview = QLabel()
        preview.setFixedSize(20, 20)
        preview.setStyleSheet("border: 1px solid #555; border-radius: 2px;")

        def current_hsv():
            return tuple(spin_boxes[name].value() for name in prop_names)

        def update_preview():
            h, s, v = current_hsv()
            bgr = cv2.cvtColor(np.array([[[h, s, v]]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0, 0]
            rgb = (int(bgr[2]), int(bgr[1]), int(bgr[0]))
            preview.setStyleSheet(
                "border: 1px solid #555; border-radius: 2px; background: #{:02X}{:02X}{:02X};".format(*rgb))

        for idx, pn in enumerate(prop_names):
            text = QLabel(labels_map[pn])
            text.setStyleSheet("color: #999; font-size: 11px;")
            layout.addWidget(text)

            spin = QSpinBox()
            spin.setRange(0, 179 if idx == 0 else 255)
            spin.setValue(int(getattr(self._current_node, pn, 0)))
            spin.valueChanged.connect(lambda value, n=pn: self._set_property_value(n, value))
            spin.valueChanged.connect(lambda _=None: update_preview())
            layout.addWidget(spin)
            spin_boxes[pn] = spin

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

    # ── ROI Widget ────────────────────────────────────────────────────

    def _get_current_image(self):
        if self._image_viewer is not None and getattr(self._image_viewer, "image", None) is not None:
            return self._image_viewer.image
        if isinstance(self._current_node, VisionNodeData):
            if self._current_node.mat is not None:
                return self._current_node.mat
            if isinstance(self._current_node._result_image_source, np.ndarray):
                return self._current_node._result_image_source
        return None

    def _snapshot_roi_value(self, node: ROINodeData) -> dict:
        rect = node.get_active_roi_rect()
        return {"mode": type(node.roi).__name__, "rect": tuple(rect) if rect else None}

    def _format_roi_text(self, node: ROINodeData) -> str:
        rect = node.get_active_roi_rect()
        if rect is None:
            return f"当前模式: {node.roi.name}（无有效 ROI）"
        x, y, w, h = rect
        return f"当前模式: {node.roi.name} | X={x}, Y={y}, W={w}, H={h}"

    def _update_roi_overlay(self, node: ROINodeData):
        if self._image_viewer is None:
            return
        self._image_viewer.set_roi_rect(node.get_active_roi_rect(),
                                         label=node.roi.name if node.roi else "ROI")

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

    # ── Condition Widget ──────────────────────────────────────────────

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
                summary.setText("\n".join(
                    f"• {condition.display_text()}" for condition in node.conditions[:3]))
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

    # ── Helpers ───────────────────────────────────────────────────────

    def _browse_file_path(self, line_edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", line_edit.text(),
            "所有文件 (*.*);;图像文件 (*.png *.jpg *.bmp *.tiff)")
        if path:
            line_edit.setText(path)

    def _set_property_value(self, prop_name: str, new_value: Any, *, force: bool = False):
        if self._current_node is None:
            return
        old_value = getattr(self._current_node, prop_name, None)
        try:
            setattr(self._current_node, prop_name, new_value)
        except Exception:
            return
        current_value = getattr(self._current_node, prop_name, None)
        if force or old_value != current_value:
            self.property_changed.emit(prop_name, old_value, current_value)

    def flash_highlight(self):
        """Briefly flash the first GroupBox border to draw attention (WPF ShowViewCommand feedback).

        Finds the first QGroupBox in the form layout and cycles its border color
        from #0078d4 (accent blue) → #ff9800 (alert orange) → #0078d4 over ~500ms.
        """
        from PyQt5.QtCore import QPropertyAnimation, QTimer
        # Find the first group box
        first_group = None
        for i in range(self._form_layout.count()):
            w = self._form_layout.itemAt(i).widget()
            if isinstance(w, QGroupBox):
                first_group = w
                break
        if first_group is None:
            return

        original = first_group.styleSheet()
        # Flash: set bright accent border, then restore after 300ms
        flash_style = (
            "QGroupBox {"
            "color: #ff9800; border: 2px solid #ff9800; border-radius: 3px;"
            "margin-top: 10px; padding-top: 14px; font-weight: bold; font-size: 11px;"
            "}"
            "QGroupBox::title {"
            "subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #ff9800;"
            "}"
        )
        first_group.setStyleSheet(flash_style)
        QTimer.singleShot(350, lambda: first_group.setStyleSheet(original))

    def refresh(self):
        """Force refresh of the property display."""
        if self._current_node:
            self._do_refresh()
