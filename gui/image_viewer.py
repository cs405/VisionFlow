"""
图像显示控件 - 支持缩放、拖拽、ROI绘制
严格解耦：只通过EventBus与Core层通信
"""

import cv2
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QWheelEvent

from core.events import EventBus, Event, EventType


class ImageGraphicsView(QGraphicsView):
    """图像图形视图"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)

        self.zoom_factor = 1.15
        self.zoom_range = (0.1, 5.0)

    def wheelEvent(self, event: QWheelEvent):
        """鼠标滚轮缩放"""
        if event.modifiers() == Qt.ControlModifier:
            zoom = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
            new_zoom = self.transform().m11() * zoom

            if self.zoom_range[0] <= new_zoom <= self.zoom_range[1]:
                self.scale(zoom, zoom)
        else:
            super().wheelEvent(event)

    def reset_view(self):
        """重置视图"""
        self.resetTransform()
        self.centerOn(0, 0)

    def fit_to_view(self, scene_rect: QRectF):
        """适应视图"""
        if not scene_rect.isNull():
            self.fitInView(scene_rect, Qt.KeepAspectRatio)


class ImageViewer(QWidget):
    """
    图像显示控件
    显示图像，支持缩放、拖拽
    """

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.event_bus = event_bus
        self.current_image = None
        self.pixmap_item = None

        # 订阅事件
        self._subscribe_events()

        # 创建UI
        self._setup_ui()

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.NODE_EXECUTED, self._on_node_executed)
        self.event_bus.subscribe(EventType.IMAGE_UPDATED, self._on_image_updated)

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 工具栏
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #2D2D2D; border-bottom: 1px solid #3D3D3D;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        self.info_label = QLabel("无图像")
        self.info_label.setStyleSheet("color: #A0A0A0;")
        toolbar_layout.addWidget(self.info_label)

        toolbar_layout.addStretch()

        fit_btn = QPushButton("适应窗口")
        fit_btn.setFixedSize(80, 26)
        fit_btn.clicked.connect(self.fit_to_view)
        toolbar_layout.addWidget(fit_btn)

        zoom_in_btn = QPushButton("放大")
        zoom_in_btn.setFixedSize(60, 26)
        zoom_in_btn.clicked.connect(lambda: self._zoom(1.2))
        toolbar_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("缩小")
        zoom_out_btn.setFixedSize(60, 26)
        zoom_out_btn.clicked.connect(lambda: self._zoom(0.8))
        toolbar_layout.addWidget(zoom_out_btn)

        reset_btn = QPushButton("重置")
        reset_btn.setFixedSize(60, 26)
        reset_btn.clicked.connect(self.reset_view)
        toolbar_layout.addWidget(reset_btn)

        layout.addWidget(toolbar)

        # 图形视图
        self.scene = QGraphicsScene()
        self.view = ImageGraphicsView(self)
        self.view.setScene(self.scene)
        layout.addWidget(self.view)

        self.setLayout(layout)

        # 初始占位
        self._show_placeholder()

    def _show_placeholder(self):
        """显示占位符"""
        placeholder = QLabel("暂无图像\n\n请执行工作流或选择图像源节点")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #606060; font-size: 14px; background-color: #252526;")
        placeholder.setFixedSize(400, 300)

        # 清除场景
        self.scene.clear()
        self.scene.addWidget(placeholder)
        self.current_image = None
        self.pixmap_item = None

    def _zoom(self, factor: float):
        """缩放"""
        self.view.scale(factor, factor)

    def numpy_to_qpixmap(self, img: np.ndarray) -> QPixmap:
        """numpy数组转QPixmap"""
        if img is None:
            return None

        img = np.ascontiguousarray(img)

        if len(img.shape) == 2:
            h, w = img.shape
            qimage = QImage(img.data, w, h, w, QImage.Format_Grayscale8)
        elif len(img.shape) == 3:
            h, w, c = img.shape
            if c == 3:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                qimage = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
            elif c == 4:
                rgba = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
                qimage = QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888)
            else:
                return None
        else:
            return None

        return QPixmap.fromImage(qimage)

    def set_image(self, image: np.ndarray, title: str = None):
        """设置显示图像"""
        if image is None:
            return

        pixmap = self.numpy_to_qpixmap(image)
        if pixmap is None:
            return

        self.current_image = image

        # 清除场景
        self.scene.clear()

        # 添加图像
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))

        # 更新信息
        h, w = image.shape[:2]
        info = f"{w} x {h}"
        if len(image.shape) == 3:
            info += f" x {image.shape[2]}"
        if title:
            info = f"{title} | {info}"
        self.info_label.setText(info)

        # 适应视图
        self.view.fit_to_view(self.scene.sceneRect())

    def clear(self):
        """清除图像"""
        self._show_placeholder()
        self.current_image = None
        self.info_label.setText("无图像")

    def fit_to_view(self):
        """适应视图"""
        if self.pixmap_item:
            self.view.fit_in_view(self.scene.sceneRect())

    def reset_view(self):
        """重置视图"""
        self.view.reset_view()
        if self.pixmap_item:
            self.view.fit_in_view(self.scene.sceneRect())

    def _on_node_executed(self, event: Event):
        """节点执行完成"""
        node_id = event.data.get("node_id")
        outputs = event.data.get("outputs", {})

        for name, value in outputs.items():
            if hasattr(value, 'shape') and len(value.shape) in [2, 3]:
                self.set_image(value, f"{node_id[:8]}")
                break

    def _on_image_updated(self, event: Event):
        """图像更新事件"""
        image = event.data.get("image")
        title = event.data.get("title", "")
        if image is not None:
            self.set_image(image, title)

    def get_current_image(self) -> np.ndarray:
        """获取当前图像"""
        return self.current_image