"""形态学节点基类"""

import cv2
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class MorphBase(OpenCVNodeDataBase):
    """形态学节点基类 — 封装卷积核设置与 morphologyEx 调用。子类只需设置 _morph_op。"""

    __group__ = "形态学模块"

    kernel_size = Property(3, name="卷积核大小", group=PropertyGroupNames.RUN_PARAMETERS)
    iterations = Property(1, name="迭代次数", group=PropertyGroupNames.RUN_PARAMETERS)
    kernel_shape = Property("RECT", name="卷积核形状", group=PropertyGroupNames.RUN_PARAMETERS,
                            editor="choices", choices=["RECT", "ELLIPSE", "CROSS"])

    _morph_op: int = cv2.MORPH_DILATE

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        shapes = {"RECT": cv2.MORPH_RECT, "ELLIPSE": cv2.MORPH_ELLIPSE, "CROSS": cv2.MORPH_CROSS}
        kernel = cv2.getStructuringElement(
            shapes.get(self.kernel_shape, cv2.MORPH_RECT),
            (self.kernel_size, self.kernel_size))
        result = cv2.morphologyEx(mat, self._morph_op, kernel, iterations=self.iterations)
        return self.ok(result)
