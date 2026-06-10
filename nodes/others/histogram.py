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
        bins = max(1, min(self.hist_size, 512))
        hist = cv2.calcHist([gray], [0], None, [bins], [0, 256])
        # 白色背景 + 柱状图
        w_img, h_img = bins, 200
        hist_img = np.ones((h_img, w_img, 3), dtype=np.uint8) * 255
        cv2.normalize(hist, hist, 0, h_img, cv2.NORM_MINMAX)
        bin_w = max(1, w_img // bins)
        for i in range(bins):
            x = i * bin_w
            bar_h = int(hist[i])
            cv2.rectangle(hist_img, (x, h_img - bar_h), (x + bin_w - 1, h_img), (100, 100, 100), -1)
        return self.ok(hist_img, "直方图计算完成")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
