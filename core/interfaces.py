"""Core interfaces (ABCs) — contracts between layers.

Defines abstract base classes for all key domain objects.
Services depend on these interfaces, not concrete implementations.
GUI widgets depend on interfaces + services, not on core model classes directly.

Ported from WPF: IVisionNodeData, IVisionDiagramData, ISrcFilesNodeData, etc.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.data_packet import FlowableResult


# ═══════════════════════════════════════════════════════════════════════════
# Node interfaces
# ═══════════════════════════════════════════════════════════════════════════

class INodeData(ABC):
    """Minimal node contract — all diagram nodes implement this."""

    @property
    @abstractmethod
    def node_id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def ports(self) -> list[Any]: ...

    @abstractmethod
    def to_dict(self) -> dict: ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> INodeData: ...


class IVisionNodeData(INodeData):
    """Vision processing node — produces result images."""

    @property
    @abstractmethod
    def message(self) -> str: ...

    @message.setter
    def message(self, value: str): ...

    @property
    @abstractmethod
    def result_image_source(self) -> Any: ...

    @abstractmethod
    def invoke(self, previors: Any, diagram: Any) -> FlowableResult: ...


class ISrcFilesNodeData(INodeData):
    """Node that loads data from files (images/videos)."""

    @property
    @abstractmethod
    def src_file_path(self) -> str: ...

    @src_file_path.setter
    def src_file_path(self, value: str): ...

    @property
    @abstractmethod
    def src_file_paths(self) -> list[str]: ...

    @abstractmethod
    def add_files(self, paths: list[str]): ...

    @abstractmethod
    def add_files_from_folder(self, folder: str): ...

    @abstractmethod
    def clear_files(self): ...


class IROINodeData(IVisionNodeData):
    """Node with ROI region-of-interest support."""

    @abstractmethod
    def get_active_roi_rect(self) -> tuple | None: ...


# ═══════════════════════════════════════════════════════════════════════════
# Diagram / Workflow interfaces
# ═══════════════════════════════════════════════════════════════════════════

class IDiagramData(ABC):
    """A diagram / flow page containing nodes and links."""

    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class IWorkflowEngine(ABC):
    """Executable workflow of connected nodes."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def add_node(self, node: INodeData): ...

    @abstractmethod
    def remove_node(self, node_id: str): ...

    @abstractmethod
    def get_node_by_id(self, node_id: str) -> INodeData | None: ...

    @abstractmethod
    def get_all_nodes(self) -> list[INodeData]: ...

    @abstractmethod
    def add_link(self, from_id: str, to_id: str, **kwargs) -> Any: ...

    @abstractmethod
    def remove_link(self, link_id: str): ...

    @abstractmethod
    def get_all_links(self) -> list[Any]: ...

    @abstractmethod
    def execute(self) -> FlowableResult: ...

    @abstractmethod
    def stop(self): ...


# ═══════════════════════════════════════════════════════════════════════════
# Project interface
# ═══════════════════════════════════════════════════════════════════════════

class IProjectItem(ABC):
    """A project containing multiple diagrams."""

    @property
    @abstractmethod
    def id(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def display_name(self) -> str: ...

    @property
    @abstractmethod
    def diagrams(self) -> list[IDiagramData]: ...

    @property
    @abstractmethod
    def selected_diagram(self) -> IDiagramData | None: ...

    @abstractmethod
    def add_diagram(self, name: str = "") -> IDiagramData: ...

    @abstractmethod
    def delete_diagram(self, diagram: IDiagramData) -> bool: ...


# ═══════════════════════════════════════════════════════════════════════════
# Service interfaces (bridge layer)
# ═══════════════════════════════════════════════════════════════════════════

class INodeService(ABC):
    """Service for node type discovery, creation, and lifecycle."""

    @abstractmethod
    def get_all_node_types(self) -> list[type]: ...

    @abstractmethod
    def get_node_type(self, type_name: str) -> type | None: ...

    @abstractmethod
    def create_node(self, type_name: str) -> INodeData | None: ...

    @abstractmethod
    def get_groups(self) -> list[Any]: ...


class IProjectService(ABC):
    """Service for project CRUD + serialization."""

    @property
    @abstractmethod
    def current_project(self) -> IProjectItem | None: ...

    @abstractmethod
    def new_project(self) -> IProjectItem: ...

    @abstractmethod
    def load(self, path: str) -> IProjectItem | None: ...

    @abstractmethod
    def save(self, project: IProjectItem) -> bool: ...

    @abstractmethod
    def save_as(self, project: IProjectItem, path: str) -> bool: ...

    @property
    @abstractmethod
    def recent_projects(self) -> list[str]: ...


class IThemeService(ABC):
    """Service for theme management."""

    @abstractmethod
    def toggle(self): ...

    @abstractmethod
    def get_stylesheet(self) -> str: ...

    @property
    @abstractmethod
    def is_dark(self) -> bool: ...

    @property
    @abstractmethod
    def colors(self) -> Any: ...


class IEventBus(ABC):
    """Publish-subscribe event bus for inter-component communication."""

    @abstractmethod
    def subscribe(self, event_type: Any, handler): ...

    @abstractmethod
    def unsubscribe(self, event_type: Any, handler): ...

    @abstractmethod
    def publish(self, event_type: Any, sender: Any = None, **kwargs): ...
