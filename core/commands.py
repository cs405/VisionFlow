"""Undo/redo command system

Encapsulates diagram mutations as reversible commands.
Supports: add/remove/move node, add/remove link, batch commands.

GUI-framework-agnostic: uses plain (x, y) tuples for positions.
The GUI layer converts Qt points via _to_point().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Command(ABC):
    """A reversible operation on the diagram. Scene is passed at execute/undo time."""

    def __init__(self):
        self._description = self.__class__.__name__

    @abstractmethod
    def execute(self, scene: Any) -> Any:
        """Execute the command on the given scene."""
        ...

    @abstractmethod
    def undo(self, scene: Any) -> Any:
        """Reverse the command on the given scene."""
        ...

    @property
    def description(self) -> str:
        return self._description


class BatchCommand(Command):
    """A group of commands executed and undone together."""

    def __init__(self, description: str = "批量操作"):
        super().__init__()
        self._description = description
        self._commands: list[Command] = []

    def add(self, cmd: Command):
        self._commands.append(cmd)

    def execute(self, scene: Any) -> Any:
        for cmd in self._commands:
            cmd.execute(scene)

    def undo(self, scene: Any) -> Any:
        for cmd in reversed(self._commands):
            cmd.undo(scene)


class AddNodeCommand(Command):
    """Command: add a node at a position."""

    def __init__(self, scene, node_data: Any, pos=None, group_name: str = ""):
        super().__init__()
        self._node_data = node_data
        self._pos = pos
        self._group_name = group_name
        self._node_id = node_data.node_id
        self._description = f"添加节点: {node_data.name}"
        self._scene = scene  # store for undo

    def execute(self, scene: Any) -> Any:
        pos = _to_point(self._pos) if self._pos else None
        return scene.add_node_item(self._node_data, pos, self._group_name)

    def undo(self, scene: Any) -> Any:
        scene.remove_node_item(self._node_id)


class RemoveNodeCommand(Command):
    """Command: remove a node (storing position + links for undo)."""

    def __init__(self, scene, node_id: str):
        super().__init__()
        self._node_id = node_id
        self._saved_node: Any = None
        self._saved_pos = (0.0, 0.0)
        self._group_name: str = ""
        self._description = f"删除节点: {node_id}"

    def execute(self, scene: Any) -> Any:
        item = scene.get_node_item(self._node_id)
        if item is None:
            return
        self._saved_node = item.node_data
        p = item.pos()
        self._saved_pos = (p.x(), p.y())
        scene.remove_node_item(self._node_id)

    def undo(self, scene: Any) -> Any:
        if self._saved_node is None:
            return
        pos = _to_point(self._saved_pos)
        scene.add_node_item(self._saved_node, pos, self._group_name, sync_workflow=False)


class AddLinkCommand(Command):
    """Command: add a link between two sockets."""

    def __init__(self, scene, from_socket: Any, to_socket: Any):
        super().__init__()
        self._from_node_id = from_socket.port.node_id
        self._to_node_id = to_socket.port.node_id
        self._from_port_id = from_socket.port.port_id
        self._to_port_id = to_socket.port.port_id
        self._link_id: str = ""
        self._description = "添加连线"

    def execute(self, scene: Any) -> Any:
        from_item = scene.get_node_item(self._from_node_id)
        to_item = scene.get_node_item(self._to_node_id)
        if not from_item or not to_item:
            return None
        fs = from_item.get_socket_by_port_id(self._from_port_id)
        ts = to_item.get_socket_by_port_id(self._to_port_id)
        if fs and ts:
            edge = scene.create_edge(fs, ts)
            if edge and edge.link_data:
                self._link_id = edge.link_data.link_id
            return edge
        return None

    def undo(self, scene: Any) -> Any:
        if self._link_id:
            scene.remove_edge_item(self._link_id)


class RemoveLinkCommand(Command):
    """Command: remove a link (storing endpoints for undo)."""

    def __init__(self, scene, link_id: str):
        super().__init__()
        self._link_id = link_id
        self._saved_from_node = ""
        self._saved_to_node = ""
        self._saved_from_port = ""
        self._saved_to_port = ""
        self._description = f"删除连线: {link_id}"

    def execute(self, scene: Any) -> Any:
        edge = scene.get_edge_item(self._link_id)
        if edge and edge.link_data:
            ld = edge.link_data
            self._saved_from_node = ld.from_node_id
            self._saved_to_node = ld.to_node_id
            self._saved_from_port = ld.from_port_id
            self._saved_to_port = ld.to_port_id
        scene.remove_edge_item(self._link_id)

    def undo(self, scene: Any) -> Any:
        from_item = scene.get_node_item(self._saved_from_node)
        to_item = scene.get_node_item(self._saved_to_node)
        if not from_item or not to_item:
            return
        fs = from_item.get_socket_by_port_id(self._saved_from_port)
        ts = to_item.get_socket_by_port_id(self._saved_to_port)
        if fs and ts:
            scene.create_edge(fs, ts, sync_workflow=True)


class MoveNodeCommand(Command):
    """Command: move a node from old position to new."""

    def __init__(self, scene, node_id: str, old_pos, new_pos):
        super().__init__()
        self._node_id = node_id
        self._old_pos = old_pos
        self._new_pos = new_pos
        self._description = f"移动节点: {node_id}"

    def execute(self, scene: Any) -> Any:
        item = scene.get_node_item(self._node_id)
        if item is None:
            return
        item.setPos(_to_point(self._new_pos))

    def undo(self, scene: Any) -> Any:
        item = scene.get_node_item(self._node_id)
        if item is None:
            return
        item.setPos(_to_point(self._old_pos))


class CommandStack:
    """Undo/redo stack — executes commands immediately, tracks for undo.

    The scene must be set before executing commands. All commands
    receive the scene parameter at execute/undo time.
    """

    def __init__(self, scene=None):
        self._scene = scene
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []

    def set_scene(self, scene):
        self._scene = scene

    def execute(self, cmd: Command) -> Any:
        """Execute command immediately and push to undo stack."""
        result = cmd.execute(self._scene)
        self._undo_stack.append(cmd)
        self._redo_stack.clear()
        return result

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo(self._scene)
        self._redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.execute(self._scene)
        self._undo_stack.append(cmd)
        return True

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_description(self) -> str:
        return self._undo_stack[-1].description if self._undo_stack else ""

    @property
    def redo_description(self) -> str:
        return self._redo_stack[-1].description if self._redo_stack else ""


# ── Point conversion (lazy-initialized) ───────────────────────────────────

_point_converter = None


def _to_point(pos):
    """Convert (x, y) tuple to framework-specific point type."""
    global _point_converter
    if _point_converter is None:
        try:
            from PyQt5.QtCore import QPointF
            _point_converter = lambda p: QPointF(p[0], p[1])
        except ImportError:
            _point_converter = lambda p: p
    return _point_converter(pos)
