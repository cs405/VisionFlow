"""
节点图形项 — WPF VisionMaster风格外观
左侧状态条、选中高亮、悬停效果
"""

from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QBrush, QColor, QPen, QFont, QPainter, QPainterPath,
    QLinearGradient, QGradient
)

from core.events import EventBus, Event, EventType

from .socket_item import GraphicsSocket


class GraphicsNode(QGraphicsItem):
    """WPF风格的图形节点"""

    # 节点颜色方案 (WPF VisionMaster配色)
    COLORS = {
        "IO": {"bg": QColor(40, 60, 50), "header": QColor(60, 110, 70)},
        "预处理": {"bg": QColor(45, 48, 58), "header": QColor(65, 70, 95)},
        "特征检测": {"bg": QColor(55, 48, 45), "header": QColor(95, 65, 65)},
        "匹配": {"bg": QColor(48, 48, 55), "header": QColor(75, 75, 95)},
        "测量": {"bg": QColor(48, 55, 55), "header": QColor(65, 95, 95)},
        "增强": {"bg": QColor(55, 48, 40), "header": QColor(95, 75, 55)},
        "几何变换": {"bg": QColor(48, 48, 53), "header": QColor(75, 75, 85)},
        "颜色处理": {"bg": QColor(52, 43, 52), "header": QColor(85, 65, 85)},
        "default": {"bg": QColor(48, 48, 55), "header": QColor(65, 65, 95)}
    }

    # 状态颜色
    STATE_COLORS = {
        "Running": QColor("#2196F3"),   # 蓝色
        "Success": QColor("#4CAF50"),   # 绿色
        "Error": QColor("#F44336"),     # 红色
    }

    def __init__(self, node_data: dict, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.node_id = node_data.get("id", "")
        self.node_name = node_data.get("name", "Node")
        self.category = node_data.get("category", "default")
        self.inputs = node_data.get("inputs", [])
        self.outputs = node_data.get("outputs", [])
        self.parameters = node_data.get("parameters", [])

        self.event_bus = event_bus

        # 尺寸
        self.width = 180
        self.height = 80
        self.header_height = 34
        self.status_bar_width = 6

        # 端口
        self.input_sockets = []
        self.output_sockets = []

        # 交互状态
        self._selected = False
        self._hovered = False
        self._execution_state = None  # None / "Running" / "Success" / "Error"

        # 设置标志
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        # 创建端口
        self._create_sockets()

        # 设置Z序
        self.setZValue(1)

    def _create_sockets(self):
        """创建端口图形项"""
        for i, socket_def in enumerate(self.inputs):
            socket = GraphicsSocket(socket_def, self, self.event_bus, is_input=True)
            socket.setPos(0, self.header_height + 12 + i * 26)
            socket.setParentItem(self)
            self.input_sockets.append(socket)

        for i, socket_def in enumerate(self.outputs):
            socket = GraphicsSocket(socket_def, self, self.event_bus, is_input=False)
            socket.setPos(self.width, self.header_height + 12 + i * 26)
            socket.setParentItem(self)
            self.output_sockets.append(socket)

        max_sockets = max(len(self.input_sockets), len(self.output_sockets), 1)
        self.height = self.header_height + max_sockets * 26 + 12

    def _get_colors(self):
        """获取节点颜色"""
        colors = self.COLORS.get(self.category, self.COLORS["default"])

        if self._selected:
            bg = QColor(60, 60, 70)
            header = colors["header"].lighter(120)
        elif self._hovered:
            bg = QColor(55, 55, 65)
            header = colors["header"].lighter(110)
        else:
            bg = colors["bg"]
            header = colors["header"]

        return bg, header

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 6, 6)
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        bg_color, header_color = self._get_colors()

        # 阴影效果
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(2, 3, self.width, self.height + 1, 6, 6)
        painter.fillPath(shadow_path, QColor(0, 0, 0, 40))

        # 节点主体
        body_path = QPainterPath()
        body_path.addRoundedRect(0, 0, self.width, self.height, 6, 6)
        painter.fillPath(body_path, QBrush(bg_color))

        # 边框
        if self._selected:
            border_color = QColor("#FF9800")  # 橙色选中边框
            border_width = 2
        elif self._hovered:
            border_color = QColor(120, 120, 140)
            border_width = 1.5
        else:
            border_color = QColor(70, 70, 85)
            border_width = 1

        painter.setPen(QPen(border_color, border_width))
        painter.drawPath(body_path)

        # 左侧状态条
        if self._execution_state in self.STATE_COLORS:
            state_color = self.STATE_COLORS[self._execution_state]
            status_bar = QPainterPath()
            status_bar.addRoundedRect(0, 1, self.status_bar_width, self.height - 2, 3, 3)
            painter.fillPath(status_bar, QBrush(state_color))

        # 标题栏
        header_path = QPainterPath()
        header_path.setFillRule(Qt.WindingFill)
        header_path.addRoundedRect(0, 0, self.width, self.header_height, 6, 6)
        # 覆盖底部圆角为直角
        header_path.addRect(0, self.header_height - 6, self.width, 6)

        gradient = QLinearGradient(0, 0, self.width, 0)
        gradient.setColorAt(0, header_color)
        gradient.setColorAt(1, header_color.darker(108))
        painter.fillPath(header_path, QBrush(gradient))

        # 标题文字
        font = QFont("Microsoft YaHei", 9, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))

        display_name = self.node_name[:16] + ".." if len(self.node_name) > 16 else self.node_name
        painter.drawText(QRectF(6, 0, self.width - 12, self.header_height),
                         Qt.AlignVCenter | Qt.AlignCenter,
                         display_name)

        # 分类标签
        if self.category != "default":
            font_small = QFont("Microsoft YaHei", 7)
            painter.setFont(font_small)
            painter.setPen(QColor(160, 160, 180))
            painter.drawText(QRectF(6, self.header_height - 13, self.width - 12, 11),
                            Qt.AlignRight,
                            self.category[:10])

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setSelected(True)
            self.event_bus.emit(Event(
                type=EventType.NODE_SELECTED,
                data={
                    "node_id": self.node_id,
                    "node_metadata": {
                        "id": self.node_id,
                        "name": self.node_name,
                        "category": self.category,
                        "inputs": self.inputs,
                        "outputs": self.outputs,
                        "parameters": self.parameters
                    }
                }
            ))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.event_bus.emit(Event(
            type=EventType.NODE_DOUBLE_CLICKED,
            data={"node_id": self.node_id}
        ))
        super().mouseDoubleClickEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            self.event_bus.emit(Event(
                type=EventType.NODE_MOVED,
                data={"node_id": self.node_id, "pos_x": value.x(), "pos_y": value.y()}
            ))
        elif change == QGraphicsItem.ItemSelectedChange:
            self._selected = value
            self.update()
        return super().itemChange(change, value)

    def set_execution_state(self, state: str):
        """设置执行状态 (None/Running/Success/Error)"""
        self._execution_state = state
        self.update()

    def get_input_socket(self, name: str):
        for socket in self.input_sockets:
            if socket.socket_name == name:
                return socket
        return None

    def get_output_socket(self, name: str):
        for socket in self.output_sockets:
            if socket.socket_name == name:
                return socket
        return None

    def get_socket_by_name(self, name: str, is_input: bool):
        if is_input:
            return self.get_input_socket(name)
        else:
            return self.get_output_socket(name)

    def update_node_data(self, node_data: dict):
        self.node_name = node_data.get("name", self.node_name)
        self.update()
