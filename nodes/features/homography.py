"""Homography 单应性变换 — 对应 WPF 相关功能"""

import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class HomographyTransform(OpenCVNodeDataBase):
    """使用 SIFT 特征匹配进行单应性变换"""

    __group__ = "特征提取模块"

    match_count = Property(0, name="匹配点数", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "单应性变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        if src is None or src.mat is None:
            return self.ok(mat, "无参考图像")

        ref = src.mat
        gray1 = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY) if len(ref.shape) == 3 else ref
        gray2 = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat

        sift = cv2.SIFT_create()
        kp1, des1 = sift.detectAndCompute(gray1, None)
        kp2, des2 = sift.detectAndCompute(gray2, None)
        if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
            return self.ok(mat, "特征点不足")

        bf = cv2.BFMatcher()
        matches = bf.knnMatch(des1, des2, k=2)
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]
        self.match_count = len(good)

        if len(good) >= 4:
            src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            H, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC)
            h, w = ref.shape[:2]
            result = cv2.warpPerspective(mat, H, (w, h))
            return self.ok(result, f"单应性变换: {len(good)} 匹配点")
        return self.ok(mat, f"不足4个匹配点 ({len(good)})")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
