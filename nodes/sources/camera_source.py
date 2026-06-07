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

    def invoke_core(self, src_image_node_data, from_node_data, diagram) -> FlowableResult:
        cap = cv2.VideoCapture(self.camera_index)
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            ret, frame = cap.read()
            if not ret:
                return self.error(None, f"无法从摄像头 {self.camera_index} 读取帧")
            self.pixel_width = frame.shape[1]
            self.pixel_height = frame.shape[0]
            return self.ok(frame, "摄像头捕获")
        finally:
            cap.release()

    def _update_result_image_source(self):
        self._result_image_source = self._mat

