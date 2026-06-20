"""图像拼接将源节点图像和上游图像拼接为一张大图。"""

import cv2
import numpy as np
from core.node_base import Property, PropertyGroupNames
from core.node_selectable import OpenCVNodeDataBase
from core.data_packet import FlowableResult

_STATUS_MSG = {
    cv2.Stitcher_OK: "拼接成功",
    cv2.Stitcher_ERR_NEED_MORE_IMGS: "需要更多图像（至少2张）",
    cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL: "特征匹配失败（两图重叠区域不足或差异太大）",
    cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL: "相机参数调整失败",
}


class Stitching(OpenCVNodeDataBase):
    """图像拼接 — 上游(图1) + 源节点(图2) → 拼接大图。

    使用方式：连两个图像源 → 上游=左图/上图，数据源=右图/下图。
    两张图需要有重叠区域才能拼接成功。
    """

    __group__ = "其他模块"
    mode = Property("SCANS", name="拼接模式", group=PropertyGroupNames.RUN_PARAMETERS,
                    editor="choices", choices=["PANORAMA", "SCANS"],
                    description="PANORAMA=全景(透视变形), SCANS=扫描件(仿射变换,更快)")

    def __init__(self):
        super().__init__()
        self.name = "图像拼接"

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self._require_input_mat(from_node)
        if mat is None:
            return self.error(None, "无输入图像（上游=图1）")
        if src is None or src.mat is None:
            return self.ok(mat, "未连接数据源（数据源=图2），输出原图")
        img2 = src.mat
        # 大图缩到 800 宽加速拼接
        img1, img2 = self._resize_if_large(mat, img2)
        mode_map = {"PANORAMA": cv2.Stitcher_PANORAMA, "SCANS": cv2.Stitcher_SCANS}
        stitcher = cv2.Stitcher_create(mode_map.get(self.mode, cv2.Stitcher_SCANS))
        try:
            status, result = stitcher.stitch([img1, img2])
            if status == cv2.Stitcher_OK:
                return self.ok(result, f"拼接成功 ({self.mode})")
            msg = _STATUS_MSG.get(status, f"拼接失败: status={status}")
            return self.ok(mat, msg)
        except Exception as e:
            return self.ok(mat, f"拼接异常: {e}")

    def _resize_if_large(self, img1, img2):
        max_dim = 800
        res = []
        for img in (img1, img2):
            h, w = img.shape[:2]
            if max(w, h) > max_dim:
                scale = max_dim / max(w, h)
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
            res.append(img)
        return res[0], res[1]
