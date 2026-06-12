"""
节点基类层次结构
定义所有视觉处理节点的完整继承链

继承关系（自上而下）:
    NodeBase  （端口、样式、图表数据）
      -> VisionNodeDataBase  （流程延迟）
        -> ShowPropertyNodeDataBase  （属性展示器）
          -> HelpNodeDataBase  （帮助 URL）
            -> DemoNodeDataBase  （示例参数）
              -> VisionNodeData  （Mat、ResultImages、调用生命周期）
                -> ROINodeData  （DrawROI / FromROI / InputROI）
                -> SelectableResultImageNodeData  （选择上游结果）
                  -> OpenCVNodeDataBase  （OpenCV 特有的 Mat 处理）
                -> SrcFilesVisionNodeData （基于文件的图像源）
                -> Base64MatchingNodeData  （模板匹配
                -> ConditionNodeData  （条件分支）
                -> WaitAllParallelNodeData  （并行同步屏障）

"""

from __future__ import annotations

import os
import cv2
import time
import uuid
import base64
import inspect
import importlib
import numpy as np
from enum import Enum, auto
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable


from core.data_packet import FlowableResult, FlowableInvokeMode, VisionResultImage
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
        # 发布属性变更事件
        event_system.publish(EventType.NODE_PROPERTY_CHANGED,
                            sender=self, name=name, old=old_value, new=new_value)

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
        NodeBase.__init__(node)
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
# VisionNodeDataBase - 流延迟参数
# =============================================================================

class VisionNodeDataBase(NodeBase):
    """
    添加流程控制延迟参数的节点基类。
    """


# =============================================================================
# ShowPropertyNodeDataBase - 属性展示器
# =============================================================================

class ShowPropertyNodeDataBase(VisionNodeDataBase):
    """为属性面板提供属性展示器的基类。"""

    def get_property_presenter(self) -> Any:
        """返回在属性面板中显示的对象。默认返回自身。"""
        return self

# =============================================================================
# HelpNodeDataBase - 帮助/文档URL
# =============================================================================

class HelpNodeDataBase(ShowPropertyNodeDataBase):
    """提供带文档URL的帮助展示器的基类。"""

    def create_help_presenter(self) -> dict:
        """返回帮助面板所需的帮助信息。子类可重写以自定义。"""
        # 获取当前节点的类
        cls = type(self)
        # 获取类的文档字符串，取第一行作为简短描述
        doc = (cls.__doc__ or "").strip().split("\n")[0] if cls.__doc__ else ""
        return {
            # 帮助文档URL（使用类名作为路径）
            "url": f"https://github.com/cs405/visionflow/{cls.__name__}",
            # 节点名称
            "name": self.name,
            # 节点描述
            "description": doc or f"{self.name} - {cls.__name__}",
            # 源代码文件路径
            "source": inspect.getfile(cls),
        }

# =============================================================================
# DemoNodeDataBase - 示例/演示参数
# =============================================================================

class DemoNodeDataBase(HelpNodeDataBase):
    """添加演示/示例参数以展示参数系统模式的基类。"""

    # 示例：基本参数（用于演示如何在基本参数分组中添加参数）
    demo_base_parameter1 = Property("", name="示例：基本参数", group=PropertyGroupNames.BASE_PARAMETERS,
                                    description="用来演示如何增加基本参数", order=9999)
    # 示例：运行参数（用于演示如何在运行参数分组中添加参数）
    demo_run_parameter1 = Property("", name="示例：运行参数", group=PropertyGroupNames.RUN_PARAMETERS,
                                   description="用来演示如何增加结果参数", order=9999)
    # 示例：结果参数（只读，用于演示结果参数分组）
    demo_result1 = Property("", name="示例：结果参数", group=PropertyGroupNames.RESULT_PARAMETERS,
                            description="用来演示如何增加结果参数", readonly=True, order=9999)

    def create_result_presenter(self) -> Any:
        """为结果面板创建结果展示器。子类可重写。"""
        return None


# =============================================================================
# VisionNodeData - 核心视觉处理节点
# =============================================================================

class VisionNodeData(DemoNodeDataBase):
    """
    核心通用视觉处理节点。
    这是核心类——大多数视觉节点都继承自它。
    主要职责：
        - 维护 Mat 对象（当前图像的 NumPy 数组）
        - 提供 ResultImages 列表
        - 实现 Invoke 生命周期（查找源/来源、执行、返回结果）
        - 流程控制辅助函数：OK()、Error()、Break()
        - 图像处理管理
    """

    # UseInvokedPart - 控制输出是否进入历史记录/预览
    use_invoked_part = Property(True, name="启用输出历史记录", group=PropertyGroupNames.DISPLAY_PARAMETERS,
                                description="用于控制是否输出到历史记录和预览图像")

    def __init__(self):
        super().__init__()
        # 当前图像数据（NumPy数组）
        self._mat: np.ndarray | None = None
        # 原始图像数据（未经处理的源图像）
        self._original_mat: np.ndarray | None = None
        # 预处理后的输入图像（用于invoke_core处理）
        self._prepared_input: np.ndarray | None = None
        # 结果展示器
        self._result_presenter: Any = None

    # -- Mat（当前图像/数据） --

    @property
    def mat(self) -> np.ndarray | None:
        """获取当前图像数据"""
        return self._mat

    @mat.setter
    def mat(self, value: np.ndarray | None):
        """设置当前图像数据"""
        self._mat = value

    def get_input_mat(self, fallback: np.ndarray | None = None) -> np.ndarray | None:
        """获取用于 invoke_core 处理的有效输入图像。

        如果 _prepared_input 已设置（例如由 image_source_mode 或 ROI 逻辑设置），
        则返回 _prepared_input，否则返回 fallback（通常来自 from_node.mat）。
        这避免了修改 UI 线程可见的上游节点的 _mat。
        """
        return self._prepared_input if self._prepared_input is not None else fallback

    # -- 结果图像 --

    @property
    def result_images(self) -> list[VisionResultImage]:
        """获取结果图像列表"""
        return list(self._get_result_images())

    def _get_result_images(self):
        """生成结果图像。子类可重写以提供自定义结果。"""
        if self._mat is not None:
            yield VisionResultImage(name=f"{self.name} - 图像", image=self._mat)

    # -- 结果展示器 --

    @property
    def result_presenter(self) -> Any:
        """获取结果展示器"""
        return self._result_presenter

    @result_presenter.setter
    def result_presenter(self, value: Any):
        """设置结果展示器"""
        self._result_presenter = value

    # -- 主要的 invoke 方法 --

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """工作流引擎调用的入口点。

        1. 查找源节点（ISrcVisionNodeData）
        2. 查找上游节点（IVisionNodeData）
        3. 传递上游的原始图像
        4. 调用 InvokeAction 执行实际处理
        """
        # 查找源节点（数据来源）
        src_data = self._find_source_node(diagram)
        # 查找上游节点
        from_data = self._find_from_node(diagram, previors)

        # 传递上游的原始图像，使每个节点都能访问未处理的源图像
        if isinstance(from_data, VisionNodeData):
            upstream_original = getattr(from_data, '_original_mat', None)
            if upstream_original is not None:
                self._original_mat = upstream_original
            elif from_data.mat is not None:
                self._original_mat = from_data.mat.copy()

        # 执行核心处理
        return self._invoke_action(lambda: self.invoke_core(src_data, from_data or src_data, diagram))

    def update_invoke_current(self):
        """从第一个上游节点单步执行。"""
        # 检查图表数据是否存在
        if self.diagram_data is None:
            return
        # 如果工作流正在运行，则不执行
        if hasattr(self.diagram_data, 'state') and self.diagram_data.state.name == "RUNNING":
            return

        # 查找源节点
        src_data = self._find_source_node(self.diagram_data)
        # 获取上游节点列表
        from_nodes = self.from_node_datas

        # 根据上游节点数量确定 from_data
        if len(from_nodes) == 0:
            from_data = self
        elif len(from_nodes) > 1:
            return  # 多输入时无法自动选择
        else:
            from_data = from_nodes[0]

        # 验证输入有效并执行
        if isinstance(from_data, VisionNodeData) and from_data.mat is not None:
            if not self.is_valid(from_data.mat):
                return
            result = self._invoke_action(lambda: self.invoke_core(src_data, from_data, self.diagram_data))
            # 更新图表的结果图像源
            if hasattr(self.diagram_data, 'result_image_source'):
                self.diagram_data.result_image_source = self._result_image_source

    def _invoke_action(self, action: Callable[[], FlowableResult]) -> FlowableResult:
        """包装实际的 invoke 调用，管理 Mat 生命周期。

        1. 清除之前的结果展示器
        2. 执行动作
        3. 释放旧的 Mat，设置新的 Mat
        4. 更新结果图像源
        5. 必要时创建结果展示器
        """
        # 清除之前的结果展示器
        self._result_presenter = None
        # 发布节点开始执行事件
        event_system.publish(EventType.NODE_STARTED, sender=self)

        # 执行核心处理
        result = action()

        # 如果新 mat 不是旧 mat，则释放旧 mat
        if self._mat is not None and result.value is not self._mat:
            self._mat = None  # 旧 mat 将被 GC 回收

        # 更新当前图像和消息
        self._mat = result.value
        self.message = result.message

        # 更新结果图像源
        if self.use_result_image_source:
            self._update_result_image_source()

        # 创建结果展示器（如果尚未创建）
        if self._result_presenter is None:
            self._result_presenter = self.create_result_presenter()

        # 先写入历史记录，再发布事件
        # 通过 workflow.on_history_changed() 注册的回调（如 ResultPanel）
        # 在这里同步触发，并使用 Qt::QueuedConnection 调度到主线程，
        # 以保证 QTableWidget 的线程安全访问
        state = "Success" if result.is_ok else "Error"
        ts = time.strftime("%H:%M:%S")
        if self.diagram_data and hasattr(self.diagram_data, 'on_node_completed'):
            self.diagram_data.on_node_completed(self, state, ts)

        # 记录错误状态（供 update_from_node / refresh_all_node_states 读取）
        self._last_error = result.is_error

        # 发布事件
        if result.is_ok:
            event_system.publish(EventType.NODE_COMPLETED, sender=self, result=result)
        elif result.is_error:
            event_system.publish(EventType.NODE_ERROR, sender=self, result=result)

        return result

    # -- 子类必须实现的抽象方法 --

    def is_valid(self, mat: np.ndarray) -> bool:
        """检查输入图像是否有效。子类可重写。"""
        return mat is not None

    @abstractmethod
    def invoke_core(self, src_image_node_data: "VisionNodeData | None",
                    from_node_data: "VisionNodeData | None",
                    diagram: "WorkflowEngine") -> FlowableResult:
        """核心处理逻辑。子类实现此方法。

        参数：
            src_image_node_data: 源图像节点（数据来源）
            from_node_data: 直接上游节点
            diagram: 工作流引擎上下文

        返回：
            包含处理后的图像和元数据的 FlowableResult
        """
        ...

    def _update_result_image_source(self):
        """更新图像结果图像源"""
        self._result_image_source = self._mat if self._mat is not None else None

    # -- 流程控制辅助函数 --

    def ok(self, mat: np.ndarray | None, message: str = "运行成功",
           result_presenter: Any = None) -> FlowableResult:
        """返回成功结果"""
        self.message = message
        if result_presenter is not None:
            self._result_presenter = result_presenter
        return FlowableResult.ok(mat, message)

    def error(self, mat: np.ndarray | None = None, message: str = "运行错误") -> FlowableResult:
        """返回错误结果"""
        self.message = message
        return FlowableResult.error(mat, message)

    def break_(self, mat: np.ndarray | None = None, message: str = "不满足条件返回") -> FlowableResult:
        """返回中断结果（流程在此分支停止）"""
        self.message = message
        return FlowableResult.break_(mat, message)

    # -- 内部辅助方法 --

    def _find_source_node(self, diagram: "WorkflowEngine") -> "VisionNodeData | None":
        """查找图表中的源节点（数据来源）"""
        if diagram is None:
            return None
        # 获取所有起始节点
        starts = diagram.get_start_nodes()
        for node in starts:
            if isinstance(node, VisionNodeData):
                return node
        return None

    def _find_from_node(self, diagram: "WorkflowEngine",
                        previors: LinkData | None) -> "VisionNodeData | None":
        """从连线数据中查找直接上游节点"""
        if previors is not None and diagram is not None:
            node = diagram.get_node_by_id(previors.from_node_id)
            if isinstance(node, VisionNodeData):
                return node
        # 后备方案：使用第一个 from_node_data
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData):
                return n
        return None

    # -- 序列化 --

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        data["use_invoked_part"] = self.use_invoked_part
        return data

    def dispose(self):
        """释放 Mat 内存和结果图像"""
        super().dispose()
        self._mat = None
        self._result_presenter = None


# =============================================================================
# ROINodeData - ROI支持（NoROI / DrawROI / FromROI / InputROI）
# =============================================================================

class ROIBase:
    """ROI定义的基类。"""

    def __init__(self, roi_type: str = ""):
        # ROI名称，未指定时使用类名
        self.name = roi_type or self.__class__.__name__

    def to_dict(self) -> dict:
        """序列化ROI对象为字典"""
        return {"type": self.__class__.__name__, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict) -> "ROIBase":
        """从字典反序列化创建ROI对象"""
        # 获取ROI类型
        roi_type = data.get("type", "ROIBase")

        # NoROI：无ROI区域
        if roi_type == "NoROI":
            return NoROI()

        # DrawROI：用户绘制的ROI区域
        if roi_type == "DrawROI":
            roi = DrawROI()
            roi.rect = tuple(data.get("rect", roi.rect))
            return roi

        # InputROI：手动输入的ROI区域（坐标+宽高）
        if roi_type == "InputROI":
            roi = InputROI()
            roi.x = int(data.get("x", roi.x))
            roi.y = int(data.get("y", roi.y))
            roi.width = int(data.get("width", roi.width))
            roi.height = int(data.get("height", roi.height))
            return roi

        # FromROI：来自上游节点的ROI
        return FromROI()


class FromROI(ROIBase):
    """从上游节点获取的ROI区域。"""

    def __init__(self, source_node: NodeBase = None):
        # 调用父类构造函数，设置ROI名称为"使用上游ROI"
        super().__init__("使用上游ROI")
        # ROI来源节点（上游节点）
        self.source_node = source_node


class DrawROI(ROIBase):
    """在图像上交互式绘制的ROI区域。"""

    def __init__(self):
        super().__init__("绘制ROI")
        self.image_source: Any = None
        self.rect: tuple | None = None  # None=未绘制，等用户在编辑器中画

    def to_dict(self) -> dict:
        """序列化为字典"""
        data = super().to_dict()
        # 将矩形区域转为列表存储
        data["rect"] = list(self.rect or (0, 0, 100, 100))
        return data


class InputROI(ROIBase):
    """手动输入数值的ROI区域。"""

    def __init__(self):
        # 调用父类构造函数，设置ROI名称为"输入ROI"
        super().__init__("输入ROI")
        # 左上角X坐标
        self.x: int = 0
        # 左上角Y坐标
        self.y: int = 0
        # ROI宽度
        self.width: int = 100
        # ROI高度
        self.height: int = 100

    def to_dict(self) -> dict:
        """序列化为字典"""
        data = super().to_dict()
        # 添加坐标和尺寸信息
        data.update({
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        })
        return data


class NoROI(ROIBase):
    """无ROI — 不应用任何感兴趣区域。"""

    def __init__(self):
        # 调用父类构造函数，设置ROI名称为"无"
        super().__init__("无")


class ROINodeData(VisionNodeData):
    """
    为视觉节点添加ROI支持。
    支持四种ROI模式：NoROI（无）、FromROI（上游）、DrawROI（交互绘制）、InputROI（手动输入）。
    默认使用 NoROI，以防止意外的ROI级联传递。
    """

    def __init__(self):
        super().__init__()
        # 无ROI模式实例
        self.no_roi = NoROI()
        # 使用上游ROI模式实例，源节点指向自身
        self.from_roi = FromROI(source_node=self)
        # 绘制ROI模式实例
        self.draw_roi = DrawROI()
        # 输入ROI模式实例
        self.input_roi = InputROI()
        # 当前激活的ROI，默认为无ROI
        self._roi: ROIBase = self.no_roi

    @property
    def roi(self) -> ROIBase:
        """获取当前激活的ROI"""
        return self._roi

    @roi.setter
    def roi(self, value: ROIBase):
        """设置当前激活的ROI"""
        self._roi = value

    def get_rois(self) -> list[ROIBase]:
        """获取所有可用的ROI选项"""
        # 更新绘制ROI的图像源为当前结果图像
        self.draw_roi.image_source = self._result_image_source
        # 返回所有ROI选项列表
        return [self.no_roi, self.from_roi, self.draw_roi, self.input_roi]

    def get_active_roi_rect(self) -> tuple | None:
        """获取当前激活的ROI矩形区域，返回 (x, y, w, h) 或 None"""
        # 无ROI模式：返回None
        if isinstance(self._roi, NoROI):
            return None
        # 绘制ROI模式：返回绘制的矩形区域
        if isinstance(self._roi, DrawROI):
            if self._roi.rect:
                return self._roi.rect
        # 输入ROI模式：返回手动输入的坐标和尺寸
        elif isinstance(self._roi, InputROI):
            return (self._roi.x, self._roi.y, self._roi.width, self._roi.height)
        # 使用上游ROI模式：递归向上游节点获取ROI
        elif isinstance(self._roi, FromROI):
            src = self._roi.source_node
            if isinstance(src, ROINodeData) and src is not self:
                return src.get_active_roi_rect()
        return None

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """执行节点处理，支持ROI裁剪"""
        # 查找上游节点
        from_data = self._find_from_node(diagram, previors)

        # 为 FromROI 模式连接上游ROI
        if isinstance(from_data, ROINodeData) and from_data is not self:
            self.from_roi.source_node = from_data

        # 传递上游的原始图像
        if isinstance(from_data, VisionNodeData):
            upstream_original = getattr(from_data, '_original_mat', None)
            if upstream_original is not None:
                self._original_mat = upstream_original
            elif from_data.mat is not None:
                self._original_mat = from_data.mat.copy()

        # 根据图像源模式确定有效的输入图像
        if from_data is not None and from_data.mat is not None:
            if hasattr(self, 'image_source_mode') and self.image_source_mode == "原图":
                input_mat = self._original_mat
            else:
                input_mat = from_data.mat
        else:
            input_mat = None

        # 获取当前节点的ROI矩形（如果不是 NoROI 模式）
        roi_rect = self.get_active_roi_rect() if not isinstance(self._roi, NoROI) else None

        # 验证ROI矩形有效性（边界检查和裁剪）
        if roi_rect is not None and input_mat is not None:
            x, y, w, h = int(roi_rect[0]), int(roi_rect[1]), int(roi_rect[2]), int(roi_rect[3])
            h_img, w_img = input_mat.shape[:2]
            # 裁剪到图像边界内
            x, y = max(0, x), max(0, y)
            w, h = min(w, w_img - x), min(h, h_img - y)
            if w <= 0 or h <= 0:
                roi_rect = None  # ROI无效，走无ROI路径

        # 有ROI时的处理
        if roi_rect is not None and input_mat is not None:
            x, y, w, h = int(roi_rect[0]), int(roi_rect[1]), int(roi_rect[2]), int(roi_rect[3])
            h_img, w_img = input_mat.shape[:2]
            x, y = max(0, x), max(0, y)
            w, h = min(w, w_img - x), min(h, h_img - y)
            self._prepared_input = input_mat[y:y+h, x:x+w]
            result = super().invoke(previors, diagram)
            self._prepared_input = None
        else:
            # 无ROI时的处理
            if from_data is not None and input_mat is not from_data.mat:
                self._prepared_input = input_mat
                result = super().invoke(previors, diagram)
                self._prepared_input = None
            else:
                result = super().invoke(previors, diagram)

        # 更新绘制ROI的图像源
        self.draw_roi.image_source = self._result_image_source
        return result

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        # 保存当前ROI配置
        data["roi"] = self._roi.to_dict() if self._roi is not None else None
        return data

    def restore_from_dict(self, data: dict) -> "ROINodeData":
        """从字典反序列化恢复节点状态"""
        super().restore_from_dict(data)
        roi_data = data.get("roi")
        if roi_data:
            self._roi = ROIBase.from_dict(roi_data)
        # 将反序列化的ROI替换为实例中的对应对象
        if isinstance(self._roi, NoROI):
            self._roi = self.no_roi
        elif isinstance(self._roi, DrawROI):
            r = tuple(self._roi.rect) if self._roi.rect else None
            if r == (0, 0, 100, 100):
                r = None  # 忽略旧版预设值
            self.draw_roi.rect = r
            self._roi = self.draw_roi
        elif isinstance(self._roi, InputROI):
            self.input_roi.x = int(self._roi.x)
            self.input_roi.y = int(self._roi.y)
            self.input_roi.width = int(self._roi.width)
            self.input_roi.height = int(self._roi.height)
            self._roi = self.input_roi
        elif isinstance(self._roi, FromROI):
            self._roi = self.from_roi
        else:
            self._roi = self.no_roi
        return self

# =============================================================================
# SelectableResultImageNodeData - 选择使用哪个上游节点的结果图像
# =============================================================================

class SelectableResultImageNodeData(ROINodeData):
    """允许选择处理哪个上游节点的结果图像。"""

    def __init__(self):
        super().__init__()
        # 当前选中的结果图像
        self._selected_result_image: VisionResultImage | None = None

    @property
    def selected_result_image(self) -> VisionResultImage | None:
        """获取当前选中的结果图像"""
        return self._selected_result_image

    @selected_result_image.setter
    def selected_result_image(self, value: VisionResultImage | None):
        """设置当前选中的结果图像"""
        self._selected_result_image = value

    def get_selectable_src_node_datas(self) -> list[VisionResultImage]:
        """获取所有上游 VisionNodeData 节点的结果图像列表"""
        results: list[VisionResultImage] = []
        # 遍历所有上游节点
        for node in self.get_all_from_node_datas():
            # 如果是视觉节点，将其结果图像添加到列表中
            if isinstance(node, VisionNodeData):
                results.extend(node.result_images)
        return results

# =============================================================================
# OpenCVNodeDataBase - OpenCV特定的Mat处理
# =============================================================================

class OpenCVNodeDataBase(SelectableResultImageNodeData):
    """基于OpenCV的视觉节点基类。Mat就是numpy.ndarray。"""

    # 图像源选择属性：可选择使用"处理后图片"（上游节点输出）或"原图"（数据源原始图像）
    image_source_mode = Property(
        "处理后图片", name="图像源", group=PropertyGroupNames.BASE_PARAMETERS,
        description="选择输入图像来源：处理后图片(上游节点输出) 或 原图(数据源原始图像)",
        editor="choices", choices=["处理后图片", "原图"], order=1000,
    )

    def is_valid(self, mat: np.ndarray) -> bool:
        """检查输入图像是否有效：非空且包含数据"""
        return mat is not None and mat.size > 0

    def _update_result_image_source(self):
        """将numpy数组转换为可显示的格式（由GUI层处理）。

        在GUI中，这将转换为QImage/QPixmap。在核心层，我们存储numpy数组，
        让GUI层处理转换。
        """
        # 存储numpy数组作为结果图像源
        self._result_image_source = self._mat

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        # 保存选中的结果图像名称（如果有）
        if self._selected_result_image:
            data["selected_result_image"] = self._selected_result_image.name
        return data

# =============================================================================
# SrcFilesVisionNodeData - 基于文件的图像源节点
# =============================================================================

class SrcFilesVisionNodeData(ROINodeData):
    """从文件加载图像的节点基类。
    提供文件列表管理、图像属性（宽度/高度/颜色类型）。
    """

    # 图像宽度（只读，用于显示结果信息）
    pixel_width = Property(0, name="图像宽度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 图像高度（只读，用于显示结果信息）
    pixel_height = Property(0, name="图像高度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 颜色类型（只读，如灰度、RGB、BGR等）
    image_color_type = Property(0, name="颜色类型", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 是否使用所有图像（True：循环使用所有图像，False：只使用当前图像）
    use_all_image = Property(False, name="使用所有图像", group=PropertyGroupNames.RUN_PARAMETERS)
    # 是否自动切换（True：自动切换到下一张，False：手动切换）
    use_auto_switch = Property(True, name="自动切换", group=PropertyGroupNames.RUN_PARAMETERS)
    # 当前选中的文件路径
    src_file_path = Property("", name="当前文件", group=PropertyGroupNames.RUN_PARAMETERS)
    # 执行延迟（毫秒），用于控制连续执行时的帧率
    invoke_milliseconds_delay = Property(33, name="执行延迟", group=PropertyGroupNames.FLOW_PARAMETERS,
                                         description="连续执行时，每次采集图像的目标间隔（毫秒）。33ms≈30FPS，500ms≈2FPS")

    def __init__(self):
        # 文件路径列表
        self.src_file_paths: list[str] = []
        super().__init__()
        # 此节点可以作为流程起始节点
        self.use_start = True

    # 支持的图像文件扩展名列表
    _IMAGE_EXTENSIONS = (
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
        ".webp", ".svg", ".tga", ".dds", ".eps", ".pdf",
    )

    @classmethod
    def collect_image_files(cls, folder_path: str, recursive: bool = True,
                            image_extensions: tuple = None) -> list[str]:
        """从文件夹中收集所有图像文件，可选择是否递归扫描子目录。

        参数：
            folder_path: 要扫描的根文件夹路径
            recursive: 是否递归扫描子目录
            image_extensions: 覆盖默认的图像扩展名元组

        返回：
            匹配图像扩展名的文件绝对路径列表（已排序）
        """
        if image_extensions is None:
            image_extensions = cls._IMAGE_EXTENSIONS

        result: list[str] = []

        def _scan(directory: str):
            try:
                entries = os.listdir(directory)
            except (PermissionError, OSError):
                return

            for name in sorted(entries):
                full_path = os.path.join(directory, name)
                # 在Windows上跳过隐藏和系统文件
                try:
                    # import stat
                    attrs = os.stat(full_path).st_file_attributes if os.name == 'nt' else 0
                    if attrs & (2 | 4):  # hidden | system
                        continue
                except (OSError, AttributeError):
                    pass  # 无法获取属性则继续

                if os.path.isdir(full_path):
                    if recursive:
                        _scan(full_path)
                elif name.lower().endswith(image_extensions):
                    result.append(full_path)

        _scan(folder_path)
        return result

    def add_files_from_folder(self, folder_path: str, recursive: bool = True,
                              image_extensions: tuple = None):
        """从文件夹添加所有图像文件
          - 默认递归扫描子目录
          - 跳过隐藏和系统文件
          - 仅当 SrcFilePath 之前为空时才设置它
        """
        new_files = self.collect_image_files(folder_path, recursive, image_extensions)
        if not new_files:
            return
        self.src_file_paths.extend(new_files)
        # 如果当前没有选中文件，则选中第一个
        if not self.src_file_path:
            self.src_file_path = self.src_file_paths[0]

    def add_files(self, file_paths: list[str]):
        """添加指定的图像文件"""
        self.src_file_paths.extend(file_paths)
        # 如果当前没有选中文件且列表非空，则选中第一个
        if self.src_file_paths and not self.src_file_path:
            self.src_file_path = self.src_file_paths[0]

    def clear_files(self):
        """清空所有文件路径"""
        self.src_file_paths.clear()
        self.src_file_path = ""

    def delete_current_file(self):
        """从列表中移除当前选中的文件"""
        if self.src_file_path and self.src_file_path in self.src_file_paths:
            idx = self.src_file_paths.index(self.src_file_path)
            self.src_file_paths.remove(self.src_file_path)
            if self.src_file_paths:
                # 选择前一个或第一个文件
                new_idx = min(idx, len(self.src_file_paths) - 1)
                self.src_file_path = self.src_file_paths[new_idx]
            else:
                self.src_file_path = ""

    def move_next(self) -> bool:
        """切换到列表中的下一个文件。返回是否成功循环。
          → 索引 = SrcFilePaths.IndexOf(SrcFilePath)
          → 索引 = 索引 < 总数-1 ? 索引+1 : 0
          → SrcFilePath = SrcFilePaths[索引]
        """
        if not self.src_file_paths:
            return False
        # 如果当前文件不在列表中，选中第一个
        if self.src_file_path not in self.src_file_paths:
            self.src_file_path = self.src_file_paths[0]
            return True
        idx = self.src_file_paths.index(self.src_file_path)
        next_idx = (idx + 1) % len(self.src_file_paths)
        # 如果循环到开头但不使用所有图像，则返回False
        if next_idx == 0 and not self.use_all_image:
            return False
        self.src_file_path = self.src_file_paths[next_idx]
        return True

    def move_prev(self) -> bool:
        """切换到列表中的上一个文件。返回是否成功循环。

        与 move_next() 相反方向，用于"上一张"单步导航。
        """
        if not self.src_file_paths:
            return False
        # 如果当前文件不在列表中，选中最后一个
        if self.src_file_path not in self.src_file_paths:
            self.src_file_path = self.src_file_paths[-1]
            return True
        idx = self.src_file_paths.index(self.src_file_path)
        prev_idx = idx - 1
        if prev_idx < 0:
            if not self.use_all_image:
                return False
            prev_idx = len(self.src_file_paths) - 1
        self.src_file_path = self.src_file_paths[prev_idx]
        return True

    def is_valid_file_list(self) -> tuple[bool, str]:
        """检查文件列表是否有效。返回 (是否有效, 消息)"""
        if not self.src_file_paths:
            return False, "请选择数据源中的图片"
        if self.src_file_path is None:
            self.src_file_path = self.src_file_paths[0]
        return self.src_file_path is not None, ""

    def load_default(self):
        """加载默认设置：从 assets/images 文件夹添加示例图片"""
        super().load_default()
        # 获取 assets/images 文件夹路径
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images")
        if os.path.isdir(assets_dir):
            self.add_files_from_folder(assets_dir)
        self.src_file_path = ""

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        data["src_file_paths"] = list(self.src_file_paths)
        data["src_file_path"] = self.src_file_path
        data["use_all_image"] = self.use_all_image
        data["use_auto_switch"] = self.use_auto_switch
        data["invoke_milliseconds_delay"] = self.invoke_milliseconds_delay
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "SrcFilesVisionNodeData":
        """从字典反序列化节点"""
        node = super().from_dict(data)
        node.src_file_paths = data.get("src_file_paths", [])
        node.src_file_path = data.get("src_file_path", "")
        return node

# =============================================================================
# Base64MatchingNodeData - 模板匹配基类
# =============================================================================

class Base64MatchingNodeData(VisionNodeData):
    """使用Base64编码模板图像的模板匹配节点的基类。"""

    # 匹配数量结果（只读）
    matching_count_result = Property(0, name="匹配数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 置信度结果（只读）
    confidence = Property(0.0, name="置信度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 是否匹配到目标（只读，供条件分支使用）
    matched = Property(False, name="是否匹配", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    # 匹配矩形坐标（只读）
    match_x = Property(0, name="匹配X", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_y = Property(0, name="匹配Y", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_w = Property(0, name="匹配宽度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_h = Property(0, name="匹配高度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        # Base64编码的模板图像字符串
        self._base64_string: str = ""

    @property
    def base64_string(self) -> str:
        """获取Base64编码的模板图像"""
        return self._base64_string

    @base64_string.setter
    def base64_string(self, value: str):
        """设置Base64编码的模板图像"""
        self._base64_string = value

    def set_template_from_image(self, image: np.ndarray):
        """将numpy图像编码为Base64字符串，用于模板存储。"""
        # 将图像编码为PNG格式
        _, buffer = cv2.imencode(".png", image)
        # 将二进制数据编码为Base64字符串
        self._base64_string = base64.b64encode(buffer).decode("utf-8")

    def get_template_image(self) -> np.ndarray | None:
        """将Base64模板解码为numpy图像。"""
        if not self._base64_string:
            return None

        # 将Base64字符串解码为二进制数据
        buffer = base64.b64decode(self._base64_string)
        # 将二进制数据转为numpy数组
        arr = np.frombuffer(buffer, dtype=np.uint8)
        # 解码为彩色图像
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    # ── ROI 暴露：将匹配结果作为下游可用的 ROI ──

    def get_active_roi_rect(self) -> tuple | None:
        """如果匹配成功，返回匹配矩形作为 ROI，供下游节点"来自上游"截取。"""
        if getattr(self, "matched", False):
            x, y, w, h = self.match_x, self.match_y, self.match_w, self.match_h
            if w > 0 and h > 0:
                return (int(x), int(y), int(w), int(h))
        return super().get_active_roi_rect()

    # ── 序列化 ──

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["base64_string"] = self._base64_string
        return data

    def restore_from_dict(self, data: dict) -> "Base64MatchingNodeData":
        super().restore_from_dict(data)
        self._base64_string = data.get("base64_string", "")
        return self

    @classmethod
    def from_dict(cls, data: dict) -> "Base64MatchingNodeData":
        node = super().from_dict(data)
        node._base64_string = data.get("base64_string", "")
        return node


# =============================================================================
# LogicModuleNode - 逻辑模块标记接口
# =============================================================================

class LogicModuleNode:
    """标记接口：实现此接口的节点自动归入"逻辑模块"分组。
    解耦了"属于逻辑模块"和"是 ConditionNodeData 子类"之间的强绑定。
    """
    pass


# ConditionNodeData - 条件分支节点
# =============================================================================

class ConditionNodeData(VisionNodeData):
    """基于上游节点结果评估条件并实现流程分支的节点。
    """

    def __init__(self):
        super().__init__()
        self.use_invoked_part = False

    # -- ConditionsPrensenter (lazy init) --

    @property
    def conditions_presenter(self):
        """获取条件分支集合管理器。延迟导入避免循环依赖。"""
        if getattr(self, '_conditions_presenter', None) is None:
            from core.conditions import ConditionsPrensenter
            self._conditions_presenter = ConditionsPrensenter()
        return self._conditions_presenter

    @conditions_presenter.setter
    def conditions_presenter(self, value):
        self._conditions_presenter = value

    # -- 兼容旧 API (deprecated, 映射到 presenter.branches[0]) --

    @property
    def conditions(self) -> list:
        """[兼容] 获取旧版 VisionPropertyCondition 列表。新代码应使用 conditions_presenter.branches。"""
        return self._legacy_conditions()

    @conditions.setter
    def conditions(self, value: list):
        self._set_legacy_conditions(value)

    def _legacy_conditions(self) -> list:
        """将 presenter 的 branches 转回旧版 VisionPropertyCondition 格式（仅用于兼容）。"""
        result = []
        for branch in self.conditions_presenter.branches:
            for cond in branch.conditions:
                result.append(VisionPropertyCondition(
                    property_name=cond.property_name,
                    operator=cond.filter_operate.value,
                    threshold=cond.value,
                    output_node_id=branch.selected_output_node_id,
                ))
        return result

    def _set_legacy_conditions(self, value: list):
        from core.conditions import ConditionBranch, PropertyCondition, FilterOperate
        self.conditions_presenter.clear()
        for old in value:
            op_name = PropertyCondition._migrate_operator(getattr(old, 'operator', '>'))
            pc = PropertyCondition(
                property_name=getattr(old, 'property_name', ''),
                filter_operate=FilterOperate[op_name],
                value=getattr(old, 'threshold', ''),
            )
            branch = ConditionBranch()
            branch.selected_output_node_id = getattr(old, 'output_node_id', '')
            branch.conditions = [pc]
            self.conditions_presenter.branches.append(branch)

    def add_condition(self, condition: "VisionPropertyCondition"):
        from core.conditions import ConditionBranch, PropertyCondition, FilterOperate
        op_name = PropertyCondition._migrate_operator(condition.operator)
        pc = PropertyCondition(
            property_name=condition.property_name,
            filter_operate=FilterOperate[op_name],
            value=condition.threshold,
        )
        branch = ConditionBranch()
        branch.selected_output_node_id = condition.output_node_id
        branch.conditions = [pc]
        self.conditions_presenter.branches.append(branch)

    def remove_condition(self, index: int):
        self.conditions_presenter.remove_branch(index)

    def evaluate_conditions(self, upstream_results: dict[str, Any]) -> list["VisionPropertyCondition"]:
        upstream_snapshots = self.conditions_presenter.collect_upstream_snapshots()
        matches = []
        for branch in self.conditions_presenter.branches:
            snap = upstream_snapshots.get(branch.selected_input_node_id, {})
            if branch.is_match(snap):
                for cond in branch.conditions:
                    matches.append(VisionPropertyCondition(
                        property_name=cond.property_name,
                        operator=cond.filter_operate.value,
                        threshold=cond.value,
                        output_node_id=branch.selected_output_node_id,
                    ))
        return matches

    def get_condition_candidates(self) -> list[tuple[str, Any]]:
        """为条件编辑器收集可评估的上游节点属性。返回 [(node_name.prop_name, value), ...]"""
        candidates: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for node in self.from_node_datas:
            if not isinstance(node, VisionNodeData):
                continue
            node_name = node.name or type(node).__name__
            for prop_name, prop_desc in node.get_property_descriptors():
                key = f"{node_name}.{prop_name}"
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((key, getattr(node, prop_name, None)))
            if node.message and f"{node_name}.message" not in seen:
                seen.add(f"{node_name}.message")
                candidates.append((f"{node_name}.message", node.message))
        return candidates

    def collect_upstream_results(self) -> dict[str, Any]:
        return dict(self.get_condition_candidates())

    # -- 核心调用 --

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """执行条件分支逻辑。委托给 ConditionsPrensenter 评估。
        实际路由由 get_flowable_output_links() 控制。
        """
        from_node = None
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData):
                from_node = n
                break

        src_data = self._find_source_node(diagram)

        # 加载节点数据到 presenter（恢复节点引用）
        self.conditions_presenter.load_data(self)

        # 调用 invoke_core 执行透传
        return self._invoke_action(lambda: self.invoke_core(src_data, from_node or src_data, diagram))

    def get_flowable_output_links(self, diagram: "WorkflowEngine") -> list["LinkData"]:
        """根据条件分支匹配结果，路由到对应的输出端口。
        """
        self.conditions_presenter.load_data(self)
        upstream_snapshots = self.conditions_presenter.collect_upstream_snapshots()
        matching_output_ids = self.conditions_presenter.get_matching_output_node_ids(upstream_snapshots)

        if not matching_output_ids:
            # 无匹配：检查是否有活动端口名（如 PixelThresholdConditionNode 设置的）
            active_port_name = getattr(self, '_active_output_port_name', None)
            if active_port_name:
                active_ids = {p.port_id for p in self.get_output_ports()
                             if p.name == active_port_name}
                return [l for l in (diagram.get_all_links() if diagram else [])
                        if l.from_node_id == self.node_id and l.from_port_id in active_ids]
            return []

        # 路由到匹配分支指向的输出节点
        result: list["LinkData"] = []
        for link in (diagram.get_all_links() if diagram else []):
            if link.from_node_id != self.node_id:
                continue
            if link.to_node_id in matching_output_ids:
                result.append(link)
        return result

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        return self.ok(from_node_data.mat if from_node_data else None)

    # -- 序列化 --

    def to_dict(self) -> dict:
        data = super().to_dict()
        presenter = getattr(self, '_conditions_presenter', None)
        if presenter is not None:
            data["conditions_presenter"] = presenter.to_dict()
        return data

    def restore_from_dict(self, data: dict) -> "ConditionNodeData":
        super().restore_from_dict(data)
        from core.conditions import ConditionsPrensenter
        presenter_data = data.get("conditions_presenter")
        if presenter_data is not None:
            self._conditions_presenter = ConditionsPrensenter.from_dict(presenter_data)
        elif "conditions" in data:
            # 兼容旧格式
            self._conditions_presenter = ConditionsPrensenter.from_dict({"conditions": data["conditions"]})
        return self


# =============================================================================
# VisionPropertyCondition — 旧版条件规则（保留用于兼容）
# =============================================================================

class VisionPropertyCondition:
    """[兼容] 旧版单条条件规则。新代码应使用 core.conditions.PropertyCondition + ConditionBranch。

    该类的功能已迁移至:
      - PropertyCondition (单条过滤)
      - ConditionBranch (分支 = 输入节点 + 条件 + 输出节点)
      - ConditionsPrensenter (分支集合管理)

    保留此类用于:
      1. GUI 兼容 (condition_editor.py)
      2. 旧项目文件反序列化
    """

    SUPPORTED_OPERATORS = (">", "<", ">=", "<=", "==", "!=", "contains", "not contains")

    def __init__(self, property_name: str = "", operator: str = ">",
                 threshold: Any = 0.0, output_node_id: str = ""):
        self.property_name = property_name
        self.operator = operator
        self.threshold = threshold
        self.output_node_id = output_node_id

    def display_text(self) -> str:
        target = f" → {self.output_node_id}" if self.output_node_id else ""
        return f"{self.property_name} {self.operator} {self.threshold}{target}"

    def evaluate(self, upstream_results: dict[str, Any]) -> bool:
        from core.conditions import PropertyCondition, FilterOperate
        op_name = PropertyCondition._migrate_operator(self.operator)
        try:
            filter_op = FilterOperate[op_name]
        except KeyError:
            filter_op = FilterOperate.EQUALS
        pc = PropertyCondition(
            property_name=self.property_name,
            filter_operate=filter_op,
            value=self.threshold,
        )
        return pc.is_match(upstream_results)

    def to_dict(self) -> dict:
        return {
            "property_name": self.property_name,
            "operator": self.operator,
            "threshold": self.threshold,
            "output_node_id": self.output_node_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VisionPropertyCondition":
        return cls(
            property_name=data.get("property_name", ""),
            operator=data.get("operator", ">"),
            threshold=data.get("threshold", 0.0),
            output_node_id=data.get("output_node_id", ""),
        )


# =============================================================================
# WaitAllParallelNodeData - 并行执行同步屏障
# =============================================================================

class WaitAllParallelNodeData(VisionNodeData, LogicModuleNode):
    """等待所有并行上游节点完成后才继续执行的同步屏障节点。

    作为同步屏障：统计来自并行分支的调用次数，
    只有当所有并行前驱节点都完成后才继续执行。
    """
    # 节点分组（用于UI分类）
    __group__ = "逻辑模块"

    def __init__(self):
        super().__init__()
        # 节点显示名称
        self.name = "并行等待"
        # 已完成的并行分支计数
        self._result_count = 0

    def invoke(self, previors: LinkData | None, diagram: "WorkflowEngine") -> FlowableResult:
        """统计并行调用次数。只有当所有分支都完成时才继续执行。"""
        # 获取第一个上游节点
        from_node = None
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData):
                from_node = n
                break

        # 查找源节点
        src_data = self._find_source_node(diagram)

        # 调用每个并行分支完成时的处理
        self.on_parallel_from_invoked(src_data, from_node, diagram)
        # 增加完成计数
        self._result_count += 1

        # 统计并行模式的上游节点数量
        parallel_count = sum(1 for n in self.from_node_datas
                           if hasattr(n, 'invoke_mode') and n.invoke_mode == FlowableInvokeMode.PARALLEL)

        # 如果所有并行分支都已完成
        if self._result_count >= parallel_count:
            # 重置计数
            self._result_count = 0
            # 调用所有并行分支完成时的处理
            return self._invoke_action(lambda: self.on_all_parallels_invoked(src_data, from_node, diagram))
        else:
            # 还有分支未完成，中断等待
            return self.break_(from_node.mat if from_node else None, "等待其他并行分支完成")

    def on_parallel_from_invoked(self, src_image_node_data, from_node, diagram):
        """每个并行分支完成时调用。子类可重写以累积结果。"""
        pass

    def on_all_parallels_invoked(self, src_image_node_data, from_node, diagram) -> FlowableResult:
        """所有并行分支都完成时调用。子类可重写以合并结果。"""
        return self.ok(from_node.mat if from_node else None)

    def _update_result_image_source(self):
        """更新结果图像源"""
        self._result_image_source = self._mat

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        """核心调用方法（透传上游图像）"""
        return self.ok(from_node_data.mat if from_node_data else None)

    def to_dict(self) -> dict:
        """序列化节点为字典"""
        data = super().to_dict()
        data["result_count"] = self._result_count
        return data