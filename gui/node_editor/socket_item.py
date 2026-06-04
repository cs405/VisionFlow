"""
端口图形项 - 绘制输入/输出端口
支持拖拽连接
"""

from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QFont, QPainter

from core.events import EventBus, Event, EventType


class GraphicsSocket(QGraphicsItem):
    """
    图形端口
    支持拖拽创建连接
    """

    # 数据类型颜色映射
    COLOR_MAP = {
        "image": QColor(100, 200, 100),      # 绿色
        "gray": QColor(150, 150, 100),       # 黄绿
        "number": QColor(100, 150, 200),     # 蓝色
        "string": QColor(200, 150, 100),     # 橙色
        "bool": QColor(200, 100, 150),       # 紫色
        "point": QColor(150, 100, 200),      # 紫罗兰
        "rect": QColor(100, 200, 200),       # 青色
        "roi_list": QColor(200, 200, 100),   # 黄色
        "any": QColor(150, 150, 150)         # 灰色
    }

    def __init__(self, socket_def: dict, parent_node, event_bus: EventBus, is_input: bool):
        super().__init__(parent_node)

        self.socket_name = socket_def.get("name", "")
        self.data_type = socket_def.get("type", "any")
        self.is_input = is_input
        self.parent_node = parent_node
        self.event_bus = event_bus

        self.radius = 6
        self._hovered = False
        self._dragging = False
        self._drag_start = None

        # 设置标志
        self.setAcceptHoverEvents(True)

        # 标签文字
        self.label = QGraphicsTextItem(socket_def.get("name", ""), self)
        self.label.setFont(QFont("Microsoft YaHei", 8))
        self.label.setDefaultTextColor(QColor(180, 180, 180))

        # 根据输入/输出调整标签位置
        if self.is_input:
            self.label.setPos(self.radius + 4, -self.label.boundingRect().height() / 2)
        else:
            self.label.setPos(-self.radius - self.label.boundingRect().width() - 4,
                              -self.label.boundingRect().height() / 2)

    def boundingRect(self) -> QRectF:
        """边界矩形"""
        return QRectF(-self.radius - 2, -self.radius - 2,
                      self.radius * 2 + 4, self.radius * 2 + 4)

    def paint(self, painter: QPainter, option, widget=None):
        """绘制端口"""
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取颜色
        color = self.COLOR_MAP.get(self.data_type, QColor(150, 150, 150))

        # 高亮状态
        if self._hovered:
            painter.setBrush(QBrush(color.lighter(130)))
            painter.setPen(QPen(color.darker(150), 2))
        else:
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color.darker(120), 1.5))

        painter.drawEllipse(QPointF(0, 0), self.radius, self.radius)

    def hoverEnterEvent(self, event):
        """鼠标进入"""
        self._hovered = True
        self.update()

    def hoverLeaveEvent(self, event):
        """鼠标离开"""
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        """鼠标按下 - 开始拖拽连接"""
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = self.scenePos()

            # 发送开始连接事件
            self.event_bus.emit(Event(
                type=EventType.CONNECTION_STARTED,
                data={
                    "socket_id": id(self),
                    "node_id": self.parent_node.node_id,
                    "socket_name": self.socket_name,
                    "is_input": self.is_input,
                    "position": (self._drag_start.x(), self._drag_start.y()),
                    "data_type": self.data_type
                }
            ))

            event.accept()

    def mouseMoveEvent(self, event):
        """鼠标移动 - 更新拖拽连接"""
        if self._dragging:
            current_pos = self.scenePos()

            # 发送连接拖拽事件
            self.event_bus.emit(Event(
                type=EventType.CONNECTION_DRAGGING,
                data={
                    "from_pos": (self._drag_start.x(), self._drag_start.y()),
                    "to_pos": (current_pos.x(), current_pos.y())
                }
            ))

    def mouseReleaseEvent(self, event):
        """鼠标释放 - 完成连接"""
        if self._dragging:
            self._dragging = False

            # 发送完成连接事件
            self.event_bus.emit(Event(
                type=EventType.CONNECTION_FINISHED,
                data={
                    "from_socket_id": id(self),
                    "from_node_id": self.parent_node.node_id,
                    "from_socket_name": self.socket_name,
                    "from_is_input": self.is_input,
                    "from_data_type": self.data_type
                }
            ))

    def get_scene_position(self) -> QPointF:
        """获取场景坐标"""
        return self.scenePos()

    def get_data_type(self) -> str:
        """获取数据类型"""
        return self.data_type