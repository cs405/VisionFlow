"""Color space conversion node."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


_COLOR_CODES = {
    "BGR2GRAY": cv2.COLOR_BGR2GRAY, "GRAY2BGR": cv2.COLOR_GRAY2BGR,
    "BGR2HSV": cv2.COLOR_BGR2HSV, "HSV2BGR": cv2.COLOR_HSV2BGR,
    "BGR2LAB": cv2.COLOR_BGR2LAB, "LAB2BGR": cv2.COLOR_LAB2BGR,
    "BGR2YUV": cv2.COLOR_BGR2YUV, "YUV2BGR": cv2.COLOR_YUV2BGR,
    "BGR2RGB": cv2.COLOR_BGR2RGB, "RGB2BGR": cv2.COLOR_RGB2BGR,
    "BGR2YCrCb": cv2.COLOR_BGR2YCrCb, "YCrCb2BGR": cv2.COLOR_YCrCb2BGR,
    "BGR2HLS": cv2.COLOR_BGR2HLS, "HLS2BGR": cv2.COLOR_HLS2BGR,
}


class CvtColor(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    color_code = Property("BGR2GRAY", name="色彩转换模式", group=PropertyGroupNames.RUN_PARAMETERS)
    dst_cn = Property(0, name="目标通道数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "色彩空间转换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        code = _COLOR_CODES.get(self.color_code, cv2.COLOR_BGR2GRAY)
        result = cv2.cvtColor(mat, code, dstCn=self.dst_cn)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
