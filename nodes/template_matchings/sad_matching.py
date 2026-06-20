"""SAD 模板匹配 — 在模板边缘点位置计算绝对像素差的平均值。"""

from __future__ import annotations

import cv2

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import (OpenCVTemplateMatchingNodeBase,
                                                      draw_matches, prepare_gray_image)


class SADMatchingNode(OpenCVTemplateMatchingNodeBase):
    """SAD 模板匹配 — 绝对像素差平均值，越低越好。"""

    tpl_canny_low = Property(50, name="Canny低阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                             min_val=0, max_val=255)
    tpl_canny_high = Property(150, name="Canny高阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                              min_val=0, max_val=255)
    max_dist = Property(0.4, name="最大平均差", group=PropertyGroupNames.RUN_PARAMETERS,
                        min_val=0.05, max_val=1.0, step=0.05, decimals=2)
    max_results = Property(200, name="最大结果数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=1, max_val=1000)

    def __init__(self):
        super().__init__()
        self.name = "SAD匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        self._reset_match_state()
        if mat is None:
            return self.error(None, "无输入图像")
        template = self._require_template(mat)
        if template is None:
            return self.error(None, "未设置模板图片，输出原图")
        try:
            from nodes.dll.vision_dll import sad_match
        except Exception as e:
            return self.error(mat, f"SAD匹配异常: {e}")
        return self._invoke_dll_match(mat, template, sad_match, "max_dist", float(self.max_dist), "SAD")
