"""
连线图形项 - 连接两个端口
"""

from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsItem
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor, QBrush

from core.events import EventBus, Event, EventType


class GraphicsEdge(QGraphicsPathItem):
    """图形连线"""

    def __init__(self, from_socket, to_socket, event_bus: EventBus):
        super().__init__()

        self.from_socket = from_socket
        self.to_socket = to_socket
        self.event_bus = event_bus

        self._selected = False

        # 设置标志
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(0)

        # 更新路径
        self.update_path()

    def update_path(self):
        """更新连线路径"""
        if not self.from_socket or not self.to_socket:
            return

        start = self.from_socket.get_scene_position()
        end = self.to_socket.get_scene_position()

        if start.isNull() or end.isNull():
            return

        # 贝塞尔曲线控制点
        ctrl_dist = abs(end.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + ctrl_dist, start.y())
        ctrl2 = QPointF(end.x() - ctrl_dist, end.y())

        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(ctrl1, ctrl2, end)

        self.setPath(path)

        # 设置画笔
        pen_color = QColor(150, 150, 180)
        if self._selected:
            pen_color = QColor(255, 200, 100)
            pen_width = 3
        else:
            pen_width = 2

        pen = QPen(pen_color, pen_width)
        pen.setStyle(Qt.SolidLine)
        self.setPen(pen)

    def paint(self, painter: QPainter, option, widget=None):
        """绘制连线"""
        self.update_path()
        super().paint(painter, option, widget)

    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.LeftButton:
            self._selected = True
            self.update()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击 - 删除连线"""
        # 获取连接信息
        from_node = self.from_socket.parent_node.node
        to_node = self.to_socket.parent_node.node

        self.event_bus.emit(Event(
            type=EventType.WORKFLOW_EDGE_REMOVED,
            data={
                "from_node": from_node.node_id,
                "from_socket": self.from_socket.socket_def.name,
                "to_node": to_node.node_id,
                "to_socket": self.to_socket.socket_def.name
            }
        ))

        # 同时从workflow中删除
        workflow = self.event_bus._listeners.get(EventType.WORKFLOW_EDGE_REMOVED)
        # 实际删除由workflow处理

        super().mouseDoubleClickEvent(event)

    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._selected = selected
        self.update()