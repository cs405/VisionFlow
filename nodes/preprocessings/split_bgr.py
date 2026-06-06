"""Split BGR - channel separation node."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class SplitBGR(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    channel = Property("B", name="输出通道", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "BGR通道分离"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        if len(mat.shape) < 3: return self.ok(mat)
        b, g, r = cv2.split(mat)
        ch = {"B": b, "G": g, "R": r}.get(self.channel, b)
        return self.ok(ch)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
