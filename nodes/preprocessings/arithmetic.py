"""Arithmetic operation nodes: Add/Subtract, Multiply/Divide, Pow."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class AddSubtract(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    operation = Property("Add", name="运算", group=PropertyGroupNames.RUN_PARAMETERS)
    scalar = Property(50.0, name="标量值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "图像加减"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        if self.operation == "Add": result = cv2.add(mat, self.scalar)
        else: result = cv2.subtract(mat, self.scalar)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class MultiplyDivide(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    operation = Property("Multiply", name="运算", group=PropertyGroupNames.RUN_PARAMETERS)
    scalar = Property(2.0, name="标量值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "图像乘除"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        if self.operation == "Multiply": result = cv2.multiply(mat, self.scalar)
        else: result = cv2.divide(mat, self.scalar)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Pow(OpenCVNodeDataBase):
    __group__ = "图像预处理模块"
    power = Property(2.0, name="幂值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "幂运算"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        result = cv2.pow(mat, self.power)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
