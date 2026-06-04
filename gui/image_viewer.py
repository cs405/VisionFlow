"""
图像显示控件 — WPF Zoombox风格
支持缩放、拖拽、自动适应、棋盘格背景、信息覆盖层
"""

import cv2
import numpy as np
from PySide6.QtWidgets import (
    QWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt, QRectF, QPointF, QSize, Signal
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QWheelEvent,
    QBrush
)

from core.events import EventBus, Event, EventType

from .theme import Colors


class ZoomboxGraphicsView(QGraphicsView):
    """Zoombox风格图形视图 — 支持双击适应、缩放范围限制"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setFocusPolicy(Qt.StrongFocus)

        self.zoom_factor = 1.15
        self.min_scale = 0.1
        self.max_scale = 5.0
        self._current_scale = 1.0

    def wheelEvent(self, event: QWheelEvent):
        """Ctrl+滚轮缩放"""
        if event.modifiers() == Qt.ControlModifier:
            zoom = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
            new_zoom = self._current_scale * zoom

            if self.min_scale <= new_zoom <= self.max_scale:
                self.scale(zoom, zoom)
                self._current_scale = new_zoom
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        """双击适应视图"""
        self.fit_to_bounds()
        super().mouseDoubleClickEvent(event)

    def fit_to_bounds(self):
        """适应内容(FitToBounds)"""
        scene = self.scene()
        if scene and not scene.sceneRect().isNull():
            self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
            self._current_scale = self.transform().m11()

    def reset_view(self):
        """重置缩放"""
        self.resetTransform()
        self._current_scale = 1.0
        self.centerOn(0, 0)

    def resizeEvent(self, event):
        """窗口大小改变时自动适应"""
        super().resizeEvent(event)
        self.fit_to_bounds()


class ImageViewer(QWidget):
    """WPF Zoombox风格图像查看器"""

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus
        self.current_image = None
        self.pixmap_item = None

        self._setup_ui()
        self._subscribe_events()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 图像显示区 (必须在工具栏之前创建，因为按钮回调引用 self.view)
        self.scene = QGraphicsScene()
        self.view = ZoomboxGraphicsView(self)

        # 设置棋盘格背景
        self._setup_checkerboard_background()

        self.view.setScene(self.scene)

        # 工具栏
        toolbar = QWidget()
        toolbar.setStyleSheet(f"""
            background-color: {Colors.BackgroundLight};
            border-bottom: 1px solid {Colors.Border};
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 3, 8, 3)
        toolbar_layout.setSpacing(4)

        self.info_label = QLabel("无图像")
        self.info_label.setStyleSheet(f"color: {Colors.ForegroundDim}; font-size: 10px;")
        toolbar_layout.addWidget(self.info_label)
        toolbar_layout.addStretch()

        btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {Colors.ForegroundDim};
                border: 1px solid {Colors.Border};
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background: {Colors.BorderLight};
                color: {Colors.Foreground};
            }}
        """

        fit_btn = QPushButton("适应")
        fit_btn.setStyleSheet(btn_style)
        fit_btn.clicked.connect(self.fit_to_view)
        toolbar_layout.addWidget(fit_btn)

        for text, factor in [("+", 1.2), ("-", 0.8), ("1:1", 0)]:
            btn = QPushButton(text)
            btn.setStyleSheet(btn_style)
            if factor:
                btn.clicked.connect(lambda checked, f=factor: self.view.scale(f, f))
            else:
                btn.clicked.connect(self.view.reset_view)
            toolbar_layout.addWidget(btn)

        layout.addWidget(toolbar)
        layout.addWidget(self.view)

        self.setLayout(layout)

        # 显示占位
        self._show_placeholder()

    def _setup_checkerboard_background(self):
        """设置棋盘格背景(Tile25)"""
        self.view.setStyleSheet(f"""
            QGraphicsView {{
                background-color: {Colors.BackgroundDark};
                border: none;
            }}
        """)

    def _show_placeholder(self):
        """显示占位符"""
        self.scene.clear()
        placeholder = QLabel("无图像\n\n请执行工作流或选择图像源")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            f"color: {Colors.ForegroundDark}; font-size: 13px; "
            f"background-color: {Colors.BackgroundDark};"
        )
        placeholder.setFixedSize(350, 200)
        self.scene.addWidget(placeholder)
        self.current_image = None
        self.pixmap_item = None

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
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))

        # 更新信息标签
        h, w = image.shape[:2]
        channels = image.shape[2] if len(image.shape) == 3 else 1
        info = f"{w}×{h}  {channels}ch"
        if title:
            info = f"{title}  |  {info}"
        self.info_label.setText(info)

        # 自动适应
        self.view.fit_to_bounds()

    def clear(self):
        self._show_placeholder()
        self.current_image = None
        self.info_label.setText("无图像")

    def fit_to_view(self):
        self.view.fit_to_bounds()

    def reset_view(self):
        self.view.reset_view()
        if self.pixmap_item:
            self.view.fit_to_bounds()

    def _subscribe_events(self):
        self.event_bus.subscribe(EventType.NODE_EXECUTED, self._on_node_executed)
        self.event_bus.subscribe(EventType.IMAGE_UPDATED, self._on_image_updated)

    def _on_node_executed(self, event: Event):
        outputs = event.data.get("outputs", {})
        for value in outputs.values():
            if hasattr(value, 'shape') and len(value.shape) in [2, 3]:
                self.set_image(value, f"节点 {event.data.get('node_id', '')[:8]}")
                break

    def _on_image_updated(self, event: Event):
        image = event.data.get("image")
        title = event.data.get("title", "")
        if image is not None:
            self.set_image(image, title)

    def get_current_image(self) -> np.ndarray:
        return self.current_image
