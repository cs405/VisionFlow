"""Zoomable image viewer - ported from H.Controls.ZoomBox + ZoomBox.Extension.

Provides: mouse wheel zoom, middle/right drag pan, fit-to-window, pixel info,
overlay layers (ROI boxes, detection boxes, text labels).
"""

import numpy as np
from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                              QGraphicsRectItem, QGraphicsTextItem, QWidget,
                              QVBoxLayout, QLabel, QHBoxLayout)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import (QPixmap, QImage, QPen, QColor, QBrush, QPainter,
                          QWheelEvent, QMouseEvent, QFont, QTransform)


def numpy_to_qimage(array: np.ndarray) -> QImage:
    """Convert numpy array (BGR/grayscale) to QImage."""
    if array is None:
        return QImage()
    h, w = array.shape[:2]
    if len(array.shape) == 2:
        # Grayscale
        return QImage(array.data, w, h, w, QImage.Format_Grayscale8)
    elif array.shape[2] == 3:
        # BGR -> RGB
        rgb = array[..., ::-1].copy()
        return QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
    elif array.shape[2] == 4:
        # BGRA -> RGBA
        rgba = array[..., [2, 1, 0, 3]].copy()
        return QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888)
    return QImage()


def numpy_to_pixmap(array: np.ndarray) -> QPixmap:
    """Convert numpy array to QPixmap."""
    qimg = numpy_to_qimage(array)
    return QPixmap.fromImage(qimg)


class ImageViewer(QGraphicsView):
    """Zoomable, pannable image viewer.

    Features:
      - Scroll wheel zoom (centered on cursor)
      - Middle/right mouse drag to pan
      - Left click to report pixel coordinates
      - Fit to window
      - Overlay layer support (ROI, detection boxes, labels)
    """

    # Signals
    pixel_clicked = pyqtSignal(int, int, object)  # x, y, pixel_value
    mouse_moved = pyqtSignal(int, int)             # x, y in image coords
    zoom_changed = pyqtSignal(float)                # zoom factor

    MIN_ZOOM = 0.01
    MAX_ZOOM = 50.0
    ZOOM_FACTOR = 1.15

    def __init__(self, parent=None):
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Main image item
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        # Overlay items
        self._overlay_items: list = []

        # State
        self._zoom = 1.0
        self._pan_start: QPointF | None = None
        self._image: np.ndarray | None = None
        self._fit_to_window = True

        # View settings
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.NoFrame)

        # Background
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))

        # Enable mouse tracking for pixel position
        self.setMouseTracking(True)

    # -- Image loading --

    def set_image(self, image: np.ndarray | QPixmap | None):
        """Set the displayed image."""
        self.clear_overlays()

        if image is None:
            self._pixmap_item.setPixmap(QPixmap())
            self._image = None
            self._scene.setSceneRect(QRectF())
            return

        if isinstance(image, np.ndarray):
            self._image = image
            pixmap = numpy_to_pixmap(image)
        elif isinstance(image, QPixmap):
            pixmap = image
            self._image = None
        else:
            return

        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(pixmap.rect()))

        if self._fit_to_window:
            self.fit_to_window()

    @property
    def image(self) -> np.ndarray | None:
        return self._image

    # -- Zoom --

    def wheelEvent(self, event: QWheelEvent):
        """Zoom with mouse wheel."""
        delta = event.angleDelta().y()
        if delta > 0:
            factor = self.ZOOM_FACTOR
        else:
            factor = 1.0 / self.ZOOM_FACTOR

        new_zoom = self._zoom * factor
        if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:
            self._zoom = new_zoom
            self.scale(factor, factor)
            self.zoom_changed.emit(self._zoom)
            self._fit_to_window = False

    def fit_to_window(self):
        """Fit the entire image in the viewport."""
        if self._pixmap_item.pixmap().isNull():
            return
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()
        self.zoom_changed.emit(self._zoom)
        self._fit_to_window = True

    def zoom_in(self):
        """Zoom in one step."""
        self._zoom = min(self._zoom * self.ZOOM_FACTOR, self.MAX_ZOOM)
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self._fit_to_window = False

    def zoom_out(self):
        """Zoom out one step."""
        self._zoom = max(self._zoom / self.ZOOM_FACTOR, self.MIN_ZOOM)
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self._fit_to_window = False

    def zoom_to_100(self):
        """Reset to 100% zoom."""
        self._zoom = 1.0
        self.resetTransform()
        self._fit_to_window = False

    def set_zoom(self, factor: float):
        """Set a specific zoom level."""
        self._zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, factor))
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self._fit_to_window = False

    @property
    def zoom_level(self) -> float:
        return self._zoom

    # -- Pan --

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.LeftButton:
            self._emit_pixel_pos(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        else:
            # Emit pixel position on mouse move
            scene_pos = self.mapToScene(event.pos())
            x, y = int(scene_pos.x()), int(scene_pos.y())
            if 0 <= x < self._scene.width() and 0 <= y < self._scene.height():
                self.mouse_moved.emit(x, y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double click to fit to window."""
        if event.button() == Qt.LeftButton:
            self.fit_to_window()
        super().mouseDoubleClickEvent(event)

    def _emit_pixel_pos(self, pos: QPointF):
        """Emit pixel coordinates for a view position."""
        scene_pos = self.mapToScene(pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())
        if self._image is not None and 0 <= y < self._image.shape[0] and 0 <= x < self._image.shape[1]:
            pixel_val = self._image[y, x].tolist()
            self.pixel_clicked.emit(x, y, pixel_val)

    # -- Overlays --

    def add_roi_overlay(self, rect: tuple, label: str = "",
                         color: QColor = QColor(0, 120, 212)):
        """Add an ROI rectangle overlay. rect = (x, y, w, h)."""
        x, y, w, h = rect
        pen = QPen(color, 2)
        pen.setStyle(Qt.DashLine)
        item = self._scene.addRect(x, y, w, h, pen)
        item.setZValue(10)
        self._overlay_items.append(item)

        if label:
            text = self._scene.addText(label, QFont("Segoe UI", 10))
            text.setPos(x, y - 20)
            text.setDefaultTextColor(color)
            text.setZValue(11)
            self._overlay_items.append(text)
        return item

    def add_detection_overlay(self, rect: tuple, label: str = "",
                               color: QColor = QColor(76, 175, 80),
                               score: float = 0.0):
        """Add a detection bounding box overlay. rect = (x, y, w, h)."""
        x, y, w, h = rect
        pen = QPen(color, 2)
        pen.setStyle(Qt.SolidLine)
        item = self._scene.addRect(x, y, w, h, pen, QBrush(Qt.NoBrush))
        item.setZValue(10)
        self._overlay_items.append(item)

        text_str = label
        if score > 0:
            text_str = f"{label} {score:.2f}"
        text = self._scene.addText(text_str, QFont("Segoe UI", 9))
        text.setPos(x, y - 18)
        text.setDefaultTextColor(color)
        text.setZValue(11)
        self._overlay_items.append(text)
        return item

    def add_circle_overlay(self, center: tuple, radius: float,
                            color: QColor = QColor(76, 175, 80)):
        """Add a circle overlay."""
        cx, cy = center
        pen = QPen(color, 2)
        item = self._scene.addEllipse(cx - radius, cy - radius,
                                       radius * 2, radius * 2, pen)
        item.setZValue(10)
        self._overlay_items.append(item)
        return item

    def add_line_overlay(self, x1: float, y1: float, x2: float, y2: float,
                          color: QColor = QColor(255, 152, 0)):
        """Add a line overlay."""
        pen = QPen(color, 1)
        item = self._scene.addLine(x1, y1, x2, y2, pen)
        item.setZValue(10)
        self._overlay_items.append(item)
        return item

    def clear_overlays(self):
        """Remove all overlays while keeping the main image."""
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()

    # -- Resize --

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_to_window and not self._pixmap_item.pixmap().isNull():
            self.fit_to_window()


class ImageViewerPanel(QWidget):
    """Panel wrapper around ImageViewer with info bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main image viewer
        self.viewer = ImageViewer()
        layout.addWidget(self.viewer)

        # Info bar at bottom
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(8, 2, 8, 2)

        self.pos_label = QLabel("位置: -")
        self.pos_label.setStyleSheet("font-size: 11px; color: #999;")
        info_layout.addWidget(self.pos_label)

        info_layout.addStretch()

        self.size_label = QLabel("尺寸: -")
        self.size_label.setStyleSheet("font-size: 11px; color: #999;")
        info_layout.addWidget(self.size_label)

        self.zoom_label = QLabel("缩放: 100%")
        self.zoom_label.setStyleSheet("font-size: 11px; color: #999;")
        info_layout.addWidget(self.zoom_label)

        info_widget = QWidget()
        info_widget.setLayout(info_layout)
        info_widget.setStyleSheet("background: #252526; border-top: 1px solid #3f3f46;")
        layout.addWidget(info_widget)

        # Connect signals
        self.viewer.mouse_moved.connect(self._on_mouse_moved)
        self.viewer.zoom_changed.connect(self._on_zoom_changed)
        self.viewer.pixel_clicked.connect(self._on_pixel_clicked)

    def set_image(self, image: np.ndarray | None):
        self.viewer.set_image(image)
        if image is not None:
            h, w = image.shape[:2]
            self.size_label.setText(f"尺寸: {w} x {h}")

    def _on_mouse_moved(self, x: int, y: int):
        self.pos_label.setText(f"位置: ({x}, {y})")

    def _on_zoom_changed(self, zoom: float):
        self.zoom_label.setText(f"缩放: {zoom * 100:.0f}%")

    def _on_pixel_clicked(self, x: int, y: int, value: object):
        self.pos_label.setText(f"位置: ({x}, {y}) | 值: {value}")
