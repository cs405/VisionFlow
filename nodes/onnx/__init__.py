"""ONNX 模块 — 分层架构:

  onnx_base.py     → 基类层: OnnxNodeDataBase, DefectBox, 枚举, 工具函数
  onnx_nodes.py    → 通用节点层: OnnxClsNode, OnnxBboxNode, OnnxSegNode, OnnxInferNode
  custom_onnx.py   → App层: Yolov5OnnxNode, Yolov5FaceOnnxNode, AgeInferOnnxNode,
                             GenderClsOnnxNode, HumanSemSegOnnxNode
"""

from nodes.onnx.onnx_base import (
    IOpenCVDnnNode,
    DefectBox,
    BoxCoordinateMode,
    BoxGeometryType,
    OnnxNodeDataBase,
    apply_nms,
    draw_detect_boxes,
    draw_detect_labels,
    read_labels,
)
from nodes.onnx.onnx_nodes import (
    OnnxClsNode,
    OnnxBboxNode,
    OnnxSegNode,
    OnnxInferNode,
    # 向后兼容别名
    OnnxClassification,
    OnnxObjectDetection,
    OnnxSemanticSegmentation,
    OnnxInference,
)
from nodes.onnx.custom_onnx import (
    Yolov5OnnxNode,
    Yolov5FaceOnnxNode,
    AgeInferOnnxNode,
    GenderClsOnnxNode,
    HumanSemSegOnnxNode,
)
