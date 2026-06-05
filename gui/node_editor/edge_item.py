"""Edge (link) graphics item — WPF LineLinkDrawer / BrokenLinkDrawer port.

Ported from H.Controls.Diagram Link + ILinkDrawer.
Straight-line or orthogonal path with arrow at target, driven by port dock positions.
"""

import math
from PyQt5.QtWidgets import (QGraphicsObject, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget, QGraphicsItem,
                              QGraphicsTextItem)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainterPath, QPainter,
                          QPainterPathStroker, QFont, QPolygonF)

from core.node_base import LinkData, PortDock

EDGE_COLOR = QColor("#FF8C00")
EDGE_COLOR_SELECTED = QColor("#FFA726")
EDGE_COLOR_HOVER = QColor("#FFB74D")
EDGE_WIDTH = 2.0
EDGE_WIDTH_HOVER = 3.0
EDGE_WIDTH_SELECTED = 2.5
ARROW_SIZE = 8.0


class EdgeItem(QGraphicsObject):
    """Straight-line / orthogonal edge between two SocketItems.

    WPF alignment: LineLinkDrawer + BrokenLinkDrawer.
    No Bezier — straight segments between port center points.
    """

    edge_selected = pyqtSignal(object)

    def __init__(self, from_socket, to_socket=None, link_data=None, parent=None):
        super().__init__(parent)
        self.from_socket = from_socket
        self.to_socket = to_socket
        self.link_data = link_data
        self._hovered = False
        self._temp_end = None
        self._label_item = None
        self._path = QPainterPath()
        self._pen = QPen(EDGE_COLOR, EDGE_WIDTH)
        self._arrow_poly = QPolygonF()

        self.setZValue(5)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsObject.ItemIsSelectable, True)

        self._rebuild()
        if self.link_data and self.link_data.text:
            self.set_label(self.link_data.text)

        from_socket.add_edge(self)
        if to_socket:
            to_socket.add_edge(self)

    # ── Path ─────────────────────────────────────────────────────────────

    def _get_start(self):
        try:
            return self.from_socket.get_center_scene_pos()
        except Exception:
            return QPointF(0, 0)

    def _get_end(self):
        if self.to_socket:
            try:
                return self.to_socket.get_center_scene_pos()
            except Exception:
                return QPointF(0, 0)
        if self._temp_end:
            return self._temp_end
        return self._get_start()

    def update_path(self):
        self._rebuild()

    def _rebuild(self):
        """Orthogonal routing — WPF BrokenLinkDrawer. L-shaped when not axis-aligned."""
        start = self._get_start()
        end = self._get_end()

        path = QPainterPath()
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 1.0:
            self.setPath(path)
            self._arrow_poly = QPolygonF()
            return

        # Decide routing based on port docks
        from_dock = self.from_socket.port.dock
        to_dock = self.to_socket.port.dock if self.to_socket else PortDock.TOP

        # Check if roughly axis-aligned
        aligned_h = abs(dx) > abs(dy) * 2  # mostly horizontal
        aligned_v = abs(dy) > abs(dx) * 2  # mostly vertical

        if aligned_h and from_dock in (PortDock.LEFT, PortDock.RIGHT):
            # Straight horizontal
            path.moveTo(start)
            path.lineTo(end)
        elif aligned_v and from_dock in (PortDock.TOP, PortDock.BOTTOM):
            # Straight vertical
            path.moveTo(start)
            path.lineTo(end)
        else:
            # Orthogonal (L-shaped) — WPF BrokenLinkDrawer
            span = 30.0
            if from_dock == PortDock.BOTTOM:
                mid1 = QPointF(start.x(), start.y() + span)
            elif from_dock == PortDock.TOP:
                mid1 = QPointF(start.x(), start.y() - span)
            elif from_dock == PortDock.RIGHT:
                mid1 = QPointF(start.x() + span, start.y())
            else:
                mid1 = QPointF(start.x() - span, start.y())

            if to_dock == PortDock.TOP:
                mid2 = QPointF(end.x(), end.y() - span)
            elif to_dock == PortDock.BOTTOM:
                mid2 = QPointF(end.x(), end.y() + span)
            elif to_dock == PortDock.LEFT:
                mid2 = QPointF(end.x() - span, end.y())
            else:
                mid2 = QPointF(end.x() + span, end.y())

            cross = QPointF(mid1.x(), mid2.y()) if abs(dx) > abs(dy) else QPointF(mid2.x(), mid1.y())

            path.moveTo(start)
            path.lineTo(mid1)
            path.lineTo(cross)
            path.lineTo(mid2)
            path.lineTo(end)

        self.setPath(path)
        self._arrow_poly = _arrow_at(end, start)

        if self._label_item:
            mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            self._label_item.setPos(mid + QPointF(5, -12))

    # ── Path accessors ───────────────────────────────────────────────────

    def setPath(self, path):
        self.prepareGeometryChange()
        self._path = path

    def boundingRect(self):
        r = self._path.boundingRect()
        if self._arrow_poly and not self._arrow_poly.isEmpty():
            r = r.united(self._arrow_poly.boundingRect())
        return r.adjusted(-8, -8, 8, 8)

    def shape(self):
        if self._path.isEmpty():
            return self._path
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0)
        return stroker.createStroke(self._path)

    # ── Color ─────────────────────────────────────────────────────────────

    def _active_color(self):
        if self.isSelected():
            return EDGE_COLOR_SELECTED, EDGE_WIDTH_SELECTED
        if self._hovered:
            return EDGE_COLOR_HOVER, EDGE_WIDTH_HOVER
        return EDGE_COLOR, EDGE_WIDTH

    # ── Paint ─────────────────────────────────────────────────────────────

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        color, width = self._active_color()
        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if not self._path.isEmpty():
            painter.drawPath(self._path)

        if self._arrow_poly and not self._arrow_poly.isEmpty():
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(self._arrow_poly)

    # ── Label ─────────────────────────────────────────────────────────────

    def set_label(self, text):
        if not self._label_item:
            self._label_item = QGraphicsTextItem(self)
            self._label_item.setFont(QFont("Segoe UI", 8))
            self._label_item.setDefaultTextColor(QColor("#999"))
            self._label_item.setZValue(6)
        self._label_item.setPlainText(text)
        self._rebuild()

    def remove_label(self):
        if self._label_item:
            self._label_item.setParentItem(None)
            if self.scene():
                self.scene().removeItem(self._label_item)
            self._label_item = None

    # ── Temp / finalize ───────────────────────────────────────────────────

    def set_temp_end(self, pos):
        self._temp_end = pos
        self._rebuild()

    def finalize(self, to_socket):
        self.to_socket = to_socket
        self._temp_end = None
        to_socket.add_edge(self)
        self._rebuild()

    def disconnect(self):
        try:
            self.from_socket.remove_edge(self)
        except Exception:
            pass
        if self.to_socket:
            try:
                self.to_socket.remove_edge(self)
            except Exception:
                pass
        self.remove_label()

    # ── Mouse ─────────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.edge_selected.emit(self)
        self.update()
        super().mousePressEvent(event)


# ── Arrow helper ───────────────────────────────────────────────────────────

def _arrow_at(tip, before):
    dx, dy = tip.x() - before.x(), tip.y() - before.y()
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.001:
        return QPolygonF()
    dx, dy = dx / length, dy / length
    s = ARROW_SIZE
    return QPolygonF([
        QPointF(tip.x(), tip.y()),
        QPointF(tip.x() - dx * s + dy * s * 0.5,
                tip.y() - dy * s - dx * s * 0.5),
        QPointF(tip.x() - dx * s - dy * s * 0.5,
                tip.y() - dy * s + dx * s * 0.5),
    ])
