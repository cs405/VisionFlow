"""Editor widget - QGraphicsView wrapping the DiagramScene.

Ported from H.Controls.Diagram.Presenter (DiagramPresenter, EditorWidget).
Provides: zoom/pan, tool buttons, context menu, drop support, mini-map.
"""

from PyQt5.QtWidgets import (QGraphicsView, QWidget, QVBoxLayout, QHBoxLayout,
                              QToolBar, QPushButton, QAction, QMenu,
                              QRubberBand)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import (QPainter, QWheelEvent, QMouseEvent, QKeyEvent,
                          QColor, QPen, QBrush, QDragEnterEvent, QDropEvent)

from core.node_base import NodeBase
from core.workflow import WorkflowEngine
from core.events import EventType, event_system
from core.registry import node_registry

from gui.node_editor.scene import DiagramScene
from gui.node_editor.node_item import NodeItem
from gui.node_editor.edge_item import EdgeItem
from gui.node_editor.socket_item import SocketItem


class DiagramEditorView(QGraphicsView):
    """QGraphicsView with zoom/pan/fit and drag-drop support.

    Handles:
      - Ctrl+scroll zoom
      - Middle-button pan
      - Right-click context menu
      - Drag-drop from toolbox
      - Keyboard shortcuts (Delete, Ctrl+A)
    """

    MIN_ZOOM = 0.05
    MAX_ZOOM = 5.0
    ZOOM_FACTOR = 1.15

    # Signals
    node_dropped = pyqtSignal(str, QPointF)  # type_name, position
    zoom_changed = pyqtSignal(float)

    def __init__(self, scene: DiagramScene, parent=None):
        super().__init__(scene, parent)
        self._diagram_scene = scene
        self._zoom = 1.0
        self._pan_start: QPointF | None = None
        self._space_pressed = False

        # View settings
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setFrameShape(QGraphicsView.NoFrame)

        # Rubber band selection
        self.setDragMode(QGraphicsView.RubberBandDrag)

        # Accept drops from toolbox
        self.setAcceptDrops(True)

        # Cursor
        self.setCursor(Qt.ArrowCursor)

        # Connect scene signals
        scene.status_message.connect(self._on_status)

    def _on_status(self, msg: str):
        pass  # Forwarded to parent

    # -- Zoom --

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
        factor = self.ZOOM_FACTOR
        self._zoom = min(self._zoom * factor, self.MAX_ZOOM)
        self.scale(factor, factor)
        self.zoom_changed.emit(self._zoom)

    def zoom_out(self):
        factor = 1.0 / self.ZOOM_FACTOR
        self._zoom = max(self._zoom * factor, self.MIN_ZOOM)
        self.scale(factor, factor)
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

    # -- Pan (middle mouse) --

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton:
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton and self._pan_start is not None:
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # -- Keyboard --

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            self._diagram_scene.delete_selected()
        elif event.key() == Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            for item in self._diagram_scene.get_all_node_items():
                item.setSelected(True)
        elif event.key() == Qt.Key_F:
            self.fit_to_window()
        elif event.key() == Qt.Key_Space:
            self._space_pressed = True
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Space:
            self._space_pressed = False
        super().keyReleaseEvent(event)

    # -- Context menu --

    def contextMenuEvent(self, event):
        pos = self.mapToScene(event.pos())
        menu = self._diagram_scene.context_menu(pos)
        if menu:
            menu.exec_(event.globalPos())

    # -- Drag-drop from toolbox --

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


class DiagramEditorWidget(QWidget):
    """Full editor widget: QGraphicsView + toolbar + statusbar.

    The main component placed in the center of the main window.
    """

    # Signals
    node_selected = pyqtSignal(object)   # node_data
    node_deselected = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workflow: WorkflowEngine | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)

        btn_style = """
            QPushButton {
                background: #3c3c3c;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px 10px;
                color: #dcdcdc;
                font-size: 11px;
            }
            QPushButton:hover { background: #4a4a4a; }
            QPushButton:pressed { background: #0078d4; }
        """

        run_btn = QPushButton("▶ 运行")
        run_btn.setStyleSheet(btn_style)
        run_btn.clicked.connect(self._on_run)
        toolbar.addWidget(run_btn)

        stop_btn = QPushButton("■ 停止")
        stop_btn.setStyleSheet(btn_style)
        stop_btn.clicked.connect(self._on_stop)
        toolbar.addWidget(stop_btn)

        toolbar.addSpacing(8)

        fit_btn = QPushButton("适应画布")
        fit_btn.setStyleSheet(btn_style)
        fit_btn.clicked.connect(lambda: self.view.fit_to_window())
        toolbar.addWidget(fit_btn)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setStyleSheet(btn_style)
        zoom_in_btn.setFixedWidth(30)
        zoom_in_btn.clicked.connect(lambda: self.view.zoom_in())
        toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setStyleSheet(btn_style)
        zoom_out_btn.setFixedWidth(30)
        zoom_out_btn.clicked.connect(lambda: self.view.zoom_out())
        toolbar.addWidget(zoom_out_btn)

        self.zoom_label = QPushButton("100%")
        self.zoom_label.setStyleSheet(btn_style + "QPushButton { background: transparent; border: none; }")
        self.zoom_label.setFixedWidth(50)
        toolbar.addWidget(self.zoom_label)

        toolbar.addStretch()

        grid_btn = QPushButton("网格")
        grid_btn.setStyleSheet(btn_style)
        grid_btn.setCheckable(True)
        grid_btn.setChecked(True)
        grid_btn.toggled.connect(lambda v: self.scene.toggle_grid())
        toolbar.addWidget(grid_btn)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        toolbar_widget.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3f3f46;")
        layout.addWidget(toolbar_widget)

        # Scene + View
        self.scene = DiagramScene()
        self.view = DiagramEditorView(self.scene)

        # Connect scene signals
        self.scene.node_selected.connect(self.node_selected.emit)
        self.scene.node_deselected.connect(self.node_deselected.emit)

        # Connect view signals
        self.view.zoom_changed.connect(lambda z: self.zoom_label.setText(f"{z*100:.0f}%"))
        self.view.node_dropped.connect(self._on_node_dropped)

        # Connect socket signals for drag-to-connect
        self._connect_socket_signals()

        layout.addWidget(self.view)

    def _connect_socket_signals(self):
        """Wire up socket drag signals for edge creation."""
        # These are connected when nodes are added via scene signals
        self.scene.node_item_added.connect(self._on_node_item_added)

    def _on_node_item_added(self, node_item: NodeItem):
        """Connect a new node's socket signals."""
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
        """Create a node from toolbox drag-drop."""
        node = node_registry.create(type_name)
        if node:
            self.scene.add_node_item(node, pos)
            if self._workflow:
                self._workflow.add_node(node)

    # -- Workflow integration --

    def bind_workflow(self, workflow: WorkflowEngine):
        """Bind to a workflow engine."""
        self._workflow = workflow
        self.scene.bind_workflow(workflow)
        self.scene.load_from_workflow(workflow)

    def _on_run(self):
        """Execute the workflow."""
        if self._workflow:
            self._workflow.execute()

    def _on_stop(self):
        """Stop workflow execution."""
        if self._workflow:
            self._workflow.stop()

    # -- Add node programmatically --

    def add_node(self, node_data: NodeBase, pos: QPointF = None, group_name: str = ""):
        """Add a node to the scene."""
        return self.scene.add_node_item(node_data, pos, group_name)

    def clear(self):
        """Clear the diagram."""
        self.scene.clear_all()
