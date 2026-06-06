"""Project management - multi-diagram projects with save/load/template support.

Ported from H.VisionMaster.Project (VisionProjectItemBase, IVisionProjectItem,
VisionProjectService) and H.Modules.Project (ProjectServiceBase).

Key WPF alignment:
  - DiagramDatas: ObservableCollection<IVisionDiagramData> → ProjectItem.diagrams (list)
  - SelectedDiagramData → ProjectItem.selected_diagram / selected_diagram_index
  - AddDiagram / DeleteDiagram / DuplicationDiagram / RunView commands
  - Serialization: diagrams array with DiagramData metadata (name, width, height, location)
  - Recent projects with QSettings persistence
"""

import json
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

try:
    from PyQt5.QtCore import QSettings
except ImportError:
    QSettings = None

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine
    from core.node_base import NodeBase


# =============================================================================
# DiagramData - wraps a single workflow with diagram metadata
# =============================================================================

class DiagramData:
    """A single diagram/workflow within a project.

    Mirrors WPF VisionDiagramDataBase / IVisionDiagramData.
    Each diagram has its own workflow, name, dimensions, and canvas location.
    """

    def __init__(self, name: str = "流程图 1"):
        self.id: str = str(uuid.uuid4())
        self.name: str = name
        self.description: str = ""
        self.width: float = 1000.0
        self.height: float = 1500.0
        self.location: str = "0,0"       # canvas scroll position "x,y"
        self.run_mode_result: bool | None = None
        self.workflow: "WorkflowEngine | None" = None

    @property
    def display_name(self) -> str:
        return self.name

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "width": self.width,
            "height": self.height,
            "location": self.location,
            "workflow": self.workflow.to_dict() if self.workflow else {"nodes": [], "links": []},
        }

    @classmethod
    def from_dict(cls, data: dict, node_factory) -> "DiagramData":
        from core.workflow import WorkflowEngine
        d = cls(name=data.get("name", "流程图"))
        d.id = data.get("id", str(uuid.uuid4()))
        d.description = data.get("description", "")
        d.width = data.get("width", 1000.0)
        d.height = data.get("height", 1500.0)
        d.location = data.get("location", "0,0")
        wf = WorkflowEngine(name=d.name)
        wf_data = data.get("workflow", {"nodes": [], "links": []})
        wf.from_dict(wf_data, node_factory)
        d.workflow = wf
        return d

    def duplicate(self) -> "DiagramData":
        """Create a deep copy via JSON round-trip."""
        from core.workflow import WorkflowEngine
        clone = DiagramData(name=self.name + " (副本)")
        clone.description = self.description
        clone.width = self.width
        clone.height = self.height
        clone.location = self.location
        if self.workflow:
            d = self.workflow.to_dict()
            wf = WorkflowEngine(name=clone.name)
            from core.registry import node_registry
            def factory(type_name: str):
                return node_registry.create(type_name)
            wf.from_dict(d, factory)
            clone.workflow = wf
        return clone


# =============================================================================
# ProjectItem - a project containing multiple diagrams
# =============================================================================

class ProjectItem:
    """A project containing a collection of diagrams/workflows.

    Ported from C# IVisionProjectItem / VisionProjectItemBase.
    Mirrors WPF: DiagramDatas (ObservableCollection) → diagrams (list)
                SelectedDiagramData → selected_diagram
    """

    def __init__(self, name: str = "新建项目", file_path: str = ""):
        self.name: str = name
        self.file_path: str = file_path
        self.created_at: str = datetime.now().isoformat()
        self.modified_at: str = self.created_at
        self.version: str = "2.0.0"
        self.description: str = ""
        self.author: str = ""
        # Multi-diagram support (mirrors WPF DiagramDatas)
        self.diagrams: list[DiagramData] = []
        self._selected_diagram_index: int = 0
        # Template storage (mirrors WPF DiagramTemplates)
        self._templates: list[DiagramData] = []

    # -- Diagram management (mirrors WPF commands) --

    @property
    def selected_diagram(self) -> DiagramData | None:
        if 0 <= self._selected_diagram_index < len(self.diagrams):
            return self.diagrams[self._selected_diagram_index]
        return None

    @selected_diagram.setter
    def selected_diagram(self, value: DiagramData | None):
        if value is None:
            return
        try:
            self._selected_diagram_index = self.diagrams.index(value)
        except ValueError:
            self.diagrams.append(value)
            self._selected_diagram_index = len(self.diagrams) - 1

    @property
    def selected_diagram_index(self) -> int:
        return self._selected_diagram_index

    @selected_diagram_index.setter
    def selected_diagram_index(self, value: int):
        if 0 <= value < len(self.diagrams):
            self._selected_diagram_index = value

    def add_diagram(self, name: str = None) -> DiagramData:
        """Add a new empty diagram (mirrors WPF AddDiagramCommand)."""
        from core.workflow import WorkflowEngine

        idx = len(self.diagrams) + 1
        diagram_name = name or f"流程图 {idx}"
        d = DiagramData(name=diagram_name)
        d.workflow = WorkflowEngine(name=diagram_name)
        self.diagrams.append(d)
        self._selected_diagram_index = len(self.diagrams) - 1
        return d

    def delete_diagram(self, diagram: DiagramData = None) -> bool:
        """Delete a diagram (mirrors WPF DeleteDiagramCommand)."""
        d = diagram or self.selected_diagram
        if d is None or len(self.diagrams) <= 1:
            return False
        self.diagrams.remove(d)
        if self._selected_diagram_index >= len(self.diagrams):
            self._selected_diagram_index = len(self.diagrams) - 1
        return True

    def duplicate_diagram(self, diagram: DiagramData = None) -> DiagramData | None:
        """Duplicate a diagram (mirrors WPF DuplicationDiagramCommand)."""
        src = diagram or self.selected_diagram
        if src is None:
            return None
        clone = src.duplicate()
        self.diagrams.append(clone)
        self._selected_diagram_index = len(self.diagrams) - 1
        return clone

    def switch_to_diagram(self, index: int) -> DiagramData | None:
        """Switch selected diagram by index."""
        if 0 <= index < len(self.diagrams):
            self._selected_diagram_index = index
            return self.diagrams[index]
        return None

    def switch_to_diagram_by_id(self, diagram_id: str) -> DiagramData | None:
        """Switch selected diagram by id."""
        for i, d in enumerate(self.diagrams):
            if d.id == diagram_id:
                self._selected_diagram_index = i
                return d
        return None

    # -- Template management (mirrors WPF DiagramTemplates) --

    def save_diagram_as_template(self, diagram: DiagramData = None,
                                   name: str = None) -> DiagramData:
        """Save a diagram as a reusable template (WPF SaveAsDiagramTemplateCommand)."""
        src = diagram or self.selected_diagram
        if src is None:
            raise ValueError("No diagram selected")
        template = src.duplicate()
        template.name = name or (src.name + " (模板)")
        self._templates.append(template)
        return template

    def add_diagram_from_template(self, template_index: int) -> DiagramData | None:
        """Create a new diagram from a saved template."""
        if 0 <= template_index < len(self._templates):
            clone = self._templates[template_index].duplicate()
            clone.name = clone.name.replace(" (模板)", "").replace(" (副本)", "")
            self.diagrams.append(clone)
            self._selected_diagram_index = len(self.diagrams) - 1
            return clone
        return None

    @property
    def can_delete_diagram(self) -> bool:
        """Whether the selected diagram can be deleted (mirrors WPF CanExecute)."""
        return self.selected_diagram is not None and len(self.diagrams) > 1

    def delete_selected_diagram(self) -> DiagramData | None:
        """Delete the selected diagram and return it."""
        if not self.can_delete_diagram:
            return None
        deleted = self.selected_diagram
        self.delete_diagram(deleted)
        return deleted
        return None

    @property
    def templates(self) -> list[DiagramData]:
        return list(self._templates)

    def remove_template(self, index: int) -> bool:
        if 0 <= index < len(self._templates):
            self._templates.pop(index)
            return True
        return False

    # -- Convenience properties for backward compatibility --

    @property
    def workflow(self) -> "WorkflowEngine | None":
        """Backward-compat: returns the selected diagram's workflow."""
        d = self.selected_diagram
        return d.workflow if d else None

    @workflow.setter
    def workflow(self, value: "WorkflowEngine | None"):
        if self.diagrams:
            d = self.selected_diagram
            if d:
                d.workflow = value
        elif value:
            d = DiagramData(name=self.name)
            d.workflow = value
            self.diagrams.append(d)

    @property
    def is_saved(self) -> bool:
        return bool(self.file_path) and os.path.exists(self.file_path)

    @property
    def display_name(self) -> str:
        if self.file_path:
            return os.path.splitext(os.path.basename(self.file_path))[0]
        return self.name

    @property
    def diagram_count(self) -> int:
        return len(self.diagrams)


# =============================================================================
# ProjectService - save/load with multi-diagram support
# =============================================================================

class ProjectService:
    """Service for saving/loading multi-diagram project files (.json).

    Ported from C# VisionProjectService + ProjectServiceBase.
    Supports: multi-diagram projects, recent projects persistence, templates.
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
        self._templates: list[DiagramData] = []

    # ── Template persistence (WPF: diagramtemplates.json) ──

    @property
    def _template_file(self) -> str:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "templates.json")

    def load_templates(self) -> list[DiagramData]:
        """Load templates from disk."""
        import traceback
        templates: list[DiagramData] = []
        if not os.path.exists(self._template_file):
            return templates
        with open(self._template_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        from core.registry import node_registry
        def factory(type_name: str):
            return node_registry.create(type_name)
        for td in data.get("templates", []):
            try:
                templates.append(DiagramData.from_dict(td, factory))
            except Exception:
                traceback.print_exc()
        return templates

    def save_templates(self, templates: list[DiagramData]):
        """Persist templates to disk."""
        data = {"templates": [t.to_dict() for t in templates]}
        os.makedirs(os.path.dirname(self._template_file), exist_ok=True)
        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        with open(self._template_file, "w", encoding="utf-8") as f:
            f.write(json_str)

    # -- Recent projects (QSettings persistence, mirrors WPF ProjectServiceBase) --

    @property
    def recent_projects(self) -> list[str]:
        self.cleanup_recent_projects(save=False)
        return list(self._recent_projects)

    def _load_recent_projects(self):
        if self._settings is None:
            return
        self._settings.beginGroup(self.SETTINGS_GROUP)
        raw = self._settings.value(self.RECENT_PROJECTS_KEY, [], type=list)
        self._settings.endGroup()
        if isinstance(raw, str):
            raw = [raw] if raw else []
        self._recent_projects = []
        for path in (raw or []):
            normalized = self._normalize_path(path)
            if normalized and normalized not in self._recent_projects:
                self._recent_projects.append(normalized)
        self.cleanup_recent_projects(save=True)

    def _save_recent_projects(self):
        if self._settings is None:
            return
        self._settings.beginGroup(self.SETTINGS_GROUP)
        self._settings.setValue(self.RECENT_PROJECTS_KEY, self._recent_projects)
        self._settings.endGroup()
        self._settings.sync()

    def _normalize_path(self, file_path: str) -> str:
        if not file_path:
            return ""
        return os.path.abspath(os.path.normpath(file_path))

    def add_recent(self, file_path: str):
        file_path = self._normalize_path(file_path)
        if not file_path:
            return
        if file_path in self._recent_projects:
            self._recent_projects.remove(file_path)
        self._recent_projects.insert(0, file_path)
        self._recent_projects = self._recent_projects[:self.MAX_RECENT_PROJECTS]
        self._save_recent_projects()

    def remove_recent(self, file_path: str):
        file_path = self._normalize_path(file_path)
        if file_path in self._recent_projects:
            self._recent_projects.remove(file_path)
            self._save_recent_projects()

    def clear_recent_projects(self):
        self._recent_projects.clear()
        self._save_recent_projects()

    def cleanup_recent_projects(self, save: bool = True):
        cleaned: list[str] = []
        for path in self._recent_projects:
            normalized = self._normalize_path(path)
            if normalized and os.path.exists(normalized) and normalized not in cleaned:
                cleaned.append(normalized)
        cleaned = cleaned[:self.MAX_RECENT_PROJECTS]
        changed = cleaned != self._recent_projects
        self._recent_projects = cleaned
        if changed and save:
            self._save_recent_projects()

    def get_recent_projects_info(self) -> list[dict]:
        """Return recent project info for UI display (name, path, modified time)."""
        info = []
        for path in self.recent_projects:
            name = os.path.splitext(os.path.basename(path))[0]
            mtime = ""
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
            except OSError:
                pass
            info.append({"name": name, "path": path, "modified": mtime})
        return info

    # -- Save --

    def save(self, project: ProjectItem = None) -> bool:
        project = project or self.current_project
        if project is None or not project.file_path:
            return False
        project.modified_at = datetime.now().isoformat()
        data = self._serialize(project)
        try:
            with open(project.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            self.add_recent(project.file_path)
            from core.events import EventType, event_system
            event_system.publish(EventType.PROJECT_SAVED, sender=self, project=project)
            return True
        except Exception as e:
            from core.events import EventType, event_system
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"保存失败: {e}")
            return False

    def save_as(self, project: ProjectItem, file_path: str) -> bool:
        project.file_path = file_path
        project.name = os.path.splitext(os.path.basename(file_path))[0]
        return self.save(project)

    # -- Load --

    def load(self, file_path: str) -> ProjectItem | None:
        file_path = self._normalize_path(file_path)
        if not file_path or not os.path.exists(file_path):
            self.remove_recent(file_path)
            from core.events import EventType, event_system
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"文件不存在: {file_path}")
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            project = self._deserialize(data, file_path)
            if not project.diagrams:
                project.add_diagram(project.name)
            self.current_project = project
            self.add_recent(file_path)
            from core.events import EventType, event_system
            event_system.publish(EventType.PROJECT_LOADED, sender=self, project=project)
            return project
        except Exception as e:
            from core.events import EventType, event_system
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"加载失败: {e}")
            return None

    # -- New project --

    def new_project(self, name: str = "新建项目") -> ProjectItem:
        project = ProjectItem(name=name)
        project.add_diagram(name)
        self.current_project = project
        from core.events import EventType, event_system
        event_system.publish(EventType.PROJECT_CHANGED, sender=self, project=project)
        return project

    # -- Serialization (multi-diagram format) --

    def _serialize(self, project: ProjectItem) -> dict:
        return {
            "name": project.name,
            "version": project.version,
            "description": project.description,
            "author": project.author,
            "created_at": project.created_at,
            "modified_at": project.modified_at,
            "selected_diagram_index": project.selected_diagram_index,
            "diagrams": [d.to_dict() for d in project.diagrams],
            "templates": [t.to_dict() for t in project._templates],
        }

    def _deserialize(self, data: dict, file_path: str) -> ProjectItem:
        from core.registry import node_registry
        from core.workflow import WorkflowEngine

        project = ProjectItem(
            name=data.get("name", "新建项目"),
            file_path=file_path,
        )
        project.version = data.get("version", "2.0.0")
        project.description = data.get("description", "")
        project.author = data.get("author", "")
        project.created_at = data.get("created_at", "")
        project.modified_at = data.get("modified_at", "")

        def node_factory(type_name: str) -> "NodeBase | None":
            return node_registry.create(type_name)

        # Load diagrams array (new format)
        diagrams_data = data.get("diagrams")
        if diagrams_data:
            for dd in diagrams_data:
                project.diagrams.append(DiagramData.from_dict(dd, node_factory))
            project._selected_diagram_index = data.get("selected_diagram_index", 0)
        else:
            # Backward compatibility: load single workflow
            workflow = WorkflowEngine(name=project.name)
            wf_data = data.get("workflow", {"nodes": [], "links": []})
            workflow.from_dict(wf_data, node_factory)
            d = DiagramData(name=project.name)
            d.workflow = workflow
            project.diagrams.append(d)
            project._selected_diagram_index = 0

        # Load templates
        templates_data = data.get("templates", [])
        for td in templates_data:
            project._templates.append(DiagramData.from_dict(td, node_factory))

        return project

    # -- Project CRUD (mirrors WPF ProjectServiceBase) --

    def close_project(self):
        self.current_project = None

    def delete_project_file(self, file_path: str) -> bool:
        file_path = self._normalize_path(file_path)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            self.remove_recent(file_path)
            return True
        except OSError:
            return False


# Global instance
project_service = ProjectService()
