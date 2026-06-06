"""Bitwise NOT node."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class BitwiseNot(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"

    def __init__(self):
        super().__init__()
        self.name = "按位取反"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        return self.ok(cv2.bitwise_not(mat))

    def _update_result_image_source(self):
        self._result_image_source = self._mat
