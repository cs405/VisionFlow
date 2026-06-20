import cv2
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult

# HaarType 枚举映射到 OpenCV haarcascades 文件
_HAAR_TYPES = {
    "正脸": "haarcascade_frontalface_default.xml",
    "侧脸": "haarcascade_profileface.xml",
    "眼睛": "haarcascade_eye.xml",
    "左眼": "haarcascade_lefteye_2splits.xml",
    "右眼": "haarcascade_righteye_2splits.xml",
    "嘴部": "haarcascade_smile.xml",
    "全身": "haarcascade_fullbody.xml",
    "上半身": "haarcascade_upperbody.xml",
    "下半身": "haarcascade_lowerbody.xml",
    "猫脸": "haarcascade_frontalcatface.xml",
    "车牌(俄)": "haarcascade_russian_plate_number.xml",
    "车牌": "haarcascade_licence_plate_rus_16stages.xml",
}

class HaarCascade(OpenCVNodeDataBase):
    __group__ = "其他模块"
    haar_type = Property("正脸", name="检测类型", group=PropertyGroupNames.RUN_PARAMETERS,
                         editor="choices", choices=list(_HAAR_TYPES.keys()))
    cascade_path = Property("", name="级联文件路径", group=PropertyGroupNames.RUN_PARAMETERS,
                            description="留空则使用内置预设")
    scale_factor = Property(1.1, name="缩放因子", group=PropertyGroupNames.RUN_PARAMETERS, step=0.05, decimals=2)
    min_neighbors = Property(3, name="最小邻居数", group=PropertyGroupNames.RUN_PARAMETERS)
    detect_count = Property(0, name="检测数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "人脸检测(HAAR)"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        if self.cascade_path:
            cascade = cv2.CascadeClassifier(self.cascade_path)
        else:
            xml_name = _HAAR_TYPES.get(self.haar_type, "haarcascade_frontalface_default.xml")
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + xml_name)
        objects = cascade.detectMultiScale(gray, self.scale_factor, self.min_neighbors)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        for (x, y, w, h) in objects:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        self.detect_count = len(objects)
        return self.ok(out, f"检测到 {len(objects)} 个目标 ({self.haar_type})")
