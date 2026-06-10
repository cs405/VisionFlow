"""HSV 色相 Blob 匹配节点 — 对应 WPF HSVInRangeRenderBlobMatchingNodeData。

将 BGR 图像转 HSV，通过 H/S/V 范围过滤找到匹配区域，绘制轮廓。
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
    """HSV 色相 Blob 匹配 — 对应 WPF HSVInRangeRenderBlobMatchingNodeData : RenderBlobs。

    通过 HSV 色彩空间的范围过滤找到目标区域，绘制轮廓。
    """

    __group__ = "模板匹配模块"

    # ── H/S/V 范围参数 ──
    h_low = Property(0, name="H色相低", group=PropertyGroupNames.RUN_PARAMETERS,
                     min_val=0, max_val=180)
    h_high = Property(180, name="H色相高", group=PropertyGroupNames.RUN_PARAMETERS,
                      min_val=0, max_val=180)
    s_low = Property(0, name="S饱和度低", group=PropertyGroupNames.RUN_PARAMETERS,
                     min_val=0, max_val=255)
    s_high = Property(255, name="S饱和度高", group=PropertyGroupNames.RUN_PARAMETERS,
                      min_val=0, max_val=255)
    v_low = Property(0, name="V明度低", group=PropertyGroupNames.RUN_PARAMETERS,
                     min_val=0, max_val=255)
    v_high = Property(255, name="V明度高", group=PropertyGroupNames.RUN_PARAMETERS,
                      min_val=0, max_val=255)

    # ── 结果参数 ──
    blob_count = Property(0, name="Blob数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "HSV色相匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        lower = np.array([self.h_low, self.s_low, self.v_low], dtype=np.uint8)
        upper = np.array([self.h_high, self.s_high, self.v_high], dtype=np.uint8)
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
