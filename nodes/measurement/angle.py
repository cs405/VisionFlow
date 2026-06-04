"""
角度测量节点 - 计算三点之间的角度
"""

import cv2
import numpy as np
from typing import Any, Dict, List, Tuple, Optional

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class AngleNode(NodeBase):
    """
    角度测量节点
    计算图像中三点之间的角度（顶点为中间点）
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "角度测量"
        self.category = "测量"
        self.description = "计算三点之间的角度"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像"),
            Socket("points", DataType.ROI_LIST, is_input=True, description="点列表（可选，需3个点）")
        ]
        self.output_sockets = [
            Socket("angle", DataType.NUMBER, is_input=False, description="计算的角度"),
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
                default=200,
                min=0,
                max=2000,
                step=1
            ),
            "vertex_x": NodeParameter(
                name="vertex_x",
                label="顶点 X坐标",
                type=ParamType.SLIDER,
                default=150,
                min=0,
                max=2000,
                step=1
            ),
            "vertex_y": NodeParameter(
                name="vertex_y",
                label="顶点 Y坐标",
                type=ParamType.SLIDER,
                default=150,
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
                default=200,
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
            "draw_lines": NodeParameter(
                name="draw_lines",
                label="绘制射线",
                type=ParamType.BOOL,
                default=True
            ),
            "draw_arc": NodeParameter(
                name="draw_arc",
                label="绘制角度弧线",
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
                label="线条颜色",
                type=ParamType.ENUM,
                default="green",
                options=["red", "green", "blue", "yellow", "cyan", "magenta"]
            ),
            "angle_color": NodeParameter(
                name="angle_color",
                label="角度弧线颜色",
                type=ParamType.ENUM,
                default="yellow",
                options=["red", "green", "blue", "yellow", "cyan", "magenta"]
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

        # 缓存点坐标
        self._point1 = None
        self._vertex = None
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

    def _extract_points_from_input(self, points_input) -> List[Tuple[int, int]]:
        """从输入数据中提取点坐标"""
        points = []

        if points_input is None:
            return points

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

    def _calculate_angle(self, p1: Tuple[int, int],
                         vertex: Tuple[int, int],
                         p2: Tuple[int, int]) -> float:
        """
        计算三点之间的角度
        vertex是角的顶点
        返回角度（度数，0-180）
        """
        # 计算向量
        v1 = (p1[0] - vertex[0], p1[1] - vertex[1])
        v2 = (p2[0] - vertex[0], p2[1] - vertex[1])

        # 计算点积
        dot_product = v1[0] * v2[0] + v1[1] * v2[1]

        # 计算模长
        norm1 = np.sqrt(v1[0] ** 2 + v1[1] ** 2)
        norm2 = np.sqrt(v2[0] ** 2 + v2[1] ** 2)

        if norm1 == 0 or norm2 == 0:
            return 0

        # 计算角度（弧度）
        cos_angle = dot_product / (norm1 * norm2)
        cos_angle = max(-1.0, min(1.0, cos_angle))  # 限制范围

        angle_rad = np.arccos(cos_angle)
        angle_deg = angle_rad * 180.0 / np.pi

        return angle_deg

    def _draw_angle_arc(self, img, vertex: Tuple[int, int],
                        p1: Tuple[int, int], p2: Tuple[int, int],
                        angle: float, radius: int, color: Tuple[int, int, int]):
        """绘制角度弧线"""
        # 计算起始和结束角度
        v1 = (p1[0] - vertex[0], p1[1] - vertex[1])
        v2 = (p2[0] - vertex[0], p2[1] - vertex[1])

        # 计算向量角度
        angle1 = np.arctan2(v1[1], v1[0]) * 180 / np.pi
        angle2 = np.arctan2(v2[1], v2[0]) * 180 / np.pi

        # 确保起始角度小于结束角度
        if angle1 > angle2:
            angle1, angle2 = angle2, angle1

        # 如果角度差大于180，调整
        if angle2 - angle1 > 180:
            angle1, angle2 = angle2, angle1
            angle1 += 360

        # 绘制弧线
        center = (int(vertex[0]), int(vertex[1]))
        axes = (radius, radius)

        # 使用椭圆绘制弧线
        cv2.ellipse(img, center, axes, 0, angle1, angle2, color, 2)

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        points_input = inputs.get("points")

        # 获取点坐标
        use_input_points = self.get_param("use_input_points")

        if use_input_points and points_input is not None:
            points = self._extract_points_from_input(points_input)
            if len(points) >= 3:
                self._point1 = points[0]
                self._vertex = points[1]
                self._point2 = points[2]
            else:
                return {
                    "angle": 0,
                    "debug_image": img.copy() if img is not None else None,
                    "info": "输入点不足3个"
                }
        else:
            # 使用参数中的坐标
            self._point1 = (self.get_param("point1_x"), self.get_param("point1_y"))
            self._vertex = (self.get_param("vertex_x"), self.get_param("vertex_y"))
            self._point2 = (self.get_param("point2_x"), self.get_param("point2_y"))

        if self._point1 is None or self._vertex is None or self._point2 is None:
            return {
                "angle": 0,
                "debug_image": img.copy() if img is not None else None,
                "info": "未设置测量点"
            }

        # 计算角度
        angle = self._calculate_angle(self._point1, self._vertex, self._point2)

        # 构建调试图像
        debug_img = None
        if img is not None:
            debug_img = img.copy()

            draw_lines = self.get_param("draw_lines")
            draw_arc = self.get_param("draw_arc")
            draw_points = self.get_param("draw_points")
            line_color = self._get_color(self.get_param("line_color"))
            angle_color = self._get_color(self.get_param("angle_color"))

            x1, y1 = self._point1
            vx, vy = self._vertex
            x2, y2 = self._point2

            # 绘制射线
            if draw_lines:
                cv2.line(debug_img, (x1, y1), (vx, vy), line_color, 2)
                cv2.line(debug_img, (x2, y2), (vx, vy), line_color, 2)

            # 绘制角度弧线
            if draw_arc:
                # 计算合适的弧线半径
                dist1 = np.sqrt((x1 - vx) ** 2 + (y1 - vy) ** 2)
                dist2 = np.sqrt((x2 - vx) ** 2 + (y2 - vy) ** 2)
                radius = min(dist1, dist2) * 0.3
                radius = int(max(20, min(80, radius)))
                self._draw_angle_arc(debug_img, self._vertex, self._point1,
                                     self._point2, angle, radius, angle_color)

            # 绘制点标记
            if draw_points:
                cv2.circle(debug_img, (x1, y1), 5, line_color, -1)
                cv2.circle(debug_img, (vx, vy), 6, line_color, -1)
                cv2.circle(debug_img, (x2, y2), 5, line_color, -1)

            # 显示角度文本
            text_x = vx + 20
            text_y = vy - 10
            text = f"{angle:.1f}°"
            cv2.putText(debug_img, text, (text_x, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, angle_color, 2)

        info = f"顶点: ({vx}, {vy}) | 点1: ({x1}, {y1}) | 点2: ({x2}, {y2}) | 角度: {angle:.1f}°"

        return {
            "angle": angle,
            "debug_image": debug_img,
            "info": info
        }