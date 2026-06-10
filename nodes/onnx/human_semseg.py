"""人类语义分割 — 对应 WPF HumanSemSegOnnxNodeData"""

import os
from nodes.onnx.onnx_seg import OnnxSegNode


def _models_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "models")


class HumanSemSegOnnxNode(OnnxSegNode):
    """人类语义分割。模型: human_segmentation_pphumanseg_2023mar.onnx。输出: [1, 2, 192, 192]"""

    def __init__(self):
        super().__init__()
        self.name = "人像分割"
        d = _models_dir()
        self.model_path = os.path.join(d, "human_segmentation_pphumanseg_2023mar.onnx")
        self.input_width = 192
        self.input_height = 192
        self.output_row_index = 1
        self.output_column_index = 2
        self.output_mask_index = "1"
        self.alpha = 0.5
        self.blob_scale_factor = 255.0
