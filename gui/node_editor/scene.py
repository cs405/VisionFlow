"""
节点编辑器场景 - 管理所有图形项
"""

from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtCore import Qt, QPointF, QLineF  # 添加 QLineF
from PySide6.QtGui import QPen, QColor, QBrush, QPainterPath

from core.workflow import Workflow
from core.events import EventBus, Event, EventType

from .node_item import GraphicsNode
from .edge_item import GraphicsEdge


class NodeScene(QGraphicsScene):
    """节点编辑器场景"""

    def __init__(self, workflow: Workflow, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.workflow = workflow
        self.event_bus = event_bus

        # 图形项映射
        self.graphics_nodes: dict = {}  # node_id -> GraphicsNode
        self.graphics_edges: dict = {}  # edge_id -> GraphicsEdge

        # 场景设置
        self.setSceneRect(-5000, -5000, 10000, 10000)
        self.setBackgroundBrush(QBrush(QColor(40, 40, 40)))

        # 网格设置
        self.grid_size = 20
        self.grid_pen = QPen(QColor(60, 60, 60), 1, Qt.SolidLine)

        # 订阅事件
        self._subscribe_events()

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.WORKFLOW_NODE_ADDED, self._on_node_added)
        self.event_bus.subscribe(EventType.WORKFLOW_NODE_REMOVED, self._on_node_removed)
        self.event_bus.subscribe(EventType.WORKFLOW_EDGE_ADDED, self._on_edge_added)
        self.event_bus.subscribe(EventType.WORKFLOW_EDGE_REMOVED, self._on_edge_removed)

    def drawBackground(self, painter, rect):
        """绘制网格背景"""
        super().drawBackground(painter, rect)

        # 计算网格范围
        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)

        # 构建线条列表 - 使用 QLineF 对象
        lines = []

        # 垂直线
        x = left
        while x < rect.right():
            lines.append(QLineF(x, rect.top(), x, rect.bottom()))
            x += self.grid_size

        # 水平线
        y = top
        while y < rect.bottom():
            lines.append(QLineF(rect.left(), y, rect.right(), y))
            y += self.grid_size

        painter.setPen(self.grid_pen)
        painter.drawLines(lines)  # 现在 lines 是 QLineF 列表

    def _on_node_added(self, event: Event):
        """节点添加事件"""
        node = event.data.get("node")
        if node and node.node_id not in self.graphics_nodes:
            graphics_node = GraphicsNode(node, self.event_bus)
            graphics_node.setPos(node.pos_x, node.pos_y)
            self.addItem(graphics_node)
            self.graphics_nodes[node.node_id] = graphics_node

    def _on_node_removed(self, event: Event):
        """节点删除事件"""
        node_id = event.data.get("node_id")
        if node_id in self.graphics_nodes:
            graphics_node = self.graphics_nodes.pop(node_id)
            self.removeItem(graphics_node)

    def _on_edge_added(self, event: Event):
        """连接添加事件"""
        data = event.data
        edge_id = f"{data['from_node']}_{data['from_socket']}_{data['to_node']}_{data['to_socket']}"

        if edge_id in self.graphics_edges:
            return

        from_node = self.graphics_nodes.get(data['from_node'])
        to_node = self.graphics_nodes.get(data['to_node'])

        if from_node and to_node:
            from_socket = from_node.get_output_socket(data['from_socket'])
            to_socket = to_node.get_input_socket(data['to_socket'])

            if from_socket and to_socket:
                edge = GraphicsEdge(from_socket, to_socket, self.event_bus)
                self.addItem(edge)
                self.graphics_edges[edge_id] = edge

    def _on_edge_removed(self, event: Event):
        """连接删除事件"""
        data = event.data
        edge_id = f"{data['from_node']}_{data['from_socket']}_{data['to_node']}_{data['to_socket']}"

        if edge_id in self.graphics_edges:
            edge = self.graphics_edges.pop(edge_id)
            self.removeItem(edge)

    def get_graphics_node(self, node_id: str):
        """获取图形节点"""
        return self.graphics_nodes.get(node_id)

    def clear_all(self):
        """清空所有图形项"""
        for node in list(self.graphics_nodes.values()):
            self.removeItem(node)
        for edge in list(self.graphics_edges.values()):
            self.removeItem(edge)
        self.graphics_nodes.clear()
        self.graphics_edges.clear()