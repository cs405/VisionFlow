"""节点服务 — 节点类型发现和创建。

将 NodeRegistry + NodeDataGroupBase 包装在干净的接口后面。
依赖 AppContext 获取注册表和分组管理器引用。
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from core.interfaces import INodeData, INodeService

if TYPE_CHECKING:
    from services.app_context import AppContext


class NodeService(INodeService):
    """使用 AppContext 中的注册表和分组管理器的默认节点服务。"""

    def __init__(self, ctx: AppContext = None):
        """初始化节点服务

        参数：
            ctx: 应用程序上下文对象
        """
        # 如果未提供上下文
        if ctx is None:
            # 从 services.app_context 模块获取全局应用上下文
            from services.app_context import get_app_context
            ctx = get_app_context()
        # 保存上下文引用
        self._ctx = ctx

    @property
    def _registry(self):
        """获取节点注册表（私有属性）

        返回：
            节点注册表对象
        """
        return self._ctx.node_registry

    @property
    def _groups(self):
        """获取节点分组管理器（私有属性）

        返回：
            节点分组管理器对象
        """
        return self._ctx.node_groups

    def get_all_node_types(self) -> list[type]:
        """获取所有已注册的节点类型

        返回：
            节点类型列表
        """
        # 如果节点注册表存在，返回所有节点类型；否则返回空列表
        return self._registry.get_all_node_types() if self._registry else []

    def get_node_type(self, type_name: str) -> type | None:
        """根据类型名称获取节点类型

        参数：
            type_name: 节点类型名称

        返回：
            节点类型或None
        """
        # 如果节点注册表存在，返回指定类型的节点；否则返回None
        return self._registry.get_node_type(type_name) if self._registry else None

    def create_node(self, type_name: str) -> INodeData | None:
        """根据类型名称创建节点实例

        参数：
            type_name: 节点类型名称

        返回：
            节点实例或None
        """
        # 如果节点注册表存在，创建并返回节点实例；否则返回None
        return self._registry.create(type_name) if self._registry else None

    def get_groups(self) -> list:
        """获取所有节点分组

        返回：
            节点分组列表
        """
        # 如果分组管理器存在，返回所有分组；否则返回空列表
        return self._groups.get_all_groups() if self._groups else []

    def discover_module(self, module, group_prefix: str = ""):
        """发现模块中的 NodeBase 子类并注册

        参数：
            module: Python 模块对象
            group_prefix: 分组前缀
        """
        # 如果分组管理器存在
        if self._groups:
            # 调用分组管理器的 discover_module 方法发现并注册节点
            self._groups.discover_module(module, group_prefix)