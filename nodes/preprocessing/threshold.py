"""
阈值分割节点 - 图像二值化
"""

import cv2
from typing import Any, Dict

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class ThresholdNode(NodeBase):
    """
    阈值分割节点
    将灰度图像转换为二值图像
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "阈值分割"
        self.category = "预处理"
        self.description = "将灰度图像转换为二值图像"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("image", DataType.GRAY_IMAGE, is_input=False, description="输出二值图像"),
            Socket("info", DataType.STRING, is_input=False, description="阈值信息")
        ]

        # 参数
        self.parameters = {
            "method": NodeParameter(
                name="method",
                label="阈值方法",
                type=ParamType.ENUM,
                default="binary",
                options=["binary", "binary_inv", "trunc", "tozero", "tozero_inv",
                         "otsu", "adaptive_mean", "adaptive_gaussian"]
            ),
            "threshold": NodeParameter(
                name="threshold",
                label="阈值",
                type=ParamType.SLIDER,
                default=127,
                min=0,
                max=255
            ),
            "max_value": NodeParameter(
                name="max_value",
                label="最大值",
                type=ParamType.SLIDER,
                default=255,
                min=0,
                max=255
            ),
            "block_size": NodeParameter(
                name="block_size",
                label="块大小",
                type=ParamType.SLIDER,
                default=11,
                min=3,
                max=255,
                step=2
            ),
            "c": NodeParameter(
                name="c",
                label="常数C",
                type=ParamType.INT,
                default=2,
                min=-10,
                max=10
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"image": None, "info": "无输入图像"}

        # 转换为灰度图
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        method = self.get_param("method")
        thresh = self.get_param("threshold")
        max_val = self.get_param("max_value")
        block_size = self.get_param("block_size")
        c = self.get_param("c")

        # 确保块大小为奇数
        if block_size % 2 == 0:
            block_size += 1

        # 应用阈值方法
        if method in ["otsu"]:
            result, actual_thresh = cv2.threshold(gray, 0, max_val,
                                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            info = f"OTSU, 阈值: {actual_thresh:.1f}"
        elif method in ["adaptive_mean", "adaptive_gaussian"]:
            adaptive_method = cv2.ADAPTIVE_THRESH_MEAN_C if method == "adaptive_mean" else cv2.ADAPTIVE_THRESH_GAUSSIAN_C
            result = cv2.adaptiveThreshold(gray, max_val, adaptive_method,
                                           cv2.THRESH_BINARY, block_size, c)
            info = f"{method}, 块大小: {block_size}, C: {c}"
        else:
            # 标准阈值方法
            thresh_map = {
                "binary": cv2.THRESH_BINARY,
                "binary_inv": cv2.THRESH_BINARY_INV,
                "trunc": cv2.THRESH_TRUNC,
                "tozero": cv2.THRESH_TOZERO,
                "tozero_inv": cv2.THRESH_TOZERO_INV
            }
            thresh_type = thresh_map.get(method, cv2.THRESH_BINARY)
            result, actual_thresh = cv2.threshold(gray, thresh, max_val, thresh_type)
            info = f"{method}, 阈值: {thresh}"

        return {"image": result, "info": info}