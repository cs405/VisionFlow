"""SIFT 特征匹配"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import OpenCVTemplateMatchingNodeBase, MatcherType, NormType

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class SiftFeatureMatchingNode(OpenCVTemplateMatchingNodeBase):
    """SIFT 特征匹配"""

    matcher_type = Property("bf", name="匹配器类型", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=[e.value for e in MatcherType])
    norm_type = Property("L2", name="范数类型", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=[e.value for e in NormType])
    cross_check = Property(False, name="交叉检查", group=PropertyGroupNames.RUN_PARAMETERS)
    n_features = Property(0, name="特征点数量", group=PropertyGroupNames.RUN_PARAMETERS, description="0 = 不限制")
    n_octave_layers = Property(3, name="组内层数", group=PropertyGroupNames.RUN_PARAMETERS)
    contrast_threshold = Property(0.04, name="对比度阈值", group=PropertyGroupNames.RUN_PARAMETERS, step=0.01, decimals=4)
    edge_threshold = Property(10.0, name="边缘阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma = Property(1.6, name="高斯Sigma", group=PropertyGroupNames.RUN_PARAMETERS, step=0.1, decimals=1)
    min_area = Property(100.0, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_area = Property(float(2**31 - 1), name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS)
    feature_count_result = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "SIFT特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        self._reset_match_state()
        if mat is None:
            return self.error(None, "无输入图像")
        template = self._require_template(mat)
        if template is None:
            return self.error(None, "未设置模板图片，输出原图")
        gray1 = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
        gray2 = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if mat.ndim == 3 else mat
        sift = cv2.SIFT_create(nfeatures=self.n_features or None, nOctaveLayers=self.n_octave_layers,
                               contrastThreshold=self.contrast_threshold, edgeThreshold=self.edge_threshold, sigma=self.sigma)
        kp1, des1 = sift.detectAndCompute(gray1, None)
        kp2, des2 = sift.detectAndCompute(gray2, None)
        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            return self.error(None, "无法提取特征点")
        good = self._match(des1, des2)
        out = mat.copy()
        match_rect = self._get_homography_rect(out, template, kp1, kp2, good)
        self.feature_count_result = len(kp1)
        self.matching_count_result = len(good)
        self.confidence = len(good) / max(len(kp1), 1)
        if match_rect is not None:
            self.matched = True
            self.match_x, self.match_y, self.match_w, self.match_h = match_rect
        else:
            self._reset_match_state()
        msg = f"SIFT匹配 {len(good)}/{len(kp1)} 个特征点"
        if not match_rect and len(good) >= 4:
            msg += " (面积过滤未通过)"
        if self.matched:
            return self.ok(out, msg)
        else:
            return self.error(None, msg)


SiftBase64FeatureMatchingNode = SiftFeatureMatchingNode
