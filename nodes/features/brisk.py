"""BRISK 特征检测 — 对应 WPF BriskFeatureDetector"""

import cv2
from nodes.features.feature_base import FeatureBase


class BriskFeatureDetector(FeatureBase):
    """BRISK 特征检测"""

    def __init__(self):
        super().__init__()
        self.name = "BRISK"

    def _create_detector(self):
        return cv2.BRISK_create()
