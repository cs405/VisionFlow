"""
连线图形项 - 连接两个端口
"""

from PySide6.QtWidgets import QGraphicsPathItem
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
        self._hovered = False

        # 设置标志
        self.setFlag(QGraphicsPathItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
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

        # 计算控制点（贝塞尔曲线）
        dx = abs(end.x() - start.x()) * 0.5
        ctrl1 = QPointF(start.x() + dx, start.y())
        ctrl2 = QPointF(end.x() - dx, end.y())

        path = QPainterPath()
        path.moveTo(start)
        path.cubicTo(ctrl1, ctrl2, end)

        self.setPath(path)

        # 设置画笔
        self._update_pen()

    def _update_pen(self):
        """更新画笔"""
        if self._selected:
            color = QColor(255, 200, 100)
            width = 3
        elif self._hovered:
            color = QColor(200, 180, 100)
            width = 2.5
        else:
            # 根据数据类型选择颜色
            data_type = self.from_socket.get_data_type() if self.from_socket else "any"
            color_map = {
                "image": QColor(100, 200, 100),
                "number": QColor(100, 150, 200),
                "any": QColor(150, 150, 180)
            }
            color = color_map.get(data_type, QColor(150, 150, 180))
            width = 2

        pen = QPen(color, width)
        pen.setStyle(Qt.SolidLine)
        self.setPen(pen)

    def paint(self, painter: QPainter, option, widget=None):
        """绘制连线"""
        self.update_path()
        super().paint(painter, option, widget)

    def hoverEnterEvent(self, event):
        """鼠标进入"""
        self._hovered = True
        self._update_pen()
        self.update()

    def hoverLeaveEvent(self, event):
        """鼠标离开"""
        self._hovered = False
        self._update_pen()
        self.update()

    def mousePressEvent(self, event):
        """鼠标按下"""
        if event.button() == Qt.LeftButton:
            self._selected = True
            self._update_pen()
            self.update()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """鼠标双击 - 删除连线"""
        if self.from_socket and self.to_socket:
            from_node = self.from_socket.parent_node
            to_node = self.to_socket.parent_node

            # 发送删除连接事件
            self.event_bus.emit(Event(
                type=EventType.WORKFLOW_EDGE_REMOVED,
                data={
                    "from_node": from_node.node_id,
                    "from_socket": self.from_socket.socket_name,
                    "to_node": to_node.node_id,
                    "to_socket": self.to_socket.socket_name
                }
            ))

        super().mouseDoubleClickEvent(event)

    def set_selected(self, selected: bool):
        """设置选中状态"""
        self._selected = selected
        self._update_pen()
        self.update()

    def get_connection_info(self) -> dict:
        """获取连接信息"""
        return {
            "from_node": self.from_socket.parent_node.node_id,
            "from_socket": self.from_socket.socket_name,
            "to_node": self.to_socket.parent_node.node_id,
            "to_socket": self.to_socket.socket_name
        }