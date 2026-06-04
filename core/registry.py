"""
节点注册表 - 支持插件化动态加载
"""

import sys
import os
import importlib
import pkgutil
import inspect

from typing import Dict, Type, List, Optional

from .node_base import NodeBase
from .events import EventBus


class NodeRegistry:
    """
    节点注册表 - 单例模式
    管理所有可用的节点类型
    """

    _instance = None
    _nodes: Dict[str, Type[NodeBase]] = {}
    _categories: Dict[str, List[str]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._event_bus = EventBus()
        return cls._instance

    @classmethod
    def _get_event_bus(cls):
        """获取事件总线实例"""
        if cls._instance is None:
            # 创建实例
            cls()
        return cls._instance._event_bus

    @classmethod
    def register(cls, node_class: Type[NodeBase], category: str = None):
        """注册节点类"""
        node_name = node_class.__name__
        cls._nodes[node_name] = node_class

        actual_category = category or getattr(node_class, 'category', '通用')
        cls._categories.setdefault(actual_category, [])
        if node_name not in cls._categories[actual_category]:
            cls._categories[actual_category].append(node_name)

        # 安全地发送日志
        try:
            event_bus = cls._get_event_bus()
            event_bus.emit_log("INFO", f"节点已注册: {node_name} [{actual_category}]")
        except Exception:
            print(f"[INFO] 节点已注册: {node_name} [{actual_category}]")

    @classmethod
    def unregister(cls, node_name: str):
        """注销节点"""
        if node_name in cls._nodes:
            del cls._nodes[node_name]
            for category, nodes in cls._categories.items():
                if node_name in nodes:
                    nodes.remove(node_name)
                    break

    @classmethod
    def get_node_class(cls, node_type: str) -> Optional[Type[NodeBase]]:
        """获取节点类"""
        return cls._nodes.get(node_type)

    @classmethod
    def create_instance(cls, node_type: str, node_id: str = None) -> Optional[NodeBase]:
        """创建节点实例"""
        node_class = cls.get_node_class(node_type)
        if node_class is None:
            try:
                event_bus = cls._get_event_bus()
                event_bus.emit_log("ERROR", f"未知节点类型: {node_type}")
            except Exception:
                print(f"[ERROR] 未知节点类型: {node_type}")
            return None
        instance = node_class(node_id)
        instance.on_init()
        return instance

    @classmethod
    def get_all_nodes(cls) -> Dict[str, Type[NodeBase]]:
        """获取所有节点"""
        return cls._nodes.copy()

    @classmethod
    def get_categories(cls) -> Dict[str, List[str]]:
        """获取分类结构"""
        return cls._categories.copy()

    @classmethod
    def get_nodes_by_category(cls, category: str) -> List[str]:
        """获取指定分类下的节点"""
        return cls._categories.get(category, [])

    @classmethod
    def discover_nodes(cls, package_path: str = "nodes"):
        """自动发现并注册节点"""
        try:
            # 尝试导入包
            package = importlib.import_module(package_path)
            package_dir = os.path.dirname(package.__file__)

            # 遍历所有模块
            for _, module_name, _ in pkgutil.iter_modules([package_dir]):
                try:
                    module = importlib.import_module(f"{package_path}.{module_name}")
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (inspect.isclass(attr) and
                            issubclass(attr, NodeBase) and
                            attr != NodeBase):
                            cls.register(attr)
                except Exception as e:
                    # 安全地发送警告日志
                    try:
                        event_bus = cls._get_event_bus()
                        event_bus.emit_log("WARNING", f"加载模块 {module_name} 失败: {e}")
                    except Exception:
                        print(f"[WARNING] 加载模块 {module_name} 失败: {e}")
        except ImportError:
            try:
                event_bus = cls._get_event_bus()
                event_bus.emit_log("WARNING", f"包 {package_path} 不存在，跳过自动发现")
            except Exception:
                print(f"[WARNING] 包 {package_path} 不存在，跳过自动发现")

    @classmethod
    def discover_plugins(cls, plugin_dir: str = "plugins"):
        """发现插件目录中的节点"""
        if not os.path.exists(plugin_dir):
            return

        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)

        try:
            for filename in os.listdir(plugin_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    module_name = filename[:-3]
                    try:
                        module = importlib.import_module(module_name)
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (inspect.isclass(attr) and
                                issubclass(attr, NodeBase) and
                                attr != NodeBase):
                                cls.register(attr)
                    except Exception as e:
                        try:
                            event_bus = cls._get_event_bus()
                            event_bus.emit_log("WARNING", f"加载插件 {filename} 失败: {e}")
                        except Exception:
                            print(f"[WARNING] 加载插件 {filename} 失败: {e}")
        finally:
            if plugin_dir in sys.path:
                sys.path.remove(plugin_dir)

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls()
        return cls._instance