"""基于 XFeat 的特征模板匹配。

实现思路：
1. 使用 XFeat 从模板和搜索图中提取稀疏特征点与描述符；
2. 通过互近邻 (MNN) + 余弦相似度进行特征匹配；
3. 通过 RANSAC 估计单应性矩阵，计算模板在搜索图中的位置；
4. 支持旋转、缩放、透视变换的鲁棒匹配。
"""

import os as _os
_os.environ["CUDA_VISIBLE_DEVICES"] = ""

import cv2
import numpy as np
import torch

from core.node_base import Base64MatchingNodeData, OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import ITemplateMatchingGroupableNode


# ---------------------------------------------------------------------------
# 全局模型缓存
# ---------------------------------------------------------------------------

_global_device = None
_global_xfeat = None


def _get_device():
    global _global_device
    if _global_device is None:
        _global_device = torch.device("cpu")
    return _global_device


def _get_xfeat():
    global _global_xfeat
    if _global_xfeat is None:
        from kornia.feature import XFeat
        device = _get_device()
        _global_xfeat = XFeat().to(device).eval()
        _global_xfeat.detection_threshold = 0.0
        _global_xfeat.top_k = 2048
    return _global_xfeat


# ---------------------------------------------------------------------------
# ShapeModel
# ---------------------------------------------------------------------------

class ShapeModel:
    """缓存模板 tensor，供 XFeat match_xfeat 使用。"""

    def __init__(self, img):
        self._device = _get_device()
        self.h, self.w = img.shape[:2]
        self._tensor = self._to_tensor(img)

    def _to_tensor(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        if gray.dtype != np.uint8:
            gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        tensor = torch.from_numpy(gray.copy()).float()[None, None] / 255.0
        return tensor.to(self._device)

    @property
    def device(self):
        return self._device

    @property
    def tensor(self):
        return self._tensor

    @property
    def shape(self):
        return (self.h, self.w)

    @property
    def num_pts(self):
        return 1  # 模板总是有效（特征在匹配时提取）


# ---------------------------------------------------------------------------
# find_shape_match — XFeat MNN + RANSAC
# ---------------------------------------------------------------------------

def find_shape_match(img, model, min_match_dist=0.75, max_matches=5,
                     min_inliers=8, ransac_thresh=5.0):
    """使用 XFeat 特征 + BFMatcher ratio test + RANSAC 单应性估计。

    Args:
        img: 搜索图像 (H, W, 3) BGR
        model: ShapeModel 实例
        min_match_dist: ratio test 阈值 (越小越严格)
        min_inliers: RANSAC 最少内点数
        ransac_thresh: RANSAC 重投影误差阈值 (像素)

    Returns:
        list[dict]
    """
    if model is None:
        return []

    xfeat = _get_xfeat()
    img_tensor = model._to_tensor(img)

    # 提取特征
    f0 = xfeat.detectAndCompute(model.tensor, detection_threshold=0.0)[0]
    f1 = xfeat.detectAndCompute(img_tensor, detection_threshold=0.0)[0]

    if len(f0["keypoints"]) < 4 or len(f1["keypoints"]) < 4:
        return []

    desc0 = f0["descriptors"].cpu().numpy()
    desc1 = f1["descriptors"].cpu().numpy()
    kpts0_np = f0["keypoints"].cpu().numpy()
    kpts1_np = f1["keypoints"].cpu().numpy()

    # BFMatcher + ratio test
    bf = cv2.BFMatcher(cv2.NORM_L2)
    raw = bf.knnMatch(desc0, desc1, k=2)
    good = [m for m, n in raw if m.distance < min_match_dist * n.distance]

    if len(good) < 4:
        return []

    kpts0 = np.float32([kpts0_np[m.queryIdx] for m in good])
    kpts1 = np.float32([kpts1_np[m.trainIdx] for m in good])

    H, mask = cv2.findHomography(kpts0, kpts1, cv2.RANSAC, ransac_thresh)
    if H is None or mask is None:
        return []

    inliers = int(mask.sum())
    if inliers < min_inliers:
        return []

    h, w = model.h, model.w
    corners = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
    transformed = cv2.perspectiveTransform(corners, H)
    pts = transformed.reshape(-1, 2)

    x, y = pts[:, 0].min(), pts[:, 1].min()
    bw, bh = pts[:, 0].max() - x, pts[:, 1].max() - y

    v = pts[1] - pts[0]
    angle = float(np.degrees(np.arctan2(v[1], v[0])))

    return [{
        "x": float(pts[0, 0]),
        "y": float(pts[0, 1]),
        "cx": float(x + bw / 2.0),
        "cy": float(y + bh / 2.0),
        "angle": angle,
        "scale": float(bw) / max(w, 1.0),
        "score": float(inliers) / max(len(kpts0), 1),
        "rect_size": (float(bw), float(bh)),
        "quad": pts.tolist(),
    }]


# ---------------------------------------------------------------------------
# ShapeTemplateMatchingNode
# ---------------------------------------------------------------------------

class ShapeTemplateMatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase,
                                ITemplateMatchingGroupableNode):
    __group__ = "模板匹配模块"
    template_image = Property("", name="模板图片", group=PropertyGroupNames.RUN_PARAMETERS,
                              editor="crop", order=1000)

    min_match_dist = Property(80, name="Ratio Test阈值(%)", group=PropertyGroupNames.RUN_PARAMETERS,
                              min_val=50, max_val=100, step=5)
    max_matches = Property(3, name="最大匹配数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=1, max_val=100)
    min_inliers = Property(8, name="最少内点数", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=4, max_val=500)
    ransac_thresh = Property(5.0, name="RANSAC阈值(px)", group=PropertyGroupNames.RUN_PARAMETERS,
                             min_val=1.0, max_val=50.0, step=0.5)

    matching_count_result = Property(0, name="匹配数量", group=PropertyGroupNames.RESULT_PARAMETERS,
                                     readonly=True)
    confidence = Property(0.0, name="置信度(0-100)", group=PropertyGroupNames.RESULT_PARAMETERS,
                          readonly=True)

    def __init__(self):
        Base64MatchingNodeData.__init__(self)
        OpenCVNodeDataBase.__init__(self)
        self.name = "形状模板匹配"
        self._model = None
        self._model_b64 = ""

    def invoke_core(self, src, from_node, diagram) -> FlowableResult:
        mat = self.get_input_mat(from_node.mat if from_node else None)
        if mat is None:
            return self.error(None, "无输入图像")
        template = self.get_template_image()
        if template is None:
            return self.ok(mat, "未设置模板图片，输出原图")

        if self._model is None or self._model_b64 != self.base64_string:
            try:
                self._model = ShapeModel(template)
            except Exception as e:
                return self.ok(mat, f"特征提取失败: {e}")
            self._model_b64 = self.base64_string

        if self._model is None:
            return self.ok(mat, "模板无效")

        try:
            results = find_shape_match(
                mat,
                self._model,
                min_match_dist=self.min_match_dist / 100.0,
                max_matches=self.max_matches,
                min_inliers=self.min_inliers,
                ransac_thresh=self.ransac_thresh,
            )
        except Exception as e:
            return self.ok(mat, f"匹配异常: {e}")

        out = mat.copy()
        best = 0.0
        for result in results:
            score = float(result["score"])
            sc = int(round(score * 100.0))
            best = max(best, float(sc))

            cx, cy = result["cx"], result["cy"]
            rw, rh = result["rect_size"]
            x1, y1 = int(cx - rw / 2), int(cy - rh / 2)
            x2, y2 = int(cx + rw / 2), int(cy + rh / 2)
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)

            label_x = x1
            label_y = y1 - 5 if y1 > 10 else y2 + 15
            cv2.putText(out, f"{sc}%",
                        (label_x, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        self.matching_count_result = len(results)
        self.confidence = best
        return self.ok(out, f"匹配 {len(results)} 处 (最高: {best:.0f})")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def is_valid(self, mat):
        return mat is not None and mat.size > 0
