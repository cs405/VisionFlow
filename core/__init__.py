# VisionFlow - Core Framework

from core.ioc import ServiceCollection, ServiceProvider, service_collection
from core.events import EventSystem, event_system
from core.data_packet import DataPacket, FlowableResult, FlowableResultState
from core.node_base import (
    NodeBase,
    Property,
    Port,
    PortType,
    PortDock,
    PropertyGroupNames,
)
from core.node_vision import (
    VisionNodeData
)
from core.node_roi import ROINodeData
from core.node_selectable import (
    SelectableResultImageNodeData,
    SrcFilesVisionNodeData,
    Base64MatchingNodeData,
    OpenCVNodeDataBase,
)
from core.node_condition import (
    ConditionNodeData,
    WaitAllParallelNodeData,
)
from core.node_group import NodeGroup, NodeDataGroupBase
from core.registry import NodeRegistry, node_registry
from core.workflow import WorkflowEngine, WorkflowState
from core.project import ProjectItem, DiagramData, ProjectService, project_service
from core.plugin_manager import PluginManager
from core.conditions import (
    ConditionOperate,
    FilterOperate,
    PropertyCondition,
    ConditionBranch,
    ConditionsPresenter,
    ConditionsPrensenter,  # 向后兼容别名（已弃用）
)
