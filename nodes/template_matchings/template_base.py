"""模板匹配模块基类层 — 对应 WPF H.VisionMaster 的 Base64MatchingNodeData + OpenCV 基类。

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

    对应 WPF ITemplateMatchingGroupableNodeData。
    """
    pass


# =============================================================================
# MatcherType — 匹配器类型 (对应 WPF MatcherType 枚举)
# =============================================================================

class MatcherType(Enum):
    """特征匹配器类型 — 对应 WPF MatcherType。"""
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

    对应 WPF:
      - Base64MatchingNodeData<T> (模板存储 + 裁剪 UI + 结果参数)
      - OpenCVBase64MatchingNodeDataBase (Mat 验证 + 图像转换)
    """

    __group__ = "模板匹配模块"

    # 模板图片 — 触发属性面板的 crop editor (对应 WPF CropImagePropertyPresenter)
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
