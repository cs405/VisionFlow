"""QRCode 二维码识别 — 对应 WPF QRCode"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.detectors.detector_base import IDetectorGroupableNode

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class QRCode(OpenCVNodeDataBase, IDetectorGroupableNode):
    """二维码识别 — 对应 WPF QRCode : OpenCVDetectorNodeDataBase, IDetectorGroupableNodeData"""

    __group__ = "对象识别模块"

    qr_result = Property("", name="二维码结果", group=PropertyGroupNames.RESULT_PARAMETERS,
                         readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "二维码识别"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(mat)
        out = mat.copy()
        if data:
            self.qr_result = data
            if points is not None:
                pts = points.astype(int)
                for i in range(4):
                    cv2.line(out, tuple(pts[i][0]), tuple(pts[(i+1) % 4][0]), (0, 255, 0), 2)
            return self.ok(out, f"QR: {data}")
        self.qr_result = ""
        return self.ok(out, "未检测到二维码")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
