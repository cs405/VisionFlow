"""模板裁剪对话框 - 基于ROI的图像裁剪用于模板创建。

让用户在源图像上选择区域并将其提取为模板图像，
该模板图像可以直接使用或转换为base64用于模板匹配节点。
支持矩形、旋转矩形和圆形三种选区类型。
"""

import base64

import cv2
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialogButtonBox, QWidget, QFormLayout, QSpinBox, QDoubleSpinBox,
    QTextEdit, QMessageBox, QComboBox, QInputDialog,
)
from PyQt5.QtGui import QPixmap, QImage

from gui.image_viewer import ImageViewer
from gui.widget_utils import set_spin_ranges_from_image, clamp_rect_to_image


_ROI_TYPE_RECT = "矩形"
_ROI_TYPE_ROTATED = "旋转矩形"
_ROI_TYPE_CIRCLE = "圆形"


class CropDialog(QDialog):
    """从图像中裁剪区域用于匹配节点中的模板。

    支持矩形、旋转矩形和圆形ROI选择，
    并提供数值微调控件。
    """

    def __init__(self, image: np.ndarray | None = None,
                 rect: tuple[int, int, int, int] | None = None,
                 roi_type: str = _ROI_TYPE_RECT,
                 angle: float = 0.0,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("模板裁剪器")
        self.resize(960, 680)
        self._image = image
        self._updating = False
        self._roi_type = roi_type
        self._cropped: np.ndarray | None = None

        self.viewer = ImageViewer(self)
        self.viewer.set_image(image)
        self.viewer.roi_picked.connect(self._on_viewer_roi_picked)
        self.viewer.roi_moved.connect(self._on_viewer_roi_moved)

        # 矩形控件
        self._x_spin = QSpinBox()
        self._y_spin = QSpinBox()
        self._w_spin = QSpinBox()
        self._h_spin = QSpinBox()

        # 旋转矩形额外控件
        self._angle_spin = QDoubleSpinBox()
        self._angle_spin.setRange(-180.0, 180.0)
        self._angle_spin.setValue(0.0)
        self._angle_spin.setDecimals(1)
        self._angle_spin.setSingleStep(1.0)
        self._cx_spin = QSpinBox()
        self._cy_spin = QSpinBox()

        # 圆形控件
        self._circ_cx = QSpinBox()
        self._circ_cy = QSpinBox()
        self._radius_spin = QSpinBox()

        # 预览标签
        self._preview_label = QLabel()
        self._base64_output = QTextEdit()
        self._size_label = QLabel("尺寸: -")

        # 统一连接所有 spin 信号
        for s in [self._x_spin, self._y_spin, self._w_spin, self._h_spin,
                  self._cx_spin, self._cy_spin, self._circ_cx, self._circ_cy, self._radius_spin]:
            s.valueChanged.connect(self._on_any_spin_changed)
        self._angle_spin.valueChanged.connect(self._on_any_spin_changed)

        self._setup_ui()
        if roi_type != _ROI_TYPE_RECT:
            self._type_combo.setCurrentText(roi_type)
        self._updating = True
        self._set_spin_ranges(image)
        self._updating = False

        if rect:
            self.set_rect(rect, angle)

    def _setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        tip = QLabel("在图像上拖拽选择模板区域，使用「框选」按钮激活选区模式，或用右侧数值微调。")
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.viewer, 2)

        # 右侧控件区域
        side = QWidget()
        side.setFixedWidth(280)
        side_lo = QVBoxLayout(side)
        side_lo.setContentsMargins(0, 0, 0, 0)
        side_lo.setSpacing(8)

        # ROI类型选择器
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("类型:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems([_ROI_TYPE_RECT, _ROI_TYPE_ROTATED, _ROI_TYPE_CIRCLE])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        type_row.addWidget(self._type_combo, 1)
        side_lo.addLayout(type_row)

        # 参数面板（切类型时重建行）
        self._param_panel = QWidget()
        self._param_form = QFormLayout(self._param_panel)
        self._param_form.setContentsMargins(0, 0, 0, 0)
        self._param_form.setSpacing(6)
        self._rebuild_param_panel()
        side_lo.addWidget(self._param_panel)

        # 动作按钮行
        btn_row = QHBoxLayout()
        full_btn = QPushButton("整图")
        full_btn.clicked.connect(self._use_full_image)
        btn_row.addWidget(full_btn)
        pick_btn = QPushButton("框选")
        pick_btn.clicked.connect(lambda: (self.viewer.clear_roi_rect(), self.viewer.set_roi_pick_mode(True)))
        btn_row.addWidget(pick_btn)
        center_btn = QPushButton("居中1:1")
        center_btn.clicked.connect(self._center_square)
        btn_row.addWidget(center_btn)
        side_lo.addLayout(btn_row)

        # 保存模板按钮
        save_btn = QPushButton("保存模板")
        save_btn.setStyleSheet(
            "QPushButton { background: #1a5a1a; color: #66ff66; border: 1px solid #383;"
            "border-radius: 2px; padding: 4px 12px; }"
            "QPushButton:hover { background: #2a7a2a; }"
        )
        save_btn.clicked.connect(self._save_template)
        side_lo.addWidget(save_btn)

        # 预览区域
        side_lo.addWidget(QLabel("预览"))
        self._preview_label.setFixedSize(120, 120)
        self._preview_label.setStyleSheet("border: 1px solid #555; background: #1e1e1e;")
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setText("(无预览)")
        side_lo.addWidget(self._preview_label)

        side_lo.addWidget(QLabel(""))
        self._size_label.setStyleSheet("color: #999; font-size: 11px;")
        side_lo.addWidget(self._size_label)

        side_lo.addStretch()
        body.addWidget(side)
        layout.addLayout(body, 1)

        # Base64输出部分
        layout.addWidget(QLabel("Base64 编码 (复制到模板匹配节点):"))
        self._base64_output.setReadOnly(True)
        self._base64_output.setFixedHeight(80)
        self._base64_output.setStyleSheet("background: #1e1e1e; color: #dcdcdc; border: 1px solid #505050; font-family: monospace; font-size: 11px;")
        self._base64_output.setPlaceholderText("裁剪后将自动生成 Base64 编码...")
        layout.addWidget(self._base64_output)

        # 复制按钮行
        copy_row = QHBoxLayout()
        copy_btn = QPushButton("复制 Base64")
        copy_btn.clicked.connect(self._copy_base64)
        copy_row.addWidget(copy_btn)
        preview_btn = QPushButton("预览裁剪结果")
        preview_btn.clicked.connect(self._preview_crop)
        copy_row.addWidget(preview_btn)
        copy_row.addStretch()
        layout.addLayout(copy_row)

        # 对话框按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 默认启用ROI拾取模式
        self.viewer.set_roi_pick_mode(True)

    def _rebuild_param_panel(self):
        """清空并重建参数面板的 form 行"""
        self._updating = True
        f = self._param_form
        while f.rowCount() > 0:
            items = f.takeRow(0)
            if items.labelItem:
                label = items.labelItem.widget()
                if label is not None:
                    label.hide()
                    label.deleteLater()
            if items.fieldItem:
                field = items.fieldItem.widget()
                if field is not None:
                    field.hide()

        spin_style = "QSpinBox { padding: 3px; }"
        if self._roi_type == _ROI_TYPE_CIRCLE:
            for label, spin in [("中心X", self._circ_cx), ("中心Y", self._circ_cy), ("半径", self._radius_spin)]:
                spin.setStyleSheet(spin_style)
                f.addRow(label, spin)
                spin.show()
        elif self._roi_type == _ROI_TYPE_ROTATED:
            for label, spin in [("中心X", self._cx_spin), ("中心Y", self._cy_spin),
                                 ("宽度", self._w_spin), ("高度", self._h_spin)]:
                spin.setStyleSheet(spin_style)
                f.addRow(label, spin)
                spin.show()
            f.addRow("旋转角°", self._angle_spin)
            self._angle_spin.show()
        else:
            for label, spin in [("X", self._x_spin), ("Y", self._y_spin),
                                 ("宽度", self._w_spin), ("高度", self._h_spin)]:
                spin.setStyleSheet(spin_style)
                f.addRow(label, spin)
                spin.show()
        self._updating = False

    def _set_spin_ranges(self, image: np.ndarray | None):
        """设置输入框的范围"""
        set_spin_ranges_from_image(image,
                                    size_spins=(self._w_spin, self._h_spin),
                                    pos_spins=(self._x_spin, self._y_spin,
                                               self._cx_spin, self._cy_spin,
                                               self._circ_cx, self._circ_cy),
                                    extra_spins=(self._radius_spin,))

    def _clamp_rect(self, r: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """限制矩形区域在图像边界内"""
        return clamp_rect_to_image(r, self._image)

    def set_rect(self, rect: tuple[int, int, int, int], angle: float = 0.0):
        """设置矩形区域"""
        if rect is None or (rect[2] <= 0 and rect[3] <= 0):
            return
        self._updating = True
        x, y, w, h = self._clamp_rect(rect)
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._w_spin.setValue(w)
        self._h_spin.setValue(h)
        self._cx_spin.setValue(x + w // 2)
        self._cy_spin.setValue(y + h // 2)
        self._circ_cx.setValue(x + w // 2)
        self._circ_cy.setValue(y + h // 2)
        self._radius_spin.setValue(min(w, h) // 2)
        self._angle_spin.setValue(angle)
        self._updating = False
        draw_map = {_ROI_TYPE_RECT: "rect", _ROI_TYPE_ROTATED: "rotated", _ROI_TYPE_CIRCLE: "circle"}
        self.viewer.set_roi_rect((x, y, w, h), angle=angle,
                                 draw_type=draw_map.get(self._roi_type, "rect"))
        self._update_crop()

    def get_rect(self) -> tuple[int, int, int, int]:
        """获取当前矩形区域"""
        if self._roi_type == _ROI_TYPE_CIRCLE:
            cx, cy, r = self._circ_cx.value(), self._circ_cy.value(), self._radius_spin.value()
            r = max(1, r)
            return (cx - r, cy - r, r * 2, r * 2)
        if self._roi_type == _ROI_TYPE_ROTATED:
            cx = self._cx_spin.value()
            cy = self._cy_spin.value()
            w = self._w_spin.value()
            h = self._h_spin.value()
            return (cx - w // 2, cy - h // 2, w, h)
        return self._clamp_rect((
            self._x_spin.value(),
            self._y_spin.value(),
            self._w_spin.value(),
            self._h_spin.value()))

    def get_roi_data(self) -> dict:
        """获取完整的ROI数据"""
        return {
            "type": self._roi_type,
            "rect": self.get_rect(),
            "angle": self._angle_spin.value() if self._roi_type == _ROI_TYPE_ROTATED else 0.0,
        }

    def get_cropped_image(self) -> np.ndarray | None:
        """获取裁剪后的图像"""
        return self._cropped

    def get_base64(self) -> str:
        """获取裁剪图像的Base64编码"""
        if self._cropped is None:
            return ""
        _, buf = cv2.imencode(".png", self._cropped)
        return base64.b64encode(buf).decode("ascii")

    def _update_crop(self):
        """更新裁剪结果"""
        if self._image is None:
            return
        x, y, w, h = self.get_rect()
        if w <= 0 or h <= 0:
            return

        if self._roi_type == _ROI_TYPE_ROTATED:
            angle = self._angle_spin.value()
            cx, cy = x + w / 2.0, y + h / 2.0
            M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
            rotated = cv2.warpAffine(self._image, M, (self._image.shape[1], self._image.shape[0]),
                                     flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_CONSTANT,
                                     borderValue=(0, 0, 0))
            self._cropped = rotated[y:y+h, x:x+w].copy()
        else:
            self._cropped = self._image[y:y+h, x:x+w].copy()

        self._size_label.setText(f"尺寸: {w} x {h} px")
        self._update_base64_output()
        self._scale_preview(self._cropped)

    def _update_base64_output(self):
        """更新Base64输出文本框"""
        b64 = self.get_base64()
        if b64:
            preview = b64[:80] + "..." if len(b64) > 80 else b64
            self._base64_output.setText(preview)
            self._base64_output.setToolTip(f"长度: {len(b64)} 字符")
        else:
            self._base64_output.clear()

    def _scale_preview(self, img: np.ndarray):
        """缩放预览图像"""
        h, w = img.shape[:2]
        max_sz = 120
        scale = min(max_sz / w, max_sz / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)
        if nw <= 0 or nh <= 0:
            return
        if len(img.shape) == 3:
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        resized = cv2.resize(rgb, (nw, nh))
        h_bytes = resized.tobytes()
        qimg = QImage(h_bytes, nw, nh, nw * 3, QImage.Format_RGB888).copy()
        self._preview_label.setPixmap(QPixmap.fromImage(qimg).scaled(
            120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_any_spin_changed(self):
        """任意输入框值变化时的回调"""
        if self._updating:
            return
        self._updating = True
        r = self.get_rect()
        if not (r[2] <= 0 and r[3] <= 0):
            angle = self._angle_spin.value() if self._roi_type == _ROI_TYPE_ROTATED else 0.0
            draw_map = {_ROI_TYPE_RECT: "rect", _ROI_TYPE_ROTATED: "rotated", _ROI_TYPE_CIRCLE: "circle"}
            self.viewer.set_roi_rect(r, angle=angle,
                                     draw_type=draw_map.get(self._roi_type, "rect"))
        if self._roi_type == _ROI_TYPE_RECT:
            self._cx_spin.setValue(r[0] + r[2] // 2)
            self._cy_spin.setValue(r[1] + r[3] // 2)
        self._updating = False
        self._update_crop()

    def _on_type_changed(self, roi_type: str):
        """ROI类型变化时的回调"""
        self._roi_type = roi_type
        draw_map = {_ROI_TYPE_RECT: "rect", _ROI_TYPE_ROTATED: "rotated", _ROI_TYPE_CIRCLE: "circle"}
        self.viewer.set_roi_draw_type(draw_map.get(roi_type, "rect"))
        self._rebuild_param_panel()
        if self._image is not None:
            self.set_rect(self.get_rect())

    def _on_viewer_roi_picked(self, rect: tuple[int, int, int, int]):
        """查看器ROI拾取回调"""
        angle = getattr(self.viewer, '_last_roi_angle', 0.0)
        self.set_rect(rect, angle)
        self.viewer.set_roi_pick_mode(False)

    def _on_viewer_roi_moved(self, rect: tuple[int, int, int, int]):
        """查看器ROI拖动回调"""
        angle = self._angle_spin.value() if self._roi_type == _ROI_TYPE_ROTATED else 0.0
        self.set_rect(rect, angle)

    def _use_full_image(self):
        """使用整图"""
        if self._image is not None:
            self.viewer.set_roi_pick_mode(False)
            h, w = self._image.shape[:2]
            self.set_rect((0, 0, w, h))

    def _center_square(self):
        """居中正方形裁剪"""
        if self._image is not None:
            self.viewer.set_roi_pick_mode(False)
            h, w = self._image.shape[:2]
            sz = min(w, h)
            self.set_rect(((w - sz) // 2, (h - sz) // 2, sz, sz))

    def _save_template(self):
        """保存当前裁剪区域为可复用模板"""
        if self._cropped is None:
            QMessageBox.warning(self, "提示", "请先选择裁剪区域")
            return
        h, w = self._cropped.shape[:2]
        name, ok = QInputDialog.getText(
            self, "保存模板", "请输入模板名称:",
        )
        if not ok or not name.strip():
            return
        from gui.img_template_manager import save_img_template
        save_img_template(name.strip(), self.get_base64(), w, h)
        QMessageBox.information(self, "已保存", f"模板「{name.strip()}」已保存 ({w}x{h} px)")

    def _preview_crop(self):
        """预览裁剪结果（使用OpenCV窗口）"""
        if self._cropped is not None:
            cv2.imshow("裁剪预览 (按任意键关闭)", self._cropped)
            cv2.waitKey(0)
            cv2.destroyWindow("裁剪预览 (按任意键关闭)")

    def _copy_base64(self):
        """复制Base64编码到剪贴板"""
        b64 = self.get_base64()
        if b64:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(b64)
            QMessageBox.information(self, "已复制", f"Base64 编码已复制到剪贴板 ({len(b64)} 字符)")

    def _on_accept(self):
        """确定按钮点击处理"""
        self._update_crop()
        if self._cropped is None:
            QMessageBox.warning(self, "提示", "请先选择裁剪区域")
            return
        self.accept()

    @classmethod
    def crop_image(cls, image: np.ndarray | None,
                   rect: tuple[int, int, int, int] | None = None,
                   roi_type: str = _ROI_TYPE_RECT,
                   angle: float = 0.0,
                   parent=None) -> dict | None:
        """打开裁剪对话框并返回裁剪后的图像数据。

        参数：
            image: 源图像
            rect: 初始矩形区域
            roi_type: ROI类型
            angle: 旋转角度
            parent: 父对象

        返回：
            包含以下键的字典：'image'（ndarray），'base64'（str），'rect'（tuple）
            如果取消则返回None
        """
        dialog = cls(image=image, rect=rect, roi_type=roi_type, angle=angle, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return {
                "image": dialog.get_cropped_image(),
                "base64": dialog.get_base64(),
                "rect": dialog.get_rect(),
            }
        return None
