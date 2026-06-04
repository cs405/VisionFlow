"""
节点图形项 - 绘制和交互
严格解耦：只通过EventBus与Core层通信
"""

from PySide6.QtWidgets import (
    QGraphicsItem, QStyleOptionGraphicsItem, QGraphicsTextItem
)
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QBrush, QColor, QPen, QFont, QPainter, QPainterPath,
    QLinearGradient, QGradient
)

from core.events import EventBus, Event, EventType

from .socket_item import GraphicsSocket


class GraphicsNode(QGraphicsItem):
    """
    图形节点
    负责节点的可视化显示和用户交互
    """

    # 节点颜色方案
    COLORS = {
        "io": {"bg": QColor(40, 60, 50), "header": QColor(60, 100, 70)},
        "preprocessing": {"bg": QColor(50, 50, 60), "header": QColor(70, 70, 100)},
        "feature": {"bg": QColor(60, 50, 50), "header": QColor(100, 70, 70)},
        "match": {"bg": QColor(50, 50, 50), "header": QColor(80, 80, 100)},
        "measurement": {"bg": QColor(50, 60, 60), "header": QColor(70, 100, 100)},
        "enhance": {"bg": QColor(60, 50, 40), "header": QColor(100, 80, 60)},
        "geometry": {"bg": QColor(50, 50, 55), "header": QColor(80, 80, 90)},
        "color": {"bg": QColor(55, 45, 55), "header": QColor(90, 70, 90)},
        "default": {"bg": QColor(50, 50, 60), "header": QColor(70, 70, 100)}
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
        self.header_height = 32

        # 端口
        self.input_sockets = []
        self.output_sockets = []

        # 交互状态
        self._selected = False
        self._hovered = False

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
        # 输入端口（左侧）
        for i, socket_def in enumerate(self.inputs):
            socket = GraphicsSocket(socket_def, self, self.event_bus, is_input=True)
            socket.setPos(0, self.header_height + 15 + i * 28)
            socket.setParentItem(self)
            self.input_sockets.append(socket)

        # 输出端口（右侧）
        for i, socket_def in enumerate(self.outputs):
            socket = GraphicsSocket(socket_def, self, self.event_bus, is_input=False)
            socket.setPos(self.width, self.header_height + 15 + i * 28)
            socket.setParentItem(self)
            self.output_sockets.append(socket)

        # 调整高度
        max_sockets = max(len(self.input_sockets), len(self.output_sockets), 1)
        self.height = self.header_height + max_sockets * 28 + 15

    def _get_colors(self):
        """获取节点颜色"""
        colors = self.COLORS.get(self.category, self.COLORS["default"])
        if self._selected:
            bg = colors["header"].lighter(120)
            header = colors["header"].lighter(120)
        elif self._hovered:
            bg = colors["bg"].lighter(110)
            header = colors["header"].lighter(110)
        else:
            bg = colors["bg"]
            header = colors["header"]
        return bg, header

    def boundingRect(self) -> QRectF:
        """边界矩形"""
        return QRectF(0, 0, self.width, self.height)

    def shape(self) -> QPainterPath:
        """形状（用于碰撞检测）"""
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 6, 6)
        return path

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        """绘制节点"""
        painter.setRenderHint(QPainter.Antialiasing)

        bg_color, header_color = self._get_colors()

        # 节点背景
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 6, 6)
        painter.fillPath(path, QBrush(bg_color))

        # 边框
        border_color = QColor(80, 80, 100) if not self._selected else QColor(100, 150, 200)
        painter.setPen(QPen(border_color, 1.5))
        painter.drawPath(path)

        # 标题栏
        header_path = QPainterPath()
        header_path.moveTo(6, 0)
        header_path.lineTo(self.width - 6, 0)
        header_path.arcTo(self.width - 12, 0, 12, 12, 90, -90)
        header_path.lineTo(self.width, self.header_height)
        header_path.lineTo(0, self.header_height)
        header_path.lineTo(0, 12)
        header_path.arcTo(0, 0, 12, 12, 180, -90)
        header_path.closeSubpath()

        # 标题栏渐变
        gradient = QLinearGradient(0, 0, self.width, 0)
        gradient.setColorAt(0, header_color)
        gradient.setColorAt(1, header_color.darker(105))
        painter.fillPath(header_path, QBrush(gradient))

        # 标题文字
        font = QFont("Microsoft YaHei", 9, QFont.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))

        # 截断过长标题
        display_name = self.node_name[:12] + ".." if len(self.node_name) > 12 else self.node_name
        painter.drawText(QRectF(8, 0, self.width - 16, self.header_height),
                         Qt.AlignVCenter | Qt.AlignCenter,
                         display_name)

        # 分类标签（小字）
        if self.category != "default":
            font_small = QFont("Microsoft YaHei", 7)
            painter.setFont(font_small)
            painter.setPen(QColor(180, 180, 200))
            painter.drawText(QRectF(8, self.header_height - 14, self.width - 16, 12),
                             Qt.AlignRight,
                             self.category)

    def hoverEnterEvent(self, event):
        """鼠标进入"""
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        """鼠标离开"""
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.LeftButton:
            self.setSelected(True)
            # 发送节点选中事件
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
        """鼠标双击 - 打开参数面板"""
        self.event_bus.emit(Event(
            type=EventType.NODE_DOUBLE_CLICKED,
            data={"node_id": self.node_id}
        ))
        super().mouseDoubleClickEvent(event)

    def itemChange(self, change, value):
        """项目变化事件"""
        if change == QGraphicsItem.ItemPositionChange:
            # 发送节点位置变化事件
            self.event_bus.emit(Event(
                type=EventType.NODE_MOVED,
                data={
                    "node_id": self.node_id,
                    "pos_x": value.x(),
                    "pos_y": value.y()
                }
            ))
        elif change == QGraphicsItem.ItemSelectedChange:
            self._selected = value
            self.update()

        return super().itemChange(change, value)

    def get_input_socket(self, name: str):
        """获取输入端口"""
        for socket in self.input_sockets:
            if socket.socket_name == name:
                return socket
        return None

    def get_output_socket(self, name: str):
        """获取输出端口"""
        for socket in self.output_sockets:
            if socket.socket_name == name:
                return socket
        return None

    def get_socket_by_name(self, name: str, is_input: bool):
        """根据名称获取端口"""
        if is_input:
            return self.get_input_socket(name)
        else:
            return self.get_output_socket(name)

    def update_node_data(self, node_data: dict):
        """更新节点数据"""
        self.node_name = node_data.get("name", self.node_name)
        self.update()