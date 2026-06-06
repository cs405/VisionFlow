"""Repeat - pixel replication node."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Repeat(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    repeat_y = Property(2, name="纵向重复次数", group=PropertyGroupNames.RUN_PARAMETERS)
    repeat_x = Property(2, name="横向重复次数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "像素复制"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        result = np.tile(mat, (self.repeat_y, self.repeat_x) if len(mat.shape) == 2
                          else (self.repeat_y, self.repeat_x, 1))
        return self.ok(result.astype(mat.dtype))

    def _update_result_image_source(self):
        self._result_image_source = self._mat
