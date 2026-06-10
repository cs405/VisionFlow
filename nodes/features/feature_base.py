"""特征检测器基类 — 对应 WPF FeatureOpenCVNodeDataBase"""

import cv2

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class FeatureBase(OpenCVNodeDataBase):
    """特征检测器基类 — 对应 WPF FeatureOpenCVNodeDataBase : OpenCVNodeDataBase, IFeatureDetectorOpenCVNodeData。

    子类只需实现 _create_detector() 返回对应的 cv2 Feature2D 对象。
    """

    __group__ = "特征提取模块"

    feature_count = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                             readonly=True)

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        try:
            detector = self._create_detector()
        except Exception as e:
            return self.error(None, f"特征算法不可用: {e}")

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
        """子类重写：创建特征检测器。"""
        raise NotImplementedError

    def _update_result_image_source(self):
        self._result_image_source = self._mat
