"""Resize - scale or fixed-size image resizing."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Resize(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    resize_mode = Property("Scale", name="缩放模式", group=PropertyGroupNames.RUN_PARAMETERS)
    scale = Property(1.0, name="缩放比例", group=PropertyGroupNames.RUN_PARAMETERS)
    width = Property(640, name="目标宽度", group=PropertyGroupNames.RUN_PARAMETERS)
    height = Property(640, name="目标高度", group=PropertyGroupNames.RUN_PARAMETERS)
    interpolation = Property("LINEAR", name="插值方式", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "图像缩放"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        inter = getattr(cv2, f"INTER_{self.interpolation}", cv2.INTER_LINEAR)
        if self.resize_mode == "Scale":
            w = int(mat.shape[1] * self.scale)
            h = int(mat.shape[0] * self.scale)
        else:
            w, h = self.width, self.height
        result = cv2.resize(mat, (max(1, w), max(1, h)), interpolation=inter)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
