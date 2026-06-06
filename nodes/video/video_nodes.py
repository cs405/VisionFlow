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
        mat = self.get_input_mat(from_node.mat if from_node else None)
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
    output_path = Property("output.avi", name="输出路径", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="视频输出文件路径 (.avi/.mp4)")
    fps = Property(30.0, name="帧率", group=PropertyGroupNames.RUN_PARAMETERS,
                    description="输出视频帧率")
    fourcc_code = Property("XVID", name="编码格式", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="FourCC 编码代码 (XVID/MJPG/H264/MP4V)")
    frame_count = Property(0, name="已写入帧数", group=PropertyGroupNames.RESULT_PARAMETERS,
                           readonly=True)

    # Valid fourcc codes for common encoders
    VALID_FOURCC = {"XVID", "MJPG", "H264", "MP4V", "DIVX", "I420", "IYUV", "WMV1", "WMV2"}

    def __init__(self):
        super().__init__()
        self.name = "视频写入"
        self._writer: cv2.VideoWriter | None = None

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        if self._writer is None:
            if len(self.fourcc_code) != 4:
                return self.error(None, f"无效的 FourCC 编码: '{self.fourcc_code}' (需要4个字符)")
            if self.fourcc_code not in self.VALID_FOURCC:
                self._log_warning(f"未知编码格式: {self.fourcc_code}，尝试使用")
            h, w = mat.shape[:2]
            try:
                fourcc = cv2.VideoWriter_fourcc(*self.fourcc_code)
                self._writer = cv2.VideoWriter(self.output_path, fourcc, self.fps, (w, h))
                if not self._writer.isOpened():
                    return self.error(None, f"无法打开视频写入: {self.output_path}")
            except Exception as e:
                return self.error(None, f"初始化视频编码器失败: {e}")
        self._writer.write(mat)
        self.frame_count += 1
        return self.ok(mat, f"写入第 {self.frame_count} 帧")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def dispose(self):
        if self._writer:
            self._writer.release()
            self._writer = None
        super().dispose()
