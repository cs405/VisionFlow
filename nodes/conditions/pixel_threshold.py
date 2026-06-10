"""像素阈值条件节点"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames, LogicModuleNode
from core.data_packet import FlowableResult

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class PixelThresholdConditionNode(OpenCVNodeDataBase, LogicModuleNode):
    """像素阈值条件

    通过左右两个输出端口实现分支路由（"满足条件"/"不满足条件"）。

    端口布局:
           ┌── 输入(Top) ──┐
           │                │
      不满足(Left)      满足(Right)
    """

    __group__ = "逻辑模块"

    threshold = Property(128, name="像素阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    compare = Property(">", name="比较方式", group=PropertyGroupNames.RUN_PARAMETERS)
    min_pixels = Property(100, name="最小像素数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "像素阈值条件"
        self._match_count = 0
        self._active_output_port_name = ""

    def _init_ports(self):
        """1 个顶部输入 + 左右 2 个命名输出"""
        from core.node_base import PortDock, PortType
        self.ports = []
        p = self.create_port_data()
        p.dock = PortDock.TOP
        p.port_type = PortType.INPUT
        self.ports.append(p)
        p = self.create_port_data()
        p.dock = PortDock.LEFT
        p.port_type = PortType.OUTPUT
        p.name = "不满足条件"
        self.ports.append(p)
        p = self.create_port_data()
        p.dock = PortDock.RIGHT
        p.port_type = PortType.OUTPUT
        p.name = "满足条件"
        self.ports.append(p)

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        if self.compare == ">":
            count = int(np.sum(gray > self.threshold))
        else:
            count = int(np.sum(gray < self.threshold))
        self._match_count = count
        if count >= self.min_pixels:
            self._active_output_port_name = "满足条件"
            return self.ok(mat, f"满足条件: {count} >= {self.min_pixels}")
        else:
            self._active_output_port_name = "不满足条件"
            return self.ok(mat, f"不满足条件: {count} < {self.min_pixels}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
