"""
节点图形项 - 绘制和交互
"""

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsLinearLayout, QGraphicsWidget, QStyleOptionGraphicsItem
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QBrush, QColor, QPen, QFont, QPainter, QPainterPath,
    QLinearGradient, QGradient
)

from core.node_base import NodeBase
from core.events import EventBus, Event, EventType

from .socket_item import GraphicsSocket


class GraphicsNode(QGraphicsItem):
    """图形节点"""

    def __init__(self, node: NodeBase, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.node = node
        self.event_bus = event_bus

        # 尺寸
        self.width = 160
        self.height = 80
        self.header_height = 30

        # 端口
        self.input_sockets = []
        self.output_sockets = []

        # 交互状态
        self._selected = False
        self._dragging = False

        # 设置标志
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        # 创建端口
        self._create_sockets()

        # 设置Z序
        self.setZValue(1)

    def _create_sockets(self):
        """创建端口图形项"""
        # 输入端口（左侧）
        for i, socket_def in enumerate(self.node.input_sockets):
            socket = GraphicsSocket(socket_def, self, self.event_bus)
            socket.setPos(0, self.header_height + 10 + i * 25)
            socket.setParentItem(self)
            self.input_sockets.append(socket)

        # 输出端口（右侧）
        for i, socket_def in enumerate(self.node.output_sockets):
            socket = GraphicsSocket(socket_def, self, self.event_bus)
            socket.setPos(self.width, self.header_height + 10 + i * 25)
            socket.setParentItem(self)
            self.output_sockets.append(socket)

        # 调整高度
        max_sockets = max(len(self.input_sockets), len(self.output_sockets), 1)
        self.height = self.header_height + max_sockets * 25 + 10

    def boundingRect(self) -> QRectF:
        """边界矩形"""
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        """绘制节点"""
        painter.setRenderHint(QPainter.Antialiasing)

        # 节点背景
        if self._selected:
            bg_color = QColor(80, 100, 120)
        else:
            bg_color = QColor(50, 50, 60)

        # 圆角矩形路径
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 8, 8)

        # 填充背景
        painter.fillPath(path, QBrush(bg_color))

        # 边框
        pen = QPen(QColor(100, 100, 120), 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

        # 标题栏
        header_path = QPainterPath()
        header_path.moveTo(8, 0)
        header_path.lineTo(self.width - 8, 0)
        header_path.arcTo(self.width - 16, 0, 16, 16, 90, -90)
        header_path.lineTo(self.width, self.header_height)
        header_path.lineTo(0, self.header_height)
        header_path.lineTo(0, 16)
        header_path.arcTo(0, 0, 16, 16, 180, -90)
        header_path.closeSubpath()

        # 标题栏渐变
        gradient = QLinearGradient(0, 0, self.width, 0)
        gradient.setColorAt(0, QColor(70, 130, 200))
        gradient.setColorAt(1, QColor(50, 100, 160))
        painter.fillPath(header_path, QBrush(gradient))

        # 标题文字
        font = QFont("Microsoft YaHei", 9, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRectF(8, 0, self.width - 16, self.header_height),
                         Qt.AlignVCenter | Qt.AlignCenter,
                         self.node.name[:15])

    def itemChange(self, change, value):
        """项目变化事件"""
        if change == QGraphicsItem.ItemPositionChange:
            self.node.pos_x = value.x()
            self.node.pos_y = value.y()
            self.event_bus.emit_log("DEBUG", f"节点位置: {self.node.name} ({self.node.pos_x}, {self.node.pos_y})")
        elif change == QGraphicsItem.ItemSelectedChange:
            self._selected = value
            if value:
                self.event_bus.emit(Event(
                    type=EventType.NODE_SELECTED,
                    data={"node_id": self.node.node_id}
                ))

        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.LeftButton:
            self._dragging = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """鼠标释放"""
        self._dragging = False
        super().mouseReleaseEvent(event)

    def get_input_socket(self, name: str):
        """获取输入端口"""
        for socket in self.input_sockets:
            if socket.socket_def.name == name:
                return socket
        return None

    def get_output_socket(self, name: str):
        """获取输出端口"""
        for socket in self.output_sockets:
            if socket.socket_def.name == name:
                return socket
        return None