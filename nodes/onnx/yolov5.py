"""YOLOv5 目标检测 — 对应 WPF Yolov5OnnxNodeData"""

import os
from nodes.onnx.onnx_bbox import OnnxBboxNode


def _models_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "models")


class Yolov5OnnxNode(OnnxBboxNode):
    """YOLOv5 ONNX 目标检测。模型: yolov5s.onnx, 标签: lable.txt。输出: [1, 25200, 85]"""

    def __init__(self):
        super().__init__()
        self.name = "YOLOv5检测"
        d = _models_dir()
        self.model_path = os.path.join(d, "yolov5s.onnx")
        self.label_path = os.path.join(d, "lable.txt")
        self.input_width = 640
        self.input_height = 640
        self.output_row_index = 1
        self.output_column_index = 2
        self.output_confidence_index = 4
        self.conf_threshold = 0.25
        self.nms_threshold = 0.45
        self.blob_scale_factor = 255.0
