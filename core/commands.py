"""Undo/redo command system — ported from C# ICommand / RevertibleStack.

Encapsulates diagram mutations as reversible commands.
Supports: add/remove/move node, add/remove link, batch commands.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from PyQt5.QtCore import QPointF


class Command(ABC):
    """A reversible operation on the diagram."""

    @abstractmethod
    def execute(self) -> bool:
        """Perform the operation. Returns True on success."""
        ...

    @abstractmethod
    def undo(self) -> bool:
        """Reverse the operation. Returns True on success."""
        ...

    @property
    def description(self) -> str:
        return self.__class__.__name__


class CommandStack:
    """Maintains undo and redo stacks of Command objects."""

    def __init__(self, max_size: int = 100):
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._max_size = max_size
        self._clean = True

    def execute(self, cmd: Command) -> bool:
        """Execute a command and push it onto the undo stack."""
        if cmd.execute():
            self._undo_stack.append(cmd)
            self._redo_stack.clear()
            if len(self._undo_stack) > self._max_size:
                self._undo_stack.pop(0)
            self._clean = False
            return True
        return False

    def undo(self) -> bool:
        """Undo the last command."""
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        if cmd.undo():
            self._redo_stack.append(cmd)
            return True
        self._undo_stack.append(cmd)  # push back on failure
        return False

    def redo(self) -> bool:
        """Redo the last undone command."""
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        if cmd.execute():
            self._undo_stack.append(cmd)
            return True
        self._redo_stack.append(cmd)
        return False

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def is_clean(self) -> bool:
        return self._clean

    def mark_clean(self):
        self._clean = True

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._clean = True

    @property
    def undo_description(self) -> str:
        return self._undo_stack[-1].description if self._undo_stack else ""

    @property
    def redo_description(self) -> str:
        return self._redo_stack[-1].description if self._redo_stack else ""


# ═══════════════════════════════════════════════════════════════════════════
# Concrete commands
# ═══════════════════════════════════════════════════════════════════════════

class AddNodeCommand(Command):
    """Add a node to the scene."""

    def __init__(self, scene, node_data, pos: QPointF = None, group_name: str = ""):
        self._scene = scene
        self._node_data = node_data
        self._pos = pos
        self._group_name = group_name
        self._node_item = None
        self.description = f"添加节点: {node_data.name}"

    def execute(self) -> bool:
        if self._node_item is not None:
            # Re-add existing item
            self._scene.addItem(self._node_item)
            self._scene._node_items[self._node_data.node_id] = self._node_item
        else:
            self._node_item = self._scene.add_node_item(
                self._node_data, self._pos, self._group_name)
        return self._node_item is not None

    def undo(self) -> bool:
        if self._node_item:
            self._scene.remove_node_item(self._node_data.node_id)
            return True
        return False


class RemoveNodeCommand(Command):
    """Remove a node and its edges from the scene."""

    def __init__(self, scene, node_id: str):
        self._scene = scene
        self._node_id = node_id
        self._node_item = scene.get_node_item(node_id)
        self._pos = self._node_item.pos() if self._node_item else QPointF()
        self._node_data = self._node_item.node_data if self._node_item else None
        self._edges: list[tuple] = []  # (link_data, from_id, to_id)
        self.description = f"删除节点: {getattr(self._node_data, 'name', node_id)}"

    def execute(self) -> bool:
        if self._node_item is None:
            return False
        # Save edges before removal
        self._edges.clear()
        for eid, edge in list(self._scene._edge_items.items()):
            if (edge.from_socket and edge.from_socket.port.node_id == self._node_id) or \
               (edge.to_socket and edge.to_socket.port.node_id == self._node_id):
                self._edges.append((edge.link_data, edge.from_socket.port.node_id if edge.from_socket else "",
                                   edge.to_socket.port.node_id if edge.to_socket else ""))
        self._pos = self._node_item.pos()
        self._scene.remove_node_item(self._node_id)
        return True

    def undo(self) -> bool:
        if self._node_data is None:
            return False
        self._node_item = self._scene.add_node_item(self._node_data, self._pos)
        # Restore edges
        for link, fid, tid in self._edges:
            f_item = self._scene.get_node_item(fid)
            t_item = self._scene.get_node_item(tid)
            if f_item and t_item:
                fs = f_item.get_socket_by_port_id(link.from_port_id)
                ts = t_item.get_socket_by_port_id(link.to_port_id)
                if fs and ts:
                    self._scene.create_edge(fs, ts)
        return self._node_item is not None


class AddLinkCommand(Command):
    """Add a link between two sockets."""

    def __init__(self, scene, from_socket, to_socket):
        self._scene = scene
        self._from_socket = from_socket
        self._to_socket = to_socket
        self._link_id: str = ""
        self.description = "添加连线"

    def execute(self) -> bool:
        edge = self._scene.create_edge(self._from_socket, self._to_socket)
        if edge:
            self._link_id = edge.link_data.link_id
            return True
        return False

    def undo(self) -> bool:
        if self._link_id:
            self._scene.remove_edge_item(self._link_id)
            return True
        return False


class RemoveLinkCommand(Command):
    """Remove a link."""

    def __init__(self, scene, link_id: str):
        self._scene = scene
        self._link_id = link_id
        edge = scene.get_edge_item(link_id)
        self._from_socket = edge.from_socket if edge else None
        self._to_socket = edge.to_socket if edge else None
        self.description = "删除连线"

    def execute(self) -> bool:
        self._scene.remove_edge_item(self._link_id)
        return True

    def undo(self) -> bool:
        if self._from_socket and self._to_socket:
            edge = self._scene.create_edge(self._from_socket, self._to_socket)
            if edge:
                self._link_id = edge.link_data.link_id
                return True
        return False


class MoveNodeCommand(Command):
    """Move a node to a new position."""

    def __init__(self, scene, node_id: str, old_pos: QPointF, new_pos: QPointF):
        self._scene = scene
        self._node_id = node_id
        self._old_pos = QPointF(old_pos)
        self._new_pos = QPointF(new_pos)
        self.description = "移动节点"

    def execute(self) -> bool:
        item = self._scene.get_node_item(self._node_id)
        if item:
            item.setPos(self._new_pos)
            return True
        return False

    def undo(self) -> bool:
        item = self._scene.get_node_item(self._node_id)
        if item:
            item.setPos(self._old_pos)
            return True
        return False


class BatchCommand(Command):
    """Execute multiple commands as one atomic unit."""

    def __init__(self, commands: list[Command] = None, description: str = "批量操作"):
        self._commands = commands or []
        self.description = description

    def add(self, cmd: Command):
        self._commands.append(cmd)

    def execute(self) -> bool:
        for cmd in self._commands:
            if not cmd.execute():
                # Rollback already executed commands
                for prev in reversed(self._commands[:self._commands.index(cmd)]):
                    prev.undo()
                return False
        return True

    def undo(self) -> bool:
        for cmd in reversed(self._commands):
            cmd.undo()
        return True
