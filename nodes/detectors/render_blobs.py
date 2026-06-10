"""RenderBlobs 连通区域识别"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.detectors.detector_base import IDetectorGroupableNode

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class RenderBlobs(OpenCVNodeDataBase, IDetectorGroupableNode):
    """连通区域识别"""

    __group__ = "对象识别模块"

    connectivity = Property(4, name="像素连通性", group=PropertyGroupNames.RUN_PARAMETERS,
                            editor="choices", choices=[4, 8])
    min_area = Property(100.0, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_area = Property(10000000.0, name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS)
    blob_count = Property(0, name="Blob数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "连通区域识别"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

        # 连通组件分析
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=self.connectivity)

        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        count = 0
        for i in range(1, num_labels):  # skip background (label 0)
            area = stats[i, cv2.CC_STAT_AREA]
            if self.min_area <= area <= self.max_area:
                x = stats[i, cv2.CC_STAT_LEFT]
                y = stats[i, cv2.CC_STAT_TOP]
                w = stats[i, cv2.CC_STAT_WIDTH]
                h = stats[i, cv2.CC_STAT_HEIGHT]
                cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
                count += 1

        self.blob_count = count
        return self.ok(out, f"发现 {count} 个连通区域")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
