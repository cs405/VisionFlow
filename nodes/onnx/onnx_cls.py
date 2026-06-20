"""ONNX 图像分类"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.onnx.onnx_base import OnnxNodeDataBase
from nodes.onnx.detection_utils import read_labels

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class OnnxClsNode(OnnxNodeDataBase):
    """图像分类, 输出形状: [batch_size, num_classes]"""

    label_path = Property("", name="标签路径/数值", group=PropertyGroupNames.RUN_PARAMETERS)
    class_name_result = Property("", name="分类结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    confidence_result = Property(0.0, name="置信度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ONNX分类"
        self.input_width = 224
        self.input_height = 224
        self.output_row_index = 0
        self.output_column_index = 1

    def _validate_model(self) -> FlowableResult | None:
        err = super()._validate_model()
        if err:
            return err
        return None

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        err = self._validate_model()
        if err:
            return self.ok(mat, f"[模型未加载] {err.message}")
        forwards = self._forward(mat)
        if not forwards:
            if self._last_forward_error:
                return self.ok(mat, f"[推理失败] {self._last_forward_error[:120]}")
        class_names = read_labels(self.label_path)
        all_results: list[tuple[str, float]] = []
        for forward in forwards:
            rs = forward.shape[self.output_row_index]
            cs = forward.shape[self.output_column_index]
            output_data = forward.reshape(rs, cs) if forward.ndim > 2 else forward
            for i in range(output_data.shape[1] if output_data.ndim > 1 else output_data.shape[0]):
                val = float(output_data[0, i]) if output_data.ndim > 1 else float(output_data[i])
                name = class_names[i] if i < len(class_names) else ""
                all_results.append((name, val))
        if all_results:
            all_results.sort(key=lambda x: x[1], reverse=True)
            self.class_name_result = all_results[0][0]
            self.confidence_result = all_results[0][1]
            return self.ok(mat, f"分类: {'，'.join(f'{n} {c:.2f}' for n,c in all_results[:5])}")
        self.class_name_result = "未知"
        self.confidence_result = 0.0
        return self.ok(mat, "无分类结果")
