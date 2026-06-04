"""Zoomable image viewer - ported from H.Controls.ZoomBox + ZoomBox.Extension.

Provides: mouse wheel zoom, middle/right drag pan, fit-to-window, pixel info,
overlay layers (ROI boxes, detection boxes, text labels), structured overlay model,
selection highlighting, and zoom-to-rect navigation.
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from PyQt5.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                              QWidget,
                              QVBoxLayout, QLabel, QHBoxLayout)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QPropertyAnimation, QEasingCurve, QVariantAnimation
from PyQt5.QtGui import (QPixmap, QImage, QPen, QColor, QBrush, QPainter,
                          QWheelEvent, QMouseEvent, QFont)


def numpy_to_qimage(array: np.ndarray) -> QImage:
    """Convert numpy array (BGR/grayscale) to QImage."""
    if array is None:
        return QImage()
    h, w = array.shape[:2]
    if len(array.shape) == 2:
        return QImage(array.data, w, h, w, QImage.Format_Grayscale8)
    elif array.shape[2] == 3:
        rgb = array[..., ::-1].copy()
        return QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
    elif array.shape[2] == 4:
        rgba = array[..., [2, 1, 0, 3]].copy()
        return QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888)
    return QImage()


def numpy_to_pixmap(array: np.ndarray) -> QPixmap:
    """Convert numpy array to QPixmap."""
    qimg = numpy_to_qimage(array)
    return QPixmap.fromImage(qimg)


# ── Overlay Model ──────────────────────────────────────────────────────────

class OverlayType(Enum):
    RECT = "rect"
    CIRCLE = "circle"
    LINE = "line"
    TEXT = "text"
    ROI = "roi"
    DETECTION = "detection"


@dataclass
class OverlayItem:
    """Structured overlay metadata for management and hit-testing."""
    uid: str
    type: OverlayType
    geometry: dict  # varies by type: {x, y, w, h} or {cx, cy, r} or {x1,y1,x2,y2}
    label: str = ""
    color: QColor = field(default_factory=lambda: QColor("#0078d4"))
    line_width: int = 2
    score: float = 0.0
    z_value: int = 10
    selected: bool = False
    highlighted: bool = False
    graphics_items: list = field(default_factory=list)  # QGraphicsItem references

    def to_rect(self) -> tuple[int, int, int, int] | None:
        """Get the bounding rect as (x, y, w, h)."""
        geo = self.geometry
        if self.type in (OverlayType.RECT, OverlayType.ROI, OverlayType.DETECTION):
            return (geo.get("x", 0), geo.get("y", 0),
                    geo.get("w", 0), geo.get("h", 0))
        return None


# ── Image Viewer ───────────────────────────────────────────────────────────

class ImageViewer(QGraphicsView):
    """Zoomable, pannable image viewer with structured overlay management.

    Features:
      - Scroll wheel zoom (centered on cursor)
      - Middle/right mouse drag to pan
      - Left click to report pixel coordinates
      - Fit to window / 1:1 zoom
      - Structured overlay model with selection/highlight
      - zoom_to_rect() with animated navigation
      - Color pick mode and ROI pick mode
    """

    # Signals
    pixel_clicked = pyqtSignal(int, int, object)  # x, y, pixel_value
    mouse_moved = pyqtSignal(int, int)             # x, y in image coords
    zoom_changed = pyqtSignal(float)                # zoom factor
    color_picked = pyqtSignal(object)               # dict: rgb/bgr/hsv/hex/x/y
    roi_picked = pyqtSignal(tuple)                  # (x, y, w, h)
    overlay_selected = pyqtSignal(str)              # overlay uid
    overlay_deselected = pyqtSignal()

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

        # State
        self._zoom = 1.0
        self._pan_start: QPointF | None = None
        self._image: np.ndarray | None = None
        self._fit_to_window = True
        self._color_pick_mode = False
        self._roi_pick_mode = False
        self._roi_drag_start: QPointF | None = None
        self._roi_pick_item = None

        # Overlay model
        self._overlays: dict[str, OverlayItem] = {}
        self._selected_uid: str | None = None
        self._overlay_counter = 0

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

        # Mouse tracking
        self.setMouseTracking(True)

    # ── Image Loading ─────────────────────────────────────────────────

    def set_image(self, image: np.ndarray | QPixmap | None):
        """Set the displayed image."""
        self.clear_overlays()
        self.clear_roi_rect()

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

    # ── Zoom ──────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = self.ZOOM_FACTOR if delta > 0 else 1.0 / self.ZOOM_FACTOR
        new_zoom = self._zoom * factor
        if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:
            self._zoom = new_zoom
            self.scale(factor, factor)
            self.zoom_changed.emit(self._zoom)
            self._fit_to_window = False

    def fit_to_window(self):
        if self._pixmap_item.pixmap().isNull():
            return
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()
        self.zoom_changed.emit(self._zoom)
        self._fit_to_window = True

    def zoom_in(self):
        self._zoom = min(self._zoom * self.ZOOM_FACTOR, self.MAX_ZOOM)
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self._fit_to_window = False

    def zoom_out(self):
        self._zoom = max(self._zoom / self.ZOOM_FACTOR, self.MIN_ZOOM)
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self._fit_to_window = False

    def zoom_to_100(self):
        self._zoom = 1.0
        self.resetTransform()
        self._fit_to_window = False

    def set_zoom(self, factor: float):
        self._zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, factor))
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self._fit_to_window = False

    @property
    def zoom_level(self) -> float:
        return self._zoom

    # ── zoom_to_rect ──────────────────────────────────────────────────

    def zoom_to_rect(self, rect: tuple[int, int, int, int],
                     padding: float = 0.1, animate: bool = True):
        """Zoom and pan to center on a specific region.

        Args:
            rect: (x, y, w, h) in image coordinates
            padding: fraction of viewport to pad around the rect
            animate: if True, smoothly animate to the target rect
        """
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return

        pw = w * padding
        ph = h * padding
        target_rect = QRectF(x - pw, y - ph, w + 2 * pw, h + 2 * ph)

        if animate and hasattr(self, '_zoom_anim') and self._zoom_anim is not None:
            self._zoom_anim.stop()

        if animate and not target_rect.isEmpty():
            self._animate_to_rect(target_rect)
        else:
            self.fitInView(target_rect, Qt.KeepAspectRatio)
            self._zoom = self.transform().m11()
            self._fit_to_window = False
            self.zoom_changed.emit(self._zoom)

    def _animate_to_rect(self, target_rect: QRectF):
        """Smoothly animate the view to the target rect."""
        start_rect = self.viewport_rect_in_scene()
        if start_rect.isEmpty():
            self.fitInView(target_rect, Qt.KeepAspectRatio)
            self._zoom = self.transform().m11()
            self._fit_to_window = False
            self.zoom_changed.emit(self._zoom)
            return

        self._zoom_anim = QVariantAnimation(self)
        self._zoom_anim.setDuration(250)  # 250ms smooth animation
        self._zoom_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._zoom_anim.setStartValue(start_rect)
        self._zoom_anim.setEndValue(target_rect)

        def _step(rect):
            self.fitInView(rect, Qt.KeepAspectRatio)
            self._zoom = self.transform().m11()
            self._fit_to_window = False

        self._zoom_anim.valueChanged.connect(_step)
        self._zoom_anim.finished.connect(lambda: (
            self.zoom_changed.emit(self._zoom),
            setattr(self, '_zoom_anim', None)
        ))
        self._zoom_anim.start()

    def viewport_rect_in_scene(self) -> QRectF:
        """Get the currently visible scene rect."""
        return self.mapToScene(self.viewport().rect()).boundingRect()

    # ── Pan ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._roi_pick_mode and not self._pixmap_item.pixmap().isNull():
            self._roi_drag_start = self.mapToScene(event.pos())
            if self._roi_pick_item is None:
                pen = QPen(QColor(0, 120, 212), 2)
                pen.setStyle(Qt.DashLine)
                self._roi_pick_item = self._scene.addRect(QRectF(), pen)
                self._roi_pick_item.setZValue(50)
            self._roi_pick_item.setRect(QRectF(self._roi_drag_start, self._roi_drag_start))
            event.accept()
            return
        if event.button() == Qt.LeftButton and self._color_pick_mode:
            self._emit_pixel_pos(event.pos())
            self._emit_color_info(event.pos())
            event.accept()
            return
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.LeftButton:
            self._emit_pixel_pos(event.pos())
            # Check overlay hit test
            self._hit_test_overlays(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._roi_drag_start is not None and self._roi_pick_mode:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self._roi_drag_start, current_pos).normalized()
            if self._roi_pick_item is not None:
                self._roi_pick_item.setRect(rect)
            event.accept()
            return
        if self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
        else:
            scene_pos = self.mapToScene(event.pos())
            x, y = int(scene_pos.x()), int(scene_pos.y())
            if 0 <= x < self._scene.width() and 0 <= y < self._scene.height():
                self.mouse_moved.emit(x, y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self._roi_drag_start is not None and self._roi_pick_mode:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self._roi_drag_start, current_pos).normalized()
            self._roi_drag_start = None
            roi_rect = self._scene_rect_to_tuple(rect)
            if self._roi_pick_item is not None:
                self._scene.removeItem(self._roi_pick_item)
                self._roi_pick_item = None
            if roi_rect[2] > 0 and roi_rect[3] > 0:
                self.roi_picked.emit(roi_rect)
            event.accept()
            return
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.fit_to_window()
        super().mouseDoubleClickEvent(event)

    def _emit_pixel_pos(self, pos: QPointF):
        scene_pos = self.mapToScene(pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())
        if self._image is not None and 0 <= y < self._image.shape[0] and 0 <= x < self._image.shape[1]:
            pixel_val = self._image[y, x].tolist()
            self.pixel_clicked.emit(x, y, pixel_val)

    def _emit_color_info(self, pos: QPointF):
        scene_pos = self.mapToScene(pos)
        x, y = int(scene_pos.x()), int(scene_pos.y())
        self.pick_color_at(x, y)

    def pick_color_at(self, x: int, y: int) -> dict | None:
        """Pick a color directly from image coordinates."""
        if self._image is None or not (0 <= y < self._image.shape[0] and 0 <= x < self._image.shape[1]):
            return
        pixel = self._image[y, x]
        if np.isscalar(pixel):
            gray = int(pixel)
            bgr = (gray, gray, gray)
        else:
            values = [int(v) for v in pixel.tolist()]
            if len(values) >= 3:
                bgr = tuple(values[:3])
            elif len(values) == 1:
                bgr = (values[0], values[0], values[0])
            else:
                return
        hsv = cv2.cvtColor(np.array([[bgr]], dtype=np.uint8), cv2.COLOR_BGR2HSV)[0, 0].tolist()
        rgb = (bgr[2], bgr[1], bgr[0])
        payload = {
            "x": x, "y": y,
            "bgr": bgr, "rgb": rgb,
            "hsv": tuple(int(v) for v in hsv),
            "hex": "#{:02X}{:02X}{:02X}".format(*rgb),
        }
        self.color_picked.emit(payload)
        return payload

    def _scene_rect_to_tuple(self, rect: QRectF) -> tuple[int, int, int, int]:
        if self._image is None:
            return (int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
        max_w = self._image.shape[1]
        max_h = self._image.shape[0]
        x1 = max(0, min(int(round(rect.left())), max_w))
        y1 = max(0, min(int(round(rect.top())), max_h))
        x2 = max(0, min(int(round(rect.right())), max_w))
        y2 = max(0, min(int(round(rect.bottom())), max_h))
        return (x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    # ── Color/ROI Pick Mode ───────────────────────────────────────────

    def set_color_pick_mode(self, enabled: bool):
        self._color_pick_mode = enabled
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)

    def set_roi_pick_mode(self, enabled: bool):
        self._roi_pick_mode = enabled
        if not enabled:
            self._roi_drag_start = None
            if self._roi_pick_item is not None:
                self._scene.removeItem(self._roi_pick_item)
                self._roi_pick_item = None
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)

    # ── ROI Overlay ───────────────────────────────────────────────────

    def clear_roi_rect(self):
        """Remove the fixed-position ROI overlay."""
        for item in getattr(self, '_roi_overlay_items', []):
            self._scene.removeItem(item)
        self._roi_overlay_items = []

    def set_roi_rect(self, rect: tuple[int, int, int, int] | None,
                     label: str = "ROI",
                     color: QColor = QColor(0, 120, 212)):
        self.clear_roi_rect()
        if not hasattr(self, '_roi_overlay_items'):
            self._roi_overlay_items = []
        if rect is None:
            return
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return

        pen = QPen(color, 2)
        pen.setStyle(Qt.DashLine)
        item = self._scene.addRect(x, y, w, h, pen)
        item.setZValue(40)
        self._roi_overlay_items.append(item)

        if label:
            text = self._scene.addText(label, QFont("Segoe UI", 10))
            text.setPos(x, max(0, y - 20))
            text.setDefaultTextColor(color)
            text.setZValue(41)
            self._roi_overlay_items.append(text)

    # ── Structured Overlay Model ──────────────────────────────────────

    def add_rect_overlay(self, rect: tuple, label: str = "",
                         color: QColor = QColor(0, 120, 212),
                         score: float = 0.0,
                         overlay_type: OverlayType = OverlayType.RECT) -> str:
        """Add a rectangle overlay with structured tracking.

        Returns a unique overlay ID that can be used for selection/highlight/removal.
        """
        self._overlay_counter += 1
        uid = f"overlay_{self._overlay_counter}"
        x, y, w, h = rect

        pen = QPen(color, 2)
        pen.setStyle(Qt.DashLine if overlay_type == OverlayType.ROI else Qt.SolidLine)
        rect_item = self._scene.addRect(x, y, w, h, pen)
        rect_item.setZValue(10)
        gfx_items = [rect_item]

        if label or score > 0:
            text_str = f"{label} {score:.2f}" if score > 0 else label
            text_item = self._scene.addText(text_str, QFont("Segoe UI", 9))
            text_item.setPos(x, y - 18)
            text_item.setDefaultTextColor(color)
            text_item.setZValue(11)
            gfx_items.append(text_item)

        overlay = OverlayItem(
            uid=uid,
            type=overlay_type,
            geometry={"x": x, "y": y, "w": w, "h": h},
            label=label,
            color=color,
            score=score,
            graphics_items=gfx_items,
        )
        self._overlays[uid] = overlay
        return uid

    def add_circle_overlay(self, center: tuple, radius: float,
                            label: str = "",
                            color: QColor = QColor(76, 175, 80)) -> str:
        """Add a circle overlay with structured tracking."""
        self._overlay_counter += 1
        uid = f"overlay_{self._overlay_counter}"
        cx, cy = center

        pen = QPen(color, 2)
        item = self._scene.addEllipse(cx - radius, cy - radius,
                                       radius * 2, radius * 2, pen)
        item.setZValue(10)
        gfx_items = [item]

        if label:
            text_item = self._scene.addText(label, QFont("Segoe UI", 9))
            text_item.setPos(cx - radius, cy - radius - 18)
            text_item.setDefaultTextColor(color)
            text_item.setZValue(11)
            gfx_items.append(text_item)

        overlay = OverlayItem(
            uid=uid,
            type=OverlayType.CIRCLE,
            geometry={"cx": cx, "cy": cy, "r": radius},
            label=label,
            color=color,
            graphics_items=gfx_items,
        )
        self._overlays[uid] = overlay
        return uid

    def add_line_overlay(self, x1: float, y1: float, x2: float, y2: float,
                          label: str = "",
                          color: QColor = QColor(255, 152, 0)) -> str:
        """Add a line overlay with structured tracking."""
        self._overlay_counter += 1
        uid = f"overlay_{self._overlay_counter}"
        pen = QPen(color, 1)
        item = self._scene.addLine(x1, y1, x2, y2, pen)
        item.setZValue(10)
        gfx_items = [item]

        if label:
            text_item = self._scene.addText(label, QFont("Segoe UI", 9))
            text_item.setPos(x1, y1 - 18)
            text_item.setDefaultTextColor(color)
            text_item.setZValue(11)
            gfx_items.append(text_item)

        overlay = OverlayItem(
            uid=uid,
            type=OverlayType.LINE,
            geometry={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            label=label,
            color=color,
            graphics_items=gfx_items,
        )
        self._overlays[uid] = overlay
        return uid

    def remove_overlay(self, uid: str):
        """Remove a single overlay by ID."""
        overlay = self._overlays.pop(uid, None)
        if overlay:
            for item in overlay.graphics_items:
                self._scene.removeItem(item)
            if self._selected_uid == uid:
                self._clear_selection()

    def clear_overlays(self):
        """Remove all structured overlays."""
        for overlay in list(self._overlays.values()):
            for item in overlay.graphics_items:
                self._scene.removeItem(item)
        self._overlays.clear()
        self._clear_selection()

    # ── Selection & Highlight ─────────────────────────────────────────

    def select_overlay(self, uid: str):
        """Select an overlay and apply visual highlight."""
        if uid == self._selected_uid:
            return
        self._clear_selection()
        overlay = self._overlays.get(uid)
        if overlay is None:
            return
        overlay.selected = True
        self._selected_uid = uid

        # Visual: redraw with highlight color
        highlight_color = QColor("#FFD700")  # Gold
        for item in overlay.graphics_items[:1]:  # Main rect/ellipse/line
            pen = item.pen()
            pen.setColor(highlight_color)
            pen.setWidth(3)
            item.setPen(pen)

        self.overlay_selected.emit(uid)

    def deselect_overlay(self):
        """Deselect current overlay."""
        self._clear_selection()
        self.overlay_deselected.emit()

    def _clear_selection(self):
        if self._selected_uid and self._selected_uid in self._overlays:
            overlay = self._overlays[self._selected_uid]
            overlay.selected = False
            for item in overlay.graphics_items[:1]:
                pen = item.pen()
                pen.setColor(overlay.color)
                pen.setWidth(overlay.line_width)
                item.setPen(pen)
        self._selected_uid = None

    def highlight_overlay(self, uid: str, highlight_color: QColor = QColor("#FFD700"),
                          duration_ms: int = 2000):
        """Temporarily highlight an overlay (useful for result panel linkage).

        After duration_ms, the highlight fades back to the original color.
        """
        overlay = self._overlays.get(uid)
        if overlay is None:
            return

        # Zoom to it
        rect = overlay.to_rect()
        if rect:
            self.zoom_to_rect(rect, padding=0.2, animate=True)

        for item in overlay.graphics_items[:1]:
            pen = item.pen()
            pen.setColor(highlight_color)
            pen.setWidth(4)
            item.setPen(pen)

        # Restore after duration
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(duration_ms, lambda: self._restore_highlight(uid))

    def _restore_highlight(self, uid: str):
        overlay = self._overlays.get(uid)
        if overlay and not overlay.selected:
            for item in overlay.graphics_items[:1]:
                pen = item.pen()
                pen.setColor(overlay.color)
                pen.setWidth(overlay.line_width)
                item.setPen(pen)

    def _hit_test_overlays(self, view_pos: QPointF):
        """Check if a click hits any overlay and select it."""
        scene_pos = self.mapToScene(view_pos)
        x, y = scene_pos.x(), scene_pos.y()

        for uid, overlay in reversed(list(self._overlays.items())):
            geo = overlay.geometry
            if overlay.type in (OverlayType.RECT, OverlayType.ROI, OverlayType.DETECTION):
                gx, gy, gw, gh = geo.get("x", 0), geo.get("y", 0), geo.get("w", 0), geo.get("h", 0)
                if gx <= x <= gx + gw and gy <= y <= gy + gh:
                    self.select_overlay(uid)
                    return
            elif overlay.type == OverlayType.CIRCLE:
                cx, cy, r = geo.get("cx", 0), geo.get("cy", 0), geo.get("r", 0)
                if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                    self.select_overlay(uid)
                    return

        self.deselect_overlay()

    # ── Legacy convenience methods ────────────────────────────────────

    def add_roi_overlay(self, rect: tuple, label: str = "",
                         color: QColor = QColor(0, 120, 212)):
        """Legacy method - add an ROI rectangle overlay."""
        return self.add_rect_overlay(rect, label, color, overlay_type=OverlayType.ROI)

    def add_detection_overlay(self, rect: tuple, label: str = "",
                               color: QColor = QColor(76, 175, 80),
                               score: float = 0.0):
        """Legacy method - add a detection bounding box overlay."""
        return self.add_rect_overlay(rect, label, color, score=score,
                                     overlay_type=OverlayType.DETECTION)

    def get_overlay(self, uid: str) -> OverlayItem | None:
        """Get overlay metadata by ID."""
        return self._overlays.get(uid)

    def get_all_overlays(self) -> dict[str, OverlayItem]:
        return dict(self._overlays)

    # ── Video frame support ──────────────────────────────────────────

    def show_video_frame(self, frame: np.ndarray, frame_index: int = 0,
                          total_frames: int = 0, fps: float = 0.0):
        """Display a video frame with overlay indicator.

        Args:
            frame: numpy array (BGR)
            frame_index: current frame number (0-based)
            total_frames: total frames in video
            fps: frames per second
        """
        self.set_image(frame)
        if total_frames > 0:
            info = f"视频帧 {frame_index + 1}/{total_frames}"
            if fps > 0:
                info += f" @ {fps:.1f} FPS"
            self._show_frame_overlay(info)

    def _show_frame_overlay(self, text: str):
        """Show a semi-transparent overlay with frame info at the top-left."""
        self._clear_frame_overlay()
        overlay = self._scene.addRect(0, 0, 300, 28, QPen(Qt.NoPen),
                                       QBrush(QColor(0, 0, 0, 140)))
        overlay.setZValue(100)
        self._frame_overlay_items = [overlay]
        txt = self._scene.addText(text, QFont("Segoe UI", 10))
        txt.setDefaultTextColor(QColor("#00ff00"))
        txt.setPos(6, 4)
        txt.setZValue(101)
        self._frame_overlay_items.append(txt)

    def _clear_frame_overlay(self):
        for item in getattr(self, '_frame_overlay_items', []):
            self._scene.removeItem(item)
        self._frame_overlay_items = []

    def clear_video_frame(self):
        """Remove video frame overlay."""
        self._clear_frame_overlay()

    # ── Resize ────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_to_window and not self._pixmap_item.pixmap().isNull():
            self.fit_to_window()


# ── Image Viewer Panel ─────────────────────────────────────────────────────

class ImageViewerPanel(QWidget):
    """Panel wrapper around ImageViewer with info bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.viewer = ImageViewer()
        layout.addWidget(self.viewer)

        # Info bar
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(8, 2, 8, 2)

        self._pos_label = QLabel("位置: -")
        self._pos_label.setStyleSheet("font-size: 11px; color: #999;")
        info_layout.addWidget(self._pos_label)

        info_layout.addStretch()

        self._size_label = QLabel("尺寸: -")
        self._size_label.setStyleSheet("font-size: 11px; color: #999;")
        info_layout.addWidget(self._size_label)

        self._zoom_label = QLabel("缩放: 100%")
        self._zoom_label.setStyleSheet("font-size: 11px; color: #999;")
        info_layout.addWidget(self._zoom_label)

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
            self._size_label.setText(f"尺寸: {w} x {h}")
        else:
            self._size_label.setText("尺寸: -")

    def set_roi_rect(self, rect: tuple[int, int, int, int] | None, label: str = "ROI"):
        self.viewer.set_roi_rect(rect, label=label)

    def clear_roi_rect(self):
        self.viewer.clear_roi_rect()

    def _on_mouse_moved(self, x: int, y: int):
        self._pos_label.setText(f"位置: ({x}, {y})")

    def _on_zoom_changed(self, zoom: float):
        self._zoom_label.setText(f"缩放: {zoom * 100:.0f}%")

    def _on_pixel_clicked(self, x: int, y: int, value: object):
        self._pos_label.setText(f"位置: ({x}, {y}) | 值: {value}")
