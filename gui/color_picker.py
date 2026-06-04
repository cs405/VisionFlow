"""Color picker dialog with RGB/HSV sync and optional image sampling."""

from __future__ import annotations

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
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
    QLineEdit,
    QColorDialog,
)


class ColorPickerDialog(QDialog):
    """Pick a color using RGB/HSV controls or sample from an ImageViewer."""

    def __init__(self, rgb: tuple[int, int, int] = (255, 255, 255), viewer=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("颜色选择器")
        self.resize(420, 320)
        self._viewer = viewer
        self._updating = False

        self._r = QSpinBox()
        self._g = QSpinBox()
        self._b = QSpinBox()
        self._h = QSpinBox()
        self._s = QSpinBox()
        self._v = QSpinBox()
        self._hex_edit = QLineEdit()
        self._preview = QLabel()
        self._pick_button = QPushButton("从图像取色")

        self._setup_ui()
        self.set_rgb(rgb)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        tip = QLabel("支持 RGB / OpenCV HSV 联动；若当前预览区有图像，可直接点击取色。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        content = QHBoxLayout()
        content.setSpacing(12)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setLabelAlignment(Qt.AlignLeft)

        for spin in (self._r, self._g, self._b, self._s, self._v):
            spin.setRange(0, 255)
        self._h.setRange(0, 179)

        self._r.valueChanged.connect(self._on_rgb_changed)
        self._g.valueChanged.connect(self._on_rgb_changed)
        self._b.valueChanged.connect(self._on_rgb_changed)
        self._h.valueChanged.connect(self._on_hsv_changed)
        self._s.valueChanged.connect(self._on_hsv_changed)
        self._v.valueChanged.connect(self._on_hsv_changed)

        form.addRow("R", self._r)
        form.addRow("G", self._g)
        form.addRow("B", self._b)
        form.addRow("H", self._h)
        form.addRow("S", self._s)
        form.addRow("V", self._v)

        self._hex_edit.setReadOnly(True)
        form.addRow("HEX", self._hex_edit)

        controls = QHBoxLayout()
        sys_btn = QPushButton("系统颜色")
        sys_btn.clicked.connect(self._pick_system_color)
        controls.addWidget(sys_btn)

        self._pick_button.clicked.connect(self._start_pick_from_viewer)
        controls.addWidget(self._pick_button)
        form.addRow("", self._wrap_layout(controls))

        content.addWidget(form_widget, 1)

        preview_box = QVBoxLayout()
        preview_title = QLabel("预览")
        preview_title.setStyleSheet("font-weight: bold;")
        preview_box.addWidget(preview_title)

        self._preview.setFixedSize(120, 120)
        self._preview.setStyleSheet("border: 1px solid #555; border-radius: 4px;")
        preview_box.addWidget(self._preview, alignment=Qt.AlignTop | Qt.AlignHCenter)
        preview_box.addStretch()
        content.addLayout(preview_box)

        layout.addLayout(content)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._pick_button.setEnabled(self._viewer is not None)

    def _wrap_layout(self, layout: QHBoxLayout) -> QWidget:
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _rgb_to_hsv(self, rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        bgr = np.array([[[rgb[2], rgb[1], rgb[0]]]], dtype=np.uint8)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0]
        return int(hsv[0]), int(hsv[1]), int(hsv[2])

    def _hsv_to_rgb(self, hsv: tuple[int, int, int]) -> tuple[int, int, int]:
        bgr = cv2.cvtColor(np.array([[hsv]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0, 0]
        return int(bgr[2]), int(bgr[1]), int(bgr[0])

    def set_rgb(self, rgb: tuple[int, int, int]):
        rgb = tuple(max(0, min(255, int(v))) for v in rgb)
        hsv = self._rgb_to_hsv(rgb)
        self._updating = True
        self._r.setValue(rgb[0])
        self._g.setValue(rgb[1])
        self._b.setValue(rgb[2])
        self._h.setValue(hsv[0])
        self._s.setValue(hsv[1])
        self._v.setValue(hsv[2])
        self._updating = False
        self._update_preview()

    def set_hsv(self, hsv: tuple[int, int, int]):
        hsv = (
            max(0, min(179, int(hsv[0]))),
            max(0, min(255, int(hsv[1]))),
            max(0, min(255, int(hsv[2]))),
        )
        rgb = self._hsv_to_rgb(hsv)
        self._updating = True
        self._r.setValue(rgb[0])
        self._g.setValue(rgb[1])
        self._b.setValue(rgb[2])
        self._h.setValue(hsv[0])
        self._s.setValue(hsv[1])
        self._v.setValue(hsv[2])
        self._updating = False
        self._update_preview()

    def get_rgb(self) -> tuple[int, int, int]:
        return self._r.value(), self._g.value(), self._b.value()

    def get_hsv(self) -> tuple[int, int, int]:
        return self._h.value(), self._s.value(), self._v.value()

    def get_color_data(self) -> dict:
        return {
            "rgb": self.get_rgb(),
            "hsv": self.get_hsv(),
            "hex": self._hex_edit.text(),
        }

    def _on_rgb_changed(self):
        if self._updating:
            return
        self.set_rgb(self.get_rgb())

    def _on_hsv_changed(self):
        if self._updating:
            return
        self.set_hsv(self.get_hsv())

    def _update_preview(self):
        rgb = self.get_rgb()
        hex_value = "#{:02X}{:02X}{:02X}".format(*rgb)
        self._hex_edit.setText(hex_value)
        self._preview.setStyleSheet(
            f"border: 1px solid #555; border-radius: 4px; background: {hex_value};"
        )

    def _pick_system_color(self):
        color = QColorDialog.getColor(QColor(*self.get_rgb()), self, "选择颜色")
        if color.isValid():
            self.set_rgb((color.red(), color.green(), color.blue()))

    def _start_pick_from_viewer(self):
        if self._viewer is None:
            return
        self._viewer.color_picked.connect(self._on_viewer_color_picked)
        self._viewer.set_color_pick_mode(True)
        self._pick_button.setText("点击预览区取色…")
        self._pick_button.setEnabled(False)

    def _stop_pick_from_viewer(self):
        if self._viewer is None:
            return
        try:
            self._viewer.color_picked.disconnect(self._on_viewer_color_picked)
        except TypeError:
            pass
        self._viewer.set_color_pick_mode(False)
        self._pick_button.setText("从图像取色")
        self._pick_button.setEnabled(True)

    def _on_viewer_color_picked(self, payload: dict):
        self.set_rgb(tuple(payload.get("rgb", self.get_rgb())))
        self._stop_pick_from_viewer()

    def closeEvent(self, event):
        self._stop_pick_from_viewer()
        super().closeEvent(event)

    @classmethod
    def get_color(cls, rgb: tuple[int, int, int] = (255, 255, 255), viewer=None, parent=None) -> dict | None:
        dialog = cls(rgb=rgb, viewer=viewer, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_color_data()
        return None

