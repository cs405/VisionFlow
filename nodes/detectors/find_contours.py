"""FindContours 轮廓识别 """

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.detectors.detector_base import IDetectorGroupableNode, DrawContourType

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class FindContours(OpenCVNodeDataBase, IDetectorGroupableNode):
    """轮廓识别"""

    __group__ = "对象识别模块"

    retrieval_mode = Property("TREE", name="检索模式", group=PropertyGroupNames.RUN_PARAMETERS,
                              editor="choices",
                              choices=["EXTERNAL", "LIST", "CCOMP", "TREE"])
    approx_mode = Property("SIMPLE", name="近似方法", group=PropertyGroupNames.RUN_PARAMETERS,
                           editor="choices",
                           choices=["NONE", "SIMPLE", "TC89_L1", "TC89_KCOS"])
    draw_type = Property("contours", name="绘制类型", group=PropertyGroupNames.RUN_PARAMETERS,
                         editor="choices",
                         choices=["contours", "bounding_rect", "min_area_rect",
                                  "convex_hull", "approx_poly"])
    contour_idx = Property(-1, name="轮廓索引", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="-1 = 全部")
    min_area = Property(100.0, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_area = Property(float(2**31 - 1), name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS)
    contour_count = Property(0, name="轮廓数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                             readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "轮廓识别"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

        mode_map = {"EXTERNAL": cv2.RETR_EXTERNAL, "LIST": cv2.RETR_LIST,
                    "CCOMP": cv2.RETR_CCOMP, "TREE": cv2.RETR_TREE}
        approx_map = {"NONE": cv2.CHAIN_APPROX_NONE, "SIMPLE": cv2.CHAIN_APPROX_SIMPLE,
                      "TC89_L1": cv2.CHAIN_APPROX_TC89_L1, "TC89_KCOS": cv2.CHAIN_APPROX_TC89_KCOS}

        contours, _ = cv2.findContours(
            binary, mode_map.get(self.retrieval_mode, cv2.RETR_TREE),
            approx_map.get(self.approx_mode, cv2.CHAIN_APPROX_SIMPLE))

        dt = DrawContourType(self.draw_type)
        out = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 2 else mat.copy()

        for c in contours:
            area = cv2.contourArea(c)
            if not (self.min_area <= area <= self.max_area):
                continue

            if dt == DrawContourType.CONTOURS:
                cv2.drawContours(out, [c], self.contour_idx, (0, 255, 0), 2)
            elif dt == DrawContourType.BOUNDING_RECT:
                x, y, w, h = cv2.boundingRect(c)
                cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
            elif dt == DrawContourType.MIN_AREA_RECT:
                rect = cv2.minAreaRect(c)
                box = np.int32(cv2.boxPoints(rect))
                cv2.drawContours(out, [box], 0, (0, 255, 0), 2)
            elif dt == DrawContourType.CONVEX_HULL:
                hull = cv2.convexHull(c)
                cv2.drawContours(out, [hull], 0, (0, 255, 0), 2)
            elif dt == DrawContourType.APPROX_POLY:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                cv2.drawContours(out, [approx], 0, (0, 255, 0), 2)

        self.contour_count = len(contours)
        return self.ok(out, f"发现 {len(contours)} 个轮廓")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
