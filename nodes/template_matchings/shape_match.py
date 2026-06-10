"""基于边缘方向的形状模板匹配。

实现思路：
1. 从模板和搜索图中提取 Canny 边缘与归一化梯度方向；
2. 对模板做真实几何旋转/缩放（而不是只旋转方向向量）；
3. 通过 TM_CCORR 计算方向点积响应，并结合最小边缘重叠率过滤；
4. 通过局部极大值 + 旋转矩形 NMS 输出匹配结果。

该实现比普通灰度模板匹配更抗光照变化，支持旋转与有限尺度变化；
但它仍是轻量级形状匹配，并不等同于 HALCON 的工业级 shape model。
"""

import cv2
import numpy as np
from core.node_base import Base64MatchingNodeData, OpenCVNodeDataBase, Property, PropertyGroupNames
from core.data_packet import FlowableResult
from nodes.template_matchings.template_base import ITemplateMatchingGroupableNode


_EPS = np.float32(1e-6)


def _to_uint8_gray(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    if gray.dtype == np.uint8:
        return gray
    if np.issubdtype(gray.dtype, np.floating):
        gray = np.nan_to_num(gray)
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    return gray.astype(np.uint8)


def _edge_map(img, low=50, high=150):
    """提取边缘掩膜 + 归一化梯度方向向量 (cos, sin)"""
    gray = _to_uint8_gray(img)
    edges = cv2.Canny(gray, low, high, L2gradient=True) > 0
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, 3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, 3)
    mag = np.sqrt(gx * gx + gy * gy) + _EPS
    # 只在 Canny 边缘上保留梯度方向，其余置零
    cos_a = np.where(edges, gx / mag, np.float32(0))
    sin_a = np.where(edges, gy / mag, np.float32(0))
    return edges, cos_a.astype(np.float32), sin_a.astype(np.float32)


def _safe_resize(img, scale):
    h, w = img.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)


def _generate_scales(min_percent, max_percent, step_percent):
    min_percent = float(min_percent)
    max_percent = float(max_percent)
    step_percent = max(float(step_percent), 1.0)
    if min_percent > max_percent:
        min_percent, max_percent = max_percent, min_percent
    if abs(max_percent - min_percent) < 1e-6:
        return [min_percent / 100.0]
    scales = np.arange(min_percent, max_percent + step_percent * 0.5, step_percent, dtype=np.float32) / 100.0
    scales = np.clip(scales, 0.1, 10.0)
    scales = np.unique(np.round(scales, 4))
    return [float(s) for s in scales]


def _subpixel_offset(left_v, center_v, right_v):
    denom = float(left_v - 2.0 * center_v + right_v)
    if abs(denom) < 1e-6:
        return 0.0
    offset = 0.5 * float(left_v - right_v) / denom
    return float(np.clip(offset, -1.0, 1.0))


def _local_maxima(sm, thresh, max_peaks=256):
    """使用膨胀找局部极大值，并做简单亚像素细化。"""
    if sm.size == 0:
        return []
    k = np.ones((3, 3), np.uint8)
    d = cv2.dilate(sm, k)
    mask = (sm >= d) & (sm >= thresh)
    ys, xs = np.where(mask)
    peaks = []
    h, w = sm.shape
    for x, y in zip(xs.tolist(), ys.tolist()):
        score = float(sm[y, x])
        dx = dy = 0.0
        if 0 < x < w - 1:
            dx = _subpixel_offset(sm[y, x - 1], sm[y, x], sm[y, x + 1])
        if 0 < y < h - 1:
            dy = _subpixel_offset(sm[y - 1, x], sm[y, x], sm[y + 1, x])
        peaks.append({"x": float(x) + dx, "y": float(y) + dy, "score": score})
    peaks.sort(key=lambda item: item["score"], reverse=True)
    return peaks[:max_peaks]


def _rotate_model(model, angle_deg, scale=1.0):
    """对模板做真实几何旋转/缩放，并同步旋转梯度方向。"""
    if scale <= 0:
        return None
    h, w = model.shape
    center = ((w - 1) * 0.5, (h - 1) * 0.5)
    mat = cv2.getRotationMatrix2D(center, angle_deg, scale)
    abs_cos = abs(mat[0, 0])
    abs_sin = abs(mat[0, 1])
    bound_w = max(1, int(np.ceil(h * abs_sin + w * abs_cos)))
    bound_h = max(1, int(np.ceil(h * abs_cos + w * abs_sin)))
    mat[0, 2] += bound_w * 0.5 - center[0]
    mat[1, 2] += bound_h * 0.5 - center[1]

    edges_warp = cv2.warpAffine(
        model.edges_u8,
        mat,
        (bound_w, bound_h),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    edge_mask = edges_warp > 0
    if not np.any(edge_mask):
        return None

    cos_warp = cv2.warpAffine(
        model.cos_a,
        mat,
        (bound_w, bound_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    sin_warp = cv2.warpAffine(
        model.sin_a,
        mat,
        (bound_w, bound_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    rad = np.radians(angle_deg)
    c, s = np.float32(np.cos(rad)), np.float32(np.sin(rad))
    rot_cos = cos_warp * c - sin_warp * s
    rot_sin = cos_warp * s + sin_warp * c
    mag = np.sqrt(rot_cos * rot_cos + rot_sin * rot_sin)
    valid = edge_mask & (mag > _EPS)
    if not np.any(valid):
        return None

    rot_cos = np.where(valid, rot_cos / (mag + _EPS), 0).astype(np.float32)
    rot_sin = np.where(valid, rot_sin / (mag + _EPS), 0).astype(np.float32)
    edge_f = valid.astype(np.float32)
    num_pts = int(np.count_nonzero(valid))
    if num_pts == 0:
        return None

    return {
        "cos": rot_cos,
        "sin": rot_sin,
        "edges_f": edge_f,
        "shape": (bound_h, bound_w),
        "num_pts": num_pts,
        "center": (bound_w * 0.5, bound_h * 0.5),
        "rect_size": (max(1.0, model.w * scale), max(1.0, model.h * scale)),
        "angle": float(angle_deg),
        "scale": float(scale),
    }


def _prepare_source_maps(src_edg, src_cos, src_sin):
    """为匹配准备带微小容差的边缘与方向场，减轻栅格旋转带来的错位。"""
    src_edg_tol = cv2.dilate(src_edg.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32)
    src_cos_tol = cv2.GaussianBlur(src_cos, (5, 5), 0)
    src_sin_tol = cv2.GaussianBlur(src_sin, (5, 5), 0)
    mag = np.sqrt(src_cos_tol * src_cos_tol + src_sin_tol * src_sin_tol)
    src_cos_tol = np.where(mag > _EPS, src_cos_tol / (mag + _EPS), 0).astype(np.float32)
    src_sin_tol = np.where(mag > _EPS, src_sin_tol / (mag + _EPS), 0).astype(np.float32)
    return src_edg_tol, src_cos_tol, src_sin_tol


def _match_rotated_template(rotated, src_cos, src_sin, src_edg_f, min_overlap=0.3):
    """在单个旋转/缩放姿态下生成匹配得分图。"""
    tpl_h, tpl_w = rotated["shape"]
    src_h, src_w = src_cos.shape
    if tpl_h > src_h or tpl_w > src_w:
        return None

    s1 = cv2.matchTemplate(src_cos, rotated["cos"], cv2.TM_CCORR)
    s2 = cv2.matchTemplate(src_sin, rotated["sin"], cv2.TM_CCORR)
    dot_score = np.abs(s1 + s2)
    overlap = cv2.matchTemplate(src_edg_f, rotated["edges_f"], cv2.TM_CCORR)

    sm = np.zeros_like(dot_score, dtype=np.float32)
    valid = overlap >= float(rotated["num_pts"]) * float(min_overlap)
    if np.any(valid):
        mean_alignment = np.zeros_like(dot_score, dtype=np.float32)
        mean_alignment[valid] = dot_score[valid] / (overlap[valid] + _EPS)
        coverage = np.minimum(overlap / np.float32(rotated["num_pts"]), 1.0)
        sm[valid] = coverage[valid] * np.sqrt(np.clip(mean_alignment[valid], 0.0, 1.0))
    np.clip(sm, 0.0, 1.0, out=sm)
    return sm


def _rotated_rect_iou(candidate, other):
    rect_a = ((candidate["cx"], candidate["cy"]), candidate["rect_size"], candidate["angle"])
    rect_b = ((other["cx"], other["cy"]), other["rect_size"], other["angle"])
    inter_type, inter_pts = cv2.rotatedRectangleIntersection(rect_a, rect_b)
    if inter_type == cv2.INTERSECT_NONE or inter_pts is None or len(inter_pts) < 3:
        return 0.0
    inter_area = abs(cv2.contourArea(inter_pts))
    if inter_area <= 0:
        return 0.0
    area_a = max(candidate["rect_size"][0] * candidate["rect_size"][1], 1.0)
    area_b = max(other["rect_size"][0] * other["rect_size"][1], 1.0)
    denom = area_a + area_b - inter_area
    if denom <= 0:
        return 0.0
    return float(inter_area / denom)


def _suppress_candidates(candidates, max_matches, iou_thresh=0.25):
    filtered = []
    for cand in sorted(candidates, key=lambda item: item["score"], reverse=True):
        keep = True
        for chosen in filtered:
            dist = np.hypot(cand["cx"] - chosen["cx"], cand["cy"] - chosen["cy"])
            near_thresh = min(cand["rect_size"]) * 0.15
            if dist <= near_thresh or _rotated_rect_iou(cand, chosen) >= iou_thresh:
                keep = False
                break
        if keep:
            filtered.append(cand)
            if len(filtered) >= max_matches:
                break
    return filtered


class ShapeModel:
    """轻量级形状模板模型。"""
    def __init__(self, img, low=50, high=150):
        self.edges, self.cos_a, self.sin_a = _edge_map(img, low, high)
        self.h, self.w = self.edges.shape
        self.num_pts = int(np.sum(self.edges))
        self.edges_u8 = self.edges.astype(np.uint8) * 255

    @property
    def shape(self):
        return (self.h, self.w)


def find_shape_match(img, model, angle_step=5, min_score=0.4, max_matches=5,
                     scale_range=None, min_overlap=0.3):
    if model is None or model.num_pts == 0:
        return []
    src_edg, src_cos, src_sin = _edge_map(img)
    src_edg_f, src_cos, src_sin = _prepare_source_maps(src_edg, src_cos, src_sin)
    if scale_range is None:
        scale_range = (1.0,)
    angle_step = max(int(angle_step), 1)
    angles = np.arange(0, 360, angle_step, dtype=np.float32)
    results = []
    for scale in scale_range:
        for deg in angles:
            rotated = _rotate_model(model, float(deg), float(scale))
            if rotated is None:
                continue
            sm = _match_rotated_template(rotated, src_cos, src_sin, src_edg_f, min_overlap=min_overlap)
            if sm is None:
                continue
            for peak in _local_maxima(sm, min_score):
                results.append({
                    "x": peak["x"],
                    "y": peak["y"],
                    "cx": peak["x"] + rotated["center"][0],
                    "cy": peak["y"] + rotated["center"][1],
                    "angle": rotated["angle"],
                    "scale": rotated["scale"],
                    "score": peak["score"],
                    "rect_size": rotated["rect_size"],
                    "canvas_size": (rotated["shape"][1], rotated["shape"][0]),
                })
    return _suppress_candidates(results, max_matches)


class ShapeTemplateMatchingNode(Base64MatchingNodeData, OpenCVNodeDataBase, ITemplateMatchingGroupableNode):
    __group__ = "模板匹配模块"
    template_image = Property("", name="模板图片", group=PropertyGroupNames.RUN_PARAMETERS,
                              editor="crop", order=1000)
    angle_step = Property(10, name="角度步长", group=PropertyGroupNames.RUN_PARAMETERS, min_val=2, max_val=30)
    min_scale = Property(100, name="最小缩放(%)", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=50, max_val=200, step=5)
    max_scale = Property(100, name="最大缩放(%)", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=50, max_val=200, step=5)
    scale_step = Property(10, name="缩放步长(%)", group=PropertyGroupNames.RUN_PARAMETERS,
                          min_val=1, max_val=50, step=1)
    min_score = Property(50, name="最低分数", group=PropertyGroupNames.RUN_PARAMETERS,
                         min_val=0, max_val=100, step=5)
    min_overlap = Property(30, name="最小重叠(%)", group=PropertyGroupNames.RUN_PARAMETERS,
                           min_val=10, max_val=100, step=5)
    max_matches = Property(3, name="最大匹配数", group=PropertyGroupNames.RUN_PARAMETERS, min_val=1, max_val=100)
    matching_count_result = Property(0, name="匹配数量", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)
    confidence = Property(0.0, name="置信度(0-100)", group=PropertyGroupNames.RESULT_PARAMETERS, readonly=True)

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
            self._model = ShapeModel(template)
            self._model_b64 = self.base64_string
        if self._model.num_pts == 0:
            return self.ok(mat, "模板无边缘，请重新框选")

        # 大图缩放到 480px 加速（模板与搜索图同步缩放）
        h, w = mat.shape[:2]
        scale = 1.0
        if max(w, h) > 480:
            scale = 480.0 / max(w, h)
            mat_s = _safe_resize(mat, scale)
            # 重建模型以适应缩放后的尺度
            tpl_s = _safe_resize(template, scale)
            model = ShapeModel(tpl_s)
        else:
            mat_s = mat
            model = self._model

        scale_range = _generate_scales(self.min_scale, self.max_scale, self.scale_step)
        results = find_shape_match(
            mat_s,
            model,
            self.angle_step,
            self.min_score / 100.0,
            self.max_matches,
            scale_range=scale_range,
            min_overlap=self.min_overlap / 100.0,
        )

        out = mat.copy()
        best = 0.0
        for result in results:
            score = float(result["score"])
            sc = int(round(score * 100.0))
            best = max(best, float(sc))
            cx = float(result["cx"] / scale)
            cy = float(result["cy"] / scale)
            rect_w = float(result["rect_size"][0] / scale)
            rect_h = float(result["rect_size"][1] / scale)
            rect = ((cx, cy), (max(rect_w, 1.0), max(rect_h, 1.0)), float(result["angle"]))
            box = cv2.boxPoints(rect).astype(np.int32)
            cv2.polylines(out, [box], True, (0, 255, 0), 2)
            label_x = int(np.min(box[:, 0]))
            label_y = int(np.min(box[:, 1])) - 5
            label_y = max(label_y, 15)
            cv2.putText(out, f"{sc}% {result['angle']:.0f}° x{result['scale']:.2f}", (label_x, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        self.matching_count_result = len(results)
        self.confidence = best
        return self.ok(out, f"匹配 {len(results)} 处 (最高: {best:.0f})")

    def _update_result_image_source(self):
        self._result_image_source = self._mat

    def is_valid(self, mat):
        return mat is not None and mat.size > 0
