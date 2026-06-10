"""HSV 色相 Blob 匹配节点 — 对应 WPF HSVInRangeRenderBlobMatchingNodeData : RenderBlobs。

取色方式与 nodes/takeoffs/HSVInRange 一致：
  吸管取色 → BGR→HSV 转换 → 容差范围计算 HSV 上下限 → inRange 过滤。
在此基础上增加轮廓检测与绘制（Blob 分析）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import ITemplateMatchingGroupableNode

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class HSVBlobMatchingNode(OpenCVNodeDataBase, ITemplateMatchingGroupableNode):
    """HSV 色相 Blob 匹配 — 对应 WPF HSVInRangeRenderBlobMatchingNodeData。

    取色机制与 takeoffs/HSVInRange 相同：
      - pick_color: 吸管取色（hex 色值）
      - h_range / s_range / v_range: 以取色点为中心的容差
      - 自动计算 HSV 上下限 → inRange → 轮廓检测 → 绘制
    """

    __group__ = "模板匹配模块"

    # ── 取色与容差 (与 takeoffs/HSVInRange 一致) ──
    pick_color = Property("#008000", name="取色", group=PropertyGroupNames.RUN_PARAMETERS,
                          editor="color", description="吸管取色，确定目标颜色的HSV中心值")
    h_range = Property(35, name="色相范围(H)", group=PropertyGroupNames.RUN_PARAMETERS,
                       min_val=0, max_val=85,
                       description="以取色点为中心的色相容差")
    s_range = Property(30, name="饱和度范围(S)", group=PropertyGroupNames.RUN_PARAMETERS,
                       min_val=0, max_val=255,
                       description="以取色点为中心的饱和度容差")
    v_range = Property(30, name="明度范围(V)", group=PropertyGroupNames.RUN_PARAMETERS,
                       min_val=0, max_val=255,
                       description="以取色点为中心的明度容差")

    # ── 结果参数 ──
    blob_count = Property(0, name="Blob数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "HSV色相匹配"

    # ── 取色 → HSV 范围 (与 takeoffs/HSVInRange 完全一致) ──

    def _hex_to_bgr_pixel(self) -> np.ndarray:
        """Hex 取色 → BGR 像素数组 (用于 cv2.cvtColor)。"""
        hex_color = (self.pick_color or "#008000").lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return np.array([[[b, g, r]]], dtype=np.uint8)

    def _get_hsv_range(self) -> tuple[np.ndarray, np.ndarray]:
        """根据取色和容差计算 HSV 上下限。

        1. 取色 BGR → OpenCV HSV
        2. OpenCV 尺度 (0-179, 0-255, 0-255) → WPF 尺度 (0-360, 0-100, 0-100)
        3. Lower = 中心 - 全容差, Upper = 中心 + 半容差
        4. 转回 OpenCV 尺度
        """
        bgr = self._hex_to_bgr_pixel()
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0]
        h, s, v = int(hsv[0]), int(hsv[1]), int(hsv[2])

        # OpenCV → WPF 尺度
        h_wpf = h * 2              # [0,179] → [0,360]
        s_wpf = s / 2.55           # [0,255] → [0,100]
        v_wpf = v / 2.55

        hr, sr, vr = self.h_range, self.s_range, self.v_range

        # Lower: 全容差
        l_h_min = max(0, h_wpf - hr)
        l_s_min = max(0, s_wpf - sr)
        l_v_min = max(0, v_wpf - vr)

        # Upper: 半容差
        u_h_max = min(360, h_wpf + hr / 2)
        u_s_max = min(100, s_wpf + sr / 2)
        u_v_max = min(100, v_wpf + vr / 2)

        lower = np.array([l_h_min / 2, l_s_min * 2.55, l_v_min * 2.55], dtype=np.uint8)
        upper = np.array([u_h_max / 2, u_s_max * 2.55, u_v_max * 2.55], dtype=np.uint8)
        return lower, upper

    # ── 核心处理 ──

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        # 保存图像副本供取色器的吸管工具采样
        self._picker_mat = mat.copy()

        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        lower, upper = self._get_hsv_range()
        mask = cv2.inRange(hsv, lower, upper)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = mat.copy()
        cv2.drawContours(out, contours, -1, (0, 255, 0), 2)

        self.blob_count = len(contours)
        return self.ok(out, f"发现 {len(contours)} 个Blob")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def is_valid(self, mat: np.ndarray) -> bool:
        return mat is not None and mat.size > 0


# 向后兼容别名
HSVInRangeRenderBlobMatchingNode = HSVBlobMatchingNode
