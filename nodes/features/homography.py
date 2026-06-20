"""Homography 单应性变换"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class HomographyTransform(OpenCVNodeDataBase):
    """单应性变换 — 通过 SIFT 特征匹配计算透视变换矩阵，将输入图像对齐到参考图像。

    源节点（数据源）提供参考图，上游节点提供待变换图。
    """

    __group__ = "特征提取模块"

    ratio_threshold = Property(0.75, name="Lowe比值阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                               min_val=0.5, max_val=0.95, step=0.05, decimals=2,
                               description="最近邻/次近邻距离比上限，越小匹配越严格")
    ransac_threshold = Property(5.0, name="RANSAC阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                                min_val=1.0, max_val=20.0, step=0.5,
                                description="RANSAC 重投影误差阈值(像素)")
    n_features = Property(0, name="特征点数量", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="SIFT 最大特征点数，0=不限制")
    match_count = Property(0, name="匹配点数", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "单应性变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        if src is None or src.mat is None:
            return self.ok(mat, "无参考图像，输出原图")

        ref = src.mat
        gray1 = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY) if len(ref.shape) == 3 else ref
        gray2 = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat

        sift = cv2.SIFT_create(nfeatures=self.n_features or None)
        kp1, des1 = sift.detectAndCompute(gray1, None)
        kp2, des2 = sift.detectAndCompute(gray2, None)
        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            return self.ok(mat, "特征点不足，输出原图")

        bf = cv2.BFMatcher()
        matches = bf.knnMatch(des1, des2, k=2)
        good = [m for m, n in matches if m.distance < self.ratio_threshold * n.distance]
        self.match_count = len(good)

        if len(good) >= 4:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, self.ransac_threshold)
            h, w = ref.shape[:2]
            result = cv2.warpPerspective(mat, H, (w, h))
            return self.ok(result, f"单应性变换: {len(good)} 匹配点")
        return self.ok(mat, f"匹配点不足 ({len(good)} < 4)，输出原图")
