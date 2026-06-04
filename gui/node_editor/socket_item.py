"""Socket (port) graphics item - the connection points on nodes.

Ported from H.Controls.Diagram (PortData, FlowablePortData, SocketItem).
6px diameter circle, white fill, orange when connected.
Draggable to create new connections.
"""

from PyQt5.QtWidgets import (QGraphicsEllipseItem, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QLineF
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath,
                          QLinearGradient)

from core.node_base import Port, PortType, PortDock


PORT_RADIUS = 4.0
PORT_DIAMETER = PORT_RADIUS * 2
PORT_HOVER_RADIUS = 6.0


class SocketItem(QGraphicsEllipseItem):
    """Visual port on a node. Can be dragged to create edges.

    Colors match C# OpenCVFlowablePortData:
      - Fill: white
      - Link color: orange (#FF8C00)
    """

    # Signals for the scene to handle
    connection_started = pyqtSignal(object)   # socket_item
    connection_moved = pyqtSignal(object, QPointF)  # socket_item, scene_pos
    connection_ended = pyqtSignal(object, object)  # from_socket, to_socket

    def __init__(self, port: Port, parent=None):
        super().__init__(parent)
        self.port = port
        self._hovered = False
        self._dragging = False
        self._connected_edges: list = []

        self.setRect(-PORT_RADIUS, -PORT_RADIUS, PORT_DIAMETER, PORT_DIAMETER)
        self.setAcceptHoverEvents(True)
        self.setFlag(self.ItemSendsGeometryChanges, True)
        self.setZValue(20)  # Above nodes
        self.setCursor(Qt.CrossCursor)

        self._update_style()

    def _update_style(self):
        """Apply visual style based on port type and state."""
        if self._hovered or self._dragging:
            self.setPen(QPen(QColor("#FF8C00"), 2))
            self.setBrush(QBrush(QColor("#FF8C00")))
        elif self.port.is_output:
            self.setPen(QPen(QColor("#666666"), 1.5))
            self.setBrush(QBrush(QColor("#FFFFFF")))
        else:
            self.setPen(QPen(QColor("#888888"), 1.5))
            self.setBrush(QBrush(QColor("#FFFFFF")))

    def add_edge(self, edge):
        """Register a connected edge."""
        if edge not in self._connected_edges:
            self._connected_edges.append(edge)

    def remove_edge(self, edge):
        """Remove a connected edge."""
        if edge in self._connected_edges:
            self._connected_edges.remove(edge)

    def get_center_scene_pos(self) -> QPointF:
        """Get the center point in scene coordinates."""
        return self.mapToScene(0, 0)

    # -- Hover --

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = True
        self._update_style()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = False
        if not self._dragging:
            self._update_style()
        super().hoverLeaveEvent(event)

    # -- Drag to create connections --

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._update_style()
            self.connection_started.emit(self)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging:
            scene_pos = self.mapToScene(event.pos())
            self.connection_moved.emit(self, scene_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging:
            self._dragging = False
            self._update_style()
            scene_pos = self.mapToScene(event.pos())
            self.connection_ended.emit(self, scene_pos)
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            # Update connected edges
            for edge in self._connected_edges:
                edge.update_path()
        return super().itemChange(change, value)
