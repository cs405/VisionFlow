"""Takeoff/segmentation nodes: HSVInRange, BitwiseAnd, SeamlessClone."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, VisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class HSVInRange(OpenCVNodeDataBase):
    __group__ = "图像分割提取模块"
    h_low = Property(0, name="H最小值", group=PropertyGroupNames.RUN_PARAMETERS)
    h_high = Property(180, name="H最大值", group=PropertyGroupNames.RUN_PARAMETERS)
    s_low = Property(0, name="S最小值", group=PropertyGroupNames.RUN_PARAMETERS)
    s_high = Property(255, name="S最大值", group=PropertyGroupNames.RUN_PARAMETERS)
    v_low = Property(0, name="V最小值", group=PropertyGroupNames.RUN_PARAMETERS)
    v_high = Property(255, name="V最大值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "HSV色彩提取"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        lower = np.array([self.h_low, self.s_low, self.v_low], dtype=np.uint8)
        upper = np.array([self.h_high, self.s_high, self.v_high], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        return self.ok(mask, "HSV色彩范围提取完成")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class BitwiseAnd(OpenCVNodeDataBase):
    __group__ = "图像分割提取模块"

    def __init__(self):
        super().__init__()
        self.name = "按位与掩膜"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        mask = None
        for n in self.from_node_datas:
            if isinstance(n, VisionNodeData) and n.mat is not None and len(n.mat.shape) == 2:
                mask = n.mat
                break
        if mask is None:
            return self.ok(mat, "无掩膜输入，保持原图")
        result = cv2.bitwise_and(mat, mat, mask=mask)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class SeamlessCloneBackground(OpenCVNodeDataBase):
    __group__ = "图像分割提取模块"
    clone_type = Property("NORMAL_CLONE", name="融合方式", group=PropertyGroupNames.RUN_PARAMETERS)
    center_x = Property(0, name="中心X", group=PropertyGroupNames.RUN_PARAMETERS)
    center_y = Property(0, name="中心Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "无缝融合/背景替换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        if src is None or src.mat is None:
            return self.ok(mat, "无背景图像，保持原图")
        clone_map = {"NORMAL_CLONE": cv2.NORMAL_CLONE, "MIXED_CLONE": cv2.MIXED_CLONE,
                      "MONOCHROME_TRANSFER": cv2.MONOCHROME_TRANSFER}
        mask = np.ones(mat.shape[:2], dtype=np.uint8) * 255
        cx, cy = self.center_x or mat.shape[1] // 2, self.center_y or mat.shape[0] // 2
        result = cv2.seamlessClone(mat, src.mat, mask, (cx, cy),
                                    clone_map.get(self.clone_type, cv2.NORMAL_CLONE))
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat
