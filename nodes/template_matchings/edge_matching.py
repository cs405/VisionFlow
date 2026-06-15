"""边缘梯度匹配 — Canny 提取模板边缘 + Sobel 梯度 + 滑动窗口点积相似度。"""

from __future__ import annotations

import cv2

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import OpenCVTemplateMatchingNodeBase, draw_matches


class EdgeMatchingNode(OpenCVTemplateMatchingNodeBase):
    """边缘梯度匹配 — 支持旋转角度搜索的模板匹配。"""

    tpl_canny_low = Property(50, name="Canny低阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                             min_val=0, max_val=255)
    tpl_canny_high = Property(150, name="Canny高阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                              min_val=0, max_val=255)
    match_threshold = Property(0.5, name="提前终止阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                               min_val=0.1, max_val=0.9, step=0.05, decimals=2)
    min_score = Property(0.2, name="最低分数", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=0.0, max_val=1.0, step=0.05, decimals=2)
    angle_start = Property(-45, name="起始角度", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=-180, max_val=180)
    angle_end = Property(45, name="结束角度", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=-180, max_val=180)
    angle_step = Property(5, name="角度步长", group=PropertyGroupNames.RUN_PARAMETERS,
                          min_val=1, max_val=45)
    max_results = Property(200, name="最大结果数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=1, max_val=1000)

    def __init__(self):
        super().__init__()
        self.name = "边缘匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        self.matched = False
        self.match_x = self.match_y = self.match_w = self.match_h = 0
        if mat is None:
            return self.error(None, "无输入图像")
        template = self._require_template(mat)
        if template is None:
            return self.error(None, "未设置模板图片，输出原图")

        tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
        img_gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if mat.ndim == 3 else mat

        from nodes.dll.vision_dll import edge_match
        results, ms = edge_match(
            img_gray, tpl_gray,
            tpl_canny_low=self.tpl_canny_low,
            tpl_canny_high=self.tpl_canny_high,
            match_threshold=self.match_threshold,
            min_score=self.min_score,
            angle_start=self.angle_start,
            angle_end=self.angle_end,
            angle_step=self.angle_step,
            max_results=self.max_results,
        )

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
            return self.ok(out, f"边缘匹配 {len(results)} 处 ({ms:.0f}ms)")
        return self.error(None, f"边缘匹配: 未匹配到目标 ({ms:.0f}ms)")
