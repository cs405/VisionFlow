"""SIFT 特征匹配"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import OpenCVTemplateMatchingNodeBase, MatcherType

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class SiftFeatureMatchingNode(OpenCVTemplateMatchingNodeBase):
    """SIFT 特征匹配"""

    matcher_type = Property("bf", name="匹配器类型", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=["bf", "flann"])
    norm_type = Property("L2", name="范数类型", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=["L2", "L1", "HAMMING"])
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
        mat = self.get_input_mat(from_node.mat if from_node else None)
        self.matched = False
        self.match_x = self.match_y = self.match_w = self.match_h = 0
        if mat is None:
            return self.error(None, "无输入图像")
        template = self._require_template(mat)
        if template is None:
            return self.error(mat, "未设置模板图片，输出原图")
        gray1 = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
        gray2 = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if mat.ndim == 3 else mat
        sift = cv2.SIFT_create(nfeatures=self.n_features or None, nOctaveLayers=self.n_octave_layers,
                               contrastThreshold=self.contrast_threshold, edgeThreshold=self.edge_threshold, sigma=self.sigma)
        kp1, des1 = sift.detectAndCompute(gray1, None)
        kp2, des2 = sift.detectAndCompute(gray2, None)
        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            return self.error(mat, "无法提取特征点")
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
            self.matched = False
            self.match_x = self.match_y = self.match_w = self.match_h = 0
        msg = f"SIFT匹配 {len(good)}/{len(kp1)} 个特征点"
        if not match_rect and len(good) >= 4:
            msg += " (面积过滤未通过)"
        if self.matched:
            return self.ok(out, msg)
        else:
            return self.error(out, msg)

    def _match(self, des1, des2) -> list:
        mt = MatcherType(self.matcher_type)
        norm = {"L2": cv2.NORM_L2, "L1": cv2.NORM_L1, "HAMMING": cv2.NORM_HAMMING}.get(self.norm_type, cv2.NORM_L2)
        if mt == MatcherType.BFMATCHER:
            bf = cv2.BFMatcher(norm, crossCheck=self.cross_check)
            if self.cross_check:
                return sorted(bf.match(des1, des2), key=lambda x: x.distance)
            knn = bf.knnMatch(des1, des2, k=2)
            return [m for m, n in knn if m.distance < 0.75 * n.distance]
        else:
            flann = cv2.FlannBasedMatcher(dict(algorithm=0, trees=5), dict(checks=50))
            knn = flann.knnMatch(des1, des2, k=2)
            return [m for m, n in knn if m.distance < 0.75 * n.distance]

    def _get_homography_rect(self, out, template, kp1, kp2, good) -> tuple | None:
        if len(good) < 4:
            return None
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is None:
            return None
        h, w = template.shape[:2]
        corners = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)
        transformed = cv2.perspectiveTransform(corners, H)
        x, y, rw, rh = cv2.boundingRect(np.int32(transformed))
        if self.min_area <= rw * rh <= self.max_area:
            cv2.rectangle(out, (x, y), (x + rw, y + rh), (0, 255, 0), 2)
            return (x, y, rw, rh)
        return None


SiftBase64FeatureMatchingNode = SiftFeatureMatchingNode
