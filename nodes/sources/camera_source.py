"""Camera capture source - captures frames from a webcam.
"""

import cv2
import numpy as np

from core.node_base import OpenCVNodeDataBase, SrcFilesVisionNodeData, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class CameraCaptureNodeData(SrcFilesVisionNodeData, OpenCVNodeDataBase):
    """Captures frames from a camera device.
    """
    __group__ = "图像数据源"

    camera_index = Property(0, name="摄像头索引", group=PropertyGroupNames.RUN_PARAMETERS)
    frame_width = Property(640, name="帧宽度", group=PropertyGroupNames.RUN_PARAMETERS)
    frame_height = Property(480, name="帧高度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        SrcFilesVisionNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "摄像头"
        self.src_file_paths.clear()
        self.src_file_path = ""
        # 摄像头长连接：只在首次 invoke 时打开，dispose 时释放，避免每次拍照都重新 open/close
        self._cap: cv2.VideoCapture | None = None

    def _ensure_cap(self) -> cv2.VideoCapture | None:
        """懒加载摄像头连接，只打开一次"""
        if self._cap is not None and self._cap.isOpened():
            return self._cap
        self._cap = cv2.VideoCapture(self.camera_index)
        if not self._cap.isOpened():
            self._cap = None
            return None
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)  # 设置摄像头分辨率宽度
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)  # 设置摄像头分辨率高度
        return self._cap

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        cap = self._ensure_cap()  # 复用已打开的摄像头连接，不再每次重新 open/close
        if cap is None:
            return self.error(None, f"无法打开摄像头 {self.camera_index}")
        ret, frame = cap.read()  # 从持续打开的摄像头读取最新一帧
        if not ret:
            return self.error(None, f"无法从摄像头 {self.camera_index} 读取帧")
        self.pixel_width = frame.shape[1]   # 记录图像宽度（像素）
        self.pixel_height = frame.shape[0]  # 记录图像高度（像素）
        return self.ok(frame, "摄像头捕获")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def dispose(self):
        """释放摄像头长连接"""
        if self._cap is not None:
            self._cap.release()  # 释放摄像头硬件资源
            self._cap = None
        super().dispose()

