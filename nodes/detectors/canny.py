"""Canny 边缘检测"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.detectors.detector_base import IDetectorGroupableNode

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class Canny(OpenCVNodeDataBase, IDetectorGroupableNode):
    """Canny 边缘检测 """

    __group__ = "对象识别模块"

    threshold1 = Property(50.0, name="低阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                          min_val=50.0, max_val=100.0)
    threshold2 = Property(200.0, name="高阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                          min_val=150.0, max_val=200.0)
    aperture_size = Property(3, name="Sobel核大小", group=PropertyGroupNames.RUN_PARAMETERS)
    l2_gradient = Property(False, name="L2梯度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "边缘识别"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        result = cv2.Canny(gray, self.threshold1, self.threshold2,
                           apertureSize=self.aperture_size, L2gradient=self.l2_gradient)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
