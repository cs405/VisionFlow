"""
颜色转换节点 - 转换图像颜色空间
"""

import cv2
from typing import Any, Dict

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class CvtColorNode(NodeBase):
    """
    颜色转换节点
    转换图像颜色空间（BGR2GRAY, BGR2HSV等）
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "颜色转换"
        self.category = "预处理"
        self.description = "转换图像颜色空间"

        # 端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像")
        ]
        self.output_sockets = [
            Socket("image", DataType.IMAGE, is_input=False, description="输出图像"),
            Socket("info", DataType.STRING, is_input=False, description="转换信息")
        ]

        # 参数
        self.parameters = {
            "code": NodeParameter(
                name="code",
                label="转换类型",
                type=ParamType.ENUM,
                default="BGR2GRAY",
                options=["BGR2GRAY", "BGR2RGB", "BGR2HSV", "BGR2LAB",
                         "BGR2YUV", "GRAY2BGR", "HSV2BGR"]
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        if img is None:
            return {"image": None, "info": "无输入图像"}

        code_map = {
            "BGR2GRAY": cv2.COLOR_BGR2GRAY,
            "BGR2RGB": cv2.COLOR_BGR2RGB,
            "BGR2HSV": cv2.COLOR_BGR2HSV,
            "BGR2LAB": cv2.COLOR_BGR2LAB,
            "BGR2YUV": cv2.COLOR_BGR2YUV,
            "GRAY2BGR": cv2.COLOR_GRAY2BGR,
            "HSV2BGR": cv2.COLOR_HSV2BGR
        }

        code_name = self.get_param("code")
        code = code_map.get(code_name, cv2.COLOR_BGR2GRAY)

        try:
            result = cv2.cvtColor(img, code)

            # 信息
            info = f"{code_name}: {result.shape[1]}x{result.shape[0]}"
            if len(result.shape) == 2:
                info += ", 灰度图"
            else:
                info += f", {result.shape[2]}通道"

            return {"image": result, "info": info}
        except Exception as e:
            self._event_bus.emit_log("ERROR", f"颜色转换失败: {str(e)}")
            return {"image": None, "info": f"转换失败: {str(e)}"}