"""ONNX 通用节点层 — 对应 WPF H.NodeDatas.Onnx.OpenCV.NodeDatas

四类通用节点 (所有逻辑在基类, 这里只是具象化的入口):
  - OnnxClsNode:       图像分类 (对应 ClsOnnxNodeData → ClsOnnxNodeDataBase)
  - OnnxBboxNode:      目标检测 (对应 ObjDetectOnnxNodeData → ObjDetectOnnxNodeDataBase)
  - OnnxSegNode:       语义分割 (对应 SemSegOnnxNodeData → SemSegOnnxNodeDataBase)
  - OnnxInferNode:     数值推理 (对应 InferOnnxNodeData → InferOnnxNodeDataBase)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.onnx.onnx_base import (
    OnnxNodeDataBase,
    DefectBox,
    BoxCoordinateMode,
    BoxGeometryType,
    apply_nms,
    draw_detect_boxes,
    draw_detect_labels,
    read_labels,
)

if TYPE_CHECKING:
    from core.workflow import WorkflowEngine


# =============================================================================
# OnnxClsNode — 图像分类 (对应 WPF ClsOnnxNodeDataBase + ClsOnnxNodeData)
# =============================================================================

class OnnxClsNode(OnnxNodeDataBase):
    """使用 ONNX 模型的图像分类节点 — 对应 WPF ClsOnnxNodeData。

    输出形状: [batch_size, num_classes]
    """

    # ── 标签路径 (对应 WPF LabelPath) ──
    label_path = Property("", name="标签路径/数值", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="标签文件路径或逗号分隔的类名文本，如 'cat,dog,bird'")

    # ── 结果参数 (只读, ResultParameters) ──
    class_name_result = Property("", name="分类结果", group=PropertyGroupNames.RESULT_PARAMETERS,
                                 readonly=True)
    confidence_result = Property(0.0, name="置信度", group=PropertyGroupNames.RESULT_PARAMETERS,
                                 readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ONNX分类"
        self.input_width = 224
        self.input_height = 224
        self.output_row_index = 0
        self.output_column_index = 1

    def _validate_model(self) -> FlowableResult | None:
        err = super()._validate_model()
        if err:
            return err
        return None  # 标签路径可选

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        err = self._validate_model()
        if err:
            return err

        forwards = self._forward(mat)
        class_names = read_labels(self.label_path)

        # 遍历所有输出层 (对应 Classification 扩展方法)
        all_results: list[tuple[str, float]] = []
        for forward in forwards:
            # 解析输出张量 (对应 forward.ToOutput)
            rs = forward.shape[self.output_row_index]
            cs = forward.shape[self.output_column_index]
            output_data = forward.reshape(rs, cs) if forward.ndim > 2 else forward

            for i in range(output_data.shape[1] if output_data.ndim > 1 else output_data.shape[0]):
                val = float(output_data[0, i]) if output_data.ndim > 1 else float(output_data[i])
                name = class_names[i] if i < len(class_names) else ""
                all_results.append((name, val))

        if all_results:
            all_results.sort(key=lambda x: x[1], reverse=True)
            best_name, best_conf = all_results[0]
            self.class_name_result = best_name
            self.confidence_result = best_conf
            summary = "，".join(f"{n} {c:.2f}" for n, c in all_results[:5])
            return self.ok(mat, f"分类: {summary}")

        self.class_name_result = "未知"
        self.confidence_result = 0.0
        return self.ok(mat, "无分类结果")


# =============================================================================
# OnnxBboxNode — 目标检测 (对应 WPF ObjDetectOnnxNodeDataBase + ObjDetectOnnxNodeData)
# =============================================================================

class OnnxBboxNode(OnnxNodeDataBase):
    """使用 ONNX 模型的目标检测节点 — 对应 WPF ObjDetectOnnxNodeData。

    输出形状: [batch_size, num_boxes, (class_probs + bbox_coords)]
    """

    # ── 标签路径 ──
    label_path = Property("", name="标签路径", group=PropertyGroupNames.RUN_PARAMETERS,
                          description="标签文件路径或逗号分隔的类名")

    # ── 检测参数 (对应 WPF Threshold, NmsThreshold) ──
    conf_threshold = Property(0.25, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                              description="低于此值的框会被过滤", min_val=0.0, max_val=1.0, step=0.05)
    nms_threshold = Property(0.45, name="NMS重叠阈值", group=PropertyGroupNames.RUN_PARAMETERS,
                             description="IoU 大于此值的框会被抑制", min_val=0.0, max_val=1.0, step=0.05)

    # ── 坐标系与几何类型 (对应 WPF BoxCoordinateMode, BoxGeometryType) ──
    box_coordinate_mode = Property("absolute", name="坐标系模式",
                                   group=PropertyGroupNames.RUN_PARAMETERS,
                                   editor="choices", choices=["absolute", "normalized"])
    box_geometry_type = Property("center_size", name="几何表示类型",
                                 group=PropertyGroupNames.RUN_PARAMETERS,
                                 editor="choices",
                                 choices=["center_size", "point_size", "corner_points"])

    # ── 显示选项 ──
    use_score = Property(True, name="绘制置信度", group=PropertyGroupNames.DISPLAY_PARAMETERS,
                         description="在输出图像上绘制置信度数值")

    # ── 结果参数 (只读, ResultParameters — 可被条件分支引用) ──
    matching_count_result = Property(0, name="目标数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                                     readonly=True)
    matching_max_class = Property("", name="最高置信度标签", group=PropertyGroupNames.RESULT_PARAMETERS,
                                  readonly=True)
    max_confidence_result = Property(0.0, name="最高置信度", group=PropertyGroupNames.RESULT_PARAMETERS,
                                     readonly=True)

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
            return err

        img_h, img_w = mat.shape[:2]
        max_len = max(img_w, img_h)
        factor = max_len / float(self.input_width)

        # 解析坐标系和几何类型
        coord_mode = BoxCoordinateMode(self.box_coordinate_mode)
        geom_type = BoxGeometryType(self.box_geometry_type)

        forwards = self._forward(mat)
        class_names = read_labels(self.label_path)

        all_boxes: list[DefectBox] = []

        for forward in forwards:
            # 解析输出 (对应 forward.ToOutput)
            rs = forward.shape[self.output_row_index]
            cs = forward.shape[self.output_column_index]
            output_data = forward.reshape(rs, cs)

            # 解析每个检测 (对应 output.ToDefectBoxs)
            for i in range(output_data.shape[0]):
                # 获取置信度
                conf_idx = self.output_confidence_index
                if conf_idx >= 0 and conf_idx < output_data.shape[1]:
                    conf = float(output_data[i, conf_idx])
                else:
                    conf = float(output_data[i, -1])

                if conf < self.conf_threshold:
                    continue

                # 解析框坐标
                x = float(output_data[i, 0])
                y = float(output_data[i, 1])
                bw = float(output_data[i, 2])
                bh = float(output_data[i, 3])

                # 确定类别
                class_id = 0
                if output_data.shape[1] > 5:
                    class_scores = output_data[i, 5:]
                    if class_scores.size > 0:
                        class_id = int(np.argmax(class_scores))
                        class_conf = float(np.max(class_scores))
                        if class_conf < self.conf_threshold:
                            continue
                        conf = class_conf

                # 坐标转换
                rect = self._convert_box(x, y, bw, bh, coord_mode, geom_type, factor)

                all_boxes.append(DefectBox(class_id=class_id, box=rect, score=conf))

        # NMS (对应 ToNMSBoxes)
        nms_boxes = apply_nms(all_boxes, self.conf_threshold, self.nms_threshold)

        # 绘制
        result = mat.copy()
        draw_detect_boxes(result, nms_boxes)
        tuples = draw_detect_labels(result, nms_boxes, class_names, self.use_score)

        # 设置结果参数 (可被条件分支引用)
        self.matching_count_result = len(tuples)
        if tuples:
            best = max(tuples, key=lambda t: t[2])
            self.matching_max_class = best[1]
            self.max_confidence_result = best[2]
        else:
            self.matching_max_class = ""
            self.max_confidence_result = 0.0

        return self.ok(result, f"检测到 {len(tuples)} 个目标")

    def _convert_box(self, x: float, y: float, bw: float, bh: float,
                     coord_mode: BoxCoordinateMode, geom_type: BoxGeometryType,
                     factor: float) -> tuple[float, float, float, float]:
        """将模型输出的框坐标转换为 (x, y, w, h) 格式 — 对应 WPF DefectBoxes 中的 convertToRect。"""
        v1, v2, v3, v4 = x * factor, y * factor, bw * factor, bh * factor

        if coord_mode == BoxCoordinateMode.NORMALIZED_RATIO:
            v1 *= self.input_width
            v2 *= self.input_height
            v3 *= self.input_width
            v4 *= self.input_height

        if geom_type == BoxGeometryType.CORNER_POINTS:
            return (v1, v2, v3 - v1, v4 - v2)
        if geom_type == BoxGeometryType.POINT_WITH_SIZE:
            return (v1, v2, v3, v4)
        if geom_type == BoxGeometryType.CENTER_WITH_SIZE:
            width, height = v3, v4
            left = v1 - 0.5 * width
            top = v2 - 0.5 * height
            return (left, top, width, height)
        # PolarWithAngle: 使用极坐标的半径作为包围盒
        return (v1 - v3, v2 - v3, 2 * v3, 2 * v3)


# =============================================================================
# OnnxSegNode — 语义分割 (对应 WPF SemSegOnnxNodeDataBase + SemSegOnnxNodeData)
# =============================================================================

class OnnxSegNode(OnnxNodeDataBase):
    """使用 ONNX 模型的语义分割节点 — 对应 WPF SemSegOnnxNodeData。

    输出形状: [batch_size, num_classes, height, width]
    """

    # ── 显示选项 ──
    alpha = Property(0.5, name="混合透明度", group=PropertyGroupNames.DISPLAY_PARAMETERS,
                     description="原图与掩码的混合比例", min_val=0.0, max_val=1.0, step=0.05)
    output_mask_index = Property("", name="显示掩码索引", group=PropertyGroupNames.DISPLAY_PARAMETERS,
                                 description="逗号分隔的掩码索引，空=全部显示，如 '1' 或 '0,2'")

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
            return err

        img_h, img_w = mat.shape[:2]
        forwards = self._forward(mat)

        # 解析要显示的掩码索引
        mask_indices: list[int] = []
        if self.output_mask_index.strip():
            mask_indices = [int(x.strip()) for x in self.output_mask_index.split(",") if x.strip()]

        result = mat.copy()

        for forward in forwards:
            num_classes = forward.shape[1]
            # 获取所有类别掩码 (对应 GetMasks)
            for c in range(num_classes):
                if mask_indices and c not in mask_indices:
                    continue

                # 提取单通道掩码并还原到原图尺寸 (对应 ToSrcMask)
                mask = forward[0, c]
                mask = (mask * 255).astype(np.uint8)
                mask = cv2.resize(mask, (img_w, img_h), interpolation=cv2.INTER_LINEAR)
                _, mask = cv2.threshold(mask, 128, 255, cv2.THRESH_BINARY)

                # 混合显示
                color_overlay = np.zeros_like(result)
                color_overlay[mask > 0] = (0, 255, 0)
                result = cv2.addWeighted(result, 1 - self.alpha, color_overlay, self.alpha, 0)

        return self.ok(result, "语义分割完成")


# =============================================================================
# OnnxInferNode — 数值推理 (对应 WPF InferOnnxNodeDataBase + InferOnnxNodeData)
# =============================================================================

class OnnxInferNode(OnnxNodeDataBase):
    """使用 ONNX 模型的数值推理节点 — 对应 WPF InferOnnxNodeData。

    输出形状: [batch_size, num_values]
    适用于年龄推测、回归等输出为数值的任务。
    """

    # ── 结果参数 ──
    value_result = Property("", name="推测结果", group=PropertyGroupNames.RESULT_PARAMETERS,
                            readonly=True, description="可被条件分支等引用")

    def __init__(self):
        super().__init__()
        self.name = "ONNX推理"
        self.input_width = 224
        self.input_height = 224
        self.output_row_index = 0
        self.output_column_index = 1

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")

        err = self._validate_model()
        if err:
            return err

        forwards = self._forward(mat)

        all_values: list[float] = []
        for forward in forwards:
            rs = forward.shape[self.output_row_index]
            cs = forward.shape[self.output_column_index]
            output_data = forward.reshape(rs, cs) if forward.ndim > 2 else forward

            for i in range(output_data.shape[1] if output_data.ndim > 1 else output_data.shape[0]):
                val = float(output_data[0, i]) if output_data.ndim > 1 else float(output_data[i])
                all_values.append(val)

        self.value_result = "，".join(f"{v:.4f}" for v in all_values)
        return self.ok(mat, f"推测结果: {self.value_result}" if all_values else "无结果")


# =============================================================================
# 向后兼容 — 保留旧类名作为子类，使注册表中的 __name__ 正确
# =============================================================================

class OnnxClassification(OnnxClsNode):
    """[兼容] 旧名称，等同于 OnnxClsNode"""
    pass

class OnnxObjectDetection(OnnxBboxNode):
    """[兼容] 旧名称，等同于 OnnxBboxNode"""
    pass

class OnnxSemanticSegmentation(OnnxSegNode):
    """[兼容] 旧名称，等同于 OnnxSegNode"""
    pass

class OnnxInference(OnnxInferNode):
    """[兼容] 旧名称，等同于 OnnxInferNode"""
    pass
