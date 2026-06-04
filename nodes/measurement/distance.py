"""
距离测量节点 - 计算两点之间的距离
"""

import cv2
import numpy as np
from typing import Any, Dict, List, Tuple, Optional

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class DistanceNode(NodeBase):
    """
    距离测量节点
    计算图像中两点之间的像素距离或实际距离
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "距离测量"
        self.category = "测量"
        self.description = "计算两点之间的距离"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像"),
            Socket("points", DataType.ROI_LIST, is_input=True, description="点列表（可选）")
        ]
        self.output_sockets = [
            Socket("distance", DataType.NUMBER, is_input=False, description="计算的距离"),
            Socket("debug_image", DataType.IMAGE, is_input=False, description="调试图像"),
            Socket("info", DataType.STRING, is_input=False, description="测量信息")
        ]

        # 参数
        self.parameters = {
            "point1_x": NodeParameter(
                name="point1_x",
                label="点1 X坐标",
                type=ParamType.SLIDER,
                default=100,
                min=0,
                max=2000,
                step=1
            ),
            "point1_y": NodeParameter(
                name="point1_y",
                label="点1 Y坐标",
                type=ParamType.SLIDER,
                default=100,
                min=0,
                max=2000,
                step=1
            ),
            "point2_x": NodeParameter(
                name="point2_x",
                label="点2 X坐标",
                type=ParamType.SLIDER,
                default=200,
                min=0,
                max=2000,
                step=1
            ),
            "point2_y": NodeParameter(
                name="point2_y",
                label="点2 Y坐标",
                type=ParamType.SLIDER,
                default=100,
                min=0,
                max=2000,
                step=1
            ),
            "use_input_points": NodeParameter(
                name="use_input_points",
                label="使用输入点",
                type=ParamType.BOOL,
                default=False
            ),
            "calibration_pixel_per_mm": NodeParameter(
                name="calibration_pixel_per_mm",
                label="像素/毫米比例",
                type=ParamType.FLOAT_SLIDER,
                default=1.0,
                min=0.1,
                max=100.0,
                step=0.1
            ),
            "unit": NodeParameter(
                name="unit",
                label="显示单位",
                type=ParamType.ENUM,
                default="px",
                options=["px", "mm", "cm"]
            ),
            "draw_line": NodeParameter(
                name="draw_line",
                label="绘制连线",
                type=ParamType.BOOL,
                default=True
            ),
            "draw_points": NodeParameter(
                name="draw_points",
                label="绘制点标记",
                type=ParamType.BOOL,
                default=True
            ),
            "line_color": NodeParameter(
                name="line_color",
                label="连线颜色",
                type=ParamType.ENUM,
                default="green",
                options=["red", "green", "blue", "yellow", "cyan", "magenta"]
            ),
            "point_color": NodeParameter(
                name="point_color",
                label="点颜色",
                type=ParamType.ENUM,
                default="red",
                options=["red", "green", "blue", "yellow", "cyan", "magenta"]
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

        # 缓存点坐标
        self._point1 = None
        self._point2 = None

    def _get_color(self, color_name: str) -> Tuple[int, int, int]:
        """获取BGR颜色值"""
        color_map = {
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "blue": (255, 0, 0),
            "yellow": (0, 255, 255),
            "cyan": (255, 255, 0),
            "magenta": (255, 0, 255)
        }
        return color_map.get(color_name, (0, 255, 0))

    def _get_unit_multiplier(self, unit: str) -> float:
        """获取单位转换系数"""
        if unit == "mm":
            return 1.0
        elif unit == "cm":
            return 0.1
        else:
            return 1.0

    def _get_unit_label(self, unit: str) -> str:
        """获取单位标签"""
        if unit == "mm":
            return "mm"
        elif unit == "cm":
            return "cm"
        else:
            return "pixels"

    def _extract_points_from_input(self, points_input) -> List[Tuple[int, int]]:
        """从输入数据中提取点坐标"""
        points = []

        if points_input is None:
            return points

        # 处理不同的输入格式
        if isinstance(points_input, list):
            for item in points_input:
                if isinstance(item, dict):
                    if "x" in item and "y" in item:
                        points.append((int(item["x"]), int(item["y"])))
                    elif "point" in item:
                        p = item["point"]
                        points.append((int(p[0]), int(p[1])))
                elif isinstance(item, (tuple, list)) and len(item) >= 2:
                    points.append((int(item[0]), int(item[1])))

        return points

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        points_input = inputs.get("points")

        # 获取点坐标
        use_input_points = self.get_param("use_input_points")

        if use_input_points and points_input is not None:
            points = self._extract_points_from_input(points_input)
            if len(points) >= 2:
                self._point1 = points[0]
                self._point2 = points[1]
            else:
                return {
                    "distance": 0,
                    "debug_image": img.copy() if img is not None else None,
                    "info": "输入点不足2个"
                }
        else:
            # 使用参数中的坐标
            self._point1 = (self.get_param("point1_x"), self.get_param("point1_y"))
            self._point2 = (self.get_param("point2_x"), self.get_param("point2_y"))

        if self._point1 is None or self._point2 is None:
            return {
                "distance": 0,
                "debug_image": img.copy() if img is not None else None,
                "info": "未设置测量点"
            }

        # 计算像素距离
        x1, y1 = self._point1
        x2, y2 = self._point2
        pixel_distance = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        # 应用标定系数
        calibration = self.get_param("calibration_pixel_per_mm")
        unit = self.get_param("unit")
        unit_multiplier = self._get_unit_multiplier(unit)

        if unit == "px":
            actual_distance = pixel_distance
        else:
            actual_distance = pixel_distance / calibration * unit_multiplier

        # 构建调试图像
        debug_img = None
        if img is not None:
            debug_img = img.copy()

            draw_line = self.get_param("draw_line")
            draw_points = self.get_param("draw_points")
            line_color = self._get_color(self.get_param("line_color"))
            point_color = self._get_color(self.get_param("point_color"))

            # 绘制连线
            if draw_line:
                cv2.line(debug_img, (x1, y1), (x2, y2), line_color, 2)

            # 绘制点标记
            if draw_points:
                cv2.circle(debug_img, (x1, y1), 5, point_color, -1)
                cv2.circle(debug_img, (x2, y2), 5, point_color, -1)

            # 显示距离文本
            mid_x = (x1 + x2) // 2
            mid_y = (y1 + y2) // 2
            unit_label = self._get_unit_label(unit)
            text = f"{actual_distance:.2f} {unit_label}"
            cv2.putText(debug_img, text, (mid_x - 30, mid_y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, line_color, 2)

        info = f"点1: ({x1}, {y1}) | 点2: ({x2}, {y2}) | 距离: {actual_distance:.2f} {unit_label}"

        return {
            "distance": actual_distance,
            "debug_image": debug_img,
            "info": info
        }