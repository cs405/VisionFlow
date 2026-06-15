"""形状上下文匹配 — 边缘点采样 + 对数极坐标直方图 + 最近邻匹配 + RANSAC。"""

from __future__ import annotations

import cv2

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import (OpenCVTemplateMatchingNodeBase,
                                                      draw_matches, prepare_gray_image)


class ShapeContextMatchingNode(OpenCVTemplateMatchingNodeBase):
    """形状上下文匹配 — 对数极坐标直方图描述子 + RANSAC 鲁棒匹配。"""

    sample_step = Property(5, name="采样间隔", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=1, max_val=30)
    n_radial = Property(4, name="径向bin数", group=PropertyGroupNames.RUN_PARAMETERS,
                        min_val=1, max_val=10)
    n_angular = Property(8, name="角度bin数", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=1, max_val=16)
    min_score = Property(0.4, name="最低分数", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=0.0, max_val=1.0, step=0.05, decimals=2)
    max_targets = Property(10, name="最大目标数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=1, max_val=100)
    max_results = Property(200, name="最大结果数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=1, max_val=1000)

    def __init__(self):
        super().__init__()
        self.name = "形状上下文匹配"

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
            from nodes.dll.vision_dll import shape_context
            results, ms = shape_context(
                img_gray, tpl_gray,
                sample_step=int(self.sample_step),
                n_radial=int(self.n_radial),
                n_angular=int(self.n_angular),
                min_score=float(self.min_score),
                max_targets=int(self.max_targets),
                max_results=int(self.max_results),
            )
        except Exception as e:
            return self.error(mat, f"形状上下文匹配异常: {e}")

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
            return self.ok(out, f"形状上下文匹配 {len(results)} 处 ({ms:.0f}ms)")
        return self.error(mat, f"形状上下文匹配: 未匹配到目标 ({ms:.0f}ms)")
