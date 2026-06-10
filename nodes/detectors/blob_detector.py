"""BlobDetector Blob 识别 — 对应 WPF BlobDetector"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.detectors.detector_base import IDetectorGroupableNode

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class BlobDetector(OpenCVNodeDataBase, IDetectorGroupableNode):
    """Blob 识别 — 对应 WPF BlobDetector : OpenCVDetectorNodeDataBase, IDetectorGroupableNodeData"""

    __group__ = "对象识别模块"

    blob_type = Property("none", name="形状类型", group=PropertyGroupNames.RUN_PARAMETERS,
                         editor="choices", choices=["none", "circle", "oval"])
    threshold_step = Property(10.0, name="阈值步长", group=PropertyGroupNames.RUN_PARAMETERS)
    min_threshold = Property(10.0, name="最小阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    max_threshold = Property(220.0, name="最大阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    min_repeatability = Property(2, name="最小重复性", group=PropertyGroupNames.RUN_PARAMETERS)
    min_dist_between_blobs = Property(10.0, name="最小间距", group=PropertyGroupNames.RUN_PARAMETERS)
    filter_by_color = Property(True, name="按颜色过滤", group=PropertyGroupNames.RUN_PARAMETERS)
    blob_color = Property(0, name="颜色(0=暗 255=亮)", group=PropertyGroupNames.RUN_PARAMETERS)
    filter_by_area = Property(True, name="按面积过滤", group=PropertyGroupNames.RUN_PARAMETERS)
    min_area = Property(100.0, name="最小面积", group=PropertyGroupNames.RUN_PARAMETERS)
    max_area = Property(10000.0, name="最大面积", group=PropertyGroupNames.RUN_PARAMETERS)
    filter_by_circularity = Property(True, name="按圆形度过滤", group=PropertyGroupNames.RUN_PARAMETERS)
    min_circularity = Property(0.8, name="最小圆形度", group=PropertyGroupNames.RUN_PARAMETERS)
    max_circularity = Property(10.0, name="最大圆形度", group=PropertyGroupNames.RUN_PARAMETERS)
    filter_by_convexity = Property(True, name="按凸性过滤", group=PropertyGroupNames.RUN_PARAMETERS)
    min_convexity = Property(0.87, name="最小凸性", group=PropertyGroupNames.RUN_PARAMETERS)
    max_convexity = Property(10.0, name="最大凸性", group=PropertyGroupNames.RUN_PARAMETERS)
    filter_by_inertia = Property(False, name="惯性过滤", group=PropertyGroupNames.RUN_PARAMETERS)
    min_inertia_ratio = Property(0.1, name="最小惯性比", group=PropertyGroupNames.RUN_PARAMETERS)
    max_inertia_ratio = Property(10.0, name="最大惯性比", group=PropertyGroupNames.RUN_PARAMETERS)
    blob_count = Property(0, name="Blob数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    _PRESETS = {
        "circle": {
            "min_threshold": 10, "max_threshold": 230, "filter_by_area": True,
            "min_area": 500, "max_area": 50000, "filter_by_circularity": True,
            "min_circularity": 0.9, "filter_by_convexity": True, "min_convexity": 0.95,
            "filter_by_inertia": True, "min_inertia_ratio": 0.95,
        },
        "oval": {
            "min_threshold": 10, "max_threshold": 230, "filter_by_area": True,
            "min_area": 500, "max_area": 10000, "filter_by_circularity": True,
            "min_circularity": 0.58, "filter_by_convexity": True, "min_convexity": 0.96,
            "filter_by_inertia": True, "min_inertia_ratio": 0.1,
        },
    }

    def __init__(self):
        super().__init__()
        self.name = "Blob识别"
        self._last_blob_type = "none"

    def _apply_preset(self, preset_name: str):
        """应用预设参数 — 对应 WPF RefreshData + CopyFrom。仅在形状类型切换时调用。"""
        if preset_name in self._PRESETS:
            for k, v in self._PRESETS[preset_name].items():
                setattr(self, k, v)

    def _build_params(self) -> cv2.SimpleBlobDetector_Params:
        """从当前属性构建 SimpleBlobDetector 参数 — 对应 WPF CopyTo。"""
        if self.blob_type != self._last_blob_type and self.blob_type != "none":
            self._apply_preset(self.blob_type)
        self._last_blob_type = self.blob_type

        params = cv2.SimpleBlobDetector_Params()
        params.thresholdStep = float(self.threshold_step)
        params.minThreshold = float(self.min_threshold)
        params.maxThreshold = float(self.max_threshold)
        params.minRepeatability = int(self.min_repeatability)
        params.minDistBetweenBlobs = float(self.min_dist_between_blobs)
        params.filterByColor = bool(self.filter_by_color)
        params.blobColor = int(self.blob_color)
        params.filterByArea = bool(self.filter_by_area)
        params.minArea = float(self.min_area)
        params.maxArea = float(self.max_area)
        params.filterByCircularity = bool(self.filter_by_circularity)
        params.minCircularity = float(self.min_circularity)
        params.maxCircularity = float(self.max_circularity)
        params.filterByConvexity = bool(self.filter_by_convexity)
        params.minConvexity = float(self.min_convexity)
        params.maxConvexity = float(self.max_convexity)
        params.filterByInertia = bool(self.filter_by_inertia)
        params.minInertiaRatio = float(self.min_inertia_ratio)
        params.maxInertiaRatio = float(self.max_inertia_ratio)
        return params

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        params = self._build_params()
        detector = cv2.SimpleBlobDetector_create(params)
        keypoints = detector.detect(mat)
        out = cv2.drawKeypoints(mat, keypoints, None, (0, 255, 0),
                                cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        self.blob_count = len(keypoints)
        return self.ok(out, f"检测到 {len(keypoints)} 个Blob")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
