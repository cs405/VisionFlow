"""Node graphics item — visual node on the canvas with state-aware rendering.

Ported from H.Controls.Diagram (NodeItem, NodeContent, Node).

Features:
  - Adaptive sizing based on title length and node type
  - Execution states: idle / running (pulse) / completed (green) / error (red) / disabled
  - Type-differentiated templates: Source (thick border), Condition (diamond hint),
    Output (double border), Default (rounded rect)
  - Shadow, colored left flag, title, 4 typed ports
"""

from enum import Enum

from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsTextItem,
                              QGraphicsSceneMouseEvent, QStyleOptionGraphicsItem,
                              QWidget)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath,
                          QFont, QFontMetrics, QLinearGradient)

from core.node_base import (NodeBase, Port, PortType, PortDock,
                             VisionNodeData, SrcFilesVisionNodeData,
                             ConditionNodeData, WaitAllParallelNodeData)
from gui.node_editor.socket_item import SocketItem, PORT_DIAMETER


class NodeState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    DISABLED = "disabled"


class NodeTemplate(Enum):
    DEFAULT = "default"
    SOURCE = "source"
    CONDITION = "condition"
    OUTPUT = "output"


# Base dimensions
NODE_MIN_WIDTH = 110.0
NODE_MIN_HEIGHT = 32.0
NODE_CORNER_RADIUS = 3.0
NODE_FLAG_WIDTH = 6.0
CHAR_WIDTH = 7.5  # approximate pixel width per char at 9pt

# Theme colors
NODE_BG = QColor("#3c3c3c")
NODE_BG_SELECTED = QColor("#4a4a4a")
NODE_BORDER = QColor("#555555")
NODE_BORDER_SELECTED = QColor("#0078d4")
NODE_TITLE_COLOR = QColor("#dcdcdc")
NODE_FLAG_DEFAULT = QColor("#888888")
NODE_SHADOW = QColor(0, 0, 0, 60)

# State colors
STATE_COLORS = {
    NodeState.IDLE: QColor("#999999"),
    NodeState.RUNNING: QColor("#2196f3"),
    NodeState.COMPLETED: QColor("#4caf50"),
    NodeState.ERROR: QColor("#f44336"),
    NodeState.DISABLED: QColor("#555555"),
}

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
    "数据源": QColor("#4a9eff"),
    "图像预处理": QColor("#ff8c00"),
    "滤波模糊": QColor("#9c27b0"),
    "图像分割": QColor("#00bcd4"),
    "形态学": QColor("#00bcd4"),
    "条件": QColor("#ff9800"),
    "模板匹配": QColor("#4caf50"),
    "检测": QColor("#f44336"),
    "特征提取": QColor("#ff9800"),
    "视频": QColor("#9c27b0"),
    "输出": QColor("#607d8b"),
    "ONNX": QColor("#e91e63"),
    "网络通讯": QColor("#795548"),
}

PORT_OFFSETS = {
    PortDock.TOP: lambda w, h: QPointF(0, -h / 2),
    PortDock.BOTTOM: lambda w, h: QPointF(0, h / 2),
    PortDock.LEFT: lambda w, h: QPointF(-w / 2, 0),
    PortDock.RIGHT: lambda w, h: QPointF(w / 2, 0),
}


class NodeItem(QGraphicsItem):
    """Visual node on the diagram canvas.

    Adapts size to content, shows execution state, and uses type-specific templates.
    """

    node_selected = pyqtSignal(object)
    node_moved = pyqtSignal(object)
    node_double_clicked = pyqtSignal(object)

    def __init__(self, node_data: NodeBase, group_name: str = "", parent=None):
        super().__init__(parent)
        self.node_data = node_data
        self._group_name = group_name
        self._hovered = False
        self._state = NodeState.IDLE
        self._template = self._detect_template()
        self._flag_color = GROUP_COLORS.get(group_name, NODE_FLAG_DEFAULT)
        self._port_positions: dict[str, QPointF] = {}
        self._pulse_val = 0.0
        self._pulse_timer: QTimer | None = None

        # Compute adaptive size
        self._node_w, self._node_h = self._compute_size()
        self._rect = QRectF(-self._node_w / 2, -self._node_h / 2, self._node_w, self._node_h)

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        self.sockets: list[SocketItem] = []
        self._create_sockets()

    # ── Templates ─────────────────────────────────────────────────────

    def _detect_template(self) -> NodeTemplate:
        nd = self.node_data
        if isinstance(nd, SrcFilesVisionNodeData):
            return NodeTemplate.SOURCE
        if isinstance(nd, ConditionNodeData):
            return NodeTemplate.CONDITION
        if nd.__class__.__name__.lower().startswith("show") or \
           "output" in nd.__class__.__name__.lower():
            return NodeTemplate.OUTPUT
        return NodeTemplate.DEFAULT

    def _compute_size(self) -> tuple[float, float]:
        """Adaptive size based on title length and template."""
        title = self.node_data.title or self.node_data.name
        # Approximate text width
        text_w = max(60, len(title) * CHAR_WIDTH + 20)
        w = max(NODE_MIN_WIDTH, text_w)
        h = NODE_MIN_HEIGHT

        # Templates tweak sizes
        if self._template == NodeTemplate.SOURCE:
            h = max(h, 38.0)
        elif self._template == NodeTemplate.CONDITION:
            h = max(h, 40.0)
        elif self._template == NodeTemplate.OUTPUT:
            h = max(h, 36.0)

        # Extra height for multi-port nodes
        if len(self.node_data.ports) > 4:
            h += 8

        return w, h

    # ── Sockets ───────────────────────────────────────────────────────

    def _create_sockets(self):
        for port in self.node_data.ports:
            socket = SocketItem(port, self)
            offset_fn = PORT_OFFSETS.get(port.dock)
            if offset_fn:
                socket.setPos(offset_fn(self._node_w, self._node_h))
            self.sockets.append(socket)
            self._port_positions[port.port_id] = socket.pos()

    def get_socket_at(self, pos: QPointF) -> SocketItem | None:
        threshold = PORT_DIAMETER * 2
        for socket in self.sockets:
            sp = socket.get_center_scene_pos()
            dx = pos.x() - sp.x()
            dy = pos.y() - sp.y()
            if dx * dx + dy * dy < threshold * threshold:
                return socket
        return None

    def get_socket_by_port_id(self, port_id: str) -> SocketItem | None:
        for s in self.sockets:
            if s.port.port_id == port_id:
                return s
        return None

    def get_input_sockets(self) -> list[SocketItem]:
        return [s for s in self.sockets if s.port.is_input]

    def get_output_sockets(self) -> list[SocketItem]:
        return [s for s in self.sockets if s.port.is_output]

    # ── State management ──────────────────────────────────────────────

    def set_state(self, state: NodeState):
        self._state = state
        self.prepareGeometryChange()
        self.update()

        if state == NodeState.RUNNING:
            self._start_pulse()
        else:
            self._stop_pulse()

    def _start_pulse(self):
        if self._pulse_timer is None:
            self._pulse_timer = QTimer()
            self._pulse_timer.timeout.connect(self._pulse_tick)
        self._pulse_val = 0.0
        self._pulse_timer.start(50)

    def _stop_pulse(self):
        if self._pulse_timer:
            self._pulse_timer.stop()
        self._pulse_val = 0.0

    def _pulse_tick(self):
        import math
        self._pulse_val += 0.1
        self.update()

    def update_from_node(self):
        """Update visual state from the backing node data."""
        if isinstance(self.node_data, VisionNodeData):
            msg = self.node_data.message or ""
            if hasattr(self.node_data, '_last_error') and self.node_data._last_error:
                self.set_state(NodeState.ERROR)
            elif "错误" in msg:
                self.set_state(NodeState.ERROR)
            elif msg:
                self.set_state(NodeState.COMPLETED)
        self.update()

    # ── Bounds ────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        pad = PORT_DIAMETER + 4
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if self._template == NodeTemplate.CONDITION:
            # Diamond-like shape
            w, h = self._node_w, self._node_h
            path.moveTo(0, -h / 2)
            path.lineTo(w / 2, 0)
            path.lineTo(0, h / 2)
            path.lineTo(-w / 2, 0)
            path.closeSubpath()
        else:
            path.addRoundedRect(self._rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        return path

    # ── Paint ─────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        painter.setRenderHint(QPainter.Antialiasing)

        state_color = STATE_COLORS.get(self._state, QColor("#999999"))

        # Shadow
        sr = self._rect.adjusted(2, 2, 2, 2)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(sr, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        painter.fillPath(shadow_path, NODE_SHADOW)

        # Body
        body_path = QPainterPath()
        body_path.addRoundedRect(self._rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)

        if self._state == NodeState.RUNNING:
            import math
            pulse = (math.sin(self._pulse_val * 4) + 1) / 2
            r = int(60 + pulse * 30)
            g = int(60 + pulse * 30)
            b = int(60 + pulse * 30)
            body_color = QColor(r, g, b)
        elif self._state == NodeState.DISABLED:
            body_color = QColor("#2a2a2a")
        elif self.isSelected():
            body_color = NODE_BG_SELECTED
        elif self._hovered:
            body_color = NODE_BG_SELECTED
        else:
            body_color = NODE_BG

        painter.fillPath(body_path, body_color)

        # Left flag
        self._draw_flag(painter)

        # Border — template-specific
        if self.isSelected():
            border_color = NODE_BORDER_SELECTED
            border_width = 2.0
        elif self._state == NodeState.ERROR:
            border_color = STATE_COLORS[NodeState.ERROR]
            border_width = 2.5
        elif self._state == NodeState.COMPLETED:
            border_color = STATE_COLORS[NodeState.COMPLETED]
            border_width = 2.0
        elif self._template == NodeTemplate.SOURCE:
            border_color = self._flag_color
            border_width = 2.0
        elif self._template == NodeTemplate.OUTPUT:
            border_color = self._flag_color
            border_width = 1.5
        else:
            border_color = NODE_BORDER
            border_width = 1.0

        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(body_path)

        # OUTPUT template: double border
        if self._template == NodeTemplate.OUTPUT and not self.isSelected():
            inner = self._rect.adjusted(3, 3, -3, -3)
            ipath = QPainterPath()
            ipath.addRoundedRect(inner, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
            painter.setPen(QPen(border_color.lighter(120), 0.5))
            painter.drawPath(ipath)

        # Title text
        painter.setPen(NODE_TITLE_COLOR)
        font = QFont("Segoe UI", 9)
        if self._state == NodeState.DISABLED:
            painter.setPen(QColor("#777777"))
        painter.setFont(font)

        title = self.node_data.title or self.node_data.name
        metrics = QFontMetrics(font)
        max_text_w = int(self._node_w - NODE_FLAG_WIDTH - 12)
        elided = metrics.elidedText(title, Qt.ElideRight, max_text_w)

        text_rect = QRectF(
            -self._node_w / 2 + NODE_FLAG_WIDTH + 4,
            -self._node_h / 2 + 2,
            self._node_w - NODE_FLAG_WIDTH - 8,
            self._node_h - 4,
        )
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        # State indicator dot
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(state_color))
        dot_r = 3.5
        painter.drawEllipse(QPointF(self._node_w / 2 - 8, -self._node_h / 2 + 8), dot_r, dot_r)

    def _draw_flag(self, painter: QPainter):
        """Draw the colored left strip."""
        flag_rect = QRectF(-self._node_w / 2, -self._node_h / 2,
                           NODE_FLAG_WIDTH, self._node_h)
        flag_path = QPainterPath()
        r = NODE_CORNER_RADIUS
        flag_path.moveTo(-self._node_w / 2 + r, -self._node_h / 2)
        flag_path.lineTo(-self._node_w / 2 + NODE_FLAG_WIDTH, -self._node_h / 2)
        flag_path.lineTo(-self._node_w / 2 + NODE_FLAG_WIDTH, self._node_h / 2)
        flag_path.lineTo(-self._node_w / 2 + r, self._node_h / 2)
        flag_path.quadTo(-self._node_w / 2, self._node_h / 2,
                        -self._node_w / 2, self._node_h / 2 - r)
        flag_path.lineTo(-self._node_w / 2, -self._node_h / 2 + r)
        flag_path.quadTo(-self._node_w / 2, -self._node_h / 2,
                        -self._node_w / 2 + r, -self._node_h / 2)

        color = self._flag_color
        if self._state == NodeState.DISABLED:
            color = QColor(80, 80, 80)
        painter.fillPath(flag_path, color)

    # ── Mouse events ──────────────────────────────────────────────────

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

    # ── Position tracking ─────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            self.node_moved.emit(self.node_data)
        return super().itemChange(change, value)

    def set_node_position(self, x: float, y: float):
        self.setPos(x, y)

    def get_node_position(self) -> tuple[float, float]:
        pos = self.pos()
        return (pos.x(), pos.y())
