"""
Vision Matching DLLs — 五个算法的 Python ctypes 封装。

使用方法:
    import numpy as np
    from vision_dll import edge_match, shape_context, chamfer_match, sad_match, ncc_match

    img = np.asarray(cv2.imread("target.png", 0))   # uint8, (H, W)
    tpl = np.asarray(cv2.imread("template.png", 0))  # uint8, (H, W)

    results, ms = edge_match(img, tpl, tpl_canny_low=250, tpl_canny_high=200,
                             match_threshold=0.9, min_score=0.7, angle_step=5)

每个函数返回 (list[dict], float): (匹配结果列表, 耗时毫秒)。
每个匹配结果 dict: {"x": float, "y": float, "angle": float, "score": float}
"""

import ctypes, os, numpy as np

_dll_dir = os.path.dirname(os.path.abspath(__file__))


class _EdgeResult(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float),
                ("angle", ctypes.c_float), ("score", ctypes.c_float)]

class _ShapeResult(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float),
                ("angle", ctypes.c_float), ("score", ctypes.c_float), ("scale", ctypes.c_float)]

class _ChamferResult(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float),
                ("angle", ctypes.c_float), ("score", ctypes.c_float)]

class _SADResult(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float),
                ("angle", ctypes.c_float), ("score", ctypes.c_float)]

class _NCCResult(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float),
                ("angle", ctypes.c_float), ("score", ctypes.c_float)]


def _load(name):
    dll = ctypes.CDLL(os.path.join(_dll_dir, name))
    # ensure numpy array is contiguous uint8
    def _check(arr):
        a = np.ascontiguousarray(arr)
        if a.dtype != np.uint8:
            a = a.astype(np.uint8)
        return a
    return dll, _check


# ========================================================================
# edge_match — 算法10.4 边缘梯度匹配
# ========================================================================
def edge_match(img: np.ndarray, tpl: np.ndarray,
               tpl_canny_low: float = 250, tpl_canny_high: float = 200,
               match_threshold: float = 0.9, min_score: float = 0.7,
               angle_start: float = -180, angle_end: float = 180,
               angle_step: float = 5, max_results: int = 200):
    """
    边缘梯度匹配 — Canny提取模板边缘 + Sobel梯度 + 滑动窗口点积相似度。

    ---------- 参数 ----------
    img, tpl : np.ndarray (uint8, H×W)
        目标图像 和 模板图像，灰度图，值范围 0~255。
    tpl_canny_low, tpl_canny_high : float
        Canny 边缘检测的高低阈值。
        (50, 150) → 模板标准边缘（~752点），匹配全面但较慢。
        (250, 200) → 只保留强边缘（~200点），速度快，适合PCB等对比度高的场景。
    match_threshold : float [0.1~0.9]
        提前终止阈值。滑动窗口时，处理完一部分边缘点后，如果剩余点数即使全部满分
        也无法达标，就提前跳过该位置。
        0.1 = 几乎不跳过，最慢，匹配最全。
        0.5 = 平衡。
        0.9 = 激进跳过大部位置，最快，但可能漏掉低分目标。
    min_score : float [0.0~1.0]
        最低匹配分数。只有分数 ≥ 该值的位置才被保留。
        0.5 = 只保留中等以上匹配。
        0.7 = 只保留强匹配，框更少。
        0.3 = 保留较多候选（可能有误检）。
    angle_start, angle_end : float
        旋转搜索范围（度）。(-180, 180) = 全角度搜索。
    angle_step : float
        角度步长（度）。5° = 精细（每5°搜一次），10° = 快速。
    max_results : int
        最多返回多少个匹配结果。

    ---------- 返回 ----------
    (results, elapsed_ms)
    results: list[dict], 每个 dict: {"x":中心x, "y":中心y, "angle":角度°, "score":分数0~1}
    elapsed_ms: float, 耗时毫秒
    """
    dll, check = _load("edge_match.dll")
    dll.edge_match_dll.restype = ctypes.c_int
    dll.edge_match_dll.argtypes = [
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
        ctypes.c_float, ctypes.c_float, ctypes.c_float,
        ctypes.POINTER(_EdgeResult), ctypes.c_int,
        ctypes.POINTER(ctypes.c_double)]
    img, tpl = check(img), check(tpl)
    buf = (_EdgeResult * max_results)()
    ms = ctypes.c_double(0)
    n = dll.edge_match_dll(
        img.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), img.shape[1], img.shape[0],
        tpl.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), tpl.shape[1], tpl.shape[0],
        tpl_canny_low, tpl_canny_high, match_threshold, min_score,
        angle_start, angle_end, angle_step,
        buf, max_results, ctypes.byref(ms))
    return [{"x": buf[i].x, "y": buf[i].y, "angle": buf[i].angle, "score": buf[i].score}
            for i in range(min(n, max_results))], ms.value


# ========================================================================
# shape_context — 算法10.5 形状上下文
# ========================================================================
def shape_context(img: np.ndarray, tpl: np.ndarray,
                  sample_step: int = 8, n_radial: int = 4, n_angular: int = 8,
                  min_score: float = 0.2, max_targets: int = 10,
                  max_results: int = 200):
    """
    形状上下文匹配 — 边缘点采样 + 对数极坐标直方图 + 最近邻匹配 + RANSAC。

    ---------- 参数 ----------
    sample_step : int
        边缘点采样间隔（像素）。
        5 = 密集采样，点数多，精度高，速度慢。
        15 = 稀疏采样，速度快，精度降低。
    n_radial, n_angular : int
        对数极坐标直方图 bin 数。默认 (4, 8) = 32维描述子。
    min_score : float [0.0~1.0]
        最低 RANSAC inlier 比例。0.2 = 宽松，0.5 = 严格。
    max_targets : int
        最多检出几个目标。
    """
    dll, check = _load("shape_context.dll")
    dll.shape_context_dll.restype = ctypes.c_int
    dll.shape_context_dll.argtypes = [
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_float, ctypes.c_int,
        ctypes.POINTER(_ShapeResult), ctypes.c_int,
        ctypes.POINTER(ctypes.c_double)]
    img, tpl = check(img), check(tpl)
    buf = (_ShapeResult * max_results)()
    ms = ctypes.c_double(0)
    n = dll.shape_context_dll(
        img.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), img.shape[1], img.shape[0],
        tpl.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), tpl.shape[1], tpl.shape[0],
        sample_step, n_radial, n_angular, min_score, max_targets,
        buf, max_results, ctypes.byref(ms))
    return [{"x": buf[i].x, "y": buf[i].y, "angle": buf[i].angle,
             "score": buf[i].score, "scale": buf[i].scale}
            for i in range(min(n, max_results))], ms.value


# ========================================================================
# chamfer_match — 算法10.3 Chamfer 距离
# ========================================================================
def chamfer_match(img: np.ndarray, tpl: np.ndarray,
                  tpl_canny_low: float = 50, tpl_canny_high: float = 150,
                  max_dist: float = 30, max_results: int = 200):
    """
    Chamfer 距离匹配 — Canny提取模板边缘点，计算目标距离变换，
    在模板边缘点位置累加距离值，取平均。分数 = 平均距离(px)，越低越好。

    ---------- 参数 ----------
    tpl_canny_low, tpl_canny_high : float
        模板 Canny 高低阈值。
    max_dist : float
        最大平均距离(像素)。匹配位置的 Chamfer 距离必须 ≤ 该值。
        10 = 严格匹配（框少但准）。
        30 = 宽松匹配（框多但可能有误检）。
    """
    dll, check = _load("chamfer_match.dll")
    dll.chamfer_match_dll.restype = ctypes.c_int
    dll.chamfer_match_dll.argtypes = [
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.c_float, ctypes.c_float, ctypes.c_float,
        ctypes.POINTER(_ChamferResult), ctypes.c_int,
        ctypes.POINTER(ctypes.c_double)]
    img, tpl = check(img), check(tpl)
    buf = (_ChamferResult * max_results)()
    ms = ctypes.c_double(0)
    n = dll.chamfer_match_dll(
        img.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), img.shape[1], img.shape[0],
        tpl.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), tpl.shape[1], tpl.shape[0],
        tpl_canny_low, tpl_canny_high, max_dist,
        buf, max_results, ctypes.byref(ms))
    return [{"x": buf[i].x, "y": buf[i].y, "angle": buf[i].angle, "score": buf[i].score}
            for i in range(min(n, max_results))], ms.value


# ========================================================================
# sad_match — 算法10.1 SAD 模板匹配
# ========================================================================
def sad_match(img: np.ndarray, tpl: np.ndarray,
              tpl_canny_low: float = 50, tpl_canny_high: float = 150,
              max_dist: float = 0.3, max_results: int = 200):
    """
    SAD 模板匹配 — 在模板边缘点位置计算 |目标像素值 - 模板像素值| 的平均值。
    分数 = 平均绝对像素差(归一化0~1)，越低越好。

    ---------- 参数 ----------
    tpl_canny_low, tpl_canny_high : float
        模板 Canny 高低阈值。
    max_dist : float [0.0~1.0]
        最大平均像素差。0.15 = 非常严格。0.3 = 平衡。0.5 = 宽松。
    """
    dll, check = _load("sad_match.dll")
    dll.sad_match_dll.restype = ctypes.c_int
    dll.sad_match_dll.argtypes = [
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.c_float, ctypes.c_float, ctypes.c_float,
        ctypes.POINTER(_SADResult), ctypes.c_int,
        ctypes.POINTER(ctypes.c_double)]
    img, tpl = check(img), check(tpl)
    buf = (_SADResult * max_results)()
    ms = ctypes.c_double(0)
    n = dll.sad_match_dll(
        img.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), img.shape[1], img.shape[0],
        tpl.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), tpl.shape[1], tpl.shape[0],
        tpl_canny_low, tpl_canny_high, max_dist,
        buf, max_results, ctypes.byref(ms))
    return [{"x": buf[i].x, "y": buf[i].y, "angle": buf[i].angle, "score": buf[i].score}
            for i in range(min(n, max_results))], ms.value


# ========================================================================
# ncc_match — 算法10.2 相关系数法
# ========================================================================
def ncc_match(img: np.ndarray, tpl: np.ndarray,
              tpl_canny_low: float = 50, tpl_canny_high: float = 150,
              min_score: float = 0.5, max_results: int = 200):
    """
    NCC 相关系数 — 在模板边缘点位置计算 Pearson 相关系数。
    分数范围 -1~1，1 = 完美匹配。

    ---------- 参数 ----------
    tpl_canny_low, tpl_canny_high : float
        模板 Canny 高低阈值。
    min_score : float [0.0~1.0]
        最低相关系数。0.3 = 宽松。0.5 = 平衡。0.7 = 严格。
    """
    dll, check = _load("ncc_match.dll")
    dll.ncc_match_dll.restype = ctypes.c_int
    dll.ncc_match_dll.argtypes = [
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int,
        ctypes.c_float, ctypes.c_float, ctypes.c_float,
        ctypes.POINTER(_NCCResult), ctypes.c_int,
        ctypes.POINTER(ctypes.c_double)]
    img, tpl = check(img), check(tpl)
    buf = (_NCCResult * max_results)()
    ms = ctypes.c_double(0)
    n = dll.ncc_match_dll(
        img.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), img.shape[1], img.shape[0],
        tpl.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), tpl.shape[1], tpl.shape[0],
        tpl_canny_low, tpl_canny_high, min_score,
        buf, max_results, ctypes.byref(ms))
    return [{"x": buf[i].x, "y": buf[i].y, "angle": buf[i].angle, "score": buf[i].score}
            for i in range(min(n, max_results))], ms.value
