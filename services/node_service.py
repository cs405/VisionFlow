"""Node service — node type discovery and creation.

Wraps NodeRegistry + NodeDataGroupBase behind a clean interface.
Depends on AppContext for registry and group manager references.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from core.interfaces import INodeData, INodeService

if TYPE_CHECKING:
    from services.app_context import AppContext


class NodeService(INodeService):
    """Default node service using registry + group manager from AppContext."""

    def __init__(self, ctx: AppContext = None):
        if ctx is None:
            from services.app_context import get_app_context
            ctx = get_app_context()
        self._ctx = ctx

    @property
    def _registry(self):
        return self._ctx.node_registry

    @property
    def _groups(self):
        return self._ctx.node_groups

    def get_all_node_types(self) -> list[type]:
        return self._registry.get_all_node_types() if self._registry else []

    def get_node_type(self, type_name: str) -> type | None:
        return self._registry.get_node_type(type_name) if self._registry else None

    def create_node(self, type_name: str) -> INodeData | None:
        return self._registry.create(type_name) if self._registry else None

    def get_groups(self) -> list:
        return self._groups.get_all_groups() if self._groups else []

    def discover_module(self, module, group_prefix: str = ""):
        """Discover NodeBase subclasses in a module and register."""
        if self._groups:
            self._groups.discover_module(module, group_prefix)
