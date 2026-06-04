"""
霍夫圆检测节点 - 检测图像中的圆形
"""

import cv2
import numpy as np
from typing import Any, Dict, List

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class FindCirclesNode(NodeBase):
    """
    霍夫圆检测节点
    使用霍夫变换检测图像中的圆形
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "霍夫圆检测"
        self.category = "特征提取"
        self.description = "检测图像中的圆形"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("circles", DataType.ROI_LIST, is_input=False, description="圆列表"),
            Socket("debug_image", DataType.IMAGE, is_input=False, description="调试图像"),
            Socket("count", DataType.NUMBER, is_input=False, description="圆数量")
        ]

        # 参数
        self.parameters = {
            "dp": NodeParameter(
                name="dp",
                label="分辨率倒数",
                type=ParamType.FLOAT_SLIDER,
                default=1.0,
                min=0.5,
                max=2.0,
                step=0.1
            ),
            "min_dist": NodeParameter(
                name="min_dist",
                label="最小圆心距",
                type=ParamType.SLIDER,
                default=50,
                min=10,
                max=200,
                step=5
            ),
            "param1": NodeParameter(
                name="param1",
                label="Canny高阈值",
                type=ParamType.SLIDER,
                default=100,
                min=50,
                max=300,
                step=10
            ),
            "param2": NodeParameter(
                name="param2",
                label="圆心累加器阈值",
                type=ParamType.SLIDER,
                default=30,
                min=10,
                max=200,
                step=5
            ),
            "min_radius": NodeParameter(
                name="min_radius",
                label="最小半径",
                type=ParamType.SLIDER,
                default=10,
                min=5,
                max=100,
                step=5
            ),
            "max_radius": NodeParameter(
                name="max_radius",
                label="最大半径",
                type=ParamType.SLIDER,
                default=50,
                min=10,
                max=300,
                step=10
            ),
            "draw_circle": NodeParameter(
                name="draw_circle",
                label="绘制圆",
                type=ParamType.BOOL,
                default=True
            ),
            "draw_center": NodeParameter(
                name="draw_center",
                label="绘制圆心",
                type=ParamType.BOOL,
                default=True
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"circles": [], "debug_image": None, "count": 0}

        # 转换为灰度图
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # 获取参数
        dp = self.get_param("dp")
        min_dist = self.get_param("min_dist")
        param1 = self.get_param("param1")
        param2 = self.get_param("param2")
        min_radius = self.get_param("min_radius")
        max_radius = self.get_param("max_radius")

        # 霍夫圆检测
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp, min_dist,
            param1=param1, param2=param2,
            minRadius=min_radius, maxRadius=max_radius
        )

        # 解析结果
        circles_data = []
        debug_img = img.copy()

        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            for (x, y, r) in circles:
                circles_data.append({
                    "x": int(x),
                    "y": int(y),
                    "radius": int(r),
                    "area": float(np.pi * r * r),
                    "perimeter": float(2 * np.pi * r)
                })

                if self.get_param("draw_circle"):
                    cv2.circle(debug_img, (x, y), r, (0, 255, 0), 2)
                if self.get_param("draw_center"):
                    cv2.circle(debug_img, (x, y), 2, (0, 0, 255), 3)

        return {
            "circles": circles_data,
            "debug_image": debug_img,
            "count": len(circles_data)
        }