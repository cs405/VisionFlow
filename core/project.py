"""Project management - save/load/export workflow projects.

Ported from H.VisionMaster.Project + VisionProjectService.
Uses JSON for serialization (replacing Newtonsoft.Json).
"""

import json
import os
from datetime import datetime

try:
    from PyQt5.QtCore import QSettings
except ImportError:  # CLI/tests can still run without Qt available
    QSettings = None

from core.workflow import WorkflowEngine
from core.node_base import NodeBase
from core.registry import node_registry
from core.events import EventType, event_system


class ProjectItem:
    """A project file containing a workflow.

    Ported from C# IVisionProjectItem / VisionProjectItemBase.
    """

    def __init__(self, name: str = "新建项目", file_path: str = ""):
        self.name = name
        self.file_path = file_path
        self.created_at = datetime.now().isoformat()
        self.modified_at = self.created_at
        self.version = "2.0.0"
        self.description = ""
        self.author = ""
        self.workflow: WorkflowEngine | None = None

    @property
    def is_saved(self) -> bool:
        return bool(self.file_path) and os.path.exists(self.file_path)

    @property
    def display_name(self) -> str:
        if self.file_path:
            return os.path.splitext(os.path.basename(self.file_path))[0]
        return self.name


class ProjectService:
    """Service for saving/loading project files (.json).

    Ported from C# VisionProjectService using Newtonsoft.Json.
    """

    FILE_EXTENSION = ".json"
    FILE_FILTER = "VisionFlow 项目文件 (*.json)"
    SETTINGS_GROUP = "Project"
    RECENT_PROJECTS_KEY = "recentProjects"
    MAX_RECENT_PROJECTS = 10

    def __init__(self):
        self.current_project: ProjectItem | None = None
        self._recent_projects: list[str] = []
        self._settings = QSettings() if QSettings is not None else None
        self._load_recent_projects()

    # -- Recent projects --

    @property
    def recent_projects(self) -> list[str]:
        self.cleanup_recent_projects(save=False)
        return list(self._recent_projects)

    def _load_recent_projects(self):
        """Load recent project list from persistent settings."""
        if self._settings is None:
            return

        self._settings.beginGroup(self.SETTINGS_GROUP)
        raw_value = self._settings.value(self.RECENT_PROJECTS_KEY, [], type=list)
        self._settings.endGroup()

        if isinstance(raw_value, str):
            raw_value = [raw_value] if raw_value else []

        self._recent_projects = []
        for path in raw_value or []:
            normalized = self._normalize_project_path(path)
            if normalized and normalized not in self._recent_projects:
                self._recent_projects.append(normalized)

        self.cleanup_recent_projects(save=True)

    def _save_recent_projects(self):
        """Persist recent project list to QSettings."""
        if self._settings is None:
            return

        self._settings.beginGroup(self.SETTINGS_GROUP)
        self._settings.setValue(self.RECENT_PROJECTS_KEY, self._recent_projects)
        self._settings.endGroup()
        self._settings.sync()

    def _normalize_project_path(self, file_path: str) -> str:
        if not file_path:
            return ""
        return os.path.abspath(os.path.normpath(file_path))

    def add_recent(self, file_path: str):
        """Add a project to the recent list."""
        file_path = self._normalize_project_path(file_path)
        if not file_path:
            return
        if file_path in self._recent_projects:
            self._recent_projects.remove(file_path)
        self._recent_projects.insert(0, file_path)
        self._recent_projects = self._recent_projects[:self.MAX_RECENT_PROJECTS]
        self._save_recent_projects()

    def remove_recent(self, file_path: str):
        """Remove a project path from the recent list."""
        file_path = self._normalize_project_path(file_path)
        if file_path in self._recent_projects:
            self._recent_projects.remove(file_path)
            self._save_recent_projects()

    def clear_recent_projects(self):
        """Clear all recent project entries."""
        self._recent_projects.clear()
        self._save_recent_projects()

    def cleanup_recent_projects(self, save: bool = True):
        """Remove invalid or duplicate entries from the recent list."""
        cleaned: list[str] = []
        for path in self._recent_projects:
            normalized = self._normalize_project_path(path)
            if normalized and os.path.exists(normalized) and normalized not in cleaned:
                cleaned.append(normalized)

        cleaned = cleaned[:self.MAX_RECENT_PROJECTS]
        changed = cleaned != self._recent_projects
        self._recent_projects = cleaned
        if changed and save:
            self._save_recent_projects()

    # -- Save --

    def save(self, project: ProjectItem = None) -> bool:
        """Save a project to its file path."""
        project = project or self.current_project
        if project is None or not project.file_path:
            return False

        project.modified_at = datetime.now().isoformat()
        data = self._serialize(project)
        try:
            with open(project.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            self.add_recent(project.file_path)
            event_system.publish(EventType.PROJECT_SAVED, sender=self, project=project)
            return True
        except Exception as e:
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"保存失败: {e}")
            return False

    def save_as(self, project: ProjectItem, file_path: str) -> bool:
        """Save a project to a new file path."""
        project.file_path = file_path
        project.name = os.path.splitext(os.path.basename(file_path))[0]
        return self.save(project)

    # -- Load --

    def load(self, file_path: str) -> ProjectItem | None:
        """Load a project from a file."""
        file_path = self._normalize_project_path(file_path)
        if not file_path or not os.path.exists(file_path):
            self.remove_recent(file_path)
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"加载失败: 文件不存在 - {file_path}")
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            project = self._deserialize(data, file_path)
            self.current_project = project
            self.add_recent(file_path)
            event_system.publish(EventType.PROJECT_LOADED, sender=self, project=project)
            return project
        except Exception as e:
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"加载失败: {e}")
            return None

    # -- New project --

    def new_project(self, name: str = "新建项目") -> ProjectItem:
        """Create a new empty project."""
        project = ProjectItem(name=name)
        project.workflow = WorkflowEngine(name=name)
        self.current_project = project
        event_system.publish(EventType.PROJECT_CHANGED, sender=self, project=project)
        return project

    # -- Serialization --

    def _serialize(self, project: ProjectItem) -> dict:
        """Serialize a project to a JSON-compatible dict."""
        return {
            "name": project.name,
            "version": project.version,
            "description": project.description,
            "author": project.author,
            "created_at": project.created_at,
            "modified_at": project.modified_at,
            "workflow": project.workflow.to_dict() if project.workflow else {"nodes": [], "links": []},
        }

    def _deserialize(self, data: dict, file_path: str) -> ProjectItem:
        """Deserialize a project from a JSON dict."""
        project = ProjectItem(
            name=data.get("name", "新建项目"),
            file_path=file_path,
        )
        project.version = data.get("version", "2.0.0")
        project.description = data.get("description", "")
        project.author = data.get("author", "")
        project.created_at = data.get("created_at", "")
        project.modified_at = data.get("modified_at", "")

        # Create workflow
        workflow = WorkflowEngine(name=project.name)
        workflow_data = data.get("workflow", {"nodes": [], "links": []})

        def node_factory(type_name: str) -> NodeBase | None:
            return node_registry.create(type_name)

        workflow.from_dict(workflow_data, node_factory)
        project.workflow = workflow
        return project


# Global instance
project_service = ProjectService()
