import cv2
from core.data_packet import FlowableResult
from nodes.others.haar_cascade import HaarCascade


class LbpCascade(HaarCascade):
    __group__ = "其他模块"

    def __init__(self):
        super().__init__()
        self.name = "LBP级联分类器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "lbpcascade_frontalface_improved.xml")
        objects = cascade.detectMultiScale(gray, self.scale_factor, self.min_neighbors)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        for (x, y, w, h) in objects:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        self.detect_count = len(objects)
        return self.ok(out, f"LBP检测到 {len(objects)} 个目标")
