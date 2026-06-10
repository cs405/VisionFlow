import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class Yolov3(OpenCVNodeDataBase):
    __group__ = "其他模块"
    config_path = Property("", name="配置文件", group=PropertyGroupNames.RUN_PARAMETERS)
    weights_path = Property("", name="权重文件", group=PropertyGroupNames.RUN_PARAMETERS)
    confidence = Property(0.5, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    nms_threshold = Property(0.4, name="NMS阈值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "YOLOv3检测器"
        self._net = None

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        if self._net is None and self.config_path and self.weights_path:
            self._net = cv2.dnn.readNetFromDarknet(self.config_path, self.weights_path)
        if self._net is None:
            return self.error(mat, "未设置YOLOv3配置文件/权重")
        h, w = mat.shape[:2]
        blob = cv2.dnn.blobFromImage(mat, 1/255.0, (416, 416), swapRB=True, crop=False)
        self._net.setInput(blob)
        outputs = self._net.forward(self._net.getUnconnectedOutLayersNames())
        out = mat.copy()
        for output in outputs:
            for det in output:
                scores = det[5:]
                class_id = np.argmax(scores)
                if scores[class_id] > self.confidence:
                    cx, cy, bw, bh = det[0:4] * np.array([w, h, w, h])
                    x, y = int(cx - bw / 2), int(cy - bh / 2)
                    cv2.rectangle(out, (x, y), (int(x + bw), int(y + bh)), (0, 255, 0), 2)
        return self.ok(out, "YOLOv3检测完成")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
