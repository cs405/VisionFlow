"""ONNX 模块基类层

提供:
  - DefectBox 数据结构 (检测框)
  - BoxCoordinateMode / BoxGeometryType 枚举
  - OnnxNodeDataBase (模型加载 + 预处理 + 输出解析)
  - IOpenCVDnnNode 标记接口 (分组发现)
  - 绘制辅助函数
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import (
    OpenCVNodeDataBase, Property, PropertyGroupNames, LogicModuleNode
)
from core.data_packet import FlowableResult

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# IOpenCVDnnNode — 分组发现接口
# =============================================================================

class IOpenCVDnnNode:
    """标记接口：实现此接口的节点自动归入 'Onnx通用模型' 分组。

    节点实现此接口即可被 OnnxDataGroup 发现。
    """
    pass


# =============================================================================
# DefectBox — 检测结果数据结构
# =============================================================================

@dataclass
class DefectBox:
    """单个检测框结果"""
    class_id: int
    box: tuple[float, float, float, float]  # (x, y, w, h)
    score: float


# =============================================================================
# BoxCoordinateMode / BoxGeometryType
# =============================================================================

class BoxCoordinateMode(Enum):
    """检测框坐标基准"""
    ABSOLUTE_PIXELS = "absolute"    # 绝对像素坐标
    NORMALIZED_RATIO = "normalized"  # 归一化比例 (0~1)


class BoxGeometryType(Enum):
    """检测框几何表示 """
    CENTER_WITH_SIZE = "center_size"    # 中心点 + 宽高 (YOLO)
    POINT_WITH_SIZE = "point_size"      # 左上角 + 宽高
    CORNER_POINTS = "corner_points"     # 对角坐标 (x1,y1,x2,y2)
    POLAR_WITH_ANGLE = "polar_angle"    # 极坐标


# =============================================================================
# 绘制辅助函数
# =============================================================================

def draw_detect_boxes(image: np.ndarray, boxes: list[DefectBox],
                      color: tuple = (0, 255, 0), thickness: int = 2) -> np.ndarray:
    """在图像上绘制检测框"""
    for db in boxes:
        x, y, w, h = int(db.box[0]), int(db.box[1]), int(db.box[2]), int(db.box[3])
        cv2.rectangle(image, (x, y), (x + w, y + h), color, thickness)
    return image


def draw_detect_labels(image: np.ndarray, boxes: list[DefectBox],
                       class_names: list[str] = None, use_score: bool = True,
                       color: tuple = (0, 255, 0),
                       label_color: tuple = (255, 255, 255)) -> list[tuple[DefectBox, str, float]]:
    """绘制检测框标签并返回标签元组

    返回: [(DefectBox, class_name, score), ...]
    """
    results: list[tuple[DefectBox, str, float]] = []
    class_names = class_names or []
    for db in boxes:
        name = ""
        if class_names:
            if db.class_id < len(class_names):
                name = class_names[db.class_id]
            elif len(class_names) == 1:
                name = class_names[0]
        label = f"{name} {db.score*100:.1f}%" if use_score and name else name
        if not label:
            continue
        x, y, w, h = int(db.box[0]), int(db.box[1]), int(db.box[2]), int(db.box[3])
        # 标签背景
        (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(image, (x, y - th - bl - 4), (x + tw, y), label_color, -1)
        cv2.putText(image, label, (x, y - bl - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        results.append((db, name, db.score))
    return results


# =============================================================================
# NMS — 非极大值抑制
# =============================================================================

def apply_nms(boxes: list[DefectBox], conf_threshold: float = 0.25,
              nms_threshold: float = 0.45) -> list[DefectBox]:
    """对检测框应用 NMS"""
    if not boxes:
        return []

    # 过滤低置信度
    filtered = [b for b in boxes if b.score >= conf_threshold]
    if not filtered:
        return []

    # 准备 NMS 输入
    rects = [[b.box[0], b.box[1], b.box[2], b.box[3]] for b in filtered]  # 直接使用 (x,y,w,h)
    scores = [b.score for b in filtered]

    indices = cv2.dnn.NMSBoxes(rects, scores, conf_threshold, nms_threshold)
    if len(indices) == 0:
        return []

    result = [filtered[i] for i in indices.flatten()]
    return result


# =============================================================================
# 标签读取
# =============================================================================

def read_labels(label_path: str) -> list[str]:
    """读取标签文件或解析内联逗号分隔文本

    支持:
      - 文件路径 (每行一个标签)
      - 内联文本 ("Female Male" 或 "cat,dog,bird")
    """
    if not label_path:
        return []
    if os.path.isfile(label_path):
        with open(label_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    # 内联文本
    import re
    return [s.strip() for s in re.split(r'[,，\s]+', label_path) if s.strip()]


# =============================================================================
# OnnxNodeDataBase — ONNX 节点基类
# =============================================================================

class OnnxNodeDataBase(OpenCVNodeDataBase, IOpenCVDnnNode):
    """ONNX 模型节点基类

    提供:
      - 模型路径、输入尺寸、归一化参数
      - 输出张量解析参数
      - 模型验证 (BeforeInvokeAsync → _validate_model)
      - Blob 创建 (_to_input_blob)
    """

    # ── 模型路径 ──
    model_path = Property("", name="模型路径", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="ONNX 模型文件路径", editor="file")

    # ── 输入尺寸 ──
    input_width = Property(640, name="输入宽度", group=PropertyGroupNames.RUN_PARAMETERS,
                           description="模型输入宽度")
    input_height = Property(640, name="输入高度", group=PropertyGroupNames.RUN_PARAMETERS,
                            description="模型输入高度")

    # ── 归一化参数 ──
    blob_scale_factor = Property(255.0, name="归一化比例", group=PropertyGroupNames.RUN_PARAMETERS,
                                 description="Blob 缩放因子，通常为 255.0 表示 1/255")
    blob_mean = Property("0,0,0", name="归一化均值", group=PropertyGroupNames.RUN_PARAMETERS,
                         description="各通道减去均值，逗号分隔如 0.485,0.456,0.406")
    blob_std = Property("", name="归一化标准差", group=PropertyGroupNames.RUN_PARAMETERS,
                        description="各通道除以标准差，逗号分隔如 0.229,0.224,0.225；空则不除")

    # ── 输出解析索引 ──
    output_row_index = Property(1, name="结果行位置", group=PropertyGroupNames.RUN_PARAMETERS,
                                description="输出张量中行数据的位置，YOLO 通常为 1")
    output_column_index = Property(2, name="结果列位置", group=PropertyGroupNames.RUN_PARAMETERS,
                                   description="输出张量中列数据的位置，YOLO 通常为 2")
    output_confidence_index = Property(-1, name="置信度位置", group=PropertyGroupNames.RUN_PARAMETERS,
                                       description="置信度列索引，YOLO 通常为 4，其他模型 -1")

    # ── 节点分组 ──
    __group__ = "Onnx通用模型"

    def __init__(self):
        super().__init__()
        self._net: cv2.dnn.Net | None = None
        self._last_forward_error: str = ""
        self.name = self.__class__.__name__

    # ── 模型验证 ──

    def _validate_model(self) -> FlowableResult | None:
        """验证模型文件存在。不存在时返回错误结果。

        子类可重写以增加额外验证（如标签文件）。
        """
        if not self.model_path or not os.path.isfile(self.model_path):
            return self.error(None, f"模型文件不存在: {self.model_path or '(未设置)'}")
        return None  # 验证通过

    # ── 网络加载 ──

    def _get_net(self) -> cv2.dnn.Net | None:
        """获取或加载 ONNX 网络模型。"""
        if self._net is None and self.model_path:
            self._net = cv2.dnn.readNetFromONNX(self.model_path)
        return self._net

    # ── Blob 创建  ──

    def _to_input_blob(self, mat: np.ndarray) -> np.ndarray:
        """将图像转换为模型输入 Blob

        处理流程:
          1. 将图像放在正方形背景上 (letterbox)
          2. BlobFromImage (swapRB=True, crop=False)
          3. 可选: 除以标准差
        """
        h, w = mat.shape[:2]
        max_len = max(h, w)
        input_w = self.input_width
        input_h = self.input_height

        # Letterbox: 放在正方形背景上
        max_image = np.zeros((max_len, max_len, 3), dtype=np.uint8)
        max_image[0:h, 0:w] = mat if mat.shape[2:] == (3,) else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)

        # 解析均值
        means = [float(x.strip()) for x in self.blob_mean.split(",") if x.strip()]
        if len(means) == 1:
            means = means * 3
        elif len(means) == 0:
            means = [0.0, 0.0, 0.0]

        blob = cv2.dnn.blobFromImage(
            max_image,
            1.0 / self.blob_scale_factor,
            (input_w, input_h),
            tuple(means),
            swapRB=True,
            crop=False,
        )

        # 可选: 标准差归一化
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

    # ── 前向推理 ──

    def _forward(self, mat: np.ndarray) -> list[np.ndarray]:
        """执行模型前向推理，返回所有输出层的结果。

        获取所有 unconnected output layers。
        模型未加载或推理失败时返回空列表。
        """
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
        # fallback: 单输出模型或 named forward 失败时尝试无参 forward
        try:
            return [net.forward()]
        except Exception as e:
            self._last_forward_error = str(e)
            return []

    # ── 生命周期 ──

    def is_valid(self, mat: np.ndarray) -> bool:
        return mat is not None and mat.size > 0

    def dispose(self):
        super().dispose()
        self._net = None
