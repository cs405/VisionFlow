"""带有RGB/HSV同步和图像取色的颜色选择器对话框。"""

from __future__ import annotations

import cv2
import numpy as np
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPixmap
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
    QScrollArea,
    QApplication,
    QSizePolicy,
)

from gui.widget_utils import wrap_layout


class ImagePickLabel(QLabel):
    """可点击取色的图像标签

    将 BGR 图像缩放显示，鼠标左键点击时反算原始坐标，
    提取像素的 BGR 值并通过 color_picked 信号发出 RGB 元组。
    """
    color_picked = pyqtSignal(tuple)  # (r, g, b)

    def __init__(self, bgr_image: np.ndarray, parent=None):
        super().__init__(parent)
        # 保存副本用于取色时反查像素值
        self._bgr = bgr_image.copy()
        h, w = bgr_image.shape[:2]

        # 使用已有的稳定转换（避免 QImage 直接引用 numpy 内存导致悬空指针闪退）
        from gui.image_viewer import numpy_to_pixmap
        self._full_pixmap = numpy_to_pixmap(bgr_image)

        # 缩放到适合屏幕
        screen = QApplication.primaryScreen().availableGeometry()
        max_w = int(screen.width() * 0.75)
        max_h = int(screen.height() * 0.75)
        self._scaled = self._full_pixmap.scaled(
            max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._scale_x = w / max(self._scaled.width(), 1)
        self._scale_y = h / max(self._scaled.height(), 1)
        self.setPixmap(self._scaled)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        sw = self._scaled.width()
        sh = self._scaled.height()
        ox = (self.width() - sw) // 2
        oy = (self.height() - sh) // 2
        x = int((event.x() - ox) * self._scale_x)
        y = int((event.y() - oy) * self._scale_y)
        h, w = self._bgr.shape[:2]
        x, y = max(0, min(w - 1, x)), max(0, min(h - 1, y))
        pixel = self._bgr[y, x]
        if len(self._bgr.shape) == 2:
            self.color_picked.emit((int(pixel), int(pixel), int(pixel)))
        else:
            b, g, r = int(pixel[0]), int(pixel[1]), int(pixel[2])
            self.color_picked.emit((r, g, b))


class ImagePickDialog(QDialog):
    """从图像取色的模态对话框

    显示节点的输入图像，用户点击目标区域即可提取该像素的 RGB 颜色。
    """
    def __init__(self, bgr_image: np.ndarray, parent=None):
        super().__init__(parent)
        self.setWindowTitle("从图像取色 — 点击目标颜色区域")
        self._color = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setStyleSheet("QScrollArea { border: none; background: #1e1e1e; }")
        self._label = ImagePickLabel(bgr_image)
        self._label.color_picked.connect(self._on_picked)
        scroll.setWidget(self._label)
        layout.addWidget(scroll)
        h, w = bgr_image.shape[:2]
        self.resize(min(w + 20, 1200), min(h + 20, 900))

    def _on_picked(self, rgb: tuple):
        self._color = rgb
        self.accept()

    @property
    def picked_rgb(self) -> tuple | None:
        return self._color


class ColorPickerDialog(QDialog):
    """使用RGB/HSV控件或从图像采样来选取颜色。"""

    def __init__(self, rgb: tuple[int, int, int] = (255, 255, 255),
                 viewer=None, picker_image: np.ndarray = None, parent=None):
        """初始化颜色选择器对话框

        参数：
            rgb: 初始RGB颜色值，默认为白色
            viewer: 图像查看器对象（用于取色功能）
            parent: 父对象
        """
        # 调用父类QDialog的构造函数
        super().__init__(parent)
        # 设置窗口标题
        self.setWindowTitle("颜色选择器")
        # 设置窗口大小为420x320
        self.resize(420, 320)
        # 保存图像查看器引用
        self._viewer = viewer
        # 保存静态取色图像
        self._picker_image = picker_image
        # 更新中标志（防止循环更新）
        self._updating = False

        # R通道输入框（0-255）
        self._r = QSpinBox()
        # G通道输入框（0-255）
        self._g = QSpinBox()
        # B通道输入框（0-255）
        self._b = QSpinBox()
        # H通道输入框（0-179，OpenCV中Hue范围）
        self._h = QSpinBox()
        # S通道输入框（0-255）
        self._s = QSpinBox()
        # V通道输入框（0-255）
        self._v = QSpinBox()
        # HEX颜色显示编辑框（只读）
        self._hex_edit = QLineEdit()
        # 颜色预览标签
        self._preview = QLabel()
        # 从图像取色按钮
        self._pick_button = QPushButton("从图像取色")

        # 设置UI界面
        self._setup_ui()
        # 设置初始RGB颜色
        self.set_rgb(rgb)

    def _setup_ui(self):
        """设置UI界面"""
        # 创建垂直布局作为主布局
        layout = QVBoxLayout(self)
        # 设置布局边距
        layout.setContentsMargins(10, 10, 10, 10)
        # 设置布局间距
        layout.setSpacing(8)

        # 提示标签
        tip = QLabel("支持 RGB / OpenCV HSV 联动；若当前预览区有图像，可直接点击取色。")
        # 允许换行
        tip.setWordWrap(True)
        # 设置样式
        tip.setStyleSheet("color: #999; font-size: 12px;")
        # 添加到布局
        layout.addWidget(tip)

        # 创建内容水平布局
        content = QHBoxLayout()
        # 设置间距
        content.setSpacing(12)

        # 表单容器
        form_widget = QWidget()
        # 创建表单布局
        form = QFormLayout(form_widget)
        # 设置标签左对齐
        form.setLabelAlignment(Qt.AlignLeft)

        # 设置RGB和SV通道输入框的范围（0-255）
        for spin in (self._r, self._g, self._b, self._s, self._v):
            spin.setRange(0, 255)
        # H通道范围0-179（OpenCV标准）
        self._h.setRange(0, 179)

        # 连接RGB通道变化信号
        self._r.valueChanged.connect(self._on_rgb_changed)
        self._g.valueChanged.connect(self._on_rgb_changed)
        self._b.valueChanged.connect(self._on_rgb_changed)
        # 连接HSV通道变化信号
        self._h.valueChanged.connect(self._on_hsv_changed)
        self._s.valueChanged.connect(self._on_hsv_changed)
        self._v.valueChanged.connect(self._on_hsv_changed)

        # 添加表单行
        form.addRow("R", self._r)
        form.addRow("G", self._g)
        form.addRow("B", self._b)
        form.addRow("H", self._h)
        form.addRow("S", self._s)
        form.addRow("V", self._v)

        # HEX编辑框设为只读
        self._hex_edit.setReadOnly(True)
        form.addRow("HEX", self._hex_edit)

        # 按钮容器
        controls = QHBoxLayout()
        # 系统颜色按钮
        sys_btn = QPushButton("系统颜色")
        # 连接系统颜色按钮点击信号
        sys_btn.clicked.connect(self._pick_system_color)
        # 添加到按钮布局
        controls.addWidget(sys_btn)

        # 取色按钮
        self._pick_button.clicked.connect(self._start_pick_from_viewer)
        controls.addWidget(self._pick_button)
        # 添加按钮行到表单
        form.addRow("", self._wrap_layout(controls))

        # 将表单容器添加到内容布局，拉伸因子为1
        content.addWidget(form_widget, 1)

        # 预览区域垂直布局
        preview_box = QVBoxLayout()
        # 预览标题
        preview_title = QLabel("预览")
        # 设置粗体样式
        preview_title.setStyleSheet("font-weight: bold;")
        preview_box.addWidget(preview_title)

        # 预览标签（固定大小120x120）
        self._preview.setFixedSize(120, 120)
        # 设置预览标签样式：边框，圆角
        self._preview.setStyleSheet("border: 1px solid #555; border-radius: 4px;")
        # 添加到预览布局，顶部居中对齐
        preview_box.addWidget(self._preview, alignment=Qt.AlignTop | Qt.AlignHCenter)
        # 添加弹性空间
        preview_box.addStretch()
        # 将预览布局添加到内容布局
        content.addLayout(preview_box)

        # 添加内容布局到主布局
        layout.addLayout(content)

        # 按钮框（确定/取消）
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        # 连接确定按钮信号
        buttons.accepted.connect(self.accept)
        # 连接取消按钮信号
        buttons.rejected.connect(self.reject)
        # 添加到布局
        layout.addWidget(buttons)

        # 根据是否有查看器或取色图像来启用取色按钮
        self._pick_button.setEnabled(self._viewer is not None or self._picker_image is not None)

    def _wrap_layout(self, layout: QHBoxLayout) -> QWidget:
        """将水平布局包装成控件"""
        return wrap_layout(layout)

    def _rgb_to_hsv(self, rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        """将RGB颜色转换为OpenCV HSV颜色

        参数：
            rgb: RGB元组 (R, G, B)，各值范围0-255

        返回：
            HSV元组 (H, S, V)，H范围0-179，S/V范围0-255
        """
        # 将RGB转换为BGR格式并创建numpy数组
        bgr = np.array([[[rgb[2], rgb[1], rgb[0]]]], dtype=np.uint8)
        # 使用OpenCV转换为HSV
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0]
        # 返回HSV整数值
        return int(hsv[0]), int(hsv[1]), int(hsv[2])

    def _hsv_to_rgb(self, hsv: tuple[int, int, int]) -> tuple[int, int, int]:
        """将OpenCV HSV颜色转换为RGB颜色

        参数：
            hsv: HSV元组 (H, S, V)，H范围0-179，S/V范围0-255

        返回：
            RGB元组 (R, G, B)，各值范围0-255
        """
        # 创建numpy数组并转换为BGR
        bgr = cv2.cvtColor(np.array([[hsv]], dtype=np.uint8), cv2.COLOR_HSV2BGR)[0, 0]
        # 返回RGB整数值
        return int(bgr[2]), int(bgr[1]), int(bgr[0])

    def set_rgb(self, rgb: tuple[int, int, int]):
        """设置RGB颜色并同步更新HSV和预览

        参数：
            rgb: RGB元组 (R, G, B)
        """
        # 限制RGB值在0-255范围内
        rgb = tuple(max(0, min(255, int(v))) for v in rgb)
        # 转换为HSV
        hsv = self._rgb_to_hsv(rgb)
        # 设置更新标志，防止循环更新
        self._updating = True
        # 设置R值
        self._r.setValue(rgb[0])
        # 设置G值
        self._g.setValue(rgb[1])
        # 设置B值
        self._b.setValue(rgb[2])
        # 设置H值
        self._h.setValue(hsv[0])
        # 设置S值
        self._s.setValue(hsv[1])
        # 设置V值
        self._v.setValue(hsv[2])
        # 清除更新标志
        self._updating = False
        # 更新预览
        self._update_preview()

    def set_hsv(self, hsv: tuple[int, int, int]):
        """设置HSV颜色并同步更新RGB和预览

        参数：
            hsv: HSV元组 (H, S, V)
        """
        # 限制HSV值范围
        hsv = (
            max(0, min(179, int(hsv[0]))),   # H: 0-179
            max(0, min(255, int(hsv[1]))),   # S: 0-255
            max(0, min(255, int(hsv[2]))),   # V: 0-255
        )
        # 转换为RGB
        rgb = self._hsv_to_rgb(hsv)
        # 设置更新标志，防止循环更新
        self._updating = True
        # 设置R值
        self._r.setValue(rgb[0])
        # 设置G值
        self._g.setValue(rgb[1])
        # 设置B值
        self._b.setValue(rgb[2])
        # 设置H值
        self._h.setValue(hsv[0])
        # 设置S值
        self._s.setValue(hsv[1])
        # 设置V值
        self._v.setValue(hsv[2])
        # 清除更新标志
        self._updating = False
        # 更新预览
        self._update_preview()

    def get_rgb(self) -> tuple[int, int, int]:
        """获取当前RGB颜色"""
        return self._r.value(), self._g.value(), self._b.value()

    def get_hsv(self) -> tuple[int, int, int]:
        """获取当前HSV颜色"""
        return self._h.value(), self._s.value(), self._v.value()

    def get_color_data(self) -> dict:
        """获取完整的颜色数据

        返回：
            包含rgb、hsv、hex的字典
        """
        return {
            "rgb": self.get_rgb(),      # RGB值
            "hsv": self.get_hsv(),      # HSV值
            "hex": self._hex_edit.text(), # HEX值
        }

    def _on_rgb_changed(self):
        """RGB值改变时的回调"""
        # 如果正在更新中，跳过
        if self._updating:
            return
        # 用当前RGB值更新颜色
        self.set_rgb(self.get_rgb())

    def _on_hsv_changed(self):
        """HSV值改变时的回调"""
        # 如果正在更新中，跳过
        if self._updating:
            return
        # 用当前HSV值更新颜色
        self.set_hsv(self.get_hsv())

    def _update_preview(self):
        """更新预览区域和HEX显示"""
        # 获取当前RGB值
        rgb = self.get_rgb()
        # 格式化为HEX字符串
        hex_value = "#{:02X}{:02X}{:02X}".format(*rgb)
        # 设置HEX编辑框文本
        self._hex_edit.setText(hex_value)
        # 设置预览标签的背景色
        self._preview.setStyleSheet(
            f"border: 1px solid #555; border-radius: 4px; background: {hex_value};"
        )

    def _pick_system_color(self):
        """打开系统颜色选择器"""
        # 获取当前颜色
        color = QColorDialog.getColor(QColor(*self.get_rgb()), self, "选择颜色")
        # 如果选择了有效颜色
        if color.isValid():
            # 设置RGB值
            self.set_rgb((color.red(), color.green(), color.blue()))

    def _start_pick_from_viewer(self):
        """开始从图像取色 — 优先使用静态图像，其次使用ImageViewer"""
        # 如果有静态取色图像（来自HSV节点的输入），弹出ImagePickDialog
        if self._picker_image is not None:
            dlg = ImagePickDialog(self._picker_image, self)
            if dlg.exec_() == QDialog.Accepted and dlg.picked_rgb is not None:
                self.set_rgb(dlg.picked_rgb)
            return

        # 如果没有查看器，返回
        if self._viewer is None:
            return
        # 连接查看器的颜色拾取信号（先断开防止重复连接）
        try:
            self._viewer.color_picked.disconnect(self._on_viewer_color_picked)
        except TypeError:
            pass
        self._viewer.color_picked.connect(self._on_viewer_color_picked)
        # 启用查看器的取色模式
        self._viewer.set_color_pick_mode(True)
        # 改变取色按钮文本
        self._pick_button.setText("点击预览区取色…")
        # 禁用取色按钮
        self._pick_button.setEnabled(False)

    def _stop_pick_from_viewer(self):
        """停止从图像查看器取色"""
        # 如果没有查看器，返回
        if self._viewer is None:
            return
        try:
            # 断开颜色拾取信号连接
            self._viewer.color_picked.disconnect(self._on_viewer_color_picked)
        except TypeError:
            # 如果未连接，忽略异常
            pass
        # 关闭查看器的取色模式
        self._viewer.set_color_pick_mode(False)
        # 恢复取色按钮文本
        self._pick_button.setText("从图像取色")
        # 启用取色按钮
        self._pick_button.setEnabled(True)

    def _on_viewer_color_picked(self, payload: dict):
        """查看器颜色拾取回调

        参数：
            payload: 包含rgb等信息的字典
        """
        # 获取RGB值并设置
        self.set_rgb(tuple(payload.get("rgb", self.get_rgb())))
        # 停止取色模式
        self._stop_pick_from_viewer()

    def closeEvent(self, event):
        """关闭事件回调"""
        # 确保停止取色模式
        self._stop_pick_from_viewer()
        # 调用父类的closeEvent
        super().closeEvent(event)

    @classmethod
    def get_color(cls, rgb: tuple[int, int, int] = (255, 255, 255),
                  viewer=None, picker_image: np.ndarray = None, parent=None) -> dict | None:
        """静态方法：打开颜色选择器对话框并获取颜色

        参数：
            rgb: 初始RGB颜色，默认白色
            viewer: 图像查看器对象
            picker_image: 用于取色的静态图像（BGR格式numpy数组），优先级高于viewer
            parent: 父对象

        返回：
            如果确定则返回颜色数据字典，否则返回None
        """
        # 创建对话框实例
        dialog = cls(rgb=rgb, viewer=viewer, picker_image=picker_image, parent=parent)
        # 如果用户确认
        if dialog.exec_() == QDialog.Accepted:
            # 返回颜色数据
            return dialog.get_color_data()
        # 取消则返回None
        return None