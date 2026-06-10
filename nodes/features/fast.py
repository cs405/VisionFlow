"""FAST 特征检测 — 对应 WPF FastFeatureDetector"""

import cv2
from core.node_base import Property, PropertyGroupNames
from nodes.features.feature_base import FeatureBase


class FastFeatureDetector(FeatureBase):
    """FAST 特征检测"""

    threshold = Property(10, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    nonmax_suppression = Property(True, name="非极大抑制", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "FAST"

    def _create_detector(self):
        return cv2.FastFeatureDetector_create(self.threshold, self.nonmax_suppression)
