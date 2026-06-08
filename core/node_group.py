"""Node group system - toolbox categories for node discovery.

Each group discovers node types implementing a marker interface and orders them
for display in the toolbox. In Python, we use class decorators / __init_subclass__

Categories :
  10000 - 图像数据源 (SrcImageDataGroup)
  10001 - 系统数据源 (ZooNodeDataGroup)
  10100 - 图像预处理模块 (PreprocessingDataGroup)
  10200 - 滤波模块 (BlurDataGroup)
  10300 - 图像分割提取模块 (TakeoffDataGroup)
  10400 - 形态学模块 (MorphologyDataGroup)
  10500 - 逻辑模块 (ConditionDataGroup)
  10600 - 模板匹配模块 (TemplateMatchingDataGroup)
  10700 - 对象识别模块 (DetectorDataGroup)
  10700 - 网络通讯模块 (NetworkDataGroup)
  10900 - 其他模块 (OtherDataGroup)
  10900 - 结果输出模块 (OutputDataGroup)
"""

from typing import Type

from core.node_base import NodeBase


class NodeGroup:
    """A category/group of nodes shown in the toolbox.

    """

    def __init__(self, name: str, description: str = "", order: int = 0,
                 icon: str = "", category: str = ""):
        self.name = name
        self.description = description
        self.order = order
        self.icon = icon
        self.category = category or name
        self._node_types: list[Type[NodeBase]] = []

    @property
    def node_types(self) -> list[Type[NodeBase]]:
        return sorted(self._node_types, key=lambda t: getattr(t, 'order', 0))

    def register(self, node_type: Type[NodeBase]):
        """Register a node type in this group."""
        if node_type not in self._node_types:
            self._node_types.append(node_type)

    def unregister(self, node_type: Type[NodeBase]):
        """Remove a node type from this group."""
        if node_type in self._node_types:
            self._node_types.remove(node_type)

    def create_node(self, node_type: Type[NodeBase]) -> NodeBase:
        """Instantiate a node from its type."""
        return node_type()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "icon": self.icon,
            "category": self.category,
            "node_types": [t.__name__ for t in self.node_types],
        }


class NodeDataGroupBase:
    """Manages all node groups and provides discovery.
    """

    def __init__(self):
        self._groups: dict[str, NodeGroup] = {}  # 组，存放左侧控制面板的大组
        self._node_registry: dict[str, Type[NodeBase]] = {}  # 注册节点

    # -- Group management --

    def add_group(self, group: NodeGroup):
        """Add a node group."""
        self._groups[group.name] = group

    def remove_group(self, name: str):
        """Remove a node group."""
        self._groups.pop(name, None)

    def get_group(self, name: str) -> NodeGroup | None:
        """Get a group by name."""
        return self._groups.get(name)

    def get_all_groups(self) -> list[NodeGroup]:
        """Get all groups sorted by order."""
        return sorted(self._groups.values(), key=lambda g: g.order)

    # -- Node type registry --

    def register_node(self, node_type: Type[NodeBase], group_name: str):
        """Register a node type in a specific group."""
        self._node_registry[node_type.__name__] = node_type
        if group_name not in self._groups:
            self._groups[group_name] = NodeGroup(name=group_name)
        self._groups[group_name].register(node_type)

    def get_node_type(self, type_name: str) -> Type[NodeBase] | None:
        """Look up a node type by name."""
        return self._node_registry.get(type_name)

    def create_node(self, type_name: str) -> NodeBase | None:
        """Instantiate a node by type name."""
        node_type = self.get_node_type(type_name)
        if node_type:
            return node_type()
        return None

    def get_all_node_types(self) -> list[Type[NodeBase]]:
        """Get all registered node types."""
        return list(self._node_registry.values())

    # -- Discovery --

    def discover_module(self, module, group_prefix: str = ""):
        """Discover NodeBase subclasses in a module and register them.

        Each class must have a `group` class attribute or `__group__` attribute
        to specify which group it belongs to.
        """
        import inspect
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, NodeBase) or obj is NodeBase:
                continue
            if getattr(obj, '__abstract__', False) or inspect.isabstract(obj):
                continue
            group_name = getattr(obj, '__group__', None) or group_prefix
            if group_name:
                self.register_node(obj, group_name)


# =============================================================================
# Standard groups
# =============================================================================

def create_standard_groups() -> NodeDataGroupBase:
    """Create all standard node groups"""
    manager = NodeDataGroupBase()

    groups = [
        NodeGroup("图像数据源", "设置输入图像", order=10000, icon="Camera"),
        NodeGroup("系统数据源", "系统自带测试图像集", order=10001, icon="Dataset"),
        NodeGroup("图像预处理模块", "对图像进行预处理操作", order=10100, icon="Color"),
        NodeGroup("滤波模块", "图像滤波与模糊处理", order=10200, icon="Blur"),
        NodeGroup("图像分割提取模块", "提取与分割图像区域", order=10300, icon="Cut"),
        NodeGroup("形态学模块", "形态学图像处理操作", order=10400, icon="Morphology"),
        NodeGroup("逻辑模块", "条件分支与并行控制", order=10500, icon="Logic"),
        NodeGroup("模板匹配模块", "模板匹配与特征匹配", order=10600, icon="Match"),
        NodeGroup("对象识别模块", "目标检测与识别", order=10700, icon="Detect"),
        NodeGroup("网络通讯模块", "Modbus等网络通讯", order=10700, icon="Network"),
        NodeGroup("其他模块", "其他图像处理功能", order=10900, icon="Other"),
        NodeGroup("结果输出模块", "流程结果输出", order=10900, icon="Output"),
        NodeGroup("Onnx通用模型", "ONNX深度学习模型推理", order=10500, icon="DNN"),
        NodeGroup("特征提取模块", "图像特征检测与提取", order=10800, icon="Feature"),
        NodeGroup("视频处理模块", "视频分析与处理", order=11000, icon="Video"),
    ]

    for g in groups:
        manager.add_group(g)

    return manager


# Global instance
node_data_group_manager = create_standard_groups()
