"""核心接口（抽象基类）—— 层与层之间的契约

定义了所有关键领域对象的抽象基类。
服务依赖这些接口而非具体实现。
GUI 控件依赖接口和服务，而不是直接依赖核心模型类。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.data_packet import FlowableResult


# ═══════════════════════════════════════════════════════════════════════════
# 节点接口
# ═══════════════════════════════════════════════════════════════════════════

class INodeData(ABC):
    """最小节点契约 —— 所有图表节点都实现此接口"""

    @property
    @abstractmethod
    def node_id(self) -> str: ...
    """节点唯一标识符"""

    @property
    @abstractmethod
    def name(self) -> str: ...
    """节点名称"""

    @property
    @abstractmethod
    def display_name(self) -> str: ...
    """节点显示名称（用于UI）"""

    @property
    @abstractmethod
    def ports(self) -> list[Any]: ...
    """节点的端口列表"""

    @abstractmethod
    def to_dict(self) -> dict: ...
    """序列化为字典"""

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> INodeData: ...
    """从字典反序列化"""


class IVisionNodeData(INodeData):
    """视觉处理节点 —— 生成结果图像"""

    @property
    @abstractmethod
    def message(self) -> str: ...
    """节点消息"""

    @message.setter
    @abstractmethod
    def message(self, value: str): ...
    """设置节点消息

    参数：
        value: 节点消息字符串
    """

    @property
    @abstractmethod
    def result_image_source(self) -> Any: ...
    """结果图像源"""

    @abstractmethod
    def invoke(self, previors: Any, diagram: Any) -> FlowableResult: ...
    """调用节点执行处理"""


class ISrcFilesNodeData(INodeData):
    """从文件（图像/视频）加载数据的节点"""

    @property
    @abstractmethod
    def src_file_path(self) -> str: ...
    """源文件路径"""

    @src_file_path.setter
    def src_file_path(self, value: str):
        """设置源文件路径"""
        ...

    @property
    @abstractmethod
    def src_file_paths(self) -> list[str]: ...
    """源文件路径列表"""

    @abstractmethod
    def add_files(self, paths: list[str]): ...
    """添加文件"""

    @abstractmethod
    def add_files_from_folder(self, folder: str): ...
    """从文件夹添加文件"""

    @abstractmethod
    def clear_files(self): ...
    """清空所有文件"""


class IROINodeData(IVisionNodeData):
    """支持 ROI（感兴趣区域）的节点"""

    @abstractmethod
    def get_active_roi_rect(self) -> tuple | None: ...
    """获取当前活动的 ROI 矩形区域"""


# ═══════════════════════════════════════════════════════════════════════════
# 图表/工作流接口
# ═══════════════════════════════════════════════════════════════════════════

class IDiagramData(ABC):
    """包含节点和连线的图表/流程页面"""

    @property
    @abstractmethod
    def id(self) -> str: ...
    """图表唯一标识符"""

    @property
    @abstractmethod
    def name(self) -> str: ...
    """图表名称"""


class IWorkflowEngine(ABC):
    """可执行的工作流（由连通的节点组成）"""

    @property
    @abstractmethod
    def name(self) -> str: ...
    """工作流名称"""

    @abstractmethod
    def add_node(self, node: INodeData): ...
    """添加节点"""

    @abstractmethod
    def remove_node(self, node_id: str): ...
    """移除节点"""

    @abstractmethod
    def get_node_by_id(self, node_id: str) -> INodeData | None: ...
    """根据ID获取节点"""

    @abstractmethod
    def get_all_nodes(self) -> list[INodeData]: ...
    """获取所有节点"""

    @abstractmethod
    def add_link(self, from_id: str, to_id: str, **kwargs) -> Any: ...
    """添加连接"""

    @abstractmethod
    def remove_link(self, link_id: str): ...
    """移除连接"""

    @abstractmethod
    def get_all_links(self) -> list[Any]: ...
    """获取所有连接"""

    @abstractmethod
    def execute(self) -> FlowableResult: ...
    """执行工作流"""

    @abstractmethod
    def stop(self): ...
    """停止工作流执行"""


# ═══════════════════════════════════════════════════════════════════════════
# 项目接口
# ═══════════════════════════════════════════════════════════════════════════

class IProjectItem(ABC):
    """包含多个图表的项目"""

    @property
    @abstractmethod
    def id(self) -> str: ...
    """项目唯一标识符"""

    @property
    @abstractmethod
    def name(self) -> str: ...
    """项目名称"""

    @property
    @abstractmethod
    def display_name(self) -> str: ...
    """项目显示名称"""

    @property
    @abstractmethod
    def diagrams(self) -> list[IDiagramData]: ...
    """项目中的所有图表"""

    @property
    @abstractmethod
    def selected_diagram(self) -> IDiagramData | None: ...
    """当前选中的图表"""

    @abstractmethod
    def add_diagram(self, name: str = "") -> IDiagramData: ...
    """添加新图表"""

    @abstractmethod
    def delete_diagram(self, diagram: IDiagramData) -> bool: ...
    """删除图表"""


# ═══════════════════════════════════════════════════════════════════════════
# 服务接口（桥接层）
# ═══════════════════════════════════════════════════════════════════════════

class INodeService(ABC):
    """节点类型发现、创建和生命周期管理服务"""

    @abstractmethod
    def get_all_node_types(self) -> list[type]: ...
    """获取所有节点类型"""

    @abstractmethod
    def get_node_type(self, type_name: str) -> type | None: ...
    """根据名称获取节点类型"""

    @abstractmethod
    def create_node(self, type_name: str) -> INodeData | None: ...
    """创建节点实例"""

    @abstractmethod
    def get_groups(self) -> list[Any]: ...
    """获取节点分组列表"""


class IProjectService(ABC):
    """项目 CRUD 和序列化服务"""

    @property
    @abstractmethod
    def current_project(self) -> IProjectItem | None: ...
    """当前打开的项目"""

    @abstractmethod
    def new_project(self) -> IProjectItem: ...
    """新建项目"""

    @abstractmethod
    def load(self, path: str) -> IProjectItem | None: ...
    """加载项目"""

    @abstractmethod
    def save(self, project: IProjectItem) -> bool: ...
    """保存项目"""

    @abstractmethod
    def save_as(self, project: IProjectItem, path: str) -> bool: ...
    """另存为"""

    @property
    @abstractmethod
    def recent_projects(self) -> list[str]: ...
    """最近打开的项目列表"""


class IThemeService(ABC):
    """主题管理服务"""

    @abstractmethod
    def toggle(self): ...
    """切换主题"""

    @abstractmethod
    def get_stylesheet(self) -> str: ...
    """获取样式表"""

    @property
    @abstractmethod
    def is_dark(self) -> bool: ...
    """是否为暗色主题"""

    @property
    @abstractmethod
    def colors(self) -> Any: ...
    """主题颜色配置"""


class IEventBus(ABC):
    """组件间通信的发布-订阅事件总线"""

    @abstractmethod
    def subscribe(self, event_type: Any, handler): ...
    """订阅事件"""

    @abstractmethod
    def unsubscribe(self, event_type: Any, handler): ...
    """取消订阅"""

    @abstractmethod
    def publish(self, event_type: Any, sender: Any = None, **kwargs): ...
    """发布事件"""