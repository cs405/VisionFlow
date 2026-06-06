"""ONNX/DNN model nodes: classification, object detection, segmentation, inference."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class _OnnxBase(OpenCVNodeDataBase):
    """Base for ONNX model nodes using cv2.dnn."""
    model_path = Property("", name="模型路径", group=PropertyGroupNames.RUN_PARAMETERS)
    input_size = Property(224, name="输入尺寸", group=PropertyGroupNames.RUN_PARAMETERS)
    scale = Property(1.0, name="缩放因子", group=PropertyGroupNames.RUN_PARAMETERS)
    mean = Property("0,0,0", name="均值", group=PropertyGroupNames.RUN_PARAMETERS)

    _net: cv2.dnn.Net | None = None

    def _get_net(self) -> cv2.dnn.Net | None:
        if self._net is None and self.model_path:
            self._net = cv2.dnn.readNetFromONNX(self.model_path)
        return self._net

    def _blob_from_image(self, mat: np.ndarray, size: int = None) -> np.ndarray:
        sz = size or self.input_size
        means = [float(x) for x in self.mean.split(",")]
        if len(means) == 1: means = means * 3
        return cv2.dnn.blobFromImage(mat, self.scale, (sz, sz), tuple(means), swapRB=True, crop=False)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class OnnxClassification(_OnnxBase):
    """Image classification using ONNX model."""
    __group__ = "Onnx通用模型"
    label_path = Property("", name="标签文件", group=PropertyGroupNames.RUN_PARAMETERS)
    class_result = Property("", name="分类结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    conf_result = Property(0.0, name="置信度", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ONNX分类"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        net = self._get_net()
        if net is None: return self.error(mat, "模型未加载")
        blob = self._blob_from_image(mat)
        net.setInput(blob)
        output = net.forward()
        class_id = np.argmax(output)
        self.conf_result = float(output[0][class_id])
        self.class_result = str(class_id)
        if self.label_path:
            try:
                with open(self.label_path) as f:
                    labels = [l.strip() for l in f.readlines()]
                self.class_result = labels[class_id] if class_id < len(labels) else str(class_id)
            except Exception: pass
        return self.ok(mat, f"分类: {self.class_result} ({self.conf_result:.3f})")


class OnnxObjectDetection(_OnnxBase):
    """Object detection using ONNX model (e.g. YOLOv5)."""
    __group__ = "Onnx通用模型"
    conf_threshold = Property(0.5, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    nms_threshold = Property(0.4, name="NMS阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    detect_count = Property(0, name="检测数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ONNX目标检测"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        net = self._get_net()
        if net is None: return self.error(mat, "模型未加载")
        blob = self._blob_from_image(mat, 640)
        net.setInput(blob)
        output = net.forward()
        h, w = mat.shape[:2]
        out = mat.copy()
        count = 0
        for det in output[0]:
            conf = float(det[4])
            if conf > self.conf_threshold:
                cx, cy, bw, bh = det[0:4]
                cx, cy = cx * w / 640, cy * h / 640
                bw, bh = bw * w / 640, bh * h / 640
                x1, y1 = int(cx - bw/2), int(cy - bh/2)
                x2, y2 = int(cx + bw/2), int(cy + bh/2)
                cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(out, f"{conf:.2f}", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                count += 1
        self.detect_count = count
        return self.ok(out, f"检测到 {count} 个目标")


class OnnxSemanticSegmentation(_OnnxBase):
    """Semantic segmentation using ONNX model."""
    __group__ = "Onnx通用模型"
    alpha = Property(0.5, name="混合透明度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "ONNX语义分割"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        net = self._get_net()
        if net is None: return self.error(mat, "模型未加载")
        blob = self._blob_from_image(mat)
        net.setInput(blob)
        output = net.forward()
        mask = np.argmax(output[0], axis=0).astype(np.uint8)
        h, w = mat.shape[:2]
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
        colors = np.random.randint(0, 255, (int(mask.max()) + 2, 3), dtype=np.uint8)
        color_mask = colors[mask]
        result = cv2.addWeighted(mat, 1 - self.alpha, color_mask, self.alpha, 0)
        return self.ok(result, "语义分割完成")


class OnnxInference(_OnnxBase):
    """Generic numeric inference using ONNX model."""
    __group__ = "Onnx通用模型"
    value_result = Property("", name="推理结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "ONNX推理"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        net = self._get_net()
        if net is None: return self.error(mat, "模型未加载")
        blob = self._blob_from_image(mat)
        net.setInput(blob)
        output = net.forward()
        values = output.flatten()
        self.value_result = ", ".join([f"{v:.4f}" for v in values[:20]])
        return self.ok(mat, self.value_result)
