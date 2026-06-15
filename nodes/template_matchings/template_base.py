"""模板匹配模块基类层

提供:
  - ITemplateMatchingGroupableNode 标记接口 (分组发现)
  - MatcherType 枚举 (BFMatcher / FlannBasedMatcher)
  - OpenCVTemplateMatchingNodeBase (Base64MatchingNodeData + OpenCVNodeDataBase 合并基类)
"""

from __future__ import annotations

import base64
from enum import Enum
from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import (
    Base64MatchingNodeData, OpenCVNodeDataBase, Property, PropertyGroupNames,
)
from core.data_packet import FlowableResult

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# ITemplateMatchingGroupableNode — 分组发现接口
# =============================================================================

class ITemplateMatchingGroupableNode:
    """标记接口：实现此接口的节点自动归入 '模板匹配模块' 分组。

    """
    pass


# =============================================================================
# MatcherType — 匹配器类型
# =============================================================================

class MatcherType(Enum):
    """特征匹配器类型"""
    BFMATCHER = "bf"
    FLANN_BASED = "flann"


# =============================================================================
# OpenCVTemplateMatchingNodeBase — 合并基类
# =============================================================================

class OpenCVTemplateMatchingNodeBase(Base64MatchingNodeData, OpenCVNodeDataBase,
                                      ITemplateMatchingGroupableNode):
    """模板匹配节点 OpenCV 合并基类。

    将 Base64MatchingNodeData + OpenCVNodeDataBase 的双继承合并为单一入口，
    提供公共的 _update_result_image_source 和 is_valid。
    同时实现 ITemplateMatchingGroupableNode 标记接口。
    """

    __group__ = "模板匹配模块"

    # 模板图片 — 触发属性面板的 crop editor
    template_image = Property("", name="模板图片", group=PropertyGroupNames.RUN_PARAMETERS,
                              editor="crop", description="从上游图像中裁剪模板区域用于匹配",
                              order=1000)

    def __init__(self):
        Base64MatchingNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def is_valid(self, mat: np.ndarray) -> bool:
        return mat is not None and mat.size > 0

    # ── 模板图像获取辅助 ──

    def _require_template(self, mat: np.ndarray) -> np.ndarray | None:
        """获取模板图像，如果未设置则返回 None。

        调用方应检查返回值，为 None 时返回 self.ok(mat, "未设置模板图片，输出原图")。
        始终使用 mat（输入图像）作为结果的值，保证画面流畅。
        """
        template = self.get_template_image()
        if template is None:
            return None
        return template


# ── 经典匹配结果绘制辅助 ────────────────────────────────────────────

def draw_matches(out: np.ndarray, tpl: np.ndarray, results: list[dict],
                 color=(0, 0, 255), max_draw=30):
    """在输出图像上绘制旋转矩形匹配结果。

    参数：
        out: 输出图像（原地修改）。
        tpl: 模板图像（用于获取宽高）。
        results: 匹配结果列表，每项含 x, y, angle, score。
        color: 绘制颜色。
        max_draw: 最多绘制数量。
    """
    h, w = tpl.shape[:2]
    for r in results[:max_draw]:
        cx, cy, angle = r['x'], r['y'], r.get('angle', 0)
        rad = np.radians(angle)
        cos_a, sin_a = np.cos(rad), np.sin(rad)
        corners = np.array([
            [-w / 2, -h / 2], [w / 2, -h / 2],
            [w / 2, h / 2], [-w / 2, h / 2]
        ])
        rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
        pts = (corners @ rot.T + [cx, cy]).astype(np.int32)
        cv2.polylines(out, [pts], True, color, 2)
        score = r.get('score', 0)
        cv2.putText(out, f'{score:.2f}', (int(cx) - 20, int(cy) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)


# ── 图像格式归一化辅助 ────────────────────────────────────────────

def prepare_gray_image(img: np.ndarray) -> np.ndarray:
    """将任意格式的输入图像归一化为 uint8 灰度连续数组，供 DLL 安全使用。

    处理逻辑：
      - float32/float64 → 先缩放到 0-255 再转 uint8
      - 4 通道 (RGBA/BGRA) → 先取前 3 通道 BGR 再转灰度
      - 3 通道 (BGR/RGB) → 转灰度
      - 2 通道 → 取第一通道
      - uint8 灰度 → 直接使用
    始终返回 C-contiguous uint8 (H, W) 数组。
    """
    # 确保是 numpy 数组
    img = np.asarray(img)

    # 处理浮点类型：假设值域 0.0-1.0 或 0.0-255.0
    if img.dtype in (np.float32, np.float64, np.float16):
        if img.max() <= 1.0:
            img = (img * 255).astype(np.uint8)
        else:
            img = np.clip(img, 0, 255).astype(np.uint8)

    # 确保 uint8
    if img.dtype != np.uint8:
        img = img.astype(np.uint8)

    # 处理通道数
    if img.ndim == 2:
        gray = img
    elif img.ndim == 3:
        ch = img.shape[2]
        if ch == 4:
            gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
        elif ch == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        elif ch == 2:
            gray = img[:, :, 0]
        else:
            gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        raise ValueError(f"不支持的图像维度: {img.ndim}")

    return np.ascontiguousarray(gray, dtype=np.uint8)
