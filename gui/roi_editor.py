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
    QStackedWidget,
)

from gui.image_viewer import ImageViewer


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
        # 调用父类QDialog的构造函数
        super().__init__(parent)
        # 设置窗口标题
        self.setWindowTitle("ROI 编辑器")
        # 设置窗口大小为960x680
        self.resize(960, 680)
        # 全屏标志，初始为False
        self._fullscreen = False
        # 保存图像
        self._image = image
        # 更新中标志（防止循环更新）
        self._updating = False
        # ROI类型
        self._roi_type = roi_type

        # 创建图像查看器
        self.viewer = ImageViewer(self)
        # 设置图像
        self.viewer.set_image(image)
        # 连接ROI拾取信号
        self.viewer.roi_picked.connect(self._on_viewer_roi_picked)

        # 矩形控件
        self._x_spin = QSpinBox()   # X坐标
        self._y_spin = QSpinBox()   # Y坐标
        self._w_spin = QSpinBox()   # 宽度
        self._h_spin = QSpinBox()   # 高度

        # 旋转矩形额外控件
        self._angle_spin = QDoubleSpinBox()  # 旋转角度
        self._cx_spin = QSpinBox()           # 中心X坐标
        self._cy_spin = QSpinBox()           # 中心Y坐标

        # 圆形控件
        self._circ_cx = QSpinBox()    # 圆心X坐标
        self._circ_cy = QSpinBox()    # 圆心Y坐标
        self._radius_spin = QSpinBox() # 半径

        # 设置UI
        self._setup_ui()
        # 设置输入框范围
        self._set_spin_ranges(image)

        # 如果提供了初始矩形，设置矩形
        if rect:
            self.set_rect(rect, angle)
        else:
            # 否则使用整图
            self._use_full_image()

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局
        layout = QVBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(10, 10, 10, 10)
        # 设置布局间距
        layout.setSpacing(8)

        # 提示标签
        tip = QLabel("选择ROI类型并用鼠标在图像上框选，或通过右侧面板微调数值。")
        tip.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(tip)

        # 主体水平布局
        body = QHBoxLayout()
        body.setSpacing(12)
        # 添加图像查看器，拉伸因子为2
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

        # 堆叠参数面板
        self._param_stack = QStackedWidget()
        self._param_stack.addWidget(self._build_rect_panel())      # 矩形面板（索引0）
        self._param_stack.addWidget(self._build_rotated_panel())   # 旋转矩形面板（索引1）
        self._param_stack.addWidget(self._build_circle_panel())    # 圆形面板（索引2）
        side_lo.addWidget(self._param_stack)

        # 动作按钮行
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

        # 弹性空间
        side_lo.addStretch()
        # 添加右侧控件到主体布局
        body.addWidget(side)
        # 添加主体布局到主布局，拉伸因子为1
        layout.addLayout(body, 1)

        # 对话框按钮（确定/取消）
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 默认启用ROI拾取模式
        self.viewer.set_roi_pick_mode(True)
        # 默认显示矩形面板
        self._param_stack.setCurrentIndex(0)

    def _build_rect_panel(self) -> QWidget:
        """构建矩形参数面板

        返回：
            面板控件
        """
        # 创建容器
        w = QWidget()
        # 创建表单布局
        form = QFormLayout(w)
        # 设置边距为0
        form.setContentsMargins(0, 0, 0, 0)
        # 设置间距为6
        form.setSpacing(6)
        # 添加X、Y、宽度、高度控件
        for label, spin in [("X", self._x_spin), ("Y", self._y_spin),
                             ("宽度", self._w_spin), ("高度", self._h_spin)]:
            # 连接值变化信号
            spin.valueChanged.connect(self._on_rect_changed)
            # 添加表单行
            form.addRow(label, spin)
        return w

    def _build_rotated_panel(self) -> QWidget:
        """构建旋转矩形参数面板

        返回：
            面板控件
        """
        # 创建容器
        w = QWidget()
        # 创建表单布局
        form = QFormLayout(w)
        # 设置边距为0
        form.setContentsMargins(0, 0, 0, 0)
        # 设置间距为6
        form.setSpacing(6)
        # 添加中心X、中心Y、宽度、高度控件
        for label, spin in [("中心X", self._cx_spin), ("中心Y", self._cy_spin),
                             ("宽度", self._w_spin), ("高度", self._h_spin)]:
            # 连接值变化信号
            spin.valueChanged.connect(self._on_rotated_changed)
            # 添加表单行
            form.addRow(label, spin)
        # 设置角度输入框范围
        self._angle_spin.setRange(-180.0, 180.0)
        self._angle_spin.setValue(0.0)
        self._angle_spin.setDecimals(1)      # 1位小数
        self._angle_spin.setSingleStep(1.0)  # 步进1度
        self._angle_spin.valueChanged.connect(self._on_rotated_changed)
        form.addRow("旋转角°", self._angle_spin)
        return w

    def _build_circle_panel(self) -> QWidget:
        """构建圆形参数面板

        返回：
            面板控件
        """
        # 创建容器
        w = QWidget()
        # 创建表单布局
        form = QFormLayout(w)
        # 设置边距为0
        form.setContentsMargins(0, 0, 0, 0)
        # 设置间距为6
        form.setSpacing(6)
        # 添加圆心X、圆心Y、半径控件
        for label, spin in [("中心X", self._circ_cx), ("中心Y", self._circ_cy),
                             ("半径", self._radius_spin)]:
            # 连接值变化信号
            spin.valueChanged.connect(self._on_circle_changed)
            # 添加表单行
            form.addRow(label, spin)
        return w

    def _set_spin_ranges(self, image: np.ndarray | None):
        """设置输入框的范围

        参数：
            image: 源图像
        """
        # 如果没有图像，返回
        if image is None:
            return
        # 获取图像高度和宽度
        h, w = image.shape[:2]
        # 最大尺寸
        max_dim = max(w, h)
        # 设置位置相关输入框的范围（0到max_dim）
        for spin in (self._x_spin, self._y_spin, self._cx_spin, self._cy_spin,
                      self._circ_cx, self._circ_cy):
            spin.setRange(0, max_dim)
        # 设置尺寸相关输入框的范围（1到max_dim）
        for spin in (self._w_spin, self._h_spin):
            spin.setRange(1, max_dim)
        # 设置半径输入框的范围（1到max_dim）
        self._radius_spin.setRange(1, max_dim)

    def _clamp_rect(self, r: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """限制矩形区域在图像边界内

        参数：
            r: 矩形元组 (x, y, width, height)

        返回：
            限制后的矩形元组
        """
        # 将各值转换为整数并确保不小于0
        x, y, w, h = [max(0, int(v)) for v in r]
        # 如果没有图像，直接返回
        if self._image is None:
            return x, y, max(1, w), max(1, h)
        # 获取图像尺寸
        iw, ih = self._image.shape[1], self._image.shape[0]
        # X坐标不能超过图像宽度-1
        x = min(x, iw - 1)
        # Y坐标不能超过图像高度-1
        y = min(y, ih - 1)
        # 宽度至少为1，不能超出右边界
        w = max(1, min(w, iw - x))
        # 高度至少为1，不能超出下边界
        h = max(1, min(h, ih - y))
        return x, y, w, h

    def set_rect(self, rect: tuple[int, int, int, int], angle: float = 0.0):
        """设置矩形区域

        参数：
            rect: 矩形元组 (x, y, width, height)
            angle: 旋转角度（仅用于旋转矩形）
        """
        # 设置更新标志，防止循环更新
        self._updating = True
        # 限制矩形边界
        x, y, w, h = self._clamp_rect(rect)
        # 设置矩形控件的值
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._w_spin.setValue(w)
        self._h_spin.setValue(h)
        # 设置旋转矩形控件的值（中心坐标）
        self._cx_spin.setValue(x + w // 2)
        self._cy_spin.setValue(y + h // 2)
        # 设置圆形控件的值（圆心坐标）
        self._circ_cx.setValue(x + w // 2)
        self._circ_cy.setValue(y + h // 2)
        # 设置半径（取宽高中的较小者的一半）
        self._radius_spin.setValue(min(w, h) // 2)
        # 设置角度
        self._angle_spin.setValue(angle)
        # 清除更新标志
        self._updating = False
        # 更新查看器的ROI矩形
        self.viewer.set_roi_rect((x, y, w, h))

    def get_rect(self) -> tuple[int, int, int, int]:
        """获取当前矩形区域

        返回：
            (x, y, w, h) 元组
        """
        # 如果是圆形类型
        if self._roi_type == _ROI_TYPE_CIRCLE:
            # 获取圆心坐标和半径
            cx, cy, r = self._circ_cx.value(), self._circ_cy.value(), self._radius_spin.value()
            # 确保半径至少为1
            r = max(1, r)
            # 返回外接矩形
            return (cx - r, cy - r, r * 2, r * 2)
        # 返回矩形类型的结果
        return self._clamp_rect((
            self._x_spin.value(),   # X坐标
            self._y_spin.value(),   # Y坐标
            self._w_spin.value(),   # 宽度
            self._h_spin.value()))  # 高度

    def get_roi_data(self) -> dict:
        """获取完整的ROI数据，包括类型和旋转角

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

    def _on_rect_changed(self):
        """矩形参数变化时的回调"""
        # 如果正在更新中，返回
        if self._updating:
            return
        # 获取当前矩形
        r = self.get_rect()
        # 更新查看器的ROI矩形
        self.viewer.set_roi_rect(r)
        # 同步更新旋转矩形的中心点
        self._cx_spin.setValue(r[0] + r[2] // 2)
        self._cy_spin.setValue(r[1] + r[3] // 2)

    def _on_rotated_changed(self):
        """旋转矩形参数变化时的回调"""
        # 如果正在更新中，返回
        if self._updating:
            return
        # 获取旋转矩形参数
        cx = self._cx_spin.value()
        cy = self._cy_spin.value()
        w = self._w_spin.value()
        h = self._h_spin.value()
        # 计算左上角坐标
        x = cx - w // 2
        y = cy - h // 2
        # 更新查看器的ROI矩形
        self.viewer.set_roi_rect((x, y, w, h))

    def _on_circle_changed(self):
        """圆形参数变化时的回调"""
        # 如果正在更新中，返回
        if self._updating:
            return
        # 获取当前矩形（圆形转换为外接矩形）
        r = self.get_rect()
        # 更新查看器的ROI矩形
        self.viewer.set_roi_rect(r)

    def _on_type_changed(self, roi_type: str):
        """ROI类型变化时的回调

        参数：
            roi_type: 新的ROI类型
        """
        # 保存ROI类型
        self._roi_type = roi_type
        # 类型到索引的映射
        idx_map = {_ROI_TYPE_RECT: 0, _ROI_TYPE_ROTATED: 1, _ROI_TYPE_CIRCLE: 2}
        # 切换堆叠面板
        self._param_stack.setCurrentIndex(idx_map.get(roi_type, 0))
        # 重新设置矩形（更新显示）
        self.set_rect(self.get_rect())

    def _on_viewer_roi_picked(self, rect: tuple[int, int, int, int]):
        """查看器ROI拾取回调

        参数：
            rect: 拾取的矩形区域
        """
        # 设置矩形
        self.set_rect(rect)
        # 关闭ROI拾取模式
        self.viewer.set_roi_pick_mode(False)

    def _use_full_image(self):
        """使用整图作为ROI"""
        # 如果有图像
        if self._image is not None:
            # 获取图像尺寸
            h, w = self._image.shape[:2]
            # 设置矩形为整图
            self.set_rect((0, 0, w, h))

    def _center_square(self):
        """居中正方形ROI"""
        # 如果有图像
        if self._image is not None:
            # 获取图像尺寸
            h, w = self._image.shape[:2]
            # 取较小者作为边长
            sz = min(w, h)
            # 居中放置
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
                 parent=None) -> tuple[int, int, int, int] | None:
        """静态方法：打开ROI编辑器并获取ROI

        参数：
            image: 源图像
            rect: 初始矩形区域
            parent: 父对象

        返回：
            如果确认则返回矩形 (x, y, w, h)，否则返回None
        """
        # 创建对话框实例
        dialog = cls(image=image, rect=rect, parent=parent)
        # 如果用户确认
        if dialog.exec_() == QDialog.Accepted:
            # 返回矩形区域
            return dialog.get_rect()
        # 取消则返回None
        return None