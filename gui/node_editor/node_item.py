"""Node graphics item — WPF StyleNodeDataBase DataTemplate 1:1 port.

Ported from H.VisionMaster.NodeData/Themes/Generic.xaml StyleNodeDataBase template.

WPF structure:
  Border (state-aware border/background)
    ├─ DockPanel
    │   ├─ Grid (left 30px bar area)
    │   │   ├─ Border Width=30 (colored state strip)
    │   │   │   └─ FontIconTextBlock (icon centered)
    │   │   └─ ...
    │   └─ TextBlock (node title, center-aligned)
    └─ State triggers: bar visibility + icon foreground color

Port layout (WPF Layout.DoLayoutPort):
  Ports are evenly distributed along each edge by their Dock direction.
  DiagramScene._do_layout_port() is the authoritative layout method.
  NodeItem._create_sockets() sets initial positions, which are then
  refined by the scene's DoLayoutPort.
"""

import math
from enum import Enum

from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem,
                             QWidget)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer, QSizeF
from PyQt5.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath,
                         QFont, QFontMetrics, QLinearGradient)

from core.node_base import (NodeBase, Port, PortType, PortDock,
                            VisionNodeData, SrcFilesVisionNodeData,
                            ConditionNodeData, WaitAllParallelNodeData)
from gui.node_editor.socket_item import SocketItem, PORT_DIAMETER
from gui.font_icons import FontIcons, icon_font
from gui.theme import theme_manager

def _tc():
    return theme_manager.colors


# ═══════════════════════════════════════════════════════════════════════════
# Enums matching WPF
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# Dimensions — matching WPF StyleNodeDataBase
# ═══════════════════════════════════════════════════════════════════════════

NODE_MIN_WIDTH = 120.0
NODE_MIN_HEIGHT = 35.0
NODE_CORNER_RADIUS = 2.0
BAR_WIDTH = 30.0
ICON_SIZE = 14
TEXT_FONT_SIZE = 9
NODE_MARGIN = 2

# ═══════════════════════════════════════════════════════════════════════════
# Colors — WPF Brushes mapped to dark theme
# ═══════════════════════════════════════════════════════════════════════════

NODE_BG = QColor("#ffffff")
NODE_BG_HOVER = QColor("#f5f5f5")
NODE_BG_SELECTED = QColor("#ebebeb")
NODE_BG_DISABLED = QColor("#f0f0f0")

NODE_BORDER = QColor("#ebebeb")
NODE_BORDER_HOVER = QColor("#606266")
NODE_BORDER_SELECTED = QColor("#E6A23C")
NODE_BORDER_ERROR = QColor("#dc000c")

NODE_TEXT_COLOR = QColor("#1e1e1e")
NODE_TEXT_DISABLED = QColor("#999999")
NODE_SHADOW = QColor(0, 0, 0, 30)

STATE_COLORS = {
    NodeState.IDLE: QColor("#909399"),
    NodeState.RUNNING: QColor("#3399FF"),
    NodeState.COMPLETED: QColor("#67C23A"),
    NodeState.ERROR: QColor("#dc000c"),
    NodeState.DISABLED: QColor("#555555"),
}

from core.constants import get_group_color, get_group_icon

_NODE_ICONS = {
    "SrcFilesVisionNodeData": FontIcons.Camera,
    "ImageFileSource": FontIcons.Camera,
    "CameraCapture": FontIcons.Camera,
    "VideoCapture": FontIcons.Video,
    "CvtColor": FontIcons.Color,
    "GaussianBlur": FontIcons.InPrivate,
    "MedianBlur": FontIcons.InPrivate,
    "BilateralFilter": FontIcons.InPrivate,
    "DetailEnhance": FontIcons.InPrivate,
    "PencilSketch": FontIcons.InPrivate,
    "Threshold": FontIcons.InPrivate,
    "ROINodeData": FontIcons.Annotation,
    "Morphology": FontIcons.HomeGroup,
    "ErodeNode": FontIcons.HomeGroup,
    "DilateNode": FontIcons.HomeGroup,
    "ConditionNodeData": FontIcons.Dial6,
    "WaitAllParallelNodeData": FontIcons.Dial6,
    "TemplateMatching": FontIcons.GotoToday,
    "Detector": FontIcons.LargeErase,
    "Feature": FontIcons.GenericScan,
    "Modbus": FontIcons.NarratorForward,
    "TcpClient": FontIcons.NarratorForward,
    "Output": FontIcons.Ethernet,
    "Onnx": FontIcons.CommandPrompt,
    "Other": FontIcons.More,
}


def _resolve_node_icon(node_data) -> str:
    cls = type(node_data)
    for base in cls.__mro__:
        if base.__name__ in _NODE_ICONS:
            return _NODE_ICONS[base.__name__]
    group_name = getattr(node_data, '__group__', '')
    return get_group_icon(group_name)


# Initial socket offset helpers — refined by scene._do_layout_port()
_PORT_OFFSET_INIT = {
    PortDock.TOP: lambda w, h: QPointF(0, -h / 2),
    PortDock.BOTTOM: lambda w, h: QPointF(0, h / 2),
    PortDock.LEFT: lambda w, h: QPointF(-w / 2, 0),
    PortDock.RIGHT: lambda w, h: QPointF(w / 2, 0),
}


# ═══════════════════════════════════════════════════════════════════════════
# NodeItem — WPF StyleNodeDataBase visual alignment
# ═══════════════════════════════════════════════════════════════════════════

class NodeItem(QGraphicsObject):
    """Visual node on diagram canvas — 1:1 WPF DataTemplate equivalent."""

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
        self._flag_color = QColor(get_group_color(group_name))
        self._icon_text = _resolve_node_icon(node_data)
        self._pulse_val = 0.0
        self._pulse_timer: QTimer | None = None

        # Adaptive size
        self._node_w, self._node_h = self._compute_size()
        self._rect = QRectF(
            -self._node_w / 2, -self._node_h / 2,
            self._node_w, self._node_h,
        )

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        self.sockets: list[SocketItem] = []
        self._create_sockets()

    # ── Template detection ──────────────────────────────────────────────────

    def _detect_template(self) -> NodeTemplate:
        nd = self.node_data
        if isinstance(nd, SrcFilesVisionNodeData):
            return NodeTemplate.SOURCE
        if isinstance(nd, ConditionNodeData):
            return NodeTemplate.CONDITION
        cls_name = nd.__class__.__name__.lower()
        if cls_name.startswith("show") or "output" in cls_name:
            return NodeTemplate.OUTPUT
        return NodeTemplate.DEFAULT

    # ── Adaptive sizing ─────────────────────────────────────────────────────

    def _compute_size(self) -> tuple[float, float]:
        title = self.node_data.title or self.node_data.name
        font = self._title_font()
        fm = QFontMetrics(font)
        text_width = fm.boundingRect(title).width()
        w = max(NODE_MIN_WIDTH, BAR_WIDTH + text_width + 18)
        h = max(NODE_MIN_HEIGHT, fm.height() + 12)
        if self._template == NodeTemplate.SOURCE:
            h = max(h, 38.0)
        elif self._template == NodeTemplate.CONDITION:
            h = max(h, 42.0)
        elif self._template == NodeTemplate.OUTPUT:
            h = max(h, 36.0)
        return w, h

    def _title_font(self) -> QFont:
        font = QFont("Segoe UI", TEXT_FONT_SIZE)
        font.setStyleStrategy(QFont.PreferAntialias)
        return font

    # ── Sockets ─────────────────────────────────────────────────────────────

    def _create_sockets(self):
        """Create SocketItem for each port. Initial positions are set by
        _PORT_OFFSET_INIT; the scene's _do_layout_port() refines them."""
        for port in self.node_data.ports:
            socket = SocketItem(port, self)
            offset_fn = _PORT_OFFSET_INIT.get(port.dock)
            if offset_fn:
                socket.setPos(offset_fn(self._node_w, self._node_h))
            self.sockets.append(socket)

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

    # ── State management ────────────────────────────────────────────────────

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
        self._pulse_val += 0.1
        self.update()

    def update_from_node(self):
        if isinstance(self.node_data, VisionNodeData):
            msg = self.node_data.message or ""
            if hasattr(self.node_data, '_last_error') and self.node_data._last_error:
                self.set_state(NodeState.ERROR)
            elif "错误" in msg:
                self.set_state(NodeState.ERROR)
            elif msg:
                self.set_state(NodeState.COMPLETED)
        self.update()

    # ── Bounds ──────────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        pad = PORT_DIAMETER + 4
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:
        return self._build_body_path(self._rect)

    def _build_body_path(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        if self._template == NodeTemplate.CONDITION:
            path.moveTo(rect.center().x(), rect.top())
            path.lineTo(rect.right(), rect.center().y())
            path.lineTo(rect.center().x(), rect.bottom())
            path.lineTo(rect.left(), rect.center().y())
            path.closeSubpath()
        else:
            path.addRoundedRect(rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        return path

    # ═════════════════════════════════════════════════════════════════════════
    # Paint — WPF StyleNodeDataBase visual alignment
    # ═════════════════════════════════════════════════════════════════════════

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        state_color = STATE_COLORS.get(self._state, QColor("#999999"))
        body_path = self._build_body_path(self._rect)

        is_active = self.isSelected() or self._hovered
        if self._state == NodeState.DISABLED:
            bg_color = NODE_BG_DISABLED
        elif self.isSelected():
            bg_color = NODE_BG_SELECTED
        elif self._hovered:
            bg_color = NODE_BG_HOVER
        else:
            bg_color = NODE_BG

        painter.fillPath(body_path, bg_color)

        if is_active:
            sr = self._rect.adjusted(2, 3, -2, 0)
            shadow_path = self._build_body_path(sr)
            painter.fillPath(shadow_path, NODE_SHADOW)

        self._draw_left_bar(painter, state_color)

        if self.isSelected():
            border_color = NODE_BORDER_SELECTED
            border_width = 2.0
        elif self._state == NodeState.ERROR:
            border_color = NODE_BORDER_ERROR
            border_width = 2.0
        elif self._state == NodeState.RUNNING:
            border_color = STATE_COLORS[NodeState.RUNNING]
            border_width = 2.0
        elif self._state == NodeState.COMPLETED:
            border_color = STATE_COLORS[NodeState.COMPLETED]
            border_width = 2.0
        elif self._hovered:
            border_color = NODE_BORDER_HOVER
            border_width = 1.5
        elif self._template == NodeTemplate.SOURCE:
            border_color = self._flag_color
            border_width = 2.0
        else:
            border_color = NODE_BORDER
            border_width = 1.0

        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(body_path)

        if self._template == NodeTemplate.OUTPUT and not self.isSelected():
            inner = self._rect.adjusted(3, 3, -3, -3)
            ipath = self._build_body_path(inner)
            painter.setPen(QPen(border_color.lighter(120), 0.5))
            painter.drawPath(ipath)

        if self._state == NodeState.DISABLED:
            text_color = NODE_TEXT_DISABLED
        elif self._state == NodeState.RUNNING:
            text_color = STATE_COLORS[NodeState.RUNNING]
        elif self._state == NodeState.COMPLETED:
            text_color = STATE_COLORS[NodeState.COMPLETED]
        elif self._state == NodeState.ERROR:
            text_color = STATE_COLORS[NodeState.ERROR]
        else:
            text_color = NODE_TEXT_COLOR
        painter.setPen(text_color)
        font = self._title_font()
        painter.setFont(font)

        title = self.node_data.title or self.node_data.name
        fm = QFontMetrics(font)
        text_rect_w = self._node_w - BAR_WIDTH - 8
        elided = fm.elidedText(title, Qt.ElideRight, int(text_rect_w))
        text_rect = QRectF(
            -self._node_w / 2 + BAR_WIDTH + 2,
            -self._node_h / 2,
            text_rect_w,
            self._node_h,
        )
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

    def _draw_left_bar(self, painter, state_color):
        bar_visible = self._state in (NodeState.RUNNING, NodeState.COMPLETED, NodeState.ERROR)
        icon_rect = QRectF(
            -self._node_w / 2 + 2,
            -self._node_h / 2 + 2,
            BAR_WIDTH - 4,
            self._node_h - 4,
        )
        if bar_visible:
            bar_rect = QRectF(-self._node_w / 2, -self._node_h / 2, BAR_WIDTH, self._node_h)
            bar_path = QPainterPath()
            bar_path.addRoundedRect(bar_rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
            clip = QPainterPath()
            clip.addRect(-self._node_w / 2, -self._node_h / 2,
                         BAR_WIDTH + NODE_CORNER_RADIUS, self._node_h)
            painter.fillPath(clip.intersected(bar_path), QBrush(state_color))
            icon_color = QColor("#FFFFFF")
        else:
            icon_color = NODE_TEXT_COLOR

        icon_f = icon_font(ICON_SIZE)
        painter.setFont(icon_f)
        painter.setPen(icon_color)
        painter.drawText(icon_rect, Qt.AlignCenter, self._icon_text)

    # ── Mouse events ────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.node_selected.emit(self.node_data)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.node_double_clicked.emit(self.node_data)
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        self.node_moved.emit(self.node_data)
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    # ── Position tracking ───────────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            self.node_moved.emit(self.node_data)
        return super().itemChange(change, value)

    def set_node_position(self, x: float, y: float):
        self.setPos(x, y)

    def get_node_position(self) -> tuple[float, float]:
        pos = self.pos()
        return (pos.x(), pos.y())
