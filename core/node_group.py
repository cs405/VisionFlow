"""节点分组系统 - 工具箱中的节点分类。

每个分组通过标记接口发现节点类型，并按顺序在工具箱中显示。
在 Python 中，我们使用类装饰器 / __init_subclass__ 实现。

分类：
  10000 - 图像数据源 (SrcImageDataGroup)
  10001 - 系统数据源 (ZooNodeDataGroup)
  10100 - 图像预处理模块 (PreprocessingDataGroup)
  10200 - 滤波模块 (BlurDataGroup)
  10300 - 图像分割提取模块 (TakeoffDataGroup)
  10400 - 形态学模块 (MorphologyDataGroup)
  10500 - 逻辑模块 (ConditionDataGroup)
  10501 - Onnx通用模型 (OnnxDataGroup)
  10600 - 模板匹配模块 (TemplateMatchingDataGroup)
  10700 - 对象识别模块 (DetectorDataGroup)
  10701 - 网络通讯模块 (NetworkDataGroup)
  10800 - 特征提取模块 (FeatureDetectorDataGroup)
  10900 - 其他模块 (OtherDataGroup)
  10901 - 结果输出模块 (OutputDataGroup)
  11000 - 视频处理模块 (VideoDataGroup)
"""

from typing import Type

from core.node_base import NodeBase


class NodeGroup:
    """工具箱中显示的一个节点分类/分组。"""

    def __init__(self, name: str, description: str = "", order: int = 0,
                 icon: str = "", category: str = ""):
        # 分组名称
        self.name = name
        # 分组描述
        self.description = description
        # 排序顺序（数值越小越靠前）
        self.order = order
        # 分组图标
        self.icon = icon
        # 分组类别（默认与名称相同）
        self.category = category or name
        # 该分组下的节点类型列表
        self._node_types: list[Type[NodeBase]] = []

    @property
    def node_types(self) -> list[Type[NodeBase]]:
        """获取该分组下的节点类型列表（按order排序）"""
        return sorted(self._node_types, key=lambda t: getattr(t, 'order', 0))

    def register(self, node_type: Type[NodeBase]):
        """在该分组中注册一个节点类型"""
        if node_type not in self._node_types:
            self._node_types.append(node_type)

    def unregister(self, node_type: Type[NodeBase]):
        """从该分组中移除一个节点类型"""
        if node_type in self._node_types:
            self._node_types.remove(node_type)

    def create_node(self, node_type: Type[NodeBase]) -> NodeBase:
        """实例化一个节点类型的节点"""
        return node_type()

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "icon": self.icon,
            "category": self.category,
            "node_types": [t.__name__ for t in self.node_types],
        }


class NodeDataGroupBase:
    """管理所有节点分组并提供节点发现功能。"""

    def __init__(self):
        # 分组字典，键为分组名称，值为 NodeGroup 对象
        self._groups: dict[str, NodeGroup] = {}
        # 节点注册表，键为节点类型名称，值为节点类
        self._node_registry: dict[str, Type[NodeBase]] = {}

    # -- 分组管理 --

    def add_group(self, group: NodeGroup):
        """添加一个节点分组"""
        self._groups[group.name] = group

    def remove_group(self, name: str):
        """删除一个节点分组"""
        self._groups.pop(name, None)

    def get_group(self, name: str) -> NodeGroup | None:
        """根据名称获取分组"""
        return self._groups.get(name)

    def get_all_groups(self) -> list[NodeGroup]:
        """获取所有分组（按order排序）"""
        return sorted(self._groups.values(), key=lambda g: g.order)

    # -- 节点类型注册 --

    def register_node(self, node_type: Type[NodeBase], group_name: str):
        """在指定分组中注册一个节点类型"""
        # 将节点类名注册到节点注册表
        self._node_registry[node_type.__name__] = node_type
        # 如果分组不存在，先创建分组
        if group_name not in self._groups:
            self._groups[group_name] = NodeGroup(name=group_name)
        # 将节点注册到分组中
        self._groups[group_name].register(node_type)

    def get_node_type(self, type_name: str) -> Type[NodeBase] | None:
        """根据类型名称查找节点类型"""
        return self._node_registry.get(type_name)

    def create_node(self, type_name: str) -> NodeBase | None:
        """根据类型名称实例化节点"""
        node_type = self.get_node_type(type_name)
        if node_type:
            return node_type()
        return None

    def get_all_node_types(self) -> list[Type[NodeBase]]:
        """获取所有已注册的节点类型"""
        return list(self._node_registry.values())

    # -- 发现功能 --

    def discover_module(self, module, group_prefix: str = ""):
        """发现模块中的 NodeBase 子类并注册它们。

        每个类必须有一个 `group` 类属性或 `__group__` 属性来指定所属分组。
        """
        import inspect
        # 遍历模块中的所有成员
        for name, obj in inspect.getmembers(module, inspect.isclass):
            # 只处理 NodeBase 的子类且不是 NodeBase 本身
            if not issubclass(obj, NodeBase) or obj is NodeBase:
                continue
            # 跳过抽象类
            if getattr(obj, '__abstract__', False) or inspect.isabstract(obj):
                continue
            # 获取分组名称（优先使用 __group__ 属性，否则使用前缀）
            group_name = getattr(obj, '__group__', None) or group_prefix
            if group_name:
                self.register_node(obj, group_name)


# =============================================================================
# 标准分组
# =============================================================================

def create_standard_groups() -> NodeDataGroupBase:
    """创建所有标准节点分组。

    注意：order 值间距较小（如 10500/10501），第三方插件需插入中间位置时
    可考虑使用浮点数（如 10500.5）或重新编号。
    """
    manager = NodeDataGroupBase()

    # 定义所有标准分组
    groups = [
        NodeGroup("图像数据源", "设置输入图像", order=10000, icon="Camera"),
        NodeGroup("系统数据源", "系统自带测试图像集", order=10001, icon="Dataset"),
        NodeGroup("图像预处理模块", "对图像进行预处理操作", order=10100, icon="Color"),
        NodeGroup("滤波模块", "图像滤波与模糊处理", order=10200, icon="Blur"),
        NodeGroup("图像分割提取模块", "提取与分割图像区域", order=10300, icon="Cut"),
        NodeGroup("形态学模块", "形态学图像处理操作", order=10400, icon="Morphology"),
        NodeGroup("逻辑模块", "条件分支与并行控制", order=10500, icon="Logic"),
        NodeGroup("Onnx通用模型", "ONNX深度学习模型推理", order=10501, icon="DNN"),
        NodeGroup("模板匹配模块", "模板匹配与特征匹配", order=10600, icon="Match"),
        NodeGroup("对象识别模块", "目标检测与识别", order=10700, icon="Detect"),
        NodeGroup("网络通讯模块", "Modbus等网络通讯", order=10701, icon="Network"),
        NodeGroup("特征提取模块", "图像特征检测与提取", order=10800, icon="Feature"),
        NodeGroup("其他模块", "其他图像处理功能", order=10900, icon="Other"),
        NodeGroup("结果输出模块", "流程结果输出", order=10901, icon="Output"),
        NodeGroup("视频处理模块", "视频分析与处理", order=11000, icon="Video"),
    ]

    # 添加所有分组到管理器
    for g in groups:
        manager.add_group(g)

    return manager


# 全局实例
node_data_group_manager = create_standard_groups()