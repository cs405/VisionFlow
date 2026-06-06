"""Normalize node."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Normalize(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    alpha = Property(1.0, name="Alpha", group=PropertyGroupNames.RUN_PARAMETERS)
    beta = Property(0.0, name="Beta", group=PropertyGroupNames.RUN_PARAMETERS)
    norm_type = Property("MinMax", name="归一化类型", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "归一化"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        nmap = {"MinMax": cv2.NORM_MINMAX, "L1": cv2.NORM_L1, "L2": cv2.NORM_L2, "INF": cv2.NORM_INF}
        result = np.zeros_like(mat, dtype=np.float32)
        cv2.normalize(mat, result, self.alpha, self.beta, nmap.get(self.norm_type, cv2.NORM_MINMAX))
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
