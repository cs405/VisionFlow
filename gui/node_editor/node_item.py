"""Node graphics item - visual representation of a node on the canvas.

Ported from H.Controls.Diagram (NodeItem, NodeContent, Node).
Rounded rect with title bar, colored left flag, and 4 port sockets.
Size: 120x35 (from C# StyleNodeDataBase.LoadDefault).
"""

from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsTextItem,
                              QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem,
                              QWidget, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath,
                          QFont, QFontMetrics)

from core.node_base import NodeBase, Port, PortType, PortDock, VisionNodeData
from gui.node_editor.socket_item import SocketItem, PORT_DIAMETER

# Node dimensions (from C# StyleNodeDataBase.LoadDefault)
NODE_WIDTH = 120.0
NODE_HEIGHT = 35.0
NODE_CORNER_RADIUS = 3.0
NODE_FLAG_WIDTH = 6.0  # Left colored strip

# Theme
NODE_BG = QColor("#3c3c3c")
NODE_BG_SELECTED = QColor("#4a4a4a")
NODE_BORDER = QColor("#555555")
NODE_BORDER_SELECTED = QColor("#0078d4")
NODE_TITLE_COLOR = QColor("#dcdcdc")
NODE_FLAG_DEFAULT = QColor("#888888")
NODE_SHADOW_COLOR = QColor(0, 0, 0, 60)

# Port positions relative to node center
PORT_OFFSETS = {
    PortDock.TOP: QPointF(0, -NODE_HEIGHT / 2),
    PortDock.BOTTOM: QPointF(0, NODE_HEIGHT / 2),
    PortDock.LEFT: QPointF(-NODE_WIDTH / 2, 0),
    PortDock.RIGHT: QPointF(NODE_WIDTH / 2, 0),
}

# Node colors by group (matching theme.py)
GROUP_COLORS = {
    "图像数据源": QColor("#4a9eff"),
    "系统数据源": QColor("#4a9eff"),
    "图像预处理模块": QColor("#ff8c00"),
    "滤波模块": QColor("#9c27b0"),
    "图像分割提取模块": QColor("#00bcd4"),
    "形态学模块": QColor("#00bcd4"),
    "逻辑模块": QColor("#ff9800"),
    "模板匹配模块": QColor("#4caf50"),
    "对象识别模块": QColor("#f44336"),
    "网络通讯模块": QColor("#795548"),
    "其他模块": QColor("#607d8b"),
    "结果输出模块": QColor("#607d8b"),
    "Onnx通用模型": QColor("#e91e63"),
    "特征提取模块": QColor("#e91e63"),
    "视频处理模块": QColor("#9c27b0"),
}


class NodeItem(QGraphicsItem):
    """Visual node on the diagram canvas.

    Shows: rounded rect body, colored left flag, title text, 4 sockets.
    Supports: drag to move, selection, double-click to edit.
    """

    # Signals
    node_selected = pyqtSignal(object)    # node_data
    node_moved = pyqtSignal(object)       # node_data
    node_double_clicked = pyqtSignal(object)  # node_data

    def __init__(self, node_data: NodeBase, group_name: str = "", parent=None):
        super().__init__(parent)
        self.node_data = node_data
        self._group_name = group_name

        # Visual state
        self._hovered = False
        self._flag_color = GROUP_COLORS.get(group_name, NODE_FLAG_DEFAULT)

        # Store port positions
        self._port_positions: dict[str, QPointF] = {}

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        # Bounding rect
        self._rect = QRectF(-NODE_WIDTH / 2, -NODE_HEIGHT / 2, NODE_WIDTH, NODE_HEIGHT)

        # Create socket items
        self.sockets: list[SocketItem] = []
        self._create_sockets()

    def _create_sockets(self):
        """Create 4 socket items positioned at the port docks."""
        for port in self.node_data.ports:
            socket = SocketItem(port, self)
            offset = PORT_OFFSETS.get(port.dock, QPointF(0, 0))
            socket.setPos(offset)
            self.sockets.append(socket)
            self._port_positions[port.port_id] = offset

    def get_socket_at(self, pos: QPointF) -> SocketItem | None:
        """Find a socket at the given scene position (within threshold)."""
        threshold = PORT_DIAMETER * 2
        for socket in self.sockets:
            socket_pos = socket.get_center_scene_pos()
            dx = pos.x() - socket_pos.x()
            dy = pos.y() - socket_pos.y()
            if dx * dx + dy * dy < threshold * threshold:
                return socket
        return None

    def get_socket_by_port_id(self, port_id: str) -> SocketItem | None:
        """Find a socket by its port ID."""
        for s in self.sockets:
            if s.port.port_id == port_id:
                return s
        return None

    def get_input_sockets(self) -> list[SocketItem]:
        return [s for s in self.sockets if s.port.is_input]

    def get_output_sockets(self) -> list[SocketItem]:
        return [s for s in self.sockets if s.port.is_output]

    # -- Bounds --

    def boundingRect(self) -> QRectF:
        """Bounding rect with some padding for ports and shadow."""
        pad = PORT_DIAMETER + 4
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:
        """Exact shape for mouse hit testing."""
        path = QPainterPath()
        path.addRoundedRect(self._rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        return path

    # -- Paint --

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        painter.setRenderHint(QPainter.Antialiasing)

        # Shadow
        shadow_rect = self._rect.adjusted(2, 2, 2, 2)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        painter.fillPath(shadow_path, NODE_SHADOW_COLOR)

        # Body
        body_path = QPainterPath()
        body_path.addRoundedRect(self._rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)

        if self.isSelected():
            body_color = NODE_BG_SELECTED
            border_color = NODE_BORDER_SELECTED
            border_width = 2.0
        elif self._hovered:
            body_color = NODE_BG_SELECTED
            border_color = QColor("#777777")
            border_width = 1.5
        else:
            body_color = NODE_BG
            border_color = NODE_BORDER
            border_width = 1.0

        painter.fillPath(body_path, body_color)

        # Left colored flag
        flag_rect = QRectF(-NODE_WIDTH / 2, -NODE_HEIGHT / 2,
                           NODE_FLAG_WIDTH, NODE_HEIGHT)
        flag_path = QPainterPath()
        # Rounded left side only
        flag_path.moveTo(-NODE_WIDTH / 2 + NODE_CORNER_RADIUS, -NODE_HEIGHT / 2)
        flag_path.lineTo(-NODE_WIDTH / 2 + NODE_FLAG_WIDTH, -NODE_HEIGHT / 2)
        flag_path.lineTo(-NODE_WIDTH / 2 + NODE_FLAG_WIDTH, NODE_HEIGHT / 2)
        flag_path.lineTo(-NODE_WIDTH / 2 + NODE_CORNER_RADIUS, NODE_HEIGHT / 2)
        flag_path.quadTo(-NODE_WIDTH / 2, NODE_HEIGHT / 2,
                        -NODE_WIDTH / 2, NODE_HEIGHT / 2 - NODE_CORNER_RADIUS)
        flag_path.lineTo(-NODE_WIDTH / 2, -NODE_HEIGHT / 2 + NODE_CORNER_RADIUS)
        flag_path.quadTo(-NODE_WIDTH / 2, -NODE_HEIGHT / 2,
                        -NODE_WIDTH / 2 + NODE_CORNER_RADIUS, -NODE_HEIGHT / 2)
        painter.fillPath(flag_path, self._flag_color)

        # Border
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(body_path)

        # Title text
        painter.setPen(NODE_TITLE_COLOR)
        font = QFont("Segoe UI", 9)
        painter.setFont(font)

        title = self.node_data.title or self.node_data.name
        metrics = QFontMetrics(font)
        elided = metrics.elidedText(title, Qt.ElideRight,
                                     int(NODE_WIDTH - NODE_FLAG_WIDTH - 12))

        text_rect = QRectF(
            -NODE_WIDTH / 2 + NODE_FLAG_WIDTH + 4,
            -NODE_HEIGHT / 2 + 2,
            NODE_WIDTH - NODE_FLAG_WIDTH - 8,
            NODE_HEIGHT - 4,
        )
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        # Execution state indicator
        if isinstance(self.node_data, VisionNodeData):
            msg = self.node_data.message
            if msg:
                indicator_color = QColor("#4caf50")  # Green for success/default
                if "错误" in msg:
                    indicator_color = QColor("#f44336")
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(indicator_color))
                painter.drawEllipse(QPointF(NODE_WIDTH / 2 - 8, -NODE_HEIGHT / 2 + 8), 3, 3)

    # -- Mouse events --

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton:
            self.node_selected.emit(self.node_data)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent):
        self.node_double_clicked.emit(self.node_data)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        self.node_moved.emit(self.node_data)
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    # -- Position tracking --

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            self.node_moved.emit(self.node_data)
        return super().itemChange(change, value)

    # -- Serialization helpers --

    def set_node_position(self, x: float, y: float):
        """Set position from saved data."""
        self.setPos(x, y)

    def get_node_position(self) -> tuple[float, float]:
        """Get position for saving."""
        pos = self.pos()
        return (pos.x(), pos.y())
