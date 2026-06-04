"""
节点编辑器主控件 - 整合场景和视图
负责拖拽创建节点、连接交互等
"""

from PySide6.QtWidgets import QWidget, QGraphicsView, QVBoxLayout
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import QPainter, QWheelEvent, QMouseEvent, QBrush, QColor, QPen

from core.events import EventBus, Event, EventType

from .scene import NodeScene
from .edge_item import GraphicsEdge


class NodeGraphicsView(QGraphicsView):
    """节点图形视图"""

    def __init__(self, scene: NodeScene, parent=None):
        super().__init__(scene, parent)

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        # 临时连接线
        self.temp_edge = None
        self.connection_start = None

        self.zoom_factor = 1.15
        self.zoom_range = (0.1, 3.0)

    def wheelEvent(self, event: QWheelEvent):
        """鼠标滚轮缩放"""
        if event.modifiers() == Qt.ControlModifier:
            zoom = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
            new_zoom = self.transform().m11() * zoom

            if self.zoom_range[0] <= new_zoom <= self.zoom_range[1]:
                self.scale(zoom, zoom)
        else:
            super().wheelEvent(event)

    def reset_view(self):
        """重置视图"""
        self.resetTransform()
        self.centerOn(0, 0)

    def fit_to_content(self):
        """适应内容大小"""
        if self.scene():
            rect = self.scene().itemsBoundingRect()
            if not rect.isNull():
                self.fitInView(rect, Qt.KeepAspectRatio)


class NodeEditorWidget(QWidget):
    """节点编辑器主控件"""

    def __init__(self, event_bus: EventBus, parent=None):  # 修复：只需要 event_bus，不需要 workflow
        super().__init__(parent)

        self.event_bus = event_bus
        self.scene = NodeScene(event_bus, self)
        self.view = NodeGraphicsView(self.scene, self)

        # 连接状态
        self.is_connecting = False
        self.connection_start_socket = None

        # 布局
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.setLayout(layout)

        # 接受拖拽
        self.setAcceptDrops(True)

        # 订阅事件
        self._subscribe_events()

    def _subscribe_events(self):
        """订阅事件"""
        self.event_bus.subscribe(EventType.CONNECTION_STARTED, self._on_connection_started)
        self.event_bus.subscribe(EventType.CONNECTION_DRAGGING, self._on_connection_dragging)
        self.event_bus.subscribe(EventType.CONNECTION_FINISHED, self._on_connection_finished)
        self.event_bus.subscribe(EventType.NODE_CREATE_REQUEST, self._on_node_create_request)

    def dragEnterEvent(self, event):
        """拖拽进入"""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """放置 - 创建节点"""
        node_type = event.mimeData().text()
        scene_pos = self.view.mapToScene(event.position().toPoint())

        # 发送创建节点事件
        self.event_bus.emit(Event(
            type=EventType.NODE_CREATE_REQUEST,
            data={
                "node_type": node_type,
                "pos_x": scene_pos.x(),
                "pos_y": scene_pos.y()
            }
        ))

    def _on_node_create_request(self, event: Event):
        """处理节点创建请求"""
        data = event.data
        node_type = data.get("node_type")
        pos_x = data.get("pos_x", 0)
        pos_y = data.get("pos_y", 0)

        # 发送到core层创建节点
        self.event_bus.emit(Event(
            type=EventType.NODE_CREATE,
            data={
                "node_type": node_type,
                "pos_x": pos_x,
                "pos_y": pos_y
            }
        ))

    def _on_connection_started(self, event: Event):
        """连接开始"""
        data = event.data
        self.is_connecting = True
        self.connection_start_socket = {
            "node_id": data.get("node_id"),
            "socket_name": data.get("socket_name"),
            "is_input": data.get("is_input"),
            "data_type": data.get("data_type"),
            "position": QPointF(data["position"][0], data["position"][1])
        }

    def _on_connection_dragging(self, event: Event):
        """连接拖拽中"""
        if not self.is_connecting:
            return

        data = event.data
        start_pos = QPointF(data["from_pos"][0], data["from_pos"][1])
        end_pos = QPointF(data["to_pos"][0], data["to_pos"][1])

        # 显示临时连接线
        self._show_temp_edge(start_pos, end_pos)

    def _show_temp_edge(self, start: QPointF, end: QPointF):
        """显示临时连接线"""
        # 移除旧的临时线
        if hasattr(self.scene, 'temp_edge') and self.scene.temp_edge:
            self.scene.removeItem(self.scene.temp_edge)

        # 创建临时线
        class TempSocket:
            def __init__(self, pos, data_type):
                self._pos = pos
                self._data_type = data_type
            def get_scene_position(self):
                return self._pos
            def get_data_type(self):
                return self._data_type

        temp_from = TempSocket(start, self.connection_start_socket["data_type"])
        temp_to = TempSocket(end, self.connection_start_socket["data_type"])

        self.scene.temp_edge = GraphicsEdge(temp_from, temp_to, self.event_bus)
        # 设置虚线样式
        pen = QPen(QColor(150, 150, 180), 2, Qt.DashLine)
        self.scene.temp_edge.setPen(pen)
        self.scene.addItem(self.scene.temp_edge)

    def _on_connection_finished(self, event: Event):
        """连接完成"""
        data = event.data

        if self.is_connecting and self.connection_start_socket:
            # 移除临时线
            if hasattr(self.scene, 'temp_edge') and self.scene.temp_edge:
                self.scene.removeItem(self.scene.temp_edge)
                self.scene.temp_edge = None

            # 查找目标socket（通过鼠标位置）
            cursor_pos = self.cursor().pos()
            view_pos = self.view.mapFromGlobal(cursor_pos)
            scene_pos = self.view.mapToScene(view_pos)

            # 查找场景中的socket
            target_socket = self._find_socket_at_position(scene_pos)

            if target_socket and self.connection_start_socket:
                start = self.connection_start_socket
                end = target_socket

                # 验证连接有效性
                if self._validate_connection(start, end):
                    # 发送添加连接事件
                    if start["is_input"] and not end["is_input"]:
                        self.event_bus.emit(Event(
                            type=EventType.WORKFLOW_EDGE_ADDED,
                            data={
                                "from_node": end["node_id"],
                                "from_socket": end["socket_name"],
                                "to_node": start["node_id"],
                                "to_socket": start["socket_name"]
                            }
                        ))
                    elif not start["is_input"] and end["is_input"]:
                        self.event_bus.emit(Event(
                            type=EventType.WORKFLOW_EDGE_ADDED,
                            data={
                                "from_node": start["node_id"],
                                "from_socket": start["socket_name"],
                                "to_node": end["node_id"],
                                "to_socket": end["socket_name"]
                            }
                        ))

        self.is_connecting = False
        self.connection_start_socket = None

    def _find_socket_at_position(self, scene_pos: QPointF):
        """查找指定位置的socket"""
        items = self.scene.items(scene_pos)
        for item in items:
            if hasattr(item, 'socket_name') and hasattr(item, 'parent_node'):
                return {
                    "node_id": item.parent_node.node_id,
                    "socket_name": item.socket_name,
                    "is_input": item.is_input,
                    "data_type": item.data_type,
                    "socket_item": item
                }
        return None

    def _validate_connection(self, start: dict, end: dict) -> bool:
        """验证连接有效性"""
        # 不能连接同一个节点
        if start["node_id"] == end["node_id"]:
            return False

        # 必须一个输入一个输出
        if start["is_input"] == end["is_input"]:
            return False

        # 检查数据类型兼容性
        start_type = start["data_type"]
        end_type = end["data_type"]

        if start_type != end_type and end_type != "any" and start_type != "any":
            return False

        return True

    def add_node_graphics(self, node_data: dict):
        """添加节点图形"""
        self.scene.add_node_graphics(node_data)

    def remove_node_graphics(self, node_id: str):
        """移除节点图形"""
        self.scene.remove_node_graphics(node_id)

    def add_edge_graphics(self, edge_data: dict):
        """添加连线图形"""
        self.scene.add_edge_graphics(edge_data)

    def remove_edge_graphics(self, edge_data: dict):
        """移除连线图形"""
        self.scene.remove_edge_graphics(edge_data)

    def refresh_from_workflow_data(self, workflow_data: dict):
        """从工作流数据刷新显示"""
        self.scene.clear_all()

        # 重建节点
        for node_data in workflow_data.get("nodes", []):
            self.scene.add_node_graphics(node_data)

        # 重建连接
        for conn in workflow_data.get("connections", []):
            self.scene.add_edge_graphics(conn)

        # 适应内容
        QTimer.singleShot(100, self.view.fit_to_content)

    def clear_scene(self):
        """清空场景"""
        self.scene.clear_all()

    def reset_view(self):
        """重置视图"""
        self.view.reset_view()