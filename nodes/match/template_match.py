"""
模板匹配节点 - 在图像中查找模板
"""

import cv2
import numpy as np
from typing import Any, Dict, List, Tuple

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class TemplateMatchNode(NodeBase):
    """
    模板匹配节点
    在输入图像中查找模板图像的位置
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "模板匹配"
        self.category = "匹配"
        self.description = "在图像中查找模板"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像"),
            Socket("template", DataType.IMAGE, is_input=True, description="模板图像")
        ]
        self.output_sockets = [
            Socket("matches", DataType.ROI_LIST, is_input=False, description="匹配结果"),
            Socket("debug_image", DataType.IMAGE, is_input=False, description="调试图像"),
            Socket("best_score", DataType.NUMBER, is_input=False, description="最佳匹配分数")
        ]

        # 参数
        self.parameters = {
            "method": NodeParameter(
                name="method",
                label="匹配方法",
                type=ParamType.ENUM,
                default="ccoeff_normed",
                options=["sqdiff", "sqdiff_normed", "ccorr", "ccorr_normed",
                         "ccoeff", "ccoeff_normed"]
            ),
            "threshold": NodeParameter(
                name="threshold",
                label="匹配阈值",
                type=ParamType.FLOAT_SLIDER,
                default=0.7,
                min=0,
                max=1,
                step=0.01
            ),
            "max_matches": NodeParameter(
                name="max_matches",
                label="最大匹配数",
                type=ParamType.SLIDER,
                default=1,
                min=1,
                max=10
            ),
            "draw_rect": NodeParameter(
                name="draw_rect",
                label="绘制矩形",
                type=ParamType.BOOL,
                default=True
            ),
            "draw_score": NodeParameter(
                name="draw_score",
                label="显示分数",
                type=ParamType.BOOL,
                default=True
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        template = inputs.get("template")

        if img is None:
            return {"matches": [], "debug_image": None, "best_score": 0}

        if template is None:
            return {"matches": [], "debug_image": img.copy(), "best_score": 0}

        # 转换为灰度图
        if len(img.shape) == 3:
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = img.copy()

        if len(template.shape) == 3:
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            template_gray = template.copy()

        h, w = template_gray.shape

        # 匹配方法
        method_map = {
            "sqdiff": cv2.TM_SQDIFF,
            "sqdiff_normed": cv2.TM_SQDIFF_NORMED,
            "ccorr": cv2.TM_CCORR,
            "ccorr_normed": cv2.TM_CCORR_NORMED,
            "ccoeff": cv2.TM_CCOEFF,
            "ccoeff_normed": cv2.TM_CCOEFF_NORMED
        }
        method = method_map.get(self.get_param("method"), cv2.TM_CCOEFF_NORMED)
        threshold = self.get_param("threshold")
        max_matches = self.get_param("max_matches")

        # 执行模板匹配
        result = cv2.matchTemplate(img_gray, template_gray, method)

        # 查找匹配位置
        matches = []
        debug_img = img.copy()

        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            # 对于SQDIFF，值越小表示匹配越好
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            best_score = 1 - max_val if method == cv2.TM_SQDIFF_NORMED else 1 / (1 + max_val)
        else:
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            best_score = max_val

        # 使用阈值过滤
        locations = []
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            locations = np.where(result <= threshold)
            # 转换分数
            if method == cv2.TM_SQDIFF_NORMED:
                scores = 1 - result[locations]
            else:
                scores = 1 / (1 + result[locations])
        else:
            locations = np.where(result >= threshold)
            scores = result[locations]

        # 整理匹配结果
        matches_list = []
        for pt in zip(*locations[::-1]):
            matches_list.append({
                "x": int(pt[0]),
                "y": int(pt[1]),
                "width": w,
                "height": h,
                "score": float(scores[0] if isinstance(scores, np.ndarray) else scores),
                "center_x": int(pt[0] + w / 2),
                "center_y": int(pt[1] + h / 2)
            })

        # 按分数排序并限制数量
        matches_list.sort(key=lambda x: x["score"], reverse=True)
        matches_list = matches_list[:max_matches]

        # 绘制结果
        for match in matches_list:
            if self.get_param("draw_rect"):
                cv2.rectangle(debug_img,
                              (match["x"], match["y"]),
                              (match["x"] + w, match["y"] + h),
                              (0, 255, 0), 2)
            if self.get_param("draw_score"):
                cv2.putText(debug_img,
                            f"{match['score']:.2f}",
                            (match["x"], match["y"] - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        best_score = matches_list[0]["score"] if matches_list else 0

        return {
            "matches": matches_list,
            "debug_image": debug_img,
            "best_score": best_score
        }