"""
节点基类层次结构
定义所有视觉处理节点的完整继承链

继承关系（自上而下）:
    NodeBase  （端口、样式、图表数据）                              ← node_base.py
      -> VisionNodeDataBase  （流程延迟）                           ← node_vision.py
        -> ShowPropertyNodeDataBase  （属性展示器）
          -> HelpNodeDataBase  （帮助 URL）
            -> DemoNodeDataBase  （示例参数）
              -> VisionNodeData  （Mat、ResultImages、调用生命周期）
                -> ROINodeData  （DrawROI / FromROI / InputROI）    ← node_roi.py
                -> SelectableResultImageNodeData  （选择上游结果）   ← node_selectable.py
                  -> OpenCVNodeDataBase  （OpenCV 特有的 Mat 处理）
                -> SrcFilesVisionNodeData （基于文件的图像源）
                -> Base64MatchingNodeData  （模板匹配）
                -> ConditionNodeData  （条件分支）                  ← node_condition.py
                -> WaitAllParallelNodeData  （并行同步屏障）

"""

from __future__ import annotations

import uuid
import importlib
import numpy as np
from enum import Enum, auto
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

from contextlib import contextmanager

from core.data_packet import FlowableResult, FlowableInvokeMode
from core.events import EventType, event_system

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# 参数分组名称
# =============================================================================

class PropertyGroupNames:
    """属性分组名称常量类，用于UI中分组显示节点参数"""

    RUN_PARAMETERS = "运行参数"  # 运行时相关参数（如执行次数、延时等）
    BASE_PARAMETERS = "基本参数"  # 节点基础参数（如名称、描述等）
    RESULT_PARAMETERS = "结果参数"  # 输出结果相关参数（如保存路径、格式等）
    FLOW_PARAMETERS = "流程控制"  # 流程控制参数（如条件判断、循环等）
    DISPLAY_PARAMETERS = "显示参数"  # UI显示相关参数（如颜色、透明度等）
    OTHER_PARAMETERS = "其他参数"  # 未归类参数


# =============================================================================
# 属性描述符
# =============================================================================

class Property:
    """带元数据的可观察属性描述符。

    属性面板的扩展元数据：
      - editor: str | None  -> 自定义编辑器提示（"color", "roi", "file", "slider", "choices"）
      - choices: list | None -> 下拉选项
      - min_val / max_val: 范围约束
      - validator: callable | None -> 验证函数 (value) -> (bool, str)
      - step: float -> 步进值（用于数值调节控件）
      - decimals: int -> 浮点数显示的小数位数
    """

    def __init__(self, default: Any = None, *, name: str = "", group: str = "",
                 description: str = "", readonly: bool = False, order: int = 0,
                 editor: str = "", choices: list = None,
                 min_val: Any = None, max_val: Any = None,
                 validator: callable = None,
                 step: float = 0.1, decimals: int = 3):

        self.default = default  # 属性的默认值
        self.display_name = name  # 在UI中显示的属性名称
        self.group = group  # 属性所属的分组（用于在属性面板中归类）
        self.description = description  # 属性的描述文本（用于工具提示等）
        self.readonly = readonly  # 是否为只读属性
        self.order = order  # 在属性面板中的显示顺序（数值越小越靠前）
        self.editor = editor  # 扩展元数据：自定义编辑器类型
        self.choices = choices or []  # 扩展元数据：下拉选项列表
        self.min_val = min_val  # 扩展元数据：最小值约束
        self.max_val = max_val  # 扩展元数据：最大值约束
        self.validator = validator  # 扩展元数据：验证函数
        self.step = step  # 扩展元数据：步进值
        self.decimals = decimals  # 扩展元数据：小数位数

    def __set_name__(self, owner, name):
        """描述符协议：在类创建时被调用，用于设置属性名称"""
        # 存储属性的私有变量名（以下划线开头）
        self.attr_name = f"_{name}"
        # 存储属性的公开名称
        self.public_name = name

    def __get__(self, obj, objtype=None):
        """描述符协议：获取属性值时被调用"""
        # 如果通过类访问（obj为None），返回描述符本身
        if obj is None:
            return self
        # 从实例中获取私有变量值，不存在则返回默认值
        return getattr(obj, self.attr_name, self.default)

    def __set__(self, obj, value):
        """描述符协议：设置属性值时被调用"""
        # 获取旧值
        old = getattr(obj, self.attr_name, self.default)
        # 设置新值
        setattr(obj, self.attr_name, value)
        # 如果值发生变化，通知属性变更
        if old != value:
            obj._notify_property_changed(self.public_name, old, value)


# =============================================================================
# 端口类型
# =============================================================================

class PortType(Enum):
    """端口类型枚举"""
    INPUT = auto()   # 输入端口
    OUTPUT = auto()  # 输出端口
    BOTH = auto()    # 双向端口（既可作为输入也可作为输出）


class PortDock(Enum):
    """端口停靠位置枚举"""
    TOP = auto()     # 顶部停靠
    BOTTOM = auto()  # 底部停靠
    LEFT = auto()    # 左侧停靠
    RIGHT = auto()   # 右侧停靠



class Port:
    """
    节点上的连接端口
    节点有4个端口：顶部（输入）、底部（输出）、左侧（输入）、右侧（输出）
    """

    def __init__(self, node_id: str, port_type: PortType, dock: PortDock,
                 port_id: str = None, name: str = ""):

        self.port_id = port_id or str(uuid.uuid4())[:8]  # 端口唯一标识符，未提供时自动生成8位UUID
        self.node_id = node_id  # 所属节点的ID
        self.port_type = port_type  # 端口类型（输入/输出/双向）
        self.dock = dock  # 端口停靠位置（上/下/左/右）
        self.name = name  # 端口显示名称
        self.width = 6  # 端口的视觉宽度（像素）
        self.height = 6  # 端口的视觉高度（像素）
        self.fill_color = "#FFFFFF"  # 端口填充颜色
        self.link_color = "#FF8C00"  # 连接线颜色，橙色，与 OpenCVFlowablePortData 保持一致
        self.connected_links: list["LinkData"] = []  # 与该端口相连的所有连接线列表

    @property
    def is_input(self) -> bool:
        """判断是否为输入端口（包括 INPUT 和 BOTH 类型）"""
        return self.port_type in (PortType.INPUT, PortType.BOTH)

    @property
    def is_output(self) -> bool:
        """判断是否为输出端口（包括 OUTPUT 和 BOTH 类型）"""
        return self.port_type in (PortType.OUTPUT, PortType.BOTH)

    def to_dict(self) -> dict:
        """将端口对象序列化为字典"""
        return {
            "port_id": self.port_id,           # 端口唯一标识符
            "node_id": self.node_id,           # 所属节点ID
            "port_type": self.port_type.name,  # 存储枚举名称
            "dock": self.dock.name,            # 存储枚举名称
            "name": self.name,                 # 端口显示名称
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Port":
        """从字典反序列化创建端口对象"""
        return cls(
            node_id=data["node_id"],
            port_type=PortType[data["port_type"]],  # 根据名称获取枚举值
            dock=PortDock[data["dock"]],            # 根据名称获取枚举值
            port_id=data.get("port_id"),            # 端口ID，反序列化时可能存在
            name=data.get("name", ""),   # 端口显示名称，反序列化时可能存在
        )

    def invoke(self, previors: "LinkData | None" = None,
               diagram: "WorkflowEngine | None" = None) -> "FlowableResult":
        """
        执行端口级逻辑
        默认行为：发布 PORT_STARTED 事件 → 返回 OK 结果 → 发布 PORT_COMPLETED 事件。
        子类可重写此方法以实现自定义端口处理（验证、转换等）
        """
        # 延迟导入避免循环依赖
        from core.data_packet import FlowableResult
        from core.events import EventType, event_system
        # 发布端口开始执行事件
        event_system.publish(EventType.PORT_STARTED, sender=self, diagram=diagram)
        # 创建成功结果
        result = FlowableResult.ok(message="port ok")
        # 发布端口执行完成事件
        event_system.publish(EventType.PORT_COMPLETED, sender=self, result=result,
                             diagram=diagram)
        return result


class LinkData:
    """连接两个端口的连线数据类"""

    def __init__(self, from_node_id: str = "", from_port_id: str = "",
                 to_node_id: str = "", to_port_id: str = "",
                 text: str = ""):

        self.link_id = str(uuid.uuid4())[:8]  # 连线唯一标识符，自动生成8位UUID
        self.from_node_id = from_node_id  # 源节点ID
        self.from_port_id = from_port_id  # 源端口ID
        self.to_node_id = to_node_id  # 目标节点ID
        self.to_port_id = to_port_id  # 目标端口ID
        self.text = text  # 连线上的文本标签
        self.stroke_color = "#FF8C00"  # 连线颜色，橙色

    def to_dict(self) -> dict:
        """将连线对象序列化为字典"""
        return {
            "link_id": self.link_id,
            "from_node_id": self.from_node_id,
            "from_port_id": self.from_port_id,
            "to_node_id": self.to_node_id,
            "to_port_id": self.to_port_id,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LinkData":
        """从字典反序列化创建连线对象"""
        link = cls(
            from_node_id=data.get("from_node_id", ""),
            from_port_id=data.get("from_port_id", ""),
            to_node_id=data.get("to_node_id", ""),
            to_port_id=data.get("to_port_id", ""),
            text=data.get("text", ""),
        )
        # 使用字典中的link_id覆盖自动生成的ID（保持ID一致性）
        link.link_id = data.get("link_id", link.link_id)
        return link

    def invoke(self, diagram: "WorkflowEngine | None" = None) -> "FlowableResult":
        """
        执行连线级逻辑
        默认行为：发布 LINK_STARTED 事件 → 返回 OK 结果 → 发布 LINK_COMPLETED 事件。
        子类可重写此方法以实现自定义连线处理（过滤、转换等）
        """
        from core.events import EventType, event_system
        # 发布连线开始执行事件
        event_system.publish(EventType.LINK_STARTED, sender=self)
        # 创建成功结果
        result = FlowableResult.ok(message="link ok")
        # 发布连线执行完成事件
        event_system.publish(EventType.LINK_COMPLETED, sender=self, result=result)
        return result


# =============================================================================
# 节点基类
# =============================================================================

class NodeBase(ABC):
    """
    所有图表节点的根基类。
    提供：端口、样式、图表数据管理和序列化。
    """

    def __init__(self):
        # 节点唯一标识符，自动生成8位UUID
        self._id = str(uuid.uuid4())[:8]
        # 显示名称，默认为类名
        self._name = self.__class__.__name__
        # 显示文本
        self._text = ""
        # 标题
        self._title = ""

        # 属性更改回调字典，键为属性名，值为回调函数列表
        self._property_callbacks: dict[str, list[Callable]] = {}

        # 样式属性
        self.width: float = 120.0      # 节点宽度
        self.height: float = 35.0      # 节点高度
        self.corner_radius: float = 2.0  # 圆角半径
        self.fill_color: str = "#FFFFFF"  # 填充颜色
        self.flag_length: float = 10.0    # 标志长度

        # 端口列表
        self.ports: list[Port] = []
        self._init_ports()  # 初始化端口

        # 图表数据（工作流引擎引用）
        self._diagram_data: WorkflowEngine | None = None
        # 上游节点列表
        self.from_node_datas: list[NodeBase] = []
        # 下游节点列表
        self.to_node_datas: list[NodeBase] = []

        # 结果图像（来自 IResultImageSourceNodeData）
        self.use_result_image_source: bool = True
        # 结果图像源（GUI用QImage/QPixmap，内部用numpy数组）
        self._result_image_source: Any = None

        # Flowable相关
        self.message: str = ""

        # 执行模式
        self.invoke_mode: FlowableInvokeMode = FlowableInvokeMode.SEQUENTIAL

        # 工具箱排序顺序
        self.order: int = 0

        self.load_default()

    # -- 属性变更通知 --

    def _notify_property_changed(self, name: str, old_value: Any, new_value: Any):
        """当属性值发生变化时，由 Property 描述符调用此方法"""
        # 调用所有注册的回调函数
        for cb in self._property_callbacks.get(name, []):
            cb(name, old_value, new_value)
        # 批量更新模式下跳过事件发布，避免逐个属性变更时洪水式发布
        if not getattr(self, '_batch_updating', False):
            event_system.publish(EventType.NODE_PROPERTY_CHANGED,
                                sender=self, name=name, old=old_value, new=new_value)

    @contextmanager
    def batch_updates(self):
        """批量属性更新上下文管理器。

        在此上下文中修改多个属性时，不会逐个发布 NODE_PROPERTY_CHANGED 事件。
        退出上下文时发布一次汇总事件。
        用于 restore_from_dict 等批量恢复场景。
        """
        was_batching = getattr(self, '_batch_updating', False)
        self._batch_updating = True
        try:
            yield
        finally:
            self._batch_updating = was_batching
            if not was_batching:
                event_system.publish(EventType.NODE_PROPERTY_CHANGED,
                                    sender=self, name="*", old=None, new=None)

    def on_property_changed(self, name: str, callback: Callable):
        """注册属性变更回调函数"""
        self._property_callbacks.setdefault(name, []).append(callback)

    # -- 标识属性 --

    @property
    def node_id(self) -> str:
        """获取节点ID"""
        return self._id

    @property
    def name(self) -> str:
        """获取节点名称"""
        return self._name

    @name.setter
    def name(self, value: str):
        """设置节点名称"""
        self._name = value

    @property
    def title(self) -> str:
        """获取节点标题（优先使用_title，否则使用_name）"""
        return self._title or self._name

    @title.setter
    def title(self, value: str):
        """设置节点标题，同时更新文本"""
        self._title = value
        self._text = value

    @property
    def text(self) -> str:
        """获取节点显示文本"""
        return self._text or self._name

    @text.setter
    def text(self, value: str):
        """设置节点显示文本"""
        self._text = value

    @property
    def display_name(self) -> str:
        """获取在工具箱和UI中显示的名称"""
        return self._name

    # -- 图表数据绑定 --

    @property
    def diagram_data(self) -> WorkflowEngine | None:
        """获取工作流引擎引用"""
        return self._diagram_data

    @diagram_data.setter
    def diagram_data(self, value: WorkflowEngine | None):
        """设置工作流引擎引用"""
        self._diagram_data = value

    def get_all_from_node_datas(self) -> list["NodeBase"]:
        """递归获取所有上游节点"""
        visited: set[str] = set()
        result: list[NodeBase] = []

        def traverse(node: NodeBase):
            # 避免重复访问
            if node.node_id in visited:
                return
            visited.add(node.node_id)
            for from_node in node.from_node_datas:
                result.append(from_node)
                traverse(from_node)

        traverse(self)
        return result

    def get_all_from_this_node_datas(self) -> list["NodeBase"]:
        """获取当前节点及所有上游节点"""
        return [self] + self.get_all_from_node_datas()

    def get_start_node_datas(self) -> list["NodeBase"]:
        """查找根节点（没有输入的节点）"""
        all_nodes = self.get_all_from_this_node_datas()
        return [n for n in all_nodes if len(n.from_node_datas) == 0]

    def get_from_node_data(self, node_type: type) -> "NodeBase | None":
        """查找最近的上游节点（指定类型）"""
        for from_node in self.from_node_datas:
            if isinstance(from_node, node_type):
                return from_node
            result = from_node.get_from_node_data(node_type)
            if result is not None:
                return result
        return None

    # -- 端口管理 --

    def _init_ports(self):
        """初始化4个默认端口（上/下/左/右）"""
        self.ports = []
        # 顶部 - 输入端口
        p = self.create_port_data()
        p.dock = PortDock.TOP
        p.port_type = PortType.INPUT
        self.ports.append(p)
        # 底部 - 输出端口
        p = self.create_port_data()
        p.dock = PortDock.BOTTOM
        p.port_type = PortType.OUTPUT
        self.ports.append(p)
        # 左侧 - 输入端口
        p = self.create_port_data()
        p.dock = PortDock.LEFT
        p.port_type = PortType.INPUT
        self.ports.append(p)
        # 右侧 - 输出端口
        p = self.create_port_data()
        p.dock = PortDock.RIGHT
        p.port_type = PortType.OUTPUT
        self.ports.append(p)

    def create_port_data(self) -> Port:
        """创建单个端口。子类可重写以自定义端口样式"""
        return Port(node_id=self.node_id, port_type=PortType.BOTH,
                   dock=PortDock.TOP)

    def get_input_ports(self) -> list[Port]:
        """获取所有输入端口"""
        return [p for p in self.ports if p.is_input]

    def get_output_ports(self) -> list[Port]:
        """获取所有输出端口"""
        return [p for p in self.ports if p.is_output]

    def get_flowable_output_links(self, diagram: "WorkflowEngine") -> list["LinkData"]:
        """获取应从本节点路由的输出连线。

        默认行为：返回所有连接到输出端口的连线。
        子类可重写以实现选择性端口路由（如条件分支）。
        """
        active_port_ids = set()
        active_port_name = getattr(self, '_active_output_port_name', None)
        if active_port_name:
            # 只路由到指定的活动端口
            for p in self.get_output_ports():
                if p.name == active_port_name:
                    active_port_ids.add(p.port_id)
        else:
            # 默认：所有输出端口都激活
            active_port_ids = {p.port_id for p in self.get_output_ports()}

        return [l for l in diagram.get_all_links()
                if l.from_node_id == self.node_id and l.from_port_id in active_port_ids]

    # -- 结果图像 --

    @property
    def result_image_source(self) -> Any:
        """获取结果图像源"""
        return self._result_image_source

    @result_image_source.setter
    def result_image_source(self, value: Any):
        """设置结果图像源"""
        self._result_image_source = value

    # -- 生命周期 --

    def load_default(self):
        """设置默认值。子类可重写"""
        pass

    @classmethod
    def get_property_descriptors(cls) -> list[tuple[str, Property]]:
        """获取类层次结构中声明的所有 Property 描述符"""
        result: list[tuple[str, Property]] = []
        seen: set[str] = set()
        # 遍历MRO（方法解析顺序），从子类到父类
        for owner in cls.__mro__:
            if owner is object:
                break
            for name, desc in owner.__dict__.items():
                if isinstance(desc, Property) and name not in seen:
                    result.append((name, desc))
                    seen.add(name)
        return result

    def _serialize_property_value(self, value: Any) -> Any:
        """将属性值序列化为JSON可序列化的格式"""
        # numpy整数转为Python int
        if isinstance(value, (np.integer,)):
            return int(value)
        # numpy浮点数转为Python float
        if isinstance(value, (np.floating,)):
            return float(value)
        # numpy数组转为列表
        if isinstance(value, np.ndarray):
            return value.tolist()
        # 枚举类型
        if isinstance(value, Enum):
            return {
                "__enum__": f"{value.__class__.__module__}.{value.__class__.__name__}",
                "name": value.name,
            }
        # 元组转为特殊字典
        if isinstance(value, tuple):
            return {"__tuple__": [self._serialize_property_value(v) for v in value]}
        # 列表递归处理
        if isinstance(value, list):
            return [self._serialize_property_value(v) for v in value]
        # 字典递归处理
        if isinstance(value, dict):
            return {k: self._serialize_property_value(v) for k, v in value.items()}
        # 基本类型直接返回
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        # 有to_dict方法的对象
        if hasattr(value, "to_dict") and callable(value.to_dict):
            return {
                "__type__": value.__class__.__name__,
                "data": value.to_dict(),
            }
        # 其他类型转为字符串
        return str(value)

    def _deserialize_property_value(self, value: Any) -> Any:
        """从序列化格式恢复属性值"""
        if isinstance(value, list):
            return [self._deserialize_property_value(v) for v in value]
        if not isinstance(value, dict):
            # 尝试将字符串数字转回数字（numpy序列化的后备方案）
            if isinstance(value, str):
                try:
                    if '.' in value or 'e' in value.lower():
                        return float(value)
                    return int(value)
                except (ValueError, OverflowError):
                    pass
            return value

        # 恢复元组
        if "__tuple__" in value:
            return tuple(self._deserialize_property_value(v) for v in value.get("__tuple__", []))

        # 恢复枚举
        if "__enum__" in value:
            enum_path = value.get("__enum__", "")
            enum_name = value.get("name", "")
            try:
                module_name, class_name = enum_path.rsplit(".", 1)
                enum_type = getattr(importlib.import_module(module_name), class_name)
                return enum_type[enum_name]
            except Exception:
                return value

        # 恢复自定义对象
        if "__type__" in value:
            type_name = value.get("__type__", "")
            data = value.get("data", {})
            if type_name in {"ROIBase", "FromROI", "DrawROI", "InputROI", "NoROI"}:
                from core.node_roi import ROIBase
                return ROIBase.from_dict(data)

        return {k: self._deserialize_property_value(v) for k, v in value.items()}

    def _serialize_properties(self) -> dict[str, Any]:
        """序列化所有 Property 值（可读和可写属性都保存）"""
        properties: dict[str, Any] = {}
        for name, desc in self.get_property_descriptors():
            properties[name] = self._serialize_property_value(getattr(self, name, desc.default))
        return properties

    def restore_from_dict(self, data: dict) -> "NodeBase":
        """从序列化的项目数据恢复节点状态"""
        with self.batch_updates():
            self._id = data.get("id", self._id)
            self.name = data.get("name", self.name)
            self._title = data.get("title", "")
            self._text = data.get("text", "")
            self.width = data.get("width", 120.0)
            self.height = data.get("height", 35.0)
            self._pos_x = data.get("pos_x", 0.0)
            self._pos_y = data.get("pos_y", 0.0)

            # 恢复执行模式
            invoke_mode_name = data.get("invoke_mode", "SEQUENTIAL")
            try:
                self.invoke_mode = FlowableInvokeMode[invoke_mode_name]
            except KeyError:
                self.invoke_mode = FlowableInvokeMode.SEQUENTIAL

            # 恢复端口
            ports_data = data.get("ports", [])
            if ports_data:
                self.ports = [Port.from_dict(port_data) for port_data in ports_data]
            else:
                for port in self.ports:
                    port.node_id = self._id

            # 恢复属性值
            serialized_properties = data.get("properties", {})
            property_map = dict(self.get_property_descriptors())
            for name, raw_value in serialized_properties.items():
                if name not in property_map:
                    continue
                try:
                    setattr(self, name, self._deserialize_property_value(raw_value))
                except Exception:
                    continue

        return self

    def to_dict(self) -> dict:
        """序列化节点为字典，用于JSON项目保存"""
        return {
            "id": self.node_id,
            "type": self.__class__.__name__,
            "name": self.name,
            "title": self._title,
            "text": self._text,
            "width": self.width,
            "height": self.height,
            "ports": [p.to_dict() for p in self.ports],
            "invoke_mode": self.invoke_mode.name,
            "properties": self._serialize_properties(),
            "pos_x": getattr(self, '_pos_x', 0.0),
            "pos_y": getattr(self, '_pos_y', 0.0),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NodeBase":
        """从字典反序列化节点"""
        node = cls.__new__(cls)
        cls.__init__(node)  # 调用完整 __init__ 链，确保子类状态正确初始化
        node._id = data.get("id", node._id)
        node.name = data.get("name", node.name)
        node._title = data.get("title", "")
        node._text = data.get("text", "")
        node.width = data.get("width", 120.0)
        node.height = data.get("height", 35.0)
        node.invoke_mode = FlowableInvokeMode[data.get("invoke_mode", "SEQUENTIAL")]
        node._pos_x = data.get("pos_x", 0.0)
        node._pos_y = data.get("pos_y", 0.0)
        return node

    def dispose(self):
        """释放资源"""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.node_id}, name={self.name})"


# =============================================================================
# 从子模块重新导出，保持向后兼容
# =============================================================================

from core.node_vision import (           # noqa: E402, F401
    VisionNodeDataBase,
    ShowPropertyNodeDataBase,
    HelpNodeDataBase,
    DemoNodeDataBase,
    VisionNodeData,
)
from core.node_roi import (              # noqa: E402, F401
    ROIBase,
    FromROI,
    DrawROI,
    InputROI,
    NoROI,
    ROINodeData,
)
from core.node_selectable import (       # noqa: E402, F401
    SelectableResultImageNodeData,
    OpenCVNodeDataBase,
    SrcFilesVisionNodeData,
    Base64MatchingNodeData,
)
from core.node_condition import (        # noqa: E402, F401
    LogicModuleNode,
    ConditionNodeData,
    VisionPropertyCondition,
    WaitAllParallelNodeData,
)
