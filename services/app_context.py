"""应用程序上下文 — 中央依赖注入容器。

用单个可注入的 AppContext 替换所有全局单例（event_system、node_registry、
node_data_group_manager、project_service、theme_manager）。

用法：
    ctx = AppContext()
    ctx.init_defaults()                  # 使用默认值引导
    main_window = MainWindow(ctx=ctx)    # 注入到所有控件中
"""

from __future__ import annotations
# from typing import TYPE_CHECKING

# if TYPE_CHECKING:
import core.events as _ev                     # 导入事件模块
import core.node_group as _ng                 # 导入节点分组模块
import core.registry as _reg                  # 导入节点注册模块
from core.interfaces import (INodeService, IProjectService,
                              IThemeService)  # 导入服务接口
from core.events import EventSystem            # 导入事件系统类
from core.registry import NodeRegistry         # 导入节点注册表类
from core.node_group import NodeDataGroupBase, create_standard_groups  # 导入节点分组基类和创建标准分组函数


class AppContext:
    """所有应用程序范围服务的单一数据源。

    所有单例都保存在这里，通过构造函数注入。
    没有全局导入 — 始终通过 ctx 访问。
    """

    def __init__(self):
        """初始化应用程序上下文"""
        # 事务总线（事件系统），初始为None
        self._event_bus: EventSystem | None = None
        # 节点注册表，初始为None
        self._node_registry: NodeRegistry | None = None
        # 节点分组管理器，初始为None
        self._node_groups: NodeDataGroupBase | None = None
        # 项目服务，初始为None
        self._project_service: IProjectService | None = None
        # 节点服务，初始为None
        self._node_service: INodeService | None = None
        # 主题服务，初始为None
        self._theme_service: IThemeService | None = None

    # ── 引导初始化 ───────────────────────────────────────────────────

    def init_defaults(self):
        """使用默认实现初始化所有服务。

        同时也同步回模块级别的全局变量，以便迁移期间现有的导入
        node_registry / node_data_group_manager / event_system 的代码继续工作。
        """
        # 导入事件模块
        # import core.events as _ev
        # 导入节点分组模块
        # import core.node_group as _ng
        # 导入节点注册模块
        # import core.registry as _reg

        # 初始化事务总线
        self._event_bus = _ev.EventSystem()
        # 初始化节点分组，左侧节点控制面板
        self._node_groups = _ng.create_standard_groups()
        # 初始化节点注册表
        self._node_registry = _reg.NodeRegistry()

        # 将节点注册表的组类更新为左侧控制面板的组类
        self._node_registry._groups = self._node_groups

        # ── 同步遗留全局变量（向后兼容）──
        # 将事件系统同步到事件模块的全局变量
        _ev.event_system = self._event_bus
        # 将节点分组同步到节点分组模块的全局变量
        _ng.node_data_group_manager = self._node_groups
        # 将节点注册表同步到节点注册模块的全局变量
        _reg.node_registry = self._node_registry

    # ── 访问器属性 ───────────────────────────────────────────────────

    @property
    def event_bus(self):
        """获取事件总线

        返回：
            事件系统对象
        """
        return self._event_bus

    @property
    def node_registry(self):
        """获取节点注册表

        返回：
            节点注册表对象
        """
        return self._node_registry

    @property
    def node_groups(self):
        """获取节点分组管理器

        返回：
            节点分组管理器对象
        """
        return self._node_groups

    @property
    def project_service(self) -> IProjectService | None:
        """获取项目服务

        返回：
            项目服务对象或None
        """
        return self._project_service

    @project_service.setter
    def project_service(self, value):
        """设置项目服务

        参数：
            value: 项目服务对象
        """
        self._project_service = value

    @property
    def node_service(self) -> INodeService | None:
        """获取节点服务

        返回：
            节点服务对象或None
        """
        return self._node_service

    @node_service.setter
    def node_service(self, value):
        """设置节点服务

        参数：
            value: 节点服务对象
        """
        self._node_service = value

    @property
    def theme_service(self) -> IThemeService | None:
        """获取主题服务

        返回：
            主题服务对象或None
        """
        return self._theme_service

    @theme_service.setter
    def theme_service(self, value):
        """设置主题服务

        参数：
            value: 主题服务对象
        """
        self._theme_service = value


# 全局实例（软迁移 — 模块仍可通过此变量访问）
# 新代码应接受 ctx 作为构造函数参数，而不是直接调用此函数。
_app_context: AppContext | None = None


def get_app_context() -> AppContext:
    """获取或创建全局 AppContext。

    优先使用构造函数注入而不是直接调用此函数。

    返回：
        AppContext 对象
    """
    # 声明全局变量
    global _app_context
    # 如果全局上下文为空
    if _app_context is None:
        # 创建新的应用程序上下文
        _app_context = AppContext()
        # 初始化默认服务
        _app_context.init_defaults()
    # 返回全局上下文
    return _app_context


def set_app_context(ctx: AppContext):
    """替换全局 AppContext（用于测试）

    参数：
        ctx: 新的应用程序上下文对象
    """
    # 声明全局变量
    global _app_context
    # 设置全局上下文
    _app_context = ctx