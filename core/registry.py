"""Node registry - quick lookup and instantiation of node types.

"""

from typing import Type, Callable

from core.node_base import NodeBase


class NodeRegistry:
    """Central registry for node types.

    Maps node type names -> node classes for instantiation.
    """

    def __init__(self):
        self._nodes: dict[str, Type[NodeBase]] = {}
        self._categories: dict[str, list[str]] = {}  # category -> [type_names]

    def register(self, node_type: Type[NodeBase], category: str = ""):
        """Register a node type."""
        self._nodes[node_type.__name__] = node_type
        if category:
            self._categories.setdefault(category, []).append(node_type.__name__)

    def unregister(self, type_name: str):
        """Remove a node type."""
        self._nodes.pop(type_name, None)
        for cat_names in self._categories.values():
            if type_name in cat_names:
                cat_names.remove(type_name)

    def get(self, type_name: str) -> Type[NodeBase] | None:
        """Get a node type by name."""
        return self._nodes.get(type_name)

    def create(self, type_name: str) -> NodeBase | None:
        """Create a node instance by type name."""
        node_type = self.get(type_name)
        if node_type:
            return node_type()
        return None

    def get_by_category(self, category: str) -> list[Type[NodeBase]]:
        """Get all node types in a category."""
        names = self._categories.get(category, [])
        return [self._nodes[n] for n in names if n in self._nodes]

    def get_all(self) -> list[Type[NodeBase]]:
        """Get all registered node types."""
        return list(self._nodes.values())

    def get_all_instantiable(self) -> list[Type[NodeBase]]:
        """Get all non-abstract node types."""
        import inspect
        return [t for t in self._nodes.values() if not inspect.isabstract(t)]

    def get_node_type(self, type_name: str) -> Type[NodeBase] | None:
        """Alias for get() — used by services/AppContext."""
        return self.get(type_name)

    def get_all_node_types(self) -> list[Type[NodeBase]]:
        """Alias for get_all_instantiable() — used by services/AppContext."""
        return self.get_all_instantiable()

    def clear(self):
        """Clear all registrations."""
        self._nodes.clear()
        self._categories.clear()


# Decorator for easy registration
def register_node(category: str = "", registry: NodeRegistry = None):
    """Decorator to register a node class in the registry.

    Usage:
        @register_node("图像预处理模块")
        class CvtColorNode(OpenCVNodeDataBase):
            ...
    """
    def decorator(cls):
        reg = registry or node_registry
        reg.register(cls, category)
        return cls
    return decorator


# Global instance
node_registry = NodeRegistry()
