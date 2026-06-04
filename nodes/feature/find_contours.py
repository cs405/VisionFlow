"""
轮廓检测节点
"""

import cv2
import numpy as np
from typing import Any, Dict, List

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class FindContoursNode(NodeBase):
    """
    轮廓检测节点
    查找图像中的轮廓
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "轮廓检测"
        self.category = "特征提取"
        self.description = "查找图像中的轮廓"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入二值图像")
        ]
        self.output_sockets = [
            Socket("contours", DataType.ROI_LIST, is_input=False, description="轮廓列表"),
            Socket("debug_image", DataType.IMAGE, is_input=False, description="调试图像"),
            Socket("count", DataType.NUMBER, is_input=False, description="轮廓数量")
        ]

        # 参数
        self.parameters = {
            "mode": NodeParameter(
                name="mode",
                label="检索模式",
                type=ParamType.ENUM,
                default="external",
                options=["external", "list", "tree", "ccomp"]
            ),
            "method": NodeParameter(
                name="method",
                label="近似方法",
                type=ParamType.ENUM,
                default="simple",
                options=["simple", "none", "approx_tc89_l1", "approx_tc89_kcos"]
            ),
            "draw_color": NodeParameter(
                name="draw_color",
                label="绘制颜色",
                type=ParamType.ENUM,
                default="green",
                options=["red", "green", "blue", "yellow", "cyan", "magenta"]
            ),
            "min_area": NodeParameter(
                name="min_area",
                label="最小面积",
                type=ParamType.SLIDER,
                default=100,
                min=0,
                max=10000
            ),
            "max_area": NodeParameter(
                name="max_area",
                label="最大面积",
                type=ParamType.SLIDER,
                default=100000,
                min=100,
                max=1000000
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"contours": [], "debug_image": None, "count": 0}

        # 转换为二值图像
        if len(img.shape) == 3:
            binary = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            binary = img.copy()

        # 轮廓检索模式
        mode_map = {
            "external": cv2.RETR_EXTERNAL,
            "list": cv2.RETR_LIST,
            "tree": cv2.RETR_TREE,
            "ccomp": cv2.RETR_CCOMP
        }

        # 轮廓近似方法
        method_map = {
            "simple": cv2.CHAIN_APPROX_SIMPLE,
            "none": cv2.CHAIN_APPROX_NONE,
            "approx_tc89_l1": cv2.CHAIN_APPROX_TC89_L1,
            "approx_tc89_kcos": cv2.CHAIN_APPROX_TC89_KCOS
        }

        mode = mode_map.get(self.get_param("mode"), cv2.RETR_EXTERNAL)
        method = method_map.get(self.get_param("method"), cv2.CHAIN_APPROX_SIMPLE)
        min_area = self.get_param("min_area")
        max_area = self.get_param("max_area")

        # 查找轮廓
        contours, hierarchy = cv2.findContours(binary, mode, method)

        # 按面积过滤
        filtered_contours = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_area <= area <= max_area:
                filtered_contours.append(cnt)

        # 颜色映射
        color_map = {
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "blue": (255, 0, 0),
            "yellow": (0, 255, 255),
            "cyan": (255, 255, 0),
            "magenta": (255, 0, 255)
        }
        color = color_map.get(self.get_param("draw_color"), (0, 255, 0))

        # 绘制调试图像
        debug_img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR) if len(binary.shape) == 2 else binary.copy()
        cv2.drawContours(debug_img, filtered_contours, -1, color, 2)

        # 转换轮廓为可序列化格式
        contours_data = []
        for cnt in filtered_contours:
            approx = cv2.approxPolyDP(cnt, 3, True)
            contours_data.append({
                "area": float(cv2.contourArea(cnt)),
                "perimeter": float(cv2.arcLength(cnt, True)),
                "points": approx.tolist(),
                "point_count": len(cnt)
            })

        return {
            "contours": contours_data,
            "debug_image": debug_img,
            "count": len(filtered_contours)
        }