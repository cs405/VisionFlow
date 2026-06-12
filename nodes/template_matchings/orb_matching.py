"""ORB 特征匹配节点
使用 ORB 检测 + BFMatcher + RANSAC Homography 进行图像匹配。
检测特征点 → 暴力匹配 → Homography 变换 → 绘制多边形。
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
    """ORB 特征匹配 + Homography

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
    min_area = Property(100.0, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_area = Property(float(2**31 - 1), name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS)
    # ── 结果参数 ──
    match_count = Property(0, name="总匹配数", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ORB特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        self.matched = False
        self.match_x = self.match_y = self.match_w = self.match_h = 0
        if mat is None:
            return self.error(None, "无输入图像")

        template = self._require_template(mat)
        if template is None:
            return self.error(mat, "未设置模板图片，输出原图")

        # ORB 检测
        orb = cv2.ORB_create(nfeatures=self.n_features)
        kp1, des1 = orb.detectAndCompute(template, None)
        kp2, des2 = orb.detectAndCompute(mat, None)

        if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
            return self.error(mat, "无法提取特征点")

        # BFMatcher 暴力匹配
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        good = sorted(matches, key=lambda x: x.distance)[:self.good_match_count]

        if len(good) < 4:
            return self.error(mat, f"匹配点不足 ({len(good)} < 4)，无法计算 Homography")

        # Homography
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,
                                               self.ransac_threshold)

        out = mat.copy()
        matched = False
        match_x = match_y = match_w = match_h = 0
        if homography is not None:
            h, w = template.shape[:2]
            corners = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)
            transformed = cv2.perspectiveTransform(corners, homography)
            pts = np.int32(transformed)
            match_x, match_y, match_w, match_h = cv2.boundingRect(pts)
            area = match_w * match_h
            if self.min_area <= area <= self.max_area:
                cv2.rectangle(out, (match_x, match_y), (match_x + match_w, match_y + match_h), (0, 255, 0), 2)
                matched = True

        self.matched = matched
        self.match_x, self.match_y, self.match_w, self.match_h = match_x, match_y, match_w, match_h
        self.match_count = len(matches)
        self.matching_count_result = len(good)
        inliers = int(np.sum(mask)) if mask is not None else 0
        self.confidence = inliers / max(len(good), 1) if good else 0.0
        msg = f"ORB 匹配: {len(good)}/{len(matches)} 特征点 (内点: {inliers})"
        if not matched and len(good) >= 4:
            msg += " (面积过滤未通过)"
        if self.matched:
            return self.ok(out, msg)
        else:
            return self.error(out, msg)
