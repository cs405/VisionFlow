"""特征检测器基类"""

import cv2
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class FeatureBase(OpenCVNodeDataBase):
    """特征检测器基类。提供 _draw_keypoints 标准绘制，子类实现 invoke_core。"""

    __group__ = "特征提取模块"
    feature_count = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def _get_gray(self, from_node):
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return None, None
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        return mat, gray

    def _draw_keypoints(self, mat, keypoints, color=(0, 255, 0)):
        """标准 rich keypoints 绘制"""
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        cv2.drawKeypoints(out, keypoints, out, color, cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        return out

    def _update_result_image_source(self):
        self._result_image_source = self._mat
