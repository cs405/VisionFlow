"""Diagram scene — WPF Diagram + Layer architecture 1:1 port.

Layers (Z-value bands matching WPF NodeLayer / LinkLayer / DynamicLayer):
  - NodeLayer (Z=10):   NodeItem
  - LinkLayer (Z=5):    EdgeItem (committed links)
  - DynamicLayer (Z=100): _dynamic_edge (reusable drag preview)

Event flow (WPF Diagram-level MouseMove/MouseLeftButtonUp pattern):
  1. SocketItem.mousePressEvent → emits signal → scene.start_edge_drag()
  2. scene.event() intercepts GraphicsSceneMouseMove → scene._on_scene_mouse_move()
  3. scene.event() intercepts GraphicsSceneMouseRelease → scene._on_scene_mouse_release()
  4. QTimer.singleShot(10, _commit_edge) — delayed creation (WPF Dispatcher.BeginInvoke)
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


SCENE_RECT = QRectF(-5000, -5000, 10000, 10000)

# Checkerboard tile — 1:1 port of WPF H.Theme BrushKeys Tile pattern
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


# ── Layer Z-values (WPF Z-order: NodeLayer → LinkLayer → DynamicLayer) ──

class LayerZ:
    """Z-value constants matching WPF layer ordering.

    In WPF the layers are Panels stacked in a Canvas. In Qt we use Z-values.
    Higher Z = rendered on top.
    """
    LINK = 5          # LinkLayer — edges render below nodes
    NODE = 10         # NodeLayer — nodes render above edges
    DYNAMIC = 100     # DynamicLayer — drag preview renders above everything


class DiagramScene(QGraphicsScene):
    """Main diagram scene with WPF-aligned layer and event architecture."""

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
        self._link_drawer: ILinkDrawer = BrokenLinkDrawer()  # WPF default: 折线

        # ── WPF DynamicLayer: single reusable preview edge ──
        self._dynamic_edge: EdgeItem | None = None

        # ── WPF Diagram-level drag state (replaces SocketItem-level handling) ──
        self._connecting = False
        self._drag_from_socket: SocketItem | None = None
        self._drag_to_pos: QPointF = QPointF()

        # ── Pending commit (WPF Dispatcher.BeginInvoke queue) ──
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

        self.selectionChanged.connect(self._on_selection_changed)

    # ═══════════════════════════════════════════════════════════════════════════
    # WPF Diagram-Level Event Handling (event() override)
    # ═══════════════════════════════════════════════════════════════════════════

    def event(self, e: QEvent) -> bool:
        """Intercept mouse events at scene level — WPF Diagram.MouseMove/.MouseLeftButtonUp.

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
        """WPF Diagram_MouseMove equivalent."""
        self._drag_to_pos = event.scenePos()
        if self._dynamic_edge is not None:
            self._dynamic_edge.set_temp_end(self._drag_to_pos)

    def _on_scene_mouse_release(self, event: QGraphicsSceneMouseEvent):
        """WPF Diagram_MouseLeftButtonUp equivalent."""
        if not self._connecting:
            return
        self._connecting = False
        scene_pos = event.scenePos()
        target = self._find_socket_at(scene_pos, exclude=self._drag_from_socket)
        from_sock = self._drag_from_socket
        self._drag_from_socket = None

        # Hide preview immediately (WPF Clear → _dynamicLink.Visibility = Collapsed)
        if self._dynamic_edge is not None:
            self._dynamic_edge.hide_preview()

        if not target or not from_sock:
            self.status_message.emit("连线已取消")
            return

        # WPF: Dispatcher.BeginInvoke(InputPriority, Create(port))
        self._pending_from = from_sock
        self._pending_to = target
        self._commit_timer.start()

    # ═══════════════════════════════════════════════════════════════════════════
    # Command stack access
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def link_drawer(self) -> ILinkDrawer:
        """WPF Diagram.LinkDrawer — replaceable link drawing strategy."""
        return self._link_drawer

    @link_drawer.setter
    def link_drawer(self, value: ILinkDrawer):
        self._link_drawer = value
        # Refresh all edges — WPF RefreshLinkDrawer()
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
    # Node management (WPF Diagram.AddNode / RemoveNode)
    # ═══════════════════════════════════════════════════════════════════════════

    def bind_workflow(self, workflow: WorkflowEngine):
        self._workflow = workflow

    def add_node_item(self, node_data: NodeBase, pos: QPointF = None,
                      group_name: str = "", sync_workflow: bool = True) -> NodeItem:
        item = NodeItem(node_data, group_name)
        item.setZValue(LayerZ.NODE)
        if pos is not None:
            item.setPos(pos)
        else:
            count = len(self._node_items)
            x = (count % 5) * 170 - 340
            y = (count // 5) * 70 - 200
            item.setPos(x, y)

        # DoLayoutPort — position sockets along edges (WPF Layout.DoLayoutPort)
        self._do_layout_port(item)

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
        # Remove connected edges first
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

    # ═══════════════════════════════════════════════════════════════════════════
    # Edge management (WPF Diagram.AddLink / RemoveLink)
    # ═══════════════════════════════════════════════════════════════════════════

    def create_edge(self, from_socket: SocketItem, to_socket: SocketItem,
                    sync_workflow: bool = True,
                    existing_link: LinkData | None = None) -> EdgeItem | None:
        """Create a committed edge — WPF Link.Create + diagram.AddLink combined."""
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

        # Create EdgeItem with scene's default drawer (WPF: diagram.LinkDrawer)
        edge = EdgeItem(from_socket, to_socket, link, drawer=self._link_drawer)
        edge.setZValue(LayerZ.LINK)

        # Add to scene FIRST, then register with sockets (avoids Qt double-add issues)
        self.addItem(edge)
        self._edge_items[link.link_id] = edge

        # Register with sockets AFTER scene.addItem (WPF: LinkLayer.Children.Add then wire up)
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
    # WPF Layout: DoLayoutPort / DoLayoutLink
    # ═══════════════════════════════════════════════════════════════════════════

    def _do_layout_port(self, node_item: NodeItem):
        """Position sockets evenly along each edge — WPF Layout.DoLayoutPort()."""
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
        """Compute start/end from port positions and rebuild path — WPF Layout.DoLayoutLink()."""
        if edge.from_socket is None or edge.to_socket is None:
            return
        start = edge.from_socket.get_center_scene_pos()
        end = edge.to_socket.get_center_scene_pos()
        edge._path_start = start
        edge._path_end = end
        edge._rebuild()

    def _relayout_links_for_node(self, node_item: NodeItem):
        """Update all edges connected to a node — WPF Layout.DoLayoutLink(node)."""
        node_id = node_item.node_data.node_id
        for edge in self._edge_items.values():
            if (edge.from_socket and edge.from_socket.port.node_id == node_id) or \
               (edge.to_socket and edge.to_socket.port.node_id == node_id):
                self._do_layout_link(edge)
                edge.update()
        # Also re-layout ports for the moved node
        self._do_layout_port(node_item)

    # ═══════════════════════════════════════════════════════════════════════════
    # WPF DynamicLayer: Drag-to-connect with reusable singleton preview
    # ═══════════════════════════════════════════════════════════════════════════

    def _init_dynamic_edge(self):
        """Lazy-create the single reusable preview edge (WPF _dynamicLink singleton)."""
        if self._dynamic_edge is not None:
            return
        self._dynamic_edge = EdgeItem()
        self._dynamic_edge.setZValue(LayerZ.DYNAMIC)
        self._dynamic_edge.setVisible(False)
        self._dynamic_edge.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self._dynamic_edge.setAcceptHoverEvents(False)
        self.addItem(self._dynamic_edge)

    def start_edge_drag(self, from_socket: SocketItem):
        """WPF PortLinkBehavior.Init → InitDynamic."""
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
        """WPF Dispatcher.BeginInvoke callback — delayed edge creation."""
        fs = self._pending_from
        ts = self._pending_to
        self._pending_from = None
        self._pending_to = None
        if fs is not None and ts is not None:
            self._commit_edge(fs, ts)

    def _commit_edge(self, from_socket: SocketItem, to_socket: SocketItem):
        """Delayed edge creation — WPF Dispatcher.BeginInvoke(Create(port))."""
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
        """Hit-test for sockets at scene position — WPF VisualTreeHelper.HitTest equivalent."""
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
        """Update node AND connected edges to reflect execution state — WPF State triggers."""
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

        # Update connected edges — WPF Link DataTriggers (State=Running/Success/Error)
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

    # ═══════════════════════════════════════════════════════════════════════════
    # Context menu
    # ═══════════════════════════════════════════════════════════════════════════

    def context_menu(self, pos: QPointF) -> QMenu | None:
        item = self.itemAt(pos, QTransform())
        menu = QMenu()

        if isinstance(item, NodeItem):
            run_act = QAction("▶  运行此节点", menu)
            run_act.triggered.connect(lambda: self._run_single_node(item.node_data))
            menu.addAction(run_act)
            menu.addSeparator()

            prop_act = QAction("⚙  属性...", menu)
            prop_act.triggered.connect(lambda: self.node_properties_requested.emit(item.node_data))
            menu.addAction(prop_act)

            copy_act = QAction("📋  复制", menu)
            copy_act.triggered.connect(self.copy_selected)
            menu.addAction(copy_act)
            menu.addSeparator()

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

            help_act = QAction("?  帮助", menu)
            help_act.triggered.connect(lambda: self.node_help_requested.emit(item.node_data))
            menu.addAction(help_act)

        elif isinstance(item, EdgeItem):
            delete_act = QAction("删除连线", menu)
            delete_act.triggered.connect(
                lambda: self._cmd_stack.execute(
                    RemoveLinkCommand(self, item.link_data.link_id) if item.link_data else None))
            menu.addAction(delete_act)
            menu.addSeparator()
            label_act = QAction("添加标签", menu)
            label_act.triggered.connect(lambda: item.set_label(
                getattr(item.from_socket.port, 'data_type', 'image') if item.from_socket else ''))
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

    # ═══════════════════════════════════════════════════════════════════════════
    # Serialization
    # ═══════════════════════════════════════════════════════════════════════════

    def clear_all(self, sync_workflow: bool = True):
        for node_id in list(self._node_items.keys()):
            self.remove_node_item(node_id, sync_workflow=sync_workflow)
        self._node_items.clear()
        self._edge_items.clear()
        self._cmd_stack.clear()

    def load_from_workflow(self, workflow: WorkflowEngine):
        self.clear_all(sync_workflow=False)
        self._workflow = workflow

        for node in workflow.get_all_nodes():
            x = getattr(node, '_pos_x', 0.0) or 0.0
            y = getattr(node, '_pos_y', 0.0) or 0.0
            pos = QPointF(x, y) if (x or y) else None
            item = self.add_node_item(node, pos, sync_workflow=False)
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
