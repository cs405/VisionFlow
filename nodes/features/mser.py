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
        mser = cv2.MSER_create(_delta=self.delta, _min_area=self.min_area, _max_area=self.max_area,
                                _max_variation=self.max_variation, _min_diversity=self.min_diversity,
                                _max_evolution=self.max_evolution, _area_threshold=self.area_threshold,
                                _min_margin=self.min_margin, _edge_blur_size=self.edge_blur_size)
        contours, _ = mser.detectRegions(gray)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        for pts in contours:
            color = (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255))
            for pt in pts:
                cv2.circle(out, (int(pt[0][0]), int(pt[0][1])), 1, color, -1)
        self.feature_count = len(contours)
        return self.ok(out, f"{self.feature_count} 个MSER区域")
