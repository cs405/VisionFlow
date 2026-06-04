"""Video processing nodes: MOG background subtraction, VideoWriter."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class MOG(OpenCVNodeDataBase):
    """MOG2 background subtraction for motion detection."""
    __group__ = "视频处理模块"
    history = Property(500, name="历史帧数", group=PropertyGroupNames.RUN_PARAMETERS)
    var_threshold = Property(16.0, name="方差阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    detect_shadows = Property(True, name="检测阴影", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "MOG背景减除"
        self._mog = None

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        if self._mog is None:
            self._mog = cv2.createBackgroundSubtractorMOG2(self.history, self.var_threshold, self.detect_shadows)
        mask = self._mog.apply(mat)
        return self.ok(mask, "前景检测完成")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class VideoWriter(OpenCVNodeDataBase):
    """Write frames to a video file."""
    __group__ = "视频处理模块"
    output_path = Property("output.avi", name="输出路径", group=PropertyGroupNames.RUN_PARAMETERS)
    fps = Property(30.0, name="帧率", group=PropertyGroupNames.RUN_PARAMETERS)
    fourcc_code = Property("XVID", name="编码格式", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "视频写入"
        self._writer: cv2.VideoWriter | None = None
        self._frame_count = 0

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        if self._writer is None:
            h, w = mat.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*self.fourcc_code)
            self._writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (w, h))
        self._writer.write(mat)
        self._frame_count += 1
        return self.ok(mat, f"写入第 {self._frame_count} 帧")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def dispose(self):
        if self._writer:
            self._writer.release()
            self._writer = None
        super().dispose()
