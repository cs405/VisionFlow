"""ROI editor dialog for selecting and refining rectangular regions."""

from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QFormLayout,
)

from gui.image_viewer import ImageViewer


class RoiEditorDialog(QDialog):
    """Simple rectangular ROI editor with canvas selection and numeric controls."""

    def __init__(self, image: np.ndarray | None = None,
                 rect: tuple[int, int, int, int] | None = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROI 编辑器")
        self.resize(900, 640)
        self._image = image
        self._updating = False

        self.viewer = ImageViewer(self)
        self.viewer.set_image(image)
        self.viewer.roi_picked.connect(self._on_viewer_roi_picked)

        self._x_spin = QSpinBox()
        self._y_spin = QSpinBox()
        self._w_spin = QSpinBox()
        self._h_spin = QSpinBox()

        self._setup_ui()
        self._set_spin_ranges(image)
        self.set_rect(rect or self._default_rect(image))

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        tip = QLabel("拖拽图像可重新框选 ROI；也可直接修改右侧数值。")
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        body = QHBoxLayout()
        body.setSpacing(10)
        body.addWidget(self.viewer, 1)

        side = QWidget()
        side.setFixedWidth(240)
        form = QFormLayout(side)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)

        for spin in (self._x_spin, self._y_spin, self._w_spin, self._h_spin):
            spin.valueChanged.connect(self._on_spin_rect_changed)

        form.addRow("X", self._x_spin)
        form.addRow("Y", self._y_spin)
        form.addRow("宽度", self._w_spin)
        form.addRow("高度", self._h_spin)

        button_row = QHBoxLayout()
        full_btn = QPushButton("整图")
        full_btn.clicked.connect(self._use_full_image)
        button_row.addWidget(full_btn)

        pick_btn = QPushButton("框选")
        pick_btn.clicked.connect(lambda: self.viewer.set_roi_pick_mode(True))
        button_row.addWidget(pick_btn)
        form.addRow("", self._wrap_layout(button_row))

        body.addWidget(side)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.viewer.set_roi_pick_mode(True)

    def _wrap_layout(self, layout: QHBoxLayout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _set_spin_ranges(self, image: np.ndarray | None):
        width = int(image.shape[1]) if image is not None else 99999
        height = int(image.shape[0]) if image is not None else 99999

        self._x_spin.setRange(0, max(0, width))
        self._y_spin.setRange(0, max(0, height))
        self._w_spin.setRange(0, max(0, width))
        self._h_spin.setRange(0, max(0, height))

    def _default_rect(self, image: np.ndarray | None) -> tuple[int, int, int, int]:
        if image is None:
            return (0, 0, 100, 100)
        h, w = image.shape[:2]
        return (0, 0, w, h)

    def _clamp_rect(self, rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        x, y, w, h = [max(0, int(v)) for v in rect]
        if self._image is None:
            return x, y, w, h

        max_w = int(self._image.shape[1])
        max_h = int(self._image.shape[0])
        x = min(x, max_w)
        y = min(y, max_h)
        w = min(w, max(0, max_w - x))
        h = min(h, max(0, max_h - y))
        return x, y, w, h

    def set_rect(self, rect: tuple[int, int, int, int]):
        x, y, w, h = self._clamp_rect(rect)
        self._updating = True
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._w_spin.setValue(w)
        self._h_spin.setValue(h)
        self._updating = False
        self.viewer.set_roi_rect((x, y, w, h))

    def get_rect(self) -> tuple[int, int, int, int]:
        return self._clamp_rect((
            self._x_spin.value(),
            self._y_spin.value(),
            self._w_spin.value(),
            self._h_spin.value(),
        ))

    def _on_spin_rect_changed(self):
        if self._updating:
            return
        self.viewer.set_roi_rect(self.get_rect())

    def _on_viewer_roi_picked(self, rect: tuple[int, int, int, int]):
        self.set_rect(rect)
        self.viewer.set_roi_pick_mode(False)

    def _use_full_image(self):
        self.set_rect(self._default_rect(self._image))

    @classmethod
    def edit_roi(cls, image: np.ndarray | None,
                 rect: tuple[int, int, int, int] | None = None,
                 parent=None) -> tuple[int, int, int, int] | None:
        dialog = cls(image=image, rect=rect, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_rect()
        return None

