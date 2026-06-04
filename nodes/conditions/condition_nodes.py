"""Condition/logic nodes: condition branch and pixel threshold condition."""
import cv2
import numpy as np
from core.node_base import (ConditionNodeData, OpenCVNodeDataBase, Property,
                           PropertyGroupNames, WaitAllParallelNodeData)  # re-export for plugin discovery
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class OpenCVConditionNode(ConditionNodeData, OpenCVNodeDataBase):
    """General condition branch node. Evaluates conditions on upstream results."""
    __group__ = "逻辑模块"

    def __init__(self):
        ConditionNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "条件分支"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        return self.ok(mat)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class PixelThresholdConditionNode(OpenCVNodeDataBase):
    """Condition based on pixel count above/below threshold."""
    __group__ = "逻辑模块"
    threshold = Property(128, name="像素阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    compare = Property(">", name="比较方式", group=PropertyGroupNames.RUN_PARAMETERS)
    min_pixels = Property(100, name="最小像素数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "像素阈值条件"
        self._match_count = 0

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        if self.compare == ">":
            count = np.sum(gray > self.threshold)
        else:
            count = np.sum(gray < self.threshold)
        self._match_count = count
        if count >= self.min_pixels:
            return self.ok(mat, f"满足条件: {count} >= {self.min_pixels}")
        return self.break_(mat, f"不满足条件: {count} < {self.min_pixels}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
