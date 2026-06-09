"""项目管理 - 支持保存/加载/模板的多图项目。

  - DiagramDatas: ObservableCollection<IVisionDiagramData> → ProjectItem.diagrams (列表)
  - SelectedDiagramData → ProjectItem.selected_diagram / selected_diagram_index
  - AddDiagram / DeleteDiagram / DuplicationDiagram / RunView 命令
  - 序列化：带 DiagramData 元数据（名称、宽、高、位置）的 diagrams 数组
  - 使用 QSettings 持久化的最近项目列表
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
# DiagramData - 包装带图表元数据的单个工作流
# =============================================================================

class DiagramData:
    """项目中的单个图表/工作流。

    每个图表都有自己的工作流、名称、尺寸和画布位置。
    """

    def __init__(self, name: str = "流程图 1"):
        # 图表唯一标识符
        self.id: str = str(uuid.uuid4())
        # 图表名称
        self.name: str = name
        # 图表描述
        self.description: str = ""
        # 图表宽度
        self.width: float = 1000.0
        # 图表高度
        self.height: float = 1500.0
        # 画布滚动位置 "x,y"
        self.location: str = "0,0"
        # 运行模式结果
        self.run_mode_result: bool | None = None
        # 关联的工作流引擎
        self.workflow: "WorkflowEngine | None" = None

    @property
    def display_name(self) -> str:
        """获取显示名称"""
        return self.name

    def to_dict(self) -> dict:
        """序列化为字典"""
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
        """从字典反序列化"""
        from core.workflow import WorkflowEngine
        # 创建图表对象
        d = cls(name=data.get("name", "流程图"))
        # 恢复基本属性
        d.id = data.get("id", str(uuid.uuid4()))
        d.description = data.get("description", "")
        d.width = data.get("width", 1000.0)
        d.height = data.get("height", 1500.0)
        d.location = data.get("location", "0,0")
        # 创建并恢复工作流
        wf = WorkflowEngine(name=d.name)
        wf_data = data.get("workflow", {"nodes": [], "links": []})
        wf.from_dict(wf_data, node_factory)
        d.workflow = wf
        return d

    def duplicate(self) -> "DiagramData":
        """通过 JSON 往返创建深拷贝"""
        from core.workflow import WorkflowEngine
        # 创建克隆图表
        clone = DiagramData(name=self.name + " (副本)")
        # 复制属性
        clone.description = self.description
        clone.width = self.width
        clone.height = self.height
        clone.location = self.location
        # 复制工作流
        if self.workflow:
            d = self.workflow.to_dict()
            wf = WorkflowEngine(name=clone.name)
            from core.registry import node_registry
            # 定义节点工厂函数
            def factory(type_name: str):
                return node_registry.create(type_name)
            wf.from_dict(d, factory)
            clone.workflow = wf
        return clone


# =============================================================================
# ProjectItem - 包含多个图表的项目
# =============================================================================

class ProjectItem:
    """包含多个图表/工作流集合的项目。"""

    def __init__(self, name: str = "新建项目", file_path: str = ""):
        # 项目名称
        self.name: str = name
        # 项目文件路径
        self.file_path: str = file_path
        # 创建时间
        self.created_at: str = datetime.now().isoformat()
        # 修改时间
        self.modified_at: str = self.created_at
        # 项目版本
        self.version: str = "2.0.0"
        # 项目描述
        self.description: str = ""
        # 作者
        self.author: str = ""
        # 多图支持：图表列表
        self.diagrams: list[DiagramData] = []
        # 当前选中的图表索引
        self._selected_diagram_index: int = 0
        # 模板存储
        self._templates: list[DiagramData] = []

    # -- 图表管理 --

    @property
    def selected_diagram(self) -> DiagramData | None:
        """获取当前选中的图表"""
        if 0 <= self._selected_diagram_index < len(self.diagrams):
            return self.diagrams[self._selected_diagram_index]
        return None

    @selected_diagram.setter
    def selected_diagram(self, value: DiagramData | None):
        """设置当前选中的图表"""
        if value is None:
            return
        try:
            self._selected_diagram_index = self.diagrams.index(value)
        except ValueError:
            # 如果图表不在列表中，添加它
            self.diagrams.append(value)
            self._selected_diagram_index = len(self.diagrams) - 1

    @property
    def selected_diagram_index(self) -> int:
        """获取选中图表索引"""
        return self._selected_diagram_index

    @selected_diagram_index.setter
    def selected_diagram_index(self, value: int):
        """设置选中图表索引"""
        if 0 <= value < len(self.diagrams):
            self._selected_diagram_index = value

    def add_diagram(self, name: str = None) -> DiagramData:
        """添加一个新的空图表"""
        from core.workflow import WorkflowEngine

        # 生成图表名称
        idx = len(self.diagrams) + 1
        diagram_name = name or f"流程图 {idx}"
        # 创建图表
        d = DiagramData(name=diagram_name)
        d.workflow = WorkflowEngine(name=diagram_name)
        # 添加到列表
        self.diagrams.append(d)
        self._selected_diagram_index = len(self.diagrams) - 1
        return d

    def delete_diagram(self, diagram: DiagramData = None) -> bool:
        """删除一个图表"""
        d = diagram or self.selected_diagram
        # 不能删除最后一个图表
        if d is None or len(self.diagrams) <= 1:
            return False
        self.diagrams.remove(d)
        # 调整选中索引
        if self._selected_diagram_index >= len(self.diagrams):
            self._selected_diagram_index = len(self.diagrams) - 1
        return True

    def duplicate_diagram(self, diagram: DiagramData = None) -> DiagramData | None:
        """复制一个图表"""
        src = diagram or self.selected_diagram
        if src is None:
            return None
        # 创建副本
        clone = src.duplicate()
        self.diagrams.append(clone)
        self._selected_diagram_index = len(self.diagrams) - 1
        return clone

    def switch_to_diagram(self, index: int) -> DiagramData | None:
        """按索引切换选中图表"""
        if 0 <= index < len(self.diagrams):
            self._selected_diagram_index = index
            return self.diagrams[index]
        return None

    def switch_to_diagram_by_id(self, diagram_id: str) -> DiagramData | None:
        """按ID切换选中图表"""
        for i, d in enumerate(self.diagrams):
            if d.id == diagram_id:
                self._selected_diagram_index = i
                return d
        return None

    # -- 模板管理 --

    def save_diagram_as_template(self, diagram: DiagramData = None,
                                   name: str = None) -> DiagramData:
        """将图表保存为可重用的模板"""
        src = diagram or self.selected_diagram
        if src is None:
            raise ValueError("未选中图表")
        # 创建模板副本
        template = src.duplicate()
        template.name = name or (src.name + " (模板)")
        self._templates.append(template)
        return template

    def add_diagram_from_template(self, template_index: int) -> DiagramData | None:
        """从保存的模板创建新图表"""
        if 0 <= template_index < len(self._templates):
            clone = self._templates[template_index].duplicate()
            # 清理名称中的模板标记
            clone.name = clone.name.replace(" (模板)", "").replace(" (副本)", "")
            self.diagrams.append(clone)
            self._selected_diagram_index = len(self.diagrams) - 1
            return clone
        return None

    @property
    def can_delete_diagram(self) -> bool:
        """判断当前图表是否可以删除"""
        return self.selected_diagram is not None and len(self.diagrams) > 1

    def delete_selected_diagram(self) -> DiagramData | None:
        """删除当前选中的图表并返回它"""
        if not self.can_delete_diagram:
            return None
        deleted = self.selected_diagram
        self.delete_diagram(deleted)
        return deleted

    @property
    def templates(self) -> list[DiagramData]:
        """获取模板列表"""
        return list(self._templates)

    def remove_template(self, index: int) -> bool:
        """删除指定索引的模板"""
        if 0 <= index < len(self._templates):
            self._templates.pop(index)
            return True
        return False

    # -- 向后兼容的属性 --

    @property
    def workflow(self) -> "WorkflowEngine | None":
        """向后兼容：返回当前图表的工作流"""
        d = self.selected_diagram
        return d.workflow if d else None

    @workflow.setter
    def workflow(self, value: "WorkflowEngine | None"):
        """向后兼容：设置当前图表的工作流"""
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
        """判断项目是否已保存到磁盘"""
        return bool(self.file_path) and os.path.exists(self.file_path)

    @property
    def display_name(self) -> str:
        """获取显示名称（不含扩展名）"""
        if self.file_path:
            return os.path.splitext(os.path.basename(self.file_path))[0]
        return self.name

    @property
    def diagram_count(self) -> int:
        """获取图表数量"""
        return len(self.diagrams)


# =============================================================================
# ProjectService - 支持多图项目的保存/加载服务
# =============================================================================

class ProjectService:
    """
    用于保存/加载多图项目文件（.json）的服务
    支持：多图项目、最近项目持久化、模板
    """

    FILE_EXTENSION = ".json"
    FILE_FILTER = "VisionFlow 项目文件 (*.json)"
    SETTINGS_GROUP = "Project"
    RECENT_PROJECTS_KEY = "recentProjects"
    MAX_RECENT_PROJECTS = 10

    def __init__(self):
        # 当前打开的项目
        self.current_project: ProjectItem | None = None
        # 最近项目列表
        self._recent_projects: list[str] = []
        # QSettings 实例
        self._settings = QSettings() if QSettings is not None else None
        # 加载最近项目列表
        self._load_recent_projects()
        # 模板列表
        self._templates: list[DiagramData] = []

    # ── 模板持久化 ──

    @property
    def _template_file(self) -> str:
        """获取模板文件路径"""
        return os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "templates.json")

    def load_templates(self) -> list[DiagramData]:
        """从磁盘加载模板"""
        import traceback
        templates: list[DiagramData] = []
        # 模板文件不存在时返回空列表
        if not os.path.exists(self._template_file):
            return templates
        with open(self._template_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        from core.registry import node_registry
        # 节点工厂函数
        def factory(type_name: str):
            return node_registry.create(type_name)
        # 反序列化每个模板
        for td in data.get("templates", []):
            try:
                templates.append(DiagramData.from_dict(td, factory))
            except Exception:
                traceback.print_exc()
        return templates

    def save_templates(self, templates: list[DiagramData]):
        """将模板持久化到磁盘"""
        data = {"templates": [t.to_dict() for t in templates]}
        # 确保目录存在
        os.makedirs(os.path.dirname(self._template_file), exist_ok=True)
        # 写入文件
        json_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        with open(self._template_file, "w", encoding="utf-8") as f:
            f.write(json_str)

    # -- 最近项目（QSettings 持久化） --

    @property
    def recent_projects(self) -> list[str]:
        """获取最近项目列表"""
        self.cleanup_recent_projects(save=False)
        return list(self._recent_projects)

    def _load_recent_projects(self):
        """从 QSettings 加载最近项目"""
        if self._settings is None:
            return
        self._settings.beginGroup(self.SETTINGS_GROUP)
        raw = self._settings.value(self.RECENT_PROJECTS_KEY, [], type=list)
        self._settings.endGroup()
        # 处理字符串情况
        if isinstance(raw, str):
            raw = [raw] if raw else []
        self._recent_projects = []
        for path in (raw or []):
            normalized = self._normalize_path(path)
            if normalized and normalized not in self._recent_projects:
                self._recent_projects.append(normalized)
        self.cleanup_recent_projects(save=True)

    def _save_recent_projects(self):
        """保存最近项目到 QSettings"""
        if self._settings is None:
            return
        self._settings.beginGroup(self.SETTINGS_GROUP)
        self._settings.setValue(self.RECENT_PROJECTS_KEY, self._recent_projects)
        self._settings.endGroup()
        self._settings.sync()

    def _normalize_path(self, file_path: str) -> str:
        """标准化文件路径"""
        if not file_path:
            return ""
        return os.path.abspath(os.path.normpath(file_path))

    def add_recent(self, file_path: str):
        """添加项目到最近列表"""
        file_path = self._normalize_path(file_path)
        if not file_path:
            return
        # 如果已存在，先移除
        if file_path in self._recent_projects:
            self._recent_projects.remove(file_path)
        # 插入到开头
        self._recent_projects.insert(0, file_path)
        # 限制最大数量
        self._recent_projects = self._recent_projects[:self.MAX_RECENT_PROJECTS]
        self._save_recent_projects()

    def remove_recent(self, file_path: str):
        """从最近列表中移除项目"""
        file_path = self._normalize_path(file_path)
        if file_path in self._recent_projects:
            self._recent_projects.remove(file_path)
            self._save_recent_projects()

    def clear_recent_projects(self):
        """清空最近项目列表"""
        self._recent_projects.clear()
        self._save_recent_projects()

    def cleanup_recent_projects(self, save: bool = True):
        """清理不存在的项目路径"""
        cleaned: list[str] = []
        for path in self._recent_projects:
            normalized = self._normalize_path(path)
            # 只保留存在的路径
            if normalized and os.path.exists(normalized) and normalized not in cleaned:
                cleaned.append(normalized)
        cleaned = cleaned[:self.MAX_RECENT_PROJECTS]
        changed = cleaned != self._recent_projects
        self._recent_projects = cleaned
        if changed and save:
            self._save_recent_projects()

    def get_recent_projects_info(self) -> list[dict]:
        """返回最近项目信息用于UI显示（名称、路径、修改时间）"""
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

    # -- 保存 --

    def save(self, project: ProjectItem = None) -> bool:
        """保存项目"""
        project = project or self.current_project
        if project is None or not project.file_path:
            return False
        # 更新修改时间
        project.modified_at = datetime.now().isoformat()
        # 序列化
        data = self._serialize(project)
        try:
            with open(project.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            # 添加到最近项目
            self.add_recent(project.file_path)
            # 发布保存事件
            from core.events import EventType, event_system
            event_system.publish(EventType.PROJECT_SAVED, sender=self, project=project)
            return True
        except Exception as e:
            from core.events import EventType, event_system
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"保存失败: {e}")
            return False

    def save_as(self, project: ProjectItem, file_path: str) -> bool:
        """另存为"""
        project.file_path = file_path
        project.name = os.path.splitext(os.path.basename(file_path))[0]
        return self.save(project)

    # -- 加载 --

    def load(self, file_path: str) -> ProjectItem | None:
        """加载项目"""
        file_path = self._normalize_path(file_path)
        if not file_path or not os.path.exists(file_path):
            self.remove_recent(file_path)
            from core.events import EventType, event_system
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"文件不存在: {file_path}")
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 反序列化
            project = self._deserialize(data, file_path)
            # 确保至少有一个图表
            if not project.diagrams:
                project.add_diagram(project.name)
            self.current_project = project
            self.add_recent(file_path)
            # 发布加载事件
            from core.events import EventType, event_system
            event_system.publish(EventType.PROJECT_LOADED, sender=self, project=project)
            return project
        except Exception as e:
            from core.events import EventType, event_system
            event_system.publish(EventType.MESSAGE_ERROR, sender=self, message=f"加载失败: {e}")
            return None

    # -- 新建项目 --

    def new_project(self, name: str = "新建项目") -> ProjectItem:
        """新建项目"""
        project = ProjectItem(name=name)
        project.add_diagram(name)
        self.current_project = project
        # 发布项目变更事件
        from core.events import EventType, event_system
        event_system.publish(EventType.PROJECT_CHANGED, sender=self, project=project)
        return project

    # -- 序列化（多图格式） --

    def _serialize(self, project: ProjectItem) -> dict:
        """序列化项目为字典"""
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
        """从字典反序列化项目"""
        from core.registry import node_registry
        from core.workflow import WorkflowEngine

        # 创建项目对象
        project = ProjectItem(
            name=data.get("name", "新建项目"),
            file_path=file_path,
        )
        # 恢复项目属性
        project.version = data.get("version", "2.0.0")
        project.description = data.get("description", "")
        project.author = data.get("author", "")
        project.created_at = data.get("created_at", "")
        project.modified_at = data.get("modified_at", "")

        # 节点工厂函数
        def node_factory(type_name: str) -> "NodeBase | None":
            return node_registry.create(type_name)

        # 加载图表数组（新格式）
        diagrams_data = data.get("diagrams")
        if diagrams_data:
            for dd in diagrams_data:
                project.diagrams.append(DiagramData.from_dict(dd, node_factory))
            project._selected_diagram_index = data.get("selected_diagram_index", 0)
        else:
            # 向后兼容：加载单个工作流
            workflow = WorkflowEngine(name=project.name)
            wf_data = data.get("workflow", {"nodes": [], "links": []})
            workflow.from_dict(wf_data, node_factory)
            d = DiagramData(name=project.name)
            d.workflow = workflow
            project.diagrams.append(d)
            project._selected_diagram_index = 0

        # 加载模板
        templates_data = data.get("templates", [])
        for td in templates_data:
            project._templates.append(DiagramData.from_dict(td, node_factory))

        return project

    # -- 项目 CRUD --

    def close_project(self):
        """关闭当前项目"""
        self.current_project = None

    def delete_project_file(self, file_path: str) -> bool:
        """删除项目文件"""
        file_path = self._normalize_path(file_path)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            self.remove_recent(file_path)
            return True
        except OSError:
            return False


# 全局实例
project_service = ProjectService()