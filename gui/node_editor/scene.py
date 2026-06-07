"""Diagram scene
"""

from PyQt5.QtWidgets import (QGraphicsScene, QGraphicsItem, QMenu, QAction,
                              QGraphicsSceneMouseEvent)
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QLineF, QMimeData, QTimer, QEvent
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
from gui.node_editor.edge_item import EdgeItem, EdgeState
from gui.node_editor.link_drawer import ILinkDrawer, BrokenLinkDrawer
from core.node_group import node_data_group_manager


SCENE_RECT = QRectF(-5000, -5000, 10000, 10000)

# Checkerboard tile
CHECKER_TILE = 40
CHECKER_CELL = 20
from gui.theme import theme_manager


def _make_checker_brush(tile=CHECKER_TILE, cell=CHECKER_CELL,
                         base=None, alt=None):
    if base is None:
        base = theme_manager.color("canvas_checker_base")
    if alt is None:
        alt = theme_manager.color("canvas_checker_alt")
    pixmap = QPixmap(tile, tile)
    pixmap.fill(base)
    p = QPainter(pixmap)
    p.fillRect(0, 0, cell, cell, alt)
    p.fillRect(cell, cell, cell, cell, alt)
    p.end()
    return QBrush(pixmap)


# ── Layer Z-values ──

class LayerZ:
    """Z-value constants
    """
    LINK = 5          # LinkLayer — edges render below nodes
    NODE = 10         # NodeLayer — nodes render above edges
    DYNAMIC = 100     # DynamicLayer — drag preview renders above everything


class DiagramScene(QGraphicsScene):
    """Main diagram scene"""

    node_item_added = pyqtSignal(NodeItem)
    node_item_removed = pyqtSignal(str)
    edge_item_added = pyqtSignal(EdgeItem)
    edge_item_removed = pyqtSignal(str)
    node_selected = pyqtSignal(object)
    node_deselected = pyqtSignal()
    node_properties_requested = pyqtSignal(object)
    node_help_requested = pyqtSignal(object)
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(SCENE_RECT)
        self.setBackgroundBrush(_make_checker_brush())

        self._workflow: WorkflowEngine | None = None
        self._node_items: dict[str, NodeItem] = {}
        self._edge_items: dict[str, EdgeItem] = {}
        self._show_grid = True
        self._link_drawer: ILinkDrawer = BrokenLinkDrawer()  # 折线

        # ── single reusable preview edge ──
        self._dynamic_edge: EdgeItem | None = None

        # ── Diagram-level drag state (replaces SocketItem-level handling) ──
        self._connecting = False
        self._drag_from_socket: SocketItem | None = None
        self._drag_to_pos: QPointF = QPointF()

        # ── Pending commit ──
        self._pending_from: SocketItem | None = None
        self._pending_to: SocketItem | None = None
        self._commit_timer = QTimer()
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(0)
        self._commit_timer.timeout.connect(self._do_pending_commit)

        # ── Command stack ──
        self._cmd_stack = CommandStack(scene=self)

        # ── Clipboard ──
        self._clipboard: list[dict] = []

        # ── Sequential index counter ──
        self._node_counter: int = 0

        self.selectionChanged.connect(self._on_selection_changed)

    # ═══════════════════════════════════════════════════════════════════════════
    #  Diagram-Level Event Handling (event() override)
    # ═══════════════════════════════════════════════════════════════════════════

    def event(self, e: QEvent) -> bool:
        """Intercept mouse events at scene level —  Diagram.MouseMove/.MouseLeftButtonUp.

        Qt note: QGraphicsScene.event() fires BEFORE item dispatch. When _connecting
        is True, we intercept move/release here so SocketItem doesn't need drag logic.
        """
        if self._connecting:
            if e.type() == QEvent.GraphicsSceneMouseMove:
                self._on_scene_mouse_move(e)
                return True
            if e.type() == QEvent.GraphicsSceneMouseRelease:
                self._on_scene_mouse_release(e)
                return True
            if e.type() == QEvent.GraphicsSceneMousePress:
                # During a drag, block further presses
                return True
        return super().event(e)

    def _on_scene_mouse_move(self, event: QGraphicsSceneMouseEvent):
        """ Diagram_MouseMove equivalent."""
        self._drag_to_pos = event.scenePos()
        if self._dynamic_edge is not None:
            self._dynamic_edge.set_temp_end(self._drag_to_pos)

    def _on_scene_mouse_release(self, event: QGraphicsSceneMouseEvent):
        """ Diagram_MouseLeftButtonUp equivalent."""
        if not self._connecting:
            return
        self._connecting = False
        scene_pos = event.scenePos()
        target = self._find_socket_at(scene_pos, exclude=self._drag_from_socket)
        from_sock = self._drag_from_socket
        self._drag_from_socket = None

        # Hide preview immediately (Clear → _dynamicLink.Visibility = Collapsed)
        if self._dynamic_edge is not None:
            self._dynamic_edge.hide_preview()

        if not target or not from_sock:
            self.status_message.emit("连线已取消")
            return

        # Dispatcher.BeginInvoke(InputPriority, Create(port))
        self._pending_from = from_sock
        self._pending_to = target
        self._commit_timer.start()

    # ═══════════════════════════════════════════════════════════════════════════
    # Command stack access
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def link_drawer(self) -> ILinkDrawer:
        """ Diagram.LinkDrawer — replaceable link drawing strategy."""
        return self._link_drawer

    @link_drawer.setter
    def link_drawer(self, value: ILinkDrawer):
        self._link_drawer = value
        # Refresh all edges —  RefreshLinkDrawer()
        for edge in self._edge_items.values():
            edge._drawer = value
            edge._rebuild()
            edge.update()

    @property
    def command_stack(self) -> CommandStack:
        return self._cmd_stack

    # ═══════════════════════════════════════════════════════════════════════════
    # Grid background
    # ═══════════════════════════════════════════════════════════════════════════

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        if not self._show_grid:
            return
        grid_color = theme_manager.color("canvas_grid")
        grid_pen = QPen(grid_color, 0.5)
        painter.setPen(grid_pen)
        gs = 20.0
        left = int(rect.left() / gs) * gs
        top = int(rect.top() / gs) * gs
        x = left
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += gs
        y = top
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += gs

    def toggle_grid(self):
        self._show_grid = not self._show_grid
        if self._show_grid:
            self.setBackgroundBrush(_make_checker_brush())
        else:
            self.setBackgroundBrush(QBrush(theme_manager.color("canvas_checker_base")))
        self.update()

    # ═══════════════════════════════════════════════════════════════════════════
    # Node management (Diagram.AddNode / RemoveNode)
    # ═══════════════════════════════════════════════════════════════════════════

    def bind_workflow(self, workflow: WorkflowEngine):
        self._workflow = workflow

    def add_node_item(self, node_data: NodeBase, pos: QPointF = None,
                      group_name: str = "", sync_workflow: bool = True,
                      auto_link: bool = True) -> NodeItem:
        item = NodeItem(node_data, group_name)
        item.setZValue(LayerZ.NODE)
        if pos is not None:
            item.setPos(pos)
        else:
            count = len(self._node_items)
            x = (count % 5) * 170 - 340
            y = (count // 5) * 70 - 200
            item.setPos(x, y)

        # DoLayoutPort — position sockets along edges
        self._do_layout_port(item)

        # Assign sequential index
        self._node_counter += 1
        item._index = self._node_counter

        self.addItem(item)
        self._node_items[node_data.node_id] = item
        item.node_selected.connect(self._on_node_item_selected)
        item.node_moved.connect(self._on_node_item_moved)

        if sync_workflow and self._workflow:
            self._workflow.add_node(node_data)

        # Auto-connect to previous index node (skip the first node, only for new user actions)
        if auto_link and item._index > 1:
            self._auto_connect_to_previous(item)

        event_system.publish(EventType.NODE_ADDED, sender=self, node=node_data)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.node_item_added.emit(item)
        return item

    def _auto_connect_to_previous(self, current_item: NodeItem):
        """Auto-connect current node to the node with index = current_index - 1."""
        prev_item = next(
            (it for it in self._node_items.values()
             if it._index == current_item._index - 1),
            None
        )
        if prev_item is None:
            return

        out_socket = prev_item.get_output_sockets()[0] if prev_item.get_output_sockets() else None
        in_socket = current_item.get_input_sockets()[0] if current_item.get_input_sockets() else None
        if out_socket and in_socket:
            self.create_edge(out_socket, in_socket, sync_workflow=True)

    def remove_node_item(self, node_id: str, sync_workflow: bool = True):
        item = self._node_items.pop(node_id, None)
        if item is None:
            return

        # Collect incoming and outgoing edges before removal
        incoming_sockets: list[SocketItem] = []
        outgoing_sockets: list[SocketItem] = []
        edges_to_remove: list[str] = []
        for eid, edge in list(self._edge_items.items()):
            if edge.from_socket and edge.from_socket.port.node_id == node_id:
                # This node is the source — find the target socket
                if edge.to_socket:
                    outgoing_sockets.append(edge.to_socket)
                edges_to_remove.append(eid)
            elif edge.to_socket and edge.to_socket.port.node_id == node_id:
                # This node is the target — find the source socket
                if edge.from_socket:
                    incoming_sockets.append(edge.from_socket)
                edges_to_remove.append(eid)

        # Remove connected edges
        for eid in edges_to_remove:
            self.remove_edge_item(eid, sync_workflow=sync_workflow)

        # Bridge: reconnect each incoming source to each outgoing target
        for in_sock in incoming_sockets:
            for out_sock in outgoing_sockets:
                self.create_edge(in_sock, out_sock, sync_workflow=sync_workflow)

        self.removeItem(item)
        if sync_workflow and self._workflow:
            self._workflow.remove_node(node_id)
        self._reindex_nodes()
        event_system.publish(EventType.NODE_REMOVED, sender=self, node=item.node_data)
        event_system.publish(EventType.DIAGRAM_CHANGED, sender=self)
        self.node_item_removed.emit(node_id)

    def _reindex_nodes(self):
        """Re-assign sequential indices to all nodes after a deletion."""
        items = sorted(self._node_items.values(), key=lambda it: it._index)
        self._node_counter = 0
        for it in items:
            self._node_counter += 1
            it._index = self._node_counter
            it.update()

    def get_node_item(self, node_id: str) -> NodeItem | None:
        return self._node_items.get(node_id)

    def get_all_node_items(self) -> list[NodeItem]:
        return list(self._node_items.values())

    # ═══════════════════════════════════════════════════════════════════════════
    # Edge management
    # ═══════════════════════════════════════════════════════════════════════════

    def create_edge(self, from_socket: SocketItem, to_socket: SocketItem,
                    sync_workflow: bool = True,
                    existing_link: LinkData | None = None) -> EdgeItem | None:
        """Create a committed edge —  Link.Create + diagram.AddLink combined."""
        # Normalize direction: output → input
        if from_socket.port.is_input and to_socket.port.is_output:
            from_socket, to_socket = to_socket, from_socket
        if not from_socket.port.is_output or not to_socket.port.is_input:
            return None
        if from_socket.port.node_id == to_socket.port.node_id:
            return None

        # Check for duplicate
        for edge in self._edge_items.values():
            if (edge.from_socket is from_socket and edge.to_socket is to_socket) or (
                edge.link_data and
                edge.link_data.from_port_id == from_socket.port.port_id and
                edge.link_data.to_port_id == to_socket.port.port_id
            ):
                return None

        # Create LinkData in workflow
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

        # Create EdgeItem with scene's default drawer
        edge = EdgeItem(from_socket, to_socket, link, drawer=self._link_drawer)
        edge.setZValue(LayerZ.LINK)

        # Add to scene FIRST, then register with sockets (avoids Qt double-add issues)
        self.addItem(edge)
        self._edge_items[link.link_id] = edge

        # Register with sockets AFTER scene.addItem
        from_socket.add_edge(edge)
        to_socket.add_edge(edge)

        # DoLayoutLink — compute start/end points and rebuild path
        self._do_layout_link(edge)

        edge.edge_selected.connect(self._on_edge_selected)
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

    # ═══════════════════════════════════════════════════════════════════════════
    # DoLayoutPort / DoLayoutLink
    # ═══════════════════════════════════════════════════════════════════════════

    def _do_layout_port(self, node_item: NodeItem):
        """Position sockets evenly along each edge"""
        ports_by_dock: dict[PortDock, list[SocketItem]] = {}
        for sock in node_item.sockets:
            ports_by_dock.setdefault(sock.port.dock, []).append(sock)

        w, h = node_item._node_w, node_item._node_h

        for dock, sockets in ports_by_dock.items():
            n = len(sockets)
            if n == 0:
                continue
            for i, sock in enumerate(sockets):
                if dock == PortDock.TOP:
                    x = -w / 2 + w * (i + 1) / (n + 1)
                    y = -h / 2
                elif dock == PortDock.BOTTOM:
                    x = -w / 2 + w * (i + 1) / (n + 1)
                    y = h / 2
                elif dock == PortDock.LEFT:
                    x = -w / 2
                    y = -h / 2 + h * (i + 1) / (n + 1)
                else:  # RIGHT
                    x = w / 2
                    y = -h / 2 + h * (i + 1) / (n + 1)
                sock.setPos(QPointF(x, y))

    def _do_layout_link(self, edge: EdgeItem):
        """Compute start/end from port positions and rebuild path """
        if edge.from_socket is None or edge.to_socket is None:
            return
        start = edge.from_socket.get_center_scene_pos()
        end = edge.to_socket.get_center_scene_pos()
        edge._path_start = start
        edge._path_end = end
        edge._rebuild()

    def _relayout_links_for_node(self, node_item: NodeItem):
        """Update all edges connected to a node """
        node_id = node_item.node_data.node_id
        for edge in self._edge_items.values():
            if (edge.from_socket and edge.from_socket.port.node_id == node_id) or \
               (edge.to_socket and edge.to_socket.port.node_id == node_id):
                self._do_layout_link(edge)
                edge.update()
        # Also re-layout ports for the moved node
        self._do_layout_port(node_item)

    # ═══════════════════════════════════════════════════════════════════════════
    # Drag-to-connect with reusable singleton preview
    # ═══════════════════════════════════════════════════════════════════════════

    def _init_dynamic_edge(self):
        """Lazy-create the single reusable preview edge"""
        if self._dynamic_edge is not None:
            return
        self._dynamic_edge = EdgeItem()
        self._dynamic_edge.setZValue(LayerZ.DYNAMIC)
        self._dynamic_edge.setVisible(False)
        self._dynamic_edge.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self._dynamic_edge.setAcceptHoverEvents(False)
        self.addItem(self._dynamic_edge)

    def start_edge_drag(self, from_socket: SocketItem):
        """PortLinkBehavior.Init → InitDynamic."""
        # Only output/both ports can start connections
        if not from_socket.port.is_output:
            return

        self._init_dynamic_edge()
        self._dynamic_edge.show_preview(from_socket)
        self._drag_from_socket = from_socket
        self._drag_to_pos = from_socket.get_center_scene_pos()
        self._connecting = True

    def update_edge_drag(self, sock, scene_pos: QPointF):
        """Legacy path — kept for SocketItem signal compatibility.
        Primary path is now via event() → _on_scene_mouse_move."""
        if not self._connecting:
            return
        self._drag_to_pos = scene_pos
        if self._dynamic_edge is not None:
            self._dynamic_edge.set_temp_end(scene_pos)

    def end_edge_drag(self, sock, scene_pos: QPointF):
        """Legacy path — kept for SocketItem signal compatibility.
        Primary path is now via event() → _on_scene_mouse_release."""
        if not self._connecting:
            return
        self._connecting = False
        target = self._find_socket_at(scene_pos, exclude=sock)
        from_sock = self._drag_from_socket
        self._drag_from_socket = None
        if self._dynamic_edge is not None:
            self._dynamic_edge.hide_preview()
        if not target or not from_sock:
            self.status_message.emit("连线已取消")
            return
        self._pending_from = from_sock
        self._pending_to = target
        self._commit_timer.start()

    def _do_pending_commit(self):
        """Dispatcher.BeginInvoke callback — delayed edge creation."""
        fs = self._pending_from
        ts = self._pending_to
        self._pending_from = None
        self._pending_to = None
        if fs is not None and ts is not None:
            self._commit_edge(fs, ts)

    def _commit_edge(self, from_socket: SocketItem, to_socket: SocketItem):
        """Delayed edge creation"""
        try:
            cmd = AddLinkCommand(self, from_socket, to_socket)
            result = self._cmd_stack.execute(cmd)
            if result:
                self.status_message.emit("连线已创建")
            else:
                self.status_message.emit("连线创建失败")
        except Exception as e:
            self.status_message.emit(f"连线异常: {e}")

    def _find_socket_at(self, scene_pos: QPointF, exclude: SocketItem = None) -> SocketItem | None:
        """Hit-test for sockets at scene position"""
        exclude_node_id = exclude.port.node_id if exclude else None
        for node_item in self._node_items.values():
            socket = node_item.get_socket_at(scene_pos)
            if socket is None or socket is exclude:
                continue
            if socket.port.node_id == exclude_node_id:
                continue
            return socket
        return None

    # ═══════════════════════════════════════════════════════════════════════════
    # Selection
    # ═══════════════════════════════════════════════════════════════════════════

    def _on_node_item_selected(self, node_data: NodeBase):
        self.node_selected.emit(node_data)
        event_system.publish(EventType.NODE_SELECTED, sender=node_data, node=node_data)

    def _on_node_item_moved(self, node_data: NodeBase):
        """When a node moves, re-layout its ports and connected edges."""
        item = self._node_items.get(node_data.node_id)
        if item:
            self._relayout_links_for_node(item)
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
        items = self.selectedItems()
        if not items:
            return
        batch = BatchCommand(description="删除选中项")
        for item in items:
            if isinstance(item, NodeItem):
                batch.add(RemoveNodeCommand(self, item.node_data.node_id))
            elif isinstance(item, EdgeItem):
                if item.link_data:
                    batch.add(RemoveLinkCommand(self, item.link_data.link_id))
        self._cmd_stack.execute(batch)

    # ═══════════════════════════════════════════════════════════════════════════
    # Copy / Paste
    # ═══════════════════════════════════════════════════════════════════════════

    def copy_selected(self):
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
        if not self._clipboard:
            return
        batch = BatchCommand(description="粘贴节点")
        offset = 30 + 15 * len(self._clipboard)
        for clip in self._clipboard:
            node = node_registry.create(clip["type"])
            if node:
                if "data" in clip and clip["data"]:
                    node.from_dict(clip["data"]) if hasattr(node, 'from_dict') else None
                pos = QPointF(clip.get("x", 0) + offset, clip.get("y", 0) + offset)
                batch.add(AddNodeCommand(self, node, (pos.x(), pos.y())))
        self._cmd_stack.execute(batch)
        self.status_message.emit(f"已粘贴 {len(self._clipboard)} 个节点")
        self._clipboard.clear()

    # ═══════════════════════════════════════════════════════════════════════════
    # Alignment
    # ═══════════════════════════════════════════════════════════════════════════

    def align_selected(self, mode: str):
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

    # ═══════════════════════════════════════════════════════════════════════════
    # Undo / Redo
    # ═══════════════════════════════════════════════════════════════════════════

    def undo(self):
        if self._cmd_stack.undo():
            self.status_message.emit(f"撤销: {self._cmd_stack.undo_description}")

    def redo(self):
        if self._cmd_stack.redo():
            self.status_message.emit(f"重做: {self._cmd_stack.redo_description}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Workflow state feedback
    # ═══════════════════════════════════════════════════════════════════════════

    def on_workflow_state_changed(self, node_id: str, state: str):
        """Update node AND connected edges to reflect execution state"""
        item = self._node_items.get(node_id)
        if item is None:
            return
        state_map = {
            "running": NodeState.RUNNING,
            "completed": NodeState.COMPLETED,
            "error": NodeState.ERROR,
            "idle": NodeState.IDLE,
        }
        ns = state_map.get(state, NodeState.IDLE)
        item.set_state(ns)

        # Update connected edges
        edge_state_map = {
            "running": EdgeState.RUNNING,
            "completed": EdgeState.SUCCESS,
            "error": EdgeState.ERROR,
            "idle": EdgeState.NORMAL,
        }
        es = edge_state_map.get(state, EdgeState.NORMAL)
        for edge in self._edge_items.values():
            if (edge.from_socket and edge.from_socket.port.node_id == node_id) or \
               (edge.to_socket and edge.to_socket.port.node_id == node_id):
                edge.set_state(es)

    def on_link_state_changed(self, link_id: str, state: str):
        """Update an individual link's edge visual state"""
        edge = self._edge_items.get(link_id)
        if edge is None:
            return
        state_map = {
            "running": EdgeState.RUNNING,
            "completed": EdgeState.SUCCESS,
            "error": EdgeState.ERROR,
        }
        es = state_map.get(state, EdgeState.NORMAL)
        edge.set_state(es)

    def on_port_state_changed(self, node_id: str, port_id: str, state: str):
        """Update a socket's visual state"""
        node_item = self._node_items.get(node_id)
        if node_item is None:
            return
        for sock in node_item.sockets:
            if sock.port.port_id == port_id:
                if state == "running":
                    sock.set_highlight(True)
                else:
                    sock.set_highlight(False)
                break

    # ═══════════════════════════════════════════════════════════════════════════
    # Context menu
    # ═══════════════════════════════════════════════════════════════════════════

    def context_menu(self, pos: QPointF) -> QMenu | None:
        item = self.itemAt(pos, QTransform())
        menu = QMenu()

        if isinstance(item, NodeItem):
            return None

        elif isinstance(item, EdgeItem):
            return None

        else:
            px, py = pos.x(), pos.y()
            add_menu = menu.addMenu("添加节点")
            self._build_node_type_menu(add_menu, menu, px, py)
            return menu

    def _run_single_node(self, node_data: NodeBase):
        if self._workflow and isinstance(node_data, VisionNodeData):
            node_data.update_invoke_current()
            item = self._node_items.get(node_data.node_id)
            if item:
                item.update_from_node()
            self.status_message.emit(f"已执行: {node_data.name}")

    def _build_node_type_menu(self, parent_menu: QMenu, root_menu: QMenu,
                               px: float, py: float):
        """Build hierarchical node-type menu from registered groups."""
        import re
        import inspect
        all_instantiable = {
            t.__name__: t
            for t in node_registry._nodes.values()
            if not inspect.isabstract(t)
        }

        def _node_label(node_type: type) -> str:
            """Resolve display name: try instantiation, fall back to class name."""
            try:
                inst = node_type()
                name = inst.name or ''
                if name and name != node_type.__name__ and len(name) < 30:
                    return name
            except Exception:
                pass
            cls_name = node_type.__name__
            spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', cls_name)
            spaced = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', spaced)
            return spaced

        used: set[str] = set()
        for group in node_data_group_manager.get_all_groups():
            group_types: list[type] = []
            for nt in group.node_types:
                if nt.__name__ in all_instantiable and nt.__name__ not in used:
                    group_types.append(nt)
                    used.add(nt.__name__)
            if not group_types:
                continue
            sub_menu = parent_menu.addMenu(group.name)
            for node_type in group_types:
                label = _node_label(node_type)
                action = QAction(label, root_menu)
                action.triggered.connect(
                    lambda checked, nt=node_type, x=px, y=py:
                        self._cmd_stack.execute(AddNodeCommand(self, nt(), (x, y))))
                sub_menu.addAction(action)
        # Ungrouped nodes
        ungrouped = [t for n, t in all_instantiable.items() if n not in used]
        if ungrouped:
            sub_menu = parent_menu.addMenu("其他")
            for node_type in ungrouped:
                label = _node_label(node_type)
                action = QAction(label, root_menu)
                action.triggered.connect(
                    lambda checked, nt=node_type, x=px, y=py:
                        self._cmd_stack.execute(AddNodeCommand(self, nt(), (x, y))))
                sub_menu.addAction(action)

    # ═══════════════════════════════════════════════════════════════════════════
    # Serialization
    # ═══════════════════════════════════════════════════════════════════════════

    def clear_all(self, sync_workflow: bool = True):
        for node_id in list(self._node_items.keys()):
            self.remove_node_item(node_id, sync_workflow=sync_workflow)
        self._node_items.clear()
        self._edge_items.clear()
        self._cmd_stack.clear()
        self._node_counter = 0

    def load_from_workflow(self, workflow: WorkflowEngine):
        self.clear_all(sync_workflow=False)
        self._workflow = workflow

        for node in workflow.get_all_nodes():
            x = getattr(node, '_pos_x', 0.0) or 0.0
            y = getattr(node, '_pos_y', 0.0) or 0.0
            pos = QPointF(x, y) if (x or y) else None
            item = self.add_node_item(node, pos, sync_workflow=False, auto_link=False)
            if item:
                node._pos_x = item.pos().x()
                node._pos_y = item.pos().y()

        for link in workflow.get_all_links():
            from_item = self.get_node_item(link.from_node_id)
            to_item = self.get_node_item(link.to_node_id)
            if from_item and to_item:
                fs = from_item.get_socket_by_port_id(link.from_port_id)
                ts = to_item.get_socket_by_port_id(link.to_port_id)
                if fs and ts:
                    self.create_edge(fs, ts, sync_workflow=False, existing_link=link)

    def save_to_workflow(self, workflow: WorkflowEngine):
        for node_id, item in self._node_items.items():
            pos = item.pos()
            nd = item.node_data
            nd._pos_x = pos.x()
            nd._pos_y = pos.y()
        workflow._links = []
        for edge in self._edge_items.values():
            if edge.link_data:
                workflow._links.append(edge.link_data)
