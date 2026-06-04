"""
节点编辑器主控件 - 整合场景和视图
"""

from PySide6.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QVBoxLayout
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QWheelEvent, QMouseEvent  # 添加 QPainter

from core.workflow import Workflow
from core.registry import NodeRegistry
from core.events import EventBus

from .scene import NodeScene


class NodeGraphicsView(QGraphicsView):
    """节点图形视图"""

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)

        # 现在 QPainter 已导入，这行可以正常工作
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        self.zoom_factor = 1.15
        self.zoom_range = (0.1, 3.0)

    def wheelEvent(self, event: QWheelEvent):
        """鼠标滚轮缩放"""
        zoom = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
        new_zoom = self.transform().m11() * zoom

        if self.zoom_range[0] <= new_zoom <= self.zoom_range[1]:
            self.scale(zoom, zoom)

    def reset_view(self):
        """重置视图"""
        self.resetTransform()
        self.centerOn(0, 0)


class NodeEditorWidget(QWidget):
    """节点编辑器主控件"""

    def __init__(self, workflow: Workflow, event_bus: EventBus, parent=None):
        super().__init__(parent)

        self.workflow = workflow
        self.event_bus = event_bus
        self.node_registry = NodeRegistry()

        # 创建场景和视图
        self.scene = NodeScene(workflow, event_bus, self)
        self.view = NodeGraphicsView(self.scene, self)

        # 布局
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.setLayout(layout)

        # 接受拖拽
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        """拖拽进入"""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """放置 - 创建节点"""
        node_type = event.mimeData().text()
        scene_pos = self.view.mapToScene(event.position().toPoint())

        node = self.node_registry.create_instance(node_type)
        if node:
            node.pos_x = scene_pos.x()
            node.pos_y = scene_pos.y()
            self.workflow.add_node(node)

    def refresh_from_workflow(self):
        """从工作流刷新显示"""
        self.scene.clear_all()

        # 导入图形节点和边（延迟导入避免循环引用）
        from .node_item import GraphicsNode
        from .edge_item import GraphicsEdge

        # 重建节点
        for node in self.workflow.nodes.values():
            graphics_node = GraphicsNode(node, self.event_bus)
            graphics_node.setPos(node.pos_x, node.pos_y)
            self.scene.addItem(graphics_node)
            self.scene.graphics_nodes[node.node_id] = graphics_node

        # 重建连接
        for conn in self.workflow.connections:
            from_node = self.scene.graphics_nodes.get(conn['from_node'])
            to_node = self.scene.graphics_nodes.get(conn['to_node'])
            if from_node and to_node:
                from_socket = from_node.get_output_socket(conn['from_socket'])
                to_socket = to_node.get_input_socket(conn['to_socket'])
                if from_socket and to_socket:
                    edge = GraphicsEdge(from_socket, to_socket, self.event_bus)
                    self.scene.addItem(edge)
                    edge_id = f"{conn['from_node']}_{conn['from_socket']}_{conn['to_node']}_{conn['to_socket']}"
                    self.scene.graphics_edges[edge_id] = edge

    def clear_scene(self):
        """清空场景"""
        self.scene.clear_all()

    def reset_view(self):
        """重置视图"""
        self.view.reset_view()