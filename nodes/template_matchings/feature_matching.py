"""SIFT / SURF 特征匹配节点 — 对应 WPF SiftBase64FeatureMatchingNodeData / SurfBase64FeatureMatchingNodeData。

独立实现，不再相互继承。每个节点包含 WPF 对应参数的完整集合。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import (
    OpenCVTemplateMatchingNodeBase, MatcherType,
)

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# SiftFeatureMatchingNode — SIFT 特征匹配 (对应 WPF SiftBase64FeatureMatchingNodeData)
# =============================================================================

class SiftFeatureMatchingNode(OpenCVTemplateMatchingNodeBase):
    """SIFT 特征匹配 — 对应 WPF SiftBase64FeatureMatchingNodeData。

    使用尺度不变特征变换 (SIFT) 进行图像特征匹配。
    """

    # ── 匹配器参数 ──
    matcher_type = Property("bf", name="匹配器类型", group=PropertyGroupNames.RUN_PARAMETERS,
                            editor="choices", choices=["bf", "flann"])
    norm_type = Property("L2", name="范数类型", group=PropertyGroupNames.RUN_PARAMETERS,
                         editor="choices", choices=["L2", "L1", "HAMMING"])
    cross_check = Property(False, name="交叉检查", group=PropertyGroupNames.RUN_PARAMETERS)

    # ── SIFT 参数 (对应 WPF SIFT 属性) ──
    n_features = Property(0, name="特征点数量", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="0 = 不限制")
    n_octave_layers = Property(3, name="组内层数", group=PropertyGroupNames.RUN_PARAMETERS)
    contrast_threshold = Property(0.04, name="对比度阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                                  step=0.01, decimals=4)
    edge_threshold = Property(10.0, name="边缘阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma = Property(1.6, name="高斯Sigma", group=PropertyGroupNames.RUN_PARAMETERS,
                     step=0.1, decimals=1)

    # ── 过滤参数 ──
    min_area = Property(100.0, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_area = Property(float(2**31 - 1), name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS)

    # ── 结果参数 ──
    feature_count_result = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                                    readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "SIFT特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        template = self._require_template(mat)
        if template is None:
            return self.error(mat, "未设置模板图片")

        # 转灰度
        gray1 = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
        gray2 = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if mat.ndim == 3 else mat

        # 创建 SIFT
        sift = cv2.SIFT_create(
            nfeatures=self.n_features or None,
            nOctaveLayers=self.n_octave_layers,
            contrastThreshold=self.contrast_threshold,
            edgeThreshold=self.edge_threshold,
            sigma=self.sigma,
        )
        kp1, des1 = sift.detectAndCompute(gray1, None)
        kp2, des2 = sift.detectAndCompute(gray2, None)

        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            return self.ok(mat, "无法提取特征点")

        # 匹配
        matcher_type = MatcherType(self.matcher_type)
        norm_map = {"L2": cv2.NORM_L2, "L1": cv2.NORM_L1, "HAMMING": cv2.NORM_HAMMING}
        norm = norm_map.get(self.norm_type, cv2.NORM_L2)

        if matcher_type == MatcherType.BFMATCHER:
            bf = cv2.BFMatcher(norm, crossCheck=self.cross_check)
            if self.cross_check:
                matches = bf.match(des1, des2)
                good = sorted(matches, key=lambda x: x.distance)
            else:
                knn = bf.knnMatch(des1, des2, k=2)
                good = [m for m, n in knn if m.distance < 0.75 * n.distance]
        else:
            # FLANN
            index_params = dict(algorithm=0, trees=5)
            search_params = dict(checks=50)
            flann = cv2.FlannBasedMatcher(index_params, search_params)
            knn = flann.knnMatch(des1, des2, k=2)
            good = [m for m, n in knn if m.distance < 0.75 * n.distance]

        # 绘制
        out = cv2.drawMatches(gray1, kp1, gray2, kp2, good, None,
                              flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

        self.feature_count_result = len(kp1)
        self.matching_count_result = len(good)
        self.confidence = len(good) / max(len(kp1), 1)
        return self.ok(out, f"SIFT匹配 {len(good)}/{len(kp1)} 个特征点")


# =============================================================================
# SurfFeatureMatchingNode — SURF 特征匹配 (对应 WPF SurfBase64FeatureMatchingNodeData)
# =============================================================================

class SurfFeatureMatchingNode(OpenCVTemplateMatchingNodeBase):
    """SURF 特征匹配 — 对应 WPF SurfBase64FeatureMatchingNodeData。

    使用加速鲁棒特征 (SURF) 进行图像特征匹配。
    如果 OpenCV 没有 SURF (xfeatures2d 不可用)，回退到 SIFT。
    """

    # ── 匹配器参数 ──
    matcher_type = Property("bf", name="匹配器类型", group=PropertyGroupNames.RUN_PARAMETERS,
                            editor="choices", choices=["bf", "flann"])
    norm_type = Property("L2", name="范数类型", group=PropertyGroupNames.RUN_PARAMETERS,
                         editor="choices", choices=["L2", "L1", "HAMMING"])
    cross_check = Property(False, name="交叉检查", group=PropertyGroupNames.RUN_PARAMETERS)

    # ── SURF 参数 (对应 WPF SURF 属性) ──
    hessian_threshold = Property(200.0, name="Hessian阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                                 description="Hessian 行列式阈值，越大特征点越少但越稳定")
    n_octaves = Property(4, name="组数", group=PropertyGroupNames.RUN_PARAMETERS)
    n_octave_layers = Property(2, name="组内层数", group=PropertyGroupNames.RUN_PARAMETERS)
    extended = Property(False, name="扩展描述符", group=PropertyGroupNames.RUN_PARAMETERS,
                        description="True=128维, False=64维")
    upright = Property(True, name="忽略方向", group=PropertyGroupNames.RUN_PARAMETERS,
                       description="True=不计算方向 (U-SURF)")

    def __init__(self):
        super().__init__()
        self.name = "SURF特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        template = self._require_template(mat)
        if template is None:
            return self.error(mat, "未设置模板图片")

        gray1 = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
        gray2 = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if mat.ndim == 3 else mat

        # 尝试创建 SURF，不可用时回退到 SIFT
        try:
            surf = cv2.xfeatures2d.SURF_create(
                hessianThreshold=self.hessian_threshold,
                nOctaves=self.n_octaves,
                nOctaveLayers=self.n_octave_layers,
                extended=self.extended,
                upright=self.upright,
            )
            kp1, des1 = surf.detectAndCompute(gray1, None)
            kp2, des2 = surf.detectAndCompute(gray2, None)
        except AttributeError:
            # SURF 不可用，回退到 SIFT
            sift = cv2.SIFT_create()
            kp1, des1 = sift.detectAndCompute(gray1, None)
            kp2, des2 = sift.detectAndCompute(gray2, None)

        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            return self.ok(mat, "无法提取特征点")

        # 匹配
        matcher_type = MatcherType(self.matcher_type)
        norm_map = {"L2": cv2.NORM_L2, "L1": cv2.NORM_L1, "HAMMING": cv2.NORM_HAMMING}
        norm = norm_map.get(self.norm_type, cv2.NORM_L2)

        if matcher_type == MatcherType.BFMATCHER:
            bf = cv2.BFMatcher(norm, crossCheck=self.cross_check)
            if self.cross_check:
                matches = bf.match(des1, des2)
                good = sorted(matches, key=lambda x: x.distance)
            else:
                knn = bf.knnMatch(des1, des2, k=2)
                good = [m for m, n in knn if m.distance < 0.75 * n.distance]
        else:
            index_params = dict(algorithm=0, trees=5)
            search_params = dict(checks=50)
            flann = cv2.FlannBasedMatcher(index_params, search_params)
            knn = flann.knnMatch(des1, des2, k=2)
            good = [m for m, n in knn if m.distance < 0.75 * n.distance]

        out = cv2.drawMatches(gray1, kp1, gray2, kp2, good, None,
                              flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

        self.matching_count_result = len(good)
        self.confidence = len(good) / max(len(kp1), 1)
        return self.ok(out, f"SURF匹配 {len(good)}/{len(kp1)} 个特征点")


# 向后兼容别名
SiftBase64FeatureMatchingNode = SiftFeatureMatchingNode
SurfBase64FeatureMatchingNode = SurfFeatureMatchingNode
