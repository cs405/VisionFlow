"""QRCode 二维码识别"""

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


class QRCode(OpenCVNodeDataBase, IDetectorGroupableNode):
    """二维码识别。大图自动缩放加速检测。"""

    __group__ = "对象识别模块"

    qr_result = Property("", name="二维码结果", group=PropertyGroupNames.RESULT_PARAMETERS,
                         readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "二维码识别"
        self._detector = None
        self._frame_skip = 0
        self._cached_points = None
        self._cached_msg = ""

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        # 每 3 帧检测一次，其余帧复用缓存
        self._frame_skip = (self._frame_skip + 1) % 3
        if self._frame_skip == 0:
            if self._detector is None:
                self._detector = cv2.QRCodeDetector()
            try:
                # detectAndDecode 一次性检测+解码，points 用于画框
                data, points, _ = self._detector.detectAndDecode(mat)
                if points is not None:
                    self._cached_points = points.reshape(4, 2).astype(int)
                    if data:
                        self.qr_result = data
                        self._cached_msg = f"QR: {data}"
                    else:
                        self._cached_msg = "检测到二维码 (解码失败)"
                else:
                    self.qr_result = ""
                    self._cached_points = None
                    self._cached_msg = ""
            except Exception:
                self.qr_result = ""
                self._cached_points = None
                self._cached_msg = ""

        out = mat.copy()
        if self._cached_points is not None:
            pts = self._cached_points  # shape (4, 2), pts[i] = [x, y]
            for i in range(4):
                p1 = tuple(pts[i])
                p2 = tuple(pts[(i+1) % 4])
                cv2.line(out, p1, p2, (0, 255, 0), 2)
            return self.ok(out, self._cached_msg)
        return self.ok(out, self._cached_msg or "未检测到二维码")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
