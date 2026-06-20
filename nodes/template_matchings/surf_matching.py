"""SURF 特征匹配 """

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import OpenCVTemplateMatchingNodeBase, MatcherType, NormType

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class SurfFeatureMatchingNode(OpenCVTemplateMatchingNodeBase):
    """SURF 特征匹配"""

    matcher_type = Property("bf", name="匹配器类型", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=[e.value for e in MatcherType])
    norm_type = Property("L2", name="范数类型", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=[e.value for e in NormType])
    cross_check = Property(False, name="交叉检查", group=PropertyGroupNames.RUN_PARAMETERS)
    min_area = Property(100.0, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_area = Property(float(2**31 - 1), name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS)
    hessian_threshold = Property(200.0, name="Hessian阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    n_octaves = Property(4, name="组数", group=PropertyGroupNames.RUN_PARAMETERS)
    n_octave_layers = Property(2, name="组内层数", group=PropertyGroupNames.RUN_PARAMETERS)
    extended = Property(False, name="扩展描述符", group=PropertyGroupNames.RUN_PARAMETERS)
    upright = Property(True, name="忽略方向", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "SURF特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        self.matched = False
        self.match_x = self.match_y = self.match_w = self.match_h = 0
        if mat is None:
            return self.error(None, "无输入图像")
        template = self._require_template(mat)
        if template is None:
            return self.error(None, "未设置模板图片，输出原图")
        gray1 = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
        gray2 = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if mat.ndim == 3 else mat
        try:
            surf = cv2.xfeatures2d.SURF_create(hessianThreshold=self.hessian_threshold,
                nOctaves=self.n_octaves, nOctaveLayers=self.n_octave_layers,
                extended=self.extended, upright=self.upright)
            kp1, des1 = surf.detectAndCompute(gray1, None)
            kp2, des2 = surf.detectAndCompute(gray2, None)
        except AttributeError:
            sift = cv2.SIFT_create()
            kp1, des1 = sift.detectAndCompute(gray1, None)
            kp2, des2 = sift.detectAndCompute(gray2, None)
        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            return self.error(None, "无法提取特征点")
        good = self._match(des1, des2)
        out = mat.copy()
        match_rect = self._get_homography_rect(out, template, kp1, kp2, good)
        self.matching_count_result = len(good)
        self.confidence = len(good) / max(len(kp1), 1)
        if match_rect is not None:
            self.matched = True
            self.match_x, self.match_y, self.match_w, self.match_h = match_rect
        else:
            self.matched = False
            self.match_x = self.match_y = self.match_w = self.match_h = 0
        msg = f"SURF匹配 {len(good)}/{len(kp1)} 个特征点"
        if not match_rect and len(good) >= 4:
            msg += " (面积过滤未通过)"
        if self.matched:
            return self.ok(out, msg)
        else:
            return self.error(None, msg)


SurfBase64FeatureMatchingNode = SurfFeatureMatchingNode
