"""性别分类 — 对应 WPF GenderClsOnnxNodeData"""

import os
from nodes.onnx.onnx_cls import OnnxClsNode


def _models_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "models")


class GenderClsOnnxNode(OnnxClsNode):
    """性别分类。模型: gender_efficientnet_b2.onnx, 标签: Male Female"""

    def __init__(self):
        super().__init__()
        self.name = "性别分类"
        d = _models_dir()
        self.model_path = os.path.join(d, "gender_efficientnet_b2.onnx")
        self.label_path = "Male Female"
        self.input_width = 224
        self.input_height = 224
        self.output_row_index = 0
        self.output_column_index = 1
        self.blob_scale_factor = 255.0
