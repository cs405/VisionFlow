"""Node graphics item — WPF StyleNodeDataBase DataTemplate 1:1 port.

Ported from H.VisionMaster.NodeData/Themes/Generic.xaml StyleNodeDataBase template.

WPF structure:
  Border (state-aware border/background)
    ├─ DockPanel
    │   ├─ Grid (left 30px bar area)
    │   │   ├─ Border Width=30 (colored state strip, hidden idle → visible on Running/Success/Error)
    │   │   │   └─ FontIconTextBlock (icon centered, turns white when bar visible)
    │   │   └─ ...
    │   └─ TextBlock (node title, center-aligned, ellipsis)
    └─ State triggers: bar visibility + icon foreground color

Dark-theme adaptation:
  - Default bg: #3c3c3c, hover: #4a4a4a, selected: #4a4a4a
  - Default border: #555, hover: #0078d4, selected: #FF8C00 (WPF Orange)
  - 30px left bar: hidden idle, colored on Running/Success/Error
  - FontIcon in bar: turns white when bar visible
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
NODE_CORNER_RADIUS = 2.0       # WPF CornerRadius bindings use small radius
BAR_WIDTH = 30.0               # WPF: Border Width="30" (was 6.0)
ICON_SIZE = 14                 # WPF FontIconTextBlock font size
TEXT_FONT_SIZE = 9             # WPF TextBlock default font size
NODE_MARGIN = 2                # WPF: Border Margin="2"

# ═══════════════════════════════════════════════════════════════════════════
# Colors — WPF Brushes mapped to dark theme
# ═══════════════════════════════════════════════════════════════════════════

# Backgrounds (WPF: White / LightGray → dark equivalents)
NODE_BG = QColor("#3c3c3c")
NODE_BG_HOVER = QColor("#4a4a4a")
NODE_BG_SELECTED = QColor("#4a4a4a")
NODE_BG_DISABLED = QColor("#2a2a2a")

# Borders
NODE_BORDER = QColor("#555555")
NODE_BORDER_HOVER = QColor("#0078d4")       # WPF: Foreground brush
NODE_BORDER_SELECTED = QColor("#FF8C00")    # WPF: BrushKeys.Orange
NODE_BORDER_ERROR = QColor("#f44336")

# Text
NODE_TEXT_COLOR = QColor("#dcdcdc")
NODE_TEXT_DISABLED = QColor("#777777")
NODE_SHADOW = QColor(0, 0, 0, 60)

# State colors (used for left bar background)
STATE_COLORS = {
    NodeState.IDLE: QColor("#999999"),
    NodeState.RUNNING: QColor("#2196f3"),
    NodeState.COMPLETED: QColor("#4caf50"),
    NodeState.ERROR: QColor("#f44336"),
    NodeState.DISABLED: QColor("#555555"),
}


# Group → flag color (used when bar is visible in idle state for SOURCE template)
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


# Node icon mapping (matching WPF FontIcons per node category)
NODE_ICONS = {
    "SrcFilesVisionNodeData": FontIcons.Photo2,
    "ImageFileSource": FontIcons.Photo2,
    "CameraCapture": FontIcons.Camera,
    "VideoCapture": FontIcons.Video,
    "GaussianBlur": FontIcons.Filter,
    "CvtColor": FontIcons.Color,
    "Threshold": FontIcons.Filter,
    "ConditionNodeData": "⇄",
    "TemplateMatching": "⌖",
    "ROINodeData": FontIcons.Crop,
    "Morphology": "⬒",
    "Detector": "◉",
    "Feature": "✣",
    "Output": "↗",
    "Modbus": "⌁",
    "Onnx": "AI",
}


def _resolve_node_icon(node_data: NodeBase) -> str:
    """Resolve the FontIcon for a node, falling back through type hierarchy."""
    cls = type(node_data)
    for base in cls.__mro__:
        if base.__name__ in NODE_ICONS:
            return NODE_ICONS[base.__name__]
    # Check group-based icon
    group_name = getattr(node_data, '__group__', '')
    if group_name in GROUP_META_ICONS:
        return GROUP_META_ICONS[group_name]
    return "◇"


# Group icon mapping
GROUP_META_ICONS = {k: v["icon"] if isinstance(v, dict) else v for k, v in {
    "图像数据源": FontIcons.Photo2,
    "滤波模块": FontIcons.Filter,
    "图像预处理模块": FontIcons.Color,
    "图像分割提取模块": FontIcons.Cut,
    "形态学模块": "⬒",
    "逻辑模块": "⇄",
    "模板匹配模块": "⌖",
    "对象识别模块": "◉",
    "特征提取模块": "✣",
    "网络通讯模块": "⌁",
    "结果输出模块": "↗",
    "Onnx通用模型": "AI",
    "其他模块": "◇",
    "视频处理模块": FontIcons.Video,
}.items()}


PORT_OFFSETS = {
    PortDock.TOP: lambda w, h: QPointF(0, -h / 2),
    PortDock.BOTTOM: lambda w, h: QPointF(0, h / 2),
    PortDock.LEFT: lambda w, h: QPointF(-w / 2, 0),
    PortDock.RIGHT: lambda w, h: QPointF(w / 2, 0),
}


# ═══════════════════════════════════════════════════════════════════════════
# NodeItem — WPF StyleNodeDataBase visual alignment
# ═══════════════════════════════════════════════════════════════════════════

class NodeItem(QGraphicsObject):
    """Visual node on diagram canvas — 1:1 WPF DataTemplate equivalent.

    Structure:
      ┌──────────────────────────────────────┐
      │ [30px colored bar + FontIcon]  Title │
      │  ← BAR_WIDTH →  ← text area →       │
      └──────────────────────────────────────┘

    State behavior (WPF DataTriggers):
      - IDLE: bar hidden (thin colored line hint), icon not visible
      - RUNNING: bar visible (blue), icon white
      - COMPLETED: bar visible (green), icon white
      - ERROR: bar visible (red), icon white
      - DISABLED: bar hidden, dimmed colors

    Selection (WPF IsSelected DataTrigger):
      - Border: #FF8C00 (Orange), width 2.0

    Hover (WPF IsMouseOver Trigger):
      - Border: #0078d4, background lightens
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
        self._flag_color = GROUP_COLORS.get(group_name, QColor("#888888"))
        self._icon_text = _resolve_node_icon(node_data)
        self._port_positions: dict[str, QPointF] = {}
        self._pulse_val = 0.0
        self._pulse_timer: QTimer | None = None

        # Compute adaptive size with QFontMetrics
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
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

        self.sockets: list[SocketItem] = []
        self._create_sockets()

    # ── Template detection ──────────────────────────────────────────────

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

    # ── Adaptive sizing ─────────────────────────────────────────────────

    def _compute_size(self) -> tuple[float, float]:
        """Compute node size from title text using QFontMetrics."""
        title = self.node_data.title or self.node_data.name
        font = self._title_font()
        fm = QFontMetrics(font)
        text_width = fm.boundingRect(title).width()
        # Padding: bar (30) + left padding (6) + right padding (8) + margin
        w = max(NODE_MIN_WIDTH, BAR_WIDTH + text_width + 18)
        h = max(NODE_MIN_HEIGHT, fm.height() + 12)

        # Template-specific adjustments
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

    # ── Sockets ─────────────────────────────────────────────────────────

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

    # ── State management ────────────────────────────────────────────────

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

    # ── Bounds ──────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        pad = PORT_DIAMETER + 4
        return self._rect.adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:
        return self._build_body_path(self._rect)

    def _build_body_path(self, rect: QRectF) -> QPainterPath:
        path = QPainterPath()
        if self._template == NodeTemplate.CONDITION:
            # Diamond shape
            path.moveTo(rect.center().x(), rect.top())
            path.lineTo(rect.right(), rect.center().y())
            path.lineTo(rect.center().x(), rect.bottom())
            path.lineTo(rect.left(), rect.center().y())
            path.closeSubpath()
        else:
            path.addRoundedRect(rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
        return path

    # ═════════════════════════════════════════════════════════════════════
    # Paint — WPF StyleNodeDataBase visual alignment
    # ═════════════════════════════════════════════════════════════════════

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        painter.setRenderHint(QPainter.Antialiasing)

        state_color = STATE_COLORS.get(self._state, QColor("#999999"))
        body_path = self._build_body_path(self._rect)

        # ── Shadow ──
        sr = self._rect.adjusted(2, 2, 2, 2)
        shadow_path = self._build_body_path(sr)
        painter.fillPath(shadow_path, NODE_SHADOW)

        # ── Body background ──
        # WPF: White default, LightGray on hover/selected → dark equivalents
        if self._state == NodeState.DISABLED:
            bg_color = NODE_BG_DISABLED
        elif self.isSelected():
            bg_color = NODE_BG_SELECTED
        elif self._hovered:
            bg_color = NODE_BG_HOVER
        elif self._state == NodeState.RUNNING:
            import math
            pulse = (math.sin(self._pulse_val * 4) + 1) / 2
            r = int(60 + pulse * 30)
            bg_color = QColor(r, r, r)
        else:
            bg_color = NODE_BG

        painter.fillPath(body_path, bg_color)

        # ── Left bar (WPF: Border Width=30, Visibility bound to State) ──
        self._draw_left_bar(painter, state_color)

        # ── Border ──
        # WPF: DiagramKeys.StateBorder base + IsMouseOver → Foreground, IsSelected → Orange
        if self.isSelected():
            border_color = NODE_BORDER_SELECTED   # WPF Orange
            border_width = 2.0
        elif self._state == NodeState.ERROR:
            border_color = NODE_BORDER_ERROR
            border_width = 2.0
        elif self._hovered:
            border_color = NODE_BORDER_HOVER       # WPF Foreground brush
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

        # ── OUTPUT double border ──
        if self._template == NodeTemplate.OUTPUT and not self.isSelected():
            inner = self._rect.adjusted(3, 3, -3, -3)
            ipath = self._build_body_path(inner)
            painter.setPen(QPen(border_color.lighter(120), 0.5))
            painter.drawPath(ipath)

        # ── Title text (WPF: TextBlock center-aligned, right of bar) ──
        text_color = NODE_TEXT_DISABLED if self._state == NodeState.DISABLED else NODE_TEXT_COLOR
        painter.setPen(text_color)
        font = self._title_font()
        painter.setFont(font)

        title = self.node_data.title or self.node_data.name
        fm = QFontMetrics(font)
        # Text area: from left bar edge to right padding
        text_rect_w = self._node_w - BAR_WIDTH - 8
        elided = fm.elidedText(title, Qt.ElideRight, int(text_rect_w))

        # WPF uses HorizontalAlignment="Center" VerticalAlignment="Center"
        text_rect = QRectF(
            -self._node_w / 2 + BAR_WIDTH + 2,
            -self._node_h / 2,
            text_rect_w,
            self._node_h,
        )
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        # ── State indicator dot (right side, replaces WPF border-based state) ──
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(state_color))
        dot_r = 3.0
        painter.drawEllipse(
            QPointF(self._node_w / 2 - 8, -self._node_h / 2 + 8),
            dot_r, dot_r,
        )

    def _draw_left_bar(self, painter: QPainter, state_color: QColor):
        """Draw the 30px left colored bar with centered FontIcon.

        WPF behavior:
          - Bar Visibility: Hidden in IDLE/DISABLED → Visible in RUNNING/SUCCESS/ERROR
          - Bar Background: Bound to parent Border's BorderBrush (= state color)
          - Icon foreground: White when bar is visible (Running/Success/Error triggers)
          - For SOURCE template or IDLE state with group color: thin-colored left edge hint
        """
        bar_rect = QRectF(
            -self._node_w / 2,
            -self._node_h / 2,
            BAR_WIDTH,
            self._node_h,
        )

        bar_visible = self._state in (NodeState.RUNNING, NodeState.COMPLETED, NodeState.ERROR)

        if bar_visible:
            # WPF: bar background = state color, icon = white
            bar_path = QPainterPath()
            bar_path.addRoundedRect(bar_rect, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
            # Clip to left portion only (rounded top-left + bottom-left)
            clip_path = QPainterPath()
            clip_path.addRect(
                -self._node_w / 2, -self._node_h / 2,
                BAR_WIDTH + NODE_CORNER_RADIUS, self._node_h,
            )
            bar_path = clip_path.intersected(bar_path)

            painter.fillPath(bar_path, QBrush(state_color))

            # FontIcon centered in bar
            icon_color = QColor("#FFFFFF")
            icon_f = icon_font(ICON_SIZE)
            painter.setFont(icon_f)
            painter.setPen(icon_color)
            icon_rect = QRectF(
                -self._node_w / 2 + 2,
                -self._node_h / 2 + 2,
                BAR_WIDTH - 4,
                self._node_h - 4,
            )
            painter.drawText(icon_rect, Qt.AlignCenter, self._icon_text)
        else:
            # WPF: bar hidden in idle — draw thin left edge hint with flag color
            thin_bar = QRectF(
                -self._node_w / 2, -self._node_h / 2,
                3.0, self._node_h,
            )
            thin_path = QPainterPath()
            thin_path.addRoundedRect(thin_bar, NODE_CORNER_RADIUS, NODE_CORNER_RADIUS)
            clip_path = QPainterPath()
            clip_path.addRect(
                -self._node_w / 2, -self._node_h / 2,
                3.0 + NODE_CORNER_RADIUS, self._node_h,
            )
            thin_path = clip_path.intersected(thin_path)

            if self._state == NodeState.DISABLED:
                painter.fillPath(thin_path, QBrush(QColor(80, 80, 80)))
            else:
                painter.fillPath(thin_path, QBrush(self._flag_color))

    # ── Mouse events ────────────────────────────────────────────────────

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

    # ── Position tracking ───────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == self.ItemPositionHasChanged:
            self.node_moved.emit(self.node_data)
        return super().itemChange(change, value)

    def set_node_position(self, x: float, y: float):
        self.setPos(x, y)

    def get_node_position(self) -> tuple[float, float]:
        pos = self.pos()
        return (pos.x(), pos.y())
