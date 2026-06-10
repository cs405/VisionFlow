"""ONNX 检测辅助函数 — 对应 WPF OnnxExtension 中的 Draw/NMS/Label 方法"""

import os

import cv2
import numpy as np

from nodes.onnx.defect_box import DefectBox


def draw_detect_boxes(image: np.ndarray, boxes: list[DefectBox],
                      color: tuple = (0, 255, 0), thickness: int = 2) -> np.ndarray:
    """在图像上绘制检测框 — 对应 WPF DrawDetectBoxes。"""
    for db in boxes:
        x, y, w, h = int(db.box[0]), int(db.box[1]), int(db.box[2]), int(db.box[3])
        cv2.rectangle(image, (x, y), (x + w, y + h), color, thickness)
    return image


def draw_detect_labels(image: np.ndarray, boxes: list[DefectBox],
                       class_names: list[str] = None, use_score: bool = True,
                       color: tuple = (0, 255, 0),
                       label_color: tuple = (255, 255, 255)) -> list[tuple[DefectBox, str, float]]:
    """绘制检测框标签并返回标签元组 — 对应 WPF DrawDetectBoxLabels。"""
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
        (tw, th), bl = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(image, (x, y - th - bl - 4), (x + tw, y), label_color, -1)
        cv2.putText(image, label, (x, y - bl - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        results.append((db, name, db.score))
    return results


def apply_nms(boxes: list[DefectBox], conf_threshold: float = 0.25,
              nms_threshold: float = 0.45) -> list[DefectBox]:
    """对检测框应用 NMS — 对应 WPF ToNMSBoxes。"""
    if not boxes:
        return []
    filtered = [b for b in boxes if b.score >= conf_threshold]
    if not filtered:
        return []
    rects = [[b.box[0], b.box[1], b.box[2], b.box[3]] for b in filtered]
    scores = [b.score for b in filtered]
    indices = cv2.dnn.NMSBoxes(rects, scores, conf_threshold, nms_threshold)
    if len(indices) == 0:
        return []
    return [filtered[i] for i in indices.flatten()]


def read_labels(label_path: str) -> list[str]:
    """读取标签文件或解析内联文本 — 对应 WPF GetClassNames。"""
    if not label_path:
        return []
    if os.path.isfile(label_path):
        with open(label_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    import re
    return [s.strip() for s in re.split(r'[,，\s]+', label_path) if s.strip()]
