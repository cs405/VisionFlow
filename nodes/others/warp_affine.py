import cv2
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class WarpAffineTransform(OpenCVNodeDataBase):
    __group__ = "其他模块"
    dx = Property(0, name="平移X", group=PropertyGroupNames.RUN_PARAMETERS)
    dy = Property(0, name="平移Y", group=PropertyGroupNames.RUN_PARAMETERS)
    angle = Property(0.0, name="旋转角度", group=PropertyGroupNames.RUN_PARAMETERS)
    scale = Property(1.0, name="缩放", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "仿射变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), self.angle, self.scale)
        M[0, 2] += self.dx
        M[1, 2] += self.dy
        return self.ok(cv2.warpAffine(mat, M, (w, h)))

    def _update_result_image_source(self):
        self._result_image_source = self._mat
