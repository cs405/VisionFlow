"""App 层 ONNX 节点 — 为特定模型预配置的具象化节点。

对应 WPF H.App.VisionMaster.OpenCV/NodeDatas/:
  - Yolov5OnnxNode     → Yolov5OnnxNodeData     (ObjDetectOnnxNodeDataBase)
  - Yolov5FaceOnnxNode → Yolov5FaceOnnxNodeData  (ObjDetectOnnxNodeDataBase)
  - AgeInferOnnxNode   → AgeInferOnnxNodeData    (InferOnnxNodeDataBase)
  - GenderClsOnnxNode  → GenderClsOnnxNodeData   (ClsOnnxNodeDataBase)
  - HumanSemSegOnnxNode → HumanSemSegOnnxNodeData (SemSegOnnxNodeDataBase)

每个节点只重写 __init__/load_default，预置模型路径和参数。
所有模型文件位于 assets/models/ 下。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.onnx.onnx_nodes import OnnxBboxNode, OnnxClsNode, OnnxInferNode, OnnxSegNode

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


def _models_dir() -> str:
    """获取 assets/models/ 绝对路径。"""
    base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(base, "assets", "models")


def _model_path(filename: str) -> str:
    return os.path.join(_models_dir(), filename)


# =============================================================================
# Yolov5OnnxNode — YOLOv5 目标检测 (对应 WPF Yolov5OnnxNodeData)
# =============================================================================

class Yolov5OnnxNode(OnnxBboxNode):
    """YOLOv5 ONNX 目标检测 — 对应 WPF Yolov5OnnxNodeData : ObjDetectOnnxNodeDataBase。

    模型: yolov5s.onnx, 标签: lable.txt
    输出: [1, 25200, 85]  → num_boxes, (class_probs + bbox_coords)
    """

    def __init__(self):
        super().__init__()
        self.name = "YOLOv5检测"
        self.model_path = _model_path("yolov5s.onnx")
        self.label_path = _model_path("lable.txt")
        self.input_width = 640
        self.input_height = 640
        self.output_row_index = 1
        self.output_column_index = 2
        self.output_confidence_index = 4  # YOLO: 第5列(0-indexed=4)是置信度
        self.conf_threshold = 0.25
        self.nms_threshold = 0.45
        self.blob_scale_factor = 255.0
        self.box_coordinate_mode = "center_size"
        self.box_geometry_type = "center_size"


# =============================================================================
# Yolov5FaceOnnxNode — YOLOv5 人脸检测 (对应 WPF Yolov5FaceOnnxNodeData)
# =============================================================================

class Yolov5FaceOnnxNode(OnnxBboxNode):
    """YOLOv5 人脸检测 — 对应 WPF Yolov5FaceOnnxNodeData : ObjDetectOnnxNodeDataBase。

    模型: yolov5s-face.onnx, 标签: 内联 "Face"
    """

    def __init__(self):
        super().__init__()
        self.name = "YOLOv5人脸检测"
        self.model_path = _model_path("yolov5s-face.onnx")
        self.label_path = "Face"  # 内联标签
        self.input_width = 640
        self.input_height = 640
        self.output_row_index = 1
        self.output_column_index = 2
        self.output_confidence_index = 4
        self.conf_threshold = 0.5
        self.nms_threshold = 0.4
        self.blob_scale_factor = 255.0


# =============================================================================
# AgeInferOnnxNode — 年龄推测 (对应 WPF AgeInferOnnxNodeData)
# =============================================================================

class AgeInferOnnxNode(OnnxInferNode):
    """年龄推测 — 对应 WPF AgeInferOnnxNodeData : InferOnnxNodeDataBase。

    模型: age_efficientnet_b2.onnx
    使用 EfficientNet-B2，带 ImageNet 标准归一化参数。
    """

    # 推测年龄结果 (只读, ResultParameters — 可被条件分支引用)
    age_result = Property(0.0, name="推测年龄结果", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "年龄推测"
        self.model_path = _model_path("age_efficientnet_b2.onnx")
        self.input_width = 224
        self.input_height = 224
        self.output_row_index = 0
        self.output_column_index = 1
        self.output_confidence_index = -1
        self.blob_scale_factor = 255.0
        # ImageNet 标准归一化参数
        self.blob_mean = "0.485,0.456,0.406"
        self.blob_std = "0.229,0.224,0.225"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        err = self._validate_model()
        if err:
            return err

        forwards = self._forward(mat)
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


# =============================================================================
# GenderClsOnnxNode — 性别分类 (对应 WPF GenderClsOnnxNodeData)
# =============================================================================

class GenderClsOnnxNode(OnnxClsNode):
    """性别分类 — 对应 WPF GenderClsOnnxNodeData : ClsOnnxNodeDataBase。

    模型: gender_efficientnet_b2.onnx, 标签: Female, Male
    """

    def __init__(self):
        super().__init__()
        self.name = "性别分类"
        self.model_path = _model_path("gender_efficientnet_b2.onnx")
        self.label_path = "Male Female"  # 内联标签
        self.input_width = 224
        self.input_height = 224
        self.output_row_index = 0
        self.output_column_index = 1
        self.blob_scale_factor = 255.0


# =============================================================================
# HumanSemSegOnnxNode — 人类语义分割 (对应 WPF HumanSemSegOnnxNodeData)
# =============================================================================

class HumanSemSegOnnxNode(OnnxSegNode):
    """人类语义分割 — 对应 WPF HumanSemSegOnnxNodeData : SemSegOnnxNodeDataBase。

    模型: human_segmentation_pphumanseg_2023mar.onnx
    输出: [1, 2, 192, 192]  → 2类掩码 (背景, 人像)
    """

    def __init__(self):
        super().__init__()
        self.name = "人像分割"
        self.model_path = _model_path("human_segmentation_pphumanseg_2023mar.onnx")
        self.input_width = 192
        self.input_height = 192
        self.output_row_index = 1
        self.output_column_index = 2
        self.output_mask_index = "1"  # 只显示人像掩码 (索引1)
        self.alpha = 0.5
        self.blob_scale_factor = 255.0
