import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class HSVInRange(OpenCVNodeDataBase):
    """HSV色彩范围提取 — 吸管取色 + 容差参数自动计算 HSV 上下限"""
    __group__ = "图像分割提取模块"

    pick_color = Property("#008000", name="取色", group=PropertyGroupNames.RUN_PARAMETERS, editor="color")
    h_range = Property(35, name="色相范围(H)", group=PropertyGroupNames.RUN_PARAMETERS, min_val=0, max_val=85)
    s_range = Property(30, name="饱和度范围(S)", group=PropertyGroupNames.RUN_PARAMETERS, min_val=0, max_val=255)
    v_range = Property(30, name="明度范围(V)", group=PropertyGroupNames.RUN_PARAMETERS, min_val=0, max_val=255)

    def __init__(self):
        super().__init__()
        self.name = "HSV色彩提取"

    def _hex_to_bgr_pixel(self) -> np.ndarray:
        hex_color = (self.pick_color or "#008000").lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return np.array([[[b, g, r]]], dtype=np.uint8)

    def _get_hsv_range(self) -> tuple[np.ndarray, np.ndarray]:
        bgr = self._hex_to_bgr_pixel()
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0, 0]
        h, s, v = int(hsv[0]), int(hsv[1]), int(hsv[2])
        h_f, s_f, v_f = h * 2, s / 2.55, v / 2.55
        hr, sr, vr = self.h_range, self.s_range, self.v_range
        l_h_min = max(0, h_f - hr)
        l_s_min = max(0, s_f - sr)
        l_v_min = max(0, v_f - vr)
        u_h_max = min(360, h_f + hr / 2)
        u_s_max = min(100, s_f + sr / 2)
        u_v_max = min(100, v_f + vr / 2)
        lower = np.array([l_h_min / 2, l_s_min * 2.55, l_v_min * 2.55], dtype=np.uint8)
        upper = np.array([u_h_max / 2, u_s_max * 2.55, u_v_max * 2.55], dtype=np.uint8)
        return lower, upper

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        self._picker_mat = mat.copy()
        lower, upper = self._get_hsv_range()
        hsv = cv2.cvtColor(mat, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower, upper)
        return self.ok(mask, "HSV色彩范围提取完成")
