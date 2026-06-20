"""ONNX 目标检测"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.onnx.onnx_base import OnnxNodeDataBase
from nodes.onnx.defect_box import DefectBox, BoxCoordinateMode, BoxGeometryType
from nodes.onnx.detection_utils import apply_nms, draw_detect_boxes, draw_detect_labels, read_labels

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


class OnnxBboxNode(OnnxNodeDataBase):
    """目标检测, 输出形状: [batch_size, num_boxes, (class_probs + bbox_coords)]"""

    label_path = Property("", name="标签路径", group=PropertyGroupNames.RUN_PARAMETERS)
    conf_threshold = Property(0.25, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS, min_val=0.0, max_val=1.0, step=0.05)
    nms_threshold = Property(0.45, name="NMS重叠阈值", group=PropertyGroupNames.RUN_PARAMETERS, min_val=0.0, max_val=1.0, step=0.05)
    box_coordinate_mode = Property("absolute", name="坐标系模式", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=["absolute", "normalized"])
    box_geometry_type = Property("center_size", name="几何表示类型", group=PropertyGroupNames.RUN_PARAMETERS, editor="choices", choices=["center_size", "point_size", "corner_points"])
    use_score = Property(True, name="绘制置信度", group=PropertyGroupNames.DISPLAY_PARAMETERS)
    matching_count_result = Property(0, name="目标数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    matching_max_class = Property("", name="最高置信度标签", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    max_confidence_result = Property(0.0, name="最高置信度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ONNX目标检测"
        self.input_width = 640
        self.input_height = 640
        self.output_row_index = 1
        self.output_column_index = 2

    def _validate_model(self) -> FlowableResult | None:
        err = super()._validate_model()
        if err:
            return err
        return None

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        err = self._validate_model()
        if err:
            return self.ok(mat, f"[模型未加载] {err.message}")
        img_h, img_w = mat.shape[:2]
        factor = max(img_w, img_h) / float(self.input_width)
        try:
            coord_mode = BoxCoordinateMode(self.box_coordinate_mode)
        except ValueError:
            coord_mode = BoxCoordinateMode.ABSOLUTE_PIXELS
        try:
            geom_type = BoxGeometryType(self.box_geometry_type)
        except ValueError:
            geom_type = BoxGeometryType.CENTER_WITH_SIZE
        forwards = self._forward(mat)
        if not forwards:
            if self._last_forward_error:
                return self.ok(mat, f"[推理失败] {self._last_forward_error[:120]}")
        class_names = read_labels(self.label_path)
        all_boxes: list[DefectBox] = []
        for forward in forwards:
            all_boxes.extend(self._decode_predictions(forward, coord_mode, geom_type, factor))
        nms_boxes = apply_nms(all_boxes, self.conf_threshold, self.nms_threshold)
        result = mat.copy()
        draw_detect_boxes(result, nms_boxes)
        tuples = draw_detect_labels(result, nms_boxes, class_names, self.use_score)
        self.matching_count_result = len(tuples)
        if tuples:
            best = max(tuples, key=lambda t: t[2])
            self.matching_max_class = best[1]
            self.max_confidence_result = best[2]
        else:
            self.matching_max_class = ""
            self.max_confidence_result = 0.0
        return self.ok(result, f"检测到 {len(tuples)} 个目标")

    def _decode_predictions(self, forward, coord_mode, geom_type, factor) -> list[DefectBox]:
        """从单个 forward 输出张量解码出 DefectBox 列表"""
        rs = forward.shape[self.output_row_index]
        cs = forward.shape[self.output_column_index]
        output_data = forward.reshape(rs, cs)
        boxes: list[DefectBox] = []
        for i in range(output_data.shape[0]):
            conf_idx = self.output_confidence_index
            if 0 <= conf_idx < output_data.shape[1]:
                conf = float(output_data[i, conf_idx])
            else:
                conf = float(output_data[i, -1])
            if conf < self.conf_threshold:
                continue
            class_id = 0
            if output_data.shape[1] > 5:
                class_scores = output_data[i, 5:]
                if class_scores.size > 0:
                    class_id = int(np.argmax(class_scores))
                    if float(np.max(class_scores)) < self.conf_threshold:
                        continue
            x, y, bw, bh = [float(output_data[i, j]) for j in range(4)]
            rect = self._convert_box(x, y, bw, bh, coord_mode, geom_type, factor)
            boxes.append(DefectBox(class_id=class_id, box=rect, score=conf))
        return boxes

    def _convert_box(self, x, y, bw, bh, coord_mode, geom_type, factor):
        v1, v2, v3, v4 = x * factor, y * factor, bw * factor, bh * factor
        if coord_mode == BoxCoordinateMode.NORMALIZED_RATIO:
            v1 *= self.input_width; v2 *= self.input_height; v3 *= self.input_width; v4 *= self.input_height
        if geom_type == BoxGeometryType.CORNER_POINTS:
            return (v1, v2, v3 - v1, v4 - v2)
        if geom_type == BoxGeometryType.POINT_WITH_SIZE:
            return (v1, v2, v3, v4)
        if geom_type == BoxGeometryType.CENTER_WITH_SIZE:
            return (v1 - 0.5 * v3, v2 - 0.5 * v4, v3, v4)
        return (v1 - v3, v2 - v3, 2 * v3, 2 * v3)
