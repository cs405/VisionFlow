"""
Canny边缘检测节点
"""

import cv2
from typing import Any, Dict

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class CannyNode(NodeBase):
    """
    Canny边缘检测节点
    使用Canny算法检测图像边缘
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "Canny边缘检测"
        self.category = "特征提取"
        self.description = "使用Canny算法检测图像边缘"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("edges", DataType.GRAY_IMAGE, is_input=False, description="边缘图像"),
            Socket("info", DataType.STRING, is_input=False, description="参数信息")
        ]

        # 参数
        self.parameters = {
            "threshold1": NodeParameter(
                name="threshold1",
                label="低阈值",
                type=ParamType.SLIDER,
                default=50,
                min=0,
                max=255
            ),
            "threshold2": NodeParameter(
                name="threshold2",
                label="高阈值",
                type=ParamType.SLIDER,
                default=150,
                min=0,
                max=255
            ),
            "aperture_size": NodeParameter(
                name="aperture_size",
                label="Sobel核大小",
                type=ParamType.ENUM,
                default=3,
                options=[3, 5, 7]
            ),
            "l2gradient": NodeParameter(
                name="l2gradient",
                label="L2梯度",
                type=ParamType.BOOL,
                default=False
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"edges": None, "info": "无输入图像"}

        # 转换为灰度图
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # 获取参数
        t1 = self.get_param("threshold1")
        t2 = self.get_param("threshold2")
        aperture = self.get_param("aperture_size")
        l2gradient = self.get_param("l2gradient")

        # Canny边缘检测
        edges = cv2.Canny(gray, t1, t2, apertureSize=aperture, L2gradient=l2gradient)

        info = f"阈值: {t1}/{t2}, Sobel核: {aperture}"

        return {"edges": edges, "info": info}