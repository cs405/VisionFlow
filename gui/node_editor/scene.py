"""Diagram scene - QGraphicsScene managing nodes, edges, and canvas interactions.

Ported from H.Controls.Diagram (DiagramCanvas, DiagramSurface).
Handles: grid background, node management, edge creation via drag, selection.
"""

from PyQt5.QtWidgets import (QGraphicsScene, QGraphicsItem, QMenu, QAction,
                              QGraphicsSceneMouseEvent)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QLineF
from PyQt5.QtGui import (QPainter, QPen, QColor, QBrush, QFont, QPainterPath,
                          QTransform)

from core.node_base import NodeBase, Port, PortType, PortDock, LinkData, VisionNodeData
from core.workflow import WorkflowEngine
from core.events import EventType, event_system
from core.registry import node_registry

from gui.node_editor.node_item import NodeItem
from gui.node_editor.socket_item import SocketItem, PORT_DIAMETER
from gui.node_editor.edge_item import EdgeItem


# Grid settings
GRID_SIZE_MAJOR = 20
GRID_SIZE_MINOR = 20
SCENE_RECT = QRectF(-5000, -5000, 10000, 10000)

# Colors
GRID_MAJOR_COLOR = QColor(50, 50, 50)
GRID_MINOR_COLOR = QColor(38, 38, 38)
BACKGROUND_COLOR = QColor(30, 30, 30)


class DiagramScene(QGraphicsScene):
    """Main diagram scene managing nodes, edges, and interactions.

    Responsibilities:
      - Draw background grid
      - Manage NodeItem and EdgeItem instances
      - Handle socket drag-to-connect
      - Sync with WorkflowEngine (node/link data model)
      - Context menu
      - Selection and clipboard
    """

    # Signals
    node_item_added = pyqtSignal(NodeItem)
    node_item_removed = pyqtSignal(str)         # node_id
    edge_item_added = pyqtSignal(EdgeItem)
    edge_item_removed = pyqtSignal(str)          # link_id
    node_selected = pyqtSignal(object)           # node_data
    node_deselected = pyqtSignal()
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(SCENE_RECT)
        self.setBackgroundBrush(QBrush(BACKGROUND_COLOR))

        # Data
        self._workflow: WorkflowEngine | None = None
        self._node_items: dict[str, NodeItem] = {}   # node_id -> NodeItem
        self._edge_items: dict[str, EdgeItem] = {}    # link_id -> EdgeItem

        # Interaction state
        self._drag_edge: EdgeItem | None = None       # Edge being created
        self._drag_from_socket: SocketItem | None = None
        self._connecting = False

        # Grid visibility
        self._show_grid = True

        # Selection
        self.selectionChanged.connect(self._on_selection_changed)

    # -- Grid drawing --

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draw the grid background."""
        super().drawBackground(painter, rect)

        if not self._show_grid:
            return

        painter.setRenderHint(QPainter.Antialiasing, False)

        left = int(rect.left()) - int(rect.left()) % GRID_SIZE_MAJOR
        top = int(rect.top()) - int(rect.top()) % GRID_SIZE_MAJOR
        right = int(rect.right())
        bottom = int(rect.bottom())

        # Minor grid (every 20px)
        pen = QPen(GRID_MINOR_COLOR, 0.5)
        painter.setPen(pen)
        lines = []
        for x in range(left, right, GRID_SIZE_MINOR):
            lines.append(QLineF(x, top, x, bottom))
        for y in range(top, bottom, GRID_SIZE_MINOR):
            lines.append(QLineF(left, y, right, y))
        painter.drawLines(lines)

        # Major grid (every 100px)
        pen = QPen(GRID_MAJOR_COLOR, 1.0)
        painter.setPen(pen)
        lines = []
        major = GRID_SIZE_MAJOR * 5
        for x in range(left, right, major):
            lines.append(QLineF(x, top, x, bottom))
        for y in range(top, bottom, major):
            lines.append(QLineF(left, y, right, y))
        painter.drawLines(lines)

    def toggle_grid(self):
        """Toggle grid visibility."""
        self._show_grid = not self._show_grid
        self.update()

    # -- Node management --

    def bind_workflow(self, workflow: WorkflowEngine):
        """Bind this scene to a workflow engine for sync."""
        self._workflow = workflow

    def add_node_item(self, node_data: NodeBase, pos: QPointF = None,
                      group_name: str = "") -> NodeItem:
        """Create and add a NodeItem for the given node_data."""
        item = NodeItem(node_data, group_name)
        if pos:
            item.setPos(pos)
        else:
            # Place at a semi-random position to avoid stacking
            count = len(self._node_items)
            x = (count % 5) * 160 - 320
            y = (count // 5) * 60 - 200
            item.setPos(x, y)

        self.addItem(item)
        self._node_items[node_data.node_id] = item

        # Connect signals
        item.node_selected.connect(self._on_node_item_selected)
        item.node_moved.connect(self._on_node_item_moved)

        # Also add to workflow if bound
        if self._workflow:
            self._workflow.add_node(node_data)

        event_system.publish(EventType.NODE_ADDED, sender=self, node=node_data)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.node_item_added.emit(item)

        return item

    def remove_node_item(self, node_id: str):
        """Remove a node item and its connected edges."""
        item = self._node_items.pop(node_id, None)
        if item is None:
            return

        # Remove connected edges
        edges_to_remove = []
        for edge_id, edge in list(self._edge_items.items()):
            if edge.from_socket in item.sockets or (edge.to_socket and edge.to_socket in item.sockets):
                edges_to_remove.append(edge_id)

        for edge_id in edges_to_remove:
            self.remove_edge_item(edge_id)

        self.removeItem(item)
        if self._workflow:
            self._workflow.remove_node(node_id)

        event_system.publish(EventType.NODE_REMOVED, sender=self, node=item.node_data)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.node_item_removed.emit(node_id)

    def get_node_item(self, node_id: str) -> NodeItem | None:
        return self._node_items.get(node_id)

    def get_all_node_items(self) -> list[NodeItem]:
        return list(self._node_items.values())

    # -- Edge management --

    def create_edge(self, from_socket: SocketItem, to_socket: SocketItem) -> EdgeItem | None:
        """Create an edge between two sockets. Returns the EdgeItem or None if invalid."""
        # Validate: from must be output, to must be input
        if not from_socket.port.is_output:
            return None
        if not to_socket.port.is_input:
            return None
        # Can't connect to self
        if from_socket.port.node_id == to_socket.port.node_id:
            return None
        # Can't duplicate connection
        for edge in self._edge_items.values():
            if (edge.from_socket is from_socket and edge.to_socket is to_socket):
                return None

        from_node_id = from_socket.port.node_id
        to_node_id = to_socket.port.node_id

        # Create link data
        link = LinkData(
            from_node_id=from_node_id,
            from_port_id=from_socket.port.port_id,
            to_node_id=to_node_id,
            to_port_id=to_socket.port.port_id,
        )

        edge = EdgeItem(from_socket, to_socket, link)
        self.addItem(edge)
        self._edge_items[link.link_id] = edge

        edge.edge_selected.connect(self._on_edge_selected)

        # Sync with workflow
        if self._workflow:
            self._workflow.add_link(from_node_id, to_node_id)

        event_system.publish(EventType.LINK_ADDED, sender=self, link=link)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.edge_item_added.emit(edge)

        return edge

    def remove_edge_item(self, link_id: str):
        """Remove an edge item."""
        edge = self._edge_items.pop(link_id, None)
        if edge is None:
            return

        edge.disconnect()
        self.removeItem(edge)

        if self._workflow:
            self._workflow.remove_link(link_id)

        event_system.publish(EventType.LINK_REMOVED, sender=self, link=link_id)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.edge_item_removed.emit(link_id)

    def get_edge_item(self, link_id: str) -> EdgeItem | None:
        return self._edge_items.get(link_id)

    def get_all_edge_items(self) -> list[EdgeItem]:
        return list(self._edge_items.values())

    # -- Drag-to-connect handling (called by editor_widget) --

    def start_edge_drag(self, from_socket: SocketItem):
        """Begin creating an edge by dragging from a socket."""
        self._drag_from_socket = from_socket
        self._drag_edge = EdgeItem(from_socket, None)
        self._drag_edge.setZValue(100)
        self.addItem(self._drag_edge)
        self._connecting = True

    def update_edge_drag(self, scene_pos: QPointF):
        """Update the temporary edge endpoint during drag."""
        if self._drag_edge:
            self._drag_edge.set_temp_end(scene_pos)

    def end_edge_drag(self, scene_pos: QPointF):
        """Finish edge drag: connect to socket under cursor or cancel."""
        if not self._drag_edge or not self._drag_from_socket:
            self._cleanup_drag()
            return

        # Find socket at drop position
        target_socket = self._find_socket_at(scene_pos, exclude=self._drag_from_socket)

        if target_socket and target_socket is not self._drag_from_socket:
            self.create_edge(self._drag_from_socket, target_socket)
            self.status_message.emit("连线已创建")
        else:
            self.status_message.emit("连线已取消")

        self._cleanup_drag()

    def _cleanup_drag(self):
        """Clean up the drag-creation temporary state."""
        if self._drag_edge:
            self.removeItem(self._drag_edge)
            self._drag_edge = None
        self._drag_from_socket = None
        self._connecting = False

    def _find_socket_at(self, scene_pos: QPointF, exclude: SocketItem = None) -> SocketItem | None:
        """Find a socket at the given scene position."""
        for node_item in self._node_items.values():
            socket = node_item.get_socket_at(scene_pos)
            if socket and socket is not exclude:
                return socket
        return None

    # -- Selection --

    def _on_node_item_selected(self, node_data: NodeBase):
        """Handle node selection."""
        self.node_selected.emit(node_data)
        event_system.publish(EventType.NODE_SELECTED, sender=node_data, node=node_data)

    def _on_node_item_moved(self, node_data: NodeBase):
        """Handle node movement."""
        event_system.publish(EventType.NODE_PROPERTY_CHANGED, sender=node_data)

    def _on_edge_selected(self, edge: EdgeItem):
        """Handle edge selection."""
        pass

    def _on_selection_changed(self):
        """Handle selection changes."""
        selected = self.selectedItems()
        if not selected:
            self.node_deselected.emit()
            event_system.publish(EventType.NODE_DESELECTED, sender=self)

    def get_selected_node_data(self) -> NodeBase | None:
        """Get the node_data of the first selected NodeItem."""
        for item in self.selectedItems():
            if isinstance(item, NodeItem):
                return item.node_data
        return None

    def delete_selected(self):
        """Delete all selected node and edge items."""
        items = self.selectedItems()
        for item in items:
            if isinstance(item, NodeItem):
                self.remove_node_item(item.node_data.node_id)
            elif isinstance(item, EdgeItem):
                self.remove_edge_item(item.link_data.link_id)

    # -- Context menu --

    def context_menu(self, pos: QPointF) -> QMenu | None:
        """Create a context menu for the given scene position."""
        item = self.itemAt(pos, QTransform())
        menu = QMenu()

        if isinstance(item, NodeItem):
            # Node context menu
            delete_action = QAction("删除节点", menu)
            delete_action.triggered.connect(
                lambda: self.remove_node_item(item.node_data.node_id))
            menu.addAction(delete_action)

            run_action = QAction("单步执行", menu)
            run_action.triggered.connect(
                lambda: self._run_single_node(item.node_data))
            menu.addAction(run_action)

            menu.addSeparator()

            copy_action = QAction("复制", menu)
            menu.addAction(copy_action)
        elif isinstance(item, EdgeItem):
            # Edge context menu
            delete_action = QAction("删除连线", menu)
            delete_action.triggered.connect(
                lambda: self.remove_edge_item(item.link_data.link_id))
            menu.addAction(delete_action)
        else:
            # Canvas context menu
            add_menu = menu.addMenu("添加节点")
            for node_type in node_registry.get_all_instantiable():
                action = QAction(node_type.__name__, menu)
                action.triggered.connect(
                    lambda checked, nt=node_type: self.add_node_item(nt(), pos))
                add_menu.addAction(action)

        return menu

    def _run_single_node(self, node_data: NodeBase):
        """Execute a single node."""
        if self._workflow and isinstance(node_data, VisionNodeData):
            node_data.update_invoke_current()
            self.status_message.emit(f"已执行: {node_data.name}")

    # -- Serialization --

    def clear_all(self):
        """Remove all nodes and edges."""
        for node_id in list(self._node_items.keys()):
            self.remove_node_item(node_id)
        self._node_items.clear()
        self._edge_items.clear()

    def load_from_workflow(self, workflow: WorkflowEngine):
        """Populate the scene from a workflow engine."""
        self.clear_all()
        self._workflow = workflow

        # Create nodes
        pos = QPointF(0, 0)
        for node in workflow.get_all_nodes():
            item = self.add_node_item(node, pos)
            pos += QPointF(160, 0)
            if pos.x() > 600:
                pos = QPointF(0, pos.y() + 80)
