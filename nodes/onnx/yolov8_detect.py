"""YOLOv8 目标检测节点

基于 onnxruntime 推理，参考 detect.py 的解码流程。
输出格式: [1, 4+num_classes, 8400]，每列为 [cx, cy, w, h, class_0, ..., class_n]。

配合模板匹配使用：上游 xfeat_match 匹配成功后输出裁剪区域，
本节点对该区域执行检测，通过置信度/面积/长宽比过滤后设置 matched 状态。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import cv2
import numpy as np
import onnxruntime as ort

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.onnx.onnx_base import OnnxNodeDataBase
from nodes.onnx.detection_utils import read_labels

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class Yolov8OnnxNode(OnnxNodeDataBase):
    """YOLOv8 目标检测（onnxruntime 推理）。

    接收上游（通常为模板匹配）输出的裁剪图像，执行 YOLOv8 推理，
    按置信度、面积、长宽比过滤后，设置 matched 状态供下游条件节点判断。
    """

    __group__ = "Onnx通用模型"

    # ── 模型参数 ──
    label_path = Property("", name="标签路径", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="标签文件路径或逗号分隔的标签文本，可选")

    # ── 过滤参数 ──
    conf_threshold = Property(0.25, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                              min_val=0.0, max_val=1.0, step=0.05)
    nms_threshold = Property(0.45, name="NMS重叠阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                             min_val=0.0, max_val=1.0, step=0.05)
    min_area = Property(0, name="最小面积(px²)", group=PropertyGroupNames.RUN_PARAMETERS,
                        min_val=0, max_val=10000000, step=100)
    max_area = Property(10000000, name="最大面积(px²)", group=PropertyGroupNames.RUN_PARAMETERS,
                        min_val=0, max_val=10000000, step=100)
    min_aspect_ratio = Property(0.0, name="最小长宽比", group=PropertyGroupNames.RUN_PARAMETERS,
                                min_val=0.0, max_val=100.0, step=0.1)
    max_aspect_ratio = Property(100.0, name="最大长宽比", group=PropertyGroupNames.RUN_PARAMETERS,
                                min_val=0.0, max_val=100.0, step=0.1)

    # ── 结果属性 ──
    matching_count_result = Property(0, name="检测数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                                     readonly=True)
    matching_max_class = Property("", name="最高置信度标签", group=PropertyGroupNames.RESULT_PARAMETERS,
                                  readonly=True)
    max_confidence_result = Property(0.0, name="最高置信度", group=PropertyGroupNames.RESULT_PARAMETERS,
                                     readonly=True)
    confidence = Property(0.0, name="置信度", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)
    matched = Property(False, name="是否匹配", group=PropertyGroupNames.RESULT_PARAMETERS,
                       readonly=True)
    match_x = Property(0, name="匹配X", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_y = Property(0, name="匹配Y", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_w = Property(0, name="匹配宽度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    match_h = Property(0, name="匹配高度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "YOLOv8检测"
        self.input_width = 640
        self.input_height = 640
        self._session: ort.InferenceSession | None = None
        self._session_model_path: str = ""
        self._lb_scale: float = 1.0
        self._lb_dw: float = 0.0
        self._lb_dh: float = 0.0

    # ── 推理引擎 ──

    def _get_session(self) -> ort.InferenceSession | None:
        if self._session is not None and self._session_model_path == self.model_path:
            return self._session
        if not self.model_path or not os.path.isfile(self.model_path):
            return None
        try:
            self._session = ort.InferenceSession(
                self.model_path,
                providers=['CPUExecutionProvider'],
            )
            self._session_model_path = self.model_path
            self._last_forward_error = ""
            return self._session
        except Exception as e:
            self._last_forward_error = str(e)
            return None

    def _forward(self, mat: np.ndarray) -> list[np.ndarray]:
        session = self._get_session()
        if session is None:
            return []
        blob = self._to_input_blob(mat)
        input_name = session.get_inputs()[0].name
        try:
            outputs = session.run(None, {input_name: blob})
            return list(outputs)
        except Exception as e:
            self._last_forward_error = str(e)
            return []

    def _to_input_blob(self, mat: np.ndarray) -> np.ndarray:
        """Letterbox 预处理：等比缩放 + 居中填充 → NCHW blob [0,1]。
        参考 detect.py 的预处理流程。"""
        h, w = mat.shape[:2]
        scale = min(self.input_width / w, self.input_height / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(mat, (new_w, new_h))
        dw = (self.input_width - new_w) / 2.0
        dh = (self.input_height - new_h) / 2.0
        canvas = np.full((self.input_height, self.input_width, 3), 114, dtype=np.uint8)
        canvas[int(dh):int(dh) + new_h, int(dw):int(dw) + new_w] = resized
        self._lb_scale = scale
        self._lb_dw = dw
        self._lb_dh = dh
        return cv2.dnn.blobFromImage(canvas, 1.0 / 255.0,
                                     (self.input_width, self.input_height),
                                     (0, 0, 0), swapRB=True, crop=False)

    def _validate_model(self) -> FlowableResult | None:
        if not self.model_path or not os.path.isfile(self.model_path):
            return self.error(None, f"模型文件不存在: {self.model_path or '(未设置)'}")
        return None

    def dispose(self):
        super().dispose()
        self._session = None
        self._session_model_path = ""

    # ── 主流程 ──

    def reset_execution_state(self):
        """每轮执行前重置，清除上次结果的 matched 及坐标残留。"""
        super().reset_execution_state()
        self._reset_match_state()

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            self._reset_match_state()
            return self.error(None, "无输入图像")

        err = self._validate_model()
        if err:
            self._reset_match_state()
            return self.error(mat, f"[模型未加载] {err.message}")

        forwards = self._forward(mat)
        if not forwards:
            self._reset_match_state()
            if self._last_forward_error:
                return self.error(mat, f"[推理失败] {self._last_forward_error[:120]}")
            return self.error(mat, "[推理失败] 模型无输出")

        class_names = read_labels(self.label_path)

        # 解码 — 参考 detect.py: squeeze + transpose
        all_boxes, all_scores, all_class_ids = self._decode_predictions(forwards[0])

        # NMS — cv2.dnn.NMSBoxes，轴对齐快速
        keep = self._do_nms(all_boxes, all_scores)
        final_boxes = [all_boxes[i] for i in keep]
        final_scores = [all_scores[i] for i in keep]
        final_class_ids = [all_class_ids[i] for i in keep]

        # 绘制
        out = mat.copy()
        self._draw_boxes(out, final_boxes, final_scores, final_class_ids, class_names)

        # 状态
        self.matching_count_result = len(keep)
        self.matched = len(keep) > 0
        self.confidence = max(final_scores) if final_scores else 0.0
        if final_scores:
            best_idx = int(np.argmax(final_scores))
            self.matching_max_class = class_names[final_class_ids[best_idx]] if final_class_ids[best_idx] < len(class_names) else str(final_class_ids[best_idx])
            self.max_confidence_result = final_scores[best_idx]
        else:
            self.matching_max_class = ""
            self.max_confidence_result = 0.0

        # 抠图：参考 xfeat_match，匹配成功时裁剪最高置信度区域返回
        if self.matched:
            best_idx = int(np.argmax(final_scores))
            bx, by, bw, bh = final_boxes[best_idx]
            scale = self._lb_scale
            dw = self._lb_dw
            dh = self._lb_dh
            bx = int((bx - dw) / scale)
            by = int((by - dh) / scale)
            bw = int(bw / scale)
            bh = int(bh / scale)
            h, w = mat.shape[:2]
            bx = max(0, bx); by = max(0, by)
            bw = min(bw, w - bx); bh = min(bh, h - by)
            self.match_x, self.match_y = bx, by
            self.match_w, self.match_h = bw, bh
            if bw > 0 and bh > 0:
                matched_region = mat[by:by + bh, bx:bx + bw].copy()
                return self.ok(matched_region,
                    f"检测 {len(keep)} 个目标 | 抠出区域 ({bx},{by},{bw}x{bh})")
            return self.error(None, "裁剪区域无效")
        else:
            self.match_x = self.match_y = self.match_w = self.match_h = 0

        return self.ok(out, f"未检测到符合条件的目标")

    # ── 解码：参考 detect.py ──

    def _decode_predictions(self, output: np.ndarray) -> tuple[list, list, list]:
        """解码 YOLOv8 ONNX 输出 [1, 4+nc, 8400] → boxes/scores/class_ids。
        参考 detect.py: np.squeeze(output).T → [8400, 4+nc]，逐行处理。
        cx/cy/w/h 为 letterbox 画布像素值 (0~640)。
        """
        data = np.squeeze(output).T  # [8400, 4+nc]

        boxes: list[list] = []
        scores: list[float] = []
        class_ids: list[int] = []

        for row in data:
            class_scores = row[4:]
            class_id = int(np.argmax(class_scores))
            score = float(class_scores[class_id])
            if score < self.conf_threshold:
                continue

            cx, cy, w, h = float(row[0]), float(row[1]), float(row[2]), float(row[3])
            x = cx - w / 2.0
            y = cy - h / 2.0

            # 面积 / 长宽比过滤（画布空间）
            area = w * h
            if area < self.min_area or area > self.max_area:
                continue
            ar = w / max(h, 1.0)
            if ar < self.min_aspect_ratio or ar > self.max_aspect_ratio:
                continue

            boxes.append([x, y, w, h])
            scores.append(score)
            class_ids.append(class_id)

        return boxes, scores, class_ids

    # ── NMS ──

    def _do_nms(self, boxes: list[list], scores: list[float]) -> list[int]:
        """轴对齐 NMS，使用 cv2.dnn.NMSBoxes。"""
        if not boxes:
            return []
        indices = cv2.dnn.NMSBoxes(boxes, scores, self.conf_threshold, self.nms_threshold)
        if len(indices) == 0:
            return []
        return [int(i) for i in indices.flatten()]

    # ── 绘制 ──

    def _draw_boxes(self, image: np.ndarray, boxes: list[list],
                    scores: list[float], class_ids: list[int],
                    class_names: list[str]):
        """在图像上绘制检测框，坐标从画布空间反算回原图。"""
        scale = self._lb_scale
        dw = self._lb_dw
        dh = self._lb_dh
        for box, score, class_id in zip(boxes, scores, class_ids):
            x, y, w, h = box
            # letterbox 反算 — 参考 detect.py
            x = (x - dw) / scale
            y = (y - dh) / scale
            w = w / scale
            h = h / scale
            x1, y1 = int(x), int(y)
            x2, y2 = int(x + w), int(y + h)
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            name = ""
            if class_names and class_id < len(class_names):
                name = class_names[class_id]
            label = f"{name} {score*100:.1f}%" if name else f"{score*100:.1f}%"
            (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(image, (x1, y1 - th - bl - 4), (x1 + tw, y1), (0, 255, 0), -1)
            cv2.putText(image, label, (x1, y1 - bl - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # ── 辅助 ──

    def _reset_match_state(self):
        self.matching_count_result = 0
        self.matching_max_class = ""
        self.max_confidence_result = 0.0
        self.confidence = 0.0
        self.matched = "false"
