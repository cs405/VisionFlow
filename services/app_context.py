"""Application context — centralized DI container.

Replaces all global singletons (event_system, node_registry,
node_data_group_manager, project_service, theme_manager) with
a single injectable AppContext.

Usage:
    ctx = AppContext()
    ctx.init_defaults()                  # bootstrap with defaults
    main_window = MainWindow(ctx=ctx)    # inject into all widgets
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.interfaces import (INodeService, IProjectService,
                                  IThemeService, IEventBus)
    from core.events import EventSystem
    from core.registry import NodeRegistry
    from core.node_group import NodeDataGroupBase


class AppContext:
    """Single source of truth for all application-wide services.

    All singletons are held here and injected via constructor.
    Nothing is imported as a global — always reachable via ctx.
    """

    def __init__(self):
        self._event_bus: EventSystem | None = None
        self._node_registry: NodeRegistry | None = None
        self._node_groups: NodeDataGroupBase | None = None
        self._project_service: IProjectService | None = None
        self._node_service: INodeService | None = None
        self._theme_service: IThemeService | None = None

    # ── Bootstrap ───────────────────────────────────────────────────

    def init_defaults(self):
        """Initialize all services with default implementations.

        Also syncs back to legacy module-level globals so existing code
        that imports node_registry / node_data_group_manager / event_system
        continues to work during the migration period.
        """
        import core.events as _ev
        import core.node_group as _ng
        import core.registry as _reg

        self._event_bus = _ev.EventSystem()
        self._node_groups = _ng.create_standard_groups()
        self._node_registry = _reg.NodeRegistry()

        # Wire registry to groups
        self._node_registry._groups = self._node_groups

        # ── Sync legacy globals (backward compat) ──
        _ev.event_system = self._event_bus
        _ng.node_data_group_manager = self._node_groups
        _reg.node_registry = self._node_registry

    # ── Accessors ───────────────────────────────────────────────────

    @property
    def event_bus(self):
        return self._event_bus

    @property
    def node_registry(self):
        return self._node_registry

    @property
    def node_groups(self):
        return self._node_groups

    @property
    def project_service(self) -> IProjectService | None:
        return self._project_service

    @project_service.setter
    def project_service(self, value):
        self._project_service = value

    @property
    def node_service(self) -> INodeService | None:
        return self._node_service

    @node_service.setter
    def node_service(self, value):
        self._node_service = value

    @property
    def theme_service(self) -> IThemeService | None:
        return self._theme_service

    @theme_service.setter
    def theme_service(self, value):
        self._theme_service = value


# Global instance (soft migration — modules can still access via this)
# New code should accept ctx as constructor parameter instead.
_app_context: AppContext | None = None


def get_app_context() -> AppContext:
    """Get or create the global AppContext.

    Prefer constructor injection over calling this directly.
    """
    global _app_context
    if _app_context is None:
        _app_context = AppContext()
        _app_context.init_defaults()
    return _app_context


def set_app_context(ctx: AppContext):
    """Replace the global AppContext (for testing)."""
    global _app_context
    _app_context = ctx
