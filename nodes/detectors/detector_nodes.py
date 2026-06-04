"""Detector nodes: Canny, FindContours, HoughLines, HoughLinesP, RenderBlobs, BlobDetector, QRCode."""
import cv2
import numpy as np
from core.node_base import OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class Canny(OpenCVNodeDataBase):
    __group__ = "对象识别模块"
    threshold1 = Property(50.0, name="阈值1", group=PropertyGroupNames.RUN_PARAMETERS)
    threshold2 = Property(200.0, name="阈值2", group=PropertyGroupNames.RUN_PARAMETERS)
    aperture_size = Property(3, name="Sobel孔径", group=PropertyGroupNames.RUN_PARAMETERS)
    l2_gradient = Property(False, name="L2梯度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "Canny边缘检测"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        result = cv2.Canny(gray, self.threshold1, self.threshold2,
                            apertureSize=self.aperture_size, L2gradient=self.l2_gradient)
        return self.ok(result)

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class FindContours(OpenCVNodeDataBase):
    __group__ = "对象识别模块"
    contour_count = Property(0, name="轮廓数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "查找轮廓"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(out, contours, -1, (0, 255, 0), 2)
        self.contour_count = len(contours)
        return self.ok(out, f"发现 {len(contours)} 个轮廓")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class HoughLines(OpenCVNodeDataBase):
    __group__ = "对象识别模块"
    rho = Property(1.0, name="距离分辨率", group=PropertyGroupNames.RUN_PARAMETERS)
    theta = Property(1.0, name="角度分辨率", group=PropertyGroupNames.RUN_PARAMETERS)
    threshold = Property(100, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "霍夫线检测"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        edges = cv2.Canny(gray, 50, 200)
        lines = cv2.HoughLines(edges, self.rho, np.pi / 180 * self.theta, self.threshold)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        count = 0
        if lines is not None:
            for line in lines:
                rho, theta = line[0]
                a, b = np.cos(theta), np.sin(theta)
                x0, y0 = a * rho, b * rho
                pt1 = (int(x0 + 1000 * (-b)), int(y0 + 1000 * a))
                pt2 = (int(x0 - 1000 * (-b)), int(y0 - 1000 * a))
                cv2.line(out, pt1, pt2, (0, 0, 255), 1)
                count += 1
        return self.ok(out, f"检测到 {count} 条直线")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class HoughLinesP(OpenCVNodeDataBase):
    __group__ = "对象识别模块"
    rho = Property(1.0, name="Rho", group=PropertyGroupNames.RUN_PARAMETERS)
    min_line_length = Property(50, name="最小线长", group=PropertyGroupNames.RUN_PARAMETERS)
    max_line_gap = Property(10, name="最大间隔", group=PropertyGroupNames.RUN_PARAMETERS)
    threshold = Property(50, name="阈值", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "霍夫线段检测"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        edges = cv2.Canny(gray, 50, 200)
        lines = cv2.HoughLinesP(edges, self.rho, np.pi / 180, self.threshold,
                                 minLineLength=self.min_line_length, maxLineGap=self.max_line_gap)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        count = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
                count += 1
        return self.ok(out, f"检测到 {count} 条线段")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class RenderBlobs(OpenCVNodeDataBase):
    __group__ = "对象识别模块"

    def __init__(self):
        super().__init__()
        self.name = "Blob渲染"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        gray = cv2.cvtColor(mat, cv2.COLOR_BGR2GRAY) if len(mat.shape) == 3 else mat
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = mat.copy() if len(mat.shape) == 3 else cv2.cvtColor(mat, cv2.COLOR_GRAY2BGR)
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        return self.ok(out, f"渲染 {len(contours)} 个Blob")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class BlobDetector(OpenCVNodeDataBase):
    __group__ = "对象识别模块"

    def __init__(self):
        super().__init__()
        self.name = "Blob检测器"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        params = cv2.SimpleBlobDetector_Params()
        detector = cv2.SimpleBlobDetector_create(params)
        keypoints = detector.detect(mat)
        out = cv2.drawKeypoints(mat, keypoints, None, (0, 255, 0),
                                 cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        return self.ok(out, f"检测到 {len(keypoints)} 个Blob")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class QRCode(OpenCVNodeDataBase):
    __group__ = "对象识别模块"
    qr_result = Property("", name="二维码结果", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

    def __init__(self):
        super().__init__()
        self.name = "二维码识别"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        detector = cv2.QRCodeDetector()
        data, points, _ = detector.detectAndDecode(mat)
        out = mat.copy()
        if data:
            self.qr_result = data
            if points is not None:
                pts = points.astype(int)
                for i in range(4):
                    cv2.line(out, tuple(pts[i][0]), tuple(pts[(i+1)%4][0]), (0, 255, 0), 2)
            return self.ok(out, f"QR: {data}")
        self.qr_result = ""
        return self.ok(out, "未检测到二维码")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
