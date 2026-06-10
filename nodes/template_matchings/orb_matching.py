"""ORB 特征匹配节点 — 对应 WPF BestMatchBase64TemplateMatchingNodeData。

使用 ORB 检测 + BFMatcher + RANSAC Homography 进行图像匹配。
与 WPF 实现一致：检测特征点 → 暴力匹配 → Homography 变换 → 绘制多边形。
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


class OrbFeatureMatchingNode(OpenCVTemplateMatchingNodeBase):
    """ORB 特征匹配 + Homography — 对应 WPF BestMatchBase64TemplateMatchingNodeData。

    使用 ORB 检测特征点，BFMatcher 暴力匹配，取最近的 N 个匹配点，
    通过 RANSAC 计算 Homography 单应矩阵，绘制匹配多边形。
    """

    # ── ORB 参数 ──
    n_features = Property(1000, name="特征点数量", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="ORB 检测的最大特征点数量",
                          min_val=100, max_val=10000, step=100)
    good_match_count = Property(10, name="最优匹配数", group=PropertyGroupNames.RUN_PARAMETERS,
                                description="取距离最小的前 N 个匹配用于 Homography",
                                min_val=4, max_val=100)
    ransac_threshold = Property(5.0, name="RANSAC阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                                description="RANSAC 重投影误差阈值（像素）",
                                min_val=1.0, max_val=20.0, step=0.5)
    draw_matches = Property(True, name="绘制匹配线", group=PropertyGroupNames.DISPLAY_PARAMETERS)

    # ── 结果参数 ──
    match_count = Property(0, name="总匹配数", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ORB特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        template = self._require_template(mat)
        if template is None:
            return self.error(mat, "未设置模板图片")

        # ORB 检测
        orb = cv2.ORB_create(nfeatures=self.n_features)
        kp1, des1 = orb.detectAndCompute(template, None)
        kp2, des2 = orb.detectAndCompute(mat, None)

        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            return self.ok(mat, "无法提取特征点")

        # BFMatcher 暴力匹配
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        good = sorted(matches, key=lambda x: x.distance)[:self.good_match_count]

        if len(good) < 4:
            return self.ok(mat, f"匹配点不足 ({len(good)} < 4)，无法计算 Homography")

        # Homography
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,
                                               self.ransac_threshold)

        h, w = template.shape[:2]
        corners = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)

        out = mat.copy()
        if homography is not None:
            transformed = cv2.perspectiveTransform(corners, homography)
            cv2.polylines(out, [np.int32(transformed)], True, (0, 255, 0), 2)

        if self.draw_matches:
            out = cv2.drawMatches(template, kp1, out, kp2, good, None,
                                  flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

        self.match_count = len(matches)
        self.matching_count_result = len(good)
        inliers = int(np.sum(mask)) if mask is not None else 0
        self.confidence = inliers / max(len(good), 1) if good else 0.0

        return self.ok(out, f"ORB 匹配: {len(good)}/{len(matches)} 特征点 (内点: {inliers})")
