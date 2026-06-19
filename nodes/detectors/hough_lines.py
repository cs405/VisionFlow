"""HoughLines 直线识别"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from nodes.detectors.detector_base import IDetectorGroupableNode

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class HoughLines(OpenCVNodeDataBase, IDetectorGroupableNode):
    """直线识别"""

    __group__ = "对象识别模块"

    rho = Property(1.0, name="距离分辨率", group=PropertyGroupNames.RUN_PARAMETERS,
                   min_val=1.0, max_val=10000.0)
    theta = Property(180.0, name="角度分辨率", group=PropertyGroupNames.RUN_PARAMETERS,
                     min_val=1.0, max_val=360.0)
    threshold = Property(100, name="投票阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=100, max_val=200)
    srn = Property(0.0, name="细化距离分辨率", group=PropertyGroupNames.RUN_PARAMETERS)
    stn = Property(0.0, name="细化角度分辨率", group=PropertyGroupNames.RUN_PARAMETERS)
    line_count = Property(0, name="直线数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "直线识别"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        edges = cv2.Canny(gray, 50, 200)
        lines = cv2.HoughLines(edges, self.rho, np.pi / self.theta, self.threshold,
                               srn=self.srn, stn=self.stn)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        count = 0
        if lines is not None:
            for line in lines[:10]:  # limit to 10
                rho, theta = line[0]
                a, b = np.cos(theta), np.sin(theta)
                x0, y0 = a * rho, b * rho
                pt1 = (int(x0 + 1000 * (-b)), int(y0 + 1000 * a))
                pt2 = (int(x0 - 1000 * (-b)), int(y0 - 1000 * a))
                cv2.line(out, pt1, pt2, (0, 0, 255), 1)
                count += 1
        self.line_count = count
        return self.ok(out, f"检测到 {count} 条直线")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
