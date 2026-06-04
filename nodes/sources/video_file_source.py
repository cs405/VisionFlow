"""Video file source - reads frames from a video file.

Ported from H.VisionMaster.OpenCV/NodeDatas/1 - Src/SrcVideoFilesNodeData.cs
"""

import os
import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, SrcFilesVisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class SrcVideoFilesNodeData(SrcFilesVisionNodeData, OpenCVNodeDataBase):
    """Reads video frames as image source.

    Mirrors C# SrcVideoFilesNodeData : VideoCaptureNodeDataBase.
    """
    __group__ = "图像数据源"

    frame_index = Property(0, name="帧索引", group=PropertyGroupNames.RUN_PARAMETERS, readonly=True)
    fps = Property(0.0, name="帧率", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        SrcFilesVisionNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "视频文件"
        self._cap: cv2.VideoCapture | None = None

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        path = self.src_file_path
        if not path or not os.path.exists(path):
            return self.error(None, f"视频文件不存在: {path}")

        if self._cap is None or not self._cap.isOpened():
            self._cap = cv2.VideoCapture(path)
            self.fps = self._cap.get(cv2.CAP_PROP_FPS)

        ret, frame = self._cap.read()
        if not ret:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
            if not ret:
                return self.error(None, "无法读取视频帧")

        self.frame_index = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
        self.pixel_width = frame.shape[1]
        self.pixel_height = frame.shape[0]
        return self.ok(frame, f"帧: {self.frame_index}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def dispose(self):
        if self._cap:
            self._cap.release()
            self._cap = None
        super().dispose()
