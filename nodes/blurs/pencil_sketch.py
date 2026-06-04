"""Pencil sketch + Stylization nodes."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class PencilSketch(OpenCVNodeDataBase):
    __group__ = "滤波模块"
    sigma_s = Property(60.0, name="空间标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma_r = Property(0.07, name="色彩标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    shade_factor = Property(0.02, name="阴影强度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "铅笔素描"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        gray, color = cv2.pencilSketch(mat, sigma_s=self.sigma_s, sigma_r=self.sigma_r,
                                         shade_factor=self.shade_factor)
        return self.ok(gray)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Stylization(OpenCVNodeDataBase):
    __group__ = "滤波模块"
    sigma_s = Property(60.0, name="空间标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma_r = Property(0.45, name="色彩标准差", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "风格化"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        return self.ok(cv2.stylization(mat, sigma_s=self.sigma_s, sigma_r=self.sigma_r))

    def _update_result_image_source(self):
        self._result_image_source = self._mat
