"""ONNX 模型节点基类"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult
from nodes.onnx.dnn_interface import IOpenCVDnnNode

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class OnnxNodeDataBase(OpenCVNodeDataBase, IOpenCVDnnNode):
    """ONNX 模型节点基类

    提供: 模型路径、输入尺寸、归一化参数、输出张量解析、模型验证、Blob 创建。
    """

    model_path = Property("", name="模型路径", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="ONNX 模型文件路径", editor="file")
    input_width = Property(640, name="输入宽度", group=PropertyGroupNames.RUN_PARAMETERS)
    input_height = Property(640, name="输入高度", group=PropertyGroupNames.RUN_PARAMETERS)
    blob_scale_factor = Property(255.0, name="归一化比例", group=PropertyGroupNames.RUN_PARAMETERS)
    blob_mean = Property("0,0,0", name="归一化均值", group=PropertyGroupNames.RUN_PARAMETERS)
    blob_std = Property("", name="归一化标准差", group=PropertyGroupNames.RUN_PARAMETERS)
    output_row_index = Property(1, name="结果行位置", group=PropertyGroupNames.RUN_PARAMETERS)
    output_column_index = Property(2, name="结果列位置", group=PropertyGroupNames.RUN_PARAMETERS)
    output_confidence_index = Property(-1, name="置信度位置", group=PropertyGroupNames.RUN_PARAMETERS)

    __group__ = "Onnx通用模型"

    def __init__(self):
        super().__init__()
        self._net: cv2.dnn.Net | None = None
        self._last_forward_error: str = ""
        self.name = self.__class__.__name__

    def _validate_model(self) -> FlowableResult | None:
        if not self.model_path or not os.path.isfile(self.model_path):
            return self.error(None, f"模型文件不存在: {self.model_path or '(未设置)'}")
        return None

    def _get_net(self) -> cv2.dnn.Net | None:
        if self._net is None and self.model_path:
            self._net = cv2.dnn.readNetFromONNX(self.model_path)
        return self._net

    def _to_input_blob(self, mat: np.ndarray) -> np.ndarray:
        h, w = mat.shape[:2]
        max_len = max(h, w)
        max_image = np.zeros((max_len, max_len, 3), dtype=np.uint8)
        max_image[0:h, 0:w] = mat if mat.shape[2:] == (3,) else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        means = [float(x.strip()) for x in self.blob_mean.split(",") if x.strip()]
        if len(means) == 1:
            means = means * 3
        elif len(means) == 0:
            means = [0.0, 0.0, 0.0]
        elif len(means) == 2:
            means = means + [0.0]  # 补齐到 3 通道
        elif len(means) > 3:
            means = means[:3]
        blob = cv2.dnn.blobFromImage(max_image, 1.0 / self.blob_scale_factor,
                                      (self.input_width, self.input_height),
                                      tuple(means), swapRB=True, crop=False)
        if self.blob_std.strip():
            stds = [float(x.strip()) for x in self.blob_std.split(",") if x.strip()]
            if len(stds) == 1:
                stds = stds * 3
            if len(stds) >= 3:
                std_mat = np.ones(blob.shape, dtype=np.float32)
                for c in range(min(3, len(stds))):
                    if stds[c] != 0:
                        std_mat[0, c, :, :] = stds[c]
                blob = blob / std_mat
        return blob

    def _forward(self, mat: np.ndarray) -> list[np.ndarray]:
        net = self._get_net()
        if net is None:
            return []
        blob = self._to_input_blob(mat)
        net.setInput(blob)
        try:
            output_names = net.getUnconnectedOutLayersNames()
            return [net.forward(name) for name in output_names]
        except Exception:
            pass
        try:
            return [net.forward()]
        except Exception as e:
            self._last_forward_error = str(e)
            return []

    def is_valid(self, mat: np.ndarray) -> bool:
        return mat is not None and mat.size > 0

    def dispose(self):
        super().dispose()
        self._net = None
