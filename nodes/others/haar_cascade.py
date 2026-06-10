import cv2
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult


class HaarCascade(OpenCVNodeDataBase):
    __group__ = "其他模块"
    cascade_path = Property("", name="级联文件路径", group=PropertyGroupNames.RUN_PARAMETERS)
    scale_factor = Property(1.1, name="缩放因子", group=PropertyGroupNames.RUN_PARAMETERS)
    min_neighbors = Property(3, name="最小邻居数", group=PropertyGroupNames.RUN_PARAMETERS)
    detect_count = Property(0, name="检测数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "Haar级联分类器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        if self.cascade_path:
            cascade = cv2.CascadeClassifier(self.cascade_path)
        else:
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        objects = cascade.detectMultiScale(gray, self.scale_factor, self.min_neighbors)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        for (x, y, w, h) in objects:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        self.detect_count = len(objects)
        return self.ok(out, f"检测到 {len(objects)} 个目标")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
