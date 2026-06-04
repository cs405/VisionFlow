"""Feature extraction nodes: AKAZE, BRISK, FAST, FREAK, KAZE, MSER, Star, Homography."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _FeatureBase(OpenCVNodeDataBase):
    """Base for feature detector nodes. Checks algorithm availability before running."""
    feature_count = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        try:
            detector = self._create_detector()
        except Exception as e:
            return self.error(None, f"特征算法不可用: {e}\n请确认 opencv-contrib-python 已安装")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        try:
            keypoints = detector.detect(gray, None)
        except Exception as e:
            return self.error(None, f"特征检测失败: {e}")
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        cv2.drawKeypoints(out, keypoints, out, (0, 255, 0),
                           cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        self.feature_count = len(keypoints)
        return self.ok(out, f"{len(keypoints)} 个特征点")

    def _create_detector(self):
        raise NotImplementedError

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class AKazeFeatureDetector(_FeatureBase):
    __group__ = "特征提取模块"
    def __init__(self): super().__init__(); self.name = "AKAZE"
    def _create_detector(self): return cv2.AKAZE_create()


class BriskFeatureDetector(_FeatureBase):
    __group__ = "特征提取模块"
    def __init__(self): super().__init__(); self.name = "BRISK"
    def _create_detector(self): return cv2.BRISK_create()


class FastFeatureDetector(_FeatureBase):
    __group__ = "特征提取模块"
    threshold = Property(10, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    nonmax_suppression = Property(True, name="非极大抑制", group=PropertyGroupNames.RUN_PARAMETERS)
    def __init__(self): super().__init__(); self.name = "FAST"
    def _create_detector(self): return cv2.FastFeatureDetector_create(self.threshold, self.nonmax_suppression)


class FreakFeatureDetector(OpenCVNodeDataBase):
    """FREAK is a descriptor extractor (needs keypoints first)."""
    __group__ = "特征提取模块"
    feature_count = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "FREAK"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        fast = cv2.FastFeatureDetector_create()
        kp = fast.detect(gray, None)
        freak = cv2.xfeatures2d.FREAK_create() if hasattr(cv2, 'xfeatures2d') else None
        if freak is not None:
            kp, des = freak.compute(gray, kp)
        out = cv2.drawKeypoints(mat, kp, None, (0, 255, 0),
                                 cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        self.feature_count = len(kp)
        return self.ok(out, f"{len(kp)} 个FREAK特征点")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class KazeFeatureDetector(_FeatureBase):
    __group__ = "特征提取模块"
    def __init__(self): super().__init__(); self.name = "KAZE"
    def _create_detector(self): return cv2.KAZE_create()


class MserFeatureDetector(_FeatureBase):
    __group__ = "特征提取模块"
    def __init__(self): super().__init__(); self.name = "MSER"
    def _create_detector(self): return cv2.MSER_create()


class StarFeatureDetector(_FeatureBase):
    __group__ = "特征提取模块"
    def __init__(self): super().__init__(); self.name = "StarDetector"
    def _create_detector(self):
        return cv2.xfeatures2d.StarDetector_create() if hasattr(cv2, 'xfeatures2d') else cv2.SIFT_create()


class HomographyTransform(OpenCVNodeDataBase):
    """Homography transform using feature matching between two images."""
    __group__ = "特征提取模块"
    match_count = Property(0, name="匹配点数", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "单应性变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
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
