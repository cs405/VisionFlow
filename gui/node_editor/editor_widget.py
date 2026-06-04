"""
WPF TabControl + Zoombox 流程图编辑区精确还原
- QTabWidget: 多流程切换 + 每Tab有名称+启动/停止/重置按钮
- Zoombox: QGraphicsView (双击Fit, FitOnSizeChange)
- 拖拽创建节点 + 拖拽连线交互
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView,
    QTabWidget, QPushButton, QTabBar, QLabel
)
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QPainter, QWheelEvent, QPen, QColor, QFont

from core.workflow import Workflow
from core.events import EventBus, Event, EventType
from core.registry import NodeRegistry
from .scene import NodeScene
from .edge_item import GraphicsEdge
from ..theme import Colors


class NodeGraphicsView(QGraphicsView):
    """WPF Zoombox — 双击适应 + Ctrl滚轮缩放"""

    def __init__(self, scene: NodeScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setStyleSheet(f"background-color: {Colors.SceneBackground.name()}; border: none;")

        self._zoom_factor = 1.15
        self._min_scale = 0.1
        self._max_scale = 3.0
        self._current_scale = 1.0

    def wheelEvent(self, e: QWheelEvent):
        if e.modifiers() == Qt.ControlModifier:
            z = self._zoom_factor if e.angleDelta().y() > 0 else 1 / self._zoom_factor
            ns = self._current_scale * z
            if self._min_scale <= ns <= self._max_scale:
                self.scale(z, z)
                self._current_scale = ns
        else:
            super().wheelEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.fit_to_bounds()
        super().mouseDoubleClickEvent(e)

    def fit_to_bounds(self):
        s = self.scene()
        if s:
            r = s.itemsBoundingRect()
            if not r.isNull():
                self.fitInView(r.adjusted(-80, -80, 80, 80), Qt.KeepAspectRatio)
                self._current_scale = self.transform().m11()

    def reset_view(self):
        self.resetTransform()
        self._current_scale = 1.0


class NodeEditorWidget(QWidget):
    """WPF TabControl 多流程节点编辑器"""

    def __init__(self, event_bus: EventBus, parent=None):
        super().__init__(parent)
        self.event_bus = event_bus

        self._flows: dict[str, Workflow] = {}
        self._scenes: dict[str, NodeScene] = {}
        self._views: dict[str, NodeGraphicsView] = {}

        self._connecting = False
        self._conn_start = None

        self._setup_ui()
        self._subscribe_events()
        self._add_flow("主流程")

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {Colors.Background}; }}
            QTabBar::tab {{
                background: {Colors.BackgroundLight};
                color: {Colors.ForegroundDim};
                padding: 5px 8px;
                font: 10px "Microsoft YaHei";
                border: none;
                border-bottom: 2px solid transparent;
                min-width: 60px;
            }}
            QTabBar::tab:selected {{
                color: {Colors.Foreground};
                border-bottom-color: {Colors.Accent};
            }}
            QTabBar::tab:hover:!selected {{ color: {Colors.Foreground}; }}
        """)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setToolTip("添加新流程")
        add_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {Colors.ForegroundDim}; border: none; font-size: 16px; font-weight: bold; }}
            QPushButton:hover {{ color: {Colors.Foreground}; background: {Colors.Border}; border-radius: 2px; }}
        """)
        add_btn.clicked.connect(lambda: self._add_flow(f"流程{len(self._flows)+1}"))
        self.tabs.setCornerWidget(add_btn, Qt.TopRightCorner)

        layout.addWidget(self.tabs)
        self.setLayout(layout)
        self.setAcceptDrops(True)

    def _add_flow(self, name: str):
        base = name
        i = 1
        while name in self._flows:
            name = f"{base}({i})"
            i += 1

        wf = Workflow()
        wf.project_name = name
        scene = NodeScene(self.event_bus)
        view = NodeGraphicsView(scene)

        self._flows[name] = wf
        self._scenes[name] = scene
        self._views[name] = view

        idx = self.tabs.addTab(view, name)
        self.tabs.setCurrentIndex(idx)

    def _close_tab(self, idx: int):
        if self.tabs.count() <= 1:
            return
        name = self.tabs.tabText(idx)
        self.tabs.removeTab(idx)
        self._flows.pop(name, None)
        self._scenes.pop(name, None)
        self._views.pop(name, None)

    def _on_tab_changed(self, idx: int):
        if idx >= 0:
            self.event_bus.emit(Event(type=EventType.WORKFLOW_NEW_FLOW,
                                       data={"flow_name": self.tabs.tabText(idx)}))

    def _current_flow(self) -> Workflow:
        idx = self.tabs.currentIndex()
        return self._flows.get(self.tabs.tabText(idx)) if idx >= 0 else None

    def _current_scene(self) -> NodeScene:
        idx = self.tabs.currentIndex()
        return self._scenes.get(self.tabs.tabText(idx)) if idx >= 0 else None

    def _current_view(self) -> NodeGraphicsView:
        idx = self.tabs.currentIndex()
        return self._views.get(self.tabs.tabText(idx)) if idx >= 0 else None

    # ===== 拖拽创建节点 =====

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        node_type = e.mimeData().text()
        view = self._current_view()
        if view:
            sp = view.mapToScene(e.position().toPoint())
            self.event_bus.emit(Event(type=EventType.NODE_CREATE_REQUEST,
                data={"node_type": node_type, "pos_x": sp.x(), "pos_y": sp.y()}))

    # ===== 连线交互 =====

    def _subscribe_events(self):
        self.event_bus.subscribe(EventType.CONNECTION_STARTED, self._on_conn_start)
        self.event_bus.subscribe(EventType.CONNECTION_DRAGGING, self._on_conn_drag)
        self.event_bus.subscribe(EventType.CONNECTION_FINISHED, self._on_conn_finish)
        self.event_bus.subscribe(EventType.NODE_CREATE_REQUEST, self._on_create_req)

    def _on_create_req(self, e: Event):
        d = e.data
        self.event_bus.emit(Event(type=EventType.NODE_CREATE,
            data={"node_type": d["node_type"], "pos_x": d.get("pos_x", 0), "pos_y": d.get("pos_y", 0)}))

    def _on_conn_start(self, e: Event):
        d = e.data
        self._connecting = True
        self._conn_start = {"node_id": d["node_id"], "socket_name": d["socket_name"],
                            "is_input": d["is_input"], "data_type": d["data_type"]}

    def _on_conn_drag(self, e: Event):
        if not self._connecting:
            return
        d = e.data
        sp = QPointF(d["from_pos"][0], d["from_pos"][1])
        ep = QPointF(d["to_pos"][0], d["to_pos"][1])
        self._show_temp_edge(sp, ep)

    def _show_temp_edge(self, s, e):
        sc = self._current_scene()
        if not sc:
            return
        if hasattr(sc, 'temp_edge') and sc.temp_edge:
            sc.removeItem(sc.temp_edge)

        class T:
            def __init__(s2, p, dt): s2._p, s2._dt = p, dt
            def get_scene_position(s2): return s2._p
            def get_data_type(s2): return s2._dt

        dt = self._conn_start.get("data_type", "any") if self._conn_start else "any"
        sc.temp_edge = GraphicsEdge(T(s, dt), T(e, dt), self.event_bus)
        sc.temp_edge.setPen(QPen(QColor(150, 150, 180), 2, Qt.DashLine))
        sc.addItem(sc.temp_edge)

    def _on_conn_finish(self, e: Event):
        if not self._connecting or not self._conn_start:
            return
        sc = self._current_scene()
        if sc and hasattr(sc, 'temp_edge') and sc.temp_edge:
            sc.removeItem(sc.temp_edge)
            sc.temp_edge = None

        view = self._current_view()
        if view:
            cp = self.cursor().pos()
            vp = view.mapFromGlobal(cp)
            sp = view.mapToScene(vp)
            target = self._find_socket(sp)
            if target and self._conn_start:
                st = self._conn_start
                if self._valid(st, target):
                    if st["is_input"] and not target["is_input"]:
                        self.event_bus.emit(Event(type=EventType.WORKFLOW_EDGE_ADDED, data={
                            "from_node": target["node_id"], "from_socket": target["socket_name"],
                            "to_node": st["node_id"], "to_socket": st["socket_name"]}))
                    elif not st["is_input"] and target["is_input"]:
                        self.event_bus.emit(Event(type=EventType.WORKFLOW_EDGE_ADDED, data={
                            "from_node": st["node_id"], "from_socket": st["socket_name"],
                            "to_node": target["node_id"], "to_socket": target["socket_name"]}))
        self._connecting = False
        self._conn_start = None

    def _find_socket(self, pos):
        sc = self._current_scene()
        if not sc:
            return None
        for item in sc.items(pos):
            if hasattr(item, 'socket_name') and hasattr(item, 'parent_node'):
                return {"node_id": item.parent_node.node_id, "socket_name": item.socket_name,
                        "is_input": item.is_input, "data_type": item.data_type}
        return None

    def _valid(self, a, b):
        if a["node_id"] == b["node_id"] or a["is_input"] == b["is_input"]:
            return False
        at, bt = a["data_type"], b["data_type"]
        return at == bt or bt == "any" or at == "any" or (at == "gray" and bt == "image")

    # ===== 公开API =====

    def refresh_from_workflow(self, data: dict = None):
        sc = self._current_scene()
        if not sc:
            return
        sc.clear_all()
        if data:
            for nd in data.get("nodes", []):
                sc.add_node_graphics(nd)
            for ed in data.get("connections", []):
                sc.add_edge_graphics(ed)
        view = self._current_view()
        if view:
            QTimer.singleShot(100, view.fit_to_bounds)

    def clear_scene(self):
        sc = self._current_scene()
        if sc:
            sc.clear_all()

    def reset_view(self):
        v = self._current_view()
        if v:
            v.reset_view()

    def add_node_graphics(self, nd: dict):
        sc = self._current_scene()
        if sc:
            sc.add_node_graphics(nd)

    def remove_node_graphics(self, nid: str):
        sc = self._current_scene()
        if sc:
            sc.remove_node_graphics(nid)

    def add_edge_graphics(self, ed: dict):
        sc = self._current_scene()
        if sc:
            sc.add_edge_graphics(ed)

    def remove_edge_graphics(self, ed: dict):
        sc = self._current_scene()
        if sc:
            sc.remove_edge_graphics(ed)
