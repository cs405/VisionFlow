"""年龄推测 — 对应 WPF AgeInferOnnxNodeData"""

import os
from core.node_base import Property, PropertyGroupNames
from nodes.onnx.onnx_infer import OnnxInferNode


def _models_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "models")


class AgeInferOnnxNode(OnnxInferNode):
    """年龄推测。模型: age_efficientnet_b2.onnx, ImageNet 归一化参数。"""

    age_result = Property(0.0, name="推测年龄结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "年龄推测"
        d = _models_dir()
        self.model_path = os.path.join(d, "age_efficientnet_b2.onnx")
        self.input_width = 224
        self.input_height = 224
        self.output_row_index = 0
        self.output_column_index = 1
        self.output_confidence_index = -1
        self.blob_scale_factor = 255.0
        self.blob_mean = "0.485,0.456,0.406"
        self.blob_std = "0.229,0.224,0.225"

    def invoke_core(self, src, from_node, diagram):
        from core.data_packet import FlowableResult
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        err = self._validate_model()
        if err:
            return self.ok(mat, f"[模型未加载] {err.message}")
        forwards = self._forward(mat)
        if not forwards:
            if self._last_forward_error:
                return self.ok(mat, f"[推理失败] {self._last_forward_error[:120]}")
        values: list[float] = []
        for forward in forwards:
            for i in range(forward.shape[1] if forward.ndim > 1 else forward.shape[0]):
                val = float(forward[0, i]) if forward.ndim > 1 else float(forward[i])
                values.append(val)
        if values:
            self.age_result = values[0]
            self.value_result = "，".join(f"{v:.1f}" for v in values)
            return self.ok(mat, f"推测年龄: {self.age_result:.0f} 岁")
        self.age_result = 0.0
        return self.ok(mat, "无推测结果")
