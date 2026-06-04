"""
端口图形项 - 绘制输入/输出端口
"""

from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QFont, QPainter

from core.node_base import Socket
from core.events import EventBus, Event, EventType


class GraphicsSocket(QGraphicsItem):
    """图形端口"""

    # 颜色映射
    COLOR_MAP = {
        "image": QColor(100, 200, 100),  # 绿色
        "gray": QColor(150, 150, 100),  # 黄绿
        "number": QColor(100, 150, 200),  # 蓝色
        "string": QColor(200, 150, 100),  # 橙色
        "bool": QColor(200, 100, 150),  # 紫色
        "point": QColor(150, 100, 200),  # 紫罗兰
        "rect": QColor(100, 200, 200),  # 青色
        "roi_list": QColor(200, 200, 100),  # 黄色
        "any": QColor(150, 150, 150)  # 灰色
    }

    def __init__(self, socket_def: Socket, parent_node, event_bus: EventBus):
        super().__init__(parent_node)

        self.socket_def = socket_def
        self.parent_node = parent_node
        self.event_bus = event_bus

        self.radius = 6
        self._hovered = False

        # 设置标志
        self.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)

        # 标签文字
        self.label = QGraphicsTextItem(socket_def.name, self)
        self.label.setFont(QFont("Microsoft YaHei", 8))
        self.label.setDefaultTextColor(QColor(200, 200, 200))

        if socket_def.is_input:
            self.label.setPos(self.radius + 4, -self.label.boundingRect().height() / 2)
        else:
            self.label.setPos(-self.radius - self.label.boundingRect().width() - 4,
                              -self.label.boundingRect().height() / 2)

    def boundingRect(self) -> QRectF:
        """边界矩形"""
        return QRectF(-self.radius, -self.radius, self.radius * 2, self.radius * 2)

    def paint(self, painter: QPainter, option, widget=None):
        """绘制端口"""
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取颜色
        color = self.COLOR_MAP.get(self.socket_def.data_type.value, QColor(150, 150, 150))

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

    def get_scene_position(self) -> QPointF:
        """获取场景坐标"""
        return self.scenePos()