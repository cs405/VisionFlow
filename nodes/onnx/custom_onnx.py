"""Custom ONNX nodes - preconfigured for specific models.
"""

import cv2
import numpy as np
from nodes.onnx.onnx_nodes import (
    OnnxObjectDetection, OnnxClassification, OnnxInference, OnnxSemanticSegmentation,
)
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Yolov5OnnxNode(OnnxObjectDetection):
    """YOLOv5 ONNX object detection."""
    __group__ = "Onnx通用模型"

    def __init__(self):
        super().__init__()
        self.name = "YOLOv5检测"
        self.input_size = 640
        self.conf_threshold = 0.5
        self.nms_threshold = 0.4


class Yolov5FaceOnnxNode(OnnxObjectDetection):
    """YOLOv5 Face ONNX detection."""
    __group__ = "Onnx通用模型"

    def __init__(self):
        super().__init__()
        self.name = "YOLOv5人脸检测"
        self.input_size = 640
        self.conf_threshold = 0.5


class AgeInferOnnxNode(OnnxInference):
    """Age inference using ONNX model (e.g., efficientnet)."""
    __group__ = "Onnx通用模型"

    def __init__(self):
        super().__init__()
        self.name = "年龄推测"
        self.input_size = 224
        self.model_path = "assets/models/age_efficientnet_b2.onnx"


class GenderClsOnnxNode(OnnxClassification):
    """Gender classification using ONNX model."""
    __group__ = "Onnx通用模型"

    def __init__(self):
        super().__init__()
        self.name = "性别分类"
        self.input_size = 224
        self.model_path = "assets/models/gender_efficientnet_b2.onnx"
        self.label_path = "assets/models/lable.txt"


class HumanSemSegOnnxNode(OnnxSemanticSegmentation):
    """Human semantic segmentation using ONNX model."""
    __group__ = "Onnx通用模型"

    def __init__(self):
        super().__init__()
        self.name = "人像分割"
        self.input_size = 224
        self.model_path = "assets/models/human_segmentation_pphumanseg_2023mar.onnx"
        self.alpha = 0.5
