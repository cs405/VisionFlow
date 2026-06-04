"""Template crop dialog - ROI-based image cropping for template creation.

Ported from WPF Base64MatchingNodeData.CropImagePresenter.
Lets the user select a region on the source image and extracts it as a
template image that can be used directly or converted to base64 for
template matching nodes.
"""

import base64
from io import BytesIO

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialogButtonBox, QWidget, QFormLayout, QSpinBox, QTextEdit,
    QMessageBox, QComboBox,
)
from PyQt5.QtGui import QPixmap, QImage

from gui.image_viewer import ImageViewer


class CropDialog(QDialog):
    """Crop a region from an image for use as a template in matching nodes.

    Supports rectangular ROI selection on the image viewer, with
    numeric fine-tuning controls for X/Y/Width/Height.
    """

    def __init__(self, image: np.ndarray | None = None,
                 rect: tuple[int, int, int, int] | None = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("模板裁剪器")
        self.resize(960, 680)
        self._image = image
        self._updating = False
        self._cropped: np.ndarray | None = None

        self.viewer = ImageViewer(self)
        self.viewer.set_image(image)
        self.viewer.roi_picked.connect(self._on_viewer_roi_picked)

        self._x_spin = QSpinBox()
        self._y_spin = QSpinBox()
        self._w_spin = QSpinBox()
        self._h_spin = QSpinBox()
        self._preview_label = QLabel()
        self._base64_output = QTextEdit()
        self._size_label = QLabel("尺寸: -")

        self._setup_ui()
        self._set_spin_ranges(image)
        if rect:
            self.set_rect(rect)
        else:
            self._use_full_image()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        tip = QLabel("在图像上拖拽选择模板区域，使用「框选」按钮激活选区模式，或用右侧数值微调。")
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        body = QHBoxLayout()
        body.setSpacing(12)

        # Left: image viewer
        body.addWidget(self.viewer, 2)

        # Right: controls
        side = QWidget()
        side.setFixedWidth(280)
        form = QFormLayout(side)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)

        spin_style = "QSpinBox { padding: 3px; }"
        for label, spin in [("X", self._x_spin), ("Y", self._y_spin),
                             ("宽度", self._w_spin), ("高度", self._h_spin)]:
            spin.setStyleSheet(spin_style)
            spin.valueChanged.connect(self._on_spin_rect_changed)
            form.addRow(label, spin)

        # Buttons
        btn_row = QHBoxLayout()
        full_btn = QPushButton("整图")
        full_btn.clicked.connect(self._use_full_image)
        btn_row.addWidget(full_btn)

        pick_btn = QPushButton("框选")
        pick_btn.clicked.connect(lambda: self.viewer.set_roi_pick_mode(True))
        btn_row.addWidget(pick_btn)

        center_btn = QPushButton("居中1:1")
        center_btn.clicked.connect(self._center_square)
        btn_row.addWidget(center_btn)
        form.addRow("", self._wrap(btn_row))

        # Preview
        form.addRow("预览", self._preview_label)
        self._preview_label.setFixedSize(120, 120)
        self._preview_label.setStyleSheet("border: 1px solid #555; background: #1e1e1e;")
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setText("(无预览)")

        form.addRow(QLabel(""), self._size_label)
        self._size_label.setStyleSheet("color: #999; font-size: 11px;")

        body.addWidget(side)
        layout.addLayout(body, 1)

        # Base64 output section
        layout.addWidget(QLabel("Base64 编码 (复制到模板匹配节点):"))
        self._base64_output.setReadOnly(True)
        self._base64_output.setFixedHeight(80)
        self._base64_output.setStyleSheet("background: #1e1e1e; color: #dcdcdc; border: 1px solid #505050; font-family: monospace; font-size: 11px;")
        self._base64_output.setPlaceholderText("裁剪后将自动生成 Base64 编码...")
        layout.addWidget(self._base64_output)

        # Copy button row
        copy_row = QHBoxLayout()
        copy_btn = QPushButton("复制 Base64")
        copy_btn.clicked.connect(self._copy_base64)
        copy_row.addWidget(copy_btn)

        preview_btn = QPushButton("预览裁剪结果")
        preview_btn.clicked.connect(self._preview_crop)
        copy_row.addWidget(preview_btn)
        copy_row.addStretch()
        layout.addLayout(copy_row)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.viewer.set_roi_pick_mode(True)

    def _wrap(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget(); w.setLayout(layout); return w

    def _set_spin_ranges(self, image: np.ndarray | None):
        if image is None:
            return
        h, w = image.shape[:2]
        for spin in (self._x_spin, self._y_spin):
            spin.setRange(0, max(w, h))
        for spin in (self._w_spin, self._h_spin):
            spin.setRange(1, max(w, h))

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

    def set_rect(self, rect: tuple[int, int, int, int]):
        x, y, w, h = self._clamp_rect(rect)
        self._updating = True
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._w_spin.setValue(w)
        self._h_spin.setValue(h)
        self._updating = False
        self.viewer.set_roi_rect((x, y, w, h))
        self._update_crop()

    def get_rect(self) -> tuple[int, int, int, int]:
        return self._clamp_rect((
            self._x_spin.value(), self._y_spin.value(),
            self._w_spin.value(), self._h_spin.value()))

    def get_cropped_image(self) -> np.ndarray | None:
        return self._cropped

    def get_base64(self) -> str:
        if self._cropped is None:
            return ""
        _, buf = cv2.imencode(".png", self._cropped)
        return base64.b64encode(buf).decode("ascii")

    def _update_crop(self):
        if self._image is None:
            return
        x, y, w, h = self.get_rect()
        if w <= 0 or h <= 0:
            return
        self._cropped = self._image[y:y+h, x:x+w].copy()
        self._size_label.setText(f"尺寸: {w} x {h} px")
        self._update_base64_output()
        self._scale_preview(self._cropped)

    def _update_base64_output(self):
        b64 = self.get_base64()
        if b64:
            preview = b64[:80] + "..." if len(b64) > 80 else b64
            self._base64_output.setText(preview)
            self._base64_output.setToolTip(f"长度: {len(b64)} 字符")
        else:
            self._base64_output.clear()

    def _scale_preview(self, img: np.ndarray):
        h, w = img.shape[:2]
        max_sz = 120
        scale = min(max_sz / w, max_sz / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)
        if nw <= 0 or nh <= 0:
            return
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        resized = cv2.resize(rgb, (nw, nh))
        h_bytes = resized.tobytes()
        qimg = QImage(h_bytes, nw, nh, nw * 3, QImage.Format_RGB888)
        self._preview_label.setPixmap(QPixmap.fromImage(qimg).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_spin_rect_changed(self):
        if self._updating:
            return
        self.viewer.set_roi_rect(self.get_rect())
        self._update_crop()

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
            x = (w - sz) // 2
            y = (h - sz) // 2
            self.set_rect((x, y, sz, sz))

    def _preview_crop(self):
        if self._cropped is not None:
            cv2.imshow("裁剪预览 (按任意键关闭)", self._cropped)
            cv2.waitKey(0)
            cv2.destroyWindow("裁剪预览 (按任意键关闭)")

    def _copy_base64(self):
        b64 = self.get_base64()
        if b64:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(b64)
            QMessageBox.information(self, "已复制", f"Base64 编码已复制到剪贴板 ({len(b64)} 字符)")

    def _on_accept(self):
        self._update_crop()
        if self._cropped is None:
            QMessageBox.warning(self, "提示", "请先选择裁剪区域")
            return
        self.accept()

    @classmethod
    def crop_image(cls, image: np.ndarray | None,
                   rect: tuple[int, int, int, int] | None = None,
                   parent=None) -> dict | None:
        """Open crop dialog and return cropped image data.

        Returns:
            dict with keys: 'image' (ndarray), 'base64' (str), 'rect' (tuple)
            or None if cancelled.
        """
        dialog = cls(image=image, rect=rect, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return {
                "image": dialog.get_cropped_image(),
                "base64": dialog.get_base64(),
                "rect": dialog.get_rect(),
            }
        return None
