"""
算子基类 - 所有视觉算子的抽象基类
纯逻辑实现，不依赖任何UI框架
"""

from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import uuid

from .events import EventBus, Event, EventType
from .data_packet import DataPacket, DataType


class ParamType(Enum):
    """参数类型枚举"""
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "str"
    SLIDER = "slider"  # 整数滑块
    FLOAT_SLIDER = "float_slider"
    RANGE = "range"  # 范围选择
    COLOR = "color"
    POINT = "point"
    RECT = "rect"
    ENUM = "enum"  # 枚举下拉


@dataclass
class NodeParameter:
    """节点参数定义"""
    name: str  # 参数名（唯一标识）
    label: str  # 显示名称
    type: ParamType  # 参数类型
    default: Any  # 默认值
    min: Optional[float] = None  # 最小值
    max: Optional[float] = None  # 最大值
    step: Optional[float] = None  # 步长
    options: Optional[List[str]] = None  # ENUM类型的选项


@dataclass
class Socket:
    """端口定义"""
    name: str
    data_type: DataType
    is_input: bool
    description: str = ""
    multi_connection: bool = False  # 是否允许多连接


class NodeBase(ABC):
    """
    所有算子的基类
    不包含任何UI代码，通过EventBus发送事件
    """

    def __init__(self, node_id: str = None):
        self.node_id = node_id or str(uuid.uuid4())
        self.name = "Node"
        self.category = "通用"
        self.description = ""

        # 端口定义（子类在__init__中定义）
        self.input_sockets: List[Socket] = []
        self.output_sockets: List[Socket] = []

        # 参数定义
        self.parameters: Dict[str, NodeParameter] = {}
        self._param_values: Dict[str, Any] = {}

        # 运行时状态
        self._last_inputs: Dict[str, Any] = {}
        self._last_outputs: Dict[str, Any] = {}
        self._cache_hash: Optional[int] = None

        # 位置信息（用于序列化）
        self.pos_x: float = 0
        self.pos_y: float = 0

        # 事件总线
        self._event_bus = EventBus()

        # 初始化参数默认值
        for name, param in self.parameters.items():
            self._param_values[name] = param.default

    # ========== 子类必须实现的方法 ==========

    @abstractmethod
    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        核心执行方法，子类必须实现

        Args:
            inputs: 输入端口名 -> 值的字典

        Returns:
            输出端口名 -> 值的字典
        """
        pass

    # ========== 可选重写的方法 ==========

    def on_init(self):
        """节点初始化时调用（在构造函数之后）"""
        pass

    def on_param_changed(self, name: str, value: Any):
        """参数改变时的回调"""
        pass

    def on_execute_start(self, inputs: Dict[str, Any]):
        """执行开始前的回调"""
        pass

    def on_execute_end(self, outputs: Dict[str, Any]):
        """执行结束后的回调"""
        pass

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """验证输入数据的有效性"""
        for socket in self.input_sockets:
            if socket.name not in inputs:
                if not self._optional_input(socket.name):
                    self._event_bus.emit_log("ERROR", f"节点[{self.name}]缺少输入: {socket.name}")
                    return False
        return True

    def _optional_input(self, socket_name: str) -> bool:
        """判断输入是否可选（默认全部必需）"""
        return False

    # ========== 公开API ==========

    def get_param(self, name: str) -> Any:
        """获取参数值"""
        return self._param_values.get(name, self.parameters.get(name, None))

    def set_param(self, name: str, value: Any) -> bool:
        """设置参数值"""
        if name not in self.parameters:
            return False

        # 类型验证和转换
        param_def = self.parameters[name]
        try:
            if param_def.type in [ParamType.INT, ParamType.SLIDER]:
                value = int(value)
            elif param_def.type in [ParamType.FLOAT, ParamType.FLOAT_SLIDER]:
                value = float(value)
            elif param_def.type == ParamType.BOOL:
                value = bool(value)

            # 范围验证
            if param_def.min is not None and value < param_def.min:
                value = param_def.min
            if param_def.max is not None and value > param_def.max:
                value = param_def.max
        except (ValueError, TypeError):
            return False

        old_value = self._param_values.get(name)
        if old_value != value:
            self._param_values[name] = value
            self._cache_hash = None  # 清除缓存
            self.on_param_changed(name, value)

            # 发送事件
            self._event_bus.emit(Event(
                type=EventType.NODE_PARAM_CHANGED,
                data={
                    "node_id": self.node_id,
                    "param_name": name,
                    "old_value": old_value,
                    "new_value": value
                }
            ))

        return True

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行节点（带缓存机制）
        外部调用此方法
        """
        # 检查缓存
        cache_key = self._compute_cache_key(inputs)
        if self._cache_hash == cache_key and self._last_outputs:
            return self._last_outputs

        # 验证输入
        if not self.validate_inputs(inputs):
            return {}

        # 保存输入
        self._last_inputs = inputs.copy()

        # 执行前回调
        self.on_execute_start(inputs)

        # 执行
        try:
            outputs = self.evaluate(inputs)
        except Exception as e:
            self._event_bus.emit_log("ERROR", f"节点[{self.name}]执行失败: {str(e)}")
            return {}

        # 执行后回调
        self.on_execute_end(outputs)

        # 更新缓存
        self._last_outputs = outputs
        self._cache_hash = cache_key

        # 发送执行完成事件
        self._event_bus.emit(Event(
            type=EventType.NODE_EXECUTED,
            data={"node_id": self.node_id, "outputs": outputs}
        ))

        return outputs

    def _compute_cache_key(self, inputs: Dict[str, Any]) -> int:
        """计算缓存键"""
        # 使用参数值+输入哈希
        param_hash = hash(frozenset(self._param_values.items()))
        input_hash = hash(frozenset(inputs.items()))
        return hash((param_hash, input_hash))

    def get_metadata(self) -> Dict:
        """获取节点元数据"""
        return {
            "id": self.node_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "inputs": [
                {"name": s.name, "type": s.data_type.value, "description": s.description}
                for s in self.input_sockets
            ],
            "outputs": [
                {"name": s.name, "type": s.data_type.value, "description": s.description}
                for s in self.output_sockets
            ],
            "parameters": [
                {
                    "name": p.name,
                    "label": p.label,
                    "type": p.type.value,
                    "default": p.default,
                    "min": p.min,
                    "max": p.max,
                    "step": p.step,
                    "options": p.options
                }
                for p in self.parameters.values()
            ]
        }

    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "id": self.node_id,
            "type": self.__class__.__name__,
            "name": self.name,
            "params": self._param_values.copy(),
            "pos_x": self.pos_x,
            "pos_y": self.pos_y
        }

    def from_dict(self, data: Dict):
        """从字典反序列化"""
        self.node_id = data.get("id", self.node_id)
        self.name = data.get("name", self.name)
        self.pos_x = data.get("pos_x", 0)
        self.pos_y = data.get("pos_y", 0)
        for name, value in data.get("params", {}).items():
            self.set_param(name, value)