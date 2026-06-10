import cv2
from core.node_base import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class Hog(OpenCVNodeDataBase):
    __group__ = "其他模块"

    def __init__(self):
        super().__init__()
        self.name = "HOG描述子"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        hog = cv2.HOGDescriptor()
        h = hog.compute(gray)
        return self.ok(mat, f"HOG特征维度: {h.shape}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
