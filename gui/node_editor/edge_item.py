"""Edge (link) graphics item — Bezier curve with arrow, labels, type coloring.

Ported from H.Controls.Diagram (LinkData, FlowableLinkData, BezierLink).

Features:
  - Cubic Bezier routing between port dock positions
  - Arrowhead at target endpoint
  - Self-loop routing (when connecting to same node)
  - Data-type color coding (from source port)
  - Hoverable label with link info
  - Selection and deletion support
"""

import math
from PyQt5.QtWidgets import (QGraphicsPathItem, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget, QGraphicsItem,
                              QGraphicsTextItem)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainterPath, QPainter,
                          QPainterPathStroker, QFont, QFontMetrics,
                          QPolygonF)

from core.node_base import LinkData, PortDock


# Colors by data type
EDGE_COLORS = {
    "image": QColor("#FF8C00"),      # Orange
    "control": QColor("#FFD700"),    # Gold
    "text": QColor("#00BCD4"),       # Cyan
    "any": QColor("#AAAAAA"),        # Gray
}
EDGE_COLOR_DEFAULT = QColor("#FF8C00")
EDGE_COLOR_SELECTED = QColor("#FFA726")
EDGE_COLOR_HOVER = QColor("#FFB74D")
EDGE_WIDTH = 2.0
EDGE_WIDTH_HOVER = 3.0
EDGE_WIDTH_SELECTED = 2.5
CONTROL_POINT_OFFSET = 80
ARROW_SIZE = 8.0


class EdgeItem(QGraphicsPathItem):
    """Bezier curve edge connecting two SocketItems.

    Supports:
      - Cubic Bezier routing with port-dock-aware control points
      - Arrow at target
      - Self-loop rendering (circular loopback)
      - Data-type-aware coloring
      - Label display
      - Selection and hover states
    """

    edge_selected = pyqtSignal(object)

    def __init__(self, from_socket: "SocketItem", to_socket: "SocketItem" = None,
                 link_data: LinkData = None, parent=None):
        super().__init__(parent)
        self.from_socket = from_socket
        self.to_socket = to_socket
        self.link_data = link_data
        self._hovered = False
        self._temp_end: QPointF | None = None
        self._label_item: QGraphicsTextItem | None = None

        # Determine color from source port data type
        dt = getattr(from_socket.port, 'data_type', 'image') or 'image'
        self._edge_color = EDGE_COLORS.get(dt, EDGE_COLOR_DEFAULT)

        self.setZValue(5)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        self._update_color()
        self.update_path()

        from_socket.add_edge(self)
        if to_socket:
            to_socket.add_edge(self)

    # ── Color ─────────────────────────────────────────────────────────

    def _update_color(self):
        if self.isSelected():
            color = EDGE_COLOR_SELECTED
            width = EDGE_WIDTH_SELECTED
        elif self._hovered:
            color = EDGE_COLOR_HOVER
            width = EDGE_WIDTH_HOVER
        else:
            color = self._edge_color
            width = EDGE_WIDTH

        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)

    # ── Path computation ──────────────────────────────────────────────

    def update_path(self):
        """Recompute the Bezier path."""
        start = self.from_socket.get_center_scene_pos()
        if self.to_socket:
            end = self.to_socket.get_center_scene_pos()
        elif self._temp_end:
            end = self._temp_end
        else:
            end = start

        is_self_loop = (self.from_socket.port.node_id ==
                        getattr(getattr(self.to_socket, 'port', None), 'node_id', None))

        path = QPainterPath()
        path.moveTo(start)

        if is_self_loop:
            # Self-loop: draw a circular loop to the side
            self._draw_self_loop(path, start)
        elif self.to_socket:
            ctrl1 = self._control_point(start, end, self.from_socket.port.dock)
            ctrl2 = self._control_point(end, start, self.to_socket.port.dock)
            path.cubicTo(start + ctrl1, end + ctrl2, end)
        else:
            # Temporary drag line
            mid = (start + end) / 2
            ctrl = self._control_point(start, end, self.from_socket.port.dock)
            path.cubicTo(start + ctrl, mid, end)

        self.setPath(path)
        self._update_arrow(end)

        # Update label position
        if self._label_item:
            mid_pt = path.pointAtPercent(0.5)
            self._label_item.setPos(mid_pt + QPointF(5, -12))

    def _draw_self_loop(self, path: QPainterPath, center: QPointF):
        """Draw a self-loop as a small circle to the right of the node."""
        r = 20.0
        offset = QPointF(r * 2, -r)
        ctrl = QPointF(r * 2, -r * 2)
        path.cubicTo(center + QPointF(r, -r), center + ctrl, center + offset)
        path.cubicTo(center + QPointF(0, -r), center + QPointF(r, r), center)

    def _control_point(self, pos: QPointF, other: QPointF, dock: PortDock) -> QPointF:
        """Compute control point offset based on port dock and relative position."""
        dist = CONTROL_POINT_OFFSET
        dx = other.x() - pos.x()
        dy = other.y() - pos.y()

        if dock == PortDock.BOTTOM:
            return QPointF(0, abs(dist) if dy >= 0 else dist)
        elif dock == PortDock.TOP:
            return QPointF(0, -abs(dist) if dy <= 0 else -dist)
        elif dock == PortDock.RIGHT:
            return QPointF(abs(dist) if dx >= 0 else dist, 0)
        elif dock == PortDock.LEFT:
            return QPointF(-abs(dist) if dx <= 0 else -dist, 0)
        return QPointF(dist, 0)

    # ── Arrowhead ─────────────────────────────────────────────────────

    def _update_arrow(self, end: QPointF):
        """Compute and cache arrowhead polygon."""
        if not self.to_socket and not self._temp_end:
            self._arrow_poly = None
            return

        # Get direction at end of path
        percent = self.path().percentAtLength(self.path().length() - 1e-6)
        tangent = self.path().angleAtPercent(max(0.001, percent - 0.001))
        # Actually use pointAtPercent
        pt_before = self.path().pointAtPercent(max(0.001, percent - 0.05))
        dx, dy = end.x() - pt_before.x(), end.y() - pt_before.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length > 0:
            dx, dy = dx / length, dy / length

        s = ARROW_SIZE
        p1 = QPointF(end.x() - dx * s + dy * s * 0.5,
                      end.y() - dy * s - dx * s * 0.5)
        p2 = QPointF(end.x() - dx * s - dy * s * 0.5,
                      end.y() - dy * s + dx * s * 0.5)
        self._arrow_poly = QPolygonF([QPointF(end.x(), end.y()), p1, p2])

    # ── Label ─────────────────────────────────────────────────────────

    def set_label(self, text: str):
        """Set a visible label on the edge."""
        if not self._label_item:
            self._label_item = QGraphicsTextItem(self)
            self._label_item.setFont(QFont("Segoe UI", 8))
            self._label_item.setDefaultTextColor(QColor("#999"))
            self._label_item.setZValue(6)
        self._label_item.setPlainText(text)
        self.update_path()

    def remove_label(self):
        if self._label_item:
            self._label_item.setParentItem(None)
            if self.scene():
                self.scene().removeItem(self._label_item)
            self._label_item = None

    # ── Paint ─────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        painter.setRenderHint(QPainter.Antialiasing)
        self._update_color()
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        # Arrowhead
        if hasattr(self, '_arrow_poly') and self._arrow_poly and not self._arrow_poly.isEmpty():
            painter.setBrush(QBrush(self.pen().color()))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(self._arrow_poly)

    def shape(self) -> QPainterPath:
        """Wider shape for easier mouse hit detection."""
        stroker = QPainterPathStroker()
        stroker.setWidth(10.0)
        return stroker.createStroke(self.path())

    # ── Temp end (drag creation) ──────────────────────────────────────

    def set_temp_end(self, pos: QPointF):
        self._temp_end = pos
        self.update_path()

    def finalize(self, to_socket: "SocketItem"):
        self.to_socket = to_socket
        self._temp_end = None
        to_socket.add_edge(self)
        self.update_path()

    def disconnect(self):
        self.from_socket.remove_edge(self)
        if self.to_socket:
            self.to_socket.remove_edge(self)
        self.remove_label()

    # ── Interaction ───────────────────────────────────────────────────

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            self.edge_selected.emit(self)
        super().mousePressEvent(event)
