"""模板裁剪对话框 - 基于ROI的图像裁剪用于模板创建。

让用户在源图像上选择区域并将其提取为模板图像，
该模板图像可以直接使用或转换为base64用于模板匹配节点。
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
    """从图像中裁剪区域用于匹配节点中的模板。

    支持在图像查看器上选择矩形ROI，
    并提供X/Y/宽/高的数值微调控件。
    """

    def __init__(self, image: np.ndarray | None = None,
                 rect: tuple[int, int, int, int] | None = None,
                 parent=None):
        """初始化裁剪对话框

        参数：
            image: 源图像（numpy数组）
            rect: 初始矩形区域 (x, y, width, height)
            parent: 父对象
        """
        # 调用父类QDialog的构造函数
        super().__init__(parent)
        # 设置窗口标题
        self.setWindowTitle("模板裁剪器")
        # 设置窗口大小为960x680
        self.resize(960, 680)
        # 保存源图像
        self._image = image
        # 更新中标志（防止循环更新）
        self._updating = False
        # 裁剪后的图像
        self._cropped: np.ndarray | None = None

        # 创建图像查看器
        self.viewer = ImageViewer(self)
        # 设置图像
        self.viewer.set_image(image)
        # 连接ROI拾取信号
        self.viewer.roi_picked.connect(self._on_viewer_roi_picked)

        # X坐标输入框
        self._x_spin = QSpinBox()
        # Y坐标输入框
        self._y_spin = QSpinBox()
        # 宽度输入框
        self._w_spin = QSpinBox()
        # 高度输入框
        self._h_spin = QSpinBox()
        # 预览标签
        self._preview_label = QLabel()
        # Base64输出文本框
        self._base64_output = QTextEdit()
        # 尺寸标签
        self._size_label = QLabel("尺寸: -")

        # 设置UI界面
        self._setup_ui()
        # 设置输入框的范围
        self._set_spin_ranges(image)
        # 如果提供了初始矩形，设置矩形
        if rect:
            self.set_rect(rect)
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
        tip = QLabel("在图像上拖拽选择模板区域，使用「框选」按钮激活选区模式，或用右侧数值微调。")
        # 设置样式
        tip.setStyleSheet("color: #999; font-size: 12px;")
        # 添加到布局
        layout.addWidget(tip)

        # 主体水平布局
        body = QHBoxLayout()
        # 设置间距
        body.setSpacing(12)

        # 左侧：图像查看器，拉伸因子为2
        body.addWidget(self.viewer, 2)

        # 右侧：控件区域
        side = QWidget()
        # 设置固定宽度280
        side.setFixedWidth(280)
        # 创建表单布局
        form = QFormLayout(side)
        # 设置边距
        form.setContentsMargins(0, 0, 0, 0)
        # 设置间距
        form.setSpacing(6)

        # 输入框样式
        spin_style = "QSpinBox { padding: 3px; }"
        # 遍历创建X、Y、宽度、高度输入框
        for label, spin in [("X", self._x_spin), ("Y", self._y_spin),
                             ("宽度", self._w_spin), ("高度", self._h_spin)]:
            # 设置样式
            spin.setStyleSheet(spin_style)
            # 连接值变化信号
            spin.valueChanged.connect(self._on_spin_rect_changed)
            # 添加表单行
            form.addRow(label, spin)

        # 按钮行
        btn_row = QHBoxLayout()
        # 整图按钮
        full_btn = QPushButton("整图")
        # 连接点击信号
        full_btn.clicked.connect(self._use_full_image)
        # 添加到布局
        btn_row.addWidget(full_btn)

        # 框选按钮
        pick_btn = QPushButton("框选")
        # 连接点击信号：启用ROI拾取模式
        pick_btn.clicked.connect(lambda: self.viewer.set_roi_pick_mode(True))
        # 添加到布局
        btn_row.addWidget(pick_btn)

        # 居中1:1按钮
        center_btn = QPushButton("居中1:1")
        # 连接点击信号
        center_btn.clicked.connect(self._center_square)
        # 添加到布局
        btn_row.addWidget(center_btn)
        # 添加按钮行到表单
        form.addRow("", self._wrap(btn_row))

        # 预览区域
        form.addRow("预览", self._preview_label)
        # 设置预览标签固定大小120x120
        self._preview_label.setFixedSize(120, 120)
        # 设置预览标签样式
        self._preview_label.setStyleSheet("border: 1px solid #555; background: #1e1e1e;")
        # 设置居中对齐
        self._preview_label.setAlignment(Qt.AlignCenter)
        # 设置预览文本
        self._preview_label.setText("(无预览)")

        # 尺寸标签
        form.addRow(QLabel(""), self._size_label)
        # 设置尺寸标签样式
        self._size_label.setStyleSheet("color: #999; font-size: 11px;")

        # 添加右侧控件到主体布局
        body.addWidget(side)
        # 添加主体布局到主布局，拉伸因子为1
        layout.addLayout(body, 1)

        # Base64输出部分
        layout.addWidget(QLabel("Base64 编码 (复制到模板匹配节点):"))
        # 设置只读
        self._base64_output.setReadOnly(True)
        # 设置固定高度80
        self._base64_output.setFixedHeight(80)
        # 设置样式
        self._base64_output.setStyleSheet("background: #1e1e1e; color: #dcdcdc; border: 1px solid #505050; font-family: monospace; font-size: 11px;")
        # 设置占位符文本
        self._base64_output.setPlaceholderText("裁剪后将自动生成 Base64 编码...")
        # 添加到布局
        layout.addWidget(self._base64_output)

        # 复制按钮行
        copy_row = QHBoxLayout()
        # 复制Base64按钮
        copy_btn = QPushButton("复制 Base64")
        # 连接点击信号
        copy_btn.clicked.connect(self._copy_base64)
        # 添加到布局
        copy_row.addWidget(copy_btn)

        # 预览裁剪结果按钮
        preview_btn = QPushButton("预览裁剪结果")
        # 连接点击信号
        preview_btn.clicked.connect(self._preview_crop)
        # 添加到布局
        copy_row.addWidget(preview_btn)
        # 添加弹性空间
        copy_row.addStretch()
        # 添加到主布局
        layout.addLayout(copy_row)

        # 对话框按钮（确定/取消）
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        # 连接确定按钮信号
        buttons.accepted.connect(self._on_accept)
        # 连接取消按钮信号
        buttons.rejected.connect(self.reject)
        # 添加到布局
        layout.addWidget(buttons)

        # 默认启用ROI拾取模式
        self.viewer.set_roi_pick_mode(True)

    def _wrap(self, layout: QHBoxLayout) -> QWidget:
        """将水平布局包装成控件"""
        # 创建容器控件
        w = QWidget()
        # 设置布局
        w.setLayout(layout)
        # 返回控件
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
        # 设置X和Y输入框范围（0到max(w,h)）
        for spin in (self._x_spin, self._y_spin):
            spin.setRange(0, max(w, h))
        # 设置宽度和高度输入框范围（1到max(w,h)）
        for spin in (self._w_spin, self._h_spin):
            spin.setRange(1, max(w, h))

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
        # 获取图像宽度和高度
        iw, ih = self._image.shape[1], self._image.shape[0]
        # X坐标不能超过图像宽度-1
        x = min(x, iw - 1)
        # Y坐标不能超过图像高度-1
        y = min(y, ih - 1)
        # 宽度至少为1，不能超出图像右边界
        w = max(1, min(w, iw - x))
        # 高度至少为1，不能超出图像下边界
        h = max(1, min(h, ih - y))
        # 返回限制后的矩形
        return x, y, w, h

    def set_rect(self, rect: tuple[int, int, int, int]):
        """设置矩形区域

        参数：
            rect: 矩形元组 (x, y, width, height)
        """
        # 限制矩形在图像边界内
        x, y, w, h = self._clamp_rect(rect)
        # 设置更新标志，防止循环更新
        self._updating = True
        # 设置X值
        self._x_spin.setValue(x)
        # 设置Y值
        self._y_spin.setValue(y)
        # 设置宽度值
        self._w_spin.setValue(w)
        # 设置高度值
        self._h_spin.setValue(h)
        # 清除更新标志
        self._updating = False
        # 更新查看器的ROI矩形
        self.viewer.set_roi_rect((x, y, w, h))
        # 更新裁剪结果
        self._update_crop()

    def get_rect(self) -> tuple[int, int, int, int]:
        """获取当前矩形区域"""
        # 获取输入框的值并限制范围
        return self._clamp_rect((
            self._x_spin.value(),   # X坐标
            self._y_spin.value(),   # Y坐标
            self._w_spin.value(),   # 宽度
            self._h_spin.value()))  # 高度

    def get_cropped_image(self) -> np.ndarray | None:
        """获取裁剪后的图像"""
        return self._cropped

    def get_base64(self) -> str:
        """获取裁剪图像的Base64编码"""
        # 如果没有裁剪图像，返回空字符串
        if self._cropped is None:
            return ""
        # 将图像编码为PNG格式
        _, buf = cv2.imencode(".png", self._cropped)
        # 返回Base64编码字符串
        return base64.b64encode(buf).decode("ascii")

    def _update_crop(self):
        """更新裁剪结果"""
        # 如果没有图像，返回
        if self._image is None:
            return
        # 获取矩形区域
        x, y, w, h = self.get_rect()
        # 如果宽或高无效，返回
        if w <= 0 or h <= 0:
            return
        # 裁剪图像
        self._cropped = self._image[y:y+h, x:x+w].copy()
        # 更新尺寸标签
        self._size_label.setText(f"尺寸: {w} x {h} px")
        # 更新Base64输出
        self._update_base64_output()
        # 缩放预览
        self._scale_preview(self._cropped)

    def _update_base64_output(self):
        """更新Base64输出文本框"""
        # 获取Base64编码
        b64 = self.get_base64()
        # 如果有编码
        if b64:
            # 如果长度超过80，截断显示
            preview = b64[:80] + "..." if len(b64) > 80 else b64
            # 设置文本框内容
            self._base64_output.setText(preview)
            # 设置工具提示显示完整长度
            self._base64_output.setToolTip(f"长度: {len(b64)} 字符")
        else:
            # 清空文本框
            self._base64_output.clear()

    def _scale_preview(self, img: np.ndarray):
        """缩放预览图像

        参数：
            img: 要预览的图像
        """
        # 获取图像尺寸
        h, w = img.shape[:2]
        # 最大预览尺寸120
        max_sz = 120
        # 计算缩放比例
        scale = min(max_sz / w, max_sz / h, 1.0)
        # 计算新尺寸
        nw, nh = int(w * scale), int(h * scale)
        # 如果尺寸无效，返回
        if nw <= 0 or nh <= 0:
            return
        # 转换为RGB格式用于Qt显示
        if len(img.shape) == 3:
            # BGR转RGB
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            # 灰度图转RGB
            rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        # 调整大小
        resized = cv2.resize(rgb, (nw, nh))
        # 转换为字节数据
        h_bytes = resized.tobytes()
        # 创建QImage
        qimg = QImage(h_bytes, nw, nh, nw * 3, QImage.Format_RGB888)
        # 设置预览标签的像素图
        self._preview_label.setPixmap(QPixmap.fromImage(qimg).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_spin_rect_changed(self):
        """输入框值变化时的回调"""
        # 如果正在更新中，跳过
        if self._updating:
            return
        # 更新查看器的ROI矩形
        self.viewer.set_roi_rect(self.get_rect())
        # 更新裁剪结果
        self._update_crop()

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
        """使用整图"""
        # 如果有图像
        if self._image is not None:
            # 获取图像尺寸
            h, w = self._image.shape[:2]
            # 设置为整图矩形
            self.set_rect((0, 0, w, h))

    def _center_square(self):
        """居中正方形裁剪"""
        # 如果有图像
        if self._image is not None:
            # 获取图像尺寸
            h, w = self._image.shape[:2]
            # 取较小者作为正方形边长
            sz = min(w, h)
            # 计算居中位置
            x = (w - sz) // 2
            y = (h - sz) // 2
            # 设置居中正方形矩形
            self.set_rect((x, y, sz, sz))

    def _preview_crop(self):
        """预览裁剪结果（使用OpenCV窗口）"""
        # 如果有裁剪图像
        if self._cropped is not None:
            # 显示图像
            cv2.imshow("裁剪预览 (按任意键关闭)", self._cropped)
            # 等待按键
            cv2.waitKey(0)
            # 关闭窗口
            cv2.destroyWindow("裁剪预览 (按任意键关闭)")

    def _copy_base64(self):
        """复制Base64编码到剪贴板"""
        # 获取Base64编码
        b64 = self.get_base64()
        # 如果有编码
        if b64:
            # 从PyQt5导入剪贴板
            from PyQt5.QtWidgets import QApplication
            # 设置剪贴板文本
            QApplication.clipboard().setText(b64)
            # 显示信息对话框
            QMessageBox.information(self, "已复制", f"Base64 编码已复制到剪贴板 ({len(b64)} 字符)")

    def _on_accept(self):
        """确定按钮点击处理"""
        # 更新裁剪结果
        self._update_crop()
        # 如果没有裁剪图像
        if self._cropped is None:
            # 显示警告
            QMessageBox.warning(self, "提示", "请先选择裁剪区域")
            return
        # 接受对话框
        self.accept()

    @classmethod
    def crop_image(cls, image: np.ndarray | None,
                   rect: tuple[int, int, int, int] | None = None,
                   parent=None) -> dict | None:
        """打开裁剪对话框并返回裁剪后的图像数据。

        参数：
            image: 源图像
            rect: 初始矩形区域
            parent: 父对象

        返回：
            包含以下键的字典：'image'（ndarray），'base64'（str），'rect'（tuple）
            如果取消则返回None
        """
        # 创建对话框实例
        dialog = cls(image=image, rect=rect, parent=parent)
        # 如果用户确认
        if dialog.exec_() == QDialog.Accepted:
            # 返回裁剪数据
            return {
                "image": dialog.get_cropped_image(),  # 裁剪后的图像
                "base64": dialog.get_base64(),        # Base64编码
                "rect": dialog.get_rect(),            # 矩形区域
            }
        # 取消则返回None
        return None