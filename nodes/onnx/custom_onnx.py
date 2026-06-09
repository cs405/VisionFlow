"""自定义ONNX节点 - 为特定模型预配置。"""

import cv2
import numpy as np
from nodes.onnx.onnx_nodes import (
    OnnxObjectDetection,      # ONNX目标检测基类
    OnnxClassification,       # ONNX分类基类
    OnnxInference,            # ONNX推理基类
    OnnxSemanticSegmentation, # ONNX语义分割基类
)
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Yolov5OnnxNode(OnnxObjectDetection):
    """YOLOv5 ONNX目标检测节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"

    def __init__(self):
        """初始化YOLOv5检测节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "YOLOv5检测"
        # 输入图像尺寸（640x640）
        self.input_size = 640
        # 置信度阈值（0.5）
        self.conf_threshold = 0.5
        # NMS阈值（0.4）
        self.nms_threshold = 0.4


class Yolov5FaceOnnxNode(OnnxObjectDetection):
    """YOLOv5人脸ONNX检测节点"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"

    def __init__(self):
        """初始化YOLOv5人脸检测节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "YOLOv5人脸检测"
        # 输入图像尺寸（640x640）
        self.input_size = 640
        # 置信度阈值（0.5）
        self.conf_threshold = 0.5


class AgeInferOnnxNode(OnnxInference):
    """使用ONNX模型进行年龄推测（例如efficientnet）"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"

    def __init__(self):
        """初始化年龄推测节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "年龄推测"
        # 输入图像尺寸（224x224）
        self.input_size = 224
        # 模型文件路径
        self.model_path = "assets/models/age_efficientnet_b2.onnx"


class GenderClsOnnxNode(OnnxClassification):
    """使用ONNX模型进行性别分类"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"

    def __init__(self):
        """初始化性别分类节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "性别分类"
        # 输入图像尺寸（224x224）
        self.input_size = 224
        # 模型文件路径
        self.model_path = "assets/models/gender_efficientnet_b2.onnx"
        # 标签文件路径
        self.label_path = "assets/models/lable.txt"


class HumanSemSegOnnxNode(OnnxSemanticSegmentation):
    """使用ONNX模型进行人体语义分割"""
    # 节点所属分组（用于UI分类）
    __group__ = "Onnx通用模型"

    def __init__(self):
        """初始化人像分割节点"""
        # 调用父类构造函数
        super().__init__()
        # 设置节点显示名称
        self.name = "人像分割"
        # 输入图像尺寸（224x224）
        self.input_size = 224
        # 模型文件路径
        self.model_path = "assets/models/human_segmentation_pphumanseg_2023mar.onnx"
        # 透明度（用于叠加显示）
        self.alpha = 0.5