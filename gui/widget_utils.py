"""Qt 工具函数"""

import numpy as np

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSpinBox
from PyQt5.QtGui import QImage, QPixmap


def find_child_by_tip(parent, tip: str):
    """通过 toolTip 文本递归查找可见的子控件，未找到返回 None"""
    try:
        for w in parent.findChildren(QWidget):
            try:
                if w.isVisible() and hasattr(w, 'toolTip') and w.toolTip() == tip:
                    return w
            except Exception:
                continue
    except Exception:
        pass
    return None


def wrap_layout(layout: QHBoxLayout) -> QWidget:
    """将水平布局包装成控件"""
    widget = QWidget()
    widget.setLayout(layout)
    return widget


def set_spin_ranges_from_image(image: np.ndarray | None,
                                size_spins: tuple[QSpinBox, ...],
                                pos_spins: tuple[QSpinBox, ...] = (),
                                extra_spins: tuple[QSpinBox, ...] = ()):
    """根据图像尺寸设置 QSpinBox 的范围

    参数：
        image: 源图像
        size_spins: 尺寸相关输入框（范围 1 到 max(w,h)）
        pos_spins: 位置相关输入框（范围 0 到 max(w,h)）
        extra_spins: 额外的输入框（范围 0 到 max(w,h)）
    """
    if image is None:
        max_dim = 10000
    else:
        h, w = image.shape[:2]
        max_dim = max(w, h)
    for spin in pos_spins + extra_spins:
        spin.setRange(0, max_dim)
    for spin in size_spins:
        spin.setRange(0, max_dim)


def clamp_rect_to_image(r: tuple[int, int, int, int],
                         image: np.ndarray | None) -> tuple[int, int, int, int]:
    """限制矩形区域在图像边界内

    参数：
        r: 矩形元组 (x, y, width, height)
        image: 图像（None 时仅保证宽高≥1）

    返回：
        限制后的矩形元组
    """
    x, y, w, h = [max(0, int(v)) for v in r]
    if image is None:
        return x, y, max(1, w), max(1, h)
    ih, iw = image.shape[:2]
    x = min(x, iw - 1)
    y = min(y, ih - 1)
    w = max(1, min(w, iw - x))
    h = max(1, min(h, ih - y))
    return x, y, w, h


def numpy_to_qimage(array: np.ndarray) -> QImage:
    """将numpy数组（BGR/灰度）转换为QImage"""
    if array is None:
        return QImage()
    h, w = array.shape[:2]
    if len(array.shape) == 2:
        return QImage(array.data, w, h, w, QImage.Format_Grayscale8).copy()
    elif array.shape[2] == 3:
        rgb = array[..., ::-1].copy()
        return QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
    elif array.shape[2] == 4:
        rgba = array[..., [2, 1, 0, 3]].copy()
        return QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888).copy()
    return QImage()


def numpy_to_pixmap(array: np.ndarray) -> QPixmap:
    """将numpy数组转换为QPixmap"""
    return QPixmap.fromImage(numpy_to_qimage(array))
