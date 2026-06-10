"""行人检测 """

import cv2
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class Hog(OpenCVNodeDataBase):
    """行人检测使用 HOG + SVM 默认行人检测器。"""

    __group__ = "其他模块"

    hit_threshold = Property(0.0, name="命中阈值", group=PropertyGroupNames.RUN_PARAMETERS, step=0.1,
                             description="越小检出越多但误检也越多")
    win_stride = Property("8,8", name="窗口步长", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="滑动窗口步长(w,h)")
    scale = Property(1.05, name="缩放系数", group=PropertyGroupNames.RUN_PARAMETERS, step=0.01, decimals=2,
                     description="图像金字塔缩放系数")
    group_threshold = Property(2, name="分组阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                               description="0=不分组")
    detect_count = Property(0, name="检测数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "行人检测"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        ws = [int(x) for x in self.win_stride.split(",") if x.strip()]
        ws = (ws[0], ws[1]) if len(ws) == 2 else (8, 8)
        found, weights = hog.detectMultiScale(mat, hitThreshold=self.hit_threshold,
                                               winStride=ws, scale=self.scale,
                                               groupThreshold=self.group_threshold)
        out = mat.copy()
        for (x, y, w, h) in found:
            rw, rh = int(w * 0.1), int(h * 0.1)
            cv2.rectangle(out, (x + rw, y + rh), (x + w - rw, y + h - rh), (0, 255, 0), 2)
        self.detect_count = len(found)
        return self.ok(out, f"检测到 {len(found)} 个行人")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
