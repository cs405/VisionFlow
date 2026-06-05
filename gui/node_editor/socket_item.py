"""Socket (port) graphics item — typed connection points on nodes.

Ported from H.Controls.Diagram (PortData, FlowablePortData, SocketItem).

Each port now carries a data_type for visual differentiation:
  - image (default): white/solid — carries numpy image data
  - control: yellow/diamond — flow control signals
  - text: cyan/rounded — string data
  - any: gray/dashed — generic passthrough

Visual differences by type: fill color, pen style, shape.
"""

from enum import Enum
from PyQt5.QtWidgets import (QGraphicsObject, QGraphicsSceneMouseEvent,
                              QStyleOptionGraphicsItem, QWidget)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath,
                          QLinearGradient, QPolygonF)

from core.node_base import Port, PortType, PortDock


PORT_RADIUS = 4.0
PORT_DIAMETER = PORT_RADIUS * 2
PORT_HOVER_RADIUS = 6.0
PORT_HIT_RADIUS = PORT_RADIUS * 2.5


class PortDataType(Enum):
    """Data type carried by a port — determines visual style."""
    IMAGE = ("image", QColor("#FFFFFF"), QColor("#4a9eff"), False)
    CONTROL = ("control", QColor("#FFD700"), QColor("#FFD700"), True)
    TEXT = ("text", QColor("#00BCD4"), QColor("#00BCD4"), False)
    ANY = ("any", QColor("#AAAAAA"), QColor("#AAAAAA"), True)

    def __init__(self, label: str, color: QColor, glow: QColor, dashed: bool):
        self.label = label
        self.color = color
        self.glow_color = glow
        self.dashed = dashed


class SocketItem(QGraphicsObject):
    """Visual port on a node. Supports drag-to-connect.

    Colors and shapes vary by data type:
      - IMAGE: white circle, blue glow on hover
      - CONTROL: yellow diamond, yellow glow on hover
      - TEXT: cyan circle, cyan glow on hover
      - ANY: gray circle with dashed border
    """

    connection_started = pyqtSignal(object)
    connection_moved = pyqtSignal(object, QPointF)
    connection_ended = pyqtSignal(object, object)

    def __init__(self, port: Port, parent=None):
        super().__init__(parent)
        self.port = port
        self._hovered = False
        self._dragging = False
        self._connected_edges: list = []
        self._pen = QPen()
        self._brush = QBrush()
        self._rect = QRectF(-PORT_RADIUS, -PORT_RADIUS, PORT_DIAMETER, PORT_DIAMETER)

        # Determine data type from port metadata
        dt_str = getattr(port, 'data_type', 'image') or 'image'
        try:
            self._data_type = PortDataType[dt_str.upper()]
        except KeyError:
            self._data_type = PortDataType.IMAGE

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsObject.ItemSendsGeometryChanges, True)
        self.setZValue(20)
        self.setCursor(Qt.CrossCursor)

        self._update_style()

    # ── Style ─────────────────────────────────────────────────────────

    def _update_style(self):
        dt = self._data_type

        if self._hovered or self._dragging:
            self._pen = QPen(dt.glow_color, 2.5)
            self._brush = QBrush(dt.glow_color)
        elif self.port.is_output:
            self._pen = QPen(dt.color, 2.0)
            self._brush = QBrush(dt.color.lighter(120))
        else:
            self._pen = QPen(dt.color, 1.5)
            if dt.dashed:
                self._pen.setStyle(Qt.DashLine)
            self._brush = QBrush(QColor("#333337"))

        self.setToolTip(f"{self.port.dock.name} — {dt.label}")
        self.update()

    def boundingRect(self) -> QRectF:
        pad = PORT_HOVER_RADIUS + 2
        return self._rect.adjusted(-pad, -pad, pad, pad)

    # ── Shape (varies by data type) ──────────────────────────────────

    def shape(self) -> QPainterPath:
        """Hit-test area — larger than visual for easy grabbing."""
        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), PORT_HIT_RADIUS, PORT_HIT_RADIUS)
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self._pen)
        painter.setBrush(self._brush)

        r = PORT_RADIUS
        dt = self._data_type

        if dt == PortDataType.CONTROL:
            # Diamond shape
            diamond = QPolygonF([
                QPointF(0, -r), QPointF(r, 0), QPointF(0, r), QPointF(-r, 0)
            ])
            painter.drawPolygon(diamond)
        else:
            painter.drawEllipse(QPointF(0, 0), r, r)

        # Connection indicator dot
        if self._connected_edges:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(self.port.link_color if hasattr(self.port, 'link_color') else QColor("#FF8C00")))
            painter.drawEllipse(QPointF(0, 0), 2, 2)

    # ── Edge tracking ─────────────────────────────────────────────────

    def add_edge(self, edge):
        if edge not in self._connected_edges:
            self._connected_edges.append(edge)
        self.update()

    def remove_edge(self, edge):
        if edge in self._connected_edges:
            self._connected_edges.remove(edge)
        self.update()

    def get_center_scene_pos(self) -> QPointF:
        return self.mapToScene(0, 0)

    @property
    def is_connected(self) -> bool:
        return len(self._connected_edges) > 0

    # ── Hover ─────────────────────────────────────────────────────────

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = True
        self._update_style()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = False
        if not self._dragging:
            self._update_style()
        super().hoverLeaveEvent(event)

    # ── Drag to connect ───────────────────────────────────────────────

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.port.is_output:
            self._dragging = True
            self._update_style()
            s = self.scene()
            if hasattr(s, 'start_edge_drag'):
                s.start_edge_drag(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging:
            s = self.scene()
            if hasattr(s, 'update_edge_drag'):
                s.update_edge_drag(self, self.mapToScene(event.pos()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging:
            self._dragging = False
            self._update_style()
            s = self.scene()
            if hasattr(s, 'end_edge_drag'):
                s.end_edge_drag(self, self.mapToScene(event.pos()))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsObject.ItemPositionHasChanged:
            for edge in self._connected_edges:
                edge.update_path()
        return super().itemChange(change, value)
