"""ROI editor dialog - rectangle, rotated rectangle, and circle ROI types.

Ported from WPF H.Controls.ROIBox (rect/rotated-rect/circle drawing).
Provides canvas-based region selection with numeric fine-tuning controls
and three ROI shape types.
"""

from __future__ import annotations

import math

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QPushButton, QDialogButtonBox, QWidget, QFormLayout, QComboBox,
    QStackedWidget,
)

from gui.image_viewer import ImageViewer


_ROI_TYPE_RECT = "矩形"
_ROI_TYPE_ROTATED = "旋转矩形"
_ROI_TYPE_CIRCLE = "圆形"


class RoiEditorDialog(QDialog):
    """ROI editor supporting rectangle, rotated rectangle, and circle shapes.

    Mirrors WPF ROIBox with rectangular, rotated-rect, and circle ROI types.
    """

    def __init__(self, image: np.ndarray | None = None,
                 rect: tuple[int, int, int, int] | None = None,
                 roi_type: str = _ROI_TYPE_RECT,
                 angle: float = 0.0,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROI 编辑器")
        self.resize(960, 680)
        self._image = image
        self._updating = False
        self._roi_type = roi_type

        self.viewer = ImageViewer(self)
        self.viewer.set_image(image)
        self.viewer.roi_picked.connect(self._on_viewer_roi_picked)

        # Rectangle controls
        self._x_spin = QSpinBox()
        self._y_spin = QSpinBox()
        self._w_spin = QSpinBox()
        self._h_spin = QSpinBox()

        # Rotated rect extras
        self._angle_spin = QDoubleSpinBox()
        self._cx_spin = QSpinBox()
        self._cy_spin = QSpinBox()

        # Circle controls
        self._circ_cx = QSpinBox()
        self._circ_cy = QSpinBox()
        self._radius_spin = QSpinBox()

        self._setup_ui()
        self._set_spin_ranges(image)

        if rect:
            self.set_rect(rect, angle)
        else:
            self._use_full_image()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        tip = QLabel("选择ROI类型并用鼠标在图像上框选，或通过右侧面板微调数值。")
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.viewer, 2)

        # Right side controls
        side = QWidget()
        side.setFixedWidth(280)
        side_lo = QVBoxLayout(side)
        side_lo.setContentsMargins(0, 0, 0, 0)
        side_lo.setSpacing(8)

        # ROI type selector
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("类型:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems([_ROI_TYPE_RECT, _ROI_TYPE_ROTATED, _ROI_TYPE_CIRCLE])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        type_row.addWidget(self._type_combo, 1)
        side_lo.addLayout(type_row)

        # Stacked parameter panels
        self._param_stack = QStackedWidget()
        self._param_stack.addWidget(self._build_rect_panel())
        self._param_stack.addWidget(self._build_rotated_panel())
        self._param_stack.addWidget(self._build_circle_panel())
        side_lo.addWidget(self._param_stack)

        # Action buttons
        btn_row = QHBoxLayout()
        full_btn = QPushButton("整图")
        full_btn.clicked.connect(self._use_full_image)
        btn_row.addWidget(full_btn)
        pick_btn = QPushButton("框选")
        pick_btn.clicked.connect(lambda: self.viewer.set_roi_pick_mode(True))
        btn_row.addWidget(pick_btn)
        center_btn = QPushButton("居中正方形")
        center_btn.clicked.connect(self._center_square)
        btn_row.addWidget(center_btn)
        side_lo.addLayout(btn_row)

        side_lo.addStretch()
        body.addWidget(side)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.viewer.set_roi_pick_mode(True)
        self._param_stack.setCurrentIndex(0)

    def _build_rect_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        for label, spin in [("X", self._x_spin), ("Y", self._y_spin),
                             ("宽度", self._w_spin), ("高度", self._h_spin)]:
            spin.valueChanged.connect(self._on_rect_changed)
            form.addRow(label, spin)
        return w

    def _build_rotated_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        for label, spin in [("中心X", self._cx_spin), ("中心Y", self._cy_spin),
                             ("宽度", self._w_spin), ("高度", self._h_spin)]:
            spin.valueChanged.connect(self._on_rotated_changed)
            form.addRow(label, spin)
        self._angle_spin.setRange(-180.0, 180.0)
        self._angle_spin.setValue(0.0)
        self._angle_spin.setDecimals(1)
        self._angle_spin.setSingleStep(1.0)
        self._angle_spin.valueChanged.connect(self._on_rotated_changed)
        form.addRow("旋转角°", self._angle_spin)
        return w

    def _build_circle_panel(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        for label, spin in [("中心X", self._circ_cx), ("中心Y", self._circ_cy),
                             ("半径", self._radius_spin)]:
            spin.valueChanged.connect(self._on_circle_changed)
            form.addRow(label, spin)
        return w

    def _set_spin_ranges(self, image: np.ndarray | None):
        if image is None:
            return
        h, w = image.shape[:2]
        max_dim = max(w, h)
        for spin in (self._x_spin, self._y_spin, self._cx_spin, self._cy_spin,
                      self._circ_cx, self._circ_cy):
            spin.setRange(0, max_dim)
        for spin in (self._w_spin, self._h_spin):
            spin.setRange(1, max_dim)
        self._radius_spin.setRange(1, max_dim)

    def _clamp_rect(self, r: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x, y, w, h = [max(0, int(v)) for v in r]
        if self._image is None:
            return x, y, max(1, w), max(1, h)
        iw, ih = self._image.shape[1], self._image.shape[0]
        x = min(x, iw - 1)
        y = min(y, ih - 1)
        w = max(1, min(w, iw - x))
        h = max(1, min(h, ih - y))
        return x, y, w, h

    def set_rect(self, rect: tuple[int, int, int, int], angle: float = 0.0):
        self._updating = True
        x, y, w, h = self._clamp_rect(rect)
        self._x_spin.setValue(x); self._y_spin.setValue(y)
        self._w_spin.setValue(w); self._h_spin.setValue(h)
        self._cx_spin.setValue(x + w // 2); self._cy_spin.setValue(y + h // 2)
        self._circ_cx.setValue(x + w // 2); self._circ_cy.setValue(y + h // 2)
        self._radius_spin.setValue(min(w, h) // 2)
        self._angle_spin.setValue(angle)
        self._updating = False
        self.viewer.set_roi_rect((x, y, w, h))

    def get_rect(self) -> tuple[int, int, int, int]:
        if self._roi_type == _ROI_TYPE_CIRCLE:
            cx, cy, r = self._circ_cx.value(), self._circ_cy.value(), self._radius_spin.value()
            r = max(1, r)
            return (cx - r, cy - r, r * 2, r * 2)
        return self._clamp_rect((
            self._x_spin.value(), self._y_spin.value(),
            self._w_spin.value(), self._h_spin.value()))

    def get_roi_data(self) -> dict:
        """Get full ROI data including type and rotation."""
        return {
            "type": self._roi_type,
            "rect": self.get_rect(),
            "angle": self._angle_spin.value() if self._roi_type == _ROI_TYPE_ROTATED else 0.0,
            "center": (
                self._cx_spin.value() if self._roi_type == _ROI_TYPE_ROTATED
                else self._circ_cx.value() if self._roi_type == _ROI_TYPE_CIRCLE
                else self._x_spin.value() + self._w_spin.value() // 2,
                self._cy_spin.value() if self._roi_type == _ROI_TYPE_ROTATED
                else self._circ_cy.value() if self._roi_type == _ROI_TYPE_CIRCLE
                else self._y_spin.value() + self._h_spin.value() // 2,
            ),
        }

    def _on_rect_changed(self):
        if self._updating: return
        r = self.get_rect()
        self.viewer.set_roi_rect(r)
        self._cx_spin.setValue(r[0] + r[2] // 2); self._cy_spin.setValue(r[1] + r[3] // 2)

    def _on_rotated_changed(self):
        if self._updating: return
        cx, cy, w, h = self._cx_spin.value(), self._cy_spin.value(), self._w_spin.value(), self._h_spin.value()
        x, y = cx - w // 2, cy - h // 2
        self.viewer.set_roi_rect((x, y, w, h))

    def _on_circle_changed(self):
        if self._updating: return
        r = self.get_rect()
        self.viewer.set_roi_rect(r)

    def _on_type_changed(self, roi_type: str):
        self._roi_type = roi_type
        idx_map = {_ROI_TYPE_RECT: 0, _ROI_TYPE_ROTATED: 1, _ROI_TYPE_CIRCLE: 2}
        self._param_stack.setCurrentIndex(idx_map.get(roi_type, 0))
        self.set_rect(self.get_rect())

    def _on_viewer_roi_picked(self, rect: tuple[int, int, int, int]):
        self.set_rect(rect)
        self.viewer.set_roi_pick_mode(False)

    def _use_full_image(self):
        if self._image is not None:
            h, w = self._image.shape[:2]
            self.set_rect((0, 0, w, h))

    def _center_square(self):
        if self._image is not None:
            h, w = self._image.shape[:2]
            sz = min(w, h)
            self.set_rect(((w - sz) // 2, (h - sz) // 2, sz, sz))

    @classmethod
    def edit_roi(cls, image: np.ndarray | None,
                 rect: tuple[int, int, int, int] | None = None,
                 parent=None) -> tuple[int, int, int, int] | None:
        dialog = cls(image=image, rect=rect, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_rect()
        return None
