"""
图像输出节点 - 保存图像到文件
"""

import cv2
import os
from typing import Any, Dict
from datetime import datetime

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class ImageSinkNode(NodeBase):
    """
    图像输出节点
    将图像保存到文件
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "图像输出"
        self.category = "输入输出"
        self.description = "将图像保存到文件"

        # 输入端口
        self.input_sockets = [
            Socket("image", DataType.IMAGE, is_input=True, description="输入图像"),
            Socket("auto_save", DataType.BOOL, is_input=True,
                   multi_connection=False, description="自动保存触发")
        ]

        # 输出端口
        self.output_sockets = [
            Socket("saved_path", DataType.STRING, is_input=False, description="保存路径")
        ]

        # 参数
        self.parameters = {
            "save_dir": NodeParameter(
                name="save_dir",
                label="保存目录",
                type=ParamType.STRING,
                default="./output"
            ),
            "file_prefix": NodeParameter(
                name="file_prefix",
                label="文件名前缀",
                type=ParamType.STRING,
                default="image"
            ),
            "auto_save_enabled": NodeParameter(
                name="auto_save_enabled",
                label="启用自动保存",
                type=ParamType.BOOL,
                default=False
            ),
            "quality": NodeParameter(
                name="quality",
                label="JPEG质量",
                type=ParamType.SLIDER,
                default=95,
                min=1,
                max=100
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

        self._last_saved_path = ""
        self._frame_count = 0

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        img = inputs.get("image")
        auto_save_trigger = inputs.get("auto_save", False)

        if img is None:
            return {"saved_path": ""}

        auto_save_enabled = self.get_param("auto_save_enabled")

        # 自动保存模式：每帧都保存
        if auto_save_enabled:
            self._save_image(img)
            return {"saved_path": self._last_saved_path}

        # 手动触发模式：收到触发信号才保存
        if auto_save_trigger and not auto_save_enabled:
            self._save_image(img)
            return {"saved_path": self._last_saved_path}

        return {"saved_path": self._last_saved_path}

    def _save_image(self, img):
        """保存图像"""
        save_dir = self.get_param("save_dir")
        prefix = self.get_param("file_prefix")
        quality = self.get_param("quality")

        # 创建目录
        os.makedirs(save_dir, exist_ok=True)

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}_{self._frame_count:04d}.jpg"
        filepath = os.path.join(save_dir, filename)

        # 保存图像
        cv2.imwrite(filepath, img, [cv2.IMWRITE_JPEG_QUALITY, quality])
        self._last_saved_path = filepath
        self._frame_count += 1

        self._event_bus.emit_log("INFO", f"图像已保存: {filepath}")