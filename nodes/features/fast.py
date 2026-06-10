"""FAST 特征检测 — 对应 WPF FastFeatureDetector : FeatureOpenCVNodeDataBase"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.features.feature_base import FeatureBase


class FastFeatureDetector(FeatureBase):
    threshold = Property(10, name="响应阈值", group=PropertyGroupNames.RUN_PARAMETERS, min_val=0, max_val=500, description="越小特征点越多")
    nonmax_suppression = Property(True, name="非极大抑制", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "FAST"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat, gray = self._get_gray(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        fast = cv2.FastFeatureDetector_create(threshold=self.threshold, nonmaxSuppression=self.nonmax_suppression)
        kp = fast.detect(gray, None)
        # WPF: 每个关键点画彩色圆点
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        if kp:
            for kpt in kp:
                x, y = int(kpt.pt[0]), int(kpt.pt[1])
                color = (np.random.randint(0, 255), np.random.randint(0, 255), np.random.randint(0, 255))
                cv2.circle(out, (x, y), 3, color, -1)
        self.feature_count = len(kp) if kp else 0
        return self.ok(out, f"{self.feature_count} 个特征点")
