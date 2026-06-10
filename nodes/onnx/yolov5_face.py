"""YOLOv5 人脸检测"""

import os
from nodes.onnx.onnx_bbox import OnnxBboxNode


def _models_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "models")


class Yolov5FaceOnnxNode(OnnxBboxNode):
    """YOLOv5 人脸检测。模型: yolov5s-face.onnx"""

    def __init__(self):
        super().__init__()
        self.name = "YOLOv5人脸检测"
        d = _models_dir()
        self.model_path = os.path.join(d, "yolov5s-face.onnx")
        self.label_path = "Face"
        self.input_width = 640
        self.input_height = 640
        self.output_row_index = 1
        self.output_column_index = 2
        self.output_confidence_index = 4
        self.conf_threshold = 0.5
        self.nms_threshold = 0.4
        self.blob_scale_factor = 255.0
