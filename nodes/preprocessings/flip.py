"""Flip node - horizontal/vertical/both flip."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Flip(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    flip_code = Property(0, name="翻转模式", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "翻转"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        result = cv2.flip(mat, self.flip_code)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
