"""
霍夫线检测节点 - 检测图像中的直线
"""

import cv2
import numpy as np
from typing import Any, Dict, List

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class FindLinesNode(NodeBase):
    """
    霍夫线检测节点
    使用霍夫变换检测图像中的直线
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "霍夫线检测"
        self.category = "特征提取"
        self.description = "检测图像中的直线"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像（边缘图）")
        ]
        self.output_sockets = [
            Socket("lines", DataType.ROI_LIST, is_input=False, description="直线列表"),
            Socket("debug_image", DataType.IMAGE, is_input=False, description="调试图像"),
            Socket("count", DataType.NUMBER, is_input=False, description="直线数量")
        ]

        # 参数
        self.parameters = {
            "method": NodeParameter(
                name="method",
                label="检测方法",
                type=ParamType.ENUM,
                default="standard",
                options=["standard", "probabilistic"]
            ),
            "rho": NodeParameter(
                name="rho",
                label="距离精度(像素)",
                type=ParamType.FLOAT_SLIDER,
                default=1.0,
                min=0.5,
                max=10.0,
                step=0.5
            ),
            "theta": NodeParameter(
                name="theta",
                label="角度精度(度)",
                type=ParamType.FLOAT_SLIDER,
                default=1.0,
                min=0.5,
                max=10.0,
                step=0.5
            ),
            "threshold": NodeParameter(
                name="threshold",
                label="累加器阈值",
                type=ParamType.SLIDER,
                default=100,
                min=10,
                max=300,
                step=10
            ),
            "min_line_length": NodeParameter(
                name="min_line_length",
                label="最小线长度",
                type=ParamType.SLIDER,
                default=50,
                min=10,
                max=500,
                step=10
            ),
            "max_line_gap": NodeParameter(
                name="max_line_gap",
                label="最大线段间隙",
                type=ParamType.SLIDER,
                default=10,
                min=1,
                max=100,
                step=5
            ),
            "draw_lines": NodeParameter(
                name="draw_lines",
                label="绘制直线",
                type=ParamType.BOOL,
                default=True
            ),
            "line_color": NodeParameter(
                name="line_color",
                label="直线颜色",
                type=ParamType.ENUM,
                default="green",
                options=["red", "green", "blue", "yellow", "cyan", "magenta"]
            ),
            "line_thickness": NodeParameter(
                name="line_thickness",
                label="线宽",
                type=ParamType.SLIDER,
                default=2,
                min=1,
                max=5
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def _to_radians(self, degrees: float) -> float:
        """角度转弧度"""
        return degrees * np.pi / 180.0

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"lines": [], "debug_image": None, "count": 0}

        # 转换为灰度图（如果是彩色图）
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # 获取参数
        method = self.get_param("method")
        rho = self.get_param("rho")
        theta_deg = self.get_param("theta")
        theta = self._to_radians(theta_deg)
        threshold = self.get_param("threshold")
        min_line_length = self.get_param("min_line_length")
        max_line_gap = self.get_param("max_line_gap")
        draw_lines = self.get_param("draw_lines")
        line_thickness = self.get_param("line_thickness")

        # 颜色映射
        color_map = {
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "blue": (255, 0, 0),
            "yellow": (0, 255, 255),
            "cyan": (255, 255, 0),
            "magenta": (255, 0, 255)
        }
        color = color_map.get(self.get_param("line_color"), (0, 255, 0))

        lines_data = []
        debug_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) if len(gray.shape) == 2 else img.copy()

        if method == "standard":
            # 标准霍夫线检测
            lines = cv2.HoughLines(gray, rho, theta, threshold)

            if lines is not None:
                for line in lines:
                    rho_val, theta_val = line[0]
                    a = np.cos(theta_val)
                    b = np.sin(theta_val)
                    x0 = a * rho_val
                    y0 = b * rho_val
                    x1 = int(x0 + 1000 * (-b))
                    y1 = int(y0 + 1000 * (a))
                    x2 = int(x0 - 1000 * (-b))
                    y2 = int(y0 - 1000 * (a))

                    lines_data.append({
                        "type": "standard",
                        "rho": float(rho_val),
                        "theta": float(theta_val),
                        "theta_deg": float(theta_val * 180 / np.pi),
                        "start_point": (x1, y1),
                        "end_point": (x2, y2)
                    })

                    if draw_lines:
                        cv2.line(debug_img, (x1, y1), (x2, y2), color, line_thickness)

        else:  # probabilistic
            # 概率霍夫线检测
            lines = cv2.HoughLinesP(
                gray, rho, theta, threshold,
                minLineLength=min_line_length,
                maxLineGap=max_line_gap
            )

            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]

                    # 计算直线参数
                    length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi

                    lines_data.append({
                        "type": "probabilistic",
                        "start_point": (int(x1), int(y1)),
                        "end_point": (int(x2), int(y2)),
                        "length": float(length),
                        "angle": float(angle)
                    })

                    if draw_lines:
                        cv2.line(debug_img, (x1, y1), (x2, y2), color, line_thickness)

        return {
            "lines": lines_data,
            "debug_image": debug_img,
            "count": len(lines_data)
        }