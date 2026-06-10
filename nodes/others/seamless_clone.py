import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class SeamlessClone(OpenCVNodeDataBase):
    __group__ = "其他模块"
    clone_type = Property("NORMAL_CLONE", name="融合方式", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "无缝融合"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        if src is None or src.mat is None:
            return self.ok(mat, "无目标背景")
        h, w = mat.shape[:2]
        mask = np.ones((h, w), dtype=np.uint8) * 255
        cx, cy = w // 2, h // 2
        cmap = {"NORMAL_CLONE": cv2.NORMAL_CLONE, "MIXED_CLONE": cv2.MIXED_CLONE}
        result = cv2.seamlessClone(mat, src.mat, mask, (cx, cy), cmap.get(self.clone_type, cv2.NORMAL_CLONE))
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
