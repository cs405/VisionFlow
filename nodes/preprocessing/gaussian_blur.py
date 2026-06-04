"""
高斯模糊节点 - 图像平滑处理
"""

import cv2
from typing import Any, Dict

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class GaussianBlurNode(NodeBase):
    """
    高斯模糊节点
    使用高斯滤波器平滑图像
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "高斯模糊"
        self.category = "预处理"
        self.description = "使用高斯滤波器平滑图像"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("image", DataType.IMAGE, is_input=False, description="输出图像"),
            Socket("info", DataType.STRING, is_input=False, description="参数信息")
        ]

        # 参数
        self.parameters = {
            "kernel_size": NodeParameter(
                name="kernel_size",
                label="核大小",
                type=ParamType.SLIDER,
                default=5,
                min=1,
                max=31,
                step=2
            ),
            "sigma": NodeParameter(
                name="sigma",
                label="Sigma",
                type=ParamType.FLOAT_SLIDER,
                default=0,
                min=0,
                max=10,
                step=0.1
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"image": None, "info": "无输入图像"}

        ksize = self.get_param("kernel_size")
        sigma = self.get_param("sigma")

        # 确保核大小为奇数
        if ksize % 2 == 0:
            ksize += 1

        # 高斯模糊
        if sigma <= 0:
            result = cv2.GaussianBlur(img, (ksize, ksize), 0)
        else:
            result = cv2.GaussianBlur(img, (ksize, ksize), sigma)

        info = f"核大小: {ksize}x{ksize}, Sigma: {sigma if sigma > 0 else '自动'}"

        return {"image": result, "info": info}