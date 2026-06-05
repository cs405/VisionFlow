"""Editor widget — QGraphicsView + toolbar + mini-map + keyboard shortcuts.

Ported from H.Controls.Diagram.Presenter (DiagramPresenter, EditorWidget).

Features:
  - Zoom/pan with Ctrl+scroll and middle-mouse drag
  - Undo/Redo (Ctrl+Z / Ctrl+Y) via CommandStack
  - Copy/Paste (Ctrl+C / Ctrl+V)
  - Delete (Del / Backspace), Select All (Ctrl+A)
  - Fit-to-window (F), Zoom100 (Ctrl+0)
  - RunStep (Shift+F5) — single node execution
  - Mini-map corner overview
  - Toolbar with all command buttons
  - Drag-drop from toolbox
  - Context menu
"""

from PyQt5.QtWidgets import (QGraphicsView, QWidget, QVBoxLayout, QHBoxLayout,
                              QToolBar, QPushButton, QAction, QMenu,
                              QRubberBand, QLabel)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import (QPainter, QWheelEvent, QMouseEvent, QKeyEvent,
                          QColor, QPen, QBrush, QDragEnterEvent, QDropEvent,
                          QPainterPath, QFont)

from core.node_base import NodeBase, VisionNodeData
from core.workflow import WorkflowEngine
from core.events import EventType, event_system
from core.registry import node_registry

from gui.node_editor.scene import DiagramScene
from gui.node_editor.node_item import NodeItem, NodeState
from gui.node_editor.edge_item import EdgeItem
from gui.node_editor.socket_item import SocketItem

# ── Mini-map ──────────────────────────────────────────────────────────────

class MiniMapView(QGraphicsView):
    """Small overview of the full scene in the corner."""

    scene_point_clicked = pyqtSignal(QPointF)

    def __init__(self, scene: DiagramScene, parent=None):
        super().__init__(scene, parent)
        self.setFixedSize(180, 120)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHints(QPainter.Antialiasing)
        self.setFrameShape(QGraphicsView.Box)
        self.setStyleSheet("QGraphicsView { border: 2px solid #0078d4; border-radius: 4px; background: #1e1e1e; }")
        self.setInteractive(False)
        self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
        self.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)

        # Viewport rectangle overlay
        self._vp_rect: QRectF = QRectF()

    def sync_viewport(self, main_view: "DiagramEditorView"):
        """Update the minimap to reflect the main view's viewport."""
        vp_rect = main_view.mapToScene(main_view.viewport().rect()).boundingRect()
        self._vp_rect = vp_rect
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF):
        super().drawForeground(painter, rect)
        if self._vp_rect.isValid():
            painter.setPen(QPen(QColor("#0078d4"), 1.5))
            painter.setBrush(QBrush(QColor(0, 120, 212, 40)))
            painter.drawRect(self._vp_rect)

    def mousePressEvent(self, event: QMouseEvent):
        """Click to navigate the main view."""
        if event.button() == Qt.LeftButton:
            self.scene_point_clicked.emit(self.mapToScene(event.pos()))
            event.accept()
            return
        super().mousePressEvent(event)


# ── Diagram Editor View ───────────────────────────────────────────────────

class DiagramEditorView(QGraphicsView):
    """QGraphicsView with zoom/pan/fit, keyboard shortcuts, and drop support."""

    MIN_ZOOM = 0.05
    MAX_ZOOM = 5.0
    ZOOM_FACTOR = 1.15

    zoom_changed = pyqtSignal(float)
    node_dropped = pyqtSignal(str, QPointF)

    def __init__(self, scene: DiagramScene, parent=None):
        super().__init__(scene, parent)
        self._diagram_scene = scene
        self._zoom = 1.0
        self._pan_start: QPointF | None = None

        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setAcceptDrops(True)
        self.setCursor(Qt.ArrowCursor)

    # ── Zoom ──────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = self.ZOOM_FACTOR if delta > 0 else 1.0 / self.ZOOM_FACTOR
            new_zoom = self._zoom * factor
            if self.MIN_ZOOM <= new_zoom <= self.MAX_ZOOM:
                self._zoom = new_zoom
                self.scale(factor, factor)
                self.zoom_changed.emit(self._zoom)
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        self._zoom = min(self._zoom * self.ZOOM_FACTOR, self.MAX_ZOOM)
        self.scale(self.ZOOM_FACTOR, self.ZOOM_FACTOR)
        self.zoom_changed.emit(self._zoom)

    def zoom_out(self):
        self._zoom = max(self._zoom / self.ZOOM_FACTOR, self.MIN_ZOOM)
        self.scale(1.0 / self.ZOOM_FACTOR, 1.0 / self.ZOOM_FACTOR)
        self.zoom_changed.emit(self._zoom)

    def fit_to_window(self):
        self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()
        self.zoom_changed.emit(self._zoom)

    def zoom_to_100(self):
        self._zoom = 1.0
        self.resetTransform()
        self.zoom_changed.emit(self._zoom)

    @property
    def zoom_level(self) -> float:
        return self._zoom

    # ── Pan ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        btn = event.button()
        if btn in (Qt.MiddleButton, Qt.RightButton) and self._pan_start is not None:
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double-click → FitToBounds (WPF Zoombox behavior)."""
        if event.button() == Qt.LeftButton:
            self.fit_to_window()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    # ── Keyboard ──────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        k = event.key()
        mod = event.modifiers()

        if k == Qt.Key_Delete or k == Qt.Key_Backspace:
            self._diagram_scene.delete_selected()
        elif k == Qt.Key_A and mod & Qt.ControlModifier:
            for item in self._diagram_scene.get_all_node_items():
                item.setSelected(True)
        elif k == Qt.Key_C and mod & Qt.ControlModifier:
            self._diagram_scene.copy_selected()
        elif k == Qt.Key_V and mod & Qt.ControlModifier:
            self._diagram_scene.paste()
        elif k == Qt.Key_Z and mod & Qt.ControlModifier and mod & Qt.ShiftModifier:
            self._diagram_scene.redo()
        elif k == Qt.Key_Z and mod & Qt.ControlModifier:
            self._diagram_scene.undo()
        elif k == Qt.Key_Y and mod & Qt.ControlModifier:
            self._diagram_scene.redo()
        elif k == Qt.Key_F and not mod:
            self.fit_to_window()
        elif k == Qt.Key_0 and mod & Qt.ControlModifier:
            self.zoom_to_100()
        else:
            super().keyPressEvent(event)

    # ── Context menu (right-click without drag) ─────────────────────────

    def contextMenuEvent(self, event):
        if self._pan_start is not None:
            return  # was a drag, don't show menu
        pos = self.mapToScene(event.pos())
        menu = self._diagram_scene.context_menu(pos)
        if menu:
            menu.exec_(event.globalPos())

    # ── Drag-drop from toolbox ────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasText():
            type_name = event.mimeData().text()
            scene_pos = self.mapToScene(event.pos())
            self.node_dropped.emit(type_name, scene_pos)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


# ── Diagram Editor Widget ─────────────────────────────────────────────────

class DiagramEditorWidget(QWidget):
    """Full editor: toolbar + scene/view + minimap.

    Toolbar buttons match WPF Diagram Presenter toolbar:
      ▶ Run  ■ Stop  ⚡RunStep | ↩Undo ↪Redo | 📋Copy 📌Paste | Fit 1:1 | Zoom
    """

    node_selected = pyqtSignal(object)
    node_deselected = pyqtSignal()
    node_double_clicked = pyqtSignal(object)
    node_properties_requested = pyqtSignal(object)
    node_help_requested = pyqtSignal(object)
    node_executed = pyqtSignal(object, str, str)  # node, state("Success"/"Error"), time_span

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workflow: WorkflowEngine | None = None
        self._subscribed_workflow: WorkflowEngine | None = None
        self._mini_timer = QTimer(self)
        self._mini_timer.setInterval(100)
        self._mini_timer.timeout.connect(self._update_minimap)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Scene + View (create first — toolbar buttons reference them) ──
        body = QWidget()
        body_lo = QVBoxLayout(body); body_lo.setContentsMargins(0, 0, 0, 0); body_lo.setSpacing(0)

        self.scene = DiagramScene()
        self.view = DiagramEditorView(self.scene)

        self.scene.node_selected.connect(self.node_selected.emit)
        self.scene.node_deselected.connect(self.node_deselected.emit)
        self.scene.node_properties_requested.connect(self.node_properties_requested.emit)
        self.scene.node_help_requested.connect(self.node_help_requested.emit)
        self.scene.selectionChanged.connect(self._update_toolbar_state)
        self.view.node_dropped.connect(self._on_node_dropped)
        self._connect_socket_signals()

        body_lo.addWidget(self.view)
        layout.addWidget(body, 1)

        # Mini-map
        self._minimap = MiniMapView(self.scene, self)
        self._minimap.scene_point_clicked.connect(self._center_view_on_scene_point)
        self._minimap.move(6, 6)
        self._minimap.show()
        self._minimap.setParent(self.view)
        self._minimap.raise_()

        self._mini_timer.start()

    def _update_minimap(self):
        if hasattr(self, '_minimap') and hasattr(self, 'view'):
            self._minimap.sync_viewport(self.view)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_minimap'):
            self._minimap.move(self.width() - 190, 10)

    def _update_toolbar_state(self):
        pass

    def _center_view_on_scene_point(self, scene_pos: QPointF):
        self.view.centerOn(scene_pos)
        self._update_minimap()

    # ── Socket drag signals ───────────────────────────────────────────

    def _connect_socket_signals(self):
        self.scene.node_item_added.connect(self._on_node_item_added)

    def _on_node_item_added(self, node_item: NodeItem):
        node_item.node_double_clicked.connect(self.node_double_clicked.emit)
        for socket in node_item.sockets:
            socket.connection_started.connect(self._on_socket_drag_start)
            socket.connection_moved.connect(self._on_socket_drag_move)
            socket.connection_ended.connect(self._on_socket_drag_end)

    def _on_socket_drag_start(self, socket: SocketItem):
        self.scene.start_edge_drag(socket)

    def _on_socket_drag_move(self, socket: SocketItem, scene_pos: QPointF):
        self.scene.update_edge_drag(scene_pos)

    def _on_socket_drag_end(self, socket: SocketItem, scene_pos: QPointF):
        self.scene.end_edge_drag(scene_pos)

    def _on_node_dropped(self, type_name: str, pos: QPointF):
        node = node_registry.create(type_name)
        if node:
            from core.commands import AddNodeCommand
            self.scene.command_stack.execute(AddNodeCommand(self.scene, node, (pos.x(), pos.y())))

    # ── Workflow integration ──────────────────────────────────────────

    def bind_workflow(self, workflow: WorkflowEngine):
        self._unsubscribe_workflow_events()
        self._workflow = workflow
        self._subscribed_workflow = workflow
        self.scene.bind_workflow(workflow)
        self.scene.load_from_workflow(workflow)
        self._subscribe_workflow_events()

    def save_to_workflow(self):
        """Persist current scene positions/links back into the bound workflow."""
        if self._workflow:
            self.scene.save_to_workflow(self._workflow)

    def _on_run(self):
        if self._workflow:
            for item in self.scene.get_all_node_items():
                item.set_state(NodeState.IDLE)
            self._workflow.execute()

    def _on_stop(self):
        if self._workflow:
            self._workflow.stop()
            for item in self.scene.get_all_node_items():
                item.set_state(NodeState.IDLE)

    def _on_run_step(self):
        """Execute the currently selected node."""
        nd = self.scene.get_selected_node_data()
        if nd and isinstance(nd, VisionNodeData) and self._workflow:
            item = self.scene.get_node_item(nd.node_id)
            if item:
                item.set_state(NodeState.RUNNING)
            self._workflow.execute_step(nd.node_id)
            item = self.scene.get_node_item(nd.node_id)
            if item:
                item.update_from_node()
            self.scene.status_message.emit(f"单步执行: {nd.name}")

    def _on_undo(self):
        self.scene.undo()
        self._update_toolbar_state()

    def _on_redo(self):
        self.scene.redo()
        self._update_toolbar_state()

    # ── Public API ────────────────────────────────────────────────────

    def add_node(self, node_data: NodeBase, pos: QPointF = None, group_name: str = ""):
        from core.commands import AddNodeCommand
        if pos and group_name:
            item = self.scene.add_node_item(node_data, pos, group_name)
            return item
        self.scene.command_stack.execute(AddNodeCommand(self.scene, node_data, pos, group_name))
        return self.scene.get_node_item(node_data.node_id)

    def clear(self):
        self.scene.clear_all()

    def _subscribe_workflow_events(self):
        event_system.subscribe(EventType.NODE_STARTED, self._on_node_started)
        event_system.subscribe(EventType.NODE_COMPLETED, self._on_node_completed)
        event_system.subscribe(EventType.NODE_ERROR, self._on_node_error)
        event_system.subscribe(EventType.WORKFLOW_STOPPED, self._on_workflow_stopped)

    def _unsubscribe_workflow_events(self):
        event_system.unsubscribe(EventType.NODE_STARTED, self._on_node_started)
        event_system.unsubscribe(EventType.NODE_COMPLETED, self._on_node_completed)
        event_system.unsubscribe(EventType.NODE_ERROR, self._on_node_error)
        event_system.unsubscribe(EventType.WORKFLOW_STOPPED, self._on_workflow_stopped)

    def _belongs_to_bound_workflow(self, sender) -> bool:
        return bool(sender) and getattr(sender, 'diagram_data', None) is self._subscribed_workflow

    def _on_node_started(self, sender, **kwargs):
        if self._belongs_to_bound_workflow(sender):
            self.scene.on_workflow_state_changed(sender.node_id, "running")

    def _on_node_completed(self, sender, **kwargs):
        if self._belongs_to_bound_workflow(sender):
            self.scene.on_workflow_state_changed(sender.node_id, "completed")
            import time
            self.node_executed.emit(sender, "Success", time.strftime("%H:%M:%S"))

    def _on_node_error(self, sender, **kwargs):
        if self._belongs_to_bound_workflow(sender):
            self.scene.on_workflow_state_changed(sender.node_id, "error")
            import time
            self.node_executed.emit(sender, "Error", time.strftime("%H:%M:%S"))

    def _on_workflow_stopped(self, sender, **kwargs):
        if sender is self._subscribed_workflow:
            for item in self.scene.get_all_node_items():
                item.set_state(NodeState.IDLE)

