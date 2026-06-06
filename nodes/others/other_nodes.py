"""Other CV nodes: HaarCascade, LbpCascade, Histogram, HOG, SeamlessClone, Stitching,
Subdiv2D, SVM, WarpAffine, WarpPerspective, DnnSuperres, Yolov3."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


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
        if mat is None: return self.error(None, "无输入图像")
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


class LbpCascade(HaarCascade):
    __group__ = "其他模块"
    def __init__(self):
        super().__init__()
        self.name = "LBP级联分类器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "lbpcascade_frontalface_improved.xml")
        objects = cascade.detectMultiScale(gray, self.scale_factor, self.min_neighbors)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        for (x, y, w, h) in objects:
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        self.detect_count = len(objects)
        return self.ok(out, f"LBP检测到 {len(objects)} 个目标")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Hist(OpenCVNodeDataBase):
    __group__ = "其他模块"
    hist_size = Property(256, name="直方图大小", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "直方图"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        hist = cv2.calcHist([gray], [0], None, [self.hist_size], [0, 256])
        hist_img = np.zeros((256, 256, 3), dtype=np.uint8)
        cv2.normalize(hist, hist, 0, 256, cv2.NORM_MINMAX)
        for i in range(1, 256):
            cv2.line(hist_img, (i-1, 255 - int(hist[i-1])),
                      (i, 255 - int(hist[i])), (0, 255, 0), 1)
        return self.ok(hist_img, "直方图计算完成")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Hog(OpenCVNodeDataBase):
    __group__ = "其他模块"
    def __init__(self): super().__init__(); self.name = "HOG描述子"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        hog = cv2.HOGDescriptor()
        h = hog.compute(gray)
        return self.ok(mat, f"HOG特征维度: {h.shape}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class SeamlessClone(OpenCVNodeDataBase):
    __group__ = "其他模块"
    clone_type = Property("NORMAL_CLONE", name="融合方式", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "无缝融合"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        if src is None or src.mat is None: return self.ok(mat, "无目标背景")
        h, w = mat.shape[:2]
        mask = np.ones((h, w), dtype=np.uint8) * 255
        cx, cy = w // 2, h // 2
        cmap = {"NORMAL_CLONE": cv2.NORMAL_CLONE, "MIXED_CLONE": cv2.MIXED_CLONE}
        result = cv2.seamlessClone(mat, src.mat, mask, (cx, cy), cmap.get(self.clone_type, cv2.NORMAL_CLONE))
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Stitching(OpenCVNodeDataBase):
    __group__ = "其他模块"
    def __init__(self): super().__init__(); self.name = "图像拼接"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        if src is None or src.mat is None: return self.ok(mat, "需要两张图像进行拼接")
        try:
            stitcher = cv2.Stitcher_create()
            status, result = stitcher.stitch([mat, src.mat])
            if status == cv2.Stitcher_OK:
                return self.ok(result, "拼接成功")
            return self.error(mat, f"拼接失败: status={status}")
        except Exception as e:
            return self.error(mat, str(e))

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Subdiv2D(OpenCVNodeDataBase):
    __group__ = "其他模块"
    def __init__(self): super().__init__(); self.name = "2D细分"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        subdiv = cv2.Subdiv2D((0, 0, w, h))
        points = [(w//4, h//4), (3*w//4, h//4), (w//2, 3*h//4), (w//4, h//2), (3*w//4, h//2)]
        for pt in points: subdiv.insert(pt)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        cv2.circle(out, points[0], 5, (0, 0, 255), -1)
        triangles = subdiv.getTriangleList()
        for t in triangles:
            pts = [(int(t[i]), int(t[i+1])) for i in range(0, 6, 2)]
            cv2.line(out, pts[0], pts[1], (255, 0, 0), 1)
            cv2.line(out, pts[1], pts[2], (255, 0, 0), 1)
            cv2.line(out, pts[2], pts[0], (255, 0, 0), 1)
        return self.ok(out)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class SVM(OpenCVNodeDataBase):
    __group__ = "其他模块"
    svm_type = Property("C_SVC", name="SVM类型", group=PropertyGroupNames.RUN_PARAMETERS)
    kernel_type = Property("RBF", name="核函数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self): super().__init__(); self.name = "SVM分类器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        svm = cv2.ml.SVM_create()
        type_map = {"C_SVC": cv2.ml.SVM_C_SVC, "NU_SVC": cv2.ml.SVM_NU_SVC, "ONE_CLASS": cv2.ml.SVM_ONE_CLASS}
        kernel_map = {"LINEAR": cv2.ml.SVM_LINEAR, "RBF": cv2.ml.SVM_RBF, "POLY": cv2.ml.SVM_POLY}
        svm.setType(type_map.get(self.svm_type, cv2.ml.SVM_C_SVC))
        svm.setKernel(kernel_map.get(self.kernel_type, cv2.ml.SVM_RBF))
        return self.ok(mat, "SVM分类器已配置")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class WarpAffineTransform(OpenCVNodeDataBase):
    __group__ = "其他模块"
    dx = Property(0, name="平移X", group=PropertyGroupNames.RUN_PARAMETERS)
    dy = Property(0, name="平移Y", group=PropertyGroupNames.RUN_PARAMETERS)
    angle = Property(0.0, name="旋转角度", group=PropertyGroupNames.RUN_PARAMETERS)
    scale = Property(1.0, name="缩放", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self): super().__init__(); self.name = "仿射变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, self.angle, self.scale)
        M[0, 2] += self.dx
        M[1, 2] += self.dy
        result = cv2.warpAffine(mat, M, (w, h))
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class WarpPerspectiveTransform(OpenCVNodeDataBase):
    __group__ = "其他模块"
    tl_x = Property(0, name="左上X", group=PropertyGroupNames.RUN_PARAMETERS)
    tl_y = Property(0, name="左上Y", group=PropertyGroupNames.RUN_PARAMETERS)
    tr_x = Property(100, name="右上X", group=PropertyGroupNames.RUN_PARAMETERS)
    tr_y = Property(0, name="右上Y", group=PropertyGroupNames.RUN_PARAMETERS)
    bl_x = Property(0, name="左下X", group=PropertyGroupNames.RUN_PARAMETERS)
    bl_y = Property(100, name="左下Y", group=PropertyGroupNames.RUN_PARAMETERS)
    br_x = Property(100, name="右下X", group=PropertyGroupNames.RUN_PARAMETERS)
    br_y = Property(100, name="右下Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self): super().__init__(); self.name = "透视变换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        h, w = mat.shape[:2]
        src_pts = np.float32([[0, 0], [w, 0], [0, h], [w, h]])
        dst_pts = np.float32([[self.tl_x, self.tl_y], [self.tr_x, self.tr_y],
                               [self.bl_x, self.bl_y], [self.br_x, self.br_y]])
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        result = cv2.warpPerspective(mat, M, (w, h))
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class DnnSuperres(OpenCVNodeDataBase):
    __group__ = "其他模块"
    scale = Property(4, name="放大倍数", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self): super().__init__(); self.name = "DNN超分辨率"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        try:
            sr = cv2.dnn_superres.DnnSuperResImpl_create()
            result = cv2.resize(mat, (mat.shape[1] * self.scale, mat.shape[0] * self.scale),
                                 interpolation=cv2.INTER_CUBIC)
            return self.ok(result, f"放大 {self.scale}x")
        except Exception as e:
            return self.error(mat, str(e))

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class Yolov3(OpenCVNodeDataBase):
    __group__ = "其他模块"
    config_path = Property("", name="配置文件", group=PropertyGroupNames.RUN_PARAMETERS)
    weights_path = Property("", name="权重文件", group=PropertyGroupNames.RUN_PARAMETERS)
    confidence = Property(0.5, name="置信度阈值", group=PropertyGroupNames.RUN_PARAMETERS)
    nms_threshold = Property(0.4, name="NMS阈值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self): super().__init__(); self.name = "YOLOv3检测器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None: return self.error(None, "无输入图像")
        if not self.config_path or not self.weights_path:
            self._net = cv2.dnn.readNetFromDarknet(
                self.config_path or "yolov3.cfg",
                self.weights_path or "yolov3.weights")
        h, w = mat.shape[:2]
        blob = cv2.dnn.blobFromImage(mat, 1/255.0, (416, 416), swapRB=True, crop=False)
        layers = self._net.getUnconnectedOutLayersNames()
        self._net.setInput(blob)
        outputs = self._net.forward(layers)
        out = mat.copy()
        for output in outputs:
            for det in output:
                scores = det[5:]
                class_id = np.argmax(scores)
                confidence_val = scores[class_id]
                if confidence_val > self.confidence:
                    cx, cy, bw, bh = det[0:4] * np.array([w, h, w, h])
                    x = int(cx - bw / 2)
                    y = int(cy - bh / 2)
                    cv2.rectangle(out, (x, y), (int(x + bw), int(y + bh)), (0, 255, 0), 2)
        return self.ok(out, "YOLOv3检测完成")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
