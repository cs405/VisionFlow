"""Morphology nodes: Dilate, Erode, Open, Close, Gradient, TopHat, BlackHat."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _MorphBase(OpenCVNodeDataBase):
    """Base for morphology nodes with kernel settings."""
    kernel_size = Property(3, name="卷积核大小", group=PropertyGroupNames.RUN_PARAMETERS)
    iterations = Property(1, name="迭代次数", group=PropertyGroupNames.RUN_PARAMETERS)
    kernel_shape = Property("RECT", name="卷积核形状", group=PropertyGroupNames.RUN_PARAMETERS)

    _morph_op: int = cv2.MORPH_DILATE

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        shapes = {"RECT": cv2.MORPH_RECT, "ELLIPSE": cv2.MORPH_ELLIPSE, "CROSS": cv2.MORPH_CROSS}
        kernel = cv2.getStructuringElement(shapes.get(self.kernel_shape, cv2.MORPH_RECT),
                                            (self.kernel_size, self.kernel_size))
        result = cv2.morphologyEx(mat, self._morph_op, kernel, iterations=self.iterations)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Dilate(_MorphBase):
    __group__ = "形态学模块"
    _morph_op = cv2.MORPH_DILATE
    def __init__(self): super().__init__(); self.name = "膨胀"


class Erode(_MorphBase):
    __group__ = "形态学模块"
    _morph_op = cv2.MORPH_ERODE
    def __init__(self): super().__init__(); self.name = "腐蚀"


class Open(_MorphBase):
    __group__ = "形态学模块"
    _morph_op = cv2.MORPH_OPEN
    def __init__(self): super().__init__(); self.name = "开运算"


class Close(_MorphBase):
    __group__ = "形态学模块"
    _morph_op = cv2.MORPH_CLOSE
    def __init__(self): super().__init__(); self.name = "闭运算"


class Gradient(_MorphBase):
    __group__ = "形态学模块"
    _morph_op = cv2.MORPH_GRADIENT
    def __init__(self): super().__init__(); self.name = "形态学梯度"


class TopHat(_MorphBase):
    __group__ = "形态学模块"
    _morph_op = cv2.MORPH_TOPHAT
    def __init__(self): super().__init__(); self.name = "顶帽"


class BlackHat(_MorphBase):
    __group__ = "形态学模块"
    _morph_op = cv2.MORPH_BLACKHAT
    def __init__(self): super().__init__(); self.name = "黑帽"
