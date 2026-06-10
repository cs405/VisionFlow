"""ONNX 语义分割 — 对应 WPF SemSegOnnxNodeDataBase + SemSegOnnxNodeData"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.onnx.onnx_base import OnnxNodeDataBase

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class OnnxSegNode(OnnxNodeDataBase):
    """语义分割 — 对应 WPF SemSegOnnxNodeData。输出形状: [batch_size, num_classes, height, width]"""

    alpha = Property(0.5, name="混合透明度", group=PropertyGroupNames.DISPLAY_PARAMETERS, min_val=0.0, max_val=1.0, step=0.05)
    output_mask_index = Property("", name="显示掩码索引", group=PropertyGroupNames.DISPLAY_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "ONNX语义分割"
        self.input_width = 192
        self.input_height = 192
        self.output_row_index = 1
        self.output_column_index = 2

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        err = self._validate_model()
        if err:
            return self.ok(mat, f"[模型未加载] {err.message}")
        img_h, img_w = mat.shape[:2]
        forwards = self._forward(mat)
        if not forwards:
            if self._last_forward_error:
                return self.ok(mat, f"[推理失败] {self._last_forward_error[:120]}")
        mask_indices: list[int] = []
        if self.output_mask_index.strip():
            mask_indices = [int(x.strip()) for x in self.output_mask_index.split(",") if x.strip()]
        result = mat.copy()
        for forward in forwards:
            num_classes = forward.shape[1]
            for c in range(num_classes):
                if mask_indices and c not in mask_indices:
                    continue
                mask = forward[0, c]
                mask = (mask * 255).astype(np.uint8)
                mask = cv2.resize(mask, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
                _, mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)
                color_overlay = np.zeros_like(result)
                color_overlay[mask > 0] = (0, 255, 0)
                result = cv2.addWeighted(result, 1 - self.alpha, color_overlay, self.alpha, 0)
        return self.ok(result, "语义分割完成")
