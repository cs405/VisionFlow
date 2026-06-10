"""MSER 特征检测 — 对应 WPF MserFeatureDetector : FeatureOpenCVNodeDataBase"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.features.feature_base import FeatureBase


class MserFeatureDetector(FeatureBase):
    delta = Property(5, name="灰度增量", group=PropertyGroupNames.RUN_PARAMETERS)
    min_area = Property(60, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_area = Property(14400, name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_variation = Property(0.25, name="最大变化率", group=PropertyGroupNames.RUN_PARAMETERS, step=0.01, decimals=2)
    min_diversity = Property(0.2, name="最小多样性", group=PropertyGroupNames.RUN_PARAMETERS, step=0.01, decimals=2)
    max_evolution = Property(200, name="最大演化步数", group=PropertyGroupNames.RUN_PARAMETERS)
    area_threshold = Property(1.01, name="面积阈值", group=PropertyGroupNames.RUN_PARAMETERS, step=0.01, decimals=2)
    min_margin = Property(0.003, name="最小边距", group=PropertyGroupNames.RUN_PARAMETERS, step=0.001, decimals=3)
    edge_blur_size = Property(5, name="边缘模糊大小", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "MSER"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat, gray = self._get_gray(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        # 大图缩放到 480 宽加速 MSER
        h, w = gray.shape[:2]
        scale = 1.0
        if max(w, h) > 480:
            scale = 480.0 / max(w, h)
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
        mser = cv2.MSER_create()
        mser.setDelta(self.delta)
        mser.setMinArea(self.min_area)
        mser.setMaxArea(self.max_area)
        mser.setMaxVariation(self.max_variation)
        mser.setMinDiversity(self.min_diversity)
        mser.setMaxEvolution(self.max_evolution)
        mser.setAreaThreshold(self.area_threshold)
        mser.setMinMargin(self.min_margin)
        mser.setEdgeBlurSize(self.edge_blur_size)
        contours, _ = mser.detectRegions(gray)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        # 用多边形绘制代替逐点画圈（WPF 画圈但 C# 比 Python 快得多）
        if scale != 1.0:
            contours = [(pts / scale).astype(np.int32) for pts in contours]
        for pts in contours:
            cv2.polylines(out, [pts.reshape(-1, 1, 2)], True,
                         (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255)), 1)
        self.feature_count = len(contours)
        return self.ok(out, f"{self.feature_count} 个MSER区域")
