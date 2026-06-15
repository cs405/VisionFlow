"""NCC 相关系数匹配 — 在模板边缘点位置计算 Pearson 相关系数。"""

from __future__ import annotations

import cv2

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import (OpenCVTemplateMatchingNodeBase,
                                                      draw_matches, prepare_gray_image)


class NCCMatchingNode(OpenCVTemplateMatchingNodeBase):
    """NCC 相关系数匹配 — Pearson 相关系数，范围 -1~1。"""

    tpl_canny_low = Property(50, name="Canny低阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                             min_val=0, max_val=255)
    tpl_canny_high = Property(150, name="Canny高阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                              min_val=0, max_val=255)
    min_score = Property(0.5, name="最低相关系数", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=0.0, max_val=1.0, step=0.05, decimals=2)
    max_results = Property(200, name="最大结果数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=1, max_val=1000)

    def __init__(self):
        super().__init__()
        self.name = "NCC匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        self.matched = False
        self.match_x = self.match_y = self.match_w = self.match_h = 0
        if mat is None:
            return self.error(None, "无输入图像")
        template = self._require_template(mat)
        if template is None:
            return self.error(None, "未设置模板图片，输出原图")

        tpl_gray = prepare_gray_image(template)
        img_gray = prepare_gray_image(mat)

        if tpl_gray.shape[0] > img_gray.shape[0] or tpl_gray.shape[1] > img_gray.shape[1]:
            return self.error(mat, "模板尺寸大于目标图像，无法匹配")

        try:
            from nodes.dll.vision_dll import ncc_match
            results, ms = ncc_match(
                img_gray, tpl_gray,
                tpl_canny_low=float(self.tpl_canny_low),
                tpl_canny_high=float(self.tpl_canny_high),
                min_score=float(self.min_score),
                max_results=int(self.max_results),
            )
        except Exception as e:
            return self.error(mat, f"NCC匹配异常: {e}")

        out = mat.copy()
        draw_matches(out, template, results)

        self.matching_count_result = len(results)
        self.confidence = float(max((r['score'] for r in results), default=0.0))
        self.matched = len(results) > 0
        if self.matched:
            r = max(results, key=lambda x: x['score'])
            h, w = template.shape[:2]
            self.match_x, self.match_y = int(r['x'] - w / 2), int(r['y'] - h / 2)
            self.match_w, self.match_h = w, h
            return self.ok(out, f"NCC匹配 {len(results)} 处 ({ms:.0f}ms)")
        return self.error(mat, f"NCC匹配: 未匹配到目标 ({ms:.0f}ms)")
