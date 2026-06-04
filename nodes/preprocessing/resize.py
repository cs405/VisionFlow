"""
图像缩放节点 - 调整图像尺寸
"""

import cv2
from typing import Any, Dict

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class ResizeNode(NodeBase):
    """
    图像缩放节点
    调整图像尺寸
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "图像缩放"
        self.category = "预处理"
        self.description = "调整图像尺寸"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("image", DataType.IMAGE, is_input=False, description="输出图像"),
            Socket("size", DataType.STRING, is_input=False, description="尺寸信息")
        ]

        # 参数
        self.parameters = {
            "mode": NodeParameter(
                name="mode",
                label="缩放模式",
                type=ParamType.ENUM,
                default="absolute",
                options=["absolute", "percent", "fit_to_width", "fit_to_height"]
            ),
            "width": NodeParameter(
                name="width",
                label="宽度",
                type=ParamType.INT,
                default=640,
                min=1,
                max=4096
            ),
            "height": NodeParameter(
                name="height",
                label="高度",
                type=ParamType.INT,
                default=480,
                min=1,
                max=4096
            ),
            "percent": NodeParameter(
                name="percent",
                label="百分比",
                type=ParamType.SLIDER,
                default=100,
                min=1,
                max=500
            ),
            "interpolation": NodeParameter(
                name="interpolation",
                label="插值方法",
                type=ParamType.ENUM,
                default="linear",
                options=["linear", "nearest", "cubic", "lanczos"]
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"image": None, "size": "无输入图像"}

        h, w = img.shape[:2]

        # 计算目标尺寸
        mode = self.get_param("mode")

        if mode == "absolute":
            target_w = self.get_param("width")
            target_h = self.get_param("height")
        elif mode == "percent":
            percent = self.get_param("percent") / 100
            target_w = int(w * percent)
            target_h = int(h * percent)
        elif mode == "fit_to_width":
            target_w = self.get_param("width")
            target_h = int(h * target_w / w)
        elif mode == "fit_to_height":
            target_h = self.get_param("height")
            target_w = int(w * target_h / h)
        else:
            target_w, target_h = w, h

        # 插值方法
        interp_map = {
            "linear": cv2.INTER_LINEAR,
            "nearest": cv2.INTER_NEAREST,
            "cubic": cv2.INTER_CUBIC,
            "lanczos": cv2.INTER_LANCZOS4
        }
        interpolation = interp_map.get(self.get_param("interpolation"), cv2.INTER_LINEAR)

        # 缩放
        result = cv2.resize(img, (target_w, target_h), interpolation=interpolation)

        size_info = f"{w}x{h} → {target_w}x{target_h}"

        return {"image": result, "size": size_info}