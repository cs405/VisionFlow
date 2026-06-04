"""Threshold node - binary/inverse/trunc/tozero thresholding."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine

_THRESH_TYPES = {
    "Binary": cv2.THRESH_BINARY, "BinaryInv": cv2.THRESH_BINARY_INV,
    "Trunc": cv2.THRESH_TRUNC, "ToZero": cv2.THRESH_TOZERO,
    "ToZeroInv": cv2.THRESH_TOZERO_INV, "Otsu": cv2.THRESH_OTSU,
    "Triangle": cv2.THRESH_TRIANGLE,
}


class Threshold(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    thresh = Property(125.0, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    maxval = Property(255.0, name="最大值", group=PropertyGroupNames.RUN_PARAMETERS)
    threshold_type = Property("Binary", name="阈值类型", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "阈值化"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        ttype = _THRESH_TYPES.get(self.threshold_type, cv2.THRESH_BINARY)
        _, result = cv2.threshold(gray, self.thresh, self.maxval, ttype)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
