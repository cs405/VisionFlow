"""
数据包定义 - 节点间传递的数据结构
支持图像、数值、ROI、列表等多种类型
"""

from typing import Any, Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum
import numpy as np


class DataType(Enum):
    """数据类型枚举"""
    IMAGE = "image"  # numpy.ndarray (BGR格式)
    GRAY_IMAGE = "gray"  # 灰度图
    NUMBER = "number"  # int/float
    STRING = "string"  # str
    BOOL = "bool"  # bool
    POINT = "point"  # (x, y)
    RECT = "rect"  # (x, y, w, h)
    ROI_LIST = "roi_list"  # List[Dict]
    ANY = "any"  # 任意类型


@dataclass
class DataPacket:
    """数据包"""
    type: DataType
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """验证数据类型是否正确"""
        if self.type == DataType.IMAGE:
            return isinstance(self.value, np.ndarray)
        elif self.type == DataType.NUMBER:
            return isinstance(self.value, (int, float))
        elif self.type == DataType.STRING:
            return isinstance(self.value, str)
        elif self.type == DataType.BOOL:
            return isinstance(self.value, bool)
        elif self.type == DataType.POINT:
            return len(self.value) == 2 and all(isinstance(v, (int, float)) for v in self.value)
        elif self.type == DataType.RECT:
            return len(self.value) == 4 and all(isinstance(v, (int, float)) for v in self.value)
        return True

    def to_dict(self) -> Dict:
        """转换为字典"""
        value = self.value
        if isinstance(value, np.ndarray):
            return {
                "type": self.type.value,
                "value": None,  # numpy数组无法直接JSON序列化
                "shape": value.shape,
                "dtype": str(value.dtype),
                "metadata": self.metadata
            }
        return {
            "type": self.type.value,
            "value": value,
            "metadata": self.metadata
        }