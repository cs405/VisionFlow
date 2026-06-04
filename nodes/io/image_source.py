"""
图像源节点 - 从文件或摄像头读取图像
"""

import cv2
import numpy as np
from typing import Any, Dict, Optional

from core.node_base import NodeBase, Socket, NodeParameter, ParamType
from core.data_packet import DataType


class ImageSourceNode(NodeBase):
    """
    图像源节点
    从文件路径或摄像头ID读取图像
    """

    def __init__(self, node_id: str = None):
        super().__init__(node_id)
        self.name = "图像源"
        self.category = "输入输出"
        self.description = "从文件或摄像头读取图像"

        # 输出端口
        self.output_sockets = [
            Socket("image", DataType.IMAGE, is_input=False, description="输出图像"),
            Socket("info", DataType.STRING, is_input=False, description="图像信息")
        ]

        # 参数
        self.parameters = {
            "source_type": NodeParameter(
                name="source_type",
                label="源类型",
                type=ParamType.ENUM,
                default="file",
                options=["file", "camera"]
            ),
            "file_path": NodeParameter(
                name="file_path",
                label="文件路径",
                type=ParamType.STRING,
                default=""
            ),
            "camera_id": NodeParameter(
                name="camera_id",
                label="摄像头ID",
                type=ParamType.INT,
                default=0,
                min=0,
                max=10
            )
        }
        self._param_values = {k: p.default for k, p in self.parameters.items()}

        # 运行时状态
        self._camera = None
        self._current_image = None

    def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        source_type = self.get_param("source_type")

        if source_type == "file":
            return self._load_from_file()
        else:
            return self._load_from_camera()

    def _load_from_file(self) -> Dict[str, Any]:
        """从文件加载图像"""
        file_path = self.get_param("file_path")

        if not file_path:
            return {"image": None, "info": "未指定文件路径"}

        img = cv2.imread(file_path)
        if img is None:
            return {"image": None, "info": f"无法读取图像: {file_path}"}

        self._current_image = img
        info = f"{img.shape[1]}x{img.shape[0]}, {file_path.split('/')[-1]}"

        return {"image": img, "info": info}

    def _load_from_camera(self) -> Dict[str, Any]:
        """从摄像头加载图像"""
        camera_id = self.get_param("camera_id")

        # 打开摄像头
        if self._camera is None:
            self._camera = cv2.VideoCapture(camera_id)
            if not self._camera.isOpened():
                self._camera = None
                return {"image": None, "info": f"无法打开摄像头 {camera_id}"}

        # 读取帧
        ret, frame = self._camera.read()
        if not ret:
            return {"image": None, "info": "读取摄像头失败"}

        self._current_image = frame
        info = f"摄像头 {camera_id}, {frame.shape[1]}x{frame.shape[0]}"

        return {"image": frame, "info": info}

    def on_param_changed(self, name: str, value: Any):
        """参数改变时释放摄像头"""
        if name == "source_type" and value == "file":
            if self._camera:
                self._camera.release()
                self._camera = None

    def __del__(self):
        """析构时释放摄像头"""
        if hasattr(self, '_camera') and self._camera:
            self._camera.release()