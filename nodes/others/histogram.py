import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class Hist(OpenCVNodeDataBase):
    __group__ = "其他模块"
    hist_size = Property(256, name="直方图大小", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "直方图"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        hist = cv2.calcHist([gray], [0], None, [self.hist_size], [0, 256])
        hist_img = np.zeros((256, 256, 3), dtype=np.uint8)
        cv2.normalize(hist, hist, 0, 256, cv2.NORM_MINMAX)
        for i in range(1, 256):
            cv2.line(hist_img, (i-1, 255 - int(hist[i-1])), (i, 255 - int(hist[i])), (0, 255, 0), 1)
        return self.ok(hist_img, "直方图计算完成")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
