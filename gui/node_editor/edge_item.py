"""Edge (link) graphics item - Bezier curve connecting two sockets.

Ported from H.Controls.Diagram (LinkData, FlowableLinkData, BezierLink).
Orange (#FF8C00) Bezier curve between source and target ports.
"""

from PyQt5.QtWidgets import (QGraphicsPathItem, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget, QGraphicsItem)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainterPath, QPainter,
                          QPainterPathStroker, QFont, QFontMetrics)

from core.node_base import LinkData, PortDock


EDGE_COLOR = QColor("#FF8C00")       # Orange (matches C# FlowableLinkData)
EDGE_COLOR_SELECTED = QColor("#FFA726")
EDGE_COLOR_HOVER = QColor("#FFB74D")
EDGE_WIDTH = 2.0
EDGE_WIDTH_HOVER = 3.0
CONTROL_POINT_OFFSET = 80  # Distance of bezier control points from ports


class EdgeItem(QGraphicsPathItem):
    """Bezier curve edge connecting two SocketItems.

    Automatically routes from the source port's dock position to the target's.
    Supports selection, hovering, and deletion.
    """

    # Signal when edge is selected
    edge_selected = pyqtSignal(object)

    def __init__(self, from_socket: "SocketItem", to_socket: "SocketItem" = None,
                 link_data: LinkData = None, parent=None):
        super().__init__(parent)
        self.from_socket = from_socket
        self.to_socket = to_socket
        self.link_data = link_data
        self._hovered = False
        self._temp_end: QPointF | None = None  # Temporary end during drag

        self.setZValue(5)  # Below nodes, above grid
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        self._update_color()
        self.update_path()

        # Register with sockets
        from_socket.add_edge(self)
        if to_socket:
            to_socket.add_edge(self)

    def _update_color(self):
        """Update pen color based on state."""
        if self.isSelected():
            color = EDGE_COLOR_SELECTED
            width = EDGE_WIDTH_HOVER
        elif self._hovered:
            color = EDGE_COLOR_HOVER
            width = EDGE_WIDTH_HOVER
        else:
            color = EDGE_COLOR
            width = EDGE_WIDTH

        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)

    # -- Path computation --

    def update_path(self):
        """Recompute the Bezier path between the two sockets."""
        start = self.from_socket.get_center_scene_pos()

        if self.to_socket:
            end = self.to_socket.get_center_scene_pos()
        elif self._temp_end:
            end = self._temp_end
        else:
            end = start

        # Control point offset direction depends on port dock
        ctrl_offset = self._get_control_offset(self.from_socket.port.dock, start, end)

        path = QPainterPath()
        path.moveTo(start)

        if self.to_socket:
            ctrl_offset_end = self._get_control_offset(self.to_socket.port.dock, end, start)
            path.cubicTo(
                start + ctrl_offset,
                end + ctrl_offset_end,
                end,
            )
        else:
            # Temporary line during drag
            mid = (start + end) / 2
            path.cubicTo(
                start + ctrl_offset,
                mid,
                end,
            )

        self.setPath(path)
        self._update_arrow(end)

    def _get_control_offset(self, dock: PortDock, pos: QPointF, other_pos: QPointF) -> QPointF:
        """Get the control point offset based on port dock position.

        Ports on the right side extend right, ports on the left extend left, etc.
        """
        dist = CONTROL_POINT_OFFSET

        # Determine direction from center
        dx = other_pos.x() - pos.x()
        dy = other_pos.y() - pos.y()

        if dock == PortDock.BOTTOM:
            return QPointF(0, abs(dist) if dy >= 0 else dist)
        elif dock == PortDock.TOP:
            return QPointF(0, -abs(dist) if dy <= 0 else -dist)
        elif dock == PortDock.RIGHT:
            return QPointF(abs(dist) if dx >= 0 else dist, 0)
        elif dock == PortDock.LEFT:
            return QPointF(-abs(dist) if dx <= 0 else -dist, 0)
        return QPointF(0, dist)

    def set_temp_end(self, pos: QPointF):
        """Set a temporary end point (during drag creation)."""
        self._temp_end = pos
        self.update_path()

    def finalize(self, to_socket: "SocketItem"):
        """Finalize the connection to a target socket."""
        self.to_socket = to_socket
        self._temp_end = None
        to_socket.add_edge(self)
        self.update_path()

    def disconnect(self):
        """Break the connection."""
        self.from_socket.remove_edge(self)
        if self.to_socket:
            self.to_socket.remove_edge(self)

    # -- Arrow --

    def _update_arrow(self, end: QPointF):
        """Remove old arrow and draw a new one at the endpoint."""
        # Simple: the path itself is enough (we use arrow-less Bezier)
        pass

    # -- Paint --

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        """Paint the edge with optional hover widening."""
        painter.setRenderHint(QPainter.Antialiasing)

        self._update_color()
        painter.setPen(self.pen())
        painter.drawPath(self.path())

    def shape(self) -> QPainterPath:
        """Wider shape for easier mouse hit detection."""
        stroker = QPainterPathStroker()
        stroker.setWidth(8.0)
        return stroker.createStroke(self.path())

    # -- Selection --

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
