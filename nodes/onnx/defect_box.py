"""DefectBox 数据结构 + BoxCoordinateMode / BoxGeometryType 枚举 """

from dataclasses import dataclass
from enum import Enum


@dataclass
class DefectBox:
    """单个检测框结果"""
    class_id: int
    box: tuple[float, float, float, float]  # (x, y, w, h)
    score: float


class BoxCoordinateMode(Enum):
    """检测框坐标基准"""
    ABSOLUTE_PIXELS = "absolute"
    NORMALIZED_RATIO = "normalized"


class BoxGeometryType(Enum):
    """检测框几何表示"""
    CENTER_WITH_SIZE = "center_size"
    POINT_WITH_SIZE = "point_size"
    CORNER_POINTS = "corner_points"
    POLAR_WITH_ANGLE = "polar_angle"
