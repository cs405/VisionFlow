"""
数据包和流式结果类型
定义了工作流执行期间在节点之间传递的数据结构。
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
import numpy as np


class FlowableResultState(Enum):
    """流控制的结果状态枚举"""
    OK = "OK"          # 正常执行成功
    ERROR = "Error"    # 执行出错
    BREAK = "Break"    # 中断（如条件不满足时跳出循环）
    RUNNING = "Running"  # 正在运行中
    NONE = "None"      # 无状态


class FlowableInvokeMode(Enum):
    """节点在流程管道中的调用方式"""
    SEQUENTIAL = auto()  # 顺序执行
    PARALLEL = auto()    # 并行执行


@dataclass
class FlowableResult:
    """
    节点调用的结果。携带数据、状态和消息。
    """
    value: Any = None                              # 结果值
    message: str = ""                             # 附加消息
    state: FlowableResultState = FlowableResultState.OK  # 执行状态

    @property
    def is_ok(self) -> bool:
        """是否为成功状态"""
        return self.state == FlowableResultState.OK

    @property
    def is_error(self) -> bool:
        """是否为错误状态"""
        return self.state == FlowableResultState.ERROR

    @property
    def is_break(self) -> bool:
        """是否为中断状态"""
        return self.state == FlowableResultState.BREAK

    @classmethod
    def ok(cls, value: Any = None, message: str = "运行成功"):
        """创建成功结果"""
        return cls(value=value, message=message, state=FlowableResultState.OK)

    @classmethod
    def error(cls, value: Any = None, message: str = "运行错误"):
        """创建错误结果"""
        return cls(value=value, message=message, state=FlowableResultState.ERROR)

    @classmethod
    def break_(cls, value: Any = None, message: str = "不满足条件返回"):
        """创建中断结果（用于条件不满足时）"""
        return cls(value=value, message=message, state=FlowableResultState.BREAK)

    def __bool__(self):
        """布尔判断：成功状态返回True，否则返回False"""
        return self.state == FlowableResultState.OK


@dataclass
class DataPacket:
    """
    节点间流动的数据包。包含图像数据及元数据。
    在 Python 中使用 numpy.ndarray 表示图像，
    使用 DataPacket 进行更丰富的数据交换（元数据、多输出等）。
    """
    image: np.ndarray | None = None                    # 单张图像数据
    images: list[np.ndarray] = field(default_factory=list)  # 多张图像列表
    numeric_value: float = 0.0                         # 数值数据
    text_value: str = ""                               # 文本数据
    metadata: dict[str, Any] = field(default_factory=dict)  # 元数据字典
    result_objects: list[Any] = field(default_factory=list)  # 结果对象列表

    @property
    def has_image(self) -> bool:
        """是否包含图像数据"""
        return self.image is not None

    @property
    def image_shape(self) -> tuple | None:
        """获取图像的形状（H, W, C），若无图像则返回None"""
        if self.image is not None:
            return self.image.shape
        return None


@dataclass
class VisionResultImage:
    """
    表示来自视觉节点的带名称的结果图像。
    """
    name: str                                        # 图像名称
    image: np.ndarray | None = None                  # 图像数据

    def dispose(self):
        """释放图像内存"""
        self.image = None