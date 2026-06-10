"""BRISK 特征检测 — 对应 WPF BriskFeatureDetector : FeatureOpenCVNodeDataBase"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.features.feature_base import FeatureBase


class BriskFeatureDetector(FeatureBase):
    threshold = Property(50, name="响应阈值", group=PropertyGroupNames.RUN_PARAMETERS, min_val=0, max_val=500, description="越小特征点越多")
    octaves = Property(3, name="组数(Octaves)", group=PropertyGroupNames.RUN_PARAMETERS, min_val=0, max_val=8)
    pattern_scale = Property(1.0, name="采样间距", group=PropertyGroupNames.RUN_PARAMETERS, step=0.1, decimals=1)

    def __init__(self):
        super().__init__()
        self.name = "BRISK"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat, gray = self._get_gray(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        brisk = cv2.BRISK_create(thresh=self.threshold, octaves=self.octaves, patternScale=self.pattern_scale)
        kp = brisk.detect(gray, None)
        # WPF: 每个关键点画圆圈+交叉线
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        if kp:
            for kpt in kp:
                x, y = int(kpt.pt[0]), int(kpt.pt[1])
                r = int(kpt.size / 2)
                color = (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255))
                cv2.circle(out, (x, y), r, color, 1)
                cv2.line(out, (x + r, y + r), (x - r, y - r), color, 1)
                cv2.line(out, (x - r, y + r), (x + r, y - r), color, 1)
        self.feature_count = len(kp) if kp else 0
        return self.ok(out, f"{self.feature_count} 个特征点")
