"""ONNX 数值推理"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.onnx.onnx_base import OnnxNodeDataBase

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class OnnxInferNode(OnnxNodeDataBase):
    """数值推理, 输出形状: [batch_size, num_values]"""

    value_result = Property("", name="推测结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ONNX推理"
        self.input_width = 224
        self.input_height = 224
        self.output_row_index = 0
        self.output_column_index = 1

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
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
        all_values: list[float] = []
        for forward in forwards:
            rs = forward.shape[self.output_row_index]
            cs = forward.shape[self.output_column_index]
            output_data = forward.reshape(rs, cs) if forward.ndim > 2 else forward
            for i in range(output_data.shape[1] if output_data.ndim > 1 else output_data.shape[0]):
                val = float(output_data[0, i]) if output_data.ndim > 1 else float(output_data[i])
                all_values.append(val)
        self.value_result = "，".join(f"{v:.4f}" for v in all_values)
        return self.ok(mat, f"推测结果: {self.value_result}" if all_values else "无结果")
