"""节点注册表 - 节点类型的快速查找和实例化。"""

from typing import Type, Callable

from core.node_base import NodeBase


class NodeRegistry:
    """节点类型的中央注册表。

    将节点类型名称映射到节点类，用于实例化。
    """

    def __init__(self):
        # 节点字典：键为节点类型名称，值为节点类
        self._nodes: dict[str, Type[NodeBase]] = {}
        # 分类字典：键为分类名称，值为该分类下的节点类型名称列表
        self._categories: dict[str, list[str]] = {}

    def register(self, node_type: Type[NodeBase], category: str = ""):
        """注册一个节点类型。"""
        # 将节点类名注册到节点字典
        self._nodes[node_type.__name__] = node_type
        # 如果提供了分类信息，同时注册到分类字典
        if category:
            self._categories.setdefault(category, []).append(node_type.__name__)

    def unregister(self, type_name: str):
        """移除一个节点类型。"""
        # 从节点字典中移除
        self._nodes.pop(type_name, None)
        # 从所有分类中移除
        for cat_names in self._categories.values():
            if type_name in cat_names:
                cat_names.remove(type_name)

    def get(self, type_name: str) -> Type[NodeBase] | None:
        """根据节点类型名称获取节点类。"""
        return self._nodes.get(type_name)

    def create(self, type_name: str) -> NodeBase | None:
        """根据节点类型名称创建节点实例。"""
        node_type = self.get(type_name)
        if node_type:
            return node_type()
        return None

    def get_by_category(self, category: str) -> list[Type[NodeBase]]:
        """获取某个分类下的所有节点类型。"""
        names = self._categories.get(category, [])
        # 返回节点类列表，过滤掉可能不存在的节点
        return [self._nodes[n] for n in names if n in self._nodes]

    def get_all(self) -> list[Type[NodeBase]]:
        """获取所有已注册的节点类型。"""
        return list(self._nodes.values())

    def get_all_instantiable(self) -> list[Type[NodeBase]]:
        """获取所有非抽象的节点类型（可实例化）。"""
        import inspect
        return [t for t in self._nodes.values() if not getattr(t, '__abstract__', False) and not inspect.isabstract(t)]

    def get_node_type(self, type_name: str) -> Type[NodeBase] | None:
        """get() 的别名 — 供 services/AppContext 使用。"""
        return self.get(type_name)

    def get_all_node_types(self) -> list[Type[NodeBase]]:
        """get_all_instantiable() 的别名 — 供 services/AppContext 使用。"""
        return self.get_all_instantiable()

    def clear(self):
        """清空所有注册信息。"""
        self._nodes.clear()
        self._categories.clear()


# 用于便捷注册的装饰器
def register_node(category: str = "", registry: NodeRegistry = None):
    """在注册表中注册节点类的装饰器。

    用法：
        @register_node("图像预处理模块")
        class CvtColorNode(OpenCVNodeDataBase):
            ...
    """
    def decorator(cls):
        # 使用指定的注册表或全局注册表
        reg = registry or node_registry
        reg.register(cls, category)
        return cls
    return decorator


# 全局实例
node_registry = NodeRegistry()