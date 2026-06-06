"""Rotate node - rotate image by angle."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Rotate(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    angle = Property(0.0, name="旋转角度", group=PropertyGroupNames.RUN_PARAMETERS)
    scale = Property(1.0, name="缩放比例", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "旋转"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, self.angle, self.scale)
        result = cv2.warpAffine(mat, M, (w, h))
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
