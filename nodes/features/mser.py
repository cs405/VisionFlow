"""MSER 特征检测 — 对应 WPF MserFeatureDetector"""

import cv2
from nodes.features.feature_base import FeatureBase


class MserFeatureDetector(FeatureBase):
    """MSER 特征检测"""

    def __init__(self):
        super().__init__()
        self.name = "MSER"

    def _create_detector(self):
        return cv2.MSER_create()
