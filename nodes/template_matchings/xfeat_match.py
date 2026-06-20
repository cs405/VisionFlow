"""XFeat 特征模板匹配 — CVPR 2024 轻量级特征匹配。

基于 XFeat 稀疏特征点 + MNN 匹配 + MAGSAC 鲁棒单应性估计。
支持旋转/缩放/透视变换，适合实时模板匹配场景。
"""

import cv2
import numpy as np

from core.node_base import Property, PropertyGroupNames
from core.node_selectable import Base64MatchingNodeData, OpenCVNodeDataBase
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import ITemplateMatchingGroupableNode

# ---------------------------------------------------------------------------
# 全局 XFeat 模型（单例，避免重复加载）
# ---------------------------------------------------------------------------
_global_xfeat = None


def _get_xfeat(top_k=2048):
    """延迟加载 XFeat 模型和 PyTorch，避免调试器 DLL 注入冲突。"""
    global _global_xfeat
    if _global_xfeat is None:
        import os as _os
        _os.environ["CUDA_VISIBLE_DEVICES"] = ""
        global torch
        import torch
        from nodes.modules.xfeat import XFeat
        _global_xfeat = XFeat(top_k=top_k).eval()
    return _global_xfeat


# ---------------------------------------------------------------------------
# ShapeModel — 缓存模板的 XFeat 特征
# ---------------------------------------------------------------------------
class ShapeModel:
    def __init__(self, img, top_k=2048):
        self.h, self.w = img.shape[:2]
        xfeat = _get_xfeat(top_k)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        # 确保数据类型和设备与 XFeat 模型一致
        tensor = torch.from_numpy(
            gray.astype(np.float32).copy()
        ).float()[None, None] / 255.0
        tensor = tensor.to(xfeat.dev)
        try:
            self._feat = xfeat.detectAndCompute(tensor, detection_threshold=0.05)[0]
        except Exception:
            # 回退：用更低阈值重试
            self._feat = xfeat.detectAndCompute(tensor, detection_threshold=0.0)[0]
        self._feat = {k: v.cpu() for k, v in self._feat.items()}

    @property
    def shape(self):
        return (self.h, self.w)

    @property
    def num_pts(self):
        return len(self._feat.get("keypoints", []))


# ---------------------------------------------------------------------------
# find_shape_match — XFeat MNN + MAGSAC 单应性
# ---------------------------------------------------------------------------
def find_shape_match(img, model, ratio_thresh=0.82, min_inliers=10,
                     ransac_thresh=4.0, max_matches=5):
    if model is None:
        return []
    xfeat = _get_xfeat()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    t = (torch.from_numpy(gray.astype(np.float32).copy()).float()[None, None] / 255.0).to(xfeat.dev)
    cur = xfeat.detectAndCompute(t, detection_threshold=0.0)[0]
    cur = {k: v.cpu() for k, v in cur.items()}

    kpts0 = model._feat["keypoints"].numpy()
    desc0 = model._feat["descriptors"].numpy()
    kpts1 = cur["keypoints"].numpy()
    desc1 = cur["descriptors"].numpy()

    if len(kpts0) < 4 or len(kpts1) < 4:
        return []

    # MNN 匹配 (XFeat 风格)
    idx0, idx1 = xfeat.match(model._feat["descriptors"], cur["descriptors"],
                              ratio_thresh)
    if len(idx0) < 4:
        return []
    pts0 = kpts0[idx0.cpu().numpy()]
    pts1 = kpts1[idx1.cpu().numpy()]

    # MAGSAC 鲁棒单应性
    H, mask = cv2.findHomography(pts0, pts1, cv2.USAC_MAGSAC, ransac_thresh,
                                  maxIters=700, confidence=0.995)
    if H is None or mask is None:
        return []
    inliers = int(mask.sum())
    if inliers < min_inliers:
        return []

    h, w = model.h, model.w
    corners = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(corners, H).reshape(-1, 2)
    x, y = transformed[:, 0].min(), transformed[:, 1].min()
    bw, bh = transformed[:, 0].max() - x, transformed[:, 1].max() - y
    score = min(100.0, inliers / max(len(kpts0), 1) * 100.0)
    return [{
        "x": float(x), "y": float(y), "w": float(bw), "h": float(bh),
        "score": score, "inliers": inliers,
        "quad": transformed.tolist(),
    }]


# ---------------------------------------------------------------------------
# VisionFlow 节点
# ---------------------------------------------------------------------------
class XFeatMatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase,
                                 ITemplateMatchingGroupableNode):
    __group__ = "模板匹配模块"
    template_image = Property("", name="模板图片", group=PropertyGroupNames.RUN_PARAMETERS,
                              editor="crop", order=1000)
    ratio_thresh = Property(80, name="MNN阈值(%)", group=PropertyGroupNames.RUN_PARAMETERS,
                            min_val=1, max_val=99, step=1)
    min_inliers = Property(10, name="最少内点数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=4, max_val=500)
    ransac_thresh = Property(4.0, name="RANSAC阈值(px)", group=PropertyGroupNames.RUN_PARAMETERS,
                             min_val=1.0, max_val=50.0, step=0.5)
    max_matches = Property(3, name="最大匹配数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=1, max_val=100)
    top_k = Property(2048, name="最大特征点数", group=PropertyGroupNames.RUN_PARAMETERS,
                     min_val=256, max_val=4096, step=256)
    matching_count_result = Property(0, name="匹配数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                                     readonly=True)
    confidence = Property(0.0, name="置信度(0-100)", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    def __init__(self):
        Base64MatchingNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "XFeat匹配"
        self._model = None
        self._model_b64 = ""

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        self.matched = False
        self.match_x = self.match_y = self.match_w = self.match_h = 0
        if mat is None:
            return self.error(None, "无输入图像")
        template = self.get_template_image()
        if template is None:
            return self.error(None, "未设置模板图片，输出原图")

        if self._model is None or self._model_b64 != self.base64_string:
            try:
                self._model = ShapeModel(template, self.top_k)
            except Exception as e:
                return self.error(None, f"特征提取失败: {e}")
            self._model_b64 = self.base64_string

        if self._model is None:
            return self.error(None, "模板无效")

        try:
            results = find_shape_match(mat, self._model,
                                       self.ratio_thresh / 100.0,
                                       self.min_inliers,
                                       self.ransac_thresh,
                                       self.max_matches)
        except Exception as e:
            return self.error(None, f"匹配异常: {e}")

        out = mat.copy()
        best = 0.0
        best_rect = (0, 0, 0, 0)
        for r in results:
            best = max(best, r["score"])
            x, y, bw, bh = int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"])
            if r["score"] >= best:
                best_rect = (x, y, bw, bh)
            cv2.rectangle(out, (x, y), (x + bw, y + bh), (0, 255, 0), 3)
            cv2.putText(out, f"{r['score']:.0f}% in:{r['inliers']}",
                        (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        self.matching_count_result = len(results)
        self.confidence = best
        self.matched = len(results) > 0
        self.match_x, self.match_y, self.match_w, self.match_h = best_rect
        if self.matched:
            x, y, bw, bh = best_rect
            if bw > 0 and bh > 0:
                matched_region = out[y:y + bh, x:x + bw].copy()
                return self.ok(matched_region, f"匹配 {len(results)} 处 (最高: {best:.0f})")
            return self.error(None, "匹配区域无效")
        else:
            return self.error(None, f"错误: 未匹配到目标")

    def is_valid(self, mat):
        return mat is not None and mat.size > 0
