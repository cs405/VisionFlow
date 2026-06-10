"""对象识别模块 — 共享接口与枚举 """

from enum import Enum


class IDetectorGroupableNode:
    """标记接口：实现此接口的节点自动归入 '对象识别模块' 分组。"""
    pass


class DrawContourType(Enum):
    """轮廓绘制类型"""
    CONTOURS = "contours"
    BOUNDING_RECT = "bounding_rect"
    MIN_AREA_RECT = "min_area_rect"
    CONVEX_HULL = "convex_hull"
    APPROX_POLY = "approx_poly"


class BlobType(Enum):
    """Blob 预设形状类型"""
    CIRCLE = "circle"
    OVAL = "oval"
    NONE = "none"
