"""无缝融合支持三种融合方式。"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult


class SeamlessClone(OpenCVNodeDataBase):
    """无缝融合 — 将源节点图像（前景）无缝贴到上游图像（背景）上。

    上游 from.Mat = 背景(dst)，前景(src) 从文件加载或使用源节点图像。
    """

    __group__ = "其他模块"
    clone_type = Property("NORMAL_CLONE", name="融合方式", group=PropertyGroupNames.RUN_PARAMETERS,
                          editor="choices", choices=["NORMAL_CLONE", "MIXED_CLONE", "MONOCHROME_TRANSFER"])
    center_x = Property(0, name="放置中心X", group=PropertyGroupNames.RUN_PARAMETERS, description="0=自动居中")
    center_y = Property(0, name="放置中心Y", group=PropertyGroupNames.RUN_PARAMETERS, description="0=自动居中")

    def __init__(self):
        super().__init__()
        self.name = "无缝融合"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        # 背景 = 上游节点图像
        bg = self.get_input_mat(from_node.mat if from_node else None)
        if bg is None:
            return self.error(None, "无输入图像（上游=背景）")
        # 前景 = 源节点图像
        if src is None or src.mat is None:
            return self.ok(bg, "未连接数据源（源节点=前景），输出原背景")
        fg = src.mat
        if fg.shape[0] > bg.shape[0] or fg.shape[1] > bg.shape[1]:
            fg = cv2.resize(fg, (min(fg.shape[1], bg.shape[1]), min(fg.shape[0], bg.shape[0])))
        clone_map = {"NORMAL_CLONE": cv2.NORMAL_CLONE, "MIXED_CLONE": cv2.MIXED_CLONE,
                     "MONOCHROME_TRANSFER": cv2.MONOCHROME_TRANSFER}
        if len(fg.shape) != len(bg.shape):
            if len(fg.shape) == 2: fg = cv2.cvtColor(fg, cv2.COLOR_GRAY2BGR)
        mask = np.ones(fg.shape[:2], dtype=np.uint8) * 255
        bh, bw = bg.shape[:2]
        cx = bw // 2 if not self.center_x else int(self.center_x)
        cy = bh // 2 if not self.center_y else int(self.center_y)
        try:
            result = cv2.seamlessClone(fg, bg, mask, (cx, cy),
                                        clone_map.get(self.clone_type, cv2.NORMAL_CLONE))
            return self.ok(result, f"无缝融合 ({self.clone_type})")
        except cv2.error as e:
            return self.ok(bg, f"融合失败(已回退): {e}")

    def _update_result_image_source(self):
        self._result_image_source = self._mat
