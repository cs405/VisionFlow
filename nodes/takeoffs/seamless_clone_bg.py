import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class SeamlessCloneBackground(OpenCVNodeDataBase):
    """无缝融合/背景替换 — NORMAL_CLONE / MIXED_CLONE / MONOCHROME_TRANSFER"""
    __group__ = "图像分割提取模块"

    clone_type = Property("NORMAL_CLONE", name="融合方式", group=PropertyGroupNames.RUN_PARAMETERS,
                          editor="choices", choices=["NORMAL_CLONE", "MIXED_CLONE", "MONOCHROME_TRANSFER"])
    center_x = Property(0, name="中心X", group=PropertyGroupNames.RUN_PARAMETERS)
    center_y = Property(0, name="中心Y", group=PropertyGroupNames.RUN_PARAMETERS)

    def __init__(self):
        super().__init__()
        self.name = "无缝融合/背景替换"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像")
        if src is None or src.mat is None:
            return self.ok(mat, "无背景图像，保持原图")
        clone_map = {"NORMAL_CLONE": cv2.NORMAL_CLONE, "MIXED_CLONE": cv2.MIXED_CLONE,
                     "MONOCHROME_TRANSFER": cv2.MONOCHROME_TRANSFER}
        fg, bg = mat, src.mat
        if len(fg.shape) != len(bg.shape) or fg.shape[2] != bg.shape[2]:
            if len(fg.shape) == 2: fg = cv2.cvtColor(fg, cv2.COLOR_GRAY2BGR)
            if len(bg.shape) == 2: bg = cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR)
        mask = np.ones(fg.shape[:2], dtype=np.uint8) * 255
        bg_h, bg_w = bg.shape[:2]
        fg_h, fg_w = fg.shape[:2]
        cx = max(fg_w // 2, min(bg_w - (fg_w - 1) // 2 - 1, int(self.center_x))) if self.center_x else bg_w // 2
        cy = max(fg_h // 2, min(bg_h - (fg_h - 1) // 2 - 1, int(self.center_y))) if self.center_y else bg_h // 2
        try:
            result = cv2.seamlessClone(fg, bg, mask, (cx, cy), clone_map.get(self.clone_type, cv2.NORMAL_CLONE))
        except cv2.error as e:
            return self.ok(mat, message=f"无缝融合失败(已回退原图): {e}")
        return self.ok(result)
