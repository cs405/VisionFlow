"""
图像显示控件 - 支持缩放、拖拽、ROI绘制
"""

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor

from core.events import EventBus, Event, EventType


class ImageViewer(QWidget):
    """图像显示控件"""

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.current_image: np.ndarray = None
        self.pixmap_item = None
        self.zoom_factor = 1.0

        self.setMinimumSize(300, 300)

        # 创建布局
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()
        self.info_label = QLabel("无图像")
        toolbar.addWidget(self.info_label)
        toolbar.addStretch()

        reset_btn = QPushButton("适应窗口")
        reset_btn.clicked.connect(self.fit_to_view)
        toolbar.addWidget(reset_btn)

        zoom_in_btn = QPushButton("放大")
        zoom_in_btn.clicked.connect(lambda: self.zoom(1.2))
        toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("缩小")
        zoom_out_btn.clicked.connect(lambda: self.zoom(0.8))
        toolbar.addWidget(zoom_out_btn)

        layout.addLayout(toolbar)

        # 图形视图
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        layout.addWidget(self.view)
        self.setLayout(layout)

        # 订阅事件
        self._subscribe_events()

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.IMAGE_UPDATED, self._on_image_updated)
        self.event_bus.subscribe(EventType.NODE_EXECUTED, self._on_node_executed)

    def _on_image_updated(self, event: Event):
        """图像更新事件"""
        image = event.data.get("image")
        if image is not None:
            self.set_image(image)

    def _on_node_executed(self, event: Event):
        """节点执行完成"""
        outputs = event.data.get("outputs", {})
        for name, value in outputs.items():
            if hasattr(value, 'shape') and len(value.shape) in [2, 3]:
                self.set_image(value, f"{event.data.get('node_id', '')[:8]}:{name}")
                break

    def numpy_to_qpixmap(self, img: np.ndarray) -> QPixmap:
        """numpy数组转QPixmap"""
        if img is None:
            return None

        # 确保图像是连续的
        img = np.ascontiguousarray(img)

        if len(img.shape) == 2:  # 灰度图
            height, width = img.shape
            bytes_per_line = width
            qimage = QImage(img.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
        elif len(img.shape) == 3:
            height, width, channels = img.shape
            bytes_per_line = width * channels

            if channels == 3:  # BGR
                # BGR转RGB
                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                qimage = QImage(rgb_img.data, width, height, bytes_per_line, QImage.Format_RGB888)
            elif channels == 4:  # BGRA
                rgba_img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                qimage = QImage(rgba_img.data, width, height, bytes_per_line, QImage.Format_RGBA8888)
            else:
                return None
        else:
            return None

        return QPixmap.fromImage(qimage)

    def set_image(self, image: np.ndarray, title: str = None):
        """设置显示图像"""
        if image is None:
            return

        self.current_image = image

        pixmap = self.numpy_to_qpixmap(image)
        if pixmap is None:
            return

        # 清除旧项
        if self.pixmap_item:
            self.scene.removeItem(self.pixmap_item)

        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))

        # 更新信息
        h, w = image.shape[:2]
        info = f"{w} x {h}"
        if len(image.shape) == 3:
            info += f", {image.shape[2]}通道"
        self.info_label.setText(info)

        # 适应视图
        self.fit_to_view()

    def fit_to_view(self):
        """适应视图大小"""
        if self.pixmap_item:
            self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
            self.zoom_factor = self.view.transform().m11()

    def zoom(self, factor: float):
        """缩放"""
        self.view.scale(factor, factor)
        self.zoom_factor *= factor

    def clear(self):
        """清除图像"""
        if self.pixmap_item:
            self.scene.removeItem(self.pixmap_item)
            self.pixmap_item = None
        self.current_image = None
        self.info_label.setText("无图像")

    def get_current_image(self) -> np.ndarray:
        """获取当前图像"""
        return self.current_image