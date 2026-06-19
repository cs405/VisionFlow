"""ROI编辑器对话框 - 矩形、旋转矩形和圆形ROI类型。

提供基于画布的区域选择，带有数值微调控件和三种ROI形状类型。
"""

from __future__ import annotations

import math

import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QDoubleSpinBox,
    QPushButton, QDialogButtonBox, QWidget, QFormLayout, QComboBox,
)

from gui.image_viewer import ImageViewer
from gui.widget_utils import set_spin_ranges_from_image, clamp_rect_to_image


# ROI类型常量
_ROI_TYPE_RECT = "矩形"           # 矩形类型
_ROI_TYPE_ROTATED = "旋转矩形"    # 旋转矩形类型
_ROI_TYPE_CIRCLE = "圆形"         # 圆形类型


class RoiEditorDialog(QDialog):
    """支持矩形、旋转矩形和圆形的ROI编辑器。"""

    def __init__(self, image: np.ndarray | None = None,
                 rect: tuple[int, int, int, int] | None = None,
                 roi_type: str = _ROI_TYPE_RECT,
                 angle: float = 0.0,
                 parent=None):
        """初始化ROI编辑器对话框

        参数：
            image: 源图像
            rect: 初始矩形区域 (x, y, w, h)
            roi_type: ROI类型（矩形/旋转矩形/圆形）
            angle: 旋转角度（仅用于旋转矩形）
            parent: 父对象
        """
        super().__init__(parent)
        self.setWindowTitle("ROI 编辑器")
        self.resize(960, 680)
        self._fullscreen = False                                    # 全屏标志，初始为False
        self._image = image                                         # 保存图像
        self._updating = False                                      # 更新中标志（防止循环更新）
        self._roi_type = roi_type                                   # ROI类型
        self.viewer = ImageViewer(self)                             # 创建图像查看器
        self.viewer.set_image(image)                                # 设置图像
        self.viewer.roi_picked.connect(self._on_viewer_roi_picked)  # 连接ROI拾取信号
        self.viewer.roi_moved.connect(self._on_viewer_roi_moved)    # 连接ROI拖动信号

        # 矩形控件
        self._x_spin = QSpinBox()   # X坐标
        self._y_spin = QSpinBox()   # Y坐标
        self._w_spin = QSpinBox()   # 宽度
        self._h_spin = QSpinBox()   # 高度

        # 旋转矩形额外控件
        self._angle_spin = QDoubleSpinBox()  # 旋转角度
        self._angle_spin.setRange(-180.0, 180.0)
        self._angle_spin.setValue(0.0)
        self._angle_spin.setDecimals(1)
        self._angle_spin.setSingleStep(1.0)
        self._cx_spin = QSpinBox()           # 中心X坐标
        self._cy_spin = QSpinBox()           # 中心Y坐标

        # 圆形控件
        self._circ_cx = QSpinBox()    # 圆心X坐标
        self._circ_cy = QSpinBox()    # 圆心Y坐标
        self._radius_spin = QSpinBox() # 半径

        # 统一连接所有 spin 信号（只连一次）
        for s in [self._x_spin, self._y_spin, self._w_spin, self._h_spin,
                  self._cx_spin, self._cy_spin, self._circ_cx, self._circ_cy, self._radius_spin]:
            s.valueChanged.connect(self._on_any_spin_changed)
        self._angle_spin.valueChanged.connect(self._on_any_spin_changed)

        # 设置UI
        self._setup_ui()
        # _setup_ui 中 addItems 会触发 _on_type_changed 覆盖 roi_type，这里恢复
        if roi_type != _ROI_TYPE_RECT:
            self._type_combo.setCurrentText(roi_type)
        self._updating = True                                            # 阻止 setRange 触发信号链
        self._set_spin_ranges(image)                                     # 设置输入框范围
        self._updating = False

        # 如果提供了初始矩形，设置矩形；否则不预设，等待用户自行框选
        if rect:
            self.set_rect(rect, angle)

    def _setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 提示标签
        tip = QLabel("选择ROI类型并用鼠标在图像上框选，或通过右侧面板微调数值。")
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        # 主体水平布局
        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self.viewer, 2)

        # 右侧控件区域
        side = QWidget()
        side.setFixedWidth(280)  # 固定宽度280
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

        # 参数面板（切类型时清空行重建，不删控件）
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
        center_btn = QPushButton("居中正方形")
        center_btn.clicked.connect(self._center_square)
        btn_row.addWidget(center_btn)
        side_lo.addLayout(btn_row)

        side_lo.addStretch()
        body.addWidget(side)
        layout.addLayout(body, 1)

        # 对话框按钮（确定/取消）
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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

    def get_rect(self) -> tuple[int, int, int, int]:
        """
        获取当前矩形区域
        返回：
            (x, y, w, h) 元组
        """
        if self._roi_type == _ROI_TYPE_CIRCLE:
            cx, cy, r = self._circ_cx.value(), self._circ_cy.value(), self._radius_spin.value()
            r = max(1, r)
            return cx - r, cy - r, r * 2, r * 2
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
        """
        获取完整的ROI数据，包括类型和旋转角
        返回：
            ROI数据字典
        """
        return {
            "type": self._roi_type,  # ROI类型
            "rect": self.get_rect(), # 矩形区域
            "angle": self._angle_spin.value() if self._roi_type == _ROI_TYPE_ROTATED else 0.0,  # 旋转角
            "center": (  # 中心点坐标
                self._cx_spin.value() if self._roi_type == _ROI_TYPE_ROTATED
                else self._circ_cx.value() if self._roi_type == _ROI_TYPE_CIRCLE
                else self._x_spin.value() + self._w_spin.value() // 2,
                self._cy_spin.value() if self._roi_type == _ROI_TYPE_ROTATED
                else self._circ_cy.value() if self._roi_type == _ROI_TYPE_CIRCLE
                else self._y_spin.value() + self._h_spin.value() // 2,
            ),
        }

    def _on_any_spin_changed(self):
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

    def _on_type_changed(self, roi_type: str):
        """ROI类型变化时的回调"""
        self._roi_type = roi_type
        draw_map = {_ROI_TYPE_RECT: "rect", _ROI_TYPE_ROTATED: "rotated", _ROI_TYPE_CIRCLE: "circle"}
        self.viewer.set_roi_draw_type(draw_map.get(roi_type, "rect"))
        self._rebuild_param_panel()
        if self._image is not None:
            self.set_rect(self.get_rect())

    def _rebuild_param_panel(self):
        """清空并重建参数面板的 form 行，保留 spin 控件，仅替换标签"""
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

        if self._roi_type == _ROI_TYPE_CIRCLE:
            for label, spin in [("中心X", self._circ_cx), ("中心Y", self._circ_cy), ("半径", self._radius_spin)]:
                f.addRow(label, spin)
                spin.show()
        elif self._roi_type == _ROI_TYPE_ROTATED:
            for label, spin in [("中心X", self._cx_spin), ("中心Y", self._cy_spin),
                                 ("宽度", self._w_spin), ("高度", self._h_spin)]:
                f.addRow(label, spin)
                spin.show()
            f.addRow("旋转角°", self._angle_spin)
            self._angle_spin.show()
        else:
            for label, spin in [("X", self._x_spin), ("Y", self._y_spin),
                                 ("宽度", self._w_spin), ("高度", self._h_spin)]:
                f.addRow(label, spin)
                spin.show()
        self._updating = False

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
        """使用整图作为ROI"""
        if self._image is not None:
            self.viewer.set_roi_pick_mode(False)
            h, w = self._image.shape[:2]
            self.set_rect((0, 0, w, h))

    def _center_square(self):
        """居中正方形ROI"""
        if self._image is not None:
            self.viewer.set_roi_pick_mode(False)
            h, w = self._image.shape[:2]
            sz = min(w, h)
            self.set_rect(((w - sz) // 2, (h - sz) // 2, sz, sz))

    def toggle_fullscreen(self):
        """切换全屏模式（DrawROI的"全屏绘制"按钮）"""
        # 如果当前是全屏
        if self._fullscreen:
            # 恢复正常大小
            self.showNormal()
            # 设置全屏标志为False
            self._fullscreen = False
        else:
            # 最大化窗口
            self.showMaximized()
            # 设置全屏标志为True
            self._fullscreen = True

    @classmethod
    def edit_roi(cls, image: np.ndarray | None,
                 rect: tuple[int, int, int, int] | None = None,
                 roi_type: str = _ROI_TYPE_RECT,
                 angle: float = 0.0,
                 parent=None) -> dict | None:
        """
        静态方法：打开ROI编辑器并获取ROI
        参数：
            image: 源图像
            rect: 初始矩形区域
            roi_type: 初始ROI类型
            angle: 初始旋转角度
            parent: 父对象

        返回：
            如果确认则返回 ROI 数据字典，否则返回 None
        """
        dialog = cls(image=image, rect=rect, roi_type=roi_type, angle=angle, parent=parent)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_roi_data()
        return None