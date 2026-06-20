"""HoughLinesP 线段识别 """

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


class HoughLinesP(OpenCVNodeDataBase, IDetectorGroupableNode):
    """线段识别"""

    __group__ = "对象识别模块"

    rho = Property(1.0, name="距离分辨率", group=PropertyGroupNames.RUN_PARAMETERS)
    theta = Property(180.0, name="角度分辨率", group=PropertyGroupNames.RUN_PARAMETERS)
    threshold = Property(50, name="投票阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    min_line_length = Property(50.0, name="最小线段长度", group=PropertyGroupNames.RUN_PARAMETERS)
    max_line_length = Property(-1.0, name="最大线段长度", group=PropertyGroupNames.RUN_PARAMETERS,
                               description="-1 = 不限制")
    max_line_gap = Property(10.0, name="最大允许间隙", group=PropertyGroupNames.RUN_PARAMETERS)
    target_angle = Property(-1.0, name="目标角度", group=PropertyGroupNames.RUN_PARAMETERS,
                            description="-1=不过滤，只保留角度在 [目标±容差] 内的线段")
    tolerance = Property(15.0, name="角度容差", group=PropertyGroupNames.RUN_PARAMETERS)
    line_count = Property(0, name="线段数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "线段识别"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        edges = cv2.Canny(gray, 50, 200)
        lines = cv2.HoughLinesP(edges, self.rho, np.pi / self.theta, self.threshold,
                                minLineLength=self.min_line_length,
                                maxLineGap=self.max_line_gap)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        count = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # 最大长度过滤
                if self.max_line_length > 0:
                    length = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                    if length > self.max_line_length:
                        continue
                # 角度过滤
                if self.target_angle > 0:
                    angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                    diff = abs(((angle - self.target_angle) + 180) % 360 - 180)
                    if diff > self.tolerance:
                        continue
                cv2.line(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
                count += 1
        self.line_count = count
        return self.ok(out, f"检测到 {count} 条线段")
