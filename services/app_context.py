"""应用程序上下文 — 中央依赖注入容器。

用单个可注入的 AppContext 替换所有全局单例（event_system、node_registry、
node_data_group_manager、project_service、service_collection、plugin_manager）。

用法：
    ctx = AppContext()
    ctx.init_defaults()                  # 使用默认值引导
    main_window = MainWindow(ctx=ctx)    # 注入到所有控件中
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.interfaces import (INodeService, IProjectService, IThemeService)

import core.events as _ev
import core.node_group as _ng
import core.registry as _reg
import core.ioc as _ioc
import core.plugin_manager as _pm
import core.project as _prj
from core.events import EventSystem
from core.registry import NodeRegistry
from core.node_group import NodeDataGroupBase, create_standard_groups
from core.ioc import ServiceCollection
from core.plugin_manager import PluginManager
from core.project import ProjectService


class AppContext:
    """所有应用程序范围服务的单一数据源。

    所有单例都保存在这里，通过构造函数注入。
    没有全局导入 — 始终通过 ctx 访问。
    """

    def __init__(self):
        self._event_bus: EventSystem | None = None
        self._node_registry: NodeRegistry | None = None
        self._node_groups: NodeDataGroupBase | None = None
        self._service_collection: ServiceCollection | None = None
        self._plugin_manager: PluginManager | None = None
        self._project_service: ProjectService | None = None
        self._node_service: "INodeService | None" = None
        self._theme_service: "IThemeService | None" = None

    # ── 引导初始化 ───────────────────────────────────────────────────

    def init_defaults(self):
        """使用默认实现初始化所有服务。

        同时也同步回模块级别的全局变量，以便迁移期间现有的导入
        （event_system / node_registry / node_data_group_manager 等）的代码继续工作。
        """
        # 事件总线
        self._event_bus = _ev.EventSystem()
        # 节点分组（工具箱左侧面板）
        self._node_groups = _ng.create_standard_groups()
        # 节点注册表
        self._node_registry = _reg.NodeRegistry()
        # IoC 服务集合（依赖注入容器）
        self._service_collection = _ioc.ServiceCollection()
        # 插件管理器（动态节点发现）
        self._plugin_manager = _pm.PluginManager()
        # 项目服务（保存/加载/最近项目）
        self._project_service = _prj.ProjectService()

        # 将节点注册表的组类更新为左侧控制面板的组类
        # 注意：NodeRegistry 通过 _categories 管理分类，不直接持有 NodeDataGroupBase 引用
        # 节点分组由 node_data_group_manager 独立管理

        # ── 同步遗留全局变量（向后兼容，计划 v3.0 移除）──
        _ev.event_system = self._event_bus
        _ng.node_data_group_manager = self._node_groups
        _reg.node_registry = self._node_registry
        _ioc.service_collection = self._service_collection
        _pm.plugin_manager = self._plugin_manager
        _prj.project_service = self._project_service

    # ── 访问器属性 ───────────────────────────────────────────────────

    @property
    def event_bus(self) -> EventSystem | None:
        """获取事件总线"""
        return self._event_bus

    @property
    def node_registry(self) -> NodeRegistry | None:
        """获取节点注册表"""
        return self._node_registry

    @property
    def node_groups(self) -> NodeDataGroupBase | None:
        """获取节点分组管理器"""
        return self._node_groups

    @property
    def service_collection(self) -> ServiceCollection | None:
        """获取 IoC 服务集合"""
        return self._service_collection

    @property
    def plugin_manager(self) -> PluginManager | None:
        """获取插件管理器"""
        return self._plugin_manager

    @property
    def project_service(self) -> ProjectService | None:
        """获取项目服务"""
        return self._project_service

    @project_service.setter
    def project_service(self, value):
        """设置项目服务（允许注入自定义实现）"""
        self._project_service = value

    @property
    def node_service(self) -> "INodeService | None":
        """获取节点服务"""
        return self._node_service

    @node_service.setter
    def node_service(self, value):
        """设置节点服务"""
        self._node_service = value

    @property
    def theme_service(self) -> "IThemeService | None":
        """获取主题服务"""
        return self._theme_service

    @theme_service.setter
    def theme_service(self, value):
        """设置主题服务"""
        self._theme_service = value

    # ── 内省 ─────────────────────────────────────────────────────────

    def list_services(self) -> list[str]:
        """返回所有非空服务的名称列表。"""
        names = []
        if self._event_bus is not None:
            names.append('event_bus')
        if self._node_registry is not None:
            names.append('node_registry')
        if self._node_groups is not None:
            names.append('node_groups')
        if self._service_collection is not None:
            names.append('service_collection')
        if self._plugin_manager is not None:
            names.append('plugin_manager')
        if self._project_service is not None:
            names.append('project_service')
        if self._node_service is not None:
            names.append('node_service')
        if self._theme_service is not None:
            names.append('theme_service')
        return sorted(names)

    def is_ready(self) -> bool:
        """检查 6 个核心服务是否全部初始化。"""
        return all([
            self._event_bus is not None,
            self._node_registry is not None,
            self._node_groups is not None,
            self._service_collection is not None,
            self._plugin_manager is not None,
            self._project_service is not None,
        ])

    # ── 测试支持 ─────────────────────────────────────────────────────

    def reset(self):
        """重置所有服务为 None（用于测试隔离）。

        调用后需要重新调用 init_defaults() 来初始化。
        遗留全局变量保持最后一次同步的值，直到重新初始化。
        """
        self._event_bus = None
        self._node_registry = None
        self._node_groups = None
        self._service_collection = None
        self._plugin_manager = None
        self._project_service = None
        self._node_service = None
        self._theme_service = None


# 全局实例（软迁移 — 模块仍可通过此变量访问）
# 新代码应接受 ctx 作为构造函数参数，而不是直接调用此函数。
_app_context: AppContext | None = None


def get_app_context() -> AppContext:
    """获取或创建全局 AppContext。

    优先使用构造函数注入而不是直接调用此函数。

    返回：
        AppContext 对象
    """
    global _app_context
    if _app_context is None:
        _app_context = AppContext()
        _app_context.init_defaults()
    return _app_context


def set_app_context(ctx: AppContext):
    """替换全局 AppContext（用于测试）

    参数：
        ctx: 新的应用程序上下文对象
    """
    global _app_context
    _app_context = ctx
