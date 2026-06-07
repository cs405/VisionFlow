"""Plugin manager - discovers and loads node modules dynamically.
"""

import importlib
import inspect
import os
import pkgutil
from typing import Type

from core.node_base import NodeBase
from core.node_group import node_data_group_manager, NodeGroup
from core.registry import node_registry


class PluginManager:
    """Discovers and loads node implementations from the nodes/ package.

    Each node module registers itself by having classes that inherit from NodeBase
    and define a __group__ class attribute.
    """

    def __init__(self):
        self._loaded_modules: list[str] = []

    def discover_nodes_package(self, package_path: str = "nodes"):
        """Discover all node modules in the nodes/ package.

        Scans subdirectories and imports all .py files.
        Each module should contain NodeBase subclasses with __group__ defined.
        """
        try:
            package = importlib.import_module(package_path)
            package_dir = os.path.dirname(package.__file__)

            for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
                full_name = f"{package_path}.{module_name}"
                try:
                    if is_pkg:
                        self._discover_subpackage(full_name)
                    else:
                        self._load_module(full_name)
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to load node module {full_name}: {e}")

        except ModuleNotFoundError:
            pass  # nodes package not created yet

    def _discover_subpackage(self, package_path: str):
        """Discover nodes in a subpackage (e.g., nodes.preprocessings)."""
        try:
            package = importlib.import_module(package_path)
            package_dir = os.path.dirname(package.__file__)

            for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
                full_name = f"{package_path}.{module_name}"
                if not is_pkg:
                    self._load_module(full_name)
        except Exception as e:
            import logging
            logging.warning(f"Failed to discover subpackage {package_path}: {e}")

    def _load_module(self, module_name: str):
        """Load a single module and register its node classes."""
        if module_name in self._loaded_modules:
            return
        try:
            module = importlib.import_module(module_name)
            self._loaded_modules.append(module_name)
            self._register_module_classes(module)
        except Exception as e:
            import logging
            logging.warning(f"Failed to load module {module_name}: {e}")

    def _register_module_classes(self, module):
        """Register all NodeBase subclasses found in a module."""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name.startswith("_"):
                continue
            if not issubclass(obj, NodeBase) or obj is NodeBase:
                continue
            if getattr(obj, '__abstract__', False) or inspect.isabstract(obj):
                continue

            group_name = getattr(obj, '__group__', None)
            if group_name:
                node_data_group_manager.register_node(obj, group_name)

            category = getattr(obj, '__category__', None) or group_name or ""
            node_registry.register(obj, category)

    def load_from_path(self, path: str):
        """Load a single Python file as a node module."""
        import importlib.util
        module_name = os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._register_module_classes(module)

    def get_node_info(self) -> list[dict]:
        """Get information about all discovered nodes for the toolbox UI."""
        info = []
        for group in node_data_group_manager.get_all_groups():
            for node_type in group.node_types:
                info.append({
                    "type": node_type.__name__,
                    "name": getattr(node_type, 'display_name', node_type.__name__),
                    "group": group.name,
                    "description": group.description,
                    "icon": group.icon,
                    "order": getattr(node_type, 'order', group.order),
                })
        return sorted(info, key=lambda x: x["order"])


# Global instance
plugin_manager = PluginManager()
