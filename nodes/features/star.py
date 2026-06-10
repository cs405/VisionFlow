"""Star 特征检测 — 对应 WPF StarFeatureDetector"""

import cv2
from nodes.features.feature_base import FeatureBase


class StarFeatureDetector(FeatureBase):
    """Star 特征检测（不可用时回退 SIFT）"""

    def __init__(self):
        super().__init__()
        self.name = "StarDetector"

    def _create_detector(self):
        if hasattr(cv2, 'xfeatures2d'):
            return cv2.xfeatures2d.StarDetector_create()
        return cv2.SIFT_create()
