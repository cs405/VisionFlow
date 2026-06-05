"""Diagram scene — QGraphicsScene managing nodes, edges, clipboard, undo/redo.

Ported from H.Controls.Diagram (DiagramCanvas, DiagramSurface).

Features:
  - Grid background
  - Node/edge CRUD with full WorkflowEngine sync
  - load_from_workflow() with complete edge rebuilding
  - Copy/paste via internal clipboard
  - Box selection with align/distribute operations
  - Undo/redo via CommandStack integration
  - Workflow execution state feedback on node items
  - Socket drag-to-connect
  - Context menu
"""

from PyQt5.QtWidgets import (QGraphicsScene, QGraphicsItem, QMenu, QAction,
                              QGraphicsSceneMouseEvent)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QLineF, QMimeData
from PyQt5.QtGui import (QPainter, QPen, QColor, QBrush, QFont, QPainterPath,
                          QTransform, QPixmap)

from core.node_base import (NodeBase, Port, PortType, PortDock, LinkData,
                             VisionNodeData)
from core.workflow import WorkflowEngine
from core.events import EventType, event_system
from core.registry import node_registry
from core.commands import (CommandStack, AddNodeCommand, RemoveNodeCommand,
                            AddLinkCommand, RemoveLinkCommand, MoveNodeCommand,
                            BatchCommand)

from gui.node_editor.node_item import NodeItem, NodeState
from gui.node_editor.socket_item import SocketItem, PORT_DIAMETER
from gui.node_editor.edge_item import EdgeItem


SCENE_RECT = QRectF(-5000, -5000, 10000, 10000)

# Checkerboard tile — 1:1 port of WPF H.Theme BrushKeys Tile pattern
# Drawing: 100x100 tile with two 50x50 squares → tiled at smaller viewport
CHECKER_TILE = 20       # px, viewport size for tiling
CHECKER_CELL = 10       # px, half of tile (each checker square)
CHECKER_BASE = QColor("#121317")   # WPF Dark0
CHECKER_ALT = QColor("#191a20")    # WPF Dark0_1


def _make_checker_brush(tile=CHECKER_TILE, cell=CHECKER_CELL,
                         base=CHECKER_BASE, alt=CHECKER_ALT):
    """Create a tiled checkerboard QBrush matching WPF DrawingBrush + Tile."""
    pixmap = QPixmap(tile, tile)
    pixmap.fill(base)
    p = QPainter(pixmap)
    p.fillRect(0, 0, cell, cell, alt)
    p.fillRect(cell, cell, cell, cell, alt)
    p.end()
    return QBrush(pixmap)


class DiagramScene(QGraphicsScene):
    """Main diagram scene — full node/edge editor with undo/redo and clipboard."""

    node_item_added = pyqtSignal(NodeItem)
    node_item_removed = pyqtSignal(str)
    edge_item_added = pyqtSignal(EdgeItem)
    edge_item_removed = pyqtSignal(str)
    node_selected = pyqtSignal(object)
    node_deselected = pyqtSignal()
    node_properties_requested = pyqtSignal(object)   # 右键 → 属性
    node_help_requested = pyqtSignal(object)          # 右键 → 帮助
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(SCENE_RECT)
        self.setBackgroundBrush(_make_checker_brush())

        self._workflow: WorkflowEngine | None = None
        self._node_items: dict[str, NodeItem] = {}
        self._edge_items: dict[str, EdgeItem] = {}
        self._show_grid = True

        # Interaction state
        self._drag_edge: EdgeItem | None = None
        self._drag_from_socket: SocketItem | None = None
        self._connecting = False

        # Command stack (undo/redo)
        self._cmd_stack = CommandStack(scene=self)

        # Clipboard for copy/paste
        self._clipboard: list[dict] = []

        self.selectionChanged.connect(self._on_selection_changed)

    # ── Command stack access ──────────────────────────────────────────

    @property
    def command_stack(self) -> CommandStack:
        return self._cmd_stack

    # ── Grid ──────────────────────────────────────────────────────────

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Checkerboard background tiled via background brush (WPF Tile pattern)."""
        super().drawBackground(painter, rect)

    def toggle_grid(self):
        """Toggle between checkerboard and flat background."""
        self._show_grid = not self._show_grid
        if self._show_grid:
            self.setBackgroundBrush(_make_checker_brush())
        else:
            self.setBackgroundBrush(QBrush(CHECKER_BASE))
        self.update()

    # ── Node management ───────────────────────────────────────────────

    def bind_workflow(self, workflow: WorkflowEngine):
        self._workflow = workflow

    def add_node_item(self, node_data: NodeBase, pos: QPointF = None,
                      group_name: str = "", sync_workflow: bool = True) -> NodeItem:
        item = NodeItem(node_data, group_name)
        if pos is not None:
            item.setPos(pos)
        else:
            count = len(self._node_items)
            x = (count % 5) * 170 - 340
            y = (count // 5) * 70 - 200
            item.setPos(x, y)

        self.addItem(item)
        self._node_items[node_data.node_id] = item
        item.node_selected.connect(self._on_node_item_selected)
        item.node_moved.connect(self._on_node_item_moved)

        if sync_workflow and self._workflow:
            self._workflow.add_node(node_data)

        event_system.publish(EventType.NODE_ADDED, sender=self, node=node_data)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.node_item_added.emit(item)
        return item

    def remove_node_item(self, node_id: str, sync_workflow: bool = True):
        item = self._node_items.pop(node_id, None)
        if item is None:
            return
        # Remove connected edges
        for eid in list(self._edge_items.keys()):
            edge = self._edge_items[eid]
            if (edge.from_socket and edge.from_socket.port.node_id == node_id) or \
               (edge.to_socket and edge.to_socket.port.node_id == node_id):
                self.remove_edge_item(eid, sync_workflow=sync_workflow)
        self.removeItem(item)
        if sync_workflow and self._workflow:
            self._workflow.remove_node(node_id)
        event_system.publish(EventType.NODE_REMOVED, sender=self, node=item.node_data)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.node_item_removed.emit(node_id)

    def get_node_item(self, node_id: str) -> NodeItem | None:
        return self._node_items.get(node_id)

    def get_all_node_items(self) -> list[NodeItem]:
        return list(self._node_items.values())

    # ── Edge management ───────────────────────────────────────────────

    def create_edge(self, from_socket: SocketItem, to_socket: SocketItem,
                    sync_workflow: bool = True,
                    existing_link: LinkData | None = None) -> EdgeItem | None:
        if from_socket.port.is_input and to_socket.port.is_output:
            from_socket, to_socket = to_socket, from_socket
        if not from_socket.port.is_output or not to_socket.port.is_input:
            return None
        if from_socket.port.node_id == to_socket.port.node_id:
            return None
        for edge in self._edge_items.values():
            if (edge.from_socket is from_socket and edge.to_socket is to_socket) or (
                edge.link_data and
                edge.link_data.from_port_id == from_socket.port.port_id and
                edge.link_data.to_port_id == to_socket.port.port_id
            ):
                return None

        if sync_workflow and self._workflow:
            link = self._workflow.add_link(
                from_socket.port.node_id,
                to_socket.port.node_id,
                from_port_id=from_socket.port.port_id,
                to_port_id=to_socket.port.port_id,
                link_id=existing_link.link_id if existing_link else None,
                text=existing_link.text if existing_link else "",
            )
            if link is None:
                return None
        else:
            link = existing_link or LinkData(
                from_node_id=from_socket.port.node_id,
                from_port_id=from_socket.port.port_id,
                to_node_id=to_socket.port.node_id,
                to_port_id=to_socket.port.port_id,
            )

        edge = EdgeItem(from_socket, to_socket, link)
        self.addItem(edge)
        self._edge_items[link.link_id] = edge
        edge.edge_selected.connect(self._on_edge_selected)

        event_system.publish(EventType.LINK_ADDED, sender=self, link=link)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.edge_item_added.emit(edge)
        return edge

    def remove_edge_item(self, link_id: str, sync_workflow: bool = True):
        edge = self._edge_items.pop(link_id, None)
        if edge is None:
            return
        edge.disconnect()
        self.removeItem(edge)
        if sync_workflow and self._workflow:
            self._workflow.remove_link(link_id)
        event_system.publish(EventType.LINK_REMOVED, sender=self, link=link_id)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.edge_item_removed.emit(link_id)

    def get_edge_item(self, link_id: str) -> EdgeItem | None:
        return self._edge_items.get(link_id)

    def get_all_edge_items(self) -> list[EdgeItem]:
        return list(self._edge_items.values())

    # ── Drag-to-connect ───────────────────────────────────────────────

    def start_edge_drag(self, from_socket: SocketItem):
        self._drag_from_socket = from_socket
        self._drag_edge = EdgeItem(from_socket, None)
        self._drag_edge.setZValue(100)
        self.addItem(self._drag_edge)
        self._connecting = True

    def update_edge_drag(self, scene_pos: QPointF):
        if self._drag_edge:
            self._drag_edge.set_temp_end(scene_pos)

    def end_edge_drag(self, scene_pos: QPointF):
        if not self._drag_edge or not self._drag_from_socket:
            self._cleanup_drag()
            return
        target = self._find_socket_at(scene_pos, exclude=self._drag_from_socket)
        if target and target is not self._drag_from_socket:
            cmd = AddLinkCommand(self, self._drag_from_socket, target)
            self._cmd_stack.execute(cmd)
            self.status_message.emit("连线已创建")
        else:
            self.status_message.emit("连线已取消")
        self._cleanup_drag()

    def _cleanup_drag(self):
        if self._drag_edge:
            self.removeItem(self._drag_edge)
            self._drag_edge = None
        self._drag_from_socket = None
        self._connecting = False

    def _find_socket_at(self, scene_pos: QPointF, exclude: SocketItem = None) -> SocketItem | None:
        for node_item in self._node_items.values():
            socket = node_item.get_socket_at(scene_pos)
            if socket and socket is not exclude:
                return socket
        return None

    # ── Selection ─────────────────────────────────────────────────────

    def _on_node_item_selected(self, node_data: NodeBase):
        self.node_selected.emit(node_data)
        event_system.publish(EventType.NODE_SELECTED, sender=node_data, node=node_data)

    def _on_node_item_moved(self, node_data: NodeBase):
        event_system.publish(EventType.NODE_PROPERTY_CHANGED, sender=node_data)

    def _on_edge_selected(self, edge: EdgeItem):
        pass

    def _on_selection_changed(self):
        if not self.selectedItems():
            self.node_deselected.emit()
            event_system.publish(EventType.NODE_DESELECTED, sender=self)

    def get_selected_node_data(self) -> NodeBase | None:
        for item in self.selectedItems():
            if isinstance(item, NodeItem):
                return item.node_data
        return None

    def get_selected_node_items(self) -> list[NodeItem]:
        return [it for it in self.selectedItems() if isinstance(it, NodeItem)]

    def delete_selected(self):
        """Delete selected items with undo support."""
        items = self.selectedItems()
        if not items:
            return
        batch = BatchCommand(description="删除选中项")
        for item in items:
            if isinstance(item, NodeItem):
                batch.add(RemoveNodeCommand(self, item.node_data.node_id))
            elif isinstance(item, EdgeItem):
                batch.add(RemoveLinkCommand(self, item.link_data.link_id))
        self._cmd_stack.execute(batch)

    # ── Copy / Paste ──────────────────────────────────────────────────

    def copy_selected(self):
        """Copy selected nodes to internal clipboard."""
        self._clipboard.clear()
        for item in self.selectedItems():
            if isinstance(item, NodeItem):
                nd = item.node_data
                pos = item.pos()
                ports_data = [p.to_dict() for p in nd.ports]
                self._clipboard.append({
                    "type": nd.__class__.__name__,
                    "data": nd.to_dict() if hasattr(nd, 'to_dict') else {},
                    "x": pos.x(),
                    "y": pos.y(),
                    "ports": ports_data,
                })
        self.status_message.emit(f"已复制 {len(self._clipboard)} 个节点")

    def paste(self):
        """Paste nodes from clipboard at offset position."""
        if not self._clipboard:
            return
        batch = BatchCommand(description="粘贴节点")
        offset = 30 + 15 * len(self._clipboard)  # progressive offset
        for clip in self._clipboard:
            node = node_registry.create(clip["type"])
            if node:
                if "data" in clip and clip["data"]:
                    node.from_dict(clip["data"]) if hasattr(node, 'from_dict') else None
                pos = QPointF(clip.get("x", 0) + offset, clip.get("y", 0) + offset)
                batch.add(AddNodeCommand(self, node, (pos.x(), pos.y()) if hasattr(pos, 'x') else pos))
        self._cmd_stack.execute(batch)
        self.status_message.emit(f"已粘贴 {len(self._clipboard)} 个节点")
        self._clipboard.clear()

    # ── Alignment ─────────────────────────────────────────────────────

    def align_selected(self, mode: str):
        """Align selected nodes horizontally or vertically."""
        nodes = self.get_selected_node_items()
        if len(nodes) < 2:
            return
        batch = BatchCommand(description=f"对齐 ({mode})")

        if mode == "left":
            x_min = min(n.pos().x() - n._node_w / 2 for n in nodes)
            for n in nodes:
                old = n.pos()
                new = QPointF(x_min + n._node_w / 2, old.y())
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        elif mode == "right":
            x_max = max(n.pos().x() + n._node_w / 2 for n in nodes)
            for n in nodes:
                old = n.pos()
                new = QPointF(x_max - n._node_w / 2, old.y())
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        elif mode == "top":
            y_min = min(n.pos().y() - n._node_h / 2 for n in nodes)
            for n in nodes:
                old = n.pos()
                new = QPointF(old.x(), y_min + n._node_h / 2)
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        elif mode == "bottom":
            y_max = max(n.pos().y() + n._node_h / 2 for n in nodes)
            for n in nodes:
                old = n.pos()
                new = QPointF(old.x(), y_max - n._node_h / 2)
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        elif mode == "center_h":
            avg_y = sum(n.pos().y() for n in nodes) / len(nodes)
            for n in nodes:
                old = n.pos()
                new = QPointF(old.x(), avg_y)
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        elif mode == "center_v":
            avg_x = sum(n.pos().x() for n in nodes) / len(nodes)
            for n in nodes:
                old = n.pos()
                new = QPointF(avg_x, old.y())
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))

        self._cmd_stack.execute(batch)

    def distribute_selected(self, mode: str):
        """Evenly distribute selected nodes."""
        nodes = self.get_selected_node_items()
        if len(nodes) < 3:
            return
        batch = BatchCommand(description=f"分布 ({mode})")

        if mode == "horizontal":
            nodes.sort(key=lambda n: n.pos().x())
            x_min = nodes[0].pos().x()
            x_max = nodes[-1].pos().x()
            spacing = (x_max - x_min) / (len(nodes) - 1) if len(nodes) > 1 else 0
            for i, n in enumerate(nodes):
                old = n.pos()
                new = QPointF(x_min + i * spacing, old.y())
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))
        elif mode == "vertical":
            nodes.sort(key=lambda n: n.pos().y())
            y_min = nodes[0].pos().y()
            y_max = nodes[-1].pos().y()
            spacing = (y_max - y_min) / (len(nodes) - 1) if len(nodes) > 1 else 0
            for i, n in enumerate(nodes):
                old = n.pos()
                new = QPointF(old.x(), y_min + i * spacing)
                batch.add(MoveNodeCommand(self, n.node_data.node_id, (old.x(), old.y()), (new.x(), new.y())))

        self._cmd_stack.execute(batch)

    # ── Undo / Redo ───────────────────────────────────────────────────

    def undo(self):
        if self._cmd_stack.undo():
            self.status_message.emit(f"撤销: {self._cmd_stack.undo_description}")

    def redo(self):
        if self._cmd_stack.redo():
            self.status_message.emit(f"重做: {self._cmd_stack.redo_description}")

    # ── Workflow state feedback ───────────────────────────────────────

    def on_workflow_state_changed(self, node_id: str, state: str):
        """Update node visual state based on workflow execution."""
        item = self._node_items.get(node_id)
        if item is None:
            return
        state_map = {
            "running": NodeState.RUNNING,
            "completed": NodeState.COMPLETED,
            "error": NodeState.ERROR,
            "idle": NodeState.IDLE,
        }
        item.set_state(state_map.get(state, NodeState.IDLE))

    # ── Context menu ──────────────────────────────────────────────────

    def context_menu(self, pos: QPointF) -> QMenu | None:
        item = self.itemAt(pos, QTransform())
        menu = QMenu()

        if isinstance(item, NodeItem):
            # ── 运行 ──
            run_act = QAction("▶  运行此节点", menu)
            run_act.triggered.connect(lambda: self._run_single_node(item.node_data))
            menu.addAction(run_act)

            menu.addSeparator()

            # ── 编辑 ──
            prop_act = QAction("⚙  属性...", menu)
            prop_act.triggered.connect(lambda: self.node_properties_requested.emit(item.node_data))
            menu.addAction(prop_act)

            copy_act = QAction("📋  复制", menu)
            copy_act.triggered.connect(self.copy_selected)
            menu.addAction(copy_act)

            menu.addSeparator()

            # ── 删除 / 禁用 ──
            delete_act = QAction("🗑  删除节点", menu)
            delete_act.triggered.connect(
                lambda: self._cmd_stack.execute(RemoveNodeCommand(self, item.node_data.node_id)))
            menu.addAction(delete_act)

            disable_act = QAction("⊘  禁用节点", menu)
            disable_act.setCheckable(True)
            disable_act.setChecked(item._state == NodeState.DISABLED)
            disable_act.triggered.connect(
                lambda checked: item.set_state(NodeState.DISABLED if checked else NodeState.IDLE))
            menu.addAction(disable_act)

            menu.addSeparator()

            # ── 帮助 ──
            help_act = QAction("?  帮助", menu)
            help_act.triggered.connect(lambda: self.node_help_requested.emit(item.node_data))
            menu.addAction(help_act)
        elif isinstance(item, EdgeItem):
            delete_act = QAction("删除连线", menu)
            delete_act.triggered.connect(
                lambda: self._cmd_stack.execute(RemoveLinkCommand(self, item.link_data.link_id)))
            menu.addAction(delete_act)

            menu.addSeparator()
            label_act = QAction("添加标签", menu)
            label_act.triggered.connect(lambda: item.set_label(
                getattr(item.from_socket.port, 'data_type', 'image')))
            menu.addAction(label_act)
        else:
            add_menu = menu.addMenu("添加节点")
            for node_type in node_registry.get_all_instantiable():
                action = QAction(node_type.__name__, menu)
                action.triggered.connect(lambda c, nt=node_type:
                    self._cmd_stack.execute(AddNodeCommand(self, nt(), pos)))
                add_menu.addAction(action)

            menu.addSeparator()

            paste_act = QAction("粘贴", menu)
            paste_act.setEnabled(bool(self._clipboard))
            paste_act.triggered.connect(self.paste)
            menu.addAction(paste_act)

        return menu

    def _run_single_node(self, node_data: NodeBase):
        if self._workflow and isinstance(node_data, VisionNodeData):
            node_data.update_invoke_current()
            item = self._node_items.get(node_data.node_id)
            if item:
                item.update_from_node()
            self.status_message.emit(f"已执行: {node_data.name}")

    # ── Serialization ─────────────────────────────────────────────────

    def clear_all(self, sync_workflow: bool = True):
        for node_id in list(self._node_items.keys()):
            self.remove_node_item(node_id, sync_workflow=sync_workflow)
        self._node_items.clear()
        self._edge_items.clear()
        self._cmd_stack.clear()

    def load_from_workflow(self, workflow: WorkflowEngine):
        """Populate scene from workflow, fully rebuilding nodes and edges."""
        self.clear_all(sync_workflow=False)
        self._workflow = workflow

        # Create nodes at saved positions
        for node in workflow.get_all_nodes():
            # Use stored position or auto-place
            x = getattr(node, '_pos_x', 0.0) or 0.0
            y = getattr(node, '_pos_y', 0.0) or 0.0
            pos = QPointF(x, y) if (x or y) else None
            item = self.add_node_item(node, pos, sync_workflow=False)
            if item:
                # Store position for later
                node._pos_x = item.pos().x()
                node._pos_y = item.pos().y()

        # Rebuild edges from link data
        for link in workflow.get_all_links():
            from_item = self.get_node_item(link.from_node_id)
            to_item = self.get_node_item(link.to_node_id)
            if from_item and to_item:
                fs = from_item.get_socket_by_port_id(link.from_port_id)
                ts = to_item.get_socket_by_port_id(link.to_port_id)
                if fs and ts:
                    self.create_edge(fs, ts, sync_workflow=False, existing_link=link)

    def save_to_workflow(self, workflow: WorkflowEngine):
        """Save scene state back to workflow (node positions, links)."""
        for node_id, item in self._node_items.items():
            pos = item.pos()
            nd = item.node_data
            nd._pos_x = pos.x()
            nd._pos_y = pos.y()
        workflow._links = []
        for edge in self._edge_items.values():
            if edge.link_data:
                workflow._links.append(edge.link_data)
