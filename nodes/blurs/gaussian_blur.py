"""Gaussian blur node."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class GaussianBlur(OpenCVNodeDataBase):
    __group__ = "滤波模块"
    ksize = Property(7, name="卷积核大小", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma_x = Property(0.0, name="Sigma X", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma_y = Property(0.0, name="Sigma Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "高斯模糊"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        k = self.ksize if self.ksize % 2 == 1 else self.ksize + 1
        result = cv2.GaussianBlur(mat, (k, k), self.sigma_x, self.sigma_y)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Blur(OpenCVNodeDataBase):
    __group__ = "滤波模块"
    ksize = Property(7, name="卷积核大小", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "均值模糊"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        k = self.ksize if self.ksize % 2 == 1 else self.ksize + 1
        return self.ok(cv2.blur(mat, (k, k)))

    def _update_result_image_source(self):
        self._result_image_source = self._mat
