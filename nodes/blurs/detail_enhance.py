"""Detail enhance + Edge-preserving filter nodes."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class DetailEnhance(OpenCVNodeDataBase):
    __group__ = "滤波模块"
    sigma_s = Property(10.0, name="空间标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma_r = Property(0.15, name="色彩标准差", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "细节增强"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        return self.ok(cv2.detailEnhance(mat, sigma_s=self.sigma_s, sigma_r=self.sigma_r))

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class EdgePreservingFilter(OpenCVNodeDataBase):
    __group__ = "滤波模块"
    filter_type = Property("RECURSIVE", name="滤波类型", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma_s = Property(60.0, name="空间标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    sigma_r = Property(0.4, name="色彩标准差", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "边缘保留滤波"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        flags = {"RECURSIVE": cv2.RECURS_FILTER, "NORMCONV": cv2.NORMCONV_FILTER}
        return self.ok(cv2.edgePreservingFilter(mat, flags=flags.get(self.filter_type, cv2.RECURS_FILTER),
                                                  sigma_s=self.sigma_s, sigma_r=self.sigma_r))

    def _update_result_image_source(self):
        self._result_image_source = self._mat
