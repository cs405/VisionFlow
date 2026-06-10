"""FREAK 描述子提取 — 对应 WPF FreakFeatureDetector"""

import cv2
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class FreakFeatureDetector(OpenCVNodeDataBase):
    """FREAK 描述子提取（先用 FAST 检测关键点，再用 FREAK 计算描述子）"""

    __group__ = "特征提取模块"

    feature_count = Property(0, name="特征点数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                             readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "FREAK"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
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
