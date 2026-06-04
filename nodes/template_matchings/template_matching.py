"""Template matching nodes: standard, best match, SIFT, SURF, HSV Blob."""
import base64
import cv2
import numpy as np
from core.node_base import Base64MatchingNodeData, OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from core.workflow import WorkflowEngine


class TemplateBase64MatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase):
    """Template matching using cv2.matchTemplate with Base64 template."""
    __group__ = "模板匹配模块"
    match_mode = Property("CCoeffNormed", name="匹配方法", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        Base64MatchingNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "模板匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        template = self.get_template_image()
        if template is None: return self.error(mat, "未设置模板图片")

        modes = {"SQDIFF": cv2.TM_SQDIFF, "SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED,
                  "CCORR": cv2.TM_CCORR, "CCORR_NORMED": cv2.TM_CCORR_NORMED,
                  "CCoeff": cv2.TM_CCOEFF, "CCoeffNormed": cv2.TM_CCOEFF_NORMED}
        method = modes.get(self.match_mode, cv2.TM_CCOEFF_NORMED)

        result = cv2.matchTemplate(mat, template, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= 0.8:
            h, w = template.shape[:2]
            color_mat = mat.copy()
            cv2.rectangle(color_mat, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
            self.matching_count_result = 1
            self.confidence = max_val
            return self.ok(color_mat, f"匹配成功 置信度: {max_val:.3f}")
        self.matching_count_result = 0
        self.confidence = 0.0
        return self.ok(mat, "没有匹配到模板")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class BestMatchBase64TemplateMatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase):
    """Template matching that returns only the best match above threshold."""
    __group__ = "模板匹配模块"
    match_mode = Property("CCoeffNormed", name="匹配方法", group=PropertyGroupNames.RUN_PARAMETERS)
    threshold = Property(0.8, name="最小置信度", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        Base64MatchingNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "最佳匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        template = self.get_template_image()
        if template is None: return self.error(mat, "未设置模板图片")

        modes = {"SQDIFF_NORMED": cv2.TM_SQDIFF_NORMED, "CCORR_NORMED": cv2.TM_CCORR_NORMED,
                  "CCoeffNormed": cv2.TM_CCOEFF_NORMED}
        method = modes.get(self.match_mode, cv2.TM_CCOEFF_NORMED)

        result = cv2.matchTemplate(mat, template, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= self.threshold:
            h, w = template.shape[:2]
            out = mat.copy()
            cv2.rectangle(out, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
            self.matching_count_result = 1
            self.confidence = max_val
            return self.ok(out, f"最佳匹配: {max_val:.3f}")
        self.matching_count_result = 0
        self.confidence = 0.0
        return self.ok(mat, "未找到匹配")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class SiftBase64FeatureMatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase):
    """Feature matching using SIFT descriptors."""
    __group__ = "模板匹配模块"

    def __init__(self):
        Base64MatchingNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "SIFT特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        template = self.get_template_image()
        if template is None: return self.error(mat, "未设置模板图片")

        sift = cv2.SIFT_create()
        kp1, des1 = sift.detectAndCompute(template, None)
        kp2, des2 = sift.detectAndCompute(mat, None)

        if des1 is None or des2 is None:
            return self.ok(mat, "无法提取特征点")

        bf = cv2.BFMatcher()
        matches = bf.knnMatch(des1, des2, k=2)
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]

        out = mat.copy()
        out = cv2.drawMatches(template, kp1, mat, kp2, good, out,
                               flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        self.matching_count_result = len(good)
        self.confidence = len(good) / max(len(kp1), 1)
        return self.ok(out, f"匹配 {len(good)} 个特征点")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class SurfBase64FeatureMatchingNode(SiftBase64FeatureMatchingNode):
    """Feature matching using SURF (falls back to SIFT if not available)."""
    __group__ = "模板匹配模块"

    def __init__(self):
        super().__init__()
        self.name = "SURF特征匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        template = self.get_template_image()
        if template is None: return self.error(mat, "未设置模板图片")

        try:
            surf = cv2.xfeatures2d.SURF_create()
        except AttributeError:
            return SiftBase64FeatureMatchingNode.invoke_core(self, src, from_node, diagram)

        kp1, des1 = surf.detectAndCompute(template, None)
        kp2, des2 = surf.detectAndCompute(mat, None)
        if des1 is None or des2 is None: return self.ok(mat, "无法提取特征点")

        bf = cv2.BFMatcher()
        matches = bf.knnMatch(des1, des2, k=2)
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]
        out = cv2.drawMatches(template, kp1, mat, kp2, good, mat.copy(),
                               flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
        self.matching_count_result = len(good)
        return self.ok(out, f"SURF匹配 {len(good)} 个特征点")

    def _update_result_image_source(self):
        self._result_image_source = self._mat


class HSVInRangeRenderBlobMatchingNode(OpenCVNodeDataBase):
    """HSV color-based blob matching."""
    __group__ = "模板匹配模块"
    h_low = Property(0, name="H低", group=PropertyGroupNames.RUN_PARAMETERS)
    h_high = Property(180, name="H高", group=PropertyGroupNames.RUN_PARAMETERS)
    s_low = Property(0, name="S低", group=PropertyGroupNames.RUN_PARAMETERS)
    s_high = Property(255, name="S高", group=PropertyGroupNames.RUN_PARAMETERS)
    v_low = Property(0, name="V低", group=PropertyGroupNames.RUN_PARAMETERS)
    v_high = Property(255, name="V高", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "HSV Blob匹配"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = from_node.mat if from_node else None
        if mat is None: return self.error(None, "无输入图像")
        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        lower = np.array([self.h_low, self.s_low, self.v_low], dtype=np.uint8)
        upper = np.array([self.h_high, self.s_high, self.v_high], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = mat.copy()
        cv2.drawContours(out, contours, -1, (0, 255, 0), 2)
        return self.ok(out, f"发现 {len(contours)} 个Blob")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
