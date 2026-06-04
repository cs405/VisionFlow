"""
节点编辑器主控件 — WPF TabControl风格多流程管理
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView,
    QTabWidget, QPushButton, QLineEdit, QLabel, QTabBar
)
from PySide6.QtCore import Qt, QPointF, QTimer, Signal
from PySide6.QtGui import QPainter, QWheelEvent, QPen, QColor

from core.workflow import Workflow
from core.events import EventBus, Event, EventType
from core.registry import NodeRegistry

from .scene import NodeScene
from .edge_item import GraphicsEdge

from ..theme import Colors, Fonts


class NodeGraphicsView(QGraphicsView):
    """节点图形视图 — 支持Ctrl+滚轮缩放和双击适应"""

    def __init__(self, scene: NodeScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        self.zoom_factor = 1.15
        self.min_scale = 0.1
        self.max_scale = 3.0
        self._current_scale = 1.0

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.ControlModifier:
            zoom = self.zoom_factor if event.angleDelta().y() > 0 else 1 / self.zoom_factor
            new_zoom = self._current_scale * zoom
            if self.min_scale <= new_zoom <= self.max_scale:
                self.scale(zoom, zoom)
                self._current_scale = new_zoom
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.fit_to_bounds()
        super().mouseDoubleClickEvent(event)

    def reset_view(self):
        self.resetTransform()
        self._current_scale = 1.0
        self.centerOn(0, 0)

    def fit_to_bounds(self):
        if self.scene():
            rect = self.scene().itemsBoundingRect()
            if not rect.isNull():
                self.fitInView(rect.adjusted(-50, -50, 50, 50), Qt.KeepAspectRatio)
                self._current_scale = self.transform().m11()


class FlowTabHeader(QWidget):
    """流程Tab头部 — 名称编辑 + 操作按钮"""

    flow_start = Signal()
    flow_stop = Signal()
    flow_reset = Signal()
    flow_rename = Signal(str)

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._name = name
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)

        # 流程图标
        icon = QLabel("●")
        icon.setStyleSheet(f"color: {Colors.Green}; font-size: 10px;")
        layout.addWidget(icon)

        # 可编辑名称
        self.name_edit = QLineEdit(self._name)
        self.name_edit.setFixedWidth(80)
        self.name_edit.setAlignment(Qt.AlignCenter)
        self.name_edit.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {Colors.Foreground};
                border: none;
                font: 10px "{Fonts.Family}";
                padding: 0;
            }}
            QLineEdit:focus {{
                background: {Colors.Border};
            }}
        """)
        self.name_edit.editingFinished.connect(
            lambda: self.flow_rename.emit(self.name_edit.text())
        )
        layout.addWidget(self.name_edit)

        # 操作按钮
        btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {Colors.ForegroundDim};
                border: none;
                font-size: 10px;
                padding: 1px 4px;
            }}
            QPushButton:hover {{
                color: {Colors.Foreground};
                background: {Colors.Border};
                border-radius: 2px;
            }}
        """

        for label, signal in [("▶", self.flow_start), ("■", self.flow_stop), ("↺", self.flow_reset)]:
            btn = QPushButton(label)
            btn.setStyleSheet(btn_style)
            btn.setFixedSize(22, 20)
            btn.clicked.connect(signal)
            layout.addWidget(btn)

        self.setLayout(layout)


class NodeEditorWidget(QWidget):
    """节点编辑器主控件 — 多Tab流程管理"""

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus

        # 多流程支持
        self.workflows: dict[str, Workflow] = {}  # tab_name -> Workflow
        self.scenes: dict[str, NodeScene] = {}    # tab_name -> NodeScene
        self.views: dict[str, NodeGraphicsView] = {}  # tab_name -> NodeGraphicsView

        # 连接状态
        self.is_connecting = False
        self.connection_start_socket = None

        self._setup_ui()
        self._subscribe_events()

        # 创建默认流程
        self.add_flow_tab("主流程")

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab工具栏
        tab_bar = QWidget()
        tab_bar.setStyleSheet(f"background-color: {Colors.BackgroundLight}; border-bottom: 1px solid {Colors.Border};")
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(4, 2, 4, 2)
        tab_layout.setSpacing(2)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self._on_close_tab)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background-color: {Colors.Background};
            }}
            QTabBar::tab {{
                background: {Colors.BackgroundLight};
                color: {Colors.ForegroundDim};
                padding: 5px 8px;
                font: 10px "{Fonts.Family}";
                border: none;
                border-bottom: 2px solid transparent;
                min-width: 60px;
            }}
            QTabBar::tab:selected {{
                color: {Colors.Foreground};
                border-bottom-color: {Colors.Accent};
                background: {Colors.Background};
            }}
            QTabBar::tab:hover:!selected {{
                color: {Colors.Foreground};
            }}
        """)

        # "+" 按钮添加新流程
        self.add_btn = QPushButton("+")
        self.add_btn.setFixedSize(24, 24)
        self.add_btn.setToolTip("添加流程图")
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {Colors.ForegroundDim};
                border: none;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {Colors.Foreground};
                background: {Colors.Border};
                border-radius: 2px;
            }}
        """)
        self.add_btn.clicked.connect(lambda: self.add_flow_tab(f"流程{len(self.workflows)+1}"))
        self.tab_widget.setCornerWidget(self.add_btn, Qt.TopRightCorner)

        layout.addWidget(self.tab_widget)
        self.setLayout(layout)
        self.setAcceptDrops(True)

    def add_flow_tab(self, name: str):
        """添加流程Tab"""
        if name in self.workflows:
            name = f"{name} ({len(self.workflows)+1})"

        # 创建工作流
        workflow = Workflow()
        workflow.project_name = name

        # 创建场景和视图
        scene = NodeScene(self.event_bus)
        view = NodeGraphicsView(scene)

        self.workflows[name] = workflow
        self.scenes[name] = scene
        self.views[name] = view

        # 添加到Tab
        self.tab_widget.addTab(view, name)
        self.tab_widget.setCurrentWidget(view)

    def _on_close_tab(self, index: int):
        """关闭流程Tab"""
        if self.tab_widget.count() <= 1:
            return  # 至少保留一个Tab

        tab_name = self.tab_widget.tabText(index)
        self.tab_widget.removeTab(index)

        if tab_name in self.workflows:
            del self.workflows[tab_name]
            del self.scenes[tab_name]
            del self.views[tab_name]

    def _on_tab_changed(self, index: int):
        """Tab切换"""
        if index >= 0:
            tab_name = self.tab_widget.tabText(index)
            self.event_bus.emit(Event(
                type=EventType.WORKFLOW_NEW_FLOW,
                data={"flow_name": tab_name}
            ))

    def get_current_workflow(self) -> Workflow:
        """获取当前工作流"""
        index = self.tab_widget.currentIndex()
        if index >= 0:
            tab_name = self.tab_widget.tabText(index)
            return self.workflows.get(tab_name)
        return None

    def get_current_scene(self) -> NodeScene:
        """获取当前场景"""
        index = self.tab_widget.currentIndex()
        if index >= 0:
            tab_name = self.tab_widget.tabText(index)
            return self.scenes.get(tab_name)
        return None

    def get_current_view(self) -> NodeGraphicsView:
        """获取当前视图"""
        index = self.tab_widget.currentIndex()
        if index >= 0:
            tab_name = self.tab_widget.tabText(index)
            return self.views.get(tab_name)
        return None

    # ========== 拖拽创建节点 ==========

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        node_type = event.mimeData().text()
        view = self.get_current_view()
        if view:
            scene_pos = view.mapToScene(event.position().toPoint())
            self.event_bus.emit(Event(
                type=EventType.NODE_CREATE_REQUEST,
                data={
                    "node_type": node_type,
                    "pos_x": scene_pos.x(),
                    "pos_y": scene_pos.y()
                }
            ))

    # ========== 事件订阅 ==========

    def _subscribe_events(self):
        self.event_bus.subscribe(EventType.CONNECTION_STARTED, self._on_connection_started)
        self.event_bus.subscribe(EventType.CONNECTION_DRAGGING, self._on_connection_dragging)
        self.event_bus.subscribe(EventType.CONNECTION_FINISHED, self._on_connection_finished)
        self.event_bus.subscribe(EventType.NODE_CREATE_REQUEST, self._on_node_create_request)

    def _on_node_create_request(self, event: Event):
        data = event.data
        node_type = data.get("node_type")
        pos_x = data.get("pos_x", 0)
        pos_y = data.get("pos_y", 0)

        self.event_bus.emit(Event(
            type=EventType.NODE_CREATE,
            data={"node_type": node_type, "pos_x": pos_x, "pos_y": pos_y}
        ))

    def _on_connection_started(self, event: Event):
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
        if not self.is_connecting:
            return
        data = event.data
        start_pos = QPointF(data["from_pos"][0], data["from_pos"][1])
        end_pos = QPointF(data["to_pos"][0], data["to_pos"][1])
        self._show_temp_edge(start_pos, end_pos)

    def _show_temp_edge(self, start: QPointF, end: QPointF):
        scene = self.get_current_scene()
        if not scene:
            return
        if hasattr(scene, 'temp_edge') and scene.temp_edge:
            scene.removeItem(scene.temp_edge)

        class TempSocket:
            def __init__(self, pos, data_type):
                self._pos = pos
                self._data_type = data_type
            def get_scene_position(self):
                return self._pos
            def get_data_type(self):
                return self._data_type

        d_type = self.connection_start_socket.get("data_type", "any") if self.connection_start_socket else "any"
        temp_from = TempSocket(start, d_type)
        temp_to = TempSocket(end, d_type)
        scene.temp_edge = GraphicsEdge(temp_from, temp_to, self.event_bus)
        scene.temp_edge.setPen(QPen(QColor(150, 150, 180), 2, Qt.DashLine))
        scene.addItem(scene.temp_edge)

    def _on_connection_finished(self, event: Event):
        if self.is_connecting and self.connection_start_socket:
            scene = self.get_current_scene()
            if scene and hasattr(scene, 'temp_edge') and scene.temp_edge:
                scene.removeItem(scene.temp_edge)
                scene.temp_edge = None

            view = self.get_current_view()
            if view:
                cursor_pos = self.cursor().pos()
                view_pos = view.mapFromGlobal(cursor_pos)
                scene_pos = view.mapToScene(view_pos)
                target_socket = self._find_socket_at_position(scene_pos)

                if target_socket and self.connection_start_socket:
                    start = self.connection_start_socket
                    end = target_socket
                    if self._validate_connection(start, end):
                        if start["is_input"] and not end["is_input"]:
                            self.event_bus.emit(Event(
                                type=EventType.WORKFLOW_EDGE_ADDED,
                                data={"from_node": end["node_id"], "from_socket": end["socket_name"],
                                      "to_node": start["node_id"], "to_socket": start["socket_name"]}
                            ))
                        elif not start["is_input"] and end["is_input"]:
                            self.event_bus.emit(Event(
                                type=EventType.WORKFLOW_EDGE_ADDED,
                                data={"from_node": start["node_id"], "from_socket": start["socket_name"],
                                      "to_node": end["node_id"], "to_socket": end["socket_name"]}
                            ))

        self.is_connecting = False
        self.connection_start_socket = None

    def _find_socket_at_position(self, scene_pos: QPointF):
        scene = self.get_current_scene()
        if not scene:
            return None
        items = scene.items(scene_pos)
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
        if start["node_id"] == end["node_id"]:
            return False
        if start["is_input"] == end["is_input"]:
            return False
        start_type = start["data_type"]
        end_type = end["data_type"]
        if start_type != end_type and end_type != "any" and start_type != "any":
            if not (start_type == "gray" and end_type == "image"):
                return False
        return True

    # ========== 公开API ==========

    def add_node_graphics(self, node_data: dict):
        scene = self.get_current_scene()
        if scene:
            scene.add_node_graphics(node_data)

    def remove_node_graphics(self, node_id: str):
        scene = self.get_current_scene()
        if scene:
            scene.remove_node_graphics(node_id)

    def add_edge_graphics(self, edge_data: dict):
        scene = self.get_current_scene()
        if scene:
            scene.add_edge_graphics(edge_data)

    def remove_edge_graphics(self, edge_data: dict):
        scene = self.get_current_scene()
        if scene:
            scene.remove_edge_graphics(edge_data)

    def refresh_from_workflow(self, workflow_data: dict = None):
        """从工作流数据刷新"""
        scene = self.get_current_scene()
        if not scene:
            return
        scene.clear_all()

        wf = self.get_current_workflow()
        if wf and not workflow_data:
            workflow_data = wf.to_dict()

        if workflow_data:
            for node_data in workflow_data.get("nodes", []):
                scene.add_node_graphics(node_data)
            for conn in workflow_data.get("connections", []):
                scene.add_edge_graphics(conn)

        view = self.get_current_view()
        if view:
            QTimer.singleShot(100, view.fit_to_bounds)

    def clear_scene(self):
        scene = self.get_current_scene()
        if scene:
            scene.clear_all()

    def reset_view(self):
        view = self.get_current_view()
        if view:
            view.reset_view()
