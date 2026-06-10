"""模板匹配节点 — 对应 WPF TemplateBase64MatchingNodeData。

使用 cv2.matchTemplate 进行模板匹配，支持多种匹配方法。
合并了原 BestMatchBase64TemplateMatchingNode（仅多了可配置阈值）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import OpenCVTemplateMatchingNodeBase

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine

# 匹配方法映射 — 对应 WPF TemplateMatchModes 枚举
MATCH_MODES = {
    "SQDIFF": cv2.TM_SQDIFF,
    "SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
    "CCORR": cv2.TM_CCORR,
    "CCORR_NORMED": cv2.TM_CCORR_NORMED,
    "CCoeff": cv2.TM_CCOEFF,
    "CCoeffNormed": cv2.TM_CCOEFF_NORMED,
}


class TemplateMatchingNode(OpenCVTemplateMatchingNodeBase):
    """使用 cv2.matchTemplate 进行模板匹配 — 对应 WPF TemplateBase64MatchingNodeData。

    支持 6 种匹配方法，可配置置信度阈值。
    """

    # ── 运行参数 (对应 WPF TemplateMatchModes) ──
    match_mode = Property("CCoeffNormed", name="匹配方法", group=PropertyGroupNames.RUN_PARAMETERS,
                          editor="choices",
                          choices=list(MATCH_MODES.keys()))
    threshold = Property(0.8, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                         description="匹配置信度 >= 此值才视为匹配成功",
                         min_val=0.0, max_val=1.0, step=0.05, decimals=2)

    def __init__(self):
        super().__init__()
        self.name = "模板匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        template = self._require_template(mat)
        if template is None:
            return self.error(mat, "未设置模板图片")

        method = MATCH_MODES.get(self.match_mode, cv2.TM_CCOEFF_NORMED)
        result = cv2.matchTemplate(mat, template, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= self.threshold:
            h, w = template.shape[:2]
            out = mat.copy()
            cv2.rectangle(out, max_loc, (max_loc[0] + w, max_loc[1] + h),
                         (0, 255, 0), 2)
            self.matching_count_result = 1
            self.confidence = float(max_val)
            return self.ok(out, f"匹配成功 置信度: {max_val:.3f}")

        self.matching_count_result = 0
        self.confidence = 0.0
        return self.ok(mat, f"未匹配 (最高置信度: {max_val:.3f} < {self.threshold})")


# 向后兼容别名
TemplateBase64MatchingNode = TemplateMatchingNode
BestMatchBase64TemplateMatchingNode = TemplateMatchingNode
