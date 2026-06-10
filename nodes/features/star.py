"""STAR 特征检测 — 对应 WPF StarFeatureDetector : FeatureOpenCVNodeDataBase"""

import cv2
from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.features.feature_base import FeatureBase


class StarFeatureDetector(FeatureBase):
    max_size = Property(45, name="最大尺寸", group=PropertyGroupNames.RUN_PARAMETERS)
    response_threshold = Property(30, name="响应阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    line_threshold_projected = Property(10, name="投影线阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    line_threshold_binarized = Property(8, name="二值线阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    suppress_nonmax_size = Property(5, name="非极大窗口", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "StarDetector"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat, gray = self._get_gray(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        if hasattr(cv2, 'xfeatures2d'):
            detector = cv2.xfeatures2d.StarDetector_create(
                maxSize=self.max_size, responseThreshold=self.response_threshold,
                lineThresholdProjected=self.line_threshold_projected,
                lineThresholdBinarized=self.line_threshold_binarized,
                suppressNonmaxSize=self.suppress_nonmax_size)
        else:
            detector = cv2.SIFT_create()
        kp = detector.detect(gray, None)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        if kp:
            for kpt in kp:
                x, y = int(kpt.pt[0]), int(kpt.pt[1])
                r = int(kpt.size / 2)
                cv2.circle(out, (x, y), r, (0, 255, 0), 1)
                cv2.line(out, (x + r, y + r), (x - r, y - r), (0, 255, 0), 1)
                cv2.line(out, (x - r, y + r), (x + r, y - r), (0, 255, 0), 1)
        self.feature_count = len(kp) if kp else 0
        return self.ok(out, f"{self.feature_count} 个特征点")
